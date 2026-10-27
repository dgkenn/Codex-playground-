# Spec S1 -- Polymarket whitelist EV at MEASURED asks (pmxt.dev order-book archive)

**VERDICT: NO-VERDICT (spec infrastructure kill): pmxt.dev missing/unreadable for 90.1% of needed hour-files (> 20%)**

> **GEO-BLOCK DISCLOSURE (read first).** Global Polymarket (the venue priced here) remains geo-blocked to US persons, and Polymarket US lists no weather markets (checked 2026-07-23). **Even a PASS would be a measurement, not a deployment, for this operator.** Any deployment is an operator/legal decision. Nothing in this study touches Kalshi operations.

## 1. Frozen bar this is judged against (judge_specs.json, id S1 -- not re-registered, not relaxed)

- **pass**: cluster-t >= 2.25 AND mean net EV >= +0.5c/ct
- **kill**: one-sided 98.33% UCB (z=2.128) of mean net EV < +0.2c/ct
- **min_n**: >= 120 priced fires AND >= 40 city-day clusters
- **spec_kills**: > 40% unpriceable OR > 20% hour-files unreadable
- Multiple-comparison policy: Bonferroni over 3 specs, per-spec one-sided alpha 0.0167; fixed t >= 2.25, z = 2.128. No parameter was tuned (margin/sustain/glitch constants are the deployed `kwx_lock_rule.py` values), so the whole 2026-04-14..2026-07-18 window is the test set and was read once.
- Gating population = ALL item-2b bracket entries of the four cities, priced at the measured best ask, held to the venue's own resolution. Item-2a locks, per-city splits, ask buckets and every sensitivity below are **non-gating**.

## 2. Result

| population | n | city-day clusters | mean net EV (c/ct) | median | cluster t | 98.33% UCB (c) | win rate / mean ask |
|---|---:|---:|---:|---:|---:|---:|---|
| **PRIMARY (gating)** | 110 | 27 | -1.445 | -0.105 | -1.11 | +1.316 | 0.9% / 2.3c |

- Gate 1 (t >= 2.25): t = -1.114 -> NOT met.
- Gate 2 (mean >= +0.5c): mean = -1.445c -> NOT met.
- Symmetric KILL (98.33% UCB < +0.2c): UCB = +1.316c -> not triggered.
- min_n (>= 120 priced, >= 40 clusters): 110 priced / 27 clusters -> NOT met.
- Spec-kill checks: unpriceable 0.1% of in-coverage entries (kill > 40%); archive hour-files missing 90.1% (kill > 20%) -> pmxt.dev missing/unreadable for 90.1% of needed hour-files (> 20%).
- Cluster-bootstrap cross-check (resampling city-days): 1.67% / 50% / 98.33% quantiles of the mean = -4.489 / -1.364 / +0.659 c. Calendar-date-clustered sensitivity: t = -1.11, 9 clusters.

## 3. Fire accounting (every entry is in exactly one bucket)

| status | entries |
|---|---:|
| not_mirrored | 1434 |
| priced | 110 |
| before_pmxt_coverage | 1 |
| unpriceable_no_ask_in_60min | 1 |

- Thin-book among priced fires (no bid, or ask-bid >= 10c at the pricing event; descriptive): 74 of 110.
- pmxt hour-files needed by entries: 1075; archive holes: 0 []; hour-files mirrored: 111.
- Archive hours with < 40% of the median row count (possible collector outage): 1 ['2026-04-20T15'].

## 4. By city and by ask bucket (non-gating)

| population | n | city-day clusters | mean net EV (c/ct) | median | cluster t | 98.33% UCB (c) | win rate / mean ask |
|---|---:|---:|---:|---:|---:|---:|---|
| chicago | 0 | - | - | - | - | - | - |
| tokyo | 36 | 9 | +0.033 | -0.263 | +0.03 | +2.781 | 2.8% / 2.6c |
| london | 32 | 9 | -0.128 | -0.105 | -6.53 | -0.086 | 0.0% / 0.1c |
| paris | 42 | 9 | -3.716 | -0.105 | -1.17 | +3.049 | 0.0% / 3.6c |
| ask 0-10c | 105 | 27 | -0.511 | -0.105 | -3.67 | -0.215 | 0.0% / 0.5c |
| ask 10-30c | 2 | 2 | -19.218 | -19.218 | -1.55 | +7.168 | 0.0% / 18.5c |
| ask 30-60c | 2 | 2 | +10.344 | +10.344 | +0.13 | +183.647 | 50.0% / 38.5c |
| ask 60-90c | 1 | None | -87.566 | -87.566 | n/a | n/a | 0.0% / 87.0c |
| ask 90-101c | 0 | - | - | - | - | - | - |

## 5. Signal coverage by city (weather-only; usable days after guards)

| city | usable days | entries | entries into the eventual winner | days winner never entered |
|---|---:|---:|---:|---:|
| chicago | 46 | 228 | 31 | 15 |
| tokyo | 94 | 490 | 36 | 58 |
| london | 94 | 405 | 2 | 92 |
| paris | 94 | 423 | 2 | 92 |

