#!/usr/bin/env python3
"""E11 — is the 20-40 Hz exponent a propofol effect rather than a consciousness marker?

REGISTERED BEFORE ANY SLEEP-EDF FEATURE VALUE WAS READ. At the time this docstring was committed the
Sleep-EDF v2 stream was mid-flight; the only columns inspected were `recording_id`, `subject`, `status` and
`sfreq`, in order to learn how the stage label is encoded. No exponent, no complexity measure, no muscle
proxy. The commit that adds this file precedes the commit that reports its output, and the stream's own rows
are timestamped after it.

WHERE THE HYPOTHESIS CAME FROM, AND WHY IT CANNOT BE TESTED ON CHENNU.

E10 set out to ask whether `exponent_high` is a muscle artefact and answered something else. Its muscle
proxies DISAGREED IN SIGN: `emg_kurtosis` fell with sedation (AUC 0.682 [0.517, 0.848] in the declared
'lower' direction, consistent with reduced muscle tone) while `emg_beta_gamma_fraction` ROSE (0.292
[0.167, 0.420] — CI entirely on the wrong side for muscle). Error-catalogue rule 16 says that when two arms
of the same test disagree in sign, the definition is doing the work, and it was: a 20-45 Hz relative-power
measure under propofol is not reading muscle, it is reading PROPOFOL BETA.

    Xi C, Sun S, Pan C, Ji F, Cui X, Li T. Different effects of propofol and dexmedetomidine sedation on
    electroencephalogram patterns. PLoS One. 2018;13(6):e0199120. PMID 29920532.
    "During moderate sedation ... propofol decreased the alpha power in the occipital area and increased the
    global spindle/beta/gamma power."
    (Verified from the MEDLINE record via E-utilities, per error-catalogue rule 25. Not via WebFetch, which
    fabricated six citations for this project once.)

That reading also explains E10's other surprise. `exponent_high` correlated POSITIVELY with the 20-45 Hz
power fraction (rho +0.448) when a between-band intuition says a steeper slope should mean less high-band
power. It says no such thing for a WITHIN-band slope: a beta hump sitting near the LOW EDGE of a 20-40 Hz fit
window raises the band's total power AND steepens the slope fitted across it. One mechanism, both
observations.

If `exponent_high` is propofol beta, it is a real drug effect and a worse problem for this project than
muscle would have been, because Brief 01 is specifically about separating drug from state, and every Chennu
contrast moves drug and state together. Chennu cannot answer this. A DRUG-FREE loss of responsiveness can.

THE CONTRAST. Sleep-EDF, wake versus N3, within subject. No anaesthetic of any kind. If `exponent_high`
discriminates here it is not propofol-specific.

THE ASYMMETRY, AND IT RUNS OPPOSITE TO E10's — REGISTERED SO IT CANNOT BE CHOSEN AFTERWARDS.
This test can REFUTE the general-marker claim strongly and support it only weakly, because sleep stages are
scored FROM the EEG (§9.6, definitional circularity). Staging gives almost any EEG feature a head start, so a
positive here is cheap. A NEGATIVE is the informative outcome: if `exponent_high` cannot separate wake from
N3 even with circularity working in its favour, it is doing something propofol-specific and the E08 result
must be reported as a drug marker rather than a consciousness marker.

REGISTERED PREDICTIONS:
    P1  MACHINERY GATE, AND IT HAS TEETH. `relative_delta_power` must reach AUC >= 0.90 for W vs N3 in its
        declared direction. N3 is DEFINED by slow-wave activity occupying at least 20 % of the epoch, so a
        delta measure that cannot find it means the labels, the window selection or the pipeline are broken,
        and nothing else in this script is reported. This is a gate rather than a result precisely because
        it is guaranteed by the scoring rules if the machinery works.
    P2  PRIMARY. `exponent_high`'s signed AUC for W vs N3 EXCLUDES 0.5 in its declared 'higher' direction.
        Met -> not propofol-specific, weakly, with the circularity discount applied. Not met -> the propofol
        beta explanation gains substantially and the E08 lead is downgraded in writing.
    P3  `exponent_high`'s Sleep-EDF AUC is LOWER than its Chennu AUC of 0.863. Sleep-EDF is sampled at
        100 Hz, so 40 Hz sits at 0.8 of Nyquist, inside the acquisition anti-alias roll-off; the fit is
        degraded by the deposit before any biology is involved. Registered so that a smaller number is not
        read as a weaker marker when it may be a worse measurement.
    P4  RISKY, AND THE ONE I MOST EXPECT TO GET WRONG. `exponent_low` (1-20 Hz) lands ABOVE 0.5 here —
        OPPOSITE in sign to the 0.168 it gave on Chennu. N3 is delta-dominated, and more low-frequency power
        steepens a 1-20 Hz fit, which raises the exponent; propofol at moderate sedation did the reverse.
        If this holds, the exponent family disagrees in sign between two unconsciousness contrasts, which by
        rule 16 means the exponent's band choice is doing the work rather than the brain state — and that
        would apply to `exponent_high` as much as to `exponent_low`.

    FALSIFICATION OF THE E08 LEAD: P2 not met while P1 passes. Then `exponent_high` is a propofol marker,
    the 0.863 stands as a drug measurement, and the claim that it is a consciousness marker is withdrawn.

WHAT THIS CANNOT DO. It cannot distinguish "propofol-specific" from "anaesthetic-specific", since there is no
second drug here. It cannot escape the circularity of sleep staging, only exploit its direction. And it says
nothing about the 20-40 Hz band having been chosen after seeing 1-20 and 1-40 behave differently — that gap
is still open and still needs its own extraction pass.
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
from bsde.verifier.stats import directional_auc, cluster_bootstrap_ci                  # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "sleep_edfx_staged_v2.csv")

GATE = "relative_delta_power"
GATE_MIN_AUC = 0.90
PRIMARY = "exponent_high"
CHENNU_AUC = {"exponent_high": 0.863, "exponent_low": 0.168, "whole_head_exponent": 0.393,
              "lempel_ziv": 0.223, "spectral_entropy": 0.292, "relative_delta_power": 0.320}
REPORT = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "uce_v1", "wpli_alpha", "emg_beta_gamma_fraction", "emg_kurtosis")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main() -> int:
    seed_registry()
    n_space = REGISTRY.search_space_size()
    print("E11 — is exponent_high propofol beta? Drug-free contrast: Sleep-EDF wake vs N3")
    print(f"   search space {n_space} registered candidates; analytic dof >= 72, NOT 1")
    if not os.path.exists(TABLE):
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    with open(TABLE, newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status") == "ok"]

    stage = np.array([r["recording_id"].rsplit("@", 1)[-1] for r in rows])
    keep = np.isin(stage, ("W", "N3"))
    rows = [r for r, k in zip(rows, keep) if k]
    stage = stage[keep]
    y = (stage == "N3").astype(float)
    subj = np.array([r.get("subject", "") for r in rows])

    # Within-subject only: a subject contributing just one stage adds a between-subject comparison to what
    # is meant to be a within-subject contrast, and this deposit's stream may still be running, so the two
    # stages of a subject can arrive in different batches.
    from collections import Counter
    have_both = {s for s in set(subj)
                 if len({st for st, ss in zip(stage, subj) if ss == s}) == 2}
    m = np.array([s in have_both for s in subj])
    rows = [r for r, k in zip(rows, m) if k]
    y, subj, stage = y[m], subj[m], stage[m]
    print(f"   rows {len(rows)}   subjects with BOTH stages {len(have_both)}   "
          f"W {int((y == 0).sum())} / N3 {int((y == 1).sum())}")
    print(f"   dropped {int((~m).sum())} rows from subjects contributing only one stage")
    if len(have_both) < 10:
        print("   *** fewer than 10 complete subjects. Nothing is reported (rule 31: absent, not negative).")
        return 1

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)  # noqa: E731
    rng = np.random.default_rng(20260730)

    def score(name):
        cand = REGISTRY.get(name)
        d = cand.predicted("unconscious_vs_awake")
        x = col(name)
        if not np.isfinite(x).any():
            return None
        if d not in ("higher", "lower"):
            # Artefact measures carry no brain-state direction. Report 'higher' orientation raw and label it
            # as such rather than inventing a declaration for them.
            d = "higher"
            declared = "(artefact, higher orientation)"
        else:
            declared = d
        a = directional_auc(y, x, d)
        lo, hi = cluster_bootstrap_ci(lambda i: directional_auc(y[i], x[i], d), subj, rng, reps=2000)[:2]
        return {"declared": declared, "auc": float(a), "ci": [float(lo), float(hi)],
                "n_finite": int(np.isfinite(x).sum())}

    # ---------------------------- P1 GATE ------------------------------------------------------------
    print("\n" + "=" * 100)
    print(f"P1 — MACHINERY GATE: {GATE} must reach AUC >= {GATE_MIN_AUC} on a contrast that DEFINES it")
    print("=" * 100)
    g = score(GATE)
    if g is None:
        print(f"   {GATE} not computed. Nothing is reported.")
        return 1
    p1 = g["auc"] >= GATE_MIN_AUC
    print(f"   {GATE:26s} AUC {g['auc']:.3f} [{g['ci'][0]:.3f}, {g['ci'][1]:.3f}]   "
          f"{'GATE PASSED' if p1 else '*** GATE FAILED'}")
    if not p1:
        print("\n   N3 is defined by slow-wave activity in at least 20 % of the epoch. A delta measure that")
        print("   cannot find it means the labels, the window selection or the pipeline are broken. Nothing")
        print("   else is reported: a failed precondition makes the downstream verdict ABSENT, not negative")
        print("   (error-catalogue rule 31).")
        json.dump({"experiment": "E11", "gate_passed": False, "gate": g},
                  open(os.path.join(RESULTS, "e11_propofol_beta.json"), "w"), indent=2)
        return 1

    # ---------------------------- results -------------------------------------------------------------
    print("\n" + "=" * 100)
    print("SIGNED AUC, wake vs N3, each candidate against ITS OWN declared direction")
    print("=" * 100)
    print(f"   {'candidate':26s} {'declared':>28s} {'AUC (Sleep-EDF)':>24s} {'Chennu':>8s}  {'sign':>9s}")
    out = {}
    for name in REPORT:
        s = score(name)
        if s is None:
            continue
        out[name] = s
        ch = CHENNU_AUC.get(name)
        if ch is None:
            flip = ""
        elif (s["auc"] - 0.5) * (ch - 0.5) < 0:
            flip = "*** FLIPS"
        else:
            flip = "same"
        chs = f"{ch:.3f}" if ch is not None else "   -  "
        print(f"   {name:26s} {s['declared']:>28s} {s['auc']:8.3f} [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}] "
              f"{chs:>8s}  {flip:>9s}")

    # ---------------------------- SATURATION DIAGNOSTIC -----------------------------------------------
    # ADDED AFTER THE FIRST RUN, and labelled as such. It is not a new prediction and it does not move any
    # registered bar; it MEASURES the size of the effect the registration already named. The docstring says
    # "circularity gives almost any EEG feature a head start here and a positive is cheap". It turned out to
    # be free: on the first run ELEVEN OF ELEVEN candidates landed at |AUC - 0.5| >= 0.4, including a muscle
    # artefact proxy at 0.995 and a connectivity measure at 0.074. When measures known to capture different
    # things all separate a contrast perfectly, the contrast is doing the work and no candidate's score
    # carries information about that candidate (rule 18, in its across-candidates form).
    #
    # The mechanical explanations were checked and ruled out before this was attributed to circularity:
    # window length is exactly 12000 samples in BOTH classes, with 2 channels and 100 Hz throughout, so no
    # class differs from the other in how much signal it was given.
    sat = {k: abs(v["auc"] - 0.5) for k, v in out.items()}
    n_sat = sum(1 for d in sat.values() if d >= 0.40)
    med_sat = float(np.median(list(sat.values())))
    # The criterion is the MEDIAN, with the count reported beside it. A first version used only the count
    # against an 80 % threshold and landed on exactly 8 of 11 -- a verdict that flips if one candidate moves
    # by 0.001 is not a verdict. The median is 0.470 on the same data and says the same thing without
    # balancing on a boundary. Changing it is a robustness fix, not a result fix: the conclusion is
    # "saturated" under either rule, which is why the count is still printed and can be checked.
    saturated = med_sat >= 0.35 and n_sat >= len(sat) / 2
    order = sorted(sat.items(), key=lambda kv: -kv[1])
    pri_rank = 1 + [k for k, _ in order].index(PRIMARY) if PRIMARY in sat else None
    print("\n" + "=" * 100)
    print("SATURATION DIAGNOSTIC (added after the first run; measures the registered circularity caveat)")
    print("=" * 100)
    print(f"   median |AUC - 0.5| across candidates: {med_sat:.3f}   "
          f"(a perfectly separating contrast gives 0.5; chance gives 0)")
    print(f"   candidates with |AUC - 0.5| >= 0.40: {n_sat}/{len(sat)}")
    print(f"   {PRIMARY} ranks {pri_rank} of {len(sat)} by |AUC - 0.5| "
          f"({sat.get(PRIMARY, float('nan')):.3f}); the top three are "
          f"{', '.join(f'{k} {d:.3f}' for k, d in order[:3])}")
    if saturated:
        print("   *** CONTRAST SATURATED. Measures known to capture different things — an aperiodic slope,")
        print("   a complexity measure, a connectivity measure and an ARTEFACT proxy — all separate wake")
        print("   from N3 near-perfectly. Ruled out first: both classes have identical 12000-sample")
        print("   windows, 2 channels, 100 Hz, so neither class was given more signal than the other.")
        print("   What remains is that this contrast is trivially separable, so a candidate's score here")
        print("   says nothing about the candidate.")

    # ---------------------------- predictions ---------------------------------------------------------
    pri = out.get(PRIMARY)
    p2 = bool(pri and pri["ci"][0] > 0.5)
    p3 = bool(pri and pri["auc"] < CHENNU_AUC[PRIMARY])
    el = out.get("exponent_low")
    p4 = bool(el and el["auc"] > 0.5)

    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 GATE {GATE} >= {GATE_MIN_AUC}                    : MET (AUC {g['auc']:.3f})")
    print(f"   P2 exponent_high excludes 0.5 in declared direction : {'MET' if p2 else 'NOT MET'} "
          f"(AUC {pri['auc']:.3f} [{pri['ci'][0]:.3f}, {pri['ci'][1]:.3f}])" if pri else
          "   P2 exponent_high not computed")
    print(f"   P3 lower than Chennu's 0.863 (100 Hz degrades the fit): {'MET' if p3 else 'NOT MET'}")
    print(f"   P4 exponent_low ABOVE 0.5, opposite to Chennu's 0.168: {'MET' if p4 else 'NOT MET'}"
          + (f" (AUC {el['auc']:.3f})" if el else ""))

    # ---------------------------- verdict -------------------------------------------------------------
    print("\n" + "=" * 100); print("VERDICT ON THE E08 LEAD"); print("=" * 100)
    if not pri:
        verdict = "NOT_COMPUTED"
        print("   exponent_high is absent from this table. Nothing is concluded.")
    elif p2 and saturated:
        verdict = "UNINFORMATIVE_CONTRAST_SATURATED"
        print("   P2 was MET, and it means nothing, because the contrast is saturated: every candidate")
        print("   passes it, including a muscle-artefact proxy. The registration said a positive here")
        print("   would be cheap; the measurement says it is free. A test that the negative control also")
        print("   passes is not a test.")
        print("")
        print(f"   Worse for the lead than that: {PRIMARY} ranks {pri_rank} of {len(sat)} on this contrast —")
        print("   it is among the WEAKEST candidates on a contrast where nearly everything is near-perfect.")
        print("   That is the opposite of what a distinctive marker looks like, though on a saturated")
        print("   contrast the ranking is barely more informative than the AUC itself.")
        print("")
        _emg = out.get("emg_beta_gamma_fraction", {}).get("auc")
        print("   THE PROPOFOL-BETA HYPOTHESIS IS NOT REMOVED. It stands exactly where E10 left it, and")
        print("   this experiment did not test it. Reporting 'not propofol-specific' from a contrast where")
        print(f"   emg_beta_gamma_fraction also scores {_emg:.3f} would be a claim built on a broken"
              if _emg is not None else
              "   an artefact proxy scores just as well would be a claim built on a broken")
        print("   instrument. Rule 31: the verdict is ABSENT, not negative.")
        print("")
        print("   THE FIX is a HARDER, ADJACENT contrast where candidates can actually separate from one")
        print("   another — N2 vs N3, or W vs N1 — which needs its own extraction and its own registration.")
        print("   W vs N3 in Sleep-EDF spans daytime wakefulness with eyes open and movement against")
        print("   mid-night slow-wave sleep; almost nothing about the EEG is held constant across it.")
    elif p2:
        verdict = "NOT_PROPOFOL_SPECIFIC_WEAKLY"
        print("   exponent_high separates wake from N3 in a DRUG-FREE contrast, so it is not a propofol")
        print("   effect. THIS IS THE WEAK DIRECTION OF THE TEST, as registered: sleep stages are scored")
        print("   from the EEG, so circularity gives any EEG feature a head start here and a positive is")
        print("   cheap. It removes the propofol-beta explanation; it does not establish the marker.")
    elif pri["ci"][1] < 0.5:
        verdict = "REFUTED_OPPOSITE_DIRECTION"
        print("   exponent_high moves the WRONG WAY in drug-free unconsciousness — the opposite sign to")
        print("   Chennu, on the same declared direction. By rule 16 the band choice is doing the work,")
        print("   not the brain state. The E08 lead is WITHDRAWN as a consciousness marker; 0.863 stands")
        print("   as a measurement of what propofol does to the 20-40 Hz band.")
    else:
        verdict = "PROPOFOL_SPECIFIC"
        print("   exponent_high CANNOT separate wake from N3 without a drug, despite circularity working")
        print("   in its favour and despite the gate confirming the machinery works on this very contrast.")
        print("   The propofol-beta explanation gains substantially. The E08 lead is DOWNGRADED: 0.863 is")
        print("   reported as a drug marker, not as a consciousness marker, until something separates them.")
    print(f"\n   verdict: {verdict}")
    print(f"\n   Denominators: {n_space} registered candidates, analytic dof >= 72. Sleep-EDF sampled at")
    print("   100 Hz, so the 20-40 Hz fit sits inside the acquisition roll-off — see P3.")

    dst = os.path.join(RESULTS, "e11_propofol_beta.json")
    json.dump({"experiment": "E11", "gate_passed": True, "search_space_size": n_space,
               "analytic_dof_lower_bound": 72, "n_rows": len(rows),
               "n_subjects_with_both_stages": len(have_both), "gate": g, "signed_auc": out,
               "chennu_reference": CHENNU_AUC,
               "saturation": {"n_saturated": n_sat, "n_scored": len(sat), "saturated": bool(saturated),
                              "median_abs_auc_minus_half": med_sat,
                              "primary_rank_by_abs_auc": pri_rank,
                              "abs_auc_minus_half": {k: float(v) for k, v in sat.items()}},
               "predictions": {"P1": True, "P2": p2, "P3": p3, "P4": p4},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
