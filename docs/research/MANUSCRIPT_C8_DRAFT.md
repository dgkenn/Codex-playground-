# Oscillometric Cuff Monitoring Systematically Underestimates Intraoperative Hypotension and Its Harms: A Two-Cohort Study

*Draft manuscript — Anesthesiology/JAMA-family structure. All quantitative claims are drawn from the source
analyses (`docs/research/20`); no number is invented. Discovery cohort: VitalDB. Validation cohort: INSPIRE.
Both Seoul National University Hospital — same institution, different granularity/scale.*

---

## Abstract

**Background.** Intraoperative hypotension is associated with acute kidney injury, myocardial injury, and death,
and mean arterial pressure (MAP) thresholds near 65 mmHg guide treatment. This evidence base is built
overwhelmingly on intermittent oscillometric cuff (non-invasive) blood pressure, which is known to be inaccurate
at low pressures. Whether cuff monitoring systematically misclassifies hypotension against a continuous
arterial-line reference — and whether that misclassification attenuates the measured association between
hypotension and harm — has not been quantified with hard outcomes.

**Methods.** We used two surgical cohorts from the same institution that co-record oscillometric cuff MAP and
invasive arterial-line MAP. In VitalDB (high-resolution waveforms) we quantified, against a
regression-to-the-mean-safe, artifact-hardened arterial reference, the cuff's sensitivity for arterial-defined
hypotension (MAP<65). In INSPIRE (≈130,000 operations, minute-level data) we replicated the discrepancy at scale
and tested, within the same operations, whether intraoperative hypotension defined by arterial line versus by
cuff differs in its association with in-hospital mortality, AKI, hyperlactatemia, myocardial injury (troponin),
a composite, and ICU admission. A matched-cadence analysis (arterial values sampled only at cuff-measurement
times) isolated measurement bias from sampling frequency.

**Results.** In VitalDB (2,109 paired readings, artifact-hardened), the cuff detected only **59%** of
arterial-defined hypotension at MAP<65, **47%** at <60, and **34%** at <55, over-reading by ~+22 mmHg at severe
hypotension (overall Bland-Altman bias −0.2 mmHg). The discrepancy and its harm-attenuation replicated in an
external US multi-center ICU cohort (eICU, 154 hospitals, 24,691 co-recording stays: cuff missed 47% of
arterial-defined hypotension at MAP<65 and 68% at <55, over-reading at low pressure; mortality association art
OR 5.40 vs cuff 4.86). In INSPIRE (47,533 operations co-recording both), the cuff
missed **71%** of arterial-defined hypotension at MAP<65. Within the same operations (n=28,349), the association
of intraoperative hypotension with in-hospital mortality was substantially stronger when measured by arterial
line than by cuff (adjusted OR **2.09** [1.68–2.60] vs **1.48** [1.21–1.81]); the same attenuation was seen for
hyperlactatemia (1.91 [1.79–2.05] vs 1.46 [1.36–1.56]; non-overlapping), AKI (1.34 vs 1.26), a death-or-AKI
composite (1.86 vs 1.47), and ICU admission (2.63 vs 1.74); myocardial injury showed no attenuation. The
mechanism was visible in-data: the cuff-defined "non-hypotensive" group had a higher event rate than the
arterial-defined non-hypotensive group, reflecting misclassified hypotensive patients. The matched-cadence
analysis confirmed the attenuation persisted at identical measurement times (mortality 2.27 vs 1.90), isolating
it to measurement bias rather than sampling frequency. A cuff MAP of 65 corresponded to a true arterial MAP of
~68 (37% actually <65); treating at cuff MAP<70 recovered sensitivity from 57% to 75%.

**Conclusions.** Oscillometric cuff monitoring misses most intraoperative hypotension and, because the field's
evidence base rests on it, has systematically underestimated the harm of hypotension. Effect sizes and "safe"
MAP thresholds derived from cuff data warrant upward revision; where arterial monitoring is unavailable, a higher
cuff treatment threshold (MAP<70) better approximates the true target.

---

