# Findings ledger & multiplicity statement (reviewer-facing)

This study is an **exploratory discovery analysis** of VitalDB. We tested many hypotheses;
several died. This ledger makes the full search transparent, declares the **one primary
claim** we would carry forward, and shows it survives multiplicity correction. It exists
specifically to answer the *"you tested dozens of things, of course something stuck"*
critique.

## The one PRIMARY claim (the only thing framed as confirmatory-grade internally)
> In patients receiving an intraoperative norepinephrine infusion, the **early vasopressor
> dose-requirement** (a simple per-kg dose metric, measurable in the first part of the
> pressor course) identifies the **vasoplegia-prone patient** who will need sustained /
> escalating support — a signal **not** captured by demographics (age/ASA/weight) — and is
> consistent with a **control-theory principle**: because intraoperative MAP is actively
> feedback-regulated to target, the hemodynamic insult is encoded in the *dose* (controller
> effort), not in the *(held-normal) pressure*.

**Primary statistics (and multiplicity):** early-half requirement predicts late-half
requirement Spearman **+0.54** (n=52, p≈6.8×10⁻⁶); phenotype split-half reliability **0.82**
(n=30, p≈3.4×10⁻¹⁴). Across the ~30 hypothesis tests in the whole project, Bonferroni
α=0.0017 — **both primary statistics survive** by orders of magnitude. The control-theory
anchor (within-patient MAP CV 0.09 vs dose CV 0.44, ratio 5.2) is a structural fact, not a
fished p-value.

## What SUPPORTS the primary (secondary / corroborative, not independent claims)
- **Control-theory mechanism** — MAP is regulated; dose is the informative variable. Also
  shows up as: titration-transient ΔMAP is closed-loop confounded; steady-state gain ≈ 0;
  cumulative dose adds predictive value beyond MAP-AUC for AKI (association).
- **A-line vascular-tone / SVR estimator** (Pivot 2) — the routine arterial waveform tracks
  SVR validated against an INDEPENDENT cardiac-output source (thermodilution/Doppler, n=89,
  Spearman −0.42, perm p=0.001). Circularity-clean; scoped to a *ranker*, not a calibrated
  SVR. The same `map_dia_form_factor` tone carrier also predicts the requirement → the tone
  estimator and the requirement are plausibly **one vasoplegia signal seen two ways**.
- **Waveform predicts requirement** (Pivot 1) — arterial morphology predicts the requirement
  OOF Spearman +0.30 (n=52). Modest; redundant with the early dose (below).
- **Second-drug internal replication (phenylephrine)** — in PHEN (independent pure α1 agent,
  n=40) the dose-requirement is a reproducible trait: split-half reliability **0.87** (≥ norepi),
  spread 3.3×, early→late **+0.44**, construct vs exposure +0.36. → the phenotype is **drug-
  agnostic vasoconstrictor requirement**, not a norepinephrine artefact. This is the strongest
  corroboration: it replicates in a mechanistically distinct drug.

## HONEST WEAKENINGS found by internal red-team (do not hide these)
- **Specificity is partial, not airtight.** The early dose is specific by partial correlation
  (+0.47 controlling early MAP+HR) and beats placebos (HR null −0.01) and survives case-mix
  (holds excluding liver-transplant/cardiac) and jackknife ([0.51,0.57]) — BUT it does **not**
  add *cross-validated* lift beyond **early MAP** (which is itself a −0.40 predictor) at n=52.
  So: the late requirement is forecastable from early hemodynamics (MAP **and** dose); the
  dose's unique contribution is real but N-limited. Frame as "early hemodynamic state,"
  dose-led.
- **The fancy machinery is not necessary.** A plain **peak** or **time-weighted-mean** dose/kg
  matches the stable-epoch MAP-band phenotype on reliability (0.79–0.81) and correlates 0.90
  with it → use the **simple metric** as primary (more transparent, equally good). The
  stable-epoch construct earns its keep for the *mechanistic argument*, not the phenotype.
- **Selected, sicker subset.** The analyzable cohort (≥ stable epochs) has a higher adverse-
  outcome rate than excluded pressor cases (0.71 vs 0.50) → generalizes to *already-on-pressor,
  arterial-line-monitored* patients, not all-comers.
- **Construct vs SVR is the soft spot** — requirement vs EV1000 SVR +0.18 at n=15 (wrong sign,
  underpowered). The vasoplegia label rests more on dose-exposure construct than on SVR.
- **ECG pairing adds nothing** — combined ECG×A-line ≤ arterial alone for predicting
  requirement; PAT redundant with arterial morphology. Tested and negative.
- **Trajectory SHAPE / slope / onset add nothing beyond the early LEVEL** — early rate-of-rise
  is collinear with level (r=0.73); its apparent ΔR² is a negative suppressor, not a "fast
  riser = sicker" phenotype (marginal corr ≈0, fast-riser subgroup p=0.39). Onset-time
  bimodality is left-censoring artefact. Progressive-vs-transient composite RD +0.27 (p=0.13,
  severity-confounded). → the **early level is the single actionable summary**; do not sell
  trajectory shape.
- **Norepi-equivalent multi-drug expansion (N 52→154) is largely a drug-identity artefact** —
  use the norepi-only cohort for inference.

## KILLED (confounding / null — reported, not buried)
| Hypothesis | How it died |
|---|---|
| CKD personalized MAP-target (externally "validated" in 131k INSPIRE) | Negative-control calibration → renal interaction −0.0007 (z≈−0.1); generic confounding |
| Within-patient causal hypotension→AKI | Pan-organ; fails negative-control specificity → time-varying confounding |
| Cumulative pressor → AKI (causal) | Renal adjRD 0.052 < negative-control null 0.089 (z=−0.71); confounding by indication |
| ΔMAP-per-dose responsiveness (titration transient) | Closed-loop confounded (dose ↑ because MAP ↓); within slope CI crosses 0 |

## Statistical-integrity statement for the paper
1. **This is hypothesis-generating discovery, not a confirmatory trial.** No pre-registration;
   the search was sequential and adaptive. We disclose the full search (above).
2. **One primary claim**, declared here, survives Bonferroni for the project-wide test count.
3. **Effect sizes are modest and the cohort is selected/single-centre.** The honest reading is
   a *risk-stratification / early-flag* signal, not a calibrated tool and not a causal/treatment
   claim.
4. **Prospective EXTERNAL validation is the required next step** — deliberately deferred until
   internal robustness was exhausted (this ledger + the REQUIREMENT_SPECIFICITY / _PARSIMONY /
   _ONSET_SHAPE / EARLY_ID_ROBUSTNESS / PRESSOR_REQUIREMENT_PHEN batteries).

## Cross-reference
Per-finding evidence: docs/PRESSOR_REQUIREMENT.md, EARLY_ID_ROBUSTNESS.md,
REQUIREMENT_SPECIFICITY.md, REQUIREMENT_PARSIMONY.md, REQUIREMENT_ONSET_SHAPE.md,
PRESSOR_REQUIREMENT_PHEN.md, ACTIONABILITY_TESTS.md, LEVER_DISCRIMINATION.md,
PIVOT2_HOSTILE_REVIEW_VERDICT.md, COMBINED_BIOSIGNAL.md, PRESSOR_OUTCOME_CALIBRATED.md,
PRESSOR_RESPONSE_MODELING.md.
