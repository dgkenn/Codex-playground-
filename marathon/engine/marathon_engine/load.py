"""Training-load quantification and load-ratio monitoring.

What this module is for: turning a pile of runs into a small number of scalars that answer
"am I ramping too fast?" -- the question that decides whether a novice reaches the start line.

Sources
-------
* **Banister TRIMP** — Banister 1991; Morton, Fitz-Clarke & Banister 1990, *J Appl Physiol*
  69:1171. ``TRIMP = duration_min * dHR * 0.64 * exp(1.92 * dHR)`` for men
  (``0.86 * exp(1.67 * dHR)`` for women), with ``dHR`` = fraction of HR reserve. The exponential
  weighting is what makes a 30-min threshold run outrank a 45-min jog.
* **Edwards TRIMP** — Edwards 1993: zone minutes x zone weight (1..5). Cruder than Banister but
  transparent and robust to a few bad HR samples, so it is kept as a cross-check.
* **Session RPE** — Foster 1998, *Med Sci Sports Exerc* 30:1164: ``RPE(0-10) * duration_min``.
  The cheapest load metric that exists and it survives a dead sensor, which is why it is not
  optional here.
* **Monotony and strain** — Foster 1998: ``monotony = mean(daily load) / SD(daily load)`` over a
  week, ``strain = weekly load * monotony``. High monotony (>2.0) with high load is the
  "same thing every day" pattern associated with illness/overreaching in Foster's cohort.
* **Acute:chronic workload ratio** — Hulin/Gabbett; EWMA formulation from Williams et al. 2017,
  *Br J Sports Med* 51:209. **This metric is contested**: Impellizzeri et al. 2020
  (*Br J Sports Med* 54:1073, "ACWR: conceptual issues and fundamental pitfalls") and
  Impellizzeri 2021 show the classic "sweet spot" analyses suffer from mathematical coupling and
  poor reproducibility, and Wang et al. 2020 failed to replicate the injury-risk relationship.
  We therefore use ACWR as a **ramp-rate speed limit** -- a governor on how fast the plan may add
  load -- and never as an injury-probability claim. See :data:`ACWR_CAUTION` for the honest framing.

Pure functions, stdlib only.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "trimp_banister", "trimp_edwards", "session_rpe_load", "hr_tss",
    "ewma_load", "acwr", "AcwrResult", "monotony_strain", "MonotonyResult",
    "weekly_totals", "ramp_rate", "DailyLoad",
    "ACUTE_DAYS", "CHRONIC_DAYS", "ACWR_SWEET_LOW", "ACWR_SWEET_HIGH", "ACWR_HARD_CAP",
    "MONOTONY_WARN", "ACWR_CAUTION", "MAX_WEEKLY_RAMP",
]

# ----------------------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------------------

ACUTE_DAYS = 7
CHRONIC_DAYS = 28

#: The commonly cited "sweet spot". Kept because it is a *reasonable* band for a ramp governor,
#: labelled honestly because the evidence for it as an injury predictor is weak.
ACWR_SWEET_LOW = 0.80
ACWR_SWEET_HIGH = 1.30
#: Above this the planner refuses to add load regardless of how good the athlete feels. This is
#: the one place the ratio is allowed to *veto*, and it is set well above the "sweet spot" so that
#: normal week-to-week variation does not constantly trip it.
ACWR_HARD_CAP = 1.50

MONOTONY_WARN = 2.0

#: Finite stand-in for infinite monotony (a week with zero day-to-day variance) so that ``strain``
#: stays a comparable number instead of becoming inf/NaN and poisoning every downstream comparison.
_MONOTONY_SENTINEL = 10.0

#: Hard ceiling on week-over-week volume growth, as a fraction. The famous "10% rule" has never
#: been supported by a trial -- Buist et al. 2008 (*Am J Sports Med* 36:33) randomised novices to a
#: graded vs standard programme and found **no** difference in injury rate, and Nielsen's work
#: points at *within-week* spikes and individual capacity rather than a single global percentage.
#: We still impose a cap, because "no evidence that 10% helps" is not "evidence that 40% is safe",
#: and because the failure mode we are guarding against (tibial bone stress in weeks 3-10 of a
#: brand-new runner) is slow to appear and slow to heal.
MAX_WEEKLY_RAMP = 0.10

ACWR_CAUTION = (
    "ACWR is used here as a ramp-rate governor, not a risk score. The published 'sweet spot' "
    "analyses are affected by mathematical coupling (the acute load appears in both numerator and "
    "denominator) and have failed to replicate (Impellizzeri 2020/2021; Wang 2020). A ratio in "
    "range does not mean you are safe, and a ratio out of range does not mean you are injured -- "
    "it means the plan is changing load faster than the plan intends to."
)


@dataclass
class DailyLoad:
    """One day's training load. ``load`` is whichever metric the caller standardised on."""
    day: date
    load: float
    duration_min: float = 0.0
    distance_km: float = 0.0
    rpe: Optional[float] = None
    kind: str = "run"          # run | strength | cross | rest

    def to_dict(self) -> dict:
        return {"day": self.day.isoformat(), "load": round(self.load, 1),
                "duration_min": round(self.duration_min, 1),
                "distance_km": round(self.distance_km, 2),
                "rpe": self.rpe, "kind": self.kind}


