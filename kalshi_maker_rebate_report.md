# Kalshi K1: Maker-Rebate / Liquidity-Incentive Capture -- OOS Test

Generated: 2026-07-18T17:22:13.722939+00:00

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

Net-positive rate and average NET/day across the analyzed sample, at each capture-share x markout-horizon combination:

| Capture-share scenario | Markout horizon | n markets | # net-positive | % net-positive | mean NET/day | median NET/day |
|---|---|---|---|---|---|---|
| 100% | 15 min (active) | 32 | 28 | 88% | $102.80 | $12.85 |
| 100% | 6h (passive/stress) | 32 | 30 | 94% | $177.07 | $19.82 |
| 50% | 15 min (active) | 32 | 28 | 88% | $51.40 | $6.43 |
| 50% | 6h (passive/stress) | 32 | 30 | 94% | $88.53 | $9.91 |
| 20% | 15 min (active) | 32 | 28 | 88% | $20.56 | $2.57 |
| 20% | 6h (passive/stress) | 32 | 30 | 94% | $35.41 | $3.96 |
| 5% | 15 min (active) | 32 | 28 | 88% | $5.14 | $0.64 |
| 5% | 6h (passive/stress) | 32 | 30 | 94% | $8.85 | $0.99 |

**Headline scenario** (50% of the depth heuristic, 15-min active-MM markout -- a middle-of-the-road read, not the most flattering one): top net-positive markets in the analyzed sample:

| Ticker | Series | $/day pool | target size | vol/day (ct) | spread | capture share (heur.) | NET/day (headline) | NET/day (stress) |
|---|---|---|---|---|---|---|---|---|
| KXSCRSENS-26-DNOR | KXSCRSENS | $8.70 | 1000 | 68518.0 | 0.01 | 70% | $657.51 | $149.46 |
| KXLATENIGHTMENTION-26JUL19-GOAT | KXLATENIGHTMENTION | $145.75 | 1000 | 609.1 | 0.01 | 96% | $168.82 | $15.85 |
| KXAAAGASD-26JUL19-3.995 | KXAAAGASD | $192.00 | 1000 | 4158.5 | 0.01 | 100% | $147.79 | $9.66 |
| KXLATENIGHTMENTION-26JUL19-AI | KXLATENIGHTMENTION | $145.75 | 1000 | 1227.5 | 0.01 | 63% | $113.37 | $12.22 |
| KXLATENIGHTMENTION-26JUL19-GOLD | KXLATENIGHTMENTION | $145.75 | 1000 | 896.7 | 0.01 | 99% | $106.66 | $10.77 |
| KXMLBMENTION-26JUL18LADNYY-PITC | KXMLBMENTION | $188.24 | 1000 | 7625.6 | 0.01 | 95% | $102.57 | $12.11 |
| KXLATENIGHTMENTION-26JUL19-RED | KXLATENIGHTMENTION | $145.75 | 1000 | 761.4 | 0.01 | 98% | $90.86 | $8.82 |
| KXMLBMENTION-26JUL18LADNYY-WHAT | KXMLBMENTION | $188.24 | 1000 | 1183.6 | 0.02 | 96% | $90.68 | $9.36 |
| KXLATENIGHTMENTION-26JUL19-GIAN | KXLATENIGHTMENTION | $145.75 | 1000 | 846.0 | 0.02 | 98% | $77.62 | $7.69 |
| KXLATENIGHTMENTION-26JUL19-SHAK | KXLATENIGHTMENTION | $145.75 | 1000 | 304.6 | 0.01 | 96% | $71.44 | $7.18 |
| KXAAAGASD-26JUL19-4.010 | KXAAAGASD | $192.00 | 1000 | 10799.9 | 0.01 | 95% | $51.84 | $7.50 |
| KXCPICOMBO-26JULB-0203 | KXCPICOMBO | $20.88 | 1000 | 1203.5 | 0.01 | 91% | $29.45 | $2.66 |
| KXWCMENTION-26JUL18FRAENG-GOLB | KXWCMENTION | $31.18 | 1000 | 8024.6 | 0.01 | 72% | $22.97 | $0.69 |
| KXWCFIRSTSONG-MAD26JUL20-VIV | KXWCFIRSTSONG | $20.88 | 1000 | 2980.3 | 0.01 | 58% | $8.35 | $0.82 |
| KXAIRFARECPI-26AUG12-T304 | KXAIRFARECPI | $20.88 | 1000 | 54.5 | 0.01 | 64% | $8.07 | $0.79 |

## 4. Capacity

Under the headline scenario, **28** of the 32 analyzed markets are net-positive, with combined qualifying target size of **26,600 contracts** and combined estimated NET of **$1,787.19/day** if a maker could simultaneously rest at target size on every one of them. Two caveats on capacity: (1) this requires standing capital roughly equal to target_size x mid-price on BOTH the yes and no side of every market simultaneously (order of target_size dollars per market at ~$0.50 mid, more at higher mid); (2) these are almost all micro-liquidity novelty markets -- the target sizes (300-10,000 contracts) sound large but the markets themselves trade only a handful of contracts per trade, so the depth-proportional capture-share assumption is the single most load-bearing (and least verifiable without live quoting) number in this whole analysis.

## 5. What's measured vs. estimated (explicit)

**Measured directly from the live API** (not modeled): which markets are incentivized, the exact size of every reward pool, program duration, target size, discount factor, live spread and touch depth, real trade counts/sizes/timestamps, per-series fee schedule (maker-free vs maker-fee).

**Estimated / modeled, with explicit sensitivity** (cannot be measured without live two-sided quoting on Kalshi):

1. **capture_share** -- our maker's fraction of the reward score AND of the fill flow. Modeled as a depth-proportional queue heuristic and swept 100%/50%/20%/5%. This is a real, load-bearing uncertainty: Kalshi scores via random per-second snapshots of ALL resting orders at/near the touch, and we cannot see how many other makers are already there over time -- only a live snapshot of current depth.
2. **Adverse-selection cost** -- measured via real mark-outs on the actual trade tape (not simulated), but assumes our hypothetical resting maker would face the SAME average toxicity as the realized fills in the tape. This is standard practice for this kind of ex-ante estimate but is still a proxy, not a live-fill measurement.
3. Fills/day for OUR maker = daily trade volume x capture_share -- same caveat as (1).

## 6. Verdict

At the MOST OPTIMISTIC scenario tested (100% capture of the depth heuristic, 15-min active-MM markout), **88%** of analyzed markets are net-positive (mean $102.80/day, median $12.85/day). At the headline (50% capture, 15-min) scenario, **88%** are net-positive (mean $51.40/day). Under the stress scenario (5% capture, 6h passive markout), **94%** are net-positive.

**VERDICT: a real, if modest, edge on a subset of markets -- but it lives entirely on illiquid novelty markets, not Kalshi's liquid flagship products (no incentive program exists on any high-volume series). Deployability is capped by (a) the small absolute size of most reward pools once shared pro-rata, and (b) genuine uncertainty in our capture-share estimate, which is the single least-verifiable input in this analysis without live two-sided quoting. Worth a small, closely-monitored live pilot on the specific markets flagged net-positive above, sized to the smaller end of the capacity estimate -- NOT a scalable standalone strategy.
