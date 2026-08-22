// Whether the next session should be harder, the same, or easier — decided from the recording.
//
// Why this exists
// ---------------
// "Make sure I'm progressing so I'm being pushed, but not in a too aggressive way."
//
// The plan advances the run-walk ladder one rung per calendar week: 1 min, then 2, then 3, then 5,
// then 8. That is a reasonable schedule and it is not a controller — it takes no account of what
// happened. Two ways it goes wrong, and both are on the record already:
//
//   Too fast. The 22 August session prescribed seven two-minute blocks, fourteen minutes of running.
//   What the trace shows is 2.6 minutes above the gait transition, with a longest block of 37
//   seconds. The next Wednesday the schedule would have asked for three-minute blocks. Prescribing
//   three minutes to someone who has just failed to hold two is how a plan produces an injury and a
//   quit, and neither of those shows up until it is too late to undo.
//
//   Too slow. He held 4.7 minutes continuously on 5 August. A ladder that starts at one-minute
//   repeats for such a person is not caution — it is a month of sessions that never load the tissue
//   they exist to load, and it teaches that the plan does not know what he can do.
//
// So the ladder is a plan and this is the check on it: the recording of the session just finished
// against what that session asked for.
//
// Deliberately not a fitness model
// --------------------------------
// It reads four things and only four: did the running actually happen, was the longest block the
// one that was asked for, was it aerobic, and did it drift. No trend fitting, no fatigue model, no
// readiness score. Every one of those needs weeks of data that do not exist yet, and a number
// invented from two sessions is worse than no number because it will be believed.

/// Fraction of the prescribed running that has to have happened for the session to count as done.
/// Ninety per cent rather than a hundred: a traffic light, a dropped fix and a slow start are not
/// failures, and a gate that only opens on perfection never opens.
export const DONE_FRACTION = 0.9;

/// Below this the session was not the session. Not a near miss — a different, easier workout.
export const ABANDONED_FRACTION = 0.6;

/// Fraction of the running that has to have been at or below the easy ceiling to advance.
///
/// The whole point of this phase is aerobic volume. Completing the intervals by running them hard
/// builds the wrong thing and earns the next rung on false evidence, which is precisely how a
/// beginner ends up hurt while doing everything the plan said.
export const AEROBIC_FRACTION = 0.8;
export const AEROBIC_FLOOR = 0.6;

/// Aerobic decoupling above this says the duration is already at the edge of what the aerobic base
/// supports, whatever the intervals looked like. Standard practice treats 5% as good and 10% as the
/// line; this uses the line rather than the ideal because a beginner's early sessions are noisy.
export const DECOUPLING_LIMIT_PCT = 10;

export const ADVANCE = 'advance';
export const REPEAT = 'repeat';
export const EASE_BACK = 'ease_back';

/**
 * Judge one session against what it asked for.
 *
 * `prescribed` is `{runMin, walkMin, reps}` — the run/walk the plan set. `stats` is what
 * `runStats` produced from the recording. Returns `{verdict, reason, evidence, next}` or null when
 * there is not enough of either to say anything, which is a real answer and better than a guess.
 *
 * The order of the rules is the design. Abandonment is checked before intensity, because a session
 * that did not happen tells you nothing about whether it was aerobic; and intensity is checked
 * before completion, because completing the intervals by running them too hard is a reason not to
 * advance rather than a reason to.
 */
