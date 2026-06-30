# Adversarial Peer Review: Finding 3 — Fluid-vs-Pressor Resuscitation Balance and Mortality

**Reviewer role:** Reviewer 2, top critical-care/anesthesiology journal  
**Target:** FINDING 3 — "pressor-predominant resuscitation balance grades mortality"  
**Documents reviewed:** PUBLICATION_DOSSIER.md, RESUSCITATION_BALANCE_CROSSVAL.md,
MIMIC_DISCOVERED_FINDINGS.md, analysis/resuscitation_balance_crossval.py, cache/resuscitation_balance_crossval.json  
**Date:** 2026-06-30  

---

## Summary judgment

**NOT publishable as an independent finding in its current form.** Finding 3 does not meet the standard of a separable, externally validated, confounding-addressed claim. The MIMIC signal is statistically robust but methodologically entangled with Finding 4 (total NEE load), the balance metric's unit incoherence is unresolved, the severity-adjustment is critically thin, the lone external data point (VitalDB OR 1.18, CI 0.996–1.394) is formally null, and the INSPIRE arm is entirely absent due to missing data. The finding belongs in the paper as a *descriptive observation subordinate to Finding 1/4*, with its limitations stated candidly, not as an independent substantive claim.

---

## CRITICAL issues

### CRITICAL-1: The balance metric is mathematically a disguised pressor-dose metric and is not separable from Finding 4

The balance metric is defined as:

    balance = log( (NEE_load + ε) / (fluid_mL/kg + ε) )

In the co-exposed cohort (n=28,124), the numerator is the *same* quantity as Finding 4 (total NEE load). The denominator (fluid volume) is in mL/kg — a biologically orthogonal unit. A high balance value therefore arises either because NEE load is large *or* because fluid is small. The authors cannot distinguish these two contributions from this single composite metric.

More concretely: within the co-exposed cohort, high NEE load alone (Finding 4) produces high balance. Finding 4 already shows Q1 mortality 0.060 to Q4 mortality 0.474 in the same MIMIC population. The authors do not partial out the NEE contribution from the balance metric in any reported model. No model adjusting *for* NEE load while regressing on balance is presented. The claim that balance captures something *beyond* pressor dose (i.e., the low-fluid component) is entirely undemonstrated.

The minimum required analysis is a model with both log(NEE_load) and log(fluid_mLkg) entered as separate predictors, with their independent associations with mortality reported. Without this decomposition, Finding 3 and Finding 4 may be the same signal with a different label.

### CRITICAL-2: The "severity adjustment" is age only (age + single lactate value) — catastrophically inadequate for a resuscitation-strategy claim

