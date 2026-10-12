#!/usr/bin/env python3
"""E46 -- Challenge C. Where BIS is DEMONSTRABLY WRONG, does a candidate stay put?

PRE-REGISTRATION. Written and committed before the statistic was computed. The cohort definition and the
BIS/EMG occupancy below are prior results re-verified here against the raw grid; the primary statistic has
never been run in any form.

---------------------------------------------------------------------------------------------------------
WHY THIS IS DIFFERENT FROM EVERY EARLIER CHALLENGE C ATTEMPT
---------------------------------------------------------------------------------------------------------
E26, E34 and E37 all scored a candidate against SEF95 and all three scoped themselves "never ahead of BIS".
None of them ever compared against BIS itself, and `REFERENCE_AGAINST_ALL_THREE.md` §3 names that as the
gap: the lightening-detection claim in the prior work is against real BIS, on VitalDB, where BIS is
recorded -- and we had never used that comparator.

The obstacle has always been that there is no ground truth for "how deep is this patient". This design
sidesteps it by not needing one. Instead of asking who is closer to the truth everywhere, it asks a much
narrower question on a small set of rows where **BIS is known to be wrong and the clinical record says so**.

THE ROWS, RE-VERIFIED HERE RATHER THAN INHERITED (rule 2). Of 5,845 grid windows with BIS and EMG and the
sensor attached, **168 read BIS >= 80 -- nominally awake -- and 164 of those sit INSIDE the anaesthetic
record**, i.e. between `anestart` and `aneend`, with an anaesthetic running. They are not light patients.
P(BIS >= 80) by EMG decile, recomputed here:

    deciles 1-8   0.0 %      (0 of 4,676 windows)
    decile 9      0.5 %      (3 of 584)
    decile 10    28.2 %      (165 of 585)

and filtering to EMG <= 35 leaves **5 rows across 4 patients**. This is the documented frontalis-EMG
artefact in which 70-110 Hz muscle power inflates the index, visible here on the device's OWN muscle
channel. (`ingestion/vitaldb.py` records 27.6 % for decile 10 against the 28.2 % computed here; the small
difference is a row-filter difference and the number reported by this experiment is the one it computes.)

So we have 164 windows with an external, EEG-independent reason to believe the monitor is wrong. **That
makes the interesting question answerable: does a candidate move when BIS moves, or does it stay where the
patient actually is?**

---------------------------------------------------------------------------------------------------------
DESIGN
---------------------------------------------------------------------------------------------------------
Everything is WITHIN CASE, because between-case variation in any of these measures is large and irrelevant
to the question. For each case carrying at least one artefact window and at least MIN_REF reference
windows:

    reference set   = that case's windows inside the anaesthetic with BIS < 80          (normal maintenance)
    artefact set    = that case's windows inside the anaesthetic with BIS >= 80         (BIS says awake)
    delta(measure)  = mean over the artefact set of (x - mean_ref) / sd_ref             (in the case's own SD)

    #####################################################################################################
    # THE FIRST VERSION OF THIS PRIMARY WAS A GATE THAT COULD NOT FAIL. IT IS KEPT BELOW AS ARM A,
    # LABELLED NON-INTERPRETABLE, BECAUSE DELETING IT WOULD HIDE THE ERROR.
    #
    # Registered primary, first version: |delta_BIS| - |delta_candidate| over windows selected by
    # BIS >= 80. It returned ROBUST for six candidates out of six, which is itself the tell (rule 18).
    # The artefact set is DEFINED by BIS crossing a threshold, so delta_BIS is mechanically bounded below
    # by (80 - mean_ref_BIS) / sd_ref_BIS -- computed here as a mean of 4.584 across cases, against an
    # observed 5.813. Any measure not used in the selection is unconstrained and must land beneath it.
    # No candidate could have failed. That is rule 40, committed in an experiment whose own test file was
    # written to check for rule 40 -- but the tests covered the CAPABILITY gate and G1 and never asked
    # whether the PRIMARY could fail.
    #
    # CORRECTED PRIMARY (ARM B): select on EMG instead. The artefact set is a case's windows in the top
    # decile of the deposit-wide EMG distribution (>= 32.4, the decile that carries 165 of the 168
    # BIS >= 80 windows). BIS is then a fair comparator because it played no part in the selection.
    #
    # AND ONE SELECTION-FREE COMPARISON THAT SURVIVES EITHER ARM: the ORDERING of |delta| among the
    # candidates. None of them was used to select any window, so their ranking is not biased by the
    # selection rule, in either arm. That ordering is what tests E43's mechanism.
    #####################################################################################################

PRIMARY (ARM B). |delta| for each candidate against |delta| for BIS over EMG-selected windows, aggregated
across cases, with a case-clustered bootstrap CI on the DIFFERENCE |delta_BIS| - |delta_candidate|.

THE CONFOUND IN ARM B, WHICH MUST BE STATED AND NOT ARGUED AWAY. Frontalis EMG genuinely rises as
anaesthesia lightens. So a measure that moves in the top EMG decile may be contaminated OR may be correctly
tracking a lighter patient, and this design cannot separate those. What it CAN do is rank the candidates
against each other under an identical exposure, which is the E43 test. The "BIS is demonstrably wrong"
framing does not survive into Arm B -- it belonged to Arm A, and Arm A is not interpretable.

PREDICTION, stated before the run. |delta_BIS| is large by construction -- BIS >= 80 against a case median
near 42 is several within-case SDs, and that is definitional, not a finding. The registered question is
whether the candidates are SMALL. Specifically:

  * `exponent_low` (1-20 Hz) is predicted to have the smallest |delta| of the spectral measures, because
    surface EMG lives at 20-45 Hz and a fit that stops at 20 Hz cannot absorb it. E43 reached the same
    conclusion from partial correlations; this is an independent test of it with a completely different
    statistic on a different subset of rows, which is the point (rule 20).
  * `exponent_high` (20-40 Hz) is predicted to have the LARGEST |delta| of the candidates, for the same
    reason in reverse. If it does not, E43's mechanism is wrong.
  * `whole_head_exponent` is predicted to sit between them.

VERDICT RULE, and it ENUMERATES THE WRONG-DIRECTION CASE EXPLICITLY (rule 37, which has now been violated
four times in this project, most recently by printing a refutation as a confirmation). For each candidate,
exactly one of:

  (a) REFUTED -- the CI on |delta_BIS| - |delta_cand| includes zero or lies BELOW zero. The candidate moves
      as much as, or more than, BIS at the artefact windows. It is not robust here.
  (b) ROBUST -- the CI lies entirely ABOVE zero AND the placebo gate below passes.
  (c) NOT INFORMATIVE -- the placebo fails, or the candidate has too little within-case variance to have
      been able to move at all (see the capability gate).

"Excludes zero" and "supports the hypothesis" are different questions; only (b) is a pass, and (a) is
written first so the failing case is the default reading.

PLACEBO (rules 34, 47, 48). Replace the artefact set with an equal-sized RANDOM draw from the same case's
reference windows, recompute everything, repeat PLACEBO_DRAWS times. This tests the STATISTIC, not the
biology: delta must be ~0 for every measure including BIS, because a random subset of a case's own
reference windows has no reason to deviate from that case's mean. The gate is a COMPARISON -- the real
|delta_BIS| must exceed its placebo -- never an absolute threshold. If the primary difference includes zero
the placebo branch prints NOT INFORMATIVE rather than PASSED, because a placebo cannot validate a null.

CAPABILITY GATE, and it is the one that makes the primary mean anything (rule 32). A measure that is
CONSTANT within a case scores delta = 0 and would win this test while being useless. So before the primary
is read, each measure must be shown to VARY within case: the median across cases of (within-case SD /
between-case SD) must exceed MIN_VAR_RATIO. A measure failing this is reported as NOT INFORMATIVE and its
delta is not interpreted. **This gate was constructed to be failable and is checked against a deliberately
constant column in `tests/test_e46_gates_can_fail.py`** (rule 40 -- this project has shipped two gates that
could not fail).

INCUMBENT (rule 45). BIS itself, on the same rows. That is the whole design.

---------------------------------------------------------------------------------------------------------
WHAT THIS CANNOT SHOW, STATED UP FRONT
---------------------------------------------------------------------------------------------------------
* It does not show a candidate tracks anaesthetic depth better than BIS in general. It shows behaviour on
  164 windows selected precisely because BIS failed on them, which is a biased sample of the recording by
  construction -- and deliberately so. The claim it can support is "robust to the artefact that produces
  BIS's documented failure mode", not "better monitor".
* A candidate can be flat here because it is genuinely EMG-robust or because it is insensitive to
  everything. The capability gate addresses the second reading but does not eliminate it.
* VitalDB is two frontal channels at 128 Hz (Nyquist 64), maintenance only. Induction and emergence are not
  in this deposit at all -- the sensor goes on after induction and comes off around emergence.
* Artefact windows are concentrated in a minority of cases, so the case-clustered bootstrap is doing real
  work and the effective n is cases, not windows.

    python -m bsde.experiments.e46_bis_artefact_windows
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.verifier.stats import cluster_bootstrap_ci                                    # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
GRID = os.path.join(RESULTS, "vitaldb_grid.csv")
OUT = os.path.join(RESULTS, "e46_bis_artefact_windows.json")

BIS, EMG, SENSOR_OFF = "meta_bis", "meta_emg", "meta_sensor_off"
REL_ANEEND = "meta_rel_aneend_s"
CASE = "meta_caseid"

CANDIDATES = ("exponent_low", "exponent_high", "whole_head_exponent",
              "lempel_ziv", "relative_alpha_power", "spectral_edge_95", "uce_v1")

BIS_AWAKE = 80.0
"""The threshold that defines an artefact window. NOT tuned here: 80 is the conventional upper bound of the
BIS 'awake' range and the same value `ingestion/vitaldb.py` used when it characterised these windows. It is
fixed before the run and no other value is tried."""

MIN_REF = 8
"""Reference windows a case needs before its within-case SD is trusted. With fewer, sd_ref is unstable and
delta is divided by noise."""

MIN_CASES = 20
MIN_VAR_RATIO = 0.10
PLACEBO_DRAWS = 200
REPS = 20000
"""20,000 rather than the 2,000 that used to be standard here. Rule 46: E36's registered verdict flipped
across RNG seeds at 2,000 because its margin was the size of its Monte Carlo error. The extra cost is
seconds and it removes an entire class of un-reproducible verdict."""
SEED = 20260731


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:                                                          # noqa: BLE001
        return None


def _load():
    import csv
    with open(GRID) as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("status") == "ok"]
    keep = []
    for r in rows:
        b, e = _f(r.get(BIS)), _f(r.get(EMG))
        if b is None or e is None:
            continue
        if (_f(r.get(SENSOR_OFF)) or 0.0) > 0.5:
            continue
        ane = _f(r.get(REL_ANEEND))
        if ane is None or ane > 0:            # keep only windows INSIDE the anaesthetic record
            continue
        keep.append(r)
    return keep


def _case_deltas(rows, measures, artefact_pick=None, rng=None, select="bis", emg_cut=None):
    """Per-case within-case delta for each measure.

    `select` picks the ARM. "bis" reproduces the original selection (BIS >= 80) and is retained only so the
    non-interpretable Arm A can be printed alongside its mechanical bound. "emg" is the corrected primary:
    the artefact set is the case's windows at or above `emg_cut`, a deposit-wide threshold that BIS played
    no part in choosing. `artefact_pick="placebo"` overrides either with a random draw from the case's own
    reference windows.
    """
    by_case = {}
    for r in rows:
        by_case.setdefault(r[CASE], []).append(r)
    out = {m: [] for m in measures}
    cases = []
    for cid, rs in sorted(by_case.items()):
        if select == "emg":
            art_mask = [(_f(r.get(EMG)) or -1.0) >= emg_cut for r in rs]
        else:
            art_mask = [(_f(r.get(BIS)) or 0.0) >= BIS_AWAKE for r in rs]
        n_art = sum(art_mask)
        if n_art == 0:
            continue
        ref = [r for r, a in zip(rs, art_mask) if not a]
        if len(ref) < MIN_REF:
            continue
        if artefact_pick == "placebo":
            idx = rng.choice(len(ref), size=min(n_art, len(ref)), replace=False)
            art = [ref[i] for i in idx]
            ref_used = [ref[i] for i in range(len(ref)) if i not in set(idx.tolist())]
            if len(ref_used) < MIN_REF:
                continue
        else:
            art = [r for r, a in zip(rs, art_mask) if a]
            ref_used = ref
        row_ok = False
        vals = {}
        for m in measures:
            rv = [_f(r.get(m)) for r in ref_used]
            rv = [z for z in rv if z is not None]
            av = [_f(r.get(m)) for r in art]
            av = [z for z in av if z is not None]
            if len(rv) < MIN_REF or not av:
                vals[m] = float("nan")
                continue
            sd = float(np.std(rv, ddof=1))
            if sd <= 0:
                vals[m] = float("nan")
                continue
            vals[m] = float((np.mean(av) - np.mean(rv)) / sd)
            row_ok = True
        if row_ok:
            cases.append(cid)
            for m in measures:
                out[m].append(vals[m])
    return cases, {m: np.asarray(v, float) for m, v in out.items()}


def _variance_capability(rows, measures):
    """Median across cases of (within-case SD / between-case SD). The gate that stops a constant winning."""
    by_case = {}
    for r in rows:
        by_case.setdefault(r[CASE], []).append(r)
    out = {}
    for m in measures:
        case_means, within = [], []
        for _cid, rs in by_case.items():
            v = [_f(r.get(m)) for r in rs]
            v = [z for z in v if z is not None]
            if len(v) < MIN_REF:
                continue
            case_means.append(float(np.mean(v)))
            within.append(float(np.std(v, ddof=1)))
        between = float(np.std(case_means, ddof=1)) if len(case_means) > 2 else float("nan")
        out[m] = float(np.median(within) / between) if between and math.isfinite(between) and between > 0 \
            else float("nan")
    return out


def _mechanical_bound(rows):
    """The smallest delta_BIS the BIS >= 80 selection rule PERMITS, averaged over cases. If the observed
    delta_BIS sits near this, the Arm A comparison is measuring its own selection rule."""
    by_case = {}
    for r in rows:
        by_case.setdefault(r[CASE], []).append(r)
    lb = []
    for _cid, rs in by_case.items():
        art = [r for r in rs if (_f(r.get(BIS)) or 0.0) >= BIS_AWAKE]
        ref = [_f(r.get(BIS)) for r in rs if (_f(r.get(BIS)) or 0.0) < BIS_AWAKE]
        ref = [z for z in ref if z is not None]
        if not art or len(ref) < MIN_REF:
            continue
        sd = float(np.std(ref, ddof=1))
        if sd > 0:
            lb.append((BIS_AWAKE - float(np.mean(ref))) / sd)
    return float(np.mean(lb)) if lb else float("nan")


def main() -> int:
    rng = np.random.default_rng(SEED)
    rows = _load()
    measures = (BIS,) + CANDIDATES
    # Drop columns that are not populated at all before anything is designed around them (rule 6:
    # `observation_concept_id` was 100 % zero and one Counter would have shown it in seconds). uce_v1 is
    # 0/6439 in this grid, and an absent column must be reported as ABSENT, not as "too flat".
    absent = tuple(m for m in measures
                   if not any(_f(r.get(m)) is not None for r in rows))
    measures = tuple(m for m in measures if m not in absent)
    emg_all = sorted(z for z in (_f(r.get(EMG)) for r in rows) if z is not None)
    emg_cut = float(np.percentile(emg_all, 90))
    cases, deltas = _case_deltas(rows, measures)
    n_art = sum(1 for r in rows if (_f(r.get(BIS)) or 0.0) >= BIS_AWAKE)

    print("=" * 100)
    print("E46 -- where BIS is demonstrably wrong, does a candidate stay put?")
    print("=" * 100)
    print(f"windows inside anaesthetic, sensor attached : {len(rows)}")
    print(f"   of which BIS >= {BIS_AWAKE:.0f} (artefact)          : {n_art}")
    print(f"cases evaluable (>= {MIN_REF} reference windows) : {len(cases)}")
    if len(cases) < MIN_CASES:
        print(f"\nG1 FAILED: {len(cases)} evaluable cases < {MIN_CASES}. No verdict is emitted.")
        json.dump({"gate": "G1_failed", "n_cases": len(cases)}, open(OUT, "w"), indent=2)
        return 1
    print(f"G1 PASSED: {len(cases)} >= {MIN_CASES}")

    cap = _variance_capability(rows, measures)
    print(f"\nCAPABILITY GATE -- median within-case SD / between-case SD (floor {MIN_VAR_RATIO}):")
    for m in measures:
        flag = "ok" if (math.isfinite(cap[m]) and cap[m] >= MIN_VAR_RATIO) else "TOO FLAT -> NOT INFORMATIVE"
        print(f"   {m:24s} {cap[m]:7.3f}   {flag}")

    # ------------------------------------------------------------------ ARM A, retained but NOT a result
    bound = _mechanical_bound(rows)
    real_a = {m: float(np.nanmean(np.abs(deltas[m]))) for m in measures}
    print("\n" + "=" * 100)
    print("ARM A (BIS-selected) -- NON-INTERPRETABLE, printed so the error is visible rather than deleted")
    print("=" * 100)
    print(f"   delta_BIS observed                         : {real_a[BIS]:.3f}")
    print(f"   delta_BIS FORCED by the BIS >= 80 rule     : {bound:.3f}   (mean per-case lower bound)")
    print("   Every candidate is unconstrained by that rule and must land below it, so no candidate")
    print("   could have failed this comparison. Rule 40. Arm A emits no verdict.")

    # ------------------------------------------------------------------ ARM B, the corrected primary
    cases, deltas = _case_deltas(rows, measures, select="emg", emg_cut=emg_cut)
    subj = np.asarray(cases)
    if len(cases) < MIN_CASES:
        print(f"\nARM B G1 FAILED: {len(cases)} evaluable cases < {MIN_CASES}. No verdict.")
        json.dump({"gate": "armB_G1_failed", "n_cases": len(cases)}, open(OUT, "w"), indent=2)
        return 1
    pl = {m: [] for m in measures}
    for _ in range(PLACEBO_DRAWS):
        _c, d = _case_deltas(rows, measures, artefact_pick="placebo", rng=rng,
                             select="emg", emg_cut=emg_cut)
        for m in measures:
            v = d[m][np.isfinite(d[m])]
            if v.size:
                pl[m].append(float(np.mean(np.abs(v))))
    placebo = {m: (float(np.mean(pl[m])) if pl[m] else float("nan")) for m in measures}
    bis_d = deltas[BIS]
    real = {m: float(np.nanmean(np.abs(deltas[m]))) for m in measures}

    print("\n" + "=" * 100)
    print(f"ARM B (EMG-selected, top decile >= {emg_cut:.1f}) -- the corrected primary")
    print("=" * 100)
    print(f"   evaluable cases: {len(cases)}")
    print(f"\n   {'measure':24s} {'|delta|':>9s} {'placebo':>9s}")
    print("   " + "-" * 60)
    for m in sorted(measures, key=lambda z: real[z]):
        tag = "  <- INCUMBENT" if m == BIS else ""
        print(f"   {m:24s} {real[m]:9.3f} {placebo[m]:9.3f}{tag}")

    print("\n   ORDERING AMONG CANDIDATES -- selection-free, and the actual test of E43's mechanism.")
    print("   E43 predicted exponent_low (1-20 Hz) clearly steadier than exponent_high (20-40 Hz),")
    print("   because surface EMG lives at 20-45 Hz.")
    lo_v, hi_v = real.get("exponent_low", float("nan")), real.get("exponent_high", float("nan"))
    print(f"      exponent_low  {lo_v:.3f}")
    print(f"      exponent_high {hi_v:.3f}")
    print(f"      gap (high - low) = {hi_v - lo_v:+.3f}   "
          f"{'as E43 predicts' if hi_v - lo_v > 0 else 'OPPOSITE to E43'}")

    print(f"\nPRIMARY -- |delta_BIS| - |delta_candidate|, case-clustered bootstrap, {REPS} resamples")
    print("-" * 100)
    results = {}
    for m in [c for c in CANDIDATES if c in measures]:
        cd = deltas[m]

        def stat(idx, _b=bis_d, _c=cd):
            a, b = np.abs(_b[idx]), np.abs(_c[idx])
            ok = np.isfinite(a) & np.isfinite(b)
            return float(np.mean(a[ok]) - np.mean(b[ok])) if ok.sum() >= 5 else float("nan")

        lo, hi, n_ok = cluster_bootstrap_ci(stat, subj, np.random.default_rng(SEED), reps=REPS)
        point = stat(np.arange(len(subj)))
        # resample-level p on the wrong side of the null (rule 46) -- degrades gracefully where an
        # interval endpoint does not.
        draws = []
        r2 = np.random.default_rng(SEED + 1)
        uniq = np.unique(subj)
        idx_by = {u: np.flatnonzero(subj == u) for u in uniq}
        for _ in range(REPS):
            dr = r2.choice(uniq, size=len(uniq), replace=True)
            v = stat(np.concatenate([idx_by[u] for u in dr]))
            if math.isfinite(v):
                draws.append(v)
        p_wrong = float(np.mean(np.asarray(draws) <= 0.0)) if draws else float("nan")

        flat = not (math.isfinite(cap[m]) and cap[m] >= MIN_VAR_RATIO)
        placebo_ok = (math.isfinite(placebo[BIS]) and real[BIS] > placebo[BIS])
        includes_zero = not (math.isfinite(lo) and math.isfinite(hi)) or (lo <= 0.0 <= hi)

        # VERDICT -- the failing cases are written FIRST and the wrong direction is named explicitly.
        if flat:
            verdict = "NOT INFORMATIVE (too flat within case to have moved)"
        elif includes_zero:
            verdict = "REFUTED (interval includes zero: no evidence it is steadier than BIS)"
        elif hi < 0.0:
            verdict = "REFUTED IN THE OPPOSITE DIRECTION (it moves MORE than BIS)"
        elif not placebo_ok:
            verdict = "NOT INFORMATIVE (placebo gate: BIS did not beat its own placebo)"
        else:
            verdict = "ROBUST (steadier than BIS at the artefact windows)"
        results[m] = {"delta_abs": real[m], "placebo": placebo[m], "diff_vs_bis": point,
                      "ci": [lo, hi], "p_wrong_side": p_wrong, "var_ratio": cap[m],
                      "verdict": verdict, "n_boot_ok": n_ok}
        print(f"   {m:21s} diff {point:+7.3f}  [{lo:+7.3f}, {hi:+7.3f}]  p(wrong side) {p_wrong:.4f}")
        print(f"   {'':21s} -> {verdict}")

    payload = {"n_windows": len(rows), "n_artefact_bis": n_art, "n_cases_armB": len(cases),
               "absent_columns": list(absent),
               "armA_non_interpretable": {"bis_delta_abs": real_a.get(BIS),
                                          "mechanical_lower_bound": bound,
                                          "reason": "artefact set defined by BIS crossing a threshold, so "
                                                    "delta_BIS is forced large and no candidate could fail"},
               "armB_emg_cut": emg_cut,
               "bis_delta_abs": real[BIS], "bis_placebo": placebo[BIS],
               "capability": cap, "results": results,
               "reps": REPS, "seed": SEED, "bis_awake_threshold": BIS_AWAKE}
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(payload, open(OUT, "w"), indent=2)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
