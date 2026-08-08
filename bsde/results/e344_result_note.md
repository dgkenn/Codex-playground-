# E344 — result note. Ten tests: 6 interpretable, 2 refused, 1 not-interpretable-on-inspection, 1 knife-edge.

Registration: `bsde/src/bsde/experiments/e344_register_battery.py`, committed before any statistic in it
existed. Output: `bsde/results/e344_register_battery.json`.

`G0` PASS — 225 registrations, **11 (4.9 %) carried free text rather than the enum**, 0 uncanonicalisable.
The free-text share is itself a finding: the format's outcome vocabulary was not enforced by the tool that
wrote the rows. Canonicalising them moves the true-positive count from E330's 66 to **72**, so E330's
31.6 % is **32.0 %** here — a small revision, recorded rather than absorbed.

---

## T1 — the headline rates finally have intervals. **PREDICTION MET.**

| statistic | point | registration-level 95 % CI | challenge-level 95 % CI |
|---|---|---|---|
| machinery-failure | **0.240** | [0.187, 0.298] | **[0.133, 0.291]** |
| true-positive | **0.320** | [0.258, 0.382] | [0.275, 0.446] |
| no incumbent named | 0.640 | [0.578, 0.702] | [0.533, 0.753] |
| analyst-defect (of gate failures) | 0.296 | [0.185, 0.426] | [0.189, 0.432] |

Clustering by challenge widens 3 of 4 intervals by ≥ 1.3×. **The machinery-failure rate must be quoted as
"roughly a quarter, and the interval reaches down to 13 %", not as "24.0 %."** The overstatement factor
`1/0.320 = 3.13×` inherits the true-positive interval: **2.24× to 3.64×** at the challenge level.

## T2 — **NOT INTERPRETABLE, and the gate that passed was too easy. This is my error, not a finding.**

Agreement between the analyst-assigned `outcome` and an independent keyword classifier reading only
`outcome_detail` was **0.353** on the 83.1 % of rows the classifier decided. The registration named "low
agreement" as the outcome that costs the most, so I went looking for the mechanism before writing it down,
and found one:

> **54 of 225 rows contain "withdraw", "retract" or "overturn" in their detail text. Only 8 are actually
> class `withdrawn`.** My classifier checks `withdrawn` before `positive`/`negative`, and detail texts in
> this register routinely *discuss* the withdrawal or overturning of some *other* result. That mechanism
> alone accounts for at least 46 of the disagreements, and the top three confusions
> (`negative→withdrawn` 21, `positive→negative` 20, `positive→withdrawn` 14) are exactly its signature.

**So the test cannot distinguish "the analyst labelling is unreliable" from "my classifier is
unreliable", and the honest report is that E330's labelling remains unaudited.** G2's capability check
passed on 4 planted texts **that I wrote to match my own patterns** — which is rule 91's failure (a
control that passes because the case was easy) committed inside a gate built to satisfy rule 23. A
genuinely independent implementation must be built without knowledge of the primary's patterns; four
self-authored plants is not a capability gate. It is not repaired and re-run (rule 58).

## T3 — the biggest limitation on everything above. **225 rows resolve to 37 lineage roots.**

Following `successor_of`, the register's 225 registrations are **37 independent question-lineages**
(16.4 % of the row count). The largest lineages hold 32, 27, 21, 18 and 16 rows; 14 are singletons.

**Every rate in T1 should be read against an effective n nearer 37 than 225**, and the challenge-level
intervals — which cluster on 8 challenges, not 37 lineages — are the closer of the two but still not
right. This is the first thing a referee will find, and it is now measured rather than waiting to be
found.

## T4 — the machinery-failure rate is partly a property of the format. **Weak, and stated as weak.**

P(gate_failed) by gate count: 0.000 (n=8) · 0.176 (17) · 0.182 (22) · 0.200 (45) · **0.309 (94)** ·
0.212 (33) · 0.500 (4) · 0.000 (2). Slope **+0.0364 per gate**.

At the registered 5,000 permutations the observed slope coincided with the null's 95th percentile to four
decimals, so rule 46 applies. **Re-run at 20,000 permutations across five seeds: p = 0.0429, 0.0421,
0.0425, 0.0415, 0.0433** — stable, and all below 0.05. The pass is real and it is thin, and the
per-gate-count profile is **not monotone**: it is carried by the single 4-gate cell, which holds 94 of
225 registrations, and the two highest cells hold 4 and 2 rows.

The reading that survives: more gates buy more refusals, by roughly 3.6 percentage points each, so part
of the 24 % is the format refusing rather than the science failing. That direction *deflates* the
headline and is reported for that reason.

## T5 — **prediction NOT met, and the null helps the claim.**

P(positive | incumbent named) = 0.321 (n = 81); P(positive | none) = 0.319 (n = 144);
difference **+0.0015, p = 1.0000**. I predicted naming a bar would make positives harder, which would
have meant the true-positive rate was inflated by the 64 % naming no bar. **It is not.** The overstatement
factor does not depend on the incumbent field, which removes an alternative explanation rather than
supplying one.

## T6 — the external benchmark, and it is the sharpest number in the battery.

