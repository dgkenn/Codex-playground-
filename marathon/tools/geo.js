// Turning a stream of GPS fixes into pace, distance, grade and a route.
//
// Split out of the coach page and kept DOM-free so it can be tested, because every defect this
// replaces was invisible in the app and obvious in a test:
//
//   1. **Distance came from speed x time.** Integrating a noisy speed drifts, and a Doppler reading
//      that sits a little above zero while you stand at a crossing accumulates distance you did not
//      run. Distance now comes from the positions themselves, with a stationary threshold.
//   2. **Grade was never computed at all.** The pace band is supposed to move with the hill — the
//      engine has done that since the beginning — but the web coach passed grade: 0 forever, so a
//      6% climb earned "ease off" for running the pace the hill costs.
//   3. **A rejected fix still became the baseline** for the next distance calculation, so one loose
//      fix poisoned the following segment as well as its own.
//   4. **No teleport rejection on position.** A fix can pass the accuracy check and still jump.
//   5. **Displayed pace was raw**, so it flickered between numbers a runner cannot act on.
//
// The design rule throughout: prefer measurement over inference, and prefer a gap over a guess. A
// second with no trustworthy fix contributes nothing rather than an estimate.

const R_EARTH = 6371008.8;

export function haversine(a, b) {
  const rad = d => d * Math.PI / 180;
  const dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const s = Math.sin(dLat / 2) ** 2
          + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.min(1, Math.sqrt(s)));
}

