"""The diagnostic battery: find out where this runner actually is, safely, in week 1.

The hard constraint is that the athlete **has never run a 5K**. Every standard entry point to a
training plan assumes a recent race time, and the two classic field tests are both wrong here:

* A **Cooper 12-minute test** or a 5K time trial in week 1 asks an untrained person for a maximal
  effort on untrained connective tissue. That is how you generate a week-2 injury and a maximal HR
  reading that reflects nothing but discomfort tolerance.
* A **lab VO2max** is unavailable and unnecessary.

So week 1 uses a **submaximal graded walk-jog ramp** instead, which is safe, repeatable, and yields
everything the planner needs: the HR-speed relationship, a ventilatory-threshold estimate from the
talk test, a seed VDOT, cadence at each speed, and an efficiency-factor baseline to re-test against.
The maximal tests arrive later, when the tissue can take them, and in ascending order of what they
tell you: a **2000 m trial** around week 5 of the base phase, then a 5K, then a 10K, then a half. The
2000 m distance is chosen for the *duration* it produces -- roughly 11-12 minutes for a beginner, which
sits inside both Riegel's validated 3.5-230 minute window and the range where Daniels' sustainable-
%VO2max curve is well behaved. A 5K at that stage would be a longer maximal effort on less prepared
tissue for a worse estimate.

Protocol and evidence
---------------------
**A1 -- Orthostatic and resting baseline** (day 1, before any running). 5 min supine, then 2 min
standing. Yields RHR, supine RMSSD, and the standing HR rise. Purpose: anchor the HRV baseline
window that :mod:`marathon_engine.readiness` needs, and catch a resting tachycardia before we
prescribe anything.

**A2 -- Submaximal graded ramp** (day 3). 5 min easy walk, then 4-5 stages of 4 minutes, each a
step faster, ending well before exhaustion (stop at RPE 15/20 or 85% of estimated HRmax, whichever
comes first). Record the HR over the final 60 s of each stage -- HR needs ~2-3 min to reach steady
state at a given submaximal speed, so an earlier reading understates it. This is the classic
submaximal graded exercise test logic (Astrand-Rhyming, YMCA cycle protocol) transplanted to a
walk-jog treadmill or flat loop, and the HR-speed relationship in the aerobic range is close enough
to linear for extrapolation (Conconi's original claim of a deflection point has not replicated
reliably, so we fit a straight line and do **not** claim to find a "deflection").

**A3 -- Talk test**, run inside A2. At the end of each stage, recite a fixed sentence and rate it:
comfortable / effortful / impossible. The first stage where speech becomes effortful approximates
the first ventilatory threshold (Persinger et al. 2004, *Med Sci Sports Exerc* 36:1632; Foster's
talk-test work), and the last comfortable stage sits at or just below VT1. For a beginner this is a
more trustworthy threshold marker than any %HRmax formula, because it is *their* physiology
answering.

**A4 -- Gait baseline**, computed from the Verity's own accelerometer during A2: cadence at each
speed, and step-rate variability. Cadence is speed-dependent, so the useful number is
cadence-at-a-given-speed tracked over months, not a single target. The "180 spm" figure is a
misreading of Daniels' observation of elite runners at race pace and is **not** a target for a
beginner (Heiderscheit et al. 2011, *Med Sci Sports Exerc* 43:296, showed a +5-10% step-rate
increase reduces per-step load at the hip and knee -- a *relative* change from the runner's own
baseline, which is why we store the baseline).

**A5 -- Structural screen** (day 2). Single-leg calf raises to failure, 30-second sit-to-stand,
single-leg balance, and a step-down quality rating. The calf-raise count is the one that most often
explains an early Achilles or calf problem in a new runner; healthy adults should manage
roughly 20-25 unilateral raises through full range, and being well under that is a specific,
fixable finding rather than a vague "get stronger".

**A6 -- Progressive time trials**, gated by phase rather than by date: 2000 m (seeds the first genuine
VDOT), 5K, 10K (the first legitimate Riegel input), half marathon (sets marathon goal pace). VDOT is
re-derived from the **best available** result by the precedence in :data:`TT_PRECEDENCE` and is never
averaged across distances -- see :func:`best_time_trial`.

**Re-testing.** A2 repeats every 4 weeks on the same route at the same time of day. The tracked
outputs are HR at each fixed speed (should fall), efficiency factor (should rise), and the
extrapolated LT speed (should rise). Comparing anything else across tests is noise.

Pure functions and dataclasses; no I/O.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from marathon_engine.physiology import (
    TrainingPaces, ZoneModel, efficiency_factor, five_zone_model, hr_max_estimate,
    hr_at_reserve_fraction, pace_to_speed, reserve_fraction_at_hr, riegel_predict,
    speed_to_pace, training_paces, vdot_from_race, vo2_at_velocity, fmt_pace,
    RIEGEL_NOVICE_EXPONENT, TANAKA_SEE_BPM,
)

__all__ = [
    "RampStage", "RampTest", "StrengthScreen", "TimeTrial", "FitnessProfile",
    "RAMP_STAGE_MIN", "RAMP_STOP_HRR", "RAMP_STOP_RPE", "CALF_RAISE_TARGET",
    "HrMaxCandidate", "HR_MAX_SUSTAIN_S", "HR_MAX_MIN_ELAPSED_S", "HR_MAX_CADENCE_MARGIN",
    "HR_MAX_STEP_UNCONFIRMED", "HR_MAX_TOTAL_UNCONFIRMED",
    "fit_hr_speed", "speed_at_hr", "hr_at_speed", "estimate_hr_max_from_ramp",
    "lt_speed_from_talk_test", "seed_vdot_from_ramp", "profile_from_ramp",
    "profile_from_time_trial", "update_hr_max", "compare_ramps", "ramp_protocol",
    "best_time_trial", "TT_PRECEDENCE",
]

RAMP_STAGE_MIN = 4.0
#: Stop the ramp at 85% of heart-rate reserve. Submaximal by design -- we extrapolate rather than
#: push, because the extrapolation error is smaller than the injury risk of a week-1 max effort.
RAMP_STOP_HRR = 0.85
RAMP_STOP_RPE = 15          # Borg 6-20 scale, "hard"
CALF_RAISE_TARGET = 22      # unilateral, full range, controlled tempo


@dataclass
class RampStage:
    """One stage of the graded ramp."""
    speed_kmh: float
    steady_hr: float                     # mean HR over the FINAL 60 s of the stage
    rpe_6_20: Optional[int] = None
    talk: Optional[str] = None           # comfortable | effortful | impossible
    cadence_spm: Optional[float] = None
    duration_min: float = RAMP_STAGE_MIN

    @property
    def speed_m_s(self) -> float:
        return self.speed_kmh / 3.6

    @property
    def pace_sec_km(self) -> float:
        return 3600.0 / self.speed_kmh

    def to_dict(self) -> dict:
        return {"speed_kmh": self.speed_kmh, "pace": fmt_pace(self.pace_sec_km),
                "steady_hr": round(self.steady_hr, 1), "rpe_6_20": self.rpe_6_20,
                "talk": self.talk, "cadence_spm": self.cadence_spm}


@dataclass
class RampTest:
    """A completed submaximal graded ramp."""
    day: date
    stages: List[RampStage]
    hr_rest: float
    age: float
    weight_kg: Optional[float] = None
    surface: str = "treadmill"           # treadmill | track | road_flat
    temp_c: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {"day": self.day.isoformat(), "surface": self.surface,
                "hr_rest": self.hr_rest, "temp_c": self.temp_c,
                "stages": [s.to_dict() for s in self.stages], "notes": self.notes}


@dataclass
class StrengthScreen:
    """Day-2 structural screen. All counts are per side where relevant."""
    day: date
    calf_raises_left: Optional[int] = None
    calf_raises_right: Optional[int] = None
    sit_to_stand_30s: Optional[int] = None
    single_leg_balance_s_left: Optional[float] = None
    single_leg_balance_s_right: Optional[float] = None
    step_down_quality: Optional[str] = None   # good | knee_valgus | trunk_lean | pelvic_drop
    plank_s: Optional[float] = None
    notes: str = ""

    def findings(self) -> List[Dict[str, str]]:
        """Specific, actionable findings -- not a score."""
        out: List[Dict[str, str]] = []
        cl, cr = self.calf_raises_left, self.calf_raises_right
        for side, n in (("left", cl), ("right", cr)):
            if n is not None and n < CALF_RAISE_TARGET:
                out.append({"finding": f"calf_endurance_{side}", "severity": "medium",
                            "message": (f"{n} single-leg calf raises on the {side} "
                                        f"(target ~{CALF_RAISE_TARGET}). The calf-Achilles complex "
                                        "absorbs the most load per stride of any structure in "
                                        "running; this is the highest-yield thing to fix, and it "
                                        "responds in 6-8 weeks."),
                            "action": "3 x 15 heavy slow calf raises, 3x/week, straight- and bent-knee"})
        if cl is not None and cr is not None and max(cl, cr) > 0:
            asym = abs(cl - cr) / max(cl, cr)
            if asym > 0.20:
                out.append({"finding": "calf_asymmetry", "severity": "medium",
                            "message": (f"{asym*100:.0f}% side-to-side difference in calf endurance "
                                        f"({cl} vs {cr}). Asymmetry this size is worth correcting "
                                        "before adding volume, and worth mentioning if anything "
                                        "starts to hurt on the weaker side."),
                            "action": "extra set on the weaker side; re-test in 4 weeks"})
        if self.step_down_quality and self.step_down_quality != "good":
            out.append({"finding": f"step_down_{self.step_down_quality}", "severity": "low",
                        "message": (f"Step-down shows {self.step_down_quality.replace('_', ' ')}. "
                                    "Common, usually a hip-abductor and motor-control issue rather "
                                    "than a structural one."),
                        "action": "side-lying abduction, single-leg bridges, slow step-downs"})
        if self.sit_to_stand_30s is not None and self.sit_to_stand_30s < 15:
            out.append({"finding": "low_leg_power", "severity": "low",
                        "message": f"{self.sit_to_stand_30s} sit-to-stands in 30 s is on the low side.",
                        "action": "squats and split squats twice a week"})
        return out

    def to_dict(self) -> dict:
        return {"day": self.day.isoformat(),
                "calf_raises": [self.calf_raises_left, self.calf_raises_right],
                "sit_to_stand_30s": self.sit_to_stand_30s,
                "balance_s": [self.single_leg_balance_s_left, self.single_leg_balance_s_right],
                "step_down_quality": self.step_down_quality, "plank_s": self.plank_s,
                "findings": self.findings(), "notes": self.notes}


@dataclass
class TimeTrial:
    """A maximal-effort trial over a known distance."""
    day: date
    distance_m: float
    seconds: float
    mean_hr: Optional[float] = None
    peak_hr: Optional[float] = None
    mean_cadence_spm: Optional[float] = None
    conditions: str = ""
    walked: bool = False        # did it include walk breaks? (changes how we read it)

    @property
    def vdot(self) -> float:
        return vdot_from_race(self.distance_m, self.seconds)

    @property
    def pace_sec_km(self) -> float:
        return self.seconds / (self.distance_m / 1000.0)

    def to_dict(self) -> dict:
        return {"day": self.day.isoformat(), "distance_m": self.distance_m,
                "seconds": round(self.seconds, 1), "pace": fmt_pace(self.pace_sec_km),
                "vdot": round(self.vdot, 1), "mean_hr": self.mean_hr, "peak_hr": self.peak_hr,
                "walked": self.walked, "conditions": self.conditions}


# ----------------------------------------------------------------------------------------
# Ramp analysis
# ----------------------------------------------------------------------------------------


def fit_hr_speed(stages: Sequence[RampStage]) -> Tuple[float, float, float]:
    """Least-squares fit of steady HR against speed. Returns ``(slope_bpm_per_kmh, intercept, r2)``.

    Only stages at or above a brisk walk are used: HR at a stroll is dominated by postural and
    thermal noise and would flatten the slope, which would then *over*-estimate the speed at any
    given HR -- the dangerous direction.
    """
    pts = [(s.speed_kmh, s.steady_hr) for s in stages if s.speed_kmh >= 4.5]
    if len(pts) < 3:
        raise ValueError("need at least 3 stages at >=4.5 km/h to fit HR vs speed")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("all stages at the same speed")
    slope = sum((x - mx) * (y - my) for x, y in pts) / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in pts)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return slope, intercept, r2


def hr_at_speed(speed_kmh: float, fit: Tuple[float, float, float]) -> float:
    slope, intercept, _ = fit
    return slope * speed_kmh + intercept


def speed_at_hr(hr: float, fit: Tuple[float, float, float]) -> float:
    """Invert the fit: what speed corresponds to a target HR (km/h)."""
    slope, intercept, _ = fit
    if slope <= 0:
        raise ValueError("non-positive HR/speed slope -- test data is unusable")
    return (hr - intercept) / slope


def estimate_hr_max_from_ramp(ramp: RampTest) -> Tuple[float, str]:
    """HRmax estimate and its provenance: ``("observed" | "age_formula")``.

    A submaximal ramp cannot measure HRmax. We therefore keep the age formula as the anchor, but
    if the ramp's highest observed HR already *exceeds* the age prediction we trust the
    observation -- an observed heart rate is data and a regression on a population is not. The
    ramp value is then bumped by a small margin, since the athlete stopped submaximally and their
    true max is necessarily higher.
    """
    predicted = hr_max_estimate(ramp.age)
    observed = max((s.steady_hr for s in ramp.stages), default=0.0)
    if observed > predicted:
        return observed + 5.0, "observed"
    return predicted, "age_formula"


def lt_speed_from_talk_test(ramp: RampTest) -> Optional[Tuple[float, float]]:
    """``(speed_kmh, hr)`` at the talk-test threshold, or ``None`` if it was never reached.

    Defined as the midpoint between the last *comfortable* stage and the first *effortful* one --
    the threshold lies between them and pretending otherwise adds false precision.
    """
    last_ok: Optional[RampStage] = None
    first_hard: Optional[RampStage] = None
    for s in ramp.stages:
        if s.talk == "comfortable":
            last_ok = s
        elif s.talk in ("effortful", "impossible") and first_hard is None:
            first_hard = s
    if last_ok and first_hard:
        return ((last_ok.speed_kmh + first_hard.speed_kmh) / 2.0,
                (last_ok.steady_hr + first_hard.steady_hr) / 2.0)
    return None


def seed_vdot_from_ramp(ramp: RampTest) -> Tuple[float, str]:
    """Seed VDOT from the submaximal ramp, plus a note on how it was derived.

    Method: take the talk-test threshold speed when available -- that speed is close to an effort
    the athlete could hold for roughly an hour, which is the definition threshold pace
    approximates -- and convert it to VDOT by treating it as an hour race performance. Where the
    talk test did not resolve, extrapolate the HR-speed fit to 85% of HR reserve and treat *that*
    as threshold speed instead.

    This is deliberately conservative and will usually **under**-estimate. Good: the first weeks
    should feel easy, and the week-4 time trial corrects it upward with real data. An
    over-estimated seed VDOT means every prescribed pace is too fast from day one.
    """
    hr_max, _ = estimate_hr_max_from_ramp(ramp)
    tt = lt_speed_from_talk_test(ramp)
    if tt:
        speed_kmh, _hr = tt
        method = "talk_test_threshold"
    else:
        fit = fit_hr_speed(ramp.stages)
        target_hr = hr_at_reserve_fraction(RAMP_STOP_HRR, hr_max, ramp.hr_rest)
        speed_kmh = speed_at_hr(target_hr, fit)
        method = "hr_speed_extrapolation"

    # Treat the threshold speed as a one-hour effort and read VDOT off that performance.
    distance_m = speed_kmh * 1000.0
    vdot = vdot_from_race(distance_m, 3600.0)
    return vdot, method


@dataclass
class FitnessProfile:
    """Everything the planner needs to prescribe. Produced by assessment, updated by every test."""
    as_of: date
    age: float
    hr_rest: float
    hr_max: float
    hr_max_source: str                    # observed | age_formula | race
    vdot: float
    vdot_source: str
    zones: ZoneModel
    paces: TrainingPaces
    lthr: Optional[float] = None
    threshold_speed_kmh: Optional[float] = None
    cadence_by_speed: Dict[float, float] = field(default_factory=dict)
    ef_baseline: Optional[float] = None   # efficiency factor at the reference easy speed
    ramp_fit: Optional[Tuple[float, float, float]] = None
    strength_findings: List[Dict[str, str]] = field(default_factory=list)
    #: Predicted times, all clearly labelled as predictions from a novice-adjusted exponent.
    predictions: Dict[str, float] = field(default_factory=dict)
    caveats: List[str] = field(default_factory=list)
    #: ``"hr_from_ramp"`` while VDOT is below the table floor, else ``"vdot"``. The app must show
    #: whichever basis is authoritative and must not mix them in the same prescription.
    prescription_basis: str = "vdot"
    #: Zone-name -> (fast_sec_km, slow_sec_km), from the measured HR-speed fit.
    hr_paces: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    #: Longest continuous run actually observed, in minutes. ``None`` when nothing is known.
    #:
    #: The run-walk ladder assumes someone who cannot run for a minute, which is the right default
    #: and the wrong one for an athlete already holding several. Entering the ladder at the bottom
    #: for such a person is not caution -- it is weeks of sessions that never load the tissue they
    #: exist to load. This is deliberately the *observed* figure, never a self-report.
    demonstrated_run_min: Optional[float] = None
    #: Fastest speed, km/h, at which measured heart rate stayed inside the easy ceiling. ``None``
    #: when nothing is known.
    #:
    #: Observed, never self-reported, for the same reason as ``demonstrated_run_min``. It exists
    #: because the easy pace derived from a table is the pace of the WHOLE session -- running and
    #: walking averaged together -- and prescribing that as the speed to run the running blocks at
    #: asks for something close to a gait the athlete does not have. For this athlete the table said
    #: run at 14:00 per mile; 14:00 per mile is 6.9 km/h, which is a speed a person walks at, not
    #: one they run at. What he was actually observed doing was 8.0 km/h at 138 bpm, comfortably
    #: inside the easy ceiling -- so 8.0 km/h is the honest answer and the table is not.
    observed_easy_run_kmh: Optional[float] = None

    @property
    def run_block_pace_range(self) -> Optional[Tuple[float, float]]:
        """The band for the RUNNING portions of a run-walk session, in sec/km, or None.

        Distinct from ``easy_pace_range``, which is the average of a session that is part walking.
        Handing that average to a runner as the speed to run at is how you end up prescribing a pace
        below the walk-run gait transition.

        The window is +/-4%: wide enough not to nag, narrow enough that the 20% overshoot this
        athlete makes on every run block -- 10:00 per mile when 12:15 is called for, which is the
        difference between Z1 and Z4 for him -- is caught within the first twenty seconds.
        """
        if not self.observed_easy_run_kmh:
            return None
        mid = 3600.0 / self.observed_easy_run_kmh
        return (mid * 0.96, mid * 1.04)

    @property
    def easy_pace_range(self) -> Tuple[float, float]:
        """The authoritative easy-pace window, from whichever basis is in force."""
        if self.prescription_basis == "hr_from_ramp":
            for name, rng in self.hr_paces.items():
                if name.startswith("Z2"):
                    return rng
        return self.paces.easy_range

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of.isoformat(), "age": self.age,
            "hr_rest": round(self.hr_rest, 1), "hr_max": round(self.hr_max, 1),
            "hr_max_source": self.hr_max_source,
            "vdot": round(self.vdot, 1), "vdot_source": self.vdot_source,
            "lthr": round(self.lthr, 1) if self.lthr else None,
            "threshold_speed_kmh": (round(self.threshold_speed_kmh, 2)
                                    if self.threshold_speed_kmh else None),
            "zones": self.zones.to_dict(), "paces": self.paces.to_dict(),
            "prescription_basis": self.prescription_basis,
            "hr_paces": {k: [fmt_pace(v[0]), fmt_pace(v[1])] for k, v in self.hr_paces.items()},
            "easy_pace_range": [fmt_pace(self.easy_pace_range[0]),
                                fmt_pace(self.easy_pace_range[1])],
            "observed_easy_run_kmh": self.observed_easy_run_kmh,
            "cadence_by_speed": {str(k): round(v, 1) for k, v in self.cadence_by_speed.items()},
            "ef_baseline": round(self.ef_baseline, 2) if self.ef_baseline else None,
            "strength_findings": self.strength_findings,
            "predictions": {k: round(v) for k, v in self.predictions.items()},
            "predictions_display": {k: _hms(v) for k, v in self.predictions.items()},
            "caveats": self.caveats,
        }


def _hms(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


#: Below this VDOT, Daniels' tables have effectively run out (his published tables start around 30)
#: and the E-pace percentages extrapolate to paces slower than a brisk walk -- which is not a
#: physiological finding, it is the quadratic running out of validity. Beneath this threshold we
#: prescribe from the *measured* HR-speed fit instead of from VDOT. See :func:`hr_derived_paces`.
VDOT_TABLE_FLOOR = 30.0

#: Do not predict a race time more than this multiple of the longest distance actually covered.
#: A marathon prediction extrapolated from a 9 km/h treadmill stage is not a prediction, it is a
#: number with a colon in it -- and a discouraging one.
MAX_PREDICTION_EXTRAPOLATION = 2.5


#: Below this coefficient of determination the HR-speed line is not a line, and the paces implied by
#: its intercept are arithmetic rather than measurement.
#:
#: Discovered by importing an ordinary variable-pace outdoor run: the stage segmenter found apparent
#: plateaus, the fit came back at r2 = 0.31, and the engine cheerfully printed a Z1 recovery pace of
#: "122:14 per kilometre". It *did* also emit a caveat saying the fit was poor -- but a caveat beside
#: an absurd number is not a safeguard. A number that wrong should never be produced at all, because
#: somebody will read the number and not the caveat, and because a stored profile carries the number
#: forward long after the caveat has scrolled away.
MIN_FIT_R2_FOR_PACES = 0.75


def hr_derived_paces(fit: Tuple[float, float, float], zones: ZoneModel,
                     hr_max: float, hr_rest: float) -> Dict[str, Tuple[float, float]]:
    """Pace ranges (s/km) implied by the HR zones and the measured HR-speed fit.

    This is the honest prescription for a true beginner: we *measured* what speed puts this person
    at a given heart rate, so we use that, rather than extrapolating a formula fitted to trained
    runners far outside its range. Returns ``{zone_name: (fast_sec_km, slow_sec_km)}``.

    The fit is only valid across roughly the speeds tested, so each bound is flagged by the caller
    when it required extrapolation beyond the ramp's fastest stage.
    """
    if fit[2] < MIN_FIT_R2_FOR_PACES:
        # No paces at all rather than implausible ones. See MIN_FIT_R2_FOR_PACES.
        return {}
    out: Dict[str, Tuple[float, float]] = {}
    for z in zones.zones:
        try:
            v_lo = speed_at_hr(z.low_bpm, fit)      # lower HR -> slower speed
            v_hi = speed_at_hr(z.high_bpm, fit)
        except ValueError:
            continue
        if v_lo <= 0 or v_hi <= 0:
            continue
        # Faster speed = smaller s/km.
        out[z.name] = (3600.0 / max(v_lo, v_hi), 3600.0 / min(v_lo, v_hi))
    return out


def _predictions(vdot: float, paces: TrainingPaces, *, novice: bool,
                 longest_distance_m: Optional[float] = None) -> Dict[str, float]:
    """Predicted race times. From VDOT-equivalent performances, cross-checked with Riegel.

    For a novice we take the **slower** of the two for anything at or beyond the half marathon,
    because VDOT equivalence assumes the endurance to actually express that fitness over the
    distance -- an assumption a 12-week-old runner has not earned. Being pleasantly surprised on
    race day is strictly better than the alternative.

    Distances beyond :data:`MAX_PREDICTION_EXTRAPOLATION` x ``longest_distance_m`` are **omitted
    entirely** rather than predicted. Showing a beginner a 7.5-hour marathon extrapolated from a
    treadmill ramp is worse than showing nothing: it is not informative, it is not accurate, and
    it is actively demoralising.
    """
    from marathon_engine.physiology import pct_vo2max_for_duration, velocity_at_vo2

    def vdot_time(distance_m: float) -> float:
        """Solve for the time at which this VDOT's sustainable %VO2max matches the required pace."""
        lo, hi = 60.0, 8 * 3600.0
        for _ in range(80):
            mid = (lo + hi) / 2.0
            v_needed = distance_m / (mid / 60.0)                 # m/min
            v_available = velocity_at_vo2(vdot * pct_vo2max_for_duration(mid / 60.0))
            if v_available > v_needed:
                hi = mid          # can go faster -> try a shorter time
            else:
                lo = mid
        return (lo + hi) / 2.0

    out: Dict[str, float] = {}
    base_5k = vdot_time(5000.0)
    ceiling = (longest_distance_m * MAX_PREDICTION_EXTRAPOLATION
               if longest_distance_m else float("inf"))
    for label, dist in (("5k", 5000.0), ("10k", 10000.0),
                        ("half", 21097.5), ("marathon", 42195.0)):
        if dist > ceiling:
            continue
        vd = vdot_time(dist)
        if novice and dist >= 21097.5:
            rg = riegel_predict(5000.0, base_5k, dist, exponent=RIEGEL_NOVICE_EXPONENT)
            vd = max(vd, rg)
        out[label] = vd
    return out


