# EXPERIMENT QUEUE — prioritized backlog (re-rank every cycle; pull the top item that fits compute)

Priority = (impact × novelty × feasibility) / cost. GPU items are blocked until a GPU env is available;
CPU items can run now. Move done items to FINDINGS_LEDGER.md with their verdict.

## GPU-gated (the high-impact program — needs a GPU environment)
1. **[FLAGSHIP] Fine-tuned EEG foundation model → abnormal-EEG, cross-site validated.** CBraMod + a
   full-token attention/MIL head (NOT mean-pool), fine-tuned; train S-sites, test I-sites. Target AUC
   ~0.88–0.92 (published bench). Establishes the pipeline + the first cross-site EEG-FM result.
2. **EEG foundation model → in-hospital mortality (DateOfDeath), landmark + cross-site.** Prognostic EEG
   biomarker; hard endpoint; genuine white space (no FM applied to this with external validation).
3. **EEG foundation model → cognitive/encephalopathy (delirium proxy), cross-site.** Directly beats the
   DELPHI-EEG single-center bar; the delirium-prediction white space from the gap survey.
4. **Multimodal fusion: EEG-FM embedding + EHR/OMOP → outcome.** Does EEG add incremental value over
   clinical features (the question the reachable-data delirium work couldn't answer)? Quantify ΔAUC.
5. **Self-supervised EEG phenotype discovery (the repo's pre-registered Phase-1/2 design).** Unsupervised
   embedding → cluster → hospital-split confirmation → single pre-registered outcome test.

## CPU-feasible now (can run without GPU)
6. **Prior-art / novelty sweeps** for each queued idea (haiku + PubMed) before committing GPU time.
7. **Cohort + label engineering on HEEDB metadata** (OMOP outcomes, mortality linkage, site splits,
   label QC) so GPU jobs start instantly when compute is available. (Aggregate only; PHI stays local.)
8. **Tabular baselines** for each outcome (age/sex/EHR → outcome) to define the bar the EEG-FM must beat.
9. **Red-team any finding** the moment it exists (sonnet panel): external validation, confounding, p>>n,
   leakage, novelty.

## Rules
- Before any GPU item: run its CPU novelty pre-screen (#6) + tabular baseline (#8) so the GPU run has a
  clear target and isn't a known dead end.
- Log every result (positive or null) to LESSONS.md with the mechanism; a clean kill is progress.
- Re-rank after each cycle based on what was learned.
