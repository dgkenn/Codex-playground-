# A Coordinated, Immunoglobulin-Driven, Panel-Wide Racial Measurement Bias in Routine Chemistry — Anchored by Calcium

**Status:** flagship finding, multi-dataset (MIMIC-IV, eICU, SICdb), independently red-teamed.
**Source of record:** this document is a clean synthesis of `docs/REAL_RESULTS_SODIUM_RACE_BIAS.md`; every
number below is copied from that working log. Where the log reports a caveat, it is preserved here.

## Abstract

Elevated immunoglobulins in non-white patients — a well-established, decades-old finding on its own — do not
bias a single lab value; they bias **multiple routine chemistry analytes in a coordinated, chemically coherent
way**, and the correction formula clinicians rely on to compensate for protein interference **fails to remove
the bias**. The anchor analyte is **total calcium**: at matched *ionized* (physiologically true) calcium, total
calcium reads systematically higher in Black patients (MIMIC, +0.15 mg/dL, z = +11.6, n = 25,163, 3,442 Black),
a result that survives pH adjustment, albumin correction, a tight 10-minute pairing window, subject-level
clustering, citrate/CRRT exclusion, and an independent code red-team, and that **replicates across 129
hospitals in eICU** (hospital-fixed-effects +0.092 mg/dL, z = 3.30) with a matching mechanism in an
Austrian cohort (SICdb, total-Ca excess ~ total protein, z = +39.6). The same mechanism — excess plasma
globulin — produces falsely **low** sodium (z = −12.6) and chloride (z = −3.5) by indirect-ISE water
displacement, and falsely **high** calcium (z = +11.6) and (weaker/directional) ESR and total T4 by protein
binding: one mechanism, opposite-signed but chemically predicted effects across the whole panel. Critically,
the standard albumin-corrected-calcium formula — used in every EHR — omits globulin entirely and so is
itself racially miscalibrated: it reads +0.15 mg/dL too high at matched true calcium (z = +7.3), a
**continuous** miscalibration, not a differential binary miss-rate (~40% of ICU patients are missed by the
formula regardless of race). The consequence, at the measurement/misclassification level, is a masked
mild-hypocalcemia gap (Black 26.2% vs. White 18.1%, though this reverses at severe hypocalcemia) and a
spurious hypercalcemia flag (adjusted OR 1.50). The mechanism itself — globulin-driven pseudohypercalcemia —
is known, but only as a curiosity of extreme paraproteinemia/myeloma; the genuine novelty here is showing that
**ordinary, population-level, race-associated globulin variation (~0.3–0.6 g/dL) reproduces the same artifact
at population scale in the general ICU population**, with a coordinated, panel-wide, chemically coherent
signature. Threshold-dependence, a Berkson selection caveat in the paired-test cohort, and the (separately
documented, more fragile) downstream outcome-harm chain are stated plainly below.

---

## 1. The Calcium Measurement Bias

### 1.1 Primary finding (MIMIC-IV)

At matched **ionized** calcium (the protein-independent, physiologically active form), **total calcium reads
falsely high in Black patients**:

> Total calcium bias (Black vs. White, at matched ionized calcium): **+0.15 mg/dL, z = +11.6**
> (n = 25,163 pairs, 3,442 Black)

This is the calcium mirror image of the sodium/chloride findings elsewhere in this research program (falsely
*low*), and — unlike blood-gas sodium, which exists at only one hospital in public ICU data — ionized calcium
is measured on routine blood-gas panels at essentially every hospital, which is what allows this finding to
clear the single-center wall that capped the sodium result.

### 1.2 Robustness (MIMIC-IV)

The finding survives every stress test applied:

| test | result |
|---|---|
| pH adjustment | **strengthens** the estimate, +0.157 → +0.167 |
| Albumin correction | **+0.15 mg/dL, z = +7.3** (i.e., survives applying the standard corrected-calcium formula) |
| Tight 10-minute pairing window | **+0.156** (rules out temporal/physiologic drift between draws) |
| Subject-clustered SE, first-pair design | **z = 10.3** (rules out within-patient correlation inflating significance) |
| Citrate/CRRT exclusion (dialysis/ESRD proxy) | **+0.129 mg/dL, z = +9.3** (n = 23,622) — citrate chelation is not the driver |