export const GeoDefaults = {
  /// A fix looser than this is not a position, it is a rumour. 25 m keeps working under trees while
  /// still refusing a fix that could invent a sprint.
  maxAccuracyM: 25,
  /// Nobody runs faster than this. Anything above it is a bad fix, not an athlete.
  maxSpeedMS: 8.0,
  /// Below this, treat movement as GPS wander rather than travel. A stationary phone reports drift
  /// of a metre or two per second; counting it adds a few hundred metres to a standing rest.
  stationaryMS: 0.6,
  /// Shortest baseline over which movement is measured when the platform gives no Doppler speed.
  ///
  /// Consecutive fixes cannot settle this question: wander between two fixes a second apart looks
  /// exactly like 2 m/s of running. Over five seconds it usually cannot.
  movementBaselineS: 5,
  /// Slowest an athlete who is moving at all can be going, in m/s. Used only to turn a required
  /// separation in metres into a required baseline in seconds, so it is deliberately pessimistic:
  /// assuming a slow walk makes the window longer than it needs to be for a runner, and a window
  /// that is too long only costs a little corner-cutting.
  slowWalkMS: 1.2,
  /// Longest that baseline is allowed to grow. Beyond this the corner-cutting costs more than the
  /// noise does: net displacement over twenty seconds of a winding route is genuinely short.
  maxBaselineS: 25,
  /// How far the athlete must have travelled, in multiples of the fix's own stated accuracy, before
  /// that travel is taken as a measurement rather than as noise.
  ///
  /// This is the number that was missing, and its absence is what a real run exposed. A fixed
  /// five-second baseline silently assumes the fixes are good: at 4 m accuracy a jogger covers 11 m
  /// in five seconds and the signal wins comfortably, which is what the bench measured and passed.
  /// At 12 m accuracy -- ordinary under trees, between buildings, on a cold start -- a WALKER covers
  /// 4.5 m in three seconds against +/-12 m of wander, and the noise is three times the signal.
  /// Replaying a real 26-minute session through the pipeline at that accuracy, with no Doppler, the
  /// speed read **+159%**: a 13:00/mi walk-run shown as a 5:00/mi sprint.
  ///
  /// So the baseline is no longer a constant. It is however long it takes a slow walker to travel
  /// this many times the fix's own stated accuracy -- computed from the accuracy, never from the
  /// distance it is about to measure -- and when that exceeds maxBaselineS these fixes cannot answer
  /// the question and no pace is reported.
  baselineJitterK: 2.0,
  /// Window for the displayed pace.
  ///
  /// Was fifteen, and fifteen is a duration where what matters is a COUNT. A window smooths by
  /// averaging independent readings, and how many it holds depends on the fix rate: Polar, sampling
  /// at 1 Hz, averages fifteen of them; a phone delivering a fix every four seconds averages four.
  /// Same nominal window, half the noise reduction.
  ///
  /// Measured on a real session recorded against Polar. Over the one block Polar says the athlete
  /// held a steady 12:29/mi, Polar's own trace smoothed over the same fifteen seconds had a spread
  /// of 28 s/mi. This app's tile had 62 s/mi, and ranged from 11:40 to 16:46 while he ran one pace.
  /// The MEAN was right -- 12:44 against Polar's 12:29 -- so nothing was miscalculated; the number
  /// was simply too noisy to act on, which from the outside is indistinguishable from being wrong.
  ///
  /// Twenty-five seconds is where the trade stops paying. Simulated on that same session at its
  /// measured noise: 15s gives 59 s/mi of spread, 20s gives 50, 25s gives 46, 30s gives 43 -- while
  /// the error during the twenty seconds after a real change of pace climbs 1.42 -> 1.67 km/h. A
  /// steadier number costs responsiveness at transitions, and transitions are not when this number
  /// gets acted on.
  smoothS: 25,
  /// Longest gap the acceleration gate will price in. See where `room` is computed.
  maxSlewGapS: 2,
  /// Horizontal distance the grade is measured over. Barometric and GPS altitude are both noisy
  /// enough that a grade from consecutive fixes routinely reads +/-40%.
  gradeRunM: 40,
  /// Roads do not exceed this. Anything beyond is altitude noise.
  maxGrade: 0.30,
  /// A runner cannot change speed faster than this, so a sample that claims otherwise is a bad fix.
  ///
  /// 0.8 rather than 1.5: one and a half metres per second per second is sprint-start acceleration,
  /// which no session in this plan contains. The gate is only as tight as the least plausible thing
  /// it still allows, and at a fix every four seconds -- with the elapsed term capped at two seconds
  /// -- 1.5 let a single bad Doppler reading pull the displayed pace by 47 s/km. 0.8 covers a walk
  /// breaking into a jog (about 1 m/s over three seconds) with room to spare.
  ///
  /// The same idea as the heart-rate slew gate in the engine, and it belongs here for the same
  /// reason: a physical impossibility is a cleaner filter than any statistical one. Trimming the
  /// window was tried first and made things worse — under symmetric jitter it throws away
  /// information, and it only ever helped against the spikes this catches directly.
  maxAccelMS2: 0.8,
};

export class GpsTrack {
  constructor(opts = {}) {
    this.cfg = { ...GeoDefaults, ...opts };
    this.distanceM = 0;
    /// Distance from integrating measured speed, rather than from summing position steps.
    ///
    /// Both are kept because they disagree, and a session with Polar Flow recording alongside
    /// showed which way. Position-based: Polar 3109 m, this app 3064 m. Speed-based: Polar 2430 m,
    /// this app 2412 m. The two devices agree with each other WITHIN each method and disagree
    /// across them by a quarter — so the split is not a bug in either device, it is the method.
    ///
    /// The recording settled it by accident: the athlete left it running for thirty-three minutes
    /// while sitting on a couch, and Polar's position-based distance grew by 670 m — twenty metres
    /// a minute of pure drift. Apply that rate to the run and 532 m of the 3109 m was never
    /// travelled, which lands close to the speed-based figure. Position-differencing adds length
    /// for every wobble; at 14 m accuracy there are a lot of wobbles.
    this.distanceFromSpeedM = 0;
    this.path = [];                 // accepted [lat, lon, t, alt] — the route
    this.lastAccepted = null;
    this.lastAccuracy = null;
    this.speedWindow = [];          // [t, m/s]
    this.recent = [];               // accepted fixes inside the movement baseline
    this.altWindow = [];            // [cumulativeDistance, alt]
    this.rejected = 0;
    this.accepted = 0;
    /// Accepted fixes that carried a usable Doppler speed. The two speed paths have different error
    /// characteristics, so a session that paced badly is a different investigation depending on
    /// which one was live — and from a phone there is otherwise no way to tell.
    this.doppler = 0;
  }

