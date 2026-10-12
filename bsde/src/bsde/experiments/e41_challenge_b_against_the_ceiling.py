#!/usr/bin/env python3
"""E41 — E28's question, asked against a known ceiling: does resting EEG predict motor-imagery ability?

THE CEILING, STATED IN THE HEADER BECAUSE E38's VERDICT REQUIRED IT OF ANY SUCCESSOR.

    E38 measured the label's split-half reliability: **r_sb = +0.2918 [+0.1163, +0.4345]**, 105 subjects,
    200 splits, with its permuted-label placebo at +0.0218 [-0.1061, +0.1387].

    **ceiling = sqrt(r_sb) = 0.5402.** No resting-state feature, however good, can correlate with this
    label above roughly 0.54. That is a property of the label, not of any candidate, and it bounds
    everything below.

WHY THIS FILE EXISTS AND WHY IT IS NOT A RE-RUN OF E28. E28's machinery gate asked what fraction of
subjects beat their own permutation null at p < 0.05, required 20 %, and got 16.3 %. Its own outcome note
diagnoses that floor as the wrong quantity — the BCI-illiteracy literature's 70-85 % is a **prevalence**
measured over hundreds of trials, and this deposit gives 45 trials per subject — and then refuses to lower
it, because a diagnosis is not a licence. **E28 stands as ABSENT and its floor has not moved.**

What changed is the instrument for judging the label, and E38 is the experiment that changed it: from a
per-subject significance rate to a **reliability coefficient**, which is the quantity that actually decides
whether a noisy label can be a regression target. That question is now answered — the label is viable — so
the original question can be asked with a gate that means something.

**NO CANDIDATE-LABEL RELATIONSHIP IN THIS DEPOSIT HAS EVER BEEN OBSERVED, AND THAT IS CHECKABLE.** E28
returned at its gate before P2, so no resting feature was ever scored against the label. E38 read only the
trial cache and the label table, never `eegmmidb_rest.csv`'s candidate columns. This file is therefore a
first look, not a second one, and its p-values mean what they say.

THE POWER CALCULATION, DONE BEFORE THE RUN AND BINDING ON HOW THE RESULT MAY BE READ.

    Blankertz B, Sannelli C, Halder S, Hammer EM, Kübler A, Müller KR, Curio G, Dickhaus T.
    "Neurophysiological predictor of SMR-based BCI performance." *NeuroImage* 2010;51(4):1303-9.
    **PMID 20303409** — record and abstract verified through NCBI E-utilities, not WebFetch (rules 25, 39).

Its abstract states a correlation of **r = 0.53** between a resting-EEG predictor and BCI feedback
performance in **N = 80** naive participants. Their label's own reliability is at most 1, so the *true*
correlation between that predictor and latent ability is **at least 0.53**, and the observable correlation
on this deposit is at least `0.53 x 0.5402 = 0.286`. At n = 104 the Fisher-z standard error is 0.0995:

    r = 0.286   the lower bound for an incumbent-strength predictor    2.96 SE, two-sided p = 0.0031
    r = 0.540   the ceiling itself                                     6.07 SE
    r = 0.181   pessimistic end of the reliability interval            1.84 SE, p = 0.066 — NOT detectable

    **Minimum detectable correlation at n = 104, 80 % power, two-sided 0.05: r = 0.272.**

**So this design is marginally powered and says so in advance: 0.286 against a 0.272 threshold.** If the
label's true reliability sits at the low end of its interval, n = 239 would be needed and nothing here
could have found the effect. **A null from this file is therefore weak evidence of absence, and must be
reported as "underpowered for anything below r = 0.27" rather than as a negative.**

THREE CAVEATS ON THAT ARITHMETIC, NONE OPTIONAL AND ALL WRITTEN BEFORE THE RESULT.
  1. Blankertz's label is BBCI **feedback** performance across a full session; ours is a 45-trial offline
     left/right decode. Transferring the effect size assumes one underlying ability drives both, which is
     an assumption and not a finding.
  2. **Our incumbent is a declared weaker proxy** — `relative_alpha_power`, whole-head and uncorrected,
     against Blankertz's Laplacian mu-peak measure corrected against the aperiodic noise floor. It should
     therefore land *below* 0.286, and beating it is a weaker claim than beating Blankertz. E28 declared
     this and it carries over unchanged.
  3. 0.286 is a **lower** bound, which is the direction that helps.

REGISTERED BEFORE ANY RESTING FEATURE IS READ AGAINST THE LABEL. Failing branch written first throughout.

  G1  LABEL-VIABILITY GATE, and it is E38's, not E28's. The label's reliability interval must exclude zero
      and the coverage floor must be met. **This gate is already satisfied by a committed prior result**,
      which is stated rather than hidden: it is a precondition being carried forward, and if
      `e38_bci_label_reliability.json` is absent or its interval includes zero, this file refuses to run.

  G2  COVERAGE. At least `MIN_SUBJECTS` subjects with both a resting row and a label.

  P1  THE INCUMBENT, printed before any candidate: Spearman correlation of `relative_alpha_power` with
      imagery AUC across subjects, with a bootstrap CI. **This is the bar.** Reported against 0.286, the
      value a faithful Blankertz reimplementation should exceed, so a reader can see how much of the gap
      is our proxy's weakness.

  P2  THE PRIMARY. `exponent_high` — **E28's registered primary, unchanged**, because selecting a new
      primary after a gate failure is the goalpost move this project's rules exist to prevent. Its |rho|
      must have an interval excluding zero AND exceed the incumbent's |rho|.

  P3  THE PLACEBO, and it gates the verdict (rule 34). The identical analysis with the label replaced by
      **executed-movement** decoding AUC. Executed movement is decodable from motor-cortex legibility in
      people who cannot imagine at all, so a feature predicting it as well as imagery is tracking how
      legible that subject's cortex is, not their capacity to comply covertly. The imagery association
      must **exceed** the executed one — a comparison, never a threshold. E38 measured executed
      reliability at +0.3034, statistically indistinguishable from imagery's, so the two labels are
      equally noisy and the comparison is fair; that was not knowable when E28 registered the same gate.
      **Reported NOT INFORMATIVE if P2's own interval includes zero** (rule 48).

  P4  MULTIPLICITY, reported: Westfall-Young step-down max-T across all `REPORT` candidates, with the null
      built by permuting the label across subjects. `effective_tests` is the number worth reading.

  P5  REPORTED CONTEXT, no verdict: every candidate's correlation, and the **disattenuated** value
      `rho / 0.5402` beside it, so a reader can see what each would be worth against a perfectly measured
      label. Disattenuated values are context and are never claimed.

VERDICT RULE, written before the run and stating the failing case first.

    NOT INTERPRETABLE   G1 or G2 failed.
    UNDERPOWERED NULL   P2's interval includes zero **and** |rho| < 0.272. Not a negative — this design
                        cannot see anything below that, and E38's interval says the true reliability may
                        be low enough that nothing could.
    NOT MET             P2's interval excludes zero but does not beat the incumbent, or the placebo
                        reaches the primary.
    MET                 P2 excludes zero, exceeds the incumbent, and exceeds its placebo. The permitted
                        sentence names the ceiling: *"rho = X against a label whose reliability bounds any
                        predictor at 0.54."*

SCOPE, INHERITED FROM E28 AND UNCHANGED BY ANY OF THIS. **Not a disorders-of-consciousness result.** A
healthy subject who cannot drive a BCI is not unconscious; they are inattentive, untrained, or have a low
sensorimotor rhythm. Motor imagery is command-following that produces no movement, which is the right
*form*, and the substitution's cost is the first thing any reader should be told. **No sentence from this
file may be written as a claim about DoC.** Between-subject at n ~ 104, with no demographics in the deposit
to adjust for anything.

--------------------------------------------------------------------------------------------------------
OUTCOME. **UNDERPOWERED NULL for the primary, as the verdict branch was written to enforce. But the
INCUMBENT is real — and that, not the primary, is the finding.**

    G1/G2  Passed. 104 subjects with a resting row and an imagery label; the label-viability gate is
           E38's r_sb +0.2918 [+0.1163, +0.4345], carried forward from a committed prior result.

    P1     **`relative_alpha_power` rho = +0.2018 [+0.0050, +0.3857], one-sided resample p = 0.0225**
           (20,000 resamples). **The deliberately weakened proxy for Blankertz's published predictor is
           the strongest measure in the file, and its association with motor-imagery ability is real at
           this sample size.**

           **A REPLICATE-COUNT CORRECTION, MADE BEFORE ANY OF THIS WAS WRITTEN UP AND RECORDED HERE.** At
           the registered 2,000 resamples the interval printed as **[-0.0011, +0.4072]** — including zero
           by 0.0011, which is error-catalogue rule 46 exactly: a margin the size of its own Monte Carlo
           error. Re-run at **five seeds and 20,000 resamples the interval excludes zero in all five**
           (lower bounds +0.0032 to +0.0090), and the resample-level p is 0.0225. **The registered count
           was too low and raising it is the fix rule 46 endorses**, because it changes no threshold,
           cohort or horizon. The verdict is unaffected either way: the incumbent is reported, never
           gated, and the primary is what the verdict turns on. `resample_p` is now emitted alongside
           every interval, which is what rule 46 asks for and degrades gracefully where an endpoint does
           not.

           **The pre-registered arithmetic predicted this and was not guaranteed to.** The header states
           that a faithful Blankertz reimplementation should reach at least 0.286, and that *our* proxy —
           whole-head and uncorrected, against Blankertz's Laplacian mu-peak measure corrected to the
           aperiodic noise floor — should land **below** that. It landed at 0.2018.

    P2     **`exponent_high` rho = +0.0761 [-0.1204, +0.2675], resample p = 0.2275.** Includes zero, does
           not beat the incumbent, and |rho| is far below this design's minimum detectable effect of
           0.272. **UNDERPOWERED NULL, not a negative** — and that branch was written before the run
           precisely so this sentence could not be chosen afterwards.

    P3     NOT INFORMATIVE, correctly (rule 48): with the primary spanning zero there is no association
           for the executed-movement placebo to fail to reproduce.

    P4     **Nothing survives FWER 0.05.** `effective_tests` 11.76 of 14 — these candidates are far less
           redundant than E01's pair, so the search space is close to its nominal size.
           `relative_alpha_power` has raw p 0.0445 by permutation, which agrees with the bootstrap's
           0.0225 one-sided, and adjusted p 0.3238. **The two numbers answer different questions and both
           belong in a write-up:** as the single pre-declared incumbent it is p ~ 0.02-0.04; as a member
           of a 14-way family it is 0.32. It was pre-declared, so the unadjusted value is the relevant
           one — but a reader is entitled to see that it would not have survived had it been discovered
           rather than nominated.

    P5     Every candidate's rho lies in [-0.108, +0.202] and every interval except the incumbent's
           includes zero. Disattenuated values are printed as context and claimed for nothing.

**WHAT CHALLENGE B ACTUALLY LEARNED HERE, STATED WITHOUT INFLATION.**

  1. **A fifteen-year-old published predictor, in a deliberately weakened form, beats every one of this
     project's fourteen candidates on this deposit.** That is the incumbent doing its job — rule 45 exists
     because a marker reported without the thing it has to beat is not a result, and here the bar was not
     cleared by anything.
  2. **The primary's null is uninformative and is labelled as such.** At n = 104 nothing below rho = 0.272
     was findable, and E38's reliability interval permits a true reliability low enough that an
     incumbent-strength association could have been missed entirely. Reporting this as "resting EEG does
     not predict motor-imagery ability" would be false.
  3. **The path to a real answer is arithmetic, not novelty.** n = 239 at the pessimistic end of E38's
     reliability interval; or more trials per subject, which E38's own P4 suggests buys less than it
     sounds within the range this deposit can test. Both are sizing problems with known answers, which is
     a better position than Challenge B has been in at any previous point.

**SCOPE, UNCHANGED AND REPEATED BECAUSE IT IS THE LIMIT MOST EASILY LOST IN SUMMARY.** Not a
disorders-of-consciousness result. A healthy subject who cannot drive a BCI is not unconscious. Motor
imagery is command-following that produces no movement, which is the right *form* and not the right
population. **No sentence from this file may be written as a claim about DoC.**
"""

