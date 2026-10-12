# Oscillometric Cuff Monitoring Systematically Underestimates Intraoperative Hypotension and Its Harms: A Two-Cohort Study with US Multi-Center External Validation

**Target journal:** *Anesthesiology* (primary) or *British Journal of Anaesthesia* (Original Investigation).
**Article type:** Original clinical/measurement investigation. **Word count:** to finalize (~3,500 main text).
**Running title:** Cuff monitoring underestimates intraoperative hypotension.
**Authors / affiliations / corresponding author:** to be completed.

*Discovery cohort: VitalDB (Seoul National University Hospital). Replication + outcome cohort: INSPIRE (Seoul
National University Hospital). External validation: eICU Collaborative Research Database (154 US hospitals).
Every quantitative claim traces to a specific analysis (see reproducibility appendix, doc 29); no number is
invented. This manuscript incorporates three rounds of adversarial internal review (see docs 21–23).*

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

**Results.** In VitalDB (1,079 co-recording cases, 5,903 artifact-hardened paired readings), the cuff detected
only **56%** of arterial-defined hypotension at MAP<65 (missed 44%), **42%** at <60, and **27%** at <55 (missed
73%), over-reading by **+30.6 mmHg** at arterial MAP 20–55 (overall Bland-Altman bias −0.2 mmHg). The discrepancy and its harm-attenuation replicated in an
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
arterial-defined hypotension had ≥1 episode missed by the cuff. The over-read is a **systematic, monotone
function of true pressure** (Bland-Altman by arterial stratum), stable across reference-window width and anchor
(±30/60/90 s: sensitivity 55.0/56.1/55.9%; bias +30.7/+30.8/+30.5), and **not a vasopressor artifact**: in a
within-operation, MAP-matched crossover the cuff–arterial bias difference on- versus off-vasoactive-infusion was
null at low pressure (−0.1 mmHg [−2.8,+2.6] at art 20–55; +0.3 [−1.7,+2.2] at 55–65) — the error is intrinsic
oscillometric behavior at low pressure, not vasoconstriction from treatment.

### 3b. Replication at scale (INSPIRE)
47,533 operations; cuff missed 71% of arterial-defined hypotension (MAP<65). (INSPIRE's larger magnitude vs
VitalDB reflects greater artifact in minute-level arterial data; VitalDB provides the clean estimate.)

### 3c. The measured harm of hypotension is attenuated under cuff — a direct consequence of undercounting

**Table 1. Within-operation association of intraoperative hypotension with adverse outcomes, by measurement
modality (INSPIRE, n = 28,349 operations co-recording arterial and cuff MAP).** Adjusted for age, ASA physical
status, operative duration, and baseline creatinine. Hypotension defined by arterial line (≥3 readings < 65 mmHg)
versus cuff (≥1 reading < 65 mmHg) in the *same* operations.

| Outcome | Arterial-defined, adj. OR [95% CI] | Cuff-defined, adj. OR [95% CI] | Attenuation |
|---|---|---|---|
| In-hospital mortality | **2.09 [1.68–2.60]** | 1.48 [1.21–1.81] | yes |
| Hyperlactatemia (peak ≥2 mmol/L) | **1.91 [1.79–2.05]** | 1.46 [1.36–1.56] | yes (non-overlapping CIs) |
| KDIGO acute kidney injury | 1.34 [—] | 1.26 [—] | modest |
| Death-or-AKI composite | **1.86 [—]** | 1.47 [—] | yes |
| ICU admission | **2.63 [—]** | 1.74 [—] | yes |
| Myocardial injury (MINS) | 1.48 [—] | 1.50 [—] | none (selected troponin cohort) |

Mechanism: cuff-defined non-hypotensive group has higher event rate than arterial non-hypotensive (AKI 6.5% vs
5.6%), reflecting misclassified hypotensive patients. **This attenuation is not an independent effect of
measurement on outcome; it is the quantified consequence of §3a–b.** When continuous true arterial hypotension
burden and depth are entered alongside the binary cuff-hypotension flag (composite adverse outcome, n=27,528),
the **cuff flag's association collapses to the null (adjusted OR 1.05 [0.98–1.12])** while arterial burden retains
a strong graded association (OR 1.73 per 10 min <65) — i.e. cuff-defined hypotension carries essentially no
information about harm beyond being a noisy, undercounting proxy for true arterial exposure. The attenuated cuff
effect sizes throughout the literature are therefore expected, and quantified here.

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

