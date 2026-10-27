# Spec S1 -- Polymarket whitelist EV at MEASURED asks (pmxt.dev order-book archive)

**VERDICT: KILL -- Polymarket bracket-entry sleeve DEAD at measured prices: mean -1.008c/ct, 98.33% UCB -0.154c < +0.2c**

> **GEO-BLOCK DISCLOSURE (read first).** Global Polymarket (the venue priced here) remains geo-blocked to US persons, and Polymarket US listed no weather markets as of 2026-07-23 (per FINDINGS.md; not re-checked in this run). **Even a PASS would be a measurement, not a deployment, for this operator.** Any deployment is an operator/legal decision. Nothing in this study touches Kalshi operations.

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
| **PRIMARY (gating)** | 1164 | 239 | -1.008 | -0.105 | -2.51 | -0.154 | 4.2% / 5.1c |

- Gate 1 (t >= 2.25): t = -2.512 -> NOT met.
- Gate 2 (mean >= +0.5c): mean = -1.008c -> NOT met.
- Symmetric KILL (98.33% UCB < +0.2c): UCB = -0.154c -> TRIGGERED.
- min_n (>= 120 priced, >= 40 clusters): 1164 priced / 239 clusters -> met.
- Spec-kill checks: unpriceable 24.7% of in-coverage entries (kill > 40%); archive hour-files missing 0.1% (kill > 20%) -> neither triggered.
- Cluster-bootstrap cross-check (resampling city-days): 1.67% / 50% / 98.33% quantiles of the mean = -1.876 / -0.999 / -0.119 c. Calendar-date-clustered sensitivity: t = -2.43, 70 clusters.

## 3. Fire accounting (every entry is in exactly one bucket)

| status | entries |
|---|---:|
| priced | 1164 |
| unpriceable_market_not_recorded_in_archive | 358 |
| unpriceable_no_ask_in_60min | 22 |
| before_pmxt_coverage | 1 |
| archive_hole | 1 |

- Thin-book among priced fires (no bid, or ask-bid >= 10c at the pricing event; descriptive): 739 of 1164.
- pmxt hour-files needed by entries: 1075; archive holes: 1 ['2026-06-11T05']; hour-files mirrored: 1229.
- Unpriceable entries split: 358 are on city-day ladders for which the archive holds NO rows at all (market not recorded by the third-party collector) and 22 are on recorded ladders with no ask event inside 60 min. Excluding the not-recorded ladders the unpriceable share would be 1.9%. City-days whose ladder is not recorded at all in the archive: 88.
- Archive hours with < 40% of the median row count (possible collector outage): 10 ['2026-04-20T15', '2026-04-28T11', '2026-04-28T12', '2026-05-22T16', '2026-05-22T23', '2026-05-29T12', '2026-06-03T12', '2026-06-11T08', '2026-06-19T04', '2026-06-24T04'].

## 4. By city and by ask bucket (non-gating)

