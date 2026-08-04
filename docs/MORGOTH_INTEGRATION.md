# MORGOTH integration — what's done, what's pending, how to wire it

**Operational status:** the pipeline runs on the **CBraMod** frozen backbone today
(real weights, sha256-pinned, validated end-to-end on real HEEDB data). **MORGOTH
is the v3 protocol's target backbone** and is a clean future swap. This doc is the
wire-up checklist for the moment its artifacts become available.

## Why MORGOTH isn't wired yet (blocker)
- **Data is accessible:** `s3://bdsp-opendata-credentialed/morgoth1/` via the
  access point `arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-projects-ap`
  (AWS profile with the granted credentials). It holds `data/internal_dataset/`
  (labeled task sets: SEIZURE, IIIC, GPD/LPD/LRDA/GRDA, slowing, BS, sleep, …) and
  `data/pretrain/` (SSL `.mat`). **No model code or checkpoint is in S3** (108k
  keys scanned — data only).
- **Code + weights are NOT public:** `github.com/bdsp-core/morgoth` returns 404
  (the Lancet Digital Health paper is "in press"; the repo isn't released). The
  pretrained checkpoint is distributed via a **Dropbox link inside that repo's
  README**, which is therefore unreachable.
- A randomly-initialised MORGOTH rebuilt from the paper's prose would be
  meaningless — so we wait for the real checkpoint + model code.

## Architecture (from the paper, for reference)
MORGOTH = **VQ tokenizer → EEG Transformer → task heads**. The tokenizer maps
continuous EEG to **8,192 discrete tokens** via contrastive learning + vector
quantization (LaBraM-like, not CBraMod-like). Input: 19-ch 10-20 @ 200 Hz,
bandpass 0.5–70 Hz, notch 50/60, common-average; accepts EDF + MAT. Heads:
6-class IIIC, spike, slowing, burst-suppression, AASM sleep, 17 EEG-level findings.

## What you must obtain (two artifacts)
1. The **pretrained checkpoint file** (the Dropbox download from the README).
2. The **model-definition code** (the `nn.Module` for the tokenizer + transformer)
   — paste the file(s), or provide a GitHub token / repo access for `bdsp-core/morgoth`.

## How to wire it (≈ a focused session once the artifacts are in hand)
The seam is already in place; only the backbone class is new.

1. **`MorgothEmbedder`** in `pipeline/embed.py`, mirroring `FrozenEmbedder`'s
   contract:
   - `load()`: resolve + **sha256-verify** the checkpoint; load with
     `torch.load(..., weights_only=True)` if it's a pure state_dict (no pickle
     exec); construct the MORGOTH architecture from the provided code;
     `eval()` + freeze; tap the transformer-encoder output for embeddings.
   - `embed_windows(windows)`: `(n_windows, 19, n_samples)` → pooled
     `(n_windows, d)` (same as CBraMod).
   - **`task_outputs(windows)`** (NEW, MORGOTH-only): return the per-recording
     task-head probability vector (6-class IIIC + sleep + spike/slowing/BS + the
     17 findings). This is the one extra method MORGOTH adds.
2. **Backbone selection:** `pipeline/embed.py` should pick the embedder from
   `cfg.model.name` ("CBraMod" → `FrozenEmbedder`, "MORGOTH" → `MorgothEmbedder`);
   `pipeline/run_pass1.run` already constructs `FrozenEmbedder(cfg)` by default,
   so add a small factory.
3. **Config:** set `model.name: MORGOTH`, `model.repo_id`/`checkpoint_file`/
   `checkpoint_sha256` to the MORGOTH artifact; keep harmonization at 0.5–70 Hz
   (already MORGOTH-compatible).

## What is ALREADY built for MORGOTH (no further work needed)
- **Task-output persistence:** `run_pass1.process_recording` calls
  `embedder.task_outputs(windows)` **if the method exists** and writes the vector;
  `CompactTableWriter` persists it to a `model_outputs/` table; `load_compact_tables`
  exposes `tables["model_outputs"]`. No-op for CBraMod, tested both ways.
- **Redundancy / novelty control (v3 Sec 9(4), 13.3):**
  `analysis/morgoth_redundancy.py` is wired into `analysis/run_phase1.py` — it
  reads `tables["model_outputs"]` and **rejects any phenotype reducible to the
  model's task outputs**. It auto-skips when there are no task outputs (CBraMod).
  So the moment `MorgothEmbedder.task_outputs` exists, the control goes live with
  zero further wiring.
- **Phase-2 adjustment (Sec 12):** `phase2.adjusted_association` already accepts
  covariates — pass the MORGOTH findings as covariates so the outcome effect is
  the residual beyond known findings.

## Validation checklist when wiring (mirror the CBraMod bring-up)
- checkpoint sha256 matches the pinned value;
- `load()` reports only the expected missing keys (e.g. an absent head);
- `embed_windows` returns finite `(n_windows, d)`, deterministic under the frozen
  model;
- `task_outputs` returns a sane probability vector;
- a small real pilot (`scripts/run_real_pilot.py` with `PILOT_EMBEDDER` pointed at
  MORGOTH) completes and now emits a `model_outputs/` table;
- `run_phase1` reports a non-trivial `morgoth_redundancy` block.
