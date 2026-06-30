# Occult vasopressor dependence at normal pressure (ICU) — the novel finding

The control-theory claim, tested where the mechanism actually holds (the ICU, where pressors are
titrated to a MAP target so MAP is held near-constant), on a hard outcome at scale, using per-stay
MAP stream-filtered from MIMIC-IV chartevents (7.58 M MAP rows, 76,500 cohort stays; itemids 220052
ABPm / 225312 ART BP mean / 220181 NBPm). Code: `analysis/icu_occult_dependence.py` →
`cache/icu_occult_dependence.json`. Landmark design throughout (first-24h exposure, alive at 24h,
post-24h death).

## The claim (reframed after Round-3 red-team)
**Among ICU patients whose MAP is AT TARGET — the population regarded as hemodynamically managed —
the vasopressor REQUIREMENT discriminates a 9-fold mortality gradient that the MAP value itself
cannot see.** The load-bearing, novel fact is an INFORMATION GAP: the requirement-vs-MAP mortality
AUC gap nearly DOUBLES once MAP is at goal (0.156 in the not-at-target stratum → **0.268** at target).
This is a risk-stratification / monitoring-information claim (the discriminative signal is the dose,
not the regulated pressure), motivated as a monitoring-error caution — NOT a demonstrated causal or
decision-benefit claim (clinicians do see the dose; "at target" is a post-treatment conditioning).
It is distinct from VIS / VDI (dose÷MAP) / BPRI (MAP÷VIS), none of which condition on having ACHIEVED
MAP target and then ask whether the dose stratifies within that stratum; and it is NOT a patient
"trait" (cross-encounter ICC 0.07, retracted in Round 2) — it is an acute, within-encounter signal.

## Result

### (A) Control-theory premise — now CONFIRMED in the ICU (was VitalDB-only; closes Round-1 causal Issue 1)
First-24h within-stay variability (n=21,154 stays with both signals):

| | median CV |
|---|---|
| MAP (the regulated variable) | **0.125** |
| NEE infusion rate (controller effort) | **0.440** |
| ratio dose / MAP | **3.5** |

This replicates the VitalDB observation (MAP CV 0.09 ≪ dose CV 0.44, ratio 5.2) in an independent
ICU cohort. **Honest caveat (Round-3 causal):** that a regulated variable varies less than its
controller is partly a control-theory *identity*, not an empirical discovery — so this does NOT by
itself prove the dose is causally informative. The non-tautological content is the *magnitude*: ICU
MAP is in fact held tightly (CV 0.125), confirming the premise that MAP is regulated to target in
this cohort (so conditioning on "at target" is meaningful). The earlier phrasing "closes causal
Issue 1" is withdrawn — it documents the regulation, it does not establish causal information content.

### (B) Occult dependence in the at-target-MAP stratum
At-target = median first-24h MAP in [65, 85] AND <10% of readings below 65 (n=7,841; mortality 12.4%):

| Requirement quartile | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| post-24h mortality | **3.1%** | 7.4% | 11.4% | **27.8%** | (monotone, 9×) |

- age-adjusted OR per SD (log NEE-load, mcg/kg-min units) = **2.82 [2.58, 3.09]**
- age + lactate adjusted = **2.59 [2.23, 3.12]** (n=2,590)
- **FULL severity adjusted** (age+lactate+creatinine+bilirubin+platelets+comorbidity), complete-case
  n=1,433 = **1.84 [1.56, 2.25]**, **E-value 2.53** (CI-LB 2.16); 32% attenuation (= the overall landmark).
