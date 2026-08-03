"""Ingest a full-data calibration recording and derive everything the plan needs from it.

This is the "record one session with every stream on, then hand it over" path. It exists because a
single richly-instrumented session is worth more than weeks of thin data, and because the Verity
Sense supports offline recording of every stream at once -- so the recording can be made without the
phone in the loop, then fetched and analysed afterwards.

What a calibration recording gives us that the normal path does not
-------------------------------------------------------------------
* **PPG at 135-176 Hz and PPI together are impossible**, but a recording can capture PPG raw and let
  us see the actual signal quality rather than inferring it from the device's summary. Mostly this
  tells us whether the strap position is good enough to trust.
* **Gyroscope**, which the streaming path does not need but which materially improves gait analysis:
  arm-swing rotation is a cleaner periodic signal than acceleration magnitude, so cadence and
  stride-to-stride variability come out less noisy.
* **A dense HR/speed sweep**, if the session is run as the graded protocol below, giving a much
  better-conditioned fit than five 4-minute stages.
* **Ground truth for the artifact detectors.** With the full record we can measure how often the
  device froze HR, locked to cadence, or dropped out on *your* arm at *your* paces, and tune the
  thresholds to you instead of to the population.

What an arm-worn sensor honestly cannot give
--------------------------------------------
Be clear about this, because running-dynamics marketing implies otherwise. From the **upper arm**:

* **Cadence: reliable.** Arm swing is 1:1 with stride, so step rate is straightforward.
* **Stride-to-stride variability: reliable enough to be useful.** Rising variability within a run is
  a decent fatigue marker.
* **Ground contact time, vertical oscillation, and left/right balance: not reliable.** These need a
  torso or foot sensor. An arm-mounted device can produce numbers that *correlate* with them, and
  those numbers will move with fatigue and speed, but they are proxies for arm mechanics, not for what
  the foot is doing. We compute an arm-swing asymmetry index because it is genuinely informative about
  *fatigue and compensation*, and we deliberately do not call it a gait asymmetry measurement.

The protocol
------------
:func:`calibration_protocol` returns the session to run. It is the graded ramp with more stages and a
longer steady block on the end, because the steady block is what yields drift, decoupling and the
efficiency-factor baseline -- the three numbers that later tell you whether you are getting fitter.

Pure functions; no I/O. The iOS app writes the JSON, this reads it.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from marathon_engine.assessment import (
    FitnessProfile, RampStage, RampTest, fit_hr_speed, hr_at_speed, profile_from_ramp, speed_at_hr,
)
from marathon_engine.physiology import (
    decoupling, efficiency_factor, fmt_pace, hr_at_reserve_fraction, reserve_fraction_at_hr,
    speed_to_pace,
)
from marathon_engine.signal_quality import (
    FROZEN_HR_MOVEMENT_SPM, MAX_ARTIFACT_FRACTION, cadence_lock_suspicion, clean_intervals,
    frozen_hr_suspicion, HrSample, rmssd,
)

__all__ = [
    "CalibrationRecording", "RecordingSample", "SensorHealth", "GaitSummary",
    "CalibrationResult", "analyse_recording", "calibration_protocol", "load_recording",
    "SCHEMA_VERSION", "STEADY_BLOCK_MIN",
]

SCHEMA_VERSION = 1

#: Length of the steady block at the end of the calibration session. 20 minutes is the minimum that
#: gives a trustworthy decoupling figure -- below about 15 the number is dominated by the warm-up
#: transient and is noise.
STEADY_BLOCK_MIN = 20.0


@dataclass
class RecordingSample:
    """One second of a recording. Every field optional, because streams start at different times."""
    t_s: float
    hr_bpm: Optional[float] = None
    speed_m_s: Optional[float] = None
    cadence_spm: Optional[float] = None
    grade: float = 0.0
    #: SD of accelerometer magnitude over this second, in g.
    accel_sd_g: Optional[float] = None
    #: Peak-to-peak gyroscope magnitude over this second, deg/s. Arm-swing amplitude proxy.
    gyro_p2p_dps: Optional[float] = None
    #: Interval between successive arm-swing peaks, ms. Used for stride variability.
    swing_interval_ms: Optional[float] = None
    label: str = ""          # "stage_1", "steady", "warmup", ...


@dataclass
class CalibrationRecording:
    """A full-data session as exported by the app."""
    started_at: datetime
    age: float
    hr_rest: float
    samples: List[RecordingSample]
    #: Beat intervals from PPI, if a resting block was recorded. Not available during running:
    #: enabling PPI throttles HR to one update per 5 s, so it is never on during the moving part.
    resting_ppi_ms: List[float] = field(default_factory=list)
    resting_ppi_blockers: List[bool] = field(default_factory=list)
    temp_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    surface: str = "treadmill"
    strap_position: str = "upper_arm"
    device_firmware: str = ""
    notes: str = ""
    schema_version: int = SCHEMA_VERSION


def load_recording(payload: Dict[str, Any]) -> CalibrationRecording:
    """Parse the app's JSON export. Tolerant of missing optional fields, strict about the required."""
    v = int(payload.get("schema_version", 0))
    if v != SCHEMA_VERSION:
        raise ValueError(f"unsupported recording schema version {v} (expected {SCHEMA_VERSION})")
    for key in ("started_at", "age", "hr_rest", "samples"):
        if key not in payload:
            raise ValueError(f"recording missing required field {key!r}")
    samples = [RecordingSample(**{k: s[k] for k in s if k in RecordingSample.__annotations__})
               for s in payload["samples"]]
    return CalibrationRecording(
        started_at=datetime.fromisoformat(payload["started_at"]),
        age=float(payload["age"]), hr_rest=float(payload["hr_rest"]), samples=samples,
        resting_ppi_ms=list(payload.get("resting_ppi_ms", [])),
        resting_ppi_blockers=list(payload.get("resting_ppi_blockers", [])),
        temp_c=payload.get("temp_c"), humidity_pct=payload.get("humidity_pct"),
        surface=payload.get("surface", "treadmill"),
        strap_position=payload.get("strap_position", "upper_arm"),
        device_firmware=payload.get("device_firmware", ""),
        notes=payload.get("notes", ""), schema_version=v)


