# Kalshi Liquidity Census — Non-Weather Long Tail
Run 2026-07-20. Public, unauthenticated `api.elections.kalshi.com/trade-api/v2` only. No orders, no auth.

## Method
1. `GET /series` — full catalog dump, single call, `limit=200` param was ignored by the API and it
   returned the **entire catalog**: **12,022 series** across 18 categories (Sports 2945, Entertainment
   2470, Politics 2059, Elections 1500, Financials 651, Economics 605, Mentions 382, Climate & Weather
   289 [excluded per scope], Sci/Tech 281, Crypto 253, Companies 173, World 143, Health 96,
   Commodities 73, Social 52, Transportation 39, Exotics 10, Education 1).
2. `GET /events?status=open&limit=200`, paginated 40 pages to exhaustion (cursor ran out) →
   **7,937 currently-open events across 2,882 distinct series** (weather excluded). This is the honest
   "what's actually live right now" picture — much smaller than the raw 12k-series catalog, most of
   which is dead/settled tickers.
   - Caveat/lesson learned: `GET /markets?status=open` alone is a trap for a census — its default
     order surfaces combinatorial multi-leg parlay products (`KXMVESPORTSMULTIGAMEEXTENDED`,
     `KXMVECROSSCATEGORY`) that mint tens of thousands of individual market tickers off a handful of
     underlying games. A 60,000-market pull resolved to only 17 distinct series. Switched to
     `/events` for the census layer and `/markets?series_ticker=X` for targeted liquidity pulls.
3. Category breakdown of the **live** landscape: Sports 3666 events, Elections 2221, Entertainment 471,
   Politics 402, Economics 332, Financials 329, Sci/Tech 119, Crypto 87, Companies 67, Mentions 42,
   Commodities 38, Social 9, World 7, Health 6, Transportation 1.
4. Stratified sample: per non-weather category, drew series with exactly 1 open event (deepest tail)
   and series with 2-4 open events (thin-but-multi), plus the top-2-by-event-count per category as a
   HIGH-attention contrast set. **143 unique series** queried via
   `GET /markets?series_ticker=X&status=open&limit=50` (up to 50 live markets each) for real order-book
   stats: `yes_bid`, `yes_ask`, `volume`, `open_interest`.
