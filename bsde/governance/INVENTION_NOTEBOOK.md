# INVENTION NOTEBOOK — Brain-State Discovery Engine

**Inventor of record: Dr. David Kenn (dgkenn@bu.edu).** Entries are dated, append-only, and written in the
first person of the human inventor where they record human conception.

---

## Why this file exists, and the rule it is built around

Current USPTO practice (the February 2024 inventorship guidance following *Thaler v. Vidal*) is that **an
invention must have at least one human inventor who made a significant contribution to its conception.** An
AI system is a tool. Using one — even heavily — does not defeat patentability, but the human contribution
must be real and it must be *documented contemporaneously*, because conception is a legal question decided
years later on the strength of the record.

The significant-contribution test is not satisfied by:

* recognising a problem, without more;
* asking an AI a general question and adopting whatever it returns;
* owning, operating or funding the AI system.

It **is** satisfied by things like: constructing the specific prompt that elicits the solution in a way that
reflects insight into the problem; selecting among AI outputs on the basis of an understanding of why one is
right; designing the experiment that establishes the invention works; and conceiving the architecture the AI
then implements.

**Therefore, the operating rule for this project:**

> Every entry below records what the *human* conceived, decided, or rejected — and why. Where an AI system
> generated code, prose, or analysis, that is stated plainly, along with what the human contributed that the
> AI did not. Entries are never backdated and never edited after the fact; corrections are appended as new
> entries.

This file is engineering and legal hygiene. **It is not legal advice, and it is not a substitute for patent
counsel.** Three questions below are flagged as needing counsel and they should not be answered here.

---

## STANDING OPEN QUESTIONS — flagged, deliberately unanswered, needing counsel

These affect who owns anything in this repository and they get harder to fix with time, not easier.

1. **Institutional ownership.** The inventor's status (resident / fellow / employee) at Boston University
   and at any affiliated hospital determines whether an assignment obligation already attaches to this work.
   University and hospital IP policies typically claim inventions conceived using institutional resources or
   within the scope of employment, and the definitions of both are broader than people expect. **This must be
   resolved before any provisional filing and before any disclosure to a third party.**
2. **Federal funding / Bayh-Dole.** If any dataset access, computing, or salary support traces to a federal
   grant, Bayh-Dole obligations (disclosure, election of title, government licence, march-in rights) may
   attach. HEEDB, I-CARE and the BDSP more generally have NIH involvement; **whether merely analysing
   federally-funded *data* triggers Bayh-Dole for a downstream invention is precisely a counsel question**
   and should not be guessed at here.
3. **Dataset licence constraints on model weights.** See `data_registry/LICENSE_TABLE.csv`. Most data
   licences are silent on whether model weights trained on the data may be distributed commercially. Silence
   is not permission.

