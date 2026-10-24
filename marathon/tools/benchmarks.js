// Benchmarks on the way to a continuous 5K, and when to expect it.
//
// Two kinds of evidence, used differently:
//
//   * Passive, every session: what the run/walk sessions already measure (time to the ceiling, the
//     walk back down to the floor, metres per heartbeat). Free, and noisy; they are trended.
//   * Active, occasionally: a 2 km time trial, the plan's own first performance test (plan.py
//     `_time_trial_2000m`: about 11-12 minutes for a beginner, inside Riegel's validated range, a
//     shorter maximal effort on unprepared tissue than a 5K). It gives two numbers nothing else can:
//       - a predicted 5K time (Riegel: T2 = T1 x (D2/D1)^1.06), the "how fast" half of the goal;
//       - a measured heart-rate maximum. The age formula's spread is 7-10 bpm, and everything -- the
//         walk floor, the zones, the automatic ceiling -- is a percentage of it. A maximal 2 km takes
//         heart rate to within a few beats of maximum, so its peak is a floor under the true value:
//         if it beats the formula, the formula was low.
//     It is first due when the ladder reaches 10-minute blocks (enough continuous running to hold a
//     hard 11 minutes), then every three weeks.
//
// And the goal itself: the first run with 5 km inside one continuous running block. It is spotted
// live (and said out loud) and from the record afterwards.

export const BENCH_KEY = 'band.benchmarks';
export const TRIAL_M = 2000;
export const GOAL_M = 5000;
/// Riegel's fatigue exponent.
export const RIEGEL_K = 1.06;
/// The trial is first worth running once blocks are this long, then every TRIAL_EVERY_DAYS.
export const TRIAL_FROM_RUN_MIN = 10;
export const TRIAL_EVERY_DAYS = 21;

export function riegel(timeS, fromM, toM, k = RIEGEL_K) {
  return timeS * (toM / fromM) ** k;
}

/** The highest peak heart rate any time trial has recorded, or null. */
export function measuredMaxHr(benchmarks) {
  const peaks = (benchmarks || []).filter(b => b.kind === 'trial' && b.peakHr > 0).map(b => b.peakHr);
  return peaks.length ? Math.max(...peaks) : null;
}

/**
 * Whether a time trial is due: blocks of at least TRIAL_FROM_RUN_MIN, and none in the last
 * TRIAL_EVERY_DAYS. Returns {due, why}.
 */
export function trialDue({ runMin, benchmarks = [], now = new Date() }) {
  if (!(runMin >= TRIAL_FROM_RUN_MIN)) {
    return { due: false, why: `first time trial at ${TRIAL_FROM_RUN_MIN}-minute blocks` };
  }
  const last = (benchmarks || []).filter(b => b.kind === 'trial').map(b => new Date(b.at)).sort((a, b) => b - a)[0];
  if (last && now - last < TRIAL_EVERY_DAYS * 86400000) {
    const next = new Date(last.getTime() + TRIAL_EVERY_DAYS * 86400000);
    return { due: false, why: 'next time trial', nextAt: next.toISOString() };
  }
  return { due: true, why: last ? 'three weeks since the last one' : 'you can hold ten minutes now' };
}

/**
 * The longest stretch of continuous running in a session, in metres and seconds: consecutive samples
 * labelled 'run' (or, with no labels, moving faster than walking) with speed, gaps under 10 s.
 * `samples` are the page's `{t_s, speed_m_s, label}`.
 */
export function longestContinuous(samples, { walkMs = 1.9 } = {}) {
  let best = { m: 0, s: 0 }, cur = { m: 0, s: 0 }, prevT = null;
  for (const x of samples || []) {
    const running = x.label ? x.label === 'run' : (x.speed_m_s || 0) >= walkMs;
    const dt = prevT == null ? 0 : x.t_s - prevT;
    prevT = x.t_s;
    if (!running || dt > 10) { cur = { m: 0, s: 0 }; if (!running) continue; }
    if (x.speed_m_s > 0 && dt > 0) { cur.m += x.speed_m_s * dt; cur.s += dt; }
    if (cur.m > best.m) best = { ...cur };
  }
  return best;
}

/**
 * When the 5K step can be reached from here, on each track, assuming a run every `everyDays` and
 * every one good. A projection, not a promise: it is the fastest the rules allow, and the body
 * decides the rest. `step` is progression.js stepLadder; `state` its stored state.
 */
export function projectGoal({ step, state, totalsMin, longestRecentS = 0, now = new Date(), everyDays = 2,
                              advance = 'advance' }) {
  const out = {};
  for (const light of ['green', 'amber']) {
    let st = { ...(state || { rung: 0 }) };
    let longest = longestRecentS;
    let d = 0;
    const top = totalsMin.length - 1;
    for (; d <= 365 && st.rung < top; d += everyDays) {
      longest = Math.max(longest, totalsMin[st.rung] * 60);
      st = step(st, advance, { ladderLength: totalsMin.length, now: new Date(now.getTime() + d * 86400000),
                               light, totalsMin, longestRecentS: longest });
    }
    out[light] = st.rung >= top ? new Date(now.getTime() + d * 86400000).toISOString() : null;
  }
  return out;
}

/**
 * A finished time trial from the run's own record: the time at which `distM` was reached (between
 * the two ticks either side of it), and the heart rate over that time. `ticks` are `[t_s, metres]`
 * pairs (the fused distance each second); `samples` the page's `{t_s, hr_bpm}`. Null if the distance
 * was never reached.
 */
export function summariseTrial(ticks, samples, distM = TRIAL_M) {
  let timeS = null;
  for (let i = 1; i < ticks.length; i++) {
    const [t0, d0] = ticks[i - 1], [t1, d1] = ticks[i];
    if (d0 < distM && d1 >= distM) { timeS = t0 + (t1 - t0) * (distM - d0) / Math.max(1e-9, d1 - d0); break; }
  }
  if (timeS == null) return null;
  const hrs = (samples || []).filter(x => x.t_s <= timeS && x.hr_bpm > 0).map(x => x.hr_bpm);
  return {
    timeS: Math.round(timeS),
    avgHr: hrs.length ? Math.round(hrs.reduce((a, b) => a + b, 0) / hrs.length) : null,
    peakHr: hrs.length ? Math.max(...hrs) : null,
    predicted5kS: Math.round(riegel(timeS, distM, GOAL_M)),
  };
}
