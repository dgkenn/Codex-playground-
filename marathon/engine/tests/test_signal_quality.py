"""Signal-quality tests, focused on cadence lock-on -- the failure that looks like good data.

Cadence lock-on deserves the most attention of anything in this file: it produces a *lower
variance*, physiologically plausible heart rate, so any quality heuristic based on smoothness
actively prefers the corrupted signal. If the controller acts on it, it will tell a runner to slow
down because their step rate went up.
"""

from __future__ import annotations

import math

import pytest

from marathon_engine.signal_quality import (
    CADENCE_LOCK_MIN_SAMPLES, DROPOUT_TIMEOUT_S, HR_MAX_BPM, HR_MIN_BPM, MALIK_FRACTION,
    MAX_HR_SLEW_BPM_S, PPG_WARMUP_S, PPI_MAX_MS, PPI_MIN_MS, HrGate, HrSample,
    cadence_lock_suspicion, clean_intervals, frozen_hr_suspicion, ln_rmssd, not_worn_suspicion,
    rmssd,
)


# ---- interval cleaning ---------------------------------------------------------------------

def test_clean_intervals_keeps_a_good_series():
    ivs = [800, 810, 805, 815, 808]
    clean, counts = clean_intervals(ivs)
    assert clean == [float(v) for v in ivs]
    assert counts["kept"] == 5


def test_device_blocker_bit_is_respected():
    """Polar's own verdict on a beat overrides anything we could infer."""
    clean, counts = clean_intervals([800, 810, 805], blockers=[False, True, False])
    assert counts["blocker"] == 1
    assert 810.0 not in clean


def test_high_reported_error_is_dropped():
    clean, counts = clean_intervals([800, 810, 805], error_ms=[2, 200, 3], max_error_ms=30)
    assert counts["error"] == 1
    assert 810.0 not in clean


def test_implausible_intervals_dropped():
    clean, counts = clean_intervals([800, 100, 5000, 810])
    assert counts["implausible"] == 2
    assert clean == [800.0, 810.0]


def test_malik_rule_drops_a_twenty_percent_jump():
    clean, counts = clean_intervals([800, 1200, 805])
    assert counts["malik"] == 1
    assert 1200.0 not in clean


def test_malik_compares_against_last_accepted_not_last_raw():
    """Otherwise one artifact drags its innocent neighbour out with it."""
    clean, _ = clean_intervals([800, 1200, 810])
    assert 810.0 in clean, "the beat after an artifact must be judged against the last GOOD beat"


def test_clean_intervals_counts_are_complete():
    clean, counts = clean_intervals([800, 100, 1200, 805], blockers=[False, False, False, False])
    assert counts["total"] == 4
    assert counts["kept"] + counts["implausible"] + counts["malik"] \
        + counts["blocker"] + counts["error"] == 4


def test_empty_series():
    clean, counts = clean_intervals([])
    assert clean == [] and counts["kept"] == 0


# ---- RMSSD ---------------------------------------------------------------------------------

def test_rmssd_of_constant_series_is_zero():
    assert rmssd([800.0] * 10) == pytest.approx(0.0)


def test_rmssd_hand_calculation():
    # diffs: +10, -10 -> rms = sqrt((100+100)/2) = 10
    assert rmssd([800, 810, 800]) == pytest.approx(10.0)


def test_rmssd_needs_two_intervals():
    assert rmssd([800.0]) is None
    assert rmssd([]) is None


def test_ln_rmssd_matches_log_of_rmssd():
    assert ln_rmssd([800, 810, 800]) == pytest.approx(math.log(10.0))


def test_ln_rmssd_none_when_rmssd_is_zero():
    assert ln_rmssd([800.0] * 5) is None


# ---- live HR gate --------------------------------------------------------------------------

def test_gate_starts_in_dropout():
    g = HrGate()
    assert g.status == "dropout"
    assert not g.usable_for_control


def test_gate_reports_warmup_early():
    g = HrGate()
    g.update(HrSample(t_s=5.0, hr_bpm=120))
    assert g.status == "warmup"
    assert not g.usable_for_control, "warm-up data must not drive control"


def test_gate_becomes_ok_after_warmup():
    g = HrGate()
    t = PPG_WARMUP_S + 1
    for i in range(5):
        g.update(HrSample(t_s=t + i, hr_bpm=140))
    assert g.status == "ok"
    assert g.usable_for_control


def test_gate_rejects_implausible_values():
    g = HrGate()
    g.update(HrSample(t_s=40.0, hr_bpm=140))
    assert g.update(HrSample(t_s=41.0, hr_bpm=300)) == "rejected"
    assert g.value == 140, "value must hold the last good reading, not the artifact"


def test_gate_rejects_impossible_slew():
    g = HrGate()
    g.update(HrSample(t_s=40.0, hr_bpm=140))
    # +40 bpm in 1 s is far beyond MAX_HR_SLEW_BPM_S.
    assert g.update(HrSample(t_s=41.0, hr_bpm=180)) == "rejected"


