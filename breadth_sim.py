"""breadth_sim.py -- quantify the ONE stack that works: running the SAME micro_gate edge across all
crypto markets. The diversification benefit hinges on how correlated the 15-min RESOLUTION outcomes are
across BTC/ETH/SOL/XRP -- measured here from the cached tape -- and on micro_gate's per-window net stats
(from the BTC shadow windows). Projects the portfolio Sharpe & total P&L for N markets.

Sharpe_N(total) = sqrt(N) * Sharpe_1 / sqrt(1 + (N-1)*rho)   (equal-weight, pairwise corr rho)
    python breadth_sim.py
"""
from __future__ import annotations
import collections, glob, json, math, statistics


def res_by_asset():
    """ws -> {asset: res_up} from the cached multi-asset tape."""
    W = collections.defaultdict(dict)
    for ln in open("makers_trades.jsonl"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("tenor") == 15:                      # 15m only for a clean cross-asset comparison
            W[r["ws"]][r["asset"]] = r["res_up"]
    return W


def corr(x, y):
    n = len(x)
    if n < 8:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    vx = sum((u - mx) ** 2 for u in x); vy = sum((u - my) ** 2 for u in y)
    return sum((x[i] - mx) * (y[i] - my) for i in range(n)) / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def micro_gate_net():
    nets = []
    by_ws = {}
    for fp in sorted(glob.glob("gha_data/shadow_windows_*.jsonl")):
        for ln in open(fp):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("ws") is not None and "micro_gate" in r and isinstance(r["micro_gate"], dict):
                by_ws[r["ws"]] = r["micro_gate"]["net"]
    return list(by_ws.values())


def main():
    W = res_by_asset()
    assets = ["btc", "eth", "sol", "xrp"]
    # pairwise resolution-outcome correlation across assets (shared windows)
    print("=== 15-min RESOLUTION-outcome correlation across assets (shared windows) ===")
    cs = []
    for i in range(len(assets)):
        for j in range(i + 1, len(assets)):
            a, b = assets[i], assets[j]
            ks = [w for w in W if a in W[w] and b in W[w]]
            x = [W[w][a] for w in ks]; y = [W[w][b] for w in ks]
            c = corr(x, y)
            if c == c:
                cs.append(c); print(f"  {a}-{b}: rho={c:+.2f}  (n={len(ks)} shared windows)")
    rho = statistics.mean(cs) if cs else 0.0
    print(f"  mean pairwise rho = {rho:+.2f}")
    net = micro_gate_net()
    if len(net) < 5:
        print("\nnot enough micro_gate windows"); return
    m = sum(net) / len(net); sd = statistics.pstdev(net); sh1 = m / sd if sd > 0 else float("nan")
    print(f"\nmicro_gate per-market: net/win {m:+.2f}  std {sd:.2f}  Sharpe/win {sh1:+.2f}")
    print(f"\n=== BREADTH projection: micro_gate on N markets (rho={rho:+.2f}) ===")
    print(f"{'N markets':>10}{'total net/win':>15}{'Sharpe lift':>13}{'Sharpe/win':>12}")
    for N in (1, 2, 4, 6, 8):
        lift = math.sqrt(N) / math.sqrt(1 + (N - 1) * max(0, rho))
        print(f"{N:>10}{N*m:>+15.2f}{lift:>12.2f}x{sh1*lift:>12.2f}")
    print("\nRead: total net/win scales ~linearly with N (more rebate volume); Sharpe lifts by the factor "
          "shown -- full sqrt(N) if outcomes were independent, reduced by their correlation. Even at the "
          "measured rho, breadth raises BOTH total profit and risk-adjusted return -- the real stack.")


if __name__ == "__main__":
    main()
