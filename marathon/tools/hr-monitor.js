// Coaching on heart rate rather than on pace.
//
// Why this exists
// ---------------
// GPS is a good instrument for distance and for a smoothed pace, and a poor one for effort. Its
// error is a few percent on a good fix and much worse under trees, it says nothing about how hard
// the work actually is, and on a short interval it has not settled before the interval is over.
// Heart rate is the signal the whole engine is built around — the zones, the HR/speed slope, the
// in-run controller — and it is the one the athlete is now wearing.
//
// So: when the armband is connected, heart rate governs and pace is information. When it is not,
// pace governs. Never both at once — two channels talking about the same run is how you end up
// being told to ease off and lift within ten seconds of each other.
//
// The lag problem, and why a raw threshold is wrong
// ------------------------------------------------
// Heart rate responds to a change of effort as a first-order system with a time constant near 45
// seconds. The heart rate you can see belongs to the pace you were running half a minute ago, so
// controlling directly on it oscillates: ease off, heart rate keeps rising, ease off again, end up
// walking, heart rate falls, speed up, repeat.
//
// This controls on where heart rate is *heading* — `HR_ss ≈ HR + τ·dHR/dt` — which is the same lead
// compensation `marathon_engine.realtime` uses, with the same τ, deadband and confirmation window.
// It is deliberately a faithful subset rather than a fresh design: the constants were argued out
// once, against the literature, and re-deriving them here would only produce a second set to keep
// in step.
//
// What is deliberately NOT ported: interval rep management, the abort ladder, decoupling. Those
// belong to the full controller in the app. This is the ceiling, which is what an easy run needs.

export const HrTuning = {
  /// Heart rate's first-order time constant. Same value as the engine.
  tauS: 45,
  /// Ignore an excursion smaller than this. Beat-to-beat noise alone is worth a couple of bpm.
  deadbandBpm: 4,
  /// The error must persist this long before anything is said. Heart rate wanders; a threshold
  /// crossed for three seconds is not information.
  confirmS: 20,
  /// Window the slope is fitted over. Long enough to be a trend, short enough to be current.
  slopeWindowS: 30,
  /// Anti-nag floor between reminders.
  ///
  /// Longer than the pace channel's, and deliberately longer than `tauS`. Heart rate takes about
  /// forty-five seconds to reflect a change of effort, so a reminder any sooner arrives before your
  /// correction could possibly have shown up — telling you again about something you have already
  /// fixed and cannot yet prove you fixed. Twenty seconds was the first guess and produced ten tones
  /// across twenty minutes of a sustained excursion; sixty produces four, none of them premature.
  minGapS: 60,
  backoffMax: 8,
  /// A reading older than this is a memory. Same rule as the sensor driver.
  staleS: 5,
};

/**
 * Watches heart rate against a zone band and emits the same earcons as the pace channel.
 *
 * `ceilingOnly` is the normal case: an easy run has an upper bound and no lower one, and being
 * below it is the session working rather than a fault.
 */
export class HrCeilingMonitor {
  constructor({ lowBpm, highBpm, ceilingOnly = true }) {
    this.low = lowBpm;
    this.high = highBpm;
    this.ceilingOnly = ceilingOnly;

    this.history = [];            // [t, hr]
    this.state = 'unknown';       // unknown | in | fast | slow
    this.errorSince = null;
    this.errorSign = 0;
    this.lastToneT = null;
    this.pendingAck = false;
    this.consecutive = 0;
    this.lastSS = null;
  }

  /** Slope of heart rate in bpm per second, by least squares over the window. */
  slope() {
    const w = this.history;
    if (w.length < 5) return 0;
    const n = w.length;
    const mt = w.reduce((a, [t]) => a + t, 0) / n;
    const mh = w.reduce((a, [, h]) => a + h, 0) / n;
    let num = 0, den = 0;
    for (const [t, h] of w) { num += (t - mt) * (h - mh); den += (t - mt) ** 2; }
    return den > 0 ? num / den : 0;
  }

  /**
   * Feed one second.
   *
   * `hr` is null whenever the reading is absent or stale — the caller decides that, using the same
   * freshness rule the sensor driver applies, because a heart rate that stopped arriving must never
   * be coached from.
   */
  update(tS, hr) {
    if (hr == null) {
      this.history = [];
      if (this.state !== 'unknown') {
        this.state = 'unknown';
        this.errorSince = null;
        return this._emit('degraded', tS, 'heart rate lost');
      }
      return null;
    }

    this.history.push([tS, hr]);
    this.history = this.history.filter(([t]) => t >= tS - HrTuning.slopeWindowS);
    if (this.history.length < 5) return null;

    // Where heart rate is heading, not where it is.
    const ss = hr + HrTuning.tauS * this.slope();
    this.lastSS = ss;

    const tooHigh = ss > this.high + HrTuning.deadbandBpm;
    const tooLow = !this.ceilingOnly && ss < this.low - HrTuning.deadbandBpm;
    const sign = tooHigh ? 1 : (tooLow ? -1 : 0);

    if (sign === 0) {
      const wasOut = this.state === 'fast' || this.state === 'slow';
      this.state = 'in';
      this.errorSince = null;
      this.errorSign = 0;
      this.consecutive = 0;
      if (wasOut && this.pendingAck) {
        this.pendingAck = false;
        return this._emit('in_band', tS, 'back inside the zone');
      }
      this.pendingAck = false;
      return null;
    }

    if (this.errorSign !== sign) { this.errorSince = tS; this.errorSign = sign; this.consecutive = 0; }
    // Nothing is said until the excursion has persisted. Heart rate wanders.
    if (tS - this.errorSince < HrTuning.confirmS) return null;

    this.state = sign > 0 ? 'fast' : 'slow';
    const gap = HrTuning.minGapS * Math.min(HrTuning.backoffMax, 2 ** Math.max(0, this.consecutive - 1));
    if (this.lastToneT != null && tS - this.lastToneT < gap) return null;
    return this._emit(sign > 0 ? 'ease' : 'lift', tS,
                      `heading for ${Math.round(ss)}, ceiling ${Math.round(this.high)}`);
  }

  _emit(earcon, tS, reason) {
    const floor = (earcon === 'in_band' || earcon === 'degraded') ? 2 : HrTuning.minGapS;
    if (this.lastToneT != null && tS - this.lastToneT < floor) return null;
    this.lastToneT = tS;
    if (earcon === 'ease' || earcon === 'lift') { this.pendingAck = true; this.consecutive += 1; }
    return { earcon, tS, reason, hrSteadyState: this.lastSS };
  }
}
