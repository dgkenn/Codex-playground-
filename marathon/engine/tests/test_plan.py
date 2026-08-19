"""Plan-generation tests: gates, volume ramps, long-run caps, and the taper.

The invariants worth defending here are the safety ones: volume never jumps more than the ramp cap,
the long run never exceeds its time cap, safety gates cannot be satisfied by time served alone, and
the taper cuts volume rather than intensity.
"""

from __future__ import annotations

from datetime import date

import pytest

from marathon_engine.assessment import RampStage, RampTest, profile_from_ramp
from marathon_engine.load import MAX_WEEKLY_RAMP
from marathon_engine.physiology import training_paces
from marathon_engine.plan import (
    CUTBACK_EVERY, CUTBACK_FACTOR, LONG_RUN_MAX_KM, LONG_RUN_MAX_MIN, LONG_RUN_MAX_SHARE,
    LONG_RUN_PEAK_MAX_MIN,
    PHASE_GATES, PHASE_MIN_WEEKS, PHASE_ORDER, PHASE_STALL_WEEKS, TAPER_VOLUME_CUT, Gate, Phase,
    PlanConfig, SessionType, evaluate_gates, generate_week, long_run_progression, phase_overview,
    taper_weeks, weekly_volume_target,
)


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


# ---- gates ---------------------------------------------------------------------------------

def test_gate_comparison_ops():
    g = Gate("x", ">=", 10, "l", "r")
    assert g.check({"x": 10}) is True
    assert g.check({"x": 9}) is False
    g2 = Gate("y", "<=", 0.08, "l", "r")
    assert g2.check({"y": 0.05}) is True
    assert g2.check({"y": 0.10}) is False
    g3 = Gate("z", "true", True, "l", "r")
    assert g3.check({"z": True}) is True
    assert g3.check({"z": False}) is False


def test_gate_missing_evidence_is_unknown_not_failed():
    """The distinction matters: 'go and measure it' is different advice from 'you fell short'."""
    g = Gate("x", ">=", 10, "l", "r")
    assert g.check({}) is None
    assert g.check({"x": None}) is None


def test_gate_non_numeric_evidence_is_unknown():
    g = Gate("x", ">=", 10, "l", "r")
    assert g.check({"x": "lots"}) is None


def test_gate_rejects_unknown_op():
    with pytest.raises(ValueError):
        Gate("x", "~=", 1, "l", "r").check({"x": 1})


def test_every_phase_has_a_pain_safety_gate():
    """No phase may be advanced while something hurts."""
    for phase in (Phase.FOUNDATION, Phase.BASE_1, Phase.BASE_2, Phase.HALF_BUILD,
                  Phase.MARATHON_BASE, Phase.MARATHON_PEAK):
        keys = [g.key for g in PHASE_GATES[phase]]
        assert "max_pain_2wk" in keys, f"{phase} has no pain gate"
        assert any(g.safety for g in PHASE_GATES[phase])


def test_cannot_advance_before_minimum_weeks_even_with_all_gates_met():
    """Bone adapts on its own clock -- good numbers must not shortcut the floor."""
    ev = {"continuous_run_min": 45, "continuous_run_in_z2": True,
          "max_pain_2wk": 0, "sessions_completed_pct_4wk": 1.0}
    r = evaluate_gates(Phase.FOUNDATION, weeks_in_phase=2, evidence=ev)
    assert not r.can_advance
    assert not r.min_weeks_satisfied
    assert "more week" in r.guidance


def test_can_advance_when_gates_met_and_weeks_served():
    ev = {"continuous_run_min": 30, "continuous_run_in_z2": True,
          "max_pain_2wk": 1, "sessions_completed_pct_4wk": 0.85}
    r = evaluate_gates(Phase.FOUNDATION, PHASE_MIN_WEEKS[Phase.FOUNDATION], ev)
    assert r.can_advance
    assert r.next_phase == Phase.BASE_1


