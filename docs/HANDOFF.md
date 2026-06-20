# HANDOFF — continuing this project in a new (desktop) Claude Code session

This documents the project state and how to take over, especially in **Claude
Code desktop** running on your own machine — which is the right place for the
live run (your machine has your AWS credentials, your NEDC SSH key, and
unrestricted network, so even TUH works).

## Current state
- Branch: **`claude/heedb-eeg-phenotype-discovery-2mnwzx`** (all work pushed).
- **126 tests green.** The stdlib-only integrity core runs with no dependencies;
  the rest skip unless the scientific stack is installed.
- The full lifecycle runs end-to-end on synthetic data: `python cli.py demo`.
- Four data transports are wired and tested:
  - `HEEDBBDSPClient` — real HEEDB over the BDSP access point (catalog + BIDS EDFs).
  - `BDSPS3Client` — generic BDSP S3 access point (boto3).
  - `TUHRsyncClient` — TUH external replication over rsync/SSH.
  - `LocalEDFClient` — a local directory of EDF files (no credentials).
- Firewall + run-once + hashing hardened after an adversarial audit.

### Real-data status (VALIDATED on live BDSP)
The pipeline ran **end to end on real HEEDB data** from the credentialed BDSP S3
access point:
- `HEEDBBDSPClient` reads the real `EEG/eeg-metadata/{site}_*.csv` catalogs and
  streams real BIDS EDFs (validated: real 256 Hz, 50-channel routine EEGs).
- The **frozen CBraMod** model runs for real: `weighting666/CBraMod`
  `pretrained_weights.pth` loads with `weights_only=True` (no pickle exec), matches
  the architecture exactly, yields 400-d pooled embeddings; sha256 pinned + verified.
- A real pilot completed: real EDFs → mne harmonize → real CBraMod embed → real
  features → tables → Phase-1, no errors. Reproduce/scale with
  `AWS_PROFILE=physionet python scripts/run_real_pilot.py`
  (env `PILOT_PER_SITE`, `PILOT_MAX_DURATION`).

**Known gaps for the registered run (not pilot blockers):**
1. **SiteID ↔ hospital mapping** — bucket uses de-identified `S0001/S0002/I0002/
   I0003/I0009`; `config.yaml::sites` holds pilot values flagged TO-CONFIRM. Map
   to MGH/BWH/BIDMC/BCH and set discovery/held-out per protocol.
2. **Adults-only eligibility** — the catalog's `AgeAtVisit` is largely empty, so
   the ≥18 filter can't be applied from it. The real run must join
   `EEG/HEEDB_Metadata/HEEDB_patients.csv` (`AgeAtVisitAvg`, `Sex`) on patient id;
   wire this into `HEEDBBDSPClient`.
3. **Scale + compute** — CBraMod CPU inference is slow; a full discovery run wants
   a GPU. This ephemeral container is for pilots only.

## Take over in Claude Code desktop
1. Clone and check out the branch:
   ```bash
   git clone https://github.com/dgkenn/Codex-playground-.git
   cd Codex-playground- && git checkout claude/heedb-eeg-phenotype-discovery-2mnwzx
   ```
2. Open the folder in Claude Code desktop. `CLAUDE.md` auto-orients the session.
3. Sanity check (no creds needed):
   ```bash
   make test-integrity      # fast, stdlib only
   python cli.py demo       # full synthetic lifecycle
   ```
4. Install the run deps:
   ```bash
   pip install -r requirements.txt
   pip install torch braindecode huggingface_hub   # CBraMod forward pass
   ```

## Run on live data (desktop is ideal)
On your own machine you do NOT need the cloud env-var/network config; you use
your local credentials directly.

**HEEDB / BDSP (Harvard):**
```bash
aws configure                 # your BDSP-registered AWS keys + us-east-1
python cli.py preflight       # deps + AWS identity + S3 reach + catalog + checkpoint
python cli.py validate
python cli.py pass1 --limit 500    # pilot; --limit 0 = full run (resumable)
python cli.py phase1 --tables artifacts
# review artifacts/phase1_report.json; pin phase2.primary_phenotype; register OSF
python cli.py freeze
# (phase: 2; build held-out tables + outcome.json) then:
python cli.py phase2 --tables artifacts_heldout/ --outcome outcome.json
```

**TUH (external replication, after publication):** works on desktop because SSH
egress is available there (it is blocked in the cloud sandbox).
```bash
ssh-keygen -t ed25519 -C "you@institution.edu"   # email .pub to help@nedcdata.org
python cli.py tuh-test        # NEDC TEST-file probe
# set external_replication.enabled: true + manifest, then run the frozen pipeline on TUH
```

## What still needs an input (independent of credentials)
1. **BDSP catalog schema** — set `config.yaml::data.s3.catalog_key`,
   `catalog_format`, `catalog_columns` to the real bucket layout (or ask Claude
   to list the access point and infer it). These feed acquisition metadata only.
2. **`model.checkpoint_sha256`** — pinned automatically when Claude downloads the
   CBraMod checkpoint (the loader verifies it).
3. **`phase2.primary_phenotype`** — named from the Phase-1 report, before unlock.
4. **CBraMod construction/reshape** — validate on first real Pass 1 (implemented
   against the published braindecode interface, not yet run on real weights).

## Suggested first prompt to the desktop session
> Read CLAUDE.md and docs/HANDOFF.md. Run `make test-integrity` and
> `python cli.py demo` to confirm the pipeline is healthy. Then I'll run
> `aws configure`; after that, run `python cli.py preflight` and walk me through
> the BDSP pilot.

## Reference docs
- `docs/RUNBOOK.md` — full real-data procedure + governance.
- `docs/GO_LIVE.md` — config for the *cloud* web environment (not needed on desktop).
- `docs/SPEC_TRACEABILITY.md` — every binding rule → enforcing code → test.
- `CLAUDE.md` — repo conventions and map.
