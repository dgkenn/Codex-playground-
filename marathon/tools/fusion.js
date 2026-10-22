// Speed and distance from several independent sources, combined every second.
//
// Why this exists
// ---------------
// Checked against the real length of his routes (map-matched to the road network where the match was
// confident, agreeing with the recorded trace to 0.7%), the app's distance read 11% short on 22
// October and 14% short on 6 October. Polar Flow's own speed log, from the same phone, was just as
// short -- so it is the speed the phone reports, not only this app's arithmetic. Distance from GPS
// POSITIONS read 7-11% long instead: every wobble of a fix adds length. One source under, one over,
// neither right.
//
// Published validation of iPhone GPS running apps finds about 2% under-reading on an open track, so
// 11-14% is not a law of nature; it is something that can be measured and taken out. Three
// independent channels, each good at what the others are bad at:
//
//   GPS speed x a learned scale. The phone's speed is smooth and responsive but, on his evidence,
//     biased low. The bias is measured in-session: over long, straight stretches with tight fixes,
//     the straight-line distance between two positions a minute apart is an unbiased reference (the
//     wobble of two endpoints is a few metres against a hundred-plus of travel, and averages out),
//     so  scale = sum(chord) / sum(integrated speed)  over those stretches. Kept between sessions.
//
//   Steps x stride, from the phone's own accelerometer (the Verity Sense's raw motion data appears to
//     need Polar's SDK mode, which is why it reports "no accelerometer"). Cadence is measured every
//     step and needs no satellites -- under trees, between buildings, in a GPS drop-out it carries on.
//     Stride is learned against the calibrated GPS speed while the GPS is good and the pace steady,
//     as a line in cadence (longer strides at higher cadence), the method behind footpods, Garmin's
//     stride length and AutoGait. Kept between sessions.
//
//   Stillness. No steps for three seconds is standing still, which GPS can never be sure of: a
//     stationary phone's fixes wander a metre or two a second. This pins speed to zero at a crossing.
//
// A one-dimensional Kalman filter combines whichever are present each second, weighting each by how
// much it is trusted at that moment (GPS by its stated accuracy, stride by how much calibration is
// behind it), and distance is the integral of the result. Any one channel can disappear and the
// others carry on; with only GPS it is still GPS with its bias taken out.

export const FusionDefaults = {
  /// Fixes looser than this are not used for anything here.
  maxAccuracyM: 20,
  /// Fixes this tight or tighter can calibrate the GPS scale and the stride.
  calibAccuracyM: 12,
  /// Calibration window: long enough that endpoint wobble is small against the travel.
  calibWindowS: 60,
  /// ...and only on stretches this straight (chord / summed path), so corner-cutting cannot bias it.
  calibStraightness: 0.985,
  /// Minimum travel for a window to count.
  calibMinM: 80,
  /// The GPS scale is believed within these bounds and nowhere else: a "measurement" outside them is
  /// a broken window, not a phone.
  scaleMin: 0.8, scaleMax: 1.35,
  /// Seconds of calibration behind the stride model before it is trusted as a speed source.
  strideTrustS: 45,
  /// Below this the phone is taken to be still (no step for this long).
  stillAfterS: 3,
  /// Kalman process noise: how fast speed can plausibly change, m/s per sqrt(s).
  processSd: 0.35,
};

/** Great-circle distance in metres. */
function hav(a, b) {
  const R = 6371008.8, rad = d => d * Math.PI / 180;
  const dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(s)));
}

/**
 * Steps from accelerometer magnitude.
 *
 * Gravity is removed with a slow running mean, the remainder smoothed lightly, and a step is a peak
 * above an adaptive threshold at least 0.27 s after the last (220 steps a minute, faster than any
 * cadence in this plan). Works with the phone in a pocket, an armband or a hand: what is counted is
 * the impact, and each foot makes one.
 */
export class StepDetector {
  constructor() {
    this.mean = null; this.smooth = 0; this.prev = 0; this.prev2 = 0;
    this.var = 1; this.lastStepT = -Infinity; this.steps = []; // times of steps
  }