# ----------------------------------------------------------------------------------------
# Sensor health
# ----------------------------------------------------------------------------------------


@dataclass
class SensorHealth:
    """How well the armband actually behaved, on this arm, at these paces."""
    samples: int
    hr_coverage: float                  # fraction of seconds with an HR value
    frozen_seconds: float
    frozen_fraction: float
    cadence_lock_seconds: float
    dropout_seconds: float
    ppi_artifact_fraction: Optional[float]
    verdict: str                        # good | usable | poor
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"samples": self.samples, "hr_coverage": round(self.hr_coverage, 3),
                "frozen_seconds": round(self.frozen_seconds, 1),
                "frozen_fraction": round(self.frozen_fraction, 3),
                "cadence_lock_seconds": round(self.cadence_lock_seconds, 1),
                "dropout_seconds": round(self.dropout_seconds, 1),
                "ppi_artifact_fraction": (round(self.ppi_artifact_fraction, 3)
                                          if self.ppi_artifact_fraction is not None else None),
                "verdict": self.verdict, "findings": self.findings}


def _sensor_health(rec: CalibrationRecording) -> SensorHealth:
    n = len(rec.samples)
    with_hr = [s for s in rec.samples if s.hr_bpm is not None]

    # Coverage is measured against the elapsed span, NOT against the number of rows present.
    #
    # Those differ whenever a recorder omits seconds rather than writing nulls for them, which is
    # what the Web Bluetooth logger does when the armband goes out of range -- deliberately, because
    # a gap is honest and a repeated last value is undetectable fabrication. But dividing by the row
    # count then made that honesty invisible: a session with a two-minute hole reported 100% coverage
    # and zero dropout, because every row that existed did have a heart rate.
    #
    # The consequence was not cosmetic. Coverage gates whether the run contributes training load at
    # all, so a recording that lost half its data would have been treated as complete.
    span = 0.0
    if rec.samples:
        times = [s.t_s for s in rec.samples]
        span = max(times) - min(times) + 1.0
    expected = max(float(n), span)
    coverage = len(with_hr) / expected if expected else 0.0

    # Frozen: runs of bit-identical HR while moving.
    frozen_s = 0.0
    run_len = 0
    for i, s in enumerate(rec.samples):
        prev = rec.samples[i - 1] if i else None
        moving = (s.cadence_spm or 0) >= FROZEN_HR_MOVEMENT_SPM
        if prev and s.hr_bpm is not None and prev.hr_bpm == s.hr_bpm and moving:
            run_len += 1
        else:
            if run_len >= 8:
                frozen_s += run_len
            run_len = 0
    if run_len >= 8:
        frozen_s += run_len

    # Cadence lock: evaluate in 60 s windows.
    lock_s = 0.0
    window: List[HrSample] = []
    for s in rec.samples:
        if s.hr_bpm is None:
            continue
        window.append(HrSample(t_s=s.t_s, hr_bpm=s.hr_bpm, cadence_spm=s.cadence_spm))
        window = [w for w in window if w.t_s >= s.t_s - 60]
        if len(window) >= 20 and cadence_lock_suspicion(window) >= 0.8:
            lock_s += 1

    dropout_s = max(0.0, expected - len(with_hr))

    ppi_frac: Optional[float] = None
    if rec.resting_ppi_ms:
        blockers = rec.resting_ppi_blockers or None
        _, counts = clean_intervals(rec.resting_ppi_ms, blockers=blockers)
        ppi_frac = 1.0 - counts["kept"] / counts["total"] if counts["total"] else None

    frozen_frac = frozen_s / n if n else 0.0
    findings: List[str] = []
    if coverage < 0.9:
        findings.append(f"Heart rate was missing for {(1-coverage)*100:.0f}% of the session. On this "
                        "device that usually means strap position or tightness -- it wants to be snug "
                        "on the upper arm, not the forearm.")
    if frozen_frac > 0.05:
        findings.append(
            f"Heart rate was frozen at a stale value for {frozen_s:.0f} s ({frozen_frac*100:.0f}% of "
            "the session). Polar documents this: when the device detects movement it holds the last "
            "reliable value rather than reporting a gap. It looks like clean data, which is exactly "
            "why it has to be measured. Above about 10% the real-time heart-rate coaching is not "
            "trustworthy and the plan should lean on pace and effort instead.")
    if lock_s > 60:
        findings.append(f"Heart rate tracked step rate for about {lock_s:.0f} s. Re-seat the strap and "
                        "consider a chest strap for interval sessions specifically.")
    if ppi_frac is not None and ppi_frac > MAX_ARTIFACT_FRACTION:
        findings.append(f"{ppi_frac*100:.0f}% of resting beat intervals were rejected, above the 5% "
                        "ceiling that short-term HRV needs. The nightly HRV baseline will be noisy "
                        "until the strap fit improves.")

    if coverage >= 0.95 and frozen_frac <= 0.02 and lock_s <= 30:
        verdict = "good"
    elif coverage >= 0.85 and frozen_frac <= 0.10:
        verdict = "usable"
    else:
        verdict = "poor"
    if verdict == "good":
        findings.append("Sensor behaved well throughout. Heart-rate-led coaching is trustworthy.")
    return SensorHealth(samples=n, hr_coverage=coverage, frozen_seconds=frozen_s,
                        frozen_fraction=frozen_frac, cadence_lock_seconds=lock_s,
                        dropout_seconds=dropout_s, ppi_artifact_fraction=ppi_frac,
                        verdict=verdict, findings=findings)


