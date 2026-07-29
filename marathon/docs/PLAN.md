# Your plan: from no 5K to a marathon

> **Generated from the engine, not written by hand.** Every number below comes from `marathon_engine`, which is covered by its own test suite. Regenerate with `python -m marathon_engine.report`. If a constant changes in the code, this document changes with it — there is deliberately no second copy of the plan to drift.

> Advisory only. This is a training plan, not medical advice, and it is built for one person.

## The shape of it

You have no fixed race date, which is the single most useful fact about your situation. It means the plan can be **gated on measurements instead of a calendar**. Each phase has explicit criteria; you move on when you meet them, not when a week number ticks over. A calendar plan has to guess your adaptation rate in advance and then either rushes you into a stress fracture or holds you back for months. This one cannot do either.

Two guards stop gating from becoming either a stall or a shortcut:

- **Minimum weeks per phase.** Bone and tendon adapt over months; your heart and lungs adapt in two to three weeks. That mismatch is the mechanism behind most beginner injuries, so good numbers cannot buy you an early promotion.
- **A stall review.** If a gate has not moved after the phase's stall threshold, the app stops adding load and runs a diagnostic instead — under-fuelling, sleep debt, a niggle being trained through, or simply a plan that is too aggressive for now.

| Phase | Goal | Min weeks | Stall review | Weekly volume |
|---|---|---|---|---|
| **assess** | Find out where you actually are. No hard running. | 1 | — | — |
| **foundation** | Run 30 minutes continuously, comfortably, in Z2. | 6 | 14 | 45–105 min |
| **base_1** | Make running a habit and finish a 5K. Volume, not speed. | 8 | 18 | 14–26 km |
| **base_2** | Add your first real threshold work and race a 10K. | 8 | 18 | 26–38 km |
| **half_build** | Build the long run and race a half marathon. | 10 | 22 | 38–48 km |
| **marathon_base** | Develop marathon-specific endurance: the long run is the point. | 10 | 24 | 46–58 km |
| **marathon_peak** | Rehearse race day -- marathon pace, fuelling, and the long run at size. | 6 | 12 | 52–62 km |
| **taper** | Cut volume, keep intensity, arrive fresh. | 2 | — | — |

Minimum total, if every gate falls on the earliest possible week: **55 weeks** (~1.1 years) including race and recovery. Realistically expect longer, and that is the plan working rather than failing — the floors are the point.

## Step 1: find out where you actually are

Your first week runs no hard sessions at all. The reason is specific: the two normal ways to start a plan are a recent race time or a maximal field test, and you have neither. Asking an untrained body for a maximal effort in week 1 measures your tolerance for discomfort more than your fitness, and it does it on tissue that has never absorbed running load.

So week 1 is a **submaximal graded ramp** plus a structural screen. That is enough to derive everything the plan needs.

### The ramp test (day 3)

5 min easy walk at 4.5 km/h, then start stage 1 without stopping.

| Stage | Speed | Pace | Duration | Mode |
|---|---|---|---|---|
| 1 | 5.0 km/h | 12:00/km | 4 min | walk |
| 2 | 6.0 km/h | 10:00/km | 4 min | walk |
| 3 | 7.0 km/h | 8:34/km | 4 min | jog |
| 4 | 8.0 km/h | 7:30/km | 4 min | jog |
| 5 | 9.0 km/h | 6:40/km | 4 min | jog |

At the end of every stage, record three things:

1. Record the mean HR over the FINAL 60 seconds (HR needs 2-3 min to plateau).
1. Rate effort on the Borg 6-20 scale.
1. Talk test: say a full sentence out loud and rate it comfortable / effortful / impossible.

**Stop when any of these happens** — stopping early is a valid result, not a failure. The fit only needs three usable stages:

- HR reaches 167 bpm (85% of heart-rate reserve)
- RPE reaches 15/20
- Speech becomes impossible
- Any chest pain, light-headedness, or a sense that something is wrong -- stop immediately

*Cooldown:* 5 min walk, then stand still for 60 s and record HR (recovery marker).

> A maximal test in week 1 risks injury on untrained tissue and measures discomfort tolerance as much as fitness. Three good submaximal stages give us the HR-speed relationship, which is all the planner needs to start.

### What the week-1 battery produces

| Day | What | Yields |
|---|---|---|
| Mon | Screening questionnaire + orthostatic test (5 min supine, 2 min standing) | Medical clearance gate; resting HR; the start of your HRV baseline |
| Tue | Structural screen | Your specific weak link — usually calf endurance |
| Wed | Graded ramp | HR/speed relationship, talk-test threshold, cadence, seed VDOT |
| Fri | Easy walk-jog shakeout | Confirms the sensor and audio cues work |

## What that gives you (worked example)

Using illustrative ramp numbers — a talk-test threshold around 7.5 km/h and a resting HR of 55 — here is what the engine derives. **Your real numbers will differ**; this exists so you can see the machinery working before you run anything.

- **HRmax:** 187 bpm (age formula)
- **Talk-test threshold HR:** 142 bpm — this *pins* your Z3/Z4 boundary rather than letting a population formula guess it
- **Seed VDOT:** 22, from `talk_test_threshold`
- **Prescription basis:** `hr_from_ramp`

### Your zones

| Zone | HR | What it is for |
|---|---|---|
| **Z1 Recovery** | 114–134 | active recovery, pure aerobic base, conversational |
| **Z2 Easy** | 134–151 | the bread and butter: mitochondrial/capillary adaptation |
| **Z3 Steady** | 151–162 | marathon-pace effort; useful but the classic junk-mile trap |
| **Z4 Threshold** | 162–174 | lactate threshold / tempo, ~1 h race effort |
| **Z5 VO2max** | 174–194 | 3-5 min interval intensity, aerobic ceiling |

### Your paces — and why they do not come from VDOT yet

A seed VDOT of 22 sits **below the floor of Daniels' published tables** (they start around 30). Below that the pace formulas extrapolate to numbers slower than a brisk walk, which is not a physiological finding — it is a quadratic running out of validity.

So the plan ignores them and prescribes from the HR/speed relationship your own ramp test measured. That is a better instrument for you right now, and it switches to VDOT automatically once a real time trial lifts you past 30.

| Zone | Pace range |
|---|---|
| Z1 Recovery | 8:26–10:03/km |
| Z2 Easy | 7:25–8:26/km |
| Z3 Steady | 6:53–7:25/km |
| Z4 Threshold | 6:23–6:53/km |
| Z5 VO2max | 5:41–6:23/km |

**Your easy window: 7:25–8:26/km.** Nearly all of your running lives here.

For contrast, the raw VDOT table would have said 10:48/km for easy — visibly wrong, and the exact kind of error that makes someone abandon a plan in week 2.

### Predicted times: deliberately none yet