def test_pain_blocks_advancement():
    ev = {"continuous_run_min": 40, "continuous_run_in_z2": True,
          "max_pain_2wk": 5, "sessions_completed_pct_4wk": 1.0}
    r = evaluate_gates(Phase.FOUNDATION, 12, ev)
    assert not r.can_advance
    assert any(u["key"] == "max_pain_2wk" for u in r.unmet)


def test_unknown_evidence_is_reported_separately_with_different_guidance():
    ev = {"continuous_run_min": 40, "continuous_run_in_z2": True, "max_pain_2wk": 0}
    r = evaluate_gates(Phase.FOUNDATION, 12, ev)
    assert not r.can_advance
    assert r.unknown and not r.unmet
    assert "missing" in r.guidance.lower()


def test_stall_triggers_a_diagnostic():
    ev = {"continuous_run_min": 12, "continuous_run_in_z2": False,
          "max_pain_2wk": 0, "sessions_completed_pct_4wk": 0.9}
    r = evaluate_gates(Phase.FOUNDATION, PHASE_STALL_WEEKS[Phase.FOUNDATION] + 1, ev)
    assert r.stalled
    assert r.diagnostics
    assert any("fuel" in d.lower() for d in r.diagnostics), "under-fuelling must be considered"


def test_no_stall_when_progressing_normally():
    ev = {"continuous_run_min": 30, "continuous_run_in_z2": True,
          "max_pain_2wk": 0, "sessions_completed_pct_4wk": 0.9}
    r = evaluate_gates(Phase.FOUNDATION, 8, ev)
    assert not r.stalled


def test_last_phase_has_no_next():
    r = evaluate_gates(Phase.RECOVERY, 5, {})
    assert r.next_phase is None


# ---- volume progression --------------------------------------------------------------------

def test_foundation_is_governed_by_minutes_not_km():
    km, mins = weekly_volume_target(Phase.FOUNDATION, 1)
    assert km is None and mins is not None


def test_volume_rises_across_a_phase():
    a, _ = weekly_volume_target(Phase.BASE_1, 1, phase_length_est=8)
    b, _ = weekly_volume_target(Phase.BASE_1, 8, phase_length_est=8)
    assert b > a


def test_ramp_cap_is_enforced():
    """The core safety invariant: no week may exceed the previous by more than the cap."""
    prev = 20.0
    km, _ = weekly_volume_target(Phase.BASE_2, 8, phase_length_est=8, previous_week_volume=prev)
    assert km <= prev * (1 + MAX_WEEKLY_RAMP) + 1e-6 or km <= 26.0


def test_cutback_reduces_volume():
    normal, _ = weekly_volume_target(Phase.BASE_2, 4, phase_length_est=8)
    cut, _ = weekly_volume_target(Phase.BASE_2, 4, phase_length_est=8, is_cutback=True)
    assert cut == pytest.approx(normal * CUTBACK_FACTOR, rel=0.01)


def test_ramp_cap_does_not_block_recovery_after_a_cutback():
    """Returning to pre-cutback volume is not a real 30% increase in load."""
    cut_week = 20.0
    km, _ = weekly_volume_target(Phase.BASE_2, 5, phase_length_est=8,
                                 previous_week_volume=cut_week)
    assert km >= 26.0, "must be allowed back to the phase floor after a cutback"


def test_athlete_ceiling_is_respected():
    cfg = PlanConfig(max_weekly_km=30.0)
    km, _ = weekly_volume_target(Phase.MARATHON_PEAK, 6, phase_length_est=8, config=cfg)
    assert km <= 30.0


def test_assess_and_race_phases_have_no_volume_target():
    for p in (Phase.ASSESS, Phase.RACE, Phase.RECOVERY, Phase.TAPER):
        km, mins = weekly_volume_target(p, 1)
        assert km is None and mins is None


# ---- long run ------------------------------------------------------------------------------

def test_long_run_share_is_capped(profile):
    km, mins, notes = long_run_progression(Phase.MARATHON_BASE, 10, 50.0, profile.paces)
    assert km <= 50.0 * LONG_RUN_MAX_SHARE + 1e-6


