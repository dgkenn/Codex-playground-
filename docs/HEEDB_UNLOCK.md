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

## PIPELINE VALIDATED END-TO-END ON REAL DATA (the repo's previously-unvalidated step)
- **Weights:** `weighting666/CBraMod/pretrained_weights.pth` (19.8 MB) downloaded; **sha256 matches the
  pinned hash exactly**.
- **Model load:** loads into `braindecode.models.CBraMod` with **0 missing / 0 unexpected keys**
  (architecture matches the checkpoint).
- **Forward pass:** real HEEDB EDF (I0002, 50ch/256Hz/211s) → mne read → all 19 ten-twenty channels
  matched → resample 200 Hz → 30 s window → CBraMod encoder → **400-dim pooled embedding** (mean+std),
  all finite. ~0.1–3.9 s per 30 s window on CPU.
- **Implication:** the full `stream_fetch → harmonize → embed` path works on real data + verified weights.
  Compute scale is the only remaining constraint (CPU = pilot of hundreds; full 48k cohort needs GPU).

## Immediate next steps once authorized
1. Fix `catalog_key` → `EEG/eeg-metadata/` (or set per-site catalog list).
2. Pull metadata, size the EEG∩outcome cohort per site, pick the primary outcome (cognitive/behavioral
   syndrome) + a hard secondary (mortality), pre-specify the hospital split.
3. Run `pass1` (stream EDF → harmonize → CBraMod embed) on a pilot site, then phenotype → outcome with
   cross-site validation. Red-team to publication.

## First cross-site pilot (executed, CPU) — NULL, with a clear diagnosis
**Setup:** frozen CBraMod embedding (3×30 s windows, 400-dim) of routine EEGs, linear probe, outcome =
Seizure-Disorder ICD; train one site / test the other. Sites I0002 (n=68) and S0001 (n=70), balanced 35/35.
**Result:** cross-site AUC 0.47 (I0002→S0001) and 0.41 (S0001→I0002) — **at/below chance; no transportable signal.**

**Diagnosis (why, and the fix):**
1. **Label–signal mismatch (most likely):** a *seizure-disorder diagnosis* ≠ ictal EEG. Most epilepsy
   patients have a **normal interictal EEG**; 3 short windows of a routine recording rarely show seizure
   activity. The outcome is a poor target for short-window embeddings.
2. **Better-matched outcomes** (reflected in *background* EEG that a foundation model captures): the EEG
   **report normal/abnormal** label, **encephalopathy / cognitive-behavioral syndrome** (diffuse slowing),
   and **mortality** (background severity). These should be tried before concluding.
3. **Cross-site domain shift** (montage/hardware) may need harmonization/adaptation — test by checking the
   normal/abnormal-EEG label cross-site (if that transports, the pipeline is sound and seizure was the wrong label).
4. **Method:** frozen embedding + linear probe + 90 s of EEG is the weakest possible version; the real study
   uses whole-recording pooling, more windows, fine-tuning, and GPU scale (48k cohort).

**Status:** infrastructure + pipeline fully validated; first finding attempt is an honest null due to outcome
choice. Next: re-target to EEG-reflected outcomes (abnormal-EEG / encephalopathy / mortality) at GPU scale.
