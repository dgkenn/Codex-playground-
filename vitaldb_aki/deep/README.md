# Deep-learning multimodal waveform arm (`vitaldb_aki/deep/`)

Self-supervised, **label-free** encoder over the raw intraoperative VitalDB waveforms
for the postoperative-AKI study (protocol §7F, §9, §9F, §10). This is the faithful
"use **all** the information the tabular summaries discard" arm; it is benchmarked
**head-to-head against the regularized tabular baseline** (H3) — superiority is tested,
not assumed (§9, §10).

## CPU-feasibility vs GPU-full-pretraining boundary (read this first)

This box is **CPU-only** (`torch 2.5.1+cpu`, no GPU). The deliverable here is a
*correct, tested architecture + streaming* plus a **feasibility proof** that the whole
path runs end to end on a small downsampled subset with the SSL loss decreasing.

| | Feasibility (this box, CPU) | Full pretraining (GPU, future) |
|---|---|---|
| cases | 20–50 (`--cases`) | full cohort (~3.6–5.5k labelable + all waveform cases) |
| common rate | 25 Hz (`--rate`) | 100–250 Hz |
| window | 10 s | 10–60 s, possibly overlapping |
| steps | tens (`--steps`) | many epochs + early stopping on a patient-held-out split |
| encoder width | `base_channels=16`, `emb_dim=32` | tune within §10 capacity discipline |

The architecture and streaming in this package are **exactly** what a GPU run scales
up — only the scale (cases, rate, steps, width) changes. Docstrings state this boundary
honestly at every entry point.

## Files

- **`waveforms.py`** — per-case multimodal loader. Downloads the 4 verified-coverage
  channels (`SNUADC/ART`, `SNUADC/ECG_II`, `SNUADC/PLETH`, `Primus/CO2`), clips to the
  intraop window `[anestart|opstart, opend]` (**never `t > opend`**, §11), resamples
  each to a common low rate, rejects artifacts → NaN → mean-imputes/zero-fills, and
  segments into fixed `(n_windows, n_channels, win_len)` float32 windows. One case at a
  time; the whole cohort is never held (disk-sparing, mirrors `pipeline/run_pass1.py`).
  - **Packed-CSV handling:** the SNUADC tracks are served in VitalDB's *sparse-timestamp*
    ~500 Hz packed format, which the shared `data.tracks.download_track` silently drops.
    `load_packed_waveform` reconstructs the uniform time grid by interpolating the
    row-index→timestamp anchors (mirroring `features.aline_morphology.load_art_waveform`),
    **without editing the shared `tracks.py`**. `Primus/CO2` is a normal slow numeric
    track and uses `download_track` directly.
- **`encoder.py`** — compact multichannel 1D-CNN (`WaveformEncoder`): 3 depthwise-
  separable conv blocks + global average pool + linear head → `emb_dim`-vector per
  window. Capacity is deliberately small (tens of thousands of params) for the
  ~906-event reality (§10). `mean_pool_embeddings` pools per-window → one per-case vector.
- **`ssl.py`** — masked-signal-reconstruction SSL (`MaskedReconstructionSSL`). Masks
  contiguous spans of each window, reconstructs the original at the masked positions
  (MSE on masked timesteps only). **No label** → pretrains on every case's waveforms
  (whole dataset, leakage-safe, §10/§11). `make_mask` is pure NumPy + deterministic.
- **`run_pretrain.py`** — CPU feasibility driver. Streams a small subset, runs a few SSL
  steps (loss should trend **down**), freezes the encoder, and dumps per-case mean-pooled
  embeddings to `.npz`. `--cases N` caps the subset.
- **`tests` →** `vitaldb_aki/tests/test_deep.py` — offline (no network): windowing math,
  §11 post-opend exclusion, NaN handling, encoder shape, SSL loss finiteness + single-step
  decrease, pooling shape.

## Run

```bash
# offline unit tests
python3 -m unittest vitaldb_aki.tests.test_deep -v

# CPU feasibility (downloads ~20 cases, downsampled; a couple of minutes)
python -m vitaldb_aki.deep.run_pretrain --cases 20
```

## How the frozen embedding feeds the H3 head-to-head

1. **Pretrain (label-free, all cases):** SSL on every case's waveform windows; freeze
   the encoder.
2. **Per-case embedding:** for each labelable case, window its intraop waveforms, run
   the frozen encoder, mean-pool over windows → one `emb_dim` vector. `run_pretrain.py`
   writes these as `case_embeddings.npz` (`caseids`, `embeddings`).
3. **Concatenate with tabular features:** the per-case embedding is appended as extra
   columns to the §7/§8 tabular feature matrix (`features/build_matrix.py`), keyed by
   `caseid`. The **deep arm** = tabular ⊕ embedding (or embedding-only); the **baseline**
   = tabular alone. Both use **identical patient-level splits** (§10/§11.6) and the same
   nested-CV / class-imbalance handling.
4. **Report honestly (H3, §10):** ΔAUROC / AUPRC with patient-level bootstrap CIs. If the
   deep arm does not beat the baseline on this sample, that is a legitimate, reportable
   finding — "deep learning did not add value at this scale" — not something to hide.

**Leakage discipline.** Pretraining and embedding only ever see intraoperative samples
(`waveforms.py` enforces the `opend` cutoff) and never the AKI label; the embedding is a
function of the signal alone. Negative control (§11.5): phase-randomized surrogate
waveforms should collapse the arm's contribution.

**Cannot transfer to INSPIRE.** The external set has no waveforms (§13) — this arm is
VitalDB-only; only the clinical + PK components externally validate.
