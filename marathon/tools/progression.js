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

/// How much slower than the athlete's own recent baseline the ceiling-to-floor recovery may be before
/// it reads as fatigue rather than noise. See `judgeHrSession`: this is the autonomic half of the gate
/// that `judgeSession` cannot do at all, because a clock session has no ceiling to recover from.
export const RECOVERY_SLOW_FRACTION = 1.25;

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

/// The share of the planned blocks that must have run their FULL length for an HR-governed session to
/// count as done. 6 of 7 passes and 2 of 3 does not, which is deliberate: on a short rung each block
/// is a third of the session, and one cut block is a bigger fraction of the evidence.
export const HR_DONE_FRACTION = 0.85;

/**
 * Judge one HR-governed session against what it asked for.
 *
 * A rung is `{blocks, blockS}` here: N run blocks, each up to `blockS` seconds -- the dose the tendon
 * and bone are being asked to take (see hr-blocks.js). The heart rate is the other rail: it can end a
 * block early, and when it does the block is "cut", which is the heart saying today's load was enough.
 * So the evidence for moving up is how many blocks the HEART let run their full length. Blocks cut by
 * the ceiling are neither a failure nor made up later; they are simply not evidence that the rung is
 * comfortable yet, and a rung that is not comfortable is repeated.
 *
 * `summary` is `HrBlocks.summary()`. `recoveryBaseline` is this athlete's own recent median
 * ceiling-to-floor time in seconds (see `recoveryBaseline()` below) or null.
 *
 * Aerobic decoupling is NOT read here, though the first version did. It compares heart rate to pace
 * between the halves of a session, and a run/walk governed to a fixed ceiling has neither a steady
 * pace nor a free heart rate -- on 6 October it read 12% across blocks, walks and a nine-minute
 * cool-down, and would have held the ladder on a number that described the session's shape.
 *
 * Returns `{verdict, reason, evidence, next}`, or null when the session is not evidence at all.
 */
export function judgeHrSession(target, summary, recoveryBaseline) {
  // A session that fell back to the clock is a timer expiring, not a body responding to load. It has
  // no ceiling crossings, no recovery measurements, nothing HR-governed at all -- moving the ladder
  // on it would be exactly the mistake governedBy exists to prevent for judgeSession's armband-dead
  // case, just arriving from the other direction.
  if (!summary || summary.governedBy !== 'hr') return null;

  const planned = target && target.blocks;
  if (!(planned > 0)) return null;

  const full = summary.blocksFull || 0;
  const started = summary.runBlocks || 0;
  const cut = summary.blocksCut || 0;
  const fraction = full / planned;
  const blockS = target.blockS || summary.runBlockTargetS || null;
  const evidence = {
    blocksPlanned: planned,
    blocksStarted: started,
    blocksFull: full,
    blocksCut: cut,
    blockS,
    completedFraction: fraction,
    runningOverCeilingS: Math.round(summary.runningOverCeilingS || 0),
    endedBy: summary.endedBy,
    toFloorMedianS: summary.toFloorMedianS,
    recoveryBaseline,
  };
  const of = `${full} of ${planned} blocks ran their full length`
           + (cut ? ` (${cut} cut short by the heart-rate ceiling)` : '');

  if (summary.endedBy === 'stall' && started < planned * ABANDONED_FRACTION) {
    return {
      verdict: EASE_BACK, evidence,
      next: 'Repeat this session one rung easier.',
      reason: `The body stopped clearing the load after ${started} of ${planned} blocks -- two walks `
            + `in a row that never came back down to the floor. The session that was actually `
            + `possible today is easier than the plan set.`,
    };
  }

  // Every block ends at the same ceiling, so the walk from it back down to the floor is the same
  // test every session. A quarter slower than his own recent median is fatigue accumulating, not
  // fitness improving -- the reading a coach takes from a rising resting heart rate, available every
  // session without a device this athlete does not have.
  const rec = summary.toFloorMedianS;
  if (recoveryBaseline != null && rec != null && rec > recoveryBaseline * RECOVERY_SLOW_FRACTION) {
    return {
      verdict: REPEAT, evidence,
      next: 'Repeat this session; do not add load until recovery comes back.',
      reason: `Heart rate took ${Math.round(rec)} s to come back down from the ceiling, against a recent `
            + `${Math.round(recoveryBaseline)} s -- more than a quarter slower. That is accumulated `
            + `fatigue, not today's fitness, and it is not something to build on top of.`,
    };
  }

  // A stall that nonetheless got most of the blocks in is not a reason to ask for more: the ADVANCE
  // branch says the session ended by the plan rather than the body giving out, and without this guard
  // two unrecovered walks late in the session would have advanced the rung on a session whose ending
  // was the body declining to go on.
  if (summary.endedBy === 'stall') {
    return {
      verdict: REPEAT, evidence,
      next: 'Repeat this rung. The body ended the running; let it get comfortable here first.',
      reason: `${of}, and then two walks in a row never came back down to the floor. Both are true; `
            + `the second decides.`,
    };
  }

  if (fraction >= HR_DONE_FRACTION) {
    return {
      verdict: ADVANCE, evidence,
      next: 'Move up a rung: longer run blocks, same total session time.',
      reason: `${of}. Done as prescribed, with recovery holding, so the `
            + `next one can ask for more.`,
    };
  }

  return {
    verdict: REPEAT, evidence,
    next: 'Repeat this same rung before moving up.',
    reason: `${of}. A block the heart rate cuts is the heart saying today was enough, not a miss -- `
          + `but it is not yet a rung that is comfortable, and that is what earns the next one.`,
  };
}

/**
 * The athlete's own recent recovery baseline: the median ceiling-to-floor time of his last five
 * HR-governed sessions, in seconds.
 *
 * Compared against, not trended -- `judgeHrSession` asks only "is today slower than what he has been
 * doing". Requires at least three sessions before answering anything: a baseline built from one or
 * two is a guess wearing a number, and a guess that can gate REPEAT vs ADVANCE is worse than none.
 */
export function recoveryBaseline(history) {
  const vals = (history || []).map(h => h && h.toFloorMedianS).filter(v => v != null);
  const recent = vals.slice(-5);
  if (recent.length < 3) return null;
  const sorted = recent.slice().sort((a, b) => a - b);
  return sorted.length % 2
    ? sorted[(sorted.length - 1) / 2]
    : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
}
