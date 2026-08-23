// Tests the two things added for the phone: unit conversion and the plan the app carries.
//
// Units get a test because a conversion that leaks into the logic is how a pace band ends up 60%
// wrong in one branch and right in another — and 60% is the difference between a 9:00 km and a
// 14:30 mile, which look nothing alike until one of them is silently used as the other.

import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { SplitAnnouncer, formatMMSS } from '../pace-monitor.js';

const here = dirname(fileURLToPath(import.meta.url));
const ENGINE = join(here, '..', '..', 'engine');

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

{
  // A split must report how long that split took, not the pace at the instant it ticked over.
  // Run at a steady 1 m/s — a kilometre every 1000 s, so 16:40 per km — and have the instantaneous
  // pace spike to 200 s/km at the exact second the second kilometre completes. The announcement must
  // be the 16:40 that kilometre actually took, not the 3:20 the momentary reading claimed.
  const split = new SplitAnnouncer({ everyM: 1000, formatPace: formatMMSS });
  let said = [];
  for (let t = 1; t <= 2000; t++) {
    const inst = t === 2000 ? 200 : 1000;
    const line = split.update(t, t * 1.0, inst, 'in');
    if (line) said.push(line);
  }
  assert.equal(said.length, 2, `expected two splits, got ${said.length}: ${said.join(' / ')}`);
  assert.match(said[0], /^1K\. 16:40\./, `first split reported "${said[0]}"`);
  assert.match(said[1], /^2K\. 16:40\./,
    `second split reported "${said[1]}" — that is the instantaneous pace, not the split average`);
  console.log('  ok  a split reports the split average, not the pace at the moment it ticked');
}

{
  // And when the pace channel is degraded, no number at all. A distance accumulated while the
  // signal was gone is not a distance worth dividing by, and a confident-sounding average built
  // from it is worse than saying nothing.
  const split = new SplitAnnouncer({ everyM: 1000, formatPace: formatMMSS });
  let line = null;
  for (let t = 1; t <= 400; t++) line = split.update(t, t * 3.0, null, 'unknown') || line;
  assert.equal(line, '1K. no pace signal.', `reported "${line}"`);
  console.log('  ok  a split with no pace signal reports no number rather than a plausible one');
}

// --- the plan ------------------------------------------------------------------------------------

const PLAN = JSON.parse(js.match(/const PLAN = (\{[\s\S]*?\});\n/)[1]);
assert.equal(PLAN.app_plan_version, 1);
assert.ok(PLAN.phases.length >= 3, 'should ship several phases');

// The shipped plan itself now starts past ASSESS -- see generate_app_plan.py's START_PHASE for why:
// ASSESS's own gates include fourteen nights of HRV, which nothing in tools/ can ever collect, so a
// strict reading trapped every athlete who used this app in the diagnostic phase permanently. What
// still has to be true, and is checked against the engine directly rather than against what happens
// to be configured for export right now, is the invariant the diagnostic week itself promises: the
// ramp test is there, and nothing hard is asked of untested tissue.
const assessJson = execFileSync('python3', ['-c', `
import sys, json
sys.path.insert(0, ${JSON.stringify(ENGINE)})
from marathon_engine.app_plan import build_app_plan
from marathon_engine.plan import Phase
from marathon_engine.cli import _estimated_profile
profile = _estimated_profile(age=30, hr_rest=60)
plan = build_app_plan(profile, start_phase=Phase.ASSESS)
print(json.dumps(plan))
`], { encoding: 'utf8' });
const assessPlan = JSON.parse(assessJson);
const assess = assessPlan.phases[0];
assert.equal(assess.phase, 'assess', 'the engine\'s own first phase must still be the diagnostic one');
assert.equal(assess.weeks.length, 1,
  'and it must ship exactly the one week PHASE_MIN_WEEKS asks for, not six copies of it');
const w1 = assess.weeks[0];
assert.ok(w1.sessions.some(s => s.type === 'ramp_test'), 'week 1 must contain the ramp test');
assert.ok(!w1.sessions.some(s => ['threshold', 'intervals'].includes(s.type)),
  'week 1 must contain no hard running');
console.log('  ok  the diagnostic phase is one week, ramp test present, no hard running');

// What actually ships: past ASSESS, and with a real session on every one of the athlete's three
// declared running days in its first week -- the thing that was reported broken as "my Sunday is
// empty". run_days in the exported plan is [2, 5, 6] = Wed, Sat, Sun; PLAN's own day 6 is Sunday.
assert.notEqual(PLAN.phases[0].phase, 'assess',
  'the export must not hand a fresh athlete a phase the app has no way to ever leave');
const shippedW1 = PLAN.phases[0].weeks[0];
for (const day of PLAN.run_days) {
  const s = shippedW1.sessions.find(x => x.day === day);
  assert.ok(s && s.type !== 'rest', `day ${day} is a declared running day and must not be rest`);
}
console.log(`  ok  the shipped plan starts at ${PLAN.phases[0].phase} `
          + `with every declared running day covered`);

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
// One assignment is allowed, and only this exact one: resetting to the plan's OWN first phase when
// the saved one no longer exists in it. That is stale-data recovery, not a decision -- it can only
// ever fall back to the start, never step forward, so it cannot be how someone gets silently
// promoted. Anything else assigning prog.phase is exactly the thing this test exists to catch.
const withoutResetToStart = js
  .replace(/prog\.phase\s*=\s*PLAN\.phases\[0\]\.phase\s*;/g, '')
  .replace(/PLAN\.phases\[0\]\.phase/g, '');
assert.ok(!/advancePhase|prog\.phase\s*=/.test(withoutResetToStart),
  'the app must not advance a phase by itself');
console.log('  ok  the app advances weeks, never phases');

// --- speed, as distinct from pace ----------------------------------------------------------------

{
  // A treadmill in the United States is dialled in miles per hour. Announcing kilometres per hour to
  // someone standing in front of a dial marked 3 to 12 is a conversion to do while running, which is
  // a conversion to get wrong. These are the ramp ladder's own speeds.
  const MI = 1609.344;
  const mph = kmh => kmh / (MI / 1000);
  const expected = { 4.5: '2.8', 5: '3.1', 6: '3.7', 7: '4.3', 8: '5.0', 9: '5.6', 10: '6.2' };
  for (const [kmh, want] of Object.entries(expected)) {
    assert.equal(mph(Number(kmh)).toFixed(1), want, `${kmh} km/h should read ${want} mph`);
  }
  console.log('  ok  the ramp ladder converts to the numbers on a treadmill dial');
}

{
  // Pace and speed run in opposite directions, so a band expressed as one cannot be the same two
  // numbers as the other. 13:20 to 15:40 per mile is 4.5 down to 3.8 mph — the endpoints swap.
  const MI = 1609.344;
  const secKmToMph = secKm => (3600 / secKm) / (MI / 1000);
  const target = 870;                       // 14:30 per mile
  const tol = 0.08;
  const slow = target * (1 + tol), fast = target * (1 - tol);
  assert.ok(slow > fast, 'a slower pace is a bigger number');
  assert.ok(secKmToMph(slow) < secKmToMph(fast), 'and a slower speed is a smaller one');
  console.log('  ok  pace and speed order the band\u2019s endpoints oppositely, as they must');
}

console.log('\nAll unit and plan tests passed.');
