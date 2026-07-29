# CLAUDE.md — guide for Claude Code sessions in this repo

*Last updated 2026-07-29 at result R412. If you are a new session, read this file top to bottom before
touching anything, then read `docs/research/49_HANDOFF_STATE.md` for where work stopped and why.*

---

## START HERE: what this project actually is, versus what it says it is

**Read this section carefully — the repo's name and its oldest documents will mislead you.**

The repo was created for a *pre-registered, two-phase, unsupervised EEG phenotype discovery study* on HEEDB
using a frozen foundation model. **That pipeline exists, is tested, and is not what the work has been about
for some time.** It runs (`python cli.py demo`), the full suite passes, and the firewall/hashing integrity
core is sound. Treat it as a working asset in cold storage, not the active thread. Its protocol is
`HEEDB_rawSSL_phenotype_discovery_preregistration_v3.md`; its binding integrity principle (Phase 1 uses no
outcome label; Phase 2 tests one pre-registered outcome on a held-out hospital with four frozen,
hash-verified objects) still stands **if that pipeline is ever resumed**.

**The active research programme is a burst-suppression and clinical-EEG research loop on HEEDB, I-CARE and
VitalDB.** It has produced **412 logged results** and one substantive lead (below). Everything of scientific
value lives in `docs/research/41_RESULTS_LEDGER.md`, `docs/LESSONS.md`, and `docs/EXPERIMENT_QUEUE.md`.

There is also a large amount of **legacy documentation from unrelated earlier projects** — electrolytes,
MIMIC, arterial-line tooling, occult hypoxaemia. `docs/` holds 156 files and `docs/research/` holds 56; most
predate this work and are not live. The files that are live are listed under "Which documents are current".

### The current lead, in one paragraph

**The prognostic meaning of intra-burst EEG content reverses by aetiology.** AUC of intra-burst 8–30 Hz
content for 30-day death is **0.589 [0.545, 0.633]** in anoxic patients and **0.408 [0.364, 0.452]** in
non-anoxic — both intervals excluding 0.5, on opposite sides, with no model involved. It survives burden
strata (3/3), burst-count strata (3/3 — the variable gating the exclusion), and decomposition of the
non-anoxic arm (**4/4 subgroups below 0.5, clustered within 0.028**). It **retrodicts N10**, a standing
negative it was not built to explain. Its weakness is external replication: I-CARE agrees in direction only
(AUC 0.511 [0.464, 0.557], which *includes* 0.5) and, being entirely cardiac arrest, is structurally
incapable of testing an aetiology contrast at all. See R389–R392 in the ledger and
`docs/research/48_RESEARCH_LANDSCAPE.md` for what it needs next.

**Two qualifications a new session must carry with that paragraph, both established after it was written.**
(1) **R411:** the reversal survives the day-3 withdrawal landmark as an *interaction* (+4.646 [+3.092, +6.547]
full, +4.313 [+2.335, +6.481] past the landmark), but the **anoxic arm's own information is genuinely
concentrated in early deaths** — a matched null puts that at the 1st percentile, so it is not a power
artefact. Both sentences belong in an abstract. (2) **R409-R410:** the self-fulfilling-prophecy *explanation*
built on top of this in R404-R408 was tested three ways and is **not supported**; front-loaded
hypoxic-ischaemic mortality is the parsimonious reading. Do not present the withdrawal story. See
`49_HANDOFF_STATE.md` §3.0.

---

## THE MOST IMPORTANT OPERATIONAL FACT: the data cache is ephemeral

Hours of extraction live in **`/tmp/eeg_probe/`** and **it does not survive container reclamation.** A new
session will probably find it empty. Nothing there is in git and nothing should be — it is credentialed
patient-derived data.

| cached table | rows | cost to rebuild |
|---|---|---|
| `heedb_bs_burden_win.s0-3.csv` | 4 shards, ~4,800 patients each | hours (S3 + DSP over ~49k recordings) |
| `heedb_burst_morph.s0-3.csv` | 4 disjoint shards, 2,473 patients total | hours |
| `heedb_aetiology_full.csv` | 26,350 label rows | ~3 min (scans a 1 GB OMOP table) |
| `heedb_omop_quant/condition_occurrence.csv` | ~3.6 M rows, 49,232 patients | ~20 min (streams 181 parquet parts / 27 GB); **resumable** |
| `icare_cohort.csv` | 607 | minutes |
| `icare_morph2.csv` | 559 | ~40 min |
| `icare_background.csv` | 601 | ~50 min |
| `icare_topo.csv` + `icare_suppseq.csv` | 602 | ~60 min (one pass produces both) |
| `icare_seq_keep.csv` | 529 | ~2 min (WFDB headers only) |

