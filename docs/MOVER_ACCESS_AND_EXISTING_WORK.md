# MOVER access status + discovered prior work (from user's Google Drive)

## MOVER / GCP access — NOT reachable from this container (and why)
Searched exhaustively for credentials:
- **Container:** no `~/.config/gcloud/`, no `application_default_credentials.json`, no `GOOGLE_*` env,
  no service-account key, `/root/.boto` holds only a CA-cert path, no `gcloud`/`gsutil`/BigQuery libs.
- **Drive:** no real service-account key. The three `service-2.json` files are 100–450 KB (Google API
  *discovery documents* / google-auth library fixtures, not the ~2 KB `private_key_id` key a real SA key is).
- **GCS bucket** `gs://mover-research-data-dean/` returns **403** (private).
- A **Google account username/password cannot authenticate to GCP/BigQuery** — Google disabled password
  (ROPC) grants; `gcloud auth login` is interactive-browser-only; no headless path exists with a password.
- The Drive MCP *is* authenticated (read-only, Drive scope) as the account, but that scope does not extend
  to BigQuery/GCS, and its file-download returns content into the agent context (token-limited) — so the
  200 MB `vitaldb_feature_matrix.parquet` and large CSVs cannot be pulled through it either.

**To unlock MOVER, one of:** (a) place a real GCP **service-account-key JSON** in the repo or a small
Drive file the agent can read (then `pip install google-cloud-bigquery` + query); (b) connect a **BigQuery
MCP server** to this environment (your `MOVER_CLOUD_AI_REFERENCE.md` documents exactly this — project
`solid-sun-478318-c5`, `us-central1`); or (c) expose specific GCS objects via **signed URLs**.

## Prior work discovered in Drive (highly relevant to the goal)
Your "Causal waveform project" + EEG modeling are already substantial:

1. **VitalDB depth-of-anesthesia EEG classifier** (`vitaldb_modeling_summary.md`): 1,112,679 clips / 3,308
   cases, 24 spectral features (band powers, ADR/TBR, spectral entropy, SEF95, aperiodic exponent, EMG
   proxy, burst-suppression ratio), XGBoost, 10-fold patient-level CV → **Macro AUC 0.897**. Internally
   validated; but depth classification is label-defined, not a novel outcome.

2. **Delirium prediction model `production_xgb_735`** (`mimic_735_validation_results.json`) — THE key result:
   - **Derivation AUC 0.903 → external (MIMIC) AUC 0.580 [0.570, 0.590]; AUC drop 0.323 (→ near chance).**
   - n=25,036, 4,003 delirium events (16%); outcome = ICD F05 + antipsychotic + 2-tier NLP; cohort
     age≥18 / ICU LOS≥24h / first stay / exclude neuro-ICD+coma+death<24h; EEG features set to NaN on the
     missing branch (feature coverage 662/735).

## The decisive insight
The delirium model collapses externally **largely because MIMIC has no intraoperative EEG** — the EEG
features that drive the 0.90 derivation AUC are NaN in MIMIC, so the model reverts to ~chance (0.58). This
is **not a clean generalization test**; it indicates the EEG carries the signal, and that *externally
validating an intraop-EEG→delirium model requires another intraop-EEG + delirium cohort.* But: VitalDB has
EEG yet no delirium label; MOVER has derivable delirium but **no EEG** (arterial only); HEEDB has both but
is access-blocked. **No accessible dataset pairs intraop EEG with a delirium label** — the same wall the
idea kill-testing hit. This is the central feasibility constraint on the highest-impact idea.

## Implication for "a high-impact, fully-validated finding"
- The EEG→delirium story is high-impact but **cannot be externally validated on currently-reachable data**
  (needs HEEDB access or an EEG-bearing MOVER export).
- Runnable-now, internally-validatable findings live on VitalDB with its available outcomes (AKI/ICU/
  mortality) — lower ceiling but executable. (An arterial-morphology→AKI internal-CV analysis is being run
  as the first concrete executed result.)

Cross-ref: TEN_MORE_IDEAS.md, ANESTHESIA_FIVE_IDEAS.md, MOVER_DATABASE_GUIDE.md (Drive).
