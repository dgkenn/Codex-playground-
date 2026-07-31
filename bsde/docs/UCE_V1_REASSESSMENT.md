# UCE v1 reassessed — what the §0 critique actually killed, and what it left standing

*Written 2026-07-31, after the investigator asked whether the construct was abandoned prematurely. Every
number below is either computed here or quoted from a source named with its PMID.*

---

## 1. The critique hit the weights. The contribution was never the weights.

`RESEARCH_STRATEGY.md` §0 established, by algebra and then confirmed on data:

* equal PCA loadings on two z-scored, positively correlated variables are **forced by symmetry** — the
  eigenvectors of `[[1,r],[r,1]]` are `(1/√2)(1,±1)` for every `r`;
* "96.8 % of variance explained" is exactly `(1+r)/2`, i.e. a restatement of **r(frontal, posterior) = 0.936**;
* therefore the score is approximately a whole-head aperiodic exponent.

Confirmed here on three independent cohorts, no outcome label consulted:

| cohort | n rows | r(uce_v1, whole_head_exponent) |
|---|---|---|
| eegmmidb resting | 210 | **+0.980** |
| ds004541 | 124 | **+0.882** |
| chennu propofol | 80 | **+0.962** |

**That is a real and correct critique of one claim: that the frontal/posterior decomposition is a
discovery. It is not.** But it says nothing whatever about the part of the construct that is actually
novel.

**The novel part is the frozen population reference.** `F_mean = -1.4321`, `F_SD = 0.5297`,
`P_mean = -1.4658`, `P_SD = 0.5187`, derived once from 1,170 BDSP sleep patients and never re-fit. The
literature this builds on — Gao 2017 on E/I balance, Lendner 2020 on sleep, Colombo 2019 on propofol/xenon/
ketamine, Leroy 2022 on LOC, Brake 2021, Donoghue 2020 on FOOOF — establishes that the aperiodic exponent
tracks consciousness. **None of it provides a universal reference against which a new patient on a new
system in a new country can be scored without recalibration.** That is what the frozen centroid does, and
the §0 critique does not touch it.

The PCA weights were the wrapping. The centroid is the object.

## 2. Collapsing to one feature makes the product claim stronger, not weaker

The investigator's own results already said this and were read as a limitation:

* a delocalization analysis found **any single electrode captures 91 %** of the full-montage information;
* a forward model explained **99 % of the frontal-posterior difference reduction (r = 0.96)** by volume
  conduction through the skull.

So the empirical work and §0's algebra agree, and they agree in the useful direction. **If the score is a
whole-head aperiodic exponent, the device needs one electrode, not two.** One disposable electrode is a
better clinical and commercial story than two — lower cost, faster application, fewer failure modes, and
no montage assumption to violate. The correct move is to drop the frontal/posterior language and describe
the construct as *a population-referenced whole-head aperiodic exponent*, which is both what it is and an
easier thing to defend.

## 3. The I-CARE failure may be a finding, and there is independent evidence for that

The reported behaviour on post-cardiac-arrest coma is **wrong-direction predictions**, currently explained
as "structural damage is a different pathophysiology". As stated that is a post-hoc scope limit, which is
weak. But the sibling programme in this repository has an independent, pre-registered result that predicts
it:

> **The prognostic meaning of intra-burst EEG content reverses by aetiology.** AUC for 30-day death is
> **0.589 [0.545, 0.633]** in anoxic patients and **0.408 [0.364, 0.452]** in non-anoxic — both intervals
> excluding 0.5, **on opposite sides**, no model involved. It survives burden strata (3/3), burst-count
> strata (3/3), and decomposition of the non-anoxic arm (4/4 subgroups below 0.5, clustered within 0.028).
> (`docs/research/41_RESULTS_LEDGER.md`, R389-R392; qualified by R409-R411 and R417-R418.)

A measure whose direction reverses by aetiology will give wrong-direction predictions **whenever
aetiologies are pooled**, which is exactly what happens on I-CARE — a cohort that is entirely cardiac
arrest and therefore cannot itself test an aetiology contrast at all.

**This converts a post-hoc excuse into a falsifiable prediction:** the frozen equation should mispredict
specifically in the anoxic arm and behave better in non-anoxic. I-CARE cannot test it. HEEDB, with 26,350
aetiology-labelled patients, can. **That is a real experiment and it is the single most interesting thing
in this reassessment**, because a failure that is *predicted in advance by an independent finding* is
evidence for the framework rather than against it.

Caution stated plainly: the reversal above is about **spectral balance in bursts**, not about the aperiodic
exponent, and R417/R418 established that absolute band power does *not* reverse while the ratio does. So
the two measures are related but not the same, and whether the reversal transfers to the aperiodic exponent
is an open question, not an assumption.

## 4. Two numbers that will not survive review, both fixable

### (a) ρ = −0.81 for the "pharmacodynamic sensitivity index" is mathematical coupling

The claim is that a 60 s pre-induction baseline predicts spectral change at LOC, ρ = −0.81, N = 2,647. If
"change" is computed as `slope_at_LOC − slope_baseline`, **the baseline appears on both sides of the
correlation** and the null is not zero. Simulated with **no true relationship whatever**:

