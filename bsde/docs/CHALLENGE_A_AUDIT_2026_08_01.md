# Challenge A: what four experiments in one day did to the existing record

*2026-08-01, E139 through E142. Every number here is from this repository's own runs and each is named
with the experiment that produced it. Three of the four experiments returned NO VERDICT; the fourth
explains why, and it is the one that changes things.*

---

## The short version

The first attempt to compute Challenge A's acceptance condition as a single statistic failed its own
placebo. Chasing that failure produced two corrections to the existing record, in this order:

1. **Recording quality identifies the anaesthetic agent** on the Krause deposit at |AUC−0.5| = **0.2565**,
   larger than 9 of the 12 features' drug legibility (E139's failed gate).
2. **And it does not matter, because none of those legibilities were significant to begin with.** Arm is
   nested inside patient, the contrast has **15 independent units, not 115 blocks**, and against the exact
   enumerated null only **2 of 12** features are distinguishable from a between-patient nuisance. Row-level
   p-values were inflated by a mean factor of **178×** (E142).

The second finding supersedes the first: a confound in a statistic that is noise is not the thing to fix.

---

## What Challenge A asks, and what had never been computed

From the brief, verbatim: *"predicts loss and recovery across anaesthetics while **MINIMISING
drug-identification information**"*.

`CHALLENGE_DEFINITIONS_CORRECTION.md` recorded that the two halves had never been put in one expression —
E122 measured state tracking, E113/E120 measured drug identification, on different deposits in different
files. **E139** defined the missing statistic:

    state_leg(f) = |AUC(f ; awake vs unresponsive)| − 0.5     pooled over both drug arms
    drug_leg(f)  = |AUC(f ; propofol vs dexmedetomidine)| − 0.5   within the unresponsive stratum
    LAMBDA(f)    = state_leg(f) − drug_leg(f)

Both halves are direction-free legibilities in [0, 0.5], which is what makes them subtractable.

**One structural fact, established at registration and independent of everything that followed: the Krause
deposit contains no recovery.** In 0 of 27 patients does an awake block occur after the last unresponsive
block. E05 has recovery and one drug; Krause has two drugs and no recovery. **No reachable deposit has
both**, so Challenge A's "and recovery" clause is currently untestable across anaesthetics. That is the
sharpest existing argument for the Turku/Kallionpää request (within-subject LOR *and* ROR at constant
dosing) in `DATA_REQUEST_TURKU_KALLIONPAA.md`.

---

## E139 — the statistic, and the placebo that voided it

`pctGoodSamples` was carried as a fourteenth feature purely as a placebo. It failed:

| | |AUC−0.5| among unresponsive scalp blocks |
|---|---|
| **`pctGoodSamples`** | **+0.2565** (AUC 0.2435; dex median 0.9755, propofol 0.9954) |
| median of the 12 features | +0.1209 |

Verified against a Mann-Whitney written outside the project's statistics module. E139 was voided as
registered. G1 also failed (7 dexmedetomidine patients contribute both states; the bar was 8).

Two observations were recorded without verdict, and both point the same way as what came later:

* the amplitude+phase composite E36 recommended did **not** beat the best single feature (median composite
  LAMBDA +0.1760 against max single +0.2752);
* **rho(drug-free sleep transfer AUC, −drug_leg) = −0.2448**, the direction *opposite* to registration. The
  features leaking the most agent identity transferred *best* to natural sleep in the same patients. Under
  E141's quality adjustment it strengthened to **−0.5385**.

That last one is an objection to the acceptance condition itself rather than to any feature, and it needs
its own registration: *minimising drug-identification information* and *generalising beyond the drug* may
not be the same requirement, and here they anti-correlate.

---

## E140 and E141 — two attempts to remove the confound, two broken gates

**E140** adjusted three ways and all three failed GATE Q. One failure was mine rather than the method's:
residualising rank(quality) on rank(quality) is degenerate, so the gate was *inapplicable* to the rank
residual, not failed. The quintile estimator was unstable across the stratum count (0.0661, 0.0684, 0.0056,
0.0672, 0.0920 for k = 5, 8, 10, 15, 20).

**E141** replaced it with overlap weighting (Li, Morgan & Zaslavsky, JASA 2018) on the propensity of arm
given rank(quality). **Quality removal worked exactly as intended** — quality's own legibility went from
+0.2565 to **+0.0002** — and the capability probe confirmed the adjustment kept a quality-orthogonal
arm signal at ~100 % retention.