def profile_from_ramp(ramp: RampTest, *, screen: Optional[StrengthScreen] = None,
                      supine_rmssd_ms: Optional[float] = None) -> FitnessProfile:
    """Build the initial :class:`FitnessProfile` from the week-1 battery."""
    hr_max, hr_max_source = estimate_hr_max_from_ramp(ramp)
    vdot, vdot_source = seed_vdot_from_ramp(ramp)
    tt = lt_speed_from_talk_test(ramp)
    lthr = tt[1] if tt else None
    thr_speed = tt[0] if tt else None

    fit: Optional[Tuple[float, float, float]] = None
    try:
        fit = fit_hr_speed(ramp.stages)
    except ValueError:
        fit = None

    zones = five_zone_model(hr_max, ramp.hr_rest, lthr=lthr)
    paces = training_paces(vdot)

    cadence = {s.speed_kmh: s.cadence_spm for s in ramp.stages if s.cadence_spm}
    ef = None
    ref = [s for s in ramp.stages if s.talk == "comfortable"]
    if ref:
        s = ref[-1]
        ef = efficiency_factor(s.speed_m_s, s.steady_hr)

    basis = "hr_from_ramp" if vdot < VDOT_TABLE_FLOOR else "vdot"
    hr_paces = hr_derived_paces(fit, zones, hr_max, ramp.hr_rest) if fit else {}
    fastest_tested = max((s.speed_kmh for s in ramp.stages), default=0.0)
    longest_m = max((s.speed_kmh * 1000.0 / 60.0 * s.duration_min for s in ramp.stages),
                    default=None)

    caveats = [
        "Seed VDOT comes from a SUBMAXIMAL test and is deliberately conservative -- expect it to "
        "rise sharply at the week-4 time trial. Do not chase the early paces.",
        f"HRmax is {'observed during the ramp (still submaximal, so the true max is higher)' if hr_max_source == 'observed' else 'an age-based estimate with roughly +/-7 bpm standard error and up to 20 bpm individual error'}. "
        "Zones will be re-anchored after the first hard time trial.",
        "Marathon prediction uses a novice-adjusted Riegel exponent (1.15, not 1.06) because "
        "low-mileage first-timers fade much harder over the last 12 km than the standard formula "
        "assumes.",
    ]
    if fit and fit[2] < MIN_FIT_R2_FOR_PACES:
        caveats.append(
            f"The HR-speed fit is not usable (r2={fit[2]:.2f}): the points do not lie on a line, so "
            "no paces have been derived from it. That normally means the speeds were not actually "
            "held steady -- an ordinary run rather than a ramp -- or the stages were far too short. "
            "Run `protocol` on a treadmill to get a real one.")
    elif fit and fit[2] < 0.90:
        caveats.append(f"The HR-speed fit is poor (r2={fit[2]:.2f}) -- HR may have been drifting or "
                       "the stages were too short. Re-test before trusting the derived paces.")
    if ramp.temp_c is not None and ramp.temp_c > 22:
        caveats.append(f"Ramp was run at {ramp.temp_c:.0f} C; heat inflates HR at any given speed, "
                       "so this test likely understates fitness. Re-test cooler.")
    if basis == "hr_from_ramp":
        caveats.insert(0, (
            f"Seed VDOT is {vdot:.0f}, below the floor of Daniels' published tables (~30), so the "
            "VDOT pace formulas extrapolate to paces slower than a brisk walk. They are therefore "
            "NOT being used yet: your prescribed paces come from the heart-rate/speed relationship "
            "measured in your own ramp test. That is a better instrument for you right now, and "
            "the plan switches to VDOT automatically once a real time trial puts you above 30."))
    if fit and fastest_tested:
        caveats.append(f"The HR-speed fit was measured between 5 and {fastest_tested:g} km/h. Any "
                       "prescribed pace faster than that is an extrapolation -- the plan does not "
                       "prescribe outside it during the foundation phase.")

    return FitnessProfile(
        as_of=ramp.day, age=ramp.age, hr_rest=ramp.hr_rest, hr_max=hr_max,
        hr_max_source=hr_max_source, vdot=vdot, vdot_source=vdot_source, zones=zones,
        paces=paces, lthr=lthr, threshold_speed_kmh=thr_speed, cadence_by_speed=cadence,
        ef_baseline=ef, ramp_fit=fit,
        strength_findings=screen.findings() if screen else [],
        predictions=_predictions(vdot, paces, novice=True, longest_distance_m=longest_m),
        caveats=caveats, prescription_basis=basis, hr_paces=hr_paces,
    )


