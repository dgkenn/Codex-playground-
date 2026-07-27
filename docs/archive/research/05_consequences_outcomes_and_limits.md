# Consequences, Outcomes, and Honest Standing of the Immunoglobulin-Driven Racial Measurement Bias

## Abstract

A coordinated, immunoglobulin-driven measurement bias distorts routine chemistry
by race: on indirect-ISE analyzers plasma-water displacement reads sodium and
chloride falsely **low**, while excess globulin binding reads total calcium
falsely **high**, and a distinct pre-analytic pathway reads chemistry potassium
falsely **high**. This document traces those biases into their *clinical
consequences* and grades each on a strict durable-vs-hypothesis-generating
scale. The **misclassification consequences are durable**: at matched true
(physiologic) values, Black patients are over-labeled hyponatremic, carry more
masked (occult) hypocalcemia, and suffer more false-hyperkalemia alarms — all
cross-sectional, mechanistically grounded, adjustment-robust, and (for calcium)
multi-site-replicated. An independent physiological arbiter — the MIMIC-IV-ECG
machine-measurement set (**800,036 ECGs**) — confirms the direction of two of
these: the heart shows the QT prolongation that a masked total calcium hides,
and false-hyperkalemia events lack the electrophysiologic signature of true
hyperkalemia. The **hard-outcome harm chain** (masked hypocalcemia → unrecognized
long-QT → ventricular arrhythmia/death, disproportionately in Black patients) is
**explicitly hypothesis-generating, not confirmatory**: an independent red-team,
re-running the code, found it fragile (headline arrhythmia split rests on 26 vs 3
events), built on a highly selected 90%-ICU cohort at 7–8× baseline arrhythmic
risk, with structurally unverifiable temporality, and it does **not** replicate
on eICU mortality. The honest standing after multiple hostile-review rounds:
**measurement bias + mechanism + misclassification are durable and (for calcium)
multi-site-validated; the arrhythmia/mortality outcome is a lead, not a result.**

---

## 1. From measurement bias to differential misclassification (DURABLE)

The measurement biases are not abstract offsets — at a *matched true value*, they
flip diagnostic labels differentially by race. Because the comparison holds the
physiologic quantity fixed (blood-gas/direct-ISE sodium, ionized calcium,
blood-gas potassium), any residual label difference is **misclassification**, not
real disease. These are the solid, cross-sectional, mechanistically grounded
consequences.

### 1.1 Masked (occult) hypocalcemia — more common in Black patients

Total calcium reads **+0.15 mg/dL higher** in Black patients at matched *ionized*
(physiologically true) calcium (**z = +11.6**, n = 25,163, 3,442 Black). The bias
**survives albumin correction** (+0.15, **z = +7.3**) because the corrected-calcium
formula in every EHR adjusts for albumin, not the globulin-bound calcium — so even
the "corrected" value clinicians trust is racially miscalibrated.

Consequence — **masked hypocalcemia**, defined as truly low ionized calcium
(< 1.12 mmol/L) hidden behind a normal-reading total (≥ 8.5 mg/dL):

| stratum | Black | White | note |
|---|---|---|---|
| overall masked hypocalcemia | **20.9%** | **16.5%** | more masking in Black patients |
| mild true hypocalcemia (ionized 1.00–1.12) | **26.2%** | **18.1%** | Black-predominant |
| severe true hypocalcemia (ionized < 1.00) | 7.3% | 9.2% | **reverses** — report as mild-range only |

The reversal at severe hypocalcemia is an honest, non-fatal caveat: the
Black-predominant masking is a *mild-range* phenomenon, not universal. Downstream,
masking drives **less calcium repletion** (OR 0.74, z = −7.4); a spurious
**hyper**calcemia flag (false high) is also more frequent (adj OR 1.50, z = +2.9),
risking unnecessary malignancy workup. (The raw racial repletion gap at matched
true hypocalcemia, OR 0.72, z = −6.9, is **largely a general care disparity, not
mediated by the measurement** — 0.72 → 0.73 on adjustment — stated honestly.)

