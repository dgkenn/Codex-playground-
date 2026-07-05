# EXPERIMENT QUEUE — prioritized backlog (re-rank every cycle; pull the top item that fits compute)

## ACTIVE — Steroids-in-septic-shock responsive subphenotype (user idea; running)
Design (defended against the naive outcome-clustering trap): **MIMIC discover → eICU + SICdb validate.**
Cluster on BASELINE physiology at shock onset (pre-steroid, outcome/treatment excluded) → k subphenotypes;
then test hydrocortisone(±fludrocortisone) heterogeneity of effect on shock-reversal + mortality with
IPTW/propensity + landmark anchoring. Honest ceiling: hypothesis-generating HTE (confounding by indication);
confirmatory path = re-analyze ADRENAL/APROCCHSS. Running: MIMIC cohort+discovery agent + design pre-mortem.
- **MIMIC feasibility CONFIRMED:** hydrocortisone n≈32k / fludrocortisone n≈4.9k (prescriptions); vasopressors
  in inputevents; sepsis-3 shock definable; mortality + shock-reversal outcomes present.
- **SICdb external-validation IDs CONFIRMED (d_references):** Hydrocortison=1525, Fludrocortison=1751,
  Norepinephrin drug=1562 / dose-per-hour=772,773, Vasopressin=1550, Lactat(BG)=454/657,465; other steroids to
  flag PredniSOLON=1397 MethylPREDNIsolon=1506 DEXAmethason=1524; outcomes in cases.csv.gz
  (OffsetOfDeath, DischargeState, EstimatedSurvivalObservationTime, Sex, AgeOnAdmission, HeartSurgeryBeginOffset
  to exclude cardiac surgery). Have medication.csv.gz + cases.csv.gz locally; extract baseline subphenotype
  FEATURES only AFTER MIMIC discovery names them (and only if discovery shows a real signal).
- **eICU external validation:** diagnosis + infusionDrug + apacheApsVar present locally.
- **PRE-MORTEM VERDICT (do NOT run the naive version):** Rajendran et al. Nat Commun 2025 (PMID 40360520)
  ALREADY did MIMIC+eICU ML-subphenotyping + target-trial-emulation of corticosteroids on MORTALITY and got
  direction-INCONSISTENT cross-cohort effects (HR 1.05 vs 1.40; 1.24 vs 1.34 — non-replication). Li et al.
  2023 (PMID 38039761): PSM on hydrocortisone in MIMIC-IV still yields an RCT-discordant harmful estimate →
  confounding-by-indication is NOT fixable by propensity here. So the naive cluster-then-test-on-mortality is
  already-done + confounding-limited. **We only proceed with a DIFFERENTIATED wedge.** Candidate wedges (being
  novelty-checked): (1) an EHR PROXY for the transcriptomic SRS2 endotype (VANISH: SRS2 HARMED by
  hydrocortisone) — a deployable "don't-give-steroids" classifier, no EHR-proxy exists; (2) SHOCK-REVERSAL /
  vasopressor-free-days outcome (reliable steroid physiology, less confounded) instead of mortality; (3)
  catecholamine-resistance / vasopressor-dose-trajectory phenotype (the real bedside trigger). Also required if
  we run: full clone-censor-weight (not just landmark), pre-registered power thresholds, severity-vs-endotype
  falsification tests (non-monotonicity/orthogonality-to-SOFA/severity-blind-recluster), E-values. Let the
  running MIMIC discovery finish only for the reusable cohort + subphenotype STRUCTURE; do not build on its
  naive mortality-HTE.
- **DELIVERABLE PIVOT (user, stronger): a bedside steroid-decision SCORE/mnemonic** (SOFA/qSOFA/CURB-65 form
  factor) — "should I give steroids to this septic-shock patient?" This is the translation layer on the
  mechanism-anchored phenotype and differentiates from Rajendran (interpretable point-score, not black-box ML).
  Working concept: 4–5 routine bedside items encoding TWO mechanism axes — **catecholamine-refractoriness**
  (norepi-equivalent dose / ≥2 vasopressors — the real steroid trigger + where relative adrenal insufficiency
  is likeliest) and **hyperinflammation** (NLR / temperature — SRS/Calfee axis) — hypothesis: high-vasopressor
  + high-inflammation phenotype gets the biggest **shock-reversal** benefit (reliable steroid physiology; less
  confounded than mortality). Honest ceiling: it is a TREATMENT-EFFECT-MODIFIER score (rests on real HTE) →
  observational build = trial-ready tool; **gold-standard validation = apply to ADRENAL/APROCCHSS/VANISH IPD.**
  Methodology to use: parsimonious effect-modifier classifier (Sinha ARDS), Kent PATH-statement risk-based HTE,
  decision-curve analysis. Cross-cohort reproducibility (MIMIC→eICU→SICdb) is the internal-validation bar.

