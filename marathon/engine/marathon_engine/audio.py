"""The second audio channel: knowing you are on pace without looking at anything.

The problem this solves
-----------------------
:mod:`marathon_engine.realtime` is tuned to say as little as possible. Its test suite asserts fewer
than one spoken cue every two minutes, and a well-executed easy run produces two cues in forty
minutes. That is the right target for *speech*, and it completely fails a runner who cannot see the
screen and wants to know, continuously, whether they are holding pace.

The temptation is to speak more often. That is the wrong answer and it fails in a specific way: a
voice reading out your pace every thirty seconds over music becomes intolerable inside a single
session, so it gets muted -- and a muted coach cannot deliver the safety cues either. Making the
important channel noisy is how you lose the important channel.

So this is a **separate channel with a different cost profile**:

===============  ==============================  =================================
                 Speech (``realtime.py``)        Tones (this module)
===============  ==============================  =================================
Carries          Decisions, plan changes, risk   One fact: am I in the band?
Rate ceiling     0.5 per minute                  4 per minute, worst case
Duration         2-6 seconds                     ~0.2 seconds
Ducks music      Yes                             No
Attention cost   High -- must be parsed          Pre-attentive -- contour only
===============  ==============================  =================================

Why non-speech
--------------
Three reasons, in order of how much they matter.

1. **It does not compete with lyrics.** Speech over music forces the music down; a short tone sits on
   top of it.
2. **Rising-versus-falling is pre-attentive.** You do not decode a two-tone contour, you hear it the
   way you hear a phone ringing in another room. That matters at a breathing rate where parsing a
   sentence is genuinely hard.
3. **It is short enough to be frequent.** Two hundred milliseconds four times a minute is under two
   seconds of audio per minute. The same information in speech is thirty.

Silence means you are fine
--------------------------
The design is *silence while in band*. This is deliberate and it has one flaw, which is handled
rather than ignored: silence is ambiguous between "you are on pace" and "the app has died". Two
things resolve it -- a single confirming pip the moment you come back into band, so a correction
always closes its own loop, and a periodic spoken split (default every kilometre) which is short
enough to be worth its cost and doubles as proof of life.

Hysteresis, and why it is not optional
--------------------------------------
Pace derived from GPS is noisy at the tens-of-seconds-per-kilometre scale. A plain threshold at the
tolerance edge produces chatter: in, out, in, out, beeping every fifteen seconds while you run a
perfectly even pace. So the band is a Schmitt trigger -- you leave it at the tolerance and you are
not back inside until you reach :data:`RETURN_FRACTION` of it -- and the decision runs on a trailing
mean rather than the instantaneous value. Together those turn a noisy signal into a stable state.

What this module deliberately does not do
-----------------------------------------
It does not sonify heart rate continuously. Heart rate lags speed by around forty-five seconds, so a
tone tracking it would be telling you about the pace you were running most of a minute ago, and you
would chase it. Heart rate belongs to the slow, spoken loop where its lag is accounted for. This
channel tracks the thing you can change *now*.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, List, Optional, Tuple
from collections import deque

__all__ = ["Earcon", "AudioEvent", "PaceBandMonitor", "SplitAnnouncer", "TONE_MIN_GAP_S",
           "OVERLAP_FLOOR_S", "RETURN_FRACTION", "SMOOTHING_S", "MILD_MULTIPLE", "MILD_GAP_S",
           "LARGE_GAP_S", "MARGINAL_MULTIPLE", "MARGINAL_GAP_S", "ACQUIRE_GRACE_S",
           "MAX_UNACQUIRED_NUDGES"]


# ----------------------------------------------------------------------------------------
# Vocabulary
# ----------------------------------------------------------------------------------------


class Earcon(str, Enum):
    """The complete non-speech vocabulary. Five sounds, and that is the ceiling on purpose.

    Every additional sound is another thing to remember at a moment when you are breathing hard and
    thinking about traffic. Anything that cannot be said in these five belongs in speech, where it
    can be said in words instead of taught.
    """

    #: Two descending pips. You are running faster than the band.
    EASE = "ease"
    #: Two ascending pips. You are running slower than the band. Never emitted on a ceiling-only
    #: session -- see :class:`PaceBandMonitor`.
    LIFT = "lift"
    #: One mid pip. You are back in the band. This is what closes the loop on a correction, and it is
    #: the reason silence is readable as "fine" rather than "broken".
    IN_BAND = "in_band"
    #: Three quick rising pips, immediately before speech. Gives you ~400 ms to switch from listening
    #: to music to listening to words, so the first half of the sentence is not lost.
    ATTEND = "attend"
    #: A soft double-thud. Something is wrong with the signal and guidance has degraded.
    DEGRADED = "degraded"


@dataclass(frozen=True)
class AudioEvent:
    """One thing to play, and why."""
    earcon: Earcon
    t_s: float
    #: Signed fractional pace error at the moment of emission. Negative is fast, positive is slow.
    error: float = 0.0
    reason: str = ""


# ----------------------------------------------------------------------------------------
# Tuning
# ----------------------------------------------------------------------------------------

#: Never two *reminder* tones closer together than this. Four per minute is the absolute worst case,
#: and it only happens when you are a long way out and not correcting.
TONE_MIN_GAP_S = 15.0

#: Absolute floor between any two tones, so they cannot overlap in the ear.
#:
#: :data:`Earcon.IN_BAND` is exempt from :data:`TONE_MIN_GAP_S` and bounded only by this. That is
#: deliberate: the fifteen-second floor exists to stop nagging, and a confirmation is not nagging --
#: it fires at most once per excursion and it *ends* a sequence rather than extending it. Making it
#: obey the anti-nag floor meant that correcting quickly, which is the behaviour the channel is
#: trying to produce, silently lost its own acknowledgement. You would ease off, hear nothing, and
#: have no way to tell whether you had done enough.
OVERLAP_FLOOR_S = 2.0

#: Reminder interval ladder, keyed by how far outside the band you are as a multiple of the
#: tolerance. Three tiers rather than two, because two was wrong at the edge: a runner sitting a
#: fraction of a percent past a 6% tolerance was being reminded every thirty seconds, at the same
#: rate as a runner 20% out. That is nagging about a rounding error, and it is the behaviour that
#: gets a channel switched off.
#:
#: Being marginally out still deserves a reminder -- you are missing the session, and the tone costs
#: two hundred milliseconds -- but once a minute, not twice.
MARGINAL_MULTIPLE = 1.2
MARGINAL_GAP_S = 60.0

#: Gap while the error is mild -- between :data:`MARGINAL_MULTIPLE` and :data:`MILD_MULTIPLE`.
MILD_GAP_S = 30.0

#: Gap while the error is large.
LARGE_GAP_S = 15.0

#: Above this multiple of the tolerance, the error counts as large.
MILD_MULTIPLE = 1.5

#: You are back "in band" only once the error falls to this fraction of the tolerance. The gap
#: between leaving at 1.0 and returning at 0.6 is what stops boundary chatter.
RETURN_FRACTION = 0.6

#: How long the athlete may be slower than target, having never yet reached it, before the channel
#: says so once anyway.
#:
#: The acquisition rule (see :attr:`PaceBandMonitor.acquired`) exists so a warm-up is not policed.
#: This bounds it: someone who starts the work portion and simply cannot reach the prescribed pace
#: needs to be told, once, rather than left in a silence they will read as approval.
ACQUIRE_GRACE_S = 180.0

#: How many times the channel will say "you are not up to pace" before giving up on saying it.
#:
#: Same reasoning as the sensor-fault cap in :mod:`marathon_engine.realtime`: the message is
#: actionable twice, and after that it is beeping about something you have already failed or declined
#: to do. If you cannot hit the prescribed pace today, being told nine more times does not help, and
#: the spoken channel will raise it at the weekly review where it can actually change the plan.
MAX_UNACQUIRED_NUDGES = 2

#: Trailing window the pace decision is made on. Long enough to swallow GPS noise, short enough that
#: a deliberate change of effort is reflected within about half a cue interval.
SMOOTHING_S = 20.0

#: Minimum usable samples in the window before any judgement is made at all. Below this the honest
#: answer is silence, not a guess.
MIN_SAMPLES = 8


# ----------------------------------------------------------------------------------------
# Monitor
# ----------------------------------------------------------------------------------------


@dataclass
class PaceBandMonitor:
    """Decides, once a second, whether to play a tone.

    The state machine has three states -- ``in``, ``fast``, ``slow`` -- plus an ``unknown`` state for
    when pace cannot be trusted. Transitions emit tones; staying put emits nothing except the
    repeat-while-out-of-band reminder.

    :param target_pace_sec_km: the middle of the band. ``None`` disables the channel entirely, which
        is correct for a session with no pace target: beeping at someone about a number that was
        never prescribed is worse than saying nothing.
    :param tolerance: fractional half-width of the band. 0.06 means +/-6%, which at 8:40/km is about
        +/-31 s/km -- roughly the point below which GPS noise, not the runner, dominates.
    :param ceiling_only: easy and long runs have an upper bound and no lower one. On those,
        :attr:`Earcon.LIFT` is never emitted, because "you are running too slowly" is not a defect
        on a recovery run -- it is the session working.
    """

    target_pace_sec_km: Optional[float]
    tolerance: float = 0.06
    ceiling_only: bool = False
    #: Set false to silence the tone channel without silencing speech.
    enabled: bool = True

    state: str = "unknown"
    #: True once the athlete has been inside the band at least once this session.
    #:
    #: Until then, being **slow** earns silence. This is not politeness, it is a defect fix: a tempo
    #: session opens with a ten-minute warm-up jog that is deliberately far slower than the target,
    #: and without this rule the channel emitted a tone every fifteen seconds for the whole warm-up
    #: -- twenty tones telling the athlete to speed up during the part of the session where they are
    #: supposed to be going slowly. Twenty is not a coach, it is the thing you switch off.
    #:
    #: Being **fast** is policed from the first second, because there is no session where starting
    #: too hard is the prescription, and going out too fast is the beginner error this whole plan is
    #: built to prevent.
    acquired: bool = False
    _window: Deque[Tuple[float, float]] = field(default_factory=deque, repr=False)
    _last_tone_t: Optional[float] = None
    _last_tone: Optional[Earcon] = None
    #: True while a reminder has been played that has not yet been resolved by a return to band.
    #: Gates the confirming pip, so a pip is never heard without a warning it refers to.
    _pending_ack: bool = False
    #: When the current unbroken slow stretch began, for the acquisition grace.
    _slow_since: Optional[float] = None
    #: How many "not up to pace yet" nudges have been played. Capped.
    _unacquired_nudges: int = 0

    # -- input -------------------------------------------------------------------------------

    def update(self, t_s: float, pace_sec_km: Optional[float], *,
               grade: float = 0.0, pace_trusted: bool = True,
               running: bool = True) -> Optional[AudioEvent]:
        """Feed one second and get back a tone to play, or ``None``.

        ``running`` is false during warm-ups, walk breaks and pauses. The channel goes silent then,
        because a walk break in a run-walk session is not a pace failure -- it is the prescription,
        and beeping at it would teach you to ignore the beeps.
        """
        if not self.enabled or self.target_pace_sec_km is None or not running:
            self._window.clear()
            return None

        if not pace_trusted or pace_sec_km is None or pace_sec_km <= 0:
            # No trustworthy pace. Announce the degradation once, then go quiet rather than beep
            # about a number that is not real.
            self._window.clear()
            if self.state != "unknown":
                self.state = "unknown"
                return self._emit(Earcon.DEGRADED, t_s, 0.0, "pace untrusted")
            return None

        self._window.append((t_s, pace_sec_km))
        while self._window and self._window[0][0] < t_s - SMOOTHING_S:
            self._window.popleft()
        if len(self._window) < MIN_SAMPLES:
            return None

        mean_pace = sum(p for _, p in self._window) / len(self._window)
        target = self._grade_adjusted_target(grade)
        # Positive error is slow, negative is fast. Expressed as a fraction so the same tolerance
        # works across the whole range of paces this plan will ever prescribe.
        error = (mean_pace - target) / target
        return self._decide(t_s, error)

    # -- decision ----------------------------------------------------------------------------

    def _decide(self, t_s: float, error: float) -> Optional[AudioEvent]:
        tol = self.tolerance
        magnitude = abs(error)
        inside = magnitude <= (tol * RETURN_FRACTION if self.state in ("fast", "slow") else tol)

        # ---- inside the band ----------------------------------------------------------------
        if inside:
            was_out = self.state in ("fast", "slow")
            self.state = "in"
            self.acquired = True
            self._slow_since = None
            if was_out and self._pending_ack:
                # Acknowledge only what was actually announced. Reaching target pace for the first
                # time is not "back in the band" -- nothing was said, so nothing needs closing, and
                # a pip out of nowhere would be a sound with no referent.
                self._pending_ack = False
                return self._emit(Earcon.IN_BAND, t_s, error, "back in the band")
            self._pending_ack = False
            return None

        # ---- outside the band ---------------------------------------------------------------
        side = "slow" if error > 0 else "fast"

        if side == "slow" and self.ceiling_only:
            # Slower than target on an easy or long run is the session working, not a defect.
            self.state = "in"
            self._slow_since = None
            return None

        changed_side = side != self.state
        self.state = side

        if side == "slow":
            self._slow_since = self._slow_since if self._slow_since is not None else t_s
            if not self.acquired:
                # Not up to pace yet, and never has been. See ``acquired``: this is the warm-up, and
                # policing it produced twenty tones in five minutes telling someone to speed up
                # during the part of the session where slow is the instruction.
                if t_s - self._slow_since < ACQUIRE_GRACE_S:
                    return None
                if self._unacquired_nudges >= MAX_UNACQUIRED_NUDGES:
                    return None
        else:
            self._slow_since = None

        if changed_side:
            return self._emit(self._tone_for(side), t_s, error, "crossed to the other side")

        if self._last_tone_t is None:
            return self._emit(self._tone_for(side), t_s, error, "left the band")

        if magnitude > tol * MILD_MULTIPLE:
            gap = LARGE_GAP_S
        elif magnitude > tol * MARGINAL_MULTIPLE:
            gap = MILD_GAP_S
        else:
            gap = MARGINAL_GAP_S
        if t_s - self._last_tone_t >= gap:
            return self._emit(self._tone_for(side), t_s, error, "still out of the band")
        return None

    def _tone_for(self, state: str) -> Earcon:
        return Earcon.EASE if state == "fast" else Earcon.LIFT

    def _emit(self, earcon: Earcon, t_s: float, error: float,
              reason: str) -> Optional[AudioEvent]:
        floor = OVERLAP_FLOOR_S if earcon in (Earcon.IN_BAND, Earcon.DEGRADED) else TONE_MIN_GAP_S
        if self._last_tone_t is not None and t_s - self._last_tone_t < floor:
            return None
        self._last_tone_t = t_s
        self._last_tone = earcon
        if earcon in (Earcon.EASE, Earcon.LIFT):
            self._pending_ack = True
            if earcon is Earcon.LIFT and not self.acquired:
                self._unacquired_nudges += 1
        return AudioEvent(earcon=earcon, t_s=t_s, error=round(error, 4), reason=reason)

    def _grade_adjusted_target(self, grade: float) -> float:
        """The band moves with the hill, so a climb is not reported as running too slowly.

        Without this the tone channel would beep ``LIFT`` all the way up every incline, which is both
        wrong and the fastest possible way to teach someone to ignore it.
        """
        from marathon_engine.physiology import grade_adjusted_pace_factor
        assert self.target_pace_sec_km is not None
        return self.target_pace_sec_km * grade_adjusted_pace_factor(grade)

    # -- introspection -----------------------------------------------------------------------

    def band(self, grade: float = 0.0) -> Optional[Tuple[float, float]]:
        """The current band as ``(fast_edge, slow_edge)`` in seconds per kilometre."""
        if self.target_pace_sec_km is None:
            return None
        t = self._grade_adjusted_target(grade)
        return (t * (1 - self.tolerance), t * (1 + self.tolerance))


# ----------------------------------------------------------------------------------------
# Periodic spoken status
# ----------------------------------------------------------------------------------------


@dataclass
class SplitAnnouncer:
    """The short spoken line that makes silence unambiguous.

    Kept to about two seconds, with the number first. "Eight forty, on pace" is usable at a breathing
    rate where "you are currently averaging eight minutes and forty seconds per kilometre, which is
    within your target range" is not -- by the time the sentence resolves you have stopped listening,
    and worse, you have learned that these announcements are not worth listening to.
    """

    #: Announce every this many metres. ``None`` disables distance splits.
    every_m: Optional[float] = 1000.0
    #: And/or every this many seconds. ``None`` disables time splits.
    every_s: Optional[float] = None

    _last_split_m: float = 0.0
    _last_split_t: float = 0.0

    def update(self, t_s: float, distance_m: float, pace_sec_km: Optional[float],
               state: str) -> Optional[str]:
        due = False
        if self.every_m and distance_m - self._last_split_m >= self.every_m:
            self._last_split_m += self.every_m
            due = True
        if self.every_s and t_s - self._last_split_t >= self.every_s:
            self._last_split_t = t_s
            due = True
        if not due:
            return None

        from marathon_engine.physiology import fmt_pace
        parts: List[str] = []
        if self.every_m:
            km = self._last_split_m / 1000.0
            parts.append(f"{km:.0f}K" if km == int(km) else f"{km:.1f}K")
        if pace_sec_km:
            parts.append(fmt_pace(pace_sec_km))
        parts.append({"in": "on pace", "fast": "easing", "slow": "lift",
                      "unknown": "no pace signal"}.get(state, ""))
        return ". ".join(p for p in parts if p) + "."
