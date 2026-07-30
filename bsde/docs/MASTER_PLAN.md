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

> **STALE AS OF 2026-07-30 — see §9.22 for the verified current status.** Layers 5 and 7 are now
> BUILT and wired into `verify()`; layer 2's calibration primitives now run end-to-end; layer 4 is now
> exercisable on three labelled deposits. The table below is kept for the reasoning it records, not for
> its status column.

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

> **PARTLY STALE — see §9.22.** Challenge C's blocker was the temporal layer, which now exists; C is now
> blocked on DATA alone. Challenge A's blocker is sharper than the table says: two anaesthetic deposits
> are now ingested and BOTH ARE PROPOFOL, so the across-drugs requirement is still unmet.

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

### 9.12 E07: the Lempel-Ziv result is not muscle and not alpha — but it is in the WRONG DIRECTION, which I failed to check for three experiments

**P1 gate FAILED, so E07 issues no confirmatory verdict.** The composite `emg_index` is monotone in plasma in
only 35 % of subjects, below the 50 % the gate required, so by E07's own pre-committed logic it cannot
adjudicate. Everything below is therefore **exploratory**. P4 (shuffled-EMG conditioning) passed — largest loss
0.038 — so the partialling procedure is sound and the numbers are at least meaningful.

**My P2 prediction was wrong, and the reason is cleaner than the statistic.** I predicted Lempel-Ziv's dose
association would not survive conditioning on EMG. It survives essentially untouched: raw within-subject
partial ρ = **+0.693** against plasma order, becoming +0.737 conditioned on `emg_index`, +0.710 on
`emg_beta_gamma_fraction`, +0.679 on `emg_kurtosis`. It also survives conditioning on relative alpha power
(+0.664, 96 % retained), which was my second candidate explanation.

The direction argument is what settles it, and it is stronger than any partial correlation:

| level | lempel_ziv | emg_kurtosis | emg_beta_gamma |
|---|---|---|---|
| baseline | 0.740 | 0.401 | 0.0795 |
| mild | 0.770 | 0.228 | 0.1159 |
| moderate | 0.819 | 0.221 | 0.1173 |
| recovery | 0.737 | 0.348 | 0.0983 |

**Kurtosis — the muscle-specific proxy — FALLS with dose and returns at recovery, exactly as muscle relaxation
predicts. Lempel-Ziv RISES. The two move in opposite directions, so muscle relaxation cannot produce the LZ
effect.** And `emg_beta_gamma_fraction` *rises* with dose (0.0795 → 0.1173); if it were measuring muscle it
would fall, so in this dataset that proxy is tracking propofol's known beta activity rather than muscle —
resolving, by direction, the ambiguity `features/emg.py` flagged as unresolvable by magnitude.

**THE ERROR THAT MATTERS: I reported Lempel-Ziv as the best-performing candidate across three experiments
without once checking its sign against its own registered prediction.**

`seed.py` declares `lempel_ziv` as `unconscious_vs_awake: lower` — complexity should FALL under anaesthesia,
which is the entire basis of the complexity-and-consciousness literature (Casali PCI, Sarasso). **It rises.**
E05 reported "90 % monotone in plasma", E06 reported "0.900 on all channels, 0.800 at the median single
electrode", and E11's ranking put it top — all of which measured the *strength* of an association whose *sign*
was never compared with the declaration. Under the project's own rules a candidate firing opposite to its
declared direction is **refuted, not confirmed**.

The engine said so the moment the contrast was put through `layer_statistical` properly:
`FAIL directional_discrimination — AUC 0.223 [0.110, 0.335] in the declared direction (lower)`. It took running
the candidate through the machinery rather than a bespoke monotonicity score to surface it.

**This is E04's P2 defect repeating.** There I recorded that scoring every candidate as "lower" conflated two
hypotheses because "lower" means *deeper* for complexity measures and *lighter* for the exponent. I wrote that
"a direction must be declared per measure, not per experiment" and then, in E05 and E06, used an unsigned
monotonicity fraction that discards direction entirely. The lesson was recorded and not applied.

**What now stands.** There is a robust, within-subject, dose-ordered association between binarised broadband
complexity and measured plasma propofol, surviving muscle and alpha controls, at ρ ≈ +0.69 across 20 subjects.
**It is not evidence for `lempel_ziv` as a consciousness marker; it refutes its registered direction.** What
physiological account produces rising binarised complexity with deepening propofol sedation is open, and any
such account has to explain why it contradicts the perturbational-complexity literature. Until there is one,
this is an anomaly, not a marker.

**Standing rule added.** No candidate may be described as performing well on any unsigned statistic —
monotonicity fraction, |ρ|, direction-free AUC — without its signed comparison against its declared direction
reported alongside. The unsigned versions exist for nuisance probes, where sign is meaningless, and they must
not leak into candidate evaluation.

### 9.13 E08: the exponent's failure was a BAND-AVERAGING artefact — and Colombo's split finds it

**One candidate out of fourteen supports its own declared direction.** That candidate is `exponent_high`, the
aperiodic exponent fitted over **20–40 Hz only**:

| fit band | signed AUC, baseline vs moderate (declared `higher`) | verdict |
|---|---|---|
| **20–40 Hz** (`exponent_high`) | **0.863 [0.790, 0.948]** | **SUPPORTS** |
| 1–40 Hz (`whole_head_exponent`) | 0.393 [0.273, 0.513] | spans 0.5 |
| 1–20 Hz (`exponent_low`) | 0.168 [0.070, 0.242] | **OPPOSITE — refuted** |

**The two sub-bands point in opposite directions, and the whole-band fit averages them to nothing.** That is
the resolution of the puzzle E05 opened: the exponent appeared to order propofol dose in only 45 % of subjects
and to be beaten by complexity measures, and the reason is that a single 1–40 Hz slope is the average of two
regimes with *opposing* dose responses. Nothing was wrong with the estimator; the analysis band was wrong.

**§9.9's preprocessing explanation was right in spirit and wrong in mechanism.** I attributed the failure to the
deposit's 45 Hz filter roll-off contaminating a 40 Hz fit edge. The actual cause is that the spectrum has two
regimes and the project fitted across both. Fit range mattered enormously — just not for the reason given.

**This is Colombo's own decomposition, and it delivered.** `LITERATURE_MAP.md` §0 records that Colombo et al.
(PMID 30639334) fit 1–20 and 20–40 Hz separately and locate the drug dissociation specifically in 20–40 Hz.
That is why `exponent_low`/`exponent_high` were registered, with `higher` declared for both from Colombo's
sign convention, **before** anything was computed. The prediction was inherited from the literature rather
than found in the data.

**The redundancy gate killed nothing, and refuted my own P1.** I predicted `exponent_low` would duplicate the
1–40 Hz exponent at |ρ| ≥ 0.90, since most spectral power sits below 20 Hz. Measured |ρ| = **0.579** — and its
*closest* incumbent is not the exponent at all but `lempel_ziv` at 0.835. The band split is real, not a
re-parameterisation, which is exactly what makes the result above meaningful rather than circular.

`spatial_participation_ratio` also survived redundancy (max |ρ| = 0.742 against `spectral_entropy`), confirming
P2: **it reads something the per-channel measures do not.** But its direction is *refuted* (0.375 [0.243,
0.495], declared `lower`, observed higher). So spatial structure does carry information here — E06's "one
channel ≈ 91" is a fact about the feature set, not about the brain — and that information points opposite to
the prediction that anaesthesia increases spatial redundancy.

**FIVE CAVEATS, none of which the headline should be quoted without.**

1. **One hit in fourteen, against a denominator of 17 registered candidates.** The mitigating fact is that this
   was a *pre-registered directional prediction taken from prior art*, not a search hit — but the denominator
   travels with it regardless (constraint 6).
2. **`analytic_dof = 1` is known false** (§9.14, E09 in flight). The real denominator is larger than 17 and
   nobody yet knows by how much.
3. **40 Hz sits near the deposit's 45 Hz filter edge**, and E09's sweep varies `fit_hi` only for fits starting
   at 1–3 Hz. **It therefore does not test 20–40 Hz stability at all.** That is a gap in the sensitivity
   analysis, created by writing E09 before this result existed, and it must be closed before the number is
   relied on.
4. **Baseline vs moderate is a two-point contrast in 20 healthy volunteers on one drug at one site.** It says
   nothing about consciousness; the outcome is a measured drug concentration.
