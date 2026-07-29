"""Signal conditioning for optical HR: artifact rejection, dropout detection, cadence lock-on.

Everything downstream -- zones, TRIMP, decoupling, the real-time controller -- is a function of
heart rate. An arm-worn PPG sensor during running produces three failure modes that all look like
plausible data if you do not test for them, and each one corrupts a *different* decision:

1. **Motion artifact / dropout.** Isolated implausible values and step changes. Cheap to reject.
2. **Cadence lock-on.** The single most dangerous failure: the PPG algorithm latches onto the
   step frequency instead of the pulse, and reports a rock-steady, physiologically plausible HR
   that happens to equal cadence (or half/double it). It looks *better* than real data -- lower
   variance -- so variance-based quality checks actively prefer it. The only reliable detector is
   comparing HR against cadence, which we have because the Verity streams its own accelerometer.
   Polar's own documentation and the optical-HR validation literature both flag this for
   wrist/arm sensors during running.
3. **Warm-up / poor contact.** The first ~30 s after starting a stream, cold skin, or a loose
   strap. The Verity needs the band snug on the *upper* arm; forearm placement is materially worse.

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
    "CADENCE_LOCK_TOLERANCE", "CADENCE_LOCK_MIN_SAMPLES", "PPG_WARMUP_S",
    "clean_intervals", "rmssd", "ln_rmssd", "HrSample", "HrGate", "cadence_lock_suspicion",
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


@dataclass
class HrGate:
    """Stateful gate for a live HR stream. Feed every sample; read ``value`` and ``status``.

    ``status`` is one of:

    * ``ok``            -- trustworthy
    * ``warmup``        -- inside :data:`PPG_WARMUP_S`, value shown but not used for control
    * ``rejected``      -- this sample was implausible; ``value`` holds the last good one
    * ``dropout``       -- nothing fresh for :data:`DROPOUT_TIMEOUT_S`; there is no usable HR
    * ``cadence_lock``  -- HR is tracking step rate; the number is probably not a heart rate

    The controller must treat ``dropout`` and ``cadence_lock`` as "HR is unavailable" and fall
    back to pace/RPE guidance rather than acting on the number.
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
    return round(min(1.0, 0.5 * frac_near + 0.5 * lock_tight * frac_near), 3)
