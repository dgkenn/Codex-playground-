# Findings ledger — HEEDB EEG-foundation-model research machine

Running log of experiments + hostile-review verdicts. Status: PROVISIONAL (not gated) / GATED-NULL
(ran the hostile-review gate, no finding) / SURVIVED (passed gate + external validation) / KILLED.

| # | Cycle | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|---|
| 1 | 1 | Novelty pre-screen: frozen EEG-FM → outcome, cross-site | No prior work combines FM + clinical outcome + multi-site external validation (DELPHI-EEG single-center) | — | white space confirmed |
| 2 | 1 | Design pre-mortem (hostile-review BEFORE running) | 3 CRITICALs: site confound; abnormal-EEG is solved+circular; use ICD/death not report | redesigned → cognitive-ICD primary + mortality secondary + site gate | design gate PASSED |
| 3 | 2 | **Gated cross-site: frozen CBraMod + attention-MIL, S0001↔I0002** (n=327) | **Site-probe embedding→hospital AUC 0.961**; cross-site abnormal 0.50/0.53 (in-sample 0.52); cognitive 0.62/0.58 (underpowered) | **FAILS site-invariance gate** (site-AUC 0.96 ≫ chance); outcome AUCs confounded + ~chance | **GATED-NULL** |
| 4 | 3 | **Site-correction + re-test** (ComBat/CORAL fit on S0001 ref, align I0002; n=327) | Linear site-probe 0.961→**0.585** (both); **nonlinear MIL site-probe 0.96 (ComBat) / 0.99 (CORAL)** — residual site survives. Cognitive outcome on corrected 0.466 (25 pos, inside null band) | Linear harmonization = **false site-invariance assurance** → gate must be nonlinear (novelty **INCREMENTAL**, unpublished in EEG-FM, red-team MAJOR-REVISION). Outcome null = power-calibrated (detects ≥0.3σ, so excludes a *strong* frozen signal, not a weak one) | **GATED-NULL (outcome) + methods observation** |

| 5 | 4 | **Full-token vs mean+std decider (EEG-FM)** | matched age OOF 0.40 vs 0.48 (both ≈chance) | frozen encoder is the ceiling, not pooling → GPU fine-tuning required | **path capped (CPU exhausted)** |
| 6 | 5 | **VitalDB: induction MAP-recovery-τ → postop AKI, incremental to TWA-MAP** (n=1,255; 149 AKI) | M1 hemodynamics 0.806 → +τ 0.801 (Δ −0.005); τ coef +0.043 CI [−0.156,+0.187] | novelty pre-screen reframed idea (killed pressure-only wave-separation framing, Mynard 2012); powered → **τ adds nothing** | **GATED-NULL** |

### Cycle 5 (CPU pivot) detail → `docs/VITALDB_PIVOT_IDEA2.md`
- User chose "broaden the hunt" (EEG-FM GPU-gated). Picked VitalDB (open, 500 Hz arterial waveform).
- Novelty pre-screen (haiku+PubMed) killed the original "wave-reflection recovery kinetics" framing
  (named-index proximity + pressure-only wave separation discredited, Mynard 2012 + INSPIRE has no
  waveforms) but CONFIRMED the white space beneath (higher-MAP-target RCTs null → field needs a dynamic
  reserve dimension beyond TWA-MAP). Reframed to a pressure-only, non-named marker: MAP recovery-τ after
  induction. Feasibility gate PASSED (2,542 AKI-derivable cases, 12%). Powered read = clean NULL (τ adds 0).
- Reusable: VitalDB AKI cohort + cheap 2 s numeric hemodynamics pipeline. Next = re-rank (Idea 4/3 or a
  MIMIC↔eICU externally-validated tabular question).

### Cycle 3 detail → `docs/CYCLE3_SITE_INVARIANCE.md`
- **Methods observation (Claim A):** a *linear* site-probe collapses to 0.585 after ComBat/CORAL (looks
  invariant) while a *nonlinear* probe recovers hospital at 0.96–0.99 from the same corrected embeddings.
  A site-invariance gate must be **nonlinear**. Novelty INCREMENTAL (safeguard, not discovery); needs
  per-fold CIs + ≥3–5 sites before it is a publishable methods note. Best home: the site-gate methods
  section of the main study, not a headline.
- **Outcome null (Claim B):** no *strong* cross-site cognitive signal survives in the frozen mean+std
  representation (injected-signal calibration: pipeline detects ≥0.3σ effects at n=25; found none). A weak
  signal cannot be excluded at 25 positives. Needs a larger multi-site cohort to resolve.