5. **The seed set is otherwise a graveyard.** Six of fourteen candidates are refuted outright, including
   `lempel_ziv` (0.223, confirming §9.12), `spectral_entropy`, `relative_delta_power` and three of the six
   exotic features. Five more span 0.5. A field in which one measure works and thirteen do not should raise
   the prior that the one is also an artefact until it replicates elsewhere.

**Next, in order:** close the caveat-3 gap by sweeping `exponent_high`'s own fit band; then test it on
ds005620 and Sleep-EDF, where it has never been computed. A 20–40 Hz result that holds across three deposits
with different filtering would be the first finding in this project worth calling a lead.

### 9.14 E09: the exponent is stably WRONG, not unstable — and the fit-edge gradient independently confirms §9.13

**My P1 was wrong, and the falsification branch fired.** I predicted the exponent's signed AUC would be
sign-unstable across preprocessing variants. It is not: **0 of 72 variants above 0.5, 72 of 72 below.** Every
defensible combination of fit range (1–3 to 20–45 Hz), estimator (OLS or robust) and Welch window (2/4/8 s)
puts the exponent *opposite* to its declared direction. It is not noisy — it is consistently wrong.

**But the gradient is the finding.** Median signed AUC by upper fit edge:

| fit_hi | median signed AUC |
|---|---|
| 20 Hz | 0.070 |
| 30 Hz | 0.129 |
| 40 Hz | 0.247 |
| 45 Hz | 0.344 |

**Monotone: the more high-frequency content the fit includes, the closer it moves to 0.5 and beyond.** E08
completes the line — a fit that *starts* at 20 Hz and excludes the low band entirely reaches **0.863**. E09 was
designed and committed before E08's result existed, so this is an independent reproduction of the same
mechanism: the low band and high band carry opposite dose responses, and any fit spanning both is a weighted
average whose sign is set by whichever dominates.

**§9.9's explanation is dead in its stated form and alive in another.** The filter-roll-off account is
refuted — extending the fit *into* the roll-off (45 Hz) makes the result *better*, not worse, which is the
opposite of contamination. What survives is the band-composition account of §9.13.

**P4, the control, passed and therefore licenses the above.** `relative_delta_power` — a band integral rather
than a slope fit — has an IQR of **0.018** across the same 72 variants against the exponent's **0.196**, an
eleven-fold difference. The instability is specific to the slope estimator, not a property of the cohort or the
outcome. Had the control been equally unstable, none of this would have been interpretable.

**`analytic_dof` has been misreported in every SEARCH_LOG entry.** The measured lower bound is **72 for the
aperiodic exponent alone**, against the `1` declared throughout. A lower bound because reference scheme cannot
be varied here — the deposit arrives average-referenced and the original reference is unrecoverable, and
reference choice is known to change the exponent.

**The correction is to the denominators, not to the results.** No experiment is invalidated: the numbers were
computed as described and the code is unchanged. What was wrong is the claim about how many analyses *could*
have been reported. Every previously logged `effective_search_space` is too small — E02 through E08 recorded
8–17 when the exponent alone contributes 72 analytic variants. Re-running is not the remedy; restating is.
Going forward, `analytic_dof` must be the number of analysis variants that were *available and defensible*, not
the number executed, and a value of 1 is only honest when the analysis genuinely admits no choices.

### 9.15 E10: the muscle test refuted its own instrument — and named a worse explanation than muscle

**Why the test existed.** `exponent_high` fits **20–40 Hz**. `EMG_BAND` is **(20, 45)**. E08's best candidate
by a wide margin reads the same frequencies as this project's own muscle proxy, and the confound comes with
the right sign for free: propofol reduces muscle tone → less high-band power → steeper 20–40 Hz slope →
*higher* exponent, which is exactly what `exponent_high` declares for unconsciousness. Rule 28 is why this got
a whole experiment rather than a footnote: three times this project has assumed two differently-measured
things must measure different things. Here they are not even differently measured.

**Every number below was verified against an independent implementation before acceptance** (rule 23):
brute-force pairwise Mann–Whitney AUC and `scipy.stats.rankdata`, not the project's own midrank module. All
agreed to three decimals.

**The instruments disagree in sign, which is rule 16 firing on the test itself.**

| muscle proxy | signed AUC, declared `lower` | reading |
|---|---|---|
| `emg_kurtosis` | **0.682 [0.517, 0.848]** | spikiness falls with sedation — consistent with muscle |
| `emg_beta_gamma_fraction` | **0.292 [0.167, 0.420]** | 20–45 Hz power *rises* — cannot be muscle |
| `emg_index` (composite) | 0.585 [0.415, 0.752] | averages two opposing phenomena; **discarded** |

The EMG direction was declared **a priori from physiology**, not read off the data. The first draft scored
both orientations and took the maximum, which picks the sign from the sample and then asks whether it beats
0.5 — a question already forced to *yes*, since the two AUCs sum to 1. The bootstrap lower bound inherits that
bias and clause (a) would have fired on noise. Caught and fixed before the run.

**A 20–45 Hz relative-power measure under propofol is not reading muscle. It is reading propofol beta.**

> Xi C, Sun S, Pan C, Ji F, Cui X, Li T. *Different effects of propofol and dexmedetomidine sedation on
> electroencephalogram patterns: wakefulness, moderate sedation, deep sedation and recovery.*
> PLoS One. 2018;13(6):e0199120. **PMID 29920532.** — "During moderate sedation … propofol decreased the alpha
> power in the occipital area and **increased the global spindle/beta/gamma power**."
>
> Verified from the MEDLINE record via E-utilities (rule 25). Not WebFetch, which fabricated six citations for
> this project once.

**On the one instrument that survives its own sign check, `exponent_high` survives: 0.863 → 0.812 [0.680,
0.932]** after residualising on `emg_kurtosis`. Clause (a) failed — no proxy tracks sedation as well as the
candidate does — so the two-clause confound rule never had standing to fire.

**The clearance is weak, and doubly so.** The deposit is filtered 0.5–45 Hz and the suite already measured
that a 45 Hz low-pass substantially degrades detection of realistically-peaked muscle (§9.11). A negative from
a degraded instrument is *weak evidence of no muscle*, not *evidence of no muscle*. Clearing it properly needs
a deposit with unfiltered high frequencies.

**P1 failed and my reasoning was backwards.** I predicted `rho ≤ −0.5` against the muscle proxy and got
**+0.448**. A steeper slope means less high-band power only for a *between*-band ratio; `exponent_high` is a
*within*-band slope and no such relation holds. The positive sign has a single coherent explanation: a
propofol beta hump near the **low edge** of a 20–40 Hz fit window raises the band's total power *and* steepens
the slope fitted across it. One mechanism, both observations — and it is the propofol-beta reading again,
arriving by a second route.

**The alternative explanation this generated is worse for the project than muscle would have been.** If
`exponent_high` is propofol beta, it is a real *drug* effect and not a consciousness marker, and Brief 01 is
specifically about separating drug from state. It cannot be tested on Chennu, where every contrast moves drug
and state together, and it cannot be tested by E10, which generated it — testing it there would be exactly the
rewrite-after-seeing the anti-p-hacking constraints forbid. **E11 registers it on Sleep-EDF (drug-free, wake
vs N3), committed before any Sleep-EDF feature value was read.**

**Three presentation/logic defects fixed, none touching the registered predictions:** no rule-16 sign check
existed (added, and it now *gates* the verdict); `*** no longer excludes 0.5` printed beside candidates whose
raw AUC never excluded it — most of them, since most registered candidates are refuted (rule 4); and the
registered control proved weak (`relative_delta_power` raw 0.320, |AUC−0.5| = 0.180), so `exponent_low`
(0.333) is reported *beside* it as the stronger control rather than substituted for it after the fact.

**Still open, and stated in the script's own docstring:** the 20–40 Hz band was itself chosen *after* seeing
1–20 and 1–40 behave differently. E09 swept only `fit_lo ∈ {1,2,3}`; **no sweep of the high band has ever been
run.** That needs its own extraction pass and its own pre-registration.

### 9.16 CORRECTION, and it is the largest one in this project: Chennu never reaches unconsciousness

**Every candidate in this project is scored against `predicted("unconscious_vs_awake")`. The Chennu contrast
that produced E08's 0.863 is not that contrast, and I never checked.**

Chennu ships the behavioural data needed to check, in columns this project has been loading since E05:

| level | plasma propofol µg/L (median, range) | n_correct / 40 (median, range) | subjects < 20/40 | subjects with no responses at all |
|---|---|---|---|---|
| 1 baseline | 0 (0–0) | 39 (30–40) | 0/20 | 0/20 |
| 2 mild | 438 (144–878) | 37.5 (5–40) | 2/20 | 0/20 |
| **3 moderate** | **803 (433–1521)** | **35 (0–40)** | **6/20** | **2/20** |
| 4 recovery | 276 (148–483) | 38 (33–40) | 0/20 | 0/20 |

**At level 3 the median subject gets 35 of 40 correct and 14 of 20 subjects score at or above 20/40.** Two
subjects out of twenty stop responding entirely. The primary contrast used in E05, E07, E08, E09 and E10 —
level 1 versus level 3 — is therefore **fully awake versus mostly still awake**. It is a model of mild-to-
moderate sedation. It is not a model of unconsciousness, and the outcome it is scored against is named
`unconscious_vs_awake`.

**This is not a small mislabelling; it reorganises the whole result set.** It explains the pattern that has
been visible in every table and never questioned: on Chennu, *nearly every candidate scores below 0.5*.
`exponent_low` 0.168, `lempel_ziv` 0.223, `spectral_entropy` 0.292, `relative_delta_power` 0.320,
`whole_head_exponent` 0.393. Their declared directions were calibrated against unconsciousness, and moderate
sedation moves the EEG somewhere else, so they read as refuted when they were merely being asked the wrong
question. E11's Sleep-EDF table shows the same measures at 0.99+ in the declared direction on a contrast that
does reach N3.

**And it sharpens the case against the project's best number rather than defending it.** `exponent_high` is
the one candidate that goes the declared way under moderate sedation — which is exactly what a measure of
propofol's sedative-dose beta activation would do.

> Xi C, et al. PLoS One. 2018;13(6):e0199120. **PMID 29920532** — "During moderate sedation … propofol …
> increased the global spindle/beta/gamma power."
>
> Purdon PL, Pierce ET, Mukamel EA, … Brown EN. *Electroencephalogram signatures of loss and recovery of
> consciousness from propofol.* Proc Natl Acad Sci U S A. 2013;110(12):E1142-51. **PMID 23487781** — "Loss of
> consciousness was marked simultaneously by an increase in low-frequency EEG power (<1 Hz), the loss of
> spatially coherent occipital alpha oscillations (8–12 Hz), and the appearance of spatially coherent frontal
> alpha oscillations."
>
> Both verified from the MEDLINE record via E-utilities (rule 25).

The signature of *actual* loss of consciousness under propofol is a low-frequency and alpha phenomenon.
**The 20–40 Hz band where `exponent_high` lives is where propofol's sedative-dose effect lives, and is not
where the loss-of-consciousness signature lives.** That is a sourced statement about band position, and it is
deliberately weaker than "beta disappears at deeper levels" — Xi et al. report beta power still elevated at
*deep* sedation, so that stronger claim is not supported and is not made.

**What must be restated, per rule 1 (a correction propagates to everything downstream, not just the number
that prompted it).** No number is withdrawn — every value was computed as described. What changes is what
each one is a measurement *of*:

- **E05, E07, E08, E09, E10 report on MILD-TO-MODERATE SEDATION IN RESPONSIVE VOLUNTEERS, not on
  unconsciousness.** Any sentence in this project pairing a Chennu number with the word "unconscious" is
  wrong and must be rewritten to say "moderately sedated".
- **E08's 0.863 is a sedation-depth discrimination, not a consciousness discrimination.** It may still be a
  fine anaesthesia-monitoring result — Brief 01's commercial wedge is depth-of-anaesthesia — but it is not
  evidence about consciousness, and the flagship claim cannot rest on it.
- **The "candidates mostly fail on Chennu" finding is largely an artefact of the mismatch.** The failures are
  real as *sedation* results and are not evidence against those measures as *unconsciousness* markers.
- **`unconscious_vs_awake` is the wrong outcome key for every Chennu cohort.** The registry should carry a
  distinct outcome (`sedated_vs_awake`), so that a candidate's direction is scored against the state actually
  present. Until that exists, every Chennu direction test is comparing against a declaration written for a
  different question.

**How this was missed, which is the part worth keeping.** The behavioural columns were loaded, printed in
table headers, and passed through five experiments without once being turned into the question "is this
cohort unconscious?". Error-catalogue rule 32 says a measurement's availability defines a stratum and that
stratum is selected on the thing that makes the measurement possible; the sibling failure here is simpler and
worse — **the outcome's NAME was taken as a description of the data instead of as a claim to be checked, and
one `median()` over a column already in the table would have caught it at E05.**

### 9.17 E12 is registered and BLOCKED: the Chennu host's certificate no longer covers its own name

E12's pre-registration is committed (`e12_high_band_sweep.py`, 108 variants) and its extraction **cannot
run**. Diagnosis, recorded so the next session does not repeat it:

```
api.repository.cam.ac.uk   TLS fails — the certificate presented has
                           subject CN = repository.cam.ac.uk
                           SAN       = DNS:repository.cam.ac.uk   (only)
                           so the SAN does not cover the host being requested
repository.cam.ac.uk       502 on CONNECT at the egress gateway
```

The certificate is a genuine University of Cambridge certificate, so this is an **upstream server
misconfiguration**, not a proxy trust problem — pointing at the proxy CA bundle changes nothing, because the
failure is hostname coverage rather than chain validation. The same host served this project successfully
earlier the same day (the `chennu_features_v3` extraction completed at 13:51), so it is a change on
Cambridge's side and may well be transient. Three retries over a minute all failed identically, so it is not
a single bad edge node.

**Not worked around.** Disabling certificate verification would make every future Chennu fetch
unauthenticated, and the standing instruction is explicit that TLS verification is never disabled and egress
denials are reported rather than routed around. `E12_LIMIT` and the resume logic mean the sweep can be
restarted from zero cost as soon as the host is fixed: `python src/bsde/experiments/e12_high_band_sweep.py`.

**What this blocks.** The 20–40 Hz band remains **unswept**, so E08's 0.863 still has an unknown denominator.
That is the single most important open item, because §9.16 has already reduced what the number means (a
sedation-depth discrimination, not a consciousness one) and E12 decides whether it survives as even that.

### 9.18 Where the project actually stands after E10, E11 and correction 9.16

**The headline number has not been withdrawn, but almost everything about what it means has changed.**

| claim | status after this session |
|---|---|
| `exponent_high` AUC 0.863 on Chennu | **stands as computed**, verified against an independent implementation |
| …as a *consciousness* marker | **withdrawn.** §9.16: the cohort is not unconscious at any level |
| …as a *sedation-depth* marker | plausible, unswept band, one deposit, n = 20 |
| muscle artefact explanation | **weakly disfavoured** — survives residualisation on the one proxy that passes its own sign check (0.863 → 0.812 [0.680, 0.932]), on a deposit whose filtering degrades the instrument |
| propofol-beta explanation | **live and untested.** E11 could not test it; E12 would, and is blocked |
| band choice (20–40 Hz) | **never swept.** Chosen after seeing 1–20 and 1–40 behave differently |
| Sleep-EDF replication | **uninformative** — contrast saturated, median \|AUC−0.5\| = 0.470 across candidates |

**Nothing here is presentable as a finding yet, and the reason is worth stating plainly rather than softening.
The strongest result in this project is a measurement of what a sedative dose of propofol does to a
frequency band, in twenty responsive volunteers, at a band position that was chosen after looking.** Each of
those three qualifiers came from a check this session ran on itself, and each was preventable by a check that
existed before the work started.

**The next three things, in order:**
1. **E12 when Cambridge's host is fixed** — decides whether 0.863 is a peak or a plateau. Everything else is
   downstream of that answer.
2. **A `sedated_vs_awake` contrast in the registry**, with directions cited from the literature and flagged
   as *declared post-exposure* — the Chennu results have been seen, so those directions can only be tested
   cleanly on a different sedation deposit. ds005620 is streaming and is the natural candidate.
3. **A harder sleep contrast (N2 vs N3, or W vs N1)** so that a drug-free test can actually discriminate
   between candidates instead of passing all of them.

### 9.19 Verifier layers 5 and 7 built — and layer 7 says the 0.863 would not be usable

**Three of the seven layers did not exist. Two now do.** Layer 6 (mechanistic) remains gated on data this
project cannot reach — it needs ketamine, locked-in or neuromuscular-blockade dissociations — not on code.

