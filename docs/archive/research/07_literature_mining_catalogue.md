# Literature-Mining Catalogue — NEJM · JAMA · Nature (2014–2025)

**Purpose.** A curated, PubMed-verified catalogue of observational (and minable-secondary)
studies in the top general-medicine and science venues, mined for new studies that fit this
program's proven template: **measurement or definitional bias → differential misclassification
by subgroup**, runnable on our data (MIMIC-IV, eICU-CRD, SICdb, MIMIC-IV-ECG).

**Method.** Four parallel librarian+methodologist sweeps (NEJM ×2 by domain, JAMA-family,
Nature-family), each verifying every entry against PubMed (title + first author + year + PMID +
DOI) and instructed to flag anything unverifiable rather than fabricate. Compiled 2026-07-03.

**Verification discipline.** Every citation below carries a real PMID confirmed by the sweeps.
Where a famous paper is *not* in the requested venue, it is flagged (do not miscite). Nothing
here is invented.

---

## Part A — Catalogue of verified studies

### A1. NEJM — measurement bias, race-in-algorithms, disparities, target-trial emulation

| Study | Topic | PMID | Finding |
|-------|-------|------|---------|
| Sjoding 2020 | Pulse-ox racial bias | 33326721 | Black patients ~3× occult hypoxemia (SaO₂<88 despite SpO₂ 92–96). **Template anchor.** |
| Vyas 2020 | Race-correction review | 32853499 | "Hidden in Plain Sight" — catalogues race-adjusted algorithms (eGFR, VBAC, ASCVD, STONE, PFT) that divert resources from Black patients. |
| Manrai 2016 | Genetic misclassification | 27532831 | HCM variants called "pathogenic" over-represented in Black Americans; later reclassified benign — non-diverse controls → differential misdiagnosis. |
| Inker 2021 | Race-free eGFR | 34554658 | New CKD-EPI creatinine+cystatin-C equations remove race; cystatin-C most accurate without race. |
| Hsu 2021 | Ancestry & GFR | 34554660 | Neither self-reported race nor genetic ancestry improves GFR estimation once biomarkers included. |
| Pottel 2023 | GFR without race **or sex** | 36720134 | EKFC cystatin-C equation estimates GFR without race or sex. |
| Diao 2024 | Race-neutral spirometry | 38767252 | Race-neutral PFT equations reclassify impairment/disability/eligibility for 369,077 people. |
| Neumann 2019 | hs-troponin thresholds | 31242362 | Validated hs-troponin rule-in/out cutoffs — reference for uniform-vs-sex-specific misclassification. |
| Dickerman 2021 | Target-trial emulation (VA) | 34942066 | 440k-veteran emulated vaccine trial — EHR comparative-effectiveness template. |
| Hubbard 2024 | TTE methods | 39588897 | "Target Trial Emulation — Potential and Pitfalls" (design wrapper). |
| Barnett 2023 | OUD treatment disparity | 37163624 | Black/Hispanic Medicare enrollees get far less buprenorphine/naltrexone. |
| Garcia 2022 | Bystander-CPR disparity | 36300973 | Black/Hispanic patients less likely to receive bystander CPR. |

### A2. NEJM — critical care / nephrology (mostly RCTs; secondary/measurement questions minable)

| Study | Topic | PMID | Finding |
|-------|-------|------|---------|
| Asfar 2014 (SEPSISPAM) | MAP target | 24635770 | MAP 80–85 vs 65–70: no mortality difference (motivates the MAP-65 measurement question). |
| Amato 2015 | Driving pressure | 25427113 | Driving pressure, not Vt/PEEP alone, tied to ARDS survival (OBS mediation). |
| Semler 2018 (SMART) | Balanced vs saline | 29485925 | Balanced crystalloids lower death/RRT/renal dysfunction. |
| Seymour 2017 | Sepsis bundle timing | 28528569 | Each hour to antibiotic in the 3-h bundle → higher mortality (NY-mandate cohort). |
| STARRT-AKI 2020 | RRT timing | 32668114 | Accelerated RRT: no mortality benefit, more dialysis dependence. |
| Schjørring 2021 (HOT-ICU) | O₂ target | 33471452 | PaO₂ 60 vs 90: no mortality difference. |
| ICU-ROX 2019 | O₂ target | 31613432 | Conservative O₂: no ventilator-free-day difference. |
| Holst 2014 (TRISS) | Transfusion trigger | 25270275 | Hb 7 vs 9 g/dL: equivalent mortality (motivates the Hb-method-discordance question). |

### A3. JAMA family — device bias, race-in-algorithms, prediction miscalibration, sex thresholds

