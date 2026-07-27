# Creative/bespoke methodologies for the 6 trials the assay-noise IV can't touch

The assay-noise IV needs a lab-flag trigger. Six trials are symptom/gestalt/disease-triggered (#2 PPI, #4 benzo,
#5 albumin, #7 opioid, #8 antipsychotic, #10 steroid). Generic provider-preference IV works but has a weak
exclusion restriction. Below: **bespoke** exogenous-variation sources per trial — plus **three cross-cutting
NEW instruments** that are the real methodological payoff (each turns a "no-instrument" treatment into an
identifiable one and generalizes across the portfolio).

## Three NEW cross-cutting instruments (the generalizable contributions)

### A. Contraindication-GATE assay-noise IV — "identify off the withholding side"
Most gestalt treatments have a **measured-value GATE that WITHHOLDS** them, and that gate has assay noise:
- Antipsychotics (#8): withheld if **QTc > 500 ms** (ECG QTc has real measurement/lead/rate-correction noise).
- SUP/PPI (#2) & VTE-ppx (#9): withheld/modified if **platelet < 50k** or **INR > 1.5** (assay noise).
- Steroids in COPD/asthma (#10): increasingly **eosinophil-count**-gated (blood eos has counting noise).
- Benzos in withdrawal (#4): **CIWA-Ar** protocol threshold (subjective, but protocolized).
- Anticoag dosing (#9): **CrCl < 30** dose-reduction threshold.
**Insight:** conditional on true value, which side of the *contraindication* gate a noisy measurement falls
randomizes *withholding* — the exact same noise-IV logic, applied to the gate rather than the indication. This
**extends the assay-noise method to 4 of the 6 "non-lab" trials** via their measured gate. Novel and clean
(a contraindication gate has an even more defensible exclusion restriction than an indication flag — crossing
QTc 500 does little except withhold the drug). This is the single most valuable idea here.

### B. Nurse-level PRN-administration preference IV — "the second decision is more exogenous than the first"
For PRN drugs (benzo #4, opioid #7, antipsychotic #8), the physician writes a standing order but the **nurse
decides whether/when to administer** each dose. Given an active PRN order, *which nurse is on and their
administration propensity* is as-if-random w.r.t. the patient and driven by nurse practice + workload → a
**nurse-preference IV on PRN administration**, conditional on the order existing. Much cleaner than the
physician-order decision (the order-writing is confounded by indication; the administration, given the order, far
less so). Bespoke to inpatient PRN meds, essentially unexploited. Data: `emar` (administration events) + nurse ID.

### C. Attending-rotation time-RDD — "exogenous within-patient shock" (defeats the sicker-episode confound)
Naive within-patient FE fails because the treated episode is the sicker episode. But **scheduled service/attending
handoffs mid-stay** change the prescriber's habit for the **same patient** at an **as-if-random calendar time**
unrelated to the patient's trajectory. Regress treatment continuation/discontinuation on the handoff (RDD in time
within patient): the new attending's deprescribing propensity is the instrument. Applies to any *continued*
reflexive treatment (PPI continued from ICU #2, benzo #4, steroid taper #10). Uses an EXOGENOUS shock, not the
patient's own severity path → fixes within-patient FE's fatal flaw. Data: service transfers / provider changes.

## Bespoke per-trial (ranked; each with its killer reviewer attack)

### #2 PPI/H2 stress-ulcer prophylaxis
1. **Coagulopathy-gate assay-noise** (platelet<50k / INR>1.5 SUP trigger) — cleanest; *attack:* coagulopathy also
   directly raises bleed risk → but that's the exclusion the gate isolates; test with negative-control outcomes.
2. **ICU-unit default-order preference IV** (units differ hugely in reflexive SUP) — *attack:* SUP-happy units
   sicker → condition within unit-type + negative controls.
3. **Transfer-continuation natural experiment** (ICU→ward: SUP should stop, variably does) — de-implementation-
   specific; *attack:* transfer timing ~ recovery → landmark at transfer.

### #4 Benzodiazepines (older inpatients)
1. **Prescriber-preference IV restricted to the SLEEP/insomnia indication** (cleanest, least-confounded
   indication; insomnia ~ random) + **landmark** (exclude baseline delirium) to kill reverse causation.
2. **Nurse-PRN-administration IV** (instrument B) for PRN sedation.
3. **CIWA-gate** design for the alcohol-withdrawal subgroup. *Killer attack across all:* reverse causation
   (delirium→benzo) → landmark/lag design is mandatory; and ascertainment of delirium (CAM charting) → negative controls.

### #5 IV albumin
1. **Albumin-shortage interrupted-time-series/DiD** (documented national shortages = exogenous rationing) —
   strongest IF calendar available (MIMIC dates obfuscated → may be infeasible; flag).
2. **Colloid-vs-crystalloid unit-default preference IV** within the resuscitation indication.
3. Restrict to non-cirrhotic post-op hypoalbuminemia (strip the RCT-settled SBP/HRS bundles). *Attack:* sparse
   albumin draws + inseparable indications → weakest trial; may stay DROP.

### #7 Opioid intensity
1. **Post-op prescriber/anesthesiologist-preference IV WITHIN procedure type** (surgery fixes the pain
   indication → the cleanest natural stratifier) — strongest.
2. **Nurse-PRN-administration IV** (instrument B) — same PRN order, different nurses administer at different rates.
3. Genetic **CYP2D6 metabolizer** as MR for opioid *effect* (complementary, level not decision). *Killer attack:*
   pain severity unmeasured + reverse causation → the procedure-fixed post-op design is the answer.

### #8 Antipsychotics for delirium (RCT-settled → VALIDATION)
1. **QTc>500 contraindication-gate assay-noise** (instrument A) — clean exogenous *withholding*; novel.
2. **Prescriber-preference IV** to recover the MIND-USA null (validation). *Attack:* delirium severity + reverse
   causation + ascertainment → validation framing (recover the known null) disciplines it.

### #10 Systemic corticosteroids
1. **Fix indication to COPD exacerbation**, then **eosinophil-count-gate assay-noise** (eos-guided steroids is
   emerging practice → a measured-value trigger with counting noise) — novel lab-flag angle inside a "non-lab" trial.
2. **Prescriber-preference IV within COPD-exacerbation** (REDUCE gives a duration benchmark).
3. **Stress-dose trigger:** hypotension-threshold for stress-dose steroids. *Killer attack:* indication
   heterogeneity → MUST fix one indication or the estimand is meaningless.

## The upshot for the "universal solvent"
The creative work reveals the real structure: **almost every reflexive treatment has SOME measured gate** (an
indication flag OR a contraindication gate OR a protocol score), and where it doesn't, there is a **second, more
exogenous decision** (nurse administration) or an **exogenous time shock** (attending rotation, shortage,
guideline change). So the near-universal solvent = **{assay-noise IV on indication-flags} ∪ {assay-noise IV on
contraindication-gates (A)} ∪ {nurse-PRN administration IV (B)} ∪ {attending-rotation time-RDD (C)} ∪
{prescriber-preference IV within a fixed indication}**, every estimate **calibrated with negative controls** and
**triangulated** into bounds, and **anchored to the RCTs** we do have. Instruments A/B/C are the new pieces that
push coverage from ~40% (lab-flag only) toward near-universal. Next: build the contraindication-gate runner
(reuses the assay-noise engine on QTc/platelet/INR/eos gates) — highest leverage, minimal new code.