The engine refuses to predict beyond 2.5× the longest distance you have actually covered. Extrapolating a marathon time from a treadmill ramp produces a number with a colon in it and no information — and, for a beginner, a demoralising one. Predictions unlock as you race: a 5K unlocks the 10K, a half unlocks the marathon.

### Structural findings from the example screen

- **calf_endurance_left** (medium) — 14 single-leg calf raises on the left (target ~22). The calf-Achilles complex absorbs the most load per stride of any structure in running; this is the highest-yield thing to fix, and it responds in 6-8 weeks.
  - *Do:* 3 x 15 heavy slow calf raises, 3x/week, straight- and bent-knee
- **calf_endurance_right** (medium) — 18 single-leg calf raises on the right (target ~22). The calf-Achilles complex absorbs the most load per stride of any structure in running; this is the highest-yield thing to fix, and it responds in 6-8 weeks.
  - *Do:* 3 x 15 heavy slow calf raises, 3x/week, straight- and bent-knee
- **calf_asymmetry** (medium) — 22% side-to-side difference in calf endurance (14 vs 18). Asymmetry this size is worth correcting before adding volume, and worth mentioning if anything starts to hurt on the weaker side.
  - *Do:* extra set on the weaker side; re-test in 4 weeks
- **step_down_pelvic_drop** (low) — Step-down shows pelvic drop. Common, usually a hip-abductor and motor-control issue rather than a structural one.
  - *Do:* side-lying abduction, single-leg bridges, slow step-downs

### Caveats the engine attaches to its own numbers

- Seed VDOT is 22, below the floor of Daniels' published tables (~30), so the VDOT pace formulas extrapolate to paces slower than a brisk walk. They are therefore NOT being used yet: your prescribed paces come from the heart-rate/speed relationship measured in your own ramp test. That is a better instrument for you right now, and the plan switches to VDOT automatically once a real time trial puts you above 30.
- Seed VDOT comes from a SUBMAXIMAL test and is deliberately conservative -- expect it to rise sharply at the week-4 time trial. Do not chase the early paces.
- HRmax is an age-based estimate with roughly +/-7 bpm standard error and up to 20 bpm individual error. Zones will be re-anchored after the first hard time trial.
- Marathon prediction uses a novice-adjusted Riegel exponent (1.15, not 1.06) because low-mileage first-timers fade much harder over the last 12 km than the standard formula assumes.
- The HR-speed fit was measured between 5 and 9 km/h. Any prescribed pace faster than that is an extrapolation -- the plan does not prescribe outside it during the foundation phase.

## The weeks

Your schedule is **3 runs + 2 strength sessions**, with the long run on Sun. Sessions get rescheduled automatically around your rota — the long run gets first pick of days, quality work never lands on a post-night day, and nothing is ever scheduled on a night shift.

> **A note on the paces in the later phases.** They are shown at an *illustrative projected fitness* (VDOT rising from your seed toward the low 40s), not at your week-1 numbers. Showing marathon-phase sessions at beginner paces would make the weekly volumes look impossible, when in fact they become reachable precisely because your easy pace gets quicker. Your real paces come from your own time trials.

### Assess

**Goal:** Find out where you actually are. No hard running.

**To leave this phase** (all of these, plus at least 1 weeks):

- **Pre-participation screening cleared** 🛑 — The ACSM screening algorithm, applied once before anything else. It exists to catch the small number of people who need clearance -- exertional chest discomfort, unusual breathlessness, exertional dizziness, or known cardiovascular/metabolic/renal disease -- not to put a barrier in front of exercise. Nothing else in this plan runs until it passes, because the plan eventually asks for a maximal effort.
- **Graded ramp test completed** — Everything downstream -- zones, paces, the efficiency baseline -- is derived from it.
- **Structural screen completed** — Finds the specific weak link (usually calf endurance) before load exposes it.
- **At least 7 nights of HRV data** — The readiness engine needs a personal baseline; a population norm is useless here.

#### Week 1 of assess

| Day | Session | Target |
|---|---|---|
| Mon | **Screening + baseline day -- no running** |  |
| Tue | **Structural screen** | 30 min |
| Wed | **Graded ramp test** | 35 min |
| Thu | **Rest** |  |
| Fri | **Easy shakeout walk-jog** | 25 min · Z1-2 · run 1/walk 2 x8 |
| Sat | **Rest** |  |
| Sun | **Rest** |  |

**Structural screen**
- Single-leg calf raises to failure per side
- 30 s sit-to-stand
- single-leg balance
- step-down quality
- plank hold.
> *Why:* Find the weak link before load finds it.

**Graded ramp test** — 5 min walk warm-up, then 4 min stages at 5, 6, 7, 8, 9 km/h. Record heart rate over the final 60 s of each stage, plus Borg 6-20 and the talk test. Stop at 85% of heart-rate reserve, RPE 15/20, or when speech becomes impossible.
> *Why:* Derive the heart-rate/speed relationship, the talk-test threshold, cadence at each speed, and the seed VDOT. Everything else follows.

- No hard running this week, on purpose. A maximal test on untrained tissue measures discomfort tolerance and buys an injury.
- Wear the armband overnight every night from now on -- the readiness engine needs at least 14 nights before its band means anything.

### Foundation

**Goal:** Run 30 minutes continuously, comfortably, in Z2.

**To leave this phase** (all of these, plus at least 6 weeks):

- **30 minutes of continuous running** — The classic couch-to-5K endpoint and the precondition for structured aerobic work.
- **That 30 minutes stayed in Z1-Z2** — Running 30 minutes is not the same as running 30 aerobic minutes. If it needed Z4, the aerobic base is not there yet and threshold work would be wasted on you.
- **No pain above 2/10 for two weeks** 🛑 — The pain-monitoring model treats 0-2/10 as acceptable, 3-5/10 as a warning to hold volume, and anything above 5/10 as a stop. Two clean weeks means the tissue is tolerating the current load, which is the precondition for adding more.
- **80% of planned sessions completed over 4 weeks** — Consistency is the variable that actually predicts progress. Advancing a phase on the strength of a good fortnight inside a patchy block just moves the problem forward.

#### Week 1 of foundation — target **24 min of running**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Run-walk 1/2 x 8** | 34 min · Z1-2 · run 1/walk 2 x8 |
| Wed | **Rest** |  |
| Thu | **Run-walk 1/2 x 8** | 34 min · Z1-2 · run 1/walk 2 x8 |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | **Rest** |  |
| Sun | **Run-walk 1/2 x 8** | 34 min · Z1-2 · run 1/walk 2 x8 |

