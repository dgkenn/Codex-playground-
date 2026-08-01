#!/usr/bin/env python3
"""E142 -- E36's drug legibilities against the EXACT null, by enumerating all 6,435 arm assignments.

REGISTERED BEFORE ANY PERMUTATION HAS BEEN RUN. This is an audit of numbers already reported in this
repository, and it introduces no new measurement: the features, the cohort and the statistic are E35's and
E36's untouched. What changes is the null they are compared against.

=========================================================================================================
WHY, AND IT CAME OUT OF A GATE FAILING
=========================================================================================================
E141's GATE N failed. A probe column of **pure Gaussian noise**, independent of quality, arm and
everything else, produced a drug legibility of **|AUC - 0.5| = 0.0844** on these 115 blocks. The bar was
0.05. So the bar sat below the statistic's own chance floor and no adjustment could ever have passed it --
my defect, and the second gate-mechanics defect in three experiments (E140's GATE Q was the first).

But a bar below the noise floor is not only a broken gate. It says something about the numbers the gate
was built around. E36's headline is:

    PHASE      frontwPLI 0.0584   allwPLI 0.0790   longwPLI 0.0917   backwPLI 0.1931
    AMPLITUDE  frontalDelta 0.0901  frontalAlpha 0.0946  AvgAlpha 0.0993  AvgGamma 0.1426
               AvgDelta 0.1771  EffDim 0.2700  NmlzCmplx 0.3478  allEnvCorr 0.3532

and three of the four PHASE values sit at or below what one draw of noise produced.

`docs/REFERENCE_AGAINST_ALL_THREE.md` diagnosed this class of error a month before it happened, in these
words: *"That is a discrimination statistic, and it has the wrong null. Failing to reject 'the agents are
distinguishable' is not evidence that they are equivalent."* The diagnosis was applied to the design of
future two-agent work and never turned back on the numbers already in hand.

=========================================================================================================
THE CORRECT NULL, AND WHY IT IS NOT THE OBVIOUS ONE
=========================================================================================================
The 115 unresponsive scalp blocks come from **15 patients**, and **arm is nested inside patient**: a
patient is either a dexmedetomidine patient or a propofol patient, never both (constraint A1). So the
contrast has 15 independent units, not 115, and any feature that varies between patients -- which is every
EEG feature ever measured -- will produce a drug legibility by chance far above the row-level floor.

The exact null follows directly and requires no model: **enumerate every way of labelling 7 of the 15
patients as dexmedetomidine**, keeping each patient's real blocks and real feature values, and recompute
the statistic. C(15, 7) = **6,435** assignments, which is small enough to enumerate completely, so the
p-values below carry no Monte Carlo error at all.

Both nulls are reported, because the difference between them is the size of the error:
    ROW-LEVEL     labels shuffled across the 115 blocks -- what treating blocks as independent implies
    PATIENT-LEVEL labels shuffled across the 15 patients -- exact, enumerated, correct

=========================================================================================================
GATE -- and it validates this file against an independent implementation (rule 23)
=========================================================================================================
G1  CORRECTNESS. E139's G3 sampled the patient-level drug permutation 2,000 times with different code and
    obtained a fraction of **0.0030** for `allEnvCorr` (observed +0.3532). This file's exact enumeration
    must return a p-value for `allEnvCorr` inside [0.000, 0.010]. Outside that, the enumeration is wrong
    and nothing below is reported. Self-written code checked against self-written code shares blind spots;
    this checks it against a differently-written sampler that already exists.
G2  MANIFEST. Exactly 15 patients, 7 dexmedetomidine and 8 propofol, and 6,435 enumerated assignments.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
P1  ABSOLUTE LEAKAGE. **PREDICTION: at least 3 of the 4 PHASE features have exact patient-level
    p > 0.20**, i.e. are not distinguishable from a between-patient nuisance. If instead the phase
    features clear p < 0.05, then their low legibility is a measured low value rather than an absence of
    power, and E36's absolute claim stands as written.

P2  THE FAMILY CONTRAST, which is the claim E36 actually defended and the one that matters.

        GAP = mean |AUC-0.5|(AMPLITUDE) - mean |AUC-0.5|(PHASE) = +0.0913

    E36 tested its partition against **495 alternative partitions of the 13 features** and got p = 0.002.
    That is a real test and it is not what this file tests. Enumerating partitions asks *"is this split of
    the features special, given these AUC values?"*; it holds the AUC values fixed and cannot ask whether
    they are noise. This file permutes the **patients**, which asks *"could these AUC values, and hence
    this gap, arise with no drug effect at all?"* The two are complementary and only one of them has been
    run.

    **PREDICTION: exact patient-level p for GAP is > 0.05** -- the family contrast does not survive the
    correct null.

    **IF p < 0.05**, E36's contrast survives clustering and the correction is confined to P1: the relative
    claim (amplitude leaks more than phase) would stand and only the absolute claim (phase leaks little)
    would fall. That is the more favourable branch for the existing record and it is written first so it
    cannot be presented afterwards as the thing that was expected.

CONSEQUENCE IF BOTH PREDICTIONS HOLD. E36's family split cannot support Challenge A's acceptance
condition, which is stated in absolute terms -- *"MINIMISING drug-identification information"* -- and is
therefore a question about how close to zero the leakage is, not about which family leaks more. The
deposit's answer would be that it cannot resolve leakage below roughly the clustered floor measured here,
whatever that floor turns out to be. **This does not retract E36's partition result**, which tested a
different proposition and tested it correctly.

WHAT WAS ALREADY SEEN (rule 41). E141's full output including its failed probe gates; a 20,000-draw
row-level noise floor (mean 0.0435, p95 0.1059) and a 20,000-draw *model-based* clustered floor
(mean 0.1253, p95 0.2993) computed while diagnosing E141's GATE N failure. The model-based clustered floor
assumed a between-patient variance ratio and is superseded by the exact enumeration here; it is disclosed
because it is why the exact version was written and because its magnitude informed P1's bar.

    python bsde/src/bsde/experiments/e142_exact_clustered_null_for_drug_legibility.py
"""
from __future__ import annotations

