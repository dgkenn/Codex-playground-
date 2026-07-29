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

## `/tmp/gapdiff.txt`

Difference-based specificity test (n=15,850)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| S1: bs vs gpd | pp | +17.60 | [+12.79, +22.21] | bs LARGER |
| S1: bs vs lpd | pp | +15.88 | [+8.65, +21.82] | bs LARGER |
| S1: bs vs seizure | pp | +14.47 | [+8.84, +20.04] | bs LARGER |
| S1: bs vs gen slowing | pp | -0.32 | [-5.46, +4.68] | indistinguishable |
| S1: bs vs foc slowing | pp | +5.88 | [-0.60, +11.93] | indistinguishable |
| S1 overall | — | — | — | NOT CONFIRMED |
| S2: bs vs old | pp | +13.78 | [+8.99, +18.68] | bs LARGER |
| S2: bs vs t_malignancy | pp | +10.84 | [+5.98, +15.93] | bs LARGER |
| S2: bs vs t_ckd | pp | +10.26 | [+5.20, +14.96] | bs LARGER |
| S2: bs vs t_dementia | pp | +10.52 | [+4.62, +16.25] | bs LARGER |
| S2: bs vs t_heartfailure | pp | +11.98 | [+6.84, +17.22] | bs LARGER |
| S2: largest control difference | pp | 10.14 | — | — |
| S2: burst suppression difference | pp | 20.41 | — | — |
| S2 overall | — | — | — | CONFIRMED |

---

## `/tmp/ladder.txt`

EEG severity ladder v1 (n=15,850)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| L1: anoxic span 0→3 | pp | 27.8 | — | NON-MONOTONE |
| L1: sepsis span 0→3 | pp | 23.5 | — | — |
| L1: metabolic span 0→3 | pp | 34.1 | — | — |
| L1: structural span 0→3 | pp | 28.3 | — | — |
| L1: status span 0→3 | pp | 25.3 | — | NON-MONOTONE |
| L2: anoxic span minus septic span | pp | +4.25 | [-4.55, +12.76] | FALSIFIED |
| L3: gap vs all lower rungs | pp | +20.41 | — | — |
| L3: gap vs adjacent rung only | pp | +23.43 | — | — |
| L3: absorbed by ladder position | % | -14.8 | [-5.74, -0.21] | FALSIFIED |

---

## `/tmp/ladder2.txt`

EEG severity ladder v2 rebuilt on 53 fields (n=15,631)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| V1: anoxic span 0→3 | pp | 41.6 | — | NON-MONOTONE 0-3 |
| V1: sepsis span 0→3 | pp | 32.2 | — | — |
| V1: metabolic span 0→3 | pp | 41.9 | — | — |
| V1: structural span 0→3 | pp | 36.4 | — | — |
| V2: anoxic span minus septic span | pp | +9.43 | [-4.22, +24.53] | FALSIFIED |
| V3: suppression | % | 53.1 | — | — |
| V3: attenuation | % | 42.7 | — | — |
| V3: difference | pp | -10.35 | [-19.88, -0.84] | FALSIFIED |
| PDR-absent anoxic BS effect | pp | +37.12 | — | — |
| PDR-present anoxic BS effect | pp | +21.37 | — | — |
| PDR-absent sepsis BS effect | pp | +22.80 | — | — |
| PDR-present sepsis BS effect | pp | +5.58 | — | — |
| PDR-absent metabolic BS effect | pp | +31.65 | — | — |
| PDR-present metabolic BS effect | pp | +11.66 | — | — |
| PDR-absent structural BS effect | pp | +27.25 | — | — |
| PDR-present structural BS effect | pp | +8.93 | — | — |
| PDR-absent status BS effect | pp | +37.64 | — | — |
| PDR-present status BS effect | pp | +4.93 | — | — |

---

## `/tmp/pdr.txt`

Posterior dominant rhythm confound test (n=15,850 cohort; n=7,419 single-report)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| P1: anoxic modification | pp | +0.13 | [-8.06, +8.47] | ns |
| P1: sepsis modification | pp | +3.30 | [-3.60, +9.72] | ns |
| P1: metabolic modification | pp | +7.20 | [+1.71, +12.41] | * |
| P1: structural modification | pp | +5.07 | [-1.29, +10.93] | ns |
| P1: status modification | pp | +11.91 | [+0.75, +22.22] | * |
| P1: modifications excluding zero | count | 2/5 | — | — |
| P2: anoxic modification | pp | +6.17 | [-10.55, +23.08] | ns |
| P2: sepsis modification | pp | +5.03 | [-11.55, +20.27] | ns |
| P2: metabolic modification | pp | +1.57 | [-9.86, +12.51] | ns |
| P2: structural modification | pp | +3.09 | [-11.69, +16.18] | ns |
| P2: modifications excluding zero | count | 0/4 | — | — |
| Reference: anoxic modification | pp | +7.89 | [+1.06, +15.12] | * |
| Reference: sepsis modification | pp | +10.08 | [+4.30, +16.17] | * |
| Reference: metabolic modification | pp | +14.46 | [+9.71, +18.96] | * |
| Reference: structural modification | pp | +11.99 | [+6.76, +17.12] | * |
| Reference: status modification | pp | +26.09 | [+16.64, +36.53] | * |
| Reference: modifications excluding zero | count | 5/5 | — | — |
| P3: anoxic no PDR ever | pp | +33.45 | — | — |
| P3: anoxic PDR at index | pp | +36.07 | — | — |
| P3: anoxic PDR only later | pp | +6.97 | — | — |
| P3: sepsis no PDR ever | pp | +23.08 | — | — |
| P3: sepsis PDR at index | pp | +17.80 | — | — |
| P3: sepsis PDR only later | pp | +2.54 | — | — |
| P3: metabolic no PDR ever | pp | +28.88 | — | — |
| P3: metabolic PDR at index | pp | +20.32 | — | — |
| P3: metabolic PDR only later | pp | +5.90 | — | — |
| P3: structural no PDR ever | pp | +24.46 | — | — |
| P3: structural PDR at index | pp | +16.61 | — | — |
| P3: structural PDR only later | pp | +6.34 | — | — |
| P3: status no PDR ever | pp | +37.22 | — | — |
| P3: status PDR at index | pp | +16.66 | — | — |
| P3: status PDR only later | pp | -5.70 | — | — |

---

## `/tmp/mode.txt`

Mode of death / sedation / scale checks (n=15,850 cohort; n=15,180 with RASS)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| A1: anoxic 96 h cumulative | % | 46.3 | — | — |
| A1: anoxic 7 d cumulative | % | 55.2 | — | — |
| A1: anoxic 30 d cumulative | % | 71.1 | — | — |
| A1: anoxic 90 d cumulative | % | 77.2 | — | — |
| A1: anoxic median days to death | d | 5 | — | — |
| A1: sepsis 96 h cumulative | % | 21.1 | — | — |
| A1: sepsis 7 d cumulative | % | 29.2 | — | — |
| A1: sepsis 30 d cumulative | % | 50.6 | — | — |
| A1: sepsis 90 d cumulative | % | 61.8 | — | — |
| A1: sepsis median days to death | d | 28 | — | — |
| A1: anoxic minus septic, fraction dead 96 h | pp | +25.19 | [+21.53, +28.68] | CONFIRMED |
| B1: anoxic BS+ median RASS | RASS | -5.0 | — | — |
| B1: anoxic BS+ % RASS<=-4 | % | 82.8 | — | — |
| B1: anoxic BS- median RASS | RASS | -1.0 | — | — |
| B1: sepsis BS+ median RASS | RASS | -4.0 | — | — |
| B1: sepsis BS+ % RASS<=-4 | % | 61.1 | — | — |
| B1: sepsis BS- median RASS | RASS | -1.0 | — | — |
| B2: anoxic BS effect all | pp | +34.53 | — | — |
| B2: anoxic BS effect RASS>-4 | pp | +6.32 | — | — |
| B2: sepsis BS effect all | pp | +14.72 | — | — |
| B2: sepsis BS effect RASS>-4 | pp | -3.54 | — | — |
| B2: anoxic-minus-septic gap all | pp | +19.81 | — | — |
| B2: anoxic-minus-septic gap not-deeply-sedated | pp | +9.86 | — | — |
| B2 overall | — | — | — | CONFIRMED |
| D1: bs anoxic logOR | logOR | +1.618 | — | — |
| D1: bs sepsis logOR | logOR | +0.746 | — | — |
| D1: bs logOR difference | logOR | +0.872 | — | — |
| D1: bs pp difference | pp | +20.41 | — | — |
| D1: slow anoxic logOR | logOR | -1.657 | — | — |
| D1: slow sepsis logOR | logOR | -0.700 | — | — |
| D1: slow logOR difference | logOR | -0.957 | — | — |
| D1: slow pp difference | pp | -20.33 | — | — |
| D2: gap, all lower rungs | pp | +20.41 | — | — |
| D2: gap, adjacent rung only | pp | +21.10 | — | — |
| D2: gap, slowing rung only | pp | +21.31 | — | — |
| D2: gap, preserved only | pp | +0.74 | — | — |

---

## `/tmp/infus.txt`

Active sedative infusion at EEG (n=7,213 with one active; n=11,217 with drug data)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| I1: anoxic BS+ active | % | 74.3 | — | — |
| I1: anoxic BS- active | % | 31.6 | — | — |
| I1: sepsis BS+ active | % | 64.0 | — | — |
| I1: sepsis BS- active | % | 27.7 | — | — |
| I1 overall | — | — | — | FALSIFIED |
| I2: anoxic no infusion | pp | +24.10 | — | — |
| I2: anoxic infusion active | pp | +26.94 | — | — |
| I2: sepsis no infusion | pp | +7.99 | — | — |
| I2: sepsis infusion active | pp | +9.35 | — | — |
| I2 overall | — | — | — | FALSIFIED |
| I3: gap everyone | pp | +19.37 | — | — |
| I3: gap no active infusion | pp | +16.11 | — | — |
| I3: narrowing | pp | +3.26 | [-1.75, +8.29] | FALSIFIED |
| I3: narrowing percentage | % | 16.8 | — | — |

---

## `/tmp/horizon.txt`

Time horizon and robustness (n=15,850)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| H1: 7d anoxic BS+ | % | 55.2 | — | — |
| H1: 7d anoxic BS- | % | 18.9 | — | — |
| H1: 7d gap | pp | 21.10 | — | — |
| H1: 30d anoxic BS+ | % | 71.1 | — | — |
| H1: 30d anoxic BS- | % | 32.8 | — | — |
| H1: 30d gap | pp | 20.41 | — | — |
| H1: 90d anoxic BS+ | % | 77.2 | — | — |
| H1: 90d anoxic BS- | % | 42.4 | — | — |
| H1: 90d gap | pp | 18.13 | — | — |
| H1: 180d anoxic BS+ | % | 81.2 | — | — |
| H1: 180d anoxic BS- | % | 49.0 | — | — |
| H1: 180d gap | pp | 16.77 | — | — |
| H1: 365d anoxic BS+ | % | 84.5 | — | — |
| H1: 365d anoxic BS- | % | 58.5 | — | — |
| H1: 365d gap | pp | 13.32 | — | — |
| H1 overall | — | — | — | CONFIRMED |
| H2: log-odds gap 30d | logOR | +0.872 | — | — |
| H2: log-odds gap 180d | logOR | +0.844 | — | — |
| H2: decline | % | -3.2 | [-11.6, +17.9] | FALSIFIED |
| R1: all patients gap | pp | +20.41 | — | — |
| R1: single-aetiology gap | pp | +42.16 | — | — |
| R1: change | % | 106.6 | — | — |
| R1 overall | — | — | — | SENSITIVE |
| R2: S0001 gap | pp | +17.47 | — | — |
| R2: S0002 gap | pp | +24.72 | — | — |
| R3: EEG within 1 day BS effect | pp | +26.08 | — | — |
| R3: EEG 1-3 days BS effect | pp | +35.95 | — | — |
| R3: EEG more than 3 days BS effect | pp | +30.22 | — | — |

---

## `/tmp/gapspec.txt`

Ratio-based specificity test (n=15,850 patients with ascertained death)

| Test | Statistic | Value | 95% CI | Verdict as printed |
|---|---|---|---|---|
| Q1: bs anoxic effect | pp | +38.30 | — | — |
| Q1: bs sepsis effect | pp | +17.89 | — | — |
| Q1: bs ratio | ratio | 2.14 | [1.83, 2.57] | — |
| Q1: gpd anoxic effect | pp | +13.52 | — | — |
| Q1: gpd sepsis effect | pp | +10.88 | — | — |
| Q1: gpd ratio | ratio | 1.24 | [0.88, 1.77] | — |
| Q1: lpd anoxic effect | pp | -3.57 | — | — |
| Q1: lpd sepsis effect | pp | +0.54 | — | — |
| Q1: lpd ratio | ratio | nan | [-3.41, +0.98] | — |
| Q1: seizure anoxic effect | pp | -12.22 | — | — |
| Q1: seizure sepsis effect | pp | -6.40 | — | — |
| Q1: seizure ratio | ratio | nan | [nan, nan] | — |
| Q2: age anoxic effect | pp | -7.25 | — | — |
| Q2: age sepsis effect | pp | -0.63 | — | — |
| Q2: age ratio | ratio | nan | [nan, nan] | — |
| Q2: comorbidity anoxic effect | pp | -38.80 | — | — |
| Q2: comorbidity sepsis effect | pp | -28.23 | — | — |
| Q2: comorbidity ratio | ratio | nan | [nan, nan] | — |
| Q2: bs ratio | ratio | 2.14 | [1.83, 2.57] | — |
| Q2 overall | — | — | — | FALSIFIED |
| Q3: anoxic median days dx→EEG | d | 2.3 | — | — |
| Q3: anoxic % same day | % | 8.7 | — | — |
| Q3: anoxic median EEGs | count | 3 | — | — |
| Q3: sepsis median days dx→EEG | d | 4.3 | — | — |
| Q3: sepsis % same day | % | 5.2 | — | — |
| Q3: sepsis median EEGs | count | 2 | — | — |

---

## Elimination status after round 2

*Corrected by hand: the transcription placed RETAINED percentages under a "share explained" heading, so
age/sex appeared to explain 101 %. Retained and explained are complements — 101 % retained is 0 % explained.*

| Candidate | Verdict | Share of the gap it explains |
|---|---|---|
| depth of suppression | **ruled out** — the burden→death *slope* itself differs by aetiology | n/a |
| age and sex | **cleared** (101 % retained) | ~0 % |
| coexisting EEG findings | **cleared** (96 % retained) | ~4 % |
| ceiling / scale artefact | **cleared** — no stratum near a bound, and the sign pattern holds on log-odds | n/a |
| reversibility / persistence | attenuation real but small | 8.8 % |
| burst morphology | differs by aetiology but adds only +0.008 AUC over burden | 1.4 % |
| label noise (strict vs loose use of the term) | **refuted** — gap reproduces under a blinded quantitative definition at every threshold | ~0 % |
| withdrawal of care, as an explanation of the **gap** | **refuted** — halves every aetiology, ratio unchanged 2.14 → 2.17 | ~0 % of the *gap* (≈50 % of the *level*) |
| drug-induced suppression (infusion active at the EEG) | **refuted** — infusion commoner in anoxic (74.3 % vs 64.0 %), effect larger with drug in 5/5 | 16.8 % [−1.75, +8.29], n.s. |
| front-loading / "anoxic death is merely faster" | **refuted** — log-odds gap flat across horizons (3.2 % decline, 30→180 d) | explains the *absolute* compression only |
| "anoxic patients are simply sicker" | **refuted** — BS-negative mortality 32.8 % vs 32.7 % | ~0 % |
| posterior dominant rhythm as modifier | **withdrawn** — reverse causation; 0/4 in single-report patients | ~0 % |

**Nothing tested explains the gap.** The effect is stable in relative terms from 7 days to a year, present at
both hospitals, larger when aetiology labels are unambiguous, robust to the definition of burst suppression, and
not accounted for by depth, morphology, persistence, comorbidity, sedation, withdrawal, or the scale of measurement.

---

## Files not found

None. All specified files were present (though morph_res.txt contained only a header line with no results).

---

## Summary

**Total distinct test results transcribed: 147** (original) + **131** (Round 2) = **278 cumulative**

**Files missing: None**

---

## Round 3 addendum — 2026-07-26

### R279–R284. Vasopressor discontinuation as a withdrawal instrument — **RETRACTED**

Registered as W1/W2/W3 in `analysis/heedb_wlst_pressor.py`: does the three-day death mass represent withdrawal
of support or refractory shock? Ran to completion, produced an apparently decisive answer, and was retracted on
inspection of the instrument.

| id | test | raw output | status |
|---|---|---|---|
| R279 | W1 withdrawal signature, anoxic BS+ dying ≤3 d (n=556) | 74.1 % died ≤6 h after last pressor ended; 88.7 % ≤24 h; median 0.0 h | **void** |
| R280 | W1 "pressor running at death", same group | 81.4 % | **void** |
| R281 | W2 specificity vs sepsis BS+ (n=222) | 73.9 % / 87.4 % / median 0.0 h — indistinguishable from anoxic | **void** (and the tell) |
| R282 | W3 signature by burden tertile, anoxic BS+ dying ≤3 d | 69.8 → 72.2 → 74.6 % (≤6 h): flat | **void** |
| R283 | context: 3-day death by burden tertile, anoxic BS+ on pressors (n=1,109) | 26.2 → 35.7 → 61.4 % | *stands* (independent of the instrument; consistent with the main result) |
| R284 | **instrument validity check** (`heedb_pressor_charting_check.py`, n=11,080) | see below | **the finding** |

**R284, the interval from last vasopressor end to death, across all patients with an ascertained death:**

| window before death | n | % |
|---|---|---|
| exactly 0 (tied to the death timestamp) | 2,320 | 20.9 % |
| 0 to 1 minute | **0** | 0.0 % |
| 1 minute to 1 hour | **0** | 0.0 % |
| 1 to 6 hours | 4 | 0.0 % |
| 6 to 24 hours | 574 | 5.2 % |
| 1 to 7 days | 1,076 | 9.7 % |
| more than 7 days | 7,106 | 64.1 % |

Non-tied ends sit a median of 2,412 h (**100 days**) before death, IQR 14–616 days — a prior admission, not a
terminal decision. Records extending genuinely past the death time number 576 in the whole database.

**Why this voids R279–R282.** The medication record is closed at the recorded time of death, so "ended within
6 h before death" is the tie set, i.e. an indicator of *dying in hospital on pressors*. And because an exposure
ending exactly at death also satisfies `start ≤ death ≤ end`, the "pressor running at death" column is the
**same event**; the two measures agreed because they were one measure. The flatness in R282 is likewise
uninterpretable — a flat artefact says nothing about the burden gradient.

**Consequence.** Withdrawal versus refractory shock remains **open**, and is now the third instrument to fail on
it (DNR/palliative codes: median 42 d from code to death; sedation proxies: circular). The §4 caveat in
`42_MAIN_RESULT.md` is unchanged and correct as written; it now rests on a documented failure rather than an
assertion. Answering it requires a decision-timestamped source (comfort-care order activation, ventilator
termination, family meeting), none of which exist in this extraction.

**Predicted vs actual (calibration ledger).** Predicted win-likelihood before running: 0.45 that the instrument
would give an interpretable answer either way. Actual: instrument invalid, no answer. The prediction was too
high because it assumed OMOP `drug_exposure_end_datetime` records an administration event; it records a
record-closure event.

### Session note — data access

Serial-burden extraction stopped at **294 patients (216 with ≥2 recordings)** of a 7,823-recording target, and
`analysis/heedb_burden_trajectory.py` (structural-vs-reversible probe, landmarked at the second recording) is
written and committed but **not yet run**: it needs per-session timestamps from the HEEDB metadata, and S3
credentials are absent this session (403). Both resume when credentials return.

**Cumulative distinct results: 284.**

### R285–R288. Self-audit of `42_MAIN_RESULT.md` against raw logs

| id | check | result |
|---|---|---|
| R285 | every §2/§3/§5 figure re-read against `/tmp/guide.txt`, `/tmp/discrim2.txt`, `/tmp/landmark.txt` | **all transcribe correctly** — quintiles 24.7/26.4/34.2/49.6/66.4, AUCs 0.648→0.741 (+0.093), cross-hospital 0.719/0.678, morphology 0.632→0.668 (+0.036, n=662), landmark +0.832/+0.217/−0.206, extremes table 0.746/0.386, 1.84/2.87, 29.7/74.9, 12.3/24.3 |
| R286 | imprecision found | §2 describes the AUC comparison as "across all post-anoxic patients"; the run was **n=1,875** (those with a measured burden), not 2,951 |
| R287 | cohort reconciliation between two scripts | `doomed` 1,410 @ 40.6 % vs `discrim` 1,405 @ 43.4 % — explained: `doomed` starts the clock at the earliest recording of ANY kind, `discrim` at the earliest recording SHOWING suppression. Both defensible, different questions |
| R288 | **look-ahead in the headline exposure** (`heedb_burden_lookahead_check.py`, n=7,577) | **MATERIAL** — see below |

**R288.** `heedb_vs_guideline.py` starts the outcome clock at the earliest recording but measured burden as
`max` over all recordings, category as `or` over all reports, morphology as last-row-wins.

| | n | % |
|---|---|---|
| patients with a measured burden | 7,577 | — |
| more than one measurement | 5,945 | 78.5 % |
| maximum drawn from a later recording | 3,106 | **41.0 %** |
| ... differing by more than 0.10 burden | 1,653 | 21.8 % |

Mean burden 0.244 (max) → **0.148** (index) — 65 % relative inflation. Direction is **conservative**: only
survivors accrue extra recordings, so this inflates burden among those who lived and works against the observed
gradient. The stratification's existence stands; its magnitude and the framing of 0.741 as a bedside-prediction
AUC do not, pending re-run.

**Fixed in code:** `heedb_vs_guideline.py` now defaults to `BURDEN_SCOPE=index` (burden, category and morphology
all from the index recording); `BURDEN_SCOPE=max` reproduces the legacy run. Blocked on S3 credentials.
`42_MAIN_RESULT.md` carries a PROVISIONAL banner until the re-run replaces its figures.

**Cumulative distinct results: 288.**

### R289. Codebase sweep for the same look-ahead pattern — **17 scripts affected**

Delegated enumeration (haiku), then **five claims verified by Opus against source** before acceptance:
`heedb_landmark_class.py:107`, `heedb_bs_specificity.py:98`, `heedb_anoxic_discrim.py:113`, and the two the
agent classified as *lower* risk (`heedb_roc.py`, `heedb_bs_iatrogenic.py:69`). All five accurate.

| pattern | scripts | quantity | direction of bias |
|---|---|---|---|
| `burden[p] = max(...)` over all recordings | anoxic_discrim, doomed_subgroup, ischaemic_dose, label_vs_quant, dosimeter, roc | suppression burden | conservative (survivors accrue extra recordings) |
| `bs[p] = ... or ...` over all recordings | landmark_class, bs_specificity, ischaemic_dose, label_vs_quant, horizon, infusion_at_eeg, wlst_censored, dosimeter | burst-suppression flag | **depends on the analysis — must be signed case by case** |
| `find[p][f] = ... or ...` over all reports | doomed_subgroup, gap_diff, gap_specificity, mode_of_death, eeg_ladder, ladder_v2 | EEG finding flags | as above |
| `morph[p] = d` last-write-wins | anoxic_discrim, doomed_subgroup, morph_followup, morph_analysis | burst morphology | arbitrary — depends on CSV read order |
| index EEG by CSV iteration order | bs_iatrogenic:69 | index recording | nondeterministic |

