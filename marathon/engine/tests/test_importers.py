"""Tests for reading what Polar Flow actually exports.

The fixtures here are synthesised rather than recorded, which is a real limitation and is stated
rather than hidden: a genuine Polar export may differ in ways these tests cannot anticipate. What
they do pin down is everything that is a property of the *format* and of the arithmetic — namespace
handling, timestamp variants, cumulative-distance differentiation, the refusal to invent data that is
not there, and the stage segmentation that makes an import worth doing at all.

One test below documents a finding rather than a requirement: a perfectly noiseless heart-rate series
trips the frozen-HR detector. That is correct behaviour on the detector's part — a heart rate that
never moves *is* what a frozen sensor looks like — and it matters here because it means a synthetic
fixture must carry beat-to-beat jitter or it will fail for reasons that have nothing to do with the
importer.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from marathon_engine.calibration import analyse_recording
from marathon_engine.importers import (
    MAX_PLAUSIBLE_SPEED_M_S, label_stages, load_any, recording_from_csv, recording_from_tcx)

T0 = datetime(2026, 8, 2, 7, 30, 0, tzinfo=timezone.utc)


def _tcx(points, *, namespaced=True, cadence=False):
    """Build a TCX document from ``(t_s, hr, cumulative_m, altitude_m)`` tuples."""
    ext = ('<Extensions><TPX xmlns="http://www.garmin.com/xmlschemas/ActivityExtension/v2">'
           "<RunCadence>82</RunCadence></TPX></Extensions>") if cadence else ""
    body = "".join(
        f"<Trackpoint><Time>"
        f'{(T0 + timedelta(seconds=t)).isoformat().replace("+00:00", "Z")}</Time>'
        f"<AltitudeMeters>{a:.1f}</AltitudeMeters>"
        f"<DistanceMeters>{d:.2f}</DistanceMeters>"
        f"<HeartRateBpm><Value>{int(round(h))}</Value></HeartRateBpm>{ext}</Trackpoint>"
        for t, h, d, a in points)
    ns = ' xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"' if namespaced else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?><TrainingCenterDatabase{ns}>'
            f"<Activities><Activity Sport=\"Running\"><Lap><Track>{body}</Track></Lap>"
            f"</Activity></Activities></TrainingCenterDatabase>")


def _ramp_points(*, jitter=1.4, seed=7, stage_s=240, speeds_kmh=(5, 6, 7, 8, 9, 10)):
    """A treadmill ramp: walking warm-up then constant-speed stages, HR lagging with tau=45 s."""
    rng = random.Random(seed)
    pts, dist, hr, t = [], 0.0, 62.0, 0
    for dur, v in [(300, 1.25)] + [(stage_s, k / 3.6) for k in speeds_kmh]:
        for _ in range(dur):
            hr += (55 + v * 3.6 * 12 - hr) * (1 - math.exp(-1 / 45))
            dist += v
            pts.append((t, hr + rng.gauss(0, jitter), dist, 30.0))
            t += 1
    return pts


# ------------------------------------------------------------------------------------------------
# TCX
# ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("namespaced", [True, False])
def test_parses_with_and_without_the_namespace(namespaced):
    """Some exporters drop the namespace. Both shapes are real files."""
    rec, _ = recording_from_tcx(_tcx(_ramp_points(), namespaced=namespaced), age=30, hr_rest=55)
    assert len(rec.samples) == 1740
    assert rec.samples[0].hr_bpm is not None


def test_speed_is_derived_from_cumulative_distance():
    rec, _ = recording_from_tcx(_tcx(_ramp_points()), age=30, hr_rest=55)
    speeds = [s.speed_m_s for s in rec.samples if s.speed_m_s]
    # The ramp tops out at 10 km/h = 2.78 m/s; the warm-up walks at 1.25.
    assert 1.1 < min(speeds) < 1.5
    assert 2.6 < max(speeds) < 2.9


def test_distance_going_backwards_yields_no_speed_rather_than_a_negative_one():
    """GPS does this. A negative speed downstream would be worse than a gap."""
    pts = [(t, 140, 100.0 - t, 30.0) for t in range(60)]     # distance decreasing
    rec, _ = recording_from_tcx(_tcx(pts), age=30, hr_rest=55)
    assert all(s.speed_m_s is None for s in rec.samples)


def test_implausible_speed_is_rejected():
    """A teleport in the distance track is a bad fix, not a sprint."""
    pts = [(t, 140, t * 50.0, 30.0) for t in range(60)]      # 50 m/s
    rec, _ = recording_from_tcx(_tcx(pts), age=30, hr_rest=55)
    assert all(s.speed_m_s is None or s.speed_m_s <= MAX_PLAUSIBLE_SPEED_M_S
               for s in rec.samples)


def test_cadence_is_doubled_from_polar_stride_rate():
    """Polar writes RunCadence as strides per minute; everything else here uses steps."""
    rec, _ = recording_from_tcx(_tcx(_ramp_points(), cadence=True), age=30, hr_rest=55)
    cads = [s.cadence_spm for s in rec.samples if s.cadence_spm]
    assert cads and all(c == pytest.approx(164.0) for c in cads)


def test_missing_heart_rate_is_an_error_not_an_empty_result():
    """There is nothing to calibrate from, and saying so beats returning an empty recording."""
    body = ("<Trackpoint><Time>2026-08-02T07:30:00Z</Time>"
            "<DistanceMeters>1.0</DistanceMeters></Trackpoint>")
    doc = ('<?xml version="1.0"?><TrainingCenterDatabase>'
           f"<Activities><Activity><Lap><Track>{body}</Track></Lap></Activity></Activities>"
           "</TrainingCenterDatabase>")
    with pytest.raises(ValueError, match="no heart rate"):
        recording_from_tcx(doc, age=30, hr_rest=55)


def test_absent_accelerometer_is_reported_not_silently_assumed_fine():
    """The difference between 'the band was fine' and 'nothing here could show otherwise'."""
    _, warnings = recording_from_tcx(_tcx(_ramp_points()), age=30, hr_rest=55)
    assert any("PARTIAL" in w for w in warnings)
    assert any("accelerometer" in w for w in warnings)


def test_sparse_sampling_is_called_out():
    """Polar Flow's 'smart' recording rate throws most of the data away."""
    pts = [(t * 10, 140 + (t % 3), t * 10 * 2.5, 30.0) for t in range(60)]
    _, warnings = recording_from_tcx(_tcx(pts), age=30, hr_rest=55)
    assert any("1 second" in w for w in warnings)


