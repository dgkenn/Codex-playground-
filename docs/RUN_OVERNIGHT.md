# RUN_OVERNIGHT — 16-worker single-GPU-box Pass-1 runbook

This document describes how to run the full HEEDB Pass-1 pipeline overnight on
a single GPU box using 16 parallel shard workers.  The run is **resumable**:
re-running the launch command is safe and skips already-completed recordings.

---

## 1. Prerequisites on the GPU box

### 1.1 Clone and check out the branch

```bash
git clone <repo-url> Codex-playground
cd Codex-playground
git checkout claude/heedb-eeg-phenotype-discovery-2mnwzx
```

### 1.2 Install Python dependencies

```bash
pip install -r requirements.txt   # includes torch (uses GPU automatically)
pip install psutil                 # required by scripts/monitor_usage.py
```

PyTorch will detect and use the GPU automatically when CUDA is available.
No extra configuration is needed for single-GPU use.

### 1.3 Configure AWS credentials

```bash
aws configure --profile physionet
# Enter your BDSP access key, secret, and the correct region (us-east-1).
```

Verify access:

```bash
aws s3 ls s3://bdsp-prd-ohif/ --profile physionet --no-sign-request 2>/dev/null \
  || aws s3 ls s3://bdsp-prd-ohif/ --profile physionet
```

---

## 2. Config for a full run

Edit `config.yaml` before launching.  Key fields:

| Field | Value for full overnight run |
|---|---|
| `phase` | `1` |
| `sites.train` | list all HEEDB hospital site IDs for Phase 1 |
| `sites.held_out` | the single confirmation site (NEVER used in Phase 1) |
| `data.heedb.max_duration_s` | `null` (no per-recording cap) |
| `data.heedb.tasks` | `["Routine", "LTM", "EMU"]` |
| `embedding.max_windows_per_recording` | `40` (speed cap; keep for overnight) |
| `data.s3.bucket` | your BDSP bucket name |
| `seeds.global_seed` | fixed (e.g. `42`) |

Example snippet:

```yaml
phase: 1
sites:
  train: [MGH, BWH, NMC]     # adjust to your actual site IDs
  held_out: BIDMC             # NEVER unlocked during Phase 1

data:
  heedb:
    max_duration_s: null
    tasks: ["Routine", "LTM", "EMU"]
  s3:
    bucket: bdsp-prd-ohif

embedding:
  max_windows_per_recording: 40

seeds:
  global_seed: 42
```

Run a quick preflight check to catch credential / config problems before committing to the overnight run:

```bash
python3 cli.py preflight
```

---

## 3. Launch the overnight run

```bash
chmod +x scripts/run_parallel.sh

AWS_PROFILE=physionet OUT=artifacts ./scripts/run_parallel.sh 16
```

This command:

1. Creates `artifacts/logs/`.
2. Starts `scripts/monitor_usage.py` in the background (writes to `artifacts/logs/monitor.log`).
3. Launches 16 shard workers (`scripts/run_shard.py --shard K --num-shards 16`) in the background, each logging to `artifacts/logs/shard_KK.log`.
4. Waits for all workers to finish, then writes `artifacts/STOP_MONITOR` and prints a final summary.

**The run is resumable.**  If it is interrupted, re-run the same command and workers will pick up where they left off (each shard skips recording IDs already listed in `artifacts/pass1_done_wKK.txt`).

---

## 4. Monitoring while it runs

### 4.1 Watch the live dashboard

```bash
tail -f artifacts/logs/monitor.log
```

The dashboard refreshes every 30 seconds and shows:

| Field | Meaning |
|---|---|
| `CPU %` / `load(1/5)` | Host CPU utilisation and 1-/5-min load averages |
| `RAM` | Used / total GB and percent |
| `Disk/out` | Space on the filesystem holding `artifacts/` |
| `Disk/tmp` | Space on the scratch filesystem (`/tmp/heedb_scratch` by default) |
| `Net IN MB/s` | Network bytes received per second — proxy for S3 download rate |
| `GPU util / mem` | Per-GPU utilisation % and VRAM used/total (from `nvidia-smi`) |
| `Workers` | Live `run_shard.py` processes / expected count |
| `rows` | Total embedding records written so far |
| `completed` | Total recording IDs fully processed (across all `pass1_done_w*.txt`) |
| `rate` | Rows per minute since monitor started |
| `ETA` | Estimated time to finish (only if `--target` was given) |

The same values are also appended as CSV rows to `artifacts/monitor.log` for
post-run analysis.

### 4.2 Watch an individual worker

```bash
tail -f artifacts/logs/shard_00.log
```

Each shard log shows per-recording progress, skip messages for already-done IDs,
and any per-recording errors.

---

## 5. Disk layout and space planning

Raw EDFs are streamed to the scratch directory and **deleted immediately after
embedding**.  Only compact tables persist:

```
artifacts/
  embeddings/    part-wKK-NNNNNN.{jsonl|parquet}   # ~1-3 GB total for full HEEDB
  features/      part-wKK-NNNNNN.{jsonl|parquet}
  qc/            part-wKK-NNNNNN.{jsonl|parquet}
  pass1_done_wKK.txt                                # completed recording IDs
  logs/          monitor.log  shard_00.log ...
  monitor.log                                        # CSV resource log
```

**Scratch space requirement:** at least `NUM_WORKERS x 1.5 GB` free on the
scratch filesystem (the largest single HEEDB EDF is ~1.5 GB; each worker holds
at most one EDF at a time).  With 16 workers, budget ~25 GB of scratch.

If scratch fills up during the run, lower `NUM_WORKERS` (re-run with a smaller
number; the remaining shards will resume automatically).

---

## 6. What to watch for

- **GPU utilisation** should spike to 80-100% during embedding bursts and drop
  between recordings (data loading is the bottleneck between bursts).  Sustained
  low GPU util suggests a bottleneck in S3 download or harmonisation.
- **Net IN MB/s** is the S3 download rate proxy.  Expect 10-50 MB/s per worker
  depending on network and EDF size; 16 workers can saturate a 1 Gbit link.
- **Disk/tmp** — watch this column.  If it approaches 0 GB free, lower
  `NUM_WORKERS` to reduce concurrent scratch usage.
- **Workers alive** should equal `NUM_WORKERS` until shards begin to drain
  (small shards finish first).  If a worker exits early, check its log:
  `tail -100 artifacts/logs/shard_KK.log`.
- **rows vs completed** — `rows` counts embedding records (can be many per
  recording if windowed); `completed` counts full recordings.  Both should
  increase monotonically.  A large gap between the two is normal.

---

## 7. After the run finishes

### 7.1 Run Phase-1 analysis

```bash
python3 cli.py phase1 --tables artifacts
```

This reads the compact tables, applies site correction, runs the clustering and
phenotype characterisation, and writes phase-1 outputs (phenotype assignments,
QC reports).

### 7.2 Freeze and move to Phase 2

Once Phase-1 outputs are reviewed and the pre-registered primary phenotype is
confirmed:

```bash
python3 cli.py freeze --tables artifacts
python3 cli.py phase2 --tables artifacts
```

See `docs/RUNBOOK.md` for the full freeze/phase2 protocol and
`docs/HANDOFF.md` for continuing in a new session.

---

## 8. Quick reference

| Task | Command |
|---|---|
| Full overnight launch | `AWS_PROFILE=physionet OUT=artifacts ./scripts/run_parallel.sh 16` |
| Resume interrupted run | Same command — safe to re-run |
| Watch dashboard | `tail -f artifacts/logs/monitor.log` |
| Watch one worker | `tail -f artifacts/logs/shard_00.log` |
| Stop monitor manually | `touch artifacts/STOP_MONITOR` |
| Run Phase-1 analysis | `python3 cli.py phase1 --tables artifacts` |
| Preflight check | `python3 cli.py preflight` |
