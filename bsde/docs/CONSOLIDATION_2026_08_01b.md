# Consolidation — the re-derivation programme, E166 to E177

*Written 2026-08-01, after the session that re-derived the increment-decided ledger rows. Supersedes
nothing in `CONSOLIDATION_2026_08_01.md`; it is the next block of results, and where the two disagree this
one is later. Two experiments (E168's per-lambda floors, E170's placebo distribution) were still running
when this was written and are marked as such.*

---

## 1. The headline, in one paragraph

**The instrument was worse than "blind" — it was, in two places, wrong.** E146 had already measured
`oob_regression_increment`'s tail fraction as conservative to the point of detecting in 0 % of draws where
a proper test detected in 88 %. This session re-derived the seven remaining rows that instrument had
decided, and **four of six re-derivable rows moved to ADDS**. One of them, e99, had been recorded as
**HURTS with an interval excluding zero and a written mechanistic story**, and the sign was an artefact of
a **missing intercept column** in a design matrix. Separately, Challenge B produced its first calibrated
positive by changing the unit of analysis from the subject to the trial, and Challenge D's replacement
transport rule survived its first forward test.

---

## 2. E166 — the seven rows, re-derived against a measured floor

Every cohort was rebuilt inside E166 and had to reproduce its ledger row's size before anything was
scored. All seven did, to the row.

| row | rows | clusters | increment | p | floor | verdict |
|---|---|---|---|---|---|---|
| e26 @ SR>0 | 597 | 81 | −0.01089 | 0.1520 | 0.05 | ABSENT ABOVE FLOOR |
| e26 @ SR≥10 | 213 | 33 | +0.00514 | 0.6260 | 0.20 | BASELINE DEAD |
| **e34** | 79,429 | 129 | **−0.02147** | **0.0000** | 0.05 | **ADDS** (was PLAIN NULL) |
| **e37** | 38,684 | 70 | **−0.00737** | **0.0000** | 0.10 | **ADDS** (was P3b NOT MET) |
| **e58** | 5,845 | 247 | **−0.25637** | **0.0000** | none | **ADDS** (was NO GAIN) |
| **e99** | 5,798 | 247 | **−0.02000** | **0.0000** | 0.10 | **ADDS** (was HURTS) |
| E130 | 78 | 20 | −0.23192 | 0.0060 | 0.40 | BASELINE DEAD |

Lower is better throughout: a negative increment means the addition helps.

**The floor is the reusable part.** Each null now says *nothing above ρ = X* instead of *nothing found*,
where X is measured by injecting a known partial effect and running the identical machinery. The floors
ordered exactly as cluster count and headroom predict — 0.05 at 129 clusters, 0.10 at 70 and at 247, 0.20
at 33, 0.40 at 20 — and the ρ = 0 calibration rung fired in 0 of 3 draws on every one of the seven rows.

**Two rows are refused rather than re-decided, and that is the gate working.** e26 at SR ≥ 10 and E130
both fail baseline aliveness: BIS does not predict substantial suppression (p = 0.2200, consistent with
its recorded AUC 0.449 whose interval spans 0.5), and measured plasma propofol does not predict reaction
time (p = 0.1000). E130's increment of −0.232 at p = 0.0060 therefore cannot be read as "the EEG adds to
plasma" — there was nothing to add to (rule 53).

**e58's ladder detected nothing at any rung** while its primary reached p = 0.0000, and the ladder's own
p-values sat at 0.97–1.00 (the injected column consistently *hurt* median |err| in an 18-column ridge). Its
floor is therefore **not measured**, and its ADDS rests on the primary alone. Reported, not smoothed over.

---

## 3. e99 — a missing intercept produced a plausible wrong sign that survived a ledger row

`oob_auc_increment` fits an IRLS logistic that carries no intercept of its own, and said so in its
docstring. E99 passed `[BIS]` and `[BIS, whole_head_exponent]` bare. Both models were fitted through the
origin.

| | increment |
|---|---|
| without the intercept (what E99 ran) | **−0.0320 [−0.0544, −0.0111]** → recorded HURTS |
| with the intercept, identical rows | **+0.0168 [+0.0049, +0.0269]** → ADDS |

Re-run in full, every arm of E99's own design returns ADDS (primary +0.0160, artefact-clean +0.0207,
muscle +0.0260) and its negative control stays null at −0.0005. **E173** then checked whether this was an
estimator disagreement and found it was not: cluster bootstrap with the logistic +0.0160, cluster
bootstrap with a linear ridge +0.0162, 5-fold cross-fit +0.0235, and a 50–95 % training-fraction sweep
that never leaves +0.017…+0.023.

