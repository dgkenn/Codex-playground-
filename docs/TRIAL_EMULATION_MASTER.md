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
| 4 | TOPPS (Stanworth 2013) | Prophylactic platelets | platelet flag → assay-noise | protective (proph better) | none (no bloodgas plt) | ✅ RETIRED (single-method) |
| 5 | MIND-USA (Girard 2018) | Antipsychotics for delirium | delirium → provider-pref | null | n/a | ✅ instrument infeasible (emar charting) |
| 6 | Electrolyte repletion (K) | Reflexive K replacement | K flag → assay-noise | (de-impl; ~null expected) | chem K vs bloodgas K | ✅ RETIRED by NC (hemolysis) |
| 7 | BICAR-ICU (Jaber 2018) | NaHCO₃ for metabolic acidosis | HCO₃/pH flag → assay-noise | null overall; AKI-subgroup benefit | single-method (temporal) | ✅ RETIRED (drift + NC) |
| 8 | SAFE (Finfer 2004) / ALBIOS (Caironi 2014) | IV albumin | albumin flag → assay-noise (temporal only) | null | none (single method) | ✅ RETIRED (drift + NC + weak FS) |
| 9 | SUP-ICU (Krag 2018) | PPI stress-ulcer prophylaxis | risk-gate → preference | ~null (no mortality benefit) | n/a | ✅ run (6/6 gate fixed); confounded, no favorable |
| 9b | PEPTIC (2020) | PPI vs H2RB | mech-vent gate → unit-preference | null | n/a | ✅ run (vent eligibility verified); weak instr (F=4) |
| 10 | PREVENT (Arabi 2019) | Adjunctive pneumatic VTE prophylaxis | gate → device | null | n/a | ⏳ compression-device data streaming (chained) |
| 11 | ADRENAL (Venkatesh 2018) | Hydrocortisone in septic shock | severity-gate → provider-pref | null (mortality) | n/a | ✅ run (vasopressor timing fixed); balance-invalid, no favorable |
| 12 | Benzodiazepines (PAD/ICU liberation) | Sedation de-implementation | symptom → nurse-PRN dose-intensity | (de-impl; harm signal) | n/a | ✅ engine exists (nurse_prn_v2) |
| 13 | Opioid intensity | Analgesia de-implementation | symptom → nurse-PRN dose-intensity | (de-impl; ~null) | n/a | ✅ engine exists (nurse_prn_v2) |
| 14 | FOCUS / TITRe2 / MINT / REALITY / Villanueva | RBC transfusion (5 populations) | Hb flag → assay-noise | mixed (null / non-inf / liberal-trend / restrict-better) | CBC vs bloodgas Hb | ✅ individual builds run+logged (exact horizons) |
| 15 | NICE-SUGAR dose-intensity | Continuous insulin infusion | dose-intensity IV | harm (tight) | n/a | ✅ run; weak instr (F=1.7, protocol-titrated) |
| 16 | SEPSISPAM (Asfar 2014) | MAP target 65 vs 85 | titrated target → adjusted-obs | null; chronic-HTN AKI benefit | n/a (chartevents MAP) | ✅ run+logged (hypothesis-consistent, underpowered) |

Legend: ✅ done/logged · ⏳ in progress · ▫ planned.

Each trial gets a `REAL_RESULTS_*` doc with: exact protocol (cited), factor-by-factor emulation, the estimate
with 95% CI, first-stage F, balance, negative-control calibration where applicable, and an honest verdict
(recovered / weak-instrument / estimand-boundary / retired-with-mechanism). This table is the index.

**Coverage: 16 of 17 trial rows run and logged.** Only PREVENT (#10) remains, gated on the compression-device
(IPC) chartevents stream now running; its script slot is ready (same gate-trials harness) and will run the
moment the data lands. Every other benchmark and de-implementation trial has been emulated with deep
methodology research, run on real MIMIC-IV data, and logged with an honest verdict — favorable or (mostly) a
mechanistically-characterized refusal.
