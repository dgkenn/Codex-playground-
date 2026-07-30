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
already crowded. The proprietary asset is the verifier — Brief 03's point being that "EEG does not have a perfect equivalent of a Lean proof
checker" and that building one is the opportunity,
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
| 3 | I-CARE is listed as a plain Tier-1/MVP-stack PhysioNet resource ("approximately 23.7 GB") alongside openly reusable datasets, with no field-of-use caveat, feeding into Brief 03's proprietary "harmonized multi-domain data architecture" asset | Brief 02, dataset #4; Brief 03 "proprietary layers" list | I-CARE's licence is **CC BY-NC-SA 4.0 — commercially blocked** (VERIFIED against the PhysioNet view-license page). Actual size is **1.5 TB uncompressed, not 23.7 GB** (VERIFIED against the PhysioNet content page — the brief's figure is low by a factor of roughly 63 and the dataset cannot be fully downloaded in this environment, 19 GB free). Whether a model *trained on* I-CARE features counts as ShareAlike "Adapted Material" is an open question this project has explicitly deferred to counsel, not resolved. | I-CARE is used exactly as Brief 02 itself later cautions (§ "critical conceptual warning") — external validation, domain shift, confounder resistance, **never** a trained artefact offered commercially — and this project's governance record (`LICENSE_TABLE_NOTES.md` §2–3) treats it, `vitaldb`, and every dataset with an unverified licence as **blocked by default** for any commercial claim until a lawyer signs off. Brief 03's "proprietary data architecture" cannot include I-CARE-derived weights as a shippable asset under current terms. |
| 4 | The aperiodic/1/f exponent and UCE built from it are presented as the investigator's own construct and a candidate piece of novel IP (Brief 01 §4; Brief 03's "discovered representations" as a proprietary layer) | Brief 01 §4; Brief 03 "proprietary advantage" | **Colombo et al., PMID 30639334, is prior art** (VERIFIED — `LITERATURE_MAP.md` §0 records an NCBI E-utilities retrieval of this record on 2026-07-29 with the abstract read in full; that file uses E-utilities rather than WebFetch precisely because WebFetch has fabricated PubMed content in this project before) for the resting-state spectral (aperiodic) exponent as a marker of the *presence* of consciousness, tested across propofol/xenon/ketamine, n=5/group. | UCE's scientific contribution is **validation at scale of an existing marker**, not discovery of a new one. Any IP claim (`governance/INVENTION_NOTEBOOK.md`) must be built on what is actually novel here — the verifier architecture, the redundancy/confound-probe machinery, any genuinely new invariant the engine discovers later — not on "aperiodic exponent predicts unconsciousness," which Colombo anticipates. This is exactly the kind of prior-art check Brief 01 §11 asks for and it must land in `LITERATURE_MAP.md`, not only here. |
| 5 | BNCI/BCI-Competition-IV 2a/2b are listed as freely reusable method-development datasets (Brief 02, Tier 4, item 13) with no licence caveat | Brief 02, dataset #13 | Licence is **CC BY-ND 4.0** (VERIFIED, `LICENSE_TABLE.csv`) — explicitly "You do not have permission... to Share Adapted Material." A trained decoder or feature representation built on 2a/2b could plausibly count as Adapted Material. | Usable for internal method development (decoder benchmarking, false-positive calibration) exactly as Brief 02 intends, but **no derived model, weight set, or representation trained on 2a/2b may be published or shipped** without a legal read of the No-Derivatives clause — flagged in `LICENSE_TABLE.csv` row `bnci_bciciv_2a2b`, not yet resolved. |
| 6 | ds005620 supports the contrast "unresponsive sedation **with** later reported experience" vs "**without**" — Brief 02 calls it the dataset that "helps break a major conceptual error" | Brief 02 dataset #6 | **The experience reports are not in the public deposit.** Verified 2026-07-29 by enumerating the COMPLETE S3 key list: the only tabular files are `channels.tsv` (202), `events.tsv` (202), `scans.tsv` (21) and `participants.tsv` (1). `participants.json` documents every column — `age, sex, awakenings, TMS, tms_count, excluded, bad_after_preprocessing` — and `awakenings` is *"Number of times the participant was awakened during sedation"*, a count, **not** a report of whether anything was experienced. `events.tsv` holds only BrainVision `New Segment` boilerplate. Zero files match dream/experience/report/beh/questionnaire/rating/subjective. | **Claim component 3 becomes untestable on reachable public data** (§3.2, §9.5). ds005620 stays worth ingesting for what it verifiably carries — 21 subjects, 202 recordings, within-subject `awake`/`sed`/`sed2`, and **55 TMS recordings** — but must never be described as testing experience under unresponsiveness, and `awakenings` must never be used as an experience label. It is also **BrainVision, not EDF**. |

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
| 5 | OpenNeuro ds005620 (propofol/dreaming) | Experience despite unresponsiveness | **streamable, but NOT via the existing adapter** — licence VERIFIED **CC-BY-4.0** (`README.txt`, not CC0). Format VERIFIED **BrainVision** (`.vhdr`/`.vmrk`/`.eeg`), so `ingestion/openneuro_s3.py`, which delegates to `read_edf_window_http`, **cannot read it**; a BrainVision-over-HTTP adapter is required. Complete S3 key enumeration: 21 subjects, 202 recordings, tasks `awake`/`sed`/`sed2`, acq `EC`/`EO`/`rest`/`tms`, **55 TMS recordings**. **The experience reports are NOT in the deposit** (§1 row 6, §9.5) |
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
| 3. Representation ≠ arousal | ~~ds005620 experience reports~~ **NOT IN THE DEPOSIT** (§1 row 6); Chennu mild-vs-moderate; MCS-vs-UWS and locked-in (Figshare labels do not exist); eyes-open/closed | **UNTESTABLE ON REACHABLE PUBLIC DATA.** Verified 2026-07-29: no public dataset supplies the experience-under-unresponsiveness dissociation. What remains — graded sedation depth, REM-vs-NREM — confounds arousal with experience rather than separating them. Every `unconscious_vs_awake` result therefore stays **compatible with H4**. See §9.5. |
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
   (c) supplies real outcome/severity variables that Figshare cannot. *Unblocks:* a **discriminant-validity
   control** for claim component 4 — **not** confirmation of it, see §9.1 —
   the first real cross-domain pair for layer 4, and the temporal layer's first candidate substrate (§2 layer
   5, §4 program 6).