**`heedb_omop_quant` is NOT the same as `heedb_omop`, and using the wrong one is a scientific error.**
`heedb_omop/` was extracted for burst-suppression patients *with an ascertained death* — that is limitation
L3, which R393 lifted. `heedb_omop_quant/` is the same table re-extracted for the **full 49,232-patient
findings cohort including survivors**, and every aetiology analysis from R398 onward reads it. Rebuild with:

```bash
PIDS_FILE=/tmp/heedb_quant_patients.txt OMOP_OUT=/tmp/eeg_probe/heedb_omop_quant \
  python analysis/heedb_omop_extract.py condition_occurrence
```

where the PID file is the union of patient ids in the two `*_EEG__reports_findings.csv` objects (morph and
burden patients are all inside that set — verified 2026-07-29).

**The container REAPS large files in `/tmp` mid-session — observed twice on 2026-07-29**, both times taking
the 3.3 GB `heedb_omop_quant/` while every smaller cache survived. Do not depend on a multi-gigabyte
intermediate. `analysis/heedb_aetiology_compact.py` reduces that table to the ~1 MB
`heedb_aetiology_compact.csv` (one row per patient, one column per aetiology group) and rebuilds itself from
the big table on first use; prefer `load_anoxic()` from it over parsing `condition_occurrence.csv` directly.

**Rebuild order:** aetiology cache first (cheap, unblocks all HEEDB work), then `analysis/icare_topography.py`
(one S3 pass, produces topography *and* the per-second suppression series), then the rest as needed. Every
extraction script is **resumable** — each reads what is already in its output file and fetches only the
remainder. The HEEDB burden/morphology shards are the expensive ones; treat them as precious.

---

## Credentials, and the trap that will cost you an hour

Real HEEDB/I-CARE/MORGOTH access is credentialed. **Never commit credentials.**
**Durable storage: set `BDSP_AWS_ACCESS_KEY_ID` / `BDSP_AWS_SECRET_ACCESS_KEY` in the Claude Code web
environment's environment-variable settings** — they are attached to the environment, not the session, so
every future session gets them. `scripts/bdsp_bootstrap.sh` materializes `~/.aws/credentials` at session
start and probes it. Full detail in **`docs/CREDENTIALS.md`**.

**TUH access was APPROVED 2026-07-27, and it still cannot replicate this finding — do not plan around it.** The TUH EEG Corpus carries **no linked
outcome data** (manifest: `recording_id, patient_id, edf_path, sfreq, age, sex`) and no diagnosis, so it
cannot replicate any outcome association, and certainly not an aetiology contrast. Established at ledger
**R321**. It can validate a *measurement* against a clinician label elsewhere, which is a lesser claim. Separately and independently, TUH cannot be
pulled from this sandbox at all: outbound **port 22 is blocked** (measured — 443 is open, 22 times out), so
no SSH client reaches NEDC from here regardless of the key. TUH work needs an unrestricted host. See
`docs/CREDENTIALS.md`.

**The sandbox injects placeholder `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` for its proxy. Static env
credentials outrank profile credentials in boto3's resolution chain, so every script silently authenticates
as the stub and gets 403 — which reads exactly like expired credentials and is not.** Always run through:

```bash
scripts/heedb_run.sh python analysis/<script>.py
```

It unsets the two stub variables and leaves `AWS_CA_BUNDLE`/`HTTPS_PROXY` alone. Diagnose credential problems
with `sts get-caller-identity` **per credential source**, not globally (catalogue rule 8).

- HEEDB clinical: access point `.../bdsp-credentialed-access-point`, key prefix `EEG/HEEDB_Metadata/`
- I-CARE: `.../bdsp-restricted-access-point`, prefix `ICARE_train/training/`
- MORGOTH label sets: `.../bdsp-credentialed-projects-ap`, prefix `morgoth1/data/internal_dataset/`
- AWS profile: `physionet`

---

## SOP: model delegation and token budget (STANDING — applies to every session)

Research on this repo is token-expensive and has come close to the weekly usage cap. **Opus is the
orchestrator and the reviewer, not the labourer.** Bulk reading, searching, editing and mechanical
transformation should not happen in the main Opus context.

| task | model | why |
|---|---|---|
| Orchestration, experiment design, deciding what to run next, final synthesis, anything that becomes a **reported number or a committed claim** | **opus** (main) | judgment the whole result rests on |
| Red-teaming a document or result, code review, literature triage, drafting prose, interpreting ambiguous output | **sonnet** | needs judgment, but is checkable afterwards |
| Mechanical and verifiable: applying a precise edit spec across files, running a script and extracting fields, counting/tabulating, grepping a large tree, log triage, boilerplate | **haiku** | cheap, and correctness is checkable by inspection |