# ----------------------------------------------------------------------------------------
# Per-session load metrics
# ----------------------------------------------------------------------------------------


def trimp_banister(duration_min: float, mean_hr: float, hr_rest: float, hr_max: float,
                   *, female: bool = False) -> float:
    """Banister TRIMP from a session's mean HR.

    Using the *mean* HR of a whole interval session understates it, because the exponential
    weighting is convex: the correct way is to sum TRIMP over short segments. Prefer
    :func:`trimp_banister_series` when you have the samples.
    """
    if duration_min <= 0:
        return 0.0
    if hr_max <= hr_rest:
        raise ValueError("hr_max must exceed hr_rest")
    dhr = (mean_hr - hr_rest) / (hr_max - hr_rest)
    dhr = max(0.0, min(1.3, dhr))
    a, b = (0.86, 1.67) if female else (0.64, 1.92)
    return duration_min * dhr * a * math.exp(b * dhr)


def trimp_banister_series(samples: Sequence[Tuple[float, float]], hr_rest: float, hr_max: float,
                          *, female: bool = False) -> float:
    """Banister TRIMP summed over ``(duration_min, hr)`` segments.

    Convexity matters: 30 min at 150 bpm plus 30 min at 110 bpm is a materially *larger* TRIMP
    than 60 min at 130 bpm, and only this form captures that.
    """
    return sum(trimp_banister(d, hr, hr_rest, hr_max, female=female) for d, hr in samples)


#: Edwards zone weights, by five-zone index (1..5).
_EDWARDS_WEIGHTS = {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0}


def trimp_edwards(zone_minutes: Dict[int, float]) -> float:
    """Edwards TRIMP: sum of ``minutes_in_zone * zone_index``."""
    return sum(_EDWARDS_WEIGHTS.get(z, 0.0) * m for z, m in zone_minutes.items())


def session_rpe_load(rpe_0_10: float, duration_min: float) -> float:
    """Foster session-RPE load. Survives a dead HR sensor; collect it every single run."""
    if not 0 <= rpe_0_10 <= 10:
        raise ValueError("RPE must be 0-10")
    return rpe_0_10 * max(0.0, duration_min)


def hr_tss(duration_min: float, mean_hr: float, lthr: float, hr_rest: float) -> float:
    """TrainingPeaks-style hrTSS: 100 points = 1 h at lactate threshold.

    Uses fraction of *threshold* reserve squared, mirroring how TSS scales with intensity
    (an hour at LT = 100). Provided because it is the unit most third-party tools speak; the
    engine's own decisions key off Banister TRIMP.
    """
    if lthr <= hr_rest:
        raise ValueError("lthr must exceed hr_rest")
    intensity = (mean_hr - hr_rest) / (lthr - hr_rest)
    return duration_min / 60.0 * 100.0 * intensity ** 2


# ----------------------------------------------------------------------------------------
# Rolling load
# ----------------------------------------------------------------------------------------


def ewma_load(loads: Sequence[float], n_days: int) -> float:
    """Exponentially weighted moving average with ``lambda = 2/(n+1)``.

    ``loads`` is in chronological order, one entry per calendar day including zeros for rest
    days. Omitting rest days is the most common way to make this number lie.
    """
    if n_days <= 0:
        raise ValueError("n_days must be positive")
    if not loads:
        return 0.0
    lam = 2.0 / (n_days + 1.0)
    ewma = loads[0]
    for x in loads[1:]:
        ewma = x * lam + ewma * (1.0 - lam)
    return ewma


@dataclass
class AcwrResult:
    acute: float
    chronic: float
    ratio: float
    band: str            # detraining | optimal | caution | danger | insufficient_history
    method: str          # ewma | rolling
    days_of_history: int
    note: str = ""

    def to_dict(self) -> dict:
        return {"acute": round(self.acute, 1), "chronic": round(self.chronic, 1),
                "ratio": round(self.ratio, 2), "band": self.band, "method": self.method,
                "days_of_history": self.days_of_history, "note": self.note}


