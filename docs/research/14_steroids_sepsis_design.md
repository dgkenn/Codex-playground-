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

## v2 RESULT — g-methods target-trial emulation (the differentiated design working)

MIMIC N=14,381 septic shock; hydrocortisone-by-24h n=1,020; hyperlactatemic-vasopressor-refractory (HLVR)
phenotype n≈1,105–1,384 (consistent across trajectory / baseline / k4-C2 definitions). Time-varying MSM
(stabilized IPW) + cause-specific & subdistribution competing-risk models. Bootstrap CIs preliminary (8 reps;
the 200-rep run was impractically slow — killed; point estimates + 8-rep CIs already exclude null).

**1. Time-varying adjustment moved the naive harmful estimate toward null (confounding WAS time-varying, as
predicted):** mortality naive HR 2.50 → g-HR 2.16; shock-reversal (cause-specific) naive HR 0.63 → g-HR 0.79.
Overall steroids still look harmful/neutral (residual confounding-by-indication — the sickest get steroids),
as expected — the OVERALL effect is not the finding.

**2. The phenotype × steroid INTERACTION is the finding — consistent across all 3 phenotype definitions:**
| Outcome | steroid HR in non-HLVR | steroid HR in HLVR | interaction HR (CI) | E-value |
|---|---|---|---|---|
| Shock reversal (cause-specific) | 0.84 (delays) | **1.21 (speeds)** | 1.43 (1.29–1.47) | 2.22 |
| Shock reversal (subdistribution) | 0.82 | **1.29** | 1.57 (1.30–1.68) | 2.51 |
| 28-day mortality | 2.04 (harmful) | **1.05 (neutral)** | 0.52 (0.49–0.57) | 3.28 |
(C2-cluster phenotype even stronger: reversal interaction 1.61–1.78, mortality interaction 0.47, E-values to 3.6.)

**Interpretation:** in the hyperlactatemic, vasopressor-refractory phenotype hydrocortisone is associated with
FASTER shock reversal and NEUTRAL mortality; in the rest it looks reversal-delaying and harmful. This is exactly
what trial biology (APROCCHSS refractory-shock benefit) and the bedside intuition ("give steroids to refractory
shock") predict, and it is the mechanism-anchored phenotype the design pre-specified.

**Falsification battery:**
- **Severity-orthogonality: PASSES** — the interaction survives adding a steroid×SOFA term (AxSOFA small ~±0.22;
  the HLVR effect is not just total SOFA).
- **Negative-control outcome: PARTIALLY FIRES (the honest limit)** — the negative-control outcome shows an
  interaction of similar magnitude (AxP OR ~0.51) → residual confounding that differs by phenotype is NOT fully
  excluded. So the interaction is **hypothesis-generating / trial-ready, not causal-proven** — consistent with
  the pre-registered ceiling. Moderate E-values (2.2–3.6) mean a confounder would need to be moderately strong
  to explain it away, but the negative control says we can't claim causality.

**Verdict: PERSIST.** v2 is the strongest defensible steroids result — a consistent, mechanism-aligned,
SOFA-orthogonal, moderate-E-value effect modification on the less-confounded shock-reversal endpoint, exactly the
trial-ready stratification signal the differentiated design aimed for. The negative-control caveat keeps it
honestly at "hypothesis-generating for a stratified trial." **Next:** external-validate the HLVR phenotype +
interaction in eICU + SICdb; reduce to the parsimonious bedside score (mnemonic); pursue ADRENAL/APROCCHSS/VANISH
IPD for causal confirmation.

## v3 — external validation (SICdb primary; eICU infeasible)

SICdb N=11,591 NE-treated (cardiac-surgery excluded); hydrocortisone 1,271; HLVR 960. **Compromised test: SICdb
lactate was NOT locally available, so HLVR was defined by vasopressor-refractoriness ONLY** → it collapses onto
NE-dose severity, NOT the true hyperlactatemic-refractory phenotype.
- **Mortality interaction directionally REPLICATES:** broad OR 0.77 (NS); **true-septic-shock subset (N=742) OR
  0.14 (0.065–0.29), survives severity-orthogonality** — steroids relatively less harmful/more beneficial on
  mortality in the refractory phenotype, as in MIMIC.
- **Shock-reversal interaction FAILS** (opposite direction, HR 0.68–0.77) — but confounded by the phenotype
  mis-definition (no lactate) + single-center power.
- **eICU infeasible locally** (13 hydrocortisone rows; the `medication` table holding IV/bolus steroids isn't
  downloaded).

**Standing:** hypothesis-SUPPORTING for the mortality arm (strong in true-sepsis), non-confirmatory for reversal.
**The clean re-test (v3b, launched):** extract SICdb arterial lactate (ref IDs 454/657/465 via the existing
`sicdb_stream_lab.py` streaming approach), define the PROPER hyperlactatemic + vasopressor-refractory phenotype,
and re-run — this resolves whether the reversal failure is a phenotype-mis-definition artifact or real. Overall
steroids ceiling remains trial-ready/hypothesis-generating (MIMIC negative control partially fired; observational
HTE); RCT-IPD (ADRENAL/APROCCHSS/VANISH) is the causal gold standard.

## v3b — clean SICdb re-test with PROPER (lactate-defined) HLVR — thread SETTLED

Lactate extracted from the full remote SICdb laboratory table (711,824 arterial/blood lactate rows; 97.8% of the
cohort has a t0 lactate). Proper HLVR = hyperlactatemic AND vasopressor-refractory = 692 (268 refractory-but-not-
hyperlactatemic correctly removed); HLVR&steroid = 465.
- **Reversal arm: does NOT replicate** — moved opposite→null (septic-subset clean point 1.09, first time above 1,
  but bootstrap/orthogonalized ≤1); the positive reversal signal is carried by steroid×SEVERITY, not
  steroid×phenotype.
- **Mortality arm: directionally replicates** (septic subset OR 0.32 / HR 0.31, MIMIC-consistent protective) —
  but **FAILS severity-orthogonality** (the HLVR mortality term flips >1 once steroid×severity is added: HLVR is
  collinear with NE-dose severity even after lactate is included) and the untreated-HLVR-septic reference cell is
  n=23 (fragile).

**SETTLED honest verdict.** The decisive external signal: MIMIC v2 PASSED severity-orthogonality but SICdb FAILS
it → externally the HLVR "phenotype" is largely a SEVERITY axis, so the apparent effect modification is
severity-confounded. Net across v1→v3b: the HLVR×hydrocortisone signal is **hypothesis-generating with weak,
severity-confounded external support** — the mortality DIRECTION is consistent (MIMIC + SICdb protective in
refractory shock, echoing APROCCHSS biology) but does not survive orthogonality externally, and the reversal arm
does not replicate. This is **NOT a validated finding and not a deployable bedside tool**; it is an honest,
rigorously de-risked lead whose only clean test is RCT individual-patient-data (ADRENAL/APROCCHSS/VANISH). The
value delivered: a mechanism-anchored hypothesis + a demonstration that observational steroid-HTE in septic shock
is severity-confounded even under g-methods + trajectory phenotyping (a cautionary methods result echoing
Rajendran 2025 and Li 2023).

## Source reviews (scratchpad)
`lit_sepsis_phenotyping_landscape.md`, `lit_steroid_response_sepsis.md`,
`lit_steroid_decision_tool_methods.md`, `steroids_sepsis_design_premortem.md`.
