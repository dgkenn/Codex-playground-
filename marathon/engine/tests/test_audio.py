"""Tests for the tone channel.

The question every one of these answers is the same: **would a person wearing AirPods, unable to see
the screen, be helped or annoyed?** So the assertions are mostly about rate and about silence, not
about internal state. A channel that is technically correct and beeps forty times an hour has failed,
because it will be switched off and then it protects nobody.

The GPS-noise test is the load-bearing one. Instantaneous running pace from GPS wanders by tens of
seconds per kilometre even on a good fix, and a naive threshold turns that wander into a metronome.
"""

from __future__ import annotations

import random

import pytest

from marathon_engine.audio import (ACQUIRE_GRACE_S, LARGE_GAP_S, MILD_GAP_S, OVERLAP_FLOOR_S,
                                   SMOOTHING_S, TONE_MIN_GAP_S, AudioEvent, Earcon,
                                   PaceBandMonitor, SplitAnnouncer)

TARGET = 520.0          # 8:40 /km, a realistic easy pace for this athlete


def drive(monitor, paces, *, start=0, **kw):
    """Feed a list of per-second paces and collect the tones."""
    out = []
    for i, p in enumerate(paces):
        ev = monitor.update(start + i, p, **kw)
        if ev:
            out.append(ev)
    return out


# ------------------------------------------------------------------------------------------------
# Silence when it should be silent
# ------------------------------------------------------------------------------------------------


def test_running_on_pace_is_completely_silent():
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    assert drive(m, [TARGET] * 600) == []


def test_small_wander_inside_the_band_is_silent():
    """+/-4% on a 6% band. This is a person running normally."""
    rng = random.Random(1)
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    paces = [TARGET * (1 + rng.uniform(-0.04, 0.04)) for _ in range(900)]
    assert drive(m, paces) == []


def test_realistic_gps_noise_does_not_produce_a_metronome():
    """The load-bearing test. Even pace, noisy measurement, must not beep.

    Sigma of 5% is at the pessimistic end of what a phone reports second-to-second while running,
    and it straddles the 6% band constantly. Without the trailing mean and the hysteresis this test
    produces a tone every fifteen seconds for the whole run.
    """
    rng = random.Random(4)
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    paces = [TARGET * (1 + rng.gauss(0, 0.05)) for _ in range(1800)]
    events = drive(m, paces)
    assert len(events) <= 2, f"{len(events)} tones in 30 min of even running: {events[:6]}"


def test_no_tones_while_not_running():
    """Warm-up, walk break, paused. A walk break is the prescription, not a pace failure."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    assert drive(m, [900.0] * 600, running=False) == []


def test_channel_is_off_entirely_without_a_pace_target():
    """Beeping about a number that was never prescribed is worse than saying nothing."""
    m = PaceBandMonitor(target_pace_sec_km=None)
    assert drive(m, [900.0] * 600) == []


def test_no_judgement_until_the_window_has_filled():
    """Eight samples. Before that the honest answer is silence, not a guess off two readings."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    assert drive(m, [TARGET * 1.5] * 4) == []


# ------------------------------------------------------------------------------------------------
# Speaking up when it should
# ------------------------------------------------------------------------------------------------


def test_running_too_fast_earns_a_descending_pair():
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    events = drive(m, [TARGET * 0.85] * 60)
    assert events, "20% too fast produced no tone at all"
    assert events[0].earcon is Earcon.EASE
    assert events[0].error < 0


def test_running_slow_before_ever_reaching_pace_is_not_policed():
    """The warm-up rule.

    A tempo session opens with a ten-minute jog deliberately far slower than the target. Policing it
    produced twenty tones in five minutes telling the athlete to speed up during the part of the
    session where slow is the instruction -- found by reading a simulated transcript, not the code.
    """
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=False)
    assert drive(m, [TARGET * 1.20] * 120) == []


def test_never_reaching_pace_is_eventually_said_once():
    """But silence must not become approval. The grace is bounded."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=False)
    events = drive(m, [TARGET * 1.20] * int(ACQUIRE_GRACE_S + 120))
    assert events, "never told the athlete they were not up to pace at all"
    assert events[0].earcon is Earcon.LIFT
    assert events[0].t_s >= ACQUIRE_GRACE_S
    assert events[0].error > 0


def test_slowing_down_after_reaching_pace_is_policed_immediately():
    """Once you have held the pace, dropping off it is a real event and gets no grace."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=False)
    drive(m, [TARGET] * 60)                       # acquire
    events = drive(m, [TARGET * 1.20] * 60, start=60)
    assert events and events[0].earcon is Earcon.LIFT
    assert events[0].t_s < 60 + ACQUIRE_GRACE_S