  /** One accelerometer reading (m/s^2, gravity included). Returns true when a step is detected. */
  add(t, ax, ay, az) {
    if (ax == null || ay == null || az == null) return false;
    const m = Math.hypot(ax, ay, az);
    this.mean = this.mean == null ? m : this.mean + (m - this.mean) * 0.02;
    const x = m - this.mean;
    this.smooth += (x - this.smooth) * 0.35;
    this.var += (this.smooth * this.smooth - this.var) * 0.01;
    const thr = Math.max(1.0, 0.6 * Math.sqrt(this.var));
    // A peak: the previous sample was above both neighbours and above the threshold.
    let step = false;
    if (this.prev > thr && this.prev >= this.prev2 && this.prev > this.smooth && t - this.lastStepT >= 0.27) {
      step = true;
      this.lastStepT = t;
      this.steps.push(t);
    }
    this.prev2 = this.prev; this.prev = this.smooth;
    while (this.steps.length && this.steps[0] < t - 10) this.steps.shift();
    return step;
  }

  /** Steps per minute over the last `windowS`, or null with fewer than 4 steps in it. */
  cadence(t, windowS = 6) {
    const xs = this.steps.filter(s => s > t - windowS);
    if (xs.length < 4) return null;
    return 60 * (xs.length - 1) / (xs[xs.length - 1] - xs[0]);
  }

  /** Seconds since the last step. */
  sinceStep(t) { return t - this.lastStepT; }
}

/**
 * Stride as a line in cadence, learned by exponentially-weighted least squares from (cadence, speed)
 * pairs taken while the GPS is good and the pace steady.
 */
export class StrideModel {
  constructor(saved = null) {
    // Sufficient statistics, decayed so the model follows him as he gets fitter.
    Object.assign(this, { n: 0, sx: 0, sy: 0, sxx: 0, sxy: 0, seconds: 0 }, saved || {});
  }

  add(cadenceSpm, strideM) {
    const k = 0.998;
    this.n = this.n * k + 1;
    this.sx = this.sx * k + cadenceSpm; this.sy = this.sy * k + strideM;
    this.sxx = this.sxx * k + cadenceSpm * cadenceSpm; this.sxy = this.sxy * k + cadenceSpm * strideM;
    this.seconds += 1;
  }

  /** Stride in metres at this cadence, or null before there is anything to go on. */
  stride(cadenceSpm) {
    if (this.n < 5) return null;
    const mx = this.sx / this.n, my = this.sy / this.n;
    const vx = this.sxx / this.n - mx * mx;
    // With a narrow spread of cadences the slope is not identifiable; use the mean stride alone.
    if (vx < 25) return my;
    let b = (this.sxy / this.n - mx * my) / vx;
    b = Math.max(0, Math.min(0.02, b));          // longer strides at higher cadence, within reason
    return Math.max(0.3, my + b * (cadenceSpm - mx));
  }

  toJSON() {
    const { n, sx, sy, sxx, sxy, seconds } = this;
    return { n, sx, sy, sxx, sxy, seconds };
  }
}

export class SpeedFusion {
  /**
   * `saved` is what `state()` returned at the end of an earlier session: the GPS scale and the stride
   * model carry over, so a new session starts calibrated rather than from scratch.
   */
  constructor({ saved = null, ...opts } = {}) {
    this.cfg = { ...FusionDefaults, ...opts };
    this.steps = new StepDetector();
    this.strideModel = new StrideModel(saved && saved.stride);
    // The GPS scale: sum of reference chords and of integrated speed over qualifying windows, with
    // the carried-over value entered as a prior worth a few windows.
    const prior = saved && saved.scale && saved.scale >= this.cfg.scaleMin && saved.scale <= this.cfg.scaleMax
      ? saved.scale : 1;
    this.scaleChord = 150 * prior; this.scaleSpeed = 150;
    this.windows = 0;
    this.fixes = [];               // recent accepted fixes {t, lat, lon, acc, v, cum}
    this.lastFix = null;
    this.x = 0; this.P = 1;        // Kalman state: speed and its variance
    this.lastT = null;
    this.distanceM = 0;
    this.distanceGpsM = 0;         // calibrated GPS alone, for comparison
    this.shares = { gps: 0, steps: 0, still: 0, none: 0 };
    this.lastSource = 'none';
    this.motionSeen = false;
  }

  get scale() { return this.scaleChord / this.scaleSpeed; }

