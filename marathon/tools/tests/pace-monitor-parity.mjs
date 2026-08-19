// The JS port against the same golden vectors as Python (authoritative) and Swift.
//
// Three implementations, one set of traces. A port that merely looks right is how two channels
// drift apart, and the runner would never know which one was lying to them.

import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { PaceBandMonitor, gradeAdjustedPaceFactor } from '../pace-monitor.js';

const vectors = JSON.parse(readFileSync(
  new URL('../../ios/MarathonCoach/Resources/golden_vectors.json', import.meta.url), 'utf8'));

const T = 520.0;
const rep = (v, n) => Array.from({ length: n }, () => v);

// Same inputs the Python exporter used. Held here rather than in the fixture on purpose: a fixture
// carrying its own inputs could drift from the generator with nothing failing.
const INPUTS = {
  even_pace_silent:          [rep(T, 300), rep(0, 300)],
  too_fast_then_corrects:    [[...rep(T * 0.85, 120), ...rep(T, 180)], rep(0, 300)],
  too_slow_lift:             [rep(T * 1.20, 300), rep(0, 300)],
  ceiling_only_ignores_slow: [rep(T * 1.35, 300), rep(0, 300)],
  ceiling_only_still_eases:  [rep(T * 0.80, 300), rep(0, 300)],
  far_out_repeats:           [rep(T * 0.70, 600), rep(0, 600)],
  climb_moves_the_band:      [rep(T * gradeAdjustedPaceFactor(0.06), 300), rep(0.06, 300)],
  boundary_chatter:          [Array.from({ length: 600 }, (_, i) => T * (i % 2 === 1 ? 1.062 : 1.058)),
                              rep(0, 600)],
};

let checked = 0;
for (const c of vectors.earcons) {
  const input = INPUTS[c.case];
  assert.ok(input, `no JS-side input for golden case ${c.case}`);
  const [paces, grades] = input;

  const m = new PaceBandMonitor({
    targetPaceSecKm: c.target_pace_sec_km,
    tolerance: c.tolerance,
    ceilingOnly: c.ceiling_only,
  });

  const got = [];
  for (let i = 0; i < paces.length; i++) {
    const ev = m.update(i, paces[i], { grade: grades[i] });
    if (ev) got.push(ev);
  }

  assert.equal(got.length, c.events.length,
    `${c.case}: expected ${c.events.length} tones, got ${got.length}`);
  for (let i = 0; i < got.length; i++) {
    assert.equal(got[i].earcon, c.events[i].earcon, `${c.case} tone ${i}`);
    assert.equal(got[i].tS, c.events[i].t_s, `${c.case} timing ${i}`);
    assert.ok(Math.abs(got[i].error - c.events[i].error) < 1e-4,
      `${c.case} error ${i}: ${got[i].error} vs ${c.events[i].error}`);
    assert.equal(got[i].reason, c.events[i].reason, `${c.case} reason ${i}`);
  }
  assert.equal(m.state, c.final_state, `${c.case} final state`);
  console.log(`  ok  ${c.case.padEnd(28)} ${String(c.events.length).padStart(2)} tones match`);
  checked++;
}

assert.equal(checked, vectors.earcons.length);
console.log(`\nJS port agrees with Python on all ${checked} traces.`);
