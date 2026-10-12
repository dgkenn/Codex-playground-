# Ideas ledger — everything explored, status, and impact ranking

Complete log of every idea pursued in this project (VitalDB / MIMIC-IV / INSPIRE vasopressor work),
its current status, and an impact ranking against the bar: **an Anesthesiology-tier (or above)
publishable finding.** Status tags: **STANDS** (survived hostile review), **SUPPORTING** (feeds a
standing claim), **EXPLORATORY** (promising, not hardened), **NULL** (tested, no effect), **RETRACTED**
(found to be an artifact), **KILLED** (failed a decisive control).

## A. The spine — vasopressor requirement as a trait
| # | Idea | Status | Evidence / why |
|---|---|---|---|
| A1 | **Vasopressor dose-REQUIREMENT is a reliable, early, mortality-graded patient trait** (control-theory: MAP is regulated, the insult is in the dose) | **TRAIT RETRACTED (R2)** → encounter-level severity signal | Cross-encounter reliability ICC **0.074** (R2 settling test) kills "stable patient trait"; the 0.95 was within-drip autocorrelation. SURVIVES: within-encounter early→late 0.62; control-theory (VitalDB); fully-adj landmark OR 1.74, delta-AUC 0.024 (but = known VIS lit). RED_TEAM_ROUND2_SYNTHESIS.md |
| A2 | Phenylephrine replication of the requirement trait (pure α1, independent drug) | **STANDS** | split-half reliability 0.87 ≥ norepi. PRESSOR_REQUIREMENT_PHEN.md |
| A3 | Requirement onset shape / trajectory (does early shape predict late) | SUPPORTING | early→late 0.5–0.6. REQUIREMENT_ONSET_SHAPE.md, PRESSOR_REQUIREMENT_TRAJECTORY.md |
| A4 | Requirement parsimony (simplest sufficient metric) | SUPPORTING | median stable-epoch dose/kg is sufficient. REQUIREMENT_PARSIMONY.md |
| A5 | Requirement specificity / within-patient specificity | SUPPORTING | trait is patient-specific, not epoch-noise. REQUIREMENT_SPECIFICITY.md, WITHIN_PATIENT_SPECIFICITY.md |
| A6 | Control-theory premise: MAP CV << dose CV | **STANDS** (VitalDB) | within-patient MAP CV 0.09 vs dose CV 0.44 (ratio 5.2). The conceptual core. |

## B. Dose / load → hard outcomes
| # | Idea | Status | Evidence |
|---|---|---|---|
| B1 | **NEE total vasopressor load → mortality, PROSPECTIVE (landmark)** | **STANDS (upgraded)** | first-24h NEE, alive at 24h → subsequent death: age+lactate OR **2.27 [2.10,2.48]**, n=23,925, monotone. Reverse-causation rejected. FINDING4_LANDMARK.md |
| B2 | Requirement → AKI (KDIGO) | STANDS predictive / **KILLED causal** | OR 1.38/SD, gradient 38→61%; INSPIRE negative-control calibrates causal to OR 0.98. REQUIREMENT_AKI_CROSSVAL.md |
| B3 | Fluid-vs-pressor resuscitation balance → mortality | **EXPLORATORY (demoted)** | MIMIC OR 3.5 but not separable from B1 load; collider; null VitalDB. REDTEAM_PUB_FINDING3.md |
| B4 | MIMIC dose-response / early-warning / severity scores / SOFA-lactate | SUPPORTING | builds the beyond-severity case for A1/B1. MIMIC_*.md |
| B5 | Drug-agnostic mortality (norepi + phenylephrine) | SUPPORTING | A1 holds across agents. |

## C. Control-theory / MAP-regulation mechanism
| # | Idea | Status | Evidence |
|---|---|---|---|
| C1 | Personalized MAP target (HTE by patient) | **NULL** | no heterogeneity of treatment effect; LRT p≈0.88. MAP_TARGET_RESULTS.md, MAP_HTE.md |
| C2 | MAP threshold (universal harm threshold) | NULL/known | reproduces known <65 harm, no new signal. INSPIRE_MAP_THRESHOLD.md |
| C3 | CKD × MAP causal interaction | **KILLED** | dies on negative-control calibration. REDTEAM_CKD_MAP.md |

## D. A-line / waveform decision tools
| # | Idea | Status | Evidence |
|---|---|---|---|
| D1 | A-line picks fluid-vs-pressor ("independent levers") | **RETRACTED** | built on a degenerate constant column; real axes correlated r=+0.23. LEVER_DISCRIMINATION.md |
| D2 | Deep-learning A-line → responsiveness | EXPLORATORY (feasibility only) | ALINE_FLUID_VS_PRESSOR_DL.md |
| D3 | Predict ΔMAP from vasopressor dose (responsiveness) | **KILLED** | closed-loop titration reverse-confounds (dose↑ because MAP↓). PRESSOR_RESPONSE_MODELING.md |
| D4 | SVRI morphology from waveform | EXPLORATORY | feasibility + hostile review. SVRI_MORPHOLOGY_*.md |
| D5 | Recovery velocity (per-beat MAP recovery) | EXPLORATORY/specificity-limited | RECOVERY_VELOCITY_SPECIFICITY.md |
| D6 | Dynamic tone tracking / reperfusion dynamics | EXPLORATORY | DYNAMIC_TONE_TRACKING.md, REPERFUSION_DYNAMICS.md |
| D7 | Vasoplegia biomarker | **RELABELED** | not vasoplegia-specific → "vasopressor requirement". VASOPLEGIA_*.md |