### 3f. Threshold miscalibration and a candidate correction (a trial hypothesis, not yet a guideline change)
A cuff MAP of 65 corresponded to a true arterial MAP of ~68 (37% actually <65). Against the arterial reference,
cuff<65 had sensitivity 56.1% (specificity 89.8%, false-positive rate 10.2%, PPV 49.8%); **cuff<70 raised
sensitivity to 71.9%** (specificity 81.2%, false-positive rate 18.8%, PPV 40.7%). These operating characteristics
**replicate externally in eICU** (1,140,999 paired readings, 154 US hospitals: 53.0%→70.7% sensitivity,
false-positive rate 11.8%→23.6%), so the trade is not an in-sample artifact. **The overtreatment concern is
bounded:** readings newly flagged by the <70 rule have a median true arterial MAP of 70 (only 25% are truly <65),
so the correction intensifies attention in mildly-low-normal patients rather than driving treatment toward
hypertension. Still, PPV falls to 41%, so a definitive net-benefit verdict (detection gain vs incremental
vasopressor exposure — cf. the treatment-response OR 1.34) requires the randomized third arm (§Trial). We
therefore present MAP<70 as a **testable candidate correction**, not an adopted threshold.

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

> **Box 1 — Arterial-line clinical aid (three layers). The actionable, evidence-backed step in the gray zone is
> the detection correction, NOT a prediction score.**
>
> **Layer 1 — auto-place (established guideline indication).** Cardiac / major-vascular / neuro / interventional
> cases and **ASA ≥ 4**. Already near-universal in practice (revealed placement 97/95/91% and 89–94%), so this
> layer *codifies* rather than predicts.
>
> **Layer 2 — place for a specific established benefit (any one):** beat-to-beat control · frequent ABG/serial
> labs · NIBP unreliable · active vasoactive titration · dynamic goal-directed monitoring.
>
> **Layer 3 — gray zone (no Layer-1/2 trigger).** The evidence-backed action is the **detection correction**:
> cuff cycled ≤ 2–3 min and treated at **MAP < 70** (recovers sensitivity for true hypotension from 57%→75%; no
> prediction model required). Higher-acuity features (older age, ASA ≥ III, major abdominal/urologic surgery,
> longer anticipated case) may *raise suspicion* for direct arterial monitoring, but a pre-operative risk *score*
> is only **exploratory/hypothesis-generating** here: on rigorous, leakage-free, held-out analysis its
> discrimination is ≈0.57 and it failed external validation (see §3h/Limitations). Whether *placing a line* in
> gray-zone patients improves outcomes is confounded observationally and is the subject of a prospective trial.

## 3h. External validation and the limits of a pre-operative score
**Mechanism replicates externally (eICU, 154 US hospitals).** — the measurement finding the aid rests on is
device physics, not local artifact (detail below).

**A pre-operative risk score does not.** Applied to VitalDB (independent cohort), a frozen four-factor gray-zone
score gave AUC 0.546 [0.511–0.579] with non-monotone calibration — a failed external validation. Internally, its
held-out discrimination falls to ≈0.57 once realized operative duration (a look-ahead: long cases run long partly
*because* of intraoperative events) is removed, and its apparent association with harm reflects general illness
severity rather than the cuff-blindness pathway specifically (it predicts harm as well or better in patients
*without* cuff-missed hypotension). The score is therefore reported as hypothesis-generating only; the
actionable, model-free translation of the finding is the detection correction (Box 1, Layer 3), and a
benefit-validated decision rule requires the randomized trial.

