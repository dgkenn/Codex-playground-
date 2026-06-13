# RUNG 5 (HEDGE) -- at-scale perp + deployable ETH cross-asset. Phase-C optimization.
Generated 2026-06-13. Data: 45-day Kalshi BTC15M + ETH15M parquet tape (367 OOS windows; 136 strands total, strand rate 14.8%/window). Baseline = always-pair P0. Judge vs live_current; forward bar t>3 / n>=300. **Backtests SCREEN, they do not confirm.**
## TL;DR verdict
- **HEDGE is the strongest single ablation lever** (dropping h=150 perp = -0.98c/win OOS, +4.2c CVaR) but that backtest is OPTIMISTIC: it models a smooth proportional hedge the $6 perp-min forbids at unit size.
- **PERP is NOT deployable now and does not become a proper hedge until ~box_ct=4 (~$20/window)** -- the scale where 1 integer $6 perp contract matches a strand's delta within a 0.6-1.6x band. Below that it is an over-hedge (a BTC bet) or no hedge at all.
- **ETH cross-asset binary is the deployable-now 5a hedge** (best config n_ct=1 / maker / k<=10 / gap=hold, coverage 59%) -- but on THIS 136-strand pool it did NOT reduce variance (std_red -12.1%), contradicting the established ~10%. The ETH binary's lumpy $0/$1 payout behaves like a 2nd directional bet on a small pool. Keep as a candidate; forward-validate before trusting the std-reduction.
- **Cross-strike is the modeled winner (~88% corr) but DATA-BLOCKED** -- KXBTC15M is single-strike, so it needs the DAILY-ladder adjacent-strike books collected (spec below).
- **Honest take:** hedging caps the residual-strand tail but does not fix the root cause. PREVENT + COMPLETE + COOL-OFF remain load-bearing at current size; HEDGE is a tail-insurance rung that activates at scale (perp) or adds a thin overlay now (ETH).

## Strand pool (the thing being hedged)
- 136 strands; YES-strands 79 (mean naked -5.19c), NO-strands 57 (mean naked -8.16c).
- Naked strand: mean -6.44c, std 23.35c.
- OPTIMISTIC smooth h=150 over-hedge (the ablation model): mean +0.46c, std 21.71c -- this is the upside the $6-min forbids at unit size.

## PART 1 -- PERP AT SCALE (integer-contract lumpiness)
Model: a stranded `box_ct`-contract leg has ~$1/contract of BTC delta. The hedge is `n_perp = round(box_ct*$1 / $6)` integer perp contracts, each $6 notional. Per-contract value = `settle + sgn*(n_perp*$6)*r%/100 / box_ct`. The $6-min granularity tax lives in the rounding.

| box_ct | box $ | n_perp | hedge $ | over/under | strand mean | strand std | std_red |
|---|---|---|---|---|---|---|---|
| 1 | $5 | 0 | $0 | no hedge | -6.44c | 23.35c | +0.0% |
| 2 | $10 | 0 | $0 | no hedge | -6.44c | 23.35c | +0.0% |
| 3 | $15 | 1 | $6 | 2.00x | -6.34c | 23.19c | +0.7% |
| 4 | $20 | 1 | $6 | 1.50x | -6.37c | 23.23c | +0.5% |
| 6 | $30 | 1 | $6 | 1.00x | -6.39c | 23.27c | +0.3% |
| 8 | $40 | 1 | $6 | 0.75x | -6.40c | 23.29c | +0.3% |
| 10 | $50 | 2 | $12 | 1.20x | -6.38c | 23.26c | +0.4% |
| 12 | $60 | 2 | $12 | 1.00x | -6.39c | 23.27c | +0.3% |
| 15 | $75 | 3 | $18 | 1.20x | -6.38c | 23.26c | +0.4% |
| 20 | $100 | 3 | $18 | 0.90x | -6.39c | 23.28c | +0.3% |
| 30 | $150 | 5 | $30 | 1.00x | -6.39c | 23.27c | +0.3% |
| 50 | $250 | 8 | $48 | 0.96x | -6.39c | 23.28c | +0.3% |

**Scale threshold: box_ct >= 4 (~$20/window)** -- first box size where an integer perp lands in a proper 0.6-1.6x hedge band AND does not worsen naked mean/std. At box_ct=1-2 (current), the honest `round($1/$6)=0` gives NO hedge; box_ct=3 is the first non-zero hedge but still a 2x over-hedge.

