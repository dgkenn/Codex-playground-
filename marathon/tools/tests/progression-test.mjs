// The gate on the ladder: does the next session get harder, stay, or get easier?
//
// Driven with the athlete's own two sessions, because those are the two cases that matter and both
// are real: 22 August, where a fourteen-minute prescription produced 2.6 minutes of running, and a
// hypothetical clean execution of the same session. A gate that passes both is not a gate.

import assert from 'node:assert/strict';
import { judgeSession, nextRung, ADVANCE, REPEAT, EASE_BACK,
         DECOUPLING_LIMIT_PCT, judgeHrSession, hrrBaseline, HRR_DROP_FRACTION, HR_DONE_FRACTION } from '../progression.js';

const PRESCRIBED = { runMin: 2, walkMin: 2, reps: 7 };      // 14 minutes of running

{
  // 22 August, as recorded. Polar's own speed trace: 2.6 minutes above the gait transition inside a
  // 26-minute session, longest block 37 seconds, against seven two-minute blocks.
  //
  // Under the calendar ladder the following Wednesday asks for three-minute blocks. Asking someone
  // for three minutes when they have just not held two is how a plan produces an injury, and the
  // plan would never have known.
  const j = judgeSession(PRESCRIBED, {
    runningS: 156, longestRunBlockS: 37, pctAtOrBelowEasy: 93, decouplingPct: 17,
  });
  assert.equal(j.verdict, EASE_BACK, j.reason);
  assert.match(j.reason, /2:36.*14:00/, `the numbers must be in the reason: "${j.reason}"`);
  assert.ok(j.evidence.completedFraction < 0.2);
  console.log(`  ok  a session that did not happen steps the ladder DOWN ("${j.reason.slice(0, 62)}…")`);
}

{
  // The same session executed. Seven two-minute blocks at the prescribed pace, aerobic throughout.
  const j = judgeSession(PRESCRIBED, {
    runningS: 14 * 60, longestRunBlockS: 121, pctAtOrBelowEasy: 91, decouplingPct: 4,
  });
  assert.equal(j.verdict, ADVANCE, j.reason);
  assert.match(j.next, /rung/);
  console.log(`  ok  a session done as prescribed moves it UP ("${j.reason.slice(0, 58)}…")`);
}

{
  // Completed, but by running the blocks hard. This is the case the gate exists for: every number a
  // schedule looks at says success, and the thing the phase is actually training was not trained.
  const hard = judgeSession(PRESCRIBED, {
    runningS: 14 * 60, longestRunBlockS: 125, pctAtOrBelowEasy: 65, decouplingPct: 5,
  });
  assert.equal(hard.verdict, REPEAT, hard.reason);
  assert.match(hard.reason, /above the easy ceiling/);

  // And well past the ceiling is a step back, not a repeat — the intervals were a workout.
  const veryHard = judgeSession(PRESCRIBED, {
    runningS: 14 * 60, longestRunBlockS: 125, pctAtOrBelowEasy: 40, decouplingPct: 5,
  });
  assert.equal(veryHard.verdict, EASE_BACK, veryHard.reason);
  console.log('  ok  completing the intervals by running them hard does not earn the next rung');
}

{
  // Total running fine, longest block short: the blocks were broken up. The block length is what
  // this phase trains, so it is the thing the gate has to be sensitive to.
  const j = judgeSession(PRESCRIBED, {
    runningS: 13 * 60, longestRunBlockS: 75, pctAtOrBelowEasy: 95, decouplingPct: 3,
  });
  assert.equal(j.verdict, REPEAT, j.reason);
  assert.match(j.reason, /1:15.*2:00/, j.reason);
  console.log('  ok  enough running in the wrong shape is a repeat, not an advance');
}

{
  // Drift: the intervals were fine and the duration was not.
  const j = judgeSession(PRESCRIBED, {
    runningS: 14 * 60, longestRunBlockS: 122, pctAtOrBelowEasy: 95,
    decouplingPct: DECOUPLING_LIMIT_PCT + 5,
  });
  assert.equal(j.verdict, REPEAT, j.reason);
  assert.match(j.reason, /drift/i);
  console.log('  ok  heart-rate drift holds the duration even when the intervals were clean');
}