def acwr(daily_loads: Sequence[float], *, method: str = "ewma") -> AcwrResult:
    """Acute:chronic workload ratio over a chronological, gap-filled daily load series.

    ``method``: ``ewma`` (Williams 2017, recommended -- it decays old load smoothly instead of
    dropping it off a cliff at day 28) or ``rolling`` (the original Gabbett formulation).

    A ratio computed from fewer than :data:`CHRONIC_DAYS` days of history is reported as
    ``insufficient_history`` and must not gate anything: for a brand-new runner the chronic load
    starts at literally zero, which makes the ratio explode on the first easy jog. This is a real
    and well-known defect of applying ACWR to beginners -- during the first four weeks the plan
    uses :func:`ramp_rate` and absolute caps instead.
    """
    n = len(daily_loads)
    if method == "ewma":
        a = ewma_load(daily_loads[-ACUTE_DAYS:] if n >= ACUTE_DAYS else daily_loads, ACUTE_DAYS)
        c = ewma_load(daily_loads, CHRONIC_DAYS)
    elif method == "rolling":
        a = statistics.fmean(daily_loads[-ACUTE_DAYS:]) if n else 0.0
        c = statistics.fmean(daily_loads[-CHRONIC_DAYS:]) if n else 0.0
    else:
        raise ValueError(f"unknown method {method!r}")

    if n < CHRONIC_DAYS:
        return AcwrResult(a, c, (a / c if c > 0 else 0.0), "insufficient_history", method, n,
                          note=(f"only {n} of {CHRONIC_DAYS} days of history -- ratio is not "
                                "meaningful yet; absolute caps govern instead"))
    if c <= 0:
        return AcwrResult(a, c, 0.0, "insufficient_history", method, n,
                          note="no chronic load to compare against")

    ratio = a / c
    if ratio < ACWR_SWEET_LOW:
        band = "detraining"
    elif ratio <= ACWR_SWEET_HIGH:
        band = "optimal"
    elif ratio <= ACWR_HARD_CAP:
        band = "caution"
    else:
        band = "danger"
    return AcwrResult(a, c, ratio, band, method, n, note=ACWR_CAUTION)


@dataclass
class MonotonyResult:
    monotony: float
    strain: float
    weekly_load: float
    flagged: bool
    note: str = ""

    def to_dict(self) -> dict:
        return {"monotony": round(self.monotony, 2), "strain": round(self.strain, 1),
                "weekly_load": round(self.weekly_load, 1), "flagged": self.flagged,
                "note": self.note}


def monotony_strain(week_loads: Sequence[float]) -> MonotonyResult:
    """Foster monotony and strain for one week of daily loads (include rest days as 0).

    Monotony rewards *variation*: a week of seven identical medium runs scores worse than the same
    total split into hard days and genuine rest. For a runner with an erratic shift schedule the
    practical reading is inverted from the usual one -- their risk is rarely monotony, it is the
    Saturday where everything gets crammed in.
    """
    loads = list(week_loads)
    total = sum(loads)
    if len(loads) < 2:
        return MonotonyResult(0.0, 0.0, total, False, "need at least 2 days")
    sd = statistics.pstdev(loads)
    if sd == 0:
        # Zero variance is the *most* monotonous week possible, not an edge case to be excused.
        # Reporting inf for monotony is mathematically right, but the flag and the strain figure
        # must still behave: substituting a finite sentinel keeps strain comparable and, crucially,
        # keeps the warning switched on. Failing to flag this was a real bug -- seven identical
        # sessions is precisely the pattern Foster's monotony measure exists to catch.
        mono = float("inf") if total > 0 else 0.0
        mono_for_strain = _MONOTONY_SENTINEL if total > 0 else 0.0
    else:
        mono = statistics.fmean(loads) / sd
        mono_for_strain = mono
    strain = total * mono_for_strain
    flagged = total > 0 and (math.isinf(mono) or mono > MONOTONY_WARN)
    note = ("Every day looks the same -- add a real rest day and make the hard days harder."
            if flagged else "")
    return MonotonyResult(mono, strain, total, flagged, note)


def weekly_totals(loads: Sequence[DailyLoad]) -> Dict[date, float]:
    """Sum load by ISO week, keyed by that week's Monday."""
    out: Dict[date, float] = {}
    for dl in loads:
        monday = dl.day - timedelta(days=dl.day.weekday())
        out[monday] = out.get(monday, 0.0) + dl.load
    return dict(sorted(out.items()))


def ramp_rate(this_week: float, last_week: float) -> float:
    """Week-over-week fractional change. ``0.10`` = 10% more than last week.

    Returns 0.0 when last week was zero -- a first week of training has no ramp rate, and
    reporting infinity there would make every guard downstream trip on day one.
    """
    if last_week <= 0:
        return 0.0
    return this_week / last_week - 1.0
