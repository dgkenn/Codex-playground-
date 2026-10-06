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
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120 });
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
  assert.ok(s.toFloorMedianS > 0, 'and each walk must yield a recovery measurement');
  console.log(`  ok  ceiling ends the run, floor ends the walk `
            + `(${s.runBlocks} blocks, ${s.runningS}s running, ${s.toFloorMedianS}s ceiling-to-floor)`);
}

{
  // Heart rate lags, so the first seconds of a block report the block before it. Without a floor on
  // block length a session that opens with an elevated heart rate collapses into run-two-seconds,
  // walk-two-seconds -- not a workout, and the kind of thing that makes an athlete stop trusting
  // the app entirely.
  // Pinned just AT the ceiling, which is the case the floor is for: a block that drifts up to the
  // line, where the first seconds are still reporting the walk that preceded it. (Pinned far OVER
  // the line is a different question and is the next case.)
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120 });
  const evs = drive(b, 900, () => CEIL + 2);
  const runs = [];
  let last = null;
  for (const e of evs) {
    if (e.previous === Phase.RUN && last != null) runs.push(e.t - last);
    if (e.phase === Phase.RUN) last = e.t;
  }
  assert.ok(runs.every(d => d >= 30), `no block may be shorter than minRunS: ${JSON.stringify(runs)}`);
  console.log(`  ok  a heart rate sitting at the ceiling still yields real blocks, not a stutter `
            + `(${runs.length} blocks, shortest ${Math.min(...runs, Infinity)}s)`);
}

{
  // Far over the ceiling is not a lag artefact and must not be waited out. At fifteen beats over,
  // thirty seconds of grace is another ten beats -- and this athlete's recorded session reached 177
  // against a 155 ceiling, which is the number this exists to cut short.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120 });
  const evs = drive(b, 600, () => 200);         // 50 over: unambiguous
  const first = evs.find(e => e.previous === Phase.RUN);
  assert.ok(first, 'a run block must have been ended');
  assert.equal(first.reason, 'well over the ceiling',
    `far over the ceiling must cut the block on its own reason, not wait out minRunS: ${first.reason}`);
  const started = evs.find(e => e.phase === Phase.RUN);
  assert.ok(first.t - started.t < 30,
    `and it must not have waited the full floor: ${first.t - started.t}s`);
  console.log(`  ok  a heart rate far over the ceiling ends the block immediately `
            + `(${first.t - started.t}s, "${first.reason}")`);
}

{
  // The cap must not block the gate the whole phase exists to reach. FOUNDATION's exit is "run 30
  // minutes continuously, comfortably, in Z2", and the ladder's top rung is 30 min x 1 -- so a cap
  // that forced a walk at fifteen minutes made that gate unreachable under heart-rate governance
  // however easy the running felt.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 1800, walkS: 120 });
  drive(b, 2400, () => CEIL - 20);              // comfortably under the ceiling throughout
  b.finish(2400);                               // the block is still open; summary counts closed ones
  const s = b.summary();
  assert.ok(s.longestRunBlockS >= 1800,
    `30 continuous minutes under the ceiling must be possible: longest was ${s.longestRunBlockS}s`);
  console.log(`  ok  a comfortable 30-minute block is not cut short by the cap `
            + `(${Math.round(s.longestRunBlockS / 60)} min continuous)`);
}

{
  // The armband dies mid-run. This has happened to this athlete: one session lost heart rate
  // halfway through, another had none at all. Governance must fall back to the clock session he
  // came out to do, and must not freeze in whichever phase it happened to be in.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120 });
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
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120 });
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
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120 });
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
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 60, walkS: 60 });
  drive(b, 600, () => null, { hrFresh: () => false });
  assert.equal(b.summary().governedBy, 'clock');
  assert.equal(b.summary().hrr60Median, null, 'and it yields no autonomic measurement');
  console.log('  ok  a session run without heart rate is labelled as clock-governed, not evidence');
}

