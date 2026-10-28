// The gate on the ladder: does the next session get harder, stay, or get easier?
//
// Driven with the athlete's own two sessions, because those are the two cases that matter and both
// are real: 22 August, where a fourteen-minute prescription produced 2.6 minutes of running, and a
// hypothetical clean execution of the same session. A gate that passes both is not a gate.

import assert from 'node:assert/strict';
import { judgeSession, nextRung, ADVANCE, REPEAT, EASE_BACK,
         DECOUPLING_LIMIT_PCT, judgeHrSession, recoveryBaseline, RECOVERY_SLOW_FRACTION, HR_DONE_FRACTION,
         talkTestOffset, talkTestApplies, TALK_LIMIT_BPM, HR_DOSE_FRACTION,
         stepLadder, QUALIFYING_TO_ADVANCE, MIN_DAYS_BETWEEN_STEPS, demonstratedRung,
         trafficLight, TRACKS, SPIKE_MAX, hasHeadroom, SKIP_MARGIN_BPM } from '../progression.js';

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
  runBlockTargetS: 120, runningOverCeilingS: 0, toFloorMedianS: 80, ...over,
});

{
  // A clock-governed session -- the armband died, or it was never worn -- is a timer expiring, not a
  // body responding to load. Nothing here moves the ladder in either direction.
  const j = judgeHrSession(HR_TARGET, hrSummary({ governedBy: 'clock', toFloorMedianS: null }), null);
  assert.equal(j, null, 'a clock-governed summary must not move the ladder');
  console.log('  ok  a clock-governed HR summary returns nothing, not a guess');
}

{
  // The body stopped clearing the load early: two unrecovered walks after 3 of 7 blocks.
  const j = judgeHrSession(HR_TARGET,
    hrSummary({ endedBy: 'stall', runBlocks: 3, blocksFull: 2, blocksCut: 1 }), null);
  assert.equal(j.verdict, EASE_BACK, j.reason);
  assert.match(j.reason, /stopped clearing the load/);
  console.log(`  ok  a stall well short of the plan eases the ladder back ("${j.reason.slice(0, 50)}…")`);
}

{
  // A stall late in the session -- six blocks done -- is not an ease-back and must not advance.
  const j = judgeHrSession(HR_TARGET,
    hrSummary({ endedBy: 'stall', runBlocks: 6, blocksFull: 6 }), null);
  assert.equal(j.verdict, REPEAT,
    `a session the body ended must not advance the rung however close it got: ${j.verdict}`);
  assert.match(j.reason, /the second decides/);
  console.log('  ok  stalling late holds the rung rather than raising it');
}

{
  // Ceiling-to-floor a quarter slower than his own recent baseline: accumulated fatigue, so the
  // rung holds even though every block ran full.
  const baseline = 80;
  const j = judgeHrSession(HR_TARGET, hrSummary({ toFloorMedianS: baseline * RECOVERY_SLOW_FRACTION + 5 }), baseline);
  assert.equal(j.verdict, REPEAT, j.reason);
  assert.match(j.reason, /fatigue/);
  console.log('  ok  recovery a quarter slower than baseline holds the ladder, despite completion');
}

{
  // Decoupling is not evidence about a run/walk held to a ceiling (6 October read 12% across blocks,
  // walks and a cool-down). It must not hold the ladder.
  const j = judgeHrSession(HR_TARGET, hrSummary(), 80);
  assert.equal(j.verdict, ADVANCE, j.reason);
  assert.equal(judgeHrSession.length, 3, 'the judge takes no stats object to read drift from');
  console.log('  ok  heart-rate drift is not read for a ceiling-governed run/walk');
}

{
  // Every block ran full length, recovery holding, no drift: this is what earns the next rung.
  const j = judgeHrSession(HR_TARGET, hrSummary(), 80);
  assert.equal(j.verdict, ADVANCE, j.reason);
  assert.match(j.next, /rung/);
  assert.equal(j.evidence.blocksFull, 7);
  console.log(`  ok  every block full with recovery clean moves the ladder up ("${j.reason.slice(0, 46)}…")`);
}

