# Candidate Bedside Decision Tools (Mnemonics/Scores) — Anesthesia & Critical Care

Backlog of clinical DECISIONS that would most benefit from a validated, SOFA/qSOFA/CURB-65-style bedside
mnemonic. Ranked with the discriminator adapted for decision-tools. Each is scored on 5 axes and given a
predicted win-likelihood; the single strongest tractability signal is a **✅ objective, less-confounded
intermediate outcome in our data** (the "shock-reversal trick" that made the steroids tool tractable).

**Two tool archetypes (matters a lot for feasibility):**
- **Effect-modifier tool** ("who benefits from treatment X") — confounding-by-indication limited → observational
  build is *trial-ready*, gold-standard validation needs RCT individual-patient-data (IPD). Higher impact,
  harder.
- **Diagnostic / prognostic-threshold tool** ("who will fail / who is at risk") — far less confounded, often
  has a clean objective outcome → more tractable observationally. Lower ceiling of novelty per idea but higher
  hit rate.

**Datasets:** MIMIC-IV, eICU (~200 hosp), SICdb (Salzburg), VitalDB (intraop 500 Hz waveforms), INSPIRE
(121k non-cardiac surgeries), MIMIC-IV-ECG.

Scoring key: Impact / Equipoise+variation / Data-feasibility / Novelty (no dominant tool) / Validation-path.
H=high, M=med, L=low.

---

## CRITICAL CARE

### 1. Steroids in septic shock — who benefits (ANCHOR, in progress)
Effect-modifier. ✅ shock-reversal / vasopressor-free-days intermediate. Impact H / Equipoise H / Data H /
Novelty M (Rajendran 2025 did the naive version; our wedge = bedside score + SRS2-harm proxy + shock-reversal)
/ Validation: ADRENAL/APROCCHSS/VANISH IPD. **Win: HIGH-as-scoped.**

### 2. New-onset AF in sepsis/critical illness — rate vs rhythm, and anticoagulate or not
Two decisions, both tool-less. ~10–25% of septic shock; huge practice variation; anticoagulation is a genuine
stroke-vs-bleed dilemma with NO ICU-specific validated tool (CHA₂DS₂-VASc/HAS-BLED are outpatient, poor in
critical illness). Mnemonic axes: hemodynamic consequence of AF, sepsis severity, structural/embolic-risk
proxies, ICU bleeding markers. Data: MIMIC/eICU/MIMIC-ECG (AF onset, amiodarone/diltiazem/BB, anticoag, stroke/
systemic-embolism + major bleed + mortality). ✅ objective intermediates: rhythm restoration, rate control,
in-ICU stroke/bleed events. The **anticoagulation arm is a RISK tool (less confounded)** — the tractable half.
Impact H / Equipoise H / Data H / Novelty H / Validation: cross-cohort + objective events. **Win: HIGH.**

### 3. Timing of renal replacement therapy in AKI — start now vs watchful waiting
Effect-modifier. AKIKI/ELAIN/STARRT-AKI equipoise (trials mostly favor waiting, but subgroups?). Mnemonic:
refractory acidosis/hyperK/volume-overload trajectory + AKI severity + non-renal organ failure. Data:
MIMIC/eICU (Cr, urine output, K, HCO₃, RRT start, mortality/RRT-dependence). Outcome: mortality, RRT-free days
(confounded — sickest get early RRT). Impact H / Equipoise H / Data H / Novelty M / Validation: strong RCT-IPD
priors. **Win: MEDIUM** (heavily confounded; RCT-IPD validation is the saving grace).

### 4. Extubation — safe-to-extubate / reintubation risk (+ who needs prophylactic post-extubation HFNC/NIV)
✅ **reintubation within 48–72h is a clean, objective, hard-to-game outcome** — one of the most tractable on
this list. SBT passers still fail 10–15%; reintubation → 25–40% mortality. Existing pieces (RSBI, cuff-leak) are
weak and non-composite → room for a better validated mnemonic. The prophylactic-support arm (who benefits from
preemptive HFNC/NIV) is a novel effect-modifier. Data: MIMIC/eICU (vent settings, SBT, extubation/reintubation
timestamps, secretions/cuff-leak proxies). Impact H / Equipoise M-H / Data H / Novelty M-H / Validation:
cross-cohort + objective outcome. **Win: MEDIUM-HIGH.**

### 5. Beta-blockade (esmolol) in tachycardic septic shock — who benefits
Effect-modifier. Morelli 2013 mortality signal (single-center, controversial); the "persistent tachycardia
despite adequate resuscitation + preserved perfusion" phenotype. ✅ HR control + shock-reversal intermediate.
Data: MIMIC/eICU (HR, esmolol/BB, vasopressors, mortality). Challenge: **sparse exposure** (esmolol uncommon in
sepsis) + confounding. Impact M-H / Equipoise H / Data M (exposure sparsity) / Novelty H / Validation: limited.
**Win: MEDIUM.**

