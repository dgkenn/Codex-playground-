# EXPERIMENT QUEUE — prioritized backlog (re-rank every cycle; pull the top item that fits compute)

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
