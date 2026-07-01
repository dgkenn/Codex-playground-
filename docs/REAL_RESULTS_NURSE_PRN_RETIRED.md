# Nurse-PRN administration IV (instrument B) — RETIRED on real data (honest negative result)

Instrument B was the most speculative of the toolkit (flagged as novel/untested). On real MIMIC-IV emar it
**fails**, for a fundamental data reason, not a coding bug. Reporting it transparently.

## What we saw (emar, benzo/opioid/antipsychotic)
| class | adminRate | nurseSpread | FS | RF(mort) | balAge |
|---|---|---|---|---|---|
| benzo | 0.968 | 0.029 | +0.75 | −0.89 | +27.8 yr |
| opioid | 0.978 | 0.019 | +1.14 | −2.39 | −32.0 yr |
| antipsy | 0.931 | 0.046 | +0.78 | −0.09 | +36.5 yr |

RF magnitudes are numerically nonsensical (a −2.4 mortality "coefficient"), the instrument has near-zero
variance, and balance is off by ±30 years. The design is degenerate.

## Why (three real problems)
1. **The give/hold denominator is largely unobserved.** emar charts doses that were GIVEN: 2.93M
   "Administered" vs 75k "Not Given" (~2.5%). A PRN dose a nurse decides not to give usually generates no
   record → the counterfactual the instrument needs is missing → administration rate ≈ 0.97 with tiny variation.
2. **The "Not Given" holds that exist are mostly non-discretionary** (NPO, procedures, patient refusal), not the
   exogenous nurse-workload variation the design requires.
3. **Patient-level aggregation is confounded.** Instrument = mean administration-rate of the nurses a patient
   drew; sicker/longer-stay patients accrue more emar events across more nurses, so the aggregate correlates with
   LOS/severity → balAge ±30. The balance gate correctly rejects it.

## Decision
**Retire the nurse-PRN administration-decision IV in MIMIC-IV.** It is not identifiable when non-administrations
are uncharted. Possible salvage (future work, NOT pursued now): a *dose-intensity* estimand (PRN doses given per
patient-day, instrumented by nurse tendency) with event-level modeling clustered on patient and explicit
LOS/acuity control + emar_detail hold-reason filtering — but this is a different, weaker design and does not
rescue the administration-decision version.

## Consequence for the toolkit
The gestalt-triggered drugs (benzo, opioid, antipsychotic, PPI, steroid) now rely on: **provider-preference IV
in the elective/low-acuity stratum** (validated — recovers the antipsychotic MIND-USA null) and the
**contraindication-gate assay-noise IV** (PPI@platelet/INR, steroid@eos). Instrument B is removed from the
active toolkit. This is the bulletproof battery working: a speculative instrument was proposed, tested, and
honestly rejected on its balance/variance gate rather than force-fit.
