# Methods & Reproducibility

Companion to the findings documents (01–05). This describes the data sources, cohort
construction, statistical methods, and the script inventory needed to reproduce every
number. All statistics themselves live in the findings docs and in the authoritative
log [`../REAL_RESULTS_SODIUM_RACE_BIAS.md`](../REAL_RESULTS_SODIUM_RACE_BIAS.md).

---

## 1. Data sources

| Cohort | Access | Population | Race variable | Reference methods used |
|--------|--------|-----------|---------------|------------------------|
| **MIMIC-IV** (Beth Israel Deaconess, Boston) | PhysioNet credentialed | ICU + ED | Yes (admissions.race) | blood-gas Na/K/Cl (direct ISE), ionized Ca; chemistry Na/K/Cl/total-Ca (indirect ISE) |
| **eICU-CRD** | PhysioNet credentialed | 208 US hospitals | Yes | ionized Ca; osmolality-reconstructed Na (no paired blood-gas Na) |
| **SICdb** (Salzburg Intensive Care database, Austria) | PhysioNet credentialed | ICU, single Austrian center | **No** | dual-method chemistry + blood-gas; total protein (36% coverage) |
| **MIMIC-IV-ECG** | PhysioNet credentialed | 800,036 12-lead ECGs | via subject link to MIMIC-IV | machine measurements: QT, QTc(Bazett), QRS, PR, axes, report text |

**Why the cohorts play the roles they do:**
- The **racial differential** needs *race* + *two measurement methods of the same analyte*
  on the same patient. Only MIMIC-IV has this for sodium; MIMIC-IV **and** eICU/SICdb have
  it for calcium (ionized Ca is on every blood-gas panel), which is why **calcium breaks the
  single-center wall** and sodium does not.
- The **mechanism** (protein → bias dose-response) needs only *protein* + *two methods*, not
  race — so **SICdb** (Austrian, no race field) provides a clean, well-powered, cross-national
  replication of the mechanism.
- **MIMIC-IV-ECG** is used as an *independent physiological arbiter*: the heart's electrical
  behavior confirms or refutes what the lab claims (peaked-T/wide-QRS for hyperkalemia; QTc
  for hypocalcemia).

### Access & handling
- All access is credentialed and supplied at **runtime** (the user's own PhysioNet / AWS
  credentials); nothing is committed.
- PhysioNet files are streamed with `wget --netrc` (the agent proxy does not serve mid-file
  byte ranges; `curl` is unavailable). Large tables are filtered on the fly:
  `wget --netrc -O- URL | gunzip -c | python filter.py`.
- **No raw or PHI-adjacent data is committed** — raw extracts live only in the gitignored
  `scratchpad/`.

---

## 2. Cohort construction (paired-measurement design)

The core design is a **within-patient paired-measurement contrast** that holds the *true*
analyte value fixed and asks whether the *reported* (indirect-ISE / total) value differs by
race.

1. **Extract both methods** for the analyte (e.g. chemistry sodium `lab_na.csv` and blood-gas
   sodium `lab_nabg.csv`), each as `(subject/hadm, charttime, value)`, filtered to
   physiologic ranges to drop parse errors.
2. **Pair** each reference draw with the nearest same-analyte draw of the other method within
   a time window (default **≤1 h**; sensitivity at **≤10 min** to rule out temporal drift
   between two separate blood draws).
3. **One pair per admission** (first qualifying pair) for the primary analysis; subject-level
   clustering / one-obs-per-subject collapse as a sensitivity.
4. **Race** mapped from `admissions.race` to BLACK / WHITE / OTHER; analysis restricted to
   BLACK vs WHITE for the racial contrast.
5. **Bias** = reported − reference (e.g. chem Na − blood-gas Na). The racial differential is
   the BLACK−WHITE difference in this bias at matched true value.

Calcium uses **ionized Ca** as the true value and **total Ca** as the reported value; "masked
hypocalcemia" = ionized < 1.12 mmol/L but total ≥ 8.5 mg/dL. Potassium uses **blood-gas K**
as truth and **chemistry K** as reported; "false hyperkalemia" = blood-gas 3.5–5.0 but
chemistry ≥ 5.5.

---

## 3. Statistical methods

- **Linear models (OLS)** with **heteroskedasticity-robust** (sandwich) SEs for the
  continuous bias contrasts; **subject-clustered** SEs where multiple pairs per patient.
- **Logistic regression** (Newton–Raphson, `logit_cl`) with **cluster-robust** SEs for the
  misclassification outcomes (false-hyponatremia label, false-hyperkalemia, masked
  hypocalcemia, hard outcomes). Cluster = subject_id.
- **Adjustment sets**: true (reference) value, age, creatinine (renal), albumin, lipids,
  relevant disease flags — specified per analysis in the findings docs.
- **Selection controls**: inverse-probability-of-entry weighting (IPW) for who gets a paired
  draw (severity-adjusted), and stratification by sampling intensity (pairs/stay) as a
  selection probe.