- **Consequence:** the frozen + CPU path cannot yield a positive cross-site clinical finding now. Real
  levers (evidence-backed): larger labeled n, and encoder fine-tuning (GPU).

## Reading
- The machine's hostile-review gate is doing its job: it **refused to claim a cross-site finding** because
  the frozen embeddings encode hospital (AUC 0.96) → any outcome signal is site-confounded, and the frozen
  per-window MIL shows little usable outcome signal (in-sample ~chance/weak). This is the honest state.
- **The path forward is concrete** (LESSONS cycle-3 fixes): site-correction (`correct_sites.py`) with a
  published post-correction site-AUC ≤ ~0.6 gate; fix class/outcome balance; then re-test. If corrected
  site-invariant frozen embeddings still underperform, that is itself a publishable methods result
  (frozen EEG-FM insufficient for cross-site clinical outcome → fine-tuning required).
- No over-claim anywhere. Every step committed + logged.

## Cycle 9 — critical-care/anesthesia measurement-bias batch (5 ideas) + 4-venue literature mine
| # | Cycle | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|---|
| 7a | 9 | **Occult hypoxemia (SpO₂ vs SaO₂) by race → harm** (MIMIC-IV) | Racial direction replicates (occult OR 1.47, z=+3.5); magnitude/harm blocked — labevents 50817 SaO₂ mixes arterial+venous (p25=70) | Not gated — data-quality block; needs chartevents 220227; occult-vs-overt harm acuity-confounded | **PARTIAL / blocked** |
| 7b | 9 | **Cuff vs arterial MAP discordance → vasopressor under-titration** (MIMIC-IV, 232,656 pairs) | Naive +14.4 mmHg@MAP<55, occult-hypotension 43%, under-titration OR 0.82 | Red-team: **+14→+1.5 mmHg (RTM binning artifact, Bland-Altman); harm reverses to null on sustained; known device behavior** | **KILLED** |
| 7c | 9 | **Personalized MAP floor for chronic HTN** (MIMIC-IV, 33,861 stays) | Sub-65 harm interaction significant in WRONG direction (z=−2.97); "count<T" metric monotone-artifact | Not supported / opposite | **GATED-NULL** |
| 7d | 9 | **Creatinine-masked AKI by sex/muscle mass** (MIMIC-IV, n=320,677) | Isolated-absolute-criterion sensitivity F 90.5% vs M 97.4% (OR 0.47–0.63, robust to baseline def/RTM/draws); male AKI excess 1.295→0.999 artifact | Red-team: effect ROBUST but **not novel** (Nat Rev Nephrol + BMJ Public Health), applies to **isolated-absolute EHR alerts only** (full KDIGO misses no one), whole effect in baseline<0.6 (noise zone, no cystatin C) | **SURVIVES, reframed → methods/quality letter (not flagship)** |
| 7e | 9 | **Blood-gas vs lab glucose discordance in shock** (MIMIC-IV, 47,894 pairs) | Discordance real (SD 16) but widens at HIGH glucose; missed-hypo no mortality signal (OR 0.86 ns); central lab is bigger misser (opposite of hypothesis) | Mostly null | **GATED-NULL** |
| 8 | 9 | **4-venue literature mine (NEJM/JAMA/Nature, PubMed-verified)** → doc 07 | ~50 verified studies; sweeps independently re-derived our corrected-Ca/K⁺-discordance/KDIGO-creatinine/cuff-MAP bets; new leads: Bazett/Fridericia QTc, eGFR→ICU drug-dosing | — | **catalogue built; leads queued** |

