# Challenge D — the transport prediction, committed before the numbers exist

*Written 2026-08-03 while the MIMIC extraction is still streaming. The point of writing it now is that
once the transport result is visible the prediction cannot honestly be made.*

## What is being predicted, and why a prediction is required

`PROGRAMME_ROADMAP.md` states the rule the programme has accumulated:

> **transport succeeds when the construct matches and fails when it does not, and construct match is
> specifiable in advance**

and immediately flags its weakness:

> **The rule is currently a RETRODICTION over four observations.** `CLAUDE.md`'s cadence section is
> explicit that a finding which explains the existing set is worth little until it makes a falsifiable
> forward prediction.

The four observations it was built from: E131 (disjoint BCI predictors), E123 (a muscle association that
did not survive a montage change), the PK validation (per-case R² 0.9990 against cross-patient MDAPE
54.9 %), and E129 (succeeded precisely where the construct matched Blankertz's). This file makes the
prediction that turns it into a testable claim.

## The transport being tested

E122's pharmacology arm on DOSE-I, carried to MIMIC-IV. E122 measured what there is to transport: an
exposure model reaching **out-of-bag rho 0.4595** against MOAA/S, climbing from 0.1755 for cumulative dose
to 0.4263 once the 8-rate kinetic basis was used.

| axis | DOSE-I | MIMIC-IV | matched? |
|---|---|---|---|
| dosing | intermittent **bolus** | **infusion** | NO |
| drugs | propofol alone | propofol + midazolam + ketamine + dexmedetomidine + opioids | NO |
| state scale | MOAA/S 1–5, observer-rated | RASS −5…+4, observer-rated | partial — both observer-rated ordinals |
| cadence | every few minutes | a few times a day | NO — two orders of magnitude |
| horizon | ~20 minutes | days | NO |
| population | elective endoscopy, healthy enough for day-case | critically ill ICU | NO |

**Five of six axes do not match.** The rule therefore predicts transport FAILS.

## The prediction, stated as a number so it can be wrong

**PRIMARY PREDICTION: the DOSE-I-shaped exposure model will reach out-of-bag rho BELOW +0.25 against RASS
in MIMIC-IV** — i.e. it will lose more than half of E122's 0.4595, and will land closer to E122's
kinetics-free L0 rung (0.1755) than to its best rung.

Three ways this can be wrong, and each is a different finding:

1. **rho ≥ 0.40** — transport is essentially intact despite five mismatched axes. The construct-match rule
   is then wrong, or "construct" means something narrower than the six axes above, and D's central claim
   collapses. This is the outcome that costs the most and it is listed first.
2. **0.25 ≤ rho < 0.40** — partial transport. The rule is directionally right and its binary framing is
   too coarse; what would be needed is a *graded* notion of construct distance, which this table does not
   supply.
3. **rho < 0.25** — as predicted.

**A SECOND PREDICTION, which discriminates better than the first.** If the rule is right for the reason it
claims — construct mismatch rather than mere noise — then within MIMIC the *kinetic elaboration* should
buy less than it did in DOSE-I. E122's basis more than doubled cumulative dose (0.1755 → 0.4263) because
bolus dosing makes Ce non-monotone. Under infusion at ICU timescales, cumulative dose and concentration
order cases almost identically, so:

> **the L0 → L2 gain in MIMIC will be under half the DOSE-I gain of +0.2508.**

This is the sharper test because it predicts a *mechanism*, not just a magnitude, and because E121 already
found exactly this pattern on VitalDB maintenance data — which is the closest existing analogue.

## Gates

* **G1** ≥ 500 ICU stays with ≥ 3 RASS observations and a non-empty sedative record.
* **G2 THE OUTCOME MUST BE ALIVE.** RASS must vary within stays. A cohort of uniformly alert-and-calm
  patients has nothing for any exposure model to predict, and a null would be about the cohort.
* **G3 NEGATIVE CONTROL** — a Gaussian exposure column must not predict RASS.
* **G4 PARSING.** RASS is stored as free text with leading whitespace (`" 0  Alert and calm"`,
  `"-5 Unarousable, no response to voice or physical stimulation"`). The numeric parse must be validated
  against the full observed value set and the count of unparsed rows reported, not silently dropped.

## What has already been seen, disclosed (rule 41)

The extraction is partially complete and these were observed while checking it was working: 35,648 rows
at last look, 472 stays at 20,474 rows, split 11,262 RASS / 9,212 goal-RASS, and the RASS value
distribution (modal " 0  Alert and calm" at 5,199 of 11,262, full scale −5…+2 represented).

**None of that is the transport statistic.** No exposure model has been fitted against RASS, and the
prediction above is a number that the observed marginals cannot inform.

## The item that makes this worth more than a transport test

`228299 Goal Richmond-RAS Scale` is charted at **82 %** of the rate of RASS itself. E127 destroyed E126 by
showing the residual LEADS the concentration direction — clinicians withhold drug from a patient who
already looks deeper than intended, which manufactures a hysteresis signature containing no hysteresis.
DOSE-I records no target, so that confound could be detected and never removed. **MIMIC charts intent,
which makes it conditionable.** That is a Challenge C repair carried out on Challenge D's data, and it is
noted here so it is not later presented as a lucky find.
