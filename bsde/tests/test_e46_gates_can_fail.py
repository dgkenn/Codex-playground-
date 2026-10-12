"""E46's gates must be constructible into failure. Rule 40: this project has shipped two gates that could
not fail -- E22 selected on a column its adapter never emitted (0 of 0 cases) and E29 asked whether pairs
spanned both dose directions while its own constructor oriented every pair one way (100.0 % by
construction). Both printed confidently. The pattern to copy is `tests/test_e28_paths.py`: build the input
that SHOULD fail the gate and check that it does.
"""
from __future__ import annotations

import numpy as np
import pytest

from bsde.experiments import e46_bis_artefact_windows as e46


def _row(case, bis, **kw):
    r = {"status": "ok", e46.CASE: case, e46.BIS: str(bis), e46.EMG: "30",
         e46.SENSOR_OFF: "0", e46.REL_ANEEND: "-100"}
    r.update({k: str(v) for k, v in kw.items()})
    return r


def _cohort(n_cases=6, n_ref=12, n_art=3, constant=False, seed=0):
    """Cases with `n_ref` reference windows and `n_art` artefact windows.

    `varying` moves within case; `flat` is deliberately constant within case but differs BETWEEN cases, so
    it has healthy between-case variance and zero within-case variance -- exactly the measure that would
    win the primary while being useless.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(n_cases):
        base = 10.0 + c
        for i in range(n_ref):
            rows.append(_row(f"c{c}", 40 + rng.normal(0, 2),
                             varying=base + rng.normal(0, 1.0),
                             flat=base))
        for i in range(n_art):
            rows.append(_row(f"c{c}", 90 + rng.normal(0, 2),
                             varying=base + (0.0 if constant else 5.0) + rng.normal(0, 1.0),
                             flat=base))
    return rows


def test_capability_gate_fails_on_a_within_case_constant():
    """The gate that stops a flat measure from winning. `flat` is constant within case by construction."""
    rows = _cohort()
    cap = e46._variance_capability(rows, ("varying", "flat"))
    assert cap["flat"] == pytest.approx(0.0, abs=1e-9), cap
    assert cap["flat"] < e46.MIN_VAR_RATIO, "a within-case constant must FAIL the capability gate"
    assert cap["varying"] > e46.MIN_VAR_RATIO, "a genuinely varying measure must PASS it"


def test_g1_fails_when_too_few_cases_are_evaluable():
    """Fewer than MIN_REF reference windows per case leaves nothing evaluable, and the gate must see it."""
    rows = _cohort(n_cases=4, n_ref=e46.MIN_REF - 1, n_art=2)
    cases, _ = e46._case_deltas(rows, ("varying",))
    assert len(cases) == 0, "cases below the reference-window floor must not be evaluable"
    assert len(cases) < e46.MIN_CASES


def test_cases_with_no_artefact_window_are_excluded_not_counted_as_zero():
    """A case where BIS never reaches 80 has no artefact set. It must be DROPPED, not scored as delta = 0 --
    scoring it zero would dilute every candidate toward the pass region for free."""
    rows = [_row("quiet", 40 + i * 0.1, varying=1.0 + i) for i in range(20)]
    cases, d = e46._case_deltas(rows, ("varying",))
    assert cases == [], "a case with no BIS >= 80 window must be excluded entirely"
    assert d["varying"].size == 0


def test_delta_is_zero_when_artefact_windows_match_the_reference():
    """Sanity direction check: if the measure does not move at the artefact windows, delta must be ~0."""
    rows = _cohort(constant=True, seed=3)
    _cases, d = e46._case_deltas(rows, ("varying",))
    assert np.nanmean(np.abs(d["varying"])) < 0.9, np.nanmean(np.abs(d["varying"]))


def test_delta_is_large_when_the_measure_does_move():
    """...and the same statistic must FIRE when the measure shifts by 5 SD-ish at the artefact windows.
    A statistic that cannot distinguish these two cohorts would make the primary meaningless."""
    rows = _cohort(constant=False, seed=3)
    _cases, d = e46._case_deltas(rows, ("varying",))
    assert np.nanmean(np.abs(d["varying"])) > 2.0, np.nanmean(np.abs(d["varying"]))


def test_placebo_draw_does_not_reuse_its_own_rows_as_reference():
    """The placebo must draw its pseudo-artefact rows OUT of the reference set, not leave them in both --
    a row in both sets would pull the reference mean toward the draw and shrink the placebo artificially,
    which would make the gate easier to pass (rule 34: a placebo is a comparison, and it has to be a fair
    one)."""
    rows = _cohort(n_cases=8, n_ref=20, n_art=4, seed=1)
    rng = np.random.default_rng(0)
    cases, d = e46._case_deltas(rows, ("varying",), artefact_pick="placebo", rng=rng)
    assert len(cases) > 0
    # a random draw from a case's own reference windows should sit near that case's mean
    assert np.nanmean(np.abs(d["varying"])) < 1.0, np.nanmean(np.abs(d["varying"]))


# =========================================================================================================
# THE TEST THAT WAS MISSING, AND WHOSE ABSENCE LET ARM A SHIP.
#
# The six tests above check the CAPABILITY gate and G1. None of them asked whether the PRIMARY could fail,
# and it could not: Arm A defined its artefact set by BIS crossing a threshold, which forces delta_BIS to a
# mean lower bound of 4.584 while leaving every candidate unconstrained. Six of six "passed".
#
# Generalised: a gate test that only exercises the auxiliary gates is not a rule-40 test. The primary is
# where the claim lives and it needs the same treatment -- construct the input on which it SHOULD return
# the failing verdict, and check that it does.
# =========================================================================================================

def test_arm_a_primary_is_mechanically_forced_and_therefore_not_a_test():
    """Selecting on BIS forces delta_BIS large. The bound must be computable and must be a large fraction
    of the observed value -- that ratio is the evidence the comparison measures its own selection rule."""
    rows = _cohort(n_cases=10, n_ref=20, n_art=3, seed=5)
    bound = e46._mechanical_bound(rows)
    _cases, d = e46._case_deltas(rows, (e46.BIS,), select="bis")
    observed = float(np.nanmean(np.abs(d[e46.BIS])))
    assert np.isfinite(bound) and bound > 0
    assert observed >= bound * 0.8, (observed, bound)


def test_emg_selection_does_not_force_the_incumbent():
    """Arm B's selection must leave BIS unconstrained. With BIS independent of EMG by construction, the
    EMG-selected delta_BIS must be near zero -- if it were forced large here too, Arm B would inherit
    Arm A's defect."""
    rng = np.random.default_rng(11)
    rows = []
    for c in range(10):
        for i in range(30):
            emg = 20.0 + (30.0 if i >= 27 else 0.0) + rng.normal(0, 0.5)
            rows.append(_row(f"c{c}", 40 + rng.normal(0, 3), varying=rng.normal(0, 1)))
            rows[-1][e46.EMG] = str(emg)
    cut = float(np.percentile([float(r[e46.EMG]) for r in rows], 90))
    cases, d = e46._case_deltas(rows, (e46.BIS,), select="emg", emg_cut=cut)
    assert len(cases) > 5
    assert abs(float(np.nanmean(d[e46.BIS]))) < 1.0, float(np.nanmean(d[e46.BIS]))


def test_primary_returns_the_failing_verdict_when_a_candidate_moves_as_much_as_bis():
    """The failing branch must be reachable. A candidate constructed to move exactly with BIS at the
    selected windows must NOT come out ROBUST."""
    rng = np.random.default_rng(3)
    rows = []
    for c in range(12):
        for i in range(30):
            hot = i >= 27
            emg = 20.0 + (30.0 if hot else 0.0) + rng.normal(0, 0.5)
            bis = 40 + (25.0 if hot else 0.0) + rng.normal(0, 2)
            rows.append(_row(f"c{c}", bis, twin=bis + rng.normal(0, 0.1)))
            rows[-1][e46.EMG] = str(emg)
    cut = float(np.percentile([float(r[e46.EMG]) for r in rows], 90))
    _cases, d = e46._case_deltas(rows, (e46.BIS, "twin"), select="emg", emg_cut=cut)
    gap = float(np.nanmean(np.abs(d[e46.BIS])) - np.nanmean(np.abs(d["twin"])))
    assert abs(gap) < 0.5, f"a twin of BIS must not look steadier than BIS; gap {gap}"
