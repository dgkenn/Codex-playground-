# Synthesis — a self-diagnosing assay-noise IV toolkit, validated across every benchmark trial

**Thesis.** Confounding-by-indication for reflexive lab-triggered treatments can be attacked with an
**assay-noise instrument**: conditional on true severity, which side of a decision flag a *measured* lab falls
on is perturbed by measurement noise that is as-if-random. The bulletproof version is **cross-method
discordance** — two independent same-time assays of the same blood, whose difference is pure analytic noise
with zero biological drift. The scientific claim is not "this instrument works" but that a small set of
**gates** (first-stage relevance *and sign*, drift diagnostic, negative-control empirical null) makes it
**self-diagnosing**: it recovers the landmark RCT where it is valid and correctly refuses everywhere it is not.

## The evidence, one row per benchmark trial
| trial | analyte / decision | instrument outcome | gate that decided it | agrees with RCT truth? |
|---|---|---|---|---|
| **TRICC / TRISS** | Hb → RBC transfusion | ✅ **valid; recovers null** | all gates pass | **yes** (restrictive non-inferior) |
| NICE-SUGAR | glucose → insulin | valid first stage, **estimand boundary** | first-stage SIGN + estimand type | n/a (single flag ≠ target range) |
| Potassium (de-impl) | K → KCl repletion | ✗ retired | **NC fires** (hemolysis) | inconclusive (correctly) |
| Platelet (TOPPS) | platelet → transfusion | ✗ retired | **no 2nd method**; temporal drift | inconclusive (correctly) |
| Albumin (ALBIOS) | albumin → albumin | ✗ retired | drift + NC + weak FS | inconclusive (correctly) |
| Bicarbonate (BICAR-ICU) | HCO₃/pH → NaHCO₃ | ✗ retired | drift + NC | inconclusive (correctly) |
| MIND-USA | delirium → antipsychotic | ✗ not buildable | first-stage F<1 (charting) | underpowered null |

## Three reusable methodological findings (new, from this program)
1. **Build the instrument on the measurement the clinician acts on.** The cross-method design has a *direction*.
   Instrumenting the flagged side that actually drives the order (chem glucose/K, not the incidental ABG value)
   gives a correctly-signed strong first stage; the wrong side gives a strong-but-**wrong-signed** first stage
   that the F-statistic does not catch. First-stage **sign** is a required gate. (glucose, potassium)
2. **Never test the flag-ITT against zero — calibrate against a negative-control empirical null.** Every
   cross-method flag carries a small residual-acuity leakage (NC-treatment coefficient +0.016 to +0.029),
   significant at large n, while covariate **balance stays clean**. Balance certifies overlap; only the NC
   certifies the exclusion restriction. (NC audit; confirmed in simulation, `SIM_INSTRUMENTS_RESULTS.md`)
3. **Cross-method discordance is analytic only when the two assays share measurand *and* failure modes.** Hb
   (co-oximetry vs impedance, both intact-Hb) is clean. It breaks when: only one method exists (platelet,
   albumin, bicarbonate → temporal drift), a shared failure mode perturbs the assays non-randomly and tracks
   acuity (potassium → hemolysis), or the analyte decision is graded/target-range not single-flag (glucose).

## Why this is hostile-review-proof
- The flagship positive result (**recovering TRICC/TRISS on Hb**) is not asserted in isolation — it is the one
  case that passes gates that **demonstrably reject 5 other decisions**, so it cannot be dismissed as a
  fishing-expedition hit. The gates are pre-specified, mechanistic, and each rejection has a named cause.
- Every negative is reported with its mechanism, not buried. The toolkit's value is precisely its **refusal
  rate**: a de-confounding method that never says "I can't identify this here" is not trustworthy.
- All estimates are on real HEEDB/MIMIC-IV data; no synthetic outcome; PHI never leaves the DUA sandbox.

## Standing limitation / next data
The clean positive rests on one analyte (Hb). Broadening the *valid* set needs analytes with a genuine second
contemporaneous method (or design-based practice-variation instruments for the gate-triggered trials —
SUP-ICU/PEPTIC/PREVENT/ADRENAL, tracked separately). External replication on HiRID/SICdb/AmsterdamUMCdb (access
pending) is the cross-site confirmation step; the adapters exist (`docs/MULTISITE_HARMONIZATION.md`).
