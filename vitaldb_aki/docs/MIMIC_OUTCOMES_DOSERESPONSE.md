# MIMIC-IV vasopressor requirement: long-term mortality, dose-response, formulation, LOS

Impact-raising outcome tests on the norepinephrine-requirement finding, all age-adjusted (severity adjustment is in MIMIC_MORTALITY_SEVERITY.md). Per-stay requirement = median norepi rate (0<rate<=5 mcg/kg/min). Reuses cache/mimic_norepi.csv.

- ICU stays with norepinephrine: **15949**.

## 1. Longer-term mortality (from ICU admission, via patients.dod)
- Stays with valid intime+age: 15949; with a recorded dod: 9723.
- MIMIC dates are de-identified/shifted but internally consistent per subject, so (dod - intime) day-differences are valid. Deaths beyond the file horizon are censored (treated as alive) -- so absolute long-horizon rates are lower bounds.
  - **28d:** {'n': 15949, 'events': 5140, 'event_rate': 0.322, 'adj_or_per_sd': 2.014, 'ci': [1.873, 2.158], 'auc_age_alone': 0.574, 'auc_age_plus_dose': 0.708, 'delta_auc': 0.1341}
  - **90d:** {'n': 15949, 'events': 6351, 'event_rate': 0.398, 'adj_or_per_sd': 1.776, 'ci': [1.669, 1.897], 'auc_age_alone': 0.58, 'auc_age_plus_dose': 0.679, 'delta_auc': 0.099}
  - **1y:** {'n': 15949, 'events': 7685, 'event_rate': 0.482, 'adj_or_per_sd': 1.522, 'ci': [1.44, 1.62], 'auc_age_alone': 0.59, 'auc_age_plus_dose': 0.651, 'delta_auc': 0.0606}

**Verdict:** PREDICTS LONG-TERM DEATH -- 28d: OR 2.014/SD [1.873, 2.158] (AUC +0.1341 over age, 0.322 died); 90d: OR 1.776/SD [1.669, 1.897] (AUC +0.099 over age, 0.398 died); 1y: OR 1.522/SD [1.44, 1.62] (AUC +0.0606 over age, 0.482 died). The requirement marks risk well beyond hospital discharge (de-identified-but-internally-consistent dod; follow-up beyond file horizon is censored).

## 2. Dose-response gradient (in-hospital mortality)
- Quartiles: n/bin [3988, 3987, 3987, 3987], mortality/bin [0.1399, 0.2032, 0.3248, 0.6509], monotonic non-decreasing: True.
- **Q1 mortality 0.1399 -> Q4 0.6509 (risk ratio 4.65x; absolute +0.511).**
- Cochran-Armitage trend z=49.693, p=0.0; logistic linear-trend OR 3.746/SD, p=0.0.
- Deciles mortality/bin: [0.1197, 0.148, 0.1693, 0.1893, 0.2313, 0.269, 0.3386, 0.4251, 0.5655, 0.8413] (monotonic: True).

**Verdict:** DOSE-RESPONSE: Q1 mortality 0.1399 -> Q4 0.6509 (risk ratio 4.65x, abs +0.511); quartiles monotonic non-decreasing: True; Cochran-Armitage p=0.0; logistic linear-trend p=0.0. A clean monotone dose-response gradient -- more compelling than a single per-SD OR.

## 3. Which dose summary is most prognostic? (age-adjusted AUC for in-hospital death)
- n=15949, deaths=5258.
- Ranking by ΔAUC over age (formulation, ΔAUC, OR/SD):
  - time-weighted-mean rate: ΔAUC +0.2149, OR 3.994/SD
  - median rate: ΔAUC +0.2051, OR 3.798/SD
  - peak/max rate: ΔAUC +0.1703, OR 1.862/SD
  - total exposure (rate*min): ΔAUC +0.1258, OR 1.953/SD
  - duration on norepi (h): ΔAUC +0.0508, OR 1.378/SD

**Verdict:** BEST DOSE SUMMARY for in-hospital death: 'time-weighted-mean rate' (ΔAUC over age +0.2149, OR 3.994/SD). Full ranking by ΔAUC: time-weighted-mean rate (+0.2149), median rate (+0.2051), peak/max rate (+0.1703), total exposure (rate*min) (+0.1258), duration on norepi (h) (+0.0508).