  /**
   * Speed from net displacement, over a baseline long enough for the displacement to outrun the noise.
   *
   * The window length comes from the fix's stated accuracy and a pessimistic walking speed, so it is
   * long when the fixes are poor and short when they are good -- and it is decided BEFORE the
   * distance it will measure is looked at, which is what keeps it unbiased.
   *
   * Returns null when no anchor inside maxBaselineS clears the floor. That is not a failure to
   * report — at 12 m accuracy and a slow walk it is the truthful answer, and the alternative is the
   * +159% over-read a real session actually produced. Null propagates to `paceSecKm`, the display
   * shows no pace, and the coach stands down instead of shouting a number it made up.
   */
  _baselineSpeed(lat, lon, t, accuracy) {
    // How long the baseline needs to be is decided by the accuracy and a conservative walking speed,
    // and by nothing else. The obvious alternative -- walk back until the measured displacement
    // clears the floor -- is a selection on the noisy quantity itself and is badly biased: it stops
    // early exactly when noise happens to inflate the displacement, so it keeps the inflated ones.
    // Tried on the real session it was WORSE than the fixed window at clean accuracy, +42% against
    // +12%. Choosing the window by time alone, before looking at the distance it will measure,
    // leaves the noise symmetric.
    const needS = (this.cfg.baselineJitterK * (accuracy ?? 0)) / this.cfg.slowWalkMS;
    if (needS > this.cfg.maxBaselineS) return null;      // these fixes cannot answer the question
    const target = Math.max(this.cfg.movementBaselineS, needS);
    // The newest anchor that is at least `target` old: closest to the window we asked for, without
    // ever being shorter than it.
    let anchor = null;
    for (let i = this.recent.length - 2; i >= 0; i--) {
      if (t - this.recent[i].t >= target) { anchor = this.recent[i]; break; }
    }
    if (!anchor) return null;                            // not enough history yet
    return haversine(anchor, { lat, lon }) / (t - anchor.t);
  }

