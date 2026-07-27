# The upstream mechanism: race-associated immunoglobulin/globulin variation as a population-scale measurement-bias driver

**Source data:** MIMIC-IV paired chemistry–blood-gas draws with directly-measured globulin, immunoglobulins
(IgG, IgA), and cholesterol (`sodium_mechanism_definitive.py`); cross-cohort extension across race/ethnicity
(`sodium_extend.py`, n=15,098); external literature (PubMed/WebSearch, retrieved July 2026). This document
consolidates the *biological mechanism* underlying the sodium/chloride/calcium/ESR measurement biases
described in `docs/REAL_RESULTS_SODIUM_RACE_BIAS.md`; potassium (`02_potassium_pseudohyperkalemia.md`) is
explicitly excluded — its bias runs the opposite direction and traces to a distinct, pre-analytic
(hemolysis) mechanism, not to globulins.

## Abstract

Total plasma globulin and specific immunoglobulins (IgG, IgA) are elevated in non-white populations
relative to White patients, and this elevation produces a graded, dose-dependent measurement bias across
routine chemistry: it **displaces plasma water**, causing indirect-ISE assays to under-report sodium and
chloride, and it **binds calcium**, causing total calcium to over-report relative to the physiologically
active ionized fraction (with a parallel rouleaux effect elevating ESR). Each analyte's dose-response slope
on directly-measured globulin/immunoglobulin/lipid is statistically robust (sodium: globulin −1.02 mEq/L
per g/dL, z = −2.9; IgG −0.107 per 100 mg/dL, z = −3.3; IgA −0.178 per 100 mg/dL, z = −2.3; cholesterol
−1.58 per 100 mg/dL, z = −7.0), and the same immunoglobulin elevation is documented across every affected
non-white group (IgG: WHITE 961 → BLACK 1350, HISPANIC 1458, ASIAN 1240 mg/dL), with the sodium bias
itself extending beyond the Black–White axis to Hispanic (−1.01 mEq/L, z = −6.8) and Asian (−0.71 mEq/L,
z = −4.9) patients. None of this chemistry is new in isolation — globulin-driven pseudohyponatremia and
pseudohypercalcemia are textbook phenomena, and elevated immunoglobulins in Black populations have been
documented for over 50 years. What is novel is the **synthesis**: that ordinary, population-level,
race-associated globulin variation (on the order of 0.5 g/dL) — far short of the myeloma/paraproteinemia
extremes the existing interference literature focuses on — is large enough to produce a systematic,
racially-structured measurement bias across the routine chemistry panel in the general hospitalized
population, not merely in rare monoclonal-gammopathy patients.

## 1. The mechanism

Elevated plasma globulins/immunoglobulins act on different assays in different, chemically-predictable
ways:

- **Indirect-ISE sodium/chloride (falsely low):** the indirect-ISE method infers ion concentration from a
  diluted sample and back-calculates assuming a fixed plasma-water fraction. Excess protein/lipid solids
  displace plasma water; the assay does not correct for this displacement, so it under-reports sodium and
  chloride when protein (or lipid) is elevated. This is the classic "electrolyte-exclusion effect."
- **Total calcium (falsely high):** roughly 40–45% of plasma calcium circulates bound to protein, and a
  meaningful fraction of that is bound to globulin, not just albumin. Excess globulin binds additional
  calcium, raising *total* calcium while the physiologically active *ionized* calcium is unaffected. Because
  the standard correction formula adjusts only for albumin, it does not remove this globulin-driven excess.
- **ESR (falsely high):** excess circulating immunoglobulin promotes red-cell rouleaux formation, which
  accelerates erythrocyte sedimentation independent of the inflammatory process ESR is meant to track.

All three are consequences of the same upstream quantity — elevated globulin/immunoglobulin — acting through
three distinct, well-established biophysical pathways (water displacement, calcium binding, rouleaux), each
producing bias in the chemistry-predicted direction.

## 2. Dose-response on directly-measured analytes

Streaming directly-measured globulin, IgG, IgA, and cholesterol (rather than proxying with total
protein − albumin) gives a clean dose-response test of the mechanism on the sodium bias:

| solid-phase analyte | dose-response slope (sodium bias) | z |
|---|---|---|
| **globulin** | **−1.02 mEq/L per g/dL** | **−2.9** |
| **IgG** | **−0.107 mEq/L per 100 mg/dL** | **−3.3** |
| IgA | −0.178 mEq/L per 100 mg/dL | −2.3 |
| **cholesterol** (lipid pathway) | **−1.58 mEq/L per 100 mg/dL** | **−7.0** |
| total protein (proxy) | −0.93 mEq/L per g/dL | −7.3 |

