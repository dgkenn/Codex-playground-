"""The coach, without the phone.

Everything the iPhone app decides is decided here first -- the app is a port of this engine plus a
sensor driver and a voice. So with no Mac and therefore no app, this is not a degraded fallback; it is
the same brain reached through a terminal instead of a touchscreen. What it cannot do is the two
things that genuinely need the phone: read the armband live, and talk to you mid-run.

    python -m marathon_engine.cli protocol          # the session to record
    python -m marathon_engine.cli import run.tcx    # turn a Polar Flow export into your profile
    python -m marathon_engine.cli today             # what to do today
    python -m marathon_engine.cli week              # this week
    python -m marathon_engine.cli log --minutes 32 --km 4.1 --rpe 4
    python -m marathon_engine.cli status            # where you are and what the gates want
    python -m marathon_engine.cli review            # end-of-week review

State lives in ``~/.marathon-coach`` as plain JSON, one file per concern, so it can be read, edited,
backed up and diffed without this program. A training history you cannot inspect is one you cannot
trust, and it will outlive whatever code is reading it today.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from marathon_engine import plan as planmod
from marathon_engine.assessment import FitnessProfile
from marathon_engine.calibration import analyse_recording, calibration_protocol
from marathon_engine.importers import label_stages, load_any
from marathon_engine.physiology import fmt_pace, hr_max_estimate

STATE_DIR = Path.home() / ".marathon-coach"
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ------------------------------------------------------------------------------------------------
# Storage
# ------------------------------------------------------------------------------------------------


def _default(o: Any) -> Any:
    if is_dataclass(o):
        return asdict(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, tuple):
        return list(o)
    if hasattr(o, "value"):          # Enum
        return o.value
    if hasattr(o, "__dict__"):
        return {k: v for k, v in vars(o).items() if not k.startswith("_")}
    return str(o)


def _read(name: str, fallback: Any) -> Any:
    p = STATE_DIR / name
    if not p.exists():
        return fallback
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: could not read {p}: {exc}", file=sys.stderr)
        return fallback


def _write(name: str, payload: Any) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = STATE_DIR / name
    # Written to a sibling then moved, so an interrupted write cannot truncate the history that is
    # already there. A half-written sessions.json is worse than no sessions.json.
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=_default))
    tmp.replace(p)
    return p


def _profile() -> Optional[Dict[str, Any]]:
    return _read("profile.json", None)


def _state() -> Dict[str, Any]:
    return _read("state.json", {"phase": "assess", "week_in_phase": 1, "week_index": 1})


def _sessions() -> List[Dict[str, Any]]:
    return _read("sessions.json", [])


# ------------------------------------------------------------------------------------------------
# Formatting
# ------------------------------------------------------------------------------------------------


def _rule(title: str = "") -> str:
    return f"\n{'=' * 78}\n{title}\n{'=' * 78}" if title else "=" * 78


def _wrap(text: str, indent: str = "    ", width: int = 74) -> str:
    import textwrap
    return "\n".join(textwrap.fill(line, width=width, initial_indent=indent,
                                   subsequent_indent=indent)
                     for line in text.split("\n") if line.strip())


def _profile_or_die() -> FitnessProfile:
    p = _profile()
    if p is None:
        print("No profile yet. Two ways to get one:\n\n"
              "  1. Record the calibration session and import it:\n"
              "       python -m marathon_engine.cli protocol\n"
              "       python -m marathon_engine.cli import <export.tcx>\n\n"
              "  2. Start from age-based estimates, and let the first weeks measure you:\n"
              "       python -m marathon_engine.cli init --age 30 --hr-rest 55\n",
              file=sys.stderr)
        raise SystemExit(2)
    return _rehydrate(p)


def _rehydrate(d: Dict[str, Any]) -> FitnessProfile:
    """Rebuild a FitnessProfile from stored JSON.

    Kept explicit rather than clever: the stored shape is a stable file format that outlives any
    refactor of the dataclass, so a field appearing or disappearing should be a visible change here
    rather than a silent ``TypeError`` at some later call site.
    """
    from marathon_engine.physiology import TrainingPaces, ZoneModel, Zone

    zones_d = d["zones"]
    zones = ZoneModel(
        kind=zones_d.get("kind", "five_zone_hrr"),
        hr_max=zones_d["hr_max"], hr_rest=zones_d["hr_rest"], lthr=zones_d.get("lthr"),
        zones=tuple(Zone(**z) for z in zones_d["zones"]))
    pd = dict(d["paces"])
    pd["easy_range"] = tuple(pd["easy_range"])
    paces = TrainingPaces(**pd)
    return FitnessProfile(
        as_of=date.fromisoformat(d["as_of"]), age=d["age"], hr_rest=d["hr_rest"],
        hr_max=d["hr_max"], hr_max_source=d["hr_max_source"], vdot=d["vdot"],
        vdot_source=d["vdot_source"], zones=zones, paces=paces, lthr=d.get("lthr"),
        threshold_speed_kmh=d.get("threshold_speed_kmh"),
        cadence_by_speed={float(k): v for k, v in (d.get("cadence_by_speed") or {}).items()},
        ef_baseline=d.get("ef_baseline"),
        ramp_fit=tuple(d["ramp_fit"]) if d.get("ramp_fit") else None,
        predictions=d.get("predictions") or {}, caveats=d.get("caveats") or [],
        prescription_basis=d.get("prescription_basis", "vdot"),
        hr_paces={k: tuple(v) for k, v in (d.get("hr_paces") or {}).items()})


# ------------------------------------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------------------------------------


def cmd_protocol(args: argparse.Namespace) -> int:
    p = _profile()
    age = args.age or (p["age"] if p else 30.0)
    hr_rest = args.hr_rest or (p["hr_rest"] if p else 55.0)
    proto = calibration_protocol(age=age, hr_rest=hr_rest)

    print(_rule("CALIBRATION SESSION"))
    print(f"\nAbout {proto['total_min']:.0f} minutes in total.\n")

    print("BEFORE YOU START")
    for line in proto["device_setup"]:
        print(_wrap(f"- {line}", indent="  "))

    rb = proto["resting_block"]
    print("\nRESTING BLOCK  (do this first, before any movement)")
    print(_wrap(f"{rb['what']}  Streams: {rb['streams']}", indent="  "))
    print(_wrap(f"Why: {rb['why']}", indent="  "))

    print(f"\nWARM-UP\n  {proto['warmup']}")

    print("\nSTAGES  (4 minutes each, no break between them)")
    print(f"  {'stage':<10}{'speed':>10}{'pace/km':>12}   mode")
    for s in proto["stages"]:
        print(f"  {s['label']:<10}{s['speed_kmh']:>7.1f} km/h{s['pace_per_km']:>12}   {s['mode']}")

    for key in ("steady_block", "stop_rules", "afterwards"):
        val = proto.get(key)
        if not val:
            continue
        print(f"\n{key.replace('_', ' ').upper()}")
        if isinstance(val, str):
            print(_wrap(val, indent="  "))
        elif isinstance(val, dict):
            for k, v in val.items():
                print(_wrap(f"{k}: {v}", indent="  "))
        else:
            for v in val:
                print(_wrap(f"- {v}", indent="  "))

    print("\nAFTERWARDS")
    print(_wrap("Sync in Polar Flow, then export the session as TCX from flow.polar.com and run:",
                indent="  "))
    print("      python -m marathon_engine.cli import <file>.tcx")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    p = _profile()
    age = args.age or (p["age"] if p else None)
    hr_rest = args.hr_rest or (p["hr_rest"] if p else None)
    if age is None or hr_rest is None:
        print("Need --age and --hr-rest the first time (there is no profile to take them from).",
              file=sys.stderr)
        return 2

    try:
        rec, warnings = load_any(args.path, age=age, hr_rest=hr_rest, surface=args.surface)
    except (OSError, ValueError) as exc:
        print(f"Could not read {args.path}: {exc}", file=sys.stderr)
        return 1

    n_stages = label_stages(rec)
    result = analyse_recording(rec)

    print(_rule("IMPORT"))
    dur = (rec.samples[-1].t_s - rec.samples[0].t_s) / 60 if rec.samples else 0
    print(f"\n{len(rec.samples)} samples, {dur:.0f} minutes, {n_stages} steady stage(s) recovered.")

    if warnings:
        print("\nWHAT THIS FILE COULD NOT TELL ME")
        for w in warnings:
            print(_wrap(f"- {w}", indent="  "))

    s = result.sensor
    print("\nSENSOR")
    print(f"  heart-rate coverage {s.hr_coverage * 100:.0f}%   frozen {s.frozen_fraction * 100:.0f}%"
          f"   verdict: {s.verdict}")
    for f in s.findings:
        print(_wrap(f"- {f}", indent="  "))

    if result.gait and result.gait.cadence_overall:
        print(f"\nGAIT\n  cadence {result.gait.cadence_overall:.0f} spm overall")

    prof = result.profile
    if prof is None:
        print("\nNO PROFILE PRODUCED")
        print(_wrap("No steady stages long enough to fit heart rate against speed. That fit is the "
                    "whole point of the calibration session, and it needs constant-speed blocks of "
                    "at least two and a half minutes each. A variable-pace outdoor run cannot "
                    "produce it. Re-record following `protocol`, ideally on a treadmill where speed "
                    "is imposed rather than chosen.", indent="  "))
        return 1

    print("\nPROFILE")
    print(f"  HRmax        {prof.hr_max:.0f} bpm   ({prof.hr_max_source})")
    print(f"  resting HR   {prof.hr_rest:.0f} bpm")
    if prof.ramp_fit:
        slope, intercept, r2 = prof.ramp_fit
        print(f"  HR vs speed  {slope:.1f} bpm per km/h   (r2 = {r2:.3f})")
        print(_wrap("This slope is what makes the in-run coaching yours rather than a guessed "
                    "constant: it is how much your heart rate moves for a given change of pace.",
                    indent="    "))
    print(f"  VDOT         {prof.vdot:.1f}   ({prof.vdot_source})")
    print(f"  basis        {prof.prescription_basis}")
    if prof.lthr:
        print(f"  LTHR         {prof.lthr:.0f} bpm")

    print("\n  ZONES")
    for z in prof.zones.zones:
        print(f"    {z.name:<16}{z.low_bpm:>4}-{z.high_bpm:<4} bpm   {z.purpose}")

    paces = prof.hr_paces if prof.prescription_basis == "hr_from_ramp" else None
    if paces:
        print("\n  PACES  (from your measured heart-rate line, not from a VDOT table)")
        for name, (fast, slow) in paces.items():
            print(f"    {name:<16}{fmt_pace(slow)} - {fmt_pace(fast)} /km")

    if prof.caveats:
        print("\n  READ THESE")
        for c in prof.caveats:
            print(_wrap(f"- {c}", indent="    "))

    if args.save:
        path = _write("profile.json", prof)
        _write("state.json", _state())
        print(f"\nSaved to {path}")
        print("Next:  python -m marathon_engine.cli week")
    else:
        print("\n(Nothing saved. Re-run with --save to keep this as your profile.)")
    return 0


def _estimated_profile(*, age: float, hr_rest: float) -> FitnessProfile:
    """A profile from age alone, every field labelled as the estimate it is.

    This exists so the plan is usable on day one, before any calibration session. It is deliberately
    pessimistic about itself: `hr_max_source` says `age_formula`, `vdot_source` says `assumed_novice`,
    and the caveats say what that costs. Everything downstream keys off those labels, so an estimated
    profile can never be mistaken for a measured one.
    """
    from marathon_engine.physiology import five_zone_model, training_paces

    hr_max = hr_max_estimate(age)
    # The lowest VDOT the tables cover. Someone who has not run a 5K is at or below this, and
    # pretending otherwise prescribes paces they cannot hold.
    vdot = 30.0
    zones = five_zone_model(hr_max=hr_max, hr_rest=hr_rest)
    return FitnessProfile(
        as_of=date.today(), age=age, hr_rest=hr_rest, hr_max=hr_max,
        hr_max_source="age_formula", vdot=vdot, vdot_source="assumed_novice",
        zones=zones, paces=training_paces(vdot), prescription_basis="hr_from_ramp",
        caveats=[
            "HRmax is Tanaka's age formula, which has a between-individual standard deviation of "
            "about 7 bpm. Your zones could be most of a zone-width wrong in either direction, so "
            "treat the zone edges as soft until a real measurement replaces them.",
            "VDOT is the table floor, assumed rather than measured. Paces derived from it are a "
            "starting point only. The 2000 m trial in week 5 of BASE_1 replaces it with something "
            "real; until then, run by effort and let heart rate be the check.",
        ])


def cmd_init(args: argparse.Namespace) -> int:
    """Seed a profile from age-based estimates, clearly labelled as estimates."""
    prof = _estimated_profile(age=args.age, hr_rest=args.hr_rest)
    _write("profile.json", prof)
    _write("state.json", {"phase": "assess", "week_in_phase": 1, "week_index": 1})
    print(f"Profile seeded from estimates: HRmax {prof.hr_max:.0f} ({prof.hr_max_source}), "
          f"VDOT {prof.vdot:.1f} ({prof.vdot_source}).")
    print(_wrap("These are population estimates, not measurements. Tanaka's formula has a standard "
                "deviation of about 7 bpm between individuals, so your zones could be a zone-width "
                "wrong in either direction. Record the calibration session and import it as soon as "
                "you can -- everything downstream gets better at once.", indent="  "))
    return 0


def _phase(st: Dict[str, Any]) -> planmod.Phase:
    """Tolerant of the stored value's case, strict about it being a real phase."""
    raw = str(st.get("phase", "assess")).strip().lower()
    try:
        return planmod.Phase(raw)
    except ValueError:
        valid = ", ".join(p.value for p in planmod.Phase)
        raise SystemExit(f"state.json has phase {raw!r}, which is not one of: {valid}")