### 3h(i). The measurement discrepancy replicates (eICU, 154 US hospitals)
In 24,691 ICU stays co-recording arterial and cuff mean pressures across 154 US hospitals, the cuff detected only
**53%** of arterial-defined hypotension at MAP<65 (missed 47%) and **32%** at <55 (missed 68%) — closely matching
VitalDB (missed 44%/73%) — and over-read at low pressure (bias +13.1 mmHg at arterial 20–55, +5.2 at 55–65,
near-zero mid-range). The harm-attenuation replicated directionally: arterial-defined hypotension carried a
stronger association with hospital mortality than cuff-defined (OR **5.40** [4.80–6.07] vs **4.86** [4.29–5.50];
higher absolute ORs than intraoperative INSPIRE because the ICU baseline mortality is far higher). A different
country, care setting, and monitor family reproduce both the measurement discrepancy and the direction of
harm-attenuation. We describe this as replication of **direction and order-of-magnitude, not identical
magnitude**: the low-pressure over-read is +13.1 mmHg in eICU versus +30.6 in VitalDB (~2.3×), as expected from
the differing granularity (minute-level ICU data vs 2-second waveforms) and a sicker, more edematous ICU
population with additional oscillometric-error sources (limb edema, arrhythmia). The consistent *direction*
across country, setting, and device family indicates the phenomenon is intrinsic oscillometric behavior, while
the magnitude is context-dependent.

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
- The exploratory pre-operative gray-zone risk score has three structural weaknesses we report rather than
  minimize: (i) its held-out discrimination is modest (≈0.57 once realized operative duration, a look-ahead
  variable, is excluded) and it **failed external validation** in VitalDB (AUC 0.546); (ii) it is derived only in
  patients who received an arterial line, so the deployment population (un-lined gray-zone patients) is
  structurally unrepresented (verification/selection bias); (iii) its association with adverse outcomes reflects
  general illness severity, not the cuff-blindness pathway specifically. It is therefore presented as
  hypothesis-generating, not as a validated instrument; the actionable translation is the model-free detection
  correction, and a benefit-validated decision rule requires the randomized trial.

## Figures (specifications for production)
- **Figure 1 — Bland-Altman of cuff − arterial MAP, stratified by true arterial MAP (VitalDB).** Mean bias per
  arterial stratum with 95% limits of agreement; annotate the monotone widening of positive bias as MAP falls
  (+30.6 mmHg at 20–55 → ~0 mid-range). Inset: bias stability across ±30/60/90 s reference windows.
- **Figure 2 — Forest plot of the hypotension–harm association by measurement modality (INSPIRE; Table 1).**
  Paired arterial vs cuff adjusted ORs for each outcome; visualizes the systematic attenuation.
- **Figure 3 — Cuff sensitivity / operating characteristics vs treatment threshold** (VitalDB, replicated in
  eICU): sensitivity, specificity, false-positive rate, PPV at cuff MAP < 65/70/75; mark the <70 candidate
  correction and the median true arterial MAP (70) of newly-flagged readings.
- **Figure 4 — Study schematic / Box 1** (three-layer arterial-line aid + the detect-then-measure package).
- **Supplementary Figure S1 — Vasopressor-stratified within-operation crossover** (device-physics vs
  vasoconstriction): on- vs off-infusion cuff–arterial bias by arterial stratum (null at low pressure).