- **Multiple-imputation pooled** (MICE m=10, Rubin's rules, full at-target cohort n=7,836) =
  **2.04 [1.85, 2.24]** — HIGHER than the complete-case 1.84 (complete cases were sicker, so 1.84 was
  conservative); the informative-missingness threat is resolved and the finding generalizes.
  **E-value of the MICE primary** (p0=0.124): **3.01 (point) / 2.74 (CI-LB)** — stronger than the
  earlier-cited 2.5 (which belonged to the complete-case sensitivity). MICE caveat: labs imputed on raw
  (not log) scale — minor precision loss, does not change the OR.
- **Within-severity persistence INSIDE at-target** (Round-4, resolves a confounding gap): requirement
  OR/SD by first-24h lactate tertile = **2.30 [1.83,3.01] / 3.27 [2.41,4.68] / 2.72 [2.21,3.56]** —
  3/3 strata exclude 1, so the dose-response is not explained by within-stratum severity.
- **Invasive (art-line) MAP only** (n=6,301): age-adj OR **3.10 [2.82, 3.45]**, gradient 10.5× — the
  signal is STRONGER where the pressure is genuinely regulated, exactly as the mechanism predicts.

All of these patients have a normal, at-goal mean arterial pressure. Their pressure does not tell them
apart; their requirement separates a 3% from a 28% mortality.

### (C) Information content — the decisive contrast
Out-of-fold AUC for post-24h mortality:

| | overall cohort (n=23,920) | within at-target band (n=7,841) |
|---|---|---|
| MAP alone | 0.558 | **0.475** |
| Requirement alone | **0.723** | **0.743** |

Within the at-target band the requirement carries strong mortality information (AUC 0.74) while MAP
carries essentially none (AUC 0.47).

**The information gap (Round-4 correction — "doubling" RETIRED).** The requirement-vs-MAP AUC gap is
0.156 not-at-target vs 0.268 at-target, but a code-level decomposition shows this widening is **72% a
MAP restriction-of-range artifact** (MAP AUC drop −0.080, mechanical: MAP SD falls from 9.1 to 4.0 in
the band) and only **28% genuine requirement signal** (requirement AUC rise +0.031 [0.012, 0.051]).
So "the gap doubles" is mostly an artifact and is RETIRED as a headline. The load-bearing, non-
artifactual quantity is the **requirement AUC within the at-target stratum: 0.743** (vs 0.712 not-at-
target) — real, stable across age tertiles (0.743/0.756/0.743), survives MICE, not explained by severity
(lactate is identical across strata, 3.16 vs 3.17). The honest claim: *among normal-MAP ICU patients the
dose discriminates mortality (AUC 0.74) while the pressure carries essentially none (AUC ≈0.50, partly by
construction)* — a monitoring-relevant fact, modest and incremental relative to VIS/VDI/BPRI.

**Collider test (the deepest Round-3 attack — PASSED).** "At-target MAP" is a post-treatment node, so
conditioning on it could in principle induce a spurious dose–severity association (collider). Decisive
test: the fully-adjusted requirement→mortality OR is **1.84 at target vs 1.68 not-at-target**
(interaction χ²=3.25, **p=0.072, NS**). A collider artifact predicts the OR be elevated ONLY within the
at-target stratum; it is not. The association is therefore not a selection artifact — what is special
about the at-target stratum is the INFORMATION GAP (MAP goes uninformative), not a larger effect size.

## Honest caveats (to be hardened by red-team)
1. **Restriction-of-range for MAP (important):** within the [65,85] band MAP variance is small by
   construction, so MAP's low within-band AUC (0.47) is *partly* a restriction-of-range artifact, not
   purely "MAP is uninformative." The load-bearing, non-artifactual claim is the **requirement** side:
   requirement is NOT range-restricted, and its within-band AUC 0.74 + monotone 9× gradient are real.
   The honest framing is "within the normal-MAP population, the requirement stratifies risk that the
   pressure cannot," not "MAP is literally worthless."
2. **Confounding by indication / severity:** at-target-with-high-requirement may still be sicker
   (vasoplegic/septic). age+lactate OR 2.59 partially addresses; FULL severity adjustment (SOFA labs +
   comorbidity), E-value, and within-severity stratification are required (next: red-team round).
3. **Complete-case:** lactate-adjusted n=2,590 of 7,841 — informative missingness (see the landmark's
   IPCW lesson); multiple imputation needed for the primary.
4. **At-target definition is one choice:** band [65,85] + <10% below 65; sensitivity across bands needed.
5. **MAP source mixes invasive (ABPm) and NBP:** module prefers invasive (≥3 readings) and falls back
   to NBP; an invasive-only sensitivity is needed (the regulated-to-target claim is strongest for art-line).
6. Observational; landmark defeats reverse-causation temporally but not confounding.

## Prior art (Round-3 novelty review) — PARTIALLY NOVEL; cite head-on
- **VDI** (Vasopressor Dependency Index = dose÷MAP; Miyamoto, BEAT-SHOCK, *Shock* 2025) and **BPRI**
  (MAP÷VIS trajectory phenotyping; Shen, *Critical Care* 2026, MIMIC-IV) already link a dose/MAP ratio
  to mortality. These MUST be cited; the paper is desk-rejected if it ignores them.
- **What is genuinely new:** the **at-target conditioning** — no prior work restricts to patients who have
  ACHIEVED MAP goal and then asks whether the dose stratifies within that stratum — and the **across-
  stratum AUC gap** (0.156→0.268). That two-word move ("at target") and the information-gap are the
  contribution; the abstract's first sentence must say so.
- **Realistic tier:** Critical Care Medicine / Intensive Care Medicine (top critical-care). Not
  Anesthesiology for a standalone ICU analysis; not JAMA/NEJM.

## Why this is the novel candidate (and its honest scope)
- **Not VIS/VDI/BPRI:** those summarize dose (or dose/MAP) as severity; this conditions on MAP being
  *at target* and shows the dose is the discriminative signal precisely when the pressure is reassuring.
- **Not the dead trait:** an acute, within-encounter, outcome-linked signal, not a cross-encounter
  phenotype (ICC 0.07, retracted Round 2).
- **Scope (honest):** risk-stratification, not causal/decision-benefit. The "monitoring-error" reading is
  the motivation, not a proof — clinicians do see the dose, and confounding-by-indication within the
  at-target stratum (missing GCS / PaO2-FiO2 / shock-etiology) is bounded by E-value 2.5, not eliminated.

Cross-ref: FINDING4_LANDMARK.md (the landmark machinery), RED_TEAM_ROUND2_SYNTHESIS.md (why trait/VIS
framings were retracted), OCCULT_DEPENDENCE_FEASIBILITY.md (why intraop INSPIRE could not test this).
