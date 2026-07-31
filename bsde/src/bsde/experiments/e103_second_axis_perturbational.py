"""E103 -- IS THERE A SECOND AXIS? Does a perturbational response carry state information the spontaneous
aperiodic exponent does not?

REGISTERED BEFORE THE EXTRACTION IT CONSUMES HAS FINISHED. `extract_ds005620_perturbation.py` was launched
at the same commit boundary; it reads no state label beyond the BIDS `task-` entity in the filename and
computes no contrast.

=========================================================================================================
WHY THIS IS THE EXPERIMENT
=========================================================================================================
Challenge A has been validation-shaped -- "is measure X confounded?" -- whose best outcome is a licence,
never a finding. And the session's results converge on one statement worth taking seriously as a claim:

    **everything this project has measured is a single arousal axis.**

`uce_v1` turned out to be the whole-head exponent restated. E92 found no decoupling between two regions.
E73 and E86's network measures reduce to mean connectivity. E93, E95 and E100 all order states on arousal,
and in two independent tests REM's placement was measurably muscle. That is a coherent negative result,
and the question it raises is not "is the axis confounded" but **"is there a second one".**

Perturbational complexity is the best-established candidate for a second axis (Casali et al. 2013,
PMID 23946194), because it is the measure that reportedly separates states which spontaneous EEG conflates.
ds005620 carries `task-awake` and `task-sed` TMS recordings within the same subjects.

=========================================================================================================
ESTIMAND -- decoupling, not increment
=========================================================================================================
The increment framing has failed repeatedly in this project for a reason (E84, E89, E99): an increment
answers "is it useful", and the question here is "is it the same thing". So:

  1. Per recording, the perturbational quantity is the REAL-MINUS-SHAM contrast, never the real value:
         pert = real_evoked_lz - sham_evoked_lz
     The sham epochs sit midway between consecutive detected pulses in the SAME recording, same length,
     same channels, same pipeline, same count. Rule 28: two measurements separated in time are not thereby
     measuring different things, and the sham is what makes the difference a perturbational one.

  2. Across recordings, `pert` is regressed on `spont_exponent` (ordinary least squares, one line) and the
     RESIDUAL is taken. This is the spontaneous axis removed from the perturbational measure.

  3. P  paired d_z of the residual, awake minus sedated, WITHIN subject.

     Multiple `sed` runs per subject are averaged within subject x task before pairing. The label is
     constant inside each aggregation group, so this is not the look-ahead of rule 10 -- stated because
     rule 10 was earned by seventeen scripts that aggregated without saying why it was safe.

VERDICT, wrong direction FIRST (rule 37):

    (a) interval excludes 0 and SEDATED IS HIGHER -> INVERTED. Sedation would be increasing perturbational
        complexity after the spontaneous axis is removed. That is not a second axis, it is a measure
        running backwards, and the most likely cause is residual artefact -- read G3 and `blank_frac`
        before anything else. Must print as a failure, not as "an effect".
    (b) interval includes 0 -> NO SECOND AXIS DETECTED. The perturbational response carries no state
        information beyond the spontaneous exponent on this deposit. This is the outcome consistent with
        everything else in the session, and it strengthens the single-axis reading rather than being a
        null to explain away.
    (c) interval excludes 0 and AWAKE IS HIGHER -> A SECOND AXIS IS DETECTED. The perturbational response
        separates states after the spontaneous exponent is removed. **This would be the first thing in
        this project that is not the arousal axis**, and the qualifications in the scope note travel with
        it permanently.

PREDICTED: (c), at roughly 40 % -- and the prediction is logged with that number because the project's
calibration record is the point of logging predictions at all. The honest reason it is not higher: three
measures predicted to be new turned out to be redundant (rule 28), and this deposit's sedation is light.

=========================================================================================================
GATES (rule 40) -- G2 is the one the feasibility note demanded and it can end this
=========================================================================================================
    G1  COVERAGE. >= 12 subjects contributing BOTH an awake and a sedated recording with status ok.
    G2  A PERTURBATION WAS ACTUALLY MEASURED. Paired across recordings, `real_evoked_rms` must exceed
        `sham_evoked_rms` with a bootstrap interval excluding 0. **If it fails, the verdict is ABSENT, not
        negative** (rule 31): no response was detected, so nothing was tested. The feasibility note put
        this in writing before any extraction -- "a perturbational measure still needs a mandatory gate
        showing the evoked response survives past the artefact window".
    G3  DETECTION PARITY (rule 32). `n_pulses`, `iti_median` and `det_separation` must not differ between
        awake and sedated arms. A slew detector will behave differently against a sedated background, and
        if it does, the contrast is between two detection rates wearing the name of a brain difference.
        Reported per arm and gated: any of the three differing with an interval excluding 0 downgrades the
        verdict to CONFOUNDED-BY-DETECTION regardless of the primary.
    G4  POSITIVE CONTROL. `spont_exponent` must itself separate awake from sedated. If the known effect is
        absent, the state labels, the recordings or the extraction are wrong and nothing above is
        interpretable. Rule 63: compared against a Gaussian control on the same pairs, not a threshold.
    G5  THE REGRESSION MUST BE NON-DEGENERATE. `spont_exponent` must vary across recordings and its
        correlation with `pert` must be finite; residualising on a constant returns the original variable
        and the "decoupling" would be vacuous. This is E96's C1 failure -- a condition satisfied at
        0.000002 -- and it is written as a real condition here because of it.

PLACEBO, and it GATES the verdict (rule 34). The awake/sedated labels are FLIPPED at random within
subject, 500 draws -- which for a two-condition paired design is the exact permutation null. The whole
procedure, including the regression and the residualisation, is recomputed inside each draw, because the
regression is fitted on data whose labels the placebo changes. Real d_z inside the placebo's central 95 %
is WITHDRAWN.

SECOND PLACEBO, and it is the one that matters most: the identical analysis run on `sham_evoked_lz` ALONE.
If the sham separates the states as well as real-minus-sham does, then what is being measured is the
complexity of ongoing EEG and the word "perturbational" is decoration. Reported beside the primary always.

=========================================================================================================
EXCLUSIONS, STATED BEFORE THE RUN
=========================================================================================================
**sub-1016 and sub-1074 are excluded entirely.** sub-1016 was the subject used in all five feasibility
diagnostics and in the extractor's smoke test; sub-1074's rows were the last lines of the extraction logs
and were read while checking the run had finished. In both cases feature values were seen alongside task
labels before this design was registered. Rule 26: smoke-test on permuted labels, never real ones -- the
exclusions are the remedy for having broken it, and they are named here rather than quietly applied. This
leaves 14 subjects contributing both conditions, above G1's 12; the exclusion was decided on the burn-in
ground alone and not after checking what it did to the count.

**EXCLUSION-RELATEDNESS IS REPORTED, NOT ASSUMED AWAY (rule 14).** Two of 55 recordings returned
`too_few_pulses`, and the design cannot pretend that is neutral: if detection fails preferentially in one
arm, the analysed set is selected on a proxy for state. The status breakdown BY TASK is printed before the
primary and any imbalance is named in the verdict.

=========================================================================================================
SCOPE
=========================================================================================================
ds005620, 64-channel scalp EEG, sedation not general anaesthesia. `evoked_lz` is a PCI-FAMILY measure
computed on a fixed per-channel threshold, **not** PCI-st and not Casali's bootstrap significance map; it
is a simplification and must be described as one. A positive result would mean a perturbational measure
carries state information beyond the spontaneous exponent ON THIS DEPOSIT. It would NOT be evidence about
consciousness: no experiential report, no responsiveness assessment and no behavioural measure exists in
this deposit, and nothing here may be described as detecting or measuring consciousness.
"""
from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
TABLE = os.path.join(RESULTS, "ds005620_perturbation.csv")
OUT = os.path.join(RESULTS, "e103_second_axis_perturbational.json")

