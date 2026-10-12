# Can UCE pass the three challenges, and what does it teach us?

*Written 2026-07-31. Companion to `UCE_V1_REASSESSMENT.md`. Every number is from this repository's own
registered experiments or computed here.*

**The short version.** This project has already tested the construct three times without framing it that
way — E05, E30 and E41 all scored `uce_v1` and/or `whole_head_exponent`. **On Challenge A the evidence is
specifically unfavourable and E36 says why. On Challenge B there is no evidence it helps and it is not the
bottleneck. On Challenge C it has never been tested against the comparator its own strongest claim names,
and that is the real opportunity.** The most valuable things in it are methodological, and they are things
this project does not currently do at all.

---

## Challenge A — "predicts loss and recovery across anaesthetics while MINIMISING drug-identification information"

### What has been measured

**E05 asked exactly this question and returned indeterminate — but pointing the favourable way.** Its
statistic `S` is positive when a candidate follows behavioural STATE and negative when it follows the DRUG,
computed within subject on the Chennu recovery dissociation:

| candidate | S | 95 % CI | verdict |
|---|---|---|---|
| **`uce_v1`** | **+0.1795** | [−0.014, +0.382] | INDETERMINATE |
| **`whole_head_exponent`** | **+0.0605** | [−0.148, +0.273] | INDETERMINATE |
| `relative_delta_power` | −0.2804 | [−0.515, −0.039] | **DRUG** |
| `relative_alpha_power` | −0.1614 | [−0.342, +0.060] | undetermined |
| `wpli_alpha` | −0.1384 | [−0.390, +0.107] | undetermined |

`uce_v1` has the most state-leaning point estimate of all eight candidates and comes closest to excluding
zero on the state side. **E05's registered prediction was S < 0 (follows the drug), deliberately against
this project's interest — and the observed direction went the other way.** A failed prediction in the
favourable direction is weak evidence, not strong, and the interval still spans zero at n = 20.

**E30 is the unfavourable one, and it is specific.** Registered on two deposits — propofol without opioid,
volatiles with — its primary was `exponent_high`. Outcome: *"propofol +0.710 [+0.614, +0.820] survives its
placebo; **P3 FAILED, arms disagree in sign**."* Arms disagreeing in sign is error-catalogue rule 16: when
two arms of the same test disagree in direction, the definition is doing the work rather than the biology.
**A measure whose behaviour differs by agent class is carrying agent identity, which is precisely what
Challenge A's acceptance condition penalises.**

**E36 predicts why, and the prediction is sharp.** E35/E36 established a split by measure family at matched
unresponsiveness on the Krause propofol/dexmedetomidine deposit:

| family | drug-identity legibility |AUC−0.5| |
|---|---|
| phase-based coupling (wPLI variants) | **0.000 – 0.128** |
| power and complexity | **0.217 – 0.368** |

with the split surviving as the unique maximum of all 495 alternative partitions (p = 0.002) and a
capability control excluding the "phase measures are just weaker" explanation to within ±0.10.

**Stated precisely, because the extrapolation matters:** the aperiodic exponent was **not** among the
thirteen features E36 tested — the Krause deposit ships derived features only, and no raw traces (215
entries enumerated, no EDF or iEEG), so it could not be computed there. The exponent is a *spectral
amplitude summary*, the same kind of object as the family that leaked. **So E36 makes a falsifiable
prediction rather than a finding: the aperiodic exponent should carry agent identity.** E30's sign
disagreement is independent evidence consistent with it.

### Verdict, and the refinement that would actually address it

**As constituted, unlikely to pass — and the reason is structural rather than a tuning problem.** A single
spectral amplitude summary is in the family that carries agent identity. Re-weighting cannot fix it (§0:
the weights are forced by symmetry), and neither can changing the reference.

**The refinement E36 points to is a composite.** Pair the exponent with a phase-based measure — the two
families are near-orthogonal in what they leak, and one supplies the state sensitivity while the other
supplies the agent-invariance. `wpli_alpha` and now `icoh_alpha` are implemented and registered here. That
is a concrete v2 with a pre-registrable prediction: **the composite should retain the exponent's state
discrimination while its drug-identity legibility falls toward the phase family's.**

