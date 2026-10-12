# Generalizability of requirement -> in-hospital mortality across MIMIC-IV subgroups

The pooled MIMIC-IV ICU cohort already shows a strong vasopressor-requirement -> mortality signal. This asks whether the SAME (age-adjusted) signal holds *within* clinically distinct subgroups and whether it is CONSISTENT (overlapping CIs) or HETEROGENEOUS. The finding originated intraoperatively (anaesthesia): holding in SURGICAL (SICU) and CARDIAC (CVICU) ICUs bridges the ICU result back to that origin; holding within SEPSIS (the classic vasoplegia population, where everyone is sick) and across MICU/CCU/TSICU shows breadth.

- Cohort: **15949** norepi ICU stays with age + mortality + careunit join.
- Per-stay requirement = median norepinephrine rate (mcg/kg/min), gate 0<rate<=5.

## Overall
- OR 3.798/SD [3.441, 4.174], n=15949, deaths=5258 (0.33), AUC age 0.559 -> +req 0.764 (Delta 0.2051)

## 1. By ICU type (first_careunit) -- SICU + CVICU highlighted (bridge to OR origin)
- **MICU:** OR 3.779/SD [3.287, 4.298], n=5083, deaths=1896 (0.373), AUC age 0.557 -> +req 0.751 (Delta 0.194)
- **SICU:** OR 2.684/SD [2.276, 3.16], n=1650, deaths=570 (0.345), AUC age 0.583 -> +req 0.739 (Delta 0.156)  <- surgical/cardiac, bridge to intraoperative origin
- **CVICU:** OR 4.096/SD [2.568, 7.103], n=2363, deaths=363 (0.154), AUC age 0.532 -> +req 0.793 (Delta 0.2617)  <- surgical/cardiac, bridge to intraoperative origin
- **CCU:** OR 4.882/SD [3.504, 6.641], n=1854, deaths=738 (0.398), AUC age 0.58 -> +req 0.796 (Delta 0.2151)
- **MICU/SICU:** OR 3.32/SD [2.798, 4.045], n=2848, deaths=986 (0.346), AUC age 0.565 -> +req 0.755 (Delta 0.1898)
- **TSICU:** OR 3.918/SD [2.472, 5.842], n=1569, deaths=512 (0.326), AUC age 0.564 -> +req 0.769 (Delta 0.2051)

## 2. Sepsis (ICD-9 995.91/995.92/785.52; ICD-10 A41*, R65.20/R65.21)
Does the requirement still stratify mortality WITHIN septic patients (vasoplegia expected, everyone sick)?
- **Septic:** OR 3.519/SD [3.208, 3.863], n=7894, deaths=3062 (0.388), AUC age 0.565 -> +req 0.754 (Delta 0.1894)
- **Non-septic:** OR 3.855/SD [3.275, 4.578], n=8055, deaths=2196 (0.273), AUC age 0.553 -> +req 0.766 (Delta 0.2131)

## 3. Age strata
- **<55:** OR 3.63/SD [2.877, 4.496], n=3730, deaths=1069 (0.287), AUC age 0.521 -> +req 0.765 (Delta 0.2441)
- **55-70:** OR 3.911/SD [3.445, 4.401], n=6174, deaths=1864 (0.302), AUC age 0.503 -> +req 0.765 (Delta 0.262)
- **>70:** OR 3.75/SD [3.198, 4.36], n=6045, deaths=2325 (0.385), AUC age 0.544 -> +req 0.753 (Delta 0.2092)

## Sex
- **male:** OR 3.701/SD [3.227, 4.229], n=9315, deaths=2969 (0.319), AUC age 0.547 -> +req 0.764 (Delta 0.217)
- **female:** OR 3.926/SD [3.357, 4.532], n=6634, deaths=2289 (0.345), AUC age 0.572 -> +req 0.764 (Delta 0.1916)

## Heterogeneity / consistency
- Subgroups with a fitted OR+CI: 13; OR range [2.684, 4.882].
- Every subgroup CI excludes 1.0 (positive everywhere): **True**.
- All subgroup CIs overlap (no heterogeneity): **False**.
- Subgroups whose CI does not overlap the overall CI: ['ICU:SICU'].

## Verdict
GENERALIZABILITY (MIMIC-IV, n=15949 norepi ICU stays; age-adjusted, observational): overall requirement->mortality OR 3.798/SD [3.441, 4.174]. SURGICAL/SICU OR 2.684 [2.276, 3.16] (n=1650). CARDIAC/CVICU OR 4.096 [2.568, 7.103] (n=2363) -- bridges back to the intraoperative origin. WITHIN SEPSIS OR 3.519 [3.208, 3.863] (n=7894, deaths=3062): requirement still stratifies mortality where vasoplegia is expected and everyone is sick. MOSTLY GENERALIZES with HETEROGENEITY in MAGNITUDE: every subgroup OR>1 (CI excludes 1.0) but some CIs do not all overlap (OR range [2.684, 4.882]; outliers vs overall: ['ICU:SICU']). DIRECTION is consistent; effect SIZE varies by population. CAVEAT: age-adjusted only; the OR is confounded by illness severity within each stratum (sicker -> more pressor AND more death). Shows the requirement MARKS risk broadly, not a treatment effect.

## Caveats
- OBSERVATIONAL, AGE-ADJUSTED ONLY. The OR is confounded by illness severity within every stratum (sicker patients need more pressor AND die more). Subgroup analysis does not remove this; it shows the requirement MARKS risk within each stratum, not a treatment effect.
- Requirement = median of segment rates (mcg/kg/min); MIMIC rate is already per-kg.
- Sepsis is flagged by ICD diagnosis codes on the admission (hadm), not a clinical Sepsis-3 definition; it is a coarse proxy.
- first_careunit is the FIRST ICU of the stay; transfers are not modelled.
- 'Overlapping CIs' is a screen for heterogeneity, not a formal interaction test.
- Does NOT validate the arterial-waveform tone estimator (needs MIMIC-IV-Waveform).