**The review rule, which is not optional.** Any subagent output that will become a reported number, a claim in
a document, or a commit must be **verified by Opus against the raw source** before use. Subagents are useful
and also wrong often enough to matter. Delegate the work, never delegate the acceptance.

**Practical token discipline:** never `cat` a large file — `head`/`tail`/`grep`/`sed -n 'a,bp'` to specific
lines. Long analyses write to a log; read back result lines only. Background anything over ~2 minutes and poll
with a cheap `until` loop rather than foreground sleeps. Do not re-read a file already read this session, and
do not re-read a file just edited. Never read a subagent's raw transcript — it will overflow the context.

---

## SOP: the error catalogue (STANDING — read before designing any analysis)

Every rule below was paid for with a wrong result in this project.

### A. Correction discipline

1. **A correction propagates to everything downstream, not just the number that prompted it.** When a
   definition changes, list every claim that depends on it before re-running anything.
2. **Numbers inherited from a superseded extraction must be re-derived, never carried forward.**
3. **Stale claims survive in earlier sections.** Put the withdrawal where a reader would rely on the claim,
   not only at the end.
4. **Hardcoded literals in captions, titles and prose go stale silently.** Compute every number that appears
   in output, including in labels.

### B. Silent failure

5. **Empty is not evidence of absence until the filter has been shown capable of matching something.**
   Assert non-empty, or assert the filter matches a known positive.
6. **Check that a `concept_id` column is populated before designing around it.** `observation_concept_id` was
   100 % zero; one `Counter` over 100k rows would have shown it in seconds.
7. **Before choosing an administrative table as an instrument, ask what makes a row appear in it.** Billing
   tables see reimbursable acts; state tables see charted statuses; **neither sees decisions**.
   `procedure_occurrence` contains zero extubations because extubation is not separately billable.
8. **An access failure may be credential *precedence*, not expiry.** Diagnose per credential source.

### C. Statistical rules

9. **Bootstrap AUC increments out-of-bag.** Train on the resample, evaluate on the patients *not* drawn.
   Bootstrapping fixed out-of-fold predictions ignores refit variance; refitting *and* evaluating on the same
   resample puts patients in train and test. Both were used here and both were wrong.
10. **Any per-patient aggregation over repeated measurements is look-ahead until proven otherwise.** `max()`,
    `or` and bare assignment across rows all leaked. The pattern was in 17 scripts.
11. **Sign the bias separately for every analysis a shared bug touches.** "Conservative" established for one
    estimand did not transfer.
12. **Predictive increment cannot identify a mechanism when the measure is noisy.** Two readings of a
    *constant* beat one. Decompose into `mean` and `difference` and test the **sign** of the difference term.
13. **Never "fix" a confound by conditioning on a post-exposure variable.** That is a collider.
14. **Report exclusions and check whether they are outcome-related.** Both major exclusions in this project
    turned out to be.
15. **Discrimination without calibration is half a result**, and the missing half is the half clinicians use.

### D. Reading the evidence

16. **When two arms of the same test disagree in SIGN, the definition is doing the work, not the biology.**
17. **When a fix makes the effect stronger, the diagnosis was wrong** — a refutation, not a refinement.
18. **Uniformity across strata whose clinical handling is known to differ is evidence AGAINST validity.**
19. **Before two measures can corroborate each other, check whether one row can satisfy both definitions.**
20. **When two scripts compute the same quantity, diff them even if only one is published.**
21. **Run the literature check BEFORE the analysis when the prediction rests on a premise about a disease.**
    "Dead cortex cannot seize" is sound physiology and false after cardiac arrest.

### E. Verification

22. **A validity figure living in a code comment is not a validity figure.** "AUC 0.829" in a comment was not
    reproducible; measured properly it is 0.749.
23. **Self-written code plus self-written tests share blind spots.** Validate against an *independent*
    implementation — an exact solver caught a 0.775 deviation that seven unit tests missed.
24. **Delegate the enumeration, verify the classification — and spot-check the calls rated LOW risk.**
25. **Verify every citation from the MEDLINE record via E-utilities.** WebFetch fabricates PubMed content
    under CAPTCHA; it cost this project six wrong citations once.

### F. Added 2026-07-27

26. **Smoke-test an analysis on PERMUTED labels, never real ones.** It exercises every code path on real
    feature distributions while revealing nothing about the association, so a pre-registration stays clean —
    and repeated a few hundred times the same harness measures the procedure's false-positive rate directly.
    That is how `diff_ci` and `oob_increment` came to be audited at all.
