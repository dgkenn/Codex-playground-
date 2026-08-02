# Challenge A reframed: it was never an alpha story, and it may not be a biology story

*2026-08-02. Supersedes the framing in `NOTE_ALPHA_INSTABILITY.md`, which is left intact as the record of
how the question was arrived at. All numbers recomputed by Opus against the raw source.*

## The scan that should have been run first

Every Challenge A experiment in this programme has asked about `relative_alpha_power`, because that is
where the effect was first noticed. **Nobody asked whether the effect is specific to it.** It is not.

Within-case median Spearman between each feature and that case's own drug concentration, by arm — a
statistic that never crosses a patient boundary, uses no depth anchor, and involves no BIS:

| feature | propofol | sevoflurane | difference |
|---|---|---|---|
| `exponent_low` | +0.0222 | **+0.5061** | +0.4838 |
| `multiscale_entropy_slope` | +0.1321 | **+0.5515** | +0.4194 |
| `alpha_peak_hz` | +0.0703 | **−0.3475** | −0.4178 |
| `spectral_edge_95` | −0.0628 | **−0.4496** | −0.3868 |
| **`relative_alpha_power`** | **+0.0960** | **−0.2778** | **−0.3737** |
| `critical_slowing_ar1` | +0.1504 | **+0.5147** | +0.3643 |
| `emg_beta_gamma_fraction` | −0.0709 | −0.4185 | −0.3476 |
| `relative_delta_power` | +0.0978 | +0.3577 | +0.2599 |
| `spectral_entropy` | −0.0845 | −0.3370 | −0.2524 |
| `whole_head_exponent` | +0.0836 | +0.3353 | +0.2517 |
| `relative_theta_power` | +0.1034 | +0.2999 | +0.1965 |
| … 6 more, all \|difference\| < 0.11 | | | |

**`relative_alpha_power` ranks 5 of 17** on the size of the asymmetry — the 76.5th percentile. Four features
show a larger one, and eleven show a substantial one.

## What the table actually says

Read the **propofol column**: every one of seventeen features sits between −0.26 and +0.15. Read the
**sevoflurane column**: values reach ±0.55. The finding is not that alpha behaves differently between
agents. It is:

> **Within a case, EEG features track sevoflurane concentration and do not track propofol concentration —
> across essentially the whole panel.**

That is one fact about the exposure variable, not seventeen facts about seventeen measures, and it is far
more parsimonious than any of the six mechanisms tested and refuted so far.

## The most likely explanation is provenance, not biology

The two exposures are not the same kind of quantity, and the repo's own extraction documents say so:

| arm | variable | what it is |
|---|---|---|
| propofol | `Orchestra/PPF20_CE` | **the infusion pump's own MODELLED effect-site concentration** — a deterministic function of the infusion history through a PK model |
| sevoflurane | `Primus/EXP_SEVO` | **a MEASURED end-tidal gas concentration** |

A modelled concentration cannot carry information the model does not have. It is smooth by construction and
contains no physiology beyond what the infusion record implies. A measured gas concentration carries real
breath-to-breath variation, and that variation is coupled to the patient's actual state.

**Two independent observations already in hand fit this and nothing else needs to be invoked.** The two
exposures have *identical* within-case variability — coefficient of variation 0.341 against 0.355, interval
spanning zero — so this is not about how much the dose moved. And each exposure's ability to track its own
depth index differs in the same direction: within-case rho against BIS is **−0.3359 for propofol Ce** and
**−0.4973 for sevoflurane end-tidal**. The propofol exposure is simply the weaker instrument.

## What this does to the earlier work

* **The "alpha instability" framing is superseded.** Alpha is one of eleven features showing the same thing
  and it is not the largest. Every experiment that treated alpha as the object of study — E213, E214, E216,
  E218 — was investigating a general property through one arbitrary window on it. Their verdicts stand;
  their framing does not.
* **The six refuted mechanisms are refuted for a better reason than they were.** Band placement, burst
  suppression, age, dose range, co-medication and non-equipotence were all tested as explanations of an
  *alpha* effect. None of them could ever have explained an effect that appears in seventeen measures at
  once, including muscle and complexity measures with no band structure at all.