{
  // One block cut by the ceiling out of seven still advances (6/7 >= HR_DONE_FRACTION); three cut does
  // not -- the heart is saying the rung is not yet comfortable, which is a repeat, not an ease-back.
  const one = judgeHrSession(HR_TARGET, hrSummary({ blocksFull: 6, blocksCut: 1 }), 80);
  assert.ok(6 / 7 >= HR_DONE_FRACTION);
  assert.equal(one.verdict, ADVANCE, one.reason);
  const three = judgeHrSession(HR_TARGET, hrSummary({ blocksFull: 4, blocksCut: 3 }), 80);
  assert.equal(three.verdict, REPEAT, three.reason);
  assert.match(three.reason, /3 cut short by the heart-rate ceiling/);
  console.log('  ok  one cut block still advances; several cut blocks repeat the rung');
}

{
  // 24 October: blocks cut by the ceiling at 75-100 s, but the controller's extra blocks exist to make
  // the running up. Done in full, that is the rung's dose delivered -- it advances. Short of it, it
  // repeats, as before.
  const done = judgeHrSession(HR_TARGET, hrSummary({ runBlocks: 9, blocksFull: 4, blocksCut: 5,
                                                     runningS: 820, runningTargetS: 840 }), 80);
  assert.ok(820 / 840 >= HR_DOSE_FRACTION);
  assert.equal(done.verdict, ADVANCE, done.reason);
  assert.match(done.reason, /extra blocks made up the rest: 14 min of the 14 min/);
  const short = judgeHrSession(HR_TARGET, hrSummary({ runBlocks: 7, blocksFull: 4, blocksCut: 3,
                                                      runningS: 735, runningTargetS: 840 }), 80);
  assert.equal(short.verdict, REPEAT, short.reason);
  // and the guards still come first: a stall or slow recovery is not rescued by the dose
  const slow = judgeHrSession(HR_TARGET, hrSummary({ blocksFull: 4, blocksCut: 5, runningS: 840,
                                                     runningTargetS: 840, toFloorMedianS: 200 }), 80);
  assert.equal(slow.verdict, REPEAT);
  console.log('  ok  the rung\'s running done in full, extra blocks included, advances; short of it repeats');
}

{
  // Hills: blocks cut on climbs, or ended at the top of a steep descent, are set aside. Five of five
  // flat blocks full is an advance even with two hill blocks cut; a session that was mostly hills
  // tests nothing and holds the rung.
  const j = judgeHrSession(HR_TARGET, hrSummary({ blocksFull: 5, blocksCut: 2, blocksHill: 2 }), 80);
  assert.equal(j.verdict, ADVANCE, j.reason);
  assert.equal(j.evidence.blocksTested, 5);
  assert.match(j.reason, /2 on hills set aside/);
  const hilly = judgeHrSession(HR_TARGET,
    hrSummary({ blocksFull: 2, blocksCut: 3, blocksHill: 3, blocksSteepDown: 2 }), 80);
  assert.equal(hilly.verdict, REPEAT, hilly.reason);
  assert.match(hilly.reason, /decided by hills/);
  console.log('  ok  hill blocks are set aside; a mostly-hill session holds the rung rather than judging it');
}

{
  // The athlete stopped early, no stall, no fatigue signal: a repeat, not a verdict either way.
  const j = judgeHrSession(HR_TARGET,
    hrSummary({ endedBy: 'athlete', runBlocks: 4, blocksFull: 4, toFloorMedianS: null }), null);
  assert.equal(j.verdict, REPEAT, j.reason);
  console.log('  ok  stopping short without a stall or fatigue signal is a repeat');
}

{
  // No target, no summary: a real answer, not a guess.
  assert.equal(judgeHrSession(null, { governedBy: 'hr' }, null), null);
  assert.equal(judgeHrSession(HR_TARGET, null, null), null);
  console.log('  ok  an unjudgeable HR session returns nothing rather than a guess');
}

// --- recoveryBaseline: this athlete's own recent ceiling-to-floor time, in place of overnight HRV -----------

{
  assert.equal(recoveryBaseline([]), null);
  assert.equal(recoveryBaseline([{ toFloorMedianS: 20 }, { toFloorMedianS: 22 }]), null,
    'two sessions is a guess wearing a number, not a baseline');
  const three = recoveryBaseline([{ toFloorMedianS: 18 }, { toFloorMedianS: 20 }, { toFloorMedianS: 22 }]);
  assert.equal(three, 20);
  console.log(`  ok  a baseline needs at least three sessions and is their median (${three})`);
}

