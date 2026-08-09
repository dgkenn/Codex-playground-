# E346 — result note. Seven interpretable, two refused, one bounded rather than pointed.

Registration: `bsde/src/bsde/experiments/e346_external_register.py`, committed before any statistic in it
existed. Output: `bsde/results/e346_external_register.json`. Every ClinicalTrials.gov response is cached
under the scratchpad, so the run is reproducible.

**The headline: this project's register is no longer a single-lab curiosity.** Its machinery-failure rate
now sits beside an external register with an exact denominator of **300,090** studies, and the two land in
the same region for a reason T4 identifies.

---

## T1 — the external upper bound. Exact denominator, no sampling.

Interventional studies with a terminal status: COMPLETED **255,348**, TERMINATED **29,598**, WITHDRAWN
**13,711**, SUSPENDED **1,433** — total **300,090**.

**Stopped share = 44,742/300,090 = 0.1491 [0.1478, 0.1504].** This is an **upper** bound on the
`gate_failed` analogue, because some stops are results rather than machinery.

## T2 — machinery or result? **G2 passed, thinly, and the answer is a range not a point.**

Over 5,000 stopped studies: **MACHINERY 0.472**, **RESULT 0.059**, **OTHER 0.468**. Leading reasons:
accrual 1,224, funding 537, logistics 253, business 144, safety 140, pandemic 123, efficacy 109.

The construct-validity gate — fixed at registration, and deliberately not self-written plants, because
that is exactly how E344/T2 failed — required the RESULT share to be higher in PHASE3 than PHASE1.
**It passed: 0.138 vs 0.172.** But the intervals overlap (PHASE1 [0.115, 0.163], PHASE3 [0.148, 0.200]),
so this is a thin pass and is reported as one. It is the direction the registration predicted, on
n = 800 per arm, and not more than that.

**The number that matters is a range, not the point the registration anticipated.** Because 46.8 % of
`whyStopped` texts are unclassified (1,796 unmatched, 546 blank), the machinery share of 0.472 is a
**floor**. So:

> **The external machinery-failure rate lies between 0.070 and 0.149** — 0.070 if every unclassified stop
> is a result (implausible), 0.149 if every one is machinery. Quoting 0.0704 alone, as the registration's
> formula would have, understates it.

## T3 — pipeline check. **PASS.** Not a finding of this file.

Results posting among completed interventional studies: **62,020/255,348 = 0.2429**, inside the range the
metaresearch literature reports. The pipeline returns a sane value on a quantity measured many times
before, so the other numbers here are not coming from a broken fetch.

## T4 — **the result that makes the whole comparison work. Machinery failure is a function of study size.**

| enrolment | stopped / total | rate |
|---|---|---|
| 1–20 | 15,173 / 55,537 | **0.2732** |
| 21–100 | 10,575 / 138,428 | 0.0764 |
| 101–500 | 4,179 / 68,685 | 0.0608 |
| 501+ | 1,020 / 20,348 | **0.0501** |

**A 5.5-fold gradient.** Small studies die on machinery at five times the rate of large ones — and this
project's register is entirely small-n analyses. That reframes E330's 24.0 %: it is not evidence of an
unusually error-prone lab, it is what the smallest stratum of a 300,000-study external register also does
(0.2732). The prediction was registered in advance and met.

## T5 — **NOT INTERPRETABLE. My registered censoring handling was inadequate, and I can show it.**

The by-year rates rise from 0.1267 (2005) to 0.1810 (2020), slope **+0.00142/year**, which reads as
"terminations are getting worse". **It is an artefact.** The registration excluded 2021+ as right-censored;
a diagnostic run afterwards shows censoring is present in **every** year and grows monotonically:

| year | 2005 | 2010 | 2015 | 2018 | 2019 | 2020 |
|---|---|---|---|---|---|---|
| share still ongoing | 0.069 | 0.112 | 0.183 | 0.258 | 0.301 | **0.346** |

**corr(ongoing share, stopped share) across the 16 years = +0.643**, and the slope flips sign with the
window: **+0.01175** (2005–08), **+0.00034** (2005–13), **−0.00012** (2005–15), +0.00142 (all). A trend
that changes sign depending on where you cut it, in the presence of a confound correlated at +0.64 in
exactly the observed direction, is not a trend. Terminated studies reach a terminal status early;
completed ones reach it late; so incomplete follow-up inflates the stopped share, more so in recent years.

**Reported as NOT INTERPRETABLE rather than as a finding.** The registration's stated handling — one
cutoff at 2021 — was the wrong instrument, and saying so is cheaper than the alternative.

## T6 — machinery failure by phase. Non-monotone.

PHASE1 0.1737 · **PHASE2 0.2354** · PHASE3 0.1607 · PHASE4 0.1628. Phase 2 is the worst, not phase 1.
Descriptive, and it supplies T2's contrast.

## T7 — **FAILED, and the failure is a real finding about what can be audited.**

