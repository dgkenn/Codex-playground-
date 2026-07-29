"""Load-metric tests, with particular attention to the ways these numbers lie.

Three failure modes are covered explicitly because each one produces a plausible-looking number
that would silently misgovern the plan:

* TRIMP from a *mean* HR understates an interval session (the weighting is convex).
* ACWR computed for a beginner explodes, because chronic load starts at zero.
* Omitting rest days from the daily series inflates every rolling average.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from marathon_engine.load import (
    ACUTE_DAYS, ACWR_HARD_CAP, ACWR_SWEET_HIGH, ACWR_SWEET_LOW, CHRONIC_DAYS, DailyLoad,
    MAX_WEEKLY_RAMP, MONOTONY_WARN, acwr, ewma_load, hr_tss, monotony_strain, ramp_rate,
    session_rpe_load, trimp_banister, trimp_edwards, weekly_totals,
)
from marathon_engine.load import trimp_banister_series


# ---- Banister TRIMP ----------------------------------------------------------------------

def test_banister_trimp_matches_hand_calculation():
    # dHR = (150-55)/(187-55) = 0.71969...
    d = (150 - 55) / (187 - 55)
    expected = 60 * d * 0.64 * math.exp(1.92 * d)
    assert trimp_banister(60, 150, 55, 187) == pytest.approx(expected)


def test_banister_uses_female_coefficients_when_asked():
    male = trimp_banister(60, 150, 55, 187, female=False)
    female = trimp_banister(60, 150, 55, 187, female=True)
    assert male != female


def test_banister_is_zero_for_zero_duration():
    assert trimp_banister(0, 150, 55, 187) == 0.0


def test_banister_rejects_inverted_hr_anchors():
    with pytest.raises(ValueError):
        trimp_banister(60, 150, 190, 187)


def test_banister_clamps_supramaximal_hr():
    """A brief HR above the assumed max must not blow the load up without bound."""
    a = trimp_banister(10, 300, 55, 187)
    b = trimp_banister(10, 500, 55, 187)
    assert a == b


def test_convexity_mean_hr_understates_interval_session():
    """The documented trap: 30 min at 170 + 30 min at 110 is NOT 60 min at 140."""
    split = trimp_banister_series([(30, 170), (30, 110)], 55, 187)
    lumped = trimp_banister(60, 140, 55, 187)
    assert split > lumped, "convex weighting means the split session must score higher"


# ---- Edwards and session RPE --------------------------------------------------------------

def test_edwards_weights_zones_linearly():
    assert trimp_edwards({1: 10}) == 10
    assert trimp_edwards({5: 10}) == 50
    assert trimp_edwards({1: 30, 4: 10}) == 30 + 40


def test_edwards_ignores_unknown_zones():
    assert trimp_edwards({9: 100}) == 0


def test_session_rpe_load_is_the_product():
    assert session_rpe_load(6, 45) == 270


def test_session_rpe_rejects_out_of_range():
    with pytest.raises(ValueError):
        session_rpe_load(11, 45)
    with pytest.raises(ValueError):
        session_rpe_load(-1, 45)


def test_hr_tss_is_100_for_an_hour_at_threshold():
    assert hr_tss(60, lthr=160, mean_hr=160, hr_rest=55) == pytest.approx(100.0)


def test_hr_tss_scales_with_intensity_squared():
    half = hr_tss(60, mean_hr=55 + 0.5 * (160 - 55), lthr=160, hr_rest=55)
    assert half == pytest.approx(25.0)


# ---- EWMA and ACWR ------------------------------------------------------------------------

def test_ewma_of_constant_series_is_that_constant():
    assert ewma_load([50.0] * 30, 7) == pytest.approx(50.0)


def test_ewma_weights_recent_days_more():
    rising = ewma_load([0.0] * 20 + [100.0] * 7, 7)
    falling = ewma_load([100.0] * 20 + [0.0] * 7, 7)
    assert rising > falling


def test_ewma_rejects_bad_window():
    with pytest.raises(ValueError):
        ewma_load([1.0], 0)


def test_ewma_of_empty_is_zero():
    assert ewma_load([], 7) == 0.0


def test_acwr_reports_insufficient_history_for_a_beginner():
    """The critical guard: a new runner has zero chronic load, so the ratio is meaningless.

    Without this, week 1 of the plan would show a 'danger' ratio on the first easy jog and the
    governor would refuse to add any load at all.
    """
    r = acwr([0.0] * 6 + [40.0])
    assert r.band == "insufficient_history"
    assert "history" in r.note


def test_acwr_optimal_for_steady_load():
    r = acwr([50.0] * 40)
    assert r.band == "optimal"
    assert r.ratio == pytest.approx(1.0, abs=0.05)


def test_acwr_detects_a_spike():
    r = acwr([30.0] * 30 + [120.0] * 7)
    assert r.ratio > ACWR_SWEET_HIGH
    assert r.band in ("caution", "danger")


def test_acwr_detects_detraining():
    r = acwr([80.0] * 30 + [10.0] * 7)
    assert r.ratio < ACWR_SWEET_LOW
    assert r.band == "detraining"


def test_acwr_rolling_method_available_and_differs():
    loads = [30.0] * 30 + [90.0] * 7
    e = acwr(loads, method="ewma")
    r = acwr(loads, method="rolling")
    assert e.method == "ewma" and r.method == "rolling"
    assert e.ratio != r.ratio


def test_acwr_rejects_unknown_method():
    with pytest.raises(ValueError):
        acwr([1.0] * 40, method="magic")


def test_acwr_note_is_honest_about_the_evidence():
    """The band names sound authoritative; the note must say the metric is contested."""
    r = acwr([50.0] * 40)
    assert "not" in r.note.lower() and "risk score" in r.note.lower()


def test_acwr_handles_zero_chronic_load():
    r = acwr([0.0] * 40)
    assert r.band == "insufficient_history"
    assert r.ratio == 0.0


# ---- monotony and strain ------------------------------------------------------------------

def test_monotony_infinite_for_identical_days_and_strain_stays_finite():
    """Zero variance means infinite monotony. Strain must not become NaN/inf as a result --
    a non-finite strain would poison every downstream comparison."""
    m = monotony_strain([50.0] * 7)
    assert math.isinf(m.monotony)
    assert math.isfinite(m.strain)
    assert m.weekly_load == pytest.approx(350.0)
    # Seven identical sessions is the WORST monotony case, so it must be flagged. Regression guard:
    # an earlier version required monotony to be finite, which silently exempted exactly this case.
    assert m.flagged is True
    assert "rest day" in m.note


def test_monotony_flags_a_samey_week():
    m = monotony_strain([50, 50, 51, 49, 50, 50, 50])
    assert m.monotony > MONOTONY_WARN
    assert m.flagged
    assert "rest day" in m.note


def test_monotony_low_for_a_varied_week():
    m = monotony_strain([0, 60, 0, 90, 0, 40, 150])
    assert m.monotony < MONOTONY_WARN
    assert not m.flagged


def test_monotony_zero_load_week_is_not_flagged():
    m = monotony_strain([0.0] * 7)
    assert not m.flagged


def test_strain_is_load_times_monotony():
    m = monotony_strain([0, 60, 0, 90, 0, 40, 150])
    assert m.strain == pytest.approx(m.weekly_load * m.monotony)


def test_monotony_needs_two_days():
    m = monotony_strain([50.0])
    assert "2 days" in m.note


# ---- weekly aggregation and ramp ----------------------------------------------------------

def test_weekly_totals_group_by_monday():
    d = date(2026, 8, 5)          # a Wednesday
    loads = [DailyLoad(d, 30.0), DailyLoad(d + timedelta(days=1), 20.0),
             DailyLoad(d + timedelta(days=5), 40.0)]     # next Monday
    out = weekly_totals(loads)
    assert out[date(2026, 8, 3)] == 50.0
    assert out[date(2026, 8, 10)] == 40.0


def test_weekly_totals_sorted():
    d = date(2026, 8, 5)
    loads = [DailyLoad(d + timedelta(days=14), 10.0), DailyLoad(d, 10.0)]
    keys = list(weekly_totals(loads))
    assert keys == sorted(keys)


def test_ramp_rate_basic():
    assert ramp_rate(55, 50) == pytest.approx(0.10)


def test_ramp_rate_is_zero_from_a_standing_start():
    """First week of training has no ramp rate; returning inf would trip every guard on day one."""
    assert ramp_rate(20, 0) == 0.0


def test_max_weekly_ramp_is_ten_percent():
    assert MAX_WEEKLY_RAMP == pytest.approx(0.10)
