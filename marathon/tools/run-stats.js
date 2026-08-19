// What a run actually says, computed from the samples it recorded.
//
// Why these numbers and not others
// --------------------------------
// A beginner's first six months are decided by two questions, and almost nothing else: is the
// aerobic engine improving, and is the easy running actually easy. Distance and average pace answer
// neither — they move with terrain, weather, traffic lights and how much you were willing to hurt
// on the day, which is exactly the thing being trained away.
//
// So the headline numbers here are the ones that hold still:
//
//   * **Efficiency factor** — speed per heartbeat. The cleanest single progress signal there is:
//     the same pace at a lower heart rate, or a faster pace at the same one, is fitness and nothing
//     else. Only comparable between similar sessions in similar conditions, which is why it is
//     reported per session and never averaged across a week.
//   * **Beats per mile** — the same quantity upside down, and the one people find intuitive. It
//     falls as you get fitter. It is the number to watch.
//   * **Decoupling** — whether heart rate drifted up relative to pace across the run. Under 5% the
//     effort was genuinely aerobic; above it, the pace was too hot for the distance, whatever the
//     average said.
//   * **Time at or below the easy ceiling** — the compliance number. An athlete whose heart rate
//     reaches 180 inside four minutes does not need a faster plan, he needs the easy runs to be
//     easy, and this is the only number that says whether they were.
//   * **Longest continuous run block** — capacity, measured rather than self-reported. It is what
//     the run-walk ladder is entered on.
//
// Definitions match `marathon_engine.physiology` exactly — `efficiency_factor` and `decoupling` are
// ported line for line and checked against the Python by the parity suite. A second definition of
// "efficiency factor" that disagrees by 3% is worse than not having one.

/// Metres in a mile. Named in full because the page already declares a short `MI`, and two
/// `const` of the same name in one scope is a page that does not parse at all — the build now
/// checks for exactly that.
export const METRES_PER_MILE = 1609.344;

/// Below this a sample is standing still, not running slowly. Used for moving time and for the
/// continuous-block measurement.
export const MOVING_MS = 0.7;
/// A block only counts as *running* above this — about 12:00 per mile. Below it, walking.
export const JOG_MS = 2.24;
/// A gap longer than this breaks a continuous block, even if both sides are running.
export const BLOCK_GAP_S = 5;

const mean = xs => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

/** Speed per heartbeat, m/s per bpm scaled by 1000. Ported from physiology.efficiency_factor. */
export function efficiencyFactor(meanSpeedMS, meanHr) {
  if (!(meanHr > 0)) return null;
  return meanSpeedMS / meanHr * 1000;
}

/**
 * Aerobic decoupling as a fraction: `EF_first / EF_second - 1`.
 *
 * Positive means heart rate drifted up relative to pace. Ported from physiology.decoupling,
 * including its rule that only samples with both a positive speed and a positive heart rate count.
 */
export function decoupling(firstHalf, secondHalf) {
  const ef = pairs => {
    const good = pairs.filter(([s, h]) => s > 0 && h > 0);
    if (!good.length) return null;
    return efficiencyFactor(mean(good.map(p => p[0])), mean(good.map(p => p[1])));
  };
  const a = ef(firstHalf), b = ef(secondHalf);
  if (a == null || b == null || !(b > 0)) return null;
  return a / b - 1;
}

/**
 * Banister TRIMP: one number for how much the session cost.
 *
 * Weights time by heart-rate reserve exponentially, so ten minutes hard is worth far more than ten
 * minutes easy — which is the point, and why summed duration is a poor proxy for load. The 1.92
 * coefficient is the male form; the female form uses 1.67.
 */
export function trimp(minutes, meanHr, hrRest, hrMax, { male = true } = {}) {
  if (!(hrMax > hrRest) || meanHr == null) return null;
  const reserve = (meanHr - hrRest) / (hrMax - hrRest);
  if (!(reserve > 0)) return 0;
  const k = male ? 1.92 : 1.67;
  return minutes * reserve * 0.64 * Math.exp(k * reserve);
}

