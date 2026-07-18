#!/usr/bin/env python3
"""kwx_conviction_optimize.py -- grid-search the OPTIMAL conviction thresholds + cap, robustly.

Optimizes THREE knobs jointly on the real fires:
  - CUSHION threshold (deg F over strike): a fire is 'conviction' if cushion >= this   {1,2,3}
  - GAP threshold (cents): ...AND gap >= this                                          {5,10,15,20,25,30}
  - CONV cap: the per-fire bankroll fraction allowed on conviction fires               {5..25%}
Base (non-conviction) fires stay at 5% cap. Objective: MAX median growth s.t. ruin <= 0.5% and p5 >= start
(profit while minimizing risk). Reports the frontier + the robust PLATEAU (not a knife-edge), because a
single-point max on 65 summer days is overfit. Same honest stressors + 60%/day + depth caps as the sizing sim.

Usage: python kwx_conviction_optimize.py --bankroll 150 --latency 5 --trials 2500
"""
import argparse, statistics as st
from collections import defaultdict
import kwx_conviction_sizing as C   # reuse load_fires / simulate / cushion machinery


def load(latency):
    fires = C.load_fires(latency)
    by_day = defaultdict(list)
    for f in fires:
        by_day[f["date"]].append(f)
    return fires, by_day, list(by_day)


def tag(fires_by_day, cushion_thr, gap_thr):
    # re-tag conviction under candidate thresholds (mutates the per-fire 'conviction' flag)
    for day in fires_by_day.values():
        for f in day:
            f["conviction"] = (f["cushion"] >= cushion_thr and f["gap"] >= gap_thr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bankroll", type=float, default=150.0)  # small = the cap-binding regime (where this matters)
    ap.add_argument("--latency", type=int, default=5)
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--trials", type=int, default=2500)
    args = ap.parse_args()

    fires, by_day, day_keys = load(args.latency)
    print(f"conviction threshold optimization | ${args.bankroll:.0f} | {args.latency}min | {len(fires)} fires / "
          f"{len(day_keys)} days | grid x {args.trials} trials\n")

    rows = []
    for cush in (1, 2, 3):
        for gap in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
            tag(by_day, cush, gap)
            nconv = sum(1 for f in fires if f["conviction"])
            if nconv < 20:      # too few to matter/trust
                continue
            for cap in (0.05, 0.10, 0.15, 0.20, 0.25):
                m = C.simulate(by_day, day_keys, 0.05, cap, args.bankroll, args.days, args.trials, conv_tail=0.005)
                rows.append({"cush": cush, "gap": gap, "cap": cap, "nconv": nconv,
                             "med": m["median"] / args.bankroll, "p5": m["p5"] / args.bankroll,
                             "ruin": m["ruin"] * 100, "worst": m["worstday"] * 100})

    # frontier: ruin<=0.5% and p5>=1x; rank by median growth
    ok = [r for r in rows if r["ruin"] <= 0.5 and r["p5"] >= 1.0]
    ok.sort(key=lambda r: -r["med"])
    base = next((r for r in rows if r["cush"] == 1 and abs(r["gap"] - 0.05) < 1e-9 and abs(r["cap"] - 0.05) < 1e-9), None)
    print("=== TOP configs (ruin<=0.5%, p5>=1x), ranked by median growth ===")
    print(f"{'cushion':>8}{'gap':>6}{'cap':>6}{'nconv':>7}{'medianX':>9}{'p5X':>7}{'ruin%':>7}{'worstDay%':>11}")
    for r in ok[:14]:
        print(f"{r['cush']:>7}F{r['gap']*100:>5.0f}c{r['cap']*100:>5.0f}%{r['nconv']:>7}{r['med']:>8.1f}x"
              f"{r['p5']:>6.1f}x{r['ruin']:>7.2f}{r['worst']:>10.1f}")
    if base:
        print(f"\n  (baseline flat-5%: median {base['med']:.1f}x, p5 {base['p5']:.1f}x, ruin {base['ruin']:.2f}%)")

    # robustness: the PLATEAU -- best config, and how wide the near-optimal region is
    if ok:
        best = ok[0]
        near = [r for r in ok if r["med"] >= best["med"] * 0.995]  # within 0.5% of the max
        cushs = sorted(set(r["cush"] for r in near)); gaps = sorted(set(r["gap"] for r in near)); caps = sorted(set(r["cap"] for r in near))
        print(f"\n=== ROBUST PLATEAU (configs within 0.5% of the max median) ===")
        print(f"  n={len(near)} configs | cushion in {cushs}F | gap in {[int(g*100) for g in gaps]}c | cap in {[int(c*100) for c in caps]}%")
        print(f"  -> OPTIMAL (max median, robust): cushion>={best['cush']}F, gap>={int(best['gap']*100)}c, conv-cap {int(best['cap']*100)}%"
              f"  (median {best['med']:.1f}x vs base {base['med'] if base else float('nan'):.1f}x = +{100*(best['med']/base['med']-1):.0f}%)")


if __name__ == "__main__":
    main()