**Strength (running-specific)**
- Heavy slow calf raises: 3 x 12 straight-knee + 3 x 12 bent-knee, 3 s down. Add load once 12 reps is easy -- this is the single highest-yield injury-prevention exercise for a runner.
- Single-leg work: split squats or step-ups, 3 x 8 per side, loaded.
- Hip abduction: side-lying or cable, 3 x 15 per side.
- Posterior chain: Romanian deadlift or hip thrust, 3 x 8.
- Anti-rotation core: Pallof press or suitcase carry, 3 x 30 s per side.
> *Why:* Injury prevention and running economy. Strength training substantially reduces overuse injury (Lauersen 2014/2018) and improves running economy without unwanted mass (Blagrove 2018). You already lift -- fold these in rather than adding a separate session.
> - Keep heavy lower-body work at least 24 h away from a quality run and 48 h from the long run.
> - Do not chase soreness. The goal is stiffness and strength, not a session that compromises the running.

**Run-walk 1/2 x 8** — 5 min walk warm-up, then 8 x (1 min easy running + 2 min walking), 5 min walk cool-down.
> *Why:* Build running-specific tissue tolerance in doses the tissue can actually absorb. The walk break is not a concession -- it is what keeps the running portions aerobic and the total load survivable.
> - Run the running portions slowly enough that the walk break feels almost unnecessary.
> - Do not skip the walk breaks because you feel good. The breaks are why you feel good.

- Run-walk ladder rung 1 of 8: 1 min running / 2 min walking x 8 (8 min of running per session, 24 min across the week).
- Repeat a rung rather than advancing if the previous week felt hard, hurt, or was interrupted. There is no deadline.

#### Week 2 of foundation — target **42 min of running**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Run-walk 2/2 x 7** | 38 min · Z1-2 · run 2/walk 2 x7 |
| Wed | Rest | — |
| Thu | **Run-walk 2/2 x 7** | 38 min · Z1-2 · run 2/walk 2 x7 |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Run-walk 2/2 x 7** | 38 min · Z1-2 · run 2/walk 2 x7 |

- Run-walk ladder rung 2 of 8: 2 min running / 2 min walking x 7 (14 min of running per session, 42 min across the week).
- Repeat a rung rather than advancing if the previous week felt hard, hurt, or was interrupted. There is no deadline.

#### Week 3 of foundation — target **54 min of running**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Run-walk 3/2 x 6** | 40 min · Z1-2 · run 3/walk 2 x6 |
| Wed | Rest | — |
| Thu | **Run-walk 3/2 x 6** | 40 min · Z1-2 · run 3/walk 2 x6 |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Run-walk 3/2 x 6** | 40 min · Z1-2 · run 3/walk 2 x6 |

- Run-walk ladder rung 3 of 8: 3 min running / 2 min walking x 6 (18 min of running per session, 54 min across the week).
- Repeat a rung rather than advancing if the previous week felt hard, hurt, or was interrupted. There is no deadline.

#### Week 4 of foundation — target **54 min of running** · *cutback week*

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Run-walk 3/2 x 6** | 40 min · Z1-2 · run 3/walk 2 x6 |
| Wed | Rest | — |
| Thu | **Run-walk 3/2 x 6** | 40 min · Z1-2 · run 3/walk 2 x6 |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Run-walk 3/2 x 6** | 40 min · Z1-2 · run 3/walk 2 x6 |

- Run-walk ladder rung 3 of 8: 3 min running / 2 min walking x 6 (18 min of running per session, 54 min across the week).
- Repeat a rung rather than advancing if the previous week felt hard, hurt, or was interrupted. There is no deadline.
- The ladder holds at the previous rung this week rather than advancing.
- Cutback week: volume x0.70. Every 4th week drops volume so the slow tissues catch up with the fast ones. [Convention rather than trial-tested, but the mechanism is sound and the cost is low.]

#### Week 6 of foundation — target **72 min of running**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Run-walk 12/2 x 2** | 38 min · Z1-2 · run 12/walk 2 x2 |
| Wed | Rest | — |
| Thu | **Run-walk 12/2 x 2** | 38 min · Z1-2 · run 12/walk 2 x2 |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Run-walk 12/2 x 2** | 38 min · Z1-2 · run 12/walk 2 x2 |

- Run-walk ladder rung 6 of 8: 12 min running / 2 min walking x 2 (24 min of running per session, 72 min across the week).
- Repeat a rung rather than advancing if the previous week felt hard, hurt, or was interrupted. There is no deadline.

*(Week 5 follow the same shape, progressing between the volumes shown.)*

### Base 1

**Goal:** Make running a habit and finish a 5K. Volume, not speed.

**To leave this phase** (all of these, plus at least 8 weeks):

- **20+ km/week for three consecutive weeks** — A stable floor of aerobic volume, held long enough to be real rather than a spike.
- **5K completed continuously** — The first honest performance measurement -- it replaces the conservative submaximal seed VDOT with a real one.
- **20+ single-leg calf raises per side** 🛑 — Calf-Achilles endurance is the most common structural limiter in new runners and the one most likely to fail as volume climbs.
- **No pain above 2/10 for two weeks** 🛑 — The pain-monitoring model treats 0-2/10 as acceptable, 3-5/10 as a warning to hold volume, and anything above 5/10 as a stop. Two clean weeks means the tissue is tolerating the current load, which is the precondition for adding more.
- **80% of planned sessions completed over 4 weeks** — Consistency is the variable that actually predicts progress. Advancing a phase on the strength of a good fortnight inside a patchy block just moves the problem forward.

#### Week 1 of base_1 — target **14 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Easy run** | 40 min · Z1-2 · 8:43/km |
| Wed | **Rest** |  |
| Thu | **Easy run + strides** | 40 min · Z1-2 · 8:43/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | **Rest** |  |
| Sun | **Long run** | 43 min · 4.9 km · Z1-2 · 8:43/km |

**Strength (running-specific)**
- Heavy slow calf raises: 3 x 12 straight-knee + 3 x 12 bent-knee, 3 s down. Add load once 12 reps is easy -- this is the single highest-yield injury-prevention exercise for a runner.
- Single-leg work: split squats or step-ups, 3 x 8 per side, loaded.
- Hip abduction: side-lying or cable, 3 x 15 per side.
- Posterior chain: Romanian deadlift or hip thrust, 3 x 8.
- Anti-rotation core: Pallof press or suitcase carry, 3 x 30 s per side.
- Low-amplitude plyometrics: 3 x 10 pogo hops, 2 x 10 alternating bounds. Stiffness work -- improves running economy (Blagrove 2018)
- introduce only once the calf-raise gate is met, and never within 48 h of a long run.
> *Why:* Injury prevention and running economy. Strength training substantially reduces overuse injury (Lauersen 2014/2018) and improves running economy without unwanted mass (Blagrove 2018). You already lift -- fold these in rather than adding a separate session.
> - Keep heavy lower-body work at least 24 h away from a quality run and 48 h from the long run.
> - Do not chase soreness. The goal is stiffness and strength, not a session that compromises the running.

