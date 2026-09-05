// Coaching in words, on a clock, instead of tones on a threshold crossing.
//
// Why this exists
// ---------------
// Two complaints from the same run, and they have the same cause:
//
//   "I feel like the pacing tones never really came."
//   "Even sometimes when they did, I couldn't tell if I was going too fast, too slow, or just right."
//
// The first is measurable rather than a matter of impression. Driving PaceBandMonitor through a
// 7 x (2 min run / 2 min walk) session with every run block taken 20% too fast -- the exact mistake
// this plan exists to coach out -- produces **ten tones in twenty-eight minutes**, six of which are a
// single beep in the opening seconds of a block followed by silence for the rest of it. That is not
// a bug in the monitor. It is a monitor tuned for a continuous hour doing what it was told: smooth
// over 20 s, wait 8 samples, hold 15 s between tones, and back the reminders off geometrically so a
// long run does not nag. Every one of those is right for an hour and wrong for a two-minute block,
// because the block ends before the machinery finishes being careful.
//
// The second is a property of tones as such. A rising or falling pair is unambiguous on a sofa and
// far less so at 160 steps a minute, through wind, under music, having heard it four times in a
// month. Speech does not need to be learned, cannot be confused with the music, and -- this is the
// part that matters most -- can carry the number.
//
//   "I'm having a really hard time pacing. I'm not sure where I am, like, exactly."
//
// Nothing threshold-triggered can fix that, because silence is ambiguous: inside the band and
// "nothing has been computed yet" sound identical. So this speaks on a fixed cadence whether or not
// anything has changed, and always leads with the measured pace. Being told "twelve twenty, ease up"
// every twenty seconds is a different experience from being beeped at twice in a session.
//
// What this is not
// ----------------
// Not a replacement for PaceBandMonitor. That module is checked against the Python original by
// golden vectors and drives the tones, and retuning it for intervals would either break that parity
// or make the tones wrong for the long continuous runs coming in later phases. This is a second,
// independent channel over the same measurement, with its own cadence rules, and the page can run
// either or both.

/**
 * Seconds of pace history the spoken number is averaged over.
 *
 * Small on purpose, because this is the SECOND filter in the chain, not the first: what arrives here
 * is already a trailing mean over GeoDefaults.smoothS (fifteen) seconds of GPS speed. Averaging that
 * again over ten seconds bought very little noise reduction and cost a great deal of lag -- the two
 * windows add, so the spoken number was not purely about the current run block until twenty-five
 * seconds into it, a fifth of a two-minute block. Five keeps the guard against speaking off a single
 * odd fix (MIN_SAMPLES is the real defence there anyway) without paying for smoothing already done.
 */
export const SMOOTHING_S = 5;

/** How often to speak while running. */
export const EVERY_S = 22;

/**
 * How long after a block starts before the first line.
 *
 * GPS speed lags a change of pace, so announcing at the instant a run block opens would report the
 * walk that preceded it -- the most misleading possible moment to be precise.
 *
 * This was nine seconds, chosen as "several", and nine is not enough. Driving a full 5 x (40 s run /
 * 30 s walk) session through the built page with every run block taken 20% too fast, the first line
 * of four blocks out of five was a number from the walk break:
 *
 *     1:11  Run - rep 2/5        1:20  "13:46. Easy."      (he was running 10:05)
 *     3:31  Run - rep 4/5        3:40  "12:40. On pace."   (he was running 10:05)
 *     4:41  Run - rep 5/5        4:50  "13:47. Easy."      (he was running 10:05)
 *
 * Every later line in every block read 10:05 and said "Ease up", correctly. So the channel worked
 * and the opening line of each block was worse than saying nothing: it told an athlete who had just
 * set off too fast -- the single mistake this whole plan exists to coach out -- that he was fine, at
 * the one moment in the block when the correction is cheapest to make.
 *
 * The number is not arbitrary any more. Two windows sit between the legs and the sentence and they
 * add: GeoDefaults.smoothS (fifteen seconds of GPS speed) and this module's own SMOOTHING_S (five).
 * Until both have emptied of the walk break, the number is partly about the walk however it is
 * phrased -- so the settle is their sum, and the first line of a block is the first honest one.
 */
export const SETTLE_S = 20;

/** Minimum samples before any number is spoken. Below this the average is not one. */
export const MIN_SAMPLES = 4;

/// Named for this module, not `mean`: every module here inlines into one scope in the built page,
/// so a bare `mean` collides with run-stats.js and the whole page stops parsing. The build checks
/// for exactly that, which is how this was caught rather than shipped as a blank screen.
const meanPace = xs => xs.reduce((a, b) => a + b, 0) / xs.length;

/**
 * Turns a stream of measured paces into spoken lines.
 *
 * `formatPace` is injected because the athlete's unit lives in the page and this module must not
 * know about it; it is handed seconds per kilometre and returns whatever the athlete thinks in.
 */
