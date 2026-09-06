// The athlete's aerobic ceiling, read off their own sessions instead of an age formula.
//
// Why this exists
// ---------------
// Every zone edge in this plan descends from Tanaka's HRmax estimate, which has a between-person
// standard deviation of about 7 bpm. That is a whole zone width: the difference between prescribing
// easy and prescribing steady, for the rest of the plan, invisibly.
//
// The usual fix is a graded ramp test to exhaustion. That is the wrong instrument here for a reason
// that is not about willpower: this athlete cannot yet hold Z2 for twenty-six minutes, and a
// near-maximal test on an unadapted musculoskeletal system inside the bone-vulnerable window is a
// poor trade for a number that can be obtained another way.
//
// It can be obtained another way. The first ventilatory threshold shows up in ordinary training as
// the heart rate above which the athlete stops getting proportionate speed for their beats. Below
// it, metres travelled per heartbeat is roughly flat across heart-rate bands; above it, it falls
// away. On this athlete's 5 September session, first half only:
//
//     HR 130-134   0.80 m/beat        HR 145-149   0.82
//     HR 135-139   0.78               HR 150-154   0.74   <- the roll-off
//     HR 140-144   0.79
//
// which puts his threshold around 150, against the 155 the age formula prescribed.
//
// The one trap, and it is the whole reason this module is careful
// ---------------------------------------------------------------
// Cardiac drift produces exactly the same signature. Later in a session heart rate is higher AND
// pace is slower, so a whole-session average shows efficiency falling with heart rate whether or not
// a threshold exists. Measured over his full session the roll-off appeared at 150 -- and also, much
// more weakly, at 115, which is nonsense.
//
// So only the FIRST HALF is used. Within it, fatigue cannot explain a roll-off, and his data holds
// 0.78-0.82 flat from 130 to 149 before dropping. The second half of the same session sits at
// 0.63-0.67 across every band uniformly, which is what drift looks like and is correctly ignored.

/** Heart-rate bands are this wide. Narrow enough to locate a threshold, wide enough to fill. */
export const BAND_BPM = 5;

/** A band with fewer samples than this is not a measurement. */
export const MIN_SAMPLES_PER_BAND = 25;

/** Efficiency must fall by at least this fraction for a band to count as past the threshold. */
export const ROLLOFF_FRACTION = 0.06;

/** Bands below this are walking, not running, and belong to a different relationship. */
export const MIN_SPEED_MS = 1.0;

/**
 * Heart rate lags effort. Pair each speed with the heart rate it produced, not the one it followed.
 *
 * Twenty seconds is the standard first-order lag for a step change in running effort. Getting this
 * wrong smears every band into its neighbours and flattens the roll-off being looked for.
 */
export const HR_LAG_S = 20;

/** How many sessions must agree before the measured number is trusted over the age formula. */
export const MIN_SESSIONS = 2;

/// Named for this module: every module inlines into one scope in the built page, so a bare `mean`
/// collides with run-stats.js and the whole page stops parsing. The build checks for exactly that.
const meanOf = xs => xs.reduce((a, b) => a + b, 0) / xs.length;

/**
 * Estimate the first ventilatory threshold from one session's samples.
 *
 * `samples` are `{t_s, speed_m_s, hr_bpm}` as the app records them. Returns
 * `{bpm, bands, confidence}` or null when the session cannot answer -- too short, no heart rate, or
 * not enough running spread across enough bands to see a roll-off at all.
 *
 * `bpm` is the TOP of the last band whose efficiency was still holding: the highest heart rate at
 * which the athlete was still getting full value for their beats.
 */
export function estimateThreshold(samples, { lagS = HR_LAG_S } = {}) {
  const ss = (samples || []).filter(s => s && s.t_s != null).slice().sort((a, b) => a.t_s - b.t_s);
  if (ss.length < 300) return null;

  // First half only. See the module note: drift is indistinguishable from a threshold in a whole
  // session, and the first half is where fatigue cannot be the explanation.
  const midT = ss[0].t_s + (ss[ss.length - 1].t_s - ss[0].t_s) / 2;
  const byT = new Map(ss.map(s => [s.t_s, s]));

  const bands = new Map();
  for (const s of ss) {
    if (s.t_s > midT) break;
    if (!(s.speed_m_s > MIN_SPEED_MS)) continue;
    const later = byT.get(s.t_s + lagS);
    const hr = later && later.hr_bpm;
    if (!hr) continue;
    const key = Math.floor(hr / BAND_BPM) * BAND_BPM;
    if (!bands.has(key)) bands.set(key, []);
    bands.get(key).push(s.speed_m_s);
  }

  const rows = [...bands.entries()]
    .filter(([, xs]) => xs.length >= MIN_SAMPLES_PER_BAND)
    .map(([lo, xs]) => {
      const v = meanOf(xs);
      // Metres per beat: the speed bought with those heartbeats. Band midpoint for the rate.
      return { lo, hi: lo + BAND_BPM - 1, n: xs.length, speedMS: v,
               mPerBeat: (v * 60) / (lo + BAND_BPM / 2) };
    })
    .sort((a, b) => a.lo - b.lo);
  if (rows.length < 3) return null;

  // Walk up from the best band. The threshold is the top of the last band still holding its value,
  // and the reference is the best seen so far rather than the immediately preceding band -- a single
  // noisy band should not be able to redefine "holding" for everything above it.
  let best = rows[0].mPerBeat;
  let ceiling = null;
  for (let i = 1; i < rows.length; i++) {
    if (rows[i].mPerBeat > best) { best = rows[i].mPerBeat; continue; }
    if (rows[i].mPerBeat < best * (1 - ROLLOFF_FRACTION)) { ceiling = rows[i - 1].hi; break; }
  }
  if (ceiling == null) return null;          // never rolled off: he stayed under it the whole time

  return {
    bpm: ceiling,
    // How much of the session is behind the number. Two bands either side of the roll-off is a
    // usable reading; one sparse band on each side is a coincidence.
    confidence: Math.min(1, rows.reduce((a, r) => a + r.n, 0) / 600),
    bands: rows,
  };
}

/**
 * Combine per-session estimates into the number the coach should actually use.
 *
 * `history` is a list of `{bpm, confidence, at}`, newest last. The median is taken rather than the
 * mean, and rather than the latest: a single session run in heat, or on tired legs, or with a badly
 * seated optical sensor, produces a low estimate, and a training ceiling that drops because of one
 * hot Tuesday would ratchet the athlete downward for no physiological reason.
 *
 * Returns null until MIN_SESSIONS agree, so the age formula keeps governing until there is
 * something better -- an unmeasured ceiling is a worse failure than a slightly wrong one.
 */
export function ceilingFrom(history, { minSessions = MIN_SESSIONS } = {}) {
  const usable = (history || []).filter(h => h && h.bpm > 0 && (h.confidence ?? 1) >= 0.5);
  if (usable.length < minSessions) return null;
  // The most recent six, so the number follows fitness instead of averaging over a whole block.
  const recent = usable.slice(-6).map(h => h.bpm).sort((a, b) => a - b);
  const mid = recent.length % 2
    ? recent[(recent.length - 1) / 2]
    : Math.round((recent[recent.length / 2 - 1] + recent[recent.length / 2]) / 2);
  return { bpm: mid, sessions: usable.length,
           source: `measured over ${usable.length} session${usable.length === 1 ? '' : 's'}` };
}
