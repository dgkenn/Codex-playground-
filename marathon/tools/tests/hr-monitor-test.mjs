// The heart-rate channel. The lead compensation is the whole point, so most of these check that it
// anticipates rather than reacts — a controller that waits for heart rate to arrive is one that
// oscillates.

import assert from 'node:assert/strict';
import { HrCeilingMonitor } from '../hr-monitor.js';

// Z2 for this athlete on current estimates: 134-151 bpm.
const BAND = { lowBpm: 134, highBpm: 151 };

function drive(m, series, { start = 0 } = {}) {
  const out = [];
  series.forEach((hr, i) => { const e = m.update(start + i, hr); if (e) out.push(e); });
  return out;
}

/** First-order approach to a steady value, the way a heart actually responds. */
function approach(from, to, seconds, tau = 45) {
  const out = [];
  let hr = from;
  for (let i = 0; i < seconds; i++) { hr += (to - hr) * (1 - Math.exp(-1 / tau)); out.push(hr); }
  return out;
}

{
  const m = new HrCeilingMonitor(BAND);
  assert.equal(drive(m, Array(600).fill(145)).length, 0, 'a steady in-zone heart rate said something');
  console.log('  ok  sitting inside the zone is silent');
}
{
  const m = new HrCeilingMonitor(BAND);
  assert.equal(drive(m, Array(600).fill(120)).length, 0);
  console.log('  ok  ceiling-only stays silent when you are easy');
}
{
  const m = new HrCeilingMonitor(BAND);
  assert.equal(drive(m, Array(400).fill(153)).length, 0, 'fired inside the deadband');
  console.log('  ok  a couple of bpm over the ceiling is not an excursion');
}
{
  const m = new HrCeilingMonitor(BAND);
  const series = [...Array(60).fill(145), ...Array(10).fill(170), ...Array(120).fill(145)];
  assert.equal(drive(m, series).length, 0, 'a ten-second spike was reported');
  console.log('  ok  a spike shorter than the confirmation window is ignored');
}

{
  const m = new HrCeilingMonitor(BAND);
  const series = approach(140, 185, 300);
  const ev = drive(m, series);
  assert.ok(ev.length, 'never warned about a heart rate climbing far past the ceiling');
  const hrThen = series[Math.round(ev[0].tS)];
  assert.ok(hrThen < 165, `warned at ${hrThen.toFixed(0)} bpm — reacting, not anticipating`);
  assert.ok(ev[0].hrSteadyState > hrThen + 5, 'the projection should lead the reading');
  console.log(`  ok  warns at ${hrThen.toFixed(0)} bpm while heading for `
              + `${ev[0].hrSteadyState.toFixed(0)} — anticipation, not reaction`);
}
{
  const m = new HrCeilingMonitor(BAND);
  assert.equal(drive(m, approach(180, 140, 240)).length, 0, 'nagged someone already recovering');
  console.log('  ok  a high but falling heart rate is left alone');
}

{
  const m = new HrCeilingMonitor(BAND);
  const ev = drive(m, Array(1200).fill(178));
  assert.ok(ev.length <= 5, `${ev.length} tones in 20 minutes of being ignored`);
  // No reminder may arrive before the correction could have shown up: heart rate's time constant is
  // 45 s, so anything tighter is telling you about a problem you may already have fixed.
  const firstGap = ev.length > 1 ? ev[1].tS - ev[0].tS : Infinity;
  assert.ok(firstGap >= 45, `reminded after ${firstGap}s, inside heart rate's own time constant`);
  const gaps = ev.slice(1).map((e, i) => e.tS - ev[i].tS);
  assert.ok(gaps.every((g, i) => i === 0 || g >= gaps[i - 1]), `gaps should grow: ${gaps}`);
  console.log(`  ok  twenty minutes over the ceiling earns ${ev.length} tones, spaced out`);
}
{
  const m = new HrCeilingMonitor(BAND);
  const ev = drive(m, [...approach(140, 180, 200), ...approach(180, 143, 200)]);
  assert.ok(ev.some(e => e.earcon === 'ease'), 'never warned');
  assert.equal(ev.filter(e => e.earcon === 'in_band').length, 1,
    'the return to zone should be acknowledged once');
  assert.equal(ev[ev.length - 1].earcon, 'in_band', 'the acknowledgement should end the sequence');
  console.log('  ok  easing off is acknowledged once and ends the sequence');
}

{
  const m = new HrCeilingMonitor(BAND);
  drive(m, Array(60).fill(145));
  const ev = drive(m, Array(120).fill(null), { start: 60 });
  assert.equal(ev.length, 1, 'losing heart rate should be said once, then silence');
  assert.equal(ev[0].earcon, 'degraded');
  console.log('  ok  losing the signal is announced once');
}
{
  const m = new HrCeilingMonitor(BAND);
  drive(m, approach(140, 180, 100));
  drive(m, Array(30).fill(null), { start: 100 });
  const ev = drive(m, Array(60).fill(145), { start: 130 });
  assert.ok(!ev.some(e => e.earcon === 'ease'),
    'a gap left stale history that produced a phantom warning');
  console.log('  ok  a gap clears the history rather than leaving stale slope');
}

{
  const m = new HrCeilingMonitor({ lowBpm: 162, highBpm: 174, ceilingOnly: false });
  assert.ok(drive(m, Array(300).fill(140)).some(e => e.earcon === 'lift'),
    'a tempo run below its zone said nothing');
  console.log('  ok  a two-sided band asks you to lift');
}

console.log('\nAll heart-rate monitor tests passed.');
