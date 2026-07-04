# IDEA GATE — a pre-run screen to raise the win rate

Derived empirically from ~40 ideas run this session (~12 wins, ~25 nulls/demotions). Winners and
losers had distinct, learnable structure. **Score every candidate idea against this gate BEFORE
spending compute. Run only ideas that clear ~5/7 AND both hard gates.** Read alongside
`FINDINGS_LEDGER.md` (what's already done — do not repeat) and `LESSONS.md`.

## The winning template (what every durable win instantiated)

> **An established analytical/physiological MECHANISM + a GROUND-TRUTH REFERENCE in the same
> patients + a documented SUBGROUP DIFFERENCE in the upstream driver → differential
> misclassification at the MEASUREMENT/CLASSIFICATION level.**

Examples that won: indirect-ISE electrolyte-exclusion (Na/Cl↓, Ca↑) with blood-gas/ionized as the
reference and higher globulins in Black patients as the driver; muscle-mass → creatinine with the
proportional criterion as reference.

## The gate (score 0/1 each)

**HARD GATES — kill the idea if either is 0:**
1. **Ground-truth reference in the same patients?** A second measurement method or gold standard
   (blood-gas vs chem; ionized vs total; adjudicated label). *This is the #1 discriminator — nearly
   every null this session died here.* If there is no clean "truth" to measure the bias against, do
   not run it.
2. **Named mechanism predicting the DIRECTION?** A specific analytical/physiological reason the
   subgroup differs (not "maybe analyte X is biased"). Mechanism-first, never phenotype-first fishing.

**SOFT GATES — need ~3 of these 5:**
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

## How to use

1. Draft candidates. 2. Score each on the gate; drop anything failing a hard gate or <5/7.
3. Run the pre-mortem on survivors. 4. Verify the ground-truth reference actually exists in the data.
5. Run only the survivors. 6. After results, append the win/loss + why to the ledger to keep tuning the gate.