export function judgeSession(prescribed, stats) {
  if (!prescribed || !stats) return null;
  const { runMin, walkMin = 0, reps } = prescribed;
  if (!(runMin > 0) || !(reps > 0)) return null;

  const wantBlockS = runMin * 60;
  const wantRunningS = wantBlockS * reps;
  const gotRunningS = stats.runningS || 0;
  const gotBlockS = stats.longestRunBlockS || 0;
  // `pctAtOrBelowEasy` is null without the armband, and null is not zero: a session with no heart
  // rate has not failed the aerobic test, it simply was not sat. Treating absence as failure would
  // freeze the ladder for anyone whose strap died.
  const aerobic = stats.pctAtOrBelowEasy == null ? null : stats.pctAtOrBelowEasy / 100;
  const drift = stats.decouplingPct;

  const evidence = {
    runningS: Math.round(gotRunningS),
    prescribedRunningS: Math.round(wantRunningS),
    completedFraction: wantRunningS > 0 ? gotRunningS / wantRunningS : null,
    longestBlockS: Math.round(gotBlockS),
    prescribedBlockS: Math.round(wantBlockS),
    aerobicFraction: aerobic,
    decouplingPct: drift,
  };
  const mins = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

  if (gotRunningS < wantRunningS * ABANDONED_FRACTION) {
    return {
      verdict: EASE_BACK, evidence,
      next: 'Repeat this session one rung easier — shorter run blocks, same total time.',
      reason: `${mins(gotRunningS)} of running against ${mins(wantRunningS)} asked for. `
            + `The session that was actually done is an easier one than the plan set, so the plan `
            + `should say so rather than build on top of it.`,
    };
  }

  if (aerobic != null && aerobic < AEROBIC_FLOOR) {
    return {
      verdict: EASE_BACK, evidence,
      next: 'Repeat one rung easier, and run the blocks slower rather than shorter.',
      reason: `Only ${Math.round(aerobic * 100)}% of the running was at or below the easy ceiling. `
            + `The intervals were completed by running them hard, which builds something else and `
            + `earns the next rung on evidence that is not about aerobic fitness.`,
    };
  }

  const complete = gotRunningS >= wantRunningS * DONE_FRACTION
                && gotBlockS >= wantBlockS * DONE_FRACTION;
  if (!complete) {
    return {
      verdict: REPEAT, evidence,
      next: 'Repeat this same session before moving up.',
      reason: gotBlockS < wantBlockS * DONE_FRACTION
        ? `Longest continuous block ${mins(gotBlockS)} against ${mins(wantBlockS)} asked for. `
          + `The block length is the thing this phase is training; repeating it is not lost time.`
        : `${mins(gotRunningS)} of running against ${mins(wantRunningS)}. Close, and close is a `
          + `reason to do it again rather than to add to it.`,
    };
  }

  if (aerobic != null && aerobic < AEROBIC_FRACTION) {
    return {
      verdict: REPEAT, evidence,
      next: 'Repeat, and take the run blocks slower.',
      reason: `The intervals were completed, but ${Math.round((1 - aerobic) * 100)}% of the running `
            + `was above the easy ceiling. Hold the pace down and this rung becomes easy, which is `
            + `what earns the next one.`,
    };
  }

  if (drift != null && drift > DECOUPLING_LIMIT_PCT) {
    return {
      verdict: REPEAT, evidence,
      next: 'Repeat at this duration before adding to it.',
      reason: `Heart rate drifted ${drift.toFixed(0)}% against pace between the halves. The `
            + `intervals were fine; the duration is at the edge of what the aerobic base currently `
            + `supports, and that is the part to let catch up.`,
    };
  }

  return {
    verdict: ADVANCE, evidence,
    next: 'Move up a rung: longer run blocks, same total session time.',
    reason: `${mins(gotRunningS)} of running, longest block ${mins(gotBlockS)}`
          + (aerobic != null ? `, ${Math.round(aerobic * 100)}% of it aerobic` : '')
          + `. Done as prescribed, so the next one can ask for more.`,
  };
}

/**
 * Where a verdict puts you on the ladder, given where you are.
 *
 * Separate from the judging so that the rule "never advance more than one rung, never fall below the
 * bottom" lives in one place. Advancing two rungs because a session went unusually well is exactly
 * the aggression this whole module exists to prevent.
 */
export function nextRung(current, verdict, ladderLength) {
  const i = Math.max(0, Math.min(current | 0, ladderLength - 1));
  if (verdict === ADVANCE) return Math.min(i + 1, ladderLength - 1);
  if (verdict === EASE_BACK) return Math.max(i - 1, 0);
  return i;
}