The lipid pathway (cholesterol/triglycerides) is confirmed independently — this is the classic
*lipemic* pseudohyponatremia — but lipids are **higher in White patients** (triglycerides 233 vs 197), so
the lipid pathway does **not** drive the racial component of the bias; it is a parallel, non-racial
contributor to the same indirect-ISE artifact. The racial component is specifically attributable to
**protein/globulin/immunoglobulin**, cleanly separated from lipid. The magnitude is also quantitatively
consistent with plasma-water physics: the plasma-water equation predicts roughly −1.0 to −1.4 mEq/L of
sodium bias per g/dL of plasma solids at a sodium near 140 mEq/L, and the observed globulin/total-protein
slopes (−0.9 to −1.0) fall directly in that predicted range — a quantitative match, not merely a directional
association.

On the calcium side, total-calcium excess over ionized calcium tracks total protein at **+0.30 mg/dL per
g/dL (z = +9.5)**, and a directly-fitted protein coefficient in the same analysis gives **+0.31 mg/dL per
g/dL** — the same mechanism, opposite-signed effect (binding raises total calcium rather than diluting it),
exactly as globulin-binding chemistry predicts.

## 3. Elevated in every affected non-white group

The mediating quantities — total protein, globulin, and specifically IgG — are elevated across Black,
Hispanic, and Asian patients relative to White patients, tracking the same groups in which the sodium bias
is observed:

| group | mean IgG (mg/dL) |
|---|---|
| WHITE | 961 |
| BLACK | **1350** |
| HISPANIC | **1458** |
| ASIAN | **1240** |

## 4. Cross-ethnic extent of the measurement bias

The sodium bias itself extends across the same groups, not merely Black–White (`sodium_extend.py`,
n=15,098):

| group | mean chem − blood-gas Na bias | differential vs WHITE | z |
|---|---|---|---|
| WHITE | +2.28 | ref | — |
| BLACK | +1.09 | −1.18 | −12.6 |
| **HISPANIC** | +1.27 | **−1.01** | **−6.8** |
| **ASIAN** | +1.56 | **−0.71** | **−4.9** |
| OTHER | +2.35 | +0.07 | ns |

The disparity is therefore a broad non-white measurement bias — not an artifact specific to the Black–White
comparison — consistent with the immunoglobulin elevation being broadly non-white rather than
Black-specific.

## 5. Literature: what is already known, and what is genuinely new