/** Split the run into per-unit splits, returning elapsed seconds and pace for each. */
export function splits(samples, everyM) {
  const out = [];
  let covered = 0, lastAt = 0, n = 0;
  let prevT = samples.length ? samples[0].t_s : 0;
  for (const s of samples) {
    const dt = Math.max(0, s.t_s - prevT);
    prevT = s.t_s;
    if (s.speed_m_s > 0) covered += s.speed_m_s * dt;
    while (covered >= (n + 1) * everyM) {
      n += 1;
      const took = s.t_s - lastAt;
      lastAt = s.t_s;
      out.push({ n, atS: s.t_s, tookS: took, paceSecKm: took / (everyM / 1000) });
    }
  }
  return out;
}

/**
 * The longest unbroken block of actual running, in seconds.
 *
 * Measured rather than asked for, because it is what the run-walk ladder is entered on and a
 * self-reported figure would quietly set the whole plan's starting point.
 */
export function longestRunBlock(samples) {
  let best = 0, cur = 0, prevT = null;
  for (const s of samples) {
    const running = s.speed_m_s != null && s.speed_m_s >= JOG_MS;
    const gap = prevT == null ? 0 : s.t_s - prevT;
    if (running && gap <= BLOCK_GAP_S) cur += gap || 1;
    else if (running) cur = 1;
    else cur = 0;
    if (cur > best) best = cur;
    prevT = s.t_s;
  }
  return best;
}

/**
 * Everything worth knowing about one run.
 *
 * `zones` is the five-zone model, so time-in-zone and the easy ceiling come from the athlete's own
 * numbers rather than from a constant. Absent, the heart-rate section still computes what it can.
 */
export function runStats(samples, {
  zones = null, hrRest = null, hrMax = null, unit = 'mi', tones = 0, male = true,
} = {}) {
  const ss = (samples || []).slice().sort((a, b) => a.t_s - b.t_s);
  if (!ss.length) return null;

  const spanS = ss[ss.length - 1].t_s - ss[0].t_s + 1;
  const moving = ss.filter(s => s.speed_m_s != null && s.speed_m_s >= MOVING_MS);
  const withHr = ss.filter(s => s.hr_bpm != null);
  const both = moving.filter(s => s.hr_bpm != null);

  // Distance from speed x elapsed rather than from the sample count, so a gap in the recording is a
  // gap in the distance too rather than being silently interpolated over.
  let distanceM = 0, prevT = ss[0].t_s;
  for (const s of ss) {
    const dt = Math.max(0, Math.min(BLOCK_GAP_S, s.t_s - prevT));
    prevT = s.t_s;
    if (s.speed_m_s > 0) distanceM += s.speed_m_s * dt;
  }

  const movingS = moving.length;
  const meanSpeed = mean(moving.map(s => s.speed_m_s));
  const avgPaceSecKm = meanSpeed > 0 ? 1000 / meanSpeed : null;

  let ascentM = 0, descentM = 0;
  for (const s of ss) {
    if (s.grade == null || s.speed_m_s == null) continue;
    const rise = s.grade * s.speed_m_s;
    if (rise > 0) ascentM += rise; else descentM -= rise;
  }

  const out = {
    // --- always available -------------------------------------------------------------------
    durationS: spanS,
    movingS,
    distanceM: Math.round(distanceM),
    distance: distanceM / (unit === 'mi' ? METRES_PER_MILE : 1000),
    avgPaceSecKm,
    splits: splits(ss, unit === 'mi' ? METRES_PER_MILE : 1000),
    longestRunBlockS: longestRunBlock(ss),
    // Walking is not failure in this plan — it is prescribed — so the ratio is reported, not judged.
    runningS: ss.filter(s => s.speed_m_s >= JOG_MS).length,
    ascentM: Math.round(ascentM),
    descentM: Math.round(descentM),
    tones,
    tonesPerMin: spanS > 0 ? tones / (spanS / 60) : 0,
    hrCoveragePct: Math.round(withHr.length / spanS * 100),
    // Pacing evenness. A high spread on a run meant to be steady says the pace was being chased
    // rather than held, which is the habit the tones exist to break.
    paceCv: null,
    // --- heart rate -------------------------------------------------------------------------
    avgHr: withHr.length ? Math.round(mean(withHr.map(s => s.hr_bpm))) : null,
    maxHr: withHr.length ? Math.max(...withHr.map(s => s.hr_bpm)) : null,
    minHr: withHr.length ? Math.min(...withHr.map(s => s.hr_bpm)) : null,
    efficiencyFactor: null,
    beatsPerKm: null,
    beatsPerUnit: null,
    decouplingPct: null,
    zoneSecs: null,
    pctAtOrBelowEasy: null,
    trimp: null,
    hrr60: null,
  };

  if (moving.length > 1 && meanSpeed > 0) {
    const paces = moving.map(s => 1000 / s.speed_m_s);
    const m = mean(paces);
    const sd = Math.sqrt(mean(paces.map(p => (p - m) ** 2)));
    out.paceCv = m > 0 ? sd / m : null;
  }

  if (both.length >= 30) {
    const ms = mean(both.map(s => s.speed_m_s));
    const mh = mean(both.map(s => s.hr_bpm));
    out.efficiencyFactor = efficiencyFactor(ms, mh);
    // Cardiac cost: how many beats it took to cover the distance. Falls as fitness rises, which is
    // the direction people expect a "cost" to move, unlike EF.
    out.beatsPerKm = mh / (ms * 3.6);
    out.beatsPerUnit = unit === 'mi' ? out.beatsPerKm * (METRES_PER_MILE / 1000) : out.beatsPerKm;

    // Decoupling needs a run long enough for drift to mean anything. Under twenty minutes the
    // number is dominated by the warm-up and reports fitness that is not there.
    if (both.length >= 1200) {
      const mid = Math.floor(both.length / 2);
      const pair = s => [s.speed_m_s, s.hr_bpm];
      const d = decoupling(both.slice(0, mid).map(pair), both.slice(mid).map(pair));
      out.decouplingPct = d == null ? null : d * 100;
    }
  }

  if (zones && zones.length) {
    const secs = zones.map(() => 0);
    let below = 0;
    for (const s of withHr) {
      const i = zones.findIndex(z => s.hr_bpm >= z.low && s.hr_bpm < z.high);
      if (i >= 0) secs[i] += 1; else if (s.hr_bpm < zones[0].low) below += 1;
    }
    out.zoneSecs = secs;
    out.belowZ1S = below;
    // The compliance number. Z2's top is the easy ceiling: everything at or under it was aerobic.
    const easyTop = zones[1] ? zones[1].high : zones[0].high;
    const easy = withHr.filter(s => s.hr_bpm <= easyTop).length;
    out.pctAtOrBelowEasy = withHr.length ? easy / withHr.length * 100 : null;
    out.easyCeilingBpm = easyTop;
    out.timeAboveEasyS = withHr.length - easy;
  }

  if (out.avgHr != null && hrRest != null && hrMax != null) {
    out.trimp = trimp(spanS / 60, out.avgHr, hrRest, hrMax, { male });
  }

  // Recovery: how far heart rate fell in the minute after the last moving sample. A classic and
  // very cheap autonomic-fitness marker — it improves early and visibly — but only if the recording
  // kept running after stopping, so its absence is normal rather than a fault.
  if (moving.length) {
    const endT = moving[moving.length - 1].t_s;
    const at = t => {
      const c = withHr.filter(s => Math.abs(s.t_s - t) <= 3);
      return c.length ? mean(c.map(s => s.hr_bpm)) : null;
    };
    const a = at(endT), b = at(endT + 60);
    if (a != null && b != null) out.hrr60 = Math.round(a - b);
  }

  return out;
}

