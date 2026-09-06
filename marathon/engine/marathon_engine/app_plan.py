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
from marathon_engine.plan import Phase, PHASE_MIN_WEEKS
from marathon_engine.assessment import FitnessProfile
from marathon_engine.physiology import fmt_pace
from marathon_engine import safety

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

#: How fast the walk breaks should be, km/h. A brisk walk, not a stroll.
#:
#: Measured rather than chosen: this athlete's own walking sat at 5.5-6.0 km/h across the 22 August
#: session, at 121-130 bpm, which is exactly the "recovering but still aerobic" the break is for.
_WALK_KMH = 5.6

#: Session types the pace coach can actually run. Everything else is shown but not started.
#:
#: ``strides`` belongs here even though it has structure the app cannot time. It is an easy run --
#: same duration, same zones, same pace band as the ``easy`` session it is derived from -- with six
#: twenty-second efforts somewhere inside it. Excluding it made a scheduled RUNNING day report
#: "Not a session the app can run", which is both false and unhelpful: the athlete still has to go
#: out and do it, and the band still applies to the running that makes up almost all of it. The app
#: says which part the band is for rather than refusing the day.
COACHABLE = {"easy", "long", "run_walk", "steady", "threshold", "marathon_pace", "recovery",
             "strides"}


def _ramp_dict(profile: FitnessProfile) -> Dict[str, Any]:
    """The ramp test as a timed sequence the phone can actually run.

    The protocol already exists in machine-readable form in ``calibration.calibration_protocol``;
    what was shipped to the phone was its prose summary, which a person can read and an app cannot
    run. So the athlete stood on a treadmill with a paragraph, timing four-minute stages by hand and
    trying to remember which of five speeds came next -- during the one session whose entire purpose
    is to produce a clean heart-rate/speed fit.

    Only the timed part crosses over. The resting block, the device setup and the analysis stay in
    the engine, because they are not things a stopwatch can help with.
    """
    from marathon_engine.calibration import calibration_protocol

    proto = calibration_protocol(profile.age, profile.hr_rest)
    steps: List[Dict[str, Any]] = [
        {"kind": "warmup", "label": "Walk warm-up", "minutes": 5.0, "speed_kmh": 4.5,
         "say": "Five minutes easy walking. Four and a half kilometres an hour."},
    ]
    for i, st in enumerate(proto["stages"], start=1):
        steps.append({
            "kind": "stage", "label": f"Stage {i}", "index": i,
            "minutes": float(st["duration_min"]), "speed_kmh": float(st["speed_kmh"]),
            # The last minute is the only part the fit uses, so it gets its own announcement.
            "measure_last_s": 60,
            "say": f"Stage {i}. {st['speed_kmh']:g} kilometres an hour.",
        })
    steps.append({"kind": "recovery", "label": "Walk recovery", "minutes": 5.0, "speed_kmh": 4.5,
                  "say": "Five minutes walking. Recover."})
    steps.append({"kind": "steady", "label": "Steady block", "minutes": 20.0,
                  "say": "Twenty minutes at the fastest speed you could still talk comfortably."})
    steps.append({"kind": "cooldown", "label": "Cool down", "minutes": 5.0, "speed_kmh": 4.5,
                  "say": "Five minutes walking to cool down."})

    return {
        "steps": steps,
        "stop_when_any": list(proto["stop_when_any"]),
        # Repeated at every stage change, because it is the one thing the recording cannot capture
        # and the single most informative observation in the session.
        "at_each_stage": "Say a full sentence out loud. Comfortable, effortful, or impossible?",
        "total_min": sum(float(x["minutes"]) for x in steps),
    }