## Cycle 10 — ten-idea measurement-bias batch (from the top-tier journal mine) + red-team on 2 winners
| # | Cycle | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|---|
| 9a | 10 | **Chloride indirect-ISE vs blood-gas discordance by race** (MIMIC-IV, 12,056 pairs) | chem Cl −1.31 mmol/L lower in Black at matched true Cl (z=−9.4); hyperchloremia gap inflated 3.6× at >106, sign-flip at >110 | Red-team SURVIVES: A-V confound disclosed but doesn't explain (art-confirmed −1.37); Na-independent (~69%, adj floor −0.8 z=−5.65); mechanism = hypothesis (protein n=134); critical-care-only | **SURVIVES (tempered) — coordinated 4th analyte for flagship panel** |
| 9b | 10 | **Hyperglycemia-corrected sodium → false-hyponatremia labeling by race** (2.5M pairs) | flip rate Black 20.3% vs White 14.1% (z=37.7) | Red-team: robust to clustering/factor, BUT Oaxaca shows 84% = known hyperglycemia disparity, 16% residual (~1pp); framing is translocational not pseudo; consequence untested | **DEMOTED — modest label-quality restatement of a known disparity** |
| 9c | 10 | **Corrected calcium by SEX** (24,674 ionized triplets) | no residual sex offset (+0.023 mg/dL z=0.99); correction collapses true sex gap | — | **NULL — valuable specificity control (bias race-specific not sex-specific → reinforces flagship)** |
| 9d | 10 | QTc Bazett vs Fridericia by sex/HR (798k ECG) | 450ms cutoff: Bazett female excess +2.1pp (z=8.5) reverses to −1.0pp under Fridericia | already-known mechanism | **confirmatory + modest formula-artifact** |
| 9e | 10 | HbA1c–glucose by race (27,897 A1c) | at matched glucose Black cross A1c≥6.5% ~2×; ~½ inpatient diabetes gap artifact | already-known (Bergenstal) | **confirmatory** |
| 9f | 10 | Benign ethnic neutropenia ANC threshold (80k adm) | baseline ANC ↓ in Black (z=−22.8) but over-labeling REVERSES in ICU | acuity confound; BEN is outpatient | **NULL in this cohort** |
| 9g | 10 | Anion-gap albumin correction subgroup (379k) | +42pp masking in low-albumin (known) but NULL by race/sex | hypoalbuminemia race/sex-invariant | **already-known + NULL subgroup** |
| 9h | 10 | Co-oximetry vs CBC Hb → transfusion (26,764) | discordance −0.28 g/dL (known); sex gap is base-rate, vanishes conditioning on Hb (z=−0.76) | base-rate artifact | **NULL/confounded** |
| 9i | 10 | eGFR equation → renal drug-dosing (415k) | race arm arithmetically forced; sex CG-vs-CKDEPI 5.9pp (z=12) | tautological / already-known | **mechanism-only** |
| 9j | 10 | Bilirubin–Jaffe creatinine interference (750k) | −0.017 mg/dL per SD bilirubin (z=−2.3), trivial, inseparable from sarcopenia | already-known | **NULL** |

## Chloride use-case round (post cycle-10) — 2 wins survive red-team (tempered)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| 10a | **Chloride acid-base propagation/cancellation** (8,018 paired) | absolute Cl/Na bias −1.2/−1.1 (z≈−8.5) but AG/SID/Na−Cl bias +0.10 (z=0.65) — self-protected | Red-team SURVIVES: RTM correctly handled; AG>16 "residual" is case-mix not bias; null underpowered (CI −0.21..+0.42); needs external rep | **WIN (tempered) — the "where bias matters vs cancels" map** |
| 10b | **Chloride prognostic misclassification** (4,010 paired) | false-hypochloremia Black 11.7% vs White 4.8% (Fisher p=0.0001); apparent hypochloremia gap vanishes at truth | Red-team SURVIVES at measurement level; harm framing overclaimed (mortality OR 2.77→1.28 adj; no CDS tool) | **WIN (measurement-classification disparity, not harm)** |
| 10c | **Masked hyperchloremia & AKI** (fluid-type infeasible) | masked hyperchloremia Black 14.7% vs White 10.9% (z=3.34); no AKI harm at matched true Cl (adjOR 1.03) | acuity-confounded outcome; clean measurement signal | **partial / mechanism-only** |

## Fluid-responsiveness program (scoping + first results)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| 11a | **MIMIC fluid-response trait-vs-state** (5,612 boluses, 3,740 subj) | corrected response +1.46 mmHg (73% RTM); within-episode ICC 0.126, CROSS-ENCOUNTER ICC −0.046 (≈0); Frank-Starling fails; both NCs pass | rigorous null; novel framing (0 prior cross-encounter work) | **STATE-not-phenotype (de-hyping win); red-team pending** |
| 11b | **VitalDB objective ΔSV-after-bolus label gate** | label VALID (pre-bolus SVV AUROC 0.814) but routine boluses not timestamped → only 15 FMS cases (n≈4 w/ ECG+pleth) | hybrid design adopted (train device-SVV 871, anchor on objective boluses) | **gate done; full model queued** |
| 11c | VitalDB non-invasive SVV model (ECG-increment-over-PVI) | interrupted by session limit | — | **queued/resume** |
| 11d | INSPIRE preop-labs → intraop instability | interrupted (labs downloaded) | — | **queued/resume** |
| 11e | MIMIC objective SV-bolus label probe (PiCCO subset) | interrupted (extracting) | — | **queued/resume** |