def profile_from_time_trial(tt: TimeTrial, previous: FitnessProfile) -> FitnessProfile:
    """Re-derive the profile from a real time trial, carrying forward what the trial cannot measure.

    A maximal trial supersedes the submaximal seed for VDOT *and* is the first legitimate chance to
    observe a true HRmax -- so ``peak_hr`` from a genuinely maximal effort is adopted when it beats
    the current value.
    """
    vdot = tt.vdot
    hr_max, src = previous.hr_max, previous.hr_max_source
    if tt.peak_hr and tt.peak_hr > hr_max:
        hr_max, src = tt.peak_hr, "race"
    # A run that included walk breaks is not a valid maximal continuous performance; treat its
    # VDOT as a floor rather than a measurement.
    vdot_source = "time_trial_with_walk_breaks" if tt.walked else f"time_trial_{int(tt.distance_m)}m"
    if tt.walked:
        vdot = max(previous.vdot, vdot)

    zones = five_zone_model(hr_max, previous.hr_rest, lthr=previous.lthr)
    paces = training_paces(vdot)
    caveats = [c for c in previous.caveats if "Seed VDOT" not in c]
    caveats.insert(0, f"VDOT now from a real {int(tt.distance_m)} m trial on {tt.day.isoformat()}.")
    if tt.distance_m < 3000:
        caveats.append("VDOT from a short trial over-predicts long-distance ability for someone "
                       "without endurance mileage yet -- the 5K trial will be the honest one.")
    # Re-decide the prescription basis: a real trial can still land below the VDOT table floor,
    # and silently switching to extrapolated VDOT paces just because a trial happened would undo
    # the whole point of the floor check.
    basis = "hr_from_ramp" if (vdot < VDOT_TABLE_FLOOR and previous.hr_paces) else "vdot"
    if basis == "hr_from_ramp":
        caveats.append(f"VDOT {vdot:.0f} is still below the table floor ({VDOT_TABLE_FLOOR:.0f}), "
                       "so paces continue to come from your measured HR-speed relationship.")
    #: The longest distance actually covered -- the trial, or a previous longer one.
    longest = max(tt.distance_m, previous.predictions and 0.0 or 0.0)
    return FitnessProfile(
        as_of=tt.day, age=previous.age, hr_rest=previous.hr_rest, hr_max=hr_max,
        hr_max_source=src, vdot=vdot, vdot_source=vdot_source, zones=zones, paces=paces,
        lthr=previous.lthr, threshold_speed_kmh=previous.threshold_speed_kmh,
        cadence_by_speed=dict(previous.cadence_by_speed), ef_baseline=previous.ef_baseline,
        ramp_fit=previous.ramp_fit, strength_findings=previous.strength_findings,
        predictions=_predictions(vdot, paces, novice=tt.distance_m < 21097.5,
                                longest_distance_m=longest),
        caveats=caveats, prescription_basis=basis,
        hr_paces=dict(previous.hr_paces),
    )


