"""kalshi_opt.py -- find the BEST Kalshi 15-min maker strategy on the real trade tape, judged by
the full METRICS.md battery (not net alone).

SEARCH SPACE (the maker family; directional is a settled null -- directional_deep 0/36):
  placement   join the touch (q_ahead scenario) | IMPROVE one 0.1c micro-tick to the front
  gate        none | sided past-spot-move pull: theta bps over lag minutes (pull the side the spot
              move runs against; quote the safe side) -- theta x lag grid
  rest-window minutes [m0, m1) of the 15 (skip the open chaos / the terminal minutes)
  band        none | skip mid-zone | skip tails (price-level toxicity shape)

FILL MODEL (tape-replay, counterfactual-honest): an IMPROVED bid at b0+tick is FRONT of book; any
taker SELL print at p <= b0 within the rest minute fills it (the print would have hit us first).
A JOINED bid fills only when prints exhaust q_ahead. Symmetric for asks. Fills held to settlement.
Costs: maker fee 0 (verify schedule); the improve tick is paid in the fill price itself.

PROTOCOL: select on IS (first 60% of windows, by Calmar then net t), confirm on OOS (last 40%);
winner gets the FULL battery: net/win + t, Sortino, MDD, Calmar, ProfitFactor, win%, W/L, Ulcer,
time-under-water, skew, Monte-Carlo bootstrap %positive, walk-forward thirds, parameter
neighborhood sensitivity.       python kalshi_opt.py btc
"""
from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

TICK = 0.001


