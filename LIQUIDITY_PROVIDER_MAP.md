# Where can WE be the liquidity provider? — consolidated venue map (2026-06-21)

Search goal: find venues/markets where a patient US-retail MAKER is the structural liquidity provider
(the validated Kalshi longshot-maker edge). Three parallel deep-dives + all prior work. The answer
converges on one law.

## THE LAW: uncontested <=> small
The liquidity-provider premium (the spread / favorite-longshot "optimism tax") is REAL in every venue.
It accrues to whoever holds the provider seat. **Every scalable/liquid pool already has a PROFESSIONAL
in that seat; we can only hold it where the pool is too small for a pro to bother.** So being the
provider and having scale are mutually exclusive for us. This is structural, not a gap in the search.

## Venue map
| Venue / angle | Verdict | Seat-holder / killer | Doc |
|---|---|---|---|
| Listed options (lottery/VRP) | scalable but NOT ours | PFOF wholesalers (Citadel/SIG/Wolverine) take 85-90% of retail flow; we get residual @ Sharpe 0.5-0.8 | OPTIONS_LOTTERY_PREMIUM.md |
| Sports exchanges (Novig/ProphetX maker) | dead | pros engineered into the book; 2% rake; amateur makers historically -2% (Becker) | SPORTS_EXCHANGE_MAKER.md |
| 2026 CFTC venues (ForecastEx/Rothera/DKeX/CME/Cboe) | dead | each engineered a pro MM in, or macro-efficient / sports-only / fee-killed | MAKER_VENUES.md |
| PredictIt | dead | 10%+5% fees, $850 cap, winding down | MAKER_VENUES.md |
| Kalshi new-listing land-grab | not separately tradable | richest per-contract <6h (+7.9c) but only ~1.8% of flow then; confirms early-in-life tilt only | MAKER_VENUES.md |
| **Polymarket-US (QCEX/QCX)** | **the one lead (portability test)** | CFTC-licensed US venue; fee-free + rebated retail maker; SAME seat as Kalshi -- measure, don't assume | MAKER_VENUES.md |
| **Kalshi soft-longshot (incumbent)** | **the validated edge** | too small for a pro MM -> we ARE the provider; ~$30-150/mo, high Sharpe | KALSHI_LONGSHOT_OPTIMAL.md |

## Honest caveat carried forward (Becker yellow flag)
Becker (72.1M Kalshi trades): amateur makers historically realized the WRONG sign (-2.0%); the +1.12%
maker premium appeared only post-Oct-2024 professionalization. Reconciliation: that was makers across ALL
bands (favorites/mids are -EV in our own data); we isolate the longshot-sell sub-band [0.05,0.15] that
survived adverse selection. BUT it is a legitimate reason NOT to take the edge on faith -> the FORWARD
paper-track + decision-audit is the arbiter. If a pro MM is actually our counterparty on soft longshots,
realized fills will be adversely selected and won't match the +5.45c backtest. Do not scale real money
past the $10 plumbing test until forward realized edge matches backtest.

## Strategic conclusion
The search is exhausted. The deployable picture:
1. **Small uncontested alpha:** the Kalshi soft-longshot harvest (built, optimized, audited), possibly
   ported to **Polymarket-US** for a second small pond (run the identical sell-YES p[0.05,0.15] settled-P&L
   measurement there first).
2. **Scalable growth:** the trend-overlaid all-weather + convex barbell portfolio (risk premia pay everyone
   who bears the risk -- no provider seat to win).
There is NO scalable uncontested-maker edge; stop hunting for one. Scale comes from risk premia, alpha comes
from the small uncontested ponds.
