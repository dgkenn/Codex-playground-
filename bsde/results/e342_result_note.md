# E342 — result note. **REDUCIBLE. My prediction was wrong and E321's headline must be rewritten.**

Registration: `bsde/src/bsde/experiments/e342_reducibility2.py`, committed before any statistic in it
existed, declaring E341's unlicensed numbers as seen. Output: `bsde/results/e342_reducibility2.json`.

**All four gates PASS. The registered verdict is REDUCIBLE, and it fired against the registered
prediction.** The registration named this outcome first because it costs the most, and it is the one that
happened.

---

## The correction, in one paragraph

E321 is quoted in `CLAUDE.md` as "the one result to quote": complexity places REM with wake and drug
unresponsiveness with N3, while delta cannot tell the drug from N3. **The behaviour is real and survives
every check E342 threw at it. What is wrong is the attribution to complexity.** Running E321's own three
criteria across all 17 measures in the same inventory, **four power and connectivity measures dissociate
exactly as the complexity measures do** — `allEnvCorr`, `AvgGamma`, `parietalDelta` and `frontwPLI`. A
property shared by an amplitude-envelope correlation, a gamma band power, a parietal delta power and a
frontal phase-lag index is not a property of complexity. **"Complexity dissociates arousal from cognitive
processing" cannot be claimed. "Several measures in this inventory dissociate, and most do not" can.**

## What each primary returned

