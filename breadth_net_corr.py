"""breadth_net_corr.py -- the REAL breadth Sharpe, measured from the multi-asset shadow.

breadth_sim.py projected the breadth benefit from RESOLUTION-OUTCOME correlation (a proxy: rho~0.80).
But what actually matters for a market maker is how correlated the STRATEGY's per-window NET P&L is
across assets -- two markets can have correlated outcomes yet uncorrelated maker P&L (the rebate comes
from fill volume + microstructure, not the up/down result). This reads the multi-asset shadow windows
(written per-asset by multi_market.py, each row carrying `asset`/`ws`) and computes, for a given variant
(default micro_gate), the pairwise correlation of its per-window net across assets -> the true Sharpe lift.

    python breadth_net_corr.py [variant]      # default: micro_gate
"""
from __future__ import annotations
import collections, glob, json, math, statistics, sys


def load(variant):
    """{asset: {ws: net}} for `variant`, deduped per (asset, ws)."""
    by = collections.defaultdict(dict)
    for fp in sorted(glob.glob("gha_data/shadow_windows_*.jsonl")):
        for ln in open(fp):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            a = r.get("asset")
            v = r.get(variant)
            if a and r.get("ws") is not None and isinstance(v, dict) and "net" in v:
                by[a][r["ws"]] = v["net"]          # last write wins (dedupe by window)
    return by


def corr(x, y):
    n = len(x)
    if n < 6:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    vx = sum((u - mx) ** 2 for u in x); vy = sum((u - my) ** 2 for u in y)
    return (sum((x[i] - mx) * (y[i] - my) for i in range(n)) / math.sqrt(vx * vy)
            if vx > 0 and vy > 0 else float("nan"))


def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else "micro_gate"
    by = load(variant)
    assets = [a for a in ("btc", "eth", "sol", "xrp") if a in by] + \
             [a for a in by if a not in ("btc", "eth", "sol", "xrp")]
    if len(assets) < 2:
        print(f"need >=2 assets with `{variant}` windows; have {assets}. "
              "Run the multi-asset collector (multi_market.py) and sync gha-data first.")
        return
    print(f"=== per-window NET correlation of `{variant}` across assets ===")
    print("(this is what sets the breadth Sharpe -- NOT the resolution-outcome corr)")
    # per-asset stats
    for a in assets:
        s = list(by[a].values()); m = sum(s) / len(s)
        sd = statistics.pstdev(s) if len(s) > 1 else 0.0
        print(f"  {a:>4}: net/win {m:+.2f}  std {sd:5.2f}  (n={len(s)} windows)")
    cs = []
    print("\n  pairwise net correlation (shared windows):")
    for i in range(len(assets)):
        for j in range(i + 1, len(assets)):
            a, b = assets[i], assets[j]
            ks = sorted(set(by[a]) & set(by[b]))
            x = [by[a][k] for k in ks]; y = [by[b][k] for k in ks]
            c = corr(x, y)
            if c == c:
                cs.append(c)
                print(f"    {a}-{b}: rho_net={c:+.2f}  (n={len(ks)} shared)")
            else:
                print(f"    {a}-{b}: (too few shared windows: {len(ks)})")
    if not cs:
        print("\nno asset pair has enough shared windows yet -- let data accumulate.")
        return
    rho = statistics.mean(cs)
    # pooled single-market Sharpe/win across all assets (the per-market unit)
    allnet = [v for a in assets for v in by[a].values()]
    m = sum(allnet) / len(allnet); sd = statistics.pstdev(allnet)
    sh1 = m / sd if sd > 0 else float("nan")
    print(f"\n  mean pairwise rho_net = {rho:+.2f}")
    print(f"  pooled per-market: net/win {m:+.2f}  std {sd:.2f}  Sharpe/win {sh1:+.2f}")
    print(f"\n=== REAL breadth projection ({variant}, measured rho_net={rho:+.2f}) ===")
    print(f"{'N markets':>10}{'total net/win':>15}{'Sharpe lift':>13}{'Sharpe/win':>12}")
    for N in (1, 2, 4, 6, 8):
        lift = math.sqrt(N) / math.sqrt(1 + (N - 1) * max(0.0, rho))
        print(f"{N:>10}{N * m:>+15.2f}{lift:>12.2f}x{sh1 * lift:>12.2f}")
    print("\nRead: rho_net (maker P&L correlation) is usually BELOW the resolution-outcome rho, because the "
          "rebate edge is microstructural, not directional -- so the true breadth Sharpe lift is LARGER than "
          "breadth_sim.py's outcome-based estimate. Compare the two to bound it.")


if __name__ == "__main__":
    main()
