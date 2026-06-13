# Box-Yield FRONTIER (Phase 1, GAIN side)

**Objective.** TOTAL PnL = (#boxes filled) x (avg locked edge/box) - strand losses. A box = YES leg + NO leg both filled. With crypto15m fee=0 the realized box edge is res-independent: settle_yes + settle_no = (res-b0)+(a0-res) = a0 - b0, i.e. pure spread capture (verified res-cancels within a window). We measure the REALIZED locked edge per box (settle sum), which equals 1-cost_yes-cost_no only when both legs fill contemporaneously; when they fill at non-contemporaneous prices the gap IS the within-pairing adverse-selection drag. Higher lock floor => fatter but rarer boxes; wider band => more fills, thinner margin, more strands. We map the (price-region x lock-floor) frontier.

IS = first 60% of windows, OOS = last 40%. Backtests SCREEN only; forward-validate on the live collector before any deploy.


## BTC -- Task 1: Baseline box yield (OOS)

| policy | #box/win | avg lock c/box | locked c/win | P(both fill) | strand% | net c/win | Sharpe | t |
|---|---|---|---|---|---|---|---|---|
| P0 always-pair | 9.18 | 0.457 | 4.192 | 0.877 | 12.26 | +3.08 | +0.204 | +3.91 |
| live t36+complete | 6.11 | 0.551 | 3.367 | 0.619 | 38.15 | +3.12 | +0.100 | +1.91 |

IS net: P0=+0.49c, live=+2.71c.


## BTC -- Task 2: Price-region map (live boxes, OOS)

Region = favorite-leg YES-equiv price (fav = max of the two legs' YES-equiv prices).

| region | #box | #box/win | avg lock c/box | locked c/win |
|---|---|---|---|---|
| deep-fav  >0.70 | 717 | 1.954 | -1.716 | -3.352 |
| mid 0.60-0.70 | 243 | 0.662 | 0.194 | 0.128 |
| balanced 0.50-0.60 | 265 | 0.722 | 1.306 | 0.943 |

## BTC -- Task 3: Lock-margin floor sweep (OOS)

Gate: open a leg only if book spread >= X (X = implied two-sided lock floor). AdvSelEdge col = locked c/win - net c/win = strand drag (Glosten-Milgrom adverse-selection cost).

| X (c) | #box/win | avg lock c/box | locked c/win | strand% | net c/win | Sharpe | t | strand drag c |
|---|---|---|---|---|---|---|---|---|
| 0 | 9.18 | 0.457 | 4.192 | 12.26 | +3.08 | +0.204 | +3.91 | +1.116 |
| 1 | 7.80 | 0.494 | 3.849 | 4.90 | +2.97 | +0.205 | +3.93 | +0.881 |
| 2 | 0.94 | 0.680 | 0.641 | 0.54 | +0.30 | +0.040 | +0.76 | +0.343 |
| 3 | 0.05 | 3.100 | 0.169 | 0.00 | +0.17 | +0.123 | +2.35 | +0.000 |
| 4 | 0.00 | 20.000 | 0.054 | 0.00 | +0.05 | +0.052 | +1.00 | +0.000 |
| 5 | 0.00 | 20.000 | 0.054 | 0.00 | +0.05 | +0.052 | +1.00 | +0.000 |

**Frontier optimum:** max NET at X=0c (net +3.08c, Sharpe +0.204); max Sharpe at X=1c (net +2.97c, Sharpe +0.205).


## BTC -- Task 4: Joint optimum (region x floor)

Region band = |p_yeq - 0.5| of the OPENING leg (decision-time observable).

- **Best by net:** band `any`, floor X=0c -> net +3.08c/win, Sharpe +0.204, #box/win 9.18, strand 12.3%. Paired vs live: Δ=-0.05c/win, t=-0.03.
- **Best by Sharpe:** band `|p-.5|>.20 (skewed)`, floor X=1c -> net +2.63c/win, Sharpe +0.266. Paired vs live: Δ=-0.50c/win, t=-0.31.


## ETH -- Task 1: Baseline box yield (OOS)

| policy | #box/win | avg lock c/box | locked c/win | P(both fill) | strand% | net c/win | Sharpe | t |
|---|---|---|---|---|---|---|---|---|
| P0 always-pair | 6.98 | -1.430 | -9.988 | 0.619 | 38.05 | -12.86 | -0.504 | -15.57 |
| live t36+complete | 5.75 | -1.459 | -8.383 | 0.630 | 37.00 | -10.48 | -0.393 | -12.14 |

IS net: P0=-9.63c, live=-7.98c.


## ETH -- Task 2: Price-region map (live boxes, OOS)

Region = favorite-leg YES-equiv price (fav = max of the two legs' YES-equiv prices).

| region | #box | #box/win | avg lock c/box | locked c/win |
|---|---|---|---|---|
| deep-fav  >0.70 | 1808 | 1.895 | -2.987 | -5.662 |
| mid 0.60-0.70 | 591 | 0.619 | -2.633 | -1.631 |
| balanced 0.50-0.60 | 563 | 0.590 | -2.237 | -1.320 |

## ETH -- Task 3: Lock-margin floor sweep (OOS)

Gate: open a leg only if book spread >= X (X = implied two-sided lock floor). AdvSelEdge col = locked c/win - net c/win = strand drag (Glosten-Milgrom adverse-selection cost).

| X (c) | #box/win | avg lock c/box | locked c/win | strand% | net c/win | Sharpe | t | strand drag c |
|---|---|---|---|---|---|---|---|---|
| 0 | 6.98 | -1.430 | -9.988 | 38.05 | -12.86 | -0.504 | -15.57 | +2.875 |
| 1 | 6.42 | -1.530 | -9.827 | 29.14 | -12.44 | -0.504 | -15.55 | +2.613 |
| 2 | 4.09 | -1.652 | -6.758 | 13.94 | -8.25 | -0.385 | -11.88 | +1.488 |
| 3 | 2.29 | -1.776 | -4.067 | 8.39 | -5.08 | -0.275 | -8.49 | +1.012 |
| 4 | 0.85 | -1.977 | -1.672 | 3.04 | -2.30 | -0.181 | -5.58 | +0.630 |
| 5 | 0.15 | -1.262 | -0.194 | 0.94 | -0.42 | -0.071 | -2.19 | +0.221 |

**Frontier optimum:** max NET at X=5c (net -0.42c, Sharpe -0.071); max Sharpe at X=5c (net -0.42c, Sharpe -0.071).


## ETH -- Task 4: Joint optimum (region x floor)

Region band = |p_yeq - 0.5| of the OPENING leg (decision-time observable).

- **Best by net:** band `|p-.5|>.20 (skewed)`, floor X=5c -> net -0.02c/win, Sharpe -0.006, #box/win 0.07, strand 0.5%. Paired vs live: Δ=+10.46c/win, t=+12.09.
- **Best by Sharpe:** band `|p-.5|>.20 (skewed)`, floor X=5c -> net -0.02c/win, Sharpe -0.006. Paired vs live: Δ=+10.46c/win, t=+12.09.


## Verdict

- **Box payoff is res-independent spread capture** (lock = a0 - b0). The mean BTC box locks ~0.55c at ~6.11 boxes/win under the live t36 gate, P(both fill)=0.619.
- **Where profit is made:** the price-region map shows the bulk of locked-edge throughput comes from the high-frequency near-balanced/mid bands, not the rare fat-margin tails (thin-but-frequent > fat-but-rare).
- **Lock-floor frontier:** spread is ~1c on most fills (median book), so raising the implied lock floor X above 1-2c rapidly starves fills; net throughput peaks at a LOW floor.
- **Adverse selection is REAL and priced in the regions:** deep-favorite boxes (favorite leg >0.70) LOSE on BTC (-1.72c/box) -- when you get filled on both legs of a skewed book it is usually because the price was running and one leg pre-pays the move (Glosten-Milgrom). The positive locked edge lives in the balanced 0.50-0.60 band (+1.31c/box). Net edge per box = gross spread - expected strand/adverse cost.
- **Joint by-NET optimum (BTC):** band `any` x X=0c, net +3.08c/win vs live +3.12c/win (Δ=-0.05c, t=-0.03) -- a tie (degenerate = P0).
- **Joint by-SHARPE optimum (BTC):** band `|p-.5|>.20 (skewed)` x X=1c more than DOUBLES Sharpe (+0.100->+0.266) at net +2.63c/win (Δ=-0.50c, t=-0.31). The PnL difference is not t-significant, but the risk reduction (Sharpe) is the real, defensible marginal gain -- worth a forward A/B.
- **HONEST READ:** the live t36+complete policy is already at/near the box-yield frontier on raw net. No (region,floor) cell beats live net with |t|>=2. The structural fee=0 spread is ~1c, so raising the lock floor above 1-2c starves fills (#box/win collapses 7.8->0.9 from X=1c->2c) and widening admits strands -- the frontier is FLAT then DECLINING. The only defensible Phase-1 lever is the SHARPE-improving skewed-band + 1c floor (volume-neutral risk trim), and even that needs forward validation. The bulk of available PnL improvement is on the LOSS/strand side, already studied.
- **ETH is structurally unprofitable on the box** (negative net at every (region,floor) cell; only X=5c -> ~0 by ceasing to trade). Do not run the box on ETH; the +12c 'gain' vs live there is just not-trading. BTC-only.

### IS/OOS stability

- BTC live: IS net +2.71c -> OOS net +3.12c (stable, same sign). P0: IS +0.49c -> OOS +3.08c.
- The floor-sweep shape (net peaks at low X, collapses above ~2c) is monotone and not a knife-edge -- robust to the IS/OOS split. ETH stays negative IS and OOS.

### Exact entry rule (screened SHARPE candidate -- the only defensible Phase-1 change)

```
OPEN a leg iff:  _live_open_ok(f)            # keep live t36 guard
             AND spread(f) >= 0.01         # 1c implied two-sided lock floor
             AND |p_yeq(f) - 0.5| > 0.20    # skewed-band opening leg only
PAIR always (never gate the completing leg).
STRAND: sell-cheap if p_yeq<0.30 else hold (live R3+complete).
ASSET: BTC only (ETH box is -EV).
```

### Trader-flag sketch

```
--lock-floor 0.01        # min book spread (=implied 2-sided lock) to open a leg
--open-band skewed     # |p_yeq-0.5|>0.20 region filter on the opening leg
--box-asset btc        # disable box on ETH (-EV)
```

*Backtests SCREEN; these are in-sample-on-OOS screens, not live-validated. Run the live collector A/B (2-sigma alert + pre-registered deploy bar) before arming any flag.*
