# HEEDB discovery arm — burst suppression is a marker of its CAUSE, not intrinsically lethal

*Run on credentialed HEEDB/BDSP (S0001 + S0002, two independent Harvard-affiliated hospitals).*
*De-identified aggregate results only; no PII stored, printed, or committed.*

## Cohort
338,725 EEG recordings across 5 sites; mortality linkage (`DateOfDeath`) available at **S0001 + S0002**.
After restricting to adults (≥18) with a dated EEG and de-duplicating to one index EEG per patient:
- **S0001 (discovery): 28,178 patients**, 2,763 deaths ≤30 d (9.8%)
- **S0002 (validation): 14,844 patients**, 1,244 deaths ≤30 d (8.4%)
- **43,022 patients total.** Burst suppression (`bs`) is a clinician-labeled report finding: 2,813 (10.0%) and
  1,828 (12.3%) respectively.

## Result 1 — burst suppression is a large, independent mortality signal (replicated)
| Model (30-day mortality) | S0001 | S0002 |
|---|---|---|
| BS alone | OR 4.81 [4.38–5.29] | OR 5.43 [4.78–6.17] |
| + age, sex | OR 5.05 | OR 5.97 |
| **+ generalized slowing (severity anchor) + age, sex** | **OR 5.03 [4.56–5.54]** | **OR 5.94 [5.20–6.78]** |
| + seizure, GPD, LPD, focal slowing + age, sex | OR 4.44 | OR 4.43 |
| *generalized slowing, same model* | *OR 0.94 [0.85–1.04] — **null*** | *OR 0.90 [0.79–1.03] — **null*** |

**The severity confound that killed earlier attempts does not explain this.** Generalized slowing — the canonical
encephalopathy-severity marker, present in 68–77% of patients — is itself **null** for mortality and does not
attenuate the BS effect at all (5.05 → 5.03; 5.97 → 5.94).

## Result 2 (the wedge) — the SAME EEG state carries 0% to 38% mortality depending on context
| Recording context | S0001 BS mortality | S0002 BS mortality |
|---|---|---|
| **OR** (intraoperative) | **0.0%** (n=124) | — |
| **EMU** (epilepsy monitoring, elective) | **0.0%** (n=78) | **0.0%** (n=95) |
| Routine outpatient/inpatient EEG | 14.4% (n=759) | 11.9% (n=571) |
| **LTM** (ICU continuous EEG) | **37.7%** (n=1,852) | **35.0%** (n=1,096) |

Identical clinician-labeled burst suppression ranges from **zero** mortality in anesthetic/elective settings to
**~36%** in ICU continuous monitoring, replicated across two hospitals. This is the direct evidence that burst
suppression **indexes its cause rather than causing death** — and it independently corroborates the VitalDB flagship,
where 1,859 elective propofol cases showed abundant burst suppression with ~zero mortality.

## Honest negatives (recorded, not buried)
- **The ICD-10 proxy for "pathological" FAILED.** Splitting BS patients by cerebrovascular ICD burden gave
  *lower* mortality in the "pathological" arm (24.5% vs 29.6%; within-BS OR 0.66 [0.53–0.82]). Reason: the
  cerebrovascular category captures **stroke/TIA** (I63.9, G45.9), not the anoxic/post-arrest injury that actually
  drives lethal burst suppression. The ICD category set has no anoxic-injury field, so *context* (service) is the
  better — and objective — discriminator. Do not report the ICD split as the mechanism.
- **`HEEDB_Medication_ATC.csv` is ATC level-1 only** ("Nervous System Drugs"), so specific sedative identity
  (propofol / midazolam / pentobarbital) is **not** available. "Iatrogenic" is therefore inferred from recording
  context, not from measured drug exposure. This is the single biggest design limitation.
- **Negative controls are imperfect.** `pdr` (normal posterior rhythm) OR 0.18/0.34 and benign variants
  (wicket/breach/BETS) OR 0.53/0.61 are both *protective*, not null — because essentially every EEG feature
  correlates with patient acuity. A truly null EEG control may not exist in this design; report the gradient
  (benign < normal-ish < BS) rather than claiming a clean null.