### 1.2 False hyperkalemia — more common in Black patients

Chemistry potassium reads **higher** than blood-gas potassium (opposite of Na/Cl),
and the excess is larger in Black patients (`potassium_rigor.py`, n = 20,200):

- Racial K-bias differential **+0.124 mEq/L (z = +9.2)**; survives adjustment for
  creatinine/age/true-K (**+0.122, z = +8.8**) and a tight 10-min window (**+0.125,
  z = +7.3**) → not timing, not CKD.
- **False hyperkalemia** (chem K ≥ 5.5 at true-normal blood-gas K 3.5–5.0):
  **BLACK 13.5% vs WHITE 6.3%, adj OR 2.36 (2.01–2.76, z = +10.6)**, subject-clustered.
- Masked *true* hyperkalemia is **not** elevated in Black patients — the harm is
  **false alarms, not missed lethal hyperkalemia**.

Mechanistically this is a **distinct** pathway from the protein bias: the K-bias
is essentially uncorrelated with the sodium protein-bias (r = −0.19), and protein
exclusion would push chemistry K *down* (like Na/Cl), not up. The driver is
**pre-analytic** (hemolysis / clotting / platelet release / transport delay) — a
serum-vs-whole-blood pseudohyperkalemia, plausibly linked to draw-difficulty /
access / transport (structural care-delivery factors). Clinical stakes are high:
false hyperkalemia triggers emergency treatment (insulin/dextrose → hypoglycemia;
calcium; kayexalate; dialysis; ECG monitoring; treatment delays). A 2.4× excess of
false alarms is a large, actionable safety disparity; the fix is method/process-level
(blood-gas/whole-blood confirmation, better sample handling).

### 1.3 Hyponatremia over-labeling (and its mirror, missed hypernatremia)

Chemistry (indirect-ISE) sodium reads **−1.18 mEq/L lower** in Black patients at
matched true (blood-gas) sodium (SE 0.09, **z = −12.6**). Restricting to truly-normal
sodium so any label difference is misclassification:

| true-Na band | race | n | chem < 135 (false hypo-label) |
|---|---|---|---|
| 135–140 (normal) | WHITE | 4,455 | **3.9%** |
| 135–140 (normal) | BLACK | 539 | **10.8% (2.8×)** |

Adjusted for age/sex/glucose/BUN/creatinine/true-Na, the **false-hyponatremia label
remains OR 1.68 (1.20–2.37), z = +3.0**, and is stable across every cutoff 133–138
(OR 2.22–2.87, all z > 4) — not a knife-edge artifact. The mirror harm, **missed
hypernatremia** (true Na ≥ 148 reading chem < 145), is **adj OR 2.58 (1.20–5.56,
z = +2.4)** — Black patients with true hypernatremia are 2.6× more likely to read
"normal." A subtler systemic consequence: **APACHE-II severity-score inflation**
(the score awards points for low sodium) — racial differential **+0.055 points
(z = +3.8)**, which biases prognostication, triage, and, insidiously, any study
that risk-adjusts on APACHE.

### 1.4 Coordinated panel and its specificity check

The three biases are one mechanism (excess plasma protein/globulin) expressed in
three directions, each matching known chemistry:

| analyte | direction | racial bias | z | consequence |
|---|---|---|---|---|
| Sodium (indirect ISE vs blood-gas) | falsely **low** | −1.18 | −12.6 | pseudohyponatremia, missed hyperNa (OR 2.58), APACHE inflation |
| Chloride (indirect ISE vs blood-gas) | falsely **low** | −0.79 | −3.5 | missed hyperchloremia adj OR 2.40 (z = +6.5) |
| Calcium (total vs ionized) | falsely **high** | +0.15 mg/dL | +11.6 | masked hypocalcemia 20.9% vs 16.5% |
| Potassium (chem vs blood-gas) | falsely **high** | +0.124 | +9.2 | false hyperkalemia OR 2.36 |

