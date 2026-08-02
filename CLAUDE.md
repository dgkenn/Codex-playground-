# CLAUDE.md — guide for Claude Code sessions in this repo

*Last updated 2026-07-29 at result R418. If you are a new session, read this file top to bottom before
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
VitalDB.** It has produced **418 logged results** and one substantive lead (below). Everything of scientific
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

**(0) READ THIS BEFORE DESCRIBING THE LEAD AT ALL — R417/R418 corrected what it is a claim ABOUT.** The
paragraph above says "intra-burst EEG content", which reads as *how much fast activity there is*. That is
**wrong**, and the correction is not cosmetic. **Absolute band power does not reverse** — more absolute fast
power, and more absolute slow power, are each **protective in BOTH aetiologies** (fast: anoxic AUC 0.390 /
non-anoxic 0.403; slow: 0.371 / 0.445, all four excluding 0.5). What reverses is the **RATIO** — the
*balance* between fast and slow — which correlates **+0.002** with absolute fast power and retains **117 %**
of its interaction after adjustment for both absolute powers *and* their interactions. **State the lead as a
reversal in SPECTRAL BALANCE, orthogonal to signal amount. Never as "more fast activity kills after
anoxia".** Alpha and beta each carry it independently and equally (+0.343 / +0.340, summing to the
composite's +0.690 — additive to within 1 %), so do not describe it as an alpha phenomenon either.

(3) **R414:** the reversal is **not a sedation artefact** — it survives where no burst-suppression-capable agent was running (n = 286, interaction +12.6 [+7.8, +19.7]) and is about **twice as wide on AUC** there (gap 0.308 vs 0.151), i.e. strongest where the suppression is pathological rather than drug-induced.

---

## THE ACTIVE PROJECT AS OF 2026-07-29: bsde/ — Brain-State Discovery Engine

**As of 2026-07-29 the investigator's stated priority is a third project, `bsde/`, not the burst-suppression
programme above.** BSDE (Brain-State Discovery Engine) is an autonomous discovery-and-validation system aimed
at separating arousal, cognitive-processing capacity, command-following and behavioral output in EEG — not
another consciousness classifier, and explicitly not an attempt to own "an AI model for EEG." Its proprietary
asset is meant to be the **verifier** (a multi-layer proof-checker EEG measures do not otherwise have), not
any single biomarker, including its first candidate, UCE. Two applications sit on top of it in deliberately
different roles: the **wedge** is anaesthesia/perioperative EEG (commercially tractable now); the **flagship**
is covert consciousness / cognitive motor dissociation (the highest-value, highest-stakes target, not yet
reachable with public data).

**THE plan for this project is `/home/user/Codex-playground-/bsde/docs/MASTER_PLAN.md`.** Read it before
touching `bsde/`. It reconciles the three investigator-supplied briefs below with what has actually been
verified in the repo, and it is revised as results come in — unlike the briefs, which never are.

The three immutable investigator briefs — **never edit these, regardless of what analysis later finds**:
- `/home/user/Codex-playground-/bsde/docs/RESEARCH_PROGRAM_BRIEF.md` (Brief 01 — the scientific question)
- `/home/user/Codex-playground-/bsde/docs/BRIEF_02_DATASET_STRATEGY.md` (Brief 02 — which datasets, and why)
- `/home/user/Codex-playground-/bsde/docs/BRIEF_03_AI_DISCOVERY_LAB.md` (Brief 03 — how the AI research loop works)

**Standing rule for this project: the verifier is built before the search.** Candidate representations (UCE
or anything after it) are only worth reporting once they have cleared the verifier's layers — do not let a
biomarker result outrun the machinery that checks it.

**The burst-suppression programme above continues and is not being wound down** — R418 and everything in
`docs/research/` remains live and correct. `bsde/` is now a **second active thread alongside it, not a
replacement for it.** Check which project a task belongs to before applying either project's conventions —
the two have separate docs, separate ledgers, and separate error catalogues; do not cross-apply findings or
SOPs between them without checking they actually transfer.

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

### The container RESTORES FROM A SNAPSHOT on restart — this is the single most disruptive fact about working here

**Diagnosed 2026-07-29 after it happened five times in one session.** `/tmp` and the repo working tree are
both rolled back to a snapshot (that day: `/tmp/eeg_probe` at Jul 27 01:45, `.git` at Jul 27 14:18). It is
**not** a size-based reaper — a 1 MB file created this session vanished alongside a 3.3 GB one, while Jul
25–26 files of every size survived. Age relative to the snapshot is what matters.

Three consequences, all of which cost time before the mechanism was understood:

1. **Any cache built this session will disappear**, so budget for rebuilding rather than assuming
   persistence. There is no durable local store — a gitignored path in the repo is rolled back too.
2. **`git` gets rolled back with it.** A push that fails as non-fast-forward usually means this, not a real
   divergence. **The remote is the source of truth.** Recover with
   `git fetch origin <branch> && git rebase origin/<branch>` — do NOT reset away the remote's commits.
   Committing and pushing after every result is what makes this survivable; it has cost nothing but a rebase
   each time.
3. **Prefer small derived caches.** `analysis/heedb_aetiology_compact.py` reduces the 3.3 GB condition table
   to a ~1 MB per-patient table (one column per aetiology group) and rebuilds itself from the big table on
   first use; prefer `load_anoxic()` from it over parsing `condition_occurrence.csv` directly. It still
   vanishes on restart, but rebuilding it from a surviving big table is seconds rather than 22 minutes.

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

### Delegation SOP for `bsde/`

The delegation table and the review rule above apply to `bsde/` exactly as written — no separate SOP for this
project. In particular: designing or interpreting a verifier layer, ranking candidates, and anything that
becomes a claim in `MASTER_PLAN.md` or `RESEARCH_STRATEGY.md` is **opus** work, and any subagent output feeding
one of those documents is **verified by Opus against the raw source** before it lands there — a verifier that
has not itself been checked is not a verifier.

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
37. **A permissive comparison operator quietly converts a null into a pass — check the VERDICT code as
    carefully as the analysis code.** Two consecutive results shipped a wrong printed verdict. R415 evaluated
    the placebo *before* the primary, so a clean refutation printed as "not interpretable". R416's `sign()`
    counted a CI spanning 0.5 as satisfying "protective" (`s in (-1, 0)`), and its placebo check asked
    whether the placebo attenuated *a lot* instead of whether it attenuated *more than the variable of
    interest*. Both bugs made a failing test print as passing. **Rules that fall out of this:** a cell that
    spans the null is neither direction and must not satisfy a directional criterion; a placebo gate is a
    COMPARISON against the real effect, never an absolute threshold; and the primary is evaluated before any
    gate, because a gate can only invalidate a pass, never rescue a null. Write the verdict branch to state
    the failing case first.
    **THIRD OCCURRENCE, 2026-07-31, and this time it was the PLACEBO's own null test that was one-sided.**
    E40 asked per band whether an AUC interval excluded chance and wrote it as `lo > 0.5`. Its placebo then
    printed "at chance" in every band while the incumbent scored **0.237 [0.115, 0.418]** against a *fake*
    landmark — an interval lying entirely **below** 0.5, which is discriminable, not null. Two-sided, the
    placebo fired in 5 of 7 gated bands, and the design turned out to have a second fatal flaw that the
    operator had hidden. **A placebo can fire in EITHER direction, because whatever confound it exposes has
    no reason to share the real effect's sign** — E40's position confound separated its classes in reverse,
    which is precisely what a position confound does. So: `excludes_null` is always two-sided, `above_null`
    is a separate and narrower question, and one name must never do both jobs.
    **FOURTH OCCURRENCE, 2026-07-31, and the most expensive yet — a REFUTATION printed as a CONFIRMATION.**
    E43 tested whether BIS is more muscle-contaminated than a spectral slope, as an asymmetry of two
    partial correlations. Its registered verdict rule enumerated "interval includes zero" and "excludes
    zero and beats the placebo" — **and never contemplated excluding zero on the WRONG side.** The code
    tested `lo > 0 or hi < 0` and printed CONTAMINATION over `partial(BIS,EMG|state) = +0.165` against
    `partial(state,EMG|BIS) = -0.262`, an asymmetry of **-0.0967 [-0.1798, -0.0100]** that refutes the
    hypothesis. The placebo compounded it: with both asymmetries negative, `asym > q` was satisfied by
    being *less* negative and printed "muscle-specific". Caught by reading the numbers rather than the
    label. **A verdict rule must ENUMERATE THE WRONG-DIRECTION CASE EXPLICITLY**, because "excludes the
    null" and "supports the hypothesis" are different questions and a confidence interval only answers the
    first. Three prior entries were not enough to prevent it; write the sign into the branch, not the
    prose.
    **FIFTH OCCURRENCE, 2026-07-31 — the gate was unreachable because of the STATISTIC'S GRANULARITY, and
    the fix is to compare against the placebo's DISTRIBUTION rather than its mean.** E75's registered
    branch (c) was "NOT INFORMATIVE — the label-permutation placebo reproduces the agreement rate", coded
    as `abs(real - 0.5) <= abs(placebo_mean - 0.5)`. Both halves fail. `placebo_mean` is an average over
    300 draws and sits at ~0.500 *by construction*, so the right-hand side is ~0; and `real` is a fraction
    over an **odd** number of testable features, so it can never equal 0.500 either. **The branch could not
    fire for any data.** It printed SPLIT — "Challenge A's candidate list" — over 4 agreements in 7
    features, which is exactly the median of a Binomial(7, 0.5); against the placebo *distribution*,
    **0.487 of draws reach that rate or better**. A pure null had been about to be written up as the
    informative outcome. **Rules that fall out: a placebo comparison is against the placebo's
    DISTRIBUTION, never its mean — a mean placebo is a point with no width and every real value differs
    from it. And before trusting any verdict branch, ask what VALUES the statistic can actually take:
    a rate over 7 items takes 8 values, none of them 0.5, so any branch keyed to 0.5 is dead code.**
    Fixing this made the test stricter after seeing a pass, which is the safe direction and the only one
    that does not need permission; a fix that loosens a gate after a failure is the move
    `DISCOVERY_LOOP.md` §2 forbids.
