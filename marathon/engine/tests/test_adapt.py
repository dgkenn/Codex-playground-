"""Adaptation tests: readiness downgrades, shift rescheduling, and the never-carry-load-forward rule.

The single most important invariant in this file is that a missed session is never made up. That is
the rule which stops a disrupted week from becoming next week's load spike, and it is tested from
several directions because it is also the rule a well-meaning implementation is most likely to break.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from marathon_engine.load import ACWR_HARD_CAP, MAX_WEEKLY_RAMP, AcwrResult, acwr
from marathon_engine.adapt import (
    POST_NIGHT_BLOCK_H, QUALITY_TYPES, ShiftDay, apply_readiness, replan_week, reschedule_week,
)
from marathon_engine.assessment import RampStage, RampTest, profile_from_ramp
from marathon_engine.plan import (
    CUTBACK_FACTOR, Phase, PlanConfig, Session, SessionType, generate_week,
)
from marathon_engine.readiness import NightSummary, Readiness, daily_readiness

MONDAY = date(2026, 8, 3)


@pytest.fixture(scope="module")
def profile():
    ramp = RampTest(day=date(2026, 8, 3), age=30, hr_rest=55, temp_c=19, stages=[
        RampStage(5.0, 98, 8, "comfortable", 118),
        RampStage(6.0, 112, 10, "comfortable", 132),
        RampStage(7.0, 133, 12, "comfortable", 152),
        RampStage(8.0, 151, 14, "effortful", 160),
        RampStage(9.0, 166, 16, "impossible", 166),
    ])
    return profile_from_ramp(ramp)


def band(name: str) -> Readiness:
    return Readiness(day=MONDAY, band=name,
                     action={"primed": "proceed_or_upgrade", "normal": "proceed",
                             "suppressed": "downgrade_to_easy", "strained": "rest_or_walk",
                             "unknown": "proceed_conservatively"}[name],
                     score=50, hrv_status="within", rolling_ln_hrv=4.0, baseline=None,
                     headline="h", detail="d",
                     override_reason=None if name in ("primed", "normal") else "HRV below band")


def threshold_session():
    return Session(day_offset=1, type=SessionType.THRESHOLD, title="Threshold 3 x 8 min",
                   duration_min=60, zones=(4,), intent="raise threshold")


# ---- readiness -> today's session ------------------------------------------------------------

def test_normal_readiness_leaves_the_session_alone():
    s = threshold_session()
    out, adj = apply_readiness(s, band("normal"))
    assert out is s and not adj


def test_primed_does_not_upgrade_automatically():
    """Asymmetry by design: a good HRV reading is permission to run the plan well, not to add load."""
    s = threshold_session()
    out, adj = apply_readiness(s, band("primed"))
    assert out is s and not adj
    assert out.type == SessionType.THRESHOLD


def test_suppressed_downgrades_quality_to_easy_at_the_same_duration():
    s = threshold_session()
    out, adj = apply_readiness(s, band("suppressed"), paces_easy_sec_km=420.0)
    assert out.type == SessionType.EASY
    assert out.duration_min == s.duration_min, "time on feet is preserved; only intensity goes"
    assert adj and "downgraded" in adj[0].change


def test_suppressed_explains_that_the_workout_is_not_lost():
    s = threshold_session()
    out, _ = apply_readiness(s, band("suppressed"))
    assert "not lost" in out.intent.lower()


def test_strained_cancels_to_rest():
    s = threshold_session()
    out, adj = apply_readiness(s, band("strained"))
    assert out.type == SessionType.REST
    assert any("walk" in c.lower() for c in out.cues)
    assert adj


def test_suppressed_strips_marathon_pace_from_a_long_run():
    s = Session(day_offset=6, type=SessionType.MARATHON_PACE, title="Long + MP",
                duration_min=150, intent="rehearse race pace")
    out, adj = apply_readiness(s, band("suppressed"))
    assert out.type == SessionType.LONG
    assert "removed" in out.structure.lower()


def test_suppressed_keeps_the_long_run_but_permits_cutting_it_short():
    s = Session(day_offset=6, type=SessionType.LONG, title="Long run", duration_min=120,
                intent="time on feet")
    out, adj = apply_readiness(s, band("suppressed"))
    assert out.type == SessionType.LONG
    assert any("cut it short" in c.lower() for c in out.cues)


def test_unknown_band_adds_an_easy_caution_without_changing_the_session():
    s = Session(day_offset=1, type=SessionType.EASY, title="Easy", duration_min=40, intent="aerobic")
    out, adj = apply_readiness(s, band("unknown"))
    assert out.type == SessionType.EASY
    assert any("easy" in c.lower() for c in out.cues)
    assert not adj


def test_strength_session_is_untouched_by_suppressed_readiness():
    s = Session(day_offset=0, type=SessionType.STRENGTH, title="Strength", duration_min=45,
                intent="prehab")
    out, adj = apply_readiness(s, band("suppressed"))
    assert out.type == SessionType.STRENGTH


# ---- shift rescheduling ----------------------------------------------------------------------

def rota(kinds):
    return [ShiftDay(MONDAY + timedelta(days=i), kind=k) for i, k in enumerate(kinds)]


def test_nothing_is_scheduled_on_a_night_shift(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    r = rota(["day", "night", "post_night", "day", "night", "post_night", "off"])
    out, adj = reschedule_week(week, r)
    night_offsets = {1, 4}
    for s in out.sessions:
        if s.type != SessionType.REST:
            assert s.day_offset not in night_offsets, f"{s.title} scheduled on a night shift"


def test_quality_is_not_scheduled_post_night(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    r = rota(["day", "night", "post_night", "day", "off", "off", "off"])
    out, adj = reschedule_week(week, r)
    for s in out.sessions:
        if s.type in QUALITY_TYPES:
            assert s.day_offset != 2, "quality work landed on a post-night day"


def test_long_run_gets_first_pick_of_days(profile):
    week = generate_week(profile, Phase.MARATHON_BASE, 4)
    # Only two viable days: Wednesday(2) and Sunday(6).
    r = rota(["night", "night", "off", "night", "night", "night", "off"])
    out, adj = reschedule_week(week, r)
    longs = [s for s in out.sessions if s.type in (SessionType.LONG, SessionType.MARATHON_PACE)]
    assert longs, "the long run must survive a bad week"
    assert longs[0].day_offset in (2, 6)


def test_long_run_prefers_the_configured_day_when_available(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    out, adj = reschedule_week(week, rota(["off"] * 7), config=PlanConfig())
    longs = [s for s in out.sessions if s.type == SessionType.LONG]
    assert longs[0].day_offset == 6


def test_quality_and_long_run_are_kept_apart(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    out, adj = reschedule_week(week, rota(["off"] * 7))
    long_day = next(s.day_offset for s in out.sessions if s.type == SessionType.LONG)
    for s in out.sessions:
        if s.type in QUALITY_TYPES:
            gap = min(abs(s.day_offset - long_day), 7 - abs(s.day_offset - long_day))
            assert gap >= 2, "hard sessions must not be adjacent"


def test_strength_is_not_the_day_before_the_long_run(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    out, adj = reschedule_week(week, rota(["off"] * 7))
    long_day = next(s.day_offset for s in out.sessions if s.type == SessionType.LONG)
    for s in out.sessions:
        if s.type == SessionType.STRENGTH:
            assert s.day_offset != (long_day - 1) % 7


def test_quality_is_dropped_before_the_long_run_in_a_brutal_week(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    r = rota(["night", "night", "night", "night", "night", "night", "off"])
    out, adj = reschedule_week(week, r)
    assert any(s.type == SessionType.LONG for s in out.sessions)
    dropped = [a for a in adj if "dropped" in a.change]
    assert dropped, "sessions that cannot fit must be reported as dropped"


def test_every_reschedule_reports_a_reason(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    out, adj = reschedule_week(week, rota(["night", "night", "off", "off", "off", "off", "off"]))
    for a in adj:
        assert a.reason, f"{a.target} moved without a reason"


def test_rest_days_explain_themselves_on_shift_days(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    out, adj = reschedule_week(week, rota(["night", "off", "off", "off", "off", "off", "off"]))
    monday = next(s for s in out.sessions if s.day_offset == 0)
    assert monday.type == SessionType.REST
    assert "night" in monday.intent.lower()


def test_reschedule_still_covers_seven_days(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    out, adj = reschedule_week(week, rota(["night", "post_night", "day", "off", "night",
                                           "post_night", "off"]))
    assert set(range(7)).issubset({s.day_offset for s in out.sessions})


def test_reschedule_does_not_duplicate_a_day_with_two_runs(profile):
    week = generate_week(profile, Phase.BASE_2, 2)
    out, adj = reschedule_week(week, rota(["off"] * 7))
    run_days = [s.day_offset for s in out.sessions
                if s.type not in (SessionType.REST, SessionType.STRENGTH) and not s.optional]
    assert len(run_days) == len(set(run_days)), "two runs stacked on one day"


# ---- next-week replanning ---------------------------------------------------------------------

def test_good_week_advances_within_the_ramp_cap():
    d = replan_week(planned_volume=33.0, achieved_volume=30.0,
                    sessions_planned=3, sessions_completed=3)
    assert d.action == "advance"
    assert d.next_volume <= 30.0 * (1 + MAX_WEEKLY_RAMP) + 1e-6


def test_advance_is_capped_off_achieved_not_planned():
    """If the plan said 40 but you ran 20, next week comes off 20."""
    d = replan_week(planned_volume=40.0, achieved_volume=20.0,
                    sessions_planned=3, sessions_completed=3)
    assert d.next_volume <= 20.0 * (1 + MAX_WEEKLY_RAMP) + 1e-6


def test_pain_holds_volume():
    d = replan_week(30.0, 30.0, 3, 3, max_pain=4)
    assert d.action == "hold"
    assert d.next_volume == pytest.approx(30.0)
    assert any("pain" in r.lower() for r in d.reasons)


def test_pain_beats_a_perfect_week():
    d = replan_week(30.0, 30.0, 3, 3, max_pain=3, readiness_bands=["normal"] * 7)
    assert d.action == "hold"


def test_acwr_above_the_hard_cap_cuts():
    spike = acwr([20.0] * 28 + [200.0] * 7)
    assert spike.ratio > ACWR_HARD_CAP
    d = replan_week(50.0, 50.0, 3, 3, acwr_result=spike)
    assert d.action == "cut"
    assert d.next_volume < 50.0
    assert d.warnings and "risk score" in d.warnings[0].lower()


def test_insufficient_acwr_history_does_not_cut():
    """A beginner's exploding ratio must not veto their first weeks of training."""
    early = acwr([0.0] * 6 + [40.0])
    assert early.band == "insufficient_history"
    d = replan_week(20.0, 20.0, 3, 3, acwr_result=early)
    assert d.action != "cut"


