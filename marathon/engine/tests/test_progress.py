"""Progress-layer tests: pain escalation, training status, and the anti-streak.

The pain tests are the important ones. Focal bone pain and next-morning pain must escalate even when
the reported *level* is mild, because those two features -- not the number -- are what distinguish a
stress injury from an ache.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from marathon_engine.progress import (
    ADHERENCE_CLIFF_WEEKS, PAIN_ESCALATION_DAYS, PainEntry, RouteEffort, compare_route_efforts,
    consistency, pain_trend, progress_narrative, training_status,
)

D = date(2026, 8, 1)


# ---- pain ----------------------------------------------------------------------------------

def test_no_entries_returns_nothing():
    assert pain_trend([]) == []


def test_single_mild_ache_is_only_watched():
    t = pain_trend([PainEntry(D, "left_calf", 2, timing="after_run")])
    assert len(t) == 1
    assert t[0].verdict == "watch"
    assert "logging" in t[0].actions[0].lower()


def test_focal_pain_escalates_to_urgent_even_when_mild():
    """The key test. A 2/10 focal bone pain is more serious than a 5/10 diffuse ache."""
    t = pain_trend([PainEntry(D, "right_shin", 2, focal=True)])
    assert t[0].verdict == "urgent"
    assert "stress injury" in t[0].message.lower()
    assert any("stop running" in a.lower() for a in t[0].actions)


def test_focal_message_warns_against_testing_it():
    t = pain_trend([PainEntry(D, "right_shin", 2, focal=True)])
    assert any("test it" in a.lower() for a in t[0].actions)


def test_high_level_pain_stops_and_assesses():
    t = pain_trend([PainEntry(D, "left_knee", 7)])
    assert t[0].verdict == "stop_and_assess"
    assert "5/10" in t[0].message


def test_next_morning_pain_holds_volume_even_at_low_level():
    """Next-day pain is the most informative overuse signal and the most often dismissed."""
    t = pain_trend([PainEntry(D, "left_achilles", 2, timing="next_morning")])
    assert t[0].verdict == "hold_volume"
    assert "morning after" in t[0].message.lower()


def test_pain_that_worsens_during_the_run_holds_volume():
    t = pain_trend([PainEntry(D, "left_itb", 3, worsens_during_run=True)])
    assert t[0].verdict == "hold_volume"
    assert "worsens" in t[0].message.lower()


def test_repeated_reports_become_a_pattern():
    es = [PainEntry(D + timedelta(days=i * 3), "left_calf", 2) for i in range(PAIN_ESCALATION_DAYS)]
    t = pain_trend(es, as_of=D + timedelta(days=9))
    assert t[0].verdict == "hold_volume"
    assert "pattern" in t[0].message.lower()


def test_escalating_levels_are_detected():
    es = [PainEntry(D, "left_calf", 1), PainEntry(D + timedelta(days=2), "left_calf", 2),
          PainEntry(D + timedelta(days=4), "left_calf", 4)]
    t = pain_trend(es, as_of=D + timedelta(days=4))
    assert t[0].escalating
    assert t[0].verdict == "hold_volume"


def test_old_entries_fall_out_of_the_window():
    es = [PainEntry(D - timedelta(days=60), "left_calf", 8), PainEntry(D, "left_calf", 1)]
    t = pain_trend(es, as_of=D)
    assert t[0].max_level == 1, "an old severe entry must not keep flagging"


def test_sites_are_reported_separately():
    es = [PainEntry(D, "left_calf", 2), PainEntry(D, "right_knee", 7)]
    t = pain_trend(es, as_of=D)
    assert {x.site for x in t} == {"left_calf", "right_knee"}


def test_most_serious_site_is_reported_first():
    es = [PainEntry(D, "left_calf", 1), PainEntry(D, "right_shin", 2, focal=True)]
    t = pain_trend(es, as_of=D)
    assert t[0].site == "right_shin"
    assert t[0].verdict == "urgent"


def test_hold_volume_actions_include_dropping_quality():
    t = pain_trend([PainEntry(D, "left_achilles", 3, timing="next_morning")])
    assert any("quality" in a.lower() for a in t[0].actions)


def test_trend_is_serialisable():
    import json
    json.dumps([x.to_dict() for x in pain_trend([PainEntry(D, "left_calf", 2)])])


# ---- training status ------------------------------------------------------------------------

def test_insufficient_history_says_so():
    s = training_status(50, 0, None, None, weeks_training=1)
    assert "baseline" in s.label.lower()


def test_rising_load_and_improving_fitness_is_productive():
    s = training_status(acute_load=120, chronic_load=100, ef_recent=1.05, ef_baseline=1.0,
                        weeks_training=10)
    assert s.label == "Productive"
    assert s.load_trend == "rising" and s.fitness_trend == "improving"


def test_rising_load_with_declining_fitness_is_overreaching():
    """The one combination where the honest advice is to do less."""
    s = training_status(acute_load=140, chronic_load=100, ef_recent=0.95, ef_baseline=1.0,
                        weeks_training=10)
    assert s.label == "Overreaching"
    assert "will not fix it" in s.detail.lower()


def test_rising_load_flat_fitness_is_normal_and_says_so():
    s = training_status(acute_load=120, chronic_load=100, ef_recent=1.0, ef_baseline=1.0,
                        weeks_training=10)
    assert s.label == "Building"
    assert "lags" in s.detail.lower()


def test_falling_load_improving_fitness_is_peaking():
    s = training_status(acute_load=60, chronic_load=100, ef_recent=1.05, ef_baseline=1.0,
                        weeks_training=20)
    assert s.label == "Peaking"


def test_falling_both_is_detraining_and_reassures_about_fitness():
    s = training_status(acute_load=40, chronic_load=100, ef_recent=0.9, ef_baseline=1.0,
                        weeks_training=20)
    assert s.label == "Detraining"
    assert "comes back quickly" in s.detail.lower()


def test_steady_declining_looks_outside_training_first():
    s = training_status(acute_load=100, chronic_load=100, ef_recent=0.95, ef_baseline=1.0,
                        weeks_training=20)
    assert s.label == "Unproductive"
    assert "ferritin" in s.detail.lower()


def test_missing_ef_data_is_treated_as_flat():
    s = training_status(120, 100, None, None, weeks_training=10)
    assert s.fitness_trend == "flat"


def test_status_is_serialisable():
    import json
    json.dumps(training_status(120, 100, 1.05, 1.0, weeks_training=10).to_dict())


# ---- consistency (the anti-streak) -----------------------------------------------------------

def test_no_weeks_scored():
    c = consistency([], [])
    assert c.weeks_scored == 0


def test_good_adherence_is_on_path():
    c = consistency([3, 3, 3, 3], [3, 3, 3, 2])
    assert c.band == "on_path"
    assert c.adherence > 0.9


def test_adherence_message_says_it_predicts_the_start_line():
    c = consistency([3] * 4, [3] * 4)
    assert "start line" in c.detail.lower()


def test_middling_adherence_blames_the_plan_not_the_person():
    c = consistency([3, 3, 3, 3], [2, 2, 2, 2])
    assert c.band == "slipping"
    assert "rota" in c.detail.lower() or "discipline" in c.detail.lower()


def test_poor_adherence_suggests_changing_the_plan():
    c = consistency([3, 3, 3, 3], [1, 1, 1, 0])
    assert c.band == "off_path"
    assert "two runs" in c.detail.lower()


def test_extra_sessions_on_rest_days_are_flagged_not_rewarded():
    """The anti-streak requirement: doing more is not automatically better."""
    c = consistency([3] * 4, [3] * 4, planned_rest_days=[4] * 4, extra_sessions=[2, 2, 2, 2])
    assert c.band == "overreaching"
    assert c.rest_compliance < 1.0
    assert "part of it" in c.detail.lower()


def test_perfect_compliance_including_rest_is_on_path():
    c = consistency([3] * 4, [3] * 4, planned_rest_days=[4] * 4, extra_sessions=[0] * 4)
    assert c.band == "on_path"
    assert c.rest_compliance == 1.0


def test_consistency_is_serialisable():
    import json
    json.dumps(consistency([3] * 4, [3] * 4).to_dict())


# ---- route self-comparison -------------------------------------------------------------------

def test_needs_two_efforts():
    assert compare_route_efforts([RouteEffort(D, "loop", 5.0, 1800)]) is None


def test_same_pace_lower_hr_is_called_the_improvement_that_matters():
    efforts = [
        RouteEffort(D, "loop", 5.0, 1800, mean_hr=160),
        RouteEffort(D + timedelta(days=60), "loop", 5.0, 1800, mean_hr=148),
    ]
    r = compare_route_efforts(efforts)
    assert r is not None
    assert any("matters" in n.lower() for n in r["notes"])


def test_faster_but_much_higher_hr_is_not_called_progress():
    efforts = [
        RouteEffort(D, "loop", 5.0, 1800, mean_hr=150),
        RouteEffort(D + timedelta(days=60), "loop", 5.0, 1700, mean_hr=162),
    ]
    r = compare_route_efforts(efforts)
    assert any("not read it as progress" in n.lower() for n in r["notes"])


def test_faster_at_same_hr_is_unambiguous():
    efforts = [
        RouteEffort(D, "loop", 5.0, 1800, mean_hr=155),
        RouteEffort(D + timedelta(days=60), "loop", 5.0, 1700, mean_hr=155),
    ]
    r = compare_route_efforts(efforts)
    assert any("unambiguous" in n.lower() for n in r["notes"])


def test_big_temperature_difference_is_flagged():
    efforts = [
        RouteEffort(D, "loop", 5.0, 1800, mean_hr=150, temp_c=8),
        RouteEffort(D + timedelta(days=60), "loop", 5.0, 1800, mean_hr=158, temp_c=26),
    ]
    r = compare_route_efforts(efforts)
    assert any("conditions differ" in n.lower() for n in r["notes"])


def test_picks_the_most_repeated_route():
    efforts = [
        RouteEffort(D, "a", 5.0, 1800), RouteEffort(D + timedelta(days=1), "b", 5.0, 1800),
        RouteEffort(D + timedelta(days=2), "b", 5.0, 1790),
        RouteEffort(D + timedelta(days=3), "b", 5.0, 1780),
    ]
    r = compare_route_efforts(efforts)
    assert r["route_id"] == "b"
    assert r["efforts"] == 3


# ---- narrative -------------------------------------------------------------------------------

def test_narrative_surfaces_invisible_progress():
    n = progress_narrative(10, hr_at_fixed_pace_delta=-8, ef_change_pct=6,
                           longest_run_km=12.0, first_longest_run_km=3.0)
    text = " ".join(n["highlights"]).lower()
    assert "heart rate" in text and "cannot feel" in text
    assert "12" in " ".join(n["highlights"])


def test_adherence_cliff_warning_fires_in_the_danger_window():
    n = progress_narrative(ADHERENCE_CLIFF_WEEKS)
    assert n["adherence_cliff_warning"]
    assert "stop" in n["adherence_cliff_warning"].lower()
    assert "nothing is wrong" in n["adherence_cliff_warning"].lower()


def test_no_cliff_warning_early_on():
    assert progress_narrative(3)["adherence_cliff_warning"] is None


def test_cliff_warning_suggests_a_concrete_target():
    n = progress_narrative(ADHERENCE_CLIFF_WEEKS + 1)
    assert "5k" in n["adherence_cliff_warning"].lower()


def test_narrative_handles_no_data():
    n = progress_narrative(2)
    assert n["highlights"]
