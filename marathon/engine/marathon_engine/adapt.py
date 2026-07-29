"""Adaptation: turn readiness, completed work, and a shift rota into next week's actual plan.

Three timescales, three functions:

* **Today** -- :func:`apply_readiness` mutates the planned session using this morning's band.
* **This week** -- :func:`reschedule_week` moves sessions around the shift rota, protecting the
  long run and the quality session and refusing to stack them.
* **Next week** -- :func:`replan_week` decides whether to add, hold, or cut volume, from what was
  actually completed rather than what was planned.

Design principles
-----------------
**Never move load forward.** A missed session is *gone*, not owed. Absorbing a skipped run by
adding it to next week converts a rest into a spike, which is the specific mechanism the ramp caps
exist to prevent. :func:`replan_week` therefore never carries volume forward; it only decides the
next week's target from the *achieved* baseline.

**Downgrade, do not delete.** A suppressed-readiness day keeps its duration and loses its
intensity where possible. Keeping the habit and the aerobic time while removing the hard part costs
almost nothing and preserves consistency, which is the variable that actually predicts progress.

**The shift rota wins.** For a resident, the schedule is not negotiable and pretending otherwise
produces a plan that gets abandoned. Post-night and post-call days are treated as unavailable for
quality work by default -- sleep deprivation degrades time to exhaustion and inflates perceived
effort, and a 24-hour shift is itself a large physiological load that happens to leave no trace in
any training-load metric.

Sources
-------
* Sleep restriction and endurance performance: reduced time to exhaustion and elevated RPE at the
  same workload; reviews summarised in Fullagar et al. 2015, *Sports Med* 45:161.
* Night-shift and post-call impairment: Van Dongen et al. 2003, *Sleep* 26:117 (dose-dependent
  neurobehavioural deficits from cumulative restriction) -- the same debt that degrades clinical
  vigilance degrades training quality, and the plan should not spend a hard session into it.
* Consistency over heroics: the strongest observed predictor of marathon completion in novice
  cohorts is completed training weeks, not peak weekly volume.

Pure functions; no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from marathon_engine.load import (
    ACWR_HARD_CAP, ACWR_SWEET_HIGH, MAX_WEEKLY_RAMP, AcwrResult, ramp_rate,
)
from marathon_engine.plan import (
    CUTBACK_FACTOR, Phase, PlanConfig, PlannedWeek, Session, SessionType,
)
from marathon_engine.readiness import Readiness

__all__ = [
    "ShiftDay", "SHIFT_KINDS", "apply_readiness", "reschedule_week", "replan_week",
    "ReplanDecision", "Adjustment", "POST_NIGHT_BLOCK_H", "QUALITY_TYPES",
]

#: Session types that count as "quality" -- the ones a bad day should remove.
QUALITY_TYPES = (SessionType.THRESHOLD, SessionType.INTERVALS, SessionType.HILLS,
                 SessionType.MARATHON_PACE, SessionType.TIME_TRIAL)

SHIFT_KINDS = ("day", "night", "call", "off", "post_night", "post_call")

#: Hours after a night shift ends during which quality work is off the table. 24 h covers the
#: recovery sleep; the session is not banned, only its intensity.
POST_NIGHT_BLOCK_H = 24


@dataclass
class ShiftDay:
    """One day of the rota."""
    day: date
    kind: str = "off"                 # see SHIFT_KINDS
    start_hour: Optional[int] = None
    end_hour: Optional[int] = None

    @property
    def is_night(self) -> bool:
        return self.kind in ("night", "call")

    @property
    def blocks_quality(self) -> bool:
        return self.kind in ("night", "call", "post_night", "post_call")

    @property
    def blocks_running(self) -> bool:
        """Only a night/call day itself makes running genuinely impractical."""
        return self.kind in ("night", "call")


@dataclass
class Adjustment:
    """One change made to the plan, with the reason, for the athlete to see."""
    target: str                 # e.g. "Tue threshold"
    change: str                 # e.g. "downgraded to easy 40 min"
    reason: str

    def to_dict(self) -> dict:
        return {"target": self.target, "change": self.change, "reason": self.reason}


# ----------------------------------------------------------------------------------------
# Today
# ----------------------------------------------------------------------------------------


def apply_readiness(session: Session, readiness: Readiness,
                    *, paces_easy_sec_km: Optional[float] = None) -> Tuple[Session, List[Adjustment]]:
    """Mutate today's session for today's readiness band.

    * ``primed``     -- unchanged (never *upgraded* automatically; a good HRV reading is permission
      to run the plan's hard session well, not a licence to invent extra load).
    * ``normal``     -- unchanged.
    * ``suppressed`` -- quality becomes easy at the same duration; the long run keeps its duration
      but loses any marathon-pace segment.
    * ``strained``   -- everything becomes rest or a 20-minute walk.
    * ``unknown``    -- unchanged, but easy sessions get an explicit "keep it genuinely easy" cue.

    The asymmetry is deliberate. Automatically *adding* load on a good day compounds error, because
    a single high HRV reading is a weak signal and the cost of a wrong upgrade is a lost week; the
    cost of a wrongly easy day is one easy day.
    """
    adj: List[Adjustment] = []
    band = readiness.band
    label = f"{session.type.value} '{session.title}'"

    if band in ("primed", "normal"):
        return session, adj

    if band == "unknown":
        s = _copy(session)
        if s.type in (SessionType.EASY, SessionType.LONG):
            s.cues = list(s.cues) + ["No readiness baseline yet -- err genuinely easy today."]
        return s, adj

    if band == "strained":
        why = readiness.override_reason or "readiness is in the strained band"
        s = Session(day_offset=session.day_offset, type=SessionType.REST,
                    title="Rest (readiness override)", duration_min=None,
                    intent=f"Cancelled because {why}. {readiness.detail}",
                    cues=["A 20-minute easy walk is fine and often helps. Running is not."])
        adj.append(Adjustment(label, "cancelled -> rest or 20 min walk", why))
        return s, adj

    # suppressed
    why = readiness.override_reason or "HRV is below your baseline band"

    # ORDER MATTERS. MARATHON_PACE is a member of QUALITY_TYPES, so this branch has to come first
    # or a 150-minute marathon-pace long run gets rewritten as a 150-minute "easy run" and loses
    # its identity as a long run -- which then fails the long-run gates and corrupts the load
    # accounting. What we actually want is to keep the long run and remove only the fast segment.
    if session.type == SessionType.MARATHON_PACE:
        s = _copy(session)
        s.type = SessionType.LONG
        s.title = "Long run (marathon-pace segment removed)"
        s.structure = "Easy throughout -- the marathon-pace finish is removed today."
        s.pace_target_sec_km = paces_easy_sec_km or s.pace_target_sec_km
        adj.append(Adjustment(label, "marathon-pace segment removed", why))
        return s, adj

    if session.type in QUALITY_TYPES:
        dur = session.duration_min or 40.0
        s = Session(day_offset=session.day_offset, type=SessionType.EASY,
                    title=f"Easy {dur:.0f} min (was {session.title})",
                    duration_min=dur, zones=(1, 2),
                    pace_target_sec_km=paces_easy_sec_km,
                    intent=f"Intensity removed because {why}. Same time on feet, none of the cost. "
                           "The workout is not lost -- it moves to the next green day.",
                    cues=["Keep this in Z1-Z2 the whole way. The point today is aerobic time and "
                          "keeping the habit, not stimulus.",
                          "If it still feels hard at easy pace, cut it short. That is data, not "
                          "weakness."])
        adj.append(Adjustment(label, f"downgraded to easy {dur:.0f} min", why))
        return s, adj

    if session.type == SessionType.LONG:
        s = _copy(session)
        s.cues = list(s.cues) + [
            f"Readiness is suppressed ({why}). Keep this at the slow end of easy, take walk breaks "
            "if you want them, and cut it short without hesitation if it stops feeling easy."]
        adj.append(Adjustment(label, "kept, run at the slow end with permission to cut short", why))
        return s, adj

    return session, adj


def _copy(s: Session) -> Session:
    return Session(day_offset=s.day_offset, type=s.type, title=s.title,
                   duration_min=s.duration_min, distance_km=s.distance_km, zones=s.zones,
                   pace_target_sec_km=s.pace_target_sec_km,
                   pace_range_sec_km=s.pace_range_sec_km, structure=s.structure,
                   intent=s.intent, run_walk=s.run_walk, optional=s.optional,
                   fuelling=s.fuelling, cues=list(s.cues))


# ----------------------------------------------------------------------------------------
# This week
# ----------------------------------------------------------------------------------------


def reschedule_week(week: PlannedWeek, rota: Sequence[ShiftDay],
                    *, config: Optional[PlanConfig] = None) -> Tuple[PlannedWeek, List[Adjustment]]:
    """Move this week's sessions around the shift rota.

    Rules, in priority order:

    1. The **long run** is placed on the best available day -- a day that is off, not post-night,
       and ideally follows a day that was also not a night. It is the session with the least
       substitutable training effect, so it gets first pick.
    2. The **quality session** goes on another available day, never adjacent to the long run
       (48 h apart if the week allows it).
    3. **Easy runs** fill what is left; they may sit on a day shift.
    4. Nothing lands on a night or call day.
    5. If fewer days are available than sessions, the *easy* run is dropped first, then the quality
       session. The long run is dropped last and only if the week has no viable day at all.

    Returns the reshuffled week plus a list of what moved and why.
    """
    cfg = config or PlanConfig()
    adj: List[Adjustment] = []
    by_offset = {sd.day.weekday(): sd for sd in rota}

    def available(offset: int) -> bool:
        sd = by_offset.get(offset)
        return not (sd and sd.blocks_running)

    def quality_ok(offset: int) -> bool:
        sd = by_offset.get(offset)
        return available(offset) and not (sd and sd.blocks_quality)

    runs = [s for s in week.sessions
            if s.type not in (SessionType.REST, SessionType.STRENGTH, SessionType.CROSS)
            and not s.optional]
    others = [s for s in week.sessions if s not in runs]
    if not runs:
        return week, adj

    long_runs = [s for s in runs if s.type in (SessionType.LONG, SessionType.MARATHON_PACE,
                                               SessionType.RACE)]
    quality = [s for s in runs if s.type in QUALITY_TYPES and s not in long_runs]
    easy = [s for s in runs if s not in long_runs and s not in quality]

    taken: set = set()
    placed: List[Session] = []

    # 1. Long run: prefer the configured day, else the best available.
    for s in long_runs:
        cands = [d for d in range(7) if quality_ok(d) and d not in taken]
        if not cands:
            cands = [d for d in range(7) if available(d) and d not in taken]
        if not cands:
            adj.append(Adjustment(s.title, "dropped -- no viable day this week",
                                  "every day is a night or call shift"))
            continue
        # Prefer the configured day, then a day whose previous day was not a night.
        def long_key(d: int) -> Tuple[int, int, int]:
            prev = by_offset.get((d - 1) % 7)
            return (0 if d == cfg.long_run_day else 1,
                    1 if (prev and prev.is_night) else 0,
                    abs(d - cfg.long_run_day))
        d = sorted(cands, key=long_key)[0]
        if d != s.day_offset:
            adj.append(Adjustment(s.title, f"moved to day {d}",
                                  _move_reason(by_offset.get(s.day_offset))))
        s2 = _copy(s); s2.day_offset = d
        taken.add(d); placed.append(s2)

    long_day = next((s.day_offset for s in placed), None)

    # 2. Quality: as far from the long run as the week allows.
    for s in quality:
        cands = [d for d in range(7) if quality_ok(d) and d not in taken]
        if not cands:
            adj.append(Adjustment(s.title, "dropped this week",
                                  "no day free of night/post-night duty -- intensity into sleep "
                                  "debt is worse than no intensity"))
            continue
        def q_key(d: int) -> Tuple[int, int]:
            gap = 7 if long_day is None else min(abs(d - long_day), 7 - abs(d - long_day))
            return (0 if gap >= 2 else 1, -gap)
        d = sorted(cands, key=q_key)[0]
        if d != s.day_offset:
            adj.append(Adjustment(s.title, f"moved to day {d}",
                                  _move_reason(by_offset.get(s.day_offset))))
        s2 = _copy(s); s2.day_offset = d
        taken.add(d); placed.append(s2)

    # 3. Easy runs fill the rest; a day shift is fine.
    for s in easy:
        cands = [d for d in range(7) if available(d) and d not in taken]
        if not cands:
            adj.append(Adjustment(s.title, "dropped this week", "no day available"))
            continue
        d = sorted(cands, key=lambda d: abs(d - s.day_offset))[0]
        if d != s.day_offset:
            adj.append(Adjustment(s.title, f"moved to day {d}",
                                  _move_reason(by_offset.get(s.day_offset))))
        s2 = _copy(s); s2.day_offset = d
        taken.add(d); placed.append(s2)

    # 4. Strength: keep off night days, and never the day before the long run.
    for s in others:
        if s.type != SessionType.STRENGTH:
            continue
        d = s.day_offset
        bad = (not available(d)) or (long_day is not None and d == (long_day - 1) % 7)
        if bad:
            cands = [x for x in range(7)
                     if available(x) and x not in taken
                     and not (long_day is not None and x == (long_day - 1) % 7)]
            if not cands:
                # Relax the long-run-adjacency preference before giving up: being next to the long
                # run is a preference, being on a night shift is impossible.
                cands = [x for x in range(7) if available(x) and x not in taken]
            if cands:
                nd = sorted(cands, key=lambda x: abs(x - d))[0]
                adj.append(Adjustment(s.title, f"moved to day {nd}",
                                      "kept off night duty and off the day before the long run"))
                d = nd
            else:
                # No viable day at all. DROP it -- silently leaving it on a night shift was a real
                # bug: it produced a plan with a gym session scheduled during a 12-hour shift.
                adj.append(Adjustment(s.title, "dropped this week",
                                      "no day free of night duty -- strength work resumes next week"))
                continue
        s2 = _copy(s); s2.day_offset = d
        taken.add(d); placed.append(s2)

    for s in others:
        if s.type == SessionType.STRENGTH:
            continue
        if s.optional:
            cands = [d for d in range(7) if available(d) and d not in taken]
            if not cands:
                continue
            s2 = _copy(s); s2.day_offset = cands[0]
            taken.add(s2.day_offset); placed.append(s2)

    for d in range(7):
        if d not in taken:
            sd = by_offset.get(d)
            note = ("Night shift -- rest." if sd and sd.is_night else
                    "Post-shift recovery." if sd and sd.blocks_quality else
                    "Rest. Adaptation happens now.")
            placed.append(Session(day_offset=d, type=SessionType.REST, title="Rest", intent=note))

    placed.sort(key=lambda s: (s.day_offset, s.type == SessionType.REST))
    notes = list(week.notes)
    if adj:
        notes.append(f"{len(adj)} change(s) made for your rota this week.")
    return PlannedWeek(week_index=week.week_index, phase=week.phase,
                       week_in_phase=week.week_in_phase, sessions=placed,
                       volume_target_km=week.volume_target_km,
                       volume_target_min=week.volume_target_min,
                       is_cutback=week.is_cutback, focus=week.focus, notes=notes), adj


def _move_reason(sd: Optional[ShiftDay]) -> str:
    if not sd:
        return "schedule fit"
    if sd.kind in ("night", "call"):
        return f"{sd.kind} shift that day"
    if sd.kind in ("post_night", "post_call"):
        return f"day after a {sd.kind.replace('post_', '')} shift -- intensity into sleep debt " \
               "buys fatigue, not fitness"
    return "schedule fit"


# ----------------------------------------------------------------------------------------
# Next week
# ----------------------------------------------------------------------------------------


@dataclass
class ReplanDecision:
    action: str                     # advance | hold | cut | cutback | rebuild
    next_volume: Optional[float]
    completed_fraction: float
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    carry_forward: str = "none"     # always "none" -- kept explicit so the rule is visible

    def to_dict(self) -> dict:
        return {"action": self.action,
                "next_volume": round(self.next_volume, 1) if self.next_volume else None,
                "completed_fraction": round(self.completed_fraction, 2),
                "reasons": self.reasons, "warnings": self.warnings,
                "carry_forward": self.carry_forward}


def replan_week(planned_volume: Optional[float], achieved_volume: float,
                sessions_planned: int, sessions_completed: int,
                *, acwr_result: Optional[AcwrResult] = None,
                readiness_bands: Sequence[str] = (),
                max_pain: int = 0,
                weeks_since_cutback: int = 0,
                phase: Optional[Phase] = None) -> ReplanDecision:
    """Decide next week's volume from what actually happened.

    The decision tree, in precedence order:

    1. **Pain in the warning band** (>= ``PAIN_WARN``) -> hold volume. Never add load onto a niggle.
    2. **ACWR above the hard cap** -> cut to the chronic level. The ratio is a ramp governor here,
       not a risk score (see :data:`~marathon_engine.load.ACWR_CAUTION`).
    3. **Two or more suppressed/strained readiness days** -> hold, and flag the likely cause.
    4. **Less than 60% of the week completed** -> rebuild from what was achieved, not from what was
       planned. Resuming at the planned number after a disrupted week is the classic spike.
    5. **Cutback due** (every 4th week) -> cutback.
    6. **Otherwise** -> advance, capped by :data:`~marathon_engine.load.MAX_WEEKLY_RAMP` off the
       **achieved** volume.

    Volume is never carried forward. A missed run is gone.
    """
    frac = (sessions_completed / sessions_planned) if sessions_planned else 0.0
    reasons: List[str] = []
    warnings: List[str] = []
    base = achieved_volume if achieved_volume > 0 else (planned_volume or 0.0)
    bad_days = sum(1 for b in readiness_bands if b in ("suppressed", "strained"))

    if max_pain >= 3:
        reasons.append(f"Pain reached {max_pain}/10 this week. Volume holds where it is until two "
                       "consecutive pain-free weeks -- this is the single cheapest injury "
                       "prevention available.")
        return ReplanDecision("hold", round(base, 1), frac, reasons, warnings)

    if acwr_result and acwr_result.ratio > ACWR_HARD_CAP and acwr_result.band != "insufficient_history":
        # Scale the volume down by the ratio's overshoot rather than targeting
        # ``chronic * ACWR_SWEET_HIGH``. That earlier formulation did not actually cut anything,
        # and the reason is the mathematical coupling this module documents: the spike week is
        # itself inside the chronic EWMA, so a big spike inflates ``chronic`` enough that
        # ``chronic * 1.3`` lands above the volume we were trying to reduce. Scaling by
        # ``ACWR_SWEET_HIGH / ratio`` is immune to that, because it only uses the ratio.
        scaled = base * (ACWR_SWEET_HIGH / acwr_result.ratio)
        # Floor the cut at 60% of the achieved volume: a 4-week rolling metric should not be able
        # to halve next week on its own, or the plan whiplashes.
        target = max(base * 0.60, scaled)
        reasons.append(f"Acute:chronic load ratio is {acwr_result.ratio:.2f}, above the "
                       f"{ACWR_HARD_CAP:.2f} cap. Cutting to {target:.1f} to bring the ramp back "
                       "under control.")
        warnings.append(acwr_result.note)
        return ReplanDecision("cut", round(min(base, target), 1), frac, reasons, warnings)

    if bad_days >= 2:
        reasons.append(f"{bad_days} days of suppressed or strained readiness. Holding volume "
                       "rather than adding -- when recovery markers are down, added load does not "
                       "become fitness.")
        warnings.append("If this repeats, look at sleep first: chronic debt caps adaptation more "
                        "than any training variable.")
        return ReplanDecision("hold", round(base, 1), frac, reasons, warnings)

    if frac < 0.60:
        # Rebuild from what was ACHIEVED, and specifically not from ``base`` -- which falls back to
        # the planned figure when nothing was run. That fallback was a real bug: a week with zero
        # sessions completed produced a target of 105% of the plan, i.e. the single largest jump
        # the engine could emit, in exactly the situation calling for the smallest.
        if achieved_volume <= 0:
            target = (planned_volume or 0.0) * 0.50
            reasons.append(f"Nothing was run this week. Coming back at half the planned volume "
                           f"({target:.1f}) rather than picking up where the plan left off -- a "
                           "week off costs very little fitness, and resuming at full volume after "
                           "one is a textbook load spike.")
        else:
            target = achieved_volume * 1.05
            reasons.append(f"Only {sessions_completed} of {sessions_planned} sessions done. Next "
                           f"week rebuilds from what you actually ran ({achieved_volume:.1f}), not "
                           "from the plan. Nothing is owed -- missed volume is gone, and trying to "
                           "make it up is how a quiet week becomes an injury.")
        if planned_volume:
            target = min(target, planned_volume)
        return ReplanDecision("rebuild", round(target, 1), frac, reasons, warnings)

    if weeks_since_cutback >= 3:
        reasons.append("Fourth week -- cutback. Volume drops so the slow tissues catch up with the "
                       "fast ones.")
        return ReplanDecision("cutback", round(base * CUTBACK_FACTOR, 1), frac, reasons, warnings)

    cap = base * (1.0 + MAX_WEEKLY_RAMP)
    target = min(planned_volume, cap) if planned_volume else cap
    reasons.append(f"Good week ({sessions_completed}/{sessions_planned} done). Advancing to "
                   f"{target:.1f}, capped at +{MAX_WEEKLY_RAMP*100:.0f}% off what you actually ran.")
    return ReplanDecision("advance", round(target, 1), frac, reasons, warnings)
