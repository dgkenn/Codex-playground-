# External Validation on INSPIRE — replication harness (PRE-REGISTERED)

**Status today: BLOCKED / pending.** The INSPIRE feature matrix
(`cache/inspire_matrix.csv`) is **absent on this host**, so the harness
correctly refuses to run and **never fabricates an INSPIRE result**. This
document and `analysis/external_validation.py` are the *plan + runnable
machinery*; they are analogous to the gated Phase-2 specs in
`docs/PHASE2_*` and the `analysis/phase2_prereq_guard.py` gate.

Implemented by: `analysis/external_validation.py`
Smoke test: `tests/test_external_validation.py`
Live status doc: `cache/external_validation_status.json` (written by the harness)

---

## 1. Why external validation matters

Every headline finding in this repo is **observational and single-centre**
(VitalDB / SNUH):

- organ-injury / fragility **phenotypes** (`phenotypes.py`, `phenotype_v2.py`),
- **hypotension-burden → AKI/composite** association (`hypotension_treatment.py`),
- **personalized-MAP-target HTE** (`map_hte.py`, `map_target_analysis.py`),
- **reperfusion-velocity** incremental biomarker (`reperfusion_dynamics.py`),
- **pressor-choice** (phe vs norepi) effect (`actionable_targets.py`).

Single-centre observational results are **hypothesis-generating only**. To be
publishable as more than that, the findings that *can* be replicated must be
re-run — unchanged estimator, unchanged estimand — on an **independent,
multi-centre** cohort. **INSPIRE** is the natural external cohort: it carries
intraoperative MAP, serum creatinine (pre/post → KDIGO AKI), pressor
administrations, and baseline covariates. It does **not** carry continuous
arterial waveforms, so the waveform-morphology arm is **unvalidatable** there
(Section 5).

The harness reports the **INSPIRE estimate beside the internal VitalDB
estimate** for each target, with a **pre-specified concordance verdict**. It
reuses the *same* internal estimators (IPTW from `hypotension_treatment.py`,
`e_value` from `actionable_targets.py`, the paired-OOF DeLong incremental AUROC
from `reperfusion_dynamics.py` / `models/metrics.py`) — replication means the
*identical* analysis on new data, not a re-derived one.

---

## 2. Replication-target registry

`REPLICATION_TARGETS` in `analysis/external_validation.py`. Each names the
internal finding, the internal result JSON holding the VitalDB estimate, the
estimand kind (and therefore its null), the estimator re-run on INSPIRE, and the
required mapped columns.

| Target key | Finding | Estimand (null) | Internal source | Estimator re-run on INSPIRE |
|---|---|---|---|---|
| `hypotension_burden_aki` | Hypotension-burden → AKI/composite | IPTW **OR** (null 1) + RD/RR + AUROC | `hypotension_treatment_results.json :: iptw_or` | `hypotension_treatment.run_analysis` (IPTW logistic) |
| `personalized_map_target_hte` | Personalized-MAP-target HTE: burden × subgroup | within-subgroup **RR** (null 1) | `map_target_results.json :: C_modifiable_iptw.organ_renal.target_65` | IPTW within-`preop_htn` high-vs-low-burden RR (bootstrap CI) |
| `reperfusion_velocity_increment` | Reperfusion-velocity incremental AUROC over static burden | **Δ-AUROC** (null 0) | `reperfusion_dynamics_results.json :: incremental_auroc.organ_renal` | `reperfusion_dynamics.incremental_auroc` (paired-OOF DeLong) |
| `pressor_choice_phe_vs_norepi` | Pressor choice phe vs norepi | IPTW **RR** (null 1) | `actionable_results.json :: exposures.phe_vs_norepi.organ_renal.within_high_risk_phenotype` | IPTW phe-vs-norepi RR (bootstrap CI) |

Notes:
- **`personalized_map_target_hte`** replicates the *direction and steepness* of
  the burden→injury dose-response inside the right-shifted-autoregulation
  subgroup (default `preop_htn==1`; CKD via `egfr_ckd_epi<60` is the secondary
  axis). The internal comparator defaults to the 65-mmHg target RR.
- **`pressor_choice_phe_vs_norepi`** is *better powered on INSPIRE*: norepi is
  explicit in INSPIRE medications, whereas in VitalDB it is pump-track-only
  (~88 cases). This is a target where INSPIRE could *strengthen* the evidence.
- **`reperfusion_velocity_increment`** is a **degraded-resolution** replication
  (Section 5): INSPIRE's coarse (≈1-min) MBP can only support a proxy
  `recovery_velocity`, not the high-resolution biomarker. Flagged in the report.

---

## 3. INSPIRE → internal variable mapping

`INSPIRE_VARIABLE_MAP` in `analysis/external_validation.py` is the authoritative
machine-readable copy; this table is the human-readable mirror. Keys are the
**internal** feature names the estimators expect.

