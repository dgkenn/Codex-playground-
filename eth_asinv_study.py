"""eth_asinv_study.py -- Avellaneda-Stoikov inventory-skewed maker on Kalshi ETH 15-min binary.

GOAL: does inventory-aware A-S quoting turn the DEAD naive two-sided box (-13c OOS, t=-15)
into +EV by avoiding the inventory accumulation that creates toxic completions?

MODEL (A-S adapted to a 15-min binary, |net|<=1 cap):
  microprice m_k     = mid_k (+ depth-imbalance tilt if available)
  reservation r_k    = m_k - q * gamma * sigma_k^2 * tau_k      (q in {-1,0,+1})
  optimal half-spread delta_k = gamma*sigma_k^2*tau_k/2 + (1/gamma)*ln(1+gamma/kappa)
  -> post bid_q = r_k - delta_k,  ask_q = r_k + delta_k  (in YES price units, cents).
  sigma_k = realized intra-window vol of the YES mid up to minute k (per-minute std of mid changes),
            expressed in PRICE units (cents/contract) so gamma*sigma^2*tau is in price units.

FILL MODEL (realistic, tape-replay -- the load-bearing part):
  We post resting quotes for minute k. A maker fill occurs ONLY when a taker crosses our quote in
  the next ~2 minutes (same horizon window_fills uses):
    resting bid at pb fills if a taker SELL prints at p <= pb   (someone hits our bid)
    resting ask at pa fills if a taker BUY  prints at p >= pa   (someone lifts our ask)
  Posting BEHIND the touch (wide A-S delta) -> fewer crossings -> lower fill prob (the realistic cost
  of inventory aversion). Posting at/through the touch -> fills like the naive box.
  We clamp quotes so we never post through the market (bid<=touch_bid, ask>=touch_ask is the passive
  side; we allow improving up to the touch). Inventory cap |net|<=1: if q=+1 we only post an ask
  (to reduce), if q=-1 only a bid; q=0 posts both. This IS the inventory-skew mechanism on a binary.

  Residual inventory at expiry settles at res_up (YES) / (1-res_up) (NO): the structural loss when
  price ran is exactly the inventory you are stuck with.

IS = first 60% of windows, OOS = last 40%. Maker fee = 0 (fee-advantaged).
"""
from __future__ import annotations
import sys, math
sys.path.insert(0, '/tmp/ev_asinv')
import numpy as np, pandas as pd

from ladder_baseline_study import load_parquet_windows, run_p0, full_metrics, parse_arr
from box_policy_ab import _vpin_buckets, _vpin_at


# ----------------------------------------------------------------------------
# Build a richer per-window structure straight from parquet (we need the raw
# book paths + tape, because A-S quotes at custom prices and must be re-filled).
# ----------------------------------------------------------------------------
def load_raw_windows(asset='eth'):
    hist = pd.read_parquet(f'/tmp/ev_asinv/hist_kalshi_{asset}15m.parquet')
    trades = pd.read_parquet(f'/tmp/ev_asinv/trades_kalshi_{asset}15m.parquet')
    hidx = {r['ws']: r for _, r in hist.iterrows()}
    tidx = {r['ws']: r for _, r in trades.iterrows()}
    common = sorted(set(hidx) & set(tidx))
    out = []
    for ws in common:
        h = hidx[ws]; t = tidx[ws]
        bid = parse_arr(h['bid_path']); ask = parse_arr(h['ask_path'])
        mid = parse_arr(h['mid_path']); spot = parse_arr(h['spot_path'])
        depth = parse_arr(h['vol_path']) if h.get('vol_path') is not None else np.full(15, np.nan)
        tape = (parse_arr(t['t']), parse_arr(t['p']), parse_arr(t['sz']),
                parse_arr(t['buy']).astype(bool))
        out.append(dict(ws=ws, res=int(h['res_up']), bid=bid, ask=ask, mid=mid,
                        spot=spot, depth=depth, tape=tape))
    return out


def realized_sigma_path(mid):
    """Per-minute realized vol of YES mid (price units, cents) up to each minute k.
    sigma_k = std of minute-to-minute mid changes observed in [0..k]. Floored to avoid 0."""
    sig = np.full(15, np.nan)
    dm = np.diff(mid)
    for k in range(15):
        seg = dm[:max(k, 1)]
        seg = seg[~np.isnan(seg)]
        s = seg.std(ddof=0) if len(seg) >= 2 else (abs(seg[0]) if len(seg) == 1 else 0.0)
        sig[k] = max(s, 0.005)   # floor 0.5c
    return sig


