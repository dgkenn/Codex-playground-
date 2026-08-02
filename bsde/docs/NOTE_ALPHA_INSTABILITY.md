# The alpha instability — two challenges pointing at one feature

*Written 2026-08-02. Every number below was recomputed by Opus against the raw source; two delegated
diagnostics produced them first and agreed to four decimal places.*

## The observation

Two independent lines of work arrived at the same feature from opposite directions.

**Challenge A (E210).** A depth axis fitted on propofol cases does not merely degrade on sevoflurane, it
**inverts**: cross margin **−0.1931** against a within margin of **+0.8319** (difference −1.0249
[−1.2819, −0.7676] over 71 paired cases). Decomposing that inversion, the two arms' axes are **near
orthogonal, not anti-parallel** — cosine(w_propofol, w_sevoflurane) = **+0.0968** — and exactly two of
the ten features move in *opposite directions with depth* between the agents:

| feature | propofol deep−light | sevoflurane deep−light |
|---|---|---|
| **alpha_peak_hz** | **+0.2452** | **−0.8283** |
| **relative_alpha_power** | **+0.3201** | **−0.5108** |
| lempel_ziv | −0.7014 | −0.5238 |
| relative_theta_power | +0.2923 | +0.5496 |
| exponent_low | +0.0647 | +0.8999 |
| whole_head_exponent | +0.2098 | +0.8400 |
| spectral_edge_95 | −0.0082 | −0.8835 |
| spectral_entropy | −0.2009 | −0.7768 |
| relative_delta_power | +0.2934 | +0.7051 |
| exponent_high | +0.3225 | +0.2179 |

Only `alpha_peak_hz` clears a stable-flip criterion (|mean| > 2 SD in both arms over 50 subsamples);
`relative_alpha_power` flips in 46 of 50 subsamples and clears easily on the propofol side (|m|/sd 5.26)
but not on the sevoflurane side (1.34). **Both are alpha measures. None of the other eight flips.**

> **CORRECTION, 2026-08-02 (E218): the inversion is ASYMMETRIC, and calling it an inversion overstates it.**
> Testing each arm against its own within-arm sign-flip null, `relative_alpha_power`'s deep-minus-light
> change is **−0.5211 against a floor of 0.2394 in sevoflurane — decisively alive** — and **+0.2273 against
> a floor of 0.3182 in propofol, which does NOT clear.** So what the table above shows as two arms pointing
> opposite ways is really **one arm moving and the other not detectably moving.** Every description of this
> finding in the programme's documents, including the sentences below, says "inverts" or "opposite
> directions"; read them with this correction. The arm GAP is real and survives (|G| 0.3742 against an
> arm-permutation p95 of 0.1901) — it is the two-sided reading of it that does not.

**Challenge C (E209).** Of the three DOSE-I survivors testable on ds005620, two replicate and one does
not — and the one that fails is **`relative_alpha_power`** (+0.0978 [−0.0405, +0.2334]), which had the
**largest** DOSE-I increment of the five (−0.03331). The two that replicate were smaller.

## Why the obvious explanation is wrong

The natural guess is redundancy with the incumbent. **It is refuted by measurement, and in the opposite
direction:**

| feature | pooled rho with `spectral_edge_95` | replicated? |
|---|---|---|
| relative_alpha_power | **+0.1074** (least redundant) | **no** |
| multiscale_entropy_slope | +0.1247 | yes |
| whole_head_exponent | **−0.8851** (most redundant) | **yes** |

The most redundant feature replicates; the least redundant fails. Redundancy orders these three almost
exactly opposite to replication.

What *does* order them is within-subject consistency:

| feature | within-subject label rho | sd | d_z | sign-consistent subjects |
|---|---|---|---|---|
| whole_head_exponent | +0.4434 | 0.2562 | **+1.7306** | 18/20 |
| multiscale_entropy_slope | −0.4196 | 0.3285 | **−1.2773** | 18/20 |
| relative_alpha_power | +0.2937 | 0.3138 | **+0.9360** | **15/20** |
| spectral_edge_95 (incumbent) | −0.2301 | 0.2958 | −0.7777 | 15/20 |

`relative_alpha_power` is the only one of the three whose |rho| does not separate from the incumbent's
(paired Wilcoxon p = 0.2627, against 0.0160 and 0.0042 for the two replicators).

## The claim, and its limits

**`relative_alpha_power` is unstable in the specific sense that its relationship to depth depends on the
agent** — measured directly in Challenge A on 115 VitalDB cases — **and it is the survivor that fails to
travel to a deposit with a different sedation protocol.** A feature whose depth sign is drug-dependent is
exactly the feature that should fail a cross-deposit replication, and it did.

