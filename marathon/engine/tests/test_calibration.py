"""Calibration-recording tests: parsing, sensor health, gait, and stage summarisation.

The important ones are the sensor-health tests. The whole point of a calibration session is to find
out how the device behaves *on this arm at these paces* rather than assuming, so the detectors have to
work on recorded data as well as live.
"""

from __future__ import annotations

import json
import math
from datetime import datetime

import pytest

from marathon_engine.calibration import (
    SCHEMA_VERSION, STEADY_BLOCK_MIN, CalibrationRecording, RecordingSample, analyse_recording,
    calibration_protocol, load_recording,
)


def sample_series(*, seconds: int, hr, speed_kmh: float, cadence: float = 168.0,
                  label: str = "stage_1", start: float = 0.0, frozen: bool = False):
    out = []
    for i in range(seconds):
        v = hr if isinstance(hr, (int, float)) else hr(i)
        out.append(RecordingSample(
            t_s=start + i, hr_bpm=(hr if frozen else v), speed_m_s=speed_kmh / 3.6,
            cadence_spm=cadence, accel_sd_g=0.35, gyro_p2p_dps=180.0,
            swing_interval_ms=60_000.0 / cadence * 2, label=label))
    return out


def good_recording() -> CalibrationRecording:
    samples = []
    t = 0.0
    for i, (kmh, base) in enumerate([(5.0, 98), (6.0, 112), (7.0, 133), (8.0, 151), (9.0, 165)],
                                    start=1):
        samples += sample_series(seconds=240, hr=lambda k, b=base: b + 2.0 * math.sin(k / 25.0),
                                 speed_kmh=kmh, label=f"stage_{i}", start=t)
        t += 240
    samples += sample_series(seconds=1200, hr=lambda k: 140 + 3.0 * math.sin(k / 40.0),
                             speed_kmh=7.0, label="steady", start=t)
    return CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                                samples=samples, temp_c=18.0, surface="treadmill",
                                resting_ppi_ms=[900 + (i % 7) for i in range(600)])


# ---- parsing -------------------------------------------------------------------------------

def test_load_recording_roundtrip():
    payload = {
        "schema_version": SCHEMA_VERSION,
        "started_at": "2026-08-05T07:00:00",
        "age": 30, "hr_rest": 55,
        "samples": [{"t_s": 0.0, "hr_bpm": 100.0, "speed_m_s": 2.0, "label": "stage_1"}],
        "temp_c": 18.0,
    }
    rec = load_recording(payload)
    assert rec.age == 30
    assert len(rec.samples) == 1
    assert rec.samples[0].hr_bpm == 100.0


def test_load_rejects_wrong_schema_version():
    with pytest.raises(ValueError, match="schema version"):
        load_recording({"schema_version": 999, "started_at": "2026-08-05T07:00:00",
                        "age": 30, "hr_rest": 55, "samples": []})


def test_load_rejects_missing_required_field():
    with pytest.raises(ValueError, match="hr_rest"):
        load_recording({"schema_version": SCHEMA_VERSION,
                        "started_at": "2026-08-05T07:00:00", "age": 30, "samples": []})


def test_load_tolerates_unknown_sample_fields():
    """Forward compatibility: a newer app version adding a field must not break the parser."""
    payload = {"schema_version": SCHEMA_VERSION, "started_at": "2026-08-05T07:00:00",
               "age": 30, "hr_rest": 55,
               "samples": [{"t_s": 0.0, "hr_bpm": 100.0, "future_field": 42}]}
    rec = load_recording(payload)
    assert len(rec.samples) == 1


# ---- stage summarisation -------------------------------------------------------------------

def test_stages_are_found_and_summarised():
    r = analyse_recording(good_recording())
    assert len(r.stages) == 5
    assert r.stages[0]["speed_kmh"] == pytest.approx(5.0, abs=0.05)


def test_stage_hr_uses_only_the_final_minute():
    """HR needs 2-3 min to plateau, so a whole-stage mean understates it -- and understates it MORE
    at higher speeds, which biases the HR/speed slope shallow and makes every derived pace too fast."""
    rising = []
    for i in range(240):
        rising.append(RecordingSample(t_s=float(i), hr_bpm=100.0 + i * 0.2, speed_m_s=2.0,
                                      cadence_spm=168.0, label="stage_1"))
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                               samples=rising)
    r = analyse_recording(rec)
    # Whole-stage mean would be ~124; the final minute averages ~144.
    assert r.stages[0]["steady_hr"] > 140