**G1 PASS.** The plant search stepped the noise multiplier from 1.20 down to 0.35, where the measured
pooled-z correlation with `AvgDelta` landed at **+0.9387**, inside the registered [0.90, 0.98] window
(E341's guessed constant had reached only 0.7542). `_planted_free` topped out at −0.2438. The detector
flagged the reducible plant and not the free one. **This is the control E341 lacked, and it is what makes
the reducibility finding readable rather than a null of unknown power.**

**P1 — co-linearity — DID NOT FIRE.** Neither dissociator reaches the 0.90 bar against a power or
connectivity measure:

| dissociator | strongest POWER/CONNECTIVITY rival | ρ | strongest rival of any family | ρ |
|---|---|---|---|---|
| `NmlzCmplx` | `allEnvCorr` | −0.8755 | `EffDim` (COMPLEXITY) | **+0.9613** |
| `EffDim` | `allEnvCorr` | −0.7926 | `NmlzCmplx` (COMPLEXITY) | **+0.9613** |

**P2 — behavioural substitution — FIRED.** E321's (a)(b)(c) on all 17 measures, 5,000-draw paired
sign-flip nulls, with criterion (c)'s new explicit INSUFFICIENT state:

| measure | family | (a) wake−N3 | (b) REM−N3 | (c) drugU−N3 | status | graded (E340) |
|---|---|---|---|---|---|---|
| `NmlzCmplx` | COMPLEXITY | +1.930 / 0.002 | +2.010 / 0.002 | −0.216 / 0.544 | **DISSOCIATES** | yes |
| `EffDim` | COMPLEXITY | +1.671 / 0.002 | +1.792 / 0.002 | −0.140 / 0.550 | **DISSOCIATES** | yes |
| `AvgGamma` | POWER | +1.949 / 0.001 | +1.620 / 0.002 | +0.201 / 0.769 | **DISSOCIATES** | no |
| `allEnvCorr` | CONNECTIVITY | −1.192 / 0.010 | −1.233 / 0.012 | −0.427 / 1.000 | **DISSOCIATES** | yes |
| `frontwPLI` | CONNECTIVITY | −0.937 / 0.033 | −1.009 / 0.011 | −0.122 / 1.000 | **DISSOCIATES** | yes |
| `parietalDelta` | POWER | −1.945 / 0.019 | −1.437 / 0.022 | −0.999 / **0.069** | **DISSOCIATES** | no |
| `AvgDelta` | POWER | −1.934 / 0.012 | −1.772 / 0.013 | −1.697 / 0.014 | ambiguous | no |
| `temporalDelta` | POWER | −1.760 / 0.010 | −1.983 / 0.012 | −1.836 / 0.016 | ambiguous | no |
| `limbicDelta` | POWER | −1.697 / 0.009 | −1.480 / 0.012 | −1.325 / 0.015 | ambiguous | no |
| `frontalDelta` | POWER | −1.574 / 0.020 | −1.525 / 0.022 | INSUFFICIENT (n = 11) | arousal+REM only | no |
| `AvgAlpha` | POWER | +0.591 / 0.296 | −0.393 / 0.174 | +0.195 / 0.543 | — | no |
| `frontalAlpha` | POWER | −0.781 / 0.272 | −0.951 / 0.065 | INSUFFICIENT (n = 11) | — | yes |
| `frontBias` | POWER | −0.841 / 0.151 | −0.776 / 0.066 | INSUFFICIENT (n = 11) | — | yes |
| `allwPLI` | CONNECTIVITY | −0.314 / 0.621 | −0.927 / 0.013 | +0.997 / 0.069 | — | no |
| `longwPLI` | CONNECTIVITY | −0.489 / 0.461 | −1.033 / 0.012 | +0.520 / 0.354 | — | no |
| `backwPLI` | CONNECTIVITY | +0.424 / 0.639 | −0.854 / 0.040 | +0.454 / 0.562 | — | no |
| `InsAwPLI` | CONNECTIVITY | −0.616 / 0.188 | −0.930 / 0.016 | INSUFFICIENT (n = 9) | — | no |

n = 18 / 18 / 13 for most measures; 16 / 16 / 12 for `parietalDelta`, 16 / 16 / 11 for the frontal
measures, 13 / 13 / 9 for `InsAwPLI`.

**P3 — residual dissociation — SURVIVES for both**, after residualising on `allEnvCorr` in the z space
over the sleep states (G3 confirms orthogonality at exactly 0.0000; over all states, where the drug blocks
are an extrapolation of the removal, it is 0.7093 and 0.7732 and is descriptive only):

| dissociator | (a) | p | (b) | p | (c) | p | n |
|---|---|---|---|---|---|---|---|
| `NmlzCmplx` | +0.1246 | 0.0384 | +0.2121 | 0.0022 | +0.0736 | 1.0000 | 18/18/13 |
| `EffDim` | +0.1001 | 0.0406 | +0.1426 | 0.0022 | +0.5102 | 0.7792 | 18/18/13 |

So the dissociation is **not** a re-description of `allEnvCorr` — removing it entirely leaves the effect
intact. That matters for what the correction is and is not: the complexity measures are not the envelope
correlation wearing a different name. They are simply not *special*, because five other measures do the
same job.

---

## What survives from E321 and E340, precisely

**Survives.**
- The dissociation itself, at p = 0.002 on both steps for both complexity measures, and surviving removal
  of its strongest correlated rival.
- **The delta result, but narrowed.** Three delta measures (`AvgDelta`, `temporalDelta`, `limbicDelta`)
  are ambiguous — they separate REM from N3 *and* the drug from N3 by almost the same amount, which is
  E321's actual contribution and the sentence worth keeping: delta would pass as a consciousness measure
  if the drug arm were absent.
- E340's graded ladder for `NmlzCmplx` and `EffDim`, and the fact that no delta measure is graded.

**Does not survive.**
- **"Complexity" as the operative category.** Four non-complexity measures dissociate.
- **"Every delta measure fails the drug check."** `parietalDelta` dissociates. Its (c) passes at
  **p = 0.069**, which is marginal, and criterion (c) is equivalence-shaped tested by an NHST — it rewards
  low power, and `parietalDelta` has the second-smallest support in the panel (16/16/12). That is an
  argument for treating its pass as weak, **not** for excluding it: excluding a measure because its pass
  is inconvenient, after seeing that it passed, is exactly the move rule 58 forbids. The honest statement
  is "4 of 5 delta measures fail the drug check; the fifth passes marginally on the smallest support".
- **`NmlzCmplx` and `EffDim` as two corroborating measures.** They correlate at **+0.9613**, above the
  0.90 bar that would have called either reducible to a rival family. On this deposit they are one
  instrument (rule 28), and E321 must not be read as two measures agreeing.

## The post-hoc conjunction, labelled as post-hoc

Crossing E342's dissociation criterion with E340's graded criterion — **a conjunction of two experiments'
registered criteria, formed after seeing both, and therefore not a registered result** — leaves four
measures that both dissociate and order the intermediate behavioural state: `NmlzCmplx`, `EffDim`,
`allEnvCorr`, `frontwPLI`. `AvgGamma` and `parietalDelta` drop out. This is a hypothesis for a successor
to register, not a finding, and its most interesting property is that it removes the two measures with the
weakest claim on the biology — the muscle-exposed gamma power and the marginal `parietalDelta`.

## Operational defect, recorded

The registered JSON was **clobbered** by a `--reps 20` diagnostic invocation run to inspect G1's search
trace: only `--smoke` suppressed the write, and a reduced replicate count is just as much "not the
registered run" as a permuted one. It was regenerated by re-executing the identical file at the registered
seed and 5,000 replicates, reproducing every number in this note exactly. The file now refuses to write
its artifact whenever `--reps` differs from the registered value. Same family as rule 56: the invocation
that looks harmless is writing to the artifact you rely on.