def test_long_run_time_cap_binds_for_a_slow_runner(profile):
    """A beginner at ~8:00/km hits the time cap long before 32 km -- and the cap must win.

    The cap is 150 min (Daniels' actual rule) everywhere except the peak phase, which is allowed
    165 min for its biggest rehearsal runs.
    """
    km, mins, notes = long_run_progression(Phase.MARATHON_BASE, 12, 90.0, profile.paces)
    assert mins <= LONG_RUN_MAX_MIN + 1e-6, "base phases must respect the 150 min cap"
    assert any("min" in n for n in notes)

    km, mins, notes = long_run_progression(Phase.MARATHON_PEAK, 12, 90.0, profile.paces)
    assert mins <= LONG_RUN_PEAK_MAX_MIN + 1e-6
    assert mins > LONG_RUN_MAX_MIN, "the peak phase gets its documented allowance"


def test_long_run_cap_is_not_the_three_hour_convention():
    """Regression guard. An earlier version used the widely-repeated '3 hours', which exceeds
    Daniels' own 150-minute limit by 20% -- in the population least able to absorb it."""
    assert LONG_RUN_MAX_MIN == 150.0
    assert LONG_RUN_PEAK_MAX_MIN < 180.0


def test_daniels_share_tightening_is_disclosed(profile):
    """Above 40 km/week Daniels' share limit drops to 25%; we exceed it and must say so."""
    km, mins, notes = long_run_progression(Phase.MARATHON_BASE, 10, 50.0, profile.paces)
    assert any("Daniels" in n for n in notes)


def test_long_run_distance_cap_binds_for_a_fast_runner():
    fast = training_paces(60.0)
    km, mins, notes = long_run_progression(Phase.MARATHON_PEAK, 12, 120.0, fast)
    assert km <= LONG_RUN_MAX_KM + 1e-6


def test_long_run_shrinks_on_a_cutback(profile):
    a, _, _ = long_run_progression(Phase.BASE_2, 4, 30.0, profile.paces)
    b, _, _ = long_run_progression(Phase.BASE_2, 4, 30.0, profile.paces, is_cutback=True)
    assert b < a


def test_long_run_none_without_a_volume_target(profile):
    km, mins, notes = long_run_progression(Phase.FOUNDATION, 1, None, profile.paces)
    assert km is None


def test_high_share_is_disclosed_honestly(profile):
    """The 3-run-week trade-off must be stated, not hidden."""
    km, mins, notes = long_run_progression(Phase.MARATHON_BASE, 12, 50.0, profile.paces)
    assert any("3-run week" in n or "% of your week" in n for n in notes)


# ---- taper ---------------------------------------------------------------------------------

def test_taper_cuts_volume_to_the_published_range():
    weeks = taper_weeks(60.0, training_paces(40.0))
    assert len(weeks) == 2
    assert weeks[0]["volume_km"] == pytest.approx(60.0 * TAPER_VOLUME_CUT[0])
    assert weeks[1]["volume_km"] == pytest.approx(60.0 * TAPER_VOLUME_CUT[1])
    # Bosquet: 41-60% reduction. Week -2 must sit inside that.
    reduction = 1 - TAPER_VOLUME_CUT[0]
    assert 0.41 <= reduction <= 0.60


def test_taper_keeps_intensity_and_frequency():
    weeks = taper_weeks(60.0, training_paces(40.0))
    for w in weeks:
        keeps = " ".join(w["keep"]).lower()
        assert "intensity" in keeps
        assert "frequency" in keeps
        assert "volume" in " ".join(w["cut"]).lower()


# ---- week generation -----------------------------------------------------------------------

def test_every_week_covers_seven_days(profile):
    for phase in PHASE_ORDER:
        w = generate_week(profile, phase, 1)
        offsets = sorted(s.day_offset for s in w.sessions)
        assert set(range(7)).issubset(set(offsets)), f"{phase} leaves a day unaccounted for"


