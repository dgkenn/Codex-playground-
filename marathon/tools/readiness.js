// Morning readiness: the engine's HRV-guided-training rule, on the phone.
//
// A port of marathon_engine/readiness.py (authoritative; its docstring carries the evidence) and
// of the beat cleaning in signal_quality.py. tests/readiness-parity.mjs holds this file to vectors
// exported from the Python, so the two cannot drift apart unnoticed.
//
// In one paragraph: lnRMSSD, averaged over the last 7 days (at least 3 measurements), is compared
// with the athlete's own 60-day baseline (at least 14 measurements). The band is +/-0.5 of the
// within-person between-day SD around that baseline. Above or inside it, run the plan as written;
// below it, today becomes easy; well below it for two days running, rest. Short sleep, illness, an
// elevated resting heart rate or a bad morning self-report can each override a good HRV. That is
// the rule the HRV-guided running trials used (Vesterinen et al. 2016: fewer hard sessions and a
// larger 3000 m improvement than a fixed plan).
//
// What is different on the phone is the measurement, not the rule. The engine was written for
// overnight data; here it is a five-minute check lying down on waking, with the armband's own
// beat-to-beat intervals. The Verity Sense's resting heart rate is accurate, but its RMSSD reads
// high against a chest strap and agrees poorly in absolute terms, worse when upright (a Georgia
// Southern University thesis against the Polar H10). So: the same posture every morning, never compared with anyone else's
// numbers, and a check with more than 5% of its beats rejected is not counted at all.

export const PPI_MIN_MS = 250;
export const PPI_MAX_MS = 2500;
export const MALIK_FRACTION = 0.20;
export const MAX_ARTIFACT_FRACTION = 0.05;

export const SWC_MULTIPLIER = 0.5;
export const ROLLING_DAYS = 7;
export const BASELINE_DAYS = 60;
export const MIN_BASELINE_NIGHTS = 14;
export const SLEEP_FLOOR_MIN = 6 * 60;
export const SLEEP_TARGET_MIN = 7.5 * 60;
/// About four minutes of clean beats: the floor that tells a sensor failure from a usable check.
export const MIN_CLEAN_BEATS = 240;

export const BAND_ACTIONS = {
  primed: 'proceed', normal: 'proceed', suppressed: 'downgrade_to_easy',
  strained: 'rest_or_walk', unknown: 'proceed_conservatively',
};

/**
 * Drop beats the band flagged as moved, beats outside 250-2500 ms, and beats more than 20% off the
 * previous ACCEPTED beat (Malik). Returns {clean, counts}. Same order and rules as the engine.
 */
export function cleanIntervals(intervals, { blockers = null, errorMs = null, maxErrorMs = 30 } = {}) {
  const counts = { total: intervals.length, blocker: 0, error: 0, implausible: 0, malik: 0, kept: 0 };
  const clean = [];
  let prev = null;
  intervals.forEach((v, i) => {
    if (blockers && i < blockers.length && blockers[i]) { counts.blocker += 1; return; }
    if (errorMs && i < errorMs.length && errorMs[i] > maxErrorMs) { counts.error += 1; return; }
    if (!(v >= PPI_MIN_MS && v <= PPI_MAX_MS)) { counts.implausible += 1; return; }
    if (prev != null && Math.abs(v - prev) > MALIK_FRACTION * prev) { counts.malik += 1; return; }
    clean.push(v);
    prev = v;
  });
  counts.kept = clean.length;
  return { clean, counts };
}

export function rmssd(intervals) {
  if (intervals.length < 2) return null;
  let s = 0;
  for (let i = 0; i + 1 < intervals.length; i++) s += (intervals[i + 1] - intervals[i]) ** 2;
  return Math.sqrt(s / (intervals.length - 1));
}

/**
 * One morning check from the band's raw beats: what goes into the history. Resting heart rate is
 * from the clean intervals (60000 / mean), which is what "resting heart rate" means in the zone
 * model: lying down, on waking, before standing up.
 */
export function summariseCheck(beats, { settleS = 60 } = {}) {
  // The first minute is settling: heart rate is still coming down from rolling over to reach the phone.
  let t = 0;
  const kept = [];
  for (const b of beats) { t += b.ppiMs / 1000; if (t > settleS) kept.push(b); }
  const { clean, counts } = cleanIntervals(kept.map(b => b.ppiMs),
    { blockers: kept.map(b => b.blocker), errorMs: kept.map(b => b.errMs) });
  const artifact = counts.total ? 1 - counts.kept / counts.total : null;
  const r = rmssd(clean);
  const mean = clean.length ? clean.reduce((a, b) => a + b, 0) / clean.length : null;
  return {
    hrvMs: r == null ? null : Math.round(r * 10) / 10,
    restingHr: mean ? Math.round(60000 / mean * 10) / 10 : null,
    cleanCount: counts.kept, artifactFraction: artifact == null ? null : Math.round(artifact * 1000) / 1000,
    counts,
  };
}

const lnHrv = n => (n.hrvMs != null && n.hrvMs > 0 ? Math.log(n.hrvMs) : null);

