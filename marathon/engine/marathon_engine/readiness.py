"""Daily readiness: decide what today's session should become, before the run starts.

This is the HRV-guided-training layer. It consumes the nightly stream the user's **Eight Sleep
controller** already produces (``avg_hrv``, ``resting_hr``, ``total_sleep_min``, ``wake_events``,
``sleep_efficiency``) plus optional morning subjective input, and emits a band that the planner
and the watch-free run screen both key off.

Design decisions that matter
----------------------------
**We use lnRMSSD, a rolling 7-day mean, and a smallest-worthwhile-change band, not a vendor
"recovery score".** That is the exact machinery the HRV-guided training RCTs used, and the
comparison that has actually beaten a fixed plan in a trial:

* Vesterinen et al. 2016, *Med Sci Sports Exerc* 48(7):1347-1354 — HRV-guided training in
  recreational runners: 13.2 vs 17.7 hard sessions and a 2.1% vs 1.1% 3000 m improvement, i.e.
  *better* results from *fewer* hard sessions, which is the entire argument for this module.
* Javaloyes et al. 2019, *Int J Sports Physiol Perform* 14(1):23-32 — HRV-guided vs **traditional**
  periodisation in well-trained cyclists. Javaloyes et al. 2020, *J Strength Cond Res* 34(6) is the
  separate block-periodisation comparison; the two are routinely conflated and are different papers.
* Nuuttila et al. 2017 — individualised HRV-guided training in runners.
* Plews et al. 2013, *Eur J Appl Physiol* 113:1509 — why a **7-day rolling mean** beats any single
  morning value, and why the *trend* is the signal.

  Note on what is *not* claimed: Kiviniemi et al. 2007 is often cited as the origin of this decision
  rule, but it used high-frequency R-R power with a mean-minus-1-SD reference, not lnRMSSD with a
  symmetric band. The rule implemented here is the Vesterinen/Javaloyes/Nuuttila one.

**The band logic.** Let ``M7`` be the 7-day rolling mean of lnRMSSD and ``B`` the baseline mean
with between-day SD ``SD_b``, both from a rolling reference window. The band half-width is
``0.5 * SD_b``. Then:

*On the 0.5 multiplier.* This is **not** Hopkins' smallest worthwhile change, and citing him for it
is a common error: Hopkins' SWC is 0.2 x *between-subject* SD. The 0.5 x *within-individual* SD
figure comes from the Plews/Buchheit HRV practice, and it is a different quantity with a different
justification. The constant is named :data:`SWC_MULTIPLIER` for continuity with that literature,
and the docstring says what it actually is.

*Why the band is applied to the 7-day MEAN and not to a single day.* This matters and is easy to get
wrong. Under normality only ~38% of individual daily values fall inside mean +/- 0.5 SD, so a band
that narrow applied to *today's reading* would flag roughly 3 days in 5 -- useless as a gate. The
standard error of a 7-day mean is ``SD/sqrt(7) ~= 0.38 SD``, so the same +/-0.5 SD band around the
rolling mean is +/-1.3 standard errors and contains about 80% of observations. That is the behaviour
we want: a fifth of days flagged, driven by trend rather than by one bad night. Applying this band to
a single morning value would be a statistical error, and the implementation deliberately does not.

* ``M7 > B + SWC``  -> **primed**: proceed with the week's hardest session as planned. Note that
  this is *the same prescription as ``normal``* -- in Vesterinen and Javaloyes, hard work was
  prescribed when HRV was within **or** above the band, and there is no third "add extra load"
  band anywhere in that literature. We keep ``primed`` as a distinct *label* because it is
  informative to see, but it must never authorise load the plan did not already call for.
* ``B - SWC <= M7 <= B + SWC`` -> **normal**: run the plan as written.
* ``M7 < B - SWC``  -> **suppressed**: replace intensity with easy aerobic work.
* ``M7 < B - 2*SWC`` for >=2 consecutive days -> **strained**: rest or 20 min walk, and if it
  persists past 4 days, treat it as a flag to look for illness / a life stressor, not to push on.

**Sleep is not a tiebreaker for this user, it is a primary input.** A resident's short nights are
not noise: <7 h sleep is associated with a large increase in musculoskeletal injury in athletes
(Milewski et al. 2014, *J Pediatr Orthop* 34:129 -- adolescent athletes, so the effect size does
not transfer directly, but the direction is consistent), and sleep restriction degrades
time-to-exhaustion and perceived effort. The user's own sleep-debt figure from the Eight Sleep
controller therefore enters the score directly and can veto quality work on its own.

**Honest limits.** HRV-guided training has been shown to work with *chest-strap or ECG* morning
measurements taken in a standardised position. Optical PPI from an armband worn overnight is a
noisier substrate; the artifact rejection in :mod:`marathon_engine.signal_quality` is what makes
it usable, and any night with too few clean intervals is dropped rather than averaged in.
This module is advisory. It is not a medical device and it does not diagnose anything.

Pure functions, stdlib only.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "NightSummary", "HrvBaseline", "Readiness", "hrv_baseline", "daily_readiness",
    "SWC_MULTIPLIER", "ROLLING_DAYS", "BASELINE_DAYS", "MIN_BASELINE_NIGHTS",
    "SLEEP_FLOOR_MIN", "SLEEP_TARGET_MIN", "BAND_ACTIONS",
]

#: Band half-width as a multiple of the within-individual between-day SD of lnRMSSD. From the
#: Plews/Buchheit HRV practice -- NOT Hopkins' smallest worthwhile change, which is 0.2 x
#: between-subject SD. See the module docstring for why this is applied to the 7-day mean.
SWC_MULTIPLIER = 0.5
ROLLING_DAYS = 7              # Plews: the 7-day rolling mean is the signal
BASELINE_DAYS = 60            # reference window for the baseline mean and between-day SD
MIN_BASELINE_NIGHTS = 14      # below this, we do not pretend to have a baseline

SLEEP_FLOOR_MIN = 6 * 60      # below this, quality work is vetoed outright
SLEEP_TARGET_MIN = 7.5 * 60   # the "no deficit" target

#: Maximum fraction of rejected beats for a night's HRV to be usable. RMSSD is the most
#: artifact-sensitive HRV index; accepted practice is <5%.
MAX_ARTIFACT_FRACTION = 0.05

#: What each band does to today's planned session. The planner reads this; the app displays it.
BAND_ACTIONS: Dict[str, str] = {
    # Deliberately the same action as "normal": above-band and within-band both simply run the
    # plan. An "upgrade" band would be an unvalidated intensity-escalation path invented for a
    # beginner, which is the last person who needs one.
    "primed": "proceed",
    "normal": "proceed",
    "suppressed": "downgrade_to_easy",
    "strained": "rest_or_walk",
    "unknown": "proceed_conservatively",
}


@dataclass
class NightSummary:
    """One night, as the Eight Sleep controller reports it.

    ``hrv_ms`` is RMSSD in milliseconds (the controller computes it from Polar RR/PPI intervals);
    ``clean_interval_count`` lets us reject a night whose HRV came from too little good data.
    """
    day: date                       # the morning this night belongs to
    hrv_ms: Optional[float] = None
    #: Which metric ``hrv_ms`` is, and where it came from. This is NOT bookkeeping -- it is a
    #: correctness requirement. Device, posture (supine vs standing) and window length each shift
    #: lnRMSSD by MORE than the band we are trying to detect, so a series that mixes sources
    #: generates a spurious flag on every source switch. :func:`hrv_baseline` therefore refuses to
    #: build a baseline from mixed sources and keeps one series per source.
    #:
    #: Two specific traps this guards against:
    #:  * **HealthKit exposes only SDNN** (``heartRateVariabilitySDNN``). There is no RMSSD type and
    #:    no beat-interval type. SDNN and RMSSD are different quantities and one cannot be converted
    #:    to the other, so anything arriving via Apple Health must be tagged ``healthkit_sdnn`` and
    #:    kept in its own series with its own baseline.
    #:  * **The Eight Sleep pod is under-mattress ballistocardiography, not PPG**, and its HRV output
    #:    is not independently validated. Where the SleepController computes RMSSD from Polar
    #:    RR/PPI intervals, that is a Polar-derived number and should be tagged as such.
    hrv_source: str = "polar_ppi_rmssd"
    #: Posture matters as much as device; a standing measurement is not comparable to a supine one.
    hrv_posture: str = "sleep"      # sleep | supine | standing
    resting_hr: Optional[float] = None
    total_sleep_min: Optional[float] = None
    wake_events: Optional[int] = None
    sleep_efficiency: Optional[float] = None
    clean_interval_count: Optional[int] = None
    #: Fraction of beats rejected by :func:`~marathon_engine.signal_quality.clean_intervals`.
    artifact_fraction: Optional[float] = None
    sleep_debt_min: Optional[float] = None   # cumulative, from the controller's own accounting
    #: True when this night followed or contained a night shift or call. Shift nights make sleep
    #: duration bimodal, so they get their own baseline rather than polluting the normal one.
    shift_night: bool = False

    #: Optional morning subjective input (Hooper-style 1-7 scales; lower is better for all three).
    soreness_1_7: Optional[int] = None
    fatigue_1_7: Optional[int] = None
    stress_1_7: Optional[int] = None
    motivation_1_7: Optional[int] = None
    hard_day_yesterday: bool = False
    illness: bool = False
    alcohol: bool = False

    @property
    def ln_hrv(self) -> Optional[float]:
        """Natural log of RMSSD. HRV is log-normally distributed, so every statistic here --
        mean, SD, SWC -- must be computed on the log scale or the band is wrong."""
        if self.hrv_ms is None or self.hrv_ms <= 0:
            return None
        return math.log(self.hrv_ms)

    @property
    def usable_hrv(self) -> bool:
        """Whether this night's HRV may enter the baseline.

        Rejects nights with too few clean beat intervals. 240 is a deliberately modest floor:
        it is roughly 4 minutes of clean beats, far less than a full night, because the goal is
        to exclude a *sensor failure*, not to demand perfection from an optical armband.
        """
        if self.ln_hrv is None:
            return False
        if self.clean_interval_count is not None and self.clean_interval_count < 240:
            return False
        if self.artifact_fraction is not None and self.artifact_fraction > MAX_ARTIFACT_FRACTION:
            # RMSSD is the most artifact-sensitive time-domain HRV index there is: a few percent of
            # missed or extra beats inflates it severalfold, and interpolating them deflates it.
            # Accepted practice is <5% artifacts. Accepting a noisier window while trying to detect
            # a 0.5-SD shift means the artifact noise exceeds the signal.
            return False
        return True

    def to_dict(self) -> dict:
        return {"day": self.day.isoformat(), "hrv_ms": self.hrv_ms,
                "resting_hr": self.resting_hr, "total_sleep_min": self.total_sleep_min,
                "wake_events": self.wake_events, "sleep_efficiency": self.sleep_efficiency,
                "usable_hrv": self.usable_hrv}


@dataclass
class HrvBaseline:
    """The athlete's own HRV reference: mean, between-day SD, and the derived SWC band."""
    mean_ln: float
    sd_ln: float
    n_nights: int
    swc: float
    rhr_mean: Optional[float] = None
    rhr_sd: Optional[float] = None

    @property
    def low(self) -> float:
        return self.mean_ln - self.swc

    @property
    def high(self) -> float:
        return self.mean_ln + self.swc

    def to_dict(self) -> dict:
        return {"mean_ln": round(self.mean_ln, 4), "sd_ln": round(self.sd_ln, 4),
                "n_nights": self.n_nights, "swc": round(self.swc, 4),
                "band_ln": [round(self.low, 4), round(self.high, 4)],
                "band_ms": [round(math.exp(self.low), 1), round(math.exp(self.high), 1)],
                "mean_ms": round(math.exp(self.mean_ln), 1),
                "rhr_mean": round(self.rhr_mean, 1) if self.rhr_mean else None}


