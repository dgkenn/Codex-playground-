# Data acquisition search, formal-access-only — 2026-08-02

**No new dataset clears the bar.** Under the constraint stated below, exactly two deposits qualify for
Challenge B, and both were already known and already the subject of drafted requests before this search:
**Bath (BATH-01632, requested)** and **Chennu 2014 / WBIC (drafted, unsent)**. Every other candidate located
in this session — including two with the right construct and one with a far larger cohort — fails the
constraint on the same axis: the record's own published route is a **personal address of a corresponding
author**, not a data office, a DPO inbox, or an application form. This is a confirmed absence under the
stated rule, not a failure to look; the method and every dead end are recorded below so the negative is
auditable rather than asserted.

*Feasibility only. No registration, no ledger row, no bulk download.* Every claim below was produced by
`curl`/`urllib` against a real API or by NCBI E-utilities (`efetch.fcgi`/`esummary.fcgi`) and is quoted from
the raw bytes returned in this session — nothing here is carried over from an earlier document's quote
without being refetched and rechecked against the live source. `WebSearch` was used twice, only to surface
candidate names to go and verify directly (rules 25/39 forbid trusting its content) — every fact attributed
to a paper or a repository below was independently re-fetched via E-utilities or the repository's own API/
HTML after the search surfaced it.

---

## The constraint, applied

**IN SCOPE**: PhysioNet-style credentialed tiers; an institutional data-access portal with an application
form; a managed-access archive with a data office or DPO inbox that is the record's own published route;
registered-access schemes with a named review process.

**OUT OF SCOPE**: "available from the corresponding author on reasonable request"; any route whose only
named contact is a person's institutional email rather than an office, committee, or inbox; cold-emailing a
PI. The distinction is read from the **verbatim access statement**, not from a summary of it — several
candidates below look identical to an in-scope route until the actual sentence is read.

---

## Part 1 — the two IN-SCOPE deposits (both already known, both already actioned)

### 1. Bath prolonged-DoC MI-BCI dataset — DOI `10.15125/BATH-01632`

**Independently refetched this session** from `https://researchdata.bath.ac.uk/1632/` (HTTP 200, page
metadata parsed directly, not summarised):

> *"Access to these data is restricted due to the specialised clinical nature of the participant cohort and
> the specific methodological context in which the data were acquired. The dataset is intended for use by
> bona fide researchers conducting research in areas such as disorders of consciousness, brain–computer
> interfaces, or clinical neurophysiology. Access will be granted upon reasonable request, subject to review
> by the data custodians. Requests should include a brief description of the proposed research use, evidence
> of relevant ethical approval, and agreement to data use conditions that prohibit data redistribution or use
> beyond the approved scope. … Requests for access should be directed to the corresponding data custodian and
> will be considered on a case-by-case basis."*

**IN SCOPE** — this is the institutional research-data archive's own published route (`researchdata.bath.ac.uk`,
an EPrints instance with a formal request mechanism and a named custodian review step), not a personal email
to Prof. Coyle, even though he is also listed as corresponding author. It has an "access request" record type
distinct from open download, which is exactly the registered-access shape the constraint asks for.

**Cohort** (parsed from the same page's `DC.description`): registered under `NCT03827187` ("Awareness
Detection and Communication in Disorders of Consciousness," lead: University of Ulster, status RECRUITING,
enrollment estimated 30, `ipdSharing: UNDECIDED` — reverified live against `clinicaltrials.gov/api/v2/studies/NCT03827187`
in this session). **N = 42**: UWS 14, MCS 17, LIS 11, plus 2 able-bodied benchmark participants. EEG recorded
during structured motor-imagery BCI sessions cued auditorily, with session-linked CRS-R and WHIM scores.

**Command-following outcome**: the MI-BCI classifier's trial-level detection of motor-imagery-driven
command-following, computed from the EEG itself — independent of the CRS-R/WHIM bedside scores, which are
available as the candidate incumbent (an *observation*, so rule 86 risk is non-zero but lower than HEEDB's,
since CRS-R/WHIM are not simultaneous with the MI-BCI task in general; time-since-injury is available as a
genuinely exposure-like covariate).

**New in this session**: the record now lists a live companion publication, `10.1038/s43856-026-01574-x`,
*"Advancing EEG-based assessment of consciousness and cognition in prolonged disorders of consciousness"*
(*Communications Medicine*, published 2026-04-17, confirmed via CrossRef API, du Bois/Korik/Hodge et al.) —
the dataset is actively maintained and being published on, not a static one-off deposit.

**Status**: per `DECISIONS_2026_08_02_LINES_AND_BLOCKERS.md`, the request "has just been requested." This
document does not change that status; it re-verifies the target is real and current.

