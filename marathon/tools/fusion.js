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
//   Steps x stride, from two accelerometers: the phone's own, and the Verity Sense's (52 Hz in its
//     normal mode, started over Polar's measurement service -- see sensor.js). Cadence is measured
//     every step and needs no satellites -- under trees, between buildings, in a GPS drop-out it
//     carries on. Stride is learned against the GPS speed while the GPS is good and the pace steady,
//     from cadence and how hard the steps land, the method behind footpods, Garmin's stride length
//     and AutoGait. Each accelerometer has its own model; either can drop out. Kept between sessions.
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
    this.peaks = [];                                            // [t, peak] per step
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
      this.peaks.push([t, this.prev]);
    }
    this.prev2 = this.prev; this.prev = this.smooth;
    while (this.steps.length && this.steps[0] < t - 10) this.steps.shift();
    while (this.peaks.length && this.peaks[0][0] < t - 10) this.peaks.shift();
    return step;
  }

  /**
   * Steps per minute from the last four step intervals (median, so one missed or doubled step does
   * not swing it): about a second and a half of history, where a six-second window was six. Null
   * with too few steps, or when the last step is too long ago for the rhythm to still hold.
   */
  cadence(t) {
    const xs = this.steps.filter(s => s > t - 6);
    if (xs.length < 5) return null;
    const iv = [];
    for (let i = xs.length - 4; i < xs.length; i++) iv.push(xs[i] - xs[i - 1]);
    iv.sort((a, b) => a - b);
    const med = (iv[1] + iv[2]) / 2;
    if (t - xs[xs.length - 1] > 1.5 * med + 0.5) return null;
    return 60 / med;
  }

  /** How hard the recent steps landed (mean peak, in the detector's units), or null. */
  intensity(t) {
    const ps = this.peaks.filter(([pt]) => pt > t - 4).map(([, p]) => p);
    return ps.length >= 3 ? ps.reduce((a, b) => a + b, 0) / ps.length : null;
  }

  /** Seconds since the last step. */
  sinceStep(t) { return t - this.lastStepT; }
}

/**
 * Stride from cadence and impact intensity, learned by exponentially-weighted ridge regression from
 * (cadence, intensity, stride) taken while the GPS is good and the pace steady.
 *
 * Intensity is there because the literature is consistent that within running, speed changes mostly
 * through stride length while step frequency barely moves -- so a stride fixed by cadence alone can
 * only follow a change of pace as slowly as the GPS teaches it. Harder landings go with longer, faster
 * strides; the regression learns by how much, per sensor (a phone in a pocket and a band on the arm
 * feel the same step differently, so each source has its own model).
 */
export class StrideModel {
  constructor(saved = null) {
    this.seconds = 0;
    // Normal-equation sums for features [1, cadence - 160, intensity - i0], decayed.
    this.A = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    this.b = [0, 0, 0];
    this.i0 = null;
    if (saved && saved.A && saved.b) Object.assign(this, { A: saved.A, b: saved.b, i0: saved.i0, seconds: saved.seconds || 0 });
  }

  _f(cad, inten) {
    return [1, cad - 160, inten == null || this.i0 == null ? 0 : inten - this.i0];
  }

  add(cadenceSpm, intensity, strideM) {
    if (this.i0 == null && intensity != null) this.i0 = intensity;
    const f = this._f(cadenceSpm, intensity), k = 0.998;
    for (let i = 0; i < 3; i++) {
      this.b[i] = this.b[i] * k + f[i] * strideM;
      for (let j = 0; j < 3; j++) this.A[i][j] = this.A[i][j] * k + f[i] * f[j];
    }
    this.seconds += 1;
  }