Priority = (impact × novelty × feasibility) / cost. **CPU-only right now; overnight runs are fine.** Every
item must clear the hostile-review gate (RESEARCH_MACHINE.md) before it counts. Move done items to
FINDINGS_LEDGER.md with their verdict + the attack map.

## DONE (cycle 3) — see docs/CYCLE3_SITE_INVARIANCE.md + FINDINGS_LEDGER #4
- Fitted ComBat/CORAL site-correction, re-ran the probe with a LINEAR **and** NONLINEAR head, re-tested the
  outcome, and power-calibrated the null. Result: linear harmonization gives FALSE site-invariance
  assurance (linear probe 0.585 but nonlinear 0.96–0.99); no *strong* frozen cross-site outcome signal
  (calibration: detects ≥0.3σ at n=25, found none). GATED-NULL on outcome + an INCREMENTAL methods
  observation. **The published site gate is now the NONLINEAR probe, not ≤0.6 logistic.**

## NEXT (cycle 4) — re-ranked from Cycle-3 evidence
0a. **[DONE] Positive-control outcome (age/sex).** Sex 0.50, age 0.55 (all) / 0.61 (S0001). Harness works
    (injected-signal 0.6σ→0.84) but the frozen **mean+std** representation barely encodes even age → the
    REPRESENTATION is the bottleneck. This promotes 0a-prime to the single most important experiment:
0a-prime. **[DONE — VERDICT: frozen ENCODER is the ceiling, not pooling].** Ran the clean MATCHED decider
    (same patients, same windows NWIN=24, same folds; one embed pass emits BOTH mean+std 24×400 and
    channel-resolved full-token 456×200). Age>median OOF AUC at n=98: **mean+std 0.401 [0.391,0.414] vs
    full-token 0.476 [0.417,0.519]** — both ≈chance, full-token gives no meaningful rescue. The frozen
    CBraMod representation does NOT reliably encode even age (a signal EEG carries strongly) under any pooling
    tested. (The earlier mean+std 0.61 at n=239 was a weaker/subset-dependent read; on a clean random subset
    it's ~chance → the frozen age signal is fragile.) **CONCLUSION: richer CPU pooling is NOT the lever;
    encoder fine-tuning (GPU) is.** The CPU/frozen path is exhausted for a positive clinical finding.
0b. **[if we pursue the methods note] Harden Claim A to a publishable safeguard:** refit ComBat/CORAL
    PER-FOLD (kill the global-fit leakage objection), add bootstrap CIs on all four site-AUCs, add a
    permutation null for the site probes, and — the big one — **add ≥1–2 more HEEDB sites** so the
    linear-passes/nonlinear-fails gap is shown across multiple site pairs (2 sites confound site with every
    between-site variable). Then it can be the site-gate methods section of the main study.
0c. **[real lever for a POSITIVE finding] Larger labeled multi-site cohort for the cognitive/mortality
    outcome.** The n=25-positive null only excludes a *strong* frozen signal; a weak one needs hundreds of
    positives to resolve. Cache outcome-balanced across all 4 sites (mortality/DateOfDeath has far more
    events than cognitive-ICD → better-powered secondary endpoint). Only after this is a frozen-path
    outcome claim (positive or a real null) defensible.
0d. **[deferred, GPU] Encoder fine-tuning** — now evidence-backed as the main lever: the frozen
    representation is site-dominated (nonlinearly) and outcome-poor. This is the path to a positive finding
    if 0c's larger-n frozen test still underperforms.

## META-LESSON (after 2 nulls: EEG-FM capped, VitalDB-τ null) — RE-RANK PRINCIPLE
Novel-single-marker hunts on ONE dataset keep producing nulls, AND the mission bar demands EXTERNAL
validation. So the next picks are re-prioritized by two filters the last two cycles lacked:
1. **External validation by construction** — discovery + replication datasets BOTH already in hand
   (MIMIC-IV ↔ eICU, both cached/open), so a positive can be externally validated immediately, and a
   transport-failure is itself publishable (cf. delirium 0.90→0.58).
2. **A decision/mechanism, not a marginal marker** — avoid the "another way to detect sick patients"
   incremental trap that capped vasopressor + τ. Prefer questions where the answer changes an action or
   reveals a mechanism, with a pre-registered adjustment for the confounder that would otherwise sink it.
Waveform-marker ideas (VitalDB Ideas 3/4) are DEMOTED: they share the fragile single-open-dataset EV path.

## NEXT (cycle 6) — pull the screened MIMIC↔eICU candidate
Run a novelty+feasibility triage (delegated) over 2–3 externally-validatable candidates; pull the top one.
Discipline: novelty pre-screen (PubMed) + tabular baseline (the bar to beat) + pre-registered confounder
handling BEFORE modeling; power any null (Cycle-3/5 lesson) before believing it.

## FLAGSHIP — runnable now on CPU (overnight), dodges the GPU block
1. **[BUILD, overnight] Frozen CBraMod per-window embedding cache at scale.** Stream HEEDB EEGs (µV
   scaling!), embed 30 s windows across the recording, cache **per-window** embeddings (NOT mean-pooled)
   + labels + site for ~3–4k patients/site across the 4 sites. Checkpoint every 50 patients. This is the
   substrate for #2–#4.
2. **[FLAGSHIP — redesigned after Cycle-1 pre-mortem] Attention/MIL head over frozen per-window embeddings
   → COGNITIVE/ENCEPHALOPATHY ICD-10 (primary), MORTALITY (secondary), cross-SITE validated.**
   NOT abnormal-EEG (solved benchmark + circular report label — demoted to a calibration check). Primary
   outcome = Behavioral/Cognitive-Syndrome ICD-10 (HEEDB_ICD10_for_Neurology.csv); secondary = DateOfDeath.
   Attention/MIL head over per-window embeddings (attends over windows, dodges mean-pool ceiling).
   MANDATORY before trusting any result: (a) site-invariance gate — site_probe.py on tokens +
   correct_sites.py Route-A fit on train site only, require post-correction site-AUC ≤ chance; (b) train
   S0001 / tune I0002 / confirm on a THIRD untouched site; (c) re-run the mean-pool-ceiling diagnostic at
   the MIL/token level. Honest sub-SOTA (frozen≠fine-tuned) framing. Full hostile-review gate on the result.
3. **EEG (frozen-embedding + MIL head) → in-hospital mortality (DateOfDeath), landmark + cross-site.**
   Prognostic EEG biomarker on a hard endpoint; genuine white space; CPU-feasible on the cached embeddings.
4. **EEG → cognitive/encephalopathy (delirium proxy), cross-site.** Beats the DELPHI-EEG single-center bar.
5. **Multimodal: frozen-EEG-embedding + EHR/OMOP → outcome.** Does EEG add incremental ΔAUC over clinical
   features? (The question the reachable-data delirium work couldn't answer.) Tabular part is CPU-trivial.

## CPU pre-work (do before / alongside the flagship)
6. **Prior-art / novelty sweeps** (haiku + PubMed) for #2–#5 — confirm each is still white space, not a
   named index, before spending overnight compute.
7. **HEEDB cohort + label engineering** (OMOP outcomes, mortality linkage, per-site splits, label QC,
   EEG↔outcome join). Aggregate metrics only; PHI stays in scratchpad.
8. **Tabular baselines** (age/sex/EHR → each outcome) = the bar the EEG model must beat to matter.

## Deferred — GPU-only (revisit when a GPU env exists)
9. **Encoder fine-tuning** of CBraMod end-to-end (the last lever to reach ~0.90). GPU-only; the frozen
   MIL-head path (#2) is the CPU stand-in that should still beat frozen mean-pool.
10. **Self-supervised phenotype discovery** (repo Phase-1/2) at full scale.

## Rules
- Before any overnight run: novelty pre-screen (#6) + tabular baseline (#8) so the run has a clear target.
- Log every result (positive or null) + its full attack map to LESSONS.md with the mechanism.
- Re-rank after each cycle based on what was learned.

## NEXT (cycle 10) — from the 4-venue literature mine (docs/research/07); PubMed novelty pre-screen FIRST
Ranked by cross-venue support × template-fit × feasibility. Each REQUIRES a 2-min PubMed novelty
pre-screen before running (cycle-9 lesson: the creatinine mechanism was already published).
1. **[TOP] Bazett vs Fridericia QTc over-correction → false "prolonged QT" flags by sex/HR.** Support 3/4;
   data in hand (800k machine QT/RR in ecg_features_full.csv) + meds for QT-drug exposure. "Trusted formula
   fails by subgroup" — cleanest new fit. Novelty risk: moderate (QTc-formula lit is large) — pre-screen hard.
2. **eGFR equation (race-based vs race-free; Cockcroft-Gault vs CKD-EPI) → differential ICU renal drug-dosing.**
   Support 2/4; MIMIC-IV+eICU have race+creatinine+meds. Unclaimed *dosing-action* endpoint on the well-cited
   race-free-eGFR line (vancomycin/DOAC/contrast threshold crossings).
3. **Complete the two-method discordance panel: lactate (Sepsis-3 >2) + hemoglobin (transfusion <7).**
   Support 4/4; extends the sodium/K⁺ work we've already built; MIMIC pairs both methods.
4. **Occult hypoxemia → downstream DECISION endpoint** (SOFA-resp, SF-ratio/ARDS, O₂ target, trial eligibility).
   ONLY after re-extracting clean arterial SaO₂ (chartevents itemid 220227). Frame on the care-decision endpoint —
   the raw discordance is saturated (Sjoding/Fawzy/Wong). Nature-family venue white-space if done cleanly.
5. **[low-cost confirmatory only] Sex-specific hs-troponin threshold → MI under-detection in women.** Support 3/4
   but JAMA (Rubini Giménez) suggests likely NULL — run as a cheap arm, not a bet.

## FOLLOW-UPS on cycle-9 (open)
- **eICU external replication of the creatinine-AKI sex artifact** — eICU lab.csv.gz (516MB) streaming via the
  flaky proxy; patient.csv (gender/age) already landed (200,860). Finish the download, confirm the 1.295→0.999
  artifact + female-sensitivity OR generalize. (Mechanism is arithmetic → expected to replicate; value is the
  artifactual-disparity magnitude across a 208-hospital cohort.)
- **Corrected-calcium by-subgroup extension** (albumin-corrected vs ionized differential misclassification by
  sex/albumin stratum) — flagged 4/4 in the mine; extends doc-01 flagship; SICdb sex/protein replication.

## CYCLE-10 OUTCOME + follow-ups (2 winners red-teamed; chloride survives)
- **DONE cycle 10:** 10-idea batch → 1 WIN (chloride 4th analyte, tempered), 1 demoted (Na-glucose), 8
  nulls/confirmatory. See docs/research/08 + FINDINGS_LEDGER #9a–9j.
- **[chloride follow-up] Confirm the electrolyte-exclusion MECHANISM for chloride** — the racial discordance
  is solid but protein-mediation is n=134 (unpowered). Need a cohort where TOTAL PROTEIN is co-drawn with a
  blood-gas chloride: (a) mine SICdb (has protein + dual-method, no race → mechanism/sex axis), (b) or widen
  the MIMIC window / add albumin as a proxy. Until then chloride's mechanism stays a hypothesis.
- **[flagship integration] Add chloride as the 4th analyte to the coordinated-panel doc (01/03)** once the
  mechanism cohort lands — panel becomes Na↓, Cl↓, Ca↑ (all indirect-ISE electrolyte-exclusion) + K↑ (distinct
  pre-analytic).
- **[demoted, low priority] Na-glucose label quality:** only worth revisiting if linked to a differential
  TREATMENT endpoint (hypertonic saline / fluid restriction orders) — otherwise it's a known-disparity restatement.
- **Still-open from cycle 9:** eICU creatinine external validation is PROXY-BLOCKED (516MB lab.csv.gz won't
  stream through the flaky proxy; patient.csv landed). SICdb (sex, smaller lab file) is the viable alternative
  for both the creatinine-AKI and the chloride-mechanism external checks.

## GATE-SCREENED BATCH (produced by the IDEA_GATE pre-screen — see docs/IDEA_GATE.md)
Pre-filtered for win probability (both hard gates + >=5/7). Run in order; power-check before believing any null.

### Depth moves on the confirmed electrolyte-exclusion seam (data in hand)
1. **[7/7] Sodium masked-HYPERnatremia** — the untested upper-tail threshold complement. BG Na>145 (true) reads
   "normal" on chem Na → under-recognized hypernatremia (the dangerous direction). Ref: lab_nabg vs lab_na.
   Prediction: masking shift ~= the −1.18 mEq/L displacement (no new parameter). Risk: power in the hypernatremia tail.
2. **[5-6/7] "It's globulin, not race": multi-group protein-gradient dose-response** of the Na/Cl bias — pool all
   race groups onto one continuous measured-globulin→bias line (race-blind, actionable fix). Risk: protein-paired
   subsample small (MNAR); frame as mediated-fraction, not race→0.
3. **[5-6/7] Within-patient coordinated Na+Cl fingerprint** — within-patient Na-bias & Cl-bias correlated, slope =
   ion concentration ratio (~0.71). Hard to fake (gate-6 gold). Ref: simultaneous BG Na+Cl vs chem.
4. **[5-6/7] Total-T4 / TBG protein-binding** — free T4 as truth for total T4; total-T4-excess ~ protein (opposite
   sign to Na/Cl, same as Ca) → a mechanistically-independent 6th panel analyte. Risk: power (lead with dose-response).
5. **[5/7] Potassium concentration-scaled specificity control** — BG K (244k, best-powered pair); predicted racial
   displacement ~= −0.03 (near-zero). A quantitative negative control completing the concentration law. Risk: hemolysis
   (screen/adjust).
6. **[5/7] Osmolar-gap protein floor via MEASURED osmolality** (distinct from the demoted 13c) — anchor to measured
   osm (protein-independent) in a no-toxic-exposure subgroup. MANDATORY red-team: compute the parent Na regression
   alongside; kill if z matches (the 13c rescaling trap).
7. **[5/7] Occult hypoxemia → S:F ratio / SOFA-resp under-scoring by race** — SpO2 bias → falsely reassuring S:F →
   under-scored organ dysfunction. Run PubMed novelty screen FIRST (S/F-by-race is active); corollary risk.

### NEW SEAM (from the new-triple search — a distinct mechanism, its own potential flagship)
8. **POC handheld glucose-meter HEMATOCRIT interference by anemia (race/sex/CKD).** Whole-blood fingerstick meters
   over-read glucose at low Hct (RBC-volume displacement) → differential false-hyperglycemia + insulin-dose error in
   anemic (Black/female/CKD) patients. Ref: lab plasma glucose 50931 (truth) vs fingerstick meter chartevents 225664;
   Hct 51221 as modifier (all confirmed present; 225664 needs extraction). Distinct physical mechanism; Lyon-2020 did
   it by simulation, the real paired-EHR racial differential is unmined. Falsifiable: negative Hct dose-response slope;
   specificity control = a Hct-insensitive POC analyte shows no effect. Pre-registered risk: modern Hct-corrected
   meters (StatStrip) may attenuate to null (MIMIC 2008-2019, device-dependent).

Kill list (gate-failed, do not re-propose): Mg/phosphate total-vs-ionized (no reference), chem lactate (empty),
cystatin-C/fructosamine/transcutaneous/biotin/BCG-BCP (not in MIMIC), eICU sodium replication (no BG Na), and all
cycle 10-11 done/known items.

## PhysioNet catalogue scan (verified from data dictionaries) — MC-MED is the key target
- **MC-MED (Stanford ED, physionet mc-med/1.0.1, netrc-downloadable, released 3/2025, ~UNMINED):** 70,545 pts /
  118,385 ED visits; HAS Race + Hispanic ethnicity, DIVERSE (Asian 16% / Hispanic 27% / Black 6.5% / Other 34%);
  institutionally INDEPENDENT of BIDMC/eICU. **The only PhysioNet-downloadable, racially-diverse, unmined cohort
  that can give the calcium flagship an INDEPENDENT racial validation** (ICU→ED, Boston→Stanford). Gate: verify
  ionized calcium is in labs.csv on download.
- Structural finding: NO non-US racially-diverse cohort exists on PhysioNet (EU = no ethnicity by design;
  East-Asian = homogeneous). Amsterdam/HiRID/SICdb/PIC = mechanism-only (like INSPIRE). MIMIC-IV-Waveform = only
  200 records (unusable). MIMIC-III = BIDMC (not independent). AmsterdamUMCdb/MOVER need separate non-netrc DUAs.
- Action: pull MC-MED → verify Ca-ionized/Ca-total/albumin/race → run the racial false-hyperCa/masked-hypoCa +
  mechanism validation. Full scan: scratchpad/physionet_catalogue_scan.md.

## NEXT (loop cycle — post-MC-MED) — new-triple search, MIMIC/eICU protein-binding seam depth stalling
Context: calcium flagship is complete & externally validated (5 cohorts); MC-MED racial endpoint bounded
(ICU-hypoalbuminemia-specific, does not replicate in normal-albumin ED). Tangential protein-binding analytes
now hit diminishing novelty (K-T4 killed at gate). Generated fresh triples (docs/IDEA_GATE.md):
1. **[TOP, pull if novelty-screen survives] NEW-A: Albumin-corrected anion gap masks lactic acidosis in
   hypoalbuminemia.** Reference = measured lactate (clean/free); driver = hypoalbuminemia; decision endpoint =
   missed/delayed acidosis recognition. Novelty pre-screen RUNNING (sonnet). If NOVEL/NARROW-BUT-NOVEL → run the
   masking analysis: at matched lactate ≥4, P(AG>12) vs albumin (monotone predicted); corrected-AG recovery;
   delayed-recognition endpoint; normal-albumin specificity control. Data in MIMIC labevents (local copy is
   truncated — fine for signal; re-stream full file if it becomes the paper).
2. NEW-B (temp-uncorrected ABG) — only if NEW-A dies AND paired corrected/uncorrected gas co-occurrence passes.
3. NEW-C (Sheiner-Tozer phenytoin) — low priority, likely gate-kill (titrated endpoint + textbook).
If all three strike out → hunt new (mechanism + reference + driver) triples in less-mined data (PIC/SICdb/INSPIRE
substrates already downloaded); or develop the PIC pediatric age-dependent calcium-correction WIN (ledger 12d)
into a standalone companion note.

## NEXT (loop) — NEW-A landed as bounded WIN (doc 15); Phase-2 decision endpoint is make-or-break
Phase 1 done: severity-stratified anion-gap masking gradient REAL (missed-acidosis RR 8.95 [5.29–15.12]), but the
naive corrected-AG fix reproduces Dinh 2006 (specificity 45%→8%). The finding is NARROW-BUT-NOVEL; it becomes
publishable only if the DECISION endpoint holds:
- **Phase 2: does a masked-normal AG delay lactate measurement / resuscitation?** Population = chem panel
  (AG+albumin) with NO concurrent lactate; exposure = hypoalb-masked normal AG (uncorr≤12 & corr>12) vs
  truly-normal (both ≤12) vs flagged (uncorr>12); outcome = time-to-first-lactate, later-revealed acidosis,
  mortality. **Blockers to clear FIRST:** (a) full labevents re-download (local copy truncated → "no lactate"
  can be an artifact); (b) acuity-confounding (why lactate wasn't drawn ~ how sick they looked) → adjust +
  falsification (masked vs truly-normal AG should diverge only if the AG drove behavior). If Phase 2 confounds
  fatally (likely, per the paired-design/indication trap) → log as bounded win + methods caution, do NOT overclaim.
- If Phase 2 is deemed not worth the full-labevents re-download: NEW-A stands as a bounded short-report-tier
  result; pivot to NEW-B (temp-uncorrected ABG, feasibility-gate first) or hunt fresh triples in less-mined data.
