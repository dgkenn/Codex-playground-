"""
Hourly multi-strike crypto ladder cross-strike arbitrage SCREEN (mid-only).
Markets: KX{ETH,SOL,XRP,BTC}D hourly ladders. YES=price>=strike at close.

SCREENS (all on stored MID; bid/ask NOT available -> flag for re-fetch):
 1. Static cross-strike monotonicity: P(>=K) must be non-increasing in K at every (event,minute).
    A higher strike with a higher YES mid = monotonicity violation (potential lock).
 2. Vertical-spread / box consistency: adjacent vertical cost in [0,width(=1 for binary pair)];
    butterfly (long K1, short 2*K2, long K3) cost >=0. Negative-cost butterfly = riskless lock screen.
 3. Near-money efficiency + favorite-longshot: calibration of mid vs realized res in 0.1-0.9 band,
    binned; bias vs cost.
 4. Longer-tenor maker box estimate: strand-rate proxy via mid path NaN / settle-cross.

FEE MODEL (Kalshi taker): fee_per_ct = ceil(M*P*(1-P)*100)/100, M=0.07 std / 0.14 crypto-premium.
Maker ~0. A 2-leg arb pays ~2 taker fees + 2 half-spreads.
"""
import math
import numpy as np
import pandas as pd

ASSETS = ["eth", "sol", "xrp", "btc"]
M_STD, M_PREM = 0.07, 0.14


def taker_fee(p, M):
    p = min(max(p, 0.0), 1.0)
    return math.ceil(M * p * (1 - p) * 100) / 100.0


def load(asset):
    df = pd.read_parquet(f"ladder_{asset}_hourly.parquet")
    # explode mid path into a long per-minute frame keyed by (event, minute, strike)
    return df


def per_minute_snapshots(df):
    """Yield (event, minute, sub-df sorted by strike) where sub has mid at that minute (non-NaN)."""
    out = []
    for ev, g in df.groupby("event"):
        # build matrix: rows=strike-markets, cols=minute
        strikes = g["strike"].values
        res = g["res"].values
        mids = np.array([np.asarray(m, dtype=float) for m in g["mid"].values])  # (nstrike, 60)
        n_min = mids.shape[1]
        for t in range(n_min):
            col = mids[:, t]
            mask = ~np.isnan(col)
            if mask.sum() < 2:
                continue
            sk = strikes[mask]
            mv = col[mask]
            rs = res[mask]
            order = np.argsort(sk)
            out.append((ev, t, sk[order], mv[order], rs[order]))
    return out


def monotonicity_screen(df, asset):
    snaps = per_minute_snapshots(df)
    # A violation: at a (event,minute), exists i<j (strike_i < strike_j) with mid_i < mid_j - eps
    # (lower strike should have HIGHER-or-equal YES). Magnitude = max adjacent inversion.
    n_snap = len(snaps)
    viol_snaps = 0
    adj_inversions = []  # (event, minute, k_lo, k_hi, mid_lo, mid_hi, gap_cents)
    # persistence: track violations per (event, adjacent strike pair) across minutes
    pair_minutes = {}  # (event,klo,khi) -> list of minutes violated
    for ev, t, sk, mv, rs in snaps:
        snap_has = False
        for i in range(len(sk) - 1):
            lo, hi = sk[i], sk[i + 1]
            mlo, mhi = mv[i], mv[i + 1]
            # lower strike must have >= mid; violation if mlo < mhi
            gap = (mhi - mlo)
            if gap > 0:
                snap_has = True
                adj_inversions.append((ev, t, lo, hi, mlo, mhi, gap * 100))
                pair_minutes.setdefault((ev, lo, hi), []).append(t)
        if snap_has:
            viol_snaps += 1
    inv = pd.DataFrame(adj_inversions, columns=["event", "minute", "k_lo", "k_hi", "mid_lo", "mid_hi", "gap_cents"])
    # persistence: how many violated pairs persist >=3 consecutive-ish minutes
    persist = []
    for key, mins in pair_minutes.items():
        mins = sorted(mins)
        # longest run of consecutive minutes
        best = run = 1
        for a, b in zip(mins, mins[1:]):
            run = run + 1 if b == a + 1 else 1
            best = max(best, run)
        persist.append((key, len(mins), best))
    pdf = pd.DataFrame(persist, columns=["pair", "n_min_violated", "longest_consec_run"]) if persist else pd.DataFrame(columns=["pair","n_min_violated","longest_consec_run"])
    return {
        "n_snap": n_snap,
        "viol_snaps": viol_snaps,
        "viol_snap_pct": 100 * viol_snaps / n_snap if n_snap else 0,
        "n_adj_inversions": len(inv),
        "inv": inv,
        "persist": pdf,
    }


