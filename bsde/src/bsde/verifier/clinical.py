"""Verifier layer 7 — clinical. Would using this measure help, on one patient, at real prevalence?

WHAT THIS LAYER ADDS THAT LAYERS 2 AND 5 DO NOT.

Layer 2 reports AUC and calibration. **AUC is prevalence-free and threshold-free, and clinical use is
neither.** A measure with AUC 0.86 is a fine measure and says nothing about what happens when someone has to
pick a cut-off and act on one patient drawn from a population where the condition is rare. Calibration
(already checked in layer 2) is necessary for that and not sufficient: a perfectly calibrated measure can
still be useless if acting on it does more harm than treating everyone or no one.

Layer 5 asks whether one window is stable enough to read. This layer asks whether reading it changes what
you would do.

FOUR CHECKS.

1. `prevalence_sensitivity` — POSITIVE PREDICTIVE VALUE AT A DECLARED PREVALENCE.
   **The sample prevalence is a design choice, not a fact about the world**, and every cohort in this project
   is close to 50/50 by construction: Chennu contributes one baseline and one sedated window per subject,
   Sleep-EDF one wake and one N3. Computing PPV from that is computing PPV for a world in which half of all
   patients are unconscious. Prevalence must therefore be SUPPLIED, and this check reports how PPV moves
   across the supplied range rather than quoting one number.

2. `operating_point` — SENSITIVITY AND SPECIFICITY AT THRESHOLDS FIXED BY A DECLARED RULE.
   The thresholds are the ones achieving a target sensitivity and a target specificity, chosen by rule rather
   than by maximising anything on the evaluation data. Youden-optimal cut-offs are deliberately NOT used:
   picking the threshold that maximises a statistic on the same data you then report it from is optimistic by
   construction, and the size of that optimism is exactly what nobody reports.

3. `net_benefit` — DOES ACTING ON IT BEAT TREATING EVERYONE AND TREATING NO ONE?
   The decision curve (Vickers and Elkin's net benefit): NB(pt) = TPR*prev - FPR*(1-prev)*pt/(1-pt), where
   `pt` is the threshold probability at which a clinician would act, and its odds encode the harm ratio of a
   false positive to a false negative. A measure FAILS this check if there is no threshold probability in the
   declared plausible range where it beats BOTH defaults. That is a real and common failure and no AUC will
   reveal it.

4. `minimum_detectable_change` — CAN YOU TELL THAT ONE PATIENT CHANGED?
   Composed with layer 5: MDC = 1.96 * sqrt(2) * within-state scatter, the smallest difference between two
   readings of the same patient distinguishable from measurement noise. Compared against the between-state
   difference the measure is supposed to detect. Group discrimination answers "are these two populations
   different"; this answers "did this person move", which is the question a monitor is actually asked.

WHAT THIS LAYER CANNOT DO. It cannot supply the prevalence, the harm ratio, or the target sensitivity — those
are clinical and product facts, not statistical ones, and the caller must declare them. Every check here
returns NOT_RUN rather than guessing when they are absent, and a NOT_RUN is not a pass.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from bsde.verifier.report import Evidence, FAIL, NOT_APPLICABLE, NOT_RUN, PASS

MIN_N_CLINICAL = 20
DEFAULT_THRESHOLD_PROBS = (0.05, 0.10, 0.20, 0.30, 0.50)
"""Threshold probabilities spanned by the decision curve. `pt` is where a clinician would act; pt/(1-pt) is
the harm of a false positive relative to a false negative."""


def ppv_npv(sens: float, spec: float, prevalence: float) -> dict:
    """Bayes, written out rather than inferred from a confusion matrix, because the whole point is that the
    prevalence is NOT the sample's."""
    if not (0.0 < prevalence < 1.0) or not np.isfinite(sens) or not np.isfinite(spec):
        return {"ppv": float("nan"), "npv": float("nan")}
    tp = sens * prevalence
    fp = (1.0 - spec) * (1.0 - prevalence)
    fn = (1.0 - sens) * prevalence
    tn = spec * (1.0 - prevalence)
    return {"ppv": tp / (tp + fp) if (tp + fp) > 0 else float("nan"),
            "npv": tn / (tn + fn) if (tn + fn) > 0 else float("nan")}


