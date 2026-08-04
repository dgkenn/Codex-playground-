# Resuscitation balance + norepinephrine-equivalent load: bidirectional cross-validation

Two resuscitation-strategy findings, each tested in MIMIC-IV ICU (in-hospital death) and cross-validated in the OPPOSITE population (VitalDB / INSPIRE intra-operative). Single stream-filter of icu/inputevents (fluid + vasopressor itemids), raw deleted after.

- MIMIC stays with any filtered fluid/pressor event: **76533** (with a pressor: 28327; with crystalloid/colloid: 76301).
- NEE weights: {'norepi': 1.0, 'epi': 1.0, 'phenylephrine': 0.1, 'dopamine': 0.01, 'vasopressin_per_unit_min': 2.5, 'dobutamine': 'EXCLUDED (inotrope)', 'angiotensinII_229764': 'EXCLUDED (no standard NEE weight)'}.

## A. Fluid-vs-pressor BALANCE -> in-hospital mortality (MIMIC)
Balance = log((NEE-load + eps) / (fluid mL/kg + eps)); higher = more pressor-predominant.
- n=76374, deaths=9475, dropped (no weight)=159; median fluid 36.1 mL/kg, median NEE-load 0.0.
- Age-adjusted (full): {'n': 76374, 'events': 9475, 'event_rate': 0.124, 'adj_or_per_sd': 2.144, 'ci': [2.095, 2.201], 'auc_adjust_only': 0.606, 'auc_with_exposure': 0.735, 'delta_auc': 0.1288, 'adjusted_for': ['age']}
- Tertiles full (fluid->pressor predominant): {'n_per_tertile': [25458, 25458, 25458], 'mortality_per_tertile': [0.0702, 0.0663, 0.2357], 'monotonic_nondecreasing': False, 'cochran_armitage_z': 56.625, 'cochran_armitage_p': 0.0}
  (lowest tertile is 1.0 NO-pressor stays -> raw balance partly encodes 'got a pressor at all'; see co-exposed below for the clean read).
- CO-EXPOSED (pressor+fluid both, n=28124) age-adjusted: {'n': 28124, 'events': 6068, 'event_rate': 0.216, 'adj_or_per_sd': 3.505, 'ci': [3.345, 3.689], 'auc_adjust_only': 0.55, 'auc_with_exposure': 0.778, 'delta_auc': 0.2281, 'adjusted_for': ['age']}
- CO-EXPOSED tertiles: {'n_per_tertile': [9375, 9375, 9374], 'mortality_per_tertile': [0.0649, 0.1531, 0.4294], 'monotonic_nondecreasing': True, 'cochran_armitage_z': 60.67, 'cochran_armitage_p': 0.0}
- Lactate-adjusted full (n with lactate=17742): {'n': 17742, 'events': 2712, 'event_rate': 0.153, 'adj_or_per_sd': 1.939, 'ci': [1.837, 2.058], 'auc_adjust_only': 0.7, 'auc_with_exposure': 0.755, 'delta_auc': 0.0549, 'adjusted_for': ['age', 'log_lactate']}
- Lactate-adjusted CO-EXPOSED: {'n': 8623, 'events': 1976, 'event_rate': 0.229, 'adj_or_per_sd': 3.398, 'ci': [3.142, 3.698], 'auc_adjust_only': 0.677, 'auc_with_exposure': 0.811, 'delta_auc': 0.1337, 'adjusted_for': ['age', 'log_lactate']}

**Verdict A (MIMIC):** FLUID-vs-PRESSOR BALANCE -> in-hospital mortality (MIMIC, n=76374, 9475 deaths): age-adj OR 2.144/SD [2.095, 2.201] (higher = more pressor-predominant; AUC +0.1288 over age). Tertile mortality [0.0702, 0.0663, 0.2357] (fluid->pressor predominant; monotone False, CA p=0.0) -- NB the lowest tertile is 1.0 no-pressor stays, so raw balance partly encodes 'got a pressor at all'. CO-EXPOSED (both pressor+fluid, n=28124): age-adj OR 3.505/SD [3.345, 3.689], tertile mortality [0.0649, 0.1531, 0.4294] (monotone True) -- the clean within-resuscitated gradient: pressor-predominant is worse. Lactate-adjusted full (n=17742): OR 1.939/SD [1.837, 2.058]; co-exposed+lactate OR 3.398/SD [3.142, 3.698] -- survives severity (lactate) adjustment.

