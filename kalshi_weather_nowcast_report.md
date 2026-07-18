# Kalshi KXHIGH Weather Settlement-Nowcast Backtest

## Executive summary

**n = 808 city-days, 20 cities, 42 days (2026-06-06 to 2026-07-18).** ASOS(1-min)-vs-official-CLI full-day agreement = 0.975 (20/808 city-days disagree, almost always ASOS reading a touch *higher* than the eventual official value).

**LONG side (buy YES once running max clears strike+margin) -- a real but small, margin-sensitive, low-frequency edge, NOT a riskless one:**

- margin=1°F: fired 40x (0.050 of city-days), mean entry 0.3613, **win rate 0.575**, mean net PnL/ct 0.2031, day-clustered t=2.78 (n_clusters=26), locked-YES-settled-NO = 17, fillable 38/40.
- margin=2°F: fired 15x (0.019 of city-days), mean entry 0.6780, **win rate 0.933**, mean net PnL/ct 0.2449, day-clustered t=3.83 (n_clusters=14), locked-YES-settled-NO = 1, fillable 15/15.
- margin=3°F: fired 8x (0.010 of city-days), mean entry 0.8812, **win rate 0.875**, mean net PnL/ct -0.0091, day-clustered t=-0.28 (n_clusters=8), locked-YES-settled-NO = 1, fillable 7/8.

margin=1°F fires often (40x) but is dominated by raw 1-minute ASOS sensor noise: win rate only 57.5%, 17/40 'locked' events actually settled the other way -- this margin is NOT safe. margin=2°F is much better (93% win rate, 1/15 miss) with a genuinely large mean edge (~24.5c/contract, t=3.83), but n=15 over 6 weeks x 20 cities is thin, and going to margin=3°F does NOT fix the residual tail risk -- the one recurring miss (KXHIGHMIA-26JUN16-T95, ASOS read 98°F vs an official settlement of ≤95°F, a 3°F ASOS-vs-CLI gap) still fires at margin=3, while the higher margin pushes the average entry price to 88c and erases the edge (mean PnL turns *negative*, -0.9c/contract). There is a real irreducible tail: a free, un-QC'd 1-minute ASOS feed occasionally runs materially hotter than what NWS ultimately certifies, and no margin size cleanly separates 'genuine crossing' from 'this station's data quality'.

**SHORT side (buy NO late in the day, well below strike) -- honest null:**

- Fires on 0.844 of city-days but mean entry price is already 0.9948 (i.e. essentially 0 gap left) by the time it fires; mean net PnL/ct is 0.0007 (t=2.89) -- statistically detectable but economically meaningless (a fraction of a cent). Only 0.235 of fired events have any volume in the following 5 minutes -- most of the 'edge' is not fillable. Sweeping the late-day cutoff hour (15:00-21:00 LST) shows mean PnL shrinking and turning **negative** at later, 'more locked' cutoffs -- the opposite of what a real edge should do. This side is priced efficiently; there is no capturable edge here net of fees and realistic fills.

**Capacity:** mean open interest at execution is roughly 5,000-20,000 contracts and mean volume at the execution minute for LONG-side fires is tens to low-hundreds of contracts/minute -- individually fillable, but the LONG-side opportunity itself only fires 15-40 times across 20 cities over 6 weeks (margin-dependent), so aggregate deployable size is small (order low tens of thousands of dollars of notional over the period, not a scalable book).

**BLUNT VERDICT:** No riskless nowcast edge. The SHORT/locked-NO side is an honest null -- Kalshi's market makers are already watching the same obs and price it in before it is fillable. The LONG/locked-YES side has a real, fee-surviving, day-clustered-significant edge at a 2°F margin (t=3.83) with decent fills, but it is (a) low frequency (~0.2-1 event per city-week), (b) small-n and therefore not yet fully trustworthy, and (c) subject to a real, quantified tail risk from ASOS-vs-official-CLI disagreement (~2.5% of all city-days, occasionally 2-3°F, that can flip a 'locked' win into a near-total loss) that margin alone cannot fully engineer away. Deployable only as a small, carefully-margined, per-trade-capped position -- not a scalable strategy as specified, and it should be run live for longer before sizing it up.

---

Window: 2026-06-06 to 2026-07-18 (42 days), 20 KXHIGH city series.