50. **MEASURING A DIFFERENCE IS NOT MEASURING ITS CAUSE — GET THE BASELINE BEFORE YOU NAME THE MECHANISM.**
    Three corrections in one day, all the same shape: an effect was measured and a *cause* was asserted
    without the control that would separate causes.
    * **E46** compared candidates against BIS on rows selected by BIS, and called the gap robustness. The
      selection rule alone forced it (rule 49).
    * **E53** compared one deposit under two pipelines, measured a floor of **0.898**, and called it a
      *pipeline effect*. The same-pipeline baseline — 60 subjects × 3 sessions through identical code —
      puts single-measurement retest noise at **0.667**, so a displacement's noise is
      √2 × 0.667 = **0.943**. Ordinary noise accounts for the whole thing and **nothing is left for
      pipeline**. The wrong attribution pointed at an expensive and useless remedy (re-extract every
      deposit through one path) instead of the real one (**more subjects, or more data per subject —
      harmonisation cannot shrink a noise floor**).
    * **E50** claimed a mechanism that `MASTER_PLAN.md` §9.13 had already established, because the
      project's own record was never searched.
    **The habit that prevents all three costs one extra measurement: before attributing a difference to
    X, measure the difference when X is held constant — AND MATCH THE BASELINE'S STATISTICAL STRUCTURE TO
    THE EFFECT'S.** The E53 correction above was itself retracted within the hour because it compared a
    *cohort-mean* difference (0.898, same subjects, so sampling noise cancels) against a *per-subject*
    mean absolute change (0.667, where it does not), and multiplied the wrong quantity by √2. The
    structurally matched control — a cohort-mean shift between sessions on the same subjects — is
    **0.242**, and E53's original attribution to pipeline was right all along. **A baseline of the wrong
    shape is worse than no baseline, because it carries the authority of a measurement.** Same-pipeline retest, same-selection placebo,
    same-drug floor. If the baseline reproduces the effect, the attribution is wrong no matter how
    plausible the mechanism sounds — and the plausible mechanism is exactly what stops you checking.
    **Corollary for search:** an internal record is a source like any other, and rules 25 and 39 apply to
    it. Grep the ledger and the plan before claiming a finding is new.
49. **A RULE-40 TEST THAT ONLY COVERS THE AUXILIARY GATES IS NOT A RULE-40 TEST — THE PRIMARY IS WHERE THE
    CLAIM LIVES.** E46 shipped with a six-test file written explicitly to check that its gates could fail.
    Every one of those tests covered the capability gate or the case-count gate. **None asked whether the
    PRIMARY could fail, and it could not.** The design selected its artefact windows by `BIS >= 80` and
    then compared `|delta_BIS|` against each candidate — but selecting on BIS mechanically forces
    `delta_BIS >= (80 - mean_ref)/sd_ref`, a per-case mean of **4.584** against an observed **5.813**,
    while every candidate is unconstrained and must land beneath it. Six candidates out of six returned
    ROBUST. **The uniformity was the only warning** (rule 18), and it is a weak one — six passes reads as
    a strong result until you ask what a failure would have looked like.
    **The check that catches this costs one calculation: before running a comparison, compute what the
    statistic is FORCED to be by the selection rule alone, and compare it to the observed value.** If they
    are close, the comparison is measuring its own selection rule. The corrected arm moved the selection
    onto a variable the incumbent played no part in (EMG's top decile) and immediately produced a
    failure — `spectral_edge_95`, CI [-0.378, +1.079]. **A test that nothing fails is not evidence that
    everything passed.** Corollary, and it generalises past selection bias: **never select rows on the
    incumbent you intend to beat.**
60. **A MEASURE CHOSEN FOR BELONGING TO A DIFFERENT FAMILY MUST BE SHOWN TO DIFFER FROM THAT FAMILY —
    RULE 28 RUN IN REVERSE.** Rule 28 warns against assuming two measurements are measuring different
    things. This is the mirror error and it is easier to make, because the whole point of the design is
    that the new measure is *different in kind*. **E73** existed because every Challenge B candidate this
    project had run was an amplitude summary, and its pre-declared primary was
    `wpli_alpha_global_efficiency` — a graph measure, chosen precisely to escape that family. Across the
    62 subject means it correlates with `wpli_alpha_mean_degree` at **+0.9962** and with plain
    `wpli_alpha` at **+0.8639**. On an unthresholded weighted graph shortest paths are dominated by direct
    edges, so global efficiency is mean connectivity strength restated, and the "network" test was a re-run
    of the connectivity test. The null it returned is real and it is *not* a null about network topology.
    **The check costs one correlation matrix and must run BEFORE the registration: correlate the new
    measure against the family it is supposed to escape, on the same units the design will use.** If it
    lands above ~0.9 on anything already tested, the design has not changed its instrument (see rule 58's
    successor requirement) and the registration should say so or pick something else. The one measure in
    E73's family that WAS nearly orthogonal to the primary (`wpli_alpha_clustering`, −0.076) is also the
    only one that behaved differently — which is the pattern to expect and the reason the check is worth
    its cost.

61. **SUBSTRING-MATCHING A STRUCTURED IDENTIFIER IS NOT PARSING IT, AND IT MISLABELS STATE SILENTLY.**
    E87 assigned each recording to `awake` or `anaesthetised` by testing whether a token appeared anywhere
    in the recording id. Both deposits were mislabelled and neither raised anything. On **ds004541**, whose
    ids are offsets around loss of consciousness (`@start-180`, `@loc-300`, `@loc+30`), the anaesthetised
    token `loc` matched `@loc-300` — **300 seconds BEFORE** the event — so the anaesthetised set contained
    pre-LOC recordings. On **ds005620**, whose ids are BIDS (`task-sed2_acq-rest_run-1`), the awake token
    `rest` matched `acq-rest` **inside a sedated recording**, so the awake set contained sedated ones. The
    two failures have one cause: a BIDS filename or an offset label is a STRUCTURED string with fields,
    and `token in name` reads across the field boundaries. **Parse the entity (`task-`, the sign of the
    offset) and match the parsed value; never substring-match the whole identifier.** Both errors were
    caught only because an unrelated gate refused the run — nothing in the state assignment itself could
    fail, which is rule 40 in the labelling step rather than in the verdict.

62. **A PERCENTILE IS ONLY INFORMATIVE INSIDE THE SUPPORT OF ITS REFERENCE — AN AWAKE-ONLY REFERENCE HAS
    NO RESOLUTION BELOW WAKEFULNESS.** E91 ran a seven-scheme bake-off for population referencing and rank
    (percentile) referencing won both axes: worst transport 0.298 against the z-scheme's 1.212, and the
    BEST discrimination of any autonomous scheme. E93 then placed twenty state strata on that coordinate
    and the sleep staircase collapsed: W +0.4674, N1 −0.2837, **N2 −0.5000, N3 −0.5000** — both pinned at
    the floor, along with VitalDB's BIS [20,60) bands and ds004541's whole anaesthetised arm. Everything
    below the awake reference's range maps to the 0th percentile and becomes indistinguishable.
    **E91 could not have seen this**, because it scored discrimination on a BINARY awake-versus-suppressed
    contrast, where saturation is free. The cost only appears against a GRADED outcome. **Two rules follow.
    A bake-off scored on a binary contrast cannot rank schemes that will be deployed against a graded one —
    match the outcome's granularity to the intended use. And build the reference over the RANGE YOU INTEND
    TO MEASURE**, not over the state you happen to call normal: an anaesthesia index needs anaesthetised
    recordings in its reference or it has no dynamic range exactly where it must work.

63. **A GATE THRESHOLD PICKED AS A ROUND NUMBER MEASURES THE ROUND NUMBER — DERIVE IT FROM WHAT THE
    MACHINERY CAN ACHIEVE.** Twice in one session a registered gate refused a run for a threshold chosen
    by habit rather than by arithmetic. **E92's G3a** required a recomputed score to match a stored one to
    `1e-9`; double-precision accumulation over a 20 s window at 5 kHz sits right at that scale, and the
    two deposits came in at **9.98e-10 and 1.05e-9** — either side by a few percent, so one passed and one
    was refused on float noise. **E95's G2** required the extreme-percentile fraction below `0.05`; three
    successively deeper references produced **0.5168 → 0.2028 → 0.0705**, every step halving saturation
    and improving transport, and the last was refused by 2 points of a criterion with nothing behind it.
    In both cases the *trend* was unambiguous and the *gate* was arbitrary. **Before registering a
    numerical gate, compute what value the machinery can actually reach** — the float precision of the
    arithmetic, the tail mass of the test distribution against a finite reference — and set the threshold
    from that, or state explicitly that it is a convention and cannot distinguish success from its own
    resolution. A gate is only worth its refusal if the refusal means something.

64. **A CONTRAST SPLIT AT AN EXTREMUM IS A TIME SPLIT IN DISGUISE, AND ONLY A RANDOM-SPLIT PLACEBO SHOWS
    IT.** E98 asked whether measures differ between descent and emergence at matched BIS, splitting each
    case at its own BIS minimum. **Seven of eighteen features returned a gap whose interval excluded zero
    — and all seven were withdrawn by the placebo**, including the aperiodic exponent itself at
    −0.159 [−0.247, −0.069]. The reason is arithmetic, not physiological: an extremum sits near the middle
    of a recording, so "before versus after the minimum" is very nearly "first half versus second half",
    and **any feature with a within-case time trend produces a gap that has nothing to do with the
    landmark**. Electrode drift, temperature, fluid shifts and cumulative artefact all supply one.
    **The placebo that reveals it re-splits at a RANDOM index while preserving the group sizes and every
    stratification** — destroying the landmark and nothing else. Without it this experiment would have
    reported seven direction-dependent measures. Applies to any before/after design keyed to a maximum, a
    minimum, a threshold crossing or an onset; rule 35's matched-subset control is the same idea for
    restriction designs.

65. **TWO EVENT FILES THAT AGREE WITH EACH OTHER CAN BOTH BE WRONG ABOUT THE SAMPLES — VALIDATE A MARKER
    AGAINST THE SIGNAL, NEVER AGAINST ANOTHER MARKER FILE.** ds005620's TMS recordings ship markers twice:
    the BIDS `events.tsv` and the native BrainVision `.vmrk`. **They agree to 0.2 ms**, which reads as
    corroboration and is not — they are two serialisations of the same upstream table, so agreement
    between them tests the export, not the timing. Measured against the waveform, **the marker windows sit
    at percentile 49.5 of randomly chosen windows, 0 of 15 above the 95th**, while the actual pulses are
    ~1,800× larger and stand 23,408 µV/sample above a 10.5 µV/sample background. The markers point
    somewhere else entirely. This cost four diagnostics because each earlier one had an innocent
    explanation available — an inflated baseline, a loose detector, an off-by-one — and only the
    random-window control (rule 5) settled it. **The check is one line: compare the statistic at the
    markers against the same statistic at random times.** Two independent ~2 s trains with different
    jitter never coincide, and nothing short of that control distinguishes "no response" from "wrong
    index". Related to rule 27: the time axis is the thing least often verified and most often broken.

66. **RULE 27 APPLIES TO THE FREQUENCY DOMAIN TOO: CONCATENATING SHORT SEGMENTS BEFORE A SPECTRAL
    ESTIMATE GLUES TIME TOGETHER.** Rule 27 was written about modelling transitions and it says an
    order-free summary is safe. **A power spectrum is not an order-free summary of the samples handed to
    it.** The perturbational extractor concatenated ~46 pre-pulse segments of 0.4 s and then ran Welch
    with a 1.0 s window, so every window straddled ~2.5 segment boundaries and each boundary injected a
    broadband step. The aperiodic slope it produced failed to separate awake from sedated (d_z −0.4765,
    right direction, not clearing its Gaussian control at n = 14) while **the same deposit, the same
    subjects and whole recordings gave d_z −0.9909, clearing comfortably**. The fix is to transform each
    contiguous stretch on its own samples and average only the resulting POWER SPECTRA — never the time
    series. Two lessons travel with this. First, **any window longer than the segment it is cut from is a
    bug, and the check is one comparison of two numbers**. Second, this was caught only because E103
    carried a positive control that failed; without it the experiment would have reported a clean-looking
    ABSENT and the bug would have survived into every successor. A design whose known effect is not
    tested cannot tell a null apart from a broken instrument.

67. **LINEAR DEFLATION CANNOT COUNT AXES, AND A SYNTHETIC ONE-AXIS CONTROL EXPOSES IT IN ONE RUN.**
    E115 reframed Challenge A from "is there a second axis?" (asked and answered no six times) to "how
    many are there?", by sequentially finding the leading stage-discriminating direction, scoring it on
    held-out SUBJECTS, deflating, and repeating until a within-subject permutation null was not cleared.
    It returned **5 axes** at out-of-sample discriminability 0.94/0.89/0.86/0.80/0.79 against nulls of
    ~0.02, unchanged with the EMG features removed. Every gate passed and it read as a clean positive.
    **A synthetic inventory built from ONE latent variable, viewed through 16 distinct monotone
    non-linearities, returned 5 axes from the same pipeline — and scored HIGHER: 0.98/0.98/0.97/0.93.**
    The cause is structural rather than a tuning problem: **a linear projection cannot remove an axis
    that features encode non-linearly**, so a battery of spectral and complexity summaries of one process
    re-presents the same axis in a new linear guise at every deflation step. Any deflation-based
    dimensionality count needs this control as its FIRST gate, and rank-based or kernel deflation is the
    minimum fix. The generalisation is rule 40's: **before believing a count, construct a system whose
    true count you know and check the procedure returns it.** Note also what the control bought beyond
    the refutation — the real data decayed FASTER than the one-axis synthetic, which is weak evidence
    toward one axis and would have been invisible without a reference system to compare against.

68. **VALIDATING THAT A DISCOVERY PROCEDURE WORKS IS NOT VALIDATING THAT ITS DISCOVERY IS NEW.**
    E116 counted the state-carrying axes in a 16-measure inventory and found **two**, surviving four
    synthetic controls: one latent axis counted as one, two counted as two, an arch (one axis with 35 %
    of features non-monotone in it) counted as one, and a null whose calibration had to converge. E118
    then confirmed the second axis's predicted **inverted U** against anaesthetic depth in an independent
    deposit, with the arousal combination curving oppositely. It read as a genuine discovery.
    **E119 asked one question none of those controls asked — what IS it? — and the answer was alpha
    power.** On the discovery deposit, comp2's stage rank profile correlates with `relative_alpha_power`
    at **+1.0000**: the axis and the single measure order the five stages identically. In VitalDB the
    inverted U retains **20 %** of itself after alpha is residualised out in one arm and **6.6 %**, with
    an interval spanning zero, in the arm that had passed the strictest gate.
    Every control was about the counter's ARITHMETIC — could it count correctly. None was about the
    counted object's IDENTITY. **A dimensionality or discovery method needs a rule-60 escape check on
    every component it reports, against the single measures already in its own inventory, and that check
    costs one correlation.** The corollary is worth stating plainly: a well-validated search pointed at
    an inventory containing a well-known phenomenon will find that phenomenon and present it as a
    discovery. Related failure in the same run: **P4 was registered as a primary and the first draft
    never let it reach the verdict**, so the file printed "NOT REDUCIBLE TO ALPHA" while a +1.0000
    correlation sat in its own output — a gate that exists in prose and not in code, for the third time.

36. **Credential precedence, third occurrence.** The sandbox exports `AWS_ACCESS_KEY_ID` as a 14-character
    `prox…` proxy token that outranks `~/.aws/credentials`, and the failure reads as `InvalidAccessKeyId` —
    indistinguishable from expiry. `common/awsenv.py` now drops it (only when it provably is not an AWS key
    id and a shared credentials file exists) and the 53 S3 scripts call it. **An `unset` in `~/.bashrc` does
    nothing here** — the tool's shells are non-interactive and never source it. That was tried first.

### G. Added 2026-07-29

38. **Before declaring work lost to a container rollback, `git fetch` and compare HEAD against the remote.
    The rollback restores an OLD COMMIT, not an empty tree — so anything pushed is intact and the local
    worktree merely looks catastrophic.** A snapshot-restore reset this worktree to an R412-era commit,
    `bsde/` vanished, `/tmp` was empty, and the workflow journal *and* its script were gone. That much was
    real. But the conclusion drawn from it — that a 227-line `MASTER_PLAN.md`, a 14-row registry expansion and
    a `CLAUDE.md` edit had all been destroyed — was **wrong**, and a plan to rewrite them from scratch was
    written and approved before anyone checked. `git fetch` plus `git merge-base --is-ancestor HEAD
    origin/<branch>` showed the local HEAD was simply 37 commits behind; `git reset --hard origin/<branch>`
    restored everything. Only genuinely uncommitted edits were lost, and there were three of them.
    **Diagnostic order, always:** (1) `git fetch origin <branch>`; (2) `git merge-base --is-ancestor HEAD
    origin/<branch>` — if it PASSES the local branch is behind and `reset --hard` discards nothing; if it
    FAILS **stop**, because the reset would destroy real work; (3) `git log --oneline HEAD..origin/<branch>`
    to size the recovery; (4) only now enumerate what is actually missing. The corollary is the cheap habit
    that made recovery possible at all: **commit and push at every artifact boundary, not at the end of a
    work item.** An artifact that has not been pushed does not exist.
39. **WebFetch fabricated a file manifest, not just a citation — rule 25 extends to ANY record, not only
    bibliographic ones.** Asked to summarise the Figshare API record for the DoC dataset, WebFetch's
    summariser invented "435 files" and "91 subject datasets" — numbers that would have exactly corroborated
    the investigator's brief and would therefore have been believed. It was caught only because the same URL
    was re-pulled with `curl` and compared byte-for-byte against the local `meta.json`: they were identical,
    and neither contained anything resembling those figures. Third occurrence of this failure mode here.
    **Use `curl` plus a parser for any manifest, index, file listing or bibliographic record — never a
    WebFetch summary of one.** Fabrications that agree with your hypothesis are the ones that survive review.

### H. Added 2026-07-30 (BSDE, from thirteen registered designs of which eight died on machinery)

40. **A GATE THAT CANNOT FAIL IS NOT A GATE, and this project shipped two.** E22 selected epochs by
    `meta_epoch`, a column its adapter never emitted, so every test matched the empty string and the gate
    saw 0 of 0 cases. E29 checked that pairs spanned "both directions of dose" while its own pair
    constructor ORIENTED every pair higher-dose-second, so the answer was 100.0 % by construction. Both
    printed confidently. **Before trusting a gate, construct the input that should fail it and check that
    it does** — `tests/test_e28_paths.py` does this for a placebo, and it is the pattern to copy.
41. **RUN THE FEASIBILITY PROBE BEFORE REGISTERING, NOT AFTER FAILING.** Eight of thirteen designs died on
    coverage, sentinels, artefact-tracking or exposure shape — and every one was computable in advance from
    the label, exposure, artefact channels and clinical record, with **no candidate column touched**.
    `bsde/governance/feasibility.py` runs the six checks; it reproduces E21's sentinel (one value holding
    49.1 % of a continuous column), E22's artefact gradient (label rising 0.30 -> 0.74 across EMG deciles)
    and E32's exposure shape (53 % zeros) in seconds. The probe reports numbers and never chooses
    thresholds, and it must be run **before** the registration so the floors are set knowing the coverage —
    a probe run after a gate fails, used to find the setting that would have passed, is the move
    `DISCOVERY_LOOP.md` §2 forbids.
