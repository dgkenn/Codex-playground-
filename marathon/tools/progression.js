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
/// ...or the rung's running done in total: this share of the planned running time, the blocks the
/// ceiling cut made up in the extra blocks the controller adds for exactly that (hr-blocks.js).
export const HR_DOSE_FRACTION = 0.95;

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
  // Blocks the TERRAIN decided are set aside, not scored: cut by the ceiling on a climb, or ended at
  // the top of a steep descent. A hilly route should neither hold the rung (every climb cut short) nor
  // be a reason to avoid the hills; it simply tests fewer blocks.
  const terrain = (summary.blocksHill || 0) + (summary.blocksSteepDown || 0);
  const tested = Math.max(0, planned - terrain);
  const fraction = tested > 0 ? full / tested : 0;
  const blockS = target.blockS || summary.runBlockTargetS || null;
  const evidence = {
    blocksPlanned: planned,
    blocksStarted: started,
    blocksFull: full,
    blocksCut: cut,
    blocksTerrain: terrain,
    blocksTested: tested,
    blockS,
    completedFraction: fraction,
    runningOverCeilingS: Math.round(summary.runningOverCeilingS || 0),
    endedBy: summary.endedBy,
    toFloorMedianS: summary.toFloorMedianS,
    recoveryBaseline,
  };
  const of = `${full} of ${tested} blocks ran their full length`
           + (cut - (summary.blocksHill || 0) > 0
              ? ` (${cut - (summary.blocksHill || 0)} cut short by the heart-rate ceiling)` : '')
           + (terrain ? `; ${terrain} on hills set aside` : '');

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

  // Mostly terrain: not a test of the rung either way. Keep it, and say where to test it.
  if (tested < planned / 2) {
    return {
      verdict: REPEAT, evidence,
      next: 'Repeat this rung, on flatter ground if you want it to count.',
      reason: `${terrain} of ${planned} blocks were decided by hills rather than by you, so this `
            + `session cannot say whether the rung is comfortable. The hills were good training; `
            + `they are just not a test of the rung.`,
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

  // The rung is a dose for bone and tendon -- this much running, in blocks no longer than this --
  // and the heart-rate ceiling is the intensity governor inside it. When the ceiling cut blocks and
  // the extra blocks made the running up, the dose the tissue was asked for was delivered, in pieces
  // no longer than the rung allows. Holding the rung on that was holding the TISSUE progression on a
  // CARDIAC signal: 22 and 24 October both repeated 7 x 2 min, with the athlete reporting both too
  // easy. The next rung is self-limiting in the same way -- longer blocks the ceiling will cut, and at
  // most three extra blocks to make them up -- so it is only reached when the running really fits.
  const dose = summary.runningTargetS > 0 ? (summary.runningS || 0) / summary.runningTargetS : 0;
  evidence.doseFraction = dose;
  if (dose >= HR_DOSE_FRACTION) {
    const mins = s => `${Math.round(s / 60)} min`;
    return {
      verdict: ADVANCE, evidence,
      next: 'Move up a rung: longer run blocks, same total session time.',
      reason: `${of}, and the extra blocks made up the rest: ${mins(summary.runningS)} of the `
            + `${mins(summary.runningTargetS)} of running done, with recovery holding.`,
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

/**
 * The talk test, as a correction to the heart-rate ceiling.
 *
 * The ceiling is meant to sit at the first ventilatory threshold, and the talk test is the field
 * marker for exactly that point: below it you can speak in full sentences, at it speech starts to
 * break up. Everything else the ceiling is built from is indirect -- 80% of an age-predicted maximum
 * (good to about +/-10 bpm), and an efficiency roll-off read off one early session. (The maximum
 * itself looks about right: 9 and 13 October both topped out at 178, the second at the end of an
 * eleven-minute run to his limit, which puts his true maximum around 180-188.) His own answer to
 * "could you talk at the moment the ceiling called the walk" is the direct measurement, so it moves
 * the ceiling:
 *
 *   'easy' -> +3 bpm      'just' -> 0      'hard' -> -5 bpm
 *
 * Asymmetric on purpose: being over the threshold costs more than being a few beats under it. Small
 * steps, because each answer is one person's impression at one moment, and the next session tests
 * the new number. Bounded to +/-10 of where the ceiling started; the caller also caps the result at
 * 80% of heart-rate reserve, the most this phase ever asks for.
 *
 * `answers` is `[{answer, at}]`, oldest first. Returns the offset in bpm.
 */
export const TALK_STEP_BPM = { easy: 3, just: 0, hard: -5 };
export const TALK_LIMIT_BPM = 10;

export function talkTestOffset(answers) {
  let off = 0;
  for (const a of answers || []) {
    const step = a && TALK_STEP_BPM[a.answer];
    if (step == null) continue;
    off = Math.max(-TALK_LIMIT_BPM, Math.min(TALK_LIMIT_BPM, off + step));
  }
  return off;
}

/**
 * Whether a session tested the ceiling at all, and so whether to ask. Only when heart rate actually
 * ended at least two blocks: if every block ran its full length (9 October, one-minute blocks), the
 * walk was called by the clock, and "could you talk then" is a question about a different heart rate.
 */
export function talkTestApplies(summary) {
  return !!summary && summary.governedBy === 'hr'
    && ((summary.blocksCut || 0) - (summary.blocksHill || 0)) >= 2;
}

/// How many sessions in a row must earn ADVANCE on a rung before it moves up.
export const QUALIFYING_TO_ADVANCE = 2;
/// And the least time between two steps up, in days.
export const MIN_DAYS_BETWEEN_STEPS = 6;

/**
 * How fast the ladder may move, set by the body's own signals.
 *
 * The fixed rule above (two good runs, six days) is the steady track, and it stays the default. The
 * athlete asked for the fastest safe route to a continuous 5K "as long as it adapts to my
 * biofeedback", and the evidence says where the speed can come from: in 5,200 runners followed for
 * 18 months, injury risk rose with single SESSIONS longer than ~10% beyond the longest of the last
 * 30 days, and weekly load changes were not associated with it (Frandsen et al., Br J Sports Med
 * 2025). Most steps on this ladder do not lengthen the session at all -- 4 x 5 -> 5 x 4, 6 x 4 ->
 * 8 x 3, 10 x 3 -> 15 x 2 -> 30 x 1 keep the running time and only remove walk breaks, which costs
 * the heart, not the tissue. So:
 *
 *   green  -- everything says go: one good run moves a step; a step that keeps the running time can
 *             come two days after the last, one that adds running three days after, at most two of
 *             those a week, and never more than 30% over the longest session of the last 30 days.
 *   amber  -- one signal says wait (HRV below the band, a "hard" talk test, a niggle logged this
 *             week): the steady track.
 *   red    -- a pain pattern, or HRV well below for days, or illness: no step up at all.
 *
 * The ease-back side is untouched: a session that goes wrong steps back the same day on any track.
 */
export const TRACKS = {
  green: { label: 'fast track', qualifying: 1, minDays: 2, loadMinDays: 3, loadStepsPerWeek: 2 },
  amber: { label: 'steady track', qualifying: QUALIFYING_TO_ADVANCE, minDays: MIN_DAYS_BETWEEN_STEPS,
           loadMinDays: MIN_DAYS_BETWEEN_STEPS, loadStepsPerWeek: 1 },
  red: { label: 'holding', qualifying: Infinity, minDays: Infinity, loadMinDays: Infinity, loadStepsPerWeek: 0 },
};
/// A step that adds running may not take a session past this multiple of the longest session of the
/// last 30 days. Frandsen's lowest-risk band was +10%; 30% is the top of the band above it, and the
/// aggressive end the athlete chose -- the ladder's own steps are built to fit inside it.
export const SPIKE_MAX = 1.3;

/// A session clears the ceiling by this much, inside every block, for the next step to be skipped.
export const SKIP_MARGIN_BPM = 10;
/// At most one skipped step in this many days.
export const SKIP_EVERY_DAYS = 7;

/**
 * Whether a heart-rate-governed session had room to spare: every planned block ran its full length,
 * none was cut, and heart rate inside the blocks stayed SKIP_MARGIN_BPM under the ceiling. Asked for
 * on 28 October ("you can skip a step"), after 7 x 2 min ran full with heart rate 142-162. The
 * margin is on the in-block peak, which the armband reports late, so it is a real margin.
 */
export function hasHeadroom(summary) {
  if (!summary || summary.governedBy !== 'hr' || !(summary.ceilingBpm > 0)) return false;
  if (!(summary.blocksPlanned > 0) || summary.blocksFull < summary.blocksPlanned || summary.blocksCut > 0) return false;
  return summary.peakRunHr != null && summary.peakRunHr <= summary.ceilingBpm - SKIP_MARGIN_BPM;
}

/**
 * The light for the next step, from the signals the app has. All inputs optional; with none of them
 * the light is green (no evidence against). Returns `{light, why: [..]}`.
 *
 *   readiness  -- readiness.js band: 'strained' is red, 'suppressed' is amber
 *   painHold   -- load-watch.js painHolds() result: a hold is red
 *   painRecent -- a niggle logged in the last 7 days that is not (yet) a pattern: amber
 *   lastTalk   -- the most recent talk-test answer within a week: 'hard' is amber
 */
export function trafficLight({ readiness = null, painHold = null, painRecent = false, lastTalk = null } = {}) {
  const red = [], amber = [];
  if (painHold && painHold.hold) red.push(`the ${String(painHold.site || 'niggle').replace(/_/g, ' ')} is a pattern`);
  if (readiness === 'strained') red.push('morning readiness says rest');
  if (readiness === 'suppressed') amber.push('morning HRV is below your band');
  if (painRecent) amber.push('a niggle logged this week');
  if (lastTalk === 'hard') amber.push('the last talk test was hard');
  if (red.length) return { light: 'red', why: red };
  if (amber.length) return { light: 'amber', why: amber };
  return { light: 'green', why: [] };
}

/**
 * Move along the ladder, at the pace tissue adapts rather than the pace the heart does.
 *
 * `nextRung` alone advanced on any single ADVANCE, and three sessions a week meant three rungs a week
 * were possible: 8 minutes of running to 18 in five days. The heart adapts in weeks; bone and tendon
 * remodel over months, show nothing in any heart-rate measure, and are what ends a beginner's first
 * year. So a step up needs TWO qualifying sessions in a row on the current rung AND at least six
 * days since the last step up -- at three runs a week, one rung a week when everything goes right,
 * which is the couch-to-5K cadence and puts thirty continuous minutes about two months out. A REPEAT
 * resets the count (the two must be consecutive). An EASE_BACK is immediate: protection does not wait.
 * A pain pattern holds the step up (the caller passes `painHold`).
 *
 * `state` is `{rung, qualifying, changedAt}` or null; `now` is a Date. Returns the new state plus
 * `{moved, from, to, why}` for the athlete.
 */
export function stepLadder(state, verdict, { ladderLength, now = new Date(), painHold = false,
                                           catchUpRung = null, light = 'amber', totalsMin = null,
                                           longestRecentS = null, headroom = false } = {}) {
  const from = Math.max(0, Math.min((state && state.rung) | 0, ladderLength - 1));
  const changedAt = state && state.changedAt ? new Date(state.changedAt) : null;
  const days = changedAt ? (now - changedAt) / 86400000 : Infinity;
  const base = { rung: from, qualifying: (state && state.qualifying) || 0,
                 changedAt: state && state.changedAt ? state.changedAt : null,
                 loadSteps: (state && state.loadSteps) || [], skips: (state && state.skips) || [] };

  if (verdict === EASE_BACK) {
    const to = Math.max(0, from - 1);
    return { ...base, rung: to, qualifying: 0, changedAt: to !== from ? now.toISOString() : base.changedAt,
             moved: to !== from, from, to, why: 'stepping back one rung' };
  }
  if (verdict !== ADVANCE) {
    return { ...base, qualifying: 0, moved: false, from, to: from,
             why: 'repeat this rung; two good runs in a row move it up' };
  }
  const qualifying = base.qualifying + 1;
  if (from >= ladderLength - 1) {
    return { ...base, qualifying, moved: false, from, to: from, why: 'top of the ladder' };
  }
  if (painHold) {
    return { ...base, qualifying, moved: false, from, to: from, why: 'holding while the niggle settles' };
  }
  // Catching up to what he has already shown he can do (see demonstratedRung): one good run is enough
  // and there is no wait, because the load is not new -- the tissue has already taken it.
  if (catchUpRung != null && from < catchUpRung) {
    return { rung: from + 1, qualifying: 0, changedAt: now.toISOString(),
             moved: true, from, to: from + 1, why: 'catching up to what you have already run' };
  }
  const track = TRACKS[light] || TRACKS.amber;
  if (light === 'red') {
    return { ...base, qualifying, moved: false, from, to: from, track: light, why: 'holding: the body says not now' };
  }
  if (qualifying < track.qualifying) {
    return { ...base, qualifying, moved: false, from, to: from, track: light,
             why: `${qualifying} of ${track.qualifying} good runs on this rung` };
  }
  // A step that adds running (the session gets longer) is the one the injury evidence is about; a
  // step that only lengthens the blocks is not. `gate(to)` applies the track's waits and the spike cap
  // to a move from `from` to `to`, and returns the hold if one applies.
  const gate = to => {
    const isLoad = !!(totalsMin && totalsMin[to] > totalsMin[from]);
    const needDays = isLoad ? track.loadMinDays : track.minDays;
    if (days < needDays) {
      const ready = new Date(changedAt.getTime() + needDays * 86400000);
      return { isLoad, hold: { ...base, qualifying, moved: false, from, to: from, readyAt: ready.toISOString(), track: light,
        why: `earned, but the last step up was ${Math.floor(days)} day${Math.floor(days) === 1 ? '' : 's'} ago` } };
    }
    if (isLoad) {
      const week = base.loadSteps.filter(t => now - new Date(t) < 7 * 86400000).sort();
      if (week.length >= track.loadStepsPerWeek) {
        const ready = new Date(new Date(week[0]).getTime() + 7 * 86400000);
        return { isLoad, hold: { ...base, qualifying, moved: false, from, to: from, readyAt: ready.toISOString(), track: light,
          why: `earned, but ${week.length} step${week.length === 1 ? '' : 's'} that added running already this week` } };
      }
      if (longestRecentS > 0 && totalsMin[to] * 60 > SPIKE_MAX * longestRecentS) {
        return { isLoad, hold: { ...base, qualifying, moved: false, from, to: from, track: light,
          why: `the next step is ${totalsMin[to]} min of running and your longest session in 30 days is `
             + `${Math.round(longestRecentS / 60)} -- run this step's full time first` } };
      }
    }
    return { isLoad, hold: null };
  };
  const move = (to, isLoad, skipped) => ({
    rung: to, qualifying: 0, changedAt: now.toISOString(),
    loadSteps: isLoad ? [...base.loadSteps, now.toISOString()].slice(-10) : base.loadSteps,
    skips: skipped ? [...base.skips, now.toISOString()].slice(-5) : base.skips,
    moved: true, from, to, track: light, skipped,
    why: skipped ? 'every block ran full with heart rate well under the ceiling -- skipping a step'
                 : `${qualifying} good run${qualifying === 1 ? '' : 's'} in a row on this rung`,
  });

  // Two rungs at once: room to spare under the ceiling, every signal green, the rung exists, no skip
  // in the last week -- and the landing rung passes the same waits and spike cap as any other step.
  // If it does not, the ordinary one-rung step is tried instead.
  const recentSkip = base.skips.some(t => now - new Date(t) < SKIP_EVERY_DAYS * 86400000);
  if (headroom && light === 'green' && from + 2 <= ladderLength - 1 && !recentSkip) {
    const g2 = gate(from + 2);
    if (!g2.hold) return move(from + 2, g2.isLoad, true);
  }
  const g = gate(from + 1);
  return g.hold || move(from + 1, g.isLoad, false);
}

/**
 * The highest rung his own recent running already covers -- below which stepping up is catching up,
 * not adding load.
 *
 * Two limits, both from sessions in the last 30 days, and the rung must satisfy both:
 *   * its block is no more than HALF the longest continuous run (the same margin the plan's entry
 *     rule uses: one effort is not the same as the block repeated, aerobically);
 *   * its total running is no more than 15% over the most running done in one session. Single
 *     sessions much longer than the longest recent one are where novice injuries cluster
 *     (Frandsen et al. 2025), and that is tissue, which the heart rate cannot see.
 *
 * `sessions` are `[{at, longestRunS, runningS}]`; `ladder` is `[{run_min, reps}]`. Returns a rung
 * index, or null with no qualifying history.
 */
export function demonstratedRung(sessions, ladder, { now = new Date(), days = 30 } = {}) {
  const since = now.getTime() - days * 86400000;
  const recent = (sessions || []).filter(x => x && x.at && new Date(x.at).getTime() >= since);
  if (!recent.length || !(ladder && ladder.length)) return null;
  const longest = Math.max(0, ...recent.map(x => x.longestRunS || 0));
  const most = Math.max(0, ...recent.map(x => x.runningS || 0));
  let best = null;
  ladder.forEach((r, i) => {
    if (r.run_min * 60 <= longest / 2 && r.run_min * r.reps * 60 <= most * 1.15) best = i;
  });
  return best;
}