{
  // The failure that made this a two-rail controller. With heart rate sitting at 142 -- comfortably
  // under a 150 ceiling -- the first version called "run" at warm-up and did not call a walk for
  // fourteen minutes, because only the ceiling could end a block. Heart rate protects the heart, not
  // the tendon: the rung's block length ends the block, and under the ceiling it ends it on time.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120, reps: 7 });
  const evs = drive(b, 600, () => 142);
  const start = evs.find(e => e.phase === Phase.RUN);
  const end = evs.find(e => e.previous === Phase.RUN);
  assert.ok(end, 'a block held under the ceiling must still end');
  assert.equal(end.reason, 'full', `and say that it ran its full length: ${end.reason}`);
  assert.equal(end.t - start.t, 120, `at the rung's length, not later: ${end.t - start.t}s`);
  assert.equal(end.phase, Phase.WALK);
  console.log(`  ok  heart rate held under the ceiling ends the block at the rung's length (${end.t - start.t}s, "${end.reason}")`);
}

{
  // Either limit may shorten a block, neither may lengthen one. Blocks: one that runs to its full
  // length, then one the heart rate cuts. The summary must tell the judge which was which.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120, reps: 2 });
  let hr = 110;
  let runs = 0, prev = Phase.WARMUP;
  drive(b, 1200, () => {
    if (b.phase === Phase.RUN && prev !== Phase.RUN) runs += 1;
    prev = b.phase;
    // Block one stays low; block two climbs through the ceiling.
    const target = b.phase === Phase.RUN ? (runs === 1 ? 140 : 175) : 100;
    hr += (target - hr) / 15;
    return hr;
  });
  const s = b.summary();
  assert.equal(s.blocksPlanned, 2);
  assert.equal(s.blocksFull, 1, `one block ran full length: ${JSON.stringify(s)}`);
  assert.equal(s.blocksCut, 1, `one was cut by the heart rate: ${JSON.stringify(s)}`);
  assert.equal(s.runBlockTargetS, 120);
  assert.ok(s.longestRunBlockS <= 120, `no block may exceed the rung's length: ${s.longestRunBlockS}`);
  assert.ok(s.toCeilingMedianS > 0 && s.toCeilingMedianS < 120,
    `time to the ceiling is the cut block's length: ${s.toCeilingMedianS}`);
  console.log(`  ok  the summary separates full blocks from blocks the heart rate cut (${s.blocksFull} full, ${s.blocksCut} cut)`);
}

{
  // The session is the rung's block count and no more: the last block's end is a cool-down whose
  // reason is 'reps', whether that block ran full or was cut. Missed volume is not carried forward.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 60, walkS: 60, reps: 3 });
  let hr = 110;
  const evs = drive(b, 3600, () => {
    hr += ((b.phase === Phase.RUN ? 140 : 100) - hr) / 15;
    return hr;
  });
  const s = b.summary();
  assert.equal(b.phase, Phase.COOLDOWN, 'the last block ends in a cool-down, not DONE');
  assert.equal(s.endedBy, 'reps');
  assert.equal(s.runBlocks, 3, `exactly the planned blocks: ${s.runBlocks}`);
  assert.equal(evs.filter(e => e.phase === Phase.RUN).length, 3);
  const last = evs.findIndex(e => e.reason === 'blocks done');
  assert.ok(last >= 0 && evs.slice(last + 1).every(e => e.phase !== Phase.RUN),
    'a cool-down must never call another run block');
  console.log(`  ok  the last planned block moves to cool-down, endedBy=reps (${s.runBlocks} blocks)`);
}

{
  // A walk is expected to last walkS and may be extended by walkExtraS while heart rate is still
  // above the floor -- no more. Pinned above the floor the whole time, so no walk can recover.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 60, walkS: 100, reps: 5 });
  const evs = drive(b, 2000, () => (b.phase === Phase.RUN ? 140 : 140));
  const walkEnds = evs.filter(e => e.previous === Phase.WALK);
  assert.ok(walkEnds.length >= 1, 'a walk that never recovers must still end');
  const startOfFirstWalk = evs.find(e => e.phase === Phase.WALK).t;
  assert.equal(walkEnds[0].t - startOfFirstWalk, 100 + 90,
    `the cap is the plan's walk plus the extension: ${walkEnds[0].t - startOfFirstWalk}s`);
  assert.equal(walkEnds[0].reason, 'going again');
  console.log('  ok  a walk that never reaches the floor ends at the plan\'s walk + 90 s');
}