/**
 * How the progress numbers have moved across sessions.
 *
 * Only sessions carrying heart rate are compared, and only against the most recent previous one that
 * does — comparing an easy run to a ramp test produces a number that looks like a result and is an
 * artefact of the two sessions being different.
 */
export function progress(history) {
  const usable = (history || []).filter(h => h && h.efficiencyFactor != null);
  if (usable.length < 2) return null;
  const [now, prev] = usable;
  const delta = (a, b) => (a == null || b == null ? null : a - b);
  return {
    sessions: usable.length,
    efficiencyFactor: { now: now.efficiencyFactor, prev: prev.efficiencyFactor,
                        delta: delta(now.efficiencyFactor, prev.efficiencyFactor) },
    beatsPerUnit: { now: now.beatsPerUnit, prev: prev.beatsPerUnit,
                    delta: delta(now.beatsPerUnit, prev.beatsPerUnit) },
    pctAtOrBelowEasy: { now: now.pctAtOrBelowEasy, prev: prev.pctAtOrBelowEasy,
                        delta: delta(now.pctAtOrBelowEasy, prev.pctAtOrBelowEasy) },
    longestRunBlockS: { now: now.longestRunBlockS, prev: prev.longestRunBlockS,
                        delta: delta(now.longestRunBlockS, prev.longestRunBlockS) },
  };
}
