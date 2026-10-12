"""Ground-truth tests for verifier layer 5 (temporal).

THE TEST THAT JUSTIFIES THE LAYER is `test_a_measure_with_perfect_group_auc_can_fail_the_temporal_layer`.
It plants a measure that layers 2-4 would wave through — group AUC 1.0, no leakage, no confound — and whose
window-to-window scatter within a state is larger than the gap between states. Such a measure is useless on
the single window a clinician actually has, and before this layer existed nothing in the engine could see it.

The mirror test (`..._and_a_stable_one_passes`) exists so the layer is not merely a machine for failing
things: the same construction with small within-state scatter must pass.

The remaining tests pin the behaviour that keeps a NOT_RUN honest. Every feature table this project currently
has holds ONE window per state, so `temporal_snr` must report NOT_RUN on all of them, and a candidate whose
declaration requires the temporal layer must still be blocked. A layer that silently passed on tables it
cannot evaluate would be worse than no layer, because it would convert an absent check into a satisfied one.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from bsde.verifier.report import FAIL, NOT_RUN, PASS
from bsde.verifier.temporal import (MIN_WINDOWS_PER_STATE, intraclass_correlation, layer_temporal,
                                    single_window_penalty, temporal_snr)


def _panel(n_subj=30, n_win=5, state_gap=10.0, within_sd=1.0, seed=0):
    """Repeated windows for two states per subject, with controlled within-state scatter."""
    rng = np.random.default_rng(seed)
    vals, subj, state, y = [], [], [], []
    for s in range(n_subj):
        level = rng.normal(0.0, 2.0)                      # subject-level offset
        for st, shift in (("A", 0.0), ("B", state_gap)):
            for _ in range(n_win):
                vals.append(level + shift + rng.normal(0.0, within_sd))
                subj.append(f"s{s:02d}")
                state.append(st)
                y.append(0.0 if st == "A" else 1.0)
    return (np.array(vals), np.array(subj), np.array(state), np.array(y))


# --- the test the layer exists for -----------------------------------------------------------------

def test_a_measure_with_perfect_group_auc_can_fail_the_temporal_layer():
    """A measure separating two states perfectly at the GROUP level, unusable on one window.

    within_sd 12 against a state gap of 10: averaged over five windows the state difference is obvious, and
    on any single window it is buried. Layers 2-4 see only the average and would pass it.
    """
    vals, subj, state, y = _panel(state_gap=10.0, within_sd=12.0, seed=1)
    ev = {e.check: e for e in layer_temporal(None, vals, subj, state, y, np.random.default_rng(0))}
    assert ev["temporal_snr"].status == FAIL, ev["temporal_snr"].values
    assert ev["temporal_snr"].fatal, "an unusable-on-one-window measure must be a refutation, not a note"
    assert ev["temporal_snr"].values["snr"] < 1.0


def test_and_a_stable_one_passes():
    vals, subj, state, y = _panel(state_gap=10.0, within_sd=0.5, seed=1)
    ev = {e.check: e for e in layer_temporal(None, vals, subj, state, y, np.random.default_rng(0))}
    assert ev["temporal_snr"].status == PASS, ev["temporal_snr"].values
    assert ev["temporal_snr"].values["snr"] > 5.0


def test_the_snr_is_a_ratio_of_the_two_reported_terms():
    """The reason for reporting both terms is that a bad ratio must be attributable. Pin the arithmetic."""
    vals, subj, state, _ = _panel(state_gap=8.0, within_sd=2.0, seed=3)
    r = temporal_snr(vals, subj, state)
    assert r["snr"] == pytest.approx(r["between"] / r["within"], rel=1e-9)


# --- NOT_RUN must stay honest ----------------------------------------------------------------------

def test_one_window_per_state_gives_NOT_RUN_not_PASS():
    """The shape of every feature table this project currently has."""
    vals, subj, state, y = _panel(n_win=1, seed=4)
    ev = {e.check: e for e in layer_temporal(None, vals, subj, state, y, np.random.default_rng(0))}
    for check in ("temporal_snr", "single_window_auc_penalty", "effective_sample_size"):
        assert ev[check].status == NOT_RUN, f"{check} claimed a result it cannot have"
    assert not ev["temporal_snr"].fatal, "NOT_RUN is not a refutation either"
    assert ev["temporal_snr"].values["max_windows_per_subject_state"] == 1


def test_two_windows_is_still_not_enough():
    """MIN_WINDOWS_PER_STATE is 3 because a spread from two points is a single difference."""
    assert MIN_WINDOWS_PER_STATE == 3
    vals, subj, state, y = _panel(n_win=2, seed=5)
    ev = {e.check: e for e in layer_temporal(None, vals, subj, state, y, np.random.default_rng(0))}
    assert ev["temporal_snr"].status == NOT_RUN


def test_the_not_run_reason_says_unmeasured_rather_than_adequate():
    """Wording is load-bearing here: an absent check must not read as a satisfied one."""
    vals, subj, state, y = _panel(n_win=1, seed=6)
    ev = {e.check: e for e in layer_temporal(None, vals, subj, state, y, np.random.default_rng(0))}
    reason = ev["temporal_snr"].reason.lower()
    assert "unmeasured" in reason
    assert "not the same as" in reason


# --- the supporting statistics ---------------------------------------------------------------------

def test_single_window_penalty_is_positive_when_windows_are_noisy():
    vals, subj, state, y = _panel(state_gap=3.0, within_sd=6.0, seed=7)
    r = single_window_penalty(vals, subj, y, np.random.default_rng(0))
    assert np.isfinite(r["penalty"])
    assert r["penalty"] > 0, "averaging must help when the windows are noisy"


def test_single_window_penalty_is_near_zero_when_windows_are_clean():
    vals, subj, state, y = _panel(state_gap=10.0, within_sd=0.2, seed=8)
    r = single_window_penalty(vals, subj, y, np.random.default_rng(0))
    assert abs(r["penalty"]) < 0.05, r


def test_penalty_does_not_punish_a_candidate_for_running_below_half():
    """Both AUCs are folded to the same side of 0.5 before differencing. Without that, a measure whose
    association is inverted would post an enormous 'penalty' purely because of its direction."""
    vals, subj, state, y = _panel(state_gap=10.0, within_sd=0.2, seed=9)
    flipped = single_window_penalty(-vals, subj, y, np.random.default_rng(0))
    assert abs(flipped["penalty"]) < 0.05, flipped
    assert flipped["mean_auc"] < 0.5, "the setup should genuinely invert the association"


def test_icc_is_high_when_subjects_differ_and_windows_agree():
    rng = np.random.default_rng(10)
    vals, subj = [], []
    for s in range(25):
        level = rng.normal(0, 10)
        for _ in range(4):
            vals.append(level + rng.normal(0, 0.1))
            subj.append(f"s{s}")
    r = intraclass_correlation(np.array(vals), np.array(subj))
    assert r["icc"] > 0.95, r
    assert r["n_eff"] < 0.35 * r["n_rows"], "high ICC must collapse the effective sample size"


def test_icc_is_low_when_windows_are_independent_noise():
    rng = np.random.default_rng(11)
    vals = rng.normal(size=100)
    subj = np.array([f"s{i // 4}" for i in range(100)])
    r = intraclass_correlation(vals, subj)
    assert r["icc"] < 0.25, r
    assert r["n_eff"] > 0.7 * r["n_rows"]


def test_icc_never_reports_a_negative_correlation_as_extra_information():
    """A negative variance-component estimate is a sampling artefact, not evidence that windows are
    ANTI-correlated, and letting it through would inflate n_eff above n_rows."""
    rng = np.random.default_rng(12)
    vals = rng.normal(size=120)
    subj = np.array([f"s{i % 30}" for i in range(120)])   # deliberately scrambles any subject structure
    r = intraclass_correlation(vals, subj)
    assert r["icc"] >= 0.0
    assert r["n_eff"] <= r["n_rows"] + 1e-9


# --- integration with the engine's blocking behaviour ----------------------------------------------

def test_a_candidate_requiring_the_temporal_layer_is_still_blocked_by_verify():
    """`critical_slowing_ar1` declares `requires: temporal`. Until a table with repeated windows exists it
    must remain unreportable, and E08's P4 is the standing check on that."""
    from bsde.candidates.seed import seed_registry
    from bsde.candidates.registry import REGISTRY
    seed_registry()
    cand = REGISTRY.get("critical_slowing_ar1")
    assert "temporal" in cand.requires, (
        "if this ever stops being true, the layer's blocking behaviour is no longer being exercised")