#: HRmax capture guards. See :func:`update_hr_max` for why each exists.
HR_MAX_SUSTAIN_S = 15.0          # must hold within +/-3 bpm for this long
HR_MAX_MIN_ELAPSED_S = 300.0     # past the optical sensor's unreliable early window
HR_MAX_CADENCE_MARGIN = 5.0      # must be this far from cadence and cadence/2
HR_MAX_STEP_UNCONFIRMED = 5.0    # max raise per event without chest-strap confirmation
HR_MAX_TOTAL_UNCONFIRMED = 15.0  # max cumulative raise without chest-strap confirmation


@dataclass
class HrMaxCandidate:
    """Evidence for a new maximum heart rate, so the guards can be checked rather than assumed."""
    observed_hr: float
    sustained_s: float
    elapsed_in_session_s: float
    fraction_through_effort: float          # 0..1; 1.0 = at the very end
    cadence_spm: Optional[float] = None
    hr_status: str = "ok"                   # from signal_quality.HrGate
    chest_strap_confirmed: bool = False


def update_hr_max(profile: FitnessProfile, candidate: HrMaxCandidate,
                  *, context: str = "hard session",
                  total_unconfirmed_raise: float = 0.0
                  ) -> Tuple[FitnessProfile, Optional[str], List[str]]:
    """Adopt a higher observed HRmax **only** when every guard passes.

    Returns ``(profile, message, rejections)``.

    An earlier version of this function accepted any observed peak above the current maximum, on the
    reasoning that an observed heart rate is data and a population regression is not. That reasoning
    is right and the implementation was still wrong, because on an *optical armband* the highest
    number in a session is very often not a heart rate at all. A single cadence-lock spike would have
    been adopted as the new maximum, and since every zone boundary is derived from HRmax, one artifact
    would silently shift the entire zone model upward -- turning every prescribed "easy" run into a
    tempo run for weeks, with no visible error anywhere.

    So all of these must hold:

    1. **Sustained** for :data:`HR_MAX_SUSTAIN_S` within a few bpm. A true maximum is held briefly at
       the end of a hard effort; an artifact is a spike.
    2. **Past** :data:`HR_MAX_MIN_ELAPSED_S` into the session. Optical signal quality is at its worst
       in the first minutes, before the sensor and skin have settled.
    3. **Not near cadence or half cadence**, by :data:`HR_MAX_CADENCE_MARGIN`. This is the specific
       artifact being guarded against, so it gets an explicit check rather than relying on the
       upstream gate alone.
    4. **Plausible**: within three standard errors of the age prediction. The Tanaka SEE is ~7 bpm, so
       ~21 bpm of headroom -- generous enough for a genuine outlier, tight enough to reject nonsense.
    5. **In the final quarter of a hard effort.** A maximum reached in the middle of a steady run is
       not a maximum; it is a sensor problem or a different kind of problem.
    6. **Sensor state is clean** -- not dropout, frozen, cadence-locked or warming up.

    And even when all six pass, an **unconfirmed** capture may raise HRmax by at most
    :data:`HR_MAX_STEP_UNCONFIRMED` per event and :data:`HR_MAX_TOTAL_UNCONFIRMED` in total. Only a
    simultaneous chest-strap recording -- a different sensing modality, without this failure mode --
    allows the full observed value to be adopted. The asymmetry is deliberate: too low an HRmax makes
    the plan slightly conservative, while too high a one makes every easy day a hard day.

    **Caller responsibility:** changing HRmax invalidates every historical TRIMP value, because
    Banister TRIMP is a function of heart-rate reserve. Recompute the load history under a new version
    id and keep the old series -- do not silently rewrite it.
    """
    rejections: List[str] = []
    obs = candidate.observed_hr

    if obs <= profile.hr_max:
        return profile, None, ["not higher than the current maximum"]
    if candidate.hr_status != "ok":
        rejections.append(f"sensor state was '{candidate.hr_status}', not clean")
    if candidate.sustained_s < HR_MAX_SUSTAIN_S:
        rejections.append(f"held for only {candidate.sustained_s:.0f} s "
                          f"(need {HR_MAX_SUSTAIN_S:.0f} s) -- looks like a spike, not a maximum")
    if candidate.elapsed_in_session_s < HR_MAX_MIN_ELAPSED_S:
        rejections.append(f"occurred {candidate.elapsed_in_session_s:.0f} s into the session, "
                          f"inside the {HR_MAX_MIN_ELAPSED_S:.0f} s window where optical signal "
                          "quality is least reliable")
    if candidate.cadence_spm:
        for label, ref in (("cadence", candidate.cadence_spm),
                           ("half cadence", candidate.cadence_spm / 2.0)):
            if abs(obs - ref) <= HR_MAX_CADENCE_MARGIN:
                rejections.append(f"within {HR_MAX_CADENCE_MARGIN:.0f} bpm of {label} "
                                  f"({ref:.0f}) -- the classic lock-on artifact")
    ceiling = hr_max_estimate(profile.age) + 3 * TANAKA_SEE_BPM
    if obs > ceiling:
        rejections.append(f"{obs:.0f} bpm exceeds the plausibility ceiling of {ceiling:.0f} "
                          "(age prediction plus three standard errors)")
    if candidate.fraction_through_effort < 0.75:
        rejections.append(f"occurred {candidate.fraction_through_effort*100:.0f}% through the effort; "
                          "a genuine maximum comes at the end")

    if rejections:
        return profile, None, rejections

    # Guards passed. Cap the adopted value unless a chest strap corroborates it.
    if candidate.chest_strap_confirmed:
        new_max = obs
        provenance = "observed_confirmed"
        note = "Confirmed by a simultaneous chest-strap recording, so the full value is adopted."
    else:
        headroom = max(0.0, HR_MAX_TOTAL_UNCONFIRMED - total_unconfirmed_raise)
        step = min(HR_MAX_STEP_UNCONFIRMED, headroom)
        if step <= 0:
            return profile, None, [
                f"all guards passed, but the cumulative unconfirmed raise is already at the "
                f"{HR_MAX_TOTAL_UNCONFIRMED:.0f} bpm limit. Confirm with a chest strap to go further "
                "-- optical peaks alone should not keep pushing the zone model upward."]
        new_max = min(obs, profile.hr_max + step)
        provenance = "observed_capped"
        note = (f"Raised by {new_max - profile.hr_max:.0f} bpm rather than straight to {obs:.0f}: "
                "unconfirmed optical peaks move HRmax in small steps, because one artifact adopted "
                "as a maximum would shift every zone boundary upward.")
    zones = five_zone_model(new_max, profile.hr_rest, lthr=profile.lthr)
    msg = (f"New maximum heart rate: {new_max:.0f} bpm during {context} "
           f"(was {profile.hr_max:.0f}, {profile.hr_max_source}). All HR zones have shifted up. "
           f"{note} Every historical training-load value needs recomputing, because TRIMP is a "
           "function of heart-rate reserve.")
    updated = FitnessProfile(
        as_of=profile.as_of, age=profile.age, hr_rest=profile.hr_rest, hr_max=new_max,
        hr_max_source=provenance, vdot=profile.vdot, vdot_source=profile.vdot_source,
        zones=zones, paces=profile.paces, lthr=profile.lthr,
        threshold_speed_kmh=profile.threshold_speed_kmh,
        cadence_by_speed=dict(profile.cadence_by_speed), ef_baseline=profile.ef_baseline,
        ramp_fit=profile.ramp_fit, strength_findings=profile.strength_findings,
        predictions=profile.predictions, caveats=profile.caveats,
        prescription_basis=profile.prescription_basis, hr_paces=dict(profile.hr_paces),
    )
    return updated, msg, []


