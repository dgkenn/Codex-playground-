"""insights.py -- regenerate the data-backed insights (INSIGHTS_4DAY.md) from the multi-asset shadow data.
Uses the FULL per-(asset,ws) window sample (leaderboard.py collapses by ws only) + the ungated fill tape.

    git fetch origin gha-data && git checkout origin/gha-data -- gha_data/
    python insights.py
"""
from __future__ import annotations
import glob, json, collections, math, statistics


def load_windows():
    rows = {}
    for fp in glob.glob("gha_data/shadow_windows_*.jsonl"):
        for ln in open(fp):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("ws") is not None and any(isinstance(v, dict) and "net" in v for v in r.values()):
                rows[(r.get("asset", "btc"), r["ws"])] = r          # full sample, keyed by (asset, ws)
    return rows


def load_fills():
    out = []
    for fp in glob.glob("gha_data/fills_*.jsonl"):
        for ln in open(fp):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("var") == "baseline" and r.get("reason") == "fill" and r.get("mo5") is not None:
                out.append(r)
    return out


def vstat(rows, v):
    s = [r[v]["net"] for r in rows.values() if isinstance(r.get(v), dict) and "net" in r[v]]
    if len(s) < 10:
        return None
    m = sum(s) / len(s); sd = statistics.pstdev(s)
    g = [r[v]["gross"] for r in rows.values() if isinstance(r.get(v), dict) and r[v].get("gross") is not None]
    return m, (m / (sd / math.sqrt(len(s))) if sd > 0 else 0.0), (sum(g) / len(g) if g else float("nan")), len(s)


def bucket(fills, fn, edges):
    g = collections.defaultdict(list)
    for r in fills:
        v = fn(r)
        if v is None:
            continue
        for lo, hi, nm in edges:
            if lo <= v < hi:
                g[nm].append(r["mo5"]); break
    return [(nm, sum(g[nm]) / len(g[nm]), len(g[nm])) for _, _, nm in edges if g[nm]]


def corr_pairs(rows, v, assets=("btc", "eth", "sol", "xrp")):
    d = collections.defaultdict(dict)
    for (a, w), r in rows.items():
        if isinstance(r.get(v), dict):
            d[a][w] = r[v]["net"]
    cs = []
    A = [a for a in assets if a in d]
    for i in range(len(A)):
        for j in range(i + 1, len(A)):
            ks = sorted(set(d[A[i]]) & set(d[A[j]]))
            if len(ks) >= 8:
                x = [d[A[i]][k] for k in ks]; y = [d[A[j]][k] for k in ks]; n = len(x)
                mx, my = sum(x) / n, sum(y) / n
                vx = sum((u - mx) ** 2 for u in x); vy = sum((u - my) ** 2 for u in y)
                if vx > 0 and vy > 0:
                    cs.append(sum((x[k] - mx) * (y[k] - my) for k in range(n)) / math.sqrt(vx * vy))
    return cs


def main():
    rows = load_windows()
    if not rows:
        print("no data. run: git fetch origin gha-data && git checkout origin/gha-data -- gha_data/")
        return
    fills = load_fills()
    print(f"windows={len(rows)}  fills={len(fills)}  assets={sorted({a for a,_ in rows})}\n")

    print("[1/2] top variants by net/win (full per-(asset,ws) sample):")
    tab = [(v, *vstat(rows, v)) for v in sorted({k for r in rows.values() for k, x in r.items()
            if isinstance(x, dict) and "net" in x}) if vstat(rows, v)]
    for v, m, t, g, n in sorted(tab, key=lambda x: -x[1])[:12]:
        flag = "  <-- deployed" if v == "micro_gate" else ""
        print(f"  {v:14} net {m:+6.2f}  t {t:+5.1f}  gross {g:+6.2f}  n={n}{flag}")

    print("\n[3] per-asset (micro_ufat):")
    for a in ("btc", "eth", "sol", "xrp"):
        s = [r["micro_ufat"]["net"] for (aa, w), r in rows.items() if aa == a and isinstance(r.get("micro_ufat"), dict)]
        if s:
            print(f"  {a}: net/win {sum(s)/len(s):+.2f}  win%={100*sum(1 for x in s if x>0)/len(s):.0f}  n={len(s)}")
    cs = corr_pairs(rows, "micro_ufat"); rho = sum(cs) / len(cs) if cs else 0.0
    print(f"\n[4] cross-asset net corr = {rho:+.2f} -> 4-mkt Sharpe lift {2/math.sqrt(1+3*max(0,rho)):.2f}x")

    if fills:
        print("\n[5] mo5 by time-to-close:", bucket(fills, lambda r: r.get("tau"),
              [(0, 120, "<2m"), (120, 300, "2-5m"), (300, 600, "5-10m"), (600, 1e9, ">10m")]))
        print("[6] mo5 by spread:", bucket(fills, lambda r: (r["ba"] - r["bb"]) if r.get("ba") and r.get("bb") else None,
              [(0, .015, "1tk"), (.015, .025, "2tk"), (.025, 1, "3+tk")]))
        print("[7] mo5 by P(up):", bucket(fills, lambda r: r.get("mid"),
              [(0, .3, "<.3"), (.3, .45, ".3-.45"), (.45, .55, "~.5"), (.55, .7, ".55-.7"), (.7, 1, ">.7")]))
        print("[8] mo5 by queue-ahead:", bucket(fills, lambda r: r.get("q_ahead"),
              [(0, 1, "front"), (1, 50, "1-50"), (50, 200, "50-200"), (200, 1e9, "deep")]))
    print("\nSee INSIGHTS_4DAY.md for the written 10 insights + ranked bot changes.")


if __name__ == "__main__":
    main()