| Study | Journal | PMID | Finding |
|-------|---------|------|---------|
| Fawzy 2022 | JAMA Intern Med | 35639368 | Pulse-ox overestimates SaO₂ in Asian/Black/Hispanic COVID → occult hypoxemia ~29% vs 17% + delayed therapy eligibility. |
| Wong 2021 | JAMA Netw Open | 34730820 | SpO₂–SaO₂ "hidden hypoxemia" by race (eICU+MIMIC) → higher SOFA, mortality, lactate. |
| Zelnick 2021 | JAMA Netw Open | 33443583 | eGFR race coefficient overestimated GFR ~3 mL/min, delayed Black transplant-listing ~1.9 yr. |
| Bragg-Gresham 2021 | JAMA Netw Open | 33512516 | Removing Black race coefficient raises estimated CKD prevalence in Black adults. |
| Diao 2024 | JAMA | 39073797 | Race-free PREVENT reclassifies ~half of US adults; 15.8M lose statin/antihypertensive eligibility. |
| Anderson 2024 | JAMA Intern Med | 38856978 | PREVENT lowers ASCVD risk most in Black adults; 17.3M lose statin eligibility. |
| Hong 2023 | JAMA | 36692561 | Stroke-risk models show consistently worse discrimination in Black vs White across 4 cohorts. |
| Rubini Giménez 2016 | JAMA Cardiol | 27653005 | Sex-specific hs-cTnT cutoffs reclassified only 3/2734 → uniform cutoff "adequate" (**null**, consistent with our threshold-optimization caution). |
| Bird 2024 | JAMA | 38241060 | Denosumab vs bisphosphonates: 41% vs 2% severe *albumin-corrected* hypocalcemia (older female dialysis). |
| Wong 2021 | JAMA Intern Med | 34152373 | Epic Sepsis Model external AUC 0.63, poor calibration, high alert burden. |

### A4. Nature family — AI/EHR bias, device/measurement, ancestry calibration, ICU foundation work

| Study | Journal | PMID | Finding |
|-------|---------|------|---------|
| Seyyed-Kalantari 2021 | Nat Med | 34893776 | CXR classifiers selectively **underdiagnose** Black, female, low-SES, intersectional patients. |
| Groh 2024 | Nat Med | 38317019 | Physicians + AID ~4 pts less accurate on dark vs light skin. |
| Komorowski 2018 | Nat Med | 30349085 | "AI Clinician" RL sepsis policy (MIMIC-III+eICU) — inputs (SpO₂/lactate/creatinine) are themselves subgroup-biased (mining angle). |
| Yang 2024 | Nat Med | 38942996 | "Fair" imaging AI loses fairness OOD by encoding demographics as a shortcut. |
| Omar 2025 | Nat Med | 40195448 | Identical vignettes → LLMs give different management by race/sex/income. |
| Hager 2024 | Nat Med | 38965432 | LLMs fail real MIMIC clinical decision-making (dangerous ordering/management). |
| Orcutt/Parikh 2025 | Nat Med | 39753967 | "TrialTranslator" — RCT benefit shrinks in high-risk real-world EHR phenotypes. |
| Zhang 2024 | Nat Commun | 38956041 | X-chromosome dosage drives statin dysglycemia; women more susceptible (sex-differential ADR). |
| Shapiro/O'Reilly 2023 | npj Digit Med | 37500721 | 72M SpO₂ readings — small but significant race/sex differences in reference SpO₂. |
| Jiang/Oermann 2023 | Nature | 37286606 | NYUTron EHR-notes LLM predicts readmission/mortality/LOS — no subgroup-fairness audit (gap). |

*(Full per-sweep tables with DOIs and additional entries — Caironi/ALBIOS, Frat/FLORALI, Khanna/ATHOS-3,
Annane/APROCCHSS, Combes/EOLIA, Barbar/IDEAL-ICU, Girard/MIND-USA, Shehabi/SPICE-III, Self/SALT-ED,
Walther/Hsu eGFR, Ghosh, McCormick, Kurani, Walsh, Butler, Smit, Huang, Bhagwat, STANDING-Together,
Topol — are preserved in the sweep logs; the above are the highest-relevance anchors.)*

---

## Part B — Consolidated mining table (deduplicated across all four sweeps)

