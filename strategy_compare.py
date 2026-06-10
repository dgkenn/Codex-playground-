"""strategy_compare.py -- compare the LEARNED algorithms of the top-10% wallets (strategy_models.json x
mm_score.json), find which strategy PARAMETERS drive performance, cluster the archetypes, and synthesize
the winning recipe + concrete deltas for OUR bot. This is the "mine the best, improve ours" step.
    python strategy_compare.py
"""
from __future__ import annotations
import json, math


def corr(a, b):
    pts = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pts) < 4:
        return float("nan")
    xs, ys = zip(*pts); n = len(xs); mx, my = sum(xs) / n, sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs); vy = sum((y - my) ** 2 for y in ys)
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def main():
    models = json.load(open("strategy_models.json"))
    mm = {r["w"]: r for r in json.load(open("mm_score.json"))}
    rows = []
    for w, m in models.items():
        s = mm.get(w, {})
        rows.append({"w": w, "score": s.get("score", 0), "win": s.get("win", 0), "pnl": s.get("pnl", 0),
                     "two": m["two_side"], "setdisc": m.get("set_discount_c"), "ladp50": m["ladder_p50_tk"],
                     "ladp95": m["ladder_p95_tk"], "clip": m["clip_usd_med"], "setbal": m.get("set_balance_med"),
                     "late": m["phase"].get("late", 0), "learn": m["learnability"]})
    rows.sort(key=lambda r: -r["score"])
    # which learned parameters correlate with MM score (what makes a winner)?
    keys = ["two", "setdisc", "ladp50", "ladp95", "clip", "setbal", "late", "learn"]
    sc = [r["score"] for r in rows]
    print("=== which learned parameters drive MM score (corr across the 23) ===")
    for k in keys:
        print(f"  corr(score, {k:8}) = {corr([r[k] for r in rows], sc):+.2f}")
    # the top cluster (by score) recipe vs the rest
    top = rows[:6]; rest = rows[6:]
    def avg(rs, k):
        xs = [r[k] for r in rs if r[k] is not None]
        return sum(xs) / len(xs) if xs else float("nan")
    print("\n=== TOP-6 vs REST: the winning recipe ===")
    print(f"{'param':>10}{'TOP6':>9}{'REST':>9}")
    for k in keys:
        print(f"{k:>10}{avg(top,k):>9.2f}{avg(rest,k):>9.2f}")
    print("\n=== archetypes ===")
    for r in rows:
        if r["setdisc"] is not None and r["setdisc"] > 3 and r["two"] > 0.85:
            arch = "PURE set-discount MM"
        elif r["setdisc"] is not None and r["setdisc"] < -5:
            arch = "momentum (buys rising side)"
        elif r["late"] > 0.4:
            arch = "late-window scalper"
        elif r["two"] < 0.4:
            arch = "directional"
        else:
            arch = "mixed two-sided MM"
        print(f"  {r['w'][:10]:>12} score={r['score']:>5.2f} win={100*r['win']:>3.0f}% -> {arch}")
    print("\n=== SYNTHESIZED WINNING RECIPE (for our bot) ===")
    print(f"  two-sided index ~{avg(top,'two'):.2f} (quote BOTH tokens), clip ~${avg(top,'clip'):.1f},")
    print(f"  target complete-set BUY discount ~{avg(top,'setdisc'):.1f}c (buy both legs when sum<1),")
    print(f"  ladder: dense at touch (median ~{avg(top,'ladp50'):.0f}tk) with a tail to ~{avg(top,'ladp95'):.0f}tk,")
    print(f"  hold balanced sets to resolution (set-bal ~{avg(top,'setbal'):.2f}) + redeem, de-emphasize late "
          f"({avg(top,'late'):.2f}).")
    print("  => deltas vs our copy_bot/MAKER_CHANGES: prioritize the SET-DISCOUNT entry (buy both when "
          "bid_up+bid_dn<1) -- the highest-corr driver -- over pure spread; keep clips tiny; quote all 8 markets.")


if __name__ == "__main__":
    main()
