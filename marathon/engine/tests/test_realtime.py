"""Real-time controller tests. The two that matter most:

* :func:`test_controller_does_not_oscillate` -- the failure mode that makes naive HR control useless.
* :func:`test_drift_on_long_run_does_not_nag` -- the failure mode that makes it *annoying*, which in
  practice means switched off, which is the same as useless.
"""

from __future__ import annotations

import math

import pytest

from marathon_engine.physiology import five_zone_model
from marathon_engine.realtime import (
    ABORT_HR_FRACTION, ABORT_HR_SUSTAIN_S, CONFIRM_S, DECOUPLE_CONVERT, HR_DEADBAND_BPM,
    PACE_CUE_MIN_GAP_S, PAIN_STOP, PAIN_WARN, REP_FADE_ABORT_PCT, TAU_HR, ControlMode, Cue,
    CueLevel, CueScheduler, InRunController, RunState, RunTick, SessionIntent, classify_hr_rise,
    predict_steady_state_hr, safety_check, speed_correction,
)

ZONES = five_zone_model(187, 55)     # this user: Z2 = 134-151


def easy_intent():
    return SessionIntent(kind="easy", target_zones=(1, 2), target_pace_sec_km=420.0)


def controller(intent=None, slope=12.0):
    return InRunController(zones=ZONES, intent=intent or easy_intent(), hr_speed_slope=slope)


# ---- estimators ----------------------------------------------------------------------------

def test_steady_state_prediction_is_first_order_inverse():
    assert predict_steady_state_hr(140, 0.2) == pytest.approx(140 + TAU_HR * 0.2)


def test_steady_state_equals_current_when_flat():
    assert predict_steady_state_hr(140, 0.0) == 140


def test_steady_state_looks_ahead_on_a_rise():
    """The whole point: a rising HR is reported as heading higher than it currently reads."""
    assert predict_steady_state_hr(140, 0.3) > 140


def test_speed_correction_uses_the_athletes_own_slope():
    # 12 bpm too high, 12 bpm per km/h -> slow by 1 km/h = 1/3.6 m/s.
    assert speed_correction(12.0, 12.0) == pytest.approx(-1.0 / 3.6)


def test_speed_correction_sign_is_slow_down_for_high_hr():
    assert speed_correction(10.0, 12.0) < 0
    assert speed_correction(-10.0, 12.0) > 0


def test_speed_correction_guards_against_an_absurd_slope():
    """A near-zero slope from a bad fit would otherwise demand an enormous speed change."""
    assert abs(speed_correction(10.0, 0.001)) <= abs(speed_correction(10.0, 3.0))


# ---- drift vs effort -----------------------------------------------------------------------

def test_stable_hr_classified_stable():
    hr = [(float(i), 140.0) for i in range(0, 300, 10)]
    sp = [(float(i), 3.0) for i in range(0, 300, 10)]
    kind, _ = classify_hr_rise(hr, sp)
    assert kind == "stable"


def test_slow_rise_at_steady_pace_is_drift():
    # +1 bpm/min over 5 min at constant pace.
    hr = [(float(i), 140.0 + i / 60.0) for i in range(0, 300, 10)]
    sp = [(float(i), 3.0) for i in range(0, 300, 10)]
    kind, diag = classify_hr_rise(hr, sp)
    assert kind == "drift"
    assert diag["pace_cv"] < 0.06


def test_fast_rise_is_effort_increase():
    # +10 bpm/min.
    hr = [(float(i), 140.0 + 10.0 * i / 60.0) for i in range(0, 300, 10)]
    sp = [(float(i), 3.0) for i in range(0, 300, 10)]
    kind, _ = classify_hr_rise(hr, sp)
    assert kind == "effort_increase"


def test_rise_with_changing_pace_is_effort_increase():
    """Same HR slope as the drift case, but the pace moved -- so it is not drift."""
    hr = [(float(i), 140.0 + i / 60.0) for i in range(0, 300, 10)]
    sp = [(float(i), 3.0 + 0.5 * math.sin(i / 30.0)) for i in range(0, 300, 10)]
    kind, _ = classify_hr_rise(hr, sp)
    assert kind == "effort_increase"


