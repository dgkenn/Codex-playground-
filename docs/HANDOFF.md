# HANDOFF — continuing this project in a new (desktop) Claude Code session

This documents the project state and how to take over, especially in **Claude
Code desktop** running on your own machine — which is the right place for the
live run (your machine has your AWS credentials, your NEDC SSH key, and
unrestricted network, so even TUH works).

## Current state
- Branch: **`claude/heedb-eeg-phenotype-discovery-2mnwzx`** (all work pushed).
- **106 tests green.** The stdlib-only integrity core runs with no dependencies;
  the rest skip unless the scientific stack is installed.
- The full lifecycle runs end-to-end on synthetic data: `python cli.py demo`.
- The real signal path is validated on actual EDF bytes (mne harmonize → real
  band-power/aperiodic/wPLI/entropy/microstate features) via `LocalEDFClient`.
- Three data transports are wired and tested (catalog/command construction):
  - `BDSPS3Client` — HEEDB over the BDSP credentialed S3 access point (boto3).
  - `TUHRsyncClient` — TUH external replication over rsync/SSH.
  - `LocalEDFClient` — a local directory of EDF files (no credentials).
- Firewall + run-once + hashing hardened after an adversarial audit.

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
