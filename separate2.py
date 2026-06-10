"""Better separation of winning vs losing fills.

Findings so far: the microprice EDGE is the one linearly-robust separator (sign-consistent
across windows); imbalance is informative only NONLINEARLY (the bid-HEAVY extreme is toxic).
This builds a composite toxicity score from the robust pieces, deciles it, and -- the real
test -- checks whether the top-vs-bottom separation holds PER WINDOW (cluster-aware), not just
pooled. Target = mo30 (short-horizon markout = toxicity; within-window estimable, t<0 robust).

    python separate2.py
"""
from __future__ import annotations
import glob, json
import numpy as np
from collections import defaultdict


def load():
    rows = []
    for f in glob.glob("gha_data/fills_r*.jsonl"):
        for ln in open(f):
            ln = ln.strip()
            if ln:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if r.get("var") == "baseline" and r.get("sz", 0) > 0 \
                   and r.get("mo30") is not None and r.get("micro") is not None:
                    rows.append(r)
    return rows


def edge(r):
    return (r["p"] - r["micro"]) if r["side"] == "ASK" else (r["micro"] - r["p"])


def buckets(rows, keyfn, edges, labels, tgt="mo30"):
    for (lo, hi), nm in zip(edges, labels):
        b = [r for r in rows if lo <= keyfn(r) < hi]
        if b:
            mo = np.mean([r[tgt] for r in b]); mr = np.mean([r["mo_res"] for r in b])
            pn = np.mean([r["pnl"] for r in b])
            print(f"    {nm:16}: n={len(b):5d}  mo30={mo:+.4f}  mo_res={mr:+.4f}  pnl/fill={pn:+.4f}")


def main():
    rows = load()
    nwin = len(set(r["ws"] for r in rows))
    print(f"baseline fills: {len(rows)} over {nwin} windows\n")
    for r in rows:
        r["_edge"] = edge(r)

    print("== separation by EDGE (microprice edge; the robust linear separator) ==")
    qs = np.quantile([r["_edge"] for r in rows], [0, .2, .4, .6, .8, 1.0])
    buckets(rows, lambda r: r["_edge"],
            [(qs[i], qs[i+1] + (1e-9 if i == 4 else 0)) for i in range(5)],
            [f"Q{i+1} edge[{qs[i]:+.3f},{qs[i+1]:+.3f}]" for i in range(5)])

    # composite TOXICITY score: standardized(-edge) + standardized(imb) [both point toward toxic].
    # nonlinear imb captured by also adding the bid-HEAVY indicator.
    ed = np.array([r["_edge"] for r in rows]); im = np.array([r.get("imb") or 0.5 for r in rows])
    z = lambda a: (a - a.mean()) / (a.std() or 1)
    score = z(-ed) + z(im) + 1.0 * (im > 0.8)
    for r, s in zip(rows, score):
        r["_tox"] = float(s)
    print("\n== separation by COMPOSITE TOXICITY score (-edge + imb + bid-HEAVY) ==")
    tq = np.quantile(score, [0, .2, .4, .6, .8, 1.0])
    buckets(rows, lambda r: r["_tox"],
            [(tq[i], tq[i+1] + (1e-9 if i == 4 else 0)) for i in range(5)],
            [f"Q{i+1} (low->high tox)" for i in range(5)])

    # the decisive test: does the top-vs-bottom split hold PER WINDOW?
    print("\n== per-window robustness: does low-tox beat high-tox (mo30) within each window? ==")
    for nm, key in (("edge", "_edge"), ("composite tox", "_tox")):
        byw = defaultdict(list)
        for r in rows:
            byw[r["ws"]].append(r)
        agree = tot = 0
        gaps = []
        for ws, g in byw.items():
            if len(g) < 40:
                continue
            v = sorted(g, key=lambda r: r[key])
            k = max(len(v) // 5, 1)
            lo = np.mean([r["mo30"] for r in v[:k]])      # lowest score (for edge: worst edge)
            hi = np.mean([r["mo30"] for r in v[-k:]])     # highest score
            # for edge: high edge should have HIGHER mo30; for tox: high tox should have LOWER mo30
            good = (hi > lo) if key == "_edge" else (lo > hi)
            agree += good; tot += 1
            gaps.append((hi - lo) if key == "_edge" else (lo - hi))
        if tot:
            print(f"  {nm:14}: separates correctly in {agree}/{tot} windows "
                  f"({'ROBUST' if agree/tot >= 0.7 else 'mixed'}); mean favorable-minus-toxic mo30 gap = {np.mean(gaps):+.4f}")


if __name__ == "__main__":
    main()
