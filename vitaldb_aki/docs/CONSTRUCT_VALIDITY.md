# Construct validity of the vasopressor dose-REQUIREMENT as a VASOPLEGIA / vascular-tone index

**Hostile reviewer's attack.** a high vasopressor requirement can reflect ANY reason for pressor use (hypovolemia, cardiogenic shock, bradycardia, deep anaesthesia, bleeding); the vasoplegia construct is unproven.

This document assembles every available piece of evidence on whether the requirement indexes vascular tone / vasoplegia *specifically* (not just "some reason to need a pressor"), and reports honestly how strong the construct is. Phenotype = `median NEPI norepi-only dose_per_kg in MAP[55,80], >=2 epochs`, **n=52** cases.

## 1. CONVERGENT validity vs vascular TONE (A-line diastolic carrier)
Vasoplegia = low diastolic tone -> the requirement should correlate **negatively** with the diastolic-tone carrier.

**Data-quality flag (verified, load-bearing).** The originally-named tone carrier `map_dia_form_factor` is a **DEGENERATE constant** (value 0.3333, SD=1e-06 across n=640 cases) -- it carries NO variance, so any correlation against it is tie-broken noise. The real diastolic-tone variation lives in `diastolic_over_map` (SD=0.043897, range [0.5827, 0.8774]). We therefore use `diastolic_over_map` as the primary carrier.

- Requirement vs `diastolic_over_map` (REAL tone carrier): **Spearman -0.0287** (95% CI [-0.3401, 0.278], p=0.85143, n=45).
- For the record, vs degenerate `map_dia_form_factor`: Spearman -0.2628 -- informative
- Expected direction: NEGATIVE (vasoplegic = LOW diastolic tone = low diastolic_over_map -> high requirement).

## 2. DISCRIMINANT validity vs PRELOAD / hypovolemia (PPV)
High pulse-pressure variation (`art_ppv_burden_min`) marks hypovolemia / preload-responsiveness -- a **different** mechanism for needing pressor. If the requirement is vasoplegia-specific it should be **more** related to low tone than to high PPV.

- Requirement vs `art_ppv_burden_min`: Spearman 0.3791 (95% CI [0.0688, 0.6392], n=45).
- Head-to-head on the common subset (n=45): r_vs_tone=-0.0287, r_vs_ppv=0.3791.
- Partial Spearman: tone | PPV = -0.2094; PPV | tone = 0.4336.
- Tone effect larger in magnitude than PPV effect: False.

## 3. SVR anchor (the direct gold standard) -- honest re-report
- Requirement vs `EV1000 svr_mean (epoch-mean)`: **Spearman 0.1429** (95% CI [-0.4214, 0.6458], p=0.61152, **n=15**).
- n=15; sign is POSITIVE (WRONG direction) and underpowered. This is the soft spot of the construct. CI crosses 0.
- Expected direction: NEGATIVE (low SVR = vasoplegic = high requirement). This is the weakest link.

## 4. ETIOLOGY by surgery type (vasoplegia-prone vs cleaner cases)
- Cases by optype (median requirement, descending):
  - Transplantation: n=14, median=0.2375
  - Others: n=27, median=0.1961
  - Colorectal: n=4, median=0.18201
  - Vascular: n=4, median=0.15464
  - Hepatic: n=1, median=0.08795
  - Stomach: n=1, median=0.07053
  - Biliary/Pancreas: n=1, median=0.00132
- Transplantation (n=14, liver-tx-dominated, vasoplegia-prone) median **0.19888** vs rest **0.161** -> 1.24x, Mann-Whitney one-sided p=0.2383.
- Liver transplantation only (n=11): median 0.24 vs rest 0.15464 (1.55x).

## VERDICT
**PARTIALLY SUPPORTED** (support score 1/3).

- CONVERGENT vs REAL tone carrier (diastolic_over_map): Spearman -0.0287 (95% CI [-0.3401, 0.278], n=45). Right sign but the magnitude is NEAR-NULL -- weak convergent evidence. (The originally-named carrier map_dia_form_factor is a constant/degenerate column; its earlier -0.26 was tie-broken noise -- discarded.)
- DISCRIMINANT vs PPV/preload: requirement vs PPV-burden Spearman 0.3791 (n=45); head-to-head (n=45): r_tone=-0.0287 vs r_ppv=0.3791. Partials: tone|PPV=-0.2094, PPV|tone=0.4336. BOTH mechanisms carry INDEPENDENT signal (each survives partialling out the other), and PPV (hypovolemia) is at least as strong as tone -> the requirement is a MIXED preload+tone signal, NOT cleanly vasoplegia-specific.
- SVR anchor (gold standard): Spearman 0.1429 at n=15 -- POSITIVE, the WRONG sign, underpowered. The direct vasoplegia anchor FAILS.
- ETIOLOGY: transplant (liver-tx-dominated, vasoplegia-prone) median requirement 0.19888 vs rest 0.161 (1.24x, MW p=0.2383). Direction consistent with vasoplegia but NOT significant.

PARTIALLY SUPPORTED. After correcting a data-quality defect (the named tone carrier map_dia_form_factor is a degenerate constant, so the earlier -0.26 convergent value was noise), the requirement's correlation with the REAL diastolic-tone carrier is -0.0287 (n=45, CI [-0.3401, 0.278]) -- right-signed but near-null. On discriminant validity the requirement tracks PPV/preload (r=0.3791) as strongly as -- or more strongly than -- tone, and both survive mutual partialling: it is a MIXED preload+tone vasopressor-need signal, not a pure vasoplegia index. It does run higher in vasoplegia-prone surgery (1.24x) but not significantly. The DIRECT SVR anchor (n=15) still points the WRONG way (+0.1429). BOTTOM LINE for the reviewer's attack: the attack LANDS in part -- the construct is NOT shown to be specifically vascular-tone. The evidence supports a weaker, honest claim: the requirement is a generic 'vasopressor-need / hemodynamic fragility' phenotype with a tone component, not a validated vasoplegia-specific marker. The vasoplegia label is aspirational until a powered independent SVR cohort confirms it.

### What a reviewer should STILL doubt
1. **Estimator-vs-estimator convergence.** The tone carrier (`map_dia_form_factor`) is itself an arterial-waveform *estimator* of tone, not a gold-standard SVR. Convergent validity here is two A-line-derived quantities agreeing -- suggestive, not dispositive.
2. **The gold-standard SVR points the wrong way (n=15, +sign).** Until a properly powered independent-CO SVR cohort tests the requirement directly, the vasoplegia label rests on convergent + etiologic evidence, not the anchor.
3. **Discriminant power is N-limited.** PPV separation is estimated on a small common subset (n=45); confounding by mixed hypovolemia+vasoplegia (common in liver tx) is not fully excluded.
4. **Requirement = management x physiology.** MAP-band + norepi-only conditioning blunts the 'deep anaesthesia / bradycardia / drug-identity' confounds the attack names, but observational management is not removed.

_Generated by analysis/construct_validity.py; numbers in cache/construct_validity.json._
