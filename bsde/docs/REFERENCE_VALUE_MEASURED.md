# What the conditional reference actually buys, measured

*Written 2026-07-31 from E44, E45, E47, E48, E51, E54 and E55. Every number here was computed in this
repo; nothing is inherited. This document exists because the reference was adopted as a strategy on a
plausibility argument, and it is now possible to put a number on it.*

---

## The headline: the rationale is sound and the effect size is small

`REFERENCE_AGAINST_ALL_THREE.md` proposed a conditional reference as a lever on all three challenges. The
gain has a closed form — **r rises by 1 / sqrt(1 − R²)** — so it is measurable rather than arguable.

| context | measure | R² | gain |
|---|---|---|---|
| awake healthy adults, age + sex (E54, n = 745) | `exponent_low_robust` | 0.147 | **1.083** |
| " | `whole_head_exponent` | 0.113 | 1.062 |
| " | `exponent_low` | 0.088 | 1.047 |
| " | `lempel_ziv` | 0.056 | 1.029 |
| " | **`lrtc_alpha`** — Challenge B's own marker | **0.0003** | **1.000** |
| anaesthetised at matched BIS, age (E55, n = 240) | `spectral_edge_95` | 0.047 | 1.024 |
| " | `whole_head_exponent` | 0.045 | 1.023 |
| " | `exponent_low` | 0.004 | 1.002 |

**The best gain measured anywhere is 1.083. Challenge B's own marker gains 1.000.** For scale, E41's
Challenge B target effect is 0.286 against a minimum detectable effect of 0.272: the best available gain
moves 0.286 → 0.310, and the actual marker's moves it 0.286 → 0.286.

**No challenge's feasibility changes.** That is the finding.

---

## What is nonetheless established, and should not be thrown out with it

1. **The rationale is real (E55).** At the same BIS reading, `whole_head_exponent` (−0.228 [−0.360,
   −0.092]), `lempel_ziv` (−0.188) and `spectral_edge_95` (+0.235) all differ systematically by age in
   adults, and adjusting for anaesthetic agent, ASA, sex and BMI moves those estimates by less than 0.01.
   A fixed 40–60 band is genuinely not age-neutral. **Small R² and a real defect are compatible** — a
   systematically mis-centred target can matter clinically at an R² that buys little statistical power.
2. **The pipeline is calibrated (E47).** `alpha_peak_hz ~ age` reproduces the published adult decline,
   −0.01131 Hz/yr [−0.01898, −0.00390], replicating on two independent rigs. Whatever is built on it
   inherits that.
3. **The measure to build on is settled (E45 + E44).** `exponent_low_robust` has the highest five-year ICC
   of ten measures (0.841 [0.787, 0.882]) *and* the highest covariate R² (0.147) *and* retains 98.4 % of
   `exponent_low`'s eye-state sensitivity. It dominates on three criteria at once.
4. **`lempel_ziv` must come off the scale (E45).** ICC 0.193 caps its trait correlation at 0.44. It is an
   excellent state measure and a poor reference measure; the two roles were being conflated.

---

## The decision this forces, and the one hypothesis that could still justify the build

The HEEDB reference build is expensive: an in-signal wake detector **and** an eye-state detector (E44 puts
eye state at d_z = −1.214, first-order), a signal pass over 4,944 recordings, then freezing and hashing.
Q21 established the metadata cannot substitute — `pdr` with no sleep marker selects only 186 of 4,944
recordings — so the detectors are unavoidable.

**Against the build:** every measured gain is 2–8 %, and Challenge B's is zero.

**For the build, and it is one specific hypothesis rather than a general argument:** the deposits measured
here carry **only age and sex**. `NORMAL_REFERENCE_COVARIATES.md` §2 argues the covariates that matter most
are **medication and comorbidity** — 88.9 % of the HEEDB strict-normal cohort carries nervous-system drugs,
and no existing normative database corrects for medication at all. If those covariates explain substantially
more variance than age and sex do, the gain could be materially larger. **That is untested and it is the
only live argument for the build.**

> **RECOMMENDATION.** Do not commission the full reference build on the general argument — it has been
> measured and it is worth single-digit percent. Test the medication/comorbidity hypothesis first, which is
> far cheaper than the build: it needs a signal pass over a *subset* of HEEDB stratified on drug exposure,
> not the whole cohort, and it does not need a frozen, hashed, versioned artefact to answer. If R² on
> medication and comorbidity is comparable to age and sex, the build is not justified by the evidence
> available. If it is several times larger, it is.

**A caveat that cuts the other way and belongs in the decision.** The reference's value for Challenge A was
never about R² — it was about supplying a common absolute scale for an equivalence test. E49 closed that
route for an unrelated reason (the cross-deposit sampling floor at n ≈ 20 is comparable to the state effects
themselves), and E53 showed harmonisation cannot shrink that floor. So the Challenge A case for the
reference is neither supported nor refuted by the numbers above; it is blocked upstream on data access.
