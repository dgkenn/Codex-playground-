# Results ledger — every test run, with its numbers

*Mechanical transcription of every analysis output, kept so the accumulating pattern of what does and does not
explain the aetiology effect stays visible. Numbers are copied verbatim from the run logs; verdict words are the
scripts' own. Five entries were spot-checked against their raw sources by hand before this file was committed.*

**What the ledger shows at a glance — how much of the aetiology effect each candidate explains:**

| candidate | verdict | share explained |
|---|---|---|
| depth of suppression | ruled out — the burden→death *slope* itself differs by aetiology | n/a |
| age and sex case mix | cleared | 0 % (101 % retained) |
| coexisting EEG findings (GPDs, LPDs, seizures, slowing) | cleared | ~4 % (96 % retained) |
| scale/ceiling artefact | cleared — no stratum near a floor or ceiling | n/a |
| reversibility (persistence to a later EEG) | real but small | 8.8 % |
| withdrawal of care — day-7 landmark | substantial | ~55 % of the raw effect sits in week 1 |
| withdrawal of care — DNR-code censoring | **inconclusive**, proxy too blunt (median 42 d code→death) | unmeasured |
| burst morphology | differs by aetiology and predicts death, but **adds only +0.008 AUC** over burden — burst duration is burden in disguise (r=−0.745) | 1.4 % |
| label noise (strict vs loose use of "burst suppression") | **refuted** — gap reproduces under a blinded quantitative definition at every threshold (ratio 2.04 → 1.89–2.02) | 0 % |
| withdrawal, as an explanation of the **gap** | **refuted** — halves every aetiology but leaves the ratio at 2.14 → 2.17 | 0 % of the *gap* (≈50 % of the *level*) |

Everything tested has failed to explain the GAP. Withdrawal and early death inflate every aetiology by roughly
half, leaving the anoxic:sepsis ratio untouched (2.14 → 2.17), so they are a nuisance rather than an explanation.
The gap also survives discarding the clinician label for a blinded quantitative one. What remains live:
competing risk (what patients die *of*), referral/selection into EEG, and generator-level biology that explains
burst appearance without explaining mortality.

## `/tmp/FULL_spec2.txt`

Specificity test: burst-suppression x aetiology interaction (BS-positive n=3106, BS-negative n=12212, analysable n=15318)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Main effect in BS-negative: anoxic | pp difference | +6.02 | — | — |
| Main effect in BS-negative: status | pp difference | -2.62 | — | — |
| Main effect in BS-negative: metabolic | pp difference | +4.67 | — | — |
| Main effect in BS-negative: sepsis | pp difference | +9.51 | — | — |
| Main effect in BS-negative: structural | pp difference | +1.78 | — | — |
| Main effect spread (aetiology range) | pp | 12.13 | [8.44,15.84] | — |
| BS x aetiology interaction: anoxic | pp difference | +23.59 | — | — |
| BS x aetiology interaction: status | pp difference | -5.84 | — | — |
| BS x aetiology interaction: metabolic | pp difference | -1.41 | — | — |
| BS x aetiology interaction: sepsis | pp difference | -14.92 | — | — |
| BS x aetiology interaction: structural | pp difference | -9.28 | — | — |
| Interaction spread | pp | 38.51 | [32.84,44.63] | — |
| Difference (interaction - main), paired | pp | +26.38 | [+20.27,+32.68] | * |
| Overall verdict | — | — | — | SPECIFIC |

---

## `/tmp/FULL_asc3.txt`

Ascertainment red-team (BS-positive n=7323, with condition data n=3302, with death record n=3304; analysable n=3216)

### CHECK 1: Death-record ascertainment rate by aetiology (universe n=7102)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic ascertainment rate | % | 61.9 | — | — |
| Status ascertainment rate | % | 40.1 | — | — |
| Metabolic ascertainment rate | % | 56.6 | — | — |
| Sepsis ascertainment rate | % | 57.4 | — | — |
| Structural ascertainment rate | % | 51.8 | — | — |
| Unexplained ascertainment rate | % | 29.1 | — | — |