def battery(nets):
    """The METRICS.md suite on a per-window net series (ws order)."""
    x = np.asarray(nets, float)
    n = len(x)
    m = x.mean(); sd = x.std(ddof=1) if n > 1 else float("nan")
    t = m / (sd / np.sqrt(n)) if sd and sd > 0 else float("nan")
    downside = x[x < 0]
    sortino = m / (downside.std(ddof=1) / np.sqrt(1)) if len(downside) > 2 and downside.std(ddof=1) > 0 else float("nan")
    cum = np.cumsum(x); peak = np.maximum.accumulate(cum)
    dd = peak - cum; mdd = float(dd.max()) if n else 0.0
    calmar = (cum[-1] / mdd) if mdd > 1e-9 else float("inf")
    gp = x[x > 0].sum(); gl = -x[x < 0].sum()
    pf = gp / gl if gl > 0 else float("inf")
    winp = float((x > 0).mean())
    wl = (x[x > 0].mean() / -x[x < 0].mean()) if (x > 0).any() and (x < 0).any() else float("nan")
    ulcer = float(np.sqrt(np.mean(dd ** 2)))
    tuw = float((dd > 1e-9).mean())
    skew = float(((x - m) ** 3).mean() / sd ** 3) if sd and sd > 0 else float("nan")
    rng = np.random.default_rng(7)
    boots = [x[rng.integers(0, n, n)].mean() for _ in range(1000)]
    mc_pos = float(np.mean(np.array(boots) > 0))
    thirds = [x[i * n // 3:(i + 1) * n // 3].mean() for i in range(3)]
    return {"net/win": m, "t": t, "Sortino": sortino, "MDD": mdd, "Calmar": calmar,
            "PF": pf, "win%": winp * 100, "W/L": wl, "Ulcer": ulcer, "TUW%": tuw * 100,
            "skew": skew, "MC+%": mc_pos * 100, "walk3": thirds}


def load(asset):
    hist = pd.read_parquet(f"hist_kalshi_{asset}15m.parquet").set_index("ws")
    tap = pd.read_parquet(f"trades_kalshi_{asset}15m.parquet").set_index("ws")
    common = sorted(set(hist.index) & set(tap.index))
    W = []
    for w in common:
        h = hist.loc[w]; t = tap.loc[w]
        spot = np.asarray(h.spot_path, float)
        W.append({
            "ws": w, "res": float(h.res_up),
            "bid": np.asarray(h.bid_path, float), "ask": np.asarray(h.ask_path, float),
            "spot_l": np.concatenate([[np.nan], spot[:-1]]),   # close of bar k-1 = known at minute k
            "tt": np.asarray(t.t, float), "tp": np.asarray(t.p, float),
            "tsz": np.asarray(t.sz, float), "tbuy": np.asarray(t.buy, bool),
        })
    return W


def run_cfg(W, improve, gate, m0, m1, band, q0=0.0):
    """gate: None or (theta_bps, lag_min). Returns per-window nets (ws order)."""
    nets = np.zeros(len(W))
    for i, w in enumerate(W):
        res = w["res"]; bid = w["bid"]; ask = w["ask"]; spot_l = w["spot_l"]
        tt, tp, tsz, tbuy = w["tt"], w["tp"], w["tsz"], w["tbuy"]
        pnl = 0.0
        for k in range(m0, m1):
            b0, a0 = bid[k], ask[k]
            if np.isnan(b0) or np.isnan(a0):
                continue
            mid = (b0 + a0) / 2
            if band == "notmid" and 0.35 <= mid < 0.65:
                continue
            if band == "notail" and not (0.10 <= mid <= 0.90):
                continue
            rb = ra = True
            if gate is not None:
                th, lag = gate
                s_now, s_then = spot_l[k], spot_l[max(k - lag, 0)]
                if np.isnan(s_now) or np.isnan(s_then) or s_then <= 0:
                    rb = ra = False
                else:
                    mv = (s_now / s_then - 1) * 1e4
                    if abs(mv) > th:
                        rb, ra = mv > 0, mv < 0
            lo, hi = w["ws"] + 60 * (k + 1), w["ws"] + 60 * (k + 2)
            i0, i1 = np.searchsorted(tt, lo), np.searchsorted(tt, hi)
            if improve:
                pb, pa = round(b0 + TICK, 4), round(a0 - TICK, 4)
                if pa - pb < TICK:                       # 1-tick book: nothing to improve into
                    pb, pa = b0, a0
                fb = rb and np.any((~tbuy[i0:i1]) & (tp[i0:i1] <= b0 + 1e-9))
                fa = ra and np.any((tbuy[i0:i1]) & (tp[i0:i1] >= a0 - 1e-9))
                if fb:
                    pnl += res - pb
                if fa:
                    pnl += pa - res
            else:
                qb = qa = q0
                fb = fa = False
                for j in range(i0, i1):
                    if fb and fa:
                        break
                    if rb and not fb and not tbuy[j] and tp[j] <= b0 + 1e-9:
                        if qb >= tsz[j]:
                            qb -= tsz[j]
                        else:
                            pnl += res - b0; fb = True
                    if ra and not fa and tbuy[j] and tp[j] >= a0 - 1e-9:
                        if qa >= tsz[j]:
                            qa -= tsz[j]
                        else:
                            pnl += a0 - res; fa = True
        nets[i] = pnl
    return nets


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else "btc"
    W = load(asset)
    n = len(W); cut = int(n * 0.6)
    print(f"{asset}: {n} windows | IS {cut} / OOS {n - cut}\n")
    gates = [None] + [(th, lag) for th in (3, 5, 8, 12) for lag in (2, 3, 5)]
    cfgs = []
    for improve in (True, False):
        for gate in gates:
            for m0, m1 in ((2, 13), (2, 9), (5, 13), (3, 12)):
                for band in (None, "notmid", "notail"):
                    cfgs.append((improve, gate, m0, m1, band))
    print(f"searching {len(cfgs)} maker configs (placement x gate x window x band) ...")
    rows = []
    for c in cfgs:
        nets = run_cfg(W, *c)
        is_n, oos_n = nets[:cut], nets[cut:]
        cum = np.cumsum(is_n); mdd = float((np.maximum.accumulate(cum) - cum).max())
        cal = cum[-1] / mdd if mdd > 1e-9 else float("inf")
        rows.append((c, nets, is_n.mean(), cal, oos_n.mean()))
    # SELECT on IS Calmar (risk-adjusted, the project standard), top-10 -> confirm OOS
    rows.sort(key=lambda r: -(r[3] if np.isfinite(r[3]) else 1e9))
    print(f"\n{'cfg':>46} {'IS net':>8} {'IS Cal':>8} {'OOS net':>8} {'OOS t':>6}")
    best = None
    for c, nets, ism, cal, oosm in rows[:10]:
        oos = nets[cut:]
        t = oos.mean() / (oos.std(ddof=1) / np.sqrt(len(oos))) if oos.std(ddof=1) > 0 else float("nan")
        nm = (f"{'improve' if c[0] else 'join'}+{('g%g/%g' % c[1]) if c[1] else 'nogate'}"
              f"+m{c[2]}-{c[3]}+{c[4] or 'noband'}")
        print(f"{nm:>46} {ism * 100:>+8.2f} {cal:>8.1f} {oosm * 100:>+8.2f} {t:>+6.1f}")
        if best is None and oosm > 0 and t > 2:
            best = (nm, c, nets)
    if best is None:
        print("\nNo config positive OOS with t>2 -- report the top row's battery anyway.")
        c, nets, *_ = rows[0]
        best = ("top-IS", c, nets)
    nm, c, nets = best
    print(f"\n=== WINNER: {nm} -- FULL METRICS BATTERY ===")
    for half, xs in (("IS", nets[:cut]), ("OOS", nets[cut:]), ("FULL", nets)):
        b = battery(xs * 100)        # cents
        print(f"  [{half:>4}] " + "  ".join(
            f"{k}={v:+.2f}" if isinstance(v, float) else f"{k}={['%+.2f' % t for t in v]}"
            for k, v in b.items()))
    # parameter neighborhood sensitivity (gate theta +/- one step)
    if c[1] is not None:
        th, lag = c[1]
        print("\n  sensitivity (gate theta):")
        for th2 in (max(th - 2, 1), th, th + 2):
            nets2 = run_cfg(W, c[0], (th2, lag), c[2], c[3], c[4])
            print(f"    theta={th2}: OOS {nets2[cut:].mean() * 100:+.2f}c/win")


if __name__ == "__main__":
    main()