# --- the wiring: layers 5 and 7 must actually RUN inside verify(), not just exist -------------------

def _cand(requires):
    from bsde.candidates.registry import Candidate
    return Candidate(
        name="probe", version="1.0", fn=lambda *a, **k: 0.0,
        interpretation="a throwaway candidate used only to exercise the engine's layer wiring",
        predictions={"unconscious_vs_awake": "higher"},
        failure_conditions=["it fails any required layer"],
        requires=tuple(requires), complexity=1)


def test_verify_runs_the_temporal_layer_when_repeated_windows_are_supplied():
    """The wiring test. Before layers 5 and 7 were connected, `verify()` emitted a hardcoded NOT_RUN stub for
    'temporal' regardless of the data, so a table WITH repeated windows would still have been treated as
    unmeasured. This asserts the real checks appear."""
    from bsde.verifier.engine import Cohort, verify
    # gap/scatter chosen so the pooled AUC is ~0.93, BELOW the engine's 0.98 leakage threshold. The first
    # version used gap 10 with scatter 0.5, which separates the classes perfectly; `label_leakage` fired and
    # the verdict was REJECT before completeness was ever reached. The engine was right and the fixture was
    # unrealistic -- a synthetic panel has to look like data the engine would accept, or it tests the wrong
    # branch.
    vals, subj, state, y = _panel(n_subj=30, n_win=4, state_gap=3.5, within_sd=0.5, seed=20)
    coh = Cohort(values=vals, y=y, subject=subj, state=state, contrast="unconscious_vs_awake",
                 dataset="synthetic")
    rep = verify(_cand(("computational", "temporal")), [coh], np.random.default_rng(0))
    checks = {e.check: e for e in rep.evidence if e.layer == "temporal"}
    assert "temporal_snr" in checks, sorted(checks)
    assert checks["temporal_snr"].status == PASS, checks["temporal_snr"].values
    assert "temporal_layer" not in checks, "the hardcoded stub must be gone when the layer can run"


