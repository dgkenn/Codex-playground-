// Third port of marathon_engine/audio.py, after the Swift one.
//
// It exists because the iPhone app needs a Mac to build and there isn't one, so the coaching would
// otherwise be unreachable on the only device that goes running with you. Safari has no Bluetooth,
// but it has GPS, Web Audio and speech — which is enough for the pace half of the job.
//
// This file is deliberately separate from the page that uses it, and deliberately free of any DOM
// reference, for one reason: it is checked against the same golden vectors as the Python original
// and the Swift port. Three implementations, one set of traces, verified by execution. A port that
// merely looks right is how the two channels drift apart, and the runner would never know which one
// was lying.
//
// Every constant and every branch below has its justification in the Python module's docstring and
// is not repeated. Where behaviour looks arbitrary it is usually a defect fix; see audio.py.

export const Earcon = {
  EASE: 'ease',
  LIFT: 'lift',
  IN_BAND: 'in_band',
  ATTEND: 'attend',
  DEGRADED: 'degraded',
};

export const Tuning = {
  toneMinGapS: 15,
  overlapFloorS: 2,
  marginalMultiple: 1.2,
  marginalGapS: 60,
  mildGapS: 30,
  largeGapS: 15,
  mildMultiple: 1.5,
  returnFraction: 0.6,
  acquireGraceS: 180,
  maxUnacquiredNudges: 2,
  // Each unheeded reminder doubles the wait, to this multiple of the base. See audio.py.
  reminderBackoffMax: 8,
  smoothingS: 20,
  minSamples: 8,
};

// Minetti's metabolic cost polynomial, via the same grade-adjustment the rest of the engine uses.
// Present here so a hill moves the band rather than earning a stream of "lift" tones.
function minettiCost(i) {
  return 155.4 * i ** 5 - 30.4 * i ** 4 - 43.3 * i ** 3 + 46.3 * i * i + 19.5 * i + 3.6;
}
export function gradeAdjustedPaceFactor(grade) {
  return minettiCost(grade) / minettiCost(0);
}

export class PaceBandMonitor {
  constructor({ targetPaceSecKm, tolerance = 0.06, ceilingOnly = false, enabled = true }) {
    this.targetPaceSecKm = targetPaceSecKm;
    this.tolerance = tolerance;
    this.ceilingOnly = ceilingOnly;
    this.enabled = enabled;

    this.state = 'unknown';       // unknown | in | fast | slow
    this.acquired = false;
    this.window = [];
    this.lastToneT = null;
    this.pendingAck = false;
    this.slowSince = null;
    this.unacquiredNudges = 0;
    this.consecutiveReminders = 0;
  }

  /** Feed one second. Returns an event `{earcon, tS, error, reason}` or null. */
  update(tS, paceSecKm, { grade = 0, paceTrusted = true, running = true } = {}) {
    if (!this.enabled || this.targetPaceSecKm == null || !running) {
      this.window = [];
      return null;
    }
    if (!paceTrusted || paceSecKm == null || paceSecKm <= 0) {
      this.window = [];
      if (this.state !== 'unknown') {
        this.state = 'unknown';
        return this._emit(Earcon.DEGRADED, tS, 0, 'pace untrusted');
      }
      return null;
    }

    this.window.push([tS, paceSecKm]);
    this.window = this.window.filter(([t]) => t >= tS - Tuning.smoothingS);
    if (this.window.length < Tuning.minSamples) return null;

    const mean = this.window.reduce((a, [, p]) => a + p, 0) / this.window.length;
    const adjusted = this.targetPaceSecKm * gradeAdjustedPaceFactor(grade);
    return this._decide(tS, (mean - adjusted) / adjusted);
  }

  _decide(tS, error) {
    const magnitude = Math.abs(error);
    const out = this.state === 'fast' || this.state === 'slow';
    const threshold = out ? this.tolerance * Tuning.returnFraction : this.tolerance;

    if (magnitude <= threshold) {
      const wasOut = out;
      this.state = 'in';
      this.acquired = true;
      this.slowSince = null;
      this.consecutiveReminders = 0;
      if (wasOut && this.pendingAck) {
        this.pendingAck = false;
        return this._emit(Earcon.IN_BAND, tS, error, 'back in the band');
      }
      this.pendingAck = false;
      return null;
    }

    const side = error > 0 ? 'slow' : 'fast';

    if (side === 'slow' && this.ceilingOnly) {
      this.state = 'in';
      this.slowSince = null;
      return null;
    }

    const changedSide = side !== this.state;
    this.state = side;

    if (side === 'slow') {
      if (this.slowSince == null) this.slowSince = tS;
      if (!this.acquired) {
        if (tS - this.slowSince < Tuning.acquireGraceS) return null;
        if (this.unacquiredNudges >= Tuning.maxUnacquiredNudges) return null;
      }
    } else {
      this.slowSince = null;
    }

    if (changedSide) {
      this.consecutiveReminders = 0;
      return this._emit(this._tone(side), tS, error, 'crossed to the other side');
    }
    if (this.lastToneT == null) {
      return this._emit(this._tone(side), tS, error, 'left the band');
    }

    let gap;
    if (magnitude > this.tolerance * Tuning.mildMultiple) gap = Tuning.largeGapS;
    else if (magnitude > this.tolerance * Tuning.marginalMultiple) gap = Tuning.mildGapS;
    else gap = Tuning.marginalGapS;

    const backoff = Math.min(Tuning.reminderBackoffMax,
                             2 ** Math.max(0, this.consecutiveReminders - 1));
    if (tS - this.lastToneT >= gap * backoff) {
      return this._emit(this._tone(side), tS, error, 'still out of the band');
    }
    return null;
  }

