# Probe 2026-08-02 — Dreyer BCI cache, Challenge B feasibility

*Reconnaissance only. No experiment, registration or ledger row written. All counts below are measured
directly from the files in `bsde/results/` on this machine, not estimated.*

Files inspected:
- `bsde/results/dreyer_performance.csv` (the outcome + questionnaire/demographic deposit)
- `bsde/results/dreyer_graph.s0.csv` … `.s5.csv` (resting-state graph/spectral features)
- `bsde/results/dreyer_smr.s0.csv` … `.s5.csv` (Blankertz SMR predictor features)
- (out of scope but noted for context) `dreyer_trials.csv`, `dreyer_trials.s0-3.csv`, `e188_dreyer_external_replication.json`

---

## 1. Columns, rows, subjects, join key

**`dreyer_performance.csv`** — this is the deposit's raw `Perfomances.csv` (semicolon-delimited,
comma-decimal, three concatenated sections "DATA A/B/C" with repeated header rows and trailing blank
lines). Parsed with a strict `^[A-Za-z]\d+$` match on the id field (rule 61 — do not substring/naively
split a structured file):

- **73 columns**, **87 real subject rows** (dataset A = 60, B = 21, C = 6 — matches E129/E131's stated
  cohort exactly), **87 unique `SUJ_ID`**, zero duplicates.
- Header (in order): `SUJ_ID, SUJ_gender, EXP_gender, COMMENTS, Perf_RUN_3..6, Birth_year, Vision,
  Vision_assistance, Symptoms, Level of study, Level_knowledge neuro, Meditation practice, Laterality
  answered, Manual activity, Manual activity TXT, score, time_1, time_2, PRE_Mood, PRE_Mindfulness,
  PRE_Motivation, PRE_Hours_sleep_last_night, PRE_Usual_sleep, PRE_Level_of_alertness,
  PRE_Stimulant_doses_12h, PRE_Stimulant_doses_2h, PRE_Stim_normal, PRE_Tabacco, PRE_Tabacco_normal,
  PRE_Alcohol, PRE_Last_meal, PRE_Last_pills, PRE_Pills_TXT, POST_Mood, POST_Mindfulness, POST_Motivation,
  POST_Cognitive load, POST_Agentivity, POST_Expectations_filled, active, reflexive, sensory, intuitive,
  visual, verbal, sequential, global (Index-of-Learning-Style), A,B,C_,E,F,G,H,I,L,M,N,O,Q1-Q4,IM,EX,AX,TM,
  IN,SC (16PF5 personality factors), Interrogation`.

**`dreyer_graph.s0-5.csv`** — 6 shards, **174 total data rows, all `status=ok`, 0 errors**, **87 unique
subjects**, exactly **2 rows per subject** (one `run=OE`, one `run=CE` — eyes-open / eyes-closed resting
baseline). Columns: `subject, dataset, run, status, error, n_channels, sfreq, n_samples, ge, cl, deg,
ge_norm, cl_norm, smallworld, modularity, strength_cv, iaf, alpha_prom`.

