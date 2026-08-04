# Red-team: CKD personalized-MAP-target finding (INSPIRE 131k)

Adversarial stress-tests. Each round mounts the strongest attack a skeptical reviewer/biostatistician would make and tests it empirically. SURVIVES = the finding withstands; WEAKENED/BREAKS = honest downgrade.

## round1: RR non-collapsibility -- does CKD excess survive on the ADDITIVE (RD) scale?

```json
{
 "attack": "RR non-collapsibility -- does CKD excess survive on the ADDITIVE (RD) scale?",
 "strata": {
  "ckd": {
   "n": 8011,
   "events": 1020,
   "base_risk_unexposed": 0.0876,
   "crude_RD": 0.1221,
   "crude_RR": 2.393,
   "adj_RD": 0.0608,
   "adj_RD_ci": [
    0.0451,
    0.0774
   ],
   "adj_RR": 1.585
  },
  "non_ckd": {
   "n": 82235,
   "events": 3477,
   "base_risk_unexposed": 0.0291,
   "crude_RD": 0.0567,
   "crude_RR": 2.946,
   "adj_RD": 0.0151,
   "adj_RD_ci": [
    0.0118,
    0.0181
   ],
   "adj_RR": 1.409
  }
 },
 "additive_interaction_RD_ckd_minus_RD_nonckd": 0.0457,
 "multiplicative_ratio_RR_ckd_over_RR_nonckd": 1.125,
 "verdict": "SURVIVES on the additive scale (CKD adj-RD > non-CKD adj-RD AND CKD adj-RD CI excludes 0) -- the excess is real, not just RR non-collapsibility"
}
```
**Verdict:** SURVIVES on the additive scale (CKD adj-RD > non-CKD adj-RD AND CKD adj-RD CI excludes 0) -- the excess is real, not just RR non-collapsibility

## round2: confounding by indication/severity/procedure -- negative-control outcomes + procedure adjustment + E-value

```json
{
 "attack": "confounding by indication/severity/procedure -- negative-control outcomes + procedure adjustment + E-value",
 "negative_control_outcome_panel": {
  "organ_renal": {
   "additive_interaction": 0.0457,
   "RD_ckd": 0.0608,
   "RD_nonckd": 0.0151,
   "events": 4497
  },
  "organ_hypoperfusion": {
   "additive_interaction": 0.0297,
   "RD_ckd": 0.1185,
   "RD_nonckd": 0.0888,
   "events": 1769
  },
  "organ_hepatocellular": {
   "additive_interaction": 0.054,
   "RD_ckd": 0.0663,
   "RD_nonckd": 0.0122,
   "events": 6051
  },
  "organ_cholestatic": {
   "additive_interaction": 0.0437,
   "RD_ckd": 0.0697,
   "RD_nonckd": 0.026,
   "events": 4868
  },
  "organ_coagulation": {
   "additive_interaction": 0.0415,
   "RD_ckd": 0.0909,
   "RD_nonckd": 0.0494,
   "events": 3112
  }
 },
 "renal_additive_interaction": 0.0457,
 "max_nonrenal_control_interaction": 0.054,
 "procedure_adjusted": {
  "additive_interaction": 0.0407,
  "RD_ckd": 0.0542,
  "RD_nonckd": 0.0135,
  "added_cov": [
   "optype_code",
   "surgery_duration"
  ]
 },
 "ckd_adjusted_RR": 1.585,
 "e_value_ckd_RR": 2.549,
 "verdict": "WEAKENED -- specificity fails (renal 0.0457 vs max control 0.054); procedure-adjusted 0.0407 holds."
}
```
**Verdict:** WEAKENED -- specificity fails (renal 0.0457 vs max control 0.054); procedure-adjusted 0.0407 holds.

## round3: ascertainment (mortality endpoint) + dose-response confounding-resistance

```json
{
 "attack": "ascertainment (mortality endpoint) + dose-response confounding-resistance",
 "mortality_additive_interaction": {
  "interaction": 0.0412,
  "RD_ckd": 0.0487,
  "RD_nonckd": 0.0074,
  "events": 1474
 },
 "dose_response_aki_by_map_lowest": {
  "ckd": [
   {
    "band": ">=75",
    "n": 1628,
    "aki_rate": 0.0479
   },
   {
    "band": "65-75",
    "n": 1232,
    "aki_rate": 0.0787
   },
   {
    "band": "55-65",
    "n": 2398,
    "aki_rate": 0.1126
   },
   {
    "band": "<55",
    "n": 2745,
    "aki_rate": 0.2095
   }
  ],
  "non_ckd": [
   {
    "band": ">=75",
    "n": 12777,
    "aki_rate": 0.0172
   },
   {
    "band": "65-75",
    "n": 18222,
    "aki_rate": 0.0299
   },
   {
    "band": "55-65",
    "n": 30992,
    "aki_rate": 0.0297
   },
   {
    "band": "<55",
    "n": 20200,
    "aki_rate": 0.0884
   }
  ]
 },
 "dose_gradient_ckd": 0.1616,
 "dose_gradient_nonckd": 0.0712,
 "gradient_steeper_in_ckd": true,
 "verdict": "PARTIAL -- mortality CKD x hypotension additive excess = 0.0412 (ascertainment-robust, but mortality is itself non-specific); hypotension dose-response gradient steeper in CKD (0.1616 vs 0.0712)=True. A steeper CKD dose-response is the one confounding-resistant signal, but R2's pan-organ non-specificity still caps the renal-specific claim."
}
```
**Verdict:** PARTIAL -- mortality CKD x hypotension additive excess = 0.0412 (ascertainment-robust, but mortality is itself non-specific); hypotension dose-response gradient steeper in CKD (0.1616 vs 0.0712)=True. A steeper CKD dose-response is the one confounding-resistant signal, but R2's pan-organ non-specificity still caps the renal-specific claim.

