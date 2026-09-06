// The gate on the ladder: does the next session get harder, stay, or get easier?
//
// Driven with the athlete's own two sessions, because those are the two cases that matter and both
// are real: 22 August, where a fourteen-minute prescription produced 2.6 minutes of running, and a
// hypothetical clean execution of the same session. A gate that passes both is not a gate.

import assert from 'node:assert/strict';
import { judgeSession, nextRung, ADVANCE, REPEAT, EASE_BACK,
         DECOUPLING_LIMIT_PCT, judgeHrSession, hrrBaseline, HRR_DROP_FRACTION } from '../progression.js';

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

const HR_TARGET = { runningMinTarget: 14 };      // 14 minutes of running under the ceiling, total

{
  // A clock-governed session -- the armband died, or it was never worn -- is a timer expiring, not a
  // body responding to load. No ceiling crossings happened at all; there is nothing here to move the
  // ladder on, in either direction.
  const j = judgeHrSession(HR_TARGET,
    { governedBy: 'clock', runningUnderCeilingS: 900, endedBy: 'athlete', hrr60Median: null },
    null, null);
  assert.equal(j, null, 'a clock-governed summary must not move the ladder');
  console.log('  ok  a clock-governed HR summary returns nothing, not a guess');
}

{
  // Two stalled recoveries ended the running well short of the target -- the body ended this session,
  // and the plan should say so rather than pretend the target was met.
  const j = judgeHrSession(HR_TARGET,
    { governedBy: 'hr', endedBy: 'stall', runningUnderCeilingS: 240, hrr60Median: 20 }, null, null);
  assert.equal(j.verdict, EASE_BACK, j.reason);
  assert.match(j.reason, /stopped clearing the load/);
  console.log(`  ok  a stall well short of the target eases the ladder back ("${j.reason.slice(0, 50)}…")`);
}

{
  // The gap the reviewer found in the first version: a stall that had nonetheless reached the target
  // fell through to ADVANCE, while the ADVANCE reason text claimed the session was "ended by the plan
  // or the athlete rather than the body giving out". Reached-and-stalled is the load to sit at.
  const j = judgeHrSession(HR_TARGET,
    { governedBy: 'hr', endedBy: 'stall', runningUnderCeilingS: HR_TARGET.runningMinTarget * 60 * 0.95,
      hrr60Median: 20 }, { decouplingPct: 3 }, null);
  assert.equal(j.verdict, REPEAT,
    `a session the body ended must not advance the rung however close it got: ${j.verdict}`);
  assert.match(j.reason, /the body said that was enough/);
  console.log('  ok  reaching the target and then stalling holds the rung rather than raising it');
}

{
  // HRR60 down more than a fifth against his own recent baseline: accumulated fatigue, checked before
  // decoupling and before completion, because it is the more direct explanation for either.
  const baseline = 20, droppedHrr = baseline * HRR_DROP_FRACTION - 1;
  const j = judgeHrSession(HR_TARGET,
    { governedBy: 'hr', endedBy: 'reps', runningUnderCeilingS: 800, hrr60Median: droppedHrr },
    { decouplingPct: 3 }, baseline);
  assert.equal(j.verdict, REPEAT, j.reason);
  assert.match(j.reason, /fatigue/);
  console.log('  ok  HRR60 down more than a fifth from baseline holds the ladder, despite completion');
}

{
  // Recovery is fine, but heart rate drifted against pace between the halves: the ceiling did its
  // job on intensity, the duration is what is at the edge.
  const j = judgeHrSession(HR_TARGET,
    { governedBy: 'hr', endedBy: 'reps', runningUnderCeilingS: 800, hrr60Median: 25 },
    { decouplingPct: DECOUPLING_LIMIT_PCT + 5 }, 20);
  assert.equal(j.verdict, REPEAT, j.reason);
  assert.match(j.reason, /drift/i);
  console.log('  ok  heart-rate drift holds the ladder even with the target reached and recovery fine');
}

{
  // Reached the target, ended by the plan's own rep count, recovery holding, no drift: this is what
  // earns the next rung.
  const j = judgeHrSession(HR_TARGET,
    { governedBy: 'hr', endedBy: 'reps', runningUnderCeilingS: 800, hrr60Median: 25 },
    { decouplingPct: 3 }, 20);
  assert.equal(j.verdict, ADVANCE, j.reason);
  assert.match(j.next, /rung/);
  console.log(`  ok  a target reached with recovery and decoupling both clean moves the ladder up `
            + `("${j.reason.slice(0, 46)}…")`);
}

{
  // `endedBy: 'target'` is what a session under HR governance actually reports now -- see
  // hr-blocks.js: `reps` is retired as the block cap once the body is calling the blocks, replaced by
  // a total-running target, and reaching it must read exactly like reaching the old rep count did:
  // "the plan", not "the athlete", ended this, and it advances on the same evidence.
  const j = judgeHrSession(HR_TARGET,
    { governedBy: 'hr', endedBy: 'target', runningUnderCeilingS: 800, hrr60Median: 25 },
    { decouplingPct: 3 }, 20);
  assert.equal(j.verdict, ADVANCE, j.reason);
  assert.match(j.reason, /ended by the plan/,
    `endedBy 'target' must read as the plan's own end, same as 'reps': "${j.reason}"`);
  console.log(`  ok  endedBy 'target' with the running target met advances the ladder, same as 'reps'`);
}

{
  // Short of the target but not by a stall -- the athlete ended it, or the target was set a little
  // ahead of what today had. Not a near miss that should be counted as done, and not a body failure
  // that eases back either -- repeat and see.
  const j = judgeHrSession(HR_TARGET,
    { governedBy: 'hr', endedBy: 'athlete', runningUnderCeilingS: 600, hrr60Median: null }, null, null);
  assert.equal(j.verdict, REPEAT, j.reason);
  console.log('  ok  short of the target without a stall or fatigue signal is a repeat, not a verdict either way');
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