3. **Ingest Sleep-EDF Expanded via the existing streaming path.** *Why now:* fully open (ODC-BY 1.0), small,
   and gives a second *labelled* dataset (sleep stage) immediately — the cheapest way to make leave-one-
   dataset-out (§2 layer 4) real instead of synthetic-only. *Unblocks:* an actual cross-domain verifier run,
   which has never happened on real data.
4. **File the Bath access request.** *Why now:* it is the only path to the command-following evidence tier
   (Challenge B, §5) and access review takes real calendar time independent of any engineering here — starting
   it does not compete with items 2–3. *Unblocks:* Challenge B eventually; nothing else does.
5. ~~Run the Colombo PMID 30639334 prior-art check through NCBI E-utilities.~~ **ALREADY DONE** —
   `LITERATURE_MAP.md` §0 records the E-utilities retrieval on 2026-07-29 with the abstract read in full. An
   earlier draft of this document listed it as outstanding; that was wrong, and §1 row 4 is corrected.
   *Kept as a live warning rather than deleted:* the reason that file uses E-utilities at all is that WebFetch
   fabricated PubMed content in the sibling project (error-catalogue rule 25) — **and it did so again during
   the work that produced this document**, inventing "435 files" and "91 subject datasets" for the Figshare
   record. That was caught only because the same URL was re-pulled with `curl` and compared byte-for-byte.
   Never accept a WebFetch summary of a bibliographic or manifest record.
6. **Wire `brier()` and `calibration()` into `layer_statistical`.** They exist in `verifier/stats.py` and are
   called from nowhere. Discrimination without calibration is half a result, and the missing half is the half
   clinicians use.

---

## 9. Known reasoning risks in this plan

*Recorded, not repaired. Each was found by adversarial review of an earlier draft of this document; §9.1 and
§9.2 were missed by the orchestrator and caught by an independent reviewer. They are written here rather than
quietly fixed because a risk that has been silently patched cannot be re-examined.*

### 9.1 I-CARE cannot confirm claim component 4 — it can only fail to refute it

An earlier draft of §8 said ingesting I-CARE "unblocks claim component 4" (*the representation is not merely
prognosis or injury severity*). That is backwards. **I-CARE's only ground truth is CPC outcome, which is
prognosis.** Brief 02 says so itself: *"I-CARE does not provide direct evidence of contemporaneous awareness.
CPC outcome is prognostic, not a consciousness label. Do not train a 'consciousness classifier' using
good-versus-poor CPC."* A dataset whose sole label is prognosis cannot supply evidence that a marker is
something other than prognosis.

Its correct role there is **discriminant validity — a negative control.** If a candidate predicts CPC as well
as it predicts consciousness-relevant contrasts elsewhere, that is evidence **against** the candidate. A
strong CPC result in I-CARE is neutral-to-negative for claim component 4, never progress on it.

