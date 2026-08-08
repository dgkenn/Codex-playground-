# E341 — result note. **NOT INTERPRETABLE (G1).** The numbers below are UNLICENSED.

Registration: `bsde/src/bsde/experiments/e341_reducibility.py` (committed `ca7eca1`, before any statistic
in it existed). Output: `bsde/results/e341_reducibility.json`.

**Verdict as registered: NOT INTERPRETABLE — G1 failed.** Rule 31: the downstream verdict is absent, not
negative. Everything in P1, P2 and P3 is reported below because a correction that is not auditable is not
a correction, and because the successor must declare what was seen — but **none of it licenses a claim**,
in either direction, about whether E321's dissociation is reducible.

**E341 is not repaired and re-run.** The gate failed *after* the primaries printed, so I have seen the
answer, and rule 58 is explicit that revising the apparatus at that point is goalpost-moving however
defensible each individual fix is. One repair was already spent, during the smoke and before any real
statistic existed, on P3's residualisation space (recorded in the file). The successor is a new
registration.

---

## Why G1 failed

`_planted_reducible` was built as `AvgDelta + N(0, 0.30·|AvgDelta|)` per row and had to reach a measured
pooled-z correlation of ≥ 0.90 with `AvgDelta` to be a valid positive control. **It reached 0.7542.**
The negative control was fine (`_planted_free`, largest |ρ| against any measure = 0.1808).

The construction error is the one rule 77 and rule 84 exist for, and it is instructive that writing the
verification is what caught it: the noise was scaled to the **level** of `AvgDelta` and the statistic is
computed on **across-block variation** of `AvgDelta`. Those are different quantities, and 30 % of the
level turns out to be a large fraction of the across-state spread. The code that constructs a control is
not evidence that the control has the property; only the measurement is, and here the measurement said no.

**With no working positive control, a null on P1 cannot be read as "not reducible"** — a detector that
was never shown able to detect a planted reduction cannot license the absence of one (rule 40).

## Two further defects the run exposed, both of which the successor must fix

**(1) P2's instrument saturates and cannot discriminate.** The state profile is a Spearman over **8
states**, and the run returned |ρ_profile| = **1.0000** for `NmlzCmplx` vs `InsAwPLI` and for `EffDim` vs
`allEnvCorr` — perfect, at the registered 0.95 bar. It also returned −1.0000 for `NmlzCmplx` vs
`frontalAlpha`. Several unrelated measures order eight monotone-ish depth states identically, because
that is what depth-tracking measures do. A bar of 0.95 on a rank correlation over 8 points is rule 63 in
its purest form: the threshold was picked as a round number without asking what values the machinery can
reach or how often it reaches them. The successor must measure the distribution of |ρ_profile| over **all
pairs** in the inventory and either calibrate the bar against it or retire the instrument.

**(2) Criterion (c) in P3 was satisfied by absence of data, not by evidence.** The drug-state contrast
came back `n = 9`, below the 12-patient floor, so `p` was NaN and the code's `(not isfinite(p)) or
p >= 0.05` branch scored it as passing. That is the E37 failure (rule 48) in a new place: a criterion
that a missing measurement satisfies. The n fell because the repaired residualisation needs ≥ 4 states
shared between the dissociator and its competitor within each patient, which the drug blocks often do not
have. **So P3's "SURVIVES" rests on (a) and (b) only, with (c) vacuous.**

---

## The unlicensed numbers, recorded in full

18 patients with wake-sleep, REM and N3 within patient; 17 depositor measures; 15 POWER + CONNECTIVITY
competitors.

### P1 — pooled-z co-linearity (bar 0.90)

| dissociator | strongest POWER/CONNECTIVITY rival | ρ | strongest rival of any family | ρ |
|---|---|---|---|---|
| `NmlzCmplx` | `allEnvCorr` | **−0.8723** | `EffDim` (COMPLEXITY) | +0.9588 |
| `EffDim` | `allEnvCorr` | **−0.7921** | `NmlzCmplx` (COMPLEXITY) | +0.9588 |

Neither reaches 0.90. Two observations that the successor must carry, both stated as observations rather
than as findings:

- **`allEnvCorr` is the near-miss for both, and it is the measure the registration deliberately assigned
  to CONNECTIVITY "where it can hurt" (rule 47).** Amplitude-envelope correlation across channels sits at
  −0.87 with `NmlzCmplx`. Had it been assigned to POWER — arguably defensible, since it is an amplitude
  instrument — the family partition would be unchanged and so would this number. It is the single
  measure most likely to make the reducibility claim, and it is a hair under the bar.
- **The two dissociators correlate with each other at +0.9588**, above the bar that would have called
  either reducible to a rival family. On this deposit `NmlzCmplx` and `EffDim` are close to one
  instrument, and E321 should not be read as two measures independently corroborating one another
  (rule 28). This is the registration's third branch, and it is the one the unlicensed numbers point at.

### P2 — state-profile identity (bar 0.95) — **instrument saturated, see defect (1)**

`NmlzCmplx`: `InsAwPLI` −1.0000, `frontalAlpha` −1.0000, `frontwPLI` −0.8286, `AvgGamma` +0.8857.
`EffDim`: `allEnvCorr` −1.0000, `InsAwPLI` −0.9429, `frontalAlpha` −0.9429, `AvgGamma` +0.9429.

### P3 — survival of residualising on the strongest power/connectivity competitor

Both dissociators were residualised on `allEnvCorr`, within patient, in the space the primary is computed
in. G3 confirms the adjustment adjusted: residual-vs-competitor |ρ| = 0.0077 and 0.0097 against a 0.10
bar.

| dissociator | (a) wake−N3 | p | (b) REM−N3 | p | same sign | (c) drugU−N3 |
|---|---|---|---|---|---|---|
| `NmlzCmplx` | +0.3371 | 0.0018 | +0.6764 | 0.0012 | yes | n = 9, **vacuous** |
| `EffDim` | +0.5109 | 0.0028 | +0.5481 | 0.0022 | yes | n = 9, **vacuous** |

The arousal separation and the REM-toward-wake dissociation both survive removal of the strongest
competitor, at p ≤ 0.0028 on all four tests. **This is the outcome that would license E321 if the gate
had held, and it is exactly the situation rule 58 exists for**: the result I wanted is sitting under a
failed control, and the temptation to fix the control is at its maximum. It is not fixed here.

---

## What the successor is

E342 re-runs the same three questions with:

1. **A plant whose noise is scaled to the competitor's across-block variance, with the constructed
   correlation searched to clear the bar and printed before use** — the same repair E305 made to its G3
   when |r| ≈ 1/√(n−1) made its threshold unreachable.
2. **A calibrated profile instrument.** The distribution of |ρ_profile| over all 136 measure pairs in this
   inventory is measured first, and P2's bar is set from it or the instrument is retired (rule 63).
3. **An explicit `INSUFFICIENT` state for criterion (c)**, distinct from "does not exclude zero", so a
   missing measurement can never satisfy a criterion (rule 48).
4. **The declaration, in its own registration, that E341's numbers above were seen.**