# ----------------------------------------------------------------------------------------
# Gait
# ----------------------------------------------------------------------------------------


@dataclass
class GaitSummary:
    """What an upper-arm sensor can honestly say about how you run."""
    cadence_by_speed: Dict[float, float]
    cadence_overall: Optional[float]
    stride_variability_cv: Optional[float]
    swing_amplitude_change_pct: Optional[float]
    asymmetry_index: Optional[float]
    findings: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"cadence_by_speed": {str(k): round(v, 1) for k, v in self.cadence_by_speed.items()},
                "cadence_overall": (round(self.cadence_overall, 1)
                                    if self.cadence_overall else None),
                "stride_variability_cv": (round(self.stride_variability_cv, 4)
                                          if self.stride_variability_cv else None),
                "swing_amplitude_change_pct": (round(self.swing_amplitude_change_pct, 1)
                                               if self.swing_amplitude_change_pct is not None
                                               else None),
                "asymmetry_index": (round(self.asymmetry_index, 4)
                                    if self.asymmetry_index is not None else None),
                "findings": self.findings, "caveats": self.caveats}


def _gait(rec: CalibrationRecording) -> GaitSummary:
    by_speed: Dict[float, List[float]] = {}
    for s in rec.samples:
        if s.cadence_spm and s.speed_m_s and s.speed_m_s > 1.0:
            bucket = round(s.speed_m_s * 3.6 * 2) / 2      # 0.5 km/h buckets
            by_speed.setdefault(bucket, []).append(s.cadence_spm)
    cadence_by_speed = {k: statistics.fmean(v) for k, v in sorted(by_speed.items())
                        if len(v) >= 10}
    all_cad = [s.cadence_spm for s in rec.samples if s.cadence_spm]
    overall = statistics.fmean(all_cad) if all_cad else None

    intervals = [s.swing_interval_ms for s in rec.samples if s.swing_interval_ms]
    cv = None
    if len(intervals) > 20:
        m = statistics.fmean(intervals)
        cv = statistics.pstdev(intervals) / m if m > 0 else None

    # Arm-swing amplitude: first quarter vs last quarter of the moving portion.
    moving = [s for s in rec.samples if s.gyro_p2p_dps and (s.cadence_spm or 0) > 100]
    amp_change = None
    if len(moving) > 40:
        q = len(moving) // 4
        first = statistics.fmean([s.gyro_p2p_dps for s in moving[:q]])
        last = statistics.fmean([s.gyro_p2p_dps for s in moving[-q:]])
        if first > 0:
            amp_change = (last / first - 1.0) * 100.0

    # Asymmetry: alternating swing intervals. On a symmetric gait, consecutive intervals alternate
    # evenly; a limp or a dominant side produces a consistent long-short pattern.
    asym = None
    if len(intervals) > 40:
        odd = intervals[0::2]
        even = intervals[1::2]
        mo, me = statistics.fmean(odd), statistics.fmean(even)
        if mo + me > 0:
            asym = abs(mo - me) / ((mo + me) / 2)

    findings: List[str] = []
    if cadence_by_speed:
        lo = min(cadence_by_speed), max(cadence_by_speed)
        findings.append(
            "Cadence at each speed is recorded as your personal baseline. There is no target here: "
            "the '180 steps per minute' figure is a misreading of an observation of elite runners at "
            "race pace. What has evidence is a 5-10% increase from your OWN baseline reducing "
            "per-step load, which is why the baseline is what gets stored.")
    if cv is not None:
        if cv > 0.06:
            findings.append(f"Stride timing variability {cv*100:.1f}%. On the high side; it usually "
                            "falls as running becomes more practised, so this is a number to watch "
                            "rather than to act on.")
        else:
            findings.append(f"Stride timing variability {cv*100:.1f}% -- consistent.")
    if amp_change is not None and amp_change < -12:
        findings.append(f"Arm-swing amplitude fell {abs(amp_change):.0f}% from the start of the run "
                        "to the end. That is a fatigue signature worth tracking across sessions: if "
                        "it starts happening earlier in runs, the sessions are too long or too hard "
                        "for where you are.")
    if asym is not None and asym > 0.08:
        findings.append(f"Left/right swing timing differs by {asym*100:.0f}%. Worth mentioning if "
                        "anything starts to hurt on one side -- but see the caveat below before "
                        "reading anything into it.")

    caveats = [
        "Cadence and stride variability from an upper-arm sensor are trustworthy. Ground contact "
        "time, vertical oscillation and true left/right balance are NOT -- those need a torso or "
        "foot sensor, and any number an arm-mounted device produces for them describes arm mechanics "
        "rather than what your foot is doing.",
        "The asymmetry index above is an arm-swing timing measure. It is genuinely useful as a "
        "fatigue and compensation signal, and it is not a gait analysis.",
    ]
    return GaitSummary(cadence_by_speed=cadence_by_speed, cadence_overall=overall,
                       stride_variability_cv=cv, swing_amplitude_change_pct=amp_change,
                       asymmetry_index=asym, findings=findings, caveats=caveats)


