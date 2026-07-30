"""Export tests: the plan resource and the golden-vector contract with the Swift port.

These matter more than they look. `PortParityTests.swift` asserts the Swift implementation agrees with
whatever is in `golden_vectors.json` -- so if the vectors themselves were empty, trivial, or did not
cover the cases where the two implementations could plausibly diverge, the parity suite would pass
while proving nothing. These tests check that the contract has teeth.
"""

from __future__ import annotations

import json

import pytest

from marathon_engine.export import (
    EXPORT_VERSION, export_golden_vectors, export_plan, export_protocols, write_all,
)
from marathon_engine.plan import PHASE_MIN_WEEKS, PHASE_ORDER, Phase


# ---- plan resource --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def plan():
    return export_plan()


def test_plan_is_serialisable_and_versioned(plan):
    json.dumps(plan)
    assert plan["export_version"] == EXPORT_VERSION


def test_every_phase_is_exported(plan):
    assert [p["phase"] for p in plan["phases"]] == [ph.value for ph in PHASE_ORDER]


def test_every_phase_has_more_weeks_than_its_minimum(plan):
    """A gated plan can sit in a phase well past its minimum -- that is the whole point of gating. If
    the export stopped at the minimum, the app would fall off the end of the templates."""
    for p in plan["phases"]:
        n = PHASE_MIN_WEEKS.get(Phase(p["phase"]), 1)
        assert len(p["weeks"]) > n, f"{p['phase']} exports only {len(p['weeks'])} weeks for min {n}"


def test_exported_weeks_cover_all_seven_days(plan):
    for p in plan["phases"]:
        for w in p["weeks"]:
            offsets = {s["day_offset"] for s in w["sessions"]}
            assert set(range(7)).issubset(offsets), \
                f"{p['phase']} week {w['week_in_phase']} leaves a day unaccounted for"


def test_exported_sessions_all_state_their_intent(plan):
    for p in plan["phases"]:
        for w in p["weeks"]:
            for s in w["sessions"]:
                assert s["intent"], f"{p['phase']}/{s['title']} has no intent"


def test_gates_are_exported_with_rationales(plan):
    for p in plan["phases"]:
        for g in p["gates"]:
            assert g["label"] and g["rationale"]


def test_safety_gates_survive_the_export(plan):
    """The pain gate is a safety gate, and a safety gate that loses its flag in serialisation is a
    safety gate the app will let you waive."""
    for p in plan["phases"]:
        keys = {g["key"] for g in p["gates"]}
        if "max_pain_2wk" in keys:
            pain = next(g for g in p["gates"] if g["key"] == "max_pain_2wk")
            assert pain["safety"] is True


def test_run_days_reflect_the_configured_schedule(plan):
    assert plan["config"]["run_days"] == [2, 5, 6]      # Wed, Sat, Sun


def test_ir_floor_is_exported(plan):
    assert plan["vdot_ir_floor"] == 35.0


# ---- golden vectors -------------------------------------------------------------------------

@pytest.fixture(scope="module")
def vectors():
    return export_golden_vectors()


def test_vectors_serialisable(vectors):
    json.dumps(vectors)


def test_vectors_cover_every_shared_surface(vectors):
    """Each key here corresponds to logic that exists in BOTH Python and Swift. A missing key means an
    unverified port."""
    for key in ("zones", "grade_factors", "paces", "steady_state_hr", "speed_correction",
                "hr_rise", "signal_quality", "controller_trace"):
        assert key in vectors and vectors[key], f"{key} vectors missing or empty"


def test_zone_vectors_include_a_pinned_lthr_case(vectors):
    """LTHR pinning is the zone logic most likely to be ported wrong, because it mutates two zones."""
    assert any(c["lthr"] for c in vectors["zones"])


def test_grade_vectors_include_the_clamped_extremes(vectors):
    grades = [c["grade"] for c in vectors["grade_factors"]]
    assert max(grades) > 0.45 and min(grades) < -0.45, \
        "the clamp boundaries must be exercised or a port could extrapolate silently"


def test_grade_vectors_capture_the_downhill_minimum(vectors):
    """Minetti's actual finding: the cheapest gradient is downhill, not flat."""
    best = min(vectors["grade_factors"], key=lambda c: c["cost"])
    assert -0.25 <= best["grade"] <= -0.05


def test_pace_vectors_straddle_the_ir_floor(vectors):
    flags = {c["vdot"]: c["ir_prescribable"] for c in vectors["paces"]}
    assert any(not v for v in flags.values()) and any(flags.values()), \
        "both sides of the interval-prescribability floor must appear"
    assert flags[34] is False and flags[35] is True