Ideas ranked by **cross-venue support × template fit × feasibility**, annotated with **our program
status** (what we've already run and its verdict). "Support" = how many of the 4 sweeps independently
proposed it — a strong signal of both importance and non-obviousness.

| Idea | Cross-venue support | Our program status | Datasets | Feasibility |
|------|:---:|--------------------|----------|:---:|
| **Two-method electrolyte discordance (K⁺/Na⁺/glucose/lactate/Hb) flips a decision threshold by subgroup** | 4/4 | **PARTLY DONE** — sodium (done, docs 03/04), potassium false-hyperK (done, doc 02); glucose-in-shock **run this cycle = weak/null**; lactate & Hb-transfusion **NOT yet run** | MIMIC-IV, eICU, SICdb | High |
| **Albumin-corrected calcium vs ionized calcium fails by subgroup** | 4/4 | **DONE = FLAGSHIP** (doc 01) — corrected-Ca racially miscalibrated, multi-site | MIMIC-IV, eICU, SICdb | High |
| **KDIGO absolute-creatinine AKI criterion biased by sex/muscle mass** | 4/4 | **RUN this cycle → survives but reframed/demoted** (doc 06; not novel, isolated-absolute only, <0.6-baseline caveat) | MIMIC-IV, eICU, SICdb | High |
| **Bazett vs Fridericia QTc over-correction → false "prolonged QT" flags by sex/HR** | 3/4 | **NOT RUN — top new lead**; we already have 800k machine QT/RR extracted | MIMIC-IV-ECG + meds | High |
| **Oscillometric cuff vs arterial-line MAP discordance → MAP-65 mistitration** | 4/4 | **RUN this cycle → KILLED by red-team** (RTM binning artifact; harm reverses on sustained; known device behavior) | MIMIC-IV | — |
| **Pulse-ox occult hypoxemia → downstream care/score misclassification (SOFA resp, SF-ratio/ARDS, O₂ target, trial eligibility)** | 4/4 | **PARTIAL** — direction replicated this cycle (OR 1.47) but SaO₂ extract arterial/venous-contaminated; needs chartevents 220227. Core discordance heavily published (Sjoding/Fawzy/Wong) — **novelty must be the downstream-decision endpoint** | MIMIC-IV, eICU | High (after re-extract) |
| **eGFR equation choice (race-based vs race-free; CG vs CKD-EPI) → differential renal drug-dosing at ICU admission** | 2/4 | **NOT RUN — strong new lead**; vancomycin/DOAC/contrast threshold crossings | MIMIC-IV, eICU | High |
| **Uniform vs sex-specific hs-troponin threshold → differential MI misclassification in women** | 3/4 | **NOT RUN — but null-risk flagged** (JAMA Rubini Giménez reclassified 3/2734). Run only as low-cost confirmatory arm | MIMIC-IV labs + ECG | Med |
| **ECG voltage LVH criteria (Sokolow-Lyon/Cornell) miscalibrated by sex/race** | 1/4 | **NOT RUN — new lead**; validate vs echo | MIMIC-IV-ECG + echo | Med |
| **Sepsis-RL / prediction-model inputs are themselves subgroup-biased (artifactual-disparity reframe of a Nature-Medicine flagship)** | 1/4 | **NOT RUN — high-impact critique**; more null/scope risk | MIMIC-IV, eICU | Med |

**Deprioritized (per LESSONS):** treatment-disparity replications (Barnett/Morden/Garcia) reproduce
*known* disparities rather than the artifactual-measurement reframe; causal/IV/threshold-optimization and
single-marker prognosis have historically nulled for us; target-trial-emulation (Dickerman/Hubbard) is
best used as a **design wrapper** around the discordance ideas, not a standalone.

---

## Part C — New leads to queue (not yet run), ranked

Each carries a **mandatory PubMed novelty pre-screen** first (cycle-9 lesson: the creatinine mechanism
turned out to be already published — check before running, not after).

1. **Bazett vs Fridericia QTc over-correction by sex/HR** (support 3/4, high feasibility, data in hand).
   Cleanest new "trusted formula fails by subgroup" fit; 800k machine ECGs already extracted; measured
   outcome (QT interval); directly actionable (drug-QT safety alerts). *Novelty risk: moderate — check
   the QTc-formula literature, which is large.*
2. **eGFR equation → differential ICU renal drug-dosing** (support 2/4, high). Extends the well-cited
   JAMA/NEJM race-free-eGFR line into an unclaimed ICU *dosing-action* endpoint.
3. **Lactate and hemoglobin two-method discordance at Sepsis-3 / transfusion thresholds** (support 4/4
   for the family, high). Completes the electrolyte-discordance panel we've partly built.
4. **Occult hypoxemia → downstream decision endpoint** (support 4/4) — only after re-extracting clean
   arterial SaO₂ (chartevents 220227); frame strictly on the care-decision endpoint, since the raw
   discordance is saturated in the literature.
5. **Sex-specific troponin** (support 3/4) — low-cost confirmatory arm only; JAMA evidence suggests a
   likely null.

**White-space signal (from the Nature sweep):** no Nature-family journal has published the ICU
paired-SpO₂–SaO₂ occult-hypoxemia → differential-treatment study at MIMIC scale — a genuine venue gap
if lead 4 is executed cleanly.

---

## Through-line

The four-venue sweep independently re-derived this program's core bets — corrected-calcium, two-method
electrolyte discordance, KDIGO-creatinine, and (the now-killed) cuff-MAP — confirming the template is
well-aligned with what top journals treat as important. The genuinely *new* actionable leads it adds are
the **QTc-formula** and **eGFR-drug-dosing** studies, both high-feasibility on data we already hold.
