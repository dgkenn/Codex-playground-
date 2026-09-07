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
from marathon_engine import safety  # noqa: E402
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
    assert refused == ["race", "time_trial"], (
        f"these running days are refused by the app: {refused}. Both are honest refusals and for "
        "the same reason -- they are raced, not paced, and a band would be actively wrong. Note "
        "'race' appears here because of the 5K and 10K; the half marathon is scheduled as a PACED "
        "rehearsal, carries a real target, and IS coachable. Same type, opposite answers.")


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
        # Type alone stopped deciding this when races arrived: a 5K and a half marathon are both
        # "race", and only one of them has a number to run against. So the rule is now type AND a
        # band, and the flag must agree with exactly that.
        has_band = bool(s.get("pace") or s.get("run_walk"))
        assert (s["type"] in COACHABLE and has_band) == bool(s.get("coachable")), (
            f"{s['type']}: coachable={s.get('coachable')} but type-in-COACHABLE="
            f"{s['type'] in COACHABLE} and has_band={has_band}")


def test_the_bone_window_actually_clamps(plan):
    """A long run may not jump over the athlete's own recent longest while bone is still adapting.

    Every other governor in this engine is cardiovascular or autonomic -- TRIMP, ACWR, readiness,
    the heart-rate ceiling. Bone is in none of them, and it adapts months behind the fitness that
    lets you run further, so a new runner can pass every gate, feel excellent, and be well into a
    stress reaction. `safety.clamp_single_run` has existed and been tested since the beginning and
    had no production caller at all.
    """
    assert plan["bone_window"]["in_window"] is True, (
        "an athlete starting at week 0 of running is inside the window by definition")

    longest = None
    grew = False
    for s in _sessions(plan):
        km = s.get("km")
        if not km:
            continue
        if longest is not None:
            # No single run may exceed the growth rate the spike guard itself calls "ok".
            assert km <= longest * safety.BONE_LOAD_SPIKE_RATIO + 0.05, (
                f"a {km} km run follows a longest of {longest} km inside the bone window, "
                f"a {(km / longest - 1) * 100:.0f}% jump")
            if km > longest + 0.05:
                grew = True
        longest = max(longest or 0.0, km)

    # The tier that was missing entirely. The clamp used to apply only while the window was armed,
    # so the week it expired the plan caught up all at once: an 11.6 -> 17.1 km long run, a 47%
    # single-run jump, on week 21 of running. Nothing about week 21 makes that safe, and the RUNSAFE
    # cohort found risk rising continuously from the smallest progressions with no free threshold.
    # So the outer cap has no expiry -- this walks the WHOLE export, including the weeks past the
    # window, and the window's own effect is the tighter rate inside it.
    settled = build_app_plan(_estimated_profile(age=30.0, hr_rest=67.0),
                             start_phase=Phase.FOUNDATION,
                             weeks_running_at_start=safety.NEW_RUNNER_BONE_WINDOW_WEEKS + 4)
    prev = None
    for s in _sessions(settled):
        km = s.get("km")
        if not km:
            continue
        if prev is not None:
            assert km <= prev * safety.BONE_LOAD_SPIKE_RATIO + 0.05, (
                f"outside the bone window a {km} km run still follows a longest of {prev} km, "
                f"a {(km / prev - 1) * 100:.0f}% jump -- the cap must not expire with the window")
        prev = max(prev or 0.0, km)

    # And it must still PROGRESS. The first attempt at this used `clamp_single_run`, whose in-window
    # ratio is 1.00 -- correct as a runtime rule, and a deadlock in a generator: every week capped at
    # the previous week's figure froze the long run at 4.9 km for the whole eighteen-week export.
    # A safety limit that stops the plan working gets switched off, which protects nobody.
    assert grew, "the long run must still grow inside the window, just slowly"


def test_a_clamped_run_says_so(plan):
    """A run that was quietly shortened is indistinguishable from a plan that never asked for more.

    If the clamp fires it has to appear in the text the athlete actually reads, or the app is
    silently overriding the plan and the athlete has no way to know it happened -- which is how you
    lose trust in both.
    """
    held = [s for s in _sessions(plan) if "Held to" in (s.get("structure") or "")]
    assert held, (
        "this plan's own long-run progression exceeds 10% a week and jumps 44% at the BASE_1 to "
        "BASE_2 boundary, so the limit must actually be firing somewhere in this export -- if it "
        "never fires, nothing here is being tested")
    for s in held:
        # It must say WHY, not necessarily "bone". The clamp now has two tiers and only the inner one
        # is about bone -- a run held outside the window is held because a single run should not jump
        # far past your recent longest at any stage, which is a different true sentence.
        why = s["structure"].lower()
        assert "bone" in why or "recent longest" in why, (
            f"{s['type']} was shortened without saying why: {s['structure']!r}")


def test_a_settled_runner_is_not_clamped_like_a_beginner(plan):
    """The window lifts. A clamp that never releases is a plan that never progresses."""
    settled = build_app_plan(_estimated_profile(age=30.0, hr_rest=67.0),
                             start_phase=Phase.FOUNDATION,
                             weeks_running_at_start=safety.NEW_RUNNER_BONE_WINDOW_WEEKS + 4)
    assert settled["bone_window"]["in_window"] is False
    longest_new = max((s.get("km") or 0) for s in _sessions(plan))
    longest_settled = max((s.get("km") or 0) for s in _sessions(settled))
    assert longest_settled >= longest_new, (
        f"an established runner must be allowed at least as far as a novice: "
        f"{longest_settled} vs {longest_new}")


def test_a_raced_race_carries_no_band_and_a_paced_one_does(plan):
    """The distinction that made `coachable` stop being a property of the session type.

    The 5K and 10K are raced flat out -- prescribing a target pace for something you are racing
    defeats the point of racing it -- while the half marathon is scheduled as a paced REHEARSAL of
    marathon day, at a controlled effort, and carries a real target. Both are SessionType.RACE.
    """
    import marathon_engine.plan as pm
    from marathon_engine.app_plan import _session_dict
    profile = _estimated_profile(age=30.0, hr_rest=67.0)

    seen = {}
    for phase in (Phase.BASE_2, Phase.HALF_BUILD):
        for wk in range(1, safety.NEW_RUNNER_BONE_WINDOW_WEEKS):
            try:
                w = pm.generate_week(profile, phase, wk, week_index=wk)
            except Exception:
                break
            for s in w.sessions:
                if s.type == pm.SessionType.RACE:
                    seen[s.title] = _session_dict(s, profile.paces, profile)

    assert "5K" in seen and "Half marathon" in seen, (
        f"both a raced and a paced race must be schedulable: {sorted(seen)}")
    assert not seen["5K"].get("pace"), "a 5K is raced; a prescribed pace would contradict that"
    assert seen["5K"]["coachable"] is False, "and with no band the app must not claim to run it"
    assert seen["Half marathon"].get("pace"), (
        "the half is a paced rehearsal and must carry the target that makes it one")
    assert seen["Half marathon"]["coachable"] is True, "and the app can run that"