# ----------------------------------------------------------------------------------------
# The analysis
# ----------------------------------------------------------------------------------------


@dataclass
class CalibrationResult:
    profile: Optional[FitnessProfile]
    sensor: SensorHealth
    gait: GaitSummary
    stages: List[Dict[str, Any]]
    steady: Optional[Dict[str, Any]]
    observed_hr_max: Optional[float]
    warnings: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"profile": self.profile.to_dict() if self.profile else None,
                "sensor": self.sensor.to_dict(), "gait": self.gait.to_dict(),
                "stages": self.stages, "steady": self.steady,
                "observed_hr_max": (round(self.observed_hr_max, 1)
                                    if self.observed_hr_max else None),
                "warnings": self.warnings, "next_actions": self.next_actions}


def _stage_summaries(rec: CalibrationRecording) -> List[Dict[str, Any]]:
    """Summarise each labelled stage, using only the FINAL 60 s of each for the HR figure.

    The final-minute rule is not cosmetic: heart rate takes 2-3 minutes to plateau at a given
    submaximal speed, so a whole-stage mean systematically understates it, and the understatement is
    larger at higher speeds -- which biases the HR/speed slope shallow, which makes every derived
    pace too fast. Exactly the wrong direction.
    """
    stages: Dict[str, List[RecordingSample]] = {}
    for s in rec.samples:
        if s.label.startswith("stage"):
            stages.setdefault(s.label, []).append(s)
    out: List[Dict[str, Any]] = []
    for label, ss in sorted(stages.items()):
        ss.sort(key=lambda x: x.t_s)
        end = ss[-1].t_s
        tail = [x for x in ss if x.t_s >= end - 60 and x.hr_bpm]
        speeds = [x.speed_m_s for x in ss if x.speed_m_s]
        cads = [x.cadence_spm for x in ss if x.cadence_spm]
        if not tail or not speeds:
            continue
        out.append({
            "label": label,
            "speed_kmh": round(statistics.fmean(speeds) * 3.6, 2),
            "steady_hr": round(statistics.fmean([x.hr_bpm for x in tail]), 1),
            "duration_min": round((end - ss[0].t_s) / 60, 1),
            "cadence_spm": round(statistics.fmean(cads), 1) if cads else None,
            "samples_in_tail": len(tail),
        })
    return out