| population | n | city-day clusters | mean net EV (c/ct) | median | cluster t | 98.33% UCB (c) | win rate / mean ask |
|---|---:|---:|---:|---:|---:|---:|---|
| chicago | 162 | 31 | -1.045 | -0.210 | -0.75 | +1.915 | 14.2% / 15.0c |
| tokyo | 370 | 69 | -1.881 | -0.315 | -1.81 | +0.334 | 7.0% / 8.7c |
| london | 308 | 69 | -0.258 | -0.105 | -3.29 | -0.091 | 0.0% / 0.2c |
| paris | 324 | 70 | -0.704 | -0.105 | -1.65 | +0.206 | 0.0% / 0.7c |
| ask 0-10c | 1043 | 234 | -0.565 | -0.105 | -11.33 | -0.458 | 0.0% / 0.5c |
| ask 10-30c | 49 | 44 | -8.291 | -15.637 | -1.89 | +1.020 | 10.2% / 17.8c |
| ask 30-60c | 43 | 40 | -0.403 | -35.122 | -0.05 | +17.603 | 44.2% / 43.4c |
| ask 60-90c | 10 | 10 | -17.921 | +11.522 | -0.98 | +20.828 | 60.0% / 77.1c |
| ask 90-101c | 19 | 19 | +0.983 | +0.095 | +2.00 | +2.029 | 100.0% / 99.0c |

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
| tied-ms rows: lowest ask | 1164 | 239 | -1.000 | -0.105 | -2.50 | -0.147 | 4.2% / 5.1c |
| tied-ms rows: highest ask | 1164 | 239 | -1.023 | -0.105 | -2.54 | -0.165 | 4.2% / 5.1c |
| ask event within 5 min of signal | 1128 | 238 | -1.029 | -0.105 | -2.49 | -0.148 | 4.1% / 5.0c |
| ask event within 60 s of signal | 1035 | 235 | -1.077 | -0.105 | -2.40 | -0.122 | 4.2% / 5.1c |
| excl. thin-book (no bid or spread>=10c) | 425 | 160 | -2.190 | -0.525 | -2.33 | -0.192 | 9.4% / 11.4c |
| thin-book only | 739 | 207 | -0.328 | -0.105 | -1.17 | +0.267 | 1.2% / 1.5c |
| ask <= 97c | 1148 | 237 | -1.024 | -0.105 | -2.52 | -0.158 | 2.9% / 3.8c |
| 3c < ask < 97c | 152 | 86 | -5.861 | -9.409 | -1.96 | +0.498 | 21.7% / 26.9c |
| excl. thin pmxt hours | 1153 | 239 | -0.994 | -0.105 | -2.46 | -0.133 | 4.2% / 5.1c |
| fee ignored (diagnostic) | 1164 | 239 | -0.902 | -0.100 | -2.27 | -0.055 | 4.2% / 5.1c |
| excluding Chicago | 1002 | 208 | -1.002 | -0.105 | -2.44 | -0.129 | 2.6% / 3.5c |
| Chicago only | 162 | 31 | -1.045 | -0.210 | -0.75 | +1.915 | 14.2% / 15.0c |
| un-rounded conversion (reference harness literal) | 1098 | 239 | -1.193 | -0.105 | -2.61 | -0.221 | 6.3% / 7.3c |
| signal timestamp + 5 min | 1157 | 239 | -0.771 | -0.105 | -2.06 | +0.025 | 4.1% / 4.7c |

## 7. Item-2a deployed-rule LOCKS priced at the measured ask (separate, non-gating)

| population | n | city-day clusters | mean net EV (c/ct) | median | cluster t | 98.33% UCB (c) | win rate / mean ask |
|---|---:|---:|---:|---:|---:|---:|---|
| all | 1104 | 234 | +0.108 | +0.000 | +2.95 | +0.185 | 100.0% / 99.9c |
| yes_side | 17 | 17 | +0.594 | +0.095 | +1.30 | +1.567 | 100.0% / 99.4c |
| no_side | 1087 | 234 | +0.100 | +0.000 | +2.84 | +0.175 | 100.0% / 99.9c |

Lock pricing status: {'before_pmxt_coverage': 1, 'unpriceable_no_ask_in_60min': 136, 'priced': 1104, 'unpriceable_market_not_recorded_in_archive': 315}. YES locks priced on the YES token, NO locks on the NO token's own ask.

## 8. Every skipped city-day (reason)

- **chicago** -- `thin_station_data` (28): 2026-04-14, 2026-04-15, 2026-04-16, 2026-04-17, 2026-04-18, 2026-04-19, 2026-04-20, 2026-04-21, 2026-04-22, 2026-04-23, 2026-04-24, 2026-04-25, 2026-04-26, 2026-04-28, 2026-04-29, 2026-04-30, 2026-05-01, 2026-05-02, 2026-05-03, 2026-05-04, 2026-05-05, 2026-05-06, 2026-05-07, 2026-05-08, 2026-05-09, 2026-05-10, 2026-05-19, 2026-06-24
- **chicago** -- `station_feed_gap_near_dayend` (19): 2026-04-27, 2026-05-11, 2026-05-13, 2026-05-15, 2026-05-20, 2026-05-22, 2026-05-24, 2026-05-26, 2026-05-27, 2026-05-30, 2026-06-07, 2026-06-12, 2026-06-21, 2026-06-22, 2026-06-23, 2026-06-25, 2026-06-28, 2026-07-09, 2026-07-16
- **chicago** -- `event_not_found` (2): 2026-05-17, 2026-05-18
- **chicago** -- `not_resolved_or_unparseable` (1): 2026-06-18
- **london** -- `event_not_found` (2): 2026-05-17, 2026-05-18
- **paris** -- `event_not_found` (2): 2026-05-17, 2026-05-18
- **tokyo** -- `event_not_found` (2): 2026-05-17, 2026-05-18

