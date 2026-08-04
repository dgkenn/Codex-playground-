# Prompt to paste into Claude Code on your own machine

*Two prompts. The first is a one-off to get the machine performing; the second is the standing research
loop, adjusted for local hardware. Paste them verbatim — the specifics are what make them work.*

---

## Prompt 1 — take over and optimise the pipeline (run this first)

```
Read CLAUDE.md top to bottom, then LOCAL_SETUP.md and bsde/docs/EXTRACTION_TAKEOVER.md.

Hardware: AMD Ryzen 7 5700G (8 cores / 16 threads), 16 GB DDR4-3200, Radeon RX 6600 XT
8 GB (unused — nothing here is GPU-bound), NVMe. Linux or WSL2. Tell me the free disk
before you start; the full VitalDB waveform pass needs ~55 GB and caching the raw
tracks needs ~55 GB more.

Goal: resume the paused E248 extraction (35,988 of 56,731 windows done) and make this
machine as fast as it can usefully be, WITHOUT changing any registered design.

Work in this order and MEASURE at each step rather than assuming:

1. Verify the install: `make test-integrity` (expect 31/31) and `pytest bsde/tests -q`
   (expect 472 passed, 2 failed, 6 skipped — both failures are pre-existing and
   documented in LOCAL_SETUP.md §4; do not "fix" them).

2. Establish a baseline. Resume the extraction at the current 4 shards and measure
   windows/min over 2 minutes. Report the number before changing anything.

3. Raise the shard count. Note that changing --of repartitions the cases, so archive
   the existing shards and start a fresh output set rather than mixing partitions.
   Set OMP_NUM_THREADS=1 / OPENBLAS_NUM_THREADS=1 / MKL_NUM_THREADS=1 per process —
   with many shards, BLAS thread oversubscription usually costs more than the extra
   shards gain. Measure at 4, 8 and 16 and give me the three numbers. Stop raising it
   when throughput stops improving or errors climb: api.vitaldb.net is a free public
   resource and that ceiling is theirs, not mine.

4. Add a disk cache for raw VitalDB tracks, keyed by tid, in
   bsde/src/bsde/ingestion/vitaldb.py::_fetch. Cache directory from an env var, never
   inside the repo, and gitignored. This is the change that matters most: it makes
   every FUTURE extraction CPU-bound instead of network-bound, so re-running with a
   different window grid costs minutes instead of two hours. Verify it by re-running a
   small extraction twice and showing the second is much faster and byte-identical.

5. Reuse HTTP connections (requests.Session or urllib3.PoolManager, one per process).
   This matters more for the small numeric probes than the 9.4 MB waveform fetches.

Constraints, all of which are load-bearing:
- Do NOT modify stream_features' resume/append/fsync logic. Everything depends on it.
- Never run two writers on one CSV (catalogue rule 56 — it has already corrupted a
  table in this project).
- Do NOT change the window grid, offsets or candidate panel. They are registered in
  E248 and the fixed window count is what keeps recording length out of the summary.
- Never commit credentials or patient-derived data. This GitHub repo is PUBLIC.

When the extraction finishes, run the E248 analysis --smoke FIRST (it permutes the arm
label and writes no report), then the real run, and show me the verdict with its gates.
```

---

## Prompt 2 — the standing research loop

```
Do all recommended next steps. Continue on all fronts. Consider previous results and
current blockers.

Before investing in a finding, check whether it is already published — search PubMed
via NCBI E-utilities (never WebFetch or WebSearch for a bibliographic record) before
the third experiment on a thread, not after. Write the abstract first. If a line of
work succeeds completely, state the one sentence it would license — and if that
sentence is already true in the literature, or too weak to matter, stop the line.

If stuck, consider combining literature or acquiring new databases, and consider
solutions from other fields and exotic novel solutions you brainstorm yourself. When
approaching a problem, brainstorm many solutions and diagnostics and then run them in
parallel using delegated sonnet or haiku agents. Always check agent output with opus
against the raw source before it becomes a reported number.

Work on each challenge independently and in parallel. State explicitly when a line
should be abandoned, not just what to do next. State explicitly what is blocked on ME
so I can help remove it.

Local hardware: 8 cores / 16 threads, 16 GB RAM, no useful GPU. Extractions are
network-bound, so run them sharded in the background with nohup and poll, and prefer
the cached-track path over re-downloading. You do not need scripts/checkpoint_loop.sh
here — that existed only because the cloud container kept rolling the tree back.
```

---

## Why these two are separate

Prompt 1 is infrastructure and has a definite end state. Prompt 2 is the research loop and never
terminates on its own. Running Prompt 2 before the machine is set up will produce the same behaviour as
the cloud sessions — correct but throttled by a two-hour extraction every time a design changes.

## Two things worth knowing before you start

**Token cost does not change.** `CLAUDE.md`'s standing SOP says this research is token-expensive and has
come close to the weekly cap. Claude Code on your machine calls the same API. The delegation table there
(opus orchestrates and reviews, sonnet red-teams, haiku does mechanical work) is the lever that matters,
not the hardware.

**The GPU will not help.** Everything here is Welch PSDs, Lempel-Ziv, AUCs and permutation nulls — all
CPU-trivial. The only direction that would use a GPU is training a domain-adversarial model to go after
Jeong 2025's approach directly, and for that an 8 GB RDNA2 card on Windows is a poor platform. Don't let
a session talk you into a ROCm detour.