The total-protein dose-response underlying the mechanism (below) is also citrate-independent (z = +9.5).

### 1.3 Independent red-team (code re-execution)

An independent reviewer re-ran the calcium code end-to-end and **reproduced every number**. Verdict: **survives**.
The reviewer additionally surfaced two honest, non-fatal caveats (both preserved in Section 6, Limitations,
below): the masking effect is threshold-dependent (mild vs. severe hypocalcemia), and the paired-test cohort
is subject to Berkson-type selection (ionized calcium is drawn non-randomly, and at different rates by race).

### 1.4 Multi-hospital replication (eICU, 129 hospitals — WITH race)

eICU is the one public ICU dataset that carries race *and* a second calcium measurement channel, so — unlike
sodium — a true multi-site **racial** replication is possible here.

> eICU calcium replication (`eicu_calcium_replication.py`, n = 62,388 pairs, 21,275 patients, 129 hospitals):
> - **Naive** estimate (total Ca ~ BLACK + ionized): **+0.236 mg/dL, z = 8.1**
> - **Hospital-fixed-effects** estimate (removes between-hospital analyzer/case-mix confounding): **+0.092 mg/dL,
>   z = 3.30, p < 0.001**

Same sign as MIMIC in both specifications; the hospital-FE estimate retains roughly 40–60% of the naive
magnitude after removing between-hospital confounding, and is robust across pairing windows. A unit-scale
inconsistency in eICU's ionized-calcium field was identified and resolved during this analysis, and shown not
to fabricate the effect. **This is a genuine multi-site racial replication of the measurement bias itself**,
which the sodium finding structurally could not achieve.

Masked hypocalcemia also replicates in eICU: **Black 22.7% vs. White 13.2%** (hospital-FE-adjusted +3.0
percentage points, z = 2.1).

### 1.5 Mechanism replication (SICdb, Salzburg, Austria — cross-national)

SICdb provides an independent, cross-national test of the underlying chemistry (protein → calcium-excess
dose-response), though SICdb has no race variable, so it replicates the **mechanism**, not the racial
differential itself:

> Total-calcium excess (over ionized) ~ total protein: **+0.053 mmol/L per g/dL, z = +39.6**

This is a very large, precisely-estimated, monotone dose-response on an independent continent with different
instrumentation — strong evidence the calcium artifact is a genuine chemical/analytic phenomenon rather than a
MIMIC-specific confound.

### 1.6 Mechanism: globulin binding

The chemistry is the mirror image of the sodium/chloride dilution mechanism. Where indirect-ISE sodium and
chloride are falsely lowered by protein displacing plasma water, **calcium is falsely raised because excess
globulin (a class of plasma protein, dominated by immunoglobulins) binds additional calcium**, and the total
(bound + free/ionized) calcium assay cannot distinguish protein-bound calcium from the physiologically active
ionized fraction:

> Total-calcium excess over ionized ~ total protein: **+0.30 mg/dL per g/dL, z = +9.5** (MIMIC)

(A separately fitted correction-tool coefficient from the same data — used for a candidate globulin-inclusive
correction formula, Section 3 — gives a closely matching **+0.31 mg/dL per g/dL protein**.)

The magnitude is chemically sensible: the plasma-water/protein-binding equations predict roughly this order of
effect at physiologic globulin concentrations, and — as with sodium — the driving quantity (globulin/total
protein/IgG) is independently documented to be higher in Black, Hispanic, and Asian populations than in White
populations (e.g., MIMIC IgG: White 961 vs. Black 1,350 mg/dL; matching external literature at White 1,209
vs. Black 1,587 mg/dL).

---

## 2. The Coordinated, Panel-Wide Bias

The same excess-globulin exposure does not stop at calcium. It produces a **coordinated, chemically coherent**
pattern of bias across the routine chemistry panel — each analyte biased in the direction its own
protein-chemistry predicts:

| analyte | mechanism | direction | z |
|---|---|---|---|
| **Sodium** (indirect ISE vs. blood-gas) | plasma-water displacement (dilution) | falsely **LOW** (−1.18 mEq/L) | **−12.6** |
| **Chloride** (indirect ISE vs. blood-gas) | plasma-water displacement (dilution) | falsely **LOW** (−0.79 mEq/L) | **−3.5** |
| **Calcium (total)** (vs. ionized) | globulin binding | falsely **HIGH** (+0.15 mg/dL) | **+11.6** |
| **ESR** (at matched CRP) | globulin rouleaux/aggregation | falsely **HIGH** | **+4.2** |
| **Total T4** (at matched free T4) | TBG (globulin-class carrier) binding | falsely high, directional (ns) | **+1.3 (underpowered)** |

