# REDTEAM_PUB_FINDING1.md — Publication-lens adversarial review of FINDING 1

**Reviewer role:** Reviewer 2, top critical-care/anesthesiology journal  
**Task:** Would FINDING 1 survive external peer review, and what must be fixed or retracted before submission?  
**Review date:** 2026-06-30  
**Scope:** The vasopressor dose-requirement is a reliable, early, mortality-graded patient trait that survives severity adjustment (OR ~2.5–3.0 beyond lactate+SOFA+comorbidity), with confounding by indication argued against on five fronts, and externally validated VitalDB → INSPIRE → MIMIC. Scoped as risk-stratification, not causal.

---

## Preamble — what the internal rounds missed

Three internal hostile-review rounds are thorough by the standards of analytical self-critique, but they share a blind spot: they ask "does the result hold?" rather than "is the result publishable?" Publication review applies additional filters that internal adversarial reasoning tends to underweight:

1. Exact scoping and sentence-level overclaim in prose (not just data)
2. Reporting completeness versus field expectation
3. Novel contribution clearly distinguished from prior art
4. Data-integrity standards a journal data editor would flag
5. Reproducibility and code/data availability
6. Integrity of each quasi-experimental argument evaluated at publication standard, not just "stronger than nothing"

The concerns below are organized as CRITICAL (reject-level or major-revision required), MODERATE (required revisions before acceptance), or MINOR (revise before final submission).

---

## CRITICAL CONCERNS

### C1. The "beyond-severity" decisive test rests on an unfinished dataset — this is not publishable as-is

**The problem.** The headline claim that OR survives beyond lactate+SOFA (OR 2.44–2.53, CI 1.90–3.21) is computed on a **38–46% subject-sorted subsample** of MIMIC's labevents file, because the full 2.4 GB gzip file suffered a transfer corruption mid-stream (`zlib invalid distance code`). The internal docs carry a "PRELIMINARY" banner and explicitly state the full-N run was never completed.

No top-tier journal will accept a decisive "beyond-severity" analysis on an admittedly incomplete dataset. "Two independent subsamples converged" is a reasonable internal reassurance, but it does not satisfy data-integrity standards for publication. A reviewer or data editor will:

- Immediately notice the complete-case N (3,824) is only 24% of the stated cohort (15,949 norepi stays)
- Note that the "convergence" argument is itself derived from the same partial download
- Flag that the SOFA approximation (no GCS, no PaO2/FiO2) means the adjusted OR 2.44 is already a ceiling, and full-SOFA could attenuate further

**The fix required before submission.** Download the full labevents file cleanly, run the lactate+SOFA analysis on the complete N=15,949 cohort, and report a single definitive estimate. The subsample convergence argument is not a substitute for the actual data. Until this is done, the headline "survives lactate+SOFA-labs" claim cannot be published.

**Why this is CRITICAL.** Without the complete analysis, the paper's central quantitative contribution — the "OR 2.44–2.53 beyond severity" — is not a reportable number. The paper cannot advance past internal analysis stage.

---

### C2. The prescribing-preference IV has a fatal unit-level confounding problem that the internal review undersells

**The problem.** The IV uses the patient's ICU care unit as the instrument (leave-one-out mean unit dose tendency, first-stage F=156). The argument is: provider preference, not individual severity, drives dose variation, so the IV isolates a severity-independent dose signal.

This argument fails the exclusion restriction test in a way the internal docs acknowledge only obliquely: *"a unit that titrates higher may also be a sicker unit."* This is not a minor caveat — it is the instrument's Achilles heel. ICU care units are not randomly assigned. The MICU, CVICU, SICU, and CCU serve systematically different patient populations (CVICU OR 4.1 vs SICU OR 2.7 in the subgroup table). If the instrument is correlated with unobserved patient severity (which it demonstrably is, given the known case-mix differences across unit types), the exclusion restriction is violated and the IV estimate is biased in an unknown direction.

Furthermore, the **IV-OR (3.78) is larger than the naive OR (~2.57)**, which is a red flag that publication reviewers will seize on. When an IV estimate exceeds the unadjusted estimate in a setting where confounding should attenuate the naive estimate downward, one of two things is true: (a) the IV has successfully isolated a LATE that is genuinely larger than the ATE, which is plausible but requires justification, or (b) the instrument is invalid (exclusion restriction violated), biasing the IV upward. The internal response cites (a) but does not provide the evidence needed to distinguish it from (b). A reviewer will not accept this on faith.