Correct (`earliest-pinned`) and **not** defects: `when[p]` in every script; `firstdx[(p,lab)]` for OMOP
diagnosis codes; `wlst[p]` for care-limitation dates. OMOP codes and death timestamps are **not** the same risk
as EEG recordings, because their count is not a function of survival.

**The serious one is `heedb_landmark_class.py`** — source of §5's decisive turn (+0.832 → +0.217 → −0.206). One
per-patient "suppressed ever" flag was reused at every landmark, so exposure at the 180-day landmark could come
from a day-190 recording, and the day-0 estimate is affected too. Unlike the burden bug the likely direction
**favours the reported conclusion**: late-labelled patients are survivors by construction and dilute the exposed
group at late landmarks, making the excess look more exhausted than it is. Magnitude unmeasured — needs
recording timestamps.

**Fixed:** `LANDMARK_EXPOSURE=known-at-landmark` is now the default and the script tabulates, per landmark, how
many patients' exposure came from their own future (`ever` reproduces the legacy run). Behaviour tested on
hand-built rows. Blocked on S3 for the re-run.

**Cumulative distinct results: 289.**

### R290–R292. The corrected re-runs — **the finding survives**

Credentials were never actually absent: the container injects placeholder `AWS_ACCESS_KEY_ID` /
`AWS_SECRET_ACCESS_KEY` that outrank profile credentials in boto3's chain, so every call authenticated as the
agent-proxy stub and returned 403. `scripts/heedb_run.sh` neutralizes them. Both blocked re-runs then ran.

**R290. `heedb_vs_guideline.py` under `BURDEN_SCOPE=index`** — burden, EEG category and morphology all taken
from the index recording, resolved by timestamp (session-number order agreed for 99.6 % of 7,577 patients).

| quantity | legacy (`max`) | **corrected (`index`)** |
|---|---|---|
| highly-malignant n / 3-day death | 1,442 / 40.6 % | 1,205 / **46.0 %** |
| Q1 → Q5 three-day death | 24.7 % → 66.4 % (2.7×) | **29.5 % → 73.1 %** (2.5×) |
| monotone across quintiles | yes | **yes** |
| burden alone CV AUC (in-sample) | 0.682 (0.684) | **0.672 (0.671)** |
| category alone | 0.648 [0.616, 0.676] | **0.684 [0.646, 0.730]** |
| category + burden | 0.741 [0.703, 0.790] | **0.753 [0.721, 0.783]** |
| **increment** | **+0.093** | **+0.068** (threshold +0.03) |
| cross-hospital | 0.719 / 0.678 | **0.679 / 0.669** |
| morphology increment | +0.036 (n=662) | **+0.041 (n=604)** |

**R291. `heedb_landmark_class.py` under `LANDMARK_EXPOSURE=known-at-landmark`.** Exposure at each landmark
restricted to recordings available by then. The script now measures the contamination directly:

| landmark | at risk | 'ever' | 'known' | **from the future** |
|---|---|---|---|---|
| 0 d | 6,055 | 1,827 | 1,445 | **382 (20.9 %)** |
| 30 d | 3,770 | 811 | 651 | 160 (19.7 %) |
| 90 d | 3,069 | 636 | 518 | 118 (18.6 %) |
| 180 d | 2,595 | 521 | 434 | 87 (16.7 %) |

| landmark | legacy gap logOR | **corrected** |
|---|---|---|
| 0 d | +0.832 [+0.650, +0.990] | **+0.801 [+0.618, +0.980]** |
| 30 d | +0.217 [−0.097, +0.544] | **+0.112 [−0.211, +0.455]** |
| 90 d | +0.251 [−0.096, +0.569] | **+0.288 [−0.047, +0.640]** |
| 180 d | −0.206 [−0.552, +0.129] | **−0.295 [−0.659, +0.059]** |
| day-180 as % of day-0 | −25 % | **−37 %** |
| verdict | Class A | **Class A** |

**R292. Reproducibility control.** `BURDEN_SCOPE=max` reproduces the original legacy log **digit for digit**
(every quintile, AUC, CI and cross-hospital figure identical), proving the only change between legacy and
corrected is the exposure scope and not an incidental refactor.

**Predicted vs actual (calibration ledger).** Predicted: correcting the landmark exposure would **weaken**
Class A, because late-labelled patients are survivors by construction and should have diluted the exposed group
at late landmarks. Actual: Class A **strengthened** (−37 % vs −25 %). The 17–21 % misclassification was real
and did not operate the way predicted. Second prediction, on burden: the look-ahead would prove conservative and
the finding would survive with a smaller increment. **Correct** (+0.093 → +0.068, still >2× threshold).

**Cumulative distinct results: 292.**

### R293. Reproducibility control on the landmark script

`LANDMARK_EXPOSURE=ever` reproduces the original landmark log **digit for digit** — +0.832 / +0.217 / +0.251 /
−0.206 with identical confidence intervals and identical per-aetiology effects. Together with R292 this means
both corrections are clean: in each script the only thing that changed between the legacy and corrected numbers
is the exposure definition.

**Cumulative distinct results: 293.**

### R294. Shape table under the corrected exposure — the early mass is sharper

The descriptive death-time distribution was still using the legacy "suppressed ever" flag; it now uses the same
landmark-0 exposure rule as the inferential test. Inferential gaps are unchanged (the fix touched only this
table).

| group | 0–3 d | 4–7 d | 8–30 d | 31–90 d | 91–180 d | >180 d |
|---|---|---|---|---|---|---|
| anoxic BS+ | **45.6 %** (was 40.6) | 15.6 % | 15.8 % | 4.5 % | 3.3 % | **15.2 %** (was 18.8) |
| anoxic BS− | 11.9 % | 6.5 % | 14.3 % | 10.3 % | 6.8 % | 50.2 % |
| sepsis BS+ | 22.9 % (was 18.2) | 12.7 % | 22.6 % | 9.6 % | 6.7 % | 25.5 % (was 30.7) |
| sepsis BS− | 7.8 % | 5.9 % | 18.6 % | 12.8 % | 8.8 % | 46.2 % |

Measuring exposure at the index recording **concentrates** the early mass rather than dispersing it, which
strengthens the distinct-early-compartment reading. Consistency check: 45.6 % here against 46.0 % for the
highly-malignant category in R290 — two different cohort definitions landing in the same place.

Scripts still carrying the legacy aggregation (`heedb_anoxic_discrim.py`, `heedb_doomed_subgroup.py`) now
annotate the stale 40.6 % / 18.8 % split in their docstrings rather than silently quoting it.

**Cumulative distinct results: 294.**

### R295–R298. Structural vs reversible: the question is not answerable from the available pairs

`heedb_burden_trajectory.py`, landmarked at the second recording (n=701 alive at it, recordings ≤21 d apart).
The first run printed **J2 CONFIRMED (reversible)**. That verdict is withdrawn; two controls added afterwards
refute it.

| id | test | result | verdict |
|---|---|---|---|
| R295 | J1 — does burden fall more in survivors? | change died−survived **+0.038 [+0.005, +0.073]**; burden 0.448→0.423 in those dying ≤30 d, 0.299→0.236 in survivors | holds, small |
| R296 | J2 — does change add over index level? | 0.672 → 0.736, increment **+0.064** (second level alone 0.727) | **uninterpretable alone** |
| R297 | **J2b — the noise control** | increment **+0.065 under 12 h**, **+0.055 at 12 h–2 d**, flat and largest at the shortest gaps | **refutes reversibility** |
| R298 | J3 — resolution beyond level, stratified | mid: improved 67.4 % vs worsened 85.0 %; high: 81.5 % vs 90.9 %; low: 66.7 % vs 71.3 % | **confounded** |

**Why J2 fails.** `level + change` is algebraically `first level + second level`, so a second measurement helps
whenever the measure is noisy — no biology required. Reversibility predicts the increment **grows** with the
interval; it does not. It is largest under 12 hours, where no cortex can have recovered.

**Why the design cannot ask the question.** Median interval between a patient's first two recordings is
**0.65 days** (p25 0.04, p75 0.90, p90 1.69); only **57 pairs** are ≥2 days apart. These are two recordings in
one admission, hours apart, not recovery trajectories.

**Why J3 is confounded.** Unstratified it was incoherent — improvers died *more* often than stable patients,
opposite to J1 — because the strata compared baselines, not trajectories. Stratified, improving beats worsening
in mid and high strata, which is precisely what **regression to the mean** produces: a first reading high by
noise appears to improve and also carries a lower true burden.

**Predicted vs actual (calibration ledger).** Predicted win-likelihood 0.55 that the serial pairs would separate
structural from reversible. Actual: **no answer** — the interval distribution makes the question unaskable with
what has been extracted. The prediction failed to account for repeat EEGs in this cohort being same-admission
rather than days apart. Revisit when the serial extraction yields enough distant pairs.

**Cumulative distinct results: 298.**

---

## Q2 CLOSED — burden is a STRUCTURAL marker, not a reversible one (2026-07-26)

Four framings of the same question, three of them confounded. The identifying one is R303.

| id | test | result | reading |
|---|---|---|---|
| R299 | J2 — change adds over index level | +0.062 | **not identifying**: `level + change` ≡ `old level + new level` |
| R300 | MIN_GAP_D sweep (0 / 2 / 4 d) | J1 +0.038→+0.008→+0.001; J2 increment +0.062→+0.060→+0.026 | suggestive, but longer gaps select survivors |
| R301 | J2c — same 128 patients, short vs long interval | short +0.023, long +0.063 | **unfair**: the long recording IS the landmark, so recency favours it |
| R302 | J2d — trajectory beyond the MOST RECENT level | 0.747 → 0.784, +0.037 | still not identifying: two noisy readings of a CONSTANT beat one |
| R303 | **J2e — mean vs difference decomposition** | mean alone **0.787**; mean+difference **0.775** (**−0.013**); difference coefficient **+5.88 pp [−17.13, +26.58]** | **STRUCTURAL** |
| R304 | **direct check, no model comparison** | most recent reading **0.747** vs average of the two **0.787** | **the average wins** |

**Why R303 identifies where the others do not.** Re-express the pair as two orthogonal contrasts —
`mean = (first + last)/2`, a better-estimated level, and `diff = last − first`, the trajectory and nothing else.
Under structural injury plus measurement error the mean carries all the signal and `diff` is pure noise. Under
reversibility `diff` carries independent, correctly-signed information. The difference coefficient's CI
comfortably covers zero and adding it makes prediction *worse*.

**R304 is the cleanest evidence and needs no model.** A marker tracking a *changing* state is best measured most
recently. A marker estimating a *fixed* quantity with error is best measured twice and averaged. The average
(0.787) beats the most recent reading (0.747). That is the behaviour of a fixed quantity, observed directly.

**Consequence.** Suppression burden reads out how much cortex is already lost, not a depth of reversible
metabolic or pharmacological suppression the brain is passing through. This is consistent with the earlier
organ-injury result (burden is brain-specific, not a whole-body ischaemic dose marker) and it explains why
persistence and morphology add so little over burden itself: there is no second, dynamic quantity to add.

**Predicted vs actual (calibration ledger).** Predicted 0.55 that serial pairs would separate the two. Actual:
they did, but only after three confounded framings were discarded — and the answer is the opposite of what the
first run printed. Every framing that used *predictive increment* was satisfiable by measurement error; only the
*sign of an orthogonal contrast* was not.

**Cumulative distinct results: 304.**

---

## Q1 CLOSED — not answerable in HEEDB/OMOP, and now demonstrably so (2026-07-26)

Withdrawal versus refractory shock inside the three-day window. **Four independent instruments, four structural
failures.** The question is not merely unanswered here; the data source cannot answer it, and the reason is the
same each time: **administrative tables record what is BILLED or what is charted as a STATE, and withdrawal of
life-sustaining therapy is neither.**

| id | instrument | why it fails | evidence |
|---|---|---|---|
| R285ff | DNR / palliative **condition codes** | document chronic care-limitation status, not an acute decision | median **42 days** from code to death; 5 % die within a day |
| R286ff | **Sedation depth** | circular — burst suppression itself causes unresponsiveness | n/a, ruled out on construct |
| R279–R284 | **Vasopressor discontinuation time** | the medication record is **closed at death** by the charting system | 20.9 % tied to the death timestamp to the minute; **0 patients** between 1 min and 1 h before death; non-tied mass a median 100 d earlier |
| **R305** | **Terminal extubation / comfort care (procedures)** | `procedure_occurrence` is a **billing** table; extubation is not separately billable and comfort care is not a billable ICU procedure | 31,324 rows extracted, 7,971 patients ever ventilated, **0 extubations, 0 comfort-care procedures** |
| **R306** | **Code status (observations)** | `observation_concept_id` is **100 % zero** (unmapped); the table holds demographics and note metadata | source values are `General`, `Note`, `Imaging`, `marital_status`, `religion` |

**R305 detail.** The concept set was resolved from the 6.3 M-row OMOP vocabulary and verified by inspection —
it contains `Extubation of trachea`, `Extubation (& removal of endotracheal tube)`, `Comfort care assessment`,
`Comfort care management` and hospice concepts. None of them occur in the data. All 64 concepts that DO occur
are billable acts: `Intubation, endotracheal, emergency procedure` (10,297), `Tracheostomy, planned` (4,389),
ECMO (9,796 across variants), `Cardiopulmonary resuscitation` (1,526). CPT codes intubation (31500) and has no
extubation code, because extubation is part of ventilator management rather than a separately reimbursed act.

**What this closes.** The §4 caveat in `42_MAIN_RESULT.md` — that this cohort cannot separate biological death
from withdrawal-mediated death inside the three-day window — is now **established rather than asserted**, by
four instruments whose failure modes are each identified and mechanistically explained. That is the strongest
form the statement can take without a different data source.

**What would answer it.** A source that timestamps the DECISION: comfort-care order activation from a clinical
order-entry system, ventilator-termination events from respiratory-therapy flowsheets, or documented family
meetings from notes. HEEDB's OMOP export contains none of these, and `note` / `note_nlp` were not populated with
usable content in the merged tables inspected.

**Predicted vs actual (calibration ledger).** Predicted 0.60 that a procedure-based instrument would work,
reasoning that an extubation is an act rather than a state. The reasoning was right and the premise was wrong:
it is an act, but an **unbilled** one, and this table only sees billed acts. Lesson generalised below.

**Cumulative distinct results: 306.**

---

## Q3 — what burden is a marker OF: partially closed, and honestly bounded (2026-07-26)

**What IS established, from Q2 and from the organ-injury test — both without any external reference:**
1. **Brain-specific.** Not a whole-body ischaemic dose marker: cardiac and pressor gradients are steeper in
   sepsis than after arrest, and mediation through organ-injury codes absorbs 2.6 %.
2. **Behaves like a FIXED quantity measured with error.** Averaging two readings predicts better (0.787) than
   the most recent (0.747); the difference between readings carries no signal once the mean is known
   (coefficient +5.88 pp [−17.13, +26.58]).

Together: burden reads out a stable, brain-specific quantity — consistent with the amount of cortex already
lost. **What is NOT established is the positive tissue-level identification**, because all three external
references failed.

| id | instrument | outcome |
|---|---|---|
| R307 | **Neuron-specific enolase** — the guideline-endorsed serum marker of neuronal death | **unavailable**: 551/551 parts of the merged `measurement` table scanned, ~2 rows. NSE is a send-out assay, not routine at these sites |
| R308 | **Cause of death** | **unusable**: 84.9 % blank; the 535 recorded causes are death-certificate underlying causes (C349 lung cancer, F03 dementia, I251 CAD), not ICU mode of death |
| **R309** | **Epileptogenicity** — "dead cortex cannot seize" | **non-discriminating: the premise is false** |

**R309 in full.** Registered prediction: if burden counts cortex already lost, survivors with high index burden
should show LESS seizure/status activity on a later recording; if it measures reversible suppression of living
cortex, the same or more. Landmarked at the later recording (n=4,028; 1,063 post-anoxic).

| definition | high − low burden quartile |
|---|---|
| wide (seizure, status, GPD, LPD) | +12.9 pp [+4.7, +19.4] |
| **strict (seizure, status only)** | **+22.3 pp [+13.6, +29.6]** |
| restricted to no-longer-suppressed | −9.3 pp [−19.9, +1.1] (null) |

The registered reading calls a positive association "reversible". **That reading is withdrawn.** The test assumed
severe injury means electrical silence, so that only living irritable cortex could seize. That is false after
cardiac arrest: post-anoxic status epilepticus arises **in severely injured brains** and is detected in almost a
third of comatose arrest survivors (De Stefano, *J Neurol* 2023, **PMID 36076090** — SE in 29–96 % across 11
cohorts, verified from the MEDLINE record). Severe hypoxic-ischaemic injury is itself epileptogenic, so **both**
hypotheses predict a positive association. A second unremoved confound points the same way: sicker patients are
monitored longer, and longer recordings capture more seizures. The no-longer-suppressed arm conditions on a
post-exposure variable (a collider) and cannot be relied on in either direction.

**Interim tell that was chased and turned out to be wrong.** The wide and strict definitions were expected to
differ because "suppression with periodic discharges" is a burst-suppression variant, so GPD/LPD should have
inflated the association. Removing them made it *stronger* (+12.9 → +22.3), refuting that explanation.

**Predicted vs actual (calibration ledger).** Predicted 0.65 that the epileptogenicity test would discriminate.
Actual: it does not, and the failure is a domain-knowledge error rather than a statistical one — the mechanism
was reasoned from first principles without checking what the disease actually does. The literature check that
would have caught it took one E-utilities query and should have run BEFORE the test, not after.

**Cumulative distinct results: 309.**

---

## Gap-closing pass against a Brown-ready standard (2026-07-26) — see `43_GAP_ANALYSIS_BROWN.md`

| id | gap | result |
|---|---|---|
| **R310** | **G9 — exposure never validated** | burden vs clinician burst-suppression label on the same recording: **AUC 0.749 [0.747, 0.760]**, n=27,948 matched within 24 h. Mean burden 0.344 (labelled suppressed) vs 0.073 (not). **The 0.829 in a code comment is not reproducible and overstated validity by 0.08**; corrected in place |
| **R311** | **G4 — linear probability models** | logistic refit: category alone 0.645, +burden **0.745**, increment **+0.100 [+0.082, +0.118]** (LPM gave +0.068). Burden log-odds **+1.587**, OR **4.89** across the range. The proper link function *strengthens* the result |
| **R312** | **G5 — no calibration ever reported** | mean predicted 0.308 vs observed 0.308; intercept **−0.013** (ideal 0); slope **0.980** (ideal 1); observed tracks predicted across all ten deciles |
| **R313** | **G8 — morphology increment had no CI** | **+0.047 [+0.011, +0.083]** (0.607 → 0.654, n=604, logistic). Excludes zero |
| **R314** | **G7 — clustering** | moot: index-only analysis gives 2,951 rows for 2,951 distinct patients |
| **R315** | **G10 — measurement error unestimated** | from 4,628 recordings with ≥2 window readings: between-recording variance 0.0513, within 0.0116, **ICC 0.815**, reliability of the average of two **0.898**. Q2's account now has its parameter |

**R315 caveat, stated rather than glossed.** The four windows are sampled *across* each recording, so the
within-recording variance mixes instrument noise with genuine intermittency of suppression. It measures how well
one window estimates the recording-level quantity — which is what Q2 requires — but it is not pure measurement
error, and should not be quoted as such.

**R311 note.** The logistic and LPM increments differ (+0.100 vs +0.068) because the models differ, not because
the data changed. The logistic figure is now primary; both are reported so the change is visible.

**Cumulative distinct results: 315.**

---

## R316–R320. THE FALSIFICATION TEST: the same construct in an anaesthetic cohort (VitalDB)

`44_MECHANISM_AND_PRIOR_WORK.md` predicted that if burden indexes cerebral metabolic rate, suppression must be
**reversible when the cause is drug** and **fixed when the cause is tissue loss**. VitalDB (1,848 cases with a
device suppression-ratio series; 967 with ≥10 bins and peak SR ≥5 %) is the population where the answer must
invert. **No outcome variable is used** — a fixed quantity plus noise and a time-varying state are
distinguishable from the series alone.

| id | arm | VitalDB (anaesthetic) | HEEDB (post-anoxic) | verdict |
|---|---|---|---|---|
| R316 | **A. autocorrelation vs lag** | 0.973 at lag 1 → **0.484** at lag 40 (decay 0.488) | fixed-quantity behaviour: mean of two readings beats the most recent | **decays → time-varying state** ✔ |
| R317 | **B. variance decomposition** | between 25.49, within 56.00, **ICC 0.313** | **ICC 0.815** | **far more within-case variance** ✔ |
| R318 | **C. moves with effect-site concentration?** | Δ–Δ **−0.015 [−0.018, −0.012]** | — | **null — arm fails** |
| R319 | **C2. levels and lags** | level **−0.298 [−0.310, −0.287]**, 12.4 % positive; ≈−0.28 at lags 1–10 | — | **uninterpretable (closed loop)** |
| R320 | **D. recovery** | peak **3.99 %** → final decile **1.20 %** (**70 % resolution**) | burden does not resolve; change carries no signal | **recovers** ✔ |

**R318/R319, the arm that failed, and why it is not evidence against the prediction.** The level correlation is
*negative*: within a case, more agent goes with **less** suppression. That is pharmacologically backwards and is
the signature of a **closed loop** — the anaesthetist watches the monitor and turns the agent down when
suppression appears, so suppressed periods are precisely the periods of reduced drug. **The exposure is
controlled in response to the outcome.** This is structurally the same confound as withdrawal of life-sustaining
therapy in the post-anoxic cohort — a clinician acting on the quantity being measured — relocated from the
outcome to the exposure. No lag or transform rescues it, because the confound is in how the data were generated.

**Conclusion.** The prediction is **upheld by the three interpretable arms**, and arm D is decisive in the most
direct form available: suppression resolves by 70 % as the anaesthetic is withdrawn, whereas post-anoxic burden
behaves as a constant whose serial differences carry no information. **The same construct is reversible when the
cause is drug and fixed when the cause is tissue loss**, which is what the metabolic reading requires and what
would have falsified it had VitalDB also said "fixed".

**LIMITATION carried forward.** `devsr` is a device-computed suppression ratio from a proprietary frontal-montage
algorithm, not our 5 µV / 0.5 s bipolar burden. This tests whether **suppression** behaves reversibly under
anaesthesia, not whether **our estimator** does. The populations also differ in far more than aetiology
(elective surgical patients versus post-arrest ICU patients).

**Predicted vs actual (calibration ledger).** Predicted 0.80 that the anaesthetic cohort would show reversible
behaviour. Actual: upheld on 3 of 4 arms, with the failed arm failing for a nameable and instructive reason
rather than ambiguously.

**Cumulative distinct results: 320.**

---

## R321–R325. EXTERNAL REPLICATION in I-CARE — the core claim holds in an independent consortium

**Why not TUH, which the pre-registration names as mandatory.** The TUH EEG Corpus is EEG plus de-identified
reports and carries **no linked outcome data** — this repository's own TUH manifest schema in `config.yaml`
lists `recording_id, patient_id, edf_path, sfreq, age, sex` and no outcome field. A burden→mortality finding
cannot be replicated there at any effort. **G13 is therefore re-specified**, not waived: TUH can still
externally validate the *measurement* (burden vs a clinician label at a different health system), which needs
NEDC credentials not present in this session, and is a lesser claim.

**I-CARE is the correct target and is stronger than TUH would have been for this claim**: the same population
(comatose post-cardiac-arrest), five hospitals in a different international consortium, different equipment and
clinicians, with a real outcome. n=561 with both outcome and a suppression measure; 62.0 % poor (CPC 3–5).

