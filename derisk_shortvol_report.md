# DE-RISKING the weekly crypto SHORT-VOL longshot edge -- defined-risk vertical spreads

_Question: can the confirmed naked short-vol edge (+0.12/ct, brutal left tail) be turned into a positive-EV, bounded-tail sleeve by buying a far-OTM wing as insurance -- and at what EV cost?_

## Method (one paragraph)

On each weekly BTC/ETH strike ladder, SELL YES(above X) with executable in-band ask p_s in [0.15,0.30] (the confirmed short) and BUY YES(above Y>X) as tail insurance, PAYING the executable ask p_b (the far wing is itself a longshot, so we pay up). Both legs settle 0/1; since Y>X, `PnL = (p_s-p_b) - (out_X - out_Y)`: keep the net credit unless settle lands in the middle band (X,Y) (bounded loss 1-credit), and -- crucially -- the BIG-RALLY tail (settle>Y) that annihilates the naked seller now just KEEPS the credit. Prices are size-weighted YES-buy prints in the first half of each market's life (no lookahead). Capital = max loss/contract; weekly return = sum(PnL)/sum(capital). Week-clustered t over ISO resolution-weeks.

## 1. NAKED BASELINE (recomputed on this sample)

- Positions **1803** over **49** resolution-weeks; position win-rate 0.8575.

- Edge **0.0587/ct**, week-clustered t=**2.366**.

- TAIL: worst week **-70%** of deployed capital (week 2025-W33, mean -0.5166/ct); 5th-pctile week -28%; median week 12.3%; max drawdown -82%. Worst single position -0.85/ct.

## 2. VERTICAL-SPREAD FRONTIER (each row = one hedge structure)

`ceil_c` = buy the nearest higher strike with ask<=c; `nextk_k` = buy the k-th strike up. EV cost of hedge = mean wing ask - realized wing YES-rate (= how overpriced the wing is). worst/p5 week = fully-deployed weekly return on capital.

| structure | n | vert EV/ct | wk t | matched naked EV/ct | hedge EV cost | wing ask->realized | net credit | band-hit | maxloss/pos | worst wk | p5 wk | median wk | maxDD |

|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|

| ceil_0.15 | 1676 | **0.0063** | 0.359 | 0.0731 | 0.0672 | 0.0869->0.0197 | 0.1327 | 0.1175 | 0.9913 | -31% | -26% | 2.5% | -59% |

| ceil_0.12 | 1630 | **0.0012** | 0.055 | 0.0624 | 0.0604 | 0.0745->0.0141 | 0.1448 | 0.1239 | 0.9677 | -63% | -30% | 4.2% | -73% |

| ceil_0.1 | 1559 | **0.0218** | 1.132 | 0.075 | 0.0525 | 0.0634->0.0109 | 0.1557 | 0.1251 | 0.95 | -35% | -26% | 5.5% | -60% |

| ceil_0.08 | 1499 | **0.0228** | 1.115 | 0.0693 | 0.0466 | 0.0539->0.0073 | 0.1653 | 0.1274 | 0.93 | -34% | -25% | 5.5% | -61% |

| ceil_0.06 | 1362 | **0.0284** | 1.303 | 0.0631 | 0.0344 | 0.041->0.0066 | 0.1782 | 0.1307 | 0.9097 | -33% | -27% | 5.7% | -58% |

| ceil_0.04 | 1062 | **0.0356** | 1.414 | 0.0595 | 0.0245 | 0.0283->0.0038 | 0.1908 | 0.1403 | 0.8889 | -47% | -30% | 11.0% | -59% |

| nextk_1 | 1707 | **-0.004** | -0.268 | 0.0723 | 0.0778 | 0.1159->0.0381 | 0.1043 | 0.1025 | 0.9999 | -30% | -21% | 0.7% | -57% |

| nextk_2 | 1501 | **-0.0086** | -0.394 | 0.0554 | 0.0637 | 0.073->0.0093 | 0.1503 | 0.1392 | 0.9983 | -43% | -33% | 1.1% | -84% |

| nextk_3 | 1140 | **-0.0097** | -0.358 | 0.0362 | 0.0473 | 0.0499->0.0026 | 0.1785 | 0.1588 | 0.991 | -51% | -41% | 1.9% | -94% |


_For each structure the matched-naked worst week (same positions, no hedge) is in the JSON; the hedge always lifts the worst week vs its own matched naked._

## 3. BEST VIABLE CONFIG