### 8b. City-days whose whole ladder is absent from the archive (all their entries are `unpriceable_market_not_recorded_in_archive`)

pmxt.dev's collected universe shrinks over the window (about 113k distinct asset_ids in a mid-May hour-file vs about 39k in mid-June and 51k in mid-July) and the weather ladders drop out entirely for 2026-05-18/19, 2026-06-13..28 and 2026-07-10..16 (partly 06-12, 06-29, 07-09). This is a coverage hole of the third-party archive, not a market with no asks. These fires are counted as unpriceable against the 40% bar (conservative) but are NOT imputed.

- **chicago** (14): 2026-06-13, 2026-06-14, 2026-06-15, 2026-06-16, 2026-06-17, 2026-06-19, 2026-06-20, 2026-06-26, 2026-06-27, 2026-07-10, 2026-07-11, 2026-07-12, 2026-07-13, 2026-07-15
- **london** (25): 2026-05-19, 2026-06-13, 2026-06-14, 2026-06-15, 2026-06-16, 2026-06-17, 2026-06-18, 2026-06-19, 2026-06-20, 2026-06-21, 2026-06-22, 2026-06-23, 2026-06-24, 2026-06-25, 2026-06-26, 2026-06-27, 2026-06-28, 2026-06-29, 2026-07-10, 2026-07-11, 2026-07-12, 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16
- **paris** (24): 2026-05-19, 2026-06-13, 2026-06-14, 2026-06-15, 2026-06-16, 2026-06-17, 2026-06-18, 2026-06-19, 2026-06-20, 2026-06-21, 2026-06-22, 2026-06-23, 2026-06-24, 2026-06-25, 2026-06-26, 2026-06-27, 2026-06-28, 2026-07-10, 2026-07-11, 2026-07-12, 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16
- **tokyo** (25): 2026-05-19, 2026-06-13, 2026-06-14, 2026-06-15, 2026-06-16, 2026-06-17, 2026-06-18, 2026-06-19, 2026-06-20, 2026-06-21, 2026-06-22, 2026-06-23, 2026-06-24, 2026-06-25, 2026-06-26, 2026-06-27, 2026-06-28, 2026-06-29, 2026-07-10, 2026-07-11, 2026-07-12, 2026-07-13, 2026-07-14, 2026-07-15, 2026-07-16

## 9. Reading the result, and its limits

**What S1 establishes.** On the registered population (all 1164 priced item-2b bracket entries, 239 city-day clusters, four cities), buying at the *measured* best ask and holding to resolution has mean net EV -1.008 c/contract (cluster t = -2.51, one-sided 98.33% UCB -0.154 c). The UCB is below the pre-registered +0.2c KILL line, so the Polymarket bracket-entry sleeve is declared DEAD at measured prices; the PASS bar is not close. This replaces the earlier last-trade-plus-half-spread proxy (-19.4c, which was dominated by a 20c snapshot spread) and the item-2b reweighting (+0.43c on n=31) with direct per-fire accounting: the sign is now measured, and it is negative.

**Why the kill is robust to the obvious attacks (all non-gating, section 6).** Re-pricing the same population with the lowest/highest tied ask, requiring the ask within 60 s or 5 min of the signal, dropping thin archive hours, ignoring fees, excluding Chicago, the +5 minute signal-latency shift and the literal un-rounded reference conversion all give a mean between about -0.8c and -1.2c, and the UCB stays below +0.2c in every one of them (largest: +0.025c, the latency shift). Cluster bootstrap and calendar-date clustering agree. Chicago's 228 entries reproduce Track A exactly (228 of 228), so this is the harness that passed the coverage GO-check. Only two *sub-population cuts* have a UCB above the line (thin-book-only and 3c < ask < 97c); those are subsets, not re-estimates of the registered population.