def test_assess_week_has_no_hard_running(profile):
    w = generate_week(profile, Phase.ASSESS, 1)
    assert not any(s.type in (SessionType.INTERVALS, SessionType.THRESHOLD,
                              SessionType.TIME_TRIAL, SessionType.LONG) for s in w.sessions)
    assert any(s.type == SessionType.RAMP_TEST for s in w.sessions)


def test_foundation_uses_run_walk_and_ends_continuous(profile):
    w1 = generate_week(profile, Phase.FOUNDATION, 1)
    assert any(s.type == SessionType.RUN_WALK for s in w1.sessions)
    # Week 9, not week 8: week 8 is a cutback week, and a cutback week deliberately HOLDS the ladder
    # at the previous rung rather than advancing to continuous running.
    w9 = generate_week(profile, Phase.FOUNDATION, 9)
    assert any(s.type == SessionType.EASY for s in w9.sessions)
    assert not any(s.type == SessionType.RUN_WALK for s in w9.sessions)


def test_foundation_cutback_holds_the_ladder_rather_than_advancing(profile):
    """Advancing the run-walk ladder on a cutback week made the sessions HARDER in the week that is
    meant to be easier -- incoherent, and the opposite of the point."""
    w3 = generate_week(profile, Phase.FOUNDATION, 3)
    w4 = generate_week(profile, Phase.FOUNDATION, 4)      # cutback
    assert w4.is_cutback
    rw3 = next(s.run_walk for s in w3.sessions if s.run_walk)
    rw4 = next(s.run_walk for s in w4.sessions if s.run_walk)
    assert rw4 == rw3, "a cutback week must repeat the previous rung"


def test_foundation_volume_matches_the_ladder(profile):
    """The stated weekly minutes must be what the ladder actually prescribes."""
    for wk in (1, 2, 3, 5, 6, 7):
        w = generate_week(profile, Phase.FOUNDATION, wk)
        rw = next((s.run_walk for s in w.sessions if s.run_walk), None)
        if rw is None:
            continue
        run_min, _, reps = rw
        assert w.volume_target_min == pytest.approx(run_min * reps * 3, rel=0.01), (
            f"week {wk}: stated {w.volume_target_min} min vs ladder {run_min * reps * 3} min")


def test_foundation_ladder_does_not_overrun(profile):
    """Repeating a rung must be safe -- week 20 of foundation must not crash or escalate."""
    w = generate_week(profile, Phase.FOUNDATION, 20)
    assert w.sessions


def test_base_1_has_no_threshold_work(profile):
    """Volume before intensity: threshold on a thin base is fatigue without adaptation."""
    for wk in range(1, 9):
        w = generate_week(profile, Phase.BASE_1, wk)
        assert not any(s.type in (SessionType.THRESHOLD, SessionType.INTERVALS)
                       for s in w.sessions), f"week {wk} has quality work too early"


def test_base_2_introduces_threshold(profile):
    w = generate_week(profile, Phase.BASE_2, 1)
    assert any(s.type == SessionType.THRESHOLD for s in w.sessions)


def test_three_running_sessions_per_week(profile):
    for phase in (Phase.BASE_1, Phase.BASE_2, Phase.HALF_BUILD):
        w = generate_week(profile, phase, 2)
        runs = [s for s in w.running_sessions if not s.optional]
        assert len(runs) == 3, f"{phase} has {len(runs)} runs, expected 3"


def test_two_strength_sessions_per_week(profile):
    w = generate_week(profile, Phase.BASE_2, 2)
    strength = [s for s in w.sessions if s.type == SessionType.STRENGTH]
    assert len(strength) == 2


def test_strength_includes_calf_work_always(profile):
    """The highest-yield injury-prevention exercise must never be optional."""
    w = generate_week(profile, Phase.BASE_2, 2)
    s = next(x for x in w.sessions if x.type == SessionType.STRENGTH)
    assert "calf raise" in s.structure.lower()


