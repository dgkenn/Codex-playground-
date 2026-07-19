# Kalshi K1: Maker-Rebate / Liquidity-Incentive Capture -- OOS Test

Generated: 2026-07-18T17:26:52.252220+00:00

## Correction to prior kill

The earlier 'LP-REWARDS' kill was **Polymarket's** latency-bound CLOB liquidity-rewards pool (real yield, but a first-in-queue speed game -- infra edge, not risk edge). **Kalshi is a separate, pure CLOB exchange** with its own CFTC-filed Liquidity Incentive Program: a published per-market reward pool paid pro-rata by resting size x price-distance decay, sampled once per second. No latency requirement to be first in queue -- you just need to rest meaningful size near the touch for a large share of the period. Confirmed genuinely distinct mechanism via live API (`GET /incentive_programs`) and Kalshi's own program docs.

## 1. Universe: incentivized markets right now

- **2717 active liquidity-incentive programs** across **196 unique series** (one program per market; all observed programs are `incentive_type=liquidity`, none are `volume` type at capture time).
- Total daily reward pool across ALL active programs: **$55,577/day**.
- Per-market daily reward pool: min $1.36, p25 $3.57, **median $15.02**, p75 $22.73, max $192.70.
- Target (qualifying) resting size: min 300, median 1000, max 10000 contracts.
- Program duration: min 0.52d, median 7.0d, max 30.5d.
- **3/196 series charge a maker fee** (`quadratic_with_maker_fees`): KXAAAGASM, KXEGGS, KXLLM1. The other 193 use standard `quadratic` fee type, where **maker (resting) fills are free** -- only a taker crossing the book pays.

**Top series by number of incentivized markets** (i.e. where Kalshi is concentrating its subsidy):

| Series | # incentivized markets |
|---|---|
| KXH200MS | 141 |
| KXWORLDCUPHALFTIME | 131 |
| KXB200MS | 117 |
| KXH100MS | 117 |
| KXWCSTART | 104 |
| KXWCFIRSTSONG | 92 |
| KXRTX5090MS | 92 |
| KXA100MS | 91 |
| KXWCMENTION | 71 |
| KXH100WS | 63 |
| KXMC | 52 |
| KXWCFINALSONGS | 52 |
| KXA100WS | 51 |
| KXAAAGASM | 42 |
| KXFEDERALCHARGE | 40 |

**Critical structural observation**: none of Kalshi's flagship, genuinely-liquid series (BTC/ETH daily strikes, weather highs, presidential/election markets, NFL/NBA game lines) carry ANY active incentive program:

| Flagship series checked | # incentive programs |
|---|---|
| KXBTCD | 0 |
| KXETHD | 0 |
| KXHIGH | 0 |
| KXPRES | 0 |
| KXFED | 0 |
| KXNFLGAME | 0 |
| KXNBASERIES | 0 |
| KXINX | 0 |

Every incentive dollar is aimed at markets that would otherwise have **no organic liquidity**: gas-price micro-strikes, MLB/NBA in-game player-mention props, World Cup halftime-song and attendance markets, federal-charge and movie-casting novelty markets, CPI sub-bracket markets, etc. Kalshi is renting liquidity precisely where the natural adverse-selection risk is highest (thin books, jumpy/event-driven prices, small number of informed participants relative to total flow) -- exactly the setup this OOS test needs to price honestly rather than assume away.

## 2. Method

Analyzed **70** markets: the top-$/day candidates plus a random cross-section for representativeness. **32** had enough real trade-tape volume (>= 8 trades in the lookback window) to produce an estimate; **38** were too thin to estimate at all and are reported as an honest NULL rather than a fabricated number.

For each estimable market:

- **Daily rebate pool** = `period_reward` ($, converted from centi-cents) / program duration (days) -- this is measured directly from the live API, not estimated.
- **Adverse-selection cost per contract** = a mark-out computed from the REAL trade tape: for every trade, the resting counterparty's forward P&L to a later trade at/after a fixed horizon. Two horizons: 15 min (an active MM that re-quotes/manages inventory quickly) and 6h (a passive maker that cannot hedge -- the stress case, matching the 'no live two-sided quoting available' honesty caveat).
- **capture_share** -- the fraction of BOTH the reward score and the taker fill flow our hypothetical maker would actually capture by resting `target_size` contracts. This is the one input we CANNOT measure without live quoting (no L3 queue-position data). Estimated via a depth-proportional heuristic: `target_size / (live resting depth at the best price + target_size)`, then swept at 100%/50%/20%/5% of that heuristic to bound the honest range rather than assert a single number.
- **Fees**: $0 on the maker fill for the 193/196 series using standard `quadratic` fee type (measured, not assumed); Kalshi's quadratic taker-fee formula applied for the 3 `quadratic_with_maker_fees` series.
- `NET/day = daily_rebate*capture_share - fills/day*capture_share*markout_cost - fee_cost`.

