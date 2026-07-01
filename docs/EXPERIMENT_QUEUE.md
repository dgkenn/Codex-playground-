# EXPERIMENT QUEUE — prioritized backlog (re-rank every cycle; pull the top item that fits compute)

Priority = (impact × novelty × feasibility) / cost. **CPU-only right now; overnight runs are fine.** Every
item must clear the hostile-review gate (RESEARCH_MACHINE.md) before it counts. Move done items to
FINDINGS_LEDGER.md with their verdict + the attack map.

## FLAGSHIP — runnable now on CPU (overnight), dodges the GPU block
1. **[BUILD, overnight] Frozen CBraMod per-window embedding cache at scale.** Stream HEEDB EEGs (µV
   scaling!), embed 30 s windows across the recording, cache **per-window** embeddings (NOT mean-pooled)
   + labels + site for ~3–4k patients/site across the 4 sites. Checkpoint every 50 patients. This is the
   substrate for #2–#4.
2. **[FLAGSHIP] Attention/MIL head over frozen per-window embeddings → abnormal-EEG, cross-SITE validated.**
   Train a small attention/multiple-instance head (CPU-fast on cached embeddings) that attends over windows
   instead of mean-pooling — directly attacks the mean-pool ceiling (LESSONS: mean-pool is amplitude-
   dominated/low-rank). Train S-sites, test I-sites. Target: beat the 0.62 frozen-mean-pool floor and
   approach the fine-tuned bench; report the honest cross-site AUC. Hostile-review gate mandatory.
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