The failure mode is specific and it flatters the result, which is what makes it dangerous: I-CARE gets
ingested, a candidate discriminates CPC well, and it gets logged as progress on the very claim it undercuts.
I-CARE's genuine contributions are elsewhere and are substantial — site probes, drug probes, severity probes,
longitudinal recovery physiology, domain transfer, abstention behaviour.

### 9.2 Gate B adjusts for arousal as a confound — but arousal may be a mediator

The project's termination criterion (`RESEARCH_STRATEGY.md` §7; `ANALYSIS_PLAN.md` §11) is: if every candidate
is indistinguishable from an arousal marker after adjustment for arousal, stop and report negative. That
treats "survives adjustment for arousal" as a clean test of whether a marker is more than arousal.

**It may not be one.** If preserved capacity can only manifest *through* arousal — a patient must be aroused
enough to express anything at all — then arousal lies on the causal pathway, and adjusting for it removes real
signal rather than removing a confound. This is exactly the limitation already documented in
`verifier/engine.py::residual_auc` for the EMG case — *"if the nuisance is itself part of the state being
measured … then residualising removes real signal and this check will fire on a valid marker"* — now applied
to the single nuisance the entire termination criterion rests on.

The consequence is a false negative produced by the safeguard against false positives: a genuine capacity
marker fails Gate B for structural reasons and triggers a pre-committed "stop and report negative". The
criterion was deliberately written down so that it *could not be renegotiated after seeing a result*, which is
correct discipline and also means an unexamined flaw here is hard to correct once it fires.

**Mitigation, not resolution.** Any Gate B NO-GO must be reported together with (a) the unadjusted estimate,
and (b) an explicit statement that an arousal-*mediated* capacity marker produces the same result as a pure
arousal marker under this test. It may not be described as "the marker is only arousal" without that
sentence. No statistical adjustment settles this; only a design that dissociates arousal from experience
does — which is precisely why ds005620 is action #1.

### 9.3 `unconscious_vs_awake` merges the two states H4 predicts behave alike

`candidates/seed.py::CONTRASTS` defines `unconscious_vs_awake` as *"anaesthetic LOC, or sleep N3 vs wake"*.
Sleep N3 and anaesthetic unresponsiveness are precisely the two states the arousal hypothesis (H4) predicts
should move together. A `layer_cross_domain` PASS spanning only sleep and anaesthesia is therefore **neutral
between H4 and the capacity hypothesis** — it is what a pure arousal index produces — yet the engine reports a
bare PASS with no annotation saying so.

A warning to this effect now sits at the contrast definition in the code. The informative domains are the ones
that dissociate arousal from experience: ds005620 (unresponsive with vs without reported experience),
ketamine, locked-in syndrome. **"Cross-domain validated" must never be written of a sleep-plus-anaesthesia
PASS.** This also downgrades Sleep-EDF from "the cheapest way to make leave-one-dataset-out real" to "a cheap
way to exercise the machinery, informative about robustness and uninformative about the central question".

### 9.4 The redundancy finding's denominator travels with it

E02's |ρ| = 0.9896 is load-bearing: it retires "96.8 % of variance explained", redescribes UCE v1
project-wide, and demotes it from discovery to validation. It was produced against a **hand-picked
eight-candidate seed set with `analytic_dof = 1`** — fit range, reference and window length all held fixed.

Two things are true at once and both belong next to the number. It is **not** a search hit:
`RESEARCH_STRATEGY.md` §0 predicted it algebraically *before any data existed*, so the multiplicity concern
that applies to a discovery does not apply here in the usual way. And the denominator must still travel with
the claim wherever it appears, because anti-p-hacking constraint #6 (§6) admits no exceptions — and because a
reader cannot verify the first point without being handed the second.

### 9.5 The decisive claim has no public dataset — three deposits in a row withheld their labels

Claim component 3 (*the representation is not merely arousal*) is what the whole project turns on: H4 is the
default hypothesis (§1 row 1) and only a design that dissociates arousal from experience can displace it
(§9.2). As of 2026-07-29 **no reachable public dataset supplies that dissociation.** The pattern is now
threefold and worth naming, because it will recur:

| Dataset | What the brief expected | What the public deposit actually contains |
|---|---|---|
| Figshare DoC resting | 59 patients + 32 controls with diagnostic categories | EEG only. No labels of any kind (§1 row 2). |
| ds005620 | unresponsive **with** vs **without** reported experience | EEG, task/acq codes, and `awakenings` **counts**. No experience reports (§1 row 6). |
| Bath PDoC MI-BCI | session-linked CRS-R and WHIM alongside task EEG | unknown — **access-restricted**, so unverifiable until granted (§1 row 5) |