* **E220's identifiability result is unaffected and remains the strongest methodological finding.** The
  agent main effect is not identifiable when each patient receives one agent, whatever the feature.

## THE PREDICTION WAS TESTED THE SAME DAY AND IT LARGELY FAILS

The test below was run. **Provenance moves the number in the predicted direction and is nowhere near large
enough to explain the asymmetry.**

VitalDB carries two volatile exposures with different provenance, so the instrument can be degraded without
touching the cohort: `Primus/EXP_SEVO` is **end-tidal** — measured gas leaving the patient, carrying uptake
and therefore physiology — while `insp_sevo` is **inspired**, essentially the vaporiser's delivered
setting, which carries none. Median per-case |rho| against the drug's own concentration, over six features:

| exposure | provenance | mean \|rho\| |
|---|---|---|
| propofol `Ce` | **pump PK-model output** | **0.0912** |
| sevoflurane **inspired** | delivered setting | **0.4192** |
| sevoflurane MAC | monitor-derived from end-tidal | 0.4392 |
| sevoflurane **end-tidal** | **measured** | **0.4925** |

**Within the sevoflurane arm the ordering is exactly as predicted and monotone** — measured 0.4925 >
monitor-derived 0.4392 > delivered 0.4192 — so provenance is real and it costs about **15 %** of tracking
when a measured exposure is replaced by a delivered one.

**But the worst sevoflurane exposure still tracks the EEG 4.6 times better than propofol's modelled Ce.**
Degrading the volatile instrument as far as this deposit allows closes almost none of the gap. Provenance
is a contributor and not the explanation, and the headline of this note as first written was wrong.

*Caveat that cuts against the test rather than for it:* inspired sevoflurane is still a MEASURED gas
concentration, just one that does not reflect uptake. It is not a model output, so it is an imperfect
analogue of propofol's Ce and the 15 % is a LOWER bound on what full modelling would cost. It would have to
be a thirty-fold underestimate to close a 4.6-fold gap.

**What this leaves.** The scan's central observation stands and is unexplained: within a case, EEG tracks
sevoflurane concentration and does not track propofol concentration, across the whole panel. Smoothness is
not the reason either — the two exposures have matched within-case variability (CV 0.341 vs 0.355) and
propofol in fact has MORE distinct values per case (18.5 vs 11.5), so it is not a coarse staircase.

## The original prediction, kept for the record

If provenance is the cause, then **a propofol exposure that is MEASURED rather than modelled should track
the EEG as well as sevoflurane's does.** VitalDB does not carry measured plasma propofol. Two routes exist:

1. **A deposit with measured propofol concentrations.** Chennu's cohort carries `meta_plasma_propofol` —
   an assayed concentration, not a pump model — and this programme has already used it. On that deposit the
   prediction is that within-case tracking is comparable to sevoflurane's here.
2. **Degrade the sevoflurane exposure to match.** Replace measured end-tidal with a *modelled* volatile
   concentration derived from the same record and re-run. If the asymmetry shrinks, provenance is doing the
   work.

Route 2 is the stronger test because it changes only the instrument, and it needs no new data.

---

## CORRECTION, 2026-08-02 (same day): the gap is 2.30x, not 4.6x, and the statistic was doing part of the work

The "4.6 times" headline above compares 0.0912 against 0.4925. Both numbers are real, and the comparison
between them is not clean, for two reasons found while building E224:

1. **The arms were not mutually exclusive.** The sevoflurane arm (n = 70) allowed cases that also received
   propofol; 101 of 250 VitalDB cases carry both. Recomputed on arms that are disjoint by construction —
   propofol-only (n = 44) against sevoflurane-only (n = 86) — and on one fixed 15-column panel for both:

   | statistic | propofol | sevoflurane | ratio |
   |---|---:|---:|---:|
   | mean over features of \|median signed rho\| | 0.1402 | 0.3225 | **2.30x** |
   | mean over features of per-case \|rho\| | 0.2466 | 0.3663 | **1.49x** |