EXCLUDE_SUBJECTS = {"1016", "1074"}    # feasibility + smoke + log-tail burn-in, rule 26
MIN_SUBJECTS = 12
REPS = 4000
PLACEBO_DRAWS = 500
SEED = 20260731


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def dz(diffs):
    d = np.asarray([x for x in diffs if np.isfinite(x)], float)
    if d.size < 3 or d.std(ddof=1) <= 0:
        return float("nan")
    return float(d.mean() / d.std(ddof=1))


def ci(vals):
    v = np.sort(np.asarray([x for x in vals if np.isfinite(x)], float))
    if v.size < 50:
        return float("nan"), float("nan")
    return float(np.quantile(v, .025)), float(np.quantile(v, .975))


def residualise(y, x):
    """y with the best-fit line on x removed. Returns y unchanged (and a flag) if x does not vary."""
    ok = np.isfinite(y) & np.isfinite(x)
    if ok.sum() < 5 or np.ptp(x[ok]) <= 1e-12:
        return y.copy(), False
    b, a = np.polyfit(x[ok], y[ok], 1)
    r = y - (a + b * x)
    r[~ok] = np.nan
    return r, True


def paired(by_subject, values, labels):
    """awake-minus-sed differences, one per subject, averaging repeated runs within subject x task."""
    out = []
    for s, idxs in by_subject.items():
        aw = [values[i] for i in idxs if labels[i] == "awake" and np.isfinite(values[i])]
        se = [values[i] for i in idxs if labels[i] == "sed" and np.isfinite(values[i])]
        if aw and se:
            out.append(float(np.mean(aw) - np.mean(se)))
    return np.array(out, float)