**What this is not.** It is not a demonstration that the Challenge A inversion *causes* the Challenge C
failure: the two analyses use different cohorts, different labels and different estimators, and
`alpha_peak_hz` — the feature with the *stronger* stable flip — is in neither DOSE-I's nor ds005620's
panel, so the prediction it would generate cannot be tested here. The link is a consistency between two
measurements, not a mechanism.

**The forward prediction it does generate, and which is testable:** on any deposit whose sedation is
maintained with a halogenated agent rather than propofol, `relative_alpha_power` should track depth in the
*opposite* direction to its DOSE-I sign. That is falsifiable and no experiment here has used it.

## Addendum, 2026-08-02 — the mechanism was tested and REFUTED (E213)

*This section corrects an attribution made earlier the same day. Nothing above changes.*

### The premise, which is real and was measured first

`alpha_peak_hz` is computed as the **raw PSD maximum inside 8–13 Hz**. It therefore **cannot report a peak
below 8 Hz** and pins at the band floor instead. Measured over 6,437 finite VitalDB windows its range is
exactly **[8.000, 13.000]** with nothing outside — the estimator has no resolution outside the range it was
built over, which is catalogue rule 62 appearing in a new place.

The censoring is strongly agent-dependent. **The original version of this table stratified on BIS < 40 and
that was a mistake** — see the standing caution below — so it is given here on BOTH stratifications, and the
conclusion does not depend on which:

| stratification | arm | n windows | median `alpha_peak_hz` | at the 8.0 Hz floor | at the 13.0 Hz ceiling |
|---|---|---|---|---|---|
| BIS < 40 *(BIS-dependent, superseded)* | propofol | 493 | 9.75 | 8.92 % | 0.00 % |
| BIS < 40 *(BIS-dependent, superseded)* | volatile | 637 | 8.50 | 28.57 % | 0.16 % |
| **deep exposure tercile (no EEG index)** | **propofol** | **355** | **9.75** | **10.70 %** | **0.85 %** |
| **deep exposure tercile (no EEG index)** | **volatile** | **575** | **8.50** | **26.78 %** | **0.70 %** |

The floor-pinning excess in the volatile arm is 2.5-fold on the BIS-free stratification against 3.2-fold on
the BIS one, and the medians are identical. **Quote the exposure-tercile row.**

### STANDING CAUTION: BIS cannot serve as a depth anchor in this programme, for two independent reasons

1. **It is not equipotent across agents.** Kuizenga 2019 (PMID 31567365) puts the EEG-index value at which
   50 % of subjects lose a behavioural endpoint at **46.7 for propofol against 68 for sevoflurane**, and
   41.5 against 59.2, and 29.5 against 61.1, while the drug concentrations themselves are *"perfectly
   correlated (correlation coefficient = 1)"*. Two arms matched on BIS are therefore **not** matched on
   state, and any statement of the form "at equal BIS, the agents differ in X" is confounded by the depth
   they are actually at.
2. **It is computed from the same EEG.** BIS incorporates band-ratio terms, so residualising a spectral
   feature on BIS partly residualises that feature on itself. This is not a small effect for alpha measures
   specifically.

**Consequence for what is reported above.** The within-case table's *BIS-adjusted* column — sevoflurane
retaining 40 % of its raw association — is affected by BOTH problems at once: the adjustment removes
shared spectral construction, and it removes a different amount in each arm because the index is
non-equipotent. **It should not be quoted as a mediation estimate.** The RAW column involves no adjustment
and is the one that carries the finding: alpha tracks sevoflurane dose at −0.3827 [−0.467, −0.246] and does
not track propofol dose at +0.0416 [−0.003, +0.103].

**And this cohort has no clean depth anchor at all.** Every candidate is either an EEG index (problems 1
and 2) or the drug's own concentration (problem 1 by itself, since MAC and effect-site concentration are
not equipotent). Suppression ratio is 0.000 throughout, so it cannot serve either. That is a structural
limit on what any Challenge A analysis on VitalDB can establish about *depth*, as opposed to about *dose*.

**One consequence, and one that I got wrong and E218 corrected.** The row for `alpha_peak_hz` in the table
above (sevoflurane deep−light −0.8283) is measured through a censored instrument and its magnitude should
not be quoted without that caveat. That stands.