def test_gate_accepts_a_fast_but_physiological_rise():
    g = HrGate()
    g.update(HrSample(t_s=40.0, hr_bpm=140))
    # +6 bpm in 1 s is under the 8 bpm/s ceiling, so a hard interval start is not clipped.
    assert g.update(HrSample(t_s=41.0, hr_bpm=146)) == "ok"


def test_gate_declares_dropout_after_timeout():
    g = HrGate()
    g.update(HrSample(t_s=40.0, hr_bpm=140))
    assert g.tick(40.0 + DROPOUT_TIMEOUT_S + 1) == "dropout"
    assert g.value is None, "a stale value must be cleared, not held indefinitely"


def test_gate_recovers_after_dropout():
    g = HrGate()
    g.update(HrSample(t_s=40.0, hr_bpm=140))
    g.tick(60.0)
    assert g.status == "dropout"
    for i in range(5):
        g.update(HrSample(t_s=61.0 + i, hr_bpm=142))
    assert g.status == "ok"


# ---- cadence lock-on -----------------------------------------------------------------------

def test_no_suspicion_without_cadence_data():
    """Detection genuinely requires the accelerometer -- this is why we stream ACC, not just HR."""
    hist = [HrSample(t_s=float(i), hr_bpm=160.0) for i in range(60)]
    assert cadence_lock_suspicion(hist) == 0.0


def test_no_suspicion_with_too_few_samples():
    hist = [HrSample(t_s=float(i), hr_bpm=160.0, cadence_spm=160.0)
            for i in range(CADENCE_LOCK_MIN_SAMPLES - 1)]
    assert cadence_lock_suspicion(hist) == 0.0


def test_locked_signal_is_detected():
    """HR exactly tracking cadence, with a rock-steady ratio -- the classic lock-on."""
    hist = []
    for i in range(60):
        cad = 158.0 + (i % 5)          # cadence varies
        hist.append(HrSample(t_s=float(i), hr_bpm=cad, cadence_spm=cad))   # HR follows exactly
    assert cadence_lock_suspicion(hist) >= 0.8


def test_half_and_double_cadence_lock_also_detected():
    for mult in (0.5, 2.0):
        hist = []
        for i in range(60):
            cad = 160.0 + (i % 4)
            hist.append(HrSample(t_s=float(i), hr_bpm=cad * mult, cadence_spm=cad))
        assert cadence_lock_suspicion(hist) >= 0.8, f"multiplier {mult} not detected"


def test_genuine_hr_that_happens_to_equal_cadence_is_not_flagged():
    """The false-positive case that matters: a real HR of ~160 at a cadence of ~160.

    Real HR drifts independently of cadence, so the ratio is not constant. This is exactly why the
    detector weights ratio stability, not just proximity -- proximity alone would flag every runner
    whose heart rate happens to sit near their step rate.
    """
    hist = []
    for i in range(60):
        cad = 160.0 + (i % 3)
        hr = 158.0 + 6.0 * math.sin(i / 8.0)      # independent physiological wander
        hist.append(HrSample(t_s=float(i), hr_bpm=hr, cadence_spm=cad))
    assert cadence_lock_suspicion(hist) < 0.8


def test_normal_easy_run_is_not_flagged():
    """HR 135 at cadence 165 -- nowhere near a lock."""
    hist = [HrSample(t_s=float(i), hr_bpm=135.0 + (i % 4), cadence_spm=165.0 + (i % 3))
            for i in range(60)]
    assert cadence_lock_suspicion(hist) < 0.3


def test_gate_flags_cadence_lock_status():
    g = HrGate()
    t0 = PPG_WARMUP_S + 1
    for i in range(60):
        cad = 158.0 + (i % 5)
        g.update(HrSample(t_s=t0 + i, hr_bpm=cad, cadence_spm=cad))
    assert g.status == "cadence_lock"
    assert not g.usable_for_control, "a locked signal must never drive the controller"


def test_walking_cadence_is_ignored():
    """Cadence under 100 spm is walking; the lock heuristic does not apply."""
    hist = [HrSample(t_s=float(i), hr_bpm=90.0, cadence_spm=90.0) for i in range(60)]
    assert cadence_lock_suspicion(hist) == 0.0


# ---- frozen HR (Polar's documented "fixed to last reliable value") --------------------------

def test_frozen_hr_detected_while_running():
    """Polar: 'If movement is detected, the heart rate is fixed to the last reliable value.'

    A frozen HR is the most dangerous of the failure modes because the value is entirely plausible
    and perfectly smooth -- every variance-based quality check prefers it to real data.
    """
    hist = [HrSample(t_s=float(i), hr_bpm=152.0, cadence_spm=168.0) for i in range(20)]
    assert frozen_hr_suspicion(hist) >= 0.8


def test_frozen_hr_needs_a_long_enough_run():
    hist = [HrSample(t_s=float(i), hr_bpm=152.0, cadence_spm=168.0) for i in range(4)]
    assert frozen_hr_suspicion(hist) == 0.0