export function usableHrv(n) {
  if (lnHrv(n) == null) return false;
  if (n.cleanCount != null && n.cleanCount < MIN_CLEAN_BEATS) return false;
  if (n.artifactFraction != null && n.artifactFraction > MAX_ARTIFACT_FRACTION) return false;
  return true;
}

// Days as 'YYYY-MM-DD', arithmetic in UTC so a daylight-saving change cannot move a day.
const dayNum = d => Math.round(Date.parse(`${d}T00:00:00Z`) / 86400000);
const fmean = xs => xs.reduce((a, b) => a + b, 0) / xs.length;
const stdev = xs => {
  const m = fmean(xs);
  return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1));
};
/// Python's round(): halves go to the even neighbour. Only the display score uses it, but parity is parity.
const pyRound = x => {
  const f = Math.floor(x), d = x - f;
  if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1;
  return Math.round(x);
};

export function hrvBaseline(nights, { asOf = null, windowDays = BASELINE_DAYS } = {}) {
  if (!nights.length) return null;
  const end = asOf ? dayNum(asOf) : Math.max(...nights.map(n => dayNum(n.day)));
  const start = end - windowDays;
  let usable = nights.filter(n => dayNum(n.day) >= start && dayNum(n.day) <= end && usableHrv(n));
  // One baseline per source and posture: a change of either shifts lnRMSSD by more than the band.
  if (usable.length) {
    const key = n => `${n.source || 'polar_ppi_rmssd'}|${n.posture || 'sleep'}`;
    const tally = new Map();
    for (const n of usable) tally.set(key(n), (tally.get(key(n)) || 0) + 1);
    const dominant = [...tally.entries()].sort((a, b) => b[1] - a[1])[0][0];
    usable = usable.filter(n => key(n) === dominant);
  }
  if (usable.length < MIN_BASELINE_NIGHTS) return null;
  const lns = usable.map(lnHrv);
  const meanLn = fmean(lns);
  const sdLn = lns.length > 1 ? stdev(lns) : 0;
  const rhrs = usable.map(n => n.restingHr).filter(Boolean);
  return {
    meanLn, sdLn, n: usable.length, swc: SWC_MULTIPLIER * sdLn,
    low: meanLn - SWC_MULTIPLIER * sdLn, high: meanLn + SWC_MULTIPLIER * sdLn,
    rhrMean: rhrs.length ? fmean(rhrs) : null,
    rhrSd: rhrs.length > 1 ? stdev(rhrs) : null,
  };
}

function rollingMeanLn(nights, asOf, days = ROLLING_DAYS) {
  const end = dayNum(asOf), start = end - (days - 1);
  const lns = nights.filter(n => dayNum(n.day) >= start && dayNum(n.day) <= end && usableHrv(n)).map(lnHrv);
  return lns.length >= 3 ? fmean(lns) : null;
}

function consecutiveWellBelow(nights, today, base) {
  if (!base) return 0;
  const threshold = base.meanLn - 2 * base.swc;
  let count = 0, d = dayNum(today);
  for (;;) {
    const m = rollingMeanLn(nights, new Date(d * 86400000).toISOString().slice(0, 10));
    if (m == null || m >= threshold) return count;
    count += 1; d -= 1;
    if (count > 30) return count;
  }
}

function hooperPenalty(n) {
  let penalty = 0;
  const flags = [];
  for (const [label, val, w] of [['soreness', n.soreness, 3], ['fatigue', n.fatigue, 3], ['stress', n.stress, 2]]) {
    if (val != null && val > 3) {
      penalty += (val - 3) * w;
      if (val >= 6) flags.push({ flag: `high_${label}`, severity: 'medium', message: `Self-reported ${label} ${val}/7.` });
    }
  }
  if (n.motivation != null && n.motivation <= 2) {
    penalty += 4;
    flags.push({ flag: 'low_motivation', severity: 'low',
                 message: 'Low motivation -- often the first sign of accumulated fatigue.' });
  }
  return [Math.min(30, penalty), flags];
}

/**
 * Today's band from the history of checks. Each check: {day, hrvMs, restingHr, sleepMin,
 * cleanCount, artifactFraction, soreness, fatigue, stress, motivation (1-7), illness, source,
 * posture}. Precedence as in the engine: illness, then short sleep, then HRV well below for two
 * days, then the HRV band; no baseline yet is "unknown".
 */
