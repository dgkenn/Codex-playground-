# Polymarket sports vs sportsbook (de-vigged) — mispricing test

**Date:** 2026-07-18 · **Script:** `pmkt_sportsbook.py` · **Summary JSON:** `pmkt_sportsbook_summary.json`

## Question
Is Polymarket's price on team-vs-team moneyline markets mispriced relative to the
de-vigged sportsbook line, such that buying the book-favored side is +EV? Prior:
sharp/consensus books beat retail prediction markets on sports.

## Data & method
- **Book (truth proxy):** ESPN core API `.../events/<id>/competitions/<id>/odds`.
  This returns a **single book — DraftKings — not a consensus/sharp (Pinnacle) line.**
  Moneyline → implied prob → **de-vig** by normalizing the two sides to sum to 1.
- **Polymarket:** gamma `events?slug=<league>-<away>-<home>-<date>` (slug order = away, home;
  outcomes `[away_name, home_name]`). Live = `bestBid`/`bestAsk`. For settled games gamma only
  stores the 0/1 resolution, so pre-game price came from the **CLOB `prices-history`** endpoint
  (hourly mid): P_poly = last mid at/before `gameStartTime`.
- **Matching (conservative):** slug built from ESPN abbreviations (with a small fallback map
  e.g. `ath/oak`, `chw/cws`); a match is accepted **only if** the two PM outcome names share the
  team nickname with the ESPN away/home names, in the correct order. Wrong-order or name-mismatch → rejected.
- **Coverage:** MLB (baseball/mlb) finals **Jul 9–12, 14, 17** + upcoming Jul 17–19; WNBA (basketball/wnba)
  finals Jul 9–16 + upcoming. Mid-July is the **MLB All-Star break**, so Jul 13–16 had ~0 MLB games.
- **In-progress games excluded** from the live snapshot (PM reflects live game state while the book
  field is the pregame line — not comparable).
- **Execution:** measured live PM spread is a uniform **1¢**; backtest buys the underpriced side at
  **mid + 0.5¢** (half-spread), zero PM fee, hold to resolution. PnL = outcome − executed price.

## Matched sample
- **88 matched games** (MLB + WNBA); **68 backtestable finals**, **19 scheduled-live**.
- Unmatched: 9 no-PM-slug, 1 name-mismatch — i.e. match rate ~90%, no accepted wrong matches.
- Example matches: `bos@nym` DK(123,-148)→P_book_away 0.446; `ari@lad` DK(168,-205)→0.363; all with PM outcome names verified.

## Deviation distribution  (P_poly − P_book, away side)
| set | n | mean \|dev\| | median \|dev\| | %>3¢ | %>5¢ | %>10¢ | max \|dev\| |
|---|---|---|---|---|---|---|---|
| **finals** (mid at game start) | 68 | **0.95¢** | 0.60¢ | 2.9% | 1.5% | 0% | 8.0¢ |
| **live scheduled** (bid/ask mid) | 19 | **0.76¢** | 0.61¢ | 0% | 0% | 0% | 1.7¢ |

Polymarket's pre-game price tracks the de-vigged DraftKings line to **under one cent on average —
tighter than the market's own 1¢ bid/ask spread.** Deviations above 5¢ are rare (1.5% of finals) and
none of them are systematic.

## Calibration (Brier, away outcome, 68 finals)
- **Brier(book) = 0.2429**  vs  **Brier(poly) = 0.2452**.
- The book is marginally better (Δ = 0.0023), consistent with the prior direction, but both sit at
  ~0.25 (MLB single-game outcomes are near coin-flips and noisy) and n = 68 is far too small to call
  this distinguishable. Even taking it at face value, PM does not deviate from the book enough to exploit.

## Backtest (trade toward the book when |dev| > threshold; day-clustered)
| threshold | trades | mean PnL | win rate | t (per-trade) |
|---|---|---|---|---|
| 3¢ | **2** | +0.205 | 0.50 | 0.58 |
| 5¢ | **1** | +0.56 | 1.00 | n/a |
| 10¢ | **0** | — | — | — |

The strategy essentially **never triggers**: with mean deviation <1¢, only 2 of 68 games cross a 3¢
gate and 0 cross 10¢. The nonzero PnLs are 1–2 observations — pure noise, no t-stat, no signal.

## Verdict — BLUNT
**Null. Polymarket already tracks the sportsbook line; there is no tradeable mispricing here.**

On liquid MLB (and WNBA) moneyline markets, Polymarket's pre-game price equals the de-vigged
DraftKings line to sub-cent precision — closer than its own 1¢ spread — both measured at game time
(finals) and pre-game (scheduled). The book is at best a hair better calibrated (Brier 0.243 vs 0.245,
n=68, not significant), but PM's deviations from it are smaller than the round-trip trading cost, so the
"buy the book-favored side" strategy has no games to trade. The retail-mispricing prior is **rejected**
for these markets.

**Why no edge, and what would be needed:**
- To profit you must find games where PM is *wrong*. PM matches DraftKings to <1¢, so beating PM
  requires a line **sharper than DraftKings** by more than ~1¢ + fees. ESPN only exposes DraftKings,
  not Pinnacle/consensus; the free data literally cannot resolve errors at the scale PM makes them.
- The only large gaps observed were an artifact: **in-progress** games (PM live price vs pregame book) —
  excluded once identified. That is a data-hygiene trap, not an edge.
- A residual structural quirk: PM away-side mid runs ~0.5–1¢ *below* the de-vig book on many games,
  but it is inside the spread and vanishes after paying the half-spread — not exploitable.

**Capacity:** moot. (Per-game PM liquidity ~$10–58k, 1¢ books; even a real edge would be small.)

**Caveats:** single book (DraftKings), not a sharp consensus; n=68 finals over ~5 trading days;
backtest P_poly is hourly CLOB *mid* (not historical bid/ask, which PM doesn't expose) plus an assumed
0.5¢ half-spread calibrated from current live books.