**Coherence is the evidence.** Sodium and chloride — both measured by the same indirect-ISE method, both
subject to the same protein-driven plasma-water displacement — are biased in the *same* direction and by
comparable relative magnitude. Calcium and (directionally) T4 — both partly protein-bound analytes for which
a *higher* binding-protein pool inflates the *total* measurement relative to the physiologically active free
fraction — are biased in the *opposite* direction, exactly as globulin-binding chemistry predicts. ESR, a assay
that is directly driven by plasma protein-induced red-cell aggregation (rouleaux), is elevated independently of
inflammatory status (i.e., at matched CRP). A single upstream exposure (excess plasma globulin/immunoglobulin,
elevated in non-white populations) thus produces a whole panel of directionally-predicted, mechanistically
distinct biases — this internal coherence is itself strong evidence that the effect is a genuine
protein-interference artifact and not a generic confound or selection effect.

---

## 3. The Corrected-Calcium Formula Is Racially Miscalibrated (Precise Claim)

The standard albumin-corrected-calcium formula, embedded in essentially every EHR, adjusts total calcium for
albumin but **does not include globulin** — and globulin, not albumin, is the protein fraction elevated in
non-white populations and responsible for the binding-driven excess. The precise, honestly-stated result:

- Applying the albumin correction does **not** remove the racial bias: corrected calcium still reads
  **+0.15 mg/dL higher in Black patients at matched (true) ionized calcium, z = +7.3**.
- The albumin-corrected formula **misses true (ionized) hypocalcemia in roughly 40% of ICU patients overall**
  — but this miss rate is **not meaningfully differential by race in the binary sense**: among patients whose
  corrected calcium reads "normal," 40.9% of White patients and 38.8% of Black patients are, in truth,
  hypocalcemic by ionized calcium.

**The correct framing, stated precisely, is that the racial miscalibration is *continuous*, not a *differential
binary miss-rate*.** The corrected-calcium value itself sits systematically higher in Black patients at any
given true calcium level (a calibration shift, z = +7.3) — it is not the case that the formula's binary
"normal/abnormal" call is differentially wrong by race (the ~40% overall miss rate is essentially equal across
races). This is analogous to, but structurally different from, the eGFR race-coefficient problem: there, a race
term was explicitly present and removed; here, the formula is *blind* to a race-associated variable (globulin)
that it should — but does not — include. The fitted coefficients (Section 1.6; Ca +0.30–0.31 mg/dL per g/dL
protein) point toward a globulin-inclusive correction as the formal fix, though — as discussed in Section 5 —
the pragmatic, deployable answer is measuring the physiologically active quantity (ionized calcium) directly
rather than retrofitting the total-calcium formula, because total protein/globulin is itself measured in only
~2–3% of draws and that subsample is not representative (MNAR — sicker patients, enriched for globulin-workup
pathology).

---

## 4. Consequences at the Measurement/Misclassification Level (Solid)

These are consequences of the biased *measurement itself* — misclassification, not downstream treatment or
hard clinical outcomes (the latter is a separate, more fragile chain; see Section 6).

### 4.1 Masked hypocalcemia — threshold-dependent

Overall, masked hypocalcemia (true ionized calcium <1.12 but total calcium reads ≥8.5, i.e., "normal") is more
common in Black patients: **20.9% vs. 16.5%** (White). Breaking this down by severity of the true (ionized)
hypocalcemia reveals a threshold-dependent — and honestly reported — reversal:

| true hypocalcemia band (ionized calcium) | Black | White |
|---|---|---|
| Mild (1.00–1.12) | **26.2%** masked | **18.1%** masked |
| Severe (<1.00) | **7.3%** masked | **9.2%** masked |

The Black-excess masking effect is concentrated in, and should be reported as specific to, the **mild**
hypocalcemia range; at severe hypocalcemia the direction **reverses** (White patients are masked slightly more
often). This threshold-dependence is a load-bearing caveat and must not be generalized to "all hypocalcemia."