def test_two_bad_readiness_days_hold_volume():
    d = replan_week(30.0, 30.0, 3, 3,
                    readiness_bands=["normal", "suppressed", "strained", "normal"])
    assert d.action == "hold"
    assert any("sleep" in w.lower() for w in d.warnings)


def test_one_bad_readiness_day_does_not_hold():
    d = replan_week(30.0, 30.0, 3, 3, readiness_bands=["normal", "suppressed", "normal"])
    assert d.action == "advance"


def test_disrupted_week_rebuilds_from_achieved():
    d = replan_week(planned_volume=40.0, achieved_volume=12.0,
                    sessions_planned=3, sessions_completed=1)
    assert d.action == "rebuild"
    assert d.next_volume == pytest.approx(12.0 * 1.05, rel=0.01)
    assert d.next_volume < 40.0


def test_missed_volume_is_never_carried_forward():
    """The central rule, stated three ways so a refactor cannot quietly break it."""
    for planned, achieved, done in ((40.0, 10.0, 1), (40.0, 20.0, 2), (60.0, 0.0, 0)):
        d = replan_week(planned, achieved, 3, done)
        assert d.carry_forward == "none"
        assert d.next_volume <= max(planned, achieved * (1 + MAX_WEEKLY_RAMP)) + 1e-6
        assert d.next_volume < planned + (planned - achieved), \
            "the deficit must not be added to next week"


