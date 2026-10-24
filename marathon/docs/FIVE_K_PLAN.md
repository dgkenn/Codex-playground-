# The fastest safe route to a continuous 5K

The goal is a 5K without stopping, as soon as the body allows, then a faster one. The athlete asked
for an aggressive programme "as long as it adapts to my biofeedback". This is that programme, and
where in the app each piece lives.

## The idea in one paragraph

Heart and lungs adapt in weeks; bone and tendon take months and show nothing in any heart-rate
measure. The best current evidence on where running injuries come from is about **single sessions**.
In 5,200 runners followed for 18 months, injury risk rose when one run was more than about 10% longer
than the longest of the previous 30 days. Changes in weekly load were not associated with it
([Frandsen et al., BJSM 2025](https://blogs.bmj.com/bjsm/?p=11751)). The older weekly 10% rule never
had strong support for novices ([Nielsen et al., JOSPT 2014](https://vbn.aau.dk/da/publications/excessive-progression-in-weekly-running-distance-and-risk-of-runn)).

So the speed comes from two places:
- **Steps that do not lengthen the session** are taken fast. Most of the ladder is these: 4 × 5 →
  5 × 4, 6 × 4 → 8 × 3, 10 × 3 → 15 × 2 → 30 × 1 only remove walk breaks.
- **Steps that do lengthen it** are spaced out and capped.

Signals from the body (morning HRV, pain, the talk test) decide which pace applies.

## The route

| Step | Running | Total running | Kind |
|---|---|---|---|
| 1 | 1 min × 8 | 8 min | |
| 2 | 2 min × 7 | 14 min | ← here on 24 Oct |
| 3 | 3 min × 6 | 18 min | adds running |
| 4 | 4 min × 5 | 20 min | adds running |
| 5 | 5 min × 4 | 20 min | longer blocks only |
| 6 | 6 min × 4 | 24 min | adds running |
| 7 | 8 min × 3 | 24 min | longer blocks only |
| 8 | 10 min × 3 | 30 min | adds running · **first 2 km time trial** |
| 9 | 15 min × 2 | 30 min | longer blocks only |
| 10 | 30 min continuous | 30 min | longer blocks only · **Foundation complete** |
| 11 | 35 min continuous | 35 min | adds running (bridge) |
| 12 | 40 min continuous | 40 min | adds running · **the 5K step** |

At about 2.2 m/s, 40 minutes is a little over 5 km. The goal is recorded the first time 5 km falls
inside one running block. The app says so out loud at the moment it happens.

The heart-rate ceiling (165, the athlete's choice, moved by the talk test) still ends any block that
goes over it. Extra blocks make up the running, and a step counts as done when the full running time
is delivered (`progression.js`, `judgeHrSession`).

## How fast it moves: the traffic light

| Light | When | What a step up needs |
|---|---|---|
| **Green: fast track** | Nothing says wait | One good run on the step. A step that keeps the running time: 2 days after the last step. A step that adds running: 3 days after, at most two a week, and never more than **30%** over the longest session of the last 30 days. |
| **Amber: steady track** | HRV below its band (morning check), a niggle logged this week, or the last talk test was "hard" | Two good runs in a row, six days apart. |
| **Red: holding** | A pain pattern (the niggle log's hold), illness, or HRV well below its band for days | No step up. Stepping back still happens at once if a session goes wrong. |

**What "good run" means.** The judge's verdict: the full running time done, recovery to the walk
floor not more than a quarter slower than your recent median, and the session not ended by two
unrecovered walks.

**Projected dates.** All green, a run every other day, from step 2 on 26 October: the 5K step in
about **4 weeks** (late November). On the steady track: about **9 weeks** (late December). The goal
card shows both dates, recomputed from wherever you are.

The 30% cap is aggressive by design. Frandsen's lowest-risk band was +10%, and the 10–30% band
carried a higher injury rate. The athlete chose aggressive; the ladder's own steps are built to fit
inside 30%, and amber or red slows or stops it.

## Benchmarks

**Passive, every session** (no extra effort): time to the ceiling, the walk back down to the floor,
metres per heartbeat in the running blocks, and the 45-second heart-rate drop in the walks. On
24 October that drop was 23 bpm, up from 15–20 in earlier sessions.

**The 2 km time trial**, from step 8 (10-minute blocks), then every three weeks:
- **Warm-up:** 10 minutes easy.
- **The trial:** 2 km as fast as can be held evenly. The app calls each 500 m and ends the run at
  2 km by itself.
- **Why 2 km first:** it is the plan's own first performance test. For a beginner it takes about
  11–12 minutes, inside Riegel's validated range, and is a shorter all-out effort on unprepared
  tissue than a 5K.
- **It gives two numbers nothing else can:**
  - **A predicted 5K time:** Riegel, T5K = T2K × 2.5^1.06. 12:00 for 2 km predicts about 31:40.
  - **A measured maximum heart rate.** An all-out 2 km peaks within a few beats of maximum. If the
    peak beats the age formula's 187, the app uses the measured value, and the walk floor, the zones
    and the automatic ceiling move with it. That settles the question the 165 ceiling raised.
- **Stopping early:** a trial stopped before 2 km is not recorded.

**The 5K itself:** recorded the first time 5 km falls inside one running block.

**After the goal:** the time trials keep running every three weeks, and each one predicts the 5K
time. That makes "faster" measurable too.

## What can go wrong, and what the app does

| Situation | What the app does |
|---|---|
| A niggle | Log it: amber for a week. A pattern (repeated, focal, or getting worse during runs) turns red until two clean weeks. |
| A bad night or illness | The morning check turns amber or red, and the session that day drops its extra blocks. |
| Too hard | Answer "hard" on the talk test: the ceiling comes down 5 and the light goes amber. |
| A session that does not go well | The judge repeats or steps back at once, on any track. |

## Sources

- [Frandsen et al. 2025, BJSM blog summary](https://blogs.bmj.com/bjsm/?p=11751) ·
  [physiotutors summary](https://www.physiotutors.com/?p=26053)
- [Nielsen et al. 2014, JOSPT (Aalborg record)](https://vbn.aau.dk/da/publications/excessive-progression-in-weekly-running-distance-and-risk-of-runn)
- [Couch-to-5K completion and injury, IJERPH 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10487403/):
  27% finished a 9-week programme, and prior injury was the strongest risk factor. A rigid schedule
  is also a dropout risk, which is part of why this one adapts.
- [Vesterinen et al. 2016, HRV-guided training in recreational runners](https://jyx.jyu.fi/handle/123456789/50625)
- Riegel's endurance model, and the plan's own reasoning for the 2 km trial: `engine/marathon_engine/plan.py`,
  `_time_trial_2000m` and the BASE_1 gates.
