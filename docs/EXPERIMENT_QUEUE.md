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
0a-prime. **[TOP PRIORITY, CPU, overnight] Full-token attention-MIL — no mean+std collapse.** Re-embed
    (or re-cache) so each window keeps its full 19×30 token grid; attention-MIL over ALL tokens. Re-run the
    AGE positive control first as the decider: age ≳0.75 ⇒ mean+std pooling was the bottleneck and a
    positive clinical finding may be reachable ON CPU (then redo cognitive/mortality with full tokens);
    age still ≈0.6 ⇒ frozen encoder insufficient ⇒ GPU fine-tuning. Cleanly separates "my pooling choice"
    from "frozen-encoder limit" before any GPU spend. Re-embedding is the slow part (~10 s/patient,
    credentialed) — checkpoint every 25 patients; a 40-patient time-boxed pilot is enough to decide the fork.
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
