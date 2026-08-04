# Data acquisition search: a within-subject propofol-vs-volatile-agent EEG deposit

*2026-08-02. Feasibility search only — no registration, no data pulled. Every deposit claim below is from a
`curl`/`urllib` call against the real API or from NCBI E-utilities, quoted from the raw bytes seen. No
WebFetch was used on any manifest, listing or bibliographic record (rules 25, 39).*

## Why this search

E227/E229 (see `NOTE_CHALLENGE_A_REFRAMED.md`, CORRECTION / SECOND CORRECTION / THIRD CORRECTION) established,
twice, on VitalDB: across a panel of 15 EEG measures, 10 of 11 that clear a donor-exposure null move in the
**same** direction with propofol effect-site concentration and with sevoflurane end-tidal concentration, and
exactly one — `relative_alpha_power` — moves oppositely (+0.1189 propofol / −0.2482 sevoflurane, exact
binomial p = 0.0059 for the direction split). This is a **between-patient** comparison (propofol-only cases
against sevoflurane-only cases), and E228 already tried and failed to convert it to within-patient using
VitalDB's 31 genuinely-combined cases (17 with both exposures varying, 1 with a usable epoch of each — see
`PROBE_2026_08_02_CROSSOVER.md`). **The reversal has never been tested within a subject and VitalDB cannot do
it.** This document is the search for a deposit that can.

## Part 1 — this project's own record, searched first (rule 50's corollary)

`grep -rniE "crossover|xenon|dexmedetomidine|isoflurane|desflurane|two agents"` over `bsde/docs/` and the
registration ledger turns up an extensive prior effort, not a gap. Summary, with conclusions as recorded:

| document | what it found | conclusion on record |
|---|---|---|
| `QUEUE.md` Q8/Q9 | Searched PubMed, OpenNeuro, Dryad, Zenodo, OSF, Figshare, PhysioNet for a deposit pairing EEG with two mechanistically distinct anaesthetics **in the same patients**. | "No public deposit located pairs raw EEG with two mechanistically distinct anaesthetics in the same patients." (Q9) |
| Krause/Banks deposit (Zenodo `10.5281/zenodo.15497531`, used in E35/E36) | 34 epilepsy-surgery patients: 19 propofol, 10 dexmedetomidine, 24 natural sleep, intracranial. | **0 of 29 patients share both drug arms** — disjoint by construction, not a crossover. |
| `PROBE_2026_08_02_CROSSOVER.md` (E228, same day as this search) | VitalDB's 58 "propofol\|sevoflurane"-labelled cases, decomposed by NSRI potency share. | Median within-case span of dominant-agent share = **0.000**; only 3 cases cross a strict 0.2/0.8 dominance threshold; within-patient alpha diff on those 3 is +0.0058 [−0.148, +0.088], no information. **"The within-patient agent contrast is not available in VitalDB and this route is closed."** |
| `DATA_REQUEST_TURKU_KALLIONPAA.md` | Kallionpää 2020 (PMID 32773216, `NCT01889004`), 47 volunteers, dexmedetomidine (n=23) or **propofol** (n=24), within-subject LOR/ROR. | Drafted 2026-07-31, **still unsent**. Recorded as "the cohort that has the design" for a *different* adversarial pair (alpha-2 agonist vs GABAergic), not IV-vs-volatile. |
| `DEPOSIT_ACCESS_STATUS.md` | Five-cohort table (Krause / MGH OR / MGH volunteers / VitalDB / ds004541), each scored on non-EEG state label × real agent contrast × awake baseline × recovery. | **"No row has three ticks."** MGH OR ("multimodal-surgery-anesthesia" on PhysioNet) is "propofol vs propofol+sevo, 25 vs 14 — weak", explicitly a **between-case**, not within-subject, comparison. |
| `LITERATURE_MAP.md` §0 | Colombo 2019 (PMID 30639334) and Sarasso 2015 (PMID 26752078): propofol, xenon, ketamine dissociation design. | **"Three groups of healthy participants, n = 5 each"** — quoted from the project's own note — i.e. **between-subjects**, one drug per group, not a crossover. |
| `CONSOLIDATION_2026_08_02b.md` | Consolidates E212–E222. | **"Challenge A needs a crossover cohort or it needs to stop. The identified claim is within-case and the between-agent question is not answerable with what exists publicly."** |