42. **A QUOTATION SUPPORTS ONLY WHAT IT LITERALLY SAYS.** E31 and E32 cited Gugino 2001 as fixing the
    direction of their prediction. The abstract says beta RISES in light sedation and delta/theta rise
    further at loss of consciousness; it never says beta falls. "The fast end is overtaken" was an
    inference about relative power presented as the source's content. **Label an inference as one**, and
    when a claim is load-bearing, quote the sentence next to it so a reader can check the gap.
43. **A CORRELATION NEVER LOOKS AT WHERE ITS EXPOSURE SITS; A STRATIFIED ANALYSIS HAS TO.** Four
    experiments correlated a candidate against MAC before one split the axis and found the bottom tercile
    had a median of 0.00 — half the "volatile arm" was vaporiser-off. A correlation spans an off-state
    perfectly happily. **Quantile the exposure before designing on it** (rule 41's probe does this).
44. **REFINING RESOLUTION CANNOT PRESERVE BOTH THE QUESTION AND THE BASE RATE — DECLARE WHICH.** E27 went
    from a 300 s to a 60 s grid holding the horizon at three windows, which is the same question and
    mechanically drops the base rate (it failed at 4.0 % against a 5 % floor). Holding the horizon in
    seconds instead would have preserved the base rate while silently changing "three windows ahead" to
    "fifteen windows ahead". Both were available, neither is free, and the choice must be stated in the
    registration rather than discovered in the result.
45. **A REGISTRATION MUST NAME ITS INCUMBENT.** A marker reported without the thing it has to beat is not a
    result. E26 named BIS and found the incumbent scored AUC 0.583, which is what made its own null
    meaningful; E28 named Blankertz 2010. E30 named none, and its +0.710 therefore has no bar beside it.
    The ledger now carries an `incumbent` field and an empty one is a defect.
46. **WHEN A BOOTSTRAP VERDICT'S MARGIN IS THE SIZE OF ITS MONTE CARLO ERROR, THE BINARY IS NOISE — REPORT
    THE RESAMPLE-LEVEL p AND THE SEED STABILITY.** E36's registered primary was "the 95 % CI excludes 0".
    At the registered 2,000 resamples it did, by 0.0013. Re-run at five seeds, **one of the five straddled
    zero**: the printed verdict was a property of the RNG seed, not of the data. Twenty thousand resamples
    put the one-sided p at 0.0242 — a real but weak pass, and a number that says so, unlike PASSED. Two
    habits fall out and both are cheap. **Report the fraction of resamples on the wrong side of the null,
    not only the interval** — it is the same computation and it degrades gracefully where an interval
    endpoint does not. And **re-run any boundary verdict at three or more seeds before writing it up**; if
    it moves, the replicate count was too low for the claim, and raising it is a legitimate fix precisely
    because it changes no threshold, cohort or horizon. The related trap: a folded statistic like
    `|AUC-0.5|` is biased upward under the null, so it must only ever be *differenced against itself* on
    the same rows — never reported as a single feature's effect size.
47. **A PLACEBO SHOWS A CHOICE IS EXTREME; IT CANNOT SHOW THE CHOICE WAS MADE BLIND.** E36 enumerated all
    495 alternative partitions of its feature set and its real one was the unique maximum, p = 0.002. That
    is a strong result and it is *not* an answer to "you drew the line after seeing the numbers", because
    the line genuinely was drawn afterwards. What answers that charge is structural, and has to be built in
    at registration: the partition is a property of the instruments (phase versus amplitude) rather than an
    arbitrary grouping; **the one feature that discriminates the two competing readings was assigned
    against the favoured story** and still behaved as assigned; and the denominator statistic did not exist
    in the parent experiment, so it could not have been peeked at. Write those three down at registration
    or the placebo is decoration.
48. **A PLACEBO CANNOT VALIDATE A NULL — when the real effect is zero, the gate must declare itself NOT
    INFORMATIVE rather than PASSED.** E37's primary increment was +0.0007 [-0.0539, +0.0295] and its
    placebo landmark scored -0.0042, so the file printed "P5 PASSED" directly beneath a failed primary. The
    arithmetic is correct and the sentence is misleading: a placebo asks whether a real effect survives a
    fake landmark, and there was no real effect for the fake landmark to fail to reproduce. Left in a
    write-up it reads as though something survived. **The placebo branch must test the primary's interval
    first and emit NOT INFORMATIVE when it includes the null** — the same discipline as rule 34 (a placebo
    is a comparison, never an absolute threshold) applied to the degenerate case. Related, and from the
    same run: **a sensitivity arm that cannot execute must be reported, not silently dropped.** E37's 30 s
    arm required 30 adjacent sample pairs from a 30-sample window, which contains 29 — the rule-40 shape
    inverted, a check that cannot fire rather than a gate that cannot fail. It produced no output and would
    have vanished unremarked.

---

## SOP: bugs are fixed and re-run, not narrated (STANDING — investigator instruction, 2026-07-31)

**Do not spend a chat turn announcing a bug. Fix it, re-run, and keep going.** The investigator asked for
this directly. It changes where the record lives, not whether it exists.

**Still recorded, always, and in the repo rather than in conversation:**
- the commit message names what was wrong and what changed;
- the ledger row's `outcome_detail` carries it if a registered result was affected;
- a genuinely new failure mode is appended to the error catalogue above — that catalogue is the project's
  single most valuable asset and nothing here reduces it;
- a withdrawn verdict still gets its `results/e<NN>_first_pass_note.md`, because a correction that is not
  auditable is not a correction.

**The one case that MUST still be raised in conversation: a bug that changes a number already reported to
the investigator.** Silently correcting a figure someone is already reasoning with is not brevity, it is a
false record. Say it in one sentence, give the corrected number, and move on — no post-mortem.

Everything else — a gate that could not fire, a mis-parsed identifier, a Welch window longer than its
segment — is fixed in place, re-run, committed, and mentioned only if the investigator asks.

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
| `bsde/docs/MASTER_PLAN.md` | **live — THE plan for the BSDE project**, reconciles the briefs with what's verified |
| `bsde/docs/RESEARCH_STRATEGY.md` | live — BSDE's detailed strategy, documented departures from the briefs |
| `bsde/docs/ANALYSIS_PLAN.md` | live — BSDE's analysis backlog |
| `bsde/docs/LITERATURE_MAP.md` | live — BSDE's prior-art / literature tracking |
| `bsde/docs/RESEARCH_PROGRAM_BRIEF.md`, `BRIEF_02_DATASET_STRATEGY.md`, `BRIEF_03_AI_DISCOVERY_LAB.md` | **live, immutable** — investigator-supplied verbatim, never edit |

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
51. **THE PRIMARY STATISTIC MUST BE SENSITIVE TO THE FAILURE MODE THE EXPERIMENT EXISTS TO FIND.** Rule 30
    says a rule set before the run can still be set too low. This is the sibling error: a rule set before
    the run, correctly followed, that measures the wrong part of the distribution. **E58** registered
    *median* absolute error as its primary, then produced a per-band table showing fidelity of 3.47 BIS
    units inside the clinical target band and **29.84 at BIS ≥ 80**. Median error is the statistic least
    sensitive to a tail, and the tail was the entire finding — which the primary could not see at all.
    (What the tail *meant* took a second correction: those windows are 98.2 % facial-EMG artefact, so the
    row measures failure to reproduce an artefact-driven reference, not failure to detect wakefulness.
    That correction changes the interpretation and not this rule.) The verdict stands as registered (NO GAIN, increment −0.195 [−0.424, +0.035]) and
    the same fit improves visibly on mean |err| and R², which were descriptive and stay descriptive. **The
    check to run before registering: name the way the measure is expected to fail, then ask whether the
    primary statistic would move if that failure got twice as bad.** If it would not, the primary is
    measuring somewhere else.
52. **A BAND-RESTRICTED PRIMARY CANNOT TELL AN IMPROVEMENT FROM A REALLOCATION.** Rule 51 says the primary
    must be sensitive to the failure mode you care about. Its sibling: a primary *restricted* to a subset
    is blind to what the change costs outside that subset, and a model that moves error from one region to
    another looks identical, from inside the restriction, to one that removes it. **E60** registered its
    primary as median |err| on BIS ∈ [0,40) and "nowhere else" — which correctly stopped the bar moving
    afterwards, and equally stopped the experiment from seeing that the same fit made the *target* band
    worse (3.47 → 3.91 on 2,879 windows) while improving the deep band (5.48 → 4.76 on 2,330). The verdict
    stands; the description "improvement" does not. **Whenever the primary is restricted, report the
    unrestricted effect beside it** — not as a second verdict, but because "better here" and "better" are
    different claims and only one of them was tested.
    **Corollary, from the same run and cheaper than any of this: use the quality flag the deposit already
    ships.** E60's worst sub-band, [0,20) at median |err| 39.96 under both models, turned out to have
    median **SQI 5.1 of 100** — the monitor reporting a value it simultaneously declares unreliable. The
    column was in the same table from the start and no experiment had used it. Before modelling a region
    where a reference behaves strangely, **check whether the reference says so itself.**
53. **A CONTRAST BETWEEN TWO FAMILIES REQUIRES THAT AT LEAST ONE FAMILY SHOW THE EFFECT — CHECK THAT THE
    PHENOMENON EXISTS IN THIS COHORT BEFORE ASKING WHO HAS LESS OF IT.** Rule 45 says a registration must
    name its incumbent. This is the version for contrast designs, and the gate already existed in this
    project: **E33** wrote "THE INCUMBENT MUST BE ALIVE — if the incumbent cannot predict the transition at
    all, beating it is not a result." **E61** did not carry it across. It gated on capability and on state
    discrimination, returned NO SPLIT, and only a post-hoc permutation null revealed that **not one of nine
    candidates leaked agent identity above its own null** — the amplitude family's observed 0.0903 sat
    *below* its null mean of 0.0960. The verdict was correct and the interpretation "phase does not leak
    less" would have been wrong: there was nothing in either family to leak. **The check costs one extra
    loop over code already written** — permute the label, recompute the same statistic per candidate, and
    confirm the reference family clears its own null before the comparison is read as meaningful.
54. **A CONFOUND NAMED IN THE REGISTRATION IS NOT THEREBY CONTROLLED — WRITING THE CAVEAT CREATES THE
    FEELING OF HAVING HANDLED IT.** Rule 50 says get the baseline before naming a mechanism. This is the
    failure one step earlier: **E66** registered a cross-deposit transportability statistic, wrote in its
    own docstring that between-deposit spread "confounds device, montage, reference, sampling rate,
    pipeline AND population", cited rule 50 while writing it — and then computed the statistic across
    **anaesthetised surgical patients, awake children, awake adults and sedated volunteers.** The
    `lempel_ziv` medians it produced (HBN 0.228, VitalDB 0.441, eegmmidb 0.623, chennu 0.749) are low in
    the children because they are children and low in the surgical patients because they are unconscious.
    **Those differences are the features WORKING**, and the statistic could not tell them from failure.
    The registration's own caveat was word-perfect and changed nothing about the computation.
    **The check: for every confound the registration names, point at the LINE OF CODE that handles it.**
    If there isn't one, either restrict the cohort or delete the claim — a named confound with no
    corresponding filter, covariate or matched control is an unnamed confound wearing a disclaimer.
55. **A PLACEBO MUST BE ABLE TO CHANGE THE STATISTIC IT IS A PLACEBO FOR — CHECK THE MATHEMATICS, NOT THE
    NARRATIVE.** Rule 40 says a gate that cannot fail is not a gate. This is its quietest form: a placebo
    that is *conceptually* the right destruction but is **provably insensitive to the statistic in
    question**. **E67** compared the SIGN of a within-subject effect between two arms and placebo-tested it
    by breaking the within-subject pairing. Breaking pairing changes the variance of a paired difference,
    and therefore d_z's magnitude — but a group mean difference keeps its direction whether subject i's N3
    is paired with their own W or with subject j's. **The sign is mathematically untouched.** The placebo
    returned 0.500 against a real 0.500 by construction, and the verdict branch fired on an identity.
    **The check costs one line of algebra: write down what the placebo alters, and confirm the primary
    statistic is a function of it.** Shuffling pairing tests paired structure; shuffling the STATE LABEL
    tests direction. Match the destruction to the estimand, or the gate is decoration that also looks
    rigorous.
56. **A BACKGROUND-TASK "COMPLETED" NOTIFICATION REPORTS THE LAUNCHING SHELL EXITING, NOT THE DETACHED
    CHILD FINISHING — CHECK THE PROCESS, NOT THE MESSAGE.** Launching with `setsid nohup … & disown`
    deliberately outlives its shell, so the harness reports completion the moment the wrapper returns while
    the extractor keeps writing. Acting on that notification and starting a second copy put **two
    concurrent writers on one CSV**: 931 rows where 710 were expected, **419 duplicated `recording_id`s**,
    and a real risk of torn lines that only survived because appends were flushed per row. **Before
    relaunching or resuming any background job, confirm it is dead** — `ps -eo args | grep -c <pattern>`,
    not the task message. And any resumable extractor should **de-duplicate on its key when it loads**,
    rather than trusting that it was the only writer.
57. **A POSITIVE CONTROL IS AN INSTRUMENT AND NEEDS ITS OWN VALIDATION — AND AN AMPLITUDE IN ARBITRARY
    UNITS IS NOT A MAGNITUDE.** **E71** built a muscle-attribution audit around a positive control,
    `emg_index`, which **E69 had already shown fails to detect REM atonia**. Measured against the real
    submental channel it correlates at **ρ = +0.20 pooled, +0.30 within subject** — a weak proxy pressed
    into service as ground truth, so its failure to rank first said nothing about the method. Building the
    gate was right; building it on a proxy already known to be broken was not.
    **The second half is subtler and cost more.** A synthetic control — a feature constructed to BE the
    muscle channel plus noise — returned d_z = **+0.062** for wake versus N3, on a channel whose medians
    are **3.063 against 1.104**. The effect is enormous and the standardised effect is nil, because
    submental EMG amplitude carries a subject-specific gain: one subject moves 10→3 and another 1→0.3, so
    the paired differences have huge between-subject variance. **Any EMG amplitude used as a covariate or
    an effect size must be log-transformed or within-subject standardised first**; raw units are usable
    only where a within-subject regression absorbs the scale into its slope, which is why E70's
    residualisation and its rank-position evidence survive this while E71's magnitudes do not.
58. **REVISING A GATE AFTER IT FAILS IS GOALPOST-MOVING EVEN WHEN EACH INDIVIDUAL FIX IS DEFENSIBLE — FIX
    ONCE, WITH A STATED REASON, THEN REPORT.** **E72** revised its bracket gate twice in one sitting. Both
    fixes were correct in isolation: pure noise as a negative control cannot pass an aliveness gate (rule
    40), so it was replaced with a stage-driven EMG-independent synthetic; and a RANK requirement
    ("bottom three") cannot be met by a null control when many real features are also null, since the
    control lands inside the null cluster by construction. **Each repair was right and the sequence was
    wrong.** By the second revision I was tuning the apparatus until it returned a verdict rather than
    learning from the verdict it returned. The registered outcome stands as METHOD FAILS, and the
    substantive numbers — synthetic muscle 0.810 against synthetic null 0.022, with no real feature above
    0.171 — are reported as UNLICENSED BY IT.
    **The discipline: one repair per run, with the reason written down, and if the gate fails again the
    run is over and the failure is the result.** A gate revised twice is no longer independent of the
    answer, whatever the intent behind each change.
59. **WHEN YOU IMPORT RESULTS FROM A PRIOR EXPERIMENT, IMPORT THE WHOLE ROW — A SELECTIVE IMPORT IS A
    SILENT COHORT CHOICE.** **E74** compared each feature's drug-free response against its drug response,
    and populated its `DRUG_DZ` table by hand from **E67**, taking the two drug columns and leaving E67's
    **no-drug column behind**. E67's no-drug arm was natural N3 sleep, where `whole_head_exponent` moves at
    d_z **+4.008** — more than under either anaesthetic. E74 saw only the sleep-deprivation arm (+0.034),
    concluded the feature "moves for drugs and not without one", and labelled it PHARMACOLOGY. **The
    opposite is true**: it responds to every genuine loss of consciousness, drug or natural, and its silence
    under sleep deprivation reflects a far smaller state change. The reversing feature was `lempel_ziv` all
    along (−2.281 natural, +1.551 drug), and the conclusion was exactly inverted.
    **The mechanics of the error matter more than the instance: hand-copying a subset of a prior result's
    columns into a new file's constants is a cohort decision disguised as bookkeeping.** Load the prior
    result's JSON and select from it in code, so the columns you did not use are visible in the diff — or,
    at minimum, transcribe every arm and drop the unused ones explicitly.

### I. Added 2026-08-01 (BSDE, from the E139–E142 Challenge A audit)

69. **WHEN THE EXPOSURE IS NESTED INSIDE THE CLUSTER, THE EFFECTIVE n IS THE NUMBER OF CLUSTERS, AND A
    ROW-LEVEL NULL INFLATES SIGNIFICANCE BY ORDERS OF MAGNITUDE — MEASURED HERE AT 178×.** On the Krause
    deposit a patient is either a dexmedetomidine patient or a propofol patient, never both, so the
    drug-identity contrast has **15 independent units, not 115 blocks**. **E35** and **E36** computed
    block-level AUCs as though the blocks were independent. Enumerating all C(15,7) = 6,435 patient
    labellings exactly (**E142**), only 2 of 12 features clear the null, the mean 95th percentile of that
    null is **0.2791** — above every phase feature's entire observed value — and E36's family gap of
    +0.0913 has exact **p = 0.0914**. The phase family's celebrated low leakage is **absence of power, not
    measured absence**, which is the discrimination-versus-equivalence error
    `REFERENCE_AGAINST_ALL_THREE.md` had already diagnosed for future designs and never applied to numbers
    already in hand. **Enumerate the cluster-level assignments and quote the null's 95th percentile before
    quoting any legibility.** Three experiments (E139, E140, E141) were designed around a confound in a
    statistic that turned out to be noise; the check that would have prevented all three costs one
    `math.comb`. Corollary, and it is the reusable part: **a placebo probe of pure noise measures the
    floor, so run one whenever a gate threshold is being chosen** — E141's GATE N was set at 0.05 when the
    floor was 0.084, which is how the whole thing surfaced.

70. **A CANDIDATE LIST ASSEMBLED AS "EVERY NUMERIC COLUMN" WILL CONTAIN RE-DESCRIPTIONS OF THE OUTCOME.**
    **E149** reported `mean_triallength` as the one candidate adding to the Challenge B incumbent on
    Stieger. It is not an EEG measure at all: in that cursor task a trial ends when the target is hit and
    otherwise runs to a fixed timeout, so trial length is mechanically the inverse of accuracy —
    **rho = −0.3492 over 185 sessions, range 1.77–4.87 s against a ceiling.** It entered through a loader
    whose rule was "every numeric column except this SKIP set", and a SKIP set only excludes what someone
    thought of. **Enumerate what a candidate is ALLOWED to be — a measurement of the signal, computed
    without reference to the target — rather than listing what it is not.** The tell was available before
    the statistics: a "feature" whose units are seconds, in a task whose outcome is scored in trials.

71. **A VERDICT BRANCH MUST CHECK THE GATE ON THE ARM THE WINNER CAME FROM, NOT ON ANY ARM.** E149 ran two
    deposits. Its code computed `alive = [arms whose incumbent passed G2]` and then fired the POSITIVE
    branch on `any(winners.values())` — so a winner from the arm whose incumbent was **dead**
    (Stieger, p = 0.1095) was reported against a live incumbent somewhere else. Rule 53 says check the
    phenomenon exists in the cohort you are asking about; this is the same rule applied to the verdict
    code rather than to the design. **When a file has arms, every gate is per-arm and the verdict must
    index the arm.**

72. **THE NULL OF A CROSS-VALIDATED POOLED AUC UNDER WITHIN-SUBJECT LABEL PERMUTATION IS NOT CENTRED ON
    0.5 — MEASURE IT.** E158 gated a leakage control at "permuted-label out-of-fold AUC must lie in
    [0.45, 0.55]" and it returned 0.4400, which read as leakage. Measuring the null directly over 50
    draws: **mean 0.4463, sd 0.0158, every draw below 0.48**, and the *same* for a completely unrelated
    feature family (spectral panel: 0.4486). **54 % of draws fall outside the nominal gate**, so a
    one-draw test against a nominal centre is a coin flip. The bias comes from pooling within-subject and
    between-subject comparisons in one AUC while the folds hold subjects out; it is a property of the
    design, not of the features. Two rules follow, and they generalise past this statistic: **a control's
    null must be measured under the exact resampling scheme it will be judged by (rule 63 again), and a
    gate evaluated on ONE draw cannot estimate a rate — it needs a distribution.** The corollary that
    matters for reading results: pooled out-of-fold AUCs from this design are biased low, so the
    *difference* between two representations is trustworthy where the *level* is not.

73. **NORMALISING TWO GROUPS SEPARATELY ANNIHILATES THE CONTRAST BETWEEN THEM — AND ONLY A CAPABILITY
    GATE CATCHES IT.** E165 fitted a projection to discriminate conscious from unconscious case
    summaries, and rank-normalised the conscious block and the unconscious block **independently**. Each
    is then mean-zero by construction, so the conscious-versus-unconscious offset — the entire quantity
    under test — is removed before the optimiser sees it. On synthetic data built from a known
    state-driving latent axis, held-out state legibility came back at **0.0056**; with the two blocks
    ranked JOINTLY and then split it is **0.4323**, a factor of 77. **The fix is one line and the bug is
    invisible in every summary statistic**: each block looks correctly standardised, the optimiser
    converges, the output is well-formed, and the answer is noise. What caught it was rule 40's
    capability gate — a synthetic system whose answer exists by construction, run BEFORE the real data.
    Generalises past ranks: any per-group centring, z-scoring, quantile mapping or within-condition
    baseline correction applied to the groups being compared destroys the comparison. **Normalise over
    the pooled data and split afterwards, or normalise on a variable that is not the contrast.**

74. **A DEFECT FIXED IN ONE FILE IS NOT FIXED — PUT THE GUARD IN THE SHARED MODULE.** The same failure
    appeared three times in one session. E157 scored an all-NaN column at **p = 0.0000**, because
    `nanmean(null >= nan)` counts every comparison False. E161 fixed it locally and its ledger row
    diagnosed it. **E164 then scored a CONSTANT column** — `age`, whose within-subject change is
    identically zero in a change design — at p = 0.0000 by the identical mechanism, because the local
    fix was never carried across. `verifier/stats.screen_candidates` now drops columns with too few
    finite or too few distinct values and returns them with a reason, so callers report the exclusion
    (rule 14) instead of scoring it. The rule is not "remember to check"; it is that a check living in
    one experiment will not be there for the next one, and this project's own record shows a diagnosis
    written into a ledger row does not prevent a repeat.

75. **THE SPREAD OF A STATISTIC OVER RANDOM PROJECTIONS IS NOT ITS NULL — AND USING IT AS ONE MAKES THE
    PRIMARY UNFALSIFIABLE.** E165 asked whether a fitted linear combination could keep state
    discrimination while dropping agent discrimination "to the floor", and defined the floor as the 95th
    percentile of agent legibility over 200 **random weight vectors**: **0.4203**. The correct reference,
    a cluster-level permutation null over the arm labels, was already measured on the same cohort by E154
    at a 95th percentile of **~0.19** — less than half. Against a 0.42 bar essentially any projection
    passes, and the verdict duly fired at **lambda = 0**, i.e. with no adversarial term in the objective
    at all. **The experiment could not have failed.**
    The two quantities answer different questions. A permutation null asks *could this legibility arise
    with no association*. A random-projection spread asks *how much does this statistic vary across
    directions* — and in a space where some directions genuinely carry the label, that dispersion is
    inflated by the very signal being tested. **Never let a dispersion stand in for a null.** The tell is
    available before the run and costs nothing: if a permutation null for the same statistic on the same
    cohort already exists, the two should agree, and here they differed by a factor of two.
    Related to rule 40 and rule 63, and distinct from both: the bar was neither unfailable by construction
    nor a round number, it was a real measurement of the wrong thing.

### J. Added 2026-08-01 (BSDE, from the E166–E173 re-derivation programme)

76. **A DESIGN MATRIX WITHOUT AN INTERCEPT IS A DIFFERENT MODEL, AND IT CAN REVERSE THE SIGN OF AN
    INCREMENT — SO THE REQUIREMENT MUST BE ENFORCED IN CODE, NEVER IN A DOCSTRING.** `oob_auc_increment`
    fits an IRLS logistic that carries no intercept of its own, and its docstring said so: *"`Xa` and `Xb`
    must already include an intercept column."* **E99 passed `[BIS]` and `[BIS, exponent]` bare.** Both
    models were therefore fitted through the origin, and the experiment printed
    **-0.0306 [-0.0524, -0.0101]** and logged the verdict **HURTS** — "the exponent is variance the model
    spends capacity on and does not generalise." Reproduced exactly a session later: the same call without
    the intercept gives -0.0320 [-0.0544, -0.0111]; **with** it, on the identical 5,798 windows, 247 cases
    and 977 positives, it gives **+0.0168 [+0.0049, +0.0269]**, and every arm of E99's own design then
    returns ADDS while its negative control stays null. Three independent estimators agree (+0.0160,
    +0.0162, +0.0235) and a 50–95 % training-fraction sweep never leaves +0.017…+0.023.
    **What makes this worth a rule is not the arithmetic but the shape of the failure.** The wrong sign
    was not implausible — it came with a written mechanistic story, an interval excluding zero, and a
    passing negative control, and it survived a whole ledger row and a consolidation document. A
    convention that a caller must satisfy, and that fails SILENTLY and PLAUSIBLY when they do not, is a
    defect in the callee. `stats.py` now **raises** when a design's first column is not a constant.
    Corollary that generalises past intercepts: **any helper with a precondition it does not check will
    eventually be called wrong, and the cost is proportional to how reasonable the wrong answer looks.**
    Grep for every caller when you find one — here it was two of eight, both from the same copied template.

77. **A NEGATIVE CONTROL BUILT TO BE INDEPENDENT MUST BE MEASURED FOR INDEPENDENCE — A SHARED LATENT IS
    INVISIBLE IN THE CODE THAT CONSTRUCTS IT.** E173's synthetic arm existed to disqualify estimators: one
    system where an added column genuinely carries signal, one where it is pure noise. The noise column was
    written as `e = normal(n) + 0.5 * u` where `u` was the cluster-level shift *also driving the baseline*,
    and the outcome depended on the baseline. So the "noise" column carried real information about the
    outcome through `u`, and **every scheme at every training fraction called it a real addition in 100 %
    of replicates.** The construction reads as independent — a fresh normal draw per row — and is not.
    Two independent shifts fixed it and the same schemes then land at 25-40 % positive.
    **The check is one line and belongs beside the construction: correlate the negative control with the
    outcome, in the units the estimator will see, and assert it is null.** A control that fires on
    everything looks like a working control right up until it is the thing certifying your result.
    Related and worth stating separately: with the control repaired, the cluster bootstrap called a genuine
    null "positive" in only **12 %** of replicates against the cross-fits' 25-40 %, i.e. it is biased
    slightly toward HURTS — the exact direction of the error rule 76 describes, and a reason to prefer
    cross-fitting when the sign is what is at stake.

78. **A PLACEBO MUST BE MATCHED ON THE BASELINE'S HEADROOM AND THE LABEL'S BASE RATE, OR IT MEASURES
    THOSE INSTEAD OF THE LANDMARK — AND A CALIBRATED NULL CANNOT TELL YOU THE LABEL IS THE PHENOMENON.**
    Two lessons from one run, and the second is the larger one.
    **E166** re-derived four increment rows to ADDS with a calibrated cluster-permutation null, a
    measured detection floor and a rho = 0 rung that did not fire — everything the project had learned to
    demand. **E170** then placebo-tested one of them properly, as a DISTRIBUTION over 200 fake landmarks
    rather than E34's single draw, and it died: fake landmarks at arbitrary relative positions gave a
    **mean increment of -0.04844 against the real -0.02180, with 83 % reaching or beating it.** A
    permutation null answers *does this column carry information about the label I gave it*. **It is
    silent on whether that label is the phenomenon**, and only a placebo on the LABEL can speak to that.
    Build the label placebo at the same time as the label.
    **The second half is a defect in the placebo itself, found by measuring it afterwards and recorded
    without changing the verdict** (rule 58 — a gate is not re-tuned after it fires). The fake landmark
    left the incumbent at out-of-fold AUC **0.4652** with base rate **0.097**, against the real label's
    **0.6088** and **0.312**. An added column has more room to help when the baseline is weaker and the
    positive class rarer, for reasons that have nothing to do with the landmark, **so the placebo was
    harder than the real test and its firing is partly an artefact of that.** Note which way this cuts:
    an unmatched placebo that fires can only be argued to be too HARSH, and making that argument after
    watching it fail is exactly the move `DISCOVERY_LOOP.md` §2 forbids. The verdict stands; the
    successor is what gets the matched placebo.
    **The check, before the run: compute the baseline's performance and the base rate under the real
    label AND under the placebo, and match them by rejection sampling or state that you could not.**
    If no fake landmark can reproduce the real one's baseline predictability, that is itself a finding
    about the landmark — and it must be reported as a limitation of the placebo, never as a pass.

### K. Added 2026-08-02 (BSDE, from the E187–E197 placebo programme and the Challenge A repair chain)

79. **STOP ARGUING ABOUT WHETHER A PLACEBO PRESERVES THE RIGHT THING AND MEASURE WHETHER IT MANUFACTURES
    THE RESULT.** Four experiments and most of a session went into a gate asking *does this surrogate
    preserve the candidate's autocorrelation?* — E187 with a round-number tolerance, E189 with a
    self-referential comparison, E190 with a surrogate whose preservation is a **theorem**. All three
    refused. **The gate was a proxy, and the quantity it stood for is directly measurable on the primary
    statistic itself.** E191 built a ladder of pure-noise AR(1) columns spanning the real candidates'
    measured lag-1 autocorrelation (0.678 to 0.955) and asked how often each one beats its own placebo at
    the 5 % bar. The answer for the circular shift was **0.050 / 0.100 / 0.150 / 0.050 / 0.250** across
    rungs 0.00 / 0.50 / 0.80 / 0.95 / 0.99 — a pure-noise column beats its own placebo 15 % of the time at
    exactly the autocorrelation the real candidates have. That is a number no preservation argument would
    ever have produced, and it settles in one run what three files of increasingly clever gates could not.
    **The construction generalises to any placebo, resampling scheme or null: build a null object whose
    NUISANCE structure matches the real thing and whose SIGNAL is known to be absent, then measure the
    false-positive rate as a rate, not on one draw (rule 72).** A candidate is then readable only if the
    rungs bracketing its own nuisance parameter are calibrated — which is a per-candidate licence, not a
    global one, and it correctly refused `bis_rbr` alone at |AC1| 0.955.

80. **A SURROGATE-VERSUS-SURROGATE REFERENCE CANCELS ANY BIAS THE SURROGATES SHARE, SO A GATE BUILT ON ONE
    CAN ESSENTIALLY ONLY FAIL.** E189's preservation gate compared real-versus-surrogate |ΔAC| against
    |ΔAC| between two INDEPENDENT surrogates of the same series, which reads as the ideal
    self-calibrating reference and is not. Both sides of the reference carry any systematic distortion the
    method has, so it subtracts out; the real-versus-surrogate side carries it once, undivided. Any family
    with a downward autocorrelation bias — IAAFT through amplitude re-imposition, a circular shift through
    its single wrap seam — therefore exceeds its own reference **at every sample size, however small the
    bias is in absolute terms**. Measured here: real-vs-surrogate 0.025–0.069 against surrogate-vs-surrogate
    0.014–0.036, refusing all eleven candidates **and both controls**, for a surrogate whose preservation
    is provable. The tell was available before the run and is worth one line of algebra: **ask what the
    reference distribution CANCELS. If it cancels the very thing the gate exists to detect, it is not a
    reference.** Related to rule 55 (a placebo must be able to change the statistic it is a placebo for) —
    this is the same failure moved into the gate's denominator.

81. **A GATE THAT CANNOT PASS IS AS USELESS AS ONE THAT CANNOT FAIL, AND IT IS EASIER TO WRITE.** Rule 40
    covers gates that cannot fail. E194's donor-availability gate required **every** recording to have at
    least five donor recordings *at least as long as itself* — and there is always exactly one longest
    recording, with nothing longer than it. It refused on its own first line, for arithmetic reasons, on
    any cohort that could ever exist. **Before registering a gate, construct the input that should PASS it
    and check that it does** — the mirror of rule 40's instruction, and the same one-minute cost. The
    corrected version gates two quantities that can each go either way (1.6 % of recordings had no
    long-enough donor, 91.9 % had at least five), which is what a threshold derived from the machinery
    looks like (rule 63).

82. **A PLACEBO WITH NOTHING TO SYNTHESISE HAS NOTHING TO DISTORT — LOOK FOR A REAL OBJECT BEFORE BUILDING
    A FAKE ONE.** Every surrogate family in this programme exists to manufacture a column that is realistic
    in trend, autocorrelation, marginal, drift and artefact structure. **The deposit is full of such
    columns**: the same measure, from a different patient. A random contiguous block of another recording's
    candidate needs no preservation gate, because nothing was preserved — nothing was altered. It carries
    no information about the recipient's label because it came from someone else. This is the resampling
    idea from cluster-randomised inference imported wholesale, and it took three failed gate designs to
    think of. **When a control has to be synthetic, ask first whether the dataset already contains the
    object you are trying to fake.** Declare what it destroys: a donor block replaces the recipient's
    recording-level mean as well as its timing, so it is a placebo for the WHOLE association and a
    different estimand from a timing-only one — that difference is a design choice and must be stated, not
    discovered.

83. **"THE CONFOUND IS HIDDEN" IS UNREADABLE UNTIL THE CONFOUND IS SHOWN TO BE LEGIBLE — RULE 53 FOR
    ADVERSARIAL DESIGNS.** E193 asked whether a linear combination could keep depth discrimination while
    dropping agent legibility below a cluster-permutation floor, and the success rule fired at
    **lambda = 0**: state +0.4698, agent +0.0914, floor +0.1744, with **no adversarial term in the
    objective at all**. Two readings — depth and agent are separable, or the agent was never legible in
    this family on this cohort — and the design could not tell them apart. The second was not speculative:
    E154 had measured the MEDIAN single feature identifying the arm at 0.1000 on the same 39 cases, with
    only one feature and the nuisance variable `recording duration` (0.3771) above it. **An adversarial or
    invariance design needs an ALIVENESS gate on the thing it claims to remove, run before anything is
    fitted, and multivariate** — the confound an adversarial axis would have to hide is one legible in
    combination, which a per-feature check misses. Without it, "removed the confound" and "the cohort had
    no confound to remove" print identically, and only the second is true (rule 69's absence-of-power,
    arriving from a new direction).