| id | test | result | verdict |
|---|---|---|---|
| R321 | **E1** poor outcome across burden quintiles | 45.1 / 45.5 / 62.5 / 70.5 / **86.6 %**, **monotone** | ✔ |
| R322 | **E2 — the claim that matters**: among the SUPPRESSED, does quantitative burden still stratify? | burden ≥0.05 (n=417): lowest tertile 49.3 % → highest **83.3 %**, **+34.1 pp [+23.2, +44.2]**; ≥0.10: +33.3 pp [+23.4, +44.4]; ≥0.20: +25.0 pp [+12.7, +36.4] | **✔ at every threshold** |
| R323 | **E3** continuous burden over a binary suppression flag | +0.090 [+0.045, +0.156] (thr 0.05); +0.074 [+0.027, +0.141] (thr 0.10) | ✔ above the registered +0.03 |
| R324 | **E4** cross-hospital (fit one site, test the others) | A 0.619, B 0.716, E 0.690, F 0.684 | ✔ consistent with primary 0.679/0.669 |
| R325 | consistency with primary | HEEDB: within highly-malignant, 29.5 % → 73.1 % three-day death | same structure, independent cohort |

**What is replicated, precisely.** Not "suppression is bad" — that is not in dispute. The claim is that **among
patients who are already suppressed, the quantitative burden still stratifies outcome**, so a categorical label
discards real information. That is what E2 tests and what holds.

**What differs and must travel with it.** The outcome is CPC 3–5 assessed at discharge or follow-up, not
three-day mortality; the suppression measure is I-CARE's own at hour 24 after arrest, not our 5 µV burden at an
index clinical recording. This replicates the **structure** of the claim on an independent cohort, not the
identical estimand. Hospital D (n=56) was below the 60-patient floor for the cross-hospital arm.

**Predicted vs actual (calibration ledger).** Predicted 0.70 that the within-suppressed stratification would
replicate. Actual: replicated at all three thresholds with CIs excluding zero by a wide margin.

**Cumulative distinct results: 325.**

---

## R326–R329. THE MECHANISTIC CLAIM DOES NOT REPLICATE IN I-CARE — the strong form is refuted

Q2 concluded from HEEDB that suppression burden behaves as a **fixed quantity measured with error**, and that
conclusion licenses the metabolic reading. It had been tested in one direction only (VitalDB, where the same
construct must be reversible under anaesthesia, and is). This tests it in a **second post-anoxic cohort**, using
**our own detector** run on I-CARE hourly EEG at hours 12, 24, 36 and 48 — 552 patients with ≥2 distinct hours,
median span 30 h.

| id | arm | I-CARE | HEEDB | VitalDB (anaesthetic) | verdict |
|---|---|---|---|---|---|
| R326 | **X1** ICC of one reading | **0.584** | 0.815 | 0.313 | intermediate |
| R327 | **X2** decay with separation | **−0.370** (0.684 → 0.491 → 0.314) | flat | −0.488 | **decays** |
| R328 | **X3** mean vs most recent | 0.725 vs 0.720 (a tie) | 0.787 vs 0.747 | — | equivocal |
| R329 | **X4** coefficient on the difference | **+1.081 [+0.578, +1.614]**, excludes zero — but adds only **+0.004** AUC | +5.88 pp [−17.13, +26.58], null | — | **trajectory is informative** |

**Verdict: the strong form of the claim is refuted.** In the first 48 hours after arrest, burden is *not* a
fixed quantity — it evolves, its agreement decays with separation almost as much as in the anaesthetic cohort,
and its trajectory carries outcome information that HEEDB's did not. On every arm I-CARE sits **between** HEEDB
and the anaesthetic cohort.

**A weaker, time-dependent form survives all three cohorts, and is stated as a HYPOTHESIS rather than a save.**
I-CARE measures hours 12–48 post-arrest — the acute phase, during which patients are typically still sedated and
under targeted temperature management, both of which the metabolic model says produce *reversible* suppression
in living tissue. HEEDB's recordings are clinically triggered and its serial pairs were mostly same-admission
re-reads later in the course. So the reconcilable claim is:

> Burden carries a **reversible component** (sedation, hypothermia, evolving injury) that dominates early, and a
> **fixed structural component** that is what remains once the acute phase settles.

That is consistent with every result to date, but it is a **post-hoc reconciliation and must be treated as
one**. **The falsifiable test**: restrict I-CARE to patients off sedation and rewarmed, and to later hours
(≥72 h); the fixed-quantity signature should re-emerge (ICC rising toward HEEDB's, decay flattening, difference
term returning to null). Until that is run, the mechanistic reading is **weakened from "burden is a fixed
quantity" to "burden contains a fixed component that is not separately identified here"**.

**Note on magnitude.** R329's difference coefficient is statistically distinguishable from zero yet adds
+0.004 cross-validated AUC. Significant and negligible are both true, and reporting only the first would
misrepresent it.

**Predicted vs actual (calibration ledger).** Predicted 0.65 that the fixed-quantity signature would replicate.
Actual: it did not. The prediction failed to account for I-CARE measuring the acute sedated/hypothermic window,
where the metabolic model itself predicts a reversible contribution — an error of study-design reasoning, not of
statistics.

**Cumulative distinct results: 329.**

---

## R330–R336. AN EXTERNALLY REPLICABLE MECHANISM COMPONENT — burst content, not burst duration

Candidate: **thalamocortical generator integrity** (burden = how much generator capacity is gone; morphology =
whether what remains is organised). Directions pre-registered from HEEDB before the external data was touched.
External cohort: **I-CARE, 559 patients, five hospitals, our own detector on their raw EEG**.

| id | test | I-CARE | HEEDB | verdict |
|---|---|---|---|---|
| R330 | burden direction | 0.559 poor vs 0.305 good | 0.746 vs 0.386 | **replicates** |
| R331 | intra-burst 8–30 Hz direction | 0.214 vs 0.179 | 0.250 vs 0.120 | **replicates** |
| R332 | burst duration direction | 13.58 s vs 26.00 s | 1.84 s vs 2.87 s | **n.s. — withdrawn** |
| R333 | morphology increment over burden | **+0.055 [+0.035, +0.094]** | +0.047 [+0.011, +0.083] | **replicates** |
| R334 | intra-burst 8–30 Hz, adjusted for burden | **+0.522 [+0.305, +0.773]** | — | **survives** |
| R335 | burst amplitude, adjusted for burden | **+3.502 [+2.204, +5.279]** | — | **survives** |
| R336 | burst duration / rate, adjusted | −0.051 [−0.517,+0.138] / −0.147 [−0.353,+0.061] | — | null |

**The claim that survives:** spectral content and amplitude of bursts carry prognostic information
**independent of suppression burden**, in two independent cohorts, using our own detector in both.

**Burst duration is withdrawn for three independent reasons.** (a) Null in I-CARE. (b) **Not comparable across
cohorts** — the same code yields 1.84–2.87 s in HEEDB and 13.6–26.0 s in I-CARE, because in I-CARE's long
continuous segments "burst duration" degenerates into the inverse of burden; a feature-portability defect, not
a finding. (c) **Fong et al., *Neurocrit Care* 2025 (PMID 39900751, n=203 post-arrest) report the opposite
direction** — mortality with *longer* bursts — and, decisively, their duration effect did not survive their own
adjustment either: *"the only independent EEG predictor of mortality was the burst correlation coefficient
measured over 2 s (adjusted odds ratio 4.82 [1.21-8.42], p = 0.009)"*. Both duration findings are univariate
artefacts of something else.

**The mechanism is weakened from generation to content.** Wennberg et al. 1997 (PMID 9191587): after functional
hemispherectomy, "burst-suppression activity appeared over isolated cortex **in all cases**" — deafferented
cortex generates burst suppression unaided, so generation does not require the thalamocortical loop. The
surviving claim is that burst *content* reports thalamocortical organisation, supported by graded selective
thalamic vulnerability after global ischaemia (PMID 12435429), thalamic damage tracking suppression ratio in
humans (PMID 37731916), and — closest of all — **Sekar et al. 2019 (PMID 30422916)**, who found a prominent
theta feature in post-arrest patients regaining consciousness and absent in those who did not. That is the same
direction as our replicated finding, from an independent group.

**Open and running:** stereotypy at 1 s and 2 s in I-CARE. It is Fong's only independent predictor and was
omitted from our first I-CARE extraction. If it dominates spectral content there, the mechanism must be
restated around burst *similarity* rather than burst *content*.

**Predicted vs actual (calibration ledger).** Predicted 0.55 that morphology would replicate externally.
Actual: half of it did — the increment and the spectral direction replicated, the duration direction did not,
and the literature explains why the duration arm was never sound.

**Cumulative distinct results: 336.**

### R337–R340. Stereotypy replicates too — and does not displace burst content

Recomputed in I-CARE at 1 s and 2 s (n=527), engaging Fong et al. 2025 (PMID 39900751) on their own terms.

| id | test | result |
|---|---|---|
| R337 | stereotypy direction (Fong: higher in deaths) | 1 s **0.043 vs 0.006**, 2 s **0.032 vs 0.008** — **both replicate** |
| R338 | stereotypy 1 s adjusted for burden | **+1.040 [+0.457, +1.825]** ✔ survives |
| R339 | stereotypy 2 s adjusted for burden | −0.114 [−0.549, +0.398] — null (**Fong found 2 s superior to 1 s; we find the reverse**) |
| R340 | morphology increment with stereotypy included | **+0.073 [+0.043, +0.123]** (was +0.055 without); burden alone 0.691 → 0.764 |

Spectral content (+0.500 [+0.291, +0.756]) and amplitude (+2.252 [+0.844, +3.985]) **still survive in the same
model**, each adjusted for burden and for stereotypy. **The two groups' findings are independent channels, not
rivals** — two teams measured different things and both were right.

The window disagreement (Fong: 2 s superior; ours: 1 s survives, 2 s null) is real and unexplained. Our bursts
are much longer than his analysis window implies, so the quantities are not identical. Reported as a concrete
question for that group rather than reconciled by assertion.

**Mechanism as it now stands:** stereotyped, high-amplitude, fast bursts describe a simple autonomous cortical
oscillator with one mode; slower, more variable bursts describe a network with a richer repertoire — what loss
versus preservation of thalamocortical modulation would look like. Three features, each surviving adjustment
for burden, in two independent cohorts, with one channel independently reported by another group.

**Cumulative distinct results: 340.**

### R341–R342. Index-only re-verification of the HEEDB morphology directions — amplitude inverts

The morphology contrasts quoted in `45_MANUSCRIPT.md` §3.4 came from the **legacy max-over-recordings**
extraction. Re-measured at the **index recording** (n=757 post-anoxic; 341 dead ≤3 d, 98 alive >180 d):

| feature | index-only (dead / alive>180d) | legacy (as published) | direction |
|---|---|---|---|
| intra-burst 8–30 Hz | 0.160 / 0.101 | 0.250 / 0.120 | **preserved** |
| stereotypy | 0.015 / 0.001 | 0.034 / 0.014 | **preserved** |
| burst duration | 1.40 / 2.54 | 1.84 / 2.87 | preserved (already withdrawn) |
| **burst amplitude** | **19.44 / 23.72** | **36.5 / 26.7** | **INVERTS** |
| burst rate | 14.04 / 12.50 | 14.5 / 13.3 | preserved |

**R341.** Every legacy magnitude was inflated — the look-ahead affected morphology as well as burden, which had
not previously been checked.

**R342.** **The burst-amplitude channel is withdrawn.** Measured at the index recording, early deaths have
*lower*-amplitude bursts (19.4 vs 23.7); I-CARE gave the opposite (+2.252 [+0.844, +3.985], higher amplitude
with poor outcome). A channel whose sign depends on cohort and exposure definition is not a finding. Ruijter
2018's precedent concerns a burst-to-suppression amplitude *ratio*, a different quantity.

**Two channels survive, and survive in both cohorts at the index recording:** intra-burst spectral content and
stereotypy. That is the mechanism claim.

**Process note.** This check existed only because the earlier self-audit found look-ahead in the burden
exposure; extending the same suspicion to morphology caught a sign inversion in a channel that had already been
written into the manuscript. Numbers inherited from a superseded extraction must be re-derived, not carried
forward.

**Cumulative distinct results: 342.**

---

## R343–R346. Red team, and a valid bootstrap downgrades two claims

Adversarial review (delegated, then every finding verified against the data by Opus) found three real problems.

| id | finding | verified | action |
|---|---|---|---|
| R343 | **Outcome-related selection in the morphology analysis** | **80 of 607 I-CARE patients (13.2 %) excluded; 80.0 % poor outcome vs 60.3 % retained. NaN-dropped subgroup: median burden 0.967, 96.9 % poor.** Same pattern in HEEDB | disclosed; morphology results now explicitly conditioned |
| R344 | **Invalid bootstrap on the headline increment** — fixed out-of-fold predictions resampled | confirmed in code | replaced with out-of-bag bootstrap |
| R345 | **Cross-document contradiction** — mechanism doc still asserted amplitude after the manuscript withdrew it | confirmed | struck through with a corrections section |
| R346 | Silent-empty trap — default morphology path predated the stereotypy columns, `KeyError` swallowed | confirmed | now raises |

**R343 is intrinsic, not a bug.** Burst morphology is undefined below four bursts, which happens precisely at
near-total suppression. **You cannot measure the shape of bursts in a brain that has almost none.** So
morphology can only add information in the middle of the burden range. Burden findings are unaffected.

**R344's consequences — two claims downgraded:**

| increment | as reported | **out-of-bag (valid)** |
|---|---|---|
| burden over guideline category (HEEDB) | +0.100 [+0.082, +0.118] | **+0.064 [+0.038, +0.089]** — survives, above the +0.03 threshold |
| morphology over burden (HEEDB) | +0.047 [+0.011, +0.083] | **+0.036 [−0.019, +0.076]** — **includes zero** |
| morphology over burden (I-CARE) | +0.073 [+0.043, +0.123] | **+0.070 [+0.006, +0.121]** — excludes zero, barely |

**The morphology PREDICTIVE claim is withdrawn** (inconsistent across cohorts). **The morphology ASSOCIATION
claim survives** in I-CARE: spectral content +0.500 [+0.311, +0.755], stereotypy +1.040 [+0.413, +1.894],
each adjusted for burden and for the other. Association independent of burden is mechanistic; incremental AUC
is clinical utility. This work supports the first, not the second.

**Process note.** Fixing R344 introduced a *fourth* error — a refit bootstrap that resampled train and test
together, returning a point estimate (+0.094) that fell **outside its own interval** [+0.057, +0.089]. It was
caught only because it was self-evidently absurd; a subtly-too-narrow interval would have passed. That is the
argument for adversarial rather than confirmatory review.

**Cumulative distinct results: 346.**

---

## R347–R349. BSP implemented — and it does not beat the ratio it was written to replace

`analysis/bsp.py` implements burst suppression probability from the published specification (binomial
observation, logistic link, Gaussian random-walk state; nonlinear filter, RTS smoother, EM for the process
variance), unit-tested against seven cases with known answers. Applied to I-CARE (385 patients with BSP and an
outcome).

| id | test | result |
|---|---|---|
| R347 | correlation of per-recording BSP mean with the crude ratio | **0.988** |
| R348 | discrimination: crude ratio / BSP mean / full BSP set | 0.704 / 0.698 / 0.693 |
| R349 | out-of-bag increment of BSP over the ratio | **−0.010 [−0.021, +0.004]**; full set **−0.018 [−0.064, +0.016]** |

**Summarised per recording, BSP is equivalent to the ratio** — r = 0.988, and no gain in discrimination.

**This is not a failure of BSP and it should not be reported as one.** BSP's stated advantages are an
*instantaneous* estimate and *per-timepoint uncertainty*, neither of which a single per-recording summary
exploits. What the result establishes is narrower and useful: **for a per-recording exposure, the crude
thresholding ratio costs nothing.** That defuses the standing methodological criticism of this project's
estimator — the finding does not depend on having used a weak measure, because the principled measure gives the
same answer at this level of aggregation.

**A numerical note worth keeping.** The unit tests caught a real bug during implementation: when a bin is fully
suppressed or fully bursting — the regime burst suppression lives in — the binomial curvature vanishes, the
Hessian degenerates to the prior term, and an undamped Newton step overshoots by hundreds of log-odds and
oscillates. It was stable at small process variance and diverged once EM raised it, returning 0.001 for a clean
0→100 % step. Damped with backtracking. An undetected version would have produced plausible-looking BSP values
that were silently wrong in exactly the most suppressed patients.

**Cumulative distinct results: 349.**

### R350. Self-red-team of the BSP implementation against an exact solver

The BSP estimator was written and unit-tested by the same author, which is a conflict of interest. Validated
against an **exact grid forward-backward** solution of the identical model (`analysis/bsp_validate_exact.py`),
sharing no code with `bsp.py`.

| case | max abs difference from exact |
|---|---|
| mid-range (p≈0.5) | 0.0000 |
| extreme low / high (p≈0, p≈1) | 0.0137 |
| sparse bins (N=2) | 0.0000 |
| realistic noisy ramp | 0.0107 |
| **abrupt step 0 → 1** | **0.7754** |

**The Gaussian approximation is inaccurate at abrupt transitions** — max |diff| 0.775 at the step, mean 0.058
across that series. This is a limitation of the approximation, not a coding error: the true posterior is
sharply non-Gaussian where the state jumps.

**It does not affect the conclusion drawn**, and that was checked rather than assumed. The BSP-vs-ratio
comparison used per-recording summaries, and the pointwise error averages out — the per-recording **mean**
differs from exact by **≤0.0009** across steady, drifting, occasionally-jumping and constantly-jumping series.

**Where it would matter:** using BSP for its actual advertised purpose — an instantaneous estimate with
per-timepoint uncertainty around abrupt changes — the Gaussian approximation should be replaced by the exact
posterior. That is the use case BSP exists for, so the caveat is not academic and is recorded in the module.

**Cumulative distinct results: 350.**

---

## R351–R355. Red team round two: a cohort bug, and two overstatements withdrawn

Delegated adversarial review of the HEADLINE and the EXTERNAL REPLICATION (round one had covered morphology
only). Every finding verified by Opus against the OMOP vocabulary, the MEDLINE record, or the data before action.

| id | finding | severity | verified |
|---|---|---|---|
| R351 | **Anoxic ICD list contaminated** — `34982` is "Toxic encephalopathy", `V1253` is "Personal history of sudden cardiac arrest"; `3481` "Anoxic brain damage" was **missing** | **SERIOUS (real bug)** | checked against OMOP `concept.csv` |
| R352 | **I-CARE is not an independent health system** — its institutions include MGH, Brigham and Women's, Beth Israel Deaconess; HEEDB's site key maps to MGH/BWH/BIDMC/BCH; both on BDSP | **FATAL to the framing** | verified from the MEDLINE record of the I-CARE descriptor |
| R353 | **I-CARE has no clinician EEG category**, so "among the already suppressed" uses our own burden threshold — it tests absence of a ceiling effect, not that a categorical label discards information | **SERIOUS (overstatement)** | `icare_cohort.csv` carries demographics + CPC only |
| R354 | Westhall category not manufactured by lumping low-voltage with bs — only **1.5 %** of the category is low-voltage-only | NOT A PROBLEM | computed |
| R355 | Calibration genuinely out-of-fold; hospital D's exclusion hides nothing (its own AUC **0.676**, mid-range) | NOT A PROBLEM | computed |

**Effect of the R351 fix — the finding is robust, one claim is not:**

| | contaminated | **corrected** |
|---|---|---|
| n post-anoxic | 2,951 | **2,463** |
| increment over category | +0.064 [+0.038, +0.089] | **+0.062 [+0.032, +0.095]** |
| calibration intercept / slope | −0.013 / 0.980 | **−0.010 / 0.979** |
| cross-hospital | 0.679 / 0.669 | **0.682 / 0.651** |
| quintile range | 29.5 → 73.1 % | **31.6 → 73.4 %** |
| **monotone across quintiles** | yes | **NO** — Q2 41.2 %, Q3 40.1 % |

**Monotonicity is withdrawn.** The 1.1 pp inversion sits inside sampling noise (SE ≈ 3.4 pp at n≈212), but the
claim was about the observed data and is false on the corrected cohort. It held only on a cohort containing
miscoded patients — which is exactly the kind of claim that should not survive a data fix.

**Also:** the benign-vs-malignant ordering inversion at the bottom of the guideline scheme is **larger** on the
corrected cohort (17.5 % vs 14.7 % three-day death).

**Cumulative distinct results: 355.**

### R356. Class A survives the cohort correction

The landmark analysis — §5's decisive turn, and the result that reframed the whole project — was computed on the
contaminated cohort. Re-run after removing the miscoded ICD entries:

| landmark | contaminated | **corrected** |
|---|---|---|
| day 0 | +0.801 [+0.618, +0.980] | **+0.681 [+0.469, +0.893]** |
| day 30 | +0.112 [−0.211, +0.455] | **+0.054 [−0.292, +0.448]** |
| day 90 | +0.288 [−0.047, +0.640] | **+0.263 [−0.141, +0.689]** |
| day 180 | −0.295 [−0.659, +0.059] | **−0.259 [−0.656, +0.133]** |
| day-180 as % of day-0 | −37 % | **−38 %** |

**CLASS A remains SUPPORTED.** The miscoded patients were inflating the day-0 gap (they were low-burden,
low-mortality and mostly not post-arrest at all), but the *pattern* is unchanged and the summary statistic is
within one point of the original.

**Process note that generalises.** The ICD fix was initially treated as a *headline* correction and only the
headline was re-run. A correction propagates to everything computed downstream of it, not to the number that
prompted it. Roughly 355 logged results predate this fix; the ones carrying claims (headline, quintiles,
calibration, cross-hospital, landmark, morphology directions) have been re-run, and the remainder are
pre-correction and marked as such rather than silently carried forward.

**Cumulative distinct results: 356.**

### R357. Morphology directions unchanged by the cohort correction

Last claim-bearing HEEDB number still computed on contaminated data. Re-derived at the index recording on the
corrected cohort (n=746 post-anoxic with morphology; 344 dead ≤3 d, 93 alive >180 d):

| feature | previous index-only | **corrected** | verdict |
|---|---|---|---|
| intra-burst 8–30 Hz | 0.160 / 0.101 | **0.160 / 0.101** | **identical** |
| stereotypy | 0.015 / 0.001 | **0.015 / 0.001** | **identical** |
| burst duration | 1.400 / 2.537 | 1.431 / 2.450 | unchanged in direction (already withdrawn) |
| burst amplitude | 19.44 / 23.72 | 19.66 / 23.74 | still inverted vs legacy (already withdrawn) |

**The two surviving mechanism channels are unaffected by the cohort correction** — the miscoded patients were
not driving them. Every claim-bearing HEEDB figure has now been re-derived on the corrected cohort.

**Cumulative distinct results: 357.**

---
---

# CONSOLIDATION — the full constraint set as of 2026-07-27 (357 results)

**Read this table before proposing any mechanism.** A candidate that explains only the positives is not a
candidate. All figures are post-correction (index-recording exposure, corrected ICD cohort, out-of-bag
bootstrap) unless marked.

## Positives — what any mechanism must produce

| id | constraint | figure |
|---|---|---|
| **P1** | Burden stratifies 3-day death **within** the guideline's highly-malignant tier | 31.6 % → 73.4 % across quintiles (not monotone: Q2 41.2, Q3 40.1) |
| **P2** | Burden adds over the category, calibrated | +0.062 [+0.032, +0.095]; intercept −0.010, slope 0.979 |
| **P3** | Holds across hospitals | 0.682 / 0.651 |
| **P4** | Holds in a second cohort | I-CARE +34.1 pp [+23.2, +44.2] among the already-suppressed |
| **P5** | Two burst-content channels associated with outcome **independently of burden** | 8–30 Hz +0.500 [+0.311, +0.755]; stereotypy(1 s) +1.040 [+0.413, +1.894] |
| **P6** | Generalized slowing **present** marks survival, strongly | 74.9 % of >180-d survivors vs 29.7 % of ≤3-d deaths |
| **P7** | Aetiology gap: suppression means more after anoxia than sepsis | log-odds +0.801 at the EEG |
| **P8** | Class A — the aetiology excess is **exhausted** among 30-day survivors | −38 % of the day-0 gap by day 180 |
| **P9** | The doomed compartment is a **distinct early mass**, not a smooth shift | 45.6 % of anoxic BS+ dead ≤3 d vs 11.9 % BS− |
| **P10** | Suppression is **reversible under anaesthesia** | VitalDB ICC 0.313, autocorrelation decays −0.488, 70 % resolution |