# ----------------------------------------------------------------------------
# A-S MAKER WALK (tape replay, one window)
#   gamma   : inventory risk aversion
#   kappa   : fill intensity (1/gamma*ln(1+gamma/kappa) term -> base spread)
#   base_extra : additive base half-spread floor (cents) on top of A-S delta
#   vpin_widen : if set, multiply delta by (1 + vpin_widen * max(0, vpin-vpin_ref)) (Glosten-Milgrom
#                adverse-selection widening); and PULL quotes entirely if vpin>vpin_pull.
# Returns (pnl_window, n_fills, residual_inv_settled, stranded_bool)
# ----------------------------------------------------------------------------
def as_walk_window(w, gamma, kappa, base_extra=0.0, vpin_widen=None, vpin_ref=0.42,
                   vpin_pull=None, skew_mult=1.0):
    bid, ask, mid, depth = w['bid'], w['ask'], w['mid'], w['depth']
    res = w['res']
    t_arr, p_arr, sz_arr, buy_arr = w['tape']
    ws = w['ws']
    sig_path = realized_sigma_path(mid)
    bt, bi = _vpin_buckets(t_arr, sz_arr, buy_arr)

    ln_term = (1.0 / gamma) * math.log(1.0 + gamma / kappa)   # constant base half-spread (price units)

    q = 0            # signed inventory in {-1,0,+1}
    open_leg = None  # dict with settle for the open leg (price paid relative to settlement)
    pnl = 0.0
    nf = 0

    for k in range(2, 13):
        b0, a0 = bid[k], ask[k]
        if np.isnan(b0) or np.isnan(a0):
            continue
        m = mid[k]
        if not (0.03 <= m <= 0.97):
            continue
        tau = (15 - k) / 15.0
        sig = sig_path[k]
        vp = _vpin_at(bt, bi, ws + 60 * k)
        vp = 0.42 if (vp is None or np.isnan(vp)) else vp

        # toxicity: pull quotes entirely under extreme VPIN
        if vpin_pull is not None and vp > vpin_pull:
            continue

        # A-S reservation price + half-spread (price/cent units)
        inv_skew = q * gamma * (sig ** 2) * tau * skew_mult
        r = m - inv_skew
        delta = gamma * (sig ** 2) * tau / 2.0 + ln_term + base_extra
        if vpin_widen is not None:
            delta *= (1.0 + vpin_widen * max(0.0, vp - vpin_ref))

        pb = r - delta     # our resting bid (YES)
        pa = r + delta     # our resting ask (YES)

        # Clamp: never post THROUGH the market (can't be a maker if crossing the touch).
        # Passive side: bid must be <= current ask touch's other side; practically we cap our bid at
        # the market bid touch b0 (improving in is allowed up to b0; deeper inside would cross).
        pb = min(pb, b0)
        pa = max(pa, a0)
        # also keep prices in (0,1)
        pb = min(max(pb, 0.01), 0.99)
        pa = min(max(pa, 0.01), 0.99)

        # Inventory cap drives WHICH side we post (the binary A-S skew):
        post_bid = (q <= 0)    # only add to a flat/short YES position
        post_ask = (q >= 0)    # only reduce / add NO

        # Replay tape over minute k+1..k+2 (same horizon as window_fills); first crossing fills.
        lo, hi = ws + 60 * (k + 1), ws + 60 * (k + 2)
        i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
        filled_side = None; fill_px = None
        for i in range(i0, i1):
            p, buy = p_arr[i], buy_arr[i]
            if post_bid and (not buy) and p <= pb + 1e-9:
                filled_side = 'bid'; fill_px = pb; break
            if post_ask and buy and p >= pa - 1e-9:
                filled_side = 'ask'; fill_px = pa; break

        if filled_side is None:
            continue

        nf += 1
        if filled_side == 'bid':
            # bought YES at fill_px -> settle res - fill_px
            step = +1; leg_settle = res - fill_px
        else:
            # sold YES (bought NO) at fill_px -> settle (1-res) - (1-fill_px) = fill_px - res
            step = -1; leg_settle = fill_px - res

        nn = q + step
        if abs(nn) > 1:
            continue  # cap guard (shouldn't trigger given post-side logic, but safe)
        if q != 0 and abs(nn) < abs(q):
            # pairing fill: realize both legs
            pnl += leg_settle + (open_leg if open_leg is not None else 0.0)
            open_leg = None
        else:
            open_leg = leg_settle
        q = nn

    # settle residual inventory at expiry (THE structural loss when price ran)
    stranded = open_leg is not None
    if stranded:
        pnl += open_leg
    return pnl, nf, stranded


def run_as(windows, ws_set=None, **kw):
    pnl_arr = []; nf_arr = []; st_arr = []
    for w in windows:
        if ws_set is not None and w['ws'] not in ws_set:
            continue
        pnl, nf, st = as_walk_window(w, **kw)
        pnl_arr.append(pnl); nf_arr.append(nf); st_arr.append(st)
    return np.array(pnl_arr, float), np.array(nf_arr, float), np.array(st_arr, bool)


