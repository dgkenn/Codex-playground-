#!/usr/bin/env python3
"""E16 — is the lead a measure of WHO THE PERSON IS rather than what state they are in?

REGISTERED BEFORE ANY HBN CANDIDATE VALUE EXISTS. The HBN stream was launched minutes before this file was
written and no feature column has been read. What HAS been inspected is raw signal properties, deliberately
and before designing anything: sampling rate, channel count, DC offsets, the flat reference channel, and the
event structure. Those are properties of the FILES, not of any candidate, and checking them first is what
stopped three silent corruptions (see SCOPE).

THE QUESTION, AND WHY NOTHING HERE HAS ASKED IT. Every candidate in this registry is a between-subject-
comparable scalar, and every contrast this project has run is a STATE contrast within a narrow adult
population. **Nothing has ever tested a candidate against a large healthy population.** If a measure's value
is dominated by who the person is — their age, their development — then its absolute value carries person
information rather than state information, which matters for three things at once: any between-subject
deployment, layer 7's population numbers (§9.19 already shows PPV collapsing with prevalence), and the plain
claim that the thing measures brain STATE.

HBN is the largest healthy cohort with a documented age column this project can reach: ~136 subjects in
release R1 alone, aged roughly 5-21, free, anonymous, no credentials. It serves NONE of the three discovery
challenges — no anaesthetic, no DoC, no sleep staging, no command-following — and is ingested for this one
adversarial purpose.

THE COMPARISON. `exponent_high`'s AUC for young-vs-old is directly comparable in units to its AUC for
awake-vs-sedated, because AUC is unit-free:

    Chennu, awake vs moderately sedated (adults, propofol)   0.863
    ds005620, awake vs sedated (adults, propofol, matched)   0.762
    HBN, youngest vs oldest age tertile (children, no drug)  ???

If the age figure is comparable to the state figures, the measure carries as much developmental information
as state information, and its absolute value cannot be read as a state without age normalisation.

**THIS IS NOT A LIKE-FOR-LIKE CONTRAST AND IS NOT PRESENTED AS ONE.** Different populations (children vs
adults), different manipulations (development vs drug), cross-sectional rather than longitudinal. The claim
is narrow and is the only one the design supports: *the magnitude of association with a person-level variable,
against the magnitude of association with state.*

REGISTERED PREDICTIONS:
    P1  MACHINERY GATE, AND IT IS UNCONTESTABLE ON PURPOSE. `relative_alpha_power` must be HIGHER with eyes
        closed than eyes open, within subject, in at least 80 % of subjects — alpha blocking, the most robust
        phenomenon in electroencephalography. It needs no developmental premise, and it validates in one
        check that the conditions are assigned to the right windows, that the montage and DC removal are
        sane, and that the feature path works on this deposit. `exponent_high` must also be finite in at
        least 80 % of rows. If either fails, nothing else is reported (rule 31).
    P2  PRIMARY. `exponent_high`'s signed AUC for youngest-vs-oldest age tertile (eyes-closed rows) has
        |AUC − 0.5| >= 0.20, i.e. AUC outside [0.30, 0.70]. I predict this IS met: the aperiodic exponent is
        widely reported to change across development. Not met -> the age worry is unfounded and the lead is
        cleaner than I feared, which is the outcome I would prefer and am predicting against.
    P3  COMPARISON. The age |AUC − 0.5| is at least as large as ds005620's state |AUC − 0.5| of 0.262, minus
        a 0.10 tolerance — i.e. >= 0.162. Met -> a person-level variable moves this measure about as much as
        the drug does.
    P4  DISAMBIGUATOR, AND IT DECIDES WHICH VERDICT APPLIES. Does `exponent_high` respond to eyes-open vs
        eyes-closed WITHIN subject — the fraction moving in a consistent direction, with a subject-clustered
        CI excluding 50 %? A large age effect means very different things depending on this:
          P2 met AND P4 met  -> a state measure carrying a large person-level offset. That is a CALIBRATION
                                problem: between-subject deployment needs age normalisation, within-subject
                                monitoring is untouched.
          P2 met AND P4 NOT  -> it tracks who you are and not your state within a session. Far more damaging.
        **Eyes-open/closed is a much weaker manipulation than sedation**, so a P4 null may be power rather
        than absence, and that caveat is registered here rather than discovered afterwards.

    FALSIFICATION OF THE AGE WORRY: P2 not met.

SCOPE, AND THREE FILE PROPERTIES THAT WOULD HAVE SILENTLY CORRUPTED THIS.
  1. **The units are not microvolts.** After DC removal the AC amplitude is ~724 in file units where
     plausible EEG is 5-50 uV, and the true scale factor is not in the file. No scale factor is invented.
     **Only SCALE-INVARIANT features are valid here** — `exponent_high` is one (a slope; scale moves the
     intercept only), as are band-power ratios, spectral entropy/edge, Lempel-Ziv, wPLI, MSE, PAC,
     participation ratio and kurtosis. `critical_slowing`'s `envelope_variance` is NOT and is excluded.
  2. **DC offsets between -148,179 and +60,114** across channels. `welch_psd` removes each segment's mean so
     the spectral path was already safe, but the time-domain features were not; the adapter removes the
     per-channel mean once, for everything.
  3. **The reference channel is all zeros** (EGI Cz, measured SD exactly 0.0). Dropped, and counted into
     `meta_n_flat_channels_dropped` rather than silently.

Also: the montage is EGI (`E1`...`E128`), with no 10-20 labels, so `uce_v1` returns NaN here by design
(§9.10). 20 s windows, drawn from the longest block of each condition. HBN is enriched for psychopathology;
`p_factor` is carried in the table but is not analysed here, and age is the target.
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
GATE_FEATURE = "relative_alpha_power"
GATE_MIN_FRACTION = 0.80
GATE_MIN_FINITE = 0.80
AGE_EFFECT_MIN = 0.20                 # |AUC - 0.5| for P2
DS005620_STATE_EFFECT = 0.262         # |0.762 - 0.5|, E15's acquisition-matched replication
COMPARISON_TOLERANCE = 0.10
# Scale-invariant only: see SCOPE item 1. envelope_variance is absent from the registry's reported fields,
# but the exclusion is stated so that adding it later is a deliberate act.
EXCLUDED_SCALE_DEPENDENT = ("critical_slowing_envelope_variance",)
REPORT = ("exponent_high", "exponent_gamma", "exponent_low", "whole_head_exponent",
          "relative_delta_power", "relative_alpha_power", "lempel_ziv", "spectral_entropy",
          "spectral_edge_95", "wpli_alpha", "spatial_participation_ratio",
          "multiscale_entropy_slope", "pac_slow_alpha", "emg_beta_gamma_fraction", "emg_kurtosis")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main() -> int:
    seed_registry()
    n_space = REGISTRY.search_space_size()
    print("E16 — is exponent_high a measure of WHO the person is rather than their state?")
    print(f"   search space {n_space} registered candidates; analytic dof >= 72")
    if not os.path.exists(TABLE):
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    with open(TABLE, newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status") == "ok"]
    if len(rows) < 40:
        print(f"   *** only {len(rows)} rows; the stream is still running. Nothing is reported — this is")
        print("   a statement about the table, not about the candidate.")
        return 1

    age = np.array([_f(r.get("meta_age")) for r in rows])
    cond = np.array([r.get("meta_condition", "") for r in rows])
    subj = np.array([r.get("subject", "") for r in rows])
    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)      # noqa: E731
    rng = np.random.default_rng(20260730)
    print(f"   rows {len(rows)}   subjects {len(set(subj))}   "
          f"eyes-closed {int((cond == 'closed').sum())} / eyes-open {int((cond == 'open').sum())}")
    fin_age = np.isfinite(age)
    print(f"   age: n={int(fin_age.sum())} median {np.median(age[fin_age]):.1f} "
          f"range {age[fin_age].min():.1f}-{age[fin_age].max():.1f} years")

    # ------------------------------- P1: alpha blocking + computability ----------------------------
    print("\n" + "=" * 100)
    print(f"P1 — MACHINERY GATE: {GATE_FEATURE} must be HIGHER eyes-closed, within subject (alpha blocking)")
    print("=" * 100)
    a = col(GATE_FEATURE)
    moved, n_pairs = 0, 0
    for s in np.unique(subj):
        c = a[(subj == s) & (cond == "closed")]
        o = a[(subj == s) & (cond == "open")]
        if c.size and o.size and np.isfinite(c[0]) and np.isfinite(o[0]):
            n_pairs += 1
            moved += int(c[0] > o[0])
    frac = moved / n_pairs if n_pairs else float("nan")
    p_alpha = np.isfinite(frac) and frac >= GATE_MIN_FRACTION and n_pairs >= 20
    pv = col(PRIMARY)
    frac_finite = float(np.isfinite(pv).mean())
    p_finite = frac_finite >= GATE_MIN_FINITE
    p1 = bool(p_alpha and p_finite)
    print(f"   alpha higher eyes-closed in {moved}/{n_pairs} subjects ({frac:.1%}); need "
          f"{GATE_MIN_FRACTION:.0%}   {'PASS' if p_alpha else '*** FAIL'}")
    print(f"   {PRIMARY} finite in {frac_finite:.1%} of rows; need {GATE_MIN_FINITE:.0%}   "
          f"{'PASS' if p_finite else '*** FAIL'}")
    if not p1:
        print("\n   *** GATE FAILED. Nothing about exponent_high is reported: the script exits BEFORE")
        print("   computing any age association, so P2/P3/P4 remain genuinely unexamined and a future")
        print("   experiment with a correctly specified gate can still test them cleanly.")

        # WHY IT FAILED, DIAGNOSED RATHER THAN EXCUSED. A pipeline fault would not be monotone in age.
        band = []
        for lo_a, hi_a in ((5, 8), (8, 10), (10, 13), (13, 30)):
            hits = tot = 0
            for s in np.unique(subj):
                m_age = age[subj == s]
                if not m_age.size or not np.isfinite(m_age[0]) or not (lo_a <= m_age[0] < hi_a):
                    continue
                c = a[(subj == s) & (cond == "closed")]
                o = a[(subj == s) & (cond == "open")]
                if c.size and o.size and np.isfinite(c[0]) and np.isfinite(o[0]):
                    tot += 1
                    hits += int(c[0] > o[0])
            if tot:
                band.append({"age_lo": lo_a, "age_hi": hi_a, "fraction": hits / tot, "n": tot})
        print("\n   ALPHA BLOCKING BY AGE BAND:")
        for b in band:
            print(f"      age {b['age_lo']:2d}-{b['age_hi']:2d}: {b['fraction']:5.1%}  (n={b['n']})")
        print("\n   If this gradient is MONOTONE IN AGE, a broken pipeline is not the explanation: the")
        print("   posterior dominant rhythm is slower in young children, so a fixed adult 8-12 Hz band")
        print("   misses it, and this cohort's median age is under 10. THE FEATURE IS ADULT-CALIBRATED")
        print("   AND THIS DEPOSIT IS NOT ADULT -- a finding about the registry rather than only about")
        print("   this gate, since `relative_alpha_power` carries the same fixed band everywhere.")
        print("")
        print("   NOT DONE, DELIBERATELY: an 8-subject probe of posterior-only channels and a wider")
        print("   6-13 Hz band gave 5/8 to 7/8 across four variants -- indistinguishable at that n. The")
        print("   best-looking variant is NOT adopted. Re-specifying the gate needs its own registration")
        print("   and must be labelled a re-specification after a failure, not a pre-registration.")
        json.dump({"experiment": "E16", "gate_passed": False, "alpha_fraction": frac,
                   "n_pairs": n_pairs, "primary_finite_frac": frac_finite,
                   "alpha_blocking_by_age_band": band, "primary_never_computed": True},
                  open(os.path.join(RESULTS, "e16_hbn_age.json"), "w"), indent=2)
        return 1
    print("\n   GATE PASSED")

    # ------------------------------- P2/P3: the age contrast ---------------------------------------
    ec = (cond == "closed") & fin_age
    a_ec = age[ec]
    lo_cut, hi_cut = np.percentile(a_ec, [33.3333, 66.6667])
    print("\n" + "=" * 100)
    print(f"AGE CONTRAST — youngest vs oldest tertile, eyes-closed rows "
          f"(cuts at {lo_cut:.1f} and {hi_cut:.1f} years)")
    print("=" * 100)
    sel = ec & ((age <= lo_cut) | (age >= hi_cut))
    y_age = (age[sel] >= hi_cut).astype(float)
    s_age = subj[sel]
    print(f"   young {int((y_age == 0).sum())} / old {int((y_age == 1).sum())} subjects")
    print(f"   {'candidate':28s} {'AUC old-vs-young':>24s} {'|AUC-.5|':>9s}   note")
    out = {}
    for name in REPORT:
        v = col(name)[sel]
        if np.isfinite(v).sum() < 20:
            continue
        # Direction is not declared for AGE by any candidate -- this is an adversarial probe, not a
        # prediction -- so the raw 'higher with age' orientation is reported and the magnitude is what
        # matters. Scoring a probe against an invented direction would be exactly the error E10 caught.
        au = directional_auc(y_age, v, "higher")
        blo, bhi = cluster_bootstrap_ci(lambda i: directional_auc(y_age[i], v[i], "higher"),
                                        s_age, rng, reps=2000)[:2]
        rho = spearman(age[sel], v)
        out[name] = {"auc": float(au), "ci": [float(blo), float(bhi)], "abs": float(abs(au - 0.5)),
                     "spearman_with_age": float(rho)}
        mark = "  <-- primary" if name == PRIMARY else ""
        print(f"   {name:28s} {au:8.3f} [{blo:.3f}, {bhi:.3f}] {abs(au - 0.5):9.3f}   "
              f"rho(age) {rho:+.3f}{mark}")

    pri = out.get(PRIMARY)
    p2 = bool(pri and pri["abs"] >= AGE_EFFECT_MIN)
    p3 = bool(pri and pri["abs"] >= DS005620_STATE_EFFECT - COMPARISON_TOLERANCE)

    # ------------------------------- P4: within-subject eyes-open/closed ---------------------------
    print("\n" + "=" * 100)
    print(f"P4 — DISAMBIGUATOR: does {PRIMARY} respond to eyes-open vs eyes-closed WITHIN subject?")
    print("=" * 100)
    diffs, dsubj = [], []
    for s in np.unique(subj):
        c = pv[(subj == s) & (cond == "closed")]
        o = pv[(subj == s) & (cond == "open")]
        if c.size and o.size and np.isfinite(c[0]) and np.isfinite(o[0]):
            diffs.append(float(c[0] - o[0]))
            dsubj.append(s)
    p4 = False
    ws = {}
    if len(diffs) >= 20:
        arr, sarr = np.asarray(diffs), np.asarray(dsubj)
        fr = float(np.mean(arr > 0))
        flo, fhi = cluster_bootstrap_ci(lambda i: float(np.mean(arr[i] > 0)), sarr, rng, reps=2000)[:2]
        p4 = bool(flo > 0.5 or fhi < 0.5)
        ws = {"fraction_higher_closed": fr, "ci": [float(flo), float(fhi)], "n": len(diffs)}
        print(f"   higher eyes-closed in {fr:.1%} [{flo:.1%}, {fhi:.1%}] of {len(diffs)} subjects   "
              f"{'RESPONDS' if p4 else 'undetermined — CI spans 50%'}")
    else:
        print(f"   only {len(diffs)} paired subjects; not estimable")

    # ------------------------------- verdict --------------------------------------------------------
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 GATE alpha blocking + computability                  : MET")
    print(f"   P2 age effect |AUC-0.5| >= {AGE_EFFECT_MIN}                       : "
          f"{'MET' if p2 else 'NOT MET'}" + (f" ({pri['abs']:.3f})" if pri else ""))
    print(f"   P3 age effect >= ds005620's state effect {DS005620_STATE_EFFECT} - {COMPARISON_TOLERANCE}   : "
          f"{'MET' if p3 else 'NOT MET'}")
    print(f"   P4 responds to eyes-open/closed within subject          : {'MET' if p4 else 'NOT MET'}")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p2:
        verdict = "AGE_WORRY_UNFOUNDED"
        print(f"   {PRIMARY}'s association with age is weak (|AUC-0.5| "
              f"{pri['abs'] if pri else float('nan'):.3f}). The measure is NOT substantially")
        print("   developmental in this cohort, which is the outcome I predicted against and the better")
        print("   one for the lead.")
    elif p4:
        verdict = "STATE_MEASURE_WITH_A_PERSON_LEVEL_OFFSET"
        print(f"   {PRIMARY} carries a substantial age signal (|AUC-0.5| {pri['abs']:.3f}) AND responds to")
        print("   a within-subject state change. That combination is a CALIBRATION problem rather than an")
        print("   invalidity: its absolute value cannot be read as a state without normalising for the")
        print("   person, but within-subject monitoring — the same patient before and after — is untouched.")
        print("   For the anaesthesia wedge, which is inherently within-subject, this is survivable.")
        print("   For any between-subject deployment it is not, without an age-normalised reference.")
    else:
        verdict = "TRACKS_THE_PERSON_NOT_THE_STATE"
        print(f"   {PRIMARY} carries a substantial age signal (|AUC-0.5| {pri['abs']:.3f}) and does NOT")
        print("   demonstrably respond to a within-subject state change here. That is the damaging")
        print("   combination. BUT eyes-open/closed is a far weaker manipulation than sedation, so this")
        print("   null may be power rather than absence — registered in advance, not offered now as an")
        print("   excuse. The honest reading is that the lead needs an age-normalised reference before any")
        print("   between-subject claim, and that a stronger within-subject contrast should settle P4.")
    print(f"\n   verdict: {verdict}")
    print("\n   SCOPE: uncalibrated units (scale-invariant features only), children 5-21 vs adults in the")
    print("   sedation deposits, cross-sectional age. The claim is about the MAGNITUDE of a person-level")
    print("   association against a state association — not a like-for-like contrast.")

    dst = os.path.join(RESULTS, "e16_hbn_age.json")
    json.dump({"experiment": "E16", "gate_passed": True, "search_space_size": n_space,
               "n_rows": len(rows), "n_subjects": len(set(subj)),
               "alpha_blocking_fraction": frac, "age_tertile_cuts": [float(lo_cut), float(hi_cut)],
               "age_contrast": out, "within_subject_eyes": ws,
               "ds005620_state_effect": DS005620_STATE_EFFECT,
               "excluded_scale_dependent": list(EXCLUDED_SCALE_DEPENDENT),
               "predictions": {"P1": True, "P2": p2, "P3": p3, "P4": p4},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
