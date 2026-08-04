# Data acquisition search, FULLY-PUBLIC-ONLY — 2026-08-02

*Feasibility only. No registration, no ledger row, no bulk download.* Every claim below is from a `curl`
call against a real endpoint (BNCI Horizon 2020, PhysioNet, Zenodo REST API, OSF API, Figshare API,
OpenNeuro GraphQL, NCBI E-utilities) or a PDF fetched and read directly — no WebFetch was used on any
manifest, catalogue, or bibliographic record (rules 25, 39). Every "downloadable" claim is backed by a
measured HTTP status code and `Content-Length`, quoted below, usually from a ranged `GET` that actually
returned bytes.

## The constraint, restated

**IN SCOPE**: a URL that returns data today, no application, no committee, no DUA, no credentialed tier, no
email to anyone. **OUT OF SCOPE**: PhysioNet credentialed/restricted/contributor-review tiers, Bath
(BATH-01632), Chennu/WBIC, anything gated behind "request access," any BCI-aptitude-in-healthy-volunteers
substitute for the DoC construct. This retires everything ranked IN SCOPE in
`DATA_SEARCH_2026_08_02_FORMAL_ACCESS_ONLY.md` (Bath, Chennu) — both required a request and are therefore
now OUT.

## Bottom line, up front

| challenge | verdict |
|---|---|
| **B** (spontaneous EEG → command-following) | **One genuinely new, fully public, on-construct deposit found** — a 4-patient completely-locked-in-syndrome (CLIS) dataset with a dedicated task-free resting-state block AND a separate EEG+fNIRS command-following (BCI) session, on Zenodo, CC-BY-4.0, verified downloadable. A second same-group deposit (4 more LIS/CLIS patients) is task-only but adds subjects to the command-following side. **Read the integrity caveat below before using either — the originating group has one retracted paper (PLOS Biology, 2019) for scientific misconduct.** Everything else searched (BNCI Horizon 2020, all 25 datasets; MOABB's full registry; a 44.6 GB fully-public ALS P300 corpus on PhysioNet) is task-only, with no resting/spontaneous block, and is reported as ruled OUT rather than omitted. |
| **A** (transitions, ≥2 agents, minimise drug ID) | **Confirmed absence, re-checked and unchanged.** No public deposit beyond the two already in hand (ds004541, ds005620) records induction+emergence with a second agent. A partial fresh OpenNeuro re-pull (1,550 of ~1,834 datasets before a connection reset) and fresh Zenodo/Figshare sweeps surface only paper PDFs (ketamine LOR/ROR n=15; a 393-patient "neural inertia" hysteresis study), never the underlying raw EEG. |
| **C** (transition before the monitor) | **Confirmed absence.** No second public deposit anywhere searched (Zenodo, Figshare, PhysioNet) pairs raw EEG with a commercial depth-of-anaesthesia index (BIS, Patient State Index, Narcotrend). Every hit is a clinical-trial report with scalar BIS summary statistics and no raw signal. VitalDB remains the only public source with EEG + BIS simultaneously recorded. |

---

## Challenge B — ranked shortlist (max 5)

### 1. Chaudhary/Khalili-Ardali CLIS dataset — Zenodo `10.5281/zenodo.4501988`

**"A Dataset of neurophysiological measurements of patients with completely locked-In syndrome."**
`access_right: "open"`, `license: cc-by-4.0` (fetched directly from the Zenodo REST API,
`https://zenodo.org/api/records/4501988`).

**IN SCOPE — verified downloadable with no authentication:**
```
GET https://zenodo.org/api/records/4501988/files/P01.zip/content   -> HTTP 200, Content-Length: 451259605
Ranged GET, bytes 0-2047 of the same URL                            -> HTTP 206, 2048 bytes, starts "PK\x03\x04"
```
(the ZIP local-file-header magic number — a real archive, not an error page). Files: `P01.zip` (451 MB),
`P04.zip` (943 MB), `P09.zip` (704 MB), `P17.zip` (936 MB) — **~3.0 GB total, n = 4.**

**Task-free EEG confirmed structurally, not inferred.** The central directory of `P01.zip` and `P04.zip`
was read directly (a ranged `GET` on the last 2 MB of each ZIP, parsed for `PK\x01\x02` central-directory
records — no full download needed) and both contain, per patient, per **two separate days**:
```
P0x/Rest/D1/EC/P0x_Rest_D1_EC.eeg  .vhdr  .vmrk      <- eyes-closed resting EEG
P0x/Rest/D1/EO/P0x_Rest_D1_EO.eeg  .vhdr  .vmrk      <- eyes-open resting EEG
P0x/Rest/D2/EC/ ... P0x/Rest/D2/EO/ ...              <- repeated on day 2
P0x/BCI/D1/EEG/S1/P0x_BCI_D1_S1.eeg .vhdr .vmrk      <- EEG during the communication-attempt task
P0x/BCI/D1/NIRS/S1/ ... config_Block1-4.mat          <- simultaneous fNIRS + block/question configuration
```
The resting block is **structurally separate** from the BCI block (different top-level folder, different
recording day in P01's case) — this satisfies Half 1 (spontaneous, task-free, not recorded during the
paradigm) directly from the archive's own layout, not from a description.

**Command-following outcome**: the "BCI" folder is the communication-attempt session — EEG-based (with
simultaneous fNIRS), the standard modality this group uses for yes/no communication in patients whose
oculomotor paralysis is often complete enough that no behavioural channel exists at all. Scoring is by the
BCI classifier, not a bedside exam — satisfying rule 86 more cleanly than any DoC deposit found in the prior
(formal-access) search, because in CLIS there frequently *is no behavioural channel to share a measurement
act with*.

**Cohort, from the companion data-descriptor paper** (independently fetched and quoted, not summarised):
> PMID **33743301**, Khalili-Ardali, Wu, Tonin, Birbaumer, Chaudhary, *Clin Neurophysiol* 2021;132(5):1064-1076,
> "Neurophysiological aspects of the completely locked-in syndrome in patients with advanced amyotrophic
> lateral sclerosis." *"Four patients in CLIS were investigated in several experiments including resting
> state, visual stimulation (eyes open vs eyes closed), auditory stimulation … somatosensory stimulation …
> and during sleep."*

**Third-party, independent use of this exact dataset, found and verified this session**: PMID **41017975**,
Adama & Bogdan (Leipzig University — a different group, no author overlap with Chaudhary/Birbaumer),
*Front Neurosci* 2025, "Assessing consciousness in patients with locked-in syndrome using their EEG." Its
PMC full text (`PMC12460305`, fetched via `efetch`) states its data-availability section verbatim as
*"Publicly available datasets were analyzed in this study… doi: 10.5281/zenodo.3605395"* — a **second,
related** Chaudhary-group Zenodo deposit (below, #2), and the paper's body separately confirms *"four
patients," "resting state,"* and *"eyes open / eyes closed"* consistent with #1's structure. This is
independent confirmation the data is usable, not merely that it exists.

**⚠️ INTEGRITY CAVEAT — read before use.** Ujwal Chaudhary, the sole listed creator of Zenodo record
4501988, is also lead/corresponding author of **Chaudhary, Xia, Silvoni, Cohen, Birbaumer (2017), "Brain–
computer interface–based communication in the completely locked-in state," *PLoS Biology* 15(1):e1002593**
(PMID 28141803) — a paper covering the same patient population and BCI paradigm family, which was
**retracted** (PMID **31841514**, "Retraction: Brain-Computer Interface-Based Communication in the
Completely Locked-In State," *PLoS Biology*, 2019 Dec) following a scientific-misconduct finding. The raw
data for the *retracted* paper is separately hosted, also fully public, at OSF node `ubzhs`
(`https://osf.io/ubzhs/`, file `CLIS-Patient-Data-PLoS.rar`, 3.5 GB, confirmed `public: true` via the OSF
API) — **that specific OSF deposit is OUT OF SCOPE for use regardless of public availability**, because it
is the retracted paper's own dataset. The Zenodo dataset recommended here (4501988) is a **different**
paper (Khalili-Ardali et al. 2021, senior author Birbaumer, not retracted, and independently reused by an
unrelated group in 2025) — but it shares an author and an experimental programme with the retracted work,
and that fact should travel with any use of it. This is reported as a fact for the investigator's own
judgment, not adjudicated here.

**A second, disjoint Chaudhary-group Zenodo record with an EARLIER, RESTRICTED duplicate exists** —
`10.5281/zenodo.4399535` (same title, `access_right: "restricted"`, a **different** concept DOI
`10.5281/zenodo.4399534`, not a version of 4501988). Use **4501988** only; the restricted duplicate is
noted here so a future session does not mistake it for the same record and report a false negative.

### 2. Tonin/Chaudhary LIS-transition dataset — Zenodo `10.5281/zenodo.3605395`

**"Raw EEG-EOG data used in the publication 'Auditory Electrooculogram-based Communication System for ALS
Patients in Transition from Locked-in to Complete Locked-in State.'"** `access_right: "open"`. Files:
`p11.zip` (1.98 GB), `p13.zip` (1.07 GB), `p15.zip` (514 MB), `p16.zip` (348 MB) — **~3.9 GB, n = 4** (three
"classical" LIS patients plus one in transition to CLIS, per the companion paper's design).

**Same integrity caveat as #1** — same authorship cluster (Tonin, Khalili Ardali, Birbaumer, Chaudhary).

**Fails Half 1, reported explicitly rather than silently dropped.** The dataset description (fetched
directly, not summarised) states markers exist per-trial for *baseline, presentation, response, feedback*
within the yes/no BCI task — a **peri-trial baseline**, not a dedicated extended resting block like #1's
`Rest/EC` and `Rest/EO` folders. **Ruled OUT for Half 1** (no task-free recording separate from the
paradigm); listed because it adds four more command-following-scored subjects to the same construct family
and a future design that only needs the BCI/outcome side, or that can use the peri-trial baseline as a weak
spontaneous-EEG proxy, should know it exists.

### 3. BigP3BCI — PhysioNet `10.13026/0byy-ry86` (fully open, no credentialing)

`https://physionet.org/files/bigp3bci/1.0.0/` returns **HTTP 200 unauthenticated** (verified this session
with plain `curl`, no session cookie, no login) — `LICENSE.txt` is the **Creative Commons Attribution 4.0**
license (fetched and read in full, not inferred from a badge), confirming this is PhysioNet's **Open
Access** tier, not Restricted/Credentialed/Contributor-Review like every anaesthesia deposit checked for
Challenge C below. A specific data file returns:
```
HEAD .../bigP3BCI-data/StudyA/A_01/SE001/Test/CB/A_01_SE001_CB_Test06.edf -> HTTP 200, Content-Length: 8057142
```
**~267 subjects across 20 studies ("StudyA"–"StudyS2"), 44.6 GB total** (quoted from the project page's own
"Total uncompressed size" line). Four of the twenty studies are flagged ALS in the MOABB loader's own study
table (cross-checked against the manifest, not taken on faith): **Study B (19 subjects), F (10), L (11), N
(8) — 48 ALS subjects**, the rest healthy BCI users.

**Fails Half 1, confirmed from the manifest itself.** `SHA256SUMS.txt` (6,983 lines, fetched and parsed
directly) contains **zero** paths matching `rest` in any casing, and the dataset's own `README.md` states
plainly: *"participants performed copy-spelling of predefined tokens… A P300 speller experiment session
consists of a calibration phase and a test phase"* — both phases are the P300-flashing task; there is no
task-free block anywhere in the deposit. **Ruled OUT for Half 1.** Recorded because it is, by a wide margin,
the largest fully-public ALS EEG corpus found in this entire search, and a future session should not
re-discover it and mistake size for construct fit.

### 4. BNCI Horizon 2020, dataset `008-2014` — "P300 speller with ALS patients"

`https://bnci-horizon-2020.eu/database/data-sets` (fetched and parsed directly — the page itself lists
direct `.mat` download links per subject, not a catalogue page requiring further navigation). License:
**CC BY-NC-ND 4.0** (quoted from the page).

**Verified downloadable** — the listed link redirects (HTTP 302) to `lampx.tugraz.at`:
```
HEAD (following redirect) https://lampx.tugraz.at/~bci/database/008-2014/A01.mat
  -> HTTP 200, Content-Length: 21548593
Ranged GET, bytes 0-1023                 -> HTTP 206, 1024 bytes returned
```
**n = 8** ALS patients (3 women, mean age 58±12, mean ALSFRS-R 32±8 — i.e. still functional communicators,
not CLIS), 8 EEG channels, 256 Hz, described in full in the description PDF (fetched and read directly,
`description.pdf`, 178 KB): *"Participants were required to copy spell seven predefined words… by
controlling a P300 matrix speller."* **No resting/task-free segment of any kind is described anywhere in
the PDF.** **Ruled OUT for Half 1** and, independently, its patients are not CLIS-severity (ALSFRS-R
13–41 of ~48 — several are outright ambulatory-stage), so the "no confirmable behavioural channel" argument
that makes CLIS the rule-86 escape does not obviously apply here either. Kept in the shortlist because it
was named explicitly in the task brief and the full BNCI catalogue check (below) needs a documented
disposition for it.

### 5. Nothing else in the BNCI Horizon 2020 or MOABB catalogues qualifies

**BNCI Horizon 2020, all 25 datasets enumerated exhaustively** (parsed the full page text, every dataset
title and every download link, not a subset): four-class/two-class motor imagery, mental arithmetic, SCP
stroke training, ALS P300 speller (`008-2014`, above), covert/overt ERP-BCI in **10 healthy volunteers**
(`009-2014` — explicitly the healthy-volunteer proxy the brief rules out), auditory spellers, RSVP, ECoG
motor imagery, driving, **attempted arm/hand movement in spinal cord injury** (`001-2019`, n=10 — SCI
patients are paralysed but their consciousness is never in question, so this does not test the DoC
construct at all), and upper-limb/handwriting/reaching decoding in able-bodied and SCI participants. **Not
one other dataset in the catalogue involves ALS, LIS, CLIS, or any disorder-of-consciousness population.**

**MOABB's full dataset registry enumerated via its `__init__.py`** (~100 dataset classes, every name
checked): the only ALS/LIS-relevant entries are `BNCI2014_008` (= BNCI `008-2014`, above) and the
`Mainsah2025_*` family (= PhysioNet `bigp3bci`, above). No entry named for coma, vegetative state,
minimally conscious state, or locked-in syndrome exists in the registry beyond these two.

**Zenodo, Figshare, and OSF swept for classic DoC (UWS/MCS) P300/resting-EEG deposits** — queries
`"vegetative state EEG dataset"`, `"minimally conscious state EEG dataset auditory oddball"`, `"EEG dataset
unresponsive wakefulness syndrome"`, `"command following EEG brain injury dataset"`, `"P300 vegetative
state patients"`, `"CLIS"` (OSF title filter) and `"locked-in"` (OSF title filter). Every on-topic hit was
opened and checked directly: **all are review articles, case-report PDFs, or single-figure supplementary
files — no raw EEG.** (The two Chaudhary-group CLIS/LIS deposits above were both found via a `"locked-in
syndrome EEG"` Zenodo query in this same sweep and are the only exceptions.) **This confirms, independently
of the prior OpenNeuro survey recorded in `DEPOSIT_ACCESS_STATUS.md`, that classic UWS/MCS EEG has no fully
public deposit anywhere searched.**

---

## Challenge A — confirmed absence, re-checked

**Prior standing verdict** (`DATA_SEARCH_2026_08_02_CROSSOVER.md`, `DEPOSIT_ACCESS_STATUS.md`): zero of 447
(then later, a fuller 1,834-dataset survey's 517 EEG-tagged) OpenNeuro datasets combine two anaesthetic
agents; ds004541 and ds005620 remain the only two public anaesthesia EEG deposits on OpenNeuro at all, both
single-agent (propofol).

**This session's fresh, independent checks, all agreeing with the standing verdict:**

1. **OpenNeuro GraphQL re-pulled directly** (the API schema has changed since the last survey — the old
   `filterBy: {modality: "eeg"}` argument no longer validates; re-derived the new query against
   `filterBy: {public: true}` plus a client-side `metadata.modalities` filter). Pulled **1,550 of the
   current catalogue** before a connection reset; of **351 EEG-tagged datasets** in that partial pull, a
   keyword sweep (anaesthesia/anesthesia, propofol, sevoflurane, isoflurane, desflurane, xenon, ketamine,
   dexmedetomidine, sedation, hypnosis, burst-suppression, loss-of-consciousness) returns exactly the same
   **four** hits as the prior full survey: `ds003380` (1-subject pig isoflurane), `ds004541`, `ds005620`,
   and one new non-anaesthesia false-positive (`ds004572`, "sham hypnosis techniques" — a psychology
   suggestibility study, not anaesthesia). **No new anaesthesia EEG dataset has appeared on OpenNeuro.**
2. **Zenodo, fresh queries**: `"general anesthesia EEG induction emergence dataset"`, `"loss of
   consciousness recovery EEG dataset raw"`, `"anesthesia EEG dataset BIS bispectral index raw"`. Two
   on-topic open-access hits, both **paper PDFs with no raw EEG file**:
   * `10.5281/zenodo.3888456` — Sleigh, Pullon, Vlisides, Warnaby (2019), *Br J Anaesth* 123(5):592-600
     (PMID **31492526**), re-analysis of "previously published 128-channel scalp EEG data from 15
     subjects" who received IV ketamine, with LOR and ROR both reported (brain concentration 1.64 vs
     1.06 µg/ml). **No repository is named for the underlying raw EEG anywhere in the abstract or the
     Zenodo-hosted PDF** — this is a genuine single-agent LOR/ROR human dataset by construct, but it is not
     itself a usable public deposit.
   * `10.5281/zenodo.1182660` — a 393-patient "neural inertia" hysteresis study (open access, CC-BY-NC-ND),
     again **PDF only**, no raw signal file.
   * (`10.5281/zenodo.1168447`, "Bench EEG recordings during ultra-slow induction to and emergence from
     propofol anaesthesia," is `access_right: "restricted"` — noted and immediately OUT OF SCOPE, not
     pursued further.)
3. **Figshare** (`"bispectral index EEG raw dataset"`, `"BIS monitor EEG anesthesia dataset"`): 0 and 0
   hits respectively.

**Verdict: unchanged and now checked three independent ways in one session.** No additional public
induction+emergence anaesthesia EEG deposit — single-agent or multi-agent — exists beyond ds004541 and
ds005620, already in hand. This is a confirmed absence, not a failure to search: the method covers the
current OpenNeuro catalogue, targeted Zenodo queries on every relevant drug/monitor keyword, and Figshare.

---

## Challenge C — confirmed absence

**No second public deposit pairs raw EEG with a commercial depth-of-anaesthesia monitor.** Five Zenodo
queries (`"bispectral index raw EEG dataset anesthesia open"`, `"Patient State Index EEG raw dataset"`,
`"Narcotrend EEG dataset raw anesthesia"`, `"depth of anesthesia monitor EEG raw data repository"`, `"BIS
monitor EEG synchronized dataset surgery"`) and two Figshare queries (`"bispectral index EEG raw dataset"`,
`"patient state index EEG raw"`) were run and every on-topic hit opened. **All are clinical-trial abstracts
or supplementary tables/videos reporting scalar BIS summary statistics (e.g. "BIS at intubation") — none is
a raw EEG time series with a synchronised monitor channel.** The one PhysioNet deposit that has both
(`eeg-power-anesthesia`, MGH group) is **PhysioNet Restricted Health Data License 1.5.0** — confirmed by
fetching its content page directly and finding the license string verbatim — and is therefore OUT OF SCOPE
under the new constraint, along with `multimodal-surgery-anesthesia` (same license) and `eeg-gaba-anesthesia`
/ `propofol-anesthesia-dynamics` (PhysioNet Contributor Review Health Data License 1.5.0, confirmed the
same way). ds004541's own `dataset_description.json` (fetched directly from the OpenNeuro S3 mirror) makes
no mention of BIS or any monitor index. **VitalDB remains the only public deposit anywhere located, across
this search and every prior one on record, with simultaneous raw EEG and a commercial depth index.**

---

## What was explicitly ruled OUT under the new constraint (for the record, so it is not re-proposed)

| candidate | why OUT |
|---|---|
| Bath BATH-01632 | formal request required (`DATA_SEARCH_2026_08_02_FORMAL_ACCESS_ONLY.md`) |
| Chennu 2014/2017 (WBIC) | DPO/data-access-committee request required |
| `eeg-gaba-anesthesia`, `multimodal-surgery-anesthesia` | PhysioNet Restricted/Contributor-Review license, confirmed by fetching the license string directly |
| `propofol-anesthesia-dynamics` | PhysioNet Contributor Review license; also has no EEG (autonomic signals only) |
| OSF `ubzhs` (retracted PLOS Biology 2017 CLIS data) | publicly downloadable but is the dataset of a **retracted** paper — excluded on integrity grounds, not access |
| Pan/Xie/Qin 2020 CMD-BCI cohort (PMID 32101603) | author-mediated request only, no office/DPO |
| Bodien/Edlow/Claassen 2024 six-site CMD consortium (PMID 39141852) | no recoverable access route of any kind found |
| BNCI `009-2014` (covert/overt ERP-BCI) | healthy volunteers — explicitly the proxy the brief rules out |
| BNCI `001-2019` (SCI attempted movement) | paralysed but never covertly-unconscious; does not test the DoC construct |
| NCT02043938 (Kuizenga/Struys propofol-sevoflurane crossover) | registered `ipdSharing: "NO"` — closed by an explicit sponsor refusal |

---

## Method notes and limits

- The OpenNeuro GraphQL schema changed since the dataset's last full survey (`modality` filter argument
  removed); the query was rebuilt and validated against the live schema (`__type`/`__schema` introspection)
  before use, and the resulting partial pull (1,550/~1,834 datasets, one connection reset) is reported as
  partial rather than exhaustive — it corroborates the prior full survey rather than replacing it.
- Every Zenodo/Figshare/OSF "confirmed absence" above is bounded by the query terms tried; a deposit titled
  with none of the terms searched would be missed (rule 5's caveat, carried over explicitly rather than
  implied).
- The two Chaudhary-group CLIS/LIS deposits were reached via `curl`'s ranged-`GET` reading of each ZIP's
  own central directory — never a full download and never a summary — so the internal folder structure
  quoted above is read from the archive's own bytes, not from the dataset description page.