def test_gpx_gets_a_useful_error_rather_than_a_parse_failure(tmp_path):
    p = tmp_path / "run.gpx"
    p.write_text('<?xml version="1.0"?><gpx version="1.1"><trk></trk></gpx>')
    with pytest.raises(ValueError, match="TCX"):
        load_any(p, age=30, hr_rest=55)


# ------------------------------------------------------------------------------------------------
# Stage segmentation
# ------------------------------------------------------------------------------------------------


def test_stages_are_recovered_from_a_ramp():
    """Without labels there is no HR-speed fit, and without the fit the import is pointless."""
    rec, _ = recording_from_tcx(_tcx(_ramp_points()), age=30, hr_rest=55)
    n = label_stages(rec)
    assert n >= 3, "a six-stage treadmill ramp should yield at least three usable plateaus"
    assert any(s.label.startswith("stage_") for s in rec.samples)


def test_a_variable_pace_run_yields_no_stages():
    """The right answer for a road run. A fit through speeds never held is worse than no fit."""
    rng = random.Random(3)
    pts, dist, hr = [], 0.0, 140.0
    for t in range(1800):
        v = 2.6 + math.sin(t / 45) * 0.8 + rng.gauss(0, 0.15)
        dist += max(0.5, v)
        pts.append((t, hr + rng.gauss(0, 2), dist, 30.0))
    rec, _ = recording_from_tcx(_tcx(pts), age=30, hr_rest=55)
    assert label_stages(rec) == 0


def test_standing_still_is_not_a_stage():
    pts = [(t, 70, 0.0, 30.0) for t in range(600)]
    rec, _ = recording_from_tcx(_tcx(pts), age=30, hr_rest=55)
    assert label_stages(rec) == 0


def test_the_import_produces_a_usable_profile_end_to_end():
    """The whole point: a Polar export becomes zones, paces and a controller gain."""
    rec, _ = recording_from_tcx(_tcx(_ramp_points()), age=30, hr_rest=55)
    label_stages(rec)
    result = analyse_recording(rec)
    assert result.profile is not None
    slope, _intercept, r2 = result.profile.ramp_fit
    # The fixture was generated with 12 bpm per km/h; recovering it is the test.
    assert slope == pytest.approx(12.0, abs=1.5)
    assert r2 > 0.95
    assert result.profile.prescription_basis == "hr_from_ramp"
    assert result.profile.hr_paces