### 4.2 Spurious hypercalcemia flag

The same falsely-high total calcium also produces a spurious hypercalcemia flag at the opposite end of the
distribution:

> Spurious (false) hypercalcemia flag: **adjusted OR 1.50, z = +2.9**

This drives unnecessary hypercalcemia/malignancy workup disproportionately in Black patients — a distinct,
opposite-direction misclassification harm from the masked-hypocalcemia finding, both arising from the same
systematic +0.15 mg/dL total-calcium shift.

### 4.3 Supplementary note: masking and clinical response

As a further (non-outcome) indicator that the masking is behaviorally consequential, masked hypocalcemia is
associated with **less calcium repletion** (OR 0.74, z = −7.4) — i.e., the measurement itself changes what
clinicians do. A separate analysis of the *raw* racial gap in repletion at matched true hypocalcemia (OR 0.72,
z = −6.9) barely moves after adjusting for the masking measurement (0.72 → 0.73), indicating this
repletion-rate gap is **largely a general care disparity, not one mediated by the measurement artifact** — an
honest, non-overclaimed distinction between the measurement-driven and general-disparity components of the
repletion gap.

---

## 5. Novelty

**What is already known (and must not be overclaimed as new):** globulin-driven pseudohypercalcemia, and the
failure of the albumin-correction formula in that setting, are documented — but **only in the context of
extreme paraproteinemia and monoclonal gammopathy (myeloma)**. The literature states plainly that "the effect
of globulin on calcium has not received enough attention... because of the few diseases that can cause large
fluctuations in globulin." Likewise, racial/ethnic differences in serum globulin and immunoglobulin levels, and
race-specific laboratory reference intervals, are well established — but that literature treats the elevated
values as the *true* biological state (i.e., the reference range should differ), not as a *source of
measurement error* propagating into other analytes.

**The novel synthesis of this work:** normal, everyday, population-level, race-associated globulin variation
(on the order of 0.3–0.6 g/dL — far short of myeloma-range paraproteinemia) is sufficient to reproduce the
same globulin-interference artifact **at population scale, in the general ICU population**, and to do so
**coordinately across the routine chemistry panel** (Section 2), with the standard correction formula
(Section 3) failing to remove it. This reframes globulin interference from a rare-disease laboratory curiosity
into a population-level, race-structured measurement-equity issue affecting some of the most commonly ordered
laboratory tests in medicine. No existing publication frames routine electrolyte/calcium measurement as
systematically racially biased by ordinary immunoglobulin variation, nor connects this to the race-based
reference-range debate, nor demonstrates the coordinated, panel-wide, mechanistically coherent signature
documented here.

---

## 6. Limitations

- **Threshold-dependence.** The headline masked-hypocalcemia disparity (Black 26.2% vs. White 18.1%) is
  specific to the **mild** true-hypocalcemia range (ionized 1.00–1.12); at **severe** hypocalcemia (ionized
  <1.00) the direction **reverses** (7.3% vs. 9.2%). Any presentation of this finding must state the range
  explicitly and not generalize to "hypocalcemia" without qualification.
- **Berkson-type selection in the paired-test cohort.** Ionized calcium is not drawn at random — the paired
  (total-and-ionized) cohort is race-skewed: roughly 6% of Black admissions vs. 10% of White admissions receive
  an ionized calcium draw. This caps the generalizability of *prevalence* figures (e.g., absolute masking rates
  in the full admitted population) even though the *internal* comparison (bias at matched ionized calcium,
  within the drawn cohort) is not threatened by this selection.
- **The corrected-calcium miscalibration is continuous, not a differential binary miss-rate.** As stated
  precisely in Section 3, the ~40% overall miss rate of the albumin-corrected formula is essentially the same
  across races (40.9% White vs. 38.8% Black); the racial problem is the systematic +0.15 mg/dL continuous
  upward shift at matched true calcium, not a race-differential probability of a missed binary flag. This
  document deliberately does not claim the latter.
- **Citrate/CRRT and pH are excluded as drivers** (Section 1.2), but total protein/globulin itself is measured
  in only ~2–3% of MIMIC draws, and that subsample is not missing-at-random (it is enriched for sicker patients
  undergoing a globulin workup) — the *dose-response slope* (replicated at much larger, more representative
  scale in SICdb, n in the tens of thousands, z = +39.6) is the load-bearing mechanistic evidence, not the
  small MIMIC mediation subsample.
