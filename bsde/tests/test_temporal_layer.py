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