84. **A CONTROL BUILT TO BE INSEPARABLE MUST HAVE ITS INSEPARABILITY MEASURED — RULE 77, SECOND
    OCCURRENCE, AND THE DIAGNOSIS IS THE SAME BOTH TIMES.** E193's negative capability gate was a synthetic
    system where "one latent drives both state and agent, so no axis can separate them". It fired, and the
    method was right: the construction drew the state-carrying direction `ws` and the agent-carrying
    direction `wa` as two INDEPENDENT Gaussians in eleven dimensions — near-orthogonal — and gave the state
    contrast a constant term with no latent in it at all. Separation was not merely possible, it was easy.
    **The system had the name of the property and not the property.** E195 sets `ws = wa` and then GATES
    the result: |cos(ws, wa)| verified at 1.0000 against 0.1475 for the separable system, and the
    empirical alignment between the state-contrast direction and the agent direction at 0.979 against
    0.197. Rule 77 said this about independence; it holds identically for entanglement, for exchangeability
    and for any structural property a control is built to have. **The check is one correlation and it goes
    in the file, next to the construction, printed.**

85. **WHEN A GATE'S VERDICT MOVES ON ONE MONTE CARLO DRAW, REPORT THE KNIFE-EDGE INSTEAD OF THE VERDICT.**
    E191's two surrogate families returned opposite conclusions — NO FAMILY USABLE against USABLE, 10 of 11
    licensed — and at n = 20 the Wilson lower bound crosses the nominal 0.05 between **2 hits (0.028,
    passes) and 3 hits (0.052, fails)**. The families differed at the deciding rung by exactly one hit,
    3/20 against 2/20. Rule 46 established this for a bootstrap interval; it applies to any rate-based
    gate, and the arithmetic is checkable *before* the run: **compute which integer counts straddle your
    threshold, and if adjacent integers give opposite verdicts the replicate count is too low for the
    claim.** Raising it is the one repair rule 46 permits, because it changes no threshold, cohort or
    estimand. What the under-resolved run licenses is the comparison of point estimates, never the binary —
    and a verdict branch for "the families split, but their intervals overlap" must exist so a threshold
    artefact is named rather than reported as a difference.

