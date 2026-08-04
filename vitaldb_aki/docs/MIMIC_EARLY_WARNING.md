# Early-warning value of the in-ICU norepinephrine requirement (MIMIC-IV)

Tests whether an EARLY snapshot of the norepinephrine requirement (first 6 h from the first segment) is an ACTIONABLE in-hospital-mortality early-warning, and whether the within-stay TRAJECTORY (rising dose, escalation events) adds warning beyond that early level. Real infusion timestamps + a hard endpoint -- the version VitalDB (intraoperative, no mortality) could not power. Norepinephrine (mcg/kg/min) from icu/inputevents; in-hospital death from admissions.hospital_expire_flag.

- Stays with norepinephrine: **15949**; with a mortality record: **15949**; deaths: **5258** (33%).

## 1. Does an EARLY snapshot (first 6 h) already stratify death?
- **Early-peak norepi:** {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 1.726, 'ci': [1.592, 1.89], 'auc_x_alone': 0.668, 'auc_age_alone': 0.559, 'auc_age_plus_x': 0.673, 'delta_auc_over_age': 0.1148}.
- **Early-median norepi:** {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 2.032, 'ci': [1.898, 2.153], 'auc_x_alone': 0.673, 'auc_age_alone': 0.559, 'auc_age_plus_x': 0.682, 'delta_auc_over_age': 0.1232}.
- **Whole-stay peak (reference):** {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 1.862, 'ci': [1.717, 2.058], 'auc_x_alone': 0.742, 'auc_age_alone': 0.559, 'auc_age_plus_x': 0.729, 'delta_auc_over_age': 0.1703}.
- **Whole-stay median (reference):** {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 3.798, 'ci': [3.441, 4.174], 'auc_x_alone': 0.756, 'auc_age_alone': 0.559, 'auc_age_plus_x': 0.764, 'delta_auc_over_age': 0.2051}.
- **Honest rank AUC, early-peak 0.668 vs whole-stay-peak 0.742** -> a 6 h snapshot retains **0.694** of the whole-stay rank signal (1.0 = no warning lost by looking early).

## 2. Does a RISING requirement add warning BEYOND the early level? (nested logistic)
- Trajectory-eligible stays (>=4 segments over >=6 h): **12096** (4156 deaths); rising (slope>0): **0.276**, median slope -0.00085 mcg/kg/min/h.
- Base (age+early-level) AUC 0.632 -> +slope AUC 0.771 (**+0.1385**); slope age-adj OR 5.291/SD; LR-test chi2 1743.413, **p 0.0**.

## 3. Escalation events -> mortality + lead time
- Definition: rate>= 2.0x prev OR >= prev+0.1 mcg/kg/min, after 1h. Fraction of stays with >=1 escalation: **0.49**.
- **Any escalation (age-adjusted):** {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 1.458, 'ci': [1.411, 1.506], 'auc_x_alone': 0.591, 'auc_age_alone': 0.559, 'auc_age_plus_x': 0.622, 'delta_auc_over_age': 0.063}.
- **Number of escalations (age-adjusted):** {'n': 15949, 'deaths': 5258, 'mortality_rate': 0.33, 'adj_or_per_sd': 1.388, 'ci': [1.332, 1.456], 'auc_x_alone': 0.61, 'auc_age_alone': 0.559, 'auc_age_plus_x': 0.623, 'delta_auc_over_age': 0.064}.
- Crude mortality with vs without escalation: 0.412 vs 0.251.
- **Lead time** (deaths with >=1 escalation, n=3214): median **42.73 h** from first norepi to the last escalation (IQR [10.75, 135.03]); median norepi recorded for 9.26 h after that escalation.

## 4. Simple bedside rule (early-peak norepi threshold)
_IN-SAMPLE operating points (pre-specified round-number thresholds, evaluated on the same data -- NOT cross-validated)._

| early-peak >= | n above | mortality above | mortality below | sens | spec | PPV | NPV |
|---|---|---|---|---|---|---|---|
| 0.2 mcg/kg/min | 6324 | 0.473 | 0.236 | 0.568 | 0.688 | 0.473 | 0.764 |
| 0.3 mcg/kg/min | 4020 | 0.543 | 0.258 | 0.415 | 0.828 | 0.543 | 0.742 |

## Verdict
EARLY in-ICU norepinephrine requirement (MIMIC-IV, 15949 stays, 5258 deaths, 33% mortality): ACTIONABLE EARLY-WARNING -- first-6h norepi already stratifies death (early-peak age-adj OR 1.726 [1.592, 1.89], AUC 0.668 vs whole-stay 0.742 -> 0.694 of the rank signal retained from a 6h snapshot); a RISING requirement adds warning beyond the early level (slope LR-test p 0.0, +0.1385 AUC, slope OR 5.291/SD); escalation events mark risk (any-escalation age-adj OR 1.458 [1.411, 1.506]; median lead 42.73 h from first norepi to the last escalation among deaths). Bedside rule: early-peak >= 0.2 mcg/kg/min -> 0.473 mortality vs 0.236 below (sens 0.568, spec 0.688, PPV 0.473, NPV 0.764; IN-SAMPLE). Observational, age-adjusted ONLY -- the early requirement MARKS the sicker patient (severity confounding unaddressed here, handled elsewhere); this identifies WHO is high-risk early, not that acting on the dose changes outcome (a trial).

## Caveats
- **AUC is honest (rank-based, no tuning); the bedside-rule operating points in Test 4 are IN-SAMPLE** -- pre-specified round-number thresholds (0.2/0.3 mcg/kg/min) but evaluated on the same data, so sens/spec/PPV/NPV are optimistic vs a held-out test.
- **Observational and age-adjusted ONLY.** The early requirement marks the sicker patient by construction; illness-severity confounding is NOT removed here (handled elsewhere). This identifies WHO is high-risk early, not that titrating the dose helps.
- **Early window = first 6 h from the FIRST norepi segment**, not from ICU admission; a late-starting infusion's 'early' window is late in the stay. The whole-stay comparison is the same cohort, so the early-vs-whole AUC contrast is fair.
- **No death timestamp here**, so 'lead time' is first-norepi -> last-escalation and 'runway' is last-escalation -> end-of-norepi-record, both proxies for time-to-act, not time-to-death.
- In-hospital death (hospital_expire_flag) is per-admission; the requirement is per-stay. Multi-stay admissions share an outcome (minority of stays).
- Does NOT validate the arterial-waveform tone estimator (needs MIMIC-IV-Waveform).
