# VENUE_SCAN — first venue-wide niche scan (2026-07-11)

`market_scanner.py` run for real against the live Kalshi public API. Paginated
`GET /trade-api/v2/events?status=open&with_nested_markets=true` (35 pages, 48.2s), which returns
every open event with `series_ticker`/`category` plus all nested open markets and their
top-of-book bid/ask/size/volume/open-interest in one batch call — no per-market orderbook
round-trips needed. Total script runtime: **49.2s** (well inside the 2-3 min budget; politeness
sleep is 1.2s/page, 35 pages).

Note on scope: raw `GET /markets?status=open` is ~99.9% dominated by auto-generated `KXMVE*`
"multivariate event" combinatorial markets (confirmed by manual probe: 257k open markets total,
~257k of the first sampled 258k were `KXMVE*` junk with zero volume/OI). Those never appear in
the `/events?status=open` listing, so this scan is naturally clean of them.

**Totals:** 6,988 open events scanned → 26,276 liquid-enough markets → 2,721 series.
"Liquid enough" = real two-sided quote (yes_bid>0, yes_ask<1) AND (24h volume>0 OR lifetime
volume>0 OR open interest>0).

Raw output: `gha_data/venue_scan_2026-07-11.jsonl.gz` (26,276 rows, one per liquid market).

## Top 15 by opportunity_score = median_spread_ticks × total 24h volume

| Rank | Series | Category | #Mkt | Med Spread (ticks) | Med Depth | 24h Volume | Score |
|---|---|---|---|---|---|---|---|
| 1 | KXWCADVANCE | Sports | 6 | 1.0 | 888,647.5 | 136,522,682 | 136,522,682 |
| 2 | KXMENWORLDCUP | Sports | 6 | 5.5 | 914.0 | 16,269,779 | 89,483,783 |
| 3 | KXUFCFIGHT | Sports | 16 | 1.0 | 30,094.3 | 32,040,584 | 32,040,584 |
| 4 | KXT20MATCH | Sports | 37 | 14.0 | 6.0 | 2,021,977 | 28,307,682 |
| 5 | KXODIMATCH | Sports | 6 | 39.0 | 16.0 | 712,742 | 27,796,928 |
| 6 | KXPGATOUR | Sports | 154 | 2.0 | 987.1 | 13,071,538 | 26,143,077 |
| 7 | KXWCMATCHUP | Sports | 12 | 20.5 | 47.5 | 1,047,695 | 21,477,743 |
| 8 | KXNEXTTEAMNBA | Sports | 80 | 3.0 | 53.5 | 4,183,552 | 12,550,655 |
| 9 | KXTRUMPUFC | Politics | 2 | 2.0 | 273,916.8 | 5,656,986 | 11,313,971 |
| 10 | KXUFCMOV | Sports | 50 | 1.0 | 421.8 | 6,042,359 | 6,042,359 |
| 11 | KXPGAH2H | Sports | 17 | 94.0 | 46.0 | 60,595 | 5,695,959 |
| 12 | KXMLBGAME | Sports | 44 | 1.0 | 7,225.2 | 5,568,408 | 5,568,408 |
| 13 | KXWCMOV | Sports | 15 | 1.0 | 1,000.0 | 5,013,411 | 5,013,411 |
| 14 | KXWCSCORE | Sports | 32 | 1.0 | 5,571.1 | 4,459,125 | 4,459,125 |
| 15 | KXWCGOAL | Sports | 43 | 1.0 | 246.6 | 4,120,851 | 4,120,851 |

**Caveat on the raw ranking:** `median_spread_ticks × volume` rewards enormous volume as much as
wide spread, so it's dominated by a few *already tight, already efficient* World Cup / UFC
markets (rank 1 `KXWCADVANCE` and rank 3 `KXUFCFIGHT` sit at 1 tick — the minimum possible
spread — with huge depth already resting on both sides; nothing to harvest, the market is
already efficiently market-made, likely by incumbents). For picking real MM targets I filtered
to series with `median_spread_ticks >= 3`, `24h volume > 1,000`, and `market_count >= 3` (real,
liquid, genuinely wide) — see the reference table below.

