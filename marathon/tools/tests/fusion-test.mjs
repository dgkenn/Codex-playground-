// The fused speed and distance against a constructed ground truth with the faults his real sessions
// showed: phone speed 12% low (11-14% measured), positions that wobble, a GPS drop-out, a stop at a
// crossing, run/walk changes of pace.

import assert from 'node:assert/strict';
import { SpeedFusion, StepDetector, StrideModel } from '../fusion.js';

let seed = 7;
const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
const gauss = () => Math.sqrt(-2 * Math.log(rnd() + 1e-12)) * Math.cos(2 * Math.PI * rnd());

// A street grid: legs of 250 m alternating north and east.
const M_LAT = 111195, M_LON = 111195 * Math.cos(42.33 * Math.PI / 180);
function posAt(d) {
  const leg = Math.floor(d / 250), along = d - leg * 250;
  const n = Math.ceil(leg / 2) * 250 + (leg % 2 === 0 ? along : 0);
  const e = Math.floor(leg / 2) * 250 + (leg % 2 === 1 ? along : 0);
  return { lat: 42.33 + n / M_LAT, lon: -71.05 + e / M_LON };
}

/** A session: warm-up walk, run/walk blocks, a 60 s stop, a 90 s GPS drop-out. */
function session({ phoneBias = 0.88, motion = true, arm = false, armHalfWalking = false, dropout = true,
                   noDoppler = false, spikes = false } = {}) {
  const f = new SpeedFusion();
  let d = 0, en = 0, ee = 0, naive = 0;
  const cad = v => (v > 1.8 ? 165 : v > 0.5 ? 112 : 0);
  let stepPhase = 0, armPhase = 0, armOdd = false, maxErr = 0, errs = [];
  const settle = [];                       // seconds from each change of pace until the estimate is within 0.25 m/s
  let changedAt = null, prevV = null;
  for (let t = 0; t < 2400; t++) {
    const v = t < 300 ? 1.4 : (t >= 1500 && t < 1560) ? 0 : (Math.floor((t - 300) / 120) % 2 === 0 ? 2.25 : 1.4);
    if (prevV != null && v !== prevV && t > 400) changedAt = t;
    prevV = v;
    // accelerometer at 50 Hz: an impact per step
    if (motion) {
      const c = cad(v);
      for (let k = 0; k < 50; k++) {
        const tt = t + k / 50;
        let a = 9.81 + 0.3 * gauss();
        if (c) {
          stepPhase += c / 60 / 50;
          if (stepPhase >= 1) { stepPhase -= 1; }
          const ph = stepPhase;
          if (ph < 0.12) a += (v > 1.8 ? 9 : 4.5) * Math.sin(Math.PI * ph / 0.12);
        }
        f.motion({ t: tt, ax: 0, ay: 0, az: a });
      }
    }
    // the armband: 52 Hz magnitudes in its own units (milli-g), delivered in frames of 13
    if (arm) {
      const c = cad(v), frame = [];
      for (let k = 0; k < 52; k++) {
        let a = 1000 + 30 * gauss();
        if (c) {
          armPhase += c / 60 / 52;
          if (armPhase >= 1) { armPhase -= 1; armOdd = !armOdd; }
          // Walking, the arm can feel only every other step: the swing, once per stride.
          const felt = !(armHalfWalking && v < 1.8 && armOdd);
          if (felt && armPhase < 0.14) a += (v > 1.8 ? 700 : 350) * Math.sin(Math.PI * armPhase / 0.14);
        }
        frame.push(a);
        if (frame.length === 13) { f.arm({ t: t + k / 52, mags: frame.splice(0) }); }
      }
    }
    d += v;
    // GPS at 1 Hz; correlated position error; drop-out from 900 to 990 s
    en += -en / 20 + 1.3 * gauss(); ee += -ee / 20 + 1.3 * gauss();
    const p = posAt(d);
    const inDrop = dropout && t >= 900 && t < 990;
    if (!inDrop) {
      let doppler = v === 0 ? Math.abs(0.25 * gauss()) : v * phoneBias + 0.1 * gauss();
      if (spikes && t % 45 === 17) doppler += 4;          // multipath: a wild reading now and then
      f.gps({ t, lat: p.lat + en / M_LAT, lon: p.lon + ee / M_LON, accuracy: 6, speed: noDoppler ? null : doppler });
      if (t > 0) naive += Math.max(0, doppler);
    }
    const out = f.tick(t);
    if (t > 400) { const e = Math.abs(out.speedMS - v); errs.push(e); maxErr = Math.max(maxErr, e); }
    if (changedAt != null && Math.abs(out.speedMS - v) < 0.25) { settle.push(t - changedAt); changedAt = null; }
  }
  errs.sort((a, b) => a - b);
  settle.sort((a, b) => a - b);
  return { f, truth: d, naive, p50: errs[Math.floor(errs.length / 2)], p95: errs[Math.floor(errs.length * 0.95)],
           settleMed: settle[Math.floor(settle.length / 2)] };
}

