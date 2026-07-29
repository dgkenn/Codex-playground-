# What the other apps get right, and what to steal

A teardown of Runna, Garmin Coach/Connect, Nike Run Club, Strava, TrainAsONE, Athletica.ai, Runalyze,
HRV4Training, Stryd, Coopah, WHOOP, Intervals.icu, Final Surge, TrainerRoad, Gentler Streak, GoldenCheetah
and Apple Fitness — filtered hard by one constraint that changes almost every conclusion: **there is
exactly one user, and he is not paying for it.**

That single fact removes most of what these apps spend their design effort on. No onboarding funnel, no
retention loop, no social graph, no subscription, no App Store review, no need to be legible to a
beginner who has never seen the app before. What is left is the coaching.

---

## Steal these

### 1. Pain and injury log with trend detection — *Final Surge PAIR*
The highest value-per-line-of-code feature available. Log site, level, timing and duration; surface the
pattern before it becomes an injury. Cheap to build, and it directly serves the only thing that
actually matters here.

Implemented in `progress.pain_trend`, with two deliberate departures from a naive version: **focal**
bone pain escalates to "stop" regardless of how mild the number is, and **next-morning** pain escalates
even at 2/10. Those two fields carry more information than the pain score, and both are routinely
dismissed — next-day pain especially, because by the time you run again it has eased off.

### 2. Training status as a two-axis classifier — *Garmin Training Status*
Load trend × fitness trend → a plain-English label. Garmin's version needs their proprietary EPOC
model; the same structure works from Banister TRIMP and an efficiency-factor trend, both of which are
public and computable from heart rate alone.

`progress.training_status`. The combination that earns its keep is **rising load + declining fitness**
→ *Overreaching*, the one state where the honest advice is to do less. Garmin users complain about
getting contradictory guidance — told to add intensity and to rest more simultaneously — which is what
happens when several semi-redundant scores each speak for themselves. One label, one recommendation.

### 3. Recency-weighted readiness — *Garmin Training Readiness, WHOOP Strain Coach*
Last night should count for more than last month. Already how `readiness.daily_readiness` works.

WHOOP's Strain Coach also does something worth copying at the presentation layer: it outputs a **daily
target range** rather than dumping a score and leaving you to interpret it. Every readiness band here
maps to a concrete action.

### 4. Log-transformed HRV with a rolling baseline and band — *HRV4Training*
Marco Altini's approach, and the thing that stops a single noisy night showing up as a red day. It is
also the machinery the HRV-guided-training trials actually used. `readiness.hrv_baseline`.

### 5. The Performance Management Chart — *TrainingPeaks, GoldenCheetah*
Standard EWMAs with published time constants over a TRIMP-based load. Fully public, no power meter
needed. `load.ewma_load`, `load.acwr`.

**GoldenCheetah specifically is worth having open while writing this code**: it is GPL, mature, and
implements TRIMP, the Banister model and W′bal in readable C++. Checking a formula against a working
implementation beats re-deriving it from a paper.

### 6. Monotony and strain — *Runalyze*
Published formulas with actionable thresholds, and a variability guard that can force a rest day into
an otherwise rigid template. `load.monotony_strain`.

Worth noting the reading is inverted for you: a resident's risk is rarely monotony, it is the Saturday
where everything gets crammed in around a rota.

### 7. Continuous threshold estimation instead of test days — *TrainerRoad AI FTP Detection*
Update the fitness estimate from every session's execution data rather than scheduling formal maximal
tests. For a beginner this is worth more than for anyone else: **every test day is an injury-risk day**,
and this removes most of them. `physiology.vdot_from_hr_pace` plus `assessment.compare_ramps` give the
between-test tracker; formal trials stay as occasional checkpoints rather than the only source of truth.

### 8. Non-destructive cascading reschedule — *Athletica.ai*
Move one session and the rest of the plan re-adapts around it, rather than the plan breaking. This is
the single most important UX pattern for someone with an unpredictable rota. `adapt.reschedule_week`
does it automatically from the rota, with the long run getting first pick of days and quality work
never landing post-night.

### 9. Racing your past self on a repeated route — *Apple Watch Race Route*
Self-competition with no leaderboard, which is the only competitive framing that makes sense for one
user. `progress.compare_route_efforts`, with the honest twist: for a beginner the meaningful comparison
is **heart rate at the same pace**, not pace. Same loop at the same speed for ten fewer beats per
minute is a bigger win than thirty seconds quicker while working harder, and it is the one that
transfers to a marathon.