{
  // Nulls (sessions with no recovery reading at all) are dropped rather than counted as zero, and
  // only the most recent five count -- the baseline follows fitness, it does not average a career.
  const withNulls = recoveryBaseline([{ toFloorMedianS: 10 }, { toFloorMedianS: null }, { toFloorMedianS: 12 },
                                  { toFloorMedianS: 14 }, { toFloorMedianS: 16 }, { toFloorMedianS: 18 }]);
  assert.equal(withNulls, 14);
  const longHistory = recoveryBaseline([1, 2, 3, 4, 5, 6, 7].map(toFloorMedianS => ({ toFloorMedianS })));
  assert.equal(longHistory, 5, 'only the last five sessions count toward the baseline');
  console.log(`  ok  a missing recovery reading is dropped, not counted as zero, `
            + `and the baseline follows the last five sessions (${withNulls}, ${longHistory})`);
}

// --- the talk test moves the ceiling --------------------------------------------------------------

{
  assert.equal(talkTestOffset([]), 0);
  assert.equal(talkTestOffset([{ answer: 'easy' }, { answer: 'easy' }]), 6, 'two easy answers: +6');
  assert.equal(talkTestOffset([{ answer: 'easy' }, { answer: 'hard' }]), -2, 'hard steps down further than easy steps up');
  assert.equal(talkTestOffset(Array(10).fill({ answer: 'easy' })), TALK_LIMIT_BPM, 'bounded above');
  assert.equal(talkTestOffset(Array(10).fill({ answer: 'hard' })), -TALK_LIMIT_BPM, 'and below');
  assert.equal(talkTestOffset([{ answer: 'just' }, { answer: 'nonsense' }]), 0);
  // Asked only when the ceiling actually ended blocks -- not on 9 October's all-full one-minute blocks.
  assert.equal(talkTestApplies({ governedBy: 'hr', blocksCut: 0, blocksFull: 8 }), false);
  assert.equal(talkTestApplies({ governedBy: 'hr', blocksCut: 6 }), true);
  assert.equal(talkTestApplies({ governedBy: 'hr', blocksCut: 3, blocksHill: 2 }), false, 'hill cuts do not count');
  assert.equal(talkTestApplies({ governedBy: 'clock', blocksCut: 6 }), false);
  console.log('  ok  talk-test answers move the ceiling in small bounded steps, asked only when it was tested');
}

// --- the ladder moves at the pace tissue adapts ----------------------------------------------------

{
  const L = 10, day = d => new Date(Date.UTC(2026, 9, d, 18));
  // Wed / Sat / Sun / Wed, every run qualifying. One rung a week, not three.
  let st = { rung: 1, qualifying: 0, changedAt: day(7).toISOString() };
  const trail = [];
  for (const d of [10, 11, 14, 17, 18, 21]) {
    st = stepLadder(st, ADVANCE, { ladderLength: L, now: day(d) });
    trail.push(`${d}:${st.rung}`);
  }
  assert.deepEqual(trail, ['10:1', '11:1', '14:2', '17:2', '18:2', '21:3'],
    `two in a row, six days apart: ${trail.join(' ')}`);
  // A REPEAT breaks the run of qualifying sessions.
  let r = stepLadder({ rung: 2, qualifying: 1, changedAt: day(1).toISOString() }, REPEAT, { ladderLength: L, now: day(10) });
  assert.equal(r.qualifying, 0); assert.equal(r.rung, 2);
  r = stepLadder(r, ADVANCE, { ladderLength: L, now: day(11) });
  assert.equal(r.rung, 2, 'one qualifying run after a repeat is not two');
  // EASE_BACK is immediate, however recent the last change.
  const e = stepLadder({ rung: 3, qualifying: 1, changedAt: day(9).toISOString() }, EASE_BACK, { ladderLength: L, now: day(10) });
  assert.equal(e.rung, 2); assert.equal(e.moved, true);
  // A pain pattern holds the step up but keeps the count, and the top is the top.
  const p = stepLadder({ rung: 2, qualifying: 1, changedAt: day(1).toISOString() }, ADVANCE, { ladderLength: L, now: day(10), painHold: true });
  assert.equal(p.rung, 2); assert.match(p.why, /niggle/);
  assert.equal(stepLadder({ rung: 9, qualifying: 5 }, ADVANCE, { ladderLength: L, now: day(10) }).rung, 9);
  // No history (first ever step): two qualifying runs are still needed, but no wait.
  let f = stepLadder(null, ADVANCE, { ladderLength: L, now: day(10) });
  f = stepLadder(f, ADVANCE, { ladderLength: L, now: day(11) });
  assert.equal(f.rung, 1);
  console.log(`  ok  the ladder needs ${QUALIFYING_TO_ADVANCE} good runs in a row and ${MIN_DAYS_BETWEEN_STEPS} days between steps up (${trail.join(' ')})`);
}

