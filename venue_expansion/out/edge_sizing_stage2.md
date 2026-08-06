# EDGE_SIZING Stage 2 -- realistic conversion of the oracle upper bound

Spec: `venue_expansion/EDGE_SIZING_SPEC.md Stage 2 (frozen)`

## Method

For each of the 140 Stage-1 capturable markets (the spec asks for >=150; only 140 exist in the Stage-1 sample -- disclosed shortfall, used all of them): resolved station+kind via the same HIGH/LOW city map the deployed bot uses; pulled IEM 1-minute obs for the station over `[close_time-24h, close_time]` (verified to be exactly the local calendar day in the station's fixed standard-time offset); replayed `kwx_lock_rule.sustained_extreme` / `locked_orders` **verbatim** (MARGIN_F=1.0, sustain-3, glitch bounds, MAX_PAY_CENTS=98, all unmodified) minute-by-minute across Stage 1's cached final-60-minute candlesticks, using the REAL ask/bid at each minute for the MAX_PAY gate and the FULL day's obs (not just the last 60 minutes) for the running sustained extreme. A market is REALISTICALLY CAPTURABLE iff the rule's first winner-side lock timestamp is strictly earlier than the last minute Stage 1 found the winner side still buyable at <=98c net-positive.

## SEA ground-truth check (not in the 140-market sample -- checked directly)

- Ticker: `KXLOWTSEA-26JUL29-T57`, station SEA, feed used: iem_1min
- IEM coldest reading anywhere in the market's open-to-close window: **56.0F**
- Rule fires on IEM data: **False**
- Bot's own logged extreme_f: **55.94** at 2026-07-30T07:58:43Z
- Bot value corroborated by IEM: **False**

IEM 1-minute data for KSEA never reports below 56.0F anywhere in the market's open-to-close window (2026-07-28T14:00Z .. 2026-07-30T08:00Z); the deployed rule needs a sustained reading strictly below floor-margin=56.0F to lock NO on T57, so it NEVER fires on IEM data for this market -- CONFIRMS the prior finding. The bot's own log shows extreme_f=55.94, which is 0.06F below the rule's firing threshold and would have fired; IEM's coldest sustained reading (56.0F, integer-rounded) sits exactly on the non-firing side of that boundary. IEM's 1-minute feed appears to round/report in whole degrees F at KSEA, which is not fine-grained enough to reproduce the one real, already-verified fire this whole program is anchored to -- a material feed-fidelity gap, not a footnote.

## Structural finding: bracket markets are asymmetrically unlockable

locked_orders() is asymmetric by construction: a 'between' bracket rung can only ever lock NO (via cap-overshoot for HIGH markets / floor-undershoot for LOW markets); it has no code path to ever lock YES on a bracket, or to lock the 'never reached the bracket' flavor of NO. This is a structural property of the deployed rule, independent of feed quality -- it caps the achievable conversion rate regardless of how good the obs feed is.

- Theoretically lockable by rule shape: 63 of 140
- Conversion rate among ONLY the theoretically-lockable subset: 1/63 = 0.0159 (Wilson 95% CI [0.0028, 0.0846])

## Conversion rates (of all 140 Stage-1 capturable markets)

| variant | realistic | of | rate | Wilson 95% CI |
|---|---|---|---|---|
| no delay (backtest, IEM content only) | 1 | 140 | 0.0071 | [0.0013, 0.0393] |
| +10min (MADIS-like) | 1 | 140 | 0.0071 | [0.0013, 0.0393] |
| +20min | 0 | 140 | 0.0000 | [0.0000, 0.0267] |

## Capacity ($/month), each labelled

| basis | mean estimator | median estimator (primary) |
|---|---|---|
| oracle (Stage 1 ceiling) | $45,756.11 | $2,114.72 |
| realistic (Stage 2, no delay) | $326.83 | $15.11 |
| latency-adjusted (+10min) | $326.83 | $15.11 |
| latency-adjusted (+20min) | $0.00 | $0.00 |

Stage 1's mean estimator ($45,756.11/mo) is ~22x the median ($2,114.72/mo) and is outlier-driven; the median is the primary number throughout.


**Depth caveat**: Candlesticks carry NO order-book depth. Volume traded during capturable minutes (and hence every capacity number derived from it) is an UPPER BOUND on what one participant could have taken.


**Feed-latency caveat**: IEM asos1min publishes 22-34h late; this is a backtest of feed CONTENT only. The 10/20-minute delays approximate what a live MADIS (~10min) or Synoptic (~1-5min) feed would additionally cost a real-time bot on top of the content already measured here.


## Verdict band

**under_50: retire the mechanical-lock live bot**


## Coverage / skips

{
 "stage1_capturable_markets": 140,
 "spec_asks_for": ">=150 (or all if fewer qualify)",
 "shortfall_disclosed": "only 140 Stage-1 capturable markets exist in the sample; used all 140",
 "skipped": 0,
 "scored": 140,
 "skip_reasons": {}
}


Feed used across scored markets: {
 "iem_1min": 135,
 "iem_routine_hourly": 5
}


## Per-market table

| ticker | series | result | strike_type | station | kind | feed | lockable? | last_capturable_ts | lock_ts | realistic | +10min | +20min | skip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KXLOWTHOU-26JUN27-B77.5 | KXLOWTHOU | yes | between | HOU | min | iem_1min | False | 1782623880 | None | False | False | False |  |
| KXLOWTDAL-26MAY30-B76.5 | KXLOWTDAL | yes | between | DFW | min | iem_1min | False | 1780205040 | None | False | False | False |  |
| KXLOWTPHX-26JUL18-B80.5 | KXLOWTPHX | yes | between | PHX | min | iem_routine_hourly | False | 1784443920 | None | False | False | False |  |
| KXLOWTCHI-26JUL31-B67.5 | KXLOWTCHI | no | between | MDW | min | iem_1min | True | 1785560460 | None | False | False | False |  |
| KXLOWTHOU-26JUN04-B74.5 | KXLOWTHOU | yes | between | HOU | min | iem_1min | False | 1780639200 | None | False | False | False |  |
| KXLOWTSFO-26JUN15-B57.5 | KXLOWTSFO | yes | between | SFO | min | iem_1min | False | 1781596260 | None | False | False | False |  |
| KXLOWTDC-26MAY28-B63.5 | KXLOWTDC | yes | between | DCA | min | iem_routine_hourly | False | 1780029900 | None | False | False | False |  |
| KXLOWTATL-26JUL03-B76.5 | KXLOWTATL | yes | between | ATL | min | iem_1min | False | 1783141200 | None | False | False | False |  |
| KXLOWTDC-26JUL04-B76.5 | KXLOWTDC | yes | between | DCA | min | iem_1min | False | 1783227480 | None | False | False | False |  |
| KXLOWTSFO-26MAY31-B48.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1780297200 | None | False | False | False |  |
| KXLOWTATL-26JUL17-B73.5 | KXLOWTATL | no | between | ATL | min | iem_1min | True | 1784348460 | None | False | False | False |  |
| KXLOWTMIA-26JUL21-B80.5 | KXLOWTMIA | no | between | MIA | min | iem_1min | True | 1784694360 | None | False | False | False |  |
| KXLOWTAUS-26JUL16-B72.5 | KXLOWTAUS | no | between | AUS | min | iem_1min | True | 1784267820 | None | False | False | False |  |
| KXLOWTNYC-26JUN19-B67.5 | KXLOWTNYC | no | between | NYC | min | iem_1min | True | 1781928600 | None | False | False | False |  |
| KXLOWTOKC-26JUL15-B67.5 | KXLOWTOKC | no | between | OKC | min | iem_1min | True | 1784180700 | None | False | False | False |  |
| KXLOWTMIA-26MAY29-B71.5 | KXLOWTMIA | no | between | MIA | min | iem_1min | True | 1780114380 | None | False | False | False |  |
| KXLOWTBOS-26AUG03-T69 | KXLOWTBOS | yes | greater | BOS | min | iem_routine_hourly | False | 1785818700 | None | False | False | False |  |
| KXLOWTSATX-26JUN09-T76 | KXLOWTSATX | no | greater | SAT | min | iem_1min | True | 1781069040 | None | False | False | False |  |
| KXLOWTAUS-26JUN05-B73.5 | KXLOWTAUS | yes | between | AUS | min | iem_1min | False | 1780725180 | None | False | False | False |  |
| KXLOWTNOLA-26JUN14-B76.5 | KXLOWTNOLA | yes | between | MSY | min | iem_1min | False | 1781503140 | None | False | False | False |  |
| KXLOWTMIA-26MAY24-B76.5 | KXLOWTMIA | no | between | MIA | min | iem_1min | True | 1779684300 | None | False | False | False |  |
| KXLOWTMIN-26JUL13-B74.5 | KXLOWTMIN | yes | between | MSP | min | iem_1min | False | 1784005740 | None | False | False | False |  |
| KXLOWTSATX-26JUN08-B74.5 | KXLOWTSATX | no | between | SAT | min | iem_1min | True | 1780983840 | None | False | False | False |  |
| KXLOWTLAX-26JUN06-T61 | KXLOWTLAX | yes | greater | LAX | min | iem_1min | False | 1780818420 | None | False | False | False |  |
| KXHIGHDEN-26JUL12-B96.5 | KXHIGHDEN | no | between | DEN | max | iem_1min | True | 1783925760 | None | False | False | False |  |
| KXLOWTPHIL-26JUL12-T68 | KXLOWTPHIL | yes | greater | PHL | min | iem_1min | False | 1783915260 | None | False | False | False |  |
| KXLOWTATL-26JUN14-B73.5 | KXLOWTATL | yes | between | ATL | min | iem_1min | False | 1781499360 | None | False | False | False |  |
| KXLOWTATL-26JUL05-T71 | KXLOWTATL | no | less | ATL | min | iem_1min | False | 1783313040 | None | False | False | False |  |
| KXLOWTSFO-26JUN15-B55.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1781593260 | None | False | False | False |  |
| KXLOWTDEN-26JUL08-T59 | KXLOWTDEN | no | less | DEN | min | iem_1min | False | 1783580400 | None | False | False | False |  |
| KXLOWTAUS-26JUN11-B77.5 | KXLOWTAUS | yes | between | AUS | min | iem_1min | False | 1781240700 | None | False | False | False |  |
| KXLOWTATL-26JUL14-B71.5 | KXLOWTATL | yes | between | ATL | min | iem_1min | False | 1784090040 | None | False | False | False |  |
| KXHIGHTPHX-26JUL14-B105.5 | KXHIGHTPHX | no | between | PHX | max | iem_1min | True | 1784098740 | None | False | False | False |  |
| KXLOWTSATX-26JUL23-T79 | KXLOWTSATX | no | less | SAT | min | iem_1min | False | 1784872380 | None | False | False | False |  |
| KXLOWTSFO-26MAY25-B53.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1779782400 | None | False | False | False |  |
| KXLOWTBOS-26JUL04-B73.5 | KXLOWTBOS | no | between | BOS | min | iem_1min | True | 1783227600 | None | False | False | False |  |
| KXLOWTOKC-26JUN11-B71.5 | KXLOWTOKC | no | between | OKC | min | iem_1min | True | 1781241600 | None | False | False | False |  |
| KXLOWTATL-26MAY24-B67.5 | KXLOWTATL | no | between | ATL | min | iem_1min | True | 1779682260 | None | False | False | False |  |
| KXLOWTDC-26JUN26-B67.5 | KXLOWTDC | no | between | DCA | min | iem_1min | True | 1782534960 | None | False | False | False |  |
| KXLOWTMIN-26JUL08-B68.5 | KXLOWTMIN | no | between | MSP | min | iem_1min | True | 1783575600 | None | False | False | False |  |
| KXLOWTSFO-26JUL25-T59 | KXLOWTSFO | yes | greater | SFO | min | iem_1min | False | 1785052800 | None | False | False | False |  |
| KXLOWTLAX-26JUL05-B62.5 | KXLOWTLAX | no | between | LAX | min | iem_1min | True | 1783323420 | None | False | False | False |  |
| KXLOWTLV-26JUL05-B80.5 | KXLOWTLV | no | between | LAS | min | iem_1min | True | 1783324260 | None | False | False | False |  |
| KXLOWTDC-26JUL26-T68 | KXLOWTDC | yes | greater | DCA | min | iem_1min | False | 1785125640 | None | False | False | False |  |
| KXLOWTSFO-26JUN21-B53.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1782112500 | None | False | False | False |  |
| KXLOWTMIN-26JUL21-B63.5 | KXLOWTMIN | yes | between | MSP | min | iem_1min | False | 1784699700 | None | False | False | False |  |
| KXLOWTCHI-26AUG02-B66.5 | KXLOWTCHI | yes | between | MDW | min | iem_1min | False | 1785736800 | None | False | False | False |  |
| KXLOWTNOLA-26JUN08-B76.5 | KXLOWTNOLA | yes | between | MSY | min | iem_1min | False | 1780983180 | None | False | False | False |  |
| KXLOWTDC-26JUN15-T66 | KXLOWTDC | yes | greater | DCA | min | iem_1min | False | 1781585340 | None | False | False | False |  |
| KXLOWTNYC-26JUN22-B67.5 | KXLOWTNYC | yes | between | NYC | min | iem_1min | False | 1782190320 | None | False | False | False |  |
| KXLOWTNYC-26JUL29-B66.5 | KXLOWTNYC | no | between | NYC | min | iem_1min | True | 1785387180 | None | False | False | False |  |
| KXLOWTPHX-26JUL12-B85.5 | KXLOWTPHX | no | between | PHX | min | iem_1min | True | 1783924980 | None | False | False | False |  |
| KXLOWTSFO-26JUN27-B55.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1782633600 | None | False | False | False |  |
| KXLOWTBOS-26JUN14-T65 | KXLOWTBOS | yes | greater | BOS | min | iem_1min | False | 1781496480 | None | False | False | False |  |
| KXLOWTLAX-26JUN03-B59.5 | KXLOWTLAX | yes | between | LAX | min | iem_1min | False | 1780556520 | None | False | False | False |  |
| KXLOWTMIA-26MAY28-B75.5 | KXLOWTMIA | yes | between | MIA | min | iem_1min | False | 1780030500 | None | False | False | False |  |
| KXLOWTSFO-26MAY29-B50.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1780124580 | None | False | False | False |  |
| KXLOWTNYC-26JUL25-B65.5 | KXLOWTNYC | yes | between | NYC | min | iem_1min | False | 1785039720 | None | False | False | False |  |
| KXLOWTNOLA-26JUL13-B71.5 | KXLOWTNOLA | no | between | MSY | min | iem_1min | True | 1784005620 | None | False | False | False |  |
| KXLOWTATL-26JUN18-B71.5 | KXLOWTATL | yes | between | ATL | min | iem_1min | False | 1781844420 | None | False | False | False |  |
| KXLOWTHOU-26JUN03-B74.5 | KXLOWTHOU | yes | between | HOU | min | iem_1min | False | 1780552680 | None | False | False | False |  |
| KXLOWTSFO-26JUN18-B56.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1781855760 | None | False | False | False |  |
| KXLOWTMIA-26MAY25-B76.5 | KXLOWTMIA | yes | between | MIA | min | iem_1min | False | 1779770400 | None | False | False | False |  |
| KXLOWTSFO-26JUL26-B57.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1785137400 | None | False | False | False |  |
| KXLOWTHOU-26JUL12-B78.5 | KXLOWTHOU | yes | between | HOU | min | iem_1min | False | 1783921920 | None | False | False | False |  |
| KXLOWTPHIL-26JUL09-T70 | KXLOWTPHIL | yes | greater | PHL | min | iem_1min | False | 1783656300 | None | False | False | False |  |
| KXLOWTDC-26JUN07-B72.5 | KXLOWTDC | yes | between | DCA | min | iem_routine_hourly | False | 1780894320 | None | False | False | False |  |
| KXLOWTATL-26JUL12-B71.5 | KXLOWTATL | no | between | ATL | min | iem_1min | True | 1783915980 | None | False | False | False |  |
| KXLOWTHOU-26JUN18-B78.5 | KXLOWTHOU | yes | between | HOU | min | iem_1min | False | 1781847300 | None | False | False | False |  |
| KXLOWTDAL-26JUN06-B69.5 | KXLOWTDAL | yes | between | DFW | min | iem_1min | False | 1780811580 | None | False | False | False |  |
| KXLOWTOKC-26JUN03-B69.5 | KXLOWTOKC | yes | between | OKC | min | iem_1min | False | 1780550460 | None | False | False | False |  |
| KXLOWTPHX-26AUG02-B92.5 | KXLOWTPHX | no | between | PHX | min | iem_1min | True | 1785737400 | None | False | False | False |  |
| KXLOWTDC-26JUN12-B69.5 | KXLOWTDC | no | between | DCA | min | iem_1min | True | 1781323320 | None | False | False | False |  |
| KXLOWTDC-26JUN27-B70.5 | KXLOWTDC | no | between | DCA | min | iem_1min | True | 1782622140 | None | False | False | False |  |
| KXLOWTATL-26JUL24-B72.5 | KXLOWTATL | no | between | ATL | min | iem_1min | True | 1784955300 | None | False | False | False |  |
| KXLOWTPHIL-26JUN23-B68.5 | KXLOWTPHIL | no | between | PHL | min | iem_1min | True | 1782275280 | None | False | False | False |  |
| KXHIGHDEN-26JUL18-B95.5 | KXHIGHDEN | no | between | DEN | max | iem_1min | True | 1784444340 | None | False | False | False |  |
| KXLOWTMIN-26JUN04-T64 | KXLOWTMIN | yes | greater | MSP | min | iem_1min | False | 1780639200 | None | False | False | False |  |
| KXHIGHDEN-26JUL12-B94.5 | KXHIGHDEN | yes | between | DEN | max | iem_1min | False | 1783925520 | None | False | False | False |  |
| KXLOWTLAX-26JUN19-B61.5 | KXLOWTLAX | yes | between | LAX | min | iem_1min | False | 1781942400 | None | False | False | False |  |
| KXLOWTLAX-26JUL18-B68.5 | KXLOWTLAX | yes | between | LAX | min | iem_routine_hourly | False | 1784447760 | None | False | False | False |  |
| KXLOWTCHI-26JUN01-B53.5 | KXLOWTCHI | no | between | MDW | min | iem_1min | True | 1780379760 | None | False | False | False |  |
| KXLOWTDEN-26JUN28-B56.5 | KXLOWTDEN | yes | between | DEN | min | iem_1min | False | 1782716340 | None | False | False | False |  |
| KXLOWTSEA-26MAY29-T46 | KXLOWTSEA | no | less | SEA | min | iem_1min | False | 1780125180 | None | False | False | False |  |
| KXLOWTDEN-26JUN19-B58.5 | KXLOWTDEN | yes | between | DEN | min | iem_1min | False | 1781938800 | None | False | False | False |  |
| KXLOWTNYC-26JUN01-T54 | KXLOWTNYC | yes | less | NYC | min | iem_1min | True | 1780375980 | None | False | False | False |  |
| KXLOWTCHI-26JUL16-T77 | KXLOWTCHI | yes | greater | MDW | min | iem_1min | False | 1784267760 | None | False | False | False |  |
| KXLOWTDC-26JUL17-B76.5 | KXLOWTDC | yes | between | DCA | min | iem_1min | False | 1784349960 | None | False | False | False |  |
| KXLOWTAUS-26JUL05-B73.5 | KXLOWTAUS | yes | between | AUS | min | iem_1min | False | 1783316820 | None | False | False | False |  |
| KXLOWTDC-26JUL09-T73 | KXLOWTDC | yes | greater | DCA | min | iem_1min | False | 1783659360 | None | False | False | False |  |
| KXLOWTBOS-26JUN07-B60.5 | KXLOWTBOS | no | between | BOS | min | iem_1min | True | 1780894800 | None | False | False | False |  |
| KXLOWTDAL-26MAY25-B65.5 | KXLOWTDAL | yes | between | DFW | min | iem_1min | False | 1779771900 | None | False | False | False |  |
| KXLOWTPHX-26JUL15-B87.5 | KXLOWTPHX | no | between | PHX | min | iem_1min | True | 1784185080 | None | False | False | False |  |
| KXLOWTDAL-26JUL07-B77.5 | KXLOWTDAL | yes | between | DFW | min | iem_1min | False | 1783488540 | None | False | False | False |  |
| KXLOWTNOLA-26JUL21-B81.5 | KXLOWTNOLA | yes | between | MSY | min | iem_1min | False | 1784699760 | None | False | False | False |  |
| KXLOWTDAL-26AUG01-B80.5 | KXLOWTDAL | yes | between | DFW | min | iem_1min | False | 1785650400 | None | False | False | False |  |
| KXLOWTPHIL-26JUL13-B65.5 | KXLOWTPHIL | no | between | PHL | min | iem_1min | True | 1784004900 | None | False | False | False |  |
| KXLOWTMIA-26JUN03-T71 | KXLOWTMIA | no | less | MIA | min | iem_1min | False | 1780549140 | None | False | False | False |  |
| KXLOWTLAX-26JUN03-B57.5 | KXLOWTLAX | no | between | LAX | min | iem_1min | True | 1780556460 | None | False | False | False |  |
| KXLOWTAUS-26JUL29-B75.5 | KXLOWTAUS | yes | between | AUS | min | iem_1min | False | 1785388200 | None | False | False | False |  |
| KXLOWTHOU-26JUN04-B72.5 | KXLOWTHOU | no | between | HOU | min | iem_1min | True | 1780638540 | None | False | False | False |  |
| KXLOWTMIA-26JUN03-B73.5 | KXLOWTMIA | yes | between | MIA | min | iem_1min | False | 1780549200 | None | False | False | False |  |
| KXLOWTPHIL-26JUL22-B74.5 | KXLOWTPHIL | yes | between | PHL | min | iem_1min | False | 1784782560 | None | False | False | False |  |
| KXLOWTDC-26JUN22-B70.5 | KXLOWTDC | no | between | DCA | min | iem_1min | True | 1782190440 | None | False | False | False |  |
| KXLOWTNYC-26JUN19-B65.5 | KXLOWTNYC | no | between | NYC | min | iem_1min | True | 1781928960 | None | False | False | False |  |
| KXLOWTATL-26JUL18-B73.5 | KXLOWTATL | yes | between | ATL | min | iem_1min | False | 1784433600 | None | False | False | False |  |
| KXLOWTMIN-26JUL06-B67.5 | KXLOWTMIN | yes | between | MSP | min | iem_1min | False | 1783404000 | None | False | False | False |  |
| KXLOWTSFO-26JUL25-B58.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1785052560 | None | False | False | False |  |
| KXLOWTCHI-26JUL21-B68.5 | KXLOWTCHI | no | between | MDW | min | iem_1min | True | 1784698500 | None | False | False | False |  |
| KXLOWTATL-26JUL17-B75.5 | KXLOWTATL | yes | between | ATL | min | iem_1min | False | 1784349360 | None | False | False | False |  |
| KXLOWTPHIL-26JUL06-B68.5 | KXLOWTPHIL | no | between | PHL | min | iem_1min | True | 1783400400 | None | False | False | False |  |
| KXLOWTDEN-26JUL22-T63 | KXLOWTDEN | no | less | DEN | min | iem_1min | False | 1784788620 | None | False | False | False |  |
| KXLOWTDAL-26AUG01-B82.5 | KXLOWTDAL | no | between | DFW | min | iem_1min | True | 1785648000 | None | False | False | False |  |
| KXLOWTAUS-26JUL18-B76.5 | KXLOWTAUS | yes | between | AUS | min | iem_1min | False | 1784440080 | None | False | False | False |  |
| KXLOWTATL-26JUN23-B70.5 | KXLOWTATL | no | between | ATL | min | iem_1min | True | 1782276840 | None | False | False | False |  |
| KXLOWTCHI-26JUL09-B72.5 | KXLOWTCHI | no | between | MDW | min | iem_1min | True | 1783663200 | None | False | False | False |  |
| KXLOWTAUS-26JUL06-T72 | KXLOWTAUS | no | less | AUS | min | iem_1min | False | 1783401600 | None | False | False | False |  |
| KXLOWTHOU-26JUN09-B77.5 | KXLOWTHOU | yes | between | HOU | min | iem_1min | False | 1781067780 | None | False | False | False |  |
| KXLOWTMIA-26JUN20-T74 | KXLOWTMIA | no | less | MIA | min | iem_1min | False | 1782016260 | None | False | False | False |  |
| KXLOWTDEN-26JUL27-B75.5 | KXLOWTDEN | no | between | DEN | min | iem_1min | True | 1785221700 | None | False | False | False |  |
| KXLOWTDEN-26JUN13-T50 | KXLOWTDEN | no | less | DEN | min | iem_1min | False | 1781419320 | None | False | False | False |  |
| KXLOWTNYC-26JUN11-B72.5 | KXLOWTNYC | yes | between | NYC | min | iem_1min | False | 1781238420 | None | False | False | False |  |
| KXLOWTOKC-26JUN19-B65.5 | KXLOWTOKC | no | between | OKC | min | iem_1min | True | 1781931660 | None | False | False | False |  |
| KXLOWTNYC-26MAY28-B63.5 | KXLOWTNYC | no | between | NYC | min | iem_1min | True | 1780030380 | 1780029540 | True | True | False |  |
| KXLOWTHOU-26JUN02-B75.5 | KXLOWTHOU | yes | between | HOU | min | iem_1min | False | 1780466400 | None | False | False | False |  |
| KXLOWTSFO-26JUN14-B56.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1781509920 | None | False | False | False |  |
| KXLOWTNOLA-26JUL31-B79.5 | KXLOWTNOLA | yes | between | MSY | min | iem_1min | False | 1785563880 | None | False | False | False |  |
| KXLOWTNOLA-26JUL30-B78.5 | KXLOWTNOLA | no | between | MSY | min | iem_1min | True | 1785474120 | None | False | False | False |  |
| KXLOWTLAX-26JUN22-T61 | KXLOWTLAX | yes | greater | LAX | min | iem_1min | False | 1782201540 | None | False | False | False |  |
| KXLOWTSATX-26MAY26-T64 | KXLOWTSATX | no | less | SAT | min | iem_1min | False | 1779861180 | None | False | False | False |  |
| KXLOWTMIN-26JUL20-B70.5 | KXLOWTMIN | yes | between | MSP | min | iem_1min | False | 1784610900 | None | False | False | False |  |
| KXLOWTSEA-26JUN16-B58.5 | KXLOWTSEA | yes | between | SEA | min | iem_1min | False | 1781682420 | None | False | False | False |  |
| KXLOWTSFO-26JUL10-B52.5 | KXLOWTSFO | no | between | SFO | min | iem_1min | True | 1783756740 | None | False | False | False |  |
| KXLOWTHOU-26JUN12-B77.5 | KXLOWTHOU | no | between | HOU | min | iem_1min | True | 1781326920 | None | False | False | False |  |
| KXLOWTLV-26JUN11-T80 | KXLOWTLV | yes | greater | LAS | min | iem_1min | False | 1781249700 | None | False | False | False |  |
| KXLOWTMIA-26JUN19-B75.5 | KXLOWTMIA | no | between | MIA | min | iem_1min | True | 1781929260 | None | False | False | False |  |
| KXLOWTDEN-26JUL07-B65.5 | KXLOWTDEN | yes | between | DEN | min | iem_1min | False | 1783493940 | None | False | False | False |  |
| KXLOWTAUS-26JUN22-B77.5 | KXLOWTAUS | no | between | AUS | min | iem_1min | True | 1782194400 | None | False | False | False |  |
| KXLOWTMIN-26JUN18-B54.5 | KXLOWTMIN | no | between | MSP | min | iem_1min | True | 1781846880 | None | False | False | False |  |
| KXLOWTMIN-26MAY27-B65.5 | KXLOWTMIN | no | between | MSP | min | iem_1min | True | 1779947220 | None | False | False | False |  |
