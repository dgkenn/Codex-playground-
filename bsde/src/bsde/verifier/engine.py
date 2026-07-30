"""The verifier engine: run a registered candidate's values through the layers and try to kill it.

The engine works on a `Cohort` — one row per subject-recording, the candidate already evaluated. Feature
computation lives upstream (ingestion + candidates); this module is only about whether the resulting numbers
mean what the candidate declared they mean.

THE DECISION RULE FOR CONFOUNDS IS PRE-SPECIFIED, in `docs/ANALYSIS_PLAN.md` §6, written before any of this
code existed:

    "if a probe predicts a nuisance variable BETTER than the model predicts the outcome, AND performance
     drops when that nuisance is held out, the result is reported as a failure or partial failure — not
     reframed."

Both clauses are required. Either alone is a bad rule:

  * Clause 1 alone would reject the aperiodic exponent for correlating with age, which it does and should —
    a real physiological marker is allowed to correlate with nuisances. What is not allowed is for the
    nuisance to be doing the work.
  * Clause 2 alone would reject any marker whose signal is partly shared with a covariate, which is almost
    all of them, and stratification always costs power.

Clause 2 is implemented as a STRATIFIED Mann-Whitney: concordant pairs summed across strata of the nuisance,
divided by comparable pairs summed across strata. Pairs spanning two strata are never counted, which is the
whole point — it asks whether the candidate separates outcomes among subjects who share the nuisance value.
Pooling stratum-wise AUCs with arbitrary weights was considered and rejected; the pair-counting version has
no weighting choice to get wrong.

WHAT THIS ENGINE DOES NOT DO. It does not compute features, read EEG, or choose datasets. It does not decide
that a surviving candidate is true — surviving means "this run failed to kill it", and the layers a candidate
was never required to face are printed alongside the verdict for exactly that reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Sequence

import numpy as np

from bsde.candidates.registry import Candidate
from bsde.verifier.report import (Evidence, VerifierReport, decide,
                                  PASS, FAIL, NOT_RUN, NOT_APPLICABLE)
from bsde.verifier.stats import (auc, auc_abs, directional_auc, cluster_bootstrap_ci,
                                 permutation_null, spearman, brier, calibration, cv_predict_proba)

# --- thresholds, all pre-specified here rather than chosen per-candidate -----------------------------
LEAKAGE_AUC = 0.98        # discrimination above this from a resting EEG scalar is implausible
MIN_SUBJECTS = 20         # below this, discrimination checks are NOT_RUN rather than reported noisily
MIN_PER_CLASS = 5
BOOT_REPS = 1000
PERM_REPS = 1000


@dataclass
class Cohort:
    """One row per subject-recording. `values` is the candidate already evaluated on that recording."""

    values: np.ndarray
    y: np.ndarray                                   # binary outcome for the declared contrast
    subject: np.ndarray
    contrast: str                                   # which declared prediction this cohort tests
    nuisance: Mapping[str, np.ndarray] = field(default_factory=dict)
    baseline: np.ndarray | None = None              # the trivial baseline the candidate must beat
    baseline_name: str = "trivial baseline"
    dataset: str = "unnamed"
    state: np.ndarray | None = None
    """Row-level state label, for tables with REPEATED WINDOWS per (subject, state). Optional because every
    table this project built before E14 has exactly one window per state, in which case layer 5's
    within-state checks correctly report NOT_RUN. Supplying it is what lets the temporal layer run at all."""
    prevalences: tuple = ()
    """Declared prevalences for layer 7. Empty means the clinical layer refuses to compute a PPV rather than
    silently using the sample's, which in every cohort here is ~0.5 BY DESIGN and describes no real
    population."""

    def __post_init__(self) -> None:
        self.values = np.asarray(self.values, float)
        self.y = np.asarray(self.y, float)
        self.subject = np.asarray(self.subject)
        n = len(self.values)
        if not (len(self.y) == len(self.subject) == n):
            raise ValueError("values, y and subject must be the same length")
        for k, v in self.nuisance.items():
            if len(v) != n:
                raise ValueError(f"nuisance {k!r} has length {len(v)}, expected {n}")
        if self.state is not None:
            self.state = np.asarray(self.state)
            if len(self.state) != n:
                raise ValueError("state must be the same length as values")
        if self.baseline is not None:
            self.baseline = np.asarray(self.baseline, float)
            if len(self.baseline) != n:
                raise ValueError("baseline must be the same length as values")

    @property
    def n(self) -> int:
        return len(self.values)

    def evaluable(self) -> bool:
        ok = np.isfinite(self.values) & np.isfinite(self.y)
        return (ok.sum() >= MIN_SUBJECTS
                and (self.y[ok] == 1).sum() >= MIN_PER_CLASS
                and (self.y[ok] == 0).sum() >= MIN_PER_CLASS)


# ---------------------------------------------------------------------------------------------------
# statistics used only here
# ---------------------------------------------------------------------------------------------------

def stratified_auc(y: np.ndarray, score: np.ndarray, strata: np.ndarray) -> float:
    """Mann-Whitney concordance computed WITHIN strata and pooled over pairs, not over stratum AUCs.

    Pairs that span two strata are excluded, so this answers: among subjects sharing the nuisance value,
    does the candidate still separate the outcome? Ties count half, consistent with `auc`.
    """
    y = np.asarray(y, float)
    score = np.asarray(score, float)
    strata = np.asarray(strata)
    conc = 0.0
    pairs = 0.0
    for s in np.unique(strata):
        m = (strata == s) & np.isfinite(score) & np.isfinite(y)
        a = score[m & (y == 1)]
        b = score[m & (y == 0)]
        if a.size == 0 or b.size == 0:
            continue
        d = a[:, None] - b[None, :]
        conc += float((d > 0).sum()) + 0.5 * float((d == 0).sum())
        pairs += float(a.size * b.size)
    return conc / pairs if pairs > 0 else float("nan")


def residual_auc(y: np.ndarray, x: np.ndarray, v: np.ndarray) -> float:
    """Discrimination that remains after removing everything a CONTINUOUS nuisance can explain.

    Why this exists rather than reusing `stratified_auc`. Tertile strata are too coarse to remove a strong
    continuous confound: within a tertile of EMG there is still ample EMG variation, so a candidate that IS
    the EMG index retains a healthy within-stratum association and passes. That was not a hypothetical — the
    planted pure-muscle candidate SURVIVED the first version of this engine, and this function is the fix.
    Finer strata were considered and rejected: they trade the bias for variance and the choice of bin count
    becomes a researcher degree of freedom.

    Everything is done on MIDRANKS, with a quadratic term, so any monotone nuisance-candidate relationship is
    removed regardless of its functional form — which matters because "linear in the raw units" is an
    assumption the engine has no way to check.

    LIMITATION, stated because it can invert the conclusion. If the nuisance is itself part of the state
    being measured — muscle tone genuinely falls with anaesthetic depth, so EMG is not purely an artefact —
    then residualising removes real signal and this check will fire on a valid marker. The engine cannot
    settle that; it reports which nuisance fired and the candidate's declaration says whether its author
    accepts that as a refutation.
    """
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    v = np.asarray(v, float)
    ok = np.isfinite(x) & np.isfinite(v) & np.isfinite(y)
    if ok.sum() < MIN_SUBJECTS:
        return float("nan")
    from bsde.verifier.stats import _midranks
    rx = _midranks(x[ok])
    rv = _midranks(v[ok])
    rv = (rv - rv.mean()) / (rv.std() if rv.std() > 1e-12 else 1.0)
    A = np.column_stack([np.ones(ok.sum()), rv, rv ** 2])
    try:
        beta, *_ = np.linalg.lstsq(A, rx, rcond=None)
    except np.linalg.LinAlgError:
        return float("nan")
    return auc(y[ok], rx - A @ beta)


def _is_categorical(v: np.ndarray, max_levels: int = 8) -> bool:
    """A nuisance is categorical if it is non-numeric or takes few enough distinct values to stratify on.

    The threshold decides which conditional statistic a probe uses, so it is fixed here once rather than
    per-probe. Anything with more than `max_levels` distinct numeric values is residualised, not stratified.
    """
    v = np.asarray(v)
    return bool(v.dtype.kind in "USOb" or len(np.unique(v)) <= max_levels)


def _strata_of(v: np.ndarray, max_levels: int = 8) -> np.ndarray:
    """Categorical nuisances stratify by level; continuous ones by tertile.

    Tertiles are retained only as a reported secondary description of a continuous nuisance; the clause-2
    decision for continuous variables is made by `residual_auc`, because tertiles are far too coarse to hold
    a strong continuous confound constant.
    """
    v = np.asarray(v)
    if _is_categorical(v, max_levels):
        return v.astype(str)
    f = v.astype(float)
    ok = np.isfinite(f)
    q = np.quantile(f[ok], [1 / 3, 2 / 3]) if ok.sum() > 3 else np.array([np.inf, np.inf])
    out = np.full(len(f), "nan", dtype=object)
    out[ok & (f <= q[0])] = "t1"
    out[ok & (f > q[0]) & (f <= q[1])] = "t2"
    out[ok & (f > q[1])] = "t3"
    return np.asarray(out, dtype=str)


def _probe_strength(x: np.ndarray, v: np.ndarray) -> tuple:
    """How much does the candidate know about this nuisance? Reported on the AUC scale, [0.5, 1].

    Continuous nuisances are dichotomised at the median so the number is directly comparable with the
    candidate's outcome AUC; multi-level categoricals take the strongest one-vs-rest. Dichotomising discards
    information and therefore UNDERSTATES the probe — the bias is toward keeping candidates, which is the
    direction an honest verifier should not err in, so the raw rank correlation is reported alongside it.
    """
    x = np.asarray(x, float)
    v = np.asarray(v)
    finite = v[~_isnan_like(v)]
    if finite.size and len(np.unique(finite)) == 1:
        # A nuisance that never varies cannot explain anything that does. Reporting this as "could not
        # evaluate (strongest level '')" was true but unreadable; within a single dataset sfreq and
        # n_channels are routinely constant, so this is the common case, not an edge case.
        return float("nan"), f"constant within this dataset (every row = {finite[0]!r})", float("nan")
    if v.dtype.kind in "USOb" or len(np.unique(v[~_isnan_like(v)])) <= 8:
        levels = [lv for lv in np.unique(v.astype(str)) if lv not in ("nan", "None", "")]
        best, which = float("nan"), ""
        for lv in levels:
            a = auc_abs((v.astype(str) == lv).astype(float), x)
            if np.isfinite(a) and (not np.isfinite(best) or a > best):
                best, which = a, lv
        return best, f"one-vs-rest, strongest level '{str(which)}'", float("nan")
    f = v.astype(float)
    ok = np.isfinite(f) & np.isfinite(x)
    if ok.sum() < MIN_SUBJECTS:
        return float("nan"), "too few finite values", float("nan")
    hi = (f > np.median(f[ok])).astype(float)
    return auc_abs(hi[ok], x[ok]), "dichotomised at the median", abs(spearman(x[ok], f[ok]))


def _isnan_like(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v)
    if v.dtype.kind in "USO":
        return np.isin(v.astype(str), ["nan", "None", ""])
    return ~np.isfinite(v.astype(float))


# ---------------------------------------------------------------------------------------------------
# the layers
# ---------------------------------------------------------------------------------------------------

def layer_statistical(cand: Candidate, coh: Cohort, rng) -> list:
    """Layer 2. Directional discrimination against a subject-level permutation null.

    The null is BOTH a check and a gate: the observed statistic is compared against it (a check), and the
    null's own centring is verified (a machinery gate — an off-centre null means the harness is broken and
    no comparison against it is interpretable, rule 31).
    """
    ev = []
    predicted = cand.predicted(coh.contrast)
    if predicted is None:
        return [Evidence("directional_discrimination", "statistical", NOT_APPLICABLE,
                         f"the candidate declared no prediction for contrast {coh.contrast!r}; an "
                         "undeclared contrast earns no credit and costs none",
                         item="cross_dataset_performance")]
    if predicted == "unchanged":
        a = auc_abs(coh.y, coh.values)
        ok = np.isfinite(a) and a < 0.60
        return [Evidence("invariance", "statistical", PASS if ok else FAIL,
                         f"declared UNCHANGED across {coh.contrast}; direction-free AUC {a:.3f} "
                         f"({'consistent with invariance' if ok else 'the candidate does move'})",
                         {"auc_abs": a}, item="cross_dataset_performance")]
    if not coh.evaluable():
        return [Evidence("directional_discrimination", "statistical", NOT_RUN,
                         f"cohort too small or too imbalanced (n={coh.n}, "
                         f"pos={int((coh.y == 1).sum())}, neg={int((coh.y == 0).sum())}); "
                         f"minimum is {MIN_SUBJECTS} with {MIN_PER_CLASS} per class",
                         {"n": coh.n}, item="cross_dataset_performance")]

    a = directional_auc(coh.y, coh.values, predicted)
    lo, hi, _ = cluster_bootstrap_ci(
        lambda idx: directional_auc(coh.y[idx], coh.values[idx], predicted),
        coh.subject, rng, reps=BOOT_REPS)

    # --- within-subject state response -----------------------------------------------------------
    # A mandatory report row (Brief 03) that NOTHING populated until now, caught by the standing guard in
    # tests/test_sweep_evidence.py rather than by inspection.
    #
    # This is NOT the AUC in another form. AUC pools comparisons ACROSS subjects, so a measure can separate
    # two populations while moving the wrong way inside most individuals -- between-subject variation does
    # the work and nobody sees it. The question a monitor is asked is whether the measure moves in THIS
    # person when THIS person's state changes, which is a paired quantity and needs subjects contributing
    # both classes.
    paired, subs_p = [], []
    for u in np.unique(coh.subject):
        m = (coh.subject == u) & np.isfinite(coh.values) & np.isfinite(coh.y)
        # v1/v0 rather than a/b: `a` is the AUC in this function's enclosing scope, and the first version of
        # this block shadowed it, leaking an empty array into `a > null["q975"]` sixty lines later. Sixteen
        # tests caught it, which is the system working -- but a one-letter loop variable inside a long
        # function is how it happened.
        v1, v0 = coh.values[m & (coh.y == 1)], coh.values[m & (coh.y == 0)]
        if v1.size and v0.size:
            d = float(v1.mean() - v0.mean())
            paired.append(d if predicted == "higher" else -d)
            subs_p.append(u)
    if not paired:
        # NOT_APPLICABLE, NOT NOT_RUN, and the difference decides whether the candidate can ever survive.
        # NO subject contributes both classes, so this is a BETWEEN-subject design and a within-subject
        # response is not a missing measurement -- it does not exist to be measured. Calling it NOT_RUN
        # would make a property of the study design into a permanent INCOMPLETE for every between-subject
        # cohort, which is not what an unpopulated report row means.
        ev.append(Evidence(
            "within_subject_state_response", "statistical", NOT_APPLICABLE,
            "no subject contributes both outcome classes: this is a BETWEEN-subject design and the paired "
            "quantity does not exist. That is a limitation of the design and it is worth stating plainly -- "
            "a between-subject AUC pools across people, so it can be driven entirely by between-person "
            "variation, and nothing here shows the measure moves when one person's state changes.",
            values={"n_paired": 0}, item="within_subject_state_response"))
    elif len(paired) < 10:
        # Some subjects ARE paired, so the quantity exists and there are simply too few to estimate it.
        # That is a genuine NOT_RUN and it should block.
        ev.append(Evidence(
            "within_subject_state_response", "statistical", NOT_RUN,
            f"only {len(paired)} subjects contribute both classes -- the paired quantity exists here but "
            "cannot be estimated from that many. This blocks, unlike the between-subject case, because the "
            "data could supply it and does not.",
            values={"n_paired": len(paired)}, item="within_subject_state_response"))
    else:
        arr, sarr = np.asarray(paired, float), np.asarray(subs_p)
        frac = float(np.mean(arr > 0))
        f_lo, f_hi = cluster_bootstrap_ci(lambda i: float(np.mean(arr[i] > 0)), sarr, rng,
                                          reps=BOOT_REPS)[:2]
        moves_right = f_lo > 0.5
        moves_wrong = f_hi < 0.5
        ev.append(Evidence(
            "within_subject_state_response", "statistical",
            PASS if moves_right else (FAIL if moves_wrong else NOT_APPLICABLE),
            f"{frac:.1%} [{f_lo:.1%}, {f_hi:.1%}] of {len(paired)} subjects move in the DECLARED direction "
            f"({predicted}) when their own state changes. "
            + ("Consistent within individuals, not only across the group."
               if moves_right else
               ("The majority move OPPOSITE to the declaration inside their own recordings, so any "
                "group-level separation is driven by between-subject variation."
                if moves_wrong else
                "The interval spans 50 %, so the within-subject direction is undetermined -- which a "
                "group-level AUC would have hidden entirely.")),
            values={"fraction_declared_direction": frac, "ci": [f_lo, f_hi], "n_paired": len(paired),
                    "median_signed_change": float(np.median(arr))},
            item="within_subject_state_response", fatal=moves_wrong))

    null = permutation_null(lambda yp: directional_auc(yp, coh.values, predicted),
                            coh.y, coh.subject, rng, reps=PERM_REPS)
    ev.append(Evidence(
        "permutation_null_is_centred", "statistical",
        PASS if null["null_centered"] else FAIL,
        f"label-permuted null mean {null['mean']:.4f} over {null['n']} usable permutations, scheme="
        f"{null.get('scheme')} (must sit at chance, 0.5 +/- 0.05). "
        + ("" if null["n"] else "ZERO usable permutations -- every relabelling produced a single-class "
                                "outcome, so no null exists and nothing downstream is interpretable."),
        {"null_mean": null["mean"], "null_q975": null["q975"], "n_perm": null["n"],
         "scheme": null.get("scheme")},
        machinery_gate=True, item="confound_probes"))

    # A directional claim is NOT satisfied by an interval spanning the null (rule 37).
    beats_null = np.isfinite(a) and a > null["q975"]
    excludes_half = np.isfinite(lo) and lo > 0.5
    passed = bool(beats_null and excludes_half)
    ev.append(Evidence(
        "directional_discrimination", "statistical", PASS if passed else FAIL,
        f"AUC {a:.3f} [{lo:.3f}, {hi:.3f}] in the declared direction ({predicted}); "
        f"permutation 97.5th centile {null['q975']:.3f}. "
        + ("exceeds the null and the interval excludes 0.5" if passed else
           ("interval spans 0.5" if not excludes_half else "does not exceed the permutation null")),
        {"auc": a, "ci_lo": lo, "ci_hi": hi, "null_q975": null["q975"], "n": coh.n},
        item="cross_dataset_performance"))

    # --- calibration -------------------------------------------------------------------------------
    # Discrimination without calibration is half a result, and the missing half is the half clinicians use.
    p_oof = cv_predict_proba(coh.values, coh.y, coh.subject, rng, folds=5)
    ok_p = np.isfinite(p_oof) & np.isfinite(coh.y)
    if ok_p.sum() < MIN_SUBJECTS:
        ev.append(Evidence("calibration", "statistical", NOT_RUN,
                           f"only {int(ok_p.sum())} rows received an out-of-fold probability; "
                           f"minimum is {MIN_SUBJECTS}",
                           item="cross_dataset_performance"))
    else:
        cal = calibration(coh.y[ok_p], p_oof[ok_p])
        bs = brier(coh.y[ok_p], p_oof[ok_p])
        prev = float(coh.y[ok_p].mean())
        bs_ref = brier(coh.y[ok_p], np.full(int(ok_p.sum()), prev))   # prevalence-only baseline
        skill = 1.0 - bs / bs_ref if bs_ref > 0 else float("nan")
        slope_ok = np.isfinite(cal["slope"]) and 0.5 <= cal["slope"] <= 2.0
        beats_prev = np.isfinite(skill) and skill > 0.0
        ev.append(Evidence(
            "calibration", "statistical", PASS if (slope_ok and beats_prev) else FAIL,
            f"out-of-fold Brier {bs:.4f} vs prevalence-only {bs_ref:.4f} (skill {skill:+.3f}); "
            f"calibration intercept {cal['intercept']:+.3f}, slope {cal['slope']:.3f} "
            f"(perfect is 0 and 1; slope < 1 means over-confident). "
            + ("calibrated and better than predicting the prevalence" if (slope_ok and beats_prev) else
               ("does not beat a prevalence-only prediction" if not beats_prev else
                "slope is outside [0.5, 2.0], so the probabilities are materially miscalibrated")),
            {"brier": bs, "brier_prevalence": bs_ref, "brier_skill": skill,
             "cal_intercept": cal["intercept"], "cal_slope": cal["slope"], "n": int(ok_p.sum())},
            item="cross_dataset_performance"))

    ev.append(Evidence(
        "label_leakage", "statistical", FAIL if (np.isfinite(a) and a >= LEAKAGE_AUC) else PASS,
        (f"AUC {a:.3f} >= {LEAKAGE_AUC}. A single resting-EEG scalar separating this outcome essentially "
         "perfectly is not a plausible physiological result. THREE DISTINGUISHABLE CAUSES, identical in "
         "consequence: (1) data leakage -- the outcome influenced how the feature was computed; "
         "(2) DEFINITIONAL CIRCULARITY -- the label is itself scored FROM the signal, so predicting it is "
         "close to tautological. This is the real cause on sleep data: N3 is defined by the proportion of "
         "slow-wave activity in the epoch, so a steep spectral exponent predicting N3 restates the scoring "
         "rule (MASTER_PLAN §9.6). Such a result shows CRITERION RECOVERY, never detection; "
         "(3) a genuinely near-perfect biomarker, which for EEG is the least likely of the three and is "
         "the reason this check errs toward firing. Determining WHICH cause applies is not something the "
         "engine can do -- it requires knowing how the label was produced.") if (np.isfinite(a) and a >= LEAKAGE_AUC) else
        f"AUC {a:.3f} is below the implausibility threshold {LEAKAGE_AUC}",
        {"auc": a, "threshold": LEAKAGE_AUC}, fatal=True, item="confound_probes"))
    return ev


def layer_adversarial(cand: Candidate, coh: Cohort, rng) -> list:
    """Layer 3. Confound probes and the trivial baseline, both applying pre-specified rules."""
    ev = []
    predicted = cand.predicted(coh.contrast)
    signed = predicted in ("higher", "lower")

    if not coh.nuisance:
        ev.append(Evidence("confound_probes", "adversarial", NOT_RUN,
                           "no nuisance variables were supplied with this cohort, so nothing was probed. "
                           "Absence of a probe is not absence of a confound.",
                           item="confound_probes"))
    elif not (signed and coh.evaluable()):
        ev.append(Evidence("confound_probes", "adversarial", NOT_RUN,
                           "probes need a signed prediction and an evaluable cohort", item="confound_probes"))
    else:
        a_out = auc_abs(coh.y, coh.values)
        # Orient the candidate so that "higher score" always means "declared direction", and both
        # conditional statistics below read on the same scale as the primary AUC.
        oriented = coh.values * (1.0 if predicted == "higher" else -1.0)
        for name, v in sorted(coh.nuisance.items()):
            strength, how, rho = _probe_strength(coh.values, v)
            if not np.isfinite(strength):
                ev.append(Evidence(f"probe:{name}", "adversarial", NOT_RUN,
                                   f"could not evaluate ({how})", item="confound_probes"))
                continue

            # Categorical nuisances are held constant by stratification; continuous ones by rank
            # residualisation, because tertiles leave far too much of a continuous confound in place.
            if _is_categorical(v):
                strata = _strata_of(v)
                cond_name = f"stratified within {int(len(np.unique(strata)))} levels of {name}"
                stat = lambda idx: stratified_auc(coh.y[idx], oriented[idx], strata[idx])  # noqa: E731
            else:
                cond_name = f"rank-residualised on {name} (linear + quadratic)"
                stat = lambda idx: residual_auc(coh.y[idx], oriented[idx], np.asarray(v, float)[idx])  # noqa: E731
            a_cond = stat(np.arange(coh.n))
            wlo, whi, _ = cluster_bootstrap_ci(stat, coh.subject, rng, reps=BOOT_REPS)

            clause1 = bool(strength > a_out)                            # tracks the nuisance better
            clause2 = bool(np.isfinite(wlo) and np.isfinite(whi) and (wlo <= 0.5 <= whi))
            fired = bool(clause1 and clause2)
            rho_s = f", |rho|={rho:.3f}" if np.isfinite(rho) else ""
            ev.append(Evidence(
                f"probe:{name}", "adversarial", FAIL if fired else PASS,
                (f"the candidate predicts {name} better than it predicts the outcome "
                 f"({strength:.3f} vs {a_out:.3f}{rho_s}, {how}) AND its outcome association vanishes "
                 f"once {name} is held constant ({cond_name}: AUC {a_cond:.3f} [{wlo:.3f}, {whi:.3f}], "
                 f"spanning 0.5). Both clauses of the pre-specified rule are met, so the association is "
                 f"carried by {name}, not by the candidate.") if fired else
                (f"probe strength {strength:.3f} vs outcome {a_out:.3f} ({how}{rho_s}); {cond_name} gives "
                 f"AUC {a_cond:.3f} [{wlo:.3f}, {whi:.3f}]. "
                 + ("the candidate does track this nuisance, but its outcome association survives holding "
                    "the nuisance constant" if clause1 else
                    "the candidate does not track this nuisance more strongly than the outcome")),
                {"probe_auc": strength, "outcome_auc": a_out, "conditional_auc": a_cond,
                 "cond_lo": wlo, "cond_hi": whi, "clause1": clause1, "clause2": clause2,
                 "method": cond_name},
                fatal=True, item="confound_probes"))

    # --- trivial baseline ---------------------------------------------------------------------------
    if coh.baseline is None:
        ev.append(Evidence("beats_trivial_baseline", "adversarial", NOT_RUN,
                           "no baseline was supplied; a candidate that has not been compared with the "
                           "simplest alternative has not been evaluated",
                           item="baseline_comparison"))
    elif not (signed and coh.evaluable()):
        ev.append(Evidence("beats_trivial_baseline", "adversarial", NOT_RUN,
                           "baseline comparison needs a signed prediction and an evaluable cohort",
                           item="baseline_comparison"))
    elif np.allclose(np.nan_to_num(coh.values), np.nan_to_num(coh.baseline), equal_nan=True):
        # The trivial baseline IS one of the registered candidates, so it inevitably gets compared against
        # itself: increment exactly 0, interval [0, 0], rank correlation 1.000, reported as a FAILURE. That
        # is arithmetically true and completely uninformative, and it made the baseline look refuted in
        # E03's first run. A candidate cannot fail to beat itself; there is nothing to test.
        ev.append(Evidence(
            "beats_trivial_baseline", "adversarial", NOT_APPLICABLE,
            f"this candidate IS the comparison baseline ({coh.baseline_name}) -- the two value vectors are "
            "identical, so the increment is exactly zero by construction and carries no information. "
            "Nothing is being withheld: the baseline's own worth is judged by its discrimination and "
            "calibration, not by beating itself.",
            {"r_with_baseline": 1.0, "complexity": cand.complexity},
            item="baseline_comparison"))
        ev.append(Evidence(
            "complexity_is_earned", "adversarial", NOT_APPLICABLE,
            f"complexity {cand.complexity} is the reference point other candidates are measured against, "
            "so there is no simpler alternative for it to earn its keep over.",
            {"complexity": cand.complexity}, item="complexity_interpretability"))
    else:
        a_c = directional_auc(coh.y, coh.values, predicted)
        a_b = directional_auc(coh.y, coh.baseline, predicted)
        lo, hi, _ = cluster_bootstrap_ci(
            lambda idx: (directional_auc(coh.y[idx], coh.values[idx], predicted)
                         - directional_auc(coh.y[idx], coh.baseline[idx], predicted)),
            coh.subject, rng, reps=BOOT_REPS)
        better = bool(np.isfinite(lo) and lo > 0.0)
        r = abs(spearman(coh.values, coh.baseline))
        ev.append(Evidence(
            "beats_trivial_baseline", "adversarial", PASS if better else FAIL,
            f"candidate AUC {a_c:.3f} vs {coh.baseline_name} {a_b:.3f}; paired difference "
            f"{a_c - a_b:+.3f} [{lo:+.3f}, {hi:+.3f}]. "
            + ("the increment's interval excludes zero" if better else
               "the increment's interval includes zero, so the added structure is not earning its keep")
            + f" |rank correlation with the baseline| = {r:.3f}.",
            {"auc_candidate": a_c, "auc_baseline": a_b, "delta": a_c - a_b,
             "delta_lo": lo, "delta_hi": hi, "r_with_baseline": r, "complexity": cand.complexity},
            item="baseline_comparison"))
        ev.append(Evidence(
            "complexity_is_earned", "adversarial",
            PASS if (better or cand.complexity <= 2) else FAIL,
            f"complexity {cand.complexity} against an increment of {a_c - a_b:+.3f} over a "
            f"complexity-2 baseline. "
            + ("earned" if better else
               "a candidate that does not beat the simplest alternative cannot justify being more "
               "complicated than it"),
            {"complexity": cand.complexity, "delta": a_c - a_b},
            item="complexity_interpretability"))
    return ev


REDUNDANT_R = 0.98      # at or above this, two measures are the same measurement under two names
NEAR_REDUNDANT_R = 0.90


def check_redundancy(cand: Candidate, values: np.ndarray, baseline: np.ndarray,
                     baseline_name: str, baseline_complexity: int = 2) -> Evidence:
    """LABEL-FREE. Is this candidate a re-parameterisation of a simpler one?

    This check needs no outcome, no diagnosis and no cohort structure, which makes it the only part of the
    engine that can run on a dataset shipping nothing but EEG — and there are many such datasets. It is also
    the check that settles the question E01 was built to answer.

    It is FATAL above `REDUNDANT_R`, and only when the candidate is the more complex of the two. The
    reasoning: a candidate that correlates with a simpler measure at 0.98+ is not a distinct construct that
    happens to agree; it is the same number. If the candidate's declared interpretation claims to capture
    something the simpler measure does not — as UCE v1's claim to be a two-dimensional anteroposterior
    construct does — then that specific claim is refuted, whatever the candidate's predictive performance
    turns out to be. Performance and identity are separate questions and this check is about identity.

    Between NEAR_REDUNDANT_R and REDUNDANT_R the check fails non-fatally: the candidate may still be earning
    its extra complexity, but it must now do so explicitly against the baseline.

    Spearman rather than Pearson, so a monotone re-scaling of the same quantity is caught. That matters here
    because a weighted mean of two standardised variables is exactly such a re-scaling.
    """
    r = spearman(values, baseline)
    ar = abs(r) if np.isfinite(r) else float("nan")
    n = int((np.isfinite(np.asarray(values, float)) & np.isfinite(np.asarray(baseline, float))).sum())
    if not np.isfinite(ar):
        return Evidence("redundancy_with_simpler_measure", "adversarial", NOT_RUN,
                        "the rank correlation with the baseline could not be computed",
                        {"n": n}, item="complexity_interpretability")
    simpler = baseline_complexity < cand.complexity
    if ar >= REDUNDANT_R and simpler:
        return Evidence(
            "redundancy_with_simpler_measure", "adversarial", FAIL,
            f"|Spearman r| with {baseline_name} is {ar:.4f} across n={n} recordings, at or above the {REDUNDANT_R} "
            f"identity threshold, and the candidate is the more complex of the two "
            f"(complexity {cand.complexity} vs {baseline_complexity}). These are not two measures that "
            f"agree; they are one measure under two names. The candidate's declared interpretation — "
            f"\"{cand.interpretation[:120]}...\" — claims structure that this correlation shows is absent.",
            {"abs_spearman": ar, "n": n, "complexity": cand.complexity,
             "baseline_complexity": baseline_complexity, "threshold": REDUNDANT_R},
            fatal=True, item="complexity_interpretability")
    if not simpler:
        # No simpler alternative was offered, so redundancy is not even askable. Saying "below the
        # threshold" here would be a false statement whenever r is high -- and for the trivial baseline
        # compared against itself, r is exactly 1.
        return Evidence(
            "redundancy_with_simpler_measure", "adversarial", NOT_APPLICABLE,
            f"no simpler alternative was offered for comparison (candidate complexity {cand.complexity}, "
            f"comparator {baseline_name} at {baseline_complexity}), so there is nothing this candidate "
            f"could be a redundant re-parameterisation OF. The measured |Spearman r| of {ar:.4f} across "
            f"n={n} recordings is reported for the record and carries no verdict.",
            {"abs_spearman": ar, "n": n, "complexity": cand.complexity,
             "baseline_complexity": baseline_complexity},
            item="complexity_interpretability")
    status = FAIL if ar >= NEAR_REDUNDANT_R else PASS
    return Evidence(
        "redundancy_with_simpler_measure", "adversarial", status,
        f"|Spearman r| with {baseline_name} is {ar:.4f} across n={n} recordings"
        + (f", above the {NEAR_REDUNDANT_R} near-redundancy threshold; the extra complexity "
           f"({cand.complexity} vs {baseline_complexity}) must now be justified by a measured increment"
           if status == FAIL else
           ", below the near-redundancy threshold — the candidate is measuring something distinguishable"),
        {"abs_spearman": ar, "n": n, "complexity": cand.complexity,
         "baseline_complexity": baseline_complexity},
        item="complexity_interpretability")


def layer_cross_domain(cand: Candidate, cohorts: Sequence[Cohort], rng) -> list:
    """Layer 4. Leave-one-dataset-out: the direction must hold in every held-out dataset separately.

    Pooling datasets and reporting one number hides the case that matters — a candidate that works in one
    dataset and inverts in another. The check is therefore per-dataset and the verdict is the WORST one.
    """
    names = sorted({c.dataset for c in cohorts})
    if len(names) < 2:
        return [Evidence("leave_one_dataset_out", "cross_domain", NOT_RUN,
                         f"only {len(names)} dataset ({names}) — cross-domain transfer cannot be assessed "
                         "and must not be assumed",
                         {"datasets": names}, item="leave_one_dataset_out")]
    per = {}
    for coh in cohorts:
        predicted = cand.predicted(coh.contrast)
        if predicted not in ("higher", "lower") or not coh.evaluable():
            per[coh.dataset] = float("nan")
            continue
        per[coh.dataset] = directional_auc(coh.y, coh.values, predicted)
    finite = {k: v for k, v in per.items() if np.isfinite(v)}
    if len(finite) < 2:
        return [Evidence("leave_one_dataset_out", "cross_domain", NOT_RUN,
                         f"fewer than two datasets were evaluable: {per}", {"per_dataset": per},
                         item="leave_one_dataset_out")]
    worst = min(finite.values())
    consistent = all(v > 0.5 for v in finite.values())
    return [Evidence(
        "leave_one_dataset_out", "cross_domain", PASS if consistent else FAIL,
        f"per-dataset AUC in the declared direction: "
        + ", ".join(f"{k} {v:.3f}" for k, v in sorted(finite.items()))
        + (". the direction holds in every dataset" if consistent else
           f". the direction INVERTS in at least one dataset (worst {worst:.3f}); a pooled estimate would "
           "have hidden this"),
        {"per_dataset": finite, "worst": worst}, item="leave_one_dataset_out")]


# ---------------------------------------------------------------------------------------------------

def verify(cand: Candidate, cohorts: Sequence[Cohort], rng, search_space_size: int = 0,
           extra_evidence: Sequence[Evidence] = ()) -> VerifierReport:
    """Run every implementable layer and resolve the verdict.

    `extra_evidence` is how layer 1 (computational) enters: the synthetic ground-truth tests live in
    `tests/` and their outcome is passed in, because a verifier that graded its own implementation would be
    the blind spot the sibling project's rule 23 warns about.
    """
    if isinstance(cohorts, Cohort):
        cohorts = [cohorts]
    rep = VerifierReport(candidate=cand.name, candidate_version=cand.version,
                         declaration_hash=cand.declaration_hash(),
                         search_space_size=search_space_size,
                         required_layers=sorted(cand.requires),
                         datasets=sorted({c.dataset for c in cohorts}))
    for e in extra_evidence:
        rep.add(e)
    for coh in cohorts:
        for e in layer_statistical(cand, coh, rng):
            rep.add(e)
        for e in layer_adversarial(cand, coh, rng):
            rep.add(e)
    for e in layer_cross_domain(cand, cohorts, rng):
        rep.add(e)
    # Layers 5 and 7 are implemented and are called here; layer 6 is not, and keeps the stub.
    #
    # Blocking is preserved BY CONSTRUCTION rather than by intention: both layers emit NOT_RUN checks when
    # their preconditions are absent, and `decide()` turns any NOT_RUN inside a REQUIRED layer into
    # INCOMPLETE. So a candidate declaring `requires: temporal` is still unreportable on a table with one
    # window per state -- which is every table built before E14 -- and one declaring `requires: clinical`
    # stays unreportable until someone declares a prevalence.
    from bsde.verifier.clinical import layer_clinical
    from bsde.verifier.temporal import layer_temporal

    for coh in cohorts:
        state = coh.state if coh.state is not None else coh.y
        for e in layer_temporal(cand, coh.values, coh.subject, state, coh.y, rng, dataset=coh.dataset):
            rep.add(e)
        try:
            p_oof = cv_predict_proba(coh.values, coh.y, coh.subject, rng)
        except Exception:
            p_oof = np.full(coh.n, np.nan)
        for e in layer_clinical(cand, coh.y, p_oof, rng, prevalences=coh.prevalences,
                                dataset=coh.dataset):
            rep.add(e)

    if "mechanistic" in cand.requires:
        rep.add(Evidence("mechanistic_layer", "mechanistic", NOT_RUN,
                         "the candidate's declaration requires the mechanistic layer, which this engine "
                         "version does not implement. It is gated on DATA rather than on code -- it needs a "
                         "dissociation dataset (ketamine, locked-in, neuromuscular blockade) and none has "
                         "been ingested. The candidate cannot be reported as surviving."))
    return decide(rep)