def test_profile_is_derived_from_the_stages():
    r = analyse_recording(good_recording())
    assert r.profile is not None
    assert r.profile.hr_rest == 55
    assert r.profile.zones.zones


def test_too_few_stages_warns_instead_of_guessing():
    samples = sample_series(seconds=240, hr=120, speed_kmh=6.0, label="stage_1")
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                               samples=samples)
    r = analyse_recording(rec)
    assert r.profile is None
    assert any("stages" in w for w in r.warnings)


def test_observed_hr_max_is_reported():
    r = analyse_recording(good_recording())
    assert r.observed_hr_max is not None
    assert r.observed_hr_max >= 165


# ---- steady block --------------------------------------------------------------------------

def test_steady_block_yields_decoupling_and_ef():
    r = analyse_recording(good_recording())
    assert r.steady is not None
    assert "decoupling" in r.steady
    assert r.steady["efficiency_factor"] > 0
    assert r.steady["duration_min"] >= 19


def test_low_decoupling_is_called_aerobic():
    r = analyse_recording(good_recording())
    assert abs(r.steady["decoupling"]) < 0.05
    assert "aerobic" in r.steady["interpretation"].lower()


def test_high_decoupling_says_the_pace_was_too_hot():
    """Same pace, HR climbing hard through the block."""
    samples = []
    for i, (kmh, base) in enumerate([(5.0, 98), (6.0, 112), (7.0, 133)], start=1):
        samples += sample_series(seconds=240, hr=base, speed_kmh=kmh, label=f"stage_{i}",
                                 start=(i - 1) * 240)
    for i in range(1200):
        samples.append(RecordingSample(t_s=720.0 + i, hr_bpm=140.0 + i * 0.02, speed_m_s=2.0,
                                       cadence_spm=168.0, label="steady"))
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                               samples=samples)
    r = analyse_recording(rec)
    assert r.steady["decoupling"] > 0.05
    assert "slower" in r.steady["interpretation"].lower()


def test_missing_steady_block_prompts_for_one():
    samples = []
    for i, (kmh, base) in enumerate([(5.0, 98), (6.0, 112), (7.0, 133)], start=1):
        samples += sample_series(seconds=240, hr=base, speed_kmh=kmh, label=f"stage_{i}",
                                 start=(i - 1) * 240)
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                               samples=samples)
    r = analyse_recording(rec)
    assert r.steady is None
    assert any("steady" in a.lower() for a in r.next_actions)


# ---- sensor health -------------------------------------------------------------------------

def test_clean_recording_is_graded_good():
    r = analyse_recording(good_recording())
    assert r.sensor.verdict == "good"
    assert r.sensor.hr_coverage > 0.95
    assert any("trustworthy" in f.lower() for f in r.sensor.findings)


def test_frozen_hr_is_measured_not_assumed():
    """Polar holds the last reliable value when it detects movement. On recorded data we can measure
    exactly how often that happened on THIS arm at THESE paces, rather than guessing."""
    samples = []
    for i, (kmh, base) in enumerate([(5.0, 98), (6.0, 112), (7.0, 133)], start=1):
        samples += sample_series(seconds=240, hr=base, speed_kmh=kmh, label=f"stage_{i}",
                                 start=(i - 1) * 240, frozen=True)
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                               samples=samples)
    r = analyse_recording(rec)
    assert r.sensor.frozen_seconds > 500
    assert r.sensor.frozen_fraction > 0.5
    assert any("frozen" in f.lower() for f in r.sensor.findings)


def test_heavy_freezing_recommends_a_chest_strap_for_intervals():
    samples = []
    for i, (kmh, base) in enumerate([(5.0, 98), (6.0, 112), (7.0, 133)], start=1):
        samples += sample_series(seconds=240, hr=base, speed_kmh=kmh, label=f"stage_{i}",
                                 start=(i - 1) * 240, frozen=True)
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                               samples=samples)
    r = analyse_recording(rec)
    assert any("h10" in a.lower() or "chest strap" in a.lower() for a in r.next_actions)


