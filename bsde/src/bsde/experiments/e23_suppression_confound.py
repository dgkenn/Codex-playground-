#!/usr/bin/env python3
"""E23 — is E22's state effect a burst-suppression detector wearing a consciousness label?

REGISTERED BEFORE E22 HAS BEEN RUN ON REAL LABELS, AND BEFORE ANY CANDIDATE VALUE FROM `vitaldb_grid.csv`
HAS BEEN READ. Only E22's permuted smoke run has executed, which reports nothing about the association. This
file is committed before either result exists.

THE CONFOUND, AND WHY IT IS THE FIRST ONE TO ASK ABOUT. E22 contrasts BIS <= 60 against BIS >= 80. Burst
suppression is common in the deep arm and impossible in the light one, and **a suppressed EEG is trivially
distinguishable from an unsuppressed one by almost any spectral measure** — it is a near-flat trace
interrupted by bursts. So a candidate could pass every one of E22's predictions by being a suppression
detector, which is a solved problem the BIS monitor already reports as a dedicated channel, and which says
nothing about consciousness that `BIS/SR` does not already say.

**This deposit can answer that directly, which is unusual.** `BIS/SR` is the device's own suppression ratio
— the percentage of the epoch that was suppressed — scored by the monitor, not by us, and streamed with
every window. So the question is not "might this be suppression?" but "does the effect survive where the
device says there is no suppression at all?"

WHAT THIS IS NOT. It is not a claim that suppression-driven discrimination is worthless; depth of anaesthesia
monitoring cares about suppression and the anaesthesia wedge would too. It is a claim about **what the
measure may be described as**. A candidate that only works where SR > 0 is a suppression detector and must
be reported as one.

REGISTERED PREDICTIONS, evaluated in this order. A failed gate makes the downstream verdict ABSENT, not
negative (rule 31).

    P1  MACHINERY GATE, AND IT IS ERROR-CATALOGUE RULE 32 VERBATIM. **`BIS/SR` must VARY within the
        unresponsive arm**: at least 15 patients must supply an SR > 0 window and at least 15 must supply an
        SR == 0 window, with at least 15 supplying both. Rule 32 was paid for by two ledger entries in the
        sibling project that compared two predictors across what turned out to be two cohorts, because the
        flag defining one of them was present in 100.0 % of the patients carrying the other. One `Counter`
        before the design would have caught it, so it is run first here.

    P2  HOW MUCH OF THE ARM SEPARATION IS SUPPRESSION AT ALL. Reported, not gating: the arms' separation by
        `BIS/SR` itself, and the fraction of unresponsive windows with SR > 0. If that fraction is small the
        confound is small, and this whole experiment is a formality worth having on the record.

    P3  THE PRIMARY. `exponent_high`'s within-subject AUC between the arms, recomputed on **SR == 0 windows
        only** in the unresponsive arm (the responsive arm is unsuppressed by definition, and that is
        checked rather than assumed). It must retain at least **half** of the magnitude it has on the full
        arm, |AUC - 0.5|, and its CI must still exclude 0.5. **If it does not, the effect is substantially
        suppression and the description of the candidate changes.**

    P4  THE CONVERSE, WHICH IS THE SHARPER TEST. Within the unresponsive arm ONLY, holding the behavioural
        state constant, does the candidate separate SR > 0 from SR == 0 windows? Reported as a magnitude
        against P3's. **A candidate that separates suppression from non-suppression far better than it
        separates unresponsive from responsive is a suppression detector**, whatever P3 says, because P3
        can survive on the residual while the measure's dominant sensitivity lies elsewhere.

    FALSIFICATION: P3 not met. Then E22's headline, if E22 has one, is a statement about burst suppression
    and must be written as one.

SCOPE AND LIMITS.
  * **`BIS/SR` is the device's opinion, not ground truth.** It is a proprietary algorithm on the same two
    frontal electrodes, so `SR == 0` means "the monitor detected no suppression", which is weaker than "no
    suppression occurred". The direction of that error is toward leaving some suppressed windows in the
    SR == 0 stratum, which makes P3 easier to pass — so a P3 PASS is the weaker of the two outcomes and a
    P3 FAILURE is the stronger.
  * The SR == 0 restriction is itself an exclusion and is not random: deeper anaesthesia carries more
    suppression, so restricting to SR == 0 shifts the unresponsive arm lighter. That narrows the contrast
    and biases P3 DOWNWARD — against the candidate — which is the safe direction for a confound test but
    means a marginal P3 failure is not decisive on its own. The shift in the arm's median BIS is reported so
    the size of it is visible.
  * One site, one monitor, two frontal channels, 128 Hz.
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
                                 n_evaluable_subjects, within_subject_auc)

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e23_suppression_confound.json")

BIS_UNRESPONSIVE_MAX = 60.0      # identical to E22 by construction; the arms must be the same arms
BIS_RESPONSIVE_MIN = 80.0
PRIMARY = "exponent_high"
MIN_PATIENTS = 15
RETENTION_MIN = 0.50
GATE_MIN_ROWS = 1500
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
    print(f"     P1 GATE  BIS/SR must VARY inside the unresponsive arm: >= {MIN_PATIENTS} patients with an")
    print("              SR > 0 window, >= {0} with an SR == 0 window, >= {0} with both (rule 32)"
          .format(MIN_PATIENTS))
    print("     P2       how much of the arm separation is suppression at all — reported, not gating")
    print(f"     P3       {PRIMARY}'s arm AUC on SR == 0 windows only must retain >= "
          f"{RETENTION_MIN:.0%} of its magnitude, CI still excluding 0.5")
    print("     P4       the converse: SR > 0 vs SR == 0 WITHIN the unresponsive arm, magnitude compared")


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    table = os.path.abspath(args[args.index("--table") + 1]) if "--table" in args else TABLE
    seed_registry()
    print("E23 — is the state effect a burst-suppression detector?")
    print(f"   search space {REGISTRY.search_space_size()} candidates; analytic dof >= 72")
    if not os.path.exists(table):
        print(f"\n   *** {os.path.basename(table)} absent — the VitalDB grid stream has not produced it.")
        _registered_order()
        return 2

    rows = [r for r in csv.DictReader(open(table, newline="")) if r.get("status") == "ok"]
    if len(rows) < GATE_MIN_ROWS:
        print(f"\n   *** {os.path.basename(table)} holds {len(rows)} usable rows, below the registered "
              f"floor of {GATE_MIN_ROWS}. Nothing is reported.")
        _registered_order()
        return 2

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)          # noqa: E731
    subj = np.array([r.get("subject", "") for r in rows])
    bis, sr = col("meta_bis"), col("meta_sr")
    sensor_off = np.array([str(r.get("meta_sensor_off", "")).strip().lower() == "true" for r in rows])
    x = col(PRIMARY)

    unresp = np.isfinite(bis) & (bis <= BIS_UNRESPONSIVE_MAX) & ~sensor_off
    resp = np.isfinite(bis) & (bis >= BIS_RESPONSIVE_MIN) & ~sensor_off
    keep = unresp | resp
    y = resp.astype(float)
    direction = REGISTRY.get(PRIMARY).predicted("unconscious_vs_awake") or "higher"
    rng = np.random.default_rng(20260730)

    supp = np.isfinite(sr) & (sr > 0.0)
    clean = np.isfinite(sr) & (sr == 0.0)
    print(f"\n   table {os.path.basename(table)}: {len(rows)} usable rows, {len(set(subj))} patients")
    print(f"   unresponsive rows {int(unresp.sum()):5d}   responsive rows {int(resp.sum()):5d}")
    print(f"   SR present (finite) {int(np.isfinite(sr).sum()):5d} rows;  "
          f"SR > 0 {int(supp.sum()):5d};  SR == 0 {int(clean.sum()):5d}")

    # ------------------------------------------------------------------ P1
    print("\n" + "=" * 100)
    print("P1 — GATE: does BIS/SR actually VARY inside the unresponsive arm? (rule 32)")
    print("=" * 100)
    s_supp = {s for s in subj[unresp & supp]}
    s_clean = {s for s in subj[unresp & clean]}
    both = s_supp & s_clean
    print(f"   patients with an SR > 0  unresponsive window: {len(s_supp)}")
    print(f"   patients with an SR == 0 unresponsive window: {len(s_clean)}")
    print(f"   patients with BOTH                          : {len(both)}")
    p1 = min(len(s_supp), len(s_clean), len(both)) >= MIN_PATIENTS
    print(f"   {'PASSED' if p1 else '*** FAILED'} against a floor of {MIN_PATIENTS} in every cell")
    if not p1 and len(s_supp) < MIN_PATIENTS:
        print("   NOTE: too FEW suppressed windows means the confound is small, which is good news for E22")
        print("   and is still a gate failure — it makes P3 untestable, not passed (rule 31).")
    state = {"experiment": "E23", "table": os.path.basename(table),
             "p1": {"n_supp": len(s_supp), "n_clean": len(s_clean), "n_both": len(both),
                    "passed": bool(p1)}}
    if not p1:
        print("\n   Nothing downstream is reported: ABSENT, not negative (rule 31).")
        json.dump(state, open(OUT, "w"), indent=2, default=float)
        return 1

    # ------------------------------------------------------------------ P2
    print("\n" + "=" * 100)
    print("P2 — HOW MUCH OF THE ARM SEPARATION IS SUPPRESSION AT ALL (reported, not gating)")
    print("=" * 100)
    frac_supp = float(supp[unresp].mean()) if unresp.any() else float("nan")
    frac_supp_resp = float(supp[resp].mean()) if resp.any() else float("nan")
    m_sr = keep & np.isfinite(sr)
    sr_auc = auc_abs(y[m_sr], sr[m_sr]) if len(np.unique(y[m_sr])) == 2 else float("nan")
    print(f"   unresponsive windows with SR > 0 : {frac_supp:6.1%}")
    print(f"   responsive   windows with SR > 0 : {frac_supp_resp:6.1%}  "
          "(checked, not assumed to be zero)")
    print(f"   BIS/SR itself separates the arms with |AUC| {sr_auc:.3f} over {int(m_sr.sum())} rows")
    state["p2"] = {"frac_unresp_suppressed": frac_supp, "frac_resp_suppressed": frac_supp_resp,
                   "sr_arm_auc_abs": float(sr_auc)}

    # ------------------------------------------------------------------ P3
    print("\n" + "=" * 100)
    print(f"P3 — PRIMARY: {PRIMARY}'s arm AUC restricted to SR == 0 windows "
          f"(must retain >= {RETENTION_MIN:.0%})")
    print("=" * 100)
    full = keep & np.isfinite(x)
    restricted = full & clean
    med_full = float(np.nanmedian(bis[full & unresp])) if (full & unresp).any() else float("nan")
    med_rest = float(np.nanmedian(bis[restricted & unresp])) if (restricted & unresp).any() else float("nan")
    print(f"   the restriction shifts the unresponsive arm's median BIS {med_full:.1f} -> {med_rest:.1f}"
          f"  ({med_rest - med_full:+.1f}); a lighter arm is a narrower contrast and biases P3 DOWN")

    out3 = {}
    print(f"\n   {'stratum':22s} {'pats':>5s} {'rows':>6s} {'within-subject AUC':>20s} {'95% CI':>20s} "
          f"{'|AUC-.5|':>9s}")
    for tag, m in (("all unresp windows", full), ("SR == 0 only", restricted)):
        n_eval = n_evaluable_subjects(1 - y[m], x[m], subj[m])
        if n_eval < MIN_PATIENTS:
            print(f"   {tag:22s} {n_eval:5d} {int(m.sum()):6d}   too few evaluable patients")
            continue
        ym, xm, sm = 1 - y[m], x[m], subj[m]
        au = within_subject_auc(ym, xm, sm, direction)
        lo, hi, _ = cluster_bootstrap_ci(
            lambda i: within_subject_auc(ym[i], xm[i], sm[i], direction), sm, rng, reps=2000)
        out3[tag] = {"auc": au, "ci": [float(lo), float(hi)], "abs": abs(au - 0.5),
                     "n_patients": n_eval, "n_rows": int(m.sum())}
        print(f"   {tag:22s} {n_eval:5d} {int(m.sum()):6d} {au:20.3f} "
              f"{f'[{lo:.3f}, {hi:.3f}]':>20s} {abs(au - 0.5):9.3f}")
    if len(out3) < 2:
        print("\n   P3 is ABSENT: one stratum was not evaluable (rule 31).")
        p3 = None
    else:
        a, b = out3["all unresp windows"], out3["SR == 0 only"]
        retention = b["abs"] / a["abs"] if a["abs"] > 0 else float("nan")
        excludes = b["ci"][0] > 0.5 or b["ci"][1] < 0.5
        p3 = bool(np.isfinite(retention) and retention >= RETENTION_MIN and excludes)
        print(f"\n   retention {retention:.1%} of |AUC-0.5|; restricted CI "
              f"{'excludes' if excludes else 'INCLUDES'} 0.5")
        print(f"   P3 {'PASSED — the effect is not substantially suppression' if p3 else '*** FAILED — the effect is substantially burst suppression, and E22 must be described that way'}")
        state["p3"] = {"strata": out3, "retention": float(retention), "ci_excludes_half": bool(excludes),
                       "passed": p3}
    if p3 is None:
        state["p3"] = {"passed": None, "reason": "a stratum was not evaluable"}

    # ------------------------------------------------------------------ P4
    print("\n" + "=" * 100)
    print("P4 — THE CONVERSE: SR > 0 vs SR == 0 *within* the unresponsive arm (state held constant)")
    print("=" * 100)
    print("   A candidate that separates suppression from non-suppression far better than it separates")
    print("   unresponsive from responsive is a suppression detector, whatever P3 says.")
    print(f"\n   {'candidate':26s} {'arm |AUC-.5|':>13s} {'suppression |AUC-.5|':>21s} {'ratio':>8s}")
    out4 = {}
    for cname in REPORT:
        xc = col(cname)
        mm = keep & np.isfinite(xc)                              # the arm contrast, as in E22
        m4c = unresp & np.isfinite(sr) & np.isfinite(xc)         # suppressed vs not, INSIDE the deep arm
        lab = supp[m4c].astype(float)                            # 1 = the device scored suppression
        if (n_evaluable_subjects(1 - y[mm], xc[mm], subj[mm]) < MIN_PATIENTS
                or n_evaluable_subjects(lab, xc[m4c], subj[m4c]) < MIN_PATIENTS):
            continue
        d = REGISTRY.get(cname).predicted("unconscious_vs_awake") or "higher"
        arm_abs = abs(within_subject_auc(1 - y[mm], xc[mm], subj[mm], d) - 0.5)
        sup_abs = abs(within_subject_auc(lab, xc[m4c], subj[m4c], d) - 0.5)
        ratio = sup_abs / arm_abs if arm_abs > 0 else float("inf")
        out4[cname] = {"arm_abs": float(arm_abs), "suppression_abs": float(sup_abs),
                       "ratio": float(ratio)}
        print(f"   {cname:26s} {arm_abs:13.3f} {sup_abs:21.3f} {ratio:8.2f}")
    state["p4"] = out4

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if p3 is None:
        print("   ABSENT — a stratum was not evaluable, so nothing is concluded about the confound.")
        state["verdict"] = "absent"
    elif p3:
        print("   The state effect survives where the device reports no suppression at all. E22's result,")
        print("   if it has one, is not merely a burst-suppression detector. Note the direction of the")
        print("   remaining error: SR == 0 is the monitor's opinion, and leaving suppressed windows in that")
        print("   stratum makes this test EASIER, so a pass is the weaker of the two possible outcomes.")
        state["verdict"] = "survives_suppression_restriction"
    else:
        print("   The state effect does not survive the restriction. E22's headline is a statement about")
        print("   burst suppression and must be written as one — which is a solved problem the monitor")
        print("   already reports on a dedicated channel.")
        state["verdict"] = "is_substantially_suppression"
    json.dump(state, open(OUT, "w"), indent=2, default=float)
    print(f"\n   wrote {os.path.relpath(OUT, os.path.dirname(RESULTS))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
