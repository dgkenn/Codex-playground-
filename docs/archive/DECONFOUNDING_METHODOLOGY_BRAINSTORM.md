# The big play: a broadly-applicable method to defeat confounding-by-indication for reflexive care

## The universal obstacle (demonstrated, not assumed)
Reflexive lab-/severity-triggered treatments (electrolyte repletion, PPI, transfusion, benzos, bicarb, ...)
share one structure: **treatment is a near-deterministic function of a time-varying severity signal, and that
same signal drives the outcome.** We proved every standard design breaks on it for Mg repletion:
- **RDD** — no first-stage discontinuity (smooth dose-response). Invalid.
- **Provider-preference IV** — strong first stage (+0.41) but exclusion restriction fails (provider habit ~
  care intensity); LATE +0.16 (absurd) overall, null only in low-acuity elective strata.
- **Within-patient fixed effects** — +7.3 d LOS, +0.069 AF (the repleted admission is the sicker admission);
  controls stable traits, NOT time-varying acute severity. Invalid.
- **IPTW target-trial** — RR 4.17, negative-control fails. Invalid.
Solving this ONCE, broadly, pays dividends across every de-implementation question → a top-tier METHODS play.

## Candidate novel methodologies (ranked)
### 1. ASSAY-NOISE INSTRUMENT ("the lab lottery") — most novel, broadly applicable
Insight: reflexive treatment fires when a MEASURED lab crosses a flag, but measured = true + assay noise
(analytical+biological CV ~5–10%). Two patients with IDENTICAL true severity but different noise draws get
different treatment — one flagged, one not. **The noise is exogenous to prognosis** → among patients near the
flag, treatment has a random component driven by assay error = a valid instrument ("noise-compliers").
- Identification: measured = true + ε (Var(ε) estimable from serial/paired draws — MIMIC has serial labs!);
  P(treat | true) smooth but P(treat | measured) jumps at the flag; the noise-induced gap identifies a LATE.
- Applies to EVERY lab-flag-triggered treatment (electrolytes, glucose→insulin, Hb→transfusion, INR, ...).
- Novelty: RDD-with-measurement-error exists (Pei–Shen, Battistin), but framing ASSAY NOISE as the
  de-confounding instrument for reflexive-care de-implementation appears fresh. **Prototype first.**

### 2. PROXIMAL CAUSAL INFERENCE (double negative controls) — most rigorous, hot, under-applied
Tchetgen-Tchetgen (2020): with a negative-control EXPOSURE and a negative-control OUTCOME that are proxies of
the unmeasured confounder, one can identify the causal effect DESPITE unmeasured confounding via a
"confounding bridge." Severity is the unmeasured confounder; routine labs/vitals/trajectory are rich proxies.
- Mathematically identified; broadly applicable; essentially unused in de-implementation.
- Novelty: systematic application of proximal CI to reflexive-treatment de-implementation = strong applied-
  methods paper on its own.

### 3. CONVERGENT PARTIAL IDENTIFICATION (honest bounds from oppositely-biased designs)
Provider-IV is biased toward HARM (habit ~ intensity, +); construct a design biased toward BENEFIT (−) and
BRACKET the truth (Manski-style bounds). Report the INTERVAL. If the bracket excludes clinical benefit →
de-implementation supported with honest, reviewer-proof uncertainty. Turns "triangulation" into formal bounds.

### 4. PROGNOSTIC-TWIN + EMPIRICAL CALIBRATION (the deployable stack)
Best-possible ML prognostic score (all pre-treatment labs/vitals/trajectory) → match treated/untreated on
predicted prognosis → estimate → CALIBRATE with ~100 negative-control outcomes (Schuemie/Madigan) to correct
residual bias and produce an honest CI. Combines existing tools into a rigorous, portable pipeline.

### 5. RCT-ANCHORED METHOD VALIDATION (the program's keystone)
Run the RESTRAINT trial for ONE question → use it as GROUND TRUTH to benchmark which observational method
(1–4) recovers the trial estimate → the validated method then TRANSPORTS to the many de-implementation
questions where trials are infeasible. (The RCT-DUPLICATE paradigm, purpose-built for de-implementation.)

## The high-impact framing (a program, not a paper)
**"Deconfounding reflexive care": a unified de-implementation causal-inference framework** = assay-noise IV +
proximal inference + convergent bounds, VALIDATED against a purpose-built RCT, DEPLOYED across a portfolio
(Mg/K, PPI, benzo, bicarb, ...). Methods paper (framework) + demonstration portfolio + RCT = the dividend-
paying play the user identified. Venues: methods (JASA/Biometrics/AJE/Stat-in-Med) + clinical (JAMA/NEJM).

## Portfolio status (from the novelty screen)
- DROP (RCT-settled): RBC transfusion (TRICC), IV albumin (SAFE/ALBIOS), antipsychotics-for-delirium (AID-ICU/MIND).
- KEEP but confounding-limited (need the new method): Mg/K repletion, PPI/H2 prophylaxis, benzodiazepines,
  sodium bicarbonate, corticosteroids, VTE-prophylaxis intensity, opioid intensity.
- Cleanest indication-independent cohorts (per screen): benzodiazepines-for-sleep, opioid-for-post-op-pain.

## Deep-dive plan
1. Methods literature scan (delegated): novelty of assay-noise-IV + proximal-CI in this context; prior de-
   implementation-methods work; identify the exact open gap.
2. PROTOTYPE the assay-noise IV on Mg (serial labs → estimate assay CV → noise-IV LATE) — the make-or-break.
3. Prototype proximal CI on Mg (pick neg-control exposure + outcome; estimate bridge).
4. Convergent-bounds synthesis across provider-IV + assay-noise + proximal.
5. If any recovers a credible null with a valid design → that + the RESTRAINT RCT = the flagship program.