### 6. Prone positioning in ARDS — who benefits (moderate-ARDS extension)
Effect-modifier. PROSEVA (severe benefit); under-used; who benefits at moderate PF. **Bonus link to our C12-1
finding:** proning eligibility uses PF/SF, which we showed is racially miscalibrated — a proning tool could
correct that. ✅ oxygenation response intermediate. Data: MIMIC/eICU (position events, PF, vent, mortality).
Impact H / Equipoise M-H / Data M (proning documentation quality) / Novelty M / Validation: PROSEVA priors.
**Win: MEDIUM.**

### 7. VTE prophylaxis in the ICU — pharmacologic hold vs give (bleed-vs-clot)
Diagnostic/risk. Daily decision; Padua/IMPROVE are ward tools that perform poorly in the ICU → real gap.
Mnemonic: ICU bleeding markers (platelets, INR, active bleed, recent procedure) vs thrombosis risk. Data:
MIMIC (prophylaxis administration, VTE dx, bleeding events). Challenge: **VTE/bleed outcome under-ascertainment
in codes.** Impact M-H / Equipoise H / Data M / Novelty M-H / Validation: cross-cohort. **Win: MEDIUM.**

---

## ANESTHESIA / PERIOPERATIVE

### 8. Intraoperative hypotension — personalized MAP floor + fluid-vs-vasopressor branch (prevent AKI/MINS)
Effect-modifier + threshold. Enormous surgical volume; IOH → AKI/MINS/mortality (Sessler); "how low, how long,
treat with what" has no bedside rule; baseline-relative targets debated. **VitalDB 500 Hz intraop MAP + drug
timing is a uniquely rich substrate;** INSPIRE gives 121k cases + AKI/outcomes. ✅ intraop MAP-response is
objective; postop AKI/MINS are hard endpoints. Caution: we NULLED a naive personalized-MAP-floor before (RTM/
confounding) — must use the effect-modifier framing carefully. Impact H / Equipoise H / Data H (VitalDB!) /
Novelty M / Validation: cross-cohort + waveform. **Win: MEDIUM-HIGH (best data of any candidate).**

### 9. Perioperative beta-blocker — continue/initiate or not (who benefits vs harmed)
The canonical effect-modifier: POISE showed ischemia benefit BUT stroke/hypotension harm; guidelines waffle.
Mnemonic: cardiac risk (RCRI-like) vs stroke/hypotension susceptibility. Data: INSPIRE/MIMIC (preop BB, surgery
type, MACE/stroke/mortality). Challenge: confounding. Validation: **POISE IPD exists.** Impact H / Equipoise H /
Data M-H / Novelty M / Validation: RCT-IPD. **Win: MEDIUM.**

### 10. Postoperative disposition — who truly needs ICU vs floor (and who needs MINS/troponin surveillance)
Diagnostic/resource. Common, costly, imperfect tools (SORT/POSPOM); the MINS-surveillance arm (who to screen
with postop troponin) is actionable and novel. ✅ objective outcomes: unplanned ICU escalation, postop troponin
rise, failure-to-rescue. Data: INSPIRE (121k, preop + outcomes), MIMIC (postop ICU). Impact M-H / Equipoise M /
Data H / Novelty M / Validation: cross-cohort + objective. **Win: MEDIUM.**

---

## Bench (strong alternates, swap in as feasibility dictates)
- **NMB reversal — residual-paralysis risk / sugammadex-vs-neostigmine** (very common, no simple score; data
  feasibility on TOF/reversal is the risk — check VitalDB/INSPIRE granularity first).
- **Transfusion threshold — who benefits from liberal** (cardiac/sepsis subgroups; restrictive is default but
  subgroup equipoise remains; MIMIC feasible).
- **Antibiotic duration/de-escalation — who can stop early** (procalcitonin-guided; MIMIC feasible; ✅ objective
  = recurrence/superinfection).
- **Difficult-airway / who needs awake intubation** (LEMON imperfect; high-stakes; data feasibility low here).

## How to run the next round
1. For the top 3–4, first do the CHEAP checks (as with steroids): (a) exposure/outcome co-occurrence at scale
   in our data; (b) a novelty pre-screen for an existing validated tool; (c) a design pre-mortem for the
   confounding ceiling. Kill fast.
2. Prefer candidates with a ✅ objective intermediate outcome — they survive the confounding gate.
3. For effect-modifier tools, confirm an RCT-IPD validation path exists before over-investing (trial-ready is
   the honest ceiling without it).
4. Build the mnemonic with the Kent PATH-statement + Sinha parsimonious-classifier methodology; report
   decision-curve analysis + E-values + cross-cohort (MIMIC→eICU→SICdb/INSPIRE) reproducibility.