The headline result (co-exposed OR 3.505/SD; lactate-adjusted co-exposed OR 3.398/SD) is adjusted for age and, in the lactate subset (n=8,623 of 28,124, a 30% subset), a single first-24h lactate value. No SOFA, no Charlson comorbidity, no sepsis diagnosis, no vasopressor class, no source of shock, no fluid balance trajectory. The severity confounders already deployed in Finding 1 (Charlson, Elixhauser, #vasopressors, SOFA lab components, lactate) are *absent* here.

This matters acutely for Finding 3 because the confounding-by-indication problem is *fundamentally different in character* from Finding 1. In Finding 1, the confound is "sicker patients get more pressor" — addressed by conditioning on pressor count, lactate, and comorbidity. In Finding 3, the confound is **refractory vasodilatory shock**: the sickest patients (septic, vasoplegic, cardiovascular collapse) are specifically managed with pressor-predominant strategies *because* they are not fluid-responsive and fluid administration is hazardous. The balance metric is highest in exactly the patients that restrictive fluid management guidelines (SMART, BASICS, CLOVERS trials) target — patients who by severity criteria warrant fluid restriction. Lactate adjustment is insufficient to separate "strategy choice given severity" from "strategy effect." The lactate-adjusted OR (3.398 in the co-exposed, lactate subset) is almost identical to the unadjusted co-exposed OR (3.505), suggesting lactate is doing essentially nothing — either because the relationship is truly severity-independent (implausible) or because single-value first-24h lactate does not capture the confounding severity adequately.

The E-value argument deployed in Finding 1 (E-value ~6) is explicitly *not* reported for Finding 3. This gap is conspicuous and should be filled.

### CRITICAL-3: The co-exposed selection introduces non-random censoring and likely produces collider stratification bias

The move from the full MIMIC cohort (n=76,374) to the co-exposed sub-cohort (n=28,124) to obtain "the clean within-resuscitated gradient" is presented as a methodologic improvement. It is not straightforward.

Conditioning on *both* having received a pressor *and* having received fluid (both non-zero) simultaneously conditions on two endogenous variables that are jointly caused by shock severity and clinical protocol. This is collider stratification: among patients who received both a pressor and IV fluid, the patients who nonetheless died are the subset where fluid was insufficient and pressor requirements escalated — i.e., the highest-severity patients. The co-exposed conditioning amplifies the severity gradient rather than removing it. The OR doubling from the full cohort (2.144) to the co-exposed cohort (3.505) is consistent with this interpretation: the co-exposed sample over-enriches at the extremes.

The authors acknowledge this implicitly ("lowest tertile is 1.0 NO-pressor stays") but the proposed fix (restrict to co-exposed) creates its own selection bias in the opposite direction. Neither the full nor the co-exposed analysis is clean; only a proper conditioning-free approach (e.g., marginal structural model over the full resuscitation trajectory) would address this.

### CRITICAL-4: VitalDB "validation" is formally null and the dossier's characterization of it as "concordant" is not defensible

The VitalDB cross-validation result: OR 1.183 [0.996, 1.394]. The lower confidence bound is 0.996 — the CI includes 1.00. By any conventional standard (two-sided p ≈ 0.056 by the CI), this result is not statistically significant. Calling a CI that includes the null as "concordant (but borderline)" and presenting it as supporting evidence for Finding 3 in the dossier violates basic reporting standards. The Cochran-Armitage trend across tertiles (p=0.005) is the only significant statistic, and it applies to a 3-point trend in a small-event dataset (143 AKI events across 3,924 patients — effective n for the trend is modest).

Moreover, the VitalDB "validation" tests a *different outcome* (post-operative AKI, a non-fatal renal endpoint) in a *different population* (elective intraoperative surgical patients) using a *non-equivalent pressor metric* (phe + eph + epi in raw milligrams, explicitly described as "drug-specific units" that cannot be compared across drugs) and a *different fluid definition* (intraoperative crystalloid + colloid only, no post-operative fluid). This is not cross-validation of the MIMIC finding. At best it is a directionally similar exploratory association in a population where the causal mechanisms, patient acuity, clinical context, and measurement instruments are all materially different.

The honest statement is: "The VitalDB analysis is underpowered (CI includes null), uses an incomparable pressor unit, and tests a different endpoint. It does not validate the MIMIC finding."

---

## MODERATE issues

### MODERATE-1: INSPIRE gap is presented as "partially addressing" the claim — it does not

INSPIRE lacks intraoperative fluid volume columns (only estimated blood loss, `ebl`). The authors state this explicitly and correctly. However, the dossier frames this as a "partial cross-validation" by citing the INSPIRE NEE finding (Finding 4's cross-validation). This framing is misleading: INSPIRE replicates Finding 4 (total pressor load), not Finding 3 (the fluid-vs-pressor ratio). Finding 3 has no external validation other than the null VitalDB result. Describing a single-cohort finding (MIMIC only) with a null validation in a second cohort as "partial cross-validation" overstates the evidential weight. A more accurate characterization is "single-cohort finding, external test not feasible due to missing fluid data."

### MODERATE-2: The fluid denominator conflates resuscitation fluids with maintenance and excludes blood products — creating a systematic measurement error biased toward the null

The MIMIC fluid total counts only the filtered crystalloid/colloid itemids from `inputevents`. Explicitly excluded are:
- Maintenance fluids and flushes
- Oral and enteral intake
- Blood products (packed red cells, FFP, platelets, cryoprecipitate)

In the sickest patients who receive pressor-predominant management (septic shock, hemorrhagic shock), blood products represent a large fraction of total volume resuscitation and are specifically given *instead of* crystalloid. Excluding them systematically understates the "fluid" component in the pressor-predominant group, artificially inflating the computed balance toward pressor-predominance in exactly the patients who are most severely ill. The direction of this bias is toward *overstating* the balance-mortality association. This is not a minor caveat: in septic or hemorrhagic shock management, blood products can exceed crystalloid volumes and are a critical part of the resuscitation strategy the authors claim to be measuring.

### MODERATE-3: Time windowing of the balance metric is undefined and cannot be clinically interpreted

The balance metric accumulates pressor NEE-load and fluid volumes over the *entire ICU stay* (segments gated to 0 < duration <= 24h per segment, but no stated overall time window). ICU stays in MIMIC range from hours to weeks. A patient who survived for 14 days on ICU will have a very different total fluid exposure than a patient who died on day 2. The cumulative balance metric is therefore confounded by *length of stay* and *survival time*, both of which are strongly associated with the outcome (death). A patient who dies early has less time to accumulate fluid, making the balance appear more pressor-predominant. This is an immortal-time / survivorship structure embedded in the metric definition itself.

For the metric to be interpretable, it should be limited to a fixed time window (e.g., first 24 or 48 hours), which is standard in the critical-care literature (e.g., VASST trial, SOAP II, CHEST trial). No such restriction is applied or discussed.

### MODERATE-4: The vasopressin NEE equivalence (2.5 mcg/kg/min per unit/min) is a stated approximation with large uncertainty — sensitivity analysis absent

The authors state: "vasopressin: VASO_NEE_PER_UNIT_MIN = 2.5 (stated assumption: 0.04 units/min vasopressin ~ 0.1 mcg/kg/min NEE)." Vasopressin is used at fixed dose (0.03–0.04 U/min) without up-titration, as an adjunct, not as a primary vasopressor, and its vasoconstrictor potency is not reliably comparable to catecholamines via a simple linear equivalency. Published NEE weights for vasopressin vary widely (0–5 depending on the model), and several groups exclude it from NEE calculations for this reason. Using an arbitrary equivalency of 2.5 without a sensitivity analysis (e.g., weight = 0, 1, 2.5, 5) leaves the finding vulnerable. In MIMIC, vasopressin is commonly co-administered with norepinephrine, so the vasopressin NEE contribution is not negligible. No sensitivity analysis of the vasopressin weight is presented.

### MODERATE-5: Bootstrap CI computation is likely anti-conservative due to in-sample bootstrap without held-out calibration

The CI computation (`_adj_logit`, n_boot=400) uses percentile bootstrap on the same data used to fit the logistic regression, without any correction for optimism or cross-validation. For the co-exposed lactate subset (n=8,623), this is likely adequate. For the full cohort (n=76,374) the precision is high regardless. However, for the VitalDB analysis (n=3,924, 143 events), a 400-iteration bootstrap with 2.5/97.5 percentiles is unstable and the resulting CI [0.996, 1.394] may be narrower than a proper asymptotic or BCa interval. Regardless, the CI including 1.0 is the headline issue, not the precision of the CI itself.

---

## MINOR issues

### MINOR-1: Dobutamine exclusion is correctly stated but angiotensin-II (Giapreza, itemid 229764) exclusion is acknowledged without reporting its prevalence in the cohort

If angiotensin II was used in a subset of the sickest patients (those failing catecholamine requirements) and is excluded from NEE, the balance metric for that subset will systematically understate pressor exposure. The authors acknowledge "no established single NEE weight" but do not report how many stays include angiotensin II or what their mortality rate was. This could create a selection hole at the extreme pressor end of the distribution.

### MINOR-2: The choice of epsilon (1e-3) in the log-balance formula is arbitrary and potentially influential

`balance = log((NEE_load + 1e-3) / (fluid_mLkg + 1e-3))`. For patients with very low NEE load or very low fluid volume, the epsilon term dominates and the balance reduces to approximately log(1) = 0, collapsing the signal. No sensitivity analysis to epsilon is presented. A value of 1e-3 for NEE-load in mcg/kg/min-minutes is extremely small relative to typical ICU pressor exposures but could be influential near the boundaries of the distribution.

### MINOR-3: Multiple comparison correction is not discussed for Finding 3

MIMIC was used for discovery of Finding 3 in the same database used for Findings 1, 2, and 4. The authors argue multiplicity immunity for the primary finding (Finding 1) via Fisher-z. No such argument is made for Finding 3. If Finding 3 emerged from a broader search of MIMIC features, it is subject to winner's curse and requires pre-registration or correction.

### MINOR-4: Dossier language inconsistency between the PUBLICATION_DOSSIER.md and the RESUSCITATION_BALANCE_CROSSVAL.md

PUBLICATION_DOSSIER reports the lactate-adjusted co-exposed OR as 3.4 ("survives lactate 3.4"). RESUSCITATION_BALANCE_CROSSVAL reports 3.398. The MIMIC lactate-adjusted *full cohort* OR is 1.939 — substantially lower — and this number is not prominently featured in the dossier's FINDING 3 summary. This selective emphasis (reporting the 3.4 from the co-exposed lactate subset, not the 1.9 from the full-cohort lactate adjustment) presents a best-case rather than a representative picture.

---

## Direct answers to the specific scrutiny questions

**Is "balance" a disguised dose metric?**  
Substantially yes. The balance numerator is identical to Finding 4's exposure (NEE load). The metric can rise by either increasing pressor load or decreasing fluid, but no model partials out these two contributions. The authors have not demonstrated that the fluid-restriction signal (low denominator) provides independent information beyond the pressor-load signal (high numerator/Finding 4). Until a two-predictor model (log NEE + log fluid independently) is presented, Finding 3 cannot be distinguished from a repackaged Finding 4.

**Is the co-exposed OR 3.5 (surviving lactate OR 3.4) trustworthy?**  
The internal consistency is high (large n, monotone gradient, minimal attenuation under lactate adjustment). However, the near-identical ORs before and after lactate adjustment (3.505 → 3.398) suggest either the association is truly independent of lactate or that lactate is a poor severity proxy for this confound. The latter is more plausible given that refractory vasoplegia — the specific condition for which pressor-predominant management is indicated — is poorly captured by a single lactate value. The OR is likely correct as a statistical association but severely confounded by indication for which the adjustment is inadequate.

**Is the VitalDB CI-includes-null result defensible as "concordant support"?**  
No. A CI that includes 1.00 is a null result by conventional standards. Presenting it as "concordant (but borderline)" and including it as supporting evidence in the dossier is not defensible. The authors should report it as a non-significant trend and acknowledge that the VitalDB cross-validation failed to confirm the MIMIC finding at conventional significance thresholds.

**Does "partial cross-validation" overstate external support given INSPIRE's missing fluid columns?**  
Yes. "Partial cross-validation" implies that some portion of the external replication succeeded; in fact the only available external test (VitalDB) returned a null result. INSPIRE did not test this finding at all (it tested Finding 4 instead). A more accurate characterization is "single-cohort finding; external replication was not feasible (INSPIRE) or non-significant (VitalDB)."

**Is Finding 3 distinguishable from Finding 4?**  
Not with the current analysis. They share a numerator (NEE load), are tested in the same co-exposed MIMIC cohort, and have similar ORs (3.505 vs 3.181). The claimed distinctiveness of Finding 3 rests on the balance ratio incorporating fluid volume, but this is undemonstrated to be independently informative. The joint model required to demonstrate non-redundancy is absent.

---

## Recommendations for revision to be acceptable for re-review

1. **Required: Decompose balance into two independent predictors.** Report a logistic model with log(NEE_load) and log(fluid_mLkg) as separate terms in the co-exposed cohort. If both are independently significant, Finding 3 has distinct content from Finding 4. If only log(NEE_load) is significant, Finding 3 reduces to Finding 4 and should be withdrawn as a separate finding.

2. **Required: Full severity adjustment mirroring Finding 1.** Repeat the balance→mortality analysis with Charlson/Elixhauser comorbidity, SOFA lab components, #vasopressors, and source of shock (sepsis vs other) as adjustors. The age-only adjustment is not credible for a resuscitation-strategy claim.

3. **Required: Report VitalDB honestly as a non-significant result.** The CI [0.996, 1.394] includes the null and should be described accordingly.

4. **Required: Apply a fixed time window (first 24–48h).** Recompute balance over a predefined early resuscitation window to remove the survivorship bias embedded in the cumulative metric.

5. **Required: Sensitivity analysis for vasopressin NEE weight.** Report ORs with vasopressin weights 0, 1, 2.5, and 5.

6. **Required: Include blood products in total fluid volume or analyze separately.** Report the sensitivity of the finding to adding blood product volumes to the fluid denominator.

7. **Recommended: E-value for the balance metric under the full severity-adjusted model** (once available).

8. **Recommended: Reposition Finding 3 as an exploratory observation.** Until items 1–4 are addressed, Finding 3 does not meet the bar for a primary claim and should be presented as a hypothesis-generating analysis subordinate to Findings 1 and 4.

---

## Verdict

| Category | Issue |
|---|---|
| CRITICAL | Balance metric not separable from Finding 4 (no decomposition model) |
| CRITICAL | Severity adjustment (age + lactate only) is inadequate for resuscitation-strategy confounding |
| CRITICAL | Co-exposed selection creates collider bias that amplifies severity gradient |
| CRITICAL | VitalDB CI includes null; "concordant" framing is not defensible |
| MODERATE | INSPIRE absence is single-cohort limitation, not "partial cross-validation" |
| MODERATE | Fluid denominator excludes blood products — directional bias toward overstating association |
| MODERATE | No fixed time window — cumulative metric conflates survival duration with resuscitation strategy |
| MODERATE | Vasopressin NEE weight unstated with no sensitivity analysis |
| MINOR | Angiotensin-II prevalence unreported |
| MINOR | Epsilon sensitivity absent |
| MINOR | Multiplicity not addressed |
| MINOR | Dossier reports best-case OR (co-exposed + lactate 3.4) not full-cohort + lactate (1.9) |

**PUBLISHABILITY: REJECT (major revision required).** Finding 3 in its current form cannot be published as an independent claim. The metric may be measuring the same signal as Finding 4, the severity adjustment is insufficient, the only external test is null, and the "partial cross-validation" framing misrepresents the evidence. The finding is not fabricated — the MIMIC statistical association is real and large — but it is neither externally validated, causally interpretable, nor demonstrated to be distinct from the co-submitted Finding 4. The corrective path (decomposition model, full severity adjustment, honest VitalDB characterization, fixed time window) is achievable but requires substantial new analyses. Until those are completed, Finding 3 should be repositioned as a subordinate exploratory observation, not a co-primary claim.