{
  // No armband. Absence of the aerobic evidence is not failure of it — a strap that died must not
  // freeze the ladder, and must not wave through a session it cannot see either.
  const j = judgeSession(PRESCRIBED, {
    runningS: 14 * 60, longestRunBlockS: 121, pctAtOrBelowEasy: null, decouplingPct: null,
  });
  assert.equal(j.verdict, ADVANCE, j.reason);
  assert.equal(j.evidence.aerobicFraction, null);
  assert.doesNotMatch(j.reason, /aerobic/, 'and it must not claim evidence it does not have');
  console.log('  ok  a session with no heart rate is judged on what was recorded, not penalised');
}

{
  // Nothing to judge is a real answer.
  assert.equal(judgeSession(null, { runningS: 100 }), null);
  assert.equal(judgeSession(PRESCRIBED, null), null);
  assert.equal(judgeSession({ runMin: 0, reps: 0 }, { runningS: 0 }), null);
  console.log('  ok  an unjudgeable session returns nothing rather than a guess');
}

{
  // One rung at a time, in both directions, and never off either end. A session that went unusually
  // well jumping two rungs is exactly the aggression this exists to prevent.
  assert.equal(nextRung(3, ADVANCE, 8), 4);
  assert.equal(nextRung(3, REPEAT, 8), 3);
  assert.equal(nextRung(3, EASE_BACK, 8), 2);
  assert.equal(nextRung(0, EASE_BACK, 8), 0, 'the bottom rung is the bottom');
  assert.equal(nextRung(7, ADVANCE, 8), 7, 'and the top is the top');
  assert.equal(nextRung(-4, REPEAT, 8), 0);
  console.log('  ok  the ladder moves one rung at a time and stays on itself');
}

// --- judgeHrSession: the gate for sessions where the body called the blocks, not the clock ---------

const HR_TARGET = { blocks: 7, blockS: 120 };      // seven blocks of up to two minutes

/** A summary shaped like HrBlocks.summary(): `full` blocks of `planned` ran their full length. */
const hrSummary = (over = {}) => ({
  governedBy: 'hr', endedBy: 'reps', blocksPlanned: 7, runBlocks: 7, blocksFull: 7, blocksCut: 0,
  runBlockTargetS: 120, runningOverCeilingS: 0, hrr60Median: 25, ...over,
});

{
  // A clock-governed session -- the armband died, or it was never worn -- is a timer expiring, not a
  // body responding to load. Nothing here moves the ladder in either direction.
  const j = judgeHrSession(HR_TARGET, hrSummary({ governedBy: 'clock', hrr60Median: null }), null, null);
  assert.equal(j, null, 'a clock-governed summary must not move the ladder');
  console.log('  ok  a clock-governed HR summary returns nothing, not a guess');
}

{
  // The body stopped clearing the load early: two unrecovered walks after 3 of 7 blocks.
  const j = judgeHrSession(HR_TARGET,
    hrSummary({ endedBy: 'stall', runBlocks: 3, blocksFull: 2, blocksCut: 1 }), null, null);
  assert.equal(j.verdict, EASE_BACK, j.reason);
  assert.match(j.reason, /stopped clearing the load/);
  console.log(`  ok  a stall well short of the plan eases the ladder back ("${j.reason.slice(0, 50)}…")`);
}

{
  // A stall late in the session -- six blocks done -- is not an ease-back and must not advance.
  const j = judgeHrSession(HR_TARGET,
    hrSummary({ endedBy: 'stall', runBlocks: 6, blocksFull: 6 }), { decouplingPct: 3 }, null);
  assert.equal(j.verdict, REPEAT,
    `a session the body ended must not advance the rung however close it got: ${j.verdict}`);
  assert.match(j.reason, /the second decides/);
  console.log('  ok  stalling late holds the rung rather than raising it');
}

{
  // HRR60 down more than a fifth against his own recent baseline: accumulated fatigue, checked before
  // decoupling and before completion, because it is the more direct explanation for either.
  const baseline = 20, droppedHrr = baseline * HRR_DROP_FRACTION - 1;
  const j = judgeHrSession(HR_TARGET, hrSummary({ hrr60Median: droppedHrr }), { decouplingPct: 3 }, baseline);
  assert.equal(j.verdict, REPEAT, j.reason);
  assert.match(j.reason, /fatigue/);
  console.log('  ok  HRR60 down more than a fifth from baseline holds the ladder, despite completion');
}