### 2. Chennu et al. 2014 (WBIC) — PMID 25329398, PMC4199497

**Independently refetched this session** via `efetch.fcgi?db=pmc&id=4199497`, `custom-meta id="data-availability"`,
parsed directly from the XML (not summarised):

> *"The authors confirm that, for approved reasons, some access restrictions apply to the data underlying the
> findings. Data cannot be made available publicly as they are subject to UK/EU confidentiality and ethical
> consent regulations applicable to sensitive clinical information. However, data are available by request to
> either the study authors or the Wolfson Brain Imaging Centre's data protection officer
> (enquiries@wbic.cam.ac.uk) for researchers who can meet the requisite ethical criteria for access to
> confidential UK National Health Service patient data. All requests will be subject to case-by-case review by
> the WBIC's data access committee."*

**IN SCOPE via the DPO/data-access-committee route** (`enquiries@wbic.cam.ac.uk`) — a functional inbox
belonging to a named institutional office with a stated committee review, exactly the pattern the constraint
carves out as in scope even though the same sentence also offers an author-mediated alternative. Route the
request to the DPO address, not to a named author, to stay unambiguously on the in-scope side.

**Cohort**: 32 patients, 10-minute 128-channel resting (task-free) EEG, Table 1 carries per-patient etiology,
diagnosis, CRS-R total, and **two independently-scored command-following columns** (behavioural CRS-R
command-following and fMRI-based command-following) — including at least one patient (P3) who is behaviourally
negative but fMRI-positive, the textbook cognitive-motor-dissociation case.

**Command-following outcome**: fMRI-based command detection, genuinely independent of the CRS-R behavioural
score — the cleanest rule-86 escape of anything found in this entire search, on either pass.

**A same-custodian extension worth adding to the same email, verified this session**: Chennu et al. 2017,
*"Brain networks predict metabolism, diagnosis and prognosis at the bedside in disorders of consciousness"*
(PMID 28666351, *Brain* 140(8):2120-2132, abstract refetched via `efetch.fcgi` this session), same WBIC group,
**104 patients**, resting high-density EEG, correlating network measures with behavioural diagnosis
(UWS/MCS/EMCS/LIS), PET metabolism and 1-year outcome. No PMC full text is indexed for this record
(`elink.fcgi` returns only `pubmed_pmc_refs`, i.e. citing papers, not the article's own PMC copy — checked and
reported as a negative rather than assumed), so its access statement could not be independently quoted, but it
shares WBIC/Cambridge as the data custodian. **This is not a new independent source** — it is the same DPO —
but the drafted email should ask for both cohorts, since the 2017 series is 3× the size, even though its
published outcome variable is diagnosis/PET/1-year-outcome rather than a direct command-following column and
would need to be checked against WBIC's raw records once access is granted.

**Status**: per `DATA_REQUEST_WBIC_CHENNU.md` and reverified by this session's `git log` equivalent check
against the existing file header, **drafted 2026-07-30, still unsent.** This is the single highest-leverage
unsent action for Challenge B under the new constraint, precisely because it is unambiguously in scope and
nothing else found here is.

---

## Part 2 — candidates found, and why each fails or does not add a new source

### 3. Pan, Xie, Qin, Li et al. 2020 — PMID 32101603, *Brain*, PMC7174053

*"Prognosis for patients with cognitive motor dissociation identified by brain-computer interface."*
South China University of Technology / Southern Medical University group (Guangzhou), independent of WBIC/
Bath/Columbia. **N = 78** disorders-of-consciousness patients with **no observable command-following at the
bedside** (45 UWS + 33 MCS, diagnosed by CRS-R) — every one underwent an **EEG-based BCI item-selection
task** (choose a photograph or number from two candidates). 34 of 78 (44%) showed significant BCI accuracy
("CMD patients"). **This is structurally the best-matching construct found anywhere in this search**: a
command-following outcome scored entirely by the EEG classifier, in patients selected specifically for having
*no* bedside command-following to confound it with.

**Independently fetched this session**, `efetch.fcgi?db=pmc&id=PMC7174053`, `sec-type="data-availability"`:

> *"The data that support the findings of the current study are available from the corresponding author on
> request from qualified researchers for non-commercial research purposes. A material transfer agreement may
> be required."*

**OUT OF SCOPE.** No office, no DPO, no named committee — "the corresponding author," full stop. The MTA
detail does not change the classification; a material transfer agreement negotiated with a named individual
is still an author-mediated request. Excellent construct, wrong route.

### 4. Della Bella, Sitt, Bekinschtein, Barttfeld et al. 2025 — PMID 40796934, *Communications Biology*, PMC12344011