2. **The two rows are different statistics and the difference is informative, not a nuisance.** The first
   cancels when a feature's direction varies between patients; the second does not. That propofol's ratio
   between them (0.1402 / 0.2466 = 0.57) is well below sevoflurane's (0.3225 / 0.3663 = 0.88) is the
   observation E225 was registered to test: **propofol's coupling may be real per patient and inconsistent
   in direction across patients**, which a population summary averages away.

Two panel columns, `spatial_participation_ratio` and `wpli_alpha`, are non-evaluable on this table in 0 of
130 cases and are excluded from both rows (rule 74). VitalDB is single-channel, which is why.

**The direction of the finding is unchanged and the magnitude is roughly halved.** The EEG panel still
tracks sevoflurane substantially better than propofol on a like-for-like cohort. What has to go is the
"4.6-fold" figure, and with it the argument at the end of §"The most likely explanation is provenance"
that a 15 % provenance effect "would have to be a thirty-fold underestimate" — against 2.30x it would have
to be about fifteen-fold, which is still decisive but is a different sentence.

### What E224 then established, with every gate passing

* **Restriction of range is refuted, not merely named** (rule 54). Within-case exposure dispersion,
  IQR/median, is **0.2217 for propofol against 0.2500 for sevoflurane — a ratio of 0.887**. Propofol is
  titrated across nearly as wide a relative range as sevoflurane in these cases.
* **A better exposure model buys nothing.** A ke0 sweep over eight half-lives, each a complete
  one-compartment model driven by the recorded infusion, improves on the pump's own Ce by
  **+0.0965 [+0.0708, +0.1215]** against a max-of-eight selection inflation **measured on matched noise at
  +0.1155**. The gain does not exceed what picking the best of eight buys on pure noise.
* **The sevoflurane arm is alive and the propofol arm is not.** Sevoflurane beats a circular-shift floor at
  p < 0.0005; propofol's coupling is **not distinguishable from an exposure donated by an unrelated
  patient** (0.2466 against a donor-mean null of 0.2253, p = 0.0650). E224 is therefore NOT INTERPRETABLE
  by its own registered rule, because rule 48 forbids reading a null as a pass.

So readings (i) exposure-model quality and (ii) restricted range are both unsupported, and the live
question is no longer *why does the model track propofol badly* but *is there anything there to track*.

---

## SECOND CORRECTION, 2026-08-02: this note's own headline is wrong, and alpha is back

The title of this note says Challenge A "was never an alpha story". **E227 shows it is.** All four gates
pass, including the control that refused E225.

| arm | features clearing the donor null on CONSISTENCY | on STRENGTH |
|---|---:|---:|
| propofol | **12 / 15** | 3 / 15 |
| sevoflurane | 11 / 15 | 11 / 15 |

Consistency here is a resultant length, `|mean signed rho| / mean |rho|`, bounded in [0, 1], compared
against a donor null measured per feature. The propofol arm's coupling is therefore **directionally
reliable across patients and small in magnitude** — not absent, and not sign-scrambled. E225's
sign-varying hypothesis is refuted by its successor.

**And the direction is shared.** Of the 10 features clearing consistency in *both* arms, **9 agree in
sign** (exact binomial p = 0.0107 against 50/50). The single disagreement:

| feature | propofol mean signed rho | sevoflurane mean signed rho |
|---|---:|---:|
| `relative_alpha_power` | **+0.1079** | **−0.2482** |

**`relative_alpha_power` is the one directional reversal in the panel**, and it is the feature this whole
thread started from. The scan at the top of this note was right that alpha ranks only 5th on the size of
the propofol–sevoflurane *difference* — but size of difference was the wrong statistic, because a feature
can differ by magnitude while pointing the same way. On the question that actually distinguishes a
biological reversal from an instrument-quality gap, alpha is not 5 of 17. **It is 1 of 1.**

### What replaces this note's framing

The panel-wide propofol/sevoflurane difference is **a difference of MAGNITUDE with direction preserved** —
consistent with the exposure-quality reading, and with E224's finding that neither a better ke0 nor
restricted range explains it. Sitting *inside* that is one feature that genuinely reverses. Those are two
separate phenomena and this note collapsed them into one.

