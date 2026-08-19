"""A compact plan the phone can carry.

Why not just ship ``plan.json``
-------------------------------
:mod:`marathon_engine.export` already emits the full plan, and it is 950 kB. That is the right size
for a bundled app resource and the wrong size for a single HTML file a phone loads over a mobile
connection at a trailhead. This module emits the same schedule with everything the coach cannot act
on stripped out: prose rationale, fuelling notes, cue text, gate evidence.

What survives is what the running app actually needs to *do* something: which day, what kind of
session, how long, the run-walk pattern if there is one, and the pace band if one is prescribed.

What this deliberately cannot do
--------------------------------
The real plan is gate-based. Phases advance on *measurements* — a completed ramp test, a time trial,
fourteen nights of HRV — not on a calendar, and that evaluation needs the engine and the athlete's
data. A static export cannot do it and must not pretend to.

So this carries the week-by-week schedule *within* phases, and marks the point where a phase gate
falls due. The app can advance a week on its own; advancing a phase is a decision the engine makes
with evidence in front of it. The distinction is surfaced in the export rather than hidden, because
an app that silently promoted someone from FOUNDATION to BASE_1 on a timer would be doing the exact
thing the gate design exists to prevent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from marathon_engine import plan as planmod
from marathon_engine.assessment import FitnessProfile
from marathon_engine.physiology import fmt_pace

__all__ = ["build_app_plan", "APP_PLAN_VERSION"]

APP_PLAN_VERSION = 1

#: How many weeks of each phase to carry. Enough that the phone always has the next few sessions
#: without re-export, short enough that the file stays small. Beyond this the athlete will have
#: re-imported a session anyway, which regenerates it.
WEEKS_PER_PHASE = 6

#: The phases worth shipping to a beginner's phone. Later phases are months away and their content
#: depends on measurements that do not exist yet, so shipping them would be inventing detail.
SHIPPED_PHASES = (
    planmod.Phase.ASSESS,
    planmod.Phase.FOUNDATION,
    planmod.Phase.BASE_1,
    planmod.Phase.BASE_2,
)

#: Session types the pace coach can actually run. Everything else is shown but not started.
COACHABLE = {"easy", "long", "run_walk", "steady", "threshold", "marathon_pace", "recovery"}


def _session_dict(s: planmod.Session, paces: Any) -> Dict[str, Any]:
    """One session, reduced to what a phone can act on."""
    out: Dict[str, Any] = {
        "day": s.day_offset,
        "type": s.type.value,
        "title": s.title,
        "coachable": s.type.value in COACHABLE,
    }
    if s.duration_min:
        out["minutes"] = round(s.duration_min)
    if s.distance_km:
        out["km"] = round(s.distance_km, 2)
    if s.zones:
        out["zones"] = list(s.zones)
    if s.run_walk:
        run_min, walk_min, reps = s.run_walk
        out["run_walk"] = {"run_min": run_min, "walk_min": walk_min, "reps": reps}
    if s.pace_range_sec_km:
        fast, slow = s.pace_range_sec_km
        # Midpoint and half-width, because that is the shape the band monitor wants. Converting here
        # rather than on the phone keeps one definition of "the band" in the engine.
        mid = (fast + slow) / 2
        out["pace"] = {
            "target_sec_km": round(mid, 1),
            "tolerance": round(abs(slow - fast) / 2 / mid, 4) if mid else 0.06,
            "fast": fmt_pace(fast), "slow": fmt_pace(slow),
        }
    elif s.pace_target_sec_km:
        out["pace"] = {"target_sec_km": round(s.pace_target_sec_km, 1), "tolerance": 0.06,
                       "fast": fmt_pace(s.pace_target_sec_km * 0.94),
                       "slow": fmt_pace(s.pace_target_sec_km * 1.06)}
    # Ceiling-only is a property of the session kind, and getting it wrong means telling someone to
    # speed up on a recovery run. Taken from the engine's own list rather than re-derived.
    out["ceiling_only"] = s.type.value in ("easy", "long", "run_walk", "recovery")
    if s.structure:
        out["structure"] = s.structure
    return out


def build_app_plan(profile: FitnessProfile, *,
                   config: Optional[planmod.PlanConfig] = None) -> Dict[str, Any]:
    """The schedule the phone carries, phase by phase."""
    cfg = config or planmod.PlanConfig()
    phases: List[Dict[str, Any]] = []

    for phase in SHIPPED_PHASES:
        weeks: List[Dict[str, Any]] = []
        previous_volume: Optional[float] = None
        for wk in range(1, WEEKS_PER_PHASE + 1):
            w = planmod.generate_week(profile, phase, wk, week_index=wk, config=cfg,
                                      previous_week_volume=previous_volume)
            previous_volume = w.volume_target_km
            weeks.append({
                "week": wk,
                "focus": w.focus,
                "cutback": w.is_cutback,
                "volume_km": round(w.volume_target_km, 1) if w.volume_target_km else None,
                "volume_min": round(w.volume_target_min) if w.volume_target_min else None,
                "notes": w.notes,
                "sessions": [_session_dict(s, profile.paces) for s in w.sessions],
            })
        phases.append({
            "phase": phase.value,
            "label": phase.value.replace("_", " ").title(),
            "weeks": weeks,
            # Named, not silently applied. Advancing a phase is the engine's decision, made against
            # measurements; the app says the gate is due and stops there.
            "gate_note": ("This phase advances on measurements, not on a date. When you reach the "
                          "end of the weeks here, run `cli status` or send your data — the gate "
                          "needs evidence the phone does not have."),
        })

    return {
        "app_plan_version": APP_PLAN_VERSION,
        "generated_for": {
            "age": profile.age,
            "hr_rest": profile.hr_rest,
            "hr_max": profile.hr_max,
            "hr_max_source": profile.hr_max_source,
            "prescription_basis": profile.prescription_basis,
        },
        "run_days": list(cfg.run_days),
        "strength_days": list(cfg.strength_days),
        "phases": phases,
    }