**WITHDRAWN:** I wrote here that the peak separation at depth is therefore a *lower bound*. It is not.
E218 measured the same quantity with an uncensored estimator (aperiodic-corrected peak searched over
5–15 Hz) on the same windows: the shift is **+1.38 Hz** (propofol 10.50, sevoflurane 9.12) against the
censored estimator's **+1.50 Hz** (10.00 vs 8.50). Slightly *smaller*, not larger — because censoring pins
**both** tails and removing it moves both arms' peaks upward. The lower-bound reasoning only considered the
floor. Note also that the uncensored sevoflurane peak of 9.12 Hz is materially closer to Akeju 2014's
*"approximately 10 Hz"* for both agents than 8.50 was, so the censoring accounts for part of that
disagreement without removing it.

### The mechanism this suggested, and why it does not survive

A peak sitting on the band's lower edge loses its lower skirt into theta, so a fixed 8–13 Hz window
under-counts sevoflurane's alpha at depth **for arithmetic reasons, with no biology involved.** That would
explain the inversion, the Challenge C replication failure, and why both land on alpha and nothing else.

**E213 tested it and it is ABSENT.** Restricting to the cases whose deep alpha peak is off the floor (58
sevoflurane, 42 propofol, threshold derived as one PSD bin — 0.125 Hz — above 8.0) moves the oriented arm
gap only from **+0.3742 to +0.3432**, a change of **−0.0310**, which is the **18.8th percentile** of a null
built by removing the same number of cases at random from each arm (rule 35). All three gates passed: the
inversion is alive (|G| 0.3742 vs an arm-permutation p95 of 0.1901) and the restriction is genuinely
arm-specific (pinning 18.31 % sevoflurane vs 4.55 % propofol).

**The placebo is the informative part.** `spectral_entropy`, which has no arithmetic dependence on where the
alpha peak sits, attenuated **more** than the primary (−0.0646, 2.3rd percentile), and the declared positive
control `relative_theta_power` did not show the predicted mirror (−0.0162, 34.5th percentile). So the
restriction does something mildly non-specific to the cohort and does **not** act on the alpha band in
particular.

**Withdrawn:** an ad-hoc diagnostic run earlier on 2026-08-02 reported the depth peak shift (propofol
10.00 Hz vs sevoflurane 8.50 Hz) as *confirming* band placement as the mechanism. The numbers stand; the
attribution does not survive its own control and is withdrawn. This is catalogue rule 50 exactly —
**measuring a difference is not measuring its cause**, and it was the matched-size baseline that separated
them. The sentence in "What this is not" above — *the link is a consistency between two measurements, not a
mechanism* — is now the correct summary of the whole note, and it survived the one serious attempt to
replace it.

**What E213 cannot say.** It removed *cases*; it did not build a peak-anchored *measure*. No per-window
spectra were stored anywhere in this deposit — only scalar summaries — so a band anchored to each
recording's own peak needs re-extraction. That is a successor, not a rescue clause, and its prior is now
lower than it was.

## Addendum 2, 2026-08-02 — two mechanisms REMOVED before they were proposed

*Cohort diagnostics run on E186's 115 clean single-agent cases, using only `meta_*` columns — BIS,
suppression ratio, EMG, age, BMI, ASA and the exposure itself. No alpha measure is touched. Run BEFORE
E218's result existed.*

A literature search was commissioned for candidate mechanisms that could make two GABAergic anaesthetics
disagree about the DIRECTION of an EEG-depth relationship. Two of the leading candidates can be checked
directly on this cohort, and **both are refuted here**, which narrows the search before it starts.

### The arms are at the same BIS — but that does NOT close the non-equipotent-scale explanation

**CORRECTED the same day.** The heading below originally read "the non-equipotent-scale explanation is
unavailable" and that was wrong, for a reason a verified citation supplies. Kuizenga 2019
(**PMID 31567365**, *Anesthesiology*, healthy-volunteer crossover) reports the EEG index value at which
50 % of subjects lose a behavioural endpoint as **46.7 for propofol against 68 for sevoflurane**, and
**41.5 against 59.2**, and **29.5 against 61.1** for three endpoints — while the drug concentrations
themselves are *"perfectly correlated (correlation coefficient = 1)"* for two of them. **An EEG index sits
at radically different values at matched behavioural depth between these two drugs.**

So matching the two arms on BIS, which is what the diagnostic below does, is precisely NOT matching them on
state. If anything the diagnostic's result — that BIS agrees between arms — implies under Kuizenga that the
*behavioural* depths differ. **Non-equipotent depth scales survives as the leading candidate, not the
refuted one.** What the diagnostic does establish is that the arms are matched on age, ASA and the monitor's
own reading, which removes the cruder versions of the confound.