27. **A mask that compresses out bad samples glues time together.** Right for any order-free summary, wrong
    for anything modelling transitions. One recording in 24 had a 1,817 s hole closed up, invisible in the
    output because the burden was unaffected. Verify the time axis before modelling temporal evolution.
28. **Two measurements separated in space or time are not thereby measuring different things.** Predicted
    twice — background vs intra-burst spectrum, topography vs median-across-channels — and both were redundant.
29. **Overlapping category labels cannot decompose a contrast between two of them.** When the comparison is
    A versus not-A, the decomposition must happen **inside not-A**.
30. **Write the conclusion rule before the run, then check the rule itself for holes.** Pre-registration stops
    the bar moving afterwards; it does not stop it being set too low, and that failure is harder to notice
    because the paperwork looks correct.
31. **When a replication fails its own gate, the downstream verdict is absent, not negative.** Scripts must
    refuse to emit a decisive verdict when their own precondition failed — the sentence outlives the caveat.
32. **Before comparing two predictors, check that both VARY in the stratum you will compare them in.** The
    intra-burst measure was contrasted against burst suppression across two whole ledger entries before
    anyone checked that the flag is present in **100.0 %** of the patients who carry the measure. It was not
    a comparison of two predictors; it was a comparison of two cohorts. **A measurement's availability
    defines a stratum, and that stratum is selected on exactly the thing that makes the measurement
    possible.** One `Counter` over the analysis cohort, before the design, would have caught it.
33. **A ratio of adjacent windows does not test locality.** The hypothesis was a *discontinuity* at 72 h; the
    statistic was `mean h(days 2-4) / mean h(days 5-7)`, which any steeply-decaying hazard wins with no
    discontinuity anywhere. If the claim is "a bump at day X", the statistic must be a **second difference**
    — `h[d]` against its own neighbours — not a contrast of two blocks. **Write down what shape the null
    produces before choosing the statistic.**
34. **A placebo cut is worth more than the primary test, and it must GATE the verdict, not sit beside it.**
    R410's primary passed on every pairwise comparison and was meaningless, because the same statistic fired
    at an arbitrary day where no guideline acts. A test with no placebo is a test with no denominator.
35. **When a subsetting analysis attenuates something, resample a matched subset that is NOT subset on the
    variable of interest.** Matching n, event rate and covariate composition, with no landmark applied, put
    the null at ~100 % everywhere — which is what made every departure readable as "who was removed" rather
    than "how many". This control is cheap and it should be standard for any landmark or restriction claim.
36. **Credential precedence, third occurrence.** The sandbox exports `AWS_ACCESS_KEY_ID` as a 14-character
    `prox…` proxy token that outranks `~/.aws/credentials`, and the failure reads as `InvalidAccessKeyId` —
    indistinguishable from expiry. `common/awsenv.py` now drops it (only when it provably is not an AWS key
    id and a shared credentials file exists) and the 53 S3 scripts call it. **An `unset` in `~/.bashrc` does
    nothing here** — the tool's shells are non-interactive and never source it. That was tried first.

---

## SOP: the ten-result cadence (STANDING)

Every **~10 new results** logged to `docs/research/41_RESULTS_LEDGER.md`, stop generating and consolidate:

1. **Re-read the whole ledger**, not the recent rows. The constraint table is the working object.
2. **Brainstorm mechanisms against the FULL constraint set** — every candidate must state which constraints
   it explains, which it *struggles* with, and one falsifiable prediction. A candidate that only explains the
   positives is not a candidate.
3. **Literature check on the leading candidates** — NCBI E-utilities, never WebFetch.
4. **Opus verifies** every number and citation that will be reported, then re-ranks the queue.

**A finding that retrodicts a standing negative is worth more than one that adds a positive.** The aetiology
reversal explains N10, which it was not built to explain; that is the property to look for. Record predicted
win-likelihood next to actual outcome in the ledger — the accumulating calibration record is how the
discrimination develops. To date this project has over-predicted three redundant measures and under-predicted
one real effect, all for the same reason (rule 28).

---

## Which documents are current