**Easy run + strides** — Easy running, then 6 x 20 s strides at a relaxed fast pace with full walk-back recovery. Strides are not a workout -- they are form and neuromuscular maintenance.
> *Why:* Aerobic development with minimal cost. This is the session most often ruined by running it too fast.
> - If you cannot hold a conversation, you are going too fast -- slow down, do not shorten it.
> - Heart rate is the referee, not pace. On a hot day or a bad-sleep day the same effort is a slower pace, and that is correct, not a setback.
> - Strides should feel fast and easy, never strained. Stop the set if form degrades.

**Long run** — Steady and easy throughout.
> *Why:* Time on feet. This is the session the marathon is actually built from -- mitochondrial and capillary density, fat oxidation, tendon and bone tolerance, and the confidence that comes from having been out there.
> - Daniels would cap the long run at 30% of weekly volume at this level; this one is 35%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
> - Start slower than feels natural. Negative-split the run if you can.
> - Decoupling is the metric that matters here: if heart rate drifts more than 5% relative to pace between the halves, the pace was too hot for the duration.

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 35%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- No threshold work yet. Volume and consistency first -- threshold work on a thin base produces fatigue without much adaptation.

#### Week 2 of base_1 — target **16 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Easy run** | 43 min · Z1-2 · 8:43/km |
| Wed | Rest | — |
| Thu | **Easy run + strides** | 43 min · Z1-2 · 8:43/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 50 min · 5.7 km · Z1-2 · 8:43/km |

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 37%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- No threshold work yet. Volume and consistency first -- threshold work on a thin base produces fatigue without much adaptation.

#### Week 3 of base_1 — target **17 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Easy run** | 46 min · Z1-2 · 8:43/km |
| Wed | Rest | — |
| Thu | **Easy run + strides** | 46 min · Z1-2 · 8:43/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 58 min · 6.7 km · Z1-2 · 8:43/km |

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 39%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- No threshold work yet. Volume and consistency first -- threshold work on a thin base produces fatigue without much adaptation.

#### Week 4 of base_1 — target **13 km** · *cutback week*

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Easy run** | 39 min · Z1-2 · 8:43/km |
| Wed | Rest | — |
| Thu | **Easy run + strides** | 39 min · Z1-2 · 8:43/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 38 min · 4.4 km · Z1-2 · 8:43/km |

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 41%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- Cutback week: long run trimmed 20% as well as weekly volume.
- No threshold work yet. Volume and consistency first -- threshold work on a thin base produces fatigue without much adaptation.
- Cutback week: volume x0.70. Every 4th week drops volume so the slow tissues catch up with the fast ones. [Convention rather than trial-tested, but the mechanism is sound and the cost is low.]

#### Week 8 of base_1 — target **18 km** · *cutback week*

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Easy run** | 48 min · Z1-2 · 8:43/km |
| Wed | Rest | — |
| Thu | **Easy run + strides** | 48 min · Z1-2 · 8:43/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 62 min · 7.1 km · Z1-2 · 8:43/km |

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 49%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- Cutback week: long run trimmed 20% as well as weekly volume.
- No threshold work yet. Volume and consistency first -- threshold work on a thin base produces fatigue without much adaptation.
- Cutback week: volume x0.70. Every 4th week drops volume so the slow tissues catch up with the fast ones. [Convention rather than trial-tested, but the mechanism is sound and the cost is low.]

*(Weeks 5–7 follow the same shape, progressing between the volumes shown.)*

### Base 2

**Goal:** Add your first real threshold work and race a 10K.

**To leave this phase** (all of these, plus at least 8 weeks):

- **32+ km/week for three consecutive weeks** — The volume floor that makes threshold work productive instead of merely tiring.
- **A 14 km long run completed** — Roughly a third of the marathon distance -- the checkpoint before half-marathon work.
- **10K completed** — Recalibrates VDOT at a duration where aerobic endurance actually shows up.
- **Long-run decoupling under 8%** — Heart rate drifting hard relative to pace on a long run means the aerobic base is still thin, whatever the 10K time says. Under 5% is the target; 8% is the gate.
- **No pain above 2/10 for two weeks** 🛑 — The pain-monitoring model treats 0-2/10 as acceptable, 3-5/10 as a warning to hold volume, and anything above 5/10 as a stop. Two clean weeks means the tissue is tolerating the current load, which is the precondition for adding more.
- **80% of planned sessions completed over 4 weeks** — Consistency is the variable that actually predicts progress. Advancing a phase on the strength of a good fortnight inside a patchy block just moves the problem forward.

#### Week 1 of base_2 — target **34 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 2 x 6 min** | 46 min · Z4 · 5:48/km |
| Wed | **Rest** |  |
| Thu | **Easy run** | 134 min · Z1-2 · 7:55/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | **Rest** |  |
| Sun | **Long run** | 72 min · 9.1 km · Z1-2 · 7:55/km |

**Strength (running-specific)**
- Heavy slow calf raises: 3 x 12 straight-knee + 3 x 12 bent-knee, 3 s down. Add load once 12 reps is easy -- this is the single highest-yield injury-prevention exercise for a runner.
- Single-leg work: split squats or step-ups, 3 x 8 per side, loaded.
- Hip abduction: side-lying or cable, 3 x 15 per side.
- Posterior chain: Romanian deadlift or hip thrust, 3 x 8.
- Anti-rotation core: Pallof press or suitcase carry, 3 x 30 s per side.
- Low-amplitude plyometrics: 3 x 10 pogo hops, 2 x 10 alternating bounds. Stiffness work -- improves running economy (Blagrove 2018)
- introduce only once the calf-raise gate is met, and never within 48 h of a long run.
> *Why:* Injury prevention and running economy. Strength training substantially reduces overuse injury (Lauersen 2014/2018) and improves running economy without unwanted mass (Blagrove 2018). You already lift -- fold these in rather than adding a separate session.
> - Keep heavy lower-body work at least 24 h away from a quality run and 48 h from the long run.
> - Do not chase soreness. The goal is stiffness and strength, not a session that compromises the running.

**Threshold 2 x 6 min** — 20 min easy warm-up, then 2 x 6 min at threshold pace (5:48/km) with 2 min easy jog between, then 10 min easy cool-down.
> *Why:* Raise the pace you can hold for an hour. Cruise intervals rather than one long tempo because broken threshold work accumulates more time at the intensity for less fatigue -- Daniels' own argument for the format.
> - Threshold is 'comfortably hard' -- about the pace you could hold for an hour in a race. If rep 1 feels hard, it is too fast.
> - Heart rate lags: expect it to reach the zone about 90 seconds into each rep. Do not chase the number at the start of the rep.