**The generalisable lesson: a deposit's EEG and a deposit's labels have different release politics, and the
paper describing a dataset is not evidence about what was deposited.** Signals are cheap to share and carry
little re-identification risk; behavioural, diagnostic and subjective-report variables are the sensitive,
effort-intensive, and often withheld part. Every dataset row in `DATASET_REGISTRY.csv` must therefore record
`labels_available` as an independently **verified** field, never inferred from the associated publication —
and the verification must enumerate the deposit's actual file list, because a missing labels file looks
exactly like a labels file you have not found yet.

**What this does *not* license.** It does not license using a weaker variable as a stand-in and describing it
as the strong one. Specifically: `awakenings` is a count of arousals, not evidence of experience;
sleep-stage labels confound arousal with experience rather than separating them; and CPC outcome is prognosis
(§9.1). If claim component 3 cannot be tested, the correct report is **"untested"**, not a proxy result.

**What it changes operationally.** Testing claim component 3 now requires either (a) the Bath deposit turning
out to contain contemporaneous behavioural data, (b) direct contact with the ds005620 or Chennu investigators
for the withheld behavioural variables, or (c) prospective acquisition — Brief 02's own Paper 3. Options (b)
and (c) are the honest routes and both are calendar time, not engineering. Until one lands, every candidate's
`unconscious_vs_awake` result is **compatible with H4 and must be reported that way.**

### 9.6 Sleep-stage labels are scored FROM the EEG, so predicting them is substantially circular

E03's first real run produced an AUC of **0.992 [0.978, 1.000]** for the whole-head aperiodic exponent
discriminating Wake from N3 on Sleep-EDF, with a centred permutation null and good calibration (Brier skill
+0.954, slope 0.953). The engine's `label_leakage` check fired, because a single resting-EEG scalar separating
an outcome that nearly perfectly is not a plausible physiological result.

**The check was right and its stated reason was wrong.** This is not data leakage. It is that **sleep stages
are scored by human raters reading the EEG**, and N3 is *defined* by the proportion of slow-wave activity in
the epoch. The label is a deterministic-ish function of the very signal the candidate is computed from. So a
steep aperiodic exponent predicting N3 is close to tautological: both are ways of saying "this epoch is
dominated by slow activity".

**Consequence for the whole sleep tier of Brief 02 (datasets 9, 10, 11 — Sleep-EDF, SHHS, MESA).** Sleep data
cannot show that a marker *detects unconsciousness*. It can show only that the marker **recovers the scoring
criteria**, which is a statement about agreement with a rating rule, not about brain state. That is still
worth something — it is a real measurement-validity check, and a marker that *failed* it would be suspect —
but it is a much weaker claim than the dataset's presence in a "levels of consciousness" project implies, and
Brief 02's own caution that "sleep stages are not levels of consciousness" turns out to understate the
problem: the issue is not just that the mapping is imperfect, it is that the label is derived from the
predictor's own input.

**How this is handled going forward, decided now rather than after seeing more results.** Any sleep-based
result is reported as *criterion recovery*, never as detection, and never counted toward claim component 3.
The `label_leakage` check keeps its FAIL here — the number genuinely should not be believed as a detection
result — and its reason text should be broadened to name definitional circularity alongside data leakage,
since they are distinguishable in cause and identical in consequence.

**What it does not undermine.** The same candidate's ds005620 result — AUC 0.646 [0.544, 0.750] for awake vs
propofol sedation, null centred at 0.4871, interval excluding 0.5 — is *not* circular, because responsiveness
there was determined by the experimental protocol rather than read off the EEG. That is the more honest of the
two numbers, and it is far smaller.

### 9.7 E04: the minute before waking looks DEEPER, not lighter — and two of my own predictions were mis-built

**The result.** On ds005620, with acquisition matched (`acq-rest` on both sides), 34–35 recordings per class
across 15 subjects, and a centred within-subject permutation null for every candidate: **all seven candidates
that separate `sed2` from `sed` at all say the pre-awakening minute is MORE sedated, not less.**

**FINAL, on the complete 202-recording table** (105 rows in the primary contrast, 20 subjects). The
interim numbers below it came from a 133-row partial table and were slightly optimistic, which is the
expected direction when adding data.