def compare_ramps(old: RampTest, new: RampTest) -> Dict[str, object]:
    """Progress between two ramps: HR at matched speeds, EF change, threshold-speed change.

    Only speeds present in *both* tests are compared. This is the core "am I getting fitter?"
    readout, and the honest answer requires matched conditions -- the returned dict includes a
    ``comparable`` flag that goes false when surface or temperature differ enough to matter.
    """
    old_by_speed = {s.speed_kmh: s for s in old.stages}
    matched: List[Dict[str, float]] = []
    for s in new.stages:
        o = old_by_speed.get(s.speed_kmh)
        if not o:
            continue
        matched.append({
            "speed_kmh": s.speed_kmh,
            "hr_before": round(o.steady_hr, 1),
            "hr_after": round(s.steady_hr, 1),
            "hr_delta": round(s.steady_hr - o.steady_hr, 1),
            "ef_before": round(efficiency_factor(o.speed_m_s, o.steady_hr), 2),
            "ef_after": round(efficiency_factor(s.speed_m_s, s.steady_hr), 2),
        })

    temp_gap = (abs((new.temp_c or 0) - (old.temp_c or 0))
                if (new.temp_c is not None and old.temp_c is not None) else 0.0)
    comparable = new.surface == old.surface and temp_gap <= 5.0
    mean_hr_delta = statistics.fmean([m["hr_delta"] for m in matched]) if matched else None

    verdict = "insufficient_overlap"
    if mean_hr_delta is not None:
        if mean_hr_delta <= -4.0:
            verdict = "clearly_fitter"
        elif mean_hr_delta <= -1.5:
            verdict = "fitter"
        elif mean_hr_delta < 1.5:
            verdict = "unchanged"
        else:
            verdict = "worse_or_confounded"

    notes: List[str] = []
    if not comparable:
        notes.append(f"Conditions differ (surface {old.surface}->{new.surface}, "
                     f"temp gap {temp_gap:.0f} C). Interpret with caution -- heat alone moves "
                     "submaximal HR by several bpm.")
    if verdict == "worse_or_confounded":
        notes.append("Higher HR at the same speeds usually means heat, dehydration, "
                     "under-recovery or illness before it means lost fitness. Check the "
                     "readiness trend for that week before concluding anything.")
    return {"matched": matched, "mean_hr_delta": (round(mean_hr_delta, 1)
                                                 if mean_hr_delta is not None else None),
            "verdict": verdict, "comparable": comparable, "notes": notes}


