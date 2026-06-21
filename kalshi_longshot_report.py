#!/usr/bin/env python3
"""kalshi_longshot_report.py -- the GO-LIVE readout for the longshot-maker harvest.

Reads the forward paper-track state (kalshi_longshot_paper.py output on the gha-data branch:
longshot_settled.csv + longshot_pending.json) and reports the realized forward edge, fill
proxy, by-category breakdown, and current open exposure -- so you can decide whether the live
+0.97c/contract backtest is confirmed out-of-sample before risking real money.

    python kalshi_longshot_report.py <state_dir>     # dir holding longshot_settled.csv / _pending.json
"""
import sys, os, csv, json, math
from collections import defaultdict

BACKTEST_EDGE_C = 0.97   # the in-sample net edge (cents/contract) we are validating forward


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    settled_p = os.path.join(d, "longshot_settled.csv")
    pend_p = os.path.join(d, "longshot_pending.json")

    rows = []
    if os.path.exists(settled_p):
        rows = list(csv.DictReader(open(settled_p)))
    pend = json.load(open(pend_p)) if os.path.exists(pend_p) else []

    print("=" * 64)
    print("LONGSHOT-MAKER HARVEST -- forward paper-track readout")
    print("=" * 64)

    # ---- current open exposure ----
    by_theme = defaultdict(int)
    for p in pend:
        by_theme[p.get("series", "?")] += 1
    print(f"\nOPEN paper positions: {len(pend)}  across {len(by_theme)} event-themes")
    if pend:
        cats = defaultdict(int)
        for p in pend:
            cats[p.get("category", "?")] += 1
        print("  by category: " + ", ".join(f"{k}:{v}" for k, v in sorted(cats.items(), key=lambda x: -x[1])))

    # ---- realized results ----
    if not rows:
        print("\nNo SETTLED paper positions yet. The edge is validated as snapshots resolve")
        print("(soft-market longshots can take days-weeks to settle). Re-run after they mature.")
        return
    n = len(rows)
    pnl = [float(r["pnl_per_contract"]) for r in rows]
    nowin = sum(1 for r in rows if r["result"] == "no")
    fills = [float(r.get("vol_after_entry", 0) or 0) for r in rows]
    mean_c = sum(pnl) / n * 100
    sd = (sum((x - sum(pnl)/n)**2 for x in pnl) / n) ** 0.5
    t = (sum(pnl)/n) / (sd / math.sqrt(n)) if sd else 0.0

    print(f"\nSETTLED paper positions: {n}")
    print(f"  realized edge      : {mean_c:+.2f} c/contract   (backtest was +{BACKTEST_EDGE_C:.2f}c)")
    print(f"  NO-win rate        : {nowin/n:.3f}   (longshots that did NOT hit = our wins)")
    print(f"  t-stat vs 0        : {t:+.2f}   (|t|>=2 => forward edge confirmed)")
    print(f"  total harvested    : {sum(pnl)*100:+.1f} c per 1-contract clip")
    print(f"  fill-proxy (vol after entry): median {sorted(fills)[len(fills)//2]:.0f} contracts traded post-snapshot")

    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(float(r["pnl_per_contract"]))
    print("\n  by category (realized c/contract):")
    for c, xs in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        print(f"    {c:>24}: n={len(xs):>4}  mean={sum(xs)/len(xs)*100:+.2f}c  NO-win={sum(1 for r in rows if r['category']==c and r['result']=='no')/len(xs):.2f}")

    print("\nGO-LIVE GATE: deploy real money (tiny clips) only when realized edge is positive AND")
    print("t>=2 AND the fill-proxy shows your resting quotes would actually get lifted. Until then,")
    print("the paper-track keeps accruing. (Backtest: +0.97c @17sigma; capacity ~$30-150/mo.)")


if __name__ == "__main__":
    main()