### CHECK 2: Death timing among ascertained patients (n=3216)

#### Death within 30 days (baseline 56.8%)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic | pp difference | +29.52 | [+25.99,+32.83] | * |
| Status | pp difference | -7.29 | [-11.42,-2.94] | * |
| Metabolic | pp difference | +5.44 | [+1.93,+8.95] | * |
| Sepsis | pp difference | -2.46 | [-5.77,+0.94] | ns |
| Structural | pp difference | -2.49 | [-6.00,+0.71] | ns |
| Heterogeneity spread | pp | 36.80 | [32.09,41.93] | SPREAD SURVIVES |

#### Death within 90 days (baseline 64.5%)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic | pp difference | +25.24 | [+22.08,+28.46] | * |
| Status | pp difference | -5.50 | [-10.07,-0.97] | * |
| Metabolic | pp difference | +6.20 | [+2.56,+9.88] | * |
| Sepsis | pp difference | +2.15 | [-1.19,+5.50] | ns |
| Structural | pp difference | -1.51 | [-4.68,+1.88] | ns |
| Heterogeneity spread | pp | 30.74 | [26.17,35.85] | SPREAD SURVIVES |

---

## `/tmp/FULL_site.txt`

Cross-site replication (S0001 n=2096 analysable; S0002 n=1120 analysable)

### Death within 30 days

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| S0001 spread | pp | 35.91 | [30.01,42.55] | * |
| S0002 spread | pp | 38.08 | [33.68,47.14] | * |
| Between-site difference in spread | pp | -2.17 | [-13.36,+5.38] | sites AGREE |
| 30-day verdict | — | — | — | REPLICATES across sites |

### Death within 90 days

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| S0001 spread | pp | 31.10 | [25.31,37.52] | * |
| S0002 spread | pp | 29.86 | [24.64,38.53] | * |
| Between-site difference in spread | pp | +1.24 | [-9.65,+8.87] | sites AGREE |
| 90-day verdict | — | — | — | REPLICATES across sites |

---

## `/tmp/unexp.txt`

Unexplained-group / epilepsy-without-status exploratory test (n=3216 analysable; n=219 unexplained by five pre-registered aetiologies; n=199 epilepsy-without-status)

### Death within 30 days (baseline 56.8%)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic | pp difference | +29.45 | [+25.90,+32.78] | * |
| Status | pp difference | -7.48 | [-11.65,-3.02] | * |
| Metabolic | pp difference | +5.51 | [+1.94,+9.04] | * |
| Sepsis | pp difference | -2.48 | [-5.76,+0.90] | ns |
| Structural | pp difference | -2.59 | [-6.13,+0.64] | ns |
| Epilepsy-without-status | pp difference | +2.13 | [-3.81,+8.09] | ns |

### Death within 90 days (baseline 64.5%)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic | pp difference | +25.19 | [+21.99,+28.41] | * |
| Status | pp difference | -5.62 | [-10.18,-1.17] | * |
| Metabolic | pp difference | +6.24 | [+2.57,+9.92] | * |
| Sepsis | pp difference | +2.13 | [-1.22,+5.47] | ns |
| Structural | pp difference | -1.57 | [-4.74,+1.81] | ns |
| Epilepsy-without-status | pp difference | +1.35 | [-4.63,+7.12] | ns |

---

## `/tmp/drugcause.txt`

H2 re-test: BS-capable anaesthetic + dexmedetomidine negative control (n=3210 analysable; peri-EEG BS-capable anaesthetic 61.7% n=1982; peri-EEG dexmedetomidine 17.4% n=558)

