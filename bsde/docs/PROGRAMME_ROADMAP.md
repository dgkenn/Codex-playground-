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
