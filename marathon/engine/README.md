# marathon-engine

The tested science core for the coaching app. Pure Python, stdlib only, no I/O — every module is a
set of pure functions and dataclasses so that the training logic can be verified without a phone,
a sensor, or a running shoe.

## Why this exists separately from the iOS app

The decisions that matter (what pace to prescribe, when to add volume, when to say stop) are
arithmetic over published formulas. Arithmetic can be tested; a SwiftUI view cannot be tested here.
So the arithmetic lives here with 266 tests against published worked examples, and the iOS app is a
faithful port of the parts that must run on the phone.

## Modules

| module | what it owns |
|---|---|
| `physiology.py` | HR zones, VDOT/Daniels paces, Riegel prediction, Minetti grade adjustment, WBGT, decoupling |
| `load.py` | Banister/Edwards TRIMP, session-RPE, hrTSS, EWMA ACWR, Foster monotony/strain, ramp caps |
| `signal_quality.py` | Beat-interval cleaning (Malik, Polar blocker bits), HR gating, **cadence lock-on detection** |
| `readiness.py` | lnRMSSD baseline + SWC band, sleep/RHR/subjective integration, daily band and its overrides |
| `assessment.py` | The week-1 diagnostic battery, HR-speed fit, seed VDOT, structural screen, progress re-tests |
| `plan.py` | Gate-based periodisation, weekly session templates, volume/long-run progression, taper |
| `adapt.py` | Readiness downgrades, shift-rota rescheduling, next-week replanning |
| `realtime.py` | The in-run controller: lead-compensated HR control, drift discrimination, cue scheduling |

## Running the tests

```bash
cd marathon/engine
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
```

## The claims these tests actually check

Not "the code runs" — these check that the science is transcribed correctly:

- `test_training_paces_reproduce_daniels_table_vdot50` — the prescribed E/M/T/I paces match Daniels'
  printed tables. This one matters more than any other test in the suite: it caught that taking
  Daniels' prose "59–74% VO2max" literally makes the fast end of *easy* faster than *marathon* pace.
- `test_minetti_minimum_is_downhill_not_flat` — the gradient polynomial reproduces Minetti's actual
  finding, that gentle downhill running is cheaper than flat.
- `test_controller_does_not_oscillate` — simulates an obedient runner with a first-order HR response
  and asserts the controller converges in ≤6 cues over 20 minutes instead of hunting.
- `test_genuine_hr_that_happens_to_equal_cadence_is_not_flagged` — the cadence-lock detector's
  false-positive case, which a proximity-only check would fail.
- `test_acwr_reports_insufficient_history_for_a_beginner` — ACWR is meaningless with zero chronic
  load, so it must not gate a beginner's first weeks.
- `test_missed_volume_is_never_carried_forward` — the rule that stops a disrupted week becoming next
  week's load spike.

## Honesty notes

Where the evidence is weak, the code says so rather than dressing a convention up as a finding:
`ACWR_CAUTION` states plainly that the acute:chronic ratio's "sweet spot" has failed to replicate;
`MAX_WEEKLY_RAMP` records that the 10% rule was never supported by a trial (Buist 2008) and explains
why a cap is still imposed; cutback-week cadence is labelled convention; `heat_pace_factor` is
labelled a heuristic.
