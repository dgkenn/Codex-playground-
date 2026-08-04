#!/usr/bin/env python3
"""E17 — E16's question, with a gate that does not assume the subjects are adults.

THIS IS A GATE RE-SPECIFICATION AFTER A FAILURE, AND IS LABELLED AS ONE. It is not a clean pre-registration
of the gate, and no amount of wording makes it one. What IS still clean is everything the gate protects:
E16 exited before computing any age association, so **`exponent_high`'s relationship with age has never been
looked at**, and P2/P3/P4 below are carried over verbatim and remain unexamined.

E16 IS LEFT IN PLACE, UNEDITED, AS THE RECORD OF THE FAILURE. Editing it until it passed would have erased
the most useful thing that happened.

*** CORRECTION, ADDED 2026-07-30 AFTER THE GATE WAS REGISTERED AND BEFORE IT WAS RUN. ***
The developmental account below is NOT established and was asserted too confidently. The band-free gate
registered here came out at **46.3 %** on a partial table -- chance, and WORSE than the band-dependent gate
it replaced (63.0 % on the same subjects). Two gates near chance pointed at the windows rather than at any
feature, and the adapter was wrong: HBN's resting run ends on an eyes-open instruction, `blocks_from_events`
returned that final block unbounded, and "the longest block" therefore selected ~35 s of POST-PROTOCOL
recording as every subject's eyes-open window. Fixed (trailing block dropped; 2 s lead-in; 16 s window),
regression-tested, and the table re-streamed.

**What this means for the reasoning below: the age gradient in alpha blocking (42 % -> 74 %) was computed
from invalid eyes-open windows and cannot be interpreted until re-run.** My claim that "a broken pipeline
does not produce a monotone age gradient" was wrong -- a broken pipeline CAN, if the breakage interacts with
age, and older children plausibly move less in the minutes after a protocol ends. The developmental
explanation may still be right; it is simply not evidenced yet. The gate itself is unchanged, and the
one-attempt commitment stands.

WHAT FAILED, AND WHY IT WAS THE GATE RATHER THAN THE PIPELINE (SUPERSEDED -- see the correction above).
E16 gated on alpha blocking: `relative_alpha_power` higher with eyes closed than eyes open, in at least 80 %
of subjects. Measured: **57.1 %**. But the failure is monotone in age, which a broken pipeline does not
produce:

    age  5-8   42.3 %       age 10-13   73.7 %
    age  8-10  45.8 %       age 13-22   69.6 %

The posterior dominant rhythm is slower in young children, and this cohort's median age is **9.8**. A fixed
adult 8-12 Hz band simply does not contain much of this cohort's dominant rhythm. **The premise was wrong,
not the logic** — and that is a finding about the registry rather than about HBN, because
`relative_alpha_power` carries the same fixed band everywhere it is used in this project.

THE NEW GATE IS BAND-FREE, WHICH IS WHY IT DOES NOT INHERIT THE DEFECT.
`spectral_entropy` measures how peaked the normalised spectrum is, with no band edges at all. Closing the
eyes concentrates power into a narrow oscillation wherever that oscillation happens to sit, so the spectrum
becomes more peaked and its entropy FALLS — at 6 Hz in a seven-year-old exactly as at 10 Hz in an adult.

`spectral_edge_95` is also band-free and is DELIBERATELY NOT CHOSEN, for a reason stated before looking at
either: the 95th-percentile edge is dominated by the high-frequency tail, and eyes-open recordings carry more
blink and movement artefact than eyes-closed ones, so that measure would confound the contrast with artefact.
Choosing between two band-free options after seeing which one passes is exactly the move this file exists to
avoid, so the choice is made on that argument and recorded here.

**ONE ATTEMPT. IF THIS GATE ALSO FAILS, THE ANSWER IS THAT THIS DEPOSIT CANNOT VALIDATE THE FEATURE PATH AND
NOTHING ABOUT `exponent_high` IS REPORTED FROM IT — EVER, not "until a third gate is tried".** A sequence of
gates tried until one passes is a search over gates, and it would make the eventual pass meaningless.

REGISTERED PREDICTIONS (P2-P4 carried over from E16 verbatim and still unexamined):
    P1  GATE, BAND-FREE. `spectral_entropy` must be LOWER with eyes closed than eyes open, within subject, in
        at least 80 % of subjects. `exponent_high` must also be finite in at least 80 % of rows.
    P2  PRIMARY. `exponent_high`'s signed AUC for youngest-vs-oldest age tertile (eyes-closed rows) has
        |AUC - 0.5| >= 0.20. I predict this IS met. Not met -> the age worry is unfounded, which is the
        outcome I would prefer and am predicting against.
    P3  COMPARISON. The age |AUC - 0.5| is at least ds005620's state |AUC - 0.5| of 0.262 minus a 0.10
        tolerance, i.e. >= 0.162 — a person-level variable moving the measure about as much as the drug does.
    P4  DISAMBIGUATOR. Does `exponent_high` respond to eyes-open vs eyes-closed WITHIN subject?
          P2 met AND P4 met  -> a state measure with a large person-level offset: a CALIBRATION problem.
                                Between-subject deployment needs age normalisation; within-subject
                                monitoring, which is what the anaesthesia wedge is, is untouched.
          P2 met AND P4 NOT  -> it tracks who you are rather than your state. Far more damaging.
        Eyes-open/closed is a much weaker manipulation than sedation, so a P4 null may be power rather than
        absence — registered here, not offered afterwards as an excuse.

    FALSIFICATION OF THE AGE WORRY: P2 not met.

SCOPE is E16's, unchanged: uncalibrated units so **scale-invariant features only** (`exponent_high` is one);
per-channel DC removed; the flat EGI reference dropped; EGI montage so `uce_v1` is NaN by design; children
5-21 against adults in the sedation deposits; cross-sectional age. The comparison is of the MAGNITUDE of a
person-level association against a state association, and is not a like-for-like contrast.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                        # noqa: E402
from bsde.candidates.seed import seed_registry                                        # noqa: E402
from bsde.verifier.stats import directional_auc, cluster_bootstrap_ci, spearman        # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "hbn_r1_resting.csv")

PRIMARY = "exponent_high"
GATE_FEATURE = "spectral_entropy"
GATE_DIRECTION = "lower_when_closed"
GATE_MIN_FRACTION = 0.80
GATE_MIN_FINITE = 0.80
MIN_ROWS = 100
AGE_EFFECT_MIN = 0.20
DS005620_STATE_EFFECT = 0.262
COMPARISON_TOLERANCE = 0.10
REPORT = ("exponent_high", "exponent_gamma", "exponent_low", "whole_head_exponent",
          "relative_delta_power", "relative_alpha_power", "lempel_ziv", "spectral_entropy",
          "spectral_edge_95", "wpli_alpha", "spatial_participation_ratio",
          "multiscale_entropy_slope", "pac_slow_alpha", "emg_beta_gamma_fraction", "emg_kurtosis")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def paired(subj, cond, values):
    """(closed, open) pairs per subject, both finite. The unit is the subject, never the row."""
    out, subs = [], []
    for s in np.unique(subj):
        c = values[(subj == s) & (cond == "closed")]
        o = values[(subj == s) & (cond == "open")]
        if c.size and o.size and np.isfinite(c[0]) and np.isfinite(o[0]):
            out.append((float(c[0]), float(o[0])))
            subs.append(s)
    return out, np.asarray(subs)


def main() -> int:
    seed_registry()
    n_space = REGISTRY.search_space_size()
    print("E17 — E16's question with a band-free gate (gate RE-SPECIFIED after failure; P2-P4 unexamined)")
    print(f"   search space {n_space} registered candidates; analytic dof >= 72")
    if not os.path.exists(TABLE):
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    with open(TABLE, newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status") == "ok"]
    if len(rows) < MIN_ROWS:
        print(f"   *** only {len(rows)} rows; need {MIN_ROWS}. The stream is still running. This is a")
        print("   statement about the TABLE, not about the candidate.")
        return 1

    age = np.array([_f(r.get("meta_age")) for r in rows])
    cond = np.array([r.get("meta_condition", "") for r in rows])
    subj = np.array([r.get("subject", "") for r in rows])
    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)      # noqa: E731
    rng = np.random.default_rng(20260730)
    fin = np.isfinite(age)
    print(f"   rows {len(rows)}   subjects {len(set(subj))}   "
          f"closed {int((cond == 'closed').sum())} / open {int((cond == 'open').sum())}")
    print(f"   age n={int(fin.sum())} median {np.median(age[fin]):.1f} "
          f"range {age[fin].min():.1f}-{age[fin].max():.1f}")

    # ------------------------------- P1: band-free gate --------------------------------------------
    print("\n" + "=" * 100)
    print(f"P1 — BAND-FREE GATE: {GATE_FEATURE} must be LOWER eyes-closed (a peakier spectrum), "
          f"in >= {GATE_MIN_FRACTION:.0%} of subjects")
    print("=" * 100)
    prs, psubs = paired(subj, cond, col(GATE_FEATURE))
    frac = float(np.mean([c < o for c, o in prs])) if prs else float("nan")
    p_gate = bool(prs and len(prs) >= 20 and frac >= GATE_MIN_FRACTION)
    pv = col(PRIMARY)
    frac_finite = float(np.isfinite(pv).mean())
    p_finite = frac_finite >= GATE_MIN_FINITE
    p1 = bool(p_gate and p_finite)
    print(f"   entropy lower eyes-closed in {int(np.sum([c < o for c, o in prs]))}/{len(prs)} subjects "
          f"({frac:.1%})   {'PASS' if p_gate else '*** FAIL'}")
    print(f"   {PRIMARY} finite in {frac_finite:.1%} of rows   {'PASS' if p_finite else '*** FAIL'}")
    if not p1:
        print("\n   *** GATE FAILED, AND THAT IS THE END OF IT. Registered in advance: one attempt. Two")
        print("   gates have now failed on this deposit — one band-dependent, one band-free — so the")
        print("   feature path is not validated here and NOTHING about exponent_high is reported from")
        print("   HBN. Trying a third gate would be a search over gates, and would make any eventual")
        print("   pass meaningless. The age question needs a different cohort.")
        json.dump({"experiment": "E17", "gate_passed": False, "gate_feature": GATE_FEATURE,
                   "gate_fraction": frac, "n_paired": len(prs), "primary_finite_frac": frac_finite,
                   "primary_never_computed": True, "no_further_gates": True},
                  open(os.path.join(RESULTS, "e17_hbn_age.json"), "w"), indent=2)
        return 1
    print("\n   GATE PASSED — the feature path responds to a within-subject state change on this deposit")

    # ------------------------------- the age contrast ----------------------------------------------
    ec = (cond == "closed") & fin
    lo_cut, hi_cut = np.percentile(age[ec], [33.3333, 66.6667])
    sel = ec & ((age <= lo_cut) | (age >= hi_cut))
    y_age = (age[sel] >= hi_cut).astype(float)
    s_age = subj[sel]
    print("\n" + "=" * 100)
    print(f"AGE CONTRAST — youngest vs oldest tertile, eyes-closed rows (cuts {lo_cut:.1f} / {hi_cut:.1f} y)")
    print("=" * 100)
    print(f"   young {int((y_age == 0).sum())} / old {int((y_age == 1).sum())}")
    print(f"   {'candidate':28s} {'AUC old-vs-young':>24s} {'|AUC-.5|':>9s}   rho(age)")
    out = {}
    for name in REPORT:
        v = col(name)[sel]
        if np.isfinite(v).sum() < 20:
            continue
        # No candidate declares a direction for AGE -- this is an adversarial probe, not a prediction --
        # so the raw orientation is reported and the MAGNITUDE is what the predictions turn on. Scoring a
        # probe against an invented direction is the error E10 caught.
        au = directional_auc(y_age, v, "higher")
        blo, bhi = cluster_bootstrap_ci(lambda i: directional_auc(y_age[i], v[i], "higher"),
                                        s_age, rng, reps=2000)[:2]
        out[name] = {"auc": float(au), "ci": [float(blo), float(bhi)], "abs": float(abs(au - 0.5)),
                     "spearman_with_age": float(spearman(age[sel], v))}
        print(f"   {name:28s} {au:8.3f} [{blo:.3f}, {bhi:.3f}] {abs(au - 0.5):9.3f}   "
              f"{out[name]['spearman_with_age']:+.3f}" + ("  <-- primary" if name == PRIMARY else ""))

    pri = out.get(PRIMARY)
    p2 = bool(pri and pri["abs"] >= AGE_EFFECT_MIN)
    p3 = bool(pri and pri["abs"] >= DS005620_STATE_EFFECT - COMPARISON_TOLERANCE)

    # ------------------------------- P4 ------------------------------------------------------------
    print("\n" + "=" * 100)
    print(f"P4 — does {PRIMARY} respond to eyes-open vs eyes-closed WITHIN subject?")
    print("=" * 100)
    prs2, psubs2 = paired(subj, cond, pv)
    p4, ws = False, {}
    if len(prs2) >= 20:
        arr = np.array([c - o for c, o in prs2])
        fr = float(np.mean(arr > 0))
        flo, fhi = cluster_bootstrap_ci(lambda i: float(np.mean(arr[i] > 0)), psubs2, rng, reps=2000)[:2]
        p4 = bool(flo > 0.5 or fhi < 0.5)
        ws = {"fraction_higher_closed": fr, "ci": [float(flo), float(fhi)], "n": len(prs2)}
        print(f"   higher eyes-closed in {fr:.1%} [{flo:.1%}, {fhi:.1%}] of {len(prs2)} subjects   "
              f"{'RESPONDS' if p4 else 'undetermined — CI spans 50%'}")
    else:
        print(f"   only {len(prs2)} paired subjects; not estimable")

    # ------------------------------- verdict --------------------------------------------------------
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 band-free gate + computability                       : MET ({frac:.1%})")
    print(f"   P2 age effect |AUC-0.5| >= {AGE_EFFECT_MIN}                       : "
          f"{'MET' if p2 else 'NOT MET'}" + (f" ({pri['abs']:.3f})" if pri else ""))
    print(f"   P3 age effect >= {DS005620_STATE_EFFECT} - {COMPARISON_TOLERANCE} (as large as the drug) : "
          f"{'MET' if p3 else 'NOT MET'}")
    print(f"   P4 responds within subject to eyes-open/closed          : {'MET' if p4 else 'NOT MET'}")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p2:
        verdict = "AGE_WORRY_UNFOUNDED"
        print(f"   {PRIMARY}'s association with age is weak (|AUC-0.5| {pri['abs']:.3f} "
              f"[{pri['ci'][0]:.3f}, {pri['ci'][1]:.3f}]). It is NOT substantially developmental in this")
        print("   cohort — the outcome I predicted against, and the better one for the lead.")
    elif p4:
        verdict = "STATE_MEASURE_WITH_A_PERSON_LEVEL_OFFSET"
        print(f"   {PRIMARY} carries a substantial age signal (|AUC-0.5| {pri['abs']:.3f}) AND responds to")
        print("   a within-subject state change. That is a CALIBRATION problem, not an invalidity: the")
        print("   absolute value cannot be read as a state without normalising for the person, but")
        print("   within-subject monitoring — the same patient before and after — is untouched. Survivable")
        print("   for the anaesthesia wedge, which is inherently within-subject. Not survivable for any")
        print("   between-subject deployment without an age-normalised reference.")
    else:
        verdict = "TRACKS_THE_PERSON_NOT_THE_STATE"
        print(f"   {PRIMARY} carries a substantial age signal (|AUC-0.5| {pri['abs']:.3f}) and does NOT")
        print("   demonstrably respond to a within-subject state change here. That is the damaging")
        print("   combination. Eyes-open/closed is far weaker than sedation, so this null may be power")
        print("   rather than absence — registered in advance, not offered now as an excuse.")
    print(f"\n   verdict: {verdict}")
    print("\n   THE GATE WAS RE-SPECIFIED AFTER E16'S FAILED, and that is on the record: this is a clean")
    print("   test of P2-P4, which were never examined, and NOT a clean pre-registration of P1.")

    dst = os.path.join(RESULTS, "e17_hbn_age.json")
    json.dump({"experiment": "E17", "gate_passed": True, "gate_feature": GATE_FEATURE,
               "gate_fraction": frac, "gate_respecified_after_e16": True,
               "search_space_size": n_space, "n_rows": len(rows), "n_subjects": len(set(subj)),
               "age_tertile_cuts": [float(lo_cut), float(hi_cut)], "age_contrast": out,
               "within_subject_eyes": ws, "ds005620_state_effect": DS005620_STATE_EFFECT,
               "predictions": {"P1": True, "P2": p2, "P3": p3, "P4": p4},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