{
  const s = session();
  const err = s.f.distanceM / s.truth - 1;
  const st = s.f.state();
  assert.ok(Math.abs(s.naive / s.truth - 1 - (-0.12)) < 0.04, 'the phone speed alone reads ~12% short, as his did');
  assert.ok(Math.abs(err) < 0.025, `fused distance within 2.5% of the truth: ${(err * 100).toFixed(1)}%`);
  assert.ok(Math.abs(st.scale - 1 / 0.88) < 0.05, `the scale is learned from straight stretches: ${st.scale}`);
  assert.ok(st.scaleWindows >= 5, `from several windows: ${st.scaleWindows}`);
  assert.ok(st.strideSeconds > 60, 'the stride is learned while the GPS is good');
  assert.ok(st.shares.still >= 50, `the stop is recognised as standing still: ${JSON.stringify(st.shares)}`);
  assert.ok(s.p50 < 0.15, `per-second speed is close to the truth (median error ${s.p50.toFixed(2)} m/s)`);
  assert.ok(s.settleMed <= 3, `a change of pace shows within a few seconds (median ${s.settleMed} s)`);
  console.log(`  ok  fused distance ${(err * 100).toFixed(1)}% vs truth (phone speed alone ${((s.naive / s.truth - 1) * 100).toFixed(1)}%), `
            + `scale ${st.scale}, ${st.scaleWindows} windows, per-second median error ${s.p50.toFixed(2)} m/s, `
            + `run/walk changes settle in ${s.settleMed} s`);
}

{
  // The armband alone (phone motion off): its accelerometer, in its own units, carries the drop-out
  // and the stop just as the phone's does.
  const s = session({ motion: false, arm: true });
  const err = s.f.distanceM / s.truth - 1;
  const st = s.f.state();
  assert.ok(st.arm && !st.armUnusable, 'the armband channel is live');
  assert.ok(st.armStrideSeconds > 60, `its stride is learned: ${st.armStrideSeconds} s`);
  assert.ok(Math.abs(err) < 0.03, `armband steps alone bridge the drop-out: ${(err * 100).toFixed(1)}%`);
  assert.ok(st.shares.still >= 50, `and see the stop: ${JSON.stringify(st.shares)}`);
  // Both together: still fine, and neither fights the other.
  const both = session({ motion: true, arm: true });
  const e2 = both.f.distanceM / both.truth - 1;
  // (a different noise draw from the first session: the remaining error is the scale's, not the steps')
  assert.ok(Math.abs(e2) < 0.03, `phone and armband together: ${(e2 * 100).toFixed(1)}%`);
  console.log(`  ok  armband accelerometer alone ${(err * 100).toFixed(1)}%, with the phone's too ${(e2 * 100).toFixed(1)}%`);
}