  /** Ridge solution; `fixCad` pins the cadence slope and refits the rest around it. */
  _solve(fixCad = null) {
    if (this.A[0][0] < 5) return null;
    // Ridge on the two slopes keeps them at zero until the data actually shows them.
    let M = this.A.map((r, i) => r.map((v, j) => v + (i === j && i > 0 ? (i === 1 ? 50 : 5) : 0)));
    let v = this.b.slice();
    let idx = [0, 1, 2];
    if (fixCad != null) {
      idx = [0, 2];
      v = idx.map(i => v[i] - M[i][1] * fixCad);
      M = idx.map(i => idx.map(j => M[i][j]));
    }
    const n = idx.length;
    // Gaussian elimination with partial pivoting.
    for (let c = 0; c < n; c++) {
      let p = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
      [M[c], M[p]] = [M[p], M[c]]; [v[c], v[p]] = [v[p], v[c]];
      if (Math.abs(M[c][c]) < 1e-9) return null;
      for (let r = c + 1; r < n; r++) {
        const m = M[r][c] / M[c][c];
        for (let k = c; k < n; k++) M[r][k] -= m * M[c][k];
        v[r] -= m * v[c];
      }
    }
    const y = new Array(n).fill(0);
    for (let r = n - 1; r >= 0; r--) {
      let acc = v[r];
      for (let k = r + 1; k < n; k++) acc -= M[r][k] * y[k];
      y[r] = acc / M[r][r];
    }
    return fixCad == null ? y : [y[0], fixCad, y[1]];
  }

  /** Stride in metres at this cadence and landing intensity, or null before there is anything to go on. */
  stride(cadenceSpm, intensity = null) {
    let x = this._solve();
    if (!x) return null;
    // Keep the cadence slope physical (no shorter stride at a higher cadence, within reason). A slope
    // outside that is pinned and the rest refitted, so the answer at the cadences actually seen stays
    // what the data says: clipping it after the fact would move every prediction away from 160 spm.
    const pinned = Math.max(0, Math.min(0.02, x[1]));
    if (pinned !== x[1]) x = this._solve(pinned) || x;
    const f = this._f(cadenceSpm, intensity);
    return Math.max(0.3, x[0] + x[1] * f[1] + x[2] * f[2]);
  }

  toJSON() { return { A: this.A, b: this.b, i0: this.i0, seconds: this.seconds }; }
}

