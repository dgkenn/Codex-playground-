# Multi-site external validation — expanded design (up to 6 databases, 4 countries)

Pending credentialed access to HiRID (CH), SICdb (AT), and AmsterdamUMCdb (NL), the external-validation stack
becomes one of the strongest in the ICU-EHR literature. This is the strategic plan; the technical concept→ID
mappings + adapter skeletons are in `MULTISITE_HARMONIZATION.md` + `{hirid,sicdb,amsterdam}_run.py`.

## The stack
| Database | Country | Setting | Role | Status |
|---|---|---|---|---|
| MIMIC-IV | US (Boston) | ICU + ward | derivation | running |
| eICU-CRD | US (200+ hosp) | ICU | replication #1 | engine built |
| **HiRID** | Switzerland | ICU (high-res) | replication #2 | adapter pending access |
| **SICdb** | Austria | ICU | replication #3 | adapter pending access |
| **AmsterdamUMCdb** | Netherlands | ICU | replication #4 | adapter pending access |
| INSPIRE | Korea | perioperative | supplementary | engine built |

= **4 countries, 3 distinct European health systems, US academic + US multicenter + a floor (ward) cohort +
an Asian perioperative cohort.** For the benchmark analytes (Hb, glucose, platelets, bicarbonate) which are
measured everywhere, this makes "the method recovers the RCT truth across every system we can access" a claim a
reviewer cannot dismiss as site-specific.

## Why this is a top-tier lever (not a checkbox)
- The killer calibration figure gains **one panel per database** — the method should sit on the y=x diagonal
  (recovers RCT truth) in ALL of them while naive scatters toward false harm. Concordance across 4 countries is
  the single most persuasive robustness result in observational causal inference.
- It directly answers the deepest reviewer attack ("confounding-by-indication is unsolvable / site-specific"):
  if the same instrument reproduces TRICC/TRISS/NICE-SUGAR/etc. in Boston, 200 US hospitals, Bern, Salzburg, and
  Amsterdam, the identification is credible.
- Heterogeneity is a feature: different flag thresholds/practice cultures across systems test whether the
  flag-ITT tracks the *local* policy effect (a strength, not noise).

## Harmonization approach (the enabling design)
Each adapter emits a HARMONIZED stream so the core engine is dataset-agnostic:
`(stay_id, time, analyte, value)` + `(stay_id, time, tx_class)` + `patient(age, mortality)`. The assay-noise /
flag-ITT engine (identical math to `portfolio_run.py`) then runs unchanged. This mirrors the `ricu` common-data-
model philosophy and means adding a database = writing one thin adapter, not a new analysis.

## Day-one-on-access runbook (per new database)
1. Fetch the **variable/item reference dictionary** first (HiRID variable ref; AmsterdamUMCdb dictionary; SICdb
   d_references) + stream table HEADERS to confirm columns — the agent's mappings are from public docs and MUST
   be verified against the real files before trusting.
2. Fill any `TO-CONFIRM-ON-ACCESS` cells in `MULTISITE_HARMONIZATION.md`.
3. Stream-filter labs + treatments (disk-sparing, resumable `wget -c`) exactly as for MIMIC/eICU.
4. Run the adapter → the same falsification battery + NC calibration + naive-vs-method contrast.
5. Add the resulting points to `benchmark_results.csv` → `make_figures.py` regenerates the multi-panel
   calibration figure.

## Guardrails (keep it honest)
- Magnesium is absent in some DBs (confirmed for INSPIRE); report only the analytes each database actually has.
- NC-outcome panels differ by coding system (ICD-10 vs local) — rebuild the negative-control set per database.
- Pre-register the benchmark thresholds/cases BEFORE running each new database (extend `BENCHMARK_PREREGISTRATION.md`)
  so multi-site concordance can't be dismissed as post-hoc tuning.

## Impact on tiering
With ≥3 of the European databases replicating the benchmark concordantly, the flagship (Paper A) moves solidly
into **top-tier clinical** range: a validated de-confounding method that reproduces landmark ICU trials across
four countries and answers a high-volume de-implementation question. This is the single highest-leverage
addition available, and it's now a fetch-verify-run task rather than new research.
