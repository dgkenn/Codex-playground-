"""What separates PROFITABLE fills from UNPROFITABLE fills?

Pools the per-decision audit ledger (baseline+micro_gate fills) and asks which DECISION-TIME
features (no lookahead) separate good from bad fills. Guardrails:
  * predictors are only what we knew BEFORE the fill (imb, flow, taker size, tau, price,
    spread, microprice-edge, inventory). dspot30/mo30/mo_res are OUTCOMES.
  * primary target = mo30 (short-horizon markout = toxicity), which varies WITHIN a window so
    it's estimable with ~15 windows; resolution pnl is shown too but is regime-confounded.
  * we also control for the BTC move (dspot30) to isolate MICROSTRUCTURE flow-quality from
    "BTC happened to move," and we report per-window sign-consistency (cluster-aware), not just
    a pooled t that ignores the ~n=windows reality.

    python flow_separation.py
"""
from __future__ import annotations
import glob, json
from collections import defaultdict
import numpy as np

FEATS = ["edge", "imb", "flow30", "flow5", "tk_sz", "tau", "p", "spread", "absdelta", "is_sell"]


def load():
    rows = []
    for f in glob.glob("gha_data/fills_r*.jsonl"):
        for ln in open(f):
            ln = ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except Exception: pass
    return [r for r in rows if r.get("sz", 0) > 0 and r.get("mo30") is not None]


def feat(r):
    mp = r.get("micro"); p = r["p"]; sell = (r["side"] == "ASK")
    edge = None
    if mp is not None:
        edge = (p - mp) if sell else (mp - p)
    bb, ba = r.get("bb"), r.get("ba")
    return {
        "edge": edge,
        "imb": r.get("imb"),
        "flow30": r.get("flow30"),
        "flow5": r.get("flow5"),
        "tk_sz": r.get("tk_sz"),
        "tau": r.get("tau"),
        "p": p,
        "spread": (ba - bb) if (bb is not None and ba is not None) else None,
        "absdelta": abs(r.get("delta", 0.0)),
        "is_sell": 1.0 if sell else 0.0,
    }


def ols(X, y):
    Xb = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(Xb, y, rcond=None)
    yhat = Xb @ beta
    ss_res = float(np.sum((y - yhat) ** 2)); ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return beta, r2


def main():
    rows = load()
    nwin = len(set(r["ws"] for r in rows))
    print(f"fills with mo30: {len(rows)} over {nwin} windows (effective n ~= windows)\n")
    # build standardized feature matrix (drop rows with any missing feature)
    F = [feat(r) for r in rows]
    keep = [i for i, f in enumerate(F) if all(f[k] is not None for k in FEATS)]
    rows = [rows[i] for i in keep]; F = [F[i] for i in keep]
    X = np.array([[f[k] for k in FEATS] for f in F], float)
    mu, sd = X.mean(0), X.std(0); sd[sd == 0] = 1
    Xs = (X - mu) / sd
    mo30 = np.array([r["mo30"] for r in rows], float)
    pnl = np.array([r["pnl"] for r in rows], float)
    dsp = np.array([r.get("dspot30") if r.get("dspot30") is not None else 0.0 for r in rows], float)

    print("=== WINNERS vs LOSERS by mo30 sign (mean decision-time feature) ===")
    win = [i for i in range(len(rows)) if mo30[i] > 0]
    los = [i for i in range(len(rows)) if mo30[i] < 0]
    print(f"  winners(mo30>0)={len(win)}  losers(mo30<0)={len(los)}")
    print(f"  {'feature':>9} {'winners':>9} {'losers':>9} {'gap(std)':>9}")
    for j, k in enumerate(FEATS):
        wv, lv = X[win, j].mean(), X[los, j].mean()
        print(f"  {k:>9} {wv:>9.3f} {lv:>9.3f} {(wv-lv)/sd[j]:>+9.2f}")

    print("\n=== standardized OLS coefficients (sign = direction; |size| = importance) ===")
    for tgt, name in ((mo30, "mo30 (toxicity)"), (pnl, "pnl (regime-confounded)")):
        beta, r2 = ols(Xs, tgt)
        order = sorted(range(len(FEATS)), key=lambda j: -abs(beta[j + 1]))
        print(f"  target={name}  R2={r2:.3f}")
        for j in order:
            print(f"     {FEATS[j]:>9} {beta[j+1]:+.4f}")
    # control for BTC move: add standardized dspot30 -> other coefs = microstructure flow-quality
    ds = (dsp - dsp.mean()) / (dsp.std() or 1)
    beta, r2 = ols(np.column_stack([Xs, ds]), mo30)
    print(f"\n=== mo30 controlling for BTC move (dspot30); coefs = microstructure flow-quality  R2={r2:.3f} ===")
    labs = FEATS + ["dspot30(ctrl)"]
    for j in sorted(range(len(labs)), key=lambda j: -abs(beta[j + 1])):
        print(f"     {labs[j]:>13} {beta[j+1]:+.4f}")

    # cluster-aware robustness: per-window sign of the simple corr(feature, mo30) for top features
    print("\n=== per-window sign-consistency of corr(feature, mo30) (robustness vs n~=windows) ===")
    byw = defaultdict(list)
    for i, r in enumerate(rows): byw[r["ws"]].append(i)
    for k in ["edge", "imb", "tau", "flow30"]:
        j = FEATS.index(k); pos = neg = 0
        for ws, idx in byw.items():
            if len(idx) < 20: continue
            xs = X[idx, j]; ys = mo30[idx]
            if xs.std() == 0: continue
            c = np.corrcoef(xs, ys)[0, 1]
            if c > 0: pos += 1
            elif c < 0: neg += 1
        tot = pos + neg
        print(f"  {k:>9}: +{pos}/-{neg} windows  ({'consistent' if tot and max(pos,neg)/tot>=0.7 else 'mixed'})")


if __name__ == "__main__":
    main()
