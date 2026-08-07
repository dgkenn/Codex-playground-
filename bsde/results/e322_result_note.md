# E322 — the REM half replicates on scalp, and in doing so shows the REM contrast alone is nearly uninformative

*2026-08-07. 141 subjects with all five stages, scalp, features from this project's own extractor,
real submental EMG. Smoke bites hard: 1 of 16 measures pass P1 and 0 pass P2 under permuted stages.*

---

## 1. It replicates — 13 of 16 measures, which is the problem

| measure | P1 W−N3 | P2 REM−N3 | p | note |
|---|---|---|---|---|
| `spectral_entropy` | +2.3937 | **+2.3073** | 0.0000 | dissociates |
| `lempel_ziv` | +2.6686 | **+1.8592** | 0.0000 | dissociates |
| `exponent_low` | −2.6311 | **−2.0492** | 0.0000 | dissociates |
| `relative_delta_power` | −1.7002 | **−1.7461** | 0.0000 | dissociates |
| `whole_head_exponent` | −2.8289 | **−1.5698** | 0.0000 | dissociates |
| `multiscale_entropy_slope` | −2.5186 | **−1.5550** | 0.0000 | dissociates |
| `spatial_participation_ratio` | −1.0000 | +0.1731 | 0.3360 | REM ≈ N3 |
| `uce_v1` | — | — | — | NOT INTERPRETABLE, n = 0 |

Registered verdict: **REPLICATES ON SCALP** for the complexity analogues. But **13 of 16 measures pass**,
including `relative_delta_power` at −1.7461.

**That is the finding, and it is about the design rather than about any measure.** REM is *paradoxical*
sleep — its EEG resembles wake on almost every summary anyone computes. So "does this measure separate
REM from N3?" is passed by nearly everything and discriminates almost nothing. E321's discriminating
power came **entirely from the drug arm**, where delta separated the drug from N3 as strongly as it
separated REM (−1.70 vs −1.77) while complexity did not (−0.22 vs +2.01).

This was stated in the registration before the run — "a pass does not revive delta and does not transfer
the drug result to scalp" — and the result is the sharpest possible demonstration of why. **A cohort with
REM but no anaesthetic cannot test this question.** Krause's value is precisely that it has both.

## 2. The EEG-derived muscle proxies contradict the real muscle channel

**Real submental EMG: REM − N3 = −0.3320, p = 0.0000. Atonia confirmed**, as it must be.

Yet the three EEG-derived muscle proxies place REM *above* N3: `emg_index` **+1.2702**,
`emg_kurtosis` **+1.0034**, `emg_beta_gamma_fraction` **+0.9186**, all p = 0.0000.

**They point the opposite way to the actual muscle.** These proxies are high-frequency power summaries,
and REM's cortical high-frequency activity rises while its muscle tone collapses. Catalogue rule 57
already recorded that `emg_index` fails to detect REM atonia (E69) and correlates with the real channel
at only ρ ≈ 0.20–0.30; this is that failure measured directly, with the sign, on 141 subjects.

**Consequence for E321, which had no muscle channel at all:** its `AvgGamma` result — the sole survivor of
the delta adjustment — is the one most exposed to this. A high-frequency measure rising in REM is exactly
what these proxies do for reasons unrelated to muscle *or* consciousness. `AvgGamma` should be treated as
the weakest of E321's three dissociators, not the headline.

## 3. The flagship is uncomputable again

`uce_v1` returns n = 0 here, as it did on VitalDB. Two frontal-ish derivations are not enough for it. The
project's frozen flagship candidate has still never been evaluated on a dissociation contrast.

## 4. What this means for the programme

* **The REM-versus-N3 contrast is not a discriminating test on its own.** Any future design using it must
  carry a second contrast that separates conscious from unconscious *without* the sleep-stage confound —
  which in practice means an anaesthetic arm in the same subjects.
* **E321 stands, and its scope narrows to what the drug arm licensed**: complexity places
  drug-unresponsiveness at N3 while delta places it near REM. That is the claim. "Complexity tracks REM"
  is not news and this experiment demonstrates it is not evidence either.
* **The acquisition target sharpens.** What the high-impact version needs is not more sleep data and not
  more anaesthesia data, but **both in the same subjects at scale** — which is Krause (n = 18,
  intracranial, epilepsy) and essentially nothing else public.
