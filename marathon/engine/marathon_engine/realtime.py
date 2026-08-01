"""The in-run controller: decide, second by second, what to say and whether to change the session.

This is the module that makes the app worth building rather than just another run tracker. It is
also the one where naive implementations fail in predictable ways, so the design starts from those
failure modes.

Why not a PID loop on heart rate
--------------------------------
The obvious design -- "HR above target, say slow down; HR below target, say speed up" -- oscillates
badly, and the reason is physiological, not tuning. Heart rate responds to a step change in speed
as roughly a **first-order system with dead time**: a delay of a few seconds, then an exponential
approach to a new steady state with a time constant of ~30-60 s at moderate intensity (slower at
higher intensity and in the untrained). So the HR you can see is the HR of the speed you were
running half a minute ago. A controller that reacts to it directly chases its own tail: the runner
slows, HR keeps rising for 20 s, the controller says slow down again, the runner ends up walking,
then HR falls below target and it says speed up, and the cycle repeats.

Three mechanisms fix this here:

1. **Lead compensation instead of raw HR.** We estimate the *steady-state* HR the current effort is
   heading toward, ``HR_ss ~= HR + TAU_HR * dHR/dt``, and control on that. This is the standard
   first-order inverse and it is what lets the controller act on where HR is going rather than
   where it is (:func:`predict_steady_state_hr`).
2. **A feedforward gain taken from the athlete's own ramp test.** The assessment measured the slope
   of steady HR against speed in bpm per km/h. So the correction for an HR error is not a guessed
   gain -- it is ``delta_speed = delta_HR / slope``, this runner's own physiology
   (:func:`speed_correction`). This is the single biggest advantage of having run the ramp test.
3. **Deadband, confirmation time, and cue rate limiting.** No cue until the error is outside a
   deadband *and* has stayed there for :data:`CONFIRM_S`, and never more than one pace cue per
   :data:`PACE_CUE_MIN_GAP_S`. Anti-windup: the integral term does not accumulate while HR is still
   slewing toward its steady state.

The other failure modes, and what handles them
----------------------------------------------
* **Cardiac drift misread as running too hard.** On a long run in the heat, HR rises at constant
  pace. Telling the runner to slow repeatedly is wrong -- the correct response is one explanation
  and a *widened* target band, not a nag. :func:`classify_hr_rise` separates a slow drift at steady
  pace from a genuine step change in effort by looking at the pace record alongside the HR slope.
* **Optical HR failure.** Dropout, motion artifact, and cadence lock-on are handled upstream in
  :mod:`marathon_engine.signal_quality`; this module treats "HR unavailable" as a first-class state
  (:data:`ControlMode.PACE_ONLY`) rather than acting on a bad number. That distinction matters most
  precisely when it is most tempting to ignore.
* **Hills.** A grade-adjusted target, via Minetti, so the controller does not demand flat pace up a
  hill or flag an easy descent as slacking.
* **Audio nagging.** A priority queue with per-priority rate limits, and hard rules about what may
  never be interrupted (:class:`CueScheduler`).

Safety
------
:func:`safety_check` runs before anything else on every tick and can abort the session outright.
The criteria are deliberately conservative and include the symptoms that matter clinically, not
just heart-rate numbers. **This is advisory software, not a medical device.** It cannot detect a
cardiac event, and its abort criteria exist to prompt a sensible human decision, not to replace one.

Pure functions and small state machines; no I/O, no audio, no BLE. The iOS layer supplies samples
and renders the returned cues, which is what makes all of this testable.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from marathon_engine.physiology import (
    Zone, ZoneModel, grade_adjusted_pace_factor, reserve_fraction_at_hr, speed_to_pace, fmt_pace,
)

__all__ = [
    "TAU_HR", "DEAD_TIME_S", "CONFIRM_S", "HR_DEADBAND_BPM", "PACE_CUE_MIN_GAP_S",
    "DRIFT_MAX_BPM_PER_MIN", "STEP_MIN_BPM_PER_MIN", "PACE_STEADY_CV",
    "ABORT_HR_FRACTION", "ABORT_HR_SUSTAIN_S", "PAIN_STOP", "PAIN_WARN",
    "REP_FADE_ABORT_PCT", "RECOVERY_HR_FRACTION", "RECOVERY_FAILURES_TO_CUT",
    "DECOUPLE_CONVERT",
    "CueLevel", "Cue", "CueScheduler", "ControlMode", "RunState", "SessionIntent",
    "RunTick", "ControlDecision", "predict_steady_state_hr", "speed_correction",
    "classify_hr_rise", "safety_check", "InRunController",
]

# ---- physiological time constants --------------------------------------------------------

#: First-order time constant of the HR response to a step change in running speed, in seconds.
#: Reported values for moderate-intensity exercise cluster around 30-45 s in trained subjects and
#: are longer in the untrained and at higher intensities. 45 s is chosen as a deliberately
#: conservative middle: over-estimating tau makes the controller *more* patient, which is the safe
#: direction for a beginner.
TAU_HR = 45.0

#: Transport/dead time before HR responds at all.
DEAD_TIME_S = 5.0

#: How long an error must persist outside the deadband before any cue fires.
CONFIRM_S = 20.0

#: Deadband around the target zone edges. Wider than sensor noise and wider than the beat-to-beat
#: variability of a steady effort, so a runner sitting legitimately near a zone edge is not nagged.
HR_DEADBAND_BPM = 4.0

#: Minimum gap between successive pace cues. A runner cued more often than this stops listening,
#: which is worse than not cueing at all.
PACE_CUE_MIN_GAP_S = 75.0

#: Cardiac drift is slow. Above :data:`STEP_MIN_BPM_PER_MIN` the rise is an effort change, below
#: :data:`DRIFT_MAX_BPM_PER_MIN` at steady pace it is drift; between them is ambiguous.
DRIFT_MAX_BPM_PER_MIN = 1.5
STEP_MIN_BPM_PER_MIN = 6.0

#: Coefficient of variation of pace below which pace counts as "steady" for drift detection.
PACE_STEADY_CV = 0.06

# ---- safety ------------------------------------------------------------------------------

#: Fraction of HRmax which, if sustained, aborts the session. 0.95 is above any zone this plan
#: prescribes, so reaching it means either a genuine maximal effort in a session that did not call
#: for one, or a problem.
ABORT_HR_FRACTION = 0.95
ABORT_HR_SUSTAIN_S = 45.0

#: Pain-monitoring model, as used in tendon rehab (Silbernagel-style): 0-2 acceptable,
#: 3-5 a warning that caps load, above 5 stop. Applied to running, where the same logic holds and
#: the alternative -- "run through it" -- is how a niggle becomes a season.
PAIN_WARN = 3
PAIN_STOP = 5

#: Interval-set abort: if a rep is this fraction slower than the first rep, the set is over.
#: Continuing past this point accumulates fatigue without the intended stimulus.
REP_FADE_ABORT_PCT = 0.08

#: Recovery between reps must bring HR below this fraction of reserve.
#:
#: Kept at 0.75 rather than the 0.60 a later review proposed. The argument for lowering it was that
#: 0.75 rarely fires and is therefore not a real gate; the argument against is stronger. A beginner on
#: a two-to-three minute jog recovery frequently will not drop to 60% of reserve even when everything
#: is fine, so a 0.60 gate would cut sets on physiology that is behaving normally -- and wrongly
#: aborting a workout has a real cost. The gate is made meaningful instead by
#: :data:`RECOVERY_FAILURES_TO_CUT`, which is the correct fix for "it never fires": require the signal
#: to repeat rather than making a single reading easier to trip.
RECOVERY_HR_FRACTION = 0.75

#: Consecutive poor recoveries required before the set is cut. One high reading is noise; two in a row
#: is a pattern.
RECOVERY_FAILURES_TO_CUT = 2

#: Mid-run decoupling above this converts the remainder of a long run to easy/walk.
DECOUPLE_CONVERT = 0.10


class CueLevel(int, Enum):
    """Audio priority. Higher pre-empts lower; equal levels queue."""
    SAFETY = 4          # stop now
    SESSION = 3         # the workout itself has changed
    PACE = 2            # speed up / slow down
    INFO = 1            # split, distance, encouragement


@dataclass(frozen=True)
class Cue:
    level: CueLevel
    text: str
    key: str            # dedupe key: the same key will not repeat inside its cooldown
    cooldown_s: float = 0.0

    def to_dict(self) -> dict:
        return {"level": int(self.level), "text": self.text, "key": self.key}


#: Per-level minimum gaps, in seconds. Safety is never rate limited.
_LEVEL_MIN_GAP: Dict[CueLevel, float] = {
    CueLevel.SAFETY: 0.0,
    CueLevel.SESSION: 20.0,
    CueLevel.PACE: PACE_CUE_MIN_GAP_S,
    CueLevel.INFO: 120.0,
}


@dataclass
class CueScheduler:
    """Rate-limited priority queue for spoken cues.

    Rules, in order:

    1. A :attr:`CueLevel.SAFETY` cue always fires immediately and clears anything queued below it.
    2. A cue whose ``key`` fired within its ``cooldown_s`` is dropped, not queued -- repeating
       "slow down" every 30 s is how a runner learns to ignore the app.
    3. Lower-priority cues are suppressed while a higher-priority one is within its own gap, so a
       session change is never talked over by a split announcement.
    4. Nothing below :attr:`CueLevel.SESSION` fires inside :data:`_PROTECTED_WINDOW_S` of an
       interval rep starting or ending. Those moments already carry their own cue and adding to
       them turns guidance into noise.
    """
    last_fired: Dict[CueLevel, float] = field(default_factory=dict)
    last_key: Dict[str, float] = field(default_factory=dict)
    protected_until: float = -1.0

    def protect(self, now_s: float, seconds: float = 8.0) -> None:
        """Mark a window in which only SAFETY and SESSION cues may speak."""
        self.protected_until = now_s + seconds

    def submit(self, cues: Sequence[Cue], now_s: float) -> Optional[Cue]:
        """Return the one cue that should be spoken now, or ``None``."""
        if not cues:
            return None
        ordered = sorted(cues, key=lambda c: -int(c.level))
        for cue in ordered:
            if cue.level == CueLevel.SAFETY:
                self.last_fired[cue.level] = now_s
                self.last_key[cue.key] = now_s
                return cue
            if now_s < self.protected_until and cue.level < CueLevel.SESSION:
                continue
            prev_key = self.last_key.get(cue.key)
            if prev_key is not None and now_s - prev_key < cue.cooldown_s:
                continue
            prev_level = self.last_fired.get(cue.level)
            if prev_level is not None and now_s - prev_level < _LEVEL_MIN_GAP[cue.level]:
                continue
            # Do not talk under a higher-priority cue that just fired.
            blocked = False
            for lvl in (l for l in CueLevel if l > cue.level):
                t = self.last_fired.get(lvl)
                if t is not None and now_s - t < _LEVEL_MIN_GAP[lvl]:
                    blocked = True
                    break
            if blocked:
                continue
            self.last_fired[cue.level] = now_s
            self.last_key[cue.key] = now_s
            return cue
        return None


class ControlMode(str, Enum):
    HR_AND_PACE = "hr_and_pace"     # both signals trustworthy
    PACE_ONLY = "pace_only"         # HR dropped out or locked to cadence
    HR_ONLY = "hr_only"             # no GPS (treadmill, tunnel, urban canyon)
    EFFORT_ONLY = "effort_only"     # neither -- fall back to RPE and time


class RunState(str, Enum):
    WARMUP = "warmup"
    STEADY = "steady"
    REP = "rep"
    RECOVERY = "recovery"
    COOLDOWN = "cooldown"
    WALK_BREAK = "walk_break"
    PAUSED = "paused"
    ABORTED = "aborted"
    DONE = "done"


@dataclass
class SessionIntent:
    """What this session is *for*, which determines how deviations should be treated."""
    kind: str                                   # easy | long | threshold | intervals | run_walk ...
    target_zones: Tuple[int, ...] = (1, 2)
    target_pace_sec_km: Optional[float] = None
    pace_tolerance: float = 0.06                # +/- fraction for pace-based control
    planned_duration_min: Optional[float] = None
    reps: Optional[int] = None
    rep_duration_s: Optional[float] = None
    rep_distance_m: Optional[float] = None
    recovery_s: Optional[float] = None
    #: Easy and long runs are *ceiling*-controlled: too slow is fine, too fast is not.
    ceiling_only: bool = False

    def __post_init__(self) -> None:
        if self.kind in ("easy", "long", "run_walk", "recovery"):
            self.ceiling_only = True


@dataclass
class RunTick:
    """One sample of the run, as the iOS layer supplies it."""
    t_s: float
    hr_bpm: Optional[float]
    hr_status: str = "ok"                        # from signal_quality.HrGate
    speed_m_s: Optional[float] = None
    grade: float = 0.0
    cadence_spm: Optional[float] = None
    distance_m: float = 0.0
    pain_0_10: Optional[int] = None
    rpe_6_20: Optional[int] = None
    #: Set by the app when the user taps a red flag button, or reports a symptom.
    symptom: Optional[str] = None               # chest_pain | dizzy | calf_swelling | focal_bone_pain


@dataclass
class ControlDecision:
    mode: ControlMode
    state: RunState
    in_target: Optional[bool]
    hr_ss_estimate: Optional[float]
    target_band: Optional[Tuple[float, float]]
    speed_correction_m_s: Optional[float]
    cue: Optional[Cue]
    session_change: Optional[str] = None
    abort: bool = False
    reason: str = ""
    diagnostics: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"mode": self.mode.value, "state": self.state.value, "in_target": self.in_target,
                "hr_ss": round(self.hr_ss_estimate, 1) if self.hr_ss_estimate else None,
                "target_band": ([round(self.target_band[0], 1), round(self.target_band[1], 1)]
                                if self.target_band else None),
                "speed_correction_m_s": (round(self.speed_correction_m_s, 3)
                                         if self.speed_correction_m_s is not None else None),
                "cue": self.cue.to_dict() if self.cue else None,
                "session_change": self.session_change, "abort": self.abort,
                "reason": self.reason, "diagnostics": self.diagnostics}


# ----------------------------------------------------------------------------------------
# Core estimators
# ----------------------------------------------------------------------------------------


def predict_steady_state_hr(hr_now: float, hr_slope_bpm_per_s: float,
                            tau_s: float = TAU_HR) -> float:
    """Where HR is heading, given how fast it is currently moving.

    For a first-order system ``tau * dHR/dt = HR_ss - HR``, so ``HR_ss = HR + tau * dHR/dt``.
    Controlling on this instead of on ``hr_now`` is what removes the oscillation: it is the
    difference between steering by where the car is pointed and by where it currently sits.

    The slope must be computed over a window long enough to be a trend rather than beat-to-beat
    noise -- see :meth:`InRunController._hr_slope`, which uses a 30 s regression.
    """
    return hr_now + tau_s * hr_slope_bpm_per_s


def speed_correction(hr_error_bpm: float, hr_speed_slope_bpm_per_kmh: float) -> float:
    """Speed change (m/s) that should remove an HR error, from the athlete's own ramp slope.

    ``hr_error_bpm`` is positive when HR is too high (so the returned correction is negative --
    slow down). Guards against an implausibly shallow slope, which would ask for an enormous
    speed change from a small HR error.
    """
    slope = max(3.0, hr_speed_slope_bpm_per_kmh)      # bpm per km/h; below 3 the fit is unusable
    delta_kmh = -hr_error_bpm / slope
    return delta_kmh / 3.6


def classify_hr_rise(hr_series: Sequence[Tuple[float, float]],
                     speed_series: Sequence[Tuple[float, float]]) -> Tuple[str, Dict[str, float]]:
    """Classify a rising HR as ``"drift"``, ``"effort_increase"``, ``"ambiguous"`` or ``"stable"``.

    The discriminator is pace. Cardiac drift is a slow rise *at constant pace*, driven by
    dehydration, hyperthermia and falling stroke volume. An effort increase is a faster rise
    accompanied by a pace change. Getting this wrong in the "drift" direction produces a controller
    that repeatedly tells someone to slow down on a hot long run when the honest message is
    "this is normal, here is a wider band".

    ``hr_series`` and ``speed_series`` are ``(t_s, value)`` over the analysis window
    (5 minutes works well).
    """
    if len(hr_series) < 6:
        return "stable", {}
    ts = [t for t, _ in hr_series]
    hrs = [v for _, v in hr_series]
    span_min = (ts[-1] - ts[0]) / 60.0
    if span_min <= 0:
        return "stable", {}
    mt, mh = statistics.fmean(ts), statistics.fmean(hrs)
    sxx = sum((t - mt) ** 2 for t in ts)
    slope_bpm_s = (sum((t - mt) * (h - mh) for t, h in hr_series) / sxx) if sxx else 0.0
    slope_bpm_min = slope_bpm_s * 60.0

    speeds = [v for _, v in speed_series if v and v > 0]
    cv = (statistics.pstdev(speeds) / statistics.fmean(speeds)) if len(speeds) > 2 else 1.0
    pace_steady = cv <= PACE_STEADY_CV

    diag = {"slope_bpm_min": round(slope_bpm_min, 2), "pace_cv": round(cv, 3),
            "window_min": round(span_min, 1)}

    if slope_bpm_min < DRIFT_MAX_BPM_PER_MIN * 0.3:
        return "stable", diag
    if pace_steady and slope_bpm_min <= DRIFT_MAX_BPM_PER_MIN:
        return "drift", diag
    if slope_bpm_min >= STEP_MIN_BPM_PER_MIN or not pace_steady:
        return "effort_increase", diag
    return "ambiguous", diag


def safety_check(tick: RunTick, hr_max: float, sustained_high_s: float) -> Optional[Cue]:
    """Hard safety criteria, checked before any control logic. Returns a SAFETY cue or ``None``.

    The symptom list is the part that matters: a heart-rate threshold cannot detect the things that
    actually require stopping. These are the classic exertional red flags -- chest pain or pressure,
    pre-syncope, focal bone pain (a stress fracture presents as a *point* of pain that worsens with
    loading, not diffuse ache), and unilateral calf swelling or pain at rest.

    Explicitly not a diagnosis and explicitly not a substitute for medical assessment. The app's
    job is to stop the run and say so plainly.
    """
    if tick.symptom:
        messages = {
            "chest_pain": ("Stop now. Chest pain or pressure during exercise needs to be assessed "
                           "today, not after the run. Walk, do not push on, and seek medical "
                           "attention."),
            "dizzy": ("Stop and sit down. Light-headedness or feeling faint during a run means stop "
                      "and rehydrate; if it does not resolve quickly, get assessed."),
            "focal_bone_pain": ("Stop running and walk home. A specific point of bone pain that "
                                "worsens with each step is how a stress fracture presents. Do not "
                                "run again until it has been assessed -- running through this is "
                                "how a 6-week problem becomes a 6-month one."),
            "calf_swelling": ("Stop. A swollen, painful calf that hurts at rest needs to be ruled "
                              "out as a clot before you run again. Get it assessed."),
        }
        return Cue(CueLevel.SAFETY, messages.get(tick.symptom,
                   "Stop the run and get this checked."), key=f"symptom_{tick.symptom}")

    if tick.pain_0_10 is not None and tick.pain_0_10 > PAIN_STOP:
        return Cue(CueLevel.SAFETY,
                   f"Pain {tick.pain_0_10} out of 10 -- stop running and walk. Above "
                   f"{PAIN_STOP}/10 the rule is stop, every time. Nothing in this plan is worth "
                   "the next three weeks.", key="pain_stop")

    if tick.hr_bpm and tick.hr_status == "ok":
        if tick.hr_bpm >= ABORT_HR_FRACTION * hr_max and sustained_high_s >= ABORT_HR_SUSTAIN_S:
            return Cue(CueLevel.SAFETY,
                       f"Heart rate has been above {ABORT_HR_FRACTION*100:.0f}% of your maximum "
                       f"for {sustained_high_s:.0f} seconds. Ease to a walk. No session in this "
                       "plan requires that.", key="hr_abort")
    return None


# ----------------------------------------------------------------------------------------
# The controller
# ----------------------------------------------------------------------------------------


@dataclass
class InRunController:
    """Stateful in-run controller. Feed :class:`RunTick` to :meth:`update` once per second.

    Deliberately small state: an HR history for slope estimation, a speed history for drift
    discrimination, an error timer for the confirmation window, and the cue scheduler. Everything
    else is derived, so the whole thing is trivially testable and portable to Swift.
    """
    zones: ZoneModel
    intent: SessionIntent
    hr_speed_slope: float = 12.0          # bpm per km/h, from the ramp fit
    state: RunState = RunState.WARMUP
    scheduler: CueScheduler = field(default_factory=CueScheduler)

    _hr_hist: List[Tuple[float, float]] = field(default_factory=list, repr=False)
    _sp_hist: List[Tuple[float, float]] = field(default_factory=list, repr=False)
    _error_since: Optional[float] = None
    _error_sign: int = 0
    _high_hr_since: Optional[float] = None
    _drift_announced: bool = False
    _band_widened_bpm: float = 0.0
    _rep_paces: List[float] = field(default_factory=list, repr=False)
    _recovery_failures: int = 0
    _aborted: bool = False
    #: How many times each sensor-degradation cue has actually been spoken this run. Capped at two.
    _degraded_said: Dict[str, int] = field(default_factory=dict, repr=False)

    # ---- helpers ----------------------------------------------------------------------

    def _target_band(self, grade: float = 0.0) -> Tuple[float, float]:
        """HR band for the session's target zones, plus any drift widening."""
        zs = [z for z in self.zones.zones if z.index in self.intent.target_zones]
        if not zs:
            zs = [self.zones.zones[1]]
        lo = min(z.low_bpm for z in zs)
        hi = max(z.high_bpm for z in zs)
        return float(lo), float(hi) + self._band_widened_bpm

    def _hr_slope(self, window_s: float = 30.0) -> float:
        """Least-squares HR slope in bpm/s over the trailing window."""
        if len(self._hr_hist) < 4:
            return 0.0
        t_end = self._hr_hist[-1][0]
        pts = [(t, v) for t, v in self._hr_hist if t >= t_end - window_s]
        if len(pts) < 4:
            return 0.0
        mt = statistics.fmean([t for t, _ in pts])
        mv = statistics.fmean([v for _, v in pts])
        sxx = sum((t - mt) ** 2 for t, _ in pts)
        if sxx == 0:
            return 0.0
        return sum((t - mt) * (v - mv) for t, v in pts) / sxx

    def _mode(self, tick: RunTick) -> ControlMode:
        hr_ok = tick.hr_bpm is not None and tick.hr_status == "ok"
        pace_ok = tick.speed_m_s is not None and tick.speed_m_s > 0.3
        if hr_ok and pace_ok:
            return ControlMode.HR_AND_PACE
        if pace_ok:
            return ControlMode.PACE_ONLY
        if hr_ok:
            return ControlMode.HR_ONLY
        return ControlMode.EFFORT_ONLY

    # ---- main tick --------------------------------------------------------------------

    def update(self, tick: RunTick) -> ControlDecision:
        """Advance the controller by one sample and return what to do."""
        if self._aborted:
            return ControlDecision(mode=self._mode(tick), state=RunState.ABORTED, in_target=None,
                                   hr_ss_estimate=None, target_band=None,
                                   speed_correction_m_s=None, cue=None,
                                   abort=True, reason="already aborted")

        if tick.hr_bpm is not None and tick.hr_status == "ok":
            self._hr_hist.append((tick.t_s, tick.hr_bpm))
            if len(self._hr_hist) > 600:
                self._hr_hist.pop(0)
        if tick.speed_m_s:
            self._sp_hist.append((tick.t_s, tick.speed_m_s))
            if len(self._sp_hist) > 600:
                self._sp_hist.pop(0)

        # ---- 1. safety, always first ----
        hr_max = self.zones.hr_max
        if tick.hr_bpm and tick.hr_bpm >= ABORT_HR_FRACTION * hr_max:
            self._high_hr_since = self._high_hr_since or tick.t_s
        else:
            self._high_hr_since = None
        sustained = (tick.t_s - self._high_hr_since) if self._high_hr_since else 0.0

        safety = safety_check(tick, hr_max, sustained)
        if safety:
            self._aborted = True
            self.state = RunState.ABORTED
            return ControlDecision(self._mode(tick), RunState.ABORTED, False, tick.hr_bpm,
                                   self._target_band(), None,
                                   self.scheduler.submit([safety], tick.t_s),
                                   session_change="abort", abort=True, reason=safety.key)

        cues: List[Cue] = []
        mode = self._mode(tick)

        # ---- 2. pain in the warning band caps the session but does not stop it ----
        if tick.pain_0_10 is not None and PAIN_WARN <= tick.pain_0_10 <= PAIN_STOP:
            cues.append(Cue(CueLevel.SESSION,
                            f"Pain {tick.pain_0_10} out of 10. Finish this as an easy run -- no "
                            "faster running today, and if it is still there next run we hold "
                            "volume rather than adding.", key="pain_warn", cooldown_s=600.0))

        # ---- 3. sensor degradation ----
        #
        # Capped at two mentions per fault per run. The cooldown alone would repeat a persistent
        # fault every five minutes for the length of the run -- eight times on a long run. The
        # message is actionable exactly twice: once to tell you, once in case you missed it. After
        # that it is nagging about something you have already decided not to fix, and a coach you
        # mute cannot warn you about the things that matter.
        #
        # Every non-ok status gets a message. An earlier version reported only ``cadence_lock`` and
        # ``dropout``, which meant the two most insidious failures were silent: a frozen heart rate
        # and a band that has worked loose both keep *producing numbers*, so the gate would quietly
        # stop trusting them and the athlete would finish the run with no idea the data was junk --
        # and no idea to reseat the strap, which is the one thing that would have fixed it.
        #
        # Silence is the wrong default here. A sensor fault the athlete can correct mid-run is worth
        # interrupting for exactly once, which is what the cooldown is for.
        degraded_key = {"frozen": "hr_frozen", "not_worn": "hr_not_worn",
                        "cadence_lock": "cadence_lock", "dropout": "hr_dropout"}.get(tick.hr_status)
        if degraded_key and self._degraded_said.get(degraded_key, 0) >= 2:
            pass
        elif tick.hr_status == "frozen":
            cues.append(Cue(CueLevel.SESSION,
                            "Heart rate has been stuck on the same value -- that usually means the "
                            "strap has shifted. Guiding by pace until it recovers. Snug the band a "
                            "little higher on your forearm.",
                            key="hr_frozen", cooldown_s=300.0))
        elif tick.hr_status == "not_worn":
            cues.append(Cue(CueLevel.SESSION,
                            "The armband looks like it is not reading your skin. Check it has not "
                            "worked loose. Guiding by pace until it is back.",
                            key="hr_not_worn", cooldown_s=300.0))
        elif tick.hr_status == "cadence_lock":
            cues.append(Cue(CueLevel.SESSION,
                            "Heart rate has locked onto your step rate, so I am ignoring it and "
                            "guiding by pace. Try shifting the strap slightly and snugging it.",
                            key="cadence_lock", cooldown_s=300.0))
        elif tick.hr_status == "dropout":
            cues.append(Cue(CueLevel.SESSION,
                            "Lost the heart-rate signal. Guiding by pace and feel until it "
                            "returns.", key="hr_dropout", cooldown_s=300.0))

        # ---- 4. drift vs effort ----
        window = 300.0
        hr_win = [(t, v) for t, v in self._hr_hist if t >= tick.t_s - window]
        sp_win = [(t, v) for t, v in self._sp_hist if t >= tick.t_s - window]
        rise_kind, rise_diag = classify_hr_rise(hr_win, sp_win)
        if (rise_kind == "drift" and self.intent.kind in ("long", "easy")
                and not self._drift_announced and tick.t_s > 1800):
            self._drift_announced = True
            # Widen the ceiling rather than repeatedly demanding a slowdown: on a long run this
            # rise is expected and the correct response is to keep effort, not chase the number.
            self._band_widened_bpm = 5.0
            cues.append(Cue(CueLevel.INFO,
                            "Your heart rate is drifting up at steady pace -- that is normal this "
                            "far into a long run, not a sign you are going too hard. I have "
                            "widened the target by 5 beats. Keep the effort, let the pace ease if "
                            "it wants to, and drink.", key="drift_explained", cooldown_s=3600.0))

        # ---- 5. zone adherence, on the LEAD-COMPENSATED HR ----
        in_target: Optional[bool] = None
        hr_ss: Optional[float] = None
        band: Optional[Tuple[float, float]] = None
        correction: Optional[float] = None

        if mode in (ControlMode.HR_AND_PACE, ControlMode.HR_ONLY) and tick.hr_bpm:
            slope = self._hr_slope()
            hr_ss = predict_steady_state_hr(tick.hr_bpm, slope)
            lo, hi = self._target_band(tick.grade)
            band = (lo, hi)
            too_high = hr_ss > hi + HR_DEADBAND_BPM
            too_low = (hr_ss < lo - HR_DEADBAND_BPM) and not self.intent.ceiling_only
            in_target = not (too_high or too_low)

            sign = 1 if too_high else (-1 if too_low else 0)
            if sign == 0:
                self._error_since, self._error_sign = None, 0
            else:
                if self._error_sign != sign:
                    self._error_since, self._error_sign = tick.t_s, sign
                held = tick.t_s - (self._error_since or tick.t_s)
                if held >= CONFIRM_S and self.state not in (RunState.REP, RunState.WARMUP):
                    err = (hr_ss - hi) if too_high else (hr_ss - lo)
                    correction = speed_correction(err, self.hr_speed_slope)
                    if too_high:
                        # Do not nag during genuine drift -- that case is handled above.
                        if rise_kind != "drift":
                            pace_txt = ""
                            if tick.speed_m_s:
                                new_pace = speed_to_pace(max(0.5, tick.speed_m_s + correction))
                                # Two cases where naming a pace is worse than naming none.
                                #
                                # On a climb, pace is not the instruction -- effort is. The
                                # grade-adjusted arithmetic is correct and still produces numbers
                                # like "16:01 per kilometre", which is a walking pace being offered
                                # as a running target. Nobody can act on that.
                                #
                                # And any target slower than about 12 min/km is slower than a brisk
                                # walk, so the honest instruction is to walk, not to run a number.
                                if abs(tick.grade) >= 0.03:
                                    pace_txt = (" Do not chase a pace on this climb -- "
                                                "back the effort off and let the pace be whatever "
                                                "it is.")
                                elif new_pace > 720:
                                    pace_txt = (" That is walking pace now -- drop to a walk until "
                                                "your heart rate comes back down.")
                                else:
                                    pace_txt = f" Try about {fmt_pace(new_pace)} per kilometre."
                            cues.append(Cue(CueLevel.PACE,
                                            f"Ease off -- you are heading for {hr_ss:.0f} beats and "
                                            f"this should top out around {hi:.0f}.{pace_txt}",
                                            key="slow_down", cooldown_s=PACE_CUE_MIN_GAP_S))
                    else:
                        cues.append(Cue(CueLevel.PACE,
                                        f"You can pick it up a little -- heart rate is settling "
                                        f"around {hr_ss:.0f} and the target starts at {lo:.0f}.",
                                        key="speed_up", cooldown_s=PACE_CUE_MIN_GAP_S))

        # ---- 6. pace-only fallback ----
        elif (mode == ControlMode.PACE_ONLY and self.intent.target_pace_sec_km and tick.speed_m_s
              and self.state not in (RunState.REP, RunState.WARMUP)):
            # The warm-up guard was missing here while the HR branch above had it, so a session with
            # a pace target would open by telling the athlete their warm-up jog was too slow. A
            # warm-up is *supposed* to be slower than the session's target; correcting it is not
            # merely noisy, it is wrong, and it lands in the first ten seconds of the run where it
            # does the most damage to trust in everything said afterwards.
            target = self.intent.target_pace_sec_km * grade_adjusted_pace_factor(tick.grade)
            actual = speed_to_pace(tick.speed_m_s)
            tol = self.intent.pace_tolerance
            in_target = abs(actual - target) <= tol * target
            if actual < target * (1 - tol):
                cues.append(Cue(CueLevel.PACE,
                                f"That is {fmt_pace(actual)} -- quicker than the "
                                f"{fmt_pace(target)} this session calls for. Ease back.",
                                key="slow_down", cooldown_s=PACE_CUE_MIN_GAP_S))
            elif actual > target * (1 + tol) and not self.intent.ceiling_only:
                cues.append(Cue(CueLevel.PACE,
                                f"That is {fmt_pace(actual)}; target is {fmt_pace(target)}.",
                                key="speed_up", cooldown_s=PACE_CUE_MIN_GAP_S))

        chosen = self.scheduler.submit(cues, tick.t_s)
        if chosen is not None and chosen.key in ("hr_frozen", "hr_not_worn", "cadence_lock",
                                                 "hr_dropout"):
            # Counted on *speaking*, not on generating: a cue suppressed by the scheduler was never
            # heard, so it must not consume one of the two mentions.
            self._degraded_said[chosen.key] = self._degraded_said.get(chosen.key, 0) + 1
        return ControlDecision(
            mode=mode, state=self.state, in_target=in_target, hr_ss_estimate=hr_ss,
            target_band=band, speed_correction_m_s=correction, cue=chosen,
            reason=rise_kind,
            diagnostics={**rise_diag, "band_widened_bpm": self._band_widened_bpm,
                         "hr_slope_bpm_s": round(self._hr_slope(), 4),
                         "error_held_s": (round(tick.t_s - self._error_since, 1)
                                          if self._error_since else 0.0)},
        )

    # ---- interval-set management -------------------------------------------------------

    def record_rep(self, rep_index: int, rep_pace_sec_km: float, hr_at_rep_end: float,
                   now_s: float, *, hr_after_recovery: Optional[float] = None) -> Optional[Cue]:
        """Log a completed rep and decide whether the set should be cut short.

        Two independent abort conditions, both about *quality* rather than willpower:

        * the rep faded more than :data:`REP_FADE_ABORT_PCT` off the first rep's pace, or
        * HR failed to fall below :data:`RECOVERY_HR_FRACTION` of reserve **by the end of the
          recovery interval**.

        The two HR arguments are deliberately separate and must not be conflated. ``hr_at_rep_end``
        is high by definition -- a VO2max rep finishes near 90% of reserve, that is what makes it a
        VO2max rep -- so testing *it* against a recovery threshold would cut almost every interval
        set ever run. Only ``hr_after_recovery``, sampled at the end of the jog recovery, carries
        the "not recovering" signal, and the check is skipped entirely when it is not supplied.

        Both conditions mean the remaining reps would be run at the wrong intensity, which is
        training fatigue rather than fitness. Stopping the set here is the correct outcome, not a
        failure, and the cue says so -- because a beginner told to stop mid-workout will otherwise
        read it as one.
        """
        self._rep_paces.append(rep_pace_sec_km)
        self.scheduler.protect(now_s, 8.0)
        if len(self._rep_paces) < 2:
            return None
        first = self._rep_paces[0]
        fade = (rep_pace_sec_km - first) / first
        if fade > REP_FADE_ABORT_PCT:
            return Cue(CueLevel.SESSION,
                       f"That rep was {fade*100:.0f}% slower than your first. The set has done its "
                       "job -- stop here and jog easy for the rest. Grinding out slower reps adds "
                       "fatigue, not fitness.", key="set_cut_fade")
        if hr_after_recovery is not None:
            frac = reserve_fraction_at_hr(hr_after_recovery, self.zones.hr_max, self.zones.hr_rest)
            if frac > RECOVERY_HR_FRACTION:
                self._recovery_failures += 1
                # Hysteresis: require TWO consecutive poor recoveries before cutting the set.
                #
                # This is the deliberate answer to a suggestion that the threshold be lowered from 75%
                # to 60% of reserve on the grounds that 75% rarely fires. Lowering it would make the
                # gate stricter in the wrong way -- a beginner on a jog recovery often will not reach
                # 60% of reserve within two or three minutes even when perfectly fine, so the set
                # would be cut on physiology that is working as expected. One high reading is noise
                # (a hill on the recovery jog, a badly timed sample, a moment of impatience); two in a
                # row is a pattern. Hysteresis keeps the gate meaningful without making it trigger-happy.
                if self._recovery_failures >= RECOVERY_FAILURES_TO_CUT:
                    return Cue(CueLevel.SESSION,
                               "Your heart rate has not come down between the last two reps. Finish "
                               "the set here and jog easy -- that is the honest read on today.",
                               key="set_cut_recovery")
            else:
                # A good recovery clears the count: the rule is two *consecutive* failures.
                self._recovery_failures = 0
        return None

    def check_long_run_decoupling(self, decouple: float, now_s: float,
                                  fraction_done: float) -> Optional[Cue]:
        """Mid-run decoupling check for a long run.

        Above :data:`DECOUPLE_CONVERT` at or past halfway, the remainder converts to easy running
        with walk breaks. Decoupling that high means the aerobic system is no longer holding the
        pace, and the last third of such a run reliably costs more in recovery than it returns.
        """
        if fraction_done < 0.5 or decouple <= DECOUPLE_CONVERT:
            return None
        return Cue(CueLevel.SESSION,
                   f"Heart rate has drifted {decouple*100:.0f}% relative to pace. Switching the "
                   "rest of this run to easy with walk breaks every 10 minutes -- you will still "
                   "get the time on feet, without the cost.", key="long_run_converted")
