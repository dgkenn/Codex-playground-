# Kalshi Intra-Venue Structural / Logical-Consistency No-Arb -- OOS Test

Run window: 2026-07-18T16:53:37.657641+00:00 -> 2026-07-18T17:07:07.964660+00:00  
Polls completed: 8 / 8 (spaced 90.0s apart)  
Persistence bar: a violation must be seen, orderbook-depth-confirmed, and net-fee-positive in >= 3 of 8 polls to count as REAL.  
Min executable depth: 5 contracts/leg. Min RAW (pre-fee) edge to flag a candidate: $0.0010. Min NET (post-fee) edge to ever count an observation toward REAL: $0.01.  
Fee model: `kalshi_fee = ceil(fee_multiplier * 0.07 * C * P * (1-P) * 100)/100 dollars, both legs, taker-side`

## Universe scanned per poll

| poll | events | markets | MECE events | fetch(s) | S1 cand | S2 cand | S3 cand |
|---|---|---|---|---|---|---|---|
| 0 | 7969 | 72186 | 3186 | 7.25 | 3 | 0 | 1 |
| 1 | 7974 | 72192 | 3187 | 25.26 | 3 | 0 | 1 |
| 2 | 7970 | 72183 | 3183 | 22.37 | 2 | 0 | 0 |
| 3 | 7970 | 72183 | 3183 | 23.71 | 3 | 0 | 1 |
| 4 | 7966 | 72175 | 3182 | 23.63 | 3 | 0 | 0 |
| 5 | 7960 | 72159 | 3178 | 21.42 | 3 | 0 | 0 |
| 6 | 7959 | 72171 | 3177 | 23.67 | 3 | 0 | 0 |
| 7 | 7966 | 72251 | 3184 | 23.59 | 3 | 0 | 0 |

## Per-structure results

| Structure | Flagged (candidate) | REAL (persistent+executable+exact) | Stale/unconfirmed | Mean net edge (c/$, confirmed) | Max net edge (c/$) | Mean confirmed depth (contracts) |
|---|---|---|---|---|---|---|
| S1 Ladder monotonicity | 4 | 0 | 4 | -2.5 | -1.0 | 135.2 |
| S2 Complement sum | 0 | 0 | 0 | 0.0 | 0.0 | 0.0 |
| S3 Event-sum completeness | 1 | 0 | 1 | -7.0 | -7.0 | 72.4 |

## Totals

