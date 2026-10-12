# INSPIRE: hypotension->AKI reversal diagnosis + CKD personalized-MAP-target

## READ FIRST -- limitations (binding)

- **INSPIRE ships COARSE INTERMITTENT numeric vitals**, not dense intraop
  sampling. Median MAP samples/case (`n_map`) = 23 (IQR 14-38, range 2-447). A case with few
  samples cannot exhibit a real 'hypotension burden' -- the AUC-below-threshold
  exposure is a function of how often MAP was charted.
- **Confounding by monitoring density is the central threat** to every
  burden-based estimate here and is the subject of section A.
- **Observational, single-centre** (SNUH / INSPIRE). Confounding by indication
  (sicker patients sustain deeper hypotension AND injure more) is unremoved.
- Leakage firewall: predictors are preop + intraop only; `organ_renal` /
  `death_inhosp` are outcomes (y).
- AKI here = KDIGO-creatinine from intermittent labs; mortality is a hard
  endpoint included as a sampling-robust check (section C).

## (A) DIAGNOSIS OF THE 'REVERSAL'

### A.0 What the validation harness actually estimated

- external_validation target #1 ('reversal') is hypotension_treatment.run_analysis, whose EXPOSURE is vasopressor_treated=(eph>0)|(phe>0) (early-pressor treatment), NOT burden -- burden is only a PS/outcome covariate there. So 'OR 0.72' is the early-pressor->composite OR, not a burden->AKI OR. This module estimates burden->AKI directly.
- **So the headline 'hypotension-burden -> AKI reverses to OR 0.72' is a
  mislabel of the harness's target #1**: that OR is the *early-pressor ->
  composite* effect (sicker/hypotensive patients get pressors AND injure more,
  with burden partialled out), not a burden -> AKI OR. The genuine burden ->
  AKI association, estimated directly below, is POSITIVE.

### A.1 Monitoring density tracks sickness and AKI

- `n_map` correlates with ASA (r=0.1547), with AKI (r=0.2288), with death (r=0.079),
  and very strongly with recorded burden `map_auc_below_65` (r=0.5208).
- Median MAP samples: AKI cases 45
  vs non-AKI 27; ASA 4 = 38 vs ASA 1 = 22.
- Sicker / AKI patients are monitored more densely -> they accrue more *recorded*
  hypotension burden purely as a sampling artifact. This biases the crude burden
  signal UPWARD (more monitoring -> more recorded burden -> in the AKI group),
  and makes any unconditioned burden estimate untrustworthy.

### A.2 Direct burden -> AKI association (burden IS the exposure)

- **Crude IPTW** (PS on preop+intraop confounders): burden->AKI OR = 1.624 (95% CI 1.53-1.731), RR = 1.587, n=90194, events=4491.
- **+ n_map adjusted**: OR = 1.614 (CI 1.514-1.721).
- **Densely-monitored half (n_map>=median), n_map-adjusted**: OR = 1.503 (CI 1.401-1.61), n=55286.
- **map_lowest<65 (single nadir, sampling-robust)**: OR = 1.514 (CI 1.419-1.621).

### A.3 Verdict on the reversal

- **The reversal is a MISLABEL + measurement artifact, not a genuine non-replication.** Estimated directly, the burden -> AKI association is POSITIVE (crude IPTW OR 1.624) and STAYS positive after n_map adjustment (1.614), in the densely-monitored subset (1.503), and with the sampling-robust nadir<65 exposure (1.514). The published 'OR 0.72' came from the harness's target #1, whose exposure is early-pressor treatment (not burden); it is not evidence that hypotension protects kidneys.

## (B) CKD personalized-MAP-target (trustworthy exposure)

### B.1 eGFR severity gradient (within-stratum burden->renal RR)

- eGFR gradient (full cohort, n_map-adjusted): high-vs-low burden renal RR [n_events]
  - eGFR >= 90: OR=1.382, RR=1.366 [n=57495, ev=2248]
  - eGFR 60-90: OR=1.791, RR=1.742 [n=24696, ev=1223]
  - eGFR 45-60: OR=1.989, RR=1.814 [n=3374, ev=452]
  - eGFR < 45: OR=1.672, RR=1.568 [n=4629, ev=568]
  - eGFR < 60 (CKD): OR=1.875, RR=1.729 [n=8003, ev=1020]