### 10. Rest-aware consistency instead of streaks — *Gentler Streak*
Gentler Streak rebuilt the streak concept around *appropriate* rest, using an adaptive band rather than
a consecutive-day counter. This is exactly the pattern needed here, because a consecutive-day streak is
a mechanism that rewards training when the body says rest — the precise failure everything else in this
system exists to prevent.

`progress.consistency` scores adherence to the plan **including its rest days**, and training on a
planned rest day *lowers* the score. Doing extra is not a bonus.

### 11. Event-triggered audio, not continuous narration — *PulsePacer, Cadence, RunXP*
Brief cues on zone entry and transitions. Continuous narration produces cue fatigue and then gets
switched off. `realtime.CueScheduler` is a priority queue with per-level rate limits and protected
windows around interval starts.

### 12. Explainability on every automated change — *the lesson from TrainAsONE*
TrainAsONE's ML plan is criticised as a black box you cannot interrogate or negotiate with. That
matters more for a self-coached user than anyone, because there is no human coach to translate the
model's intent. Every adaptation here returns its reason as a first-class field: `Adjustment.reason`,
`GateReport.guidance`, `ReplanDecision.reasons`, `ControlDecision.reason`.

### 13. Open analytics, no paywall, data portability — *Intervals.icu*
The architectural reference for a private single-user analytics layer. Also its auto-estimation of
threshold from best recent efforts, which is the same idea as #7.

---

## Learn from these failures

| App | Complaint | What we do |
|---|---|---|
| **Runna** | Violates progression guidance; only offers a *vacation* reschedule path, nothing for injury | Explicit ramp caps, plus an injury path: pain holds volume, `return_to_run` handles time off |
| **TrainAsONE** | Black-box prescriptions, no explanation or negotiation | Every change carries its reason; gates are visible and checkable |
| **Nike Run Club** | Audio narration stalls mid-run and dumps missed cues in a burst after pause/resume | Concrete QA item: test cue continuity through pause/resume/backgrounding before trusting it. The scheduler drops stale cues rather than queueing them |
| **Garmin Connect v5** | Cluttered; widgets intermittently fail to populate; contradictory guidance | One glanceable metric per screen; one ranked recommendation |
| **Strava** | Social feed is the product | No feed |
| Most of them | Streaks and badges that reward training through fatigue | See #10 |

---

## Explicitly do not build

- Social feed, kudos, followers, leaderboards, clubs, segment competition against other people.
- Consecutive-day streaks, badges, levels, or any gamification that makes training-through-fatigue feel
  like winning.
- Subscription, paywall, onboarding funnel, push notifications designed to drive engagement.
- A dashboard of twelve widgets. One number that matters, and the reasoning behind it on request.
- Cadence targets (see `RESEARCH.md` — the 180 figure is a misreading).
- Shoe recommendations by foot type.
- Anything that requires a server. This runs on the phone, talks to the SleepController on the local
  network, and keeps its data in one SQLite file you can copy.

---

## The adherence cliff, which is a design constraint

Large-cohort fitness-app data shows a steep drop-off with a pronounced cliff around **three to four
months**. For this plan that lands squarely in the middle of base building — the least externally
rewarding phase, where sessions stop obviously getting harder and no race is close.

This is not solved by motivational copy. It is solved by **evidence of invisible progress**:
heart rate falling at a fixed pace, efficiency factor rising, the same loop getting easier. Those are
real physiological changes you cannot feel from the inside, and showing them is the whole job of
`progress.progress_narrative`, which fires a specific warning in that window:

> You are 14 weeks in. This is statistically where people stop — the novelty is gone, base building is
> not dramatic, and there is no race close enough to pull you along. Nothing is wrong with your plan.
> The base you are building now is what the marathon is actually made of, and it is the least visible
> part of the whole process. If you need a target, put a 5K or 10K on the calendar.

---

## Two practical notes from the teardown

**Phone carry.** Armband phone carriers cause one-sided weight asymmetry and sweat-induced slippage.
The Verity Sense will already be on one upper arm, so putting the phone on the other arm compounds the
asymmetry — a waist belt or vest is the better default.

**Critical speed as a live fatigue gauge.** Stryd's critical-power model is proprietary, but the
underlying two-parameter hyperbolic model and the W′-balance differential form (Skiba) are public and
implemented in GoldenCheetah. Usable with GPS pace instead of power. Filed as *nice-to-have*: it is a
genuinely interesting live "anaerobic fuel gauge", and it is also the kind of feature that matters far
more to a competitive 5K runner than to someone whose goal is to finish a first marathon aerobically.
