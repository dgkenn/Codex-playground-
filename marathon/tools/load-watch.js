// Load and pain: the two things that decide whether a plan survives contact with a body.
//
// Both of these already exist in the engine -- `load.acwr` and `progress.pain_trend`, written,
// tested, and with zero production callers between them. They are ported rather than called because
// the engine is Python on a laptop and the athlete is on a phone in a park: the decision has to be
// available at the moment the session ends, not the next time someone runs a CLI. The Python stays
// the reference implementation and this is checked against its constants and its rule order.
//
// Why these two and not the rest of the engine's decision surface: they are the only unwired parts
// whose inputs this athlete can actually produce. `readiness.py` needs fourteen nights of overnight
// HRV and sleep data he has no way to collect, and returns "unknown" forever without it. These need
// a heart rate he already records and a form he can fill in.

// =================================================================================================
// Load
// =================================================================================================

export const ACUTE_DAYS = 7;
export const CHRONIC_DAYS = 28;
export const ACWR_SWEET_LOW = 0.80;
export const ACWR_SWEET_HIGH = 1.30;
export const ACWR_HARD_CAP = 1.50;

/**
 * Exponentially weighted moving average, lambda = 2/(n+1).
 *
 * `loads` must be one entry per CALENDAR day including zeros for rest days. Omitting rest days is
 * the single most common way to make this number lie, and it lies optimistically: drop the zeros
 * and a three-run week looks like a seven-run week's worth of chronic load.
 */
export function ewmaLoad(loads, nDays) {
  if (!(nDays > 0)) throw new Error('nDays must be positive');
  if (!loads || !loads.length) return 0;
  const lam = 2 / (nDays + 1);
  let e = loads[0];
  for (let i = 1; i < loads.length; i++) e = loads[i] * lam + e * (1 - lam);
  return e;
}

/**
 * Acute:chronic workload ratio over a gap-filled daily series.
 *
 * Reported as a ramp-rate governor, not a risk score -- the evidence for ACWR as a predictor of
 * individual injury is contested, and it is used here for the thing it is good at: noticing that
 * this week is a long way out of line with the last month.
 *
 * Below CHRONIC_DAYS of history it refuses to answer. For a brand-new runner chronic load starts at
 * literally zero, which makes the ratio explode on the first easy jog -- a real and well-known
 * defect of applying this to beginners, and exactly the situation this athlete is in.
 */
export function acwr(dailyLoads) {
  const n = (dailyLoads || []).length;
  const acute = ewmaLoad(n >= ACUTE_DAYS ? dailyLoads.slice(-ACUTE_DAYS) : dailyLoads, ACUTE_DAYS);
  const chronic = ewmaLoad(dailyLoads || [], CHRONIC_DAYS);
  if (n < CHRONIC_DAYS) {
    return { acute, chronic, ratio: chronic > 0 ? acute / chronic : 0, band: 'insufficient_history',
             days: n,
             note: `${n} of ${CHRONIC_DAYS} days recorded — the ratio is not meaningful yet, and `
                 + 'for a new runner it reads high for weeks purely because there is no history '
                 + 'to compare against.' };
  }
  if (chronic <= 0) {
    return { acute, chronic, ratio: 0, band: 'insufficient_history', days: n,
             note: 'no chronic load to compare against' };
  }
  const ratio = acute / chronic;
  const band = ratio < ACWR_SWEET_LOW ? 'detraining'
             : ratio <= ACWR_SWEET_HIGH ? 'optimal'
             : ratio <= ACWR_HARD_CAP ? 'caution' : 'danger';
  return { acute, chronic, ratio, band, days: n,
           note: band === 'danger'
             ? 'This week is a long way above the last month. Hold or cut rather than adding.'
             : band === 'caution' ? 'Rising faster than the last month. Worth holding here.'
             : band === 'detraining' ? 'Well below the last month — fine after a cutback, a '
                                     + 'problem if it keeps going.'
             : 'In line with the last month.' };
}

/**
 * Turn a session history into the gap-filled daily series `acwr` needs.
 *
 * `sessions` are `{at, trimp}`; `at` is anything Date can parse. Days with no session get a zero,
 * which is the whole point -- see ewmaLoad.
 */
export function dailyLoadSeries(sessions, { asOf = new Date(), days = CHRONIC_DAYS * 2 } = {}) {
  const byDay = new Map();
  for (const s of sessions || []) {
    if (!s || s.trimp == null) continue;
    const d = new Date(s.at);
    if (isNaN(d)) continue;
    const key = d.toISOString().slice(0, 10);
    byDay.set(key, (byDay.get(key) || 0) + s.trimp);
  }
  const out = [];
  const end = new Date(asOf);
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(end);
    d.setDate(d.getDate() - i);
    out.push(byDay.get(d.toISOString().slice(0, 10)) || 0);
  }
  return out;
}

// =================================================================================================
// Pain
// =================================================================================================

/** Times the same site can come up in the window before it stops being a niggle. */
export const PAIN_ESCALATION_DAYS = 3;

export const PAIN_WINDOW_DAYS = 14;

/// Named for this module: everything inlines into one scope in the built page, so a bare `mean` --
/// or, as this file first tried, a `meanOf` already taken by threshold.js -- stops the whole page
/// parsing. The build checks for exactly that, which is how this was caught rather than shipped.
const meanLevel = xs => xs.reduce((a, b) => a + b, 0) / xs.length;

