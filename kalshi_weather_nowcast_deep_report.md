# Kalshi KXHIGH Weather Settlement-Nowcast Backtest -- DEEP HISTORY RERUN (v2)

## Executive summary

**n = 1272 city-days, 20 cities, 67 days (2026-05-12 to 2026-07-17 -- the FULL history Kalshi's API exposes for KXHIGH in this environment; see data-depth note below the table of contents).** ASOS(1-min)-vs-official-CLI full-day UNCONDITIONAL agreement = 0.975 (32/1272 city-days disagree).

**LONG side (buy YES once running max clears strike+margin), ALL 5 pre-registered margins x 3 gap thresholds tested and Bonferroni-corrected, no cherry-pick:**

- margin=1°F: fired 71x (0.056 of city-days, 7.42/week), mean entry 0.4003, **win rate 0.620**, cond. loss rate given fired 0.380 (Wilson-95 worst-case 0.497), mean net PnL/ct 0.2094, day-clustered t=4.15 (n_clusters=45), worst-case analytic EV=0.0931, settled-wrong-way=27, fillable 68/71.
- margin=2°F: fired 35x (0.028 of city-days, 3.66/week), mean entry 0.7386, **win rate 0.914**, cond. loss rate given fired 0.086 (Wilson-95 worst-case 0.224), mean net PnL/ct 0.1678, day-clustered t=4.60 (n_clusters=29), worst-case analytic EV=0.0297, settled-wrong-way=3, fillable 33/35.
- margin=3°F: fired 19x (0.015 of city-days, 1.99/week), mean entry 0.8468, **win rate 0.842**, cond. loss rate given fired 0.158 (Wilson-95 worst-case 0.376), mean net PnL/ct -0.0068, day-clustered t=-0.44 (n_clusters=17), worst-case analytic EV=-0.2246, settled-wrong-way=3, fillable 16/19.
- margin=4°F: fired 7x (0.006 of city-days, 0.73/week), mean entry 0.7371, **win rate 0.714**, cond. loss rate given fired 0.286 (Wilson-95 worst-case 0.641), mean net PnL/ct -0.0242, day-clustered t=-1.16 (n_clusters=7), worst-case analytic EV=-0.3796, settled-wrong-way=2, fillable 5/7.
- margin=5°F: fired 4x (0.003 of city-days, 0.42/week), mean entry 0.5400, **win rate 0.500**, cond. loss rate given fired 0.500 (Wilson-95 worst-case 0.850), mean net PnL/ct -0.0424, day-clustered t=-1.26 (n_clusters=4), worst-case analytic EV=-0.3924, settled-wrong-way=2, fillable 3/4.

**Bonferroni correction:** 15-cell pre-registered family (margin x gap threshold), corrected per-cell alpha = 0.00333 (|t| >= 2.94 required). See section 2c of the report for the full cell-by-cell table -- this determines which margins survive multiple-testing scrutiny versus which only looked significant under an uncorrected single-test alpha of 0.05.

**Tail-risk root cause, not just its rate:** decomposing the 27 margin=1 misses finds 1 are outright **raw-feed sensor/transmission glitches**, not genuine ASOS-vs-official-CLI methodology gaps -- e.g. {'ticker': 'KXHIGHLAX-26MAY24-T69', 'strike': 69, 'asos_full_day_max': 120.0}: a single free 1-min ASOS reading that is not a physically plausible temperature for that city/season. This is exactly the un-QC'd-feed risk the original 42-day report warned about in the abstract; deep history now shows a concrete example of it. It also means part of the tail is in principle cheaply fixable with a basic outlier filter (reject single-point spikes far outside the recent rolling range before treating them as a settlement-deciding cross) rather than being an irreducible property of the strategy -- a natural next iteration, not implemented here.

**SHORT side (buy NO late in the day, well below strike):**

- At margin=1°F, fires on 0.856 of city-days but mean entry price is already 0.9943 (little gap left) by the time it fires; mean net PnL/ct is -0.0008 (t=-0.65). Only 0.230 of fired events have any volume in the following 5 minutes -- most of any apparent 'edge' here is not fillable. This side is priced efficiently by Kalshi's book; see section 2b for the late-day-cutoff sweep. Kept as a comparison/control, not the object of this rerun (task brief is specifically about the LONG side).

**Capacity at the recommended margin (1°F):** ~7.42 fires/week across all 20 cities, 0.958 fillable, median fillable size 307.7 contracts, mean entry 0.4003 -- a rough weekly notional throughput of $875. This is inherently a low-frequency, small-book strategy, not a scalable one, regardless of verdict.

**BLUNT VERDICT: CONFIRMED.** 
Margin=1°F survives ALL three pre-specified bars on the full-history sample: n_fired=71 >= 8, Bonferroni-significant (p_bonferroni=0.0005 vs corrected alpha 0.00333), and worst-case (Wilson-95-upper-bound loss rate 0.497) analytic EV still positive at 0.0931/contract. The original 42-day, margin=2-only finding is now backed by a larger, honestly-corrected sample rather than a single cherry-picked cell. Deployable as a small, per-trade-capped position sized to the capacity figures above -- still not a scalable book, and should keep accumulating live data given the sample is still bounded by this environment's ~67-day Kalshi history ceiling.

---

**Requested** lookback: 400 days (an intentionally large upper bound). **Actual** history available and used: **2026-05-12 to 2026-07-17** (67 calendar days), 20 KXHIGH city series.

**Data-depth finding (read this first):** direct pagination probing of Kalshi's `/markets?series_ticker=...&status=settled` endpoint (and confirming with `max_close_ts` filters before the apparent floor) shows every KXHIGH* series in this environment starts at the SAME date, 2026-05-12, with the SAME market count. That is a hard floor on the Kalshi side, not a self-imposed limit -- this script fetches ALL of it (`LOOKBACK_DAYS=400` as an upper bound, real depth rediscovered from the data every run). IEM's ASOS 1-min archive was independently checked back to 2020 and has no such limit, so the ceiling here is specifically "how much settled KXHIGH history Kalshi exposes", not weather-data availability. This means the 'deep history' rerun is ~1.6x the original 42-day sample, not the 6-18 months / hundreds-of-events scale the task brief anticipated -- reported honestly below rather than working around it.

City-days analyzed: **1272** (skipped 68 for insufficient ASOS/candle data).

ASOS data resolution: using IEM's true **one-minute ASOS product** (`asos1min.py`), median obs gap across 20 stations = 1.0 min (min 1.0, max 1.0). The plain hourly-cadence ASOS archive endpoint was tested first and rejected: it visibly missed a real ~2F spike at KDEN on 2026-07-08 that occurred between two hourly readings and flipped a market's settlement (see below).


## 1. ASOS-observed vs official CLI settlement agreement -- the true tail risk

UNCONDITIONAL: comparing (full-LST-day ASOS max at the settlement station > strike) to the official Kalshi result across ALL city-days (not just fired events): agreement = **1240/1272** (0.975). Disagreements: **32** (0.025).

CONDITIONAL (the real loss probability): given the LONG decision event actually FIRES (running ASOS max clears strike+margin), the loss rate is `cond_loss_rate_given_fired` reported per margin in section 2 below -- this is what matters for sizing the trade, not the unconditional rate above, since firing already selects for days where ASOS ran hot relative to strike.


Example disagreements (ASOS says one thing, official CLI settled the other):

| ticker | date | strike | ASOS full-day max | official result |
|---|---|---|---|---|
| KXHIGHDEN-26JUL09-T91 | 2026-07-09 | 91 | 92.0 | no |
| KXHIGHDEN-26JUN27-T97 | 2026-06-27 | 97 | 98.0 | no |
| KXHIGHDEN-26JUN24-T90 | 2026-06-24 | 90 | 78.0 | yes |
| KXHIGHDEN-26JUN16-T93 | 2026-06-16 | 93 | 94.0 | no |
| KXHIGHDEN-26JUN18-T88 | 2026-06-18 | 88 | 89.0 | no |
| KXHIGHDEN-26MAY23-T74 | 2026-05-23 | 74 | 73.0 | yes |
| KXHIGHMIA-26JUN26-T95 | 2026-06-26 | 95 | 96.0 | no |
| KXHIGHMIA-26JUN16-T95 | 2026-06-16 | 95 | 98.0 | no |
| KXHIGHMIA-26MAY16-T91 | 2026-05-16 | 91 | 97.0 | no |
| KXHIGHTBOS-26MAY16-T80 | 2026-05-16 | 80 | 81.0 | no |
| KXHIGHTSEA-26JUL10-T78 | 2026-07-10 | 78 | 79.0 | no |
| KXHIGHTSEA-26JUN27-T70 | 2026-06-27 | 70 | 71.0 | no |
| KXHIGHTSFO-26JUL02-T71 | 2026-07-02 | 71 | 72.0 | no |
| KXHIGHTSFO-26JUN30-T73 | 2026-06-30 | 73 | 74.0 | no |
| KXHIGHTSFO-26JUN25-T70 | 2026-06-25 | 70 | 71.0 | no |
| KXHIGHTSFO-26MAY18-T80 | 2026-05-18 | 80 | 81.0 | no |
| KXHIGHTDC-26JUL11-T89 | 2026-07-11 | 89 | 85.0 | yes |
| KXHIGHTATL-26JUL16-T93 | 2026-07-16 | 93 | 94.0 | no |
| KXHIGHTATL-26JUL11-T94 | 2026-07-11 | 94 | 95.0 | no |
| KXHIGHTATL-26MAY30-T85 | 2026-05-30 | 85 | 86.0 | no |


## 2. Decision-event backtest, by margin


### Margin = 1°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 71 / 1272 city-days (fire rate 0.056)
- Mean execution price at t*: 0.4003 (median 0.2700)
- Realized win rate: 0.620
- **Locked-YES that settled the other way: 27** ['KXHIGHDEN-26JUL09-T91', 'KXHIGHDEN-26JUN27-T97', 'KXHIGHDEN-26JUN16-T93', 'KXHIGHDEN-26JUN18-T88', 'KXHIGHMIA-26JUN26-T95', 'KXHIGHMIA-26JUN16-T95', 'KXHIGHMIA-26MAY16-T91', 'KXHIGHTBOS-26MAY16-T80', 'KXHIGHTSEA-26JUL10-T78', 'KXHIGHTSEA-26JUN27-T70', 'KXHIGHTSFO-26JUL02-T71', 'KXHIGHTSFO-26JUN30-T73', 'KXHIGHTSFO-26JUN25-T70', 'KXHIGHTSFO-26MAY18-T80', 'KXHIGHTATL-26JUL16-T93', 'KXHIGHTATL-26JUL11-T94', 'KXHIGHTATL-26MAY30-T85', 'KXHIGHTATL-26MAY28-T88', 'KXHIGHTDAL-26JUN06-T89', 'KXHIGHTSATX-26MAY23-T85', 'KXHIGHTOKC-26JUN12-T91', 'KXHIGHTOKC-26MAY28-T84', 'KXHIGHTHOU-26MAY22-T90', 'KXHIGHPHIL-26JUL11-T89', 'KXHIGHPHIL-26JUN02-T80', 'KXHIGHLAX-26JUN28-T72', 'KXHIGHLAX-26MAY24-T69']
- Net PnL/contract: mean 0.2094, day-clustered SE 0.0504, **t = 4.15**, p (normal-approx, uncorrected) = 0.0000 (n=71, n_clusters=45)
- **Conditional loss rate given fired (the real tail risk): 0.380** | Wilson-95 worst-case upper bound on that loss rate given only n=71 fired events: **0.497**
  - Miss decomposition: 26 plausible ASOS-vs-CLI methodology gap(s) (station reads a few degrees hot vs the certified CLI value) vs **1 raw-feed glitch(es)** (overshoot>8F or a physically implausible reading) [{'ticker': 'KXHIGHLAX-26MAY24-T69', 'strike': 69, 'asos_full_day_max': 120.0}]
- Analytic EV/contract at point-estimate loss rate: 0.2094 (sanity check vs. empirical mean PnL above) | at Wilson-95 **worst-case** loss rate: **0.0931**
- Fires/week (over the 67-day window): 7.42
- Worst trade: -0.6952 on 2026-05-23 (KXHIGHTSATX-26MAY23-T85)
- Capacity proxy: mean volume at execution candle = 76.9 contracts/min (median 8.1); mean open interest = 9822.4; median fillable volume in the 5min after t* = 307.7 contracts
- **Fillable (>0 volume in the 5min after t*): 68/71 (0.958)**, mean exec price when fillable = 0.4160, day-clustered t (fillable-only) = 4.26 (mean 0.2207, n=68)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=71, mean PnL = 0.2094, t=4.15, p=0.0000
  - gap > 0.02: n=70, mean PnL = 0.2123, t=4.19, p=0.0000
  - gap > 0.05: n=68, mean PnL = 0.2180, t=4.25, p=0.0000

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 1089 / 1272 city-days (fire rate 0.856)
- Mean execution price at t*: 0.9943 (median 1.0000)
- Realized win rate: 0.994
- **Locked-NO that settled the other way: 7** ['KXHIGHDEN-26JUN24-T90', 'KXHIGHDEN-26MAY23-T74', 'KXHIGHTBOS-26MAY25-T75', 'KXHIGHTBOS-26MAY17-T88', 'KXHIGHTDC-26JUL11-T89', 'KXHIGHTDAL-26JUN15-T85', 'KXHIGHLAX-26MAY20-T76']
- Net PnL/contract: mean -0.0008, day-clustered SE 0.0013, **t = -0.65**, p (normal-approx, uncorrected) = 0.5140 (n=1089, n_clusters=66)
- Worst trade: -0.9720 on 2026-05-25 (KXHIGHTBOS-26MAY25-T75)
- Capacity proxy: mean volume at execution candle = 37.2 contracts/min (median 0.0); mean open interest = 9015.1; median fillable volume in the 5min after t* = 0.0 contracts
- **Fillable (>0 volume in the 5min after t*): 251/1089 (0.230)**, mean exec price when fillable = 0.9916, day-clustered t (fillable-only) = -0.70 (mean -0.0039, n=251)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=44, mean PnL = -0.0205, t=-0.65, p=0.5185
  - gap > 0.02: n=23, mean PnL = -0.0477, t=-0.80, p=0.4241
  - gap > 0.05: n=13, mean PnL = -0.0262, t=-0.35, p=0.7266

### Margin = 2°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 35 / 1272 city-days (fire rate 0.028)
- Mean execution price at t*: 0.7386 (median 0.8300)
- Realized win rate: 0.914
- **Locked-YES that settled the other way: 3** ['KXHIGHMIA-26JUN16-T95', 'KXHIGHMIA-26MAY16-T91', 'KXHIGHLAX-26MAY24-T69']
- Net PnL/contract: mean 0.1678, day-clustered SE 0.0365, **t = 4.60**, p (normal-approx, uncorrected) = 0.0000 (n=35, n_clusters=29)
- **Conditional loss rate given fired (the real tail risk): 0.086** | Wilson-95 worst-case upper bound on that loss rate given only n=35 fired events: **0.224**
  - Miss decomposition: 2 plausible ASOS-vs-CLI methodology gap(s) (station reads a few degrees hot vs the certified CLI value) vs **1 raw-feed glitch(es)** (overshoot>8F or a physically implausible reading) [{'ticker': 'KXHIGHLAX-26MAY24-T69', 'strike': 69, 'asos_full_day_max': 120.0}]
- Analytic EV/contract at point-estimate loss rate: 0.1678 (sanity check vs. empirical mean PnL above) | at Wilson-95 **worst-case** loss rate: **0.0297**
- Fires/week (over the 67-day window): 3.66
- Worst trade: -0.1589 on 2026-05-24 (KXHIGHLAX-26MAY24-T69)
- Capacity proxy: mean volume at execution candle = 212.5 contracts/min (median 5.0); mean open interest = 14555.3; median fillable volume in the 5min after t* = 470.9 contracts
- **Fillable (>0 volume in the 5min after t*): 33/35 (0.943)**, mean exec price when fillable = 0.7527, day-clustered t (fillable-only) = 4.66 (mean 0.1783, n=33)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=25, mean PnL = 0.2349, t=5.38, p=0.0000
  - gap > 0.02: n=25, mean PnL = 0.2349, t=5.38, p=0.0000
  - gap > 0.05: n=24, mean PnL = 0.2432, t=5.52, p=0.0000

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 1026 / 1272 city-days (fire rate 0.807)
- Mean execution price at t*: 0.9957 (median 1.0000)
- Realized win rate: 0.995
- **Locked-NO that settled the other way: 5** ['KXHIGHDEN-26JUN24-T90', 'KXHIGHTBOS-26MAY25-T75', 'KXHIGHTDC-26JUL11-T89', 'KXHIGHTDAL-26JUN15-T85', 'KXHIGHLAX-26MAY20-T76']
- Net PnL/contract: mean -0.0006, day-clustered SE 0.0010, **t = -0.63**, p (normal-approx, uncorrected) = 0.5306 (n=1026, n_clusters=66)
- Worst trade: -0.9720 on 2026-05-25 (KXHIGHTBOS-26MAY25-T75)
- Capacity proxy: mean volume at execution candle = 34.9 contracts/min (median 0.0); mean open interest = 8636.0; median fillable volume in the 5min after t* = 0.0 contracts
- **Fillable (>0 volume in the 5min after t*): 225/1026 (0.219)**, mean exec price when fillable = 0.9940, day-clustered t (fillable-only) = -0.70 (mean -0.0030, n=225)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=28, mean PnL = -0.0219, t=-0.62, p=0.5325
  - gap > 0.02: n=14, mean PnL = -0.0532, t=-0.77, p=0.4400
  - gap > 0.05: n=6, mean PnL = 0.0116, t=0.89, p=0.3753

### Margin = 3°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 19 / 1272 city-days (fire rate 0.015)
- Mean execution price at t*: 0.8468 (median 1.0000)
- Realized win rate: 0.842
- **Locked-YES that settled the other way: 3** ['KXHIGHMIA-26JUN16-T95', 'KXHIGHMIA-26MAY16-T91', 'KXHIGHLAX-26MAY24-T69']
- Net PnL/contract: mean -0.0068, day-clustered SE 0.0157, **t = -0.44**, p (normal-approx, uncorrected) = 0.6633 (n=19, n_clusters=17)
- **Conditional loss rate given fired (the real tail risk): 0.158** | Wilson-95 worst-case upper bound on that loss rate given only n=19 fired events: **0.376**
  - Miss decomposition: 2 plausible ASOS-vs-CLI methodology gap(s) (station reads a few degrees hot vs the certified CLI value) vs **1 raw-feed glitch(es)** (overshoot>8F or a physically implausible reading) [{'ticker': 'KXHIGHLAX-26MAY24-T69', 'strike': 69, 'asos_full_day_max': 120.0}]
- Analytic EV/contract at point-estimate loss rate: -0.0068 (sanity check vs. empirical mean PnL above) | at Wilson-95 **worst-case** loss rate: **-0.2246**
- Fires/week (over the 67-day window): 1.99
- Worst trade: -0.2320 on 2026-06-16 (KXHIGHMIA-26JUN16-T95)
- Capacity proxy: mean volume at execution candle = 485.8 contracts/min (median 20.0); mean open interest = 20403.0; median fillable volume in the 5min after t* = 179.7 contracts
- **Fillable (>0 volume in the 5min after t*): 16/19 (0.842)**, mean exec price when fillable = 0.8800, day-clustered t (fillable-only) = -0.40 (mean -0.0075, n=16)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=7, mean PnL = -0.0186, t=-0.45, p=0.6543
  - gap > 0.02: n=7, mean PnL = -0.0186, t=-0.45, p=0.6543
  - gap > 0.05: n=5, mean PnL = -0.0409, t=-0.68, p=0.4982

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 893 / 1272 city-days (fire rate 0.702)
- Mean execution price at t*: 0.9955 (median 1.0000)
- Realized win rate: 0.996
- **Locked-NO that settled the other way: 4** ['KXHIGHDEN-26JUN24-T90', 'KXHIGHTDC-26JUL11-T89', 'KXHIGHTDAL-26JUN15-T85', 'KXHIGHLAX-26MAY20-T76']
- Net PnL/contract: mean 0.0001, day-clustered SE 0.0000, **t = 1.31**, p (normal-approx, uncorrected) = 0.1904 (n=893, n_clusters=66)
- Worst trade: -0.0107 on 2026-06-24 (KXHIGHDEN-26JUN24-T90)
- Capacity proxy: mean volume at execution candle = 31.4 contracts/min (median 0.0); mean open interest = 7615.6; median fillable volume in the 5min after t* = 0.0 contracts
- **Fillable (>0 volume in the 5min after t*): 173/893 (0.194)**, mean exec price when fillable = 0.9939, day-clustered t (fillable-only) = 1.59 (mean 0.0003, n=173)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=13, mean PnL = 0.0039, t=1.39, p=0.1633
  - gap > 0.02: n=5, mean PnL = -0.0048, t=-0.92, p=0.3572
  - gap > 0.05: n=4, mean PnL = -0.0107, t=n/a, p=n/a

### Margin = 4°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 7 / 1272 city-days (fire rate 0.006)
- Mean execution price at t*: 0.7371 (median 1.0000)
- Realized win rate: 0.714
- **Locked-YES that settled the other way: 2** ['KXHIGHMIA-26MAY16-T91', 'KXHIGHLAX-26MAY24-T69']
- Net PnL/contract: mean -0.0242, day-clustered SE 0.0208, **t = -1.16**, p (normal-approx, uncorrected) = 0.2447 (n=7, n_clusters=7)
- **Conditional loss rate given fired (the real tail risk): 0.286** | Wilson-95 worst-case upper bound on that loss rate given only n=7 fired events: **0.641**
  - Miss decomposition: 1 plausible ASOS-vs-CLI methodology gap(s) (station reads a few degrees hot vs the certified CLI value) vs **1 raw-feed glitch(es)** (overshoot>8F or a physically implausible reading) [{'ticker': 'KXHIGHLAX-26MAY24-T69', 'strike': 69, 'asos_full_day_max': 120.0}]
- Analytic EV/contract at point-estimate loss rate: -0.0242 (sanity check vs. empirical mean PnL above) | at Wilson-95 **worst-case** loss rate: **-0.3796**
- Fires/week (over the 67-day window): 0.73
- Worst trade: -0.1589 on 2026-05-24 (KXHIGHLAX-26MAY24-T69)
- Capacity proxy: mean volume at execution candle = 14.3 contracts/min (median 0.0); mean open interest = 15535.8; median fillable volume in the 5min after t* = 9.3 contracts
- **Fillable (>0 volume in the 5min after t*): 5/7 (0.714)**, mean exec price when fillable = 0.8300, day-clustered t (fillable-only) = -1.12 (mean -0.0318, n=5)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=2, mean PnL = -0.0848, t=-1.62, p=0.1056
  - gap > 0.02: n=2, mean PnL = -0.0848, t=-1.62, p=0.1056
  - gap > 0.05: n=2, mean PnL = -0.0848, t=-1.62, p=0.1056

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 712 / 1272 city-days (fire rate 0.560)
- Mean execution price at t*: 0.9944 (median 1.0000)
- Realized win rate: 0.994
- **Locked-NO that settled the other way: 4** ['KXHIGHDEN-26JUN24-T90', 'KXHIGHTDC-26JUL11-T89', 'KXHIGHTDAL-26JUN15-T85', 'KXHIGHLAX-26MAY20-T76']
- Net PnL/contract: mean 0.0000, day-clustered SE 0.0000, **t = 0.12**, p (normal-approx, uncorrected) = 0.9079 (n=712, n_clusters=66)
- Worst trade: -0.0107 on 2026-06-24 (KXHIGHDEN-26JUN24-T90)
- Capacity proxy: mean volume at execution candle = 29.5 contracts/min (median 0.0); mean open interest = 6460.7; median fillable volume in the 5min after t* = 0.0 contracts
- **Fillable (>0 volume in the 5min after t*): 128/712 (0.180)**, mean exec price when fillable = 0.9920, day-clustered t (fillable-only) = 0.74 (mean 0.0001, n=128)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=8, mean PnL = 0.0005, t=0.12, p=0.9078
  - gap > 0.02: n=5, mean PnL = -0.0048, t=-0.92, p=0.3572
  - gap > 0.05: n=4, mean PnL = -0.0107, t=n/a, p=n/a

### Margin = 5°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 4 / 1272 city-days (fire rate 0.003)
- Mean execution price at t*: 0.5400 (median 0.5750)
- Realized win rate: 0.500
- **Locked-YES that settled the other way: 2** ['KXHIGHMIA-26MAY16-T91', 'KXHIGHLAX-26MAY24-T69']
- Net PnL/contract: mean -0.0424, day-clustered SE 0.0337, **t = -1.26**, p (normal-approx, uncorrected) = 0.2084 (n=4, n_clusters=4)
- **Conditional loss rate given fired (the real tail risk): 0.500** | Wilson-95 worst-case upper bound on that loss rate given only n=4 fired events: **0.850**
  - Miss decomposition: 1 plausible ASOS-vs-CLI methodology gap(s) (station reads a few degrees hot vs the certified CLI value) vs **1 raw-feed glitch(es)** (overshoot>8F or a physically implausible reading) [{'ticker': 'KXHIGHLAX-26MAY24-T69', 'strike': 69, 'asos_full_day_max': 120.0}]
- Analytic EV/contract at point-estimate loss rate: -0.0424 (sanity check vs. empirical mean PnL above) | at Wilson-95 **worst-case** loss rate: **-0.3924**
- Fires/week (over the 67-day window): 0.42
- Worst trade: -0.1589 on 2026-05-24 (KXHIGHLAX-26MAY24-T69)
- Capacity proxy: mean volume at execution candle = 25.0 contracts/min (median 18.0); mean open interest = 14523.4; median fillable volume in the 5min after t* = 21.7 contracts
- **Fillable (>0 volume in the 5min after t*): 3/4 (0.750)**, mean exec price when fillable = 0.7167, day-clustered t (fillable-only) = -1.22 (mean -0.0530, n=3)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=2, mean PnL = -0.0848, t=-1.62, p=0.1056
  - gap > 0.02: n=2, mean PnL = -0.0848, t=-1.62, p=0.1056
  - gap > 0.05: n=2, mean PnL = -0.0848, t=-1.62, p=0.1056

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 527 / 1272 city-days (fire rate 0.414)
- Mean execution price at t*: 0.9962 (median 1.0000)
- Realized win rate: 0.996
- **Locked-NO that settled the other way: 2** ['KXHIGHDEN-26JUN24-T90', 'KXHIGHLAX-26MAY20-T76']
- Net PnL/contract: mean -0.0000, day-clustered SE 0.0000, **t = -0.12**, p (normal-approx, uncorrected) = 0.9084 (n=527, n_clusters=66)
- Worst trade: -0.0107 on 2026-06-24 (KXHIGHDEN-26JUN24-T90)
- Capacity proxy: mean volume at execution candle = 33.2 contracts/min (median 0.0); mean open interest = 6632.7; median fillable volume in the 5min after t* = 0.0 contracts
- **Fillable (>0 volume in the 5min after t*): 89/527 (0.169)**, mean exec price when fillable = 0.9887, day-clustered t (fillable-only) = 0.37 (mean 0.0001, n=89)
- Gap-threshold sensitivity (min required 1-price edge; part of the pre-registered Bonferroni test family for the LONG side, see section 2c):
  - gap > 0.0: n=3, mean PnL = -0.0009, t=-0.12, p=0.9083
  - gap > 0.02: n=3, mean PnL = -0.0009, t=-0.12, p=0.9083
  - gap > 0.05: n=2, mean PnL = -0.0107, t=n/a, p=n/a

## 2b. SHORT side sensitivity to late-day cutoff hour (margin=1°F)

| cutoff (LST hr) | fired | fire rate | mean price | win rate | mean PnL | t (all) | fillable n | t (fillable) |
|---|---|---|---|---|---|---|---|---|
| 15:00 | 1089 | 0.856 | 0.9943 | 0.994 | -0.0008 | -0.65 | 251 | -0.70 |
| 17:00 | 1030 | 0.810 | 0.9951 | 0.995 | 0.0001 | 0.83 | 204 | 1.14 |
| 19:00 | 948 | 0.745 | 0.9948 | 0.995 | -0.0001 | -2.33 | 197 | -1.02 |
| 21:00 | 827 | 0.650 | 0.9940 | 0.994 | -0.0001 | -2.32 | 187 | -1.43 |

## 2c. Multiple-testing correction (Bonferroni) -- LONG side, margin x gap-threshold

Pre-registered test family: **15 cells** = 5 margins x 3 gap thresholds, ALL tested and reported (no post-hoc pick of the best-looking cell). Family-wise alpha = 0.05, Bonferroni-corrected per-cell alpha = **0.00333** (two-sided normal-approx |t| >= 2.94 required for significance).

| margin | gap thr | n | mean PnL | t | p (uncorrected) | p (Bonferroni) | sig @ .05 uncorr. | **sig @ Bonferroni** |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 71 | 0.2094 | 4.15 | 0.0000 | 0.0005 | yes | **YES** |
| 1 | 0.02 | 70 | 0.2123 | 4.19 | 0.0000 | 0.0004 | yes | **YES** |
| 1 | 0.05 | 68 | 0.2180 | 4.25 | 0.0000 | 0.0003 | yes | **YES** |
| 2 | 0.0 | 25 | 0.2349 | 5.38 | 0.0000 | 0.0000 | yes | **YES** |
| 2 | 0.02 | 25 | 0.2349 | 5.38 | 0.0000 | 0.0000 | yes | **YES** |
| 2 | 0.05 | 24 | 0.2432 | 5.52 | 0.0000 | 0.0000 | yes | **YES** |
| 3 | 0.0 | 7 | -0.0186 | -0.45 | 0.6543 | 1.0000 | no | no |
| 3 | 0.02 | 7 | -0.0186 | -0.45 | 0.6543 | 1.0000 | no | no |
| 3 | 0.05 | 5 | -0.0409 | -0.68 | 0.4982 | 1.0000 | no | no |
| 4 | 0.0 | 2 | -0.0848 | -1.62 | 0.1056 | 1.0000 | no | no |
| 4 | 0.02 | 2 | -0.0848 | -1.62 | 0.1056 | 1.0000 | no | no |
| 4 | 0.05 | 2 | -0.0848 | -1.62 | 0.1056 | 1.0000 | no | no |
| 5 | 0.0 | 2 | -0.0848 | -1.62 | 0.1056 | 1.0000 | no | no |
| 5 | 0.02 | 2 | -0.0848 | -1.62 | 0.1056 | 1.0000 | no | no |
| 5 | 0.05 | 2 | -0.0848 | -1.62 | 0.1056 | 1.0000 | no | no |

## 3. By city, by margin (LONG side)


### Margin = 1°F

| series | city | station | city-days | fired | win rate | mean PnL | settled wrong way |
|---|---|---|---|---|---|---|---|
| KXHIGHMIA | Miami | KMIA | 65 | 11 | 0.727 | 0.3866 | 3 |
| KXHIGHTSFO | San Francisco | KSFO | 63 | 10 | 0.600 | 0.1167 | 4 |
| KXHIGHDEN | Denver | KDEN | 65 | 9 | 0.556 | 0.1027 | 4 |
| KXHIGHTBOS | Boston | KBOS | 67 | 7 | 0.857 | 0.3459 | 1 |
| KXHIGHTATL | Atlanta | KATL | 67 | 6 | 0.333 | 0.0518 | 4 |
| KXHIGHLAX | Los Angeles | KLAX | 62 | 5 | 0.600 | 0.2922 | 2 |
| KXHIGHTOKC | Oklahoma City | KOKC | 66 | 4 | 0.500 | 0.2289 | 2 |
| KXHIGHTSEA | Seattle | KSEA | 66 | 3 | 0.333 | 0.1120 | 2 |
| KXHIGHTDC | Washington DC | KDCA | 38 | 3 | 1.000 | 0.8385 | 0 |
| KXHIGHNY | New York (Central Park) | NYC | 66 | 3 | 1.000 | 0.1614 | 0 |
| KXHIGHPHIL | Philadelphia | KPHL | 65 | 3 | 0.333 | -0.0279 | 2 |
| KXHIGHAUS | Austin (Bergstrom) | KAUS | 64 | 2 | 1.000 | 0.1229 | 0 |
| KXHIGHTDAL | Dallas | KDFW | 65 | 2 | 0.500 | -0.0606 | 1 |
| KXHIGHTSATX | San Antonio | KSAT | 66 | 1 | 0.000 | -0.6952 | 1 |
| KXHIGHTHOU | Houston (Hobby) | KHOU | 64 | 1 | 0.000 | -0.1379 | 1 |
| KXHIGHTNOLA | New Orleans | KMSY | 67 | 1 | 1.000 | 0.8726 | 0 |

(4 of 20 cities never fired at this margin over the full window.)


### Margin = 2°F

| series | city | station | city-days | fired | win rate | mean PnL | settled wrong way |
|---|---|---|---|---|---|---|---|
| KXHIGHMIA | Miami | KMIA | 65 | 8 | 0.750 | 0.1136 | 2 |
| KXHIGHTSFO | San Francisco | KSFO | 63 | 5 | 1.000 | 0.2337 | 0 |
| KXHIGHDEN | Denver | KDEN | 65 | 4 | 1.000 | 0.1202 | 0 |
| KXHIGHTBOS | Boston | KBOS | 67 | 4 | 1.000 | 0.1234 | 0 |
| KXHIGHNY | New York (Central Park) | NYC | 66 | 3 | 1.000 | 0.1839 | 0 |
| KXHIGHLAX | Los Angeles | KLAX | 62 | 3 | 0.667 | 0.2134 | 1 |
| KXHIGHTATL | Atlanta | KATL | 67 | 2 | 1.000 | 0.0374 | 0 |
| KXHIGHTSEA | Seattle | KSEA | 66 | 1 | 1.000 | 0.6035 | 0 |
| KXHIGHTDC | Washington DC | KDCA | 38 | 1 | 1.000 | 0.4925 | 0 |
| KXHIGHTDAL | Dallas | KDFW | 65 | 1 | 1.000 | 0.3931 | 0 |
| KXHIGHTOKC | Oklahoma City | KOKC | 66 | 1 | 1.000 | 0.0000 | 0 |
| KXHIGHPHIL | Philadelphia | KPHL | 65 | 1 | 1.000 | 0.0654 | 0 |
| KXHIGHTNOLA | New Orleans | KMSY | 67 | 1 | 1.000 | 0.0000 | 0 |

(7 of 20 cities never fired at this margin over the full window.)


### Margin = 3°F

| series | city | station | city-days | fired | win rate | mean PnL | settled wrong way |
|---|---|---|---|---|---|---|---|
| KXHIGHMIA | Miami | KMIA | 65 | 6 | 0.667 | -0.0405 | 2 |
| KXHIGHDEN | Denver | KDEN | 65 | 2 | 1.000 | 0.0187 | 0 |
| KXHIGHTBOS | Boston | KBOS | 67 | 2 | 1.000 | 0.0000 | 0 |
| KXHIGHTSFO | San Francisco | KSFO | 63 | 2 | 1.000 | 0.0610 | 0 |
| KXHIGHTATL | Atlanta | KATL | 67 | 2 | 1.000 | 0.0374 | 0 |
| KXHIGHNY | New York (Central Park) | NYC | 66 | 2 | 1.000 | 0.0000 | 0 |
| KXHIGHLAX | Los Angeles | KLAX | 62 | 2 | 0.500 | -0.0795 | 1 |
| KXHIGHTDAL | Dallas | KDFW | 65 | 1 | 1.000 | 0.0373 | 0 |

(12 of 20 cities never fired at this margin over the full window.)


### Margin = 4°F

| series | city | station | city-days | fired | win rate | mean PnL | settled wrong way |
|---|---|---|---|---|---|---|---|
| KXHIGHDEN | Denver | KDEN | 65 | 2 | 1.000 | 0.0000 | 0 |
| KXHIGHMIA | Miami | KMIA | 65 | 1 | 0.000 | -0.0107 | 1 |
| KXHIGHTBOS | Boston | KBOS | 67 | 1 | 1.000 | 0.0000 | 0 |
| KXHIGHTATL | Atlanta | KATL | 67 | 1 | 1.000 | 0.0000 | 0 |
| KXHIGHNY | New York (Central Park) | NYC | 66 | 1 | 1.000 | 0.0000 | 0 |
| KXHIGHLAX | Los Angeles | KLAX | 62 | 1 | 0.000 | -0.1589 | 1 |

(14 of 20 cities never fired at this margin over the full window.)


### Margin = 5°F

| series | city | station | city-days | fired | win rate | mean PnL | settled wrong way |
|---|---|---|---|---|---|---|---|
| KXHIGHDEN | Denver | KDEN | 65 | 2 | 1.000 | 0.0000 | 0 |
| KXHIGHMIA | Miami | KMIA | 65 | 1 | 0.000 | -0.0107 | 1 |
| KXHIGHLAX | Los Angeles | KLAX | 62 | 1 | 0.000 | -0.1589 | 1 |

(17 of 20 cities never fired at this margin over the full window.)


## 3b. Capacity (fires/week x fillable size), by margin -- LONG side

| margin | fires/week (all 20 cities) | fillable rate | median fillable vol (5min) | mean entry price | rough weekly notional (USD) |
|---|---|---|---|---|---|
| 1 | 7.42 | 0.958 | 307.7 | 0.4003 | 875 |
| 2 | 3.66 | 0.943 | 470.9 | 0.7386 | 1199 |
| 3 | 1.99 | 0.842 | 179.7 | 0.8468 | 254 |
| 4 | 0.73 | 0.714 | 9.3 | 0.7371 | 4 |
| 5 | 0.42 | 0.750 | 21.7 | 0.5400 | 4 |

## 4. Best-margin selection and verdict

Selection rule (pre-specified): among margins [1, 2, 3, 4, 5] at gap-threshold=0, require (a) n_fired >= 8, (b) Bonferroni-significant at the corrected alpha above, and (c) worst-case (Wilson-95 upper-bound loss rate) analytic EV still positive. Survivors ranked by worst-case EV, not raw mean PnL.

| margin | n | win rate | mean PnL | t | p (Bonferroni) | cond. loss rate | worst-case loss rate | EV (point) | **EV (worst-case)** | fires/wk | passes all bars |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 71 | 0.620 | 0.2094 | 4.15 | 0.0005 | 0.380 | 0.497 | 0.2094 | **0.0931** | 7.42 | YES |
| 2 | 35 | 0.914 | 0.1678 | 4.60 | 0.0000 | 0.086 | 0.224 | 0.1678 | **0.0297** | 3.66 | YES |
| 3 | 19 | 0.842 | -0.0068 | -0.44 | 1.0000 | 0.158 | 0.376 | -0.0068 | **-0.2246** | 1.99 | no |
| 4 | 7 | 0.714 | -0.0242 | -1.16 | 1.0000 | 0.286 | 0.641 | -0.0242 | **-0.3796** | 0.73 | no |
| 5 | 4 | 0.500 | -0.0424 | -1.26 | 1.0000 | 0.500 | 0.850 | -0.0424 | **-0.3924** | 0.42 | no |

**Recommended margin: 1°F. Verdict: CONFIRMED.**

(Full narrative verdict is in the Executive Summary at the top of this document.)