# ----------------------------------------------------------------------------
# kappa calibration from the tape: A-S kappa = fill intensity decay with distance from mid.
# Empirically, P(fill within horizon | posting at distance d from mid) ~ exp(-kappa*d).
# We estimate kappa by: for each minute, distance of each taker print from mid, build the empirical
# arrival rate vs distance, fit log-linear slope. Reported in 1/price-cent units.
# ----------------------------------------------------------------------------
def calibrate_kappa(windows):
    dists = []
    for w in windows:
        mid = w['mid']; ws = w['ws']
        t_arr, p_arr, sz_arr, buy_arr = w['tape']
        for k in range(2, 13):
            m = mid[k]
            if np.isnan(m) or not (0.03 <= m <= 0.97):
                continue
            lo, hi = ws + 60 * k, ws + 60 * (k + 1)
            i0, i1 = np.searchsorted(t_arr, lo), np.searchsorted(t_arr, hi)
            for i in range(i0, i1):
                d = abs(p_arr[i] - m)
                if d > 0:
                    dists.append(d)
    dists = np.array(dists)
    if len(dists) < 50:
        return 20.0
    # exponential MLE: kappa_hat = 1/mean(distance)
    kappa = 1.0 / dists.mean()
    return kappa, dists


# ----------------------------------------------------------------------------
def fmt_row(lbl, m, nf=None, st=None):
    extra = ''
    if nf is not None:
        extra += f" fills/win={nf:>5.2f}"
    if st is not None:
        extra += f" strand={st*100:>4.1f}%"
    return (f"{lbl:<30} net={m['nc']:>+7.2f}c sh={m['sh']:>+6.3f} "
            f"wr={m['wr']:>4.1f}% t={m['ts']:>+6.2f} n={m['n']:>4d}" + extra)