**Conclusion of Part 1: this exact question has already been asked and searched twice today (E228's probe,
and the standing Q8/Q9 record), and the verdict on record is that no public deposit satisfies it.** Part 2
is a fresh, independent check of that verdict — repeating the search rather than trusting the prior negative
outright (rule 20-adjacent: re-derive, don't just cite).

## Part 2 — fresh search, 2026-08-02, this session

### OpenNeuro (GraphQL, full pull — `curl` against `https://openneuro.org/crn/graphql`)

Paginated `datasets(modality: "eeg", first: 100, ...)` over **all 447 EEG-tagged datasets** currently on
OpenNeuro (raw JSON parsed, not summarised by a fetch tool). Keyword scan of each dataset's `id` and
`description.Name` for `propofol|sevoflurane|isoflurane|desflurane|xenon|anesthesia|anaesthesia|anesthetic|
ketamine|dexmedetomidine` returns exactly **two** hits:

```
ds004541 | Multimodal EEG-fNIRS data from patients undergoing general anesthesia
ds005620 | A repeated awakening study exploring the capacity of complexity measures to capture dreaming during propofol sedation
```

Both are single-agent (propofol only; ds004541's agent is not specified in the title and this project has
already extracted it — one agent, no second-drug contrast). **Zero of 447 EEG datasets on OpenNeuro combine
two anaesthetic agents in their title/description**, consistent with — and a fresh confirmation of — Q8's
conclusion. (`ds003380`, the 1-subject isoflurane pig recording already known to this project, is tagged
`ieeg` rather than `eeg` and does not appear in this pull; it is single-agent regardless.)

### Zenodo (REST API, `https://zenodo.org/api/records`)

- `propofol AND sevoflurane AND EEG` → **3 hits**, none an EEG dataset (a BIS-vs-end-tidal-gas clinical
  study record, a paediatric sedation review, and a philosophy-of-consciousness preprint).
- `(isoflurane OR desflurane) AND propofol AND EEG` → **2 hits**, the same two irrelevant records.

### Dryad (`https://datadryad.org/api/v2/search?q=propofol+sevoflurane+EEG`)

`"count": 0`. Nothing.

### Figshare (`POST https://api.figshare.com/v2/articles/search`, `"search_for":"propofol sevoflurane EEG crossover"`)

Empty list, `[]`.

### OSF (`https://api.osf.io/v2/nodes/?filter[title]=propofol`)

16 total nodes titled with "propofol"; browsed in full. All are protocols, meta-analyses or unrelated
studies (ketamine/opioid sedation reviews, memory-consolidation experiments, a cancer-surgery outcomes
review). None is an anaesthetic-agent-contrast EEG dataset.

### PhysioNet (already resolved in `DEPOSIT_ACCESS_STATUS.md`, re-verified by HTTP status this session)

`eeg-gaba-anesthesia`, `multimodal-surgery-anesthesia`, `propofol-anesthesia-dynamics`, `eeg-power-anesthesia`
all return HTTP 200 at their versioned path (`/1.0.0/` or `/1.0/`) — none blocked at the project-listing
level. Per the existing record: `eeg-gaba-anesthesia` is propofol-only and DUA-gated (403 on file access);
`multimodal-surgery-anesthesia` ("MGH OR") is a **between-case**, not within-subject, propofol-vs-combined
comparison (25 vs 14 different surgical cases); `propofol-anesthesia-dynamics` has no EEG at all, autonomic
signals only.

### Literature: the one real match, found and verified via NCBI E-utilities and ClinicalTrials.gov API

Searching PubMed for `propofol AND sevoflurane AND crossover AND EEG` returns **8 records**; the one that is
an actual crossover PK/PD study (not a review) is **PMID 31567365**:

> **Title (literal, from the E-utilities XML):** "Population Pharmacodynamics of Propofol and Sevoflurane in
> Healthy Volunteers Using a Clinical Score and the Patient State Index: A Crossover Study." *Anesthesiology*
> 2019;131(6):1223-1238. Kuizenga MH, Colin PJ, Reyntjens KMEM, Touw DJ, Nalbat H, Knotnerus FH, Vereecke HEM,
> Struys MMRF. MeSH: **Cross-Over Studies**.
>
> **Methods, quoted literally:** *"This is a reanalysis of previously published data. Volunteers received
> four anesthesia sessions, each with different drug combinations of propofol or sevoflurane, with or
> without remifentanil."*

This is a genuine same-subject, two-agent design. Tracing the parent trial:

- **PMID 29452809** ("Test of neural inertia in humans during general anaesthesia"), same group, quotes:
  *"Thirty-six healthy volunteers received four sessions of anaesthesia with different drug combinations in
  a step-up/step-down design. Propofol or sevoflurane was administered with or without remifentanil… Loss and
  return of responsiveness (LOR-ROR), response to pain (PAIN), Patient State Index (PSI) and spectral edge
  frequency (SEF) were modeled."* Registration: **`NCT02043938`**.
- **PMID 33315176** ("Frontal electroencephalogram based drug, sex, and age independent sedation level
  prediction using non-linear machine learning algorithms"), same group, quotes: *"Forty-four quantitative
  features estimated from a pooled dataset of 204 EEG recordings from 66 healthy adult volunteers who
  received either propofol, dexmedetomidine, or sevoflurane… Clinical trial registration: NCT02043938 and
  NCT03143972."* This confirms **raw/continuous EEG, not only the derived PSI/SEF indices, was digitised and
  analysed** by this group — the feature set it names (44 quantitative EEG features) cannot be computed from
  a scalar index alone.

**Trial registry, queried directly (`https://clinicaltrials.gov/api/v2/studies/NCT02043938`, JSON parsed):**

```
officialTitle: "Study of the Cerebral Effects of Sevoflurane, Propofol and Remifentanil as Measured by
                the Spontaneous Electro-encephalogram"
overallStatus: COMPLETED
leadSponsor:   {"name": "Masimo Corporation", "class": "INDUSTRY"}
enrollment:    {"count": 46, "type": "ACTUAL"}
ipdSharingStatementModule: {"ipdSharing": "NO"}
```

**This is the design the project needs — same volunteers, propofol AND sevoflurane, spontaneous EEG
recorded throughout — and it is closed by an explicit registry statement, not by a search failure.** The
trial is industry-sponsored (Masimo, maker of the Patient State Index monitor); the equipment-validation
framing and the "NO" on IPD sharing are consistent with the underlying EEG being treated as sponsor data
rather than a research deposit. It has never surfaced in this project's OpenNeuro/Zenodo/Dryad/Figshare/OSF
searches because **it was never deposited anywhere a repository search would find it** — it lives only in
the trial registry and the papers that reanalyse it. Q9's note that *"a registered crossover study … may
have deposited data under a title no repository search would surface"* predicted exactly this outcome.

For comparison, the same query run against **`NCT01889004`** (Turku/Kallionpää, already the subject of the
drafted, unsent request) returns `ipdSharingStatementModule: None` — no stated refusal, just nothing on
record, which is consistent with an academic (University of Turku) rather than industry sponsor and leaves
the drafted request a live option in a way NCT02043938's explicit "NO" does not.

## Ranked shortlist (max 6), FAILs stated explicitly

| # | candidate | n / who received what | same subject, both agents? | EEG both agents? | size / access | verdict |
|---|---|---|---|---|---|---|
| **1** | **NCT02043938 / Kuizenga-Vereecke-Struys crossover** (Groningen/Ghent, sponsor Masimo). No repository DOI — trial registry only, papers PMID 29452809 / 31567365 / 33315176. | 36–46 healthy volunteers, 4 sessions each: propofol ± remifentanil, sevoflurane ± remifentanil | **YES** — literal crossover, MeSH "Cross-Over Studies" | **YES** — official title is "…Measured by the Spontaneous Electro-encephalogram"; PMID 33315176 computed 44 raw EEG features from it | Not deposited; would require direct author contact. Registry: **`ipdSharing: "NO"`** | **Best fit to the question, but closed by an explicit sponsor refusal, not absent.** Only real candidate with the target design (IV agent + volatile agent, same subject, EEG both). Actionable next step: an author-mediated request (à la `DATA_REQUEST_TURKU_KALLIONPAA.md`), explicit that raw traces (not the PSI/SEF derivatives already published) are what is needed — not guaranteed given the "NO", but not the same as no route existing. |
| **2** | **NCT01889004 / Turku-Kallionpää** (PMID 32773216) — request already drafted, unsent, `DATA_REQUEST_TURKU_KALLIONPAA.md` | 47 healthy volunteers, dexmedetomidine (n=23) **or** propofol (n=24) | **NO** — each volunteer gets one drug, not two | n/a (single agent per subject) | 64-channel scalp EEG; author request, no stated IPD refusal (`ipdSharingStatementModule: None`) | **FAILS the "same subject, two agents" bar** — it is within-subject for LOR/ROR at *one* drug, not an agent contrast. Weaker version noted in the brief (IV vs a pharmacologically distinct but non-volatile agent) — real, but does not test propofol-vs-volatile. Kept ranked #2 because it is the closest already-actionable request and its registry status is more favourable than #1's. |
| **3** | **Krause/Banks** (Zenodo `10.5281/zenodo.15497531`), already downloaded and used (E35/E36) | 34 epilepsy-surgery patients: 19 propofol, 10 dexmedetomidine, 24 sleep | **NO** — 0 of 29 patients in both drug arms | n/a | 2.1 GB, CC-BY-SA, open (raw iEEG needs a separate U. Iowa DUA) | **FAILS** — disjoint patients by construction; already the basis of E35/E36's *unclaimed* finding for exactly this reason. |
| **4** | **VitalDB**, `propofol\|sevoflurane`-labelled cases | 250 surgical cases; 58 labelled as receiving both drugs | **Labelled yes, actually NO** — median within-case dominant-agent span = 0.000 (E228, this project, today) | Technically yes but at most 1 usable epoch of each agent, on 1 case | Public, PhysioNet, already fully extracted here | **FAILS, verified today** — label reflects induction-propofol-then-maintenance-volatile, not a genuine two-regime recording. Closed by this project's own probe. |
| **5** | **Colombo 2019 / Sarasso 2015** (PMID 30639334, 26752078) — propofol, xenon, ketamine | **3 separate groups, n = 5 each** | **NO** — between-subjects, one drug per group | n/a | Not deposited as raw data anywhere found | **FAILS** — quoted directly from this project's own literature note: "Three groups of healthy participants, n = 5 each." Xenon is the agent this brief would most want, and this is the closest published contact point for it, but the design cannot supply a within-subject contrast and no dataset was located. |
| **6** | **PhysioNet `multimodal-surgery-anesthesia`** ("MGH OR") | 101 surgeries: 25 pure propofol, 14 propofol+sevoflurane | **NO** — different surgical cases, not the same patient under each agent at different times | Partial / unconfirmed (EEG content not yet verified in this project) | Accessible (HTTP 200), EEG content unconfirmed | **FAILS** — between-case, already characterised as "weak" in `DEPOSIT_ACCESS_STATUS.md`; even if usable it does not isolate one patient under two regimes. |

## Bottom line

**No public, downloadable deposit exists that lets `relative_alpha_power`'s reversal be tested within one
subject across an IV and a volatile agent.** This is now confirmed independently by (a) the project's own
Q8/Q9 record, (b) today's VitalDB-internal probe (E228, `PROBE_2026_08_02_CROSSOVER.md`), and (c) a fresh
OpenNeuro/Zenodo/Dryad/Figshare/OSF sweep in this session, all agreeing. That is a **confirmed absence**, not
a failure to look — the search is wide (five repositories plus a keyword-scanned full pull of every EEG
dataset OpenNeuro hosts) and it is reported as absence rather than padded with weak substitutes.

The one qualification is that **a matching design exists and is documented in the literature
(`NCT02043938`) but was never deposited**, and its registry entry states outright that individual
participant data will not be shared. That converts the open question from "does a usable deposit exist" (no)
to "is a direct data request to a named, identified group worth sending" (plausibly, but the odds are worse
than the already-drafted Turku request, whose registry carries no such refusal). If a request is made, it
should go to the Groningen/Ghent group (Kuizenga, Vereecke, Struys) behind NCT02043938, and it should ask
specifically for the raw spontaneous EEG traces already known (from PMID 33315176) to have been digitised and
feature-extracted — not the published PSI/SEF summary values, which cannot support an alpha-power
reanalysis.