| candidate | AUC scored as "sed2 lower" | reading | interim (partial) |
|---|---|---|---|
| whole_head_exponent | **0.385 [0.279, 0.476]** | sed2 exponent **higher** → deeper | 0.367 |
| uce_v1 | **0.376 [0.271, 0.469]** | deeper | 0.354 |
| relative_delta_power | **0.405 [0.327, 0.471]** | sed2 delta **higher** → deeper | 0.380 |
| spectral_entropy | **0.585 [0.505, 0.673]** | sed2 entropy **lower** → deeper | 0.616 |
| lempel_ziv | **0.592 [0.507, 0.684]** | sed2 complexity **lower** → deeper | 0.609 |
| spectral_edge_95 | 0.565 [0.489, 0.655] | *interval now spans 0.5* | 0.602 |
| relative_alpha_power | 0.562 [0.487, 0.642] | *interval now spans 0.5* | 0.583 |
| wpli_alpha | 0.427 [0.313, 0.536] | *interval now spans 0.5* | 0.373 |

**Five of eight retain intervals excluding 0.5 on the full data, and all five point the same way. Three
became non-significant. NONE reversed to indicate lightening.** The unanimity is what carries the result:
zero candidates out of eight support a pre-awakening lightening, at any effect size.

Seven measures, four of them moving in numerically opposite directions, all agreeing on the physiology. That
unanimity is what makes this a result rather than noise.

**This refutes the transition-precursor hypothesis on this dataset.** E04 registered the falsification
condition in advance and it is met in the strongest available form: not "no signal", but a *consistent signal
in the wrong direction*. There is no detectable lightening in the minute before an awakening at 20 s
resolution in these features.

The reading I registered in advance now applies: awakenings were not randomly timed. The most economical
explanation is that the awakening **stimulus** is what lightens the subject, so the minute preceding it
carries no precursor at all — and that minute may systematically sit at the end of a stable deep-sedation
period. For Brief 03's Program 3 and Discovery Challenge C this is informative and discouraging: it says a
forecastable emergence precursor is not present in this protocol, and that a dataset where awakening is
externally triggered may be structurally incapable of showing one. Spontaneous emergence data would be needed.

**Two flaws in my own predictions, stated rather than rescored.**

*P2 was mis-operationalised.* It reads "`sed2` shows a LOWER aperiodic exponent" — a claim about one measure —
but the code scored **every** candidate as "lower". For complexity measures, lower means *more* sedated, so
scoring them that way tests the opposite of what P2 asserts. The printed "P2 MET for lempel_ziv,
spectral_edge_95, spectral_entropy" is therefore misleading: those three moving "lower" supports the *reverse*
of P2's claim. The substantive finding is unanimous; the scoring conflated two hypotheses under one sign
convention. **The recorded verdict stands as printed and is not retroactively re-scored** — the fix belongs in
a future experiment's design, and a direction must be declared per measure, not per experiment.

*P3 is undefined when the reference effect is absent.* P3 compares |primary − 0.5| against |reference − 0.5|.
For `relative_alpha_power` (ref 0.510), `spectral_entropy` (0.469) and `wpli_alpha` (0.490) the reference is
indistinguishable from chance, so any primary effect exceeds it trivially. P3's NOT MET is driven entirely by
those three. It is **not** evidence that "the labelling or windowing is doing the work"; it is a test that
should have been gated on the reference being non-null in the first place.

**Rule 17 fired on me.** I predicted that restricting the awake class to `acq-EC` — dropping eyes-open and TMS
— would *reduce* the ds005620 awake-vs-sedated AUC, since eyes-open inflates apparent separation. It went
from 0.646 to **0.947 [0.885, 0.987]** on the complete table (0.934 on the partial). The pooled acquisitions
were *diluting* the effect through
heterogeneity, not inflating it. Error-catalogue rule 17 says that when a fix makes the effect stronger the
diagnosis was wrong, and it was: I had the mechanism backwards. The 0.934 is the acquisition-matched number
and supersedes the 0.646 I reported earlier — while remaining an upper bound, because awake was never
recorded at `acq-rest` and that residual mismatch cannot be removed (§9.7 predecessor, commit 4378270).

### 9.8 Chennu is the best labelled dataset the project has, and it contains a drug-vs-state dissociation

**Accessed 2026-07-30 with no authentication and no download.** The deposit's 3.69 GB zip
(`api.repository.cam.ac.uk/server/api/core/bitstreams/e94a6722-.../content`, reached through a 302 from the
`www` host) serves HTTP range requests. Reading the End-of-Central-Directory record from the tail and then the
central directory gives a full index — 166 members, **80 `.set` + 80 `.fdt` EEGLAB pairs** (20 subjects × 4
conditions) plus `datainfo.mat` — after transferring about 85 kB of a 3.69 GB archive. `datainfo.mat` was
inflated in memory and parsed. Nothing was written to disk and no credential was used.

**`datainfo.mat` carries four labels, and the deposit documents all five columns explicitly:** dataset name;
sedation level (1 baseline, 2 mild, 3 moderate, 4 recovery); **propofol concentration MEASURED IN BLOOD
PLASMA** (µg/L); mean reaction time in a speeded two-choice task (ms); and correct responses out of 40.

