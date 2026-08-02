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

The censoring is strongly agent-dependent. At BIS < 40:

| arm | n windows | median `alpha_peak_hz` | at the 8.0 Hz floor | at the 13.0 Hz ceiling |
|---|---|---|---|---|
| propofol | 494 | 9.75 | **8.91 %** | 0.00 % |
| volatile | 957 | 8.50 | **28.74 %** | 0.10 % |

**Two consequences.** The propofol-minus-sevoflurane peak separation at depth is a **lower bound, not an
estimate** — every peak that has actually moved below 8 Hz is recorded as 8.0. And the row for
`alpha_peak_hz` in the table above (sevoflurane deep−light −0.8283) is measured through a censored
instrument, so its magnitude should not be quoted without this caveat.

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

## Consequence for the programme

Alpha power is the single most-used feature in this project's Challenge C panel and it is a headline
measure in the anaesthesia EEG literature. If its depth sign is agent-dependent, then **any normative or
transportable depth measure built on alpha is agent-specific by construction**, and E210's finding that a
propofol-trained axis inverts on sevoflurane is the population-level shadow of that.