**`dreyer_smr.s0-5.csv`** — 6 shards, **87 total data rows, all `status=ok`, 0 errors**, **87 unique
subjects**, exactly **1 row per subject** (`run=OE` only — Blankertz's protocol is eyes-open only).
Columns: `subject, dataset, run, status, error, sfreq, n_samples, smr_C3_db, smr_C4_db, smr_predictor_db,
smr_peak_hz`.

**Join key: `subject` == `SUJ_ID`.** Verified exactly: all 87 `dreyer_performance` ids are present in both
feature files at `status=ok`, and neither feature file has a subject absent from the performance file (set
difference is empty both directions, both files). `dreyer_graph` needs an aggregation step (mean of OE/CE,
or OE-only) before a 1:1 join with performance/`dreyer_smr`, since it carries 2 rows/subject.

---

## 2. The outcome

`Perf_RUN_3`, `Perf_RUN_4`, `Perf_RUN_5`, `Perf_RUN_6` — OpenViBE **online classification accuracy** (%),
one value per run, 4 runs per subject, from the deposit's live feedback classifier.

- **Machine-scored**, not a human judgement: it is the output of the OpenViBE 2-class (left/right motor
  imagery) online decoder during real-time feedback, exactly analogous to Stieger's online BCI accuracy.
  No clinician or rater is in the loop.
- Non-missing counts: `Perf_RUN_3` 87/87, `Perf_RUN_4` 87/87, `Perf_RUN_5` 86/87, `Perf_RUN_6` 86/87.
- Ranges/means: RUN_3 [30.0, 100.0] mean 61.92; RUN_4 [32.5, 100.0] mean 63.62; RUN_5 [40.0, 100.0] mean
  63.14; RUN_6 [32.5, 100.0] mean 64.83. (The 4-run mean is the construct all prior Dreyer experiments in
  this project used as "online accuracy".)
- **87 subjects carry the outcome.**

This is a genuine escape from rule 86: the incumbent-vs-outcome shared-observer problem does not apply
here because the outcome is not a bedside/clinician score at all.

---

## 3. Resting / task-free EEG block — the make-or-break criterion

**It exists, and it is exactly what `dreyer_graph.csv` / `dreyer_smr.csv` were computed from.** Per
`bsde/scripts/extract_dreyer_graph.py` and `extract_dreyer_smr.py`: each subject contributes two dedicated
baseline recordings, `<SUJ>_OE_baseline.gdf` (eyes-open, 2 minutes) and `<SUJ>_CE_baseline.gdf` (eyes-closed,
2 minutes), recorded **before the four online BCI runs**, described in the source as a "relax with eyes
open/closed" condition — structurally distinct files from the motor-imagery trial runs, not epochs cut out
of the task blocks. `WINDOW_S = 120.0` (2 minutes) is taken from the start of each baseline file. All 174
graph rows and 87 SMR rows in the cache were extracted from these baseline files, confirmed by `run` values
of only `{OE, CE}` — never a trial-run identifier.

**Criterion (3) is satisfied. This is not the blocking constraint.**

(For contrast: `dreyer_trials.csv`/`dreyer_trials.s0-3.csv`, 13,832 rows across all 87 subjects, is a
*separate* cache of **pre-cue, trial-locked** features used by E188/E192/E201 for the now-closed "pre-cue
alpha" line — task-adjacent, not task-free. Not part of what was asked for here, flagged only so it is not
confused with the resting block.)

---

## 4. Non-clinician incumbent/covariate candidates in `dreyer_performance.csv`

All are single-session, no repeated sessions exist for any subject (Dreyer is single-session for all 87),
so there is no session-index, prior-session-count, or time-of-day column. What actually exists:

| candidate | column(s) | n non-missing / 87 | note |
|---|---|---|---|
| age (proxy) | `Birth_year` | 87 | no test-year field, so only relative age is recoverable, not exact age |
| sex | `SUJ_gender` | 87 | 2 levels |
| experimenter sex | `EXP_gender` | 85 | 2 levels — an exposure variable, not touched by any prior experiment |
| education level | `Level of study` | 87 | 4 levels |
| neuroscience familiarity | `Level_knowledge neuro` | 74 | 5 levels |
| meditation practice | `Meditation practice` | 79 | 3 levels |
| handedness | `Laterality answered` | 87 | 3 levels |
| manual/hobby activity level | `Manual activity` (+ free-text `Manual activity TXT`) | 87 / 79 | ordinal coded |
| mental rotation score + admin times | `score`, `time_1`, `time_2` | 84 / 84 / 84 | **already tested, E132, null** (rho -0.1700 [-0.3833, +0.0434]) |
| pre-session state | 12 `PRE_*` columns (mood, mindfulness, motivation, sleep, alertness, stimulants, tobacco, alcohol, last meal/pills) | 72-84 | one (`PRE_Level_of_alertness`) already tested, null; the other 11 are untested |
| Index of Learning Style | 8 columns (`active/reflexive`, `sensory/intuitive`, `visual/verbal`, `sequential/global`) | 82-83 | untested |
| 16PF5 personality | 20 factor columns (`A,B,C_,E,F,G,H,I,L,M,N,O,Q1-Q4,IM,EX,AX,TM,IN,SC`) | 83 each | untested |
| `Interrogation` | 1 column | 71 | **provenance unclear** — position/name suggest an item-count from the personality/ILS battery rather than a session-outcome variable, but this was not verified against a data dictionary; treat as excluded until clarified |

**`POST_*` columns (6: Mood, Mindfulness, Motivation, Cognitive load, Agentivity, Expectations_filled) are
measured AFTER the online runs and must not be used as predictors** — this is rule 10 (look-ahead) applied
to a questionnaire, already established once in this exact deposit: E132 registered `POST_Agentivity` as a
secondary, got +0.2714 [+0.0415, +0.4135], and withdrew it for this exact reason. All six POST_* columns
carry the identical defect and none has been used as a predictor since.

---

## 5. Rule-70 check — every feature column, is it a measurement of the EEG signal alone?

**What a candidate is ALLOWED to be:** a quantity computed from the raw baseline EEG waveform (spectrum,
connectivity, complexity, channel amplitude), on a fixed a-priori time window, with no reference anywhere
in its computation to trial count, trial timing, cue onset, classifier output/confidence, or run index.

**`dreyer_graph.*.csv` (12 substantive columns) — ALL PASS.** `ge, cl, deg` (raw graph-theory summaries of
the wPLI alpha-band connectivity matrix), `ge_norm, cl_norm, smallworld, modularity, strength_cv`
(normalised/derived graph measures), `iaf` (individual alpha frequency from the PSD), `alpha_prom` (alpha
peak-to-background prominence). Every one is computed from the 120 s `OE`/`CE` baseline files only, via
`extract_stieger_graph62.py`'s `graph_features`/`periodic_features_at` (imported, not reimplemented — rule
20). None takes a trial index, run label, or performance value as input. `n_channels`, `sfreq`, `n_samples`
are extraction metadata, not candidates (see §6).

