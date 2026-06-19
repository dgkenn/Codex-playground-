# RUNBOOK — running the pipeline on real HEEDB data (BDSP)

This pipeline cannot run on real HEEDB data from an ephemeral cloud container:
BDSP is **credentialed clinical data** behind an S3 access point that requires
*your own* AWS credentials, a signed DUA, and CITI training. Run it in **your
approved, credentialed compute environment** (a workstation or VM under your
control whose AWS account is registered with BDSP). Raw waveforms are streamed
and deleted per recording (Sec 0); only the compact tables (~1–3 GB) persist.

## 0. One-time access prerequisites (bdsp.io/about/howto_accessdata)
1. Create/identify an **AWS account**; note its 12-digit Account ID.
2. Register that Account ID in the **BDSP Cloud Credentials dashboard**.
3. Sign the **project-specific DUA** for HEEDB.
4. Complete **CITI "Data or Specimens-Only Research"** training; upload the cert.
5. From the dashboard, get your **access-point alias**
   (e.g. `bdsp-credentialed-ac-…-s3alias`).

## 1. Environment
```bash
git clone <this repo> && cd Codex-playground-
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # includes boto3 + mne
pip install torch braindecode huggingface_hub   # for the CBraMod forward pass
aws configure                            # your BDSP-registered AWS keys + us-east-1
aws s3 ls s3://<YOUR-ACCESS-POINT-ALIAS>/   # sanity: you can list the data
```
Credentials live only in your AWS config / environment — **never** in this repo.

## 2. Pin the two runtime values in `config.yaml`
- `model.checkpoint_sha256`: download the CBraMod checkpoint once and record its
  SHA-256 (the loader verifies it before Pass 1).
- `data.s3.access_point`: set to **your** access-point alias (or keep the shared
  ARN — both work with your keys). Confirm `catalog_key` / `catalog_columns`
  against the real bucket layout (the defaults are a documented guess — verify
  with `aws s3 ls` and adjust the column map; these feed only acquisition
  metadata, never an outcome).

## 3. Phase 1 — discovery (no outcome, no held-out site)
```bash
python cli.py validate                   # config invariants
python cli.py pass1 --limit 500          # stream -> harmonize -> embed -> features
                                         #   PILOT cap of 500 recordings (resumable);
                                         #   --limit 0 = full run (durable compute only)
python cli.py phase1 --tables artifacts  # correct -> gate -> cluster -> bar -> report
```
Start with the 500-recording pilot to validate the real path end to end (this
environment is ephemeral); scale up `--limit` (or set `execution.max_recordings:
null`) only on durable compute. Pass 1 is resumable — re-running continues where
it left off and already-done recordings don't count against the limit.
Inspect `artifacts/phase1_report.json`: the site-probe gate must pass, the
phenotype bar lists **provisional** phenotypes, and the negative-control says the
structure is real. The held-out hospital (`sites.held_out`) is hard-blocked
throughout — a `FirewallBreach` is raised if any code tries to load it.

## 4. Freeze (Phase-1 close) — before any outcome is touched
```bash
# Pin phase2.primary_phenotype in config.yaml to the phenotype matching the
# mechanistic prior (named from the Phase-1 report, BEFORE unlock), then:
python cli.py freeze                     # hashes the 4 objects -> frozen manifest
```
This stamps the frozen-pipeline hash. Register it on OSF before Phase 2.

## 5. Phase 2 — confirmation (single test, run once)
Set `phase: 2` in `config.yaml`. Produce the held-out compact tables by running
Pass 1 over the held-out hospital with the **frozen** harmonization config, and
build `outcome.json` from your Phase-2-only outcome loader (must guarantee EEG
precedes the outcome per patient):
```json
{ "outcome": [0,1,0,...], "covariates": {"age":[...],"sex":[...],"care_setting":[...]},
  "temporal_precedence_verified": true }
```
```bash
python cli.py phase2 --tables artifacts_heldout/ --outcome outcome.json
```
The CLI verifies the frozen-pipeline hash, re-verifies each frozen object,
unlocks the held-out site (logged), runs the cross-site reproducibility check
(provisional → confirmed), and — only if confirmed — runs the single adjusted-OR
test once, with a shuffled-outcome leakage control. The run-once lock prevents a
second test.

## 6. Governance
Archive `artifacts/frozen/manifest.json`, the compact tables, and the logs under
`artifacts/logs/`. Log every deviation. External replication (TUH) is the next
step and is out of scope here (Sec 15).

## 7. External replication — TUH EEG Corpus (Sec 15, optional, after publication)
TUH is a **different health system** and is **not** part of the HEEDB
discovery/held-out split. It is the gold-standard external check: a HEEDB finding
is a hypothesis until it replicates on TUH. Run this only after the frozen
pipeline and Phase-2 result are registered.

```bash
# One-time (per NEDC email): generate a key, email the .pub to help@nedcdata.org
ssh-keygen -t ed25519 -C "you@institution.edu"      # defaults; key at ~/.ssh/id_ed25519
sudo apt-get install -y rsync openssh-client         # if absent

# Verify access with NEDC's TEST probe (wraps the exact documented rsync):
python cli.py tuh-test
#   -> runs: rsync -auvxL -e "ssh -i ~/.ssh/id_ed25519 ..." \
#            nedc-tuh-eeg@www.isip.piconepress.com:data/tuh_eeg/TEST <scratch>
```
Then in `config.yaml` set `external_replication.enabled: true`, point
`external_replication.tuh.manifest` at a local TSV of EDF paths (+ acquisition
metadata) built from the corpus listing
(isip.piconepress.com/projects/nedc/html/tuh_eeg/), and run the frozen
harmonize→embed→assign pipeline over TUH as its own corpus — comparing the
phenotype structure and the outcome association to the HEEDB result. Per NEDC,
**delete the data when done** (the transport already deletes each EDF after use).

---
### What is wired vs. what you must confirm
- **Wired & tested:** S3 catalog → `RecordingRef` mapping, firewall filtering,
  the whole analysis/freeze/confirm chain (`python cli.py demo` runs it all on
  synthetic data).
- **Confirm on first real run:** the BDSP catalog key/columns (`data.s3`), the
  CBraMod construction/reshape against real weights (implemented against the
  published braindecode interface, not yet validated on hardware), and the exact
  HEEDB minor version.