def test_classify_needs_enough_samples():
    kind, _ = classify_hr_rise([(0.0, 140.0)], [(0.0, 3.0)])
    assert kind == "stable"


# ---- safety --------------------------------------------------------------------------------

def test_chest_pain_aborts_with_clinical_advice():
    cue = safety_check(RunTick(t_s=100, hr_bpm=140, symptom="chest_pain"), 187, 0)
    assert cue and cue.level == CueLevel.SAFETY
    assert "stop" in cue.text.lower()
    assert "medical" in cue.text.lower()


def test_focal_bone_pain_aborts_and_says_why():
    cue = safety_check(RunTick(t_s=100, hr_bpm=140, symptom="focal_bone_pain"), 187, 0)
    assert cue and "stress fracture" in cue.text.lower()


def test_calf_swelling_aborts():
    cue = safety_check(RunTick(t_s=100, hr_bpm=140, symptom="calf_swelling"), 187, 0)
    assert cue and cue.level == CueLevel.SAFETY


def test_unknown_symptom_still_aborts():
    cue = safety_check(RunTick(t_s=100, hr_bpm=140, symptom="something_odd"), 187, 0)
    assert cue and cue.level == CueLevel.SAFETY


def test_pain_above_stop_threshold_aborts():
    cue = safety_check(RunTick(t_s=100, hr_bpm=140, pain_0_10=PAIN_STOP + 1), 187, 0)
    assert cue and "stop" in cue.text.lower()


def test_pain_at_stop_threshold_does_not_abort():
    """Boundary: the rule is 'above 5/10', so exactly 5 is a warning, not a stop."""
    assert safety_check(RunTick(t_s=100, hr_bpm=140, pain_0_10=PAIN_STOP), 187, 0) is None


def test_sustained_max_hr_aborts():
    hr = ABORT_HR_FRACTION * 187 + 2
    assert safety_check(RunTick(t_s=100, hr_bpm=hr), 187, ABORT_HR_SUSTAIN_S + 1) is not None


def test_brief_high_hr_does_not_abort():
    hr = ABORT_HR_FRACTION * 187 + 2
    assert safety_check(RunTick(t_s=100, hr_bpm=hr), 187, 5.0) is None


def test_high_hr_from_a_bad_sensor_does_not_abort():
    """An artifact must not trigger a safety abort -- that is what erodes trust in the alarm."""
    hr = ABORT_HR_FRACTION * 187 + 20
    tick = RunTick(t_s=100, hr_bpm=hr, hr_status="rejected")
    assert safety_check(tick, 187, ABORT_HR_SUSTAIN_S + 1) is None


# ---- cue scheduler -------------------------------------------------------------------------

def test_safety_cue_always_fires():
    s = CueScheduler()
    s.protect(0.0, 100.0)
    cue = s.submit([Cue(CueLevel.SAFETY, "stop", "k")], 10.0)
    assert cue is not None


def test_higher_priority_wins():
    s = CueScheduler()
    out = s.submit([Cue(CueLevel.INFO, "info", "i"), Cue(CueLevel.SESSION, "session", "s")], 10.0)
    assert out.level == CueLevel.SESSION


def test_same_key_respects_cooldown():
    s = CueScheduler()
    c = Cue(CueLevel.PACE, "slow", "slow_down", cooldown_s=60.0)
    assert s.submit([c], 100.0) is not None
    assert s.submit([c], 130.0) is None, "must not repeat inside the cooldown"
    assert s.submit([c], 200.0) is not None


def test_pace_cues_are_rate_limited():
    s = CueScheduler()
    a = Cue(CueLevel.PACE, "slow", "slow_down")
    b = Cue(CueLevel.PACE, "faster", "speed_up")
    assert s.submit([a], 100.0) is not None
    assert s.submit([b], 100.0 + PACE_CUE_MIN_GAP_S - 5) is None
    assert s.submit([b], 100.0 + PACE_CUE_MIN_GAP_S + 1) is not None


