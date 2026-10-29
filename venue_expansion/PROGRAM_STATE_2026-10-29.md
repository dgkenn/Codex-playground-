# Program state after 54 studies — 2026-10-29

## The catalog calibration result

**Anchor (a) replicated exactly**, so the pipeline is trustworthy: the new code re-derived
`TAIL_PRICING`'s T=15 sell-at-bid table from its 503 cached hours with all 7 longshot buckets matching
on both n and YES count, and the 46.6% no-bid fraction matching. On a freshly fetched `KXBTCD` stratum
(302 events), 5 of 5 sell longshot cells have the mean bid inside the Wilson interval at both 95% and
99.98%.

**Verdict: INSUFFICIENT** — 0 PASS cells, and my frozen KILL clause could not fire.

But the directional evidence is unambiguous:

| | |
|---|---|
| cells whose Wilson interval excludes the price in the **profitable** direction, at any n | **0 of 280** |
| cells whose interval excludes it in the **unprofitable** direction | **85 of 280** |
| cells with a positive point estimate | **29 of 280** |
| expected under a zero-drift null | **~140** |
| pooled fee-inclusive taker edge negative with CI excluding zero | **25 of 28** category×T×direction rows |

**The deficit of positive cells — 29 where chance alone gives ~140 — is the most general statement
this program has produced.** It is not "we failed to find an edge." It is a measured, venue-wide
negative drift equal to the spread plus the fee. The calibration curves have the same shape in every
category: **the realised frequency lands inside the quoted spread**, far below the ask and far above
the bid. That is precisely what an efficient market with a transaction cost looks like.

Magnitudes: crypto ex-`KXBTCD` pooled T=15 net is **−3.3c on buys and −4.5c on sells**; other
categories are worse. Best point estimate anywhere: +0.75c (Crypto T=60 sell, n=172, 16 events).

**The apparent miscalibration is a trap, not an opportunity.** Sports T=15 buys show ask 96c against a
realised 32% — but those are **stale one-sided books on markets already determined NO** (≈25 NHL
first-goal-scorer markets quoted at 95c with no bid and zero volume). The mispricing is in the
direction that costs a buyer money, and the profitable side has no bid to hit.

## Four defects in my own spec

1. **My KILL clause was unfireable — the third in a row.** I required the Wilson interval to *contain*
   the executable price **in both directions**, but spread and tick-floor structure break containment
   in the unprofitable direction automatically, so the clause is near-unreachable in thin books. The
   agent correctly refused to apply a non-frozen rule. **The lesson, now explicit: a KILL clause must
   be stated as "the profitable-direction edge fails to clear a threshold," never as a two-sided
   containment condition.** Under that correctly-formed clause these data give 0 of 280 and would read
   as a KILL — but I am not claiming that, because reading a gate off data I have already seen is the
   exact error this whole apparatus exists to prevent.
2. **My series counts were wrong.** The catalog holds **15,416 series, 9,116 in the seven categories
   (Sports 4,055)** — not the 9,191/4,067 I reported. My figures came from summing per-category API
   responses and double-counted.
3. **I missed a whole category.** **Elections (2,331 series)** is separate from Politics and sits
   outside my frozen seven.
4. **An empty ask prints as `100c`, not `0`.** My untradeable definition keyed on 0; the agent
   classed 100c-with-no-offer as untradeable, which is right.

## Power reality: most of this is unreachable, and that is a finding

| category | events priced | median cell needs |
|---|---:|---|
| Politics | 267 of 703 (38%) | **~10,300 events — more than exist in its entire universe** |
| Economics | 267 of 2,377 (11%) | ~1,100 |
| Climate | 267 of 9,544 (2.8%) | ~9,500 |
| Sports | 267 of 165,070 (**0.16%**) | — |

Criterion 2 is **provably unreachable in Politics at any sample size.** Elsewhere, closing the gap
means 10–35× more fetching against an API that returned HTTP 429 on roughly one call in four, for a
confirmatory null. **That is not worth doing.**

## Where the program stands

Every mechanism by which an outside participant could profit here has been tested and closed:

| mechanism | verdict |
|---|---|
| Information (know the outcome sooner/better) | closed — the market forecasts faster than we observe (47 studies) |
| Determined-before-close | closed at the catalog level — the venue designs it out |
| Speed / arbitrage | closed — crossings live under 100 ms, taken at the same microsecond |
| Risk premium / mispricing | **closed here** — 0 of 280 profitable-direction exclusions |
| Liquidity provision (taker fee) | closed — adverse selection matches the spread |
| Incentive rebates | closed — pro-rata pots are capital-weighted and competition-diluted |
| **Liquidity provision, fee-free, favourite side** | **OPEN** — `FAVOURITE_MAKER_REVISIT.md`, re-run ≥130 days |

**The one surviving thread is the only one that pays no fee**, and that is not a coincidence. The
measured taker drag is 1c of fee plus several cents of spread; the favourite-side maker point estimate
is +1.2–1.8c per quoted contract. An edge of that size **cannot** survive the taker cost structure —
so if anything exists for this operator, it must be on the fee-free side of the book. That is a
structural conclusion, not a hope, and it is what 54 studies have narrowed to.

## The single piece of missing data

`FAVOURITE_MAKER_REVISIT` names **queue position** as the decisive unknown, and every maker study had
to *assume* it (`N ∈ {25, 100}` contracts resting ahead). Open-market records expose
`yes_bid_size_fp` / `yes_ask_size_fp` — **live top-of-book depth** — but **only while a market is
open**. Settled markets expose candlesticks, which carry no depth.

So this cannot be backfilled. It needs **forward snapshot collection** on `KXBTCD` favourites, which
needs a schedule, which needs either a workflow on the default branch (the operator's call — GitHub
Actions honours `schedule:` only from the default branch) or a process the operator runs. **This is
the one concrete, cheap thing that would convert the last open thread from assumption to measurement,
and it has to start before December's re-run to be useful.**