def test_verify_still_blocks_a_temporal_candidate_on_a_one_window_table():
    """The behaviour that must NOT change. Every table built before E14 has one window per state, and a
    candidate declaring `requires: temporal` has to stay unreportable on those — otherwise wiring the layer
    in would have converted a blocked candidate into a surviving one, which is the opposite of the point."""
    from bsde.verifier.engine import Cohort, verify
    from bsde.verifier.report import INCOMPLETE, SURVIVE
    vals, subj, state, y = _panel(n_subj=30, n_win=1, state_gap=3.0, within_sd=0.5, seed=21)
    coh = Cohort(values=vals, y=y, subject=subj, state=state, contrast="unconscious_vs_awake",
                 dataset="synthetic")
    rep = verify(_cand(("computational", "temporal")), [coh], np.random.default_rng(0))
    assert rep.verdict != SURVIVE
    assert rep.verdict == INCOMPLETE, (rep.verdict, rep.verdict_reasons)
    assert any("temporal_snr" in r for r in rep.verdict_reasons), rep.verdict_reasons


def test_verify_blocks_a_clinical_candidate_until_a_prevalence_is_declared():
    """Layer 7 refuses to invent a prevalence, so a candidate requiring it stays INCOMPLETE until the caller
    supplies one. That is the discipline, not an oversight."""
    from bsde.verifier.engine import Cohort, verify
    from bsde.verifier.report import INCOMPLETE
    vals, subj, state, y = _panel(n_subj=30, n_win=1, state_gap=3.0, within_sd=0.5, seed=22)
    bare = Cohort(values=vals, y=y, subject=subj, contrast="unconscious_vs_awake", dataset="synthetic")
    rep = verify(_cand(("computational", "clinical")), [bare], np.random.default_rng(0))
    assert rep.verdict == INCOMPLETE
    assert any("prevalence_sensitivity" in r for r in rep.verdict_reasons), rep.verdict_reasons


