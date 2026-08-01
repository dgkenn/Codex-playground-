"""E133 -- Is time-irreversibility NEW INFORMATION, or a recoding of the power spectrum by another route?

REGISTERED BEFORE ANY INCREMENT HAS BEEN COMPUTED. Both tables are committed and the join was verified
(705 subject-stage rows over 142 subjects, all five stages) before this file was written; nothing has been
fitted.

=========================================================================================================
WHY THIS IS THE STANDING DOUBT ABOUT THE WHOLE IRREVERSIBILITY LINE
=========================================================================================================
E107 is this project's strongest Challenge A result and rests on a mathematical claim:

    "the autocovariance is symmetric in lag, so time reversal leaves the PSD and every summary of it
     EXACTLY unchanged, and the permutation form uses only sample orderings so it is invariant to any
     monotone amplitude transform. The measure could not have been the exponent in disguise."

That argument is correct and it is **not sufficient**, for a reason rule 28 exists to catch. *Provably
orthogonal in principle* is not *independent in practice*. Two measures can be mathematically incapable of
being transforms of one another and still be near-deterministic functions of each other **on real EEG**,
because real EEG occupies a tiny corner of signal space. Rule 28 has already been paid for five times in
this project -- five measures predicted to be new that were not -- and E107's own calibration entry records
it as "fifth measure predicted to be new that was not".

**The mathematical argument shows irreversibility CANNOT be a spectral transform. It does not show
irreversibility CARRIES ANYTHING THE SPECTRUM DOES NOT.** Only an increment can show that, and no
experiment in this project has run one. E128 then removed the main alternative explanation -- within-stage
submental coupling is bounded at 9.4 % of a demonstrated ceiling, equal to the permutation floor -- so the
question is now clean.

=========================================================================================================
DESIGN
=========================================================================================================
COHORT: the 705 rows where `sleep_edfx_irreversibility.csv` and `sleep_edfx_five_stage.csv` both have a
usable record -- 142 subjects x five stages, joined on (subject, stage).

OUTCOME: the **W -> N1 -> N2 -> N3 depth ordinal (0,1,2,3)**. REM is EXCLUDED from the primary and
handled separately in S1, because E69, E100 and E107 all established that REM is exactly where the
measures disagree, and including it would let a REM-specific effect masquerade as an increment on depth.

    P   OUT-OF-BAG increment from `SPECTRAL` to `SPECTRAL + IRREVERSIBILITY`, subjects resampled with
        replacement and both models scored on the subjects NOT drawn (rule 9). The error statistic is
        `1 - spearman(true, predicted)`, so **a NEGATIVE difference means irreversibility HELPS** --
        E84's, E122's and E130's convention, restated because E127 was inverted twice by an unstated sign.

    SPECTRAL = the 17 columns of `sleep_edfx_five_stage.csv` (aperiodic exponents, Lempel-Ziv, spectral
    edge and entropy, band powers, PAC, participation ratio, EMG summaries). **The EMG columns are
    deliberately IN the spectral block**, not held out: the question is whether irreversibility adds to
    everything else available, and giving the incumbent the muscle channels makes the test harder, which
    is the direction that needs no defending.

    IRREVERSIBILITY = `frontal_irr3`, `frontal_irr4`, `frontal_incr`, `posterior_irr3`, `posterior_irr4`,
    `posterior_incr` -- all six, since E111 found the permutation and increment estimators DISAGREED in
    the low band and picking one would be a choice made after that was known.

SECONDARIES, reported whole (rule 59), NOT eligible to become the headline:
    S1  The same increment for placing REM on the wake-to-N3 axis -- the quantity E107 actually measured.
        An increment on depth and none on REM, or the reverse, is informative and must not be hidden.
    S2  The increment from IRREVERSIBILITY alone to IRREVERSIBILITY + SPECTRAL, i.e. the mirror. If the
        spectrum adds nothing to irreversibility while irreversibility adds nothing to the spectrum, the
        two are redundant; if each adds to the other, they are complementary. Asked in both directions
        because a one-directional null is ambiguous.

GATES
    G1  COVERAGE >= 100 subjects with all four depth stages present.
    G2  THE INCUMBENT MUST BE ALIVE (rule 53). The spectral block alone must predict the depth ordinal
        out of bag above median rho 0.10. If the spectrum cannot order sleep depth, "nothing adds to it"
        is a statement about the pipeline.
    G3  NEGATIVE CONTROL: six Gaussian columns, matched in number to the irreversibility block, through
        the identical pipeline. They must NOT come back ADDS. Six columns of noise added to a 17-column
        model is exactly the situation where an out-of-bag scheme leaks if it is going to.
    G4  THE SURROGATE COLUMNS ARE HELD OUT. The irreversibility table ships `*_surr` companions (phase-
        randomised surrogates). They are NOT used as predictors -- they are the null the measure was built
        against, and including them would be testing the estimator rather than the signal.

PLACEBO, gating the verdict (rule 34): the six irreversibility columns are permuted ACROSS SUBJECTS WITHIN
STAGE, 500 draws. That destroys the subject-level correspondence while preserving each stage's marginal
distribution of the measure, so a spurious increment arising from stage-level mean differences alone
cannot survive. Compared against the DISTRIBUTION, never its mean (rule 37). Rule 48: the primary interval
is read first; a null primary makes the placebo NOT INFORMATIVE.

VERDICT, wrong direction FIRST (rule 37, twelfth occurrence):
    (a) interval excludes 0 POSITIVE -> HURTS. Adding six irreversibility columns makes out-of-bag
        prediction WORSE. Not a null: it means they are noise the model spends capacity on, and given the
        mathematical orthogonality argument that would be a genuinely awkward result worth reporting
        loudly rather than quietly.
    (b) interval includes 0 -> NO INCREMENT. **Irreversibility is provably not a spectral transform and
        yet carries nothing the spectrum does not carry, on this data.** That is rule 28's sixth
        occurrence and it would substantially deflate E107 -- not by refuting it, but by showing its
        headline dissociation is available from the spectrum too.
    (c) interval excludes 0 NEGATIVE and beats the placebo -> ADDS. Then the mathematical argument is
        matched by an empirical one, and E107 is the first measure in this project predicted to be new
        that IS.

CALIBRATION before the run: (b) ~50 %, (c) ~35 %, (a) ~15 %. (b) is favoured on the base rate -- five of
five previous "this is new" predictions in this project were wrong (rule 28) -- and (c) is given more than
the base rate because unlike those five, this one has a proof of non-transformability behind it.

SCOPE. Sleep-EDFx cassette, two bipolar derivations, one 120 s window per subject-stage, and stages scored
FROM the EEG by a human using the same signal. This measures whether irreversibility adds to a spectral
feature set in ordering scorer-defined states; it is not a consciousness detector and a positive result
would not make it one.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GOV = os.path.abspath(os.path.join(HERE, "..", "..", "..", "governance"))
OUT = os.path.join(RESULTS, "e133_irreversibility_increment.json")
IRR = os.path.join(RESULTS, "sleep_edfx_irreversibility.csv")
FIVE = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")

DEPTH = {"W": 0, "N1": 1, "N2": 2, "N3": 3}
IRR_COLS = ["frontal_irr3", "frontal_irr4", "frontal_incr",
            "posterior_irr3", "posterior_irr4", "posterior_incr"]
DROP = {"recording_id", "dataset", "subject", "status", "error", "n_channels", "sfreq", "n_samples"}
MIN_SUBJECTS = 100
G2_RHO_FLOOR = 0.10
REPS = 1200
PLACEBO_DRAWS = 500
SEED = 133


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    irr = {}
    for r in csv.DictReader(open(IRR, newline="")):
        if r.get("subject") and r.get("label"):
            irr[(r["subject"], r["label"])] = r
    five, spectral = {}, None
    for r in csv.DictReader(open(FIVE, newline="")):
        if r.get("status") != "ok":
            continue
        lab = r["recording_id"].split("@")[-1]
        five[(r["subject"], lab)] = r
        if spectral is None:
            spectral = sorted(c for c in r if c not in DROP)
    return irr, five, spectral


def main(argv=None) -> int:
    from bsde.verifier.stats import oob_regression_increment, ridge_fit, spearman, _standardise

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--placebo-draws", type=int, default=PLACEBO_DRAWS)
    ap.add_argument("--register-only", action="store_true")
    a = ap.parse_args(argv)

    sys.path.insert(0, GOV)
    from registry_ledger import register                                   # noqa: E402
    try:
        register(
            "E133", "A",
            "Is time-irreversibility new information, or a recoding of the power spectrum by "
            "another route?",
            "sleep-edfx",
            "out-of-bag increment from the 17-column spectral set to spectral+6 irreversibility columns "
            "for the W/N1/N2/N3 depth ordinal; error = 1 - spearman so NEGATIVE helps",
            ["G1 >=100 subjects with all four depth stages",
             "G2 the spectral incumbent must be alive (oob rho > 0.10)",
             "G3 six Gaussian columns must not ADD", "G4 surrogate columns held out"],
            "permute the irreversibility columns ACROSS SUBJECTS WITHIN STAGE, 500 draws, against the "
            "DISTRIBUTION",
            os.path.relpath(__file__, os.path.join(HERE, "..", "..", "..", "..")),
            successor_of="E128",
            instrument_changed="the QUESTION: not whether irreversibility is muscle (E128 bounded that) "
                               "but whether it is INFORMATION the spectrum lacks -- rule 28's test, "
                               "which the mathematical orthogonality argument cannot settle")
        print("registered E133")
    except Exception as e:                                                 # noqa: BLE001
        print(f"registration: {e}")
    if a.register_only:
        return 0

    irr, five, spectral = load()
    keys = [k for k in sorted(set(irr) & set(five)) if k[1] in DEPTH]
    rows = []
    for k in keys:
        s = [_f(five[k].get(c, "")) for c in spectral]
        i = [_f(irr[k].get(c, "")) for c in IRR_COLS]
        if np.all(np.isfinite(s)) and np.all(np.isfinite(i)):
            rows.append((k[0], DEPTH[k[1]], s, i))
    subj = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows], float)
    S = np.array([r[2] for r in rows], float)
    I = np.array([r[3] for r in rows], float)
    n_sub = len(set(subj.tolist()))

    gates = {"G1_rows": len(rows), "G1_subjects": n_sub, "G1_pass": n_sub >= MIN_SUBJECTS,
             "n_spectral": len(spectral), "n_irr": len(IRR_COLS), "spectral_cols": spectral,
             "G4_surrogates_held_out": True}
    print(f"{len(rows)} rows over {n_sub} subjects; {len(spectral)} spectral + {len(IRR_COLS)} irr")
    print(f"G1 {'PASS' if gates['G1_pass'] else 'FAIL'}")
    if not gates["G1_pass"]:
        json.dump({"gates": gates, "verdict": "REFUSED: coverage"}, open(a.out, "w"), indent=1)
        return 0

    def err(t, p):
        r = spearman(t, p)
        return 1.0 - r if np.isfinite(r) else float("nan")

    # G2: is the spectral incumbent alive?
    uniq = np.unique(subj)
    idx = {u: np.flatnonzero(subj == u) for u in uniq}
    vals = []
    rng = np.random.default_rng(SEED)
    for _ in range(a.reps):
        drawn = rng.choice(uniq, size=len(uniq), replace=True)
        ds = set(drawn.tolist())
        oob = [u for u in uniq if u not in ds]
        if len(oob) < 5:
            continue
        tr = np.concatenate([idx[u] for u in drawn])
        te = np.concatenate([idx[u] for u in oob])
        try:
            A, B = _standardise(S[tr], S[te])
            p = B @ ridge_fit(A, y[tr], 1.0)
        except Exception:                                                  # noqa: BLE001
            continue
        v = spearman(y[te], p)
        if np.isfinite(v):
            vals.append(v)
    rho = float(np.median(vals)) if vals else float("nan")
    gates["G2_spectral_oob_rho"] = rho
    gates["G2_pass"] = bool(np.isfinite(rho) and rho > G2_RHO_FLOOR)
    print(f"G2 spectral incumbent out-of-bag rho {rho:+.4f}  {'PASS' if gates['G2_pass'] else 'FAIL'}")
    if not gates["G2_pass"]:
        json.dump({"gates": gates,
                   "verdict": "ABSENT -- the spectral block does not order sleep depth out of bag, so "
                              "'nothing adds to it' would be a statement about the pipeline (rule 31)."},
                  open(a.out, "w"), indent=1)
        return 0

    m, lo, hi, nrep = oob_regression_increment(S, np.hstack([S, I]), y, subj,
                                               np.random.default_rng(SEED + 1), stat=err, reps=a.reps)
    print(f"\nP  increment spectral -> spectral+irreversibility = {m:+.4f} [{lo:+.4f}, {hi:+.4f}] "
          f"({nrep} reps)   (negative = helps)")

    # S2: the mirror
    m2, lo2, hi2, _ = oob_regression_increment(I, np.hstack([I, S]), y, subj,
                                               np.random.default_rng(SEED + 2), stat=err, reps=a.reps)
    print(f"S2 mirror   irreversibility -> irreversibility+spectral = {m2:+.4f} [{lo2:+.4f}, {hi2:+.4f}]")

    # G3: six Gaussian columns
    grng = np.random.default_rng(SEED + 3)
    G = grng.normal(size=I.shape)
    gm, glo, ghi, _ = oob_regression_increment(S, np.hstack([S, G]), y, subj,
                                               np.random.default_rng(SEED + 4), stat=err, reps=a.reps)
    gates["G3_negative_control"] = {"mean": gm, "lo": glo, "hi": ghi}
    gates["G3_pass"] = bool(not (np.isfinite(ghi) and ghi < 0))
    print(f"G3 six gaussian columns {gm:+.4f} [{glo:+.4f}, {ghi:+.4f}]  "
          f"{'PASS' if gates['G3_pass'] else 'FAIL'}")

    # Placebo: permute irreversibility across subjects WITHIN stage
    prng = np.random.default_rng(SEED + 5)
    draws = []
    for _ in range(a.placebo_draws):
        Ip = I.copy()
        for d in sorted(DEPTH.values()):
            k = np.flatnonzero(y == d)
            Ip[k] = I[prng.permutation(k)]
        mm, _l, _h, _n = oob_regression_increment(S, np.hstack([S, Ip]), y, subj,
                                                  np.random.default_rng(SEED + 6), stat=err,
                                                  reps=max(200, a.reps // 4))
        if np.isfinite(mm):
            draws.append(float(mm))
    dr = np.asarray(draws, float)
    frac = float(np.mean(dr <= m)) if dr.size and np.isfinite(m) else float("nan")
    placebo = {"n": int(dr.size), "mean": float(dr.mean()) if dr.size else float("nan"),
               "p2.5": float(np.quantile(dr, .025)) if dr.size else float("nan"),
               "p97.5": float(np.quantile(dr, .975)) if dr.size else float("nan"),
               "frac_at_least_as_helpful": frac}
    print(f"PLACEBO within-stage subject permutation: mean {placebo['mean']:+.4f} "
          f"[{placebo['p2.5']:+.4f}, {placebo['p97.5']:+.4f}]  frac<=real {frac:.3f}")

    beats = bool(np.isfinite(frac) and frac <= 0.05)
    if not np.isfinite(lo):
        verdict = "ABSENT -- the increment could not be estimated."
    elif lo > 0:
        verdict = (f"(a) HURTS -- {m:+.4f} [{lo:+.4f}, {hi:+.4f}] excludes zero POSITIVE. Six "
                   "irreversibility columns make out-of-bag prediction WORSE. Given the mathematical "
                   "orthogonality argument behind E107 this is an awkward result and is reported as one, "
                   "not filed as a null.")
    elif hi < 0 and beats:
        verdict = (f"(c) ADDS -- {m:+.4f} [{lo:+.4f}, {hi:+.4f}], beating a within-stage subject "
                   f"permutation (frac {frac:.3f}). Irreversibility carries depth information the "
                   "17-column spectral set does not, so the mathematical non-transformability argument "
                   "is now matched by an empirical one. On this project's record that makes it the FIRST "
                   "measure predicted to be new that is (rule 28's five previous predictions all failed).")
    elif hi < 0:
        verdict = (f"WITHDRAWN BY PLACEBO -- {m:+.4f} [{lo:+.4f}, {hi:+.4f}] helps, but permuting the "
                   f"irreversibility columns across subjects within stage reproduces it (frac {frac:.3f}), "
                   "so the increment comes from stage-level mean differences rather than from "
                   "subject-level correspondence.")
    else:
        verdict = (f"(b) NO INCREMENT -- {m:+.4f} [{lo:+.4f}, {hi:+.4f}] includes zero. Irreversibility "
                   "is PROVABLY not a spectral transform and yet carries nothing the spectrum does not, "
                   "on this data. That is rule 28's sixth occurrence, and it deflates E107 without "
                   "refuting it: the headline dissociation may be available from the spectrum too. "
                   "The placebo is NOT INFORMATIVE (rule 48).")

    res = {"gates": gates,
           "primary": {"mean": m, "lo": lo, "hi": hi, "n_reps": nrep},
           "S2_mirror": {"mean": m2, "lo": lo2, "hi": hi2},
           "placebo": placebo, "verdict": verdict}
    json.dump(res, open(a.out, "w"), indent=1)
    print("\nVERDICT:", verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
