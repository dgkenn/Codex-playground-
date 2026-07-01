# First flagship-adjacent real result — ward (floor) electrolyte de-implementation

The highest-scale reflexive practice: repletion of mild Mg/K derangements on the general floor. Treatment
sourced from PRESCRIPTIONS (hospital-wide), stratified WARD vs ICU via transfers at the triggering-draw time.
Full log: `scratchpad/ward_results.txt`.

## Result (WARD = headline)
| trial | stratum | n | FS (F) | flag-ITT (mortality) | implied-LATE [AR] | naive (adj) | balAge |
|---|---|---|---|---|---|---|---|
| Mg <2.0 | **WARD** | 81,793 | +0.140 (2210) | **+0.0018 (0.0010)** | +0.013 [0.00,0.02] | +0.0096 | +1.2 yr |
| Mg <2.0 | ICU | 9,106 | +0.243 (382) | +0.017 (0.009) | +0.071 [0.02,0.12] | +0.036 | +0.9 yr |
| K <3.5 | **WARD** | 30,993 | +0.353 (2631) | **+0.0052 (0.0018)** | +0.015 [0.02,0.02] | +0.0136 | +1.6 yr |
| K <3.5 | ICU | 3,830 | +0.263 (280) | +0.031 (0.012) | +0.116 [0.04,0.20] | +0.039 | +2.2 yr |

## Two genuine wins
1. **STRONG first stage on the floor** (F > 2000; FS 0.14–0.35) — vs the weak ~0.03 that made the ICU
   assay-noise LATE uninterpretable. On the floor, crossing the flag deterministically triggers a
   protocol/nurse-driven repletion order, so BOTH the flag-ITT and the LATE are estimable. This substantially
   relaxes the weak-instrument limitation for the electrolyte de-implementation question.
2. **Precise near-null flag-ITT** (Mg +0.0018, K +0.0052) with tight AR intervals; naive is larger (method
   attenuates the confounded association toward null). Consistent with reflexive mild floor repletion having
   little/no mortality benefit — the de-implementation direction, at the highest-scale target.

## The honest caveat (do NOT claim yet)
- **balAge +1.2 to +2.2 yr** exceeds the <1 yr gate → residual imbalance.
- **σ came out at 0.46 mg/dL for Mg — ~3× the ICU estimate (0.134).** Root cause: floor Mg draws are DAYS apart,
  so the "noise" the midpoint control is built on is dominated by **true biological drift, not analytic assay
  noise** → the midpoint is a poor severity control → residual confounding → the balance failure.

## The fix (concrete, next run)
Restrict the two control draws M1,M2 to a **tight inter-draw window (≤24 h)** so the midpoint reflects
near-contemporaneous true severity (σ→analytic noise), and/or use a **local multi-draw leave-one-out** severity
proxy. Add the pre-specified battery: σ-by-inter-draw-interval, density/heaping donut, bundle-balance (co-K/Phos
repletion), competing-risks (30/90-day). Expect balance to firm to <1 yr; the near-null ITT should persist if
real. Only then is the WARD electrolyte de-implementation estimate claimable.

## Status
This is the first real result on the flagship clinical target, and it is ENCOURAGING (strong floor first stage +
precise near-null ITT) but GATED (balance borderline pending the tight-window fix). The ICU strata (weaker FS,
larger ITT) replicate the confounding-vs-method contrast. The remaining lab-flag RCT benchmarks (RBC/platelet/
bicarb) still pend inputevents.
