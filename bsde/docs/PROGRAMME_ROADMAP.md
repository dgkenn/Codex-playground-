# Programme roadmap — the five challenges after that, and the three that run beside them

*Written 2026-08-03, at 131 registered experiments. Supersedes nothing; `QUEUE.md` remains the working
backlog and this is the frame it sits in.*

The three original challenges (A: discover something new about consciousness on EEG; B: network measures
predicting BCI performance; C: a depth marker) are necessary and not sufficient. Two further challenges
are needed for a top-tier clinical claim or a product, and **both are contingent on A/B/C producing a
marker first**. Three further tracks are NOT contingent, run in parallel from today, and are here because
each is already costing results by its absence.

---

## CONTINGENT — D and E, which need a marker before they can start

### Challenge D — Calibration and transport

**Transport failure is this programme's central finding and we keep filing it as a caveat.**

| where | what happened |
|---|---|
| E131 | Two BCI cohorts, **disjoint** working predictors: `ge_norm`/`iaf` in Stieger, `smr`/`alpha_prom` in Dreyer, nothing in both |
| E123 | E43's muscle association did not survive VitalDB frontal → Fpz-Cz/Pz-Oz; it killed the experiment |
| PK validation | Same model: per-case R² **0.9990**, cross-patient MDAPE **54.9 %** |
| E129 | Succeeded *precisely* where the construct matched Blankertz's, failed where it did not |

That is one phenomenon seen four times, with a candidate rule attached: **transport succeeds when the
construct matches and fails when it does not, and construct match is specifiable in advance.** Formalised
and tested *prospectively* that is a methods contribution which explains a literature-wide replication
failure rather than adding one more measure to it.

> ### THE RULE WAS TESTED PROSPECTIVELY AND IT IS REFUTED — E160 and E162, 2026-08-01
>
> `CHALLENGE_D_PREREGISTRATION.md` committed the forward prediction while the extraction was still
> streaming: five of six axes mismatched, therefore **out-of-bag rho below +0.25**. The DOSE-I exposure
> ladder carried to 123,728 RASS observations from 4,000 MIMIC-IV ICU stays reproduces **to within 0.01 at
> every rung** — L0 +0.1872 against +0.1755, L2 **+0.4293** against +0.4263, L0→L2 gain +0.2421 against
> +0.2508. Both the primary and the sharper secondary fail.
>
> Two alternative explanations were tested before the verdict was allowed to stand. **Time is refuted**
> (`hours_in` alone +0.0695, and it adds nothing to the model). **Clinical intent looked decisive and was
> not**: the most-recent sedation goal correlates with the *previous* RASS in the same stay at +0.5549, so
> it is a collider — conditioning on it drags the cumulative-dose rung from +0.19 to +0.55 by importing the
> outcome. Adjusting instead for the stay's **first** charted goal, which is near pre-exposure, leaves the
> ladder unchanged at L2 **+0.4289**, gain +0.2330 (E162).
>
> **So a pharmacology model built for bolus propofol in day-case endoscopy, scored against a 1–5 observer
> scale over twenty minutes, transports essentially intact to multi-drug infusion in critically ill ICU
> patients scored on RASS over days.** The paragraph above is retained because it is what the programme
> believed and why Challenge D was posed, but the rule it proposes does not survive its first forward test
> and must not be cited as a finding. What the four retrodicted observations have in common is something
> narrower than "construct match", and naming it is open work.
>
> Full record in `CONSOLIDATION_2026_08_01.md` §4.

**The rule is currently a RETRODICTION over four observations.** `CLAUDE.md`'s cadence section is explicit
that a finding which explains the existing set is worth little until it makes a falsifiable forward
prediction. So D's first act must be to state, in advance, which of a set of untested cohort pairs will
transport — and then be wrong or right.