## 4. Length of stay (age-adjusted; death truncates LOS)
- ICU LOS, all: {'n': 15940, 'tag': 'all', 'median_los_days': 4.12, 'age_adj_beta_log1p_per_sd': -0.1639, 'approx_pct_change_per_sd': np.float64(-15.1), 'spearman_req_vs_los': -0.055}
- ICU LOS, survivors only: {'n': 10688, 'tag': 'survivors', 'median_los_days': 4.21, 'age_adj_beta_log1p_per_sd': 0.0737, 'approx_pct_change_per_sd': np.float64(7.6), 'spearman_req_vs_los': 0.191}
- Hospital LOS, all: {'n': 15906, 'tag': 'all', 'median_los_days': 11.24, 'age_adj_beta_log1p_per_sd': -0.274, 'approx_pct_change_per_sd': np.float64(-24.0), 'spearman_req_vs_los': -0.151}
- Hospital LOS, survivors only: {'n': 10691, 'tag': 'survivors', 'median_los_days': 12.87, 'age_adj_beta_log1p_per_sd': 0.0392, 'approx_pct_change_per_sd': np.float64(4.0), 'spearman_req_vs_los': 0.129}

**Verdict:** LOS: ICU LOS +-15.1%/SD (rho -0.055) all, +7.6%/SD (rho 0.191) survivors; hospital LOS +-24.0%/SD (rho -0.151) all, +4.0%/SD (rho 0.129) survivors (age-adjusted, per +1 SD requirement). Death truncates LOS, so the survivor-only estimate is the honest read of 'longer stay'.

## Overall verdict
IMPACT TESTS (MIMIC-IV ICU, 15949 norepi stays; age-adjusted only -- severity adjustment handled in mimic_mortality_severity.py). PREDICTS LONG-TERM DEATH -- 28d: OR 2.014/SD [1.873, 2.158] (AUC +0.1341 over age, 0.322 died); 90d: OR 1.776/SD [1.669, 1.897] (AUC +0.099 over age, 0.398 died); 1y: OR 1.522/SD [1.44, 1.62] (AUC +0.0606 over age, 0.482 died). The requirement marks risk well beyond hospital discharge (de-identified-but-internally-consistent dod; follow-up beyond file horizon is censored). DOSE-RESPONSE: Q1 mortality 0.1399 -> Q4 0.6509 (risk ratio 4.65x, abs +0.511); quartiles monotonic non-decreasing: True; Cochran-Armitage p=0.0; logistic linear-trend p=0.0. A clean monotone dose-response gradient -- more compelling than a single per-SD OR. BEST DOSE SUMMARY for in-hospital death: 'time-weighted-mean rate' (ΔAUC over age +0.2149, OR 3.994/SD). Full ranking by ΔAUC: time-weighted-mean rate (+0.2149), median rate (+0.2051), peak/max rate (+0.1703), total exposure (rate*min) (+0.1258), duration on norepi (h) (+0.0508). LOS: ICU LOS +-15.1%/SD (rho -0.055) all, +7.6%/SD (rho 0.191) survivors; hospital LOS +-24.0%/SD (rho -0.151) all, +4.0%/SD (rho 0.129) survivors (age-adjusted, per +1 SD requirement). Death truncates LOS, so the survivor-only estimate is the honest read of 'longer stay'. HONEST: observational; the requirement marks risk/illness burden, not a treatment effect.

## Caveats
- Observational; **only age-adjusted here** -- the requirement marks risk/illness burden, not a treatment effect. Severity-adjusted analysis is in MIMIC_MORTALITY_SEVERITY.md (the requirement OR attenuates but the question of 'beyond severity' is answered there, not here).
- Long-term mortality uses patients.dod; MIMIC records death out to a limited post-discharge window, so deaths past the file horizon are unobserved (censored as alive) -> long-horizon absolute rates are LOWER bounds, but the dose->death ORDERING is robust to this (non-differential by dose).
- Dose formulations (peak, time-weighted-mean, total exposure, duration) use segment start/endtimes; segments with non-positive or >24h durations are dropped from the duration-weighted summaries (median/peak always available).
- LOS is right-skewed -> modelled on log1p(days); reported as approx %/SD. Death shortens LOS, hence the explicit survivor-only estimate.
