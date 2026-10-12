# Taking over the E248 extraction, and making it fast on your own machine

*Paused 2026-08-04 at 35,988 of 56,731 windows. Everything below is measured on the sandbox unless
marked as a projection.*

---

## 1. Exactly where it stopped

| | |
|---|---|
| windows written | **35,988** of 56,731 (63 %) |
| of those, `status=ok` | **35,679** |
| `status=error` | **305** — all legitimate (`window … is entirely NaN (device disconnected)`), **not** network failures |
| distinct cases touched | 1,654 of 2,608 |
| shards | `vitaldb_ventwin.s0…s3.csv`, 8,821–9,128 rows each, all ending on a complete line |
| remaining | ~954 cases, ~20,700 windows |

All four shards are committed and pushed on branch `research`. Nothing is lost.

**Why the error rows don't matter here.** `stream_features` builds its resume set from *every* existing
`recording_id` regardless of status, so error rows are treated as done and never retried. That would be a
problem if they were transient network failures — they aren't. Every one is a window where the BIS strip
was disconnected and the signal is entirely NaN, which will error identically on any retry.

## 2. Resume it unchanged — one command

```bash
git clone -b research https://github.com/dgkenn/Codex-playground-.git
cd Codex-playground- && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e 'bsde[io,dev]'

for k in 0 1 2 3; do
  python3 bsde/scripts/stream_vitaldb_transitions.py \
    --plan bsde/results/vitaldb_ventwin_plan.json \
    --out bsde/results/vitaldb_ventwin.s$k.csv --case-shard $k --of 4 &
done; wait
```

It picks up from row 35,988. **Do not change `--of` on a resume of these four files** — the shard
assignment is `index % of == shard`, so a different `--of` reshuffles which case belongs to which shard
and the four existing files would no longer cover a clean partition. To change the shard count, see §3.1.

Then the analysis:

```bash
cd bsde/src
python3 -m bsde.experiments.e248_agent_leakage_at_scale --smoke   # permuted labels, writes no report
python3 -m bsde.experiments.e248_agent_leakage_at_scale
```

## 3. Making it faster — in the order the wins actually rank

**Measure first.** The sandbox ran ~800–1,000 windows/min across 4 shards while the DSP alone can do
~11 windows/sec/shard. So the job is **~10× network-bound** and every optimisation below targets I/O, not
compute. Re-measure on your box before assuming the same ratio holds.

### 3.1 More shards — the immediate win, and the only one that needs no code change

Each shard is one process doing *fetch → DSP → fetch* serially, so it is idle most of the time. Four
shards saturated roughly 50 Mbit/s on the sandbox. On a 500 Mbit/s home line there is a lot of headroom.

To change the shard count you must start a **fresh output set**, because the partition changes:

```bash
# finish the current 4-shard run first, OR archive it and start clean:
mkdir -p bsde/results/archive && mv bsde/results/vitaldb_ventwin.s?.csv bsde/results/archive/

N=8            # try 8 first, measure, then consider 12-16
for k in $(seq 0 $((N-1))); do
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 bsde/scripts/stream_vitaldb_transitions.py \
    --plan bsde/results/vitaldb_ventwin_plan.json \
    --out bsde/results/ventwin8.s$k.csv --case-shard $k --of $N &
done; wait
```

**`OMP_NUM_THREADS=1` is not optional at high shard counts.** numpy/scipy will each spawn a thread pool
sized to your 16 logical cores; sixteen processes doing that is 256 threads fighting over 8 physical
cores. Pinning each process to one BLAS thread is usually worth more than the extra shards themselves.

**Measure, don't guess** — run each setting for two minutes and count:

```bash
before=$(cat bsde/results/ventwin8.s*.csv | wc -l); sleep 120
echo "$(( ($(cat bsde/results/ventwin8.s*.csv | wc -l) - before) / 2 )) windows/min"
```

**Be a good citizen.** `api.vitaldb.net` is a free public resource with no rate-limit documentation. If
you see errors climb or throughput stop improving, you have found their limit, not yours — back off. 16
concurrent fetchers is a reasonable ceiling to respect regardless of what your line can do.

### 3.2 Cache the raw tracks — the change that alters how you work

**This is the biggest win available to you and the sandbox could not do it** (it had ~20 GB free).

Right now every feature extraction re-downloads all 5,870 EEG tracks. `VitalDBTargetedAdapter._series`
caches exactly **one** track in memory and `_fetch` has no disk cache at all, so any change to the window
grid, the offsets or the candidate panel means another full ~55 GB pass and another ~70 minutes.

With ~55 GB of disk you cache once and every subsequent extraction is pure CPU:

- fetch-bound today: **~70 min** for 56,731 windows
- CPU-bound after caching: 11.3 windows/sec/shard × 8 shards ≈ 90/s ⇒ **~10 min**, and no network at all
  *(projection from the measured per-shard DSP rate, not yet measured end-to-end)*

That turns "try a different window grid" from a two-hour decision into a coffee break, which matters far
more than the one-off speedup. The change is small — a content-addressed disk cache keyed by `tid` in
`bsde/src/bsde/ingestion/vitaldb.py::_fetch`, with the cache directory read from an env var so it never
lands in the repo.

### 3.3 Reuse HTTP connections — small, cheap, do it while you're in there

`_fetch` calls `urllib.request.urlopen` per request, so every track pays a fresh TCP + TLS handshake.
Across ~2,600 cases × 2–3 fetches that is thousands of handshakes. A `requests.Session` or a
`urllib3.PoolManager` held per process removes them. Worth maybe a few minutes on the waveform pass — but
much more on the *numeric* probes (`vitaldb_ventilation_probe.py`, `vitaldb_mac_landmark_probe.py`), where
fetches are small and handshake cost dominates transfer.

### 3.4 Overlap fetch and DSP — only after the above

A prefetch thread per shard hides DSP time behind the next download. Since DSP is ~10× faster than the
fetch, the ceiling is ~10 %. Not worth the complexity until §3.1–3.3 are done and re-measured.

### 3.5 Drop the sandbox scaffolding

- **`scripts/checkpoint_loop.sh` is unnecessary locally.** It exists because this container rolled the
  working tree and `.git` back to a fixed old commit **five times** on 2026-08-04, killing every
  background job. (It earned its keep: the last rollback took the tree back to a commit at 26,127 rows
  while the loop had already pushed 35,988.) Keep committing at artifact boundaries — that's good
  practice — but you don't need a timer.
- **`scripts/heedb_run.sh`** works around a placeholder-AWS-credential injection that only exists here.
- Point caches at durable paths. Nothing needs to live in `/tmp` on your machine.

## 4. What NOT to change

- **Don't touch the resume/append/fsync logic** in `bsde/src/bsde/ingestion/runner.py::stream_features`.
  Every extraction in this project depends on it, and a partial write that isn't fsynced is how you get a
  torn row that poisons a shard silently.
- **Don't run two writers on one CSV** (catalogue rule 56). It produced 931 rows where 710 were expected
  and 419 duplicated `recording_id`s once already. One process per output file, always.
- **Don't change the window grid to speed things up.** The 21 fixed offsets are load-bearing: E154 found
  recording duration identifies the anaesthetic agent at |AUC−0.5| = 0.3771, above every candidate, and a
  fixed window count is what keeps case length out of the summary. This is registered in E248.
