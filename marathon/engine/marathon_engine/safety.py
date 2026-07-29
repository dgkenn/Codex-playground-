"""Pre-participation screening, bone-loading accounting, and the hydration/medication rules.

This module exists because an adversarial review of the rest of this engine found three gaps, each
of which mattered more than anything the engine already did well:

1. **No pre-participation screening.** The plan was prescribing a maximal time trial, a deliberate
   all-out HRmax capture, and eventually a marathon to a previously sedentary adult, with no
   screening step at all.
2. **No bone-loading model.** Bone remodels on a timescale of months. HRV, ACWR and readiness are
   all blind to it, so an athlete can be "green" every single morning and still be accumulating a
   tibial stress injury. This is the single highest-consequence novice running injury and the one
   the volume caps are really protecting against, so it needs its own accounting rather than being
   an implicit hope.
3. **No exercise-associated hyponatraemia guidance.** EAH disproportionately affects *slow
   first-time marathoners who over-drink* -- precisely this athlete's risk profile -- and it is one
   of the few genuinely life-threatening things that happens in mass-participation marathons. An app
   that prompts fluid intake without addressing it is actively increasing risk.

Sources
-------
* **Screening** — ACSM's preparticipation health screening algorithm (Riebe et al. 2015,
  *Med Sci Sports Exerc* 47:2473), which replaced the old blanket age/risk-factor referral with a
  logic based on current activity level, known disease, and symptoms. The point of the 2015 revision
  was to *reduce* unnecessary barriers to exercise, so this module aims to identify the small number
  of people who need clearance rather than to send everyone to a doctor.
* **Marathon cardiac risk, for calibration not alarm** — Kim et al. 2012, *N Engl J Med* 366:130
  (RACER): cardiac arrest in 1 per ~184,000 marathon/half-marathon participants, concentrated in
  marathon (not half) and in men, most commonly hypertrophic cardiomyopathy or coronary disease.
  The absolute risk is very low; the honest framing is that it is low *and* that exertional
  symptoms are the thing that must never be ignored.
* **Bone stress injury** — Warden, Davis & Fredericson 2014, *J Orthop Sports Phys Ther* 44:749;
  Bennell & Brukner on tibial stress fracture epidemiology in runners; Nielsen et al. on
  progression and novice injury. Bone adapts to *strain magnitude and rate*, and the adaptation lag
  is months rather than weeks -- the mismatch with cardiorespiratory fitness (2-3 weeks) is the
  mechanism. Novice runners' bone stress injuries cluster in the first few months of running.
* **Single-run progression** — the Garmin-RUNSAFE cohort (5,205 runners, 588,071 sessions) found
  injury hazard elevated for a single run exceeding the previous 30 days' longest run, rising
  continuously from small progressions upward. The authors' own conclusion is that there is **no
  safe threshold**, which is why :func:`single_run_progression` returns a graded caution rather
  than a pass/fail at 10%.
* **Hyponatraemia** — Hew-Butler et al. 2015, *Clin J Sport Med* 25:303 (3rd International
  Exercise-Associated Hyponatremia Consensus): drink to thirst; the primary risk factor is
  overdrinking hypotonic fluid; slower finishers, smaller body mass and NSAID use are associated.
  Rosner & Kirven 2007 on the pathophysiology.
* **NSAIDs** — NSAID use during prolonged endurance exercise is associated with hyponatraemia and
  with acute kidney injury, and does not improve performance. This is the one piece of advice in
  this module the athlete (a physician) will already know, and it is included because knowing it and
  remembering it at 30 km with a sore knee are different things.
* **Caffeine** — 3-6 mg/kg, 30-60 min pre-exercise, is among the best-evidenced ergogenic aids
  (Guest et al. 2021, *J Int Soc Sports Nutr* 18:1).
* **Iron and vitamin D** — worth checking in a shift worker ramping aerobic volume; low ferritin is
  common, symptomatically silent, and directly limits adaptation.

Pure functions; no I/O. **Advisory only. This is not a medical device and does not diagnose.**
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ScreeningAnswers", "ScreeningResult", "screen_participant",
    "BoneLoadState", "bone_load", "single_run_progression", "clamp_single_run",
    "SPIKE_DEFAULT_CLAMP", "SPIKE_CLAMP_IN_BONE_WINDOW", "bone_window_increment_factor",
    "hydration_plan", "MEDICATION_WARNINGS", "SUPPLEMENT_CHECKS",
    "RED_FLAG_SYMPTOMS", "return_to_run",
    "BONE_ADAPTATION_WEEKS", "BONE_LOAD_SPIKE_RATIO", "NEW_RUNNER_BONE_WINDOW_WEEKS",
]

# ----------------------------------------------------------------------------------------
# Pre-participation screening
# ----------------------------------------------------------------------------------------


@dataclass
class ScreeningAnswers:
    """The ACSM-style screening inputs. All default to the *safe* interpretation (unknown = ask)."""
    currently_exercising_regularly: Optional[bool] = None    # >=30 min moderate, >=3 d/wk, >=3 mo
    known_cardiovascular_disease: Optional[bool] = None
    known_metabolic_disease: Optional[bool] = None           # type 1 or 2 diabetes
    known_renal_disease: Optional[bool] = None
    #: Signs/symptoms suggestive of cardiovascular disease, at rest OR on exertion.
    symptoms_chest_discomfort: bool = False
    symptoms_dyspnoea_unusual: bool = False
    symptoms_dizziness_syncope: bool = False
    symptoms_palpitations: bool = False
    symptoms_ankle_oedema: bool = False
    symptoms_claudication: bool = False
    #: Other things that change the plan rather than blocking it.
    family_history_sudden_death_under_50: bool = False
    pregnant: bool = False
    current_musculoskeletal_pain: bool = False
    smoker: bool = False
    bp_known_high: bool = False
    on_beta_blocker: bool = False

    @property
    def any_symptoms(self) -> bool:
        return any([self.symptoms_chest_discomfort, self.symptoms_dyspnoea_unusual,
                    self.symptoms_dizziness_syncope, self.symptoms_palpitations,
                    self.symptoms_ankle_oedema, self.symptoms_claudication])

    @property
    def any_known_disease(self) -> bool:
        return bool(self.known_cardiovascular_disease or self.known_metabolic_disease
                    or self.known_renal_disease)


@dataclass
class ScreeningResult:
    clearance: str            # "proceed" | "medical_clearance_first" | "urgent_review"
    can_start_training: bool
    can_do_maximal_test: bool
    reasons: List[str] = field(default_factory=list)
    advisories: List[str] = field(default_factory=list)
    headline: str = ""

    def to_dict(self) -> dict:
        return {"clearance": self.clearance, "can_start_training": self.can_start_training,
                "can_do_maximal_test": self.can_do_maximal_test, "reasons": self.reasons,
                "advisories": self.advisories, "headline": self.headline}


def screen_participant(a: ScreeningAnswers) -> ScreeningResult:
    """Apply the ACSM 2015 screening logic. Advisory; the athlete is a physician, not a patient.

    The 2015 revision deliberately *lowered* the barrier to starting exercise, because the risk of
    not exercising is larger than the risk of exercising for almost everyone. So this returns
    ``proceed`` for the common case and reserves referral for symptoms and known disease.

    Note the separation of ``can_start_training`` from ``can_do_maximal_test``. These are genuinely
    different risks: starting a walk-jog programme is safe for nearly everyone, while a deliberate
    maximal effort is the highest-risk single thing this plan ever asks for. The plan is built so
    that no maximal test happens for months, which means clearance can be sorted out long before it
    is needed.
    """
    reasons: List[str] = []
    advisories: List[str] = []

    if a.any_symptoms:
        symptoms = [name.replace("symptoms_", "").replace("_", " ")
                    for name, val in (
                        ("symptoms_chest_discomfort", a.symptoms_chest_discomfort),
                        ("symptoms_dyspnoea_unusual", a.symptoms_dyspnoea_unusual),
                        ("symptoms_dizziness_syncope", a.symptoms_dizziness_syncope),
                        ("symptoms_palpitations", a.symptoms_palpitations),
                        ("symptoms_ankle_oedema", a.symptoms_ankle_oedema),
                        ("symptoms_claudication", a.symptoms_claudication)) if val]
        reasons.append(f"Reported symptom(s) that need explaining before exertion: "
                       f"{', '.join(symptoms)}.")
        return ScreeningResult(
            clearance="urgent_review", can_start_training=False, can_do_maximal_test=False,
            reasons=reasons,
            advisories=["Do not start or continue a training programme until these have been "
                        "assessed. Exertional chest discomfort, unusual breathlessness, and "
                        "exertional dizziness or syncope are the three that matter most."],
            headline="Get these symptoms assessed before training")

    if a.any_known_disease:
        which = [n for n, v in (("cardiovascular", a.known_cardiovascular_disease),
                                ("metabolic", a.known_metabolic_disease),
                                ("renal", a.known_renal_disease)) if v]
        reasons.append(f"Known {', '.join(which)} disease: ACSM recommends medical clearance "
                       "before starting or intensifying exercise.")
        return ScreeningResult(
            clearance="medical_clearance_first", can_start_training=False,
            can_do_maximal_test=False, reasons=reasons,
            advisories=["Light-to-moderate activity is usually encouraged even with known disease; "
                        "the clearance step is about the *progression* this plan involves."],
            headline="Medical clearance needed before starting")

    if a.currently_exercising_regularly is None:
        advisories.append("Activity history not recorded -- the ramp will start conservatively.")

    if a.pregnant:
        advisories.append("Pregnancy changes the plan substantially (target heart rates, "
                          "thermoregulation, and race goals). Get obstetric input and expect the "
                          "marathon timeline to move.")
    if a.family_history_sudden_death_under_50:
        advisories.append("Family history of sudden death under 50 is worth raising with a "
                          "clinician before any maximal effort, even with no symptoms of your own.")
    if a.bp_known_high:
        advisories.append("Known raised blood pressure: worth having it controlled and rechecked "
                          "as volume climbs. Aerobic training will usually help it.")
    if a.on_beta_blocker:
        advisories.append("Beta blockade blunts heart rate at every intensity, so HR zones derived "
                          "from an age formula will be wrong. The measured ramp test matters more "
                          "than usual, and RPE and the talk test should lead.")
    if a.smoker:
        advisories.append("Smoking is the single largest modifiable factor here, dwarfing anything "
                          "in the training plan.")
    if a.current_musculoskeletal_pain:
        advisories.append("Existing musculoskeletal pain: get it assessed first. Starting a running "
                          "programme on an unexplained painful joint is how a small problem becomes "
                          "the reason you stop.")

    advisories.append(
        "For calibration rather than alarm: cardiac arrest during a marathon or half marathon "
        "occurs in roughly 1 per 184,000 participants (Kim et al., NEJM 2012). The absolute risk is "
        "very low. The rule that follows from it is not 'do not run' -- it is 'never train through "
        "exertional chest discomfort, unusual breathlessness, or feeling faint'.")

    return ScreeningResult(
        clearance="proceed", can_start_training=True, can_do_maximal_test=True,
        reasons=["No symptoms, no known cardiovascular, metabolic or renal disease."],
        advisories=advisories, headline="Cleared to start")


#: Symptoms that stop a run immediately, at any point, regardless of what the plan says. Mirrors
#: :func:`marathon_engine.realtime.safety_check` so the in-run and out-of-run lists cannot drift.
RED_FLAG_SYMPTOMS: Dict[str, str] = {
    "chest_pain": "Chest pain, pressure, or tightness on exertion. Stop and get assessed today.",
    "dyspnoea": "Breathlessness out of proportion to the effort. Stop.",
    "dizziness": "Light-headedness, feeling faint, or greying vision. Stop and sit down.",
    "palpitations": "A racing or irregular heartbeat that does not settle when you stop.",
    "focal_bone_pain": ("A specific POINT of bone pain that worsens with each step -- the classic "
                        "presentation of a stress fracture. Stop running; do not run again until "
                        "it has been assessed."),
    "calf_swelling": "A swollen, painful calf, especially if it hurts at rest. Needs assessment.",
    "confusion": ("Confusion, disorientation, or a headache with nausea late in a long run or race "
                  "-- consider both heat illness and hyponatraemia. Stop; do not drink large "
                  "volumes of plain water."),
}


# ----------------------------------------------------------------------------------------
# Bone loading
# ----------------------------------------------------------------------------------------

#: Bone takes roughly this long to complete a remodelling cycle and express adaptation. The number
#: is deliberately expressed in *months* of weeks: the point is the order of magnitude versus the
#: 2-3 weeks of cardiorespiratory adaptation, not a precise figure.
BONE_ADAPTATION_WEEKS = 16

#: Weeks from a runner's first ever run during which bone stress risk is elevated and the plan
#: should be maximally conservative regardless of how good the readiness numbers look.
NEW_RUNNER_BONE_WINDOW_WEEKS = 20

#: A single run this much larger than the previous 30 days' longest is a flagged spike.
#: NOT a safe/unsafe threshold -- see :func:`single_run_progression`.
BONE_LOAD_SPIKE_RATIO = 1.10


@dataclass
class BoneLoadState:
    """Cumulative impact-loading picture, which no other metric in this engine can see."""
    weeks_running: int
    cumulative_impact_km: float
    weeks_since_start_of_ramp: int
    in_high_risk_window: bool
    band: str                       # building | consolidating | established
    guidance: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"weeks_running": self.weeks_running,
                "cumulative_impact_km": round(self.cumulative_impact_km, 1),
                "in_high_risk_window": self.in_high_risk_window, "band": self.band,
                "guidance": self.guidance}


def bone_load(weekly_km_history: Sequence[float], *, weeks_running: Optional[int] = None
              ) -> BoneLoadState:
    """Track cumulative impact loading and flag the high-risk early window.

    Why this is separate from every other load metric here: TRIMP, ACWR and readiness are all
    *cardiovascular or autonomic*. Bone does not appear in any of them. A runner can pass every gate
    in :mod:`marathon_engine.plan`, feel excellent, show a rising HRV baseline, and still be
    twelve weeks into building a tibial stress fracture -- because bone strain accumulates and its
    adaptation lags months behind the fitness that lets you run further.

    The practical consequence encoded here is modest and specific: during the first
    :data:`NEW_RUNNER_BONE_WINDOW_WEEKS` weeks of running, prefer *frequency* over *session length*,
    keep surfaces varied, and treat any focal bone pain as a hard stop rather than a niggle.
    """
    weeks = weeks_running if weeks_running is not None else len(
        [w for w in weekly_km_history if w > 0])
    cumulative = float(sum(weekly_km_history))
    in_window = weeks < NEW_RUNNER_BONE_WINDOW_WEEKS

    if weeks < 8:
        band = "building"
    elif weeks < NEW_RUNNER_BONE_WINDOW_WEEKS:
        band = "consolidating"
    else:
        band = "established"

    guidance: List[str] = []
    if in_window:
        guidance.append(
            "While this window is armed the weekly increment cap is halved and single-run "
            "progression is disabled -- the plan grows more slowly than the numbers alone would "
            "justify, on purpose.")
    if in_window:
        guidance.append(
            f"You are {weeks} weeks into running, inside the ~{NEW_RUNNER_BONE_WINDOW_WEEKS}-week "
            "window where bone stress injuries cluster in new runners. Nothing in your heart-rate, "
            "HRV or load numbers can see bone -- it remodels over months, while your fitness "
            "improves in weeks, and that gap is the injury.")
        guidance.append("Practical version: spread the same volume over more runs rather than "
                        "fewer longer ones, vary the surface, and treat any pain at a single "
                        "POINT on a bone as a stop, not a niggle.")
    if weeks >= 8 and cumulative < 100:
        guidance.append("Cumulative volume is still low. Consistency over the next two months "
                        "does more for your durability than any single session can.")
    if band == "established":
        guidance.append("Past the highest-risk early window. The load caps stay, but the plan can "
                        "trust your structure more than it did.")
    return BoneLoadState(weeks_running=weeks, cumulative_impact_km=cumulative,
                         weeks_since_start_of_ramp=len(weekly_km_history),
                         in_high_risk_window=in_window, band=band, guidance=guidance)


#: Default clamp applied when a single run is flagged. A graded warning that the athlete can simply
#: dismiss is a warning that gets dismissed, so the planner clamps by default and says it did.
SPIKE_DEFAULT_CLAMP = 1.05
#: While the bone-vulnerable window is armed, no single-run progression at all.
SPIKE_CLAMP_IN_BONE_WINDOW = 1.00


def single_run_progression(planned_km: float, longest_run_last_30d: Optional[float],
                           *, in_bone_window: bool = False
                           ) -> Tuple[str, float, str]:
    """Grade a single run against the longest run of the previous 30 days.

    Returns ``(band, ratio, message)`` where band is ``ok`` / ``caution`` / ``high``.

    **There is deliberately no "safe" threshold here.** The Garmin-RUNSAFE cohort (5,205 runners,
    588,071 sessions) found injury hazard already elevated in the smallest progression band they
    examined and rising from there, and the authors use that result specifically to argue *against*
    the existence of a safe 10% cut-off. Encoding a threshold would therefore misrepresent the
    evidence, so this returns a graded caution whose message scales with the size of the jump.

    This guard catches something the weekly-volume cap structurally cannot: a week whose *total* is
    perfectly reasonable but which contains one run far longer than anything done recently. On a
    3-runs-per-week schedule that is a live risk, because the long run is a large fraction of the
    week by design.
    """
    if not longest_run_last_30d or longest_run_last_30d <= 0:
        return ("ok", 0.0,
                "No comparable run in the last 30 days, so there is nothing to compare against. "
                "Build up rather than jumping straight to the planned distance.")
    ratio = planned_km / longest_run_last_30d
    if ratio <= 1.0:
        return "ok", ratio, "No longer than your recent longest run."
    pct = (ratio - 1.0) * 100.0
    if ratio < BONE_LOAD_SPIKE_RATIO:
        return ("ok", ratio,
                f"{pct:.0f}% longer than your longest run in the last month. Modest, but note that "
                "the RUNSAFE data show risk rising continuously from small progressions -- there is "
                "no magic safe percentage, so keep the pace genuinely easy.")
    if ratio < 1.30:
        return ("caution", ratio,
                f"{pct:.0f}% longer than anything you have run in the last month. That is a real "
                "step up. Run it slower than you think you need to, and take walk breaks by choice "
                "rather than necessity.")
    return ("high", ratio,
            f"{pct:.0f}% longer than your longest run in the last month. This is the single-session "
            "spike pattern most strongly associated with injury in the RUNSAFE cohort. Split it, or "
            "cap it nearer your recent longest, and come back to this distance next week.")


def clamp_single_run(planned_km: float, longest_run_last_30d: Optional[float],
                     *, in_bone_window: bool = False,
                     allow_override: bool = False) -> Dict[str, object]:
    """Apply the spike guard as an actual limit, not just a warning.

    A graded caution the athlete can wave away is a caution that gets waved away, usually on the
    morning they feel good -- which is exactly the wrong day to allow a step up. So the planner
    clamps by default and reports that it did, with the original figure shown so nothing is hidden.

    ``allow_override`` lets a *caution*-band run through at its planned distance if the athlete
    explicitly insists. It deliberately does **not** apply in the ``high`` band or inside the
    bone-vulnerable window, because those are the two cases where the cost of being wrong is a
    stress injury rather than a hard week.
    """
    band, ratio, message = single_run_progression(planned_km, longest_run_last_30d,
                                                  in_bone_window=in_bone_window)
    if not longest_run_last_30d or longest_run_last_30d <= 0 or band == "ok":
        return {"band": band, "ratio": round(ratio, 3), "planned_km": round(planned_km, 1),
                "allowed_km": round(planned_km, 1), "clamped": False, "message": message}

    limit_ratio = SPIKE_CLAMP_IN_BONE_WINDOW if in_bone_window else SPIKE_DEFAULT_CLAMP
    allowed = longest_run_last_30d * limit_ratio
    if band == "caution" and allow_override and not in_bone_window:
        return {"band": band, "ratio": round(ratio, 3), "planned_km": round(planned_km, 1),
                "allowed_km": round(planned_km, 1), "clamped": False,
                "message": message + " Running it as planned at your explicit request."}
    if allowed >= planned_km:
        return {"band": band, "ratio": round(ratio, 3), "planned_km": round(planned_km, 1),
                "allowed_km": round(planned_km, 1), "clamped": False, "message": message}
    why = ("no single-run progression at all while the bone-vulnerable window is armed"
           if in_bone_window else
           f"capped at {limit_ratio:.2f}x your recent longest run")
    return {"band": band, "ratio": round(ratio, 3), "planned_km": round(planned_km, 1),
            "allowed_km": round(allowed, 1), "clamped": True,
            "message": (f"{message} Shortened from {planned_km:.1f} km to {allowed:.1f} km -- "
                        f"{why}. The distance is not lost; it comes back next week off a higher base.")}


# ----------------------------------------------------------------------------------------
# Hydration, medication, micronutrients
# ----------------------------------------------------------------------------------------


def hydration_plan(duration_min: float, wbgt_c: Optional[float] = None,
                   body_mass_kg: Optional[float] = None) -> Dict[str, object]:
    """Fluid guidance built around *not* over-drinking.

    Exercise-associated hyponatraemia is the risk this function exists to manage, and its profile
    matches this athlete almost exactly: it disproportionately affects **slow, first-time
    marathoners who drink more than they lose**, and it is one of the few genuinely
    life-threatening events in mass-participation racing. The 3rd International EAH Consensus
    (Hew-Butler et al. 2015) is unambiguous about the primary prevention strategy: **drink to
    thirst.** Not to a schedule, not "ahead of thirst", and not a fixed millilitres-per-hour target.

    A 4-to-5-hour first marathon plus enthusiastic aid-station drinking plus NSAIDs is the textbook
    setup, so the guidance gets firmer as duration rises, in the *opposite* direction from most
    apps' hydration prompts.
    """
    out: Dict[str, object] = {
        "primary_rule": "Drink to thirst. Thirst is a good regulator and beating it is the actual "
                        "risk here.",
        "do_not": [
            "Do not drink to a schedule or to a fixed millilitres-per-hour target.",
            "Do not drink at every aid station out of habit if you are not thirsty.",
            "Do not take NSAIDs before or during a long run or race.",
        ],
        "warning_signs": [
            "Weight GAIN over a long run or race -- the clearest sign of over-drinking.",
            "Headache with nausea, puffiness in hands or face, or confusion late in a long effort.",
            "Feeling worse the more you drink.",
        ],
        "notes": [],
    }
    notes: List[str] = []
    if duration_min >= 150:
        notes.append(
            "Past about two and a half hours, use a sodium-containing sports drink rather than "
            "plain water for most of your intake. Slow first-time marathoners who drink large "
            "volumes of plain water are the classic hyponatraemia presentation, and this is the "
            "single most useful change.")
        notes.append("If you can, weigh yourself before and after two long runs to learn your own "
                     "sweat rate. Losing 1-2% of body mass is normal and fine; *gaining* weight "
                     "means you drank too much.")
    if duration_min >= 90:
        notes.append("Carry fluid rather than relying on fountains, and practise drinking while "
                     "running -- it is a skill.")
    if wbgt_c is not None and wbgt_c >= 24:
        notes.append(f"WBGT around {wbgt_c:.0f} C: expect a materially slower pace at the same "
                     "effort, start slower still, and use shade and early starts. In heat this "
                     "severe the correct adjustment is to the session's purpose, not just its pace.")
    if wbgt_c is not None and wbgt_c <= 5:
        notes.append("Cold suppresses thirst, so drinking less is normal and usually fine -- but "
                     "warm up longer, and expect heart rate to read low for the first few km.")
    if body_mass_kg:
        notes.append(f"Caffeine, if you use it: 3-6 mg/kg is the well-evidenced range, so roughly "
                     f"{body_mass_kg*3:.0f}-{body_mass_kg*6:.0f} mg 30-60 min before the start. "
                     "Rehearse it on a long run first; it is also a diuretic-adjacent GI risk for "
                     "some people.")
    out["notes"] = notes
    return out


MEDICATION_WARNINGS: Dict[str, str] = {
    "nsaids": ("Avoid NSAIDs (ibuprofen, naproxen, diclofenac) before and during long runs and "
               "races. They do not improve endurance performance, and their use during prolonged "
               "exercise is associated with both exercise-associated hyponatraemia and acute "
               "kidney injury -- the combination of a long slow effort, generous fluid intake and "
               "an NSAID is the specific pattern that causes harm. Paracetamol is not a "
               "straightforward substitute either; the better answer is to not need one."),
    "antihistamines": "Sedating antihistamines impair thermoregulation and alertness.",
    "beta_blockers": ("Blunt heart rate at every intensity, so every HR zone derived from an age "
                      "formula is wrong. Use the measured ramp test, RPE and the talk test."),
    "stimulants": ("Stimulants (including high-dose caffeine and decongestants) raise heart rate "
                   "and core temperature and mask fatigue -- a poor combination with a long run in "
                   "the heat."),
}

SUPPLEMENT_CHECKS: List[Dict[str, str]] = [
    {"item": "ferritin",
     "why": ("Low iron stores are common, silent, and directly cap aerobic adaptation -- you feel "
             "flat and the plan looks like it has stalled. Worth checking before concluding that "
             "training is not working, and particularly worth checking in a shift worker whose "
             "eating is irregular."),
     "when": "If a phase stalls, or if easy pace at a given heart rate stops improving."},
    {"item": "vitamin D",
     "why": ("Relevant to bone stress injury risk, and low status is common in anyone who works "
             "indoors on shifts. This is the one micronutrient with a plausible direct link to the "
             "specific injury this plan is most worried about."),
     "when": "Once, early, especially entering winter."},
    {"item": "energy availability",
     "why": ("Under-fuelling relative to training load looks exactly like 'not adapting', and it "
             "is the most common invisible cause of a stalled block. It also directly impairs bone "
             "health. A resident skipping meals on a long shift and then adding a marathon block is "
             "a realistic setup for it."),
     "when": "Any time a gate stalls, or if weight is drifting down unintentionally."},
]


# ----------------------------------------------------------------------------------------
# Return to running
# ----------------------------------------------------------------------------------------


def return_to_run(days_off: int, reason: str, *, pain_free: bool = True,
                  last_weekly_km: float = 0.0) -> Dict[str, object]:
    """What to do after time off. Explicit, because "just pick the plan back up" is how people
    get injured twice.

    Detraining is much slower than people fear: aerobic fitness is largely intact after a week or
    two, and the reason to come back gradually is **tissue tolerance**, not lost fitness. That
    distinction matters, because it tells you which variable to restore slowly (volume and impact)
    and which you can trust (your aerobic engine).
    """
    if not pain_free:
        return {
            "clearance": "not_yet",
            "message": ("Do not restart while it still hurts. The test is not 'can I run' -- it is "
                        "walking 30 minutes pain-free, then jogging 1 minute at a time pain-free "
                        "the next day AND the morning after. Pain that appears the day after a run "
                        "is the signal that matters most and the one most often ignored."),
            "next_step": "Walk 30 min pain-free, then start the walk-jog ladder from the beginning.",
        }

    if reason in ("illness_fever", "covid", "flu"):
        return {
            "clearance": "graded",
            "message": ("After a febrile illness, resume gradually and abandon the session if the "
                        "heart rate at easy pace is much higher than usual or it simply feels wrong. "
                        "Elevated resting heart rate and suppressed HRV are the objective markers to "
                        "watch, and they usually lag feeling better by several days."),
            "start_at_pct": 50,
            "first_week_km": round(last_weekly_km * 0.5, 1),
            "rule": "No quality work until resting heart rate and HRV are back inside your bands.",
        }

    if days_off <= 7:
        pct = 90
        note = ("A week off costs very little fitness. Restart at about 90% of your previous week "
                "and carry on -- the ramp cap does the rest.")
    elif days_off <= 21:
        pct = 70
        note = ("Two to three weeks off: your aerobic fitness is largely intact, but tendon and "
                "bone tolerance falls faster than VO2max does. Come back at roughly 70% of your "
                "previous volume, keep it all easy for a week, and rebuild from there.")
    elif days_off <= 56:
        pct = 50
        note = ("A month or two off: restart at about half your previous volume, all easy, and "
                "expect to feel unfit for the first two or three runs before it comes back "
                "quickly. Do not chase the paces you had.")
    else:
        pct = 0
        note = ("More than two months off puts you back in the bone-stress window. Restart from the "
                "run-walk ladder rather than from your old volume. This is not a demotion -- it is "
                "the same reason the ladder existed the first time.")
    return {
        "clearance": "graded",
        "message": note,
        "start_at_pct": pct,
        "first_week_km": round(last_weekly_km * pct / 100.0, 1) if pct else None,
        "rule": ("Two consecutive pain-free weeks before any quality session returns."
                 if days_off > 21 else "Reintroduce one quality session per week, not two."),
    }


def bone_window_increment_factor(state: BoneLoadState) -> float:
    """Multiplier applied to the weekly volume increment while the bone window is armed.

    Halving the ramp for the first months is the one intervention that directly targets the injury
    the whole plan is most worried about, and it is cheap: the cost is a few weeks of slower
    progression, against a stress fracture that costs three to four months.

    An honest limit on the model: bone resorption runs for roughly 2-4 weeks after a new loading
    stimulus and formation takes 3-4 months, while recruit stress-fracture incidence peaks around
    weeks 3-6. So the window is a **simplification, and real vulnerability may extend past it** --
    which is exactly why absolute weekly increment caps stay in force for the entire build rather
    than only inside the window.
    """
    return 0.5 if state.in_high_risk_window else 1.0