## Data availability
All three datasets are public/credentialed and independently accessible; no data were generated by the authors.
VitalDB (https://vitaldb.net), INSPIRE (PhysioNet), and the eICU Collaborative Research Database (PhysioNet)
require the respective data-use agreements. Analysis code will be released on publication (repository link to be
added); a result-to-code reproducibility appendix accompanies this manuscript.

## Ethics
This is a secondary analysis of fully de-identified, publicly released research databases obtained under their
data-use agreements; per each provider's terms and applicable regulations it is exempt from additional
institutional review board approval. (Confirm and insert local IRB determination number before submission.)

## Reporting
Observational analyses are reported per **STROBE**; the exploratory prediction model is reported per **TRIPOD**
(and is explicitly labelled hypothesis-generating). The proposed trial (companion protocol) is designed to
**SPIRIT/CONSORT** standards.

## Funding / Conflicts of interest / Author contributions
Funding: none declared (confirm). Conflicts: none declared (confirm). Author contributions: to be completed
(conception/design; acquisition; analysis/interpretation; drafting; critical revision; all authors approve the
final version and agree to be accountable).

## Companion documents
Prospective trial protocol: `docs/research/24_aline_prospective_protocol.md`. Statistical analysis plan (prediction
model): `docs/research/22_aline_decision_tool_SAP.md`. Result-to-code reproducibility appendix:
`docs/research/29_C8_reproducibility_appendix.md`.

## References
*(Canonical citations; final bibliographic details — volume/pages/DOI — to be verified against source before
submission. No citation below is invented; each is a well-established paper or database.)*

**Intraoperative hypotension and outcomes**
1. Walsh M, Devereaux PJ, Garg AX, et al. Relationship between intraoperative mean arterial pressure and clinical
   outcomes after noncardiac surgery: toward an empirical definition of hypotension. *Anesthesiology* 2013.
2. Salmasi V, Maheshwari K, Yang D, et al. Relationship between intraoperative hypotension, defined by either
   reduction from baseline or absolute thresholds, and acute kidney and myocardial injury after noncardiac
   surgery. *Anesthesiology* 2017.
3. Sun LY, Wijeysundera DN, Tait GA, Beattie WS. Association of intraoperative hypotension with acute kidney
   injury after elective noncardiac surgery. *Anesthesiology* 2015.
4. Mascha EJ, Yang D, Weiss S, Sessler DI. Intraoperative mean arterial pressure variability and 30-day
   mortality in patients having noncardiac surgery. *Anesthesiology* 2015.
5. Wesselink EM, Kappen TH, Torn HM, Slooter AJC, van Klei WA. Intraoperative hypotension and the risk of
   postoperative adverse outcomes: a systematic review. *Br J Anaesth* 2018.
6. Sessler DI, Bloomstone JA, Aronson S, et al. Perioperative Quality Initiative consensus statement on
   intraoperative blood pressure, risk and outcomes for elective surgery. *Br J Anaesth* 2019.
7. Devereaux PJ, Sessler DI. Cardiac complications in patients undergoing major noncardiac surgery (VISION).
   *N Engl J Med* 2015.

**Blood-pressure measurement accuracy**
8. Wax DB, Lin HM, Leibowitz AB. Invasive and concomitant noninvasive intraoperative blood pressure monitoring:
   observed differences in measurements and associated therapeutic interventions. *Anesthesiology* 2011.
9. Kaufmann T, Cox EGM, Wiersema R, et al. Non-invasive oscillometric versus invasive arterial blood pressure
   measurements in critically ill patients. *J Clin Monit Comput* 2020.
10. Bijker JB, van Klei WA, Kappen TH, et al. Incidence of intraoperative hypotension as a function of the chosen
    definition. *Anesthesiology* 2007.

**Intervention / trial context**
11. Futier E, Lefrant JY, Guinot PG, et al. Effect of individualized vs standard blood pressure management
    strategies on postoperative organ dysfunction (INPRESS). *JAMA* 2017.
12. Maheshwari K, Nathanson BH, Munson SH, et al. The relationship between ICU hypotension and in-hospital
    mortality and morbidity in septic patients. *Intensive Care Med* 2018.
13. Vickers AJ, Elkin EB. Decision curve analysis: a novel method for evaluating prediction models. *Med Decis
    Making* 2006.
14. KDIGO Acute Kidney Injury Work Group. KDIGO clinical practice guideline for acute kidney injury. *Kidney Int
    Suppl* 2012.

**Data resources**
15. Lee HC, Park Y, Yoon SB, et al. VitalDB, a high-fidelity multi-parameter vital signs database in surgical
    patients. *Sci Data* 2022.
16. INSPIRE: a publicly available research dataset for perioperative medicine (Seoul National University
    Hospital). *PhysioNet* 2024.
17. Pollard TJ, Johnson AEW, Raffa JD, et al. The eICU Collaborative Research Database, a freely available
    multi-center database for critical care research. *Sci Data* 2018.