City-days analyzed: **808** (skipped 32 for insufficient ASOS/candle data).

ASOS data resolution: using IEM's true **one-minute ASOS product** (`asos1min.py`), median obs gap across 20 stations = 1.0 min (min 1.0, max 1.0). The plain hourly-cadence ASOS archive endpoint was tested first and rejected: it visibly missed a real ~2F spike at KDEN on 2026-07-08 that occurred between two hourly readings and flipped a market's settlement (see below).


## 1. ASOS-observed vs official CLI settlement agreement (the key tail risk)

Comparing (full-LST-day ASOS max at the settlement station > strike) to the official Kalshi result: agreement = **788/808** (0.975). Disagreements: **20**.


Example disagreements (ASOS says one thing, official CLI settled the other):

| ticker | date | strike | ASOS full-day max | official result |
|---|---|---|---|---|
| KXHIGHDEN-26JUL09-T91 | 2026-07-09 | 91 | 92.0 | no |
| KXHIGHDEN-26JUN27-T97 | 2026-06-27 | 97 | 98.0 | no |
| KXHIGHDEN-26JUN18-T88 | 2026-06-18 | 88 | 89.0 | no |
| KXHIGHDEN-26JUN24-T90 | 2026-06-24 | 90 | 78.0 | yes |
| KXHIGHDEN-26JUN16-T93 | 2026-06-16 | 93 | 94.0 | no |
| KXHIGHMIA-26JUN16-T95 | 2026-06-16 | 95 | 98.0 | no |
| KXHIGHMIA-26JUN26-T95 | 2026-06-26 | 95 | 96.0 | no |
| KXHIGHTSEA-26JUL10-T78 | 2026-07-10 | 78 | 79.0 | no |
| KXHIGHTSEA-26JUN27-T70 | 2026-06-27 | 70 | 71.0 | no |
| KXHIGHTSFO-26JUL02-T71 | 2026-07-02 | 71 | 72.0 | no |
| KXHIGHTSFO-26JUN30-T73 | 2026-06-30 | 73 | 74.0 | no |
| KXHIGHTSFO-26JUN25-T70 | 2026-06-25 | 70 | 71.0 | no |
| KXHIGHTDC-26JUL11-T89 | 2026-07-11 | 89 | 85.0 | yes |
| KXHIGHTATL-26JUL16-T93 | 2026-07-16 | 93 | 94.0 | no |
| KXHIGHTATL-26JUL11-T94 | 2026-07-11 | 94 | 95.0 | no |


## 2. Decision-event backtest, by margin


### Margin = 1°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 40 / 808 city-days (fire rate 0.050)
- Mean execution price at t*: 0.3613 (median 0.2550)
- Realized win rate: 0.575
- **Locked-YES that settled the other way: 17** ['KXHIGHDEN-26JUL09-T91', 'KXHIGHDEN-26JUN27-T97', 'KXHIGHDEN-26JUN18-T88', 'KXHIGHDEN-26JUN16-T93', 'KXHIGHMIA-26JUN16-T95', 'KXHIGHMIA-26JUN26-T95', 'KXHIGHTSEA-26JUL10-T78', 'KXHIGHTSEA-26JUN27-T70', 'KXHIGHTSFO-26JUL02-T71', 'KXHIGHTSFO-26JUN30-T73', 'KXHIGHTSFO-26JUN25-T70', 'KXHIGHTATL-26JUL16-T93', 'KXHIGHTATL-26JUL11-T94', 'KXHIGHTDAL-26JUN06-T89', 'KXHIGHTOKC-26JUN12-T91', 'KXHIGHPHIL-26JUL11-T89', 'KXHIGHLAX-26JUN28-T72']
- Net PnL/contract: mean 0.2031, day-clustered SE 0.0730, **t = 2.78** (n=40, n_clusters=26)
- Worst trade: -0.6365 on 2026-06-25 (KXHIGHTSFO-26JUN25-T70)
- Capacity proxy: mean volume at execution candle = 64.4 contracts/min (median 7.0); mean open interest = 9340.9
- **Fillable (>0 volume in the 5min after t*): 38/40 (0.950)**, mean exec price when fillable = 0.3771, day-clustered t (fillable-only) = 2.88 (mean 0.2172, n=38)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=40, mean PnL = 0.2031
  - gap > 0.02: n=40, mean PnL = 0.2031
  - gap > 0.05: n=40, mean PnL = 0.2031

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 682 / 808 city-days (fire rate 0.844)
- Mean execution price at t*: 0.9948 (median 1.0000)
- Realized win rate: 0.996
- **Locked-NO that settled the other way: 3** ['KXHIGHDEN-26JUN24-T90', 'KXHIGHTDC-26JUL11-T89', 'KXHIGHTDAL-26JUN15-T85']
- Net PnL/contract: mean 0.0007, day-clustered SE 0.0003, **t = 2.89** (n=682, n_clusters=41)
- Worst trade: -0.0107 on 2026-06-24 (KXHIGHDEN-26JUN24-T90)
- Capacity proxy: mean volume at execution candle = 42.0 contracts/min (median 0.0); mean open interest = 9727.3
- **Fillable (>0 volume in the 5min after t*): 160/682 (0.235)**, mean exec price when fillable = 0.9967, day-clustered t (fillable-only) = 2.97 (mean 0.0030, n=160)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=24, mean PnL = 0.0212
  - gap > 0.02: n=13, mean PnL = 0.0313
  - gap > 0.05: n=6, mean PnL = 0.0415