def _steady_summary(rec: CalibrationRecording) -> Optional[Dict[str, Any]]:
    """Decoupling, efficiency factor and drift over the steady block."""
    ss = [s for s in rec.samples if s.label == "steady" and s.hr_bpm and s.speed_m_s]
    if len(ss) < 600:      # need ~10 min of usable data before this means anything
        return None
    ss.sort(key=lambda x: x.t_s)
    mid = len(ss) // 2
    first = [(x.speed_m_s, x.hr_bpm) for x in ss[:mid]]
    second = [(x.speed_m_s, x.hr_bpm) for x in ss[mid:]]
    try:
        dec = decoupling(first, second)
    except ValueError:
        return None
    mean_speed = statistics.fmean([x.speed_m_s for x in ss])
    mean_hr = statistics.fmean([x.hr_bpm for x in ss])
    dur = (ss[-1].t_s - ss[0].t_s) / 60
    return {
        "duration_min": round(dur, 1),
        "mean_speed_kmh": round(mean_speed * 3.6, 2),
        "mean_pace": fmt_pace(speed_to_pace(mean_speed)),
        "mean_hr": round(mean_hr, 1),
        "efficiency_factor": round(efficiency_factor(mean_speed, mean_hr), 2),
        "decoupling": round(dec, 4),
        "decoupling_pct": round(dec * 100, 1),
        "interpretation": (
            "Under 5% -- that effort was genuinely aerobic and sustainable, which is what makes it a "
            "valid reference for your easy pace."
            if dec < 0.05 else
            f"{dec*100:.0f}% -- heart rate drifted relative to pace, so that pace was above what you "
            "can hold aerobically for this duration. Not a problem, but it means your easy pace "
            "should sit slower than this block, and the plan will set it there."),
    }