## Fluid-responsiveness program — COMPLETE (post-red-team verdicts)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| 11f | **VitalDB ECG→SVV (increment + equivalence)** | M0 0.618 / ECG-alone 0.632 / pleth-PVI 0.733; ECG-alone−pleth −0.100 [−0.138,−0.061]; ECG-alone−M0 +0.014 (≈0) | pre-registered; equivalence REJECTED not underpowered; uncorrelated w/ pleth; no rescue in low-perfusion | **SOLID NULL — ECG not a non-invasive FR signal under GA** |
| 11g | **MIMIC real-SV proxy + trait-state** | ΔMAP AUROC 0.56 for true ΔCO≥10%; within-episode CCO ICC −0.06 | Red-team: CCO no-bolus noise floor SD 14.2%/21.4%≥10% ≈ post-bolus 24.5% (p=0.49) → CCO reliability ~0% | **A (ΔMAP poor proxy) survives PRACTICAL/softened; B (state-not-phenotype) NOT ESTABLISHED** |
| 11h | **MIMIC continuous-CO as FR ground truth** | test-retest reliability ~0% (no-bolus var ≥ post-bolus var) | red-team noise-floor | **cautionary methods result — MIMIC CO too noisy to ground-truth FR** |
| 11i | **INSPIRE preop-labs → intraop instability** | severe AUROC 0.808 / routine 0.734; labs add only +0.017 over structural | associational/confounded | **MODEST/NULL — preop labs add little** |

## Chloride mechanism — cross-national confirmation (SICdb)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| 12 | **SICdb chloride electrolyte-exclusion mechanism** (8,912 paired patients) | discordance∼total-protein slope −0.552 mmol/L/g/dL (z=−18.6), strictly monotone quartiles; 10-min robust (−0.495); Na:Cl slope ratio 0.65 ≈ conc ratio 0.71 | replicates the 4-rounds-survived sodium method; cleaner reference (no sensor flag); self-checked (window/monotonicity/globulin/slope-ratio) | **CONFIRMED — chloride is a validated coordinated 4th analyte (Na↓,Cl↓,Ca↑)** |

## Cycle 11 — second measurement-bias batch (10 novel-angle ideas) + red-team on 2 wins
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| 13a | **False hypercalcemia (corrected-Ca) by race** (103,655 pairs) | corrected>10.5 at ionized<1.30: Black 13.3% vs White 8.0%, OR 1.77 (z=4.66); matched-band 32.9% vs 20.0% | Red-team SURVIVES: robust to threshold; not RTM; not albumin-composition (formula amplifies a genuine +0.22 mg/dL raw-total gap); scope=hypoalbuminemic 84%; classification not harm | **WIN — upper-threshold complement to the calcium flagship** |
| 13b | **Bicarbonate specificity control** (3,129 pairs) | HCO3 racial differential β=−0.16 (z=−1.32 NS); 95% CI excludes Na/Cl effects; no protein-tracking (z=0.28) | well-powered negative control | **WIN — bias specific to indirect-ISE Na/Cl, not generic** |
| 13c | **Osmolar-gap propagation** | propagates ×−2 (algebra exact); Black−White +1.9 mOsm/kg at ±6h | Red-team DEMOTED: z=2.77 is exact −2× rescaling of the sodium regression (0 incremental evidence); flag disparity null under tight timing | **DEMOTED — propagates-vs-cancels PRINCIPLE valid; clinical flag underpowered** |
| 13d | Occult hypoxemia (clean SaO2 220227) | occult Black 5.36% vs White 2.28%, OR 2.45; bias +1pp (not the contaminated +13-17) | replicates Sjoding; decision endpoint non-testable (53% already vented) | **confirmatory + validated clean source** |
| 13e | Paraprotein pseudohyponatremia | protein dose-response −0.96 mEq/L/g/dL (z=−8.3); false-hypo ~2× Black | known mechanism; extreme underpowered | **confirmatory** |
| 13f | Low-AG self-flag | AG doesn't track globulin (z=−0.3); low AG less common in Black | chain broken | **NULL** |
| 13g | Sex-specific troponin | raw female MI gap vanishes adj for troponin+age (OR 0.98 NS); cTnT can't resolve hs window | known/dataset-limited | **NULL** |
| 13h | Ferritin × inflammation | acute-phase inflation z=36.8 (known); race gap NS; no iron gold standard | feasibility-limited | **NULL subgroup** |
| 13i | TSH age/race reference | uniform>4.5 flag 7.6%→16.6% age; White 15.1% vs Black 8.0% | Surks already published age+race | **confirmatory** |
| 13j | ETCO2–PaCO2 gradient | masked hypercapnia 16.4%, lung-dz OR 3.5; no race/sex signal | dead-space physiology, known | **confirmatory** |