### Margin = 2°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 15 / 808 city-days (fire rate 0.019)
- Mean execution price at t*: 0.6780 (median 0.7700)
- Realized win rate: 0.933
- **Locked-YES that settled the other way: 1** ['KXHIGHMIA-26JUN16-T95']
- Net PnL/contract: mean 0.2449, day-clustered SE 0.0639, **t = 3.83** (n=15, n_clusters=14)
- Worst trade: -0.1484 on 2026-06-16 (KXHIGHMIA-26JUN16-T95)
- Capacity proxy: mean volume at execution candle = 265.4 contracts/min (median 7.1); mean open interest = 13333.5
- **Fillable (>0 volume in the 5min after t*): 15/15 (1.000)**, mean exec price when fillable = 0.6780, day-clustered t (fillable-only) = 3.83 (mean 0.2449, n=15)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=14, mean PnL = 0.2624
  - gap > 0.02: n=14, mean PnL = 0.2624
  - gap > 0.05: n=13, mean PnL = 0.2797

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 646 / 808 city-days (fire rate 0.800)
- Mean execution price at t*: 0.9950 (median 1.0000)
- Realized win rate: 0.995
- **Locked-NO that settled the other way: 3** ['KXHIGHDEN-26JUN24-T90', 'KXHIGHTDC-26JUL11-T89', 'KXHIGHTDAL-26JUN15-T85']
- Net PnL/contract: mean 0.0003, day-clustered SE 0.0001, **t = 2.46** (n=646, n_clusters=41)
- Worst trade: -0.0107 on 2026-06-24 (KXHIGHDEN-26JUN24-T90)
- Capacity proxy: mean volume at execution candle = 42.5 contracts/min (median 0.0); mean open interest = 9211.6
- **Fillable (>0 volume in the 5min after t*): 145/646 (0.224)**, mean exec price when fillable = 0.9988, day-clustered t (fillable-only) = 2.95 (mean 0.0012, n=145)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=18, mean PnL = 0.0106
  - gap > 0.02: n=9, mean PnL = 0.0120
  - gap > 0.05: n=3, mean PnL = -0.0107