def analyse_recording(rec: CalibrationRecording) -> CalibrationResult:
    """Turn a calibration recording into a fitness profile plus an honest data-quality report."""
    sensor = _sensor_health(rec)
    gait = _gait(rec)
    stages = _stage_summaries(rec)
    steady = _steady_summary(rec)

    hrs = [s.hr_bpm for s in rec.samples if s.hr_bpm]
    observed_max = max(hrs) if hrs else None

    warnings: List[str] = []
    actions: List[str] = []
    profile: Optional[FitnessProfile] = None

    if len(stages) >= 3:
        ramp_stages = [
            RampStage(speed_kmh=st["speed_kmh"], steady_hr=st["steady_hr"],
                      cadence_spm=st["cadence_spm"], duration_min=st["duration_min"])
            for st in stages
        ]
        # The talk test is a subjective field the recording cannot contain, so it must be supplied
        # separately. Without it the seed VDOT falls back to HR/speed extrapolation, which is why the
        # protocol asks for it explicitly.
        ramp = RampTest(day=rec.started_at.date(), stages=ramp_stages, hr_rest=rec.hr_rest,
                        age=rec.age, surface=rec.surface, temp_c=rec.temp_c,
                        notes=f"from calibration recording; {rec.notes}")
        try:
            profile = profile_from_ramp(ramp)
        except ValueError as e:
            warnings.append(f"Could not derive a profile from the stages: {e}")
    else:
        warnings.append(f"Only {len(stages)} usable stages found (need 3). Was the session run as "
                        "the graded protocol, with each stage labelled?")

    if sensor.verdict == "poor":
        warnings.append("Sensor data quality was poor, so every number derived from heart rate here "
                        "is suspect. Fix the strap fit and re-record before trusting the zones.")
        actions.append("Re-record after moving the strap higher on the upper arm and tightening it "
                       "one notch. Cold skin also hurts -- warm up indoors for five minutes first.")
    if sensor.frozen_fraction > 0.10:
        actions.append("Given how often heart rate froze, consider a Polar H10 chest strap for "
                       "interval sessions. It is a different sensing modality (electrical, not "
                       "optical), it does not have this failure mode, and the app already speaks its "
                       "protocol -- the standard heart-rate service path works unchanged.")
    if steady is None:
        actions.append(f"Add a steady block of at least {STEADY_BLOCK_MIN:.0f} minutes at a "
                       "conversational pace, labelled 'steady'. It is the only part of the session "
                       "that yields decoupling and the efficiency-factor baseline, which are the two "
                       "numbers that later show whether you are getting fitter.")
    if observed_max and profile and observed_max > profile.hr_max:
        actions.append(f"Observed heart rate reached {observed_max:.0f}, above the age-predicted "
                       f"{profile.hr_max:.0f}. The observed value wins -- zones have been rebuilt "
                       "around it.")
    actions.append("Send this file over and the plan gets rebuilt from it: zones, paces, the seed "
                   "VDOT, your cadence baseline, and the sensor-quality caveats that decide how much "
                   "the real-time coaching should trust heart rate at all.")

    return CalibrationResult(profile=profile, sensor=sensor, gait=gait, stages=stages,
                             steady=steady, observed_hr_max=observed_max,
                             warnings=warnings, next_actions=actions)