export class PaceVoice {
  constructor({ targetSecKm, tolerance = 0.06, ceilingOnly = false,
                everyS = EVERY_S, settleS = SETTLE_S, formatPace = String } = {}) {
    this.targetSecKm = targetSecKm;
    this.tolerance = tolerance;
    this.ceilingOnly = ceilingOnly;
    this.everyS = everyS;
    this.settleS = settleS;
    this.formatPace = formatPace;

    this.window = [];
    this.nextAt = null;         // when the next line is due; null while stood down
    // When the window started accumulating toward MIN_SAMPLES, independent of the window's own
    // contents -- see the gate in `update` for why sample COUNT and elapsed TIME are different
    // questions once real GPS delivery is sparser than the window's own filtering assumes.
    this.windowStartT = null;
    this.spoken = 0;
    this.lostSignal = false;
  }

  /**
   * Begin a block of running at `tS`.
   *
   * Called at the start of every run interval, and once at the start of a continuous run. Resets the
   * cadence so each block gets its own settle period rather than inheriting the previous one's
   * clock, which would otherwise put the first line of a block anywhere from immediately to twenty
   * seconds in depending on where the walk break happened to fall.
   */
  begin(tS) {
    this.window = [];
    this.windowStartT = null;
    this.nextAt = tS + this.settleS;
    this.lostSignal = false;
  }

  /** Stop speaking. The next `begin` starts a fresh cadence. */
  standDown() { this.nextAt = null; this.window = []; this.windowStartT = null; }

  /** The band, as [fast, slow] in seconds per km. */
  band() {
    const t = this.targetSecKm;
    return [t * (1 - this.tolerance), t * (1 + this.tolerance)];
  }

  /**
   * Feed one second. Returns `{text, kind, paceSecKm}` when something should be said, else null.
   *
   * `kind` is for the page's own log colouring and for tests: `fast`, `slow`, `in`, or `lost`.
   */
  update(tS, paceSecKm, { running = true, trusted = true } = {}) {
    if (!running || this.targetSecKm == null) { this.standDown(); return null; }
    if (this.nextAt == null) this.begin(tS);

    if (!trusted || !(paceSecKm > 0)) {
      this.window = [];
      this.windowStartT = null;
      // Said once per outage, not every second. The number cannot be reported, and saying so is the
      // only honest thing -- but a phone repeating "no signal" under trees is its own problem.
      if (!this.lostSignal && tS >= this.nextAt) {
        this.lostSignal = true;
        this.nextAt = tS + this.everyS;
        return { text: 'No GPS signal.', kind: 'lost', paceSecKm: null };
      }
      return null;
    }
    this.lostSignal = false;

    if (this.windowStartT == null) this.windowStartT = tS;
    this.window.push([tS, paceSecKm]);
    this.window = this.window.filter(([t]) => t >= tS - SMOOTHING_S);
    // Four fixes inside ten seconds assumes GPS delivers roughly one a second, which is a property
    // of the radio, not a guarantee of it. iOS commonly delivers watchPosition fixes every two to
    // five seconds depending on signal and power state -- at which rate four-in-ten never arrives,
    // and this channel would never speak again for the rest of the run. This was found by driving a
    // 30%-too-fast session through it at one fix every four seconds: zero lines in five minutes,
    // silently, with no error and nothing on screen to say why. MIN_SAMPLES still guards against
    // speaking off one noisy fix; SMOOTHING_S of elapsed real time, with whatever showed up, guards
    // against that turning into the channel going dark for a run whose GPS was merely being normal.
    if (tS < this.nextAt
        || (this.window.length < MIN_SAMPLES && tS - this.windowStartT < SMOOTHING_S)) return null;

    this.nextAt = tS + this.everyS;
    this.spoken += 1;

    const avg = meanPace(this.window.map(([, p]) => p));
    const [fast, slow] = this.band();
    // Smaller seconds-per-km is faster. The direction words are the athlete's, not the instrument's:
    // "ease up" and "pick it up" say what to do with the legs, where "fast" and "slow" only name a
    // state and leave the correction to be worked out while running.
    const kind = avg < fast ? 'fast' : avg > slow ? 'slow' : 'in';
    return { text: `${this.formatPace(avg)}. ${this._direction(kind)}`, kind, paceSecKm: avg };
  }

  _direction(kind) {
    if (kind === 'fast') return 'Ease up.';
    // On a ceiling-only session the slow edge is not enforced -- an easy run taken easier is not a
    // fault -- so being under it must not be reported as one. Saying "on pace" instead would be a
    // lie about a number just spoken aloud; "easy" is true and is also the point of the session.
    if (kind === 'slow') return this.ceilingOnly ? 'Easy.' : 'Pick it up.';
    return 'On pace.';
  }
}