{
  const L = [[1, 8], [2, 7], [3, 6], [4, 5], [5, 4], [6, 4], [8, 3], [10, 3], [15, 2], [30, 1]]
    .map(([run_min, reps]) => ({ run_min, reps }));
  const now = new Date(Date.UTC(2026, 9, 13, 21));
  // 13 October as Polar recorded it: 11.2 min continuous, ~15.7 min of running in the session.
  const r = demonstratedRung([{ at: '2026-10-13T20:09:00Z', longestRunS: 672, runningS: 942 }], L, { now });
  assert.equal(r, 2, `3 x 6: block <= half of 11.2 min, total 18 <= 1.15 x 15.7: got ${r}`);
  // Old sessions do not count.
  assert.equal(demonstratedRung([{ at: '2026-08-01T00:00:00Z', longestRunS: 1800, runningS: 1800 }], L, { now }), null);
  // Catching up: one good run, no wait.
  const day = d => new Date(Date.UTC(2026, 9, d, 18));
  let st = { rung: 1, qualifying: 0, changedAt: day(12).toISOString() };
  st = stepLadder(st, ADVANCE, { ladderLength: 10, now: day(14), catchUpRung: 2 });
  assert.equal(st.rung, 2); assert.match(st.why, /catching up/);
  st = stepLadder(st, ADVANCE, { ladderLength: 10, now: day(15), catchUpRung: 2 });
  assert.equal(st.rung, 2, 'at the demonstrated rung the ordinary rule applies again');
  // A repeat is still a repeat while catching up.
  assert.equal(stepLadder({ rung: 1 }, REPEAT, { ladderLength: 10, now: day(14), catchUpRung: 4 }).rung, 1);
  console.log('  ok  stepping up to what recent sessions already covered needs one good run and no wait');
}

{
  // The fast track, all green, from 2 min x 7 to the 5K: a run every other day, every one good. The
  // ladder's totals (min of running): steps that keep the total come every 2 days; steps that add
  // running every 3+, at most two a week, never past 1.3x the longest session of the last 30 days.
  const totals = [8, 14, 18, 20, 20, 24, 24, 30, 30, 30, 35, 40];
  const t0 = new Date('2026-10-26T12:00:00Z');
  const day = d => new Date(t0.getTime() + d * 86400000);
  let st = { rung: 1, qualifying: 0, changedAt: day(-3).toISOString() };
  let longest = 14 * 60;
  const trail = [];
  for (let d = 0; d <= 80 && st.rung < totals.length - 1; d += 2) {
    longest = Math.max(longest, totals[st.rung] * 60);   // he runs the step's full time
    const r = stepLadder(st, ADVANCE, { ladderLength: totals.length, now: day(d), light: 'green',
                                        totalsMin: totals, longestRecentS: longest });
    if (r.moved) {
      trail.push(`d${d}:${totals[r.to]}`);
      if (totals[r.to] > totals[r.from]) assert.ok(totals[r.to] * 60 <= SPIKE_MAX * longest, 'no spike past 1.3x');
    }
    st = r;
  }
  const doneDay = Number(trail.at(-1).split(':')[0].slice(1));
  assert.equal(st.rung, totals.length - 1, `reached the top: ${trail.join(' ')}`);
  assert.ok(doneDay >= 21 && doneDay <= 35, `about three to five weeks all-green, not days and not months: day ${doneDay}`);
  const loads = trail.map(x => x.split(':')).filter((x, i, a) => i > 0 && Number(x[1]) > Number(a[i - 1][1]));
  // no more than two running-adding steps in any 7 days
  const ld = st.loadSteps.map(x => new Date(x).getTime());
  for (const a of ld) assert.ok(ld.filter(b => b >= a && b - a < 7 * 86400000).length <= 2, 'at most two load steps a week');
  console.log(`  ok  all green, the fast track reaches the 5K step in ${doneDay} days (${trail.join(' ')})`);

  // The same run of good sessions on the steady track takes about twice as long or more.
  let a = { rung: 1, qualifying: 0, changedAt: day(-3).toISOString() };
  let ad = null;
  for (let d = 0; d <= 200 && a.rung < totals.length - 1; d += 2) {
    a = stepLadder(a, ADVANCE, { ladderLength: totals.length, now: day(d), light: 'amber', totalsMin: totals, longestRecentS: 40 * 60 });
    if (a.rung === totals.length - 1) ad = d;
  }
  assert.ok(ad >= doneDay * 1.8, `steady track ${ad} days vs fast ${doneDay}`);
  console.log(`  ok  the steady track takes ${ad} days for the same run of good sessions`);
}