**What S1 does NOT establish (read before drawing a wider conclusion).**
1. *The gating population is dominated by near-zero-cost losers:* 90% of priced fires have an ask under 10c (mean -0.565c, UCB -0.458c). That is the registered population and the verdict is on it, but it means the kill is largely a statement about those fires. The mid-priced entries that could carry an edge (3c < ask < 97c) number only 152 fires in 86 clusters with mean -5.861c and UCB +0.498c: that subset is underpowered and is **not** shown dead or alive. Any claim about it would need a new registration.
2. *Chicago alone is underpowered:* 31 clusters, UCB +1.9c. The Track A coverage result (a hit on the winning bracket on 64% of usable days) is untouched by this; what S1 adds is that hitting the winning bracket early enough is not the same as buying it cheaply, because the market prices the winner as it is being confirmed: the 49 priced entries that did go on to win were bought at a mean ask of 66.1c (median 64.0c), against a mean ask of 5.1c over all priced entries.
3. *Archive coverage:* 23% of in-coverage entries (88 city-day ladders) sit on days the third-party archive did not record at all, so the estimate is for the recorded days only (the calendar pattern is in section 8b), not a uniform draw from the window. The absences follow the calendar, not the outcome, and the unpriceable share (24.7%) is under the 40% spec-kill, but it is a real limit on generalising.
4. *Geo-block:* Global Polymarket is not accessible to US persons. This is a measurement of a venue the operator cannot trade, and nothing here supports building a Polymarket harness.
5. *Post-hoc observations that are NOT findings:* priced entries with ask >= 90c won 19 of 19 (mean +0.983c, t = +2.00), and the item-2a locks priced at the measured ask (section 7) show 1104 locks / 234 clusters at a ~99.9c ask, 100% correct, mean +0.108c per contract (t = +2.95, one-sided 98.33% bounds [+0.030, +0.185]c). These are exactly the 'late, nearly certain' regime the Kalshi lock rule already harvests (+0.15 to +0.21c per contract per ref/pmkt_final_verdict.md); they were not gating here, were chosen after seeing the table, and an edge of roughly a tenth of a cent per contract at a 99.9c ask is a capacity-and-latency question, not a statistics question. They are hypothesis-generating at most, and the venue is geo-blocked.

**Implication for the program.** The Polymarket bracket-entry sleeve is dead at measured prices. The coverage blocker Track A lifted does not translate into an executable edge on this venue. This changes nothing about Kalshi operations, and it does not help a US-person operator.

**Float-rounding note.** The un-rounded reference conversion changes 312 entries (flipped by float noise at integer thresholds, mostly London and Paris on integer-C feeds); the verdict is unchanged under it.


## 10. Method, and every judgement call (disclosed, none tuned on outcomes)

**Signal.** `kwx_lock_rule.sustained_extreme` / `locked_orders` (byte-identical shim of the deployed rule: margin 1.0F / 0.5C, sustain-3, glitch filter) run over each city-day's weather feed; an item-2b entry is the first obs at which the filtered sustained running max falls inside a rung's margin-adjusted band (`floor+margin < extreme <= cap+margin`). Signal time = the timestamp of the obs completing the sustain condition. No market input and no outcome input enters the signal.

**Feeds.** Chicago: IEM true 1-minute ASOS, station ORD. Tokyo: JMA 10-min AMeDAS (prec_no=44, block 0371, 144 rows/day; C converted to F at the fetch boundary so the rule's degF constants apply). London EGLC / Paris LFPB: IEM asos.py with report_type=3&4 (~48 rows/day). Mexico City and Sao Paulo are excluded per the registration (no verified sub-hourly feed).

**Ladders and outcomes.** Gamma event ladders (`highest-temperature-in-<city>-on-<month>-<d>-<yyyy>`); YES/NO token order is read from each market's own `outcomes` field; the resolved rung is the market whose `outcomePrices` is exactly [1,0] (the venue's own resolution), and a day is skipped unless exactly one rung resolved YES.