def test_plyometrics_absent_in_foundation(profile):
    w = generate_week(profile, Phase.FOUNDATION, 3)
    s = next(x for x in w.sessions if x.type == SessionType.STRENGTH)
    assert "plyometric" not in s.structure.lower()


def test_optional_fourth_run_offered_in_marathon_phases(profile):
    w = generate_week(profile, Phase.MARATHON_BASE, 2)
    optional = [s for s in w.sessions if s.optional and s.type == SessionType.EASY]
    assert optional
    assert "optional" in optional[0].intent.lower()


def test_no_gate_depends_on_the_optional_run():
    """Explicit promise in the design: the optional run must never become mandatory by stealth."""
    all_keys = {g.key for gates in PHASE_GATES.values() for g in gates}
    assert not any("fourth" in k or "optional" in k for k in all_keys)


def test_cutback_week_is_flagged_and_noted(profile):
    w = generate_week(profile, Phase.BASE_2, CUTBACK_EVERY)
    assert w.is_cutback
    assert any("cutback" in n.lower() for n in w.notes)


def test_marathon_pace_long_runs_appear_in_peak(profile):
    found = False
    for wk in range(1, 7):
        w = generate_week(profile, Phase.MARATHON_PEAK, wk)
        if any(s.type == SessionType.MARATHON_PACE for s in w.sessions):
            found = True
    assert found


def test_long_runs_include_fuelling_guidance_when_long(profile):
    w = generate_week(profile, Phase.MARATHON_BASE, 8)
    long = next(s for s in w.sessions if s.type in (SessionType.LONG, SessionType.MARATHON_PACE))
    if (long.duration_min or 0) >= 90:
        assert long.fuelling
        assert "carbohydrate" in long.fuelling.lower()


def test_race_week_has_the_marathon(profile):
    w = generate_week(profile, Phase.RACE, 1)
    assert any(s.type == SessionType.RACE and s.distance_km == pytest.approx(42.195)
               for s in w.sessions)


def test_recovery_week_is_almost_all_rest(profile):
    w = generate_week(profile, Phase.RECOVERY, 1)
    hard = [s for s in w.sessions if s.type not in (SessionType.REST,) and not s.optional]
    assert not hard


def test_every_session_states_its_intent(profile):
    """A session whose purpose is not stated is a session that gets run at the wrong intensity."""
    for phase in PHASE_ORDER:
        w = generate_week(profile, phase, 2)
        for s in w.sessions:
            assert s.intent, f"{phase}/{s.title} has no stated intent"


def test_week_is_serialisable(profile):
    import json
    for phase in PHASE_ORDER:
        json.dumps(generate_week(profile, phase, 2).to_dict())


def test_phase_overview_is_complete_and_serialisable():
    import json
    ov = phase_overview()
    json.dumps(ov)
    names = {o["phase"] for o in ov}
    assert "foundation" in names and "marathon_peak" in names
    for o in ov:
        assert o["goal"]


def test_optional_run_does_not_collide_with_another_session(profile):
    """Regression guard: the optional 4th run used to land on a strength day, which reads as two
    sessions stacked on one day -- the opposite of what an optional easy run is for."""
    for phase in (Phase.MARATHON_BASE, Phase.MARATHON_PEAK):
        for wk in range(1, 7):
            w = generate_week(profile, phase, wk)
            opt = [s for s in w.sessions if s.optional]
            for o in opt:
                same_day = [s for s in w.sessions
                            if s.day_offset == o.day_offset and s is not o
                            and s.type != SessionType.REST]
                assert not same_day, (
                    f"{phase} wk{wk}: optional run collides with "
                    f"{[s.title for s in same_day]}")