def main():
    print("=" * 92)
    print("ETH A-S INVENTORY-SKEWED MAKER")
    print("=" * 92)

    windows = load_raw_windows('eth')
    n = len(windows)
    cut = int(n * 0.6)
    ws_all = [w['ws'] for w in windows]
    is_set = set(ws_all[:cut]); oos_set = set(ws_all[cut:])
    print(f"ETH windows: {n}  IS={len(is_set)}  OOS={len(oos_set)}")

    # --- baselines (naive box P0) via harness, on matching windows ---
    fills_eth, ws_h = load_parquet_windows('eth')
    cuth = int(len(ws_h) * 0.6)
    ws_is_h, ws_oos_h = ws_h[:cuth], ws_h[cuth:]
    p0_is, p0st_is = run_p0(fills_eth, ws_is_h)
    p0_oos, p0st_oos = run_p0(fills_eth, ws_oos_h)
    mp0i = full_metrics(p0_is, p0_is, p0_is)
    mp0o = full_metrics(p0_oos, p0_oos, p0_oos)

    # --- kappa calibration ---
    kappa, dists = calibrate_kappa(windows)
    sig_samples = [realized_sigma_path(w['mid'])[7] for w in windows]
    sig_med = float(np.median(sig_samples))
    print(f"\nCALIBRATION:")
    print(f"  kappa (fill intensity, 1/cent) = {kappa:.2f}  (mean taker dist from mid = {dists.mean()*100:.2f}c, n={len(dists)})")
    print(f"  sigma (realized YES-mid vol @ k=7, median) = {sig_med*100:.2f}c  -> sigma^2={sig_med**2*100:.3f}c-units")
    print(f"  P0 naive box IS  net={mp0i['nc']:+.2f}c  OOS net={mp0o['nc']:+.2f}c  (the DEAD baseline)")

    # gamma we report calibration around. base_extra=0 = pure A-S spread.
    GAMMA0 = 1.5
    print(f"\n=== A-S vs NAIVE BOX vs P0 (gamma={GAMMA0}, kappa={kappa:.1f}, base_extra=0) ===")
    print("-- IS --")
    print(fmt_row("P0 naive box (dead)", mp0i, nf=None, st=p0st_is.mean()))
    asi, asnfi, asti = run_as(windows, is_set, gamma=GAMMA0, kappa=kappa)
    mas_i = full_metrics(asi)
    print(fmt_row("A-S inventory maker", mas_i, nf=asnfi.mean(), st=asti.mean()))
    print("-- OOS --")
    print(fmt_row("P0 naive box (dead)", mp0o, nf=None, st=p0st_oos.mean()))
    aso, asnfo, asto = run_as(windows, oos_set, gamma=GAMMA0, kappa=kappa)
    mas_o = full_metrics(aso)
    print(fmt_row("A-S inventory maker", mas_o, nf=asnfo.mean(), st=asto.mean()))

    # --- GAMMA + base-spread sweep (OOS, with IS shown) ---
    print(f"\n=== GAMMA x BASE-SPREAD SWEEP (kappa={kappa:.1f}) ===")
    print(f"{'gamma':>6} {'base_c':>7} | {'IS net':>8} {'IS t':>6} {'IS f/w':>6} | "
          f"{'OOS net':>8} {'OOS sh':>7} {'OOS t':>6} {'OOS f/w':>6} {'strand':>7}")
    print("-" * 92)
    best = None
    for gamma in [0.25, 0.5, 1.0, 1.5, 2.5, 4.0, 6.0]:
        for be in [0.0, 0.005, 0.01, 0.02]:
            ai, nfi, sti = run_as(windows, is_set, gamma=gamma, kappa=kappa, base_extra=be)
            ao, nfo, sto = run_as(windows, oos_set, gamma=gamma, kappa=kappa, base_extra=be)
            mi = full_metrics(ai); mo = full_metrics(ao)
            if not mi or not mo:
                continue
            print(f"{gamma:>6.2f} {be*100:>6.1f}c | {mi['nc']:>+7.2f}c {mi['ts']:>+6.2f} {nfi.mean():>6.2f} | "
                  f"{mo['nc']:>+7.2f}c {mo['sh']:>+6.3f} {mo['ts']:>+6.2f} {nfo.mean():>6.2f} {sto.mean()*100:>6.1f}%")
            # pick best by IS net then require OOS>=0 ish
            key = mi['nc']
            if best is None or key > best[0]:
                best = (key, gamma, be, mi, mo, nfi.mean(), nfo.mean(), sti.mean(), sto.mean())

    print(f"\nBest-by-IS-net: gamma={best[1]} base_extra={best[2]*100:.1f}c "
          f"-> IS {best[3]['nc']:+.2f}c (t={best[3]['ts']:+.2f}), OOS {best[4]['nc']:+.2f}c "
          f"(sh={best[4]['sh']:+.3f}, t={best[4]['ts']:+.2f}), OOS fills/win={best[6]:.2f}, strand={best[8]*100:.1f}%")

    # --- TOXICITY EXTENSION: A-S + VPIN widening / pull, on the best gamma ---
    gbest = best[1]; bebest = best[2]
    print(f"\n=== TOXICITY EXTENSION (gamma={gbest}, base_extra={bebest*100:.1f}c) ===")
    print(f"{'variant':<34} | {'IS net':>8} {'IS t':>6} | {'OOS net':>8} {'OOS sh':>7} {'OOS t':>6} {'f/w':>6} {'strand':>7}")
    print("-" * 92)
    def show(lbl, **kw):
        ai, nfi, sti = run_as(windows, is_set, gamma=gbest, kappa=kappa, base_extra=bebest, **kw)
        ao, nfo, sto = run_as(windows, oos_set, gamma=gbest, kappa=kappa, base_extra=bebest, **kw)
        mi = full_metrics(ai); mo = full_metrics(ao)
        print(f"{lbl:<34} | {mi['nc']:>+7.2f}c {mi['ts']:>+6.2f} | "
              f"{mo['nc']:>+7.2f}c {mo['sh']:>+6.3f} {mo['ts']:>+6.2f} {nfo.mean():>6.2f} {sto.mean()*100:>6.1f}%")
        return mi, mo, nfo.mean(), sto.mean()
    show("A-S only (no tox)")
    show("A-S + VPIN widen 3x", vpin_widen=3.0)
    show("A-S + VPIN widen 6x", vpin_widen=6.0)
    show("A-S + VPIN pull>0.55", vpin_pull=0.55)
    show("A-S + VPIN pull>0.50", vpin_pull=0.50)
    show("A-S + widen3 + pull0.55", vpin_widen=3.0, vpin_pull=0.55)
    show("A-S + widen6 + pull0.50", vpin_widen=6.0, vpin_pull=0.50)

    # --- aggressive-skew test: does strong skew help or just kill volume? ---
    print(f"\n=== SKEW-AGGRESSION (gamma={gbest}): skew_mult on the inventory term ===")
    print(f"{'skew_mult':>10} | {'OOS net':>8} {'OOS t':>6} {'f/w':>6} {'strand':>7}")
    print("-" * 60)
    for sm in [0.0, 1.0, 2.0, 4.0]:
        ao, nfo, sto = run_as(windows, oos_set, gamma=gbest, kappa=kappa, base_extra=bebest, skew_mult=sm)
        mo = full_metrics(ao)
        print(f"{sm:>10.1f} | {mo['nc']:>+7.2f}c {mo['ts']:>+6.2f} {nfo.mean():>6.2f} {sto.mean()*100:>6.1f}%")

    print("\nDONE.")


if __name__ == '__main__':
    main()