**CRITICAL HONEST FINDING -- the integer-perp hedge barely reduces variance even at scale.** A *delta-neutral* perp (the only kind the $6-min permits without becoming a directional bet) cuts strand-pool std by only ~0.3-0.7% (e.g. 23.4c -> ~23.2c). This is consistent with the perp's established **1.7% R^2 basis** vs the 15-min strand: a 15-min strand outcome is almost pure idiosyncratic Bernoulli noise that a BTC-spot delta hedge cannot offset. The ablation's headline (-0.98c/win, +4.2c CVaR from dropping h=150) came from h=150 = ~$150 of hedge per contract = a **massive over-hedge / directional BTC bet that happened to capture in-sample drift**, NOT a delta-neutral hedge. So the at-scale perp's *honest* value is much smaller than the ablation implies. **The scale threshold is where perp becomes a clean hedge, not where it becomes a strong PnL lever -- those are different claims.**

**Recommended at-scale perp spec:**
- Activate at **box_ct >= 4** (SCALE_GATE Stage A+; ~$20/window net strand notional comparable to the $6 perp min). Below this, do NOT hedge with perp.
- **REACTIVE timing** (hedge only confirmed strands), not prophylactic: pair-rate is 85%, so prophylactic hedging pays the perp round-trip on ~85% of legs that pair anyway -- pure drag.
- **delta_mult ~1.0** (delta-neutral); over-hedging (>1.5x) only helps in-sample by capturing BTC drift = a directional bet, not a hedge. Hold the line at neutral.
- **Side-specific:** NO-strands carry the larger naked loss; size both sides at neutral, do not asymmetrically over-hedge YES (the in-sample YES-drift is not a stable signal).
- **ALWAYS-hedge beats conditional** (vpin/cheap) at scale -- the integer perp is cheap once sized right, and conditional filters leave most strands naked.
- At-scale OOS window metrics (per-contract, scale-invariant): net +2.78c/win, Sharpe +0.180, CVaR95 44.86c, skew -1.68 (vs naked net +2.77c, CVaR95 45.00c).

## PART 2 -- ETH CROSS-ASSET (deployable now, 5a)
Rule: BTC YES-strand -> buy ETH-NO; BTC NO-strand -> buy ETH-YES. Coverage 80/136 = 59% (needs a concurrent active ETH window within 450s).

| n_ct | mode | k_cut | gap | strand mean | strand std | std_red |
|---|---|---|---|---|---|---|
| 1 | maker | 10 | hold | -1.82c | 26.17c | -12.1% | (BEST)