**Long run** — Steady and easy throughout.
> *Why:* Time on feet. This is the session the marathon is actually built from -- mitochondrial and capillary density, fat oxidation, tendon and bone tolerance, and the confidence that comes from having been out there.
> *Fuelling:* Water is enough, but practise carrying it. Start rehearsing a gel late in the run.
> - Daniels would cap the long run at 30% of weekly volume at this level; this one is 35%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
> - Start slower than feels natural. Negative-split the run if you can.
> - Decoupling is the metric that matters here: if heart rate drifts more than 5% relative to pace between the halves, the pace was too hot for the duration.

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 35%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- First threshold block. One quality session a week is the correct dose on three runs a week -- the long run is already a hard session.

#### Week 2 of base_2 — target **36 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 2 x 6 min** | 46 min · Z4 · 5:48/km |
| Wed | Rest | — |
| Thu | **Easy run** | 139 min · Z1-2 · 7:55/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 81 min · 10.2 km · Z1-2 · 7:55/km |

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 37%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- First threshold block. One quality session a week is the correct dose on three runs a week -- the long run is already a hard session.

#### Week 8 of base_2 — target **37 km** · *cutback week*

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 8 min** | 60 min · Z4 · 5:48/km |
| Wed | Rest | — |
| Thu | **Easy run** | 128 min · Z1-2 · 7:55/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 83 min · 10.4 km · Z1-2 · 7:55/km |

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 49%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- Cutback week: long run trimmed 20% as well as weekly volume.
- First threshold block. One quality session a week is the correct dose on three runs a week -- the long run is already a hard session.
- Cutback week: volume x0.70. Every 4th week drops volume so the slow tissues catch up with the fast ones. [Convention rather than trial-tested, but the mechanism is sound and the cost is low.]

*(Weeks 3–7 follow the same shape, progressing between the volumes shown.)*

### Half Build

**Goal:** Build the long run and race a half marathon.

**To leave this phase** (all of these, plus at least 10 weeks):

- **42+ km/week for three consecutive weeks** — The base a marathon block is built on. Going into marathon-specific work below this is the single most common reason first marathons go badly.
- **A 20 km long run completed** — Half-marathon readiness.
- **Half marathon completed** — The best available predictor of marathon readiness, and a rehearsal of fuelling, pacing and kit at a distance where mistakes are survivable.
- **No pain above 2/10 for two weeks** 🛑 — The pain-monitoring model treats 0-2/10 as acceptable, 3-5/10 as a warning to hold volume, and anything above 5/10 as a stop. Two clean weeks means the tissue is tolerating the current load, which is the precondition for adding more.
- **80% of planned sessions completed over 4 weeks** — Consistency is the variable that actually predicts progress. Advancing a phase on the strength of a good fortnight inside a patchy block just moves the problem forward.

#### Week 1 of half_build — target **36 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 8 min** | 60 min · Z4 · 5:18/km |
| Wed | **Rest** |  |
| Thu | **Easy run** | 80 min · Z1-2 · 7:16/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | **Rest** |  |
| Sun | **Long run** | 97 min · 13.3 km · Z1-2 · 7:16/km |

**Strength (running-specific)**
- Heavy slow calf raises: 3 x 12 straight-knee + 3 x 12 bent-knee, 3 s down. Add load once 12 reps is easy -- this is the single highest-yield injury-prevention exercise for a runner.
- Single-leg work: split squats or step-ups, 3 x 8 per side, loaded.
- Hip abduction: side-lying or cable, 3 x 15 per side.
- Posterior chain: Romanian deadlift or hip thrust, 3 x 8.
- Anti-rotation core: Pallof press or suitcase carry, 3 x 30 s per side.
- Low-amplitude plyometrics: 3 x 10 pogo hops, 2 x 10 alternating bounds. Stiffness work -- improves running economy (Blagrove 2018)
- introduce only once the calf-raise gate is met, and never within 48 h of a long run.
> *Why:* Injury prevention and running economy. Strength training substantially reduces overuse injury (Lauersen 2014/2018) and improves running economy without unwanted mass (Blagrove 2018). You already lift -- fold these in rather than adding a separate session.
> - Keep heavy lower-body work at least 24 h away from a quality run and 48 h from the long run.
> - Do not chase soreness. The goal is stiffness and strength, not a session that compromises the running.

**Threshold 3 x 8 min** — 20 min easy warm-up, then 3 x 8 min at threshold pace (5:18/km) with 2 min easy jog between, then 10 min easy cool-down.
> *Why:* Raise the pace you can hold for an hour. Cruise intervals rather than one long tempo because broken threshold work accumulates more time at the intensity for less fatigue -- Daniels' own argument for the format.
> - Threshold is 'comfortably hard' -- about the pace you could hold for an hour in a race. If rep 1 feels hard, it is too fast.
> - Heart rate lags: expect it to reach the zone about 90 seconds into each rep. Do not chase the number at the start of the rep.

**Long run** — Steady and easy throughout.
> *Why:* Time on feet. This is the session the marathon is actually built from -- mitochondrial and capillary density, fat oxidation, tendon and bone tolerance, and the confidence that comes from having been out there.
> *Fuelling:* Take 30-60 g of carbohydrate per hour after the first hour, and drink to thirst. Above ~2.5 h aim toward 60-90 g/h using a glucose+fructose mix -- the gut is trainable and this is the training (ACSM/ISSN guidance; the high end needs practice, so build up to it rather than trying it on race day).
> - Daniels would cap the long run at 30% of weekly volume at this level; this one is 35%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
> - Start slower than feels natural. Negative-split the run if you can.
> - Decoupling is the metric that matters here: if heart rate drifts more than 5% relative to pace between the halves, the pace was too hot for the duration.

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 35%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.

#### Week 2 of half_build — target **37 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 8 min** | 60 min · Z4 · 5:18/km |
| Wed | Rest | — |
| Thu | **Easy run** | 80 min · Z1-2 · 7:16/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 105 min · 14.5 km · Z1-2 · 7:16/km |

- Daniels would cap the long run at 30% of weekly volume at this level; this one is 37%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.

#### Week 10 of half_build — target **45 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 5 x 8 min** | 80 min · Z4 · 5:18/km |
| Wed | Rest | — |
| Thu | **Easy run** | 68 min · Z1-2 · 7:16/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 147 min · 20.2 km · Z1-2 · 7:16/km |

- Daniels would cap the long run at 25% of weekly volume at this level; this one is 50%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- The long run is 50% of your week. That is high, and it is the unavoidable cost of a 3-run week -- the textbook figure is 30-35%. Adding a short fourth easy run is the cleanest way to bring it down.

*(Weeks 3–9 follow the same shape, progressing between the volumes shown.)*

### Marathon Base

**Goal:** Develop marathon-specific endurance: the long run is the point.

**To leave this phase** (all of these, plus at least 10 weeks):

