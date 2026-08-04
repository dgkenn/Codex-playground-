# Is there already a validated age/sex normative EEG model we should be using?

*Written 2026-07-31. Every record below was pulled with `curl` against NCBI E-utilities, Europe PMC REST,
the OpenNeuro GraphQL API and the Synapse REST API, and parsed — never through a WebFetch summary (error
catalogue rules 25 and 39). Where a fact could not be verified, it says so.*

---

## The short answer

**Yes — at least six, and one of them is genuinely excellent. None of them is usable as *our* reference, for
two independent reasons, and the good news is buried in the second one.**

1. **The well-validated ones are commercial.** NeuroGuide, Neurometrics, BrainDx, SKIL and qEEG-Pro (the
   last is FDA-approved) are products. The two best academic databases release data "on request" only.
2. **Not one of them models the aperiodic exponent.** Every existing normative EEG system is band power —
   or log source spectra — per electrode. Our own measurement (E43 and its band decomposition) says the
   quantity that should go on a normative scale is `exponent_low` (1–20 Hz), and no normative database in
   the field carries it.

**But the second reason has an exit.** The best open resource, **HarMNqEEG**, shares *cross-spectral
tensors* rather than band summaries — and the diagonal of a cross-spectrum is the power spectrum. Another
group has already done exactly this: **PMID 42040156 estimates aperiodic components on 1,965 HarMNqEEG
participants aged 5–100.** So the shared data is demonstrably sufficient for our measure. That converts
"nobody has a normative model for the exponent" from a dead end into a **build order on an already-harmonised
multinational deposit.**

---

## 0. CORRECTION — this document searched the literature and not the project's own record

**Added 2026-07-31, after the fact.** Everything below came from PubMed and public deposit APIs. It should
have started with `MASTER_PLAN.md`, which **already named a normative reference** and which I did not check:

> §9.28: *"**LENS on BDSP — 'Lifespan and Sleep-Stage-Resolved Normative EEG Background' — is the right
> shape**, being lifespan rather than paediatric, and is the deposit to pursue."*
> §3.1: *"**LENS** … is a genuine normative reference for the age question in E16/E17, and is credentialed."*

So the project had already identified a candidate, on **the same BDSP platform that serves HEEDB**, and the
answer given to the investigator was assembled entirely from external sources.

**Access status, probed rather than assumed (2026-07-31):** LENS is **NOT reachable with current
credentials.** It appears at none of the three access points —
`bdsp-credentialed-access-point` (8 prefixes: ECG, EEG, EHR, Imaging, NAX, OMOP, PSG, PatientMergeHistory),
`bdsp-credentialed-projects-ap` (37 project prefixes), `bdsp-restricted-access-point` (19) — and not inside
`EEG/` (HEEDB_Metadata, bids, eeg-metadata) or `PSG/` either. **It requires a separate BDSP access request,
which is an investigator action, not something this session can do.**

That does not change §1's conclusions — none of the six public systems models an aperiodic measure, and
LENS's own contents are unverified here, so whether it would either is unknown. But it changes the *order*
the question should have been answered in, and LENS belongs at the top of any access-request list.

---

## 1. What exists, verified

| resource | n | ages | sex modelled? | data access | models the exponent? |
|---|---|---|---|---|---|
| **HarMNqEEG** (PMID 35398285, *Neuroimage* 2022) | **1,564** (1,965 in the 2026 re-use) | lifespan; 5–100 in PMID 42040156 | **unverified** — see below | **open**, Synapse `syn26712693`, free account needed | not in the paper, but **the data supports it** (PMID 42040156) |
| **qEEGt / CHBMP** (PMID 32848689) | Cuban Human Brain Mapping | age-corrected | age only, as stated | dockerised on CBRAIN | no — log **source** spectra |
| **ISB-NormDB** (PMID 34975376) | **1,289** (553 M / 736 F) | 4.5–81 | **yes — separate male and female models** | corresponding author "on reasonable request"; authors at iMediSync | no — band power |
| **Taiwan normative database** (PMID 36831893) | 260 | 10-year bands | partly | "on request" | no |
| **EEG growth chart** (PMID 38537603) | 1,056 | 1 month – 18 y | — | — | no — a CNN functional brain age, paediatric, N1/N2 sleep |
| **NeuroGuide / Neurometrics / BrainDx / SKIL / qEEG-Pro** | — | lifespan | yes | **commercial**; qEEG-Pro is FDA-approved | no |

**On HarMNqEEG's covariate model, an honest limit.** The abstract states *"developmental equations for the
mean and standard deviation of qEEG traditional and Riemannian DPs were calculated using additive
mixed-effects models"* — it names age. The paper is **not open access** (Europe PMC: `isOpenAccess: N`), so
**whether sex is a term in those equations is unverified here** and must be checked before the model is
relied on. Do not repeat "HarMNqEEG is age and sex" until someone has read the methods.

**What is verified about it**, because it was queried directly:

* Synapse project `syn26712693`, "Multinational EEG Cross-Spectrum", created 2022-01-10.
* One child folder `ShareRawData` → **14 study folders**: Barbados, Bern, CHBMP, Chengdu, Chongqing,
  Colombia, Cuba2003, Cuba2004, Cuba90, Germany, Malaysia, NewYork, Russia, Switzerland. That matches the
  paper's "9 countries, 12 devices, 14 studies".
* Contents are **per-subject `.mat` files** (CHBMP folder: 50 of them).
* **Anonymous download returns HTTP 403** — `"Anonymous users have only READ access permission"`. A free
  Synapse account is required. **That is a decision for the investigator, not something to do unilaterally.**

---

## 2. The structural gap, stated precisely

Search, PubMed, normative-modelling terms **AND** EEG **AND** aperiodic/spectral-exponent/1-over-f:
**13 hits total.** Read individually, every one uses "normative" descriptively — *"normative age-related
decreases were attenuated in ADHD"* (PMID 42312350) — rather than describing a normative reference
resource. **The count of published normative *databases* that model the aperiodic exponent is zero.**

Meanwhile the age-and-sex **effect** literature on the exponent is real, and it does not agree with itself:

* **PMID 42107212** (*Dev Cogn Neurosci* 2026, registered report, Healthy Brain Network) — 1,426 children
  5–18. Exponent declines linearly with age across all participants; **the decline is steeper in females
  in some conditions**; ADHD status does not move it.
* **PMID 34781249** — longitudinal, n = 186 at ages 13 and 15. Age-related reductions in **both** offset and
  exponent, **and significant sex differences in both**.
* **PMID 39235879** (Bucharest Early Intervention Project) — **nonlinear** age trajectories in both, and a
  **sex difference in offset but explicitly not in exponent**.

Three studies, three different answers on whether sex moves the exponent. **That is a reason to fit sex
ourselves on a large cohort rather than to import somebody's coefficient** — and it is a reason to expect
the sex term to be small.

---

## 3. Two numbers this search produced that change our own plan

### (a) The exponent's five-year reliability is 0.668 — so the trait ceiling is ~0.82

**PMID 42395346** (*Front Aging Neurosci* 2026) measured exactly the quantity E38 taught us to measure
first, on public data:

| measure | EO/EC state sensitivity (Cohen's d) | five-year stability (ICC) |
|---|---|---|
| posterior alpha relative power | **1.553** | **0.843** |
| theta/beta ratio | −0.342 | 0.772 |
| alpha peak frequency | 0.238 | 0.734 |
| **aperiodic exponent** | **−0.761** | **0.668** |

Two consequences, and they point in opposite directions, which is why both matter.

**The reassuring one.** ICC 0.668 over *five years* caps a trait correlation at sqrt(0.668) ≈ **0.82**. That
is a ceiling we are nowhere near — E41's target effects live around 0.29 — so long-run instability is not
what is limiting Challenge B. Short-interval reliability is much higher again (ICC 0.77–0.88 for the
aperiodic component across two MEG sessions, PMID 38820994), and a **2–3 minute recording is enough**
(same paper; PMID 32425762 gets stable FOOOF parameters from 2 minutes). **Our reference does not need long
recordings.**

**The alarming one.** `NORMAL_REFERENCE_COVARIATES.md` §7 lists eyes-open-versus-closed as a "known unknown".
It is no longer unknown: **d = −0.761 on the exponent**, which is large, and larger than any comorbidity
effect we should expect. HEEDB does not record eye state. This is now the **leading uncontrolled covariate
in the reference**, ahead of medication, and second only to vigilance. It must be moved out of §7 and into
the design — either detected in-signal alongside wake state, or declared as the reference's principal
limitation. It cannot stay on a list of vague unknowns.

### (b) Aperiodic correction can *remove* age dependence — which is a threat to Q16

**PMID 42294963** (*Clin EEG Neurosci* 2026) corrected the posterior theta/alpha ratio for the aperiodic
component and reported that in a normative cohort of 587 adults aged 20–79, the corrected ratio was
**"completely age-independent (r = 0.000)"**.

Q16's step-4 regression asks how much between-subject variance age, sex, comorbidity and medication explain,
and `REFERENCE_AGAINST_ALL_THREE.md` §2 converts that R² into the Challenge B gain via 1/sqrt(1−R²).
**A measure engineered to be age-independent has R² ≈ 0 and therefore no gain.** The two measures we are
carrying sit on opposite sides of this: the raw exponent is strongly age-dependent (three studies above),
while aperiodic-*corrected* quantities may not be. **Run Q16's regression on `exponent_low` and
`lempel_ziv` separately and do not pool them** — they may have genuinely different covariate structure, and
a pooled R² would hide it.

---

## 4. One open dataset worth pulling now, verified live

**OpenNeuro `ds005385`** — *"Resting-state EEG data before and after cognitive activity across the adult
lifespan and a 5-year follow-up"* (Wascher, Schneider, Gajewski, Getzmann; Dortmund Vital Study).
Queried through the OpenNeuro GraphQL API, snapshot 1.0.3:

* **608 subjects**, 2 sessions, 17,541 files, 79.5 GB
* `participants.tsv` carries **`age`, `sex`, `handedness`** and per-session participation flags
* **376 F / 232 M**; age **20–70**, by decade: 20s **137**, 30s **111**, 40s **111**, 50s **140**,
  60s **95**, 70 **14**
* **no credentials required**

Three things it gives us that nothing else on this list does. It is an **independent adult age+sex reference**
to check a HEEDB-derived reference against — the held-out-site property `NORMAL_REFERENCE_COVARIATES.md` §8
says the whole exercise exists to obtain. Its **two sessions five years apart** let us reproduce the ICC in
§3(a) on our own estimator rather than citing it. And it is almost certainly the cohort PMID 42395346 used
(same design, same interval, "publicly available") — **though that identification is inferred, not verified;
the paper is not yet in PMC.**

Its limits are real and should be stated with it: healthy volunteers, not clinically-read-normal — so it does
**not** substitute for the HEEDB cohort's acquisition-matching argument (`NORMATIVE_EEG_STATE_OF_THE_ART.md`
§3a) — and it stops at 70, where HEEDB reaches 90.

