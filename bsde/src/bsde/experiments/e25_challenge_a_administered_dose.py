#!/usr/bin/env python3
"""E25 — Discovery Challenge A, third attempt: the depth axis is the drug that was GIVEN.

REGISTERED BEFORE `vitaldb_agents.csv` EXISTS. The join that produces it is running as this file is written
and no dose value has been read. What has been read of the grid table is BIS, SQI, EMG and the window
timings — the machinery columns, in the course of closing E22 — and no candidate value from it has been read
at any point.

WHY THERE IS A THIRD ATTEMPT, AND WHY IT IS NOT THE SAME QUESTION RE-ASKED UNTIL IT PASSES.

    E21 defined its arms by a charted time. It failed because `BIS/BIS` writes 0.0 with the sensor off and
    `aneend` lags emergence.
    E22 defined its arms by the depth index. It failed because **every BIS >= 80 window in this deposit is a
    facial-EMG artefact** — P(BIS >= 80) is 0.0 % in EMG deciles 1 through 8 and 27.6 % in decile 10, and
    filtering the light arm to EMG <= 35 leaves 5 rows across 4 patients.

Both failures share one cause: **the label came from the signal, or from a monitor computed from the
signal.** E25 does not re-ask E22's question with a kinder threshold. It changes the axis to one the EEG
cannot contaminate — the anaesthetic that was administered — and it therefore also changes what is being
claimed, from *tracks consciousness* to *tracks anaesthetic dose*. That is a narrower claim and it is
stated as the narrower one throughout.

WHAT MAKES THE AXIS WORTH HAVING. `Primus/MAC` is present in 6,338 cases. MAC — minimum alveolar
concentration, age-adjusted — is the standard normalised potency scale for volatile anaesthetics: 1.0 MAC is
by definition the concentration at which half of patients do not move to a skin incision. **Sevoflurane and
desflurane land on that one axis with no fitting on our part**, which is exactly the cross-drug x-axis
Challenge A needs, supplied by pharmacology rather than by us.

THE TWO ARMS, AND WHY THEY ARE NOT POOLED.

    volatile     depth = `Primus/MAC`            cases with a volatile agent present
    propofol     depth = `Orchestra/PPF20_CE`    TIVA cases, effect-site concentration in ug/mL

MAC and effect-site concentration are different quantities in different units. **They are never pooled into
one regression.** The cross-drug comparison is of ASSOCIATION STRENGTH in two arms, never of a shared
threshold, and P3 is worded accordingly.

REGISTERED PREDICTIONS, evaluated in this order. A failed gate makes the downstream verdict ABSENT, not
negative (rule 31).

    P1  MACHINERY GATE, in three parts, using no candidate at all.
        (a) **DOSE MUST VARY WITHIN THE PATIENT — error-catalogue rule 32, for the third time in this
            deposit.** At least `MIN_PATIENTS` patients per arm must have at least `MIN_DISTINCT` distinct
            dose values across at least `MIN_POINTS` windows. A patient held at one steady concentration all
            case contributes nothing to a within-subject dose-response, and averaging their undefined
            correlation in as a zero would dilute the estimate with subjects who could not have contributed.
        (b) COVERAGE — both arms must clear that floor. Challenge A is a cross-drug claim.
        (c) **THE MUSCLE GATE, WHICH IS HERE BECAUSE E22 DIED OF ITS ABSENCE.** The analysis runs on windows
            with `BIS/EMG <= EMG_MAX` only, and at least `MIN_PATIENTS` per arm must survive that filter.
            The dose axis cannot be contaminated by EMG — it is a vaporiser reading — but a CANDIDATE can
            be, and EMG rises as anaesthetic falls, so an EMG-driven candidate would correlate with dose for
            entirely the wrong reason. The filter is applied to the analysis, not merely reported.

    P2  THE PRIMARY. `exponent_high`'s within-subject Spearman correlation with dose — the mean over
        patients of each patient's own rank correlation — with a subject-clustered CI excluding zero, in
        each arm separately.

    P3  CROSS-DRUG CONSISTENCY, which is the "across drugs" half of the challenge. The correlation must
        have **the same sign** in both arms, and the smaller |rho| must be at least half the larger. Sign
        first and explicitly: error-catalogue rule 16 says that when two arms of the same test disagree in
        sign, the definition is doing the work rather than the biology, and a magnitude criterion alone
        would let a sign flip through as "a weak effect in one arm".

    P4  THE DRUG-IDENTITY PROBE — THE ACCEPTANCE CONDITION, and MAC is what finally makes it a fair test.
        **Within the volatile arm only, at matched MAC**, can the candidate tell sevoflurane from
        desflurane? Matching is by MAC decile, so the comparison holds pharmacological depth constant on a
        scale both agents share — which is the comparison E22 could not make, since it had no common depth
        axis and had to hold "state" constant using a label that turned out to be muscle. The probe's
        |AUC - 0.5| must be BELOW the depth association's strength, expressed on the same scale by
        converting the within-subject rho to a comparable |AUC - 0.5| via the standard rank identity
        AUC = (rho + 1) / 2 for a two-group comparison. **If the drug is more legible than the depth, the
        representation encodes pharmacology and Challenge A is failed however good P2 looks.**

    P5  THE PLACEBO, AND IT GATES THE VERDICT (rule 34). Same estimator, dose replaced by
        `Orchestra/RFTN20_CE` — remifentanil effect-site concentration. Remifentanil is co-administered,
        rises and falls with the phase of the case, and is a mu-opioid with a far weaker EEG signature than
        any hypnotic at clinical doses. So a candidate correlating with remifentanil as strongly as with the
        hypnotic is tracking the phase of the operation, not hypnotic depth. **The placebo |rho| must be
        below half the primary's, and this is a COMPARISON against the real effect rather than an absolute
        threshold** — rule 37, which was paid for by a placebo check that asked whether the placebo
        attenuated "a lot" instead of "more than the variable of interest".
            Its limitation, stated before it runs: remifentanil is not EEG-silent, and at high doses it
        does slow the EEG. That makes this placebo conservative — it can withdraw a real effect, and it
        cannot manufacture one.

    P6  THE OPIOID COVARIATE, reported and not gating. Opioids substantially reduce MAC requirement, so a
        case at 0.7 MAC on high remifentanil is not lighter than one at 1.0 MAC without it. P2 recomputed
        within remifentanil terciles says whether the dose association is an artefact of co-administration.

    NOTE ON THE OTHER CANDIDATES IN THE TABLES. The primary is one pre-declared candidate, so the headline
    is one test. Every other candidate is printed for CONTEXT with an UNADJUSTED interval, and a claim from
    the best of them would first have to pass `verifier/multiplicity.py`. None is made here.

    FALSIFICATION: P2 fails in either arm, or P3's signs disagree, or P4 fails, or P5 fails. Each is a
    result, and P4 failing is the specific outcome Challenge A was designed to detect.

SCOPE AND LIMITS, none of which a larger n repairs.
  * **DOSE IS NOT CONSCIOUSNESS, and this is the limit that matters most.** MAC and effect-site
    concentration are what was administered; individual sensitivity varies severalfold; a patient at 1.0 MAC
    and a patient at 0.6 MAC may be equally unaware. Everything here is a claim about tracking anaesthetic
    dose. **No sentence from this experiment may be written as a claim about consciousness**, which is the
    programme's standing constraint and is also simply what the data supports.
  * **The two arms are not on a common scale** and are never pooled. P3 compares association strengths.
  * **Effect-site concentration is a MODEL output, not a measurement.** `Orchestra/PPF20_CE` is a
    pharmacokinetic simulation from the infusion pump given weight and age; it is not a blood sample. Its
    errors are systematic within a patient, which is the direction that most affects a within-subject
    correlation, and there is no way to check it from this deposit.
  * **MAC is inspired-agent-derived and lags effect site.** The vaporiser leads the brain by minutes, so a
    within-subject correlation against a changing MAC is attenuated by that lag. Attenuation is toward the
    null, so it costs power rather than validity.
  * **Only maintenance is covered.** The strip goes on after induction and comes off before emergence
    (`ingestion/vitaldb.py`, corrected 2026-07-30), so the dose range sampled here is the clinical
    maintenance range, not the full span from awake to deep.
  * One site, one monitor, two frontal channels, 128 Hz: `exponent_gamma` is above Nyquist, `uce_v1` needs
    a posterior region this montage lacks.
  * Cases are taken in ascending case id, never selected by result.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                          # noqa: E402
from bsde.candidates.seed import seed_registry                                          # noqa: E402
from bsde.verifier.stats import (auc_abs, cluster_bootstrap_ci,                          # noqa: E402
                                 n_evaluable_spearman, within_subject_spearman)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
OUT = os.path.join(RESULTS, "e25_challenge_a_dose.json")

ARMS = (("volatile", "mac"), ("propofol", "ppf_ce"))
EMG_MAX = 35.0
"""The muscle gate. 35 is the top of the tight EMG band this deposit sits in during maintenance -- deciles 1
through 8 span 20.4 to 28.6 and decile 9 ends at 32.3 -- so it admits normal maintenance windows and
excludes the tail where every BIS >= 80 artefact lived. Declared before any dose value was read."""
MIN_POINTS = 4
MIN_DISTINCT = 3
MIN_PATIENTS = 20
PRIMARY = "exponent_high"
CROSS_ARM_MIN_RATIO = 0.50
PLACEBO_MAX_RATIO = 0.50
PROBE_DECILES = 10
GATE_MIN_CASES = 240
"""A floor on JOINED CASES, not on rows, and it is corrected from a row floor after the correction was
needed. E25 was first written with `GATE_MIN_ROWS = 1500`, copied from E22. The agent join produces roughly
27 rows per case, so 60 of the 250 cases already cleared 1,500 rows and the experiment ran on a quarter of
the cohort and printed `P1 *** FAILED` -- the propofol arm had 17 evaluable patients against a floor of 20,
for no reason except that the join had not reached them yet. **A coverage gate must be floored on the
quantity it is counting.** Nothing was contaminated: P1 reads no candidate value and that partial run
reported nothing but patient counts, which is the same class of information the E22 amendment was licensed
on. It is recorded here rather than quietly overwritten."""
REPORT = ("exponent_high", "exponent_low", "whole_head_exponent", "relative_delta_power",
          "relative_alpha_power", "lempel_ziv", "spectral_entropy", "spectral_edge_95",
          "multiscale_entropy_slope", "pac_slow_alpha", "critical_slowing_ar1")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _registered_order() -> None:
    print("   Registered order of evaluation, fixed here and not re-openable:")
    print(f"     P1 GATE  dose must VARY within patient (rule 32), both arms covered, and >= "
          f"{MIN_PATIENTS} patients/arm surviving the EMG <= {EMG_MAX:.0f} muscle filter")
    print(f"     P2       {PRIMARY}'s within-subject Spearman with dose, CI excluding 0, in EACH arm")
    print(f"     P3       same SIGN in both arms and the smaller |rho| >= "
          f"{CROSS_ARM_MIN_RATIO:.0%} of the larger")
    print("     P4       sevo vs des at MATCHED MAC must not out-predict depth — the acceptance condition")
    print(f"     P5 GATE  remifentanil placebo |rho| must be < {PLACEBO_MAX_RATIO:.0%} of the primary's")
    print("     P6       remifentanil terciles — reported, not gating")


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    grid = os.path.abspath(args[args.index("--grid") + 1]) if "--grid" in args else GRID
    agents = os.path.abspath(args[args.index("--agents") + 1]) if "--agents" in args else AGENTS
    seed_registry()
    print("E25 — Challenge A on the ADMINISTERED dose axis (MAC and propofol effect-site concentration)")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    print("   CLAIM SCOPE: this experiment is about tracking anaesthetic DOSE. Nothing here is a claim")
    print("   about consciousness, and no sentence from it may be written as one.")
    if not (os.path.exists(grid) and os.path.exists(agents)):
        missing = [p for p in (grid, agents) if not os.path.exists(p)]
        print(f"\n   *** absent: {[os.path.basename(p) for p in missing]}")
        _registered_order()
        return 2

    dose_by_rid = {r["recording_id"]: r for r in csv.DictReader(open(agents, newline=""))}
    rows = [r for r in csv.DictReader(open(grid, newline=""))
            if r.get("status") == "ok" and r["recording_id"] in dose_by_rid]
    n_cases = len({r.get("meta_caseid", "") for r in rows})
    if n_cases < GATE_MIN_CASES:
        print(f"\n   *** {n_cases} joined cases ({len(rows)} rows), below the registered floor of "
              f"{GATE_MIN_CASES} cases. The join is still running; nothing is reported.")
        _registered_order()
        return 2

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)                    # noqa: E731
    dcol = lambda k: np.array([_f(dose_by_rid[r["recording_id"]].get(k, "")) for r in rows], float)  # noqa: E731,E501
    subj = np.array([r.get("subject", "") for r in rows])
    emg = col("meta_emg")
    sensor_off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    agents_present = np.array([r.get("meta_agents_present", "") for r in rows])
    mac, ppf, rftn = dcol("mac"), dcol("ppf_ce"), dcol("rftn_ce")
    sevo, des = dcol("insp_sevo"), dcol("insp_des")
    dose = {"mac": mac, "ppf_ce": ppf}

    volatile = np.array(["sevoflurane" in g or "desflurane" in g for g in agents_present])
    arm_mask = {"volatile": volatile, "propofol": ~volatile}
    clean = ~sensor_off & np.isfinite(emg) & (emg <= EMG_MAX)

    print(f"\n   joined {len(rows)} rows, {len(set(subj))} patients")
    print(f"   windows surviving the EMG <= {EMG_MAX:.0f} muscle filter: {int(clean.sum())} "
          f"({clean.mean():.1%}), {len(set(subj[clean]))} patients")
    print(f"   dose columns finite: MAC {int(np.isfinite(mac).sum())}, "
          f"propofol Ce {int(np.isfinite(ppf).sum())}, remifentanil Ce {int(np.isfinite(rftn).sum())}")

    # ------------------------------------------------------------------ P1
    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE (no candidate: dose variation, coverage, and the muscle filter)")
    print("=" * 100)
    x_dummy = np.arange(len(rows), dtype=float)          # a stand-in so the counter needs no candidate
    p1_cells, cov = {}, []
    print(f"   {'arm':12s} {'dose':8s} {'pats (any)':>11s} {'pats (dose varies)':>20s} "
          f"{'pats (+ EMG filter)':>21s}")
    for arm, key in ARMS:
        m = arm_mask[arm] & ~sensor_off
        n_any = len(set(subj[m]))
        n_var = n_evaluable_spearman(x_dummy[m], dose[key][m], subj[m], MIN_POINTS, MIN_DISTINCT)
        mc = m & clean
        n_clean = n_evaluable_spearman(x_dummy[mc], dose[key][mc], subj[mc], MIN_POINTS, MIN_DISTINCT)
        p1_cells[arm] = {"dose_column": key, "n_any": n_any, "n_dose_varies": n_var,
                         "n_after_emg_filter": n_clean}
        cov.append(n_clean >= MIN_PATIENTS)
        print(f"   {arm:12s} {key:8s} {n_any:11d} {n_var:20d} {n_clean:21d}")
    p1 = all(cov)
    print(f"\n   floor is {MIN_PATIENTS} patients per arm in the final column   "
          f"{'PASSED' if p1 else '*** FAILED'}")
    print("   (rule 32: a patient held at one steady concentration has no within-subject dose-response and")
    print("    is excluded rather than averaged in as a zero — that exclusion is the middle column)")
    state = {"experiment": "E25", "emg_max": EMG_MAX, "p1": {"arms": p1_cells, "passed": bool(p1)}}
    if not p1:
        print("\n   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    # ------------------------------------------------------------------ P2
    rng = np.random.default_rng(20260730)
    print("\n" + "=" * 100)
    print(f"P2 — PRIMARY: {PRIMARY}'s within-subject Spearman with administered dose, per arm")
    print("=" * 100)
    x = col(PRIMARY)
    per_arm = {}
    print(f"   {'arm':12s} {'pats':>5s} {'rows':>6s} {'within-subject rho':>20s} {'95% CI':>22s}")
    for arm, key in ARMS:
        m = arm_mask[arm] & clean & np.isfinite(x) & np.isfinite(dose[key])
        n_eval = n_evaluable_spearman(x[m], dose[key][m], subj[m], MIN_POINTS, MIN_DISTINCT)
        if n_eval < MIN_PATIENTS:
            print(f"   {arm:12s} {n_eval:5d} {int(m.sum()):6d}   too few evaluable patients; not reported")
            continue
        xm, zm, sm = x[m], dose[key][m], subj[m]
        rho = within_subject_spearman(xm, zm, sm, MIN_POINTS, MIN_DISTINCT)
        lo, hi, _ = cluster_bootstrap_ci(
            lambda i: within_subject_spearman(xm[i], zm[i], sm[i], MIN_POINTS, MIN_DISTINCT),
            sm, rng, reps=2000)
        per_arm[arm] = {"rho": rho, "ci": [float(lo), float(hi)], "n_patients": n_eval,
                        "n_rows": int(m.sum()), "dose_column": key}
        print(f"   {arm:12s} {n_eval:5d} {int(m.sum()):6d} {rho:20.3f} "
              f"{f'[{lo:+.3f}, {hi:+.3f}]':>22s}")
    bad = [a for a, d in per_arm.items() if not (d["ci"][0] > 0 or d["ci"][1] < 0)]
    p2 = bool(len(per_arm) == len(ARMS) and not bad)
    print(f"\n   P2 {'PASSED' if p2 else '*** FAILED'}"
          + (f" — CI includes zero in {bad}" if bad else
             ("" if p2 else " — an arm was not reportable")))
    state["p2"] = {"per_arm": per_arm, "passed": p2}

    # ------------------------------------------------------------------ P3
    print("\n" + "=" * 100)
    print("P3 — CROSS-DRUG CONSISTENCY: same SIGN in both arms, smaller |rho| >= half the larger")
    print("=" * 100)
    if len(per_arm) < 2:
        print("   fewer than two reportable arms — ABSENT, not failed (rule 31).")
        p3 = None
    else:
        rhos = {a: d["rho"] for a, d in per_arm.items()}
        # A CI spanning zero is neither direction and cannot satisfy a directional criterion (rule 37).
        signs = {a: (0 if (per_arm[a]["ci"][0] <= 0 <= per_arm[a]["ci"][1])
                     else int(np.sign(per_arm[a]["rho"]))) for a in per_arm}
        same_sign = len({s for s in signs.values()}) == 1 and 0 not in signs.values()
        mags = [abs(v) for v in rhos.values()]
        ratio = min(mags) / max(mags) if max(mags) > 0 else float("nan")
        p3 = bool(same_sign and np.isfinite(ratio) and ratio >= CROSS_ARM_MIN_RATIO)
        for a in per_arm:
            print(f"   {a:12s} rho {rhos[a]:+.3f}   sign {signs[a]:+d}"
                  + ("  (interval spans zero — counted as NO direction)" if signs[a] == 0 else ""))
        print(f"   same sign: {same_sign}    magnitude ratio {ratio:.1%} "
              f"(floor {CROSS_ARM_MIN_RATIO:.0%})")
        print(f"   P3 {'PASSED' if p3 else '*** FAILED'}")
        state["p3"] = {"rhos": rhos, "signs": signs, "ratio": float(ratio), "passed": p3}
    if p3 is None:
        state["p3"] = {"passed": None, "reason": "fewer than two reportable arms"}

    # ------------------------------------------------------------------ P4
    print("\n" + "=" * 100)
    print("P4 — DRUG-IDENTITY PROBE: sevoflurane vs desflurane AT MATCHED MAC (acceptance condition)")
    print("=" * 100)
    print("   Matching is by MAC decile, so pharmacological depth is held constant on a scale both agents")
    print("   share. This is the comparison E22 could not make: it had no common depth axis and had to")
    print("   hold 'state' constant with a label that turned out to be muscle.")
    is_sevo = np.isfinite(sevo) & (sevo > 0) & ~(np.isfinite(des) & (des > 0))
    is_des = np.isfinite(des) & (des > 0) & ~(np.isfinite(sevo) & (sevo > 0))
    pm = clean & np.isfinite(mac) & np.isfinite(x) & (is_sevo | is_des)
    n_s, n_d = len(set(subj[pm & is_sevo])), len(set(subj[pm & is_des]))
    print(f"\n   sevoflurane patients {n_s}   desflurane patients {n_d}   rows {int(pm.sum())}")
    if min(n_s, n_d) < MIN_PATIENTS or "volatile" not in per_arm:
        print(f"   fewer than {MIN_PATIENTS} patients on one side — the probe is ABSENT, not passed.")
        print("   Challenge A's acceptance condition is therefore UNTESTED (rule 31).")
        p4 = None
        state["p4"] = {"passed": None, "reason": "probe underpowered", "n_sevo": n_s, "n_des": n_d}
    else:
        # Residualise within MAC decile: rank the candidate INSIDE each decile so any depth difference
        # between the agents cannot leak into the probe.
        idx = np.flatnonzero(pm)
        edges = np.quantile(mac[pm], np.linspace(0, 1, PROBE_DECILES + 1))
        resid = np.full(idx.size, np.nan)
        for b in range(PROBE_DECILES):
            lo_e, hi_e = edges[b], edges[b + 1]
            sel = (mac[idx] >= lo_e) & ((mac[idx] <= hi_e) if b == PROBE_DECILES - 1
                                        else (mac[idx] < hi_e))
            if sel.sum() < 2:
                continue
            v = x[idx][sel]
            r = np.argsort(np.argsort(v)).astype(float)
            resid[sel] = (r - r.mean()) / max(1.0, r.std())
        okp = np.isfinite(resid)
        py = is_des[idx][okp].astype(float)
        ps = subj[idx][okp]
        probe = auc_abs(py, resid[okp])
        plo, phi, _ = cluster_bootstrap_ci(lambda i: auc_abs(py[i], resid[okp][i]), ps, rng, reps=2000)
        probe_abs = abs(probe - 0.5)
        # Put the depth association on the probe's scale: for a rank statistic, AUC = (rho + 1) / 2.
        depth_abs = abs(per_arm["volatile"]["rho"]) / 2.0
        p4 = bool(probe_abs < depth_abs)
        print(f"   drug probe |AUC-0.5| = {probe_abs:.3f}  (AUC {probe:.3f}, CI [{plo:.3f}, {phi:.3f}], "
              f"{int(okp.sum())} rows)")
        print(f"   depth      |AUC-0.5| = {depth_abs:.3f}  (volatile-arm rho {per_arm['volatile']['rho']:+.3f}"
              " mapped by AUC = (rho+1)/2)")
        print(f"\n   P4 {'PASSED — depth is more legible than the agent' if p4 else '*** FAILED — the agent is more legible than the depth; Challenge A is FAILED'}")
        state["p4"] = {"probe_auc": float(probe), "probe_ci": [float(plo), float(phi)],
                       "probe_abs": float(probe_abs), "depth_abs": float(depth_abs),
                       "n_sevo": n_s, "n_des": n_d, "passed": p4}

    # ------------------------------------------------------------------ P5
    print("\n" + "=" * 100)
    print(f"P5 — PLACEBO GATE: remifentanil must correlate < {PLACEBO_MAX_RATIO:.0%} as strongly as the "
          "hypnotic")
    print("=" * 100)
    print("   Remifentanil is co-administered, rises and falls with the phase of the case, and is a")
    print("   mu-opioid with a far weaker EEG signature than any hypnotic at clinical doses. A candidate")
    print("   correlating with it as strongly as with the hypnotic is tracking the phase of the operation.")
    print("   It is not EEG-silent, so this placebo is CONSERVATIVE: it can withdraw a real effect and it")
    print("   cannot manufacture one.")
    placebo = {}
    for arm, key in ARMS:
        if arm not in per_arm:
            continue
        m = arm_mask[arm] & clean & np.isfinite(x) & np.isfinite(rftn)
        n_eval = n_evaluable_spearman(x[m], rftn[m], subj[m], MIN_POINTS, MIN_DISTINCT)
        if n_eval < MIN_PATIENTS:
            print(f"   {arm:12s} only {n_eval} evaluable patients; placebo ABSENT for this arm")
            continue
        rho_p = within_subject_spearman(x[m], rftn[m], subj[m], MIN_POINTS, MIN_DISTINCT)
        ratio = abs(rho_p) / abs(per_arm[arm]["rho"]) if per_arm[arm]["rho"] else float("inf")
        placebo[arm] = {"rho": float(rho_p), "ratio_to_primary": float(ratio), "n_patients": n_eval}
        print(f"   {arm:12s} remifentanil rho {rho_p:+.3f}   = {ratio:6.1%} of the hypnotic's "
              f"{per_arm[arm]['rho']:+.3f}")
    if not placebo:
        print("\n   P5 is ABSENT — P2 is UNGATED and must not be read as established (rule 31).")
        p5 = None
    else:
        worst = max(placebo.values(), key=lambda d: d["ratio_to_primary"])
        p5 = bool(worst["ratio_to_primary"] < PLACEBO_MAX_RATIO)
        print(f"\n   P5 {'PASSED' if p5 else '*** FAILED — P2 is WITHDRAWN: this tracks the phase of the case'}"
              f"   (worst arm {worst['ratio_to_primary']:.1%})")
    state["p5"] = {"per_arm": placebo, "passed": p5}

    # ------------------------------------------------------------------ P6
    print("\n" + "=" * 100)
    print("P6 — OPIOID COVARIATE (reported, not gating): the dose association within remifentanil terciles")
    print("=" * 100)
    out6 = {}
    for arm, key in ARMS:
        if arm not in per_arm:
            continue
        m = arm_mask[arm] & clean & np.isfinite(x) & np.isfinite(dose[key]) & np.isfinite(rftn)
        if m.sum() < 30:
            continue
        edges = np.quantile(rftn[m], [0.0, 1 / 3, 2 / 3, 1.0])
        for b in range(3):
            sel = m & (rftn >= edges[b]) & ((rftn <= edges[b + 1]) if b == 2 else (rftn < edges[b + 1]))
            n_eval = n_evaluable_spearman(x[sel], dose[key][sel], subj[sel], MIN_POINTS, MIN_DISTINCT)
            if n_eval < 10:
                print(f"   {arm:12s} remi tercile {b + 1}: only {n_eval} evaluable patients")
                continue
            rho_t = within_subject_spearman(x[sel], dose[key][sel], subj[sel], MIN_POINTS, MIN_DISTINCT)
            out6.setdefault(arm, {})[f"tercile_{b + 1}"] = {"rho": float(rho_t), "n_patients": n_eval}
            print(f"   {arm:12s} remi tercile {b + 1} ({edges[b]:6.2f}-{edges[b + 1]:6.2f}): "
                  f"rho {rho_t:+.3f}  ({n_eval} patients)")
    state["p6"] = out6

    # ------------------------------------------------------------------ context table
    print("\n" + "=" * 100)
    print("CONTEXT — other candidates, UNADJUSTED intervals, not claims (see the header note)")
    print("=" * 100)
    print(f"   {'candidate':26s}" + "".join(f"{a + ' rho':>18s}" for a, _ in ARMS))
    ctx = {}
    for cname in REPORT:
        xc = col(cname)
        line, vals = f"   {cname:26s}", {}
        for arm, key in ARMS:
            m = arm_mask[arm] & clean & np.isfinite(xc) & np.isfinite(dose[key])
            n_eval = n_evaluable_spearman(xc[m], dose[key][m], subj[m], MIN_POINTS, MIN_DISTINCT)
            if n_eval < MIN_PATIENTS:
                line += f"{'—':>18s}"
                continue
            r = within_subject_spearman(xc[m], dose[key][m], subj[m], MIN_POINTS, MIN_DISTINCT)
            vals[arm] = float(r)
            line += f"{r:+18.3f}"
        ctx[cname] = vals
        print(line)
    state["context"] = ctx

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p5 is False:
        print("   P2 is WITHDRAWN by its own placebo: the association tracks the phase of the operation.")
        verdict = "withdrawn_by_placebo"
    elif p5 is None:
        print("   UNGATED — the placebo could not be evaluated, so P2 is provisional (rule 31).")
        verdict = "ungated"
    elif p4 is None:
        print("   Challenge A's acceptance condition is UNTESTED — the probe was underpowered. P2 and P3")
        print("   stand on their own terms and do not, between them, address the challenge.")
        verdict = "acceptance_condition_untested"
    elif p2 and p3 and p4:
        print("   Challenge A is MET on this deposit, ON THE DOSE AXIS: one representation tracks the")
        print("   administered anaesthetic in both a volatile and a propofol arm, with the same sign and")
        print("   comparable strength, carries less agent-identity information than depth information at")
        print("   matched MAC, and survives a co-administered-drug placebo. **This is a statement about")
        print("   anaesthetic dose, not about consciousness**, on one site with one monitor.")
        verdict = "met_on_dose_axis"
    elif p4 is False:
        print("   Challenge A is FAILED: at matched MAC the agent is more legible than the depth.")
        verdict = "failed_drug_probe"
    else:
        print("   Challenge A is not met: the dose association did not clear P2 or P3.")
        verdict = "failed_p2_or_p3"
    state["verdict"] = verdict
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