/**
 * Group pain reports by site and classify each one's trajectory.
 *
 * The two fields carrying the most weight are deliberately not the pain score:
 *
 *   * `focal` -- a specific point of bone tenderness is a different problem from a diffuse ache and
 *     escalates straight to stopping however mild it feels. This matters more than usual here: the
 *     athlete is 180 lb, inside the first twenty weeks of running, and bone appears in none of the
 *     heart-rate measures that govern everything else.
 *   * `timing === 'next_morning'` -- next-day pain is the most informative signal in overuse injury
 *     and the one most often dismissed, because by the time you run again it has eased off.
 *
 * `entries` are `{day, site, level, timing, focal, worsensDuringRun}` with `day` an ISO date.
 */
export function painTrend(entries, { asOf = null, windowDays = PAIN_WINDOW_DAYS } = {}) {
  const es = (entries || []).filter(e => e && e.site && e.day);
  if (!es.length) return [];
  const day = e => e.day.slice(0, 10);
  const end = asOf ? asOf.slice(0, 10) : es.map(day).sort().slice(-1)[0];
  const startD = new Date(end);
  startD.setDate(startD.getDate() - (windowDays - 1));
  const start = startD.toISOString().slice(0, 10);
  const recent = es.filter(e => day(e) >= start && day(e) <= end);

  const bySite = new Map();
  for (const e of recent) {
    if (!bySite.has(e.site)) bySite.set(e.site, []);
    bySite.get(e.site).push(e);
  }

  const out = [];
  for (const [site, list] of [...bySite.entries()].sort()) {
    list.sort((a, b) => day(a).localeCompare(day(b)));
    const levels = list.map(e => Number(e.level) || 0);
    const spanDays = Math.round(
      (new Date(day(list[list.length - 1])) - new Date(day(list[0]))) / 86400000) + 1;
    let escalating = false;
    if (levels.length >= 3) {
      const mid = Math.floor(levels.length / 2);
      escalating = meanLevel(levels.slice(mid)) > meanLevel(levels.slice(0, mid)) + 0.5;
    }
    const focal = list.some(e => e.focal);
    const nextMorning = list.some(e => e.timing === 'next_morning');
    const worsening = list.some(e => e.worsensDuringRun);
    const name = site.replace(/_/g, ' ');

    let verdict = 'watch', message = '', actions = [];
    if (focal) {
      verdict = 'urgent';
      message = `Pain at a single point on the ${name}. Focal bone tenderness that worsens with `
              + 'loading is how a stress injury presents, and it does not need to be severe to be '
              + 'serious. Stop running and get it assessed before the next run.';
      actions = ['Stop running now — do not test it with an easy run.',
                 'Get it assessed. Caught early it is a few weeks; run through it is a few months.',
                 'Cross-train without impact meanwhile if that is pain-free.'];
    } else if (Math.max(...levels) > 5) {
      verdict = 'stop_and_assess';
      message = `Pain reached ${Math.max(...levels)}/10 at the ${name}. Above 5/10 the rule is `
              + 'stop, every time.';
      actions = ['No running until it is below 3/10 at rest and while walking.',
                 'Then restart from the run-walk ladder, not from your previous volume.'];
    } else if (escalating || list.length >= PAIN_ESCALATION_DAYS || nextMorning || worsening) {
      verdict = 'hold_volume';
      const why = [];
      if (escalating) why.push('it is getting worse across the fortnight');
      if (list.length >= PAIN_ESCALATION_DAYS) {
        why.push(`it has come up ${list.length} times in ${spanDays} days`);
      }
      if (nextMorning) why.push('it is there the morning after, which is the signal that matters most');
      if (worsening) why.push('it worsens as the run goes on rather than warming up');
      message = `The ${name} is a pattern rather than a niggle: ${why.join(', and ')}.`;
      actions = ['Volume holds where it is — no increases until two clean weeks.',
                 'Easy running only, and only if it is pain-free during AND the next morning.',
                 'If it has not settled in ten days, get it looked at.'];
    } else {
      message = `Occasional mild discomfort at the ${name} (max ${Math.max(...levels)}/10). Within `
              + 'the acceptable band — keep logging it.';
      actions = ['Keep logging. The log is what turns this into a pattern you can see.'];
    }
    out.push({ site, entries: list.length, maxLevel: Math.max(...levels),
               meanLevel: meanLevel(levels), spanDays, escalating, verdict, message, actions });
  }
  const order = { urgent: 0, stop_and_assess: 1, hold_volume: 2, watch: 3 };
  return out.sort((a, b) => order[a.verdict] - order[b.verdict]);
}

/**
 * Does anything in the pain log say the plan should not go up this week?
 *
 * The one line the progression loop needs. Deliberately conservative: a `hold_volume` verdict stops
 * the ladder advancing but does not step it back, because pain that is a pattern is a reason to
 * stop adding rather than a reason to detrain.
 */
export function painHolds(trends) {
  const worst = (trends || [])[0];
  if (!worst) return null;
  if (worst.verdict === 'urgent' || worst.verdict === 'stop_and_assess') {
    return { stop: true, hold: true, site: worst.site, message: worst.message };
  }
  if (worst.verdict === 'hold_volume') {
    return { stop: false, hold: true, site: worst.site, message: worst.message };
  }
  return null;
}
