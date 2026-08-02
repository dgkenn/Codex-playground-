"""Export the plan, gates and golden vectors as JSON for the iOS app to bundle.

Three artifacts, each with a different job:

* ``plan.json`` — the full phase structure, gates and weekly templates. The app **consumes** this
  rather than reimplementing plan generation, which is the whole point: plan construction runs once a
  week, so duplicating it in Swift would double the surface where the two implementations could drift
  apart for no benefit.
* ``golden_vectors.json`` — input/output pairs for the logic that *does* have to exist twice (zones,
  the real-time controller, signal gating). Both the Python tests and the Swift XCTests read this same
  file, so "the port matches" becomes a checkable claim rather than a hopeful one.
* ``protocols.json`` — the assessment and calibration protocols as structured data, so the app can
  render them as checklists without hardcoding the text.

Run: ``python -m marathon_engine.export ../ios/MarathonCoach/Resources``
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from marathon_engine.assessment import (
    FitnessProfile, RampStage, RampTest, ramp_protocol, profile_from_ramp,
)
from marathon_engine.calibration import calibration_protocol
from marathon_engine.physiology import (
    VDOT_IR_FLOOR, five_zone_model, grade_adjusted_pace_factor, minetti_cost, training_paces,
)
from marathon_engine.plan import (
    PHASE_GATES, PHASE_GOALS, PHASE_MIN_WEEKS, PHASE_ORDER, PHASE_STALL_WEEKS, Phase, PlanConfig,
    generate_week, phase_overview, taper_weeks,
)
from marathon_engine.realtime import (
    ControlMode, InRunController, RunTick, SessionIntent, classify_hr_rise,
    predict_steady_state_hr, speed_correction,
)
from marathon_engine.adapt import replan_week
from marathon_engine.load import acwr, ewma_load
from marathon_engine.safety import RED_FLAG_SYMPTOMS, SUPPLEMENT_CHECKS, hydration_plan
from marathon_engine.signal_quality import (
    HrGate, HrSample, cadence_lock_suspicion, frozen_hr_suspicion, not_worn_suspicion,
)

EXPORT_VERSION = 1

__all__ = ["export_plan", "export_golden_vectors", "export_protocols", "write_all",
           "EXPORT_VERSION"]


def _reference_profile() -> FitnessProfile:
    """The profile the exported templates are rendered against.

    Deliberately the same illustrative ramp used in the generated document, so the bundled plan and
    the written plan describe the same thing. The app replaces it with the athlete's real profile on
    first launch; these templates carry the *structure*, and the paces get recomputed on device.
    """
    ramp = RampTest(day=date(2026, 8, 5), age=30, hr_rest=55, temp_c=19, surface="treadmill",
                    stages=[RampStage(5.0, 98, 8, "comfortable", 118),
                            RampStage(6.0, 112, 10, "comfortable", 132),
                            RampStage(7.0, 133, 12, "comfortable", 152),
                            RampStage(8.0, 151, 14, "effortful", 160),
                            RampStage(9.0, 166, 16, "impossible", 166)])
    return profile_from_ramp(ramp)


def export_plan(config: Optional[PlanConfig] = None) -> Dict[str, Any]:
    """The whole plan structure: phases, gates, and one rendered week per phase-week."""
    cfg = config or PlanConfig()
    p = _reference_profile()
    phases: List[Dict[str, Any]] = []
    for phase in PHASE_ORDER:
        n = PHASE_MIN_WEEKS.get(phase, 1)
        weeks = []
        prev_vol: Optional[float] = None
        # Export every week up to the phase minimum, plus a few beyond so a phase that runs long
        # still has templates. A gated plan can sit in a phase well past its minimum, and falling
        # back to "repeat the last week forever" would silently stop progressing.
        for wk in range(1, n + 9):
            w = generate_week(p, phase, wk, week_index=wk, config=cfg,
                              previous_week_volume=prev_vol, phase_length_est=n)
            weeks.append(w.to_dict())
            if w.volume_target_km:
                prev_vol = w.volume_target_km
        phases.append({
            "phase": phase.value,
            "goal": PHASE_GOALS[phase],
            "min_weeks": n,
            "stall_review_weeks": PHASE_STALL_WEEKS.get(phase),
            "gates": [g.to_dict() for g in PHASE_GATES.get(phase, ())],
            "weeks": weeks,
        })
    return {
        "export_version": EXPORT_VERSION,
        "generated_from": "marathon_engine.export",
        "config": cfg.to_dict(),
        "phase_order": [ph.value for ph in PHASE_ORDER],
        "overview": phase_overview(cfg),
        "phases": phases,
        "taper": taper_weeks(50.0, p.paces),
        "reference_profile": p.to_dict(),
        "vdot_ir_floor": VDOT_IR_FLOOR,
    }


def export_golden_vectors() -> Dict[str, Any]:
    """Input/output pairs for every piece of logic that exists in both Python and Swift.

    This is the mechanism that keeps the port honest. Each entry is a call and its expected result;
    ``PortParityTests.swift`` reads the same file and asserts the Swift implementation agrees. Where a
    vector disagrees, the Python side is authoritative by definition -- it is the one with the science
    tests behind it.
    """
    v: Dict[str, Any] = {"export_version": EXPORT_VERSION}

    # Zones for a range of anchors, including a pinned LTHR.
    zone_cases = []
    for hr_max, hr_rest, lthr in ((187, 55, None), (187, 55, 142), (180, 48, 158), (195, 62, None)):
        m = five_zone_model(hr_max, hr_rest, lthr=lthr)
        zone_cases.append({"hr_max": hr_max, "hr_rest": hr_rest, "lthr": lthr,
                           "zones": [{"index": z.index, "low_bpm": z.low_bpm,
                                      "high_bpm": z.high_bpm} for z in m.zones]})
    v["zones"] = zone_cases

    # Minetti gradient factors, including the clamped extremes and the downhill minimum.
    v["grade_factors"] = [{"grade": g, "factor": round(grade_adjusted_pace_factor(g), 9),
                           "cost": round(minetti_cost(g), 9)}
                          for g in (-0.9, -0.45, -0.3, -0.2, -0.15, -0.1, -0.05, 0.0,
                                    0.02, 0.05, 0.1, 0.2, 0.45, 0.9)]

    # Training paces across the VDOT range, including either side of the I/R floor.
    v["paces"] = [{"vdot": vd,
                   "easy": round(training_paces(vd).easy, 6),
                   "marathon": round(training_paces(vd).marathon, 6),
                   "threshold": round(training_paces(vd).threshold, 6),
                   "interval": round(training_paces(vd).interval, 6),
                   "repetition": round(training_paces(vd).repetition, 6),
                   "ir_prescribable": training_paces(vd).ir_prescribable}
                  for vd in (22, 28, 30, 34, 35, 40, 50, 60)]

    # Lead compensation and the feedforward gain.
    v["steady_state_hr"] = [{"hr": hr, "slope_bpm_s": sl,
                             "hr_ss": round(predict_steady_state_hr(hr, sl), 9)}
                            for hr, sl in ((140, 0.0), (140, 0.2), (140, -0.2), (165, 0.35))]
    v["speed_correction"] = [{"hr_error": e, "slope_bpm_kmh": s,
                              "delta_m_s": round(speed_correction(e, s), 9)}
                             for e, s in ((12, 12), (-10, 12), (10, 0.001), (25, 15))]

    # Drift vs effort classification.
    drift_cases = []
    for name, hr_fn, sp_fn in (
        ("stable", lambda i: 140.0, lambda i: 3.0),
        ("drift", lambda i: 140.0 + i / 60.0, lambda i: 3.0),
        ("effort_increase", lambda i: 140.0 + 10.0 * i / 60.0, lambda i: 3.0),
        ("pace_varying", lambda i: 140.0 + i / 60.0,
         lambda i: 3.0 + 0.5 * math.sin(i / 30.0)),
    ):
        hrs = [(float(i), hr_fn(i)) for i in range(0, 300, 10)]
        sps = [(float(i), sp_fn(i)) for i in range(0, 300, 10)]
        kind, diag = classify_hr_rise(hrs, sps)
        drift_cases.append({"case": name, "hr": hrs, "speed": sps, "expected_kind": kind,
                            "slope_bpm_min": diag.get("slope_bpm_min"),
                            "pace_cv": diag.get("pace_cv")})
    v["hr_rise"] = drift_cases

    # Signal-quality detectors, including the false-positive cases that matter most.
    sq = []
    def _hist(hr_fn, cad_fn, accel=None, n=60):
        return [HrSample(t_s=float(i), hr_bpm=hr_fn(i), cadence_spm=cad_fn(i),
                         accel_sd_g=(accel(i) if accel else None)) for i in range(n)]
    for name, hist in (
        ("cadence_lock_true", _hist(lambda i: 150.0 + 20.0 * math.sin(i / 10.0),
                                    lambda i: 150.0 + 20.0 * math.sin(i / 10.0))),
        ("cadence_lock_coincidence_constant_cadence",
         _hist(lambda i: 165.0 + (i % 3), lambda i: 168.0)),
        ("cadence_lock_false_independent_hr",
         _hist(lambda i: 158.0 + 6.0 * math.sin(i / 8.0), lambda i: 160.0 + (i % 3))),
        ("frozen_running", _hist(lambda i: 152.0, lambda i: 170.0)),
        ("frozen_resting", _hist(lambda i: 56.0, lambda i: 0.0)),
        ("not_worn", _hist(lambda i: 72.0, lambda i: 0.0, accel=lambda i: 0.001)),
        ("worn_still_person", _hist(lambda i: 60.0 + (i % 4), lambda i: 0.0,
                                    accel=lambda i: 0.001)),
    ):
        sq.append({
            "case": name,
            "samples": [{"t_s": s.t_s, "hr_bpm": s.hr_bpm, "cadence_spm": s.cadence_spm,
                         "accel_sd_g": s.accel_sd_g} for s in hist],
            "cadence_lock": cadence_lock_suspicion(hist),
            "frozen": frozen_hr_suspicion(hist),
            "not_worn": not_worn_suspicion(hist),
        })
    v["signal_quality"] = sq

    # A full controller trace: the anti-oscillation behaviour, as a sequence the Swift port must match.
    zones = five_zone_model(187, 55)
    ctrl = InRunController(zones=zones, intent=SessionIntent(kind="easy", target_zones=(1, 2)),
                           hr_speed_slope=12.0)
    ctrl.state = ctrl.state.__class__.STEADY
    trace = []
    hr, speed = 165.0, 3.2
    for t in range(1, 600):
        d = ctrl.update(RunTick(t_s=float(t), hr_bpm=hr, speed_m_s=speed))
        if d.cue:
            trace.append({"t_s": t, "cue_key": d.cue.key, "level": int(d.cue.level),
                          "hr_ss": round(d.hr_ss_estimate, 6) if d.hr_ss_estimate else None,
                          "correction": (round(d.speed_correction_m_s, 9)
                                         if d.speed_correction_m_s is not None else None)})
            if d.speed_correction_m_s:
                speed = max(1.5, speed + d.speed_correction_m_s)
        # 12 bpm per km/h, so the speed delta must be converted to km/h first. Getting this wrong
        # (using m/s directly) makes the simulated runner barely leave the zone and the trace
        # vacuous -- which is exactly what happened the first time.
        hr_target = 142.0 + (speed - 2.4) * 3.6 * 12.0
        hr += (hr_target - hr) / 45.0
    # Weekly-review decisions. Ported to Swift because they must run on device every Monday with no
    # server, so they need the same parity treatment as the controller. Each case is chosen to exercise
    # one branch of the precedence order, including the ones that only differ by which rule fires first.
    replan_cases = []
    for name, kwargs in (
        ("good_week", dict(planned_volume=33.0, achieved_volume=30.0,
                           sessions_planned=3, sessions_completed=3)),
        ("pain_holds", dict(planned_volume=33.0, achieved_volume=30.0,
                            sessions_planned=3, sessions_completed=3, max_pain=4)),
        ("two_bad_readiness_days", dict(planned_volume=33.0, achieved_volume=30.0,
                                        sessions_planned=3, sessions_completed=3,
                                        readiness_bands=["normal", "suppressed", "strained"])),
        ("disrupted_week", dict(planned_volume=40.0, achieved_volume=12.0,
                                sessions_planned=3, sessions_completed=1)),
        ("zero_volume_week", dict(planned_volume=40.0, achieved_volume=0.0,
                                  sessions_planned=3, sessions_completed=0)),
        ("cutback_due", dict(planned_volume=40.0, achieved_volume=40.0,
                             sessions_planned=3, sessions_completed=3, weeks_since_cutback=3)),
        ("pain_beats_cutback", dict(planned_volume=40.0, achieved_volume=40.0,
                                    sessions_planned=3, sessions_completed=3,
                                    weeks_since_cutback=3, max_pain=5)),
        ("advance_capped_off_achieved", dict(planned_volume=40.0, achieved_volume=20.0,
                                             sessions_planned=3, sessions_completed=3)),
    ):
        d = replan_week(**kwargs)
        replan_cases.append({"case": name,
                             "planned_volume": kwargs.get("planned_volume"),
                             "achieved_volume": kwargs["achieved_volume"],
                             "sessions_planned": kwargs["sessions_planned"],
                             "sessions_completed": kwargs["sessions_completed"],
                             "readiness_bands": kwargs.get("readiness_bands", []),
                             "max_pain": kwargs.get("max_pain", 0),
                             "weeks_since_cutback": kwargs.get("weeks_since_cutback", 0),
                             "expected_action": d.action,
                             "expected_next_volume": d.next_volume})

    # The ACWR-cut case separately, because it needs a load series rather than scalars.
    spike_series = [20.0] * 28 + [200.0] * 7
    spike = acwr(spike_series)
    spike_decision = replan_week(50.0, 50.0, 3, 3, acwr_result=spike)
    replan_cases.append({"case": "acwr_above_hard_cap",
                         "daily_loads": spike_series,
                         "planned_volume": 50.0, "achieved_volume": 50.0,
                         "sessions_planned": 3, "sessions_completed": 3,
                         "readiness_bands": [], "max_pain": 0, "weeks_since_cutback": 0,
                         "expected_ratio": round(spike.ratio, 9),
                         "expected_band": spike.band,
                         "expected_action": spike_decision.action,
                         "expected_next_volume": spike_decision.next_volume})
    v["replan"] = replan_cases

    # EWMA and the insufficient-history guard, which is what stops a beginner's exploding ratio from
    # vetoing their first four weeks of training.
    v["acwr"] = []
    for name, series in (("steady", [50.0] * 40),
                         ("spike", [30.0] * 30 + [120.0] * 7),
                         ("detraining", [80.0] * 30 + [10.0] * 7),
                         ("beginner_insufficient_history", [0.0] * 6 + [40.0]),
                         ("all_zero", [0.0] * 40)):
        r = acwr(series)
        v["acwr"].append({"case": name, "daily_loads": series,
                          "acute": round(r.acute, 9), "chronic": round(r.chronic, 9),
                          "ratio": round(r.ratio, 9), "band": r.band})

    # --- the tone channel ---------------------------------------------------------------------
    #
    # Traced rather than spot-checked because the interesting behaviour is *sequential*: the Schmitt
    # trigger, the two floors, and the ceiling-only suppression are all history-dependent, and a port
    # can agree on every individual decision while producing a different sequence.
    from marathon_engine.audio import PaceBandMonitor

    v["earcons"] = []
    for name, target, tol, ceiling, paces, grades in (
            ("even_pace_silent", 520.0, 0.06, False, [520.0] * 300, [0.0] * 300),
            ("too_fast_then_corrects", 520.0, 0.06, False,
             [520.0 * 0.85] * 120 + [520.0] * 180, [0.0] * 300),
            ("too_slow_lift", 520.0, 0.06, False, [520.0 * 1.20] * 300, [0.0] * 300),
            ("ceiling_only_ignores_slow", 520.0, 0.06, True, [520.0 * 1.35] * 300, [0.0] * 300),
            ("ceiling_only_still_eases", 520.0, 0.06, True, [520.0 * 0.80] * 300, [0.0] * 300),
            ("far_out_repeats", 520.0, 0.06, False, [520.0 * 0.70] * 600, [0.0] * 600),
            ("climb_moves_the_band", 520.0, 0.06, False,
             [520.0 * grade_adjusted_pace_factor(0.06)] * 300, [0.06] * 300),
            ("boundary_chatter", 520.0, 0.06, False,
             [520.0 * (1.062 if i % 2 else 1.058) for i in range(600)], [0.0] * 600),
    ):
        mon = PaceBandMonitor(target_pace_sec_km=target, tolerance=tol, ceiling_only=ceiling)
        events = []
        for i, (pace, grade) in enumerate(zip(paces, grades)):
            ev = mon.update(float(i), pace, grade=grade)
            if ev:
                events.append({"t_s": ev.t_s, "earcon": ev.earcon.value,
                               "error": round(ev.error, 6), "reason": ev.reason})
        v["earcons"].append({"case": name, "target_pace_sec_km": target, "tolerance": tol,
                             "ceiling_only": ceiling, "events": events,
                             "final_state": mon.state})

    v["controller_trace"] = {
        "description": ("Obedient runner with a first-order HR response. The Swift port must produce "
                        "the same cue sequence; a divergence means the lead compensation, deadband or "
                        "rate limiting differ."),
        "intent": {"kind": "easy", "target_zones": [1, 2]},
        "hr_speed_slope": 12.0,
        "zones": {"hr_max": 187, "hr_rest": 55},
        "initial": {"hr": 165.0, "speed_m_s": 3.2},
        "cues": trace,
        "final_hr_approx": round(hr, 3),
    }
    return v


def export_protocols() -> Dict[str, Any]:
    """Assessment and calibration protocols, plus the safety copy, as renderable data."""
    return {
        "export_version": EXPORT_VERSION,
        "ramp": ramp_protocol(30, 55),
        "calibration": calibration_protocol(30, 55),
        "red_flags": RED_FLAG_SYMPTOMS,
        "supplements": SUPPLEMENT_CHECKS,
        "hydration_long": hydration_plan(240, wbgt_c=18, body_mass_kg=80),
    }


def write_all(out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    vectors = export_golden_vectors()
    for name, payload in (("plan.json", export_plan()),
                          ("golden_vectors.json", vectors),
                          ("protocols.json", export_protocols())):
        path = out_dir / name
        path.write_text(json.dumps(payload, indent=1, sort_keys=False))
        written.append(path)

    # Also write the golden vectors into the Swift test target's own fixtures directory. SwiftPM
    # forbids a target's resources from living outside its own path, so the file genuinely has to
    # exist in two places -- and writing both from one command is what stops the test copy going
    # stale, which would make the parity suite pass against yesterday's engine.
    fixtures = out_dir.parent / "Tests" / "Fixtures"
    if fixtures.parent.exists():
        fixtures.mkdir(parents=True, exist_ok=True)
        for name in ("golden_vectors.json", "plan.json"):
            p = fixtures / name
            p.write_text((out_dir / name).read_text())
            written.append(p)
    return written


def main(argv: List[str]) -> int:
    out = Path(argv[0]) if argv else Path("../ios/MarathonCoach/Resources")
    for p in write_all(out):
        print(f"wrote {p} ({p.stat().st_size:,} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
