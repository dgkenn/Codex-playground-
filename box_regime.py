"""box_regime.py -- WINDOW-SELECTION regime filter for the Kalshi BTC 15M maker-box.

Question: can we turn the box net-positive in AGGREGATE by choosing WHICH WINDOWS to trade
(a regime/time filter on features known BEFORE the window opens), even though per-OPEN toxicity
is unpredictable (BOX_ADVERSE_OPEN.md, AUC 0.56)?

Approach: reconstruct per-window box outcomes from the historical tape (gha_data collector streams,
the same fills box_policy_ab.py uses), compute per-window box net P&L (settle-adjusted, always-pair
P0) and strand flag, attach REGIME features (time-of-day, day-of-week, session, opening book
depth/spread, BTC realized vol, strand-streak, distance-to-round-strike), bucket on broad robust
cuts, and test the window-selection filter (good-regime-only vs always) net-of-volume + OOS.

Reuses box_policy_ab.py infrastructure (load_window_books, load_trades, per_minute_touch,
window_fills, pol_p0). Reproduce: python box_regime.py
"""
from __future__ import annotations
import glob, gzip, json, os, datetime as dt
import numpy as np
import pandas as pd

import box_policy_ab as ab

ASSET = "btc"
DATA_DIRS = sorted(glob.glob("gha_data/2026-*"))
STRAND_BE = 0.044   # break-even strand rate (BOX_SIZING_ALLOC: post-fix tox -15c -> 4.4%)
# clean edge / toxic loss for the LIVE-calibrated net model (cents/box)
CLEAN_C = 0.69
TOX_C = -15.0       # bounded post-fix disposal loss (give-cap 0.25); LIVE truth, see BOX_SIZING_ALLOC


def round_strike_dist(strike, spot):
    """Distance from settlement strike to the nearest $1000 round number, in $.
    Round-number strikes attract directional taker flow -> queue contention. Known at open
    (strike is set at window creation). Returns abs $ to nearest 1000, normalized 0..500."""
    if strike is None or strike <= 0:
        return None
    return abs(((strike + 500) % 1000) - 500)


def load_window_meta(paths, asset):
    """ws -> dict(strike, open_spot, floor_strike) from book meta records (known at open)."""
    meta = {}
    for d in paths:
        for fp in set(ab._rglob(d, f"book_kalshi_{asset}15m_*.jsonl.gz")):
            for r in ab.iter_gz(fp):
                if r.get("type") != "meta":
                    continue
                ws = r.get("ws"); m = r.get("meta") or {}
                if ws is None:
                    continue
                fs = ab._f(m.get("floor_strike"))
                if ws not in meta and fs is not None:
                    meta[ws] = {"floor_strike": fs,
                                "open_interest": ab._f(m.get("open_interest_fp")),
                                "volume": ab._f(m.get("volume_fp"))}
    return meta