- **Downstream hard clinical-outcome harm is separate and more fragile, and is not the subject of this
  document.** A chain linking masked hypocalcemia to unrecognized QT prolongation and arrhythmia/mortality was
  explored elsewhere in this research program; an independent red-team of that chain concluded the
  measurement bias and a modest ECG (QTc) association are real, but the hard arrhythmia/mortality outcome
  claims are **not robustly established** (fragile event counts, unresolved ICD-timing/temporality concerns in
  MIMIC, and non-replication of the mortality association in eICU) and should be treated as
  hypothesis-generating, not demonstrated. This document is scoped to the measurement bias, the mechanism, and
  the misclassification-level consequences, which are the solid, multi-dataset-replicated components of the
  finding.
- **Single-hospital origin of the primary point estimate.** The precise +0.15 mg/dL magnitude is a MIMIC
  (single hospital) estimate; the eICU hospital-fixed-effects replication (+0.092 mg/dL, z = 3.30) confirms the
  **direction and a substantial fraction of the magnitude** across 129 independent hospitals, but the exact
  point estimate — like any single-analyzer measurement — is not expected to be identical across sites with
  different instrumentation.

---

## Appendix: Key Numbers at a Glance

| claim | dataset | estimate | z / stat | n |
|---|---|---|---|---|
| Total Ca falsely high vs. ionized Ca, Black vs. White | MIMIC | +0.15 mg/dL | z = +11.6 | 25,163 pairs, 3,442 Black |
| ...pH-adjusted | MIMIC | +0.167 (strengthens) | — | — |
| ...albumin-corrected | MIMIC | +0.15 mg/dL | z = +7.3 | full albumin cohort (n=10,005) |
| ...tight 10-min window | MIMIC | +0.156 | — | — |
| ...subject-clustered, first-pair | MIMIC | +0.15-scale | z = 10.3 | — |
| ...citrate/CRRT excluded | MIMIC | +0.129 mg/dL | z = +9.3 | 23,622 |
| Total-Ca excess ~ total protein (mechanism) | MIMIC | +0.30 mg/dL per g/dL | z = +9.5 | — |
| Total-Ca excess ~ total protein (correction-tool fit) | MIMIC | +0.31 mg/dL per g/dL | — | — |
| Total-Ca excess ~ total protein (mechanism replication) | SICdb (Austria) | +0.053 mmol/L per g/dL | z = +39.6 | — |
| Calcium racial replication, naive | eICU | +0.236 mg/dL | z = 8.1 | 62,388 pairs, 21,275 pts, 129 hospitals |
| Calcium racial replication, hospital-FE | eICU | +0.092 mg/dL | z = 3.30 (p<0.001) | same |
| Masked hypocalcemia, overall | MIMIC | 20.9% Black vs. 16.5% White | — | — |
| Masked hypocalcemia, mild band (ionized 1.00–1.12) | MIMIC | 26.2% vs. 18.1% | — | — |
| Masked hypocalcemia, severe band (ionized <1.00) — reverses | MIMIC | 7.3% vs. 9.2% | — | — |
| Masked hypocalcemia | eICU | 22.7% vs. 13.2% (FE-adj +3.0pp) | z = 2.1 | — |
| Spurious hypercalcemia flag | MIMIC | adj OR 1.50 | z = +2.9 | — |
| Masking → less Ca repletion | MIMIC | OR 0.74 | z = −7.4 | — |
| Sodium (indirect ISE vs. blood-gas), Black−White | MIMIC | −1.18 mEq/L | z = −12.6 | — |
| Chloride (indirect ISE vs. blood-gas), Black−White | MIMIC | −0.79 mEq/L | z = −3.5 | — |
| ESR falsely high at matched CRP | MIMIC | — | z = +4.2 | — |
| Total T4 falsely high at matched free T4 (ns) | MIMIC | — | z = +1.3 (underpowered) | — |
| Corrected-Ca continuous racial shift | MIMIC | +0.15 mg/dL | z = +7.3 | — |
| Corrected-Ca binary miss rate (NOT differential) | MIMIC | 40.9% White vs. 38.8% Black | — | — |
