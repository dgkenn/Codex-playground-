"""Turn what Polar Flow will actually give you into what the engine needs.

Why this module exists
----------------------
:mod:`marathon_engine.calibration` consumes a JSON recording in the app's own schema -- one sample per
second, with accelerometer and gyroscope alongside heart rate. That schema is the right one, and if
the iPhone app is running it is what you get.

Without the app there is no such file. What there *is*, on day one, is Polar's own Flow app, which
pairs with the Verity Sense, records a session, and exports **TCX** -- an XML format carrying a
timestamped trackpoint every second or two with heart rate, cumulative distance and altitude. That is
strictly less than the app's schema. It is also enough for the single most valuable thing week 1 was
going to do anyway: fit the line relating heart rate to speed, which becomes both the prescription
basis and the in-run controller's feedforward gain.

So this module reads what exists rather than waiting for what doesn't.

What is lost, and what that costs
---------------------------------
TCX has no accelerometer and no gyroscope. Three things therefore cannot be derived from it:

* **Gait metrics** -- arm-swing amplitude and stride variability come from GYRO.
* **The not-worn and cadence-lock detectors** -- both need accelerometer variance to distinguish a
  band that has slipped from a genuinely steady pulse.
* **Cadence**, unless the export happens to carry it (Polar sometimes does, via the Garmin activity
  extension; parsed opportunistically below).

The consequence is stated plainly in :func:`recording_from_tcx`'s ``notes`` and carried into the
:class:`~marathon_engine.calibration.CalibrationResult`: sensor-health scoring on an import is
*partial*, and a clean result means "nothing detectable in this data was wrong", not "the band
behaved". That distinction matters enough to survive into the output rather than living only here.

Speed
-----
TCX gives cumulative distance, not speed. Differentiating a noisy cumulative distance sample-by-sample
produces garbage, so speed is computed over a centred window (default 15 s) and then only where the
time base is sane. A GPS distance series that jumps backwards -- which happens -- yields no speed for
that span rather than a negative one.
"""

from __future__ import annotations

import csv
import io
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from marathon_engine.calibration import (SCHEMA_VERSION, CalibrationRecording, RecordingSample)

__all__ = ["recording_from_tcx", "recording_from_csv", "load_any", "ImportWarning_"]

#: Window over which distance is differentiated to get speed. Short enough to see a stage change in a
#: ramp, long enough that GPS jitter does not dominate.
SPEED_WINDOW_S = 15.0

#: A speed above this is not a person running; it is a bad fix. Marathon world record pace is about
#: 5.8 m/s, so 8.0 leaves generous room while still catching a teleport.
MAX_PLAUSIBLE_SPEED_M_S = 8.0

_TCX_NS = {
    "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ext": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
}


class ImportWarning_(str):
    """A note about something the import could not do. Subclasses ``str`` so it prints plainly."""


# ------------------------------------------------------------------------------------------------
# TCX
# ------------------------------------------------------------------------------------------------


def _parse_time(text: str) -> datetime:
    """Parse a TCX timestamp. Tolerates the ``Z`` suffix and fractional seconds."""
    t = text.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    # Some exporters emit more than six fractional digits, which fromisoformat rejects.
    t = re.sub(r"\.(\d{6})\d+", r".\1", t)
    dt = datetime.fromisoformat(t)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _speeds_from_distance(times: Sequence[float], dists: Sequence[Optional[float]],
                          window_s: float = SPEED_WINDOW_S) -> List[Optional[float]]:
    """Centred-difference speed from cumulative distance.

    Returns ``None`` wherever a trustworthy speed cannot be formed: no distance at either end of the
    window, a non-positive time base, a distance that went backwards, or a result that is not a speed
    a human produces.
    """
    n = len(times)
    out: List[Optional[float]] = [None] * n
    if n < 2:
        return out
    half = window_s / 2.0
    lo = 0
    hi = 0
    for i in range(n):
        while lo < n and times[lo] < times[i] - half:
            lo += 1
        while hi < n - 1 and times[hi + 1] <= times[i] + half:
            hi += 1
        a, b = max(0, lo - 1 if times[lo] > times[i] - half and lo > 0 else lo), hi
        if b <= a:
            continue
        d0, d1 = dists[a], dists[b]
        dt = times[b] - times[a]
        if d0 is None or d1 is None or dt <= 0:
            continue
        dd = d1 - d0
        if dd < 0:                       # cumulative distance must not decrease
            continue
        v = dd / dt
        if v > MAX_PLAUSIBLE_SPEED_M_S:  # a bad fix, not a sprint
            continue
        out[i] = v
    return out


