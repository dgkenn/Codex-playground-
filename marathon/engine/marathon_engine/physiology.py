"""Exercise-physiology primitives: HR zones, VDOT, training paces, grade adjustment, drift.

Every formula here is transcribed from a named source and covered by a test that checks it
against a published worked example, because a silently-wrong constant in this file would
misprescribe every workout downstream.

Sources
-------
* **HRmax estimation** — Tanaka, Monahan & Seals 2001, *J Am Coll Cardiol* 37:153-156,
  ``HRmax = 208 - 0.7 * age`` (SEE ~7 bpm for an individual, so this is a *starting* guess that
  must be replaced by an observed maximum; see :func:`hr_max_estimate`).
  Gellish et al. 2007, *Med Sci Sports Exerc* 39:822-829, ``207 - 0.7 * age``.
* **Karvonen / HR reserve** — Karvonen, Kentala & Mustala 1957. Percent of *reserve*, not of max,
  because %HRmax and %HRR diverge badly at the low end where a beginner trains.
* **VDOT / training paces** — Daniels & Gilbert, *Oxygen Power* (1979); Daniels,
  *Daniels' Running Formula* 3rd ed. (2014). The two Gilbert equations are in
  :func:`vo2_at_velocity` and :func:`pct_vo2max_for_duration`.
* **Riegel endurance exponent** — Riegel 1981, *Am Sci* 69:285-290, ``T2 = T1 * (D2/D1)**1.06``.
  Known to *under*-predict marathon time for low-mileage novices; see :func:`riegel_predict`.
* **Grade-adjusted pace** — Minetti et al. 2002, *J Appl Physiol* 93:1039-1046 (energy cost of
  gradient running, the fifth-order polynomial in :func:`minetti_cost`).
* **Aerobic decoupling** — Friel, *The Triathlete's Training Bible*; efficiency-factor ratio of
  second half to first half, <5% treated as "aerobically coupled".
* **Heat/humidity** — pace decrement rises with wet-bulb globe temperature; the coefficients in
  :func:`heat_pace_factor` are a conservative fit to published decrement tables and are marked as
  a heuristic, not a validated model.

Pure functions, stdlib only. No I/O, no device access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "hr_max_estimate", "hr_at_reserve_fraction", "reserve_fraction_at_hr",
    "Zone", "ZoneModel", "five_zone_model", "seiler_three_zone", "zone_for_hr",
    "vo2_at_velocity", "velocity_at_vo2", "pct_vo2max_for_duration", "vdot_from_race",
    "velocity_for_pct_vdot", "TrainingPaces", "training_paces", "vdot_from_hr_pace",
    "riegel_predict", "minetti_cost", "grade_adjusted_pace_factor", "grade_adjusted_pace",
    "decoupling", "efficiency_factor", "heat_pace_factor", "wbgt_estimate",
    "pace_to_speed", "speed_to_pace", "fmt_pace", "parse_pace",
    "TANAKA_SEE_BPM", "RIEGEL_EXPONENT", "RIEGEL_NOVICE_EXPONENT", "DECOUPLING_OK",
]

# ----------------------------------------------------------------------------------------
# Unit helpers.  Internally: speed in m/s, pace in seconds per kilometre.
# ----------------------------------------------------------------------------------------


def pace_to_speed(sec_per_km: float) -> float:
    """Pace (s/km) -> speed (m/s)."""
    if sec_per_km <= 0:
        raise ValueError("pace must be positive")
    return 1000.0 / sec_per_km


def speed_to_pace(m_per_s: float) -> float:
    """Speed (m/s) -> pace (s/km)."""
    if m_per_s <= 0:
        raise ValueError("speed must be positive")
    return 1000.0 / m_per_s


def fmt_pace(sec_per_km: float, *, per_mile: bool = False) -> str:
    """Render a pace as ``m:ss``. ``per_mile`` converts km -> mile first."""
    s = sec_per_km * 1.609344 if per_mile else sec_per_km
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def parse_pace(text: str, *, per_mile: bool = False) -> float:
    """Parse ``"5:30"`` -> seconds per km (or per mile when ``per_mile``)."""
    mins, _, secs = text.strip().partition(":")
    total = int(mins) * 60 + int(secs or 0)
    return total / 1.609344 if per_mile else float(total)


# ----------------------------------------------------------------------------------------
# Heart rate
# ----------------------------------------------------------------------------------------

#: Standard error of estimate for the Tanaka HRmax equation, in bpm. Reported ~7 bpm; an
#: individual can sit 15-20 bpm off the prediction, which is why every estimated HRmax in this
#: system is provisional and gets replaced by the highest *validly observed* HR.
TANAKA_SEE_BPM = 7.0


def hr_max_estimate(age: float, *, formula: str = "tanaka") -> float:
    """Age-predicted HRmax in bpm.

    ``formula``: ``tanaka`` (208 - 0.7*age, default), ``gellish`` (207 - 0.7*age),
    or ``fox`` (220 - age, included only because it is what everyone quotes; it is the least
    accurate, over-predicting in the young and under-predicting past ~40).

    This is a *seed* value. Treat any observed HR above it as evidence the estimate is wrong,
    not as an artifact -- see :func:`~marathon_engine.assessment.update_hr_max`.
    """
    if age <= 0 or age > 120:
        raise ValueError("age out of range")
    f = formula.lower()
    if f == "tanaka":
        return 208.0 - 0.7 * age
    if f == "gellish":
        return 207.0 - 0.7 * age
    if f == "fox":
        return 220.0 - age
    raise ValueError(f"unknown formula {formula!r}")


def hr_at_reserve_fraction(frac: float, hr_max: float, hr_rest: float) -> float:
    """Karvonen: HR corresponding to a fraction of heart-rate reserve."""
    if hr_max <= hr_rest:
        raise ValueError("hr_max must exceed hr_rest")
    return hr_rest + frac * (hr_max - hr_rest)


def reserve_fraction_at_hr(hr: float, hr_max: float, hr_rest: float) -> float:
    """Inverse Karvonen: what fraction of reserve a given HR represents (may exceed 1.0)."""
    if hr_max <= hr_rest:
        raise ValueError("hr_max must exceed hr_rest")
    return (hr - hr_rest) / (hr_max - hr_rest)


@dataclass(frozen=True)
class Zone:
    """One heart-rate zone. Bounds are inclusive-low, exclusive-high, in bpm."""
    index: int
    name: str
    low_bpm: int
    high_bpm: int
    low_frac: float          # fraction of HR reserve
    high_frac: float
    purpose: str

    def contains(self, hr: float) -> bool:
        return self.low_bpm <= hr < self.high_bpm

    def to_dict(self) -> dict:
        return {"index": self.index, "name": self.name, "low_bpm": self.low_bpm,
                "high_bpm": self.high_bpm, "low_frac": round(self.low_frac, 3),
                "high_frac": round(self.high_frac, 3), "purpose": self.purpose}


@dataclass(frozen=True)
class ZoneModel:
    """A named set of zones plus the HR anchors they were derived from."""
    kind: str                       # "five_zone_hrr" | "seiler3"
    hr_max: float
    hr_rest: float
    zones: Tuple[Zone, ...]
    lthr: Optional[float] = None    # lactate-threshold HR, when known from a field test

    def zone_for(self, hr: float) -> Zone:
        return zone_for_hr(hr, self)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "hr_max": round(self.hr_max, 1),
                "hr_rest": round(self.hr_rest, 1),
                "lthr": round(self.lthr, 1) if self.lthr else None,
                "zones": [z.to_dict() for z in self.zones]}


#: Five-zone boundaries as fractions of heart-rate *reserve*. Chosen to line up with the
#: Daniels intensity families (E / M / T / I / R) rather than with any one vendor's colour bands.
_FIVE_ZONE_HRR: Tuple[Tuple[str, float, float, str], ...] = (
    ("Z1 Recovery", 0.45, 0.60, "active recovery, pure aerobic base, conversational"),
    ("Z2 Easy",     0.60, 0.73, "the bread and butter: mitochondrial/capillary adaptation"),
    ("Z3 Steady",   0.73, 0.81, "marathon-pace effort; useful but the classic junk-mile trap"),
    ("Z4 Threshold", 0.81, 0.90, "lactate threshold / tempo, ~1 h race effort"),
    ("Z5 VO2max",   0.90, 1.05, "3-5 min interval intensity, aerobic ceiling"),
)


def five_zone_model(hr_max: float, hr_rest: float, *, lthr: Optional[float] = None) -> ZoneModel:
    """Five HR-reserve zones.

    When a measured ``lthr`` is supplied the Z3/Z4 boundary is *pinned* to it, because a beginner's
    threshold routinely sits well away from the population %HRR guess and threshold work is the
    session type where getting the anchor wrong matters most.
    """
    zones: List[Zone] = []
    for i, (name, lo, hi, purpose) in enumerate(_FIVE_ZONE_HRR, start=1):
        low = hr_at_reserve_fraction(lo, hr_max, hr_rest)
        high = hr_at_reserve_fraction(hi, hr_max, hr_rest)
        zones.append(Zone(index=i, name=name, low_bpm=int(round(low)), high_bpm=int(round(high)),
                          low_frac=lo, high_frac=hi, purpose=purpose))
    if lthr:
        # Pin the Z3->Z4 edge to the measured threshold, keeping zone order intact.
        pinned = int(round(lthr))
        z3, z4 = zones[2], zones[3]
        if z3.low_bpm < pinned < z4.high_bpm:
            zones[2] = Zone(z3.index, z3.name, z3.low_bpm, pinned,
                            z3.low_frac, reserve_fraction_at_hr(pinned, hr_max, hr_rest), z3.purpose)
            zones[3] = Zone(z4.index, z4.name, pinned, z4.high_bpm,
                            reserve_fraction_at_hr(pinned, hr_max, hr_rest), z4.high_frac, z4.purpose)
    return ZoneModel(kind="five_zone_hrr", hr_max=hr_max, hr_rest=hr_rest,
                     zones=tuple(zones), lthr=lthr)


def seiler_three_zone(hr_max: float, hr_rest: float, *,
                      lthr: Optional[float] = None) -> ZoneModel:
    """Seiler's three-zone model (below LT1 / between LT1-LT2 / above LT2).

    This is the model the 80/20 intensity-distribution literature is actually stated in
    (Seiler & Kjerland 2006, *Scand J Med Sci Sports*), so polarization compliance is measured
    against *these* zones, not the five-zone display model.
    """
    lt2 = lthr if lthr else hr_at_reserve_fraction(0.85, hr_max, hr_rest)
    lt1 = lt2 - 0.13 * (hr_max - hr_rest)   # LT1 sits ~13% of reserve below LT2 in most athletes
    zones = (
        Zone(1, "Low (below LT1)", int(round(hr_at_reserve_fraction(0.40, hr_max, hr_rest))),
             int(round(lt1)), 0.40, reserve_fraction_at_hr(lt1, hr_max, hr_rest),
             "the 80% -- easy volume"),
        Zone(2, "Threshold (LT1-LT2)", int(round(lt1)), int(round(lt2)),
             reserve_fraction_at_hr(lt1, hr_max, hr_rest),
             reserve_fraction_at_hr(lt2, hr_max, hr_rest), "the grey zone -- use deliberately"),
        Zone(3, "High (above LT2)", int(round(lt2)),
             int(round(hr_at_reserve_fraction(1.05, hr_max, hr_rest))),
             reserve_fraction_at_hr(lt2, hr_max, hr_rest), 1.05, "the 20% -- hard intervals"),
    )
    return ZoneModel(kind="seiler3", hr_max=hr_max, hr_rest=hr_rest, zones=zones, lthr=lthr)


def zone_for_hr(hr: float, model: ZoneModel) -> Zone:
    """Which zone an HR falls in, clamped to the first/last zone outside the modelled range."""
    for z in model.zones:
        if z.contains(hr):
            return z
    return model.zones[0] if hr < model.zones[0].low_bpm else model.zones[-1]


# ----------------------------------------------------------------------------------------
# VDOT (Daniels & Gilbert)
# ----------------------------------------------------------------------------------------


def vo2_at_velocity(v_m_per_min: float) -> float:
    """Gilbert's oxygen cost of running at ``v`` m/min, in ml/kg/min.

    ``VO2 = -4.60 + 0.182258*v + 0.000104*v**2``
    """
    if v_m_per_min <= 0:
        raise ValueError("velocity must be positive")
    return -4.60 + 0.182258 * v_m_per_min + 0.000104 * v_m_per_min ** 2


def velocity_at_vo2(vo2: float) -> float:
    """Invert :func:`vo2_at_velocity` -> m/min (positive root of the quadratic)."""
    a, b, c = 0.000104, 0.182258, -4.60 - vo2
    disc = b * b - 4 * a * c
    if disc < 0:
        raise ValueError("no real velocity for that VO2")
    return (-b + math.sqrt(disc)) / (2 * a)


def pct_vo2max_for_duration(minutes: float) -> float:
    """Gilbert's fraction of VO2max sustainable for ``minutes`` of racing (0..1).

    ``%max = 0.8 + 0.1894393*exp(-0.012778*t) + 0.2989558*exp(-0.1932605*t)``

    Note the shape: it exceeds 1.0 for very short durations (a 2-minute race is run above
    VO2max in this model), which is intended -- it is a curve fit to race performance, not a
    physiological ceiling.
    """
    if minutes <= 0:
        raise ValueError("duration must be positive")
    return (0.8 + 0.1894393 * math.exp(-0.012778 * minutes)
            + 0.2989558 * math.exp(-0.1932605 * minutes))


def vdot_from_race(distance_m: float, seconds: float) -> float:
    """VDOT from a race performance (Daniels' pseudo-VO2max).

    VDOT is *not* a measured VO2max: it is the VO2max a runner with average economy would need
    to produce this performance, so it silently folds in economy and durability. That is a
    feature for prescribing paces and a trap for comparing physiologies.
    """
    if distance_m <= 0 or seconds <= 0:
        raise ValueError("distance and time must be positive")
    minutes = seconds / 60.0
    v = distance_m / minutes                       # m/min
    return vo2_at_velocity(v) / pct_vo2max_for_duration(minutes)


def velocity_for_pct_vdot(vdot: float, pct: float) -> float:
    """Velocity (m/min) at ``pct`` (0..1.1) of a given VDOT."""
    return velocity_at_vo2(vdot * pct)


#: Daniels' intensity families as a fraction of VDOT.
#:
#: IMPORTANT CALIBRATION NOTE. Daniels *describes* Easy running as "59-74% of VO2max", but his
#: published E-pace **table** is not that band: for VDOT 50 the book prints 5:35-6:04 /km, which
#: back-solves to roughly 57-62.5% of VDOT through the Gilbert equations. Taking the prose band
#: literally puts the fast end of "easy" at 4:54 /km for VDOT 50 -- faster than his marathon pace,
#: i.e. it would prescribe a tempo run every time the app said "easy". The percentages below are
#: therefore fitted to reproduce the printed tables (verified in ``test_physiology.py`` against
#: VDOT 30/38/50 for E, M, T and I), not copied from the prose. This is the single most
#: consequential constant set in the codebase for a beginner, since running easy days too hard is
#: the classic failure mode.
#:
#: We prescribe from the *slow* half of the Easy band for the same reason: the cost of an easy run
#: being slightly too easy is approximately zero, and the cost of it being too hard is a missed
#: quality session later in the week.
_PACE_FAMILIES: Dict[str, Tuple[float, float, float]] = {
    #  name          low     high   prescribe_at
    "easy":         (0.570, 0.625, 0.590),
    "marathon":     (0.750, 0.800, 0.780),
    "threshold":    (0.860, 0.885, 0.880),
    "interval":     (0.950, 1.000, 0.970),
    "repetition":   (1.050, 1.100, 1.075),
}


@dataclass(frozen=True)
class TrainingPaces:
    """Prescribed paces in seconds per kilometre, plus the VDOT they came from."""
    vdot: float
    easy: float
    marathon: float
    threshold: float
    interval: float
    repetition: float
    easy_range: Tuple[float, float]

    def to_dict(self) -> dict:
        return {
            "vdot": round(self.vdot, 1),
            "easy_sec_km": round(self.easy),
            "easy_range_sec_km": [round(self.easy_range[0]), round(self.easy_range[1])],
            "marathon_sec_km": round(self.marathon),
            "threshold_sec_km": round(self.threshold),
            "interval_sec_km": round(self.interval),
            "repetition_sec_km": round(self.repetition),
            "display": {k: fmt_pace(v) for k, v in (
                ("easy", self.easy), ("marathon", self.marathon), ("threshold", self.threshold),
                ("interval", self.interval), ("repetition", self.repetition))},
        }


def training_paces(vdot: float) -> TrainingPaces:
    """Daniels E/M/T/I/R paces (s/km) for a VDOT."""
    if vdot <= 0:
        raise ValueError("vdot must be positive")

    def pace_at(pct: float) -> float:
        return speed_to_pace(velocity_for_pct_vdot(vdot, pct) / 60.0)

    lo, hi, _ = _PACE_FAMILIES["easy"]
    return TrainingPaces(
        vdot=vdot,
        easy=pace_at(_PACE_FAMILIES["easy"][2]),
        marathon=pace_at(_PACE_FAMILIES["marathon"][2]),
        threshold=pace_at(_PACE_FAMILIES["threshold"][2]),
        interval=pace_at(_PACE_FAMILIES["interval"][2]),
        repetition=pace_at(_PACE_FAMILIES["repetition"][2]),
        # Slower pace = larger s/km, so the LOW %VDOT gives the SLOW end of the range.
        easy_range=(pace_at(hi), pace_at(lo)),
    )


def vdot_from_hr_pace(hr: float, pace_sec_km: float, hr_max: float, hr_rest: float) -> float:
    """Estimate VDOT from a *submaximal* steady HR/pace pair.

    Uses the fraction-of-reserve as a proxy for fraction of VO2max -- crude, because %HRR and
    %VO2max agree only approximately (they are closest in the 60-85% band, which is exactly
    where easy/steady running lives). Only trust this from a >=10 min steady segment, and only
    as a *between-test* tracker; the field tests in :mod:`marathon_engine.assessment` remain the
    source of truth for prescribing paces.
    """
    frac = reserve_fraction_at_hr(hr, hr_max, hr_rest)
    if not 0.5 <= frac <= 1.0:
        raise ValueError("HR outside the band where %HRR approximates %VO2max")
    vo2 = vo2_at_velocity(pace_to_speed(pace_sec_km) * 60.0)
    return vo2 / frac


# ----------------------------------------------------------------------------------------
# Race prediction
# ----------------------------------------------------------------------------------------

RIEGEL_EXPONENT = 1.06
#: Riegel's 1.06 was fitted to *trained* racers. Low-mileage novices fade far harder over the
#: marathon; a higher exponent is the honest default until the user has actually run long. 1.15
#: is at the pessimistic end of the published novice range and is chosen deliberately -- an
#: over-optimistic marathon prediction is the mechanism by which first-timers blow up at 30 km.
RIEGEL_NOVICE_EXPONENT = 1.15


def riegel_predict(known_distance_m: float, known_seconds: float,
                   target_distance_m: float, *, exponent: float = RIEGEL_EXPONENT) -> float:
    """Riegel's endurance-law prediction, in seconds.

    ``T2 = T1 * (D2/D1) ** exponent``
    """
    if min(known_distance_m, known_seconds, target_distance_m) <= 0:
        raise ValueError("inputs must be positive")
    return known_seconds * (target_distance_m / known_distance_m) ** exponent


# ----------------------------------------------------------------------------------------
# Terrain and environment
# ----------------------------------------------------------------------------------------


def minetti_cost(grade: float) -> float:
    """Minetti 2002 energy cost of running at ``grade`` (rise/run, e.g. 0.05 = 5% up), J/kg/m.

    ``Cr = 155.4 i^5 - 30.4 i^4 - 43.3 i^3 + 46.3 i^2 + 19.5 i + 3.6``

    Validated by Minetti over -0.45..+0.45; the polynomial misbehaves outside that, so we clamp.
    Note the minimum is at a *downhill* grade near -10%, not at zero -- gentle downhill running
    is genuinely cheaper than flat, which is why naive "distance only" pacing punishes hills
    twice.
    """
    i = max(-0.45, min(0.45, grade))
    return (155.4 * i ** 5 - 30.4 * i ** 4 - 43.3 * i ** 3
            + 46.3 * i ** 2 + 19.5 * i + 3.6)


def grade_adjusted_pace_factor(grade: float) -> float:
    """Multiplier converting *actual* pace on a grade to the equivalent flat pace.

    Ratio of Minetti's cost at ``grade`` to the flat cost (3.6 J/kg/m). A factor of 1.20 means
    running this grade costs 20% more per metre, so 5:00/km up it is worth 5:00/1.20 = 4:10/km
    on the flat.
    """
    return minetti_cost(grade) / minetti_cost(0.0)


def grade_adjusted_pace(pace_sec_km: float, grade: float) -> float:
    """Flat-equivalent pace (s/km) for a pace actually run on ``grade``."""
    return pace_sec_km / grade_adjusted_pace_factor(grade)


def wbgt_estimate(temp_c: float, rel_humidity: float, *,
                  solar: bool = False, wind_m_s: float = 1.0) -> float:
    """Rough outdoor WBGT (deg C) from the fields a weather API actually returns.

    A true WBGT needs a black-globe thermometer. This is the standard psychrometric
    approximation via wet-bulb temperature (Stull 2011, *J Appl Meteorol Climatol* 50:2267)
    combined as ``WBGT ~= 0.7*Tw + 0.2*Tg + 0.1*Ta``, with the globe temperature approximated
    from air temperature plus a solar-load term. Treat it as a *heuristic index* for deciding
    how much to slow down, not as an occupational-exposure measurement.
    """
    rh = max(1.0, min(100.0, rel_humidity))
    t = temp_c
    # Stull's wet-bulb approximation.
    tw = (t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
          + math.atan(t + rh) - math.atan(rh - 1.676331)
          + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh)
          - 4.686035)
    solar_load = 0.0
    if solar:
        solar_load = max(0.0, 6.0 - 1.5 * max(0.0, wind_m_s - 1.0))
    tg = t + solar_load
    return 0.7 * tw + 0.2 * tg + 0.1 * t


def heat_pace_factor(wbgt_c: float) -> float:
    """Pace *slow-down* multiplier for heat: 1.0 = no adjustment, 1.06 = run 6% slower.

    [heuristic] Piecewise-linear in WBGT above a 10 deg C reference, at ~1.5% per deg C to 20 C
    and ~2.5% per deg C beyond, capped at 20%. This is calibrated to the widely-used
    temperature/pace decrement tables rather than to a single published equation, and the cap
    exists because past roughly WBGT 28 C the correct answer is to move the session indoors or
    change its purpose, not to keep scaling a pace target.
    """
    if wbgt_c <= 10.0:
        return 1.0
    if wbgt_c <= 20.0:
        return 1.0 + 0.015 * (wbgt_c - 10.0)
    return min(1.20, 1.15 + 0.025 * (wbgt_c - 20.0))


# ----------------------------------------------------------------------------------------
# Within-run analysis
# ----------------------------------------------------------------------------------------


def efficiency_factor(mean_speed_m_s: float, mean_hr: float) -> float:
    """Speed per heartbeat proxy: m/s per bpm, scaled x1000 for readability.

    Rising EF at the same perceived effort across weeks is the cleanest single number showing
    aerobic fitness improving, provided it is only ever compared between *similar* sessions in
    similar conditions.
    """
    if mean_hr <= 0:
        raise ValueError("hr must be positive")
    return mean_speed_m_s / mean_hr * 1000.0


DECOUPLING_OK = 0.05


def decoupling(first_half: Sequence[Tuple[float, float]],
               second_half: Sequence[Tuple[float, float]]) -> float:
    """Aerobic decoupling as a fraction: ``EF_first/EF_second - 1``.

    Each half is a sequence of ``(speed_m_s, hr_bpm)`` samples. Positive means HR drifted up
    relative to pace (or pace fell at the same HR) -- the classic aerobic-durability marker.
    Friel's rule of thumb: <5% (:data:`DECOUPLING_OK`) means the effort was genuinely aerobic
    and sustainable; >5% on a run that was *meant* to be easy is evidence the pace was too hot,
    the day was too hot, or the athlete was underfuelled or under-recovered.

    Compute this only over steady-state efforts of >=~45 min with the warm-up excluded, or the
    number is noise.
    """
    def ef(samples: Sequence[Tuple[float, float]]) -> float:
        good = [(s, h) for s, h in samples if s > 0 and h > 0]
        if not good:
            raise ValueError("no valid samples")
        mean_s = sum(s for s, _ in good) / len(good)
        mean_h = sum(h for _, h in good) / len(good)
        return efficiency_factor(mean_s, mean_h)

    return ef(first_half) / ef(second_half) - 1.0