## E. Quasi-experimental / confounding control
| # | Idea | Status | Evidence |
|---|---|---|---|
| E1 | Confounding-by-indication battery (E-value, within-severity, negative-control exposure) | SUPPORTING (load-bearing for A1) | E-value ~6; 8/8 strata; propofol OR 0.88 vs norepi 3.01. CONFOUNDING_*.md |
| E2 | Prescribing-preference IV (unit/caregiver) | **DEMOTED** | IV-OR > naive = invalid-instrument signature. CONFOUNDING_QUASI_EXPERIMENT.md |

## F. Actionability / decision-benefit
| # | Idea | Status | Evidence |
|---|---|---|---|
| F1 | Concordance → outcome (acting on the signal helps) | **NULL** | adjusted RD null, attenuates with N. CONCORDANCE_OUTCOME.md |
| F2 | Actionability / treatment-effect tests | **NULL** | no decision-benefit demonstrated. ACTIONABILITY_TESTS.md |

## G. Misc
| # | Idea | Status | Evidence |
|---|---|---|---|
| G1 | Combined biosignal / multitask embedding | EXPLORATORY | COMBINED_BIOSIGNAL.md |
| G2 | Discovery screen / phenotype clustering | SUPERSEDED | early unsupervised pass; superseded by the requirement trait. PHENOTYPES.md |

---

## Impact ranking (against the Anesthesiology-tier-or-above bar)

**#1 (HIGHEST) — The control-theory vasopressor-requirement paper: A1 + A6 anchored by the landmarked
B1.** This is the pick. Rationale:
- **Novelty (the differentiator for a top journal):** the control-theory reframing — intraoperative
  arterial pressure is feedback-regulated, so the hemodynamic insult is carried by the *requirement*
  (controller effort), not the regulated pressure. This is a genuinely new lens, not another risk marker.
- **Intraop-native:** lives in VitalDB + INSPIRE (anesthesiology cohorts); the home turf of Anesthesiology.
- **Now empirically bulletproof on the prospective axis:** the landmark test (B1) gives a clean,
  large (n≈24k), monotone, severity-adjusted PROSPECTIVE dose-response (OR 2.27 beyond lactate) — it
  is no longer just a contemporaneous association.
- **Most-hardened:** survived 3 adversarial rounds + an 8-agent publication panel; confounding argued
  on multiple fronts; honest scope already written.

**#2 — Landmarked NEE → mortality (B1) as a standalone.** Most robust single result, but "vasopressor
load predicts death" is less novel alone; strongest as the prospective backbone of #1, not separate.

**#3 — Requirement → AKI predictive risk-stratifier (B2).** A second hard outcome, but causal arm is
dead and it is derivative of #1; a secondary/companion result.

**#4 — Fluid-vs-pressor balance (B3).** Exploratory only; not separable from load; demoted.

**Not viable as primary:** all decision-tool / waveform ideas (D*) are feasibility/retracted/killed;
MAP-target HTE (C*) is null; actionability (F*) is null. These are honest negative results that
*strengthen* #1 by bounding its scope (it is risk-stratification, not a decision tool — stated, not hidden).

## The pick → next step
Selected finding to drive to 100%: **the control-theory vasopressor-requirement trait paper (A1+A6+B1).**
Now entering iterative hostile-review rounds (RED_TEAM_ROUND_*.md) until a full round surfaces no new
conclusion-changing hole. Target framing for the paper is in REDTEAM_PUBLICATION_VERDICT.md (Finding 1
+ landmarked Finding 4).

---

## OUTCOME after 4 hostile-review rounds (final, see VASOPRESSOR_PROJECT_FINAL.md)
| Round | What it killed / found |
|---|---|
| R1 | "trait" is not the novelty (dose→mortality IS the VIS literature); reframed to reliability-first |
| R2 | reliability-as-trait KILLED: cross-encounter ICC **0.07** (the 0.95 was infusion autocorrelation) |
| hunt | pivoted to a genuinely new angle: **occult dependence at normal pressure** (ICU) |
| pull | streamed 30 GB MIMIC chartevents → per-stay MAP (7.58M rows, 76,500 stays) — clean |
| R3 | occult-dependence SURVIVES: collider test passed, MICE OR **2.04 [1.85,2.24]**, invasive-only 3.10, reproduces exactly |
| R4 | but INCREMENTAL: "information gap doubles" is **72% restriction-of-range artifact**; novel at-target move buys only **+0.031 AUC** over VIS/VDI/BPRI |

| # | Idea | Final status |
|---|---|---|
| H1 | **Occult vasopressor dependence at normal pressure (ICU)** | **REAL but INCREMENTAL** — CCM/ICM supporting analysis, not standalone top-tier. Hardened (MICE OR 2.04, E-value 3.0/2.7, within-severity 3/3, single-pressor 1.64, collider passed). ICU_OCCULT_DEPENDENCE.md, REDTEAM_R3/R4_*.md |

**Final verdict:** the vasopressor space yields a defensible CCM/ICM paper but NOT an Anesthesiology-tier-
or-above *novel* standalone finding. Data ceiling reached. **User decision: PIVOT to new data/topic
(option 3).** Reusable assets for any pivot: the disk-safe MIMIC stream-filter pattern, the landmark +
MICE + collider-test machinery (finding4_landmark.py / icu_occult_dependence.py), and the per-stay MIMIC
MAP extract. Do NOT re-mine the vasopressor→outcome vein — it is exhausted for top-tier novelty.