## Gate-demonstration batch (IDEA_GATE pre-screened; depth on the electrolyte seam)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| 14a | **Potassium concentration-scaled specificity control** (46,968 pairs) | de-hemolyzed racial displacement +0.009 [−0.003,+0.020] (well-powered null); concentration law Na −1.08 / Cl −1.29 / K +0.009 (~100× smaller as predicted) | quantitative negative control confirmed; cleanly separated from the hemolysis false-hyperK mechanism | **WIN — completes the concentration-scaled displacement law** |
| 14b | Sodium masked-hypernatremia (upper-tail complement) | racial differential replicates (−0.84, z=−7.7) but chem OVER-reads Na → over-flags not masks; artifactual-disparity reframe NULL (DiD +0.12pp — hypernatremia gap is genuine) | threshold-complement premise fails on baseline offset direction | **NULL** |
| 14c | Within-patient Na+Cl fingerprint (slope=0.71) | correlation r≈0.25 (known, PMID 16548813); slope 0.25–0.34 across all estimators incl albumin-IV → 0.71 FALSIFIED; Cl only partially protein-mediated | sharp prediction cleanly falsified | **NULL (clean falsification)** |

## New-seam pilot (from the discriminator's new-triple search)
| # | Experiment | Predicted | Result | Status |
|---|---|---|---|---|
| 15 | **POC glucose-meter hematocrit interference** (137,984 POC↔lab pairs) | high (all-3-ingredients) | Hct dose-response −0.449 mg/dL/%Hct (z=−11.9), monotone +5.7→−10; negative control clean (plasma-cal POC slope 0.00); ~1.8× false-hyperglycemia in anemia. BUT racial framing FAILS specificity (Black=White Hct in ICU 29.8 vs 29.7; race offset +4 unchanged by Hct adj → not a Hct effect) | **PARTIAL: anemia→false-hyperglycemia mechanism-confirmed WIN; racial flagship NOT supported (confounded)** |
| 16 | **Thrombocytosis → pseudohyperkalemia (serum vs plasma K)** (platelet-binned K discordance) | med-high (clean textbook mechanism + abundant driver range + reference) | platelet slope **+0.052 mEq/L per 100k (z=22.9)**, strictly monotone to +0.79 at platelets >1000k; false-hyperK 1.6%→28% across platelet bands; **WBC arm null** (localizes to platelets); racial false-hyperK gap replicates (Black 6.6% vs White 3.3%) but is **NOT platelet-mediated** (unchanged adjusting for platelets) | **WIN — driver with abundant in-cohort range + clean reference; racial angle confounded/separate** |
| 16b | **COHb → pulse-oximeter SpO₂ bias** (co-oximetry SaO₂ vs SpO₂) | high (predicted) → **wrong** | driver has **no dynamic range** in ICU (COHb mean 1.1%, max ~7%; severe CO triaged elsewhere) → no dose-response detectable. Clean sub-result: **COHb is racially invariant** (Black≈White), so it cannot confound the Sjoding occult-hypoxemia racial gap | **NULL (driver lacks in-cohort range) — but rules COHb out as a confounder of occult hypoxemia** |
| 16c | **MetHb → pulse-oximeter SpO₂ bias** (co-oximetry) | med-high | mechanism directionally consistent but MetHb≥5% only **n=28** → extreme-tail power failure; no subgroup test possible | **mechanism-only (underpowered)** |