export function dailyReadiness(nights, { asOf = null, baseline = null } = {}) {
  if (!nights.length) {
    return { day: asOf, band: 'unknown', action: BAND_ACTIONS.unknown, score: 50, hrvStatus: 'no_baseline',
             rollingLn: null, baseline: null, components: {}, flags: [], override: null };
  }
  const today = asOf || nights.map(n => n.day).sort().at(-1);
  const tonight = nights.find(n => n.day === today) || null;
  const base = baseline || hrvBaseline(nights, { asOf: today });
  const m7 = rollingMeanLn(nights, today);
  const flags = [], components = {};

  let hrvStatus = 'no_baseline', hrvC = 50;
  if (base && m7 != null) {
    if (m7 > base.high) { hrvStatus = 'above'; hrvC = 85; }
    else if (m7 >= base.low) {
      const span = Math.max(1e-9, base.high - base.low);
      hrvC = 50 + 25 * ((m7 - base.meanLn) / (span / 2));
      hrvStatus = 'within';
    } else if (m7 >= base.meanLn - 2 * base.swc) { hrvStatus = 'below'; hrvC = 30; }
    else { hrvStatus = 'well_below'; hrvC = 12; }
    components.hrv = hrvC;
    if (hrvStatus === 'below' || hrvStatus === 'well_below') {
      flags.push({ flag: 'hrv_suppressed', severity: hrvStatus === 'well_below' ? 'high' : 'medium',
                   message: `7-day HRV ${Math.exp(m7).toFixed(0)} ms is below your ${Math.exp(base.meanLn).toFixed(0)} ms baseline band.` });
    }
  }

  let sleepC = 50;
  const tst = tonight ? tonight.sleepMin ?? null : null;
  if (tst != null) {
    sleepC = Math.max(0, Math.min(100, 100 * tst / SLEEP_TARGET_MIN));
    components.sleep = sleepC;
    if (tst < SLEEP_FLOOR_MIN) {
      flags.push({ flag: 'short_sleep', severity: 'high',
                   message: `${(tst / 60).toFixed(1)} h of sleep -- below the ${SLEEP_FLOOR_MIN / 60} h floor for quality work.` });
    }
  }

  let rhrC = 50;
  if (tonight && tonight.restingHr && base && base.rhrMean && base.rhrSd) {
    const z = (tonight.restingHr - base.rhrMean) / Math.max(1, base.rhrSd);
    rhrC = Math.max(0, Math.min(100, 50 - z * 20));
    components.rhr = rhrC;
    if (z >= 1.5) {
      flags.push({ flag: 'elevated_rhr', severity: 'medium',
                   message: `Resting HR ${tonight.restingHr.toFixed(0)} bpm is ${z.toFixed(1)} SD above baseline -- a classic early illness or overreaching signal.` });
    }
  }

  // Sleep continuity is an overnight measure; a morning check has none, so it sits at its neutral 100.
  const continuity = 100;
  components.continuity = continuity;

  const [subj, subjFlags] = tonight ? hooperPenalty(tonight) : [0, []];
  flags.push(...subjFlags);
  if (subj) components.subjective_penalty = -subj;

  let score = 'hrv' in components
    ? 0.40 * hrvC + 0.28 * sleepC + 0.14 * rhrC + 0.18 * continuity
    : 0.55 * sleepC + 0.45 * continuity;
  score = Math.max(0, Math.min(100, score - subj));

  let band, override = null;
  if (tonight && tonight.illness) { band = 'strained'; override = 'illness reported'; }
  else if (tst != null && tst < SLEEP_FLOOR_MIN && (hrvStatus === 'below' || hrvStatus === 'well_below')) {
    band = 'strained'; override = 'short sleep plus suppressed HRV';
  } else if (tst != null && tst < SLEEP_FLOOR_MIN) {
    band = 'suppressed'; override = `sleep below the ${SLEEP_FLOOR_MIN / 60} h floor`;
  } else if (hrvStatus === 'no_baseline') band = 'unknown';
  else if (hrvStatus === 'well_below' && consecutiveWellBelow(nights, today, base) >= 2) {
    band = 'strained'; override = 'HRV more than 2xSWC below baseline for 2+ days';
  } else if (hrvStatus === 'well_below' || hrvStatus === 'below') band = 'suppressed';
  else if (hrvStatus === 'above') band = 'primed';
  else band = 'normal';

  if ((band === 'primed' || band === 'normal') && flags.some(f => f.severity === 'high')) {
    band = 'suppressed'; override = 'a high-severity flag is present';
  }
  return { day: today, band, action: BAND_ACTIONS[band], score: pyRound(score), hrvStatus,
           rollingLn: m7, baseline: base, components, flags, override };
}

/** What the run screen says about it, in the athlete's terms. */
export function readinessText(r) {
  const why = r.override ? r.override.charAt(0).toUpperCase() + r.override.slice(1) + '. ' : '';
  switch (r.band) {
    case 'primed': return { headline: 'Primed', detail: 'HRV above your usual band. Run the plan as written -- this is not a licence to add more.' };
    case 'normal': return { headline: 'Run the plan', detail: 'HRV inside your usual band. Nothing to change.' };
    case 'suppressed': return { headline: 'Back off today',
      detail: `${why || 'HRV below your usual band. '}Today runs the rung's blocks only, no extra blocks -- the work will still be there when you have recovered.` };
    case 'strained': return { headline: 'Rest',
      detail: `${why || 'HRV well below your usual band for days. '}A rest day or a 20-minute walk. If this lasts more than four days, look for a cause rather than training through it.` };
    default: return { headline: 'Building your baseline',
      detail: 'Fourteen morning checks before HRV can say anything about you. Run the plan as written meanwhile.' };
  }
}
