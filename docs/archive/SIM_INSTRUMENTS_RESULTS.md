# Known-truth simulation of the new instruments — provider-IV & nurse-PRN (bulletproofing)

Data-free Monte Carlo (`docs/sim_instruments.py`) validating the estimator code AND stress-testing the
diagnostics, before trusting any real-data output. This is the same discipline that caught the fatal
leaky-control bug in the flagship assay-noise design.

## Result 1 — Nurse-PRN administration IV: VALIDATED
True administration effect −0.030 → recovered **LATE −0.0267** (FS +0.99, balance clean). The patient-level
aggregation (mean of leave-one-out nurse-administration rates over the nurses a patient drew) is unbiased.
Instrument B is sound.

## Result 2 — Provider-preference IV: NEGATIVE CONTROLS ARE MANDATORY (balance is not enough)
Setup: true treatment effect = 0; a knob `rho` correlates provider *preference* (the instrument) with provider
*care-quality* (which affects the outcome directly = an exclusion-restriction violation). Provider quality is a
**provider-level** trait, orthogonal to patient severity — so patient covariate balance cannot see it.

| condition | LATE (truth 0) | covariate balance (age) | NC-outcome coef |
|---|---|---|---|
| rho=0 (exclusion holds in population) | +0.017 | +0.23 (looks clean) | **+0.018** |
| rho=0.5 (exclusion VIOLATED) | +0.113 | +0.23 (still looks clean) | **+0.111** |

**The finding:** the negative-control-outcome coefficient tracks the LATE bias **almost exactly** in both cases
(+0.018≈+0.017; +0.111≈+0.113), while **balance-on-covariates stays clean regardless**. So:
1. Covariate balance CANNOT detect provider-quality exclusion violations (the dominant failure mode of
   provider-preference IV) — a design that "passes balance" can still be badly biased.
2. The negative-control outcome DOES detect it, and because the NC coefficient ≈ the bias, **empirical-null
   calibration (`negcontrol.py`) removes it** — recovering the true null.
3. Even at rho=0, finite provider count induces a small spurious preference↔quality correlation → small bias,
   also caught by the NC. NC calibration corrects residual/finite-sample bias too.

**Implication (now locked into the checklist):** for provider-IV (and by extension attending-RDD and nurse-PRN,
any preference-type instrument), **negative-control-outcome calibration is a required gate, not an optional
robustness check.** Balance is necessary but far from sufficient. This is itself a publishable methods point:
"why preference-instrument studies that report only covariate balance are not bulletproof."

## Status
Both new estimators validated against known truth; the mandatory-NC result strengthens the bulletproof battery.
Next real-data step consumes `diagnoses_icd` (streaming) to build the ~20–50 negative-control-outcome panel and
calibrate every provider-IV / gate / RDD estimate.