{
  // Recovery is fine, but heart rate drifted against pace between the halves.
  const j = judgeHrSession(HR_TARGET, hrSummary(), { decouplingPct: DECOUPLING_LIMIT_PCT + 5 }, 20);
  assert.equal(j.verdict, REPEAT, j.reason);
  assert.match(j.reason, /drift/i);
  console.log('  ok  heart-rate drift holds the ladder even with every block full and recovery fine');
}

{
  // Every block ran full length, recovery holding, no drift: this is what earns the next rung.
  const j = judgeHrSession(HR_TARGET, hrSummary(), { decouplingPct: 3 }, 20);
  assert.equal(j.verdict, ADVANCE, j.reason);
  assert.match(j.next, /rung/);
  assert.equal(j.evidence.blocksFull, 7);
  console.log(`  ok  every block full with recovery and decoupling clean moves the ladder up ("${j.reason.slice(0, 46)}…")`);
}

{
  // One block cut by the ceiling out of seven still advances (6/7 >= HR_DONE_FRACTION); three cut does
  // not -- the heart is saying the rung is not yet comfortable, which is a repeat, not an ease-back.
  const one = judgeHrSession(HR_TARGET, hrSummary({ blocksFull: 6, blocksCut: 1 }), { decouplingPct: 3 }, 20);
  assert.ok(6 / 7 >= HR_DONE_FRACTION);
  assert.equal(one.verdict, ADVANCE, one.reason);
  const three = judgeHrSession(HR_TARGET, hrSummary({ blocksFull: 4, blocksCut: 3 }), { decouplingPct: 3 }, 20);
  assert.equal(three.verdict, REPEAT, three.reason);
  assert.match(three.reason, /3 cut short by the heart-rate ceiling/);
  console.log('  ok  one cut block still advances; several cut blocks repeat the rung');
}

{
  // The athlete stopped early, no stall, no fatigue signal: a repeat, not a verdict either way.
  const j = judgeHrSession(HR_TARGET,
    hrSummary({ endedBy: 'athlete', runBlocks: 4, blocksFull: 4, hrr60Median: null }), null, null);
  assert.equal(j.verdict, REPEAT, j.reason);
  console.log('  ok  stopping short without a stall or fatigue signal is a repeat');
}

{
  // No target, no summary: a real answer, not a guess.
  assert.equal(judgeHrSession(null, { governedBy: 'hr' }, null, null), null);
  assert.equal(judgeHrSession(HR_TARGET, null, null, null), null);
  console.log('  ok  an unjudgeable HR session returns nothing rather than a guess');
}

// --- hrrBaseline: this athlete's own recent autonomic baseline, in place of overnight HRV -----------

{
  assert.equal(hrrBaseline([]), null);
  assert.equal(hrrBaseline([{ hrr60Median: 20 }, { hrr60Median: 22 }]), null,
    'two sessions is a guess wearing a number, not a baseline');
  const three = hrrBaseline([{ hrr60Median: 18 }, { hrr60Median: 20 }, { hrr60Median: 22 }]);
  assert.equal(three, 20);
  console.log(`  ok  a baseline needs at least three sessions and is their median (${three})`);
}

{
  // Nulls (sessions with no recovery reading at all) are dropped rather than counted as zero, and
  // only the most recent five count -- the baseline follows fitness, it does not average a career.
  const withNulls = hrrBaseline([{ hrr60Median: 10 }, { hrr60Median: null }, { hrr60Median: 12 },
                                  { hrr60Median: 14 }, { hrr60Median: 16 }, { hrr60Median: 18 }]);
  assert.equal(withNulls, 14);
  const longHistory = hrrBaseline([1, 2, 3, 4, 5, 6, 7].map(hrr60Median => ({ hrr60Median })));
  assert.equal(longHistory, 5, 'only the last five sessions count toward the baseline');
  console.log(`  ok  a missing recovery reading is dropped, not counted as zero, `
            + `and the baseline follows the last five sessions (${withNulls}, ${longHistory})`);
}

console.log('\nAll progression tests passed.');
