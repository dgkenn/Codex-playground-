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
  // No Doppler at all, which some fixes and some devices simply do not supply. Pace then has to come
  // out of the positions, and HOW it comes out of them decides whether the number is usable.
  //
  // Differencing consecutive fixes is biased, and only ever one way: haversine returns a magnitude,
  // so jitter can lengthen an apparent step but never shorten it, and nothing cancels. At one fix a
  // second a jogger covers 2.2 m while the jitter is +/-4 m, so the noise is the larger term. The old
  // fallback did exactly that and told a 12:04/mi jogger they were running 9:16 — a number that would
  // have had the athlete slowing down to hit a pace they were already holding.
  //
  // Displacement over the five-second baseline instead. It under-reads slightly on bends, which is
  // the honest cost and is a couple of percent.
  const TRUE_MS = 2.222;                    // 8.0 km/h, the prescribed run-block jog
  const g = new GpsTrack();
  let lat = BOSTON.lat, seed = 11;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648 - 0.5;
  for (let t = 0; t <= 180; t++) {
    lat += TRUE_MS / 111320;
    g.add({ lat: lat + (rnd() * 8) / 111320, lon: BOSTON.lon,
            accuracy: 8, speed: null, t });     // speed: null — no Doppler
  }
  const truthSecKm = 1000 / TRUE_MS;
  const errPct = ((g.paceSecKm - truthSecKm) / truthSecKm) * 100;
  assert.ok(Math.abs(errPct) < 15,
    `no-Doppler pace is off by ${errPct.toFixed(1)}% (${g.paceSecKm.toFixed(0)} vs ${truthSecKm.toFixed(0)} s/km)`);
  // Direction matters as much as magnitude: reading fast is the failure that makes an athlete slow
  // down below their target, so the fallback must never land on the optimistic side by much.
  assert.ok(errPct > -8, `no-Doppler pace reads ${(-errPct).toFixed(1)}% fast, the old bias`);
  console.log(`  ok  pace without Doppler is within ${errPct.toFixed(1)}% of truth, not 23% fast`);
}

{
  // The same question at an accuracy a real run actually produces, which is the case that broke.
  //
  // The test above uses 8 m fixes one second apart, where a jogger covers 11 m over a five-second
  // baseline and the signal wins comfortably. That is the easy half. Under trees, between buildings
  // or on a cold start the fixes come at 12-15 m and every two to five seconds, and then a WALKER
  // covers 4.5 m against +/-12 m of wander -- the noise is three times the signal, and a baseline
  // fixed at five seconds is measuring the noise. Replaying a real 26-minute session through the
  // pipeline under exactly those conditions, the speed read **+159%**: a 13:00/mi walk-run shown as
  // a 5:00/mi sprint, which is what "the pace was wildly inaccurate" looked like from the inside.
  //
  // The window now comes from the accuracy rather than from a constant, so this is the case that
  // pins it. Walking, because walking is where the ratio is worst.
  const WALK_MS = 1.35;                     // ~4.9 km/h, a brisk walk break
  const ACC = 14, FIX_S = 3;
  const g = new GpsTrack();
  let lat = BOSTON.lat, seed = 29;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648 - 0.5;
  for (let t = 0; t <= 300; t += FIX_S) {
    lat += (WALK_MS * FIX_S) / 111132.92;
    g.add({ lat: lat + (rnd() * 2 * ACC) / 111132.92, lon: BOSTON.lon,
            accuracy: ACC, speed: null, t });
  }
  const truth = 1000 / WALK_MS;
  const errPct = ((g.paceSecKm - truth) / truth) * 100;
  assert.ok(g.paceSecKm != null, 'a walk on 14 m fixes must still produce a pace');
  assert.ok(Math.abs(errPct) < 20,
    `14 m fixes every ${FIX_S}s read ${(-errPct).toFixed(0)}% fast: `
    + `${g.paceSecKm.toFixed(0)} vs ${truth.toFixed(0)} s/km`);
  console.log(`  ok  a walk on ${ACC} m fixes reads within ${errPct.toFixed(1)}%, not +159%`);
}

