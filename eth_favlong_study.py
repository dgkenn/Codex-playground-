"""eth_favlong_study.py -- Favorite-longshot bias test on Kalshi ETH 15-min binaries.

Data model (verified against parquet, 0% mismatch on 38k fills):
  Each fill is a position TAKEN at price `p` (the price actually paid).
    - side=='bid' : bought YES at price p ; position wins iff settle>0
    - side=='ask' : bought NO  at price p ; position wins iff settle>0
  settle == (1-p) if the position won, == -p if it lost.
  So `p` is ALWAYS the implied win-probability of the position bought, and
  the realized outcome of that position is (settle>0).

Favorite-longshot test: bucket every position by its price p (= implied prob),
compute realized win-rate, and compare to p. Favorites (high p) underpriced =>
win-rate > p. Longshots (low p) overpriced => win-rate < p.

We treat every fill as one "bettable" observation at price p. Because both sides
are present and prices are symmetric (a YES bid at p and the matching NO ask at
1-p are the two faces of the same window), the price axis is naturally covered
0..1 by combining both sides.

TAKER cost: crossing the spread costs half_spread = spread/2 (paid once on entry;
fee=0 on Kalshi crypto15m). A taker buying the favorite pays p + spread/2.

Author: ETH favorite-longshot screen.  Usage: python eth_favlong_study.py
Writes: ETH_FAVLONG.md
"""
from __future__ import annotations
import warnings; warnings.filterwarnings('ignore')
import sys; sys.path.insert(0, '/tmp/ev_favlong')
import numpy as np
from math import sqrt
from ladder_baseline_study import load_parquet_windows

Z = 1.96  # 95% CI


def wilson(k, n, z=Z):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (np.nan, np.nan, np.nan)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return phat, center - half, center + half


def collect_positions(fills_per_ws, ws_list):
    """Return list of dicts: one per fill, with p (implied prob of position bought),
    win (bool), spread, k, sig, side. p is the price paid = implied prob."""
    out = []
    for ws in ws_list:
        for f in fills_per_ws[ws]:
            out.append(dict(
                p=float(f['p']),
                win=bool(f['settle'] > 0),
                spread=float(f.get('spread', 0.02)),
                k=int(f.get('k', 7)),
                sig=float(f.get('sig', 0.0) or 0.0),
                side=f['side'],
                settle=float(f['settle']),
                ws=ws,
            ))
    return out


def calibration_table(pos, edges=None):
    if edges is None:
        edges = [round(x, 2) for x in np.arange(0.05, 1.0, 0.05)]
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sub = [r for r in pos if lo <= r['p'] < hi]
        n = len(sub)
        if n == 0:
            rows.append((lo, hi, 0, np.nan, np.nan, np.nan, np.nan, np.nan))
            continue
        k = sum(r['win'] for r in sub)
        mid = (lo + hi) / 2
        wr, ci_lo, ci_hi = wilson(k, n)
        bias = wr - mid  # realized minus implied; >0 = underpriced (favorite-like)
        rows.append((lo, hi, n, mid, wr, ci_lo, ci_hi, bias))
    return rows


def ev_per_trade(pos, thr, taker=True, slot=None, sig_dir=False):
    """Strategy: BUY the position whenever its price p >= thr (a favorite).
    EV/trade in $ per contract.
      win pays (1-p), loss pays -p, taker pays extra spread/2 on entry.
    Returns dict with n, winrate, ev, sharpe, tstat, pnl array."""
    pnl = []
    for r in pos:
        if r['p'] < thr:
            continue
        if slot is not None and not (slot[0] <= r['k'] <= slot[1]):
            continue
        p = r['p']
        cost = (r['spread'] / 2.0) if taker else 0.0
        # payoff of the bought position: settle already = (1-p) if win else -p
        x = r['settle'] - cost
        pnl.append(x)
    pnl = np.array(pnl, float)
    n = len(pnl)
    if n < 2:
        return dict(n=n, wr=np.nan, ev=np.nan, sh=np.nan, ts=np.nan, pnl=pnl)
    ev = pnl.mean()
    sd = pnl.std(ddof=1)
    sh = ev / sd if sd > 1e-12 else np.nan
    ts = ev / (sd / sqrt(n)) if sd > 1e-12 else np.nan
    wr = (pnl > 0).mean()
    return dict(n=n, wr=wr, ev=ev, sh=sh, ts=ts, pnl=pnl)


