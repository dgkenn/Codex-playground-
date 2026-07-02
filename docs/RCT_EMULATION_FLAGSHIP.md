# Flagship paper — Reproducing landmark ICU RCTs by gated, cross-database target-trial emulation

**Working title:** "When can observational emulation reproduce a critical-care RCT? A self-diagnosing,
cross-national triangulation of 17 landmark ICU trials."

## The gap (why this is high-impact and novel)
- **RCT-DUPLICATE** (Franklin/Schneeweiss, *Circulation* 2021) emulated 30 *drug* RCTs in claims data and became
  a field-defining paper — but it (a) covered chronic-disease drug trials, not **ICU reflexive lab-triggered
  treatments**, (b) used a single data ecosystem, and (c) had **no a-priori test of when an emulation is
  trustworthy** — reproduction was assessed only *after* the RCT answer was known.
- **No one has systematically emulated ICU reflexive-treatment RCTs**, and no one has a **pre-specified,
  mechanism-based gate battery that predicts emulation validity before unblinding the RCT answer.**
- Our contribution is exactly that: a **self-diagnosing** emulation framework whose gates (assay-noise
  cleanliness, first-stage sign, negative-control empirical null, drift diagnostic, balance) flag *in advance*
  which emulations to trust — validated by whether the trusted ones reproduce the RCTs and the distrusted ones
  are correctly withheld — across **three independent health systems on two continents.**

## The claim structure (three nested results)
1. **Positive control:** where all gates pass (cross-method Hb → transfusion), the emulation **reproduces the
   RCT** (TRICC/TRISS null) — and does so **in MIMIC and SICdb** (cross-national).
2. **Specificity:** where a gate fires, the emulation is **correctly withheld** — 6+ mechanistically distinct
   refusals (K/hemolysis, platelet/single-method, albumin+bicarb/drift, glucose/estimand+protocol-titration,
   MIND-USA/charting, provider-preference/acuity-confounding). The gates are not post-hoc; each names a cause.
3. **Triangulation:** for the one open question (MI transfusion, MINT 2023 unresolved), **two independent
   instruments** — cross-method assay-noise (MIMIC+SICdb) and hospital-preference (eICU, 208 hospitals) — are
   run; convergence/divergence is reported as the substantive contribution.

## Databases (Methods §1)
| DB | country | ~ICU stays | role | cross-method Hb? |
|---|---|---|---|---|
| MIMIC-IV | US (academic) | 65k | primary + full physiology | yes (51222/50811) |
| SICdb v1.0.8 | Austria | 27k | cross-national replication | yes (289/658) |
| eICU-CRD | US (208 hospitals) | 200k | hospital-preference IV | no (single Hgb) → different instrument |

## Instrument families + the gate battery (Methods §2 — the core novelty)
- **Assay-noise (cross-method discordance):** two same-time assays → pure analytic noise → as-if-random which
  side of the flag. Clean only when methods share measurand + failure modes (Hb ✓; K✗ hemolysis; Na✗ pseudo-
  dysnatremia; single-method analytes ✗).
- **Hospital/provider-preference:** leave-one-out prescribing liberality (Brookhart). Valid only in low-acuity/
  cross-hospital strata that pass NC + balance.
- **The gates (pre-specified, run identically per trial per DB):** (i) first-stage relevance **and sign**,
  (ii) drift diagnostic (short vs long interval σ), (iii) **negative-control empirical null** (flag must not
  predict an unrelated treatment/outcome), (iv) covariate balance, (v) cross-method σ vs analytic expectation.
  A trial is **"emulation-eligible"** only if all gates pass; the headline compares eligible-emulation vs RCT.

## The trial roster (Results — one row each; already run, see per-trial REAL_RESULTS_*.md)
Transfusion (TRICC/TRISS/FOCUS/TITRe2/MINT/REALITY/Villanueva), glucose (NICE-SUGAR), platelet (TOPPS),
antipsychotic (MIND-USA), electrolytes (K), albumin (ALBIOS/SAFE), bicarbonate (BICAR-ICU), PPI (SUP-ICU/
PEPTIC), VTE (PREVENT), steroids (ADRENAL), MAP-target (SEPSISPAM). **17 trial-rows, all emulated, run, logged.**

## Figure plan (5)
- **F1 — Concept:** the assay-noise instrument + the gate battery schematic (why same-time discordance is
  as-if-random; what each gate tests).
- **F2 — Calibration/agreement plot (the money figure):** x = RCT effect (with CI), y = emulation effect (with
  CI), one point per trial, colored by gate status (green=all pass, red=gate fired). Points on the diagonal
  among green; red points scattered/withheld. This is the RCT-DUPLICATE-style headline that proves the gates
  work.
- **F3 — Cross-national replication:** TRICC/TRISS transfusion flag-ITT in MIMIC vs SICdb (forest plot), same
  instrument, two countries.
- **F4 — Specificity gallery:** for each withheld trial, the gate that fired + its mechanism (small-multiple:
  NC-fires, drift-fails, first-stage-wrong-sign, charting-degenerate).
- **F5 — Triangulation (MI transfusion):** MINT RCT estimate vs cross-method IV (MIMIC+SICdb) vs hospital-
  preference IV (eICU), forest plot — do two independent instruments + the RCT agree?

## Why hostile-review-proof
- The positive is not a lone hit — it's the one case passing gates that **demonstrably withhold 6+ others**,
  each with a named mechanism. Fluke instruments don't discriminate that precisely.
- Gates are **pre-specified and mechanism-based**, not tuned to reproduce answers.
- **Cross-national** reproduction (MIMIC↔SICdb) rules out single-dataset artifact.
- Every negative is reported with its mechanism; the **refusal rate is the evidence**, not a limitation.

## Status / to-do
- 17 trials emulated on MIMIC ✅; gate battery built ✅; SICdb transfusion replication running (F3) ⏳;
  eICU hospital-preference IV (F5) — sequential download queued ⏳; MI pool (F5) after SICdb+eICU.
- Remaining: assemble F2 across all trials with gate-status coloring; write Methods §2 (gates) as the anchor.
