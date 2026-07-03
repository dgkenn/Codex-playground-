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