{
  // Red holds; the light comes from the body's signals.
  const r = stepLadder({ rung: 3, qualifying: 3 }, ADVANCE, { ladderLength: 12, light: 'red', now: new Date() });
  assert.equal(r.moved, false);
  assert.match(r.why, /holding/);
  assert.equal(trafficLight({}).light, 'green');
  assert.equal(trafficLight({ readiness: 'suppressed' }).light, 'amber');
  assert.equal(trafficLight({ lastTalk: 'hard' }).light, 'amber');
  assert.equal(trafficLight({ painRecent: true }).light, 'amber');
  assert.equal(trafficLight({ readiness: 'strained' }).light, 'red');
  const p = trafficLight({ painHold: { hold: true, site: 'left_shin' }, readiness: 'suppressed' });
  assert.equal(p.light, 'red');
  assert.match(p.why[0], /left shin is a pattern/);
  // A spike: the next step adds running past 1.3x the longest of the last 30 days -- held, with why.
  const s = stepLadder({ rung: 1, qualifying: 0, changedAt: '2026-10-01T00:00:00Z' }, ADVANCE,
    { ladderLength: 12, light: 'green', totalsMin: [8, 14, 18], longestRecentS: 12 * 60, now: new Date('2026-10-26T00:00:00Z') });
  assert.equal(s.moved, false);
  assert.match(s.why, /longest session in 30 days is 12/);
  console.log('  ok  red holds; amber and red come from HRV, pain, and the talk test; a spike is held with the reason');
}

console.log('\nAll progression tests passed.');

{
  // Skipping a step (asked for 28 October): every block full, heart rate 10+ under the ceiling, green.
  const full = { governedBy: 'hr', ceilingBpm: 170, blocksPlanned: 6, blocksFull: 6, blocksCut: 0, peakRunHr: 158 };
  assert.equal(hasHeadroom(full), true);
  assert.equal(hasHeadroom({ ...full, peakRunHr: 170 - SKIP_MARGIN_BPM + 1 }), false, 'too close to the ceiling');
  assert.equal(hasHeadroom({ ...full, blocksFull: 5, blocksCut: 1 }), false, 'a block cut');
  assert.equal(hasHeadroom({ ...full, governedBy: 'clock' }), false);
  assert.equal(hasHeadroom(null), false);

  const totals = [8, 14, 18, 20, 20, 24, 24, 30, 30, 30, 35, 40];
  const now = new Date('2026-11-01T12:00:00Z');
  const st = { rung: 2, qualifying: 0, changedAt: new Date('2026-10-28T12:00:00Z').toISOString() };
  const opts = { ladderLength: totals.length, now, light: 'green', totalsMin: totals, longestRecentS: 18 * 60, headroom: true };
  const r = stepLadder(st, ADVANCE, opts);
  assert.equal(r.to, 4, `6 x 3 skips 5 x 4 to 4 x 5: ${JSON.stringify(r)}`);
  assert.equal(r.skipped, true); assert.equal(r.skips.length, 1);
  // Not on amber, not twice in a week, and not past the spike cap (then one ordinary step instead).
  assert.equal(stepLadder(st, ADVANCE, { ...opts, light: 'amber' }).skipped, undefined);
  const again = stepLadder({ ...st, skips: [new Date('2026-10-29T12:00:00Z').toISOString()] }, ADVANCE, opts);
  assert.equal(again.to, 3); assert.equal(again.skipped, false);
  const spike = stepLadder({ ...st, rung: 5 }, ADVANCE, { ...opts, longestRecentS: 20 * 60 });   // 4x6 (24) -> 3x8 (24) ok; 3x10 (30) > 1.3 x 20
  assert.equal(spike.to, 6, `the skip would be a spike, so one step: ${JSON.stringify(spike)}`);
  // Without headroom, the ordinary step.
  assert.equal(stepLadder(st, ADVANCE, { ...opts, headroom: false }).to, 3);
  console.log('  ok  a step is skipped with room under the ceiling on green, once a week, never past the spike cap');
}