**None of these is scored from the EEG.** That is the property Sleep-EDF lacks (§9.6) and it makes Chennu the
first dataset here with a labelled, non-circular, within-subject contrast *and* complete labels actually
present in the deposit — the third dataset checked and the first to pass (§9.5).

| level | n | plasma median (µg/L) | RT median (ms) | correct median /40 |
|---|---|---|---|---|
| 1 baseline | 20 | 0.0 | 996.0 | 39.0 |
| 2 mild | 20 | 438.0 | 893.5 | 37.5 |
| 3 moderate | 20 | 803.0 | *missing* | 35.0 |
| 4 recovery | 20 | **276.5** | 819.0 | 38.0 |

**THE DESIGN THIS UNLOCKS — a within-subject dissociation of drug level from behavioural state.** At
*recovery*, plasma propofol is **276.5 µg/L — not zero, and above baseline** — while behaviour is almost fully
restored (38/40 against baseline's 39/40). So level 4 has *drug present with responsiveness recovered*, in the
same subjects. A candidate can therefore be asked which of the two it follows:

* if its recovery value resembles **baseline**, it tracks behavioural state;
* if its recovery value resembles **mild sedation** (the comparable plasma level), it tracks the drug.

That is Discovery Challenge A — "predicts loss and recovery of responsiveness across anaesthetics while
minimising drug-identification information" — in its testable form, and it is runnable now on 20 subjects.
It also directly attacks §9.2's mediator problem: drug level and behaviour are here measured *separately*, so
arousal need not be adjusted away blindly.

**Three caveats found in the label table itself, before any analysis.**

1. **Reaction time is contaminated by practice order.** RT *falls* monotonically across the session
   (996 → 893 → 819 ms) including from baseline to mild sedation, which is the wrong direction for a
   sedative. Level order is fixed (baseline → mild → moderate → recovery), so RT carries a learning effect
   confounded with drug exposure. **RT must not be used as a responsiveness measure without accounting for
   order**, and correct-response count (39 → 37.5 → 35 → 38) is the better behavioural label because it moves
   in the expected direction and returns at recovery.
2. **Reaction time is missing at moderate sedation.** That missingness is almost certainly outcome-related —
   a subject too sedated to respond produces no RT — so it must be reported as informative, not imputed
   (`ANALYSIS_PLAN.md` §9).
3. **Recovery is not a drug-free state.** Calling level 4 "recovery" invites treating it as a second
   baseline. Its plasma concentration says otherwise, and that is precisely what makes it useful.

**Consequence for the plan.** Brief 02 rates Chennu a "controlled pharmacologic perturbation dataset", which
undersells it: the measured plasma concentrations and behavioural scores make it the only reachable dataset
that can separate drug from state. It moves to the top of the ingestion queue, and the `.set`/`.fdt` remote-zip
adapter needed to read it is worth building for that reason alone.

### 9.9 E05: the drug-vs-state question is undetermined at n=20 — but the aperiodic exponent does not track dose

**The primary result is a registered negative.** Of eight candidates, seven have subject-level S intervals
spanning 0, so the design does not determine whether they follow drug or state at n = 20. Only
`relative_delta_power` is determined — **S = −0.280 [−0.515, −0.039], following the DRUG**, with its placebo
gate passing (−0.078 ≥ −0.280) and its permutation null centred at +0.004. That is the honest outcome E05
registered as its falsification condition: this design cannot separate drug from state at this n for almost
everything tested, and Discovery Challenge A is not answered by public data.

**P4 failed for both exponent candidates, so their primaries are WITHHELD, not reported.** For
`whole_head_exponent` the placebo S (recovery vs *moderate*) came in marginally below the primary S (recovery
vs *mild*), which is the condition under which the plasma ordering cannot be said to drive the statistic. The
gate ran before the primary was interpreted (rules 34, 37) and the primary was suppressed. `uce_v1` failed the
same way. This is the placebo gate doing precisely the job it was built for, on the project's own flagship.

**THE INCIDENTAL FINDING IS MORE IMPORTANT THAN THE PRIMARY.** P2 asked whether each candidate rises
monotonically with *measured plasma propofol* across baseline → mild → moderate, within subject:

| candidate | subjects monotone in plasma |
|---|---|
| **lempel_ziv** | **90 %** |
| **spectral_entropy** | **80 %** |
| spectral_edge_95 | 65 % |
| uce_v1 | 50 % |
| relative_alpha_power | 45 % |
| **whole_head_exponent** | **45 %** |
| relative_delta_power | 40 % |
| wpli_alpha | 30 % |

**The aperiodic exponent is monotone in plasma concentration in 45 % of subjects — below chance — while
Lempel-Ziv reaches 90 % and spectral entropy 80 %.** P2 was registered as *gating* P3's interpretability, and
it failed, so P3 is not interpretable for the exponent by the experiment's own pre-committed logic.

This is the first evidence in this project that **the complexity measures track a drug's dose better than the
aperiodic exponent does**, and it runs against the premise the whole programme inherited from Brief 01. It is
also not contradicted by ds005620's AUC 0.947 for awake-vs-sedated (§9.7): separating two well-separated states
and ordering three dose levels within a subject are different questions, and a marker can do the first while
failing the second.

**Two alternative explanations that must be tested before the finding is believed.**

1. **Preprocessing.** The Chennu deposit is filtered **0.5–45 Hz** and average-referenced. The project's
   aperiodic fit runs 1–40 Hz, whose upper edge sits inside the filter's roll-off, and average referencing
   changes the exponent. A slope estimated across a filter shoulder can be distorted in a dose-independent
   way that destroys monotonicity without saying anything about physiology. **This is exactly what
   `preprocessing_sensitivity` — the required report item that nothing currently computes (§2, layer 3) —
   exists to settle, and it is now the highest-priority unbuilt check.**
2. **Three points is a fragile monotonicity test.** With three levels there are only 6 orderings, so chance
   agreement is not 50 % in the naive sense and the comparison against "chance" above is loose. The ranking
   *between* candidates is the defensible part; the absolute percentages are not.

Until (1) is settled, the correct statement is: **on this deposit, as preprocessed, the aperiodic exponent does
not order propofol dose within subject, and two complexity measures do.** Whether that is a fact about the
marker or about the filtering is unresolved.

### 9.10 Correction: UCE v1 IS computable on Chennu — I fabricated the channel list

I reported that Chennu's montage is EGI-numbered (E2…E92), that UCE v1's frontal/posterior grouping therefore
matches zero channels, and that this made a **third** montage on which the frozen construct cannot be computed.
**That was wrong.**

Chennu's 91 channels are a **hybrid**: mostly EGI numbering, but with the 10-20 landmark positions labelled
conventionally — `Fp1, Fp2, Fz, F3, F4, F7, F8, C3, C4, Cz, T3, T4, T5, T6, P3, P4, Pz, O1, O2, Oz`. UCE v1
matches **7 frontal and 8 posterior** channels and computed successfully on all 80 recordings.

**How the error happened, because the mechanism matters more than the fact.** I read the first five channel
names from a real load (`E2 … E6`), generalised "all EGI" from that prefix, and then *verified* the claim by
running `group_indices` against a channel list **I had generated myself** — `['E'+str(i) for i in range(2,93)]`
— rather than against the names the data actually carries. The check confirmed my assumption because it was
executed on my assumption. A synthetic stand-in for real metadata is not a verification of anything, and it is
indistinguishable from a real check in the transcript.

The engine caught it immediately and without being asked: the stream reported `uce_v1 non-empty: 80` where I
had predicted 0, which is why the error survived for one commit rather than entering the record.

**What stands after the correction.** Sleep-EDF's 2-channel montage remains the only case so far where UCE v1
is genuinely not computable, so the montage-fragility claim is *weaker* than I stated — one montage, not three.
Its redundancy with the whole-head exponent (§1 row 1) is unaffected, since that rests on E01/E02.

### 9.11 E06: one channel is nearly as good as 91 — and the frontal gradient makes EMG a live explanation

**The direct answer to "how few channels?" — all four predictions met.** Monotonicity with measured plasma
propofol, within subject, across 91 electrodes swept individually:

| candidate | all 91 | 10-20 subset (19) | **median single** | single range |
|---|---|---|---|---|
| **lempel_ziv** | 0.900 | 0.900 | **0.800** | [0.35, 1.00] |
| spectral_entropy | 0.800 | 0.800 | 0.700 | [0.40, 1.00] |
| spectral_edge_95 | 0.650 | 0.550 | 0.650 | [0.20, 0.90] |
| whole_head_exponent | 0.450 | 0.550 | 0.400 | [0.05, 0.80] |
| relative_alpha_power | 0.450 | 0.400 | 0.400 | [0.15, 0.70] |
| relative_delta_power | 0.400 | 0.400 | 0.250 | [0.00, 0.80] |
| uce_v1 | 0.500 | 0.500 | **NOT COMPUTABLE** | — |
| wpli_alpha | 0.300 | 0.400 | **NOT COMPUTABLE** | — |

**Channel count barely matters.** For Lempel-Ziv the 19-channel 10-20 subset scores *identically* to all 91
(0.900), and the median single electrode retains 0.800 — about 89 % of the full montage. `spectral_edge_95`'s
median single equals its all-channel value exactly. **None of these measures is exploiting spatial structure**,
which is a deflating result for any construct whose premise is spatial organisation, and an encouraging one for
deployment on a frontal strip or a wearable.

Two candidates are *structurally* impossible on one channel and the pipeline says so rather than substituting:
wPLI needs a pair, and UCE v1 needs an electrode that is simultaneously frontal and posterior. That check
exists because §9.10 records me making exactly that substitution error by hand.

**The best single electrode reached 1.00 — perfect monotonicity in all 20 subjects — and it is reported as an
anecdote, not a result.** Four electrodes (E15, E16, E23, E26) hit 1.00. Quoting any of them as "a
single-channel biomarker with 100 % consistency" would be a search over 91 with a denominator of 1. The median
is the result.

**THE FINDING THAT MATTERS MORE THAN THE HEADLINE — a frontal gradient.** Breaking the 91 single-channel
scores down by scalp position for `lempel_ziv`:

| region | n | median | range |
|---|---|---|---|
| frontal 10-20 | 7 | **0.950** | [0.80, 0.95] |
| EGI-numbered (mixed) | 71 | 0.800 | [0.35, 1.00] |
| posterior 10-20 | 8 | **0.700** | [0.45, 0.85] |
| central 10-20 | 5 | 0.632 | [0.50, 0.85] |

Every frontal electrode sits at or above the overall median; the four perfect electrodes are all
low-numbered, i.e. anterior in an EGI net. P4 passed only at its boundary (+0.15 exactly), and **the direction
of the miss is the one P4 was written to detect.**

**This gives E05's headline a mundane alternative explanation that the project cannot currently rule out.**
E05 found Lempel-Ziv ordering propofol dose in 90 % of subjects while the aperiodic exponent managed 45 %.
Facial and scalp muscle is frontally dominant; EMG adds broadband high-frequency content, which *raises*
binarised complexity; and propofol *relaxes muscle*. So "frontally-dominant broadband complexity falls with
increasing propofol dose" is exactly what progressive facial-muscle relaxation would produce, with no cortical
content whatsoever.

Real physiology predicts frontal dominance too — propofol's frontal alpha and anterior-dominant slowing are
well established — so the gradient does not settle it either way. What settles it is a measurement the project
does not yet make.

**CORRECTION, 2026-07-30 — my caveat about the retained band was too strong.** I wrote that the Chennu
deposit's 0.5–45 Hz filter had "already removed" the high-frequency evidence needed to settle the muscle
question. Building the EMG index and testing it against planted muscle showed otherwise, and the test that
found it was written to fail loudly if the caveat was wrong:

* With the project's own synthetic EMG — **flat 20–90 Hz noise** — a 45 Hz low-pass barely reduces
  detectability at all (separation 0.923 filtered against 0.914 unfiltered). About 36 % of flat 20–90 Hz power
  lies in 20–45 Hz, and that residue is still overwhelming at large amplitudes.
* With **realistically peaked EMG** (a broad hump at ~70 Hz, where surface motor-unit activity actually lives),
  the same low-pass *does* substantially reduce detectability.

So the calibrated statement is: **muscle contributes to 20–45 Hz as well as above it, so the retained band is
not devoid of muscle information — but how much sensitivity survives depends on the true EMG spectrum, which
cannot be observed in a deposit that removed it.** A null EMG result on Chennu is therefore **weak evidence of
no muscle, not no evidence**. That is a materially different claim from the one I made, and it makes the proxy
more useful than I said, not less.

**`ANALYSIS_PLAN.md` §3 already anticipated this and named the remedy**: *"EMG index is a predictor of
interest, not only a nuisance. If it predicts the outcome as well as the aperiodic exponent does, the exponent
result is an EMG result."* **No EMG index is implemented.** It now joins `preprocessing_sensitivity` (§9.9) as
a required-but-absent check, and between the two it is the more urgent, because it bears on the one positive
finding this project has rather than on a negative one.

**Standing consequence.** Until an EMG index exists, the E05/E06 complexity finding is reported as
*"frontally-dominant broadband complexity tracks propofol dose, with muscle relaxation unexcluded"* — never as
a cortical-complexity result.

**Scope, restated because it bounds the deployment claim.** The deposit is average-referenced, and average
referencing is a spatial operation that mixes all 91 channels into every one of them. A "single channel" here
is one channel *of an average-referenced montage*, so these are an **upper bound** on true single-electrode
performance. Answering the deployment question properly needs a raw or single-referenced deposit.