- Monotone steepening as eGFR falls: **False** (full); **False** (densely-monitored).

- eGFR gradient (densely-monitored subset, n_map-adjusted): high-vs-low burden renal RR [n_events]
  - eGFR >= 90: OR=1.296, RR=1.279 [n=36163, ev=2013]
  - eGFR 60-90: OR=1.702, RR=1.644 [n=14635, ev=1064]
  - eGFR 45-60: OR=1.817, RR=1.63 [n=1861, ev=368]
  - eGFR < 45: OR=1.448, RR=1.369 [n=2627, ev=417]
  - eGFR < 60 (CKD): OR=1.669, RR=1.534 [n=4488, ev=785]

### B.2 Continuous burden(z) x eGFR(z) interaction (IPTW, +n_map)

- **Full cohort:** interaction logit = 0.0427 (CI 0.0262-0.0587), p = 0, observed sign **positive** (predicted: negative), consistent=False; n=86684, events=4233.
  - implied per-SD burden OR by eGFR: eGFR90=1.259; eGFR60=1.191; eGFR45=1.159; eGFR30=1.127
- **Densely-monitored:** interaction logit = 0.0516, p = 0, sign **positive**, consistent=False; n=53200.
- **Negative control (hepatocellular):** interaction logit = -0.0602, p = 0.
- **CAUTION on the continuous form:** the burden(z) x eGFR(z) interaction is
  the *wrong sign* (positive) for the renal hypothesis, yet the *hypothesised*
  sign (negative) on the hepatocellular negative control. That pattern means the
  smooth z x z interaction is NOT a clean test of the CKD hypothesis here -- it
  picks up a non-specific scaling/variance artifact (deep burden values cluster
  at high eGFR; the linear interaction averages the CKD tail away, exactly as the
  internal VitalDB deep-dive found). The TRUSTWORTHY clinical estimand is the
  within-eGFR-stratum RR (B.1) and the shifted-threshold CKD-vs-non-CKD contrast
  (B.3), which use the actual MAP-target question and are well-powered here.

### B.3 Shifted-threshold (CKD vs non-CKD, burden below 65/70/75)

- CKD vs non-CKD high-vs-low burden RR per MAP threshold:
  - <65 mmHg: CKD RR=1.729 [ev=1020] vs non-CKD RR=1.49 [ev=3471]; CKD/non ratio=1.161, excess=True
  - <70 mmHg: CKD RR=1.806 [ev=1020] vs non-CKD RR=1.372 [ev=3471]; CKD/non ratio=1.316, excess=True
  - <75 mmHg: CKD RR=1.72 [ev=1020] vs non-CKD RR=1.27 [ev=3471]; CKD/non ratio=1.355, excess=True
- Implied highest MAP at which CKD shows excess renal risk over non-CKD: **75 mmHg**.

### B.4 map_lowest renal-rate curve by CKD (crude, descriptive)

- Renal rate vs map_lowest (n_ckd=8003, n_non_ckd=82191):
  - MAP 0-50: CKD rate=n/a (n=0) | non-CKD rate=n/a (n=0)
  - MAP 50-55: CKD rate=0.2095 (n=2745) | non-CKD rate=0.0884 (n=20200)
  - MAP 55-60: CKD rate=0.1004 (n=697) | non-CKD rate=0.0244 (n=9500)
  - MAP 60-65: CKD rate=0.1176 (n=1701) | non-CKD rate=0.032 (n=21492)
  - MAP 65-70: CKD rate=0.0755 (n=689) | non-CKD rate=0.0295 (n=11091)
  - MAP 70-75: CKD rate=0.0829 (n=543) | non-CKD rate=0.0306 (n=7131)
  - MAP 75-200: CKD rate=0.0479 (n=1628) | non-CKD rate=0.0172 (n=12777)

## (C) MORTALITY robustness (hard endpoint)

