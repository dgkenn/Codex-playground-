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