*"Detection of EEG dynamic complex patterns in disorders of consciousness."* 237 acute/chronic DoC patients
across 3 centres (this is the deposit already on record as `DEPOSIT_ACCESS_STATUS.md`'s fallback #1).
**Reverified independently in this session, two ways.**

Public table, `https://api.osf.io/v2/nodes/nfwyj/files/osfstorage/` (fetched live): exactly two files exist,
`table1.ods` (23,516 bytes) and `Supplementary information.pdf` (488,924 bytes) — **no EEG signal file of any
kind**, confirming this is a demographics/summary table, not a usable EEG deposit, before the access question
even arises.

Raw-EEG access statement, `efetch.fcgi?db=pmc&id=PMC12344011`, `notes-type="data-availability"`:

> *"The numerical source data behind the figures are available in Figshare. The patient data that support the
> findings of this study are not openly available due to reasons of sensitivity and are available from the
> corresponding author upon reasonable request."*

**OUT OF SCOPE** on the raw EEG (author-mediated, no office named) — and even if it were in scope, the public
per-patient table carries **CRS-R total**, not a command-following subscore or an fMRI/BCI-scored outcome, so
it fails construct (b) independent of the access question (consistent with the prior finding in
`CONSOLIDATION_2026_08_02_CHALLENGE_B.md` fallback #1, now reverified rather than only cited).

### 5. Bodien, Edlow, Claassen, Schiff, Sitt, Naccache, Owen et al. 2024 — PMID 39141852, *N Engl J Med* 391:598-608, PMC7617195

*"Cognitive Motor Dissociation in Disorders of Consciousness."* The largest and most directly on-construct
cohort found in this search: a **6-site prospective consortium — MGH/Spaulding, the Wolfson Brain Imaging
Centre (Cambridge), the Coma Science Group (Liège), Columbia/Weill Cornell (Claassen, Schiff), the Paris
Brain Institute (Sitt, Rohaut, Naccache), and Western Ontario (Owen)** — task-based fMRI and/or EEG,
**N = 353** analysed of 478 in the pooled "central database." Cognitive motor dissociation (a command
response on fMRI/EEG with none observable behaviourally) was found in 60 of 241 (25%) of participants without
an observable bedside response — the outcome scored by the imaging/EEG classifier, independent of the CRS-R
diagnosis used to select the cohort.

**Investigated for a formal access route and none was found.** The PMC full-text XML for this record (fetched
in full, 102 KB, body text present through the final results table) contains **no data-availability or
data-sharing section at all** — checked for `"Data Sharing"`, `"data-availability"`, `"FITBIR"`,
`"repository"`, `"ClinicalTrials"`, `"NCT0"`, `"Curing Coma"`, all absent. NEJM's own article page
(`nejm.org/doi/10.1056/NEJMoa2400645`) returned **HTTP 403** to a direct `curl` in this session (paywalled,
not fetchable without a subscription — reported as a measured status, not inferred). `clinicaltrials.gov`
title and sponsor-name searches for this specific consortium returned **no matching registration**
(`query.titles=cognitive+motor+dissociation` returns one unrelated stroke study; `query.term="cognitive motor
dissociation" Bodien` returns zero). **Verdict: NOT ACTIONABLE under this constraint** — not because it is
confirmed author-mediated (unlike #3 and #4, no verbatim statement was recovered either way), but because no
office, portal, or DPO route could be found to point a request at, and every site with an identifiable
mechanism (Cambridge = WBIC, already being pursued as #2) is a route already accounted for elsewhere in this
list rather than a new one. Listed here so a future session does not re-discover the paper and assume it is
untried; the DOI is `10.1056/NEJMoa2400645`.

### 6. Di Gregorio, La Porta, Petrone et al. 2022 — PMID 36009445, pilot study; data at Zenodo `10.5281/zenodo.6951440`

*"Accuracy of EEG Biomarkers in the Detection of Clinical Outcome in Disorders of Consciousness after Severe
Acquired Brain Injury."* AUSL di Bologna / IRCCS ISNB / UNIBO. **Fully open — no request of any kind needed**,
confirmed by fetching the Zenodo record directly: `"access_right": "open"`, CC-BY-4.0, four raw `.edf` files
(`02^01.edf`, `04^01.edf`, `19^01.edf`, `32^01.edf`, 15–28 MB each) downloadable with no authentication.

**Not IN SCOPE vs. OUT OF SCOPE — moot, because it fails on construct and size before access is even a
question.** The paper's own abstract (refetched this session) states the outcome is **clinical outcome at 6
months post-injury**, not command-following, predicted from EEG functional connectivity and dominant
frequency in a cohort of 33 patients — and only **4 of those 33 patients'** raw recordings were actually
deposited (checked directly: exactly 4 files). Recorded here because it is the one candidate in this entire
search that is more open than any "formal access" route, and because a future search should not re-find it
and assume the small file count means the search failed rather than that the deposit itself is a 4-patient
preliminary release.

---

## Part 3 — repositories searched with no usable result (dead ends, reported rather than omitted)

Per rule 5, a search that returns nothing must show the filter was capable of matching something, or be
reported as an inconclusive negative rather than a confirmed one. All four below are the latter.

- **NITRC** (`nitrc.org/search/`): the search endpoint returns HTTP 200 with a static results shell for every
  query tried (`coma`, `consciousness`, `vegetative`, `eeg`) and the parsed HTML contains no project links in
  any case, including the sanity-check term `eeg`, which should self-evidently return hits on a neuroimaging
  tool/data catalogue. **This reads as the search UI requiring JavaScript/session state `curl` cannot
  provide, not as zero NITRC EEG/DoC projects existing.** Unresolved; flagged rather than reported as absence.
- **EBRAINS Knowledge Graph** (`search.kg.ebrains.eu`): `/instances/Dataset` returns HTTP 200 but is a
  single-page JS application (Angular bootstrap HTML only, confirmed by inspecting the returned bytes); every
  REST-shaped guess (`/api/instances`, `/api/groups/public/instances`, `/api/groups/public/search/Dataset`)
  returned 404. `core.kg.ebrains.eu/v3-beta/queries` returned 401 (authenticated API, as expected). **Not
  searched — no anonymous API endpoint was found in the time budgeted for this**, not a finding of zero
  matches.
- **FITBIR** (`fitbir.nih.gov`): the site is reachable (HTTP 200) but no public study-search API endpoint was
  found by guessing (`/dictionary/publicData/getStudy`, `/rest/rSearch/getStudy` both 404). Cross-checked
  indirectly via `clinicaltrials.gov`: searching registered trials for `FITBIR` combined with `coma`,
  `EEG`, or `disorders of consciousness` returned no DoC/EEG study naming FITBIR as its repository (one
  DoD-funded vestibular-rehabilitation trial, `NCT06819904`, does use FITBIR, confirming the mechanism is
  real and reachable by other studies — just not, as far as this search found, by an EEG/command-following
  one).
- **UK Data Service** (`ukdataservice.ac.uk`): reachable, but its catalogue is ESRC-funded social/economic
  survey data by mandate; no API endpoint for the beta catalogue could be reached in this session
  (`beta.ukdataservice.ac.uk` search calls returned 404), and the domain mismatch (clinical EEG is not its
  remit) makes a null result unsurprising rather than diagnostic either way.
- **University of Birmingham UBIRA eData** (`edata.bham.ac.uk`, checked because Damian Cruse — the
  Lancet 2011/2012 command-following-BCI-in-DoC author — is based there): search API works (confirmed
  returning real, on-topic hits for other terms), but `consciousness`, `vegetative state EEG`,
  `disorders of consciousness EEG`, and `brain injury EEG` all return **zero** results, and `command
  following` returns twelve results that are all off-topic false positives on generic word overlap
  (verified by title). **This is a confirmed negative**, not a search-mechanism failure — the search
  demonstrably works on other queries, and Cruse's DoC-BCI datasets are not deposited there.
- **Zenodo / Dryad / Figshare / OSF**, general DoC-EEG-command-following keyword sweeps beyond the specific
  papers above: returned nothing on-construct beyond items #3–#6, already covered.

---

## Bottom line

Under the formal-access-only constraint, **Challenge B has exactly two qualifying targets and both were
already identified before this search.** The one actionable finding this session adds is not a new dataset:
it is that the **Chennu 2014 WBIC route should be pointed at the DPO inbox specifically** (verified this
session to name an actual "data access committee," which is a stronger in-scope signal than the earlier
draft's characterisation), and that the request, when sent, should ask for **both** the 2014 (n=32,
command-following-labelled) and 2017 (n=104, larger but not command-following-labelled as published) WBIC
cohorts in one message, since they share a custodian. Two structurally excellent candidates — the 78-patient
BCI-scored CMD cohort (#3) and the 353-patient six-site consortium (#5), the latter of which even includes
WBIC as one of its sites — were found and are recorded here specifically so a future session does not
re-discover them and mistake "found a great cohort" for "found a route": #3's own paper states its access
route in one unambiguous author-mediated sentence, and #5's has no recoverable access route of any kind under
this search's method. **Sending the Chennu email and confirming/actually filing the Bath request (per
`DECISIONS_2026_08_02_LINES_AND_BLOCKERS.md`, already in progress for Bath) remain the only two moves that
change Challenge B's data situation** — this search does not add a third.
