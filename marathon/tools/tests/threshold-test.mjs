// The threshold estimator, checked against a synthetic athlete whose threshold is known by
// construction, and then against the real recording it was designed from.

import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { estimateThreshold, ceilingFrom } from '../threshold.js';

/**
 * An athlete with a known threshold.
 *
 * Built backwards on purpose: heart rate is swept across its range and the speed follows from a
 * stated efficiency curve, rather than a speed being chosen and a heart rate derived from it. That
 * is the right construction for testing THIS, because the estimator's job is to recover a
 * metres-per-beat curve from binned, noisy, lagged data -- so the curve should be the input.
 *
 * Two earlier attempts are worth recording as dead ends. Deriving heart rate from a chosen speed
 * with a steeper slope past the threshold produces no roll-off at all: binning a monotone HR(speed)
 * map by heart rate puts higher speeds in every higher band by construction, so metres per beat only
 * ever rises. Modelling the supra-threshold drift as feedback -- heart rate climbing in proportion to
 * how far above the threshold it already is -- is a positive loop, and it ran to 876 bpm.
 *
 * `driftFrac` is the confounder the whole module is arranged around: in the second half, the same
 * heart rate buys proportionally less speed, uniformly across every band. That is what cardiac drift
 * does, and a whole-session average cannot tell it apart from a threshold.
 */