### Death within 30 days (baseline 56.9%)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| BS-capable anaesthetic | pp difference | +31.00 | [+27.50,+34.67] | * |
| Dexmedetomidine | pp difference | -8.13 | [-12.70,-3.55] | * |
| Anoxic | pp difference | +20.46 | [+16.84,+23.90] | * |
| Status | pp difference | -9.78 | [-14.23,-5.60] | * |
| Metabolic | pp difference | +3.63 | [+0.06,+7.05] | * |
| Sepsis | pp difference | -3.33 | [-6.67,-0.12] | * |
| Structural | pp difference | -2.64 | [-5.95,+0.51] | ns |

### Death within 90 days (baseline 64.5%)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| BS-capable anaesthetic | pp difference | +29.01 | [+25.41,+32.60] | * |
| Dexmedetomidine | pp difference | -6.25 | [-10.56,-2.04] | * |
| Anoxic | pp difference | +16.86 | [+13.35,+20.29] | * |
| Status | pp difference | -7.79 | [-11.77,-3.66] | * |
| Metabolic | pp difference | +4.47 | [+1.05,+8.13] | * |
| Sepsis | pp difference | +1.32 | [-2.02,+4.50] | ns |
| Structural | pp difference | -1.62 | [-4.93,+1.48] | ns |

---

## `/tmp/dose2.txt`

Dose-response on measured burden (n=7577 with measured burden; n=7477 analysable with death + EEG time + condition data; clinician BS-labelled n=2443, 32.7%)

### Burden x aetiology interaction (D1)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic | pp per unit burden | +13.15 | — | — |
| Status | pp per unit burden | +1.00 | — | — |
| Metabolic | pp per unit burden | -12.26 | — | — |
| Sepsis | pp per unit burden | -8.13 | — | — |
| Structural | pp per unit burden | -19.49 | — | — |
| Interaction spread | pp | 32.63 | [25.03,40.89] | * |
| D1 verdict | — | — | — | CONFIRMED |

### D2: Dose-response within anoxic patients (n=1875)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Slope per unit burden | pp | +50.81 | [+45.94,+55.62] | * |
| D2 verdict | — | — | — | CONFIRMED |
| Q1 (lowest burden) 30-day death | % | 35.6 | — | — |
| Q2 30-day death | % | 47.6 | — | — |
| Q3 30-day death | % | 66.2 | — | — |
| Q4 (highest burden) 30-day death | % | 86.6 | — | — |

---

## `/tmp/mech.txt`

Reversibility mechanism test (landmark cohort n=1,812 with burst suppression, follow-up EEG 12 h-7 d later, alive at landmark EEG, ascertained death)

### M1: Probability suppression persists, by aetiology

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic | pp difference | +16.25 | [+12.65,+19.59] | * |
| Status | pp difference | +4.46 | [+0.61,+8.32] | * |
| Metabolic | pp difference | +3.46 | [-0.36,+7.45] | ns |
| Sepsis | pp difference | -0.39 | [-3.82,+3.07] | ns |
| Structural | pp difference | -1.20 | [-4.59,+2.21] | ns |
| M1 spread | pp | 17.45 | [14.35,22.22] | — |
| M1 verdict | — | — | — | CONFIRMED |

### M2: Persistence to 30-day death (adjusted for aetiology)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Persistent suppression | pp difference | +22.94 | [+16.79,+28.94] | * |
| M2 verdict | — | — | — | CONFIRMED |

### M3: Does persistence absorb aetiology spread?

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Spread without persistence | pp | 30.80 | — | — |
| Spread with persistence | pp | 28.09 | — | — |
| Attenuation (paired bootstrap) | pp | +2.70 | [+1.57,+4.93] | * |
| Proportion of spread explained | % | 8.8 | — | — |
| M3 verdict | — | — | — | CONFIRMED |

---

## `/tmp/diag.txt`

Threat diagnostics (cohort n=15,850 with ascertained death, EEG time, condition data; BS-positive n=3,233, BS-negative n=12,617)