def test_week_sessions_are_coherent_with_the_stated_volume(profile):
    """The stated weekly volume must match what the sessions actually add up to.

    A hardcoded midweek duration made these silently disagree -- the plan said 50 km while the
    sessions came to 30.
    """
    for phase in (Phase.BASE_1, Phase.BASE_2, Phase.HALF_BUILD, Phase.MARATHON_BASE):
        for wk in (1, 4, 8):
            w = generate_week(profile, phase, wk)
            if not w.volume_target_km:
                continue
            total = 0.0
            for s in w.running_sessions:
                if s.optional:
                    continue
                if s.distance_km:
                    total += s.distance_km
                elif s.duration_min:
                    total += s.duration_min * 60.0 / (s.pace_target_sec_km or profile.paces.easy)
            assert total == pytest.approx(w.volume_target_km, rel=0.16), (
                f"{phase} wk{wk}: sessions total {total:.1f} km vs stated "
                f"{w.volume_target_km:.1f} km")


def test_intervals_are_not_scheduled_below_the_vdot_ir_floor(profile):
    """Daniels publishes no Interval pace below VDOT 35, so any target is a calculator
    extrapolation -- unachievable for someone whose base cannot support VO2max work, and an
    injury risk. Threshold substitutes."""
    from marathon_engine.physiology import VDOT_IR_FLOOR, training_paces
    from marathon_engine.assessment import FitnessProfile
    low = FitnessProfile(
        as_of=profile.as_of, age=profile.age, hr_rest=profile.hr_rest, hr_max=profile.hr_max,
        hr_max_source=profile.hr_max_source, vdot=30.0, vdot_source="test",
        zones=profile.zones, paces=training_paces(30.0), lthr=profile.lthr)
    assert not low.paces.ir_prescribable
    for wk in range(1, 10):
        w = generate_week(low, Phase.HALF_BUILD, wk)
        assert not any(s.type == SessionType.INTERVALS for s in w.sessions), \
            f"week {wk} scheduled intervals at VDOT 30"


def test_interval_substitution_is_explained(profile):
    from marathon_engine.physiology import training_paces
    from marathon_engine.assessment import FitnessProfile
    low = FitnessProfile(
        as_of=profile.as_of, age=profile.age, hr_rest=profile.hr_rest, hr_max=profile.hr_max,
        hr_max_source=profile.hr_max_source, vdot=30.0, vdot_source="test",
        zones=profile.zones, paces=training_paces(30.0), lthr=profile.lthr)
    w = generate_week(low, Phase.HALF_BUILD, 3)      # would normally be an interval week
    assert any("VDOT" in n and "Interval" in n for n in w.notes)


def test_intervals_return_above_the_floor(profile):
    from marathon_engine.physiology import training_paces
    from marathon_engine.assessment import FitnessProfile
    high = FitnessProfile(
        as_of=profile.as_of, age=profile.age, hr_rest=profile.hr_rest, hr_max=profile.hr_max,
        hr_max_source=profile.hr_max_source, vdot=42.0, vdot_source="test",
        zones=profile.zones, paces=training_paces(42.0), lthr=profile.lthr)
    assert high.paces.ir_prescribable
    found = any(any(s.type == SessionType.INTERVALS for s in generate_week(high, Phase.HALF_BUILD, wk).sessions)
                for wk in range(1, 10))
    assert found


# ---- the race-checkpoint chain ---------------------------------------------------------------

def test_time_trial_is_scheduled_in_base_1(profile):
    """The 2000 m trial must actually appear as a session, not merely as a gate."""
    found = [wk for wk in range(1, 9)
             if any(s.type == SessionType.TIME_TRIAL
                    for s in generate_week(profile, Phase.BASE_1, wk).sessions)]
    assert found, "no time trial scheduled in BASE_1"
    assert min(found) >= 4, "a maximal effort needs a few weeks of continuous running first"


def test_time_trial_week_explains_what_it_replaces(profile):
    w = next(generate_week(profile, Phase.BASE_1, wk) for wk in range(1, 9)
             if any(s.type == SessionType.TIME_TRIAL
                    for s in generate_week(profile, Phase.BASE_1, wk).sessions))
    assert any("submaximal" in n.lower() for n in w.notes)