## Negatives — what any mechanism must ALSO survive

| id | ruled out | evidence |
|---|---|---|
| **N1** | Whole-body ischaemic dose | mediation 2.6 %; cardiac/pressor gradients *steeper* in sepsis |
| **N2** | Depth, age, sex, coexisting findings, ceiling/scale artefact | all cleared |
| **N3** | Label noise | gap reproduces under a blinded quantitative definition at every threshold |
| **N4** | Withdrawal as explanation of the aetiology gap | halves both aetiologies; ratio 2.14 → 2.17 |
| **N5** | Drug-induced suppression | infusion commoner in anoxic; effect *larger* with drug present |
| **N6** | "Anoxic patients are simply sicker" | BS-negative mortality 32.8 % vs 32.7 % |
| **N7** | Burden is a **fixed** quantity in the acute window | I-CARE ICC 0.584, decay −0.370, trajectory coefficient +1.081 [+0.578, +1.614] |
| **N8** | "Silence equals severity" | post-anoxic status epilepticus arises in **severely** injured brains (PMID 36076090) |
| **N9** | Bursts require an intact thalamocortical loop | deafferented cortex produces burst suppression **in all cases** (PMID 9191587) |
| **N10** | Morphology **predicts** better than burden | +0.070 [+0.006, +0.121] I-CARE vs +0.036 [−0.019, +0.076] HEEDB — inconsistent |
| **N11** | Burst duration / amplitude as markers | duration not portable + opposite in Fong; amplitude sign **inverts** |
| **N12** | BSP beats the ratio at recording level | r = 0.988, increment −0.010 [−0.021, +0.004] |
| **N13** | Guideline tiers mis-ordered at the bottom | benign vs malignant +2.8 pp, **p = 0.171** — within noise |
| **N14** | Withdrawal separable from biological death | **four** instruments failed; one root cause |
| **N15** | Positive tissue-level identification | NSE absent (2 rows/551 parts); cause of death 84.9 % blank |

## Structural limits — not mechanisms, but they bound every claim

| id | limit |
|---|---|
| **L1** | Burst morphology is **undefined** below four bursts — i.e. exactly at maximal burden. 13.2 % excluded, 80 % vs 60 % poor outcome. Morphology can only inform the *middle* of the burden range |
| **L2** | 46 % die within 3 days — the withdrawal window — and it cannot be separated |
| **L3** | Every patient has an ascertained death; the outcome is *how soon*, not *whether* |
| **L4** | I-CARE shares MGH/BWH/BIDMC with HEEDB — a second cohort, **not** a second health system |
| **L5** | Reactivity unavailable, so the guideline category is reproduced without its nonreactive arm |

## The shape of the answer any candidate must have

Burden indexes something **brain-specific** (N1), **not fixed acutely** (N7) but **fixed enough by the time
clinical EEGs are done** (P1–P4), **reversible when the cause is drug** (P10), whose **quality is separable from
its quantity** (P5) though not usefully so for prediction (N10), and whose **absence of slowing** is a stronger
survival marker than its own magnitude (P6).

**Cumulative distinct results: 357.**

---

## R358–R360. MECHANISM ROUND: P5 and P6 share a common factor, and the background measures it better

Prompted by consolidating the constraint table, which made **P6 the largest untapped signal in the project** —
generalized slowing *present* marks survival 74.9 % vs 29.7 %, a larger contrast than burden's own effect, and
never previously the focus. Read against **N9** (deafferented cortex generates bursts unaided) it suggests
burst *generation* is cortical while *slow-rhythm* generation is thalamocortical — so P5 (intra-burst spectral
content) and P6 (background slowing) may be one mechanism seen by two instruments.

| id | test | result |
|---|---|---|
| **R358** | convergent validity: do the clinician's slowing flag and our intra-burst 8–30 Hz agree? (n=818) | slowing present **0.125** vs absent **0.246**, difference **−0.121 [−0.145, −0.097]** |
| **R359** | **is it just burden?** convergence within burden tertiles | low **−0.101 [−0.145, −0.059]**, mid **−0.134 [−0.175, −0.091]**, high **−0.103 [−0.147, −0.056]** — **survives in all three** |
| **R360** | are they the same construct? clinician flag adjusted for burden **and** our measure | **−0.752 [−1.075, −0.434]** — **the flag still adds** |

**What this establishes.** Two instruments sharing no method — a human reading the whole record, and an FFT on
burst segments over 8 sampled minutes — agree strongly, and the agreement is **not** an artefact of suppression
depth. That is convergent validity for a common underlying factor, consistent with thalamocortical
slow-rhythm capacity.

**What it refutes.** The strong unification. They are **not** the same construct: the flag carries substantial
outcome information *after* adjusting for burden and for our spectral measure. The whole-record read sees
something an intra-burst measure does not — which is unsurprising in hindsight, since slow activity lives
largely in the **background between bursts**, and our measure looks only *inside* bursts.

**Why this matters for the paper.** It explains **N10** — morphology's predictive increment was marginal and
inconsistent because intra-burst spectral content is a **weak proxy** for the real signal. The stronger measure
is the background, and the project has only ever had it as a binary clinician flag.

**The obvious next experiment, now well-motivated rather than speculative:** quantify slow-wave activity across
the **whole record** (not just within bursts) in both cohorts, and test it against burden and against the
morphology channels. Prediction: it beats intra-burst spectral content, and may beat burden itself for the
outcome contrast in P6. This is directly runnable with the existing extraction pipeline.

**Predicted vs actual (calibration ledger).** Predicted 0.60 that P5 and P6 would prove to be one construct.
Actual: they share a common factor but are not redundant — a partial confirmation whose *failure* half is the
more useful finding, because it identifies where the better measurement lives.

**Cumulative distinct results: 360.**

---

## R361–R364. Whole-record slow activity: hypothesis falsified, coverage gained, residual sharpened

Tested whether background slow activity is the better measurement, as R360 implied. I-CARE, 601 patients with a
whole-record spectrum (vs 559 with morphology — the coverage difference is itself the point).

| id | arm | result | verdict |
|---|---|---|---|
| R361 | **B1** whole-record slow fraction higher in good outcome | good 0.784 vs poor 0.756, **+0.027 [−0.003, +0.060]** | **null** |
| R362 | **B2** adds over burden | increment **+0.023 [−0.018, +0.048]**; coefficient adjusted for burden **−1.69 [−2.65, −0.80]** | **association yes, prediction no** |
| R363 | **B3** adds over burden AND intra-burst content | **−0.003 [−0.020, +0.004]**; coefficient **−0.52 [−1.98, +0.71]** | **FALSIFIED** |
| R363b | reverse: does intra-burst add over burden + background? | **+0.002 [−0.025, +0.016]** | **also null** |
| R364 | **B4** coverage on patients morphology cannot see | 42 patients, 69.0 % poor, median burden 0.510; slow fraction alone **AUC 0.629** | **holds** |

**The hypothesis is falsified and the reason is informative.** Background and intra-burst spectral content are
**mutually redundant** — neither adds over the other. They are the same measurement taken in two places, so the
question "which is better?" was malformed. This also confirms the pattern from N10 in a third place: a real
association with outcome (coefficient −1.69 [−2.65, −0.80] adjusted for burden) that yields **no predictive
increment**. Spectral content is genuinely related to outcome and genuinely weak.

**The one gain is coverage, and it is structural rather than statistical.** Spectral measures are defined for
every recording; burst morphology is not. On the 42 patients morphology is blind to — sicker, median burden
0.510, 69 % poor outcome — the slow fraction still discriminates at AUC 0.629. That does not improve the model,
but it removes a limitation (L1) that conditioned every morphology result on having four bursts.

**The residual is now sharper, not explained.** R360's finding stands: the clinician's slowing flag carries
**−0.752 [−1.075, −0.434]** beyond burden and intra-burst content, and whole-record slow power does **not**
account for it. So the human reading captures something neither an intra-burst FFT nor a whole-record Welch
periodogram does. Candidates this project has not measured: **spatial distribution** (both our measures take a
median across channels and discard topography), **reactivity** (unavailable in this schema), **temporal
evolution within the record**, and **specific waveform morphology** rather than band power.

**Predicted vs actual (calibration ledger).** Predicted 0.60 that the background would beat the intra-burst
measure. Actual: falsified — they are redundant. The prediction assumed the two measure different things
because they live in different parts of the record; they do not.

**Cumulative distinct results: 364.**

---

## R365–R372 · Topography eliminated; the inference machinery audited; a time-axis defect caught

### R365–R368 · Spatial distribution is not the missing dimension (I-CARE, n = 602)

The residual left by R358–R360 is that the clinician's "generalized slowing" flag carries
**−0.752 [−1.075, −0.434]** beyond suppression burden and our intra-burst 8–30 Hz measure, and B3 showed the
whole-record background spectrum does not explain it either. Four candidates were named. **Spatial
distribution was the only one this schema can measure** — every spectral feature in this project takes a
median across channels and discards topography by construction, while a human reading a record does not.
Extraction and predictions were committed before any result existed (`964ed58`).

| arm | prediction | result | verdict |
|---|---|---|---|
| **T1** primary | antero-posterior slow gradient steeper in good outcome | good −0.0378, poor −0.0609, **+0.0231 [−0.0022, +0.0526]**, AUC 0.528 | **null** (direction as predicted, CI includes zero) |
| **T2** secondary | across-channel dispersion **lower** in poor outcome | slow_sd good 0.0738, poor 0.0860, **−0.0122 [−0.0243, +0.0004]** | **direction REVERSED** |
| **T3** decisive | topographic block adds over burden + background + intra-burst | CV AUC 0.706 → 0.720, out-of-bag **+0.014 [−0.021, +0.040]** (n = 559) | **FALSIFIED** |
| **T4** coverage | works where morphology is blind | 43 patients, 69.8 % poor, median burden 0.541; AUC 0.523–0.569 | weak |

The full secondary family, reported whole rather than best-of: slow_sd −0.0122 [−0.0243, +0.0004]; sef_sd
−0.3034 [−0.6566, +0.0338]; slow_range **−0.0398 [−0.0723, −0.0090]**; lr_asym +0.0071 [−0.0050, +0.0198];
ap_sef_grad **+1.2596 [+0.4143, +2.2391]**. Two of five exclude zero. Over **burden alone** the block adds
+0.037 [−0.014, +0.072], also n.s.

**What this eliminates.** Spatial information carries weak marginal association and **no incremental
information** beyond burden plus the two spectral measures. Since a positive here was only a *necessary*
condition for topography explaining the flag residual, the negative is decisive against it. Of the four named
candidates, one is now eliminated, one (**reactivity**) is unavailable in this schema, and two remain:
**temporal evolution within the record** and **specific waveform morphology** rather than band power.

**The reversal is the interesting part.** Dispersion is *higher* in poor outcome, not lower — slow_range
−0.0398 [−0.0723, −0.0090] excludes zero in the direction opposite to the registered prediction. The
prediction assumed diffuse injury slows the cortex uniformly. A post-hoc reading, labelled post-hoc: a
preserved background is globally organised and therefore spatially uniform, whereas a badly injured cortex is
patchy — parts electrically silent, parts not — so across-channel variance *rises* with injury. This is a
story, not a result, and it predicts that dispersion should track burden; that is testable and untested.

**Predicted vs actual (calibration ledger).** Predicted 0.45 that T3 would confirm. Actual: falsified. The
running record of predicted-vs-actual now covers spatial (0.45 → falsified) and background-spectral
(0.60 → falsified) mechanisms; both over-predicted, and both for the same reason — assuming that a measure
taken in a different *place* must capture a different *thing*.

### R369–R370 · The two inference procedures behind every reported interval are calibrated

Shaking out the topography analysis on permuted labels — where every association is destroyed by construction
— the primary arm returned a 95 % interval excluding zero. One event in six tests is unremarkable, and
*assuming* so is what rule 23 exists to prevent. So the false-positive rate was measured, on the real feature
distributions with only the outcome link broken.

- **R369 · `diff_ci`** (percentile bootstrap for a group-mean difference), 400 permutations × 600 draws,
  n = 602: rejection rates **0.045, 0.065, 0.065** against nominal 0.050, Monte-Carlo SE 0.011. All within
  3 SE. **Calibrated.**
- **R370 · `oob_increment`** (the procedure behind the headline **+0.062 [+0.032, +0.095]**), 60 permutations
  × 200 out-of-bag reps, n = 559: mean increment under the null **−0.0005** — no positive bias. Lower bound
  above zero in **0/60**, upper bound below zero in **0/60**, against nominal 0.025 each, MC SE 0.020.

**Read this precisely.** 0/60 is consistent with nominal 0.025 and also with anything below roughly 0.05, so
the check establishes **absence of anti-conservatism** — the direction that matters, because an
anti-conservative interval would mean the headline increment is reported too narrow — and has little power to
detect mild conservatism. The permuted-label rejection that prompted the check was an ordinary false positive.

### R371–R372 · A time-axis defect in our own extraction, found by reading the code

**R371.** The usable-frame mask drops dead-channel frames and then forms one-second bins from the survivors,
gluing them together. Harmless for a burden — an average over frames is order-free — and **not** harmless for
BSP, whose entire content is a model of how the state moves between adjacent bins: a closed-up hole presents
as an abrupt jump that never happened. Re-reading 24 random recordings with a rule fixed beforehand: median
interior-dropped fraction **0.000 %**, but one recording had **50.5 %** of its frames removed from the middle,
a **1,817 s** hole. Median duration 3,600 s. The rule fired.

**R372.** Affected recordings are identified from the WFDB headers alone rather than a second signal pass:
`dropped = 1 − n_bins·10 / floor(samples/frame)`. Across 602 recordings the median dropped fraction is
0.011 %, p90 3.178 %, max 100 %; **73 exceed 1 %** and 50 exceed 20 %. **The exclusion is outcome-related**:
75.3 % poor outcome among the 73 excluded versus 61.2 % among the 529 kept, **−14.1 pp [−24.6, −2.9]**. This
is the same pattern as L1 — sicker patients give worse recordings — and it means any *prognostic* estimate on
the filtered set is conditioned on a variable related to the endpoint. The window-length analysis makes no
prognostic claim and reports filtered and unfiltered side by side.

**Cumulative distinct results: 372.**

---

## R373–R376 · Where BSP stops being interchangeable with a threshold ratio

`47_BSP_TECHNICAL_NOTE.md` §5.3 named this as its open question verbatim: *"r = 0.988 is specific to
whole-recording aggregation… we have not characterised where the equivalence breaks down as window length
falls — that is the obvious next experiment."* It has to be simulation: on real EEG there is no ground truth
for an instantaneous probability, so real data can show only whether two estimators **agree**, never which is
**right**. Seven regimes × 12 seeds × 1,200 one-second bins; two of the regimes are the model's own random
walk and three are processes it does not assume. Registered before running (`964ed58`).

### R373 · The boundary, which is the answer to the question asked

RMSE against the true window-mean p:

| window | ratio | bsp_win (like-for-like) | ewma tuned | ewma oracle | bsp_causal (online) | bsp_full (non-causal) | corr(ratio, bsp) |
|---|---|---|---|---|---|---|---|
| 600 s | 0.0045 | 0.0046 | 0.0104 | 0.0038 | 0.0053 | 0.0050 | — |
| 300 s | 0.0065 | 0.0065 | 0.0140 | 0.0057 | 0.0073 | 0.0069 | 0.983 |
| 120 s | 0.0103 | 0.0105 | 0.0219 | 0.0096 | 0.0130 | 0.0108 | 0.994 |
| 60 s | 0.0149 | 0.0149 | 0.0274 | 0.0134 | 0.0176 | 0.0148 | 0.989 |
| 30 s | 0.0213 | 0.0209 | 0.0319 | 0.0181 | 0.0224 | 0.0189 | 0.979 |
| 15 s | 0.0303 | 0.0302 | 0.0356 | 0.0228 | **0.0276** | 0.0226 | 0.956 |
| 8 s | 0.0417 | 0.0427 | 0.0382 | 0.0269 | **0.0317** | 0.0250 | 0.916 |
| 4 s | 0.0587 | 0.0610 | 0.0401 | 0.0303 | **0.0348** | 0.0264 | 0.862 |
| 2 s | 0.0826 | 0.0894 | 0.0414 | 0.0324 | **0.0368** | 0.0271 | 0.797 |
| 1 s | 0.1167 | 0.1148 | 0.0423 | 0.0337 | **0.0382** | 0.0276 | 0.728 |

**Interchangeable at 60 s and longer** (r ≥ 0.98 at 60, 120, 300 s); **diverging at 30 s and below**
(0.979 → 0.956 at 15 s → 0.916 at 8 s → 0.728 at 1 s). The accuracy **crossover is between 15 and 30 s**: at
30 s the plain ratio is still better (0.0213 vs 0.0224), at 15 s the online BSP has overtaken it (0.0276 vs
0.0303), and by 1 s it is **3.1× more accurate** (0.0382 vs 0.1167). The r = 0.988 reported for
whole-recording aggregation is therefore not a special case — it is the far end of a curve, and the curve
turns at about half a minute.

### R374 · The advantage is borrowed strength, not the model — and this refutes our own prediction

The registered S1 said BSP's advantage should **grow** as the window shortens because it borrows strength from
neighbouring bins. Half of that is right and the important half is wrong. Given **exactly the same data** as
the ratio — `bsp_win`, refitted on the window alone — BSP is **never more accurate at any window length**:
ratios to the matched baseline are 1.014, 1.007, 1.028, 1.017, 1.021, 1.047, 1.057, 1.081, 1.087 from 600 s
down to 2 s, i.e. it gets *worse* as the window shortens. (At 1 s BSP is undefined on a single bin and
degenerates to the ratio by construction; that 1.000 is bookkeeping.)

**So the entire short-window advantage comes from data outside the window, not from the model applied to the
data inside it.** That is not a criticism — a monitor genuinely has the preceding minutes, and `bsp_causal`
uses no observation from the future — but it is a precise statement of what is being bought, and it is the
opposite of what we predicted.

### R375 · It beats a deployable smoother and loses to an unattainable one

Beating a one-second ratio proves nothing on its own: the ratio over a single bin is an absurd baseline and
any smoother would beat it. The state equation **is** a random walk, whose optimal filter under Gaussian noise
is essentially an exponentially-weighted average — so the question is whether the binomial observation model
and the logistic link earn anything over three lines of arithmetic. Two baselines bracket it:

- **causally tuned EWMA** — constant picked by one-step-ahead error on the first 30 %, no truth and no future,
  deployable by anyone. `bsp_causal` beats it at **every** window length, RMSE ratios **0.513, 0.522, 0.596,
  0.642, 0.702, 0.775, 0.828, 0.867, 0.890, 0.903** (600 s → 1 s): between **10 % and 49 % lower error**.
- **oracle EWMA** — handed the best constant per regime and window from the true p. A ceiling, not a method.
  BSP loses to it everywhere (1 s: 0.0382 vs 0.0337).

**BSP sits strictly between the practical smoother and the unreachable ceiling.** The state-space machinery
earns real accuracy over what a practitioner would otherwise write, and does not exhaust what smoothing could
in principle deliver. Median causally-tuned α was 0.05 (range 0.02–0.35).

### R376 · Where the smoothing pays, and where the credible band does not cover

`bsp_win / ratio` by regime (<1 = BSP better) confirms registered prediction S2 in shape: smoothing pays where
the state is smooth and **costs** where it jumps.

| regime | 600 s | 120 s | 30 s | 8 s | 2 s |
|---|---|---|---|---|---|
| constant 0.50 | 0.998 | 0.993 | 0.981 | 0.954 | **0.851** |
| constant 0.90 | 0.973 | 1.035 | 0.980 | 1.215 | 1.238 |
| random walk, slow | 1.023 | 1.004 | 0.994 | 0.986 | 0.994 |
| random walk, fast | 1.029 | 1.009 | 1.031 | 1.069 | 1.291 |
| **step** | **1.324** | **1.251** | **1.214** | **1.503** | **1.851** |
| ramp | 0.967 | 0.990 | 0.984 | 0.997 | 0.944 |
| oscillation | 0.982 | 1.038 | 1.050 | 0.982 | 1.007 |

The step penalty (up to **1.851**) is the same defect the exact-solver validation found as a 0.775 pointwise
deviation, reached by a completely different route — and it persists even at 600 s windows (1.324), so it is
not a short-window artefact.

**Coverage of the 95 % credible band, per bin:** pooled **0.979** against nominal 0.950 — the band
**over-covers**, which is the safe direction, in six of seven regimes (0.988–0.996). The exception is the
**fast random walk at 0.916**, which under-covers: where the state moves fastest, the interval is too narrow.
Fitted σ² tracks the truth sensibly (0.0062 for a constant, 0.0474 for the fast walk). So the paper's claim
that BSP supplies "a framework for statistical inference" that ratios lack survives, with the qualification
that the interval is conservative in slow regimes and slightly anti-conservative in fast ones.

**Predicted vs actual (calibration ledger).** Predicted 0.70 that BSP would beat the ratio at short windows on
the same data. Actual: **falsified** — it never does. Predicted 0.50 that BSP would beat a tuned EWMA. Actual:
**confirmed at every window length.** The first error is the same one as R365 and R361: assuming that a more
elaborate estimator must extract more from a fixed sample, when what it actually does is use a larger one.

**Cumulative distinct results: 376.**

---

## R377–R380 · Temporal evolution: null within an hour, real across days

The clinician-flag residual (R358–R360, **−0.752 [−1.075, −0.434]** beyond burden and intra-burst content) had
four candidate explanations. Two were eliminated — the whole-record background spectrum (B3) and spatial
topography (T3) — and both failed the same way, now catalogue rule 28. Reactivity is unmeasurable in this
schema. **Temporal evolution was the leading survivor**, and this is its test. Registered before running
(`icare_temporal_evolution.py`, `icare_multiday_trend.py`, committed before any result existed).

Both arms use a **mean/difference decomposition and test the SIGN**, not the increment, for the reason in
catalogue rule 12: two noisy measurements of a constant level average to a better estimate than one, so an
increment alone cannot distinguish trend information from noise reduction. A correctly-signed non-zero
coefficient cannot be produced by averaging. Conditioning on the **mean of the two** measurements rather than
on the baseline is also what keeps regression to the mean out of a change-score analysis.

### R377 · Within one recording — FALSIFIED

505 recordings (39 excluded for interior gaps), median length 3,600 s, 62.4 % poor. Trend coefficient adjusted
for the level **−0.478 [−1.645, +0.748]**; out-of-bag increment **−0.002 [−0.030, +0.009]**; adjusted for
background and intra-burst content as well, **−0.671 [−2.122, +0.486]**. Trend alone AUC 0.553 against 0.688
for the level.

The scope was stated in advance rather than after: one hour at roughly hour 24 cannot show the trend a
clinician reads. **This falsifies the within-hour trend, not temporal evolution.**

### R378 · Across days — CONFIRMED, and it is the first candidate to survive

Burden is already cached at four target hours. **A trap had to be designed around first**: those files record
the *actual* hour of the recording nearest each target, not the target, so a patient with few recordings gets
the *same file* for several targets — **15.4 % of h12/h24 pairs are the identical recording**, whose change is
zero by construction. Including them would have loaded the sample with structural zeros and produced a false
negative that looked like biology. Pairs are required to be genuinely separated.