  /**
   * Feed one fix. Returns `{accepted, reason}` — `reason` names the rejection so a run that
   * collected nothing can say why rather than just showing zeroes.
   */
  add({ lat, lon, alt = null, accuracy = null, speed = null, t }) {
    this.lastAccuracy = accuracy;

    if (accuracy == null || accuracy > this.cfg.maxAccuracyM) {
      this.rejected++;
      // Deliberately NOT updating lastAccepted. A rejected fix must not become the baseline for the
      // next segment, or one loose reading corrupts two.
      return { accepted: false, reason: 'accuracy' };
    }

    const prev = this.lastAccepted;
    let segment = 0, dt = 0, derived = null;

    if (prev) {
      dt = t - prev.t;
      if (dt <= 0) { this.rejected++; return { accepted: false, reason: 'time went backwards' }; }
      segment = haversine(prev, { lat, lon });
      derived = segment / dt;
      if (derived > this.cfg.maxSpeedMS) {
        this.rejected++;
        return { accepted: false, reason: 'implausible jump' };
      }
    }

    // Confirm movement before counting any of it, over a baseline long enough for the movement to
    // be distinguishable from the wander. See baselineJitterK: the length that takes is a property
    // of how good the fixes are and how fast the athlete is going, so it cannot be a constant.
    this.recent.push({ lat, lon, t, accuracy });
    this.recent = this.recent.filter(f => f.t >= t - this.cfg.maxBaselineS);
    const netMS = this._baselineSpeed(lat, lon, t, accuracy);

    // Doppler speed when the platform supplies a valid one — it is measured rather than inferred and
    // is markedly better than differencing two positions. iOS uses -1 for "unknown".
    //
    // Without it, the baseline displacement rate rather than the per-fix one, and the difference is
    // not small. Jitter can only ever LENGTHEN an apparent step — haversine returns a distance, so
    // noise has no sign to cancel against — which makes consecutive-fix differencing biased one way,
    // always fast, and worse the shorter the interval. Measured against a known ground-truth speed
    // with 4 m of jitter: a jog differenced fix-to-fix at 1 Hz reads **+109%**, more than double the
    // speed actually run. Over the five-second baseline the same trace reads +3.9%.
    //
    // The cost is real and much smaller: net displacement cuts corners, so a route turning ninety
    // degrees every thirty seconds reads 1-3% slow. Trading a 3% under-read on bends for a 109%
    // over-read on the straights is not a close call.
    //
    // And when the baseline cannot clear the noise floor, there is NO number — not `derived` as a
    // consolation. `derived` is the estimator this replaced; falling back to it whenever the going
    // gets noisy would reinstate the bug exactly where it does the most damage, since the conditions
    // that stop the baseline resolving are the same ones that make per-fix differencing worst.
    // `paceSecKm` then reads null, the tile shows no pace, and the coach stands down. Saying nothing
    // is a bad outcome; saying 5:00/mi to a man walking is a worse one.
    const hasDoppler = speed != null && speed >= 0 && speed <= this.cfg.maxSpeedMS;
    if (hasDoppler) this.doppler++;
    let v = hasDoppler ? speed : netMS;

    // Doppler settles it when the platform supplies one; otherwise net displacement over the
    // baseline does. Falling back to the per-fix speed would reinstate the bug this replaces.
    const movingBy = (speed != null && speed >= 0) ? speed : netMS;
    const moving = movingBy == null ? true : movingBy >= this.cfg.stationaryMS;

    if (prev && moving) this.distanceM += segment;
    if (!moving) v = 0;
    // Integrated from the speed that has already been through the movement gate and, below, the
    // acceleration limit — so a rejected fix contributes nothing rather than a jump.
    if (prev && moving && v != null && v > 0) {
      this.distanceFromSpeedM += v * Math.max(0, Math.min(5, t - prev.t));
    }

    // Reject a speed no runner could have reached from the last one. See maxAccelMS2.
    if (v != null && this.speedWindow.length) {
      const [lastT, lastV] = this.speedWindow[this.speedWindow.length - 1];
      // The elapsed term is CAPPED, and the cap is the whole point. Written as accel x elapsed it
      // grows without limit as fixes get sparser: at one fix every four seconds -- ordinary on a
      // phone -- it allows a 6 m/s step between readings, which is larger than the rejection
      // threshold, so the gate stops existing exactly where it is needed. Sweeping it over this
      // athlete's own recorded session confirmed it: tightening the constant from 1.5 to 0.25
      // changed the displayed pace's steadiness by one second per mile. It was not doing anything.
      //
      // Two seconds of acceleration is a real athlete's worst case -- a standing start into a
      // sprint -- so beyond that the gap is the radio being slow, not the legs being fast.
      const room = this.cfg.maxAccelMS2 * Math.min(this.cfg.maxSlewGapS, Math.max(0.5, t - lastT));
      if (Math.abs(v - lastV) > room) v = lastV + Math.sign(v - lastV) * room;
    }
    if (v != null) {
      this.speedWindow.push([t, v]);
      this.speedWindow = this.speedWindow.filter(([tt]) => tt >= t - this.cfg.smoothS);
    }

    if (alt != null) {
      this.altWindow.push([this.distanceM, alt]);
      this.altWindow = this.altWindow.filter(([d]) => d >= this.distanceM - this.cfg.gradeRunM * 2);
    }

    this.lastAccepted = { lat, lon, t, alt };
    this.path.push([lat, lon, t, alt]);
    this.accepted++;
    return { accepted: true, reason: '' };
  }