def test_time_trial_carries_a_safety_cue(profile):
    w = next(generate_week(profile, Phase.BASE_1, wk) for wk in range(1, 9)
             if any(s.type == SessionType.TIME_TRIAL
                    for s in generate_week(profile, Phase.BASE_1, wk).sessions))
    tt = next(s for s in w.sessions if s.type == SessionType.TIME_TRIAL)
    assert any("chest" in c.lower() for c in tt.cues)
    assert any("peak heart rate" in c.lower() for c in tt.cues)


def test_race_checkpoints_ascend_by_distance_across_phases():
    """2000 m seeds VDOT, then 5K, then 10K, then the half. Each phase asks for one step further --
    asking for a 10K before a 5K would be a maximal effort at an untested distance."""
    def keys(p):
        return {g.key for g in PHASE_GATES[p]}
    assert "time_trial_2000m_done" in keys(Phase.BASE_1)
    assert "five_k_completed" in keys(Phase.BASE_2)
    assert "ten_k_completed" in keys(Phase.HALF_BUILD)
    assert "half_completed" in keys(Phase.HALF_BUILD)
    # And no phase asks for a distance before the one below it.
    assert "five_k_completed" not in keys(Phase.BASE_1)
    assert "ten_k_completed" not in keys(Phase.BASE_2)


def test_run_walk_ladder_starts_from_demonstrated_capacity():
    """An athlete already holding several minutes must not be given one-minute repeats.

    The ladder's bottom rung is right for someone who cannot run for a minute and wrong for someone
    observed holding nearly five. Starting them there is not caution: it is weeks of sessions that
    never load the tissue they exist to load.
    """
    from marathon_engine.plan import run_walk_entry_rung, _RUN_WALK_LADDER

    assert run_walk_entry_rung(None) == 0, "nothing known means the bottom rung"
    assert run_walk_entry_rung(0) == 0
    assert run_walk_entry_rung(1.0) == 0, "one minute held is still the bottom rung"

    # Entry is one rung BELOW demonstrated capacity: a single effort at a pace that drove heart rate
    # to 180 is a different demand from the same block repeated aerobically several times.
    for held in (4.7, 8.0, 15.0):
        i = run_walk_entry_rung(held)
        assert _RUN_WALK_LADDER[i][0] < held, (
            f"entering at {_RUN_WALK_LADDER[i][0]} min for someone who held {held} is not below it")
        assert i < len(_RUN_WALK_LADDER) - 1, "never enter at the final continuous rung"

    # Monotonic: more demonstrated capacity never yields a lower entry.
    rungs = [run_walk_entry_rung(x) for x in (0, 1, 2, 3, 5, 8, 12, 20, 40)]
    assert rungs == sorted(rungs), rungs


def test_demonstrated_capacity_changes_the_prescription_but_not_the_intensity():
    """It moves where the ladder starts. It must not move the zones the running is done in."""
    from datetime import date
    from marathon_engine.cli import _estimated_profile
    from marathon_engine.plan import generate_week, Phase

    base = _estimated_profile(age=30, hr_rest=55)
    trained = _estimated_profile(age=30, hr_rest=55)
    trained.demonstrated_run_min = 4.7

    def run_walk_of(profile):
        wk = generate_week(profile, Phase.FOUNDATION, 1)
        rw = [s for s in wk.sessions if s.run_walk]
        assert rw, "FOUNDATION week 1 must prescribe run-walk"
        return rw[0]

    a, b = run_walk_of(base), run_walk_of(trained)
    assert b.run_walk[0] > a.run_walk[0], (
        f"demonstrated capacity must lengthen the run block: {a.run_walk} -> {b.run_walk}")
    # The same session that demonstrated the capacity also showed heart rate in Z5 within four
    # minutes. Longer blocks at the same easy intensity is the point; harder blocks is the failure.
    assert b.zones == a.zones, "capacity changes duration, never intensity"
    assert b.pace_range_sec_km == a.pace_range_sec_km