def test_protected_window_blocks_low_priority():
    s = CueScheduler()
    s.protect(100.0, 8.0)
    assert s.submit([Cue(CueLevel.PACE, "slow", "slow_down")], 102.0) is None
    assert s.submit([Cue(CueLevel.SESSION, "changed", "chg")], 102.0) is not None


def test_empty_submission_returns_none():
    assert CueScheduler().submit([], 10.0) is None


# ---- the controller ------------------------------------------------------------------------

def test_mode_detection():
    c = controller()
    d = c.update(RunTick(t_s=1, hr_bpm=140, speed_m_s=2.5))
    assert d.mode == ControlMode.HR_AND_PACE
    d = c.update(RunTick(t_s=2, hr_bpm=None, hr_status="dropout", speed_m_s=2.5))
    assert d.mode == ControlMode.PACE_ONLY
    d = c.update(RunTick(t_s=3, hr_bpm=140, speed_m_s=None))
    assert d.mode == ControlMode.HR_ONLY
    d = c.update(RunTick(t_s=4, hr_bpm=None, hr_status="dropout", speed_m_s=None))
    assert d.mode == ControlMode.EFFORT_ONLY


def test_in_zone_produces_no_pace_cue():
    c = controller()
    c.state = RunState.STEADY
    for t in range(1, 200):
        d = c.update(RunTick(t_s=float(t), hr_bpm=142.0, speed_m_s=2.4))
    assert d.in_target is True
    assert d.cue is None


def test_too_hot_produces_a_slow_down_after_the_confirmation_window():
    c = controller()
    c.state = RunState.STEADY
    cues = []
    for t in range(1, 120):
        d = c.update(RunTick(t_s=float(t), hr_bpm=170.0, speed_m_s=3.2))
        if d.cue:
            cues.append((t, d.cue))
    assert cues, "a sustained over-target HR must eventually cue"
    first_t = cues[0][0]
    assert first_t >= CONFIRM_S, "must not cue before the confirmation window elapses"
    assert "ease off" in cues[0][1].text.lower()


def test_brief_spike_inside_the_deadband_does_not_cue():
    c = controller()
    c.state = RunState.STEADY
    got = None
    for t in range(1, 40):
        hr = 152.0 if 10 <= t <= 15 else 142.0       # 1 bpm over Z2 for 5 s
        d = c.update(RunTick(t_s=float(t), hr_bpm=hr, speed_m_s=2.4))
        got = got or d.cue
    assert got is None


def test_controller_does_not_oscillate():
    """The core anti-oscillation test.

    Simulate a runner who *obeys* the controller with a realistic first-order HR response. A naive
    proportional controller on raw HR produces a slow-down/speed-up limit cycle. With lead
    compensation, a deadband and rate limiting, the number of cues over 20 minutes must stay small.
    """
    c = controller()
    c.state = RunState.STEADY
    hr = 165.0                    # starts too hot
    speed = 3.2
    target_mid = 142.0
    cue_count = 0
    for t in range(1, 1200):
        d = c.update(RunTick(t_s=float(t), hr_bpm=hr, speed_m_s=speed))
        if d.cue:
            cue_count += 1
            if d.speed_correction_m_s:
                speed = max(1.5, speed + d.speed_correction_m_s)
        # First-order HR response toward the HR implied by the current speed.
        hr_target = target_mid + (speed - 2.4) * 12.0 / 3.6 * 3.6      # 12 bpm per km/h
        hr += (hr_target - hr) / TAU_HR
    assert cue_count <= 6, f"controller oscillated: {cue_count} cues in 20 minutes"
    assert abs(hr - target_mid) < 15, f"controller failed to converge: HR ended at {hr:.0f}"