def test_declaring_a_prevalence_lets_the_clinical_layer_run():
    from bsde.verifier.engine import Cohort, verify
    vals, subj, state, y = _panel(n_subj=30, n_win=1, state_gap=3.0, within_sd=0.5, seed=23)
    coh = Cohort(values=vals, y=y, subject=subj, contrast="unconscious_vs_awake", dataset="synthetic",
                 prevalences=(0.2, 0.05))
    rep = verify(_cand(("computational", "clinical")), [coh], np.random.default_rng(0))
    checks = {e.check: e for e in rep.evidence if e.layer == "clinical"}
    assert checks["prevalence_sensitivity"].status != NOT_RUN, checks["prevalence_sensitivity"].reason
    assert "by_prevalence" in checks["prevalence_sensitivity"].values


def test_the_mechanistic_stub_survives_and_says_it_is_gated_on_data():
    """Layer 6 is genuinely unimplemented and must keep blocking — but its message should say it needs a
    dissociation DATASET, not more code, because that determines what someone does about it."""
    from bsde.verifier.engine import Cohort, verify
    vals, subj, state, y = _panel(n_subj=30, n_win=1, state_gap=3.0, within_sd=0.5, seed=24)
    coh = Cohort(values=vals, y=y, subject=subj, contrast="unconscious_vs_awake", dataset="synthetic")
    rep = verify(_cand(("computational", "mechanistic")), [coh], np.random.default_rng(0))
    stub = [e for e in rep.evidence if e.layer == "mechanistic"]
    assert stub and stub[0].status == NOT_RUN
    assert "dataset" in stub[0].reason.lower() and "ketamine" in stub[0].reason.lower()


def test_icc_groups_by_cell_not_by_subject_when_state_is_supplied():
    """The regression for E14's inverted result. Repeated windows inside ONE state are near-identical; a
    subject's windows ACROSS states are not. Grouping by subject alone buries the first fact under the
    second and reports near-independence for data that is anything but."""
    rng = np.random.default_rng(30)
    vals, subj, state = [], [], []
    for s in range(20):
        level = rng.normal(0, 1.0)
        for st, shift in (("A", 0.0), ("B", 50.0)):        # a huge between-state gap
            base = level + shift
            for _ in range(3):
                vals.append(base + rng.normal(0, 0.05))    # windows within a state are near-identical
                subj.append(f"s{s}")
                state.append(st)
    vals, subj, state = np.array(vals), np.array(subj), np.array(state)
    by_subject = intraclass_correlation(vals, subj)["icc"]
    by_cell = intraclass_correlation(vals, subj, state)["icc"]
    assert by_cell > 0.95, by_cell
    assert by_subject < by_cell - 0.3, (
        f"grouping by subject ({by_subject:.3f}) must understate the true within-cell dependence "
        f"({by_cell:.3f}); if it does not, this test no longer reproduces E14's failure")


def test_layer_temporal_passes_state_through_to_the_icc():
    vals, subj, state, y = _panel(n_subj=30, n_win=4, state_gap=3.5, within_sd=0.05, seed=31)
    ev = {e.check: e for e in layer_temporal(None, vals, subj, state, y, np.random.default_rng(0))}
    assert ev["effective_sample_size"].values["icc"] > 0.5, ev["effective_sample_size"].values