- **Three long runs of 26 km or more** — Time on feet is the specific adaptation the marathon demands, and one long run does not build it.
- **Long-run decoupling under 6%** — Aerobic durability at duration -- the thing that decides whether the last 10 km is running or survival.
- **48+ km/week for three consecutive weeks** — Peak-phase volume floor for a 3-day-a-week schedule with cross-training.
- **No pain above 2/10 for two weeks** 🛑 — The pain-monitoring model treats 0-2/10 as acceptable, 3-5/10 as a warning to hold volume, and anything above 5/10 as a stop. Two clean weeks means the tissue is tolerating the current load, which is the precondition for adding more.
- **80% of planned sessions completed over 4 weeks** — Consistency is the variable that actually predicts progress. Advancing a phase on the strength of a good fortnight inside a patchy block just moves the problem forward.

#### Week 1 of marathon_base — target **41 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 10 min** | 66 min · Z4 · 5:00/km |
| Wed | **Optional 4th easy run (30 min)** *(optional)* | 30 min · Z1-2 · 6:51/km |
| Thu | **Easy run** | 80 min · Z1-2 · 6:51/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 110 min · 16.1 km · Z1-2 · 6:51/km |

- Daniels would cap the long run at 25% of weekly volume at this level; this one is 35%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- A fourth easy run is offered this phase. Optional, and no gate needs it.

#### Week 2 of marathon_base — target **42 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 10 min** | 66 min · Z4 · 5:00/km |
| Wed | **Optional 4th easy run (30 min)** *(optional)* | 30 min · Z1-2 · 6:51/km |
| Thu | **Easy run** | 80 min · Z1-2 · 6:51/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 117 min · 17.0 km · Z1-2 · 6:51/km |

- Daniels would cap the long run at 25% of weekly volume at this level; this one is 37%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- A fourth easy run is offered this phase. Optional, and no gate needs it.

#### Week 10 of marathon_base — target **51 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 5 x 10 min** | 90 min · Z4 · 5:00/km |
| Wed | **Optional 4th easy run (30 min)** *(optional)* | 30 min · Z1-2 · 6:51/km |
| Thu | **Easy run** | 76 min · Z1-2 · 6:51/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 150 min · 21.9 km · Z1-2 · 6:51/km |

- Daniels would cap the long run at 25% of weekly volume at this level; this one is 50%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- Capped at 150 min (21.9 km at your easy pace). This is Daniels' own long-run time limit; time on feet is the adaptation that matters, and past roughly two and a half hours the damage and recovery cost climb faster than the benefit does.
- The long run is 50% of your week. That is high, and it is the unavoidable cost of a 3-run week -- the textbook figure is 30-35%. Adding a short fourth easy run is the cleanest way to bring it down.
- A fourth easy run is offered this phase. Optional, and no gate needs it.

*(Weeks 3–9 follow the same shape, progressing between the volumes shown.)*

### Marathon Peak

**Goal:** Rehearse race day -- marathon pace, fuelling, and the long run at size.

**To leave this phase** (all of these, plus at least 6 weeks):

- **Two long runs with marathon-pace segments** — Rehearses race pace on tired legs, which is the only way to know it is realistic.
- **A long run of 150+ minutes** — Time on feet matters more than distance for a first marathon.
- **Race fuelling rehearsed on two long runs** 🛑 — The gut is trainable and untrained guts fail at 30 km. Practise the exact products and timing you will use.
- **No pain above 2/10 for two weeks** 🛑 — The pain-monitoring model treats 0-2/10 as acceptable, 3-5/10 as a warning to hold volume, and anything above 5/10 as a stop. Two clean weeks means the tissue is tolerating the current load, which is the precondition for adding more.

#### Week 1 of marathon_peak — target **44 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 10 min** | 66 min · Z4 · 4:48/km |
| Wed | **Optional 4th easy run (30 min)** *(optional)* | 30 min · Z1-2 · 6:36/km |
| Thu | **Easy run** | 80 min · Z1-2 · 6:36/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | **Rest** |  |
| Sun | **Long run with marathon-pace finish** | 120 min · 18.2 km · Z2-3 · 5:18/km |

**Strength (running-specific)**
- Heavy slow calf raises: 3 x 12 straight-knee + 3 x 12 bent-knee, 3 s down. Add load once 12 reps is easy -- this is the single highest-yield injury-prevention exercise for a runner.
- Single-leg work: split squats or step-ups, 3 x 8 per side, loaded.
- Hip abduction: side-lying or cable, 3 x 15 per side.
- Posterior chain: Romanian deadlift or hip thrust, 3 x 8.
- Anti-rotation core: Pallof press or suitcase carry, 3 x 30 s per side.
- Low-amplitude plyometrics: 3 x 10 pogo hops, 2 x 10 alternating bounds. Stiffness work -- improves running economy (Blagrove 2018)
- introduce only once the calf-raise gate is met, and never within 48 h of a long run.
> *Why:* Injury prevention and running economy. Strength training substantially reduces overuse injury (Lauersen 2014/2018) and improves running economy without unwanted mass (Blagrove 2018). You already lift -- fold these in rather than adding a separate session.
> - Keep heavy lower-body work at least 24 h away from a quality run and 48 h from the long run.
> - Do not chase soreness. The goal is stiffness and strength, not a session that compromises the running.

**Threshold 3 x 10 min** — 20 min easy warm-up, then 3 x 10 min at threshold pace (4:48/km) with 2 min easy jog between, then 10 min easy cool-down.
> *Why:* Raise the pace you can hold for an hour. Cruise intervals rather than one long tempo because broken threshold work accumulates more time at the intensity for less fatigue -- Daniels' own argument for the format.
> - Threshold is 'comfortably hard' -- about the pace you could hold for an hour in a race. If rep 1 feels hard, it is too fast.
> - Heart rate lags: expect it to reach the zone about 90 seconds into each rep. Do not chase the number at the start of the rep.

**Long run with marathon-pace finish** — Easy at 6:36/km, then the final 20 min at marathon pace (5:18/km). Do not start the fast section early.
> *Why:* Marathon pace on pre-fatigued legs -- the closest safe rehearsal of the second half of the race, and the honest test of whether the goal pace is real.
> *Fuelling:* Rehearse race fuelling exactly: same products, same timing, same volume of fluid.
> - If you cannot hold marathon pace at the end of this, the goal pace is wrong. That is information, not failure -- and far cheaper to learn here than at 30 km.
> - Practise the race-day details: kit, shoes, gels, bottle, start time, breakfast.

- Daniels would cap the long run at 25% of weekly volume at this level; this one is 35%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- A fourth easy run is offered this phase. Optional, and no gate needs it.
- Honest note: this week's sessions come to about 44 km, short of the 52 km corridor target. Three runs a week plus a 150-minute long-run cap has a real ceiling at your current easy pace, and the ceiling rises as your pace does rather than by being wished away. If the gap matters to you, the fourth easy run is the fix.