def hrv_baseline(nights: Sequence[NightSummary], *, as_of: Optional[date] = None,
                 window_days: int = BASELINE_DAYS) -> Optional[HrvBaseline]:
    """Rolling baseline over the last ``window_days``, or ``None`` if there is not enough data.

    Returning ``None`` rather than a guess is deliberate: with fewer than
    :data:`MIN_BASELINE_NIGHTS` usable nights, an SWC band is narrower than the measurement noise
    and would flip the plan around at random. Until then readiness falls back to sleep and
    subjective input only.
    """
    if not nights:
        return None
    end = as_of or max(n.day for n in nights)
    start = end - timedelta(days=window_days)
    usable = [n for n in nights if start <= n.day <= end and n.usable_hrv]

    # Never build one baseline from mixed measurement sources or postures. A device or posture
    # change shifts lnRMSSD by more than the band being detected, so a mixed series would flag a
    # spurious "suppressed" on the day the source changed and keep flagging until the window rolled
    # over. Keep the dominant source and drop the rest rather than silently averaging them.
    if usable:
        keys = [(n.hrv_source, n.hrv_posture) for n in usable]
        dominant = max(set(keys), key=keys.count)
        usable = [n for n in usable if (n.hrv_source, n.hrv_posture) == dominant]

    if len(usable) < MIN_BASELINE_NIGHTS:
        return None
    lns = [n.ln_hrv for n in usable if n.ln_hrv is not None]
    mean_ln = statistics.fmean(lns)
    sd_ln = statistics.stdev(lns) if len(lns) > 1 else 0.0
    rhrs = [n.resting_hr for n in usable if n.resting_hr]
    return HrvBaseline(
        mean_ln=mean_ln, sd_ln=sd_ln, n_nights=len(usable),
        swc=SWC_MULTIPLIER * sd_ln,
        rhr_mean=statistics.fmean(rhrs) if rhrs else None,
        rhr_sd=statistics.stdev(rhrs) if len(rhrs) > 1 else None,
    )


