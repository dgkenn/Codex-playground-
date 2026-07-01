# Bulletproof-methodology checklist (per instrument) — any result publishable IFF every gate passes

**Operating principle (user directive):** for these 10 de-implementation questions the *finding* is
irrelevant — a rigorously-identified null is as publishable as an effect. So 100% of the effort is on making
identification survive hostile review. A result is reportable **only if every pre-specified gate below passes**;
a failed gate is itself a reportable methods finding ("this design is invalid here, and here is the test that
proves it"). No gate is optional and none is chosen after seeing the outcome.

## Universal battery (applied to EVERY instrument, every trial)
| Assumption / threat | Test | PASS gate | If it fails |
|---|---|---|---|
| Instrument relevance | first-stage coef + Olea–Pflueger effective F | F ≥ 10 (else weak-IV regime) | report reduced-form/ITT only; AR CIs; do not scale LATE |
| Weak-IV honest inference | Anderson–Rubin / Fieller CI (never delta-method as headline) | AR CI reported | — |
| Exogeneity (balance) | covariate battery ~ Z (age, sex, prior-severity proxies, comorbidity proxy) | all \|std diff\| < 0.05 | instrument invalid → drop or re-condition |
| **Residual confounding (the decisive one)** | **negative-control OUTCOMES** (≥20 dx the treatment cannot affect) → empirical null (Schuemie) | null centered at 0, sd small; target calibrated-p | **calibrate every estimate to the empirical null**; if null is shifted, the design is biased |
| Multiplicity (10 trials × outcomes) | pre-registered primary + BH-FDR across the family | FDR-controlled | — |
| Specification robustness | bandwidth × functional-form × window sensitivity surface | estimate stable across grid | flag as spec-dependent |
| Outcome timing | competing-risks (death vs discharge); 30/90-day, not just in-hospital | conclusions stable | LOS-confounded → use fixed-horizon |
| Pre-registration | thresholds/estimand/outcomes locked before unblinding (`DECONFOUNDING_PREREGISTRATION.md`) | logged | post-hoc = exploratory only |

## Instrument 1 — Assay-noise IV on an INDICATION flag (Mg/K, RBC, bicarb, glucose)
| Assumption | Test | PASS gate |
|---|---|---|
| Noise exogeneity \| true severity | balance on age & prior labs conditional on midpoint control | \|Δ\| < 0.05 (sim-verified midpoint is unbiased under equal-variance noise) |
| Equal draw variance (midpoint validity) | σ by draw context / inter-draw interval; symmetry check | Var(ε₁)≈Var(ε₂) | 
| Noise is analytic, not biologic drift | σ vs inter-draw interval; **lag-1 autocorr of detrended residuals** | autocorr ≈ 0; σ flat in Δt |
| No manipulation/heaping at the round flag | **McCrary/CJM density test**; histogram at reporting resolution | no density jump; else **donut hole** |
| Exclusion (flag ⇒ only this treatment) | **bundle-balance**: co-treatments, telemetry, LOS ~ Z | all ~ 0 (ward untestable: chartevents ICU-only → disclose) |
| Selection into ≥2 pre-tx draws | characterize excluded single-draw-then-treat cohort | difference bounded/disclosed |

## Instrument A — Assay-noise IV on a CONTRAINDICATION gate (PPI@plt/INR, steroid@eos, antipsy@QTc)
Same as Instrument 1, plus: gate exclusion is **stronger** (crossing e.g. QTc 500 does little except withhold the
drug) — but verify the gate isn't a multi-trigger (nothing else keyed to that exact cutoff in order-set logic).
QTc gate deferred (chartevents-only). Calculated values (HCO₃ from pH/pCO₂) have **correlated** error → use
directly-measured analyte or model the correlation.

## Instrument 3 — Provider-preference IV (PPI, benzo, opioid, antipsychotic, steroid, anticoag-ppx)
| Assumption | Test | PASS gate |
|---|---|---|
| Relevance (providers vary) | first stage: exposure ~ provider LOO rate; F | F ≥ 10; p10–p90 spread material |
| As-if-random patient↔provider | balance battery ~ provider tendency **within service** | \|Δ\| < 0.05 |
| **Exclusion (habit ⟂ other care)** — the weak point | (a) balance on mortality-predictors; (b) **negative-control outcomes → empirical null**; (c) restrict within service/unit | NC null centered at 0 |
| Monotonicity (no defiers) | first-stage sign stable across subgroups | same sign |
| Reverse causation (benzo/opioid) | **landmark/lag** (exclude baseline delirium; exposure before outcome window) | conclusions stable |
| Estimand well-defined | **fix the indication** (opioid→post-op within procedure; steroid→COPD exacerbation) | pre-specified cohort |

## Instrument C — Attending-rotation time-RDD (continued PPI/benzo/steroid)
| Assumption | Test | PASS gate |
|---|---|---|
| Handoff timing exogenous to trajectory | severity/vitals continuous through handoff (no jump) | no discontinuity in covariates at handoff |
| Relevance | continuation ~ receiving-service LOO propensity; F | F ≥ 10 |
| Exclusion (handoff changes only prescribing) | balance; NC outcomes; sending-service FE | NC null at 0 |
| Not confounded by scheduled care changes at handoff | check nothing else protocolized changes at transfer | — |

## Instrument B — Nurse-PRN administration IV — ❌ RETIRED (real-data negative result)
Tested on real emar and FAILED: non-administrations are uncharted (2.93M "Administered" vs 75k "Not Given" →
adminRate 0.97, no instrument variation), holds are non-discretionary, and patient-level aggregation is
LOS-confounded (balance ±30 yr). Not identifiable in MIMIC. See `REAL_RESULTS_NURSE_PRN_RETIRED.md`. Gestalt
drugs now route to provider-IV (elective) + contraindication-gate. (Original design retained below for record.)

### [RETIRED] original design — Nurse-PRN administration IV (benzo/opioid/antipsychotic)
`emar` is stream-filtered to due-dose decisions (medication class × event_txt Administered/Not-Given ×
enter_provider_id = administering nurse); instrument = nurse leave-one-out administration rate. Gates: relevance
F≥10; balance (age/severity ~ nurse tendency) ~0; nurse↔patient assignment as-if-random **within unit×shift**
(test acuity ~ nurse tendency); workload confounder controlled (unit census/acuity); NC-outcome calibration.
Refinement: restrict to PRN orders (join poe/prescriptions). Runner: `nurse_prn_iv.py` (auto-runs on emar).

## The certification logic (why any result is then publishable)
1. **RCT-anchored calibration:** run the toolkit on the SETTLED cases (RBC=TRICC/TRISS, glucose=NICE-SUGAR,
   antipsychotic=MIND-USA, COPD-steroid-duration=REDUCE). If it recovers the known answers *after* the gates +
   negative-control calibration, the method is certified — this is the reply to "CBI is observationally
   unsolvable." Only then do the vacuum trials (Mg/K, bicarb, benzo-sleep, opioid-post-op) carry weight.
2. **Triangulation:** each vacuum estimate must be bracketed by convergent bounds (`triangulate.py`); the anchor
   sitting inside the bracket is a falsifiable check.
3. **Empirical-null calibration on every estimate** (`negcontrol.py`) — the single most important defense against
   the reviewer's "residual confounding" attack: the negative controls *measure* the residual bias and correct for it.
4. A trial that **passes all gates and calibration** yields a publishable result whatever its sign; a trial that
   **fails a gate** yields a publishable methods result ("here is why this question is not identifiable this way").
   Either way the methodology — not the finding — is the product.
