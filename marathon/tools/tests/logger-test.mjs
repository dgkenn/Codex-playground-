// Runs verity-logger.html's script in a stubbed DOM to test the parts that do not need a radio.
//
// The Bluetooth connection cannot be tested here. Everything that decides what lands in the file
// can be, and that is where the damage happens: a logger that fabricates data is worse than one
// that fails to connect, because the failure to connect is obvious and the fabrication is not.

import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../verity-logger.html', import.meta.url), 'utf8');
const js = html.match(/<script>([\s\S]*)<\/script>/)[1];

function makeEnv() {
  const els = new Map();
  const el = id => {
    if (!els.has(id)) els.set(id, {
      id, textContent: '', innerHTML: '', style: {}, value: '', disabled: false,
      classList: { add() {}, remove() {}, contains: () => false },
      querySelector: () => ({ insertRow: () => ({ insertCell: () => ({}) }) }),
      appendChild() {}, dataset: {},
    });
    return els.get(id);
  };
  const env = {
    document: {
      getElementById: el,
      addEventListener() {},
      querySelectorAll: () => [],
      createElement: () => el('tmp'),
      hidden: false,
    },
    navigator: { bluetooth: {} },
    setInterval: () => 0,
    setTimeout: (fn) => 0,
    Blob: class {}, URL: { createObjectURL: () => '', revokeObjectURL() {} },
  };
  return { env, el };
}

const { env } = makeEnv();
const fn = new Function(...Object.keys(env), js + '\n;return { state, tick, STALE_HR_MS };');
const api = fn(...Object.values(env));

// ---------------------------------------------------------------------------------------------

function drive({ hrSeconds, gapSeconds, thenSeconds }) {
  const { state, tick, STALE_HR_MS } = api;
  state.perSecond.clear();
  state.recording = true;
  state.gaps = 0;
  state.gapOpen = false;
  state.label = 'stage_1';
  let now = 1_000_000;
  state.startedAt = now;
  const origNow = Date.now;
  Date.now = () => now;

  for (let i = 0; i < hrSeconds; i++) {
    state.hr = 140; state.hrAt = now;
    tick(); now += 1000;
  }
  for (let i = 0; i < gapSeconds; i++) { tick(); now += 1000; }   // no new hrAt: out of range
  for (let i = 0; i < thenSeconds; i++) {
    state.hr = 145; state.hrAt = now;
    tick(); now += 1000;
  }
  Date.now = origNow;
  return [...state.perSecond.values()];
}

// --- the bug this file exists for ---------------------------------------------------------------

{
  const samples = drive({ hrSeconds: 60, gapSeconds: 120, thenSeconds: 60 });
  const stale = Math.ceil(api.STALE_HR_MS / 1000);

  // A repeated last value would give 240 samples with a flat plateau in the middle. A gap gives
  // roughly 120 + the few seconds before the staleness threshold trips.
  assert.ok(samples.length < 140,
    `wrote ${samples.length} samples across a 120 s dropout — the last value is being repeated`);
  assert.ok(samples.length >= 120,
    `wrote only ${samples.length}; the good seconds should still be there`);

  const times = samples.map(s => s.t_s);
  const gaps = times.slice(1).map((t, i) => t - times[i]).filter(d => d > 1);
  assert.equal(gaps.length, 1, 'expected exactly one gap in the timeline');
  assert.ok(gaps[0] > 110, `gap was only ${gaps[0]} s, expected ~120`);

  // And nothing inside the gap claims a heart rate.
  const inGap = samples.filter(s => s.t_s > 60 + stale && s.t_s < 180);
  assert.equal(inGap.length, 0, 'samples were written during the dropout');
  console.log(`  ok  dropout leaves a real gap (${samples.length} samples, ${gaps[0]}s missing)`);
}

{
  const samples = drive({ hrSeconds: 300, gapSeconds: 0, thenSeconds: 0 });
  assert.equal(samples.length, 300, 'a clean run should write every second');
  assert.ok(samples.every(s => s.hr_bpm === 140));
  assert.ok(samples.every(s => s.speed_m_s !== null), 'stage label should supply a speed');
  console.log('  ok  a clean run writes every second, with speed from the stage label');
}

{
  // Recovery: the seconds after the band comes back must be present and correct.
  const samples = drive({ hrSeconds: 30, gapSeconds: 60, thenSeconds: 30 });
  const after = samples.filter(s => s.t_s >= 90);
  assert.ok(after.length >= 28, `only ${after.length} samples after reconnect`);
  assert.ok(after.every(s => s.hr_bpm === 145), 'post-gap samples carry the new value');
  console.log('  ok  recording resumes correctly after the signal returns');
}

console.log('\nAll logger tests passed.');
