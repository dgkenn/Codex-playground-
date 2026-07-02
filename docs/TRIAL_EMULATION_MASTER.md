# Master tracker — faithful target-trial emulation of ALL benchmark/de-implementation trials

Goal: emulate every trial as closely as possible to its original protocol (all factors), on real MIMIC-IV/HEEDB
data, with the appropriate instrument, and log each. RCT truth is known for each → validates (or bounds) the
de-confounding toolkit. Instrument taxonomy: **assay-noise** (lab-flag trigger, cross-method discordance where
a 2nd same-time assay exists); **provider/nurse-preference** (symptom/gestalt trigger); **gate** (risk-factor
eligibility, no single lab flag).

| # | Trial | Domain | Trigger → instrument | RCT truth | Cross-method assay | Status |
|---|---|---|---|---|---|---|
| 1 | TRICC (Hébert 1999) | RBC transfusion, restrictive | Hb flag → assay-noise | null (restrictive non-inf) | CBC Hb 51222 vs bloodgas 50811 | ✅ recovered |
| 2 | TRISS (Holst 2014) | RBC transfusion, septic shock | Hb flag → assay-noise | null | same | ✅ weak-instr flagged |
| 3 | NICE-SUGAR (Finfer 2009) | Tight glucose control | glucose flag → assay-noise | harm (tight) | chem 50931 vs bloodgas 50809 | ✅ estimand boundary |
| 4 | TOPPS (Stanworth 2013) | Prophylactic platelets | platelet flag → assay-noise | protective (proph better) | none (no bloodgas plt) | ⏳ feasibility |
| 5 | MIND-USA (Girard 2018) | Antipsychotics for delirium | delirium → provider-pref | null | n/a | ⏳ building |
| 6 | Electrolyte repletion (K) | Reflexive K replacement | K flag → assay-noise | (de-impl; ~null expected) | chem K vs bloodgas K | ✅ RETIRED by NC (hemolysis) |
| 7 | BICAR-ICU (Jaber 2018) | NaHCO₃ for metabolic acidosis | HCO₃/pH flag → assay-noise | null overall; AKI-subgroup benefit | chem HCO₃ vs bloodgas (thin, 11k) | ▫ planned |
| 8 | SAFE (Finfer 2004) / ALBIOS (Caironi 2014) | IV albumin | albumin flag → assay-noise (temporal only) | null | none (single method) | ▫ planned |
| 9 | SUP-ICU (Krag 2018) / PEPTIC (2020) | PPI stress-ulcer prophylaxis | risk-gate → gate/preference | ~null (no mortality benefit) | n/a | ▫ planned |
| 10 | PREVENT (Arabi 2019) | Adjunctive pneumatic VTE prophylaxis | gate → gate | null | n/a | ▫ planned |
| 11 | ADRENAL (Venkatesh 2018) | Hydrocortisone in septic shock | severity-gate → provider-pref | null (mortality) | n/a | ▫ planned |
| 12 | Benzodiazepines (PAD/ICU liberation) | Sedation de-implementation | symptom → nurse-PRN dose-intensity | (de-impl; harm signal) | n/a | ✅ engine exists (nurse_prn_v2) |
| 13 | Opioid intensity | Analgesia de-implementation | symptom → nurse-PRN dose-intensity | (de-impl; ~null) | n/a | ✅ engine exists (nurse_prn_v2) |

Legend: ✅ done/logged · ⏳ in progress · ▫ planned.

Each trial gets a `REAL_RESULTS_*` doc with: exact protocol (cited), factor-by-factor emulation, the estimate
with 95% CI, first-stage F, balance, negative-control calibration where applicable, and an honest verdict
(recovered / weak-instrument / estimand-boundary / retired-with-mechanism). This table is the index.
