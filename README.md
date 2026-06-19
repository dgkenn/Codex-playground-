# HEEDB EEG Phenotype Discovery (Pre-Registration v2)

Implementation scaffold for **Unsupervised Raw-Waveform EEG Phenotype Discovery
on HEEDB via an Adapted Foundation Model, with Hospital-Split Confirmation**
(Pre-Registration + Execution Spec v2).

> **Integrity principle (binding).** Phase 1 (discovery) uses **no outcome label
> of any kind**. Phase 2 tests **one** pre-specified outcome on a **held-out
> hospital never touched in Phase 1**, with the model checkpoint, the
> harmonization parameters, the embedding-correction transform, and the
> phenotype-assignment function all **frozen and hash-verified** before the
> held-out data is unlocked. Any breach voids confirmatory status.

This repository encodes that firewall **in code**, not just in prose. See
[`docs/SPEC_TRACEABILITY.md`](docs/SPEC_TRACEABILITY.md) for the rule→code→test
matrix.

## What is implemented vs. left as a seam

The **integrity-critical machinery is real and unit-tested with the standard
library only** — the firewall guard, content-hashing, config invariants,
run-once lock, freeze manifest, and the disk-sparing shard/checkpoint/resume
bookkeeping. The **disk-light analysis stages** (site correction + the site
probe gate, consensus-PAC clustering, characterization, negative-control
battery) are functional on the compact tables and tested on synthetic data when
NumPy/scikit-learn are present.

Only the **site/model-specific I/O is left as a clearly-marked adapter
boundary** (`NotImplementedError` with instructions):

- `pipeline/stream_fetch.py::_BDSPClient` — credentialed BDSP catalog + streaming.
- `pipeline/embed.py::FrozenEmbedder.load / embed_windows` — load + freeze the
  chosen open checkpoint (CBraMod by default) and run the frozen forward pass.
- `phase2/unlock_and_test.py::_load_frozen_assigner` — load the frozen assigner.

## Layout

```
config.yaml                 # single source of truth: PHASE flag, seeds, sites, all params
common/                     # hashing, config validation, append-only audit log (stdlib only)
guards/heldout_guard.py     # refuses held-out loads while phase==1; logs hash-stamped unlock
pipeline/                   # Pass 1: stream_fetch -> harmonize -> embed -> features -> run_pass1
                            #   + writer.py (compact-table sink: 3 aligned tables, sharded)
analysis/                   # correct_sites, site_probe (gate), cluster, characterize, audits,
                            #   phenotype_bar (the "real phenotype" gate), run_phase1 (orchestrator)
phase2/                     # freeze (4 objects) -> run_phase2 (unlock -> cross-site
                            #   reproducibility -> single run-once outcome test)
artifacts/                  # PERSISTED compact tables only (~1-3 GB); raw is never written
tests/                      # test_integrity (stdlib) + analysis/e2e/DSP (skipped w/o sci stack)
docs/SPEC_TRACEABILITY.md   # spec section -> enforcing code -> test
```

## Phase-1 analysis chain (runs on the compact tables)

`analysis/run_phase1.py` composes the disk-light stages end-to-end:

```
load compacts -> guard sites -> Route-A correction -> site-probe GATE
 -> consensus-PAC k selection -> stability -> fit assigner
 -> per-cluster site-alignment + leave-one-site-out -> phenotype bar
 -> interpretable characterization -> acquisition-covariate audit -> report
```

It touches no outcome and no held-out site. Because the held-out hospital is
locked in Phase 1, the phenotype bar tops out at **provisional**; the held-out
cross-site ARI check (EEG only, no outcome) runs post-unlock and promotes
provisional → **confirmed** before the single Phase-2 test. `tests/test_pipeline_e2e.py`
exercises this whole chain on synthetic data with a planted site confound.

## Disk-sparing model (Sec 0)

Raw waveforms are **transient**. Each recording is streamed once, harmonized in
memory, embedded by the frozen model, reduced to one compact row (pooled
embedding + interpretable features + QC), then discarded. `open_recording` is a
context manager that deletes the shard on exit; never more than one shard of raw
exists on disk. All downstream analysis runs on the compact Parquet/Zarr tables.

## Running the tests

```bash
# Integrity core — standard library only, always runs:
python -m unittest tests.test_integrity -v

# Analysis stages — auto-skip unless numpy/scikit-learn/scipy are installed:
pip install -r requirements.txt
python -m unittest tests.test_analysis -v
```

## The two phases

1. **Phase 1 (`phase: 1`).** Discovery on `sites.discovery` only. The held-out
   hospital is hard-blocked by `HeldoutGuard`; no outcome field can enter a
   loader (`assert_no_outcome_in_loader_fields`). Produces compact embedding +
   feature tables, a site-invariant embedding, stability-selected clusters, and
   the refutation-battery results.
2. **Freeze (`phase2/freeze.py`).** Hash the four objects into
   `artifacts/frozen/manifest.json` and stamp the combined pipeline hash.
3. **Phase 2 (`phase: 2`, `phase2/run_phase2.py`).** Verifies the frozen-pipeline
   hash **and** re-verifies each frozen object (correction transform, assignment
   fn) by content hash against the manifest — so the *same* objects from
   discovery are applied, not a re-fit that could have peeked. Unlocks the
   held-out hospital (logged), acquires the single-use run-once lock, applies the
   frozen correction + assignment, runs the **cross-site reproducibility** check
   (EEG only → promotes the primary phenotype provisional → confirmed), and only
   if confirmed runs the **single** pre-registered phenotype↔outcome contrast
   **once**, followed by a shuffled-outcome leakage control. No iteration back to
   Phase 1.

## Claim discipline (Sec 16)

"We used a foundation model" is a method, not a contribution. The contribution is
the site-invariance rigor, cross-hospital reproducibility, and interpretable
characterization. Failed phenotypes are reported as negative results. No causal
language; no generalization claims absent external (TUH) replication.

## Status

Scaffold + integrity core + analysis logic + Phase-1 & Phase-2 orchestrators,
all tests green (57 tests). The
spec's `[fill]` slots are now **pinned** in `config.yaml` as documented design
decisions, with two deliberate exceptions that cannot be resolved yet:

- `model.checkpoint_sha256` — **pin at download**: the SHA-256 cannot be computed
  until the CBraMod file is fetched; it is hashed and verified before Pass 1.
- `phase2.primary_phenotype` — **set at freeze**: phenotypes do not exist until
  Phase-1 discovery runs; the phenotype matching the mechanistic prior is named
  at Phase-1 close, *before* the held-out unlock.

Guards refuse to unlock while either remains `TO-CONFIRM`. The only other
unwired pieces are the BDSP/model adapter boundaries listed above.

Key pinned choices: discovery = MGH + BWH, **held-out = BIDMC** (BCH is pediatric
and stays in the separate sensitivity cohort, never the adult confirmation site);
base model = CBraMod (`weighting666/CBraMod`, 200 Hz, 1 s patches); Phase-2
outcome = electrographic seizure / status (ICU "irritable-cortex" prior), minimum
adjusted OR 1.5 with a 95% CI excluding 1.