### Margin = 3°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 8 / 808 city-days (fire rate 0.010)
- Mean execution price at t*: 0.8812 (median 1.0000)
- Realized win rate: 0.875
- **Locked-YES that settled the other way: 1** ['KXHIGHMIA-26JUN16-T95']
- Net PnL/contract: mean -0.0091, day-clustered SE 0.0329, **t = -0.28** (n=8, n_clusters=8)
- Worst trade: -0.2320 on 2026-06-16 (KXHIGHMIA-26JUN16-T95)
- Capacity proxy: mean volume at execution candle = 1040.6 contracts/min (median 4.1); mean open interest = 19703.8
- **Fillable (>0 volume in the 5min after t*): 7/8 (0.875)**, mean exec price when fillable = 0.8643, day-clustered t (fillable-only) = -0.28 (mean -0.0104, n=7)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=3, mean PnL = -0.0242
  - gap > 0.02: n=3, mean PnL = -0.0242
  - gap > 0.05: n=2, mean PnL = -0.0550

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 570 / 808 city-days (fire rate 0.705)
- Mean execution price at t*: 0.9947 (median 1.0000)
- Realized win rate: 0.995
- **Locked-NO that settled the other way: 3** ['KXHIGHDEN-26JUN24-T90', 'KXHIGHTDC-26JUL11-T89', 'KXHIGHTDAL-26JUN15-T85']
- Net PnL/contract: mean 0.0001, day-clustered SE 0.0001, **t = 0.99** (n=570, n_clusters=41)
- Worst trade: -0.0107 on 2026-06-24 (KXHIGHDEN-26JUN24-T90)
- Capacity proxy: mean volume at execution candle = 39.5 contracts/min (median 0.0); mean open interest = 8400.0
- **Fillable (>0 volume in the 5min after t*): 117/570 (0.205)**, mean exec price when fillable = 0.9997, day-clustered t (fillable-only) = 1.35 (mean 0.0002, n=117)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=9, mean PnL = 0.0037
  - gap > 0.02: n=4, mean PnL = -0.0034
  - gap > 0.05: n=3, mean PnL = -0.0107

## 2b. SHORT side sensitivity to late-day cutoff hour (margin=1°F)

| cutoff (LST hr) | fired | fire rate | mean price | win rate | mean PnL | t (all) | fillable n | t (fillable) |
|---|---|---|---|---|---|---|---|---|
| 15:00 | 682 | 0.844 | 0.9948 | 0.996 | 0.0007 | 2.89 | 160 | 2.97 |
| 17:00 | 646 | 0.800 | 0.9952 | 0.995 | 0.0001 | 0.89 | 130 | 1.28 |
| 19:00 | 587 | 0.726 | 0.9949 | 0.995 | -0.0001 | -1.81 | 122 | n/a |
| 21:00 | 503 | 0.623 | 0.9941 | 0.994 | -0.0001 | -1.80 | 124 | n/a |

## 3. By city (margin=1, LONG side)

| series | city | station | city-days | fired | mean PnL |
|---|---|---|---|---|---|
| KXHIGHDEN | Denver | KDEN | 40 | 8 | 0.0835 |
| KXHIGHTSFO | San Francisco | KSFO | 40 | 7 | 0.0488 |
| KXHIGHMIA | Miami | KMIA | 40 | 3 | 0.1787 |
| KXHIGHTSEA | Seattle | KSEA | 41 | 3 | 0.1120 |
| KXHIGHTDC | Washington DC | KDCA | 38 | 3 | 0.8385 |
| KXHIGHTATL | Atlanta | KATL | 42 | 3 | 0.1294 |
| KXHIGHLAX | Los Angeles | KLAX | 38 | 3 | 0.4253 |
| KXHIGHTBOS | Boston | KBOS | 42 | 2 | 0.4544 |
| KXHIGHNY | New York (Central Park) | NYC | 41 | 2 | 0.2374 |
| KXHIGHTOKC | Oklahoma City | KOKC | 41 | 2 | 0.3674 |
| KXHIGHPHIL | Philadelphia | KPHL | 41 | 2 | -0.0151 |
| KXHIGHAUS | Austin (Bergstrom) | KAUS | 41 | 1 | 0.2272 |
| KXHIGHTDAL | Dallas | KDFW | 40 | 1 | -0.2528 |
| KXHIGHCHI | Chicago (Midway) | KMDW | 41 | 0 | n/a |
| KXHIGHTMIN | Minneapolis | KMSP | 40 | 0 | n/a |
| KXHIGHTSATX | San Antonio | KSAT | 41 | 0 | n/a |
| KXHIGHTLV | Las Vegas | KLAS | 38 | 0 | n/a |
| KXHIGHTPHX | Phoenix | KPHX | 40 | 0 | n/a |
| KXHIGHTHOU | Houston (Hobby) | KHOU | 41 | 0 | n/a |
| KXHIGHTNOLA | New Orleans | KMSY | 42 | 0 | n/a |

## 4. Verdict

(Full narrative verdict is in the Executive Summary at the top of this document.) In short: SHORT side = honest null (priced in, not fillable). LONG side = real, fee-surviving edge at margin=2°F (t=3.83, 93% win rate) but low-frequency, small-n, and carries a quantified, margin-resistant tail risk from ASOS-vs-official-CLI disagreement.