{
  // And when the fixes are too loose to answer at all, the answer is no answer.
  //
  // The temptation is to fall back to differencing consecutive fixes so that SOMETHING is displayed.
  // That is precisely backwards: the conditions that stop the baseline resolving are the same ones
  // that make per-fix differencing worst, so the fallback would be at its most confident exactly
  // where it is most wrong. A blank pace tile is a bad outcome. Telling a walking man he is running
  // 5:00 miles, and coaching him on it, is a worse one.
  const g = new GpsTrack({ maxBaselineS: 8 });          // a tight cap, to force the condition
  let lat = BOSTON.lat;
  for (let t = 0; t <= 60; t += 2) {
    lat += 2.7 / 111132.92;
    g.add({ lat, lon: BOSTON.lon, accuracy: 24, speed: null, t });   // 24 m needs 40 s of baseline
  }
  assert.equal(g.paceSecKm, null,
    `fixes too loose to measure must report no pace, not a guess: ${g.paceSecKm}`);
  console.log('  ok  fixes too loose to measure report no pace rather than a guess');
}

{
  // The same protection at the fix rate a phone actually delivers, which is where it had stopped
  // working.
  //
  // The test above feeds a wild sample one second after the last good one. Written as
  // `accel x elapsed`, the allowance grows without limit as fixes get sparser: at one fix every four
  // seconds it came to 6 m/s, which is larger than the whole plausible speed range, so the gate
  // waved everything through exactly when GPS was at its worst. Silent, and invisible to every test
  // here, because every test here ran at 1 Hz.
  //
  // It was found by sweeping the constant over a real recorded session and watching nothing happen:
  // tightening it sixfold, from 1.5 to 0.25, moved the displayed pace's steadiness by one second per
  // mile. A knob that does nothing at any setting is not tuned, it is disconnected.
  const g = new GpsTrack();
  let lat = BOSTON.lat;
  for (let t = 0; t <= 40; t += 4) {              // one fix every four seconds, steady 2.8 m/s
    lat += (2.8 * 4) / 111132.92;
    g.add({ lat, lon: BOSTON.lon, accuracy: 8, speed: 2.8, t });
  }
  const before = g.paceSecKm;
  lat += (2.8 * 4) / 111132.92;
  g.add({ lat, lon: BOSTON.lon, accuracy: 8, speed: 7.9, t: 44 });   // a wild Doppler reading
  const moved = Math.abs(g.paceSecKm - before);
  assert.ok(moved < 30,
    `a wild sample four seconds after a good one moved the pace by ${moved.toFixed(0)} s/km`);
  console.log(`  ok  the slew gate still binds at one fix per 4s (moved ${moved.toFixed(0)} s/km)`);
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

{
  // Two distances, because they disagree and one of them over-reads.
  //
  // A session recorded alongside Polar Flow showed the split is not device-specific: position-based
  // came to 3109 m on Polar and 3064 m here; speed-based to 2430 m on Polar and 2412 m here. The two
  // devices agree within each method and differ by a quarter across them. The recording settled it
  // by accident — thirty-three minutes left running on a couch, during which Polar's position-based
  // distance grew by 670 m of pure drift.
  const track = new GpsTrack();
  const t0 = 1000;
  // Stand still, with the fixes wobbling by a few metres as they do at 14 m accuracy.
  for (let i = 0; i < 60; i++) {
    track.add({
      lat: 42.35 + (i % 3 - 1) * 4e-5, lon: -71.10 + (i % 2 - 0.5) * 4e-5,
      accuracy: 14, speed: 0, t: t0 + i,
    });
  }
  assert.equal(Math.round(track.distanceFromSpeedM), 0,
    'a stationary GPS must integrate to no distance at all');
  console.log(`  ok  standing still adds nothing to the speed-integrated distance `
            + `(position-based added ${track.distanceM.toFixed(0)} m of wobble)`);
}

{
  // And when genuinely moving, it must agree with the ground it covered.
  const track = new GpsTrack();
  const t0 = 2000, SPEED = 2.5;
  let lat = 42.35;
  for (let i = 0; i < 200; i++) {
    lat += SPEED / 111320;
    track.add({ lat, lon: -71.10, accuracy: 5, speed: SPEED, t: t0 + i });
  }
  const expected = SPEED * 199;
  assert.ok(Math.abs(track.distanceFromSpeedM - expected) / expected < 0.05,
    `200 s at 2.5 m/s is ${expected.toFixed(0)} m, got ${track.distanceFromSpeedM.toFixed(0)}`);
  console.log(`  ok  and real movement integrates to the ground covered `
            + `(${track.distanceFromSpeedM.toFixed(0)} m of ${expected.toFixed(0)})`);
}

console.log('\nAll geo tests passed.');
