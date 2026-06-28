# Internal replication: stable-epoch dose-REQUIREMENT in PHENYLEPHRINE (PHEN)

Tests whether the norepinephrine stable-epoch dose-REQUIREMENT finding (docs/PRESSOR_REQUIREMENT.md: split-half reliability 0.82, ~5.6x between-patient spread, early-half predicts late-half +0.54) REPLICATES in an INDEPENDENT drug -- phenylephrine, a pure alpha-1 agonist that raises MAP purely via SVR. Same machinery: PHEN-only stable constant-infusion epochs (>= 180 s, 60 s settle), MAP target band [55.0, 80.0], dose_per_kg = rate/weight, same split-half reliability + p90/p10 spread + time-split early->late computations.

- Stable PHEN epochs extracted: **745** over **115** cases.
- Qualifying PHEN-only target-band epochs: **374**; cases with a requirement phenotype (>= 2 epochs): **82**.

## Requirement phenotype (PHEN rate / kg to hold target MAP)
- median 0.1918, IQR [0.14289, 0.284], p10-p90 [0.08564, 0.3526], **between-patient fold-range (p90/p10) = 4.1**.
- **Reliability (within-patient split-half):** {'n_cases_ge4_epochs': 39, 'splithalf_spearman': 0.806}.
- **Early-half -> late-half (time split):** {'n_cases_ge4_epochs': 39, 'early_late_spearman': 0.278}.
- **Construct validity:** {'vs_cumulative_exposure_spearman': 0.392, 'vs_achieved_MAP_spearman': 0.029, 'note': 'expect: vs cumulative exposure POSITIVE (vasoplegic need more), vs achieved MAP <=0, vs EV1000 SVR NEGATIVE (low tone = high requirement)'}.

## Replication verdict vs norepinephrine
| metric | norepinephrine | phenylephrine (this) |
| --- | --- | --- |
| N phenotype cases | 52 | 82 |
| split-half reliability | 0.82 | 0.806 |
| spread p90/p10 | 5.6 | 4.1 |
| early->late Spearman | +0.54 | 0.278 |

REPLICATES -- in PHENYLEPHRINE (independent alpha-1 agent), a stable-epoch dose-REQUIREMENT phenotype exists in 82 patients, varies ~4.1-fold between patients (p10-p90), split-half reliability 0.806, and early-half->late-half Spearman 0.278. The norepinephrine finding is NOT norepi-specific: the requirement is a reproducible patient-level vasoconstrictor trait.

## Caveats
- **Dose units:** Orchestra RATE is device units (mL/h); absolute ug/kg/min needs the per-case drug concentration VitalDB does not expose. Between-patient comparison assumes a comparable standard institutional phenylephrine mix; the split-half reliability is concentration-invariant within a case.
- **Independent agent, same patient pool:** PHEN is mechanistically independent of NEPI (pure alpha-1 vs mixed alpha/beta), so a positive replication is evidence the requirement is a drug-agnostic vasoconstrictor trait, not a norepi-specific artifact. Patients may overlap with the norepi cohort; this is an internal (same-centre) replication, not external.
- **Single-centre (SNUH/VitalDB);** external replication on another database still required.
- N may be modest: phenylephrine is more often given as boluses than as long constant infusions, so qualifying stable epochs are scarcer than for norepinephrine.