**Refined deployable ETH spec:**
- Size **1 ETH contract(s)** per BTC strand contract; **maker (post at touch, 0 fee)** entry (maker captures the extra ~2.7c/strand the prior work found vs taker's +0.5c).
- **k-slot cutoff k<=10**: only place the ETH hedge if the concurrent ETH window has enough time left to fill the hedge leg and settle (late ETH windows give thin coverage and the BTC/ETH co-move has less time to mean-revert).
- **Coverage gap (41% of strands with no concurrent ETH window): gap=hold** -- hold (fall back to COMPLETE/MANAGE rungs 3/4); selling cheap strands in the gap did not improve the pool here.
- OOS window metrics: net +3.79c/win, Sharpe +0.237, CVaR95 42.37c, skew -1.48 (vs naked net +2.77c, CVaR95 45.00c).
- **HONEST SCREENING DISCREPANCY:** the established 5a finding was ~10% std-reduction (R^2 18.6% vs strand loss). On THIS 136-strand pool (45 OOS) the ETH binary overlay did NOT reduce strand-pool variance (best config std_red -12.1% = it ADDED variance). Reason: an ETH 15-min binary has a discrete $0/$1 payout swing that, even delta-scaled by the ~0.43 BTC/ETH binary corr, is lumpy relative to the ~23c strand std on a small pool -- it behaves like a second directional bet, not a smooth variance reducer. The established +10% was derived on a larger/differently-sampled pool; with only 136 strands the per-strand estimate is noisy. **Forward validation (n>=300) is required before trusting either number.**
- It remains DEPLOYABLE now (same Kalshi API, no perp min) and may still earn its place as a low-risk overlay once forward data settles the variance question; but this screening does NOT confirm the ~10% std-reduction. Treat as a candidate, not a validated reducer.

## PART 3 -- CROSS-STRIKE DATA-COLLECTION SPEC (unlock the modeled winner)
Cross-strike is the modeled best basis (~88% settlement correlation vs perp's ~13% / ETH's ~43% binary corr) but KXBTC15M is SINGLE-STRIKE, so the offsetting strike must come from the **daily KXBTC multi-strike ladder** at a comparable level. It is DATA-BLOCKED: the ladder files we have are arb-flags only, not full strike books.

**Collect (extend `kalshi_ladder_collect.py`):**
1. For each active 15-min BTC window, snapshot the **daily KXBTC ladder strikes k-1, k, k+1** bracketing the current BTC spot (k = nearest strike). Capture full top-of-book: `(ts, strike, yes_bid, yes_ask, no_bid, no_ask, yes_bid_sz, no_bid_sz)` at >=1Hz.
2. Tag each snapshot with the concurrent 15-min window `ws`, BTC spot, and the 15-min strand side/price if one is open (so we can join strand -> available adjacent-strike hedge at decision time).
3. Record **settlement** of each daily strike (res_up per strike) to measure realized cross-strike settlement correlation vs the 15-min strand outcome.
4. Minimum 2-3 weeks to get >=300 strand events with a concurrent populated ladder book.

**Hedge rule to validate once unblocked:**
- BTC 15-min YES-strand (long up) -> SELL the daily YES at strike k (or buy daily NO@k): a down-move that loses the 15-min YES is offset by the daily NO gaining.
- BTC 15-min NO-strand -> BUY daily YES@k.
- Size by the strikes' delta ratio (15-min strike's $-delta / daily strike's $-delta); the daily strike is coarser so expect ~1 daily contract per several 15-min strands -- model with the SAME integer-lumpiness discipline as the perp (do not assume a smooth ratio).
- Basis risk = the 15-min vs end-of-day settlement-window mismatch; this is why we MEASURE realized corr before trusting the ~88% model.

## PART 4 -- COMPARISON (perp at-scale vs ETH now vs cross-strike modeled)
| Hedge | Basis (corr vs strand) | Cost/strand | Coverage | Deployable | Rung |
|---|---|---|---|---|---|
| BTC perp (smooth h=150) | ~13% (1.7% R^2) | ~0 (0% fee) | 100% | NO ($6 min = 12x over at $5) | 5b at-scale |
| BTC perp (integer, box_ct>=4) | ~13% | ~0 | 100% (at scale) | ONLY at ~$20+/window | 5b at-scale |
| ETH 15-min binary | ~43% (18.6% R^2)* | +0.5c tkr / +3.2c mkr | 59% | YES (now, $5) | 5a deployable |

*ETH R^2/std-reduction is the ESTABLISHED 5a number; this screening's 136-strand pool did NOT reproduce a variance reduction (lumpy binary payout on a small pool) -- forward-validate.
| Cross-strike (daily ladder) | ~88% modeled | ~0 (maker) | TBD | DATA-BLOCKED | 5a candidate |

**5a/5b split CONFIRMED:** 5a = ETH cross-asset binary (deployable now, modest, lowest-friction intra-Kalshi hedge; cross-strike supersedes it on basis once unblocked). 5b = BTC perp (highest coverage / lowest cost but ONLY a true hedge at scale; integer-lumpiness analysis pins the activation at box_ct>=4). Cross-tenor stays DEAD (a 15-min strand is one Bernoulli trial; daily/ladder instruments average it out -> R^2 <0.7%).

## Honest statement: how much does hedging actually help?
- Hedging is the **strongest single ablation lever** but it is **tail insurance, not edge**: it converts the rare residual strand's directional loss into a near-zero variance position. It does NOT prevent the strand or recover its expected cost -- that is PREVENT (t36 / entry gates), COMPLETE (force-complete at touch), and COOL-OFF/RESIZE.
- At current $5 size the perp hedge is **unavailable** (the $6 min makes it a directional bet), so the binding residual-strand handlers are COMPLETE + MANAGE. The ETH overlay is the only intra-Kalshi hedge available now, on the ~60% of strands with a concurrent ETH window, but this screening did NOT confirm it reduces variance (it added some) -- so it is a forward-test candidate, not a load-bearing reducer yet.
- The perp's full ablation value (-0.98c/win, +4.2c CVaR) is **bankable only at box_ct>=4**; below that it is optimistic. Treat the hedge rung's headline number as a SCALE option, not a current-size lever.
- **Forward validation required:** none of these clears the deploy bar (t_vs_live>3 at n>=300) on the screening backtest; the strand pool is small (per-strand stats are signal, not proof).

*https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz*