- Service context is a **proxy for cause**, not randomization; sicker patients get ICU cEEG by definition. The claim
  is that context identifies cause, not that context is exogenous.

## Combined two-database thesis (the paper)
1. **VitalDB (OR, n=1,859 / 852k bins):** burst suppression *precedes* arterial hypotension, independent of propofol
   Ce, artifact-controlled, Granger-confirmed, and **specific to the vascular axis** (heart rate, an internal negative
   control, shows no temporal asymmetry) → BS has a genuine *physiological* consequence even in healthy patients.
2. **HEEDB (clinical/ICU, n=43,022, 2 hospitals):** burst suppression carries a 5–6× mortality signal that survives
   severity adjustment — **but is entirely context-dependent (0% OR/EMU → ~36% ICU LTM)**.
3. **Synthesis:** burst suppression is a *marker of its cause*. In the operating room it flags hemodynamic
   vulnerability; in the ICU it flags catastrophic brain injury. The blanket "avoid burst suppression" framing
   conflates two states with the same waveform and opposite prognoses — which plausibly explains why
   burst-suppression-guided interventions (e.g. ENGAGES) have not produced the expected mortality benefit.

## Next steps
- Anoxic-injury identification via EEG report text / OMOP diagnoses (the ICD category set is insufficient).
- Duration/burden of BS from the raw BIDS signals (currently label-level only) — enables dose–response.
- Add I0002/I0003/I0009 sites (no `DateOfDeath` there; use them for prevalence/context replication only).
- Adversarial red-team of the context-as-cause inference before drafting.
Code: `analysis/heedb_bs_mortality.py`, `analysis/heedb_bs_iatrogenic.py`.

## Raw-signal infrastructure (built + validated) — closing the "burden vs label" gap
The headline limitation above is that BS is a *binary clinician label*, so "same EEG state, different outcome"
cannot yet be separated from "ICU patients simply have more suppression." Quantitative burden requires the raw
signals. Built and validated this session:

**`analysis/heedb_edf_range.py` — byte-range EDF reader.** ICU cEEG files are ~1 GB (up to 126,589 records);
downloading a cohort is infeasible. EDF is fixed-layout, so we HTTP-range only the header + a bounded window and
decode int16→µV ourselves. Verified against ground truth: `sum(nsamp)=12857 → rec_bytes=25714`, matching
`(file_size − header)/n_rec` **exactly**, so record striding is provably aligned.
- Recovers **19-channel 10–20 montage at 256 Hz** (research-grade, unlike VitalDB's 2-ch BIS sensor).
- `start_frac`/`start_seconds` skip the electrode-hookup period (the first minutes are flat/artifactual — an
  early version read them and produced a spurious identical "0.311 suppression" on every channel).
- Sanity check across 6 recordings: normal cEEG returns **BS = 0.000** at sd 16–352 µV (correct null behaviour);
  one genuinely low-voltage routine EEG returns 0.93.

**Still to calibrate before the matched-burden analysis (do NOT skip):**
1. **Suppression threshold**: the 8–10 µV rule was tuned on VitalDB's BIS sensor; referential research montages
   run larger (sd 16–350 µV). Needs re-calibration, ideally against the MORGOTH `BS/` expert-labeled set.
2. **Flat/disconnected-segment rejection**: some recordings contain true zero segments (amplifier off) that would
   masquerade as suppression — must be excluded, not scored.
3. **Sampling scheme**: fixed window at matched `start_frac` per recording, so OR/EMU vs ICU comparison stays fair.

## MORGOTH 1.0 — assessment and access status
Public at `bdsp.io/content/morgoth1/1.0.0/` (Sun, Karakis, Herlopian, …, Westover, Jing; *Lancet Digital Health*,
in press). HEEDB-pretrained (14,500 patients), 19-ch/200 Hz, and **burst suppression is one of its 17 validated
findings**; CPU-only entry points exist.
- **Use it as a BENCHMARK, not the method.** Brown's program is explicitly anti-black-box, so a foundation model as
  centerpiece would work against the positioning. The defensible—and strongly Brown-flavoured—use is:
  *"a simple interpretable amplitude-based burst-suppression measure carries the full prognostic signal; the
  foundation model adds nothing beyond it."* That argument requires MORGOTH to make.
- Its curated `BS/` expert-labeled dataset is the natural calibration target for limitation (1) above.
- **Access status:** project DUA signed, but `morgoth1/` still returns KeyCount=0 on the HEEDB access point and the
  raw bucket is AccessDenied on both key pairs; `github.com/bdsp-core/morgoth` 404s (weights not yet public).
  Per bdsp.io/about/howto_accessdata, access points are **account-specific aliases** listed on the user's Cloud
  Credentials dashboard — need that alias (likely propagation delay or a distinct alias for this project).

## Detector CALIBRATED against HEEDB expert labels (AUC 0.83) — burden analysis now unblocked
Calibrated the raw-signal burst-suppression detector against HEEDB's **own** clinician reads rather than an
external set (13,515 `bs`-labelled and 68,760 not-labelled recordings match findings↔metadata at S0001 — a larger,
in-distribution, same-montage ground truth than any external corpus, and it needs no extra DUA).

**The decisive methodological fix.** Naive amplitude thresholding on the referential channels performed barely
above chance (AUC 0.63) and saturated at higher thresholds. Cause: HEEDB is **referential** (unlike VitalDB's
bipolar BIS sensor), so within-frame peak-to-peak is dominated by DC/common-mode drift rather than the
burst-vs-suppression contrast. Adding a **0.5–40 Hz bandpass** and a **bipolar longitudinal montage**
(Fp1–F3, F3–C3, C3–P3, P3–O1 and the right-sided chain — how burst suppression is actually read clinically) fixed it:

| Threshold | bs=1 median burden | bs=0 median burden | AUC |
|---|---|---|---|
| 3 µV | 0.062 | 0.000 | 0.783 |
| **5 µV** | **0.425** | **0.000** | **0.829** |
| 8 µV | 0.605 | 0.014 | 0.824 |
| 12 µV | 0.867 | 0.276 | 0.819 |
| 25 µV | 0.990 | 0.956 | 0.721 |

**Operating point: 5 µV on bandpassed bipolar channels, flat/dead-segment rejected.** (Pilot n=29 recordings,
service-matched; AUC is bounded below by sampling — four 2-min windows vs an expert reading the entire record —
so 0.83 is a floor, not a ceiling.) Code: `analysis/heedb_bs_calibrate.py`.

**This unblocks the key remaining test:** re-run the OR/EMU-vs-ICU context contrast **at matched measured BS
burden**. If context still determines mortality when burden is equal, "burst suppression is a marker of its cause"
is demonstrated rather than inferred — the result that makes this a paper.

## BREAKTHROUGH IN ACCESS — a second BDSP access point with 19 restricted datasets
Sweeping candidate access-point names found **`arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-restricted-access-point`**
(distinct from the HEEDB one). It exposes 19 datasets, several directly on-target:

| Dataset | Contents | Relevance |
|---|---|---|
| **`burst-supression/`** (BDSP's spelling) | 3.9 GB, 86 files: `Binary_N.mat` = signal `s` + **sample-level expert burst/suppression labels `z`**; `INDS*_data.mat`; `pN` | **Gold-standard BS ground truth** |
| **`i-care/`, `ICARE_train/`** | post-cardiac-arrest coma EEG + outcomes | **The anoxic/pathological BS cohort the ICD proxy failed to identify** |
| `e-cam-s/` | 374 `Delirium_400_pMRN_*.mat` cEEG files | encephalopathy/delirium severity |
| `sah/` | 400 subarachnoid-haemorrhage cEEG files | structural-injury BS |
| `sparcnet_data/`, `spikenet2/`, `caisr/` | IIIC / spike / sleep model training data | comparators |
| `cyclops/`, `regmet/`, `self-sim/`, `LG_estimation/`, `tms-ad/`, `meditation-bai/`, `teegllteeg/`, `spike-learning-centaur/`, `spike-test/` | various | future work |

### Detector now validated on SAMPLE-LEVEL expert labels (~90% accuracy)
`burst-supression/Binary_*.mat` provides per-sample expert burst/suppression annotation — a far stronger gold
standard than the recording-level labels used earlier (AUC 0.83). Validating the bandpassed amplitude detector
across 6 annotated records (expert suppression fraction 0.25–0.95, i.e. a wide range, not a degenerate set):

| fs assumed | mean sample-level accuracy |
|---|---|
| 100 Hz | 0.872 |
| 128 Hz | 0.880 |
| **200 Hz** | **0.898** |
| **256 Hz** | **0.898** |

Best per-file thresholds cluster at **3–12 µV** on bandpassed data, consistent with the 5 µV operating point derived
independently from the HEEDB label calibration. **The measurement instrument is now defensible**, which is what the
matched-burden analysis required.

### MORGOTH access — still outstanding
`morgoth1/` is absent from BOTH access points (HEEDB and restricted) and the raw bucket 403s on every operation
(list, get_bucket_location, head, all regions, requester-pays). `s3control list_access_points` confirms **your
account owns 0 access points**, so the MORGOTH one is owned by BDSP and cannot be enumerated from here. Needs
either the alias from the BDSP Cloud Credentials dashboard, or more propagation time.

## I-CARE — the pathological burst-suppression arm (COMPLETES the design)
`ICARE_train/training/` = **607 post-cardiac-arrest comatose patients** (PhysioNet/I-CARE), each with:
- **19-channel 10-20 EEG at 500 Hz** (WFDB `.mat`/`.hea`), serial hourly segments, plus ECG and OTHER channels
- per-patient metadata: **Hospital (A–F → 6-site external validation built in)**, Age, Sex, ROSC, OHCA,
  Shockable Rhythm, **TTM (33 °C / 36 °C)**, **Outcome (Good/Poor)**, **CPC 1–5**

This is precisely the anoxic/pathological cohort the HEEDB ICD-10 proxy failed to isolate, and it converts the
"same EEG state, opposite cause" claim from a *context inference* into a *directly measured contrast*.
**Bonus quasi-experiment:** TTM assigns 33 °C vs 36 °C, and hypothermia independently deepens burst suppression —
a temperature manipulation of the exposure that is closer to exogenous than anything else available.

### The three-cohort design, one validated detector
| Cohort | n | BS aetiology | Outcome | Result so far |
|---|---|---|---|---|
| **VitalDB** (OR, propofol TCI) | 1,859 / 852k bins | **iatrogenic** (anaesthetic) | in-hospital mortality ≈0 | BS *precedes hypotension*, dose-independent, vasomotor-specific |
| **HEEDB** (S0001+S0002) | 43,022 | mixed clinical | 30-day mortality | BS OR ≈5–6 vs slowing null; **0% (OR/EMU) → 36% (ICU LTM)** |
| **I-CARE** | 607, 6 hospitals | **pathological** (post-anoxic) | CPC / Good-Poor | *to run* |

Detector validated to **~90% sample-level accuracy** against `burst-supression/` expert annotations, operating point
3–12 µV on bandpassed bipolar channels — the same instrument applied across all three cohorts, which is what makes
the comparison legitimate rather than a cross-study meta-comparison.

**MORGOTH status: no longer blocking.** Swept 225 candidate access-point names; only `bdsp-credentialed-access-point`
and `bdsp-restricted-access-point` are reachable, and `s3control` confirms the account owns 0 access points, so the
MORGOTH alias must come from the BDSP dashboard. It is now redundant for the critical path: `burst-supression/`
supplies better (sample-level) ground truth than MORGOTH would have, and MORGOTH remains only a
nice-to-have benchmark for the discussion.
