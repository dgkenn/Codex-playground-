"""Verifier layer 5 — temporal. Does the measure hold still long enough to be used on one window?

WHY THIS LAYER EXISTS AND WHAT IT IS FOR. Layers 2-4 all ask a question about GROUP SEPARATION: given many
subjects, does the measure's distribution differ between states? A clinician does not have many subjects.
They have one patient and one window of EEG, and they need to know what state that window is in. A measure
can separate two groups beautifully and still be unusable that way, if its window-to-window scatter WITHIN a
state is as large as the gap BETWEEN states. Nothing in layers 2-4 can see that, because every one of them
collapses a recording to a single number before it starts.

That is the same gap error-catalogue rule 15 records for calibration ("discrimination without calibration is
half a result, and the missing half is the half clinicians use"). This is its temporal sibling.

THREE CHECKS, AND THE FIRST IS THE POINT.

1. `temporal_snr` — WITHIN-STATE STABILITY AGAINST BETWEEN-STATE SEPARATION.
   Requires repeated windows from the same subject in the same state. For each (subject, state) with at least
   `MIN_WINDOWS_PER_STATE` windows, the within-state spread is summarised robustly; the between-state
   separation is the median absolute difference between state medians within a subject. The ratio is a
   signal-to-noise in the units the clinician faces. A measure whose SNR is below 1 cannot classify a single
   window even when its group AUC is 0.9.

2. `single_window_auc_penalty` — HOW MUCH DISCRIMINATION IS LOST BY USING ONE WINDOW INSTEAD OF AVERAGING.
   The same subjects, scored once from the mean of all their windows and once from a single randomly chosen
   window. The drop is the price of the clinical setting. Reported rather than thresholded, because what
   counts as an acceptable drop is a product decision and not a statistical one.

3. `effective_sample_size` — REPEATED WINDOWS FROM ONE RECORDING ARE NOT INDEPENDENT.
   If a candidate's association was computed over rows rather than subjects, its confidence interval is too
   narrow by roughly the square root of the within-subject correlation inflation. This check measures the
   intraclass correlation and reports the effective n, so that an interval computed the wrong way is visibly
   wrong rather than invisibly optimistic.

WHAT THIS LAYER DOES *NOT* DO, STATED SO IT IS NOT MISTAKEN FOR DONE. It does not test whether the measure
CHANGES BEFORE the state does — temporal precedence, the thing that would make a marker predictive rather
than descriptive. That needs densely-sampled transitions with a trustworthy time axis, and error-catalogue
rule 27 records what happens when the time axis is not checked first (a mask that compresses out bad samples
glued a 1,817 s hole shut, invisibly, in a recording used for exactly that kind of question). E04 approached
this on I-CARE and it remains the harder half of the layer.

**A NOT_RUN FROM THIS LAYER IS NOT A PASS.** Every check here refuses to report when its precondition is
absent, which for `temporal_snr` means a table with one window per state — the shape of every feature table
this project currently has. `verify()` already treats a required-but-missing layer as blocking, and that
behaviour is what this module must preserve rather than quietly satisfy.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

import numpy as np

from bsde.verifier.report import Evidence, FAIL, NOT_APPLICABLE, NOT_RUN, PASS

MIN_WINDOWS_PER_STATE = 3
"""Below three windows a within-state spread is a single difference, not a spread."""

MIN_SUBJECTS_TEMPORAL = 10
SNR_FAIL_BELOW = 1.0
"""Within-state scatter equal to between-state separation. At or below this a single window cannot be
classified, whatever the group-level AUC says."""


def _mad(x: np.ndarray) -> float:
    """Median absolute deviation, scaled to be comparable to a standard deviation for normal data.

    Robust rather than the standard deviation because one artefactual window inside a state would otherwise
    dominate the within-state term and make every measure look unstable.
    """
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return float("nan")
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def temporal_snr(values: np.ndarray, subject: np.ndarray, state: np.ndarray) -> dict:
    """Within-state scatter against between-state separation, computed per subject and pooled.

    Returns the pooled ratio plus the two terms, so a bad ratio can be attributed to the numerator or the
    denominator rather than being an opaque number.
    """
    values = np.asarray(values, float)
    subject = np.asarray(subject)
    state = np.asarray(state)
    by = defaultdict(lambda: defaultdict(list))
    for v, s, st in zip(values, subject, state):
        if np.isfinite(v):
            by[s][st].append(v)

    within, between, n_subj = [], [], 0
    for s, states in by.items():
        usable = {st: np.array(vs) for st, vs in states.items() if len(vs) >= MIN_WINDOWS_PER_STATE}
        if len(usable) < 2:
            continue
        w = [_mad(v) for v in usable.values()]
        w = [x for x in w if np.isfinite(x)]
        meds = [float(np.median(v)) for v in usable.values()]
        if not w or len(meds) < 2:
            continue
        # Between-state separation is the median pairwise gap, not the range: the range is the maximum of
        # several differences and grows with the number of states, which would reward measures merely for
        # being evaluated on more states.
        gaps = [abs(a - b) for i, a in enumerate(meds) for b in meds[i + 1:]]
        within.append(float(np.median(w)))
        between.append(float(np.median(gaps)))
        n_subj += 1

    if n_subj < MIN_SUBJECTS_TEMPORAL:
        return {"snr": float("nan"), "n_subjects": n_subj, "within": float("nan"),
                "between": float("nan"), "reason": "too few subjects with repeated windows"}
    w_pooled, b_pooled = float(np.median(within)), float(np.median(between))
    snr = b_pooled / w_pooled if w_pooled > 0 else float("nan")
    return {"snr": float(snr), "n_subjects": n_subj, "within": w_pooled, "between": b_pooled}


def single_window_penalty(values: np.ndarray, subject: np.ndarray, y: np.ndarray, rng,
                          state: np.ndarray | None = None, reps: int = 200) -> dict:
    """AUC from a cell's MEAN across windows, against AUC from ONE randomly chosen window of that cell.

    THE UNIT IS A (SUBJECT, STATE) CELL, NOT A SUBJECT, and the first version of this function got that
    wrong. It grouped rows by subject and took each subject's first row's outcome as "the subject's outcome",
    which is only meaningful in a BETWEEN-subject design. Every within-subject design this project actually
    uses — Chennu's four sedation levels, Sleep-EDF's five stages — gives each subject BOTH outcome classes,
    so the subject-level outcome was constant by construction and the function returned NaN for a table it
    should have handled. The same mistake, in the same shape, as the degenerate permutation null found
    earlier: a between-subject assumption applied to within-subject data.

    Grouping by cell is correct for both designs: in a between-subject table each subject contributes one
    cell, and the behaviour is what the first version intended.

    The single-window figure is averaged over `reps` random draws so it is not a statement about which window
    happened to be picked.

    NOTE ON THE INTERVAL THAT IS NOT COMPUTED HERE. Cells from one subject are not independent, so an AUC
    across cells has an optimistic nominal precision. This function reports point estimates only and is
    labelled NOT_APPLICABLE rather than PASS/FAIL by `layer_temporal` for exactly that reason — the number is
    a magnitude to look at, not a test. `effective_sample_size` in this module quantifies the dependence.
    """
    from bsde.verifier.stats import auc
    values = np.asarray(values, float)
    subject = np.asarray(subject)
    y = np.asarray(y, float)
    state = np.asarray(state) if state is not None else np.asarray(y, dtype=object)
    idx_by = defaultdict(list)
    for i in range(values.size):
        if np.isfinite(values[i]) and np.isfinite(y[i]):
            idx_by[(subject[i], state[i])].append(i)
    subs = [c for c, ii in idx_by.items() if len(ii) >= 2]
    if len(subs) < MIN_SUBJECTS_TEMPORAL:
        return {"mean_auc": float("nan"), "single_auc": float("nan"), "penalty": float("nan"),
                "n_cells": len(subs), "reason": "too few (subject, state) cells with repeated windows"}
    ys = np.array([y[idx_by[c][0]] for c in subs], float)
    if len(np.unique(ys)) < 2:
        return {"mean_auc": float("nan"), "single_auc": float("nan"), "penalty": float("nan"),
                "n_cells": len(subs), "reason": "outcome constant across cells"}
    mean_vals = np.array([np.mean(values[idx_by[c]]) for c in subs], float)
    a_mean = auc(ys, mean_vals)
    singles = []
    for _ in range(reps):
        pick = np.array([values[rng.choice(idx_by[c])] for c in subs], float)
        a = auc(ys, pick)
        if np.isfinite(a):
            singles.append(a)
    a_single = float(np.mean(singles)) if singles else float("nan")
    # Both are folded to the same side of 0.5 before differencing, so a candidate whose association runs
    # below 0.5 is not scored as having a huge "penalty" purely because of its direction.
    m, s_ = abs(a_mean - 0.5), abs(a_single - 0.5)
    return {"mean_auc": float(a_mean), "single_auc": a_single, "penalty": float(m - s_),
            "n_cells": len(subs)}


def intraclass_correlation(values: np.ndarray, subject: np.ndarray) -> dict:
    """One-way ICC and the effective sample size it implies for row-level (rather than subject-level) tests.

    n_eff = n_rows / (1 + (m - 1) * ICC), with m the mean windows per subject — the standard design-effect
    correction. Reported so that an interval computed over rows is visibly, quantitatively wrong.
    """
    values = np.asarray(values, float)
    subject = np.asarray(subject)
    ok = np.isfinite(values)
    values, subject = values[ok], subject[ok]
    groups = [values[subject == s] for s in np.unique(subject)]
    groups = [g for g in groups if g.size >= 2]
    if len(groups) < MIN_SUBJECTS_TEMPORAL:
        return {"icc": float("nan"), "n_rows": int(values.size), "n_eff": float("nan"),
                "reason": "too few subjects with repeated windows"}
    k = len(groups)
    n_rows = sum(g.size for g in groups)
    m = n_rows / k
    grand = float(np.mean(np.concatenate(groups)))
    msb = sum(g.size * (g.mean() - grand) ** 2 for g in groups) / (k - 1)
    msw_den = n_rows - k
    msw = (sum(((g - g.mean()) ** 2).sum() for g in groups) / msw_den) if msw_den > 0 else float("nan")
    if not np.isfinite(msw) or (msb + (m - 1) * msw) == 0:
        return {"icc": float("nan"), "n_rows": n_rows, "n_eff": float("nan"),
                "reason": "degenerate variance decomposition"}
    icc = (msb - msw) / (msb + (m - 1) * msw)
    icc = float(min(max(icc, 0.0), 1.0))
    n_eff = n_rows / (1.0 + (m - 1) * icc)
    return {"icc": icc, "n_rows": int(n_rows), "n_eff": float(n_eff), "mean_windows_per_subject": float(m)}


def layer_temporal(cand, values: np.ndarray, subject: np.ndarray, state: np.ndarray,
                   y: np.ndarray | None, rng, dataset: str = "unnamed") -> list:
    """Run the temporal layer. Every check reports NOT_RUN when its precondition is absent.

    `values`, `subject`, `state` are ROW-level: one row per (subject, state, window). A table with one window
    per state — every feature table this project currently has — makes `temporal_snr` NOT_RUN by design, and
    that must continue to block any candidate whose declaration requires this layer.
    """
    out: list = []
    counts = defaultdict(int)
    for s, st in zip(np.asarray(subject), np.asarray(state)):
        counts[(s, st)] += 1
    max_windows = max(counts.values()) if counts else 0

    if max_windows < MIN_WINDOWS_PER_STATE:
        out.append(Evidence(
            "temporal_snr", "temporal", NOT_RUN,
            f"the table has at most {max_windows} window(s) per (subject, state); this check needs "
            f"{MIN_WINDOWS_PER_STATE}. Within-state stability is UNMEASURED, which is not the same as "
            "adequate — a candidate requiring the temporal layer still cannot be reported as surviving.",
            values={"max_windows_per_subject_state": int(max_windows), "dataset": dataset},
            item="temporal_transition"))
        out.append(Evidence("single_window_auc_penalty", "temporal", NOT_RUN,
                            "needs repeated windows per subject", values={"dataset": dataset}))
        out.append(Evidence("effective_sample_size", "temporal", NOT_RUN,
                            "needs repeated windows per subject", values={"dataset": dataset}))
        return out

    snr = temporal_snr(values, subject, state)
    if not np.isfinite(snr["snr"]):
        out.append(Evidence("temporal_snr", "temporal", NOT_RUN,
                            snr.get("reason", "not estimable"), values={**snr, "dataset": dataset},
                            item="temporal_transition"))
    else:
        ok = snr["snr"] > SNR_FAIL_BELOW
        out.append(Evidence(
            "temporal_snr", "temporal", PASS if ok else FAIL,
            (f"between-state separation is {snr['snr']:.2f}x the within-state scatter"
             if ok else
             f"within-state scatter ({snr['within']:.4g}) is at least as large as the between-state "
             f"separation ({snr['between']:.4g}), SNR {snr['snr']:.2f}. Group-level discrimination does not "
             "transfer to a single window, which is the setting the measure would be used in."),
            values={**snr, "dataset": dataset}, item="temporal_transition", fatal=not ok))

    if y is not None:
        pen = single_window_penalty(values, subject, y, rng, state=state)
        out.append(Evidence(
            "single_window_auc_penalty", "temporal",
            NOT_RUN if not np.isfinite(pen["penalty"]) else NOT_APPLICABLE,
            (pen.get("reason", "not estimable") if not np.isfinite(pen["penalty"]) else
             f"|AUC-0.5| falls from {abs(pen['mean_auc'] - 0.5):.3f} (mean of all windows) to "
             f"{abs(pen['single_auc'] - 0.5):.3f} (one random window), a loss of {pen['penalty']:.3f}. "
             "Reported, not thresholded: what loss is acceptable is a product decision."),
            values={**pen, "dataset": dataset}))
    else:
        out.append(Evidence("single_window_auc_penalty", "temporal", NOT_RUN,
                            "no outcome supplied for this table", values={"dataset": dataset}))

    icc = intraclass_correlation(values, subject)
    out.append(Evidence(
        "effective_sample_size", "temporal",
        NOT_RUN if not np.isfinite(icc.get("icc", float("nan"))) else NOT_APPLICABLE,
        (icc.get("reason", "not estimable") if not np.isfinite(icc.get("icc", float("nan"))) else
         f"ICC {icc['icc']:.3f} over {icc['n_rows']} rows: an interval computed over ROWS behaves like "
         f"n={icc['n_eff']:.0f}, not n={icc['n_rows']}. Subject-level resampling is required and this "
         "number says how badly row-level resampling would mislead."),
        values={**icc, "dataset": dataset}))
    return out
