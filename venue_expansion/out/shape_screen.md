# SHAPE SCREEN - which Kalshi series stay open after their outcome is determined?

Generated 2026-10-27T18:16:51+00:00. Code: `venue_expansion/shape_screen.py` (seed 20261027). Data: `venue_expansion/out/shape_screen.json`. Every API pull is cached under `venue_expansion/cache/shape_screen/`.

> **STATUS: DESCRIPTIVE SCREEN, NOT A HYPOTHESIS TEST.** It carries no pass bar and produces no deployable claim. The capturable rate below is an ORACLE CEILING (perfect foreknowledge of the winner, zero latency, zero competition, all printed volume available to one taker). **Nothing on the shortlist may be promoted, sized, or traded without a NEW pre-registration** (frozen spec, frozen bars, adversarial verification) - the same bar every one of the 43 prior studies had to clear.

## 1. What was measured

Property: *the market stays open for hours after its outcome is physically determined.* Four structural classes, assigned from series/market metadata and rules text (never from outcomes):

| class | meaning | gap |
|---|---|---|
| DETERMINED-EARLY | outcome fixed materially before close and the venue keeps the book open (no venue-declared early close) | estimated, hours |
| DETERMINED-AT-CLOSE | resolves on a closing value / final print / value at a clock time | none by definition |
| CLOSES-AT-DECISION | venue's own early_close_condition shuts the market when the outcome occurs | none by construction |
| BULLETIN-PACED | resolves on an official release that is itself the fastest feed | none (no independent faster feed) |
| UNRESOLVED-BY-METADATA | no structural cue found in metadata (reported, not forced into a class) | unknown |

Empirical step: for each sampled settled market, 1-minute candlesticks for the final **120 minutes** before close, then `edge_sizing_v2.normalize()` + the v2 winner-cost rule (YES winner costs yes_ask; NO winner costs **100 - yes_bid**, never 100 - yes_ask; capturable minute iff cost <= 98c and net = 100 - cost - ceil(7p(1-p)) > 0). A market is *capturable* if any minute qualifies. The v2 code was imported, not re-written for the normalizer, and the winner-scan reproduces `edge_sizing_v2.scan()` exactly on 560 cached weather market-sides (0 mismatches; `selftest` stage).

**Why capturable rate alone cannot identify the property.** Any market whose outcome is still uncertain two hours out also has a winner buyable below 98c (the oracle knows the winner; nobody else does). The rate only means something when multiplied by an independently established determination gap - which is why classification comes first and why DETERMINED-AT-CLOSE series with 100% capturable rate carry zero score.

## 2. Coverage (read this before trusting any count)

| item | value |
|---|---|
| series in /series catalog | 15,416 |
| series in probe universe (recurring-frequency + seen in walked settled events) | 3,763 |
| series probed (one markets call each, newest 200 settled markets, MVE parlays excluded) | 1,857 |
| series with >= 20 settled markets in the live API window (classified) | 809 |
| markets planned for candle sample / with usable candles | 655 / 229 |
| candle skips | {"no_candles_in_window": 83, "not_yet_fetched": 343} |
| official-result re-check (GET /markets/{ticker} vs listing) | 0/0 agree |

Limits: (a) the live API only serves a rolling window of settled markets (~since 2026-05), so 'settled >= 20' is counted inside that window; (b) a non-recurring series with no settled event in the walked slice of the event listing was not probed; (c) 'newest 200' bounds per-series counts at 200 (`more` flag in the JSON); (d) candlesticks carry quotes at minutes that had activity - sparse markets have sparse minutes; (e) candlesticks have no order-book depth, so volume in capturable minutes is an upper bound on what one taker could have lifted.

## 3. Class summary

| class | series (>=20 settled) | contracts in returned markets | top categories |
|---|---|---|---|
| CLOSES-AT-DECISION | 460 | 5,430,187,643 | Sports 413, Crypto 10, Entertainment 8, Elections 8, Mentions 7 |
| BULLETIN-PACED | 146 | 65,578,513 | Economics 97, Entertainment 23, Financials 15, Politics 6, Sports 2 |
| DETERMINED-AT-CLOSE | 129 | 908,086,516 | Financials 56, Commodities 30, Crypto 26, Climate and Weather 9, Politics 5 |
| DETERMINED-EARLY | 71 | 71,737,912 | Climate and Weather 62, Economics 4, Politics 4, Entertainment 1 |
| UNRESOLVED-BY-METADATA | 3 | 451,341 | Economics 2, Politics 1 |

## 4. Measured oracle-capturable rate by sampled group

| group | markets | series | capturable (pooled) | Wilson 95% | series-mean rate | same, final 60 min | median priced-lead (min) | median winner cost T-60 | median winner cost T-10 |
|---|---|---|---|---|---|---|---|---|---|
| CONTROL-BULLETIN-PACED | 23 | 15 | 0.4783 | (0.2924, 0.6704) | 0.4889 | 0.3913 | 120 | 99 | 100 |
| CONTROL-CLOSES-AT-DECISION | 34 | 20 | 0.8824 | (0.7338, 0.9533) | 0.8 | 0.8235 | 19.6 | 83.0 | 100.0 |
| CONTROL-DETERMINED-AT-CLOSE | 25 | 20 | 0.64 | (0.4452, 0.7975) | 0.55 | 0.6 | 20.0 | 96.5 | 99 |
| CONTROL-UNRESOLVED-BY-METADATA | 3 | 2 | 0.6667 | (0.2077, 0.9385) | 0.5 | 0.6667 | 54.0 | 93.5 | 89 |
| EARLY-other | 41 | 10 | 0.2439 | (0.1382, 0.3934) | 0.2162 | 0.1463 | 120 | 100.0 | 100.0 |
| EARLY-weather | 103 | 53 | 0.0971 | (0.0536, 0.1696) | 0.0991 | 0.0777 | 120 | 100.0 | 100.0 |

`priced-lead` = minutes before close during which the winning side was NOT capturable (0 = capturable up to the last minute, i.e. outcome still open; 120 = never capturable in the window, i.e. the market had already repriced). `winner cost T-n` = cost of the eventual winner n minutes before close; a determined-early shape shows ~97-99c at T-60, an at-close shape shows a mid price.

**Positive-control reproduction.** edge_sizing_v2 (final 60 min, 40 US weather series, population-weighted) measured 10.0% capturable. This screen's weather sample (final 60 min of the same candles, sampled *per series* so heavily-traded and thin series weigh equally) gives 7.8% pooled; over the full 120 minutes 9.7%. Sampling frames differ, so agreement is directional, not exact.

## 5. Ranked shortlist (DETERMINED-EARLY candidates with >= 3 usable sampled markets)