**What makes this worth a rule (76) is the shape of the failure, not the arithmetic.** The wrong sign came
with a mechanistic story ("variance the model spends capacity on"), an interval excluding zero, and a
passing negative control. It survived a ledger row and a consolidation document. `stats.py` now raises
when a design's first column is not a constant. E89 carries the same defect from the same copied template
but gate-failed before reaching it.

E173's own synthetic control needed repairing first — its "noise" column shared a cluster-level latent
with the baseline, so every estimator called it real in 100 % of replicates (rule 77). Repaired, the
cross-fits land at 25–40 % positive on a genuine null and **the cluster bootstrap at 12 %**, i.e. slightly
biased toward HURTS — the same direction as the intercept bug, and an independent reason to prefer
cross-fitting when the sign is what is at stake.

---

## 4. Challenge B — the first calibrated positive, from changing the unit

Thirty Challenge B rows in this ledger predict a **subject-level trait** from one collapsed row per
session. `extract_stieger_features.py` was already reading the right segment — 2 s of pre-cue spontaneous
EEG per trial — and then averaging it away.

**E167** asked the trial-level question with a regression adjustment for trial position and **failed its
own gate twice**: the registered quadratic left a rank correlation of +0.2184 between trial index and the
residualised outcome against a measured null of [−0.0790, +0.0789], and the one repair rule 58 allows
(10-block centring) still left position predicting at p = 0.0000. Closed; its numbers recorded as
unlicensed.

**E172** removed the clock by construction instead: each hit trial matched to the nearest miss in the same
session, mean |gap| **1.35 trials**. Trial index scored as a candidate by the identical statistic returns
**0.4920, p = 0.2070** — the pairing did what two regressions could not.