def test_rebuild_message_says_nothing_is_owed():
    d = replan_week(40.0, 10.0, 3, 1)
    assert any("owed" in r.lower() or "gone" in r.lower() for r in d.reasons)


def test_cutback_is_scheduled_every_fourth_week():
    d = replan_week(40.0, 40.0, 3, 3, weeks_since_cutback=3)
    assert d.action == "cutback"
    assert d.next_volume == pytest.approx(40.0 * CUTBACK_FACTOR)


def test_precedence_pain_beats_cutback():
    d = replan_week(40.0, 40.0, 3, 3, weeks_since_cutback=3, max_pain=5)
    assert d.action == "hold"


def test_precedence_acwr_beats_readiness():
    spike = acwr([20.0] * 28 + [200.0] * 7)
    d = replan_week(50.0, 50.0, 3, 3, acwr_result=spike,
                    readiness_bands=["suppressed", "strained"])
    assert d.action == "cut"


def test_zero_achieved_volume_does_not_crash():
    d = replan_week(30.0, 0.0, 3, 0)
    assert d.action == "rebuild"
    assert d.next_volume is not None


def test_no_planned_sessions_does_not_divide_by_zero():
    d = replan_week(None, 0.0, 0, 0)
    assert d.completed_fraction == 0.0


def test_decision_is_serialisable():
    import json
    json.dumps(replan_week(30.0, 30.0, 3, 3).to_dict())


# ---- integration -----------------------------------------------------------------------------

def test_full_week_pipeline(profile):
    """Generate -> reschedule for a rota -> downgrade a day for readiness. Must stay coherent."""
    week = generate_week(profile, Phase.BASE_2, 3)
    r = rota(["day", "night", "post_night", "day", "off", "off", "off"])
    out, moves = reschedule_week(week, r)
    assert set(range(7)).issubset({s.day_offset for s in out.sessions})

    nights = [NightSummary(day=MONDAY + timedelta(days=i), hrv_ms=60.0, resting_hr=55.0,
                           total_sleep_min=450, wake_events=1, sleep_efficiency=0.92,
                           clean_interval_count=5000) for i in range(30)]
    for n in nights[-7:]:
        n.hrv_ms = 42.0                      # suppressed
    readiness = daily_readiness(nights)
    assert readiness.band in ("suppressed", "strained")

    changed = []
    for s in out.sessions:
        new, adj = apply_readiness(s, readiness, paces_easy_sec_km=profile.paces.easy)
        changed.append(new)
    assert not any(s.type in QUALITY_TYPES for s in changed), \
        "suppressed readiness must remove all quality work from the day"
