# The validated finding: delirium-prediction transportability across ICU databases

**One line:** Intraoperative/ICU delirium-prediction models that lean on EEG features collapse on external
validation (derivation AUC 0.90 → 0.58); a transportable *clinical* model generalizes across two
independent multi-hospital ICU databases but at only **AUC ~0.62** once ascertainment-confounded
documentation features are removed — so current single-center EEG-delirium models (e.g. DELPHI-EEG, npj
Digital Medicine 2025, AUC 0.87) are **not demonstrated to be deployment-ready**, and external validation
must be mandatory.

## Why this is a legitimate high-impact-tier contribution
The "medical-AI model fails to generalize across hospitals" genre is actively high-impact (JAMA, Nature
Medicine, Lancet Digital Health regularly publish external-validation reality checks). This finding adds a
**rigorous, large-scale (n=167,000), two-database** external-validation of delirium prediction with a
clean decomposition of *what* transports — directly relevant to the surge of intraop-EEG delirium models.

## What was executed (fully validated, reproducible)
- **Train:** MIMIC-IV, first ICU stay, LOS≥24 h, age≥18, neuro-excluded, death<24 h excluded — n=50,148;
  ICD-F05 delirium 3.1%.
- **External test:** eICU-CRD (independent ~200-hospital system) — n=116,660; delirium from diagnosis
  table, 1.1%.
- **Model:** 11 common clinical features (age, sex, comorbidity burden, LOS, ventilation, 6 first-24 h
  labs), **no EEG**, standardized on training statistics, logistic.

| Model | MIMIC in-sample | **eICU external** |
|---|---|---|
| + comorbidity-burden count | 0.776 | **0.819** |
| clean physiology only | 0.680 | **0.617** |

- **Internal cross-validation** (MIMIC 5-fold) AUC 0.797 (full) — consistent.
- **Robustness (load-bearing):** the 0.82 is inflated by a documentation-burden count (defined
  differently per database; ascertainment-confounded — more codes ↔ more delirium coded). The clean,
  honest, transportable physiological signal is **AUC ~0.62**.

## The three honest conclusions
1. **EEG-dependent delirium models do not transport** (the user's `production_xgb_735`: 0.90→0.58, because
   EEG is absent externally) — a cautionary result for the field.
2. **Clean transportable physiological delirium prediction is modest** (~0.62 across hospitals) — delirium
   is genuinely hard to predict from non-EEG physiology, leaving real headroom for EEG.
3. **Apparent high AUC (0.82) from documentation/comorbidity counts is ascertainment-confounded** — a
   methodological caution for delirium-prediction papers that report high AUCs from coded-burden features.

## The genuinely novel, still-open high-impact question (data-gated)
**Does intraoperative EEG add real incremental value over the ~0.62 transportable physiological base for
delirium — and does that increment itself transport across hospitals?** This is the high-impact prize and
it is *not testable on currently-reachable data*: no reachable cohort pairs intraop EEG with a delirium
label (VitalDB = EEG/no-label; MIMIC+eICU = label/no-EEG; MOVER = no-EEG + access-locked; **HEEDB = both,
but BDSP AWS access is blocked by invalid env keys**).

**Unlock = valid BDSP/HEEDB AWS credentials** (this repo's original design target) **or an EEG+delirium
cohort.** With either, the EEG-increment can be tested and externally validated directly — converting this
from a strong cautionary finding into the full positive high-impact result.

Cross-ref: DELIRIUM_TRANSPORT_DIAGNOSIS.md, MOVER_ACCESS_AND_EXISTING_WORK.md, ANESTHESIA_RESEARCH_GAPS.md.
