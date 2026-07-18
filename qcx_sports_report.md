# QCX (Polymarket US) Sports Efficiency / Mispricing Test

_Generated 2026-07-18T15:54:21.951093+00:00. Venue: QCX / Polymarket US (gateway.polymarket.us)._

## Setup

- QCX settled sports markets pulled: **2599** (all moneyline, Oct 2025-Jan 2026; leagues NFL/NBA/NHL/CFB/CBB/UFC).
- Pre-game executable price = last QCX trade print STRICTLY before `gameStartTime`, reconstructed from book OHLC stats. Markets whose only prints are after kickoff = **live-only, EXCLUDED** (the pregame-vs-live trap).
- Book reference = ESPN de-vigged **closing** moneyline (non-live provider), normalized two-sided to 1.0. Winner cross-checked vs QCX settlement; mismatches dropped.
- Primary analysis set = 'fresh': pre-game print within 6h of kickoff and 0.02<=price<=0.98 (aligns QCX print timing with the closing line).

## Pipeline funnel
```
total           : 2599
live_only       : 833
no_book         : 0
draw            : 1
no_espn         : 960
winner_mismatch : 35
no_odds         : 0
ok              : 757
```
Per-league (n / matched-to-ESPN / usable-with-odds):
```
nfl  : n=  163  matched=   98  ok=   98
nba  : n=  487  matched=  355  ok=  355
cfb  : n=   56  matched=   30  ok=   30
nhl  : n=  319  matched=  252  ok=  252
cbb  : n= 1561  matched=   22  ok=   22
ufc  : n=   13  matched=    0  ok=    0
```

**Usable matched games with de-vigged book line: n = 757 (fresh subset n = 679).**

## Deviation: QCX pre-game price vs de-vigged closing book

**all matched** (n=757): mean dev = +0.0018, mean|dev| = 0.0224, median|dev| = 0.0130, RMSE = 0.0539
  - |dev|>3c: 18.5%   |dev|>5c: 7.4%   |dev|>10c: 1.8%
**fresh** (n=679): mean dev = +0.0006, mean|dev| = 0.0176, median|dev| = 0.0125, RMSE = 0.0273
  - |dev|>3c: 16.2%   |dev|>5c: 5.2%   |dev|>10c: 0.9%

## Sharpness: Brier score (lower = sharper), fresh set

- Brier(QCX)  = 0.2342
- Brier(book) = 0.2308  (n=679)
- Brier(QCX) - Brier(book) = +0.0034 (book sharper)

## Backtest: |dev|>thr -> trade toward book, hold to settle (fresh set)

Net of QCX taker fee 0.06*p*(1-p). Day-clustered t (cluster = game day).

| thr | n | mean edge/contract | day-clust t | n_days | win% | total PnL |
|----:|--:|------------------:|-----------:|------:|-----:|----------:|
| 0.03 | 110 | +0.1063 | +0.69 | 54 | 51.8% | +11.70 |
| 0.05 | 35 | +0.1915 | +1.31 | 24 | 60.0% | +6.70 |
| 0.10 | 6 | +0.4480 | +2.20 | 6 | 83.3% | +2.69 |

Same backtest WITHOUT fees (to isolate whether fees kill it):

| thr | n | mean edge/contract | day-clust t |
|----:|--:|------------------:|-----------:|
| 0.03 | 110 | +0.1193 | +0.93 |
| 0.05 | 35 | +0.2043 | +1.44 |
| 0.10 | 6 | +0.4615 | +2.27 |

Multiple-testing: 3 thresholds tested; apply ~sqrt haircut / require |t|>~2.4 for a single-threshold claim.

## QCX fee schedule (from docs.polymarket.us/fees)

- Taker: **0.06 * p * (1-p)** per contract. Maker rebate -0.0125*p*(1-p).
- Taker fee in cents/contract: {0.5: 0.015, 0.7: 0.0126, 0.8: 0.0096, 0.9: 0.0054} -> **max 1.5c at p=0.50**.
- Volume taker rebates: 10/25/50% for >$250k/$1M/$10M monthly.

## Capacity (matched fresh games, notional traded per market)

- n=679, median $21510.879, mean $77970.04126067746, p90 $247237.142, max $2064877.338 (whole-market lifetime notional).

## Cross-venue

- NOT reconstructable retrospectively: QCX exposes no timestamped historical book, and Kalshi/Global historical books are not aligned to these settled games. Reported as untested.

## VERDICT

- QCX pre-game prints deviate from the closing book by mean|dev| **1.8 cents** (median 1.3c); |dev|>5c on 5% of games. This is comparable to a sub-cent mature-venue tracking error -> QCX prints are noisier.
- Brier(book)=0.231 vs Brier(QCX)=0.234: the closing book is sharper.
- Backtest (fee-net): most-populated threshold n=110 gives mean +0.106/contract, day-clustered t=+0.69 -> NOT significant. No adequately-powered (n>=30) threshold clears |t|>2.4.
- The only threshold with |t|>2 (t=+2.20) has n=6 trades -- underpowered, dies under the 3-threshold multiple-testing haircut. Not credible.
- **KEY CAVEAT (look-ahead):** the 'edge' compares a QCX print (median a couple hours pre-game) to the EVENTUAL closing line. Trading toward the closing line requires knowing it in advance; part of any raw gap is just closing-line-value (the later, sharper line), NOT a real-time exploitable mispricing. Treat a positive backtest as an UPPER BOUND.

**BLUNT: NULL (fee-surviving edge not demonstrated).** The new QCX venue's pre-game prices are NOISIER than a mature venue (wider dispersion vs the closing line, thin books), consistent with a young sports venue. But that dispersion is symmetric noise, not a systematic mispricing: the closing book is at least as sharp (Brier), and once the QCX taker fee (up to 1.5c at p=0.5) is charged, the deviation-chasing backtest does not clear a day-clustered significance bar. Even the raw (no-fee, look-ahead-inflated) signal is the ceiling. Consistent with the prior sportsbook null: legal QCX sports are not a free lunch.