def test_drift_on_long_run_explains_once_and_widens_the_band():
    """A hot long run must produce one explanation, not repeated nagging."""
    c = controller(SessionIntent(kind="long", target_zones=(1, 2)))
    c.state = RunState.STEADY
    texts = []
    # 35 min in, HR drifting 1 bpm/min at rock-steady pace.
    for i, t in enumerate(range(1800, 3600)):
        hr = 145.0 + (t - 1800) / 60.0
        d = c.update(RunTick(t_s=float(t), hr_bpm=hr, speed_m_s=2.4))
        if d.cue:
            texts.append(d.cue.text)
    drift_msgs = [x for x in texts if "drift" in x.lower()]
    assert len(drift_msgs) == 1, f"drift should be explained exactly once, got {len(drift_msgs)}"
    assert c._band_widened_bpm > 0, "the target band should widen rather than nag"


def test_easy_run_is_ceiling_only_so_too_slow_is_fine():
    """Running an easy day too slowly is not an error worth interrupting someone about."""
    c = controller(SessionIntent(kind="easy", target_zones=(1, 2)))
    c.state = RunState.STEADY
    cue = None
    for t in range(1, 300):
        d = c.update(RunTick(t_s=float(t), hr_bpm=115.0, speed_m_s=1.9))
        cue = cue or d.cue
    assert cue is None


def test_threshold_session_does_cue_when_too_slow():
    c = controller(SessionIntent(kind="threshold", target_zones=(4,)))
    c.state = RunState.STEADY
    texts = []
    for t in range(1, 300):
        d = c.update(RunTick(t_s=float(t), hr_bpm=140.0, speed_m_s=2.6))
        if d.cue:
            texts.append(d.cue.text)
    assert any("pick it up" in x.lower() for x in texts)


def test_cadence_lock_produces_a_session_cue_and_stops_hr_control():
    c = controller()
    c.state = RunState.STEADY
    d = c.update(RunTick(t_s=100.0, hr_bpm=None, hr_status="cadence_lock", speed_m_s=2.4))
    assert d.cue and "step rate" in d.cue.text.lower()
    assert d.mode == ControlMode.PACE_ONLY


def test_dropout_produces_a_session_cue():
    c = controller()
    c.state = RunState.STEADY
    d = c.update(RunTick(t_s=100.0, hr_bpm=None, hr_status="dropout", speed_m_s=2.4))
    assert d.cue and "heart-rate signal" in d.cue.text.lower()


def test_symptom_aborts_the_controller_permanently():
    c = controller()
    c.state = RunState.STEADY
    d = c.update(RunTick(t_s=100.0, hr_bpm=140, speed_m_s=2.4, symptom="chest_pain"))
    assert d.abort and d.state == RunState.ABORTED
    # And it stays aborted.
    d2 = c.update(RunTick(t_s=101.0, hr_bpm=140, speed_m_s=2.4))
    assert d2.abort


def test_pain_warning_caps_the_session_without_stopping_it():
    c = controller()
    c.state = RunState.STEADY
    d = c.update(RunTick(t_s=100.0, hr_bpm=140, speed_m_s=2.4, pain_0_10=PAIN_WARN))
    assert not d.abort
    assert d.cue and "easy run" in d.cue.text.lower()


def test_no_cues_during_warmup_state():
    """The controller must not correct pace before the runner has warmed up."""
    c = controller()
    c.state = RunState.WARMUP
    cue = None
    for t in range(1, 200):
        d = c.update(RunTick(t_s=float(t), hr_bpm=175.0, speed_m_s=3.5))
        cue = cue or (d.cue if d.cue and d.cue.level == CueLevel.PACE else None)
    assert cue is None


def test_grade_adjustment_applies_in_pace_only_mode():
    c = controller(SessionIntent(kind="threshold", target_zones=(4,),
                                 target_pace_sec_km=300.0))
    c.state = RunState.STEADY
    # Running 5:30/km up a 5% grade is FASTER in effort terms than 5:00/km flat, so no
    # "speed up" cue should fire.
    texts = []
    for t in range(1, 300):
        d = c.update(RunTick(t_s=float(t), hr_bpm=None, hr_status="dropout",
                             speed_m_s=1000.0 / 330.0, grade=0.05))
        if d.cue:
            texts.append(d.cue.text)
    assert not any("target is" in x for x in texts)


