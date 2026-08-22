// The gate on the ladder: does the next session get harder, stay, or get easier?
//
// Driven with the athlete's own two sessions, because those are the two cases that matter and both
// are real: 22 August, where a fourteen-minute prescription produced 2.6 minutes of running, and a
// hypothetical clean execution of the same session. A gate that passes both is not a gate.

import assert from 'node:assert/strict';
import { judgeSession, nextRung, ADVANCE, REPEAT, EASE_BACK,
         DECOUPLING_LIMIT_PCT } from '../progression.js';

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

console.log('\nAll progression tests passed.');
