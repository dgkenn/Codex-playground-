# E321 — the arousal/processing dissociation, and a criterion that failed in the safe direction

*2026-08-07. 18 patients, within-patient, intracranial. All gates pass; G4's smoke returns 0 dissociating
measures under permuted states. **E321 is not blind** — E320's P1/P3 were seen first, and nothing here is
tuned to them.*

---

## 1. The dissociation is real, and the classical depth markers fail it

| measure | P1 wake−N3 | P2 REM−N3 | p | P3 drug−N3 | p | verdict |
|---|---|---|---|---|---|---|
| `NmlzCmplx` | +1.9295 | **+2.0101** | 0.0018 | **−0.2164** | 0.5436 | **DISSOCIATES** |
| `EffDim` | +1.6708 | **+1.7916** | 0.0012 | **−0.1398** | 0.5506 | **DISSOCIATES** |
| `AvgGamma` | +1.9489 | **+1.6200** | 0.0028 | **+0.2007** | 0.7794 | **DISSOCIATES** |
| `AvgDelta` | −1.9335 | −1.7720 | 0.0110 | **−1.6968** | **0.0146** | ambiguous |
| `temporalDelta` | −1.7596 | −1.9831 | 0.0138 | **−1.8355** | **0.0160** | ambiguous |
| `limbicDelta` | −1.6968 | −1.4800 | 0.0134 | **−1.3245** | **0.0146** | ambiguous |

**Complexity places REM with wake and drug-unresponsiveness with N3.** `NmlzCmplx` moves +2.01 from N3
toward wake in REM while the drug moves −0.22 — indistinguishable from N3.

**Every delta measure fails the drug check.** Delta separates REM from N3 (because REM is low-delta) *and*
separates the drug from N3 by almost exactly as much (−1.77 vs −1.70; −1.98 vs −1.84). A measure that
moves equally for a conscious state and an unconscious one is not tracking consciousness. This is the
discriminating comparison the design was built for, and it is why `AvgDelta` was excluded from the
confirmatory set before the run (rule 21).

## 2. After removing delta, one measure survives all three criteria

| measure | P2 adjusted | p | P3 adjusted | p |
|---|---|---|---|---|
| **`AvgGamma`** | **+0.7508** | 0.0132 | −1.1686 | 0.1804 |
| `NmlzCmplx` | +0.9080 | 0.0022 | **−4.0373** | **0.0182** |
| `EffDim` | +0.5274 | 0.0018 | **−2.4097** | **0.0144** |

Registered verdict: **DISSOCIATION: `AvgGamma`**.

## 3. THE CRITERION FAILED IN THE SAFE DIRECTION, AND I AM NOT RE-SCORING IT

Criterion (c) was registered as "P3 does not exclude zero" — **two-sided**. Post-adjustment `NmlzCmplx`
and `EffDim` fail it at **−4.04** and **−2.41**: the drug sits far *below* N3, not toward REM.

**The failure mode the criterion existed to catch was the drug looking conscious.** A measure that places
drug-unresponsiveness as *less* conscious than N3 is not committing that error — if anything it is the
behaviour a covert-consciousness application would want. So the two strongest REM dissociators are scored
as non-dissociators on a technicality about direction.

I am reporting the verdict as registered and flagging this rather than re-scoring, because rewriting a
criterion after seeing which measures it eliminates is indistinguishable from choosing the winner
(rules 37, 58). **The successor should register (c) one-sided** — the drug must not sit toward REM — with
that direction stated in advance and the reason given here.

## 4. Novelty, and I am not overclaiming it

REM having wake-like complexity and elevated gamma is **established** — it is why the perturbational
literature treats REM as the dissociation state. This experiment does not discover that.

**What is not standard, and is this project's contribution:** running the drug check as a *primary*
alongside the REM contrast, on the same patients and the same scale. That is what shows the classical
depth markers failing — delta separates REM from N3 as strongly as complexity does, and would look like a
consciousness measure if REM were the only contrast tested. **The drug arm is what discriminates them,
and it is available in this deposit and almost nowhere else.**

A literature check against verified MEDLINE records is owed before any external claim, and has not been
run for this specific comparison.

## 5. Scope, unchanged

Intracranial electrodes in epilepsy-surgery patients; depositor-computed features (no raw traces, so an
independent re-implementation is unavailable); sleep staged at 30 s against ~6–7 min drug blocks; **REM is
a proxy for conscious experience without a report** — dream recall was not collected here, so
"REM = conscious" is an inference from the literature, not a measurement in this cohort (rule 42). Muscle
biases *against* the result, because REM is atonic; but in intracranial recordings gamma is also the band
most exposed to residual myogenic and microsaccadic contamination, so `AvgGamma` specifically deserves
more suspicion than the complexity measures do.