A key **negative** confirms specificity: the **anion gap is preserved** — sodium
(−0.76) and chloride (−0.79) carry nearly identical indirect-ISE biases, so they
cancel in AG = Na − Cl − HCO₃ (distortion +0.07, z = +0.3). The feared "masked
acidosis → missed DKA/sepsis" harm **does not occur**. The bias lands exactly where
an analyte enters a formula *alone* (dysnatremia thresholds, 2×Na osmolality,
corrected-Na, APACHE) and vanishes where chloride cancels sodium — itself evidence
of a genuine measurement artifact rather than a generic confound.

**Multi-site validation of the calcium bias (the misclassification that travels):**

| dataset | finding | z |
|---|---|---|
| MIMIC (Boston) | total Ca +0.15 mg/dL at matched ionized; survives pH + albumin + tight window | +11.6 |
| eICU (129 hospitals, WITH RACE) | +0.12–0.15; hospital-FE +0.092 | +2.5–3.3 (FE z = 3.30) |
| SICdb (Austria) | total-Ca excess ~ total protein +0.053 mmol/L per g/dL | +39.6 |

The eICU replication (n = 62,388 pairs, 21,275 patients, 129 hospitals) shows the
same sign, ~40–60% of the MIMIC magnitude after removing between-hospital
confounding (naive +0.236, z = 8.1 → hospital-FE +0.092, z = 3.30), with masked
hypocalcemia replicating (Black 22.7% vs White 13.2%; FE-adjusted +3.0 pp, z = 2.1).
Citrate/CRRT exclusion leaves it at +0.129 (z = +9.3, n = 23,622) — not a
chelation artifact. **The measurement bias and its misclassification consequence
are multi-site; this is the durable core.**

---

## 2. The ECG as an independent physiological arbiter

The strongest defense against "the lab is just noise" is an **independent
physiological readout**. We extracted QT/QTc(Bazett+Fridericia)/QRS/PR intervals
plus machine-diagnosis flags from the **MIMIC-IV-ECG machine-measurement set
(800,036 ECGs**; `extract_ecg.py`, `ecg_link.py`), time-linked to electrolyte
draws by subject_id, and asked whether the heart confirms what the biased labs
imply.

### 2.1 Calcium — the ECG reveals the hypocalcemia the total calcium hid (supports)

Among patients whose **total calcium reads normal (≥ 8.5 mg/dL)**, those with
**occult hypocalcemia** (ionized < 1.12, masked by the normal total) show more
**prolonged QTc (> 460 ms): 59.8% vs 50.0%, OR 1.48 (1.17–1.88, z = +3.3)**. An
independent physiological instrument confirms the masked hypocalcemia is a **real
QT-prolonging electrophysiologic abnormality**, not a lab curiosity — the "normal"
total calcium is falsely reassuring.

Re-run on the **complete 800,036-ECG set with strict temporality** (ECG required
*after* the calcium draw, 0–48 h): occult hypocalcemia → **subsequent** prolonged
QTc > 460 = **OR 1.62 (1.37–1.91, z = +5.7), n = 7,913** (60.8% vs 48.9%), and
**unchanged by potassium adjustment** (OR 1.62) — so the masked draw provably
*precedes* the QT prolongation, and it is not a hypokalemia confound. This is the
physiological validation the calcium misclassification finding needed.

### 2.2 Potassium — the ECG supports that false hyperkalemia is spurious (partial)

