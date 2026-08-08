# E340 — result note

Registration: `bsde/src/bsde/experiments/e340_graded_and_muscle.py` (committed `dd8ea91`, before any
statistic in it existed). Output: `bsde/results/e340_graded_and_muscle.json`.

Two independent primaries. **P1 passes and strengthens E321. P2 refuses itself on its own registered
positive control and is NOT INTERPRETABLE.**

---

## P1 — the graded ladder. PREDICTION MET.

Krause propofol arm, 15 patients with all three of `WA` (wake), `S` (sedated, responsive) and `U`
(unresponsive). Within patient, each measure is z-scored across that patient's blocks; two ordered steps
are then tested against paired sign-flip nulls (5,000 draws):

```
A = z(WA) - z(S)        the responsive step
B = z(S)  - z(U)        the unresponsive step
```

A measure is **graded** if both steps exclude zero *and carry the same sign* — i.e. it does not merely
separate the endpoints, it orders the middle.

G1 (≥ 12 patients) PASS at 15. All 17 measures, ordered by whether they are graded:

| measure | n | A (WA−S) | p | B (S−U) | p | graded |
|---|---|---|---|---|---|---|
| `NmlzCmplx` | 15 | **+0.1436** | 0.0078 | **+0.9397** | 0.0058 | **yes** |
| `EffDim` | 15 | **+0.2630** | 0.0088 | **+0.8508** | 0.0060 | **yes** |
| `frontBias` | 13 | −0.3118 | 0.0142 | −0.7309 | 0.0130 | yes |
| `frontalAlpha` | 13 | −0.2525 | 0.0162 | −0.8009 | 0.0170 | yes |
| `frontwPLI` | 15 | −0.1868 | 0.0368 | −0.8817 | 0.0394 | yes |
| `allEnvCorr` | 15 | −0.0874 | 0.0396 | −0.9866 | 0.0370 | yes |
| `AvgAlpha` | 15 | −0.2187 | 0.0088 | −0.8054 | 0.1146 | no |
| `AvgGamma` | 15 | −0.4870 | 0.0092 | **+0.2071** | 0.5764 | no (sign reverses) |
| `limbicDelta` | 15 | −0.3354 | 0.0380 | −0.6316 | 0.1146 | no |
| `AvgDelta` | 15 | −0.5242 | 0.1216 | −0.6096 | 0.2338 | no |
| `frontalDelta` | 13 | −0.1513 | 0.3354 | −0.9985 | 0.0186 | no |
| `temporalDelta` | 15 | −0.2793 | 0.1146 | +0.0739 | 1.0000 | no |
| `parietalDelta` | 12 | −0.4924 | 0.0750 | −0.1220 | 0.5480 | no |
| `allwPLI` | 15 | −0.0742 | 0.6052 | −1.0271 | 0.0074 | no |
| `longwPLI` | 15 | +0.0068 | 0.7944 | −1.1047 | 0.0094 | no |
| `backwPLI` | 15 | −0.0190 | 0.7796 | −0.9113 | 0.0068 | no |
| `InsAwPLI` | 10 | −0.1561 | 0.5076 | −0.8977 | 0.1256 | no (also below G1) |

**The registered prediction was: both complexity measures graded AND no delta measure graded. Both halves
hold** — `NmlzCmplx` and `EffDim` are graded; **0 of 5** delta measures are (`AvgDelta`, `frontalDelta`,
`temporalDelta`, `parietalDelta`, `limbicDelta`).

**`AvgGamma` — E321's post-adjustment survivor and its most muscle-exposed measure — is not graded, and
fails in the most informative way available**: it resolves the responsive step (A = −0.4870, p = 0.0092)
and then **reverses sign** on the unresponsive step (B = +0.2071, p = 0.5764). Whatever it is tracking
across `WA → S`, it stops tracking, and partly undoes, across `S → U`. E340's note in the E321 write-up
that `AvgGamma` is the weakest of the three dissociators is strengthened here: on an ordered behavioural
ladder it is not a depth measure at all.

This is the part that matters for E321. E321 established that complexity places REM with wake and drug
unresponsiveness with N3, while delta cannot tell the drug from REM. E340 adds that the same two
complexity measures also **order an intermediate behavioural state** — sedated-but-responsive sits
between wake and unresponsive, in the right order, on both steps — while the delta measures do not
resolve the responsive step at all (`AvgDelta` p = 0.1216, `frontalDelta` p = 0.3354, `allwPLI` p = 0.6052,
`longwPLI` p = 0.7944, `backwPLI` p = 0.7796). Four measures — `allwPLI`, `longwPLI`, `backwPLI`,
`frontalDelta` — fail specifically on **A**, the step between two *responsive* states, while passing
comfortably on **B**, the step across the loss of responsiveness. That is the signature of a measure that
tracks the binary and not the ladder, and it is a cleaner separation than a pass/fail count conveys.

Under `--smoke` (state labels permuted within patient) the graded set is empty, so the criterion bites.

## P2 — the between-subject muscle test. NOT INTERPRETABLE, by its own G3.

Sleep-EDFx, 113 subjects with all stages and a finite positive submental EMG amplitude in both REM and N3.
G2 (≥ 100 subjects) PASS. The test correlates, **between subjects**, each candidate's REM−N3 z-change
against the log-transformed real-EMG REM−N3 change — conditioning on nothing, which is what avoids the
collider E253 walked into (rule 13).

G3 made the EEG-derived muscle proxies the positive control: if none of them tracks real EMG at
|ρ| ≥ 0.30, the test cannot tell "not muscle" from "no sensitivity" (rule 57) and must refuse.

```
emg_index                 rho = -0.1666      lempel_ziv               rho = -0.1803
emg_beta_gamma_fraction   rho = +0.1149      spectral_entropy         rho = -0.1039
emg_kurtosis              rho = -0.0788      multiscale_entropy_slope rho = -0.0260
```

**G3 FAILS.** The best proxy reaches |ρ| = 0.1666 against a 0.30 floor. P2 is reported as NOT
INTERPRETABLE and the candidate correlations above are **not** evidence that the measures are muscle-free.

### What the G3 failure is itself evidence of, and it is worth more than the refused test

This is the third independent measurement in this project of the same thing, and they now agree from
three directions:

- **E322**: the EEG-derived muscle proxies move **opposite** to real submental EMG across REM
  (`emg_index` +1.27 against real EMG −0.33).
- **E71** (rule 57): `emg_index` correlates with the real channel at ρ = +0.20 pooled, +0.30 within
  subject — a weak proxy pressed into service as ground truth.
- **E340** here: **between subjects**, no EEG-derived proxy tracks the real channel above |ρ| = 0.17.

The family of EEG-derived "EMG index" measures that the depth-of-anaesthesia and sleep literatures use as
a muscle-contamination control is, on this deposit, not validated against actual muscle. Any experiment
that uses one as a covariate, a screen or a positive control is using an instrument whose agreement with
the thing it names has never been shown here — and it is **not** a conservative substitution, because two
of the three measurements put it in the wrong direction.

### Why this does not leave E321's muscle objection open

P2 was the wrong cohort for that objection in the first place, and the registration says so under SCOPE:
Sleep-EDFx has **no anaesthetic**, so it can only speak to the REM half. E321's discriminating power lives
in the **drug** half (P3), and E321's cohort is **intracranial** — depth and subdural electrodes, not
scalp — where submental and temporalis EMG are attenuated by the skull rather than sitting on top of it.
That is an argument, not a measurement, and it is labelled as one (rule 42). The measurement that would
settle it is a rule-60 escape check inside the Krause inventory itself, which is E341, not another scalp
cohort.