#### Week 2 of marathon_peak — target **45 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 10 min** | 66 min · Z4 · 4:48/km |
| Wed | **Optional 4th easy run (30 min)** *(optional)* | 30 min · Z1-2 · 6:36/km |
| Thu | **Easy run** | 80 min · Z1-2 · 6:36/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 127 min · 19.2 km · Z1-2 · 6:36/km |

- Daniels would cap the long run at 25% of weekly volume at this level; this one is 37%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- A fourth easy run is offered this phase. Optional, and no gate needs it.

#### Week 6 of marathon_peak — target **52 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 4 x 10 min** | 78 min · Z4 · 4:48/km |
| Wed | **Optional 4th easy run (30 min)** *(optional)* | 30 min · Z1-2 · 6:36/km |
| Thu | **Easy run** | 80 min · Z1-2 · 6:36/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 155 min · 23.4 km · Z1-2 · 6:36/km |

- Daniels would cap the long run at 25% of weekly volume at this level; this one is 45%. Three runs a week leaves no other way to build a marathon long run, so this is a real and accepted trade-off rather than an oversight -- and the time cap is what keeps it bounded.
- A fourth easy run is offered this phase. Optional, and no gate needs it.

*(Weeks 3–5 follow the same shape, progressing between the volumes shown.)*

### Taper

**Goal:** Cut volume, keep intensity, arrive fresh.

#### Week 1 of taper — target **27 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 6 min** | 54 min · Z4 · 4:48/km |
| Wed | **Rest** |  |
| Thu | **Easy run** | 30 min · Z1-2 · 6:36/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | **Rest** |  |
| Sun | **Long run** | 77 min · 11.6 km · Z1-2 · 6:36/km |

**Strength (running-specific)**
- Heavy slow calf raises: 3 x 12 straight-knee + 3 x 12 bent-knee, 3 s down. Add load once 12 reps is easy -- this is the single highest-yield injury-prevention exercise for a runner.
- Single-leg work: split squats or step-ups, 3 x 8 per side, loaded.
- Hip abduction: side-lying or cable, 3 x 15 per side.
- Posterior chain: Romanian deadlift or hip thrust, 3 x 8.
- Anti-rotation core: Pallof press or suitcase carry, 3 x 30 s per side.
- Low-amplitude plyometrics: 3 x 10 pogo hops, 2 x 10 alternating bounds. Stiffness work -- improves running economy (Blagrove 2018)
- introduce only once the calf-raise gate is met, and never within 48 h of a long run.
> *Why:* Injury prevention and running economy. Strength training substantially reduces overuse injury (Lauersen 2014/2018) and improves running economy without unwanted mass (Blagrove 2018). You already lift -- fold these in rather than adding a separate session.
> - Keep heavy lower-body work at least 24 h away from a quality run and 48 h from the long run.
> - Do not chase soreness. The goal is stiffness and strength, not a session that compromises the running.

**Threshold 3 x 6 min** — 20 min easy warm-up, then 3 x 6 min at threshold pace (4:48/km) with 2 min easy jog between, then 10 min easy cool-down.
> *Why:* Raise the pace you can hold for an hour. Cruise intervals rather than one long tempo because broken threshold work accumulates more time at the intensity for less fatigue -- Daniels' own argument for the format.
> - Threshold is 'comfortably hard' -- about the pace you could hold for an hour in a race. If rep 1 feels hard, it is too fast.
> - Heart rate lags: expect it to reach the zone about 90 seconds into each rep. Do not chase the number at the start of the rep.

**Long run** — Steady easy running; see the marathon-pace weeks for segment work.
> *Why:* Time on feet. This is the session the marathon is actually built from -- mitochondrial and capillary density, fat oxidation, tendon and bone tolerance, and the confidence that comes from having been out there.
> *Fuelling:* Water is enough, but practise carrying it. Start rehearsing a gel late in the run.
> - Short by design. You cannot gain fitness now; you can only arrive tired.
> - Start slower than feels natural. Negative-split the run if you can.
> - Decoupling is the metric that matters here: if heart rate drifts more than 5% relative to pace between the halves, the pace was too hot for the duration.

- Bosquet 2007 meta-analysis: a 2-week taper with a 41-60% volume reduction, holding intensity and frequency, produced the largest performance gain. Cutting intensity instead of volume is what makes people feel flat on race day.
- Volume is 50% of peak. Intensity and frequency stay.

#### Week 2 of taper — target **20 km**

| Day | Session | Target |
|---|---|---|
| Mon | **Strength (running-specific)** | 45 min |
| Tue | **Threshold 3 x 6 min** | 54 min · Z4 · 4:48/km |
| Wed | Rest | — |
| Thu | **Easy run** | 30 min · Z1-2 · 6:36/km |
| Fri | **Strength (running-specific)** | 45 min |
| Sat | Rest | — |
| Sun | **Long run** | 24 min · 3.7 km · Z1-2 · 6:36/km |

- Bosquet 2007 meta-analysis: a 2-week taper with a 41-60% volume reduction, holding intensity and frequency, produced the largest performance gain. Cutting intensity instead of volume is what makes people feel flat on race day.
- Volume is 30% of peak. Intensity and frequency stay.

### Race

**Goal:** Run the marathon.

#### Week 1 of race

| Day | Session | Target |
|---|---|---|
| Mon | **Rest** |  |
| Tue | **Easy shakeout** | 25 min · Z1-2 · 6:36/km |
| Wed | **Rest** |  |
| Thu | **Easy + 4 strides** | 20 min · Z1-2 · 6:36/km |
| Fri | **Rest** |  |
| Sat | **Rest** |  |
| Sun | **Marathon** | 42.2 km · Z2-3 · 5:18/km |

**Marathon** — Target 5:18/km. First 5 km deliberately 10-15 s/km slower than target.
> *Why:* Execute what you practised.
> *Fuelling:* 60-90 g carbohydrate per hour from 45 min, exactly as rehearsed. Drink to thirst.
> - The first half should feel almost too easy. Every marathon that goes wrong goes wrong in the first 10 km.
> - Heart rate will read high in the last hour from cardiac drift and heat -- that is expected. Pace and feel lead from 30 km.

- Race week. Nothing you do now adds fitness; plenty can subtract it.

### Recovery

**Goal:** Do almost nothing, on purpose.

#### Week 1 of recovery

| Day | Session | Target |
|---|---|---|
| Mon | Rest | — |
| Tue | Rest | — |
| Wed | **Optional easy jog** *(optional)* | 20 min · Z1-2 · 6:36/km |
| Thu | Rest | — |
| Fri | Rest | — |
| Sat | **Optional easy jog** *(optional)* | 25 min · Z1-2 · 6:36/km |
| Sun | Rest | — |