def test_hr_rise_vectors_include_drift_and_effort_and_the_confuser(vectors):
    kinds = {c["case"]: c["expected_kind"] for c in vectors["hr_rise"]}
    assert kinds["drift"] == "drift"
    assert kinds["effort_increase"] == "effort_increase"
    # Same HR slope as the drift case but with pace moving -- the case that separates the two.
    assert kinds["pace_varying"] == "effort_increase"


def test_signal_quality_vectors_include_the_false_positives(vectors):
    """The easy cases prove little. The vectors must pin the cases where a naive detector goes wrong."""
    cases = {c["case"]: c for c in vectors["signal_quality"]}
    for name in ("cadence_lock_true", "cadence_lock_false_independent_hr",
                 "cadence_lock_coincidence_constant_cadence", "frozen_running", "frozen_resting",
                 "not_worn", "worn_still_person"):
        assert name in cases, f"{name} vector missing"

    assert cases["cadence_lock_true"]["cadence_lock"] >= 0.8
    assert cases["cadence_lock_false_independent_hr"]["cadence_lock"] < 0.8
    assert cases["cadence_lock_coincidence_constant_cadence"]["cadence_lock"] < 0.8
    assert cases["frozen_running"]["frozen"] >= 0.8
    assert cases["frozen_resting"]["frozen"] < 0.8
    assert cases["not_worn"]["not_worn"] >= 0.7
    assert cases["worn_still_person"]["not_worn"] == 0.0


def test_controller_trace_actually_exercises_the_controller(vectors):
    """The trace is the strongest parity check there is -- and it is worthless if the simulated runner
    never leaves the target zone. An earlier version used m/s where km/h was needed, which made the
    plant respond so weakly that zero cues fired and the test passed vacuously."""
    t = vectors["controller_trace"]
    assert len(t["cues"]) >= 1, "the trace must contain at least one cue or it proves nothing"
    assert t["cues"][0]["cue_key"] == "slow_down"
    assert t["cues"][0]["correction"] < 0, "a too-hot runner must be told to slow down"


def test_controller_trace_converges_into_the_zone(vectors):
    """And it must converge, not oscillate: a trace with a cue every 75 seconds would mean the lead
    compensation is not working."""
    t = vectors["controller_trace"]
    assert len(t["cues"]) <= 8, f"{len(t['cues'])} cues suggests oscillation"
    # Z2 for hr_max 187 / hr_rest 55 tops out at 151.
    assert t["final_hr_approx"] <= 155, f"converged to {t['final_hr_approx']}, outside the zone"
    assert t["final_hr_approx"] >= 130, "over-corrected below the zone"


def test_controller_trace_records_the_slope_it_used(vectors):
    """Without the slope, the Swift side cannot reproduce the run."""
    assert vectors["controller_trace"]["hr_speed_slope"] == 12.0


# ---- protocols ------------------------------------------------------------------------------

def test_protocols_export_is_complete():
    p = export_protocols()
    json.dumps(p)
    for key in ("ramp", "calibration", "red_flags", "supplements", "hydration_long"):
        assert key in p and p[key]


def test_calibration_protocol_keeps_ppi_out_of_the_moving_part():
    p = export_protocols()["calibration"]
    setup = " ".join(p["device_setup"]).lower()
    assert "do not enable ppi" in setup


def test_red_flags_survive_export():
    flags = export_protocols()["red_flags"]
    for key in ("chest_pain", "focal_bone_pain", "calf_swelling", "confusion"):
        assert key in flags


# ---- writing --------------------------------------------------------------------------------

def test_write_all_produces_the_expected_files(tmp_path):
    out = tmp_path / "Resources"
    written = write_all(out)
    names = {p.name for p in written}
    assert {"plan.json", "golden_vectors.json", "protocols.json"} <= names
    for p in written:
        assert p.stat().st_size > 0
        json.loads(p.read_text())


def test_write_all_mirrors_vectors_into_the_swift_fixtures(tmp_path):
    """SwiftPM forbids a target's resources from living outside its own directory, so the vectors
    genuinely exist twice. Writing both from one command is what stops the test copy going stale --
    which would make the parity suite pass against a previous version of the engine."""
    root = tmp_path / "MarathonCoach"
    (root / "Tests").mkdir(parents=True)
    written = write_all(root / "Resources")
    fixture = root / "Tests" / "Fixtures" / "golden_vectors.json"
    assert fixture in written
    assert json.loads(fixture.read_text()) == json.loads(
        (root / "Resources" / "golden_vectors.json").read_text())


def test_write_all_skips_the_fixture_when_there_is_no_test_target(tmp_path):
    """Exporting into an arbitrary directory should not invent a Tests folder."""
    out = tmp_path / "somewhere" / "Resources"
    written = write_all(out)
    assert not any("Fixtures" in str(p) for p in written)