**Pricing.** pmxt.dev hourly order-book parquet (r2v2.pmxt.dev). For each fire: the first ask-bearing event at `timestamp_received >= signal time` for the rung's YES token within 60 minutes (`price_change` rows carry `best_ask`; `book` snapshots carry the ask ladder and the best ask is its minimum price; `last_trade_price` and `tick_size_change` rows carry no ask and are skipped). No ask within 60 minutes => UNPRICEABLE, never back-filled. If a needed hour-file is an archive hole the fire is bucketed `archive_hole` and counted AGAINST the 40% unpriceable bar. Net EV per contract (cents) = payout(100 if YES) - ask - 100*0.05*p*(1-p), taker only, p = the executed ask. Cluster = city-day (CR1 small-sample-corrected SE of the mean, df = G-1); calendar-date clustering and a city-day bootstrap are reported as cross-checks.

**Harness fidelity.** For Chicago the entries and entry timestamps reproduce Track A (`out/tracka_results.json`) exactly on every shared day: 228 of 228 entries identical to the minute. That ties this run to the harness that passed the coverage GO-check.

**Judgement calls and deviations (none touches the frozen bar, the entry rule, the EV formula or the population):**
1. *Mirror format.* The data plan says to mirror every hour-file used. A full hour-file is 130-590 MB; the 1,230 hour-files used (1,098 signal hours + 132 continuation hours; 1 of them is a 404 archive hole) would need roughly 0.5 TB against ~30 GB free disk. What is mirrored instead, for every hour-file used (`cache/spec_s1/pmxt/<hour>.parquet` + `.manifest.json` with size, etag, row counts): all rows of the full 7-column projection (timestamp_received, event_type, asset_id, best_bid, best_ask, bids, asks) for every YES and NO token of every ladder that has a fire in that hour or the previous one. This is a strict superset of every datum the accounting uses; `analyze` runs from this cache alone. The third-party continuity caveat stands: the mirror is a filtered copy, not the raw archive.
2. *Float rounding in the unit conversion.* The reference harness converts degF back to degC with `(f-32)*5/9` and compares at integer thresholds. Float noise (e.g. 28.0C -> 82.4F -> 28.000000000000004C) flips those strict comparisons at exactly-integer readings, which are common on integer-C METAR feeds. The primary population rounds the converted extreme to 6 decimals before the band test; the rule functions are untouched. The literal un-rounded reference behaviour is reported as a non-gating variant (section 6); the number of entries it changes is in the JSON (`n_entries_changed_by_float_rounding`). This was decided before any price was read.
3. *Chicago feed holes.* IEM's ORD 1-minute archive is empty or sparse for most of 2026-04-14..2026-05-11 and has scattered partial days after (MDW and JFK return full data for the same period, so it is an ORD-specific upstream hole, and Track A saw the same). Days failing the pre-set guards (>=100 obs and last obs within 3 h of local midnight) are skipped and listed in section 8; no other station or cadence is substituted.
4. *Guards.* Completeness guards (Chicago 100 obs / 3 h; 30-min feeds 30 obs / 4 h; JMA 90 obs / 4 h) were fixed before any obs were read; Chicago equals Track A's.
5. *Timestamp used.* `timestamp_received` (when the archive collector saw the event), not the exchange `timestamp`. When several rows share the first millisecond the primary price is the upper median of their asks (row order inside a millisecond is not recoverable); lowest/highest are reported as bounds in section 6.
6. *Signal time is the obs timestamp,* not the publication time of the obs. A +5 minute latency variant is reported in section 6.
7. *Window.* The frozen window (2026-04-14..2026-07-18) is used even though the archive now extends to about six months; nothing outside it was read.
8. *Thin book* (undefined in the registration) is defined as: no bid at the pricing event, or ask-bid >= 10c. It is descriptive only.
9. *Near-zero rungs.* A large share of item-2b entries are into rungs whose ask is a few tenths of a cent (entries at the start of a day into low rungs, and integer-reading dead-zone rungs on the C feeds). They are in the registered population and in the gating test. Section 6 shows the result with 3c < ask < 97c as a non-gating view, because a population dominated by near-zero-cost losers mechanically pulls the mean toward -0.1c and tightens its confidence interval.

