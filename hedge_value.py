"""hedge_value.py -- quantify MAKEREDGE.md #1: how much risk does delta-hedging the resolution buy back?

A variant settles gross = cash + up_inv*r + dn_inv*(1-r) = (cash+dn_inv) + end_delta*r, so the directional
factor carried into resolution is  d_w = end_delta_w * (r_w - rbar)  (the unpaired inventory's bet on the
outcome). A delta-hedge on a BTC perp offsets that factor. The RIGHT way to value it is the
minimum-variance hedge ratio (you can't do better, and -- unlike a naive end-of-window subtraction --
it can never INCREASE variance):

    beta   = Cov(net, d) / Var(d)            # optimal hedge ratio
    hedged_net_w = net_w - beta * d_w
    std(hedged) = std(net) * sqrt(1 - corr(net,d)^2)     # variance floor after hedging the factor
    mean(hedged) ~ mean(net)   (d is ~zero-mean in a calibrated market, so the hedge preserves mean)

So the payoff of hedging is VARIANCE reduction (-> size up at the same risk -> more rebate), not mean.
We also report mean(d): if it's materially <0 the market is picking us off directionally and the hedge
adds MEAN too. No hedge cost modeled (perp fee+funding is what you weigh against the variance drop).
    python hedge_value.py
"""
from __future__ import annotations
import glob, json, math


def load():
    rows, seen = [], set()
    files = sorted(glob.glob("gha_data/shadow_windows_r*.jsonl")) or sorted(glob.glob("shadow_windows*.jsonl"))
    for fp in files:
        for ln in open(fp):
            ln = ln.strip()
            if not ln:
                continue
            try:
                w = json.loads(ln)
            except Exception:
                continue
            ws = w.get("ws"); r = w.get("resolved_up")
            if ws is None or r is None or ws in seen:
                continue
            seen.add(ws); rows.append(w)
    return rows, len(files)


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def _std(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5


def _corr(a, b):
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = _mean(a), _mean(b)
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
    return cov / math.sqrt(va * vb) if va > 0 and vb > 0 else 0.0


def main():
    rows, nf = load()
    if len(rows) < 5:
        print(f"only {len(rows)} settled windows; need more for a stable read."); return
    rbar = sum(w["resolved_up"] for w in rows) / len(rows)
    variants = sorted({k for w in rows for k, v in w.items() if isinstance(v, dict) and "gross" in v})
    print(f"hedge-value over {len(rows)} windows (files={nf}); rbar(P[up])={rbar:.3f}\n")
    print(f"{'variant':>12} {'net/win':>8} {'net sd':>7} {'corr w/dir':>10} {'sd→hedged':>10} "
          f"{'sd drop':>7} {'mean dir':>8} {'size×':>6}")
    for v in variants:
        net, d = [], []
        for w in rows:
            a = w.get(v)
            if not (isinstance(a, dict) and "net" in a and "end_delta" in a):
                continue
            net.append(a["net"]); d.append(a["end_delta"] * (w["resolved_up"] - rbar))
        if len(net) < 5:
            continue
        nsd = _std(net); c = _corr(net, d)
        hsd = nsd * math.sqrt(max(0.0, 1 - c * c))      # min-variance hedge floor (never > nsd)
        drop = (1 - hsd / nsd) * 100 if nsd > 0 else 0.0
        size_mult = (nsd / hsd) if hsd > 0 else float("inf")  # size you can run at the SAME variance
        print(f"{v:>12} {_mean(net):>+8.3f} {nsd:>7.2f} {c:>+10.2f} {hsd:>10.2f} {drop:>6.0f}% "
              f"{_mean(d):>+8.3f} {size_mult:>5.2f}x")
    print("\nRead: 'sd→hedged' = P&L std after the minimum-variance BTC-perp hedge of the directional "
          "factor; 'sd drop' is the risk removed; 'size×' = how much you could scale at the SAME variance "
          "(-> ~that much more rebate), to weigh against perp fee+funding (MAKEREDGE.md #1). 'mean dir' ~0 "
          "=> hedging is variance-only (no mean cost); materially <0 => the market also picks us off "
          "directionally and the hedge adds mean. Small n -> directional terms are noisy; treat as a sizing "
          "signal, not proof.")


if __name__ == "__main__":
    main()