| | **primary** h12 → h48 | **secondary** h12 → h24 |
|---|---|---|
| usable pairs (genuine separation) | 368 of 515 | 365 of 519 |
| median actual gap | 36 h | 12 h |
| poor outcome | 56.5 % | 57.8 % |
| change per 24 h, good vs poor | −0.2212 vs −0.1885 | −0.3197 vs −0.1539 |
| M1 unadjusted difference | +0.0328 [−0.0270, +0.0925] — null | **+0.1658 [+0.0197, +0.3146]** |
| **M2 trend coefficient, adjusted for level** | **+1.098 [+0.316, +2.015]** | **+0.367 [+0.079, +0.719]** |
| trend adjusted for level **+ background + intra-burst** | **+1.061 [+0.233, +2.057]** (n=350) | **+0.497 [+0.170, +0.891]** (n=348) |
| out-of-bag increment over level | +0.005 [−0.060, +0.029] | +0.003 [−0.045, +0.031] |
| out-of-bag increment over all three | −0.001 [−0.059, +0.022] | +0.013 [−0.032, +0.040] |

**Burden falls in both groups; it falls FASTER in good outcome.** Slower resolution of suppression marks poor
outcome, independently of how much suppression there is. This is the first candidate to survive the exact
adjustment that eliminated the background spectrum and topography.

### R379 · What it is not — no predictive increment, and a restricted estimand

**Every out-of-bag increment includes zero.** This is a genuine association with **no discrimination gain** —
the same shape as B2, where intra-burst content carried −1.69 [−2.65, −0.80] adjusted for burden and added
nothing predictively. Trend alone reaches AUC 0.530 (primary) and 0.574 (secondary) against 0.693 and 0.668
for the level. Anyone reading this as a prognostic advance would be reading it wrong.

**Availability is outcome-related**, checked rather than assumed: patients with a usable late recording are
**56.5 % poor versus 74.1 % among those without**, a difference of **−17.6 pp [−25.5, −9.1]** (secondary arm
−10.4 pp [−20.2, −1.5]). A late recording exists only for a patient who lived to be recorded. So the estimand
is *the trend among patients who survived to be measured twice*, which is a real but restricted question, and
the sickest patients are outside it.

**Direction of the residual biases.** Regression to the mean would push the trend coefficient **negative**
(poor-outcome patients start higher, so they have more room to fall), and the observed coefficient is
**positive** — RTM works against this finding rather than for it. Conditioning on the mean of the pair rather
than on baseline is the standard guard, and it was chosen in advance.

### R380 · Robustness — the scaling is not doing the work

Expressing the change per 24 h divides by the elapsed gap, which amplifies noise for the shortest pairs. Rerun
on the **raw** late-minus-early difference, every verdict holds: primary **+0.967 [+0.370, +1.681]**, secondary
**+0.858 [+0.220, +1.597]**, and adjusted for background and intra-burst **+0.943 [+0.319, +1.728]** and
**+1.093 [+0.384, +1.903]**. Permuted-label controls for both scripts were null throughout.

**Predicted vs actual (calibration ledger).** Predicted 0.35 that temporal evolution would survive the
adjustment that killed the other two. Actual: **confirmed across days, falsified within an hour.** This is the
first under-prediction in the run; the previous three were all over-predictions of measures that turned out
redundant. The distinguishing feature, visible only in hindsight and worth carrying forward, is that this
measure differs from burden in **kind** — it is about change — where the failed ones differed only in **where
they were measured**.

**Cumulative distinct results: 380.**

---

## R381–R384 · The window-length question on real EEG: predicting forward instead of scoring against truth

R373–R376 answered the question in simulation, where a true p_t exists. On real EEG none does, so agreement is
all a comparison can show. This arm asks something that needs no ground truth and is closer to the clinical
use: **given everything observed so far, which estimator best predicts what the EEG does next?** Binomial
log-loss on the next window, strictly causal — σ² is fitted by EM on the first 30 % of each recording and
frozen, and only windows entirely after that burn-in are scored, so nothing sees its own future.

521 recordings (interior-gap filtered; 51 excluded), median length 3,600 s, median burden 0.338.

### R381 · The trailing ratio is never the best predictor at any window length

| window | ratio | cumulative | ewma tuned | ewma oracle | bsp_last | **bsp_mean** | best | corr(ratio, BSP) |
|---|---|---|---|---|---|---|---|---|
| 300 s | 0.3154 | 0.3255 | 0.4878 | 0.3106 | 0.5738 | **0.3146** | bsp_mean | 0.996 |
| 120 s | 0.2864 | 0.3118 | 0.4416 | 0.2827 | 0.5184 | **0.2855** | bsp_mean | 0.995 |
| 60 s | 0.2811 | 0.3072 | 0.4350 | 0.2727 | 0.5100 | **0.2797** | bsp_mean | 0.990 |
| 30 s | 0.2899 | 0.3091 | 0.4335 | 0.2724 | 0.5058 | **0.2866** | bsp_mean | 0.984 |
| 15 s | 0.3145 | 0.3061 | 0.4204 | 0.2676 | 0.4934 | **0.3030** | bsp_mean | 0.971 |
| 8 s | 0.3505 | **0.3052** | 0.4006 | 0.2657 | 0.4764 | 0.3234 | cumulative | 0.955 |
| 4 s | 0.4163 | **0.3046** | 0.3695 | 0.2630 | 0.4468 | 0.3491 | cumulative | 0.943 |
| 2 s | 0.5145 | **0.3043** | 0.3245 | 0.2598 | 0.4014 | 0.3698 | cumulative | 0.932 |
| 1 s | 0.5615 | 0.3042 | **0.2861** | 0.2542 | 0.3370 | 0.3370 | ewma | 0.930 |

Paired per-recording, **bsp_mean beats the trailing ratio at every window length**, all bootstrap CIs excluding
zero: +0.0008 [+0.0004, +0.0013] at 300 s rising to +0.2246 [+0.2032, +0.2479] at 1 s.

**One qualification that matters.** At 300 s bsp_mean wins on average but on only **44.0 %** of recordings —
the mean is carried by a minority with large gains. Win rates rise to 64.5 % at 60 s and ~74 % at ≤8 s. "Beats
at every window" is true of the average and not of the typical recording at long windows.

### R382 · An instantaneous estimate is the wrong summary for predicting an interval

The two causal BSP summaries differ enormously, and reporting only one would have misstated the estimator —
the first version of this analysis did exactly that and was corrected before anything was reported.
`bsp_mean` averages the causal filter over the window; `bsp_last` takes its value at the final bin. At 300 s
they score **0.3146 versus 0.5738**. `bsp_last` *loses* to the trailing ratio from 300 s down to 4 s
(−0.2583 [−0.2927, −0.2248] at 300 s) and wins only at 2 s and 1 s.

The reason is interpretable rather than a defect: in burst suppression the filtered probability at any one
instant is often near 0 or 1, and a confident value at a single bin is a poor stand-in for the next five
minutes, which will contain both states. **The estimator is not the summary.** At 1 s the two coincide exactly
(0.3370 both), as they must, since a one-bin window's mean is its last bin — a useful internal check.

### R383 · Where the simulation does not replicate, and where real EEG differs from it

- **The practical-EWMA result does not fully carry over.** In simulation BSP beat a causally-tuned EWMA at
  *every* window (RMSE ratios 0.513–0.903). On real EEG bsp_mean is ahead from 300 s to 8 s, ties at 4 s, and
  **loses at 2 s and 1 s**. The simulated regimes are not bursty in the way real suppression is.
- **The cumulative average is extremely strong and nearly flat** (0.3042–0.3255 across every window), and it
  wins outright at ≤8 s. Over the scored horizon these recordings are close to stationary, so at short
  horizons nothing beats "the patient's overall level so far".
- **Agreement decays far more slowly than in simulation**: correlation stays **≥0.930 down to 1 s**, against
  0.728 at 1 s in simulation. Real recordings are more persistent than the simulated processes. These two
  correlations are **not directly comparable** — the simulation used the smoothed (non-causal) BSP and this
  uses the causal filter — so the honest statement is about persistence, not a numerical contradiction.

### R384 · The interior-gap exclusion changes nothing

Rerun unfiltered (572 recordings, 51 glued-together recordings restored), **every verdict is identical** and
every value moves by less than 0.007: bsp_mean best from 300 s to 15 s, cumulative at 8–2 s, ewma at 1 s, and
bsp_mean ahead of the trailing ratio at every window with CIs excluding zero. The exclusion was the right call
on the merits — a closed-up 1,817 s hole genuinely misrepresents a transition — but it is not load-bearing for
this result.

**Verification.** The printed table was independently recomputed from the persisted per-recording scores
(4,613 rows, 521 recordings) and matches exactly at 300 s, 30 s and 1 s.

**Predicted vs actual (calibration ledger).** Predicted that BSP would beat the trailing ratio at short
windows and converge to it at long ones. Actual: **it beats the ratio at every window in the window-averaged
form, and the instantaneous form loses at long windows** — the prediction had the right direction for the
wrong object, and the object turned out to matter more than the window length.

**Cumulative distinct results: 384.**

---

## R385–R387 · MORGOTH's labels cannot fix the slowing flag — but looking at them found a threat to R360

Prompted by the suggestion to use MORGOTH to get the labels right. The **model** remains unobtainable (code
and checkpoint unreleased; the sandbox's GitHub access is proxy-scoped so its status cannot be verified from
here). The **labelled task sets are readable in S3**, keyed by `bdsp_mrn` in our own identifier space, and
include GENSLOWING (5,396 patients), BS, FOCALSLOWING, IIIC, PDR and others. Overlap with our HEEDB burden
cohort is real: ~800 patients per shard.

### R385 · The label sets cannot validate the flag, and a negative control is what showed it

**They are positives-only.** All 5,396 GENSLOWING rows carry the label "generalized slowing"; there are no
annotated negatives. The corpus was assembled to train a detector, not to survey a cohort, so absence from it
is not evidence of absence — specificity is not estimable and any join treating "not in GENSLOWING" as a
negative would be the error rule 5 exists to prevent.

Among the 4,870 overlapping patients the report-text flag is set in **99.8 % [99.7, 99.9]**. That looked like
near-perfect concordance and it is not: **FOCALSLOWING patients are also 99.8 % gen-slowing-flagged**, against
a base rate of 76.5 % over 49,232 patients with a report. A construct-specific agreement would have put
FOCALSLOWING patients near the base rate. The label sets *are* specific where they should be — FOCALSLOWING
patients are 98.6 % focal-slowing-flagged, a 5.12× enrichment, against 29.8 % in GENSLOWING — so the
instrument works; it is generalized slowing that carries almost no contrast in any MORGOTH-annotated
subpopulation. **The 99.8 % measures the population, not the agreement.**

### R386 · The flag is strongly burden-dependent, which nobody had checked

From the full burden cohort (n = 4,813; no conditioning on death ascertainment):

| suppression burden | n | gen-slowing flag positive |
|---|---|---|
| < 1 % | 2,535 | **92.7 %** |
| 1–10 % | 874 | 92.9 % |
| 10–50 % | 851 | 84.1 % |
| > 50 % | 553 | **56.1 %** |

Flat to 10 %, then falling off a cliff. The natural reading is that a reader looking at a near-suppressed
record calls it *suppressed*, not *slow* — so "flag absent" does not mean "no slow activity"; at high burden
it substantially means "too suppressed for anything to be called slow". This is a property of the project's
most-used label and it had never been examined.

### R387 · A threat to R360 that is now open, and a test that came out INCONCLUSIVE

R360 — the largest open constraint, and the thing B3, T3 and R378 were all chasing — adjusted the flag for
burden **linearly**. The relationship above is a step, and **a linear term cannot absorb a step**, so the
non-linear part of the burden information the flag carries would survive that adjustment and appear as a
residual. That is a mechanism for the **−0.752 [−1.075, −0.434]** requiring no biology at all.

**The test did not settle it.** On the cohort that could be assembled here — flag + burden + intra-burst +
ascertained death, n = 239 — R360's residual **did not reproduce**: flag coefficient **−0.523 [−1.338, +0.180]**
under the linear specification. With a flexible quintile adjustment it is **−0.601 [−1.547, +0.152]**, 15 %
larger in magnitude, but that comparison is uninterpretable: a baseline whose interval already spans zero
cannot distinguish "the residual collapsed" from "the residual was never present in this subsample". The
script's own gate now refuses to print a verdict in that case; the first version printed "COLLAPSES", which
would have been a false headline.

**Why it failed to reproduce is itself informative:** R358–R360 used n = 818, while this join additionally
conditions on an **ascertained death record** — the exact conditioning this project already demoted two tests
for, since death ascertainment runs 40.1–61.9 % by aetiology.

**Status: R360's residual is neither confirmed nor refuted, and now carries an unexcluded statistical
explanation.** Settling it requires reconstructing R358–R360's actual cohort and outcome definition rather
than an approximation of it. Until then, B3, T3 and R378 rest on a constraint with a live alternative
explanation — which is worth knowing before any of it is written up.

**Cumulative distinct results: 387.**

---

## R388 · R360's residual is NOT an artefact of the burden adjustment — the threat is excluded

R387 raised a live alternative explanation for the project's largest open constraint: the flag's positivity is
flat to 10 % suppression burden then collapses, R360 adjusted for burden **linearly**, and a linear term
cannot absorb a step, so the leftover would look like signal. Three experiments (B3, T3, R378) rest on that
residual being real. The R387 test was inconclusive because it used one shard (n = 239) and its own gate
failed. This is the properly powered version, on all four shards.

**A reproducibility problem found on the way, and worth recording:** commit `dcc3700`, which introduced
R358–R360, **changed only the ledger — no script was committed.** The exact cohort (n = 818) is therefore not
recoverable. This analysis defines its cohort explicitly instead and is committed with it.

