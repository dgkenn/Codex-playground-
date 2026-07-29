"""Progress tracking, pain surveillance, and the motivation layer that is not a streak.

Everything in this module was taken from a teardown of what existing running apps do well and badly,
then narrowed to what a single self-coached user actually needs.

**Borrowed deliberately**

* **A pain and injury log with trend detection** (Final Surge's PAIR report). Logging pain location,
  level and duration lets a pattern be caught while it is still a pattern rather than an injury.
  This is the cheapest high-value feature available to someone with no running background, and it is
  the one that most directly serves the goal of getting to a start line.
* **Training status as a two-axis classifier** (Garmin's Training Status, minus the proprietary
  parts). Load trend crossed with fitness trend gives a plain-English label, and it is implementable
  from TRIMP and an efficiency-factor trend without needing anyone's EPOC model.
* **Recency-weighted readiness** (Garmin Training Readiness, WHOOP Strain Coach). Last night matters
  more than last month. Already implemented in :mod:`marathon_engine.readiness`.
* **Rest-aware consistency instead of streaks** (Gentler Streak's "Activity Path"). A consecutive-day
  streak is a mechanism that rewards training when the body says rest, which is the exact failure
  this whole system exists to prevent. :func:`consistency` therefore scores *adherence to the plan
  including its rest days*, and a rest day taken as planned counts as compliance rather than
  breaking anything.
* **Racing your past self on a repeated route** (Apple Watch's Race Route). Self-competition without
  a leaderboard, which is the only competitive framing that makes sense for a solo user.
* **Explainability on every automated change** (the negative lesson from TrainAsONE's black box).
  Every adaptation in this engine returns its reason as a first-class field, not a log line.

**Deliberately not built**

Social feeds, kudos, leaderboards, follower counts, badges, consecutive-day streaks, subscription
upsells, or anything that makes the app's engagement a goal in itself. There is one user. The only
metric that matters is whether he gets to a marathon start line uninjured.

One number worth designing against: large-cohort fitness-app data shows adherence dropping off
steeply, with a pronounced cliff around three to four months in -- which for this plan lands squarely
in the middle of base building, the least externally rewarding phase. :func:`progress_narrative`
exists specifically to make that stretch legible, by showing the athlete the physiological
improvements they cannot feel.

Pure functions; no I/O.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "PainEntry", "PainTrend", "pain_trend", "TrainingStatus", "training_status",
    "consistency", "ConsistencyResult", "RouteEffort", "compare_route_efforts",
    "progress_narrative", "PAIN_ESCALATION_DAYS", "ADHERENCE_CLIFF_WEEKS",
]

#: A pain report at the same site on this many days inside a fortnight is a pattern, not a niggle.
PAIN_ESCALATION_DAYS = 3

#: Where app adherence typically falls off, and where this plan's least rewarding phase sits.
ADHERENCE_CLIFF_WEEKS = 14


# ----------------------------------------------------------------------------------------
# Pain surveillance
# ----------------------------------------------------------------------------------------


@dataclass
class PainEntry:
    """One pain report. ``site`` should be a stable label so entries can be grouped."""
    day: date
    site: str                       # e.g. "left_achilles", "right_shin", "left_knee_anterior"
    level_0_10: int
    #: When it hurts -- this is the field that distinguishes a nuisance from a bone problem.
    timing: str = "during_run"      # during_run | after_run | next_morning | constant
    duration_min: Optional[float] = None
    #: True when the pain is at one identifiable POINT rather than diffuse. Focal bone pain that
    #: worsens with loading is the presentation of a stress injury.
    focal: bool = False
    worsens_during_run: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return {"day": self.day.isoformat(), "site": self.site, "level": self.level_0_10,
                "timing": self.timing, "focal": self.focal,
                "worsens_during_run": self.worsens_during_run, "notes": self.notes}


@dataclass
class PainTrend:
    site: str
    entries: int
    max_level: int
    mean_level: float
    days_span: int
    escalating: bool
    verdict: str            # watch | hold_volume | stop_and_assess | urgent
    message: str = ""
    actions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"site": self.site, "entries": self.entries, "max_level": self.max_level,
                "mean_level": round(self.mean_level, 1), "days_span": self.days_span,
                "escalating": self.escalating, "verdict": self.verdict,
                "message": self.message, "actions": self.actions}


def pain_trend(entries: Sequence[PainEntry], *, as_of: Optional[date] = None,
               window_days: int = 14) -> List[PainTrend]:
    """Group pain reports by site and classify each one's trajectory.

    The escalation logic is what makes this worth having. A single 2/10 ache after a long run is
    noise. The same site three times in a fortnight, or a rising level, or pain that is **focal** or
    **present the next morning**, is a pattern -- and patterns are what you can still act on.

    The two fields that carry the most weight are deliberately not the pain score:

    * ``focal`` -- a specific point of bone tenderness is a different problem from a diffuse ache,
      and it escalates straight to stopping regardless of how mild it feels.
    * ``timing == "next_morning"`` -- next-day pain is the single most informative signal in
      overuse injury and the one most often dismissed, because by the time you are running again it
      has usually eased off.
    """
    if not entries:
        return []
    end = as_of or max(e.day for e in entries)
    start = end - timedelta(days=window_days - 1)
    recent = [e for e in entries if start <= e.day <= end]
    by_site: Dict[str, List[PainEntry]] = {}
    for e in recent:
        by_site.setdefault(e.site, []).append(e)

    out: List[PainTrend] = []
    for site, es in sorted(by_site.items()):
        es.sort(key=lambda x: x.day)
        levels = [e.level_0_10 for e in es]
        span = (es[-1].day - es[0].day).days + 1
        # Escalating if the second half of the window is worse than the first.
        escalating = False
        if len(levels) >= 3:
            mid = len(levels) // 2
            escalating = statistics.fmean(levels[mid:]) > statistics.fmean(levels[:mid]) + 0.5
        any_focal = any(e.focal for e in es)
        any_next_morning = any(e.timing == "next_morning" for e in es)
        any_worsening = any(e.worsens_during_run for e in es)

        verdict, message, actions = "watch", "", []
        if any_focal:
            verdict = "urgent"
            message = (f"Pain at a single point on the {site.replace('_', ' ')}. Focal bone "
                       "tenderness that worsens with loading is how a stress injury presents, and "
                       "it does not need to be severe to be serious. Stop running and get it "
                       "assessed before the next run.")
            actions = ["Stop running now -- do not 'test it' with an easy run.",
                       "Get it assessed. A stress reaction caught early is a few weeks; a stress "
                       "fracture run through is a few months.",
                       "Cross-train without impact in the meantime if it is pain-free."]
        elif max(levels) > 5:
            verdict = "stop_and_assess"
            message = (f"Pain reached {max(levels)}/10 at the {site.replace('_', ' ')}. Above 5/10 "
                       "the rule is stop, every time.")
            actions = ["No running until it is below 3/10 at rest and during walking.",
                       "Then restart from the walk-jog ladder rather than from your previous volume."]
        elif escalating or len(es) >= PAIN_ESCALATION_DAYS or any_next_morning or any_worsening:
            verdict = "hold_volume"
            why = []
            if escalating:
                why.append("it is getting worse across the fortnight")
            if len(es) >= PAIN_ESCALATION_DAYS:
                why.append(f"it has come up {len(es)} times in {span} days")
            if any_next_morning:
                why.append("it is there the morning after, which is the signal that matters most")
            if any_worsening:
                why.append("it worsens as the run goes on rather than warming up")
            message = (f"The {site.replace('_', ' ')} is a pattern rather than a niggle: "
                       + ", and ".join(why) + ".")
            actions = ["Volume holds where it is -- no increases until two clean weeks.",
                       "Drop the quality session; keep easy running only if it is pain-free "
                       "during AND the next morning.",
                       "If it has not settled in ten days, get it looked at rather than "
                       "continuing to manage it yourself."]
        else:
            message = (f"Occasional mild discomfort at the {site.replace('_', ' ')} "
                       f"(max {max(levels)}/10). Within the acceptable 0-2 band -- keep logging it.")
            actions = ["Keep logging. The log is what turns this into a pattern you can see."]

        out.append(PainTrend(site=site, entries=len(es), max_level=max(levels),
                             mean_level=statistics.fmean(levels), days_span=span,
                             escalating=escalating, verdict=verdict, message=message,
                             actions=actions))
    # Most serious first.
    order = {"urgent": 0, "stop_and_assess": 1, "hold_volume": 2, "watch": 3}
    return sorted(out, key=lambda t: order[t.verdict])


# ----------------------------------------------------------------------------------------
# Training status
# ----------------------------------------------------------------------------------------


@dataclass
class TrainingStatus:
    label: str
    load_trend: str          # rising | steady | falling
    fitness_trend: str       # improving | flat | declining
    message: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {"label": self.label, "load_trend": self.load_trend,
                "fitness_trend": self.fitness_trend, "message": self.message,
                "detail": self.detail}


def training_status(acute_load: float, chronic_load: float,
                    ef_recent: Optional[float], ef_baseline: Optional[float],
                    *, weeks_training: int = 0) -> TrainingStatus:
    """Two-axis status: what load is doing, crossed with what fitness is doing.

    This is Garmin's Training Status idea without the proprietary machinery. Load trend comes from
    the acute-versus-chronic comparison already computed in :mod:`marathon_engine.load`; fitness
    trend comes from the efficiency factor (speed per heartbeat) against its baseline, which is the
    cleanest fitness signal available from a heart-rate monitor alone.

    The combination that matters most is **rising load with declining fitness** -- that is the
    non-functional overreaching pattern, and it is the one case where the honest advice is to do
    less rather than more.
    """
    ratio = (acute_load / chronic_load) if chronic_load > 0 else 0.0
    if chronic_load <= 0 or weeks_training < 3:
        return TrainingStatus(
            label="Establishing baseline", load_trend="steady", fitness_trend="flat",
            message="Not enough history yet to say anything meaningful.",
            detail="Status needs about three weeks of consistent training before it means "
                   "anything. Until then, consistency is the only thing worth tracking.")

    load_trend = "rising" if ratio > 1.10 else "falling" if ratio < 0.85 else "steady"

    if ef_recent is None or ef_baseline is None or ef_baseline <= 0:
        fitness_trend = "flat"
    else:
        change = ef_recent / ef_baseline - 1.0
        fitness_trend = "improving" if change > 0.02 else "declining" if change < -0.02 else "flat"

    table: Dict[Tuple[str, str], Tuple[str, str, str]] = {
        ("rising", "improving"): (
            "Productive", "Load is climbing and your fitness is climbing with it.",
            "This is what a working block looks like. Keep the easy days easy -- this state is "
            "usually lost by making them harder, not by doing too little."),
        ("rising", "flat"): (
            "Building", "Load is up; fitness has not moved yet.",
            "Normal. Adaptation lags load by a couple of weeks, so hold the current volume rather "
            "than adding more in search of a faster response."),
        ("rising", "declining"): (
            "Overreaching", "Load is up and fitness is going down.",
            "This is the pattern that matters. Doing more will not fix it. Take a cutback week, "
            "look hard at sleep and fuelling, and re-check in ten days. If it persists, the answer "
            "is a genuine rest week rather than a lighter one."),
        ("steady", "improving"): (
            "Productive", "Steady load, improving fitness.",
            "The most efficient state there is -- you are getting fitter without adding stress. "
            "There is no need to change anything."),
        ("steady", "flat"): (
            "Maintaining", "Load and fitness are both flat.",
            "Fine for a holding phase. If you want progress, the next step is a small volume "
            "increase, not a harder session."),
        ("steady", "declining"): (
            "Unproductive", "Load is steady but fitness is slipping.",
            "Usually life rather than training: sleep, illness, stress, or under-fuelling. Check "
            "ferritin and energy availability before changing the plan."),
        ("falling", "improving"): (
            "Peaking", "Load is coming down and fitness is up.",
            "The taper working as intended. Do not add anything back."),
        ("falling", "flat"): (
            "Recovery", "Load is down, fitness holding.",
            "A recovery block doing its job. Fitness is far more durable than people fear."),
        ("falling", "declining"): (
            "Detraining", "Load and fitness both falling.",
            "Expected after time off. Aerobic fitness comes back quickly; tissue tolerance does "
            "not, so rebuild volume rather than pace first."),
    }
    label, msg, detail = table[(load_trend, fitness_trend)]
    return TrainingStatus(label=label, load_trend=load_trend, fitness_trend=fitness_trend,
                          message=msg, detail=detail)


# ----------------------------------------------------------------------------------------
# Consistency (the anti-streak)
# ----------------------------------------------------------------------------------------


@dataclass
class ConsistencyResult:
    weeks_scored: int
    adherence: float                 # 0..1, planned sessions completed
    rest_compliance: float           # 0..1, planned rest days actually rested
    band: str                        # on_path | slipping | off_path | overreaching
    message: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {"weeks_scored": self.weeks_scored, "adherence": round(self.adherence, 2),
                "rest_compliance": round(self.rest_compliance, 2), "band": self.band,
                "message": self.message, "detail": self.detail}


def consistency(planned_sessions: Sequence[int], completed_sessions: Sequence[int],
                planned_rest_days: Sequence[int] = (),
                extra_sessions: Sequence[int] = ()) -> ConsistencyResult:
    """Adherence *including* rest days, deliberately not a streak.

    A consecutive-day streak rewards training when the body says rest, which is precisely the
    behaviour every other module here is built to prevent. So the score has two components and
    **both** can be violated: skipping sessions lowers adherence, and training on planned rest days
    lowers rest compliance. Doing extra is not a bonus -- it shows up as ``overreaching``.

    Each argument is one entry per week.
    """
    n = min(len(planned_sessions), len(completed_sessions))
    if n == 0:
        return ConsistencyResult(0, 0.0, 1.0, "on_path", "No weeks scored yet.")
    planned_total = sum(planned_sessions[:n])
    done_total = sum(completed_sessions[:n])
    adherence = (done_total / planned_total) if planned_total else 0.0

    rest_planned = sum(planned_rest_days[:n]) if planned_rest_days else 0
    extra = sum(extra_sessions[:n]) if extra_sessions else 0
    rest_compliance = 1.0 if not rest_planned else max(0.0, 1.0 - extra / rest_planned)

    if extra > 0 and adherence >= 0.95 and rest_compliance < 0.8:
        band = "overreaching"
        msg = f"You did {extra} unplanned session(s) on planned rest days."
        detail = ("Rest days are not gaps in the plan, they are part of it -- adaptation happens "
                  "during them. Extra sessions on rest days is the one form of 'good compliance' "
                  "this app will push back on.")
    elif adherence >= 0.85:
        band = "on_path"
        msg = f"{adherence*100:.0f}% of planned sessions done."
        detail = ("This is the number that actually predicts whether you reach a start line -- more "
                  "than peak weekly volume, more than any single session.")
    elif adherence >= 0.65:
        band = "slipping"
        msg = f"{adherence*100:.0f}% of planned sessions done."
        detail = ("Worth a look at whether the plan fits your rota rather than at your discipline. "
                  "A plan you complete 90% of beats a better plan you complete 60% of.")
    else:
        band = "off_path"
        msg = f"{adherence*100:.0f}% of planned sessions done over {n} weeks."
        detail = ("The plan is probably wrong for your life right now, not the other way round. "
                  "Drop to two runs a week and rebuild from something you will actually do -- that "
                  "is a legitimate adjustment, not a concession.")
    return ConsistencyResult(weeks_scored=n, adherence=adherence,
                             rest_compliance=rest_compliance, band=band,
                             message=msg, detail=detail)


# ----------------------------------------------------------------------------------------
# Racing your past self
# ----------------------------------------------------------------------------------------


@dataclass
class RouteEffort:
    day: date
    route_id: str
    distance_km: float
    duration_s: float
    mean_hr: Optional[float] = None
    mean_cadence: Optional[float] = None
    temp_c: Optional[float] = None

    @property
    def pace_sec_km(self) -> float:
        return self.duration_s / self.distance_km if self.distance_km else 0.0


def compare_route_efforts(efforts: Sequence[RouteEffort]) -> Optional[Dict[str, object]]:
    """Compare the latest effort on a route with the best and first previous efforts.

    Self-competition on a repeated route is the one competitive framing worth having for a solo
    runner: no leaderboard, no comparison to strangers, just evidence against your own past.

    The honest part is the caveat: the *right* comparison for a beginner is usually heart rate at
    the same pace, not pace itself. Getting round the same loop at the same speed for ten fewer
    beats a minute is a bigger improvement than running it thirty seconds quicker while working
    harder, and it is the improvement that actually transfers to a marathon.
    """
    if len(efforts) < 2:
        return None
    by_route: Dict[str, List[RouteEffort]] = {}
    for e in efforts:
        by_route.setdefault(e.route_id, []).append(e)
    route_id, group = max(by_route.items(), key=lambda kv: len(kv[1]))
    if len(group) < 2:
        return None
    group.sort(key=lambda e: e.day)
    latest, first = group[-1], group[0]
    previous = group[:-1]
    best = min(previous, key=lambda e: e.pace_sec_km)

    out: Dict[str, object] = {
        "route_id": route_id,
        "efforts": len(group),
        "latest_pace_sec_km": round(latest.pace_sec_km, 1),
        "best_previous_pace_sec_km": round(best.pace_sec_km, 1),
        "vs_best_sec_km": round(latest.pace_sec_km - best.pace_sec_km, 1),
        "vs_first_sec_km": round(latest.pace_sec_km - first.pace_sec_km, 1),
        "notes": [],
    }
    notes: List[str] = []
    if latest.mean_hr and first.mean_hr:
        hr_delta = latest.mean_hr - first.mean_hr
        pace_delta = latest.pace_sec_km - first.pace_sec_km
        out["vs_first_hr_delta"] = round(hr_delta, 1)
        if hr_delta < -3 and pace_delta <= 5:
            notes.append(f"Same loop, same pace, {abs(hr_delta):.0f} fewer beats per minute than "
                         "your first time round it. That is the improvement that matters -- it is "
                         "aerobic fitness rather than effort, and it is what carries over to long "
                         "distances.")
        elif pace_delta < -10 and hr_delta > 5:
            notes.append(f"{abs(pace_delta):.0f} s/km quicker, but at {hr_delta:.0f} bpm higher. "
                         "That is mostly extra effort rather than extra fitness. Not a bad thing, "
                         "but do not read it as progress.")
        elif pace_delta < -10 and abs(hr_delta) <= 5:
            notes.append(f"{abs(pace_delta):.0f} s/km quicker at the same heart rate. Unambiguous "
                         "progress.")
    if latest.temp_c is not None and first.temp_c is not None and abs(latest.temp_c - first.temp_c) > 8:
        notes.append(f"Conditions differ by {abs(latest.temp_c - first.temp_c):.0f} C between these "
                     "runs, which moves heart rate at a given pace by several beats on its own. "
                     "Compare cautiously.")
    out["notes"] = notes
    return out


# ----------------------------------------------------------------------------------------
# The narrative
# ----------------------------------------------------------------------------------------


def progress_narrative(weeks_training: int, *, ef_change_pct: Optional[float] = None,
                       hr_at_fixed_pace_delta: Optional[float] = None,
                       longest_run_km: Optional[float] = None,
                       first_longest_run_km: Optional[float] = None,
                       vdot_now: Optional[float] = None,
                       vdot_start: Optional[float] = None) -> Dict[str, object]:
    """Make invisible progress visible, targeted at the point where people quit.

    Adherence data shows a steep drop-off around three to four months in, which for this plan lands
    in the middle of base building -- the phase with the least external reward, where the sessions
    stop obviously getting harder and no race is imminent. The counter is not encouragement, it is
    *evidence*: showing the athlete the physiological changes they cannot feel from inside.
    """
    items: List[str] = []
    if hr_at_fixed_pace_delta is not None and hr_at_fixed_pace_delta < -2:
        items.append(f"Your heart rate at the same pace has dropped "
                     f"{abs(hr_at_fixed_pace_delta):.0f} bpm. Same speed, less work -- this is the "
                     "single clearest sign the aerobic system is adapting, and you cannot feel it "
                     "happening.")
    if ef_change_pct is not None and ef_change_pct > 2:
        items.append(f"Efficiency factor is up {ef_change_pct:.0f}%: you are covering more ground "
                     "per heartbeat than when you started.")
    if longest_run_km and first_longest_run_km and longest_run_km > first_longest_run_km:
        items.append(f"Your longest run has gone from {first_longest_run_km:.1f} km to "
                     f"{longest_run_km:.1f} km.")
    if vdot_now and vdot_start and vdot_now > vdot_start:
        items.append(f"Estimated VDOT {vdot_start:.0f} to {vdot_now:.0f}.")

    warning = None
    if ADHERENCE_CLIFF_WEEKS - 3 <= weeks_training <= ADHERENCE_CLIFF_WEEKS + 6:
        warning = (
            f"You are {weeks_training} weeks in. This is statistically where people stop -- the "
            "novelty is gone, base building is not dramatic, and there is no race close enough to "
            "pull you along. Nothing is wrong with your plan. The base you are building now is what "
            "the marathon is actually made of, and it is the least visible part of the whole "
            "process. If you need a target, put a 5K or 10K on the calendar.")
    return {
        "weeks_training": weeks_training,
        "highlights": items or ["Not enough history yet to show a trend. Keep going."],
        "adherence_cliff_warning": warning,
    }