export class SpeedFusion {
  /**
   * `saved` is what `state()` returned at the end of an earlier session: the GPS scale and the stride
   * model carry over, so a new session starts calibrated rather than from scratch.
   */
  constructor({ saved = null, ...opts } = {}) {
    this.cfg = { ...FusionDefaults, ...opts };
    this.steps = new StepDetector();           // the phone's accelerometer
    this.armSteps = new StepDetector();        // the armband's (Verity Sense, normal mode, 52 Hz)
    this.strideModel = new StrideModel(saved && saved.stride);
    this.armModel = new StrideModel(saved && saved.armStride);
    this.armMean = null;
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
    this.shares = { gps: 0, steps: 0, arm: 0, still: 0, none: 0 };
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

  /**
   * A frame of the armband's accelerometer magnitudes, in its own units, the last at time `t` and the
   * rest spaced at 52 Hz before it. Normalised against its own running mean (gravity), so the units
   * the band happens to report in do not matter.
   */
  arm({ t, mags, hz = 52 }) {
    if (!mags || !mags.length) return;
    for (let i = 0; i < mags.length; i++) {
      const m = mags[i];
      if (!Number.isFinite(m) || m <= 0) continue;
      this.armMean = this.armMean == null ? m : this.armMean + (m - this.armMean) * 0.005;
      const tt = t - (mags.length - 1 - i) / hz;
      this.armSeen = true;
      if (this.armSteps.add(tt, 0, 0, m / this.armMean * 9.81)) this.armStepsEver = true;
    }
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
    // Predict: speed may have changed, by as much as the elapsed time allows (fractional ticks are
    // fine -- the page may ask more often than once a second for a livelier display).
    this.P += (this.cfg.processSd ** 2) * Math.max(dt, 0.25);

    const fix = this.lastFix && t - this.lastFix.t <= 3 ? this.lastFix : null;
    const gpsV = fix && fix.v != null ? fix.v * this.scale : null;
    // Each step source is checked against GPS: one that sees no steps while GPS has said "moving" for
    // twenty seconds is not seeing this run -- a desktop browser, a phone wedged somewhere that does
    // not jolt -- and its "no steps" must not pin the speed to zero. It is set aside for the session.
    const movingByGps = gpsV != null && gpsV > 1.2 && fix.acc <= this.cfg.calibAccuracyM;
    const srcs = [
      { key: 'phone', det: this.steps, model: this.strideModel, seen: this.motionSeen, ever: this.stepsEver, sd: 0.12 },
      { key: 'arm', det: this.armSteps, model: this.armModel, seen: this.armSeen, ever: this.armStepsEver, sd: 0.15 },
    ];
    this._silent = this._silent || { phone: 0, arm: 0 };
    this._unusable = this._unusable || { phone: false, arm: false };
    for (const c of srcs) {
      if (!c.seen || this._unusable[c.key]) continue;
      this._silent[c.key] = movingByGps && c.det.sinceStep(t) > this.cfg.stillAfterS ? this._silent[c.key] + 1 : 0;
      if (this._silent[c.key] >= 20) this._unusable[c.key] = true;
    }
    this.motionUnusable = this._unusable.phone;
    const live = srcs.filter(c => c.seen && !this._unusable[c.key]);
    for (const c of live) { c.cad = c.det.cadence(t); c.inten = c.det.intensity(t); }

    // Learn each source's stride while the GPS is good and the pace has held, against the phone's RAW
    // speed (scaled at use, so a later correction to the scale applies at once).
    if (gpsV != null && fix.acc <= this.cfg.calibAccuracyM && gpsV > 0.8) {
      const steady = this.fixes.filter(f => f.t >= t - 6 && f.v != null).map(f => f.v * this.scale);
      if (steady.length >= 3 && Math.max(...steady) - Math.min(...steady) < 0.35) {
        for (const c of live) if (c.cad != null) c.model.add(c.cad, c.inten, fix.v / (c.cad / 60));
      }
    }

    // Still: every live step source that has shown it can see steps has been quiet for three
    // seconds, and GPS does not say moving.
    const proven = live.filter(c => c.ever);
    const still = proven.length > 0 && proven.every(c => c.det.sinceStep(t) > this.cfg.stillAfterS)
                  && !(gpsV != null && gpsV > 1.2);
    const cad = (live.find(c => c.key === 'phone' && c.cad != null) || live.find(c => c.cad != null) || {}).cad ?? null;

    const sources = [];
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
      // The two accelerometers are not independent witnesses -- both strides were taught by the same
      // GPS -- so they enter as ONE measurement: their weighted mean, trusted as much as the better one.
      // Either alone is enough; together they cover each other's missed steps.
      let wsum = 0, vsum = 0, best = Infinity;
      for (const c of live) {
        if (c.cad == null || c.model.seconds < this.cfg.strideTrustS) continue;
        const stride = c.model.stride(c.cad, c.inten);
        if (stride == null) continue;
        const w = 1 / c.sd ** 2;
        wsum += w; vsum += w * c.cad / 60 * stride * this.scale; best = Math.min(best, c.sd);
        sources.push(c.key === 'phone' ? 'steps' : 'arm');
      }
      if (wsum > 0) this._update(vsum / wsum, best * best);
    }
    if (!sources.length && this.P > 4) this.x = 0;          // nothing for a long time: do not coast
    if (this.x < 0) this.x = 0;

    this.distanceM += this.x * dt;
    if (gpsV != null) this.distanceGpsM += gpsV * dt;
    if (sources.length) this.lastMeasT = t;
    const source = sources.length ? sources.join('+') : 'none';
    const key = sources.includes('still') ? 'still' : sources.includes('steps') ? 'steps'
              : sources.includes('arm') ? 'arm' : sources.some(x => x.startsWith('gps')) ? 'gps' : 'none';
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
      stride: this.strideModel.toJSON(), armStride: this.armModel.toJSON(),
      strideAt170: this.strideModel.stride(170) == null ? null
        : Math.round(this.strideModel.stride(170) * this.scale * 100) / 100,
      strideSeconds: this.strideModel.seconds, armStrideSeconds: this.armModel.seconds,
      motion: this.motionSeen, motionUnusable: !!this.motionUnusable,
      arm: !!this.armSeen, armUnusable: !!(this._unusable && this._unusable.arm),
      distanceM: Math.round(this.distanceM),
      distanceGpsM: Math.round(this.distanceGpsM),
      shares: Object.fromEntries(Object.entries(this.shares).map(([k, v]) => [k, Math.round(v)])),
    };
  }
}