| | |
|---|---|
| `mu_mean` (C3/C4 relative alpha) | **0.5176 [0.5054, 0.5303]**, p = 0.0060, 0.61 of sessions same side |
| `relative_alpha_power` | 0.5219, p = 0.0010 |
| `mu_c4` | 0.5171, p = 0.0095 |
| placebo (previous trial's outcome) | 0.4953, p = 0.4510 |
| measured floor | ρ = 0.05 (ρ = 0.02 not detected) |
| i.i.d. noise control | not detected, p = 0.2730 |

Nine of twelve candidates are null, and `mu_lateralisation` is flat at 0.4960 — so this is amplitude, not
hemispheric asymmetry. It replicates **PMID 27199630**, which reports central mu at cue presentation
"correlated with the success on the subsequent imagery task" without stating a sign, and the direction
agrees with Blankertz 2010's between-subject sign.

**It must not be called a mu-specific effect**: ρ(mu_mean, relative_alpha_power) = +0.8386 over 27,000
trials and the montage median scores slightly higher (rule 60). And the effect is **51.8 % against 50 %** —
real, above the measured floor, and small. The incumbent could not be scored because the deposit's artefact
flag is 0 in 27,705 of 27,900 trials; that is reported rather than left blank (rule 45).

**Two replications are extracting now.** E174 on 124 held-out Stieger sessions (same subjects, new
recording days — session-generality, explicitly not subject-generality), one-sided in E172's direction with
every threshold fixed to E172's published values. E175 on eegmmidb: different deposit, montage, laboratory
and — the point — **a different paradigm with no feedback**, where the outcome necessarily becomes decoder
legibility rather than a behavioural hit. That is closer to the covert-consciousness construct than a
cursor is, and E175's registered prediction is NO POWER or NOT REPLICATED at ~45 trials per subject.

---

## 5. Challenge D — the replacement transport rule survives its first forward test

`CONSOLIDATION_2026_08_01.md` §4 recorded that "transport succeeds when the construct matches" was refuted
by its own pre-registered test. The replacement, recorded in `PROGRAMME_ROADMAP.md` as a retrodiction over
five observations and explicitly not citable: **both survivors were specified OUTSIDE the cohort they were
tested in; every failure was selected inside its own.**

**E177** staked it on one cell nobody had looked at. On eegmmidb, 101 subjects, identical rows, one
estimator, directions declared in advance:

| measure | origin | ρ | one-sided p |
|---|---|---|---|
| `alpha_prom` (Blankertz 2010) | **imported** | **+0.2939** | **0.0015** |
| `ge_norm` (selected in Stieger) | discovered | −0.1326 | 0.9030 |
| `iaf` (selected in Stieger) | discovered | +0.1011 | 0.1415 |

Both labels cleared the aliveness gate (between-subject variance at 4.83× and 2.91× per-subject estimation
noise). **Reported and not dropped:** on the weaker secondary label, `iaf` reaches p = 0.0490 — a marginal
partial violation, on the label E124 replaced precisely because it was too weak, and it does not survive on
the primary.

**Five retrodictions and one forward success is one forward success**, and the file prints that count
itself. By-product worth carrying: `alpha_prom` at +0.2939 is a **stronger eegmmidb incumbent** than the
`relative_alpha_power` (+0.2018) E149 used, and `INCUMBENT_REGISTRY.md` should say so.

**E171** produced the project's first calibrated output, which rule 15 and the roadmap both say had never
been done. Against DOSE-I's clinician-assigned MOAA/S on all 171 recordings, three arms are alive out of
fold: panel ρ **+0.5115**, PE31 **+0.4497**, SEF95 **+0.2737**. Of twelve arm × stratification cells, **one
exceeds its own random-stratum noise floor and it is the incumbent's**: SEF95's calibration slope across
BMI terciles runs +0.987 / +1.376 / +0.518 (spread 0.8581, p = 0.0240) while the panel's and PE31's do not
beat theirs. The defensible sentence is *the incumbent's calibration demonstrably varies with BMI and ours
is not shown to* — narrower than the registered label. The sex stratification points the other way and is
reported; **E109's age finding is not reproduced against this reference**, so the wedge argument does not
get to borrow this result.

---

## 6. Challenge A — the bar was vacuous, and the cohort cannot pose the question

**E168** repaired E165's floor and validated the repair against a second, exactly computable null: the
full-pipeline case-level permutation gives p95 **0.1944 (MC sd 0.0137)** against the exact λ = 0 null's
**0.1886**. E165's bar had been the 95th percentile of agent legibility over **random projections,
0.4203** — a statement about random projections, not about chance, and more than twice the real floor.
That is why its verdict fired at λ = 0 with no adversarial pressure applied (rule 75).

With the correct floor, the λ = 0 axis's agent legibility is **0.0857**, *below* its own floor. The MGH
cohort's amplitude family does not leak the anaesthetic to begin with — its contrast is 25 pure-propofol
against 14 **mixed-agent** cases, not one drug against another — so no adversarial term was ever needed and
the design cannot speak. E168 enumerated that outcome in advance as VACUOUS. *(Per-λ floors still running.)*

**E169** moves to the cohort where E161 measured real leakage in seven of ten features: VitalDB's 44
propofol-alone against 71 sevoflurane-alone cases. VitalDB has **no awake baseline** (0 of 6,437 windows
before `anestart`), so the state axis becomes depth anchored on administered exposure, ranked within case
so MAC and propofol Ce are never compared. Its G5 is the gate E168 lacked: **the nuisance must be alive**.

**E176** asks the question none of the linear files can: is the entanglement a property of linearity or of
the data? Non-parametric (k-NN) agent legibility before and after residualising every feature on the depth
axis, with an over-adjustment gate (depth is downstream of agent choice — rule 13) and a placebo that
residualises on 500 random scores of matched variance.

---

## 7. New error-catalogue rules

**76** — a helper with an unenforced precondition will eventually be called wrong, and the cost is
proportional to how reasonable the wrong answer looks. Enforce in code, and grep every caller.
**77** — a negative control built to be independent must be *measured* for independence; a shared latent is
invisible in the code that constructs it.

---

## 8. What to do next, in order

1. **Finish and record E168's per-λ floors and E170's placebo distribution.** E170 is the gate on E34's
   overturn and it can still kill it: the muscle comparator `rel_gamma` sits at −0.01985 against the
   primary's −0.02180, exceeded by 0.002 on a scale where the order-pattern family spans 0.07, and DOSE-I
   has no EMG channel. See `NOTE_OSTERTAG_AND_THE_PE_OVERTURN.md`, written before the verdict.
2. **Run E169 and E176** once E168 releases the CPU. Between them they decide whether Challenge A's
   entanglement is a fact about linear combinations or about the features.
3. **Read E174 and E175 as a pair.** A pass on E174 with a NO POWER on E175 is the most likely outcome and
   means the effect is session-general and untested outside the deposit — which is exactly the state that
   makes BATH-01632 and Turku the binding constraints again.
4. **Update `INCUMBENT_REGISTRY.md`** with `alpha_prom` (+0.2939 on eegmmidb csp_auc) and with `PE31`
   (+0.4497 against MOAA/S on DOSE-I). Two designs in this session named weaker incumbents than were
   available.
5. **The four moved Challenge C rows need a single document** stating what the project now believes about
   order-pattern measures and imminent loss of consciousness — not four corrected ledger rows.