  /** One GPS fix. `speed` is the phone's own (Doppler) speed in m/s, or null/negative if unknown. */
  gps({ t, lat, lon, accuracy, speed }) {
    if (accuracy == null || accuracy > this.cfg.maxAccuracyM || lat == null) return;
    const v = speed != null && speed >= 0 && speed <= 8 ? speed : null;
    const prev = this.fixes[this.fixes.length - 1];
    const dt = prev ? t - prev.t : 0;
    if (prev && dt <= 0) return;
    // Integrated phone speed, for the scale; trapezoid over the gap, capped at 10 s (a longer gap is
    // not integrated and so cannot enter a calibration window).
    const cum = prev ? prev.cum + (v != null && prev.v != null && dt <= 10 ? (v + prev.v) / 2 * dt : 0) : 0;
    const fix = { t, lat, lon, acc: accuracy, v, cum, gap: !prev || dt > 10 || v == null || prev.v == null };
    this.fixes.push(fix);
    while (this.fixes.length && this.fixes[0].t < t - this.cfg.calibWindowS * 2) this.fixes.shift();
    this.lastFix = fix;
    this._calibrate(fix);
  }

  /** Try to close a calibration window ending at this fix. */
  _calibrate(end) {
    if (end.acc > this.cfg.calibAccuracyM || end.v == null) return;
    const want = end.t - this.cfg.calibWindowS;
    let i = this.fixes.length - 1;
    while (i > 0 && this.fixes[i - 1].t >= want) i -= 1;
    const start = this.fixes[i];
    if (!start || end.t - start.t < this.cfg.calibWindowS * 0.8 || start.acc > this.cfg.calibAccuracyM) return;
    const win = this.fixes.slice(i);
    if (win.some((f, k) => k > 0 && f.gap)) return;
    // Do not reuse the same stretch: windows must not overlap.
    if (this._lastWindowEnd != null && start.t < this._lastWindowEnd) return;
    // Straightness over points ~10 s apart: summing 1 Hz fixes would add every wobble to the path
    // (the very bias this corrects) and no window would ever look straight.
    let path = 0, last = win[0];
    for (let k = 1; k < win.length; k++) {
      if (win[k].t - last.t >= 10 || k === win.length - 1) { path += hav(last, win[k]); last = win[k]; }
    }
    const chord = hav(start, end);
    const integ = end.cum - start.cum;
    if (chord < this.cfg.calibMinM || integ <= 0 || path <= 0) return;
    if (chord / path < this.cfg.calibStraightness) return;
    const r = chord / integ;
    if (r < this.cfg.scaleMin || r > this.cfg.scaleMax) return;
    this.scaleChord += chord; this.scaleSpeed += integ;
    this.windows += 1;
    this._lastWindowEnd = end.t;
  }

  /** One accelerometer reading (m/s^2, gravity included). */
  motion({ t, ax, ay, az }) {
    // A browser can fire motion events with nothing in them; those are not a sensor.
    if (![ax, ay, az].every(Number.isFinite)) return;
    this.motionSeen = true;
    if (this.steps.add(t, ax, ay, az)) this.stepsEver = true;
  }