**No structure clears the strict bar (EV/ct>=+0.03 AND week-t>=2 AND worst week>-25%).** See verdict for why -- the far wing is overpriced enough that protection either guts the EV or the middle-band losses re-introduce a tail.


Best tail-improver regardless of the EV bar: **nextk_1** -- worst week -30% (naked -70%), EV -0.004/ct, t=-0.268.

## 4. CORRELATION-AWARE SIZING (crypto book = ONE bet)

- Mean 36.8 positions/week; per-position return std 0.4511.

- A naive-INDEPENDENT sizer expects weekly-return std ~0.0744 (pos_std/sqrt(N)); the REALIZED weekly std is **0.2227** -- **2.99x larger**.

- Implied effective independent bets **4.1** (not N), implied avg pairwise correlation **0.223**.

- A naive-independent sizer assumes week-std shrinks like 1/sqrt(N); the realized week-std is much larger because crypto longshots move together. Sizing the crypto book as ONE bet (N_eff ~ few, not N) is required -- otherwise Kelly/vol-target sizing oversizes by the understatement factor and the correlated rally still wipes the week.

## 5. PER-WEEK GROSS-CAP FRONTIER

Deploying g% of bankroll per week bounds the worst week to g*|worst fully-deployed week|. Max g keeping worst week > -25%, and the mean weekly return you earn at that cap:

| book | worst fully-deployed wk | mean wk | max gross cap (g) | mean wk return @ g |

|---|--:|--:|--:|--:|

| naked | -70% | 7.43% | 36% | 2.66% |

| ceil_0.15 | -31% | 0.73% | 81% | 0.59% |

| ceil_0.12 | -63% | 0.20% | 40% | 0.08% |

| ceil_0.1 | -35% | 2.58% | 72% | 1.86% |

| ceil_0.08 | -34% | 2.72% | 72% | 1.97% |

| ceil_0.06 | -33% | 3.46% | 75% | 2.60% |

| ceil_0.04 | -47% | 4.39% | 53% | 2.32% |

| nextk_1 | -30% | -0.42% | 84% | -0.36% |

| nextk_2 | -43% | -1.02% | 58% | -0.59% |

| nextk_3 | -51% | -1.23% | 49% | -0.61% |


## 6. Secondary lever: dynamic stop-out / underlying hedge (feasibility only)

- **Dynamic stop-out:** buy back the short YES if its price runs from ~0.20 toward ~0.50 intra-week. Feasible (books are live), but longshot exits are the widest/most adversely-selected fills exactly when you need out, and it converts a defined statistical edge into a path-dependent one; the vertical achieves the same tail cap mechanically without discretionary execution risk. Worth paper-testing, not modeled here.

- **Underlying (perp/spot) hedge:** delta-hedge the short book by buying BTC/ETH when it rallies into the strike zone. Feasible with the perp infra already in this repo, but it re-introduces continuous P&L, funding cost, and basis/settlement (Binance noon candle) mismatch; the vertical hedges the exact same event in the same instrument with no basis. Note only.


## BLUNT VERDICT

- **Mostly NO at the strict bar.** No structure simultaneously holds EV/ct>=+0.03, week-t>=2, and worst week>-25%. The far wing carries the SAME longshot overpricing as the near strike, so buying protection transfers most of the edge to the wing seller.
- **The tradeoff, quantified:** hedge EV cost ranges 0.0245/ct (`ceil_0.04`, wing ask 0.0283 vs realized 0.0038) to 0.0778/ct (`nextk_1`). Cheaper/farther wings preserve more EV but leave a wider middle band (more moderate-move losses); closer wings cap the band but cost more credit. The frontier row that best trades these off is the pick above.
- **Tail is genuinely fixable:** every vertical lifts the worst week vs naked; the best tail-improver `nextk_1` reaches -30% (from -70%). The mechanism is real: the correlated BIG rally that clears every near strike ALSO clears the wings, so the vertical keeps its credit exactly when the naked book blows up.
- **Correlation is the whole game:** the crypto longshot book behaves like ~4.1 independent bets (avg pairwise corr ~0.223), so a naive-independent sizer understates weekly risk by 2.99x. Whatever structure is chosen must be sized as ONE crypto bet, and a per-week gross cap is mandatory belt-and-suspenders.
- **Bottom line:** the vertical does what it is supposed to -- it removes the catastrophic big-rally tail mechanically and in the same instrument (no basis, no discretion). The cost is real EV handed to the overpriced far wing. Whether the residual edge clears your bar depends on the structure; the table above and the best-config line make that call explicitly on this sample.