## 6. Sensitivities (all NON-gating; none can change the verdict)

| population | n | city-day clusters | mean net EV (c/ct) | median | cluster t | 98.33% UCB (c) | win rate / mean ask |
|---|---:|---:|---:|---:|---:|---:|---|
| tied-ms rows: lowest ask | 110 | 27 | -1.436 | -0.105 | -1.11 | +1.307 | 0.9% / 2.3c |
| tied-ms rows: highest ask | 110 | 27 | -1.445 | -0.105 | -1.11 | +1.316 | 0.9% / 2.3c |
| ask event within 5 min of signal | 109 | 27 | -1.457 | -0.105 | -1.11 | +1.329 | 0.9% / 2.3c |
| ask event within 60 s of signal | 87 | 27 | -1.783 | -0.105 | -1.09 | +1.698 | 1.1% / 2.9c |
| excl. thin-book (no bid or spread>=10c) | 36 | 16 | -1.727 | -0.525 | -0.94 | +2.164 | 2.8% / 4.3c |
| thin-book only | 74 | 26 | -1.308 | -0.105 | -1.08 | +1.268 | 0.0% / 1.3c |
| ask <= 97c | 110 | 27 | -1.445 | -0.105 | -1.11 | +1.316 | 0.9% / 2.3c |
| 3c < ask < 97c | 8 | 6 | -16.158 | -9.930 | -0.87 | +23.206 | 12.5% / 28.0c |
| excl. thin pmxt hours | 110 | 27 | -1.445 | -0.105 | -1.11 | +1.316 | 0.9% / 2.3c |
| fee ignored (diagnostic) | 110 | 27 | -1.384 | -0.100 | -1.07 | +1.356 | 0.9% / 2.3c |
| excluding Chicago | 110 | 27 | -1.445 | -0.105 | -1.11 | +1.316 | 0.9% / 2.3c |
| chicago_only | 0 | - | - | - | - | - | - |
| un-rounded conversion (reference harness literal) | 99 | 27 | -0.983 | -0.210 | -1.13 | +0.873 | 2.0% / 2.9c |
| signal timestamp + 5 min | 100 | 27 | -0.557 | -0.105 | -3.67 | -0.234 | 0.0% / 0.5c |

## 7. Item-2a deployed-rule LOCKS priced at the measured ask (separate, non-gating)

| population | n | city-day clusters | mean net EV (c/ct) | median | cluster t | 98.33% UCB (c) | win rate / mean ask |
|---|---:|---:|---:|---:|---:|---:|---|
| all | 90 | 27 | +0.005 | +0.000 | +1.74 | +0.012 | 100.0% / 100.0c |
| yes_side | 0 | - | - | - | - | - | - |
| no_side | 90 | 27 | +0.005 | +0.000 | +1.74 | +0.012 | 100.0% / 100.0c |

Lock pricing status: {'before_pmxt_coverage': 1, 'unpriceable_no_ask_in_60min': 17, 'priced': 90, 'not_mirrored': 1448}. YES locks priced on the YES token, NO locks on the NO token's own ask.

## 8. Every skipped city-day (reason)

- **chicago** -- `thin_station_data` (28): 2026-04-14, 2026-04-15, 2026-04-16, 2026-04-17, 2026-04-18, 2026-04-19, 2026-04-20, 2026-04-21, 2026-04-22, 2026-04-23, 2026-04-24, 2026-04-25, 2026-04-26, 2026-04-28, 2026-04-29, 2026-04-30, 2026-05-01, 2026-05-02, 2026-05-03, 2026-05-04, 2026-05-05, 2026-05-06, 2026-05-07, 2026-05-08, 2026-05-09, 2026-05-10, 2026-05-19, 2026-06-24
- **chicago** -- `station_feed_gap_near_dayend` (19): 2026-04-27, 2026-05-11, 2026-05-13, 2026-05-15, 2026-05-20, 2026-05-22, 2026-05-24, 2026-05-26, 2026-05-27, 2026-05-30, 2026-06-07, 2026-06-12, 2026-06-21, 2026-06-22, 2026-06-23, 2026-06-25, 2026-06-28, 2026-07-09, 2026-07-16
- **chicago** -- `event_not_found` (2): 2026-05-17, 2026-05-18
- **chicago** -- `not_resolved_or_unparseable` (1): 2026-06-18
- **london** -- `event_not_found` (2): 2026-05-17, 2026-05-18
- **paris** -- `event_not_found` (2): 2026-05-17, 2026-05-18
- **tokyo** -- `event_not_found` (2): 2026-05-17, 2026-05-18

## 9. Method, and every judgement call (disclosed, none tuned on outcomes)

**Signal.** `kwx_lock_rule.sustained_extreme` / `locked_orders` (byte-identical shim of the deployed rule: margin 1.0F / 0.5C, sustain-3, glitch filter) run over each city-day's weather feed; an item-2b entry is the first obs at which the filtered sustained running max falls inside a rung's margin-adjusted band (`floor+margin < extreme <= cap+margin`). Signal time = the timestamp of the obs completing the sustain condition. No market input and no outcome input enters the signal.