The deep and light terciles are defined by EXPOSURE — MAC for sevoflurane, effect-site concentration for
propofol — and there is no guarantee that a tercile of MAC and a tercile of Ce reach the same cortical
state. If sevoflurane's "deep" arm were simply lighter, the arms would not be comparable and the inversion
could be a depth mismatch. Measured, as medians over cases with a case bootstrap on the difference:

| quantity | propofol | sevoflurane | difference | 95 % CI |
|---|---|---|---|---|
| **BIS in the DEEP tercile** | 38.86 | 40.06 | −1.20 | [−3.43, +1.84] |
| BIS in the LIGHT tercile | 44.87 | 47.06 | −2.20 | [−6.59, +4.11] |
| age (years) | 59.5 | 58.0 | +1.5 | [−5.00, +11.00] |
| ASA | 2.0 | 2.0 | 0.0 | [−1.00, +0.00] |
| BMI | 24.5 | 22.8 | +1.7 | [+0.15, +2.85] |

A permutation test on the deep-tercile BIS difference gives **p = 0.4276**. The two arms reach the same
depth by the monitor's own reckoning, at the same age and the same ASA. **BMI differs slightly** and is the
one imbalance worth carrying forward; it is not an obvious route to a sign reversal.

### The deep end is not burst suppression — the deep-end-behaviour explanation is unavailable

A second candidate is that the two agents reach burst suppression at different points on their own scales,
so that one arm's "deep" contains qualitatively different EEG. The median suppression ratio is **0.000 in
every tercile of both arms**, and only 14 of 44 propofol cases and 10 of 71 sevoflurane cases show any
suppression at all in either tercile. This cohort's deep end is oscillatory anaesthesia, not suppression,
in both arms.

### Two more mechanisms tested directly, 2026-08-02 (mechanism triage, 2 tests, count stated)

A verified literature review ranked six candidate mechanisms. Two carry predictions testable on this
cohort, and both were run:

