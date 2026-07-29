"""Signal conditioning for optical HR: artifact rejection, dropout detection, cadence lock-on.

Everything downstream -- zones, TRIMP, decoupling, the real-time controller -- is a function of
heart rate. An arm-worn PPG sensor during running produces three failure modes that all look like
plausible data if you do not test for them, and each one corrupts a *different* decision:

1. **Motion artifact / dropout.** Isolated implausible values and step changes. Cheap to reject.
2. **Cadence lock-on.** The PPG algorithm latches onto the step frequency instead of the pulse, and
   reports a rock-steady, physiologically plausible HR that happens to equal cadence (or half/double
   it). It looks *better* than real data -- lower variance -- so variance-based quality checks
   actively prefer it. The only reliable detector is comparing HR against cadence, which we have
   because the Verity streams its own accelerometer.
3. **Frozen heart rate.** Polar's own Verity Sense documentation states it plainly: *"If movement is
   detected, the heart rate is fixed to the last reliable value."* This is a distinct failure from
   lock-on and arguably worse, because the device deliberately outputs a **stale but perfectly
   plausible** number rather than admitting it has lost the signal. A frozen HR looks like an
   immaculate signal -- zero noise, physiologically sensible value, no dropout -- and every
   smoothness heuristic loves it. :func:`frozen_hr_suspicion` detects it by looking for a run of
   *identical* values over a period where a real heart rate could not plausibly have stayed
   bit-identical, and it requires evidence of movement before firing, since a genuinely resting HR
   can legitimately repeat.
4. **Warm-up / poor contact.** The first ~30 s after starting a stream, cold skin, or a loose
   strap. The Verity needs the band snug on the *upper* arm; forearm placement is materially worse.

**Skin contact is not usable on this device.** Polar documents that skin-contact detection is "very
unreliable" on the Verity Sense and that it "might be possible for the device to output a heart rate
that is not 0 even when the device is not worn" -- a limitation of this generation of optical sensor.
So the skin-contact bit is parsed and stored for diagnostics but is **never** used as a gate. Not-worn
is inferred instead from the conjunction of accelerometer stillness and a frozen HR
(:func:`not_worn_suspicion`), which is the only signal combination that actually distinguishes it.

Design stance: **reject, never interpolate silently.** A rejected sample is reported as rejected
and the consumer decides (hold last good value, widen its deadband, or refuse to make a decision).
Quietly filling gaps with plausible numbers is how a controller ends up confidently telling a
beginner to speed up during a genuine tachycardia.

Sources
-------
* Polar PMD PPI carries a per-interval ``error_ms`` and a **blocker** bit; Polar documents both,
  and the user's existing ``polar_pmd.py`` already parses them. Use them -- they are the device's
  own admission that a beat was unreliable.
* Artifact correction for HRV: Tarvainen et al. 2014 (Kubios) -- threshold-based correction against
  a local median; Lipponen & Tarvainen 2019, *J Med Eng Technol* 43:173. A few percent of corrected
  beats is tolerable for RMSSD; more than ~5% makes short-term HRV unreliable.
* Malik criterion (Malik et al. 1989): reject an interval differing >20% from the previous one.

Pure functions, stdlib only.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "PPI_MIN_MS", "PPI_MAX_MS", "MALIK_FRACTION", "MAX_ARTIFACT_FRACTION",
    "HR_MIN_BPM", "HR_MAX_BPM", "MAX_HR_SLEW_BPM_S", "DROPOUT_TIMEOUT_S",
    "CADENCE_LOCK_TOLERANCE", "CADENCE_LOCK_MIN_SAMPLES", "CADENCE_LOCK_MIN_CV", "PPG_WARMUP_S",
    "clean_intervals", "rmssd", "ln_rmssd", "HrSample", "HrGate", "cadence_lock_suspicion",
    "frozen_hr_suspicion", "not_worn_suspicion", "FROZEN_HR_WINDOW_S", "FROZEN_HR_MIN_SAMPLES",
    "FROZEN_HR_MOVEMENT_SPM", "NOT_WORN_STILLNESS_G",
]

# ---- plausibility windows ---------------------------------------------------------------

#: 240 bpm .. 24 bpm. Same window as the Eight Sleep controller's ``polar_pmd.py`` so both
#: systems reject identically and their HRV numbers stay comparable.
PPI_MIN_MS = 250
PPI_MAX_MS = 2500

#: Malik: an interval more than 20% different from its predecessor is an artifact, not a beat.
MALIK_FRACTION = 0.20

#: Above this fraction of rejected beats, a short-window HRV figure is not reportable.
MAX_ARTIFACT_FRACTION = 0.05

HR_MIN_BPM = 30.0
HR_MAX_BPM = 230.0

#: Physiological ceiling on how fast true HR can change, bpm per second. Real HR kinetics at
#: exercise onset are on the order of 1-2 bpm/s; 8 bpm/s is far above anything physiological and
#: still comfortably below the instantaneous jumps a PPG dropout produces, so it catches artifacts
#: without clipping a genuine hard interval start.
MAX_HR_SLEW_BPM_S = 8.0

#: No fresh sample for this long = treat HR as unavailable, not as "still the last value".
DROPOUT_TIMEOUT_S = 5.0

#: Cadence lock-on: HR within this fraction of cadence (or half/double it) is suspicious.
CADENCE_LOCK_TOLERANCE = 0.04
CADENCE_LOCK_MIN_SAMPLES = 20

#: Minimum coefficient of variation in cadence for a confident lock-on call. Below this, step rate is
#: effectively constant and a heart rate sitting near it is statistically indistinguishable from a
#: locked one -- so the detector reports suspicion without acting on it.
CADENCE_LOCK_MIN_CV = 0.003

#: Frozen-HR detection. A real heart rate wanders beat to beat even at steady effort, so an
#: *exactly* repeated value over this many seconds means the device is holding its last reliable
#: value rather than measuring. 12 s is comfortably longer than any plausible genuine plateau at 1 Hz
#: sampling while still catching the fault well inside a single interval rep.
FROZEN_HR_WINDOW_S = 12.0
FROZEN_HR_MIN_SAMPLES = 8

#: Movement threshold above which a frozen HR is definitely a fault rather than a resting plateau.
#: Cadence over 100 spm means running; that is the state Polar says triggers the freeze.
FROZEN_HR_MOVEMENT_SPM = 100.0

#: Not-worn inference: accelerometer essentially still AND a frozen HR. Neither alone is enough --
#: sitting still legitimately produces low motion, and a frozen HR alone happens during running.
NOT_WORN_STILLNESS_G = 0.02

#: PPG needs time to settle after a stream starts. Polar documents ~25 s before the first PPI
#: batch; we distrust HR for the first 30 s of a stream regardless.
PPG_WARMUP_S = 30.0


# ---- beat-interval cleaning -------------------------------------------------------------


def clean_intervals(intervals_ms: Sequence[float], *,
                    blockers: Optional[Sequence[bool]] = None,
                    error_ms: Optional[Sequence[float]] = None,
                    max_error_ms: float = 30.0) -> Tuple[List[float], Dict[str, int]]:
    """Filter a beat-interval series, returning ``(clean, counts)``.

    Applied in order:

    1. **Device verdict** -- drop anything Polar flagged with the blocker bit, or whose reported
       ``error_ms`` exceeds ``max_error_ms``. The device knows things we cannot infer.
    2. **Plausibility** -- drop outside :data:`PPI_MIN_MS`..:data:`PPI_MAX_MS`.
    3. **Malik** -- drop an interval differing more than :data:`MALIK_FRACTION` from the previous
       *accepted* interval. Comparing against the previous accepted value rather than the previous
       raw one matters: otherwise a single artifact drags its neighbour out with it.

    ``counts`` reports how many were dropped by each rule, so the caller can distinguish
    "a couple of noisy beats" from "the strap is loose".
    """
    counts = {"total": len(intervals_ms), "blocker": 0, "error": 0,
              "implausible": 0, "malik": 0, "kept": 0}
    clean: List[float] = []
    prev: Optional[float] = None
    for i, v in enumerate(intervals_ms):
        if blockers is not None and i < len(blockers) and blockers[i]:
            counts["blocker"] += 1
            continue
        if error_ms is not None and i < len(error_ms) and error_ms[i] > max_error_ms:
            counts["error"] += 1
            continue
        if not (PPI_MIN_MS <= v <= PPI_MAX_MS):
            counts["implausible"] += 1
            continue
        if prev is not None and abs(v - prev) > MALIK_FRACTION * prev:
            counts["malik"] += 1
            continue
        clean.append(float(v))
        prev = v
    counts["kept"] = len(clean)
    return clean, counts


def rmssd(intervals_ms: Sequence[float]) -> Optional[float]:
    """Root mean square of successive differences, in ms. ``None`` if under 2 intervals.

    Note this is computed over the *cleaned* series, which means successive differences may span
    a rejected beat. That is the standard compromise; it slightly *underestimates* RMSSD when
    rejections are frequent, which is the safe direction (it looks like less recovery, not more).
    """
    if len(intervals_ms) < 2:
        return None
    diffs = [intervals_ms[i + 1] - intervals_ms[i] for i in range(len(intervals_ms) - 1)]
    return math.sqrt(statistics.fmean(d * d for d in diffs))


def ln_rmssd(intervals_ms: Sequence[float]) -> Optional[float]:
    r = rmssd(intervals_ms)
    return math.log(r) if r and r > 0 else None


# ---- live HR gating ---------------------------------------------------------------------


@dataclass
class HrSample:
    t_s: float                       # monotonic seconds since stream start
    hr_bpm: float
    cadence_spm: Optional[float] = None   # steps per minute, from the Verity's own ACC
    #: Standard deviation of ACC magnitude over the last second, in g. Used only to infer not-worn;
    #: the device's own skin-contact bit is documented as unreliable and is never trusted.
    accel_sd_g: Optional[float] = None


@dataclass
class HrGate:
    """Stateful gate for a live HR stream. Feed every sample; read ``value`` and ``status``.

    ``status`` is one of:

    * ``ok``            -- trustworthy
    * ``warmup``        -- inside :data:`PPG_WARMUP_S`, value shown but not used for control
    * ``rejected``      -- this sample was implausible; ``value`` holds the last good one
    * ``dropout``       -- nothing fresh for :data:`DROPOUT_TIMEOUT_S`; there is no usable HR
    * ``cadence_lock``  -- HR is tracking step rate; the number is probably not a heart rate
    * ``frozen``        -- the device is holding its last reliable value (Polar's documented
                           behaviour when it detects movement); the number is stale, not wrong
    * ``not_worn``      -- still *and* frozen: the band is probably off your arm

    The controller must treat ``dropout``, ``cadence_lock``, ``frozen`` and ``not_worn`` as
    "HR is unavailable" and fall back to pace/RPE guidance rather than acting on the number.
    ``frozen`` is the most insidious of the four, because the value it reports is entirely plausible
    and perfectly smooth.
    """
    value: Optional[float] = None
    status: str = "dropout"
    last_good_t: Optional[float] = None
    rejected_run: int = 0
    _hist: List[HrSample] = field(default_factory=list, repr=False)

    def update(self, sample: HrSample) -> str:
        """Feed one sample, return the new status."""
        self._hist.append(sample)
        if len(self._hist) > 240:
            self._hist.pop(0)

        if not (HR_MIN_BPM <= sample.hr_bpm <= HR_MAX_BPM):
            self.rejected_run += 1
            self.status = "rejected"
            return self._expire(sample.t_s)

        # Slew-rate check against the last accepted value.
        if self.value is not None and self.last_good_t is not None:
            dt = max(1e-3, sample.t_s - self.last_good_t)
            if abs(sample.hr_bpm - self.value) / dt > MAX_HR_SLEW_BPM_S:
                self.rejected_run += 1
                self.status = "rejected"
                return self._expire(sample.t_s)

        self.value = sample.hr_bpm
        self.last_good_t = sample.t_s
        self.rejected_run = 0

        if sample.t_s < PPG_WARMUP_S:
            self.status = "warmup"
        elif not_worn_suspicion(self._hist) >= 0.7:
            self.status = "not_worn"
        elif frozen_hr_suspicion(self._hist) >= 0.8:
            self.status = "frozen"
        elif cadence_lock_suspicion(self._hist) >= 0.8:
            self.status = "cadence_lock"
        else:
            self.status = "ok"
        return self.status

    def tick(self, now_s: float) -> str:
        """Call on a timer even when no sample arrived, so dropout is detected promptly."""
        return self._expire(now_s)

    def _expire(self, now_s: float) -> str:
        if self.last_good_t is None or now_s - self.last_good_t > DROPOUT_TIMEOUT_S:
            self.status = "dropout"
            self.value = None
        return self.status

    @property
    def usable_for_control(self) -> bool:
        return self.status == "ok"


def cadence_lock_suspicion(history: Sequence[HrSample]) -> float:
    """Probability-ish score (0..1) that HR has locked onto cadence.

    Requires cadence: without it there is no reliable way to detect this, which is a strong
    argument for streaming the Verity's accelerometer and not just its HR.

    The test is a conjunction, because each condition alone has an innocent explanation:

    * HR sits within :data:`CADENCE_LOCK_TOLERANCE` of cadence, ``cadence/2``, or ``cadence*2``
      for most of the window -- **and**
    * the HR-to-cadence *difference* is unusually constant (a real HR wanders relative to a real
      cadence; a locked one does not).

    A runner whose true HR genuinely happens to equal their cadence -- entirely possible at
    around 160 -- will show the first condition but not the second, because their HR still drifts
    independently. That is why the ratio's standard deviation carries half the weight.
    """
    pts = [(s.hr_bpm, s.cadence_spm) for s in history
           if s.cadence_spm and s.cadence_spm > 100 and s.hr_bpm > 0]
    if len(pts) < CADENCE_LOCK_MIN_SAMPLES:
        return 0.0

    # Lock-on can only be *distinguished* from coincidence when cadence moves. If step rate is
    # essentially constant across the window, a heart rate that happens to sit near it produces
    # exactly the same statistics as a locked one, and there is no evidence either way. That is not a
    # hypothetical: a runner at a steady 168 spm with a heart rate around 165 hits this precisely, and
    # flagging it would discard a perfectly good signal at the top of a ramp test.
    #
    # So a near-constant cadence caps the score below the action threshold rather than firing. The
    # discriminating evidence is HR *following* cadence, and that requires cadence to lead.
    cadences = [c for _, c in pts]
    cad_mean = statistics.fmean(cadences)
    cad_cv = (statistics.pstdev(cadences) / cad_mean) if cad_mean > 0 else 0.0
    cadence_varies = cad_cv >= CADENCE_LOCK_MIN_CV

    near = 0
    ratios: List[float] = []
    for hr, cad in pts:
        ratios.append(hr / cad)
        for mult in (0.5, 1.0, 2.0):
            if abs(hr - cad * mult) <= CADENCE_LOCK_TOLERANCE * cad * mult:
                near += 1
                break
    frac_near = near / len(pts)
    ratio_sd = statistics.pstdev(ratios) if len(ratios) > 1 else 0.0
    # A locked ratio is essentially constant. 0.01 is tight; real HR/cadence ratio SD over a
    # minute of running is typically several times that even at steady effort.
    lock_tight = 1.0 if ratio_sd < 0.01 else max(0.0, 1.0 - (ratio_sd - 0.01) / 0.03)
    score = min(1.0, 0.5 * frac_near + 0.5 * lock_tight * frac_near)
    if not cadence_varies:
        # Report the suspicion but keep it below the gate's 0.8 action threshold: worth surfacing in a
        # diagnostic, not worth discarding the heart rate over.
        score = min(score, 0.5)
    return round(score, 3)


def frozen_hr_suspicion(history: Sequence[HrSample]) -> float:
    """Score (0..1) that the device has frozen HR at its last reliable value.

    Polar's Verity Sense documentation: *"If movement is detected, the heart rate is fixed to the
    last reliable value."* The device does not signal this -- it simply keeps emitting a stale number,
    which is why it has to be inferred.

    The detector looks for a trailing run of **bit-identical** heart-rate values spanning at least
    :data:`FROZEN_HR_WINDOW_S`. Identity, not low variance, is the key: a real heart rate at steady
    effort still varies by a beat or two from second to second, and a run of exactly equal values is
    a plateau no physiology produces.

    Movement gating matters in both directions. With cadence above
    :data:`FROZEN_HR_MOVEMENT_SPM` this is unambiguous -- running is exactly the condition Polar says
    triggers the freeze -- and the score goes to 1.0. Without movement evidence the same pattern is a
    weaker signal, because a genuinely resting heart rate really can repeat, so it is capped at 0.6:
    enough to distrust the value for control, not enough to claim a fault.
    """
    if len(history) < FROZEN_HR_MIN_SAMPLES:
        return 0.0
    last = history[-1].hr_bpm
    run: List[HrSample] = []
    for s in reversed(history):
        if s.hr_bpm != last:
            break
        run.append(s)
    if len(run) < FROZEN_HR_MIN_SAMPLES:
        return 0.0
    span = run[0].t_s - run[-1].t_s
    if span < FROZEN_HR_WINDOW_S:
        return 0.0

    cadences = [s.cadence_spm for s in run if s.cadence_spm is not None]
    moving = bool(cadences) and statistics.fmean(cadences) >= FROZEN_HR_MOVEMENT_SPM
    if moving:
        # Unambiguous. Running with a bit-identical heart rate for 12 seconds is precisely the
        # condition Polar documents, and no physiology produces it. Report full confidence
        # immediately rather than ramping: a ramp would leave the controller acting on stale data
        # for another 7 seconds while the score climbed, which is most of an interval rep.
        return 1.0
    # Without movement evidence a repeated value is weaker -- a genuinely resting heart rate really
    # can repeat -- so scale with how long it has held and cap below the gate's action threshold.
    return round(min(0.6, span / (FROZEN_HR_WINDOW_S * 2)), 3)


def not_worn_suspicion(history: Sequence[HrSample]) -> float:
    """Score (0..1) that the armband is not actually on an arm.

    This exists because the device's own skin-contact bit cannot be used. Polar documents that
    Verity Sense skin-contact detection is "very unreliable" and that the device "might output a heart
    rate that is not 0 even when not worn" -- so a plausible heart rate is not evidence of being worn,
    and the contact flag is not evidence of anything.

    The only combination that actually distinguishes not-worn from resting is **stillness plus a
    frozen value**: a band sitting on a desk produces near-zero accelerometer variance *and* a heart
    rate that never changes. A person sitting still produces the stillness but not the frozen value,
    because their heart rate keeps varying.

    Requires accelerometer data. Without it, this returns 0.0 rather than guessing -- which is the
    correct failure mode, since the consequence of a false positive is discarding a real run.
    """
    if len(history) < FROZEN_HR_MIN_SAMPLES:
        return 0.0
    sds = [s.accel_sd_g for s in history if s.accel_sd_g is not None]
    if not sds:
        return 0.0
    still = statistics.fmean(sds) < NOT_WORN_STILLNESS_G
    if not still:
        return 0.0
    frozen = frozen_hr_suspicion(history)
    # Frozen-while-still is the signature. Both conditions must hold.
    return round(min(1.0, frozen * 1.4), 3) if frozen > 0 else 0.0