def net_edge_after_cost(gap_cents, p_lo, p_hi, M, half_spread_c):
    """A monotonicity lock: SELL the rich high-strike YES (mid p_hi), BUY the cheap low-strike YES (mid p_lo).
    Gross lock per pair (cents) = gap = (p_hi - p_lo)*100 (since low strike dominates high strike,
    the spread between them should be >=0; we collect gap). Cost = 2 taker fees + 2 half-spreads.
    """
    fee = taker_fee(p_lo, M) + taker_fee(p_hi, M)
    cost_c = fee * 100 + 2 * half_spread_c
    return gap_cents - cost_c


def vertical_box_screen(df):
    """Adjacent vertical cost = (mid_lo - mid_hi) must be in [0,1] (in prob). Negative = monotonicity (covered).
    Butterfly on 3 consecutive strikes K1<K2<K3: cost = mid1 - 2*mid2 + mid3 must be >=0.
    Negative-cost butterfly = riskless-lock screen. Report frequency & magnitude."""
    snaps = per_minute_snapshots(df)
    bad_fly = []
    n_fly = 0
    for ev, t, sk, mv, rs in snaps:
        for i in range(len(sk) - 2):
            n_fly += 1
            c = mv[i] - 2 * mv[i + 1] + mv[i + 2]
            if c < 0:
                bad_fly.append((ev, t, sk[i], sk[i + 1], sk[i + 2], c * 100))
    fdf = pd.DataFrame(bad_fly, columns=["event", "minute", "k1", "k2", "k3", "cost_cents"])
    return {"n_fly": n_fly, "n_bad_fly": len(fdf), "bad_fly": fdf}


def calibration_screen(df, lo=0.1, hi=0.9, nbins=8):
    """Near-money band: use last-available mid in window (proxy for steady-state price) vs realized res.
    Bin by mid, compare mean mid to realized win-rate (favorite-longshot)."""
    rows = []
    for _, r in df.iterrows():
        m = np.asarray(r["mid"], dtype=float)
        valid = m[~np.isnan(m)]
        if len(valid) == 0:
            continue
        # use median mid over window as representative price (robust to 1-min noise)
        p = np.median(valid)
        if lo <= p <= hi:
            rows.append((p, r["res"]))
    cdf = pd.DataFrame(rows, columns=["mid", "res"])
    if cdf.empty:
        return {"n": 0, "bins": pd.DataFrame()}
    cdf["bin"] = pd.cut(cdf["mid"], bins=np.linspace(0, 1, nbins + 1))
    agg = cdf.groupby("bin", observed=True).agg(n=("res", "size"), mean_mid=("mid", "mean"), win=("res", "mean"))
    agg["bias_c"] = (agg["win"] - agg["mean_mid"]) * 100  # +ve => realized > priced (mid too cheap)
    return {"n": len(cdf), "bins": agg, "overall_mid": cdf["mid"].mean(), "overall_win": cdf["res"].mean()}


