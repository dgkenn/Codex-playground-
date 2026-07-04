# Steroids-in-Septic-Shock: a Bedside Decision Score — Synthesized Design

Synthesis of 3 deep literature reviews + a hostile design pre-mortem. This is the differentiated, defensible
design that avoids the already-published, non-replicating naive version (Rajendran 2025).

## The white space (confirmed)
- **No published bedside steroid-decision point score for septic shock exists.** The ACTH/cosyntropin-stim test
  is dead (CIRCI 2017 could not agree on a test; SSC 2021 abandoned adrenal-axis testing and now gates steroids
  on *vasopressor severity*). No ferritin/CRP sepsis steroid score exists (that lives only in ARDS/COVID).
- The only steroid-response endotypes are **transcriptomic and mutually discordant**: VANISH SRS2 (immunocompetent)
  HARMED by hydrocortisone (adj OR 8.3, 95% CI 1.4–47.8, interaction p=0.03); ADRENAL-2025 a different scheme,
  no overall interaction, harm only in pulmonary-sepsis. **They need RNA-seq** — not bedside-deployable.
- **Do NOT build an SRS2 EHR-proxy:** transcriptomic endotypes are NOT recoverable from clinical covariates
  (Davenport: 19.6–41% misclassification). Build a NATIVE clinical phenotype instead.

## The differentiated wedge (novel per review, never paired with steroids)
**A native clinical phenotype from EARLY TRAJECTORIES, not a static snapshot or an endotype proxy:**
- **Axis 1 — catecholamine-refractoriness:** norepinephrine-equivalent vasopressor-dose trajectory over the
  first 6–24 h (rising/refractory vs resolving). This is the actual bedside steroid trigger AND where relative
  adrenal insufficiency is most likely. *Novel: no prior steroid-HTE test on a vasopressor-trajectory phenotype.*
- **Axis 2 — perfusion resolution:** lactate-clearance trajectory over the same window (non-resolving vs
  clearing). Method is validated (Bhavani/Churpek GBTM trajectories beat snapshots, robust across algorithms)
  but *never paired with corticosteroids*.
- **Axis 3 (secondary, exploratory) — immune tone:** NLR / lymphopenia, with the **CORRECTED direction** — the
  immunoCOMPETENT (not immunoparalyzed) group is the harmed one (VANISH SRS2). Weak proxy (Sweeney: only
  bandemia + low-lymphocyte% correlate with the inflammopathic transcriptomic cluster; no validated NLR↔SRS
  study), so exploratory only. Watch the Weingart-2025 confound (immunocompromise status drives "hyperinflammatory"
  assignment).

## Outcome (the tractability move)
- **PRIMARY: shock reversal / vasopressor-free days** — steroids have a *reliable, less-confounded* effect here,
  and it dodges Rajendran's noisy/confounded mortality endpoint. Competing-risk aware (death before reversal).
- **SECONDARY: mortality** — report with full confounding caveats; do not lead with it.

## Method (effect-modifier, per Kent PATH statement)
1. Derive the phenotype/CATE on MIMIC: causal forest / X-learner (Wager-Athey) for the individual steroid
   treatment effect on shock reversal, features = baseline + early trajectories. (Note: a plain causal forest on
   pooled RCTs was already done by Pirracchio 2020 — our novelty is the TRAJECTORY features + the bedside-score
   reduction + the shock-reversal endpoint + 3-cohort EHR validation, not the CATE engine per se.)
2. **Reduce to a parsimonious bedside score** (Sinha ARDS-classifier template): variable-importance shortlist →
   nested-model parsimony → a 4–5 item point score with a memorable mnemonic. Validate the treatment-INTERACTION
   signal, not just the label.
3. **Report (required):** score×steroid interaction; decision-curve analysis (Vickers); **E-value on the
   interaction term** (VanderWeele); calibration.

## Causal safeguards (from the pre-mortem — mandatory)
- **Clone-censor-weight target-trial emulation** for immortal-time (not just a landmark).
- IPTW/propensity for steroid receipt within phenotype.
- **Severity-vs-endotype falsification battery:** non-monotonicity of the effect in severity; orthogonality to
  total SOFA; severity-blind re-clustering; qualitative (not just quantitative) between-phenotype difference.
- Negative controls; leakage audit (no post-freeze vasopressor/lactate features bleeding into baseline).

## Validation
- **Internal → external:** derive on MIMIC-IV → replicate phenotype + interaction on **eICU + SICdb**
  (cross-continental). Cross-cohort reproducibility of the interaction is the internal bar.
- **Gold standard (confirmatory path):** apply the frozen score to **ADRENAL / APROCCHSS / VANISH IPD**
  (negotiated trial-by-trial; Annane 2020 IPDMA protocol is precedent — not a simple Vivli download).

## Honest ceiling (state throughout)
This is a **trial-ready, hypothesis-generating stratification tool**, NOT a validated decision aid — an
observational effect-modifier claim inherits confounding-by-indication *at the interaction level*, which only
RCT-IPD can resolve. That is exactly the eGFR/Kent-PATH-appropriate framing and is publishable as such.

## Differentiation from Rajendran 2025 (Nat Commun, PMID 40360520)
Interpretable bedside SCORE (not black-box ML); native early-TRAJECTORY phenotype (not generic snapshot
clustering); SHOCK-REVERSAL primary outcome (not mortality); explicit Kent-PATH effect-modifier methodology +
decision-curve + E-value; and a 3rd (SICdb) external cohort.

## Execution plan
- **v1 (running):** naive snapshot discovery — keep ONLY for the reusable septic-shock cohort + steroid exposure
  + a first look at subphenotype structure. Not a finding.
- **v2 (next):** extract vasopressor-dose + lactate EARLY TRAJECTORIES; GBTM/consensus trajectory phenotypes +
  causal-forest CATE on shock-reversal; parsimonious score; falsification battery; then eICU + SICdb replication.
- Feasibility already confirmed: hydrocortisone n≈32k (+fludrocortisone), vasopressors in inputevents, lactate,
  outcomes; SICdb IDs mapped (queue).

## Source reviews (scratchpad)
`lit_sepsis_phenotyping_landscape.md`, `lit_steroid_response_sepsis.md`,
`lit_steroid_decision_tool_methods.md`, `steroids_sepsis_design_premortem.md`.