The blocker is the same one Q9 records: **every reachable deposit has its two agents in disjoint patients.**
The Turku cohort (Kallionpää 2020, PMID 32773216, NCT01889004 — 47 volunteers, dexmedetomidine or propofol,
**within-subject loss and return of responsiveness at constant dosing**) is the right test bed, and a data
request is drafted at `DATA_REQUEST_TURKU_KALLIONPAA.md`.

---

## Challenge B — spontaneous EEG predicting command-following

**Measured directly in E41, on 104 subjects with a pre-registered power calculation:**

| measure | ρ with motor-imagery ability | 95 % CI |
|---|---|---|
| `relative_alpha_power` (the incumbent) | **+0.2018** | [+0.0050, +0.3857] |
| `uce_v1` | +0.0853 | [−0.1066, +0.2651] |
| `whole_head_exponent` | +0.0490 | [−0.1322, +0.2430] |

Both UCE forms are null and both are beaten by a deliberately weakened proxy for a fifteen-year-old
published predictor. Nothing survives multiplicity over the fourteen-candidate family.

**But the honest reading is that UCE is not the problem and refining it is not the lever.** E41's minimum
detectable effect was ρ = 0.272 at n = 104, and E38 measured the label's reliability at r_sb = 0.2918
[0.1163, 0.4345], **capping any predictor at ρ ≈ 0.54 by attenuation alone**. The bottleneck is label
precision and sample size, not the marker. That is why the queued move is Stieger 2021 (Q14) — 62 subjects
with **450 trials per session** against eegmmidb's 45 in total — and not a better spectral feature.

**Verdict: no evidence it helps, and improving it would not move this challenge.**

---

## Challenge C — seeing a transition before the conventional monitor

**This is the one where the construct has never been given a fair test here, and where its own strongest
claim lives.**

This project's three Challenge C verdicts (E26, E34, E37) all measure candidates against **SEF95, a
computed spectral-edge proxy**, and all fail in the same place: above chance, not above the incumbent.
Claim scope was written as *"ahead of SEF95, never ahead of BIS"* precisely because BIS is not in the
DOSE-I deposit.

**The UCE claim is against real BIS** — lightening detected 2.25 minutes earlier at 85 % sensitivity and
6 % false positives, on VitalDB where BIS is actually recorded. **Our Challenge C negatives do not refute
that, because they never tested the same comparator.** Two different questions have been conflated by
sharing a challenge number.

**And the mechanism offered is checkable rather than hand-waved.** The discordant epochs are reported at
21× beta and 81× gamma power, clustering 63 % in the final third of maintenance — consistent with returning
muscle tone as neuromuscular blockade wears off, which drives BIS *into* the 40–60 range while a broadband
slope is comparatively unaffected. **That is a specific, falsifiable claim about an EMG failure mode of
BIS**, and this project has EMG proxies registered (`emg_index`, `emg_beta_gamma_fraction`,
`emg_kurtosis`) and `vitaldb_grid.csv` carries `meta_bis`, `meta_emg` and `meta_sqi` on 250 cases.

**Verdict as first written: "untested here, and the single most testable opportunity of the three."
THAT IS NOW STALE IN BOTH HALVES, and both corrections point the same way.**

**The EMG mechanism was tested, and REFUTED in the opposite direction (E43).** At matched conditioning,
`partial(BIS, EMG | spectral state) = +0.165` against `partial(spectral state, EMG | BIS) = −0.262` —
asymmetry **−0.0967 [−0.1798, −0.0100]**, with an independent EMG estimate agreeing at **−0.2120
[−0.2889, −0.1286]**. **The broadband spectral measure is MORE muscle-associated than BIS**, not less,
which is physically sensible: an aperiodic exponent is fitted straight through the 20–45 Hz band where
surface EMG lives, while BIS carries explicit EMG-suppression processing. The temporal half failed too —
EMG *falls* slightly across maintenance (Spearman −0.081) against a claim of 63 % clustering in the final
third. So the proposed mechanism for the discordance is not supported here. The discordance itself is
untouched; only the explanation is.

