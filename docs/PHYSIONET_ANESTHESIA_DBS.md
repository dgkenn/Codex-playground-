# PhysioNet Databases for Anesthesiology / Perioperative / Intraoperative Research

Standalone catalog. Not part of the HEEDB EEG-phenotype-discovery project (see root
`CLAUDE.md`) — this document surveys PhysioNet (and adjacent, PhysioNet-indexed-or-cited)
resources relevant to anesthesiology, perioperative medicine, intraoperative monitoring,
and surgical critical care, for a separate line of inquiry.

Compiled 2026-06-30 from physionet.org/content/?topic=anesthesia,
physionet.org/about/database/, and targeted web research (see Sources at bottom of each
entry's underlying search; URLs given per database below).

---

## Tier 1 — Genuine high-resolution INTRAOPERATIVE WAVEFORMS (rare, high-value)

These are the only resources in this survey that give continuous, high-sample-rate
physiological waveform data *captured during surgery in the operating room*, as opposed
to charted/manually-recorded vitals or post-hoc summary statistics. This is the scarce
asset for anesthesiology ML work (analogous to what MIMIC waveform DBs are for ICU
research).

### VitalDB
- **URL:** https://physionet.org/content/vitaldb/1.0.0/ (also distributed natively at https://vitaldb.net)
- **Size:** 6,388 surgical cases (noncardiac surgery, Seoul National University Hospital, 2016–2017); 95.4 GB uncompressed; ~2.8M data points/case; 486,451 total waveform+numeric tracks.
- **Access:** **Open** — Creative Commons Attribution 4.0, no credentialing or DUA required (registration only at vitaldb.net).
- **Signals/waveforms:** This is the crown jewel. True high-fidelity intraoperative waveforms at **62.5–500 Hz**, including:
  - ECG
  - Invasive arterial blood pressure (and other invasive pressure lines)
  - Photoplethysmography / SpO2 pleth
  - Capnography (airway pressure/CO2 waveform)
  - **Processed EEG / Bispectral Index (BIS)** — depth-of-anesthesia
  - **Cerebral/somatic oximetry (NIRS)**
  - Neuromuscular monitoring (train-of-four)
  - 196 intraoperative monitoring parameters total (~12 waveform tracks + 184 numeric tracks/case); numeric vitals at 1–7 s resolution
  - Target-controlled infusion (TCI) pump histories for IV anesthetics (propofol, remifentanil, etc.)
- **EHR/labs/meds:** 73 perioperative clinical parameters (demographics, ASA class, surgical/anesthesia details) + 34 time-series lab parameters spanning ~3 months pre/post-surgery.
- **Outcomes:** Postoperative AKI, length of hospital stay, in-hospital mortality (in `clinical_data.csv`); not a deep outcomes registry but sufficient for many endpoints.
- **Companion resource — VitalDB Arrhythmia Database** (https://physionet.org/content/vitaldb-arrhythmia/1.0.0/): expert-annotated subset, 482 surgical patients, 734,528 s continuous ECG at 500 Hz, >660,000 beats labeled (4 beat types, 10 rhythm classes) by 5 anesthesiologists (Cohen's kappa 0.93). Open access, 20.9 MB, directly linkable to parent VitalDB waveforms.
- **Why it matters:** Largest fully-open (no DUA) intraoperative multi-modal waveform dataset that includes BIS/EEG depth-of-anesthesia *and* NIRS cerebral oximetry alongside hemodynamic waveforms — unmatched combination for anesthesia-depth / neuromonitoring ML.

### MOVER (Medical Informatics Operating Room Vitals and Events Repository)
- **URL:** https://doi.org/10.24432/C5VS5G (DUA-gated download); overview at https://pmc.ncbi.nlm.nih.gov/articles/PMC10582520/ and https://academic.oup.com/jamiaopen/article/6/4/ooad084/7320357
- **Size:** 58,799 unique patients, 83,468 surgeries; University of California, Irvine Medical Center, 2015–2022. Two linked sub-cohorts: SIS dataset (19,114 patients, 9 tables) and EPIC dataset (39,685 patients / 64,354 surgeries, 10 tables).
- **Access:** **Credentialed** — Data Usage Agreement (DUA) required, open to any researcher who signs it (not a closed consortium).
- **Signals/waveforms:** Real, bedside-monitor-derived high-fidelity waveforms: **ECG, arterial pressure waveform, and pulse-oximetry (pleth) waveform**. Notably it does **not** include capnography, BIS/EEG depth-of-anesthesia, NIRS, or neuromuscular monitoring — narrower waveform scope than VitalDB. High-resolution derived hemodynamics (cardiac output, stroke volume variation) also present in the SIS arm.
- **EHR/labs/meds:** This is MOVER's real differentiator — it is explicitly billed as the first public database to **fuse EHR and high-fidelity physiologic waveforms for a large surgical census** (analogous to what MIMIC did for ICU). Full medical history, medications, labs, intake/output, lines/drains/airway devices, ventilator settings, ASA status, procedure coding.
- **Outcomes:** Postoperative complications across 11 categories (cardiovascular, respiratory, airway, metabolic, neurological, etc.), ICU transfer (45.3% of EPIC cohort), in-hospital mortality (1.6%), summary LOS (mean 7±14 days). No explicit structured AKI/delirium outcome variables called out, though derivable from labs/dx codes.
- **Why it matters:** Largest-N surgical-patient database with both waveforms AND deep EHR linkage; the closest perioperative analogue to MIMIC's "waveforms + EHR" model. Best resource if the research question needs large sample size and rich EHR context more than maximal waveform modality breadth.

### MIMIC-IV Waveform Database (and MIMIC-III Waveform DB)
- **URLs:** https://physionet.org/content/mimic4wdb/0.1.0/ ; https://physionet.org/content/mimic3wdb/1.0/
- **Size:** MIMIC-IV-WDB v0.1.0: 200 records / 198 patients (pilot; ~10,000 records planned in full release), 12.8 GB. MIMIC-III-WDB: 67,830 record sets, ~30,000 ICU patients (Matched Subset: 22,317 waveform + 10,282 linked clinical records).
- **Access:** MIMIC-IV-WDB is **open** (ODC-ODbL, no credentialing); MIMIC-III-WDB requires standard PhysioNet credentialing/CITI training (consistent with MIMIC-III Clinical DB).
- **Signals/waveforms:** ECG, arterial blood pressure, respiration, PPG, often more — at high sampling rate (MIMIC-III ECG at 500 Hz post-decimation) from **ICU bedside monitors**, not the OR.
- **Relevance caveat:** This is an **ICU**, not intraoperative, waveform resource. Relevant to this survey only insofar as (a) a meaningful fraction of surgical/post-surgical patients pass through these ICUs postoperatively (cardiac surgery, major abdominal/vascular, transplant, neurosurgery), and (b) it is the standard comparator dataset every "MIMIC of the OR" paper (VitalDB, MOVER) benchmarks itself against. No native "surgical/perioperative subset" flag exists in the data; such subsets must be derived by linking to MIMIC-IV `hosp`/`icu` module surgery/procedure tables (e.g., used in cardiac-surgery AKI studies on MIMIC-IV).
- **Why it matters:** Useful as a postoperative-critical-care complement to OR-only datasets, and as the de facto benchmark/baseline dataset in the field, but should not be confused with a true intraoperative resource.

---

## Tier 2 — Large perioperative registries (rich EHR/outcomes, but NOT high-resolution OR waveforms)

### INSPIRE
- **URL:** https://physionet.org/content/inspire/1.4.2/ (latest as of this survey; v1.1 also referenced)
- **Full name:** INformative Surgical Patient dataset for Innovative Research Environment
- **Size:** ~130,000 surgical cases released publicly (50% random sample of ~260,000 total cases performed at Seoul National University Hospital, 2011–2020).
- **Access:** **Credentialed** — PhysioNet DUA + CITI training required.
- **Signals/waveforms:** **No high-resolution intraoperative waveforms.** Charted vitals only: OR vitals auto-recorded ~every 1 minute (some sources say every 5 min), anesthesia-machine settings (FiO2, inspired/expired anesthetic gas concentration, ventilator parameters) as time series, ward vitals 4–6×/day, ICU vitals hourly or per clinician order. This is a structured-tabular/EHR registry, not a waveform database.
- **EHR/labs/meds:** Very rich — demographics, ASA class, diagnosis and procedure codes, department, anesthesia type, labs from 6 months pre- to 6 months post-op (ABG, CBC, renal/liver function, coagulation, HbA1c, lactate, cardiac enzymes), inpatient medications.
- **Outcomes:** Hospital and ICU length of stay, in-hospital death; postoperative complication/diagnosis codes derivable. Published validation work demonstrates 30-day postoperative mortality prediction (AUROC 0.944).
- **Why it matters:** The best large-N (~130k), broad-coverage perioperative *outcomes/EHR* registry on PhysioNet — ideal for outcome-prediction modeling (mortality, LOS) at scale, but pair it with VitalDB/MOVER if waveform-level physiology is needed (note: different hospital sites, not natively linkable to VitalDB despite shared institution lineage in some years).

---

## Tier 3 — Focused/depth-of-anesthesia and autonomic-signal datasets (small N, mechanistic, OR or lab setting)

### Multimodal Physiological Indices During Surgery Under Anesthesia
- **URL:** https://physionet.org/content/multimodal-surgery-anesthesia/1.0/
- **Size:** 101 surgeries (2018–2022), 18,582 minutes of recording, 49,878 annotated nociceptive stimuli.
- **Access:** Restricted (PhysioNet Restricted Health Data DUA).
- **Signals:** ECG and electrodermal activity (EDA) waveforms; derived HRV and tonic-EDA autonomic indices (15 features + 15 derivative features per 5-s window). No invasive hemodynamic or BIS/EEG waveform.
- **Other data:** Nociceptive stimulus event annotations, anesthetic medication dosing across 9 drug classes, comparator ANI (Analgesia Nociception Index) monitor output.
- **Why it matters:** Purpose-built for intraoperative **nociception/analgesia-depth** modeling (distinct from depth-of-hypnosis/BIS), with stimulus-level event labels rarely found elsewhere.

### Multitaper spectra recorded during GABAergic anesthetic unconsciousness
- **URL:** https://physionet.org/content/eeg-power-anesthesia/1.0.0/
- **Size:** 54 subjects (10 healthy volunteers + 44 OR patients).
- **Access:** Restricted (PhysioNet Restricted Health Data DUA).
- **Signals:** EEG power spectral density (multitaper, 0–50 Hz, 100 freq. bins, 2-s epochs) during **propofol** and **sevoflurane** anesthesia.
- **Why it matters:** A clean, expert-curated EEG-spectral (depth-of-anesthesia mechanism) dataset spanning both an IV (propofol/TIVA) and a volatile (sevoflurane) agent.

### Electroencephalogram dynamics during unconsciousness mediated by GABAergic-anesthetics
- **URL:** https://physionet.org/content/eeg-gaba-anesthesia/1.0.0/
- **Size:** 4 subjects total (volunteer 64-ch EEG @5000 Hz under propofol; 3 surgical patients, frontal EEG 178–250 Hz, propofol ×3 / sevoflurane ×1).
- **Access:** Most restrictive in this survey — credentialed DUA **plus** contributor review of each proposed study, CITI "Data or Specimens Only Research" certification.
- **Signals:** Raw high-density EEG (up to 64-channel, 5 kHz) plus derived alpha (8–14 Hz)/slow-wave (0.3–4 Hz) power, drug concentration/infusion-rate time series.
- **Why it matters:** Highest raw-EEG sampling fidelity of any anesthesia dataset surveyed (5,000 Hz, 64-channel on the volunteer arm) — useful for fine-grained EEG-state/connectivity work on anesthetic unconsciousness, at the cost of very small N and the heaviest access friction.

### Behavioral and autonomic dynamics during propofol-induced unconsciousness
- **URL:** https://physionet.org/content/propofol-anesthesia-dynamics/1.0/
- **Size:** 9 healthy volunteers, ~3 h continuous recording each, 6.6 GB.
- **Access:** **Open** (Contributor Review Health Data License — no DUA gate beyond standard terms).
- **Signals:** ECG and EDA (not OR/surgical — a lab sedation study), with computer-controlled stepped propofol infusion (10 target-concentration stages) and behaviorally annotated loss-of-consciousness (LOC) / return-of-consciousness (ROC) timestamps.
- **Why it matters:** Open-access (no DUA), precisely staged propofol dose-response with clean LOC/ROC ground truth — useful as a mechanistic/validation dataset even though it's volunteers under sedation rather than surgical patients.

### Pulse Amplitudes from electrodermal activity collected from healthy volunteer subjects at rest and under controlled sedation
- **URL:** https://physionet.org/content/eda-rest-sedation/1.0/
- **Access:** **Open.**
- **Relevance:** Sedation (not full surgical anesthesia) autonomic/EDA dataset; tangential but occasionally used as a comparator for nociception/sedation-depth EDA work alongside the propofol-dynamics and multimodal-surgery-anesthesia datasets above.

### Electrodermal Activity of Healthy Volunteers while Awake and at Rest
- **URL:** https://physionet.org/content/electrodermal-activity/2.0/
- **Access:** Credentialed.
- **Relevance:** Baseline/control EDA reference data; not anesthesia-specific but used as a normative comparator in some of the above autonomic-monitoring anesthesia papers.

---

## Adjacent / general critical-care databases relevant via surgical-patient subsets

These are **not** anesthesia-specific and have no native "surgical only" flag, but are
commonly used in perioperative/postoperative-outcomes research because a large fraction
of their cohorts are surgical (especially cardiac-surgery, transplant, major-vascular,
and neurosurgical patients in the postoperative ICU period). Listed for completeness
since the task scope includes "MIMIC-IV/eICU perioperative/surgical subsets."

| Database | URL | Size | Waveforms? | Access | Note |
|---|---|---|---|---|---|
| MIMIC-IV (clinical/hosp/icu modules) | https://physionet.org/content/?topic=mimic-iv | ~300k patients (BIDMC, 2008–2019) | No (linkable to MIMIC-IV-WDB for a subset) | Credentialed | Surgical/perioperative cohorts must be derived via procedure/ICD codes; widely used for cardiac-surgery AKI, ACEi-timing, etc. |
| eICU Collaborative Research Database | https://physionet.org/content/?topic=eicu | >200,000 ICU admissions, 208 US hospitals (2014–2015) | No | Credentialed | 5-min-resolution charted vitals, multi-center (valuable for external validation); surgical subset derivable from APACHE/admission-diagnosis fields. |

Not on PhysioNet but frequently cited alongside the above in perioperative-medicine
reviews (noted for context only, not catalogued in depth here): **AmsterdamUMCdb**
(~23,000 ICU admissions, hosted on amsterdammedicaldatascience.nl) and **HiRID**
(~34,000 ICU patients, Bern, 600+ variables incl. waveforms, hosted on physionet.org
under its own listing) — both ICU-general rather than OR-specific.

---

## What does NOT exist on PhysioNet (gaps found during this search)

- No dedicated **standalone cerebral oximetry/NIRS** database (NIRS is present only as
  one parameter track inside VitalDB).
- No dedicated **pupillometry** intraoperative dataset.
- No PhysioNet-hosted **national/society outcomes registries** (e.g., NSQIP, ASA Closed
  Claims, UK NPDA) — these remain institutional/membership-access only, outside
  PhysioNet's open-science model.
- No large-N dataset combining **BIS/EEG + NIRS + full EHR + adjudicated postop AKI/
  delirium outcomes** in one place — researchers currently have to choose between
  waveform depth (VitalDB) and outcome/EHR depth (INSPIRE, MOVER) and link across sites
  or accept the gap.

---

## Top 4–5 databases for high-impact anesthesiology research — single most valuable unique asset

1. **VitalDB** — the only fully **open**, no-DUA dataset with simultaneous high-fidelity
   ECG, arterial-BP, pleth, capnography, **BIS/EEG depth-of-anesthesia, and NIRS cerebral
   oximetry** waveforms across >6,000 surgeries. Unmatched modality breadth at zero
   access friction.
2. **MOVER** — the largest-N (83,468 surgeries / 58,799 patients) surgical database that
   **fuses real bedside waveforms (ECG/ABP/pleth) with deep EHR** (meds, labs, postop
   complications, ICU transfer, mortality) — the "MIMIC of the OR" for sample size and
   EHR linkage.
3. **INSPIRE** — the deepest **longitudinal outcomes registry** for perioperative
   medicine (~130,000 cases, labs from 6 months pre- to 6 months post-op, validated
   30-day mortality prediction at AUROC 0.944) — best for outcome modeling at scale when
   waveform granularity isn't required.
4. **VitalDB Arrhythmia Database** — the only **anesthesiologist-validated, beat-level
   ECG-arrhythmia ground truth** (Cohen's kappa 0.93 across 5 raters) directly linked to
   intraoperative waveforms — the gold-standard label set for intraop arrhythmia
   detection algorithms.
5. **MIMIC-IV Waveform Database** — not OR-native, but the **open, no-DUA, standard
   benchmark** ICU waveform dataset every perioperative-waveform paper is compared
   against, and the only route to postoperative-ICU high-resolution waveforms (ECG, ABP,
   PPG, respiration) for surgical patients who progress to critical care.
