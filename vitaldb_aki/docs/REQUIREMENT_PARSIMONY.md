# Is the stable-epoch dose-REQUIREMENT machinery NECESSARY? (parsimony + expansion)

Two stress-tests of the stable-epoch norepinephrine dose-requirement phenotype (docs/PRESSOR_REQUIREMENT.md). **A:** does a SIMPLER pressor metric off the same epochs match it? **B:** can norepinephrine-equivalents expand N beyond the norepi-only cohort?

**OVERALL VERDICT: MACHINERY NOT CLEARLY NECESSARY; EXPANSION HOLDS (assumption-laden -- see caveat)**

## A. Necessity -- phenotype vs simpler metrics
- Norepi-only NEPI epochs: **474** over **75** cases; cases with the target-band phenotype: **52**.

| metric | split-half reliability (n) | spread p90/p10 (n) | construct vs EV1000 SVR rho (n) | early->late rho (n) |
|---|---|---|---|---|
| **stable-epoch REQUIREMENT (median target-band dose/kg)** | 0.81 (41) | 5.6 (52) | 0.182 (15) | 0.482 (39) |
| peak dose/kg | 0.79 (52) | 8.9 (75) | 0.279 (16) | 0.622 (52) |
| total exposure sum(dose*dur) | 0.725 (52) | 17.8 (75) | 0.044 (16) | 0.566 (52) |
| time-weighted mean dose/kg | 0.798 (52) | 7.98 (75) | 0.385 (16) | 0.49 (52) |
| fraction target-band time | n/a | 7.61 (75) | -0.344 (16) | n/a |

Construct sign: a real vasoplegia REQUIREMENT should correlate **NEGATIVELY** with EV1000 SVR (low systemic tone -> needs more pressor).

**How much do the simpler metrics just reproduce the phenotype?** (Spearman vs phenotype)
- peak dose/kg: rho = 0.875 (n=52)
- total exposure sum(dose*dur): rho = 0.604 (n=52)
- time-weighted mean dose/kg: rho = 0.899 (n=52)
- fraction target-band time: rho = 0.378 (n=52)

### Verdict A
- **Machinery needed: False**
- phenotype: reliability 0.81, spread 5.6x, construct vs SVR 0.182, early->late 0.482
- best simpler metric: reliability 0.798, early->late 0.622, most-negative construct -0.344
- near-perfect proxies (rho>=0.85): ['peak', 'twm']
- phenotype reliability 0.81 is at/above the best simpler metric (0.798)
- simpler metric(s) ['peak', 'twm'] reproduce the phenotype (rho>=0.85) AND it has no construct edge -- machinery NOT necessary

## B. Norepinephrine-equivalents to expand N
> **CONCENTRATION CAVEAT (prominent):** Orchestra RATE is a DEVICE rate (mL/h), not ug/kg/min -- VitalDB does not expose per-case concentration. The norepi phenotype already assumes a standard institutional norepi concentration *between patients*. NEE conversion STACKS a second assumption: a standard mL/h->dose mapping for EACH drug AND a fixed cross-drug potency ratio. Ratios used are approximate, Goradia/Brown-style institutional norepinephrine-equivalents. **Expanded-cohort numbers are HYPOTHESIS-GENERATING ONLY.**

NEE ratios used (norepi-equivalent per device-dose/kg): {'NEPI': 1.0, 'PHEN': 0.1, 'DOPA': 0.01}. phenylephrine ~1/10 norepi; dopamine norepi-equiv = dopa/100; VASO excluded (vasopressin units are not dose-comparable).

| cohort | N (phenotype cases) | epochs | spread p90/p10 | split-half reliability | early->late rho |
|---|---|---|---|---|---|
| NEPI-only (NEE=identity) | 52 | 474 | 5.6 | 0.81 (n=41) | 0.482 (n=39) |
| NEPI+PHEN+DOPA norepi-equivalent | 154 | 1371 | 67.98 | 0.909 (n=118) | 0.769 (n=113) |

- Phenotype-case N gain from expansion: **+102** (52 -> 154).
- Drug composition of expanded phenotype cases: {'PHEN': 81, 'DOPA': 21, 'NEPI': 51, 'NEPI,PHEN': 1}
- **Expansion holds (reliability>=0.4, spread>=3x, early->late>=0.3): True**
- Reliability/spread/early->late SURVIVE the NEE pooling at the larger N -- but this could partly reflect the (assumption-laden) conversion creating apparent between-patient spread. Do NOT report expanded numbers as confirmatory.
- **RED FLAG:** the expanded spread (67.98x) is far larger than the norepi-only spread (5.6x). The 10x/100x cross-drug NEE ratios place PHEN- and DOPA-dominant patients in fixed lower bands BY CONSTRUCTION, so much of the inflated spread (and the higher split-half/early-late) is DRUG IDENTITY masquerading as a requirement trait, not new physiologic signal. The expanded N is real; the apparent improvement is largely an artefact of the conversion. Trust the norepi-only cohort for effect sizes.

