# Wang Transform (oracle3) as a longshot-SELECTION overlay -- strict OOS on our short-vol data

_Generated 2026-07-18T15:31:22.956211+00:00_

**Universe:** 1804 qualifying settled weekly BTC/ETH longshot markets (executable in-band first-half YES-buy fills in [0.15,0.3]) across 49 resolution-weeks. Confirmed blanket edge (reference, trade_flow_hist): 0.0589/ct, week-clustered t=2.376, k=49.

## The model & the covariate-label caveat

Wang: `p_true = Phi(Phi^-1(p_mkt) - lambda)`, `EDGE_SIGNAL = p_mkt - p_true` (sell the top). Published hierarchical lambda = 0.259 -0.0716*ln(1+V) + 0.1431*ln(1+D) -0.4772*|p-0.5|. **Caveat:** repo covariate #3 is ln(DURATION); task labeled it dispute-rate D. We run both. We report the task-literal D=0 version, a duration-faithful version, the crypto constant lambda=0.253, and a walk-forward MLE recalibration on our data.

## Degeneracy diagnostic (does the signal just reproduce something?)

- corr(EDGE_SIGNAL_pub, price) = **-0.1352**, corr(EDGE_SIGNAL_pub, ln V) = **-0.993**, corr(price, ln V) = 0.04.

- Published lambda mean **-0.4681** (range [-0.7489, 0.0384]) -- driven NEGATIVE by the ln(1+V) term at our volume scale; published p_true mean **0.3783** > price 0.2192 >> realized 0.1425 (mis-signed).

- Recalibrated OOS signal: corr(signal, price)=-0.5603, corr(signal, ln V)=-0.0281.

- **Published-coeff signal collapses to a VOLUME sort: corr(EDGE_SIGNAL, ln V)=-0.993, corr(EDGE_SIGNAL, price)=-0.1352. At our volume scale the -0.0716*ln(1+V) term dominates, driving lambda NEGATIVE (mean -0.4681, range [-0.7489,0.0384]) so published p_true (mean 0.3783) sits ABOVE price (0.2192) and FAR above the realized rate (0.1425). It does NOT reproduce price (unlike Deribit density), it degenerates to ranking by low volume.**

## Brier calibration (Wang p_true vs market price against realized 0/1)

| predictor | Brier |
|---|---|

| price | 0.12306 |

| wang_pub_D0 | 0.17438 |

| wang_pub_dur | 0.13571 |

| wang_crypto_const | 0.11797 |

| wang_recal_oos | 0.10688 |

| price_on_oos_subset | 0.11297 |


Brier: price=0.12306, Wang-published(D=0)=0.17438 (WORSE), Wang-duration=0.13571, Wang-crypto-const(0.253)=0.11797, Wang-recal-OOS=0.10688 vs price-on-subset=0.11297. Only a CONSTANT crypto lambda improves calibration (unconditional premium); the hierarchical covariates do not.

## Incremental predictive power: outcome ~ p + EDGE_SIGNAL (week-cluster-robust)

| variant | signal coef | cluster t | p | n | k |
|---|---|---|---|---|---|

| published D=0 | 0.0435 | 0.202 | 0.8396 | 1804 | 49 |

| published duration | 0.0117 | 0.045 | 0.9639 | 1804 | 49 |

| recalibrated OOS | 0.3653 | 0.775 | 0.4384 | 1596 | 41 |


Incremental power outcome~p+signal (week-clustered): published D=0 signal coef=0.043 (t=0.20, p=0.840); recal-OOS signal coef=0.365 (t=0.77, p=0.438). Bonferroni bar |t|>2.638 for 6 tests.

## DECISIVE selection test: top-quartile-signal vs blanket band vs bottom-quartile (seller PnL/ct)

| variant | top edge (t) | blanket edge (t) | bottom edge (t) | top-minus-blanket (t) | top-Sharpe/wk |

|---|---|---|---|---|---|

| published D=0 | 0.0552 (1.754) | 0.0589 (2.376) | 0.0455 (1.608) | **-0.0036 (-0.235)** | 0.251 |

| published duration | 0.0555 (1.702) | 0.0589 (2.376) | 0.0547 (1.827) | **-0.0034 (-0.213)** | 0.243 |

| recalibrated OOS | 0.0983 (5.514) | 0.0825 (4.007) | 0.0225 (0.608) | **0.0158 (1.144)** | 0.861 |


SELECTION (published D=0): top-quartile-signal edge=0.0552/ct (t=1.754), blanket=0.0589/ct (t=2.376), bottom=0.0455/ct (t=1.608); paired top-minus-blanket=-0.0036/ct (week-clustered t=-0.235). Recalibrated OOS: top=0.0983/ct (t=5.514), blanket=0.0825/ct, top-minus-blanket=0.0158/ct (t=1.144).

## Multiple testing

- Decisive family size = **6** (3 top-vs-blanket + 3 incremental-signal). Bonferroni alpha=0.0083 -> survive bar **|t| > 2.638**.

## BLUNT VERDICT

- **Degeneracy:** Published-coeff signal collapses to a VOLUME sort: corr(EDGE_SIGNAL, ln V)=-0.993, corr(EDGE_SIGNAL, price)=-0.1352. At our volume scale the -0.0716*ln(1+V) term dominates, driving lambda NEGATIVE (mean -0.4681, range [-0.7489,0.0384]) so published p_true (mean 0.3783) sits ABOVE price (0.2192) and FAR above the realized rate (0.1425). It does NOT reproduce price (unlike Deribit density), it degenerates to ranking by low volume.

- **Calibration (Brier):** Brier: price=0.12306, Wang-published(D=0)=0.17438 (WORSE), Wang-duration=0.13571, Wang-crypto-const(0.253)=0.11797, Wang-recal-OOS=0.10688 vs price-on-subset=0.11297. Only a CONSTANT crypto lambda improves calibration (unconditional premium); the hierarchical covariates do not.

- **Incremental signal:** Incremental power outcome~p+signal (week-clustered): published D=0 signal coef=0.043 (t=0.20, p=0.840); recal-OOS signal coef=0.365 (t=0.77, p=0.438). Bonferroni bar |t|>2.638 for 6 tests.

- **Selection:** SELECTION (published D=0): top-quartile-signal edge=0.0552/ct (t=1.754), blanket=0.0589/ct (t=2.376), bottom=0.0455/ct (t=1.608); paired top-minus-blanket=-0.0036/ct (week-clustered t=-0.235). Recalibrated OOS: top=0.0983/ct (t=5.514), blanket=0.0825/ct, top-minus-blanket=0.0158/ct (t=1.144).

- **Bottom line:** NULL / NO IMPROVEMENT. The Wang Transform does NOT sharpen the confirmed short-vol edge OOS. Neither the published-coeff overlay nor the walk-forward-recalibrated overlay produces a top-quartile seller edge that beats the blanket [0.15,0.30] band by a margin surviving the week-clustered, Bonferroni-haircut bar (|t|>2.638). Published top-minus-blanket=-0.0036/ct (t=-0.235); recalibrated top-minus-blanket=0.0158/ct (t=1.144). This is the 4th consecutive SELECTION null: the ~0.06/ct premium is essentially unconditional, and the principled Wang covariates add no per-trade EV once the volume-driven degeneracy is accounted for.