def threshold_for_target(y: np.ndarray, score: np.ndarray, target: float, mode: str) -> dict:
    """The threshold achieving at least `target` sensitivity (mode='sens') or specificity (mode='spec').

    Chosen by a declared rule rather than by maximising on the evaluation data. Among thresholds meeting the
    target, the one maximising the other axis is taken, so the rule is fully determined and has no residual
    freedom left to exploit.
    """
    y = np.asarray(y, float)
    score = np.asarray(score, float)
    ok = np.isfinite(y) & np.isfinite(score)
    y, score = y[ok], score[ok]
    if y.size < MIN_N_CLINICAL or len(np.unique(y)) < 2:
        return {"threshold": float("nan"), "sens": float("nan"), "spec": float("nan")}
    best = None
    for t in np.unique(score):
        pred = score >= t
        sens = float(pred[y == 1].mean()) if (y == 1).any() else float("nan")
        spec = float((~pred[y == 0]).mean()) if (y == 0).any() else float("nan")
        if not (np.isfinite(sens) and np.isfinite(spec)):
            continue
        meets = sens >= target if mode == "sens" else spec >= target
        if not meets:
            continue
        other = spec if mode == "sens" else sens
        if best is None or other > best[1]:
            best = (t, other, sens, spec)
    if best is None:
        return {"threshold": float("nan"), "sens": float("nan"), "spec": float("nan"),
                "reason": f"no threshold reaches {target:.0%} {mode}"}
    return {"threshold": float(best[0]), "sens": float(best[2]), "spec": float(best[3])}


def net_benefit(y: np.ndarray, p: np.ndarray, pt: float, prevalence: float | None = None) -> dict:
    """Net benefit at threshold probability `pt`, against treat-all and treat-none.

    `prevalence` overrides the sample's, which is the point of the whole layer. TPR and FPR are estimated
    from the sample (they are properties of the measure, not of the prevalence) and then recombined at the
    declared prevalence.
    """
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    if y.size < MIN_N_CLINICAL or len(np.unique(y)) < 2:
        return {"model": float("nan"), "treat_all": float("nan"), "treat_none": 0.0}
    prev = float(np.mean(y)) if prevalence is None else float(prevalence)
    pred = p >= pt
    tpr = float(pred[y == 1].mean())
    fpr = float(pred[y == 0].mean())
    w = pt / (1.0 - pt)
    return {"model": tpr * prev - fpr * (1.0 - prev) * w,
            "treat_all": prev - (1.0 - prev) * w,
            "treat_none": 0.0, "tpr": tpr, "fpr": fpr, "prevalence_used": prev}


def minimum_detectable_change(within_scatter: float, between_difference: float) -> dict:
    """MDC95 from within-state scatter, and whether the effect the measure must detect exceeds it.

    1.96 * sqrt(2) * sigma: sqrt(2) because a change is the difference of TWO noisy readings, and 1.96 for a
    95 % criterion. If MDC exceeds the between-state difference, a real state change in one patient is
    indistinguishable from measurement noise, whatever the group-level separation.
    """
    if not (np.isfinite(within_scatter) and within_scatter > 0 and np.isfinite(between_difference)):
        return {"mdc95": float("nan"), "ratio": float("nan")}
    mdc = 1.96 * np.sqrt(2.0) * within_scatter
    return {"mdc95": float(mdc), "between": float(abs(between_difference)),
            "ratio": float(abs(between_difference) / mdc)}


