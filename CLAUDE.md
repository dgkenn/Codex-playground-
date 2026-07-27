# CLAUDE.md — guide for Claude Code sessions in this repo

## What this project is
Implementation of a **pre-registered, two-phase, unsupervised EEG phenotype
discovery study** on HEEDB (Harvard EEG Database) using an adapted frozen
foundation model (**MORGOTH 1.0**, the HEEDB-pretrained clinical-EEG model;
CBraMod/LaBraM/EEGPT/BIOT are secondary alternatives), with hospital-split
confirmation and external replication on TUH. The canonical protocol is
`HEEDB_rawSSL_phenotype_discovery_preregistration_v3.md`; the section→code→test
map is `docs/SPEC_TRACEABILITY.md`.

NOTE: the protocol is at **v3** (MORGOTH backbone + redundancy/novelty control +
non-circular Phase-2 outcome). **CBraMod is the validated OPERATIONAL backbone**
today (real weights, sha256-pinned, runs end-to-end on real HEEDB data); MORGOTH
is the v3 target and a clean future swap — its code+weights are not yet public
(repo 404s; paper in press). The redundancy/novelty control and the
`model_outputs` task-output persistence are already built and tested (no-op for
CBraMod); see `docs/MORGOTH_INTEGRATION.md` for the wire-up checklist.

**Binding integrity principle (do not weaken):** Phase 1 (discovery) uses **no
outcome label**. Phase 2 tests **one** pre-registered outcome on a **held-out
hospital never touched in Phase 1**, with four objects (model checkpoint,
harmonization config, embedding-correction transform, phenotype-assignment
function) **frozen + hash-verified** before the held-out data is unlocked. Any
breach voids confirmatory status.

## SOP: model delegation and token budget (STANDING — applies to every session)

Research on this repo is token-expensive and has come close to the weekly usage cap. **Opus is the orchestrator
and the reviewer, not the labourer.** If a task is bulk reading, bulk searching, bulk editing, or mechanical
transformation, it should not be done in the main Opus context.

| task | model | why |
|---|---|---|
| Orchestration, experiment design, deciding what to run next, final synthesis, anything that becomes a **reported number or a committed claim** | **opus** (main) | judgment that the whole result rests on |
| Red-teaming a document or result, code review, literature triage, drafting prose, interpreting ambiguous output | **sonnet** | needs judgment, but is checkable afterwards |
| Mechanical and verifiable: applying a precise edit spec across files, running a script and extracting fields, counting/tabulating, grepping a large tree, log triage, boilerplate | **haiku** | cheap, and correctness is checkable by inspection |

**The review rule, which is not optional.** Any subagent output that will become a reported number, a claim in a
document, or a commit must be **verified by Opus against the raw source** before it is used. Subagents are
useful and they are also wrong often enough to matter: in the 2026-07 red-team pass, two of six findings were
wrong because the agent only had the log files and not the underlying data — and it was right about four,
including a real self-contradiction and an untested comparison in the headline claim. So: delegate the work,
never delegate the acceptance.

**Practical token discipline in the main context:**
- Never `cat` a large file. `head`/`tail`/`grep`/`sed -n 'a,bp'` to the specific lines. Reading a 1 GB CSV into
  context is never correct — compute over it in a script and print a summary.
- Long analyses write to `/tmp/<name>.txt`; read back only the result lines, not the whole log.
- Background anything over ~2 minutes (`run_in_background`) and poll with a cheap `until` loop. Do not sit in
  foreground sleeps.
- Do not re-read a file already read this session, and do not re-read a file just edited to confirm the edit.
- Prefer one batched shell call that prints several small things over several round-trips.
- **Never read a subagent's raw transcript file** — it will overflow the context. Use its returned result.

## SOP: the error catalogue (STANDING — read before designing any analysis)

Every rule below was paid for with a wrong result in this project. They are ordered by how often the mistake
recurred, not by how clever they sound.

### A. Correction discipline — the mistakes that repeated most

1. **A correction propagates to everything downstream, not just the number that prompted it.** The ICD-code fix
   changed the cohort from 2,951 to 2,463; the headline was re-run immediately, but the landmark analysis, the
   morphology directions and the figures stayed contaminated until someone went back for them. **When a
   definition changes, list every claim that depends on it before re-running anything.**
2. **Numbers inherited from a superseded extraction must be re-derived, never carried forward.** Happened
   twice: morphology contrasts quoted from the legacy max-over-recordings run (every magnitude inflated, one
   sign inverted), and the manuscript quoting pre-correction quintiles.
3. **Stale claims survive in earlier sections.** Corrections were appended as new sections while §2 still read
   as current. Put the withdrawal at the point a reader would rely on the claim, not only at the end.
4. **Hardcoded literals in captions, titles and prose go stale silently.** A figure title said "2.5-fold"
   through a correction that made it 2.3; a caveat hardcoded 40.6 % after the value moved to 46.0 %. **Compute
   every number that appears in output, including in labels.**

### B. Silent failure — wrong answers that arrive looking like nothing