The calibration half has never been touched. **Every result in this project is rank-based.** Rule 15 says
discrimination without calibration is half a result and the missing half is the half clinicians use, and we
have produced zero calibrated outputs. A monitor emits a number that must mean the same thing in an
80-year-old and a 30-year-old. E109 measured BIS degrading with age (+0.2592 [+0.1367, +0.3761]) — a wedge,
but only if ours demonstrably does not, which needs calibration slope and intercept per stratum, not AUC.

For a product this is not optional: substantial equivalence against the BIS predicate requires performance
across the intended population, and a marker needing per-site recalibration is not a device.

**D NOW HAS DATA — MIMIC-IV, confirmed 2026-08-03 (investigator's suggestion).** Challenge D does not
need EEG, which I under-weighted: the transport test is the DOSE-I pharmacology model carried to a
different population, drug set and scale. `mimiciv/3.1/icu/` is ACCESSIBLE and carries every part:

| itemid | label | table | why it matters |
|---|---|---|---|
| 228096 | Richmond-RAS Scale | chartevents | the non-EEG state measure |
| **228299** | **Goal** Richmond-RAS Scale | chartevents | **the clinician's TARGET depth** |
| 222168 | Propofol | inputevents (mg) | infusion — the exact input `infusion_basis` was built for |
| 226224 | Propofol Ingredient | ingredientevents | ingredient-level dosing |
| 221668 / 221712 / 221744 / 225150 | midazolam, ketamine, fentanyl, dexmedetomidine | inputevents | multi-drug, so the interaction model is testable |

This is the **forward** prediction D was told it must make rather than the retrodiction it started as:
DOSE-I is bolus propofol mono-sedation against MOAA/S over minutes; MIMIC is multi-drug infusion against
RASS over days. If the construct-match rule is right, it should say in advance whether the pharmacology
arm transports — and E122 measured what there is to transport (out-of-bag rho 0.4595).

**`Goal Richmond-RAS Scale` is the item to notice.** E127 found that E126's apparent hysteresis was
confounding by indication — the residual LEADS the direction, because clinicians withhold drug from a
patient who looks deeper than expected. A recorded TARGET depth is the variable that separates
"clinician responding to observed state" from "drug effect", which DOSE-I could not do at all. **The
confound that killed E126 is directly addressable here.**

eICU-CRD 2.0 (33 tables) is also accessible as a second transport cohort.

### Challenge E — an endpoint a patient cares about, in the shadow of ENGAGES

Nothing we have is top-tier, because "tracks MOAA/S better than pharmacology predicts" is an intermediate
— the argument `DEPTH_TARGET_STRATEGY.md` made against BIS applies to us.

**ENGAGES makes this harder than "go and get an outcome", and that is the opportunity.** Wildes et al.,
JAMA 2019 (PMID 30721296, verified from the MEDLINE record): delirium **26.0 %** in the EEG-guided arm
against **23.0 %** usual care, difference **+3.0 % [−2.0 %, +8.0 %]**, P = .22. Negative, and directionally
the wrong way. The intervention worked *mechanically* — the guided group received less anaesthetic (0.69
vs 0.80 MAC) and **half the suppression time (7 vs 13 min)**. The thing everyone assumed was causal was
successfully halved and the outcome did not move. ENGAGES-Canada (Deschamps, JAMA 2024, PMID 38857019)
repeated it.

Three readings, and they are distinguishable:

1. **Suppression is not causal** — a marker of vulnerable brains, not a cause of injury. Fritz 2020
   (PMID 32032096) is a mediation analysis pointing this way.
2. **Suppression is the wrong target** — the right one is something else in the EEG that guided care did
   not change.
3. **The population was wrong** — benefit concentrated in a subgroup the trial diluted.

**Reading (2) is the one that would justify this programme, and E122 is the first result pointing at it:**
the EEG carries state information pharmacology cannot predict, at every rung of the ladder. If that
*residual* — not suppression — predicts delirium, then ENGAGES failed because it titrated to the wrong
feature. That is the shape of a top-tier claim.

Feasibility: I-CARE is already in this repo with hard outcomes (30-day death, CPC). VitalDB's outcome
fields **could not be verified** — the `/cases` API returned an unusable 4-column payload on 2026-08-03 —
so they must be confirmed before anything is planned on them, not assumed.

---

## PARALLEL — F, G and H, which start now and depend on nothing

### F — Unblock the deposit layer

**Every session in this project prints this, and it has never been resolved:**

```
[bdsp_bootstrap] PhysioNet: no credentials — HiRID/SICdb/AmsterdamUMCdb unavailable.
                 Set PHYSIONET_USER and PHYSIONET_PASSWORD in the environment settings
```

Three ICU databases with drug administration records **and** hard outcomes, gated behind two environment
variables. E130 died at 20 subjects and named its blocker precisely — *an assayed or pump-reported
concentration, a non-EEG state measure, and ≥ 60 subjects* — and none was found, because those three were
never checked.

That is the shape of the whole item: **we are bounded by deposits, not by ideas, and the boundary has
never been mapped.** TUH was approved and then found to carry no outcome labels at all (R321) — discovered
*after* pursuing it. A one-time rigorous survey of what exists, what it carries, and what it can and cannot
settle is pure parallel work.

**Requires the investigator:** setting `PHYSIONET_USER` / `PHYSIONET_PASSWORD` in the environment settings
(see `docs/CREDENTIALS.md`). Everything else is ours.

### G — The incumbent sweep

E129's lesson was expensive and specific. **`alpha_prom` sat in our own `dreyer_graph.csv` predicting BCI
performance at +0.3710 and we did not see it**, because every registration pointed at `ge_norm`. Rule 45
says name the incumbent; we applied it religiously to *outcomes* and never once to *predictor families*.

One disciplined sweep per challenge: what does the published literature already claim predicts this, is it
implementable from what is quoted, and have we tested it? The output is a **fixed comparator list that
every future registration must clear**. Cheap — E-utilities only, no data — and the highest value per token
on this list. Blankertz, Hannivoort and Proekt & Kelz were all found almost by accident while looking for
something else; done deliberately they would have been found first.

### H — Feature validation and the artifact layer

The item that can undo finished work.

**Of ~30 registry candidates, four have been validated against an independent implementation** — BSP
against an exact grid solver, wPLI pair-by-pair, the PK basis against an ODE integration, irreversibility
against sawtooth and phase-randomised surrogates. The rest have self-written code and self-written tests,
which rule 23 says share blind spots. Rule 22 exists because an "AUC 0.829" in a code comment measured
0.749 when checked properly.

And every feature is computed on windows carrying only a crude finite-fraction check. E107 and E111's
entire muscle saga was an artifact question that took three experiments to bound; E60 found BIS publishing
numbers at SQI 5.1/100 and we have no equivalent self-assessment. **If contamination correlates with
state, that is rule 14's shape and it hits all three challenges simultaneously.**

Both halves are embarrassingly parallel: one feature at a time, no dependency.

---

## Two adjuncts, cheap

**A design-detectability floor.** Dozens of placebo runs have produced empirical null distributions, so a
deposit's cluster count can be turned into "what could this design have detected". E130 and E108 both burned
effort on designs that could not have won — E130's every interval was half a unit wide at n = 20. Rule 40
says a gate that cannot fail is not a gate; the same applies to a design that cannot win.

**The ledger as an asset.** 131 pre-registered experiments with predicted win-likelihood recorded against
actual outcome is a calibration curve for research judgment, and almost nobody has one. It is also the
credibility substrate: the first reviewer question is "how much did you try before this worked", and it can
be answered with a file.

---

## Ordering

D before E, for a practical reason: E is a large-n outcome-linked effort, and running it on a marker not
shown to transport would repeat the field's mistake at greater cost.

F, G and H start immediately and in parallel with A/B/C. **G first among them**, because it needs no data,
no credentials and no result from anything else — and there is direct evidence from this week that not
doing it cost a finding we already owned.
