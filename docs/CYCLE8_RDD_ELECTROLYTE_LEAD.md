# Cycle 8 (cont.) — RDD of reflexive electrolyte repletion → mortality: the session's FIRST GENUINE LEAD

**Design.** Regression-discontinuity on a ubiquitous, essentially evidence-free ICU practice: clinicians
replete magnesium when serum Mg < ~2.0 and potassium when K < ~3.5. The lab value is the running variable;
repletion jumps at the threshold; a discontinuity in outcome at the cutoff = the causal effect of repletion.
Data: MIMIC-IV (disk-sparing) — running variable + outcome fully CACHED (labevents Mg 50960 / K 50971;
admissions mortality), treatment (first stage) from a streamed compact repletion extract (inputevents
itemids KCl 225166, MgSO4 222011/227523, KPhos 225925).

## First stage — VALID (treatment jumps at the threshold)
Streamed inputevents (disk-sparing filter, ~partial), P(repletion ≤6h) by lab-value bin:
- **Magnesium: sharp ~4× jump** across Mg 1.8→2.0 (P 0.024 → 0.006 → 0.002). Threshold behaviour ≈ 2.0.
- **Potassium: graded**, strongest below K ~3.5–3.8 (fuzzier than Mg).
(P magnitudes are low because repletions were ~40% loaded; the *shape*/discontinuity is what validates the RDD.)

## Reduced form (outcome) — well-powered NULL for mortality (fully cached; treatment-independent)
Per-admission FIRST Mg / K value vs in-hospital mortality; local-linear RD at the cutoff (n=176k Mg / 191k K):
- **Mg @2.0:** mortality just below 0.0195 vs above 0.0201 → **RD −0.0006**; binned mortality smooth through 2.0.
- **K @3.5:** just below 0.0242 vs above 0.0247 → **RD −0.0005**; smooth monotonic decline, no jump at 3.5.
→ **No detectable causal effect of threshold-triggered electrolyte repletion on in-hospital mortality.**
A de-implementation / low-value-care signal on a reflexive, evidence-free practice affecting millions.

## Honest caveats (must resolve before this is a WINNER — the hostile-review gate)
1. **Digit heaping / discrete running variable.** Mg is reported to 0.1 (density check: n=0 in [1.9,2.0),
   mass at 1.8/2.0/2.1). A discrete/heaped running variable needs honest discrete-RDD inference
   (Kolesár–Rothe), NOT naive continuous local-linear; and manipulation/bunching at the cutoff must be ruled out.
2. **Wrong primary endpoint.** Mg/K are repleted to prevent ARRHYTHMIA (esp. atrial fibrillation), not to
   reduce mortality — a mortality null is expected and modest. The compelling test is arrhythmia; but a clean,
   time-resolved arrhythmia endpoint needs chartevents rhythm data (not cached) — diagnoses_icd AF codes are
   admission-level (no timing) and ascertainment-confounded.
3. **Running-variable choice.** First-Mg-per-admission is a proxy for the decision point; many repletion
   decisions key off later/lowest values. Sensitivity to the decision-point definition is needed.
4. **Selection into being measured** (Mg is checked more in sicker patients) — RDD conditions on measurement,
   but the local comparison's external validity is to measured patients.
5. **No external validation yet** — eICU (207 hospitals) has Mg/K labs + repletion (medication/infusion) for
   replication; the eICU `lab` table streaming is the bottleneck (flaky proxy, 40M rows).

## Looser vs more-aggressive repletion — is aggressive beneficial or is looser non-inferior? (user question)
Two complementary analyses (MIMIC, cached):
- **Multi-threshold RDD:** the reduced-form mortality curve is a smooth U-shape across Mg 1.5→2.3
  (0.029 → 0.021 [min ~2.0] → 0.032) with **NO discontinuity at any candidate threshold**. The higher
  mortality at low Mg is confounding (low Mg = sicker), and it is *smooth* — no jump where repletion kicks in.
  → no evidence of a mortality benefit at any threshold, i.e., more-aggressive (lower-threshold) repletion
  shows no discontinuous benefit.
- **Practice-variation quasi-IV by CARE UNIT — CONFOUNDED (a methods lesson, not a clean answer).** Units
  vary widely in aggressiveness (Neuro Intermediate 12% → CVICU 55%). But the estimate FLIPS: crude,
  aggressive units have LOWER mortality (7.4% vs 10.3%); age+Mg-adjusted, HIGHER (+0.156). Cause: the
  aggressive units are low-risk **surgical/cardiac** units (CVICU 3.6% mortality, TSICU) while loose/high-risk
  units differ on everything. **Care-unit assignment violates the exclusion restriction (unit = case-mix),
  so it is NOT a valid instrument here.** A cleaner test needs WITHIN-unit provider-preference variation
  (order_provider_id / caregiver_id) or the RDD (which is the clean, null evidence).
- **Honest answer:** on the clean (RDD) evidence, **looser repletion appears NON-INFERIOR on mortality** — no
  detectable benefit of repletion at the margin or at any threshold. The unit-level practice-variation design
  is too case-mix-confounded to confirm it. Mortality is not the mechanistic endpoint (arrhythmia is), so the
  strongest version still needs the arrhythmia outcome + a provider-preference IV + eICU replication.

## Hardening (robustness of the null)
- **Higher-acuity ICU subgroup (n=37,077, 10.3% mortality):** mortality flat across Mg 1.5–2.1; RD at 2.0 =
  **−0.0016** ≈ 0. The mortality null holds where repletion could plausibly matter most → robust, not a
  low-acuity power artifact.
- **Atrial fibrillation (mechanistic endpoint; crude, dx-code, ascertainment-caveated):** AF rate rises
  *smoothly* with Mg (confounded by renal function), with **no discontinuity at 2.0** (RD −0.033; AF is
  actually lower below the cutoff — opposite to a repletion benefit). Suggestive of no AF benefit, but needs
  a TIME-RESOLVED AF endpoint (chartevents rhythm / new-onset after the Mg) to be clean.

## Status / verdict
**The first genuinely promising lead of the search:** a valid RDD first stage + a well-powered mortality null
on an evidence-free ubiquitous practice = a real de-implementation candidate. NOT yet a confirmed winner —
it needs discrete-RDD inference, the arrhythmia endpoint, decision-point sensitivity, and eICU replication.
Unlike the prior cycles (incremental-null / weak-instrument / capture-fail), this one has a valid design AND
a defensible, novel, externally-validatable finding to develop. Next: harden per the caveats above.