| Series | Category | #Mkt | Med Spread (ticks) | Med Depth | 24h Vol |
|---|---|---|---|---|---|
| KXMENWORLDCUP | Sports | 6 | 5.5 | 914.0 | 16,269,779 |
| KXT20MATCH | Sports | 37 | 14.0 | **6.0** | 2,021,977 |
| KXODIMATCH | Sports | 6 | 39.0 | 16.0 | 712,742 |
| KXWCMATCHUP | Sports | 12 | 20.5 | 47.5 | 1,047,695 |
| KXNEXTTEAMNBA | Sports | 80 | 3.0 | 53.5 | 4,183,552 |
| KXPGAH2H | Sports | 17 | 94.0 | 46.0 | 60,595 |
| KXFEDDECISION | Economics | 53 | 10.0 | 13.0 | 117,143 |
| KXCPICOREYOY | Economics | 28 | 53.5 | 34.5 | 15,477 |
| KXCPIYOY | Economics | 42 | 47.5 | 6.5 | 14,727 |

For reference, the existing engine's home turf under the same methodology: `KXBTC15M`
med_spread 1.0 tick / vol 950,910; `KXBTCD` med_spread 1.0 tick / depth 218 / vol 1,951,574;
`KXETHD` med_spread 1.5 ticks / depth 70 / vol 41,580 — i.e. already efficiently quoted at
1-1.5 ticks, consistent with the box-harvester already operating there. Anything scoring near
or below that spread level is not a fresh opportunity.

## The 3 most promising niches to port the MM engine to

**1. KXT20MATCH (Twenty20 cricket live match-winner) — highest-confidence raw MM signal, needs
a new fair-value model.** 37 open markets, real spread (14 ticks, vs crypto's 1), real volume
(2.0M/24h) and the *thinnest* median top-of-book depth of any high-score series (6 contracts) —
textbook wide-spread × real-volume × thin-depth shape. `KXODIMATCH` (ODI cricket, 39-tick
spread) and `KXWCMATCHUP` (soccer World Cup matchups, 20.5 ticks) share the same profile at
smaller scale. These are **scheduled-event markets** in the sense that mattered for this
exercise: fair value isn't a continuous external price feed like BTC spot, it's a live win
probability that moves on discrete game events (wickets, overs, goals). Porting means keeping
the box-harvest mechanics (rest paired YES/NO, let the box be the profit) but swapping
`kalshi_trader.py`'s BTC-index fair-value calc for a live sports win-probability model (ball-by-
ball / score-state model) — a materially different, harder-to-validate build than a copy-paste.

**2. KXWTI / KXWTIMAX (WTI crude oil, Commodities/Financials) — the crypto-correlated,
port-as-is candidate.** Lower score (280K/152K) than the sports outliers above but structurally
the closest cousin to KXBTC15M/KXBTCD: a **continuous external price feed** (WTI spot/futures)
driving a periodic strike-ladder of binary markets, same shape as the crypto daily-range
series. `KXWTI` shows 4-tick median spread with real depth (500) and volume (70K/24h) across 99
markets — wider than crypto's 1 tick, meaning there's real room the crypto engine's tight-spread
quoting logic doesn't currently claim. This is the one where "the engine ports as-is" is
literally true: same fair-value architecture (external index → theoretical price → quote both
sides), just point it at an oil price feed instead of a BTC index and re-tune tick/size for the
wider observed spread and lower volume.

**3. KXCPICOREYOY / KXCPIYOY / KXFEDDECISION (Economics: CPI print, Fed rate decision) —
highest edge-per-trade, hardest fair-value model, capacity-capped.** These show the widest
spreads on the whole board (47.5-53.5 ticks on CPI, 10 ticks on FOMC) with thin depth (6.5-34
contracts) — the market is pricing in genuine macro-release uncertainty and nobody is
aggressively narrowing it. But volume is comparatively low (14.7K-117K/24h) and these are
**scheduled, low-frequency events** (CPI monthly, FOMC ~8x/year) that only trade meaningfully in
the hours around the print — no continuous price feed exists to model fair value against; it
needs a macro-nowcasting model (e.g. tracking-estimate-vs-consensus) instead. Highest
edge-per-fill of anything found, but capacity and frequency are the constraints, not spread.

**Bottom line:** nothing scored here beats crypto's own capital efficiency once you account for
its ultra-tight fill rate, but `KXT20MATCH`/cricket is the strongest "wide spread the current
engine's mechanics could exploit *if* it had a sports win-probability model," and `KXWTI` is the
one where the existing fair-value architecture transfers with the least new modeling work.
