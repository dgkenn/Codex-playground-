# Confounding-by-indication for reflexive lab-triggered treatment: gap analysis & closure status

**The /goal:** a bulletproof, broadly-applicable method to defeat confounding-by-indication for reflexive,
lab-flag-triggered inpatient treatments. This is the honest ledger of where the program stands, what is genuinely
novel vs. prior art, which gaps are closed, and what remains. Updated after: hostile red-team, formal
identification derivation, known-truth simulation, power/MDE analysis, and an RCT-anchored-validation +
prior-art literature scan.

## Headline (honest)
We have a **valid, corrected, simulation-validated methodology** and an **honest characterization of what it can
and cannot decide**. We do **not** yet have a clean real-data estimate (downloading) or the RCT-anchored
validation run. Crucially, the core idea has **direct prior art in our exact database** — so our novelty is
narrower and sharper than "we invented this."

## Novelty position (what is actually ours) — CONSTRAINED by prior art
- **Noise-induced randomization at a threshold** is established theory: Eckles, Ignatiadis, Wager, Wu
  (*Biometrika* 2025, arXiv:2004.09458) — models known running-variable noise as the randomization device and
  reweights to balance the latent variable. This is our primary methods citation, not our invention.
- **Clinical RDD at decision thresholds**: Bor et al. (*Epidemiology* 2014) — CD4/ART threshold, HR 0.65.
- **DIRECT, LOAD-BEARING PRECEDENT (must cite and distinguish):** **Bosch et al., *Ann Am Thorac Soc* 2022;
  19(7):1177–1184** ran a **fuzzy RDD at Hb 7.0 g/dL in MIMIC-IV** (+eICU+Premier), justified verbatim by
  "*measurement noise pseudorandomizes similar hemoglobin concentrations on either side of the threshold*"
  (co-author: Bor). Found transfusion raised Hb but did **not** improve organ dysfunction (mostly null). An
  editorial ("Knowledge from the Noise") reinforced the framing. **We cannot present noise-at-threshold in
  clinical data as novel.**
- **What IS genuinely ours (the defensible contribution):** (1) a **formal, estimable noise model** — assay CV /
  serial-pair variance used to *construct the instrument from the noise itself*, vs. Bosch's noise-as-prose
  justification for RDD smoothness; (2) the **renewal / repeated-decision extension** (a sequence of
  noise-randomized decisions per patient, absorbing-treatment censoring, terminal outcome, leave-one-out control
  for a serially-correlated latent state) — no prior art; (3) the **leave-one-out identification + simulation**;
  (4) the **falsification battery + honest power framing**; (5) **application to Mg/K/Phos, where NO RCT exists**
  (Bosch did Hb, where multiple definitive RCTs already exist). The program = *formalize the method → VALIDATE on
  Hb-transfusion against the RCTs (extending Bosch) → DEPLOY on Mg/K where trials are infeasible*.

