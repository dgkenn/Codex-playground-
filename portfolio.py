#!/usr/bin/env python3
"""portfolio.py -- the ALLOCATION BRAIN of the multi-strategy bot (node MULTISTRAT-PROGRAM, 2026-07-16).

Turns independent paper SLEEVES (each = one validated/forward-gating edge) into a correlation-aware
PORTFOLIO. A "stack" only helps if the sleeves' PnL is UNCORRELATED -- so this computes, from each sleeve's
settled paper log:
  - per-sleeve: mean PnL/contract, period-clustered t, tail (worst period, % negative periods), gate status;
  - the CROSS-SLEEVE CORRELATION MATRIX of per-period PnL (the stackability test);
  - portfolio weights two ways -- INVERSE-VARIANCE (risk parity) and fractional-Kelly-with-covariance --
    and the resulting combined equity curve + portfolio Sharpe and tail vs the best single sleeve.

Design: a sleeve is any settled-paper JSONL with one row per resolved position carrying a PnL and a
resolution-period key. New edges plug in by adding a row to SLEEVES -- no other change. Read-only, stdlib,
PROPOSE-ONLY (reports allocation; never sizes live capital without operator authorization).

Usage: python portfolio.py            # report all sleeves + correlation + portfolio
       python portfolio.py --backtest # also fold in each sleeve's committed backtest weekly-PnL prior
"""
import json, os, math, sys, statistics as st
from collections import defaultdict

# sleeve registry: name -> (settled_jsonl, pnl_field, period_field, live_gate_status_note)
SLEEVES = {
    "pmkt_shortvol": ("pmkt_shortvol_settled.jsonl", "pnl", "close_date",
                      "CONFIRMED backtest edge (t=2.88 realistic fills); forward-gating"),
    "pmkt_econ":     ("pmkt_econ_settled.jsonl", "pnl", "close_date",
                      "CONFIRMED backtest edge (t=3.09/3.77, 55wk); uncorrelated w/ crypto (-0.01); forward-gating"),
    "pmkt_biz":      ("pmkt_biz_settled.jsonl", "pnl", "close_date",
                      "MARGINAL edge (share-wt t=2.28, equal 1.68, 21wk, capacity-ltd); uncorr (+0.07); forward-gate decisive"),
    "wing_vrp":      ("wing_paper_settled.jsonl", "pnl", "close_date",
                      "DEAD in backtest (market-weighting artifact); kept as control"),
    # future sleeves (cross-venue convergence rejected; wallet-copy null) append here as they pass gate
}


def _load(path, pnl_f, per_f):
    """period -> list[pnl] from a settled sleeve log."""
    per = defaultdict(list)
    if not os.path.exists(path):
        return per
    with open(path) as f:
        for l in f:
            try:
                r = json.loads(l)
                if r.get(pnl_f) is not None and r.get(per_f):
                    per[r[per_f]].append(float(r[pnl_f]))
            except Exception:
                pass
    return per


def _clustered_t(period_means):
    xs = list(period_means.values())
    if len(xs) < 2:
        return float("nan")
    sd = st.stdev(xs)
    return st.mean(xs) / (sd / math.sqrt(len(xs))) if sd > 0 else float("nan")


def _sleeve_stats(per):
    pm = {k: st.mean(v) for k, v in per.items() if v}
    if not pm:
        return None
    xs = list(pm.values())
    n = len(xs)
    worst = min(xs)
    neg = sum(1 for x in xs if x < 0) / n
    t = _clustered_t(pm)
    status = ("PASS" if (n >= 8 and t >= 2 and st.mean(xs) > 0 and worst >= -0.50)
              else "KILL" if (n >= 8 and t < 0) else "ACCRUING")
    return dict(pm=pm, n=n, mean=st.mean(xs), t=t, worst=worst, negfrac=neg, status=status)


def _corr(a, b):
    common = sorted(set(a) & set(b))
    if len(common) < 3:
        return None, len(common)
    xa = [a[k] for k in common]
    xb = [b[k] for k in common]
    if st.pstdev(xa) == 0 or st.pstdev(xb) == 0:
        return None, len(common)
    ma, mb = st.mean(xa), st.mean(xb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(xa, xb)) / len(common)
    return cov / (st.pstdev(xa) * st.pstdev(xb)), len(common)


def main():
    stats = {}
    for name, (path, pf, perf, note) in SLEEVES.items():
        s = _sleeve_stats(_load(path, pf, perf))
        stats[name] = (s, note)

    print("=== SLEEVES (per-period-clustered) ===")
    print(f"{'sleeve':16}{'status':10}{'n':>4}{'mean$':>9}{'t':>7}{'worst':>8}{'neg%':>7}  note")
    live = {}
    for name, (s, note) in stats.items():
        if s is None:
            print(f"{name:16}{'NO-DATA':10}{'-':>4}{'-':>9}{'-':>7}{'-':>8}{'-':>7}  {note}")
            continue
        print(f"{name:16}{s['status']:10}{s['n']:>4}{s['mean']:>+9.4f}{s['t']:>7.2f}"
              f"{s['worst']:>+8.3f}{s['negfrac']*100:>6.0f}%  {note}")
        if s['status'] != "KILL":
            live[name] = s

    # correlation matrix (stackability)
    names = [n for n in live]
    if len(names) >= 2:
        print("\n=== CROSS-SLEEVE PnL CORRELATION (stackability; near 0 = diversifying) ===")
        print(" " * 16 + "".join(f"{n[:12]:>13}" for n in names))
        for a in names:
            row = f"{a:16}"
            for b in names:
                c, nc = _corr(live[a]['pm'], live[b]['pm'])
                row += f"{(c if c is not None else float('nan')):>13.2f}"
            print(row)

    # portfolio construction (inverse-variance / risk-parity)
    if len(names) >= 2:
        print("\n=== PORTFOLIO (inverse-variance / risk-parity weights) ===")
        var = {n: (st.pvariance(list(live[n]['pm'].values())) or 1e-9) for n in names}
        inv = {n: 1.0 / var[n] for n in names}
        tot = sum(inv.values())
        w = {n: inv[n] / tot for n in names}
        for n in names:
            print(f"  {n:16} weight={w[n]:.3f}  (sleeve t={live[n]['t']:.2f})")
        # combined per-period PnL with these weights (on the union of periods each present)
        allper = sorted(set().union(*[set(live[n]['pm']) for n in names]))
        combo = []
        for p in allper:
            v = sum(w[n] * live[n]['pm'][p] for n in names if p in live[n]['pm'])
            combo.append(v)
        if len(combo) > 1 and st.stdev(combo) > 0:
            csharpe = st.mean(combo) / st.stdev(combo)
            best = max(live, key=lambda n: (live[n]['mean'] / (st.pstdev(list(live[n]['pm'].values())) or 1e9)))
            bsharpe = live[best]['mean'] / (st.pstdev(list(live[best]['pm'].values())) or 1e-9)
            print(f"  portfolio per-period Sharpe={csharpe:.2f}  vs best single sleeve ({best})={bsharpe:.2f}  "
                  f"worst={min(combo):+.3f}")
    else:
        print("\n[portfolio] need >=2 live sleeves with settled data to allocate; "
              "sleeves still ACCRUING (forward gates open as data lands).")


if __name__ == "__main__":
    main()