86. **AN INCUMBENT THAT SHARES A MEASUREMENT ACT WITH THE OUTCOME SETS A BAR NOTHING EXTERNAL CAN CLEAR —
    RULE 45'S MISSING HALF.** Rule 45 says a registration must name its incumbent, and E204 named one
    carefully and for the right reason: GCS-motor is driven by sedation, so rather than *naming* sedation
    as a confound (rule 54) the design made **RASS the baseline**. The primary then came back
    **+0.0049 [−0.0010, +0.0095]** — a clean ABSENT with every gate passing, the noise control dead on
    zero (−0.0000 [−0.0035, +0.0030]) and the incumbent not merely alive but powerful (+0.3513 [+0.3280,
    +0.3730]).
    **The features were not uninformative. They were redundant with a co-measured observation.** The same
    panel scores **+0.1550 [+0.1312, +0.1777]** over chance on its own. RASS and GCS-motor are both
    clinician bedside scores, routinely charted by the same nurse in the same assessment round — two
    readings of one act, sharing method variance that no instrument outside the room can access.
    **The check is one question at registration: could the incumbent and the outcome have been recorded by
    the same observer, at the same moment, as part of the same procedure?** If yes, the comparison is
    partly a test of whether the new instrument can reproduce an *observer*, not a *state*, and a null is
    uninformative about the state. Prefer an incumbent that is an **exposure** (a drug record, a dose, a
    time) over one that is another **observation**; if only an observation is available, register both
    arms and say which question each answers. Related to rule 32 — a measurement's availability defines a
    stratum — but distinct: here the incumbent is available everywhere and is *too close to the outcome's
    provenance*.
