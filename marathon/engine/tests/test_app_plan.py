"""What the phone is allowed to run, and what it is told about what it cannot.

``app_plan`` is the boundary between the engine and the app: everything the phone knows about the
training plan comes through this one dictionary. It had no tests, and the gap showed up in use --
a scheduled RUNNING day reporting "Not a session the app can run", and a threshold session whose
band would have been applied to its own warm-up.

The rule these tests encode: a session's ``pace`` is a promise about which minutes it covers, and
the export has to make that promise checkable rather than leaving the app to guess from the title.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marathon_engine.app_plan import COACHABLE, build_app_plan  # noqa: E402
from marathon_engine.cli import _estimated_profile  # noqa: E402
from marathon_engine.plan import Phase  # noqa: E402

#: Session types whose prescribed pace applies from the first step to the last. The app keeps the
#: same list (WHOLE_RUN_TYPES in coach-template.html); this asserts the engine agrees with it.
WHOLE_RUN = {"easy", "long", "steady", "marathon_pace", "recovery"}

#: Days that are not runs at all. Everything else on the calendar is somewhere the athlete goes out
#: of the door, and the app owes it an answer better than a refusal.
NOT_A_RUN = {"rest", "strength", "cross_training", "mobility"}


@pytest.fixture(scope="module")
def plan():
    return build_app_plan(_estimated_profile(age=30.0, hr_rest=67.0),
                          start_phase=Phase.FOUNDATION)


def _sessions(plan):
    for phase in plan["phases"]:
        for week in phase["weeks"]:
            for s in week["sessions"]:
                yield s


def test_every_running_day_is_runnable(plan):
    """A day the plan tells you to run must not be a day the app refuses to run.

    ``strides`` failed this. It is an easy run -- same duration, same zones, same pace band -- with
    six twenty-second efforts inside it, and it was excluded from COACHABLE because of those
    efforts. The result was a scheduled running day whose card read "Not a session the app can run",
    which is false: almost all of it is exactly the easy running the band is for.
    """
    refused = sorted({s["type"] for s in _sessions(plan)
                      if s["type"] not in NOT_A_RUN
                      and not s.get("coachable") and not s.get("ramp")})
    assert refused == ["time_trial"], (
        f"these running days are refused by the app: {refused}. A time trial is the one honest "
        "refusal -- it is raced, not paced, and a band would be actively wrong.")


def test_a_banded_session_says_which_minutes_the_band_covers(plan):
    """Every coachable session is either whole-run, a run/walk, or carries its structure in prose.

    The third case is the one that bites. A threshold session's ``pace`` is threshold pace, held for
    two six-minute efforts inside forty-six minutes; the other thirty-four are warm-up, jog recovery
    and cool-down. Applied to the whole run it would tell an athlete jogging correctly to pick it up
    for half an hour. The app cannot time the parts, so the least it must be able to do is SAY which
    part -- and that needs ``structure`` present on every session of this kind.
    """
    for s in _sessions(plan):
        if not s.get("coachable") or s.get("run_walk") or s["type"] in WHOLE_RUN:
            continue
        assert s.get("structure"), (
            f"{s['type']} is coachable, is not a run/walk, and its band does not cover the whole "
            "run -- so it must carry the structure that says which part the band is for")
        assert s.get("pace"), f"{s['type']} is coachable but carries no band at all"


def test_run_walk_carries_the_pace_for_the_running_blocks(plan):
    """The block pace, not the session average.

    A run/walk session has two paces and they are far apart: 12:04/mi for the running blocks against
    a whole-session average around 13:53/mi that includes the walking. Coaching the average would
    ask for a pace that is run at no moment of the session.
    """
    seen = 0
    for s in _sessions(plan):
        rw = s.get("run_walk")
        if not rw:
            continue
        seen += 1
        assert rw.get("run_pace", {}).get("target_sec_km"), "run/walk must band the running blocks"
        assert rw["run_pace"]["target_sec_km"] < s["pace"]["target_sec_km"], (
            "the run-block pace must be faster than the session average, or one of them is the "
            "wrong number")
    assert seen, "the first phase is built of run/walk sessions; none were found"


def test_ceiling_only_matches_the_kind_of_session(plan):
    """Easy work is bounded above only; hard work is bounded both ways.

    Telling someone to speed up on a recovery run is the failure this guards. Strides is the
    interesting case and it is ceiling-only on purpose: with both edges enforced the coach calls
    "pick it up" through every walk-back recovery, which is most of the stride portion.
    """
    for s in _sessions(plan):
        if s["type"] in ("easy", "long", "run_walk", "recovery", "strides"):
            assert s["ceiling_only"], f"{s['type']} must never be told to speed up"
        elif s["type"] in ("threshold", "time_trial"):
            assert not s["ceiling_only"], f"{s['type']} is a workout; both edges apply"


def test_coachable_is_exactly_what_carries_a_band(plan):
    """No session may claim to be coachable without the number to coach against."""
    for s in _sessions(plan):
        if s.get("coachable"):
            assert s.get("pace") or s.get("run_walk"), (
                f"{s['type']} says the app can run it but gives it nothing to run against")
        assert (s["type"] in COACHABLE) == bool(s.get("coachable")), (
            f"{s['type']}: the coachable flag disagrees with COACHABLE")