{
  // A walk that does reach the floor ends then, and not before the minimum.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 60, walkS: 120, reps: 5 });
  const evs = drive(b, 1200, () => (b.phase === Phase.RUN ? 140 : 110));
  const w = evs.find(e => e.phase === Phase.WALK && e.previous === Phase.RUN);
  const r = evs.find(e => e.previous === Phase.WALK && e.t > w.t);
  assert.equal(r.reason, 'recovered');
  assert.equal(r.t - w.t, 45, `recovered walks end at the minimum, not the prescription: ${r.t - w.t}s`);
  console.log('  ok  a walk that recovers quickly ends at HR recovery, not the clock');
}

{
  // The warm-up is the plan's five minutes, whatever heart rate says. On 6 October it ended at 45 s
  // because a resting heart rate is already under the floor, and the first block went 103 -> 152 in
  // 85 seconds.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120, reps: 7 });
  const evs = drive(b, 400, () => 100);
  const first = evs.find(e => e.phase === Phase.RUN);
  assert.equal(first.t, 300, `the first block starts after the five-minute warm-up: ${first.t}s`);
  // Without an armband the same five minutes, not the walk length.
  const c = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120, reps: 7 });
  const ev2 = drive(c, 400, () => null, { hrFresh: () => false });
  assert.equal(ev2.find(e => e.phase === Phase.RUN).t, 300);
  console.log('  ok  the warm-up is the plan\'s five minutes even when heart rate is already low');
}

{
  // Recovery, measured the way 6 October showed it has to be. Heart rate keeps CLIMBING for ~20 s
  // after a block ends, and a walk can end inside a minute -- the old HRR60 read the peak at the
  // block's end and the heart rate 60 s later, which by then was usually the next run. Median: 8.
  //   - a short walk yields ceiling-to-floor seconds and NO HRR60 (it did not last long enough);
  //   - a long one yields both, HRR60 measured from the walk's own (later) peak.
  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 60, walkS: 60, reps: 3 });
  let walkT = null;
  drive(b, 2400, (t, phase) => {
    if (phase !== Phase.WALK && phase !== Phase.COOLDOWN) { walkT = null; return phase === Phase.RUN ? 140 : 110; }
    if (walkT == null) walkT = t;
    const w = t - walkT;
    // +8 bpm over 20 s, then down 0.5 bpm/s: reaches the floor (125) at ~66 s.
    return w < 20 ? 140 + w * 0.4 : 148 - (w - 20) * 0.5;
  });
  b.finish(2400);
  const r = b.recoveries;
  assert.equal(r.length, 3, `one recovery per block: ${JSON.stringify(r)}`);
  for (const x of r.slice(0, 2)) {
    assert.ok(Math.abs(x.toFloorS - 66) <= 2, `ceiling to floor in ~66 s: ${JSON.stringify(x)}`);
    assert.equal(x.hrr60, null, `a walk that ended at the floor before peak+60 has no HRR60: ${JSON.stringify(x)}`);
    assert.ok(x.peakHr >= 147, `the peak is the walk's own, after the lag: ${x.peakHr}`);
  }
  const last = r[2];                                  // the cool-down: long enough for both
  assert.ok(Math.abs(last.hrr60 - 30) <= 1, `HRR60 from the walk's own peak: ${JSON.stringify(last)}`);
  assert.ok(Math.abs(b.summary().toFloorMedianS - 66) <= 2);
  console.log(`  ok  recovery is ceiling-to-floor time, and HRR60 only when the walk lasted (${JSON.stringify(last)})`);
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

  const b = new HrBlocks({ ceilingBpm: CEIL, floorBpm: FLOOR, runBlockS: 120, walkS: 120,
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
