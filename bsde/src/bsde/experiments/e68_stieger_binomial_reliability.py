#!/usr/bin/env python3
"""E68 -- Challenge B. The label ceiling again, with an estimator that needs no split at all.

SUCCESSOR TO E63, AND THE CHANGED INSTRUMENT IS THE ESTIMATOR -- not the threshold, not the cohort, not
the horizon. **The falsification criterion is carried over unchanged**: the reliability's lower bound must
clear **0.4345**, the upper bound of eegmmidb's reliability measured in E38, or Q14's premise for moving
Challenge B to this deposit is wrong.

=========================================================================================================
WHY E63 COULD NOT REPORT, AND WHY THAT WAS THE GATE WORKING
=========================================================================================================
E63's G2 required the two halves of a split-half estimate to be exchangeable. They are not. Over 185
sessions the signed odd-minus-even difference is **+0.0094 (t = +2.68)**: the first trial of each pair
scores systematically higher than the second. Diagnosed rather than assumed -- the bias is present in
sessions with an odd number of scored trials (**+0.0085**) and an even number (**+0.0104**) alike, so it is
not the artefact of one half receiving an extra trial. Something in the task alternates.

A correlation between two non-exchangeable halves is not a reliability, so E63 returned ABSENT (rule 31)
and reported nothing. That is correct and it is preserved.

**One thing about E63's gate WAS badly chosen and it is recorded here rather than quietly fixed.** `|t| < 2`
is a SIGNIFICANCE criterion: it asks whether a bias is detectable, not whether it is material. At n = 185 it
detects a difference of under one percentage point. A properly scaled gate would have been an equivalence
bound. **That flaw is not being used to rescue E63** -- its verdict stands -- but a design whose gate
tightens as data accumulates is a design that punishes its own sample size.

=========================================================================================================
THE ESTIMATOR, AND WHY IT IS BETTER RATHER THAN MERELY DIFFERENT
=========================================================================================================
Session accuracy is a proportion over Bernoulli trials, so its measurement error is known ANALYTICALLY and
does not have to be estimated from a split:

    observed variance  =  true between-session variance  +  binomial sampling variance
    reliability        =  ( Var(acc) - mean[ p(1-p) / n ] ) / Var(acc)

**No split, so no ordering artefact can exist by construction** -- which is the exact defect that stopped
E63. It also uses every trial rather than half of them, so it is not a half-length estimate needing a
Spearman-Brown correction at all, and one source of approximation disappears.

Reported ALONGSIDE, not instead of:

  R2 ACROSS-SESSION   Spearman between session k and session k+1 for the same subject, 122 consecutive
                      pairs. Measurement noise PLUS real change. **This deposit exists to study LEARNING,
                      so the gap between R1 and R2 is signal, not error**, and the two bound different
                      ceilings: a design predicting a SESSION's accuracy from that session's EEG is capped
                      by sqrt(R1); one predicting a SUBJECT's stable ability is capped nearer sqrt(R2).
                      They must never be substituted for one another.

  G1 COVERAGE      >= 40 sessions, >= 20 subjects, >= 20 consecutive pairs (carried from E63 unchanged).
  G2 NON-DEGENERACY  the binomial correction must not exceed the observed variance -- if it does, the
                     estimate is negative and the honest report is that between-session differences are
                     indistinguishable from trial sampling noise, NOT a reliability of zero dressed up.

VERDICT RULE, wrong direction first.

  (a) DEGENERATE          -- G2 failed: observed variance does not exceed binomial noise. Accuracy
                             differences between sessions are sampling error and the label carries no
                             stable signal at this trial count.
  (b) PREMISE NOT SUPPORTED -- R1's lower bound does not clear 0.4345. More trials per session did not buy
                             a decisively better label than eegmmidb's, and Q14's premise is wrong.
  (c) PREMISE SUPPORTED   -- R1's interval clears 0.4345 with no overlap. Report the lifted ceiling
                             sqrt(R1), and report sqrt(R2) separately as the cap on a subject-ability
                             design.

    python -m bsde.experiments.e68_stieger_binomial_reliability
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from bsde.verifier.stats import spearman                                      # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "stieger_labels.csv")
OUT = os.path.join(RESULTS, "e68_stieger_binomial_reliability.json")

MIN_SESSIONS, MIN_SUBJECTS, MIN_PAIRS = 40, 20, 20
EEGMMIDB_RSB_HI = 0.4345
REPS = 5000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _reliability(p, n):
    """Binomial-corrected reliability of a proportion measured over `n` Bernoulli trials."""
    var = float(np.var(p, ddof=1))
    err = float(np.mean(p * (1.0 - p) / n))
    return (var - err) / var if var > 0 else float("nan"), var, err


def main() -> int:
    rows = list(csv.DictReader(open(TABLE, newline="")))
    subj = np.array([r["subject"] for r in rows])
    acc = np.array([_f(r["accuracy"]) for r in rows])
    nsc = np.array([_f(r["n_scored"]) for r in rows])
    ok = np.isfinite(acc) & np.isfinite(nsc) & (nsc > 0)
    p, n, s = acc[ok], nsc[ok], subj[ok]

    pairs, by = [], defaultdict(dict)
    for r in rows:
        if np.isfinite(_f(r["accuracy"])):
            by[r["subject"]][int(r["session"])] = _f(r["accuracy"])
    for sub, d in by.items():
        for k in sorted(d):
            if k + 1 in d:
                pairs.append((sub, d[k], d[k + 1]))

    n_sess, n_sub = int(ok.sum()), int(len(np.unique(s)))
    g1 = n_sess >= MIN_SESSIONS and n_sub >= MIN_SUBJECTS and len(pairs) >= MIN_PAIRS
    print(f"{n_sess} sessions, {n_sub} subjects, {len(pairs)} consecutive pairs   "
          f"G1 {'PASS' if g1 else 'FAIL'}")
    print(f"   scored trials/session: median {np.median(n):.0f} (range {n.min():.0f}-{n.max():.0f})")
    print(f"   accuracy: mean {p.mean():.4f}  sd {p.std(ddof=1):.4f}")
    if not g1:
        print("G1 FAILED -- verdict ABSENT (rule 31).")
        json.dump({"gate_g1": False}, open(OUT, "w"), indent=2)
        return 1

    r1, var, err = _reliability(p, n)
    g2 = np.isfinite(r1) and var > err
    print(f"\n   observed variance {var:.6f}   binomial noise {err:.6f}   "
          f"G2 {'PASS' if g2 else 'FAIL'}")
    rng = np.random.default_rng(SEED)
    uniq = np.unique(s)
    boot = []
    for _ in range(REPS):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([np.flatnonzero(s == u) for u in drawn])
        v, vv, ee = _reliability(p[idx], n[idx])
        if np.isfinite(v):
            boot.append(v)
    b = np.sort(boot)
    lo, hi = float(np.quantile(b, .025)), float(np.quantile(b, .975))
    print(f"R1 WITHIN-SESSION binomial-corrected reliability = {r1:.4f} [{lo:.4f}, {hi:.4f}]")

    ps = np.array([x[0] for x in pairs])
    a1 = np.array([x[1] for x in pairs])
    a2 = np.array([x[2] for x in pairs])
    r2 = spearman(a1, a2)
    up = np.unique(ps)
    b2 = []
    rng2 = np.random.default_rng(SEED + 1)
    for _ in range(REPS):
        drawn = rng2.choice(up, size=len(up), replace=True)
        i = np.concatenate([np.flatnonzero(ps == u) for u in drawn])
        v = spearman(a1[i], a2[i])
        if np.isfinite(v):
            b2.append(v)
    b2 = np.sort(b2)
    r2lo, r2hi = float(np.quantile(b2, .025)), float(np.quantile(b2, .975))
    print(f"R2 ACROSS-SESSION  session k vs k+1              = {r2:.4f} [{r2lo:.4f}, {r2hi:.4f}]"
          f"   ({len(pairs)} pairs)")
    print(f"\nceilings: sqrt(R1) = {np.sqrt(max(r1, 0)):.4f}   sqrt(R2) = {np.sqrt(max(r2, 0)):.4f}   "
          f"(eegmmidb, E38: 0.5402)")

    if not g2:
        verdict = ("DEGENERATE -- observed between-session variance does not exceed binomial trial noise. "
                   "Accuracy differences between sessions are sampling error at this trial count.")
    elif lo < EEGMMIDB_RSB_HI:
        verdict = (f"PREMISE NOT SUPPORTED -- R1's lower bound {lo:.4f} does not clear eegmmidb's upper "
                   f"bound {EEGMMIDB_RSB_HI:.4f}. More trials per session did not buy a decisively better "
                   f"label and Q14's premise for moving Challenge B here is wrong.")
    else:
        verdict = (f"PREMISE SUPPORTED -- R1 = {r1:.4f} [{lo:.4f}, {hi:.4f}] clears eegmmidb's 0.2918 "
                   f"[0.1163, 0.4345] with no overlap. The within-session ceiling rises from 0.5402 to "
                   f"{np.sqrt(max(r1, 0)):.4f}. A SUBJECT-ability design is capped nearer sqrt(R2) = "
                   f"{np.sqrt(max(r2, 0)):.4f}; the two must not be substituted for one another.")
    print(f"\nVERDICT: {verdict}")
    json.dump({"gate_g1": True, "gate_g2": bool(g2), "n_sessions": n_sess, "n_subjects": n_sub,
               "n_pairs": len(pairs), "observed_variance": var, "binomial_noise": err,
               "R1": {"value": r1, "lo": lo, "hi": hi},
               "R2": {"value": r2, "lo": r2lo, "hi": r2hi},
               "ceiling_within": float(np.sqrt(max(r1, 0))),
               "ceiling_across": float(np.sqrt(max(r2, 0))),
               "eegmmidb_reference": {"r_sb": 0.2918, "hi": EEGMMIDB_RSB_HI, "ceiling": 0.5402},
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
