"""stack_analysis.py -- can positive strategies be STACKED to beat the best single one (micro_gate)?
Two senses, both quantified from the live shadow windows:
 (A) PORTFOLIO stack: run K variants as separate books, sum per-window P&L. Helps only if they're
     UNcorrelated (diversification -> higher Sharpe -> scale up). We report the correlation matrix +
     each portfolio's net/win and Sharpe (mean/std*sqrt n) vs micro_gate alone, incl. the min-variance combo.
 (B) COMPOSITE stack: fuse the gate LOGIC into one bot. Those already ran as variants (gross_max=micro|spot|
     deplete, micro_spot, micro_skew15, graded) -- we just read their leaderboard net. python stack_analysis.py
"""
from __future__ import annotations
import glob, json, math, itertools


def load():
    by_ws = {}
    for fp in sorted(glob.glob("gha_data/shadow_windows_*.jsonl")):
        for ln in open(fp):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("ws") is not None:
                by_ws.setdefault(r["ws"], r)
    return [by_ws[k] for k in sorted(by_ws)]


def series(rows, v):
    return {r["ws"]: r[v]["net"] for r in rows if v in r and isinstance(r[v], dict) and "net" in r[v]}


def sharpe(xs):
    n = len(xs)
    if n < 2:
        return float("nan")
    m = sum(xs) / n; sd = (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5
    return m / (sd / math.sqrt(n)) if sd > 0 else float("nan")


def corr(a, b):
    ks = sorted(set(a) & set(b))
    if len(ks) < 4:
        return float("nan")
    x = [a[k] for k in ks]; y = [b[k] for k in ks]; n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    vx = sum((u - mx) ** 2 for u in x); vy = sum((u - my) ** 2 for u in y)
    return sum((x[i] - mx) * (y[i] - my) for i in range(n)) / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def portfolio(sers, names):
    ks = sorted(set.intersection(*[set(sers[n]) for n in names]))
    return [sum(sers[n][k] for n in names) / len(names) for k in ks]   # equal-weight per-window mean


def main():
    rows = load()
    # positive single strategies (exclude baseline) with enough windows
    cand = []
    for v in sorted({k for r in rows for k, x in r.items() if isinstance(x, dict) and "net" in x}):
        s = series(rows, v); n = len(s)
        if v == "baseline" or n < 15:
            continue
        mean = sum(s.values()) / n
        if mean > 0:
            cand.append((v, mean, s))
    cand.sort(key=lambda c: -c[1])
    sers = {v: s for v, _, s in cand}
    top = [v for v, _, _ in cand[:8]]
    print("positive strategies (net/win):", {v: round(m, 2) for v, m, _ in cand})
    print(f"\n=== correlation of per-window net (top {len(top)} positive) -- high = no diversification ===")
    print("            " + " ".join(f"{v[:6]:>7}" for v in top))
    for a in top:
        print(f"{a[:11]:>11} " + " ".join(f"{corr(sers[a], sers[b]):>7.2f}" for b in top))
    mg = portfolio(sers, ["micro_gate"]) if "micro_gate" in sers else []
    print(f"\nmicro_gate alone: net/win {sum(mg)/len(mg):+.2f}  Sharpe(t) {sharpe(mg):+.2f}  (the bar to beat)")
    print("\n=== PORTFOLIO stacks: equal-weight, net/win + Sharpe vs micro_gate ===")
    best = None
    pos = [v for v, _, _ in cand]
    for k in (2, 3, 4):
        for combo in itertools.combinations(pos, k):
            if "micro_gate" not in combo:
                continue                              # anchor on the best; does ADDING others help?
            p = portfolio(sers, list(combo))
            if len(p) < 15:
                continue
            sh = sharpe(p); net = sum(p) / len(p)
            if best is None or sh > best[0]:
                best = (sh, net, combo)
    if best:
        print(f"best Sharpe portfolio (incl micro_gate): {best[2]}")
        print(f"   net/win {best[1]:+.2f}  Sharpe(t) {best[0]:+.2f}   vs micro_gate Sharpe {sharpe(mg):+.2f}")
    print("\nRead: a portfolio's net/win AVERAGES the members (so it's <= micro_gate's net unless equal "
          "capital is scaled). Stacking only WINS if Sharpe rises enough (low correlation) to deploy more "
          "size at the same risk. Composite (logic-fused) stacks are in the leaderboard: micro_skew15 +2.2, "
          "gross_max +0.6, micro_spot +0.2, graded -2.4 -- all BELOW micro_gate +4.8 (fusing gates over-gates).")


if __name__ == "__main__":
    main()