**The comparator problem, which was the real content of this section, is now solved.** Q22 built a
computable BIS-like index and E58/E60 measured it: median absolute error **3.47** in [40,60) — better than
Lee et al.'s 4.1 on their own development data — and **~4.8** in [20,40) with a two-stage fit. It is
**refused** above BIS 60 and below BIS 20, on evidence rather than caution: 98.2 % of the [80,100) windows
are facial-EMG artefact and the [0,20) windows carry median SQI **5.1 of 100**. See
`BIS_FAITHFUL_OR_BRAIN_FAITHFUL.md`. So Challenge C's negatives can now be re-asked against a BIS-like
comparator instead of the SEF95 proxy they settled for — **within that validated band, and not outside
it.**

---

## What this project should learn from it, which is the more valuable half

### 1. A frozen population reference is a method we do not use, and it is why our results do not compose

Every experiment in this repository normalises **within cohort**. E39 could not combine `ds004541` and
`chennu` into one estimate for exactly this reason; E36's finding cannot be carried to another deposit
because its legibilities are cohort-relative. **The UCE approach — derive a reference once from a large
cohort, freeze it, and never re-fit — is what makes a cross-deposit claim expressible at all.** It is also
what makes a transfer failure *interpretable*, because the thing that failed to transfer is a stated
number rather than a fitting procedure.

**This is adoptable immediately and cheaply**, and it is probably the highest-value single change to how
this project reports results.

### 2. Landmarks on a shared axis are stronger evidence than a better AUC

Our outputs are AUCs and correlations. Theirs are positions on one scale: N3 at −5.2, N2 at −3.5, volatile
at −2.3, TIVA at −1.4, **LOC at −1.2 converging across four independent datasets**, awake at 0, ketamine at
+0.2. **A convergence of an independently-derived boundary across four datasets is a stronger claim than any
single AUC**, because it is an invariance rather than a discrimination — and invariance is what this
project's challenges keep failing to demonstrate. Worth adopting as an output format regardless of the
construct.

### 3. Ketamine is the dissociation we have been hunting, and it is obtainable

Challenge B's flagship needs **arousal separated from cognitive processing**. We have chased DoC cohorts
with command-following labels (WBIC request out, Q11's ds005620 reports missing) and substituted healthy
motor imagery with an explicit warning that the substitution is an analogy.

**Ketamine gives the dissociation directly, in healthy volunteers**: behaviourally unresponsive with
consciousness preserved — Colombo 2019 (PMID 30639334) reports the spectral exponent staying at wakefulness
levels under ketamine, which is the finding the UCE work reproduces at p = 0.99 on the Farnes data (n = 10).
**That is the flagship question in a population where the answer is checkable, with no DoC access required.**
It should be in the queue and is not.

### 4. The dual-slope idea is E36's logic in a different dimension

Separately fitting 1–20 Hz and 20–45 Hz to distinguish ketamine (high band flattens, divergence +0.91) from
seizure (high band steepens, −0.46), **despite both producing positive broadband scores**, is exactly the
principle behind adding `icoh_alpha` beside `wpli_alpha`: *make the second measure differ from the first by
construction, not by name* (rule 28). `subband_exponents` already exists in this registry for the Colombo
20–40 Hz result. The ketamine/seizure separation is a ready-made validation target for it.

### 5. A predicted failure is worth more than an unexplained success

The I-CARE wrong-direction result becomes evidence *for* the framework if the aetiology reversal
(R389–R392) predicts it in advance. `UCE_V1_REASSESSMENT.md` §3 sets that out, with the caution that the
reversal concerns spectral balance in bursts rather than the aperiodic exponent, so transfer is an open
question.

---

## What I would do next, in order

1. **Challenge C, the EMG-discordance test.** Fully specified, data already local, and it tests the UCE
   claim against the comparator our own work never used. Highest information per unit of effort.
2. **Adopt the frozen-reference reporting format** for at least one existing result, to see what it costs
   and what it buys.
3. **Add ketamine to the Challenge B queue** as the arousal/experience dissociation that does not need DoC
   access.
4. **Register the exponent-plus-phase composite** for Challenge A, contingent on a two-agent cohort — which
   means the Turku request is on the critical path.
5. **Do not spend effort refining UCE for Challenge B.** The ceiling is 0.54 and the bottleneck is the
   label, not the marker.
