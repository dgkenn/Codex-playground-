"""Readiness tests: the HRV band logic, and the hard overrides that must beat a good HRV number.

The band logic is the part that decides whether today's intervals happen, so the tests here focus
on the boundaries and on the precedence rules rather than on the cosmetic score.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from marathon_engine.readiness import (
    BAND_ACTIONS, MIN_BASELINE_NIGHTS, ROLLING_DAYS, SLEEP_FLOOR_MIN, SWC_MULTIPLIER,
    HrvBaseline, NightSummary, daily_readiness, hrv_baseline,
)

D0 = date(2026, 8, 1)


def nights(hrvs, *, sleep=450.0, rhr=55.0, start=D0, **kw):
    """Build a night series from a list of HRV values (``None`` = missing)."""
    out = []
    for i, h in enumerate(hrvs):
        out.append(NightSummary(day=start + timedelta(days=i), hrv_ms=h, resting_hr=rhr,
                                total_sleep_min=sleep, wake_events=1, sleep_efficiency=0.92,
                                clean_interval_count=5000, **kw))
    return out


# ---- lnRMSSD and usability ----------------------------------------------------------------

def test_ln_hrv_is_log_of_rmssd():
    n = NightSummary(day=D0, hrv_ms=60.0)
    assert n.ln_hrv == pytest.approx(math.log(60.0))


def test_ln_hrv_none_when_missing_or_nonpositive():
    assert NightSummary(day=D0).ln_hrv is None
    assert NightSummary(day=D0, hrv_ms=0.0).ln_hrv is None


def test_night_with_too_few_clean_intervals_is_unusable():
    """A sensor failure must not enter the baseline dressed up as a low-HRV night."""
    good = NightSummary(day=D0, hrv_ms=60.0, clean_interval_count=1000)
    bad = NightSummary(day=D0, hrv_ms=60.0, clean_interval_count=10)
    assert good.usable_hrv
    assert not bad.usable_hrv


def test_missing_clean_count_is_treated_as_usable():
    """Absence of a quality figure is not evidence of poor quality -- some sources do not report it."""
    assert NightSummary(day=D0, hrv_ms=60.0).usable_hrv


# ---- baseline ------------------------------------------------------------------------------

def test_no_baseline_below_minimum_nights():
    assert hrv_baseline(nights([60.0] * (MIN_BASELINE_NIGHTS - 1))) is None


def test_baseline_computed_at_minimum_nights():
    b = hrv_baseline(nights([60.0] * MIN_BASELINE_NIGHTS))
    assert b is not None
    assert b.n_nights == MIN_BASELINE_NIGHTS
    assert b.mean_ln == pytest.approx(math.log(60.0))


def test_baseline_statistics_are_on_the_log_scale():
    """HRV is log-normal; computing SD on raw ms would give the wrong SWC band."""
    vals = [40.0, 50.0, 60.0, 70.0, 80.0] * 4
    b = hrv_baseline(nights(vals))
    import statistics
    assert b.mean_ln == pytest.approx(statistics.fmean(math.log(v) for v in vals))
    assert b.swc == pytest.approx(SWC_MULTIPLIER * statistics.stdev([math.log(v) for v in vals]))


def test_baseline_band_brackets_the_mean():
    b = hrv_baseline(nights([50, 55, 60, 65, 70] * 4))
    assert b.low < b.mean_ln < b.high
    assert b.high - b.mean_ln == pytest.approx(b.swc)


def test_baseline_excludes_unusable_nights():
    ns = nights([60.0] * 20)
    ns[0].clean_interval_count = 5           # unusable
    b = hrv_baseline(ns)
    assert b.n_nights == 19


def test_baseline_respects_the_window():
    """Nights outside the rolling window must not contribute."""
    old = nights([100.0] * 20, start=date(2020, 1, 1))
    recent = nights([50.0] * 20, start=D0)
    b = hrv_baseline(old + recent, as_of=D0 + timedelta(days=19), window_days=60)
    assert b.mean_ln == pytest.approx(math.log(50.0))


def test_baseline_returns_none_for_empty():
    assert hrv_baseline([]) is None


# ---- band logic ----------------------------------------------------------------------------

def test_normal_band_when_hrv_sits_at_baseline():
    ns = nights([50, 55, 60, 65, 70] * 6)
    r = daily_readiness(ns)
    assert r.hrv_status == "within"
    assert r.band == "normal"
    assert r.action == BAND_ACTIONS["normal"]


def test_primed_when_rolling_mean_is_above_the_band():
    ns = nights([50, 55, 60, 65, 70] * 6) + nights([120.0] * 7, start=D0 + timedelta(days=30))
    r = daily_readiness(ns)
    assert r.hrv_status == "above"
    assert r.band == "primed"


def test_suppressed_when_rolling_mean_is_below_the_band():
    ns = nights([50, 55, 60, 65, 70] * 6) + nights([44.0] * 7, start=D0 + timedelta(days=30))
    r = daily_readiness(ns)
    assert r.hrv_status in ("below", "well_below")
    assert r.band in ("suppressed", "strained")
    assert r.action in ("downgrade_to_easy", "rest_or_walk")


def test_strained_requires_two_consecutive_well_below_days():
    """A single very low day suppresses; a sustained collapse is what triggers rest."""
    base = nights([50, 55, 60, 65, 70] * 6)
    deep = nights([20.0] * 7, start=D0 + timedelta(days=30))
    r = daily_readiness(base + deep)
    assert r.band == "strained"
    assert r.action == "rest_or_walk"


def test_unknown_band_without_a_baseline():
    r = daily_readiness(nights([60.0] * 5))
    assert r.hrv_status == "no_baseline"
    assert r.band == "unknown"
    assert r.action == "proceed_conservatively"


def test_empty_history_is_handled():
    r = daily_readiness([])
    assert r.band == "unknown"
    assert "baseline" in r.detail.lower()


def test_rolling_mean_needs_three_of_seven_days():
    """A '7-day mean' from one reading is one reading wearing a hat."""
    ns = nights([60.0] * 30)
    for n in ns[-6:]:
        n.hrv_ms = None
    r = daily_readiness(ns)
    assert r.rolling_ln_hrv is None


# ---- hard overrides ------------------------------------------------------------------------

def test_illness_forces_strained_regardless_of_hrv():
    ns = nights([120.0] * 30)          # excellent HRV
    ns[-1].illness = True
    r = daily_readiness(ns)
    assert r.band == "strained"
    assert r.override_reason == "illness reported"


def test_short_sleep_suppresses_even_with_good_hrv():
    ns = nights([60.0] * 30)
    ns[-1].total_sleep_min = SLEEP_FLOOR_MIN - 30
    r = daily_readiness(ns)
    assert r.band in ("suppressed", "strained")
    assert r.override_reason is not None


def test_short_sleep_plus_low_hrv_is_strained():
    ns = nights([60.0] * 24) + nights([40.0] * 7, start=D0 + timedelta(days=24))
    ns[-1].total_sleep_min = SLEEP_FLOOR_MIN - 60
    r = daily_readiness(ns)
    assert r.band == "strained"


def test_high_severity_flag_beats_a_good_hrv_number():
    """A good HRV reading must not out-vote an elevated resting HR or severe short sleep."""
    ns = nights([60.0] * 30)
    ns[-1].total_sleep_min = 300          # 5 h -> high-severity flag
    r = daily_readiness(ns)
    assert r.band != "primed"
    assert any(f["severity"] == "high" for f in r.flags)


def test_elevated_rhr_is_flagged():
    ns = nights([60.0] * 30, rhr=55.0)
    # Give the baseline some RHR variance so the z-score is computable.
    for i, n in enumerate(ns):
        n.resting_hr = 54.0 + (i % 3)
    ns[-1].resting_hr = 70.0
    r = daily_readiness(ns)
    assert any(f["flag"] == "elevated_rhr" for f in r.flags)


def test_subjective_soreness_penalises_the_score():
    a = daily_readiness(nights([60.0] * 30))
    ns = nights([60.0] * 30)
    ns[-1].soreness_1_7 = 6
    ns[-1].fatigue_1_7 = 6
    b = daily_readiness(ns)
    assert b.score < a.score
    assert any("soreness" in f["flag"] for f in b.flags)


def test_sleep_debt_penalises_and_flags():
    ns = nights([60.0] * 30)
    ns[-1].sleep_debt_min = 400
    r = daily_readiness(ns)
    assert any(f["flag"] == "sleep_debt" for f in r.flags)


def test_score_is_bounded():
    for hrv in (5.0, 60.0, 300.0):
        r = daily_readiness(nights([hrv] * 30))
        assert 0 <= r.score <= 100


def test_narration_is_actionable_not_vague():
    ns = nights([60.0] * 24) + nights([40.0] * 7, start=D0 + timedelta(days=24))
    r = daily_readiness(ns)
    assert r.headline
    # The detail must say what to DO, not just report a state.
    assert any(w in r.detail.lower() for w in ("easy", "rest", "walk", "z1", "z2"))


def test_to_dict_is_serialisable():
    import json
    r = daily_readiness(nights([50, 55, 60, 65, 70] * 6))
    json.dumps(r.to_dict())