### A. Intra-op validation (VitalDB -> post-op AKI organ_renal)
Intraop fluid = crystalloid + colloid (mL); pressor index = phe + eph + epi (mg, drug-specific units -> an INDEX, not true NEE). balance = log((pressor+eps)/(mL/kg+eps)).
- {'n': 3924, 'aki_events': 143, 'balance_vs_aki_age_adj': {'n': 3924, 'events': 143, 'event_rate': 0.036, 'adj_or_per_sd': 1.183, 'ci': [0.996, 1.394], 'auc_adjust_only': 0.524, 'auc_with_exposure': 0.559, 'delta_auc': 0.0353, 'adjusted_for': ['age']}, 'tertiles': {'n_per_tertile': [1308, 1308, 1308], 'mortality_per_tertile': [0.0291, 0.0306, 0.0497], 'monotonic_nondecreasing': True, 'cochran_armitage_z': 2.817, 'cochran_armitage_p': 0.004845916876254621}}

**Verdict A (VitalDB intraop):** VitalDB INTRAOP validation (n=3924, AKI=143): intraop balance -> organ_renal age-adj OR 1.183/SD [0.996, 1.394] -- concordant (pressor-predominant -> more AKI). Tertile AKI [0.0291, 0.0306, 0.0497].

### A. INSPIRE
- INSPIRE matrix has NO intra-op fluid volume columns (only 'ebl'); fluid-vs-pressor balance cannot be replicated in INSPIRE. Stated explicitly.

## B. All-pressor norepinephrine-equivalent (NEE) load -> mortality (MIMIC)
NEE: norepi/epi 1.0, phenylephrine 0.1, dopamine 0.01, vasopressin 2.5/unit-min (stated); dobutamine + angiotensin-II excluded. Restricted to pressor-exposed stays.
- n pressor stays=28327, deaths=6120.
- NEE-load quartiles: {'n_per_bin': [7082, 7082, 7082, 7081], 'mortality_per_bin': [0.0602, 0.1058, 0.2248, 0.4735], 'monotonic_nondecreasing': True, 'q1_mortality': 0.0602, 'q4_mortality': 0.4735, 'q4_over_q1_riskratio': 7.87, 'q4_minus_q1_abs': 0.4133, 'cochran_armitage_z': 62.142, 'cochran_armitage_p': 0.0}
- NEE-peak quartiles: {'n_per_bin': [7082, 7082, 7082, 7081], 'mortality_per_bin': [0.06, 0.0857, 0.1862, 0.5323], 'monotonic_nondecreasing': True, 'q1_mortality': 0.06, 'q4_mortality': 0.5323, 'q4_over_q1_riskratio': 8.87, 'q4_minus_q1_abs': 0.4723, 'cochran_armitage_z': 69.373, 'cochran_armitage_p': 0.0}
- NEE-load age-adjusted (log): {'n': 28327, 'events': 6120, 'event_rate': 0.216, 'adj_or_per_sd': 3.181, 'ci': [3.042, 3.308], 'auc_adjust_only': 0.551, 'auc_with_exposure': 0.777, 'delta_auc': 0.2262, 'adjusted_for': ['age']}
- NEE-peak age-adjusted: {'n': 28327, 'events': 6120, 'event_rate': 0.216, 'adj_or_per_sd': 2.607, 'ci': [2.361, 2.871], 'auc_adjust_only': 0.551, 'auc_with_exposure': 0.798, 'delta_auc': 0.2471, 'adjusted_for': ['age']}

**Verdict B (MIMIC):** ALL-PRESSOR NEE total load -> in-hospital mortality (MIMIC, 28327 pressor stays, 6120 deaths): Q1 0.0602 -> Q4 0.4735 (RR 7.87x, abs +0.4133); quartiles monotone True, CA p=0.0; age-adj OR 3.181/SD [3.042, 3.308] (log NEE-load, AUC +0.2262 over age). Widening norepi-only to ALL pressors reproduces the dose-response.

### B. INSPIRE validation (intraop NEE -> death_inhosp)
- n=130960, deaths=1555, pressor-exposed=3564.
- Adjusted (age+ASA+duration): {'n': 127074, 'events': 1384, 'event_rate': 0.011, 'adj_or_per_sd': 1.106, 'ci': [1.081, 1.129], 'auc_adjust_only': 0.812, 'auc_with_exposure': 0.816, 'delta_auc': 0.0044, 'adjusted_for': ['age', 'asa', 'duration']}
- Pressor-exposed tertiles: {'n_per_tertile': [1188, 1188, 1188], 'mortality_per_tertile': [0.0572, 0.0884, 0.1919], 'monotonic_nondecreasing': True, 'cochran_armitage_z': 10.388, 'cochran_armitage_p': 2.825487749297983e-25}
- Pressor-exposed adjusted: {'n': 3394, 'events': 344, 'event_rate': 0.101, 'adj_or_per_sd': 1.4, 'ci': [1.275, 1.54], 'auc_adjust_only': 0.667, 'auc_with_exposure': 0.702, 'delta_auc': 0.0356, 'adjusted_for': ['age', 'asa', 'duration']}

