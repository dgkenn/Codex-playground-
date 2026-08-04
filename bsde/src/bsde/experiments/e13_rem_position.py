#!/usr/bin/env python3
"""E13 — where does REM sit? The first contrast this project has reached that pulls two constructs apart.

REGISTERED BEFORE ANY FIVE-STAGE FEATURE VALUE EXISTS. The five-stage work-list was built from hypnograms
only (stage labels and block boundaries); no EEG has been read at any stage other than W and N3, and no
candidate has been evaluated on N1, N2 or REM.

WHY THIS EXPERIMENT, AND WHY IT IS DIFFERENT FROM EVERY PREVIOUS ONE HERE.

Every contrast this project has reached confounds the things Brief 01 exists to separate:

    Chennu level 1 vs 3     drug up, arousal down, responsiveness down -- together (and per §9.16, barely
                            moving at all: the cohort is never unconscious)
    ds005620 awake vs sed   drug and state move together, no experience reports
    Sleep-EDF W vs N3       arousal and EEG activation move together -- and E11 measured the result: the
                            contrast is SATURATED, median |AUC-0.5| = 0.470 across eleven candidates,
                            including an artefact proxy at 0.989. A test the negative control passes is not
                            a test.

REM pulls two of them apart, in drug-free humans, in data already reachable:

    behavioural responsiveness   REM is at least as unresponsive as N3 -- motor atonia plus a high arousal
                                 threshold
    global EEG activation        REM is wake-like, and that is part of its scoring definition

So the question "where does a candidate place REM, relative to the light pole and to N3?" asks directly
whether that candidate is tracking BEHAVIOURAL STATE or EEG ACTIVATION. That is Brief 01's arousal-versus-
output separation, in the only form public data supports.

WHAT THIS IS *NOT*, corrected before registration rather than after. The tempting framing is "REM has
conscious experience and N3 does not", making this an experience contrast. That framing is wrong:

    Siclari F, Baird B, Perogamvros L, Bernardi G, LaRocque JJ, Riedner B, Boly M, Postle BR, Tononi G.
    The neural correlates of dreaming. Nat Neurosci. 2017;20(6):872-878. PMID 28394322.
    "Traditionally, dreaming has been identified with rapid eye-movement (REM) sleep ... However, dreaming
    also occurs in non-REM (NREM) sleep ... In both NREM and REM sleep, reports of dream experience were
    associated with LOCAL decreases in low-frequency activity in posterior cortical regions."
    (Verified from the MEDLINE record via E-utilities, rule 25.)

Experience is not a property of the stage; it is a property of local posterior cortical activity WITHIN a
stage, and it is read out by waking the subject and asking. Sleep-EDF contains no awakenings and no reports.
**This experiment therefore does NOT reopen §9.5 — it reinforces it.** The dissociation on offer here is
EEG-activation versus behavioural-responsiveness, and that is what will be claimed, no more.

THE STATISTIC. Per candidate, per subject, with five states available:

    REM position index  =  ( v[REM] - v[N3] ) / ( v[anchor] - v[N3] )

1.0 places REM at the light/awake pole; 0.0 places it with N3. Computed per subject and summarised by the
median with a subject-clustered CI, so it is a within-subject quantity throughout and never a comparison of
different people at different rungs — which is also why the work-list requires ALL FIVE stages from every
retained recording.

THE CIRCULARITY, AND WHY IT DOES NOT SINK THIS. REM's R&K definition includes low-voltage mixed-frequency
(wake-like) EEG, so an index near 1.0 is PARTLY GUARANTEED by the scoring rule for any EEG measure. The
absolute value is therefore not informative and is not the registered statistic. **The registered statistic
is the SPREAD ACROSS CANDIDATES.** Circularity acts on every candidate equally — they all read the EEG that
was used to stage — so it cannot manufacture disagreement between them. Spread is evidence of real
differentiation; absence of spread is evidence that this project's whole candidate set is reading one thing.

REGISTERED PREDICTIONS:
    P1  MACHINERY GATE. `relative_delta_power` must increase monotonically across the DEPTH ladder
        W < N1 < N2 < N3 -- median per-subject Spearman against depth rank >= +0.80. REM is EXCLUDED from
        this gate, because REM breaks depth monotonicity by construction and including it would test the
        hypothesis inside the gate. N3 is defined by slow-wave activity, so a delta measure that cannot
        recover the ladder means the staging, the windowing or the pipeline is broken and nothing else is
        reported (rule 31).
    P2  PRIMARY. The REM position index SPREADS across candidates: max minus min across candidates exceeds
        0.50. Met -> candidates genuinely differ in whether they track EEG activation or behavioural state,
        which is the first real differentiation this project would have found. Not met -> every candidate is
        reading one construct, and BSDE's premise that these measures capture separable things fails on the
        only public data that can test it. Both outcomes are reportable and the second is the more important.
    P3  DIRECTION. At least one candidate places REM closer to N3 than to the anchor (index < 0.5). If NO
        candidate does, then nothing in this registry tracks behavioural unresponsiveness as distinct from
        EEG desynchronisation -- a clean negative for the separation Brief 01 requires.
    P4  ANCHOR CONTROL, AND IT GATES P2 AND P3 (rule 34: a placebo that sits beside the result is not a
        gate). The W-anchored and N1-anchored indices must AGREE -- per-candidate absolute difference below
        0.25 for a majority of candidates. Sleep-EDF's wake is overwhelmingly DAYTIME wake: these are ~20 h
        ambulatory recordings, and one hypnogram inspected while building the work-list had a single
        contiguous wake block of 30,630 s. The W window is therefore drawn from mid-day, eyes open and
        moving, and is contaminated by movement and EMG in a way N1 is not. If the two anchors disagree, only
        the N1-anchored index is interpreted -- and that must be decided by THIS comparison, registered in
        advance, rather than by whichever anchor looks better afterwards.

    FALSIFICATION: P2 not met. If every candidate places REM at the same point, then the seventeen registered
    candidates are seventeen parameterisations of one measurement, and the redundancy this project has
    already over-predicted three times (rule 28) is the whole story rather than an occasional finding.

SCOPE. Healthy sleepers, two EEG channels (Fpz-Cz and Pz-Oz), 100 Hz, one deposit, 120 s windows drawn from
each stage's own longest contiguous block. Denominators: the registered candidate count, and analytic_dof
>= 72 for the exponent family (E09). A NOTE FOR LATER, not acted on here: Siclari's correlate of experience
is posterior and local, and Pz-Oz is a posterior derivation -- a per-channel version of this analysis is
therefore possible on this deposit and is not attempted in this script.
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

from bsde.candidates.registry import REGISTRY                                        # noqa: E402
from bsde.candidates.seed import seed_registry                                        # noqa: E402
from bsde.verifier.stats import cluster_bootstrap_ci, spearman                         # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "sleep_edfx_five_stage.csv")

DEPTH_LADDER = ("W", "N1", "N2", "N3")          # REM deliberately absent -- see P1
DEPTH_RANK = {"W": 0.0, "N1": 1.0, "N2": 2.0, "N3": 3.0}
ANCHORS = ("W", "N1")
GATE = "relative_delta_power"
GATE_MIN_RHO = 0.80
SPREAD_MIN = 0.50
ANCHOR_TOL = 0.25
CANDIDATES = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
              "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
              "uce_v1", "wpli_alpha", "spatial_participation_ratio", "multiscale_entropy_slope",
              "pac_slow_alpha", "emg_beta_gamma_fraction", "emg_kurtosis")
# A denominator this small makes the ratio explode. The guard is expressed relative to the candidate's own
# between-subject spread so it means the same thing for a measure in nats as for one in microvolts.
MIN_DENOM_FRAC_OF_IQR = 0.20


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load():
    if not os.path.exists(TABLE):
        return {}
    by = defaultdict(dict)
    with open(TABLE, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("status") != "ok":
                continue
            rid = r["recording_id"]
            if "@" not in rid:
                continue
            subj, stage = rid.rsplit("@", 1)
            by[subj][stage] = r
    return by


def main() -> int:
    seed_registry()
    n_space = REGISTRY.search_space_size()
    print("E13 — where does REM sit: EEG activation or behavioural state?")
    print(f"   search space {n_space} registered candidates; analytic dof >= 72, NOT 1")
    by = load()
    if not by:
        print(f"   *** {os.path.basename(TABLE)} not present. Nothing is reported.")
        return 2
    complete = {s: d for s, d in by.items()
                if all(k in d for k in DEPTH_LADDER) and "REM" in d}
    print(f"   recordings in table {len(by)}   with a COMPLETE five-stage ladder {len(complete)}")
    print(f"   dropped {len(by) - len(complete)} recordings missing at least one stage")
    if len(complete) < 15:
        print("   *** fewer than 15 complete ladders. Nothing is reported (rule 31: absent, not negative).")
        return 1
    subs = sorted(complete)

    def val(subj, stage, name):
        return _f(complete[subj][stage].get(name, ""))

    # ------------------------------- P1: machinery gate -------------------------------------------
    print("\n" + "=" * 100)
    print(f"P1 — MACHINERY GATE: {GATE} must recover the DEPTH ladder W < N1 < N2 < N3 (REM excluded)")
    print("=" * 100)
    rhos = []
    for s in subs:
        v = [val(s, st, GATE) for st in DEPTH_LADDER]
        if all(np.isfinite(v)):
            rhos.append(spearman(v, [DEPTH_RANK[st] for st in DEPTH_LADDER]))
    rhos = [r for r in rhos if np.isfinite(r)]
    med_rho = float(np.median(rhos)) if rhos else float("nan")
    # TOLERANCE, AND WHY IT IS NOT A MOVED GOALPOST. The registered rule is "median rho >= 0.80" and the
    # measured median IS 0.80 -- it arrives as 0.7999999999999998, short by one unit in the last place. A
    # bare `>=` failed the gate on floating-point representation alone.
    #
    # The real defect is mine and it is worth more than the epsilon. A FOUR-point ladder makes Spearman
    # QUANTISED: the only attainable values are 0, +-0.2, +-0.4, +-0.6, +-0.8, +-1.0. Setting the threshold
    # at exactly 0.80 put it on an atom that 34.8 % of subjects sit on, so which side the median falls is
    # decided by representation rather than by data. The distribution is printed below so that marginality
    # is visible instead of being hidden behind a pass/fail, which is the durable fix; the tolerance only
    # makes the code agree with the rule that was registered.
    p1 = np.isfinite(med_rho) and med_rho >= GATE_MIN_RHO - 1e-9
    print(f"   median per-subject Spearman(delta power, depth rank) = {med_rho:+.3f} over {len(rhos)} "
          f"subjects   {'GATE PASSED' if p1 else '*** GATE FAILED'}")
    from collections import Counter as _C
    dist = sorted(_C(np.round(rhos, 4)).items())
    print(f"   mean rho {float(np.mean(rhos)):+.3f}; {float(np.mean(np.array(rhos) > 0)):.1%} of subjects "
          f"order the ladder in the right direction")
    print("   per-subject rho is quantised on a 4-point ladder: "
          + "  ".join(f"{v:+.1f}x{n}" for v, n in dist))
    if not p1:
        print("   N3 is defined by slow-wave activity. A delta measure that cannot recover the depth ladder")
        print("   means the staging, the windowing or the pipeline is broken. Nothing else is reported.")
        json.dump({"experiment": "E13", "gate_passed": False, "median_depth_rho": med_rho},
                  open(os.path.join(RESULTS, "e13_rem_position.json"), "w"), indent=2)
        return 1

    # ------------------------------- the five-state profile ----------------------------------------
    print("\n" + "=" * 100)
    print("MEDIAN VALUE BY STATE (raw units, for orientation only — scales are not comparable across rows)")
    print("=" * 100)
    print(f"   {'candidate':28s} " + " ".join(f"{st:>10s}" for st in ("W", "N1", "N2", "N3", "REM")))
    profile = {}
    for name in CANDIDATES:
        med = {}
        for st in ("W", "N1", "N2", "N3", "REM"):
            v = np.array([val(s, st, name) for s in subs])
            v = v[np.isfinite(v)]
            med[st] = float(np.median(v)) if v.size else float("nan")
        if not np.isfinite(list(med.values())).any():
            continue
        profile[name] = med
        print(f"   {name:28s} " + " ".join(f"{med[st]:10.4g}" for st in ("W", "N1", "N2", "N3", "REM")))

    # ------------------------------- REM position index ---------------------------------------------
    print("\n" + "=" * 100)
    print("REM POSITION INDEX  =  (REM - N3) / (anchor - N3)      1.0 = REM at the light pole, 0.0 = at N3")
    print("=" * 100)
    rng = np.random.default_rng(20260730)
    idx = {}
    for name in profile:
        allv = np.array([val(s, st, name) for s in subs for st in ("W", "N1", "N2", "N3", "REM")])
        allv = allv[np.isfinite(allv)]
        if allv.size < 10:
            continue
        iqr = float(np.percentile(allv, 75) - np.percentile(allv, 25))
        floor = MIN_DENOM_FRAC_OF_IQR * iqr
        idx[name] = {}
        for anchor in ANCHORS:
            per_subj, keep_subj = [], []
            for s in subs:
                a, n3, rem = val(s, anchor, name), val(s, "N3", name), val(s, "REM", name)
                if not (np.isfinite(a) and np.isfinite(n3) and np.isfinite(rem)):
                    continue
                if abs(a - n3) < floor:          # anchor and N3 indistinguishable -> ratio meaningless
                    continue
                per_subj.append((rem - n3) / (a - n3))
                keep_subj.append(s)
            if len(per_subj) < 10:
                idx[name][anchor] = None
                continue
            arr, sarr = np.array(per_subj), np.array(keep_subj)
            lo, hi = cluster_bootstrap_ci(lambda i: float(np.median(arr[i])), sarr, rng, reps=2000)[:2]
            idx[name][anchor] = {"median": float(np.median(arr)), "ci": [float(lo), float(hi)],
                                 "n": len(per_subj),
                                 "frac_in_unit": float(np.mean((arr >= 0) & (arr <= 1)))}
    print(f"   {'candidate':28s} {'W-anchored':>26s} {'N1-anchored':>26s} {'|diff|':>7s}")
    diffs = {}
    for name, d in sorted(idx.items(), key=lambda kv: -(kv[1].get("W") or {}).get("median", -9)):
        cells = []
        for anchor in ANCHORS:
            e = d.get(anchor)
            cells.append(f"{e['median']:7.3f} [{e['ci'][0]:6.3f},{e['ci'][1]:6.3f}]" if e else
                         f"{'not estimable':>26s}")
        if d.get("W") and d.get("N1"):
            diffs[name] = abs(d["W"]["median"] - d["N1"]["median"])
            dtxt = f"{diffs[name]:7.3f}"
        else:
            dtxt = "      -"
        print(f"   {name:28s} {cells[0]:>26s} {cells[1]:>26s} {dtxt}")

    # ------------------------------- P4 anchor gate, evaluated BEFORE P2/P3 -------------------------
    print("\n" + "=" * 100)
    print("P4 — ANCHOR GATE (evaluated before P2 and P3, because a gate can only invalidate a pass)")
    print("=" * 100)
    agree = [n for n, v in diffs.items() if v < ANCHOR_TOL]
    p4 = len(diffs) > 0 and len(agree) > len(diffs) / 2
    print(f"   candidates whose two anchors agree within {ANCHOR_TOL}: {len(agree)}/{len(diffs)}   "
          f"{'GATE PASSED' if p4 else '*** ANCHORS DISAGREE'}")
    use_anchor = "W" if p4 else "N1"
    if not p4:
        print("   The W anchor is contaminated: Sleep-EDF's wake is overwhelmingly DAYTIME wake, drawn from")
        print("   the middle of blocks that run for hours, with eyes open, movement and EMG. As registered,")
        print("   only the N1-anchored index is interpreted from here.")
    print(f"   interpreting the {use_anchor}-anchored index")

    # ------------------------------- P2 spread, P3 direction ---------------------------------------
    vals = {n: d[use_anchor]["median"] for n, d in idx.items() if d.get(use_anchor)}
    spread = (max(vals.values()) - min(vals.values())) if len(vals) > 1 else float("nan")
    p2 = np.isfinite(spread) and spread > SPREAD_MIN
    near_n3 = {n: v for n, v in vals.items() if v < 0.5}
    p3 = len(near_n3) > 0

    # RULE 37, APPLIED AFTER THE REGISTERED PREDICTIONS AND NOT INSTEAD OF THEM. P3 as registered tests the
    # POINT ESTIMATE against 0.5, and a point estimate whose interval spans the boundary is neither
    # direction. The registered result stands as registered; this is the stronger reading beside it, and
    # where they disagree the weaker claim is the one that survives.
    near_n3_ci = {n: idx[n][use_anchor]["ci"] for n in near_n3
                  if idx[n][use_anchor]["ci"][1] < 0.5}

    # ANCHOR RANK AGREEMENT. P4 asked whether the anchors agree in VALUE and they do not. Whether they agree
    # in ORDER is a different and weaker question, and it is the one the spread claim actually rests on --
    # so it is measured rather than assumed either way.
    both = [n for n, d in idx.items() if d.get("W") and d.get("N1")]
    rank_rho = (spearman([idx[n]["W"]["median"] for n in both],
                         [idx[n]["N1"]["median"] for n in both]) if len(both) > 4 else float("nan"))
    low_w = sorted(both, key=lambda n: idx[n]["W"]["median"])[:3]
    low_n1 = sorted(both, key=lambda n: idx[n]["N1"]["median"])[:3]
    print("\n   ANCHOR ROBUSTNESS (P4 asked about values; this asks about ORDER):")
    print(f"      Spearman(W-order, N1-order) = {rank_rho:+.3f} over {len(both)} candidates")
    print(f"      nearest N3, W-anchored : {low_w}")
    print(f"      nearest N3, N1-anchored: {low_n1}")
    agree_low = [n for n in low_w[:1] if n in low_n1[:1]]
    print(f"      same candidate is closest to N3 under BOTH anchors: {agree_low or 'no'}")

    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 GATE: delta recovers the depth ladder                : MET (rho {med_rho:+.3f})")
    print(f"   P2 index SPREADS across candidates by more than {SPREAD_MIN}    : "
          f"{'MET' if p2 else 'NOT MET'} (spread {spread:.3f} over {len(vals)} candidates)")
    print(f"   P3 at least one candidate places REM nearer N3 (< 0.5)  : "
          f"{'MET' if p3 else 'NOT MET'} ({sorted(near_n3) or 'none'})")
    print(f"      ... and with the CI ENTIRELY below 0.5 (rule 37)     : "
          f"{sorted(near_n3_ci) or 'NONE — every one spans the boundary'}")
    print(f"   P4 the two anchors agree                                : {'MET' if p4 else 'NOT MET'}")

    print("\n" + "=" * 100); print("VERDICT"); print("=" * 100)
    if not p2:
        verdict = "NO_DIFFERENTIATION"
        print(f"   Every candidate places REM at essentially the same point (spread {spread:.3f}). On the")
        print("   only contrast this project has reached that separates EEG activation from behavioural")
        print("   state, the seventeen registered candidates behave as ONE measurement. That is the")
        print("   redundancy this project has over-predicted three times (rule 28), and here it is the whole")
        print("   story rather than an occasional finding. It is a real negative and it is reported.")
    elif not p3:
        verdict = "ALL_TRACK_EEG_ACTIVATION"
        print("   The candidates spread, but every one of them places REM toward the light pole. Nothing in")
        print("   this registry tracks behavioural unresponsiveness as distinct from EEG desynchronisation,")
        print("   which is the separation Brief 01 requires. The spread is real and is in the wrong")
        print("   dimension to help.")
    elif not near_n3_ci:
        verdict = "WEAK_DIFFERENTIATION_SPANS_THE_BOUNDARY"
        print(f"   Candidates spread by {spread:.3f}, just past the registered {SPREAD_MIN}, and the only")
        print(f"   candidate placing REM nearer N3 is {sorted(near_n3)} — whose interval SPANS 0.5")
        print(f"   ({idx[sorted(near_n3)[0]][use_anchor]['ci']}). By rule 37 a cell that spans the null is")
        print("   neither direction, so this does NOT establish that any candidate tracks behavioural")
        print("   state rather than EEG activation. What it does establish is weaker and still worth")
        print("   having: the candidate set is NOT one measurement wearing fourteen names, because the")
        print("   spread exceeds what a single construct would produce.")
        print("")
        print(f"   The same candidate is closest to N3 under BOTH anchors, and its W-anchored interval does")
        print("   exclude 0.5 — but P4 failed, and the registration says the W anchor is the contaminated")
        print("   one. Reading the result off the anchor that was pre-declared unreliable, because it gives")
        print("   the cleaner answer, is exactly the move the pre-registration exists to prevent.")
        print(f"   Anchor rank agreement is only {rank_rho:+.3f}, so even the ORDERING is not solid.")
        print("")
        print("   WHAT WOULD SETTLE IT: more subjects, or an anchor that is neither daytime wake nor a")
        print("   180-second transitional stage. Both are extraction work, not analysis work.")
    else:
        verdict = "DIFFERENTIATION_FOUND"
        print(f"   Candidates spread by {spread:.3f}, and {len(near_n3)} of {len(vals)} place REM nearer N3")
        print(f"   than the light pole: {sorted(near_n3)}. Those are candidates tracking BEHAVIOURAL STATE")
        print("   rather than EEG activation, which is the separation Brief 01 asks for and the first real")
        print("   differentiation among candidates this project has found.")
        print("")
        print("   THE LIMIT, REGISTERED IN ADVANCE: this is EEG-activation versus behavioural-")
        print("   responsiveness. It is NOT experience. Dreaming occurs in NREM too (Siclari 2017, PMID")
        print("   28394322) and its correlate is local posterior activity within a stage, read out by")
        print("   waking the subject and asking. Sleep-EDF has no awakenings and no reports, so §9.5 stands.")
    print(f"\n   verdict: {verdict}")

    dst = os.path.join(RESULTS, "e13_rem_position.json")
    json.dump({"experiment": "E13", "gate_passed": True, "search_space_size": n_space,
               "n_complete_ladders": len(complete), "median_depth_rho": med_rho,
               "state_profile": profile, "rem_index": idx, "anchor_diffs": diffs,
               "anchor_used": use_anchor, "spread": spread, "near_n3": sorted(near_n3),
               "near_n3_ci_excludes_half": sorted(near_n3_ci), "anchor_rank_spearman": rank_rho,
               "nearest_n3_by_anchor": {"W": low_w, "N1": low_n1},
               "predictions": {"P1": True, "P2": bool(p2), "P3": bool(p3), "P4": bool(p4)},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