def _session_dict(s: planmod.Session, paces: Any, profile: Optional[FitnessProfile] = None
                  ) -> Dict[str, Any]:
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
        # The ceiling in beats, not just the zone number. The phone has the athlete's own zone model
        # and could derive it, but a session that says "zones 1-2" and a phone that decides what that
        # means in beats is two definitions of easy, and they drift.
        if profile is not None and profile.zones is not None:
            top = max(s.zones)
            edge = next((z.high_bpm for z in profile.zones.zones if z.index == top), None)
            if edge:
                out["hr_ceiling_bpm"] = int(edge)
    if s.run_walk:
        run_min, walk_min, reps = s.run_walk
        rw: Dict[str, Any] = {"run_min": run_min, "walk_min": walk_min, "reps": reps}
        # What to run the RUNNING blocks at, which is not the session's average pace.
        #
        # The session carried nothing but a schedule -- run two minutes, walk two minutes -- so the
        # phone had no target and said nothing for twenty-six minutes. Worse, the only pace on the
        # session was the easy average, and handing that to a runner as the speed to run at asks for
        # 14:00 per mile, which is below the walk-run gait transition.
        #
        # This is the single instruction that matters most for this athlete. Told to "run", he runs
        # at 10:00 per mile, which puts him at 155 bpm within three minutes and 180 at peak; at the
        # observed easy speed he sits at 138. Same session, Z4 or Z1, decided entirely by how fast
        # the running blocks are taken. It is not something effort can be trusted to find -- the
        # whole difficulty is that the wrong pace feels like the natural one.
        if profile is not None and profile.run_block_pace_range:
            fast, slow = profile.run_block_pace_range
            mid = (fast + slow) / 2
            rw["run_pace"] = {
                "target_sec_km": round(mid, 1),
                "tolerance": round(abs(slow - fast) / 2 / mid, 4),
                "fast": fmt_pace(fast), "slow": fmt_pace(slow),
            }
        # The walk is prescribed too, and briskly. A stroll drops heart rate so far that the next
        # block starts from cold and the session becomes a series of hard starts; a brisk walk keeps
        # it aerobic. Advisory rather than coached -- nobody needs tones while walking.
        rw["walk_pace"] = {"target_sec_km": round(3600.0 / _WALK_KMH, 1),
                           "say": fmt_pace(3600.0 / _WALK_KMH)}
        out["run_walk"] = rw
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
    #
    # ``strides`` is ceiling-only for a reason that is not obvious: the alternative nags MORE. With
    # both edges enforced the coach calls "pick it up" through every walk-back recovery, which is
    # most of the stride portion; with only the fast edge it calls "ease up" during a twenty-second
    # effort the athlete already knows is fast. One is wrong about the session's own prescription,
    # the other is wrong about twenty seconds.
    out["ceiling_only"] = s.type.value in ("easy", "long", "run_walk", "recovery", "strides")
    if s.structure:
        out["structure"] = s.structure
    if s.type.value == "ramp_test" and profile is not None:
        out["ramp"] = _ramp_dict(profile)
        # The session's own duration was a hand-written 35 minutes against a protocol that runs to
        # nearly an hour once the steady block and cool-down are counted. Whichever number is wrong,
        # showing both is worse: take the one the app is about to actually run.
        out["minutes"] = round(out["ramp"]["total_min"])
    return out