def _grades_from_altitude(times: Sequence[float], alts: Sequence[Optional[float]],
                          dists: Sequence[Optional[float]]) -> List[float]:
    """Grade over the same window as speed, clamped to what a road actually does.

    Barometric and GPS altitude are both noisy enough that an unclamped grade from consecutive
    samples routinely reads +/-40%, which would make the Minetti adjustment produce nonsense.
    """
    n = len(times)
    out = [0.0] * n
    half = SPEED_WINDOW_S / 2.0
    for i in range(n):
        a = i
        b = i
        while a > 0 and times[a] > times[i] - half:
            a -= 1
        while b < n - 1 and times[b] < times[i] + half:
            b += 1
        if b <= a or alts[a] is None or alts[b] is None or dists[a] is None or dists[b] is None:
            continue
        run = dists[b] - dists[a]
        if run < 5.0:                    # too short a base to divide by
            continue
        g = (alts[b] - alts[a]) / run
        out[i] = max(-0.30, min(0.30, g))
    return out


def recording_from_tcx(text: str, *, age: float, hr_rest: float,
                       surface: str = "road") -> Tuple[CalibrationRecording, List[ImportWarning_]]:
    """Parse a Polar Flow (or any Garmin-compatible) TCX export into a recording.

    Returns the recording and a list of warnings describing what could not be recovered. The warnings
    are not decoration: they are the difference between "the band was fine" and "nothing in this
    file could show that the band was not fine", and the caller is expected to surface them.
    """
    warnings: List[ImportWarning_] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"not parseable as XML: {exc}") from exc

    points = root.findall(".//tcx:Trackpoint", _TCX_NS)
    if not points:
        # Some exporters omit the namespace entirely.
        points = root.findall(".//Trackpoint")
        if not points:
            raise ValueError("no <Trackpoint> elements found -- is this a TCX file?")
        ns_prefix = ""
    else:
        ns_prefix = "tcx:"

    def find(el, path):
        return el.find(f"{ns_prefix}{path}", _TCX_NS if ns_prefix else None)

    raw: List[Tuple[datetime, Optional[float], Optional[float], Optional[float], Optional[float]]] = []
    for p in points:
        t_el = find(p, "Time")
        if t_el is None or not t_el.text:
            continue
        try:
            when = _parse_time(t_el.text)
        except ValueError:
            continue

        def num(path: str) -> Optional[float]:
            el = find(p, path)
            if el is None or el.text is None:
                return None
            try:
                return float(el.text)
            except ValueError:
                return None

        hr = None
        hr_el = find(p, "HeartRateBpm")
        if hr_el is not None:
            v = hr_el.find(f"{ns_prefix}Value", _TCX_NS if ns_prefix else None)
            if v is not None and v.text:
                try:
                    hr = float(v.text)
                except ValueError:
                    hr = None

        # Cadence, if the exporter bothered. Polar writes running cadence as the Garmin activity
        # extension RunCadence, in strides per minute -- doubled to give steps per minute, which is
        # the unit everything else in this codebase uses.
        cad = None
        for ext_path in (".//ext:RunCadence", ".//ext:Cadence"):
            el = p.find(ext_path, _TCX_NS)
            if el is not None and el.text:
                try:
                    cad = float(el.text) * 2.0
                except ValueError:
                    cad = None
                break
        if cad is None:
            c_el = find(p, "Cadence")
            if c_el is not None and c_el.text:
                try:
                    cad = float(c_el.text) * 2.0
                except ValueError:
                    cad = None

        raw.append((when, hr, num("DistanceMeters"), num("AltitudeMeters"), cad))

    if not raw:
        raise ValueError("TCX contained trackpoints but none had a usable timestamp")

    raw.sort(key=lambda r: r[0])
    started_at = raw[0][0]
    times = [(r[0] - started_at).total_seconds() for r in raw]
    hrs = [r[1] for r in raw]
    dists = [r[2] for r in raw]
    alts = [r[3] for r in raw]
    cads = [r[4] for r in raw]

    speeds = _speeds_from_distance(times, dists)
    grades = _grades_from_altitude(times, alts, dists)

    samples = [RecordingSample(t_s=t, hr_bpm=hr, speed_m_s=sp, cadence_spm=cad, grade=g,
                               accel_sd_g=None, gyro_p2p_dps=None, swing_interval_ms=None,
                               label="")
               for t, hr, sp, cad, g in zip(times, hrs, speeds, cads, grades)]

    if not any(s.hr_bpm is not None for s in samples):
        raise ValueError("no heart rate anywhere in this file -- nothing to calibrate from")
    if not any(s.speed_m_s is not None for s in samples):
        warnings.append(ImportWarning_(
            "No usable speed: the file has no distance track (an indoor session recorded without "
            "GPS does this). Heart rate alone cannot produce a HR-speed fit, so this import can "
            "give you a resting/peak heart rate and nothing else."))
    if not any(s.cadence_spm is not None for s in samples):
        warnings.append(ImportWarning_(
            "No cadence in the export. Beyond losing cadence-by-speed, this disables TWO of the "
            "sensor-fault detectors outright: both cadence lock-on and the frozen-heart-rate check "
            "need evidence that you were moving before a suspiciously steady pulse means anything. "
            "Without it a heart rate held at the last reliable value is indistinguishable from a "
            "person sitting still, so this recording cannot be checked for the failure Polar "
            "documents most explicitly."))
    warnings.append(ImportWarning_(
        "TCX carries no accelerometer or gyroscope. Gait metrics (arm-swing amplitude, stride "
        "variability) and the not-worn detector cannot run, so sensor health from this import is "
        "PARTIAL -- a clean result means nothing detectable here was wrong, not that the band "
        "behaved."))

    median_dt = _median([b - a for a, b in zip(times, times[1:])]) if len(times) > 1 else 1.0
    if median_dt > 3.0:
        warnings.append(ImportWarning_(
            f"Samples are {median_dt:.0f}s apart. Polar Flow's 'smart' recording rate throws away "
            "most of the data. Set the recording rate to 1 second in Flow before the next one."))

    rec = CalibrationRecording(
        started_at=started_at, age=age, hr_rest=hr_rest, samples=samples,
        resting_ppi_ms=[], resting_ppi_blockers=[],
        surface=surface, strap_position="upper_arm",
        notes=("Imported from TCX. No ACC/GYRO: sensor health and gait metrics are partial. "
               + " ".join(warnings)),
        schema_version=SCHEMA_VERSION)
    return rec, warnings


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


