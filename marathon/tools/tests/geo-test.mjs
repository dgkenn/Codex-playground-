// Every case here corresponds to a defect the old GPS code actually had. They are cheap to write
// and would each have shown up on a run as a wrong number the athlete had no way to question.

import assert from 'node:assert/strict';
import { GpsTrack, haversine } from '../geo.js';

const BOSTON = { lat: 42.3251, lon: -71.0581 };
/** Move north by `m` metres. One degree of latitude is close enough to 111.13 km here. */
const north = (from, m) => ({ lat: from.lat + m / 111132.92, lon: from.lon });

// --- distance ------------------------------------------------------------------------------------

{
  assert.ok(Math.abs(haversine(BOSTON, north(BOSTON, 100)) - 100) < 0.5, 'haversine is off');
  console.log('  ok  haversine measures 100 m as 100 m');
}

{
  // Ten minutes of even running: 2.8 m/s, one fix a second.
  const g = new GpsTrack();
  let p = BOSTON;
  for (let t = 0; t < 600; t++) {
    g.add({ ...p, accuracy: 8, speed: 2.8, t });
    p = north(p, 2.8);
  }
  const km = g.distanceM / 1000;
  assert.ok(Math.abs(km - 1.68) < 0.02, `expected ~1.68 km, got ${km.toFixed(3)}`);
  console.log(`  ok  even running measures ${km.toFixed(2)} km`);
}

{
  // Standing at a crossing for two minutes. The old code integrated speed x time and would happily
  // accumulate hundreds of metres from Doppler noise.
  const g = new GpsTrack();
  let seed = 7;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648 - 0.5;
  for (let t = 0; t < 120; t++) {
    g.add({ lat: BOSTON.lat + rnd() * 2e-5, lon: BOSTON.lon + rnd() * 2e-5,
            accuracy: 10, speed: 0.3, t });
  }
  assert.ok(g.distanceM < 25, `standing still accumulated ${g.distanceM.toFixed(0)} m`);
  console.log(`  ok  two minutes standing still adds ${g.distanceM.toFixed(0)} m, not hundreds`);
}

// --- rejection -----------------------------------------------------------------------------------

{
  const g = new GpsTrack();
  g.add({ ...BOSTON, accuracy: 8, speed: 2.8, t: 0 });
  const before = g.distanceM;
  const r = g.add({ ...north(BOSTON, 5000), accuracy: 8, speed: 2.8, t: 1 });
  assert.equal(r.accepted, false);
  assert.equal(r.reason, 'implausible jump');
  assert.equal(g.distanceM, before, 'a teleport added distance');
  console.log('  ok  a 5 km jump in one second is rejected');
}

{
  // The subtle one: a rejected fix must not become the baseline for the next segment, or one loose
  // reading corrupts two.
  const g = new GpsTrack();
  g.add({ ...BOSTON, accuracy: 8, speed: 2.8, t: 0 });
  g.add({ ...north(BOSTON, 3000), accuracy: 90, speed: 2.8, t: 1 });   // rejected: accuracy
  g.add({ ...north(BOSTON, 3), accuracy: 8, speed: 2.8, t: 2 });       // 3 m from the GOOD fix
  assert.ok(g.distanceM < 10,
    `a rejected fix poisoned the next segment: ${g.distanceM.toFixed(0)} m`);
  console.log('  ok  a rejected fix does not become the next baseline');
}

// --- grade ---------------------------------------------------------------------------------------

{
  // A 6% climb: 6 m up over 100 m along.
  const g = new GpsTrack();
  let p = BOSTON, alt = 20;
  for (let t = 0; t < 60; t++) {
    g.add({ ...p, alt, accuracy: 8, speed: 2.5, t });
    p = north(p, 2.5); alt += 2.5 * 0.06;
  }
  assert.ok(Math.abs(g.grade - 0.06) < 0.012, `grade read ${(g.grade * 100).toFixed(1)}%`);
  console.log(`  ok  a 6% climb reads ${(g.grade * 100).toFixed(1)}%`);
  // 60 s at 2.5 m/s is 150 m along the ground; at 6% that is 9 m of climb, not 150.
  assert.ok(g.ascentM > 8 && g.ascentM < 11, `ascent ${g.ascentM.toFixed(1)} m, expected ~9`);
  console.log(`  ok  ascent totals ${g.ascentM.toFixed(1)} m over 150 m of 6% climb`);
}