**What a publication reviewer will write:** "The unit-level instrument is not plausibly exogenous. Units differ in case-mix, staffing, protocols, and case volume — all of which predict mortality independently of vasopressor dose. The larger IV-OR is more consistent with an upward-biased invalid instrument than with a genuinely larger LATE. The authors' note that 'weak instruments bias toward the naive' is inapposite here: the first-stage F is high (156), so the IV estimate is precisely wrong if the exclusion restriction fails, not weak. The negative-control propofol test is more defensible and should carry more weight than this IV."

**The fix.** Either (a) drop the IV from the primary confounding argument and relegate it to a supplement with an explicit statement that it is hypothesis-generating due to exclusion-restriction concerns, or (b) provide a formal sensitivity analysis for exclusion restriction violation (e.g., Conley et al. or Nevo and Gorfine bounds) and a formal test that the unit-level OR is not explained by case-mix differences detectable in observed data.

**Why this is CRITICAL.** As currently presented, the IV is described as "the strongest observational check." A referee who spots the unit-confounding problem will dismiss the IV and downgrade the confounding-by-indication argument to three fronts (E-value, within-stratum, negative-control propofol), which is weaker. If the IV is retained with its current framing, it will draw a rejection recommendation from any methodologically sophisticated reviewer.

---

### C3. Scope mismatch between VitalDB (the mechanistic setting) and MIMIC (the mortality evidence) is not adequately resolved

**The problem.** The control-theory framing is the paper's conceptual anchor: MAP is feedback-regulated intraoperatively, so the dose (controller effort) encodes the hemodynamic insult. This is demonstrated only in VitalDB (MAP CV 0.09 vs dose CV 0.44). The mortality evidence lives in MIMIC (n=15,949). MIMIC ICU patients are not intraoperative — they are critically ill, MAP is NOT feedback-regulated to a fixed target by a single anesthesiologist, and the control-theory argument does not apply without independent demonstration.

