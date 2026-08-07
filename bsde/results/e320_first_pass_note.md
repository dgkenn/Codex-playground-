# E320 — registered verdict NO DISSOCIATION, and it is a MACHINERY failure, not evidence

*2026-08-07. The verdict string is correct as registered and is a bad description of what happened, which
is exactly the defect catalogue rule 97 was written about. This note is the correction.*

## What failed, and both are arithmetic

**1. The permutation null is ill-posed for a ratio statistic.** `D = (REM − N3)/(wake − N3)` is a ratio of
differences among three numbers. Permuting the three state labels within patient reassigns those same
three numbers, so the null distribution consists of *rearrangements of the observed quantities* and its
95th percentile lands at **+0.9856 / +0.9953 / +1.0396** — at or above the observed D of +0.9693 / +0.9504.
The test cannot reject, for any data, whenever the three states are ordered at all. It is rule 40's
unfailable gate wearing a null's clothing.

**2. P2 could not run.** After residualising on `AvgDelta` within patient, n = 2–6 patients survived the
denominator guard against a registered floor of 12. One repair was applied (computing the guard's IQR on
the adjusted scale rather than the raw one, since the first draft compared an adjusted denominator against
an unadjusted bar) and it was not enough. Rule 58 stops the tuning there.

So `SURVIVORS: NONE` records that **P2 produced no numbers**, not that D collapsed — and the verdict
string "every measure places REM by its arousal/delta content" asserts something the run never tested.

## What the run does show, from the part that needs no ratio null

P3 compares REM and drug-unresponsiveness on the same per-patient scale:

| measure | D (REM) | D_U (drug-unresponsive) |
|---|---|---|
| `NmlzCmplx` | **+0.9693** | **−0.0426** |
| `EffDim` | **+0.9504** | **−0.0616** |
| `temporalDelta` | +0.9690 | +0.9549 |
| `limbicDelta` | +0.9003 | +0.7698 |

**The complexity measures place REM at wake and drug-unresponsiveness at N3** — the pattern a
cognitive-processing measure must produce. **The delta measures place both near wake**, which is the
signature of tracking sleep-stage physiology rather than consciousness, and is why `AvgDelta` was excluded
from the confirmatory set before the run (REM is famously low-delta; rule 21).

This is suggestive and it is **not licensed by E320**, whose primary could not be tested.

## A rule-26 defect in this file, recorded rather than glossed

`--smoke` in E320 suppresses the JSON write and **permutes nothing**. The smoke run was therefore not
blind, and P1/P3 were seen while P2's guard was still being repaired. The predictions were committed
before any of it, so nothing could be tuned to the numbers — but the smoke did not do its job, and this
is the third distinct smoke defect this session (global-label-only in E250-E259; disk-loaded statistics in
E261/E266; no permutation at all here). **A smoke flag must permute every label the primaries depend on,
and the file should assert that at least one primary changes under it.**

## Successor

E321 changes the INSTRUMENT and nothing else (rule 58): a within-patient standardised difference in place
of a ratio, so there is no denominator to blow up and the null is a sign-flip over patients rather than a
rearrangement of the estimand's own terms. Cohort, states, guard concept, families and the delta-adjustment
requirement are unchanged. **E321 is not blind** — P1 and P3 above were seen first, and that is stated in
its registration.