* **Burst suppression differing by agent** (Kenny 2014, PMID 25565990: *"the circuit mechanisms that
  generate burst suppression activity may differ among general anesthetics"*). Prediction: the arm gap
  should be **absent or smaller** with suppression-containing cases excluded. Measured, it is **larger** —
  −0.4792 [−0.7302, −0.2082] against −0.3742 on all cases. **REFUTED**, and by catalogue rule 17's pattern:
  when a fix makes the effect stronger, the diagnosis was wrong.
* **Off-target receptor actions of the volatile** (Solt & Forman 2007, PMID 17620835: *"Volatile halogenated
  anesthetics show little selectivity for molecular targets. They act on all the channels mentioned above"*
  — i.e. sevoflurane engages the same glutamate and TREK-1 targets as the drug class behind every
  precedented EEG reversal, and propofol does not). Prediction: the effect should **scale with MAC** within
  the sevoflurane arm and be much weaker below 1 MAC. Measured: **−0.4667 below the median MAC of 1.100 and
  −0.6154 above it**, both far beyond their sign-flip floors. It is present at low dose, so this is **weak
  support at best** and arguably counts against the prediction as stated.

### Two further diagnostics, 2026-08-02 — one control passes, one reframes the finding

**A negative control passes, and the check that made it readable nearly did not happen.** Re-ordering each
case's windows by TIME instead of by drug concentration collapses everything: the arm gap falls from
−0.3742 to −0.0925 and sevoflurane's effect from −0.5211 to +0.0423. It would be tempting to read that as
evidence about mechanism. **It is not**, because the time split carries no depth content at all — the
BIS difference between its "deep" and "light" terciles is **−0.04 [−1.72, +2.02]** in sevoflurane, with
exactly 50.0 % of cases in the expected direction, against **−8.03 [−10.64, −5.50]** for the exposure
split. An ordering with no depth in it produces no effect, which is the tercile machinery working, and
nothing more. (Rule 53 again: check the contrast is alive before reading its null.)

**The window-level asymmetry, which is the sharpest statement of the finding so far.** Within each case,
across all its windows, correlating alpha against that case's own drug concentration:

| arm | n cases | rho(alpha, own exposure) | after adjusting for BIS | retained |
|---|---|---|---|---|
| propofol | 44 | **+0.0416 [−0.003, +0.103]** | +0.0350 [−0.043, +0.109] | 84 % |
| sevoflurane | 68 | **−0.3827 [−0.467, −0.246]** | −0.1527 [−0.238, −0.025] | 40 % |

**Alpha tracks sevoflurane dose and does not track propofol dose.** Propofol's interval includes zero both
before and after adjustment; sevoflurane's is decisively negative. This is a cleaner statement than
"inversion": the two agents do not disagree about alpha, one of them has an alpha–dose relationship and the
other does not detectably have one in this cohort.

**The BIS adjustment cannot be read as mediation, and that is a limitation not a result.** Sixty per cent of
sevoflurane's association disappears when BIS is adjusted for, which would be a tidy "most of it runs
through depth" story — except that **BIS is itself a spectral index computed from the same EEG**, and
incorporates band-ratio terms. Residualising alpha on BIS therefore partly residualises alpha on itself,
and this cohort has no non-EEG depth anchor (suppression ratio is 0.000 throughout) to substitute. The 40 %
that survives is a lower bound on the drug-specific component only if that shared-construction problem is
ignored, which it should not be. **What survives the caveat entirely is the propofol/sevoflurane asymmetry
in the RAW column, which involves no adjustment at all.**

### Candidate 6 tested: co-medication is a REAL imbalance and does NOT explain the finding

The literature search found no published comparison of co-medication between propofol-TIVA and volatile
cohorts and said so. The cohort answers it directly, and the imbalance is large:

| co-medication | propofol | sevoflurane | difference | 95 % CI |
|---|---|---|---|---|
| **remifentanil Ce** | **3.504** | **1.503** | **+2.001** | **[+1.568, +2.492]** |
| rocuronium | 90.0 | 75.0 | +15.0 | [+0.0, +27.5] |
| midazolam, vecuronium, emergency status | 0.0 | 0.0 | 0.0 | — |

Propofol cases run at **2.3× the remifentanil** of sevoflurane cases — the ordinary TIVA practice pattern.
Two routes by which that could manufacture the asymmetry were tested and both fail.

**Route 1, dose range: REFUTED.** If opioid-sparing compressed the propofol dose range there would be
nothing for alpha to track. The arms' dose variation is **identical** — coefficient of variation 0.341
against 0.355, difference −0.014 [−0.059, +0.042]; relative IQR 0.203 against 0.207, difference −0.005
[−0.066, +0.055]. Both intervals span zero. Propofol in fact has *more* distinct exposure values per case
(18.5 against 11.5), because effect-site concentration is continuous where MAC is coarse. Restricting both
arms to the propofol arm's interquartile CV band leaves the asymmetry untouched: propofol +0.0657 [−0.0247,
+0.1551], sevoflurane −0.3204 [−0.4780, −0.2294].

**Route 2, a direct pharmacodynamic opioid effect: NOT SUPPORTED.** Restricting both arms to their
overlapping remifentanil band [1.66, 5.51] — which costs 62 % of the sevoflurane arm and almost none of the
propofol arm — the sevoflurane effect **survives at −0.4784 [−0.6442, −0.0388] on 15 cases**. Within each
arm, higher opioid associates weakly with a more negative alpha–dose relationship (−0.25 propofol, −0.19
sevoflurane), in the **same direction in both**, so it is not an agent-specific mechanism.

*Reported and not over-read:* in the opioid-matched band the propofol association is +0.1091 [+0.0114,
+0.2077], an interval that marginally excludes zero on 41 cases where the unmatched estimate did not. That
is a weak shift on a lower bound of +0.011 and is **not** a basis for reinstating the two-sided "inversion"
reading. What the matched comparison establishes is the negative: **remifentanil does not explain the
sevoflurane effect.**

### What that leaves

Of the six candidate mechanisms, the cohort removes **differential burst suppression** (tested and refuted
above) and largely removes **age** — Purdon 2015 (PMID 26174300) reports the age effect running in the
*same* direction for both drugs, and this cohort's arms are age-matched. **Non-equipotent depth scales is
NOT removed and is now the leading candidate**, on Kuizenga's evidence above. Off-target volatile receptor
action is weakly supported at best. E213 removed **band
placement**. What remains, and is not testable on this cohort alone, is a genuine difference in the
generator of the alpha rhythm, an off-target receptor action of the volatile, or systematic co-medication.
**Two of those three are testable with case-level data that already exists** and are the obvious successors.

---

## Consequence for the programme

Alpha power is the single most-used feature in this project's Challenge C panel and it is a headline
measure in the anaesthesia EEG literature. If its depth sign is agent-dependent, then **any normative or
transportable depth measure built on alpha is agent-specific by construction**, and E210's finding that a
propofol-trained axis inverts on sevoflurane is the population-level shadow of that.
