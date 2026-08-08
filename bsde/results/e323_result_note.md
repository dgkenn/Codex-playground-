# E323 — P1 "passed" and its own smoke says the threshold is passed by chance. Not claimable.

*2026-08-07. 13 patients contribute. All numbers below are on the registered statistic.*

---

## 1. The registered pass is not informative, and G3 is what shows it

    REAL   : 5 distinct stages claimed across 12 measures, modal stage holds 0.33
    SMOKE  : 4 distinct stages claimed,                    modal stage holds 0.42
            (smoke = sleep-stage labels permuted within patient)

**The disagreement statistic barely moves when the stage labels are destroyed.** With 13 patients and
five candidate stages, nearest-stage assignment is noisy enough that modal fractions of 0.3–0.4 and four
or five distinct claims are simply what chance produces. P1's registered criterion (≥ 3 distinct stages,
modal < 0.60) is therefore **satisfied by noise**, and the verdict string "MEASURES DISAGREE" is not
licensed.

I registered G3 precisely to catch this and it caught it. The verdict is reported as printed and is
withdrawn here — the same discipline as E320, and the second time in this pivot that a statistic passed
its threshold while failing to beat its own permutation control.

## 2. What IS above chance, and it is a narrower claim

Concentration, not disagreement:

| measure | modal equivalent for propofol-unresponsive | share |
|---|---|---|
| `NmlzCmplx` | **N3** | **0.69** |
| `EffDim` | **N3** | **0.69** |
| `allEnvCorr` | N2 | 0.54 |
| `temporalDelta` | wake | 0.46 |
| `AvgDelta` | REM | 0.31 (tied three ways with wake and N2) |
| `limbicDelta` | wake | 0.31 (tied with N2) |

Against a chance share of roughly 0.3–0.4, **the two complexity measures give a concentrated answer at
0.69 and every delta measure gives a diffuse one at 0.31–0.46, several with three-way ties.** That is a
statement about which measures place a drug state *reliably* on a sleep scale, not about which stage
anaesthesia "is".

It is consistent with E321 — where complexity separated the drug from REM and delta did not — and it is
weaker than E321, because it rests on modal counts over 13 patients rather than on a paired null.

## 3. My P2 prediction was wrong in a specific way

I predicted delta would assign the drug to REM or N1. It assigns it to **wake** (`temporalDelta` 0.46,
`limbicDelta` 0.31) or spreads it. The direction of my error is worth recording: I extrapolated from
E321's z-values, where delta placed the drug near REM *relative to N3*, and did not check that REM and
wake are adjacent on a delta scale. On delta, wake and REM are both "low delta" and therefore near each
other — so "closest stage" cannot separate them. **A nearest-stage assignment is only meaningful if the
stages are well separated on that measure, and on delta two of them are not.** That is a design flaw in
the equivalent-stage idea itself, not a property of anaesthesia.

## 4. P3 could not run

Dexmedetomidine-unresponsive with sleep staging: **n = 5**, below the registered floor of 12. Reported as
NOT INTERPRETABLE, exactly as the registration said it would likely be. The depositors' published
dexmedetomidine claim is therefore neither corroborated nor challenged here.

## 5. What this run establishes about the programme, which is the useful part

Three successive designs on this deposit (E320 ratio null, E322 scalp REM contrast, E323 nearest-stage)
have each returned a statistic that either could not beat its own control or was passed by nearly every
measure. The common cause is not the analyses: **n = 13–18 patients with both sleep and anaesthesia, and
five coarse state labels, does not support a discriminating multi-measure comparison.** E321 worked
because it used a paired within-patient difference with a sign-flip null and only three states — the
most economical statistic available on this cohort — and it is the only design here that should be
quoted.

**Stop adding statistics to this deposit.** The binding constraint is the cohort.
