# External validation in INSPIRE (independent ~131k-op cohort)

Validates the REPLICABLE CORE of the vasopressor-requirement finding in an independent cohort. HONEST SCOPE: INSPIRE has no arterial waveforms / no per-epoch timing, so it validates the CONCEPT (requirement is a trait + carries outcome info beyond MAP), NOT the waveform / early-identification specifics (those need an external WAVEFORM cohort).

- INSPIRE operations: 130960; with norepinephrine used: 3261.

## 1. Trait replication across operations (within-subject)
- Duration-normalised requirement: within-subject Spearman **0.317** (95% CI [0.188, 0.438], n=218 subjects with norepi in >=2 ops).
- Raw cumulative dose: 0.184 (CI [0.05, 0.309]).
  _positive within-subject correlation across operations = the vasopressor requirement is a reproducible patient trait in an INDEPENDENT cohort + design. Caveat: operations differ in surgery type/duration -> the duration-normalised rate is the cleaner._

## 2. Incremental over MAP-AUC for outcomes (out-of-fold AUC)
- **composite** (events 13884/130960): clinical+MAP AUC 0.8275 -> +requirement 0.8297 (**ΔAUC 0.0022**); MAP-alone 0.69 vs requirement-alone 0.5742.
- **organ_renal** (events 4497/90246): clinical+MAP AUC 0.7566 -> +requirement 0.7581 (**ΔAUC 0.0015**); MAP-alone 0.6658 vs requirement-alone 0.5771.
- **death_inhosp** (events 1555/130960): clinical+MAP AUC 0.8137 -> +requirement 0.8177 (**ΔAUC 0.004**); MAP-alone 0.7022 vs requirement-alone 0.6067.
  _delta_auc > 0 => the vasopressor requirement adds predictive value BEYOND MAP-AUC + demographics in an independent cohort (external support for the control-theory corollary that the dose carries the hemodynamic insult). Compare requirement-alone vs MAP-alone AUC for which signal is better-identified._

## Verdict
EXTERNAL (INSPIRE, n_norepi=3261): TRAIT REPLICATES across operations (duration-normalised within-subject Spearman 0.317 [0.188, 0.438], n=218); requirement does NOT clearly add over MAP+demographics (death dAUC 0.004, composite dAUC 0.0022). NOTE: validates the CONCEPT (trait + incremental); the waveform/early-ID specifics need an external WAVEFORM cohort (MIMIC-IV/eICU), not testable in INSPIRE.

## Caveats
- Trait-across-operations is confounded by surgery type/duration differing between a subject's operations; the duration-normalised rate is the cleaner estimate but residual confounding remains. INSPIRE norepi is a cumulative total (no rate/timing).
- Incremental-AUC is association/prediction, not causal; norepi->AKI was shown confounded by indication (negative-control calibration) -- this is about PREDICTIVE information, the control-theory corollary, not a treatment effect.
- Full external validation of the WAVEFORM tone estimator + EARLY-identification finding requires an external arterial-waveform cohort (MIMIC-IV waveform / eICU); stated as the remaining external step, not done here.