{
  // Altitude noise on the flat must not become a grade — the old clamp was the only defence and
  // there was no window at all.
  const g = new GpsTrack();
  let p = BOSTON, seed = 3;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648 - 0.5;
  for (let t = 0; t < 120; t++) {
    g.add({ ...p, alt: 20 + rnd() * 6, accuracy: 8, speed: 2.5, t });
    p = north(p, 2.5);
  }
  assert.ok(Math.abs(g.grade) < 0.06, `flat ground with noisy altitude read ${(g.grade*100).toFixed(1)}%`);
  console.log(`  ok  noisy altitude on flat ground stays near 0%`);
}

// --- pace ----------------------------------------------------------------------------------------

{
  // Jittery Doppler must not make the displayed pace flicker between unusable numbers.
  const g = new GpsTrack();
  let p = BOSTON, seed = 11;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648 - 0.5;
  const paces = [];
  for (let t = 0; t < 120; t++) {
    g.add({ ...p, accuracy: 8, speed: 2.8 + rnd() * 0.9, t });
    p = north(p, 2.8);
    if (t > 20) paces.push(g.paceSecKm);
  }
  const spread = Math.max(...paces) - Math.min(...paces);
  // Under +/-16% Doppler jitter, which is pessimistic for iOS. The residual is arithmetic, not a
  // defect: a fifteen-sample mean of that much noise leaves about +/-20 s/km, and smoothing harder
  // to hide it would only make the number lag the running. The old raw value swung by hundreds.
  assert.ok(spread < 50, `displayed pace swung by ${spread.toFixed(0)} s/km`);
  // A wild sample in the middle of a run must not move the display. Continuing the sequence rather
  // than jumping ahead: after a long gap one sample legitimately IS all the current information,
  // and pretending otherwise would be the wrong test.
  const before = g.paceSecKm;
  g.add({ ...p, accuracy: 8, speed: 7.9, t: 120 });
  assert.ok(Math.abs(g.paceSecKm - before) < 25,
    `one wild sample moved the pace by ${Math.abs(g.paceSecKm - before).toFixed(0)} s/km`);
  console.log('  ok  a wild speed sample is slew-limited, not averaged in');
  console.log(`  ok  smoothed pace varies by ${spread.toFixed(0)} s/km, not hundreds`);
}

{
  const g = new GpsTrack();
  g.add({ ...BOSTON, accuracy: 8, speed: 2.8, t: 0 });
  assert.equal(g.trustedAt(2), true);
  assert.equal(g.trustedAt(30), false, 'a 30-second-old fix is a memory, not a position');
  console.log('  ok  a stale fix is not trusted');
}

// --- route ---------------------------------------------------------------------------------------

{
  const g = new GpsTrack();
  let p = BOSTON;
  for (let t = 0; t < 100; t++) { g.add({ ...p, accuracy: 8, speed: 2.5, t }); p = north(p, 2.5); }
  const { points, w, h } = g.projected();
  assert.equal(points.length, 100);
  assert.ok(h > 200 && h < 300, `route height ${h.toFixed(0)} m for a 247 m straight line`);
  assert.ok(points.every(([x, y]) => isFinite(x) && isFinite(y)), 'non-finite projected point');
  console.log(`  ok  route projects to ${w.toFixed(0)} x ${h.toFixed(0)} m`);
}

{
  const g = new GpsTrack();
  assert.deepEqual(g.projected().points, [], 'an empty track must project to nothing, not NaN');
  assert.equal(g.paceSecKm, null);
  assert.equal(g.grade, 0);
  console.log('  ok  an empty track degrades cleanly');
}

console.log('\nAll geo tests passed.');
