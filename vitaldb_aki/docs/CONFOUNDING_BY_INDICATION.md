# Arguing against confounding by indication (MIMIC requirement->mortality)

Confounding by indication cannot be eliminated observationally, but these tests make it an implausible sole explanation.

## 1. E-value (quantitative bias analysis)
- Severity-ADJUSTED dose-response Q4/Q1 RR 3.27: **E-value 5.99** (CI lower 5.49).
  _an unmeasured confounder would need RR>=5.5-6 with BOTH requirement and death, beyond age+Charlson+Elixhauser+#vaso, to nullify the adjusted dose-response._
- Lactate+SOFA-adjusted per-SD OR 2.53 -> approx RR 1.68, E-value 2.75.

## 2. Within-severity-stratum dose-response (condition on the indication)
Requirement->mortality age-adjusted OR per SD, WITHIN strata:
- lactate Q1: OR 1.944 (CI [1.444, 2.55], n=1161, mort 0.193).
- lactate Q2: OR 1.762 (CI [1.426, 2.231], n=993, mort 0.271).
- lactate Q3: OR 3.951 (CI [2.611, 6.32], n=1074, mort 0.277).
- lactate Q4: OR 2.499 (CI [2.084, 3.069], n=1047, mort 0.349).
- lactate Q5: OR 4.935 (CI [2.687, 8.601], n=1054, mort 0.601).
- 1_pressor: OR 1.613 (CI [1.423, 1.849], n=6758).
- 2_pressors: OR 2.225 (CI [2.019, 2.48], n=4711).
- 3plus_pressors: OR 5.846 (CI [4.536, 7.439], n=4480).

**8/8 strata have OR>1 with CI excluding 1.** dose-response persists WITHIN severity strata -> not merely sicker-got-more-drug

## 3. Homogeneous indication
- Single-pressor, lactate 2-4 (age+lactate adj): OR 1.464 (CI [1.25, 1.755], n=767).
- Sepsis only: OR 3.519 (CI [3.199, 3.861]); non-sepsis OR 3.855.

## Verdict
ARGUMENTS AGAINST CONFOUNDING-BY-INDICATION: (a) E-value ~6 (CI ~5.5) on the severity-adjusted dose-response -> an unmeasured confounder would have to be implausibly strong; (b) the requirement->mortality OR stays >1 (CI excludes 1) in 8/8 within-severity strata (lactate quintiles + #vaso) -> the dose grades mortality even after CONDITIONING on the indication; (c) it persists within a homogeneous single-pressor/lactate-2-4 band (OR 1.464) and within sepsis (OR 3.519). Confounding by indication is not eliminated (observational) but is made IMPLAUSIBLE as the sole explanation. The IV + negative-control-exposure tests (separate module) are the remaining quasi-experimental checks.

## Caveats
- Within-stratum conditioning controls MEASURED severity (lactate, #vaso, age); residual unmeasured confounding is bounded by the E-value, not removed.
- The strongest remaining checks are quasi-experimental: a negative-control EXPOSURE (propofol/sedation dose) and a prescribing-preference INSTRUMENT (separate module, needs an inputevents re-stream).
- Observational; the claim stays risk-stratification, not a treatment effect.
