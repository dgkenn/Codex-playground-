"""E173 — two estimators disagree in SIGN on the same rows. Which one is right?

REGISTERED BEFORE ANY SWEEP HAS BEEN RUN.

=========================================================================================================
THE DISAGREEMENT, AND WHY IT CANNOT BE LEFT STANDING
=========================================================================================================
E166 re-derived e99 on its recorded cohort, rebuilt to the row — 5,798 windows, 247 cases, 977 positive —
and got the OPPOSITE SIGN to the recorded result:

    recorded (oob_auc_increment, cluster bootstrap, POSITIVE = adds)   **-0.0306 [-0.0524, -0.0101]**
             ... an interval excluding zero BELOW it, printed and logged as **HURTS**
    E166     (permutation_increment, 5-fold grouped cross-fit)         **+0.0200, p = 0.0000**  ADDS

Same rows, same two features, same clustering, opposite conclusions, both with intervals or p-values that
exclude the null. **Error-catalogue rule 16: when two arms of the same test disagree in SIGN, the
definition is doing the work, not the biology.** Until this is settled, e99 has no verdict in either
direction — and neither, in a weaker sense, do e34, e37 and e58, which E166 also moved with the same
machinery.

THE PARSIMONIOUS HYPOTHESIS, stated in advance and testable. The two schemes differ in how much data the
model is fitted on. A cluster bootstrap draws 247 clusters with replacement, so roughly **1 - 1/e = 63 %**
of clusters appear in training and the rest are scored out of bag. Five-fold grouped cross-fitting trains
on **80 %**. A model with one extra column pays a variance cost that shrinks as the training set grows, so
an increment can be negative at 63 % and positive at 80 % with no inconsistency at all. If that is what is
happening, the increment should move MONOTONICALLY with training fraction and cross zero somewhere between
the two.

=========================================================================================================
DESIGN — THE SWEEP, AND THE CONTROL THAT MAKES IT READABLE
=========================================================================================================
    ARM 1  REAL DATA. e99's cohort. The increment of {BIS, whole_head_exponent} over {BIS} for
           `meta_sr > 0`, computed at grouped-CV training fractions of 50 %, 63 %, 80 %, 90 % and 95 %
           (2-, 2.7-, 5-, 10- and 20-fold), plus the cluster-bootstrap out-of-bag estimator itself at its
           own native ~63 %. Every scheme holds CASES out whole.

    ARM 2  **SYNTHETIC GROUND TRUTH, AND IT IS THE POINT OF THE FILE (rules 40, 67).** A system is built
           in which the added column genuinely carries independent signal, with the cluster structure,
           cluster count, rows-per-cluster and base rate matched to e99's. The truth is known by
           construction, so the sweep can be scored for CORRECTNESS rather than merely for consistency.
           A second synthetic system is built in which the added column is pure noise. **An estimator that
           returns the wrong sign on either synthetic system at a given training fraction is disqualified
           at that fraction**, and that is a statement no amount of arguing about the real data can
           produce.

           Without this arm the experiment could only report that two numbers differ. With it, the
           question "which one is right" has an answer.

=========================================================================================================
GATES
=========================================================================================================
G1  REBUILD: e99's cohort must come back at 5,798 windows / 247 cases / 977 positive, or nothing is
    reported (rule 31).
G2  THE DISAGREEMENT MUST REPRODUCE. Both estimators are re-run here rather than quoted from their files
    (rule 59), and they must still disagree in sign. If they do not, the disagreement was a seed or a
    version artefact and THAT is the result — reported, not buried.
G3  THE SYNTHETIC SYSTEMS MUST BE SOLVABLE. On the signal system, at least one estimator at some training
    fraction must recover the correct sign; on the noise system, at least one must return an interval or
    p-value covering the null. If neither holds, the simulation is mis-specified and arm 2 says nothing.

=========================================================================================================
VERDICT — ENUMERATED SO THAT "MY NEW ESTIMATOR WINS" IS NOT THE ONLY REACHABLE OUTCOME (rule 37)
=========================================================================================================
  (1) NOT REPRODUCED     G2 fails: the two estimators agree when both are re-run here.
  (2) SIMULATION FAILED  G3 fails.
  (3) BOOTSTRAP RIGHT    on the synthetic systems the cluster bootstrap recovers the truth where the
                         cross-fit does not. Then E166's four overturns are wrong and must be withdrawn.
                         **This branch is written first among the substantive ones deliberately**, because
                         it is the one that costs the most to accept and is therefore the one most likely
                         to be reasoned away.
  (4) CROSS-FIT RIGHT    the cross-fit recovers the truth where the bootstrap does not. e99's recorded
                         HURTS is withdrawn and E166's overturns stand.
  (5) TRAINING FRACTION  both are correct at their own training fraction and the real increment crosses
                         zero inside the sweep. Then neither verdict is an error and the honest statement
                         is that the increment for this feature is not sign-stable in the regime where
                         this cohort's data lives — which would be a caveat every increment in this
                         project inherits.
  (6) NEITHER            both fail the synthetic systems. Every increment-decided row in the ledger is
                         then unsupported by its own machinery.

NO PREDICTION IS REGISTERED. I built `permutation_increment` and would be predicting my own tool wins;
E146's calibration work justifies its p-VALUE and says nothing about which cross-fitting scheme estimates
the increment's SIGN, which is a different question and the one asked here.

    python bsde/src/bsde/experiments/e173_estimator_disagreement.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import (auc, grouped_cv_predict, oob_auc_increment,   # noqa: E402
                                 permutation_increment)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e173_estimator_disagreement.json")
SEED = 20260801

# folds -> training fraction: 2 -> 50 %, 3 -> 67 %, 5 -> 80 %, 10 -> 90 %, 20 -> 95 %
FOLDS = (2, 3, 5, 10, 20)
N_SIM = 40
REPS_BOOT = 400


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def build_e99():
    rows = list(csv.DictReader(open(GRID, newline="")))
    bis = np.array([_f(r["meta_bis"]) for r in rows])
    sr = np.array([_f(r["meta_sr"]) for r in rows])
    x = np.array([_f(r.get("whole_head_exponent", "")) for r in rows])
    subj = np.array([r["subject"] for r in rows])
    m = np.isfinite(bis) & np.isfinite(sr) & np.isfinite(x)
    return bis[m], x[m], (sr[m] > 0).astype(float), subj[m]


def cv_increment(Xa, Xb, y, subject, folds, seed):
    """AUC increment (POSITIVE = the addition adds) at a given grouped-CV training fraction."""
    rng = np.random.default_rng(seed)
    pa = grouped_cv_predict(Xa, y, subject, rng, folds=folds)
    pb = grouped_cv_predict(Xb, y, subject, np.random.default_rng(seed), folds=folds)
    ok = np.isfinite(pa) & np.isfinite(pb)
    if ok.sum() < 100 or len(np.unique(y[ok])) < 2:
        return float("nan")
    return float(auc(y[ok].astype(int), pb[ok]) - auc(y[ok].astype(int), pa[ok]))


def simulate(n_clusters, rows_per_cluster, base_rate, beta_extra, rng):
    """A system whose answer is known: `beta_extra` = 0 is a noise column, > 0 a genuine one.

    Cluster structure, cluster count, rows per cluster and base rate are matched to the real cohort, and
    the baseline column carries a real effect so the extra column has an incumbent to add to.
    """
    subj, base, extra, y = [], [], [], []
    for c in range(n_clusters):
        n = max(3, int(rng.poisson(rows_per_cluster)))
        u = rng.normal()                                   # a cluster-level shift, as real cohorts have
        b = rng.normal(size=n) + u
        e = rng.normal(size=n) + 0.5 * u
        lin = 1.0 * b + beta_extra * e
        p = 1.0 / (1.0 + np.exp(-(lin - np.quantile(lin, 1 - base_rate))))
        subj.append(np.full(n, f"s{c}"))
        base.append(b)
        extra.append(e)
        y.append((rng.random(n) < p).astype(float))
    return (np.concatenate(base), np.concatenate(extra), np.concatenate(y), np.concatenate(subj))


def main() -> int:
    print("E173 — two estimators disagree in sign on the same rows; the synthetic arm decides")
    if not os.path.exists(GRID):
        print(f"ABSENT: {GRID}")
        return 2
    bis, x, y, subj = build_e99()
    n_cases = len(set(subj.tolist()))
    res = {"experiment": "E173", "n_windows": int(len(y)), "n_cases": n_cases,
           "n_positive": int(y.sum())}
    g1 = (len(y) == 5798 and n_cases == 247 and int(y.sum()) == 977)
    print(f"G1 REBUILD  {len(y)} windows, {n_cases} cases, {int(y.sum())} positive   "
          f"{'PASS' if g1 else '*** FAIL (expected 5798 / 247 / 977)'}")
    res["G1_pass"] = bool(g1)
    if not g1:
        res["verdict"] = "NOT-INTERPRETABLE"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    Xa, Xb = bis.reshape(-1, 1), np.column_stack([bis, x])

    # G2 -- both estimators re-run HERE (rule 59), not quoted
    boot = oob_auc_increment(Xa, Xb, y, subj, np.random.default_rng(SEED), reps=REPS_BOOT)[:3]
    perm = permutation_increment(Xa, Xb, y, subj, np.random.default_rng(SEED),
                                 stat=lambda t, p: -auc(np.asarray(t, int), np.asarray(p, float)),
                                 reps=300)
    perm_signed = -perm[0]                      # back into the POSITIVE = adds convention
    res["G2"] = {"bootstrap": {"increment": boot[0], "lo": boot[1], "hi": boot[2]},
                 "crossfit_5fold": {"increment": float(perm_signed), "p": float(perm[1])}}
    print(f"G2 REPRODUCE  bootstrap {boot[0]:+.4f} [{boot[1]:+.4f}, {boot[2]:+.4f}]   "
          f"cross-fit {perm_signed:+.4f} (p {perm[1]:.4f})")
    disagree = np.isfinite(boot[0]) and np.isfinite(perm_signed) and np.sign(boot[0]) != np.sign(perm_signed)
    res["G2_disagree"] = bool(disagree)
    print(f"   signs {'DISAGREE — the disagreement reproduces' if disagree else 'AGREE'}")

    # ARM 1 -- the real sweep
    print(f"\nARM 1  real data, grouped-CV training fraction sweep (POSITIVE = the exponent adds)")
    sweep = {}
    for k in FOLDS:
        v = cv_increment(Xa, Xb, y, subj, k, SEED + k)
        sweep[k] = float(v)
        print(f"   {k:>2d}-fold ({100 * (1 - 1 / k):.0f} % train): {v:+.5f}")
    sweep["bootstrap_oob"] = float(boot[0])
    print(f"   bootstrap OOB (~63 % train): {boot[0]:+.5f}")
    res["arm1_sweep"] = {str(k): v for k, v in sweep.items()}

    # ARM 2 -- synthetic systems with a known answer
    print(f"\nARM 2  synthetic systems, {N_SIM} replicates each, structure matched to the real cohort")
    rpc = len(y) / n_cases
    br = float(y.mean())
    arm2 = {}
    for tag, beta in (("signal", 0.8), ("noise", 0.0)):
        per_fold = {k: [] for k in FOLDS}
        boots = []
        for i in range(N_SIM):
            rng = np.random.default_rng(SEED + 1000 * (1 if tag == "signal" else 2) + i)
            b, e, yy, ss = simulate(n_cases, rpc, br, beta, rng)
            A, B = b.reshape(-1, 1), np.column_stack([b, e])
            for k in FOLDS:
                per_fold[k].append(cv_increment(A, B, yy, ss, k, SEED + i))
            boots.append(oob_auc_increment(A, B, yy, ss, np.random.default_rng(SEED + i), reps=120)[0])
        truth = 1 if beta > 0 else 0
        row = {}
        print(f"   {tag} system (truth: the extra column {'ADDS' if truth else 'is noise'})")
        for k in FOLDS:
            v = np.asarray([q for q in per_fold[k] if np.isfinite(q)])
            frac_pos = float((v > 0).mean())
            row[str(k)] = {"mean": float(v.mean()), "frac_positive": frac_pos, "n": int(v.size)}
            ok = frac_pos >= 0.9 if truth else 0.25 <= frac_pos <= 0.75
            print(f"      {k:>2d}-fold ({100 * (1 - 1 / k):.0f} % train): mean {v.mean():+.5f}, "
                  f"positive in {frac_pos:.0%} of replicates   {'correct' if ok else '*** WRONG'}")
        bv = np.asarray([q for q in boots if np.isfinite(q)])
        fb = float((bv > 0).mean())
        row["bootstrap_oob"] = {"mean": float(bv.mean()), "frac_positive": fb, "n": int(bv.size)}
        okb = fb >= 0.9 if truth else 0.25 <= fb <= 0.75
        print(f"      bootstrap OOB (~63 %): mean {bv.mean():+.5f}, positive in {fb:.0%}   "
              f"{'correct' if okb else '*** WRONG'}")
        arm2[tag] = row
    res["arm2"] = arm2

    # ---- verdict
    sig, noi = arm2["signal"], arm2["noise"]

    def correct(scheme):
        return (sig[scheme]["frac_positive"] >= 0.9
                and 0.25 <= noi[scheme]["frac_positive"] <= 0.75)

    cf_ok = any(correct(str(k)) for k in FOLDS)
    bt_ok = correct("bootstrap_oob")
    g3 = cf_ok or bt_ok
    res["G3_pass"] = bool(g3)
    res["crossfit_recovers"] = bool(cf_ok)
    res["bootstrap_recovers"] = bool(bt_ok)
    vals = [sweep[k] for k in FOLDS if np.isfinite(sweep[k])] + [sweep["bootstrap_oob"]]
    crosses = bool(vals and min(vals) < 0 < max(vals))
    res["real_sweep_crosses_zero"] = crosses

    if not disagree:
        v, why = "NOT-REPRODUCED", ("re-run here, the two estimators agree in sign; the recorded "
                                    "disagreement was a seed or version artefact")
    elif not g3:
        v, why = "SIMULATION-FAILED", "neither estimator recovers a known answer; arm 2 says nothing"
    elif bt_ok and not cf_ok:
        v, why = "BOOTSTRAP-RIGHT", ("the cluster bootstrap recovers the truth where no cross-fit "
                                     "training fraction does; E166's four overturns must be withdrawn")
    elif cf_ok and not bt_ok:
        v, why = "CROSS-FIT-RIGHT", ("cross-fitting recovers the truth where the bootstrap does not; "
                                     "e99's recorded HURTS is withdrawn and E166's overturns stand")
    elif crosses:
        v, why = "TRAINING-FRACTION", ("both schemes are correct on the synthetic systems and the real "
                                       "increment crosses zero inside the sweep: the sign is not stable "
                                       "in the regime this cohort lives in, and every increment in this "
                                       "ledger inherits that caveat")
    else:
        v, why = "UNRESOLVED", ("both schemes are correct on the synthetic systems, the real sweep does "
                                "not cross zero, and the disagreement is therefore not explained by "
                                "training fraction — no verdict")
    res["verdict"], res["why"] = v, why
    print(f"\nVERDICT {v} — {why}")
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
