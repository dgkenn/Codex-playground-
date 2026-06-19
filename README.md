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
analysis/                   # correct_sites, site_probe (the gate), cluster, characterize, audits
phase2/                     # freeze (4 objects) -> unlock_and_test (single run-once test)
artifacts/                  # PERSISTED compact tables only (~1-3 GB); raw is never written
tests/                      # test_integrity (stdlib) + test_analysis (skipped w/o sci stack)
docs/SPEC_TRACEABILITY.md   # spec section -> enforcing code -> test
```

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
3. **Phase 2 (`phase: 2`).** `unlock_and_test.py` verifies the frozen hash,
   unlocks the held-out hospital (logged), applies the frozen pipeline, and runs
   the **single** pre-registered phenotype↔outcome contrast **once** (enforced by
   a persistent run-once lock). No iteration back to Phase 1.

## Claim discipline (Sec 16)

"We used a foundation model" is a method, not a contribution. The contribution is
the site-invariance rigor, cross-hospital reproducibility, and interpretable
characterization. Failed phenotypes are reported as negative results. No causal
language; no generalization claims absent external (TUH) replication.

## Status

Scaffold + integrity core + analysis logic, all tests green (30 tests). The
BDSP/model adapter boundaries and the `TO-CONFIRM` config slots (the spec's
`[fill]` values) must be wired/pinned before a real run; guards refuse to unlock
on `TO-CONFIRM` placeholders.