def layer_clinical(cand, y: Sequence, p_oof: Sequence, rng, prevalences: Sequence[float] | None = None,
                   threshold_probs: Sequence[float] = DEFAULT_THRESHOLD_PROBS,
                   target_sens: float = 0.90, target_spec: float = 0.90,
                   within_scatter: float | None = None, between_difference: float | None = None,
                   dataset: str = "unnamed") -> list:
    """Run the clinical layer on OUT-OF-FOLD predicted probabilities.

    `p_oof` must be out-of-fold. In-sample probabilities make every number here optimistic, and the layer
    cannot detect that it has been handed them — the caller is responsible, which is why `cv_predict_proba`
    exists in `stats.py`.
    """
    out: list = []
    y = np.asarray(y, float)
    p = np.asarray(p_oof, float)
    ok = np.isfinite(y) & np.isfinite(p)

    if ok.sum() < MIN_N_CLINICAL or len(np.unique(y[ok])) < 2:
        for check in ("prevalence_sensitivity", "operating_point", "net_benefit"):
            out.append(Evidence(check, "clinical", NOT_RUN,
                                f"only {int(ok.sum())} usable rows, or one outcome class absent",
                                values={"n": int(ok.sum()), "dataset": dataset}))
        return out

    # --- 2. operating points, by declared rule --------------------------------------------------------
    hi_sens = threshold_for_target(y[ok], p[ok], target_sens, "sens")
    hi_spec = threshold_for_target(y[ok], p[ok], target_spec, "spec")
    out.append(Evidence(
        "operating_point", "clinical", NOT_APPLICABLE,
        (f"at the threshold reaching {target_sens:.0%} sensitivity: sens {hi_sens['sens']:.3f}, "
         f"spec {hi_sens['spec']:.3f}. At {target_spec:.0%} specificity: sens {hi_spec['sens']:.3f}, "
         f"spec {hi_spec['spec']:.3f}. Thresholds are set by a declared rule, NOT by maximising Youden on "
         "the evaluation data, which would be optimistic by construction."),
        values={"target_sens": hi_sens, "target_spec": hi_spec, "dataset": dataset}))

    # --- 1. PPV across declared prevalences -----------------------------------------------------------
    if not prevalences:
        out.append(Evidence(
            "prevalence_sensitivity", "clinical", NOT_RUN,
            "no prevalence supplied. The sample's own prevalence is a DESIGN CHOICE — every cohort here is "
            "near 50/50 by construction — so PPV computed from it would describe a world in which half of "
            "all patients have the condition. This is a fact the caller must supply, not one the data "
            "contains.",
            values={"sample_prevalence": float(np.mean(y[ok])), "dataset": dataset}))
    else:
        rows = {}
        for prev in prevalences:
            rows[f"{prev:g}"] = {"at_target_sens": ppv_npv(hi_sens["sens"], hi_sens["spec"], prev),
                                 "at_target_spec": ppv_npv(hi_spec["sens"], hi_spec["spec"], prev)}
        ppvs = [v["at_target_sens"]["ppv"] for v in rows.values() if np.isfinite(v["at_target_sens"]["ppv"])]
        out.append(Evidence(
            "prevalence_sensitivity", "clinical", NOT_APPLICABLE,
            ("PPV at the high-sensitivity operating point ranges "
             f"{min(ppvs):.3f}-{max(ppvs):.3f} across supplied prevalences "
             f"{[f'{q:g}' for q in prevalences]}, against a sample prevalence of "
             f"{np.mean(y[ok]):.3f} which is a design choice." if ppvs else "PPV not estimable"),
            values={"by_prevalence": rows, "sample_prevalence": float(np.mean(y[ok])),
                    "dataset": dataset}))

    # --- 3. decision curve ----------------------------------------------------------------------------
    prev_for_nb = prevalences[0] if prevalences else None
    curve, beats = {}, []
    for pt in threshold_probs:
        nb = net_benefit(y[ok], p[ok], pt, prev_for_nb)
        curve[f"{pt:g}"] = nb
        if np.isfinite(nb["model"]) and nb["model"] > max(nb["treat_all"], nb["treat_none"]):
            beats.append(pt)
    any_beat = len(beats) > 0
    out.append(Evidence(
        "net_benefit", "clinical", PASS if any_beat else FAIL,
        (f"beats both treat-all and treat-none at threshold probabilities {beats}"
         if any_beat else
         "there is NO threshold probability in the declared range where acting on this measure beats both "
         "treating everyone and treating no one. Discrimination does not imply usefulness, and no AUC "
         "would have shown this."),
        values={"curve": curve, "prevalence_used": prev_for_nb, "dataset": dataset},
        fatal=not any_beat))

    # --- 4. minimum detectable change, composed with layer 5 ------------------------------------------
    if within_scatter is None or between_difference is None:
        out.append(Evidence(
            "minimum_detectable_change", "clinical", NOT_RUN,
            "needs the within-state scatter and between-state difference from layer 5 (temporal), which "
            "requires repeated windows per subject. Group discrimination cannot substitute: it answers "
            "whether two populations differ, not whether one patient moved.",
            values={"dataset": dataset}))
    else:
        m = minimum_detectable_change(within_scatter, between_difference)
        usable = np.isfinite(m["ratio"]) and m["ratio"] > 1.0
        out.append(Evidence(
            "minimum_detectable_change", "clinical", PASS if usable else FAIL,
            (f"MDC95 is {m['mdc95']:.4g} and the between-state difference is {m['between']:.4g}, a ratio of "
             f"{m['ratio']:.2f}" +
             ("" if usable else
              " — a real state change in ONE patient is indistinguishable from measurement noise, whatever "
              "the group-level separation")),
            values=m | {"dataset": dataset}, fatal=not usable))
    return out