def main():
    print(f"# data dirs: {DATA_DIRS}")
    books, res, oi_slope = ab.load_window_books(DATA_DIRS, ASSET)
    tapes = ab.load_trades(DATA_DIRS, ASSET)
    meta = load_window_meta(DATA_DIRS, ASSET)
    print(f"# windows with book: {len(books)}  with res: {len(res)}  with tape: {len(tapes)}  meta: {len(meta)}")

    rows = []
    for ws in sorted(books.keys()):
        if ws not in res or ws not in tapes:
            continue
        bid, ask, spot, depth = ab.per_minute_touch(books[ws], ws)
        r01 = res[ws]
        fills = ab.window_fills(ws, r01, bid, ask, spot, depth, tapes[ws], oi_slope.get(ws), q0=0.0)
        if not fills:
            continue
        # ----- per-window box outcome (always-pair P0; settle-adjusted, from fills) -----
        # pol_p0 returns summed settle of the always-pair walk (clean box ~ +spread, strand = big loss)
        net_p0 = ab.pol_p0(fills)        # $/contract summed across boxes in window (cents = *100)
        # strand detection: walk net; a window is STRANDED if it ends with an unpaired leg held to settle
        net = 0; stranded_leg = None; n_open = 0
        for f in fills:
            step = 1 if f["side"] == "bid" else -1
            nn = net + step
            if abs(nn) > 1:
                continue
            if net == 0 and nn != 0:
                stranded_leg = f; n_open += 1
            elif abs(nn) < abs(net):
                stranded_leg = None
            net = nn
        stranded = int(stranded_leg is not None)
        n_boxes = sum(1 for f in fills) // 2  # rough paired count
        # ----- regime features (known BEFORE / AT open) -----
        # opening book depth + spread = first valid minute's touch (k=0/1) -> proxy for "at open"
        open_depth = open_spread = open_mid = np.nan
        for k in range(0, 6):
            if not np.isnan(bid[k]) and not np.isnan(ask[k]):
                open_spread = ask[k] - bid[k]; open_mid = (bid[k] + ask[k]) / 2
                if not np.isnan(depth[k]):
                    open_depth = depth[k]
                break
        # BTC realized vol over the window's first ~3 min (proxy for entering-vol regime, causal-ish:
        # uses early-window spot moves; a true pre-open vol would need prior window -- approximated
        # below by recent_vol via prior-window close spot)
        sp = spot[~np.isnan(spot)]
        early_vol = np.nan
        ssub = spot[:5][~np.isnan(spot[:5])]
        if len(ssub) >= 2:
            rets = np.diff(ssub) / ssub[:-1]
            early_vol = np.std(rets) * 1e4  # bps
        m = meta.get(ws, {})
        strike = m.get("floor_strike")
        rsd = round_strike_dist(strike, open_mid)
        utc = dt.datetime.utcfromtimestamp(ws)
        rows.append({
            "ws": ws, "dt": utc, "hour": utc.hour, "dow": utc.weekday(),
            "net_c": net_p0 * 100.0, "stranded": stranded, "n_fills": len(fills),
            "open_depth": open_depth, "open_spread": open_spread * 100.0 if not np.isnan(open_spread) else np.nan,
            "early_vol_bps": early_vol, "round_dist": rsd, "oi": m.get("open_interest"),
        })

    df = pd.DataFrame(rows).sort_values("ws").reset_index(drop=True)
    df.to_csv("box_regime_windows.csv", index=False)
    n = len(df)
    print(f"\n# N windows (book+res+tape+fills): {n}")
    if n == 0:
        print("NO WINDOWS"); return df

    # recent vol: prior-window early_vol (autocorrelated regime, known before this window opens)
    df["prev_vol"] = df["early_vol_bps"].shift(1)
    df["prev_spread"] = df["open_spread"].shift(1)
    # strand streak: number of consecutive prior stranded windows (known before this opens)
    streak = []; s = 0
    for st in df["stranded"]:
        streak.append(s)        # streak BEFORE this window
        s = s + 1 if st else 0
    df["prev_strand_streak"] = streak
    df["prev_stranded"] = df["stranded"].shift(1).fillna(0).astype(int)

    base_strand = df["stranded"].mean()
    base_net = df["net_c"].mean()
    print(f"# BASELINE (all windows): strand={base_strand:.3f}  net={base_net:.3f} c/box-window  N={n}")
    print(f"# break-even strand ~= {STRAND_BE:.3f}")

    # ---- model net using LIVE-calibrated clean/tox (the from-fills net_c reflects q0=0 backtest
    #      strand which is optimistic; ALSO report a live-calibrated net = clean*(1-s) + tox*s) ----
    def live_net(strand):
        return CLEAN_C * (1 - strand) + TOX_C * strand

    print(f"# live-calibrated baseline net (clean {CLEAN_C}, tox {TOX_C}): {live_net(base_strand):.3f} c/box-window")

    def bucket_report(name, series, bins=None, qcut=None):
        print(f"\n## REGIME: {name}")
        d = df.dropna(subset=[series]) if series in df else df
        if qcut:
            try:
                d = d.assign(_b=pd.qcut(d[series], qcut, duplicates="drop"))
            except Exception:
                return
        elif bins is not None:
            d = d.assign(_b=pd.cut(d[series], bins))
        else:
            d = d.assign(_b=d[series])
        g = d.groupby("_b", observed=True).agg(
            n=("stranded", "size"), strand=("stranded", "mean"), net=("net_c", "mean"))
        g["live_net"] = live_net(g["strand"])
        g["frac_vol"] = g["n"] / n
        print(g.round(3).to_string())
        return g

    bucket_report("hour-of-day (UTC)", "hour")
    # session
    def sess(h):
        if 0 <= h < 8: return "Asia(0-8)"
        if 8 <= h < 13: return "EU(8-13)"
        return "US(13-24)"
    df["session"] = df["hour"].map(sess)
    bucket_report("session", "session")
    bucket_report("day-of-week", "dow")
    bucket_report("opening depth (top5 min)", "open_depth", qcut=4)
    bucket_report("opening spread (c)", "open_spread", qcut=3)
    bucket_report("prev-window vol (bps)", "prev_vol", qcut=4)
    bucket_report("prev-window spread (c)", "prev_spread", qcut=3)
    bucket_report("round-number dist ($)", "round_dist", qcut=4)
    bucket_report("prev strand streak", "prev_strand_streak")
    bucket_report("prev window stranded?", "prev_stranded")

    # ---- AUTOCORRELATION of strand (does it cluster?) ----
    s = df["stranded"].values.astype(float)
    if len(s) > 5:
        ac1 = np.corrcoef(s[:-1], s[1:])[0, 1]
        # P(strand | prev strand) vs P(strand | prev clean)
        prev = df["prev_stranded"].values
        p_after_strand = s[prev == 1].mean() if (prev == 1).any() else np.nan
        p_after_clean = s[prev == 0].mean() if (prev == 0).any() else np.nan
        print(f"\n## STRAND AUTOCORRELATION lag-1 r = {ac1:.3f}")
        print(f"   P(strand | prev stranded) = {p_after_strand:.3f}  (n={(prev==1).sum()})")
        print(f"   P(strand | prev clean)    = {p_after_clean:.3f}  (n={(prev==0).sum()})")

    # ---- FILTER TEST: run-box-only-in-good-regime vs always, net-of-volume + OOS split ----
    print("\n" + "=" * 70)
    print("## FILTER TESTS (good-regime-only vs always); OOS = last 30% of windows by time")
    print("=" * 70)
    split = int(n * 0.7)
    df_is = df.iloc[:split]; df_oos = df.iloc[split:]
    print(f"# IS n={len(df_is)}  OOS n={len(df_oos)}")

    def test_filter(name, mask_fn):
        m_all = mask_fn(df)
        m_is = mask_fn(df_is); m_oos = mask_fn(df_oos)
        def stats(d, m):
            dd = d[m]
            if len(dd) == 0:
                return (0, np.nan, np.nan, np.nan, 0.0)
            return (len(dd), dd["stranded"].mean(), dd["net_c"].mean(),
                    live_net(dd["stranded"].mean()), len(dd) / max(len(d), 1))
        na, sa, neta, lna, fva = stats(df, m_all)
        ni, si, neti, lni, fvi = stats(df_is, m_is)
        no_, so, neto, lno, fvo = stats(df_oos, m_oos)
        print(f"\n-- {name}")
        print(f"   ALL : n={na:4d} keep={fva:.2f} strand={sa:.3f} net(fill)={neta:+.3f} net(live)={lna:+.3f}")
        print(f"   IS  : n={ni:4d} keep={fvi:.2f} strand={si:.3f} net(fill)={neti:+.3f} net(live)={lni:+.3f}")
        print(f"   OOS : n={no_:4d} keep={fvo:.2f} strand={so:.3f} net(fill)={neto:+.3f} net(live)={lno:+.3f}")

    test_filter("(a) calm-vol-only (prev_vol < median)",
                lambda d: d["prev_vol"] < df["prev_vol"].median())
    test_filter("(b) deep-book-only (open_depth > median)",
                lambda d: d["open_depth"] > df["open_depth"].median())
    test_filter("(b2) deep-book top-quartile",
                lambda d: d["open_depth"] > df["open_depth"].quantile(0.75))
    test_filter("(c) US-hours only (13-24 UTC)",
                lambda d: (d["hour"] >= 13))
    test_filter("(c2) EU+US hours (8-24 UTC)",
                lambda d: (d["hour"] >= 8))
    test_filter("(d) strand-streak cooloff (skip after >=1 prev strand)",
                lambda d: d["prev_stranded"] == 0)
    test_filter("(d2) cooloff after >=2 streak",
                lambda d: d["prev_strand_streak"] < 2)
    test_filter("(e) tight-spread-only (open_spread <= 1c)",
                lambda d: d["open_spread"] <= 1.0)
    test_filter("(f) far-from-round-strike (round_dist > 250)",
                lambda d: d["round_dist"] > 250)
    test_filter("(combo) deep-book AND calm-vol",
                lambda d: (d["open_depth"] > df["open_depth"].median()) & (d["prev_vol"] < df["prev_vol"].median()))

    return df


if __name__ == "__main__":
    main()
