// PaceBandMonitor behaviour that is not a golden-vector trace — see pace-monitor-parity.mjs for the
// cross-language ones. This is the property that trace format cannot express: what happens when GPS
// itself is sparse, which is a fact about the phone rather than about the pace being run.

import assert from 'node:assert/strict';
import { PaceBandMonitor, Earcon } from '../pace-monitor.js';

const TARGET = 450;   // 12:04/mi, sec/km

{
  // "The prompting that I'm going too fast or slow didn't exist." Every other test of this monitor,
  // in this file and in the golden vectors, feeds one fix per simulated second. MIN_SAMPLES=8 inside
  // SMOOTHING_S=20 assumes that cadence is real. It is not guaranteed: iOS commonly delivers
  // watchPosition fixes every two to five seconds depending on signal and power state, and at
  // anything slower than one every 2.5s, eight-in-twenty never arrives -- not late, never, for the
  // rest of the run. Reproduced directly: the pre-fix monitor produced zero tones in five minutes of
  // running 30% too fast at one fix every four seconds.
  const m = new PaceBandMonitor({ targetPaceSecKm: TARGET, tolerance: 0.06, ceilingOnly: true });
  const events = [];
  for (let t = 0; t < 300; t += 4) {
    const ev = m.update(t, TARGET * 0.7, { paceTrusted: true, running: true });
    if (ev) events.push(ev);
  }
  assert.ok(events.length > 0,
    'a fix every four seconds must still produce tones, not permanent silence');
  assert.ok(events.every(e => e.earcon === Earcon.EASE),
    `and they must still name the fault: ${JSON.stringify(events.slice(0, 2))}`);
  // The state this drives is not only the tone: `S.monitor.state` also colours the on-screen verdict,
  // the gauge marker and the route on the map. Stuck at 'unknown' it looks like a broken pacing
  // meter even though the underlying GPS was fine -- which is the other half of what was reported.
  assert.notEqual(m.state, 'unknown', 'the verdict must resolve, not stay unknown forever');
  console.log(`  ok  sparse GPS (one fix per 4s) still produces tones and a resolved verdict `
            + `(${events.length} tones, state "${m.state}")`);
}

{
  // The normal case must be unchanged: with a real fix roughly every second, MIN_SAMPLES is reached
  // well inside SMOOTHING_S, so the time-based fallback never has anything to do. This is what the
  // eight golden-vector traces already assert; restated here as the direct claim.
  const m = new PaceBandMonitor({ targetPaceSecKm: TARGET, tolerance: 0.06 });
  let firstEventT = null;
  for (let t = 0; t < 30; t++) {
    const ev = m.update(t, TARGET * 0.7, { paceTrusted: true, running: true });
    if (ev && firstEventT == null) firstEventT = t;
  }
  assert.ok(firstEventT != null && firstEventT < 10,
    `a normal 1 Hz feed must not be slowed down by the sparse-GPS fallback: first event at ${firstEventT}`);
  console.log(`  ok  a normal fix rate is unaffected (first tone at t=${firstEventT}s)`);
}

console.log('\nAll pace-monitor tests passed.');