#: Default top stage of the ramp, for an athlete nothing is known about.
DEFAULT_TOP_STAGE_KMH = 10.0

#: A hole longer than this ends a continuous segment. Three seconds tolerates ordinary jitter in a
#: 1 Hz stream without letting a real dropout be papered over.
SEGMENT_MAX_GAP_S = 3.0

#: Margin below the fastest speed an athlete was observed to sustain under the stop threshold.
#:
#: A ramp accumulates fatigue: by the last stage you have been going for twenty-odd minutes, so a
#: speed that sat comfortably under the ceiling when fresh will not by then. Half a km/h is the
#: smallest step a treadmill offers and is enough to keep the final stage inside the protocol.
TOP_STAGE_MARGIN_KMH = 0.5


def top_stage_from_run(samples: Sequence[RecordingSample], *, hr_max: float,
                       hr_rest: float) -> Optional[float]:
    """The fastest speed this athlete held for a minute with heart rate still under the stop rule.

    Why this is worth doing: the default ladder runs to 10 km/h, which is a guess about a stranger.
    If the athlete's own data says they cross 85% of heart-rate reserve well below that, the last two
    stages of the default ramp will trigger the stop rule and never be recorded -- and a ramp that
    ends early gives fewer points to fit a line through, in the range where the line matters most.
    Shifting the whole ladder down converts a test that aborts into one that completes.

    Returns ``None`` when the data cannot support a judgement, which is the common case: this needs
    at least one continuous minute of running, and an ordinary run may not contain one.
    """
    stop_hr = hr_at_reserve_fraction(0.85, hr_max, hr_rest)
    ordered = sorted(samples, key=lambda x: x.t_s)
    best: Optional[float] = None
    run: List[RecordingSample] = []
    for x in ordered:
        running = x.speed_m_s is not None and x.speed_m_s >= 1.9 and x.hr_bpm is not None
        # A gap in the timeline ends a segment as surely as a walk does. Without this, six thirty-
        # second bursts with thirty-second holes between them read as one continuous three-minute
        # run -- and "held for three minutes" is the entire claim this function makes. Missing
        # seconds are now common by design: the Web Bluetooth logger omits them rather than
        # repeating a stale heart rate.
        gapped = bool(run) and (x.t_s - run[-1].t_s) > SEGMENT_MAX_GAP_S
        if running and not gapped:
            run.append(x)
            continue
        best = _consider_segment(run, stop_hr, best)
        run = [x] if running else []
    best = _consider_segment(run, stop_hr, best)
    return best


def _consider_segment(seg: List[RecordingSample], stop_hr: float,
                      best: Optional[float]) -> Optional[float]:
    """Judge one continuous running segment on its final 30 s, which is the closest it gets to
    settled. Anything shorter than a minute has not begun to settle and is ignored."""
    if len(seg) < 60:
        return best
    tail = [x.hr_bpm for x in seg[-30:] if x.hr_bpm]
    if not tail or statistics.fmean(tail) >= stop_hr:
        return best
    speeds = [x.speed_m_s for x in seg if x.speed_m_s]
    if not speeds:
        return best
    kmh = statistics.fmean(speeds) * 3.6
    return kmh if best is None else max(best, kmh)