E344/T2 left this project's outcome labelling unaudited because the "independent" classifier shared my own
vocabulary. E346 tried the genuinely external repair: a vocabulary derived from CTG's `whyStopped` corpus —
text written by thousands of other investigators with no knowledge of this project.

**It fires on 14 of 225 rows (6.2 %), against a registered 40 % floor, and of those 14 only 1 is labelled
`gate_failed` by me** (the other 13 are positive 7, absent 3, negative 3). Precision 0.071. G7 FAIL,
**NOT INTERPRETABLE**.

The reason is not fixable by a better word list. **Trial-stopping vocabulary is about accrual, funding,
sites and drug supply; analysis-stopping vocabulary is about gates, nulls, placebos and power.** The two
corpora barely share terms, and the 14 matches are incidental words rather than genuine machinery
statements.

> **So the honest conclusion stands after two attempts: this register's outcome labelling cannot be
> audited from its text, by my own vocabulary or by an external one.** It must be defended some other way
> — a second human reader, or a structured field written at the time — and until then every rate carries
> that caveat. This is the same lesson E343 reached about prose recurrence markers, arriving from a
> different direction.

## T8 — the four headline rates at the **lineage** level. These are the registered primaries.

37 lineages, each voting by majority of its rows:

| statistic | lineage level | row level (E344/T1) |
|---|---|---|
| machinery-failure | **0.081** [0.028, 0.213] (3/37) | 0.240 [0.187, 0.298] |
| true-positive | **0.297** [0.175, 0.458] (11/37) | 0.320 [0.258, 0.382] |
| no incumbent named | **0.703** [0.542, 0.825] (26/37) | 0.640 |
| analyst-defect | **0.444** [0.246, 0.663] (8/18) | 0.296 |

**The registration declared the lineage number primary before I saw it, and it is much lower — the
direction that weakens my own headline.** I am keeping it as registered.

But the two are **different estimands**, and I did not appreciate that clearly enough when I registered:
the row rate answers *"of the designs I registered, what fraction died on machinery"* — a statement about
effort — while the lineage rate answers *"of the independent questions, what fraction MOSTLY died"* — a
statement about questions, which majority-voting makes much stricter. Both belong in the paper with their
definitions attached; neither is a correction of the other.

Note also that **analyst-defect rises** at the lineage level, 0.296 → 0.444: a lineage is scored as
analyst-defect if *any* of its gate failures was, so the two aggregations move in opposite directions.

## T9 — side by side. **No significance test, as registered**, because the two artifacts count different objects.

```
this register, lineage level     0.081   [0.028, 0.213]     n = 37 lineages
this register, row level         0.240   [0.187, 0.298]     n = 225 registrations
ClinicalTrials.gov, plausible    0.070 - 0.149              N = 300,090 studies
ClinicalTrials.gov, smallest     0.273                      n <= 20 enrolment stratum
```

Two coincidences worth noting and not over-reading. **CTG's entire plausible range (0.070–0.149) sits
inside my lineage-level interval [0.028, 0.213]**; and my row-level 0.240 sits near CTG's smallest-study
stratum, 0.273. T4 supplies the reason the second one is not a coincidence at all — machinery failure
scales with study size, and this register is small-n throughout. **The register's rates are ordinary for
work of this size.** That is a much better sentence for a paper than "this lab fails a lot", because it is
about the structure of small studies rather than about one lab.

## T10 — the published-literature benchmark at scale. **1 in 891.**

| field | unselected rate | n | positive control | usable |
|---|---|---|---|---|
| anaesthesia/EEG | 0.0000 | 297 | 0.117 | **no** — control did not clear 0.15 |
| oncology | 0.0034 | 297 | 0.450 | yes |
| cardiology | 0.0000 | 297 | 0.517 | yes |
| psychiatry | 0.0000 | 297 | 0.200 | yes |

**Pooled over the three usable fields: 0.0011 — one abstract in 891** states that the study could not
evaluate its question. The anaesthesia/EEG arm is refused on its own control (rule 71: every gate is
per-arm and the verdict must index the arm), which is the correct handling and removes the field this
project works in from its own benchmark.

Against **7–15 % in a register of 300,090 trials** and **8–24 % in this register**, depending on the unit.

---

## What E346 does to the paper

**Externalised.** The central claim is no longer about one lab. An independent register with an exact
denominator of 300,090 studies shows 7–15 % of registered work stopping before it answers its question,
a 5.5-fold size gradient that explains this register's own rate, and a published literature that reports
such events at **1 in 891**.

**Two honest refusals that belong in the paper.** T5 cannot say whether the external rate is improving —
censoring is confounded with time at ρ = +0.643 and the slope flips sign with the window. T7 shows the
outcome labelling **cannot be audited from text at all**, by my vocabulary or anyone else's.

**Still open, and now the only thing that would close it**: a second human reader on the register's
outcome labels, or a structured field recorded at the time — which is what `preregistry/SPEC.md` v1.1
already specifies for recurrences and should specify for outcomes too.