def _week_for(prof: FitnessProfile, st: Dict[str, Any]) -> planmod.PlannedWeek:
    phase = _phase(st)
    sessions = _sessions()
    prev = None
    if sessions:
        recent = sessions[-7:]
        prev = sum(s.get("km", 0) or 0 for s in recent) or None
    return planmod.generate_week(prof, phase, st["week_in_phase"],
                                 week_index=st.get("week_index", 1),
                                 previous_week_volume=prev)


def _print_session(s: planmod.Session, prefix: str = "") -> None:
    tag = "  (optional)" if s.optional else ""
    print(f"{prefix}{DAY_NAMES[s.day_offset]:<10}{s.title}{tag}")
    pad = prefix + "          "
    if s.structure:
        print(_wrap(s.structure, indent=pad))
    if s.pace_range_sec_km:
        lo, hi = s.pace_range_sec_km
        print(f"{pad}pace  {fmt_pace(hi)} - {fmt_pace(lo)} /km")
    elif s.pace_target_sec_km:
        print(f"{pad}pace  {fmt_pace(s.pace_target_sec_km)} /km")
    if s.zones:
        print(f"{pad}zones {list(s.zones)}")
    if s.run_walk:
        run_m, walk_m, reps = s.run_walk
        print(f"{pad}run {run_m:g} min / walk {walk_m:g} min x {reps}")
    if s.intent:
        print(_wrap(f"why: {s.intent}", indent=pad))