5. **Empty is not evidence of absence until the filter has been shown capable of matching something.** Three
   separate times an error surfaced as an empty file: a text regex ANDed with a concept-id filter, an unmapped
   `concept_id` column, and a CSV predating the columns being read. **Assert non-empty, or assert the filter
   matches a known positive.**
6. **Check that a `concept_id` column is populated before designing around it.** `observation_concept_id` was
   100 % zero. One `Counter` over 100k rows would have shown it in seconds.
7. **Before choosing an administrative table as an instrument, ask what makes a row appear in it.** Billing
   tables see reimbursable acts; state tables see charted statuses; **neither sees decisions**.
   `procedure_occurrence` contains zero extubations because extubation is not separately billable.
8. **An access failure may be credential *precedence*, not expiry.** A 403 came from placeholder env
   credentials outranking a valid profile. Diagnose with `sts get-caller-identity` **per credential source**.

### C. Statistical rules

9. **Bootstrap AUC increments out-of-bag.** Train on the resample, evaluate on the patients *not* drawn.
   Bootstrapping fixed out-of-fold predictions ignores refit variance and gave a falsely narrow +0.100
   [+0.082, +0.118]; refitting *and* evaluating on the same resample puts patients in train and test and
   produced a point estimate outside its own interval. **Both were used here and both were wrong.**
10. **Any per-patient aggregation over repeated measurements is look-ahead until proven otherwise.** `max()`,
    `or`, and bare assignment across rows all leaked; in a survival analysis the *number* of measurements is
    itself an outcome. The pattern was in 17 scripts.
11. **Sign the bias separately for every analysis a shared bug touches.** "Conservative" was established for
    one estimand and did not transfer — the same defect ran the *other* way in the landmark analysis.
12. **Predictive increment cannot identify a mechanism when the measure is noisy.** Two readings of a
    *constant* beat one reading. Decompose into `mean` and `difference` and test the **sign** of the difference
    term; noise cannot produce a correctly-signed non-zero coefficient.
13. **Never "fix" a confound by conditioning on a post-exposure variable.** That is a collider and can
    manufacture a sign reversal.
14. **Report exclusions and check whether they are outcome-related.** Burst morphology is undefined below four
    bursts, which happens at near-total suppression — 13.2 % of patients excluded, at 80 % vs 60 % poor outcome.
15. **Discrimination without calibration is half a result**, and the missing half is the half clinicians use.

### D. Reading the evidence

16. **When two arms of the same test disagree in SIGN, the definition is doing the work, not the biology.**
17. **When a fix makes the effect stronger, the diagnosis was wrong** — that is a refutation of the
    explanation, not a refinement of it.
18. **Uniformity across strata whose clinical handling is known to differ is evidence AGAINST validity**, not
    for robustness. A median of 0.0 h in every aetiology exposed a charting artefact.
19. **Before two measures can corroborate each other, check whether one row can satisfy both definitions.**
20. **When two scripts compute the same quantity, diff them even if only one is published.** The unpublished
    one is a free replicate, and disagreement localises to a definition.
21. **Run the literature check BEFORE the analysis when the prediction rests on a premise about a specific
    disease.** "Dead cortex cannot seize" is sound physiology and false after cardiac arrest; one E-utilities
    query would have killed the design before it was built.

### E. Verification

22. **A validity figure living in a code comment is not a validity figure.** "AUC 0.829" in a comment was not
    reproducible; measured properly it is 0.749.
23. **Self-written code plus self-written tests share blind spots.** Validate against an *independent*
    implementation — an exact solver caught a 0.775 deviation that seven unit tests missed.
24. **Delegate the enumeration, verify the classification — and spot-check the calls the agent rated LOW
    risk.** That is where a miss is most costly.
25. **Verify every citation from the MEDLINE record via E-utilities.** WebFetch fabricates PubMed content under
    CAPTCHA; it cost this project six wrong citations once. Verifying a "contradicting" paper myself revealed
    its own headline effect failed its own adjustment — which changed the conclusion.

---

## SOP: the ten-result cadence (STANDING)

Results accumulate faster than interpretation does, and a mechanism is only worth proposing if it explains the
NEGATIVES as well as the positives. So every **~10 new test results** logged to
`docs/research/41_RESULTS_LEDGER.md`, stop generating and do a consolidation pass:

1. **Re-read the whole ledger**, not the recent rows. The elimination table at its top is the working object.
2. **Brainstorm mechanisms against the FULL constraint set** — delegate to sonnet, giving it every constraint
   including the negatives and the surprises, and require each candidate to state which constraints it explains,
   which it *struggles* with, and one falsifiable prediction. A candidate that only explains the positives is
   not a candidate.
3. **Literature check on the current leading candidates** — delegate, and require NCBI E-utilities rather than
   WebFetch, which fabricates PubMed content when the site serves a CAPTCHA (see LESSONS).
4. **Opus verifies** every number and citation that will be reported, then re-ranks the queue.

The point of the cadence is that the constraint set does the work: each negative result narrows the space more
than a positive one does, and the narrowing is only visible when the results are read together.