def ramp_protocol(age: float, hr_rest: float, *, start_kmh: float = 5.0,
                  step_kmh: float = 1.0, n_stages: int = 5) -> Dict[str, object]:
    """The instructions for running the ramp, with the stop rules made explicit.

    Speeds start at a brisk walk and step up by 1 km/h. For someone who has not run a 5K, stages
    4 and 5 will already be a jog, and it is entirely expected to stop early -- **stopping early is
    a valid result**, not a failure, because the HR-speed fit only needs three usable stages.
    """
    hr_max = hr_max_estimate(age)
    stop_hr = hr_at_reserve_fraction(RAMP_STOP_HRR, hr_max, hr_rest)
    stages = []
    for i in range(n_stages):
        kmh = start_kmh + i * step_kmh
        stages.append({"stage": i + 1, "speed_kmh": round(kmh, 1),
                       "pace_per_km": fmt_pace(3600.0 / kmh),
                       "duration_min": RAMP_STAGE_MIN,
                       "mode": "walk" if kmh <= 6.5 else "jog"})
    return {
        "warmup": "5 min easy walk at 4.5 km/h, then start stage 1 without stopping.",
        "stages": stages,
        "at_each_stage_end": [
            "Record the mean HR over the FINAL 60 seconds (HR needs 2-3 min to plateau).",
            "Rate effort on the Borg 6-20 scale.",
            "Talk test: say a full sentence out loud and rate it comfortable / effortful / impossible.",
        ],
        "stop_when_any": [
            f"HR reaches {stop_hr:.0f} bpm ({RAMP_STOP_HRR*100:.0f}% of heart-rate reserve)",
            f"RPE reaches {RAMP_STOP_RPE}/20",
            "Speech becomes impossible",
            "Any chest pain, light-headedness, or a sense that something is wrong -- stop immediately",
        ],
        "cooldown": "5 min walk, then stand still for 60 s and record HR (recovery marker).",
        "estimated_hr_max_used": round(hr_max, 1),
        "stop_hr": round(stop_hr, 1),
        "why_submaximal": (
            "A maximal test in week 1 risks injury on untrained tissue and measures discomfort "
            "tolerance as much as fitness. Three good submaximal stages give us the HR-speed "
            "relationship, which is all the planner needs to start."),
    }


