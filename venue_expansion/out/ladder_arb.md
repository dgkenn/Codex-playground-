# Ladder arbitrage: is the KXBTCD threshold ladder ever quoted crossed?  (LADDER_ARBITRAGE_SPEC.md, executed)

**VERDICT: KILL**  (frozen PASS/KILL rule applied verbatim; numbers beside each bar in section 8)

Universe: 503 KXBTCD hours (prefix of the saved seed-20261027 order, never re-sorted), 60 UTC days, 27,953 candle-minutes, 2,229,166 strike-minutes with a candle (1,286,997 two-sided). KXBTC (Parts B, C) coverage: 11 of 503 hours (2.2%, 10 days; completed set is a contiguous prefix of the order).

## 0. Plain reading (written from the tables below)

* **On simultaneous quotes the ladder is never crossed by enough to matter.** `close` reading: 6 raw crossings (bid(K2) > ask(K1)) in 5 minutes out of 1,764,729 executable pair-observations; the largest was 1c, and fees on two legs are at least 2c, so **0 are fee-clearing** (need a crossing of >= 3c). The `carried` reading (each strike's last close carried across minutes in which it did not change, valid because candle open == previous close in 100% of 162k adjacent/gap pairs tested) gives the same 6 / 0.
* **The high/low construction manufactures 8,194 'fee-clearing violations' (1,043 per-minute-max opportunities on 59 days, median net 5c, both legs traded in 99.1%) out of the same data.** They are a within-minute timing artifact: bid.high of one strike and ask.low of another are different instants. Anchor (e) says that is a finding, and it is.
* Tape check of a seeded sample of 250 of those 1,043 high/low opportunities: tape-inverted (L2) 22 of 74 (29.7%), side-correct (L3) 19.

## 1. Anchor (e): simultaneity disclosure -- FIRST, because it decides whether anything else means anything

Part A, all ordered strike pairs K1 < K2, every minute, 503 hours.  Buy YES(K1) at yes_ask, sell YES(K2) at yes_bid.  Net = bid(K2) - ask(K1) - fee(ask) - fee(bid), cents.  'Opportunity' = the maximum-net fee-clearing pair of a minute (the spec's scan unit); 'pairs' counts every fee-clearing pair.

| reading | simultaneous? | can PASS? | executable pair-observations tested | raw crossings (pairs / minutes / hours) | largest raw crossing | fee-clearing pairs | fee-clearing opportunities (minutes) | days | median net (opportunity / pair) | max net |
|---|:--:|:--:|--:|---|--:|--:|--:|--:|---|--:|
| `close`, every leg, same candle (PRIMARY) | yes | yes | 1,764,729 | 6 / 5 / 5 | 1c | **0** | **0** | 0 | n/ac / n/ac | n/a |
| `close` carried across unchanged minutes (disclosure; not in spec) | yes (state) | NO | 1,784,461 | 6 / 5 / 5 | 1c | **0** | **0** | 0 | n/ac / n/ac | n/a |
| bid.HIGH(K2) vs ask.LOW(K1), same minute (**NON-SIMULTANEOUS**) | NO | NO | 2,023,217 | 18,036 / 2,287 / 338 | 94c | **8,194** | **1,043** | 59 | 5c / 4.00c | 92 |

**Reading: the apparent opportunity is a within-minute timing artifact.** The same minutes, the same quotes, give 8,194 fee-clearing pairs when two different instants are compared and **zero** when one instant is. That is the finding.

How close does the simultaneous ladder come to being crossed?  Per minute, max over K1 < K2 of bid(K2) - ask(K1) (cents), minutes with at least one executable pair:

| reading | <= -10 | -9..-5 | -4..-2 | -1 | 0 | >= +1 | minutes |
|---|--:|--:|--:|--:|--:|--:|--:|
| close | 3,345 | 2,944 | 10,942 | 9,361 | 1,247 | 5 | 27,844 |
| carried | 3,345 | 2,938 | 10,913 | 9,312 | 1,331 | 5 | 27,844 |
| hilo | 1,977 | 1,875 | 7,302 | 10,338 | 4,126 | 2,287 | 27,905 |

(`0` = locked, bid(K2) = ask(K1); `>= +1` = crossed, but not necessarily by enough to pay 2-4c of fees.)

Why the high/low crossing is not real (the 1,043 per-minute-max high/low opportunities, looked at through the close): median bid.high - bid.close of the sold leg = 8c, median ask.close - ask.low of the bought leg = 9c; median claimed (high/low) credit 8c versus median close-to-close gap bid(K2) - ask(K1) = -11c. Share of those minutes that are crossed at the close: 0.0%; share at least 1c uncrossed at the close: 98.9%. On the tape sample, the instant of K2's highest print and of K1's lowest print are a median 35.9s apart (85% more than 2s apart; n=74).

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

Tape (GET /markets/trades) for these 0 raw crossings (not fee-clearing, so nothing 'survives' to confirm; shown because the spec requires the check wherever a crossing is claimed): both legs printed in the minute 0, fee-clearing printed inversion within 2 s (L2) 0, side-correct (L3) 0.

| K1 | K2 | end_ts | prints K1 / K2 | tape vol K1 / K2 | candle vol K1 / K2 | L1 | L2 | L3 |
|---|---|--:|--:|--:|--:|:--:|:--:|:--:|

### 2.2 `hilo` (NON-SIMULTANEOUS; reported only to size the artifact; cannot PASS)

* Fee-clearing pairs 8,194; opportunities (per-minute max) 1,043 on 59 of 60 days and 273 hours; median net 5c (pairs 4.00c), max net 92c.
* Concentration: busiest day 2026-08-25 = 6.4% of opportunities; busiest hour KXBTCD-26SEP1515 = 2.7%.
* Traded volume in the violating minute (UPPER BOUND on size only; candles carry no depth; realisable size is UNKNOWN): median leg volumes 5306 / 5402 contracts; both legs non-zero in 1,034 (99.1%); zero-volume leg (doubtful fill) in 9.
* Tape on a seeded random sample (250 opportunities, seed 20261028; the full 1,043 were not pulled because of API rate limits): both legs printed in the minute (L1) 74/74 (100.0%); fee-clearing printed inversion within 2 s (L2) 22/74 (29.7%); side-correct (L3) 19/74.
* Tape volume check: of 74 leg-pairs, tape volume equals candle volume on both legs in 74 (the validated MAKER_FILL result holds).

Gates evaluated on each reading (hilo shown only to show what it would claim; it cannot PASS):

| reading | >=100 opp. on >=20 days | tape >= 50% | median net >= +2.0c | >=50% non-zero vol both legs | no day/hour > 25% | PASS-eligible result |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| close | False | False | False | False | False | no |
| carried | False | False | False | False | False | no |
| hilo | True | False | True | True | True | not eligible (non-simultaneous) |

## 3. Part B: KXBTC partition-sum diagnostic (NOT a strategy)

KXBTC data not scanned.

## 4. Part C: 3-leg cross-series (KXBTC range vs KXBTCD pair, same hour)

Not run.

## 5. Anchors

**(a) No outcome in the P&L path.** AST scan passed on `arb_net`, `arb_net3`, `pair_scan`, `scan_hour`, `scan_C_hour`, `partition_hour`, `gap_scan`, `kd_load`, `kx_load`, `build_arrays`, `hour_grid`, `c100`, `universe_hours`, `kx_hours`: none references any identifier or string constant containing 'result', 'expiration', 'settle' or 'official'. The whole 2-leg credit is `arb_net(ask_k1, bid_k2)` -- signature ['ask_k1', 'bid_k2'], integers only, so it cannot see an outcome. The scan writes its violation rows (`violations.json`) before any `results.json` is opened; `results.json` is read only by the `verify_*` functions below, after the scan. If the profit needed the outcome it would not be an arbitrage; here it does not.

**(b) Payoff dominance.** Against the official settlement, for ALL 18,048 violation rows ever produced (6 close, 18,036 high/low, 6 carried; 0 skipped for a missing official yes/no): realised payoff of long YES(K1) / short YES(K2) = +100 in 1,644, 0 in 16,404, **negative in 0** (minimum 0). Note the spec's sample (>= 20 violations) cannot be drawn from fee-clearing `close` violations because there are none; the check was therefore run on every raw crossing, close and high/low, which is a strictly larger set. No negative payoff: the construction is right.

**(c) Monotonicity on settled outcomes.** 503 KXBTCD hours, 92,560 strikes with an official yes/no: hours with a YES above a NO (interleaving): **0** . Second form (every strike below `expiration_value` YES, every strike above NO), on the 11 hours for which a fresh KXBTCD listing was pulled with the KXBTC fetch: 2,068 strikes, **0 mismatches** . Exclusions: none.

**(d) No mid, executable sides only.** AST scan: no identifier containing 'mid' in any function other than the checker, no division/multiplication by 2 or 0.5 over an expression mixing bid- and ask-named values (44 Div/Mult nodes inspected), and `pair_scan` builds the buy cost from the ask row only and the sell proceeds from the bid row only. Ten violations re-parsed from the raw candle JSON (independently of `build_arrays`; the 6 `close` raw crossings first, then 4 high/low), with the exact yes_ask bought and yes_bid sold, and the fee recomputed with `math.ceil` directly:

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
* Tape: high/low sample 250 of 1,043 opportunities (API rate limits); missing tape rows: 182.
* KXBTC coverage 11/503 hours; Parts B and C describe that prefix only.
* Outcome exclusions (no official yes/no): none.

## 7. Contradictions with the spec's premises

* **KXBTC has 188 markets per hour, not 100**: 186 `between` ranges ($100 wide, `strike_type=between`, floor and cap), one `less` tail and one `greater` tail. It is still a complete partition (exactly one YES per hour; check above), so the structure the spec relies on holds, but 'KXBTC: 100 range markets/hour, strike_type=less' is wrong.
* **Part B needs KXBTC data, which was not cached**: the spec says Parts A and B need no new fetching, but the partition sum is over KXBTC. KXBTC candles had to be fetched in the same saved order (coverage above).
* The cached candles stop at close - 5 min (original TAIL_PRICING fetch), so the last five minutes of every hour are not scanned.
* Candle rows exist only for minutes in which a strike's quote or trade changed; a strict same-minute `close` therefore needs both legs to have changed in the same minute. The `carried` reading removes that restriction and finds the same thing (zero).

## 8. Verdict: frozen rule, numbers beside each bar

* **KILL clause 1** (`close`-only reading yields zero fee-clearing violations across the covered universe): Part A 0 (of 1,764,729 executable pair-observations, 503 hours); Part C None (11 hours). Carried-close disclosure: Part A 0. -> FIRES.
* KILL clause 2 (< 10% of candidates survive tape confirmation): not reached -- there are no fee-clearing `close` candidates to confirm.
* PASS bars, `close`-only, Part A: (1) >= 100 fee-clearing violations on >= 20 days: **0** on **0** days -> FAIL; (2) >= 50% tape-confirmed: **n/a (0/0)** -> FAIL; (3) median net >= +2.0c: **n/a** -> FAIL; (4) >= 50% non-zero volume on both legs: **n/a** -> FAIL; (5) no day > 25%: **n/a** -> FAIL.
* Part B is a diagnostic and carries no PASS/KILL bar.
* Bonferroni (3 parts x 2 readings = 6, alpha = 0.00833): no test of profitability is needed for an arbitrage and none is run; the count bars above are the whole gate.

**KILL.**  The simultaneous ladder is never crossed by more than 1c, fees on two legs are at least 2c, and no bar moved. The only 'opportunity' in the data is the high/low construction the spec itself forbids as a PASS reading. This closes the ladder-arbitrage family on these two series. Size, the spec's binding unknown after any PASS, never came up because there is nothing to size.