import csv
import itertools
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import auc                                            # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "krause_dexprosleep_allData.csv")
OUT = os.path.join(RESULTS, "e142_exact_clustered_null.json")

PHASE = ["frontwPLI", "backwPLI", "longwPLI", "allwPLI"]
AMPLITUDE = ["EffDim", "NmlzCmplx", "allEnvCorr", "AvgDelta", "AvgAlpha", "AvgGamma",
             "frontalDelta", "frontalAlpha"]
FEATURES = AMPLITUDE + PHASE


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def main(argv=None) -> int:
    rows = []
    for r in csv.DictReader(open(TABLE, newline="")):
        if r["Subdural"] != "0" or r["label"] not in ("U", "U_dex"):
            continue
        rows.append({"pid": r["patientID"], "arm": 1 if r["label"] == "U_dex" else 0,
                     **{c: _f(r.get(c, "")) for c in FEATURES}})

    pids = sorted({r["pid"] for r in rows})
    arm_of = {p: next(r["arm"] for r in rows if r["pid"] == p) for p in pids}
    n_dex = sum(arm_of.values())
    n_assign = math.comb(len(pids), n_dex)
    g2 = len(pids) == 15 and n_dex == 7 and n_assign == 6435
    print(f"G2 MANIFEST  {len(rows)} blocks, {len(pids)} patients ({n_dex} dex / "
          f"{len(pids) - n_dex} prop), {n_assign} assignments -> {'PASS' if g2 else 'FAIL'}")

    pidx = np.array([pids.index(r["pid"]) for r in rows])
    X = {c: np.array([r[c] for r in rows], float) for c in FEATURES}
    finite = {c: np.isfinite(X[c]) for c in FEATURES}
    real = np.array([arm_of[p] for p in pids], int)

    def leg(col, lab):
        """|AUC-0.5| of `col` against a patient-level labelling `lab` (length 15)."""
        m = finite[col]
        y = lab[pidx[m]]
        if y.min() == y.max():
            return float("nan")
        return abs(auc(list(y), list(X[col][m])) - 0.5)

    obs = {c: leg(c, real) for c in FEATURES}
    gap_obs = float(np.nanmean([obs[c] for c in AMPLITUDE]) - np.nanmean([obs[c] for c in PHASE]))

    # ---- exact enumeration --------------------------------------------------------------------------
    ge = {c: 0 for c in FEATURES}
    ge_gap = 0
    null_vals = {c: [] for c in FEATURES}
    null_gap = []
    for combo in itertools.combinations(range(len(pids)), n_dex):
        lab = np.zeros(len(pids), int)
        lab[list(combo)] = 1
        v = {c: leg(c, lab) for c in FEATURES}
        g = float(np.nanmean([v[c] for c in AMPLITUDE]) - np.nanmean([v[c] for c in PHASE]))
        null_gap.append(g)
        if g >= gap_obs:
            ge_gap += 1
        for c in FEATURES:
            null_vals[c].append(v[c])
            if math.isfinite(v[c]) and v[c] >= obs[c]:
                ge[c] += 1
    p_exact = {c: ge[c] / n_assign for c in FEATURES}
    p_gap = ge_gap / n_assign

    # ---- G1 CORRECTNESS against E139's independent sampler --------------------------------------------
    g1 = 0.0 <= p_exact["allEnvCorr"] <= 0.010
    print(f"G1 CORRECTNESS  allEnvCorr exact p = {p_exact['allEnvCorr']:.4f}; E139's independent 2,000-draw "
          f"sampler gave 0.0030  -> {'PASS' if g1 else 'FAIL'}")
    if not (g1 and g2):
        print("\nGATE FAILED -- nothing below is reported.")
        return 1

    # ---- row-level null, for the comparison ------------------------------------------------------------
    rng = np.random.default_rng(142)
    rowlab = np.array([r["arm"] for r in rows], int)
    p_row = {}
    for c in FEATURES:
        m = finite[c]
        y0, x0 = rowlab[m], X[c][m]
        hits = 0
        for _ in range(20000):
            hits += abs(auc(list(rng.permutation(y0)), list(x0)) - 0.5) >= obs[c]
        p_row[c] = hits / 20000

    q = np.quantile
    fl_row = float(np.mean([q(np.abs(np.asarray(null_vals[c], float))[~np.isnan(null_vals[c])], .95)
                            for c in FEATURES]))
    print(f"\n{'feature':16s} {'family':10s} {'|AUC-.5|':>9s} {'p_row':>8s} {'p_exact':>9s} "
          f"{'null p95':>9s}")
    per = {}
    for c in sorted(FEATURES, key=lambda c: -obs[c]):
        nv = np.asarray(null_vals[c], float)
        nv = nv[np.isfinite(nv)]
        per[c] = {"family": "PHASE" if c in PHASE else "AMPLITUDE", "obs": obs[c],
                  "p_row": p_row[c], "p_exact": p_exact[c],
                  "null_mean": float(nv.mean()), "null_p95": float(q(nv, .95))}
        print(f"{c:16s} {per[c]['family']:10s} {obs[c]:9.4f} {p_row[c]:8.4f} {p_exact[c]:9.4f} "
              f"{per[c]['null_p95']:9.4f}")

    ng = np.asarray(null_gap, float)
    ng = ng[np.isfinite(ng)]
    print(f"\nP2  GAP = {gap_obs:+.4f}   exact patient-level p = {p_gap:.4f}   "
          f"null mean {ng.mean():+.4f}, p95 {q(ng, .95):+.4f}")

    n_phase_null = sum(1 for c in PHASE if p_exact[c] > 0.20)
    p1 = ("CONFIRMED -- the phase family's low leakage is absence of power, not measured absence"
          if n_phase_null >= 3 else
          "REFUTED -- the phase features clear the exact null, so their low legibility is a measured value")
    p2 = ("CONFIRMED -- the family contrast does not survive the exact patient-level null"
          if p_gap > 0.05 else
          "REFUTED -- E36's family contrast survives the correct null; only the absolute claim falls")
    print(f"\nP1  {n_phase_null} of 4 PHASE features have exact p > 0.20  -> {p1}")
    print(f"P2  -> {p2}")

    inflation = float(np.mean([per[c]["p_exact"] / max(per[c]["p_row"], 1 / 20000) for c in FEATURES]))
    print(f"\nHOW BIG WAS THE ERROR  mean ratio of exact p to row-level p across the 12 features: "
          f"{inflation:.1f}x")
    print(f"                       mean 95th percentile of the exact null: {fl_row:.4f} "
          f"(the floor E36's numbers had to clear and were never compared to)")

    json.dump({"experiment": "E142", "n_blocks": len(rows), "n_patients": len(pids),
               "n_assignments": n_assign, "per_feature": per, "gap_obs": gap_obs,
               "gap_p_exact": p_gap, "gap_null_mean": float(ng.mean()),
               "gap_null_p95": float(q(ng, .95)), "P1": p1, "P2": p2,
               "n_phase_at_null": n_phase_null, "mean_p_inflation": inflation,
               "mean_exact_null_p95": fl_row},
              open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