def test_going_out_too_fast_is_policed_from_the_first_second():
    """No grace on this side. There is no session where starting too hard is the prescription."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=False)
    events = drive(m, [TARGET * 0.80] * 60)
    assert events and events[0].earcon is Earcon.EASE
    assert events[0].t_s < 30


def test_reaching_target_pace_for_the_first_time_is_not_acknowledged():
    """A pip must never be heard without a warning it refers to."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=False)
    events = drive(m, [TARGET * 1.20] * 60 + [TARGET] * 60)
    assert Earcon.IN_BAND not in [e.earcon for e in events]


def test_coming_back_into_band_closes_the_loop():
    """The single confirming pip. Without it silence is ambiguous between 'fine' and 'broken'."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    events = drive(m, [TARGET * 0.85] * 60 + [TARGET] * 60)
    kinds = [e.earcon for e in events]
    assert Earcon.EASE in kinds
    assert kinds[-1] is Earcon.IN_BAND


def test_a_ceiling_only_session_never_tells_you_to_speed_up():
    """Easy and long runs. Running slower than target is the session working, not a defect."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=True)
    assert drive(m, [TARGET * 1.35] * 600) == []


def test_a_ceiling_only_session_still_tells_you_to_ease_off():
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=True)
    events = drive(m, [TARGET * 0.80] * 60)
    assert events and events[0].earcon is Earcon.EASE


# ------------------------------------------------------------------------------------------------
# Rate ceilings
# ------------------------------------------------------------------------------------------------


