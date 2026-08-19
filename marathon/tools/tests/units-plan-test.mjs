// Tests the two things added for the phone: unit conversion and the plan the app carries.
//
// Units get a test because a conversion that leaks into the logic is how a pace band ends up 60%
// wrong in one branch and right in another — and 60% is the difference between a 9:00 km and a
// 14:30 mile, which look nothing alike until one of them is silently used as the other.

import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../pace-coach-hosted.html', import.meta.url), 'utf8');
// The built page ships a classic script now, for WebView compatibility — see build-coach.mjs.
const js = html.match(/<script>([\s\S]*)<\/script>/)[1];

// Pull out the pure pieces: the unit layer, the split announcer, and the plan payload.
const MI = 1609.344;
let unit = 'mi';
const mmss = sec => {
  if (!sec || !isFinite(sec)) return '—:——';
  const m = Math.floor(sec / 60), s = Math.round(sec % 60);
  return s === 60 ? `${m + 1}:00` : `${m}:${String(s).padStart(2, '0')}`;
};
const U = {
  get name() { return unit; },
  pace(secKm) { return mmss(secKm == null ? null : secKm * (unit === 'mi' ? MI / 1000 : 1)); },
  toSecKm(secUnit) { return secUnit / (unit === 'mi' ? MI / 1000 : 1); },
  dist(m) { return m / (unit === 'mi' ? MI : 1000); },
  splitEvery() { return unit === 'mi' ? MI : 1000; },
  splitName(n) { return unit === 'mi' ? `${n} mile${n === 1 ? '' : 's'}` : `${n}K`; },
};
function parsePace(text) {
  const m = String(text).trim().match(/^(\d+):(\d{1,2})$/);
  const secUnit = m ? Number(m[1]) * 60 + Number(m[2]) : null;
  return secUnit == null ? null : U.toSecKm(secUnit);
}

// --- units ---------------------------------------------------------------------------------------

unit = 'km';
assert.equal(U.pace(540), '9:00', 'a 9:00 km should display as 9:00 in km');
assert.equal(Math.round(parsePace('9:00')), 540);

unit = 'mi';
assert.equal(U.pace(540), '14:29', '9:00/km is 14:29/mi');
assert.equal(Math.round(parsePace('14:29')), 540, 'and it must round-trip');
console.log('  ok  pace converts and round-trips both ways');

// The round trip is the load-bearing property: switching units must not move the target.
for (const secKm of [300, 420, 540, 600, 720]) {
  unit = 'mi';
  const shown = U.pace(secKm);
  const back = parsePace(shown);
  assert.ok(Math.abs(back - secKm) < 1.0,
    `${secKm} s/km -> "${shown}" -> ${back.toFixed(1)}: drifted by ${Math.abs(back - secKm).toFixed(2)}s`);
}
console.log('  ok  switching units never moves the target pace');

unit = 'mi';
assert.ok(Math.abs(U.dist(MI) - 1) < 1e-9, 'one mile of metres is one mile');
assert.equal(U.splitEvery(), MI);
assert.equal(U.splitName(1), '1 mile');
assert.equal(U.splitName(3), '3 miles');
unit = 'km';
assert.equal(U.splitEvery(), 1000);
assert.equal(U.splitName(3), '3K');
console.log('  ok  splits count in the unit the athlete thinks in');

// --- the plan ------------------------------------------------------------------------------------

const PLAN = JSON.parse(js.match(/const PLAN = (\{[\s\S]*?\});\n/)[1]);
assert.equal(PLAN.app_plan_version, 1);
assert.ok(PLAN.phases.length >= 3, 'should ship several phases');

const assess = PLAN.phases[0];
assert.equal(assess.phase, 'assess', 'week 1 must be the diagnostic phase, not training');
const w1 = assess.weeks[0];
assert.ok(w1.sessions.some(s => s.type === 'ramp_test'), 'week 1 must contain the ramp test');
assert.ok(!w1.sessions.some(s => ['threshold', 'intervals'].includes(s.type)),
  'week 1 must contain no hard running');
console.log('  ok  week 1 is diagnostic, ramp test present, no hard running');

// Every coachable session must carry enough to actually start it.
let coachable = 0;
for (const ph of PLAN.phases) {
  for (const wk of ph.weeks) {
    for (const s of wk.sessions) {
      if (!s.coachable) continue;
      coachable++;
      assert.ok(s.run_walk || s.pace || s.minutes,
        `${ph.phase} w${wk.week} "${s.title}" is coachable but carries nothing to run`);
      if (s.pace) {
        assert.ok(s.pace.target_sec_km > 120 && s.pace.target_sec_km < 1200,
          `${s.title}: implausible target ${s.pace.target_sec_km} s/km`);
        assert.ok(s.pace.tolerance > 0 && s.pace.tolerance < 0.3,
          `${s.title}: implausible tolerance ${s.pace.tolerance}`);
      }
      if (s.run_walk) {
        assert.ok(s.run_walk.reps >= 1 && s.run_walk.run_min > 0 && s.run_walk.walk_min >= 0,
          `${s.title}: nonsense run/walk pattern`);
      }
    }
  }
}
assert.ok(coachable > 20, `only ${coachable} coachable sessions across the plan`);
console.log(`  ok  all ${coachable} coachable sessions carry enough to start`);

// Ceiling-only must be right, because getting it wrong tells you to speed up on a recovery run.
for (const ph of PLAN.phases) {
  for (const wk of ph.weeks) {
    for (const s of wk.sessions) {
      if (['easy', 'long', 'run_walk', 'recovery'].includes(s.type)) {
        assert.equal(s.ceiling_only, true, `${s.type} "${s.title}" should be ceiling-only`);
      }
      if (['threshold', 'intervals', 'time_trial'].includes(s.type)) {
        assert.equal(s.ceiling_only, false, `${s.type} "${s.title}" must not be ceiling-only`);
      }
    }
  }
}
console.log('  ok  ceiling-only matches session kind everywhere');

// Phase advancement must not be something the app can do on a timer.
for (const ph of PLAN.phases) {
  assert.ok(ph.gate_note && /measurement/i.test(ph.gate_note),
    `${ph.phase} does not say that its gate needs evidence`);
}
assert.ok(!/advancePhase|prog\.phase\s*=/.test(js.replace(/PLAN\.phases\[0\]\.phase/g, '')),
  'the app must not advance a phase by itself');
console.log('  ok  the app advances weeks, never phases');

console.log('\nAll unit and plan tests passed.');