## 3. Results by scenario

Net-positive rate and average NET/day across the analyzed sample, at each capture-share x markout-horizon combination. **Two positive counts are shown**: `rebate-driven` (the Kalshi reward pool itself accounts for >=25% of the positive NET -- the thing K1 is actually about) vs `spread-capture-dominated` (positive NET, but the reward pool is a rounding error next to negative measured adverse-selection, i.e. the trade tape shows realized mean-reversion/spread capture that would exist with or without any incentive program -- a DIFFERENT, unverified hypothesis about generic Kalshi market-making profitability, not a finding about the rebate):

| Capture-share scenario | Markout horizon | n markets | # net-positive | of which rebate-driven | of which spread-capture-dominated | mean NET/day (rebate-driven only) |
|---|---|---|---|---|---|---|
| 100% | 15 min (active) | 32 | 28 | 27 | 1 | $82.16 |
| 100% | 6h (passive/stress) | 32 | 30 | 29 | 1 | $97.45 |
| 50% | 15 min (active) | 32 | 28 | 27 | 1 | $41.08 |
| 50% | 6h (passive/stress) | 32 | 30 | 29 | 1 | $48.72 |
| 20% | 15 min (active) | 32 | 28 | 27 | 1 | $16.43 |
| 20% | 6h (passive/stress) | 32 | 30 | 29 | 1 | $19.49 |
| 5% | 15 min (active) | 32 | 28 | 27 | 1 | $4.11 |
| 5% | 6h (passive/stress) | 32 | 30 | 29 | 1 | $4.87 |

**Headline scenario** (50% of the depth heuristic, 15-min active-MM markout -- a middle-of-the-road read, not the most flattering one): top net-positive markets in the analyzed sample, flagged by whether the rebate itself is actually doing the work:

| Ticker | Series | $/day pool | vol/day (ct) | book turnover/day | capture share (heur.) | NET/day (headline) | NET/day (stress) | rebate's share of NET |
|---|---|---|---|---|---|---|---|---|
| KXSCRSENS-26-DNOR | KXSCRSENS | $8.70 | 68427.2 | 166.8x | 71% | $669.69 | $152.23 | 0% (spread-capture) |
| KXLATENIGHTMENTION-26JUL19-GOAT | KXLATENIGHTMENTION | $145.75 | 592.9 | 15.8x | 96% | $166.21 | $15.62 | 42% (REBATE-DRIVEN) |
| KXAAAGASD-26JUL19-3.995 | KXAAAGASD | $192.00 | 4010.7 | 422.2x | 99% | $133.34 | $11.64 | 71% (REBATE-DRIVEN) |
| KXLATENIGHTMENTION-26JUL19-AI | KXLATENIGHTMENTION | $145.75 | 1194.9 | 2.0x | 63% | $111.58 | $12.01 | 41% (REBATE-DRIVEN) |
| KXLATENIGHTMENTION-26JUL19-GOLD | KXLATENIGHTMENTION | $145.75 | 872.9 | 49.9x | 98% | $105.17 | $10.62 | 68% (REBATE-DRIVEN) |
| KXMLBMENTION-26JUL18LADNYY-PITC | KXMLBMENTION | $188.24 | 7359.1 | 138.9x | 95% | $102.53 | $12.05 | 87% (REBATE-DRIVEN) |
| KXMLBMENTION-26JUL18LADNYY-WHAT | KXMLBMENTION | $188.24 | 1142.2 | 57.1x | 98% | $92.19 | $9.51 | 100% (REBATE-DRIVEN) |
| KXLATENIGHTMENTION-26JUL19-RED | KXLATENIGHTMENTION | $145.75 | 741.2 | 34.1x | 98% | $90.23 | $8.76 | 79% (REBATE-DRIVEN) |
| KXLATENIGHTMENTION-26JUL19-GIAN | KXLATENIGHTMENTION | $145.75 | 823.5 | 31.1x | 97% | $77.37 | $7.66 | 92% (REBATE-DRIVEN) |
| KXLATENIGHTMENTION-26JUL19-SHAK | KXLATENIGHTMENTION | $145.75 | 296.5 | 7.3x | 96% | $71.26 | $7.16 | 98% (REBATE-DRIVEN) |
| KXAAAGASD-26JUL19-4.010 | KXAAAGASD | $192.00 | 10374.6 | 190.4x | 95% | $53.38 | $7.56 | 171% (REBATE-DRIVEN) |
| KXCPICOMBO-26JULB-0203 | KXCPICOMBO | $20.88 | 1201.9 | 6.1x | 84% | $26.96 | $2.43 | 32% (REBATE-DRIVEN) |
| KXWCMENTION-26JUL18FRAENG-GOLB | KXWCMENTION | $31.18 | 8015.2 | 21.6x | 73% | $23.12 | $0.69 | 49% (REBATE-DRIVEN) |
| KXWCFIRSTSONG-MAD26JUL20-VIV | KXWCFIRSTSONG | $20.88 | 2976.3 | 4.0x | 58% | $8.35 | $0.82 | 72% (REBATE-DRIVEN) |
| KXAIRFARECPI-26AUG12-T304 | KXAIRFARECPI | $20.88 | 54.4 | 0.1x | 64% | $8.06 | $0.79 | 83% (REBATE-DRIVEN) |

