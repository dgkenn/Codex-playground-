# Increments are not comparable across deposits until they are divided by headroom

*2026-08-02. Prompted by E223, whose every increment was near zero and whose registration blamed "almost no
headroom" without measuring it. Measured here. All numbers recomputed by Opus.*

## The problem this fixes

Challenge C's estimand is the **out-of-fold increment over an incumbent**. That estimand can only detect
what the incumbent has not already explained, so its scale depends on the incumbent's strength in that
cohort — and the incumbent's strength varies enormously between deposits. Comparing raw increments across
deposits is therefore comparing numbers measured on different rulers, and this programme has been doing it.

**Headroom**, defined as `1 − |out-of-fold incumbent rho|`, is what an add-to-incumbent estimand can
possibly reach:

| deposit | out-of-fold incumbent rho | **headroom** |
|---|---|---|
| ds005620 | +0.2088 | **0.7912** |
| capslpdb | +0.6564 | 0.3436 |
| sleep_edfx | +0.8450 | **0.1550** |

A five-fold range. An increment of +0.05 means something quite different at each end of it.

## Every Challenge C result, renormalised

| candidate | ds005620 | capslpdb | sleep_edfx |
|---|---|---|---|
| `whole_head_exponent` | +0.2133 = **27.0 %** | −0.0094 = −2.7 % | +0.0542 = **35.0 %** |
| `multiscale_entropy_slope` | +0.2347 = **29.7 %** | not testable | +0.0280 = **18.1 %** |
| `relative_alpha_power` | +0.0978 = 12.4 % *(interval included zero)* | +0.0062 = 1.8 % | −0.0036 = −2.3 % |
| `pac_slow_alpha` | not tested | not testable | +0.0095 = 6.1 % |

## What changes when you look at it this way

**E222 is a stronger result than its raw numbers suggested, not a weaker one.** `whole_head_exponent`'s
+0.0542 on sleep_edfx looked like a tenth of its +0.2133 on ds005620. On the headroom scale it is
**35.0 % against 27.0 % — larger**. The two survivors take a consistent share of what is available on both
deposits, which is what a real effect looks like across cohorts of different difficulty and what a raw
comparison actively hides.

**E223's null is confirmed and sharpened.** Its eight unexposed features all took **under 6.5 %** of a
0.155 headroom. That is not "a small effect on a hard deposit", it is nothing, and the renormalisation
removes the excuse the raw numbers offered.

**E219's null on capslpdb survives too, and its "headroom caveat" is now quantified rather than asserted.**
capslpdb's headroom is 0.3436 — twice sleep_edfx's — so the near-zero increments there are not a ceiling
effect. The ledger row said the strong incumbent left little room; measured, it left more room than
sleep_edfx did, and the candidates still took −2.7 % and 1.8 % of it. **That makes E219's negative
stronger than it was recorded as being**, and the caveat should be read as narrowed rather than removed:
what remains true is that capslpdb's candidates are strongly associated standalone yet add nothing, which
is redundancy, not absence.

## The rule to carry forward

**Report the headroom beside every increment, and the increment as a fraction of it.** A registration whose
primary is an increment should state the incumbent's out-of-fold performance in the same table, because
without it the reader cannot tell a ceiling from a null — and neither could I, across four experiments.

**Caveat on the definition.** `1 − |rho|` treats rho = 1 as the attainable ceiling, which is optimistic:
measurement noise in the label puts the real ceiling lower, and it differs by deposit. So the percentages
above are LOWER bounds on the share of attainable signal taken. That does not affect the ordering, which is
what the comparison is for.