87. **A TRACK, COLUMN OR CHANNEL BEING PRESENT IS A FACT ABOUT THE INSTRUMENT, NOT ABOUT THE PATIENT —
    RULE 6 FOR TIME SERIES, AND IT COST THREE EXPERIMENTS AT ONCE.** Rule 6 says check that a
    `concept_id` column is populated before designing around it. The time-series version is easier to
    miss because the object *is* there and *is* well-formed. **E224, E225 and E227 all registered
    "mutually exclusive arms" and all three implemented it as `"Primus/EXP_SEVO" in tracks`.** An
    anaesthesia machine logs its sevoflurane and desflurane channels whether or not the vaporiser is ever
    opened, so a propofol case on a gas-reporting machine carries a volatile track that reads **0.00 from
    end to end** — and was classified as combined-technique and discarded. Measured by one pass of
    `max(v) > 0` over 250 cases: **propofol-only 44 → 114, sevoflurane-only 90 → 88, genuinely both
    101 → 31.** Every propofol number the project had reported came from 39 % of the eligible cases.
    Three things make this worth its own rule. **The exclusion was one-sided** — it barely touched the
    comparison arm, so it is not the harmless loss of power it looks like. **It selected on the
    ANAESTHESIA MACHINE**, a property of the theatre rather than of the patient or the drug, which rule 14
    forbids assuming innocent. And **the first explanation offered for the exclusion count was a
    plausible clinical story** — propofol induces, volatile maintains, used sequentially — written into a
    ledger row before anything was measured, which is rule 50 in miniature: the plausible mechanism is
    exactly what stops you checking. **The check is one line and belongs in every cohort predicate:
    a channel counts only if it is ever nonzero, and the count of rows the two predicates disagree on
    must be printed.**
