# Ladder arbitrage: is the KXBTCD threshold ladder ever quoted crossed?  (LADDER_ARBITRAGE_SPEC.md, executed)

**VERDICT: INSUFFICIENT**  (frozen PASS/KILL rule applied verbatim; numbers beside each bar in section 8)

Universe: 503 KXBTCD hours (prefix of the saved seed-20261027 order, never re-sorted), 60 UTC days, 27,953 candle-minutes, 2,229,166 strike-minutes with a candle (1,286,997 two-sided). KXBTC (Parts B, C) coverage: 503 of 503 hours (100.0%, 60 days; completed set is a contiguous prefix of the order).

## 0. Plain reading (written from the tables below)

* **On simultaneous quotes the ladder is never crossed by enough to matter.** `close` reading: 6 raw crossings (bid(K2) > ask(K1)) in 5 minutes out of 1,764,729 executable pair-observations; the largest was 1c, and fees on two legs are at least 2c, so **0 are fee-clearing** (need a crossing of >= 3c). The `carried` reading (each strike's last close carried across minutes in which it did not change, valid because the candle stream is change-driven: next candle's open == previous candle's close in 100.000% of 620,859 gaps across no-candle minutes, 99.889% of 1,515,747 adjacent minutes) gives the same 6 / 0.
* **The high/low construction manufactures 8,194 'fee-clearing violations' (1,043 per-minute-max opportunities on 59 days, median net 5c, both legs traded in 99.1%) out of the same data.** Their COUNT is a within-minute timing artifact: bid.high of one strike and ask.low of another are different instants. Anchor (e) says that is a finding, and it is (section 2.3 says what real, brief crossings sit underneath it).
* Tape check of a seeded sample of 250 of those 1,043 high/low opportunities: tape-inverted (L2) 48 of 250 (19.2%), side-correct (L3) 38.
* **Part C (3 legs, KXBTC range vs two KXBTCD strikes) is the only place a simultaneous reading finds anything:** 31 fee-clearing `close` rows = 28 opportunities on 15 days out of 482,438 tested leg-triples, median net 1.0c after three fees, all three legs traded in 32.1%, tape-confirmed (L2) 8/28 (28.6%). Far below every PASS bar; the study verdict is INSUFFICIENT.
* **Caveat the snapshot verdict does not remove:** inside 27 of 250 sampled high/low minutes the tape shows a K1-lifted / K2-hit pair at inverted, fee-clearing prices within 100 ms of each other (section 2.3). Brief crossings exist while the 188 strikes are re-quoted; they are not visible at minute-end and, judging by the timestamps, are consumed by faster participants. That is a latency game, not the no-speed arbitrage the spec premised.

## 1. Anchor (e): simultaneity disclosure -- FIRST, because it decides whether anything else means anything

Part A, all ordered strike pairs K1 < K2, every minute, 503 hours.  Buy YES(K1) at yes_ask, sell YES(K2) at yes_bid.  Net = bid(K2) - ask(K1) - fee(ask) - fee(bid), cents.  'Opportunity' = the maximum-net fee-clearing pair of a minute (the spec's scan unit); 'pairs' counts every fee-clearing pair.

| reading | simultaneous? | can PASS? | executable pair-observations tested | raw crossings (pairs / minutes / hours) | largest raw crossing | fee-clearing pairs | fee-clearing opportunities (minutes) | days | median net (opportunity / pair) | max net |
|---|:--:|:--:|--:|---|--:|--:|--:|--:|---|--:|
| `close`, every leg, same candle (PRIMARY) | yes | yes | 1,764,729 | 6 / 5 / 5 | 1c | **0** | **0** | 0 | n/a / n/a | n/a |
| `close` carried across unchanged minutes (disclosure; not in spec) | yes (state) | NO | 1,784,461 | 6 / 5 / 5 | 1c | **0** | **0** | 0 | n/a / n/a | n/a |
| bid.HIGH(K2) vs ask.LOW(K1), same minute (**NON-SIMULTANEOUS**) | NO | NO | 2,023,217 | 18,036 / 2,287 / 338 | 94c | **8,194** | **1,043** | 59 | 5c / 4.00c | 92 |

**Reading: the apparent opportunity is a within-minute timing artifact.** The same minutes, the same quotes, give 8,194 fee-clearing pairs when two different instants are compared and **zero** when one instant is. That is the finding.

How close does the simultaneous ladder come to being crossed?  Per minute, max over K1 < K2 of bid(K2) - ask(K1) (cents), minutes with at least one executable pair:

| reading | <= -10 | -9..-5 | -4..-2 | -1 | 0 | >= +1 | minutes |
|---|--:|--:|--:|--:|--:|--:|--:|
| close | 3,345 | 2,944 | 10,942 | 9,361 | 1,247 | 5 | 27,844 |
| carried | 3,345 | 2,938 | 10,913 | 9,312 | 1,331 | 5 | 27,844 |
| hilo | 1,977 | 1,875 | 7,302 | 10,338 | 4,126 | 2,287 | 27,905 |

(`0` = locked, bid(K2) = ask(K1); `>= +1` = crossed, but not necessarily by enough to pay 2-4c of fees.)

Why the high/low crossing is not real (the 1,043 per-minute-max high/low opportunities, looked at through the close): median bid.high - bid.close of the sold leg = 8c, median ask.close - ask.low of the bought leg = 9c; median claimed (high/low) credit 8c versus median close-to-close gap bid(K2) - ask(K1) = -11c. Share of those minutes that are crossed at the close: 0.0%; share at least 1c uncrossed at the close: 98.9%. On the tape sample, the instant of K2's highest print and of K1's lowest print are a median 38.0s apart (92% more than 2s apart; n=249).

## 2. Part A: 2-leg ladder spread (KXBTCD only)

### 2.1 Primary (`close`, simultaneous)

* Fee-clearing violations: **0** (opportunities 0, days 0). Median net, per-day concentration, volume on both legs and tape-confirmation rate are therefore **undefined (0 / 0)**.
* The fee arithmetic, concretely: raw crossings exist (6), each exactly 1c; at the prices where they occur the two legs pay the fee shown below, so every one nets negative:

| K1 (buy at ask) | ask | traded vol (candle) | K2 (sell at bid) | bid | traded vol (candle) | fee buy + fee sell | net |
|---|--:|--:|---|--:|--:|--:|--:|
| KXBTCD-26SEP1109-T77399.99 | 16 | 7,654 | KXBTCD-26SEP1109-T77499.99 | 17 | 5,707 | 1 + 1 | -1 |
| KXBTCD-26SEP3010-T84899.99 | 9 | 768 | KXBTCD-26SEP3010-T84999.99 | 10 | 677 | 1 + 1 | -1 |
| KXBTCD-26OCT0209-T87399.99 | 9 | 22,200 | KXBTCD-26OCT0209-T87599.99 | 10 | 11,776 | 1 + 1 | -1 |
| KXBTCD-26OCT0209-T87499.99 | 9 | 27,991 | KXBTCD-26OCT0209-T87599.99 | 10 | 11,776 | 1 + 1 | -1 |
| KXBTCD-26SEP1111-T80899.99 | 8 | 169 | KXBTCD-26SEP1111-T80999.99 | 9 | 702 | 1 + 1 | -1 |
| KXBTCD-26SEP2811-T82199.99 | 98 | 8,724 | KXBTCD-26SEP2811-T82399.99 | 99 | 26,526 | 1 + 1 | -1 |

Tape (GET /markets/trades) for these 6 raw crossings (not fee-clearing, so nothing 'survives' to confirm; shown because the spec requires the check wherever a crossing is claimed): both legs printed in the minute 6, fee-clearing printed inversion within 2 s (L2) 2, side-correct (L3) 1.

| K1 | K2 | end_ts | prints K1 / K2 | tape vol K1 / K2 | candle vol K1 / K2 | L1 | L2 | L3 |
|---|---|--:|--:|--:|--:|:--:|:--:|:--:|
| KXBTCD-26SEP1109-T77399.99 | KXBTCD-26SEP1109-T77499.99 | 1789130040 | 55 / 61 | 7,654 / 5,707 | 7,654 / 5,707 | True | True | False |
| KXBTCD-26SEP3010-T84899.99 | KXBTCD-26SEP3010-T84999.99 | 1790775660 | 37 / 33 | 768 / 677 | 768 / 677 | True | False | False |
| KXBTCD-26OCT0209-T87399.99 | KXBTCD-26OCT0209-T87599.99 | 1790944320 | 120 / 62 | 22,200 / 11,776 | 22,200 / 11,776 | True | False | False |
| KXBTCD-26OCT0209-T87499.99 | KXBTCD-26OCT0209-T87599.99 | 1790944320 | 100 / 62 | 27,991 / 11,776 | 27,991 / 11,776 | True | True | True |
| KXBTCD-26SEP1111-T80899.99 | KXBTCD-26SEP1111-T80999.99 | 1789135440 | 16 / 12 | 169 / 702 | 169 / 702 | True | False | False |
| KXBTCD-26SEP2811-T82199.99 | KXBTCD-26SEP2811-T82399.99 | 1790607240 | 46 / 159 | 8,724 / 26,526 | 8,724 / 26,526 | True | False | False |

### 2.2 `hilo` (NON-SIMULTANEOUS; reported only to size the artifact; cannot PASS)

* Fee-clearing pairs 8,194; opportunities (per-minute max) 1,043 on 59 of 60 days and 273 hours; median net 5c (pairs 4.00c), max net 92c.
* Concentration: busiest day 2026-08-25 = 6.4% of opportunities; busiest hour KXBTCD-26SEP1515 = 2.7%.
* Traded volume in the violating minute (UPPER BOUND on size only; candles carry no depth; realisable size is UNKNOWN): median leg volumes 5306 / 5402 contracts; both legs non-zero in 1,034 (99.1%); zero-volume leg (doubtful fill) in 9.
* Tape on a seeded random sample (250 opportunities, seed 20261028; the full 1,043 were not pulled because of API rate limits): both legs printed in the minute (L1) 249/250 (99.6%); fee-clearing printed inversion within 2 s (L2) 48/250 (19.2%); side-correct (L3) 38/250.
* Tape volume check: of 256 leg-pairs, tape volume equals candle volume on both legs in 256 (the validated MAKER_FILL result holds).

### 2.3 What the tape shows INSIDE the minute (disclosure; outside the frozen bars)

The candle `close` sees the state at the end of each minute. The tape sees every print with a microsecond stamp. For the 250 sampled high/low opportunities I looked for a print on K1 and a print on K2 whose PRINTED prices clear fees (p2 - p1 - fee(p1) - fee(p2) >= 1c), and measured the smallest time gap between such a pair. L2 above used the frozen 2 s tolerance; the table is the same test at tighter tolerances (sensitivity, not a selection):

| |Dt| <= | 0.01s | 0.1s | 0.5s | 1s | 2s | 10s | 60s |
|---|--:|--:|--:|--:|--:|--:|--:|
| any taker sides (of 250) | 24 | 37 | 42 | 43 | 48 | 72 | 225 |
| K1 lifted (taker yes) AND K2 hit (taker no) | 19 | 27 | 30 | 32 | 38 | 54 | 187 |

Tightest side-correct pairs (a real taker bought K1 at its ask and a real taker sold K2 at its bid, milliseconds apart, at inverted prices):

| K1 | p1 (c) | size1 | K2 | p2 (c) | size2 | gap | printed net after fees (c) |
|---|--:|--:|---|--:|--:|--:|--:|
| KXBTCD-26AUG2609-T77499.99 | 85 | 3 | KXBTCD-26AUG2609-T77699.99 | 98 | 3 | 0.0 ms | 11 |
| KXBTCD-26AUG2303-T75299.99 | 89 | 50 | KXBTCD-26AUG2303-T75399.99 | 95 | 50 | 0.0 ms | 4 |
| KXBTCD-26AUG2201-T79099.99 | 3 | 1 | KXBTCD-26AUG2201-T79199.99 | 7 | 10 | 0.0 ms | 2 |
| KXBTCD-26OCT0209-T86799.99 | 15 | 1 | KXBTCD-26OCT0209-T86899.99 | 19 | 26 | 0.1 ms | 1 |
| KXBTCD-26AUG2409-T79499.99 | 4 | 20 | KXBTCD-26AUG2409-T79599.99 | 7 | 10 | 0.1 ms | 1 |
| KXBTCD-26AUG2203-T78699.99 | 2 | 5 | KXBTCD-26AUG2203-T78799.99 | 5 | 5 | 0.1 ms | 1 |
| KXBTCD-26AUG2502-T81199.99 | 2 | 50 | KXBTCD-26AUG2502-T81899.99 | 6 | 10 | 0.2 ms | 2 |
| KXBTCD-26SEP2120-T87099.99 | 3 | 14 | KXBTCD-26SEP2120-T87199.99 | 6 | 14 | 0.2 ms | 1 |

**This qualifies the artifact reading honestly.** The high/low COUNT is an artifact (it mixes instants), and the simultaneous end-of-minute snapshot is never crossed. But inside 10.8% of the sampled high/low minutes (27/250) the tape contains a pair of opposite-side takes (K1 bought at its ask, K2 sold at its bid) at inverted fee-clearing prices within 100 ms -- consistent with someone running this arbitrage at millisecond speed (several pairs have equal sizes on both legs and the same microsecond), during a BTC move when the 188 strikes are re-quoted one after another. So crossings do appear to exist, transiently; they are gone by the next minute-end and are consumed by participants far faster than anything the spec's 'no speed' premise allows. The bars are about simultaneous snapshots and they are not met; this paragraph does not move them. For scale (sample-based, not a measurement of the full set): 10.8% of the 1,043 high/low minutes would be about 113 minutes in 60 days. Whether any of that is capturable from here is a latency question this study does not address; the repo's `out/bench_transport.json` puts proxy-inclusive request round trips from this environment at ~55-65 ms median, i.e. not competitive with gaps of a few ms.


Gates evaluated on each reading (hilo shown only to show what it would claim; it cannot PASS):

| reading | >=100 opp. on >=20 days | tape >= 50% | median net >= +2.0c | >=50% non-zero vol both legs | no day/hour > 25% | PASS-eligible result |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| close | False | False | False | False | False | no |
| carried | False | False | False | False | False | no |
| hilo | True | False | True | True | True | not eligible (non-simultaneous) |

## 3. Part B: KXBTC partition-sum diagnostic (NOT a strategy)

The 188 KXBTC markets (186 `between` $100 ranges + a `less` and a `greater` tail) pay exactly 100c in total in every state. Buying all 188 costs sum(yes_ask) plus >= 1c fee per leg priced 1..99c; selling all 188 receives sum(yes_bid) and owes 100c. The dutch book is **not tested** (>= 188 legs of fees, spec: dead by arithmetic); only how far the sums sit from 100c is reported. Coverage: 503 of 503 hours. No mid is formed: only the ask-sum and the bid-sum, which bracket 100.

| reading | minutes with all 188 legs observed | hours | sum(yes_ask) p5 / median / p95 / min | sum(yes_bid) p5 / median / p95 / max | minutes with sum(ask) < 100 | minutes with sum(bid) > 100 | gross buy-all profit > fees (minutes) | gross sell-all profit > fees (minutes) | fee to buy all 188, median (c) |
|---|--:|--:|---|---|--:|--:|--:|--:|--:|
| strict | 185 | 175 | 401 / 2055 / 9218 / 177 | 53 / 78 / 93 / 101 | 0 | 1 | 0 | 0 | 191 |
| carried | 27,137 | 503 | 287 / 430 / 2210 / 146 | 73 / 89 / 97 / 116 | 0 | 60 | 0 | 3 | 190 |

Reading: `strict` = all 188 legs have a candle in the same minute (in practice only the opening minutes); `carried` = last close carried forward (27,137 minutes). On the carried reading the cost of buying the whole partition at the ask is 287-2210c (p5-p95; minimum 146c) against a payout of exactly 100c, so it is never a gross profit: the 1c tick floor on ~190 mostly-dead strikes makes every leg cost at least 1c. The proceeds from selling only the legs that have a bid are 73-97c (p5-p95; maximum 116c) against a maximum liability of 100c (one winner). It exceeds 100c in 60 of 27,137 minutes. The spec's 'dead by arithmetic' is exact for BUYING the partition (188 legs) but NOT for SELLING it: only the ~3-10 bid-bearing legs are sold and pay fees, so the fee floor on that side is ~3-10c, not 100c. After the fee on each sold leg, 3 minutes are positive: KXBTCD-26AUG2901 @ 1787977740 (bids sum 115c over 6 legs, fees 9c, net 6c), KXBTCD-26AUG2901 @ 1787977800 (bids sum 113c over 7 legs, fees 10c, net 3c), KXBTCD-26AUG2901 @ 1787977860 (bids sum 116c over 6 legs, fees 9c, net 7c). These are carried-state diagnostics, not a tested strategy and not tape-checked (the spec forbids testing the partition as a strategy); in that hour one of the sold legs, a range roughly $800 out of the money, is quoted 18c bid / 24c ask and shows no new candle in two of the three minutes, i.e. it looks like a stale quote, which is what would make the 'crossing' disappear. A low-leg-count partition sell is the one place this diagnostic points beyond the spec; it is 3 minutes of 27,137 and one hour of 503.

## 4. Part C: 3-leg cross-series (KXBTC range vs KXBTCD pair, same hour)

R[f, f+99.99] pays exactly when KXBTCD(>f-0.01) pays and KXBTCD(>f+99.99) does not, so R = D_lo - D_hi. C1: long R (ask), short D_lo (bid), long D_hi (ask). C2: short R (bid), long D_lo (ask), short D_hi (bid). Payoff is 0 in every state (verified in 5), net = credit - 3 fees (>= 3c). 90,186 of 91,554 `between` ranges map onto two KXBTCD strikes. Coverage 503 of 503 hours (100.0%); only the covered prefix is scanned.

| reading | can PASS? | leg-triples tested | raw credits > 0 | largest credit | fee-clearing (C1 / C2) | opportunities (minutes) | days | median net | all 3 legs non-zero vol |
|---|:--:|--:|--:|--:|---|--:|--:|--:|--:|
| `close`, simultaneous (PRIMARY) | yes | 482,438 | 15,736 | 20c | 31 (9 / 22) | 28 | 15 | 1.00 | 9 |
| carried close (disclosure) | NO | 501,544 | 15,809 | 20c | 33 (11 / 22) | 29 | 15 | 1 | 9 |
| high/low (NON-SIMULTANEOUS) | NO | 511,004 | 277,085 | 97c | 134,381 (64938 / 69443) | 46,274 | 60 | 5.00 | 32,830 |

### 4.1 Part C `close` survivors (31 fee-clearing rows = 28 per-minute-per-construction opportunities, 15 days, 18 hours)

* Net per 3-leg construction: median 1.00c (opportunities) / 1c (rows), max 16c. Every net is after three fees (>= 3c). Busiest day 2026-09-07 = 25.0% of opportunities; busiest hour KXBTCD-26SEP0700 = 25.0%.
* Traded volume in the violating minute (UPPER BOUND; no depth; realisable size UNKNOWN): all three legs non-zero in 9 of 28 (32.1%); at least one leg with zero volume (doubtful fill) in 19. The KXBTC range leg is the usual zero: it printed nothing in 19 of the 28 minutes.
* **Tape (GET /markets/trades), every one of the 31 rows, none selected** (L1 all three legs printed in the minute; L2 prints on all three legs within 2 s whose printed prices clear fees; L3 side-correct): opportunities L1 9/28, **L2 8/28 (28.6%)**, L3 7/28; rows L1 10/31, L2 9/31, L3 8/31. The other 20 opportunities are quote-only: at least one leg did not print in that minute, so the tape can neither confirm nor refute the end-of-minute quote.

| cons | KXBTC range R | minute end_ts | credit | net | candle vol R / D_lo / D_hi | prints R / D_lo / D_hi | L1 | L2 | L3 | opportunity |
|---|---|--:|--:|--:|---|---|:--:|:--:|:--:|:--:|
| C2 | KXBTC-26SEP1109-B77450 | 1789130040 | 4 | 1 | 187 / 7,654 / 5,707 | 11 / 55 / 61 | True | True | True | True |
| C2 | KXBTC-26AUG2423-B79750 | 1787624280 | 4 | 1 | 4,483 / 18,207 / 31,883 | 67 / 197 / 269 | True | True | True | False |
| C2 | KXBTC-26AUG2423-B79950 | 1787624280 | 9 | 4 | 4,283 / 37,879 / 36,277 | 35 / 257 / 269 | True | True | True | True |
| C2 | KXBTC-26AUG3018-B78850 | 1788126060 | 4 | 1 | 0 / 1,134 / 980 | 0 / 15 / 10 | False | False | False | True |
| C2 | KXBTC-26AUG3018-B78850 | 1788126180 | 4 | 1 | 0 / 2,325 / 351 | 0 / 23 / 6 | False | False | False | True |
| C2 | KXBTC-26AUG3018-B78850 | 1788126300 | 4 | 1 | 0 / 861 / 250 | 0 / 12 / 4 | False | False | False | True |
| C2 | KXBTC-26SEP1601-B75750 | 1789532580 | 7 | 2 | 0 / 3,957 / 3,662 | 1 / 31 / 63 | True | True | True | True |
| C1 | KXBTC-26OCT0220-B84350 | 1790982060 | 7 | 4 | 0 / 831 / 333 | 0 / 14 / 9 | False | False | False | False |
| C1 | KXBTC-26OCT0220-B84650 | 1790982060 | 20 | 16 | 0 / 992 / 400 | 0 / 12 / 9 | False | False | False | True |
| C1 | KXBTC-26OCT0220-B84750 | 1790982060 | 6 | 3 | 0 / 400 / 1,973 | 0 / 9 / 22 | False | False | False | False |
| C2 | KXBTC-26SEP1306-B76450 | 1789292160 | 5 | 2 | 3 / 2,799 / 24,394 | 2 / 23 / 134 | True | False | False | True |
| C1 | KXBTC-26AUG2516-B79050 | 1787687700 | 4 | 1 | 982 / 39,723 / 4,296 | 15 / 199 / 51 | True | True | True | True |
| C2 | KXBTC-26AUG2516-B78950 | 1787687700 | 8 | 3 | 1,823 / 20,252 / 39,723 | 37 / 271 / 199 | True | True | True | True |
| C2 | KXBTC-26SEP0923-B78250 | 1789007280 | 4 | 1 | 0 / 1,680 / 393 | 0 / 20 / 6 | False | False | False | True |
| C2 | KXBTC-26SEP0923-B78150 | 1789008600 | 4 | 1 | 75 / 16,434 / 14,644 | 2 / 111 / 223 | True | True | False | True |
| C1 | KXBTC-26AUG2308-B77250 | 1787485980 | 7 | 1 | 1 / 5,019 / 2,409 | 1 / 105 / 47 | True | True | True | True |
| C2 | KXBTC-26OCT1105-B82850 | 1791706440 | 4 | 1 | 0 / 917 / 718 | 0 / 6 / 22 | False | False | False | True |
| C1 | KXBTC-26SEP0700-B79650 | 1788750840 | 6 | 1 | 0 / 1,814 / 5,190 | 0 / 29 / 57 | False | False | False | True |
| C2 | KXBTC-26SEP0700-B80050 | 1788751740 | 4 | 1 | 0 / 715 / 39 | 0 / 16 / 4 | False | False | False | True |
| C2 | KXBTC-26SEP0700-B80050 | 1788751800 | 4 | 1 | 0 / 414 / 879 | 0 / 8 / 7 | False | False | False | True |
| C2 | KXBTC-26SEP0700-B80050 | 1788751920 | 4 | 1 | 0 / 1,357 / 5 | 0 / 9 / 1 | False | False | False | True |
| C2 | KXBTC-26SEP0700-B80050 | 1788751980 | 5 | 2 | 0 / 1,826 / 462 | 0 / 21 / 12 | False | False | False | True |
| C2 | KXBTC-26SEP0700-B80050 | 1788752040 | 4 | 1 | 0 / 1,994 / 30 | 0 / 21 / 6 | False | False | False | True |
| C2 | KXBTC-26SEP0700-B80050 | 1788752100 | 4 | 1 | 0 / 1,398 / 1,233 | 0 / 16 / 11 | False | False | False | True |
| C2 | KXBTC-26SEP0802-B78450 | 1788844740 | 4 | 1 | 0 / 322 / 1,348 | 0 / 6 / 18 | False | False | False | True |
| C1 | KXBTC-26AUG2300-B76950 | 1787456580 | 6 | 1 | 1,202 / 24,643 / 21,432 | 63 / 298 / 192 | True | True | True | True |
| C1 | KXBTC-26AUG2201-B78850 | 1787373540 | 6 | 2 | 0 / 5,067 / 2,918 | 0 / 85 / 25 | False | False | False | True |
| C1 | KXBTC-26AUG3104-B78150 | 1788162120 | 10 | 4 | 0 / 1,196 / 6,911 | 0 / 24 / 63 | False | False | False | True |
| C2 | KXBTC-26SEP0307-B77650 | 1788432180 | 4 | 1 | 0 / 427 / 378 | 0 / 13 / 6 | False | False | False | True |
| C2 | KXBTC-26OCT0106-B83950 | 1790847420 | 4 | 1 | 0 / 267 / 649 | 0 / 13 / 13 | False | False | False | True |
| C2 | KXBTC-26SEP0313-B81850 | 1788451440 | 5 | 2 | 0 / 904 / 796 | 0 / 13 / 8 | False | False | False | True |

Anchor (d) for Part C: five of these re-parsed from the raw candle JSON (R from the KXBTC cache, D legs from the KXBTCD cache), exact side and price of each leg, fee recomputed with `math.ceil`:

| cons | event | minute end_ts | leg 1 | leg 2 | leg 3 | fees | credit | net |
|---|---|--:|---|---|---|---|--:|--:|
| C2 | KXBTCD-26SEP1109 | 1789130040 | SELL R at yes_bid 3c | BUY D_lo at yes_ask 16c | SELL D_hi at yes_bid 17c | [1, 1, 1] | 4 | 1 |
| C2 | KXBTCD-26AUG2423 | 1787624280 | SELL R at yes_bid 9c | BUY D_lo at yes_ask 82c | SELL D_hi at yes_bid 82c | [1, 2, 2] | 9 | 4 |
| C2 | KXBTCD-26AUG3018 | 1788126060 | SELL R at yes_bid 11c | BUY D_lo at yes_ask 10c | SELL D_hi at yes_bid 3c | [1, 1, 1] | 4 | 1 |
| C2 | KXBTCD-26AUG3018 | 1788126180 | SELL R at yes_bid 11c | BUY D_lo at yes_ask 9c | SELL D_hi at yes_bid 2c | [1, 1, 1] | 4 | 1 |
| C2 | KXBTCD-26AUG3018 | 1788126300 | SELL R at yes_bid 11c | BUY D_lo at yes_ask 9c | SELL D_hi at yes_bid 2c | [1, 1, 1] | 4 | 1 |

## 5. Anchors

**(a) No outcome in the P&L path.** AST scan passed on `arb_net`, `arb_net3`, `pair_scan`, `scan_hour`, `scan_C_hour`, `partition_hour`, `gap_scan`, `kd_load`, `kx_load`, `build_arrays`, `hour_grid`, `c100`, `universe_hours`, `kx_hours`: none references any identifier or string constant containing 'result', 'expiration', 'settle' or 'official'. The whole 2-leg credit is `arb_net(ask_k1, bid_k2)` -- signature ['ask_k1', 'bid_k2'], integers only, so it cannot see an outcome. The scan writes its violation rows (`violations.json`) before any `results.json` is opened; `results.json` is read only by the `verify_*` functions below, after the scan. If the profit needed the outcome it would not be an arbitrage; here it does not. Negative controls (the scan must raise on a doctored copy of this module): {'outcome_string_in_pair_scan': "caught: anchor (a): pair_scan references an outcome: {'results.json'}", 'mid_identifier_in_arb_net': "caught: anchor (d): identifier containing 'mid'", 'bid_ask_halved_anonymous': 'caught: anchor (d): possible mid at line 222'}.

**(b) Payoff dominance.** Against the official settlement, for ALL 18,048 violation rows ever produced (6 close, 18,036 high/low, 6 carried; 0 skipped for a missing official yes/no): realised payoff of long YES(K1) / short YES(K2) = +100 in 1,644, 0 in 16,404, **negative in 0** (minimum 0). Note the spec's sample (>= 20 violations) cannot be drawn from fee-clearing `close` violations because there are none; the check was therefore run on every raw crossing, close and high/low, which is a strictly larger set. No negative payoff: the construction is right.
Part C constructions: realised payoff exactly 0 in 15,736 of 15,736 close rows checked (0 non-zero).

**(c) Monotonicity on settled outcomes.** 503 KXBTCD hours, 92,560 strikes with an official yes/no: hours with a YES above a NO (interleaving): **0** . Second form (every strike below `expiration_value` YES, every strike above NO), on the 503 hours for which a fresh KXBTCD listing was pulled with the KXBTC fetch: 92,560 strikes, **0 mismatches** . Exclusions: none.
KXBTC partition check: 503 hours, hours without exactly one YES among the 188 markets: **0** .

**(d) No mid, executable sides only.** AST scan: no identifier containing 'mid' in any function other than the checker, no division/multiplication by 2 or 0.5 over an expression mixing bid- and ask-named values (66 Div/Mult nodes inspected), and `pair_scan` builds the buy cost from the ask row only and the sell proceeds from the bid row only. Ten violations re-parsed from the raw candle JSON (independently of `build_arrays`; the 6 `close` raw crossings first, then 4 high/low), with the exact yes_ask bought and yes_bid sold, and the fee recomputed with `math.ceil` directly:

| reading | K1 (BUY at yes_ask) | yes_ask used | (its close / low) | K2 (SELL at yes_bid) | yes_bid used | (its close / high) | credit | fee buy / sell | net |
|---|---|--:|---|---|--:|---|--:|--:|--:|
| close | KXBTCD-26SEP1109-T77399.99 | 0.1600 | 0.1600 / 0.0800 | KXBTCD-26SEP1109-T77499.99 | 0.1700 | 0.1700 / 0.1900 | 1 | 1 / 1 | -1 |
| close | KXBTCD-26SEP3010-T84899.99 | 0.0900 | 0.0900 / 0.0900 | KXBTCD-26SEP3010-T84999.99 | 0.1000 | 0.1000 / 0.1500 | 1 | 1 / 1 | -1 |
| close | KXBTCD-26OCT0209-T87399.99 | 0.0900 | 0.0900 / 0.0900 | KXBTCD-26OCT0209-T87599.99 | 0.1000 | 0.1000 / 0.3100 | 1 | 1 / 1 | -1 |
| close | KXBTCD-26OCT0209-T87499.99 | 0.0900 | 0.0900 / 0.0900 | KXBTCD-26OCT0209-T87599.99 | 0.1000 | 0.1000 / 0.3100 | 1 | 1 / 1 | -1 |
| close | KXBTCD-26SEP1111-T80899.99 | 0.0800 | 0.0800 / 0.0700 | KXBTCD-26SEP1111-T80999.99 | 0.0900 | 0.0900 / 0.1000 | 1 | 1 / 1 | -1 |
| close | KXBTCD-26SEP2811-T82199.99 | 0.9800 | 0.9800 / 0.9700 | KXBTCD-26SEP2811-T82399.99 | 0.9900 | 0.9900 / 0.9900 | 1 | 1 / 1 | -1 |
| hilo | KXBTCD-26SEP2719-T84499.99 | 0.5100 | 0.5400 / 0.5100 | KXBTCD-26SEP2719-T84599.99 | 0.5600 | 0.4100 / 0.5600 | 5 | 2 / 2 | 1 |
| hilo | KXBTCD-26SEP2719-T83999.99 | 0.8800 | 0.9200 / 0.8800 | KXBTCD-26SEP2719-T84099.99 | 0.9100 | 0.8500 / 0.9100 | 3 | 1 / 1 | 1 |
| hilo | KXBTCD-26SEP2719-T83899.99 | 0.9300 | 0.9600 / 0.9300 | KXBTCD-26SEP2719-T83999.99 | 0.9800 | 0.9100 / 0.9800 | 5 | 1 / 1 | 3 |
| hilo | KXBTCD-26OCT2009-T81599.99 | 0.1400 | 0.3700 / 0.1400 | KXBTCD-26OCT2009-T81699.99 | 0.2100 | 0.2100 / 0.2100 | 7 | 1 / 2 | 4 |

**(f) Fee provenance.** Live `GET /series` today: {'KXBTCD': {'fee_type': 'quadratic', 'fee_multiplier': 1, 'frequency': 'hourly'}, 'KXBTC': {'fee_type': 'quadratic', 'fee_multiplier': 1, 'frequency': 'hourly'}}. 2026-10-27 survey catalogue (`cache/shape_screen/series_catalog.json`, mtime Tue Oct 27 16:17:15 2026): {'KXBTCD': {'fee_type': 'quadratic', 'fee_multiplier': 1}, 'KXBTC': {'fee_type': 'quadratic', 'fee_multiplier': 1}}. Both series are `quadratic`, multiplier 1 (taker-only; no maker fee). Fee per leg = ceil(7 p (1-p)) cents, p in dollars, asserted >= 1c for every price 1..99c. The ten worked rows above show the fee on each leg (the last two columns before net); examples at other prices:

| price (c) | 7 p (1-p) | fee (c) |
|--:|--:|--:|
| 1 | 0.0693 | 1 |
| 5 | 0.3325 | 1 |
| 10 | 0.6300 | 1 |
| 17 | 0.9877 | 1 |
| 25 | 1.3125 | 2 |
| 40 | 1.6800 | 2 |
| 50 | 1.7500 | 2 |
| 60 | 1.6800 | 2 |
| 83 | 0.9877 | 1 |
| 99 | 0.0693 | 1 |

## 6. Exclusions (count and reason)

* Strike-minutes in the candle grid 5,112,880; with a candle 2,229,166; the rest are 'no candle that minute' -- unobserved under the strict `close` reading (included under `carried`). Two-sided (bid >= 1 and ask >= 1) strike-minutes: 1,286,997.
* A leg is executable only if the side it trades is quoted: buy needs 1 <= yes_ask <= 99 (ask 100 = no offer), sell needs 1 <= yes_bid <= 99 (bid 0 = no bid). Pair-observations failing this are not tested; the tested count is in the section-1 table.
* Hours per candle-minute count: {55: 485, 71: 18} (the 17:00-UTC hours open 15 min early). All minutes with any candle are scanned; no minute selection.
* Tape: high/low sample 250 of 1,043 opportunities (API rate limits); missing tape rows: 0.
* KXBTC coverage 503/503 hours (100.0%); the completed set is a prefix of the saved order.
* Part C: 1,368 of 91,554 KXBTC `between` ranges have no matching KXBTCD strike pair (edge ranges beyond the KXBTCD ladder) and are excluded; the two KXBTC tails are not used in Part C. A leg is executable only at 1..99c on the side traded; failures are not counted as tested.
* One KXBTCD hour (KXBTCD-26AUG2416) lists one market with an empty `expiration_value`; the non-empty value (78750.21, identical to the KXBTC value) is used for the second form of anchor (c).
* Outcome exclusions (no official yes/no): none.

## 7. Contradictions with the spec's premises

* **KXBTC has 188 markets per hour, not 100**: 186 `between` ranges ($100 wide, `strike_type=between`, floor and cap), one `less` tail and one `greater` tail. It is still a complete partition (exactly one YES per hour; check above), so the structure the spec relies on holds, but 'KXBTC: 100 range markets/hour, strike_type=less' is wrong.
* **Part B needs KXBTC data, which was not cached**: the spec says Parts A and B need no new fetching, but the partition sum is over KXBTC. KXBTC candles had to be fetched in the same saved order (coverage above).
* **'The N-leg dutch book is dead by arithmetic' is exact only for buying the 188-leg partition.** Selling the partition needs only the legs that have a bid (3-10 of 188 in practice), so its fee floor is 3-10c, not 100c; section 3 shows 60 carried minutes with bid-sum > 100c and 3 that survive fees. Diagnostic only; the spec forbids testing it as a strategy and I did not.
* **'No forecast, no observation, no speed' does not hold for the only crossings that exist**: the tape (2.3) shows the ladder is crossed for milliseconds around BTC moves and that opposite-side takers close it within ms. On minute-end snapshots, which is all the candle archive can see, it is never crossed.
* The cached candles stop at close - 5 min (original TAIL_PRICING fetch), so the last five minutes of every hour are not scanned.
* Candle rows exist only for minutes in which a strike's quote or trade changed; a strict same-minute `close` therefore needs both legs to have changed in the same minute. The `carried` reading removes that restriction and finds the same thing (zero).

## 8. Verdict: frozen rule, numbers beside each bar

* **KILL clause 1** (the `close`-only reading yields zero fee-clearing violations across the covered universe): Part A **0** (of 1,764,729 executable pair-observations, 503 hours = 100% of the universe); Part C **31** fee-clearing rows (503 of 503 hours, 100.0%). Carried-close disclosure: Part A 0. -> does NOT fire for the study (Part A alone is zero, Part C is not).
* **KILL clause 2** (fewer than 10% of candidates survive tape confirmation): Part C candidates 28, L2-confirmed 8 = **28.6%** (bar: < 10%) -> does NOT fire.
* PASS bars, `close`-only, Part A: (1) >= 100 fee-clearing violations on >= 20 days: **0** on **0** days -> FAIL; (2) >= 50% tape-confirmed: **n/a (0/0)** -> FAIL; (3) median net >= +2.0c: **n/a** -> FAIL; (4) >= 50% non-zero volume on both legs: **n/a** -> FAIL; (5) no day > 25%: **n/a** -> FAIL.
* PASS bars, `close`-only, Part C: (1) >= 100 fee-clearing violations on >= 20 days: **28** opportunities (31 rows) on **15** days -> FAIL; (2) >= 50% confirmed on the tape: **28.6%** -> FAIL; (3) median net >= +2.0c: **1.00c** -> FAIL; (4) >= 50% non-zero volume on all legs: **32.1%** -> FAIL; (5) no day / hour > 25%: day 25.0%, hour 25.0% -> met (exactly at the bar, not over it).
* Part B is a diagnostic and carries no PASS/KILL bar.
* Bonferroni (3 parts x 2 readings = 6, alpha = 0.00833): no test of profitability is needed for an arbitrage and none is run; the count bars above are the whole gate.

**INSUFFICIENT.**  Per part: Part A KILL (clause 1); Part C INSUFFICIENT: no PASS bar met, KILL clause 2 not triggered. 
The frozen rule is applied to the study as a whole, and 'zero fee-clearing violations across the covered universe' is not true of Part C, so the study is INSUFFICIENT rather than KILL. That is not a near-PASS. Part C misses every count bar by a wide margin (28 opportunities against 100, 15 days against 20, median net 1.0c against 2.0c, tape confirmation 28.6% against 50%, full-leg volume 32.1% against 50%) and each opportunity is a few cents on one contract before any size or latency question. If 'covered universe' in the KILL clause is read per part, Part A is a clean KILL and Part C is the only live residue; I apply the clause to the study as a whole because that is its literal wording (one `close`-only reading across the covered universe). Part A, the 2-leg ladder spread, is dead on simultaneous quotes: the ladder is never crossed by more than 1c at any minute-end in 503 hours.
What neither verdict covers: millisecond-scale crossings on the tape (section 2.3) are a latency competition the spec's 'no speed' premise excludes and this study did not size. Size, the spec's binding unknown after any PASS, never arises.
