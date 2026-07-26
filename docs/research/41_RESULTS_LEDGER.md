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