def _rolling_mean_ln(nights: Sequence[NightSummary], as_of: date,
                     days: int = ROLLING_DAYS) -> Optional[float]:
    start = as_of - timedelta(days=days - 1)
    lns = [n.ln_hrv for n in nights if start <= n.day <= as_of and n.usable_hrv]
    lns = [x for x in lns if x is not None]
    # Require at least 3 of the 7 days: a "7-day mean" from one measurement is a single
    # measurement wearing a hat.
    return statistics.fmean(lns) if len(lns) >= 3 else None


@dataclass
class Readiness:
    """Today's verdict."""
    day: date
    band: str                     # primed | normal | suppressed | strained | unknown
    action: str                   # see BAND_ACTIONS
    score: int                    # 0-100, for display and trend charts only
    hrv_status: str               # above | within | below | well_below | no_baseline
    rolling_ln_hrv: Optional[float]
    baseline: Optional[HrvBaseline]
    components: Dict[str, float] = field(default_factory=dict)
    flags: List[Dict[str, str]] = field(default_factory=list)
    headline: str = ""
    detail: str = ""
    #: Set when a single hard constraint forced the band regardless of HRV.
    override_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {"day": self.day.isoformat(), "band": self.band, "action": self.action,
                "score": self.score, "hrv_status": self.hrv_status,
                "rolling_ln_hrv": (round(self.rolling_ln_hrv, 4)
                                   if self.rolling_ln_hrv is not None else None),
                "rolling_hrv_ms": (round(math.exp(self.rolling_ln_hrv), 1)
                                   if self.rolling_ln_hrv is not None else None),
                "baseline": self.baseline.to_dict() if self.baseline else None,
                "components": {k: round(v, 1) for k, v in self.components.items()},
                "flags": self.flags, "headline": self.headline, "detail": self.detail,
                "override_reason": self.override_reason}