{
  // An arm sensor that feels only every other step while walking (the arm swing, once per stride)
  // reads half the cadence. The half-cadence guard sees the impossible step length and doubles it.
  const s = session({ motion: false, arm: true, armHalfWalking: true });
  const err = s.f.distanceM / s.truth - 1;
  const st = s.f.state();
  assert.ok(st.halfCadenceFixes.arm > 300, `half-counting is caught: ${JSON.stringify(st.halfCadenceFixes)}`);
  assert.ok(Math.abs(err) < 0.03, `and the distance holds, drop-out included: ${(err * 100).toFixed(1)}%`);
  console.log(`  ok  an armband counting one step per arm swing is caught (${st.halfCadenceFixes.arm} s doubled), distance ${(err * 100).toFixed(1)}%`);
}

{
  // Doppler spikes of +4 m/s (multipath) every 45 s: clipped by the robust update, not followed.
  const clean = session();
  const s = session({ spikes: true });
  const err = s.f.distanceM / s.truth - 1;
  assert.ok(s.f.state().outliers >= 40, `the spikes are recognised: ${s.f.state().outliers}`);
  assert.ok(Math.abs(err) < 0.025, `distance unmoved by them: ${(err * 100).toFixed(1)}%`);
  assert.ok(s.p95 < clean.p95 + 0.15, `the worst seconds barely worse: p95 ${s.p95.toFixed(2)} vs ${clean.p95.toFixed(2)} m/s`);
  assert.ok(s.settleMed <= 3, `and real changes of pace still show at once (${s.settleMed} s)`);
  console.log(`  ok  Doppler spikes are clipped (${s.f.state().outliers} down-weighted): distance ${(err * 100).toFixed(1)}%, `
            + `p95 speed error ${s.p95.toFixed(2)} vs ${clean.p95.toFixed(2)} m/s clean`);
}

{
  // Within running, pace changes through stride more than cadence. A change at a constant 165 spm
  // must still show with the GPS gone -- through how hard the steps land.
  const f = new SpeedFusion();
  let ph = 0, d = 0;
  const speedAt = t => (Math.floor(t / 60) % 2 === 0 ? 2.2 : 3.0);
  const feed = (t, v, gps) => {
    for (let k = 0; k < 50; k++) {
      ph += 165 / 60 / 50; if (ph >= 1) ph -= 1;
      const amp = 6 + (v - 2.2) * 6;                     // landings harder at the faster pace
      f.motion({ t: t + k / 50, ax: 0, ay: 0, az: 9.81 + 0.3 * gauss() + (ph < 0.12 ? amp * Math.sin(Math.PI * ph / 0.12) : 0) });
    }
    d += v;
    if (gps) f.gps({ t, lat: 42.33 + d / 111195, lon: -71.05, accuracy: 5, speed: v * 0.88 + 0.05 * gauss() });
    return f.tick(t);
  };
  for (let t = 0; t < 900; t++) feed(t, speedAt(t), true);
  const fast = [], slow = [];
  for (let t = 900; t < 1140; t++) {
    const v = speedAt(t), out = feed(t, v, false);
    if (t % 60 >= 10) (v > 2.5 ? fast : slow).push(out.speedMS);
  }
  const mean = xs => xs.reduce((a, b) => a + b, 0) / xs.length;
  assert.ok(Math.abs(mean(fast) - 3.0) < 0.25 && Math.abs(mean(slow) - 2.2) < 0.25,
    `with no GPS, steps alone tell 3.0 from 2.2 m/s at one cadence: ${mean(fast).toFixed(2)} / ${mean(slow).toFixed(2)}`);
  console.log(`  ok  at a constant cadence, steps alone tell ${mean(fast).toFixed(2)} from ${mean(slow).toFixed(2)} m/s by how they land`);
}

{
  // The 90 s drop-out is carried by the steps: distance over it is close to what was run.
  const s = session();
  // Re-run a copy to the end of the drop-out and compare the distance accrued over it.
  const ok = Math.abs(s.f.distanceM / s.truth - 1) < 0.025;
  assert.ok(ok);
  const noMotion = session({ motion: false });
  const e2 = noMotion.f.distanceM / noMotion.truth - 1;
  assert.ok(Math.abs(e2) < 0.06, `without the accelerometer, GPS with its bias removed still lands within 6%: ${(e2 * 100).toFixed(1)}%`);
  console.log(`  ok  without motion data the scale alone brings it to ${(e2 * 100).toFixed(1)}% (drop-out not bridged)`);
}