Score = estimated determination gap (hours) x oracle-capturable rate x median volume (contracts) summed over the capturable minutes of a capturable market. Gap source: weather = MEASURED on US station-days from the cached IEM 1-minute archive (hours from the day's final extreme to market close); every other family = labelled ASSUMPTION. This is a ranking device, not a magnitude.

| # | series | title | subtype | gap h | capturable | median capt. vol | priced-lead min | score | graveyard verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | KXLOWTDEN | Lowest temperature in Denver | wx-daily-extreme | 17.97 | 0.25 (1/4) | 1955.42 | 120.0 | 8784.724 | RE-DISCOVERY |
| 2 | KXLOWTNYC | Lowest temperature in NYC | wx-daily-extreme | 17.97 | 0.33 (1/3) | 245.12 | 120 | 1468.122 | RE-DISCOVERY |
| 3 | KXLOWTDC | Lowest Temperature DC  | wx-daily-extreme | 17.97 | 0.67 (2/3) | 106.13 | 80.0 | 1271.501 | RE-DISCOVERY |
| 4 | KXTRUTHSOCIALD | Number of Trump Truth Social posts | running-count/mention | 0.25 | 0.25 (1/4) | 2730.48 | 120.0 | 170.655 | RE-DISCOVERY |
| 5 | KXTORNADO | Number of Tornadoes | running-count/mention | 0.25 | 0.33 (1/3) | 1506.05 | 120 | 125.492 | RE-DISCOVERY |
| 6 | KXFEDTWEETS | Fed tweets | running-count/mention | 0.25 | 0.40 (2/5) | 427.5 | 120 | 42.75 | RE-DISCOVERY |
| 7 | KXWEFTWEETS | WEF tweets | running-count/mention | 0.25 | 0.43 (3/7) | 2.0 | 120 | 0.214 | RE-DISCOVERY |
| 8 | KXHIGHAUS | Highest temperature in Austin | wx-daily-extreme | 9.07 | 0.00 (0/4) | 0.0 | 120.0 | 0.0 | RE-DISCOVERY |
| 9 | KXHIGHDEN | Highest temperature in Denver | wx-daily-extreme | 9.07 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 10 | KXHIGHLAX | Highest temperature in Los Angeles | wx-daily-extreme | 9.07 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 11 | KXHIGHTATL | Atlanta Max Temperature | wx-daily-extreme | 9.07 | 0.00 (0/4) | 0.0 | 120.0 | 0.0 | RE-DISCOVERY |
| 12 | KXHIGHTDAL | Dallas Maximum Temperature | wx-daily-extreme | 9.07 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 13 | KXHIGHTNOLA | New Orleans Max temp Daily | wx-daily-extreme | 9.07 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 14 | KXHIGHTSEA | Seattle Maximum Temperature Daily | wx-daily-extreme | 9.07 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 15 | KXIMFTWEETS | IMF tweets | running-count/mention | 0.25 | 0.75 (3/4) | 0.0 | 78.5 | 0.0 | RE-DISCOVERY |
| 16 | KXLOWTAUS | Lowest temperature in Austin | wx-daily-extreme | 17.97 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 17 | KXLOWTDAL | Lowest temperature Dallas | wx-daily-extreme | 17.97 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 18 | KXLOWTLV | Las Vegas Daily Low Temperature | wx-daily-extreme | 17.97 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 19 | KXLOWTOKC | Low Temperature Oklahoma City | wx-daily-extreme | 17.97 | 0.00 (0/3) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 20 | KXTRUTHSOCIAL | Number of Trump Truth Social posts | running-count/mention | 0.25 | 0.00 (0/5) | 0.0 | 120 | 0.0 | RE-DISCOVERY |
| 21 | KXTXERCOTPEAKD | Texas ERCOT peak electricity deman | daily-peak/extreme | 0.5 | 0.00 (0/5) | 0.0 | 120 | 0.0 | NEW (no ledger entry) |
| 22 | KXYTVIEWSW | Highest daily view count this week | daily-peak/extreme | 0.5 | 0.00 (0/5) | 0.0 | 120 | 0.0 | NEW (no ledger entry) |

### Family roll-up

| family | series | usable mkts | capturable (pooled) | median gap h | median capt. vol | median score/series | graveyard verdict |
|---|---|---|---|---|---|---|---|
| KXTRUTHSOCIALD | 1 | 4 | 0.25 | 0.25 | 2730.48 | 170.655 | RE-DISCOVERY: social-media / public-figure post counts -> #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; |
| KXTORNADO | 1 | 3 | 0.3333 | 0.25 | 1506.05 | 125.492 | RE-DISCOVERY: weather period products (rain / avg-temp streaks / tornado counts) -> same physical-feed mechanism as the KXHIGH/KXLOWT studies (#1,#2,#12, EDGE_SIZING) but these products were never tested; mention / |
| KXFEDTWEETS | 1 | 5 | 0.4 | 0.25 | 427.5 | 42.75 | RE-DISCOVERY: social-media / public-figure post counts -> #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; |
| KXWEFTWEETS | 1 | 7 | 0.4286 | 0.25 | 2.0 | 0.214 | RE-DISCOVERY: social-media / public-figure post counts -> #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; |
| KXHIGH* | 7 | 23 | 0.0 | 9.07 | 0.0 | 0.0 | RE-DISCOVERY: US daily-extreme temperature (KXHIGH*/KXLOWT*) -> #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fir |
| KXIMFTWEETS | 1 | 4 | 0.75 | 0.25 | 0.0 | 0.0 | RE-DISCOVERY: social-media / public-figure post counts -> #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; |
| KXLOWT* | 7 | 22 | 0.1818 | 17.97 | 0.0 | 0.0 | RE-DISCOVERY: US daily-extreme temperature (KXHIGH*/KXLOWT*) -> #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fir |
| KXTRUTHSOCIAL | 1 | 5 | 0.0 | 0.25 | 0.0 | 0.0 | RE-DISCOVERY: social-media / public-figure post counts -> #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; |
| KXTXERCOTPEAKD | 1 | 5 | 0.0 | 0.5 | 0.0 | 0.0 | NEW (no ledger entry):  |
| KXYTVIEWSW | 1 | 5 | 0.0 | 0.5 | 0.0 | 0.0 | NEW (no ledger entry):  |

### Same candidates ranked WITHOUT the gap term (capturable rate x median volume) - the check that the weather result is not produced by the gap column

| # | series | subtype | capturable | median capt. vol | gap-free score |
|---|---|---|---|---|---|
| 1 | KXTRUTHSOCIALD | running-count/mention | 0.25 (1/4) | 2730.48 | 682.62 |
| 2 | KXTORNADO | running-count/mention | 0.33 (1/3) | 1506.05 | 501.966 |
| 3 | KXLOWTDEN | wx-daily-extreme | 0.25 (1/4) | 1955.42 | 488.855 |
| 4 | KXFEDTWEETS | running-count/mention | 0.40 (2/5) | 427.5 | 171.0 |
| 5 | KXLOWTNYC | wx-daily-extreme | 0.33 (1/3) | 245.12 | 81.698 |
| 6 | KXLOWTDC | wx-daily-extreme | 0.67 (2/3) | 106.13 | 70.757 |
| 7 | KXWEFTWEETS | running-count/mention | 0.43 (3/7) | 2.0 | 0.857 |
| 8 | KXHIGHAUS | wx-daily-extreme | 0.00 (0/4) | 0.0 | 0.0 |
| 9 | KXHIGHDEN | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 10 | KXHIGHLAX | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 11 | KXHIGHTATL | wx-daily-extreme | 0.00 (0/4) | 0.0 | 0.0 |
| 12 | KXHIGHTDAL | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 13 | KXHIGHTNOLA | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 14 | KXHIGHTSEA | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 15 | KXIMFTWEETS | running-count/mention | 0.75 (3/4) | 0.0 | 0.0 |
| 16 | KXLOWTAUS | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 17 | KXLOWTDAL | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 18 | KXLOWTLV | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 19 | KXLOWTOKC | wx-daily-extreme | 0.00 (0/3) | 0.0 | 0.0 |
| 20 | KXTRUTHSOCIAL | running-count/mention | 0.00 (0/5) | 0.0 | 0.0 |

## 6. Screen sanity check - does it rediscover weather?

**SCREEN BROKEN OR WEATHER NOT PRESENT.** Weather family rank(s): [5, 7] of 10; gap-free first weather position: [3]. Per the task's own criterion this means the screen cannot be trusted until diagnosed.

## 7. Classifier-miss audit (non-EARLY series whose winners were already priced >= 60 min before close)

These are series the metadata classifier put in a no-gap class but whose measured price path looks like a determined-early shape (winner already at ~98c+ for the first hour of the window). Each needs a manual read of the rules text; a flag is a reason to look, not a finding.

| series | class | title | usable | median priced-lead min | capturable rate | median winner cost T-60 | median capt. vol |
|---|---|---|---|---|---|---|---|
| KXAAAGASDSC | BULLETIN-PACED | South Carolina gas price | 3 | 120 | 0.3333 | 99 | 0.0 |

## 8. Shortlist vs the graveyard: re-discovery or NEW?

| # | series | subtype | verdict | graveyard entries |
|---|---|---|---|---|
| 1 | KXLOWTDEN | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 2 | KXLOWTNYC | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 3 | KXLOWTDC | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 4 | KXTRUTHSOCIALD | running-count/mention | RE-DISCOVERY | social-media / public-figure post counts: #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; mention / said-word markets: #14, #22, #23, #25 |
| 5 | KXTORNADO | running-count/mention | RE-DISCOVERY | weather period products (rain / avg-temp streaks / tornado counts): same physical-feed mechanism as the KXHIGH/KXLOWT studies (#1,#2,#12, EDGE_SIZING) but these products were never tested; mention / said-word markets: #14, #22, #23, #25 |
| 6 | KXFEDTWEETS | running-count/mention | RE-DISCOVERY | social-media / public-figure post counts: #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; mention / said-word markets: #14, #22, #23, #25 |
| 7 | KXWEFTWEETS | running-count/mention | RE-DISCOVERY | social-media / public-figure post counts: #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; mention / said-word markets: #14, #22, #23, #25 |
| 8 | KXHIGHAUS | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 9 | KXHIGHDEN | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 10 | KXHIGHLAX | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 11 | KXHIGHTATL | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 12 | KXHIGHTDAL | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 13 | KXHIGHTNOLA | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 14 | KXHIGHTSEA | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 15 | KXIMFTWEETS | running-count/mention | RE-DISCOVERY | social-media / public-figure post counts: #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; mention / said-word markets: #14, #22, #23, #25 |
| 16 | KXLOWTAUS | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 17 | KXLOWTDAL | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 18 | KXLOWTLV | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 19 | KXLOWTOKC | wx-daily-extreme | RE-DISCOVERY | US daily-extreme temperature (KXHIGH*/KXLOWT*): #1 post-lock maker (REFUTED), #2 early-lock (NULL), #3-#11 directional SPECs, #12 near-miss conversion (NULL: market repriced before the lock rule fired in 10/10), #19 calibration fade (FAIL), #37 ensemble info-gap (NULL); EDGE_SIZING v2/stage2 (oracle |
| 20 | KXTRUTHSOCIAL | running-count/mention | RE-DISCOVERY | social-media / public-figure post counts: #14 earnings/mention markets (PROMISING-WEAKENED), #22/#23/#25 mention anchors (INCONCLUSIVE/FAIL) - mention-type mechanism, post-COUNT products not tested; mention / said-word markets: #14, #22, #23, #25 |


## 9. Caveats

- **Descriptive, not inferential.** No pass bar, no multiple-comparison control, no out-of-sample split. A ranked list from a screen over thousands of series is exactly where a plausible-looking positive is the default failure mode; every entry needs a frozen pre-registration before any claim.
- **Oracle ceiling.** Capturable = the *eventual winner* was buyable <= 98c with positive fee-inclusive net in some minute. It assumes foreknowledge, zero latency, zero competition, and the whole printed volume available to one taker. It cannot distinguish 'determined and slow to reprice' from 'simply still uncertain'; only the determination-gap column does that.
- **Gap estimates are the weakest column.** Weather is measured (IEM 1-minute: hours from the day's final extreme to close, US stations, 2026-05..10). Every other DETERMINED-EARLY gap is an assumed default because there is no independent feed in this screen to time the physical lock from. The gap-free ranking is shown beside the scored one for that reason.
- **Classification is rules-text + metadata, not outcome-aware**, and is heuristic. The empirical discriminator is off-schedule close timestamps (a venue that really shuts the book at the decision produces them; a fixed 23:59:59 close does not, whatever early_close_condition says). Misclassification is possible in both directions; section 7 audits the no-gap classes with measured price paths.
- **Live-window only.** Kalshi's live settled-market window is roughly the last 5 months; per-series counts and the 200-newest-market probe cap are inside that window. Series that settled before it (available via /historical) were not scanned, nor were non-recurring series absent from the walked slice of settled events (tier-3 coverage is reported in section 2).
- **Candlestick sparsity.** Minute candles exist where there was activity; thin markets have thin minutes. No order-book depth: volume in capturable minutes is an upper bound.
- **Sampling.** Weather sampled unconditionally (matches edge_sizing_v2's frame); non-weather samples are conditioned on the market having traded at least once, so their capturable rates are not comparable to the weather rate.
- **Outcomes** come only from `market.result` on the Kalshi market object; a random subset was re-fetched through GET /markets/{ticker} (agreement reported in section 2).

## Appendix A. Full classification table (every series with >= 20 settled markets in the probed universe)

| series | category | freq | n | class | subtype | gap h | conf | basis |
|---|---|---|---|---|---|---|---|---|
| KXHIGHLAX | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHNY | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXRAIN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close |
| KXHIGHMIA | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHCHI | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXTRUTHSOCIAL | Politics | weekly | 99 | DETERMINED-EARLY | running-count/mention | 0.25 | low | rules: running count / mention with scheduled close: number of |
| KXHIGHTPHX | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTSFO | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHAUS | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTATL | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHDEN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHPHIL | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTDAL | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXRAINWKND | Climate and We | weekly | 200+ | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close |
| KXHIGHTSEA | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTBOS | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTMIN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTHOU | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTOKC | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXTRUMPACT | Politics | weekly | 109 | DETERMINED-EARLY | running-count/mention | 0.25 | low | rules: running count / mention with scheduled close: at least 9 presidential |
| KXHIGHTDC | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTLV | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXTRUMPPHOTO | Politics | weekly | 51 | DETERMINED-EARLY | running-count/mention | 0.25 | low | rules: running count / mention with scheduled close: number of |
| KXLOWTNYC | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTNOLA | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTSATX | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXYTVIEWSW | Entertainment | weekly | 200+ | DETERMINED-EARLY | daily-peak/extreme | 0.5 | low | rules: running max/min over the period with scheduled close: at any point |
| KXLOWTDEN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTLAX | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTAUS | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXTRUTHSOCIALD | Politics | daily | 200+ | DETERMINED-EARLY | running-count/mention | 0.25 | low | rules: running count / mention with scheduled close: number of |
| KXLOWTCHI | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTMIA | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTOKC | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTSAN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTPHX | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXTXERCOTPEAKD | Economics | daily | 200+ | DETERMINED-EARLY | daily-peak/extreme | 0.5 | low | rules: running max/min over the period with scheduled close: highest hourly |
| KXLOWTLV | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTATL | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTDAL | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTHOU | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTEWR | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTMIN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTSFO | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTSDF | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTNOLA | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTDC | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTPHIL | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTBOS | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTTTN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXRAINNYCM | Climate and We | monthly | 25 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close |
| KXLOWTSDF | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXHIGHTEWR | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 9.07 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTSATX | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTSEA | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXAVGTKOKC | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close [sib |
| KXAVGTKAUS | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close [sib |
| KXLOWTTTN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXLOWTSAN | Climate and We | daily | 200+ | DETERMINED-EARLY | wx-daily-extreme | 17.97 | high | rules: daily max/min temperature; book stays open to a fixed last-trading time ('regardles |
| KXAVGTKIAH | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close [sib |
| KXAVGTKSAN | Climate and We | weekly | 45 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close [sib |
| KXAVGTKDFW | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close |
| KXAVGTKSAT | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close [sib |
| KXTORNADO | Climate and We | monthly | 22 | DETERMINED-EARLY | running-count/mention | 0.25 | low | rules: running count / mention with scheduled close: number of |
| KXAVGTKMSY | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close [sib |
| KXAVGTKPHX | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close |
| KXAVGTKLAS | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close |
| KXAVGTKDEN | Climate and We | weekly | 40 | DETERMINED-EARLY | wx-period-event | 3.0 | low | rules: weather event/accumulation over a period (monotone running state), fixed close [sib |
| KXIMFTWEETS | Economics | weekly | 24 | DETERMINED-EARLY | running-count/mention | 0.25 | low | rules: running count / mention with scheduled close: posts |
| KXFEDTWEETS | Economics | weekly | 24 | DETERMINED-EARLY | running-count/mention | 0.25 | low | rules: running count / mention with scheduled close: posts |
| KXWEFTWEETS | Economics | weekly | 24 | DETERMINED-EARLY | running-count/mention | 0.25 | low | rules: running count / mention with scheduled close: posts |
| KXTRUMPENDORSEMENTS | Politics | weekly | 79 | UNRESOLVED-BY-METADATA | unclear | 0.0 | low | no structural cue in metadata/rules |
| KXTSAW | Economics | weekly | 200+ | UNRESOLVED-BY-METADATA | unclear | 0.0 | low | no structural cue in metadata/rules |
| KXBRAZILINF | Economics | monthly | 22 | UNRESOLVED-BY-METADATA | unclear | 0.0 | low | no structural cue in metadata/rules |
| KXBTC15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXGOLD15M | Commodities | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXETH15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXXRP15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXWTI15M | Commodities | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSOL15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXRT | Entertainment | custom | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXDOGE15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSILVER15M | Commodities | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTRUMPAPPROVE | Politics | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXHYPE15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXZEC15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNEAR15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBNB15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNATGAS15M | Commodities | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXCOPPER15M | Commodities | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXWTI | Commodities | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBTCD | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXWTIW | Commodities | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXAPRPOTUS | Politics | weekly | 80 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXPALLADIUM15M | Commodities | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXPLATINUM15M | Commodities | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBRENTW | Commodities | weekly | 200 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXEURUSD15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBRENT15M | Commodities | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXGBPUSD15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDJPY15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXAUDUSD15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXINXDUD | Financials | daily | 46 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDCAD15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXVHGCB | Politics | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXGOLDD | Commodities | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTOPMODEL | Science and Te | monthly | 39 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBRENTMON | Commodities | monthly | 60 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNATGASW | Commodities | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXACTBLUETOP | Politics | weekly | 69 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBRENTD | Commodities | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPMIAH | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXGOLDW | Commodities | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTRUMPNOMNUM | Politics | weekly | 40 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXRTX5090WS | Financials | weekly | 136 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX2YRRATE15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXCOPPERW | Commodities | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXINXU | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXH200WS | Financials | weekly | 98 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXEURUSDAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXCOPPERMON | Commodities | monthly | 90 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXCOPPERD | Commodities | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXGOLDMON | Commodities | monthly | 100 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXB200WS | Financials | weekly | 124 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSILVERD | Commodities | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNASDAQDUD | Financials | daily | 46 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSILVERW | Commodities | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXINX | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPNYCHS | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXNATGASD | Commodities | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSILVERMON | Commodities | monthly | 80 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX10YRRATE15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX5YRRATE15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX30YRRATE15M | Financials | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXEURUSD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXCRYPTOLEAD15M | Crypto | fifteen_min | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXGOLDH | Commodities | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXB200MS | Financials | monthly | 28 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPCHIHS | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXETHD | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPLAXHS | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXDJI | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDJPY | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBTC | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNASDAQ100U | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPLAXH | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXUSDCADAW | Financials | weekly | 200 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNATGASMON | Commodities | monthly | 80 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDCHFAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXAUDUSDAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNASDAQ100 | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX10YRRATEH | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSHIBA | Crypto | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSHIBAD | Crypto | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPNYCH | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXNZDUSD | Financials | weekly | 200 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPCHIH | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXGBPUSDAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX30YRRATEH | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSILVERH | Commodities | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXINXHUD | Financials | one_off | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXDDR5EMS | Financials | monthly | 60 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX2YRRATEH | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX5YRRATEH | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDMXNAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXPLATINUMH | Commodities | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KX7YRRATEH | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXXRPD | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPAUSH | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXETH | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDJPYAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDNOKAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDBRLAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDINRAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDJPYAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXWTIH | Commodities | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXDDR5MS | Financials | monthly | 70 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDSEKAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXGBPUSDAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDINRAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDNOKAW | Financials | weekly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDBRLAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBNBD | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDMXNAD | Financials | daily | 40 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNZDUSDAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDCHFAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTEMPDCH | Climate and We | hourly | 200+ | DETERMINED-AT-CLOSE | wx-clock-snapshot | 0.0 | high | rules: temperature read at a clock time |
| KXXRP | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXTOP3AID | Science and Te | daily | 30 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXPALLADIUMH | Commodities | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXHYPED | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXBNB | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXDDR5WS | Financials | weekly | 200 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNDQHUD | Financials | one_off | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSOLD | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXDOGED | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXDDR5EWS | Financials | weekly | 200 | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXHYPE | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXAUDUSDAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXDOGE | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXUSDCADAD | Financials | daily | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXSOLE | Crypto | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXNKY | Financials | hourly | 200+ | DETERMINED-AT-CLOSE | snapshot | 0.0 | medium | rules/category: value read at a clock time or closing level |
| KXAAAGASW | Economics | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASD | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXHORMUZWEEKLY | Politics | weekly | 101 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: IMF |
| KXCPIYOY | Economics | monthly | 47 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXCPI | Economics | monthly | 29 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXBALLONDORRANK | Sports | annual | 90 | BULLETIN-PACED | release-closes-market | 0.0 | high | early_close_condition: This market will close and expire early after the rankings are rele |
| KXNETFLIXRANKMOVIE | Entertainment | weekly | 109 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Netflix |
| KXAAAGASM | Economics | monthly | 80 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXNETFLIXRANKSHOW | Entertainment | weekly | 110 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Netflix |
| KXU3 | Economics | monthly | 28 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: seasonally adjusted |
| KXDIESELW | Economics | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXALBUMEQUIV | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Luminate |
| KXPAYROLLS | Economics | monthly | 32 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXHORMUZPEAK | Politics | weekly | 57 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: IMF |
| KXOPENSOURCESHARE | Science and Te | one_off | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Leaderboard |
| KXAAAGASWNJ | Economics | weekly | 200 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDME | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXCPICORE | Economics | monthly | 22 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: seasonally adjusted |
| KXAAAGASDVA | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXCPICOREYOY | Economics | monthly | 30 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXBABELMANDEBWEEKLY | Politics | weekly | 54 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: IMF |
| KXAAAGASDCT | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDIN | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDNY | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXARTISTSTREAMSY | Entertainment | annual | 200+ | BULLETIN-PACED | release-closes-market | 0.0 | high | early_close_condition: This market will close and expire early if the data for the January |
| KXAAAGASDNJ | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXPANAMAWEEKLY | Politics | weekly | 44 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: IMF |
| KXNETFLIXRANKSHOWRUNNERUP | Entertainment | weekly | 110 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Netflix |
| KX30YMORTW | Economics | weekly | 170 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Federal |
| KXAAAGASDIL | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXNETFLIXRANKMOVIERUNNERUP | Entertainment | weekly | 109 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Netflix |
| KXAAAGASDNH | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDMA | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDSC | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDWA | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDCA | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDMI | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDAL | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDLA | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDWI | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDFL | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDAR | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXTOPSONG | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Billboard |
| KXAAAGASDRI | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDNE | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDWV | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXHORMUZMAX | Politics | weekly | 63 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: IMF |
| KXBIGGESTQUAKE | Climate and We | daily | 200+ | BULLETIN-PACED | release-closes-market | 0.0 | high | early_close_condition: This market may close and expire early once USGS has reviewed and f |
| KXAAAGASDKY | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXNETFLIXRANKMOVIEGLOBAL | Entertainment | weekly | 97 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Netflix |
| KXSUEZWEEKLY | Politics | weekly | 50 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: IMF |
| KXAAAGASDOH | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDVT | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDMS | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDNC | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDAZ | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDCO | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDOR | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDID | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDPA | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXSOFRD | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Federal |
| KXAAAGASDMD | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDDE | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDTX | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDMT | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDGA | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDNV | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXDIESELD | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDND | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDKS | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDOK | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDMN | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDMO | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXDIESELMON | Economics | monthly | 56 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDTN | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDIA | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDHI | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDNM | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXYTTOPVIDEOG2D | Entertainment | one_off | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: chart |
| KXYTTOPVIDEO2D | Entertainment | one_off | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: chart |
| KXYTDAILYTOPVIDEOG | Entertainment | one_off | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: chart |
| KXAAAGASDWY | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXECONSTATCPIYOY | Economics | monthly | 46 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXAAAGASDSD | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXAAAGASDUT | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXSPRLVL | Economics | weekly | 112 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Energy Information |
| KXAAAGASDAK | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: AAA |
| KXNETFLIXRANKSHOWGLOBAL | Entertainment | weekly | 98 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Netflix |
| KXTRUEV | Economics | daily | 200+ | BULLETIN-PACED | release-closes-market | 0.0 | high | early_close_condition: This market will close and expire early if the economic data is rel |
| KXPUREALBUMS | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Luminate |
| KXNETFLIXRANKMOVIEGLOBAL2 | Entertainment | weekly | 97 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Netflix |
| KXJOBLESSCLAIMS | Economics | weekly | 109 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: jobless |
| KXUST10A | Financials | daily | 165 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXBILLBOARDRUNNERUPALBUM | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Billboard |
| KXZAISHARE | Science and Te | weekly | 28 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: OpenRouter |
| KX30YRDIRHM | Financials | monthly | 55 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXUST2A | Financials | daily | 185 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KX10YRDIRHM | Financials | monthly | 62 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXCPINDEX | Economics | monthly | 58 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: seasonally adjusted |
| KXUST30A | Financials | daily | 175 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXECONSTATU3 | Economics | monthly | 46 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXTGAW | Economics | weekly | 33 | BULLETIN-PACED | release-closes-market | 0.0 | high | early_close_condition: This market will close and expire early if the economic data is rel |
| KX30YRDIRLM | Financials | monthly | 55 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXECONSTATCPI | Economics | monthly | 21 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXUST5A | Financials | daily | 155 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KX10YRDIRLM | Financials | monthly | 48 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXUST7A | Financials | daily | 155 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXNETFLIXRANKSHOWGLOBAL2 | Entertainment | weekly | 97 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Netflix |
| KXBKNUGGETS | Economics | monthly | 24 | BULLETIN-PACED | release-closes-market | 0.0 | high | early_close_condition: This market will close and expire early if the economic data is rel |
| KXOER | Economics | monthly | 40 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXECONSTATCPICORE | Economics | monthly | 21 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXRANKLISTSONGTOP10 | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Billboard |
| KXUSGASCPI | Economics | monthly | 48 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXTSAD | Economics | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: first published |
| KX10YRDIRLW | Financials | weekly | 60 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXEIACRUDEW | Economics | weekly | 104 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Federal |
| KXSHELTERCPI | Economics | monthly | 34 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXBILLBOARDRUNNERUPSONG | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Billboard |
| KX7YRDIRLM | Financials | monthly | 29 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KX2YRDIRLM | Financials | monthly | 27 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXUSEDCARCPI | Economics | monthly | 22 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXUSRETAIL | Economics | monthly | 20 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KX5YRDIRLM | Financials | monthly | 28 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXECONSTATCORECPIYOY | Economics | monthly | 32 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXSARETAIL | Economics | monthly | 20 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXTOPALBUM | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Billboard |
| KXUSPPIYOY | Economics | monthly | 32 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KX10YRDIRHW | Financials | weekly | 60 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: U.S. Treasury |
| KXNHSALES | Economics | monthly | 24 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: seasonally adjusted |
| KXAMSAVO | Economics | weekly | 110 | BULLETIN-PACED | release-closes-market | 0.0 | high | early_close_condition: This market will close and expire early if the economic data is rel |
| KXMUSKNW | Financials | monthly | 20 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXNBAPTSLEADER | Sports | custom | 200+ | BULLETIN-PACED | release-closes-market | 0.0 | high | early_close_condition: This market will close and expire early when the official box score |
| KXSETLIST | Entertainment | one_off | 45 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Billboard |
| KXJOLTSOPEN | Economics | monthly | 20 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: seasonally adjusted |
| KXCONTCLAIMS | Economics | weekly | 99 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: seasonally adjusted |
| KXFAOFPI | Economics | monthly | 20 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: ecc: release |
| KXUSHOME | Economics | monthly | 36 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: FRED |
| KXIRANCRUDE | Economics | monthly | 22 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXUKRETAIL | Economics | monthly | 24 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXSATRADEBAL | Economics | monthly | 20 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXAIRFARECPI | Economics | monthly | 28 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Bureau |
| KXUSPPI | Economics | monthly | 26 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: ecc: release |
| KXUSISMSERV | Economics | monthly | 30 | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: ISM |
| KXBBCHARTPOSITIONALBUM | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Billboard |
| KXBBCHARTPOSITIONSONG | Entertainment | weekly | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: Billboard |
| KXYTDAILYTOPVIDEO | Entertainment | daily | 200+ | BULLETIN-PACED | official-release | 0.0 | medium | rules/source cite a publication: chart |
| KXNFLGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBAGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGAGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAMXGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXATPMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXWTAMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXODIMATCH | Sports | custom | 172 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNHLGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXWTACHALLENGERMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXATPCHALLENGERMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGUE1GAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLOLGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXARGPREMDIVGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXDIMAYORGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXWT20MATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXECULPGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXT20MATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXBOXING | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAPORTUGALGAME | Sports | custom | 192 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXPERLIGA1GAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXVALORANTGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXSUPERLIGGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXEPLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGATOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXAFCCLGAME | Sports | custom | 129 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFL1H | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXLALIGA2GAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXITFWMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGASPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXMLBF5TOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAMXTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGABTTS | Sports | custom | 94 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSERIEATOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXURYPDGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLOLMAP | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNWSLGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXITFMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXCHLLDPGAME | Sports | custom | 156 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBASPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXPRIMARYMOV | Elections | one_off | 176 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if certified election resul |
| KXEPLBTTS | Sports | custom | 80 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXWTADOUBLES | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXEPLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXATPSETWINNER | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNFLOT | Sports | custom | 107 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXALLSVENSKANGAME | Sports | custom | 195 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXWTASETWINNER | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXBTCMAXMON | Crypto | monthly | 33 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXIDNSLGAME | Sports | custom | 189 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXARGPREMDIVTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBATOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXCS2GAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGA1HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXLALIGA1H | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXARGNACBGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLTD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBOLPDIVGAME | Sports | custom | 192 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAMXSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXELITESERIENGAME | Sports | custom | 168 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAMX1HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNFLPASSYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL1HSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXDIMAYORTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXTRUMPMENTION | Mentions | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAMXBTTS | Sports | custom | 93 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL1HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL1Q | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXCANPLGAME | Sports | custom | 132 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLFIRSTTD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA1H | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXAFCCLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSLGREECEGAME | Sports | custom | 165 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGUE1TOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSERIEABTTS | Sports | custom | 80 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSERIEA1HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNFL3Q | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXLALIGASCORE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXPERLIGA1TOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL2H | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNFLPASSTDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLTIE | Sports | custom | 59 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLESCALATORRSHYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early if the event occurs. This ma |
| KXNHLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSERIEASPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAPORTUGALTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAMX1H | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXSUPERLIGTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXATPCHALLENGERDOUBLES | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXCBAGAME | Sports | custom | 156 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXARGPREMDIVBTTS | Sports | custom | 134 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGA1HSPREAD | Sports | custom | 186 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNBA1Q | Sports | custom | 156 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXECULPTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXDOTA2GAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFL2Q | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXCS2MAP | Sports | daily | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXVALORANTMAP | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGA2TOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL1QSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXDIMAYORBTTS | Sports | custom | 123 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXIDNSLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXCANPLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL4Q | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNFLTEAMTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL1QTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLFG | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE11HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNFLTEAMYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXATPGTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXSERIECGAME | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLFIRSTTDTEAM | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL3QSPREAD | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXETTANGAME | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLRSHYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE1SPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXWTAGTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXTRUMPMENTIONB | Mentions | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBBLGAME | Sports | custom | 96 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLTEAMSACK | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBTCMINMON | Crypto | monthly | 27 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXLIGUE1BTTS | Sports | custom | 72 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXAFCCL1HTOTAL | Sports | custom | 132 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNFLREC | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXARGPREMDIVSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXURYPDTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLESCALATORRECYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early if the event occurs. This ma |
| KXDENSUPERLIGATOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXATPGSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXITFDOUBLES | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLWINMARGIN | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the game is declared final. |
| KXCHLLDPTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXDIMAYORSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFL3QTOTAL | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXBBSERIEAGAME | Sports | custom | 80 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXAFCCLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAMX1HSPREAD | Sports | custom | 178 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXVOTEPRIMARY | Elections | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire when election results are certifi |
| KXNFL2HSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXLOLTOTALMAPS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNFLPASSINT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHL1PTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXWORLDNEWSMENTION | Mentions | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLRSHATT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA3Q | Sports | custom | 156 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXACBGAME | Sports | custom | 92 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBAPTS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE11H | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLRECYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAPORTUGAL1HTOTAL | Sports | custom | 192 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXDOTA2MAP | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXPRIMARYPLACE | Elections | one_off | 23 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if certified election resul |
| KXELITESERIENTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL2QSPREAD | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNFLNEXTTEAM | Sports | custom | 165 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the player joins a new t |
| KXNBA1HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBNBMINMON | Crypto | monthly | 41 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXLALIGAGOAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAPORTUGALSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGATCORNERS | Sports | custom | 188 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLWINS | Sports | custom | 200+ | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 96% of closes off-schedule, can_close_early 100% |
| KXNBA1HSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGATEAMTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSUPERLIGSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXPRIMARYTURNOUT | Elections | one_off | 34 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the official vote count  |
| KXNWSLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL2HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXTRUMPSAYCOMPANY | Mentions | one_off | 99 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the specified word or ph |
| KXNBA2Q | Sports | custom | 156 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGA1HBTTS | Sports | custom | 94 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBELGIANPLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLESCALATORREC | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early if the event occurs. This ma |
| KXNFLPASSCOMP | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL1HFT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the game is complete. This  |
| KXNFLPASSATT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA1QTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXITFWDOUBLES | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXSLGREECETOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA1QSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXHURCAT | Climate and We | custom | 68 | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 100% of closes off-schedule, can_close_early 100% |
| KXNBA3D | Sports | custom | 69 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLDSTTD | Sports | custom | 107 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBERNIEMENTION | Mentions | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLNBELITEGAME | Sports | custom | 80 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFL4QSPREAD | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXMLBINNINGTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early once the specified inning i |
| KXPERLIGA1SPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXECULPBTTS | Sports | custom | 71 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAMX1HBTTS | Sports | custom | 89 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGA2H | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAPORTUGAL1H | Sports | custom | 192 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXJBLEAGUEGAME | Sports | custom | 104 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAMXSCORE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGA2BTTS | Sports | custom | 110 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA2H | Sports | custom | 156 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXARGNACBTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA4Q | Sports | custom | 156 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXAFCCL1H | Sports | custom | 132 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXKBOSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFL2QTOTAL | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGA2SPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXATPEXACTMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBA3QTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXGEMINI | Science and Te | one_off | 21 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXEPLTCORNERS | Sports | custom | 160 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLRRYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXMLS1HSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXFIRSTHURRICANE | Climate and We | custom | 21 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the first hurricane occu |
| KXVANCEMENTION | Mentions | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXAFCCLBTTS | Sports | custom | 43 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSUPERLIGBTTS | Sports | custom | 72 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXXRPMAXMON | Crypto | monthly | 23 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXLOLSPREAD | Sports | custom | 60 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the match result is declare |
| KXSERIEA1HSPREAD | Sports | custom | 160 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNFL1HTEAMTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXECULPSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGAFIRSTGOAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXAHLGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLSFTY | Sports | custom | 106 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHLF10G | Sports | custom | 187 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early when its outcome has been d |
| KXLIGAPORTUGALBTTS | Sports | custom | 64 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXVALORANTTOTALMAPS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXROML1TOTAL | Sports | custom | 112 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLRACE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXKHLGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXDENSUPERLIGASPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXATP | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXCHLLDPSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXIDNSLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXEBASKETBALLGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXPERLIGA1BTTS | Sports | custom | 72 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXEPLSCORE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE1SCORE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL4QTOTAL | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLFFPTS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLFFPTSLADDER | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early if the event occurs. This ma |
| KXLIGAMX2H | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGA2HSPREAD | Sports | custom | 186 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNBA2D | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA3QSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXEMMYCOUNT | Entertainment | one_off | 117 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXEOWEEK | Politics | weekly | 37 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if complete Federal Registe |
| KXURYPDBTTS | Sports | custom | 81 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXPRIMARYMOVD | Elections | one_off | 73 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if certified election resul |
| KXNBA2QTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAMXTEAMTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXELITESERIENSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXURYPDSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXCANPLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXMLBINNINGWIN | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGACORNERS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSERIECTOTAL | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBALLONDORAWARD | Sports | annual | 60 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early after the event occurs. Thi |
| KXNHL2PTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXYTVIEWSHIGH | Entertainment | monthly | 200+ | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 99% of closes off-schedule, can_close_early 100% |
| KXIDNSLBTTS | Sports | custom | 62 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHL1P | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXARGNACBBTTS | Sports | custom | 186 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL1QBTTS | Sports | custom | 107 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNWSLBTTS | Sports | custom | 75 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE11HSPREAD | Sports | custom | 144 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNFLLADDERRECYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early if the event occurs. This ma |
| KXSOLMAXMON | Crypto | monthly | 25 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXWTA | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBA4QTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGA1HSCORE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXMLBSERIESSCORE | Sports | custom | 59 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBAAST | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLASTWORDMENTION | Mentions | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLEQBTTS | Sports | custom | 107 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLLADDERRSHYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early if the event occurs. This ma |
| KXDENSUPERLIGABTTS | Sports | custom | 50 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA4QSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLBOTH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSERIEA1HBTTS | Sports | custom | 80 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXWEEKSNUM1 | Entertainment | one_off | 27 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the specified week count |
| KXNBA2QSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXTRUMPNUMSTATES | Politics | monthly | 31 | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 100% of closes off-schedule, can_close_early 100% |
| KXBELGIANPLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNEXTTEAMNFL | Sports | custom | 96 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBAREB | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXELHGAME | Sports | custom | 196 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLTDPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLPASSYDSPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHLGOAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNCAAWVMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE12H | Sports | custom | 189 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBATEAMTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXOWGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLTEAMFIRSTTD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA3PT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLOLFBLOOD | Sports | custom | 153 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXSLGREECESPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGUE1TEAMTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXCS2TOTALMAPS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNFLLADDERREC | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early if the event occurs. This ma |
| KXNCAAFWINS | Sports | annual | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: The market will close and expire early once the event occurs. The m |
| KXCHLLDPBTTS | Sports | custom | 50 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHL3P | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLKLGAME | Sports | custom | 56 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXARGNACBSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXMLBMATCHUP | Sports | custom | 108 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the matchup is confirmed |
| KXNHLSAVE | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLWEEKCOMPETE | Sports | weekly | 24 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the player's NFL Week 1 gam |
| KXSERIECBTTS | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXEPL2HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXETTANTOTAL | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNWSLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNHLOT | Sports | custom | 187 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA2HSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXFROPLGAME | Sports | one_off | 105 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLLONGRSH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXETTANBTTS | Sports | one_off | 176 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHLTEAMTOTAL | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA2HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLMOSTRSHYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close after a winner is declared. This market will |
| KXCANPLBTTS | Sports | custom | 44 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBAOT | Sports | custom | 56 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLALIGA2HBTTS | Sports | custom | 94 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXALBUMRELEASEDATE | Entertainment | one_off | 38 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHL3PTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXDELGAME | Sports | custom | 172 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXELITESERIENBTTS | Sports | custom | 56 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHLPTS | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXCPICOMBO | Economics | monthly | 24 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if any component becomes im |
| KXLIGAMX1HSCORE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSGPPLSPREAD | Sports | custom | 105 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXWNBA4QSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLALIGA2HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXDPZ | Financials | one_off | 23 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXVOTEBR1 | Elections | one_off | 50 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire when election results are certifi |
| KXACBTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXAFCCLTEAMTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLOLQUALIFIERS | Sports | custom | 20 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHL2P | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXACBSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXBBLSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLRECPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFL3QBTTS | Sports | custom | 107 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBBLTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXAFCCL1HSPREAD | Sports | custom | 88 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXMLBPLAYOFFHOST | Sports | custom | 21 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a title holder is declared. |
| KXNFLPASSTDSPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXTRUMPMEETM | Politics | monthly | 31 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the meeting occurs. This |
| KXBELGIANPLBTTS | Sports | custom | 63 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNCAAFAPRANK | Sports | custom | 104 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE11HBTTS | Sports | custom | 72 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSLGREECEBTTS | Sports | custom | 55 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXEPL2HBTTS | Sports | custom | 80 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLLONGREC | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXMLBSTATCOUNT | Sports | custom | 22 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXLIGAPORTUGAL1HSPREAD | Sports | custom | 128 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXETTANSPREAD | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNHL1PSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFL2QBTTS | Sports | custom | 107 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNEXTMANAGERMLB | Sports | custom | 43 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXAUTBSLGAME | Sports | custom | 66 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXFROPLTOTAL | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXZECMINMON | Crypto | monthly | 83 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXNBARACE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early when the event occurs. This |
| KXNBAPRA | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXPHKLGAME | Sports | custom | 64 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXROML1SPREAD | Sports | custom | 76 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXEPL2HSPREAD | Sports | custom | 160 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXLIGUE11HSCORE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXCS2SPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the match result is declare |
| KXNFLRSHYDSPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXVALORANTSPREAD | Sports | custom | 102 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the match result is declare |
| KXNHLFIRSTGOAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAMX2HSPREAD | Sports | custom | 160 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXNBAWINMARGIN | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXSERIECSPREAD | Sports | one_off | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXAFCCL1HBTTS | Sports | custom | 44 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBBSERIEATOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXFEATURE | Entertainment | one_off | 139 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXAFCCLSCORE | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHLAST | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXEFOOTBALLGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBASTARTERS | Sports | custom | 121 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBABLK | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHL3PSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNBASTL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXCHESSFIDERATINGTOP | Sports | custom | 154 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire once the event occurs. This marke |
| KXFUNDRAISING | Politics | one_off | 119 | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 86% of closes off-schedule, can_close_early 100% |
| KXFROPLSPREAD | Sports | one_off | 161 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXMLBDEBUT | Sports | custom | 29 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLOLKILLS | Sports | custom | 102 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXLNBELITETOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNHL2PSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAMX2HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXDARTSMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAPROMATCH | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXUE | Economics | monthly | 142 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXCBASPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAMX2HBTTS | Sports | custom | 80 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLNBELITESPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXBBSERIEASPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFL4QBTTS | Sports | custom | 107 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXESOCCERGAME | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLOLFDRAGON | Sports | custom | 153 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNFLRECYDSPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXBBSERIEA2GAME | Sports | custom | 118 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLIGAMXGOAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLOLDRAGONKILLS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXLIGUE12HTOTAL | Sports | custom | 189 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXSERIEA2HBTTS | Sports | custom | 70 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXMLS2HSPREAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXMLBSERIESSPREAD | Sports | custom | 31 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNCAAMBAPRANK | Sports | custom | 36 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSERIEA2HTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXCBATOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXZECMAXMON | Crypto | monthly | 46 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXWNBA6POY | Sports | annual | 29 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGAPORTUGAL1HBTTS | Sports | custom | 64 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXHOLBORNVOTE | Elections | one_off | 31 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire when election results are certifi |
| KXNBA1HTEAMTOTAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXH100MON | Science and Te | monthly | 20 | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 100% of closes off-schedule, can_close_early 100% |
| KXNFLMOSTRECYDS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close after a winner is declared. This market will |
| KXDOTA2TOTALMAPS | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNBAPTSPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXALBUMLENGTH | Entertainment | one_off | 25 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXEMPLOYMENTCOMBO | Economics | monthly | 24 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if any component becomes im |
| KXLOLTOWERS | Sports | custom | 92 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNBAREBPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE12HBTTS | Sports | custom | 63 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXB200MON | Science and Te | monthly | 20 | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 100% of closes off-schedule, can_close_early 100% |
| KXNCAAFTOPAPRANK | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXSERIEA2HSPREAD | Sports | custom | 140 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXRUGBYFRA14MATCH | Sports | custom | 127 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXLOLFBARON | Sports | custom | 153 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXNFLWEEKMOSTPASSYDS | Sports | weekly | 198 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close after a winner is declared. This market will |
| KXNBASTOCK | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXFROPLBTTS | Sports | one_off | 35 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXH200MON | Science and Te | monthly | 30 | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 100% of closes off-schedule, can_close_early 100% |
| KXRANKLISTDJMAGTOP10 | Entertainment | one_off | 51 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE12HSPREAD | Sports | custom | 126 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the half ends. This market  |
| KXMLBLEADERPLAYOFF | Sports | custom | 195 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the season ends earlier  |
| KXNBAASTPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXPHLGAME | Sports | one_off | 28 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXBNBMAXMON | Crypto | monthly | 31 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXNFLFFWEEKTOP | Sports | weekly | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early in accordance with Rule 7.2. |
| KXLIGAMXFIRSTGOAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNBA3PTPROT | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNFLFFWEEKLEAD | Sports | weekly | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market may close and expire early in accordance with Rule 7.2. |
| KXNFLWEEKMOSTRECYDS | Sports | weekly | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close after a winner is declared. This market will |
| KXHYPEMINMON | Crypto | monthly | 21 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXNFLWEEKMOSTRSHYDS | Sports | weekly | 182 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close after a winner is declared. This market will |
| KXHYPEMAXMON | Crypto | monthly | 31 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the price criterion is m |
| KXNFLOWNERSTAKE | Sports | custom | 33 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after the event occurs. This mark |
| KXVOTEBERLIN | Elections | one_off | 36 | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 100% of closes off-schedule, can_close_early 100% |
| KXLIGUE1GOAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXNCAAFAPANY | Sports | custom | 30 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGMAGGAME | Sports | custom | 20 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXCHAMPTOURR1LEAD | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire after a winner is declared. This  |
| KXNFLDELAY | Sports | custom | 29 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXWNBAALLDEFENSE | Sports | custom | 58 | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXLIGUE1FIRSTGOAL | Sports | custom | 200+ | CLOSES-AT-DECISION | venue-closes-on-event | 0.0 | high | early_close_condition: This market will close and expire early if the event occurs. This m |
| KXYTVIEWSD | Entertainment | daily | 200+ | CLOSES-AT-DECISION | empirical-offschedule-close | 0.0 | medium | 68% of closes off-schedule, can_close_early 100% |