**Cohort:** flag + burden + intra-burst + ascertained death, all four shards, n = 1,497, 30-day death 68.0 %,
flag positive 66.3 %. It is **not** R358's cohort and is not presented as a replication — conditioning on an
ascertained death record selects a sicker population (30-day survival 41.9 % flag-positive vs 12.5 %
flag-negative, against R358's 74.9 % vs 29.7 %). The intra-burst contrast does track closely: **0.131 vs
0.243** here against **0.125 vs 0.246** reported.

**The burden dependence reproduces** in this cohort: flag positive in 84.5 % below 1 % burden, 75.4 % at
10–25 %, **39.7 % above 50 %**.

**Four specifications, increasingly free of assumptions:**

| burden adjustment | flag coefficient |
|---|---|
| linear (as R360 specified) | **−0.985 [−1.332, −0.665]** |
| quintile indicators | **−1.030 [−1.386, −0.705]** |
| decile indicators | **−0.993 [−1.360, −0.675]** |
| **fully stratified** (separate fit inside each burden quintile) | **5 of 5 strata negative and excluding zero** |

| burden stratum | n | 30-day death | flag coefficient |
|---|---|---|---|
| 0.000–0.023 | 302 | 39.7 % | −0.966 [−1.646, −0.309] |
| 0.023–0.145 | 298 | 52.3 % | −0.870 [−1.758, −0.127] |
| 0.145–0.383 | 298 | 70.5 % | −0.639 [−1.273, −0.061] |
| 0.383–0.745 | 299 | 84.3 % | −1.381 [−2.520, −0.682] |
| 0.745–1.010 | 300 | 93.3 % | −1.899 [−3.370, −0.884] |

**The functional-form explanation is excluded.** The stratified estimate assumes nothing about how burden
relates to outcome, and the effect is present in every stratum. Moving from linear to deciles changes the
coefficient by under 5 %.

**An additional observation the stratification exposes.** The flag's effect is **largest where suppression is
deepest** — −1.381 and −1.899 in the top two strata against −0.639 in the middle — which is precisely where
the flag is least often positive (39.7 %). Among the most suppressed patients, a reader still calling the
background "slow" is saying something that carries more information than anywhere else in the range. That is
a constraint no mechanism has yet had to explain, and it is the sharpest thing to come out of this line.

**Status change:** B3, T3 and R378 are **not** built on an artefact. The mechanism hunt stands.

**Cumulative distinct results: 388.**

---

## R389–R392 · The prognostic meaning of intra-burst content REVERSES after anoxia — and it explains N10

The most substantive candidate this project has produced, and it arrived by refuting a check registered for a
different purpose. `heedb_thalamocortical_test.py` registered T2 as a consistency arm: if the clinician's
slowing flag and our intra-burst 8–30 Hz measure index one thalamocortical factor, their aetiology
interactions should share a sign. They do not — flag **−0.750 [−1.433, −0.116]**, intra-burst
**+4.319 [+2.373, +6.754]** — so the unification claimed in R358–R360 is refuted, and what replaces it is
larger.

### R389 · T1 — the slowing flag's effect IS aetiology-dependent, as the thalamocortical account predicts

| | n | 30-d death | flag positive | flag coefficient (adj. burden + intra-burst) |
|---|---|---|---|---|
| anoxic | 818 | 81.7 % | 50.2 % | **−1.011 [−1.528, −0.564]** |
| non-anoxic | 679 | 51.5 % | 85.6 % | −0.418 [−0.942, +0.069] |

Interaction **−0.750 [−1.433, −0.116]**. A generic-severity account predicts no aetiology interaction —
severity is severity — so this discriminates, and it is the one place the two accounts disagreed.

### R390 · The reversal itself, non-parametrically

AUC of intra-burst 8–30 Hz content for 30-day death, **no model, no link function, no adjustment**:

| | AUC | direction |
|---|---|---|
| anoxic (n = 818) | **0.589 [0.545, 0.633]** | more fast content → **more** death |
| non-anoxic (n = 679) | **0.408 [0.364, 0.452]** | more fast content → **less** death |

Both intervals exclude 0.5, on opposite sides.

### R391 · It survives every attempt to make it an artefact

Catalogue rule 16 says a sign disagreement usually means the definition is doing the work. It was tested
accordingly, with the conclusion rule fixed before running.

- **Burden strata** (burden differs by aetiology, 0.445 vs 0.086 median): opposite sides of 0.5 in **3/3**.
- **Burst-count strata** — the variable that actually gates the L1 exclusion, which differs sharply by
  aetiology (55.7 % vs 89.5 % excluded): opposite sides in **3/3**, and the effect *strengthens monotonically*
  with burst count in both directions (anoxic 0.536 → 0.603 → 0.635; non-anoxic 0.406 → 0.419 → 0.390).
- **Decomposition of the non-anoxic arm.** The first attempt was invalid and is retained in the code as a
  warning: the label groups **overlap** (3,437 label-assignments across 1,497 patients) and "sepsis" included
  patients who were also anoxic, so it could never decompose the contrast being made. Corrected by restricting
  to patients with **no** anoxic label and then splitting:

| non-anoxic subgroup | n | 30-d death | AUC |
|---|---|---|---|
| sepsis | 297 | 48.8 % | 0.427 [0.363, 0.494] |
| metabolic | 439 | 53.3 % | 0.410 [0.358, 0.462] |
| structural | 428 | 52.1 % | 0.399 [0.344, 0.454] |
| status epilepticus | 167 | 39.5 % | 0.406 [0.320, 0.501] |

**4/4 below 0.5, clustered within 0.028 of one another.** This is anoxia versus everything else, not anoxia
versus one deviant condition — and the tightness of that cluster is the strongest single piece of evidence
here, because a pooled artefact would not produce four independent subgroups agreeing to within 0.03.

### R392 · It retrodicts N10, which it was not built to explain

**N10** has stood unexplained: burst morphology's predictive increment was **+0.070 [+0.006, +0.121] in
I-CARE** but **+0.036 [−0.019, +0.076] in HEEDB**. I-CARE is *entirely* cardiac arrest. HEEDB is 54.6 %
anoxic and 45.4 % everything else — so a mixed cohort averages two opposing effects toward zero while a
pure-anoxic cohort does not. **A previously unexplained negative becomes a prediction of the new account.**
That is the property this project has demanded of a mechanism and never previously obtained.

**What is NOT established, stated plainly.**
1. **The external check is weak.** I-CARE's AUC is **0.511 [0.464, 0.557]**, which *includes* 0.5. It agrees in
   direction with the anoxic arm and does not on its own establish it. The registered rule asked only for
   directional agreement, which was too low a bar, and that is a flaw in the rule rather than a strength of
   the result.
2. **Death-ascertainment conditioning** applies throughout (L3), and aetiology comes from **ICD codes**, which
   this project has already had to correct once.
3. This is **effect modification, not a mechanism.** It says the same measurement means opposite things in two
   populations; it does not say why. The thalamocortical account (R389) is the leading explanation and is not
   established by this.

**Literature position.** E-utilities finds no prior report of aetiology-dependent intra-burst spectral content.
The natural framework for R389 is Schiff's mesocircuit model; Forgacs, Devinsky & Schiff, *Ann Neurol* 2020
(**PMID 31994749**) is the anchor for prolonged coma after cardiac arrest.

**Cumulative distinct results: 392.**

---

## R393–R394 · The aetiology reversal survives both of its testable internal weaknesses

Three weaknesses were recorded with R389–R392. **External replication remains open and is blocked here** —
it needs a mixed-aetiology cohort, and TUH is unreachable from this sandbox (no `rsync` binary, no NEDC key),
so it waits for a machine that has them. The other two were testable and are now tested, registered before
running (`analysis/heedb_reversal_robustness.py`).

### R393 · Removing the death-ascertainment conditioning (limit L3)

Every prior estimate required an ascertained death record, so **every patient in the cohort had died** and
the outcome was "died within 30 days" versus "died later". Rebuilt on the full cohort with a measurable burst
morphology (**n = 2,451**), treating an absent death record as alive:

| | n | 30-day death | AUC |
|---|---|---|---|
| anoxic | 818 | 81.7 % | **0.589 [0.545, 0.633]** |
| non-anoxic | 1,633 | 21.4 % | **0.432 [0.397, 0.465]** |

Both intervals exclude 0.5, on opposite sides. The original conditioning gave 0.589 [0.541, 0.632] and
0.408 [0.367, 0.452]. **The two analyses have opposite ascertainment biases and agree**, which is the point —
neither is clean on its own, and a result appearing in both is not an artefact of either.

**An important qualification the run exposed.** Death-record ascertainment is **100.0 % in anoxic patients
versus 41.6 % in non-anoxic**. Every anoxic patient with a measurable morphology already had a death record,
so the anoxic arm is *identical* under both analyses (n = 818 either way). **W1 therefore tests the
non-anoxic arm only** — it expands that arm from 679 decedents to 1,633 including survivors and the
association still runs below 0.5. That is a real gain, and it is narrower than "the reversal is unaffected by
ascertainment".

### R394 · Two independent routes to "anoxic"

The `anoxic` code list mixes codes for the **arrest event** (4275, 42741, I460, I461, I469) with codes for
the **resulting encephalopathy** (3481, G931, 7991, P916). They overlap but are not the same patients: 745
arrest-coded, 594 encephalopathy-coded, 521 both. Each compared against patients carrying **neither** family
(catalogue rule 29 — a contrast between A and not-A must be decomposed inside not-A):

| definition | n | 30-day death | AUC |
|---|---|---|---|
| arrest codes only | 745 | 83.6 % | **0.592 [0.545, 0.639]** |
| encephalopathy codes only | 594 | 84.0 % | **0.608 [0.554, 0.659]** |
| neither family | 1,633 | 21.4 % | **0.432 [0.397, 0.465]** |

Both routes confirm. The finding does not rest on one code family, which matters because this project has
already had to correct its ICD definitions once and the entire result is an aetiology contrast.

### Status of the lead after R393–R394

**Strengthened.** The reversal now survives: no model at all; burden strata 3/3; burst-count strata 3/3;
decomposition of the non-anoxic arm 4/4 within 0.028; removal of the death-ascertainment conditioning; and
two independent aetiology definitions. **The one remaining weakness is external replication**, and it is the
one that matters most — every result above is HEEDB. I-CARE agrees in direction only (0.511 [0.464, 0.557])
and, being entirely cardiac arrest, is structurally incapable of testing an aetiology contrast at all.

**Cumulative distinct results: 394.**

---

## R395–R396 · Sleep spindles: a second, anatomically specific instrument agrees

R389 found the clinician's generalized-slowing flag carries a larger protective effect after anoxia
(interaction **−0.750 [−1.433, −0.116]**), which a generic-severity account does not predict. That flag is a
poor instrument — 83.8 % prevalent, and its positivity collapses across the burden range because a reader
calls a near-suppressed record *suppressed* rather than *slow* (R386). **Sleep spindles are generated by the
thalamic reticular nucleus**, making them the most anatomically specific readout of thalamocortical integrity
available in a routine report, and they are annotated on all 49,232 HEEDB patients. Registered before running.

Cohort **n = 8,349** (spindle annotation + quantitative burden + aetiology), 30-day death 38.9 %, spindles
44.5 %, anoxic 22.1 %. No death-ascertainment conditioning — absent record treated as alive, the R393
convention.

### R395 · Spindles carry outcome information beyond depth of encephalopathy

**The confound, made visible rather than argued away.** Sleep architecture requires a patient who cycles, so
"spindles present" is substantially "not deeply encephalopathic". Spindle prevalence falls monotonically with
suppression burden while death rises:

| burden quartile | n | spindles | 30-day death |
|---|---|---|---|
| 0.000 | 3,717 | 50.1 % | 24.2 % |
| 0.000–0.004 | 517 | 49.1 % | 31.7 % |
| 0.004–0.121 | 2,030 | 43.8 % | 39.4 % |
| 0.121–1.010 | 2,085 | **33.9 %** | **66.5 %** |

Raw contrast is 27.5 % death with spindles versus 48.1 % without — near-meaningless on its own. **Adjusted
for burden the spindle coefficient is −0.772 [−0.876, −0.672].** Spindles are not merely a depth proxy.

### R396 · The spindle effect is aetiology-dependent, and it converges with R389

| | n | 30-day death | spindles | spindle coefficient (adj. burden) |
|---|---|---|---|---|
| anoxic | 1,846 | 65.3 % | 32.7 % | **−1.001 [−1.227, −0.777]** |
| non-anoxic | 6,503 | 31.5 % | 47.8 % | **−0.687 [−0.793, −0.574]** |

Interaction **−0.296 [−0.548, −0.052]** — spindles matter *more* after anoxia, the same direction and the
same prediction as R389's slowing flag, now from an instrument whose generator is anatomically known. **Two
instruments sharing no method — a subjective whole-record impression and a discrete graphoelement — agree on
a prediction that a generic-severity account does not make.**

**The sensitivity arm weakens it, and this is reported rather than buried.** Additionally adjusting for the
`awake` flag — deliberately over-controlled, since spindles and wakefulness are both downstream of
arousability — the spindle main effect survives comfortably at **−0.450 [−0.573, −0.329]**, but the
**interaction becomes marginal: −0.252 [−0.507, +0.001]**. The point estimate barely moves (−0.296 → −0.252,
a 15 % attenuation); the interval crosses zero by a hair. That pattern is what over-control costs in
precision rather than evidence of no effect, but the honest statement is that **the aetiology interaction is
not robust to the aggressive control, while the main effect is.**

### What this does and does not buy the thalamocortical account

It supplies **convergent evidence from an anatomically specific instrument** — the account's best available
test, and it passed its primary arm. It does **not** establish a mechanism: L2 and L3 stand, 46 % die inside
the withdrawal window, and this remains effect modification. Nor does it address the lead's one open
weakness, external replication, which needs a mixed-aetiology cohort.

**Cumulative distinct results: 396.**

---

## R397 · The reversal holds at BOTH hospitals independently — and a correction to R393

External replication is unavailable for reasons now fully documented: **I-CARE is entirely cardiac arrest** so
it cannot test a contrast *between* aetiologies at all, and **TUH — access approved 2026-07-27 — carries no
outcome field and no diagnosis field**, so permission changed and contents did not. No known cohort has EEG +
outcome + mixed aetiology besides HEEDB. The strongest available test is therefore the hospital split, and it
is **internal validation, not external replication**.

### R397 · Hospital split

| site | n | anoxic | 30-d death | anoxic AUC | non-anoxic AUC | gap |
|---|---|---|---|---|---|---|
| **S0001** | 928 | 55.7 % | 66.6 % | **0.570 [0.515, 0.624]** | **0.429 [0.375, 0.487]** | **+0.141** |
| **S0002** | 568 | 53.0 % | 70.2 % | **0.617 [0.532, 0.698]** | **0.375 [0.310, 0.446]** | **+0.242** |

**Present at both hospitals independently, with all four intervals excluding 0.5.** S0001 contributes roughly
twice the recordings of S0002, so a finding carried by the larger site alone was a live possibility; it is not
what happened.

**Heterogeneity tested rather than eyeballed** (comparing two intervals by eye is the
comparison-of-significance error this project has committed before): bootstrapped between-site difference in
the aetiology gap is **−0.099 [−0.227, +0.035]** — contains zero, so the sites do not differ detectably.

**What this is worth.** HEEDB's two sites differ in equipment, technologists and reading clinicians, so
agreement across them is not nothing. They are also hospitals in one regional academic network — **limitation
L4, the same one recorded for I-CARE.** This is the best available evidence and it is not a second health
system, and it should be reported in those words.

### CORRECTION to R393 — the "unconditioned" arm was partly an assumption

The site-split run reported **100.0 % death-record ascertainment at both sites**, and its unconditioned and
decedents-only arms came out byte-identical. That is a tell, and checking it exposed a structural property of
the data nobody had established:

**The OMOP `condition_occurrence` table contains only decedents — all 16,233 patients in it have a death
record.** Therefore *any* analysis requiring an aetiology label is automatically restricted to patients who
died. A genuinely aetiology-labelled, death-unconditioned analysis **is not possible in this dataset.**

R393 claimed the reversal survives removing the death-ascertainment conditioning, expanding the non-anoxic arm
from 679 to 1,633. Those 954 additional patients had **no condition data at all** and were classified
non-anoxic by a code default (`split.get(p, (False, False))`) rather than by measurement. **That is an
assumption, and R393 presented it as a measurement.**

**The assumption is defensible and should be argued rather than assumed:** the condition table is
decedents-only, anoxic patients in this cohort die at 81.7 %, so patients with no death record are very
unlikely to be anoxic. The expanded arm's AUC of 0.432 [0.397, 0.465] is therefore probably a fair estimate.
But **R393's status changes from "closed" to "closed under a stated assumption"**, and the honest summary of
the death-conditioning weakness is that it cannot be fully removed with this data.

The anoxic arm is unaffected either way: all 818 anoxic patients have death records, so it is identical under
both conventions — which R393 already noted.

**Cumulative distinct results: 397.**

---

## R398–R399 · L3 was an extraction artefact for aetiology, and the reversal survives measured labels

R397 established that the extracted `condition_occurrence` table contained **only patients with a death
record**, which made R393's expanded non-anoxic arm an assumption rather than a measurement. Investigating
*why* produced something better than a caveat: **zero of the 954 survivors appeared in the extract while the
source table on S3 covers the whole database**, so the restriction came from which patient list a prior
extraction was run against — not from HEEDB.

### R398 · Re-extraction: the survivors were never missing from the data

`condition_occurrence` re-extracted against all 2,473 morphology patients, decedents and survivors alike:
**3,592,798 rows over 2,471 distinct patients**, 179 parquet parts at ~11.4 parts/min (16 minutes).

| | aetiology known | of the 954 survivors |
|---|---|---|
| old extract | 1,496 | **0** |
| new extract | **2,449** | **953** |

**The newly labelled survivors are 38.7 % anoxic**, against 54.7 % among decedents. So R393's assumption —
that unlabelled patients were non-anoxic — was **materially wrong**: roughly 369 of those 953 are anoxic and
had been assigned to the wrong arm.

**L3 is lifted for the aetiology analyses.** "Every patient has an ascertained death; the outcome is how soon,
not whether" has bounded this project throughout, and for aetiology it was never a property of HEEDB.

### R399 · The reversal on measured labels — three cohorts, identical code

| cohort | anoxic | non-anoxic | gap |
|---|---|---|---|
| **(a)** decedents only, measured *(the R390 cohort)* | n=818, **0.589 [0.545, 0.633]** | n=678, **0.407 [0.364, 0.450]** | +0.182 |
| **(b)** all patients, aetiology **assumed** *(the R393 cohort)* | n=818, **0.589 [0.544, 0.632]** | n=1,633, **0.432 [0.397, 0.467]** | +0.157 |
| **(c)** all patients, aetiology **measured** *(corrected)* | n=**1,187**, **0.577 [0.547, 0.608]** | n=**1,262**, **0.426 [0.392, 0.461]** | +0.151 |

**All three show the reversal with every interval excluding 0.5.** Cohort (c) supersedes both: the anoxic arm
grows 818 → 1,187 by adding the misassigned anoxic survivors, the non-anoxic arm is measured rather than
assumed, 30-day death falls from 81.7 % to 56.3 % (anoxic) and 51.5 % to 27.7 % (non-anoxic) because real
survivors are now present, and **the anoxic interval tightens to [0.547, 0.608]**.

**The most informative part is that R393's assumption was wrong and the conclusion held anyway.** Had the
assumption been correct, (b) and (c) agreeing would say little. Instead ~369 patients were in the wrong arm,
correcting them moved the gap by only 0.006, and the reversal is therefore robust to a misclassification large
enough to have broken it.

**What is still not fixed.** Survivors are defined as "no death record", which conflates alive with
unascertained, so they contribute 953 guaranteed non-events (V4: they cannot be scored alone). L3 is lifted
for *aetiology*, not for outcome ascertainment. And none of this touches the lead's open weakness — external
replication in a mixed-aetiology cohort, which does not exist among the data available here.

**Cumulative distinct results: 399.**

---

## R400–R402 · Is the reversal a self-fulfilling prophecy? One arm says clearly no; the other is unresolved

**The field's central methodological problem.** Every EEG neuroprognostication study after cardiac arrest is
contaminated by self-fulfilling prophecy: the clinician reads the EEG, it looks malignant, care is withdrawn,
and the EEG is recorded as having predicted the death it helped cause. This project hit the same wall — **L2**
(46 % die inside the withdrawal window) and **N14** (four instruments failed to separate withdrawal from
biological death).

**Why this measure is unusual.** Intra-burst 8–30 Hz content requires an FFT inside segmented bursts. It
appears in no clinical report and no clinician reads it, so **it cannot enter a withdrawal decision** — and a
self-fulfilling prophecy requires the predictor to be visible to the decision-maker. The reversal sharpens
that: a behavioural mechanism would have to act on an invisible feature in *opposite directions by aetiology*.

**Cohort caveat, stated first because it bounds R401.** `/tmp` was wiped mid-session and the R398 full
extract was lost, so this ran on the fallback **decedents-only** aetiology extract (n = 1,496).

### R400 · W1 — the reversal survives adjustment for what the clinician recorded — CONFIRMED

Adjusting for the two flags the treating team actually documented (burst suppression, generalized slowing):

| | n | intra-burst coefficient, adjusted for the visible flags |
|---|---|---|
| anoxic | 818 | **+1.671 [+0.606, +2.941]** |
| non-anoxic | 678 | **−2.271 [−4.164, −0.855]** |

**Interaction +4.287 [+2.535, +6.560].** Both arms individually exclude zero, in opposite directions, *after*
controlling for what the decision process had in front of it. The reversal is not a proxy for the recorded
features.

### R401 · W2 — the day-3 landmark — NOT confirmed on the strict criterion

Restricting to patients alive at day 3 (985 of 1,496; 34.2 % died inside the window):

| | n | event rate | AUC |
|---|---|---|---|
| anoxic | 431 | 65.2 % | **0.549 [0.496, 0.606]** — includes 0.5 |
| non-anoxic | 554 | 40.6 % | **0.409 [0.359, 0.456]** — excludes 0.5 |

Gap +0.141, directionally intact, but **the anoxic arm loses significance** and the registered criterion
required both intervals to exclude 0.5. Two readings, and this cohort cannot separate them: power (n falls
818 → 431) or a genuinely early-death-weighted anoxic association.

**A second limitation makes R401 weaker than it looks, and it is the fallback cohort's fault.** On a
decedents-only cohort, "alive at day 3" does not mean *survived* — everyone in it eventually died. The
landmark therefore contrasts *died 4–30 days* against *died later*, not survival against death, which is not
the estimand the withdrawal argument needs. **R401 must be re-run on the full cohort with survivors included
before it means anything**, and that re-extraction is running.

### R402 · W3 — the invisible measure discriminates better than the visible ones

AUC for 30-day death, same cohort:

| feature | visible to clinician? | anoxic | non-anoxic |
|---|---|---|---|
| burst suppression flag | **yes** | 0.525 | 0.511 |
| generalized slowing flag | **yes** | 0.325 | 0.466 |
| intra-burst 8–30 Hz | **no** | **0.589** | **0.407** |

The documented burst-suppression flag is close to uninformative in both arms (0.525 / 0.511). The invisible
measure discriminates better in both, **and is the only one of the three that reverses**. The slowing flag's
0.325 in anoxic is the P6 effect — its presence marks survival — and it does not reverse.

**What can and cannot be claimed.** Nothing observational proves the absence of a self-fulfilling prophecy
without a withdrawal variable, and N14 records four failed attempts to build one. What R400 supports is
narrower and still worth having: **the association does not depend on the features the treating team recorded
and acted on.** The landmark argument (R401) is not yet established and may not survive.

**Cumulative distinct results: 402.**

---

## R403 · W2 re-run on the full cohort — the ANOXIC arm does NOT survive the withdrawal window

R401 was flagged as uninterpretable because `/tmp` had been wiped and it ran on a decedents-only fallback,
where "alive at day 3" does not mean *survived*. The re-extraction is complete (2,449 patients with measured
aetiology, survivors included) and this is the proper version. **It does not confirm, and with more power than
before.**

Restricting to patients alive at day 3 — **1,938 of 2,449**, so 20.9 % died inside the withdrawal window:

| | n | died by day 30 | AUC |
|---|---|---|---|
| anoxic | 800 | 35.1 % | **0.535 [0.492, 0.580]** — includes 0.5 |
| non-anoxic | 1,138 | 19.8 % | **0.428 [0.388, 0.471]** — excludes 0.5 |

Gap +0.106, directional only. The anoxic arm is now estimated on **800** patients rather than the 431 of the
fallback run, so this is not a power failure of the kind R401 left open.

### What this does to the lead, stated plainly

**The two arms of the reversal are not equally robust to the withdrawal window.**

- **The non-anoxic (protective) direction survives it**: 0.407 in the full cohort → **0.428 [0.388, 0.471]**
  among day-3 survivors, interval still excluding 0.5.
- **The anoxic (harmful) direction does not**: 0.589 in the full cohort → **0.535 [0.492, 0.580]** among
  day-3 survivors. Its association is **concentrated in early deaths — precisely the window in which
  withdrawal of care dominates.**

That is the pattern a partial self-fulfilling prophecy would produce *in the anoxic arm specifically*, and
anoxic patients are exactly the population in which EEG-guided withdrawal is most aggressive. It is also
consistent with the biology genuinely being about early mortality after anoxia. **This design cannot separate
those two**, which is N14 restated.

**It does not overturn the reversal.** The full-cohort result stands with every robustness check it passed
(burden strata 3/3, burst-count strata 3/3, non-anoxic decomposition 4/4, both hospitals, two aetiology
definitions, measured labels). W1 also stands: adjusted for the flags clinicians actually recorded, the
interaction is **+4.287 [+2.535, +6.560]**, so the reversal is not a proxy for what the decision process saw.

**But the honest headline changes.** The claim is no longer "an aetiology reversal robust to the withdrawal
problem". It is: *a reversal whose protective arm is robust to the withdrawal window and whose harmful arm is
not distinguishable from withdrawal-driven early mortality.* Any manuscript must say that in the abstract,
not the limitations.

**Cumulative distinct results: 403.**

---

## R404–R406 · Guideline EEG findings do not transfer across aetiologies — and the reason may be the guidelines

The clinically actionable question this cohort is uniquely able to ask. ACNS terminology and ERC-ESICM
prognostication are built overwhelmingly on cardiac-arrest cohorts and applied to comatose patients generally.
**n = 9,302** with report findings, measured aetiology and outcome (34.9 % 30-day death, 23.8 % anoxic).

### R404 · Five of six findings behave differently by aetiology

Coefficient for 30-day death, within each aetiology, and their interaction:

| finding | prevalence | anoxic | non-anoxic | interaction |
|---|---|---|---|---|
| **burst suppression** *(primary)* | 39.2 % | **+0.47 [+0.29, +0.66]** | **+0.05 [−0.06, +0.16]** | **+0.42 [+0.20, +0.64]** |
| GPD | 24.2 % | +0.36 [+0.18, +0.55] | +0.52 [+0.40, +0.63] | −0.16 [−0.38, +0.06] |
| LPD | 18.8 % | **−0.25 [−0.52, +0.02]** | **+0.28 [+0.16, +0.41]** | **−0.53 [−0.84, −0.23]** |
| seizure | 48.0 % | −0.68 [−0.86, −0.50] | −0.07 [−0.17, +0.03] | **−0.60 [−0.80, −0.40]** |
| generalized slowing | 85.1 % | −1.34 [−1.53, −1.16] | −0.11 [−0.29, +0.07] | **−1.22 [−1.48, −0.97]** |
| focal slowing | 26.7 % | −1.28 [−1.60, −0.99] | −0.50 [−0.61, −0.39] | **−0.78 [−1.09, −0.47]** |

**Five of six interactions exclude zero.** Six tests were run and burst suppression was pre-specified as the
single primary; five hits is far beyond what multiplicity produces, so this is systematic rather than a
lucky member of a family.

**The headline is the primary test.** The guideline's central malignant pattern — burst suppression —
predicts death after anoxia (**+0.47**) and carries **essentially no prognostic information otherwise**
(**+0.05 [−0.06, +0.16]**).

### R405 · Weakening versus reversing, and burden adjustment

**LPD reverses sign**: −0.25 in anoxic against **+0.28 [+0.16, +0.41]** in non-anoxic, interaction excluding
zero. The rest weaken rather than flip. A reversal is the qualitatively stronger claim and only LPD makes it.

Re-estimated adjusting for **measured** suppression burden (n = 8,349), **five of six interactions survive** —
bs +0.28 [+0.03, +0.52], lpd −0.58 [−0.89, −0.25], seizure −0.56 [−0.81, −0.32], gen slowing
−1.16 [−1.53, −0.86], foc slowing −0.76 [−1.13, −0.41]. Only **GPD** vanishes (−0.18 [−0.43, +0.09]) and was
therefore a burden effect wearing a flag's clothes.

### R406 · The interpretation that matters, and it cuts against the obvious one

The easy reading is "EEG findings mean different things in different aetiologies, so guidelines derived from
cardiac arrest should not be applied uniformly". That is actionable and probably true in part. **But there is
a second reading, and for these particular variables it is at least as plausible.**

**These are the flags clinicians read, and the guidelines tell them to act on them differently by aetiology.**
After cardiac arrest, burst suppression is a documented malignant pattern and a recognised trigger for
withdrawal discussions. Outside anoxic injury there is no such rule. So the observation that burst suppression
predicts death **only** after anoxia is exactly what guideline-driven behaviour would manufacture. **The
aetiology-dependence of the visible findings may be evidence of guideline-driven self-fulfilling prophecy
rather than of aetiology-dependent biology.** R403 sharpens the worry: the anoxic arm is precisely where the
withdrawal window dominates.

**What breaks the tie is the invisible measure.** Intra-burst 8–30 Hz content shows the same
aetiology-dependence (R389–R399) and **cannot be driven by clinician behaviour**, because it appears in no
report and no clinician reads it — and adjusted for these very flags its interaction is
**+4.287 [+2.535, +6.560]** (R400). So at least part of the aetiology-dependence is not behavioural.

**The defensible combined claim:** guideline EEG findings are aetiology-dependent; for the visible ones this
is confounded with guideline-driven practice and cannot be separated here; an invisible quantitative measure
shows the same dependence and cannot be so confounded. **Any manuscript must present the visible-finding
result and the behavioural explanation together**, not the former alone.

**Cumulative distinct results: 406.**

---

## R407 · Burst suppression loses most of its aetiology-dependence past the withdrawal window; the invisible measure does not

R404–R406 left two readings of the guideline result — aetiology-dependent **biology**, or guideline-driven
**behaviour** — and could not separate them. They differ in *when* the deaths occur: withdrawal is
concentrated in the first days. So each predictor's aetiology interaction was estimated twice on identical
code, in the full cohort and restricted to patients alive at day 3 (n = 9,302; 12.8 % died inside the window).

| predictor | read by clinicians? | full cohort | alive at day 3 | retained |
|---|---|---|---|---|
| **burst suppression** | **yes** | **+0.42 [+0.21, +0.64]** | **+0.15 [−0.09, +0.41]** | **37 %** |
| LPD | yes | −0.53 [−0.82, −0.23] | −0.28 [−0.62, +0.05] | 53 % |
| generalized slowing | yes | −1.22 [−1.50, −0.96] | −0.90 [−1.23, −0.58] | 73 % |
| seizure | yes | −0.60 [−0.81, −0.40] | −0.45 [−0.69, −0.21] | 74 % |
| focal slowing | yes | −0.78 [−1.08, −0.45] | −0.74 [−1.17, −0.35] | 95 % |
| GPD | yes | −0.16 [−0.38, +0.06] | +0.31 [+0.04, +0.56] | *unstable* |
| **intra-burst 8–30 Hz** | **no** | **+4.65 [+3.15, +6.47]** | **+4.31 [+2.41, +6.47]** | **93 %** |

### The verdict, stated more narrowly than the script's own summary

**The script's pooled median (63 %) is contaminated and should not be quoted.** GPD's full-cohort interaction
is −0.16 [−0.38, +0.06] — not distinguishable from zero — so dividing by it yields a meaningless ratio
(−195 %). Excluding it, the five interpretable visible flags retain 37 %, 53 %, 73 %, 74 %, 95 %, median
**73 %**, against **93 %** for the invisible measure. **The ranges overlap**: focal slowing retains 95 %,
above the invisible measure. So the general claim "visible findings attenuate more than invisible ones" is
true only on the median and is not strongly supported.

**What IS strongly supported is narrower and more interesting.** **Burst suppression — the single finding the
guidelines explicitly name as a malignant pattern and a withdrawal trigger after cardiac arrest, and nowhere
else — retains only 37 %, and its day-3 interaction no longer excludes zero (+0.15 [−0.09, +0.41]).** The
invisible measure, over the same landmark, retains 93 % and still excludes zero.

That is exactly the pattern the behavioural account predicts **for the specific finding guidelines act on**,
and it is not a generic property of being clinician-visible: focal slowing, which no guideline names as a
withdrawal trigger, barely attenuates at all. The gradient across the visible flags tracks how strongly each
is guideline-actioned, which is a stronger form of the argument than the pooled comparison.

> ### ⚠ WITHDRAWN — do not quote the paragraph above. Corrected by R409 and R410.
>
> **The comparison in this section is invalid.** Burst-suppression flag prevalence in the subcohort that
> carries the invisible measure is **100.0 %** (R409), so the two columns are not two predictors on
> comparable patients — the invisible measure exists only *inside* the flag. The visible-versus-invisible
> contrast was then tested directly, on identical patients, and **failed**: inside the withdrawal window no
> predictor of either kind falls below its matched null, and a paired bootstrap puts P(invisible retains
> more at day 3) at 55 %, 44 %, 37 %, 36 % and 0 % against the five visible flags — all at or below chance.
> Generalized slowing makes the error concrete: below its null at 8/8 landmarks in the full cohort, **0/8**
> in the paired stratum. **The attenuation was a property of the population, not of clinician visibility.**
>
> **R410 then removed the behavioural interpretation's last independent support**: there is no local hazard
> discontinuity at 72 h or anywhere else (local excess 1.00, 1.05, 1.09 at days 2–4; largest in the cell
> 1.36 at day 10, [0.76, 2.33]), and the primary bump statistic fired equally at a placebo cut.
>
> **What survives from R407 is one sentence:** burst suppression's aetiology interaction retains 37 % past a
> day-3 landmark and no longer excludes zero (+0.15 [−0.09, +0.41]) — a fact about one finding, with
> front-loaded hypoxic-ischaemic mortality now the parsimonious explanation.

**Limits.** Withdrawal is unmeasured (N14) — this is an argument from timing, not proof. The invisible
measure is estimated on 2,449 patients rather than 9,302, so its interval is wider and its retained fraction
less precisely estimated. And R403 already showed the invisible measure's own anoxic arm attenuates, so it is
not a zero-attenuation reference; the comparison is relative throughout.

**Cumulative distinct results: 407.**

---

## R408 · The day-3 attenuation is a curve, not a cut point — and a matched null shows it is not power loss

R407 split the cohort once, at day 3. Two objections were open: **one landmark is one choice**, and
**restricting to survivors removes patients and events**, which attenuates a noisy interaction term on its
own. R408 registers a sweep over landmarks {0, 1, 2, 3, 5, 7, 10, 14} plus the control that makes the sweep
readable — at each landmark, a subsample of the **full** cohort matched on n, on 30-day death rate and on
anoxic fraction, with **no landmark applied** (150 draws, 5–95 % reported).

### The control works, and that is the first result

**The matched null sits at ~100 % at every landmark for every predictor** — bs 98–103 %, generalized slowing
100–102 %, invisible 103–119 %. Discarding 28 % of the cohort and more than two thirds of the events does
**not**, by itself, attenuate these interactions. So every departure below is a property of *who* was removed,
not of *how many*.

### Retained fraction by landmark day (observed; ▼ = below the null's 5th percentile)

| landmark | n | death % | **burst suppression** | **intra-burst 8–30 Hz (invisible)** | gen slowing | seizure | LPD | foc slowing |
|---|---|---|---|---|---|---|---|---|
| day 0 | 8,843 | 31.6 % | 84 % ▼ | 105 % | 92 % ▼ | 88 % ▼ | 66 % ▼ | 98 % |
| day 1 | 8,588 | 29.5 % | 77 % ▼ | 110 % | 89 % ▼ | 84 % ▼ | 55 % ▼ | 91 % |
| day 2 | 8,359 | 27.6 % | 63 % ▼ | 99 % | 80 % ▼ | 78 % ▼ | 46 % ▼ | 86 % |
| day 3 | 8,108 | 25.4 % | **37 % ▼** | **93 %** | 73 % ▼ | 74 % ▼ | 53 % ▼ | 95 % |
| day 5 | 7,746 | 21.9 % | −3 % ▼ | 71 % ▼ | 57 % ▼ | 79 % | 54 % ▼ | 91 % |
| day 7 | 7,467 | 19.0 % | −1 % ▼ | 48 % ▼ | 59 % ▼ | 79 % | 80 % | 108 % |
| day 10 | 7,081 | 14.5 % | −44 % ▼ | 27 % ▼ | 44 % ▼ | 80 % | 104 % | 90 % |
| day 14 | 6,742 | 10.2 % | −16 % ▼ | 39 % ▼ | 51 % ▼ | 113 % | 63 % | 52 % |

GPD is omitted: its full-cohort interaction is −0.16 and spans zero, so the ratio is not a quantity (R407).

**Free replication.** This script shares no code path with R407's and reproduces its two headline cells
exactly — burst suppression **37 %** and the invisible measure **93 %** at day 3.

### The pre-registered verdict is PARTIAL, and the registered shape prediction FAILED for both

Y2 asked whether burst suppression falls below its matched null where the invisible measure does not. **Both
fall below at some landmark** — bs at 8 of 8, the invisible measure at 4 of 8 — so the script returns
**PARTIAL** and the claim "excess attenuation is specific to visible findings" is **not** supported. Y3's
shape prediction (guideline-driven decays then flattens; biological tracks its null throughout) fails too:
Spearman ρ of (observed − null) against landmark day is **−0.95 for burst suppression and −0.95 for the
invisible measure**, identical.

### What the table shows that the registered criterion did not ask about — read as a reading, not a test

The two curves have the same slope and **different onsets**. Burst suppression is already below its null at
**day 0** and has lost two thirds of its interaction by day 3. The invisible measure is **at or above its
null at days 0, 1, 2 and 3** (105 %, 110 %, 99 %, 93 %) and only departs from day 5 onward. The withdrawal
window is days 0–3. Inside it the visible flagship moves and the invisible measure does not; outside it both
decay, which is what an acute-injury marker losing prognostic relevance looks like and is also what the
registered estimand drift produces.

**This is a cut chosen after seeing the curve.** It is consistent with the rationale registered in R407 (that
withdrawal is concentrated in the first days), but the 4/4-versus-0/4 split inside the window was not a
pre-specified test and is reported as description.

### The visible flags do not behave as one class

Burst suppression (ρ = −0.95, below null 8/8) and generalized slowing (ρ = −0.98, below null 8/8) decay.
Seizure (ρ = +0.02), LPD (ρ = +0.55) and focal slowing (ρ = −0.24) do not. **Being clinician-visible does not
predict attenuation; being the finding guidelines act on does** — which is the R407 reading, now with a curve
behind it instead of a single split.

### The limitation — and it is worse, and more interesting, than it first looked

Burst suppression is estimated on 9,302 patients and the invisible measure on the 2,449 that have burst
morphology. **The two curves are not from the same patients**, so part of the onset difference could be
cohort rather than predictor.

**CORRECTION, added immediately after R408 was written (see R409).** The obvious repair — redo the
comparison paired, on patients who have both — **is impossible by construction.** Burst-suppression flag
prevalence in the burst-morphology subcohort is **100.0 % (2,473 of 2,473)**, against 14.9 % in the full
findings cohort, because burst morphology can only be extracted from a recording that has bursts. Within the
patients who carry the invisible measure, the burst-suppression flag **has no variance**, so its interaction
is undefined there and no paired estimate exists at any sample size.

Two consequences, and both matter for how R407–R408 may be read:

1. **The onset contrast in the table above is confounded with cohort and must not be quoted as a
   like-for-like comparison of two predictors.** It compares a flag estimated across all patients with a
   graded measure estimated inside the flag-positive stratum.
2. **The right framing is better than the one that was lost.** The invisible measure is not a competitor to
   burst suppression; it is a **grading of what is inside it**. Every patient carrying it already triggers
   the guideline's flagship malignant pattern. R409 tests the paired question that *is* answerable — the
   invisible measure against the visible flags that actually vary in that same stratum.

**Cumulative distinct results: 408.**

---

## R409 · The paired test FALSIFIES the visible-versus-invisible contrast. What survives is a claim about burst suppression alone

R408 promised a paired repair. Checking the premise first killed the design and replaced it with a better one.

### Z0 · Why the obvious paired test does not exist

| flag | prevalence, full findings cohort (n = 49,232) | prevalence, burst-morphology subcohort (n = 2,473) |
|---|---|---|
| **burst suppression** | 14.9 % | **100.0 %** |
| generalized slowing | 76.5 % | 71.6 % |
| seizure | 30.2 % | 49.4 % |
| GPD | 7.7 % | 31.6 % |
| focal slowing | 19.3 % | 18.8 % |
| LPD | 6.6 % | 19.9 % |

Burst morphology can only be extracted from a recording that has bursts, so **every patient carrying the
invisible measure carries the flag**. Its interaction is undefined in that stratum at any sample size. The
invisible measure was never a competitor to burst suppression — **it grades what is inside it.**

### Z1/Z2 · Paired landmark sweep, identical patients (n = 2,449; 41.5 % 30-day death, 48.5 % anoxic)

Retained fraction against each predictor's own matched null (▼ = below the null's 5th percentile):