def _hooper_penalty(n: NightSummary) -> Tuple[float, List[Dict[str, str]]]:
    """Subjective wellness penalty (0..30) plus flags, from the Hooper-style 1-7 scales.

    Subjective wellness tracks training load at least as responsively as objective markers
    (Saw, Main & Gastin 2016, *Br J Sports Med* 50:281 -- systematic review: self-report measures
    responded to load changes with *superior* sensitivity to objective ones). Two questions in the
    morning are cheap and carry real signal, so they are weighted accordingly rather than
    decoratively.
    """
    penalty, flags = 0.0, []
    for label, val, weight in (("soreness", n.soreness_1_7, 3.0),
                               ("fatigue", n.fatigue_1_7, 3.0),
                               ("stress", n.stress_1_7, 2.0)):
        if val is not None and val > 3:
            penalty += (val - 3) * weight
            if val >= 6:
                flags.append({"flag": f"high_{label}", "severity": "medium",
                              "message": f"Self-reported {label} {val}/7."})
    if n.motivation_1_7 is not None and n.motivation_1_7 <= 2:
        penalty += 4.0
        flags.append({"flag": "low_motivation", "severity": "low",
                      "message": "Low motivation -- often the first sign of accumulated fatigue."})
    return min(30.0, penalty), flags