88. **A COVARIATE PLACEBO CANNOT TEST A BETWEEN-ARM CONTRAST — ONLY AN ARM-LABEL PERMUTATION CAN.**
    Rule 55 says a placebo must be able to change the statistic it is a placebo for. This is its most
    expensive form, because the placebo *looks* like the textbook one. **E230 and E231 both died on it,
    in the same lineage, and the second death was one level deeper than the first.** The estimand was
    `mean(rho | propofol arm) - mean(rho | sevoflurane arm)`, and the placebo re-ran the covariate
    matching with the covariate rows PERMUTED. E230's match discarded nobody (85 pairs of 85 possible),
    so the placebo merely re-PAIRED identical cases and a difference of arm means does not depend on
    pairing: placebo +0.3701 against a real +0.3530. E231 added a derived caliper that genuinely
    discarded 43 of 85, and it *still* failed at p = 0.4767 — because permuting covariates changes
    **which subset of each arm is retained** and never the arm distinction itself, and a whole-arm
    effect survives any random subset of that arm. **A covariate placebo can only ever test whether the
    matching procedure manufactured the contrast; it cannot test whether the contrast is real.** The
    destruction that matches the estimand is permuting the ARM LABEL, which is the only operation that
    removes the drug contrast while preserving cohort, covariates, windows and code path.
    Two corollaries worth as much as the rule. **A stable number across matched, unmatched and randomly
    subset cohorts is evidence of robustness being misread as placebo failure** — +0.3799 / +0.3826 /
    +0.3671 across three cohorts is what insensitivity to case mix looks like, and the registered gate
    called it a refusal. And **when a confound named in a registration has an SMD that gets WORSE after
    the adjustment declared to handle it (1.1041 → 1.2105 for remifentanil here), the balance table is
    the result** — it says the two arms cannot be equated on that variable at all, and restriction to
    the stratum where it is present beats any amount of matching. Rule 54 was cited by name inside the
    file that then failed it.
89. **A RANK CORRELATION ACROSS MEASURES CAN BE ENTIRELY A ZERO-VERSUS-NONZERO SPLIT, AND THE CHECK IS
    LEAVE-GROUP-OUT, NOT LEAVE-ONE-OUT.** E234/E235 asked whether a measure's sensitivity to spectral
    translation predicts how much more it responds to sevoflurane than to propofol, over 15 panel
    measures. It returned **rho +0.6107, permutation p_hi 0.0100**, every gate passing, and printed a
    mechanistic verdict. **Four measures have essentially zero translation sensitivity and all four also
    have negative sevoflurane advantage; drop them and the correlation among the remaining eleven is
    +0.0273, p_hi 0.4705.** The relationship is a threshold contrast between two groups, not the
    dose-response the verdict's wording asserts — among measures that respond at all, how much they
    respond predicts nothing.
    **Leave-one-out does not reveal this and will reassure you falsely**: removing any single member of
    the zero group still leaves three, so rho only fell to +0.5253, which reads as robust. The diagnostic
    that works is to drop the whole group defined by the near-zero level of the independent variable and
    re-test. **Whenever an independent variable has a cluster at or near zero, the correlation is a
    two-group comparison in disguise and must be reported as one.**
    The second half matters as much: **a group defined by one property is usually defined by others too.**
    Those four measures are all high-frequency or EMG measures, so "sevoflurane's effect is concentrated
    at low frequencies" produces the identical split with no translation in it. A two-group contrast
    carries only as much mechanistic information as the groups are separable on the named property alone,
    and with n = 4 against 11 that is almost none. Related to rule 60 — check what else your grouping
    variable is correlated with, before the mechanism is named (rule 50).
