# Statistical Analysis Plan — arterial-line decision tool (pre-specified before modeling)

**Purpose.** Turn the A-LINES draft (doc 21) into a clinical decision tool that survives multiple rounds of
adversarial peer review. This SAP is written and committed *before* the modeling run so the derivation is not
retrofitted to the result. It is organized as a **threat model**: each attack a hostile reviewer would make,
and the pre-specified test that answers it.

## 0. What the tool is — and is NOT (frames everything below)
The tool is a **pre-operative risk-stratification instrument** that identifies, in the guideline gray zone,
patients at high risk of **cuff-missed arterial hypotension** — the specific harm C8 shows an arterial line can
surface and (via the treatment-gap mechanism) enable treating. It is **not** a causal claim that placing a line
improves outcomes; that is confounded by indication in any observational cohort and is reserved for the
prospective trial. This distinction is the single most important defense: we predict a *mechanistically-linked,
A-line-addressable risk*, and we do not over-claim benefit.

## 1. Threat model → pre-specified defense

| # | Reviewer attack | Pre-specified defense |
|---|---|---|
| T1 | "It's a risk model dressed as a decision tool; prediction ≠ benefit." | Explicit reframe (§0). Target is the A-line-addressable harm, not outcome-under-treatment. Benefit inference is deferred to the RCT; the observational job is risk-stratification + mechanism. |
| T2 | "A-lines go to sicker patients — confounding by indication destroys any benefit estimate." | We do NOT estimate placement→outcome benefit observationally. Where we touch causality (treatment-gap mechanism), we use within-severity matching + report an **E-value**. |
| T3 | "AUC 0.75 is in-sample / overfit." | **Subject-level 70/30 split** (no patient in both), 5-fold CV on train, **frozen coefficients** evaluated once on the held-out test set. Bootstrap 95% CIs. |
| T4 | "Your score is no better than ASA+age." | Pre-specified **nested incremental-value** sequence (ASA → +age → +duration → +surgery → +emergency) with ΔAUC 95% CIs + likelihood-ratio tests; report the parsimonious model if the full model adds nothing. |
| T5 | "Discrimination without calibration is useless." | Report **calibration slope/intercept**, calibration plot deciles, and **Brier score** on the held-out test set. |
| T6 | "So what if it discriminates — does using it help?" | **Decision-curve analysis (Vickers net benefit)** across threshold probabilities; operating point chosen where net benefit is maximized, not arbitrarily at ≥2. |
| T7 | "Derived and validated in one Seoul institution." | External validation of the **frozen** score on **VitalDB** (independent cohort, different granularity/scale, same city — honest partial); mechanism externally validated in eICU (154 US hospitals). US intra-op limitation stated. |
| T8 | "The composite-benefit endpoint is contaminated — infusions/labs happen *because* a line was placed." | Composite endpoint rebuilt on **pre-op-knowable predictors only**; realized intra-op benefits (B2 infusion, B3 labs) reported descriptively as *realized-benefit*, never as score inputs. |
| T9 | "Revealed practice defines Tier-1 — but your whole paper says practice is miscalibrated. Circular." | Tier-1 is defined by **established guideline indications**; revealed practice is reported as *corroboration that these are non-discretionary*, not as the definition. The claim "practice under-detects hypotension" (magnitude) and "practice already lines cardiac/neuro" (category) are logically independent — stated explicitly. |
| T10 | "Selection: the score is derived only in patients who got a line." | Acknowledged as the core limitation. Mechanism (cuff over-reads at low pressure) is **device physics, selection-independent**; sensitivity analysis shows discrimination is not carried solely by the sickest stratum (re-fit excluding ASA≥4 / excluding Tier-1 depts, already 0.654→0.661 stable). |
| T11 | "Duration isn't known pre-op." | Use **anticipated** duration (surgical booking estimate is standard in these tools); modeled as actual here with this stated as a calibration caveat; sensitivity model without duration reported. |
| T12 | "Arbitrary thresholds (MAP<65, ≥3 readings)." | Pre-specified from guidelines (MAP<65 = Perioperative Quality Initiative); ≥3 readings ≈ sustained (not a single artifact); sensitivity at MAP<60 and ≥1/≥5 readings. |
| T13 | "TRIPOD non-compliance." | Report per TRIPOD 2015 checklist items (population, predictors, outcome, sample size/events-per-variable, missing data, model, performance, validation). |

## 2. Population, target, features
- **Population:** INSPIRE co-recording ops (both cuff + arterial MAP recorded), n≈28k. Selection acknowledged (T10).
- **Primary target Y_missed:** cuff-missed arterial hypotension = arterial MAP<65 on ≥3 readings AND cuff never
  <65. Directly A-line-addressable; not outcome-conditioned.
- **Secondary target Y_harm:** Y_missed AND any adverse outcome (KDIGO AKI, in-hospital death, MINS, peak
  lactate ≥2). The benefit-proxy (doc-21 primary); rarer (~2%), so reported as secondary with wider CIs.
- **Candidate pre-op features:** ASA (ordinal), age (yr, and ≥65 cut), anticipated duration (min, >4 h cut),
  surgery category (data-refined high-yield set), emergency, sex, BMI. Sex/BMI pre-tested for redundancy (doc 21).
- **Events-per-variable:** with ≥500 events (Y_missed) and ≤6 candidate predictors, EPV ≫ 10 — no shrinkage
  crisis; still report penalized (ridge) sensitivity.

## 3. Modeling & validation (frozen sequence)
1. Subject-level 70/30 split (seed fixed in config-style constant).
2. On TRAIN: 5-fold CV logistic regression; nested incremental-value sequence (T4); parsimony pick by ΔAUC CI +
   AIC. Derive an integer **points score** from rounded coefficients for bedside use; verify points-score AUC
   tracks the continuous model (loss <0.01 acceptable).
3. Freeze coefficients + points map. On TEST (once): AUC + bootstrap CI, calibration slope/intercept + plot,
   Brier, decision-curve net benefit, operating-point selection.
4. External: apply frozen points score to VitalDB; report AUC + calibration.
5. Sensitivity: exclude Tier-1 depts + ASA≥4 (gray-zone-only), drop duration, MAP<60 target, ridge penalty.

## 4. Deliverables
- `docs/research/23_aline_tool_FINAL.md` — the validated tool + full TRIPOD results table.
- Manuscript update: Methods (SAP summary), Results (validation table + DCA), Box 1 already three-layer.
- `docs/research/24_aline_prospective_protocol.md` — the RCT/prospective-validation design that alone can
  establish benefit (closes T1/T2).
- Red-team pass (independent adversarial review) before finalizing.