## 1. Introduction
Intraoperative hypotension is among the most studied modifiable exposures in perioperative medicine, with a large
literature linking cumulative time below MAP thresholds (commonly 65 mmHg) to AKI, myocardial injury after
non-cardiac surgery (MINS), and mortality (Walsh 2013; Salmasi 2017; Sessler; VISION). Almost all of this
evidence uses intermittent oscillometric (cuff) blood pressure, because arterial lines are reserved for
higher-risk cases. Oscillometric devices are known to be inaccurate at the extremes of blood pressure, tending to
over-read at low pressures. If this measurement error causes the cuff to miss true hypotension, then (i) patients
are misclassified at the point of care and (ii) the entire evidence base — effect sizes, dose-response curves,
and threshold values — is derived from a systematically mismeasured exposure, biasing the apparent harm toward
the null.

We quantify both, using two surgical cohorts from the same institution that uniquely co-record cuff and
arterial-line MAP: VitalDB for a clean, high-resolution characterization of the measurement discrepancy, and
INSPIRE for large-scale replication and, critically, for testing whether the measurement choice changes the
observed hypotension–harm association against hard clinical outcomes.

## 2. Methods
### 2.1 Cohorts
- **VitalDB** (discovery) — 6,388 surgical cases with high-resolution intraoperative waveforms and 2-second
  numeric trends; 3,106 co-record Solar8000 arterial-line MAP and cuff (NIBP) MAP.
- **INSPIRE** (validation) — ≈130,000 operations with minute-level intraoperative vitals, labs, medications,
  ICU/mortality timestamps, and ICD-10 diagnoses; 47,533 co-record arterial and cuff MAP.
- **eICU Collaborative Research Database** (external validation) — ICU stays from ~200 US hospitals. We used the
  24,691 stays (154 hospitals) co-recording invasive arterial mean (`systemicmean`) and oscillometric mean
  (`noninvasivemean`) pressures, with hospital-discharge mortality as the outcome. A different country, a
  different care setting (ICU vs intraoperative), and different monitors — a stringent external test of whether
  the cuff–arterial discrepancy and its harm-attenuation are device-physics phenomena rather than local artifact.

### 2.2 Measurement-discrepancy analysis (VitalDB)
Cuff measurements were taken as NIBP value-change points (the monitor holds the last cuff value between cycles).
The arterial reference was the **median of arterial MAP within ±60 s** of each cuff reading (≥15 samples),
smoothing transient arterial-line artifacts. The primary, regression-to-the-mean-safe metric was cuff
**sensitivity** for arterial-defined hypotension (conditioning on the arterial reference, never on the cuff).
Bias by arterial band was reported with the arterial value on the reference axis.

### 2.3 Outcome-attenuation analysis (INSPIRE)
For operations co-recording both signals, intraoperative hypotension was defined separately by arterial line
(≥3 readings <65 mmHg) and by cuff (≥1 reading <65). Because arterial lines are placed in sicker patients, the
primary design was **within-operation** comparison of the two exposures against the same outcome — the relative
attenuation is confounder-controlled by construction. Outcomes: in-hospital mortality; KDIGO AKI (baseline vs
7-day peak creatinine); hyperlactatemia (peak ≥2 mmol/L); MINS (postop troponin-I≥0.04 or T≥0.02 µg/L);
death-or-AKI composite; ICU admission. Odds ratios were computed crude and adjusted for age, ASA, operative
duration, and baseline creatinine. A **matched-cadence** analysis evaluated arterial MAP only at cuff-measurement
times to isolate measurement bias from sampling frequency.

### 2.4 External validation (eICU)
In the eICU cohort we repeated, within the same ICU stays, (i) the discordance analysis — cuff sensitivity for
arterial-defined hypotension (MAP<65/60/55), the arterial reference being the median arterial MAP within ±5 min
of each cuff reading, conditioning only on the arterial value (RTM-safe) — and (ii) the harm-attenuation analysis
— arterial-defined (≥3 readings <65) versus cuff-defined (≥1 reading <65) hypotension against hospital-discharge
mortality. Both signals were joined per stay by a memory-safe streaming merge on offset-sorted vitals.

## 3. Results
### 3a. The cuff misses most intraoperative hypotension (VitalDB)
In 1,079 co-recording cases (5,903 paired readings, artifact-hardened, Bland-Altman bias −0.2 mmHg), cuff
sensitivity for arterial-defined hypotension was **56.2%** [52.9–59.4] at MAP<65 (missed 44%), **41.7%** at <60,
and **26.9%** [22.5–31.8] at <55 (missed 73%). The cuff over-read by **+30.6 mmHg** at arterial MAP 20–55 and
was near-unbiased in the normal range (see threshold table). At the case level, 60% of cases with any
arterial-defined hypotension had ≥1 episode missed by the cuff.

