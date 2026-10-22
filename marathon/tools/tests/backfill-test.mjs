// Filling a frozen page's holes from the band's memory, against a constructed run with the fault the
// 13 October session had: the page asleep for sixteen minutes in the middle.

import assert from 'node:assert/strict';
import { alignOffline, backfillSession } from '../backfill.js';

let seed = 3;
const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;

// A run/walk heart rate: warm-up, then blocks rising to ~150 and walks falling to ~125.
const hrAt = s => Math.round(s < 300 ? 100 + s / 30
  : (Math.floor((s - 300) / 180) % 2 === 0 ? 125 + Math.min(25, ((s - 300) % 180) / 5) : 150 - Math.min(25, ((s - 300) % 180) / 6)));

const started = '2026-10-13T20:18:52.000Z', startMs = Date.parse(started);
const DUR = 2700, GAP = [600, 1560];                 // asleep from 10 to 26 minutes

function session({ hrMissing = [] } = {}) {
  const t = [], hr = [], spd = [], grd = [], acc = [];
  for (let s = 0; s <= DUR; s += 5) {
    if (s >= GAP[0] && s < GAP[1]) continue;
    t.push(s); hr.push(hrMissing.some(([a, b]) => s >= a && s < b) ? null : hrAt(s));
    spd.push(20); grd.push(0); acc.push(10);
  }
  return { schema_version: 2, started_at: started, t0: 0, step_s: 5, t, hr, spd, grd, acc, labels: [[0, '']] };
}

/** The band's recording: 1 Hz from 20 s before Start to 30 s after, stamped `clockOffsetS` wrong. */
function band(clockOffsetS) {
  const out = [];
  for (let s = -20; s <= DUR + 30; s++) {
    out.push({ t: startMs + (s + clockOffsetS) * 1000, hr: hrAt(s) + (rnd() < 0.2 ? (rnd() < 0.5 ? -1 : 1) : 0) });
  }
  return out;
}

{
  // The band's clock an hour and 37 s out (a time zone and a drift): found from the data.
  const s = session(), b = band(3600 + 37);
  const a = alignOffline(s, b);
  assert.ok(a, 'aligned');
  assert.equal(a.offsetMs, -(3600 + 37) * 1000, `offset ${a.offsetMs}`);
  assert.ok(a.meanDiff < 0.5, `agreement ${a.meanDiff}`);
  const { session: out, report } = backfillSession(s, b);
  assert.equal(report.inserted, (GAP[1] - GAP[0]) / 5, `the whole sixteen minutes: ${report.inserted}`);
  const i = out.t.indexOf(900);
  assert.equal(out.hr[i], hrAt(900) + (out.hr[i] - hrAt(900)), 'a reading inside the hole');
  assert.ok(Math.abs(out.hr[i] - hrAt(900)) <= 1, `and the right one: ${out.hr[i]} vs ${hrAt(900)}`);
  assert.equal(out.spd[i], null, 'speed stays empty where the phone was asleep');
  assert.deepEqual(out.t, [...out.t].sort((x, y) => x - y), 'in time order');
  assert.equal(out.backfill.source, 'armband memory');
  console.log(`  ok  a sixteen-minute freeze is filled from the band (${report.inserted} points), its clock ${-report.offsetS} s out found from the data`);
}

{
  // Seconds the page recorded without heart rate (the band out of reach) are filled; seconds with a
  // reading keep it.
  const s = session({ hrMissing: [[1800, 1900]] });
  s.hr[s.t.indexOf(2000)] = 77;                       // a recorded reading the band disagrees with
  const { session: out, report } = backfillSession(s, band(0));
  assert.equal(report.filled, 20);
  assert.equal(out.hr[out.t.indexOf(1850)], hrAt(1850) + (out.hr[out.t.indexOf(1850)] - hrAt(1850)));
  assert.equal(out.hr[out.t.indexOf(2000)], 77, 'the page\'s own reading is never overwritten');
  console.log('  ok  heart-rate holes in recorded seconds are filled; recorded readings are kept');
}

{
  // A band trace from a different run: nothing lines up, nothing is filled.
  const s = session();
  const other = band(0).map(x => ({ t: x.t, hr: 70 + Math.round(30 * rnd()) }));
  const { session: out, report } = backfillSession(s, other);
  assert.equal(report.filled + report.inserted, 0);
  assert.equal(out, s, 'the session is returned untouched');
  console.log('  ok  a trace that does not line up fills nothing');
}

console.log('\nAll backfill tests passed.');