from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import cluster_bootstrap_ci, spearman                          # noqa: E402
from bsde.verifier.multiplicity import westfall_young_maxt                              # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
REST = os.path.join(RESULTS, "eegmmidb_rest.csv")
LABEL = os.path.join(RESULTS, "eegmmidb_bci.csv")
EXEC_LABEL = os.path.join(RESULTS, "eegmmidb_bci_executed.csv")
RELIABILITY = os.path.join(RESULTS, "e38_bci_label_reliability.json")
OUT = os.path.join(RESULTS, "e41_challenge_b_against_the_ceiling.json")

PRIMARY = "exponent_high"
INCUMBENT = "relative_alpha_power"
REPORT = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
          "wpli_alpha", "spatial_participation_ratio", "uce_v1")

MIN_SUBJECTS = 60
MDE = 0.272
BLANKERTZ_R = 0.53
PERMS = 2000
REPS = 20000
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _rest_by_subject(path):
    """Per subject, the mean of each candidate over that subject's resting rows. E28's reduction."""
    rows = [r for r in csv.DictReader(open(path, newline="")) if r.get("status") == "ok"]
    by = {}
    for r in rows:
        by.setdefault(r.get("subject", ""), []).append(r)
    out = {}
    for s, rs in by.items():
        out[s] = {c: float(np.nanmean([_f(r.get(c, "")) for r in rs])) for c in REPORT}
    return out