**Verdict B (INSPIRE intraop):** INSPIRE INTRAOP validation (n=130960, 1555 deaths, 3564 pressor-exposed): intraop NEE (norepi+epi) -> death_inhosp adj(age+ASA+duration) OR 1.106/SD [1.081, 1.129] -- REPLICATES (more intraop NEE -> more death). Pressor-exposed tertile death [0.0572, 0.0884, 0.1919] (CA p=2.825487749297983e-25).

## Overall verdict
RESUSCITATION BALANCE + NEE CROSS-VALIDATION. FLUID-vs-PRESSOR BALANCE -> in-hospital mortality (MIMIC, n=76374, 9475 deaths): age-adj OR 2.144/SD [2.095, 2.201] (higher = more pressor-predominant; AUC +0.1288 over age). Tertile mortality [0.0702, 0.0663, 0.2357] (fluid->pressor predominant; monotone False, CA p=0.0) -- NB the lowest tertile is 1.0 no-pressor stays, so raw balance partly encodes 'got a pressor at all'. CO-EXPOSED (both pressor+fluid, n=28124): age-adj OR 3.505/SD [3.345, 3.689], tertile mortality [0.0649, 0.1531, 0.4294] (monotone True) -- the clean within-resuscitated gradient: pressor-predominant is worse. Lactate-adjusted full (n=17742): OR 1.939/SD [1.837, 2.058]; co-exposed+lactate OR 3.398/SD [3.142, 3.698] -- survives severity (lactate) adjustment. VitalDB INTRAOP validation (n=3924, AKI=143): intraop balance -> organ_renal age-adj OR 1.183/SD [0.996, 1.394] -- concordant (pressor-predominant -> more AKI). Tertile AKI [0.0291, 0.0306, 0.0497]. ALL-PRESSOR NEE total load -> in-hospital mortality (MIMIC, 28327 pressor stays, 6120 deaths): Q1 0.0602 -> Q4 0.4735 (RR 7.87x, abs +0.4133); quartiles monotone True, CA p=0.0; age-adj OR 3.181/SD [3.042, 3.308] (log NEE-load, AUC +0.2262 over age). Widening norepi-only to ALL pressors reproduces the dose-response. INSPIRE INTRAOP validation (n=130960, 1555 deaths, 3564 pressor-exposed): intraop NEE (norepi+epi) -> death_inhosp adj(age+ASA+duration) OR 1.106/SD [1.081, 1.129] -- REPLICATES (more intraop NEE -> more death). Pressor-exposed tertile death [0.0572, 0.0884, 0.1919] (CA p=2.825487749297983e-25). HONEST: all observational; pressor-predominance and high NEE both co-vary with illness severity (vasoplegic/refractory shock). We adjust for age (+lactate in MIMIC, +ASA/duration in INSPIRE) and argue from the dose-response shape and cross-cohort reproduction, NOT from causal identification. Fluid restriction vs shock severity cannot be disentangled here.

## Caveats (honest)
- All associations are OBSERVATIONAL. Pressor-predominance and high NEE both rise with illness severity (vasoplegic / refractory shock). Adjustment is age + lactate (MIMIC) / age + ASA + anaesthesia duration (INSPIRE) -- NOT full severity; residual confounding by indication is expected. No causal claim.
- MIMIC fluid totals use inputevents amounts (mL) for the listed crystalloid/colloid itemids only; maintenance/flush/oral intake and blood products are NOT counted, so 'fluid' is the resuscitation-fluid subset, not total intake.
- NEE rate uses MIMIC's already-per-kg catecholamine rates (mcg/kg/min); vasopressin converted units/min*2.5 (a STATED, approximate equivalence). NEE-load = sum(rate*minutes) is an exposure integral, sensitive to segment-duration gating (0<dur<=24h).
- The VitalDB intra-op pressor index sums phe+eph+epi in milligrams (drug-specific units), so it is a crude pressor-exposure index, not a true NEE; read its direction, not its magnitude. INSPIRE NEE (norepi+epi, same units) is a cleaner equivalent.
- INSPIRE lacks intra-op fluid VOLUME columns, so the balance metric (A) cannot be replicated there; only the NEE finding (B) is cross-validated in INSPIRE.
- VitalDB intra-op outcome is post-op AKI (organ_renal), a DIFFERENT endpoint than ICU mortality -- concordant direction across endpoints is the cross-validation signal.