---

## 5. Recommendation

1. **Do not adopt any existing normative database as the reference.** The validated ones are commercial, the
   academic ones are request-gated, and *none* carries our measure. Importing one would mean changing the
   measure to fit the reference, which is backwards.
2. **Do adopt HarMNqEEG as the methodological template, and cite it as such.** Harmonisation of batch
   effects across devices and sites, developmental equations for **both** the mean and the SD, and Riemannian
   handling of cross-spectra are all solved problems there. We should reuse the approach and say so.
3. **Ask the investigator whether to open a free Synapse account** for `syn26712693`. If yes, it is a
   multinational external validation set for a HEEDB-derived reference — 14 studies, 9 countries, 12 devices
   — and PMID 42040156 has already demonstrated the aperiodic component is estimable from it.
4. **Pull `ds005385` now.** Free, no gate, and it delivers the reliability number that bounds Challenge B
   plus an independent age/sex check.
5. **Promote eyes-open/closed out of "known unknowns".** d = −0.761 makes it the largest uncontrolled term
   in the reference after vigilance, and the wake detector and the eye-state detector should be built as one
   object and frozen together.
6. **Split Q16's regression by measure.** §3(b) is a live threat to the entire conditional-reference
   rationale, and it costs nothing to test both measures separately rather than discover it afterwards.

**The position this leaves us in, honestly stated.** We are not inventing normative EEG — it is fifty years
old and better developed than this project's documents assumed a week ago. What is genuinely unoccupied is
the intersection: a normative reference **for an aperiodic measure**, **on clinically-acquired EEG**,
**conditioned on medication**, used as a **state** origin rather than a trait screen. Each of those four is
individually defensible and the field has done none of them together. That is a much stronger claim than
novelty, and unlike novelty it survives someone checking.

---

## Verified record list

| PMID | what it is | why it is cited here |
|---|---|---|
| 35398285 | HarMNqEEG, *Neuroimage* 2022 | 1,564 subjects, 9 countries, 12 devices, 14 studies; open cross-spectra on Synapse |
| 42040156 | ω-α-NET, *Natl Sci Rev* 2026 | **aperiodic components estimated on 1,965 HarMNqEEG subjects aged 5–100** |
| 32848689 | qEEGt, *Front Neuroinform* 2020 | decades-validated, age-corrected source-spectra SPMs on CBRAIN |
| 34975376 | ISB-NormDB, *Front Neurosci* 2021 | 1,289 subjects, explicit **sex-differentiated** models; data on request |
| 36831893 | Taiwan database, *Brain Sci* 2023 | 260 subjects; also names the commercial estate |
| 38537603 | EEG growth chart, *EBioMedicine* 2024 | 1,056 children, functional brain age |
| 40946930 | multi-site normative framework, *Brain Res Bull* 2025 | batch effects and montage inconsistency across sites |
| 42395346 | *Front Aging Neurosci* 2026 | **exponent ICC 0.668 at 5 y; EO/EC d = −0.761** |
| 38820994 | *Clin Neurophysiol* 2024 | aperiodic ICC 0.77–0.88 across sessions; 2–3 min sufficient |
| 32425762 | *Front Integr Neurosci* 2020 | stable FOOOF parameters from 2-minute recordings |
| 42294963 | *Clin EEG Neurosci* 2026 | aperiodic-corrected TAR **age-independent (r = 0.000)**, n = 587 |
| 42107212 | *Dev Cogn Neurosci* 2026 | n = 1,426; exponent declines with age, steeper in females |
| 34781249 | *Dev Cogn Neurosci* 2021 | sex differences in **both** offset and exponent |
| 39235879 | *Dev Psychol* 2025 | nonlinear age; sex difference in offset, **not** exponent |
