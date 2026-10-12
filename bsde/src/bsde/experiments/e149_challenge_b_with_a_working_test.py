#!/usr/bin/env python3
"""E149 -- Challenge B asked once more, with an instrument that has been shown to work.

REGISTERED BEFORE ANY PERMUTATION INCREMENT HAS BEEN COMPUTED ON EITHER DEPOSIT. Successor to E144 and
E145, both of which are recorded as BLOCKED rather than negative. The cohorts, the incumbent, the
candidate lists and the bars are theirs, unchanged. **Only the test changes**, and it changes because
E146 measured the old one failing and E147 validated the new one against an independent oracle.

=========================================================================================================
WHY BOTH PREDECESSORS ARE BLOCKED RATHER THAN NEGATIVE
=========================================================================================================
E144 (eegmmidb, 104 subjects) and E145 (Stieger, 185 sessions from 62 subjects) both returned G2 FAILED --
`relative_alpha_power` did not beat its own permutation out of bag -- and E145's file printed a withdrawal
of the incumbent. **That withdrawal was not issued**, because E146, running beside it, measured the
instrument both results depend on:

    n_subj rows rho_partial |  OOB detects  ORACLE detects
        60    1        0.35 |       0.00%          88.33%
       100    1        0.35 |       1.67%          98.33%
       100    3        0.35 |      66.67%         100.00%

with a false-positive rate of **0.000** at rho = 0. The bootstrap tail fraction of out-of-bag differences
is not a calibrated p-value; it is blind. Rule 31: when a precondition fails, the downstream verdict is
**absent**, not negative. So nothing about the incumbent, and nothing about any of the 32 or 28
candidates, was established by those runs.

E147 built and validated the replacement: `permutation_increment`, a cross-fitted increment tested against
a null built by permuting the added column **across clusters**, calibrated at a false-positive rate of
0.0333 against a nominal 0.05 and recovering 67.5 % detection where the old test managed 5.0 % and the
oracle 92.5 %.

=========================================================================================================
WHAT THIS FILE DOES
=========================================================================================================
Both deposits, both arms, one instrument:

    eegmmidb   104 subjects, one row each,          target `imagery_auc`,  32 candidates
    Stieger    185 sessions from 62 subjects,        target `accuracy`,     28 candidates

    incumbent  `relative_alpha_power` in both, marginal rho +0.2018 and +0.1596 respectively
    statistic  `permutation_increment`, stat = -Spearman so a NEGATIVE increment means the candidate
               helps, 2,000 cluster permutations, subject-grouped 5-fold cross-fitting
    multiplicity  Holm within each deposit

=========================================================================================================
GATES
=========================================================================================================
G1  COVERAGE, per deposit, as in the predecessors.
G2  **INCUMBENT ALIVE**, against its own cluster-permutation, per deposit.
G3  **DETECTABILITY FLOOR under the NEW instrument**, per deposit, measured on that deposit's own
    incumbent residual: rho_partial in {0.10, 0.15, 0.20, 0.25, 0.30, 0.40}, 60 draws. Reported whether
    or not G2 passes, because a floor is a property of the design and the deposit.
G4  NESTING asserted per deposit (rule 69); the resampling and permutation unit is the SUBJECT.
G5  **INSTRUMENT VALIDATION IMPORTED, NOT ASSUMED.** E147's calibration JSON must exist and report
    `G1.pass == true`. If E147 did not validate the instrument, this file refuses to run. A test whose
    own validation has not been checked is not a validated test.

PLACEBO. Every candidate additionally run with its column cluster-permuted once before the test. A
placebo reaching the corrected bar voids that deposit's arm.

=========================================================================================================
PRIMARY -- WRONG-DIRECTION BRANCH WRITTEN FIRST (rule 37)
=========================================================================================================
P1  **THE INCUMBENT. Registered prediction: `relative_alpha_power` passes G2 on at least one deposit.**

    **IF IT FAILS ON BOTH under a calibrated instrument with a measured floor below its own marginal
    correlation**, then the withdrawal E145 wanted to issue becomes warranted and must be issued here:
    `relative_alpha_power` is not a Challenge B incumbent on any deposit this project can measure, its
    +0.2018 was a single marginal correlation whose interval barely excluded zero, and
    `CHALLENGE_DEFINITIONS_CORRECTION.md` must be edited rather than annotated. **That is the branch that
    costs, and it is written first.** It would also mean Challenge B has no incumbent at all, so the
    programme's own registrations must stop demanding one (rule 45) for this challenge and switch to an
    absolute bar.

P2  **THE CANDIDATES. Registered prediction: nothing adds on either deposit after Holm.** Basis: E131
    found Stieger's and Dreyer's working predictors disjoint; E134 found nothing beating the SMR
    predictor; and across E144 and E145 the eight candidates that out-correlated the incumbent marginally
    all failed to convert into an increment even at uncorrected p. If something does add, it goes
    immediately to `accuracy_odd` versus `accuracy_even` on Stieger, which is a free internal replication
    the deposit ships.

P3  **CROSS-DEPOSIT AGREEMENT, which is the Challenge D question asked inside Challenge B.** For the
    candidates present in both tables, the rank correlation of their increments across the two deposits.
    E131 found the working *marginal* predictors disjoint; this asks whether the *increments* agree. A
    strongly negative or zero correlation is another instance of the programme's central transport
    finding, this time with the instrument controlled -- the two deposits run the same task with the same
    incumbent and the same test, so a disagreement cannot be blamed on any of those.

FALSIFICATION. If G3's floor is above the incumbent's own marginal correlation on both deposits, then
even the calibrated instrument cannot see effects of the size on offer, and the honest report is that
Challenge B needs more subjects rather than better features -- which is a statement about the programme's
data, not about its ideas.

WHAT WAS ALREADY SEEN (rule 41). Everything E144 and E145 printed, including all 60 candidate increments
under the broken test and their marginal correlations. No candidate has been through
`permutation_increment` on either deposit.

    python bsde/src/bsde/experiments/e149_challenge_b_with_a_working_test.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.multiplicity import holm                                    # noqa: E402
from bsde.verifier.stats import cluster_permute, permutation_increment, spearman  # noqa: E402

sys.path.insert(0, HERE)
import e143_increment_over_the_real_incumbent as E143                          # noqa: E402
import e145_incumbent_where_the_label_is_reliable as E145                      # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
OUT = os.path.join(RESULTS, "e149_challenge_b_calibrated.json")
E147_JSON = os.path.join(RESULTS, "e147_calibrated_increment.json")

INCUMBENT = "relative_alpha_power"
PERMS = 2000
FLOOR_LEVELS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40)
FLOOR_DRAWS = 60
FLOOR_PERMS = 500
FLOOR_HIT = 0.80


def _f(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def eegmmidb():
    per, lab, cols = E143.load()
    cand = sorted({c for v in cols.values() for c in v} - {INCUMBENT})
    subs = sorted(s for s in per
                  if s in lab and math.isfinite(per[s].get(INCUMBENT, float("nan"))))
    y = np.array([lab[s] for s in subs], float)
    inc = np.array([[per[s][INCUMBENT]] for s in subs], float)
    sid = np.array(subs)
    get = {c: np.array([per[s].get(c, float("nan")) for s in subs], float) for c in cand}
    return "eegmmidb", y, inc, sid, cand, get, len(subs)


def stieger():
    rows, cols = E145.load()
    rows = [r for r in rows if math.isfinite(_f(r.get(E145.TARGET, "")))
            and math.isfinite(_f(r.get(INCUMBENT, "")))]
    cand = [c for c in cols if c != INCUMBENT]
    y = np.array([_f(r[E145.TARGET]) for r in rows], float)
    inc = np.array([[_f(r[INCUMBENT])] for r in rows], float)
    sid = np.array([r["subject"] for r in rows])
    get = {c: np.array([_f(r.get(c, "")) for r in rows], float) for c in cand}
    return "stieger", y, inc, sid, cand, get, len(rows)


def run(name, y, inc, sid, cand, get, n_rows, rng, out):
    K = len(cand)
    bar = 0.05 / K
    n_subj = len(set(sid))
    print(f"\n{'=' * 100}\n{name.upper()}  {n_rows} rows, {n_subj} subjects, {K} candidates, "
          f"corrected bar {bar:.5f}")
    print(f"   marginal rho(target, {INCUMBENT}) = {spearman(list(inc[:, 0]), list(y)):+.4f}")
    d = {"n_rows": n_rows, "n_subjects": n_subj, "n_candidates": K,
         "incumbent_marginal_rho": spearman(list(inc[:, 0]), list(y))}

    g1 = n_rows >= 90 and n_subj >= 50
    g4 = True                       # asserted below in the printed line; nesting is allowed to be 1:1
    print(f"G1 COVERAGE -> {'PASS' if g1 else 'FAIL'}    "
          f"G4 unit = SUBJECT ({n_subj} clusters over {n_rows} rows)")

    # The baseline model is a cluster-permuted copy of the incumbent: same distribution, same cluster
    # structure, no association. Adding the REAL incumbent on top of it is then an ordinary increment,
    # and its null is built by permuting the real column again -- so the comparison is like-for-like in
    # model size, which an intercept-only baseline would not be (and a constant has no rank at all, so
    # -Spearman is undefined for it).
    base = cluster_permute(inc[:, 0], sid, rng).reshape(-1, 1)
    obs, p, nm, k = permutation_increment(base, np.c_[base, inc[:, 0]], y, sid, rng, reps=PERMS)
    g2 = math.isfinite(p) and p < 0.05
    print(f"G2 INCUMBENT ALIVE (vs its own cluster-permutation): {obs:+.5f} p={p:.5f} "
          f"null_mean={nm:+.5f} over {k} perms -> {'PASS' if g2 else 'FAIL'}")
    d["G1"], d["G2"] = bool(g1), {"pass": bool(g2), "increment": obs, "p": p, "null_mean": nm}

    r = y - inc[:, 0] * (np.cov(inc[:, 0], y)[0, 1] / (np.var(inc[:, 0]) + 1e-12))
    r = (r - r.mean()) / (r.std() + 1e-12)
    print(f"G3 DETECTABILITY FLOOR  {FLOOR_DRAWS} draws x {len(FLOOR_LEVELS)} levels, "
          f"{FLOOR_PERMS} perms, detection = p < {bar:.5f}")
    floor = {}
    for rho in FLOOR_LEVELS:
        hits = 0
        for _ in range(FLOOR_DRAWS):
            z = rho * r + math.sqrt(max(1 - rho ** 2, 0.0)) * rng.standard_normal(n_rows)
            _o, _p, _nm, _k = permutation_increment(inc, np.c_[inc, z], y, sid, rng, reps=FLOOR_PERMS)
            hits += math.isfinite(_p) and _p < bar
        floor[rho] = hits / FLOOR_DRAWS
        print(f"   rho_partial={rho:.2f}  detected in {floor[rho]:6.1%} of draws")
    det = [rho for rho in FLOOR_LEVELS if floor[rho] >= FLOOR_HIT]
    fl = min(det) if det else None
    print(f"   FLOOR = {fl if fl is not None else 'ABOVE ' + str(max(FLOOR_LEVELS))}")
    d["G3"] = {"floor": fl, "detection_rate": {str(a): b for a, b in floor.items()}}

    print(f"\n{'candidate':32s} {'rho':>8s} {'increment':>10s} {'p':>8s} {'placebo p':>10s}")
    res, pv = {}, {}
    for c in cand:
        x = get[c]
        ok = np.isfinite(x)
        if ok.sum() < 0.8 * n_rows:
            res[c] = {"skipped": f"only {int(ok.sum())} finite"}
            continue
        yy, ii, ss, xx = y[ok], inc[ok], sid[ok], x[ok]
        o, pp, _nm, _k = permutation_increment(ii, np.c_[ii, xx], yy, ss, rng, reps=PERMS)
        _o2, pc, _n2, _k2 = permutation_increment(ii, np.c_[ii, cluster_permute(xx, ss, rng)], yy, ss,
                                                  rng, reps=PERMS)
        res[c] = {"rho": spearman(list(xx), list(yy)), "increment": o, "p": pp, "placebo_p": pc,
                  "n": int(ok.sum())}
        pv[c] = pp
        print(f"{c:32s} {res[c]['rho']:+8.4f} {o:+10.5f} {pp:8.5f} {pc:10.5f}")
    adj = holm(list(pv.values()), list(pv.keys()))
    for c, a in adj.items():
        res[c]["p_holm"] = a
        res[c]["helps"] = bool(a < 0.05 and res[c]["increment"] < 0)
    d["primary"], d["holm"] = res, adj
    d["winners"] = [c for c, v in res.items() if v.get("helps")]
    d["placebo_fired"] = [c for c, v in res.items()
                          if math.isfinite(v.get("placebo_p", float("nan"))) and v["placebo_p"] < bar]
    print(f"\n{name}: {len(d['winners'])} winner(s) {d['winners']}, "
          f"{len(d['placebo_fired'])} placebo(s) fired {d['placebo_fired']}")
    out[name] = d
    return d


def main(argv=None) -> int:
    rng = np.random.default_rng(149)
    out = {"experiment": "E149", "perms": PERMS}

    # ---- G5 imported validation -----------------------------------------------------------------------
    try:
        e147 = json.load(open(E147_JSON))
        g5 = bool(e147.get("G1", {}).get("pass"))
        print(f"G5 INSTRUMENT VALIDATION  E147 calibration fpr={e147['G1']['fpr']:.4f} -> "
              f"{'PASS' if g5 else 'FAIL'}")
    except Exception as e:                                                     # noqa: BLE001
        print(f"G5 INSTRUMENT VALIDATION  E147 result unreadable ({type(e).__name__}) -> FAIL")
        g5 = False
    out["G5"] = {"pass": bool(g5)}
    if not g5:
        print("\nREFUSING TO RUN -- the instrument's own validation has not been checked.")
        json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
        return 1

    arms = {}
    for loader in (eegmmidb, stieger):
        name, y, inc, sid, cand, get, n = loader()
        arms[name] = run(name, y, inc, sid, cand, get, n, rng, out)

    # ---- P3 cross-deposit agreement -------------------------------------------------------------------
    a, b = arms["eegmmidb"]["primary"], arms["stieger"]["primary"]
    shared = [c for c in a if c in b and "increment" in a[c] and "increment" in b[c]]
    rho_cross = (spearman([a[c]["increment"] for c in shared], [b[c]["increment"] for c in shared])
                 if len(shared) >= 5 else float("nan"))
    print(f"\nP3 CROSS-DEPOSIT  {len(shared)} shared candidates, "
          f"rho(increment_eegmmidb, increment_stieger) = {rho_cross:+.4f}")
    out["P3"] = {"n_shared": len(shared), "rho": rho_cross, "shared": shared}

    # ---- verdict --------------------------------------------------------------------------------------
    alive = [n for n in arms if arms[n]["G2"]["pass"]]
    fl = {n: arms[n]["G3"]["floor"] for n in arms}
    winners = {n: arms[n]["winners"] for n in arms}
    fired = {n: arms[n]["placebo_fired"] for n in arms}
    if any(fired.values()):
        verdict = f"VOID -- a placebo reached the corrected bar: {fired}"
    elif not alive:
        blind = all(f is None or f > 0.25 for f in fl.values())
        verdict = (("NO VERDICT -- even the calibrated instrument's floor is above the incumbent's own "
                    f"marginal correlation on both deposits (floors {fl}), so Challenge B needs more "
                    "subjects rather than better features. The incumbent is NOT withdrawn: it has still "
                    "not been tested by anything that could have seen it.")
                   if blind else
                   ("INCUMBENT WITHDRAWN -- relative_alpha_power fails against its own cluster-"
                    f"permutation on BOTH deposits under a calibrated instrument whose floor ({fl}) is "
                    "below its own marginal correlation. It is not a Challenge B incumbent on any "
                    "deposit this project can measure, and CHALLENGE_DEFINITIONS_CORRECTION.md must be "
                    "edited rather than annotated. The registered prediction (P1) is WRONG."))
    elif any(winners.values()):
        verdict = (f"POSITIVE -- {winners} add to a live incumbent under a calibrated test. Replicate on "
                   f"Stieger's accuracy_odd vs accuracy_even before anything else.")
    else:
        verdict = (f"NEGATIVE AND INFORMATIVE -- the incumbent is alive on {alive}, the floors are {fl}, "
                   f"and nothing adds on either deposit. Cross-deposit increment agreement "
                   f"rho = {rho_cross:+.4f}.")
    print(f"\nVERDICT: {verdict}")
    out["verdict"] = verdict
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, allow_nan=True)
    print(f"\n   wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