| spread of LOC values relative to baseline | expected ρ(baseline, change) |
|---|---|
| equal | **−0.707** (analytic −0.707) |
| **0.7×** | **−0.819** (analytic −0.819) |
| 1.4× | −0.582 |

**−0.819 under a pure null is what was reported as −0.81.** And the direction is unforgiving: a genuine
positive relationship between baseline and LOC value makes the observed change-correlation *less* negative
(true ρ 0.2 → observed −0.632; 0.4 → −0.547). Anaesthesia compressing between-subject variability is
exactly what makes LOC values less variable than baselines, which is the 0.7× row.

**As stated, −0.81 is consistent with no predictive relationship at all.** This is Oldham's problem and a
reviewer will find it.

**The fix, and a correction to my own first version of it.** I initially recommended Oldham's method —
correlate the change against the *average* of baseline and LOC — and asserted its null was zero. **It is
not.** Under the null,

    corr( (a+b)/2 , a-b )  =  (var(a) - var(b)) / (var(a) + var(b))

which is zero **only when the two variances match**. Verified to three decimals: at a 0.6 spread ratio the
null is **-0.470**, at 1.6 it is **+0.438**. In exactly the situation that motivates this — an intervention
compressing between-subject variance — Oldham is still biased, just less so.

**Report `corr(baseline, LOC value)` instead. It is zero at every spread.** That is the statistic the
question was really asking anyway: *do patients with steeper awake baselines reach a different slope at
LOC?* `bsde/src/bsde/verifier/change_scores.py` computes all three side by side, each against its own
analytic null, with `tests/test_change_scores.py` checking those nulls against simulation. Run your own
baseline/LOC pairs through it — **I could not, because VitalDB's EEG strip goes on after induction and my
extraction contains no pre-induction windows at all** (0 of 6,439). If your baseline came from VitalDB,
that is worth confirming independently.

Do this before the meeting, not after.

### (b) The IFT alignment is precision the data cannot carry

Reported: UCE gives 44.9 % TIVA / 16.7 % volatile = **2.689**, against Linassi 2018's 48 % / 18 % =
**2.667** — "agreement to within 0.02". Bootstrapped:

| ratio | point | 95 % CI |
|---|---|---|
| Linassi IFT (n ≈ 565/arm) | 2.667 | **[2.21, 3.28]** |
| VitalDB UCE (2,925 / 1,124) | 2.689 | **[2.36, 3.10]** |

The intervals are ±0.3 to ±0.4 wide. Agreement to two decimal places is coincidence, and presenting it as
the headline invites a reviewer to discount the whole comparison. **The defensible version is still
good:** two ratios near 2.5–3.0, from a spectral biomarker on Korean surgical EEG and a behavioural gold
standard pooled across 22 international studies, **with no model fitting between them**. Say that.

## 5. The modification most likely to make it work

The central tension in the results as reported:

* **within** a person the score orders consciousness states very well — AUC 0.926 against behavioural
  labels in the Purdon data;
* **between** people the operating point moves enormously — Youden-optimal thresholds from **−0.30 to
  −2.09**, a spread of 1.8 SD on a scale whose whole selling point is that it is universal.

That is a between-subject nuisance-variance problem, and it is the same shape as the reliability ceiling
measured elsewhere in this project today: **a measure can order states perfectly within subjects and still
have its absolute value dominated by stable between-subject differences.**

**Concretely: keep the population SD, replace the population mean with the individual's own awake
baseline.**

```
Score = ( slope_now − slope_awake_baseline_this_patient ) / population_SD
```

* It stays calibration-free in the way that matters clinically — **no drug titration, no per-case tuning**,
  just 60 s of awake EEG that is already being recorded before induction.
* It directly attacks the −0.30 to −2.09 spread, which is the strongest objection to the current form.
* It costs the "zero is the population awake centre" framing, and gains "zero is *this patient's* awake
  state", which is what an anaesthetist actually wants to know.
* The investigator already measured this: personal calibration improved binary classification by ~7 %.
  **That should be the headline of the next version, not a footnote in the limitations.**

The population reference does not disappear — it still supplies the scale (`population_SD`), which is what
makes a score of −1.2 mean the same thing in Boston and Seoul. Only the origin moves.

## 6. What I would take to the meeting

1. **The construct, described correctly:** a population-referenced whole-head aperiodic exponent, one
   electrode, frozen reference from 1,170 patients, never re-fit.
2. **The transfer results**, which are the real contribution and are untouched by the §0 critique.
3. **The LOC boundary convergence** near −1.2 SD across independent datasets — the strongest single claim,
   and worth stating carefully because it is a claim about a *biological* boundary being visible on a
   *population-referenced* scale.
4. **The individual-baseline modification** as the proposed v2, with the 7 % as its supporting evidence.
5. **The I-CARE failure as a pre-registrable prediction**, citing the aetiology reversal.
6. Both problems in §4 **already fixed**, not defended.

What I would not take: the 0.696/0.718 weights as a finding, "96.8 % of variance" as evidence of a latent
axis, ρ = −0.81 in its current form, or the 2.68-versus-2.70 agreement as a precision claim.

**And the standing limitation that outranks all of the above: everything here is retrospective.** No
prospective patient has been tested. That is the sentence to say first, unprompted.