Arbitration logic: true hyperkalemia produces ECG changes (peaked T, wide QRS,
P-wave loss); pseudohyperkalemia should not. The machine's *categorical*
hyperkalemia flag proved **too insensitive to arbitrate** — it fires in only 0.5%
of *true* hyperkalemia and 0% of false — so the flag itself is not a usable
discriminator at this scale (honest limitation). The *quantitative* signature
(184k ECGs) does separate the groups directionally: true vs false hyperkalemia
shows wide-QRS > 110 **27.4% vs 17.6%**, long-PR > 200 **13.5% vs 7.7%**, **P-wave
loss 24.5% vs 8.8%**, and shorter QTc (446 vs 452 ms). False-hyperkalemia events
*lack* the electrophysiologic changes of true hyperkalemia → the ECG supports that
they are spurious (pseudohyperkalemia). The separation is modest — as the
literature predicts, ECG is intrinsically insensitive to hyperkalemia — so this is
**partial physiological corroboration, not a decisive arbiter**; raw T-wave
amplitude on the full set would sharpen it.

---

## 3. The hard-outcome harm chain (HYPOTHESIS-GENERATING — explicitly fragile)

The attempt to convert the durable misclassification into a *hard clinical outcome*
followed the chain: higher globulins (Black patients) → falsely-high total calcium
→ masked/occult hypocalcemia → unrecognized prolonged QTc → ventricular
arrhythmia/cardiac arrest and death → borne disproportionately by Black patients.
**Each link is measurable, and each link is also fragile.** This section reports
exactly what was found and exactly what the red-team concluded. **It is not
confirmatory.**

### 3.1 What the outcome analyses showed

**Masked hypocalcemia → arrhythmia** (`calcium_outcomes.py`; true hypocalcemic
patients, ionized < 1.12, n = 15,618; masked = total ≥ 8.5; adjusted for true
ionized + albumin + creatinine, subject-clustered):

| outcome | adj OR (masked) | z | after excluding myeloma/cirrhosis/MGUS |
|---|---|---|---|
| arrhythmia | 1.25 (1.15–1.36) | +5.3 | **1.29 (1.18–1.42), z = +5.6** (survives) |
| cardiac arrest | 1.33 (1.11–1.59) | +3.1 | **1.27 (1.05–1.55), z = +2.5** (survives) |
| mortality | 1.30 (1.17–1.45) | +4.9 | **1.11 (0.98–1.25), z = +1.7** (attenuates to ns) |
| seizure | 0.90 | −1.3 | — (null) |

The arrhythmia signal was **invariant to rich severity adjustment** (+ lactate,
BUN, glucose, age): 1.31 → 1.29 → **1.29 (1.17–1.41), z = +5.2** (n = 13,610) —
the hallmark of a real association — while **mortality honestly attenuated to
non-significance** once globulin-driven diseases were excluded (it was largely
confounded). Black patients are masked more (23.6% vs 18.5%), so they would carry
this signal disproportionately.

**The QTc → outcome chain** (`qt_outcomes.py`; n = 2,781 Ca pairs with a linked ECG):

- Prolonged QTc (> 460 ms) → ventricular arrhythmia/cardiac arrest: **OR 2.58
  (1.96–3.41, z = +6.7, 294 events)**; → mortality **OR 1.73 (z = +5.1)**.
- Within **occult hypocalcemia** (normal total hiding low ionized, n = 292):
  prolonged QTc → ventricular arrhythmia/arrest **14.9% vs 2.6% (≈ 5.7×)**;
  → mortality **OR 2.04 (z = +2.3)**.
- Unrecognized-QT-risk prevalence (occult hypocalcemia *with* prolonged QTc):
  **BLACK 8.6% vs WHITE 5.9% (≈ 1.5×)**.

**Full-power + strict temporality** (800,036 ECGs, ECG after the draw): occult →
subsequent QTc > 460 **OR 1.62 (1.37–1.91, z = +5.7), n = 7,913**; prolonged QTc →
ventricular arrhythmia/arrest **OR 2.27 (1.97–2.62, z = +11.3, 978 events)**;
→ mortality **OR 1.34 (z = +4.9)**.

The parallel chloride outcome was a **clean null**: among true-hyperchloremic
patients (blood-gas Cl ≥ 110, n = 2,134), masked chemistry Cl → AKI OR 1.25
(p = 0.076, ns), creatinine-rise β ≈ 0; mortality OR 1.51 (p = 0.005) was
White-driven and severity-confounded. No clean attributable renal harm.