  _tone(side) { return side === 'fast' ? Earcon.EASE : Earcon.LIFT; }

  _emit(earcon, tS, error, reason) {
    const floor = (earcon === Earcon.IN_BAND || earcon === Earcon.DEGRADED)
      ? Tuning.overlapFloorS : Tuning.toneMinGapS;
    if (this.lastToneT != null && tS - this.lastToneT < floor) return null;
    this.lastToneT = tS;
    if (earcon === Earcon.EASE || earcon === Earcon.LIFT) {
      this.pendingAck = true;
      this.consecutiveReminders += 1;
      if (earcon === Earcon.LIFT && !this.acquired) this.unacquiredNudges += 1;
    }
    return { earcon, tS, error: Math.round(error * 1e6) / 1e6, reason };
  }

  band(grade = 0) {
    if (this.targetPaceSecKm == null) return null;
    const t = this.targetPaceSecKm * gradeAdjustedPaceFactor(grade);
    return [t * (1 - this.tolerance), t * (1 + this.tolerance)];
  }
}

/**
 * The short spoken line that makes silence readable as "on pace" rather than "app has died".
 *
 * The formatter and the split name are injected rather than built in, because whether a split is
 * "3K" or "3 miles" is the athlete's business and not this module's — and because the alternative
 * was a second, unit-aware copy of this class living in the page, which is exactly the kind of
 * duplicate that drifts.
 */
export class SplitAnnouncer {
  constructor({ everyM = 1000, everyS = null,
                formatPace = formatMMSS,
                nameSplit = n => `${n}K` } = {}) {
    this.everyM = everyM;
    this.everyS = everyS;
    this.formatPace = formatPace;
    this.nameSplit = nameSplit;
    this.lastSplitM = 0;
    this.lastSplitT = 0;
    this.lastSplitAt = 0;
    this.n = 0;
  }

  update(tS, distanceM, paceSecKm, state) {
    let due = false;
    // What gets spoken. For a distance split it is the split's own average; see below.
    let reported = paceSecKm;

    if (this.everyM && distanceM - this.lastSplitM >= this.everyM) {
      this.lastSplitM += this.everyM;
      this.n += 1;
      // A split is how long that mile took — not the pace at the instant the odometer turned over.
      //
      // It was the instantaneous pace, which is a different number wearing the same name. Every
      // watch, every race clock and every runner means the average when they say "mile three", and
      // the instantaneous value is far noisier: a momentary surge or a GPS wobble at the wrong
      // second becomes the mile you remember running. This is also the only number of the run the
      // athlete hears rather than sees, so it is the one that has to mean what it says.
      //
      // Gated on there being a live pace at all: a null `paceSecKm` is the caller saying the pace
      // channel is degraded, and a distance accumulated while it was degraded is not a distance
      // worth dividing by. Better to say "no pace signal" and leave the number out.
      const dt = tS - this.lastSplitAt;
      if (paceSecKm != null && dt > 0) reported = dt / (this.everyM / 1000);
      this.lastSplitAt = tS;
      due = true;
    }
    if (this.everyS && tS - this.lastSplitT >= this.everyS) {
      this.lastSplitT = tS;
      due = true;
    }
    if (!due) return null;

    const parts = [];
    if (this.everyM) parts.push(this.nameSplit(this.n));
    if (reported) parts.push(this.formatPace(reported));
    parts.push({ in: 'on pace', fast: 'easing', slow: 'lift',
                 unknown: 'no pace signal' }[state] || '');
    return parts.filter(Boolean).join('. ') + '.';
  }
}

/** Seconds to `m:ss`. Unit-agnostic: the caller decides what the seconds are per. */
export function formatMMSS(sec) {
  if (!sec || !isFinite(sec)) return '—:——';
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return s === 60 ? `${m + 1}:00` : `${m}:${String(s).padStart(2, '0')}`;
}
