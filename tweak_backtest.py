"""Backtest candidate strategy TWEAKS on the historical tape (288 windows) with PAIRED
per-window significance, so we only adopt tweaks that are statistically real.

Why paired: every tweak replays the SAME windows as baseline, so the per-window
delta (tweak_net - base_net) cancels the huge shared window-outcome variance -> a real t.
We require paired |t| > 2.6 AND OOS-consistent (both halves same sign) to "graduate".

Honest fill-model caveat (see FINDINGS "CRITICAL CORRECTION"): this replay assumes we win
the opposite of every taker (optimistic gross). So:
  * tweaks acting on REBATE transfer to live (rebate is mechanical: fill -> earn it);
  * tweaks acting on GROSS may NOT transfer (live gross ~ 0). We print dNet, dRebate, dGross
    separately and flag any "win" that lives in the optimistic-gross component.

    python tweak_backtest.py
"""
from __future__ import annotations

import numpy as np

import fees
from fv_analysis import load_trades

REBATE = 0.07


def replay(g, cap=50, skew=0.25, buy_scale=1.0, mid_size=False, skip_lo=0.0, skip_hi=1.0):
    """Capped/skewed 2-sided maker over one window's (time-sorted) fills, with tweak hooks.
    Returns (gross, rebate). buy_scale scales maker-BUY (taker-SELL) fill size; mid_size
    weights size by 4p(1-p) (rebate-rich near 0.5); skip_lo/hi drop extreme-price fills."""
    tok = g["tok"]; side = g["side"]; price = g["price"]; size = g["size"]
    r = float(g["res"][0]) if len(g["res"]) else 0.0
    delta = cash = reb = up_inv = dn_inv = 0.0
    skewcap = skew * cap
    for i in range(len(price)):
        p = price[i]
        if p < skip_lo or p > skip_hi:
            continue
        is_up = (tok[i] == "U"); sells = (side[i] == "BUY"); sz = size[i]
        if not sells:
            sz *= buy_scale
        if mid_size:
            sz *= 4.0 * p * (1.0 - p)
        if sz <= 0:
            continue
        d_delta = (-sz if sells else sz) if is_up else (sz if sells else -sz)
        if abs(delta) >= skewcap and delta * d_delta > 0:
            continue
        if abs(delta + d_delta) > cap:
            room = max(0.0, cap - abs(delta)) if (delta + d_delta) * d_delta > 0 else sz
            fill = min(sz, room)
        else:
            fill = sz
        if fill <= 0:
            continue
        sign = 1.0 if sells else -1.0
        cash += sign * p * fill
        if is_up:
            up_inv += (-fill if sells else fill)
        else:
            dn_inv += (-fill if sells else fill)
        delta += (d_delta / (sz if sz else 1)) * fill
        reb += fees.maker_rebate(p, rate=REBATE) * fill
    gross = cash + up_inv * r + dn_inv * (1 - r)
    return gross, reb


def run_config(byw, **kw):
    """Per-window (gross, rebate, net) arrays for a config across all windows."""
    G, R = [], []
    for w in byw:
        gr, rb = replay(byw[w], **kw)
        G.append(gr); R.append(rb)
    G = np.array(G); R = np.array(R)
    return G, R, G + R


def paired(delta):
    d = np.asarray(delta, float); n = len(d); m = d.mean()
    s = d.std(ddof=1); t = m / (s / np.sqrt(n)) if s > 0 else np.nan
    bs = np.array([np.random.choice(d, n, replace=True).mean() for _ in range(5000)])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return m, t, lo, hi


def main():
    allt = load_trades().sort_values(["win", "t_ms"])
    cols = {c: allt[c].to_numpy() for c in ("win", "tok", "side", "price", "size", "res")}
    wa = allt.win.to_numpy(); o = np.arange(len(wa))
    order = np.unique(wa)
    byw = {}
    for w in order:
        idx = o[wa == w]; a, b = idx[0], idx[-1] + 1
        byw[w] = {k: cols[k][a:b] for k in cols}
    wins = list(byw); mid = np.median(wins)
    isw = [i for i, w in enumerate(wins) if w < mid]; oosw = [i for i, w in enumerate(wins) if w >= mid]
    print(f"historical windows={len(wins)} (IS={len(isw)} OOS={len(oosw)})\n")

    bG, bR, bN = run_config(byw, cap=50, skew=0.25)
    print(f"BASELINE cap50/skew0.25: net/win={bN.mean():+.3f}  (gross {bG.mean():+.3f} + rebate {bR.mean():+.3f})\n")

    tweaks = {
        "skew0.15":        dict(cap=50, skew=0.15),
        "skew0.40":        dict(cap=50, skew=0.40),
        "cap25":           dict(cap=25, skew=0.25),
        "cap100":          dict(cap=100, skew=0.25),
        "mid_weighted_sz": dict(cap=50, skew=0.25, mid_size=True),
        "buy_half":        dict(cap=50, skew=0.25, buy_scale=0.5),
        "buy_off":         dict(cap=50, skew=0.25, buy_scale=0.0),
        "skip_extremes":   dict(cap=50, skew=0.25, skip_lo=0.10, skip_hi=0.90),
    }
    print(f"{'tweak':>16} {'dNet/win':>9} {'paired t':>9} {'95% CI':>18} {'dGross':>8} {'dReb':>8} "
          f"{'OOS sign':>9} {'verdict':>22}")
    for name, kw in tweaks.items():
        G, R, N = run_config(byw, **kw)
        dN = N - bN; dG = G - bG; dR = R - bR
        m, t, lo, hi = paired(dN)
        is_m = dN[isw].mean(); oos_m = dN[oosw].mean()
        oos_ok = (np.sign(is_m) == np.sign(oos_m))
        graduates = (abs(t) > 2.6) and oos_ok and m > 0
        # transferability: is the win mostly in (optimistic) gross or in (real) rebate?
        src = "rebate(transfers)" if abs(dR.mean()) >= abs(dG.mean()) else "GROSS(may not transfer)"
        verdict = ("ADOPT:" + src) if graduates else ("worse" if m < 0 else "n.s.")
        print(f"{name:>16} {m:>+9.3f} {t:>+9.2f} [{lo:>+7.3f},{hi:>+7.3f}] {dG.mean():>+8.3f} "
              f"{dR.mean():>+8.3f} {'ok' if oos_ok else 'FLIP':>9} {verdict:>22}")
    print("\nGraduate = paired |t|>2.6 AND OOS-consistent AND net-positive. Then check the source: "
          "rebate-driven wins transfer to live; gross-driven wins are suspect (live gross ~ 0).")


if __name__ == "__main__":
    main()