The internal docs acknowledge this as "HONEST LIMITATION" (#13, attack map): "MIMIC never pulls MAP; premise (MAP CV<<dose CV) shown in VitalDB only." But the paper cannot simultaneously (a) use the control-theory framing as its novelty claim and (b) derive the mortality evidence from a setting where that framing is unverified. The framing either applies to the ICU (in which case, prove it in MIMIC by pulling MAP from chartevents) or the mortality claim stands alone as an observational association without the mechanistic story.

**What a reviewer will write:** "The paper's core theoretical contribution is the control-theory framing of vasopressor dose as controller effort. However, the large-N mortality evidence is from MIMIC-IV ICU stays, where the MAP-as-regulated-variable premise has not been demonstrated. ICU vasopressor titration is not the same feedback-control loop as intraoperative anesthetic management. The authors must either validate the control-theory premise in MIMIC (which requires extracting MAP from chartevents, a 30 GB file they have not accessed) or decouple the theoretical framing from the empirical mortality claim."

**The fix.** Restructure the argument: the VitalDB section is a mechanistic proof-of-concept (small N, single centre, limited phenotype) that provides the theoretical motivation. The MIMIC section is a large-N demonstration that the underlying construct (dose as a reliable patient trait that grades severity) generalizes. The control-theory premise motivates WHY we look at dose rather than pressure; it does not need to be proven in MIMIC for the association to hold. State this explicitly and do not let a reader infer the mechanism is shown in the ICU setting.

**Why this is CRITICAL.** This concern touches the paper's novel framing, which is the primary claim of scientific contribution. If a reviewer concludes the framing is applied to a setting where it is unverified, they will recommend rejection on grounds of overclaiming.

---

### C4. Novelty is unclear and may not meet the bar for a top journal

**The problem.** "Vasopressor dose predicts ICU mortality" is not new. Dunser et al. (norepinephrine dose and mortality), Martin et al. (vasopressor use and outcomes), and many others have shown this. The APACHE-III study included vasopressor use as a severity marker decades ago. The internal ledger acknowledges this but claims the novelty is:
1. The "control-theory framing" (vasopressor dose as controller effort, not just treatment intensity)
2. The "requirement-as-trait" concept (split-half reliability, early→late predictability)
3. Cross-setting replication with explicit quantification of the trait structure

These are genuinely incremental contributions. The control-theory framing is novel. The reliability decomposition is methodologically interesting. But the case that these constitute a high-impact finding for a top critical-care journal is not made in the materials reviewed.

**What a reviewer will write:** "The finding that higher vasopressor dose is associated with higher mortality is well-established. The authors frame their contribution as the 'control-theory' interpretation and the 'trait reliability' quantification. While intellectually interesting, it is unclear what the clinical or scientific implication is beyond confirming what every intensivist already knows: the patient who needs more norepinephrine is sicker and more likely to die. The reliability analysis shows that dose-ordering is stable within a patient — but this is expected from any persistent physiological state. The novelty claim requires the authors to clearly state, in the introduction, what specifically cannot be concluded from existing literature, and how the present work changes that."

**The fix required.** A systematic comparison to existing work that quantifies vasopressor dose and mortality (including APACHE models, the Vasopressin and Septic Shock Trial [VASST] dose analyses, and any severity-score literatures). Identify the specific gaps in existing work that this paper fills. The control-theory framing and trait-reliability angle must be foregrounded as the novel frame, not the association itself.

---

## MODERATE CONCERNS

### M1. The per-SD OR reporting is non-intuitive and will confuse clinical reviewers

**The problem.** Every OR is reported per-SD of the vasopressor requirement. A clinical reviewer does not know what 1 SD of norepinephrine dose means at bedside. The dose-response quartile table (Q1 14% mortality → Q4 65%) is far more interpretable and should be the primary presentation. The per-SD OR is a legitimate summary statistic for continuous predictors but should be supplementary or clearly linked to absolute dose numbers.

**The fix.** Present the dose-response gradient (Q1–Q4 mortality table, severity-adjusted) as the primary outcome. Include the natural unit of the dose (median dose per quartile in mcg/kg/min, severity-adjusted predicted risks). Move per-SD OR to secondary.

---

### M2. Complete-case selection for the lactate+SOFA analysis requires explicit handling, not just narrative justification

**The problem.** The n=3,824 complete-case analysis (lactate+SOFA) versus n=15,949 full cohort is a 76% reduction in sample size. The internal audit shows (correctly) that the age-adjusted requirement OR is 3.80 in both the complete-case and full cohort, arguing selection does not bias the effect. This is a valid observation, but it addresses only one failure mode (selection on the exposure). It does not address whether the covariate-outcome relationship changes in the lab-complete (sicker) subset in a way that makes the attenuation from OR 3.80 to 2.44 non-representative of the full cohort. The internal docs acknowledge this residual: "lab covariates have more variance to absorb there [in the sicker stratum]." This sentence is important and must be prominent in the published methods, not buried.

**The fix.** Include a multiple-imputation sensitivity analysis (impute lactate, creatinine, bilirubin, platelets) and compare the imputed-OR to the complete-case OR. If they agree, the complete-case analysis is defensible. If the imputed OR is lower, the complete-case result is an overestimate.

---

### M3. Multiplicity statement is incomplete for the MIMIC secondary analyses

**The problem.** The ledger correctly notes that the two VitalDB primary statistics (early→late Spearman, split-half reliability) survive Bonferroni across ~30 tests. But the MIMIC analysis surface is large and post-dated this Bonferroni count: 13 subgroups, 5 severity specifications, early-warning landmarking, 3 time horizons, propofol/IV quasi-experiments. None of these are covered by the original Bonferroni. The paper presents many of these with confidence intervals and "positive everywhere" language that reads confirmatory.

**The fix.** Declare exactly ONE pre-specified MIMIC primary analysis (the severity-adjusted OR from the complete-case lactate+SOFA model). Label all subgroup analyses, quasi-experiments, and secondary specifications as exploratory. Compute a multiplicity-corrected CI for the primary. This is standard practice and a reviewer will demand it.

---

### M4. The propofol negative-control argument has an important confound that is undersold

**The problem.** Propofol OR 0.88 vs norepi OR 3.01 (head-to-head) is presented as evidence that the vasopressor signal is specific, not generic treatment intensity. But propofol OR 0.88 is protective — it predicts LOWER mortality in this model. This happens because the model mutually adjusts norepi and propofol, and propofol use is a marker of sedation/analgesia competence and controlled intubation, which in some patient subsets is actually protective (sedation for ventilated patients, comfort care de-escalation, etc.). The propofol finding is non-trivial to interpret and may reflect model collinearity rather than a clean negative control.

More specifically: propofol appears protective (OR<1) in a head-to-head model with norepi. A reviewer may ask: "Is propofol being used primarily in patients who are already anesthetized for procedures, making them a systematically better-prognosis subgroup regardless of vasopressor status?" If so, the negative-control interpretation is not secure.

**The fix.** Restrict the propofol negative-control analysis to mechanically ventilated patients only (where propofol use tracks sedation depth, not anesthetic state). Report the propofol OR in ventilated patients with and without norepi adjustment. If propofol OR is null (not protective) in this subset, the negative-control argument is cleaner. If it remains protective, acknowledge the confounding more explicitly and rely on the negative-control to show only SPECIFICITY (norepi >> propofol), not to argue propofol is a clean null.

---

### M5. Characterization vs. prospective OR conflation risk persists in the abstract-level claim

**The problem.** The whole-stay OR (~3.0–3.8) is a contemporaneous characterization measured over the same stay as the outcome. The genuinely prospective number is the landmarked first-6h OR 1.54 [1.43, 1.68]. The internal docs acknowledge this separation clearly, but the abstract-level claim language ("early, reliable signal") could be read as implying a prospective prediction with OR~3. In a clinical audience, "early identification" with OR 3 at 6h vs. OR 1.54 is a clinically significant difference.

**The fix.** In the abstract and title, use OR 1.54 as the prospectively interpretable effect. The whole-stay OR belongs in the characterization/risk-stratification framing, clearly labeled as not a prospective predictor. Do not let "OR ~3" appear in the abstract unless qualified as "contemporaneous characterization."

---

### M6. VitalDB sample size and the core mechanistic claim

**The problem.** The VitalDB mechanistic analysis (control-theory, MAP CV vs dose CV, stable-epoch phenotype) rests on:
- 52 patients with a qualifying requirement phenotype (≥2 stable epochs)
- 30 cases for split-half reliability
- 15 cases for SVR correlation (n=15, wrong-signed)

This is a very small cohort. The reliability of 0.82 at n=30 is a promising signal but not a publishable mechanistic cornerstone. The five-fold between-patient spread and the split-half reliability need prospective validation in a larger intraoperative cohort before the control-theory mechanistic claims can be carried as more than hypothesis-generating. The internal docs already acknowledge the "single-mechanism setting" limitation, but the paper's framing treats the VitalDB mechanistic finding as an established anchor rather than a preliminary observation.

**The fix.** Reframe the VitalDB section as proof-of-concept (hypothesis-generating, n=52). The mechanistic claim belongs in the Discussion as a theoretical framework motivating the MIMIC analysis, not as a confirmed finding. Any reference to "control-theory" in the abstract or conclusions should be hedged appropriately.

---

### M7. INSPIRE validation is substantially weaker than presented

**The problem.** The INSPIRE external validation shows:
- Trait-across-operations Spearman 0.317 (n=218 subjects with norepi ≥2 ops) — this is a moderate trait signal
- Incremental AUC over MAP+demographics: ΔAUC 0.004 for in-hospital death, 0.0022 for composite outcomes

ΔAUC of 0.002–0.004 is not clinically meaningful. The INSPIRE validation validates the trait concept (dose ordering is reproducible) but does NOT validate that the requirement is a practically useful predictor in the INSPIRE population — it adds essentially nothing over existing clinical predictors. This distinction is critical: trait reliability ≠ clinical utility.

**The fix.** Characterize the INSPIRE result honestly: it validates that the dose-requirement construct (trait ordering) is reproducible across operations in an independent cohort, but does not demonstrate clinically meaningful incremental predictive value in that setting. Do not present INSPIRE as validating the mortality-prediction claim.

---

## MINOR CONCERNS

### m1. In-sample operating-point sensitivity/specificity must be relabeled

The early-identification ROC reports sensitivity 0.72, specificity 0.62 derived with an in-sample threshold (median of early, applied to same cohort). The AUC 0.771 is rank-based and legitimate. The sens/spec pair is in-sample optimistic and must be labeled as such or replaced with a leave-one-out threshold. This will be caught by any statistician reviewer.

### m2. VitalDB dose-unit assumption (unverified concentration)

The VitalDB dose is device mL/h/kg; between-patient comparison assumes a constant institutional norepi concentration. This assumption is stated but its scope is undersold given that between-patient "5.6-fold spread" and all phenotype conclusions rest on it. At minimum, a sensitivity analysis showing that results are consistent if concentration is assumed to vary ±20% around the institutional standard is needed. Note that split-half reliability is concentration-invariant within a patient (correctly noted), but between-patient ranking is not.

### m3. MIMIC bootstrap should cluster on subject_id, not stay

2,402 of 15,949 stays are repeat subjects. The bootstrap resamples stays; patient-clustered CIs are slightly wider but OR is robust (verified by internal audit: clustered CI [3.45, 4.19] vs reported [3.44, 4.17]). This is MINOR given the robustness check but should be corrected before publication for methodological hygiene.

### m4. Long-term (dod) competing-risks handling

The in-hospital mortality outcome is clean. Any analyses using date-of-death beyond hospital discharge require competing-risks handling (discharge alive is a competing event). The internal docs recommend promoting in-hospital mortality as the primary outcome — do so explicitly, and restrict the survival analysis to in-hospital endpoints in the main analysis. DOD-based analyses should be relegated to supplement with competing-risks framing.

### m5. Code and data availability

Publication requires a reproducibility statement. MIMIC-IV is PhysioNet-access controlled (credentialed); INSPIRE is similarly controlled; VitalDB is open-access. The analysis code should be deposited in a public repository (GitHub/Zenodo). The cache files (precomputed embeddings/aggregates) used in the analysis need either to be deposited or the regeneration pipeline must be documented and tested. The "cache/" directory in the current repo is an internal convenience; it is not a reproducibility package. This is a journal requirement, not a science concern, but editors increasingly enforce it.

### m6. ICD-based sepsis definition (not Sepsis-3)

The sepsis subgroup (n=7,894) uses ICD-9/ICD-10 diagnosis codes, which have well-documented sensitivity/specificity problems for Sepsis-3 criteria. The subgroup should be labeled "sepsis by ICD diagnosis codes (not Sepsis-3)" and a sensitivity analysis using the MIMIC-derived Sepsis-3 labels (available in MIMIC-IV as `sepsis3` derived tables) should be run. This is a standard expectation for any MIMIC-based sepsis subgroup analysis.

---

## Publishability Assessment

### Can FINDING 1 be published as currently scoped?

**Verdict: YES-WITH-MAJOR-REVISIONS**

FINDING 1 has a genuinely defensible core: vasopressor dose-requirement is a reliable patient trait (split-half reliability 0.82–0.95) with a clean mortality dose-response that survives adjustment for comorbidity and lactate+SOFA-labs beyond age alone. The cross-setting consistency (VitalDB → INSPIRE → MIMIC), the drug-agnosticism, the E-value of ~6, and the within-severity-stratum evidence are real. The control-theory framing is conceptually novel. The finding is not fatally flawed.

**However**, three CRITICAL issues must be resolved before submission:

1. The lactate+SOFA decisive analysis must be completed on the full dataset (C1). This is mechanical — redo the download, run the analysis, report a single clean number. Everything else is secondary to this.

2. The prescribing-preference IV must either be substantially revised with formal exclusion restriction sensitivity analysis or moved to a supplement and stripped of "strongest observational check" language (C2). The unit-confounding problem is real and will be caught.

3. The scope mismatch between VitalDB (mechanistic framing) and MIMIC (mortality evidence) must be restructured so the control-theory argument is clearly scoped to the intraoperative setting without implicitly claiming it explains the ICU mortality finding (C3).

The MODERATE concerns (M1–M7) are all revision-achievable: reporting style changes, a multiple-imputation sensitivity analysis, multiplicity housekeeping, and cleaner framing of the characterization vs. prospective distinction.

### Target journal tier

**Primary recommendation:** Critical Care Medicine, Intensive Care Medicine, or Anesthesiology. These journals have methodologically sophisticated editorial boards who will appreciate the reliability framing and the quasi-experimental argument structure. Critical Care (BMC) or CHEST are reasonable alternatives.

**Not ready for:** JAMA/NEJM/Lancet-level. The VitalDB N is too small for a top-tier mechanistic claim, the novelty of "vasopressor dose predicts mortality" requires extraordinarily clear differentiation from existing literature, and the incomplete lactate dataset is a fatal deficiency at that tier.

**After major revisions:** The paper could reach Intensive Care Medicine or Critical Care Medicine comfortably, and Anesthesiology if the intraoperative framing is foregrounded over the ICU mortality finding.

---

## Summary Table

| # | Concern | Severity | Required fix |
|---|---------|----------|-------------|
| C1 | Lactate+SOFA decisive test on incomplete dataset (~46% subsample) | CRITICAL | Complete the full labevents download, rerun, report single clean estimate |
| C2 | Prescribing-preference IV has fatal unit-level confounding; IV-OR > naive-OR is a red flag | CRITICAL | Strip IV from primary confounding argument, add formal exclusion restriction sensitivity analysis, or move to supplement |
| C3 | Control-theory framing claimed as mechanistic anchor but unverified in ICU (MIMIC) setting | CRITICAL | Restructure: VitalDB = mechanistic motivation (proof-of-concept), MIMIC = empirical association in a different but related setting |
| C4 | Novelty unclear relative to existing "vasopressor dose predicts mortality" literature | CRITICAL | Systematic comparison to prior art; foreground control-theory + trait-reliability as specific contributions |
| M1 | Per-SD OR not clinically intuitive; dose-response quartile table should lead | MODERATE | Restructure primary presentation around Q1–Q4 mortality with severity-adjusted absolute risks |
| M2 | Complete-case lactate selection requires multiple-imputation sensitivity | MODERATE | Run MI on lab variables; compare imputed vs complete-case OR |
| M3 | MIMIC secondary analysis multiplicity not addressed; reads confirmatory | MODERATE | Declare ONE pre-specified MIMIC primary; label rest exploratory |
| M4 | Propofol negative-control may reflect ventilation-status confounding, not just specificity | MODERATE | Restrict to mechanically ventilated patients and report stratified propofol OR |
| M5 | Characterization OR 3.8 vs prospective OR 1.54 conflation risk in abstract | MODERATE | Use OR 1.54 as the prospectively interpretable headline; relegate OR 3.8 to characterization section |
| M6 | VitalDB n=52 is too small to anchor mechanistic claims as established findings | MODERATE | Reframe as proof-of-concept, hypothesis-generating |
| M7 | INSPIRE ΔAUC 0.002–0.004 is not clinically meaningful incremental prediction | MODERATE | Characterize INSPIRE as validating trait concept only, not clinical utility |
| m1 | In-sample sens/spec (0.72/0.62) at operating point | MINOR | Label in-sample or replace with LOO-CV threshold |
| m2 | VitalDB dose-unit (mL/h/kg) concentration assumption | MINOR | ±20% concentration sensitivity analysis |
| m3 | MIMIC bootstrap should cluster on subject_id | MINOR | Recluster bootstrap; verify CI is robust (already done internally) |
| m4 | Long-term dod analyses need competing-risks handling | MINOR | Promote in-hospital mortality as primary; restrict DOD to supplement |
| m5 | Code/data availability — no reproducibility package | MINOR | GitHub + Zenodo deposit with analysis code and regeneration instructions |
| m6 | Sepsis subgroup uses ICD codes, not Sepsis-3 | MINOR | Label correctly; run sensitivity with MIMIC Sepsis-3 derived table |

---

## The one paragraph a real Reviewer 2 would write

"The authors present an interesting reframing of vasopressor dose as a controller-effort signal rather than a mere treatment-intensity proxy, with evidence for trait-reliability in VitalDB and cross-setting consistency in INSPIRE and MIMIC. The control-theory motivation is conceptually novel. However, three issues require major revision before this work can be accepted. First, the decisive 'beyond-severity' result — the paper's quantitative centrepiece — was computed on approximately 46% of the available data due to a data-transfer corruption that prevented analysis of the complete file; this is not acceptable for a submitted manuscript. Second, the prescribing-preference instrumental variable, framed as the 'strongest observational check,' has a well-known Achilles heel: ICU care units are not randomly assigned, and the instrument's exclusion restriction is not plausible when unit type and mortality are known to co-vary by case-mix (MICU vs CVICU OR 3.8 vs 4.1 in the authors' own subgroup table). The IV-OR exceeding the naive OR (3.78 vs 2.57) is consistent with an upward-biased invalid instrument, not a confirmed LATE. Third, the control-theory mechanism is demonstrated only in the 52-patient VitalDB intraoperative cohort; it is not verified in the 15,949-patient MIMIC ICU cohort that provides the mortality evidence. These three issues are individually addressable with major revision; together they define the revision roadmap."

---

_This review was generated as a structured adversarial audit for pre-submission hardening. It does not represent an actual journal decision._
