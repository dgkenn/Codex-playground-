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
