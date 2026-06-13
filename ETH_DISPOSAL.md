# ETH UNPAIRED-LEG DISPOSAL LADDER (R3 complete / R4 sell / R5 hedge)

Generated 2026-06-13. Data: Kalshi ETH15M + BTC15M parquet tape. ETH windows=2384 (IS=1430 / OOS=954, 60/40 time split). Baseline = always-pair P0 (hold stranded leg to settlement). **SCOPE: disposal of an ALREADY-stranded ETH leg only** -- entry prevention/prediction is a separate agent's job. **Backtests SCREEN, they do not confirm; forward-validation (n>=300, t_vs_live>3) required before any rung is promoted.**

## TL;DR verdict

- **The unpaired leg is the dominant ETH loss.** Naked P0 loses -11.37c/win; the strand leg alone contributes -3.61c/win (~32% of total loss). Strand rate 41%/window; strand mean settle -8.87c (95% negative, p5 -38c). Completed boxes lock ~-1.1c/box -- the leak is the strand, exactly as the operator's thesis predicted.
- **R3/R4 FLATTEN (sell the stranded leg at the touch) is the ONLY robust ETH disposal rung.** It recovers **+0.91c/win OOS** (paired t=+3.87, IR_vs_P0 +0.125), stable IS->OOS (+0.96c IS / +0.91c OOS).
- **ETH's sell cut is NOT 0.30 -- it is SELL-ALL.** Unlike BTC (where only cheap <0.30 longshots should be sold and favorites held), on ETH EVERY price bucket benefits from flattening (favorites included). ETH favorites do not mean-revert into wins the way BTC's do, so the ETH-tuned rule is **flatten-all, no price gate**.
- **HEADLINE -- the ETH strand is NOT well hedgeable by BTC.** The cross-asset basis is the MIRROR of the established ETH-hedges-BTC finding, and it is **much WORSE**: regressing ETH-strand directional P&L on the concurrent BTC 15-min move gives **R^2=4.1% / |corr|=0.20** (vs the symmetric 18.6% / 0.43). OLS std-reduction only 2.1%, and **coverage is only 22%** (most ETH windows have no concurrent BTC window on this tape). BTC is a POOR hedge for ETH strands.
- **ETH-perp at scale is near-useless too** (std-reduction ~0.2-0.4% even at proper integer ratio): a 15-min ETH strand is almost pure idiosyncratic Bernoulli noise that a spot delta-hedge cannot offset. The deployable disposal is FLATTEN, not hedge.
- **Disposal alone does NOT make the wide ETH box profitable.** Best stack moves OOS net -13.15c -> -12.24c -- still deeply negative. Flattening recovers only ~25% of the strand cost and the completed boxes still lose. **Entry-side prevention (the other agent's edge-select / fav-avoid / k-slot gating) is REQUIRED to harvest the wide boxes; disposal is a loss-mitigation back-stop, not the harvest.**

## TASK 1 -- Baseline ETH strand cost & characterization

| level | net c/win | n | strand% | win% | t |
|---|---|---|---|---|---|
| P0 ALL | -11.37 | 2384 | 40.7% | 33.3% | -21.42 |
| P0 IS  | -10.18 | 1430 | 42.4% | 34.2% | -15.00 |
| P0 OOS | -13.15 | 954 | 38.1% | 31.9% | -15.50 |

- **Strand cost = -3.61c/win** (= sum of stranded-leg settle / N windows), ~32% of the -11.37c/win total P0 loss.
- Stranded leg held naked: mean -8.87c, std 20.26c, 95% negative, p5 -38c, median -6c (970 strands; 363 OOS).
- Side split is BALANCED (unlike BTC's YES-heavy strands): YES 476 (mean -9.04c) vs NO 494 (mean -8.71c).
- **By slot:** strands are LATE-slot-heavy -- 59% at k>9 (mean -9.7c), 39% mid k5-9 (-7.2c, the least-bad), 2% early. The late slot is where ETH legs fail to pair (thin end-of-window flow).
- **By price region:** bimodal -- 41% deep longshots <0.20 (mean -6.2c) and 44% deep favorites >0.80 (mean -5.3c); the worst-per-strand are the rare mid-price 0.40-0.60 (n=22, -39c) and cheap 0.20-0.40 (n=74, -27c) strands. The mass is in the tails; the per-leg pain is in the middle.

## TASK 2 -- R3 COMPLETE (chase/flatten the stranded leg)

On BTC, force-completing from the strand minute was optimal. On ETH the deployable proxy is FLATTEN-at-touch (the framework's `exit` field = crossing the spread ~1 min later). Giving up edge to chase (`give`) is strictly worse:

| give (c) | strand mean | strand std | recover vs naked |
|---|---|---|---|
| 0.0 | -6.56c | 14.03c | +2.32c |
| 0.5 | -7.06c | 14.03c | +1.82c |
| 1.0 | -7.56c | 14.03c | +1.32c |
| 2.0 | -8.56c | 14.03c | +0.32c |
| 3.0 | -9.56c | 14.03c | -0.68c |

- COMPLETE(give=0, flatten) window OOS: net -12.24c (Δ+0.91c vs P0), IS net -9.21c (Δ+0.96c). **Stable and positive both halves.**
- Flatten cuts strand std 20.3c -> 14.0c (a 31% variance cut) AND lifts mean +2.3c -- prompt disposal removes the tail. Paying to chase (`give>0`) erodes that 1:1; **don't chase, flatten passively at the touch.**

## TASK 3 -- R4 SELL/MANAGE (ETH-tuned price threshold)

Price-threshold sweep (sell if YES-equiv price < thr, else hold). **BTC's 0.30 cut is WRONG for ETH** -- the strand-pool mean keeps improving all the way to SELL-ALL:

| sell-below thr | strand mean | strand std | Δ vs naked |
|---|---|---|---|
| 0.20 | -8.22c | 19.40c | +0.66c |
| 0.25 | -7.99c | 18.87c | +0.89c |
| 0.30 | -7.78c | 18.57c | +1.09c |
| 0.35 | -7.77c | 18.42c | +1.11c |
| 0.40 | -7.66c | 17.97c | +1.21c |
| 0.50 | -7.57c | 17.63c | +1.30c |
| **ALL (sell-all)** | **-6.56c** | **14.03c** | **+2.32c** |

**Hold-vs-sell by price bucket -- selling helps in EVERY bucket on ETH:**

| bucket | n | hold mean | sell mean | Δ(sell-hold) |
|---|---|---|---|---|
| deep longshot <0.20 | 398 | -6.18c | -4.57c | +1.60c |
| cheap 0.20-0.40 | 74 | -26.85c | -19.61c | +7.24c |
| mid 0.40-0.60 | 19 | -38.11c | -27.34c | +10.77c |
| fav 0.60-0.80 | 52 | -23.48c | -18.82c | +4.66c |
| deep fav >0.80 | 427 | -5.19c | -3.72c | +1.47c |

- **Key ETH-specific finding:** on BTC, expensive/favorite strands should be HELD (they tend to win); on ETH **even the favorites are better SOLD** (+1.5c) -- ETH's edge structure is inverted, so a deep-favorite ETH strand that failed to pair is more likely a stale/adverse leg than a winning one. The ETH-tuned rule: **flatten-all, no price gate** (`cheap_below=None`).
- Tox-conditioned exits are WEAKER than flatten-all: tox>0.45 gives +2.20c (close), tox>0.55 +1.50c, vpin>0.40 +1.36c -- all below sell-all's +2.32c. The toxicity filter leaves too many losing strands un-sold. **Unconditional flatten dominates on ETH.**

## TASK 4 -- R5 HEDGE (the headline): is the ETH strand hedgeable?

### (a) Cross-asset BTC hedge -- the MIRROR of the 18.6% symmetric finding

Rule: ETH YES-strand -> buy BTC-NO; ETH NO-strand -> buy BTC-YES. Regress ETH-strand directional P&L on the concurrent BTC 15-min % move (signed to the strand's directional sense):

| direction | n_cov | \|corr\| | R^2 | OLS std-red | naked std -> hedged std |
|---|---|---|---|---|---|
| BTC hedges ETH (THIS) ALL | 210 | 0.20 | 4.1% | 2.1% | 18.4c -> 18.0c |
| BTC hedges ETH (THIS) OOS | 207 | 0.21 | 4.5% | 2.3% | -- |
| ETH hedges BTC (established) | -- | ~0.43 | 18.6% | ~10% | -- |

- **The basis is ASYMMETRIC and the ETH-strand direction is the WEAK one: R^2=4.1% / |corr|=0.20, roughly a QUARTER of the symmetric 18.6% / 0.43.** A delta-matched (beta) hedge cuts strand std only 2.1% (18.4c -> 18.0c). The delta-matched binary overlay's best config (n_ct=1 tkr k_cut=10 gap=sellcheap) reaches std-red +6.5% on the strand pool (driven mostly by the sellcheap gap-handler, not the BTC leg itself).
- Window-level: BTC-hedge OOS net -12.57c (Δ+0.58c vs P0) -- BELOW flatten-all. The BTC binary adds a lumpy second directional bet more than it hedges.
- **Why the asymmetry?** ETH 15-min strands are dominated by ETH-idiosyncratic moves (the tails: 41% deep-longshot, 44% deep-favorite legs are ETH-specific microstructure failures, not co-moves). BTC's broad-market beta explains little of ETH's residual. The reverse (ETH explaining BTC) was stronger because BTC strands were more co-move-driven. **BTC is a worse hedge for ETH than ETH is for BTC.**

### (c) Coverage

- Concurrent-window coverage for the BTC hedge is only **210/970 = 22%** -- on this tape most ETH windows have no BTC 15-min window within 450s (the ETH tape spans ~2.6x more windows than BTC). Even if the basis were strong, the BTC hedge is unavailable for ~78% of ETH strands. The gap falls back to FLATTEN (COMPLETE/MANAGE), which is the load-bearing rung anyway.

### (b) ETH-perp delta-hedge at scale (integer-contract lumpy, $6 min)

| box_ct | box $ | n_perp | over/under | strand std | std-red |
|---|---|---|---|---|---|
| 1 | $5 | 0 | no hedge | 20.26c | +0.0% |
| 3 | $15 | 1 | 2.00x | 20.18c | +0.4% |
| 4 | $20 | 1 | 1.50x | 20.20c | +0.3% |
| 6 | $30 | 1 | 1.00x | 20.22c | +0.2% |
| 12 | $60 | 2 | 1.00x | 20.22c | +0.2% |
| 50 | $250 | 8 | 0.96x | 20.22c | +0.2% |

- The $6 perp min gives NO hedge below box_ct=3 (round($1/$6)=0). The scale threshold for a proper 0.6-1.6x integer ratio is box_ct>=4 (~$20/window), **but even at scale the std-reduction is only ~0.2-0.4%** -- a delta-neutral ETH-perp does NOT meaningfully hedge a 15-min ETH binary strand. (The smooth over-hedge would look better only by capturing in-sample drift = a directional bet, not a hedge.) **Not worth deploying at any scale for this purpose.**

## TASK 5 -- Best ETH disposal stack & net effect on the box

| variant | IS net | OOS net | ΔOOS vs P0 | OOS t | IR_vs_P0 | OOS Sharpe |
|---|---|---|---|---|---|---|
| naked P0 (hold to settle) | -10.18c | -13.15c | +0.00c | -15.50 | -- | -0.502 |
| **FLATTEN-ALL (best stack)** | **-9.21c** | **-12.24c** | **+0.91c** | -15.22 | +0.125 | -0.493 |
| flatten + BTC-hedge overlay | -10.16c | -12.71c | +0.44c | -15.21 | +0.094 | -0.492 |

**Exact ETH-tuned disposal params (deployable now):**
- `pol_sell_unpaired(F, cheap_below=None)` -- **SELL-ALL** (flatten every stranded ETH leg at the touch; NO price gate, NO tox gate). This is the ETH-tuned R3/R4: COMPLETE and MANAGE collapse to the same passive flatten on this tape.
- **Do NOT chase** (give=0): paying urgency erodes recovery 1:1.
- **Do NOT hold favorites** (ETH inversion vs BTC): even >0.80 strands are +1.5c better sold.
- **Do NOT add the BTC binary hedge or ETH-perp** as a strand disposal: R^2 4.1%, 22% coverage, <0.4% perp std-red -- both underperform plain flatten.

### Net effect on ETH box profitability (honest)

- Best disposal stack moves OOS net **-13.15c -> -12.24c** (+0.91c/win, paired t=+3.87; IS +0.96c -- stable).
- That recovers only ~25% of the -3.61c/win strand cost and ~7% of total loss. **The box is still deeply negative after the best possible disposal.**
- **VERDICT:** Disposal works (flatten-all is real, +0.9c/win OOS, t>3) but it is a LOSS-MITIGATION back-stop, not the harvest. The completed boxes themselves lose (-1.1c/box) and the strand mass is huge (40%/window). **Cutting the unpaired leg via disposal alone does NOT move the wide ETH box to profitable.** To harvest the wide boxes you MUST gate ENTRY (the other agent's edge-select: mid-slot k5-9 / non-favorite / mid-vol windows, plus fav-avoidance and t36) to (i) stop opening the legs that strand, and (ii) stop entering the negative-margin completed boxes. **Disposal + entry-prevention are complementary; disposal is the residual back-stop on the ~strands that survive the entry gate.**

### Forward validation
- These are SCREENING backtests on a 45-day tape. The flatten-all rung clears t>3 OOS on this screen but must be A/B'd forward (n>=300 windows, t_vs_live>3) before promotion. The hedge negatives are robust enough (R^2 4%, 22% coverage) to DROP without forward test.

*https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz*
