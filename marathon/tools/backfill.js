// Filling a session's heart-rate holes from the armband's own memory.
//
// Why this exists
// ---------------
// On 13 October Polar Flow was opened ten minutes into a run and iOS froze this page for sixteen
// minutes: no samples, no heart rate, and a session that could not be judged. A page cannot stop iOS
// doing that. The armband can carry on regardless: Polar's offline recording writes heart rate to the
// band's own memory, it may run alongside the live heart-rate stream (the one data type Polar allows
// both ways at once), and it keeps recording through a lost connection. polar-offline.js starts it
// at Start and reads it back afterwards; this file puts what it read into the archived session.
//
// The clock problem, and why it is solved by the data rather than by trusting a clock: the band
// stamps a recording with its own wall clock, which nothing here has set, and whether that stamp is
// UTC or local time is not something the SDK documents. Rather than guess, the band's trace is slid
// against the heart rate the page did record -- the same band, the same heart, through the live
// stream -- and the offset where the two agree is the offset. Whole-hour candidates (a time zone, a
// daylight-saving change) and then the seconds around each. Agreement must be close (within a few
// beats on average over at least two minutes), or nothing is filled: a hole is better than a
// plausible-looking heart rate from the wrong minute.
//
// Only holes are filled. A second the page recorded keeps the page's reading; the band's memory
// fills seconds that have no heart rate and grid points the page never wrote at all. Speed, grade
// and motion stay empty there -- they came from the phone, which was asleep.

export const BackfillDefaults = {
  /// Whole-hour offsets tried either side of the band's stamp: every time zone there is.
  maxHours: 14,
  /// Seconds tried around each hour.
  fineS: 120,
  /// Grid points (5 s each) that must overlap: two minutes.
  minOverlap: 24,
  /// Mean absolute disagreement allowed at the best offset, bpm. The two are the same band's
  /// output through two paths; at the right offset they differ by a beat or two at most.
  maxMeanDiffBpm: 3,
};

/** {second -> hr} from the band's samples ({t: ms, hr}). */
function bySecond(samples) {
  const m = new Map();
  for (const s of samples) if (s.hr > 0) m.set(Math.round(s.t / 1000), s.hr);
  return m;
}

const at = (m, sec) => m.get(sec) ?? m.get(sec - 1) ?? m.get(sec + 1) ?? null;

/**
 * The offset (ms, added to the band's times) that lines its trace up with the session's own heart
 * rate, or null when there is no offset they agree at. `session` is compact (session-format.js).
 */
export function alignOffline(session, samples, opts = {}) {
  const cfg = { ...BackfillDefaults, ...opts };
  const m = bySecond(samples);
  if (!m.size) return null;
  const t0s = Date.parse(session.started_at) / 1000 + (session.t0 || 0);
  const pts = [];
  session.t.forEach((t, i) => { if (session.hr[i] != null) pts.push([Math.round(t0s + t), session.hr[i]]); });
  if (pts.length < cfg.minOverlap) return null;
  let best = null;
  for (let h = -cfg.maxHours; h <= cfg.maxHours; h++) {
    for (let d = -cfg.fineS; d <= cfg.fineS; d++) {
      const off = h * 3600 + d;               // session second = band second + off
      let n = 0, sum = 0;
      for (const [sec, hr] of pts) {
        const b = at(m, sec - off);
        if (b != null) { n += 1; sum += Math.abs(b - hr); }
      }
      if (n < cfg.minOverlap) continue;
      const mean = sum / n;
      if (!best || mean < best.meanDiff || (mean === best.meanDiff && n > best.overlap)) {
        best = { offsetMs: off * 1000, meanDiff: mean, overlap: n };
      }
    }
  }
  return best && best.meanDiff <= cfg.maxMeanDiffBpm ? best : null;
}

/**
 * A copy of the compact session with its heart-rate holes filled from the band, and a report.
 * Returns {session, report}; `report.filled` is 0 (and the session unchanged) when the band's
 * trace could not be lined up or had nothing for the holes.
 */
export function backfillSession(session, samples, opts = {}) {
  const align = alignOffline(session, samples, opts);
  if (!align) return { session, report: { filled: 0, inserted: 0, reason: 'the band\'s trace did not line up with this session' } };
  const m = bySecond(samples);
  const t0s = Date.parse(session.started_at) / 1000 + (session.t0 || 0);
  const off = align.offsetMs / 1000;
  const bandAt = t => at(m, Math.round(t0s + t - off));
  const step = session.step_s || 5;

  const rows = session.t.map((t, i) => ({ t, hr: session.hr[i], spd: session.spd[i],
                                          grd: session.grd[i], acc: session.acc[i] }));
  let filled = 0, inserted = 0;
  for (const r of rows) {
    if (r.hr == null) { const b = bandAt(r.t); if (b != null) { r.hr = b; filled += 1; } }
  }
  // Grid points the page never wrote: the phone was asleep. The band was not.
  const have = new Set(rows.map(r => r.t));
  const last = rows.length ? rows[rows.length - 1].t : 0;
  for (let t = 0; t <= last; t += step) {
    if (have.has(t)) continue;
    // Only inside a real hole: no recorded point within half a step either side.
    if (rows.some(r => Math.abs(r.t - t) < step)) continue;
    const b = bandAt(t);
    if (b != null) { rows.push({ t, hr: b, spd: null, grd: null, acc: null }); inserted += 1; }
  }
  rows.sort((a, b) => a.t - b.t);
  const out = { ...session, t: rows.map(r => r.t), hr: rows.map(r => r.hr), spd: rows.map(r => r.spd),
                grd: rows.map(r => r.grd), acc: rows.map(r => r.acc) };
  const report = { filled, inserted, offsetS: Math.round(off), meanDiffBpm: Math.round(align.meanDiff * 10) / 10,
                   overlap: align.overlap };
  if (filled || inserted) out.backfill = { source: 'armband memory', ...report };
  return { session: out, report };
}
