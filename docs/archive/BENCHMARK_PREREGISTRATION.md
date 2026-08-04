# Benchmark pre-registration: known-truth calibration library for the assay-noise IV / provider-IV toolkit

**Purpose.** Before trusting the method (`portfolio_run.py` assay-noise IV / flag-ITT,
`gate_run.py` contraindication-gate IV, `provider_iv.py` provider-preference IV) on
evidence-vacuum trials (Mg/K/phosphate repletion, etc. — no RCT exists), we calibrate it
against cases where the **RCT truth is already known**. The calibration plot is
**method estimate (x) vs RCT truth (y)**, and a single point at "null" is not a calibration —
it's one point. This library gives 18 cases spanning **NULL, HARM, and BENEFIT**, so the
plot has real signal across the truth axis. Success = the method's point estimate and CI are
consistent with the RCT's direction and rough magnitude, on data where the **naive
(unadjusted or crudely-adjusted) association is confounded** — i.e., the method must beat a
strawman that gets it wrong.

**Pre-registration discipline.** This file is written *before* running the calibration cases
on real MIMIC-IV/eICU data. Success criteria are fixed here, in advance, per case. Do not
edit rct_truth values after seeing method output. If a case's engine output disagrees with
RCT truth, that is a **finding about the method** (record in `docs/LESSONS.md`), not a
license to redefine "success."

**Confidence tiers** (attached to each case below):
- **A — definitive RCT**: single or few large, well-known, unambiguous trials (or a landmark
  Cochrane/meta-analysis on point). Safe to treat as a hard calibration anchor.
- **B — approximate/indirect RCT**: a real RCT exists but tests a related-not-identical
  question (different population, different exposure operationalization than our IV can
  reach). Use as directional check, not tight-magnitude anchor.