**`dreyer_smr.*.csv` (4 substantive columns) — ALL PASS.** `smr_C3_db, smr_C4_db, smr_predictor_db,
smr_peak_hz` are Welch-PSD decibel excess over a background fit, computed on the same 120 s `OE` baseline,
Laplacian-referenced at C3/C4. No trial, timing or classifier-derived quantity enters the computation.

**No column in either feature file is a re-description of `Perf_RUN_3..6`, a trial count, a trial-length
statistic, or a classifier confidence** — the specific failure mode that destroyed `mean_triallength` in
E149 does not recur here, structurally, because these features never touch the online-run files at all.

**Within `dreyer_performance.csv`:** the six `POST_*` columns are not EEG measurements but are flagged
under rule 10 as above (§4). `Interrogation`'s provenance is unverified and is excluded pending a data
dictionary. Everything else in that file is a candidate predictor or a demographic covariate, not a
"feature" masquerading as one.

---

## 6. All-NaN / constant columns (rule 74)

- `dreyer_graph.*.csv`: **`n_channels` (constant = 27), `sfreq` (constant = 512), `n_samples` (constant =
  61,440)** across all 174 rows. Reason: identical acquisition (32-ch montage minus EOG/EMG/ECG/status/ref
  picks = 27 channels; 512 Hz; 120 s window) for every subject and run — expected extraction metadata, zero
  variance, not usable and not meant to be used as candidates. No column is all-NaN.
- `dreyer_smr.*.csv`: **`sfreq` (constant = 512), `n_samples` (constant = 61,440)** across all 87 rows,
  same reason. No column is all-NaN.
- `dreyer_performance.csv`: **no column is all-missing or constant.** Smallest non-missing count is
  `Interrogation` at 71/87 (16 missing); smallest unique-value count among substantive columns is 2
  (`SUJ_gender`, `EXP_gender`).

---

## 7. Has this project already used this deposit? (mandatory search)

**Yes, extensively — 11 registered experiments, Challenge B, spanning both the resting-baseline features
and the trial-locked ones.** Searched `bsde/docs/MASTER_PLAN.md`, `bsde/governance/REGISTRATION_LEDGER.jsonl`,
and all of `bsde/docs/` for `dreyer`/`Dreyer`/`BCI`.

