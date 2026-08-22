// The wire format, which exists because the old one was unusable.
//
// A 45-minute session exported to 345 kB. Pasting that into a chat crashed the chat; pasting it into
// a notes app produced a screen of punctuation; and the autosave serialised the whole thing every
// two seconds, which is ten megabytes a minute of string building on a phone and a plausible reason
// iOS killed the tab and took the run with it.
//
// The risk in fixing that is obvious: a format that loses the run while making it smaller. So these
// tests are mostly about what must survive — the stage labels the analysis cuts on, the holes where
// the recording stopped, and the summary statistics, which are computed at full resolution BEFORE
// anything is thinned and must not be recomputed from the thinned copy.

import assert from 'node:assert/strict';
import { compact, expand, sizeKb, COMPACT_VERSION, STEP_S } from '../session-format.js';
import { runStats } from '../run-stats.js';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ENGINE = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'engine');

function session(n, { label = i => `stage_${1 + Math.floor(i / 240)}`, hr = i => 140 + (i % 9),
                      speed = () => 2.8, gap = null } = {}) {
  const samples = [];
  for (let i = 0; i < n; i++) {
    if (gap && i >= gap[0] && i < gap[1]) continue;         // a hole in the recording
    samples.push({
      t_s: i, hr_bpm: hr(i), speed_m_s: speed(i),
      accel_sd_g: 0.3, grade: 0.01, label: label(i),
    });
  }
  return {
    schema_version: 1, started_at: '2026-08-19T18:00:00.000Z', age: 30, hr_rest: 55,
    samples, route: samples.map((s, i) => [42.35 - i * 2e-5, -71.105, s.t_s, 12.3]),
    resting_ppi_ms: [], surface: 'road', strap_position: 'upper_arm', notes: 'n',
  };
}

// --- the point of the exercise -------------------------------------------------------------------

{
  const full = session(45 * 60);
  const c = compact(full, { stats: runStats(full.samples, { unit: 'mi' }) });
  const big = sizeKb(full), small = sizeKb(c);
  assert.ok(small < 30, `${small} kB is still too big to paste into a chat window`);
  assert.ok(small < big / 10, `${small} kB vs ${big} kB is not a big enough reduction to matter`);
  console.log(`  ok  a 45-minute session compacts from ${big} kB to ${small} kB`);
}

// --- what must survive ---------------------------------------------------------------------------

{
  // The stage labels are what the engine's analysis groups by. A compaction that loses them turns an
  // hour on a treadmill into one undifferentiated blob and the session has to be run again.
  const full = session(30 * 60);
  const c = compact(full, {});
  const back = expand(c);
  const labels = [...new Set(back.samples.map(s => s.label))];
  assert.deepEqual(labels, ['stage_1', 'stage_2', 'stage_3', 'stage_4', 'stage_5', 'stage_6',
                            'stage_7', 'stage_8']);
  // Stored as changes, not repeated per second — that is most of the saving.
  assert.equal(c.labels.length, 8, `labels stored as ${c.labels.length} entries`);
  // And each label must start where it actually started, not at the nearest grid point.
  assert.equal(c.labels[1][0], 240, `stage_2 starts at ${c.labels[1][0]}s, should be 240`);
  console.log(`  ok  stage labels survive as ${c.labels.length} changes rather than ${full.samples.length} repeats`);
}

{
  // The values must come back as the same physical quantities, within the resolution claimed.
  const full = session(600, { speed: i => 2.63 + 0.4 * Math.sin(i / 40), hr: i => 138 + (i % 11) });
  const back = expand(compact(full, {}));
  for (const s of back.samples) {
    const orig = full.samples.find(x => x.t_s === s.t_s);
    assert.ok(orig, `t=${s.t_s} was invented`);
    assert.equal(s.hr_bpm, orig.hr_bpm, 'heart rate is stored exactly');
    // Speed to a decimetre per second: finer than GPS resolves.
    assert.ok(Math.abs(s.speed_m_s - orig.speed_m_s) <= 0.05,
      `speed ${s.speed_m_s} vs ${orig.speed_m_s}`);
    assert.ok(Math.abs(s.grade - orig.grade) <= 0.0001);
  }
  console.log('  ok  heart rate is exact and speed survives to a decimetre per second');
}