def daily_readiness(nights: Sequence[NightSummary], *, as_of: Optional[date] = None,
                    baseline: Optional[HrvBaseline] = None) -> Readiness:
    """Today's readiness band from the nightly history.

    Precedence, highest first -- hard constraints win over the HRV band, because no HRV reading
    makes it sensible to run intervals on 4 hours of sleep with a fever:

    1. ``illness`` reported                        -> strained (do not train)
    2. sleep < :data:`SLEEP_FLOOR_MIN`             -> suppressed at best
    3. HRV rolling mean < baseline - 2*SWC (2+ d)  -> strained
    4. HRV band comparison                         -> primed / normal / suppressed
    5. no usable baseline                          -> unknown, proceed conservatively
    """
    if not nights:
        today = as_of or date.today()
        return Readiness(day=today, band="unknown", action=BAND_ACTIONS["unknown"], score=50,
                         hrv_status="no_baseline", rolling_ln_hrv=None, baseline=None,
                         headline="No data yet",
                         detail="Wear the armband overnight for two weeks to build a baseline.")

    today = as_of or max(n.day for n in nights)
    by_day = {n.day: n for n in nights}
    tonight = by_day.get(today)
    base = baseline or hrv_baseline(nights, as_of=today)
    m7 = _rolling_mean_ln(nights, today)

    flags: List[Dict[str, str]] = []
    components: Dict[str, float] = {}

    # ---- HRV status -----------------------------------------------------------------
    hrv_status = "no_baseline"
    hrv_component = 50.0
    if base and m7 is not None:
        if m7 > base.high:
            hrv_status, hrv_component = "above", 85.0
        elif m7 >= base.low:
            # Linear inside the band so the score moves smoothly instead of stepping.
            span = max(1e-9, base.high - base.low)
            hrv_component = 50.0 + 25.0 * ((m7 - base.mean_ln) / (span / 2.0))
            hrv_status = "within"
        elif m7 >= base.mean_ln - 2 * base.swc:
            hrv_status, hrv_component = "below", 30.0
        else:
            hrv_status, hrv_component = "well_below", 12.0
        components["hrv"] = hrv_component
        if hrv_status in ("below", "well_below"):
            flags.append({"flag": "hrv_suppressed", "severity":
                          "high" if hrv_status == "well_below" else "medium",
                          "message": (f"7-day HRV {math.exp(m7):.0f} ms is below your "
                                      f"{math.exp(base.mean_ln):.0f} ms baseline band.")})

    # ---- Sleep --------------------------------------------------------------------
    sleep_component = 50.0
    tst = tonight.total_sleep_min if tonight else None
    if tst is not None:
        sleep_component = max(0.0, min(100.0, 100.0 * tst / SLEEP_TARGET_MIN))
        components["sleep"] = sleep_component
        if tst < SLEEP_FLOOR_MIN:
            flags.append({"flag": "short_sleep", "severity": "high",
                          "message": f"{tst/60:.1f} h of sleep -- below the {SLEEP_FLOOR_MIN/60:.0f} h "
                                     "floor for quality work."})
    debt = tonight.sleep_debt_min if tonight else None
    if debt:
        debt_penalty = min(25.0, debt / 600.0 * 25.0)
        components["sleep_debt_penalty"] = -debt_penalty
        if debt >= 240:
            flags.append({"flag": "sleep_debt", "severity": "medium" if debt < 360 else "high",
                          "message": f"~{debt/60:.1f} h cumulative sleep debt."})
    else:
        debt_penalty = 0.0

    # ---- Resting HR ---------------------------------------------------------------
    rhr_component = 50.0
    if tonight and tonight.resting_hr and base and base.rhr_mean and base.rhr_sd:
        z = (tonight.resting_hr - base.rhr_mean) / max(1.0, base.rhr_sd)
        rhr_component = max(0.0, min(100.0, 50.0 - z * 20.0))
        components["rhr"] = rhr_component
        if z >= 1.5:
            flags.append({"flag": "elevated_rhr", "severity": "medium",
                          "message": f"Resting HR {tonight.resting_hr:.0f} bpm is "
                                     f"{z:.1f} SD above baseline -- a classic early illness or "
                                     "overreaching signal."})

    # ---- Continuity ---------------------------------------------------------------
    continuity = 100.0
    if tonight:
        if tonight.wake_events:
            continuity -= min(50.0, tonight.wake_events * 15.0)
        if tonight.sleep_efficiency is not None and tonight.sleep_efficiency < 0.85:
            continuity -= (0.85 - tonight.sleep_efficiency) * 200.0
    continuity = max(0.0, min(100.0, continuity))
    components["continuity"] = continuity

    subj_penalty, subj_flags = _hooper_penalty(tonight) if tonight else (0.0, [])
    flags.extend(subj_flags)
    if subj_penalty:
        components["subjective_penalty"] = -subj_penalty

    # ---- Composite score (display only; the BAND is what drives training) ----------
    has_hrv = "hrv" in components
    if has_hrv:
        score = 0.40 * hrv_component + 0.28 * sleep_component + 0.14 * rhr_component \
                + 0.18 * continuity
    else:
        score = 0.55 * sleep_component + 0.45 * continuity
    score = max(0.0, min(100.0, score - debt_penalty - subj_penalty))

    # ---- Band, with hard overrides in precedence order -----------------------------
    override = None
    if tonight and tonight.illness:
        band, override = "strained", "illness reported"
    elif tst is not None and tst < SLEEP_FLOOR_MIN and hrv_status in ("below", "well_below"):
        band, override = "strained", "short sleep plus suppressed HRV"
    elif tst is not None and tst < SLEEP_FLOOR_MIN:
        band, override = "suppressed", f"sleep below the {SLEEP_FLOOR_MIN/60:.0f} h floor"
    elif hrv_status == "no_baseline":
        band = "unknown"
    elif hrv_status == "well_below" and _consecutive_well_below(nights, today, base) >= 2:
        band, override = "strained", "HRV more than 2xSWC below baseline for 2+ days"
    elif hrv_status == "well_below":
        band = "suppressed"
    elif hrv_status == "below":
        band = "suppressed"
    elif hrv_status == "above":
        band = "primed"
    else:
        band = "normal"

    # A high-severity subjective/physiological flag cannot be outvoted by a good HRV number.
    if band in ("primed", "normal") and any(f["severity"] == "high" for f in flags):
        band, override = "suppressed", "a high-severity flag is present"

    headline, detail = _narrate(band, hrv_status, tst, override)
    return Readiness(day=today, band=band, action=BAND_ACTIONS[band], score=int(round(score)),
                     hrv_status=hrv_status, rolling_ln_hrv=m7, baseline=base,
                     components=components, flags=flags, headline=headline, detail=detail,
                     override_reason=override)


