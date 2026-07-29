# MASTER PLAN

**What this is.** The single operating plan for the Brain-State Discovery Engine (BSDE), reconciling three
investigator-supplied briefs with each other and with what has actually been verified in this repository.

**Sources vs. plan.** `RESEARCH_PROGRAM_BRIEF.md` (Brief 01, the question), `BRIEF_02_DATASET_STRATEGY.md`
(Brief 02, the data), and `BRIEF_03_AI_DISCOVERY_LAB.md` (Brief 03, the method) are the investigator's own
words, saved verbatim, and **immutable — never edited, regardless of what analysis later finds.** Where this
plan departs from a brief, the departure is recorded here (and in `RESEARCH_STRATEGY.md` §9, per Brief 01
§25's explicit permission) — never smoothed into the brief's text.

**This file is the living plan.** It is revised whenever a result, a licence check, or a dataset inspection
changes what the project should do next. `RESEARCH_STRATEGY.md`, `ANALYSIS_PLAN.md`, `LITERATURE_MAP.md`, the
`data_registry/` CSVs, and `governance/` all remain authoritative for their own domain in more detail; this
document is the map between them and the briefs, not a replacement for any of them.

**How to tell which is which.** Anything under `docs/BRIEF_0*` or `docs/RESEARCH_PROGRAM_BRIEF.md` is a
source and is quoted, never paraphrased into a changed claim. Everything else, including this file, is
project output and carries a verification status on every factual claim: **VERIFIED** (checked against code,
a test run, or a primary source this session or a prior logged one), or **UNVERIFIED / REQUIRES
VERIFICATION** (asserted by a brief or a prior agent, not independently checked here). No claim below is
presented as more certain than that.

---

## 0. The thesis in one paragraph

In Brief 03's own framing, this is **"an autonomous discovery-and-validation system that identifies compact,
physiologically grounded, cross-domain brain-state representations and converts them into prospective control
products"** — explicitly *not* an attempt to own "an AI model for EEG," a category the brief itself says is
already crowded. The proprietary asset is the verifier (the "hard proof-checker" EEG does not otherwise have),
not any single biomarker, including UCE. Two applications sit on top of that engine and they are deliberately
different in kind: the **wedge** is anaesthesia/perioperative EEG — domain credibility, prospective access,
existing drug/infusion and monitor (BIS/PSI) comparators, and a controllable perturbation, all of which make
it commercially tractable now. The **flagship** is covert consciousness / cognitive motor dissociation — the
scientifically highest-value and highest-stakes question the engine can be pointed at, where a false positive
is a clinical harm (Brief 01 §20) and where public data can validate a hypothesis but, on the investigator's
own dataset survey (Brief 02), cannot yet fully train or clinically deploy one. Anaesthesia work de-risks and
funds the engine; covert consciousness is what the engine is ultimately for. Conflating the two — treating an
arousal marker validated on anaesthesia as if it says something about consciousness — is the single failure
mode this plan is most organised against (§1, §6, `RESEARCH_STRATEGY.md` §8 item 1).

---

## 1. Where the briefs disagree with established results

| # | claim | source | established result | resolution |
|---|---|---|---|---|
| 1 | UCE v1's frontal/posterior split is a discovered two-region construct; "the underlying two-feature PCA reportedly explained approximately 96.8% of variance" (Brief 01 §4); weights 0.696/0.718 are presented as the construct itself | Brief 01 §4 | **E01** (96 real recordings, VERIFIED): r(frontal, posterior exponent) = 0.9326; corr(UCE v1, z(mean exponent)) = 0.9952. For two standardised variables PC1 loadings are *always* (1/√2, 1/√2) regardless of r — the 0.696/0.718 asymmetry is arithmetic, not physiology (`RESEARCH_STRATEGY.md` §0). **E02** (VERIFIED, `governance/SEARCH_LOG.jsonl`): the engine independently REJECTed `uce_v1` for `redundancy_with_simpler_measure` at \|Spearman r\| = 0.9896 against `whole_head_exponent`. | UCE v1 stays **frozen** exactly as specified (Brief 01 §4 forbids redefinition) and is still evaluated as one candidate among eight — but every description of it in this project must call it what the algebra and the data show: **an approximately one-feature whole-head aperiodic-exponent marker.** "96.8% of variance explained" is retired as evidence (`RESEARCH_STRATEGY.md` R-04) and H4 ("UCE is an arousal marker, not a capacity marker") is the *default* hypothesis, not an alternative (R-02). |
| 2 | Figshare 10.6084/m9.figshare.23552964 "contains 59 patients with disorders of consciousness [and] 32 healthy controls" with an "associated clinical study enrolled patients evaluated using resting EEG and behavioral diagnosis" — listed as the **primary resting-state UWS/MCS benchmarking dataset** | Brief 02, dataset #2 | Exhaustive inspection of every file in the download (96 `.dat`, 98 `.vhdr`, 98 `.vmrk`, 1 `meta.json`) plus a fresh Figshare API pull (VERIFIED, re-checked 2026-07-29): **no participants file, no diagnosis field in any header or marker, no decodable patient/control naming convention across all 98 filenames.** `DATASET_REGISTRY.csv` records this as a direct disagreement with Brief 02. | Figshare is downgraded from "primary UWS/MCS benchmarking set" to an **unlabeled EEG corpus.** It remains usable for label-free measurement-property work — which is exactly what E01/E02 already did with it — and for domain-shift or aperiodic-exponent analysis, but the UWS-vs-MCS diagnostic-benchmarking role Brief 02 assigns it **cannot be executed as written** unless an external label source is located (not yet searched for). |
| 3 | I-CARE is listed as a plain Tier-1/MVP-stack PhysioNet resource ("approximately 23.7 GB") alongside openly reusable datasets, with no field-of-use caveat, feeding into Brief 03's proprietary "harmonized multi-domain data architecture" asset | Brief 02, dataset #4; Brief 03 "proprietary layers" list | I-CARE's licence is **CC BY-NC-SA 4.0 — commercially blocked** (VERIFIED against the PhysioNet view-license page). Actual size is **1.5 TB uncompressed, not 23.7 GB** (VERIFIED against the PhysioNet content page — the brief's figure is wrong by two orders of magnitude and the dataset cannot be fully downloaded in this environment, 19 GB free). Whether a model *trained on* I-CARE features counts as ShareAlike "Adapted Material" is an open question this project has explicitly deferred to counsel, not resolved. | I-CARE is used exactly as Brief 02 itself later cautions (§ "critical conceptual warning") — external validation, domain shift, confounder resistance, **never** a trained artefact offered commercially — and this project's governance record (`LICENSE_TABLE_NOTES.md` §2–3) treats it, `vitaldb`, and every dataset with an unverified licence as **blocked by default** for any commercial claim until a lawyer signs off. Brief 03's "proprietary data architecture" cannot include I-CARE-derived weights as a shippable asset under current terms. |
| 4 | The aperiodic/1/f exponent and UCE built from it are presented as the investigator's own construct and a candidate piece of novel IP (Brief 01 §4; Brief 03's "discovered representations" as a proprietary layer) | Brief 01 §4; Brief 03 "proprietary advantage" | **Colombo et al., PMID 30639334, is prior art** (UNVERIFIED beyond the citation itself — not re-pulled via E-utilities this session, flagged for the next literature-map refresh) for the resting-state spectral (aperiodic) exponent as a marker of the *presence* of consciousness, tested across propofol/xenon/ketamine, n=5/group. | UCE's scientific contribution is **validation at scale of an existing marker**, not discovery of a new one. Any IP claim (`governance/INVENTION_NOTEBOOK.md`) must be built on what is actually novel here — the verifier architecture, the redundancy/confound-probe machinery, any genuinely new invariant the engine discovers later — not on "aperiodic exponent predicts unconsciousness," which Colombo anticipates. This is exactly the kind of prior-art check Brief 01 §11 asks for and it must land in `LITERATURE_MAP.md`, not only here. |
| 5 | BNCI/BCI-Competition-IV 2a/2b are listed as freely reusable method-development datasets (Brief 02, Tier 4, item 13) with no licence caveat | Brief 02, dataset #13 | Licence is **CC BY-ND 4.0** (VERIFIED, `LICENSE_TABLE.csv`) — explicitly "You do not have permission... to Share Adapted Material." A trained decoder or feature representation built on 2a/2b could plausibly count as Adapted Material. | Usable for internal method development (decoder benchmarking, false-positive calibration) exactly as Brief 02 intends, but **no derived model, weight set, or representation trained on 2a/2b may be published or shipped** without a legal read of the No-Derivatives clause — flagged in `LICENSE_TABLE.csv` row `bnci_bciciv_2a2b`, not yet resolved. |

---

## 2. The verifier stack: Brief 03's seven layers vs what is built

| # | layer (Brief 03) | what it asks | status | module / test | what's needed to complete it |
|---|---|---|---|---|---|
| 1 | **Computational** | Correct implementation; unit tests; synthetic-signal recovery; reproduction of known effects | **BUILT** | `features/aperiodic.py`, `synth.py`; `tests/test_aperiodic_recovery.py` (7), `test_complexity_features.py` (14), `test_connectivity_features.py` (6), `test_spectral_features.py` (11) | Nothing blocking; extend ground-truth cases as new candidates are added |
| 2 | **Statistical** | Nested validation; CIs; calibration; multiple-comparison control; subject-level independence | **PARTIAL** | `verifier/engine.py::layer_statistical` (subject-level permutation null, directional AUC); `verifier/stats.py` (`cluster_bootstrap_ci`, subject-level bootstrap; `brier()` and `calibration()` exist as primitives, VERIFIED by reading `stats.py`) | Calibration primitives are **implemented but not yet wired into any engine layer or report** — no candidate has produced probabilistic output on a labelled cohort yet, so they have never actually run end-to-end. Multiple-comparison control across candidates (vs. within one candidate's contrasts) is not implemented. |
| 3 | **Adversarial** | EMG, site, drug, age, leakage probes; preprocessing sensitivity | **PARTIAL** | `verifier/engine.py::layer_adversarial` + `check_redundancy`; `tests/test_verifier_rejects_planted_confounds.py` (17) — the project's stated primary acceptance test | The probe machinery is generic (any `Cohort.nuisance` key — site, drug, age, EMG index — is probed by the same two-clause rule), so this is functionally complete for confound/redundancy checks. **Preprocessing-sensitivity sweeps (brief §12, `ANALYSIS_PLAN.md` §4) are not implemented anywhere** — `report.py` carries `preprocessing_sensitivity` as a mandatory report row but nothing computes it, so every report prints `NOT_RUN` there. |
| 4 | **Cross-domain** | Held-out datasets, devices, drugs, etiologies | **BUILT** (mechanism), **UNEXERCISED** (in practice) | `verifier/engine.py::layer_cross_domain` (leave-one-dataset-out, direction-agreement across held-out cohorts) | The mechanism is tested against synthetic multi-cohort data. It cannot yet be exercised for real because only **one** real dataset (Figshare, unlabeled) has been streamed through the pipeline — leave-one-dataset-out needs ≥ 2 labelled datasets, which do not yet exist here. |
| 5 | **Temporal** | Predicts transitions; direction preserved within-subject; prospective | **NOT BUILT** | `engine.py::verify` explicitly marks `temporal` `NOT_RUN` when a candidate's declaration requires it (lines ~524–530) | No temporal-transition feature or model exists in `src/bsde/`. Needs a candidate whose predictions are stated over time (not a single scalar) plus a dataset with serial recordings per subject (I-CARE hourly segments are the obvious first target once ingested). |
| 6 | **Mechanistic** | Ketamine, REM dreaming, locked-in, neuromuscular blockade dissociations | **NOT BUILT** | same `NOT_RUN` treatment in `engine.py` | No TMS-EEG/EBRAINS adapter exists (only `local_brainvision`, `http_edf`, `openneuro_s3`, `physionet_wfdb` are built) and no dissociation dataset (ds005620 dreaming, EBRAINS TMS-EEG) has been ingested yet. This layer is gated on §3/§4 below, not on verifier code. |
| 7 | **Clinical** | Adds value over clinicians + existing monitor; changes a decision; improves an outcome | **NOT BUILT, AND NOT REACHABLE WITH PUBLIC DATA** | same `NOT_RUN` treatment | `RESEARCH_STRATEGY.md` §6 already states Stage 5/6 (gates E/F) are "not achievable with public data" — this is a Brief-01-§19 problem, not an engineering gap. Do not build toward this before a prospective protocol exists. |

**Test count, verified by running the suite this session:** `python -m pytest tests/ -q` → **134 passed, 2
skipped in 15.4 s.** The 2 skips are network-dependent adapter tests, gated behind `BSDE_NETWORK_TESTS=1` by
design, not failures.

---

## 3. The dataset plan

### 3.1 Brief 02's minimum-viable 12-dataset stack, with current access state

| priority | dataset | core purpose (Brief 02) | CURRENT ACCESS STATE |
|---|---|---|---|
| 1 | Bath PDoC MI-BCI (DOI 10.15125/BATH-01632) | Direct task-based command-following | **access request required** — VERIFIED restricted; no named open licence; redistribution prohibited by the landing page's own text |
| 2 | Figshare 59-patient DoC EEG (10.6084/m9.figshare.23552964) | Resting-state UWS/MCS modelling | **on disk, streaming in progress** — CC BY 4.0 VERIFIED open; 98 recordings present locally at `/tmp/uce_data/figshare_doc`; feature extraction via the streaming runner produces `results/figshare_features.csv` (resumable; check the file's own row count rather than trusting a number written here) — but see §1 row 2: it carries **no usable diagnostic labels**, so it can only serve label-free work |
| 3 | I-CARE (PhysioNet v2.1) | Acute coma trajectories, multicentre validation | **streamable now** — VERIFIED open, no credentialing, via `ingestion/physionet_wfdb.py`; not yet ingested in this repo. 1.5 TB total (VERIFIED, not the brief's 23.7 GB); CC BY-NC-SA 4.0, commercially blocked (§1 row 3) |
| 4 | EBRAINS DoC TMS-EEG (12 patients) | Perturbational validation | **unverified / access route unclear** — EBRAINS Knowledge Graph is a JS-rendered SPA; static fetch returned no license or access text (VERIFIED attempt, no result). No adapter exists for EBRAINS. |
| 5 | OpenNeuro ds005620 (propofol/dreaming) | Experience despite unresponsiveness | **streamable now** — VERIFIED open (CC0, read directly from `dataset_description.json`), reachable via `ingestion/openneuro_s3.py`; 83 GB exceeds this environment's 19 GB free disk, so full local mirroring is infeasible — the streaming-only design (`runner.py`) is the intended mitigation and has not yet been pointed at this dataset |
| 6 | Chennu propofol (Cambridge) | Controlled sedation/recovery | **streamable now, likely** — CC BY 2.0 UK VERIFIED (fully open, more permissive than the registry's prior "requires verification"); size/exact file layout not yet checked against an adapter |
| 7 | VitalDB | Real-world anaesthesia scale | **access-route present, licence unresolved** — CC BY-NC-SA 4.0 base + a bespoke Registration Agreement read at MODERATE confidence only (the linked full DUA could not be fetched); treated as commercially blocked by the conservative default until counsel reads the executed agreement |
| 8 | EEGMMIDB (PhysioNet) | Motor-imagery method development | **streamable now** — VERIFIED reachable (HTTP 200); licence ODC-BY 1.0 VERIFIED fully permissive, including commercial use |
| 9 | OpenNeuro ds007554 | Multitask intentional-modulation development | **streamable now** — VERIFIED open (CC0), 4.5 GB, fits this environment |
| 10 | Sleep-EDF Expanded | Pipeline/state-transition baseline | **streamable now** — VERIFIED reachable; ODC-BY 1.0 VERIFIED; **only 2 EEG channels, so it cannot support UCE v1's frontal/posterior split as specified** — noted as a real constraint, not an oversight |
| 11 | SHHS | Large-scale sleep validation | **access request required, and currently unverifiable from here** — sleepdata.org returned HTTP 503 on every attempt this session (VERIFIED as a repeated block, not a one-off) |
| 12 | MESA Sleep | Independent demographic validation | **access request required, and currently unverifiable from here** — same HTTP 503 block as SHHS |

Two additional datasets are in `DATASET_REGISTRY.csv` beyond this 12-item list, both Brief-02-named but outside
its own "minimum viable" table: **PhysioNet GABAergic-anaesthesia multitaper spectra** (Tier 2 item 8 — turns
out to be **credentialed/restricted**, not the open PhysioNet download Brief 02's placement implies, and
contains only pre-computed spectra, not raw EEG) and **BNCI BCI-Competition-IV 2a/2b** (Tier 4 item 13 — CC
BY-ND 4.0, see §1 row 5).

### 3.2 Brief 02's five claim components, mapped to datasets

| claim component | datasets (per Brief 02) | current status of that mapping |
|---|---|---|
| 1. EEG preserves evidence of intentional command-following | Bath, EEGMMIDB, BNCI, ds007554 | Bath (the only patient-level evidence) is access-request-only; the three healthy datasets are method-development aids only, per Brief 02's own caveat — **none of the four has been ingested yet** |
| 2. Resting-state substrate predicts task capacity | Bath resting/pre-cue, Figshare, EBRAINS TMS-EEG, Chennu, sleep sets | Figshare is ingested but **unlabeled** (§1 row 2) — it can supply resting-state feature distributions but not diagnosis-conditioned ones as Brief 02 assumes |
| 3. Representation ≠ arousal | REM dreaming (ds005620), Chennu mild-vs-moderate, MCS-vs-UWS, locked-in, eyes-open/closed | Depends on data not yet ingested (ds005620, Chennu) and on Figshare labels that do not exist (locked-in/MCS/UWS) |
| 4. Not merely prognosis/injury severity | I-CARE, Figshare, Bath CRS-R | I-CARE not yet ingested; Figshare has no severity/outcome labels; Bath not yet accessed |
| 5. Survives drug/etiologic shifts | Propofol, VitalDB, sleep, cardiac-arrest coma, chronic DoC, LIS | Same gating: everything here is either not yet ingested or, for the one ingested dataset, unlabeled |

**Bottom line, stated plainly:** as of this session, exactly **one** of Brief 02's twelve datasets has any real
EEG flowing through the pipeline (Figshare), and it cannot carry claim components 2–5 in the way Brief 02
assumes, because it has no labels. The dataset plan's near-term job is ingestion of I-CARE and Sleep-EDF (both
verified open, both streamable now, no licence blocker) — not further analysis of Figshare alone.

### 3.3 What public data cannot settle (from Brief 02's own gaps section)

* No public dataset combines raw task EEG + task fMRI + repeated CRS-R + resting EEG + etiology + sedatives +
  longitudinal outcome + independent adjudication — the full multimodal CMD ground truth does not exist
  publicly.
* No public acute-ICU active-task command-following cohort exists (I-CARE is prognostic/resting; Bath is
  chronic DoC).
* Public DoC datasets rarely carry more than one active paradigm; motor imagery alone is an inadequate test of
  command-following.
* Drug metadata (sedatives, antiepileptics, baclofen) is incompletely exposed in public chronic-DoC datasets.
* Public CRS-R timestamps are often not contemporaneous with the EEG they are meant to validate.

Brief 02's own conclusion — a later **prospective acquisition protocol is required** for full clinical
validation — stands. Nothing found this session changes that.

---

## 4. The seven breakthrough programs, prioritised

| rank | program (Brief 03) | what it is | dependency | recommendation |
|---|---|---|---|---|
| 1 | **7. The EEG experimental compiler** | Software that turns a scientific question into a reproducible, pre-registered analysis end-to-end | The verifier stack (§2) and ≥ 2 labelled ingested datasets | **NOW** — this is closest to what is already built (`experiments/e01_*`, `e02_*` are hand-written instances of exactly this pattern); the highest-leverage next engineering step is generalising that pattern, not writing a ninth candidate by hand |
| 2 | **5. Automated mechanistic experiment generation** | Given competing explanations (e.g. UCE = capacity vs. UCE = GABAergic slowing), propose the dataset/experiment that best separates them | A literature/hypothesis library (`LITERATURE_MAP.md`) and the confound-probe machinery (§2 layer 3, already built) | **NOW** — H4 (UCE-as-arousal, `RESEARCH_STRATEGY.md` §3) is already exactly this kind of competing-explanation test, and the machinery to run it exists; extending it to propose the *next* dataset automatically is incremental |
| 3 | **2. Cerebral resilience as a latent phenotype** | Patient-specific dose-response/recovery curves under anaesthesia as a controlled stress test | VitalDB or Chennu ingested with per-subject dose/time series | **NEXT** — this is the commercial wedge (§0); blocked only on ingesting VitalDB (licence moderate-confidence, scientific-use is fine) or Chennu (fully open) and is not blocked by any missing verifier layer |
| 4 | **6. Automated biomarker composition** | Combine adequacy/substrate/reactivity/cognition/intentional-modulation into a profile rather than one score | Layers A–F populated with real candidates across ≥ 2 domains | **NEXT** — natural extension of the candidate registry (already 8 candidates) once cross-domain data exists; premature before §3's ingestion gap closes |
| 5 | **1. The EEG periodic table of brain states** | A low-dimensional manifold organising all major EEG states (sleep, anaesthesia, coma, cognition) | Wide multi-domain ingestion (sleep + anaesthesia + coma + DoC, at minimum 4–5 datasets) and dimensionality-reduction machinery not yet built | **LATER** — scientifically the most ambitious and the most likely to be premature; needs the ingestion breadth of §3 largely closed first |
| 6 | **3. A neural transition forecaster** | Forecast the next clinically important transition (burst suppression, emergence, seizure) | Verifier layer 5 (temporal) — **NOT BUILT** (§2) — plus serial recordings per subject | **BLOCKED** — blocking reason: no temporal-verification layer exists and no dataset with dense serial per-subject EEG has been ingested (I-CARE's hourly segments are the best public candidate and are also not yet ingested) |
| 7 | **4. AI-discovered stimulation protocols / closed-loop control** | Learn state → response-to-perturbation → next safe intervention | Verifier layer 6 (mechanistic) — **NOT BUILT** — plus prospective or interventional data, which Brief 02 states public data cannot supply | **BLOCKED** — blocking reason: requires interventional/perturbational data this project does not have and mechanistic verification this engine does not yet perform; also the furthest from Brief 01's staged gates (Stage 4+, not reachable per `RESEARCH_STRATEGY.md` §6) |

---

## 5. The three discovery challenges

| challenge | measurable endpoint | datasets required | negative controls (must gate the verdict) | currently runnable? |
|---|---|---|---|---|
| **A** — simplest representation predicting loss/recovery of responsiveness across multiple anaesthetic drugs, minimising drug-identification information | AUROC for responsive-vs-unresponsive, stratified by drug; a drug-identity probe (layer 3) must NOT out-predict the responsiveness model | ≥ 2 anaesthetic-drug datasets (e.g. Chennu propofol + VitalDB's sevoflurane cases) | Drug-identity probe (built, §2 layer 3); site probe if multi-site | **NOT YET** — needs at least Chennu and VitalDB ingested; both are licence-clear or moderate-confidence for scientific use, neither is ingested |
| **B** — spontaneous EEG features associated with active command-following in DoC, controlling for CRS-R diagnosis and injury severity | Within-subject-null-gated detection rate of command-following, adjusted for CRS-R and severity | Bath (primary), Figshare (resting substrate) — but Figshare currently supplies *no* CRS-R/diagnosis to control for (§1 row 2) | Within-subject permutation null (`ANALYSIS_PLAN.md` §7, not yet implemented in `bsde/` code — no task-trial candidate exists yet); able-bodied positive control | **BLOCKED** — Bath access is request-only and not yet granted; even if granted, no task-trial/command-following candidate or within-subject-null layer exists in `src/bsde/` yet (only resting-state candidates are registered) |
| **C** — patient-specific trajectory feature predicting burst suppression or delayed emergence ahead of conventional monitors | Lead time over a conventional monitor signal (e.g. BIS) for a state transition | VitalDB (has BIS in a subset) or I-CARE (burst-suppression states) with serial per-patient EEG | Temporal-verification layer (§2 layer 5, **NOT BUILT**); a trivial "recent-value" baseline the trajectory feature must beat | **BLOCKED** — same blocker as breakthrough program 6 above: the temporal layer does not exist and neither candidate dataset is ingested |

**Plainly: none of the three discovery challenges is runnable today.** Challenge A is closest (data-access
and licence questions only); B is blocked on both external access (Bath) and missing code (task-trial
candidates, within-subject null); C is blocked on a verifier layer that has not been built.

---

## 6. Anti-p-hacking constraints, as implemented

| # | constraint (Brief 03) | mechanism in this repo, or NOT IMPLEMENTED |
|---|---|---|
| 1 | Keep immutable external test sets | **PARTIAL.** Patient-level splitting is designed into `ANALYSIS_PLAN.md` §4 and enforced structurally in the ingestion adapters (subject is required, never defaulted from recording id — `openneuro_s3.py`). No split-manifest file has actually been written to `results/splits/` yet because no labelled modelling run has happened. |
| 2 | Register primary hypotheses | **BUILT.** `Candidate.declaration_hash()` (`candidates/registry.py`) hashes interpretation, predictions, and failure conditions before any test runs; `governance/search_log.py` records that hash against every verdict. H1–H6 are fixed in `RESEARCH_STRATEGY.md` §3 before any dataset-level modelling. |
| 3 | Require replication across datasets | **BUILT (mechanism), UNEXERCISED.** `layer_cross_domain` implements leave-one-dataset-out; cannot yet run for real (§2, §3.2) for want of a second labelled dataset. |
| 4 | Separate exploration from confirmation | **BUILT.** `ANALYSIS_PLAN.md` explicitly labels confirmatory (H1–H6) vs. exploratory analyses, and E01/E02 are documented as label-free / exploratory by design. |
| 5 | Track every attempted analysis | **BUILT.** `governance/SEARCH_LOG.jsonl` — every candidate evaluated, including rejected ones, with the failing check named (VERIFIED by reading the two logged entries: `uce_v1` REJECT, `whole_head_exponent` INCOMPLETE). |
| 6 | Report the size of the search space | **BUILT.** `search_space_size` / `effective_search_space` are logged fields on every entry (`SEARCH_LOG.jsonl`); `Candidate.complexity` is a declared, hand-checked cost. |
| 7 | Penalize complexity | **BUILT.** `check_redundancy` explicitly compares complexity of a candidate against a simpler baseline before allowing a "real difference" verdict (`engine.py`); UCE v1 (complexity 4) was rejected in favour of `whole_head_exponent` (complexity 2) on exactly this basis. |
| 8 | Demand prospective prediction | **NOT IMPLEMENTED.** No prospective/temporal layer exists (§2 layer 5); nothing in this repo tests a prediction against data collected after the prediction was made. |
| 9 | Allow the system to return "nothing survived" | **BUILT.** `report.py`'s `decide()` has explicit `REJECT`/`INCOMPLETE`/`INDETERMINATE` outcomes distinct from `SURVIVE`, and this is not decorative — E02 already produced a real `REJECT` on the project's own flagship candidate. |
| 10 | Never let the AI rewrite the hypothesis after seeing the test result | **BUILT, structurally.** The declaration hash (constraint 2) makes any post-hoc rewrite of a candidate's claim produce a *new* hash with no prior results attached to it — a silent rewrite cannot inherit an old verdict. Enforcement still depends on a human (or the orchestrator) never re-registering a candidate under the same name with a quietly changed declaration; the tooling makes this *detectable*, not impossible. |

---

## 7. Agent architecture

Brief 03 specifies ten roles (research-director, literature, hypothesis, mathematical-discovery, data-curator,
experimentalist, engineering, skeptic, statistician, IP). This project does not run ten standing agents; it
maps the same separation of concerns onto the model-delegation SOP already governing this workspace
(`../CLAUDE.md`):

* **Opus (orchestrator)** absorbs the *research-director*, *hypothesis*, and final *IP*/*statistician*
  sign-off roles — deciding what gets tested, re-ranking priorities, and being the one who verifies every
  number before it is reported or committed. This is not delegable: judgement the whole result rests on stays
  with the orchestrator.
* **Sonnet** absorbs *literature*, *skeptic*, and *experimentalist* work — red-teaming a candidate's
  declaration, drafting the next falsification test, checking whether a citation is prior art. Judgement-
  needing but checkable afterwards against the raw source.
* **Haiku** absorbs *data-curator* and *engineering* mechanical work — running an ingestion adapter, computing
  a feature table, tabulating a license field from a fetched page. Cheap, and correct by inspection.

**Standing rule, adopted without qualification from Brief 03's closing line:** *"Agents should never be
allowed to approve their own findings."* Concretely in this project: every number that becomes a reported
claim, a ledger entry, or a commit is checked by the orchestrator **against the raw source** — the actual
`SEARCH_LOG.jsonl` entry, the actual test output, the actual licence page — never against a subagent's summary
of it. This document itself was produced under that rule: every dataset/licence/test claim above was checked
against `data_registry/*.csv`, `governance/SEARCH_LOG.jsonl`, `src/bsde/`, or a live `pytest` run, not
inherited from a prior agent's report without re-verification (see §8, item 1, for the one open exception).

---

## 8. Immediate next actions

1. **Verify the prior agent's inventory and Figshare-label findings against source before relying on them
   further.** Done for this document (registry CSVs, `SEARCH_LOG.jsonl`, `engine.py`, and a live test run were
   all re-read directly) — but the Figshare feature stream must be complete before its output is
   committed (`results/*.csv` is gitignored precisely so a half-written table cannot be committed looking
   whole). *Why now:* nothing downstream should build on a half-written
   CSV. *Unblocks:* a clean, complete label-free feature table for Figshare.
2. **Ingest I-CARE via `physionet_wfdb.py` (streamed, no download of the 1.5 TB whole).** *Why now:* it is the
   only Tier-1 dataset that is simultaneously (a) verified fully open, (b) already has a working adapter, and
   (c) supplies real outcome/severity variables that Figshare cannot. *Unblocks:* claim component 4 (§3.2),
   the first real cross-domain pair for layer 4, and the temporal layer's first candidate substrate (§2 layer
   5, §4 program 6).
3. **Ingest Sleep-EDF Expanded via the existing streaming path.** *Why now:* fully open (ODC-BY 1.0), small,
   and gives a second *labelled* dataset (sleep stage) immediately — the cheapest way to make leave-one-
   dataset-out (§2 layer 4) real instead of synthetic-only. *Unblocks:* an actual cross-domain verifier run,
   which has never happened on real data.
4. **File the Bath access request.** *Why now:* it is the only path to the command-following evidence tier
   (Challenge B, §5) and access review takes real calendar time independent of any engineering here — starting
   it does not compete with items 2–3. *Unblocks:* Challenge B eventually; nothing else does.
5. **Run the Colombo PMID 30639334 prior-art check through NCBI E-utilities (not WebFetch), and update
   `LITERATURE_MAP.md`.** *Why now:* §1 row 4 currently rests on a citation that was not independently re-
   verified this session — the sibling project's error-catalogue rule 25 exists because WebFetch fabricates
   PubMed content under CAPTCHA. *Unblocks:* a defensible IP posture for anything claimed as "discovered" here.