Among **119** unselected PubMed research abstracts (EEG/anaesthesia, 2023–2025, with abstracts),
**0 (0.0 %)** state that the study could not evaluate its question. The positive control — abstracts
retrieved on "terminated early" / "failed to recruit" / "stopped early" — fires at **12/60 = 0.200**, so
the classifier can detect the statement it is counting (G6b PASS).

**0.0 % in the literature against 24.0 % [13.3 %, 29.1 %] in a register that records every design it
started.** The estimand is what authors *wrote*, not what happened, and that gap is precisely the claim:
these events occur at scale and are not reported.

## T7 — **NOT INTERPRETABLE, and honestly so. There is no prospective sample.**

Zero rows are registered after E330's own date; the register's last entry is the same day. E330 described
the register it was computed on, and nothing here is held out. **A prospective check is the single
cheapest thing that would strengthen this line and it requires only time.**

## T8 — the methodological finding with reach beyond this project. **BIASED.**

E321/E342's criterion (c) — "the drug contrast does NOT exclude zero" — is an *acceptance* of a null, so
a measure too imprecise to reject anything satisfies it for free. Synthetic measures with a **known**
drug response, swept over measurement noise (G8 PASS: 0.98 detection of a true dissociator, 0.00 false
alarms in the easy case):

| noise | P(dissociates \| **has** a drug response) | P(dissociates \| truly dissociating) |
|---|---|---|
| 0.15 | 0.000 | 0.970 |
| 0.50 | 0.000 | 0.970 |
| 0.80 | 0.005 | 0.963 |
| **1.20** | **0.113** | 0.690 |
| **2.00** | **0.110** | 0.212 |
| 3.00 | 0.025 | 0.030 |

The false-dissociation rate rises to **11 %** at intermediate noise. The full picture is worse than a
one-sided bias: by noise 2.0 the criterion returns 0.110 for a drug-responsive measure against 0.212 for
a genuinely dissociating one — **nearly uninformative**, with both collapsing to ~0.03 by noise 3.0. So
the criterion is not merely conservative at high noise; it is *anti*-informative in a band, and a measure
lands in the dissociating set partly on how noisy it is.

**This applies to the whole family of "measure X indexes consciousness but not drug effect" designs, not
just to ours.** The fix is an equivalence test with a stated margin in place of a failure to reject.

## T9 — **UNSTABLE. E342's "six of seventeen" is one draw, not a set.**

300 patient-level bootstrap resamples of the 18 Krause patients, re-running E342's P2 in each:

| measure | selection frequency | in E342's set |
|---|---|---|
| `AvgGamma` | **0.663** | yes |
| `EffDim` | 0.637 | yes |
| `NmlzCmplx` | 0.617 | yes |
| `allEnvCorr` | 0.457 | yes |
| `limbicDelta` | 0.247 | no |
| `temporalDelta` | 0.243 | no |
| `frontwPLI` | 0.237 | yes |
| `parietalDelta` | 0.213 | yes |
| `AvgDelta` | 0.210 | no |
| `frontalDelta` | 0.127 | no |
| others (7) | ≤ 0.057 | no |

**No measure is selected in more than two-thirds of resamples**, and 9 of 17 sit between 0.2 and 0.8.
Two consequences, in opposite directions:

- **E342's list must not be quoted as a list.** `frontwPLI` (0.237) and `parietalDelta` (0.213) are barely
  distinguishable from `limbicDelta` (0.247), `temporalDelta` (0.243) and `AvgDelta` (0.210), which E342
  classified as *not* dissociating.
- **E342's conclusion survives, and is strengthened.** The most stably-selected measure of all 17 is
  `AvgGamma` — a gamma **band power** — ahead of both complexity measures. Whatever this criterion
  selects, it is not selecting complexity, and that holds under resampling rather than at one draw.

Combined with T8: membership in this set is jointly a function of the true effect *and* of the measure's
noise, resampled at 18 patients. That is a small-n instability, and it is the honest ceiling on what the
Krause deposit can support.

## T10 — **NO CHANGE across the programme.**

Early half (2026-07-30 → 08-01, n = 94): P(gate_failed) = 0.202. Late half (08-01 → 08-07, n = 95):
**0.274**. Difference **+0.0716, p = 0.3134** — flat, drifting slightly *worse*, not significantly.

Registered in advance as a **time** trend and reported as one: catalogue size and calendar time are
perfectly collinear here, so nothing in this attributes the flatness to the catalogue (E343 limitation 3).
Note also the span is nine days, which is a short window in which to expect a practice effect.

---

## What this battery does to the metascience paper

**Strengthened, with numbers a referee would otherwise demand:** intervals at two clustering levels (T1);
the literature benchmark at 0.0 % against 24.0 % (T6); an alternative explanation removed (T5); and a
self-critical result that deflates the headline (T4).

**Weakened, and both must appear in the paper:** the effective n is **37 lineages, not 225** (T3), and the
outcome labelling is **still unaudited** because my independence check was not independent enough (T2).

**Not yet available:** a prospective sample (T7), which costs nothing but time.

**And two corrections travel back to the EEG line:** the dissociation criterion is noise-biased (T8), and
E342's dissociating set is unstable under patient resampling with `AvgGamma` — a band power — the most
stable member of it (T9).