  /**
   * Advance to time t (seconds) and return the fused estimate:
   * `{speedMS, distanceM, source, cadence, trusted}`. Call once a second.
   */
  tick(t) {
    const dt = this.lastT == null ? 0 : Math.max(0, Math.min(5, t - this.lastT));
    this.lastT = t;
    // Predict: speed may have changed.
    this.P += (this.cfg.processSd ** 2) * Math.max(dt, 1);

    const fix = this.lastFix && t - this.lastFix.t <= 3 ? this.lastFix : null;
    const gpsV = fix && fix.v != null ? fix.v * this.scale : null;
    // A motion sensor that sees no steps while GPS has said "moving" for twenty seconds is not
    // seeing this run -- a desktop browser, a phone wedged somewhere that does not jolt -- and its
    // "no steps" must not pin the speed to zero. It is set aside for the rest of the session.
    if (this.motionSeen && !this.motionUnusable) {
      const movingByGps = gpsV != null && gpsV > 1.2 && fix.acc <= this.cfg.calibAccuracyM;
      this.silentMovingS = movingByGps && this.steps.sinceStep(t) > this.cfg.stillAfterS
        ? (this.silentMovingS || 0) + 1 : 0;
      if (this.silentMovingS >= 20) this.motionUnusable = true;
    }
    const motionOk = this.motionSeen && !this.motionUnusable;
    const cad = motionOk ? this.steps.cadence(t) : null;
    // Still only on a sensor that has shown it can see steps, and only when GPS does not say moving.
    const still = motionOk && this.stepsEver && this.steps.sinceStep(t) > this.cfg.stillAfterS
                  && !(gpsV != null && gpsV > 1.2);
    const sources = [];

    // Learn the stride while the GPS is good and the pace has held (current speed close to the
    // speed a few seconds ago), so the reference is not a transition.
    if (gpsV != null && cad != null && fix.acc <= this.cfg.calibAccuracyM && gpsV > 0.8) {
      const steady = this.fixes.filter(f => f.t >= t - 6 && f.v != null).map(f => f.v * this.scale);
      if (steady.length >= 3 && Math.max(...steady) - Math.min(...steady) < 0.35) {
        // Learned against the phone's RAW speed, and scaled at use: a correction to the scale later
        // in the session then applies to the steps channel at once, instead of the stride carrying
        // whatever the scale was when each second was learned.
        this.strideModel.add(cad, fix.v / (cad / 60));
      }
    }

    if (still) {
      this._update(0, 0.05 ** 2); sources.push('still');
    } else {
      if (gpsV != null) {
        const sd = 0.15 + 0.015 * fix.acc;
        this._update(gpsV, sd * sd); sources.push('gps');
      } else if (fix) {
        // No phone speed at all: positions over a 10-25 s baseline, never fix to fix (jitter only
        // ever lengthens a short step). Unscaled -- a chord is not biased the way the phone's speed
        // is -- and trusted less.
        const back = this.fixes.filter(f => f.t <= fix.t - 10 && f.t >= fix.t - 25).pop();
        if (back) {
          const v = hav(back, fix) / (fix.t - back.t);
          const sd = 0.3 + 0.03 * Math.max(fix.acc, back.acc);
          if (v < 8) { this._update(v, sd * sd); sources.push('gps-pos'); }
        }
      }
      const stride = cad != null && this.strideModel.seconds >= this.cfg.strideTrustS
        ? this.strideModel.stride(cad) : null;
      if (stride != null) {
        this._update(cad / 60 * stride * this.scale, 0.12 ** 2); sources.push('steps');
      }
    }
    if (!sources.length && this.P > 4) this.x = 0;          // nothing for a long time: do not coast
    if (this.x < 0) this.x = 0;

    this.distanceM += this.x * dt;
    if (gpsV != null) this.distanceGpsM += gpsV * dt;
    if (sources.length) this.lastMeasT = t;
    const source = sources.length ? sources.join('+') : 'none';
    const key = sources.includes('still') ? 'still' : sources.includes('steps') ? 'steps'
              : sources.some(x => x.startsWith('gps')) ? 'gps' : 'none';
    this.shares[key] += dt;
    this.lastSource = source;
    // Trusted for six seconds after any measurement: an iPhone often delivers a fix every two to five
    // seconds, and a coach that goes quiet between fixes is a coach that never speaks.
    return { speedMS: this.x, distanceM: this.distanceM, source, cadence: cad,
             trusted: this.lastMeasT != null && t - this.lastMeasT <= 6 };
  }

  _update(z, r) {
    const k = this.P / (this.P + r);
    this.x += k * (z - this.x);
    this.P *= (1 - k);
  }

  /** What to carry into the next session, and what the diagnostics show. */
  state() {
    return {
      scale: Math.round(this.scale * 1000) / 1000, scaleWindows: this.windows,
      stride: this.strideModel.toJSON(),
      strideAt170: this.strideModel.stride(170) == null ? null
        : Math.round(this.strideModel.stride(170) * this.scale * 100) / 100,
      strideSeconds: this.strideModel.seconds,
      motion: this.motionSeen, motionUnusable: !!this.motionUnusable,
      distanceM: Math.round(this.distanceM),
      distanceGpsM: Math.round(this.distanceGpsM),
      shares: Object.fromEntries(Object.entries(this.shares).map(([k, v]) => [k, Math.round(v)])),
    };
  }
}
