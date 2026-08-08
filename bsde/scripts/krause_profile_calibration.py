#!/usr/bin/env python3
"""Machinery calibration for E342's profile instrument. NOT an experiment -- no primary, no verdict.

Rule 63: before registering a numerical gate, compute what value the machinery can actually reach.
E341's P2 used a Spearman correlation between two measures' 8-state median-z profiles and set the
reducibility bar at 0.95. Three unrelated pairs returned exactly 1.0000, which is what a bar chosen as a
round number looks like when the statistic is a rank correlation over 8 points and every measure in the
inventory tracks depth.

This script measures two things and prints them, so E342's registration can set its bar from a number
instead of from a habit:

  (1) the distribution of |rho_profile| over ALL pairs of measures in the inventory -- how ordinary a
      near-perfect profile match is here;
  (2) the same distribution for pairs whose POOLED-Z correlation is weak (|rho_pooled| < 0.5), which is
      the set the profile instrument is supposed to be adding information about. If near-perfect profile
      matches are common even among measures that barely correlate observation-by-observation, the
      instrument is measuring "both track depth" and not "these are the same measure".

Also prints the achievable grid: with 8 states a Spearman takes a finite number of values, and the
distance from 1.0000 to the next attainable value bounds the bar's resolution.

    python bsde/scripts/krause_profile_calibration.py
"""
from __future__ import annotations

import csv, itertools, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from bsde.experiments.e341_reducibility import (  # noqa: E402
    SKIP, SLEEP, DRUG_U, PROFILE_STATES, f, med, iqr, pear, spear)

DATA = os.path.join(ROOT, "results", "krause_dexprosleep_allData.csv")
WAKE, REM, DEEP = "WS", "R", "N3"


def main() -> int:
    rows = list(csv.DictReader(open(DATA)))
    cols = [c for c in rows[0] if c not in SKIP]
    by = {}
    for r in rows:
        by.setdefault((r["patientID"], r["label"]), []).append(r)
    pats = sorted({p for p, l in by if l == WAKE} & {p for p, l in by if l == REM}
                  & {p for p, l in by if l == DEEP})

    Z = {}
    for p in pats:
        blocks = {st: by.get((p, st), []) for st in SLEEP}
        for u in DRUG_U:
            if (p, u) in by:
                blocks[u] = by[(p, u)]
        for c in cols:
            raw = {st: [f(x.get(c)) for x in rs] for st, rs in blocks.items()}
            pool = [v for st in SLEEP for v in raw.get(st, []) if math.isfinite(v)]
            m0, s0 = med(pool), iqr(pool)
            if not (math.isfinite(m0) and math.isfinite(s0) and s0 > 0):
                continue
            Z[(p, c)] = {st: (med(v) - m0) / s0 for st, v in raw.items() if med(v) == med(v)}

    keys = [(p, st) for p in pats for st in PROFILE_STATES]
    vec = {c: [Z[(p, c)].get(st, float("nan")) if (p, c) in Z else float("nan") for p, st in keys]
           for c in cols}
    prof = {c: [med([Z[(p, c)][st] for p in pats if (p, c) in Z and st in Z[(p, c)]])
                for st in PROFILE_STATES] for c in cols}

    print(f"[cohort] {len(pats)} patients, {len(cols)} measures, {len(PROFILE_STATES)} profile states")
    n_state = sum(1 for st in PROFILE_STATES
                  if all(math.isfinite(prof[c][PROFILE_STATES.index(st)]) for c in cols))
    print(f"[profile] states finite for every measure: {n_state} of {len(PROFILE_STATES)}")

    allp, weakp = [], []
    for x, y in itertools.combinations(cols, 2):
        sp = spear(prof[x], prof[y])
        pl = pear(vec[x], vec[y])
        if not math.isfinite(sp):
            continue
        allp.append((abs(sp), x, y, pl))
        if math.isfinite(pl) and abs(pl) < 0.5:
            weakp.append((abs(sp), x, y, pl))

    def summarise(name, arr):
        v = sorted(t[0] for t in arr)
        if not v:
            print(f"  {name}: none"); return
        q = lambda f_: v[min(len(v) - 1, int(f_ * len(v)))]
        for bar in (0.90, 0.95, 0.99, 1.00):
            hit = sum(1 for t in v if t >= bar - 1e-9)
            print(f"  {name:<34} |rho| >= {bar:.2f}: {hit:4d} of {len(v):4d} pairs "
                  f"({hit / len(v):6.1%})")
        print(f"  {name:<34} median {q(0.5):.4f}  p75 {q(0.75):.4f}  p90 {q(0.90):.4f}  "
              f"p95 {q(0.95):.4f}  max {v[-1]:.4f}")

    print("\n[1] ALL measure pairs")
    summarise("all pairs", allp)
    print("\n[2] pairs whose POOLED-Z correlation is weak (|rho_pooled| < 0.5) --")
    print("    the set the profile instrument claims to add information about")
    summarise("weak-pooled pairs", weakp)

    print("\n[3] the worst offenders: near-perfect profile match, weak pooled correlation")
    for ab, x, y, pl in sorted(weakp, reverse=True)[:10]:
        print(f"    |rho_profile| = {ab:.4f}   rho_pooled = {pl:+.4f}   {x} / {y}")

    # achievable grid for a Spearman over k points with no ties
    print("\n[4] resolution of the instrument")
    for k in (5, 6, 7, 8):
        # 1 - 6*sum d^2 / (k(k^2-1)); the smallest non-zero sum d^2 for a permutation is 2
        step = 6 * 2 / (k * (k * k - 1))
        print(f"    k = {k} states: values below 1.0000 start at {1 - step:.4f} "
              f"(one adjacent transposition), so the bar has resolution {step:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