def calibration_protocol(age: float, hr_rest: float, *,
                         top_stage_kmh: Optional[float] = None) -> Dict[str, Any]:
    """The session to record. About 55 minutes including warm-up and the steady block.

    ``top_stage_kmh`` tailors the ladder to an athlete whose ceiling is already roughly known --
    see :func:`top_stage_from_run`. The six stages then descend from it in 1 km/h steps, which keeps
    the spread the fit needs while ensuring the last stage is one the athlete can actually complete.
    """
    from marathon_engine.physiology import hr_max_estimate
    hr_max = hr_max_estimate(age)
    stop_hr = hr_at_reserve_fraction(0.85, hr_max, hr_rest)

    top = DEFAULT_TOP_STAGE_KMH if top_stage_kmh is None else max(6.0, round(top_stage_kmh * 2) / 2)
    ladder = [round(top - (5 - i), 1) for i in range(6)]
    # Never prescribe a stage slower than a slow walk; below about 3.5 km/h the relationship between
    # speed and heart rate is dominated by standing metabolism rather than by locomotion.
    ladder = [v for v in ladder if v >= 3.5]

    stages = []
    for i, kmh in enumerate(ladder, start=1):
        stages.append({"label": f"stage_{i}", "speed_kmh": kmh,
                       "pace_per_km": fmt_pace(3600.0 / kmh), "duration_min": 4,
                       "mode": "walk" if kmh <= 6.5 else "jog"})
    return {
        "total_min": 5 + len(stages) * 4 + 5 + STEADY_BLOCK_MIN,
        "device_setup": [
            "Charge the armband fully. Wear it on the UPPER arm, snug -- one notch tighter than feels "
            "necessary. Forearm placement is materially worse on this device.",
            "Warm your skin up first: five minutes indoors. Cold skin is a common cause of poor "
            "optical signal at the start of a run.",
            "Start an offline recording with ACC, GYRO and PPG enabled. Do NOT enable PPI: it "
            "throttles heart rate to one update every five seconds and aborts any ongoing training, "
            "which makes the moving part of the session useless for this purpose.",
            "Record the resting PPI block SEPARATELY, before you start moving (see below).",
        ],
        "resting_block": {
            "when": "First, before any movement.",
            "what": "5 minutes lying supine, then 2 minutes standing still.",
            "streams": "PPI only (this is the one time PPI is the right stream).",
            "why": ("Yields resting heart rate, supine RMSSD, and the orthostatic rise -- the anchors "
                    "the nightly HRV baseline is compared against. It has to be a separate recording "
                    "because PPI and useful moving data are mutually exclusive on this device."),
        },
        "warmup": "5 minutes easy walking at 4.5 km/h.",
        "stages": stages,
        "at_each_stage": [
            "Keep the speed constant for the full 4 minutes -- the last minute is the only part that "
            "gets used, because heart rate needs 2-3 minutes to plateau.",
            "At the end of each stage, say a full sentence aloud and note whether it was comfortable, "
            "effortful, or impossible. Write it down; the recording cannot capture it, and it is the "
            "single most informative number in the whole session.",
            "Note your Borg 6-20 effort rating too.",
        ],
        "stop_when_any": [
            f"Heart rate reaches {stop_hr:.0f} bpm (85% of heart-rate reserve)",
            "Effort reaches 15/20",
            "Speech becomes impossible",
            "Anything feels wrong -- stop immediately",
        ],
        "steady_block": {
            "when": "After a 5-minute walk recovery from the last stage.",
            "what": f"{STEADY_BLOCK_MIN:.0f} minutes at the fastest speed where you were still "
                    "COMFORTABLE talking. Label this block 'steady'.",
            "why": ("This is the most valuable single block in the session. It yields aerobic "
                    "decoupling (does heart rate drift at constant pace?), the efficiency-factor "
                    "baseline that every future re-test is compared against, and a real-world check "
                    "on whether the pace the stages suggested is actually sustainable."),
        },
        "cooldown": "5 minutes walking, then stand still for 60 seconds and note your heart rate.",
        "afterwards": [
            "Stop the recording and put the device in sensor mode (the heart symbol, blue side LED). "
            "File transfer is blocked while it is in recording or swimming mode -- it will return a "
            "SYSTEM_BUSY error, which is the device protecting you from syncing a session that is "
            "still running.",
            "Fetch the recording, export it as JSON, and hand it over with your talk-test and effort "
            "notes.",
        ],
        "notes": [
            "Also record the temperature and whether it was a treadmill or road. Heat moves "
            "submaximal heart rate by several beats on its own, and a re-test in different conditions "
            "is not comparable.",
            "If you can only do part of this, the stages matter most and the steady block second. "
            "Three good stages are enough to derive zones.",
        ],
    }
