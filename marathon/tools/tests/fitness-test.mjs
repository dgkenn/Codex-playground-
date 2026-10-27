// The fitness index against sessions whose answer is known: heart rate generated from effort by the
// same kind of response the index assumes, at a chosen fitness, then read back.

import assert from 'node:assert/strict';
import { aerobicIndex, metabolicPower, REF_SPEED_MS, FIT_GAIN, FIT_TAU_S, FIT_DELAY_S } from '../fitness.js';

/**
 * A run/walk session at 1 Hz: 5 min walking, then `reps` x (run `runS` at `runMs`, walk `walkS`).
 * Heart rate = `base` + gain x lagged effort (+ `driftPerMin` after the first run), so the true
 * heart rate for 12:00/mi on the flat is `base + gain x P(ref)`.
 */
function session({ base = 60, runMs = 2.25, reps = 8, runS = 100, walkS = 100, gradeOf = () => 0,
                   driftPerMin = 0, tau = FIT_TAU_S, delay = FIT_DELAY_S, gain = FIT_GAIN, hrGap = null } = {}) {
  const plan = [['walk', 300, 1.4]];
  for (let r = 0; r < reps; r++) plan.push(['run', runS, runMs], ['walk', walkS, 1.4]);
  const out = [];
  let t = 0, x = metabolicPower(1.4, 0), firstRun = null;
  const xs = [];
  for (const [label, dur, v] of plan) {
    if (label === 'run' && firstRun == null) firstRun = t;
    for (let i = 0; i < dur; i++, t++) {
      const g = gradeOf(t);
      x += (metabolicPower(v, g) - x) * (1 - Math.exp(-1 / tau));
      xs.push(x);
      const lagged = xs[Math.max(0, t - delay)];
      const drift = firstRun != null ? driftPerMin * (t - firstRun) / 60 : 0;
      const hr = hrGap && t >= hrGap[0] && t < hrGap[1] ? null : Math.round(base + gain * lagged + drift);
      out.push({ t_s: t, hr_bpm: hr, speed_m_s: v, grade: g, label });
    }
  }
  return out;
}
const truth = base => Math.round(base + FIT_GAIN * metabolicPower(REF_SPEED_MS, 0));

{
  const a = aerobicIndex(session({ base: 60 }));
  assert.ok(a.ok, JSON.stringify(a));
  assert.ok(Math.abs(a.hrAtRef - truth(60)) <= 1, `${a.hrAtRef} vs ${truth(60)}`);
  const b = aerobicIndex(session({ base: 50 }));
  assert.ok(Math.abs((a.hrAtRef - b.hrAtRef) - 10) <= 1, 'ten beats fitter reads ten lower');
  console.log(`  ok  reads back the heart rate for 12:00/mi on the flat (${a.hrAtRef} vs ${truth(60)}), and a fitter session lower`);
}

{
  // Pace and hills change the heart rate, not the index: the same fitness run faster, or over hills.
  const flat = aerobicIndex(session({ base: 60 })).hrAtRef;
  const fast = aerobicIndex(session({ base: 60, runMs: 2.6 })).hrAtRef;
  const hills = aerobicIndex(session({ base: 60, gradeOf: t => 0.05 * Math.sin(t / 90) })).hrAtRef;
  const short = aerobicIndex(session({ base: 60, runS: 60, walkS: 120, reps: 10 })).hrAtRef;
  for (const [what, v] of [['faster', fast], ['hilly', hills], ['shorter blocks', short]]) {
    assert.ok(Math.abs(v - flat) <= 2, `${what}: ${v} vs ${flat}`);
  }
  console.log(`  ok  faster running, hills and shorter blocks leave it where it was (${flat}, ${fast}, ${hills}, ${short})`);
}

{
  // Cardiac drift: only the first 15 minutes count, so a longer session does not read as less fit.
  const short = aerobicIndex(session({ base: 60, reps: 4, driftPerMin: 0.8 })).hrAtRef;
  const long = aerobicIndex(session({ base: 60, reps: 12, driftPerMin: 0.8 })).hrAtRef;
  assert.ok(Math.abs(short - long) <= 1, `${short} vs ${long}`);
  console.log(`  ok  a longer session with drift reads the same as a shorter one (${short})`);
}

{
  // What it refuses: too little running, too little heart rate, heart rate unrelated to effort.
  assert.equal(aerobicIndex(session({ reps: 2, runS: 60 })).ok, false);
  const gap = aerobicIndex(session({ hrGap: [400, 800] }));
  assert.equal(gap.ok, false); assert.match(gap.why, /heart rate missing/);
  const noise = session().map((s, i) => ({ ...s, hr_bpm: 110 + ((i * 7919) % 60) }));
  const n = aerobicIndex(noise);
  assert.equal(n.ok, false); assert.match(n.why, /did not follow/);
  assert.equal(aerobicIndex([]).ok, false);
  console.log('  ok  refuses short running, missing heart rate and heart rate that ignores the effort');
}

{
  // 5-second samples (an archived, compact session) read like 1-second ones.
  const one = session({ base: 60 });
  const five = one.filter(s => s.t_s % 5 === 0);
  assert.ok(Math.abs(aerobicIndex(five).hrAtRef - aerobicIndex(one).hrAtRef) <= 1);
  console.log('  ok  archived 5-second sessions read the same as live 1-second ones');
}

console.log('\nAll fitness tests passed.');
