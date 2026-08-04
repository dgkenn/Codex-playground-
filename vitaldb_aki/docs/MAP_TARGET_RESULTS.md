# Does a Higher Intraoperative MAP Target (70/75 vs 65) Reduce End-Organ Injury?

Rigorously-confounder-controlled observational interrogation on VitalDB. Primary outcome: **organ_renal** (AKI). Secondary: **composite**.

- Cases merged: **4335**  (feature_matrix=4335, map_thresholds=4335)
- Confounders present: age, sex_male, asa, preop_htn, preop_dm, preop_cr, intraop_ebl, anesthesia_duration_min, optype_code, cum_vasopressor_dose
- All confounders present.

## Interpretation & limitations (READ FIRST)

This is **observational**. The central threat is **confounding by indication / by health**: patients who naturally hold MAP>=75 are healthier (less vasoplegia, better cardiac function, smaller/shorter operations), so achieved-MAP>=75 is mostly a **marker of being well, not a cause of good kidneys**. Every analysis here is built to neutralise that (modifiable exposures + heavy adjustment + a negative-control outcome + E-values). The deliverable is a **rigorously-controlled, externally-validatable HYPOTHESIS** for a randomized 65-vs-75 MAP-target trial (benchmark: INPRESS, RR ~0.73 for organ dysfunction) -- **not proof of causation**. Cells with <15 events are underpowered and flagged.

## (A) Incremental-band test -- HEADLINE

Does hypotension in the **65-75 band** add AKI risk **beyond** burden <65? If yes, that is risk the current 65 guideline misses.

- **organ_renal** (n=3924, events=143)
  - Band adjusted OR (per SD of band_65_75_auc): **0.9809** [0.7499, 1.2171]
  - LRT (band added to <65 base): chi2=0.0233, **p=0.878644**
  - DeLong ΔAUROC (full vs base): 0.00015  (p=0.60061)

- **composite** (n=4335, events=660)
  - Band adjusted OR (per SD of band_65_75_auc): **1.0504** [0.9046, 1.2123]
  - LRT (band added to <65 base): chi2=0.4502, **p=0.502261**
  - DeLong ΔAUROC (full vs base): -7e-05  (p=0.84605)

## (B) Adjusted threshold-response curve

Fully-adjusted OR per SD of below-T burden, T=50..80. Does adjusted risk keep rising above 65 toward 75, or flatten at 65 (= no benefit to a higher target)?

### organ_renal (events=143)

| T | adjusted OR/SD | 95% CI |
|---|----------------|--------|
| 50 | 1.1361 | [0.9768, 1.2938] |
| 55 | 1.0709 | [0.968, 1.2831] |
| 60 | 1.0917 | [0.9624, 1.325] |
| 65 | 1.1209 | [0.9881, 1.3206] |
| 70 | 1.0962 | [0.9345, 1.3199] |
| 75 | 1.0901 | [0.8826, 1.2861] |
| 80 | 1.1375 | [0.9104, 1.3806] |

Flat at 65 (no further rise to 75): **True** -- no adjusted signal for a higher target.

### composite (events=660)

| T | adjusted OR/SD | 95% CI |
|---|----------------|--------|
| 50 | 0.9949 | [0.872, 1.1108] |
| 55 | 0.9763 | [0.8973, 1.0865] |
| 60 | 0.9964 | [0.8976, 1.1134] |
| 65 | 1.0066 | [0.9176, 1.1151] |
| 70 | 1.0176 | [0.9291, 1.147] |
| 75 | 1.0241 | [0.9169, 1.1405] |
| 80 | 1.0283 | [0.9073, 1.1483] |

Flat at 65 (no further rise to 75): **True** -- no adjusted signal for a higher target.

## (C) Modifiable-exposure IPTW target-trial

Residualize below-target burden on surgical-insult+baseline covariates; the **top-tertile residual** = 'under-treated at the target' = the modifiable excess (health-marker component removed). IPTW over the full confounder set -> the causal estimate of the *modifiable* part.

- **organ_renal @ 75-target** (n=3849, events=142, exposed=1283)
  - IPTW risk difference: **0.0074** CI [-0.0062, 0.0214]
  - IPTW risk ratio: **1.2123** CI [0.8471, 1.7073]
  - Balance max-SMD pre/post weighting: 0.5332 -> 0.1273

- **organ_renal @ 65-target** (n=3849, events=142, exposed=1283)
  - IPTW risk difference: **0.0154** CI [-0.001, 0.0321]
  - IPTW risk ratio: **1.4508** CI [0.9745, 2.1305]
  - Balance max-SMD pre/post weighting: 0.5764 -> 0.1028

- **composite @ 75-target** (n=4231, events=649, exposed=1411)
  - IPTW risk difference: **0.0219** CI [-0.0025, 0.0467]
  - IPTW risk ratio: **1.1513** CI [0.9834, 1.3519]
  - Balance max-SMD pre/post weighting: 0.2064 -> 0.0797

- **composite @ 65-target** (n=4231, events=649, exposed=1411)
  - IPTW risk difference: **0.0027** CI [-0.0238, 0.0273]
  - IPTW risk ratio: **1.0173** CI [0.8575, 1.1841]
  - Balance max-SMD pre/post weighting: 0.2242 -> 0.0762

## (D) Bias-control battery

### E-values (VanderWeele)
- band_A: point E-value **1.1604**, CI-bound E-value 1.0 -- E-value for the 65-75 band adjusted OR (treated on RR scale).
- modifiable_C: point E-value **1.7196**, CI-bound E-value 1.0 -- E-value for the IPTW risk ratio of the modifiable 75-target exposure.

### Negative-control outcome (organ_cholestatic)
- Band OR on negative control: 0.9596 (LRT p=0.732851)
- IPTW RR on negative control: 1.205 CI [0.8591, 1.6984]
- organ_cholestatic should NOT be caused by the MAP target. A clearly non-null band OR or IPTW RR here flags RESIDUAL CONFOUNDING and should temper any positive primary result.

### Effect-modification by the vulnerable phenotype
- Band x phenotype interaction OR: **0.9918** (LRT p=1.0)
- Vulnerable n=657, events=43
- Interaction OR>1 with p<0.05 => the 65-75 band's AKI risk concentrates in the vulnerable phenotype (where a higher target would help most). p NS => no detectable effect-modification (likely underpowered with 143 renal events).

### Naive-vs-adjusted contrast (the instructive gap)

The naive achieved-MAP>=75 association is **confounded** (health marker). Its distance from the adjusted/modifiable estimates above is the bias this study removes.

- **organ_renal** (CONFOUNDED): AKI rate achieved>=75 = 0.0312 (n=3304) vs <75 = 0.0645 (n=620); naive RR = **0.4832**

- **composite** (CONFOUNDED): AKI rate achieved>=75 = 0.1411 (n=3607) vs <75 = 0.2074 (n=728); naive RR = **0.6803**

Dose-response is assessed in the adjusted threshold-response curve (B): a monotone rise in adjusted OR with deepening below-T burden supports causality; a flat/non-monotone curve weakens it.

---
*Generated by vitaldb_aki/analysis/map_target_analysis.py*
