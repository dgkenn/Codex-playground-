"""Gate on raising the cap (reviewer's challenge): cap 50->400 lifts $tot 18.5k->33.8k with
Sharpe still healthy, but as the cap rises we hold bigger unhedged residuals to a BINARY
resolution -- so the extra P&L could be riding a handful of lucky terminal settlements rather
than scaled edge. If so, 288-window Sharpe looks fine and still hands you a bad day live.

Checks (per-window P&L of the deployed skewed book at each cap):
  * top-k window share of the INCREMENTAL gain (cap400 - cap50);
  * leave-one-window-out: largest single-window share of total;
  * does per-window P&L correlate with |terminal move| (riding big settlements)?
  * jackknife Sharpe (drop the best 5 windows) -- does the edge survive?

    python cap_tail.py
"""
from __future__ import annotations

import numpy as np

from fairvalue import realized_vol_per_s
from fv_analysis import load_spot, load_trades
from hedge_sim import replay


def per_window(cols, bounds, res, ts_ms, px, cap):
    pnl = {}
    for w, (a, b) in bounds.items():
        g = {k: cols[k][a:b] for k in cols}
        cash, reb, ts, ups, dns, upf, dnf = replay(g, cap, skew_frac=0.25)
        r = res[w]; pnl[w] = cash + upf * r + dnf * (1 - r) + reb
    return pnl


def sh(a):
    a = np.asarray(a, float); m, s = a.mean(), a.std(ddof=1)
    return (m / s if s > 0 else np.nan)


def main():
    ts_ms, px = load_spot(); sigma = realized_vol_per_s(px, 1.0)
    allt = load_trades().sort_values(["win", "t_ms"])
    res = dict(zip(allt.win, allt.res)); wend = dict(zip(allt.win, allt.wend))
    cols = {c: allt[c].to_numpy() for c in ("win", "tok", "side", "price", "size", "t_ms")}
    wins_arr = allt.win.to_numpy(); order = np.arange(len(wins_arr))
    bounds = {w: (order[wins_arr == w][0], order[wins_arr == w][-1] + 1) for w in np.unique(wins_arr)}

    # |terminal move| per window = |log(S_end / S_open)|
    term = {}
    for w in bounds:
        s0 = px[np.clip(np.searchsorted(ts_ms, int(w) * 1000, "right") - 1, 0, len(px) - 1)]
        se = px[np.clip(np.searchsorted(ts_ms, int(wend[w]) * 1000, "right") - 1, 0, len(px) - 1)]
        term[w] = abs(np.log(se / s0))

    # --- cap frontier: jackknife Sharpe (drop best 5) vs total $; find any interior optimum ---
    print("cap frontier (jackknife Sharpe = drop best-5 windows; the luck-discounted metric):")
    print(f"  {'cap':>5} {'$tot':>9} {'mean$/w':>8} {'rawSharpe':>10} {'jkSharpe':>9} {'pos%':>6}")
    for cap in [5, 10, 25, 50, 100, 150, 200, 300, 400]:
        a = np.array(list(per_window(cols, bounds, res, ts_ms, px, cap).values()))
        print(f"  {cap:>5} {a.sum():>9,.0f} {a.mean():>8.2f} {sh(a):>10.3f} "
              f"{sh(np.sort(a)[:-5]):>9.3f} {(a>0).mean():>6.1%}")
    print("  -> jackknife Sharpe is MONOTONE DECREASING from cap~5; no interior optimum. The cap is"
          " a capacity dial: more $ for less (luck-adjusted) Sharpe, smoothly, no cliff.\n")

    p50 = per_window(cols, bounds, res, ts_ms, px, 50)
    p400 = per_window(cols, bounds, res, ts_ms, px, 400)
    wins = list(bounds)
    a50 = np.array([p50[w] for w in wins]); a400 = np.array([p400[w] for w in wins])
    tmove = np.array([term[w] for w in wins])

    for tag, a in (("cap=50", a50), ("cap=400", a400)):
        tot = a.sum(); pos = (a > 0).mean()
        srt = np.sort(a)[::-1]
        top5 = srt[:5].sum() / tot; top10 = srt[:10].sum() / tot
        jk = sh(a[np.argsort(a)[:-5]])                      # Sharpe dropping the best 5 windows
        c_term = np.corrcoef(a, tmove)[0, 1]
        print(f"{tag}: $tot={tot:,.0f} Sharpe={sh(a):+.3f} pos-windows={pos:.1%} | "
              f"top5={top5:.1%} top10={top10:.1%} of total | jackknife(-best5) Sharpe={jk:+.3f} | "
              f"corr(P&L,|term move|)={c_term:+.3f}")

    inc = a400 - a50; itot = inc.sum()
    isrt = np.sort(inc)[::-1]
    print(f"\nINCREMENTAL (cap400-cap50): $tot={itot:,.0f} | "
          f"top5 windows={isrt[:5].sum()/itot:.1%} top10={isrt[:10].sum()/itot:.1%} of the gain | "
          f"windows improved={ (inc>0).mean():.1%}")
    print(f"corr(incremental gain, |terminal move|) = {np.corrcoef(inc, tmove)[0,1]:+.3f}")
    big = tmove > np.quantile(tmove, 0.9)
    print(f"share of incremental gain from the top-decile |terminal move| windows = "
          f"{inc[big].sum()/itot:.1%} (those are {big.mean():.0%} of windows)")
    print("\nVERDICT: if top5/top10 share is modest, jackknife Sharpe stays healthy, and the gain "
          "is spread across windows (not concentrated in big-terminal-move windows), the cap is "
          "scaling EDGE. If the gain piles into a few large-move settlements, it's scaling tail "
          "risk that 288-window Sharpe hides -> raise the cap more cautiously.")


if __name__ == "__main__":
    main()
