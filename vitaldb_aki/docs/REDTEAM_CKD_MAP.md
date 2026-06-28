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


---

## OVERALL RED-TEAM VERDICT (4 rounds)

**Both positive findings are DOWNGRADED by adversarial testing — neither is as clean as
first presented, but each retains a real, defensible core.**

### CKD personalized-MAP-target — REFRAME, do not retract
- **R1 (scale):** SURVIVES. The CKD excess is real on the additive (risk-difference)
  scale (CKD hypotension→AKI RD 0.061 vs non-CKD 0.015), not RR non-collapsibility.
- **R2 (specificity):** FAILS. The CKD×hypotension additive excess is NOT renal-specific
  — equally large for cholestatic/coagulation injury (max non-renal control 0.054 ≥
  renal 0.046). Classic generic-severity / confounding-by-indication signature.
- **R3 (confounding-resistance):** PARTIAL. A confounding-resistant core remains: the
  hypotension dose-response is monotone and 2.3× steeper in CKD (gradient 0.16 vs 0.07;
  21% AKI at MAP<55 in CKD), and the excess holds on MORTALITY (ascertainment-robust,
  additive interaction 0.041).
- **Honest position:** NOT "CKD needs a higher MAP to protect the KIDNEYS specifically."
  The defensible claim is **"CKD patients are more vulnerable to DEEP intraoperative
  hypotension, across organ systems and on mortality, with a steeper dose-response"** —
  still actionable (a higher MAP floor in CKD), but the renal-specific mechanism is not
  supported and residual confounding (sicker CKD-hypotension patients) cannot be
  excluded observationally.

### A-line vasoplegia index — REAL DIRECTION, FRAGILE PACKAGING
- **R4:** the waveform-index vs measured-SVRI correlation is FRAGILE as a composite — at
  n=159 a naive z-mean index gives r=−0.15 (bootstrap CI crosses 0), vs the r=−0.34
  headline at n=108. The signal is carried by the **diastolic/MAP ratio (r=+0.24)** and
  τ (+0.16), while the augmentation-index component is wrong-signed. Construct validity
  is real in DIRECTION but MODEST and simpler than the composite implied; the diastolic/
  MAP ratio is the robust single tone-correlate. Needs the full 248-case SVR cohort + a
  pre-specified, validated index before any claim.

### Bottom line
The red-team did its job: it converted two tempting headlines into honestly-qualified
findings. The CKD-hypotension-vulnerability association is robust but non-specific
(reframe, don't retract); the vasoplegia construct validity is real but weak and
carried by one simple feature. Both are hypothesis-generating, observational,
single-/dual-centre, and need the stated next steps before publication-grade claims.