# ------------------------------------------------------------------------------------------------
# CSV
# ------------------------------------------------------------------------------------------------

#: Column aliases seen in the wild, lowercased and stripped of punctuation.
_CSV_ALIASES: Dict[str, Tuple[str, ...]] = {
    "t_s": ("time", "times", "elapsed", "seconds", "sec", "t", "timestamp"),
    "hr_bpm": ("hr", "heartrate", "heart rate", "hrbpm", "bpm", "heart_rate"),
    "speed_m_s": ("speed", "speedms", "velocity", "v"),
    "pace_sec_km": ("pace", "paceseckm", "pace_per_km"),
    "cadence_spm": ("cadence", "cad", "spm", "steps"),
    "grade": ("grade", "slope", "incline", "gradient"),
    "accel_sd_g": ("accsd", "accel_sd", "accelsd", "acc_sd_g"),
}


def _canonical(name: str) -> Optional[str]:
    key = re.sub(r"[^a-z ]", "", name.strip().lower())
    for canon, aliases in _CSV_ALIASES.items():
        if key == canon or key in aliases or key.replace(" ", "") in aliases:
            return canon
    return None


def recording_from_csv(text: str, *, age: float, hr_rest: float,
                       surface: str = "treadmill") -> Tuple[CalibrationRecording,
                                                            List[ImportWarning_]]:
    """Parse a generic per-sample CSV.

    The escape hatch. Column names are matched loosely against :data:`_CSV_ALIASES` so an export from
    a logger app, a spreadsheet you typed by hand off a treadmill display, or a Polar CSV all work
    without a bespoke parser each. Time may be elapsed seconds or an ISO timestamp; pace in sec/km is
    accepted in place of speed and converted.
    """
    warnings: List[ImportWarning_] = []
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("CSV has no data rows")

    header = rows[0]
    mapping: Dict[int, str] = {}
    for i, name in enumerate(header):
        canon = _canonical(name)
        if canon:
            mapping[i] = canon
    if "hr_bpm" not in mapping.values():
        raise ValueError(f"no heart-rate column found; saw headers {header!r}")
    if "t_s" not in mapping.values():
        warnings.append(ImportWarning_(
            "No time column, so samples are assumed to be one second apart in file order."))

    samples: List[RecordingSample] = []
    base_time: Optional[datetime] = None
    for n, row in enumerate(rows[1:]):
        vals: Dict[str, Optional[float]] = {}
        t_s: Optional[float] = None
        for i, canon in mapping.items():
            if i >= len(row):
                continue
            cell = row[i].strip()
            if not cell:
                continue
            if canon == "t_s":
                try:
                    t_s = float(cell)
                except ValueError:
                    try:
                        dt = _parse_time(cell)
                    except ValueError:
                        continue
                    if base_time is None:
                        base_time = dt
                    t_s = (dt - base_time).total_seconds()
                continue
            try:
                vals[canon] = float(cell)
            except ValueError:
                continue

        speed = vals.get("speed_m_s")
        if speed is None and vals.get("pace_sec_km"):
            p = vals["pace_sec_km"]
            speed = 1000.0 / p if p > 0 else None
        if speed is not None and (speed < 0 or speed > MAX_PLAUSIBLE_SPEED_M_S):
            speed = None

        samples.append(RecordingSample(
            t_s=float(n) if t_s is None else t_s,
            hr_bpm=vals.get("hr_bpm"), speed_m_s=speed,
            cadence_spm=vals.get("cadence_spm"), grade=vals.get("grade") or 0.0,
            accel_sd_g=vals.get("accel_sd_g")))

    if not any(s.hr_bpm is not None for s in samples):
        raise ValueError("heart-rate column found but every value was empty or non-numeric")

    if not any(s.accel_sd_g is not None for s in samples):
        warnings.append(ImportWarning_(
            "No accelerometer column, so the not-worn detector cannot run and sensor health is "
            "PARTIAL."))

    rec = CalibrationRecording(
        started_at=base_time or datetime.now(timezone.utc), age=age, hr_rest=hr_rest,
        samples=samples, surface=surface, strap_position="upper_arm",
        notes="Imported from CSV. " + " ".join(warnings), schema_version=SCHEMA_VERSION)
    return rec, warnings