The sentence to retire is "it was never an alpha story". The correct one is: **the whole-panel difference
is not an alpha story, and the reversal is.**

---

## THIRD CORRECTION, 2026-08-02: the arms were wrong, and fixing them strengthens the reversal

Every propofol number above — including the 2.30x in the first correction and the 12/15 in the second —
came from **44 of 114 eligible cases**. The arm predicate in E224, E225 and E227 asked whether a VitalDB
track KEY existed. An anaesthesia machine logs its sevoflurane and desflurane channels whether or not the
vaporiser is ever opened, so 73 propofol cases carrying an all-zero volatile track were discarded as
combined-technique. Catalogue rule 6, now written up as rule 87.

| arm | by key presence | by `max(value) > 0` |
|---|---:|---:|
| propofol-only | 44 | **114** |
| sevoflurane-only | 90 | 88 |
| genuinely both | 101 | **31** |
| desflurane-only | — | 14 |

**The correction is one-sided**: it barely touches the comparison arm, and it selected on the anaesthesia
machine — a property of the theatre, not of the patient or the drug — which rule 14 forbids treating as
innocent.

### E229: everything moves the same way

| | E227 (n=44) | E229 (n=114) |
|---|---:|---:|
| propofol features clearing the donor null on CONSISTENCY | 12 / 15 | **14 / 15** |
| propofol features clearing it on STRENGTH | 3 / 15 | **7 / 15** |
| sevoflurane, consistency / strength | 11 / 11 | 12 / 11 |
| direction agreement among features consistent in both arms | 9 / 10, p = 0.0107 | **10 / 11, p = 0.0059** |
| whole-panel gap, mean \|mean signed rho\| | 2.30x | **1.73x** |
| `relative_alpha_power`, propofol vs sevoflurane | +0.1079 / −0.2482 | **+0.1189 / −0.2482** |

**Two things follow, and they point in opposite directions.**

The whole-panel magnitude gap is **smaller than reported at every stage** — 4.6x, then 2.30x, now 1.73x —
and the propofol arm's strength passes more than double, from 3 to 7 of 15. Much of what read as "the EEG
does not track propofol" was seventy missing cases.

**The reversal is not that.** `relative_alpha_power` is still the single feature pointing the opposite
way, on 2.6 times the data, with a smaller p, and it clears its own donor null in both arms (0.4786
against 0.2438 in propofol; 0.6958 against 0.2285 in sevoflurane). A correction that shrinks the
whole-panel effect and leaves the reversal standing is the best evidence so far that the two are
different phenomena — which is what the second correction argued on much weaker grounds.

### What is still not established

E228 tried to hold the patient constant and could not: the genuinely combined cohort is 31 cases, and of
those only 17 have both exposures varying across the EEG windows and only 1 has a usable epoch of each.
**The reversal has never been tested within a patient**, and no VitalDB design can do it. That is now the
binding constraint on Challenge A, and it needs a deposit where one patient receives both agents with EEG
throughout — a crossover volunteer study, not a surgical registry.

---

## FOURTH CORRECTION, AND IT RETRACTS THE FINDING: the reversal is BAND PLACEMENT

*E233, 2026-08-02. This section supersedes the second and third corrections above, both of which argued
that the reversal was a separate phenomenon from the whole-panel magnitude gap. It is separate. It is
also not a fact about the drug.*

`relative_alpha_power` is power inside a **fixed** 8–13 Hz window over total power. It measures how much
of the spectrum falls in a box, not the state of an oscillation. `relative_alpha_power_iaf` measures the
same quantity in a ±2 Hz band centred on **each recording's own** measured peak. On the identical 6,679
windows and the identical 114 vs 87 cases:

| measure | propofol vs sevoflurane contrast | clears its donor null? |
|---|---|---|
| `relative_alpha_power` (fixed box) | **+0.3673 [+0.2754, +0.4584]** | both arms |
| `relative_alpha_power_iaf` (follows the peak) | **+0.0730 [−0.0107, +0.1584]** | **propofol only — fails in sevoflurane (0.0276 vs 0.2715)** |

