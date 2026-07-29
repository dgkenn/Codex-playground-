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

    null = permutation_null(lambda yp: directional_auc(yp, coh.values, predicted),
                            coh.y, coh.subject, rng, reps=PERM_REPS)
    ev.append(Evidence(
        "permutation_null_is_centred", "statistical",
        PASS if null["null_centered"] else FAIL,
        f"label-permuted null mean {null['mean']:.4f} (must sit at chance, 0.5 +/- 0.05)",
        {"null_mean": null["mean"], "null_q975": null["q975"], "n_perm": null["n"]},
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
         "perfectly is not a plausible physiological result; the likeliest explanations are label leakage, "
         "a circular derivation, or the outcome having been used to define the feature. This is a "
         "heuristic and it would also fire on a genuinely perfect biomarker — which is the correct default "
         "for EEG, where none exists.") if (np.isfinite(a) and a >= LEAKAGE_AUC) else
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
    for layer in ("temporal", "mechanistic", "clinical"):
        if layer in cand.requires:
            rep.add(Evidence(f"{layer}_layer", layer, NOT_RUN,
                             f"the candidate's declaration requires the {layer} layer, which this engine "
                             "version does not implement. The candidate therefore cannot be reported as "
                             "surviving.",
                             item="temporal_transition" if layer == "temporal" else ""))
    return decide(rep)
