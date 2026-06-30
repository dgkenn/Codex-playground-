# HEEDB / BDSP access — UNLOCKED (operational note, no PII)

## Status: credentials valid, pipeline preflight GREEN
The BDSP credentialed S3 access point is reachable and the repo pipeline is ready to run.

### The fix (root cause of the earlier "invalid keys" failures)
The environment had **invalid `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env vars** that **shadowed the
valid `[physionet]` profile** in `~/.aws/credentials` (boto3's chain puts env vars ahead of named profiles).
Fix: unset the env keys and use the profile, e.g.:
```bash
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN AWS_PROFILE=physionet python3 cli.py preflight
```
→ `READY: critical checks passed — safe to run pass1` (STS account 281627750420; access point reachable).

The only non-critical flag: `config.yaml::data.s3.catalog_key = "HEEDB/index.tsv"` is stale (404). The real
catalog lives under `EEG/eeg-metadata/<SITE>_eeg_metadata_*.csv` (per-site recording→patient index).

## The dataset (confirmed structure — this is the high-impact cohort)
BDSP access point top level: `ECG/ EEG/ EHR/ Imaging/ NAX/ OMOP/ PSG/ PatientMergeHistory/`. Relevant:
- **`EEG/`** — HEEDB EEG signals (BIDS format; `EEG/bids/`), per-session cEEG/LTM (hours–days long).
- **`EEG/eeg-metadata/<SITE>_eeg_metadata_*.csv`** — recording catalog: SiteID, BDSPPatientID, BidsFolder,
  SessionID, DurationInSeconds, ServiceName (cEEG/LTM), annotations flags, **DateOfDeath**.
- **`EEG/HEEDB_Metadata/`**:
  - `HEEDB_patients.csv` — master table: SiteID, BDSPPatientID, Sex, Age, Race, VisitCount, **HasEEG**,
    HasReports, MatchedEEGReports, **ICD10Count**, MedicationCount.
  - `HEEDB_ICD10_for_Neurology.csv` — per-patient neurology ICD-10 outcomes (Behavioral/Cognitive
    Syndromes [⊇ delirium/encephalopathy], Cerebrovascular, Degeneration, Cranial-nerve, …).
  - `<SITE>_EEG_reports_findings.csv` — EEG read labels (normal/abnormal/spikes/spindles/…).
  - `HEEDB_Medication_ATC.csv` — medications (ATC).
- **`EHR/<SITE>-EHR/`, `OMOP/<SITE>-OMOP/` + `OMOP/Merged/`** — full clinical records / OMOP CDM outcomes.
- **Multi-site** (S0001, S0002, I0001–I0009…) → built-in **cross-site external validation** (the repo's
  pre-registered hospital-split design).

## The high-impact, novel, validatable finding this enables
Per the gap survey (ANESTHESIA_RESEARCH_GAPS.md): **no EEG foundation model has been applied to clinical/
neuro outcome prediction anywhere (as of 2026); DELPHI-EEG is single-center with no external validation.**
HEEDB enables: **frozen EEG-foundation-model (CBraMod/MORGOTH) embeddings → neuro/clinical outcome
(cognitive-behavioral syndrome incl. delirium/encephalopathy; mortality via DateOfDeath; abnormal-EEG),
with cross-SITE external validation** — clearing a bar nothing in the literature has. This is the repo's
actual design and the genuine white space.

## BLOCKER (needs user authorization)
Pulling the HEEDB metadata/EEG to run the study moves **regulated credentialed PII (DUA)** locally; the
harness auto-mode classifier blocks this pending explicit user authorization. To proceed the user must
authorize PII handling (allow the data-movement, or run outside auto mode). No PII has been downloaded.

## Immediate next steps once authorized
1. Fix `catalog_key` → `EEG/eeg-metadata/` (or set per-site catalog list).
2. Pull metadata, size the EEG∩outcome cohort per site, pick the primary outcome (cognitive/behavioral
   syndrome) + a hard secondary (mortality), pre-specify the hospital split.
3. Run `pass1` (stream EDF → harmonize → CBraMod embed) on a pilot site, then phenotype → outcome with
   cross-site validation. Red-team to publication.