- **Fixed effects**: hospital FE (eICU) and first-care-unit FE (MIMIC) to separate
  within-analyzer from between-site confounding. *Note the documented interpretation limit:*
  care-unit FE within one hospital controls case-mix, **not** a hospital-wide analyzer effect.
- **Mediation**: protein / globulin added to the racial model to quantify attenuation
  (reported honestly as underpowered where n is small, e.g. MIMIC n=268).
- **Independent references**: measured **osmolality** as a second sodium reference (removes
  reliance on trusting the blood-gas analyzer); **ECG** as a physiological arbiter.
- **Multiplicity**: the main differential (z=−12.6) survives Bonferroni for 10 tests by >4
  orders of magnitude; SICdb (z=−28.6) is independent of MIMIC multiplicity.

All models are implemented in **NumPy only** (no sklearn/statsmodels dependency) — small,
self-contained, re-runnable estimators (`ols`, `logit`, `logit_cl`, `z`) defined at the top
of each script.

---

## 4. Script inventory

All scripts live in the gitignored `scratchpad/` (they read raw extracts that must not be
committed). Grouped by finding.

### Sodium / chloride
| Script | Purpose |
|--------|---------|
| `sodium_confounders.py` | core racial differential + confounder adjustment |
| `sodium_ipw_entry.py` | IPW-for-entry selection control |
| `sodium_disease_confound.py` | exclude/adjust globulin-raising diseases (myeloma/cirrhosis/HIV/CKD) |
| `sodium_cluster_se.py` | subject-clustered SE / one-obs-per-subject collapse |
| `sodium_matrix_hct.py` | hematocrit / matrix-artifact check; Hgb-discordance adjustment |
| `sodium_mechanism_definitive.py`, `sodium_mech_robust.py` | protein/globulin dose-response; care-unit FE |
| `sodium_extend.py`, `sodium_anion_gap.py` | chloride, anion gap, panel extension |
| `sodium_harms.py`, `sodium_harms2.py` | false-label consequences; calcium harm test |

### Calcium
| Script | Purpose |
|--------|---------|
| `calcium_outcomes.py` | masked-hypocalcemia → hard-outcome test (mortality/arrhythmia/arrest/seizure), clustered, mediation via repletion |
| `correction_tool.py` | standard albumin-correction vs proposed globulin-inclusive correction; residual racial bias at matched ionized |

### Potassium
| Script | Purpose |
|--------|---------|
| `potassium_rigor.py` | racial K-bias, tight-window, clustered; false-hyperkalemia adj OR; mechanism-distinctness (corr with Na bias); harm chain scaffold |

### ECG arbitration
| Script | Purpose |
|--------|---------|
| `extract_ecg.py`, `extract_ecg_full.py` | build `ecg_features.csv` (183,983) / `ecg_features_full.csv` (800,035) from MIMIC-IV-ECG machine measurements: QT=t_end−qrs_onset, QTc_bazett=QT/√(RR/1000), QRS, PR, keyword flags (hyperK/longQT/LVH/MI/AF) |
| `ecg_link.py` | link ECGs to electrolyte draws; potassium & calcium arbitration |
| `qt_outcomes.py` | masked hypocalcemia → unrecognized long QT → arrhythmia/mortality (the fragile chain) |

### Osmolality arbiter / robustness
| Script | Purpose |
|--------|---------|
| `mimic_osm_arbiter.py`, `mimic_osm_robust.py` | measured-osmolality second reference for sodium; osmolar-gap sensitivity |

### ECG feature definitions (validated distributions)
QT = `t_end − qrs_onset`; QTc(Bazett) = `QT / √(RR/1000)`; QRS = `qrs_end − qrs_onset`;
PR = `qrs_onset − p_onset`. Validated medians: QRS 94 ms, PR 160 ms, QTc 443 ms. Values
filtered to physiologic ranges (e.g. QTc 300–700 ms) to drop parse outliers.

---

## 5. Reproduction procedure

1. Obtain credentialed access to MIMIC-IV, eICU-CRD, SICdb, MIMIC-IV-ECG (PhysioNet).
2. Stream the required tables into `scratchpad/` via `wget --netrc -O- … | gunzip -c | …`
   (see per-analyte `ls()` loaders in each script for the exact column layout).
3. Run the relevant script with `python scratchpad/<script>.py`. Each prints its cohort
   n's and the estimates that appear in the findings docs.
4. Cross-check printed numbers against [`../REAL_RESULTS_SODIUM_RACE_BIAS.md`](../REAL_RESULTS_SODIUM_RACE_BIAS.md),
   which records the exact figures from the runs that produced this repository.

> **Determinism note:** estimators are deterministic given the same extract; the only source
> of small variation is cohort membership when re-streaming (time-window pairing on identical
> data is deterministic). Physiologic-range filters are fixed constants in each script.