**Substituting the anchored measure, direction agreement goes from 10 of 11 to 10 of 10. The panel has
no reversal left in it.**

### The mechanism, measured rather than supposed

| arm | `alpha_peak_hz_wide` mean signed rho | consistency vs its null |
|---|---:|---|
| sevoflurane | **−0.3296** | 0.8204 vs 0.2770 — **clears** |
| propofol | −0.0226 | 0.0970 vs 0.3163 — **fails** |

**Sevoflurane slides the alpha peak downward as dose rises. Propofol does not move it.** A stationary
8–13 Hz window therefore reports "alpha power falling" for sevoflurane when what is falling is the
peak's position relative to the window, while for propofol the same window tracks real power. Two arms
whose peaks behave differently relative to a fixed box will produce opposite-signed correlations with no
difference in the rhythm at all — which is exactly what was observed and reported for several rounds.

### What survives and what does not

**Does not survive:** "alpha is the one measure that reverses between the agents." That sentence, in
E229, E232, the second and third corrections above, and everything in `NOTE_ALPHA_INSTABILITY.md`
descended from it, is a statement about band placement.

**Survives:** the whole-panel finding, which never depended on alpha. Ten measures clear a donor null in
both arms and all ten agree in direction, with sevoflurane's magnitudes roughly two to three times
propofol's — a difference of degree, not of kind. And a NEW, cleaner fact replaces the retracted one:
**sevoflurane produces a measurable, consistent downward shift of the alpha peak that propofol does
not.** That is a statement about an oscillation rather than about a window, and it is what should be
carried forward.

### Why this was not caught earlier, and the general lesson

The instrument was built for exactly this on 2026-08-02 — `alpha_peak_hz_wide`,
`relative_alpha_power_iaf`, and `tests/test_iaf_capability.py`, which measures that the fixed band
collapses more than fivefold when an unchanged 10 Hz oscillation moves to 7 Hz. **It was then not
pointed at the finding for four experiments,** while E228, E230, E231 and E232 tested confounders of the
COHORT — patient identity, case mix, opioid — none of which could ever have detected an artefact of the
MEASURE. Restriction and matching cannot repair a definition. The check that settled it in one run was
available the entire time.

---

## The propofol null is defended, 2026-08-02 (E237 and its follow-up)

E237 established that `alpha_peak_hz_wide` returns a **finite peak on pure 1/f background in 87.5 % of
draws**. That makes VitalDB's 93 % detectability rate uninformative as evidence of real alpha, and it
raised a specific ambiguity about the one surviving Challenge A finding: propofol's *null* peak-dose
relationship (−0.0226, consistency 0.0970 against a null of 0.3163) could mean the peak does not move,
or it could mean propofol windows carry too little alpha for the estimator to track anything.

**Measured directly, using the anchored alpha power already cached as a peak-prominence proxy:**

| arm | n | anchored alpha power, median [IQR] | peak-NaN rate |
|---|---:|---|---:|
| propofol | 114 | **0.1972** [0.1531, 0.2610] | 0.0696 |
| sevoflurane | 88 | 0.1906 [0.1330, 0.2318] | 0.0725 |

Cohen's *d* (sevoflurane minus propofol) = **−0.3325**, arm-permutation |p| = **0.0012**.

**Propofol windows have MORE power at their own peak, not less**, and the two arms' peak-detection
failure rates are indistinguishable (0.0696 vs 0.0725). So the propofol null is not an artefact of
absent alpha — if anything the estimator had a better peak to track in the propofol arm and still found
no dose relationship. The asymmetry stands: **sevoflurane slides the alpha peak downward with dose and
propofol does not.**

Two limits remain attached to that sentence. The sevoflurane half is **already published** — Hayashi
2008 (PMID 18431119, verified against MEDLINE) reports 11.0 → 9.8 → 8.7 Hz across 1 %→2 %→3 %
sevoflurane — and the static endpoint is independently corroborated by Shen 2026 (PMID 42131603,
8.78 vs 10.88 Hz). Only the propofol dose-response half is unaddressed in the literature. And this is
still a between-patient comparison; no public deposit can make it within-patient.

