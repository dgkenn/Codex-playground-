// Drives the coach's decision path with synthetic GPS, so the cue stream can be read before a real
// run rather than discovered during one.
//
// The GPS noise figures are the point. A phone reports speed with Doppler jitter of a few percent
// and occasional loose fixes; if the channel turns that into a metronome it is useless, and the
// only way to know is to feed it noise and count.

import assert from 'node:assert/strict';
import { PaceBandMonitor, SplitAnnouncer, formatMMSS } from '../pace-monitor.js';

const TARGET = 540;                       // 9:00 /km
const TOL = 0.08;

function simulate({ name, minutes, paceAt, sigma = 0.04, ceilingOnly = true, seed = 1,
                    dropout = null }) {
  let s = seed;
  const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
  const gauss = () => (rnd() + rnd() + rnd() + rnd() - 2) * 1.2;

  const mon = new PaceBandMonitor({ targetPaceSecKm: TARGET, tolerance: TOL, ceilingOnly });
  const split = new SplitAnnouncer({ everyM: 1000, formatPace: formatMMSS });
  const out = [];
  let dist = 0;

  for (let t = 0; t < minutes * 60; t++) {
    const truePace = paceAt(t);
    const trusted = !(dropout && t >= dropout[0] && t < dropout[1]);
    const pace = trusted ? truePace * (1 + gauss() * sigma) : null;
    if (trusted) dist += 1000 / pace;

    const ev = mon.update(t, pace, { paceTrusted: trusted });
    if (ev) out.push([t, ev.earcon]);
    const line = split.update(t, dist, pace, mon.state);
    if (line) out.push([t, `SAY "${line}"`]);
  }

  const tones = out.filter(([, e]) => !String(e).startsWith('SAY')).length;
  const perMin = tones / minutes;
  console.log(`\n=== ${name} ===`);
  for (const [t, e] of out.slice(0, 14)) {
    console.log(`  ${String(Math.floor(t / 60)).padStart(2)}:${String(t % 60).padStart(2, '0')}  ${e}`);
  }
  if (out.length > 14) console.log(`  … ${out.length - 14} more`);
  console.log(`  -- ${tones} tones in ${minutes} min (${perMin.toFixed(2)}/min), ` +
              `${(dist / 1000).toFixed(2)} km`);
  return { tones, perMin, out };
}

// Realistic: you hold 9:00 with normal GPS wobble. Should be near-silent.
const steady = simulate({
  name: 'Held 9:00 for 30 min, 4% GPS noise',
  minutes: 30, paceAt: () => TARGET,
});
assert.ok(steady.perMin <= 0.2, `nagged on an evenly-run session: ${steady.perMin}/min`);

// The beginner error your last run showed: starting far too fast.
const hot = simulate({
  name: 'Started at 6:30 then settled to 9:00 (your actual pattern)',
  minutes: 30, paceAt: t => (t < 420 ? 390 : TARGET),
});
assert.ok(hot.out.some(([, e]) => e === 'ease'), 'never told to ease off');
assert.ok(hot.out.some(([, e]) => e === 'in_band'), 'never confirmed the correction');
assert.ok(hot.perMin <= 1.0, `too talkative: ${hot.perMin}/min`);

// Easy run drifting slow: a ceiling-only session must stay silent about it.
const slow = simulate({
  name: 'Easy run drifting to 10:30 (ceiling-only)',
  minutes: 25, paceAt: t => (t < 600 ? TARGET : 630),
});
assert.equal(slow.out.filter(([, e]) => e === 'lift').length, 0,
  'told the athlete to speed up on an easy run');

// GPS lost in a tunnel.
const lost = simulate({
  name: 'GPS lost for four minutes',
  minutes: 25, paceAt: () => TARGET, dropout: [600, 840],
});
assert.ok(lost.out.some(([, e]) => e === 'degraded'), 'lost signal was never announced');
const duringLoss = lost.out.filter(([t, e]) => t > 610 && t < 840 && e !== 'degraded'
                                              && !String(e).startsWith('SAY'));
assert.equal(duringLoss.length, 0, 'beeped about pace while GPS was gone');

// Pessimistic noise: a phone under trees.
const noisy = simulate({
  name: 'Held 9:00 with 8% GPS noise (heavy tree cover)',
  minutes: 30, paceAt: () => TARGET, sigma: 0.08, seed: 99,
});
assert.ok(noisy.perMin <= 0.5, `noise became a metronome: ${noisy.perMin}/min`);

console.log('\nAll pace-coach simulations passed.');
