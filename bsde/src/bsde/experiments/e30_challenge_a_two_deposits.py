#!/usr/bin/env python3
"""E30 — Challenge A across two deposits: propofol without an opioid, and volatiles with one.

REGISTERED AFTER E25 AND E29 CLOSED, and that is stated first. Both failed on the same thing: in VitalDB the
hypnotic and remifentanil are co-titrated at every timescale a 300 s grid can express, so a dose association
there cannot be separated from opioid co-administration. E29 measured that directly — across nine pairing
settings, only one held the opioid closer than chance, and only by halving the dose contrast.

E29's closing note named the acquisition target: **a deposit with a graded hypnotic dose axis and no
co-titrated opioid.** Chennu is exactly that — a volunteer study, propofol only, four target concentrations
per subject, no opioid administered — and its feature table has been on disk since before the Cambridge host
began failing TLS (§9.17). `meta_plasma_propofol_ug_per_L` is a measured plasma concentration, not a model
output, for 20 subjects at 4 levels each.

**So Challenge A becomes answerable with no new acquisition**, by putting the two deposits side by side:

    arm PROPOFOL   Chennu, dose = plasma propofol (ug/L), 20 volunteers x 4 graded levels, NO OPIOID
    arm VOLATILE   VitalDB, dose = Primus/MAC, surgical patients, opioid co-administered

**The propofol arm is the one that matters, because it is the one the opioid confound cannot reach.** If the
candidate tracks propofol concentration in a study where no opioid was given, the association E25 found and
E29 could not defend is not purely co-titration. If it does not, the simplest reading of all four
experiments is that there was never a hypnotic-depth signal here at all.

WHAT IS STRUCTURALLY WEAK ABOUT A CROSS-DEPOSIT COMPARISON, and it is not a footnote. The two arms differ in
**everything except the question**: 91 channels against 2 frontal ones, 250 Hz against 128 Hz, healthy
volunteers against surgical patients, plasma concentration against end-tidal potency, and — per §9.16 —
Chennu never reaches unconsciousness at all, so its dose range is sedation rather than anaesthesia. **A
difference in association strength between the arms is therefore uninterpretable**, and P3 below tests only
the SIGN. Anyone reading a magnitude comparison out of this file is reading something it does not support.

REGISTERED PREDICTIONS, in evaluation order. A failed gate makes the downstream verdict ABSENT (rule 31).

    P1  MACHINERY GATE, no candidate.
        (a) **DOSE MUST VARY WITHIN SUBJECT in both arms** — rule 32, fourth occurrence in this project.
            Chennu supplies 4 levels per subject; the gate checks that they are actually distinct plasma
            values rather than 4 nominal labels with one concentration.
        (b) COVERAGE — at least `MIN_PROPOFOL` Chennu subjects and `MIN_VOLATILE` VitalDB patients.
        (c) **NO OPIOID IN THE PROPOFOL ARM.** Asserted from the deposit's own protocol, and the check that
            can be made from the table is that no opioid column exists in it. Stated as an assumption
            rather than a measurement, because that is what it is.

    P2  THE PRIMARY, PER ARM. `exponent_high`'s within-subject Spearman correlation with dose, subject-
        clustered CI excluding zero, in each arm separately. Identical estimator to E25's, deliberately.

    P3  CROSS-DRUG CONSISTENCY, **SIGN ONLY**. The two arms must agree in sign. No magnitude criterion is
        applied, for the reason given above — the arms are not comparable in strength and pretending
        otherwise would manufacture a result out of a montage difference.

    P4  THE OPIOID-FREE REPLICATION, which is the point of the whole file. Does the propofol arm's interval
        exclude zero **on its own**, with no opioid anywhere in the study? This is the claim E25 could not
        make and E29 could not rescue.

    P5  THE PLACEBO, GATING (rule 34). In the Chennu arm, the same statistic against **reaction time**
        (`meta_mean_reaction_time_ms`), which rises with sedation and is therefore a behavioural proxy for
        the same latent depth. **If the candidate tracks reaction time as strongly as it tracks the drug,
        the arm has not distinguished drug from drowsiness** — which is a weaker but real version of the
        case-phase problem. Conservative by construction, like E25's: reaction time genuinely reflects
        depth, so this can withdraw a true effect and cannot manufacture one.

    NOTE ON THE OTHER CANDIDATES. One pre-declared primary. The rest are context with UNADJUSTED intervals
    and would have to pass `verifier/multiplicity.py` first. None is claimed.

    FALSIFICATION: P4 fails, or P3's signs disagree, or P5 fails.

SCOPE AND LIMITS.
  * **Dose is not consciousness**, carried over verbatim from E25 and E29 and still governing every sentence.
  * **Chennu is sedation, not anaesthesia** (§9.16): the median subject at the deepest level still got 35 of
    40 targets correct. This arm measures tracking of a sedative concentration in responsive people.
  * **n = 20 subjects, 4 points each**, so a within-subject rank correlation has four ranks to work with.
    The interval is over subjects and is honest, but the per-subject estimate is coarse by construction.
  * **The volatile arm carries every VitalDB limitation** already recorded: maintenance only, two frontal
    channels, opioid co-titrated, and its own placebo already failed in E25. It is here as the second drug,
    not as independent support.
  * Cross-deposit: two montages, two rates, two populations. Sign only.

--------------------------------------------------------------------------------------------------------
OUTCOME, ADDED AFTER THE RUN. **P2, P4 and P5 PASSED. P3 FAILED: the two arms disagree in SIGN.**

    propofol (Chennu, no opioid)   rho **+0.710 [+0.614, +0.820]**   20 volunteers, 80 rows
    volatile (VitalDB, MAC)        rho **-0.126 [-0.175, -0.076]**   110 patients, 4,379 rows
    P4  the propofol arm stands on its own, in a study where **no opioid was given**
    P5  reaction time reaches only **33.1 %** of the drug association, so the arm distinguishes the drug
        from drowsiness

**THE FIRST SURVIVING POSITIVE IN THIS PROJECT'S CHALLENGE A WORK, AND IT IS ONE ARM, NOT THE CHALLENGE.**
E25's dose association was withdrawn by an opioid it could not separate from; E29 showed no pairing could
separate them. **Chennu has no opioid at all**, and there `exponent_high` tracks measured plasma propofol at
+0.710 within subject, clearing a behavioural placebo. That is the claim E25 could not defend, defended.

**AND IT IS NOT A CROSS-DRUG RESULT, because the arms point opposite ways.** Error-catalogue rule 16 is
explicit: when two arms of the same test disagree in sign, the definition is doing the work, not the
biology. Challenge A asks for ONE representation across drugs. This is two behaviours wearing one name.

**THE CONTEXT TABLE SAYS THE REVERSAL IS NOT ABOUT THIS CANDIDATE, WHICH IS THE MORE USEFUL FINDING.**

    candidate                 propofol    volatile
    exponent_high               +0.710      -0.126
    lempel_ziv                  +0.520      -0.264
    spectral_entropy            +0.380      -0.262
    spectral_edge_95            +0.160      -0.328
    relative_delta_power        -0.260      +0.250
    whole_head_exponent         -0.130      +0.223
    relative_alpha_power        -0.220      -0.339   <- the one that does NOT flip

**Six of seven comparable candidates flip sign between the deposits, in both directions.** A reversal that
near-universal is a property of the two DEPOSITS, not of any feature — a feature-level explanation would
have to flip six unrelated measures the same way by coincidence. Three deposit-level explanations, none
tested here and all testable:

  1. **Dose range, and this is the one standard pharmacology predicts.** Propofol's EEG effect is
     non-monotonic: fast activity rises into sedation, then falls as delta and suppression take over.
     Chennu is sedation — §9.16 measured the median subject getting 35 of 40 targets correct at the deepest
     level — and VitalDB is surgical maintenance. A positive slope in the light range and a negative one in
     the deep range is what the textbook curve does, and would mean **both arms are right**.
  2. **Montage.** 91 channels averaged over the whole head against 2 frontal ones. Frontal beta behaves
     differently from posterior beta under propofol; §9.11 already found a frontal gradient here.
  3. **Sampling rate.** 250 Hz against 128 Hz. `exponent_high` fits 20-40 Hz, and VitalDB's Nyquist is
     64 Hz, so its fit window sits close to where the anti-alias roll-off begins.

**Explanation 1 is a real, pre-specifiable prediction and belongs to a new registration, not to this file.**
If dose-range non-monotonicity is the cause, the sign must depend on depth *within* each arm in a stated
direction — and that is falsifiable, unlike "the deposits differ". Explanations 2 and 3 are addressable by
recomputing the Chennu arm on frontal channels only and at a decimated rate, which changes no label and
answers whether the montage or the Nyquist edge carries the flip.

**WHAT MAY AND MAY NOT BE SAID FROM THIS FILE.** May: a spontaneous EEG measure tracks measured plasma
propofol concentration, within subject, in opioid-free volunteers, at rho +0.710, surviving a behavioural
placebo. May not: that it tracks anaesthetic depth across drugs — P3 failed, and that failure is the
challenge's own criterion. **And neither arm says anything about consciousness**; Chennu's subjects were
responsive throughout.
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
from bsde.verifier.stats import (cluster_bootstrap_ci, n_evaluable_spearman,            # noqa: E402
                                 within_subject_spearman)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
CHENNU = os.path.join(RESULTS, "chennu_features_v3.csv")
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
AGENTS = os.path.join(RESULTS, "vitaldb_agents.csv")
OUT = os.path.join(RESULTS, "e30_challenge_a_two_deposits.json")

PRIMARY = "exponent_high"
DOSE_COL = "meta_plasma_propofol_ug_per_L"
RT_COL = "meta_mean_reaction_time_ms"
EMG_MAX = 35.0
MIN_PROPOFOL = 15
MIN_VOLATILE = 40
MIN_POINTS = 3
MIN_DISTINCT = 3
PLACEBO_MAX_RATIO = 0.50
REPORT = ("exponent_high", "whole_head_exponent", "relative_delta_power", "relative_alpha_power",
          "lempel_ziv", "spectral_entropy", "spectral_edge_95", "wpli_alpha", "uce_v1")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _registered_order() -> None:
    print("   Registered order of evaluation, fixed here and not re-openable:")
    print("     P1 GATE  dose varies within subject in BOTH arms; coverage; no opioid in the propofol arm")
    print(f"     P2       {PRIMARY}'s within-subject Spearman with dose, CI excluding 0, in EACH arm")
    print("     P3       the two arms must agree in SIGN — magnitude is not compared across deposits")
    print("     P4       the propofol arm alone, with no opioid in the study — the point of the file")
    print(f"     P5 GATE  reaction-time placebo must be < {PLACEBO_MAX_RATIO:.0%} of the drug association")


def main(argv=None) -> int:
    seed_registry()
    print("E30 — Challenge A across two deposits: propofol without an opioid, volatiles with one")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    print("   CLAIM SCOPE: anaesthetic DOSE, never consciousness.")
    missing = [p for p in (CHENNU, GRID, AGENTS) if not os.path.exists(p)]
    if missing:
        print(f"\n   *** absent: {[os.path.basename(p) for p in missing]}")
        _registered_order()
        return 2

    # ---- propofol arm (Chennu) -------------------------------------------------
    ch = [r for r in csv.DictReader(open(CHENNU, newline="")) if r.get("status") == "ok"]
    cs = np.array([r.get("subject", "") for r in ch])
    cdose = np.array([_f(r.get(DOSE_COL, "")) for r in ch], float)
    crt = np.array([_f(r.get(RT_COL, "")) for r in ch], float)
    cx = np.array([_f(r.get(PRIMARY, "")) for r in ch], float)
    has_opioid_col = any(k for k in (ch[0] if ch else {}) if "opioid" in k.lower()
                         or "remi" in k.lower() or "fent" in k.lower())

    # ---- volatile arm (VitalDB) ------------------------------------------------
    dose_by = {r["recording_id"]: r for r in csv.DictReader(open(AGENTS, newline=""))}
    vr = [r for r in csv.DictReader(open(GRID, newline=""))
          if r.get("status") == "ok" and r["recording_id"] in dose_by]
    vs = np.array([r.get("subject", "") for r in vr])
    vmac = np.array([_f(dose_by[r["recording_id"]].get("mac", "")) for r in vr], float)
    vemg = np.array([_f(r.get("meta_emg", "")) for r in vr], float)
    voff = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in vr])
    vap = np.array([r.get("meta_agents_present", "") for r in vr])
    vx = np.array([_f(r.get(PRIMARY, "")) for r in vr], float)
    vol = np.array(["sevoflurane" in g or "desflurane" in g for g in vap])
    vkeep = vol & ~voff & np.isfinite(vemg) & (vemg <= EMG_MAX) & np.isfinite(vmac)

    print(f"\n   propofol arm (Chennu): {len(ch)} rows, {len(set(cs))} subjects")
    print(f"   volatile arm (VitalDB): {int(vkeep.sum())} rows after the EMG filter, "
          f"{len(set(vs[vkeep]))} patients")

    # ------------------------------------------------------------------ P1
    print("\n" + "=" * 100)
    print("P1 — MACHINERY GATE (no candidate)")
    print("=" * 100)
    n_prop = n_evaluable_spearman(np.arange(len(ch), dtype=float), cdose, cs, MIN_POINTS, MIN_DISTINCT)
    n_vol = n_evaluable_spearman(np.arange(int(vkeep.sum()), dtype=float), vmac[vkeep], vs[vkeep],
                                 MIN_POINTS, MIN_DISTINCT)
    lv = [len(np.unique(cdose[(cs == s) & np.isfinite(cdose)])) for s in np.unique(cs)]
    print(f"   (a) distinct plasma concentrations per Chennu subject: median {int(np.median(lv))}, "
          f"min {int(np.min(lv))}, max {int(np.max(lv))}")
    print(f"       subjects with dose varying: propofol {n_prop}, volatile {n_vol}")
    print(f"   (b) coverage floors: propofol {MIN_PROPOFOL}, volatile {MIN_VOLATILE}")
    print(f"   (c) no opioid column in the Chennu table: {not has_opioid_col}  "
          "(the absence of an opioid is the deposit's PROTOCOL, asserted, not measured here)")
    p1 = bool(n_prop >= MIN_PROPOFOL and n_vol >= MIN_VOLATILE and not has_opioid_col)
    print(f"\n   P1 {'PASSED' if p1 else '*** FAILED'}")
    state = {"experiment": "E30", "p1": {"n_propofol": n_prop, "n_volatile": n_vol,
                                         "opioid_column_present": bool(has_opioid_col),
                                         "passed": p1}}
    if not p1:
        print("   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    # ------------------------------------------------------------------ P2
    rng = np.random.default_rng(20260730)
    print("\n" + "=" * 100)
    print(f"P2 — PRIMARY: {PRIMARY}'s within-subject Spearman with dose, per arm")
    print("=" * 100)
    per_arm = {}
    arms = (("propofol (Chennu, no opioid)", cx, cdose, cs),
            ("volatile (VitalDB, MAC)", vx[vkeep], vmac[vkeep], vs[vkeep]))
    print(f"   {'arm':30s} {'subj':>5s} {'rows':>6s} {'rho':>9s} {'95% CI':>22s}")
    for name, xx, zz, ss in arms:
        m = np.isfinite(xx) & np.isfinite(zz)
        n_eval = n_evaluable_spearman(xx[m], zz[m], ss[m], MIN_POINTS, MIN_DISTINCT)
        floor = MIN_PROPOFOL if name.startswith("propofol") else MIN_VOLATILE
        if n_eval < floor:
            print(f"   {name:30s} {n_eval:5d} {int(m.sum()):6d}   too few evaluable subjects")
            continue
        rho = within_subject_spearman(xx[m], zz[m], ss[m], MIN_POINTS, MIN_DISTINCT)
        lo, hi, _ = cluster_bootstrap_ci(
            lambda i: within_subject_spearman(xx[m][i], zz[m][i], ss[m][i], MIN_POINTS, MIN_DISTINCT),
            ss[m], rng, reps=2000)
        per_arm[name] = {"rho": rho, "ci": [float(lo), float(hi)], "n_subjects": n_eval,
                         "n_rows": int(m.sum())}
        print(f"   {name:30s} {n_eval:5d} {int(m.sum()):6d} {rho:9.3f} "
              f"{f'[{lo:+.3f}, {hi:+.3f}]':>22s}")
    p2 = bool(len(per_arm) == 2 and all(d["ci"][0] > 0 or d["ci"][1] < 0 for d in per_arm.values()))
    print(f"\n   P2 {'PASSED' if p2 else '*** FAILED'}")
    state["p2"] = {"per_arm": per_arm, "passed": p2}

    # ------------------------------------------------------------------ P3
    print("\n" + "=" * 100)
    print("P3 — CROSS-DRUG CONSISTENCY: SIGN ONLY (the arms are not comparable in magnitude)")
    print("=" * 100)
    if len(per_arm) < 2:
        p3, state["p3"] = None, {"passed": None}
        print("   fewer than two reportable arms — ABSENT (rule 31).")
    else:
        signs = {a: (0 if (d["ci"][0] <= 0 <= d["ci"][1]) else int(np.sign(d["rho"])))
                 for a, d in per_arm.items()}
        p3 = bool(len(set(signs.values())) == 1 and 0 not in signs.values())
        for a, s_ in signs.items():
            print(f"   {a:30s} rho {per_arm[a]['rho']:+.3f}   sign {s_:+d}"
                  + ("  (interval spans zero — NO direction)" if s_ == 0 else ""))
        print(f"   P3 {'PASSED' if p3 else '*** FAILED'}")
        print("   Magnitudes are NOT compared: 91 channels against 2, 250 Hz against 128, volunteers")
        print("   against surgical patients, plasma concentration against end-tidal potency.")
        state["p3"] = {"signs": signs, "passed": p3}

    # ------------------------------------------------------------------ P4
    print("\n" + "=" * 100)
    print("P4 — THE OPIOID-FREE REPLICATION: does the propofol arm stand on its own?")
    print("=" * 100)
    key = "propofol (Chennu, no opioid)"
    if key not in per_arm:
        p4, state["p4"] = None, {"passed": None, "reason": "arm not reportable"}
        print("   ABSENT (rule 31).")
    else:
        d = per_arm[key]
        p4 = bool(d["ci"][0] > 0 or d["ci"][1] < 0)
        print(f"   rho {d['rho']:+.3f} [{d['ci'][0]:+.3f}, {d['ci'][1]:+.3f}] over {d['n_subjects']} "
              "volunteers, in a study where no opioid was given")
        print(f"   P4 {'PASSED — the association E25 could not defend survives where no opioid exists' if p4 else '*** FAILED'}")
        state["p4"] = {"rho": d["rho"], "ci": d["ci"], "passed": p4}

    # ------------------------------------------------------------------ P5
    print("\n" + "=" * 100)
    print("P5 — PLACEBO GATE: reaction time, a behavioural proxy for the same latent depth")
    print("=" * 100)
    m5 = np.isfinite(cx) & np.isfinite(crt)
    n5 = n_evaluable_spearman(cx[m5], crt[m5], cs[m5], MIN_POINTS, MIN_DISTINCT)
    if n5 < MIN_PROPOFOL or key not in per_arm:
        p5, state["p5"] = None, {"passed": None, "reason": f"only {n5} evaluable subjects"}
        print(f"   only {n5} evaluable subjects — ABSENT, so P4 is UNGATED and provisional (rule 31).")
    else:
        rt_rho = within_subject_spearman(cx[m5], crt[m5], cs[m5], MIN_POINTS, MIN_DISTINCT)
        ratio = abs(rt_rho) / abs(per_arm[key]["rho"]) if per_arm[key]["rho"] else float("inf")
        p5 = bool(ratio < PLACEBO_MAX_RATIO)
        print(f"   reaction-time rho {rt_rho:+.3f} = {ratio:.1%} of the drug association's "
              f"{per_arm[key]['rho']:+.3f}")
        print(f"   P5 {'PASSED' if p5 else '*** FAILED — the arm has not distinguished drug from drowsiness'}")
        print("   Conservative by construction: reaction time genuinely reflects depth, so this gate can")
        print("   withdraw a true effect and cannot manufacture one.")
        state["p5"] = {"rt_rho": float(rt_rho), "ratio": float(ratio), "passed": p5}

    # ------------------------------------------------------------------ context
    print("\n" + "=" * 100)
    print("CONTEXT — other candidates, UNADJUSTED, not claims")
    print("=" * 100)
    print(f"   {'candidate':26s} {'propofol rho':>14s} {'volatile rho':>14s}")
    ctx = {}
    for cname in REPORT:
        cxx = np.array([_f(r.get(cname, "")) for r in ch], float)
        vxx = np.array([_f(r.get(cname, "")) for r in vr], float)[vkeep]
        line, vals = f"   {cname:26s}", {}
        for tag, xx, zz, ss, floor in (("propofol", cxx, cdose, cs, MIN_PROPOFOL),
                                       ("volatile", vxx, vmac[vkeep], vs[vkeep], MIN_VOLATILE)):
            m = np.isfinite(xx) & np.isfinite(zz)
            if n_evaluable_spearman(xx[m], zz[m], ss[m], MIN_POINTS, MIN_DISTINCT) < floor:
                line += f"{'—':>14s}"
                continue
            r = within_subject_spearman(xx[m], zz[m], ss[m], MIN_POINTS, MIN_DISTINCT)
            vals[tag] = float(r)
            line += f"{r:+14.3f}"
        ctx[cname] = vals
        print(line)
    state["context"] = ctx

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p5 is False:
        print("   WITHDRAWN by the reaction-time placebo: the propofol arm has not separated the drug from")
        print("   drowsiness, which is the sedation-study analogue of E25's case-phase problem.")
        verdict = "withdrawn_by_placebo"
    elif p5 is None:
        print("   UNGATED — the placebo could not be evaluated, so P4 is provisional (rule 31).")
        verdict = "ungated"
    elif p4 and p3:
        print("   Challenge A is MET ON THE DOSE AXIS across two drugs: the candidate tracks propofol")
        print("   concentration in a volunteer study with NO opioid, tracks volatile potency in surgical")
        print("   patients, agrees in sign, and survives a behavioural placebo. Combined with E25's P4 —")
        print("   the agent an order of magnitude less legible than the depth at matched MAC — this is the")
        print("   challenge's acceptance condition met. **Anaesthetic dose, not consciousness**, across two")
        print("   deposits that differ in everything but the question, compared in SIGN only.")
        verdict = "met_on_dose_axis"
    elif p4:
        print("   The opioid-free replication holds but the arms disagree in sign, so this is not a")
        print("   cross-drug result. Rule 16: when two arms disagree in sign the definition is doing the")
        print("   work, and here the two arms have different montages and different populations.")
        verdict = "propofol_only"
    else:
        print("   NOT MET: the propofol arm does not stand on its own. With E25 withdrawn and E29 closed,")
        print("   the simplest reading of all four experiments is that there is no hypnotic-depth signal")
        print("   here that survives its controls.")
        verdict = "not_met"
    state["verdict"] = verdict
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