---

## WITHDRAWAL, same day: "the propofol null is defended" does not stand as argued

The section above defends E233's propofol null with two pieces of evidence. **An audit of every
peak-dependent claim found that one of them is an inference E237 refutes one section earlier in this
same document, and that the other is weaker than it was presented as being.** Both are withdrawn here.

**Leg 2, invalid.** I wrote that "the two arms' peak-detection failure rates are indistinguishable
(0.0696 vs 0.0725)" as evidence that propofol windows carry real alpha. E237 had already established, in
the section directly above, that this estimator returns a finite peak on **signal-free 1/f background in
91.5 % of draws** — so a low NaN rate is what the instrument produces from noise and carries no
information about whether alpha is present. Using availability as evidence of signal is precisely the
error rule 91 was written from, committed against my own finding.

**Leg 1, weaker than stated.** `relative_alpha_power_iaf` is power in a ±2 Hz band over 1–45 Hz total.
Under a 1/f background a 4 Hz window sitting near 9–10 Hz carries a substantial fraction of that total
whether or not any oscillation exists, so a median of 0.1972 does **not** establish a real peak. It is a
band-occupancy number, not a prominence number, and I presented it as the latter.

**What the position actually is.** The propofol null in E233's A1 arm — peak frequency not tracking
propofol dose — remains **ambiguous** between "the peak does not move" and "there is too little alpha
for the estimator to track anything". Nothing above settles it.

**What would settle it**, and it is now buildable: E239 validated a prominence statistic and a derived
threshold (k = 3.5 robust sds, taking the false-positive rate on signal-free input from 0.915 to 0.020
with no accuracy cost). Computing that statistic on the VitalDB windows and comparing its distribution
between arms is the measurement this section should have rested on. It has not been run — the equivalent
recompute is currently in flight for Sleep-EDFx only.

**The two claims this reaches.** E233's "THE PANEL HAS NO REVERSAL LEFT IN IT" depends on the anchored
measure behaving properly on these windows, and the anchored measure depends on the peak. That verdict
is not withdrawn — its own gates passed and E237 showed the estimator is monotone and accurate *where a
peak exists* — but it now carries an explicit precondition that has not been verified on this cohort.

---

## The propofol null, defended properly this time

The withdrawal above was of the ARGUMENT, not of the conclusion, and the conclusion now has evidence
that does not depend on either of the invalid legs. The test uses a property the earlier attempt
ignored: **a noise-driven peak wanders across the whole search window, a real one does not**, and the
scatter a pure-noise peak produces is measurable rather than assumable.

Running the shipped estimator on 40 synthetic "cases" of 25 signal-free 1/f windows each gives a
calibrated null for the within-case standard deviation of the peak frequency:

| | within-case sd of `alpha_peak_hz_wide` | fraction below the null's 5th percentile |
|---|---|---:|
| **pure 1/f noise (null)** | median **2.864 Hz**, IQR [2.610, 3.000] | — |
| propofol arm (n = 113) | median **1.603 Hz**, IQR [1.264, 2.052] | **0.832** |
| sevoflurane arm (n = 87) | median 1.888 Hz, IQR [1.477, 2.378] | 0.724 |

**83.2 % of propofol cases have peak scatter below the 5th percentile of what this estimator produces
from pure noise.** So propofol windows carry real peaks, and E233's propofol null — peak frequency not
tracking propofol dose — is not an absent-alpha artefact. The asymmetry stands.

Two things to keep attached to that.

**A within-case sd of 1.6 Hz is still large** for something described as an individual alpha frequency.
The propofol arm is well clear of the noise null but it is not a clean measurement, and the true
prominence statistic — which E239 validated and which is being computed on VitalDB now — will say how
much of that 1.6 Hz is real variation and how much is the estimator wandering on low-prominence windows.

**Sevoflurane's HIGHER scatter is expected and is not a defect.** Its peak genuinely moves with dose, so
some of its 1.888 Hz is signal. That the arm with the real dose-driven shift shows more within-case
scatter is a small independent corroboration of E233's A1 finding, arriving from a statistic that was
not built to test it.
