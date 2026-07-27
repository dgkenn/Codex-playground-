# Cycle 8 — Regression-discontinuity design (user-chosen lever). Design sound; first RDD target blocked on treatment capture.

**Why RDD:** the one structurally-strong CAUSAL design left. A sharp, protocolized clinical threshold acts as
quasi-randomization: running variable = a lab value; treatment jumps at the threshold; outcome discontinuity
at the threshold = the causal effect. Far stronger identification than the weak IV that capped cycle 6, and
it targets thresholds whose benefit is genuinely unproven (novel causal info).

## First target attempted: glucose → insulin-INFUSION (eICU, 207 hospitals)
Rationale: post-NICE-SUGAR, when to start an insulin drip near glucose ~180 is not cleanly settled causally.
Data confirmed present: eICU `lab` has abundant glucose (`bedside glucose` + `glucose`); `infusionDrug`
(cached) has Insulin infusions; `patient` (cached) has mortality + `hospitalid`.

**Make-or-break FIRST STAGE (validate the treatment discontinuity before the outcome RDD) — FAILED for this
target.** Single streaming pass over eICU `lab` (disk-sparing, bin-aggregated), 563k glucose decision-points:
**P(insulin infusion within 3 h of a glucose) ≈ 0 across ALL glucose bins (60–360 mg/dL).** Cause is
treatment CAPTURE, not absence of an effect:
- eICU insulin **infusions** appear in only 14,313 / 200,860 stays (7%); `infusionDrug` is known-incomplete
  (many hospitals don't chart infusions), and ICU hyperglycemia is mostly managed with **subcutaneous**
  insulin, which is not in this table.
- Infusion starts that do exist are often early (DKA protocols at admission), so few glucose values fall in
  the 3 h *before* a drip start.
→ The glucose→insulin-**infusion** exposure is too sparse/ill-timed in eICU for a valid first stage.

## Also: severe infrastructure friction (honest note)
The eICU `lab` table (~40M rows, ~2 GB) streamed through the agent proxy is slow and drops intermittently;
disk-sparing streaming required checkpointing reducers and repeated relaunches. This is a real bottleneck for
any full-`lab` RDD and argues for a one-time compact filtered extract (glucose/electrolyte rows only) rather
than repeated full streams.

## Concrete path (next, if RDD continues)
Pick a threshold-treatment that is DENSELY and RELIABLY captured:
1. **MIMIC-IV `inputevents`** charts insulin AND electrolyte repletion (K/Mg/phosphate) densely with times →
   a proper first stage is constructable. Electrolyte repletion at protocol thresholds (e.g., replace Mg<2.0,
   phosphate<2.0, K<4.0) is common, sharp-ish, and has essentially NO outcome evidence → genuinely novel RDD.
2. **RBC transfusion at Hb 7** — the sharpest guideline threshold and cleanly captured (procedures/inputevents),
   but the answer is largely known (TRICC/TRISS) → best as an RDD *methods validation*, not a winner.
3. Extract glucose/electrolyte lab rows once to a compact file (disk-modest) to avoid repeated 40M-row streams.

## Status
RDD design validated and correct; first candidate target (glucose→insulin-infusion, eICU) failed its
first-stage data-capture gate — logged, not forced. The RDD lever remains live via a densely-captured
threshold-treatment (MIMIC electrolyte repletion is the most novel next target). See LESSONS.md.