### 3.2 What the red-team concluded (`qt_redteam.py`) — the chain is TEMPERED

An independent reviewer re-ran the code and graded the chain in three tiers:

- **Robust but not novel.** Prolonged QTc → ventricular arrhythmia/arrest OR ≈ 2.6
  survives strict temporality (ECG-after, OR 2.64), K/Mg adjustment (2.55),
  early/late split, and arrest-only vs VT/VF-only. *This is established cardiology,
  not a new finding.*
- **Modest / power-dependent.** Occult hypocalcemia → QTc is a **small continuous
  shift (+7.5 ms, z = +3.1)**, surviving K/Mg/ICU/age adjustment; but the **binary
  occult → QTc > 460 is non-significant on the 184k-ECG subset (z = 1.2)** and only
  reaches z = +5.7 on the full 800k set — real but small, and ICU status *alone*
  drives a comparable +10 ms shift.
- **NOT well-supported — the headline harm.** "Masked hypocalcemia → unrecognized
  *lethal* QT → arrhythmia, disproportionately in Black patients" does not hold up:
  the **14.9% vs 2.6% arrhythmia split rests on just 26 vs 3 events** (fragile,
  single-event-sensitive); the cohort (ionized Ca + linked ECG) sits at **7–8×
  baseline arrhythmia risk and is ~90% ICU** — not the "unremarkable masked
  patient" the claim implies; arrhythmia **temporality is structurally
  unverifiable** (timestamp-free admission-level ICD codes — the event may precede
  the masked draw); and **QT-prolonging drugs, ischemia, and structural disease are
  unaddressed**.

**External replication fails for the outcome.** In eICU (the multi-site cohort
that replicated the *measurement bias*), masked hypocalcemia → mortality is
**OR 0.87, p = 0.13 — wrong direction, does not replicate**. eICU has no ECG, so it
cannot test the arrhythmia endpoint; the measurement bias is multi-site, but the
**outcome harm remains MIMIC-only and externally unconfirmed**.

### 3.3 Corrected honest standing of the outcome harm

The measurement bias and the modest QTc association are real. The **hard
arrhythmia/mortality outcome is NOT robustly established**: the MIMIC arrhythmia OR
(1.29) has ICD-timing and selection concerns, the eICU mortality does not
replicate, and the QT-arrhythmia subgroups are fragile (26 vs 3 events). **The
outcome harm must be presented as hypothesis-generating, not demonstrated.** The
durable claims are (1) the coordinated immunoglobulin-driven **measurement bias**
(multi-site, mechanism-nailed); (2) **misclassification** (masked hypocalcemia,
false hyperkalemia); and (3) a **modest, ECG-corroborated QTc association**. The
lethal-outcome chain needs prospective / time-anchored data.

---

## 4. Consolidated review history and limitations

The sodium finding passed **four rounds of hostile adversarial review** (including
two independent code re-executions); the calcium and potassium extensions each
passed their own red-team. This section consolidates what survived and what did
not, so the honest standing is unmistakable.

### 4.1 What survived hostile review (durable)

- **The measurement biases**, robust to every measured confounder, selection,
  clustering, cutoff, and matrix test. Sodium survives full adjustment at −0.80
  (z = −8.1) and IPW-for-selection at −1.14 (z = −8.6); the racial differential is
  reproduced against an **independent osmolality arbiter** (−1.01, z = −9.3), so it
  does not depend on trusting the blood-gas analyzer. In Round 4 the gate reviewer
  re-executed seven of eight cited scripts and **every core MIMIC/SICdb number
  reproduced digit-for-digit**.
- **The mechanism** — protein/globulin-driven indirect-ISE displacement — confirmed
  by a graded, monotone dose-response, **cross-nationally replicated** (MIMIC
  −0.90; SICdb −0.843, z = −28.6 per g/dL total protein) and confirmed on the exact
  implicated analytes (globulin −1.02, IgG −0.107/100 mg/dL, cholesterol
  −1.58/100 mg/dL). For calcium, total-Ca excess tracks total protein at
  +0.30 mg/dL per g/dL (z = +9.5), replicated in SICdb (+0.053 mmol/L per g/dL,
  z = +39.6).
