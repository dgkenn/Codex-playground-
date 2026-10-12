# MOVER database: access pathway, contents, and automatability

Date checked: 2026-06-30. Sources are web search + WebFetch against the live
MOVER site, the JAMIA Open publication, and PhysioNet pages for INSPIRE/VitalDB
(see citations inline). This doc answers a one-time access-due-diligence
question; it does not change any pipeline code in this repo.

## 1. Is MOVER on PhysioNet or only at UC Irvine?

**Only at UC Irvine. MOVER is NOT hosted on PhysioNet.**

- Canonical site: `https://mover.ics.uci.edu/` (UC Irvine ICS).
- Download/application portal: `https://mover.ics.uci.edu/download.html`.
- A *metadata-only* listing also exists on the UCI Machine Learning
  Repository (`archive.ics.uci.edu/dataset/877/...`, DOI
  `10.24432/C5VS5G`), but that page is explicitly marked "External" — it
  does not host the data itself and just links back to
  `mover.ics.uci.edu` for the actual DUA/download. The `ucimlrepo` Python
  package only wraps this metadata pointer, not a real download.
- The MOVER paper itself contrasts MOVER with MIMIC/PhysioNet, describing
  MOVER as filling a gap *PhysioNet does not cover* (large-census surgical
  EHR + OR waveforms), not as something distributed through PhysioNet.

There is no `physionet.org/content/mover...` page, and PhysioNet's own
database index does not list MOVER.

## 2. Exact access procedure

MOVER access is a **UC Irvine-administered Data Use Agreement (DUA) with
human review — not PhysioNet credentialing and not a pure click-through.**

Procedure as posted on `mover.ics.uci.edu/download.html`:
1. Fill out a request form (name, email, phone, date — i.e., an
   application, not a self-service account).
2. Submit; a confirmation popup is shown.
3. **"the dataset administrators"** (UC Irvine/UCLA MOVER team) manually
   review the application.
4. If approved, the requester receives **an email with credentials and a
   download URL** for the actual data transfer.

This is materially different from PhysioNet's process:

| | PhysioNet (e.g. MIMIC, eICU, INSPIRE) | MOVER |
|---|---|---|
| Account system | Centralized PhysioNet account | None — ad hoc email form |
| Training requirement | CITI "Data or Specimens Only Research" course, uploaded report | Not specified/required on the public page |
| Agreement | Standardized DUA signed electronically in PhysioNet's "Files" workflow, after credentialing + training are approved (PhysioNet states this normally completes in 24–48 hours, though the credentialing team has also posted notices of significant backlog/delays at times) | A separate, UCI-specific DUA; exact text is not published outside the request flow; no published turnaround-time commitment |
| Who approves | PhysioNet/MIT credentialing reviewers, a standardized pipeline shared across all PhysioNet "restricted" datasets | UC Irvine/MOVER project staff, a small dataset-specific team — i.e., a bespoke institutional approval, not a scalable credentialing pipeline |
| API/automatable retrieval once approved | Yes — `wget`/AWS CLI/`physionet` Python client work against a known credentialed account | Unknown/unlikely — access is "credentials and URL info sent after review," implying a one-off, possibly manually issued download link rather than a standing API account |

Net: MOVER requires a **separate, UC Irvine-specific institutional DUA**
with a human-in-the-loop review step before any credentials are issued.
It is not part of the PhysioNet ecosystem at all, so an existing
PhysioNet account/credentialing (e.g., already-approved access to MIMIC,
eICU, INSPIRE, VitalDB) confers **no** access to MOVER.

## 3. Dataset contents relevant to anesthesiology research

From the JAMIA Open description paper (Samad et al., *JAMIA Open* 6(4):
ooad084, 2023) and the MOVER site:

- **Scale:** 58,799 unique adult patients, 83,468 surgeries, UC Irvine
  Medical Center, ~2015–2022 (two source systems merged: an older "SIS"
  anesthesia-information system feed of 19,114 patients, and a newer Epic
  feed of 39,685 patients).
