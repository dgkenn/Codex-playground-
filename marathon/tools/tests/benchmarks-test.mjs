// Benchmarks: the time trial's two numbers, when it is due, spotting the 5K, and the projection.

import assert from 'node:assert/strict';
import { riegel, measuredMaxHr, trialDue, longestContinuous, projectGoal, TRIAL_EVERY_DAYS,
         summariseTrial } from '../benchmarks.js';
import { stepLadder } from '../progression.js';

{
  // Riegel: 2 km in 12:00 predicts a 5K in about 31:42 (720 x 2.5^1.06).
  const t = riegel(720, 2000, 5000);
  assert.ok(Math.abs(t - 1902) < 2, `${t}`);
  console.log(`  ok  a 12:00 2 km predicts a ${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, '0')} 5K`);
}

{
  // The measured maximum is the highest trial peak; sessions that were not trials do not count.
  assert.equal(measuredMaxHr([]), null);
  assert.equal(measuredMaxHr([{ kind: 'trial', peakHr: 191 }, { kind: 'trial', peakHr: 194 }, { kind: 'goal', peakHr: 199 }]), 194);
  console.log('  ok  the measured maximum is the highest time-trial peak');
}

{
  const now = new Date('2026-11-10T12:00:00Z');
  assert.equal(trialDue({ runMin: 8, now }).due, false, 'not before 10-minute blocks');
  assert.equal(trialDue({ runMin: 10, now }).due, true, 'first one at 10-minute blocks');
  const recent = [{ kind: 'trial', at: '2026-11-01T12:00:00Z' }];
  assert.equal(trialDue({ runMin: 15, benchmarks: recent, now }).due, false);
  const later = new Date(Date.parse('2026-11-01T12:00:00Z') + (TRIAL_EVERY_DAYS + 1) * 86400000);
  assert.equal(trialDue({ runMin: 15, benchmarks: recent, now: later }).due, true);
  console.log('  ok  the trial is due at 10-minute blocks, then every three weeks');
}

{
  // A run block of 36 minutes at 2.3 m/s is 4.97 km; one at 37 minutes passes 5 km. Walks break it.
  const samples = [];
  let t = 0;
  for (let i = 0; i < 300; i++) samples.push({ t_s: t++, speed_m_s: 1.5, label: 'walk' });
  for (let i = 0; i < 37 * 60; i++) samples.push({ t_s: t++, speed_m_s: 2.3, label: 'run' });
  for (let i = 0; i < 60; i++) samples.push({ t_s: t++, speed_m_s: 1.4, label: 'walk' });
  const c = longestContinuous(samples);
  assert.ok(c.m > 5000 && c.m < 5150, `${c.m}`);
  assert.ok(Math.abs(c.s - 37 * 60) <= 1);
  const broken = samples.map((x, i) => (i === 1500 ? { ...x, label: 'walk' } : x));
  assert.ok(longestContinuous(broken).m < 5000, 'a walk in the middle breaks it');
  console.log(`  ok  the first continuous 5K is spotted inside a run (${Math.round(c.m)} m in ${Math.round(c.s / 60)} min)`);
}

{
  // From 2 min x 7, a run every other day: the fast track's date is weeks before the steady one's.
  const totals = [8, 14, 18, 20, 20, 24, 24, 30, 30, 30, 35, 40];
  const now = new Date('2026-10-26T12:00:00Z');
  const p = projectGoal({ step: stepLadder, state: { rung: 1, qualifying: 0, changedAt: '2026-10-22T12:00:00Z' },
                          totalsMin: totals, longestRecentS: 14 * 60, now });
  const days = iso => Math.round((new Date(iso) - now) / 86400000);
  assert.ok(days(p.green) >= 21 && days(p.green) <= 35, `green ${days(p.green)} days`);
  assert.ok(days(p.amber) > days(p.green) * 1.8, `amber ${days(p.amber)} days`);
  console.log(`  ok  projected 5K step: ${days(p.green)} days all green, ${days(p.amber)} on the steady track`);
}

{
  // A trial at 2.8 m/s: 2000 m is crossed at 714.3 s; heart rate climbing to 188.
  const ticks = [], samples = [];
  for (let t = 0; t <= 760; t++) { ticks.push([t, 2.8 * t]); samples.push({ t_s: t, hr_bpm: Math.min(188, 120 + t / 10) }); }
  const r = summariseTrial(ticks, samples);
  assert.equal(r.timeS, 714);
  assert.equal(r.peakHr, 188);
  assert.ok(r.predicted5kS > 1880 && r.predicted5kS < 1900, `${r.predicted5kS}`);
  assert.equal(summariseTrial(ticks.slice(0, 600), samples), null, 'stopped short: no result');
  console.log('  ok  a trial is timed where it crossed 2 km, with its peak heart rate and a predicted 5K');
}

console.log('\nAll benchmark tests passed.');