def cmd_week(args: argparse.Namespace) -> int:
    prof = _profile_or_die()
    st = _state()
    week = _week_for(prof, st)
    print(_rule(f"{_phase(st).value.upper()}  week {st['week_in_phase']}   "
                f"(overall week {st.get('week_index', 1)})"))
    if week.focus:
        print(_wrap(f"Focus: {week.focus}", indent="  "))
    for n in week.notes:
        print(_wrap(f"- {n}", indent="  "))
    if week.is_cutback:
        print(_wrap("Cutback week. The reduction is the training, not a break from it.",
                    indent="  "))
    print()
    for s in week.sessions:
        _print_session(s, prefix="  ")
    if week.volume_target_km:
        print(f"\n  target {week.volume_target_km:.1f} km")
    elif week.volume_target_min:
        print(f"\n  target {week.volume_target_min:.0f} min")
    return 0


def cmd_today(args: argparse.Namespace) -> int:
    prof = _profile_or_die()
    st = _state()
    week = _week_for(prof, st)
    today = date.today().weekday()
    todays = [s for s in week.sessions if s.day_offset == today]
    print(_rule(DAY_NAMES[today]))
    if not todays:
        print("\n  Nothing scheduled. Rest is part of the plan, not an absence of it.\n")
        return 0
    print()
    for s in todays:
        _print_session(s, prefix="  ")
    print()
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    entry = {
        "date": (args.date or date.today().isoformat()),
        "minutes": args.minutes, "km": args.km, "rpe": args.rpe,
        "mean_hr": args.mean_hr, "pain": args.pain, "notes": args.notes or "",
        "type": args.type,
    }
    sessions = _sessions()
    sessions.append(entry)
    _write("sessions.json", sessions)
    print(f"Logged {args.minutes:.0f} min"
          + (f", {args.km:.2f} km" if args.km else "")
          + (f", RPE {args.rpe}" if args.rpe else ""))
    if args.pain and args.pain >= 3:
        print(_wrap(f"Pain {args.pain}/10 recorded. 3-5 holds volume rather than adding; above 5 the "
                    "rule is stop. Pain the morning after is the most informative signal there is, "
                    "so log that too.", indent="  "))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    prof = _profile_or_die()
    st = _state()
    sessions = _sessions()
    print(_rule("STATUS"))
    print(f"\n  phase        {_phase(st).value}, week {st['week_in_phase']}")
    print(f"  profile      HRmax {prof.hr_max:.0f} ({prof.hr_max_source}), "
          f"VDOT {prof.vdot:.1f} ({prof.vdot_source})")
    print(f"  basis        {prof.prescription_basis}")
    print(f"  sessions     {len(sessions)} logged")

    if sessions:
        last14 = [s for s in sessions
                  if (date.today() - date.fromisoformat(s["date"])).days < 14]
        km = sum(s.get("km") or 0 for s in last14)
        mins = sum(s.get("minutes") or 0 for s in last14)
        print(f"  last 14 days {km:.1f} km over {mins:.0f} min, {len(last14)} sessions")

    report = planmod.evaluate_gates(_phase(st), st["week_in_phase"], evidence={})
    print("\n  WHAT THE NEXT GATE WANTS")
    print(f"    minimum weeks satisfied: {'yes' if report.min_weeks_satisfied else 'no'}")
    for g in report.unmet:
        print(_wrap(f"- NOT MET: {g.get('label', g.get('key', g))}", indent="    "))
    # `unknown` is not `unmet`, and conflating them is how a plan starts lying to you: one means the
    # criterion failed, the other means nothing has measured it yet.
    for g in report.unknown:
        print(_wrap(f"- not yet measured: {g.get('label', g.get('key', g))}", indent="    "))
    if report.guidance:
        print()
        print(_wrap(report.guidance, indent="    "))
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from marathon_engine.adapt import replan_week
    prof = _profile_or_die()
    st = _state()
    week = _week_for(prof, st)
    sessions = _sessions()
    since = date.today() - timedelta(days=7)
    recent = [s for s in sessions if date.fromisoformat(s["date"]) >= since]
    achieved = sum(s.get("km") or 0 for s in recent)
    planned = week.volume_target_km

    print(_rule("WEEKLY REVIEW"))
    print(f"\n  planned  {planned if planned else '?'} km")
    print(f"  achieved {achieved:.1f} km over {len(recent)} sessions")

    decision = replan_week(planned_volume=planned, achieved_volume=achieved,
                           sessions_completed=len(recent),
                           sessions_planned=len(week.running_sessions))
    print(f"\n  action: {decision.action}")
    if decision.next_volume is not None:
        print(f"  next week: {decision.next_volume:.1f} km")
    for r in decision.reasons:
        print(_wrap(f"- {r}", indent="    "))
    for w in decision.warnings:
        print(_wrap(f"! {w}", indent="    "))

    if args.advance:
        st["week_in_phase"] += 1
        st["week_index"] = st.get("week_index", 1) + 1
        _write("state.json", st)
        print(f"\n  Advanced to week {st['week_in_phase']} of {st['phase']}.")
    else:
        print("\n  (Re-run with --advance to move to next week.)")
    return 0


