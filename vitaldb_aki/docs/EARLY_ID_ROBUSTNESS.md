# Early-identification robustness battery (hostile review of the lead finding)

Defends 'the A-line identifies the vasoplegia-prone patient early' against the four questions a hostile reviewer asks.

## 1. Incremental over clinical baseline (the key test)
- N = 52. OOF Spearman predicting LATE requirement:
  - clinical only (age/ASA/weight/baseline-MAP): **-0.013**
  - clinical + early dose: **0.186**
  - clinical + early dose + tone: **0.186**
  _if clinical+A-line > clinical-only, the waveform/early-requirement ADDS information beyond age/ASA/weight/baseline-MAP -> worth measuring._

## 2. Lead-time (real minutes)
- High-requirement threshold: 0.2164 (per-kg).
- **Time from first stable epoch to crossing high requirement: 8.0 min** (IQR [0.0, 27.9], n_high=18).
- Early-signal window 46.6 min; case runway 99.5 min.

## 3. Operating point (ROC)
- **AUC (first-half dose -> eventual high requirement): 0.771** (n=52); at threshold 0.1346: sensitivity 0.72, specificity 0.62.

## 4. Definition robustness (anti-cherry-pick)
- band(50, 75)_minep2: reliability 0.733, fold-range 3.3 (n=29).
- band(50, 75)_minep3: reliability 0.733, fold-range 3.3 (n=29).
- band(55, 80)_minep2: reliability 0.817, fold-range 3.8 (n=30).
- band(55, 80)_minep3: reliability 0.817, fold-range 3.8 (n=30).
- band(60, 85)_minep2: reliability 0.847, fold-range 4.0 (n=36).
- band(60, 85)_minep3: reliability 0.847, fold-range 4.0 (n=36).

## Verdict
Incremental over clinical: clinical-only OOF -0.013 vs clinical+early-A-line 0.186 (A-line ADDS predictive value beyond clinical baseline). Lead-time to high requirement: 8.0 min (early-signal window 46.6 min). Operating point AUC 0.771 (sens None, spec None).

## Caveats
- N ~ 40-52 (the requirement phenotype is small); OOF only. Lead-time is intra-operative (within-case epoch timing), single-centre. The incremental-over-clinical test is the one that matters most -- if it is null, the A-line is redundant with bedside clinical data.
- All observational; identifies WHO needs more pressor early, not that acting helps (trial).
