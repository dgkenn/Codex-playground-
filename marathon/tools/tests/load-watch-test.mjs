// The JS port checked against the Python it was ported from, not against itself.
//
// Both of these have a reference implementation in the engine (load.acwr, progress.pain_trend) with
// its own suite. The risk in a port is not that the arithmetic is wrong -- it is that a rule ORDER
// or a threshold quietly diverges, and then the phone and the laptop disagree about whether an
// athlete should be running. So the cases here are chosen to pin the boundaries and the precedence.

import assert from 'node:assert/strict';
import {
  acwr, ewmaLoad, dailyLoadSeries, painTrend, painHolds,
  ACUTE_DAYS, CHRONIC_DAYS, ACWR_SWEET_LOW, ACWR_SWEET_HIGH, ACWR_HARD_CAP,
} from '../load-watch.js';

// --- load -----------------------------------------------------------------------------------------

{
  // Constants must match the engine's. A divergence here is a silent disagreement about training.
  assert.equal(ACUTE_DAYS, 7);
  assert.equal(CHRONIC_DAYS, 28);
  assert.equal(ACWR_SWEET_LOW, 0.80);
  assert.equal(ACWR_SWEET_HIGH, 1.30);
  assert.equal(ACWR_HARD_CAP, 1.50);
  console.log('  ok  the thresholds match the engine');
}

{
  assert.equal(ewmaLoad([], 7), 0);
  assert.equal(ewmaLoad([10], 7), 10);
  // Steady input converges to that input.
  assert.ok(Math.abs(ewmaLoad(Array(60).fill(50), 7) - 50) < 0.01);
  assert.throws(() => ewmaLoad([1], 0), /positive/);
  console.log('  ok  the EWMA behaves');
}

{
  // A brand-new runner. Chronic load starts at zero, so the ratio explodes on the first easy jog --
  // this is the documented failure of applying ACWR to beginners, and it is exactly the situation
  // this athlete is in. It must refuse to answer rather than reporting "danger" on session one.
  const r = acwr(dailyLoadSeries([{ at: '2026-09-05', trimp: 60 }], { asOf: new Date('2026-09-06'), days: 10 }));
  assert.equal(r.band, 'insufficient_history',
    `a first session must not be graded: ${JSON.stringify(r)}`);
  assert.match(r.note, /not meaningful yet/);
  console.log(`  ok  a new runner's first session is not graded (${r.days} days of history)`);
}

{
  // Rest days are the point. A three-run week with the zeros omitted looks like a seven-run week.
  const sessions = [];
  const base = new Date('2026-06-01');
  for (let i = 0; i < 60; i += 2) {                       // every other day
    const d = new Date(base); d.setDate(d.getDate() + i);
    sessions.push({ at: d.toISOString(), trimp: 70 });
  }
  const withZeros = dailyLoadSeries(sessions, { asOf: new Date('2026-07-31'), days: 56 });
  assert.equal(withZeros.length, 56);
  assert.ok(withZeros.filter(x => x === 0).length > 20, 'rest days must be present as zeros');
  const r = acwr(withZeros);
  assert.equal(r.band, 'optimal', `a metronome-steady history is optimal: ${JSON.stringify(r)}`);
  // And the lie: same sessions, zeros dropped.
  const noZeros = withZeros.filter(x => x > 0);
  assert.notEqual(acwr(noZeros).chronic, r.chronic,
    'dropping rest days must change the answer, which is why it is not allowed');
  console.log(`  ok  a steady history reads optimal (ratio ${r.ratio.toFixed(2)}), and dropping `
            + 'rest days changes it');
}

{
  // A spike week against a settled month.
  const days = Array(56).fill(0).map((_, i) => (i % 2 === 0 ? 60 : 0));
  for (let i = 49; i < 56; i++) days[i] = 200;            // last week, every day, hard
  const r = acwr(days);
  assert.ok(r.ratio > ACWR_HARD_CAP, `a spike week must show as one: ${r.ratio.toFixed(2)}`);
  assert.equal(r.band, 'danger');
  console.log(`  ok  a spike week reads danger (ratio ${r.ratio.toFixed(2)})`);
}