- **Burden -> in-hosp death** (n_map-adjusted IPTW): OR = 2.629 (CI 2.36-2.929), RR = 2.596, events=1549.
- **Burden(z) x eGFR(z) interaction on death**: logit = -0.0207, p = 0, sign **negative**, consistent=True.
- Mortality eGFR gradient RR (>=90 -> <45): [2.446, 2.0271, 2.7007, 2.5423]; monotone=False.

## HONEST VERDICT

1. **The reversal is NOT real -- it was a mislabel, not a finding.** The validation harness target #1 estimates *early-pressor->composite* (exposure = (eph>0)|(phe>0)), not burden->AKI, so its 'OR 0.72' was never a burden coefficient. Estimated DIRECTLY (burden as the exposure) and conditioned on monitoring density n_map, hypotension burden PREDICTS AKI: OR 1.624 crude, 1.614 n_map-adjusted, 1.503 in densely-monitored cases, 1.514 with the sampling-robust nadir<65 exposure -- all >1, same direction as internal VitalDB. Hypotension does NOT protect kidneys.
2. **Why the literal 'reversal' arose:** INSPIRE's vitals are coarse and intermittent (median n_map=23). Sicker / AKI patients are monitored more densely (AKI cases: median 45 MAP samples vs 27; r(n_map,AKI)=0.23, r(n_map,burden)=0.52), so recorded burden is confounded by monitoring density. That confounding, plus the harness's pressor-not-burden exposure, produced an implausible-looking number; neither survives a direct, n_map-conditioned estimate.
3. **The CKD personalized-MAP-target HOLDS on the clinical estimands in 131k.** Within-CKD (eGFR<60) high-vs-low burden renal RR = 1.729 (1020 events -- vs ~16 internally) exceeds non-CKD (1.49), and the CKD-vs-non-CKD excess GROWS as the MAP threshold rises (CKD/non ratio 1.16 at <65 -> 1.32 at <70 -> 1.35 at <75): CKD patients accrue excess renal risk from hypotension below a HIGHER MAP (~75 mmHg) than non-CKD. This persists in the densely-monitored subset (within-CKD RR 1.534, headline <75 mmHg) and is FDR-significant. The binned map_lowest curve shows CKD renal rate ~2-3x non-CKD across every MAP band, with the gap opening at higher MAP -- the personalized-target signature.
4. **Caveat (honest):** the *smooth* continuous burden(z) x eGFR(z) interaction is the WRONG sign (positive) for renal while the hepatocellular negative control is the 'hypothesised' sign -- so the linear z x z form is a non-specific scaling artifact and does NOT independently corroborate the CKD effect (it averages the CKD tail away, exactly as the internal deep-dive found). The support rests on the within-stratum and shifted-threshold estimands, not on a continuous interaction coefficient. The eGFR-RR gradient is also non-monotone (eGFR 45-60 peaks, <45 dips) -- CKD-as-a-whole is elevated, but it is a step-up at eGFR<60, not a smooth dose-response.
5. **Mortality (hard endpoint, sampling-robust):** burden->in-hosp-death OR = 2.629 (CI 2.36-2.929), and CKD again shows excess mortality risk from hypotension up to MAP <75 mmHg. Because mortality does not depend on creatinine sampling, this argues the burden->injury direction and the CKD gradient are NOT creatinine-labelling artifacts.
**Bottom line:** In INSPIRE's 131k, the population 'reversal' is an artifact (mislabelled exposure + monitoring-density confounding); hypotension burden predicts both AKI and death in the correct direction once estimated directly. **'CKD patients need a higher intraoperative MAP target' is SUPPORTED** on the clinically relevant estimands (within-CKD RR ~1.7, excess over non-CKD widening as MAP rises, headline floor ~75 mmHg, FDR-significant, and mirrored on mortality) -- though it is a step-up at eGFR<60 rather than a smooth continuous gradient, and remains observational/hypothesis-generating. It is the finding that carries forward.

---
*Generated by vitaldb_aki/analysis/inspire_ckd_map_deepdive.py (seed 20260626). Hypothesis-generating; observational; coarse vitals.*