| document | status |
|---|---|
| `docs/research/41_RESULTS_LEDGER.md` | **live** — 392 results, the constraint table, the primary record |
| `docs/LESSONS.md` | **live** — accumulated memory; append after every experiment, negatives included |
| `docs/EXPERIMENT_QUEUE.md` | **live** — prioritised backlog, re-ranked 2026-07-27 |
| `docs/research/48_RESEARCH_LANDSCAPE.md` | **live** — what this data can and cannot settle, with feasibility counts |
| `docs/research/49_HANDOFF_STATE.md` | **live** — where work stopped, what is verified, what is open |
| `docs/research/47_BSP_TECHNICAL_NOTE.md` | **live** — self-contained, publishable methods note |
| `docs/research/45_MANUSCRIPT.md` | **live but predates R358–R392** — check against the ledger before quoting |
| `docs/MORGOTH_INTEGRATION.md` | live — wire-up checklist; the model remains unobtainable |
| `docs/RUNBOOK.md`, `docs/HEEDB_UNLOCK.md`, `docs/HANDOFF.md` | live — real-data procedure and pipeline handoff |
| everything else in `docs/` | **legacy from unrelated projects — ignore unless specifically directed** |

---

## Repo map

```
config.yaml            single source of truth for the phenotype pipeline (PHASE flag, seeds, sites, params)
cli.py                 phenotype pipeline: validate | preflight | pass1 | phase1 | freeze | phase2 | demo
common/ guards/        hashing, config validation, audit log, the held-out firewall  (stdlib only)
pipeline/ phase2/      the frozen-backbone phenotype pipeline (cold storage: tested, not the active thread)

analysis/              THE ACTIVE WORK. ~110 scripts. Naming: heedb_* | icare_* | vitaldb_* | bsp_*
  bsp.py                          BSP state-space estimator (damped Newton; the damping is load-bearing)
  bsp_validate_exact.py           independent exact grid forward-backward — catches what unit tests cannot
  bsp_window_sweep.py             simulation sweep: where BSP stops being a threshold ratio
  bsp_window_real.py              the same question on real EEG, scored by forward prediction
  heedb_flag_burden_nonlinear.py  R388 — the slowing-flag residual is not a functional-form artefact
  heedb_thalamocortical_test.py   R389 — the aetiology fork
  heedb_content_sign_flip.py      R390-R391 — the reversal and its red-team
  heedb_content_by_aetiology.py   R392 — the corrected decomposition (read A3, not A1)
  heedb_flag_vs_expert.py         R385 — why MORGOTH's labels cannot validate the slowing flag
  icare_topography.py             one S3 pass -> topography + per-second suppression series
  icare_seq_gap_check.py          finds glued-together dropouts
  icare_seq_exclusions.py         builds the keep-list from WFDB headers, checks outcome-relatedness
  icare_multiday_trend.py         R378 — across-days trend, the surviving mechanism candidate
  icare_inference_calibration.py  negative control for diff_ci and oob_increment
scripts/heedb_run.sh   REQUIRED wrapper for anything touching S3 (see Credentials above)
tests/                 integrity core (stdlib) + analysis/e2e/DSP/transport (skip without the sci stack)
```

**NOT part of this project:** `health_check.py`, the `test` stub, and the trading workflows under
`.github/workflows/` (`collect/live/health/kalshi-*/sports-clv/etf-paper/strategy-*/wallet-track`). Only
`.github/workflows/eeg-phenotype-tests.yml` is ours.

---

## Conventions

- **Heavy deps are lazy.** numpy/scipy/sklearn/mne/torch/boto3 import *inside* functions so the integrity core
  imports and tests with the stdlib only.
- **Everything is content-hashed** in the phenotype pipeline. Use `common/hashing` (canonical JSON,
  `allow_nan=False`). "Frozen" means the hash is recorded and re-verified.
- **Config-driven and deterministic.** Never use `hash()` for seeding — Python salts string hashes per
  process, which silently breaks reproducibility and only for the randomised paths.
- **Analysis scripts carry their pre-registration in the module docstring**, written before the run and
  committed before the result exists. Predictions, the falsification condition, and the scope limit are all
  stated up front. **This is the project's core integrity practice — keep doing it.**
- **Preprocessing:** mne reads EDF in **volts**; models expect **µV** (×1e6). Never z-norm amplitude away.
- **The firewall is load-bearing** in the phenotype pipeline. Route every site label through
  `HeldoutGuard.check_site_access`; never add an outcome-bearing column to a Phase-1 loader.

## Commands

```bash
make test-integrity                      # stdlib-only firewall/hashing/guard tests, fast, no deps
make test                                # full suite (needs numpy/scipy/sklearn/statsmodels/mne)
python cli.py demo                       # phenotype pipeline lifecycle on synthetic data
python cli.py preflight                  # check creds/network/deps before a live run
scripts/heedb_run.sh python analysis/X   # anything touching real credentialed data
```

Branch: **`claude/heedb-eeg-phenotype-discovery-2mnwzx`** — develop, commit and push here.
Run `git config user.email noreply@anthropic.com && git config user.name Claude` or commits show as
unverified on GitHub.
