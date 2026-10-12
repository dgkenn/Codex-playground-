# Does A-line WAVEFORM morphology predict the vasopressor DOSE-REQUIREMENT (vasoplegia) phenotype?

Merge-and-model test (no new waveform extraction). TARGET = the per-case norepinephrine dose-REQUIREMENT phenotype from pressor_requirement.py (median dose/kg over stable norepi-only epochs holding MAP in [55.0, 80.0] mmHg, >= 2 epochs; high requirement = vasoplegia). FEATURES = pre-existing A-line morphology (Pivot-2 tone family: diastolic/MAP form factor, tau decay, augmentation index, ...). PRE-SPECIFIED PRIMARY feature = `diastolic_over_map` (the Pivot-2 carrier). OOF (KFold) estimates ONLY; no in-sample R2.

- Phenotype cases (requirement target): **41**.
- Cases with A-line morphology: **535** (merged from vasoplegia_validation.csv, independent_svr_validation.csv, aline_sample.csv).
- **MERGED N (phenotype AND morphology) = 11**.

- Requirement (dose/kg) median 0.160267, IQR [0.11794, 0.262694]; high-requirement top-tertile threshold 0.230504 (n_high 4 / n_low 7); median epochs/case 6.

## 1-2. Out-of-fold morphology -> requirement
- Full morphology set (11 features), 5-fold x5 RidgeCV: **OOF Spearman 0.3473**, **OOF R2 -0.1987** (N=11).
- High-requirement (top tertile) logistic **OOF AUC 0.4429** (n_pos 4/11).

## 3. Pre-specified PRIMARY feature (diastolic_over_map, the Pivot-2 carrier)
- Univariate **Spearman vs requirement = 0.1455** (95% bootstrap CI [-0.5676, 0.6873], n=11).
- Hypothesised sign: NEGATIVE (low diastolic/MAP = low tone = vasoplegia = HIGH norepi requirement) -> observed is **NOT in the hypothesised direction**.
- Secondary carriers: {'art_tau_decay_mean': {'spearman': 0.0818, 'ci': [-0.662, 0.8224], 'n': 11}, 'art_aug_index_mean': {'spearman': -0.5364, 'ci': [-0.9025, 0.1206], 'n': 11}}.

## 4. Incremental value over body size (weight/age/BMI/ASA)
- Size-only OOF R2 -0.7253; +morphology OOF R2 -0.6943; **morphology incremental OOF R2 = 0.031**.

## 5. Negative control / placebo (surgery duration)
- OOF morphology -> surgery duration Spearman 0.3545 (R2 -0.3776); primary feature vs duration Spearman -0.2636 (CI [-0.6902, 0.365]).
- calibration negative control: A-line morphology should NOT predict an unrelated label (surgery duration) as strongly as the requirement phenotype.

## Verdict
FEASIBILITY-ONLY (merged N = 11 < 25). The requirement phenotype (needs >= 2 stable norepi-only target-band epochs) and the A-line morphology caches overlap on too few cases for a trustworthy out-of-fold estimate. Directional read (NOT a result): OOF morphology->requirement Spearman 0.3473, high-requirement OOF AUC 0.4429, primary feature diastolic_over_map univariate Spearman 0.1455 (CI [-0.5676, 0.6873], WRONG/null sign), morphology incremental-over-body-size OOF R2 0.031. Any Spearman/AUC on this N is dominated by sampling noise and a wide CI; GROW the phenotype cohort (more cases with >= 2 stable epochs that ALSO have an A-line morphology extraction) before claiming predictive value. The placebo correlation is reported for calibration, not inference.

## Caveats
- **N is the binding limit.** The requirement phenotype needs >= 2 stable norepi-only target-band epochs, which is rare; the A-line morphology caches were extracted for the SVR/vasoplegia sub-studies, not this phenotype. Their intersection (N=11) is the hard ceiling here. Below N=25 this is a FEASIBILITY signal, not a result -- OOF estimates at this N have very wide CIs and can flip on one case.
- **OOF only.** Every Spearman/R2/AUC headline above is out-of-fold (KFold), never in-sample, to avoid overfitting inflation at small N.
- **Observational, single-centre (SNUH/VitalDB).** The requirement reflects management + physiology; morphology features are intraoperative summaries, not strictly PRE-induction baselines -- so 'pre-emptive' is aspirational until a true pre-pressor window is used. External replication required.
- Links to: pressor_requirement.py (target), independent_svr_validation.py / PIVOT2_PREPUB_TESTS.md (the morphology->tone evidence the carrier rests on).
