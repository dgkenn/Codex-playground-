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
  /// Baseline over which movement is *confirmed*, when the platform gives no Doppler speed.
  ///
  /// Consecutive fixes cannot settle this question: wander between two fixes a second apart looks
  /// exactly like 2 m/s of running. Over five seconds it cannot — random drift stays within a couple
  /// of metres while real running covers fourteen. The distance itself is still the sum of the
  /// per-fix segments, which is what keeps corners accurate; this only gates whether to count them.
  movementBaselineS: 5,
  /// Window for the displayed pace.
  ///
  /// Fifteen seconds rather than ten because ten left the number swinging by nearly 50 s/km under
  /// pessimistic Doppler jitter — the gap between 5:57 and 6:46, which is not a number anyone can
  /// act on. Still shorter than the band monitor's own twenty-second window, so the display never
  /// lags the coaching.
  smoothS: 15,
  /// Horizontal distance the grade is measured over. Barometric and GPS altitude are both noisy
  /// enough that a grade from consecutive fixes routinely reads +/-40%.
  gradeRunM: 40,
  /// Roads do not exceed this. Anything beyond is altitude noise.
  maxGrade: 0.30,
  /// A runner cannot change speed faster than this, so a sample that claims otherwise is a bad fix.
  ///
  /// The same idea as the heart-rate slew gate in the engine, and it belongs here for the same
  /// reason: a physical impossibility is a cleaner filter than any statistical one. Trimming the
  /// window was tried first and made things worse — under symmetric jitter it throws away
  /// information, and it only ever helped against the spikes this catches directly.
  maxAccelMS2: 1.5,
};

export class GpsTrack {
  constructor(opts = {}) {
    this.cfg = { ...GeoDefaults, ...opts };
    this.distanceM = 0;
    this.path = [];                 // accepted [lat, lon, t, alt] — the route
    this.lastAccepted = null;
    this.lastAccuracy = null;
    this.speedWindow = [];          // [t, m/s]
    this.recent = [];               // accepted fixes inside the movement baseline
    this.altWindow = [];            // [cumulativeDistance, alt]
    this.rejected = 0;
    this.accepted = 0;
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

    // Doppler speed when the platform supplies a valid one — it is measured rather than inferred and
    // is markedly better than differencing two positions. iOS uses -1 for "unknown".
    let v = (speed != null && speed >= 0 && speed <= this.cfg.maxSpeedMS) ? speed : derived;

    // Confirm movement before counting any of it.
    this.recent.push({ lat, lon, t });
    this.recent = this.recent.filter(f => f.t >= t - this.cfg.movementBaselineS);
    const anchor = this.recent[0];
    const anchorDt = t - anchor.t;
    const netMS = anchorDt >= this.cfg.movementBaselineS * 0.6
      ? haversine(anchor, { lat, lon }) / anchorDt
      : null;

    // Doppler settles it when the platform supplies one; otherwise net displacement over the
    // baseline does. Falling back to the per-fix speed would reinstate the bug this replaces.
    const movingBy = (speed != null && speed >= 0) ? speed : netMS;
    const moving = movingBy == null ? true : movingBy >= this.cfg.stationaryMS;

    if (prev && moving) this.distanceM += segment;
    if (!moving) v = 0;

    // Reject a speed no runner could have reached from the last one. See maxAccelMS2.
    if (v != null && this.speedWindow.length) {
      const [lastT, lastV] = this.speedWindow[this.speedWindow.length - 1];
      const room = this.cfg.maxAccelMS2 * Math.max(0.5, t - lastT);
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
