# Marathon Coach

A private iPhone coaching app that takes one person — who has not yet run a 5K — to a marathon,
driven by a Polar Verity Sense armband and the nightly HRV/sleep data the
[SleepController](https://github.com/dgkenn/SleepController) already collects.

One user. No accounts, no server, no subscription, no social features. That constraint is what makes
the interesting parts possible: the plan can be genuinely personal, the readiness model can lean on a
year of one person's sleep data, and nothing has to be dumbed down for onboarding.

---

## Read these first

| Document | What's in it |
|---|---|
| **[docs/PLAN.md](docs/PLAN.md)** | Your week-by-week plan. Generated from the engine, not hand-written. |
| **[docs/RESEARCH.md](docs/RESEARCH.md)** | The evidence base, including the ~30 claims the fact-checkers rejected and the code changes that followed. |
| **[docs/APP_LANDSCAPE.md](docs/APP_LANDSCAPE.md)** | What Runna/Garmin/Strava/WHOOP and a dozen others get right, what to steal, what to refuse to build. |
| **[engine/README.md](engine/README.md)** | The tested science core. |

---

## How it's put together

```
marathon/
├── engine/                  Python. The science, tested. 359 tests.
│   └── marathon_engine/
│       ├── physiology.py    HR zones, VDOT/Daniels paces, Riegel, Minetti grade, WBGT, decoupling
│       ├── load.py          TRIMP, session-RPE, hrTSS, EWMA ACWR, monotony/strain, ramp caps
│       ├── signal_quality.py Beat-interval cleaning, HR gating, cadence lock-on detection
│       ├── readiness.py     lnRMSSD baseline + SWC band, sleep/RHR/subjective integration
│       ├── assessment.py    The week-1 diagnostic battery and its re-tests
│       ├── plan.py          Gate-based periodisation, weekly templates, taper
│       ├── adapt.py         Readiness downgrades, shift-rota rescheduling, weekly replanning
│       ├── realtime.py      The in-run controller
│       ├── safety.py        Screening, bone loading, hydration, return-to-run
│       ├── progress.py      Pain trends, training status, anti-streak consistency
│       └── report.py        Generates docs/PLAN.md
└── ios/MarathonCoach/
    ├── Sources/Sensors/     PolarPMD.swift (protocol codec), VeritySensor.swift (CoreBluetooth)
    ├── Sources/Engine/      Physiology.swift, InRunController.swift — ports of the Python
    ├── Sources/Views/       RunView.swift and the rest of the UI
    └── Tests/               PolarPMDTests.swift
```

### Why the science lives in Python

The decisions that matter — what pace to prescribe, when to add volume, when to say stop — are
arithmetic over published formulas. Arithmetic can be tested; a SwiftUI view cannot be tested on a
Linux box. So the arithmetic lives in `engine/` with 359 tests against published worked examples, and
the iOS app ports only what has to run on the phone.

That split earns its keep. The tests caught, among others:

- **A pace-calibration error that would have wrecked every easy run.** Daniels *describes* Easy as
  "59–74% of VO2max", but his printed table for VDOT 50 back-solves to ~57–62.5%. Taking the prose
  literally puts the fast end of "easy" faster than his own *marathon* pace.
- **An ACWR cut that didn't cut**, defeated by the exact mathematical coupling the module documents.
- **A rep-quality check that would have aborted nearly every interval session**, because it compared
  end-of-rep HR against a recovery threshold — and a VO2max rep ends near 90% of reserve by definition.
- **A rebuild rule that jumped to 105% of plan after a zero-volume week** — the largest increase the
  engine could emit, in the situation calling for the smallest.

Plan generation stays in Python and ships as a bundled JSON resource: it runs once a week, not once a
second, and duplicating it would double the surface where the two implementations could drift.

### The plan document is generated

```bash
cd engine && python -m marathon_engine.report > ../docs/PLAN.md
```

A hand-written plan drifts from the code the first time a constant changes, and then there are two
plans — the one in the document and the one the app follows. Which is worse than having no document.

---

## The four ideas that make this different from a run tracker

**1. Gates, not a calendar.** No fixed race date means phases can advance on *measurements*. A
calendar plan has to guess your adaptation rate and then either rushes you into a stress fracture or
holds you back for months. Every phase has checkable criteria, a minimum number of weeks (because bone
adapts over months while fitness adapts in weeks), and a stall review that stops adding load and runs a
diagnostic instead.

**2. The week-1 test is submaximal, and it pays for itself.** You have no race time and no measured
HRmax, and a maximal test in week 1 measures discomfort tolerance on untrained tissue. So week 1 is a
graded walk-jog ramp. It yields your HR/speed line, a talk-test threshold that *pins* your Z3/Z4
boundary, cadence at each speed, and — crucially — the **bpm-per-km/h slope that becomes the
feedforward gain in the real-time controller**. That is why the controller can be tuned to you rather
than to a guessed constant.

**3. The controller predicts, it doesn't react.** Heart rate responds to a speed change as a
first-order system with a ~45 s time constant, so the HR you can see belongs to the speed you were
running half a minute ago. Reacting to it directly oscillates: slow down, HR keeps rising, slow down
again, end up walking, HR drops, speed up, repeat. This controls on `HR_ss = HR + τ·dHR/dt` with a
deadband, a confirmation window, and cue rate limiting. It also tells the difference between cardiac
drift on a hot long run (explain once, widen the band) and actually running too hard (cue a correction).

**4. It knows what it can't see.** Optical HR during running fails in a specific and dangerous way:
the algorithm locks onto step frequency and reports a rock-steady, plausible heart rate that is
actually your cadence — and because it has *lower* variance than real data, any smoothness-based
quality check prefers it. The app streams the armband's accelerometer specifically to detect this, and
treats "heart rate unavailable" as a first-class state rather than coaching off a number it doesn't
trust.

---

## What the fact-checking changed

Six literature reviews, each attacked by a separate fact-checker. **34 of 41 claims in one dossier and
23 of 33 in another came back wrong or overstated.** The corrections that changed code:

- **Long-run cap 180 → 150 min.** Daniels' actual rule is the lesser of 25% of weekly volume or 150
  minutes. The widely repeated "3 hours" exceeds it by 20%, in the population least able to absorb it.
- **The sensor needs two modes.** Enabling PPI throttles heart rate to one update per 5 seconds
  (confirmed by SleepController's own `PPI_HR_UPDATE_S = 5.0`). A run-time PPI stream would have fed
  the 1 Hz controller data 5 seconds stale *while appearing to work*. Runs now use the standard HR
  service plus accelerometer; PPI is reserved for resting HRV.
- **HRV sources must never be mixed.** HealthKit exposes only SDNN — there is no RMSSD type and no
  beat-interval type, and SDNN cannot be converted. Device and posture each shift lnRMSSD by more than
  the band being detected, so a mixed series flags a spurious suppression on every switch.
- **The "primed → add load" band was invented.** The anchor trials prescribed hard work when HRV was
  within *or above* range. `primed` and `normal` now take the same action.
- **Three whole subsystems were missing**: pre-participation screening, a bone-loading model, and
  hyponatraemia guidance. See below.

Full list, including the fabricated statistics, in [docs/RESEARCH.md](docs/RESEARCH.md).

---

## Safety

Advisory software. Not a medical device, and it cannot detect a cardiac event.

- **Screening comes first.** The ACSM 2015 algorithm runs before anything else and is a hard gate.
  It exists to find the few people who need clearance, not to put a barrier in front of exercise.
- **Bone is the blind spot, and it has its own model.** TRIMP, ACWR, HRV and readiness are all
  cardiovascular or autonomic — bone appears in none of them. It remodels over *months* while aerobic
  fitness improves in *weeks*, which is how you can be green every morning and still be twelve weeks
  into building a tibial stress fracture. For the first ~20 weeks the app argues for frequency over
  session length and treats focal bone pain as a stop, not a niggle.
- **Hydration guidance runs opposite to most apps'.** Exercise-associated hyponatraemia
  disproportionately affects slow first-time marathoners who over-drink — which is precisely your race
  day profile. The primary rule is drink to thirst, never to a schedule, and weight *gain* over a long
  run is the warning sign.
- **Pain rules are explicit.** 0–2 acceptable, 3–5 holds volume, above 5 stops the run. Pain the
  *morning after* is treated as the most informative signal there is, because it is, and it is the one
  most often dismissed.

## What it will never do

- Add load because a recovery score looked good.
- Make you make up a missed session. Missed volume is gone; carrying it forward turns a rest into a spike.
- Give you a streak, a badge, or a leaderboard.
- Coach off a heart rate it doesn't trust.

---

## Status

**The Python engine is complete and tested** — 359 tests, all passing, runnable now.

**The iOS app is written but not compiled.** There is no Swift toolchain in this environment, so
`PolarPMD.swift`, `VeritySensor.swift`, `Physiology.swift`, `InRunController.swift` and `RunView.swift`
have not been built or run. Expect to fix compile errors on first open in Xcode. The protocol codec is
a faithful port of hardware-tested Python and carries its regression tests, but "faithful port" is a
claim verified by review, not by execution.

Still to build: HealthKit workout writing, CoreLocation pace fusion with `speedAccuracy` gating,
persistence, the SleepController bridge client, and the non-run screens.

## Running the engine

```bash
cd marathon/engine
python3 -m pip install -e '.[dev]'
python3 -m pytest -q                              # 359 tests
python3 -m marathon_engine.report > ../docs/PLAN.md
```
