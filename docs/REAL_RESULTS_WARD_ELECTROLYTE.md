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

## Update — tight-window + age-adjustment run (what actually happened)
Applied the ≤24 h inter-draw window AND an age-spline robustness adjustment. Results:
| trial | stratum | FS (F) | ITT (unadj) | ITT (age-adj) | balance | 
|---|---|---|---|---|---|
| Mg | **WARD** | +0.15 (1333) | +0.0019 | **+0.0014** | +1.3 yr |
| K | **WARD** | +0.35 (1621) | +0.0045 | **+0.0037** | +1.9 yr |
| Mg | ICU | +0.25 (327) | +0.025 | +0.023 | +0.6 yr |
| K | ICU | +0.25 (235) | +0.038 | +0.033 | +2.2 yr |

**Two honest conclusions:**
1. **The near-null is ROBUST to age adjustment** (Mg 0.0019→0.0014; K 0.0045→0.0037) — the residual age
   imbalance is NOT what produces the near-null. The de-implementation direction (mild floor repletion ≈ no
   mortality benefit) holds.
2. **The tight window did NOT fix balance** (still +1.3–1.9 yr on the ward). This is diagnostic: floor Mg/K
   varies substantially *within 24 h* → the variation is largely **real biology (renal function, diuretics), not
   analytic assay noise** → the noise-flag correlates with severity/age → imperfect exogeneity. This is an
   honest **scope limit of the assay-noise IV**: it is cleanest for precisely-measured, biologically-stable labs
   and weaker for renally-driven electrolytes on the sparse-draw floor. The method's own balance gate catches it.
   (Note ICU Mg balance is better, +0.6 yr — closer draws, monitored patients.)

## Remaining hardening to make the ward estimate fully claimable
Add a **renal-function (creatinine) control / restrict to normal-renal patients** (the driver of Mg/K
variability), report σ-by-inter-draw-interval, bundle-balance (co-K/Phos), and competing-risks (30/90-day). If
balance firms under renal control and the near-null persists, the floor electrolyte de-implementation estimate
is claimable; otherwise it is reported as "strong first stage + robust near-null, but exogeneity imperfect for
this biologically-variable analyte" — still an honest, useful result.

## Status
First real result on the flagship clinical target: **strong floor first stage + near-null ITT robust to age
adjustment** (encouraging), with an **honest exogeneity caveat** (biological Mg/K variability → residual balance
+1.3 yr, not fixed by the tight window; age-adjusted near-null is the mitigation). The lab-flag RCT benchmarks
(RBC/platelet/bicarb — precisely-measured labs where the assay-noise IV should be cleaner) still pend inputevents.