**Feeds.** Chicago: IEM true 1-minute ASOS, station ORD. Tokyo: JMA 10-min AMeDAS (prec_no=44, block 0371, 144 rows/day; C converted to F at the fetch boundary so the rule's degF constants apply). London EGLC / Paris LFPB: IEM asos.py with report_type=3&4 (~48 rows/day). Mexico City and Sao Paulo are excluded per the registration (no verified sub-hourly feed).

**Ladders and outcomes.** Gamma event ladders (`highest-temperature-in-<city>-on-<month>-<d>-<yyyy>`); YES/NO token order is read from each market's own `outcomes` field; the resolved rung is the market whose `outcomePrices` is exactly [1,0] (the venue's own resolution), and a day is skipped unless exactly one rung resolved YES.

**Pricing.** pmxt.dev hourly order-book parquet (r2v2.pmxt.dev). For each fire: the first ask-bearing event at `timestamp_received >= signal time` for the rung's YES token within 60 minutes (`price_change` rows carry `best_ask`; `book` snapshots carry the ask ladder and the best ask is its minimum price; `last_trade_price` and `tick_size_change` rows carry no ask and are skipped). No ask within 60 minutes => UNPRICEABLE, never back-filled. If a needed hour-file is an archive hole the fire is bucketed `archive_hole` and counted AGAINST the 40% unpriceable bar. Net EV per contract (cents) = payout(100 if YES) - ask - 100*0.05*p*(1-p), taker only, p = the executed ask. Cluster = city-day (CR1 small-sample-corrected SE of the mean, df = G-1); calendar-date clustering and a city-day bootstrap are reported as cross-checks.

**Harness fidelity.** For Chicago the entries and entry timestamps reproduce Track A (`out/tracka_results.json`) exactly on every shared day: 228 of 228 entries identical to the minute. That ties this run to the harness that passed the coverage GO-check.

**Judgement calls and deviations (none touches the frozen bar, the entry rule, the EV formula or the population):**
1. *Mirror format.* The data plan says to mirror every hour-file used. A full hour-file is 130-590 MB; the ~1,100+ files used would need roughly 0.5 TB against ~30 GB free disk. What is mirrored instead, for every hour-file used (`cache/spec_s1/pmxt/<hour>.parquet` + `.manifest.json` with size, etag, row counts): all rows of the full 7-column projection (timestamp_received, event_type, asset_id, best_bid, best_ask, bids, asks) for every YES and NO token of every ladder that has a fire in that hour or the previous one. This is a strict superset of every datum the accounting uses; `analyze` runs from this cache alone. The third-party continuity caveat stands: the mirror is a filtered copy, not the raw archive.
2. *Float rounding in the unit conversion.* The reference harness converts degF back to degC with `(f-32)*5/9` and compares at integer thresholds. Float noise (e.g. 28.0C -> 82.4F -> 28.000000000000004C) flips those strict comparisons at exactly-integer readings, which are common on integer-C METAR feeds. The primary population rounds the converted extreme to 6 decimals before the band test; the rule functions are untouched. The literal un-rounded reference behaviour is reported as a non-gating variant (section 6); the number of entries it changes is in the JSON (`n_entries_changed_by_float_rounding`). This was decided before any price was read.
3. *Chicago feed holes.* IEM's ORD 1-minute archive is empty or sparse for most of 2026-04-14..2026-05-11 and has scattered partial days after (MDW and JFK return full data for the same period, so it is an ORD-specific upstream hole, and Track A saw the same). Days failing the pre-set guards (>=100 obs and last obs within 3 h of local midnight) are skipped and listed in section 8; no other station or cadence is substituted.
4. *Guards.* Completeness guards (Chicago 100 obs / 3 h; 30-min feeds 30 obs / 4 h; JMA 90 obs / 4 h) were fixed before any obs were read; Chicago equals Track A's.
5. *Timestamp used.* `timestamp_received` (when the archive collector saw the event), not the exchange `timestamp`. When several rows share the first millisecond the primary price is the upper median of their asks (row order inside a millisecond is not recoverable); lowest/highest are reported as bounds in section 6.
6. *Signal time is the obs timestamp,* not the publication time of the obs. A +5 minute latency variant is reported in section 6.
7. *Window.* The frozen window (2026-04-14..2026-07-18) is used even though the archive now extends to about six months; nothing outside it was read.
8. *Thin book* (undefined in the registration) is defined as: no bid at the pricing event, or ask-bid >= 10c. It is descriptive only.
9. *Near-zero rungs.* A large share of item-2b entries are into rungs whose ask is a few tenths of a cent (entries at the start of a day into low rungs, and integer-reading dead-zone rungs on the C feeds). They are in the registered population and in the gating test. Section 6 shows the result with 3c < ask < 97c as a non-gating view, because a population dominated by near-zero-cost losers mechanically pulls the mean toward -0.1c and tightens its confidence interval.