## eICU external validation of the false-hypercalcemia (upper-threshold) calcium bias + full gate (doc 12)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| 17 | **eICU false-hypercalcemia (upper-threshold) external validation** (14,164 paired total+ionized draws, 93 hospitals; truncated-download subset) | Test1 raw gap +0.195 mg/dL (z=3.54)≈MIMIC; **false-hyperCa OR 2.57** (Black 4.68% vs White 1.87%); RTM-immune band Black 11.4% vs White 3.9% (z=5.69); masked-hypoCa OR 1.66 | 3-agent gate: **reproduction SURVIVES** (from-scratch, strengthens under stricter filters, cells>>30); **hostile panel = promotable-with-caveats**; **CKD-robust**: raw gap +0.195→+0.147 (creat+phos, sig), false-hyperCa 2.57→2.56 in creat<1.3 (SURVIVES), masked-hypoCa 1.66→1.24 (does NOT survive — renal-mediated). Total-protein mediates (mechanism, not confound); myeloma-excluded unchanged; pH negligible. Heterogeneity site-concentrated (pooled +2.67pp z=5.46 vs inverse-var meta +0.57pp) | **SURVIVES — upper-threshold error externally validated + CKD-robust + reproduction-confirmed; the durable NEJM-genre endpoint** |
| 17-gap | **eICU treatment consequence (IV calcium repletion)** | UNMEASURABLE: infusionDrug charts Ca infusion in only 316/73,547 stays; repletion is bolus/push in the absent `medication` table | data-coverage null, NOT equal-treatment evidence | **blocked in eICU → pursue in MIMIC (inputevents/repletions.csv exist)** |
| 18 | **MIMIC false-hypercalcemia → differential UNNECESSARY workup (measurement-mediated)** (25,170 pairs, 3,442 Black) | **Measurement-mediated link POWERED+robust:** biased Ca drives PTH/VitD/SPEP workup holding true ionized fixed — corrected_Ca OR 1.17 (z=3.37), total_Ca OR 1.42 (z=8.7), survives malignancy exclusion (OR 1.21, z=3.53). **Exposure disparity POWERED:** false-flag Black 4.7% vs White 2.5% (z=4.43, ~1.9×). Within-flag workup rate NOT race-differential (signal is exposure not response). Population differential-unnecessary-workup: "any workup" +1.28pp (z=3.08) but proxy-weak (repeat-ionized contaminated); **specific endpoint +0.04pp (z=0.26) UNDERPOWERED (4 Black false-flag+workup events, +72h window)** | Self-red-teamed: caught+fixed a labevents schema bug (extra order_provider_id col → false zeros); malignancy-robust; temporality enforced; honest underpowered null on the specific endpoint | **PARTIAL WIN — causal chain established (bias→workup independent of truth; Black 2× exposed); population differential promising-but-underpowered in MIMIC, needs larger corpus** |
| 18b | **Workup-differential power-check (3 windows: +72h/+7d/whole-admission)** | Black false-flag+specific-workup events 4→7→8 (all <25 needed); exposure disparity unchanged (4.7% vs 2.5%, z=4.4) at every window; within-flag workup rate favors White (Black 6.3%/10.9%/12.5% vs White 10.1%/14.1%/16.6%); widening only adds confounding | ceiling confirmed — not powerable in MIMIC | **CONFIRMED CEILING — population workup differential needs multi-site order data; the two upstream links stand** |
| 18c | **NEJM manuscript assembled** → `docs/research/MANUSCRIPT_DRAFT.md` | full eGFR-analogue framing; mechanism + eICU external validation + workup causal-link + exposure disparity; hard-outcome chain kept hypothesis-generating | flagged 4 pre-submission number-reconciliation items (cohort-size/denominator differences across extractions) | **DRAFT COMPLETE — pending number harmonization + a multi-site workup corpus** |