### 3b. Replication at scale (INSPIRE)
47,533 operations; cuff missed 71% of arterial-defined hypotension (MAP<65). (INSPIRE's larger magnitude vs
VitalDB reflects greater artifact in minute-level arterial data; VitalDB provides the clean estimate.)

### 3c. Cuff monitoring underestimates the harm of hypotension (INSPIRE, within-operation)
[TABLE — adjusted OR art vs cuff: mortality 2.09 vs 1.48; hyperlactatemia 1.91 vs 1.46; AKI 1.34 vs 1.26;
composite 1.86 vs 1.47; ICU 2.63 vs 1.74; MINS 1.48 vs 1.50 (no attenuation).]
Mechanism: cuff-defined non-hypotensive group has higher event rate than arterial non-hypotensive (AKI 6.5% vs
5.6%), reflecting misclassified hypotensive patients.

### 3d. It is measurement bias, not sampling frequency (matched-cadence)
At identical cuff-measurement times, arterial-defined hypotension still predicted harm more strongly (mortality
2.27 vs 1.90; hyperlactatemia 2.41 vs 1.88, non-overlapping), and detected hypotension in ~22% more operations.

### 3e. The vasopressor treatment gap (mechanism of harm)
Among 20,009 operations with arterial-defined hypotension, at matched true (arterial) severity, hypotension the
cuff detected was more likely to be treated with a vasopressor than hypotension it missed (min-art 55–65: 71.3%
vs 63.5%; adjusted for severity/burden/age/ASA, cuff-detected → vasopressor **OR 1.34 [1.25–1.44]**). The cuff
also lagged: among arterial-hypotension episodes, the cuff never registered <65 in 64%, and among those it
eventually detected the median delay was 9.1 min (VitalDB). Thus the measurement error propagates to a treatment
omission at the same true severity — the mechanism linking mismeasurement to the attenuated harm associations.

### 3f. Threshold miscalibration and a practical correction
A cuff MAP of 65 corresponded to a true arterial MAP of ~68 (37% actually <65). Guideline cuff<65 detected 57%
of true hypotension; cuff<70 detected 75% (false-trigger 8%). Where arterial monitoring is unavailable, a cuff
treatment threshold of MAP<70 better approximates the true <65 target.

### 3g. Preventing the harm — tested interventions
(1) **Corrected trigger:** guideline cuff<65 flags only 52% of patients with true hypotension and harm; cuff<70
flags 68% (recovering 34% of the missed) at a false-alarm rise from 17% to 30% in true-normotensives. (2)
**Decomposition:** 66% of missed hypotension is sampling gaps (cuff not cycling) and 34% is measurement over-read
— so more frequent cycling addresses the majority but not the measurement fraction (episodes last a median 2 min;
5-min cycling samples only 77% of ≥2-min episodes, ≤2-min cycling 100%). (3) **Targeting by harm yield:** the miss
is pervasive (>50% across ASA/age/duration/sex), so we target by number-needed-to-monitor (art-lines per
harm-associated missed hypotension surfaced): 18 (urology), 21 (ASA≥3), 30 (general surgery / >4 h) vs 83–198
(ASA 1, OB/gyn). We formalize this as a bedside arterial-line decision tool (**Box 1**): rather than fix
categories by fiat, the tool reads observed placement rates to auto-route already-standard cases and applies a
data-derived risk score only in the contested gray zone, judged against the full composite of A-line benefits.
Escalation is preoperative, since an early cuff signal is a weak trigger (early cuff<75 → later hypotension
PPV 40%). **Three-part package: detect** (cycle ≤2–3 min + treat at MAP<70), and where yield is high, **measure
directly** (arterial line, per Box 1).