function synth({ vt1 = 150, driftFrac = 0, seconds = 1800, seed = 5,
                 E0 = 0.80, lowHr = 105, topHr = 170 } = {}) {
  let rnd = seed;
  const rand = () => (rnd = (rnd * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff - 0.5;
  // Metres per beat: flat below the threshold, falling 10% per 10 bpm above it.
  const eff = hr => (hr <= vt1 ? E0 : E0 * Math.max(0.4, 1 - 0.10 * (hr - vt1) / 10));

  const hrTrue = [], speed = [];
  for (let t = 0; t < seconds; t++) {
    // Sweep up and down repeatedly so every band fills, several times over.
    const frac = (t % 420) / 420;
    hrTrue.push(lowHr + (topHr - lowHr) * (frac < 0.5 ? frac * 2 : (1 - frac) * 2));
    const late = t > seconds / 2 ? driftFrac : 0;
    speed.push(eff(hrTrue[t]) * (1 - late) * hrTrue[t] / 60 + rand() * 0.04);
  }
  // The heart rate the watch RECORDS lags the effort that produced it by 20 s, which is what the
  // estimator's lag correction has to undo.
  return hrTrue.map((_, t) => ({
    t_s: t, speed_m_s: speed[t], hr_bpm: hrTrue[Math.max(0, t - 20)],
  }));
}

{
  const est = estimateThreshold(synth({ vt1: 150 }));
  assert.ok(est, 'a session that crosses the threshold must produce an estimate');
  assert.ok(Math.abs(est.bpm - 150) <= 6,
    `estimated ${est.bpm} against a constructed threshold of 150`);
  console.log(`  ok  a known threshold of 150 is recovered as ${est.bpm} bpm`);
}

{
  // The trap this module exists to avoid. Cardiac drift makes heart rate rise and pace fall together
  // in the second half of ANY session, which looks exactly like a threshold to a whole-session
  // average. Only the first half is used, so a heavy drift must not move the answer.
  const clean = estimateThreshold(synth({ vt1: 150, driftFrac: 0 }));
  const drifty = estimateThreshold(synth({ vt1: 150, driftFrac: 0.18 }));
  assert.ok(drifty, 'a drifting session must still be readable');
  assert.ok(Math.abs(drifty.bpm - clean.bpm) <= 6,
    `drift moved the estimate from ${clean.bpm} to ${drifty.bpm}; it must not`);
  console.log(`  ok  18% of cardiac drift in the second half moves the estimate by `
            + `${Math.abs(drifty.bpm - clean.bpm)} bpm, not by a zone`);
}

{
  // An easy session that never approaches the threshold has not measured it. Inventing a number
  // from the top of whatever range happened to be run would ratchet the ceiling downward every time
  // the athlete did what they were told.
  const easy = synth({ vt1: 200, topHr: 145 });   // never gets near the threshold
  assert.equal(estimateThreshold(easy), null,
    'a session that never crosses the threshold must report nothing, not a guess');
  console.log('  ok  a session run entirely below the threshold measures nothing, and says so');
}

{
  assert.equal(estimateThreshold([]), null);
  assert.equal(estimateThreshold(null), null);
  assert.equal(estimateThreshold(synth({ seconds: 120 })), null, 'two minutes is not a measurement');
  console.log('  ok  too little data degrades to null rather than to a number');
}

{
  // The age formula keeps governing until there is something better. One session is a coincidence.
  assert.equal(ceilingFrom([]), null);
  assert.equal(ceilingFrom([{ bpm: 150, confidence: 1 }]), null, 'one session is not evidence');
  const two = ceilingFrom([{ bpm: 150, confidence: 1 }, { bpm: 152, confidence: 1 }]);
  assert.ok(two && two.bpm === 151, `two agreeing sessions settle it: ${JSON.stringify(two)}`);

  // And one bad day must not drag the training ceiling down. Median, not mean, not latest.
  const withOutlier = ceilingFrom([{ bpm: 150, confidence: 1 }, { bpm: 151, confidence: 1 },
                                   { bpm: 152, confidence: 1 }, { bpm: 118, confidence: 1 }]);
  assert.ok(withOutlier.bpm >= 148,
    `one hot Tuesday must not move the ceiling: got ${withOutlier.bpm}`);
  console.log(`  ok  two sessions settle the ceiling; a single bad one cannot move it `
            + `(${withOutlier.bpm} bpm despite a 118 outlier)`);
}

{
  // Low-confidence readings are dropped rather than averaged in.
  assert.equal(ceilingFrom([{ bpm: 150, confidence: 0.2 }, { bpm: 151, confidence: 0.1 }]), null);
  console.log('  ok  thin sessions do not count toward the ceiling');
}

// --- the real recording -----------------------------------------------------------------------

const POLAR = '/root/.claude/uploads/59977dd4-f843-5237-9878-b2f2ff901059/'
            + '72c85e8d-Dean_Kennedy_20260905_192305.CSV';
if (existsSync(POLAR)) {
  // The session this module was written from. Read by hand, its first half holds 0.78-0.82 m/beat
  // from 130 to 149 and drops to 0.74 at 150-154. The estimator has to find the same thing without
  // being told where to look.
  const samples = [];
  for (const line of readFileSync(POLAR, 'utf8').split('\n').slice(3)) {
    const c = line.split(',');
    if (c.length < 9 || !c[1]) continue;
    const [h, m, s] = c[1].split(':').map(Number);
    samples.push({ t_s: h * 3600 + m * 60 + s,
                   speed_m_s: c[3] ? Number(c[3]) / 3.6 : null,
                   hr_bpm: c[2] ? Number(c[2]) : null });
  }
  const est = estimateThreshold(samples);
  assert.ok(est, 'his own session must yield a threshold');
  assert.ok(est.bpm >= 140 && est.bpm <= 158,
    `his threshold should land near 150, not ${est.bpm}`);
  // The number that matters: it must come in UNDER the 155 the age formula prescribed, because that
  // is the whole claim -- he was being given a ceiling above his actual threshold.
  assert.ok(est.bpm < 155,
    `the measured ceiling must be below the age-formula 155, or the premise is wrong: ${est.bpm}`);
  console.log(`  ok  his 5 Sep session measures a threshold of ${est.bpm} bpm, below the 155 the `
            + `age formula prescribed (confidence ${est.confidence.toFixed(2)})`);
} else {
  console.log('  --  skipped the recorded-session check (the Polar export is not on this machine)');
}

console.log('\nAll threshold tests passed.');