def test_a_noiseless_heart_rate_reads_as_frozen():
    """Documents a real property of the detector, and why fixtures must carry jitter.

    A heart rate that never changes is indistinguishable from Polar holding the last reliable value,
    which is exactly what the detector exists to catch. Real optical HR jitters a beat or two at
    1 Hz; a mathematically smooth series does not, and gets flagged. That is the detector being
    right, not a bug -- but it is a trap for anyone writing a synthetic fixture.
    """
    smooth, noisy = _ramp_points(jitter=0.0), _ramp_points(jitter=1.4)
    frozen = []
    for pts in (smooth, noisy):
        # cadence=True matters: the frozen detector needs evidence of movement before a steady heart
        # rate means anything. Sitting still with a steady pulse is not a fault, it is a person
        # sitting still. Without cadence the detector cannot run at all -- which is itself worth
        # knowing, and is why the importer warns about a cadence-free export.
        rec, _ = recording_from_tcx(_tcx(pts, cadence=True), age=30, hr_rest=55)
        label_stages(rec)
        frozen.append(analyse_recording(rec).sensor.frozen_fraction)
    assert frozen[0] > 0.5, "a perfectly flat HR series should look frozen"
    assert frozen[1] < 0.05, "realistic beat-to-beat jitter should not"


# ------------------------------------------------------------------------------------------------
# CSV
# ------------------------------------------------------------------------------------------------


def test_csv_column_aliases_are_matched_loosely():
    text = "Time,Heart Rate,Speed\n0,120,2.5\n1,121,2.5\n2,122,2.6\n"
    rec, _ = recording_from_csv(text, age=30, hr_rest=55)
    assert [s.hr_bpm for s in rec.samples] == [120, 121, 122]
    assert rec.samples[0].speed_m_s == pytest.approx(2.5)


def test_csv_accepts_pace_in_place_of_speed():
    text = "t,hr,pace\n0,140,300\n1,141,300\n"
    rec, _ = recording_from_csv(text, age=30, hr_rest=55)
    # 300 s/km is 3.33 m/s.
    assert rec.samples[0].speed_m_s == pytest.approx(1000.0 / 300.0)


def test_csv_without_heart_rate_is_rejected():
    with pytest.raises(ValueError, match="heart-rate"):
        recording_from_csv("t,speed\n0,2.5\n", age=30, hr_rest=55)


def test_csv_missing_time_column_assumes_one_hertz_and_says_so():
    _, warnings = recording_from_csv("hr,speed\n140,2.5\n141,2.5\n", age=30, hr_rest=55)
    assert any("one second apart" in w for w in warnings)


def test_load_any_dispatches_on_content_not_extension(tmp_path):
    """A TCX file called .txt is still a TCX file."""
    p = tmp_path / "activity.txt"
    p.write_text(_tcx(_ramp_points()))
    rec, _ = load_any(p, age=30, hr_rest=55)
    assert len(rec.samples) == 1740


def test_a_poor_fit_produces_no_paces_rather_than_absurd_ones():
    """Found by importing an ordinary outdoor run.

    The stage segmenter found apparent plateaus in variable-pace running, the fit came back at
    r2 = 0.31, and the engine printed a Z1 recovery pace of "122:14 per kilometre" — with a caveat
    beside it saying the fit was poor. A caveat beside an absurd number is not a safeguard: somebody
    reads the number and not the caveat, and a saved profile carries the number forward long after
    the caveat has scrolled away. Below the threshold, no paces are derived at all.
    """
    from marathon_engine.assessment import MIN_FIT_R2_FOR_PACES, hr_derived_paces
    from marathon_engine.physiology import five_zone_model

    zones = five_zone_model(hr_max=187, hr_rest=55)
    good = hr_derived_paces((12.0, 55.0, 0.99), zones, 187, 55)
    bad = hr_derived_paces((6.6, 100.0, 0.31), zones, 187, 55)

    assert good, "a clean fit should still yield paces"
    assert bad == {}, "an unusable fit must yield nothing, not implausible numbers"
    assert 0.31 < MIN_FIT_R2_FOR_PACES <= 0.90


def test_no_derived_pace_is_ever_slower_than_a_walk():
    """The property behind the threshold, stated directly."""
    from marathon_engine.assessment import hr_derived_paces
    from marathon_engine.physiology import five_zone_model

    zones = five_zone_model(hr_max=187, hr_rest=55)
    for r2 in (0.31, 0.5, 0.74, 0.76, 0.9, 0.99):
        for slope in (5.0, 8.0, 12.0, 16.0):
            paces = hr_derived_paces((slope, 55.0, r2), zones, 187, 55)
            for name, (fast, slow) in paces.items():
                assert slow < 1200, f"{name} at r2={r2}, slope={slope} gave {slow:.0f} s/km"