**Known for decades, but confined to disease extremes:**
- Globulin/protein-driven indirect-ISE pseudohyponatremia (the "electrolyte-exclusion effect") is textbook,
  and IVIG-associated pseudohyponatremia is a well-documented clinical entity
  ([NEJM 1998](https://www.nejm.org/doi/full/10.1056/NEJM199808273390914);
  [StatPearls](https://www.ncbi.nlm.nih.gov/books/NBK553207/);
  [Clinical Chemistry review](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10299669/)).
- Panel-wide electrolyte exclusion (Na, K, Cl) on indirect-ISE assays is published, with a slope
  (~0.8 mmol/L Na per g/dL total protein) that matches this study's; it has been studied specifically in
  **hyperproteinemia/myeloma extremes**, and the Cl/K analogues are described as "rarely clinically
  significant" ([J Lab Physicians](https://jlabphy.org/discrepancies-in-electrolyte-measurements-by-direct-and-indirect-ion-selective-electrodes-due-to-interferences-by-proteins-and-lipids/);
  [paraproteins & electrolyte assays, 2023](https://pubmed.ncbi.nlm.nih.gov/37114525/)).
- Pseudohypercalcemia from excess globulin, and the failure of albumin-only calcium correction to remove
  it, is known — but again **only in paraproteinemia/monoclonal gammopathy**
  ([Frontiers in Oncology, 2024](https://www.frontiersin.org/journals/oncology/articles/10.3389/fonc.2024.1441851/full);
  [paraprotein cohort, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12608535/)). The literature states
  plainly that "the effect of globulin on calcium has not received enough attention... because of the few
  diseases that can cause large fluctuations in globulin."
- Elevated serum globulin/IgG in Black populations relative to White populations has been documented for
  over 50 years: a 1974 study reports gamma-globulin differences
  ([PubMed](https://pubmed.ncbi.nlm.nih.gov/4158577/)), and a 1995 study reports IgG **1,587 vs 1,209
  mg/dL** ([PubMed](https://pubmed.ncbi.nlm.nih.gov/7722770/)) — closely matching this study's own measured
  gap (1,350 vs 961 mg/dL). Race-specific reference intervals for immunoglobulins exist in the clinical
  laboratory literature, but treat the elevated values as a *true* physiological baseline requiring its own
  normal range, not as a source of *measurement error in other analytes*
  ([racial/ethnic reference intervals](https://pubmed.ncbi.nlm.nih.gov/26468426/)).
- The cause of the elevated baseline immunoglobulin level is established as **both genetic** — IGHG2/IGHG3
  immunoglobulin heavy-chain gene diversity, and the Duffy-null allele as a determinant of systemic
  immune-marker levels — **and environmental** — chronic immune activation and infectious-disease burden
  ([Genes & Immunity](https://www.nature.com/articles/s41435-021-00156-2)).
- Separately, existing epidemiology reports racial differences in the *prevalence* of hyponatremia (e.g., in
  heart failure) and treats these as real disease burden differences
  ([PMC6583993](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6583993/)), without considering that some
  fraction of the reported disparity could be a measurement artifact of the mechanism described here.

**What is genuinely novel (the synthesis):** the existing globulin-interference literature is confined to
rare, extreme disease states (myeloma, monoclonal gammopathy, IVIG infusion) and treats the interference as
a laboratory curiosity in those patients. No prior work has shown that **normal, population-level,
race-associated globulin variation (on the order of 0.5 g/dL)** — well short of paraproteinemia — produces a
**systematic, ubiquitous, racially-structured measurement bias across the routine chemistry panel in the
general hospitalized population**. Nor has prior work connected this mechanism to the ongoing debate over
race-specific reference intervals, nor shown that standard correction formulas (albumin-corrected calcium)
are themselves racially miscalibrated because they omit globulin. The reframe — from "rare myeloma
artifact" to "population-scale, immunoglobulin-driven racial measurement bias" — is the contribution of this
work.

## 6. The myeloma link

The same upstream immunoglobulin elevation that drives the panel-wide measurement bias is also upstream of
a well-described, larger disease-level phenomenon: multiple myeloma and MGUS are 2–3× more common in Black
patients, and this cohort reproduces that gradient (myeloma **0.95% vs 0.70%**, Black vs White). The scale
of the baseline (non-disease) immunoglobulin elevation is large enough that it partially closes the gap to
the myeloma population itself: Black patients **without** myeloma already have a mean IgG of approximately
**1,370 mg/dL**, approaching the mean IgG of **White myeloma** patients (~1,430 mg/dL). In other words, the
ordinary non-disease immunoglobulin baseline in Black patients sits much closer to a disease-level
(myeloma) immunoglobulin burden in White patients than either group's respective "normal" framing would
suggest — a finding with implications both for measurement bias (the subject of this document) and for how
IgG-based myeloma screening thresholds should be interpreted across race (a race-blind IgG cutoff produces
a substantially larger false-positive-flag pool in Black patients without myeloma, a related but separate
result described in the source analysis).

## 7. Limitations

- **The within-sample mediation of the racial differential is underpowered.** The clean, load-bearing
  evidence for the mechanism is the dose-response slope itself (graded, monotone, and replicated across an
  independent Austrian cohort — see `REAL_RESULTS_SODIUM_RACE_BIAS.md` §"MECHANISM DOSE-RESPONSE"), not the
  small-n within-sample mediation coefficient, which does not reach significance on its own.
- **Measured protein/globulin/immunoglobulin explains only part of the racial differential.** A
  back-of-envelope calculation (globulin gap ≈ 0.6 g/dL × slope ≈ 0.9 mEq/L per g/dL ≈ 0.5 mEq/L) accounts
  for roughly half of the observed ~1.2 mEq/L Black−White sodium differential; the remainder is
  unexplained by measured protein and should not be claimed as mechanistically closed.
- **Globulin/immunoglobulin measurement in this cohort is sparse and clinically selected (MNAR).** Total
  protein, globulin, and immunoglobulin panels are ordered selectively (more often in sicker patients with a
  suspected globulin-related workup), so the directly-measured dose-response subsample is not representative
  of the full cohort; its *direction* is corroborated by better-powered, more representative external
  cohorts, but its exact magnitude should be read cautiously.
- **The racial premise (elevated immunoglobulin) is well-established externally, but the specific
  synthesis (population-level bias across the *general* population, not just paraproteinemia) has not been
  externally replicated end-to-end in a second cohort with the same panel of directly-measured
  immunoglobulins.**
- **Subclinical, uncoded globulin elevation cannot be measured or excluded** as a residual confounder of the
  "diagnosed disease" exclusion analyses referenced in the companion sodium/calcium document.
- This document strictly excludes potassium: the potassium racial bias (`02_potassium_pseudohyperkalemia.md`)
  is uncorrelated with the sodium protein-bias and runs in the opposite direction from what the
  globulin/immunoglobulin mechanism predicts, and is attributed instead to a pre-analytic (hemolysis-type)
  mechanism.