## Cycle-12 NEJM/Nature-tier CC/anesthesia slate (discriminator-ranked; predictions in IDEA_GATE)
| # | Experiment | Predicted | Result | Status |
|---|---|---|---|---|
| C12-2 | Pre-analytic false hyperlactatemia (bg vs central lactate) → sepsis mis-triage | MED-HIGH | chem lactate 53154 = 104 rows/93 pts; 1 paired patient at ±60min — two-method design has no substrate | **NULL (infeasible; reference not co-ordered at scale)** |
| C12-3 | False-hyperK → emergency insulin/D50 → iatrogenic hypoglycemia (doc-02 consequence) | MED-HIGH | **LINK1 STRONG:** chem-K drives hyperK treatment holding true bg-K fixed, OR 2.34/mEq/L (p=1.7e-61), bg-K NS. **Exposure disparity replicates:** false-hyperK Black 13.8% vs White 6.4%, RR 2.15 (matches doc-05 OR 2.36). LINK2 unnecessary-treatment tiny absolute (0.38%). **LINK3 terminal harm EMPTY (0/4 false-flag-treated hypoglycemic).** Selection: paired-gas=ICU where true K visible protects against acting on artifact | **PARTIAL — action-level measurement-mediated link + disparity are clean, publishable (hardens doc 02); terminal iatrogenic-harm doesn't close (paired-design selection wall, same as calcium workup)** |
| C12-1 | **Occult hypoxemia → SpO₂/FiO₂ → ARDS-Berlin & SOFA-resp racial misclassification** (MIMIC, 104,696 paired ABG↔SpO₂↔FiO₂, 10,841 Black) | HIGH | SF over-reads at matched true PF: **Black +6.87 SF units (z=7.44)**; ARDS under-classification PF<200→SF≥235 **OR 1.43 (z=8.16)**, PF<300→SF≥315 **OR 2.00 (z=9.55)**; SOFA-resp under-score ≥1pt **OR 1.66 (z=14.0)**; attributable missed-ARDS **+1.2pp** (CI +0.9..+1.5). Robustness: FiO₂-charting ruled out (0.558 vs 0.556), SpO₂-nonlinearity ruled out (88–96 unchanged), PEEP≥5 holds, Sjoding occult-hypoxemia positive control replicates (OR 2.09). Honest nuance: mean PF−SF net-negative both races (SF globally conservative); racial harm is in the under-scoring TAIL | **WIN — in hostile-review gate (novelty/prior-art vs Fawzy/Gottlieb/Sjoding; cluster-robust re-inference for Tests 2–4; eICU external-validation feasibility)** |
## Extubation → reintubation-risk tool (decision-tool candidate #3)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| EX-1 | **Novelty + MIMIC feasibility (STATIC features)** (N=29,580 extubations; reintubation 6.8%/48h, 10.1% in ≥24h-MV subset) | Outcome CLEAN + abundant (opposite of AF). Static predictor signal modest: RSBI 0.573 → 6-var 0.635 → full 0.645 (~0.64 ceiling, but MISSING several Tier-1 features + the entire dynamic layer). Me-too static score is crowded: RSC/RISC (Bansal 2022 PMID 35252224, C 0.72), Fenske 2025 ML ext-validated 0.87 (PMID 40731125) | me-too STATIC score NO-GO | **STATIC score killed; SBT-DYNAMICS layer untested → EX-2** |
| EX-2 | **SBT vital-sign DYNAMICS incremental-value test** (the one novel angle) | running — does multi-vital SBT-trajectory (RR/HR/SpO₂/BP variability+trends during the SBT) add AUROC beyond static? Lit: WAVE RR-variability alone 0.69 > static RSBI 0.61 (Seely PMID 24713049), but confined to one proprietary engine; broad multi-vital SBT-dynamics = genuine open gap; field's 14 models all high-bias, only 2 ext-validated (2025 review PMID 41357524) | — | **in progress — GO only if dynamics add real incremental value + MIMIC→eICU external validation** |

**META-CALIBRATION after 3 decision-tool cycles (nuanced):** observational bedside-decision-tools have a LOW hit rate — steroids (confounding → trial-ready ceiling), AF (outcome not observable in-cohort), extubation-static (crowded). The measurement-bias-PROPAGATION template won twice (calcium, occult-hypoxemia→SOFA/ARDS) → **comparative advantage = propagation-maps.** A decision-tool is worth running only if it clears ALL FOUR: (a) clean in-cohort observable+timestamped outcome; (b) genuinely unfilled; (c) low confounding (diagnostic/risk not treatment-benefit); (d) predictable outcome. The ONE live exception: extubation's SBT-DYNAMICS layer is a specific unfilled physiology gap (b) with a clean outcome (a) — being tested (EX-2). Otherwise prefer propagation-maps.

