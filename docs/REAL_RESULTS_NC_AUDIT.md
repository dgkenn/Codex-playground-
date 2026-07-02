# Negative-control audit across cross-method instruments — why NC calibration is mandatory (not optional)

A single, discriminating experiment run on all three cross-method assay-noise instruments (Hb, glucose,
potassium). For each analyte, at its valid-direction near-threshold cohort, we regress on the flag Z
(conditioning on the contemporaneous other-method control):
- the analyte's **own** reflexive treatment → **relevance** (first stage; should be strong)
- a physiologically **unrelated** treatment → **exclusion** (a clean instrument must NOT predict it)

NC choices avoid any physiologic link: Hb own=RBC, NC=KCl; Glucose own=insulin, NC=RBC; K own=KCl, NC=RBC
(insulin deliberately NOT used as K's NC — insulin drives K intracellularly, so it is causally linked).

## Result
| analyte | n | own-tx (relevance) | NC-tx (exclusion) | balAge |
|---|---|---|---|---|
| Hb | 4,383 | RBC **+0.054 (F 8)** | KCl +0.016 (SE 0.020) — n.s. | +0.44 |
| Glucose | 4,483 | insulin **+0.090 (F 21)** | RBC **+0.029 (SE 0.013) — FIRES** | +0.92 |
| Potassium | 10,787 | KCl **+0.126 (F 49)** | RBC **+0.024 (SE 0.010) — FIRES** | +0.76 |

## Reading (honest, including the power caveat)
1. **Relevance holds for all three** — each flag strongly predicts its own reflexive treatment. The
   acted-upon-measurement rule is confirmed a third time (glucose, K first stages are large and correctly signed).
2. **The NC-tx point estimate is small-positive for ALL three (+0.016 to +0.029)** — not zero. It reaches
   significance where the cohort is large (glucose, potassium) and is non-significant for Hb — but Hb's NC is
   **underpowered** (its cross-method cohort is the smallest, SE 0.020). We do **not** claim Hb is uniquely clean;
   the honest statement is that a small residual-acuity leakage is present in every cross-method flag and becomes
   detectable as n grows.
3. **Therefore: never test flag-ITT against zero.** The flag conditional on the control still carries a small
   severity/co-intervention signal (control imperfection + analyte-specific artifacts — for K, hemolysis reading
   falsely-high and tracking difficult draws; for glucose, stress-hyperglycemia and sample glycolysis). The
   estimand must be **calibrated against a negative-control empirical null** (Schuemie/Madigan), not against 0.

## Why Hb's emulation still recovered the TRICC null cleanly
The Hb NC leakage is smallest and non-significant, so raw ≈ calibrated — which is why the TRICC/TRISS flag-ITT
landed on the null without an explicit calibration shift. For glucose and potassium the leakage is real and
significant, so their raw flag-ITTs (glucose non-diabetic +0.058; potassium ICU-30d −0.042) are **exactly the
estimates that must be NC-calibrated before any interpretation** — and are not claimable on the raw scale.

## Implication for the toolkit
The negative control is a **required gate**, not a nicety: age-balance passed for every analyte here (|balAge|
≤ 0.9 yr) while the NC-tx fired for two of three. Balance certifies covariate overlap; only the NC certifies the
exclusion restriction. Every cross-method (and, by extension, every assay-noise/provider-preference) estimate in
this program is reported with its NC status, and a raw estimate whose NC fires is treated as **not yet claimable**
pending empirical-null calibration or an instrument that removes the leakage (e.g. hemolysis-screened K).