- Total distinct violation-keys flagged (any poll, any structure): **5**
- Total REAL (persistent + orderbook-confirmed + net-fee-positive every time seen): **0**
- Stale/phantom ratio: **1.0** (fraction of flagged candidates that did NOT survive the discipline)
- Mean flagged candidates per poll (raw, cross-sectional census, NOT an arrival rate): 3.25
- Run duration: 13.51 minutes
- REAL-violation frequency, naive /week extrapolation of this run's window: 0.0
- _Each poll is a full cross-sectional census of ~7-8k open events / ~70k open markets, not an independent arrival draw, so extrapolating a short polling window into a '/week' rate is statistically unreliable for FLAGGED counts (a short run would imply an absurd rate). We report the directly observed mean flagged-candidates-per-poll instead, and only extrapolate a '/week' figure for REAL violations (and even then, only as a naive linear extrapolation of this run's window -- true frequency would require a multi-day/week continuous polling or historical-orderbook backtest, which was out of scope for this single-session live test)._

## PAVA ladder-monotonicity diagnostics (last poll, top 25 by violation mass)

| event | strike_type | n points | isotonic violation mass ($) |
|---|---|---|---|
| KXBNBD-26JUL2417 | greater | 50 | 11.9504 |
| KXBNBD-26JUL1817 | greater | 40 | 7.7954 |
| KXHYPED-26JUL1817 | greater | 40 | 4.7684 |
| KXCPIYOY-26SEP | greater | 21 | 4.132 |
| KXHYPED-26JUL1814 | greater | 75 | 3.158 |
| KXHYPED-26JUL2417 | greater | 50 | 2.86 |
| KXDEGDPQOQF-26JUL30 | greater | 15 | 2.7807 |
| KXSOLD-26JUL1814 | greater | 300 | 2.6172 |
| KXCPICOREYOY-26NOV | greater | 16 | 2.5542 |
| KXB200MON-26JUL31 | greater | 30 | 2.2799 |
| KXGDPNOM-CHN26 | greater | 16 | 2.2617 |
| KXGDPNOM-IND26 | greater | 10 | 2.1556 |
| KXCPICORE-26OCT | greater | 11 | 2.0317 |
| KXCPIYOY-26NOV | greater | 21 | 1.8864 |
| KXCPICORE-26NOV | greater | 11 | 1.8114 |
| KXCPICORE-26SEP | greater | 11 | 1.7967 |
| KXCPICOREYOY-26AUG | greater | 15 | 1.4867 |
| KXCPICOREYOY-26SEP | greater | 15 | 1.2833 |
| KXCPICORE-26AUG | greater | 11 | 1.2275 |
| KXITGDPQOQA-26JUL30 | greater | 15 | 1.19 |
| KXGOLDW-26JUL2417 | greater | 40 | 1.1845 |
| KXUSDTTBILL-27FEB28 | greater | 8 | 1.1014 |
| KXDEGDPYOYF-26JUL30 | greater | 15 | 1.0845 |
| KXH200MON-26JUL31 | greater | 30 | 1.0126 |
| KXRTX5090MAX-26DEC31 | greater | 15 | 0.84 |

## REAL violations (survived full discipline) -- detail

_None. Every candidate flagged at top-of-book failed persistence, live orderbook-depth re-confirmation, or net-of-fee positivity on at least one re-check -- i.e. every flagged crossing was a stale or phantom quote._

## Method notes / anti-stale-quote discipline actually applied

1. **NET of fees**: Kalshi's quadratic per-contract fee (`ceil(fee_multiplier*0.07*C*P*(1-P)*100)/100` dollars, looked up per-series via `/series/{ticker}`) is charged on *every leg*, *both directions*, at *taker* assumptions (crossing the resting book), which is the conservative assumption required to prove a violation is truly executable rather than a maker-only quote that may never fill.
2. **Executable depth, both legs**: every candidate's price is required to have >= 5 contracts resting at that exact price in the top-of-book size field *and* is re-verified against a live `/orderbook` fetch (full depth ladder, not the summary market object) before being counted.
3. **Persistence**: the live book was polled repeatedly, 90.0s apart, over 8 polls. A violation-key had to reappear, re-confirm executable, and stay net-fee-positive in >= 3 separate polls to be counted REAL. Anything seen once and gone (or once and un-confirmable) on the next poll is counted as stale/phantom -- this is exactly the failure mode that made the Polymarket logical-arb candidate NULL.
4. **Exact nesting/exclusivity**: legs are only ever paired within the SAME Kalshi `event_ticker` (guaranteeing identical settlement source, dates, and rules). Three additional false-pair traps were found and closed during development of this scanner (documented in-code):
   - **Parallel-subject ladders**: some events contain *two independent* threshold ladders for different subjects (e.g. a point-spread event has both a "Team A wins by >X" ladder and a "Team B wins by >Y" ladder). These are NOT nested implications of each other. S1 now splits every ladder by the market's `custom_strike` subject signature (e.g. `basketball_team` id) before comparing strikes -- this alone eliminated ~99% of initially-flagged S1 candidates (198 -> ~1-3 per poll), which were false pairs from mixing two teams' spread ladders.
   - **Non-exhaustive `mutually_exclusive` events**: Kalshi sets `mutually_exclusive=true` on both genuine tiled numeric brackets (temperature/price ranges) AND partial candidate lists (e.g. a primary-election event listing only 2 minor candidates whose combined YES-ask summed to $0.06 because ~94% of the probability mass sits on an unlisted candidate). S3 now requires a constructive proof of exhaustiveness -- exactly one unbounded-below (`less`) leg, exactly one unbounded-above (`greater`) leg, and contiguous `between` brackets tiling the real line with no gaps, verified from `floor_strike`/`cap_strike` -- and excludes categorical (`strike_type='custom'`) events entirely. This eliminated every one of the ~25 initially-flagged S3 candidates, all of which were non-exhaustive candidate/categorical events, not real range completeness violations.
   - **Same-strike, different-deadline pairs**: a few series list multiple markets at the identical strike but different close/expiration dates (e.g. "BTC > $100k before June" / "...before Sept"). These can be validly nested (earlier deadline implies later deadline) but ONLY if both markets' resolution-monitoring windows start at the same time -- Kalshi's own rules text showed a case where they did not (a 6-week gap in monitoring start between two "consecutive" deadline markets in the same event). S1 therefore requires a strictly different `floor_strike` AND identical `close_time`/`expiration_time` before pairing two markets, rather than risk pairing across a hidden window gap.
5. **S3 is executed buy-only** (buy every YES ask, or buy every NO ask) so no short-selling / margin assumption is smuggled into 'executable'.

## Verdict

NULL RESULT (same conclusion as the Polymarket OOS test). Across 8 polls of Kalshi's live order book (~7966 open events / ~72251 open markets per poll), 5 candidate structural violations were flagged at top-of-book across all three structures (ladder monotonicity, complement sum, event-sum completeness), but ZERO survived the anti-stale-quote gauntlet (persistence across >=3 polls AND live /orderbook depth re-confirmation AND net-of-fee positivity every time observed). Every flagged crossing was a single-snapshot, thin/zero-depth, or fee-eaten artifact -- i.e. a stale or phantom quote, not a real tradeable edge. There is NO real, fee-surviving, deployable structural no-arb edge on Kalshi at the scale and depth thresholds tested here.