| id | question | outcome |
|---|---|---|
| E125 | Does `ge_norm` (E86's Stieger predictor) predict online accuracy in Dreyer? | **negative** — -0.2065 [-0.3921, -0.0003], inside its own permutation interval; not replicated |
| E129 | Does Blankertz 2010's published SMR predictor replicate? | **positive** — +0.4440 [+0.2480, +0.6104], close to the attenuated expectation +0.4183. Also found `alpha_prom` (already in `dreyer_graph.csv`) works at +0.3710 [+0.1709, +0.5512] |
| E131 | Does `alpha_prom` (Dreyer's working predictor) transport to Stieger? | **negative** — +0.0747 [-0.1968, +0.3294]; the two cohorts have disjoint working predictors |
| E132 | Does mental-rotation score (Jeunet 2015) predict, and is E129 confounded by it? | primary **negative** (-0.1700 [-0.3833, +0.0434]); E129 **strengthened** (SMR predictor survives partialling out mental rotation, +0.4294); `POST_Agentivity` secondary **withdrawn** as invalid look-ahead |
| E134 | Does any graph measure add to the SMR predictor? | **negative**, 0/10 candidates |
| E163 | Re-derive E134 with a calibrated increment test | **null replicates, but is now known WEAK** — detection floor above rho_partial 0.4 at n=87, one row/subject |
| E164 | Does session-to-session CHANGE in any measure track accuracy change? | N/A to this cache — Stieger, not Dreyer |
| E177 | Does `alpha_prom` (Dreyer-discovered) transport forward to eegmmidb? | **positive** on the primary label (`csp_auc`, rho +0.2939, p 0.0015); partial violation on the secondary label |
| E188 | External replication of the "pre-cue alpha" trial-locked effect | **absent**, both arms; real EMG channels null (this is what built `dreyer_trials.csv`) |
| E192 | Graded execution-quality replication, continuous pursuit | gate-failed on a different deposit (Forenzo & He), successor of E188 |
| E201 | Same, with a corrected aliveness gate | **absent**, 0.5134 [0.4850, 0.5406]; one secondary clears BH pointing the WRONG way |

**`INCUMBENT_REGISTRY.md` (§ Challenge B, action item 1) explicitly flags the one thing in this cache that
was identified as valuable and never executed:** Rimbert 2018 (PMID 30728772, "a subjective questionnaire
as a BCI performance predictor") is marked **IMPLEMENTABLE on Dreyer** — "the deposit ships personality,
mental-rotation, mood and motivation columns in `Perfomances.csv` and we have never touched them" — and the
registry's own priority-1 action item is "Dreyer's questionnaire columns vs online performance... This is
the E129 mistake caught before it costs." Checked against the full ledger (E125 through E227, the latest
entry): **no experiment after E132 tests any of the ILS or 16PF5 columns.** Only `score`/`time_1`/`time_2`
(mental rotation) and `PRE_Level_of_alertness`/`POST_Agentivity` have ever been touched. The 8 ILS columns,
20 personality columns, `EXP_gender`, `Level of study`, `Meditation practice`, `Laterality answered`,
`Manual activity`, `Birth_year`, and 11 of 12 `PRE_*` columns are **untested** in this project's history.

`CONSOLIDATION_2026_08_02.md` (§3, Challenge B) records that as of the most recent consolidation the
project's Challenge B effort **pivoted away from Dreyer/Stieger entirely**, to a newly-unblocked HEEDB
GCS-motor design ("the actual unblock... was never a dataset, it was a label"), after concluding the
pre-cue alpha line was finished (E172/E174/E188/E201, three independent non-replications). No experiment
against Dreyer's own outcome has been registered since E201.

---

## Deliverable

**FEASIBLE**, with the binding constraint named below — this is not a rerun of anything on the ledger.

**What is feasible and new:** a Challenge B design testing the **untested personality/ILS/demographic
block** in `dreyer_performance.csv` (Rimbert 2018's comparator, `INCUMBENT_REGISTRY.md`'s own priority-1
action item, never executed past E132's mental-rotation arm) against `Perf_RUN_3..6` online accuracy, with
the SMR predictor / `alpha_prom` declared as incumbent (both already alive on this cohort: rho +0.4440 and
+0.3710 respectively, per E129). All three criteria that killed prior attempts are clear: the outcome is
machine-scored (escapes rule 86), the resting block is real and already extracted (criterion 3 passes),
and the candidate block is verifiably a measurement of the subject via questionnaire, not a re-description
of the outcome (rule 70 — none of these columns reference trial count, timing, or classifier output; the
`POST_*` look-ahead columns are the one carve-out, already known and already excludable).

**The binding constraint, and it is a power constraint, not a data-availability one:** n = 87, one row per
subject. E134/E163 already measured this design's detection floor directly on this exact cohort — **an
increment test here can only see effects above roughly rho_partial 0.40** (70% detection at 0.40, 38% at
0.30, 8% at 0.10). Any registration must be built as a single-predictor correlation against the declared
incumbent (as E129/E132 were), state the measured floor up front, and not be framed as an exhaustive sweep
of all 28 questionnaire columns — that would reproduce E134's now-corrected "comprehensive" overreach
(rule 34/63) at a fraction of its per-candidate power once any multiplicity correction is applied across
28 columns. A single pre-registered comparator (Rimbert's own construct, or the single 16PF5/ILS factor
Rimbert names, if recoverable from the paper) is the design this cache actually supports; a blanket sweep
of all 28 is not, at this n.