# ---- interval-set management ----------------------------------------------------------------

def test_rep_set_cut_when_pace_fades():
    c = controller(SessionIntent(kind="intervals", target_zones=(5,)))
    assert c.record_rep(1, 240.0, 170.0, 100.0) is None
    cue = c.record_rep(2, 240.0 * (1 + REP_FADE_ABORT_PCT + 0.02), 175.0, 400.0)
    assert cue and "stop here" in cue.text.lower()


def test_rep_set_not_cut_for_a_small_fade():
    c = controller(SessionIntent(kind="intervals", target_zones=(5,)))
    c.record_rep(1, 240.0, 170.0, 100.0)
    assert c.record_rep(2, 244.0, 172.0, 400.0) is None


def test_rep_set_cut_when_hr_fails_to_recover():
    c = controller(SessionIntent(kind="intervals", target_zones=(5,)))
    c.record_rep(1, 240.0, 170.0, 100.0)
    # HR at the END OF THE RECOVERY is still at 90% of reserve -- that is the "not recovering"
    # signal. It must be passed as hr_after_recovery, not as the rep-end HR.
    cue = c.record_rep(2, 241.0, 175.0, 400.0, hr_after_recovery=55 + 0.90 * 132)
    assert cue and "not coming down" in cue.text.lower()


def test_high_hr_at_rep_end_alone_never_cuts_the_set():
    """Regression guard for a real API bug. A VO2max rep ENDS near 90% of reserve by definition;
    testing that value against the recovery threshold cut essentially every interval set."""
    c = controller(SessionIntent(kind="intervals", target_zones=(5,)))
    c.record_rep(1, 240.0, 55 + 0.92 * 132, 100.0)
    assert c.record_rep(2, 241.0, 55 + 0.93 * 132, 400.0) is None


def test_good_recovery_does_not_cut_the_set():
    c = controller(SessionIntent(kind="intervals", target_zones=(5,)))
    c.record_rep(1, 240.0, 175.0, 100.0)
    assert c.record_rep(2, 241.0, 176.0, 400.0, hr_after_recovery=55 + 0.65 * 132) is None


def test_recording_a_rep_protects_the_cue_window():
    c = controller(SessionIntent(kind="intervals", target_zones=(5,)))
    c.record_rep(1, 240.0, 170.0, 100.0)
    assert c.scheduler.protected_until > 100.0


def test_set_cut_message_reframes_stopping_as_correct():
    c = controller(SessionIntent(kind="intervals", target_zones=(5,)))
    c.record_rep(1, 240.0, 170.0, 100.0)
    cue = c.record_rep(2, 300.0, 175.0, 400.0)
    assert "fatigue, not fitness" in cue.text.lower()


# ---- long-run conversion ---------------------------------------------------------------------

def test_long_run_converted_when_decoupling_is_high_past_halfway():
    c = controller(SessionIntent(kind="long", target_zones=(1, 2)))
    cue = c.check_long_run_decoupling(DECOUPLE_CONVERT + 0.05, 5000.0, 0.6)
    assert cue and "walk breaks" in cue.text.lower()


def test_long_run_not_converted_before_halfway():
    c = controller(SessionIntent(kind="long", target_zones=(1, 2)))
    assert c.check_long_run_decoupling(0.20, 1000.0, 0.3) is None


def test_long_run_not_converted_for_acceptable_decoupling():
    c = controller(SessionIntent(kind="long", target_zones=(1, 2)))
    assert c.check_long_run_decoupling(0.04, 5000.0, 0.8) is None


def test_decision_is_serialisable():
    import json
    c = controller()
    d = c.update(RunTick(t_s=1.0, hr_bpm=140, speed_m_s=2.4))
    json.dumps(d.to_dict())