90. **A DOCSTRING ASSERTING AN INVARIANT IS NOT THE INVARIANT — GREP THE ARGUMENT, NOT THE PROSE.**
    `fit_aperiodic`'s signature defaults to `mode="loglog_ols"`. The `whole_head_exponent` family passes
    `"loglog_robust"` explicitly (`seed.py:87`); `subband_exponents` does not (`exotic.py:295-296`), so
    `exponent_low` and `exponent_high` are fitted by a peak-biased plain OLS while the rest of the family
    is fitted robustly. **The candidate's own docstring states the opposite** — *"deliberately identical
    machinery… so any difference reflects the spectrum and not the estimator"* — which is how it survived
    review: a reader checking whether the family was consistent found a sentence saying it was.
    Measured cost: `exponent_low` comes out roughly 26× more sensitive to a 1 Hz spectral shift than
    `whole_head_exponent` despite an equally wide fixed band.
    **The most consequential instance was found only by grepping every caller** (rule 76's corollary):
    `seed.py:166` is `alpha_peak_hz_wide`'s own aperiodic fit and carries the same default, and since the
    peak is located as a residual *after* subtracting that fit, a peak-biased baseline flattens the
    residual the search depends on. A defect in a shared helper's DEFAULT propagates to every caller who
    omits the argument, and those callers are invisible at the definition site.
    **Two habits follow.** When a helper's behaviour is selected by a keyword with a default, grep every
    call site and tabulate which ones pass it — the count of callers that rely on the default is the size
    of the exposure. And when a docstring asserts that two things are computed identically, diff the two
    call sites rather than believing it (rule 20, applied to a claim of sameness rather than to two
    scripts).
91. **A GATE WRITTEN AS "SOME DRAW MUST FAIL" IS NOT A GATE, AND A SYNTHETIC CONTROL THAT IS TOO EASY
    CERTIFIES NOTHING.** E237 asked whether a known estimator defect corrupts `alpha_peak_hz_wide`. It
    returned a perfect pass — monotone at Spearman +1.0000, zero inversions, OLS and robust agreeing to
    **0.0000 Hz at every one of 17 frequencies**. That perfection was the tell. The synthetic
    oscillation was so far above the background that any peak-picker nails it, so the test never
    challenged the estimator; an SNR sweep run immediately afterwards put the cliff at amplitude ~0.08,
    where the two fits diverge and error rises to 0.34–0.46 Hz. **A control that passes at every point
    with zero error has not measured a tolerance, it has measured that the case was easy.** Sweep the
    difficulty until the thing breaks, and report where.
    **The gate failure is the more embarrassing half.** G3 required that a pure 1/f background return
    NaN, coded as `frac > 0.0` — that SOME draw refuse. Measured properly, the estimator returns a
    finite "peak" on pure noise in **87.5 %** of draws, and the gate passed on the remaining 12.5 %.
    That is rule 40 committed inside a file whose docstring cites rule 40. **A rate gate must name the
    rate**, and the consequence here was not cosmetic: a 93 % peak-detectability rate on real data had
    been read as 93 % of windows carrying an alpha peak, when it is indistinguishable from what the
    estimator produces from noise.
    **The general form, worth more than the instance:** when an instrument fires on nearly everything,
    its *availability* carries no information, so any gate built on availability (rule 32's stratum
    check included) is measuring the instrument's eagerness rather than the phenomenon. Measure the
    false-positive rate of a detector on signal-free input BEFORE using its detection rate as evidence.
92. **RULE 86'S CONVERSE, NOW DEMONSTRATED ACROSS 47 EXPERIMENTS: THE ONLY INCUMBENT THAT IS RELIABLY
    ALIVE IS THE ONE THAT SHARES A MEASUREMENT ACT WITH THE OUTCOME.** Rule 86 says an incumbent
    co-recorded with the outcome sets a bar nothing external can clear, and prescribes preferring an
    exposure or an objective measure. Challenge B has now tried that prescription five times and the
    consolidated record shows the trap it walks into. Of every incumbent this project has used —
    `relative_alpha_power`, the SMR predictor / `alpha_prom`, RASS, `any_sedative`, `Manual activity` —
    **RASS is the only one ever unambiguously alive, and it is alive precisely because a nurse charted
    it in the same assessment round as the outcome.** Every genuinely independent incumbent died, either
    structurally (sedative exposure has near-zero within-patient variance, so there is nothing to
    condition on) or empirically (E238: Rimbert 2018's manual-activity effect, ρ = 0.381 at n = 35,
    comes back at **−0.0841, |p| = 0.4368** on n = 87 with better than 95 % power for it).
    **So "name an independent incumbent" and "name a live incumbent" can be mutually exclusive, and when
    they are, the challenge is blocked on data rather than on design.** The diagnostic that establishes
    it is cheap and should be run before any further incumbent hunting: tabulate every incumbent tried,
    mark each as observation-or-exposure and alive-or-dead, and look for a cell that is both. If none
    exists after several honest attempts, further designs are rearranging the same impasse — say so, and
    spend the effort on access instead. Corollary: a null against a dead incumbent is not a weaker
    version of a null against a live one; it is a different sentence, and rule 53 exists to stop the two
    being written the same way.
93. **A SEARCH WINDOW WIDE ENOUGH TO CONTAIN A SECOND RHYTHM WILL FIND IT, AND YOU WILL CALL IT AN
    ARTEFACT.** `alpha_peak_hz_wide` searches 5-15 Hz. On Sleep-EDFx its N2 median is **13.500 Hz**, and
    I recorded that in a ledger row and a commit message as the estimator "reporting its own window edge
    where there is no alpha to find" — reasoning that slow-wave sleep has no alpha, which is true and
    irrelevant. **N2's defining electrophysiological feature is the sleep spindle at roughly 11-16 Hz**
    (PMID 33618345, verified: *"spindles are electrophysiological hallmarks of N2 sleep stage"*), and
    13.5 Hz is squarely inside it. The estimator was finding a real oscillation the search window
    happened to admit; the error was mine, and it is rule 21 — check the physiology BEFORE building a
    prediction on it, not after the numbers look odd.
    **The tell was available and I read it backwards.** Gated detection across the five stages came out
    N2 0.408 > N1 0.218 > N3 0.204 > W 0.141 > REM 0.085 — maximal in N2, reduced in slow-wave sleep,
    minimal in REM. That is the spindle-density profile, recovered by a prominence gate that was never
    told spindles exist, and it is a stronger validation of the instrument than the control the
    experiment actually registered. I had it filed as evidence the instrument was broken.
    **Two rules follow.** When a band-limited estimator is widened, enumerate every rhythm the new window
    now contains and say which one each cohort should express — an "alpha" search over 5-15 Hz is a
    theta/alpha/spindle search. And when a stage-wise or group-wise profile looks wrong, check it against
    the profile of every OTHER rhythm in range before concluding the instrument failed; a result that
    matches a different real phenomenon is not noise.
94. **A PLACEBO COMPARED WITH `>=` CANNOT FIRE AT A CEILING — AND A RANDOM-PARAMETER PLACEBO TESTS
    WHETHER THE PARAMETER IS SPECIAL, NOT WHETHER IT TRANSPORTS.** E244 ranked measures by how much
    accuracy is lost when a decision threshold learned on one deposit is imported to another. Its
    placebo drew a random threshold from the source's range and asked `mean(rand >= acc) < 0.05`.
    **`whole_head_exponent` transported at accuracy 1.0000 against a placebo MEAN of 0.6091 and was
    recorded as failing**, because 1.0000 is the maximum the statistic can take, so every random draw
    landing in the target's separation gap ties with it and counts as `>=`. The test is structurally
    incapable of passing for a perfect classifier — the better the result, the more certain the
    refusal. Rule 37's operator family, arriving at a boundary rather than at a sign.
    **The deeper error is rule 55 and it survives fixing the operator.** A random-parameter placebo asks
    whether the fitted parameter is SPECIAL. Deployment asks whether it WORKS at the target. Those come
    apart exactly when the classes separate well: if many thresholds succeed, transport is *easier*, and
    a placebo built on specialness reads that abundance as weak evidence. **Match the placebo to the
    decision, not to the parameter** — here, a threshold drawn from a deposit that shares nothing with
    either, or the target's own accuracy under a threshold from an unrelated measure.
    **The cheap general check: before trusting a placebo, ask what value the primary can maximally take,
    and whether the comparison can distinguish the real result from a tie at that value.** A statistic
    bounded above (accuracy, AUC, a rate, a resultant length) needs a strict comparison or a different
    reference, and rule 40's "construct the input that should pass" would have caught it in one line.
95. **A CHALLENGE DEFINITION IN PROSE DRIFTS; ANCHOR IT WHERE THE WORK IS REGISTERED.** The three briefed
    challenges are, verbatim: **A** *"predicts loss and recovery across anaesthetics while MINIMISING
    drug-identification information"*, **B** *"spontaneous EEG predicting command-following"*, **C**
    *"seeing a transition before the conventional monitor"*. The working characterisation drifted TWICE,
    both times caught by the investigator rather than by the project, and the second time it INVERTED
    challenge A: an entire session was spent measuring how much drug-identification information the panel
    carries — the quantity A asks a candidate to MINIMISE — and reporting a large value as a finding
    rather than as a disqualifier. A correction document written after the first occurrence did not
    prevent the second, because a document is only consulted by someone who already suspects drift.
    Two further symptoms of the same failure. **Challenge C's own negatives were scored against SEF95, a
    computed spectral-edge proxy, when the briefed comparator is the CONVENTIONAL MONITOR** — so three
    verdicts do not refute the claim they appear to refute, and VitalDB has recorded BIS all along.
    **And a fourth "challenge" accumulated that was never briefed at all**: grep returns zero hits for
    "Challenge D" in either brief, yet experiments, probes and a pre-registration were filed under it.
    **The fix is structural, not editorial.** `bsde/governance/CHALLENGES.json` holds the verbatim
    statements and each challenge's two acceptance halves; `registry_ledger.register()` now refuses any
    letter that is not briefed, names a retired one as retired, and ECHOES the verbatim statement at the
    moment of registration — so a registrant sees what they are claiming to test while claiming it. The
    general rule: **when a definition is load-bearing and consulted rarely, put it in the path of the
    action it governs.** Rule 74's lesson applied to scope rather than to a numerical guard.