## New-onset AF in sepsis — anticoagulation-decision tool (decision-tool candidate #2)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| AF-nov | **Novelty pre-screen** | NARROW-BUT-NOVEL white space (Sibley/Walkey 2025 review PMID 40323451: "no validated risk-stratification tools"; 2025 meta-analysis equipoise + 3–86% practice variation; 2026 BET calls for an RCT). **BUT** Myers/Walkey 2024 (PMID 38594918) built this exact tool and FAILED external validation (model AUC 0.54; CHA₂DS₂-VASc AUC **0.50 = chance**); Walkey 2023 target-trial (PMID 36852680) found OAC → HIGHER stroke/TIA; much stroke risk is post-discharge (MIMIC-blind) | white space real but a prior attempt failed + outcome may be in-hospital-unpredictable | — |
| AF-feas | **MIMIC feasibility + cohort** (32,168 septic; 9,214 new-onset AF; 702 in-hospital stroke, 789 bleed) | CHA₂DS₂-VASc AUROC **0.559** (poor, confirms white space). BUT binding constraint = OUTCOME VALIDITY: no ICD timestamps/POA → 54% of "in-hospital strokes" are present-on-admission (untethered to AF onset); credible incident strokes ≤324; decision-relevant thromboembolic risk is POST-DISCHARGE (MIMIC-blind); competing mortality 20.5% | **NULL on in-hospital feasibility** — needs a linked-longitudinal-outcomes dataset; MIMIC/eICU/SICdb can only phenotype the acute state | **KILLED in our data (outcome not observable/time-orderable) — validates the new checklist item; white space stays open for a linked-outcomes study** |

**CALIBRATION (decision-tool ranking):** I scored AF HIGH on tool-value but under-weighted two screens now added to the checklist — **(a) did a prior attempt already fail external validation? (b) is the outcome even predictable from in-hospital data, or does the risk live post-discharge/out-of-cohort?** CHA₂DS₂-VASc=0.50 + Myers-2024-failed are strong priors that a risk tool won't discriminate here. Predict TOOL-FEASIBILITY, not just white-space.

## Steroids-in-septic-shock bedside score (user idea; design in doc 14)
| # | Experiment | Result | Gate verdict | Status |
|---|---|---|---|---|
| S-v1 | **Naive subphenotype discovery + baseline-IPTW steroid HTE** (MIMIC, N=14,381 septic shock, 1,147 hydrocortisone) | k=2 = pure SEVERITY gradient (severity-artifact trap, as pre-mortem predicted); k=4 shows difference in KIND — **C2 hyperlactatemic vasopressor-refractory** (lactate 9.6, bicarb 14, NEE 1.23, Seymour-δ-like). Baseline-IPTW steroid assoc HARMFUL in every phenotype (RD +0.10..+0.22) = confounding-by-indication signature; attenuates to near-null (RD +0.04) ONLY in C2 | design pre-mortem's confounding warning CONFIRMED; baseline IPTW can't remove time-varying confounding | **Confounding-dominated as-is; C2 (hyperlactatemic-refractory) is the one defensible signal → rigorous g-methods follow-up (v2)** |
| S-v2 | **Target-trial emulation (g-methods, time-varying) on shock-reversal + phenotype×steroid HTE** | **Time-varying g moved naive→null (mort HR 2.50→2.16; reversal 0.63→0.79) = confounding was time-varying, as predicted. INTERACTION (consistent across 3 phenotype defs): HLVR phenotype gets FASTER shock reversal (steroid HR 1.21–1.32 vs 0.82 non-HLVR; interaction HR 1.43–1.78, CI excl 1) + NEUTRAL mortality (HR 1.05 vs 2.04; interaction HR 0.47–0.56). Survives SOFA-orthogonality; E-values 2.2–3.6.** Negative-control PARTIALLY FIRES (AxP OR ~0.51) → residual phenotype-differential confounding not fully excluded | mechanism-aligned effect modification on the less-confounded endpoint; hypothesis-generating not causal (neg-control caveat) | **PERSIST — strongest defensible steroids result; trial-ready HLVR-steroid-responsive signal → external-validate (eICU/SICdb) + parsimonious score + RCT-IPD** |

| C12-1a | **Cluster-robust re-inference + eICU feasibility** | **Task A: all effects SURVIVE subject-clustering** — SEs inflate ~1.8× (ORs unchanged): 2a OR 1.43 (cluster 95% CI 1.21–1.69, z=4.24), 2b/4 OR 2.00 (1.56–2.55, z=5.51), 3 OR 1.66 (1.46–1.88, z=7.81); one-pair-per-subject gives even larger ORs (1.46/2.78/1.98). **Task B: eICU infeasible LOCALLY** — no pulse-ox SpO₂ in the local extract (lives in un-downloaded `vitalPeriodic`); agent refused to substitute arterial co-oximetry; race + arterial gases present & powered (~34k) → download gap, not a null | inference hardened; external validation pending `vitalPeriodic` acquisition | **HARDENED — internally airtight; eICU external validation needs vitalPeriodic download** |