- Reverse taper: roughly one easy day per mile raced before any structured training resumes -- about three weeks. Walking, swimming and cycling are all fine; running is not required.
- Do not book the next goal race this week. Decide when you feel normal again.

#### Week 2 of recovery

| Day | Session | Target |
|---|---|---|
| Mon | Rest | — |
| Tue | Rest | — |
| Wed | **Optional easy jog** *(optional)* | 20 min · Z1-2 · 6:36/km |
| Thu | Rest | — |
| Fri | Rest | — |
| Sat | **Optional easy jog** *(optional)* | 25 min · Z1-2 · 6:36/km |
| Sun | Rest | — |

- Reverse taper: roughly one easy day per mile raced before any structured training resumes -- about three weeks. Walking, swimming and cycling are all fine; running is not required.
- Do not book the next goal race this week. Decide when you feel normal again.

#### Week 3 of recovery

| Day | Session | Target |
|---|---|---|
| Mon | Rest | — |
| Tue | Rest | — |
| Wed | **Optional easy jog** *(optional)* | 20 min · Z1-2 · 6:36/km |
| Thu | Rest | — |
| Fri | Rest | — |
| Sat | **Optional easy jog** *(optional)* | 25 min · Z1-2 · 6:36/km |
| Sun | Rest | — |

- Reverse taper: roughly one easy day per mile raced before any structured training resumes -- about three weeks. Walking, swimming and cycling are all fine; running is not required.
- Do not book the next goal race this week. Decide when you feel normal again.

## The long run, and its ceilings

Three caps apply, and the app tells you which one is binding:

1. **Time: 150 minutes** (rising to 165 for the biggest peak-phase runs). This is Daniels' own limit. The widely repeated "three hours" figure exceeds it by 20%, and it does so in exactly the population least able to absorb the extra half hour.
2. **Share of the week:** up to 50%. Textbook guidance is 30–35%, and on three runs a week that is arithmetically impossible for a marathon-length long run. This is the real cost of the 3-day schedule, and the app states it rather than hiding it.
3. **Distance: 32 km.** There is no evidence a first-timer gains from going further.

If you ever want a time goal rather than a strong finish, **adding a fourth easy run is the single highest-yield change available** — it is the one thing that brings the long run's share back toward the textbook figure. The plan offers it from the marathon phases onward, and no gate depends on it.

## The taper

Two weeks, volume down, **intensity and frequency held**. From Bosquet's meta-analysis: the largest performance gains came from a 2-week taper with a 41–60% volume reduction while keeping intensity. Cutting the hard sessions instead of the volume is what makes people feel flat on race day.

| Week | Volume | Long run | Keep | Cut |
|---|---|---|---|---|
| T-2 | 28 km (50% of peak) | 12 km | session frequency (still 3 runs); intensity -- the quality session stays at threshold/MP pace, just shorter | total volume; long-run length |
| T-1 | 16 km (30% of peak) | 7 km | session frequency (still 3 runs); intensity -- the quality session stays at threshold/MP pace, just shorter | total volume; long-run length |

## Safety, honestly

### Bone is the blind spot

Nothing in your HRV, resting HR, or training-load numbers can see bone. Bone remodels over **months**, while your aerobic fitness improves in **two to three weeks** — and that gap is the injury. You can be green every single morning and still be twelve weeks into building a tibial stress fracture.

For your first ~20 weeks of running, that means: prefer more frequent shorter runs over fewer longer ones, vary the surface, and treat pain at a single **point** on a bone as a hard stop rather than a niggle. The app tracks this separately from everything else, precisely because no other metric can.

### The pain rules

| Pain | Rule |
|---|---|
| 0–2 / 10 | Acceptable. Carry on and keep watching it. |
| 3–5 / 10 | Warning. Volume **holds** — no increases until two clean weeks. Today becomes easy. |
| > 5 / 10 | Stop the run. Every time. |
| Pain the *morning after* | The signal that matters most and the one most often ignored. |

### Stop immediately, whatever the plan says

- **Chest Pain** — Chest pain, pressure, or tightness on exertion. Stop and get assessed today.
- **Dyspnoea** — Breathlessness out of proportion to the effort. Stop.
- **Dizziness** — Light-headedness, feeling faint, or greying vision. Stop and sit down.
- **Palpitations** — A racing or irregular heartbeat that does not settle when you stop.
- **Focal Bone Pain** — A specific POINT of bone pain that worsens with each step -- the classic presentation of a stress fracture. Stop running; do not run again until it has been assessed.
- **Calf Swelling** — A swollen, painful calf, especially if it hurts at rest. Needs assessment.
- **Confusion** — Confusion, disorientation, or a headache with nausea late in a long run or race -- consider both heat illness and hyponatraemia. Stop; do not drink large volumes of plain water.

### Hydration: the risk is drinking too much

**Drink to thirst. Thirst is a good regulator and beating it is the actual risk here.**

This runs opposite to most apps' hydration prompts, deliberately. Exercise-associated hyponatraemia disproportionately affects **slow first-time marathoners who over-drink** — which will be you on race day — and it is one of the few genuinely life-threatening things that happens in mass-participation racing.

- Do not drink to a schedule or to a fixed millilitres-per-hour target.
- Do not drink at every aid station out of habit if you are not thirsty.
- Do not take NSAIDs before or during a long run or race.

Warning signs:

- Weight GAIN over a long run or race -- the clearest sign of over-drinking.
- Headache with nausea, puffiness in hands or face, or confusion late in a long effort.
- Feeling worse the more you drink.

- Past about two and a half hours, use a sodium-containing sports drink rather than plain water for most of your intake. Slow first-time marathoners who drink large volumes of plain water are the classic hyponatraemia presentation, and this is the single most useful change.
- If you can, weigh yourself before and after two long runs to learn your own sweat rate. Losing 1-2% of body mass is normal and fine; *gaining* weight means you drank too much.
- Carry fluid rather than relying on fountains, and practise drinking while running -- it is a skill.
- Caffeine, if you use it: 3-6 mg/kg is the well-evidenced range, so roughly 240-480 mg 30-60 min before the start. Rehearse it on a long run first; it is also a diuretic-adjacent GI risk for some people.

### What the app will never do

- Add load because a recovery score looked good. A single high HRV reading is a weak signal; the cost of a wrong upgrade is a lost week, the cost of a wrongly easy day is one easy day.
- Make you "make up" a missed session. Missed volume is gone. Carrying it forward converts a rest into a spike.
- Give you a streak, a leaderboard, or any other mechanism that rewards training when your body is saying rest.
- Coach off a heart rate it does not trust. Dropout and cadence lock-on are detected and reported, and the controller falls back to pace and feel rather than acting on a number that is probably your step rate.