{
  // A hole in the recording must stay a hole. Filling it in would manufacture heart rates for
  // minutes that were never recorded, which is the one thing this codebase refuses to do.
  const full = session(1200, { gap: [400, 700] });
  const back = expand(compact(full, {}));
  const inGap = back.samples.filter(s => s.t_s >= 400 && s.t_s < 700);
  assert.equal(inGap.length, 0, `${inGap.length} samples invented inside a five-minute dropout`);
  assert.ok(back.samples.some(s => s.t_s < 400) && back.samples.some(s => s.t_s >= 700),
    'and the recording either side must survive');
  console.log('  ok  a dropout stays a dropout rather than being filled in');
}

{
  // The statistics are computed at full resolution and carried. Recomputing them from the thinned
  // copy would give slightly different numbers under the same names — the exact failure the engine
  // parity test exists to prevent, reintroduced by the transport layer.
  const full = session(40 * 60);
  const atFullRes = runStats(full.samples, { unit: 'mi' });
  const c = compact(full, { stats: atFullRes });
  assert.equal(c.stats.durationS, atFullRes.durationS);
  assert.equal(c.stats.efficiencyFactor, atFullRes.efficiencyFactor);
  assert.equal(c.n_full, full.samples.length,
    'and the compacted payload must say how many samples the recording really had');
  assert.ok(c.t.length < c.n_full / 4, 'while carrying far fewer of them');
  console.log(`  ok  statistics travel at full resolution alongside ${c.t.length} thinned points`);
}

// --- refusing to mislead --------------------------------------------------------------------------

{
  assert.equal(expand(null), null);
  assert.equal(expand({ schema_version: 1 }), null, 'a full payload is not a compact one');
  assert.equal(expand({ schema_version: 99 }), null, 'an unknown version must be refused, not guessed');
  const empty = compact({ samples: [], route: [] }, {});
  assert.equal(empty.t.length, 0);
  assert.equal(expand(empty).samples.length, 0);
  console.log('  ok  an unknown or empty payload is refused rather than half-read');
}

{
  // The grid must be the one it claims. A step that drifts would put stage boundaries in the wrong
  // place, and the boundaries are the whole value of a ramp test.
  const full = session(600);
  const c = compact(full, {});
  assert.equal(c.step_s, STEP_S);
  assert.equal(c.schema_version, COMPACT_VERSION);
  for (let i = 1; i < c.t.length; i++) {
    assert.equal(c.t[i] - c.t[i - 1], STEP_S, `grid drifted at point ${i}`);
  }
  console.log(`  ok  the trace sits on the ${STEP_S}-second grid it declares`);
}

// --- the other side of the wire --------------------------------------------------------------------

{
  // The format only exists to be read by the engine, so "it compacts" is half a claim. This hands a
  // real compacted payload to the Python importer and checks it comes back out as the run that went
  // in — stage labels intact, because those are what the analysis groups by.
  const full = session(30 * 60);
  const c = compact(full, { stats: runStats(full.samples, { unit: 'mi' }) });

  const out = execFileSync('python3', ['-c', `
import sys, json
sys.path.insert(0, ${JSON.stringify(ENGINE)})
from marathon_engine.calibration import load_recording
rec = load_recording(json.loads(sys.stdin.read()))
labels = sorted({s.label for s in rec.samples if s.label})
print(json.dumps({
  "samples": len(rec.samples),
  "labels": labels,
  "first_hr": rec.samples[0].hr_bpm,
  "first_speed": rec.samples[0].speed_m_s,
  "age": rec.age,
}))
`], { input: JSON.stringify(c), encoding: 'utf8' });
  const got = JSON.parse(out);

  assert.equal(got.samples, c.t.length, 'every transmitted point must arrive, and no others');
  assert.deepEqual(got.labels, ['stage_1', 'stage_2', 'stage_3', 'stage_4', 'stage_5', 'stage_6',
                                'stage_7', 'stage_8']);
  assert.equal(got.first_hr, full.samples[0].hr_bpm);
  assert.ok(Math.abs(got.first_speed - full.samples[0].speed_m_s) <= 0.05);
  assert.equal(got.age, 30);
  console.log(`  ok  the engine reads the compact export back as ${got.samples} samples `
            + `across ${got.labels.length} stages`);
}

console.log('\nAll session-format tests passed.');