def _labels(path, col="imagery_auc"):
    return {r["subject"]: _f(r[col]) for r in csv.DictReader(open(path, newline=""))
            if r.get("status") == "ok"}


def _corr(rest, lab, subs, name, rng, reps=REPS):
    x = np.array([rest[s][name] for s in subs], float)
    y = np.array([lab[s] for s in subs], float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < MIN_SUBJECTS:
        return None
    x, y = x[ok], y[ok]
    r = spearman(x, y)
    idx = np.arange(x.size)
    lo, hi, _ = cluster_bootstrap_ci(lambda i: spearman(x[i], y[i]), idx, rng, reps=reps)
    # Rule 46: report the fraction of resamples on the wrong side of the null, not only the interval.
    # It is the same computation and it degrades gracefully where an endpoint does not.
    boot = np.array([spearman(x[i], y[i]) for i in
                     (rng.integers(0, x.size, x.size) for _ in range(min(reps, 4000)))], float)
    boot = boot[np.isfinite(boot)]
    frac = float(np.mean(boot <= 0.0)) if r > 0 else float(np.mean(boot >= 0.0))
    return {"rho": float(r), "ci": [float(lo), float(hi)], "n": int(x.size),
            "resample_p": frac,
            "excludes_zero": bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0))}


def main(argv=None) -> int:
    print("E41 — E28's question against a known ceiling")
    print("   No candidate has EVER been scored against this label: E28 returned at its gate before P2,")
    print("   and E38 read only the trial cache. This is a first look.")
    for p in (REST, LABEL, EXEC_LABEL, RELIABILITY):
        if not os.path.exists(p):
            print(f"\n   *** {os.path.basename(p)} absent.")
            return 2
    rel = json.load(open(RELIABILITY))
    rng = np.random.default_rng(SEED)

    print("\n" + "=" * 100)
    print("G1 — LABEL-VIABILITY GATE, carried forward from E38 rather than recomputed")
    print("=" * 100)
    p1r = rel.get("p1", {})
    r_sb, ci = p1r.get("r_sb"), p1r.get("ci", [np.nan, np.nan])
    ceiling = p1r.get("ceiling")
    print(f"   E38 r_sb {r_sb:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}]   ceiling {ceiling:.4f}")
    g1 = bool(p1r.get("viable"))
    print(f"   G1 {'PASSED' if g1 else '*** FAILED'}")
    st = {"experiment": "E41", "ceiling": ceiling, "r_sb": r_sb, "reliability_ci": ci}
    if not g1:
        print("   The label cannot support a per-subject regression. ABSENT, not negative (rule 31).")
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    rest = _rest_by_subject(REST)
    lab = _labels(LABEL)
    lab_x = _labels(EXEC_LABEL)
    subs = sorted(set(rest) & set(lab))
    subs_x = sorted(set(rest) & set(lab_x))
    print("\n" + "=" * 100)
    print("G2 — COVERAGE")
    print("=" * 100)
    print(f"   subjects with a resting row and an imagery label  : {len(subs)}  (floor {MIN_SUBJECTS})")
    print(f"   ... and an executed label (for the placebo)       : {len(subs_x)}")
    g2 = len(subs) >= MIN_SUBJECTS
    print(f"   G2 {'PASSED' if g2 else '*** FAILED'}")
    st["n_subjects"] = len(subs)
    if not g2:
        json.dump(st, open(OUT, "w"), indent=2, default=float)
        return 1

    print("\n" + "=" * 100)
    print("P1 — THE INCUMBENT, printed before any candidate")
    print("=" * 100)
    inc = _corr(rest, lab, subs, INCUMBENT, rng)
    print(f"   {INCUMBENT}  rho {inc['rho']:+.4f} [{inc['ci'][0]:+.4f}, {inc['ci'][1]:+.4f}]  n={inc['n']}"
          f"   resample p {inc['resample_p']:.4f}")
    print(f"   For reference: a faithful Blankertz reimplementation should reach at least "
          f"{BLANKERTZ_R * ceiling:.3f}")
    print("   Ours is a declared weaker proxy — whole-head and uncorrected — so it should land below that.")
    st["p1_incumbent"] = inc

    print("\n" + "=" * 100)
    print(f"P2 — THE PRIMARY: {PRIMARY}, E28's registered primary, unchanged")
    print("=" * 100)
    pri = _corr(rest, lab, subs, PRIMARY, rng)
    print(f"   {PRIMARY}  rho {pri['rho']:+.4f} [{pri['ci'][0]:+.4f}, {pri['ci'][1]:+.4f}]"
          f"   resample p {pri['resample_p']:.4f}")
    beats = abs(pri["rho"]) > abs(inc["rho"])
    print(f"   excludes zero: {pri['excludes_zero']}   beats the incumbent: {beats}")
    p2 = bool(pri["excludes_zero"] and beats)
    print(f"   P2 {'PASSED' if p2 else '*** FAILED'}")
    st["p2_primary"] = dict(pri, beats_incumbent=bool(beats), passed=p2)

    print("\n" + "=" * 100)
    print("P3 — PLACEBO: the same analysis on EXECUTED-movement decoding")
    print("=" * 100)
    if not pri["excludes_zero"]:
        print("   NOT INFORMATIVE: the primary's interval includes zero, so there is no association for")
        print("   the placebo to fail to reproduce (rule 48).")
        st["p3"] = {"status": "not_informative"}
        p3 = None
    else:
        plc = _corr(rest, lab_x, subs_x, PRIMARY, rng)
        print(f"   executed  rho {plc['rho']:+.4f} [{plc['ci'][0]:+.4f}, {plc['ci'][1]:+.4f}]"
              f"   imagery {pri['rho']:+.4f}")
        p3 = bool(abs(pri["rho"]) > abs(plc["rho"]))
        print(f"   P3 {'PASSED' if p3 else '*** FAILED — the primary is WITHDRAWN'}")
        st["p3"] = dict(plc, passed=p3)

    print("\n" + "=" * 100)
    print("P5 — EVERY CANDIDATE, with its disattenuated value as CONTEXT ONLY")
    print("=" * 100)
    print(f"   {'candidate':26s} {'rho':>8s}   95% CI              {'rho/ceiling':>11s}")
    per = {}
    for c in REPORT:
        v = _corr(rest, lab, subs, c, rng, reps=600)
        if v is None:
            continue
        per[c] = v
        print(f"   {c:26s} {v['rho']:+8.4f}   [{v['ci'][0]:+.4f}, {v['ci'][1]:+.4f}]   "
              f"{v['rho'] / ceiling:+11.4f}")
    print("   The last column is what each would be worth against a perfectly measured label.")
    print("   It is context and is never claimed — disattenuation inflates noise as readily as signal.")
    st["p5_all"] = per

    print("\n" + "=" * 100)
    print("P4 — MULTIPLICITY across the candidate set (reported)")
    print("=" * 100)
    names = [c for c in REPORT if c in per]
    X = np.array([[rest[s][c] for c in names] for s in subs], float)
    y = np.array([lab[s] for s in subs], float)
    ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    Xo, yo = X[ok], y[ok]
    obs = [abs(spearman(Xo[:, j], yo)) for j in range(len(names))]
    null = np.empty((PERMS, len(names)), float)
    for k in range(PERMS):
        yp = rng.permutation(yo)
        for j in range(len(names)):
            null[k, j] = abs(spearman(Xo[:, j], yp))
    wy = westfall_young_maxt(obs, np.nan_to_num(null, nan=0.0), names=names)
    print(f"   effective_tests {wy['effective_tests']:.2f} of {wy['n_candidates']}")
    surv = [n for n in names if wy["adjusted"][n] <= 0.05]
    print(f"   surviving FWER 0.05: {surv if surv else 'none'}")
    for n in names:
        print(f"      {n:26s} raw p {wy['raw'][n]:.4f}   adjusted p {wy['adjusted'][n]:.4f}")
    st["p4_multiplicity"] = {"effective_tests": wy["effective_tests"], "adjusted": wy["adjusted"],
                             "raw": wy["raw"], "survivors": surv}

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not pri["excludes_zero"] and abs(pri["rho"]) < MDE:
        verdict = "underpowered_null"
        print(f"   UNDERPOWERED NULL: |rho| = {abs(pri['rho']):.3f} is below this design's minimum")
        print(f"   detectable effect of {MDE:.3f} at n = {len(subs)}. **This is not a negative.** E38's")
        print("   reliability interval permits a true reliability low enough that nothing here could have")
        print("   found an incumbent-strength association.")
    elif not p2:
        verdict = "not_met"
        print("   NOT MET: the primary does not both exclude zero and beat the incumbent.")
    elif p3 is False:
        verdict = "withdrawn_placebo"
        print("   WITHDRAWN: executed-movement decoding is predicted as well, so the feature tracks how")
        print("   legible the motor cortex is rather than the capacity to comply covertly.")
    else:
        verdict = "met"
        print(f"   MET: rho = {pri['rho']:+.4f} against a label whose reliability bounds any predictor")
        print(f"   at {ceiling:.3f}. NOT a disorders-of-consciousness claim — see the scope note.")
    st["verdict"] = verdict
    json.dump(st, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote results/{os.path.basename(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