| Internal name | INSPIRE source | Derivation | Role |
|---|---|---|---|
| `map_auc_below_65` | vitals: MBP series | AUC of MAP<65 over intraop window (mmHg·min) | exposure (burden) |
| `map_min_below_65` | vitals: MBP series | minutes with MAP<65 | burden / confounder |
| `map_mean` | vitals: MBP series | time-weighted mean intraop MAP | covariate |
| `map_lowest` | vitals: MBP series | nadir MAP (gated 20–200) | static-burden baseline |
| `organ_renal` | labs: serum creatinine pre/post | **KDIGO** AKI via `inspire/labeling.py` (same thresholds as `cohort/labeling.py`: ≥0.3 mg/dL/48h OR ≥1.5× baseline/7d) | **outcome y** |
| `composite` | labs + diagnosis | composite organ-injury; on INSPIRE reduces to renal+mortality axes INSPIRE supports | outcome y |
| `any_vasopressor` | medications | 1 if any intraop pressor | exposure |
| `phe_vs_norepi` | medications | among pressor-exposed: 1=phe-dominant, 0=norepi | exposure (pressor **choice**) |
| `intraop_phe` / `intraop_norepi` / `intraop_eph` | medications | total phe (µg) / norepi (µg) / ephedrine (mg) | exposure components |
| `age` | operations.age | years | confounder / age subgroup |
| `sex_male` | operations.sex | 1=male | confounder |
| `asa_class` | operations.asa | ASA 1–5 | confounder |
| `preop_htn` | diagnosis / preop flags | 1=preop hypertension | confounder / **HTN subgroup** |
| `preop_dm` | diagnosis / preop flags | 1=preop diabetes | confounder |
| `baseline_cr` | labs: most-recent preop creatinine | mg/dL | confounder / **CKD subgroup** |
| `egfr_ckd_epi` | derived (cr+age+sex) | CKD-EPI eGFR; CKD = <60 | CKD subgroup axis |
| `surgery_duration` | operations: opstart/opend | minutes | confounder |
| `optype_code` | operations: surgery type | factorised integer | confounder |
| `ebl` | operations: EBL (if present) | mL; **partial coverage** → imputed/dropped where absent | confounder |
| `recovery_velocity` | vitals: MBP recovery slope | late-vs-early MAP recovery / nadir depth, on coarse MBP (**degraded**, Section 5) | incremental feature |

The harness checks `required_cols` per target and reports **which mapped columns
are missing** rather than silently degrading.

---

## 4. Pre-specified concordance criteria (anti-HARKing)

Fixed **before** any INSPIRE data is seen, in code as `CONCORDANCE` and here. A
target is judged **CONCORDANT (replicates)** iff **all three** hold:

1. **Same direction** — the INSPIRE point estimate lies on the same side of the
   null as the internal VitalDB estimate (null = 0 for RD / Δ-AUROC; null = 1
   for RR / OR).
2. **CI overlap** — the INSPIRE 95% CI overlaps the internal VitalDB 95% CI.
3. **Magnitude within a factor** — the INSPIRE effect magnitude is within
   **`magnitude_factor = 2.0`×** of the internal magnitude, measured on the
   estimand's natural scale (log scale for RR/OR; additive for RD/Δ-AUROC). For
   additive estimands, if both effects are below the null floor
   (`rd_abs_floor` / `auroc_abs_floor` = 0.01) they count as "both ≈ 0" and
   magnitude-concordant.

A component that cannot be evaluated (missing point/CI) → **not** concordant
(reported as *DISCORDANT / inconclusive*). When the internal estimate is absent
(e.g. the internal result JSON has not been generated) the verdict is correctly
inconclusive, never a false "replicated".

These thresholds are deliberately lenient on magnitude (a 2× factor) because
between-cohort effect-size attenuation is expected; the load-bearing criteria are
**direction** and **CI overlap**.

---

## 5. What CANNOT be validated on INSPIRE

`NO_INSPIRE_EQUIVALENT` in the harness:

- **Arterial-waveform morphology** — INSPIRE ships **no continuous arterial
  waveform**, only intermittent (≈1-min) numeric vitals. Every finding that
  depends on beat-to-beat waveform morphology — the **a-line organ-injury arm**,
  dP/dt, pulse-pressure-variation morphology, waveform-shape phenotypes — is
  **unvalidatable** on INSPIRE and must **not** be claimed as replicated.
- **Arterial-line monitoring exposure** — the `arterial_line` management exposure
  (invasive continuous BP present in the VitalDB `/trks` index) has no analogue
  in INSPIRE's schema.
- **High-resolution reperfusion dynamics** — the full beat-resolved reperfusion
  biomarker needs waveform-rate sampling. INSPIRE supports only a **degraded
  proxy** `recovery_velocity` (Section 2/3), reported with an explicit caveat.

These remain VitalDB-internal, and would need a *waveform-bearing* external
cohort (e.g. another high-resolution OR database) to validate.

---

## 6. Staging (run once a winner is locked)

External validation runs **once**, after the internal "winner" is locked on the
internal test partition — never iteratively against INSPIRE (that would be the
same multiple-peeking error the Phase-2 gate exists to prevent).

1. **Lock** the internal finding(s) on the internal test partition (estimator,
   estimand, comparator, and the internal result JSON hash).
2. **Build** `cache/inspire_matrix.csv` from the INSPIRE tables using
   `INSPIRE_VARIABLE_MAP` (labs → KDIGO via `inspire/labeling.py`; vitals → MAP
   burden / recovery; medications → pressor exposure/choice; operations →
   covariates). The matrix-builder is a separate stage; this harness consumes it.
3. **Run** `run_external_validation(cfg)` — the gate unlocks, each target's
   estimator runs on INSPIRE, and the report tables INSPIRE-vs-internal with the
   pre-specified verdict; `cache/external_validation_status.json` records it.
4. **Report** concordance as-is. A non-replication is a finding, not a failure;
   the criteria are fixed and not to be relaxed after the fact.

### Running it

```bash
# Today (matrix absent) -> prints/writes BLOCKED, fabricates nothing:
python3 -m vitaldb_aki.analysis.external_validation

# Prove the harness wiring runs end-to-end on SYNTHETIC (non-INSPIRE) data:
python3 -m vitaldb_aki.analysis.external_validation --smoke

# Once cache/inspire_matrix.csv exists, the same command runs the real replication.
```

The synthetic smoke-test frame (`make_synthetic_inspire_frame`) is **clearly
labelled synthetic**, used only to exercise the wiring, and is **never** written
to `cache/inspire_matrix.csv` nor presented as a result.