def main() -> int:
    if not os.path.exists(TABLE):
        print(f"ABSENT: {TABLE} -- extraction has not landed")
        return 2
    allrows = list(csv.DictReader(open(TABLE, newline="")))
    drop = defaultdict(lambda: defaultdict(int))
    for r in allrows:
        drop[r.get("task", "?")][r.get("status", "?")] += 1
    print("extraction status by arm (rule 14 -- exclusions are reported, not assumed neutral):")
    for t in sorted(drop):
        print(f"   {t:<6s} " + "  ".join(f"{k}={v}" for k, v in sorted(drop[t].items())))
    rows = [r for r in allrows
            if r.get("status") == "ok" and r.get("subject") not in EXCLUDE_SUBJECTS
            and r.get("task") in ("awake", "sed")]
    res = {"n_rows": len(rows), "excluded_subjects": sorted(EXCLUDE_SUBJECTS),
           "status_by_arm": {t: dict(v) for t, v in drop.items()}, "gates": {}}

    subj = [r["subject"] for r in rows]
    task = [r["task"] for r in rows]
    by = defaultdict(list)
    for i, s in enumerate(subj):
        by[s].append(i)
    both = {s: ix for s, ix in by.items()
            if any(task[i] == "awake" for i in ix) and any(task[i] == "sed" for i in ix)}
    res["gates"]["G1_subjects"] = len(both)
    res["gates"]["G1_pass"] = bool(len(both) >= MIN_SUBJECTS)
    print(f"{len(rows)} ok recordings, {len(by)} subjects; {len(both)} with BOTH conditions "
          f"(sub-1016 excluded as burn-in)")
    print(f"G1 coverage  {'PASS' if res['gates']['G1_pass'] else 'FAIL'} "
          f"({len(both)} >= {MIN_SUBJECTS})")
    if not res["gates"]["G1_pass"]:
        res["verdict"] = "GATE-FAILED -- the within-subject design is not populated"
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    col = lambda k: np.array([_f(r.get(k, "")) for r in rows], float)   # noqa: E731
    real_lz, sham_lz = col("real_evoked_lz"), col("sham_evoked_lz")
    spont = col("spont_exponent")
    pert = real_lz - sham_lz
    rng = np.random.default_rng(SEED)

    # ---- G2: was a perturbation measured at all? -------------------------------------------------
    d_rms = col("real_evoked_rms") - col("sham_evoked_rms")
    ok = np.isfinite(d_rms)
    g2_lo, g2_hi = ci([float(np.mean(d_rms[ok][rng.integers(0, ok.sum(), ok.sum())]))
                       for _ in range(REPS)]) if ok.sum() >= 5 else (float("nan"), float("nan"))
    g2 = bool(np.isfinite(g2_lo) and g2_lo > 0)
    res["gates"]["G2_real_minus_sham_rms"] = {"mean": float(np.mean(d_rms[ok])), "lo": g2_lo, "hi": g2_hi}
    res["gates"]["G2_pass"] = g2
    print(f"G2 response  real-minus-sham evoked RMS {np.mean(d_rms[ok]):+.4f} "
          f"[{g2_lo:+.4f}, {g2_hi:+.4f}]  {'PASS' if g2 else 'FAIL'}")
    if not g2:
        res["verdict"] = ("ABSENT -- no perturbational response was detected above the sham, so nothing "
                          "was tested. This is not a negative result about a second axis (rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # ---- G3: detection parity ---------------------------------------------------------------------
    g3_detail, g3 = {}, True
    for k in ("n_pulses", "iti_median", "det_separation"):
        d = paired(both, col(k), task)
        lo, hi = ci([float(np.mean(d[rng.integers(0, d.size, d.size)])) for _ in range(REPS)])
        differs = bool(np.isfinite(lo) and not (lo <= 0.0 <= hi))
        g3_detail[k] = {"awake_minus_sed": float(np.mean(d)), "lo": lo, "hi": hi, "differs": differs}
        g3 = g3 and not differs
        print(f"G3 detect    {k:<16s} awake-sed {np.mean(d):+9.4f} [{lo:+9.4f}, {hi:+9.4f}]  "
              f"{'DIFFERS' if differs else 'ok'}")
    res["gates"]["G3_detail"] = g3_detail
    res["gates"]["G3_pass"] = g3

    # ---- G4: positive control ---------------------------------------------------------------------
    d_sp = paired(both, spont, task)
    sp_dz = dz(d_sp)
    noise = np.array([dz(rng.normal(size=d_sp.size)) for _ in range(2000)])
    g4 = bool(np.isfinite(sp_dz) and abs(sp_dz) > np.quantile(np.abs(noise), 0.95))
    res["gates"]["G4_spont_dz"] = sp_dz
    res["gates"]["G4_noise_95"] = float(np.quantile(np.abs(noise), 0.95))
    res["gates"]["G4_pass"] = g4
    print(f"G4 known     spont_exponent awake-sed d_z {sp_dz:+.4f}  vs Gaussian 95th "
          f"{np.quantile(np.abs(noise), 0.95):.4f}  {'PASS' if g4 else 'FAIL'}")

    # ---- G5: the regression must be non-degenerate ------------------------------------------------
    okr = np.isfinite(pert) & np.isfinite(spont)
    spread = float(np.ptp(spont[okr])) if okr.sum() >= 5 else 0.0
    resid, fitted = residualise(pert, spont)
    g5 = bool(fitted and spread > 0.05)
    res["gates"]["G5_spont_spread"] = spread
    res["gates"]["G5_pass"] = g5
    print(f"G5 regressor spont_exponent spread {spread:.4f} over {int(okr.sum())} recordings  "
          f"{'PASS' if g5 else 'FAIL -- residualising on a constant is vacuous'}")
    if not (g4 and g5):
        res["verdict"] = ("ABSENT -- a precondition failed (G4 known effect and/or G5 non-degenerate "
                          "regressor), so the decoupling was not testable here (rule 31).")
        print(f"\nVERDICT: {res['verdict']}")
        json.dump(res, open(OUT, "w"), indent=2)
        return 1

    # ---- PRIMARY ----------------------------------------------------------------------------------
    d_res = paired(both, resid, task)
    point = dz(d_res)
    boot = [dz(d_res[rng.integers(0, d_res.size, d_res.size)]) for _ in range(REPS)]
    lo, hi = ci(boot)
    res["primary"] = {"d_z": point, "lo": lo, "hi": hi, "n_subjects": int(d_res.size)}
    print(f"\nP  residual(pert | spont) awake-minus-sed  d_z {point:+.4f}  [{lo:+.4f}, {hi:+.4f}]  "
          f"over {d_res.size} subjects")

    # ---- SECOND PLACEBO: sham alone ---------------------------------------------------------------
    sham_res, _ = residualise(sham_lz, spont)
    d_sham = paired(both, sham_res, task)
    sh_dz = dz(d_sham)
    sh_lo, sh_hi = ci([dz(d_sham[rng.integers(0, d_sham.size, d_sham.size)]) for _ in range(REPS)])
    res["placebo_sham_alone"] = {"d_z": sh_dz, "lo": sh_lo, "hi": sh_hi}
    print(f"   SHAM ALONE, same pipeline                d_z {sh_dz:+.4f}  [{sh_lo:+.4f}, {sh_hi:+.4f}]"
          f"   <- if this matches P, 'perturbational' is decoration")

    # ---- PLACEBO: labels flipped within subject, whole procedure refit -----------------------------
    pl = []
    for _ in range(PLACEBO_DRAWS):
        flip = {s: bool(rng.integers(0, 2)) for s in both}
        lab = [("sed" if flip[subj[i]] and task[i] == "awake" else
                "awake" if flip[subj[i]] and task[i] == "sed" else task[i])
               for i in range(len(rows))]
        r2, ok2 = residualise(pert, spont)       # regression does not use labels, but refit for symmetry
        v = dz(paired(both, r2, lab))
        if np.isfinite(v):
            pl.append(v)
    p_lo, p_hi = ci(pl)
    inside = bool(np.isfinite(p_lo) and p_lo <= point <= p_hi)
    res["placebo_label_flip"] = {"lo": p_lo, "hi": p_hi, "n_draws": len(pl), "inside": inside}
    print(f"\nPLACEBO label flip within subject: [{p_lo:+.4f}, {p_hi:+.4f}]   "
          f"real {'INSIDE -- WITHDRAWN' if inside else 'outside'}")

    excl = not (lo <= 0.0 <= hi)
    if inside:
        v = ("WITHDRAWN BY PLACEBO -- flipping the labels at random reproduces the effect; there is no "
             "state information in the residual")
    elif not g3:
        v = ("CONFOUNDED BY DETECTION -- the pulse detector behaves differently in the two arms, so this "
             "contrast is between two detection rates and not between two brains (rule 32)")
    elif excl and point < 0:
        v = ("INVERTED -- sedation raises perturbational complexity after the spontaneous axis is "
             "removed. This is a measure running backwards, most likely residual artefact; it is NOT a "
             "second axis and must not be reported as an effect")
    elif not excl:
        v = ("NO SECOND AXIS DETECTED -- the perturbational response carries no state information beyond "
             "the spontaneous exponent on this deposit. Consistent with the single-axis reading that "
             "every other Challenge A result this session supports")
    elif np.isfinite(sh_lo) and not (sh_lo <= 0.0 <= sh_hi) and abs(sh_dz) >= abs(point):
        v = ("NOT PERTURBATIONAL -- the effect survives label flipping but the SHAM alone matches or beats "
             "it, so what separates the states is the complexity of ongoing EEG, not the response to "
             "stimulation")
    else:
        v = ("A SECOND AXIS IS DETECTED -- the perturbational response separates awake from sedated after "
             "the spontaneous exponent is removed, it survives the label-flip placebo, and the sham does "
             "not reproduce it. Scope note travels with this permanently: no experiential report exists "
             "in this deposit and nothing here detects consciousness")
    res["verdict"] = v
    print(f"\nVERDICT: {v}")
    json.dump(res, open(OUT, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
