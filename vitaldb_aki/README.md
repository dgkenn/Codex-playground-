# VitalDB Postoperative-AKI study (PK-informed, incremental-value)

Implementation of `VitalDB_AKI_PK_incremental_prediction_protocol.md` (v1.0):
pharmacokinetically-informed multimodal prediction of KDIGO postoperative AKI on
VitalDB, evaluated by **incremental value** (not by chasing SOTA AUROC).

VitalDB is **open data** (no credentials, no DUA), so this runs end-to-end from a
plain network connection — unlike the credentialed HEEDB study in this repo.

## Status

| Stage | Protocol §| State |
|-------|-----------|-------|
| **1. Cohort + KDIGO labeling** | §5, §6 | ✅ built, tested, **run on real data** |
| 2. Feature taxonomy (preop + intraop) | §7 | ⬜ next |
| 3. PK / drug-exposure features (Eleveld/Minto/MAC-hours, exposure integrals) | §8 | ⬜ |
| 4. Nested models + incremental-value harness (ΔAUROC/NRI/IDI, nested CV) | §9, §12 | ⬜ |
| 5. Leakage & negative-control battery | §11 | ⬜ |
| 6. Deep-learning waveform arm | §9F | ⬜ |
| 7. External validation (INSPIRE — transferable components only) | §13 | ⬜ |

## Stage 1 result (real VitalDB, KDIGO creatinine criteria)

```
6,388 cases → 5,808 eligible → 3,924 labelable → 143 AKI (3.64%)
KDIGO stages: 1→103, 2→20, 3→20   |   3,748 unique patients
Selection bias confirmed (§5): labelable older (60.6 vs 54.2 y), sicker (ASA 1.9 vs 1.63)
```

143 events is the binding constraint: events-per-variable is tight, which is
exactly why §10's safeguards (nested CV, regularization, "deep learning must earn
its place") are non-negotiable. The cohort matches the protocol's expected
~3,600–5,500 labelable / small-event-count regime.

## Run it

```bash
python vitaldb_aki/cli.py cohort            # build the labelable cohort (caches /cases + /labs)
python vitaldb_aki/cli.py cohort --refresh  # re-pull from the API
python -m unittest vitaldb_aki.tests.test_labeling -v   # KDIGO + eligibility unit tests
```

Outputs (git-ignored, derived): `cache/cohort.csv`, `cache/cohort_summary.json`.

## Design principles (shared with the EEG study in this repo)

- **Config-driven.** All KDIGO windows, eligibility thresholds, splits, and seeds
  live in `config.yaml`; nothing result-changing lives in code.
- **Hash everything.** `cohort_hash` / `config_hash` via `common/hashing`
  (canonical JSON) so the cohort and splits are reproducible (§14).
- **Leakage firewall.** Prediction cutoff = end of surgery (`opend`); no
  postoperative-timed value may become a feature (§11). The label may use postop
  creatinine by definition; features may not.
- **Stdlib core.** Cohort/labeling import only the standard library, so the
  integrity logic tests with no scientific stack.
```