#: Race distances in order of how much they tell you about marathon readiness, longest first.
#: VDOT is re-derived from the **best available** result by this precedence and is **never averaged
#: across distances**. Averaging a 2000 m trial with a half marathon produces a number that describes
#: neither: the shorter effort systematically over-estimates long-distance ability in someone without
#: endurance mileage, and blending the two just hides that.
TT_PRECEDENCE: Tuple[float, ...] = (42195.0, 21097.5, 10000.0, 5000.0, 2000.0, 1609.34)


def best_time_trial(trials: Sequence[TimeTrial], *,
                    max_age_days: int = 180) -> Optional[TimeTrial]:
    """Pick the trial VDOT should be derived from: longest distance first, most recent within that.

    ``max_age_days`` exists because a six-month-old result describes a different athlete. A stale
    long-distance result does not outrank a fresh shorter one -- so anything older than the window is
    dropped before precedence is applied, rather than winning on distance alone.

    Walked trials are excluded from selection entirely: a run with walk breaks is not a valid maximal
    continuous performance, and :func:`profile_from_time_trial` already treats its VDOT as a floor
    rather than a measurement.
    """
    if not trials:
        return None
    newest = max(t.day for t in trials)
    fresh = [t for t in trials
             if (newest - t.day).days <= max_age_days and not t.walked]
    if not fresh:
        return None
    for distance in TT_PRECEDENCE:
        at_distance = [t for t in fresh if abs(t.distance_m - distance) / distance < 0.05]
        if at_distance:
            return max(at_distance, key=lambda t: t.day)
    # An unrecognised distance still beats nothing; take the longest, then the most recent.
    return max(fresh, key=lambda t: (t.distance_m, t.day))