- **Waveforms:** captured via Bernoulli Health's intraoperative
  monitoring platform. Confirmed waveform types: **ECG (EKG), the
  arterial line pressure waveform (when an arterial line is present),
  and the pulse oximetry (pleth/SpO2) waveform.** No EEG/processed-EEG
  (BIS) waveform is described as part of the standard MOVER waveform set.
  **Exact sampling rates in Hz are not stated** in the publication or on
  the public site (only that they are "high-fidelity" / "high temporal
  resolution"); the paper notes known data-quality caveats ("known
  errors... in particular in relation to the value of the gains of some
  of the waveforms"), so even after access, waveform calibration/QC work
  would likely be needed before use.
- **Outcomes:** the published outcomes table is organized as **broad
  postoperative complication categories** — Cardiovascular, Respiratory,
  Airway, Metabolic, Neurological, Administrative, Injury/Infection,
  Medication, Regional, Chronic pain, Other — plus ICU transfer (45.3%)
  and in-hospital mortality (1.6%). **No discrete, pre-labeled variable
  for postoperative delirium, AKI, or "postoperative pulmonary
  complications" is reported in the description paper.** A "Respiratory"
  category exists (1.1%) but is not broken out into pneumonia,
  reintubation, or respiratory-failure sub-codes in what's published.
  Underlying raw EHR data (labs incl. creatinine, structured flowsheets,
  free-text notes) likely exists in the full MOVER export and could in
  principle support deriving AKI (KDIGO via creatinine trend) or
  delirium (CAM screening documentation, if charted) labels post hoc —
  but that would be the requester's own derivation work, not a
  ready-made outcome column, and would require obtaining and inspecting
  the actual data dictionary (not publicly posted) after a DUA is signed.

## 4. Can an automated agent download MOVER today?

**No — realistically this needs a manual, human-mediated application.**

Reasons:
- The only documented entry point is a web **form requiring a named
  human applicant** (name/email/phone), reviewed by UC Irvine dataset
  administrators on an unspecified timeline.
- There is no API, no self-service credentialing, and no indication that
  approval is instant or rule-based (unlike PhysioNet's standardized
  CITI-training + DUA pipeline, which — while still requiring a human to
  complete training and sign once — is at least a uniform, documented,
  largely self-service flow with a stated 24–48-hour SLA).
- Credentials/URL are described as being **emailed individually after
  review**, i.e., issued per-applicant rather than via a programmatic
  account-creation endpoint.
- Even with credentials in hand, exact transfer mechanics (single
  zipped export vs. structured bucket) aren't documented publicly, so a
  first manual download would likely be needed to discover the retrieval
  pattern before any agent could automate subsequent re-syncs.

So: an agent holding only a PhysioNet login **cannot** obtain MOVER —
PhysioNet credentials are not honored at all for MOVER, which lives
entirely outside PhysioNet's infrastructure. Getting MOVER requires a
person to submit the UC Irvine request form and wait for manual approval
and a one-off credential/URL email; only after that human step could any
downstream download be scripted/automated.

## 5. INSPIRE (PhysioNet) — quick check

- **Hosted on PhysioNet:** yes — `physionet.org/content/inspire/` (current
  version 1.4 / 1.4.2 as of this check).
- **Access type:** PhysioNet **credentialed** access (not open), under a
  Korea-specific agreement: "Korea Credentialed Health Data
  Agreement-1.0.0" / "Korea Credentialed Health Data License-1.0.0",
  requiring the standard CITI "Data or Specimens Only Research" training
  report plus signing the DUA through PhysioNet's normal credentialing
  flow.
- **Waveforms:** **none.** INSPIRE is OR/ICU/ward **numeric vitals and
  EHR only** — intraoperative vitals are recorded at 1-minute intervals
  (aggregated to 5-minute medians for some fields), ICU hourly, ward
  4–6x/day. No raw ECG/arterial/pleth/EEG waveform tracks. (This is
  consistent with this repo's existing `inspire/` module, which already
  treats INSPIRE as a numeric/EHR external-validation source, not a
  waveform source — see `INSPIRE_VALIDATION.md`,
  `EXTERNAL_VALIDATION_INSPIRE.md`.)
- **Outcomes:** mortality, ICU/hospital length of stay, ICU admission
  within 24h are the headline outcomes documented. Labs include renal
  function tests (creatinine), supporting AKI derivation (as this repo
  already does). Diagnosis table is ICD-10-CM but truncated to 3 digits
  and **explicitly excludes "mental and behavioural disorders"
  diagnoses** — i.e., the diagnosis codes that would carry delirium
  (ICD-10 F05.x) appear to be removed by design. No dedicated delirium
  or postoperative-pulmonary-complication outcome variable is documented.
  ~130,000 surgeries, Seoul National University Hospital, 2011–2020.

## 6. Any PhysioNet dataset pairing intraop waveforms with delirium/PPC?

**Not as a ready-made labeled pair, as of this check.**

- **VitalDB** (`physionet.org/content/vitaldb/`, also mirrored at
  vitaldb.net) is the one PhysioNet-hosted dataset with **both**
  real intraoperative waveforms (ECG, arterial line, pleth/SpO2,
  EEG/BIS, airway pressure; waveform sampling 62.5–500 Hz, numerics
  1–7 s resolution) **and** open access (CC-BY 4.0, no credentialing
  required) — 6,388 non-cardiac surgical cases, SNUH, Aug 2016–Jun 2017.
  It is already the primary waveform/AKI source for this repo (per
  `cohort/`, `features/`, and this directory's name).
  - VitalDB's *native* released tables do not include a built-in
    delirium or PPC outcome column; it ships labs (supporting
    creatinine-based AKI labeling, which this repo already implements)
    and general perioperative/clinical parameters, not psychiatric or
    pulmonary-complication adjudication.
  - However, a 2024–2025 study (**DELPHI-EEG**, *npj Digital Medicine*)
    built a postoperative-delirium model using intraoperative EEG
    **extracted from VitalDB** (34,550 cases) — but the delirium labels
    in that study were **pulled separately from the source hospital's
    EHR** (neuropsychiatric consultation notes, CAM-ICU where available
    [only 12.4% of cases], antipsychotic administration), not from a
    label that ships in the public VitalDB release. So the
    waveform+delirium pairing exists in that paper's private analytic
    dataset, not in anything currently downloadable by a third party
    from PhysioNet.
- No other PhysioNet database was found that pairs intraoperative
  waveforms with delirium or postoperative pulmonary complications as a
  released, public label. MIMIC-family databases (MIMIC-III/IV,
  MIMIC-IV-ECG, MIMIC-IV-Waveform) are ICU-stay-based, not
  intraoperative, and likewise do not ship delirium/PPC as a curated
  label paired with raw waveforms.

**Bottom line:** if this project ever wants intraop-waveform-based
delirium or PPC modeling, the realistic options today are (a) derive
proxy labels from VitalDB's own clinical/lab tables (e.g., AKI via
creatinine, as already done; PPC proxies via ICU/ventilation/length-of-
stay fields if present) rather than expecting a native label, or (b)
pursue a manual UC Irvine DUA for MOVER and then check whether its raw
(unpublished-format) EHR export actually contains delirium/PPC
documentation — which is not guaranteed by anything publicly posted.

## Sources

- MOVER site: https://mover.ics.uci.edu/ and
  https://mover.ics.uci.edu/download.html
- MOVER paper (JAMIA Open): https://academic.oup.com/jamiaopen/article/6/4/ooad084/7320357
  and PMC mirror https://pmc.ncbi.nlm.nih.gov/articles/PMC10582520/
- MOVER preprint abstract (medRxiv/PMC):
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10029016/
- UCI ML Repository metadata listing (external pointer only):
  https://archive.ics.uci.edu/dataset/877/mover:+medical+informatics+operating+room+vitals+and+events+repository
- INSPIRE on PhysioNet: https://physionet.org/content/inspire/1.4/
- VitalDB on PhysioNet: https://physionet.org/content/vitaldb/1.0.0/
- PhysioNet credentialing process: https://physionet.org/about/citi-course/,
  https://physionet.org/news/post/395/, https://physionet.org/news/post/397/
- DELPHI-EEG (VitalDB-derived intraoperative EEG -> postoperative
  delirium model): https://www.nature.com/articles/s41746-025-02033-y