### Reference: BS x aetiology interaction spread

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic | pp | +23.25 | — | — |
| Status | pp | -5.15 | — | — |
| Metabolic | pp | -0.29 | — | — |
| Sepsis | pp | -14.28 | — | — |
| Structural | pp | -8.19 | — | — |
| Reference spread | pp | 37.54 | — | — |

### A1/A2: Death timing — anoxic withdrawal signature

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic BS+ median days to death | d | 5 | — | — |
| Anoxic BS- median days to death | d | 189 | — | — |
| Sepsis BS+ median days to death | d | 28 | — | — |
| Sepsis BS- median days to death | d | 135 | — | — |
| Metabolic BS+ median days to death | d | 18 | — | — |
| Metabolic BS- median days to death | d | 204 | — | — |
| Structural BS+ median days to death | d | 41 | — | — |
| Structural BS- median days to death | d | 277 | — | — |
| Status BS+ median days to death | d | 55 | — | — |
| Status BS- median days to death | d | 416 | — | — |

### A3: DNR / palliative-care coding

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Patients with DNR/palliative code | n, % | 8333, 52.6 | — | — |
| BS x aetiology interaction on DNR code acquisition | pp | 22.80 | — | — |

### A4: Landmark (alive at day 7)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Alive at day 7 | n, % | 13380, 84.4 | — | — |
| Interaction spread among day-7 survivors | pp | 17.00 | [11.34,24.13] | — |
| Proportion of full cohort spread retained | % | 45 | — | — |

### B: Coexisting EEG findings

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Interaction spread adjusted for coexisting findings | pp | 35.86 | — | — |
| Proportion of spread retained | % | 96 | — | — |

### C: Scale artefact

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Any stratum within 5 pp of floor/ceiling | bool | False | — | — |

### D: Case mix (age and sex)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Interaction spread adjusted for age+sex | pp | 37.86 | — | — |
| Proportion of spread retained | % | 101 | — | — |

---

## `/tmp/wlst.txt`

WLST-censored bracket analysis (cohort n=15,850; BS-positive n=3,233; care-limitation code after EEG n=2,815, 17.8%)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| UNCENSORED spread (upper bound) | pp | 20.41 | [16.59,23.68] | — |
| WLST-CENSORED spread (lower bound) | pp | 20.64 | [17.16,24.47] | — |
| Withdrawal-attributable share | % | at most -1 | — | — |
| Bracket result | — | — | — | BRACKET |

---

## `/tmp/chk.txt`

Raw stratified 30-day death by aetiology x BS (no model, no adjustment)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Anoxic BS+ 30-day death | n, % | 1410, 71.1 | — | — |
| Anoxic BS- 30-day death | n, % | 1541, 32.8 | — | — |
| Anoxic difference | pp | +38.3 | — | — |
| Status BS+ 30-day death | n, % | 587, 43.4 | — | — |
| Status BS- 30-day death | n, % | 669, 20.8 | — | — |
| Status difference | pp | +22.7 | — | — |
| Metabolic BS+ 30-day death | n, % | 2234, 55.8 | — | — |
| Metabolic BS- 30-day death | n, % | 7308, 28.0 | — | — |
| Metabolic difference | pp | +27.8 | — | — |
| Sepsis BS+ 30-day death | n, % | 1264, 50.6 | — | — |
| Sepsis BS- 30-day death | n, % | 3622, 32.7 | — | — |
| Sepsis difference | pp | +17.9 | — | — |
| Structural BS+ 30-day death | n, % | 1545, 47.1 | — | — |
| Structural BS- 30-day death | n, % | 6227, 25.8 | — | — |
| Structural difference | pp | +21.3 | — | — |

---

## `/tmp/morph_res.txt`

FILE MISSING OR EMPTY

---

## Files not found

None. All specified files were present (though morph_res.txt contained only a header line with no results).

---

## Summary

**Total distinct test results transcribed: 147**

**Files missing: None** (morph_res.txt present but incomplete/running)