# ------------------------------------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="marathon_engine.cli",
                                 description="Marathon coach, without the phone.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("protocol", help="print the calibration session to record")
    p.add_argument("--age", type=float)
    p.add_argument("--hr-rest", type=float, dest="hr_rest")
    p.set_defaults(func=cmd_protocol)

    p = sub.add_parser("import", help="import a TCX/CSV/JSON recording and build a profile")
    p.add_argument("path")
    p.add_argument("--age", type=float)
    p.add_argument("--hr-rest", type=float, dest="hr_rest")
    p.add_argument("--surface", default="road", choices=["road", "treadmill", "track", "trail"])
    p.add_argument("--save", action="store_true", help="keep the result as your profile")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("init", help="seed a profile from age-based estimates")
    p.add_argument("--age", type=float, required=True)
    p.add_argument("--hr-rest", type=float, dest="hr_rest", required=True)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("week", help="this week's sessions")
    p.set_defaults(func=cmd_week)

    p = sub.add_parser("today", help="today's session")
    p.set_defaults(func=cmd_today)

    p = sub.add_parser("log", help="record a completed session")
    p.add_argument("--minutes", type=float, required=True)
    p.add_argument("--km", type=float)
    p.add_argument("--rpe", type=float)
    p.add_argument("--mean-hr", type=float, dest="mean_hr")
    p.add_argument("--pain", type=int, help="0-10, worst during or after")
    p.add_argument("--type", default="easy")
    p.add_argument("--date")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("status", help="where you are")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("review", help="end-of-week review")
    p.add_argument("--advance", action="store_true", help="move to next week")
    p.set_defaults(func=cmd_review)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