> **Box 1 — Arterial-line decision tool (three layers, data-anchored; INSPIRE)**
>
> **Layer 1 — auto-place (revealed practice; the decision is already made).** Categories where observed A-line
> placement is near-universal, identified from the data (≥85% placement) rather than declared: **cardiothoracic
> 97.0%, neurosurgery 94.9%, interventional-radiology/hybrid 91.3%**, and **any ASA ≥ 4** (placement 89–94%
> regardless of specialty). Place an arterial line; the tool does not deliberate.
>
> **Layer 2 — place for a specific established indication (any one):** beat-to-beat control (aortic cross-clamp,
> cerebral/carotid perfusion, pheochromocytoma) · frequent ABG/serial labs (respiratory failure, one-lung
> ventilation, massive transfusion) · NIBP unreliable (morbid obesity, arrhythmia, severe PAD, positioning) ·
> active vasoactive titration · dynamic goal-directed monitoring.
>
> **Layer 3 — gray zone (no Layer-1/2 trigger): risk score.** Consider an arterial line if **≥ 2** of:
> **ASA ≥ III · Age ≥ 65 · Long case > 4 h · Serious surgery (urologic / major-abdominal / cardiothoracic /
> major-vascular / transplant) · Emergency.** Score AUC 0.75 for harm-associated cuff-missed hypotension;
> at ≥2 it flags 44% of gray-zone cases and captures 84% of that harm (NNM 25). Judged against the **composite**
> of realized A-line benefits (hypotension detection, vasoactive titration, serial ABG/labs, unreliable NIBP),
> ≥2 carries an NNM of **1.4** — most lines placed at threshold serve ≥1 concrete benefit, and composite benefit
> rises monotonically with score (39→53→65→81→95→98% across score 0→5). Below threshold: cuff cycled ≤2–3 min,
> treat at MAP < 70. *(The tool self-calibrates — re-estimating placement rates locally re-derives Layer 1. A
> memorable mnemonic for the Layer-3 factors is being finalized.)*

## 3h. External validation — the discrepancy is not local (eICU, 154 US hospitals)
In 24,691 ICU stays co-recording arterial and cuff mean pressures across 154 US hospitals, the cuff detected only
**53%** of arterial-defined hypotension at MAP<65 (missed 47%) and **32%** at <55 (missed 68%) — closely matching
VitalDB (missed 44%/73%) — and over-read at low pressure (bias +13.1 mmHg at arterial 20–55, +5.2 at 55–65,
near-zero mid-range). The harm-attenuation replicated directionally: arterial-defined hypotension carried a
stronger association with hospital mortality than cuff-defined (OR **5.40** [4.80–6.07] vs **4.86** [4.29–5.50];
higher absolute ORs than intraoperative INSPIRE because the ICU baseline mortality is far higher). A different
country, care setting, and monitor family reproduce both the measurement discrepancy and its direction of
harm-attenuation — evidence the phenomenon is device physics, not institutional artifact.

## 4. Discussion
Cuff monitoring systematically misses intraoperative hypotension because it over-reads at low pressure, and this
misclassification attenuates the measured hypotension–harm association across mortality, hyperlactatemia, AKI, a
composite, and ICU admission — an effect that persists after adjustment and at matched sampling cadence,
localizing it to measurement bias. The direct hypoperfusion marker (lactate) shows the cleanest, tightest
attenuation, providing mechanistic coherence. The practical implications are twofold: the intraoperative
hypotension evidence base has likely underestimated true effect sizes and mis-set "safe" thresholds; and, at the
bedside, a corrected cuff threshold (MAP<70) recovers much of the missed hypotension.

## 5. Limitations
- The two primary cohorts are single-institution (Seoul National University Hospital). External generalizability
  is supported by eICU (154 US hospitals), which reproduces the measurement discrepancy and the direction of
  harm-attenuation; however, eICU validates the ICU setting, not the intraoperative effect magnitude, and its
  higher absolute ORs reflect ICU baseline risk rather than a larger measurement effect.
- INSPIRE's minute-level arterial data carries more artifact than VitalDB's waveforms, inflating the INSPIRE
  discrepancy magnitude; VitalDB provides the clean estimate.
- MINS showed no attenuation, likely because troponin is measured in a selected cardiac-risk subset; this is
  reported, not omitted.
- Observational; arterial lines are placed non-randomly. The within-operation and matched-cadence designs
  control this for the relative (art-vs-cuff) comparison but not the absolute hypotension–harm association.
- The corrected cuff threshold trades sensitivity against false triggers and requires prospective validation.

## References (to complete)
Walsh 2013; Salmasi 2017; VISION/Devereaux; Wax 2011; Kaufmann 2020; Bijker 2007 (hypotension definitions).