def _consecutive_well_below(nights: Sequence[NightSummary], today: date,
                            base: Optional[HrvBaseline]) -> int:
    """How many consecutive days (ending today) the rolling mean has sat below ``mean - 2*SWC``."""
    if not base:
        return 0
    threshold = base.mean_ln - 2 * base.swc
    count, d = 0, today
    while True:
        m = _rolling_mean_ln(nights, d)
        if m is None or m >= threshold:
            return count
        count += 1
        d -= timedelta(days=1)
        if count > 30:
            return count


def _narrate(band: str, hrv_status: str, tst: Optional[float],
             override: Optional[str]) -> Tuple[str, str]:
    sleep_txt = f"{tst/60:.1f} h sleep" if tst else "sleep unknown"
    if band == "primed":
        return ("Primed",
                f"HRV is above your baseline band and you slept {sleep_txt}. If there is a hard "
                "session this week, today is the day for it.")
    if band == "normal":
        return ("Green -- run the plan",
                f"HRV inside your normal band, {sleep_txt}. Nothing to change.")
    if band == "suppressed":
        why = override or "HRV below your baseline band"
        return ("Back off today",
                f"{why.capitalize()}. Today's session becomes easy aerobic work -- same duration "
                "if you like, but keep it in Z1-Z2. Do not run the intervals; they will be there "
                "when you are recovered, and doing them now buys fatigue without adaptation.")
    if band == "strained":
        why = override or "HRV well below baseline for multiple days"
        return ("Rest",
                f"{why.capitalize()}. Rest day or a 20-minute walk. If this persists more than "
                "four days, look for a cause -- illness, a big life stressor, or genuine "
                "overreaching -- rather than training through it.")
    return ("Not enough data yet",
            f"No HRV baseline yet ({sleep_txt}). Running the plan as written, but keeping easy "
            "days genuinely easy until the baseline fills in.")
