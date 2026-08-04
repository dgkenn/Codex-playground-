#!/usr/bin/env python3
"""E21 — Discovery Challenge A, runnable for the first time: one representation across three drugs.

REGISTERED BEFORE ANY VitalDB FEATURE VALUE EXISTS. What has been inspected is the track index, the clinical
table and one raw waveform (to confirm 128 Hz and microvolt scaling) — the deposit's shape, not any
candidate's behaviour on it.

CHALLENGE A, in Brief 03's words: *the simplest representation predicting loss and recovery of responsiveness
across multiple anaesthetic drugs, while minimising the information it carries about which drug was used.*
Its stated acceptance condition is not an AUC — it is that **a drug-identity probe must NOT out-predict the
responsiveness model.** A marker that silently encodes the agent is a pharmacology detector wearing a
consciousness label.

**§5 and §9.22 recorded this as blocked since the plan was written, for want of a second identified drug.**
Chennu and ds005620 are both propofol; ds004541 does not record its agent at all. VitalDB ends that:

    single-agent cases carrying raw EEG (BIS/EEG1_WAV) and BIS, under General anaesthesia
        sevoflurane  1,493      propofol  1,008      desflurane  462

THE CONTRAST IS EMERGENCE, NOT INDUCTION, AND THAT IS FORCED BY THE DATA. `anestart` is negative in 91.8 % of
cases — the BIS sensor goes on after the patient is already asleep, so induction is simply not recorded.
`aneend` sits at a median 9,770 s into the record. So the responsive/unresponsive contrast is deep
maintenance against post-emergence, anchored on `aneend`.

    unresponsive   aneend − 1200 s, − 600 s     deep in maintenance
    responsive     aneend + 180 s, + 300 s      after the agents are off

The positive offsets stop at +300 s because they must: the EEG track ends a median of only +544 s after
`aneend`, and in one of six cases sampled it ended 860 s BEFORE it. A first run at +300/+600 s errored on
roughly half the positive windows with "runs past the record". **This deposit records the middle of an
anaesthetic well and both of its edges poorly** — the sensor goes on after induction and comes off around
emergence — and the responsive block is therefore short, close to the transition, and the least reliable
part of the design.

**That second block is a PROXY and is labelled as one.** VitalDB marks no return of consciousness; `aneend`
is when the anaesthetic stops, and responsiveness returns some minutes later. Individual patients will be
mislabelled at the margin, which costs power and does not bias the drug comparison, because the same proxy is
applied identically in all three arms.

REGISTERED PREDICTIONS:
    P1  MACHINERY GATE. `BIS/BIS` must rise from the unresponsive block to the responsive block in >= 80 % of
        cases. **Its limitation is stated rather than glossed: BIS is computed from the same EEG**, so this
        is not an independent confirmation of state — it is the clinical device's own call, used to check
        that the epochs mean what the timestamps say. It gates the machinery and it is never the outcome.
    P2  PRIMARY, PER ARM. `exponent_high` separates unresponsive from responsive within subject, with a
        subject-clustered CI excluding 0.5, **in each of the three drug arms separately.**
    P3  DRUG INVARIANCE — the "across drugs" half of the challenge. The candidate's |AUC − 0.5| differs by
        no more than 0.15 between its best and worst arm. A representation that works under propofol and
        fails under desflurane is not what Challenge A asks for.
    P4  THE DRUG-IDENTITY PROBE, WHICH IS THE ACTUAL ACCEPTANCE CONDITION AND THE ONLY PREDICTION HERE THAT
        CAN FAIL INTERESTINGLY. Using the same windows, **held at constant state — the unresponsive block
        only, so state differences cannot leak into the probe** — can a candidate tell sevoflurane from
        desflurane? The probe's |AUC − 0.5| must be BELOW the responsiveness |AUC − 0.5|. If the drug is
        more legible in the EEG than the state is, the representation encodes pharmacology and **Challenge A
        is failed however good P2 looks.**

    FALSIFICATION: P4 not met. That is a failure of the challenge, not of the experiment, and it is the
    outcome the challenge was designed to detect.

SCOPE AND LIMITS, none of which a larger n repairs.
  * **Post-emergence windows are contaminated by arousal, movement, coughing and extubation.** That is
    genuine physiology and genuine artefact together, and it inflates any awake-vs-anaesthetised separation.
    VitalDB carries `BIS/EMG`, a real muscle channel, which would quantify it directly; it is NOT streamed
    here and that is a stated gap rather than an oversight.
  * One site, one monitor, one country. A frontal two-channel BIS strip, so `uce_v1` is unavailable, and
    128 Hz sampling puts `exponent_gamma` (50–90 Hz) above Nyquist — NaN by design.
  * Cases are selected deterministically by ascending case id within each arm, never by result.
  * **AN EXCLUSION THAT IS NOT RANDOM, ADDED AFTER THE FIRST STREAM AND BEFORE ANY RESULT WAS READ.** A
    substantial fraction of cases have no usable window at `aneend + 180/+300 s` — the record simply ends —
    and those rows arrive as errors rather than data. **A case therefore enters the responsive block only if
    its monitoring continued past emergence, which is not independent of the case**: longer monitoring goes
    with longer, larger operations and with slower wake-ups. Error-catalogue rule 14 requires exclusions to
    be reported and checked for outcome-relatedness, so the surviving fraction is reported per arm, and any
    arm-to-arm difference in it is a confound for P3 rather than a nuisance. If the fractions differ
    materially between arms, P3 is comparing different populations and must be read that way.
  * Surgical populations differ by agent — desflurane and sevoflurane are not randomly assigned. Age, sex,
    BMI, ASA and emergency status are carried in the table for a later adjusted analysis and are **not**
    adjusted for here; P3 and P4 are comparisons of a marker's behaviour, not causal claims about drugs.

--------------------------------------------------------------------------------------------------------
OUTCOME, ADDED AFTER THE RUN. **P1 FAILED: BIS rose from the unresponsive block to the responsive block in
1 of 22 cases (4.5 %), against a registered floor of 80 %.** P2, P3 and P4 were therefore never computed,
which is rule 31 working as intended — a downstream verdict on a failed precondition is absent, not negative.
**This experiment is CLOSED at its gate and its result is not revised.** What follows is the diagnosis, kept
here because the failure is the informative part.

The gate failed for two reasons, both defects in the design above and neither in any candidate:

  1. `BIS/BIS` writes a literal `0.0` while the sensor is detached, and 0 is inside the index's valid range,
     so it reads as "isoelectric" — the deepest possible state. 171 of 348 decoded windows carried it, and
     the proportion climbs from 11 % at `aneend−1200` to 92 % at `aneend+300`, because the strip comes off
     with the anaesthetic. The responsive block therefore scored as *more* suppressed than maintenance and
     the gate inverted. `BIS/SQI` reads exactly 0 over precisely those spans and is a positive test for the
     off-state; it was available and was not streamed.
  2. **`aneend` lags emergence rather than marking it.** Measured on four cases: BIS is already 68–86 at
     `aneend−300`/`−120` while deep maintenance sits at 24–46. `aneend` is charted when the anaesthetic
     record is closed, after the patient is responding. The registered offsets thus put the "responsive"
     block after the monitor was unplugged — which is also why those offsets carried most of the decode
     errors, a signal the scope note above noticed and misread as short recordings alone.

Neither defect can be repaired by moving the offsets, because both say the same thing: **a window's arm must
be defined by the depth index, not by its sign relative to a charted time.** That is a different design, so
it is a different experiment — E22 — registered fresh against a re-extracted table (`VitalDBGridAdapter`,
`bsde/scripts/stream_vitaldb_grid.py`), with the arms defined by BIS under published clinical thresholds and
a different machinery gate. Editing this file's predictions to match what the data turned out to support is
exactly the move the programme's constraints forbid, and it is not taken.

An earlier bug in this file is recorded for completeness: the first version selected epochs by `meta_epoch`,
a column the VitalDB adapter does not emit (ds004541's does, and the two were conflated). Every test matched
the empty string and the gate saw 0 of 0 cases. It FAILED rather than passing vacuously, which is the
behaviour rule 5 asks for — a silently-empty filter that defaulted to "pass" would have been invisible.
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
from bsde.verifier.stats import directional_auc, cluster_bootstrap_ci                  # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "vitaldb_challenge_a.csv")

ARMS = ("propofol", "sevoflurane", "desflurane")
# Selected by NUMERIC OFFSET, not by an epoch label. The first version keyed on `meta_epoch`, which the
# VitalDB adapter does not emit -- ds004541's does, and the two were conflated. Every epoch test then matched
# the empty string, the gate saw 0 of 0 cases, and it FAILED rather than passing vacuously. That is the gate
# behaving correctly: 0/0 is visibly wrong, where a silently-empty filter that defaulted to "pass" would not
# have been (rule 5).
UNRESPONSIVE_OFF = (-1200.0, -600.0)
RESPONSIVE_OFF = (180.0, 300.0)
PRIMARY = "exponent_high"
GATE_MIN_FRACTION = 0.80
INVARIANCE_TOL = 0.15
MIN_PER_ARM = 15
PROBE_PAIR = ("sevoflurane", "desflurane")
REPORT = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "wpli_alpha", "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1",
          "emg_beta_gamma_fraction", "emg_kurtosis")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main() -> int:
    seed_registry()
    print("E21 — Challenge A: one representation across propofol, sevoflurane and desflurane")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    if not os.path.exists(TABLE):
        print(f"\n   *** {os.path.basename(TABLE)} absent — the VitalDB stream has not produced it yet.")
        print("   Registered order of evaluation, fixed here and not re-openable:")
        print("     P1 GATE   BIS rises unresponsive -> responsive in >= 80% of cases")
        print("     P2        exponent_high separates the blocks, CI excluding 0.5, IN EACH ARM")
        print(f"     P3        |AUC-0.5| differs by <= {INVARIANCE_TOL} between best and worst arm")
        print("     P4        the drug-identity probe (sevo vs des, UNRESPONSIVE block only) must NOT")
        print("               out-predict responsiveness -- the challenge's actual acceptance condition")
        return 2

    rows = [r for r in csv.DictReader(open(TABLE, newline="")) if r.get("status") == "ok"]
    arm_of = {r["recording_id"]: r.get("meta_requested_agent", "") for r in rows}
    if not any(np.isfinite(_f(r.get("meta_offset_s"))) for r in rows):
        print("   *** the table carries no meta_offset_s; the epoch filter cannot be applied.")
        return 1
    ep = np.array([_f(r.get("meta_offset_s")) for r in rows])
    subj = np.array([r.get("subject", "") for r in rows])
    arm = np.array([arm_of.get(r["recording_id"], "") for r in rows])
    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)     # noqa: E731
    rng = np.random.default_rng(20260730)
    keep = np.isin(ep, UNRESPONSIVE_OFF + RESPONSIVE_OFF)
    y = np.isin(ep, RESPONSIVE_OFF).astype(float)
    print(f"   rows {len(rows)}   patients {len(set(subj))}   "
          + "  ".join(f"{a}={len({s for s, x in zip(subj, arm) if x == a})}" for a in ARMS))

    # ---- P1 gate ----
    print("\n" + "=" * 100)
    print(f"P1 — GATE: BIS rises from unresponsive to responsive in >= {GATE_MIN_FRACTION:.0%} of cases")
    print("=" * 100)
    bis = col("meta_bis") if "meta_bis" in (rows[0] if rows else {}) else col("bis_mean")
    hits = n = 0
    for s in np.unique(subj):
        u = bis[(subj == s) & np.isin(ep, UNRESPONSIVE_OFF)]
        r_ = bis[(subj == s) & np.isin(ep, RESPONSIVE_OFF)]
        u, r_ = u[np.isfinite(u)], r_[np.isfinite(r_)]
        if u.size and r_.size:
            n += 1
            hits += int(r_.mean() > u.mean())
    frac = hits / n if n else float("nan")
    p1 = n >= 10 and np.isfinite(frac) and frac >= GATE_MIN_FRACTION
    print(f"   BIS rose in {hits}/{n} cases ({frac:.1%})   {'PASSED' if p1 else '*** FAILED'}")
    print("   NOTE, as registered: BIS is computed from the same EEG, so this checks that the epochs mean")
    print("   what the timestamps say. It is not independent confirmation of state and is never the outcome.")
    if not p1:
        print("\n   Nothing else is reported (rule 31: absent, not negative).")
        json.dump({"experiment": "E21", "gate_passed": False, "bis_rise_fraction": frac, "n": n},
                  open(os.path.join(RESULTS, "e21_challenge_a.json"), "w"), indent=2)
        return 1

    # ---- P2 per arm ----
    print("\n" + "=" * 100)
    print("P2 — RESPONSIVENESS, PER DRUG ARM (signed AUC, subject-clustered CI)")
    print("=" * 100)
    d = REGISTRY.get(PRIMARY).predicted("unconscious_vs_awake") or "higher"
    per_arm, x = {}, col(PRIMARY)
    print(f"   {'arm':14s} {'n':>4s} {'AUC (unresponsive vs responsive)':>34s} {'|AUC-.5|':>9s}")
    for a in ARMS:
        m = keep & (arm == a) & np.isfinite(x)
        npat = len(set(subj[m]))
        if npat < MIN_PER_ARM or len(np.unique(y[m])) < 2:
            print(f"   {a:14s} {npat:4d}   too few patients; not reported")
            continue
        # Direction: unconscious is the UNRESPONSIVE block, so score y=0 as the declared-unconscious side.
        au = directional_auc(1 - y[m], x[m], d)
        lo, hi = cluster_bootstrap_ci(lambda i: directional_auc(1 - y[m][i], x[m][i], d),
                                      subj[m], rng, reps=2000)[:2]
        per_arm[a] = {"auc": float(au), "ci": [float(lo), float(hi)], "abs": float(abs(au - 0.5)),
                      "n_patients": npat}
        print(f"   {a:14s} {npat:4d} {au:14.3f} [{lo:.3f}, {hi:.3f}] {abs(au - 0.5):9.3f}")
    p2 = bool(per_arm) and all(v["ci"][0] > 0.5 for v in per_arm.values()) and len(per_arm) == len(ARMS)

    # ---- P3 invariance ----
    spread = (max(v["abs"] for v in per_arm.values()) - min(v["abs"] for v in per_arm.values())
              if len(per_arm) > 1 else float("nan"))
    p3 = np.isfinite(spread) and spread <= INVARIANCE_TOL

    # ---- P4 drug-identity probe ----
    print("\n" + "=" * 100)
    print(f"P4 — DRUG-IDENTITY PROBE: {PROBE_PAIR[0]} vs {PROBE_PAIR[1]}, UNRESPONSIVE BLOCK ONLY")
    print("=" * 100)
    pm = np.isin(ep, UNRESPONSIVE_OFF) & np.isin(arm, PROBE_PAIR) & np.isfinite(x)
    probe = {}
    if len(set(subj[pm])) >= 2 * MIN_PER_ARM:
        yd = (arm[pm] == PROBE_PAIR[1]).astype(float)
        pa = max(directional_auc(yd, x[pm], "higher"), directional_auc(yd, x[pm], "lower"))
        plo, phi = cluster_bootstrap_ci(
            lambda i: max(directional_auc(yd[i], x[pm][i], "higher"),
                          directional_auc(yd[i], x[pm][i], "lower")), subj[pm], rng, reps=2000)[:2]
        probe = {"auc": float(pa), "ci": [float(plo), float(phi)], "abs": float(abs(pa - 0.5))}
        print(f"   drug identity from {PRIMARY}: |AUC-0.5| = {abs(pa - 0.5):.3f} "
              f"(AUC {pa:.3f} [{plo:.3f}, {phi:.3f}])")
        print("   NOTE: both orientations are tried and the larger taken, which BIASES THIS PROBE UPWARD --")
        print("   deliberately, because the probe is the thing that must FAIL to be small, so the")
        print("   conservative direction is to make it easy to look large.")
    worst_state = min((v["abs"] for v in per_arm.values()), default=float("nan"))
    p4 = bool(probe) and np.isfinite(worst_state) and probe["abs"] < worst_state
    if probe:
        print(f"   responsiveness |AUC-0.5|, worst arm: {worst_state:.3f}")
        print(f"   -> drug identity is {'LESS' if p4 else 'MORE'} legible than state")

    # ---- verdict ----
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    print(f"   P1 GATE BIS rises                             : MET ({frac:.1%})")
    print(f"   P2 separates the blocks in EVERY arm          : {'MET' if p2 else 'NOT MET'}")
    print(f"   P3 |AUC-0.5| spread across arms <= {INVARIANCE_TOL}      : "
          f"{'MET' if p3 else 'NOT MET'} (spread {spread:.3f})")
    print(f"   P4 drug identity does NOT out-predict state   : {'MET' if p4 else 'NOT MET'}")

    print("\n" + "=" * 100); print("VERDICT ON CHALLENGE A"); print("=" * 100)
    if not p4 and probe:
        verdict = "CHALLENGE_A_FAILED_DRUG_IS_MORE_LEGIBLE_THAN_STATE"
        print(f"   The drug is more legible in this representation than the state is "
              f"({probe['abs']:.3f} vs {worst_state:.3f}).")
        print("   That is the failure Challenge A was written to detect: a pharmacology detector wearing a")
        print("   consciousness label. It fails HOWEVER GOOD the responsiveness numbers look.")
    elif p2 and p3 and p4:
        verdict = "CHALLENGE_A_MET"
        print("   One representation separates responsiveness in all three drug arms, with comparable")
        print("   strength, while carrying less drug information than state information. That is what the")
        print("   challenge asks for, on emergence rather than induction, at one site, with a proxy label.")
    else:
        verdict = "PARTIAL"
        print("   Not all conditions met; see the per-prediction lines above. The challenge is not met and")
        print("   is not refuted -- the drug-identity probe is the acceptance condition and it is reported")
        print("   beside, not instead of, the responsiveness numbers.")
    print(f"\n   verdict: {verdict}")
    print("\n   NOT ADDRESSED HERE: post-emergence windows carry arousal, movement and extubation artefact.")
    print("   VitalDB's BIS/EMG channel would quantify it and is not streamed -- a stated gap.")

    dst = os.path.join(RESULTS, "e21_challenge_a.json")
    json.dump({"experiment": "E21", "gate_passed": True, "bis_rise_fraction": frac,
               "per_arm": per_arm, "invariance_spread": float(spread), "drug_identity_probe": probe,
               "predictions": {"P1": True, "P2": p2, "P3": p3, "P4": p4},
               "verdict": verdict}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
