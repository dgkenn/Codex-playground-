// The controller, driven by heart-rate traces rather than by assertions about its internals.
//
// The last case replays the athlete's own recorded session -- the one that peaked at 177 bpm in a
// prescription capped at 155 -- so the claim that this would have prevented it is measured against
// the physiology that produced it rather than against a model of it.

import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { HrBlocks, BlockPhase as Phase } from '../hr-blocks.js';

const CEIL = 150, FLOOR = 125;

/** Drive the controller for `seconds`, where `hrAt(t, phase)` supplies the heart rate. */
function drive(b, seconds, hrAt, { hrFresh = () => true, from = 0 } = {}) {
  const events = [];
  for (let t = from; t < from + seconds; t++) {
    const ev = b.update(t, hrAt(t, b.phase), { hrFresh: hrFresh(t) });
    if (ev) events.push({ t, ...ev });
  }
  return events;
}

{
  // The shape of the thing: warm up walking, run until the ceiling, walk until the floor.
  //
  // Heart rate modelled as a first-order response to effort, which is what it is: it rises toward a
  // running asymptote above the ceiling and falls toward a walking one below the floor, with a time
  // constant of about half a minute. The exact constant does not matter; that HR LAGS does.
  let hr = 110;
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, fallbackRunS: 120, fallbackWalkS: 120 });
  const evs = drive(b, 1800, () => {
    const target = b.phase === Phase.RUN ? 172 : 105;
    hr += (target - hr) / 30;
    return hr;
  });
  const runs = evs.filter(e => e.previous === Phase.RUN);
  const walks = evs.filter(e => e.phase === Phase.RUN && e.previous !== Phase.DONE);
  assert.ok(runs.length >= 3, `a half-hour must produce several blocks: ${runs.length}`);
  assert.ok(runs.every(e => e.reason === 'ceiling'),
    `every block must end at the ceiling: ${JSON.stringify(runs.map(e => e.reason))}`);
  assert.ok(walks.every(e => e.reason === 'recovered' || e.reason === 'warm-up done'),
    `every walk must end at the floor: ${JSON.stringify(walks.map(e => e.reason))}`);
  const s = b.summary();
  assert.equal(s.governedBy, 'hr');
  assert.ok(s.hrr60Median > 0, 'and each transition must yield a recovery measurement');
  console.log(`  ok  ceiling ends the run, floor ends the walk `
            + `(${s.runBlocks} blocks, ${s.runningS}s running, HRR60 median ${s.hrr60Median.toFixed(0)})`);
}

{
  // Heart rate lags, so the first seconds of a block report the block before it. Without a floor on
  // block length a session that opens with an elevated heart rate collapses into run-two-seconds,
  // walk-two-seconds -- not a workout, and the kind of thing that makes an athlete stop trusting
  // the app entirely.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, fallbackRunS: 120, fallbackWalkS: 120 });
  const evs = drive(b, 900, () => 200);         // pinned far above the ceiling: worst case
  const runs = [];
  let last = null;
  for (const e of evs) {
    if (e.previous === Phase.RUN && last != null) runs.push(e.t - last);
    if (e.phase === Phase.RUN) last = e.t;
  }
  assert.ok(runs.every(d => d >= 30), `no block may be shorter than minRunS: ${JSON.stringify(runs)}`);
  console.log(`  ok  a pinned-high heart rate still yields real blocks, not a stutter `
            + `(${runs.length} blocks, shortest ${Math.min(...runs, Infinity)}s)`);
}

{
  // The armband dies mid-run. This has happened to this athlete: one session lost heart rate
  // halfway through, another had none at all. Governance must fall back to the clock session he
  // came out to do, and must not freeze in whichever phase it happened to be in.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, fallbackRunS: 120, fallbackWalkS: 120 });
  let hr = 110;
  const evs = drive(b, 1500, () => { hr += ((b.phase === Phase.RUN ? 172 : 105) - hr) / 30; return hr; },
                    { hrFresh: t => t < 400 });     // band dies at 400 s
  const late = evs.filter(e => e.t > 460);
  assert.ok(late.length >= 2, `the session must keep running after the band dies: ${late.length} events`);
  assert.ok(late.every(e => e.reason === 'time'),
    `and must be on the clock: ${JSON.stringify(late.map(e => e.reason))}`);
  const durations = [];
  for (let i = 1; i < late.length; i++) durations.push(late[i].t - late[i - 1].t);
  assert.ok(durations.every(d => d === 120), `the prescribed clock, exactly: ${JSON.stringify(durations)}`);
  console.log(`  ok  a dead armband falls back to the prescribed clock (${late.length} clock transitions)`);
}

