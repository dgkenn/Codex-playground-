# IDEA DISCRIMINATOR — calibrated judgment for likely-winners vs obviously-bad ideas

**This is NOT a rigid pass/fail gate.** It is a discriminative aid: **rank candidate ideas by
win-likelihood, and reliably spot the *obviously bad* ones, before spending compute.** Use it as
judgment, not bureaucracy — a strong idea missing one feature can still be worth running if it has a
clever workaround. (Proof it's not a hard filter: masked-hypernatremia scored 7/7 and still nulled;
potassium-control scored 5/7 and won.)

**The point is to DEVELOP the ability, not apply a fixed rule.** It sharpens through calibration: for
every idea, jot a quick predicted win-likelihood (high/med/low), then compare to the actual outcome in
`FINDINGS_LEDGER.md`. Over cycles, that predicted-vs-actual record is what turns the features below into
real intuition (and reweights them — see the calibration note at the bottom).

Derived empirically from ~40 ideas run this session (~12 wins, ~25 nulls/demotions). Read alongside
`FINDINGS_LEDGER.md` (what's already done — do not repeat) and `LESSONS.md`.

## The winning template (what every durable win instantiated)

> **An established analytical/physiological MECHANISM + a GROUND-TRUTH REFERENCE in the same
> patients + a documented SUBGROUP DIFFERENCE in the upstream driver → differential
> misclassification at the MEASUREMENT/CLASSIFICATION level.**

Examples that won: indirect-ISE electrolyte-exclusion (Na/Cl↓, Ca↑) with blood-gas/ionized as the
reference and higher globulins in Black patients as the driver; muscle-mass → creatinine with the
proportional criterion as reference.

## The discriminating features (score each; higher total = more likely a winner)

**THE TWO STRONGEST SIGNALS — an idea missing either is *probably* bad; demand a clever workaround
before running it (down-weight heavily, don't reflexively kill):**
1. **Ground-truth reference in the same patients?** A second measurement method or gold standard
   (blood-gas vs chem; ionized vs total; adjudicated label). *This is the #1 discriminator — nearly
   every null this session died from its absence.* No clean "truth" ⇒ obviously-bad UNLESS there's a
   credible proxy/instrument (and even then, expect a hard road).
2. **Named mechanism predicting the DIRECTION?** A specific analytical/physiological reason the
   subgroup differs (not "maybe analyte X is biased"). Mechanism-first beats phenotype-first fishing.

**SUPPORTING SIGNALS — more of these = higher win-likelihood:**
3. **Documented subgroup difference in the upstream driver** (globulins, muscle mass, RBC lifespan,
   skin optics, body habitus…) — so the bias has a real cause.
4. **Novel** — not already published AND not a *statistical rescaling* of a finding we already have
   (see failure mode #4). Run the PubMed novelty screen; if the mechanism is textbook, only an
   unmined *subgroup/quantification/consequence* angle counts.
5. **Claim stays at the measurement/classification level** — differential misclassification, not a
   causal outcome. (Outcomes get confounded; note harm as a hypothesis only.)
6. **A quantitative mechanistic prediction exists** (dose-response slope, slope-ratio, monotone
   quartiles) that would be hard to fake. These are what survive red-team — e.g. the Na:Cl slope
   ratio = ion concentration ratio.
7. **Survives a 2-minute pre-mortem** of the standard attacks (below) on paper.

## The five failure modes that killed/demoted ideas (screen these out first)

1. **No ground truth** → collapses to noise/confounding. *(fluid responsiveness, MAP-proxy, troponin,
   ferritin — all lacked a clean reference.)*
2. **Already published** → the novelty screen catches it only if run FIRST. *(HbA1c, QTc, eGFR, TSH,
   ferritin-CRP, pseudohyponatremia.)*
3. **Decomposes into a known disparity + tiny residual** → run the Oaxaca / within-stratum
   decomposition mentally. *(sodium-glucose was 84% the known hyperglycemia disparity; troponin was
   just troponin-level.)*
4. **A statistical corollary of an existing finding** → if the "new" metric is a linear transform of
   something we already have, its regression z will MATCH the parent's. *(osmolar-gap z matched the
   sodium z to six decimals → zero new evidence.)* New content can only live where the DISTRIBUTION
   SHAPE matters (threshold crossings), not in a transform of the mean.
5. **Reaching for a causal/outcome claim** → confounding-by-indication + acuity confounding cap it at
   ~OR 1.35. *(cuff-MAP harm, fluid-vs-pressor, occult-vs-overt mortality.)*

## The pre-mortem attack list (run before, not after)

RTM / binning-a-difference-by-its-component (use Bland-Altman mean); composition-shift when widening a
pairing window (pin each input to its tight window); acuity confounding (never occult-vs-overt on
mortality — hold the true value fixed, test recognition); label-noise floor (compute the label's own
no-intervention test-retest before believing an ICC/AUROC); known-disparity decomposition; statistical
rescaling (compute the parent regression alongside); already-published; **baseline-offset direction**
(a threshold complement needs the raw analyzer offset — not just the subgroup differential — pointing the
masking way); **population≠patient-level** (a "sharper within-patient version" of a confirmed population
effect attenuates from individual-level noise — the fingerprint slope can be half the population slope).

## Exploitation moves on a CONFIRMED seam (high hit rate, incremental)

Once a bias is confirmed, these reliably win: **threshold complements** (a masking bias over-flags at
the other threshold — masked hypocalcemia ↔ false hypercalcemia; *but first check the baseline offset
direction — masked-hypernatremia nulled because chem Na over-reads*); **derived-quantity propagation maps**
(which formulas inherit vs cancel the bias — anion gap cancels, osmolar gap propagates); **specificity
controls** (a well-powered negative control that localizes the mechanism — bicarbonate, and the potassium
concentration-scaled near-zero); **cross-cohort mechanism replication** (SICdb protein dose-response);
**cross-analyte coordination** (the panel).

**Diminishing returns warning (from first gate use, 1 win / 3 depth ideas):** depth moves on a
*heavily-mined* seam increasingly CONFIRM the core mechanism but fail to EXTEND it, and the remaining wins
are negative controls (valuable, incremental). Judge the gate by **losers-not-run** (its cheap kill list —
~15 gate-failures avoided), not by hit rate on the few you pick. When depth stalls, **pivot compute to a
new (mechanism + ground-truth reference + subgroup driver) triple** — that is where fresh flagships live.

## Strategy: depth > breadth

Almost every win this session is a facet of ONE seam (electrolyte-exclusion). Depth on a confirmed
seam has a high hit rate; breadth across new analytes (cycles 9–11) yielded ~2–3 wins per 10, mostly
hardening the existing flagship. To find a *new* flagship, don't grind analytes — deliberately hunt for
new **(mechanism + ground-truth reference + subgroup driver)** triples with the winning structure.

## How to use (rank, don't filter)

1. Draft many candidates — cast wide.
2. **Score & RANK** each on the features above → a win-likelihood (high/med/low). Don't auto-drop; sort.
3. **Flag the obviously-bad** (missing a strong signal with no workaround; hits a pre-mortem failure mode;
   already-published; a statistical rescaling) — these are the cheap, confident kills.
4. Run the pre-mortem on the top-ranked survivors; verify the ground-truth reference actually exists.
5. Run the top few by likelihood (a med-likelihood idea with a cheap run + big upside can still be worth it —
   judgment, not a threshold).
6. **Record the PREDICTION** (your high/med/low) next to the outcome in `FINDINGS_LEDGER.md`.

## Calibration loop — how the ABILITY develops (the actual goal)

The discriminator is only as good as its calibration. Each cycle: log **predicted win-likelihood → actual
outcome**. Periodically review the record and ask which features actually separated wins from nulls, and
reweight:
- Confirmed strong so far: **ground-truth reference** (its absence predicted nearly every null);
  **sharp falsifiable quantitative prediction** (produced the cleanest wins *and* the cleanest, most
  informative nulls).
- Confirmed weak/overrated so far: a high feature-count alone (masked-hypernatremia 7/7 → null; the score
  is not the outcome). "Threshold-complement" and "sharper-within-patient" moves over-scored — they need the
  extra baseline-offset / population-vs-patient checks now folded into the pre-mortem.
- The record is small (n≈4 gate-scored so far). Treat the weights as provisional; the point is that they
  **improve every cycle** as predicted-vs-actual accumulates. That accumulation IS the developed ability —
  not this static list.
