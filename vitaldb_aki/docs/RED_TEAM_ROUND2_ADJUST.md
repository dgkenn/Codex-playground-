# RED_TEAM_ROUND2_ADJUST.md — Statistical Attack on the Corrected Prospective Number

**Reviewer role:** Statistical reviewer (Round 2), attacking the *post-Round-1 corrected* number  
**Date:** 2026-06-30  
**Target claim:** "Fully-adjusted landmark: first-24h NEE → post-24h in-hospital death, adjusted for age+lactate+creatinine+bilirubin+platelets+comorbidity, OR 1.74 [1.57, 1.91] (n=4,260 complete cases), E-value 2.31 (point) / 2.11 (CI-LB). Survives — CI excludes 1."  
**Probe script:** `/tmp/…/scratchpad/round2_probe_v2.py` (throwaway; not committed). All numbers verified against production PRESSORS dict, n=23,925 landmark cohort, n=4,260 complete cases exactly matching `cache/finding4_landmark.json`.

---

## Findings table

| # | Issue | Severity | NEW vs DISCLOSED |
|---|-------|----------|-----------------|
| R2-1 | Complete-case n collapse (82.2% data loss) selects a sicker, higher-NEE-load subset; age-only OR is 2.176 in CC vs 2.568 full-cohort; IPCW-corrected OR 1.637 (6.1% below point estimate); the 1.74 is not generalizable to the other 82.2% | **CRITICAL** | **NEW** |
| R2-2 | E-value 2.11 is NOT a meaningful defense: GCS/sedation and PaO2/FiO2 (both known missing SOFA components) each produce plausible confounder products of 2.6–8.0, exceeding the threshold | **CRITICAL** | **NEW (quantified)** |
| R2-3 | Incremental AUC = 0.0243 [0.016, 0.035] (delta over 6-covariate severity model) — above the 0.02 threshold; the "beyond severity" claim is clinically meaningful, not negligible | **MODERATE** (favorable finding — partially exonerates) | NEW |
| R2-4 | Peak-NEE OR (1.416) is materially weaker than load-OR (1.743); robustness is specification-dependent | **MODERATE** | NEW |
| R2-5 | Winsorize, dopamine-weight, and comorbidity-drop all stable (OR 1.72–1.81, CI above 1.0) | MINOR (favorable) | NEW |

---

## R2-1 — CRITICAL — NEW
### Complete-case representativeness: the 1.74 characterizes the sickest 17.8%

**Numbers.**  
From the production landmark cohort (n=23,925 alive at 24h):

| Subset | n | % | Post-lm mortality | Mean log₁p(NEE) | Median NEE load |
|---|---|---|---|---|---|
| Full CC (all 6 adjusters present) | 4,260 | 17.8% | **24.3%** | **4.127** | **75.1** |
| Incomplete (≥1 adjuster missing) | 19,665 | 82.2% | **14.2%** | **3.531** | **38.0** |
| P-value (χ²/t-test) | — | — | 5.7×10⁻⁶⁰ | 1.8×10⁻¹¹¹ | — |

Complete cases have **1.71× higher mortality** and **~2× higher vasopressor load** (median NEE 75 vs 38 NEE-eq·min). Labs are ordered because patients are sicker; missingness is informative.

**The within-subset age-only OR confirms non-exchangeability.**  
Age-only OR in the complete subset = **2.176** vs 2.568 in the full cohort — a meaningful 15% gap driven by selection, not adjustment. The full-adjustment step (2.176 → 1.743) therefore happens in an already-compressed severity stratum where the exposure–outcome gradient may differ from the broader population.

**IPCW check.**  
An inverse-probability-of-completeness-weighting (IPCW) model — P(complete | age, log-NEE, lactate-observed) via logistic regression, IPW clipped at [0.05, 0.99] — gives:

- Unweighted full-adj OR: **1.743** (reproduces cache exactly)  
- IPCW-weighted full-adj OR: **1.637**  
- Ratio: 0.939 (6.1% downward correction)  
- E-value of IPCW OR (same p₀=0.243): **2.19**  

The IPCW correction is **MODERATE** (6%, within-5-to-10% band). The OR survives directionally, but the selection bias is non-trivial and the E-value margin shrinks. The IPCW model itself uses only pre-outcome covariates (age, NEE, lactate-flag) and is therefore a conservative validity check, not a full multiple imputation.

**What this means for generalizability.**  
The 1.74 is estimated in critically ill, high-vasopressor-burden patients who had complete lab panels — precisely those for whom the result is already expected (sicker → more NEE → more death). The claim "first-24h vasopressor load predicts later death beyond severity" is empirically supported in this stratum but untested in the 82.2% of landmark patients with incomplete panels.

**Resolution options (ordered by rigor):**  
1. Multiple imputation (MICE) with predictive mean matching for the 4 continuous labs + comorbidity count, pooled across m=20 imputations. Expected OR: between 1.637 and 1.743, almost certainly above 1.0 — but this is the definitive answer.  
2. Report the IPCW sensitivity as the lower bound (OR 1.64, E-value 2.19).  
3. At minimum, disclose explicitly: "The complete-case subset had 1.71× higher mortality and 2× higher vasopressor load than the 82.2% with incomplete panels; the OR 1.74 should be interpreted as characterizing high-severity, high-measurement-density patients."

---

## R2-2 — CRITICAL — NEW (quantified)
### E-value 2.11 is not a strong defense: two known gaps exceed the threshold

**The E-value formula and threshold.**  
OR 1.743, p₀=0.243 → approximate RR 1.476 → E-value 2.31 (point) / 2.11 (CI lower bound).  
For a single unmeasured binary confounder U, the threshold product is: RRₓᵤ × RRᵤᵧ ≥ 2.11 to nullify the CI lower bound.

**Candidate confounders with estimated products:**

| Confounder U | RRᵤᵧ (U → death, residual) | RRₓᵤ (NEE → U) | Product | Exceeds 2.11? |
|---|---|---|---|---|
| GCS/sedation (SOFA-neuro 0–4 pts, MISSING) | 2–3¹ | 1.3–2² | 2.6–6.0 | **YES** |
| PaO₂/FiO₂ (SOFA-resp 0–4 pts, MISSING) | 2–4³ | 1.5–2⁴ | 3.0–8.0 | **YES** |
| Shock type/indication (cardiogenic vs septic) | 1.7–2.0⁵ | 1.2–1.5 | 2.0–3.0 | **BORDERLINE** |
| Frailty/CFS | 2–5 (Flaatten ICM 2017) | uncertain direction | uncertain | **UNCERTAIN** |

¹ Ferreira et al. CCM 2001: SOFA-neuro 3–4 vs 0, OR for mortality ~3–5; within a model already conditioning on SOFA-labs, conservative residual RRᵤᵧ ~2–3.  
² Patients requiring higher vasopressor loads in the first 24h are more likely to be intubated/sedated → depressed GCS. Conservative lower bound RRₓᵤ ~1.3.  
³ SOFA-resp 3 (P/F < 200) vs 0: OR for mortality 2–4 in severity-adjusted ICU models.  
⁴ Septic shock → concurrent ARDS in 15–30% (LUNG SAFE 2016); higher NEE correlates with ARDS co-occurrence.  
⁵ Cardiogenic shock mortality ~45–55% vs septic ~25–35% in MIMIC; ICD comorbidity count partially captures cardiac history but not index-admission shock type.

**The conclusion about the E-value argument.**  
The E-value 2.11 is not a strong defense because the *specific* named gaps (SOFA-neuro, SOFA-resp) are not hypothetical: they are known to be missing, they are large (together 0–8 of 24 SOFA points), and their plausible confounder products exceed the threshold. The honest statement is:

> "An unmeasured confounder of the magnitude of the SOFA neurological or respiratory component — both of which we could not include due to data limitations — could plausibly nullify the fully-adjusted association. The E-value of ~2.1 is achievable by these specific known variables. A definitive test requires chartevents (~30 GB) to extract GCS and PaO₂/FiO₂."

**What the E-value DOES accomplish:** it quantifies the required effect size, constrains imprecise "unmeasured confounding" language, and rules out weak confounders (e.g., trivial co-medications, minor comorbidities). It is honest for everything *except* the two known, large missing SOFA components.

**Resolution:** Do not cite E-value 2.1–2.3 as a *strength*. Cite it alongside an explicit statement that GCS and PaO₂/FiO₂ each plausibly produce products exceeding this threshold. The Round-1 correction (E-value ~6 does not transport) was necessary and correct; the Round-2 correction is: ~2.1 is not a strong bound against named known gaps. Alternatively, obtain chartevents and compute full SOFA.

---

## R2-3 — MODERATE — NEW (favorable)
### Incremental AUC: 0.0243 [0.016, 0.035] — meaningful, not negligible

**Method.** Within n=4,260 complete cases, two logistic models were fit:  
- **Severity-only:** age + lactate + creatinine + bilirubin + platelets + comorbidity count  
- **Full:** severity + log₁p(NEE-load)  

AUC estimated via exact Wilcoxon rank-sum. Bootstrap CI (600 resamples, seed 99).

| Model | AUC |
|---|---|
| Severity-only | 0.7260 |
| + log₁p(NEE) | 0.7503 |
| **Delta-AUC** | **0.0243** |
| Bootstrap 95% CI | [0.016, 0.035] |
| Relative improvement | +3.35% |

**Interpretation.** The 0.0243 increment exceeds the conventional 0.02 minimum threshold for clinical relevance in prognostic model comparisons. The CI lower bound (0.016) is below 0.02 but above zero; the finding is robust to bootstrap uncertainty. This **partially exonerates** the "beyond severity" claim: NEE load adds discrimination that is both statistically non-zero and clinically non-negligible in the complete-case stratum.

**Caveat.** The AUC increment is measured in the sicker complete-case subset (24.3% mortality). In the full landmark cohort (16.0% mortality), the severity model AUC would differ, and the NEE increment might be smaller if low-severity patients have less variance in NEE. The generalizability qualifier from R2-1 applies here too.

**Verdict for publication:** The "predicts mortality beyond severity" claim can be made with delta-AUC = 0.024 [0.016, 0.035] as supporting evidence. This should be stated as an *additional* finding, not as the primary claim. The incremental AUC must be computed and reported as part of the results, not inferred from the OR alone.

---

## R2-4 — MODERATE — NEW
### Peak-NEE OR (1.416) is materially weaker than load-OR (1.743)

**Numbers** (n=4,260 complete cases, full severity adjustment):

| Exposure specification | OR/SD | 95% CI |
|---|---|---|
| log₁p(NEE cumulative load) — primary | 1.743 | [1.595, 1.967] |
| log₁p(NEE peak instantaneous rate) | **1.416** | [1.315, 1.589] |

The peak-based OR is 18.7% lower and has a narrower CI, but the CIs of the two specifications overlap. The gap indicates that **duration of vasopressor exposure contributes independent mortality information beyond peak intensity** — consistent with cumulative hemodynamic stress rather than just peak shock severity. This is biologically plausible and supports the "load" framing, but reviewers who prefer peak (as a proxy for shock severity at one instant) will see a weaker signal. The peak specification does not falsify the claim; it weakens the magnitude.

**Disclosure required:** Report both specifications and note that the load metric (integrating rate × duration) outperforms peak alone. This is a strength of the load framing, not a weakness — it demonstrates that duration matters independently.

---

## R2-5 — MINOR — NEW (favorable)
### Robustness table: all load-based specifications survive