# ------------------------------------------------------------------------------------------------
# Dispatch
# ------------------------------------------------------------------------------------------------


def load_any(path: str | Path, *, age: float, hr_rest: float,
             surface: str = "road") -> Tuple[CalibrationRecording, List[ImportWarning_]]:
    """Load a recording from a file, choosing the parser by content rather than by extension.

    Content rather than extension because a file called ``activity.txt`` that happens to be TCX
    should still work, and because a mislabelled extension is a common way to lose an afternoon.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    head = text.lstrip()[:400].lower()

    if head.startswith("<?xml") or "<trainingcenterdatabase" in head or "<trackpoint" in head:
        return recording_from_tcx(text, age=age, hr_rest=hr_rest, surface=surface)
    if "<gpx" in head:
        # GPX with the Garmin TrackPointExtension carries HR in the same shape; the TCX reader's
        # element names differ, so this is a genuinely separate format rather than a near-miss.
        raise ValueError(
            "GPX export detected. GPX carries route but Polar puts heart rate in an extension this "
            "importer does not read. Export TCX from flow.polar.com instead -- same session, and it "
            "carries heart rate and distance in the standard elements.")
    if p.suffix.lower() == ".json" or head.startswith("{"):
        import json
        from marathon_engine.calibration import load_recording
        return load_recording(json.loads(text)), []
    return recording_from_csv(text, age=age, hr_rest=hr_rest, surface=surface)


# ------------------------------------------------------------------------------------------------
# Stage segmentation
# ------------------------------------------------------------------------------------------------

#: A stage must hold a speed this steady (coefficient of variation) to count as a stage.
STAGE_MAX_CV = 0.08
#: And last at least this long, because the HR figure is taken from the final 60 s of each stage and
#: heart rate needs two to three minutes to plateau at a submaximal speed.
STAGE_MIN_S = 150.0
#: Two adjacent plateaus closer than this in speed are the same stage with noise between them.
STAGE_MERGE_M_S = 0.20


def label_stages(rec: CalibrationRecording, *, min_stage_s: float = STAGE_MIN_S) -> int:
    """Find the constant-speed plateaus in a recording and label them ``stage_1``, ``stage_2``, ...

    An imported file has no stage labels -- the app writes those while it is running the protocol,
    and there is no app here. Without labels :func:`~marathon_engine.calibration.analyse_recording`
    finds no stages, produces no HR-speed fit, and the import yields nothing of value. So the
    plateaus are recovered from the data.

    This is deliberately conservative. It marks a stage only where speed is genuinely steady for long
    enough that the final-minute heart rate means something, and it does not try to guess at ragged
    outdoor running. On a treadmill ramp it recovers the stages exactly. On a road run with variable
    pace it will usually find nothing, which is the correct answer -- a fit through speeds the athlete
    never held is worse than no fit.

    Modifies ``rec`` in place and returns the number of stages found.
    """
    samples = sorted(rec.samples, key=lambda s: s.t_s)
    usable = [s for s in samples if s.speed_m_s is not None]
    if len(usable) < int(min_stage_s):
        return 0

    # Walk forward, extending a run while it stays within tolerance of the run's own mean.
    runs: List[List[RecordingSample]] = []
    current: List[RecordingSample] = []
    for s in usable:
        if not current:
            current = [s]
            continue
        speeds = [x.speed_m_s for x in current]
        mean = sum(speeds) / len(speeds)
        if mean > 0 and abs(s.speed_m_s - mean) / mean <= STAGE_MAX_CV * 2:
            current.append(s)
        else:
            runs.append(current)
            current = [s]
    if current:
        runs.append(current)

    # Merge adjacent runs at effectively the same speed, then keep the ones long enough to matter.
    merged: List[List[RecordingSample]] = []
    for r in runs:
        if merged:
            a = sum(x.speed_m_s for x in merged[-1]) / len(merged[-1])
            b = sum(x.speed_m_s for x in r) / len(r)
            if abs(a - b) < STAGE_MERGE_M_S:
                merged[-1].extend(r)
                continue
        merged.append(r)

    n = 0
    for r in merged:
        span = r[-1].t_s - r[0].t_s
        if span < min_stage_s:
            continue
        speeds = [x.speed_m_s for x in r]
        mean = sum(speeds) / len(speeds)
        if mean <= 0:
            continue
        sd = math.sqrt(sum((v - mean) ** 2 for v in speeds) / len(speeds))
        if sd / mean > STAGE_MAX_CV:
            continue
        # Walking stages are part of a ramp protocol and belong in the fit; standing still is not.
        if mean < 0.8:
            continue
        n += 1
        for x in r:
            x.label = f"stage_{n}"
    return n