def build_app_plan(profile: FitnessProfile, *,
                   config: Optional[planmod.PlanConfig] = None,
                   start_phase: planmod.Phase = planmod.Phase.ASSESS,
                   weeks_running_at_start: int = 0) -> Dict[str, Any]:
    """The schedule the phone carries, phase by phase.

    ``start_phase`` skips the export past phases already known to be done. It exists for exactly one
    situation: ASSESS's gates (screening, the ramp test, the structural screen, fourteen nights of
    HRV) are satisfied by evidence outside the app -- a completed ramp test the athlete reported, a
    self-attested screening -- and there is no other way to hand that decision to a static export.
    Advancing FOUNDATION onward stays exactly as gated as the docstring above says; this is a one-time
    door out of the phase the web app cannot itself verify the athlete has finished.
    """
    cfg = config or planmod.PlanConfig()
    phases: List[Dict[str, Any]] = []

    # ASSESS is capped at its own floor rather than the usual six.
    #
    # generate_week's ASSESS branch does not read week_in_phase at all -- it always returns the same
    # screening day, the same structural screen and the same graded ramp test, regardless of which
    # week is asked for. Shipping six of them is not six weeks of content, it is one week of content
    # copied six times, and an athlete with no way to leave ASSESS in the app (advancing a phase is
    # deliberately the engine's call, made against evidence a static export cannot hold -- see the
    # module docstring) would be invited to redo a near-maximal graded test every week for a month.
    # PHASE_MIN_WEEKS already says this phase needs exactly one; ship exactly one.
    started = SHIPPED_PHASES.index(start_phase) if start_phase in SHIPPED_PHASES else 0
    # Weeks of running elapsed, counted across the whole export rather than per phase, because bone
    # does not reset at a phase boundary.
    weeks_running = weeks_running_at_start
    longest_run_km: Optional[float] = None

    for phase in SHIPPED_PHASES[started:]:
        weeks_to_ship = PHASE_MIN_WEEKS.get(phase, WEEKS_PER_PHASE) if phase == Phase.ASSESS \
            else WEEKS_PER_PHASE
        weeks: List[Dict[str, Any]] = []
        previous_volume: Optional[float] = None
        for wk in range(1, weeks_to_ship + 1):
            w = planmod.generate_week(profile, phase, wk, week_index=wk, config=cfg,
                                      previous_week_volume=previous_volume)
            previous_volume = w.volume_target_km

            # The bone-vulnerable window, applied rather than described.
            #
            # Every other governor in this engine -- TRIMP, ACWR, readiness, the heart-rate ceiling
            # -- is cardiovascular or autonomic. Bone appears in none of them, and its adaptation
            # lags the fitness that lets you run further by months, so a new runner can pass every
            # gate, feel excellent, and be well into a tibial stress reaction. safety.py has had the
            # machinery for this since the beginning and nothing ever called it.
            #
            # What the plan asks for unclamped is worth stating, because it is the reason this is
            # needed: the long run grows 4.9 -> 5.7 -> 6.7 km in BASE_1 (+16%, +18% a week) and then
            # jumps 6.3 -> 9.1 km across the phase boundary, +44% in one step. The RUNSAFE cohort
            # (5,205 runners, 588,071 sessions) found injury hazard rising continuously from the
            # smallest progressions they measured, and the authors use that specifically to argue
            # there is no safe cut-off. A 44% single-run jump on eight-week-old bones is the shape
            # of injury this whole phase exists to avoid.
            #
            # NOT `clamp_single_run`, and the distinction matters. That function caps a run at
            # 1.00x the longest of the last thirty days while the window is armed, which is the
            # right RUNTIME rule -- it is asked "should today's run be this long, given what you
            # have actually done" and a novice should not exceed their own recent longest on a whim.
            # Applied to a GENERATOR it deadlocks: this week is capped at last week's figure, which
            # was capped at the week before's, and the long run is frozen at 4.9 km for the entire
            # eighteen-week export. Measured, not predicted -- every BASE_2 long run came out at 4.9.
            #
            # So generation uses the growth rate the same module already calls acceptable:
            # BONE_LOAD_SPIKE_RATIO, the boundary below which `single_run_progression` returns "ok".
            # The plan may grow the long run, at the fastest rate the spike guard does not flag.
            bone = safety.bone_load([], weeks_running=weeks_running)
            for sess in w.sessions:
                if not sess.distance_km:
                    continue
                if bone.in_high_risk_window and longest_run_km:
                    allowed = longest_run_km * safety.BONE_LOAD_SPIKE_RATIO
                    if sess.distance_km > allowed:
                        band, _, message = safety.single_run_progression(
                            sess.distance_km, longest_run_km, in_bone_window=True)
                        sess.distance_km = round(allowed, 1)
                        # Said out loud in the text the athlete reads. A run quietly shortened is
                        # indistinguishable from a plan that never asked for more, and an athlete
                        # who notices would be right to stop trusting both.
                        sess.structure = (sess.structure + " " if sess.structure else "") + (
                            f"Held to {sess.distance_km:.1f} km: bone adapts more slowly than "
                            f"fitness, and you are inside the first "
                            f"{safety.NEW_RUNNER_BONE_WINDOW_WEEKS} weeks of running. {message}")
                longest_run_km = max(longest_run_km or 0.0, sess.distance_km)
            weeks_running += 1

            weeks.append({
                "week": wk,
                "focus": w.focus,
                "cutback": w.is_cutback,
                "volume_km": round(w.volume_target_km, 1) if w.volume_target_km else None,
                "volume_min": round(w.volume_target_min) if w.volume_target_min else None,
                "notes": w.notes,
                "sessions": [_session_dict(s, profile.paces, profile) for s in w.sessions],
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
            "start_phase": start_phase.value,
        },
        # Always present, independent of which phases are shipped.
        #
        # The graded ramp test is only ever scheduled inside ASSESS -- it is nowhere else in
        # generate_week -- so an export that starts past ASSESS used to make the ramp permanently
        # unreachable: the app's ramp mode reads a session's own `.ramp` field, found nothing once
        # ASSESS stopped shipping, and "Load the ramp test from the plan first" became a dead end
        # forever, for every athlete who ever gets fast-forwarded past assessment. The protocol
        # itself is not week-specific -- it is derived from the profile the same way whether it is
        # week 1 or month 4 -- so it travels with the export on its own, and the app can offer a
        # recalibration ramp at any time rather than only in the one week that happens to schedule it.
        "ramp_protocol": _ramp_dict(profile),
        # The run-walk ladder as data, so the phone can move along it on evidence.
        #
        # It was baked into the weeks: week 1 got rung 0, week 2 rung 1, and so on, which makes the
        # calendar the controller. On 22 August this athlete was prescribed seven two-minute blocks,
        # managed 2.6 minutes of running with a longest block of 37 seconds, and would have been
        # asked for three-minute blocks the following Wednesday regardless. The app already computes
        # the verdict that should decide this (progression.judgeSession) and had nowhere to apply it.
        #
        # Shipping the ladder itself lets the rung be state the athlete's own sessions move, with the
        # week's prescription as the entry point rather than the whole story.
        # The bone window, stated rather than merely applied, so the athlete can see why a long run
        # was capped and when the cap lifts.
        "bone_window": {
            "weeks_running_at_start": weeks_running_at_start,
            "window_weeks": safety.NEW_RUNNER_BONE_WINDOW_WEEKS,
            "in_window": weeks_running_at_start < safety.NEW_RUNNER_BONE_WINDOW_WEEKS,
            "note": ("Bone adapts months behind the fitness that lets you run further, and appears "
                     "in none of the heart-rate measures. For the first "
                     f"{safety.NEW_RUNNER_BONE_WINDOW_WEEKS} weeks of running, single runs are "
                     "capped against your own recent longest: prefer more frequent, shorter runs "
                     "over one long one, vary the surface, and treat focal bone pain as a stop "
                     "rather than a niggle."),
        },
        "run_walk_ladder": [
            {"run_min": r, "walk_min": w, "reps": n} for r, w, n in planmod._RUN_WALK_LADDER
        ],
        "run_days": list(cfg.run_days),
        "strength_days": list(cfg.strength_days),
        "phases": phases,
    }