## Gap table
| # | Gap | Status | Closure |
|---|-----|--------|---------|
| G1 | No real-data estimate (all theory+sim) | 🟡 closing | MIMIC re-streaming; corrected pipeline auto-runs the falsification battery on arrival |
| G2 | Decisive, or valid-but-underpowered? | 🟢 **closed** | LATE hopeless for mortality (MDE 5–12pp); flag-ITT decisive (sub-pp MDE) but must be reported WITH implied-LATE bounds (see below) |
| G3 | Validated vs a KNOWN TRUTH (RCT anchor) | 🟡 **plan set** | Hb-transfusion, dual-stratum (clean general-ICU vs contested cardiac/MI), benchmarked to Bosch 2022 + TRICC/TRISS/TITRe2/MINT |
| G4 | Broadly applicable (>1 treatment) | 🟡 partial | method is treatment-agnostic; needs empirical Hb + K/Phos stacking |
| G5 | Exclusion restriction (flag → care BUNDLE) | 🟡 open+test | NOT solved by the ITT reframing (it inherits exclusion); bundle-balance test in battery; ward-level untestable in MIMIC (chartevents ICU-only) |
| G6 | Serial-correlated noise (renewal's weak point) | 🟡 test built | lag-1 autocorr of detrended residuals + σ-by-interval in the run |
| G7 | Positioning vs proximal-CI / supply-shock; triangulation bounds | 🟢 **built** | convergent-bounds estimator + doc (`docs/DECONFOUNDING_TRIANGULATION.md`, `docs/triangulate.py`); honest — decisiveness comes from the anchor, bracket is the check/packaging |
| G8 | Assay-noise magnitude vs threshold (viability per treatment) | 🟢 mapped | Mg 6.7% of flag (good); glucose 10–35% (best, but no stable RCT truth); Hb 1–2% (weak noise-IV, but RDD-proximity first stage >20pp per Bosch) |

## G2 closure — the decisive estimand, stated honestly
Power/MDE analysis (`docs/power_mde_assay_noise_iv.py`, `scratchpad/power_mde_results.txt`):
- **Per-patient LATE for mortality is not identifiable in practice** — MDE 5–12pp at realistic first-stage
  strength (3–6pp). You cannot scale a 3pp first stage into a precise mortality LATE.
- **The flag-ITT (reduced form of noise-induced flag-crossing) is well-powered** — sub-percent MDE (0.2–0.4pp on
  mortality) and is the de-implementation policy contrast health systems actually set.
- **BUT (corrected from an earlier over-claim):** the ITT does **not** escape the exclusion restriction — it
  inherits it. And a **null ITT is near-uninformative on its own** with a weak first stage (consistent with both
  "threshold doesn't matter" and "real effect too diluted to see"). **Fix, adopted:** always report the
  reduced-form ITT **together with the implied-LATE interval** (ITT ÷ first stage, with weak-IV/Anderson–Rubin
  CIs), so a null reads as "no effect OR underpowered," never silently as "no effect." Be explicit whether the
  claim is "effect of the threshold as a bundled policy lever" (clean, but not a test of the specific treatment)
  or "diluted treatment effect" (informative about the treatment, but re-inherits exclusion risk) — cannot be both.

## G3 closure plan — RCT-anchored validation on Hb-transfusion
- **Ground truth (verified):** restrictive non-inferior/superior in general ICU (TRICC *NEJM* 1999; TRISS 2014;
  FOCUS 2011; Cochrane 2021 RR 0.99; AABB *JAMA* 2023) — but **contested** in cardiac surgery (TITRe2 mortality
  HR 1.64, P=0.045) and acute MI (MINT 2023, P=0.07 favoring liberal). A *graded* truth = a stronger test.
- **Design:** assay-noise IV / flag-ITT at Hb 7.0 (and 8.0), **two strata** — clean general-ICU (expect null =
  restrictive OK) and contested cardiac/MI (expect a borderline liberal-favoring signal). Recovering BOTH tracks
  truth across effect sizes; recovering only the clean null is a soft test.
- **Must engage Bosch 2022** as the benchmark: show the *formal* noise-model instrument (a) sharpens/reweights
  or (b) extends inference beyond their local RDD. First stage is empirically proven (Bosch: >20pp discontinuity
  in transfusion at Hb 7 in MIMIC-IV).
- **Caveat:** Hb assay noise is small (CV 1–2%) → the pure noise-IV is weak; supplement with **POC-vs-central-lab
  discordance** as an additional noise channel where available.
- **Deprioritize glucose** as the anchor (no stable ground truth — Leuven→NICE-SUGAR reversal; worse exclusion);
  reserve it as a *second, novel-white-space* paper (zero prior RDD/IV art on glucose thresholds).

## Remaining open gaps (what would most change the game)
1. **G1 empirical (Mg)** — the make-or-break; produces first real first-stage, balance, heaping, bundle,
   autocorr, flag-ITT + implied-LATE. Auto-running (`corrected_iv.py`).
2. **G3 validation run (Hb)** — the keystone that converts "valid design" → "certified method." Pipeline built
   and wired (`hb_validation.py`): Hb 51222/50811 + RBC tx 225168 + services (cardiac stratum) added to the
   filter/orchestrator; dual-stratum (general vs cardiac) flag-ITT + implied-LATE, benchmarked to Bosch 2022.
   Runs right after the Mg battery.
3. **G7 triangulation bounds** — BUILT (`docs/DECONFOUNDING_TRIANGULATION.md`, `docs/triangulate.py`). Real
   bracket pending the anchor + a demonstrated benefit-biased contraindication stratum.
4. **Pre-registration** — DONE (`docs/DECONFOUNDING_PREREGISTRATION.md`): thresholds/bandwidths/control/estimand/
   outcomes/strata locked for Mg and Hb before viewing outcomes; falsification battery runs regardless.

## What is now BUILT vs PENDING DATA
- **Built (this cycle):** corrected identification + renewal; sim validation; power/MDE; RCT-anchor plan;
  Hb validation pipeline; triangulation estimator; pre-registration; prior-art position (Bosch). All committed.
- **Pending the download only:** the actual numbers (Mg battery + Hb dual-stratum validation). Everything to
  turn those into a certified result is in place and auto-runs.

## Bottom line
The conceptual problem is largely solved *and correctly bounded*: we know exactly what the method can decide
(the threshold-policy ITT, precisely; the per-patient LATE, only weakly), what is novel (formal noise model +
renewal + trial-infeasible application), and what must still be shown (the real-data battery + the Hb-RCT
validation + the triangulation bounds). It is a valid, honestly-scoped method — not yet a certified one.