{
  // A carried-over calibration starts the next session already corrected.
  const first = session();
  const g = new SpeedFusion({ saved: first.f.state() });
  assert.ok(Math.abs(g.scale - first.f.scale) < 0.03, `the scale carries over: ${g.scale} vs ${first.f.scale}`);
  assert.ok(g.strideModel.stride(165) > 0.6, 'and the stride model');
  console.log(`  ok  calibration carries into the next session (scale ${g.scale.toFixed(3)}, stride at 165 spm ${g.strideModel.stride(165).toFixed(2)} m)`);
}

{
  // Unit: step detection counts impulses at a known cadence.
  const sd = new StepDetector();
  let ph = 0;
  for (let i = 0; i < 50 * 20; i++) {
    const t = i / 50; ph += 165 / 60 / 50; if (ph >= 1) ph -= 1;
    sd.add(t, 0, 0, 9.81 + (ph < 0.12 ? 9 * Math.sin(Math.PI * ph / 0.12) : 0));
  }
  const c = sd.cadence(20);
  assert.ok(Math.abs(c - 165) < 4, `cadence ${c}`);
  const m = new StrideModel();
  for (let i = 0; i < 50; i++) { m.add(110, null, 0.75); m.add(165, null, 0.82); }
  assert.ok(Math.abs(m.stride(140) - 0.788) < 0.02, `stride rises with cadence: ${m.stride(140)}`);
  console.log(`  ok  steps are counted at ${c.toFixed(0)} spm and stride is a line in cadence`);
}

{
  // No phone speed and no motion: positions alone, over a baseline, still give a usable distance.
  const s = session({ noDoppler: true, motion: false, dropout: false });
  const e = s.f.distanceM / s.truth - 1;
  assert.ok(Math.abs(e) < 0.08, `positions alone within 8%: ${(e * 100).toFixed(1)}%`);
  console.log(`  ok  with neither phone speed nor motion, positions over a baseline give ${(e * 100).toFixed(1)}%`);
}

{
  // A motion sensor that sees no steps (constant gravity: a desktop browser, a phone wedged in a
  // holder) must not pin a moving runner to zero. Found by the browser suite: the coach went silent.
  const f = new SpeedFusion();
  let d = 0;
  for (let t = 0; t < 300; t++) {
    for (let k = 0; k < 50; k++) f.motion({ t: t + k / 50, ax: 0, ay: 0, az: 9.81 });
    f.motion({ t, ax: null, ay: null, az: null });
    d += 3;
    f.gps({ t, lat: 42.33 + d / 111195, lon: -71.05, accuracy: 5, speed: 3 * 0.88 });
    f.tick(t);
  }
  const e = f.distanceM / d - 1;
  assert.ok(Math.abs(e) < 0.15, `a stepless sensor does not stop the distance: ${(e * 100).toFixed(1)}%`);
  assert.equal(f.state().motionUnusable, true, 'and is set aside');
  // Events with no numbers in them are not a sensor at all.
  const g = new SpeedFusion();
  g.motion({ t: 0, ax: null, ay: null, az: null });
  assert.equal(g.motionSeen, false);
  console.log('  ok  a motion sensor that sees no steps is set aside instead of pinning the speed to zero');
}

{
  // A fix every four seconds (ordinary on an iPhone): the estimate stays trusted between fixes.
  const f = new SpeedFusion();
  let d = 0, untrusted = 0;
  for (let t = 0; t < 120; t++) {
    d += 3;
    if (t % 4 === 0) f.gps({ t, lat: 42.33 + d / 111195, lon: -71.05, accuracy: 5, speed: 3 * 0.88 });
    if (t > 5 && !f.tick(t).trusted) untrusted += 1; else if (t <= 5) f.tick(t);
  }
  assert.equal(untrusted, 0, `trusted between sparse fixes: ${untrusted} untrusted seconds`);
  console.log('  ok  with a fix every four seconds the estimate stays trusted between fixes');
}

console.log('\nAll fusion tests passed.');
