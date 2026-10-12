# Research documents — burst suppression and clinical EEG

*Index for `docs/research/`. Current at R392, 2026-07-27. Read `../../CLAUDE.md` first.*

This directory holds the **live** research record for the burst-suppression and clinical-EEG programme on
HEEDB, I-CARE and VitalDB. Documents from unrelated earlier projects were moved to `../archive/research/` on
2026-07-27; nothing was deleted and everything is recoverable from git history.

---

## Read in this order

| # | document | what it is |
|---|---|---|
| 1 | **`49_HANDOFF_STATE.md`** | **Start here.** What is established, what is provisional, what is dead, what to do next. Every number verified against its raw log. |
| 2 | **`48_RESEARCH_LANDSCAPE.md`** | What this data can and cannot settle, with feasibility counts. Where to invest next and what is structurally blocked. |
| 3 | **`41_RESULTS_LEDGER.md`** | **The primary record.** 392 results, and the consolidated constraint table (10 positives, 15 negatives, 5 structural limits) that every mechanism candidate must satisfy. Long — read the constraint table and the most recent sections, not the whole thing. |
| 4 | `47_BSP_TECHNICAL_NOTE.md` | Self-contained, publishable methods note on the BSP state-space estimator: independent implementation, exact-solver validation, window-length sweep, real-EEG forward prediction. |
| 5 | `45_MANUSCRIPT.md` | The manuscript draft. **Predates R358–R392** — check every claim against the ledger before quoting. |

## Supporting documents (this project, still relevant)

| document | what it is |
|---|---|
| `46_MECHANISM_BURST_CONTENT.md` | mechanism argument for burst content; predates the aetiology reversal |
| `44_MECHANISM_AND_PRIOR_WORK.md` | mechanism candidates against prior literature |
| `43_GAP_ANALYSIS_BROWN.md` | gap analysis against a publication-ready standard |
| `42_MAIN_RESULT.md` | the headline burden result |
| `39_HEEDB_FINDINGS.md`, `40_ROC_PIVOT.md` | earlier HEEDB deliverables |
| `38_HEEDB_BS_PHENOTYPE_SAP.md` | statistical analysis plan |
| `37_BROWN_SUMMARY.md`, `33_emery_brown_paper_plan.md` | positioning and paper planning |
| `34_BS_hypotension_manuscript.md`, `36_BS_hypotension_HARDENED_correction.md` | VitalDB burst-suppression / hypotension line, including its correction |
| `35_HEEDB_bs_context_findings.md` | HEEDB context findings |
| `30_EEG_toptier_loop_verdict.md`, `26_eeg_iic_ncse_SAP.md` | earlier EEG scoping |
| `figures/` | F1–F4 (burden quintiles, calibration, ROC, reliability) and the VitalDB BS figures |

---

## The current lead, so you do not have to hunt for it

**The prognostic meaning of intra-burst EEG content reverses by aetiology** (R389–R392). AUC of intra-burst
8–30 Hz content for 30-day death is **0.589 [0.545, 0.633]** in anoxic patients and **0.408 [0.364, 0.452]**
in non-anoxic — both excluding 0.5, on opposite sides, with no model involved. It survives burden strata
(3/3), burst-count strata (3/3), and decomposition of the non-anoxic arm (4/4 subgroups below 0.5, clustered
within 0.028). **It retrodicts N10**, a standing negative it was not built to explain.

Its weakness is external replication: I-CARE agrees in direction only (0.511 [0.464, 0.557], which *includes*
0.5) and, being entirely cardiac arrest, cannot test an aetiology contrast at all. Closing that gap — with a
mixed-aetiology cohort such as TUH — is the highest-value next action.

---

## Conventions in this directory

- **Numbers are quoted with their intervals.** A point estimate without one is a bug.
- **Every analysis script carries its pre-registration in its module docstring**, committed before the result
  existed. When reading a result, read the script's docstring first: it states the prediction, the
  falsification condition, and the scope limit.
- **Withdrawn claims stay visible**, marked at the point a reader would rely on them rather than only in a
  correction at the end (catalogue rule 3).