## round4: vasoplegia index vs measured-SVRI -- fragility (leverage / single component / SVRI computation)

```json
{
 "attack": "vasoplegia index vs measured-SVRI -- fragility (leverage / single component / SVRI computation)",
 "component_spearman_vs_svri": {
  "tau_decay": 0.1582,
  "diastolic_over_map": 0.2387,
  "aug_index": -0.1694
 },
 "components_directionally_consistent": true,
 "index_spearman_full": -0.146,
 "n": 159,
 "jackknife_r_range": [
  -0.1648,
  -0.1313
 ],
 "r_drop_top5_influential": -0.1719,
 "bootstrap_ci": [
  -0.2975,
  0.0092
 ],
 "verdict": "FRAGILE -- index r=-0.146; bootstrap CI [-0.2975, 0.0092]; drop-top5 r=-0.1719; consistent=True."
}
```
**Verdict:** FRAGILE -- index r=-0.146; bootstrap CI [-0.2975, 0.0092]; drop-top5 r=-0.1719; consistent=True.

## round5: DEFENSIBILITY -- negative-control empirical-null calibration + bias analysis + positivity

```json
{
 "attack": "DEFENSIBILITY -- negative-control empirical-null calibration + bias analysis + positivity",
 "empirical_null": {
  "controls": {
   "organ_hepatocellular": 0.054,
   "organ_cholestatic": 0.0437,
   "organ_coagulation": 0.0415
  },
  "null_mean": 0.0464,
  "null_sd": 0.0067
 },
 "renal_raw_interaction": 0.0457,
 "renal_calibrated_interaction": -0.0007,
 "renal_z_vs_null": -0.1,
 "mortality_raw_interaction": 0.0412,
 "mortality_calibrated_interaction": -0.0052,
 "mortality_ckd_RR": 2.335,
 "e_value_mortality_ckd_RR": 4.101,
 "positivity": {
  "ps_range": [
   0.0081,
   1.0
  ],
  "frac_ps_lt_0.05": 0.001,
  "frac_ps_gt_0.95": 0.0099,
  "ckd_ps_median": 0.2139,
  "nonckd_ps_median": 0.1764
 },
 "verdict": "Renal calibrated interaction -0.0007 (z=-0.1 vs negative-control null) -> WITHIN the empirical null -- NOT renal-specific after calibration (confirms R2). Mortality calibrated -0.0052, E-value(mort CKD RR)=4.101. Positivity OK (near-0/1 PS frac 0.001/0.0099)."
}
```
**Verdict:** Renal calibrated interaction -0.0007 (z=-0.1 vs negative-control null) -> WITHIN the empirical null -- NOT renal-specific after calibration (confirms R2). Mortality calibrated -0.0052, E-value(mort CKD RR)=4.101. Positivity OK (near-0/1 PS frac 0.001/0.0099).


---

## REVISED OVERALL VERDICT after R5 (negative-control calibration) — the decisive result

**The CKD *personalized*-MAP-target claim does NOT survive hostile review.**

R5 calibrated the CKD×hypotension renal interaction against an empirical confounding null
built from negative-control organ outcomes (hepatocellular/cholestatic/coagulation; null =
0.046 ± 0.007). The renal interaction (0.046) calibrates to **−0.0007 (z=−0.1)** — *exactly*
the confounding null. The mortality interaction likewise calibrates to ~null. Positivity/
overlap is adequate (PS 0.008–1.0; <0.1% / ~1% near 0/1).

**What this means for each claim:**
- ❌ **"CKD patients are specially vulnerable to hypotension / need a personalized higher
  MAP target"** — NOT DEFENSIBLE. The effect-modification is indistinguishable from
  generic confounding after negative-control calibration. The earlier within-CKD RR 2.14
  / RD 0.061, the eGFR gradient, and the "floor ~75" all reduce to: CKD patients have
  higher BASELINE risk and get more hypotension, not a CKD-specific causal sensitivity.
- ✅ **"Intraoperative hypotension is associated with postoperative AKI and in-hospital
  mortality"** — DEFENSIBLE but NOT NOVEL (mortality CKD-stratum RR 2.34, E-value 4.10;
  monotone dose-response; replicated VitalDB→INSPIRE). Well-established in the literature.
- ⚠️ **A-line vasoplegia index** (R4) — real in direction but FRAGILE; carried by the
  diastolic/MAP ratio (r≈+0.24); the r=−0.34 composite headline does not hold at n=159.

**Defensibility ceiling (honest):** an observational dataset cannot make the *personalized*
claim defensible — the negative-control calibration shows the modification is confounding.
A defensible novel claim would require a design that breaks confounding-by-indication
(a randomized MAP-target trial in CKD, or a credible natural experiment/instrument), which
this data does not provide. The maximally-defensible outputs here are: (1) the calibrated
null for the personalization claim (a useful *negative*), (2) the robust generic hypotension
→ AKI/mortality association, (3) the vasoplegia-tone construct-validity signal pending more N.