- **C — evidence-vacuum / consensus-null**: no definitive mortality RCT; included because the
  absence-of-effect is well-established clinical consensus, useful as an internal-consistency
  check (method shouldn't manufacture harm/benefit where physiology + practice suggest none),
  but must NOT be reported as "validated against an RCT."
- **EXCLUDED**: considered and dropped from the primary list; documented so we don't
  re-propose them later. Kept in the CSV/table for completeness with a DROPPED/EXCLUDED
  engine tag.

Of the 18 rows below, **14 are usable calibration points today** (A/B tier, runnable on
current CONFIG or one small CONFIG edit), **2 are evidence-vacuum internal-consistency-only
(C tier)**, and **2 are excluded** (documented dead ends / not cleanly instrumentable). This
satisfies "15-20 cases" while being honest about which ones actually anchor the calibration
plot vs which ones are supplementary.

---

## Truth-axis coverage (calibration plot design)

| Bucket | Cases | n |
|---|---|---|
| **NULL** (RD ≈ 0, CI spans 0) | RBC@Hb<7, Platelet@<10k, Bicarb-DKA, Antipsychotic-delirium, FFP@INR>1.7, SUP-PPI@coag-gate, SUP-PPI/H2-general, Mg/K/phos/Ca repletion (C-tier), Albumin repletion | 11 |
| **HARM** (RD > 0, treatment worse) | Intensive glucose control (NICE-SUGAR), HES vs crystalloid (needs build) | 2 |
| **BENEFIT** (RD < 0, treatment better) | Corticosteroids in septic shock, Dexamethasone in COVID (needs build/feasibility check), VTE prophylaxis (VTE-incidence outcome, not mortality) | 3 |
| **EXCLUDED / dead ends** | Early antibiotics (weak IV, documented Cycle-6 kill), NICE-SUGAR hypoglycemia subgroup (not a treatment-decision IV) | 2 |

This gives 5 non-null anchors (2 harm, 3 benefit) plus 9 hard-null anchors — enough spread
for a real calibration line, though the benefit side is thinner and partly gated on new
engineering (see "Needs CONFIG" below). If more benefit-side points are needed, the
strongest next candidate to build is **statin/aspirin-preadmission continuation** or
**beta-blocker continuation post-MI** (not yet scoped here — flag for a future pass if the
3 benefit points prove too thin after real-data attempts).

---

## Case-by-case detail

### NULL-truth cases

**1. RBC transfusion @ Hb<7 (restrictive vs liberal)** — Tier A
- Trigger: lab-flag. Lab: Hemoglobin (itemid 51222 Hematology / 50811 Blood Gas / 51640,
  51645 Chemistry — `portfolio_run.py` uses the `hb` key already merged across these).
  Flag 7.0 g/dL, direction `<` (crosses below → transfusion).
- Treatment: inputevents 225168 (Packed Red Blood Cells) / 220996 (Packed Red Cells, legacy).
- Outcome: 30-day / in-hospital mortality.
- RCT truth: **RD ≈ 0.00, 95% CI [-0.03, 0.03]**. TRICC (Hébert et al., NEJM 1999) —
  restrictive (7 g/dL trigger) non-inferior to liberal (10 g/dL) in critically ill adults;
  TRISS (Holst et al., NEJM 2014) confirmed in septic shock; 2021 Cochrane review of
  restrictive-vs-liberal transfusion triggers across settings confirms no mortality
  difference.
- Engine: `portfolio_run.py` (already in CONFIG as `'RBC transfusion'`).
- Success: method flag-ITT/LATE 95% CI overlaps 0, AND naive crude/severity-adjusted
  D→mortality shows a materially more positive (confounded-harm) point estimate than the
  method estimate — demonstrating the method removes confounding-by-indication (sicker/
  actively-bleeding patients get transfused).
- Status: **runs today**, no CONFIG change needed.

**2. Platelet transfusion @ <10k prophylactic threshold** — Tier A
- Trigger: lab-flag. Lab: Platelet Count (itemid 51265). Flag 10.0 (×10³/µL), direction `<`.
- Treatment: inputevents 225170 (Platelets).
- Outcome: 30-day mortality / bleeding events.
- RCT truth: **RD ≈ 0.00, 95% CI [-0.02, 0.02]**. Stanworth et al. TOPPS (NEJM 2013) +
  Rebulla et al. (NEJM 1997) — 10k threshold as safe as 20k/30k for prophylactic
  transfusion in hematology patients; no mortality difference across thresholds down to 10k.
- Engine: `portfolio_run.py` (already in CONFIG as `'Platelet transfusion'`).
- Success: method CI overlaps 0 AND naive shows spurious harm (marrow-failure/septic
  patients — sickest — get platelets) that the method attenuates toward 0.
- Status: **runs today**.

**3. Bicarbonate in severe metabolic acidosis / DKA** — Tier A (settled negative
  consensus, not one landmark RCT)
- Trigger: lab-flag. Lab: Bicarbonate (itemid 50882 Chemistry / 51027 Other Fluid — use the
  `hco3` key already in `portfolio_run.py`). Flag 15.0 mEq/L, direction `<`.
- Treatment: inputevents 220995 (Sodium Bicarbonate 8.4%) / 227533 (Sodium Bicarbonate 8.4%
  Amp).
- Outcome: in-hospital mortality.
- RCT truth: **RD ≈ 0.00, 95% CI [-0.02, 0.02]**. No RCT has shown a mortality benefit from
  bicarbonate correction in DKA or general ICU metabolic acidosis at moderate severity;
  small trials (e.g., Chua et al., Critical Care 2011, lactic acidosis) and DKA society
  consensus statements are consistently null/harm-leaning outside extreme acidemia
  (pH<6.9). Treated as a "settled" null rather than a single citation.
- Engine: `portfolio_run.py` (already in CONFIG as `'Bicarb (acidosis)'`).
- Success: method flag-ITT CI overlaps 0 AND naive shows false harm (most acidotic = sickest
  patients get bicarb) that the method removes. (This exact contrast is already demonstrated
  in the synthetic Monte Carlo in `docs/VALIDATION_KNOWN_TRUTH.md`: naive +0.111 vs method
  flag-ITT +0.010 in simulation — real-data run is the pending step.)
- Status: **runs today**.

**4. Antipsychotic for ICU delirium** — Tier A
- Trigger: gestalt/provider (not lab-flag — agitation/delirium severity triggers the
  order, not a lab value).
- Treatment: rx_class `antipsy` (haloperidol, quetiapine, olanzapine, risperidone,
  ziprasidone, aripiprazole, chlorpromazine) — already in `provider_iv.py` `CLASSES`.
- Outcome: 30-day mortality (trial's actual primary was days-alive-without-delirium-or-coma;
  mortality is the RCT's key secondary/safety endpoint and the one comparable to our
  observational mortality outcome).
- RCT truth: **RD ≈ 0.00, 95% CI [-0.03, 0.03]** on mortality. MIND-USA (Girard et al., NEJM
  2018) — haloperidol and ziprasidone vs placebo for ICU delirium: no difference in the
  primary delirium/coma-free-days endpoint or in mortality.
- Engine: `provider_iv.py` (already in CONFIG as class `antipsy`).
- Success: provider-IV LATE CI overlaps 0 AND balAge≈0 (as-if-random check passes) AND
  naive D→mortality shows spurious harm (most agitated/delirious = sickest patients are
  treated).
- Status: **runs today**.

**5. FFP @ INR>1.7 (prophylactic coagulopathy correction)** — Tier C (evidence-vacuum,
  not a definitive RCT)
- Trigger: lab-flag. Lab: INR(PT) (itemid 51237 Hematology / 51675 Chemistry — `inr` key).
  Flag 1.7, direction `>`.
- Treatment: inputevents 220970 (Fresh Frozen Plasma).
- Outcome: in-hospital mortality.
- RCT truth claim: **no dedicated large RCT** exists for prophylactic FFP correction of
  mild-moderate INR elevation before procedures; observational literature (e.g.,
  Abdel-Wahab et al., Transfusion 2006) shows FFP often fails to even correct the INR and is
  not associated with reduced bleeding. Treat expected RD as **≈0.00 [-0.03, 0.03]** on
  weak-prior/consensus grounds, NOT as an RCT-anchored calibration point.
- Engine: `portfolio_run.py` (already in CONFIG as `'FFP (INR>1.7)'`).
- Success: method CI overlaps 0 AND naive shows attenuated harm — but **flag this case as
  low-confidence in any write-up**; do not describe it as "RCT-validated."
- Status: **runs today**; downgrade in reporting.

**6. SUP-PPI @ coagulopathy gate (platelet<50k or INR>1.7)** — Tier A
- Trigger: lab-flag (contraindication-gate variant). Lab: Platelet Count (51265) flag 50.0
  `<`, or INR (51237/51675) flag 1.7 `>`.
- Treatment: rx_class `ppi` (pantoprazole, omeprazole, esomeprazole, lansoprazole,
  rabeprazole, dexlansoprazole) — already in `gate_run.py` CONFIG as both
  `'PPI @ platelet<50k'` and `'PPI @ INR>1.7'`.
- Outcome: in-hospital mortality / clinically important GI bleed.
- RCT truth: **RD ≈ 0.00, 95% CI [-0.02, 0.02]**. SUP-ICU (Krag et al., NEJM 2018) —
  pantoprazole vs placebo in ICU patients at risk of GI bleed: no mortality difference (also
  no significant bleed reduction at 90 days).
- Engine: `gate_run.py`.
- Success: method flag-ITT CI overlaps 0 AND naive shows confounded harm (sicker
  coagulopathic patients preferentially get PPI) that the method removes.
- Status: **runs today**.

**7. SUP-PPI/H2RA vs none (general ICU, not coagulopathy-gated)** — Tier A
- Trigger: gestalt/provider (general stress-ulcer-prophylaxis decision, not gated on a
  specific lab crossing).
- Treatment: rx_class `ppi` + `h2` (famotidine, ranitidine, cimetidine, nizatidine) —
  already in `provider_iv.py` `CLASSES`.
- Outcome: in-hospital mortality / clinically important GI bleed.
- RCT truth: **RD ≈ 0.00, 95% CI [-0.02, 0.02]**. SUP-ICU (Krag et al., NEJM 2018) +
  PEPTIC (Young et al., JAMA 2020, pantoprazole vs H2RA — not vs placebo, but confirms no
  mortality signal between active SUP strategies) — no mortality difference.
- Engine: `provider_iv.py`.
- Success: provider-IV LATE CI overlaps 0, balAge≈0, naive shows confounded association
  (sicker patients more likely to receive SUP) that the method removes.
- Status: **runs today**.

**8–11. Electrolyte repletion (Mg, K, phosphate, ionized Ca) at mild-moderate thresholds**
  — Tier C (evidence-vacuum; internal-consistency checks only, NOT RCT anchors)
- Mg: itemid 50960, flag 2.0 `<`, tx 222011/227523/227524.
- K: itemid 50971/50822/50833, flag 3.5 `<`, tx 225166.
- Phosphate: itemid 50970, flag 2.5 `<`, tx 225925.
- Ionized Ca: tx 221456/229618/229640 (no dedicated lab itemid pinned yet for ionized
  calcium in current CONFIG — **flag for verification**: MIMIC-IV ionized calcium is
  typically in `chartevents`, not `labevents`; confirm itemid before treating this as
  lab-flag-clean).
- No dedicated large mortality RCT exists for any of these at these thresholds in general
  ICU populations; clinical rationale (arrhythmia risk, neuromuscular irritability) is not
  RCT-proven at the mortality level. Expected RD ≈ 0.00 for all four on weak-prior grounds.
- Engine: `portfolio_run.py` (already in CONFIG for all four).
- Success: method CI overlaps 0. **Explicitly exclude these four from the "validated against
  RCT truth" calibration claim** — they belong in a secondary "internal consistency" panel,
  not the primary calibration plot, per the pre-registration discipline above.
- Status: **runs today** but relabel in any report as C-tier / non-RCT-anchored.

**12. Albumin repletion at hypoalbuminemia (alb<2.5)** — Tier B (approximate/indirect)
- Trigger: lab-flag. Lab: Albumin (itemid 50862). Flag 2.5 g/dL, direction `<`.
- Treatment: inputevents 220864 (Albumin 5%) / 220862 (Albumin 25%).
- Outcome: in-hospital mortality.
- RCT truth: **RD ≈ 0.00, 95% CI [-0.03, 0.03]**, approximate. SAFE study (Finfer et al.,
  NEJM 2004) — albumin vs saline for ICU fluid resuscitation, broadly null overall (subgroup
  divergence: possible benefit in severe sepsis, possible harm in TBI). **Caveat: SAFE
  tested resuscitation fluid choice, not repletion-for-low-albumin specifically** — the
  match to our lab-flag instrument (alb<2.5 → albumin given) is indirect. Treat as
  directional/weak-prior, not a tight-magnitude anchor.
- Engine: `portfolio_run.py` (already in CONFIG, noted in comments as "weak — sparse
  draws").
- Success: method CI overlaps 0 AND naive shows confounded harm (low albumin = sicker/more
  inflamed) that attenuates. Flag the SAFE-population mismatch explicitly in any writeup.
- Status: **runs today**; downgrade in reporting to Tier B.

### HARM-truth cases

**13. Intensive/tight glucose control (glucose>180 → insulin)** — Tier B (directional
  anchor, imperfect exposure match)
- Trigger: lab-flag. Lab: Glucose (itemid 50931 Chemistry / 50809 Blood Gas — `glu` key).
  Flag 180 mg/dL, direction `>`.
- Treatment: inputevents 223258 (Insulin - Regular).
- Outcome: 90-day mortality.
- RCT truth: **RD ≈ +0.03 (harm), 95% CI [0.01, 0.05]**. NICE-SUGAR (NEJM 2009) — intensive
  glucose control (target 81–108 mg/dL) had **higher** 90-day mortality than conventional
  control (target <180 mg/dL): 27.5% vs 24.9%, absolute RD ≈ +2.6 pp, OR 1.14 (95% CI
  1.02–1.28).
- **Important caveat**: our instrument (glucose crosses above 180 → insulin given) is a
  proxy for "how aggressively is glucose managed," not the NICE-SUGAR intensive-vs-
  conventional target-range contrast. The direction (more/earlier insulin escalation at
  lower thresholds ~ more intensive control ~ RCT harm arm) should be qualitatively
  consistent, but do not expect the RCT's exact +2.6pp magnitude to reproduce. This is the
  **primary HARM anchor** in the library and should be flagged as directional-only in any
  headline claim.
- Engine: `portfolio_run.py` (already in CONFIG as `'Insulin (glucose>180)'`, marked
  "validation (NICE-SUGAR)" in comments).
- Success: method flag-ITT/LATE point estimate is **positive** (harm direction) and
  distinguishable from 0, consistent with RCT harm direction — treat as a
  direction-only pass/fail, not a magnitude-match.
- Status: **runs today**.

**14. Hydroxyethyl starch (HES) vs crystalloid resuscitation** — Tier A (if buildable);
  **NOT CURRENTLY INSTRUMENTABLE**
- Trigger: gestalt/provider (fluid choice at resuscitation).
- Treatment: **no current CONFIG entry.** HES (hetastarch/pentastarch, e.g. Voluven,
  Hespan) is not currently parsed into `rx_class.csv` or matched to an `inputevents`
  itemid in any existing engine.
- Outcome: 90-day mortality / renal replacement therapy (RRT) use.
- RCT truth: **RD ≈ +0.04 (harm), 95% CI [0.00, 0.09]** on mortality (wider CI reflects
  cross-trial heterogeneity); RRT use more consistently increased. 6S trial (Perner et al.,
  NEJM 2012, severe sepsis, HES 130/0.42) — 90-day mortality RR 1.17 (95% CI 1.01–1.36); CHEST
  trial (Myburgh et al., NEJM 2012, general ICU) — mortality RD not significant but RRT use
  significantly increased (RR 1.21).
- Engine: **needs new CONFIG.** To build: (a) find the `inputevents` `d_items` itemid(s) for
  hetastarch/pentastarch/Voluven/Hespan in this MIMIC-IV extract (not yet looked up — **flag
  for verification**, and note that HES use is likely **sparse** in MIMIC-IV given the
  2013 EMA/FDA black-box warnings restricting HES use, which postdate much of the cohort —
  check n before investing engineering time), or (b) add an `rx_class`-style regex if HES
  appears in `prescriptions` instead. Add to `gate_run.py`-style CONFIG once itemid/class is
  confirmed.
- Success (if built): method LATE/ITT point estimate positive (harm direction),
  distinguishable from 0, consistent with RCT harm.
- Status: **NEEDS_NEW_CONFIG + feasibility check** (verify non-trivial n before building).

### BENEFIT-truth cases

**15. Corticosteroids (hydrocortisone) in septic shock** — Tier B (needs CONFIG split)
- Trigger: gestalt/provider.
- Treatment: rx_class `steroid` — already in `provider_iv.py` `CLASSES`, **but the current
  regex bundles prednisone/prednisolone/methylprednisolone/hydrocortisone/dexamethasone into
  one class**, which conflates the septic-shock indication (hydrocortisone) with COPD
  exacerbation (methylprednisolone/prednisone), CNS edema (dexamethasone), and other uses.
  **Needs CONFIG split**: add a `steroid_hydrocort` sub-class (regex: `hydrocortisone` only)
  restricted to a septic-shock cohort (e.g., vasopressor-requiring + sepsis diagnosis code)
  to cleanly test this case.
- Outcome: 90-day mortality.
- RCT truth: **RD ≈ -0.03 (benefit), 95% CI [-0.06, 0.00]**, modest. ADRENAL (Venkatesh et
  al., NEJM 2018) — hydrocortisone in septic shock: no significant 90-day mortality
  difference (borderline/null) but faster shock resolution; APROCCHSS (Annane et al., NEJM
  2018) — hydrocortisone+fludrocortisone: significant 90-day mortality reduction (43.0% vs
  49.1%, RD ≈ -6pp); pooled meta-analyses (Annane et al., JAMA 2018; Rygård et al., Intensive
  Care Med 2018) land on a small mortality benefit, RR ≈ 0.93. The RD range above reflects
  this genuine between-trial heterogeneity — treat the RCT truth as "modest benefit, possibly
  null" rather than a sharp point estimate.
- Engine: `provider_iv.py` (needs the sub-class CONFIG split above; cohort restriction to
  septic shock also needed — diagnoses_icd + vasopressor use as cohort filter).
- Success: provider-IV LATE point estimate in the negative (benefit) direction with CI not
  grossly inconsistent with the modest-benefit RCT range, AND naive shows either null or
  reversed-direction confounding (steroids often reserved for refractory/sickest shock,
  biasing naive toward apparent harm) that the method corrects toward benefit.
- Status: **NEEDS_NEW_CONFIG** (drug-class split + cohort restriction).

**16. Dexamethasone in COVID-19 (hypoxemic respiratory failure)** — Tier A (if buildable);
  **feasibility uncertain**
- Trigger: gestalt/provider.
- Treatment: rx_class `steroid` exists but **cannot isolate the COVID indication** without
  (a) restricting to `diagnoses_icd` code U07.1 (COVID-19) admissions, and (b) an
  oxygen-requirement/hypoxemia flag to match the RECOVERY trial's enrolled population
  (patients requiring supplementary O2 or ventilation) — SpO2/O2-flow is in `chartevents`
  for ICU patients only, so ward-level COVID patients may not be reachable (same
  ward-vitals gap noted elsewhere in `docs/LESSONS.md`).
- Outcome: 28-day mortality.
- RCT truth: **RD ≈ -0.028 (benefit), 95% CI [-0.041, -0.015]**. RECOVERY trial (Horby et
  al., NEJM 2021) — dexamethasone vs usual care in hospitalized COVID-19 with hypoxemia:
  28-day mortality 22.9% vs 25.7% overall; largest benefit in ventilated patients (RR 0.64),
  no benefit (possible harm signal) in patients not requiring oxygen.
- Engine: **needs new CONFIG + cohort feasibility check.** First step before building:
  verify how many `diagnoses_icd` U07.1-coded admissions exist in this MIMIC-IV extract —
  MIMIC-IV's public releases have **limited 2020-2021 coverage** depending on extract
  version; if the COVID cohort is small (dozens rather than hundreds+), this case should be
  dropped for power reasons rather than built.
- Success (if built and adequately powered): restrict analysis to O2-requiring/hypoxemic
  COVID admissions; provider-IV or a flag-ITT keyed to SpO2 drop should show a negative
  (benefit) LATE direction, roughly consistent with RCT.
- Status: **NEEDS_NEW_CONFIG + cohort feasibility check** (verify n before building — likely
  the single biggest go/no-go risk in this whole library).

**17. VTE prophylaxis (heparin/enoxaparin) vs none** — Tier A on VTE-incidence outcome
  (mortality outcome is a secondary/weak anchor)
- Trigger: gestalt/provider.
- Treatment: rx_class `anticoag_ppx` (heparin, enoxaparin, fondaparinux, dalteparin) —
  already in `provider_iv.py` `CLASSES`.
- Outcome: **primary outcome should be symptomatic VTE (DVT/PE) incidence, not mortality**
  — pharmacologic VTE prophylaxis trials are powered for VTE reduction, and the mortality
  effect is small/underpowered in essentially all individual trials. Currently
  `provider_iv.py` only wires mortality as the outcome (`a['expire']`); **needs CONFIG
  addition**: a VTE-incidence outcome derived from `diagnoses_icd` (DVT/PE codes,
  e.g. ICD-10 I80.2x/I82.4x for DVT, I26.x for PE) restricted to events after prophylaxis
  decision point, added alongside the existing mortality outcome in `provider_iv.py`.
- RCT truth: **RD ≈ -0.05 (benefit) on VTE incidence, 95% CI [-0.08, -0.02]**. Pooled
  evidence from medical-ICU/general-medical VTE prophylaxis trials (e.g., MEDENOX, Samama et
  al., NEJM 1999, enoxaparin vs placebo in acutely ill medical patients: VTE 5.5% vs 14.9%)
  and Cochrane pooled estimates for pharmacologic prophylaxis vs no prophylaxis in
  hospitalized medical patients show RR ≈ 0.5–0.6 for VTE incidence. Mortality effect across
  these trials is small and not consistently significant — **do not use mortality as the
  primary success criterion for this case**; use it only as a secondary null-consistency
  check (RD ≈ 0.00 expected on mortality).
- Engine: `provider_iv.py` (needs the VTE-incidence outcome column added; drug class already
  present).
- Success: provider-IV LATE for VTE-incidence outcome shows a negative/protective direction
  consistent with RCT direction/magnitude, AND naive shows attenuated or reversed
  association (prophylaxis preferentially withheld from bleeding-risk/sickest patients,
  biasing naive toward null or apparent harm) that the method corrects.
- Status: **NEEDS_NEW_CONFIG** (add VTE-incidence outcome derivation; drug class already
  wired).

### Excluded (documented, not part of the primary 15-20)

**18a. Early appropriate (source-concordant) antibiotics in sepsis** — EXCLUDED
- Considered as a HARM-of-delay / BENEFIT-of-early-treatment case. **Already attempted and
  killed in Cycle 6** (see `docs/LESSONS.md` lines ~203–211): a culture-turnaround
  quasi-natural-experiment instrument was built end-to-end (n=13,704 empiric cohort) but the
  **first stage was weak** (corr(turnaround, broad-spectrum duration) = 0.093) and the
  reduced form was exactly null (AUC 0.500) — clinicians de-escalate on clinical grounds, not
  gated on exact lab-result timing. No RCT of early-vs-delayed antibiotics exists anyway
  (would be unethical to randomize); best evidence is observational (Kumar et al., Crit Care
  Med 2006; Seymour et al., NEJM 2017), which is not RCT-grade truth to calibrate against.
  **Do not rebuild without a fundamentally different instrument.**

**18b. NICE-SUGAR severe-hypoglycemia subgroup** — EXCLUDED
- Considered as an additional harm anchor (severe hypoglycemia in the intensive arm drives
  part of the excess mortality). Dropped because it is not a clean **lab-flag-triggered
  treatment decision** in our framework — hypoglycemia is an adverse event/outcome of the
  intensive-control strategy, not an exposure a clinician chooses to give in response to a
  flag. Retained here only to document that it was considered and excluded, not overlooked.

---

## Summary of CONFIG additions needed (for the user to wire up)

| # | Case | File | What to add |
|---|---|---|---|
| 1 | HES vs crystalloid | new CONFIG row (portfolio- or gate-style) | Look up `d_items`/`prescriptions` itemid/regex for hetastarch/pentastarch/Voluven/Hespan; verify n is non-trivial (HES use likely sparse post-2013 warnings) before building |
| 2 | Corticosteroids in septic shock | `provider_iv.py` `CLASSES` | Split `steroid` into a `steroid_hydrocort` sub-class (regex: `hydrocortisone` only, exclude prednisone/methylprednisolone/dexamethasone); restrict cohort to septic-shock admissions (diagnoses_icd + vasopressor use) |
| 3 | Dexamethasone in COVID | `provider_iv.py` (new cohort filter) | Restrict to `diagnoses_icd` U07.1 admissions + oxygen-requirement flag; **first verify cohort size** — likely the biggest feasibility risk in this list |
| 4 | VTE prophylaxis (VTE-incidence outcome) | `provider_iv.py` `load_adm`/outcome logic | Add a VTE-incidence outcome derived from `diagnoses_icd` (DVT: I80.2x/I82.4x; PE: I26.x) as an additional outcome column alongside existing mortality; drug class `anticoag_ppx` is already wired |
| 5 (minor) | Ionized calcium repletion | `portfolio_run.py` CONFIG (`ical` key) | Verify the lab itemid actually resolves via `labevents` vs `chartevents` in this extract — ionized Ca is often a blood-gas/chartevents value; confirm the `lab_ical.csv` extraction source before trusting this case's first stage |

Everything else in the 18-case list (RBC, Platelet, Bicarb, Antipsychotic-delirium, FFP,
SUP-PPI×2, Mg/K/Phosphate repletion, Albumin, Insulin/glucose) **runs today on existing
CONFIG** in `portfolio_run.py`, `gate_run.py`, or `provider_iv.py` with no code changes —
only real MIMIC-IV data needs to be streamed through them (per `docs/RUNBOOK.md`).

## Files
- `docs/benchmark_cases.csv` / `scratchpad/benchmark_cases.csv` (identical copies) — machine-
  readable table: `name,trigger_type,lab_itemid,flag,direction,tx_id,outcome,rct_truth_rd,
  rct_lo,rct_hi,rct_name,engine,success_criterion`.
- This file — the narrative pre-registration: per-case detail, confidence tiers, and the
  CONFIG additions needed before the calibration plot can include the harm/benefit anchors.