{
  // Two walk breaks in a row that never reach the floor is the body saying the RUNNING is over. It
  // is not saying the recording is over: for this athlete walking IS training, so this must move to
  // a cool-down that keeps recording -- never DONE, and never another run block -- until the athlete
  // ends the session themself.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, fallbackRunS: 120, fallbackWalkS: 120 });
  // A heart rate that recovers at first and then stops coming down -- the ratchet, in miniature.
  let hr = 110;
  const evs = drive(b, 3000, t => {
    const target = b.phase === Phase.RUN ? 175 : (t < 900 ? 105 : 145);
    hr += (target - hr) / 30;
    return hr;
  });
  assert.equal(b.phase, Phase.COOLDOWN,
    'a body that stops clearing the load keeps recording, walking, as a cool-down -- not DONE');
  const stallIdx = evs.findIndex(e => e.reason === 'not recovering');
  assert.ok(stallIdx >= 0, 'the stall that caused the cool-down must be on the record');
  assert.ok(evs.slice(stallIdx + 1).every(e => e.phase !== Phase.RUN),
    `a cool-down must never call another run block: ${JSON.stringify(evs.slice(stallIdx + 1))}`);
  const s = b.summary();
  assert.ok(s.unrecoveredWalks >= 2, `and it must be recorded why: ${JSON.stringify(s)}`);
  assert.equal(s.endedBy, 'stall',
    'the summary must say the body ended the running, not the plan or the athlete');
  console.log(`  ok  a heart rate that stops recovering moves to cool-down, not DONE `
            + `(${s.runBlocks} blocks done, ${s.unrecoveredWalks} walks unrecovered, endedBy=${s.endedBy})`);
}

{
  // What the progression judge needs beyond `runningS`: how much of the running was actually inside
  // the ceiling it was governed by. Pin heart rate at 200, far above any plausible ceiling -- the
  // worst case -- and every second of every run block must land on the "over" side, none on "under".
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, fallbackRunS: 120, fallbackWalkS: 120 });
  drive(b, 900, () => 200);
  const s = b.summary();
  assert.equal(s.runningUnderCeilingS, 0, `pinned above the ceiling must count 0 seconds under it: ${JSON.stringify(s)}`);
  assert.equal(s.runningOverCeilingS, s.runningS,
    `every running second must be over the ceiling when HR never drops below it: ${JSON.stringify(s)}`);
  console.log(`  ok  a heart rate pinned above the ceiling counts every running second as over it `
            + `(${s.runningOverCeilingS}s of ${s.runningS}s running)`);
}

{
  // A session with no armband at all is not evidence about fitness. It has to be labelled as such,
  // or the progression loop will advance or retreat a ladder on the strength of a clock.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, fallbackRunS: 60, fallbackWalkS: 60 });
  drive(b, 600, () => null, { hrFresh: () => false });
  assert.equal(b.summary().governedBy, 'clock');
  assert.equal(b.summary().hrr60Median, null, 'and it yields no autonomic measurement');
  console.log('  ok  a session run without heart rate is labelled as clock-governed, not evidence');
}

// --- against the real session ---------------------------------------------------------------------

const POLAR = '/root/.claude/uploads/59977dd4-f843-5237-9878-b2f2ff901059/'
            + '72c85e8d-Dean_Kennedy_20260905_192305.CSV';
if (existsSync(POLAR)) {
  // His own 5 September session, second by second. The prescription was 7 x (2 min run / 2 min walk)
  // with a 155 bpm ceiling; he reached 177, and spent 302 s above the ceiling at a mean pace of
  // 16:59/mi -- slower than the 12:04 he was asked for.
  //
  // Replaying a recorded heart rate through a controller that would have changed it is not a
  // simulation of what would have happened; his HR would have been lower had the blocks been called
  // differently. What it DOES establish is the direction: fed the very trace that produced a 177,
  // this controller calls a walk break at every crossing of the ceiling instead of running on. The
  // count of those crossings is the count of times the old session ran through a line it should
  // have stopped at.
  const rows = readFileSync(POLAR, 'utf8').split('\n').slice(3);
  const hr = [];
  for (const line of rows) {
    const c = line.split(',');
    if (c.length < 9 || !c[1]) continue;
    hr.push(c[2] ? Number(c[2]) : null);
  }
  assert.ok(hr.length > 1000, 'the recording must have loaded');

  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, fallbackRunS: 120, fallbackWalkS: 120,
                           warmupS: 120 });
  const calls = [];
  for (let t = 0; t < hr.length; t++) {
    const ev = b.update(t, hr[t], { hrFresh: hr[t] != null });
    if (ev) calls.push({ t, phase: ev.phase, reason: ev.reason });
  }
  b.finish(hr.length - 1);
  const toWalk = calls.filter(c => c.phase === Phase.WALK && c.reason === 'ceiling');
  assert.ok(toWalk.length > 0,
    'his own trace crosses the ceiling; the controller must call a walk break each time');
  const over = hr.filter(h => h != null && h > CEIL).length;
  console.log(`  ok  replayed on the 5 Sep recording: ${toWalk.length} ceiling crossings would each `
            + `have ended a block (that session ran on through them for ${over}s above ${CEIL})`);
} else {
  console.log('  --  skipped the recorded-session replay (the Polar export is not on this machine)');
}

console.log('\nAll hr-blocks tests passed.');