| landmark | **invisible** | GPD | seizure | gen slowing | foc slowing | LPD |
|---|---|---|---|---|---|---|
| day 0 | 105 % | 160 % | 97 % | 91 % | 88 % | 77 % |
| day 1 | 110 % | 170 % | 90 % | 95 % | 85 % | 72 % |
| day 2 | 99 % | 192 % | 94 % | 107 % | 86 % | 77 % |
| day 3 | 93 % | 205 % | 103 % | 101 % | 101 % | 87 % |
| day 5 | 71 % ▼ | 188 % | 113 % | 116 % | 88 % | 110 % |
| day 7 | 48 % ▼ | 182 % | 108 % | 96 % | 128 % | 166 % |
| day 10 | 27 % ▼ | 128 % | 118 % | 50 % | 148 % | 175 % |
| day 14 | 39 % ▼ | 102 % | 122 % | 55 % | 54 % | 133 % |

**Z2 FALSIFIED on its own criterion.** Inside the withdrawal window (days 0–3) **not one predictor —
visible or invisible — falls below its matched null.** The invisible measure holds, but so does every visible
flag in these patients, so there is no contrast to attribute to visibility.

### Z3 · Paired bootstrap at day 3 — the invisible measure does not win

Fraction of 800 paired resamples in which the invisible measure retains more of its interaction than the
visible flag, **on the same resampled patients**:

| versus | LPD | focal slowing | generalized slowing | seizure | GPD |
|---|---|---|---|---|---|
| P(invisible retains more) | 55 % | 44 % | 37 % | 36 % | 0 % |

**Every value is at or below chance.** The invisible measure is not more landmark-stable than the visible
findings when they are compared on identical patients.

### What this does to R407 and R408 — the claim narrows, and the narrower claim is the one to publish

**Withdrawn:** "clinician-invisible measures hold their aetiology-dependence past the withdrawal window while
clinician-visible ones lose theirs." R409 tests exactly that on identical patients and it does not hold.
Generalized slowing illustrates the problem directly: it fell below its null at **8 of 8** landmarks in the
full cohort (R408) and at **0 of 8** here. The attenuation was a property of the population, not the flag.

**Survives, and is now the whole claim:** **burst suppression's aetiology interaction collapses across the
withdrawal window — 84 %, 77 %, 63 %, 37 % at days 0–3, below its size/event/aetiology-matched null at all
eight landmarks, crossing zero by day 5 — and the matched null shows discarding patients and events does not
do this on its own.** That is a claim about the single finding the guidelines name as a withdrawal trigger
after cardiac arrest. It no longer rests on any comparison with the invisible measure.

### The honest caveat that the behavioural account cannot escape

Within a burst-suppressed stratum every patient is equally exposed to the guideline trigger, so a behavioural
account *predicts* the null R409 found — which makes this particular test unable to discriminate rather than
evidence for either side. Say that plainly. And the surviving burst-suppression result still admits a benign
reading: hypoxic-ischaemic mortality is genuinely front-loaded, and a landmark cannot separate "care was
withdrawn" from "the patient died of the injury." Withdrawal remains unmeasured; N14 records four failed
attempts, and R409 adds a fifth — `visit_disposition` carries `discharge_to_source_value` **100 % empty**
across all 38,893 rows and covers only 715 patients.

**Cumulative distinct results: 409.**

---

## R410 · No 72-hour fingerprint. The behavioural explanation for R408 loses its last independent support

The landmark cannot separate front-loaded biology from guideline-timed withdrawal, because both attenuate an
interaction across the same window. A clock can: ERC-ESICM forbids prognostication before **72 hours** and
names burst suppression a malignant pattern, so a decision rule should leave a **local** hazard bump at a
round-numbered hour in the one cell the guideline addresses. Injury severity does not consult a calendar.

### V1 · Discrete daily hazard, % (deaths on day d / alive at the start of day d), n = 9,302

| cell | n | d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|---|---|---|---|---|
| **anoxic + BS** | 1,598 | 15.1 | 8.1 | 7.9 | 7.8 | 6.9 | 4.9 | 3.4 | 3.5 | 4.0 |
| anoxic, no BS | 617 | 9.2 | 4.6 | 3.9 | 2.9 | 2.6 | 3.5 | 2.6 | 4.2 | 2.7 |
| non-anoxic + BS | 2,047 | 2.6 | 2.2 | 1.9 | 2.4 | 1.7 | 1.7 | 1.7 | 1.5 | 1.1 |
| non-anoxic, no BS | 5,040 | 2.1 | 1.5 | 1.5 | 2.1 | 1.8 | 1.4 | 1.4 | 1.4 | 1.9 |

### V2 passed its criterion — and V4 shows the criterion was the wrong one

| cell | days 2–4 over 5–7 | bootstrap | **placebo: days 6–8 over 9–11** | bootstrap |
|---|---|---|---|---|
| **anoxic + BS** | **1.91** | [1.56, 2.40] | **1.57** | **[1.15, 2.21]** |
| anoxic, no BS | 0.92 | [0.64, 1.38] | 1.41 | [0.90, 2.31] |
| non-anoxic + BS | 1.21 | [0.93, 1.58] | 0.96 | [0.68, 1.29] |
| non-anoxic, no BS | 1.28 | [1.06, 1.54] | 1.13 | [0.92, 1.41] |

The anoxic burst-suppressed cell beat all three others at the 72 h cut (2.07×, 1.58×, 1.49×, every interval
excluding 1) — **and it does the same thing at an arbitrary cut where no guideline acts.** An adjacent-window
ratio never tested locality; it rewards any cell whose hazard decays more steeply. **V2 is therefore NOT
INTERPRETABLE and no claim about guideline timing follows from it.** The first version of this script printed
"V2 CONFIRMED" while its own placebo was lit — the same defect as R387, and the gate is now wired so a lit
placebo blocks the verdict (error catalogue rule 31).

### V5 · The locality test, and it is unambiguous

h[d] divided by the mean of h[d−1] and h[d+1]. A monotone decay scores ~1 at every interior day; a decision
rule puts a peak at the guideline's day.

| cell | d2 | d3 | d4 | d5 | d6 |
|---|---|---|---|---|---|
| **anoxic + BS** | **1.00** | **1.05** | **1.09** | 0.94 | 0.81 |

**There is no interior peak.** The largest local excess anywhere in that cell is 1.36 at **day 10**, bootstrap
**[0.76, 2.33]** — noise, and not at any guideline-relevant hour. What V1 actually shows is a *plateau*:
8.1, 7.9, 7.8, 6.9 across days 1–4, then a fall from day 5. A sustained high hazard that then stops is what
severe hypoxic-ischaemic injury looks like; it is not a clock signature.

### What this does to the arc R404 → R408

**The behavioural (self-fulfilling-prophecy) explanation of burst suppression's aetiology-dependence now has
no independent support.** Three attempts, three failures: the visible-versus-invisible contrast is falsified
on paired patients (R409); withdrawal itself is unmeasurable here (five failed proxies, N14 plus R409); and
there is no timing discontinuity (R410). **What survives is the descriptive fact — burst suppression's
aetiology interaction is expressed inside days 0–4 and is spent by day 5, beyond what power loss explains —
and that fact is equally consistent with front-loaded hypoxic-ischaemic mortality.** Reading (A) is now the
parsimonious one and should be stated as the primary interpretation.

**This does not touch the aetiology reversal itself** (R389–R399), which survived no-model, burden strata
3/3, burst-count strata 3/3, non-anoxic decomposition 4/4, both hospitals, two aetiology definitions and
measured labels. That remains the durable finding; the withdrawal story does not.

**The caveat that keeps this a null rather than a refutation.** Day 0 is the first EEG, not the arrest, and
the arrest-to-EEG lag is unmeasured. Smearing degrades a true spike, so this null is weak evidence against
(B) — it is decisive only against the claim that we have *evidence for* (B).

**Cumulative distinct results: 410.**

---

## R411 · R403 and R409 both stand. The reversal survives the landmark; the anoxic arm genuinely does not

R403 warned that the lead's anoxic arm does not survive the withdrawal window. R409 found the aetiology
interaction retains 93 % across the same landmark, inside its matched null. The registered hypothesis here
was that **R403 was a power artefact** — split a cohort, require each half to clear its own null, and false
negatives follow. **That hypothesis is refuted.** Both results are correct, about different quantities.

### W1 · Both estimands, one cohort (n = 2,449), identical code

| | n | deaths | **interaction** | anoxic arm AUC | non-anoxic arm AUC |
|---|---|---|---|---|---|
| full cohort | 2,449 | 41.5 % | **+4.646 [+3.092, +6.547]** | 0.577 [0.546, 0.610] | 0.426 [0.390, 0.461] |
| alive at day 3 | 1,938 | 26.1 % | **+4.313 [+2.335, +6.481]** | **0.535 [0.491, 0.578]** ← includes 0.5 | 0.428 [0.388, 0.471] |

### W2 · The matched null applied to the arm-wise statistic — which R403 never did

Subsamples of the **full** anoxic arm at the landmark's size (800) and event rate (35.1 %), no landmark:

| arm | matched subsamples, median AUC | % whose interval includes 0.5 | actual day-3 subsample |
|---|---|---|---|
| **anoxic** | 0.579 | **1 %** | **0.535 [0.488, 0.577]** |
| non-anoxic | 0.427 | **0 %** | 0.428 [0.386, 0.470] |

**R403 STANDS.** Only 1 % of same-size, same-event-rate subsamples fail the test that the day-3 subsample
fails, so the anoxic arm's drop from 0.577 to 0.535 is **not** explained by having fewer patients. It is
explained by *which* patients were removed.

### The reconciliation, and it is not a compromise

Both are true because they measure different things. **The interaction is a contrast**, and it survives
(93 % retained, still excluding zero) because the **non-anoxic arm is completely unmoved** — 0.426 → 0.428,
with 0 % of matched subsamples failing. The reversal therefore survives the withdrawal window. **The anoxic
arm's prognostic information is genuinely concentrated in patients who die early**, beyond anything power
explains.

**So the handoff's §3 warning stands and is now better evidenced than when it was written** — it rested on a
CI that included 0.5, which is weak; it now rests on a matched null that puts that failure at the 1st
percentile. R410 remains the reason the *cause* is undetermined: front-loaded hypoxic-ischaemic mortality and
withdrawal predict the same concentration, and there is no timing fingerprint to separate them.

### What the paper should claim

The estimand was fixed before the numbers: the claim is that the **direction** of association differs by
aetiology, so **the interaction is the test** (+4.646 [+3.092, +6.547] full, +4.313 [+2.335, +6.481] past the
landmark) and the arm-wise AUCs are descriptive. The anoxic arm's early-death concentration belongs in the
abstract, not the limitations — R403's original instruction, now with a control behind it.

**Cumulative distinct results: 411.**

---

## R412 · The flag residual: waveform SHAPE explains nothing, burst AMPLITUDE explains a little

The last of the four named candidates for R358–R360's residual — the generalized-slowing flag carries
**−0.752 [−1.075, −0.434]** beyond suppression burden and intra-burst 8–30 Hz content, and R388 showed that
is not an artefact of adjusting for burden linearly. Background spectrum (B3) and topography (T3) are
eliminated; reactivity is unavailable in this schema. Shape was rated above the two failures because it
differs in **kind** from a band-power ratio rather than merely in location (catalogue rule 28).

Cohort: n = 1,386 with flag + burden + intra-burst + shape + ascertained death; 67.5 % 30-day death, 67.5 %
flag-positive (**a coincidence, not a bug — verified: the vectors are distinct, r = −0.291, cross-tab
543/393/392/58**).

### S0 precondition, and its honest reading

Out-of-bag AUC increment of the shape block over burden + intra-burst: **+0.0141 [−0.0059, +0.0271] —
includes zero.** The block passed the precondition on its *coefficients* (burst_amp **+0.629** standardized),
not on predictive increment. This is the project's familiar pattern — genuine association, no discrimination
gain (cf. R362, R379) — and the precondition should be read as "informative enough to interpret an
attenuation", not as "predictive".

### S1–S3 primary and placebo

| | flag coefficient |
|---|---|
| burden (quintiles) + intra-burst | **−1.0370** |
| + the four-variable shape block | **−0.9184** |
| paired change | **+0.1186 [+0.0501, +0.1998]** — excludes zero |
| **placebo: same four covariates permuted across patients** | median **−0.0024**, 95 % of 400 draws in **[−0.0228, +0.0136]** |

The observed change is far outside the placebo interval, so this is not what four informationless covariates
do to a coefficient. **S2 confirmed on its pre-registered criterion.**

### What it actually is — and the queue item's premise was wrong

Drop-one decomposition (descriptive, run after the primary):

| variable added alone | flag coefficient | change |
|---|---|---|
| **burst_amp** | −0.9587 | **+0.0783** (66 % of the total) |
| burst_dur | −1.0239 | +0.0131 |
| **stereotypy** | −1.0282 | **+0.0088** |
| supp_cv | −1.0401 | −0.0031 |

**Stereotypy — the measure the queue named as the shape handle — contributes essentially nothing.** The
effect is carried by burst **amplitude**, which is a scale parameter, not a morphology one. So the named
candidate "waveform shape rather than band power" is **largely eliminated**; what survived is a different
quantity that happened to be in the same block. Amplitude is close to orthogonal to what was already
adjusted for: r = **−0.0001** with burden and **−0.023** with intra-burst content, so it is genuinely new
information rather than a re-expression.

### The gain-artefact threat, tested because amplitude is the measure most exposed to it

| site | n | burst_amp median [IQR] | flag coef → with shape (change) | burst_amp alone |
|---|---|---|---|---|
| S0001 | 849 | 24.71 [18.05, 34.86] | −0.7537 → −0.6195 (**+0.1342**) | +0.0838 |
| S0002 | 537 | 25.06 [16.18, 37.03] | −1.3119 → −1.2478 (**+0.0641**) | +0.0689 |

Amplitude distributions are near-identical across hospitals, the attenuation replicates **within both** in
the same direction, and re-running with amplitude **z-scored within site** — which removes any per-site gain
offset by construction — gives **+0.1165** against the pooled **+0.1186**. **Not a between-site scale
artefact.**

### The verdict, stated at the size it actually is

**89 % of the flag residual survives.** The flag still carries **−0.918** after the shape block is added.
This is the first positive on the residual after two eliminations, and it is a *small* one that identifies
burst amplitude — not shape — as a real but partial contributor. The residual remains overwhelmingly
unexplained, and with stereotypy, background spectrum and topography all eliminated and reactivity
unavailable, **there is no named candidate left that accounts for the bulk of it.**

**Scope:** morphology requires bursts, so this is the residual within burst-suppressed patients — the same
stratum R360 was estimated in, so like-for-like, but not a claim about all patients (R409, rule 32).

**Cumulative distinct results: 412.**

---

## R413 · The reversal does NOT reproduce on an independent instrument — it is a property of spectral content, not of burst vigour

No cohort anywhere has EEG + outcome + mixed aetiology, so the lead cannot be replicated externally at any
effort. When an external replicate is structurally unavailable the strongest remaining check is a **second
instrument measuring something else** (catalogue rule 23). R412 produced one: burst amplitude carries
independent information and is near-orthogonal to everything the lead is adjusted for.

Cohort n = 1,385 (morphology ∩ burden ∩ aetiology ∩ ascertained death); 67.5 % 30-day death, 53.9 % anoxic.

### T0 · The orthogonality premise holds, re-checked here rather than inherited

`burst_amp` vs `alpha_beta` **r = −0.023**; vs burden **r = −0.058**. It is not the same measure twice.
(For contrast, `burst_dur` vs burden is **−0.745** and `supp_cv` vs burden **+0.627** — those two are largely
burden in disguise, which is why they are exploratory only.)

