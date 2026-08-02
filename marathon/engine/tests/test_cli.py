"""Tests for the terminal front end.

These matter more than they would for a normal CLI. With no Mac there is no iPhone app, so this is
the only way the plan gets used — and the failure mode of a badly-behaved CLI here is not a stack
trace, it is a training week that quietly reads wrong.

Every test redirects ``STATE_DIR`` into a temporary directory, so running the suite can never touch a
real ``~/.marathon-coach``. A test that could eat your training history would be worse than no test.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from marathon_engine import cli


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path / "state")
    return tmp_path / "state"


def run(argv):
    return cli.main(argv)


# ------------------------------------------------------------------------------------------------
# init and the estimate labelling
# ------------------------------------------------------------------------------------------------


def test_init_writes_a_profile(isolated_state):
    assert run(["init", "--age", "30", "--hr-rest", "55"]) == 0
    data = json.loads((isolated_state / "profile.json").read_text())
    assert data["age"] == 30
    assert data["hr_max"] == pytest.approx(187.0, abs=0.5)     # Tanaka: 208 - 0.7*30


def test_an_estimated_profile_is_labelled_as_estimated(isolated_state):
    """Everything downstream keys off these labels, so they are load-bearing, not decoration."""
    run(["init", "--age", "30", "--hr-rest", "55"])
    data = json.loads((isolated_state / "profile.json").read_text())
    assert data["hr_max_source"] == "age_formula"
    assert data["vdot_source"] == "assumed_novice"
    assert data["prescription_basis"] == "hr_from_ramp"
    assert any("Tanaka" in c for c in data["caveats"])


def test_init_starts_the_plan_at_assess_not_at_training(isolated_state):
    """Week 1 is diagnostics. Starting anywhere else skips the measurement everything is built on."""
    run(["init", "--age", "30", "--hr-rest", "55"])
    assert json.loads((isolated_state / "state.json").read_text())["phase"] == "assess"


# ------------------------------------------------------------------------------------------------
# Refusing to guess
# ------------------------------------------------------------------------------------------------


def test_commands_needing_a_profile_exit_with_instructions(capsys):
    """A stack trace here would be a bad answer to a reasonable first command."""
    for cmd in (["week"], ["today"], ["status"]):
        with pytest.raises(SystemExit) as exc:
            run(cmd)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "No profile yet" in err
        assert "cli init" in err


def test_import_without_age_refuses_rather_than_assuming(tmp_path, capsys):
    p = tmp_path / "x.tcx"
    p.write_text("<TrainingCenterDatabase></TrainingCenterDatabase>")
    assert run(["import", str(p)]) == 2
    assert "--age" in capsys.readouterr().err


def test_a_corrupt_state_file_names_the_problem(isolated_state, capsys):
    run(["init", "--age", "30", "--hr-rest", "55"])
    (isolated_state / "state.json").write_text(json.dumps({"phase": "nonsense",
                                                           "week_in_phase": 1}))
    with pytest.raises(SystemExit) as exc:
        run(["week"])
    assert "nonsense" in str(exc.value)
    assert "assess" in str(exc.value), "the error should list what IS valid"


def test_phase_is_read_case_insensitively(isolated_state):
    """Tolerant of the file, strict about the meaning -- someone will hand-edit this."""
    run(["init", "--age", "30", "--hr-rest", "55"])
    (isolated_state / "state.json").write_text(json.dumps({"phase": "BASE_1", "week_in_phase": 2,
                                                           "week_index": 5}))
    assert run(["week"]) == 0


# ------------------------------------------------------------------------------------------------
# The plan
# ------------------------------------------------------------------------------------------------


def test_week_one_prescribes_no_hard_running(isolated_state, capsys):
    """The single most important property of week 1, and the easiest to regress."""
    run(["init", "--age", "30", "--hr-rest", "55"])
    run(["week"])
    out = capsys.readouterr().out
    assert "ASSESS" in out
    assert "ramp" in out.lower()
    assert "No hard running" in out


def test_week_respects_the_configured_run_days(isolated_state, capsys):
    """Wednesday, Saturday, Sunday. A plan on the wrong days is a plan that does not get run."""
    run(["init", "--age", "30", "--hr-rest", "55"])
    (isolated_state / "state.json").write_text(json.dumps({"phase": "base_1", "week_in_phase": 2,
                                                           "week_index": 6}))
    run(["week"])
    out = capsys.readouterr().out
    from marathon_engine import plan as planmod
    for day in planmod.PlanConfig().run_days:
        assert cli.DAY_NAMES[day] in out


# ------------------------------------------------------------------------------------------------
# Logging and review
# ------------------------------------------------------------------------------------------------


def test_log_appends_rather_than_replacing(isolated_state):
    run(["init", "--age", "30", "--hr-rest", "55"])
    run(["log", "--minutes", "30", "--km", "4"])
    run(["log", "--minutes", "35", "--km", "5"])
    sessions = json.loads((isolated_state / "sessions.json").read_text())
    assert len(sessions) == 2
    assert [s["km"] for s in sessions] == [4, 5]


def test_pain_at_or_above_the_warning_threshold_is_called_out(isolated_state, capsys):
    run(["init", "--age", "30", "--hr-rest", "55"])
    run(["log", "--minutes", "30", "--km", "4", "--pain", "4"])
    out = capsys.readouterr().out
    assert "holds volume" in out


def test_low_pain_is_recorded_without_a_lecture(isolated_state, capsys):
    run(["init", "--age", "30", "--hr-rest", "55"])
    run(["log", "--minutes", "30", "--km", "4", "--pain", "1"])
    assert "holds volume" not in capsys.readouterr().out


def test_review_does_not_ask_you_to_make_up_missed_volume(isolated_state, capsys):
    """The rule the whole plan is built on: missed volume is gone."""
    run(["init", "--age", "30", "--hr-rest", "55"])
    (isolated_state / "state.json").write_text(json.dumps({"phase": "base_1", "week_in_phase": 3,
                                                           "week_index": 8}))
    run(["log", "--minutes", "30", "--km", "4"])
    run(["review"])
    out = capsys.readouterr().out
    assert "Nothing is owed" in out or "missed volume is gone" in out


def test_review_advances_only_when_asked(isolated_state):
    run(["init", "--age", "30", "--hr-rest", "55"])
    run(["review"])
    assert json.loads((isolated_state / "state.json").read_text())["week_in_phase"] == 1
    run(["review", "--advance"])
    assert json.loads((isolated_state / "state.json").read_text())["week_in_phase"] == 2


def test_status_distinguishes_unmet_gates_from_unmeasured_ones(isolated_state, capsys):
    """Conflating them is how a plan starts lying about where you are."""
    run(["init", "--age", "30", "--hr-rest", "55"])
    run(["status"])
    out = capsys.readouterr().out
    assert "not yet measured" in out
    assert "NOT MET" not in out, "nothing has failed yet -- nothing has been measured"


def test_sessions_older_than_the_window_do_not_count_toward_recent_volume(isolated_state, capsys):
    run(["init", "--age", "30", "--hr-rest", "55"])
    old = (date.today() - timedelta(days=40)).isoformat()
    run(["log", "--minutes", "60", "--km", "12", "--date", old])
    run(["log", "--minutes", "30", "--km", "4"])
    run(["status"])
    out = capsys.readouterr().out
    assert "4.0 km" in out, "the 40-day-old 12 km run must not appear in a 14-day window"


# ------------------------------------------------------------------------------------------------
# Storage durability
# ------------------------------------------------------------------------------------------------


def test_writes_are_atomic(isolated_state):
    """A half-written sessions.json is worse than no sessions.json."""
    run(["init", "--age", "30", "--hr-rest", "55"])
    run(["log", "--minutes", "30", "--km", "4"])
    assert not list(isolated_state.glob("*.tmp")), "temporary file left behind"
    assert json.loads((isolated_state / "sessions.json").read_text())


def test_unreadable_state_warns_and_falls_back_rather_than_crashing(isolated_state, capsys):
    isolated_state.mkdir(parents=True, exist_ok=True)
    (isolated_state / "sessions.json").write_text("{ not json")
    assert cli._sessions() == []
    assert "could not read" in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------
# The Web Bluetooth logger's format
# ------------------------------------------------------------------------------------------------


def _logger_payload(n_stages=6):
    """Exactly what tools/verity-logger.html writes: per-second HR, speed from the stage label,
    accelerometer SD, and age/hr_rest carried in the file itself."""
    import math
    import random
    from datetime import datetime, timezone
    rng = random.Random(11)
    samples, hr, t = [], 62.0, 0
    plan = [(300, "warmup", None)]
    plan += [(240, f"stage_{i + 1}", k / 3.6)
             for i, k in enumerate([5, 6, 7, 8, 9, 10][:n_stages])]
    plan += [(1200, "steady", 7 / 3.6)]
    for dur, label, speed in plan:
        for _ in range(dur):
            v = speed if speed else 1.25
            hr += (55 + v * 3.6 * 12 - hr) * (1 - math.exp(-1 / 45))
            samples.append({"t_s": t, "hr_bpm": round(hr + rng.gauss(0, 1.4)),
                            "speed_m_s": round(speed, 4) if speed else None,
                            "accel_sd_g": round(0.30 + rng.gauss(0, 0.02), 4), "label": label})
            t += 1
    return {"schema_version": 1,
            "started_at": datetime(2026, 8, 5, 7, 0, tzinfo=timezone.utc).isoformat(),
            "age": 30, "hr_rest": 55, "samples": samples, "resting_ppi_ms": [],
            "surface": "treadmill", "strap_position": "upper_arm",
            "notes": "Recorded with the Web Bluetooth logger."}


def test_logger_json_imports_without_age_flags(tmp_path, capsys):
    """The file carries age and resting HR, so demanding them on the command line was a defect —
    the one input format that already knew the answer was the one that refused to run."""
    p = tmp_path / "verity-session.json"
    p.write_text(json.dumps(_logger_payload()))
    assert run(["import", str(p)]) == 0
    out = capsys.readouterr().out
    assert "PROFILE" in out


def test_logger_json_produces_a_usable_profile(tmp_path, capsys):
    """The whole point of the logger: a browser and an armband, and out comes a real profile."""
    p = tmp_path / "verity-session.json"
    p.write_text(json.dumps(_logger_payload()))
    run(["import", str(p), "--save"])
    out = capsys.readouterr().out
    assert "HR vs speed" in out
    # Generated with a 12 bpm per km/h slope; recovering it is the test.
    import re
    m = re.search(r"HR vs speed\s+([\d.]+) bpm per km/h", out)
    assert m, out
    assert 10.5 <= float(m.group(1)) <= 15.0


def test_logger_json_gets_full_sensor_health_not_partial(tmp_path, capsys):
    """The reason this format beats a TCX export: the accelerometer is present, so the not-worn and
    frozen-heart-rate detectors can actually run."""
    p = tmp_path / "verity-session.json"
    p.write_text(json.dumps(_logger_payload()))
    run(["import", str(p)])
    out = capsys.readouterr().out
    assert "PARTIAL" not in out
    assert "verdict: good" in out


def test_tcx_still_requires_age_and_says_why(tmp_path, capsys):
    p = tmp_path / "run.tcx"
    p.write_text("<TrainingCenterDatabase></TrainingCenterDatabase>")
    assert run(["import", str(p)]) == 2
    err = capsys.readouterr().err
    assert "--age" in err
    assert "neither format carries them" in err
