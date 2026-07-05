# Overnight candidate hunt — new top-tier (NEJM/Nature/JAMA) candidates

Autonomous overnight run. Goal: surface MORE finalized top-tier candidates beyond the calcium flagship.
Strategy: the MIMIC/eICU measurement-bias seam is tapped for new disparity wins → expand to (a) ED-observable
measurement-bias-drives-ACTION studies (MC-MED — breaks the ICU paired-design wall), (b) new non-tautological
(mechanism+reference+driver) triples in less-mined data, (c) treatment-effect heterogeneity decision rules,
externally validated. Each candidate: feasibility-gate → run → red-team → log honest verdict.

## Standing deliverable (context)
- **Calcium flagship** — validated, submission-adjacent (5-cohort mechanism; MIMIC+eICU racial reclassification;
  reconciled cohort N=23,449 OR 1.65; 63% of high-Ca ICU flags false; globulin-fix honestly bounded). This is the
  #1 candidate; overnight work seeks ADDITIONAL ones.

## Ranked backlog (idea-generation engine, sonnet) — predicted win-likelihoods
| rank | candidate | class | dataset | pred | fatal-flaw check |
|---|---|---|---|---|---|
| **1** | **Benign ethnic neutropenia (BEN) → ED ANC-threshold actions** | wall-breaker | MC-MED | **0.45** | none fatal; repeat-visit CBC density is the risk. Executes ledger #9f lesson (BEN reversed in ICU = wrong substrate; ED is right) |
| 2 | POC glucose-meter Hct interference → ED insulin/dextrose action | depth (won mechanism, ledger #15) | MC-MED | 0.40 | none fatal; safest bet; single-method action layer is the fresh piece |
| 3 | Occult hypoxemia → O2-flow action timing + Perf specificity control | wall-breaker | MC-MED | 0.30 | crowded (Fawzy 2022 JAMA-IM); narrow wedge = titration-timing + perfusion-index dissociation |
| 4 | ED triage-acuity (ESI) miscalibration vs bounce-back-admit ground truth | decision-threshold | MC-MED | 0.25 | active scoop risk (2025 arXiv) |
| 5 | Indirect-ISE Na/Cl exclusion → ED fluid/admit action | new triple | MC-MED | 0.15 | tautological direction + thin driver prevalence — gate-check before compute |
| 6 | Ketamine vs opioid ED analgesia HTE | treatment HTE | MC-MED+MIMIC-ED | 0.12 | confounding-by-indication (matches 3 prior decision-tool failures); needs a protocol-change instrument |
| 7 | PPG perfusion-index racial artifact | novel construct | MC-MED | 0.10 | no mechanism anchor; side-query only |

## Candidate ledger (this run — verdicts as they complete)
| # | Candidate | Feasibility | Verdict | Status |
|---|---|---|---|---|
| C1 | BEN → ED ANC actions (MC-MED, 97,058 ANC / 92,908 visits) | strong (real data) | **STRIKE-OUT on top-tier harm.** BEN signature CONFIRMED (Black ANC left-shifted, median 4540 vs White 5330, concentrated in MILD range; %<1500 3.2% vs 2.1% but %<1000 LOWER 0.9% vs 1.2%). Exposure disparity REAL (Black low-ANC flag 3.1% vs 1.7%, **ratio 1.85**, non-overlapping CIs). **BUT the over-workup harm hypothesis is FALSIFIED in the predicted direction:** at matched low ANC, Black patients get LESS reactive workup (repeat-CBC-after-ANC 9.8% vs 21.5%, isolation 41% vs 50%, culture 50% vs 63%) and lower admission (11.8% vs 19.1%) — most parsimoniously appropriate BEN recognition; action layer also confounded by septic presentation. Predicted 0.45 → actual: confirmatory exposure disparity, no top-tier harm | **DONE — NOT a candidate (exposure disparity real but textbook; harm falsified/reversed)** |
| C2 | POC glucose Hct → ED insulin/dextrose action | pending | — | NEXT |

## Log
- Idea engine returned 7-candidate ranked backlog. Top = BEN in MC-MED (0.45), directly executing ledger #9f
  (match cohort to where the phenomenon lives — ICU reversed it, ED is right). MC-MED data was recycled →
  re-downloading visits.csv (full) + labs.csv stream-filtered to neutrophil rows. Then: confirm ANC component,
  within-patient longitudinal BEN reference, test abnormal-flag + repeat-order rate by race at matched ANC.