def test_poor_coverage_is_flagged_with_a_fix():
    samples = []
    for i, (kmh, base) in enumerate([(5.0, 98), (6.0, 112), (7.0, 133)], start=1):
        block = sample_series(seconds=240, hr=base, speed_kmh=kmh, label=f"stage_{i}",
                              start=(i - 1) * 240)
        for s in block[:120]:
            s.hr_bpm = None                      # half the stage has no HR
        samples += block
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                               samples=samples)
    r = analyse_recording(rec)
    assert r.sensor.hr_coverage < 0.9
    assert any("upper arm" in f for f in r.sensor.findings)


def test_ppi_artifact_fraction_is_computed_from_the_resting_block():
    rec = good_recording()
    rec.resting_ppi_ms = [900] * 300 + [200] * 100      # 25% implausible
    r = analyse_recording(rec)
    assert r.sensor.ppi_artifact_fraction is not None
    assert r.sensor.ppi_artifact_fraction > 0.2
    assert any("5%" in f for f in r.sensor.findings)


def test_no_resting_block_means_no_ppi_figure():
    rec = good_recording()
    rec.resting_ppi_ms = []
    r = analyse_recording(rec)
    assert r.sensor.ppi_artifact_fraction is None


# ---- gait ----------------------------------------------------------------------------------

def test_cadence_is_bucketed_by_speed():
    r = analyse_recording(good_recording())
    assert r.gait.cadence_by_speed
    assert r.gait.cadence_overall == pytest.approx(168.0, abs=1)


def test_gait_refuses_to_claim_a_cadence_target():
    """The '180 spm' figure is a misreading of elites at race pace; what has evidence is a relative
    change from the runner's own baseline."""
    r = analyse_recording(good_recording())
    text = " ".join(r.gait.findings).lower()
    assert "180" in text and "misreading" in text


def test_gait_caveats_are_explicit_about_what_an_arm_sensor_cannot_measure():
    r = analyse_recording(good_recording())
    caveats = " ".join(r.gait.caveats).lower()
    assert "ground contact" in caveats
    assert "not" in caveats


def test_stride_variability_computed():
    r = analyse_recording(good_recording())
    assert r.gait.stride_variability_cv is not None


def test_falling_arm_swing_amplitude_is_reported_as_fatigue():
    samples = []
    for i, (kmh, base) in enumerate([(5.0, 98), (6.0, 112), (7.0, 133)], start=1):
        samples += sample_series(seconds=240, hr=base, speed_kmh=kmh, label=f"stage_{i}",
                                 start=(i - 1) * 240)
    # Swing amplitude decaying through a long steady block.
    for i in range(1200):
        samples.append(RecordingSample(t_s=720.0 + i, hr_bpm=140.0, speed_m_s=2.0,
                                       cadence_spm=168.0, gyro_p2p_dps=200.0 - i * 0.05,
                                       swing_interval_ms=714.0, label="steady"))
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, 7, 0), age=30, hr_rest=55,
                               samples=samples)
    r = analyse_recording(rec)
    assert r.gait.swing_amplitude_change_pct is not None
    assert r.gait.swing_amplitude_change_pct < -12
    assert any("fatigue" in f.lower() for f in r.gait.findings)


# ---- protocol ------------------------------------------------------------------------------

def test_protocol_forbids_ppi_during_the_moving_part():
    """Enabling PPI throttles HR to one update per 5 s and aborts any ongoing training."""
    p = calibration_protocol(30, 55)
    setup = " ".join(p["device_setup"]).lower()
    assert "do not enable ppi" in setup
    assert "five seconds" in setup or "5 seconds" in setup


def test_protocol_records_resting_ppi_separately():
    p = calibration_protocol(30, 55)
    assert "PPI only" in p["resting_block"]["streams"]
    assert "mutually exclusive" in p["resting_block"]["why"]


def test_protocol_asks_for_the_talk_test_explicitly():
    """The recording cannot capture a subjective field, and it is the most informative one."""
    p = calibration_protocol(30, 55)
    assert any("sentence" in x.lower() for x in p["at_each_stage"])


def test_protocol_explains_the_final_minute_rule():
    p = calibration_protocol(30, 55)
    assert any("plateau" in x.lower() for x in p["at_each_stage"])


def test_protocol_warns_about_sensor_mode_for_file_transfer():
    p = calibration_protocol(30, 55)
    after = " ".join(p["afterwards"]).lower()
    assert "sensor mode" in after
    assert "system_busy" in after