*("rebate's share of NET" can exceed 100% when adverse selection is a genuine positive cost that eats into the rebate but doesn't flip NET negative -- that's the intended, healthy case: the rebate is doing all the work and then some is lost to real adverse selection. It's the **spread-capture** flag, not a >100% figure, that signals a market to distrust.)*

## 4. Capacity

Restricting to the **rebate-driven** subset only (the honest answer to "is the rebate program itself deployable"): **27** of 32 analyzed markets, combined qualifying target size **25,600 contracts**, combined estimated NET **$1,109.15/day** if resting target size on all of them simultaneously. (The 1 spread-capture-dominated markets are excluded from this capacity figure -- see Section 3's caveat; their large modeled NET is not attributable to the rebate program and is separately, and more skeptically, discussed in the verdict.)

Two caveats even on the rebate-driven capacity figure: (1) it requires standing capital roughly equal to target_size x mid-price on BOTH the yes and no side of every market simultaneously (order of target_size dollars per market at ~$0.50 mid, more at higher mid); (2) these are almost all micro-liquidity novelty markets -- the target sizes (300-10,000 contracts) sound large but many of these markets trade only a handful of contracts per print, so the depth-proportional capture-share assumption is the single most load-bearing (and least verifiable without live quoting) number in this whole analysis.

## 5. What's measured vs. estimated (explicit)

**Measured directly from the live API** (not modeled): which markets are incentivized, the exact size of every reward pool, program duration, target size, discount factor, live spread and touch depth, real trade counts/sizes/timestamps, per-series fee schedule (maker-free vs maker-fee).

**Estimated / modeled, with explicit sensitivity** (cannot be measured without live two-sided quoting on Kalshi):

1. **capture_share** -- our maker's fraction of the reward score AND of the fill flow. Modeled as a depth-proportional queue heuristic and swept 100%/50%/20%/5%. This is a real, load-bearing uncertainty: Kalshi scores via random per-second snapshots of ALL resting orders at/near the touch, and we cannot see how many other makers are already there over time -- only a live snapshot of current depth.
2. **Adverse-selection cost** -- measured via real mark-outs on the actual trade tape (not simulated), but assumes our hypothetical resting maker would face the SAME average toxicity as the realized fills in the tape. This is standard practice for this kind of ex-ante estimate but is still a proxy, not a live-fill measurement.
3. Fills/day for OUR maker = daily trade volume x capture_share -- same caveat as (1).

## 6. Verdict

**The rebate-driven vs. spread-capture-dominated split is the whole story here.** At the MOST OPTIMISTIC scenario tested (100% capture of the depth heuristic, 15-min active-MM markout): **84%** of analyzed markets are net-positive WITH the rebate itself doing >=25% of the work (mean $82.16/day on that subset), vs. a further **3%** that are net-positive only because measured adverse-selection came out negative (i.e. realized spread capture / short-sample mean reversion swamps a reward pool that is a rounding error by comparison -- NOT evidence the rebate program itself works, and heavily exposed to small-sample overfitting on a few days of trade tape). At the headline (50% capture, 15-min) scenario: **84%** rebate-driven, **3%** spread-capture-only. Under the stress scenario (5% capture, 6h passive): **91%** rebate-driven, **3%** spread-capture-only.

**VERDICT ON THE REBATE ITSELF: a real, if modest, edge on a subset of markets -- but it lives entirely on illiquid novelty markets, not Kalshi's liquid flagship products (no incentive program exists on any high-volume series). Deployability is capped by (a) the small absolute size of most reward pools once shared pro-rata, and (b) genuine uncertainty in our capture-share estimate, which is the single least-verifiable input in this analysis without live two-sided quoting. Worth a small, closely-monitored live pilot on the specific REBATE-DRIVEN markets flagged net-positive above, sized to the smaller end of the capacity estimate -- NOT a scalable standalone strategy. The additional spread-capture-dominated markets in the sample are a separate, unverified hypothesis (see caveat above) and are excluded from this verdict.
