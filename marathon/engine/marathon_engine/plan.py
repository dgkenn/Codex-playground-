"""The periodisation engine: gate-based phases, weekly templates, and progression arithmetic.

Why gates instead of a calendar
-------------------------------
The athlete has no fixed race date. That is a gift, and the plan is built to exploit it: phases
advance when **measured criteria** are met, not when a week number ticks over. A calendar plan for
a beginner has to guess the adaptation rate in advance and then either rushes a slow adapter into
a stress fracture or holds a fast adapter back for months. A gated plan cannot do either. Every
phase below has explicit, checkable entry gates (:class:`Gate`), and :func:`evaluate_gates` reports
exactly which ones are outstanding and what to do about each.

The one thing gates must not become is a stall: :data:`PHASE_MIN_WEEKS` sets a *floor* on time in
each phase (bone and tendon adapt on a timescale of weeks regardless of how good the numbers look
-- fitness outruns structure, which is the mechanism behind most novice stress injuries), and
:data:`PHASE_STALL_WEEKS` triggers a diagnostic when a gate has not moved in a long time.

The 3-runs-per-week constraint, stated honestly
-----------------------------------------------
Three runs a week is a real constraint and it has a real cost, which this module does not paper
over. Standard guidance keeps the long run at 30-35% of weekly volume; on three runs a week a
marathon-capable long run is unavoidably 40-50% of the week. The precedent for making this work is
the **Furman FIRST** programme (Pierce, Murr & Moss, *Run Less, Run Faster*), which is 3 quality
runs plus 2 cross-training days, and the associated studies found 3-runs-per-week training with
hard cross-training maintained or improved performance versus higher-frequency plans
(Pierce et al. 2011; Bacon et al.). So the shape is defensible, with three deliberate adjustments:

1. The long run is capped by **time**, not distance (:data:`LONG_RUN_MAX_MIN`), because 3 hours on
   feet is where the injury and recovery cost curve bends sharply upward for a novice, and a slow
   runner hits 3 hours well before 32 km.
2. The user already lifts twice a week, so strength is *integrated* rather than added -- and the
   two lifting days double as the FIRST-style cross-training slots for aerobic volume the runs
   cannot supply.
3. From :data:`Phase.MARATHON_BASE` onward the plan **offers an optional fourth easy run**, flagged
   as the single highest-yield change if a time goal ever replaces "finish strong". It is offered,
   never required, and the gates never depend on it.

Other sources behind the arithmetic
-----------------------------------
* **Intensity distribution** — Seiler & Kjerland 2006; Esteve-Lanao 2007, *J Strength Cond Res*
  21:943 (polarised beat threshold-heavy in trained runners). We hold ~80% of *time* below LT1,
  measured in the Seiler 3-zone model, and for the first two phases it is closer to 100%.
* **Taper** — Bosquet, Montpetit, Arvisais & Mujika 2007, *Med Sci Sports Exerc* 39:1358:
  meta-analysis; the best performance gains came from a **2-week** taper with a **41-60% reduction
  in volume**, while **maintaining intensity and frequency**. :func:`taper_weeks` implements
  exactly that and deliberately does not cut intensity.
* **Volume ramp** — see :data:`marathon_engine.load.MAX_WEEKLY_RAMP` for why the "10% rule" is
  enforced as a cap despite Buist et al. 2008 finding no benefit from a graded programme.
* **Cutback weeks** — every 4th week reduces volume; the mechanism (allowing slow tissue to catch
  up with fast fitness) is well accepted even though the specific 3:1 cadence is convention rather
  than trial-tested. Labelled accordingly.
* **Strength training** — Lauersen, Bertelsen & Andersen 2014, *Br J Sports Med* 48:871, and
  Lauersen et al. 2018, *Br J Sports Med* 52:1557: strength training reduced overuse injuries
  substantially (the 2018 review reports large risk reductions, and unlike stretching the effect is
  consistent). Blagrove, Howatson & Hayes 2018, *Sports Med* 48:1117: strength training improves
  running economy without hypertrophy penalties in distance runners. This is why the two lifting
  days are treated as load-bearing parts of the plan, not optional extras.

Pure functions and dataclasses; no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from marathon_engine.assessment import FitnessProfile
from marathon_engine.load import MAX_WEEKLY_RAMP
from marathon_engine.physiology import VDOT_IR_FLOOR, TrainingPaces, fmt_pace

__all__ = [
    "Phase", "SessionType", "Session", "PlannedWeek", "PlanConfig", "Gate", "GateReport",
    "PHASE_ORDER", "PHASE_MIN_WEEKS", "PHASE_STALL_WEEKS", "PHASE_GATES", "PHASE_GOALS",
    "LONG_RUN_MAX_MIN", "LONG_RUN_MAX_SHARE", "CUTBACK_EVERY", "CUTBACK_FACTOR",
    "TAPER_VOLUME_CUT", "TAPER_WEEKS", "LONG_RUN_PEAK_MAX_MIN", "LONG_RUN_MAX_KM",
    "generate_week", "evaluate_gates", "taper_weeks",
    "long_run_progression", "weekly_volume_target", "phase_overview",
]


class Phase(str, Enum):
    """Training phases, in order. Values are stable identifiers for persistence."""
    ASSESS = "assess"                    # week 1: diagnostics only
    FOUNDATION = "foundation"            # run-walk -> 30 min continuous
    BASE_1 = "base_1"                    # consistent aerobic volume -> first 5K
    BASE_2 = "base_2"                    # volume + threshold introduction -> 10K
    HALF_BUILD = "half_build"            # -> half marathon
    MARATHON_BASE = "marathon_base"      # long-run development
    MARATHON_PEAK = "marathon_peak"      # marathon-pace specificity
    TAPER = "taper"
    RACE = "race"
    RECOVERY = "recovery"


PHASE_ORDER: Tuple[Phase, ...] = (
    Phase.ASSESS, Phase.FOUNDATION, Phase.BASE_1, Phase.BASE_2, Phase.HALF_BUILD,
    Phase.MARATHON_BASE, Phase.MARATHON_PEAK, Phase.TAPER, Phase.RACE, Phase.RECOVERY,
)

#: Minimum weeks in each phase regardless of how good the numbers look. Connective tissue and bone
#: remodel on a slower clock than VO2max: cardiorespiratory fitness improves in 2-3 weeks while
#: bone takes months, and that mismatch is the mechanism of the classic week-6-to-12 novice stress
#: injury. These floors exist to stop good HRV and a rising VDOT from talking us into a ramp the
#: skeleton has not earned.
PHASE_MIN_WEEKS: Dict[Phase, int] = {
    Phase.ASSESS: 1, Phase.FOUNDATION: 6, Phase.BASE_1: 8, Phase.BASE_2: 8,
    Phase.HALF_BUILD: 10, Phase.MARATHON_BASE: 10, Phase.MARATHON_PEAK: 6,
    Phase.TAPER: 2, Phase.RACE: 1, Phase.RECOVERY: 3,
}

#: If a phase's gates have not been met after this many weeks, stop adding load and run the
#: diagnostic in :func:`evaluate_gates` -- something is wrong (under-fuelling, a niggle being
#: trained through, chronic sleep debt, or a plan that is simply too aggressive for now).
PHASE_STALL_WEEKS: Dict[Phase, int] = {
    Phase.FOUNDATION: 14, Phase.BASE_1: 18, Phase.BASE_2: 18,
    Phase.HALF_BUILD: 22, Phase.MARATHON_BASE: 24, Phase.MARATHON_PEAK: 12,
}

PHASE_GOALS: Dict[Phase, str] = {
    Phase.ASSESS: "Find out where you actually are. No hard running.",
    Phase.FOUNDATION: "Run 30 minutes continuously, comfortably, in Z2.",
    Phase.BASE_1: "Make running a habit and finish a 5K. Volume, not speed.",
    Phase.BASE_2: "Add your first real threshold work and race a 10K.",
    Phase.HALF_BUILD: "Build the long run and race a half marathon.",
    Phase.MARATHON_BASE: "Develop marathon-specific endurance: the long run is the point.",
    Phase.MARATHON_PEAK: "Rehearse race day -- marathon pace, fuelling, and the long run at size.",
    Phase.TAPER: "Cut volume, keep intensity, arrive fresh.",
    Phase.RACE: "Run the marathon.",
    Phase.RECOVERY: "Do almost nothing, on purpose.",
}


class SessionType(str, Enum):
    REST = "rest"
    RUN_WALK = "run_walk"
    EASY = "easy"
    LONG = "long"
    STEADY = "steady"
    THRESHOLD = "threshold"
    INTERVALS = "intervals"
    HILLS = "hills"
    STRIDES = "strides"
    MARATHON_PACE = "marathon_pace"
    STRENGTH = "strength"
    CROSS = "cross"
    TIME_TRIAL = "time_trial"
    RACE = "race"
    RAMP_TEST = "ramp_test"


#: Long run ceilings. The time cap is the operative one for a novice.
#:
#: **150 minutes, not 180.** Daniels' actual rule is that the long run should be no more than the
#: LESSER of 25% of weekly mileage or **150 minutes** (30% for runners under 40 mpw). An earlier
#: version of this file used 180 min on the strength of the widely-repeated "3 hour" convention,
#: which exceeds Daniels' own limit by 20% -- and it did so in exactly the population least able to
#: absorb it. Past about two and a half hours the musculoskeletal damage, glycogen depletion and
#: recovery cost all turn sharply nonlinear, and for a first marathon the extra half hour buys very
#: little that the preceding two hours have not already bought.
LONG_RUN_MAX_MIN = 150.0

#: The one place a longer run is allowed: the two or three biggest runs of the peak phase, where
#: rehearsing the back half of the race has specific value that no shorter run provides. Still
#: capped well short of race duration -- nobody needs to run a marathon in training.
LONG_RUN_PEAK_MAX_MIN = 165.0
LONG_RUN_MAX_KM = 32.0
#: On three runs a week the long run genuinely cannot stay at the textbook 30-35% of weekly volume.
#: We allow up to 50% and treat that as the explicit cost of the 3-day schedule.
LONG_RUN_MAX_SHARE = 0.50

#: Which week of BASE_1 carries the 2000 m time trial. Four weeks of continuous running first: a
#: maximal effort is reasonable once the tissue has adapted to running at all, and not before.
_TIME_TRIAL_WEEK = 5

CUTBACK_EVERY = 4           # every 4th week is a cutback [convention, not trial-tested]
CUTBACK_FACTOR = 0.70       # volume x0.70 on a cutback week

#: Bosquet 2007: 41-60% volume reduction over 2 weeks, intensity and frequency maintained.
TAPER_VOLUME_CUT = (0.50, 0.30)   # week -2 runs 50% of peak, race week 30%
TAPER_WEEKS = 2


@dataclass
class Session:
    """One planned session. Targets are ranges, because a single number invites false precision."""
    day_offset: int                      # 0 = Monday of the plan week
    type: SessionType
    title: str
    duration_min: Optional[float] = None
    distance_km: Optional[float] = None
    #: Target HR zone indices (five-zone model), e.g. ``[1, 2]`` for easy.
    zones: Tuple[int, ...] = ()
    pace_target_sec_km: Optional[float] = None
    pace_range_sec_km: Optional[Tuple[float, float]] = None
    structure: str = ""                  # human-readable workout structure
    intent: str = ""                     # WHY this session exists
    #: Run-walk pattern, when applicable: ``(run_min, walk_min, repeats)``
    run_walk: Optional[Tuple[float, float, int]] = None
    optional: bool = False
    fuelling: str = ""
    cues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"day_offset": self.day_offset, "type": self.type.value, "title": self.title,
             "duration_min": self.duration_min, "distance_km": self.distance_km,
             "zones": list(self.zones), "structure": self.structure, "intent": self.intent,
             "optional": self.optional, "cues": self.cues}
        if self.pace_target_sec_km:
            d["pace_target"] = fmt_pace(self.pace_target_sec_km)
        if self.pace_range_sec_km:
            d["pace_range"] = [fmt_pace(self.pace_range_sec_km[0]),
                               fmt_pace(self.pace_range_sec_km[1])]
        if self.run_walk:
            d["run_walk"] = {"run_min": self.run_walk[0], "walk_min": self.run_walk[1],
                             "repeats": self.run_walk[2]}
        if self.fuelling:
            d["fuelling"] = self.fuelling
        return d


@dataclass
class PlannedWeek:
    week_index: int                      # global week number, 1-based
    phase: Phase
    week_in_phase: int
    sessions: List[Session]
    volume_target_km: Optional[float] = None
    volume_target_min: Optional[float] = None
    is_cutback: bool = False
    focus: str = ""
    notes: List[str] = field(default_factory=list)

    @property
    def running_sessions(self) -> List[Session]:
        return [s for s in self.sessions
                if s.type not in (SessionType.REST, SessionType.STRENGTH, SessionType.CROSS)]

    def to_dict(self) -> dict:
        return {"week_index": self.week_index, "phase": self.phase.value,
                "week_in_phase": self.week_in_phase, "is_cutback": self.is_cutback,
                "volume_target_km": (round(self.volume_target_km, 1)
                                     if self.volume_target_km else None),
                "volume_target_min": (round(self.volume_target_min)
                                      if self.volume_target_min else None),
                "focus": self.focus, "notes": self.notes,
                "sessions": [s.to_dict() for s in self.sessions]}


@dataclass
class PlanConfig:
    """The athlete's constraints. Defaults are this user's answers."""
    run_days_per_week: int = 3
    strength_days_per_week: int = 2
    #: Preferred weekdays, Mon=0. These are this athlete's actual days: Wednesday, Saturday, Sunday.
    #:
    #: The Saturday/Sunday pair is worth a note, because it looks like a scheduling compromise and is
    #: actually an advantage. Running the long run on Sunday off an easy Saturday means it starts on
    #: mildly pre-fatigued legs, which is a *marathon-specific* stimulus -- the same reasoning behind
    #: back-to-back long runs in ultra training, at a much gentler dose. The cost is that Saturday
    #: must stay genuinely easy; if Saturday creeps up in effort, Sunday stops being a long run and
    #: becomes the second half of a two-day hard block.
    #:
    #: Quality therefore goes on Wednesday, three days clear of the long run in both directions. That
    #: is the widest spacing this three-day pattern allows, and it is why Wednesday gets the workout
    #: rather than Saturday.
    long_run_day: int = 6
    run_days: Tuple[int, ...] = (2, 5, 6)        # Wed, Sat, Sun
    strength_days: Tuple[int, ...] = (0, 3)      # Mon, Thu -- clear of Wed quality and Sun long
    already_lifting: bool = True
    offer_fourth_run: bool = True
    metric: bool = True
    #: Hard ceiling the athlete sets on weekly volume, if any.
    max_weekly_km: Optional[float] = None
    #: Time available for the longest run, in minutes.
    max_long_run_min: float = LONG_RUN_MAX_MIN

    def to_dict(self) -> dict:
        return {"run_days_per_week": self.run_days_per_week,
                "strength_days_per_week": self.strength_days_per_week,
                "run_days": list(self.run_days), "strength_days": list(self.strength_days),
                "long_run_day": self.long_run_day, "already_lifting": self.already_lifting,
                "offer_fourth_run": self.offer_fourth_run,
                "max_weekly_km": self.max_weekly_km,
                "max_long_run_min": self.max_long_run_min}


# ----------------------------------------------------------------------------------------
# Gates
# ----------------------------------------------------------------------------------------


@dataclass
class Gate:
    """One advancement criterion.

    ``key`` names the metric in the evidence dict passed to :func:`evaluate_gates`; ``op`` and
    ``value`` form the comparison. ``rationale`` is shown to the athlete, because a gate you do
    not understand feels like an arbitrary obstacle.
    """
    key: str
    op: str                              # ">=" | "<=" | "==" | "true"
    value: object
    label: str
    rationale: str
    #: A gate marked ``safety`` can never be waived, even manually.
    safety: bool = False

    def check(self, evidence: Dict[str, object]) -> Optional[bool]:
        """``True``/``False``, or ``None`` when the evidence is absent (unknown, not failed)."""
        if self.key not in evidence or evidence[self.key] is None:
            return None
        got = evidence[self.key]
        if self.op == "true":
            return bool(got)
        try:
            if self.op == ">=":
                return float(got) >= float(self.value)      # type: ignore[arg-type]
            if self.op == "<=":
                return float(got) <= float(self.value)       # type: ignore[arg-type]
            if self.op == "==":
                return got == self.value
        except (TypeError, ValueError):
            return None
        raise ValueError(f"unknown op {self.op!r}")

    def to_dict(self) -> dict:
        return {"key": self.key, "op": self.op, "value": self.value, "label": self.label,
                "rationale": self.rationale, "safety": self.safety}


_PAIN_GATE = Gate("max_pain_2wk", "<=", 2, "No pain above 2/10 for two weeks",
                  "The pain-monitoring model treats 0-2/10 as acceptable, 3-5/10 as a warning to "
                  "hold volume, and anything above 5/10 as a stop. Two clean weeks means the "
                  "tissue is tolerating the current load, which is the precondition for adding "
                  "more.", safety=True)

_CONSISTENCY_GATE = Gate("sessions_completed_pct_4wk", ">=", 0.80,
                         "80% of planned sessions completed over 4 weeks",
                         "Consistency is the variable that actually predicts progress. Advancing "
                         "a phase on the strength of a good fortnight inside a patchy block just "
                         "moves the problem forward.")

PHASE_GATES: Dict[Phase, Tuple[Gate, ...]] = {
    Phase.ASSESS: (
        Gate("medical_screen_cleared", "true", True, "Pre-participation screening cleared",
             "The ACSM screening algorithm, applied once before anything else. It exists to catch "
             "the small number of people who need clearance -- exertional chest discomfort, unusual "
             "breathlessness, exertional dizziness, or known cardiovascular/metabolic/renal "
             "disease -- not to put a barrier in front of exercise. Nothing else in this plan runs "
             "until it passes, because the plan eventually asks for a maximal effort.",
             safety=True),
        Gate("ramp_test_done", "true", True, "Graded ramp test completed",
             "Everything downstream -- zones, paces, the efficiency baseline -- is derived from it."),
        Gate("strength_screen_done", "true", True, "Structural screen completed",
             "Finds the specific weak link (usually calf endurance) before load exposes it."),
        Gate("hrv_baseline_nights", ">=", 7, "At least 7 nights of HRV data",
             "The readiness engine needs a personal baseline; a population norm is useless here."),
    ),
    Phase.FOUNDATION: (
        Gate("continuous_run_min", ">=", 30, "30 minutes of continuous running",
             "The classic couch-to-5K endpoint and the precondition for structured aerobic work."),
        Gate("continuous_run_in_z2", "true", True, "That 30 minutes stayed in Z1-Z2",
             "Running 30 minutes is not the same as running 30 aerobic minutes. If it needed Z4, "
             "the aerobic base is not there yet and threshold work would be wasted on you."),
        _PAIN_GATE,
        _CONSISTENCY_GATE,
    ),
    Phase.BASE_1: (
        Gate("weekly_km_3wk_min", ">=", 20, "20+ km/week for three consecutive weeks",
             "A stable floor of aerobic volume, held long enough to be real rather than a spike."),
        Gate("time_trial_2000m_done", "true", True, "2000 m time trial completed",
             "The first honest performance measurement, and 2000 m rather than 5K on purpose. It "
             "takes a beginner roughly 11-12 minutes, which sits comfortably inside Riegel's "
             "validated 3.5-230 minute window AND inside the range where Daniels' sustainable-"
             "%VO2max curve is well behaved. A 5K at this stage is a longer maximal effort on less "
             "prepared tissue for a *worse* VDOT estimate. The 5K becomes the next checkpoint, not "
             "the first one."),
        Gate("calf_raises_min", ">=", 20, "20+ single-leg calf raises per side",
             "Calf-Achilles endurance is the most common structural limiter in new runners and the "
             "one most likely to fail as volume climbs.", safety=True),
        _PAIN_GATE,
        _CONSISTENCY_GATE,
    ),
    Phase.BASE_2: (
        Gate("weekly_km_3wk_min", ">=", 32, "32+ km/week for three consecutive weeks",
             "The volume floor that makes threshold work productive instead of merely tiring."),
        Gate("long_run_km", ">=", 14, "A 14 km long run completed",
             "Roughly a third of the marathon distance -- the checkpoint before half-marathon work."),
        Gate("five_k_completed", "true", True, "5K completed continuously",
             "Recalibrates VDOT over a duration where aerobic endurance starts to show, and the "
             "first race-distance checkpoint."),
        Gate("long_run_decoupling", "<=", 0.08, "Long-run decoupling under 8%",
             "Heart rate drifting hard relative to pace on a long run means the aerobic base is "
             "still thin, whatever the 10K time says. Under 5% is the target; 8% is the gate."),
        _PAIN_GATE,
        _CONSISTENCY_GATE,
    ),
    Phase.HALF_BUILD: (
        Gate("weekly_km_3wk_min", ">=", 42, "42+ km/week for three consecutive weeks",
             "The base a marathon block is built on. Going into marathon-specific work below this "
             "is the single most common reason first marathons go badly."),
        Gate("ten_k_completed", "true", True, "10K completed",
             "The first legitimate Riegel input. Below 10K the extrapolation to marathon distance "
             "spans too large a distance ratio to mean much, which is why no marathon prediction "
             "appears before this."),
        Gate("long_run_km", ">=", 20, "A 20 km long run completed", "Half-marathon readiness."),
        Gate("half_completed", "true", True, "Half marathon completed",
             "The best available predictor of marathon readiness, and a rehearsal of fuelling, "
             "pacing and kit at a distance where mistakes are survivable."),
        _PAIN_GATE,
        _CONSISTENCY_GATE,
    ),
    Phase.MARATHON_BASE: (
        Gate("long_runs_over_26km", ">=", 3, "Three long runs of 26 km or more",
             "Time on feet is the specific adaptation the marathon demands, and one long run does "
             "not build it."),
        Gate("long_run_decoupling", "<=", 0.06, "Long-run decoupling under 6%",
             "Aerobic durability at duration -- the thing that decides whether the last 10 km is "
             "running or survival."),
        Gate("weekly_km_3wk_min", ">=", 48, "48+ km/week for three consecutive weeks",
             "Peak-phase volume floor for a 3-day-a-week schedule with cross-training."),
        _PAIN_GATE,
        _CONSISTENCY_GATE,
    ),
    Phase.MARATHON_PEAK: (
        Gate("mp_long_run_done", ">=", 2, "Two long runs with marathon-pace segments",
             "Rehearses race pace on tired legs, which is the only way to know it is realistic."),
        Gate("longest_run_min", ">=", 150, "A long run of 150+ minutes",
             "Time on feet matters more than distance for a first marathon."),
        Gate("fuelling_rehearsed", "true", True, "Race fuelling rehearsed on two long runs",
             "The gut is trainable and untrained guts fail at 30 km. Practise the exact products "
             "and timing you will use.", safety=True),
        _PAIN_GATE,
    ),
}


@dataclass
class GateReport:
    phase: Phase
    weeks_in_phase: int
    met: List[Dict[str, object]]
    unmet: List[Dict[str, object]]
    unknown: List[Dict[str, object]]
    min_weeks_satisfied: bool
    can_advance: bool
    stalled: bool
    next_phase: Optional[Phase]
    guidance: str = ""
    diagnostics: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"phase": self.phase.value, "weeks_in_phase": self.weeks_in_phase,
                "met": self.met, "unmet": self.unmet, "unknown": self.unknown,
                "min_weeks_satisfied": self.min_weeks_satisfied,
                "can_advance": self.can_advance, "stalled": self.stalled,
                "next_phase": self.next_phase.value if self.next_phase else None,
                "guidance": self.guidance, "diagnostics": self.diagnostics}


def evaluate_gates(phase: Phase, weeks_in_phase: int,
                   evidence: Dict[str, object]) -> GateReport:
    """Check a phase's gates against measured evidence.

    Advancement requires **all** gates met **and** the minimum weeks served. Unknown evidence
    counts as not-met for advancement but is reported separately, because "we have not measured
    this yet" needs a different response ("go do the 5K") from "you measured it and fell short"
    ("here is why and what changes").
    """
    gates = PHASE_GATES.get(phase, ())
    met, unmet, unknown = [], [], []
    for g in gates:
        res = g.check(evidence)
        row = {**g.to_dict(), "observed": evidence.get(g.key)}
        (met if res is True else unmet if res is False else unknown).append(row)

    min_weeks = PHASE_MIN_WEEKS.get(phase, 0)
    min_ok = weeks_in_phase >= min_weeks
    can = min_ok and not unmet and not unknown
    stall_at = PHASE_STALL_WEEKS.get(phase)
    stalled = bool(stall_at and weeks_in_phase >= stall_at and (unmet or unknown))

    idx = PHASE_ORDER.index(phase)
    nxt = PHASE_ORDER[idx + 1] if idx + 1 < len(PHASE_ORDER) else None

    if can:
        guidance = (f"All gates met and {weeks_in_phase} weeks served -- advance to "
                    f"{nxt.value if nxt else 'the end'}.")
    elif not min_ok:
        remaining = min_weeks - weeks_in_phase
        guidance = (f"{'Gates met' if not unmet and not unknown else 'Progressing'}, but "
                    f"{remaining} more week(s) in {phase.value} first. Bone and tendon adapt more "
                    "slowly than heart and lungs; this floor is the whole point of the plan.")
    elif unknown and not unmet:
        guidance = ("Nothing has failed -- some evidence is simply missing: "
                    + ", ".join(u["label"] for u in unknown) + ".")
    else:
        guidance = "Outstanding: " + ", ".join(u["label"] for u in unmet) + "."

    diagnostics: List[str] = []
    if stalled:
        diagnostics = [
            "Hold volume where it is rather than adding -- a stalled gate plus rising load is how "
            "an overuse injury gets built.",
            "Check the readiness trend: a chronically suppressed HRV baseline or persistent sleep "
            "debt will cap adaptation no matter how the sessions are arranged.",
            "Check energy availability. Under-fuelling looks exactly like 'not adapting' and is "
            "the most common invisible cause, especially on a resident's schedule.",
            "Check whether a low-grade niggle is quietly capping every session.",
            "If the gate is a race checkpoint, the answer may just be that no race has been run -- "
            "schedule it.",
        ]
    return GateReport(phase=phase, weeks_in_phase=weeks_in_phase, met=met, unmet=unmet,
                      unknown=unknown, min_weeks_satisfied=min_ok, can_advance=can,
                      stalled=stalled, next_phase=nxt, guidance=guidance, diagnostics=diagnostics)


# ----------------------------------------------------------------------------------------
# Volume and long-run progression
# ----------------------------------------------------------------------------------------

#: Per-phase weekly volume corridors, in km, for a 3-runs-per-week schedule.
#: ``FOUNDATION`` is governed by *minutes* instead -- see :func:`weekly_volume_target`.
_PHASE_VOLUME_KM: Dict[Phase, Tuple[float, float]] = {
    Phase.BASE_1: (14.0, 26.0),
    Phase.BASE_2: (26.0, 38.0),
    Phase.HALF_BUILD: (38.0, 48.0),
    Phase.MARATHON_BASE: (46.0, 58.0),
    Phase.MARATHON_PEAK: (52.0, 62.0),
}

#: FOUNDATION is run in minutes of *running* (excluding walk breaks), because distance at this
#: stage is dominated by how much of the session is walking and is therefore a bad target.
_FOUNDATION_MIN: Tuple[float, float] = (45.0, 105.0)


def weekly_volume_target(phase: Phase, week_in_phase: int, *,
                         phase_length_est: int = 8,
                         previous_week_volume: Optional[float] = None,
                         config: Optional[PlanConfig] = None,
                         is_cutback: bool = False) -> Tuple[Optional[float], Optional[float]]:
    """Target volume for a week: ``(km, minutes)`` -- exactly one of which is set.

    Progression is linear across the phase corridor, then clamped by the week-over-week ramp cap
    (:data:`~marathon_engine.load.MAX_WEEKLY_RAMP`) and by any athlete-set ceiling. Cutback weeks
    scale by :data:`CUTBACK_FACTOR` and are exempt from the ramp cap on the way back *up* the
    following week -- returning to the pre-cutback volume is not a real 30% increase in load.
    """
    cfg = config or PlanConfig()
    if phase == Phase.FOUNDATION:
        lo, hi = _FOUNDATION_MIN
        frac = min(1.0, max(0.0, (week_in_phase - 1) / max(1, phase_length_est - 1)))
        target = lo + (hi - lo) * frac
        if is_cutback:
            target *= CUTBACK_FACTOR
        return None, round(target, 1)

    if phase in (Phase.ASSESS, Phase.RACE, Phase.RECOVERY, Phase.TAPER):
        return None, None

    lo, hi = _PHASE_VOLUME_KM[phase]
    frac = min(1.0, max(0.0, (week_in_phase - 1) / max(1, phase_length_est - 1)))
    target = lo + (hi - lo) * frac
    if is_cutback:
        target *= CUTBACK_FACTOR
    elif previous_week_volume and previous_week_volume > 0:
        cap = previous_week_volume * (1.0 + MAX_WEEKLY_RAMP)
        # Do not let the ramp cap block recovery of volume after a cutback week.
        target = min(target, max(cap, lo))
    if cfg.max_weekly_km:
        target = min(target, cfg.max_weekly_km)
    return round(target, 1), None


def long_run_progression(phase: Phase, week_in_phase: int, weekly_km: Optional[float],
                         paces: TrainingPaces, *, config: Optional[PlanConfig] = None,
                         is_cutback: bool = False) -> Tuple[Optional[float], float, List[str]]:
    """``(distance_km, duration_min, notes)`` for this week's long run.

    Three ceilings apply, and the binding one is reported in ``notes`` so the athlete can see why
    the long run stopped growing:

    1. :data:`LONG_RUN_MAX_SHARE` of weekly volume,
    2. the time cap (``config.max_long_run_min``, default :data:`LONG_RUN_MAX_MIN`),
    3. :data:`LONG_RUN_MAX_KM`.
    """
    cfg = config or PlanConfig()
    notes: List[str] = []
    if weekly_km is None:
        return None, 0.0, notes

    # Daniels' share rule tightens as volume rises: 30% under 40 km/week, 25% at or above it. Our
    # 3-run schedule cannot always honour that (see LONG_RUN_MAX_SHARE), but the ceiling should at
    # least move in the right direction rather than staying loose at high volume.
    daniels_share = 0.30 if weekly_km < 40.0 else 0.25

    # The time cap is 150 min everywhere except the peak phase's biggest runs.
    time_cap = cfg.max_long_run_min
    if phase == Phase.MARATHON_PEAK:
        time_cap = max(time_cap, LONG_RUN_PEAK_MAX_MIN)

    share = 0.35 + min(0.15, 0.02 * (week_in_phase - 1))
    share = min(share, LONG_RUN_MAX_SHARE)
    if share > daniels_share:
        notes.append(f"Daniels would cap the long run at {daniels_share*100:.0f}% of weekly volume "
                     f"at this level; this one is {share*100:.0f}%. Three runs a week leaves no "
                     "other way to build a marathon long run, so this is a real and accepted "
                     "trade-off rather than an oversight -- and the time cap is what keeps it "
                     "bounded.")
    km = weekly_km * share
    if is_cutback:
        km *= 0.80
        notes.append("Cutback week: long run trimmed 20% as well as weekly volume.")

    easy_pace = paces.easy
    minutes = km * easy_pace / 60.0

    if minutes > time_cap:
        km = time_cap * 60.0 / easy_pace
        minutes = time_cap
        notes.append(f"Capped at {time_cap:.0f} min ({km:.1f} km at your easy pace). This is "
                     "Daniels' own long-run time limit; time on feet is the adaptation that "
                     "matters, and past roughly two and a half hours the damage and recovery cost "
                     "climb faster than the benefit does.")
    if km > LONG_RUN_MAX_KM:
        km = LONG_RUN_MAX_KM
        minutes = km * easy_pace / 60.0
        notes.append(f"Capped at {LONG_RUN_MAX_KM:.0f} km -- there is no evidence a first-timer "
                     "gains from going further, and plenty that the recovery cost is not worth it.")
    if share >= LONG_RUN_MAX_SHARE:
        notes.append(f"The long run is {share*100:.0f}% of your week. That is high, and it is the "
                     "unavoidable cost of a 3-run week -- the textbook figure is 30-35%. Adding a "
                     "short fourth easy run is the cleanest way to bring it down.")
    return round(km, 1), round(minutes, 1), notes


def taper_weeks(peak_weekly_km: float, paces: TrainingPaces) -> List[Dict[str, object]]:
    """The two taper weeks, per Bosquet 2007: volume down 50%/70%, intensity and frequency kept.

    The commonest taper mistake is cutting the hard sessions -- that loses the sharpening the taper
    exists to reveal. Volume falls; the quality session stays, just shorter.
    """
    out = []
    for i, cut in enumerate(TAPER_VOLUME_CUT):
        km = peak_weekly_km * cut
        out.append({
            "week": f"T-{TAPER_WEEKS - i}",
            "volume_km": round(km, 1),
            "volume_pct_of_peak": round(cut * 100),
            "keep": ["session frequency (still 3 runs)",
                     "intensity -- the quality session stays at threshold/MP pace, just shorter"],
            "cut": ["total volume", "long-run length"],
            "long_run_km": round(min(km * 0.45, 16.0 if i == 0 else 10.0), 1),
            "rationale": ("Bosquet 2007 meta-analysis: a 2-week taper with a 41-60% volume "
                          "reduction, holding intensity and frequency, produced the largest "
                          "performance gain. Cutting intensity instead of volume is what makes "
                          "people feel flat on race day."),
        })
    return out


def phase_overview(config: Optional[PlanConfig] = None) -> List[Dict[str, object]]:
    """A human-readable map of the whole journey: goal, gates, and expected duration per phase."""
    out = []
    for p in PHASE_ORDER:
        if p in (Phase.RACE, Phase.RECOVERY):
            continue
        vol = _PHASE_VOLUME_KM.get(p)
        out.append({
            "phase": p.value,
            "goal": PHASE_GOALS[p],
            "min_weeks": PHASE_MIN_WEEKS.get(p, 0),
            "stall_review_weeks": PHASE_STALL_WEEKS.get(p),
            "weekly_km_corridor": list(vol) if vol else None,
            "weekly_min_corridor": (list(_FOUNDATION_MIN) if p == Phase.FOUNDATION else None),
            "gates": [g.to_dict() for g in PHASE_GATES.get(p, ())],
        })
    return out


# ----------------------------------------------------------------------------------------
# Week generation
# ----------------------------------------------------------------------------------------

#: Modelled on the couch-to-5K family and on Galloway's run-walk-run method, with the ratio
#: shifting toward running rather than the session simply getting longer -- the walk break is what
#: keeps the *running* portions genuinely aerobic in someone with no base, and Galloway's argument
#: (that planned walk breaks reduce injury and improve finishing times for beginners) is exactly
#: the case here. The last row is continuous running.
def run_walk_entry_rung(continuous_min: Optional[float]) -> int:
    """Where on the ladder a demonstrated continuous-run capacity should start.

    The ladder assumes someone who cannot run for a minute. That is the right default and the wrong
    one for an athlete who has just been observed holding four and a half minutes: starting them at
    one-minute repeats is not conservative, it is a month of sessions that do not touch the tissue
    they are supposed to load, and it teaches that the plan does not know what they can do.

    Entry is deliberately one rung BELOW demonstrated capacity. What was demonstrated was a single
    effort, at a pace that drove heart rate to 180; the ladder asks for the same block repeated
    several times, aerobically. Those are different demands, and the gap between them is exactly
    where a beginner gets hurt.

    ``None`` means nothing has been demonstrated, which returns the bottom rung.
    """
    if not continuous_min or continuous_min <= 0:
        return 0
    # The last rung whose run block is at or below what was actually held, then step back one.
    reachable = [i for i, (run_min, _, _) in enumerate(_RUN_WALK_LADDER) if run_min <= continuous_min]
    return max(0, (reachable[-1] if reachable else 0) - 1)


#: Run-walk progression for FOUNDATION, one row per week: ``(run_min, walk_min, repeats)``.
_RUN_WALK_LADDER: Tuple[Tuple[float, float, int], ...] = (
    (1.0, 2.0, 8),      # wk 1: 8 min running inside a 24 min session
    (2.0, 2.0, 7),      # wk 2: 14 min running
    (3.0, 2.0, 6),      # wk 3: 18 min running
    (5.0, 2.0, 5),      # wk 4: 25 min running
    (8.0, 2.0, 3),      # wk 5: 24 min running, longer continuous blocks
    (12.0, 2.0, 2),     # wk 6: 24 min in two blocks
    (15.0, 1.0, 2),     # wk 7: 30 min running
    (30.0, 0.0, 1),     # wk 8: continuous 30 min -- the FOUNDATION gate
)

#: Strength templates. The athlete already lifts, so these are *running-specific additions* framed
#: as constraints on his existing sessions rather than a new programme -- the calf/Achilles work and
#: the single-leg work are the parts that matter for running, and heavy compound lifting is already
#: covered. Lauersen 2014/2018 (strength training reduces overuse injury) and Blagrove 2018
#: (strength training improves running economy) are the reasons these are non-negotiable rather
#: than optional extras.
_STRENGTH_CORE = [
    "Heavy slow calf raises: 3 x 12 straight-knee + 3 x 12 bent-knee, 3 s down. Add load once "
    "12 reps is easy -- this is the single highest-yield injury-prevention exercise for a runner.",
    "Single-leg work: split squats or step-ups, 3 x 8 per side, loaded.",
    "Hip abduction: side-lying or cable, 3 x 15 per side.",
    "Posterior chain: Romanian deadlift or hip thrust, 3 x 8.",
    "Anti-rotation core: Pallof press or suitcase carry, 3 x 30 s per side.",
]
_PLYO_ADD = [
    "Low-amplitude plyometrics: 3 x 10 pogo hops, 2 x 10 alternating bounds. Stiffness work -- "
    "improves running economy (Blagrove 2018); introduce only once the calf-raise gate is met, "
    "and never within 48 h of a long run.",
]


def _easy_run(day: int, minutes: float, paces: TrainingPaces, *,
              title: str = "Easy run", zones: Tuple[int, ...] = (1, 2)) -> Session:
    return Session(
        day_offset=day, type=SessionType.EASY, title=title, duration_min=round(minutes),
        zones=zones, pace_target_sec_km=paces.easy, pace_range_sec_km=paces.easy_range,
        intent="Aerobic development with minimal cost. This is the session most often ruined by "
               "running it too fast.",
        cues=["If you cannot hold a conversation, you are going too fast -- slow down, do not "
              "shorten it.",
              "Heart rate is the referee, not pace. On a hot day or a bad-sleep day the same "
              "effort is a slower pace, and that is correct, not a setback."],
    )


def _long_run(day: int, km: Optional[float], minutes: float, paces: TrainingPaces,
              phase: Phase, notes: Sequence[str]) -> Session:
    fuelling = ""
    if minutes >= 90:
        fuelling = ("Take 30-60 g of carbohydrate per hour after the first hour, and drink to "
                    "thirst. Above ~2.5 h aim toward 60-90 g/h using a glucose+fructose mix -- "
                    "the gut is trainable and this is the training (ACSM/ISSN guidance; the high "
                    "end needs practice, so build up to it rather than trying it on race day).")
    elif minutes >= 60:
        fuelling = "Water is enough, but practise carrying it. Start rehearsing a gel late in the run."
    return Session(
        day_offset=day, type=SessionType.LONG, title="Long run",
        duration_min=round(minutes), distance_km=km, zones=(1, 2),
        pace_target_sec_km=paces.easy, pace_range_sec_km=paces.easy_range,
        structure=("Steady and easy throughout." if phase < Phase.MARATHON_BASE else
                   "Steady easy running; see the marathon-pace weeks for segment work."),
        intent="Time on feet. This is the session the marathon is actually built from -- "
               "mitochondrial and capillary density, fat oxidation, tendon and bone tolerance, "
               "and the confidence that comes from having been out there.",
        fuelling=fuelling,
        cues=list(notes) + [
            "Start slower than feels natural. Negative-split the run if you can.",
            "Decoupling is the metric that matters here: if heart rate drifts more than 5% "
            "relative to pace between the halves, the pace was too hot for the duration.",
        ],
    )


def _threshold(day: int, paces: TrainingPaces, reps: int, rep_min: float,
               recovery_min: float) -> Session:
    total = reps * (rep_min + recovery_min)
    return Session(
        day_offset=day, type=SessionType.THRESHOLD, title=f"Threshold {reps} x {rep_min:g} min",
        duration_min=round(20 + total + 10), zones=(4,),
        pace_target_sec_km=paces.threshold,
        structure=(f"20 min easy warm-up, then {reps} x {rep_min:g} min at threshold pace "
                   f"({fmt_pace(paces.threshold)}/km) with {recovery_min:g} min easy jog between, "
                   "then 10 min easy cool-down."),
        intent="Raise the pace you can hold for an hour. Cruise intervals rather than one long "
               "tempo because broken threshold work accumulates more time at the intensity for "
               "less fatigue -- Daniels' own argument for the format.",
        cues=["Threshold is 'comfortably hard' -- about the pace you could hold for an hour in a "
              "race. If rep 1 feels hard, it is too fast.",
              "Heart rate lags: expect it to reach the zone about 90 seconds into each rep. Do "
              "not chase the number at the start of the rep."],
    )


def _intervals(day: int, paces: TrainingPaces, reps: int, rep_m: int) -> Session:
    return Session(
        day_offset=day, type=SessionType.INTERVALS, title=f"Intervals {reps} x {rep_m} m",
        duration_min=round(20 + reps * 2 * (rep_m / 1000.0 * paces.interval / 60.0) + 10),
        zones=(5,), pace_target_sec_km=paces.interval,
        structure=(f"20 min easy warm-up with 4 x 20 s strides, then {reps} x {rep_m} m at "
                   f"{fmt_pace(paces.interval)}/km with equal-time jog recovery, 10 min cool-down."),
        intent="Stress VO2max -- the aerobic ceiling. Keep the total quality volume small; the "
               "purpose is stimulus, not accumulation.",
        cues=["Pace off the first rep, not the last. If the last rep is faster, the set was too easy; "
              "if you fade more than a couple of seconds, it was too hard.",
              "Heart rate is a poor guide inside short reps because of lag -- use pace and feel, "
              "and let heart rate confirm afterwards."],
    )


def _mp_long(day: int, km: Optional[float], minutes: float, paces: TrainingPaces,
             mp_min: float) -> Session:
    return Session(
        day_offset=day, type=SessionType.MARATHON_PACE, title="Long run with marathon-pace finish",
        duration_min=round(minutes), distance_km=km, zones=(2, 3),
        pace_target_sec_km=paces.marathon,
        structure=(f"Easy at {fmt_pace(paces.easy)}/km, then the final {mp_min:g} min at marathon "
                   f"pace ({fmt_pace(paces.marathon)}/km). Do not start the fast section early."),
        intent="Marathon pace on pre-fatigued legs -- the closest safe rehearsal of the second "
               "half of the race, and the honest test of whether the goal pace is real.",
        fuelling="Rehearse race fuelling exactly: same products, same timing, same volume of fluid.",
        cues=["If you cannot hold marathon pace at the end of this, the goal pace is wrong. That is "
              "information, not failure -- and far cheaper to learn here than at 30 km.",
              "Practise the race-day details: kit, shoes, gels, bottle, start time, breakfast."],
    )


def _strength(day: int, phase: Phase, *, include_plyo: bool) -> Session:
    items = list(_STRENGTH_CORE)
    if include_plyo:
        items += _PLYO_ADD
    return Session(
        day_offset=day, type=SessionType.STRENGTH, title="Strength (running-specific)",
        duration_min=45, zones=(),
        structure="; ".join(items),
        intent="Injury prevention and running economy. Strength training substantially reduces "
               "overuse injury (Lauersen 2014/2018) and improves running economy without unwanted "
               "mass (Blagrove 2018). You already lift -- fold these in rather than adding a "
               "separate session.",
        cues=["Keep heavy lower-body work at least 24 h away from a quality run and 48 h from the "
              "long run.",
              "Do not chase soreness. The goal is stiffness and strength, not a session that "
              "compromises the running."],
    )


def _time_trial_2000m(day: int, paces: TrainingPaces) -> Session:
    """The 2000 m trial that seeds a real VDOT.

    Distance chosen for the duration it produces, not for tidiness: ~11-12 minutes for a beginner
    lands inside Riegel's validated 3.5-230 min window and inside the range where Daniels'
    sustainable-%VO2max curve behaves. A 5K here would be a longer maximal effort on less prepared
    tissue and would yield a *worse* estimate, not a better one.
    """
    return Session(
        day_offset=day, type=SessionType.TIME_TRIAL, title="2000 m time trial",
        duration_min=45, distance_km=2.0, zones=(4, 5),
        structure="10 min easy warm-up plus 4 x 30 s strides. Then 2000 m (5 laps of a track, or a "
                  "measured flat 2 km) as fast as you can hold evenly. 10 min walk/jog cool-down.",
        intent="Replace the conservative submaximal estimate with a real performance. Everything "
               "downstream -- zones, every prescribed pace, the in-run targets -- is derived from "
               "this number, which is why it is worth doing properly.",
        cues=["Even effort beats a fast start. If the second half is much slower than the first, the "
              "number underestimates you and you will have to do it again.",
              "Go alone, on a flat measured course, and not into a headwind.",
              "Stop immediately for chest discomfort, light-headedness, or anything that feels "
              "wrong. A time trial is never worth that.",
              "Record your peak heart rate: if this is a genuinely maximal effort it is the first "
              "legitimate chance to observe your actual maximum."])


def _rest(day: int, note: str = "") -> Session:
    return Session(day_offset=day, type=SessionType.REST, title="Rest",
                   intent=note or "Adaptation happens now, not during the session.")


def generate_week(profile: FitnessProfile, phase: Phase, week_in_phase: int, *,
                  week_index: int = 1, config: Optional[PlanConfig] = None,
                  previous_week_volume: Optional[float] = None,
                  phase_length_est: int = 8) -> PlannedWeek:
    """Build one concrete training week.

    The shape is constant so the week is predictable around shift work -- long run on the
    preferred long-run day, the other two runs on the configured midweek days, strength on the
    remaining two -- and only the *content* of the two non-long runs changes by phase:

    * ``FOUNDATION``  -- three run-walk sessions off :data:`_RUN_WALK_LADDER`, no quality at all.
    * ``BASE_1``      -- easy, easy + strides, long. Still no threshold: volume first.
    * ``BASE_2``      -- easy + strides, threshold, long.
    * ``HALF_BUILD``  -- threshold or intervals alternating, easy, long.
    * ``MARATHON_BASE``/``MARATHON_PEAK`` -- one quality session, one easy, and a long run that
      periodically carries marathon-pace segments.
    """
    cfg = config or PlanConfig()
    is_cutback = (week_in_phase % CUTBACK_EVERY == 0) and phase not in (
        Phase.ASSESS, Phase.TAPER, Phase.RACE, Phase.RECOVERY)
    km, minutes = weekly_volume_target(phase, week_in_phase, phase_length_est=phase_length_est,
                                       previous_week_volume=previous_week_volume, config=cfg,
                                       is_cutback=is_cutback)
    paces = profile.paces
    d_long = cfg.long_run_day
    d_a, d_b = [d for d in cfg.run_days if d != d_long][:2] or [1, 3]
    s_a, s_b = cfg.strength_days
    sessions: List[Session] = []
    notes: List[str] = []
    focus = PHASE_GOALS[phase]

    include_plyo = phase not in (Phase.ASSESS, Phase.FOUNDATION)

    if phase == Phase.ASSESS:
        sessions = [
            Session(day_offset=0, type=SessionType.REST,
                    title="Screening + baseline day -- no running",
                    intent="Two things, in this order. First the pre-participation screening "
                           "questionnaire -- it takes two minutes and gates everything else. Then "
                           "the orthostatic test on waking (5 min supine, 2 min standing) and the "
                           "start of the overnight HRV series. No running today.",
                    cues=["The screening is not a formality: exertional chest discomfort, unusual "
                          "breathlessness and exertional dizziness are the three answers that stop "
                          "the plan, and they stop it whether or not you feel like they should.",
                          "Wear the armband tonight in resting mode so the HRV baseline starts "
                          "building immediately -- it needs 14 nights before it means anything."]),
            Session(day_offset=1, type=SessionType.STRENGTH, title="Structural screen",
                    duration_min=30,
                    structure="Single-leg calf raises to failure per side; 30 s sit-to-stand; "
                              "single-leg balance; step-down quality; plank hold.",
                    intent="Find the weak link before load finds it."),
            Session(day_offset=2, type=SessionType.RAMP_TEST, title="Graded ramp test",
                    duration_min=35,
                    # Deliberately does not enumerate the ladder. It used to say "stages at 5, 6,
                    # 7, 8, 9 km/h", which is five stages; calibration.calibration_protocol -- the
                    # code that actually derives the ladder, and the code that later analyses the
                    # recording -- generates six, descending from a top stage that depends on the
                    # athlete. A hand-written summary that disagrees with the generator is a card
                    # that contradicts the voice in your ear halfway through the session.
                    structure="Walk warm-up, then 4 min stages rising by 1 km/h, a walk recovery "
                              "and a 20 min steady block. Record heart rate over the final 60 s of "
                              "each stage, plus Borg 6-20 and the talk test. Stop at 85% of "
                              "heart-rate reserve, RPE 15/20, or when speech becomes impossible.",
                    intent="Derive the heart-rate/speed relationship, the talk-test threshold, "
                           "cadence at each speed, and the seed VDOT. Everything else follows."),
            _rest(3, "Recover from the ramp."),
            Session(day_offset=4, type=SessionType.RUN_WALK, title="Easy shakeout walk-jog",
                    duration_min=25,
                    run_walk=_RUN_WALK_LADDER[
                        run_walk_entry_rung(getattr(profile, "demonstrated_run_min", None))],
                    zones=(1, 2),
                    intent="Confirm the sensor setup and the audio cues work before anything "
                           "depends on them."),
            _rest(5), _rest(6),
        ]
        notes = [
            "No hard running this week, on purpose. A maximal test on untrained tissue measures "
            "discomfort tolerance and buys an injury.",
            "Wear the armband overnight every night from now on -- the readiness engine needs at "
            "least 14 nights before its band means anything.",
        ]

    elif phase == Phase.FOUNDATION:
        # A cutback week REPEATS the previous rung rather than advancing. Advancing the ladder while
        # cutting the stated volume was incoherent: the sessions got harder in the week that is
        # supposed to be easier.
        # Start from what the athlete has been observed to hold, not from zero.
        entry = run_walk_entry_rung(getattr(profile, "demonstrated_run_min", None))
        rung_index = min(entry + week_in_phase - 1, len(_RUN_WALK_LADDER) - 1)
        if is_cutback and rung_index > 0:
            rung_index -= 1
        rung = _RUN_WALK_LADDER[rung_index]
        run_min, walk_min, reps = rung
        continuous = walk_min == 0
        session_total = reps * (run_min + walk_min)
        for i, day in enumerate((d_a, d_b, d_long)):
            if continuous:
                sessions.append(_easy_run(day, run_min, paces,
                                          title=f"Continuous {run_min:g} min easy"))
            else:
                sessions.append(Session(
                    day_offset=day, type=SessionType.RUN_WALK,
                    title=f"Run-walk {run_min:g}/{walk_min:g} x {reps}",
                    duration_min=round(session_total + 10), run_walk=rung, zones=(1, 2),
                    pace_range_sec_km=paces.easy_range,
                    structure=(f"5 min walk warm-up, then {reps} x ({run_min:g} min easy running + "
                               f"{walk_min:g} min walking), 5 min walk cool-down."),
                    intent="Build running-specific tissue tolerance in doses the tissue can "
                           "actually absorb. The walk break is not a concession -- it is what "
                           "keeps the running portions aerobic and the total load survivable.",
                    cues=["Run the running portions slowly enough that the walk break feels almost "
                          "unnecessary.",
                          "Do not skip the walk breaks because you feel good. The breaks are why "
                          "you feel good."]))
        # The honest weekly figure for this phase is what the ladder actually prescribes, not a
        # separate corridor that happens to disagree with it.
        minutes = round(run_min * reps * 3, 1)
        notes = [f"Run-walk ladder rung {rung_index + 1} of {len(_RUN_WALK_LADDER)}: "
                 f"{run_min:g} min running / {walk_min:g} min walking x {reps} "
                 f"({run_min * reps:g} min of running per session, {minutes:g} min across the week).",
                 "Repeat a rung rather than advancing if the previous week felt hard, hurt, or "
                 "was interrupted. There is no deadline."]
        if is_cutback:
            notes.append("The ladder holds at the previous rung this week rather than advancing.")

    elif phase == Phase.BASE_1:
        lr_km, lr_min, lr_notes = long_run_progression(phase, week_in_phase, km, paces,
                                                       config=cfg, is_cutback=is_cutback)
        easy_km = max(0.0, (km or 0.0) - (lr_km or 0.0))
        per_easy_min = easy_km / 2.0 * paces.easy / 60.0 if easy_km else 30.0
        # The 2000 m trial replaces the first easy run once there is enough base to make a maximal
        # effort reasonable. Week 5 rather than week 1: four weeks of continuous running is the
        # minimum before asking for a maximal effort on tissue that has only just stopped walking.
        if week_in_phase == _TIME_TRIAL_WEEK:
            sessions.append(_time_trial_2000m(d_a, paces))
        else:
            sessions.append(_easy_run(d_a, per_easy_min, paces))
        strides = _easy_run(d_b, per_easy_min, paces, title="Easy run + strides")
        strides.structure = ("Easy running, then 6 x 20 s strides at a relaxed fast pace with full "
                             "walk-back recovery. Strides are not a workout -- they are form and "
                             "neuromuscular maintenance.")
        strides.type = SessionType.STRIDES
        strides.cues = strides.cues + ["Strides should feel fast and easy, never strained. Stop the "
                                       "set if form degrades."]
        sessions.append(strides)
        sessions.append(_long_run(d_long, lr_km, lr_min, paces, phase, lr_notes))
        notes = lr_notes + ["No threshold work yet. Volume and consistency first -- threshold work "
                            "on a thin base produces fatigue without much adaptation."]
        if week_in_phase == _TIME_TRIAL_WEEK:
            notes.append(
                "Time-trial week. Everything downstream -- your zones, every prescribed pace, the "
                "controller's targets -- is currently derived from a deliberately conservative "
                "submaximal estimate. This is the run that replaces it with a real measurement, so "
                "expect your paces to get quicker afterwards.")

    elif phase == Phase.BASE_2:
        lr_km, lr_min, lr_notes = long_run_progression(phase, week_in_phase, km, paces,
                                                       config=cfg, is_cutback=is_cutback)
        reps = 2 + min(2, (week_in_phase - 1) // 3)
        rep_min = 6.0 if week_in_phase < 5 else 8.0
        thr = _threshold(d_a, paces, reps, rep_min, 2.0)
        if is_cutback:
            thr = _threshold(d_a, paces, max(2, reps - 1), rep_min, 2.0)
        sessions.append(thr)
        easy_km = max(0.0, (km or 0.0) - (lr_km or 0.0) - (thr.duration_min or 0) * 60.0 / paces.easy / 1000.0)
        sessions.append(_easy_run(d_b, max(30.0, easy_km * paces.easy / 60.0), paces))
        sessions.append(_long_run(d_long, lr_km, lr_min, paces, phase, lr_notes))
        notes = lr_notes + ["First threshold block. One quality session a week is the correct dose "
                            "on three runs a week -- the long run is already a hard session."]

    elif phase in (Phase.HALF_BUILD, Phase.MARATHON_BASE, Phase.MARATHON_PEAK):
        substitution_note: Optional[str] = None
        lr_km, lr_min, lr_notes = long_run_progression(phase, week_in_phase, km, paces,
                                                       config=cfg, is_cutback=is_cutback)
        # Alternate threshold and VO2max work; threshold dominates because it is the more
        # marathon-specific adaptation and the cheaper one to recover from.
        # Never schedule VO2max intervals when the athlete's VDOT is below the floor where Daniels
        # publishes an Interval pace. There is no defensible target to run them at, and an
        # extrapolated one is both unachievable and an injury risk for someone whose aerobic base
        # cannot yet support the work. Threshold substitutes, which is the right session anyway.
        do_intervals = ((week_in_phase % 3 == 0) and phase != Phase.MARATHON_PEAK
                        and paces.ir_prescribable)
        if do_intervals:
            sessions.append(_intervals(d_a, paces, reps=5, rep_m=800))
        else:
            reps = 3 + min(2, (week_in_phase - 1) // 4)
            sessions.append(_threshold(d_a, paces, reps, 8.0 if phase == Phase.HALF_BUILD else 10.0, 2.0))
            if (week_in_phase % 3 == 0) and phase != Phase.MARATHON_PEAK and not paces.ir_prescribable:
                substitution_note = (
                    f"This week would normally be VO2max intervals, but your VDOT ({paces.vdot:.0f}) "
                    f"is below {int(VDOT_IR_FLOOR)}, where Daniels stops publishing an Interval pace. "
                    "There is no honest target to run them at, so threshold work substitutes. "
                    "Intervals appear automatically once a race result lifts VDOT past the floor -- "
                    "and threshold is the more useful session for you until then anyway.")
        # Distribute the volume the long run and quality session do not cover across the remaining
        # easy run(s), instead of hardcoding a duration. A fixed 40 min made the session list
        # silently inconsistent with the week's stated volume target -- the plan said 50 km and the
        # sessions added up to 30.
        quality_km = ((sessions[-1].duration_min or 0.0) * 60.0 / paces.easy) if sessions else 0.0
        remaining = max(0.0, (km or 0.0) - (lr_km or 0.0) - quality_km)
        easy_min = remaining * paces.easy / 60.0
        # Bounded: a midweek run below 30 min is not worth changing for, and above 80 min it stops
        # being a midweek run for someone working shifts.
        easy_min = max(30.0, min(80.0, easy_min))
        if is_cutback:
            easy_min = max(25.0, easy_min * 0.75)
        sat_before_long = (d_b + 1) % 7 == d_long
        easy = _easy_run(d_b, easy_min, paces)
        if sat_before_long:
            easy.cues = list(easy.cues) + [
                "This one sits the day before your long run, which is deliberate -- it makes tomorrow "
                "start on slightly tired legs, and that is a marathon-specific stimulus. It only "
                "works if today stays genuinely easy. If you push this, tomorrow stops being a long "
                "run and becomes the second half of a two-day hard block."]
        sessions.append(easy)
        # Marathon-pace long runs every third week in MARATHON_BASE, every other week in PEAK.
        mp_week = (phase == Phase.MARATHON_BASE and week_in_phase % 3 == 0) or \
                  (phase == Phase.MARATHON_PEAK and week_in_phase % 2 == 1)
        if mp_week and not is_cutback and lr_min:
            mp_min = min(50.0, 15.0 + 5.0 * week_in_phase)
            sessions.append(_mp_long(d_long, lr_km, lr_min, paces, mp_min))
        else:
            sessions.append(_long_run(d_long, lr_km, lr_min, paces, phase, lr_notes))
        notes = list(lr_notes)
        if substitution_note:
            notes.append(substitution_note)
        if cfg.offer_fourth_run and phase in (Phase.MARATHON_BASE, Phase.MARATHON_PEAK):
            # Put it on a day that has nothing else on it. Landing it on a strength day (which the
            # old `(d_b + 1) % 7` did) produces a schedule that reads as two sessions stacked on one
            # day, which is the opposite of what an optional easy run is for.
            busy = {x.day_offset for x in sessions} | set(cfg.strength_days) | {d_long}
            free = [x for x in range(7) if x not in busy
                    and x != (d_long - 1) % 7]          # not the day before the long run either
            optional_day = free[0] if free else (d_b + 1) % 7
            sessions.append(Session(
                day_offset=optional_day, type=SessionType.EASY,
                title="Optional 4th easy run (30 min)", duration_min=30, zones=(1, 2),
                pace_target_sec_km=paces.easy, optional=True,
                intent="Purely optional aerobic volume. If a time goal ever replaces 'finish "
                       "strong', adding this run is the single highest-yield change available -- "
                       "and it brings the long run's share of the week back toward the textbook "
                       "30-35%. No gate depends on it.",
                cues=["Skip it without guilt on a bad week. It exists to be skipped."]))
            notes.append("A fourth easy run is offered this phase. Optional, and no gate needs it.")

    elif phase == Phase.TAPER:
        peak = previous_week_volume or (km or 50.0)
        tw = taper_weeks(peak, paces)[min(week_in_phase - 1, 1)]
        km = float(tw["volume_km"])
        sessions.append(_threshold(d_a, paces, 3, 6.0, 2.0))
        sessions.append(_easy_run(d_b, 30.0, paces))
        sessions.append(_long_run(d_long, float(tw["long_run_km"]),
                                  float(tw["long_run_km"]) * paces.easy / 60.0, paces, phase,
                                  ["Short by design. You cannot gain fitness now; you can only "
                                   "arrive tired."]))
        notes = [str(tw["rationale"]),
                 f"Volume is {tw['volume_pct_of_peak']}% of peak. Intensity and frequency stay."]
        focus = PHASE_GOALS[Phase.TAPER]

    elif phase == Phase.RACE:
        sessions = [_rest(0), _easy_run(1, 25.0, paces, title="Easy shakeout"), _rest(2),
                    _easy_run(3, 20.0, paces, title="Easy + 4 strides"), _rest(4), _rest(5),
                    Session(day_offset=6, type=SessionType.RACE, title="Marathon",
                            distance_km=42.195, zones=(2, 3),
                            pace_target_sec_km=paces.marathon,
                            structure=f"Target {fmt_pace(paces.marathon)}/km. First 5 km "
                                      "deliberately 10-15 s/km slower than target.",
                            fuelling="60-90 g carbohydrate per hour from 45 min, exactly as "
                                     "rehearsed. Drink to thirst.",
                            intent="Execute what you practised.",
                            cues=["The first half should feel almost too easy. Every marathon that "
                                  "goes wrong goes wrong in the first 10 km.",
                                  "Heart rate will read high in the last hour from cardiac drift "
                                  "and heat -- that is expected. Pace and feel lead from 30 km."])]
        notes = ["Race week. Nothing you do now adds fitness; plenty can subtract it."]

    else:  # RECOVERY
        sessions = [_rest(i) for i in range(7)]
        sessions[2] = _easy_run(2, 20.0, paces, title="Optional easy jog")
        sessions[2].optional = True
        sessions[5] = _easy_run(5, 25.0, paces, title="Optional easy jog")
        sessions[5].optional = True
        notes = ["Reverse taper: roughly one easy day per mile raced before any structured "
                 "training resumes -- about three weeks. Walking, swimming and cycling are all "
                 "fine; running is not required.",
                 "Do not book the next goal race this week. Decide when you feel normal again."]
        focus = PHASE_GOALS[Phase.RECOVERY]

    # Strength days, placed away from the quality run and the long run.
    if phase not in (Phase.ASSESS, Phase.RACE, Phase.RECOVERY):
        for d in (s_a, s_b):
            sessions.append(_strength(d, phase, include_plyo=include_plyo))

    used = {s.day_offset for s in sessions}
    for d in range(7):
        if d not in used:
            sessions.append(_rest(d))
    sessions.sort(key=lambda s: (s.day_offset, s.type != SessionType.REST))

    if is_cutback:
        notes.append(f"Cutback week: volume x{CUTBACK_FACTOR:.2f}. Every {CUTBACK_EVERY}th week "
                     "drops volume so the slow tissues catch up with the fast ones. [Convention "
                     "rather than trial-tested, but the mechanism is sound and the cost is low.]")

    # Coherence check: does the week actually add up to its own target? If not, say so rather than
    # printing a target the sessions cannot reach. At a beginner's easy pace, three runs plus a
    # 150-minute long-run cap has a hard ceiling of roughly 30-35 km/week, and that ceiling rises
    # only as the easy pace itself gets quicker.
    if km:
        planned_km = 0.0
        for s in sessions:
            if s.type in (SessionType.REST, SessionType.STRENGTH, SessionType.CROSS) or s.optional:
                continue
            if s.distance_km:
                planned_km += s.distance_km
            elif s.duration_min:
                ref = s.pace_target_sec_km or paces.easy
                planned_km += s.duration_min * 60.0 / ref
        if planned_km < km * 0.85:
            notes.append(
                f"Honest note: this week's sessions come to about {planned_km:.0f} km, short of the "
                f"{km:.0f} km corridor target. Three runs a week plus a "
                f"{LONG_RUN_MAX_MIN:.0f}-minute long-run cap has a real ceiling at your current "
                "easy pace, and the ceiling rises as your pace does rather than by being wished "
                "away. If the gap matters to you, the fourth easy run is the fix.")
        km = round(planned_km, 1)

    return PlannedWeek(week_index=week_index, phase=phase, week_in_phase=week_in_phase,
                       sessions=sessions, volume_target_km=km, volume_target_min=minutes,
                       is_cutback=is_cutback, focus=focus, notes=notes)
