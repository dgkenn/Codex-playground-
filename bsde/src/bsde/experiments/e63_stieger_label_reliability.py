#!/usr/bin/env python3
"""E63 -- Challenge B. How reliable is Stieger's BCI-ability label, and does it lift E41's ceiling?

REGISTERED WHILE THE EXTRACTION IS STILL RUNNING AND BEFORE ANY CORRELATION HAS BEEN COMPUTED. 18 of 186
sessions were on disk when this was written; the only values that have been looked at are per-session
accuracies scrolling past in a progress log, and one of them (S1 session 1, accuracy 0.636905) was checked
against the figure the deposit's own documentation reports, as an extraction correctness check. No
odd-versus-even pair has been correlated, no subject has been aggregated, and no reliability computed.

=========================================================================================================
WHY THIS RUNS BEFORE THE CORRELATION, NOT AFTER IT
=========================================================================================================
E41 returned a Challenge B null: `uce_v1` against motor-imagery ability at rho = +0.0853 [-0.1066,
+0.2651], beaten by a deliberately weakened proxy for a fifteen-year-old published predictor. **That null
was an arithmetic problem, not a scientific one.** E38 then measured eegmmidb's label reliability at
**r_sb = 0.2918 [0.1163, 0.4345]**, which caps ANY predictor at rho ~ **0.5402** by attenuation alone,
against a minimum detectable effect of 0.272 at n = 104.

Q14's step 2 makes the sequencing standard: **measure the ceiling before running the correlation.** Stieger
2021's claim on Challenge B is arithmetic and checkable -- **450 trials per session against eegmmidb's 45
in total** -- and it is checkable from `BCI.TrialData` with no EEG touched at all, which is why this file
reads only the label.

=========================================================================================================
TWO RELIABILITIES, ANSWERING DIFFERENT QUESTIONS, AND CONFLATING THEM WOULD REPEAT E38's PROBLEM
=========================================================================================================
This deposit exists to study BCI LEARNING, so change between sessions is partly real.

  R1 WITHIN-SESSION SPLIT-HALF  odd versus even SCORED trials in the same session, Spearman-Brown
                                corrected. Learning cannot occur between interleaved trials, so this is
                                measurement noise alone. **It is the direct successor to E38's estimate and
                                the one comparable to it.**
  R2 ACROSS-SESSION             session k against session k+1 for the same subject. Measurement noise PLUS
                                real change. Necessarily lower; the gap between R1 and R2 is the learning.

**THEY BOUND DIFFERENT CEILINGS AND THE WRITE-UP MUST NOT SUBSTITUTE ONE FOR THE OTHER.** A design
predicting a SESSION's accuracy from that session's EEG is capped by sqrt(R1). A design predicting a
SUBJECT's stable ability is capped by something closer to sqrt(R2), because the part of a session's score
that does not persist is not a property of the subject.

PREDICTION, REGISTERED. R1 should substantially exceed eegmmidb's 0.2918, and the reason is arithmetic
rather than hopeful: at 450 trials the binomial noise on a half-session accuracy is about sqrt(.25/225) =
0.033, so unless true between-session accuracy varies by less than that, most of the observed variance is
signal. **FALSIFICATION: if R1's interval overlaps E38's 0.2918 substantially -- concretely, if its lower
bound falls below 0.4345, the upper bound of eegmmidb's interval -- then more trials did not buy a better
label and Q14's premise is wrong.** That would be a real finding and it would redirect Challenge B away
from this deposit.

  G1 COVERAGE GATE   >= `MIN_SESSIONS` sessions with both halves computable, across >= `MIN_SUBJECTS`
                     subjects; and for R2, >= `MIN_PAIRS` consecutive-session pairs.
  G2 SPLIT VALIDITY  the two halves must be exchangeable: mean |accuracy_odd - accuracy_even| must not
                     exceed `MAX_HALF_BIAS`, and the difference must not be systematically signed
                     (a paired test). A systematic gap means the halves differ in composition -- e.g.
                     unscored trials clustering -- and a correlation between them would not be a
                     reliability.

INFERENCE. Sessions from one subject are not independent, so every interval is a SUBJECT-clustered
bootstrap, never a naive one over sessions.

WHAT THIS CANNOT DO, stated because Q14 already found it out the hard way: **Stieger cannot test
`lrtc_alpha`.** The deposit is trial-epoched -- 450 separate 11.04 s epochs -- with no continuous recording,
and `lrtc_envelope` now refuses rather than silently shrinking its scale range. So a high reliability here
licenses a better SPECTRAL Challenge B experiment, not a replication of E42.

    python -m bsde.experiments.e63_stieger_label_reliability
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
OUT = os.path.join(RESULTS, "e63_stieger_label_reliability.json")

MIN_SESSIONS = 40
MIN_SUBJECTS = 20
MIN_PAIRS = 20
MAX_HALF_BIAS = 0.05
EEGMMIDB_RSB_HI = 0.4345           # E38's upper bound; R1's lower bound must clear it
REPS = 2000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _sb(r):
    """Spearman-Brown: a split-half correlation is the reliability of HALF the trials."""
    return 2.0 * r / (1.0 + r) if np.isfinite(r) and r > -1 else float("nan")


def _subject_boot(fn, subjects, rng, reps=REPS):
    uniq = np.unique(subjects)
    vals = []
    for _ in range(reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([np.flatnonzero(subjects == s) for s in drawn])
        v = fn(idx)
        if np.isfinite(v):
            vals.append(v)
    if len(vals) < reps // 2:
        return float("nan"), float("nan")
    v = np.sort(np.asarray(vals, float))
    return float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"MISSING {TABLE} -- run scripts/extract_stieger_labels.py first")
        return 2
    rows = [r for r in csv.DictReader(open(TABLE, newline=""))]
    subj = np.array([r["subject"] for r in rows])
    sess = np.array([int(r["session"]) for r in rows])
    odd = np.array([_f(r["accuracy_odd"]) for r in rows])
    even = np.array([_f(r["accuracy_even"]) for r in rows])
    acc = np.array([_f(r["accuracy"]) for r in rows])
    nsc = np.array([_f(r["n_scored"]) for r in rows])

    ok = np.isfinite(odd) & np.isfinite(even)
    n_sess, n_subj = int(ok.sum()), int(len(np.unique(subj[ok])))
    print(f"{len(rows)} sessions in table; {n_sess} with both halves, {n_subj} subjects")
    print(f"   scored trials per session: median {np.nanmedian(nsc):.0f} "
          f"(range {np.nanmin(nsc):.0f}-{np.nanmax(nsc):.0f})")

    pairs = []
    by_subj = defaultdict(dict)
    for i, r in enumerate(rows):
        if np.isfinite(acc[i]):
            by_subj[r["subject"]][int(r["session"])] = acc[i]
    for s, d in by_subj.items():
        for k in sorted(d):
            if k + 1 in d:
                pairs.append((s, d[k], d[k + 1]))
    g1 = n_sess >= MIN_SESSIONS and n_subj >= MIN_SUBJECTS and len(pairs) >= MIN_PAIRS
    print(f"   consecutive-session pairs: {len(pairs)}")
    print(f"   G1 {'PASS' if g1 else 'FAIL'} (need {MIN_SESSIONS} sessions, {MIN_SUBJECTS} subjects, "
          f"{MIN_PAIRS} pairs)")

    d = odd[ok] - even[ok]
    bias, absbias = float(d.mean()), float(np.abs(d).mean())
    tstat = bias / (d.std(ddof=1) / np.sqrt(d.size)) if d.size > 2 and d.std(ddof=1) > 0 else 0.0
    g2 = bool(absbias <= MAX_HALF_BIAS and abs(tstat) < 2.0)
    print(f"   G2 split validity: mean |odd-even| {absbias:.4f}, signed mean {bias:+.4f} "
          f"(t = {tstat:+.2f})   {'PASS' if g2 else 'FAIL'}")

    if not (g1 and g2):
        print("\nGATE FAILED -- no reliability is reported. Verdict ABSENT (rule 31), not negative.")
        json.dump({"gate_g1": g1, "gate_g2": g2, "n_sessions": n_sess, "n_subjects": n_subj,
                   "n_pairs": len(pairs), "half_abs_bias": absbias, "half_signed_bias": bias},
                  open(OUT, "w"), indent=2)
        return 1

    rng = np.random.default_rng(SEED)
    o, e, s_ok = odd[ok], even[ok], subj[ok]
    r1_half = spearman(o, e)
    r1 = _sb(r1_half)
    r1_lo, r1_hi = _subject_boot(lambda i: _sb(spearman(o[i], e[i])), s_ok, rng)

    ps = np.array([p[0] for p in pairs])
    a1 = np.array([p[1] for p in pairs])
    a2 = np.array([p[2] for p in pairs])
    r2 = spearman(a1, a2)
    r2_lo, r2_hi = _subject_boot(lambda i: spearman(a1[i], a2[i]), ps,
                                 np.random.default_rng(SEED + 1))

    print(f"\nR1 WITHIN-SESSION split-half (Spearman-Brown) = {r1:.4f} [{r1_lo:.4f}, {r1_hi:.4f}]"
          f"   raw half-half rho {r1_half:.4f}")
    print(f"R2 ACROSS-SESSION  session k vs k+1           = {r2:.4f} [{r2_lo:.4f}, {r2_hi:.4f}]"
          f"   ({len(pairs)} pairs)")
    print(f"\nattenuation ceilings   sqrt(R1) = {np.sqrt(max(r1, 0)):.4f}   "
          f"sqrt(R2) = {np.sqrt(max(r2, 0)):.4f}   (eegmmidb, E38: 0.5402)")

    if not np.isfinite(r1_lo):
        verdict = "ABSENT -- the subject-clustered bootstrap could not form an interval."
    elif r1_lo < EEGMMIDB_RSB_HI:
        verdict = (f"PREMISE NOT SUPPORTED -- R1's lower bound {r1_lo:.4f} does not clear eegmmidb's upper "
                   f"bound {EEGMMIDB_RSB_HI:.4f}. More trials per session did not buy a decisively better "
                   f"label, and Q14's premise for moving Challenge B to this deposit is wrong.")
    else:
        verdict = (f"PREMISE SUPPORTED -- R1 = {r1:.4f} [{r1_lo:.4f}, {r1_hi:.4f}] clears eegmmidb's "
                   f"0.2918 [0.1163, 0.4345] with no overlap. The label is decisively more reliable, "
                   f"lifting the within-session attenuation ceiling from 0.5402 to "
                   f"{np.sqrt(max(r1, 0)):.4f}. A SUBJECT-ability design is capped nearer sqrt(R2) = "
                   f"{np.sqrt(max(r2, 0)):.4f}, and the two must not be substituted for one another.")
    print(f"\nVERDICT: {verdict}")

    json.dump({"gate_g1": True, "gate_g2": True, "n_sessions": n_sess, "n_subjects": n_subj,
               "n_pairs": len(pairs), "half_abs_bias": absbias, "half_signed_bias": bias,
               "median_scored_trials": float(np.nanmedian(nsc)),
               "R1_within_session_sb": {"value": r1, "lo": r1_lo, "hi": r1_hi, "raw_half": r1_half},
               "R2_across_session": {"value": r2, "lo": r2_lo, "hi": r2_hi},
               "ceiling_within": float(np.sqrt(max(r1, 0))),
               "ceiling_across": float(np.sqrt(max(r2, 0))),
               "eegmmidb_reference": {"r_sb": 0.2918, "lo": 0.1163, "hi": 0.4345, "ceiling": 0.5402},
               "verdict": verdict}, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