**GATE N failed anyway, and that failure is the whole story.** A probe column of pure Gaussian noise
reached drug legibility **+0.0844** against a 0.05 bar. The bar sat below the statistic's chance floor.

---

## E142 — the exact null, and the correction

Arm is **nested inside patient**: a patient is either a dexmedetomidine patient or a propofol patient,
never both. So the drug contrast has 15 independent units. All **C(15,7) = 6,435** patient labellings were
enumerated — a complete enumeration, so the p-values carry no Monte Carlo error.

*Correctness gate:* the exact p for `allEnvCorr` is **0.0031**; E139's independently-written 2,000-draw
sampler had given **0.0030**.

| feature | family | \|AUC−0.5\| | p (row-level) | **p (exact, patient-level)** |
|---|---|---|---|---|
| allEnvCorr | AMPLITUDE | 0.3532 | 0.0000 | **0.0031** |
| NmlzCmplx | AMPLITUDE | 0.3478 | 0.0000 | **0.0057** |
| EffDim | AMPLITUDE | 0.2700 | 0.0000 | 0.0618 |
| backwPLI | PHASE | 0.1931 | 0.0004 | 0.1677 |
| AvgDelta | AMPLITUDE | 0.1771 | 0.0010 | 0.2336 |
| AvgGamma | AMPLITUDE | 0.1426 | 0.0083 | 0.3207 |
| AvgAlpha | AMPLITUDE | 0.0993 | 0.0675 | 0.5203 |
| frontalAlpha | AMPLITUDE | 0.0946 | 0.1062 | 0.5441 |
| longwPLI | PHASE | 0.0917 | 0.0889 | 0.5178 |
| frontalDelta | AMPLITUDE | 0.0901 | 0.1233 | 0.6078 |
| allwPLI | PHASE | 0.0790 | 0.1481 | 0.5938 |
| frontwPLI | PHASE | 0.0584 | 0.2821 | 0.6970 |

**The mean 95th percentile of the exact null is 0.2791.** Only two features clear it. Mean ratio of exact
p to row-level p across the twelve: **178×**.

**P1 CONFIRMED** — 3 of 4 phase features have exact p > 0.20. Their low drug legibility is **absence of
power, not measured absence**.

**P2 CONFIRMED** — E36's family gap, +0.0913, has exact patient-level **p = 0.0914**.

---

## What is and is not retracted

**Not retracted: E36's 495-partition enumeration (p = 0.002).** It asked whether the phase/amplitude split
is special *among partitions, given the AUC values*, and it answered that correctly. E142 asks a different
question — whether those AUC values could arise with no drug effect at all — and the two are complementary.

**Corrected: every absolute drug-legibility claim on this deposit**, including E35's P4, E36's quoted
ranges, E139's drug half, and the entire premise of E140 and E141. They inherit a row-level null and must
be re-derived rather than carried forward (rule 2).

**And the correction lands on Challenge A specifically**, because the brief is stated in absolute terms.
*"Minimising drug-identification information"* is a question about how close to zero the leakage is, not
about which family leaks more. On this deposit that question cannot be answered below roughly 0.28, which
is above every phase feature's entire observed value.

`REFERENCE_AGAINST_ALL_THREE.md` §1 wrote the diagnosis a month early — *"failing to reject 'the agents are
distinguishable' is not evidence that they are equivalent"* — and applied it only to the design of future
work. It was never turned back on the numbers already in hand.

---

## New error-catalogue rule

> **67. When the exposure is nested inside the cluster, the effective n is the number of CLUSTERS, and a
> row-level null inflates significance by orders of magnitude — measured here at 178×.** Enumerate the
> cluster-level assignments and quote the null's 95th percentile *before* quoting any legibility. Three
> experiments were designed around a confound in a statistic that turned out to be noise, and the cost of
> the check that would have prevented it was one `math.comb`.

## What follows

1. **Registered and unrun: the sleep-transfer objection.** −0.2448 unadjusted, −0.5385 adjusted, in the
   direction opposite to registration, on a within-subject drug-free comparison. If minimising
   drug-identity information anti-correlates with generalising beyond the drug, Challenge A's acceptance
   condition is not the right condition, and that is a bigger claim than any feature ranking.
2. **The Turku request is now the blocking dependency**, not one option among several: two agents *and*
   recovery, within subject, is the only configuration that tests the brief as written.
3. **Every legibility in this repo computed on a between-subject contrast needs the cluster-level null.**
   The check is cheap and it is now rule 67.