## Repo map (this project)
```
config.yaml            single source of truth (PHASE flag, seeds, sites, params, data.s3, TUH)
cli.py                 entry point: validate | preflight | pass1 | phase1 | freeze | phase2 | tuh-test | demo
common/                hashing, config validation, audit log   (stdlib only)
guards/heldout_guard.py the firewall (blocks held-out while phase==1; hash-stamped unlock)
pipeline/              Pass 1: stream_fetch (BDSPS3Client / TUHRsyncClient / LocalEDFClient),
                       harmonize, embed (CBraMod), features (DSP), writer, run_pass1
analysis/              correct_sites, site_probe (gate), cluster, phenotype_bar, characterize,
                       audits, run_phase1 (orchestrator)
phase2/                freeze (4 objects) -> run_phase2 (unlock -> cross-site -> single run-once test)
demo/synthetic.py      full synthetic lifecycle (no creds/model) -> `python cli.py demo`
tests/                 test_integrity (stdlib) + analysis/e2e/DSP/transport (skip w/o sci stack)
docs/                  SPEC_TRACEABILITY, RUNBOOK (real data), GO_LIVE, HANDOFF
scripts/setup_cloud.sh setup script for the cloud env
```

## NOT part of this project (leftover playground; do not touch)
`health_check.py`, the `test` stub file, and the trading workflows under
`.github/workflows/` (`collect/live/health/kalshi-*/sports-clv/etf-paper/
strategy-*/wallet-track`). Only `.github/workflows/eeg-phenotype-tests.yml` is ours.

## Conventions
- **Heavy deps are lazy.** numpy/scipy/sklearn/mne/torch/boto3 import *inside*
  functions so the integrity core + guards import and test with the stdlib only.
- **Everything is content-hashed.** Use `common/hashing` (canonical JSON,
  `allow_nan=False`). "Frozen" means the hash is recorded and re-verified.
- **Config-driven + deterministic.** All params/seeds in `config.yaml`; nothing
  that can change a result lives in code. `TO-CONFIRM` = must be pinned before
  the relevant stage (checkpoint sha256, primary phenotype, BDSP catalog schema).
- **The firewall is load-bearing.** Route every site label through
  `HeldoutGuard.check_site_access`; never add an outcome-bearing column to a
  Phase-1 loader (`assert_no_outcome_in_loader_fields` enforces this).

## Commands
```bash
make test-integrity      # stdlib-only firewall/hashing/guard tests (fast, no deps)
make test                # full suite (needs numpy/scipy/sklearn/statsmodels/mne)
python cli.py demo       # full synthetic lifecycle end-to-end
python cli.py preflight  # check creds/network/deps before a live run
```
106 tests green. Branch: `claude/heedb-eeg-phenotype-discovery-2mnwzx`.

## Running on real data
See `docs/RUNBOOK.md` (full procedure) and `docs/HANDOFF.md` (continuing in a new
desktop session). Real HEEDB/TUH access is credentialed (the user's own AWS keys
/ NEDC SSH key) and is supplied at runtime — never committed. The CBraMod
forward pass **is now validated on real weights + real HEEDB EEG** (see
`docs/HEEDB_UNLOCK.md`): weights sha256-match the pin, load with 0 missing keys,
and embed a real EDF end-to-end. Preprocessing lesson: mne reads EDF in **volts**;
CBraMod expects **µV** (×1e6) — never z-norm the amplitude away.

## Autonomous research machine (READ THIS FIRST every session)
This repo runs as a 24/7, self-learning, publication-focused research loop. Before doing any work:
1. Read **`docs/RESEARCH_MACHINE.md`** — the operating protocol (mission, self-learning loop, impact bar,
   guardrails, and the model-delegation policy).
2. Read **`docs/LESSONS.md`** — accumulated memory (what we know / what's ruled out). Never repeat a dead
   end. **Append a new lesson (with mechanism) after every experiment — negative results included.**
3. Read **`docs/EXPERIMENT_QUEUE.md`** — the prioritized backlog. Pull the top item that fits compute.
4. Read **`docs/IDEA_GATE.md`** — the idea DISCRIMINATOR (from ~40 run ideas). Not a hard filter: **score &
   RANK candidates by win-likelihood and flag the obviously-bad before spending compute; then use judgment.**
   Strongest signals = a ground-truth reference in the data + a named direction-predicting mechanism + a
   sharp falsifiable quantitative prediction. **Calibrate:** record your predicted win-likelihood next to
   the actual outcome in the ledger — that accumulating predicted-vs-actual record is how the ability
   develops. When depth on a mined seam stalls, hunt for new (mechanism + reference + driver) triples.
Then discriminate/rank → run → red-team (sonnet) → log lessons + prediction → update queue/ledger → commit+push.
**Delegate per the SOP at the top of this file** — haiku for mechanical/checkable, sonnet for judgment/red-team,
opus for orchestration + synthesis + verifying every number before it is reported.
Mission bar: **ultra-high-impact, externally-validated** findings; current white space =
first cross-site-validated EEG-foundation-model → clinical-outcome study (GPU-gated).