def maker_box_estimate(df):
    """Longer-tenor maker box proxy. A maker box pairs a YES-maker fill + NO-maker fill (both ~mid).
    'Strand' risk ~ how often the near-money mid travels far before pairing. Proxy:
    for near-money markets (median mid 0.2-0.8), measure intra-window mid range (max-min) and
    terminal drift |last - first|. Lower range over 60min vs 15min => spread-capture more likely to survive.
    Report mean intra-window range and fraction of near-money markets whose mid crosses 0.5 (flip)."""
    ranges = []
    flips = 0
    n = 0
    for _, r in df.iterrows():
        m = np.asarray(r["mid"], dtype=float)
        v = m[~np.isnan(m)]
        if len(v) < 5:
            continue
        pmed = np.median(v)
        if not (0.2 <= pmed <= 0.8):
            continue
        n += 1
        ranges.append((v.max() - v.min()))
        if (v[0] - 0.5) * (v[-1] - 0.5) < 0:
            flips += 1
    return {"n_nearmoney": n, "mean_range_c": (np.mean(ranges) * 100) if ranges else float("nan"),
            "median_range_c": (np.median(ranges) * 100) if ranges else float("nan"),
            "flip_frac": flips / n if n else float("nan")}


def main():
    SPREAD_ASSUMPTIONS = [2.0, 4.0, 6.0]  # half-spread*2 not; these are HALF-spread cents assumed per leg
    print("=" * 78)
    print("HOURLY LADDER CROSS-STRIKE ARB SCREEN (mid-only)")
    print("=" * 78)
    summary = {}
    for asset in ASSETS:
        df = load(asset)
        mono = monotonicity_screen(df, asset)
        vb = vertical_box_screen(df)
        cal = calibration_screen(df)
        mk = maker_box_estimate(df)
        summary[asset] = (mono, vb, cal, mk, df)

        print(f"\n##### {asset.upper()}  rows={len(df)} events={df.event.nunique()} #####")
        print(f"[MONO] snapshots(>=2 strikes priced)={mono['n_snap']}  "
              f"snaps_with_violation={mono['viol_snaps']} ({mono['viol_snap_pct']:.2f}%)  "
              f"adj_inversions={mono['n_adj_inversions']}")
        if mono["n_adj_inversions"]:
            inv = mono["inv"]
            print(f"       gap_cents: mean={inv.gap_cents.mean():.2f} median={inv.gap_cents.median():.2f} "
                  f"p95={inv.gap_cents.quantile(.95):.2f} max={inv.gap_cents.max():.2f}")
            print(f"       persistence: violated pairs={len(mono['persist'])}, "
                  f"longest_consec_run>=3min in {(mono['persist'].longest_consec_run>=3).sum()} pairs")
            # net edge after cost across spread assumptions & fee models
            for M, mlab in [(M_STD, "std0.07"), (M_PREM, "prem0.14")]:
                for hs in SPREAD_ASSUMPTIONS:
                    nets = [net_edge_after_cost(g, plo, phi, M, hs)
                            for g, plo, phi in zip(inv.gap_cents, inv.mid_lo, inv.mid_hi)]
                    nets = np.array(nets)
                    prof = (nets > 0).sum()
                    print(f"       net(fee={mlab},halfsprd={hs}c/leg): profitable_inversions={prof}/{len(nets)} "
                          f"mean_net={nets.mean():.2f}c bestnet={nets.max():.2f}c")
        print(f"[FLY ] butterflies_checked={vb['n_fly']}  negative_cost(riskless screen)={vb['n_bad_fly']}")
        if vb["n_bad_fly"]:
            bf = vb["bad_fly"]
            print(f"       neg-cost cents: mean={bf.cost_cents.mean():.2f} min={bf.cost_cents.min():.2f}")
        if cal["n"]:
            print(f"[CAL ] near-money n={cal['n']} overall mid={cal['overall_mid']:.3f} win={cal['overall_win']:.3f} "
                  f"=> aggregate bias={ (cal['overall_win']-cal['overall_mid'])*100:.2f}c")
            print(cal["bins"][["n", "mean_mid", "win", "bias_c"]].to_string())
        print(f"[MAKE] near-money mkts n={mk['n_nearmoney']} mean_intrawin_range={mk['mean_range_c']:.1f}c "
              f"median={mk['median_range_c']:.1f}c flip(cross0.5)_frac={mk['flip_frac']:.3f}")
    return summary


if __name__ == "__main__":
    main()