def test_tone_spacing_respects_both_floors():
    """Two floors, two jobs.

    Reminders obey the fifteen-second anti-nag floor. Confirmations obey only the two-second
    overlap floor, because a confirmation fires once per excursion and ends a sequence rather than
    extending it -- holding it back for fifteen seconds meant a quick correction lost its own
    acknowledgement, which is the exact behaviour the channel is trying to reward.
    """
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    paces = []
    for i in range(1800):
        paces.append(TARGET * (0.75 if (i // 20) % 2 == 0 else 1.30))
    events = drive(m, paces)

    times = [e.t_s for e in events]
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert all(g >= OVERLAP_FLOOR_S for g in gaps), "tones would overlap in the ear"

    reminders = [e.t_s for e in events
                 if e.earcon in (Earcon.EASE, Earcon.LIFT)]
    r_gaps = [b - a for a, b in zip(reminders, reminders[1:])]
    assert all(g >= TONE_MIN_GAP_S for g in r_gaps), \
        f"anti-nag floor violated: {min(r_gaps, default=0)}"


def test_a_correction_is_acknowledged_within_the_smoothing_window():
    """The confirmation lags your correction, and this pins down by how much.

    The lag is the trailing mean, not the anti-nag floor: after you ease off, the twenty-second
    window still holds the fast samples, so the measured error only falls below the return threshold
    as those age out. That is the price of the noise rejection that keeps the channel quiet on an
    evenly-run kilometre, and it is the right trade -- but it means the acknowledgement arrives
    roughly twenty seconds after you act, not immediately. Worth knowing before wondering why the
    pip has not come yet.
    """
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    corrected_at = 30
    events = drive(m, [TARGET * 0.85] * corrected_at + [TARGET] * 60)
    assert events[-1].earcon is Earcon.IN_BAND
    lag = events[-1].t_s - corrected_at
    assert 0 < lag <= SMOOTHING_S + 5, f"acknowledgement lagged the correction by {lag}s"


def test_worst_case_rate_stays_under_four_per_minute():
    """A runner a long way out and not correcting. This is the ceiling the design promises."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    events = drive(m, [TARGET * 0.70] * 1800)
    per_min = len(events) / 30.0
    assert per_min <= 4.0, f"{per_min:.1f} tones per minute"


def test_a_mild_error_is_reminded_less_often_than_a_large_one():
    mild = PaceBandMonitor(target_pace_sec_km=TARGET)
    large = PaceBandMonitor(target_pace_sec_km=TARGET)
    n_mild = len(drive(mild, [TARGET * 0.93] * 600))     # ~7% out, just past a 6% band
    n_large = len(drive(large, [TARGET * 0.70] * 600))   # 30% out
    assert n_large > n_mild


# ------------------------------------------------------------------------------------------------
# Degradation
# ------------------------------------------------------------------------------------------------


def test_losing_pace_is_announced_once_then_silent():
    """Beeping about a number that is not real would be worse than saying nothing."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    drive(m, [TARGET] * 60)
    events = drive(m, [None] * 300, start=60, pace_trusted=False)
    assert len(events) == 1
    assert events[0].earcon is Earcon.DEGRADED


def test_pace_returning_resumes_normal_guidance():
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    drive(m, [TARGET] * 60)
    drive(m, [None] * 120, start=60, pace_trusted=False)
    events = drive(m, [TARGET * 0.80] * 120, start=180)
    assert any(e.earcon is Earcon.EASE for e in events)


# ------------------------------------------------------------------------------------------------
# Hills
# ------------------------------------------------------------------------------------------------


def test_a_climb_moves_the_band_instead_of_nagging():
    """Otherwise the channel beeps LIFT all the way up every hill, and you learn to ignore it.

    The allowance is bigger than intuition suggests. Minetti's metabolic cost at a 6% gradient is
    about 1.37x the cost on the flat, so holding the same effort means running roughly 37% slower --
    8:40/km becomes almost 11:50/km. Testing against the engine's own factor rather than a guessed
    percentage is the point: this asserts the property (the band tracks the hill), not my arithmetic.
    """
    from marathon_engine.physiology import grade_adjusted_pace_factor
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=False)
    holding_effort = TARGET * grade_adjusted_pace_factor(0.06)
    assert drive(m, [holding_effort] * 600, grade=0.06) == []


def test_a_climb_run_at_flat_pace_is_flagged_as_too_hard():
    """The other half: refusing to nag on a hill must not become refusing to notice one."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    events = drive(m, [TARGET] * 120, grade=0.06)
    assert events and events[0].earcon is Earcon.EASE


def test_the_band_widens_in_absolute_terms_on_a_climb():
    m = PaceBandMonitor(target_pace_sec_km=TARGET)
    flat_fast, flat_slow = m.band(0.0)
    climb_fast, climb_slow = m.band(0.06)
    assert climb_slow > flat_slow
    assert climb_fast > flat_fast


# ------------------------------------------------------------------------------------------------
# Splits
# ------------------------------------------------------------------------------------------------


def test_split_fires_once_per_kilometre():
    a = SplitAnnouncer(every_m=1000.0)
    said = [a.update(t, float(t) * 3.0, TARGET, "in") for t in range(1200)]
    assert len([s for s in said if s]) == 3          # 3.6 km covered


def test_split_is_short_and_leads_with_the_number():
    a = SplitAnnouncer(every_m=1000.0)
    line = None
    for t in range(400):
        line = a.update(t, float(t) * 3.0, TARGET, "in") or line
    assert line is not None
    assert line.startswith("1K")
    assert len(line) < 40, f"too long to be useful at a breathing rate: {line!r}"
    assert "on pace" in line


def test_split_reports_a_lost_signal_rather_than_a_stale_pace():
    a = SplitAnnouncer(every_m=1000.0)
    line = None
    for t in range(400):
        line = a.update(t, float(t) * 3.0, None, "unknown") or line
    assert line and "no pace signal" in line


def test_splits_can_be_disabled():
    a = SplitAnnouncer(every_m=None, every_s=None)
    assert all(a.update(t, float(t) * 3.0, TARGET, "in") is None for t in range(2000))


def test_not_up_to_pace_is_said_at_most_twice():
    """Same rule as the sensor-fault cap: actionable twice, nagging after that.

    If you cannot hit the prescribed pace today, hearing it nine more times does not help. The
    spoken weekly review raises it where it can actually change the plan.
    """
    from marathon_engine.audio import MAX_UNACQUIRED_NUDGES
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=False)
    events = drive(m, [TARGET * 1.25] * 2400)
    lifts = [e for e in events if e.earcon is Earcon.LIFT]
    assert len(lifts) == MAX_UNACQUIRED_NUDGES, f"{len(lifts)} nudges over 40 minutes"


def test_the_cap_resets_once_you_reach_pace():
    """Having hit the target, dropping off it later is a fresh event and fully policed."""
    m = PaceBandMonitor(target_pace_sec_km=TARGET, ceiling_only=False)
    drive(m, [TARGET * 1.25] * 600)                    # burns both nudges
    drive(m, [TARGET] * 120, start=600)                # acquires
    events = drive(m, [TARGET * 1.25] * 600, start=720)
    assert len([e for e in events if e.earcon is Earcon.LIFT]) > 2