**Layer 5 (temporal)** asks whether a measure holds still long enough to be read from one window. Layers 2–4
all collapse a recording to a single number before they start, so none of them can see a measure whose
window-to-window scatter inside a state exceeds the gap between states. `temporal_snr` is fatal below 1.0.
The test that justifies the layer plants a measure with **group AUC 1.0** that layers 2–4 wave through and
that fails here. `critical_slowing_ar1` has declared `requires: temporal` since it was registered, and E08's
P4 has been standing guard over the gap ever since.

**Layer 7 (clinical)** asks whether *using* the measure would help. Its whole premise is one sentence:
**AUC is prevalence-free and threshold-free, and clinical use is neither.** Layer 2 already checks
calibration, which is necessary and not sufficient — a perfectly calibrated measure can still be worse than
treating everyone.

**Applied to the project's best result, `exponent_high` on Chennu (n = 40, 20 subjects):**

| quantity | value |
|---|---|
| raw feature AUC (E08's headline) | **0.863** |
| AUC of cross-validated fitted probabilities | 0.820 |
| specificity at the threshold reaching 90 % sensitivity | **0.500** |
| sensitivity at the threshold reaching 90 % specificity | 0.600 |
| PPV at prevalence 0.50 (the sample's own, a design choice) | 0.643 |
| PPV at prevalence 0.20 | 0.310 |
| PPV at prevalence 0.05 | **0.087** |
| net benefit vs treat-all / treat-none | PASSES at threshold probabilities 0.2–0.3 |
| minimum detectable change | NOT_RUN — needs layer 5 inputs (E14's stream) |

**The two numbers are not the same quantity and the difference must not be reported as a correction.** 0.863
is the AUC of the raw feature and involves no fitting, so it does not overfit in the usual sense. 0.820 is
the AUC of *probabilities* from a logistic fit with an intercept and slope estimated per fold on 40 rows; the
gap is fold-fitting noise at small n, not evidence that 0.863 was inflated.

**What layer 7 adds is the rest of the table, and it is unflattering.** At an operating point any clinician
would want — 90 % sensitivity — the measure's specificity is **a coin flip**. And the sample prevalence of
0.50 is not a fact about the world; it is a design artefact of contributing one baseline and one sedated
window per subject. Every cohort in this project is near 50/50 by construction, so any PPV quoted from one
describes a world in which half of all patients are sedated. **At 5 % prevalence a positive reading is
correct 8.7 % of the time.**

The layer refuses to guess the prevalence, the harm ratio or the target sensitivity — those are clinical and
product facts, and each check returns NOT_RUN with the reason rather than substituting the sample's. A
NOT_RUN is not a pass.

**The one encouraging number is the decision curve**, which is also the check most likely to be skipped
elsewhere: acting on the measure does beat both treating everyone and treating no one, at threshold
probabilities between 0.2 and 0.3. That is a genuine, if narrow, window of usefulness.

**`minimum_detectable_change` is where the two new layers compose**, and it is the question a monitor is
actually asked: not "do these two populations differ" but "did this patient move". MDC95 = 1.96·√2·(within-
state scatter), compared against the between-state difference. It cannot be computed from any table this
project currently holds, because all of them carry one window per subject per state — which is precisely why
E14's multi-window extraction exists.

### 9.20 E13: the candidate set is not one measurement — but the directional claim spans the boundary

**The first contrast this project has reached that pulls two constructs apart.** REM is at least as
behaviourally unresponsive as N3 (motor atonia, high arousal threshold) while its EEG is wake-like — which is
part of its scoring definition. So "where does a candidate place REM?" asks whether it tracks BEHAVIOURAL
STATE or EEG ACTIVATION. 141 recordings with a complete W/N1/N2/N3/REM ladder, 120 s windows.

**REM position index** = (v[REM] − v[N3]) / (v[anchor] − v[N3]); 1.0 puts REM at the light pole, 0.0 at N3.

| candidate | W-anchored | N1-anchored |
|---|---|---|
| `relative_alpha_power` | 1.345 [1.100, 1.724] | 0.789 [0.696, 0.846] |
| `wpli_alpha` | 0.839 [0.766, 0.929] | 0.990 [0.920, 1.015] |
| `lempel_ziv` | 0.638 [0.609, 0.700] | 0.824 [0.756, 0.906] |
| `whole_head_exponent` | 0.522 [0.505, 0.540] | 0.864 [0.824, 0.929] |
| `emg_beta_gamma_fraction` | 0.274 [0.225, 0.295] | 0.605 [0.516, 0.722] |
| **`exponent_high`** | **−0.189 [−0.305, −0.104]** | **0.453 [0.331, 0.639]** |

**What is established.** P2 met: the spread across candidates is **0.537**, past the registered 0.50. The
registry is **not one measurement wearing fourteen names** — and because the circularity of sleep staging
acts on every candidate equally, it cannot manufacture disagreement between them. That was the registered
falsification and it did not fire.

**What is NOT established, and the distinction is the whole result.** P3 met *as registered* — one candidate,
`exponent_high`, places REM nearer N3 — but the registered rule tests the **point estimate**, and its interval
is **[0.331, 0.639]**, which spans 0.5. **Error-catalogue rule 37: a cell that spans the null is neither
direction and must not satisfy a directional criterion.** So this does not show that any candidate tracks
behavioural state rather than EEG activation. The registered prediction is reported as met; the stronger
reading beside it is reported as not met; where they disagree the weaker claim survives.

**The temptation this result creates, named so it can be refused.** `exponent_high`'s *W-anchored* interval
[−0.305, −0.104] excludes 0.5 decisively — it places REM **beyond** N3. But **P4 failed** (anchors agree for
only 7 of 14 candidates), and the registration declared *in advance* that the W anchor is the contaminated
one: Sleep-EDF's wake is overwhelmingly daytime wake, one hypnogram carrying a single contiguous 30,630 s
wake block, drawn with eyes open and moving. **Reading the result off the anchor pre-declared unreliable,
because it gives the cleaner answer, is exactly the move the pre-registration exists to prevent.**

**Anchor robustness, measured rather than assumed.** P4 asked whether the anchors agree in *value*; they do
not. Whether they agree in *order* is the weaker question the spread claim actually rests on, so it was
measured: **Spearman +0.578** — moderate. `exponent_high` is the candidate closest to N3 under **both**
anchors, which is the one anchor-robust fact here, but the ordering as a whole is not solid.

**A machinery-gate defect worth more than the epsilon that exposed it.** P1's median Spearman came out as
0.7999999999999998 against a registered threshold of ≥ 0.80 — one unit in the last place short, so the gate
failed on floating-point representation while the registered rule was met. The tolerance fixes the code to
agree with the rule. The real error is that **a four-point ladder makes Spearman quantised** — attainable
values are 0, ±0.2, ±0.4, ±0.6, ±0.8, ±1.0 — and putting the threshold on the atom that 34.8 % of subjects
sit on means the verdict is decided by representation rather than by data. The durable fix is that the
distribution is now printed (24.1 % at +1.0, 34.8 % at +0.8, 33.3 % at +0.4, mean +0.650, **95.7 % of
subjects ordering the ladder correctly**), so marginality is visible instead of hidden behind a pass/fail.

**What would settle it:** more subjects, or an anchor that is neither daytime wake nor a 180-second
transitional stage. Both are extraction work, not analysis work.

### 9.21 E15: the exponent REPLICATES on a second propofol deposit — and §9.13's band split does not

**First independent replication in this project.** `exponent_high` on ds005620, in the `acq=tms` stratum —
the only one where acquisition condition is matched between awake and sedated (17 vs 38 recordings, 17
subjects):

| candidate | signed AUC, awake vs sed |
|---|---|
| **`exponent_high`** | **0.762 [0.648, 0.885]** |
| `whole_head_exponent` (1–40 Hz) | 0.745 [0.669, 0.841] |
| `uce_v1` | 0.732 [0.630, 0.845] |
| `relative_alpha_power` | 0.718 [0.572, 0.852] |
| `exponent_gamma` (50–90 Hz) | 0.636 [0.474, 0.776] |
| `exponent_low` (1–20 Hz) | 0.432 [0.255, 0.628] |
| `lempel_ziv` | 0.241 [0.127, 0.379] — wrong direction, as on Chennu |

**P2 met. E08's finding is not Chennu-specific.** That is the durable half of this result.

**THE BAND SPLIT DID NOT REPLICATE, AND THAT IS §9.13'S CORE CLAIM.** On Chennu the whole-band 1–40 Hz
exponent pointed the *wrong way* (0.393) while only the 20–40 Hz fit worked (0.863) — the band-averaging
story. Here the two are indistinguishable: the paired gap is **+0.017 [−0.082, +0.103]**. Whatever §9.13
described is a property of the Chennu recordings, not of propofol. **§9.13 should no longer be cited as a
general mechanism.**

**P3 was NOT MET, and that must not be read as refuting the beta-hump explanation.** My registered P3
compared two point estimates and had no way to say whether the difference was real. Bootstrapped over
subjects — both AUCs come from the same rows — the gap is **+0.125 [−0.035, +0.309]**, which **includes
zero**. And `exponent_gamma`'s own CI **spans 0.5**, so it has no established association either way. "Both
bands respond" is not what the data says. **The question is UNDETERMINED at n = 17 subjects, not answered**
(rule 31: absent, not negative). This is the third time today a point estimate has been asked to carry a
directional claim its interval will not support.

**The EMG gate passed**, which matters more here than anywhere else: unlike Chennu, ds005620 retains the
frequencies where surface muscle actually lives, so its EMG proxies are good instruments rather than degraded
ones. `exponent_gamma` survives residualisation on all three.

**What the beta-hump question still needs:** E12's band sweep on Chennu (blocked, §9.17), or more subjects
with a 50–90 Hz band. The synthetic ground truth in `tests/test_exponent_gamma.py` still stands — a 20 Hz
peak drives a 20–40 Hz fit from 1.983 to 9.872 with the aperiodic exponent fixed at 2.0 — so the mechanism
remains real, sufficient, and untested on real data.

**Where the lead now stands.** `exponent_high` discriminates sedation depth on two independent propofol
deposits, survives muscle residualisation on both, and is not explained by the band-split story that
originally motivated it. It is still not a consciousness marker (§9.16 — neither cohort reaches
unconsciousness), its 20–40 Hz band was still chosen after looking (E12 still blocked), and layer 7 says that
at 5 % prevalence a positive reading would be right 8.7 % of the time (§9.19).

### 9.22 Verified status of the seven layers and the three challenges, 2026-07-30

Supersedes the status columns of §2 and §5. Every row below was checked against the code or the results
directory, not recalled.

**The verifier stack.**

| # | layer | status now | what changed / what still blocks |
|---|---|---|---|
| 1 | Computational | **BUILT** | extended with `test_exponent_gamma.py` — the synthetic proof that a 20 Hz peak inflates a 20–40 Hz fit fivefold with the aperiodic exponent fixed |
| 2 | Statistical | **BUILT for one candidate at a time** | calibration primitives now run end-to-end inside `layer_statistical`. **Still missing: multiple-comparison control ACROSS candidates.** `search_space_size` is reported everywhere but nothing corrects for it |
| 3 | Adversarial | **PARTIAL** | confound/redundancy machinery is complete and is the project's primary acceptance test. **`preprocessing_sensitivity` is still an unpopulated report row** — E09 computed 72 variants and E12 registered 108 more, but no `Evidence` carries that item, so every report still prints `NOT_RUN` |
| 4 | Cross-domain | **BUILT and now EXERCISABLE** | was blocked on having only one labelled deposit. There are now **three** — Chennu (propofol), Sleep-EDF (sleep, two tables), ds005620 (propofol) — and E03/E11/E15 have used them |
| 5 | Temporal | **BUILT** (`verifier/temporal.py`, wired into `verify()`) | within-state stability, single-window penalty, ICC/effective-n. **Temporal PRECEDENCE — does the measure move before the label — is still not built**, and needs densely-sampled transitions with a verified time axis (rule 27) |
| 6 | Mechanistic | **NOT BUILT** | unchanged, and gated on DATA not code: needs a dissociation deposit (ketamine, locked-in, neuromuscular blockade). None ingested |
| 7 | Clinical | **PARTLY BUILT** (`verifier/clinical.py`, wired) | §2 said "not reachable with public data". That is right about *outcomes* and wrong about *decisions*: PPV at declared prevalence, operating points, net benefit and minimum detectable change are all computable now and were run in §9.19. What remains unreachable is whether using it **improves an outcome**, which needs a prospective protocol |

**Test count, verified by running the suite: 289 passed, 6 skipped** (was 134 when §2 was written).

**The three discovery challenges.**

| challenge | status | the blocker, precisely |
|---|---|---|
| **A** — simplest representation predicting loss/recovery across multiple drugs, minimising drug-identity information | **STILL BLOCKED, for a sharper reason than §5 states** | §5 said "needs at least Chennu and VitalDB ingested". Chennu is ingested and so is ds005620 — **but both are PROPOFOL.** The challenge is specifically *across anaesthetic drugs*, and a second drug is not merely un-ingested, it is unidentified. VitalDB (sevoflurane) remains the candidate and is not ingested |
| **B** — spontaneous EEG features associated with command-following in DoC | **BLOCKED, unchanged** | Bath access is request-only and not granted. Even granted, no task-trial candidate and no within-subject-null layer exist |
| **C** — trajectory feature predicting a transition ahead of a conventional monitor | **BLOCKER PARTLY REMOVED** | §5's blocker was "the temporal layer does not exist". It exists now. C is blocked on DATA alone: serial per-patient EEG with a monitor comparator (VitalDB's BIS subset, or I-CARE), neither ingested into `bsde/`. Note the temporal layer's *precedence* half — the half C actually needs — is the part still unbuilt |

**The honest one-line summary: the engine got substantially more real today and the science did not move closer
to any of the three challenges, because all three are blocked on data acquisition rather than on code.**

### 9.23 E14: discrimination survives one window — and the ICC check reported the opposite of the truth

Layer 5's first run on real data. 60 recordings x 4 states (W/N2/N3/REM) x 3 consecutive 120 s windows = 720
rows, drawn from the central 360 s of each stage block so all three sit away from stage boundaries.

**P2 was a registered PREDICTION OF FAILURE and it did not happen — the good outcome.** I predicted at least
one strongly-discriminating candidate would have temporal SNR below 1.0, meaning group AUC would not transfer
to a single window. **None does.** The worst is `pac_slow_alpha` at 3.11; `exponent_high` is at 10.76,
`emg_beta_gamma_fraction` at 41.7. On this data, group-level discrimination transfers to the single window a
clinician actually has. That is a genuine positive for the candidate set and I was wrong in the pessimistic
direction.

**P4 REPORTED THE EXACT OPPOSITE OF THE TRUTH, and the check's whole purpose is the thing it got backwards.**
`effective_sample_size` exists to warn that repeated windows are not independent, so row-level resampling
overstates precision. The first run grouped by SUBJECT alone, pooling four sleep stages into one group — so
the enormous between-STATE variance landed inside the "within-group" term and pushed the ICC down:

| candidate | ICC grouped by subject | ICC grouped by (subject, state) |
|---|---|---|
| `exponent_high` | 0.159 | **0.927** |
| `relative_delta_power` | 0.101 | **0.917** |
| `lempel_ziv` | 0.089 | **0.971** |
| `whole_head_exponent` | 0.000 | **0.984** |
| `wpli_alpha` | 0.294 | **0.921** |

Regrouped correctly the median ICC is **0.932**, so P4 flips from NOT MET to MET and the substantive warning
is real: **n_eff ≈ n_rows / 2.9**, and any interval computed over rows rather than subjects is roughly 1.7×
too narrow. The grouping is now `(subject, state)` in `intraclass_correlation` itself, with a regression test
that reproduces the failure.

**P3 IS UNDETERMINED, NOT MET, AND THE SCRIPT NOW SAYS SO.** The registered rule was "Spearman between
|AUC−0.5| and temporal SNR below +0.70", and the measured value is **0.69999999999999984** — below the
threshold by **1.1 × 10⁻¹⁶**. Spearman over eleven candidates is quantised and this landed exactly on an
attainable value. A verdict decided by floating-point representation is not a verdict. **So layer 5's own
justification — that temporal SNR is not AUC wearing a different name — is NOT established by this run**, and
the layer is retained provisionally rather than vindicated.

**That is the third boundary case today** (E11's saturation count at exactly 8/11, E13's gate one ULP short,
now this). The pattern is mine, not the data's: I keep choosing thresholds that sit on attainable values of
quantised statistics. **A threshold on a quantised statistic must be placed BETWEEN attainable values, and
where it cannot be, the boundary must be reported rather than resolved.**

### 9.24 The Bath dataset, located precisely — and it is a "mixed access regime", not a closed door

**Two Bath records get confused and only one is ours.** `researchdata.bath.ac.uk/899` (DOI 10.15125/BATH-00899)
is *"An empirical evaluation of methodologies used for emotion recognition via EEG signals"* — Hinvest et al.
2022, healthy participants viewing SEED/NimStim/ADFES-BIV stimuli. **It has no DoC patients and no
command-following.** Right archive, wrong dataset, and its 1.6 GB zip downloads anonymously, which makes the
confusion easy and expensive.

**Ours is DOI 10.15125/BATH-01632 → https://researchdata.bath.ac.uk/1632/**

> *Motor-imagery brain-computer interface electroencephalography and behavioural assessment datasets in
> prolonged disorders of consciousness.* Coyle D., Du Bois N., Korik A., 2026. ClinicalTrials.gov
> **NCT03827187**.

| property | value, read from the record |
|---|---|
| cohort | **N = 42** — UWS **14**, MCS **17**, **LIS 11** — plus **2 able-bodied benchmark** participants on the same protocol |
| task | structured motor-imagery BCI to auditory cues, event triggers marking task onset/offset, multiple sessions per participant |
| linked measures | concurrent behavioural assessment scores (session-level) |
| paradigms | **Assessment, Training, Feedback, Q&A** |
| access | **restricted, "mixed access regime"** — granted on reasonable request, subject to custodian review |

**What a request must contain, quoted from the record**: "a brief description of the proposed research use,
evidence of relevant ethical approval, and agreement to data use conditions that prohibit data redistribution
or use beyond the approved scope." **The ethical-approval requirement is the real gate** and it is not
something this project can satisfy by asking politely — it needs an institutional sponsor.

**THE PART THAT IS ALREADY OPEN, AND IT IS NOT NOTHING.** Two files download without any request:

* `/1632/22/coyle_supporting_information_ncm.docx` (10.9 MB) — the protocol supporting information
* `/1632/23/coyle_SI_supplementaryData_ncm.xlsx` (217 KB) — **per-session, per-subject decoding accuracies**
  with `subject_ID`, `run_ID`, `session_ID` and a reference/chance accuracy column, plus group-level results
  by region (frontal, parietal, left/right temporal, sensorimotor, occipital) for UWS/MCS/LIS/AB, with
  effect sizes and post-hoc comparisons that run **LIS > MCS** and **LIS > UWS**.

That is enough to write the analysis, the montage handling and the pre-registration **before** access is
granted — and it means any prediction registered afterwards must declare that the published group-level
direction was already known. It is *not* enough to develop or test an EEG feature: it contains derived
accuracies, not signal.

**LIS n = 11 matters beyond Challenge B.** Locked-in syndrome is one of the named dissociations for verifier
**layer 6 (mechanistic)** — fully conscious, no motor output — which §9.22 recorded as gated on data rather
than code. **This one deposit would bear on Challenge B and on layer 6 at the same time**, which makes the
access request the highest-value external action available to this project.

**Separately, the BDSP Neurotech BIDS path is empty of data.** `s3://bdsp-opendata-repository/EEG/bids/Neurotech/`
lists **0 objects** through the anonymous REST endpoint, consistent with the console showing only
`LICENSE.txt` and `SHA256SUMS.txt` at 2.5 KB total. The signal there is access-gated too, and nothing is
downloadable without a request.

### 9.25 Exhaustive survey of public EEG repositories — one dataset found, and it fixes §9.16

**Method, because the answer is a negative and a negative is only worth as much as the search behind it.**
OpenNeuro's GraphQL `search` field returns null and its `advancedSearch` `keywords` filter returned **zero
hits for "propofol"** — a filter that cannot find ds005620, which this project already holds, is a filter
that proves nothing (rule 5). So all **447** OpenNeuro EEG datasets were enumerated by pagination instead,
verified by confirming the known positive appears, and then every dataset's `README`,
`dataset_description.json` and `participants.json` was fetched and scanned for anaesthetic and
disorders-of-consciousness terms.

| source | result |
|---|---|
| `meagmohit/EEG-Datasets` (curated list) | **nothing relevant.** Overwhelmingly BCI, motor-imagery and emotion. Zero anaesthesia, zero DoC |
| OpenNeuro, 447 EEG datasets, full text scan | **5 mention an anaesthetic or DoC term; 1 is usable and new** |

* **ds005620** — already ingested (propofol).
* **ds003380** — 11 juvenile **pigs**, isoflurane/fentanyl/propofol plus gradual ischaemia. A genuine
  multi-drug design and the wrong species for any human claim.
* **ds004940** — a **false positive**. "Disorders of consciousness" appears in its abstract as motivation;
  `participants.tsv` is 22 neurotypical adolescents aged 12–17 doing an N400/P600 listening task. Caught by
  reading the participants file rather than trusting the keyword.
* **ds004840** — music therapy in sedated adults, n = 9; not pursued.
* **ds004541 — the find.**

### ds004541: the first reachable deposit where consciousness is documented as actually lost

> *Multimodal EEG-fNIRS data from patients undergoing general anesthesia.* n = 8 patients, **CC0**, EDF,
> 1000 Hz, 58–62 EEG channels on an extended 10-20 montage.

Its `events.tsv` carries, per subject, an explicit responsiveness ladder and two markers this project has
never had:

```
baseline → start → verbal/soft → verbal/strong → motor → tetanic/1 → LOC → end → tetanic/2 → ROC
```

**`loc` and `roc` — loss and recovery of consciousness.** §9.16 established that the Chennu cohort never
reaches unconsciousness at any level, which reduced every Chennu result to a statement about moderate
sedation in responsive volunteers. This deposit is the correction: consciousness is lost, it is marked, and
the marking is anchored to a graded stimulation protocol rather than to a plasma concentration.

The amplitude signature is visible at the markers on a first read (median channel SD, 30 s windows,
sub-02): **baseline 1404 → pre-LOC 2513 → post-LOC 827 → post-ROC 1509**.

**What it unblocks beyond §9.16:**

* **Temporal precedence** — verifier layer 5's unbuilt half, and what Challenge C needs the *method* for.
  Windows are emitted at symmetric fixed offsets around `loc` (±30 to ±300 s) so "did the measure move
  before the clinician marked it" is answerable rather than assertable.
* **`emergence_within_subject`** — a contrast declared in `CONTRASTS` since the registry was written and
  never once tested. `loc → roc` is exactly it.
* **`uce_v1` is computable here.** It selects frontal and posterior regions by 10-20 name and returns NaN on
  HBN's EGI caps; this montage is extended 10-20.
* **Dedicated EMG and EKG channels.** Every muscle-confound argument in this project has rested on spectral
  proxies computed from EEG (§9.15 found two of them disagreeing in sign). This deposit has an actual muscle
  recording — far better evidence than a proxy.

**What it does NOT unblock, and the limit is load-bearing. THE DRUG IS NOT RECORDED ANYWHERE IN THE
DEPOSIT** — not in `dataset_description.json`, not in the README (boilerplate, "in preparation"), not in
`participants.json`. **So it cannot serve Challenge A**, which needs two identified and different agents, and
it must not be assumed to be propofol merely because the project's other two anaesthesia deposits are.
Recorded as unknown pending the authors or a publication.

**Challenge A therefore remains blocked, and the survey establishes that it is blocked in a stronger sense
than before: there is no second identified anaesthetic drug in any public EEG repository reachable from
here.** VitalDB (sevoflurane) is not an EEG deposit of this kind and remains the outstanding candidate.

`participants.tsv` carries no age, sex, weight or height — every field is `n/a` — so no demographic
covariate is available and none will be claimed.

### 9.26 VitalDB unblocks Challenges A and C — the survey's real result

PhysioNet (427 projects) and BDSP (10) were enumerated and scanned the same way as OpenNeuro, with the
parse verified against a known positive before any conclusion was drawn.

| repository | outcome |
|---|---|
| PhysioNet, 427 projects | `vitaldb` **(open, and the answer)**; `eeg-gaba-anesthesia` (MGH, credentialed **plus per-study contributor review**); `eeg-power-anesthesia` (derived spectra only); `propofol-anesthesia-dynamics`; `inspire`; `i-care` (already known) |
| BDSP, 10 projects | no anaesthesia at all. Mostly epilepsy, critical care and sleep. **LENS** — "Lifespan and Sleep-Stage-Resolved Normative EEG Background" — is a genuine normative reference for the age question in E16/E17, and is credentialed |
| `meagmohit/EEG-Datasets` | nothing relevant |

**VitalDB: 6,388 surgical cases, CC-BY 4.0, no credentials.** Verified against the API, not the paper:

| track | cases | why it matters |
|---|---|---|
| `BIS/EEG1_WAV`, `BIS/EEG2_WAV` | **5,871** | **raw EEG**, 128 Hz, microvolts — verified by download (Δt = 0.0078125 s, sd ≈ 34 µV) |
| `BIS/BIS` | 5,867 | **the conventional monitor Challenge C must beat** |
| `BIS/SR` | 5,569 | suppression ratio — burst suppression, scored by the device |
| `BIS/EMG` | 5,577 | **a real muscle channel**, not a spectral proxy |
| `Orchestra/PPF20_CE` | **3,511** | propofol, effect-site concentration |
| `Primus/INSP_SEVO` | **3,687** | **sevoflurane** |
| `Primus/INSP_DES` | **2,046** | **desflurane** |

**Challenge A was blocked because there was no second identified drug. There are now three**, in thousands of
cases, on one monitor at one site — and the drug-identity probe the challenge requires is not a proxy but the
agent's own concentration track. **Challenge C was blocked because no deposit carried both EEG and a monitor
to be ahead of.** VitalDB carries both, plus `anestart`/`aneend`, and real covariates (age, sex, BMI, ASA,
emergency status) where ds004541's `participants.tsv` is entirely `n/a`.

**A muscle probe better than anything this project has had.** `intraop_rocu` and `intraop_vecu` record
neuromuscular-blocker dose. A paralysed patient cannot generate EMG, so a candidate whose value tracks NMB
dose at fixed anaesthetic depth is reading muscle — tested against an administered drug rather than against
the spectral proxies §9.15 found two of disagreeing in sign.

**THREE LIMITS, EACH MEASURED RATHER THAN ASSUMED.**

1. **Induction is not in the recording.** `anestart` is negative in **91.8 %** of cases: the BIS sensor goes
   on after the patient is already asleep. **The transition VitalDB contains is EMERGENCE, not induction** —
   `aneend` sits at a median 9,770 s into the record. The adapter anchors on `aneend` for that reason, and
   **ds004541 remains the only deposit that can speak to loss of consciousness.**
2. **128 Hz means Nyquist 64**, so `exponent_gamma` (50–90 Hz) is NaN here by design — the same graceful
   degradation it shows on Sleep-EDF. `exponent_high` (20–40 Hz) is unaffected.
3. **Two frontal channels only** (a BIS sensor strip), so `uce_v1`, which needs frontal *and* posterior 10-20
   names, is unavailable.

**Two adapter bugs caught by checking rather than by trusting the format.** The `cases` endpoint begins with
a **BOM**, which silently renames the first column to `﻿caseid` and makes every `caseid` lookup a
KeyError. And **`subjectid` is not `caseid`**: 237 of 6,388 cases share a patient with another case and one
patient has eight, so clustering on the case would have treated repeat surgeries as independent and narrowed
every interval. The adapter clusters on the patient.

### 9.27 BDSP credentials verified, and what they actually reach

**Working, and rule 36 reproduced exactly.** `sts get-caller-identity` through the `physionet` profile returns
`arn:aws:iam::281627750420:root`. The same call with the sandbox's injected `AWS_ACCESS_KEY_ID` in place
returns `InvalidClientTokenId` — a failure indistinguishable from expiry, which is why anything touching
these must drop the two stub variables first. `scripts/heedb_run.sh` exists for exactly that and should be
used rather than reimplemented.

**The three endpoints are ACCESS POINTS, not buckets** (account `184438910517`), so the full ARN goes in the
`Bucket` parameter; using the bare name returns `NoSuchBucket` and reads like a permissions problem.

| access point | 64 top-level prefixes in total |
|---|---|
| credentialed | `EEG/` (`HEEDB_Metadata/`, **`bids/` holding 12 datasets**, `eeg-metadata/`), `PSG/`, `EHR/`, `OMOP/`, `ECG/`, `Imaging/`, `NAX/` |
| restricted | **`i-care/`**, **`burst-supression/`** (86 `.mat`), `caisr/`, `sparcnet/`, `sah/`, `e-cam-s/`, `cyclops/`, +12 |
| projects | 37, including `ceeg-multimodal-cardiac-arrest/`, `hie-eeg-prognostics-1000/`, `icu-sleep/`, `sleepFM/`, `morgoth1/`, `eeg-spectrogram-atlas/` |

**I-CARE is the Challenge C route, and it is the first thing reachable that fits the requirement.** Files are
per-patient hourly segments — `0284_001_004_EEG.mat` at ~60 MB, with matching `_ECG` and `_OTHER` — giving
**serial per-patient EEG across days in comatose post-cardiac-arrest patients**. §5 blocked Challenge C on
exactly this ("serial per-patient EEG with a monitor comparator") and §9.22 narrowed the blocker to data
alone once layer 5 was built. **48.6 GB across only 15 patient directories sampled**, so the corpus is large
and any use of it needs a bounded, resumable subset rather than a bulk pull.

**`EEG/bids/Neurotech/` is the path that shows only a LICENSE file anonymously.** With credentials it is
**4,915 subjects**, EDF+ at 256 Hz on a 10-20 montage, with Natus/Xltek annotations and a `phenotype/`
directory. Licence **CC BY-NC 4.0**; authors include Westover and Goldenholz. Dates are shifted per patient
and **times of day are preserved**, which matters for any circadian or time-of-day analysis.

    TWO LIMITS, MEASURED FROM participants.tsv RATHER THAN ASSUMED. `age` is present for **2,691 of 4,915**
    subjects and `sex` for **2,213** — roughly half the cohort has no demographics at all. And the age
    distribution is paediatric (modal ~8–14), so it overlaps HBN and would **inherit the same
    adult-calibrated-band problem** that failed E16's gate: a fixed 8–12 Hz alpha band does not contain a
    young child's posterior dominant rhythm.

**What this does NOT unblock: Challenge A.** Nothing in BDSP is anaesthesia with an identified agent, so
VitalDB remains the only route to a multi-drug contrast. What it does unblock is Challenge C, and it supplies
a genuinely unresponsive clinical population while the Bath request is pending.

### 9.28 HBN is closed: two gates failed, and the pre-commitment is honoured

**E16's gate** required alpha blocking — `relative_alpha_power` higher eyes-closed — in ≥ 80 % of subjects.
Measured **57.1 %**. **E17's gate**, band-free by design so it could not inherit the adult-band defect,
required `spectral_entropy` lower eyes-closed in ≥ 80 %. Measured **56.6 %** on the complete 272-row table.

**E17 registered one attempt and that commitment is now spent.** No third gate is tried. A sequence of gates
tried until one passes is a search over gates, and it would make any eventual pass meaningless.

**So nothing about `exponent_high` is reported from HBN, and P2/P3/P4 were never computed** — the scripts
exit before touching any age association. That is not a technicality: the age question remains genuinely
open and untainted, testable on a different cohort by a clean pre-registration rather than by a fourth
framing of this one.

**What was learned along the way, and it is not nothing:**

* **A real adapter bug**, found by two gates rather than by inspection. HBN's resting run ends on an
  eyes-open instruction; `blocks_from_events` returned that final block unbounded, and "the longest block"
  therefore selected ~35 s of **post-protocol recording** as every subject's eyes-open window. Fixing it
  moved the band-free gate from 46.3 % to 56.6 % — a real improvement that still does not reach the bar.
  The general lesson is regression-tested: **"take the longest block" silently prefers whichever block is
  least well defined**, because an unbounded interval is always the longest.
* **A finding about the registry rather than about HBN.** `relative_alpha_power` carries a fixed adult
  8–12 Hz band everywhere it is used, and a young child's posterior dominant rhythm is slower than that. The
  cohort's median age is 9.7.
* **A correction to my own reasoning, recorded in E17's header.** I wrote that the monotone age gradient in
  alpha blocking could not come from a broken pipeline. That was wrong — a broken pipeline can produce an
  age-monotone artefact if the breakage interacts with age, and older children plausibly move less after a
  protocol ends. That gradient came from the invalid windows and was withdrawn.

**Where the age question goes instead.** It needs a cohort whose alpha sits where an adult band expects it,
or a per-subject individualised band. **Neurotech (§9.27) is NOT the answer** — 4,915 subjects but modal age
8–14, so it inherits the identical defect. **LENS on BDSP — "Lifespan and Sleep-Stage-Resolved Normative EEG
Background" — is the right shape**, being lifespan rather than paediatric, and is the deposit to pursue.

### 9.29 E21's gate fired at 4.5 % and it was right: BIS 0.0 is the sensor's off-state

**E21 is closed at its gate.** It required BIS to rise from the unresponsive block to the responsive block
in ≥ 80 % of cases and got **1 of 22 (4.5 %)**. P2–P4 were never computed. The gate did what a gate is for,
and the failure was in the extraction, not in any candidate.

* **`BIS/BIS` writes a literal `0.0` while the strip is detached, and 0 is inside the index's valid range.**
  171 of 348 decoded windows carried it, rising from 11 % at `aneend−1200` to 92 % at `aneend+300` because
  the sensor comes off with the anaesthetic. Read as a measurement it says *isoelectric* — the deepest
  possible state — so the emerging arm scored as more suppressed than maintenance and the comparison
  inverted. `BIS/SQI` reads exactly 0 over precisely those spans (verified on cases 30 and 35) and is a
  positive test for the off-state; it was available and was not streamed. **Error-catalogue rule 6 in a new
  dress: the column was populated, and that is not the same as valid.**
* **`aneend` lags emergence rather than marking it.** BIS is already 68–86 at `aneend−300`/`−120` while deep
  maintenance sits at 24–46. It is charted when the anaesthetic record is closed, after the patient is
  responding. The registered positive offsets therefore landed after the monitor was unplugged — which is
  also why they carried most of the decode errors, a signal E21's own scope note saw and misread as short
  recordings alone.
* **A bug in E21 that behaved correctly.** Its first version selected epochs by `meta_epoch`, a column the
  VitalDB adapter does not emit — ds004541's does, and the two were conflated. Every test matched the empty
  string and the gate saw 0 of 0 cases. It **failed** rather than passing vacuously, which is what rule 5
  asks for.

**What replaced it.** `VitalDBGridAdapter` samples the whole case on a fixed grid and carries `BIS/BIS`,
`BIS/SQI`, `BIS/SR` and `BIS/EMG` with every window, voiding all four when SQI shows the sensor off. It is
nearly free: the expensive operation is fetching a case's 9.4 MB waveform track, which is per case and not
per window, and the offset design left ~97 % of each fetched track unused. Sharding is by **case**, never by
window — the runner's own `--shard` hashes the recording id and would make each shard re-download every
case's track. Four case-shards: 9.5 h → 2.4 h.

**E22 is registered against that table and committed before it existed** (at 261 of ~6,700 rows, with its
own row-count floor refusing to report). Arms come from published clinical thresholds — BIS ≤ 60
unresponsive, ≥ 80 responsive, 60–80 excluded and counted — so nothing about the split is chosen from the
distribution. Its machinery gate uses **no EEG and no candidate**: coverage in ≥ 2 drug groups, plus
responsive windows occurring later in the case in ≥ 70 % of patients, which tests that the arms are not
*inverted* without asserting a precision the charted times do not have. Its headline limitation is stated as
one: BIS is computed from the same two frontal electrodes as the candidates, so P2 asks whether a candidate
agrees with the BIS algorithm. **P4 (the drug probe) and P5 (a placebo that gates the verdict) carry the
weight, and neither is damaged by that circularity.**

### 9.30 E20 withdrawn, and the defect behind it: 39 of 62 ds004541 channels are not EEG

E20's gate failed at 5 of 7 and the experiment stopped, as registered. **That verdict is now withdrawn as
uninterpretable — not overturned, and not replaced by a positive one.**

In one 30 s awake window of sub-02, **23 of 62 channels sit in a physiological 5–150 µV band and 39 do not**,
running from 1,600 up to 153,000 µV. `_mean_psd` averages power across all of them, and **the pipeline had
no channel-quality rejection of any kind.** In that window:

| | all 62 channels | the 23 plausible ones |
|---|---|---|
| relative delta | 0.799 | 0.456 |
| relative alpha | 0.021 | 0.092 |

An awake human with 2 % alpha has not been recorded. The whole table shows it — median relative alpha of
0.01 in **both** arms, against 0.42 on Chennu — and that flatness is why the gate had nothing to detect.

**The first diagnosis was wrong, and that is the more useful half.** The hypothesis was that one enormous
channel dominated the power sum, and the fix would be a robust aggregator: a per-frequency median across
channels. It moved relative delta by **0.007**, because on this deposit *the median channel is bad too*.
Robust aggregation defends against a minority of outliers; it cannot defend against a majority. High-pass
filtering does not touch it either (median-channel delta 0.687 → 0.651 at 1 Hz), so it is not drift leaking
into the 1–4 Hz bin. **Only rejecting channels helps.**

**Exposure, measured one window per deposit** (`scripts/diagnose_channel_spread.py`):

| deposit | plausible channels | verdict |
|---|---|---|
| ds005620 | 65/65 | unexposed — the `exponent_high` replication stands |
| vitaldb | 1/1 | unexposed — **E22 is safe**, it is one frontal channel |
| ds007554 | 29/33 | moderate: delta 0.819 → 0.729, alpha 0.018 → 0.028 |
| ds004541 | 23/62 | severe |
| chennu | **not probed** | the Cambridge host fails TLS from this sandbox (the E12 blocker). **Unmeasured, not clean.** |

**`features/quality.py`** is the first half of the repair: three tests, first-match-wins — `nonfinite`
(> 10 % of samples), `flat` (zero variance), `amplitude` (sd outside 5–150 µV). The band is **absolute
rather than relative and that is forced**: a scale-free "reject channels more than 10× the montage median"
needs no units and fails on exactly the case that motivated it. Anchoring to physiology means anchoring to
volts, so the test is only meaningful when the data really are in microvolts — and HBN declares
`"uncalibrated"`. `channel_quality` therefore **refuses to judge amplitude** when the units are not
microvolts, returning every channel kept with `units_judged=False`, so a caller can tell *every channel
passed* from *amplitude was never tested*. The flat test is unit-free and runs regardless.

**Nothing in the feature path calls it yet.** Turning it on changes the definition fingerprint of five
candidates and invalidates that column in every table already extracted — including Chennu's, which cannot
be re-extracted from this sandbox at all. That sequencing decision is open, and it is the next one to make.

**What this does not license, stated because the temptation runs the other way.** It is not grounds to
re-run E20 and keep whatever comes out; the one-attempt commitment was spent, and what a repaired pipeline
produces on ds004541 belongs to a new registration written *before* the repair runs. Nor is it evidence for
`exponent_high` — the deposit is untested on that question. Absent, not negative.

### 9.31 The sequencing decision on the channel filter, made explicitly rather than by default

`features/quality.py` exists and is tested. **Nothing calls it in the feature path, and that is a decision,
not an oversight.** Wiring it in has three costs that have to be paid deliberately:

1. **Definition drift on five candidates.** `relative_delta_power`, `relative_alpha_power`,
   `spectral_edge_95`, `spectral_entropy` and anything else routed through `_mean_psd` would change value.
   `stream_features` records a `definition_fingerprint` and refuses to resume a table across such a change,
   which is the guard working — but it means every affected table becomes v1 and needs re-extraction to
   become v2.
2. **One deposit cannot be re-extracted at all.** Chennu's host fails TLS hostname verification from this
   sandbox (§9.17). Results resting on it would be frozen at v1 with no way to check them against v2 until
   that host is reachable, and they must be labelled that way rather than quietly carried forward.
3. **Adding columns to the runner's field list breaks resumption of an in-flight table**, because
   `stream_features` refuses to append to a file whose column set differs. The VitalDB grid stream is
   running; changing the schema now would strand it.

**The decision: finish E22 on the current table first, then migrate.** The justification is measured, not
assumed — the channel-spread diagnostic found VitalDB **unexposed** (one frontal channel, 1 of 1 plausible),
so E22's input is not affected by the defect and running it now costs nothing in correctness. ds005620 is
likewise unexposed at 65 of 65, so the `exponent_high` replication does not move either.

**What the migration will be, when it happens.** Filter inside the runner, before candidates are called, so
every candidate sees the same channel set; record `n_channels_kept` and `frac_channels_kept` per row so the
exclusion is visible at analysis time rather than implicit; re-extract every reachable deposit; and mark
Chennu-derived numbers as v1-only. **`channel_quality` refuses to judge amplitude on non-microvolt data**,
so HBN passes through untouched and its rows will say so — `units_judged=False` is not the same as a clean
bill and the column must preserve the difference.

**What is NOT deferred.** ds004541 is unreadable by this pipeline today, and §9.30 already says no
experiment should be registered on it until the migration lands. That stands.
