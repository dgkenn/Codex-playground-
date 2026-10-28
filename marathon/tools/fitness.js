// Aerobic fitness from a session: the heart rate it takes to run a fixed pace on the flat.
//
// Why this exists
// ---------------
// "There should be some metric that accounts for pace, incline over heart rate." The obvious ones
// fail on this athlete's sessions:
//
// - Speed over heart rate (the efficiency factor, beats per mile) counts walking, ignores hills, and
//   reads the heart rate of the moment against the effort of the moment. In a 90-second block the
//   heart never catches up: at the end of a block heart rate is still describing the walk before it.
//   Sessions with different block lengths, ceilings or paces are then not comparable at all.
// - Heart rate at a fixed pace, the classic submaximal fitness test (Buchheit 2014), needs a steady
//   state that two-minute blocks never reach.
//
// So the steady state is modelled instead of waited for:
//
// 1. **Effort.** Every second's effort is its metabolic power: speed times the energy cost of
//    moving at that grade, from Minetti et al. 2002 (J Appl Physiol 93:1039) -- the running polynomial
//    at jogging speed, the walking one below the gait transition. Hills are in the effort, not in the
//    heart rate's excuses.
// 2. **Lag.** Heart rate follows effort as a first-order response with a time constant, plus the
//    armband's own reporting delay.
// 3. **One number.** Heart rate = offset + gain x (lagged effort). With the shape (time constant,
//    delay, gain) held fixed, the session's offset is the only unknown, and the offset plus the gain
//    times the effort of 12:00/mi on the flat is that session's heart rate for that pace, had it run
//    long enough to settle. Lower is fitter.
//
// Only the first 15 minutes from the first run block are used: cardiac drift adds heart rate the
// longer a session goes, and a longer session must not read as a less fit one.
//
// The shape was fitted on this athlete's own sessions, 6-26 October (pooled, within-session):
// time constant 80 s, delay 10 s, 12.1 bpm per W/kg. With it, 9, 22 and 26 October read 168, 173
// and 171 -- about +-3 bpm between sessions at much the same fitness. 6 and 13 October are refused
// (under five minutes at jogging speed in the window) and 24 October too (a third of its heart rate
// missing): a number from those would be a guess.

/// 12:00 per mile, the reference: inside the paces this athlete actually runs, so nothing is
/// extrapolated far.
export const REF_SPEED_MS = 1609.344 / 720;
export const FIT_TAU_S = 80;
export const FIT_DELAY_S = 10;
export const FIT_GAIN = 12.1;              // bpm per W/kg
export const FIT_WINDOW_S = 900;
/// A window with less heart rate than this, less running, or a worse fit than this says nothing.
export const MIN_HR_COVERAGE = 0.8;
export const MIN_RUNNING_S = 300;
export const MAX_RESIDUAL_SD = 12;
const GAIT_MS = 1.95;

const runCost = i => 155.4 * i ** 5 - 30.4 * i ** 4 - 43.3 * i ** 3 + 46.3 * i * i + 19.5 * i + 3.6;
const walkCost = i => 280.5 * i ** 5 - 58.7 * i ** 4 - 76.8 * i ** 3 + 51.9 * i * i + 19.6 * i + 2.5;

/** Metabolic power in W/kg of moving at `speed` m/s up `grade` (rise/run). Minetti 2002. */
export function metabolicPower(speed, grade = 0) {
  if (!(speed > 0)) return 0;
  const i = Math.max(-0.3, Math.min(0.3, grade || 0));
  return (speed >= GAIT_MS ? runCost(i) : walkCost(i)) * speed;
}

/**
 * The session's heart rate for 12:00/mi on the flat, settled. `samples` are the page's
 * `{t_s, hr_bpm, speed_m_s, grade, label}` at any spacing. Returns
 * `{hrAtRef, ciBpm, residualSd, coverage, runningS, ok, why}`; `hrAtRef` is null when `ok` is false.
 */
export function aerobicIndex(samples, { tauS = FIT_TAU_S, delayS = FIT_DELAY_S, gain = FIT_GAIN,
                                        windowS = FIT_WINDOW_S } = {}) {
  const ss = (samples || []).filter(s => s && s.t_s != null).sort((a, b) => a.t_s - b.t_s);
  const none = why => ({ hrAtRef: null, ok: false, why });
  if (ss.length < 10) return none('too short');
  const runAt = (ss.find(s => s.label === 'run')
                 || ss.find((s, k) => s.speed_m_s >= GAIT_MS && ss.slice(k, k + 30).every(x => x.speed_m_s >= GAIT_MS)) || {}).t_s;
  if (runAt == null) return none('no running');
  const from = runAt - 60, to = runAt + windowS;

  // Lagged effort at every sample: first-order filter, restarted after a gap in the recording.
  const lagged = [];
  let x = null, prevT = null;
  for (const s of ss) {
    const p = metabolicPower(s.speed_m_s, s.grade);
    const dt = prevT == null ? 0 : s.t_s - prevT;
    x = (x == null || dt > 30) ? p : x + (p - x) * (1 - Math.exp(-dt / tauS));
    lagged.push([s.t_s, x]);
    prevT = s.t_s;
  }
  const effortAt = t => {
    let lo = 0, hi = lagged.length - 1;
    if (t < lagged[0][0]) return null;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (lagged[m][0] <= t) lo = m; else hi = m - 1; }
    return lagged[lo][1];
  };

  const inWin = ss.filter(s => s.t_s >= from && s.t_s <= to);
  const step = (() => {
    const d = inWin.slice(1).map((s, k) => s.t_s - inWin[k].t_s).filter(v => v > 0).sort((a, b) => a - b);
    return d.length ? d[d.length >> 1] : 1;
  })();
  const span = Math.max(step, (inWin.length ? inWin[inWin.length - 1].t_s : from) - from);
  const res = [];
  let runningS = 0;
  for (const s of inWin) {
    if (s.speed_m_s >= GAIT_MS) runningS += step;
    if (s.hr_bpm == null || !(s.hr_bpm > 0)) continue;
    const e = effortAt(s.t_s - delayS);
    if (e != null) res.push(s.hr_bpm - gain * e);
  }
  const coverage = Math.min(1, res.length * step / span);   // a paused page leaves fewer seconds than samples
  if (runningS < MIN_RUNNING_S) return { ...none('under 5 minutes of running in the first 15'), runningS, coverage };
  if (coverage < MIN_HR_COVERAGE) return { ...none('heart rate missing for too much of it'), runningS, coverage };
  const a = res.reduce((p, q) => p + q, 0) / res.length;
  const sd = Math.sqrt(res.reduce((p, q) => p + (q - a) ** 2, 0) / res.length);
  const out = {
    hrAtRef: Math.round(a + gain * metabolicPower(REF_SPEED_MS, 0)),
    // About one independent reading a minute: heart rate is that autocorrelated.
    ciBpm: Math.round(1.96 * sd / Math.sqrt(Math.max(1, span / 60))),
    residualSd: Math.round(sd * 10) / 10, coverage: Math.round(coverage * 100) / 100, runningS, ok: true, why: null,
  };
  if (sd > MAX_RESIDUAL_SD) return { ...out, hrAtRef: null, ok: false, why: 'heart rate did not follow the effort (sensor or GPS trouble)' };
  return out;
}