def main():
    print("Loading ETH...")
    fills, ws = load_parquet_windows('eth')
    cut = int(len(ws) * 0.6)
    ws_is, ws_oos = ws[:cut], ws[cut:]
    pos_all = collect_positions(fills, ws)
    pos_is = collect_positions(fills, ws_is)
    pos_oos = collect_positions(fills, ws_oos)
    print(f"positions: all={len(pos_all)} is={len(pos_is)} oos={len(pos_oos)}")

    out = []
    def w(s=""):
        out.append(s); print(s)

    w("# ETH 15-min Favorite-Longshot Bias Study")
    w("")
    w(f"- Data: Kalshi ETH 15-min binaries. {len(ws)} windows, {len(pos_all)} position-fills.")
    w(f"- IS=first 60% ({len(ws_is)} win, {len(pos_is)} fills), OOS=last 40% ({len(ws_oos)} win, {len(pos_oos)} fills).")
    w("- Each fill = a position bought at price `p` (= implied win-prob). `win = settle>0`. Verified settle=(1-p) if win else -p, 0% mismatch.")
    w("- Taker cost = spread/2 (fee=0). Favorite = high p.")
    w("")

    # ---- TASK 1: CALIBRATION ----
    w("## 1. Calibration curve (favorite-longshot test)")
    w("")
    w("Realized win-rate vs implied prob (price), per 0.05 bucket, both sides combined. "
      "bias = realized - implied (>0 = underpriced/favorite-like, <0 = overpriced/longshot).")
    w("")
    w("| price bucket | n | implied | realized WR | 95% CI | bias (pp) |")
    w("|---|---|---|---|---|---|")
    for lo, hi, n, mid, wr, cl, ch, bias in calibration_table(pos_all):
        if n == 0:
            w(f"| {lo:.2f}-{hi:.2f} | 0 | {(lo+hi)/2:.3f} | - | - | - |")
        else:
            w(f"| {lo:.2f}-{hi:.2f} | {n} | {mid:.3f} | {wr:.3f} | [{cl:.3f},{ch:.3f}] | {bias*100:+.1f} |")
    w("")
    # Aggregate favorite vs longshot
    fav = [r for r in pos_all if r['p'] >= 0.70]
    lsh = [r for r in pos_all if r['p'] <= 0.30]
    for lbl, sub in [("FAVORITES p>=0.70", fav), ("LONGSHOTS p<=0.30", lsh)]:
        n = len(sub); k = sum(r['win'] for r in sub)
        meanp = np.mean([r['p'] for r in sub])
        wr, cl, ch = wilson(k, n)
        w(f"- **{lbl}**: n={n}, mean implied={meanp:.3f}, realized WR={wr:.3f} [{cl:.3f},{ch:.3f}], "
          f"bias={(wr-meanp)*100:+.1f}pp")
    w("")

    # IS/OOS calibration stability for favorites
    w("### IS/OOS stability of the favorite bias")
    w("")
    w("| split | slice | n | mean implied | realized WR | bias (pp) |")
    w("|---|---|---|---|---|---|")
    for split, ps in [("IS", pos_is), ("OOS", pos_oos)]:
        for lbl, cond in [("p>=0.70", lambda r: r['p'] >= 0.70),
                          ("p>=0.80", lambda r: r['p'] >= 0.80),
                          ("p<=0.30", lambda r: r['p'] <= 0.30)]:
            sub = [r for r in ps if cond(r)]
            n = len(sub)
            if n == 0:
                continue
            k = sum(r['win'] for r in sub); mp = np.mean([r['p'] for r in sub])
            wr, _, _ = wilson(k, n)
            w(f"| {split} | {lbl} | {n} | {mp:.3f} | {wr:.3f} | {(wr-mp)*100:+.1f} |")
    w("")

    # ---- TASK 2: TAKER SWEEP ----
    w("## 2. Taker strategy: buy favorites crossing the spread")
    w("")
    w("Buy every position with p>=thr as a taker (pay p+spread/2). EV/trade in cents/contract.")
    w("")
    w("| thr | split | n | hit-rate | EV/trade (c) | Sharpe | t-stat |")
    w("|---|---|---|---|---|---|---|")
    thrs = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
    for thr in thrs:
        for split, ps in [("ALL", pos_all), ("IS", pos_is), ("OOS", pos_oos)]:
            d = ev_per_trade(ps, thr, taker=True)
            if d['n'] < 2:
                w(f"| {thr:.2f} | {split} | {d['n']} | - | - | - | - |")
            else:
                w(f"| {thr:.2f} | {split} | {d['n']} | {d['wr']:.3f} | {d['ev']*100:+.2f} | {d['sh']:+.3f} | {d['ts']:+.2f} |")
    w("")
    # zero-cost (maker-ideal) reference
    w("Same sweep with NO spread cost (idealized maker fill, theta only):")
    w("")
    w("| thr | split | n | EV/trade (c) | Sharpe | t-stat |")
    w("|---|---|---|---|---|---|")
    for thr in thrs:
        for split, ps in [("ALL", pos_all), ("OOS", pos_oos)]:
            d = ev_per_trade(ps, thr, taker=False)
            if d['n'] < 2:
                continue
            w(f"| {thr:.2f} | {split} | {d['n']} | {d['ev']*100:+.2f} | {d['sh']:+.3f} | {d['ts']:+.2f} |")
    w("")

    # SELL/avoid longshots: a "sell longshot" = buy the opposite favorite, already covered.
    w("### Selling longshots")
    w("On a binary, selling a longshot at price q (q<=0.30) == buying the opposing favorite "
      "at 1-q (>=0.70). The dataset already contains both faces of every window, so the "
      "favorite-buy sweep above subsumes the sell-longshot trade. No separate edge exists "
      "beyond what the favorite buckets show.")
    w("")

    # ---- TASK 3: ONE-SIDED MAKER ----
    w("## 3. One-sided favorite maker vs taker")
    w("")
    w("A resting bid on the favored side fills at the bid (no spread crossed) but only when "
      "the tape trades through it. We approximate the maker as the SAME favorite positions at "
      "ZERO spread cost (best case) and at HALF the taker cost (a mid-ish fill). Maker realism: "
      "fills are adversely-selected (you fill more when about to lose), so true maker EV sits "
      "between the zero-cost and taker rows. We bracket it.")
    w("")
    w("| thr | mode | split | n | EV/trade (c) | Sharpe | t-stat |")
    w("|---|---|---|---|---|---|---|")
    for thr in [0.70, 0.75, 0.80]:
        for mode, costmul in [("taker(full spr)", 1.0), ("maker(half spr)", 0.5), ("maker(zero spr)", 0.0)]:
            for split, ps in [("OOS", pos_oos)]:
                pnl = []
                for r in ps:
                    if r['p'] < thr:
                        continue
                    pnl.append(r['settle'] - costmul * r['spread'] / 2.0)
                pnl = np.array(pnl, float)
                if len(pnl) < 2:
                    continue
                ev = pnl.mean(); sd = pnl.std(ddof=1)
                sh = ev / sd; ts = ev / (sd / sqrt(len(pnl)))
                w(f"| {thr:.2f} | {mode} | {split} | {len(pnl)} | {ev*100:+.2f} | {sh:+.3f} | {ts:+.2f} |")
    w("")

    # ---- TASK 4: REGIME / TIME ----
    w("## 4. Time/regime refinement (favorites p>=0.70, taker)")
    w("")
    w("### By k-slot (minute within window)")
    w("")
    w("| k-slot | split | n | hit-rate | EV/trade (c) | Sharpe | t-stat |")
    w("|---|---|---|---|---|---|---|")
    slots = [(2, 5), (6, 9), (10, 12), (9, 12), (2, 12)]
    for slo, shi in slots:
        for split, ps in [("ALL", pos_all), ("OOS", pos_oos)]:
            d = ev_per_trade(ps, 0.70, taker=True, slot=(slo, shi))
            if d['n'] < 2:
                continue
            w(f"| k {slo}-{shi} | {split} | {d['n']} | {d['wr']:.3f} | {d['ev']*100:+.2f} | {d['sh']:+.3f} | {d['ts']:+.2f} |")
    w("")

    # late-slot calibration bias
    w("### Late-slot (k>=9) calibration of favorites")
    w("")
    w("| split | slice | n | mean implied | realized WR | bias (pp) |")
    w("|---|---|---|---|---|---|")
    for split, ps in [("ALL", pos_all), ("IS", pos_is), ("OOS", pos_oos)]:
        sub = [r for r in ps if r['p'] >= 0.70 and r['k'] >= 9]
        n = len(sub)
        if n == 0:
            continue
        k = sum(r['win'] for r in sub); mp = np.mean([r['p'] for r in sub])
        wr, cl, ch = wilson(k, n)
        w(f"| {split} | p>=0.70 & k>=9 | {n} | {mp:.3f} | {wr:.3f} | {(wr-mp)*100:+.1f} |")
    w("")

    # ---- TASK 5: COST REALISM ----
    w("## 5. Cost realism")
    w("")
    w("Spread distribution for favorite (p>=0.70) positions:")
    favs = [r for r in pos_all if r['p'] >= 0.70]
    sprs = np.array([r['spread'] for r in favs])
    w("")
    for q in [0.25, 0.5, 0.75, 0.9]:
        w(f"- spread p{int(q*100)} = {np.quantile(sprs, q)*100:.1f}c")
    w(f"- mean spread = {sprs.mean()*100:.2f}c ; half-spread (taker cost) = {sprs.mean()*50:.2f}c")
    w("")
    # bias magnitude vs half-spread
    n = len(favs); k = sum(r['win'] for r in favs); mp = np.mean([r['p'] for r in favs])
    wr, cl, ch = wilson(k, n)
    gross_edge = (wr - mp)  # in $ per contract, the underpricing
    w(f"- Gross favorite underpricing edge = {gross_edge*100:+.2f}c/contract "
      f"(realized {wr:.3f} - implied {mp:.3f}).")
    w(f"- Taker half-spread cost = {sprs.mean()*50:.2f}c/contract.")
    w(f"- Net after taker cost = {gross_edge*100 - sprs.mean()*50:+.2f}c/contract.")
    w("")

    # trades-per-win for survivors
    d70 = ev_per_trade(pos_all, 0.70, taker=True)
    d70o = ev_per_trade(pos_oos, 0.70, taker=True)
    if d70['n'] > 0:
        tpw = 1.0 / d70['wr'] if d70['wr'] > 0 else np.inf
        w(f"- p>=0.70 taker ALL: {d70['n']} trades, {tpw:.2f} trades/win, EV={d70['ev']*100:+.2f}c, t={d70['ts']:+.2f}")
        w(f"- p>=0.70 taker OOS: {d70o['n']} trades, EV={d70o['ev']*100:+.2f}c, t={d70o['ts']:+.2f}")
    w("")

    with open('/tmp/ev_favlong/ETH_FAVLONG.md', 'w') as fh:
        fh.write("\n".join(out) + "\n")
    print("\nWROTE ETH_FAVLONG.md")


if __name__ == '__main__':
    main()
