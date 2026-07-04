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

**THE THREE STRONGEST SIGNALS — an idea missing any is *probably* bad; demand a clever workaround
before running it (down-weight heavily, don't reflexively kill):**
1. **Ground-truth reference in the same patients?** A second measurement method or gold standard
   (blood-gas vs chem; ionized vs total; adjudicated label). *This is the #1 discriminator — nearly
   every null this session died from its absence.* No clean "truth" ⇒ obviously-bad UNLESS there's a
   credible proxy/instrument (and even then, expect a hard road).
2. **Named mechanism predicting the DIRECTION?** A specific analytical/physiological reason the
   subgroup differs (not "maybe analyte X is biased"). Mechanism-first beats phenotype-first fishing.
3. **Does the DRIVER have the needed distribution IN THE ACTUAL COHORT?** *(added from calibration — this
   check would have correctly down-ranked BOTH of the discriminator's HIGH misses.)* A 2-minute check
   before scoring: `describe the driver in the real data`. It needs (a) **dynamic range** for a
   dose-response — COHb→pulse-ox nulled because ICU COHb is uniformly low (max 7%, severe CO triaged
   elsewhere); and (b) **variance BY SUBGROUP** for a disparity claim — glucose-meter's racial angle died
   because ICU anemia is race-invariant (Black=White Hct). A driver documented in the *general population*
   is NOT enough; the *cohort* can flatten it. (The thrombocytosis WIN had a driver with abundant range.)

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
- The record is small; treat weights as provisional; they **improve every cycle** as predicted-vs-actual
  accumulates. That accumulation IS the developed ability — not this static list.

### Calibration log (predicted → actual; append every cycle)
| Idea | Predicted | Actual | What it taught |
|------|-----------|--------|----------------|
| Potassium concentration-control | HIGH | WIN | sharp near-zero prediction + clean reference → cleanest wins |
| Masked-hypernatremia | HIGH | NULL | feature-count ≠ outcome; check baseline analyzer-offset direction |
| Na+Cl within-patient fingerprint | MED | NULL | population dose-response ≠ patient-level (individual noise attenuates) |
| Glucose-meter Hct | HIGH | PARTIAL | driver must VARY BY SUBGROUP in the cohort (ICU anemia race-invariant) |
| COHb → pulse-ox | HIGH | NULL | driver must have RANGE in the cohort (ICU COHb uniformly low) |
| MetHb → pulse-ox | MED-HIGH | mech-only | extreme-tail power (MetHb≥5% n=28) |
| Thrombocytosis → pseudohyperK | MED-HIGH | WIN | driver with abundant range + clean reference → hit |

**Pattern after 7 scored:** the two HIGH *misses* (glucose, COHb) and the MED-HIGH *win* (thrombocytosis)
are fully explained by signal #3 — the driver's in-cohort distribution. That check is now promoted to a
strong signal. The two features that keep predicting clean results remain: **ground-truth reference** +
**sharp falsifiable prediction**. Biggest recurring calibration error: over-scoring a driver documented in
the general population without checking its distribution in the actual cohort.

### Calibration log — cycle-12 NEJM/Nature-tier slate (CC/anesthesia-weighted; predictions recorded BEFORE running)

Goal: 5 NEJM/Nature-tier ideas we have data for, bonus for anesthesiology/critical care. Not restricted to
the measurement-bias template, but the 3 strong signals still rank them. The in-data-reference + driver
checks were run FIRST (a 2-min grep) → two cheap kills before any compute (the discriminator working).

| # | Idea (CC/anesth) | Ground-truth ref (in data?) | Mechanism→direction + consequence | Predicted | Actual |
|---|------|------------------------------|-----------------------------------|-----------|--------|
| C12-1 | **Occult hypoxemia → SpO₂/FiO₂ → ARDS-Berlin & SOFA-resp racial misclassification** (propagation-map; CC) | ✅ PaO₂/FiO₂ (ABG) vs SF surrogate | pulse-ox over-reads in dark skin → SF over-reads → under-classifies ARDS severity / under-scores SOFA-resp → trial/ECMO/triage inequity | **HIGH** | **WIN (cleared gate) — n=104,696; SF over-read +6.87; ARDS under-class OR 1.43–2.00; SOFA-resp OR 1.66; ALL survive subject-clustering; robustness passes; NARROW-BUT-NOVEL (fills Erlebach 2025's un-assessed race gap); tier JAMA-IM/AJRCCM/Lancet-Resp; eICU external validation downloading** |
| C12-2 | **Pre-analytic false hyperlactatemia (blood-gas vs central-lab lactate) → Sepsis-3 mis-triage** (CC) | ⚠️ both itemids exist BUT chem lactate 53154 = only 104 rows/93 pts; **1 paired patient** at ±60min | tube glycolysis + transport delay inflates central lactate → false lactate>2 → spurious sepsis-bundle/ICU triage; driver = delay (structural/site, confirm race variance) | **MED-HIGH** | **NULL — infeasible (reference not co-ordered at scale)** |
| C12-3 | **False hyperkalemia (chem vs bg K) → differential emergency hyperK TREATMENT → iatrogenic hypoglycemia** (consequence of doc 02; CC) | ✅ blood-gas K 50822 (n=26,143 pairs) | pseudohyperK triggers insulin/dextrose → hypoglycemia, disproportionately in Black patients (2.4× false-hyperK, doc 05); the "so what" for potassium | **MED-HIGH** | **PARTIAL — action-link strong (chem K OR 2.34 holding true K fixed, p=1.7e-61) + 2× exposure disparity replicates; terminal harm cell EMPTY (0/4), same selection wall as calcium workup** |
| C12-4 | **Perioperative KDIGO-creatinine muscle-mass AKI misclassification** (INSPIRE surgical cohort; anesthesia) | ✅ creatinine + surgical AKI; external-validate the MIMIC survived finding (ledger 7d) | absolute-criterion AKI alerts under-detect in low-muscle/female → perioperative AKI under-recognition | **MED** | _queued_ |
| C12-5 | **SOFA/APACHE measurement-artifact decomposition → crisis-triage equity** (CC) | ◐→❌ resp=PF (clean); **renal=NO ref (cystatin C absent from MIMIC, mGFR absent)** | oppositely-signed subscores (resp under-scores, renal over-scores) self-cancel → total-recalibration insufficient | **MED** | **NOVEL-BUT-INFEASIBLE — NARROW-BUT-NOVEL framing confirmed, but renal arm has no in-data ground truth → downgrade to a reconciliation folded into C12-1's discussion (SOFA-renal ablation + eGFR literature), not a standalone ground-truthed paper** |

**Killed cheaply (discriminator, no in-data ground-truth reference):** ionized-vs-total magnesium (only total
Mg 50960); free/bioavailable vitamin D by race (only total 25-OH 50853). **Deprioritized:** Friedewald
calc-vs-measured LDL (refs exist 50905/50906 but ICU lipids are sparse/non-decisional — wrong context).

**Running C12-1 (HIGH) + C12-2 (MED-HIGH) now; C12-3/4/5 queued (C12-5 pending a novelty check vs Ashana).**
Predictions locked; actuals + "what it taught" appended after each gate — the self-learning step that sharpens
the propagation-map and pre-analytic sub-templates.

**STRATEGIC INSIGHT after cycle-12 (the highest-value pattern this session):** the **propagation-map into a
decision-score** sub-template is the highest-hit, lowest-confound idea shape. C12-1 (occult hypoxemia → SF →
ARDS/SOFA) WON cleanly; the earlier osmolar/anion-gap propagation work and the calcium-formula miscalibration
are the same shape. Why it wins where harm-chains stall: the endpoint is the **misclassification of a formula/
score that itself drives the decision** (ARDS trials, ECMO, SOFA triage, transplant eligibility) — so you never
need the elusive terminal-harm cell, and you dodge the paired-reference selection wall (see LESSONS). **Recipe:
take a bias already externally established (occult hypoxemia, indirect-ISE displacement, globulin binding), find
a consequential FORMULA/SCORE that consumes the biased input, and quantify the racial misclassification of the
score at matched TRUTH.** Prefer this over "does the artifact cause a downstream bad outcome." Also calibrated
this cycle: **tier honesty** — a clean, novel propagation finding is JAMA-IM/AJRCCM/Lancet-Resp tier, not
automatically NEJM/Nature; the discriminator should predict *tier*, not just win/loss (C12-1 = WIN but
specialty-top, not NEJM-first).

### Fresh propagation-map batch (free-endpoint focus; predictions BEFORE gate)
After the decision-tool cycle (all walled) + vancomycin (titrated-endpoint NO-GO), pivoted back to the winning
template with the FULL checklist applied upfront (ground-truth ref + FREE untitrated endpoint + fresh mechanism +
co-occurrence feasibility + magnitude-plausible + novelty + external-validatable):
| # | Idea | Free endpoint | Predicted | Actual |
|---|------|---------------|-----------|--------|
| T1 | Temperature-SITE bias (core vs peripheral) → missed fever/SIRS/sepsis flag | fever/SIRS classification | **MED-HIGH** | _gating_ |
| H1 | HbA1c RBC-lifespan (CKD/anemia/transfusion) → diabetes MISDIAGNOSIS | ≥6.5% diagnostic label | **MED-HIGH** | **NO-GO** — novelty CROWDED (textbook + a case report of the exact misclassification, Foley 2026); the CLEAN reference (fructosamine/GA) = 0 rows in MIMIC → reference collapses to stress-confounded in-hospital glucose; magnitude split (linear undershoot +0.2pp / stratified overshoot 1–2pp) = confounded-reference fingerprint |
| T3 | Occult hypoxemia → NEWS/MEWS escalation under-trigger (lower-acuity = headroom, fixes C12-1's ICU-no-headroom failure) | ward escalation trigger | MED (ward-data feasibility risk) | _queued_ |
| T4 | Sedation-suppressed GCS → falsely-poor neuro-prognosis/WLST | prognostication | MED (high-impact, confounded) | _queued_ |
| T5 | Albumin-hidden high-AG acidosis → missed DKA/acidosis flag | acidosis/DKA classification | MED (adjacent to null AG-by-race) | _queued_ |

Note: T3 is the sharpest strategic idea — it re-tests the C12-1 propagation in the setting where it SHOULD work
(floor/ward patients have classification headroom; the ICU didn't), with a FREE endpoint (escalation, not a
titrated score). Gate it after T1/H1.

**C12-5 actual → NOVEL-BUT-INFEASIBLE. CALIBRATION REFINEMENT (novelty ≠ feasibility; check the reference for
EVERY arm):** the SOFA oppositely-signed-decomposition passed the novelty screen (NARROW-BUT-NOVEL — Ashana/
Miller are total-score only; the self-cancellation framing is unpublished) but died on the FEASIBILITY of its
RENAL arm: cystatin C is entirely absent from MIMIC and measured GFR does not exist, so "creatinine over-scores
renal organ failure at matched true GFR" has no in-cohort ground-truth reference. A multi-arm idea needs signal
#1 satisfied on EACH arm, not just the headline one — the respiratory arm's clean PF reference masked that the
renal arm had none. Add to the pre-run checklist: for a decomposition/multi-component idea, verify a ground-truth
reference for every component before scoring the whole. (Prior-art note: Gadrey 2023 PMID 36699241 already showed
occult-hypoxemia SOFA-resp under-scoring in Black patients — cite it in C12-1; C12-1's ARDS-Berlin + Erlebach-gap
framing remains distinct.)

**C12-2 actual → NULL (infeasible). CALIBRATION REFINEMENT to signal #1 (ground-truth reference):** an itemid
EXISTING is not the same as the two methods being CO-ORDERED in the same patients at scale. Chem lactate (53154)
and blood-gas lactate (50813) both exist, but they serve disjoint clinical contexts (rare floor chemistry order
vs high-volume arterial POC) → only 1 paired patient. The 2-minute feasibility grep must now count the
**co-occurrence of the paired methods within the pairing window**, not just confirm both itemids are non-empty.
Same failure class as the eICU medication table (variable conceptually present, not populated for the design).
Add to the pre-mortem: *"paired-reference co-occurrence count ≥ target N?"* — a cheap kill that would have caught
this before compute. C12-3 substituted (its potassium pairing is already validated at n≈20k, doc 02).
