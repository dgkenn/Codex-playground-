// The JS readiness port against vectors exported from the Python engine (authoritative).
// Regenerate with: python3 tests/gen_readiness_vectors.py

import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { dailyReadiness, cleanIntervals, rmssd, summariseCheck } from '../readiness.js';

const V = JSON.parse(readFileSync(new URL('./readiness_vectors.json', import.meta.url), 'utf8'));

let n = 0;
for (const [i, c] of V.cases.entries()) {
  const r = dailyReadiness(c.nights);
  const e = c.expect;
  const where = `case ${i}`;
  assert.equal(r.band, e.band, `${where}: band`);
  assert.equal(r.action, e.action, `${where}: action`);
  assert.equal(r.score, e.score, `${where}: score`);
  assert.equal(r.hrvStatus, e.hrvStatus, `${where}: HRV status`);
  assert.equal(r.override, e.override, `${where}: override`);
  assert.equal(r.baseline ? r.baseline.n : null, e.baselineN, `${where}: baseline size`);
  if (e.rollingLn == null) assert.equal(r.rollingLn, null);
  else assert.ok(Math.abs(r.rollingLn - e.rollingLn) < 1e-9, `${where}: rolling mean`);
  assert.deepEqual(r.flags.map(f => f.flag).sort(), e.flags, `${where}: flags`);
  n += 1;
}
console.log(`  ok  ${n} readiness histories agree with the engine (bands ${[...new Set(V.cases.map(c => c.expect.band))].join(', ')})`);

{
  const b = V.beats;
  const { clean, counts } = cleanIntervals(b.intervals, { blockers: b.blockers });
  assert.deepEqual(counts, b.counts);
  assert.ok(Math.abs(rmssd(clean) - b.rmssd) < 1e-9);
  console.log(`  ok  beat cleaning and RMSSD agree (${counts.kept}/${counts.total} kept)`);
}

{
  // A check: the first minute is settling and is not used; movement-flagged beats are dropped.
  const beats = [];
  for (let i = 0; i < 380; i++) beats.push({ ppiMs: i % 2 ? 1020 : 980, errMs: 4, blocker: i === 200 });
  const s = summariseCheck(beats);
  assert.equal(s.restingHr, 60);
  assert.ok(Math.abs(s.hrvMs - 40) < 0.3, `RMSSD ${s.hrvMs}`);   // the dropped beat joins two equal intervals
  assert.ok(s.cleanCount >= 300 && s.counts.blocker === 1, JSON.stringify(s.counts));
  console.log(`  ok  a morning check: resting ${s.restingHr} bpm, RMSSD ${s.hrvMs} ms, settling minute left out`);
}

console.log('\nAll readiness parity tests passed.');