- **The misclassification consequences** (Section 1): adjustment-robust,
  cutoff-stable, and — for calcium — **multi-site-replicated in eICU (129
  hospitals)**.
- **The ECG physiological corroboration** (Section 2): the QTc signature of masked
  hypocalcemia (OR 1.48 → 1.62 with strict temporality) and the absent ECG
  signature of false hyperkalemia.

### 4.2 What did not survive / was demoted (honest)

- **The sodium racial axis is single-center (MIMIC).** No public ICU dataset pairs
  race with dual-method sodium except MIMIC; eICU lacks blood-gas sodium and its
  osmolality-reconstructed racial differential is **specification-unstable and does
  not replicate** (an honest negative). Only the *mechanism* is cross-national.
- **The ~1 mEq/L sodium magnitude is analyzer-specific** — only the
  direction/mechanism generalizes across vendors, not the number.
- **Treatment/outcome harms for sodium were demoted to hypothesis-generating**: the
  hypertonic-saline "overtreatment" signal is underpowered (CI crosses 1), the
  repeat-sodium cascade runs the *opposite* way, and the overcorrection metric is
  regression-to-the-mean-confounded. Clean single-center MIMIC does not deliver a
  sodium outcome harm.
- **The calcium hard-outcome chain was tempered to hypothesis-generating** (Section
  3): fragile event counts, extreme selection, unverifiable temporality, and
  failed eICU mortality replication.
- **Mediation is only ~50% closed**: measured protein explains roughly half the
  racial sodium differential; the within-sample mediation is underpowered
  (n = 268, z = −1.6), so the load-bearing evidence is the dose-response slope, not
  a mediation coefficient.

### 4.3 Structurally unfixable ceilings (no public-data analysis closes them)

1. **Single-center race axis for sodium** — requires a US multi-hospital dataset
   with paired dual-method sodium + race (not currently public).
2. **Analyzer-specific magnitude** — the point estimate reflects one hospital's
   indirect-ISE dilution algorithm.
3. **Subclinical (un-coded) globulin elevation and unmeasured osmoles** (e.g.
   mannitol) cannot be excluded in observational data.
4. **A measurement-*attributable* hard outcome** proven causal — needs
   prospective, time-anchored (QTc-after-draw) collection with adequate events.

### 4.4 Overall honest standing

| claim | standing |
|---|---|
| Coordinated immunoglobulin-driven **measurement bias** (Na↓, Cl↓, Ca↑, K↑) | **DURABLE** — multi-site (Ca), cross-national mechanism, red-team-survived |
| **Misclassification** (masked hypocalcemia, false hyperkalemia, hyponatremia over-labeling) | **DURABLE** — adjustment-robust, cutoff-stable, ECG-corroborated |
| **Corrected-calcium formula is racially miscalibrated** (omits globulin) | **DURABLE** — survives albumin correction (z = +7.3) |
| Modest **QTc association** of masked hypocalcemia | **SUPPORTED** — small continuous shift, ECG-based, temporality-established |
| **Hard arrhythmia / mortality outcome** chain | **HYPOTHESIS-GENERATING** — fragile events, selection, unverifiable temporality, eICU mortality does not replicate |
| Sodium **treatment/overcorrection** harm | **HYPOTHESIS-GENERATING** — underpowered, RTM-confounded |

The correct, defensible conclusion: this is a **mechanism-solid, misclassification-
demonstrated, multi-site-validated (for calcium) measurement-bias finding** — a
methods/equity contribution of real patient-safety weight. The lethal-outcome harm
chain is a **lead for prospective work, not a confirmed result**, and is presented
as such throughout. Preserving that boundary is the finding's integrity.