5. Computed per series: total volume/OI across sampled markets, **% of markets with any trading
   activity** (`vol>0 or oi>0`), and **median spread restricted to genuine two-sided quotes**
   (`0.01 < bid` and `ask < 0.99`, excluding the placeholder 0¢/1¢ default quote that untouched
   far-strike markets sit at — that default is NOT a real tradable spread, just "nobody has quoted
   here yet").
6. Politeness: 0.2-0.5s jitter between calls, exponential backoff on 429 (none triggered across ~185
   total requests).

## HIGH-attention contrast (confirms the thesis — SKIP these)
Top of the sample by volume, all in mainstream/viral series: `KXLLM1` (Best AI 2026) 7.77M contracts
traded, `KXBTCMAXY` 4.08M, `KXIMPEACH` 2.83M, `KXETHMAXY` 2.14M, `KXREDISTRICTING` 1.96M,
`KXDSENATESEATS` 1.77M, `KXCLAUDE` 1.05M, `KXFEDDECISION` 340K. Spreads are 1¢ on virtually all of
these (`KXREDISTRICTING` 1.8¢, `KXU3MAX` 4.2¢ being the widest of the bunch) — textbook tight,
bot-camped, high-OI markets. This matches every prior K-WX finding: contested attention compresses
spreads to the minimum regardless of domain.

## A trap worth flagging: dead shells vs. real thin markets
Some series *look* maximally uncontested (spread ~1¢, zero volume) but are actually **empty shells**,
not opportunities — e.g. `KXBNB`, `KXETH`, `KXXRP`, `KXSHIBA` (crypto strike-grid price-range
markets): every one of 50 sampled strikes sits at the exchange's default `bid=$0.00 / ask=$0.01`
placeholder with **zero volume and zero open interest on 86-100% of strikes**. There is no
counterparty to trade against — this is "nobody has shown up yet," not "wide persistent spread." The
useful long-tail signal is **nonzero volume/OI at a wide real spread** (someone is trading, nobody is
competing on price), not zero-everything.

## Top 15 low-attention series *families* — the hunting ground
Ranked by strength of signal (real activity + genuine wide spread + low competition), not raw volume.
Stats are from the 50-market (or fewer, if series is smaller) live sample per series, 2026-07-20.

| # | Family | Example tickers | Volume (sampled) | OI | Median real spread | Why uncontested |
|---|---|---|---|---|---|---|
| 1 | **Broadcast "mentions" markets** (what will X say on air) | `KXWNBAMENTION`, `KXHEARINGMENTION`, `KXPOLITICSMENTION`, `KXMLBMENTION`, `KXHANNITYMENTION` | 1-6.8K per series | 1-5.9K | **18-71¢** | Resolution requires parsing live speech/transcripts, not a price feed — no API-driven bot edge exists yet; only 10-31 of 50 strikes even traded. |
| 2 | **Slow-moving corporate KPI trackers** | `KXDPZA` (Domino's US store count), `KXRIVN` (Rivian deliveries), `KXTSLA` (production), `KXDRAMAY` (DDR5 spot price) | 2.5-3.9K | 1.1-2.8K | **6-83¢** | Resolves off quarterly/irregular corporate disclosures, not a tick-by-tick feed; `KXDPZA` alone prints an 83¢ median spread with 100% of markets carrying OI — someone's positioned, nobody's quoting tight. |
| 3 | **Brand-new AI/LLM meta markets** | `KXGPT55Y`, `KXOPUS48Y` (input-token-price predictions) | 2.9-5.1K | 1.2-2.8K | **5¢**, 100% of sampled markets traded | Category didn't exist a cycle ago; self-referential to the AI industry itself, no incumbent quant desk has built a model for it yet. |
| 4 | **Foreign/international macro prints** | `KXSARETAIL` (South Africa retail sales), `KXSEMIPRODH` (US semiconductor production growth), `KXCBDECISIONCANADA` (Bank of Canada) | 1.2-9.4K | 0.9-4.7K | **5-16¢**, 53-100% traded | Overshadowed by the mainstream US CPI/FOMC/NFP series that dominate Economics volume; same asset class, zero of the crowd. |
| 5 | **Off-cycle / small-state elections** | `KXMIDTERMMOV`, `KXMIDTERMVOTETURN` (Wyoming Senate), `SENATESD` (South Dakota 2028) | 0.6-9.1K | 0.6-5.2K | **6-8¢** | Low-population-state races get a fraction of the media/liquidity that national or swing-state races (`KXDSENATESEATS`, 1¢ spread) command. |
| 6 | **Novelty / influencer single-shot markets** | `KXBANDANTES`, `KXDONATEMRBEAST`, `KXMICHELINNYC3`, `KXTWITCHSUBSNINJA`, `KXPOPCHANGESTATE10` | 1.2-9.3K | 0.2-2.6K | **2-8¢** | Each is a standalone 1-market series with idiosyncratic, hard-to-model resolution criteria (an internet personality's behavior) — deters systematic/API-driven bots by design. |
| 7 | **Far-future sports meta markets** | `KXSBHOST` (who hosts the 2031 championship), `KXNCAAFQF` (playoff qualifiers) | 0.2-1.4K | 0.2-1.4K | **9-21¢**, only 9-28% of strikes traded | Multi-year horizon kills urgency-driven bot interest; nobody re-quotes a 5-year-out market intraday. |
| 8 | **Foreign / non-flagship sports leagues** | `KXBUNDESLIGA` (Bundesliga champion), `KXELITESERIENSPREAD` (Norwegian Eliteserien) | 2-110 | 2-110 | **4-12¢** | US sports-betting bot infrastructure doesn't extend to European domestic leagues; genuinely thin (only 3-9 of 18-8 strikes traded) but real. |
| 9 | **Esports match/map spreads** | `KXCS2MAP` (CS2 map-by-map) | 1 | 1 | 21.5¢ (n=1 real quote) | New vertical for Kalshi, no dedicated esports MM desk yet; caveat — sample here is thin enough (1 of 50 traded) to need a longer look before trusting the number. |
| 10 | **Niche fixed-income tenors** | `KX2YFOMC` (2Y yield move on FOMC day), `KXUST2AD` (2Y Treasury level), `KXCREDITC` (SOFR) | 1.7-9.1K | 0.9-5.9K | **5-6¢** | Sits in the shadow of the heavily-traded Fed-decision headline market; same rates complex, far less crowd. |
| 11 | **Regulatory/agency approval timing** | `KXFDATYPE1DIABETES`, `KXFDAAPPROVE` (MDMA/PTSD), `KXAVGMEASLESDJT` | 8-9.2K | 4.3-4.7K | **8¢** | Needs domain/regulatory-process knowledge to price, not a market feed — outside the toolkit of a fast-quote bot. |
| 12 | **One-off corporate/political events** | `KXTAKEOVERNEE` (NextEra-Doral takeover), `KXABRAHAMQ` (Israel-Qatar normalization) | 0.03-7.3K | 0.9-2.0K | **3¢+** | Single binary event, no recurring structure for a bot to amortize infrastructure against. |
| 13 | **Fresh altcoin momentum (real, not shell)** | `KXHYPEMAXMON` ("how high will HYPE get"), distinct from the dead `KXBNB/ETH/XRP` strike-grids | 8.8K | 6.1K | **5.5¢**, 100% of sampled markets traded | Real OI/volume exists (unlike the placeholder grids above) but spread is still wide — momentum-style crypto markets on newer/smaller-cap tokens aren't yet arbed as tight as BTC/ETH majors. |
| 14 | **Human-interest / geo narrative markets** | `KXBUSHBY` (Karl Bushby's World Walk finish), `KXEUEXPANSION` (new EU member by 2030) | 5.6-8.3K | 1.3-2.6K | **2-4¢** | Ultra-low-salience, multi-year narrative events; real OI sitting there but nobody re-quotes daily. |
| 15 | **In-broadcast player/statline mentions vs. season-prop crossover** | `KXNFLSEASONRECYDS` (750+ receiving yards season prop) | 1.5K | 1.5K | **13¢**, 21/50 strikes traded | Season-long player props are a much thinner cousin of the heavily-quoted weekly game lines — long horizon + player-specific means most of the strike grid sits unquoted. |

## Bottom line
The pattern holds outside weather too: everywhere Kalshi has genuine cross-venue/price-feed inputs
(BTC/ETH majors, Fed decisions, headline elections, top AI-lab races) spreads compress to 1-2¢ with
six-to-seven-figure volume — that's `KXLLM1`, `KXBTCMAXY`, `KXIMPEACH`, `KXREDISTRICTING`,
`KXFEDDECISION` above. Everywhere resolution requires **either niche domain knowledge, human
judgment/speech parsing, or simply low enough salience that nobody bothers** — mentions markets,
corporate KPI trackers, foreign leagues/macro prints, off-cycle elections, novelty/influencer bets,
far-future meta-markets — spreads sit 5-80¢ wide with real (if thin) two-sided OI. That's the
inventory list to dig into next: pre-register a spec per family (start with #1 Mentions or #2 Corporate
KPI, both show 100%-OI-coverage evidence of standing positions with nobody quoting tight) before any
backtest.

## Limitations (be honest about these before acting on this)
- Single-day, single-timestamp snapshot (2026-07-20) — no persistence check across days/hours yet;
  "persistent" spread claims above are inferred from the fact OI exists (someone traded through the
  wide spread at some point), not from a multi-day time series. A candlestick pull across each
  finalist family is the next step before writing a spec.
- 50-market cap per series sample; series with >50 open markets (e.g., some Mentions/Sports strike
  grids) are under-sampled — genuine spread/volume could differ across the untested strikes.
- Category labels come from Kalshi's own `category` field; some are coarse (e.g., "Mentions" spans
  sports, politics, and news mentions) — families above split them by content, not just the raw field.
- No historical settled-market pull yet (candlesticks / closed-market P&L) — this census establishes
  *where to look*, not *what the edge is worth*; that's `kwx-research-funnel` pre-registration + backtest
  territory next, with a Fable adversarial-verification gate before any claimed edge is trusted.
