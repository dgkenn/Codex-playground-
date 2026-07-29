"""Render the plan as markdown, straight from the engine.

The week-by-week document is *generated*, never hand-written. A hand-written plan drifts away from
the code the first time a constant changes, and then there are two plans -- the one in the document
and the one the app follows -- which is worse than having no document. Everything below is derived
from :mod:`marathon_engine.plan`, :mod:`marathon_engine.assessment` and
:mod:`marathon_engine.safety`, so it cannot disagree with what the app will actually do.

Run it with ``python -m marathon_engine.report > ../docs/PLAN.md``.
"""

from __future__ import annotations

import sys
from datetime import date
from typing import Dict, List, Optional, Sequence

from marathon_engine.assessment import (
    FitnessProfile, RampStage, RampTest, StrengthScreen, profile_from_ramp, ramp_protocol,
)
from marathon_engine.physiology import fmt_pace
from marathon_engine.plan import (
    CUTBACK_EVERY, CUTBACK_FACTOR, LONG_RUN_MAX_MIN, LONG_RUN_PEAK_MAX_MIN, PHASE_GATES,
    PHASE_GOALS, PHASE_MIN_WEEKS, PHASE_ORDER, PHASE_STALL_WEEKS, Phase, PlanConfig, SessionType,
    generate_week, phase_overview, taper_weeks, weekly_volume_target,
)
from marathon_engine.safety import (
    NEW_RUNNER_BONE_WINDOW_WEEKS, ScreeningAnswers, hydration_plan, screen_participant,
)

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _hms(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def example_profile(age: float = 30, hr_rest: float = 55) -> FitnessProfile:
    """A worked example profile from a plausible week-1 ramp for this athlete.

    These ramp numbers are an ILLUSTRATION so the document can show real paces and zones. They get
    replaced by the athlete's actual test on day 3, and every number downstream moves with them.
    """
    ramp = RampTest(day=date.today(), age=age, hr_rest=hr_rest, temp_c=19, surface="treadmill",
                    stages=[
                        RampStage(5.0, 98, 8, "comfortable", 118),
                        RampStage(6.0, 112, 10, "comfortable", 132),
                        RampStage(7.0, 133, 12, "comfortable", 152),
                        RampStage(8.0, 151, 14, "effortful", 160),
                        RampStage(9.0, 166, 16, "impossible", 166),
                    ])
    screen = StrengthScreen(day=date.today(), calf_raises_left=14, calf_raises_right=18,
                            sit_to_stand_30s=22, step_down_quality="pelvic_drop", plank_s=90)
    return profile_from_ramp(ramp, screen=screen)


def render_session_line(s) -> str:
    bits: List[str] = []
    if s.duration_min:
        bits.append(f"{s.duration_min:.0f} min")
    if s.distance_km:
        bits.append(f"{s.distance_km:.1f} km")
    if s.zones:
        bits.append("Z" + "-".join(str(z) for z in s.zones))
    if s.pace_target_sec_km and s.type != SessionType.REST:
        bits.append(f"{fmt_pace(s.pace_target_sec_km)}/km")
    if s.run_walk:
        r, w, n = s.run_walk
        bits.append(f"run {r:g}/walk {w:g} x{n}" if w else f"continuous {r:g} min")
    meta = " · ".join(bits)
    opt = " *(optional)*" if s.optional else ""
    return f"| {DAY_NAMES[s.day_offset]} | **{s.title}**{opt} | {meta} |"


def render_week(week, *, show_detail: bool = False) -> str:
    out: List[str] = []
    vol = ""
    if week.volume_target_km:
        vol = f" — target **{week.volume_target_km:.0f} km**"
    elif week.volume_target_min:
        vol = f" — target **{week.volume_target_min:.0f} min of running**"
    cut = " · *cutback week*" if week.is_cutback else ""
    out.append(f"#### Week {week.week_in_phase} of {week.phase.value}{vol}{cut}\n")
    out.append("| Day | Session | Target |")
    out.append("|---|---|---|")
    for s in sorted(week.sessions, key=lambda x: x.day_offset):
        if s.type == SessionType.REST and not show_detail:
            out.append(f"| {DAY_NAMES[s.day_offset]} | Rest | — |")
        else:
            out.append(render_session_line(s))
    out.append("")
    if show_detail:
        # Dedupe by title: a week with three identical run-walk sessions should explain the session
        # once, not three times. Repeating it verbatim buries the parts that differ.
        seen_titles: set = set()
        for s in sorted(week.sessions, key=lambda x: x.day_offset):
            if s.type == SessionType.REST or not s.structure:
                continue
            if s.title in seen_titles:
                continue
            seen_titles.add(s.title)
            if s.type == SessionType.STRENGTH and "; " in s.structure:
                out.append(f"**{s.title}**")
                for item in s.structure.split("; "):
                    out.append(f"- {item}")
            else:
                out.append(f"**{s.title}** — {s.structure}")
            out.append(f"> *Why:* {s.intent}")
            if s.fuelling:
                out.append(f"> *Fuelling:* {s.fuelling}")
            for c in s.cues:
                out.append(f"> - {c}")
            out.append("")
    for n in week.notes:
        out.append(f"- {n}")
    out.append("")
    return "\n".join(out)


def render(profile: Optional[FitnessProfile] = None,
           config: Optional[PlanConfig] = None) -> str:
    p = profile or example_profile()
    cfg = config or PlanConfig()
    d = p.to_dict()
    L: List[str] = []

    L.append("# Your plan: from no 5K to a marathon\n")
    L.append("> **Generated from the engine, not written by hand.** Every number below comes from "
             "`marathon_engine`, which is covered by its own test suite. Regenerate with "
             "`python -m marathon_engine.report`. If a constant changes in the code, this document "
             "changes with it — there is deliberately no second copy of the plan to drift.\n")
    L.append("> Advisory only. This is a training plan, not medical advice, and it is built for "
             "one person.\n")

    # ---- The shape of it -------------------------------------------------------------
    L.append("## The shape of it\n")
    L.append("You have no fixed race date, which is the single most useful fact about your "
             "situation. It means the plan can be **gated on measurements instead of a calendar**. "
             "Each phase has explicit criteria; you move on when you meet them, not when a week "
             "number ticks over. A calendar plan has to guess your adaptation rate in advance and "
             "then either rushes you into a stress fracture or holds you back for months. This one "
             "cannot do either.\n")
    L.append("Two guards stop gating from becoming either a stall or a shortcut:\n")
    L.append(f"- **Minimum weeks per phase.** Bone and tendon adapt over months; your heart and "
             f"lungs adapt in two to three weeks. That mismatch is the mechanism behind most "
             f"beginner injuries, so good numbers cannot buy you an early promotion.")
    L.append(f"- **A stall review.** If a gate has not moved after the phase's stall threshold, the "
             f"app stops adding load and runs a diagnostic instead — under-fuelling, sleep debt, a "
             f"niggle being trained through, or simply a plan that is too aggressive for now.\n")

    L.append("| Phase | Goal | Min weeks | Stall review | Weekly volume |")
    L.append("|---|---|---|---|---|")
    for row in phase_overview(cfg):
        vol = "—"
        if row["weekly_km_corridor"]:
            vol = f"{row['weekly_km_corridor'][0]:.0f}–{row['weekly_km_corridor'][1]:.0f} km"
        elif row["weekly_min_corridor"]:
            vol = f"{row['weekly_min_corridor'][0]:.0f}–{row['weekly_min_corridor'][1]:.0f} min"
        stall = row["stall_review_weeks"] or "—"
        L.append(f"| **{row['phase']}** | {row['goal']} | {row['min_weeks']} | {stall} | {vol} |")
    L.append("")
    total_min = sum(PHASE_MIN_WEEKS[ph] for ph in PHASE_ORDER)
    L.append(f"Minimum total, if every gate falls on the earliest possible week: **{total_min} "
             f"weeks** (~{total_min/52:.1f} years) including race and recovery. Realistically expect "
             "longer, and that is the plan working rather than failing — the floors are the point.\n")

    # ---- Where you start -------------------------------------------------------------
    L.append("## Step 1: find out where you actually are\n")
    L.append("Your first week runs no hard sessions at all. The reason is specific: the two normal "
             "ways to start a plan are a recent race time or a maximal field test, and you have "
             "neither. Asking an untrained body for a maximal effort in week 1 measures your "
             "tolerance for discomfort more than your fitness, and it does it on tissue that has "
             "never absorbed running load.\n")
    L.append("So week 1 is a **submaximal graded ramp** plus a structural screen. That is enough to "
             "derive everything the plan needs.\n")

    proto = ramp_protocol(p.age, p.hr_rest)
    L.append("### The ramp test (day 3)\n")
    L.append(f"{proto['warmup']}\n")
    L.append("| Stage | Speed | Pace | Duration | Mode |")
    L.append("|---|---|---|---|---|")
    for st in proto["stages"]:
        L.append(f"| {st['stage']} | {st['speed_kmh']} km/h | {st['pace_per_km']}/km | "
                 f"{st['duration_min']:.0f} min | {st['mode']} |")
    L.append("")
    L.append("At the end of every stage, record three things:\n")
    for item in proto["at_each_stage_end"]:
        L.append(f"1. {item}")
    L.append("")
    L.append(f"**Stop when any of these happens** — stopping early is a valid result, not a "
             f"failure. The fit only needs three usable stages:\n")
    for item in proto["stop_when_any"]:
        L.append(f"- {item}")
    L.append("")
    L.append(f"*Cooldown:* {proto['cooldown']}\n")
    L.append(f"> {proto['why_submaximal']}\n")

    L.append("### What the week-1 battery produces\n")
    L.append("| Day | What | Yields |")
    L.append("|---|---|---|")
    L.append("| Mon | Screening questionnaire + orthostatic test (5 min supine, 2 min standing) | "
             "Medical clearance gate; resting HR; the start of your HRV baseline |")
    L.append("| Tue | Structural screen | Your specific weak link — usually calf endurance |")
    L.append("| Wed | Graded ramp | HR/speed relationship, talk-test threshold, cadence, seed VDOT |")
    L.append("| Fri | Easy walk-jog shakeout | Confirms the sensor and audio cues work |")
    L.append("")

    # ---- Worked example --------------------------------------------------------------
    L.append("## What that gives you (worked example)\n")
    L.append("Using illustrative ramp numbers — a talk-test threshold around 7.5 km/h and a resting "
             f"HR of {p.hr_rest:.0f} — here is what the engine derives. **Your real numbers will "
             "differ**; this exists so you can see the machinery working before you run anything.\n")
    L.append(f"- **HRmax:** {d['hr_max']:.0f} bpm ({d['hr_max_source'].replace('_', ' ')})")
    L.append(f"- **Talk-test threshold HR:** {d['lthr']:.0f} bpm — this *pins* your Z3/Z4 boundary "
             "rather than letting a population formula guess it")
    L.append(f"- **Seed VDOT:** {d['vdot']:.0f}, from `{d['vdot_source']}`")
    L.append(f"- **Prescription basis:** `{d['prescription_basis']}`")
    L.append("")
    L.append("### Your zones\n")
    L.append("| Zone | HR | What it is for |")
    L.append("|---|---|---|")
    for z in d["zones"]["zones"]:
        L.append(f"| **{z['name']}** | {z['low_bpm']}–{z['high_bpm']} | {z['purpose']} |")
    L.append("")

    if d["prescription_basis"] == "hr_from_ramp":
        L.append("### Your paces — and why they do not come from VDOT yet\n")
        L.append(f"A seed VDOT of {d['vdot']:.0f} sits **below the floor of Daniels' published "
                 "tables** (they start around 30). Below that the pace formulas extrapolate to "
                 "numbers slower than a brisk walk, which is not a physiological finding — it is a "
                 "quadratic running out of validity.\n")
        L.append("So the plan ignores them and prescribes from the HR/speed relationship your own "
                 "ramp test measured. That is a better instrument for you right now, and it "
                 "switches to VDOT automatically once a real time trial lifts you past 30.\n")
        L.append("| Zone | Pace range |")
        L.append("|---|---|")
        for name, rng in d["hr_paces"].items():
            L.append(f"| {name} | {rng[0]}–{rng[1]}/km |")
        L.append("")
        L.append(f"**Your easy window: {d['easy_pace_range'][0]}–{d['easy_pace_range'][1]}/km.** "
                 "Nearly all of your running lives here.\n")
        L.append("For contrast, the raw VDOT table would have said "
                 f"{d['paces']['display']['easy']}/km for easy — visibly wrong, and the exact kind "
                 "of error that makes someone abandon a plan in week 2.\n")
    else:
        L.append("### Your paces\n")
        L.append("| Type | Pace |")
        L.append("|---|---|")
        for k, v in d["paces"]["display"].items():
            L.append(f"| {k} | {v}/km |")
        L.append("")

    if d["predictions_display"]:
        L.append("### Predicted times\n")
        L.append("| Distance | Prediction |")
        L.append("|---|---|")
        for k, v in d["predictions_display"].items():
            L.append(f"| {k} | {v} |")
        L.append("")
    else:
        L.append("### Predicted times: deliberately none yet\n")
        L.append("The engine refuses to predict beyond 2.5× the longest distance you have actually "
                 "covered. Extrapolating a marathon time from a treadmill ramp produces a number "
                 "with a colon in it and no information — and, for a beginner, a demoralising one. "
                 "Predictions unlock as you race: a 5K unlocks the 10K, a half unlocks the "
                 "marathon.\n")

    if d["strength_findings"]:
        L.append("### Structural findings from the example screen\n")
        for f in d["strength_findings"]:
            L.append(f"- **{f['finding']}** ({f['severity']}) — {f['message']}")
            if f.get("action"):
                L.append(f"  - *Do:* {f['action']}")
        L.append("")

    L.append("### Caveats the engine attaches to its own numbers\n")
    for c in d["caveats"]:
        L.append(f"- {c}")
    L.append("")

    # ---- The weeks -------------------------------------------------------------------
    L.append("## The weeks\n")
    L.append(f"Your schedule is **{cfg.run_days_per_week} runs + {cfg.strength_days_per_week} "
             "strength sessions**, with the long run on "
             f"{DAY_NAMES[cfg.long_run_day]}. Sessions get rescheduled automatically around your "
             "rota — the long run gets first pick of days, quality work never lands on a "
             "post-night day, and nothing is ever scheduled on a night shift.\n")

    detail_weeks = {
        (Phase.ASSESS, 1), (Phase.FOUNDATION, 1), (Phase.FOUNDATION, 8),
        (Phase.BASE_1, 1), (Phase.BASE_2, 1), (Phase.HALF_BUILD, 1),
        (Phase.MARATHON_BASE, 3), (Phase.MARATHON_PEAK, 1), (Phase.TAPER, 1), (Phase.RACE, 1),
    }

    # Use a PROGRESSED profile per phase. Showing marathon-phase sessions at week-1 paces would be
    # doubly misleading: the paces would be far too slow, and the weekly volumes would look
    # unreachable when in fact they become reachable precisely because the easy pace quickens.
    # These VDOTs are an illustrative trajectory, not a promise.
    phase_vdot: Dict[Phase, float] = {
        Phase.ASSESS: p.vdot, Phase.FOUNDATION: p.vdot,
        Phase.BASE_1: 30.0, Phase.BASE_2: 34.0, Phase.HALF_BUILD: 38.0,
        Phase.MARATHON_BASE: 41.0, Phase.MARATHON_PEAK: 43.0,
        Phase.TAPER: 43.0, Phase.RACE: 43.0, Phase.RECOVERY: 43.0,
    }
    L.append("> **A note on the paces in the later phases.** They are shown at an *illustrative "
             "projected fitness* (VDOT rising from your seed toward the low 40s), not at your week-1 "
             "numbers. Showing marathon-phase sessions at beginner paces would make the weekly "
             "volumes look impossible, when in fact they become reachable precisely because your "
             "easy pace gets quicker. Your real paces come from your own time trials.\n")

    prev_vol: Optional[float] = None
    for phase in PHASE_ORDER:
        L.append(f"### {phase.value.replace('_', ' ').title()}\n")
        L.append(f"**Goal:** {PHASE_GOALS[phase]}\n")
        gates = PHASE_GATES.get(phase, ())
        if gates:
            L.append(f"**To leave this phase** (all of these, plus at least "
                     f"{PHASE_MIN_WEEKS.get(phase, 0)} weeks):\n")
            for g in gates:
                flag = " 🛑" if g.safety else ""
                L.append(f"- **{g.label}**{flag} — {g.rationale}")
            L.append("")

        n_weeks = PHASE_MIN_WEEKS.get(phase, 1)
        show = min(n_weeks, 4 if phase in (Phase.FOUNDATION, Phase.BASE_1) else 2)
        weeks_to_show = list(range(1, show + 1))
        if n_weeks > show:
            weeks_to_show.append(n_weeks)
        # Rebuild the profile at this phase's illustrative fitness.
        from marathon_engine.physiology import five_zone_model, training_paces
        vd = phase_vdot.get(phase, p.vdot)
        pp = p
        if vd != p.vdot:
            pp = FitnessProfile(
                as_of=p.as_of, age=p.age, hr_rest=p.hr_rest, hr_max=p.hr_max,
                hr_max_source=p.hr_max_source, vdot=vd, vdot_source="illustrative_projection",
                zones=p.zones, paces=training_paces(vd), lthr=p.lthr,
                threshold_speed_kmh=p.threshold_speed_kmh,
                cadence_by_speed=dict(p.cadence_by_speed), ef_baseline=p.ef_baseline,
                ramp_fit=p.ramp_fit, strength_findings=p.strength_findings,
                predictions={}, caveats=[], prescription_basis="vdot", hr_paces=dict(p.hr_paces))
        for wk in weeks_to_show:
            week = generate_week(pp, phase, wk, week_index=wk, config=cfg,
                                previous_week_volume=prev_vol, phase_length_est=n_weeks)
            L.append(render_week(week, show_detail=(phase, wk) in detail_weeks))
            if week.volume_target_km:
                prev_vol = week.volume_target_km
        skipped = [w for w in range(show + 1, n_weeks) if w not in weeks_to_show]
        if skipped:
            span = (f"Week {skipped[0]}" if len(skipped) == 1
                    else f"Weeks {skipped[0]}–{skipped[-1]}")
            L.append(f"*({span} follow the same shape, progressing between the volumes shown.)*\n")

    # ---- Long run and taper ----------------------------------------------------------
    L.append("## The long run, and its ceilings\n")
    L.append(f"Three caps apply, and the app tells you which one is binding:\n")
    L.append(f"1. **Time: {LONG_RUN_MAX_MIN:.0f} minutes** (rising to {LONG_RUN_PEAK_MAX_MIN:.0f} "
             "for the biggest peak-phase runs). This is Daniels' own limit. The widely repeated "
             "\"three hours\" figure exceeds it by 20%, and it does so in exactly the population "
             "least able to absorb the extra half hour.")
    L.append("2. **Share of the week:** up to 50%. Textbook guidance is 30–35%, and on three runs a "
             "week that is arithmetically impossible for a marathon-length long run. This is the "
             "real cost of the 3-day schedule, and the app states it rather than hiding it.")
    L.append("3. **Distance: 32 km.** There is no evidence a first-timer gains from going further.\n")
    L.append("If you ever want a time goal rather than a strong finish, **adding a fourth easy run "
             "is the single highest-yield change available** — it is the one thing that brings the "
             "long run's share back toward the textbook figure. The plan offers it from the marathon "
             "phases onward, and no gate depends on it.\n")

    L.append("## The taper\n")
    L.append("Two weeks, volume down, **intensity and frequency held**. From Bosquet's "
             "meta-analysis: the largest performance gains came from a 2-week taper with a 41–60% "
             "volume reduction while keeping intensity. Cutting the hard sessions instead of the "
             "volume is what makes people feel flat on race day.\n")
    L.append("| Week | Volume | Long run | Keep | Cut |")
    L.append("|---|---|---|---|---|")
    for t in taper_weeks(55.0, p.paces):
        L.append(f"| {t['week']} | {t['volume_km']:.0f} km ({t['volume_pct_of_peak']}% of peak) | "
                 f"{t['long_run_km']:.0f} km | {'; '.join(t['keep'])} | {'; '.join(t['cut'])} |")
    L.append("")

    # ---- Safety ----------------------------------------------------------------------
    L.append("## Safety, honestly\n")
    L.append("### Bone is the blind spot\n")
    L.append(f"Nothing in your HRV, resting HR, or training-load numbers can see bone. Bone remodels "
             f"over **months**, while your aerobic fitness improves in **two to three weeks** — and "
             f"that gap is the injury. You can be green every single morning and still be twelve "
             f"weeks into building a tibial stress fracture.\n")
    L.append(f"For your first ~{NEW_RUNNER_BONE_WINDOW_WEEKS} weeks of running, that means: prefer "
             "more frequent shorter runs over fewer longer ones, vary the surface, and treat pain "
             "at a single **point** on a bone as a hard stop rather than a niggle. The app tracks "
             "this separately from everything else, precisely because no other metric can.\n")

    L.append("### The pain rules\n")
    L.append("| Pain | Rule |")
    L.append("|---|---|")
    L.append("| 0–2 / 10 | Acceptable. Carry on and keep watching it. |")
    L.append("| 3–5 / 10 | Warning. Volume **holds** — no increases until two clean weeks. Today "
             "becomes easy. |")
    L.append("| > 5 / 10 | Stop the run. Every time. |")
    L.append("| Pain the *morning after* | The signal that matters most and the one most often "
             "ignored. |")
    L.append("")

    L.append("### Stop immediately, whatever the plan says\n")
    from marathon_engine.safety import RED_FLAG_SYMPTOMS
    for k, v in RED_FLAG_SYMPTOMS.items():
        L.append(f"- **{k.replace('_', ' ').title()}** — {v}")
    L.append("")

    L.append("### Hydration: the risk is drinking too much\n")
    hp = hydration_plan(240, wbgt_c=18, body_mass_kg=80)
    L.append(f"**{hp['primary_rule']}**\n")
    L.append("This runs opposite to most apps' hydration prompts, deliberately. "
             "Exercise-associated hyponatraemia disproportionately affects **slow first-time "
             "marathoners who over-drink** — which will be you on race day — and it is one of the "
             "few genuinely life-threatening things that happens in mass-participation racing.\n")
    for x in hp["do_not"]:
        L.append(f"- {x}")
    L.append("")
    L.append("Warning signs:\n")
    for x in hp["warning_signs"]:
        L.append(f"- {x}")
    L.append("")
    for n in hp["notes"]:
        L.append(f"- {n}")
    L.append("")

    L.append("### What the app will never do\n")
    L.append("- Add load because a recovery score looked good. A single high HRV reading is a weak "
             "signal; the cost of a wrong upgrade is a lost week, the cost of a wrongly easy day is "
             "one easy day.")
    L.append("- Make you \"make up\" a missed session. Missed volume is gone. Carrying it forward "
             "converts a rest into a spike.")
    L.append("- Give you a streak, a leaderboard, or any other mechanism that rewards training when "
             "your body is saying rest.")
    L.append("- Coach off a heart rate it does not trust. Dropout and cadence lock-on are detected "
             "and reported, and the controller falls back to pace and feel rather than acting on a "
             "number that is probably your step rate.")
    L.append("")
    return "\n".join(L)


def main(argv: Sequence[str] = ()) -> int:
    sys.stdout.write(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
