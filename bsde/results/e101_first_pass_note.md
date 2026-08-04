# E101, first pass: what was seen, and why its verdict was withdrawn before it was logged

**This file exists so the correction is auditable.** The numbers below were seen before the flaw was
found. Rule 30: pre-registration stops the bar moving afterwards; it does not stop it being set wrong, and
that failure is harder to notice because the paperwork looks correct.

## What ran, and what it printed

```
62 subjects joined to an accuracy; 61 with exactly 3 sessions
G1 coverage  PASS  (61 >= 30)

feature            ICC   rho_3   gain    r(1)    r(2)    r(3)  pred_err  d_error  d_signal
ge_norm         0.4349  0.6978  1.267 +0.2428 +0.3018 +0.3236   +0.3075  +0.0161   +0.0808
alpha_prom      0.8400  0.9403  1.058 +0.0894 +0.0982 +0.1036   +0.0946  +0.0090   +0.0142
__gauss__       0.0602  0.1613  1.636 +0.1127 +0.1269 +0.1441   +0.1844  -0.0403   +0.0314
cl_norm         0.4748  0.7306  1.240 -0.0857 -0.1044 -0.1020   -0.1063  +0.0042   -0.0164
modularity      0.4699  0.7267  1.244 -0.1245 -0.1558 -0.1663   -0.1548  -0.0115   -0.0418
iaf             0.6041  0.8207  1.166 +0.2396 +0.2582 +0.2645   +0.2793  -0.0149   +0.0248

G2 ICC usable      PASS  rho_1=0.4349
G3 r(1) non-degen  PASS  |r(1)|=0.2428 >= 0.05
G4 predictions differ PASS  |+0.3075 - +0.2428| = 0.0647 >= 0.02

BOOTSTRAP (4000 subject resamples, procedure refit inside each)
  r(3)      +0.3236  [+0.0687, +0.5450]
  d_error   +0.0161  [-0.0438, +0.0652]
  d_signal  +0.0808  [+0.0041, +0.1541]

VERDICT: CONSISTENT WITH MEASUREMENT ERROR -- the predicted gain is inside the interval and the
no-gain value is not; E86 qualification 3 stays dissolved
```

## The flaw: the "no gain" hypothesis is not a null

The registered verdict rule required `d_signal = r(3) - r(1)` to exclude 0 before it would accept the
measurement-error reading. **That condition is satisfied by construction whenever `r(1)` is not zero, for
any measure whatsoever, including pure noise.**

For a feature that is nothing but independent noise in each session, let `z1, z2, z3` be the three
session columns and `c_i = cov(z_i, y)`. Then

    r(1) = (r_1 + r_2 + r_3) / 3
    r(3) = corr( (z1+z2+z3)/3 , y ) = [ (c1+c2+c3)/3 ] / (1/sqrt(3)) = sqrt(3) * r(1)

so `d_signal = (sqrt(3) - 1) * r(1) ~ 0.73 * r(1)`, non-zero for any non-zero `r(1)`. **Averaging raises
the observed correlation of ANY imperfectly reliable measure — that is what Spearman-Brown says, and a
null that denies it is a null nothing satisfies.** The `__gauss__` row is the visible evidence: a pure
Gaussian draw went `r(1) +0.1127 -> r(3) +0.1441`, a gain of 1.28, and would itself have passed the
`d_signal` limb.

This is **error-catalogue rule 33**, recurring: *write down what shape the null produces before choosing
the statistic.* It was written for a ratio of adjacent windows and it applies unchanged here.

Two further faults, both mine, both of the same family:

1. **The C- noise control was stated in the docstring as "must come back at ~0" and never wired to
   anything.** It printed `r(1) = +0.1127` and no gate looked at it. This is the E87 pattern — a gate that
   exists in prose and not in code — and it is the second time in this project.
2. **A single Gaussian realisation is not a calibration.** With n = 61 the standard error of a Spearman
   correlation is about 0.13, so `+0.1127` is an ordinary draw. One draw cannot tell you the procedure's
   false-positive rate; a few hundred can (rule 26).

## What the corrected test is, and why it is not a moved goalpost

The theory that generated the registered prediction generates a second one for free, and it was available
before the run: **if the sessions carried no stable subject signal at all (ICC = 0), the gain would be
exactly `sqrt(k)`.** So there are two *competing models*, both computable, neither of them "no change":

    H_error :  gain = sqrt( rho_3 / rho_1 )   with rho_1 measured   -> for ge_norm, 1.267
    H_noise  : gain = sqrt(k) = sqrt(3)                              -> 1.732

The corrected primary compares `r(3)` against both. The registered wrong-direction branch (averaging
HURTS) is unchanged, the equivalence/UNDETERMINED branch is unchanged, the cohort is unchanged, the
estimator is unchanged, and the gates are unchanged. **What changed is that one uninformative comparison
was replaced by an informative one derived from the same theory** — not a threshold, not a cohort, not a
horizon. Rule 34's shape: a test with no placebo is a test with no denominator, and `H_noise` is the
denominator this design was missing.

A calibration arm is also added: 200 independent Gaussian features run through the whole procedure, so
the rate at which each limb of the verdict fires on noise is measured rather than assumed.

## What was already visible in the first pass and survives the correction

Reported here because it was seen, and because it is the part that does not depend on the broken limb:
`r(3) = +0.3236` against `H_error`'s +0.3075 and `H_noise`'s `0.2428 * 1.732 = +0.4206`. The corrected
run decides whether that separation is real; this note fixes what was known beforehand so the corrected
run cannot be read as having chosen its comparison afterwards.
