# Glucose cross-method IV — instrument transportability + an estimand boundary (NICE-SUGAR)

Transports the bulletproof cross-method assay-noise instrument to a **second analyte** (glucose) and, in doing
so, surfaces two reusable methodological principles the transfusion case could not test.

## Design
Two same-time glucose measurements: chemistry (50931, `lab_glu`) vs blood-gas (50809, `lab_glubg`), matched
within 1h → same blood, zero biological drift → **pure analytic discordance, σ = 16.2 mg/dL** (n=19,606 pairs).
D = short-acting regular insulin (inputevents 223258, the reflexive correctional dose) within 6h; band the
control glucose around the 180 mg/dL sliding-scale flag; Y = 90-day mortality (ICU) / in-hospital.

## Principle 1 — the instrument must be built on the measurement the clinician ACTS ON
Two directions of the same cross-method design give opposite first stages:

| instrument side | control | first stage (FS, F) | interpretation |
|---|---|---|---|
| Z = **blood-gas** flag | chemistry | **−0.07 to −0.17 (F 12–23)** — WRONG-SIGNED | ABG glucose is incidental; high-ABG patients are on insulin *drips*, not boluses |
| Z = **chemistry** flag | blood-gas | **+0.08 to +0.12 (F 15–26)** — correctly signed | insulin is dosed off the chem/POC value; discordance here is the real as-if-random noise |

**Lesson:** cross-method discordance is only a valid instrument when the flagged side is the measurement that
*drives the decision*. Using an arbitrary second assay (ABG glucose, which nobody titrates insulin to) produces
a strong-but-wrong-signed first stage — a trap the F-statistic alone does **not** catch (F was 12–23 for the
invalid side). The sign of the first stage is a required validity check. For Hb this was invisible because
transfusion decisions use CBC and ABG Hb interchangeably at the bedside; glucose exposes it.

## Principle 2 — a single flag ≠ NICE-SUGAR's estimand (reported, not hidden)
Correctly-built (chem-flag) flag-ITT, 90-day mortality:

| cohort (chem-flag, bloodgas control) | n | mort | naive | FS (F) | flag-ITT [95% CI] | balAge |
|---|---|---|---|---|---|---|
| ICU, band 150–220 | 3852 | 0.285 | −0.109 | +0.115 (26) | +0.028 [−0.014, +0.070] | +1.19 |
| ICU + diabetic | 1792 | 0.278 | −0.112 | +0.102 (9) | −0.007 [−0.070, +0.055] | +0.06 |
| ICU + non-diabetic | 2060 | 0.291 | −0.106 | +0.117 (15) | +0.058 [+0.001, +0.116] | +2.00 (imbalanced → gate) |
| ICU, band 140–240 | 5491 | 0.272 | −0.119 | +0.102 (25) | +0.018 [−0.020, +0.056] | +1.22 |

flag-ITT ≈ 0 across well-balanced strata. But this estimand is **"reflexive correctional insulin for glucose
> 180"** — which is what **both** NICE-SUGAR arms did (conventional target ≤180; intensive 81–108). NICE-SUGAR's
*harm* came from the intensive arm's **lower** bound (81–108) driving hypoglycemia, a graded target-range
contrast a single high-flag cannot represent. So the ≈0 here is exactly right for the decision it tests, and is
**not** evidence about NICE-SUGAR. The toolkit's estimand classifier correctly types glucose control as a
GRADED / target-range decision: testing it requires a **dose-intensity IV** (instrument insulin *intensity*),
not a single-threshold flag. The one marginal signal (non-diabetic, +0.058) fails the age-balance gate (+2.0 yr).

## Bottom line
The cross-method assay-noise instrument **transports** to glucose — but only when built on the acted-upon
measurement (a newly-exposed, required first-stage-sign validity check), and only for the single-flag decision
it actually identifies. NICE-SUGAR is a target-range trial, so the honest verdict is an **estimand boundary**:
the toolkit reproduces the (null) correctional-insulin decision and flags that the NICE-SUGAR contrast needs a
dose-intensity design — it does not over-claim a mortality effect it cannot identify.
