# INSPIRE external validation of the VitalDB-AKI study

External replication of the VitalDB / SNUH (single-centre, observational) findings
on the **INSPIRE** cohort (PhysioNet INSPIRE 1.4.2, SNUH perioperative,
~131k surgeries). INSPIRE is an *independent* cohort and links to VitalDB only via
`operations.case_id` (a partial linker; most rows have it blank).

> Builder: `inspire/build_matrix.py` -> `cache/inspire_matrix.csv` (gitignored).
> Harness: `analysis/external_validation.py` (pre-specified, gated, anti-HARKing).
> Re-run command (after vitals finishes downloading):
> ```bash
> cd /home/user/Codex-playground-
> python3 -m vitaldb_aki.inspire.build_matrix         # rebuild matrix (now WITH MAP)
> python3 -m vitaldb_aki.analysis.external_validation # replicate all 4 targets
> ```

---

## READ FIRST -- limitations (binding)

1. **No arterial waveforms.** INSPIRE ships intermittent numeric vitals only
   (`art_mbp` / `nibp_mbp`, coarse sampling). Every waveform-morphology finding
   (the a-line organ-injury arm, dP/dt, pulse-pressure-variation morphology) is
   **UNVALIDATABLE** here (`NO_INSPIRE_EQUIVALENT` in the harness). The
   `recovery_velocity` biomarker is reproducible only in a **degraded-resolution**
   sense (coarse MBP, not beat-to-beat).
2. **Relative-time unit = MINUTES.** INSPIRE `*_time` / `chart_time` columns are
   integer minutes from a per-subject reference (verified empirically: median
   `opend-opstart` = 80, p95 = 325 min). The builder converts to seconds only
   where `cohort/labeling.py::label_case` expects seconds. The earlier scaffold
   `inspire/labeling.py` assumed *seconds-from-opstart* and `name=='cr'`; the real
   schema is *minutes-from-subject-reference* and `item_name=='creatinine'`. The
   builder targets the REAL schema directly (it does not use `inspire/labeling.py`).
3. **labs/medications/diagnosis are keyed by `subject_id`, not op.** A subject can
   have several operations; each subject's labs are attributed to each of that
   subject's ops using that op's own anchors (baseline cr = last cr before the
   op's `anstart_time`). The `vitals` table IS keyed by `op_id`.
4. **Intraop pressors live in the `vitals` table** (`phe`, `eph`, `epi`, `nepi`,
   `pepi`, `vaso`, `dopai`...), NOT in `medications` (which is ward/po
   prescriptions). norepinephrine is therefore directly recorded on INSPIRE
   (better-powered than VitalDB, where norepi is pump-track-only). When `vitals`
   is absent, pressor presence falls back to medications ATC codes.
5. **Comorbidity flags are chronic-condition flags** from `diagnosis.icd10_cm`
   (HTN = I10-I15, DM = E10-E14). INSPIRE diagnosis has no clean preop/postop
   split; HTN/DM are chronic, so any recorded code flags the subject.
6. **Composite outcome** is built from the INSPIRE-derivable axes only: renal
   (KDIGO creatinine), hepatocellular (AST/ALT >= 3x ULN), cholestatic
   (tbil >= 2x ULN), coagulation (ptinr >= 1.5 from documented-normal preop),
   hypoperfusion (lactate >= 4), and in-hospital mortality. Same thresholds as
   the internal `config.yaml organ_outcomes`.
7. **Leakage firewall.** Predictors are preop labs + intraop vitals/meds only.
   Outcomes (KDIGO/composite/death) are *y* and may use postop data by definition;
   no postop value becomes a feature.

---

## Pre-specified concordance bar (fixed BEFORE seeing INSPIRE)

A target **replicates** iff ALL THREE hold (`CONCORDANCE` in the harness):
1. **same direction** vs the null (RD/dAUROC null=0; RR/OR null=1),
2. **CI overlap** between the INSPIRE 95% CI and the internal VitalDB 95% CI,
3. **magnitude within 2x** on the estimand's natural scale (log scale for RR/OR).

---

## Per-target concordance table (internal VitalDB vs INSPIRE)

Internal VitalDB point estimates (from `cache/*_results.json`):

| # | Target | Internal estimand | Internal point [95% CI] | n / events |
|---|--------|-------------------|-------------------------|------------|
| 1 | hypotension_burden -> composite | IPTW **OR** | **1.174** [0.967, 1.510] | 4335 / 660 |
| 2 | personalized-MAP-target HTE (burden, renal, target_65) | within-subgroup IPTW **RR** | **1.451** [0.975, 2.131] | 3849 / 142 |
| 3 | reperfusion-velocity increment (renal) | incremental **dAUROC** | **-0.018** [-0.055, 0.018] | 3849 / 142 |
| 3b| reperfusion-velocity increment (composite) | incremental **dAUROC** | **+0.017** [0.001, 0.032] | 4231 / 649 |
| 4 | pressor choice phe-vs-norepi (renal, within high-risk) | IPTW **RR** | **0.175** [0.084, 0.423] | 218 / 27 |

> **Target 3 was internally DOWNGRADED to generic-severity** (it failed
> renal-perfusion *specificity*): the recovery signal is null/negative on the renal
> outcome (dAUROC = -0.018) and on the hepatocellular negative control
> (dAUROC = -0.037), positive only on the broad composite (dAUROC = +0.017).
> The internal interpretation is that recovery_velocity tracks **generic illness
> severity**, not a renal-specific perfusion mechanism. INSPIRE is therefore checked
> for *non-specificity* (a negative-control panel), NOT expected to show a positive
> renal signal.

### INSPIRE estimates + verdicts

<!-- INSPIRE_RESULTS_TABLE -->
_Pending: filled by `python3 -m vitaldb_aki.analysis.external_validation` after the
matrix is built. MAP-dependent targets (1, 2, 3) are **PENDING the `vitals.csv.gz`
download**; the non-MAP target (4, pressor choice) and the descriptive base rates
run as soon as `operations`/`labs`/`medications`/`diagnosis` are present._

---

## Cohort build summary

<!-- COHORT_SUMMARY -->
_Pending build output._

---

## Honest verdict

<!-- VERDICT -->
_Pending the full run (MAP targets require the vitals download)._