def test_protocol_includes_a_steady_block_of_the_right_length():
    p = calibration_protocol(30, 55)
    assert f"{STEADY_BLOCK_MIN:.0f}" in p["steady_block"]["what"]


def test_protocol_stop_rules_present():
    p = calibration_protocol(30, 55)
    assert len(p["stop_when_any"]) >= 4


def test_result_is_serialisable():
    r = analyse_recording(good_recording())
    json.dumps(r.to_dict())


def test_missing_seconds_count_against_coverage_even_when_absent_from_the_file():
    """A recorder may signal a dropout by omitting seconds rather than writing nulls.

    The Web Bluetooth logger does exactly that, on purpose: writing the last known heart rate through
    a dropout produces a plausible flat series that cannot be detected afterwards, so it writes
    nothing instead. Dividing by the row count made that honesty invisible -- every row present had a
    heart rate, so coverage read 100% on a recording that had lost half its data. Coverage gates
    whether a session contributes training load, so this was not a display bug.
    """
    from marathon_engine.calibration import CalibrationRecording, RecordingSample, analyse_recording
    from datetime import datetime, timezone

    # Ten minutes of wall clock, but the middle five are simply not in the file.
    samples = [RecordingSample(t_s=float(t), hr_bpm=140.0, speed_m_s=2.5, cadence_spm=160.0,
                               accel_sd_g=0.3, label="steady")
               for t in list(range(0, 150)) + list(range(450, 600))]
    rec = CalibrationRecording(started_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
                               age=30, hr_rest=55, samples=samples)
    health = analyse_recording(rec).sensor
    assert health.hr_coverage < 0.6, (
        f"coverage read {health.hr_coverage:.0%} on a recording missing half its seconds")
    assert health.dropout_seconds > 250, health.dropout_seconds


def test_ramp_ladder_is_tailored_from_a_previous_run():
    """The default top stage of 10 km/h is a guess about a stranger.

    If the athlete's own data says they cross 85% of heart-rate reserve well below it, the last
    stages of the default ramp trigger the stop rule and are never recorded — and a ramp that ends
    early gives fewer points to fit a line through, in exactly the range where the line matters.
    """
    from marathon_engine.calibration import (DEFAULT_TOP_STAGE_KMH, RecordingSample,
                                             calibration_protocol, top_stage_from_run)

    # Two minutes at 9 km/h with heart rate settling comfortably under the 85% HRR stop (167).
    seg = [RecordingSample(t_s=float(t), hr_bpm=150.0, speed_m_s=2.5) for t in range(120)]
    top = top_stage_from_run(seg, hr_max=187, hr_rest=55)
    assert top is not None
    assert 8.5 < top < 9.5

    tailored = calibration_protocol(age=30, hr_rest=55, top_stage_kmh=top - 0.5)
    default = calibration_protocol(age=30, hr_rest=55)
    assert tailored["stages"][-1]["speed_kmh"] < default["stages"][-1]["speed_kmh"]
    assert default["stages"][-1]["speed_kmh"] == DEFAULT_TOP_STAGE_KMH
    # The spread the fit needs is preserved: still six stages, still 1 km/h apart.
    assert len(tailored["stages"]) == 6
    speeds = [s["speed_kmh"] for s in tailored["stages"]]
    assert all(round(b - a, 1) == 1.0 for a, b in zip(speeds, speeds[1:]))


def test_a_run_with_no_settled_minute_tailors_nothing():
    """Returning None rather than a guess. Most ordinary runs cannot support this judgement."""
    from marathon_engine.calibration import RecordingSample, top_stage_from_run
    # Thirty-second bursts only: nothing long enough to have begun settling.
    seg = []
    for block in range(6):
        seg += [RecordingSample(t_s=float(block * 60 + t), hr_bpm=150.0, speed_m_s=2.5)
                for t in range(30)]
    assert top_stage_from_run(seg, hr_max=187, hr_rest=55) is None


def test_a_run_held_above_the_stop_threshold_tailors_nothing():
    """Heart rate over the ceiling is not evidence of a sustainable speed."""
    from marathon_engine.calibration import RecordingSample, top_stage_from_run
    seg = [RecordingSample(t_s=float(t), hr_bpm=178.0, speed_m_s=2.5) for t in range(200)]
    assert top_stage_from_run(seg, hr_max=187, hr_rest=55) is None