def test_frozen_hr_needs_the_span_not_just_the_count():
    """Eight samples inside two seconds is not a 12-second freeze."""
    hist = [HrSample(t_s=i * 0.25, hr_bpm=152.0, cadence_spm=168.0) for i in range(10)]
    assert frozen_hr_suspicion(hist) == 0.0


def test_real_hr_with_normal_variation_is_not_frozen():
    """The discriminator is IDENTITY, not low variance -- a real HR wanders a beat or two."""
    hist = [HrSample(t_s=float(i), hr_bpm=150.0 + (i % 3), cadence_spm=168.0) for i in range(30)]
    assert frozen_hr_suspicion(hist) == 0.0


def test_frozen_hr_at_rest_is_only_weakly_suspicious():
    """A genuinely resting HR can legitimately repeat, so without movement evidence this is capped."""
    hist = [HrSample(t_s=float(i), hr_bpm=56.0, cadence_spm=0.0) for i in range(30)]
    score = frozen_hr_suspicion(hist)
    assert 0 < score <= 0.6


def test_frozen_hr_without_cadence_data_is_capped():
    hist = [HrSample(t_s=float(i), hr_bpm=152.0) for i in range(30)]
    assert 0 < frozen_hr_suspicion(hist) <= 0.6


def test_gate_flags_frozen_status():
    g = HrGate()
    t0 = PPG_WARMUP_S + 1
    for i in range(30):
        g.update(HrSample(t_s=t0 + i, hr_bpm=152.0, cadence_spm=170.0))
    assert g.status == "frozen"
    assert not g.usable_for_control, "a stale value must never drive the controller"


def test_frozen_then_recovering_returns_to_ok():
    g = HrGate()
    t0 = PPG_WARMUP_S + 1
    for i in range(30):
        g.update(HrSample(t_s=t0 + i, hr_bpm=152.0, cadence_spm=170.0))
    assert g.status == "frozen"
    for i in range(30, 60):
        g.update(HrSample(t_s=t0 + i, hr_bpm=150.0 + (i % 4), cadence_spm=170.0))
    assert g.status == "ok"


# ---- not worn (because the skin-contact bit is unusable on this device) ----------------------

def test_not_worn_requires_both_stillness_and_a_frozen_value():
    """Polar documents that Verity Sense skin contact is 'very unreliable' and that it may report a
    non-zero HR when not worn -- so not-worn has to be inferred from motion plus a frozen value."""
    hist = [HrSample(t_s=float(i), hr_bpm=72.0, cadence_spm=0.0, accel_sd_g=0.001)
            for i in range(30)]
    assert not_worn_suspicion(hist) >= 0.7


def test_person_sitting_still_is_not_flagged_as_not_worn():
    """Stillness alone is not enough: a resting person's HR still varies."""
    hist = [HrSample(t_s=float(i), hr_bpm=60.0 + (i % 4), cadence_spm=0.0, accel_sd_g=0.001)
            for i in range(30)]
    assert not_worn_suspicion(hist) == 0.0


def test_running_with_frozen_hr_is_not_flagged_as_not_worn():
    """Frozen alone is not enough either -- that is the freeze fault, not a removed band."""
    hist = [HrSample(t_s=float(i), hr_bpm=152.0, cadence_spm=170.0, accel_sd_g=0.4)
            for i in range(30)]
    assert not_worn_suspicion(hist) == 0.0


def test_not_worn_returns_zero_without_accelerometer_data():
    """Refuse to guess: a false positive here discards a real run."""
    hist = [HrSample(t_s=float(i), hr_bpm=72.0, cadence_spm=0.0) for i in range(30)]
    assert not_worn_suspicion(hist) == 0.0


def test_gate_flags_not_worn():
    g = HrGate()
    t0 = PPG_WARMUP_S + 1
    for i in range(30):
        g.update(HrSample(t_s=t0 + i, hr_bpm=72.0, cadence_spm=0.0, accel_sd_g=0.001))
    assert g.status == "not_worn"
    assert not g.usable_for_control


def test_constant_cadence_cannot_confirm_a_lock():
    """A real case that used to false-positive: steady 168 spm with a heart rate around 165.

    With cadence essentially constant there is no evidence either way — a coincidentally-near heart
    rate produces identical statistics to a locked one. The detector must report suspicion without
    discarding a good signal, because the discriminating evidence is HR *following* cadence, and that
    requires cadence to lead.
    """
    hist = [HrSample(t_s=float(i), hr_bpm=165.0 + (i % 3), cadence_spm=168.0) for i in range(60)]
    score = cadence_lock_suspicion(hist)
    assert score < 0.8, "must not act on an indistinguishable case"


def test_varying_cadence_still_confirms_a_real_lock():
    """The guard must not disarm the detector: when cadence moves and HR follows it, that is a lock."""
    hist = []
    for i in range(60):
        cad = 150.0 + 20.0 * math.sin(i / 10.0)      # cadence genuinely varies
        hist.append(HrSample(t_s=float(i), hr_bpm=cad, cadence_spm=cad))
    assert cadence_lock_suspicion(hist) >= 0.8
