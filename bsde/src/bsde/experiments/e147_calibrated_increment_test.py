#!/usr/bin/env python3
"""E147 -- a replacement increment test, calibrated against the same oracle that condemned the old one.

REGISTERED BEFORE ANY CELL OF THIS SWEEP HAS BEEN RUN. Synthetic data only; no deposit is touched.
Successor to E146. The instrument that changed is the test itself and it is described in full below.

=========================================================================================================
WHAT E146 MEASURED
=========================================================================================================
`oob_regression_increment`'s bootstrap tail fraction, used as a p-value across this project, is not
conservative -- it is blind:

    n_subj  rows  rho_partial |  OOB detects   ORACLE detects
        60     1         0.15 |       0.00%           38.33%
        60     1         0.25 |       0.00%           61.67%
        60     1         0.35 |       0.00%           88.33%
        60     1         0.50 |      10.00%          100.00%
        60     3         0.15 |       0.00%           65.00%

with a false-positive rate of **0.000** at rho_partial = 0 over 200 draws, so the failure is entirely one
of power. The diagnosis is structural rather than a tuning problem: **the spread of a bootstrap of
out-of-bag differences reflects resample-to-resample variability, not the sampling distribution of the
increment**, so its tail fraction is not a calibrated p-value and happens to be enormously conservative.
The point estimate is not in question; only the test built on it is.

Every null this project decided with that test therefore means "we could not have seen it" rather than
"it is not there" -- rule 31, and it applies to E84, E122's P2, E134, E143, E144 and E145 among others.
Relabelling those is separate work and is not done here. **This file builds the replacement and proves it
works before anything is re-run with it.**

=========================================================================================================
THE REPLACEMENT
=========================================================================================================
`permutation_increment`, added to `verifier/stats.py` in this commit:

  * the increment is computed ONCE, on subject-grouped out-of-fold predictions, so every row contributes
    to both the fit and the evaluation exactly once;
  * the null is built by **permuting the added column across CLUSTERS, whole blocks at a time**
    (`cluster_permute`), and refitting. A row-level shuffle would destroy the cluster structure along
    with the association and produce a null the real data could never have drawn from -- rule 69's
    principle applied to the permutation rather than to the resample;
  * the fold assignment is drawn once and reused for the observed value and every permutation, so the
    null does not carry fold noise the observed value lacks;
  * the sign convention is `oob_regression_increment`'s, unchanged: lower stat is better, so a NEGATIVE
    increment means the candidate helps. Keeping it identical is deliberate -- two increment functions
    with opposite conventions is exactly how rule 37's sign errors happen.

=========================================================================================================
GATES
=========================================================================================================
G1  **CALIBRATION, AND IT IS THE WHOLE POINT.** At rho_partial = 0, the new test's false-positive rate
    must lie in **[0.02, 0.10]** at a nominal 0.05, over 300 draws. Note this is a TWO-SIDED bar: a rate
    of 0.000 does not pass. E146's instrument scored 0.000 and that is precisely the pathology being
    fixed, so a gate that accepts 0.000 would accept the disease as a cure. A test that is merely
    conservative in a new way is not an improvement.
G2  MONOTONICITY. Detection must rise with rho_partial at every (n, rows) cell. A test whose power does
    not increase with effect size is broken whatever its calibration.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH FIRST (rule 37)
=========================================================================================================
P1  **At (n = 60 subjects, rows = 1, rho_partial = 0.35), the new test detects in >= 60 % of draws, where
    the old one detected in 0.00 % and the oracle in 88.33 %.**

    **IF IT DOES NOT** -- if the new test also lands far below the oracle -- then the loss is not the
    bootstrap tail after all but something intrinsic to judging an increment through a cross-fitted ridge,
    and the right conclusion is that **increment designs are the wrong instrument for this project at
    these sample sizes** and every challenge should be re-posed against marginal or partial statistics
    with cluster-robust inference. That is a bigger and more useful finding than a working test, and it
    is written first so it cannot be presented afterwards as the expected outcome.

P2  **Retained power (new test / oracle) exceeds 0.60 averaged over all cells where the oracle exceeds
    20 %.** The oracle ignores clustering and is anticonservative at rows_per_subject = 3, so it is an
    optimistic ceiling rather than a fair comparator; the ratio is read as "fraction of an optimistic
    ceiling" and the bar is set with that in mind.

P3  **The new test beats the old one in every single cell where the oracle exceeds 20 %.** A replacement
    that loses anywhere is not a replacement, and this is the cheapest way to say so.

SWEEP, identical to E146's so the comparison is not confounded by design: n_subjects in {60, 100, 200},
rows_per_subject in {1, 3}, rho_partial in {0.15, 0.25, 0.35, 0.50}, 40 draws per cell, 300 permutations
per call. Both instruments and the closed-form oracle are scored on **the same simulated draw**, which is
a paired comparison and strictly stronger than three independent sweeps.

WHAT WAS ALREADY SEEN (rule 41). E146's table above, and a four-point smoke test of the new function on
one seed at n = 60 while it was being written (rho 0.0/0.25/0.35/0.50 giving p = 0.935/0.475/0.040/0.000).
That smoke test is why P1's bar is 60 % rather than a guess, and it is disclosed for that reason.

    python bsde/src/bsde/experiments/e147_calibrated_increment_test.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import (oob_regression_increment,                     # noqa: E402
                                 permutation_increment, spearman)

sys.path.insert(0, HERE)
from e146_oob_increment_calibration import oracle_p, rank_stat                  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e147_calibrated_increment.json")

N_SUBJ = (60, 100, 200)
ROWS_PER = (1, 3)
RHOS = (0.15, 0.25, 0.35, 0.50)
DRAWS = 40
PERMS = 300
OOB_REPS = 800
CAL_DRAWS = 300


def simulate(rng, n_subj, rows_per, rho):
    n = n_subj * rows_per
    subj = np.repeat(np.arange(n_subj), rows_per)
    a = rng.standard_normal(n)
    y = a + rng.standard_normal(n)
    A = np.c_[np.ones(n), a]
    r = y - A @ np.linalg.lstsq(A, y, rcond=None)[0]
    r = (r - r.mean()) / (r.std() + 1e-12)
    z = rho * r + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(n)
    return a.reshape(-1, 1), np.c_[a, z], y, subj, a, z


def main(argv=None) -> int:
    rng = np.random.default_rng(147)
    out = {"experiment": "E147", "draws": DRAWS, "perms": PERMS, "cal_draws": CAL_DRAWS}

    # ---- G1 CALIBRATION, two-sided --------------------------------------------------------------------
    hits = 0
    for _ in range(CAL_DRAWS):
        Xa, Xb, y, subj, _a, _z = simulate(rng, 100, 1, 0.0)
        _o, p, _nm, _k = permutation_increment(Xa, Xb, y, subj, rng, reps=PERMS)
        hits += math.isfinite(p) and p < 0.05
    fpr = hits / CAL_DRAWS
    g1 = 0.02 <= fpr <= 0.10
    print(f"G1 CALIBRATION  false-positive rate at rho=0, n=100, {CAL_DRAWS} draws: {fpr:.4f}  "
          f"(must be in [0.02, 0.10]; 0.000 FAILS -- that is E146's pathology) -> "
          f"{'PASS' if g1 else 'FAIL'}")
    out["G1"] = {"pass": bool(g1), "fpr": fpr}
    if not g1:
        print("\nGATE FAILED -- the replacement is not calibrated; nothing below is reported.")
        json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
        return 1

    # ---- the paired sweep ------------------------------------------------------------------------------
    print(f"\n{'n_subj':>7s} {'rows':>5s} {'rho_p':>6s} | {'NEW':>8s} {'OLD':>8s} {'ORACLE':>8s} | "
          f"{'new/orc':>8s}")
    cells = {}
    for ns in N_SUBJ:
        for rp in ROWS_PER:
            for rho in RHOS:
                hn = ho_ = hor = 0
                for _ in range(DRAWS):
                    Xa, Xb, y, subj, a, z = simulate(rng, ns, rp, rho)
                    _o, pn, _nm, _k = permutation_increment(Xa, Xb, y, subj, rng, reps=PERMS)
                    _m, _lo, _hi, _n, d = oob_regression_increment(
                        Xa, Xb, y, subj, rng, stat=rank_stat, reps=OOB_REPS, return_diffs=True)
                    po = float((d >= 0).mean()) if len(d) else float("nan")
                    hn += math.isfinite(pn) and pn < 0.05
                    ho_ += math.isfinite(po) and po < 0.05
                    hor += (lambda v: math.isfinite(v) and v < 0.05)(oracle_p(a, y, z))
                nw, ol, orc = hn / DRAWS, ho_ / DRAWS, hor / DRAWS
                cells[f"{ns}|{rp}|{rho}"] = {"n_subj": ns, "rows_per": rp, "rho": rho,
                                             "new": nw, "old": ol, "oracle": orc,
                                             "retained": nw / orc if orc > 0 else float("nan")}
                print(f"{ns:7d} {rp:5d} {rho:6.2f} | {nw:8.1%} {ol:8.1%} {orc:8.1%} | "
                      f"{(nw / orc if orc > 0 else float('nan')):8.1%}")
    out["cells"] = cells

    key = cells.get("60|1|0.35")
    live = [v for v in cells.values() if v["oracle"] > 0.20]
    ret = float(np.nanmean([v["retained"] for v in live])) if live else float("nan")
    beats = [v for v in live if v["new"] > v["old"]]
    g2 = all(
        all(cells[f"{ns}|{rp}|{RHOS[i]}"]["new"] <= cells[f"{ns}|{rp}|{RHOS[i + 1]}"]["new"] + 1e-9
            for i in range(len(RHOS) - 1))
        for ns in N_SUBJ for rp in ROWS_PER)
    print(f"\nG2 MONOTONICITY  detection non-decreasing in rho at every cell -> "
          f"{'PASS' if g2 else 'FAIL'}")

    p1 = ("CONFIRMED -- the replacement recovers most of the oracle's power where the old test had none"
          if key and key["new"] >= 0.60 else
          "REFUTED -- the new test also lands far below the oracle, so the loss is intrinsic to judging "
          "an increment through a cross-fitted ridge at these n. Increment designs are the wrong "
          "instrument for this project and every challenge should be re-posed against marginal or "
          "partial statistics with cluster-robust inference.")
    p2 = ("CONFIRMED" if ret > 0.60 else f"REFUTED -- retained power {ret:.1%} <= 0.60")
    p3 = ("CONFIRMED -- the new test beats the old in every live cell"
          if len(beats) == len(live) else
          f"REFUTED -- the new test fails to beat the old in {len(live) - len(beats)} of {len(live)} "
          f"live cells")
    print(f"P1 at (60, 1, 0.35): new {key['new']:.1%} vs old {key['old']:.1%} vs oracle "
          f"{key['oracle']:.1%} -> {p1}")
    print(f"P2 mean retained power over {len(live)} live cells: {ret:.1%} -> {p2}")
    print(f"P3 -> {p3}")
    out["P1"], out["P2"], out["P3"] = p1, p2, p3
    out["G2"] = {"pass": bool(g2)}
    out["retained_mean"] = ret

    verdict = ("REPLACEMENT VALIDATED -- permutation_increment is calibrated and materially more "
               "powerful; every increment-decided null in this repository is now re-runnable and the "
               "ones that were reported as NEGATIVE must be re-derived (rule 2) or relabelled ABSENT "
               "(rule 31)."
               if (g1 and g2 and key["new"] >= 0.60 and ret > 0.60) else
               "REPLACEMENT NOT VALIDATED -- see the failing prediction above; do not re-run anything "
               "with this test until it is.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