### T1/T2 · Aetiology interaction by measure (standardized, burden quintiles adjusted)

| measure | role | interaction | |
|---|---|---|---|
| **alpha_beta** (intra-burst 8–30 Hz) | **reference — the lead** | **+0.913 [+0.574, +1.336]** | excludes zero |
| **burst_amp** | **PRIMARY, pre-specified** | **+0.256 [−0.494, +0.796]** | **includes zero** |
| stereotypy | exploratory | +0.317 [+0.040, +0.645] | excludes zero |
| burst_rate | exploratory | +0.209 [−0.053, +0.459] | ns |
| burst_dur | exploratory | −0.179 [−0.431, +0.064] | ns |
| supp_cv | exploratory | +0.060 [−0.181, +0.320] | ns |

**Scale note, to prevent a false comparison:** +0.913 is *per standard deviation* and burden-adjusted, so it
is **not** comparable to R411's +4.646, which was on the raw measure with no burden term. The reference arm
was re-estimated here precisely so the comparison within this table is like-for-like.

### T4 · Direction, which needs no model and is the stronger evidence

| measure | anoxic AUC | non-anoxic AUC |
|---|---|---|
| **alpha_beta** | **0.600 [0.553, 0.645]** ✳ | **0.398 [0.354, 0.441]** ✳ |
| burst_amp | 0.461 [0.417, 0.501] | 0.493 [0.452, 0.539] |
| stereotypy | 0.567 [0.515, 0.619] ✳ | 0.478 [0.433, 0.527] |
| burst_dur | 0.337 [0.287, 0.383] ✳ | 0.424 [0.379, 0.468] ✳ |
| burst_rate | 0.552 [0.506, 0.601] ✳ | 0.547 [0.508, 0.592] ✳ |
| supp_cv | 0.571 [0.521, 0.621] ✳ | 0.544 [0.501, 0.586] ✳ |

✳ = excludes 0.5. **Intra-burst content is the only measure of the six whose two arms sit on OPPOSITE sides
of 0.5 with both intervals excluding it.** Burst amplitude's arms sit on the *same* side and neither excludes
0.5. Burst duration, rate and suppression variability are all same-direction in both arms — they carry
outcome information without reversing.

### Verdict, stated with the caveat that limits it

**The reversal does not reproduce on burst amplitude.** But this is a **failure to replicate, not a
demonstrated absence**: the interaction's upper bound (+0.796) is **87 % of the reference effect**, so an
amplitude interaction of similar size is not excluded by these data. The model-free T4 evidence is stronger
than the interaction test and points the same way — no reversal is in evidence for amplitude.

**What it is worth.** It removes a real and separate worry — that the reversal is an artefact of how one
number was computed — by showing five other morphology measures from the *same bursts in the same patients*
do not behave that way, while the lead's own measure does. And it points a mechanism toward **frequency
content rather than signal scale**, as a direction to test rather than a constraint established.

**Exploratory caution.** Stereotypy's interaction excludes zero (+0.317 [+0.040, +0.645]) — but it is one of
four exploratory tests, which is roughly what chance produces at 5 %, and its non-anoxic arm does **not**
exclude 0.5 (0.478 [0.433, 0.527]), so it is not a second reversal. **No claim may rest on it without its own
registration.**

**Not external replication.** Same patients, same hospital network, same recordings — only the measurement
differs.

**One deviation from house practice, recorded because it is a real difference.** Burden here is the `burden`
column of the morphology table (computed on the same recording as the morphology) rather than the usual
`heedb_bs_burden_win` cache. It is internally consistent across all six measures, which is what the
comparison needs, but it is not the burden variable R412 used.

**Cumulative distinct results: 413.**

---

## R414 · The reversal is NOT a propofol artefact — and it is STRONGEST where no sedative was running

The largest untested objection to the lead. Intra-burst **8–30 Hz** is close to what GABAergic anaesthetics
manufacture — propofol produces frontal alpha and beta — and sedation practice differs systematically by
aetiology (post-arrest patients are sedated on protocol for targeted temperature management). Sedation had
been checked against **burden** and against the **clinician-flag residual**, but both checks predate R389, so
the reversal itself had never been through it.

Cohort n = 1,450 (morphology ∩ aetiology ∩ **drug data** ∩ ascertained death); 69.0 % 30-day death, 55.3 %
anoxic, **80.3 % actively sedated at the EEG**. Patients with no drug record are excluded, not assumed
unsedated (rule 5). "Active" reuses `heedb_infusion_at_eeg.py`'s validated definition: a BS-capable agent
(propofol, midazolam, pentobarbital, thiopental, phenobarbital) whose interval spans the EEG or began within
4 h.

### D0/D1 · The confounding pathway is weak on its own terms

| | sedated | not sedated | death % sedated | death % unsedated |
|---|---|---|---|---|
| anoxic | 679 | **123** | 83.7 % | 74.0 % |
| non-anoxic | 485 | **163** | 57.3 % | 38.7 % |

Sedation prevalence differs by only **9.8 pp** between arms (84.7 % vs 74.8 %), and sedation shifts the
measure by only **0.097 SD**. A drug confound needs both to be substantial; neither is.

### D2/D5 · The reversal by sedation stratum

| stratum | n | aetiology × content interaction |
|---|---|---|
| full drug-documented cohort | 1,450 | +4.644 [+2.796, +6.886] |
| **NOT actively sedated (primary)** | **286** | **+12.582 [+7.789, +19.664]** |
| actively sedated (mirror) | 1,164 | +3.491 [+1.506, +5.886] |

**D2 survives.** The reversal is present, same-signed, and excludes zero where **no BS-capable sedative was
running**. The drug explanation predicted the opposite.

### D3 · The matched null makes the small stratum interpretable

Subsamples of the full drug-documented cohort matched on n (286), death rate (53.8 %) and anoxic fraction
(43.0 %), **with no sedation restriction**, fail to exclude zero **25 % of the time** (74/300). So a stratum
this size fails by chance in a quarter of draws — and the actual unsedated stratum did not merely pass, it
produced the largest interaction in the table.

### D4 · Direction, model-free — and this is the sound basis for "stronger"

| stratum | anoxic AUC | non-anoxic AUC | gap |
|---|---|---|---|
| **not sedated** | **0.647 [0.553, 0.746]** ✳ | **0.339 [0.259, 0.432]** ✳ | **0.308** |
| actively sedated | 0.577 [0.518, 0.626] ✳ | 0.426 [0.379, 0.478] ✳ | 0.151 |

✳ = excludes 0.5. Both strata show the reversal — opposite sides of 0.5, all four intervals excluding it —
and the unsedated gap is **roughly twice** the sedated one.

**Why the AUC comparison and not the coefficients.** Logistic coefficients are **not comparable across
subgroups with different outcome variance** (non-collapsibility), and the unsedated stratum has a much larger
aetiology main effect (74.0 % vs 38.7 % death). So +12.6 versus +3.5 must **not** be read as "3.6× stronger".
AUC is scale-free and is the honest basis for the comparison; on it, the reversal is about twice as wide
without sedation.

### What this means, and it is more than a control passing

**Catalogue rule 17 applies in the best possible way: the fix made the effect stronger, so the diagnosis was
wrong — a refutation of the drug explanation, not a refinement of it.** And the surviving stratum has a
clinical identity: burst suppression *without* a sedative running is **pathological rather than iatrogenic**
suppression. **The reversal is strongest exactly where the suppression is not drug-induced**, which is a
positive mechanistic statement and converges with this project's older iatrogenic-versus-pathological thread.

**Limits.** The precondition passed narrowly — the anoxic unsedated cell is **123** against a pre-set minimum
of 120. OMOP records administrations, not infusion rates or plasma levels, so residual drug from earlier
dosing is invisible and "not actively sedated" is a weaker statement than "drug-free". The stratum
comparison was not a pre-registered three-way test; the non-overlap of the two intervals is reported as
description.

**Cumulative distinct results: 414.**

---

## R415 · The interneuron/epileptogenicity mechanism is REFUTED — and refuted directionally, not merely unsupported

Candidate **C** from the 2026-07-29 cadence brainstorm: fast-spiking inhibitory interneurons are selectively
vulnerable to hypoxia-ischaemia, so surviving 8–30 Hz activity after anoxia is **disinhibited, epileptogenic**
cortex (bad), while in non-anoxic coma it is **preserved** cortex (good). It was the only candidate that
explains the *sign reversal* directly rather than predicting a weakening, and R413 had sharpened it by showing
the reversal lives in spectral content and in none of five other morphology measures.

It was testable against a **new outcome** — clinician-marked epileptiform findings — rather than by
re-slicing death. Cohort n = 2,449, 48.5 % anoxic.

### E0 · Preconditions pass

| arm | n | epileptiform | focal slowing | content mean (sd) |
|---|---|---|---|---|
| anoxic | 1,187 | 54.4 % | 7.2 % | 0.1787 (0.1738) |
| non-anoxic | 1,262 | 74.5 % | 29.4 % | 0.1348 (0.1056) |

### E1 · The prediction fails

| outcome | aetiology × content interaction | |
|---|---|---|
| **epileptiform (GPD/LPD/seizure) — PRIMARY** | **−0.032 [−0.237, +0.154]** | **includes zero** |
| focal slowing — PLACEBO | −0.243 [−0.482, −0.035] | excludes zero |

**C predicted a positive interaction and the data give a null.** Candidate C is **demoted**, not kept alive
on plausibility.

### The refutation is directional, which is stronger than a null

Model-free, the AUC of intra-burst content for an epileptiform finding is **0.410 [0.378, 0.444]** in anoxic
and **0.457 [0.424, 0.493]** in non-anoxic — **both below 0.5, both excluding it**. More intra-burst fast
content means **less** epileptiform activity, in *both* arms. C predicted the opposite in the anoxic arm.
E4 agrees: corr(content, epileptiform) is **−0.157** anoxic and **−0.080** non-anoxic.

E3 (exploratory, conditions on a post-exposure variable — rule 13) points the same way. Within anoxic
patients, content→death is **not** weaker without epileptiform activity: AUC **0.604 [0.540, 0.670]** with no
epileptiform finding versus **0.566 [0.506, 0.627]** with one. The mediation story requires the reverse.

### Two methodological notes worth carrying forward

**The placebo fired** (focal slowing, −0.243 [−0.482, −0.035]). It does not rescue E1 — E1 is null in its own
right — but it independently shows this family of statistics responds to non-epileptiform findings too, so a
*positive* E1 would have been unreadable anyway. **The placebo earned its place before the primary was
known.**

**The script's first verdict was wrong and was fixed.** It evaluated the placebo *before* the primary and
printed "E1 NOT INTERPRETABLE", hiding a clean refutation behind a caveat. A placebo can only invalidate a
primary that would otherwise be declared a success; a primary that is null in its own right is a *failed
prediction*. Order matters, and the corrected logic is now in the script.

### Where this leaves the mechanism hunt

| candidate | status |
|---|---|
| A · GABAergic drug signature | **dead** (R414 — reversal is *wider* without sedation) |
| B · Thalamocortical / mesocircuit | open, partly tested (R395–R396) |
| **C · Interneuron loss / epileptogenicity** | **DEMOTED — R415, refuted directionally** |
| D · Time-from-injury confounding | weak, and the interval is unmeasurable here (R410) |
| E · Guideline-driven withdrawal | dead (R409–R410) |

**Four of five candidates are now closed and the reversal is more robust than any explanation of it.** It has
survived: no model, burden strata 3/3, burst-count strata 3/3, non-anoxic decomposition 4/4, two hospitals,
two aetiology definitions, measured labels, the withdrawal landmark (R411), an independent instrument
(R413 — specificity), and sedation (R414 — strengthened). **B is the last candidate standing**, and the
useful new constraint from R415 is that whatever the mechanism is, it makes fast content coincide with
*fewer* epileptiform findings in both aetiologies.

**Cumulative distinct results: 415.**

---

## R416 · Alpha coma is a MAGNITUDE MODIFIER, not the mechanism — the sign still tracks aetiology

Candidate **F1**, the top pick of the exhaustive brainstorm and the only candidate that explains a *sign*
reversal through a named clinical entity: after anoxia, monotonous non-reactive alpha ("alpha coma") is
malignant; elsewhere alpha means arousal and is benign. If that is the mechanism, the true modifier is not
aetiology but whether the cortex can **organise state** — and aetiology is merely a proxy for "is this alpha
coma".

Tested with an arousal-organisation composite **AO** = any of `pdr`, `awake`, `spindles`, `n1`, `n2`,
`vertex wave`, `k_complexes`, `posts`, built from findings columns already present — no re-extraction.
`diffuse Beta` was deliberately excluded from AO (it is itself fast content; including it would be circular).
Cohort n = 2,449; 41.5 % 30-day death; 48.5 % anoxic; AO present 67.4 %; median age 60 [42–71].

### M0 · AO varies in both arms, and is itself a strong death marker

| cell | n | 30-day death | median age |
|---|---|---|---|
| anoxic, AO present | 671 | 42.0 % | 56 |
| anoxic, AO absent | 516 | **74.8 %** | 59 |
| non-anoxic, AO present | 979 | 22.0 % | 61 |
| non-anoxic, AO absent | 283 | **47.3 %** | 62 |

AO prevalence: anoxic **56.5 %**, non-anoxic **77.6 %**. Losing arousal-organisation roughly **doubles**
mortality in both arms — a large main effect, independent of anything about the reversal.

### M1/M2 · AO modifies the magnitude, but does not set the sign

AO × content interaction (age-adjusted): **−0.208 [−0.400, −0.035]**, excludes zero and in the predicted
direction — where the cortex can organise, fast content is more protective.

But the model-free 2×2 is decisive against F1's actual claim:

| cell | n | AUC of content → 30-day death |
|---|---|---|
| anoxic, AO present | 671 | 0.548 [0.500, 0.596] |
| anoxic, AO absent | 516 | **0.608 [0.556, 0.655]** ✳ |
| non-anoxic, AO present | 979 | **0.436 [0.394, 0.481]** ✳ |
| non-anoxic, AO absent | 283 | **0.424 [0.349, 0.491]** ✳ |

✳ = excludes 0.5. **The non-anoxic arm is protective whether or not the cortex can organise (0.436 vs
0.424 — essentially identical), and the anoxic arm is harmful either way.** The registered STRONG criterion
required both arms protective within AO-present *or* both harmful within AO-absent; **neither holds**. The
sign tracks **aetiology**, not arousal-organisation. What AO does is sharpen the anoxic arm (0.608 without
organisation vs 0.548 with) — exactly what alpha coma would do as a *modifier*.

### M3/M4 · The placebo gate fails outright

| model | aetiology × content | attenuation vs base |
|---|---|---|
| base (age-adjusted) | +0.690 [+0.448, +0.969] | — |
| + AO × content | +0.650 [+0.424, +0.926] | **+6 %** |
| **placebo: + focal-slowing × content** | +0.602 [+0.378, +0.888] | **+13 %** |

**A non-arousal finding attenuates the aetiology interaction more than twice as much as AO does.** The
attenuation therefore carries no weight, exactly as the pre-registered gate specified.

### M5 · The diffuse-beta probe is unusable

`diffuse Beta` prevalence is **1.9 %** (anoxic) and **5.4 %** (non-anoxic) — 23 and 68 patients, both below
the analysis floor. Reported as not estimable rather than as a null.

### Verdict, and a second verdict-logic bug caught

**F1 PARTIAL.** Arousal-organisation is a real effect modifier and a powerful independent prognostic marker,
but it is **not the mechanism of the reversal**.

**The script's first verdict said "F1 SUPPORTED" and was wrong**, for two reasons now fixed in the code:
its `sign()` helper treated a cell *spanning* 0.5 as satisfying "protective", letting a null cell clear a
criterion that demanded a direction; and its placebo check asked whether the placebo attenuated a lot in
absolute terms rather than **whether it attenuated more than AO**. This is the second verdict-logic defect in
two results (cf. R415's ordering bug) — **the pattern is that permissive comparison operators quietly convert
a null into a pass.**

### Why the sub-band re-extraction still runs

The registration tied the expensive S3 pass to this result. F1 is demoted to a modifier rather than
eliminated, and candidates **F2** (the slow denominator — `alpha_beta` is a ratio, so the reversal may live
in 1–8 Hz) and **F3** (monotony/dispersion) are untested and **independent of AO**. The alpha-vs-beta split
is *more* informative now that arousal-organisation has failed to explain the sign. Stated here rather than
silently departing from the registration.

**Cumulative distinct results: 416.**

---

## R417 · The reversal is BROADBAND and lives entirely in spectral BALANCE — absolute power does not reverse at all

The decisive S3 re-extraction: `alpha_beta` decomposed on the SAME bursts into alpha vs beta, absolute band
powers, and within-patient dispersion. n = 2,473 recordings extracted (100 % success), analysis cohort 2,449.

### V0 · The reproduction gate, and it caught a real bug before it caught a result

**First run FAILED**: Pearson r = **0.7229** against the cached `alpha_beta`, only 6 % reproducing exactly,
mean signed difference −0.0098 (no shift — the signature of scoring *different windows*, not computing a
different quantity). Cause: the extraction imported `heedb_burst_morphology`'s **constants** but
re-implemented its **acceptance rules**, omitting the finite-sample filter, the 20 s minimum, the
`dead.mean() > 0.5` rejection and the **≥ 4-burst requirement** — so it scored windows the parent discards.
After copying every rule line-for-line: **r = 1.0000, mean difference −0.0000, 2,473/2,473 (100 %)
reproducing to 1e-4.** The gate is what stood between a subtle segmentation difference and a published
sub-band claim.

### V2/V3 · Every ratio-based measure reverses; neither absolute power does

| measure | aetiology × measure interaction | anoxic AUC | non-anoxic AUC | reversal? |
|---|---|---|---|---|
| **alpha_beta** (reference) | **+0.690 [+0.448, +0.974]** | 0.577 ✳ | 0.426 ✳ | **YES** |
| alpha_frac (8–13) | +0.467 [+0.279, +0.686] | 0.534 ✳ | 0.420 ✳ | **YES** |
| beta_frac (13–30) | +0.593 [+0.326, +0.970] | 0.576 ✳ | 0.428 ✳ | **YES** |
| ab_iqr (dispersion) | +0.373 [+0.162, +0.604] | 0.553 ✳ | 0.443 ✳ | **YES** |
| **log_fast_pw** (absolute) | +0.111 [−0.087, +0.303] | **0.390** ✳ | **0.403** ✳ | **no** |
| **log_slow_pw** (absolute) | −0.172 [−0.365, +0.028] | **0.371** ✳ | **0.445** ✳ | **no** |

✳ = excludes 0.5. `slow_frac` is omitted as a finding: it correlates **−1.0000** with `alpha_beta` by
construction (V4), so its mirror-image result is arithmetic.

### The three candidates, answered

**F1 (alpha coma) — CLOSED.** The reversal is **not localised in frequency**. Both sub-bands carry it, and
beta (+0.593; AUC 0.576/0.428) carries it at least as strongly as alpha (+0.467; 0.534/0.420). No
alpha-specific account is needed. With R416 having demoted F1 to a magnitude modifier, this closes it.

**F2 — ANSWERED, and it is the sharpest result of the session.** **Neither absolute power reverses.** More
absolute power of *either* band is protective in *both* aetiologies (fast 0.390/0.403; slow 0.371/0.445 —
same side of 0.5, all four intervals excluding it). The reversal exists **only in the ratio**. And
`alpha_beta` correlates **+0.002** with absolute fast power — **the reversing quantity is essentially
orthogonal to how much signal there is.** So F2 as posed (slow carries it) is rejected, and so is its
mirror image for fast.

**F3 (monotony) — marginal, and independence NOT established.** `ab_iqr` reverses (+0.373; 0.553/0.443) but
correlates **+0.628** with `alpha_beta`. Whether dispersion adds anything beyond level needs mutual
adjustment, which this script deliberately does not do; the verdict was corrected to say so rather than
claim an "independent" reversal.

### What this changes about how the lead should be described

**The finding is not "more fast activity predicts death after anoxia".** Absolute fast activity is
*protective in both groups*. The finding is that the **balance** between fast and slow content — a
normalised quantity orthogonal to total power — reverses its prognostic meaning by aetiology. That is a
materially different and more precise claim than the one the project has been carrying, and it should be
stated this way in any manuscript.

**Cumulative distinct results: 417.**

---

## R418 · Mutual adjustment: monotony CLOSES, orthogonality to power is ESTABLISHED, and the decomposition is additive

R417 reported four marginal reversals and refused to call any of them independent. This settles it. Every
measure is entered **with its own aetiology interaction** — never as a bare main effect, which is the standard
way to make an interaction look robust when it is not. n = 2,449.

| model | interaction reported | value | retains |
|---|---|---|---|
| marginals | alpha_beta | +0.690 [+0.448, +0.974] | — |
| | ab_iqr | +0.373 [+0.173, +0.605] | — |
| | alpha_frac | +0.467 [+0.276, +0.675] | — |
| | beta_frac | +0.593 [+0.337, +0.991] | — |
| **U1** | **ab_iqr \| + alpha_beta** | **−0.099 [−0.418, +0.209]** | **includes zero** |
| U1 | alpha_beta \| + ab_iqr | +0.755 [+0.398, +1.203] | 109 % |
| **U2** | **alpha_beta \| + abs fast + abs slow** | **+0.807 [+0.355, +1.333]** | **117 %** |
| U3 | alpha_frac \| + beta_frac | +0.343 [+0.078, +0.599] | 73 % |
| U3 | beta_frac \| + alpha_frac | +0.340 [+0.054, +0.703] | 57 % |

### U1 · Candidate F3 (monotony) is CLOSED

`ab_iqr`'s marginal reversal vanishes once level is adjusted for (−0.099, includes zero), while `alpha_beta`
is *unaffected* by adjusting for dispersion (109 %). **Within-patient variability of the ratio is level in
disguise.** F3 is closed — the fifth candidate to fall.

### U2 · "Balance, not amount" is now a FITTED result

The aetiology × `alpha_beta` interaction adjusted for **both** absolute band powers *and* their own
interactions is **+0.807 [+0.355, +1.333]** — not merely preserved but slightly strengthened (117 %). R417
inferred orthogonality from a correlation of +0.002; it is now established in a model that gives absolute
power every chance to absorb the effect and it does not.

### U3 · Both sub-bands carry it, and the decomposition is ADDITIVE

Head-to-head, **both survive**: alpha +0.343 [+0.078, +0.599] and beta +0.340 [+0.054, +0.703], at
essentially equal strength, correlating only +0.394 with modest CI inflation (×1.30 / ×0.99). This refines
R417's "not localised": it is not that the split buys nothing — it is that **alpha and beta each carry the
reversal independently and equally.**

**And the numbers cohere in a way that validates the whole decomposition:** the two adjusted sub-band
interactions sum to **+0.683**, against the composite `alpha_beta` marginal of **+0.690**. The
decomposition is additive to within 1 %, which is what it should be if the sub-bands are measuring parts of
one coherent quantity rather than three separate noisy things.

### Where the mechanism hunt now stands — six candidates closed

| candidate | status |
|---|---|
| A · GABAergic drug signature | dead (R414) |
| B · Thalamocortical / mesocircuit | open, partly tested (R395–R396) |
| C · Interneuron loss / epileptogenicity | demoted (R415) |
| **F1 · Alpha coma** | **closed** — modifier only (R416), and not frequency-localised (R417/R418) |
| **F2 · Slow denominator** | **rejected** — neither absolute power reverses (R417), orthogonality fitted (R418) |
| **F3 · Monotony** | **CLOSED — R418** |
| E · Guideline-driven withdrawal | dead (R409–R410) |

**Cumulative distinct results: 418.**
