# CLAUDE.md — guide for Claude Code sessions in this repo

## What this project is
Implementation of a **pre-registered, two-phase, unsupervised EEG phenotype
discovery study** on HEEDB (Harvard EEG Database) using an adapted frozen
foundation model (**MORGOTH 1.0**, the HEEDB-pretrained clinical-EEG model;
CBraMod/LaBraM/EEGPT/BIOT are secondary alternatives), with hospital-split
confirmation and external replication on TUH. The canonical protocol is
`HEEDB_rawSSL_phenotype_discovery_preregistration_v3.md`; the section→code→test
map is `docs/SPEC_TRACEABILITY.md`.

NOTE: the protocol is at **v3** (MORGOTH backbone + redundancy/novelty control +
non-circular Phase-2 outcome). The CODE still reflects v2 (CBraMod, seizure
outcome) — see that file's changelog; the backbone/outcome code ripple is a
pending follow-up, not yet applied.

**Binding integrity principle (do not weaken):** Phase 1 (discovery) uses **no
outcome label**. Phase 2 tests **one** pre-registered outcome on a **held-out
hospital never touched in Phase 1**, with four objects (model checkpoint,
harmonization config, embedding-correction transform, phenotype-assignment
function) **frozen + hash-verified** before the held-out data is unlocked. Any
breach voids confirmatory status.

## Repo map (this project)
```
config.yaml            single source of truth (PHASE flag, seeds, sites, params, data.s3, TUH)
cli.py                 entry point: validate | preflight | pass1 | phase1 | freeze | phase2 | tuh-test | demo
common/                hashing, config validation, audit log   (stdlib only)
guards/heldout_guard.py the firewall (blocks held-out while phase==1; hash-stamped unlock)
pipeline/              Pass 1: stream_fetch (BDSPS3Client / TUHRsyncClient / LocalEDFClient),
                       harmonize, embed (CBraMod), features (DSP), writer, run_pass1
analysis/              correct_sites, site_probe (gate), cluster, phenotype_bar, characterize,
                       audits, run_phase1 (orchestrator)
phase2/                freeze (4 objects) -> run_phase2 (unlock -> cross-site -> single run-once test)
demo/synthetic.py      full synthetic lifecycle (no creds/model) -> `python cli.py demo`
tests/                 test_integrity (stdlib) + analysis/e2e/DSP/transport (skip w/o sci stack)
docs/                  SPEC_TRACEABILITY, RUNBOOK (real data), GO_LIVE, HANDOFF
scripts/setup_cloud.sh setup script for the cloud env
```

## NOT part of this project (leftover playground; do not touch)
`health_check.py`, the `test` stub file, and the trading workflows under
`.github/workflows/` (`collect/live/health/kalshi-*/sports-clv/etf-paper/
strategy-*/wallet-track`). Only `.github/workflows/eeg-phenotype-tests.yml` is ours.

## Conventions
- **Heavy deps are lazy.** numpy/scipy/sklearn/mne/torch/boto3 import *inside*
  functions so the integrity core + guards import and test with the stdlib only.
- **Everything is content-hashed.** Use `common/hashing` (canonical JSON,
  `allow_nan=False`). "Frozen" means the hash is recorded and re-verified.
- **Config-driven + deterministic.** All params/seeds in `config.yaml`; nothing
  that can change a result lives in code. `TO-CONFIRM` = must be pinned before
  the relevant stage (checkpoint sha256, primary phenotype, BDSP catalog schema).
- **The firewall is load-bearing.** Route every site label through
  `HeldoutGuard.check_site_access`; never add an outcome-bearing column to a
  Phase-1 loader (`assert_no_outcome_in_loader_fields` enforces this).

## Commands
```bash
make test-integrity      # stdlib-only firewall/hashing/guard tests (fast, no deps)
make test                # full suite (needs numpy/scipy/sklearn/statsmodels/mne)
python cli.py demo       # full synthetic lifecycle end-to-end
python cli.py preflight  # check creds/network/deps before a live run
```
106 tests green. Branch: `claude/heedb-eeg-phenotype-discovery-2mnwzx`.

## Running on real data
See `docs/RUNBOOK.md` (full procedure) and `docs/HANDOFF.md` (continuing in a new
desktop session). Real HEEDB/TUH access is credentialed (the user's own AWS keys
/ NEDC SSH key) and is supplied at runtime — never committed. The CBraMod
forward pass is implemented against the published braindecode interface but is
**not yet validated on real weights**; validate on first real Pass 1.