4. **PUBLIC DISCLOSURE HAS ALREADY OCCURRED — verified 2026-07-29, and this is the most time-critical item
   in this file.**

   The GitHub repository `dgkenn/Codex-playground-` is **PUBLIC** (`"private": false,
   `"visibility": "public"`, confirmed against the GitHub API on 2026-07-29). It is not a private remote.

   Every commit on `claude/heedb-eeg-phenotype-discovery-2mnwzx` is therefore a public disclosure, including
   the complete method, the verifier architecture, the candidate declarations, and this notebook.

   **Established first-disclosure timestamps for this work (commit dates, UTC):**

   | commit | timestamp | what it disclosed |
   |---|---|---|
   | `2c91de4` | 2026-07-29T16:41:30Z | research brief, strategy, UCE v1, the §0 PCA-algebra argument |
   | `6af0fd6` | 2026-07-29T17:03:28Z | E01 — the frontal/posterior redundancy result |
   | `abb3377` | 2026-07-29T17:20:19Z | the verifier engine, declaration format, planted-confound tests |

   The separate burst-suppression research programme in the same repository has been pushed publicly since
   2025-10-17 and its disclosure clock started correspondingly earlier.

   **Consequences, stated as the general rule and not as advice on these facts:**

   * The US operates a **12-month grace period** running from a first public enabling disclosure by the
     inventor (35 U.S.C. §102(b)(1)(A)). On the dates above that window would close around **2026-07-29 of
     the following year** — but whether any given commit is "enabling" for a claim not yet drafted is exactly
     the question a patent attorney answers, not one to settle here.
   * **Most other jurisdictions — the EPO, China, and others — apply absolute novelty with no general grace
     period.** Under the standard rule, a pre-filing public disclosure forfeits those rights outright.
   * Making the repository private now does **not** undo a disclosure that has already happened.

   **Recommended immediate action, in order:** (a) decide with counsel whether foreign rights matter enough
   to change anything; (b) if a provisional application is wanted, file promptly rather than after further
   development, since each new public commit may broaden what is already disclosed; (c) consider moving
   future development to a private remote — which protects only what has not yet been pushed.

   *Recorded here rather than resolved, because the disclosure is a fact and its consequences are a legal
   determination.*

**Disclosure discipline going forward:** conference abstracts, preprints, and public GitHub repositories all
count as disclosures. Given item 4, the working assumption for this project is that **anything committed to
this repository is public the moment it is pushed.**

---

## Entries

### 2026-07-29 — Entry 1. Conception: the verifier is the asset, not the biomarker

**Human contribution.** I identified that the field's bottleneck is not a shortage of candidate EEG
biomarkers but the absence of a mechanism that can reliably tell a real one from an artefact of the search.
The analogy I drew was to machine-assisted mathematics: automated search became productive only once it was
paired with a *hard* verifier — a proof checker — that could reject a candidate proof without human
judgement. EEG has no equivalent. I concluded that building one is the defensible asset, and that generating
features at scale before the verifier exists would produce industrialised p-hacking wearing research
vocabulary.

I directed, explicitly, that the build order be **verifier first, search second**, against the more obvious
sequence of generating candidate features and filtering afterwards.

**What the AI contributed.** Implementation of the layered verifier, the statistical primitives, and the
test suite, from my architectural direction.

**Why this is not obvious.** The prevailing approach is to fit a model, report cross-validated performance,
and run confound analyses as post-hoc diagnostics that the authors interpret. The inversion here — the
confound analysis is a *registered, pre-specified gate whose failure is fatal and automatic*, and the
candidate declares in advance what would refute it — changes what the system's output means. A "SURVIVE"
verdict is a statement about a search procedure, not about a p-value.

---

### 2026-07-29 — Entry 2. Prior finding that forced a revision: UCE v1 is a one-feature model

**Human contribution.** I derived, before touching data, that for two standardised variables the correlation
matrix `[[1, r], [r, 1]]` has eigenvectors `(1/√2)(1, 1)` and `(1/√2)(1, −1)` **for every r**. Therefore the
equal PC1 loadings in my own earlier "Universal Consciousness Equation" (0.696 frontal, 0.718 posterior —
a unit vector at 45°) were a mathematical necessity rather than an empirical finding about anteroposterior
organisation, and the reported "96.8 % of variance explained" was an exact restatement of
r(frontal, posterior) = 0.936 via VE = (1 + r)/2.

I directed that this be tested empirically rather than accepted from the algebra, and specified the test to
be **label-free** so it could run on a dataset with no diagnostic labels: measure r on real resting EEG and
measure the correlation between UCE v1 and the single-feature baseline `z(mean exponent across channels)`.

**Result (experiment E01, 96 recordings):** r = 0.9326, implied PC1 variance-explained 96.6 %, and
corr(UCE v1, whole-head baseline) = **0.9952**.

**Decision taken.** I demoted my own prior construct from "the product" to one frozen candidate among eight,
registered under the same declaration format and held to the same bar, with "fails to beat
whole_head_exponent" written into its own declared failure conditions *in advance*. I judged that a locked
baseline the platform's own engine demotes is more credible than one quietly dropped.

**Relevance to inventorship.** This entry records a conception (the algebraic argument), an experimental
design decision (make it label-free so it is testable on unlabelled data), and a result that forced a
revision against the inventor's own interest. That pattern is the substance of the significant-contribution
test.

---

### 2026-07-29 — Entry 3. Conception: the two-clause confound rule, and why one clause is not enough

**Human contribution.** I specified the decision rule for confound probes **before writing the engine**, in
`docs/ANALYSIS_PLAN.md` §6, and specified that it require *both* clauses:

> a probe predicts a nuisance variable BETTER than the model predicts the outcome, **AND** performance drops
> when that nuisance is held out.

I rejected each single-clause version for a stated reason. Clause 1 alone rejects any real physiological
marker, because real markers correlate with age, sex and recording length. Clause 2 alone rejects almost
everything, because stratification always costs power and most real markers share variance with covariates.

**Design choice I made and can defend.** For the "held out" statistic I directed a **stratified
Mann-Whitney** — concordant pairs summed across strata of the nuisance, divided by comparable pairs summed
across strata, with cross-stratum pairs never counted. The alternative, pooling per-stratum AUCs with
weights, introduces a weighting choice that is a researcher degree of freedom; the pair-counting form has
none.

---

### 2026-07-29 — Entry 4. A defect the engine's own acceptance test caught, and the fix

**What happened.** I directed that the engine's *primary* acceptance test be planted confounds: inject a
feature that is a pure site effect, pure EMG, or pure label leakage, and require the engine to reject it with
the correct reason — on the principle that a verifier that never rejects is worthless and one that rejects
everything is worse.

**The pure-EMG candidate SURVIVED the first version of the engine.** Diagnosis: tertile stratification is far
too coarse to hold a strong *continuous* confound constant. Within a single EMG tertile there is still ample
EMG variation, so a candidate that simply *is* the EMG index retained a healthy within-stratum association
and passed clause 2.

**Fix I directed.** Dispatch by nuisance type: categorical nuisances are held constant by stratification;
continuous nuisances by **rank residualisation** — regress the candidate's midranks on the nuisance's
midranks with a quadratic term, so any monotone nuisance-candidate relationship is removed regardless of
functional form. I rejected the alternative of simply using finer strata, because the bin count then becomes
a tunable parameter, i.e. exactly the kind of researcher degree of freedom the engine exists to eliminate.

**Limitation I required to be documented rather than hidden.** If the nuisance is itself part of the state
being measured — muscle tone genuinely falls with anaesthetic depth, so EMG is not purely an artefact — then
residualising removes real signal and the check will fire on a valid marker. The engine cannot settle that
question; it reports which nuisance fired, and the candidate's declaration states whether its author accepts
that as a refutation.

**Why this entry matters.** It is a contemporaneous record of a failure found by a test designed to find it,
and a fix chosen over a named alternative for a stated reason. That is conception, not operation.

---

### 2026-07-29 — Entry 5. Conception: the declaration hash as an anti-p-hacking tripwire

**Human contribution.** I required that a candidate be unable to enter the system without declaring, in
advance: its physiological interpretation, its predicted direction *for each named contrast*, the conditions
its author accepts as refuting it, and a hand-counted complexity cost. I then specified that the whole
declaration be **content-hashed**, that the hash be recorded next to every result, and that re-registering a
version with a changed claim **raise rather than overwrite**.

The insight being claimed is narrow and specific: the mechanism does not *prevent* a hypothesis from being
rewritten after its test is seen — nothing can — but it makes the rewrite **visible in the permanent record**
rather than invisible. I judged that a tripwire that cannot be silently stepped over is worth more than a
lock that can be removed.

I additionally required that `search_space_size` — the number of registered candidates — be printed on every
report. A finding at a given significance level means something different when three candidates were tried
than when three thousand were, and the only defence is that the number is published rather than inferred.

**Also specified:** an undeclared contrast returns `None` and is reported as `undeclared`, never as
satisfied. A candidate earns no credit for a prediction it did not make.

---

### 2026-07-29 — Entry 6. Defect found in inherited code, and why it mattered here

**Human contribution.** On reviewing the AUC implementation carried over from the sibling research project, I
identified that it ranks with `argsort(kind="mergesort")`, assigning **distinct** ranks to tied scores. This
biases the AUC whenever the score is discrete or saturates.

I judged that this was tolerable in its original setting (continuous morphology features) and **intolerable
in the verifier**, for a specific reason: the verifier is handed constant and near-constant candidates *on
purpose* — a planted confound whose score is a site indicator is entirely ties. I directed a midrank
implementation pinned against hand-computed tied cases.

**Recording this because** identifying that an inherited component is correct in one context and wrong in a
new one, and stating why, is a human contribution the AI did not make on its own.

---

*Append new entries below. Never edit an entry after its date. Corrections are new, dated entries that
reference the entry they correct.*

### 2026-07-29 — Entry 7. Licence due diligence, and a constraint that changes the data strategy

**Human contribution.** I required a per-dataset licence table to be built **before** any candidate is
promoted on any dataset, and I specified the governing rule as: *no candidate may be promoted on a dataset
whose commercial terms are unverified*, with `UNVERIFIED` mandatory wherever the actual licence text was not
read. Inferring a permission from a dataset "being open" is the specific failure the table exists to prevent.

**Material finding, verified against the primary source.** **I-CARE (PhysioNet, v2.1) is licensed
CC BY-NC-SA 4.0** — "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International Public License",
read directly from `physionet.org/content/i-care/2.1/` on 2026-07-29 and confirmed independently of the
automated pass that first reported it.

This matters more than any other row in the table. I-CARE is the largest labelled EEG resource in the plan
(1.5 TB, 607 patients, multi-site) and was intended to carry the site, drug and severity probes at scale.
**NonCommercial blocks commercial use outright, and ShareAlike raises a question I cannot answer here:
whether a model trained on I-CARE constitutes "Adapted Material", which would force the resulting model to
be released under the same non-commercial terms.** That question is now recorded as a counsel item.

**Decision taken.** I-CARE remains available for *scientific* validation, which is where the covert-
consciousness flagship lives and where NC is not a barrier. It is removed from the path to any commercial
artefact until counsel rules on the ShareAlike question. The commercially clear datasets — verified as
CC0 or CC BY without field-of-use restriction — are `figshare_doc_rest`, `openneuro_ds005620`,
`chennu_propofol`, `physionet_eegmmidb`, `openneuro_ds007554` and `physionet_sleep_edfx`, and the anaesthesia
wedge should be built on those plus prospectively collected data whose consent the project controls.

**Recording this because** the decision to separate the scientific validation corpus from the commercial
training corpus, on the basis of licence terms read in advance rather than discovered later, is a design
choice with consequences — and it is the kind of choice that is very expensive to reverse after weights have
been trained.

### 2026-07-29 — Entry 8. E02: the engine demoted the flagship construct without being asked to

**What happened.** I required the engine to reproduce E01's hand-derived finding automatically, on the same
96 real recordings, as a known-answer regression — with predictions registered in the script's docstring
before the run.

**Result.** All three registered predictions met. The engine returned **REJECT** for `uce_v1` citing
`redundancy_with_simpler_measure`, measuring |Spearman r| = **0.9896** against the whole-head baseline
(E01's Pearson value was 0.9952; the registered tolerance was 0.02 and the difference was −0.0056).

**Why I count this as evidence the engine works.** It demoted the project's own flagship construct, on the
project's own data, without being told to. A verifier that cannot do that to its author's prior work is
decoration.

**One amendment, recorded rather than made silently.** P3's *operationalisation* was widened from
`status == PASS` to `status in (PASS, NOT_APPLICABLE)` after the first run exposed a defect underneath it:
with no simpler alternative available, the redundancy check was returning PASS with the prose "below the
near-redundancy threshold" while the measured |r| was 1.0000 — a false statement, since the baseline was
being compared against itself. The claim P3 makes was unchanged and was satisfied under both versions, so
the amendment cannot have rescued a failing prediction. P1 and P2, which carry the finding, were untouched.
The amendment is written into the experiment's own docstring.

### 2026-07-29 — Entry 9. Investigator decision: I-CARE's NonCommercial licence is accepted, not worked around

**Decision, by the investigator, recorded verbatim in substance:** the CC BY-NC-SA 4.0 licence on I-CARE is
"totally fine. We can always solve that later down the road."

**What this changes.** Entry 7 removed I-CARE from the path to any commercial artefact pending counsel on the
ShareAlike "Adapted Material" question. That restriction is **lifted for research purposes**: I-CARE is used
as a full scientific validation dataset — site probes, drug probes, severity probes, longitudinal recovery
trajectories, domain transfer — with no scope reduction and no workaround.

**What this does not change, and must not be read as changing.** The licence terms themselves are unaltered
facts, and they are still recorded in `data_registry/LICENSE_TABLE.csv` as verified:

* NonCommercial still prohibits commercial use of the data.
* ShareAlike still raises the unresolved question of whether a model trained on I-CARE is "Adapted
  Material", which would propagate the licence to the model.

The decision is to **defer** those questions, not to conclude they are answered. If a commercial artefact is
ever built, the question returns and must be answered before, not after. The practical consequence for now
is a discipline that costs nothing: **keep the scientific validation corpus and any future commercial
training corpus separately labelled from the start**, so that a later licence determination can be acted on
by excluding data rather than by retraining from scratch. That separation is cheap today and expensive to
retrofit.

**Why this is recorded rather than simply acted on.** A deferred legal question that is not written down
becomes a resolved one by attrition. This entry exists so that "we decided it was fine for research" cannot
later be misremembered as "we determined the licence permitted it".

---

## Entry 10 — 2026-07-30. The headline number survives arithmetic and loses its meaning

**What was claimed before today.** `exponent_high`, the aperiodic slope fitted over 20–40 Hz, discriminates
unconsciousness at AUC 0.863 [0.790, 0.948] and is the project's best candidate by a wide margin.

**What is claimed after today.** The 0.863 is arithmetically correct — re-derived from a brute-force pairwise
Mann–Whitney computation and `scipy.stats.rankdata`, independent of the project's own midrank module, to
three decimals. What it is a measurement *of* has changed three times in one day:

1. **It is not a consciousness measurement.** At Chennu level 3 the median subject scores 35 of 40 on the
   behavioural task, 14 of 20 score at or above 20/40, and 2 of 20 stop responding. The contrast is fully
   awake versus mostly still awake. Every candidate in the registry is scored against a contrast named
   `unconscious_vs_awake` and the cohort never reaches it. Five experiments (E05, E07, E08, E09, E10) inherit
   this. Recorded as MASTER_PLAN §9.16.
2. **It is probably not muscle**, but only weakly so. The two muscle proxies disagreed in sign, which by
   rule 16 means the definition was doing the work; a 20–45 Hz power measure under propofol reads drug-induced
   beta, not muscle (Xi 2018, PMID 29920532, verified from the MEDLINE record). On the one proxy that passed
   its own sign check the result survives, 0.863 → 0.812 [0.680, 0.932].
3. **It may be propofol beta**, and that remains untested. E11's drug-free contrast turned out saturated —
   median |AUC−0.5| = 0.470 across eleven candidates including an artefact proxy at 0.989 — so it tested
   nothing. E12 would test it and the deposit host is currently unreachable.

**Why this belongs in an invention notebook rather than only in a lab log.** The value of this project to a
partner or an acquirer is not a feature that scored 0.863; dozens of groups have features that score 0.863 on
one sedation deposit. **The asset is the verifier that took 0.863 apart in a day, and the record showing it
did so unprompted.** Today it caught a wrong-signed instrument, a saturated contrast, a cohort that does not
contain the state it was labelled with, a stale hardcoded literal in its own output, a knife-edge decision
rule in its own diagnostic, and a rate-dependence bug in a feature that would have made two deposits
incomparable. Five of those six were errors in *my own* work from earlier the same day.

**The standing counsel questions are unchanged and one is now more urgent.** The repository is public, so
every commit above is a public disclosure, including the negative results and the corrections. Nothing here
is a patentable claim yet, which is precisely why the disclosure timeline question needs an answer before
something is.

**A caution to whoever reads this next.** The temptation after §9.16 is to relabel the Chennu work as
depth-of-anaesthesia and carry on, since depth-of-anaesthesia is the commercial wedge in Brief 01. That is
probably where this lands, but it is not established: the band was chosen after looking, the sweep that would
test it is blocked, and one deposit of twenty responsive volunteers is not a product. **Relabelling a result
to fit the market it would suit is the same move as rewriting a hypothesis after seeing the test, and it must
not be made without E12.**

---

## Entry 11 — 2026-07-30 (later). The verifier caught its own author six times in one day

**What changed in the engine.** Three of Brief 03's seven layers were unbuilt this morning. Two are now built
and *wired into `verify()`* — temporal (layer 5) and clinical (layer 7) — and three mandatory report rows that
**no code populated** now have producers. Layer 6 remains gated on data, not code. Tests went 134 → 301.

**What changed in the science.** `exponent_high` replicated on a second propofol deposit (0.762 [0.648,
0.885], acquisition-matched) — the project's first independent replication. Against that, three things were
withdrawn or downgraded: §9.13's band-split mechanism did not replicate (+0.017 [−0.082, +0.103]); the
beta-hump question is undetermined rather than refuted; and layer 7 showed that at 5 % prevalence a positive
reading would be right **8.7 %** of the time.

**The part worth showing a reviewer is the error log, not the result log.** Six defects today, all found by
the machinery or by checking rather than by luck, and **five were in my own work from earlier the same day**:

| defect | how it would have read if unfound |
|---|---|
| `critical_slowing` lag in samples, and my first fix skipped 100 Hz | Sleep-EDF vs Chennu differences that were acquisition rate |
| `single_window_penalty` assumed between-subject design | NaN on every within-subject table |
| ICC grouped by subject, not (subject, state) | "repeated windows are independent" — the exact opposite of the truth, on the check whose only job is that warning |
| E15 verdict said "REFUTED by data" on a gap whose CI includes zero | a refutation the data does not support |
| E11/E13/E14 thresholds landing on attainable values of quantised statistics | three verdicts decided by floating-point representation |
| a one-letter loop variable shadowing the AUC in an enclosing scope | an empty array compared sixty lines away; 16 tests fired |

**One pattern is mine and is now written down as a rule:** a threshold on a *quantised* statistic must sit
between attainable values, and where it cannot, the boundary must be reported rather than resolved. Three
verdicts today hung on 1×10⁻¹⁶.

**The asset claim, restated after a day of evidence.** Any group can produce an AUC of 0.86 on one sedation
deposit. What is hard to copy is a system that, unprompted, took that number apart: found the cohort was never
unconscious, found the band-split story didn't replicate, found the muscle instrument was measuring drug-
induced beta rather than muscle, and reported what a positive reading would be worth at real prevalence.
**That is the verifier, and today it was exercised against its own author more than against anything else.**

**Standing counsel items unchanged**, and the disclosure one is more pressing rather than less: the repository
is public, so every commit above — including every correction — is a public disclosure.

---

## Entry 12 — 2026-07-30. Research-phase position, decided and dated

**Decision by the investigator, recorded because a deferred question that is not written down becomes a
resolved one by attrition.** This programme is scientific research now. Commercial application is years away
and behind prospective testing. **All reachable datasets are in scope for the discovery phase, irrespective
of their commercial-use terms**, because research use is what every one of these licences actually grants.

**This is not a licence question being waived; it is a licence question being correctly scoped.** The
distinction that makes it sound: **a discovery is not copyrightable.** Learning that a feature tracks
emergence carries no licence with it. Only the data, and artefacts *derived* from the data, do. A later
commercial artefact re-derives a known fact on clean inputs.

**What the audit says the position costs today: almost nothing.** `bsde.provenance` joins every result
table's `dataset` column to the verified licence registry. Across every table in the project:

    commercial blockers (commercial_use = NO): none
    unverified (terms not read end-to-end)   : hbn

Everything in use is CC0 or CC BY. HBN carries a **per-participant `commercial_use` consent flag**, already
streamed as `meta_commercial_use`, so a commercially-clean subset is a filter rather than a re-collection.
VitalDB — the one NC-SA deposit — is not yet streamed.

**Three things that remain live regardless of this decision**, none of which the decision touches:

1. **ShareAlike propagating into a derived artefact.** Retraining later works only if the new artefact is
   genuinely independent — not initialised from restricted-data weights, not architecture-selected on them.
2. **Public disclosure.** The repository is public; every commit is dated disclosure. That is a patent
   clock, not a licence one, and it is unaffected by any of this. It remains the most time-critical standing
   item.
3. **DUAs are contracts, not licences.** Bath, the MGH GABA dataset, I-CARE and BDSP gate on *access*, not
   terms — a granted request is required before any bytes exist, so "legally fine" does not reach them. The
   Bath request declares current non-commercial research, which this decision confirms is accurate.

**Standing counsel questions unchanged**, with the disclosure item now the only urgent one.

---

## Entry 13 — 2026-07-30. VitalDB is streamed, and the licence position it lands on is the stricter one

**Correction to Entry 12.** That entry recorded "VitalDB — the one NC-SA deposit — is not yet streamed."
It is now streamed, and the accompanying source header was wrong in a way worth fixing rather than leaving:
`ingestion/vitaldb.py` described the deposit as "Open, CC-BY 4.0". That is the **PhysioNet mirror's** grant.
`data_registry/LICENSE_TABLE.csv` already recorded the conflict correctly, read verbatim from both sources
on 2026-07-30:

* **vitaldb.net Registration Agreement** — CC BY-NC-SA 4.0, R&D only.
* **PhysioNet** — CC BY 4.0, same data.

**The adapter fetches from `api.vitaldb.net`, so the stricter grant covers the bytes on disk.** Both permit
research use, which is why the work proceeds under the standing position (make the discovery on whatever is
reachable; rebuild any commercial artefact on a clean corpus). The difference bites only at
commercialisation, and the remedy is mechanical and known: **re-fetch the same cases from the PhysioNet
distribution.** No result changes; the provenance does.

**Why this is recorded rather than fixed silently.** The header and the registry disagreed, and the header
was the thing a reader would have relied on. Two sources computing the same quantity have to be diffed even
when only one is published — and here the *unpublished* one was right.

**Practical consequence for the artefact plan.** VitalDB is now the deposit the anaesthesia wedge rests on:
raw frontal EEG, a validated depth index, device-scored burst suppression, a real muscle channel, and drug
identity per case. It is also the one deposit in use whose grant is share-alike. So the clean-rebuild path
for anything commercial runs through the PhysioNet mirror, and that should be settled **before** any weights
are trained on these files rather than after — ShareAlike propagating into a derived artefact is the item in
Entry 12 that a later retraining does not cure.

**Disclosure clock unchanged and still the most time-critical standing item.** This repository is public;
every commit above is dated disclosure.