  /**
   * Smoothed speed in m/s, or null when there is nothing recent enough to trust.
   *
   * A plain mean, because spikes are rejected on the way in rather than averaged out afterwards.
   *
   * No amount of smoothing removes the underlying uncertainty: with pessimistic jitter the display
   * still moves by around twenty seconds per kilometre, and smoothing harder to hide that would only
   * make the number lag the running. The coaching does not depend on this value — the band monitor
   * runs its own twenty-second window with hysteresis on top.
   */
  get speedMS() {
    const n = this.speedWindow.length;
    if (!n) return null;
    return this.speedWindow.reduce((a, [, v]) => a + v, 0) / n;
  }

  /** Smoothed pace in seconds per kilometre, or null when standing still. */
  get paceSecKm() {
    const v = this.speedMS;
    return v != null && v > this.cfg.stationaryMS ? 1000 / v : null;
  }

  /**
   * Grade over the last `gradeRunM` of travel, clamped to what a road actually does.
   *
   * Returns 0 rather than null when it cannot be measured: the pace band multiplies by the grade
   * factor, and 0 is the identity. A null here would have to be defended at every call site.
   */
  get grade() {
    if (this.altWindow.length < 2) return 0;
    const [d1, a1] = this.altWindow[this.altWindow.length - 1];
    let base = null;
    for (let i = this.altWindow.length - 2; i >= 0; i--) {
      if (d1 - this.altWindow[i][0] >= this.cfg.gradeRunM) { base = this.altWindow[i]; break; }
    }
    if (!base) return 0;
    const run = d1 - base[0];
    if (run < 5) return 0;
    const g = (a1 - base[1]) / run;
    return Math.max(-this.cfg.maxGrade, Math.min(this.cfg.maxGrade, g));
  }

  /** True when there is a recent, trustworthy fix to coach from. */
  trustedAt(t) {
    if (this.lastAccuracy == null || this.lastAccuracy > this.cfg.maxAccuracyM) return false;
    if (!this.lastAccepted) return false;
    // A fix older than five seconds is a memory, not a position — the same rule the armband logger
    // applies to a stale heart rate, and for the same reason.
    return (t - this.lastAccepted.t) <= 5;
  }

  /** Total climb in metres, over the whole accepted path. */
  get ascentM() {
    let up = 0, last = null;
    for (const [, , , alt] of this.path) {
      if (alt == null) continue;
      if (last != null && alt > last) up += alt - last;
      last = alt;
    }
    return up;
  }

  /**
   * The route, projected to x/y metres relative to its own bounding box, ready to draw.
   *
   * An equirectangular projection is right here and would be wrong on a continental scale: over a
   * few kilometres the error is millimetres, and it avoids shipping a projection library into a page
   * that has to stay one file.
   */
  projected() {
    if (this.path.length < 2) return { points: [], w: 0, h: 0 };
    const lats = this.path.map(p => p[0]), lons = this.path.map(p => p[1]);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats);
    const minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const midLat = (minLat + maxLat) / 2;
    const mPerDegLat = 111132.92 - 559.82 * Math.cos(2 * midLat * Math.PI / 180);
    const mPerDegLon = 111412.84 * Math.cos(midLat * Math.PI / 180);
    const points = this.path.map(([la, lo, t]) => [
      (lo - minLon) * mPerDegLon,
      (maxLat - la) * mPerDegLat,      // y grows downward, as a canvas expects
      t,
    ]);
    return {
      points,
      w: Math.max(1, (maxLon - minLon) * mPerDegLon),
      h: Math.max(1, (maxLat - minLat) * mPerDegLat),
    };
  }
}