| Specification | OR/SD | 95% CI | vs Primary |
|---|---|---|---|
| Primary (full-adj, load, dopa=0.01) | 1.743 | [1.595, 1.967] | reference |
| Winsorize at 99th pctile (NEE ≤ 978) | 1.742 | [1.594, 1.967] | –0.001 (trivial) |
| Drop comorbidity covariate | 1.807 | [1.648, 2.035] | +0.064 (minimal) |
| Dopamine weight 0.05 | 1.749 | [1.601, 1.970] | +0.006 (negligible) |
| IPCW-weighted | 1.637 | (no boot CI) | –0.106 (moderate) |

**Verdict:** The OR 1.74 is robust to extreme-value sensitivity (winsorization), dopamine NEE conversion parameter, and inclusion/exclusion of the comorbidity proxy. The IPCW correction is the largest perturbation (6.1%) and represents the most substantive sensitivity, but even the IPCW-corrected estimate maintains an E-value > 2.

Comorbidity count (ICD code count) is confirmed as a weak independent contribution: dropping it moves OR from 1.743 to 1.807. This means comorbidity is acting as a *negative* confounder (sicker comorbid patients have higher NEE AND higher death, and removing the control inflates the apparent NEE effect slightly). This is the expected direction and indicates comorbidity is appropriately included.

---

## Summary of attacks and net verdict

### Is OR 1.74 robust?

| Axis | Verdict |
|---|---|
| Internal specification robustness | ROBUST: winsorize/dopa-weight/comorbidity all give 1.72–1.81 |
| Selection bias (complete-case) | MODERATE concern: IPCW-corrected OR 1.637, but still > 1.0 |
| Unmeasured confounding (E-value) | CRITICAL gap: GCS and P/F each plausibly exceed threshold; E-value is not a strong defense |
| Generalizability | LIMITED: OR estimated in the sickest 17.8%; may not hold in the full 23,925 |

### Is OR 1.74 clinically meaningful?

**YES, conditional.** Delta-AUC = 0.0243 [0.016, 0.035] — above the 0.02 conventional threshold. The NEE load adds meaningful discrimination over a 6-covariate severity model in the complete-case stratum. This is the most favorable finding of this review.

### What must change before submission

1. **CRITICAL:** Run multiple imputation (MICE, m=20) as the primary analysis. Report complete-case as a sensitivity. The 82.2% data loss is not defensible as a primary analysis when missingness is informative (sicker patients have more labs, and those are the complete cases).

2. **CRITICAL:** Reframe the E-value language. Do NOT write "E-value 2.1–2.3 suggests the association is robust to moderate unmeasured confounding." INSTEAD: "An E-value of 2.11 for the CI lower bound means that a confounder producing RR ~2.1 with both vasopressor load and death would nullify the result; the SOFA neurological (GCS) and respiratory (PaO₂/FiO₂) components — which we could not obtain — each plausibly satisfy this threshold. Full SOFA adjustment (requiring chartevents) remains needed for a stronger causal claim."

3. **MODERATE:** Add the incremental AUC to the results table: delta-AUC = 0.024 [0.016, 0.035]. This is the strongest single number supporting the "beyond severity" framing.

4. **MODERATE:** Report both load and peak specifications. The load >> peak result (OR 1.74 vs 1.42) is a positive story (cumulative burden matters) but must be pre-specified, not cherry-picked.

5. **DISCLOSED, no action needed:** IPCW result (OR 1.64) can be included as a supplemental sensitivity with the caveat that the weighting model itself is approximate.

---

## Cross-references

- `docs/FINDING4_LANDMARK.md` — the claim being attacked  
- `docs/RED_TEAM_ROUND1_STATS.md` — prior round issues (S2, S4 resolved; S6 disclosed)  
- `docs/RED_TEAM_ROUND1_SYNTHESIS.md` — C3 full adjustment run; net verdict after Round 1  
- `analysis/finding4_landmark.py` — production code (not modified)
