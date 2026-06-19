# Pre-Registration + Execution Spec (v3): Unsupervised Raw-Waveform EEG Phenotype Discovery on HEEDB via an Adapted Foundation Model, with Hospital-Split Confirmation

> **Changelog (v3.0):** Adopt **MORGOTH 1.0** (HEEDB-team clinical-EEG foundation model, Westover/Jing, June 2026) as the frozen embedding backbone in place of CBraMod; add a mandatory **MORGOTH-finding redundancy / novelty control** (phenotypes must carry information beyond MORGOTH's own task outputs, enforced as both novelty criterion and leakage control); move the recommended Phase-2 primary outcome off MORGOTH-represented targets (seizures/IIIC) to a downstream non-EEG outcome with MORGOTH-finding adjustment; qualify the held-out claim (MORGOTH saw all four hospitals during pretraining, so the held-out test shows clustering/assignment transportability, not representation naivety) and strengthen TUH external replication; add a CC BY-NC 4.0 license/IP firewall.

**Version:** 3.0 (supersedes v2.0; v2 swapped engineered features for an adapted foundation-model embedding — v3 makes that backbone **MORGOTH**, the domain-matched HEEDB-pretrained clinical model, and adds the circularity/novelty control that this choice requires)
**Date:** _[fill]_
**PI:** Dean Kennedy, MD
**Registration target:** OSF (recommended 12-month embargo)
**Type:** Secondary analysis, two-phase, with a strict firewall between unsupervised discovery and a single pre-registered outcome test.
**Execution:** Designed for implementation by Claude Code in a **storage-constrained** environment. §0 defines the engineering constraints that govern every stage.

> **Integrity principle (binding).** Phase 1 (discovery) uses **no outcome label of any kind**. Phase 2 tests **one** pre-specified outcome on a **held-out hospital never touched in Phase 1**, with the foundation-model checkpoint, the harmonization parameters, the embedding-correction transform, and the phenotype-assignment function all **frozen and hash-verified** before the held-out data is unlocked. Any breach voids confirmatory status.

---

## 0. Execution Model and Engineering Constraints (read first)

**Disk-sparing core principle.** Raw waveforms are large and **transient**; only compact derivatives are persisted. The pipeline never materializes a full preprocessed-waveform corpus.

**Single streaming pass (Pass 1).** For each recording, exactly once:
1. fetch/stream the raw recording (or one shard at a time);
2. harmonize **on the fly** in memory (§7.2) — never written to disk;
3. run a **frozen** foundation-model forward pass → pool to a per-recording embedding (§7.3);
4. compute the interpretable feature vector in the same pass (§7.4);
5. write one compact row (embedding + MORGOTH task outputs + interpretable features + QC metadata);
6. **discard the raw** (and, if bulk-downloaded, delete the shard before fetching the next).

After Pass 1, **all analysis runs on the compact tables**; raw is touched again only if a parameter changes and recomputation is required.

**Persistent footprint (estimate).** Pooled embedding (~256–1024 floats ≈ 1–4 KB) + MORGOTH task outputs (~few dozen floats) + interpretable features (~few hundred floats) + metadata, per recording. For ~284k recordings this is **~1–3 GB total**, plus the model checkpoint (~tens of MB). The large transient cost is per-shard RAM/scratch, not persistent disk. **MORGOTH is used only as a frozen embedder/inference model: download the small published *checkpoint*, never the ~275 GB pretraining corpus.** The disk-sparing logic is unchanged from v2 by this backbone swap.

**Engineering rules (hard constraints for Claude Code):**
- **Frozen inference by default** — no activation/gradient storage. The only optionally-heavy step is continue-pretraining (§7.5), which is opt-in and operates on a streamed subset.
- **Shard + checkpoint + resume.** Process in shards; checkpoint the compact output table; the run must be resumable after interruption. Never hold more than one shard of raw in memory/scratch.
- **Compressed, memory-mapped storage** for persisted arrays (Parquet for tables; Zarr/HDF5 + blosc/zstd for any arrays); chunked/lazy reads only.
- **Held-out hospital is access-gated in code** — a guard refuses to load held-out site data while a `PHASE==1` flag is set. Unlock is an explicit, logged, hash-stamped action.
- **No outcome variable is importable into the Phase-1 workspace.** Enforce by config: Phase-1 data loaders expose EEG + acquisition metadata (and MORGOTH's EEG task outputs) only — never a clinical outcome.
- **Deterministic + config-driven.** All seeds fixed; all parameters in a single versioned config; every artifact carries a content hash.
- **Agentic loop = plumbing + audits + refutation only.** No outcome-coupled autonomous search; the loop's objective is to *break* candidate phenotypes, never to generate new hypotheses.

---

## 1. Background and Rationale

HEEDB (Sun, Westover, et al., *Epilepsia* 2025) aggregates ~284,000 clinical EEG studies from ~109,000 patients across four Harvard hospitals (MGH, BWH, BIDMC, Boston Children's), BIDS-harmonized, hosted on the Brain Data Science Platform, and EHR-linked (ICD-10, medications, notes, reports, labs).

**Why raw-waveform SSL.** Engineered features are lossy human-chosen summaries; self-supervised representations learned from raw signal can capture structure no feature set encodes, and HEEDB's scale is the regime where this pays off. Because an SSL objective sees **no outcome**, it preserves the discovery/confirmation firewall.

**Why adapt, not pretrain.** Open clinical-EEG foundation models with public checkpoints now exist. Pretraining from scratch is multi-GPU-days with little marginal gain. v3 **adapts a frozen checkpoint** (embedding extraction) by default — specifically **MORGOTH** (§7.1), which was pretrained on HEEDB itself and is therefore domain-matched and clinical-grade.

**The amplified risk (now two-headed).** First, raw signal carries the full acquisition fingerprint (amplifier, filter, montage, reference, sampling rate, 50/60 Hz, drift); an SSL objective learns the device signature efficiently, so site-invariance (§8) is load-bearing. Second, **MORGOTH was pretrained on HEEDB and fine-tuned to emit the known clinical findings, so its embedding already encodes them** — a phenotype "discovered" in this space risks being a re-expression of an existing MORGOTH output. v3 therefore adds a mandatory **redundancy/novelty control** (§9, §11, §13): a phenotype counts only if it carries information **beyond MORGOTH's own task outputs**. Phenotypes must also be characterized in **interpretable** features (§10) to remain defensible.

---

## 2. Objectives and Hypotheses

**Phase 1 (discovery; descriptive, no outcome).**
- **Aim 1.** Identify EEG phenotypes in the frozen MORGOTH-embedding space whose structure is **stable across resampling and reproducible across hospitals**.
- **Aim 2.** Give each phenotype an **interpretable** spectral/connectivity signature, and establish that it carries **information beyond MORGOTH's own task outputs** (the 17 EEG-level findings, the 6-class IIIC label, sleep stage, spike, slowing, and burst-suppression heads) — the novelty criterion, operationalized in §11/§13.

**Phase 2 (confirmation; pre-registered, single outcome, held-out hospital).**
- **H1.** Phenotype membership associates with **one** pre-specified **downstream, non-EEG outcome** that MORGOTH does not directly represent (mechanistic prior; §12), tested on the held-out hospital after the leakage/confound battery (§13), **adjusted for MORGOTH's detected findings** so the phenotype's contribution is the **residual beyond known findings**.
  - **Association criterion (fixed before unlock):** _[fill — e.g., adjusted OR/HR with 95% CI excluding 1 and a pre-specified minimum effect size]_, EEG temporally preceding the outcome, **with MORGOTH's findings included as covariates**.

**Not claimed:** disease-entity status; causality; generalization beyond the Harvard network without external replication (§15); representation naivety of the held-out hospital (MORGOTH saw all four hospitals in pretraining — §6).

---

## 3. Two-Phase Design and the Firewall

Phase 1 runs on the discovery hospitals with no outcome loaded. At Phase-1 close, four objects are frozen and hashed: (a) the MORGOTH model checkpoint, (b) the on-the-fly harmonization config, (c) the embedding-correction transform (§8), (d) the phenotype-assignment function. Only then is the held-out hospital unlocked, the frozen pipeline applied, and the single Phase-2 test run **once**. No iteration from Phase-2 results back to Phase-1 choices.

---

## 4. Data Source and Access

- **Dataset:** HEEDB v4.x via BDSP (credentialed; DUA in place).
- **Access pattern (disk-sparing):** prefer per-recording streaming; if bulk transfer is required, **batch-and-delete** (download a shard → process → delete → next).
- **Model access:** MORGOTH checkpoint + code via BDSP credentialed access / `github.com/bdsp-core/morgoth` (CC BY-NC 4.0; §16/§18). Only the compact checkpoint is fetched — never the pretraining corpus.
- **Constraints:** strong multi-site batch structure; mixed care settings (routine/EMU/ICU/sleep) and ages (pediatric at BCH); heterogeneous lengths/quality; report-derived findings are NLP/regex/expert-curated and imperfect.

---

## 5. Cohort and Eligibility

- **Adults (≥18 y)** for primary analysis; **BCH/pediatric** handled as a separate pre-specified sensitivity cohort, not pooled.
- **One qualifying recording per patient** (pre-specified rule, e.g., earliest qualifying study) to prevent within-patient leakage; **all splits patient-level**; no patient shared across partitions.
- **Phase-2 inclusion:** qualifying EEG/segment that **temporally precedes** the outcome window.
- **Exclusions:** recordings failing pre-specified signal-quality thresholds; montages not mappable to the common channel set.

---

## 6. Hospital-Split Architecture

- **Discovery hospitals:** _[pre-specify, e.g., MGH + BWH + BIDMC]_.
- **Held-out hospital:** _[pre-specify]_, untouched in Phase 1; dual role: (1) **phenotype-reproducibility check** — frozen assignments vs an independently re-derived clustering must agree (pre-specified ARI ≥ _[fill]_); (2) **locked outcome-confirmation set**.
- **Lock:** held-out access code-gated; unlock logged with the frozen-pipeline hash.
- **Backbone caveat (binding, new in v3).** MORGOTH was pretrained on **all four** HEEDB hospitals, so the held-out hospital is held out from the **clustering and the outcome test, but NOT from the representation backbone**. The held-out test therefore demonstrates **transportability of the clustering/assignment function** (do the same phenotypes re-emerge and carry the same outcome signal at an unseen site?), **not representation naivety**. Claims must be worded accordingly.
- **External replication (next step, not in this protocol):** TUH EEG Corpus (different health system) is the gold-standard validation, and is **strengthened to a requirement** in v3 (§15).

---

## 7. Representation — Adapted Foundation Model (MORGOTH; redesigned core)

**7.1 Base model.** Adopt an open checkpoint, **frozen**. **Primary (recommended): MORGOTH 1.0** — a clinical-EEG foundation model from the HEEDB team (Sun, Westover, Jing; released June 2026; in press, *Lancet Digital Health*), self-supervised on 14,500 HEEDB patients and fine-tuned with task heads for seizure/ictal–interictal-continuum (6-class: seizure/LPD/GPD/LRDA/GRDA/other), spike detection, slowing (focal/generalized/none), burst suppression, AASM sleep staging, and 17 EEG-level binary findings, across routine/EMU/ICU/sleep EEG; externally validated on 1,573 patients across 48 institutions (including TUH). Public checkpoints/code: `github.com/bdsp-core/morgoth`. **Why MORGOTH is preferred:** it is **pretrained on HEEDB itself (domain-matched)** and **clinical-grade** (validated, multi-setting), so its embedding is a strong, in-distribution representation of exactly this data. **Alternatives (now secondary):** CBraMod, LaBraM, EEGPT, BIOT — generic clinical-EEG SSL models, retained only as robustness/sensitivity comparators. Record exact version/hash of whichever backbone is used.

**7.2 On-the-fly harmonization (transient; never persisted).** Per recording, in memory, map to **MORGOTH's expected input**: 19-channel 10-20 montage; **common-average montage**; resample to **200 Hz**; **bandpass 0.5–70 Hz**; **notch 50 and 60 Hz**; window/patch per MORGOTH's spec; pre-specified automated artifact rejection. MORGOTH accepts EDF and MAT; harmonized signal feeds the model directly and is discarded.

**7.3 Embedding + task-output extraction (Pass 1; frozen forward only).** Per window → frozen MORGOTH forward → **(a)** pooled per-recording embedding (pre-specify pooling, e.g., mean + std over windows) and **(b)** MORGOTH's **task-head outputs** (the 6-class IIIC posterior, sleep-stage posterior, spike/slowing/burst-suppression, and the 17 EEG-level finding probabilities), pooled to a compact per-recording vector. **Persist both** — the embedding is the discovery space (§9); the task outputs are the reference set for the redundancy/novelty control (§11/§13) and the Phase-2 adjustment (§12). Persist **epoch-level** embeddings only for a pre-specified random subsample reserved for stability analysis (disk-sparing).

**7.4 Interpretable feature extraction (same Pass 1).** Compute and persist a compact interpretable feature vector: band powers, **aperiodic exponent and offset** (specparam), spectral edge, connectivity (e.g., wPLI), entropy/complexity, microstate parameters. This is the characterization/probing space (§10), independent of MORGOTH's heads so the §10 description is not itself circular.

**7.5 Optional Route B (heavier; opt-in).** Site-adversarial **continue-pretraining** of MORGOTH via lightweight adapters/LoRA with a gradient-reversal site head, on a **streamed subset**. Requires GPU rental and repeated raw streaming; use only if Route A (§8) leaves residual site structure. (Continue-pretraining MORGOTH weights inherits the CC BY-NC 4.0 terms — §16/§18.)

---

## 8. Site-Invariance (disk-aware)

**Route A (default; disk-light).** Correct site structure **in embedding space**, operating only on the compact stored embeddings: ComBat across hospitals/devices, or domain-adversarial/CORAL alignment, or site-classifier residualization (pre-specify one as primary). This is cheap because it runs on the small embedding table, not the raw.

**Route B (optional).** Site-adversarial continue-pretraining (§7.5).

**Site-identity probe (the gate).** After correction, attempt to predict hospital / device / sampling-rate from the corrected embeddings. Performance must be **at or near chance**; otherwise escalate correction (or invoke Route B), or reject affected structure. Phenotypes aligning with site predictions are rejected.

---

## 9. Phenotype Discovery and the "Real Phenotype" Bar

On the **corrected** embeddings (compact tables; disk-light):
- **Clustering:** pre-specified algorithm(s) (e.g., GMM / Leiden on a neighbor graph).
- **k selection:** by a **pre-specified stability criterion** (consensus clustering / PAC; corroborated by gap statistic / silhouette across resamples) — never by post-hoc interpretability.
- **A cluster is a phenotype only if ALL hold:** (1) resampling-stable above threshold; (2) cross-site reproducible — re-emerges on the held-out hospital at the ARI threshold (§6; this tests **assignment transportability**, not representation naivety); (3) survives the site audit (§8, §11); **(4) carries information beyond MORGOTH's own task outputs — the redundancy/novelty control (§11/§13): a cluster that is fully predictable from MORGOTH's findings is a re-expression of a known output and is excluded.** Failing clusters are reported as unstable/redundant and excluded from Phase 2.

---

## 10. Interpretable Characterization (descriptive; NOT the outcome test)

Probe each phenotype's interpretable signature: linear/probe mappings from the frozen embedding onto the §7.4 features, yielding a spectral/aperiodic/connectivity profile per phenotype. Report descriptive demographic/clinical distributions **for interpretation only**; this must not be used to select the Phase-2 outcome (which is pre-specified before unlock). Because the §7.4 features are computed independently of MORGOTH's heads, this characterization complements (does not substitute for) the §9(4)/§13 novelty control.

---

## 11. Site-Confound / Batch Audit (load-bearing)

All on compact tables: (1) **site-identity probe** (§8, the gate); (2) pre/post-correction structure comparison; (3) **leave-one-site-out** reproducibility (structure derived while excluding each discovery site must persist); (4) acquisition-covariate association (phenotype vs sampling rate, montage, recording length) — flag if dependent; **(5) MORGOTH-finding redundancy check (new in v3; full definition in §13.3): test whether phenotype membership is reducible to / predictable from MORGOTH's task outputs; a phenotype that adds nothing beyond them fails the novelty bar (§9(4)).** Reported regardless of result.

---

## 12. Phase 2 — Pre-Registered Single-Outcome Association

- **One outcome, mechanistic prior, fixed before unlock — and chosen to be NON-CIRCULAR with MORGOTH.** Because MORGOTH directly detects seizures and the IIIC, "progression to electrographic seizures/status" is **circular** in the MORGOTH-embedding space and is **no longer recommended as primary**. Choose a **downstream, non-EEG outcome that MORGOTH does not directly represent**:
  - **Recommended primary: in-hospital mortality** (prior: a phenotype indexing global cortical dysfunction beyond any single labeled finding precedes death), **or neurological/functional recovery** (e.g., discharge mRS / recovery after cardiac arrest; prior: a low-complexity/suppression-leaning phenotype → poor recovery). Both are downstream clinical outcomes, not EEG labels.
  - Other acceptable downstream outcomes: subsequent epilepsy diagnosis at a defined horizon, readmission, or functional status — any non-EEG outcome with a stated mechanistic prior.
  - **If a seizure/IIIC-related outcome is retained at all, it is permitted only with explicit adjustment for MORGOTH's own seizure/IIIC detection output as a covariate** (otherwise the association is mechanically circular).
- **Mandatory MORGOTH-finding adjustment (novelty + leakage control).** The single test is **adjusted for MORGOTH's detected findings** (the 17 findings + 6-class IIIC + sleep stage, plus spike/slowing/burst-suppression as applicable), so the estimated phenotype effect is the **residual contribution beyond known findings**. This single move serves as **both the novelty criterion and a leakage control**: a phenotype that only "works" because it re-encodes a MORGOTH finding will null out after adjustment.
- **Temporal precedence** verified per patient.
- **Test:** frozen phenotype membership vs the single outcome on the held-out hospital, adjusted for pre-specified covariates (age, sex, care setting) **and for MORGOTH's findings**, with effect size and 95% CI. If >1 phenotype is tested, correct across phenotypes (pre-specify) and name one primary contrast. **Run once.**

---

## 13. Leakage-Audit Battery

1. **Negative controls (must fail):** shuffled outcome labels → association collapses to chance; **phase-randomized surrogate EEG** (computed on streamed raw, transient) → phenotype structure collapses.
2. **EHR-leakage controls (Phase 2):** EEG report text, ICD codes, and medications are **never inputs**; phenotype must not proxy the **indication** for the EEG or a **medication** (test and adjust/flag); confirm EEG precedes outcome.
3. **MORGOTH-finding redundancy / novelty control (new in v3, mandatory).** Quantify how much of phenotype membership is explained by MORGOTH's task outputs: fit a classifier predicting phenotype label from MORGOTH's findings (17 binary + 6-class IIIC + sleep stage + spike/slowing/burst-suppression) and report the achievable accuracy/AUC and the residual. **A phenotype is admitted only if it is NOT fully reducible to MORGOTH's outputs** (pre-specify the residual/irreducibility threshold). In Phase 2 the outcome association is additionally **adjusted for these same findings** (§12), so a phenotype that survives carries outcome information **beyond** MORGOTH's known findings. This control is **both the novelty criterion (§9(4)) and a leakage control** — a phenotype that is merely a relabeling of a MORGOTH output cannot pass either.
4. **Partitioning:** patient-level throughout; held-out opened once; frozen-pipeline hash verified at Phase-2.

---

## 14. Statistical Analysis and Multiplicity

Phase-1 endpoints reported with pre-specified thresholds and uncertainty. Phase-2 has **one** primary phenotype-outcome contrast (adjusted for MORGOTH findings); secondary contrasts multiplicity-controlled and labeled secondary. **Patient is the unit.** Class imbalance and the single-test design (not n) govern power; pre-specify minimum evaluable held-out n.

---

## 15. What This Study Cannot Establish

Causality (observational); that phenotypes are disease entities (they are reproducible signal sub-structures until externally validated); **representation naivety of the held-out hospital** (MORGOTH was pretrained on all four hospitals — the held-out test shows assignment transportability, not an unseen representation; §6); generalization beyond the Harvard network. **A finding here is a hypothesis until it replicates on TUH** — and in v3 this is a **requirement, not an aspiration**: external replication on the TUH EEG Corpus is mandatory before any disease/biomarker claim. Because MORGOTH was itself validated on TUH, a **clinical-grade backbone baseline already exists there**, making TUH the natural and well-powered replication target; the discovered phenotype-assignment function and its MORGOTH-finding-adjusted outcome association must reproduce on TUH.

---

## 16. Claim Discipline (binding)

Permitted: "reproducible, cross-site-stable, mechanistically-characterized EEG phenotypes — **not reducible to MORGOTH's known findings** — one of which is associated with [downstream non-EEG outcome], **beyond MORGOTH's detected findings**, in a pre-registered, held-out, leakage-audited test." Prohibited: causal language; "novel biomarker" for any cluster failing §9/§11/§13 (including the redundancy control); claims from §10 descriptions; claims of held-out **representation** novelty (the backbone saw all four hospitals — §6); generalization claims absent TUH (§15). **"We used a foundation model" is a method, not a contribution** — the contribution is the site-invariance rigor, cross-hospital reproducibility, **demonstrated novelty beyond MORGOTH's outputs**, and interpretable characterization. Failed/redundant phenotypes are reported as negative results.

**License/IP firewall (binding).** MORGOTH code and weights are licensed **CC BY-NC 4.0**: academic **research and publication are permitted, but no commercial product may be built on MORGOTH weights or derivatives** (including any UCE / depth-of-anesthesia monitor or other IP). MORGOTH-based research artifacts must be kept **separate from any own-weights commercial IP from the outset** (§18).

---

## 17. Role of Automated Tooling (Claude Code)

Plumbing + audits + refutation only: build the streaming harmonize→embed→feature pipeline; enforce the §0 disk-sparing rules; build and run the negative-control, site-confound, **and MORGOTH-redundancy** batteries on **every** candidate; literature-ground each characterized phenotype against known patterns (generalized slowing, known periodic patterns, **and MORGOTH's own finding set**) to assess genuine novelty. The loop tries to **break** candidates. No outcome-coupled autonomous search. Held-out access is code-gated.

---

## 18. Reproducibility and Governance

Release code (harmonization, embedding extraction, correction, clustering, audits); pin environment; archive the frozen MORGOTH checkpoint reference, correction transform, and assignment function with content hashes; archive the compact embedding / MORGOTH-output / feature tables. Register on OSF before any outcome-coupled analysis; 12-month embargo. Log all deviations with date/rationale; separate confirmatory from exploratory.

**License/IP separation (binding governance).** Because MORGOTH is **CC BY-NC 4.0 (non-commercial)**, maintain a hard separation from the outset between (a) **MORGOTH-based research artifacts** (embeddings, derived phenotypes, analysis code that loads MORGOTH weights) — research/publication only — and (b) any **own-weights commercial IP** (e.g., a depth/UCE monitor) trained without MORGOTH weights or MORGOTH-derived data. Do not let MORGOTH weights, activations, or derivatives flow into a commercial codebase; track provenance so the non-commercial boundary is auditable.

---

## 19. Suggested Artifact Layout (for Claude Code)

```
config.yaml                 # all params, seeds, MORGOTH version, PHASE flag, site assignments
guards/heldout_guard.py     # refuses held-out loads while PHASE==1; logs unlock + hash
pipeline/
  stream_fetch.py           # per-recording / batch-and-delete fetch
  harmonize.py              # on-the-fly, in-memory only (19ch/200Hz/0.5-70/notch/common-avg)
  embed.py                  # frozen MORGOTH forward -> pooled embedding + task outputs
  features.py               # interpretable feature vector (same pass)
  run_pass1.py              # shard + checkpoint + resume; writes compact rows only
artifacts/                  # PERSISTED (compact, ~1-3 GB total)
  embeddings.parquet        # pooled per-recording MORGOTH embeddings
  morgoth_outputs.parquet   # per-recording MORGOTH task outputs (17 findings, 6-class IIIC,
                            #   sleep stage, spike/slowing/burst-suppression) -- redundancy ref
  embeddings_epoch_subset.zarr  # epoch-level, sampled subset only
  features.parquet
  qc.parquet
  frozen/                   # MORGOTH checkpoint hash, correction transform, assignment fn, hashes
analysis/                   # all on compact tables
  correct_sites.py          # Route A embedding-space correction
  site_probe.py             # the gate
  cluster.py                # discovery + stability + cross-site reproducibility
  characterize.py           # interpretable probing
  morgoth_redundancy.py     # novelty/leakage control: phenotype vs MORGOTH task outputs
  audits.py                 # negative controls + batch audit + MORGOTH-redundancy battery
phase2/
  unlock_and_test.py        # applies frozen pipeline to held-out; single test
                            #   ADJUSTED for MORGOTH findings; run-once lock
```

---

## 20. References (key anchors)
- Sun C, Jing J, … Westover MB. Harvard Electroencephalography Database. *Epilepsia* 2025;66:3411–3425.
- Sun C, Westover MB, Jing J, et al. **MORGOTH: a unified clinical-EEG foundation model.** *Lancet Digital Health* (in press, 2026). Code/checkpoints: `github.com/bdsp-core/morgoth`; resource: bdsp.io/content/morgoth1/1.0.0/ (CC BY-NC 4.0). **[primary backbone]**
- Wang J, et al. CBraMod: a criss-cross brain foundation model for EEG decoding. *ICLR* 2025. *[alternative backbone]*
- Jiang WB, et al. LaBraM: large brain model. *ICLR* 2024. *[alternative]* / Wang G, et al. EEGPT. *NeurIPS* 2024. *[alternative]* / Yang C, et al. BIOT. *NeurIPS* 2023. *[alternative]*
- Johnson WE, Li C, Rabinovic A. ComBat batch-effect adjustment. *Biostatistics* 2007.
- Ganin Y, et al. Domain-adversarial training (gradient reversal). *JMLR* 2016. / Sun B, Saenko D. CORAL. 2016.
- Monti S, et al. Consensus clustering. *Machine Learning* 2003.
- Donoghue T, et al. Parameterizing neural power spectra (specparam). *Nat Neurosci* 2020.
