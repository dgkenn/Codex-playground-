// Getting a run off the phone, in something a person can actually paste.
//
// The problem this solves
// -----------------------
// A forty-five minute session exports to 333 kB of JSON: 340,000 characters, one object per second
// with the same six keys repeated three thousand times. That is not a file, it is a wall. Pasting it
// into a chat window crashed the chat window. Pasting it into a notes app produced a screenful of
// punctuation. And the autosave, which serialised the whole thing every two seconds, was doing ten
// megabytes of `JSON.stringify` a minute on a phone — which is itself a plausible reason iOS killed
// the tab and took the session with it.
//
// So the wire format is not the working format. Compacted:
//
//   * **Columnar.** One array per field instead of one object per second. The key names appear once
//     rather than 2,700 times, which is most of the size on its own.
//   * **Integers.** Speed to a decimetre per second, grade to a ten-thousandth. Both are already
//     finer than the sensors that produced them; the extra decimal places were noise being stored
//     at full price.
//   * **Downsampled.** One point every few seconds rather than every second. Heart rate has a time
//     constant near forty-five seconds and GPS speed is smoothed over fifteen, so a five-second
//     grid loses nothing either signal actually contained.
//   * **Labels as changes.** "stage_3" written once with the second it started, not repeated for
//     each of its 240 seconds.
//
// What is deliberately NOT done: the summary statistics are computed from the FULL recording before
// any of this, and travel alongside. Downsampling changes what you can re-derive later; it must not
// change what the run said, so the numbers are computed once at full resolution and carried.

export const COMPACT_VERSION = 2;

/// The grid the trace is resampled onto. Five seconds against a heart-rate time constant of
/// forty-five and a GPS smoothing window of fifteen: below the resolution of either signal.
export const STEP_S = 5;
/// The route is for drawing a map, not for measuring, so it can be coarser still.
export const ROUTE_STEP_S = 15;

const round = (v, dp) => (v == null ? null : Math.round(v * 10 ** dp) / 10 ** dp);

/**
 * Compact a full session for transport.
 *
 * `stats` is passed in rather than recomputed, because it must describe the recording as it was
 * measured — at one hertz, with every sample — not the thinned version that travels.
 */
export function compact(session, { stats = null, stepS = STEP_S } = {}) {
  const samples = session.samples || [];
  const t = [], hr = [], spd = [], grd = [], acc = [], labels = [];
  let lastLabel = null;

  // Nearest sample to each grid point rather than an average: averaging heart rate across a stage
  // boundary invents a reading that was never taken, and the stage boundaries are what the analysis
  // cuts on.
  const byT = new Map();
  for (const s of samples) byT.set(s.t_s, s);
  const t0 = samples.length ? samples[0].t_s : 0;
  const tEnd = samples.length ? samples[samples.length - 1].t_s : 0;

  for (let k = t0; k <= tEnd; k += stepS) {
    let s = byT.get(k);
    if (!s) {
      for (let d = 1; d < stepS && !s; d++) s = byT.get(k + d) || byT.get(k - d);
    }
    // A grid point with no sample near it is a genuine hole in the recording and stays a hole.
    if (!s) continue;
    t.push(s.t_s - t0);
    hr.push(s.hr_bpm == null ? null : Math.round(s.hr_bpm));
    spd.push(s.speed_m_s == null ? null : Math.round(s.speed_m_s * 10));
    grd.push(s.grade == null ? null : Math.round(s.grade * 10000));
    acc.push(s.accel_sd_g == null ? null : Math.round(s.accel_sd_g * 100));
    const lab = s.label || '';
    if (lab !== lastLabel) { labels.push([s.t_s - t0, lab]); lastLabel = lab; }
  }

  const route = [];
  const src = session.route || [];
  for (let i = 0; i < src.length; i += ROUTE_STEP_S) {
    const [la, lo] = src[i];
    route.push([round(la, 5), round(lo, 5)]);
  }

  return {
    schema_version: COMPACT_VERSION,
    started_at: session.started_at,
    ...(session.age != null ? { age: session.age } : {}),
    ...(session.hr_rest != null ? { hr_rest: session.hr_rest } : {}),
    title: session.title || null,
    mode: session.mode || null,
    surface: session.surface || 'road',
    notes: session.notes || '',
    // Computed at full resolution, before any of this. See the note at the top of the file.
    stats: stats || session.stats || null,
    step_s: stepS,
    t0,
    n_full: samples.length,
    t, hr, spd, grd, acc,
    labels,
    route,
  };
}

/**
 * Expand a compact session back into the sample-per-second shape the engine reads.
 *
 * Only the recorded grid points come back — the seconds between them were never transmitted and are
 * not invented here. An importer that interpolated would be manufacturing heart rates, which is the
 * one thing this whole codebase refuses to do.
 */
export function expand(c) {
  if (!c || c.schema_version !== COMPACT_VERSION) return null;
  const labelAt = k => {
    let lab = '';
    for (const [at, l] of c.labels || []) { if (at <= k) lab = l; else break; }
    return lab;
  };
  const samples = (c.t || []).map((k, i) => ({
    t_s: c.t0 + k,
    hr_bpm: c.hr[i] == null ? null : c.hr[i],
    speed_m_s: c.spd[i] == null ? null : c.spd[i] / 10,
    grade: c.grd[i] == null ? null : c.grd[i] / 10000,
    accel_sd_g: c.acc && c.acc[i] != null ? c.acc[i] / 100 : null,
    label: labelAt(k),
  }));
  return {
    schema_version: 1,
    started_at: c.started_at,
    ...(c.age != null ? { age: c.age } : {}),
    ...(c.hr_rest != null ? { hr_rest: c.hr_rest } : {}),
    samples,
    route: (c.route || []).map(([la, lo], i) => [la, lo, c.t0 + i * ROUTE_STEP_S, null]),
    resting_ppi_ms: [],
    surface: c.surface || 'road',
    strap_position: 'upper_arm',
    notes: c.notes || '',
  };
}

/** Rough size of a payload once serialised, for telling someone what they are about to copy. */
export const sizeKb = obj => Math.round(JSON.stringify(obj).length / 1024);
