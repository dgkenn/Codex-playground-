# Vasopressor project — final consolidated log (before pivot)

Single record of the entire VitalDB / MIMIC-IV / INSPIRE vasopressor investigation, its honest
outcome, the reusable assets, and what is exhausted — written as the clean hand-off before pivoting
to a new data/topic (user decision: option 3).

## One-paragraph summary
We pursued the hypothesis that the intraoperative/ICU **vasopressor requirement** (the dose needed to
hold blood pressure) is a high-impact, novel risk signal. Through many analyses and **four formal
adversarial red-team rounds** (plus an earlier 8-agent publication panel), every *novel* framing was
either killed or bounded to incremental: the "stable patient trait" framing died (cross-encounter
reliability ICC 0.07 — the high reliability was infusion autocorrelation); the dose→mortality result is
real but is the **known VIS literature**; and the one genuinely new angle we surfaced — *occult
vasopressor dependence at normal pressure* in the ICU — survived hardening (collider test passed, MICE
OR 2.04, reproduces exactly) but is **incremental** (its novel "at-target" move adds only +0.031 AUC;
the flashy "information gap doubles" headline was 72% a restriction-of-range artifact). **Net: a
defensible Critical Care Medicine / Intensive Care Medicine *supporting* analysis exists, but NOT an
Anesthesiology-tier-or-above novel standalone finding. Data ceiling reached.**

## What is TRUE and publishable (the defensible residual)
- **Vasopressor load → mortality, prospectively (landmark):** first-24h NEE → post-24h death, fully
  adjusted OR 1.74 [1.57,1.91] (overall), reverse-causation defeated by design. (= confirms VIS.)
- **Occult dependence at normal pressure (ICU):** among at-target-MAP patients (median 65–85, <10%
  below 65; n=7,841), first-24h requirement → post-24h mortality Q1 3.1%→Q4 27.8%; MICE-adjusted OR
  **2.04 [1.85,2.24]**, E-value 3.0/2.7; within-severity 3/3 lactate tertiles; single-pressor 1.64;
  stronger in art-line patients (3.10). Honest scope: risk-stratification; "gap doubles" retired (72%
  artifact); incremental vs VIS/VDI/BPRI.
- **Control-theory premise:** intraop (VitalDB) AND ICU (MIMIC) MAP is tightly regulated (CV 0.09 / 0.125)
  vs dose CV 0.44 — documents the regulation (partly a control identity, not causal proof).

## What is DEAD / RULED OUT (do not re-mine)
- "Vasopressor requirement is a stable patient TRAIT" — cross-encounter ICC 0.07.
- Dose→mortality as a *novel* claim — it is VIS / VDI (dose÷MAP) / BPRI (MAP÷VIS).
- Personalized MAP target / MAP-target HTE — null (LRT p≈0.88).
- CKD×MAP causal, cumulative-pressor→AKI causal — killed by negative-control calibration.
- A-line "independent levers" / fluid-vs-pressor decision tool — retracted (degenerate column).
- Predict ΔMAP from dose (responsiveness) — killed by closed-loop titration confounding.
- Decision-benefit / actionability (concordance) — null.
- Prescribing-preference IV, propofol negative-control — demoted (invalid instrument / collider).

## Reusable assets (carry into any pivot)
- **Disk-safe stream-filter pattern** (`scratchpad/stream_map.sh`): pipe a 30 GB PhysioNet `.csv.gz`
  through `zcat|awk`, keep only cohort+itemid rows, never store the whole file. Survived a clean 30 GB
  chartevents pass.
- **Analysis machinery** (`analysis/finding4_landmark.py`, `analysis/icu_occult_dependence.py`):
  landmark design (first-window exposure / alive-at-landmark / subsequent outcome), IRLS logistic with
  bootstrap + cluster options, MICE + Rubin's pooling, E-value, OOF-AUC, collider/within-stratum tests.
- **Derived MIMIC extracts** (scratchpad/cache, gitignored): per-stay MAP (7.58M rows), pressor/fluid
  infusions, first-24h labs, KDIGO creatinine — reusable for any MIMIC-IV ICU question.
- **Red-team harness pattern:** N parallel adversaries with distinct lenses (stats / causal / novelty+
  PubMed / reproduction) per round, a code-running "crux/collapse" skeptic, synthesis + honest reckoning.

## Why we are pivoting
The user's bar is an **Anesthesiology-tier-or-above NOVEL** finding. Four rounds established that the
vasopressor→outcome vein, on the available data, tops out at *incremental* (the genuinely novel content
is small; the strong content is known). The honest move is not to keep polishing an incremental result
but to pivot to a genuinely new direction. Candidate pivot spaces (to be scoped next): the repo's
original **HEEDB EEG phenotype** work; a different MIMIC-IV/eICU question where a novel construct is not
already a named index; or a new dataset. The next step is a fresh idea-generation + feasibility scan,
NOT more vasopressor analysis.

Cross-ref: IDEAS_LEDGER.md (full idea inventory + status), REDTEAM_R3/R4_SYNTHESIS.md,
ICU_OCCULT_DEPENDENCE.md, RED_TEAM_ROUND2_SYNTHESIS.md, HOSTILE_REVIEW_FINAL.md.