// --- pain -----------------------------------------------------------------------------------------

const on = (d, extra = {}) => ({ day: d, site: 'left_shin', level: 2, timing: 'after_run',
                                 focal: false, worsensDuringRun: false, ...extra });

{
  assert.deepEqual(painTrend([]), []);
  assert.deepEqual(painTrend(null), []);
  console.log('  ok  an empty log says nothing');
}

{
  // Focal outranks everything, including a low score. This is the rule that matters most for this
  // athlete: 180 lb, inside the first twenty weeks of running, and bone shows up in none of the
  // heart-rate measures that govern the rest of the plan.
  const t = painTrend([on('2026-09-01', { level: 1, focal: true })]);
  assert.equal(t[0].verdict, 'urgent',
    `a 1/10 focal pain must still be urgent: ${JSON.stringify(t[0])}`);
  assert.match(t[0].message, /stress injury/);
  console.log('  ok  focal bone tenderness is urgent even at 1/10');
}

{
  const t = painTrend([on('2026-09-01', { level: 6 })]);
  assert.equal(t[0].verdict, 'stop_and_assess', 'above 5/10 the rule is stop');
  const ok = painTrend([on('2026-09-01', { level: 5 })]);
  assert.equal(ok[0].verdict, 'watch', 'and 5/10 exactly is the boundary, not over it');
  console.log('  ok  the 5/10 boundary is where the engine puts it');
}

{
  // Next-morning pain: the most informative signal in overuse injury and the most often dismissed,
  // because by the time you run again it has eased off.
  const t = painTrend([on('2026-09-01', { level: 2, timing: 'next_morning' })]);
  assert.equal(t[0].verdict, 'hold_volume');
  assert.match(t[0].message, /morning after/);
  console.log('  ok  one 2/10 that is still there next morning holds the volume');
}

{
  // Three times in a fortnight is a pattern.
  const t = painTrend([on('2026-09-01'), on('2026-09-04'), on('2026-09-08')]);
  assert.equal(t[0].verdict, 'hold_volume');
  assert.match(t[0].message, /3 times/);
  // Twice is not.
  assert.equal(painTrend([on('2026-09-01'), on('2026-09-04')])[0].verdict, 'watch');
  console.log('  ok  three entries in a fortnight is a pattern, two is a niggle');
}

{
  // Ordering: most serious first, because the athlete reads the top line.
  const t = painTrend([
    on('2026-09-01', { site: 'right_calf', level: 1 }),
    on('2026-09-02', { site: 'left_shin', level: 1, focal: true }),
    on('2026-09-03', { site: 'left_knee', level: 2, timing: 'next_morning' }),
  ]);
  assert.deepEqual(t.map(x => x.verdict), ['urgent', 'hold_volume', 'watch']);
  console.log('  ok  the most serious site is reported first');
}

{
  // Outside the fortnight is history, not a pattern.
  const t = painTrend([on('2026-08-01'), on('2026-08-03'), on('2026-08-05'), on('2026-09-10')],
                      { asOf: '2026-09-10' });
  assert.equal(t.length, 1);
  assert.equal(t[0].entries, 1, 'entries older than the window must not count toward escalation');
  console.log('  ok  the window is a fortnight, and older entries fall out of it');
}

{
  // The one line the progression loop actually consumes.
  assert.equal(painHolds([]), null);
  assert.equal(painHolds(painTrend([on('2026-09-01', { level: 1 })])), null,
    'a mild one-off must not hold the plan');
  const hold = painHolds(painTrend([on('2026-09-01', { level: 2, timing: 'next_morning' })]));
  assert.equal(hold.hold, true);
  assert.equal(hold.stop, false, 'a pattern holds the ladder; it does not stop the running');
  const stop = painHolds(painTrend([on('2026-09-01', { level: 2, focal: true })]));
  assert.equal(stop.stop, true, 'focal pain stops it');
  console.log('  ok  a pattern holds the ladder, focal pain stops the running');
}

console.log('\nAll load-watch tests passed.');
