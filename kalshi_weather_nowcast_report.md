# Kalshi KXHIGH Weather Settlement-Nowcast Backtest

Window: 2026-07-03 to 2026-07-18 (15 days), 3 KXHIGH city series.

City-days analyzed: **41** (skipped 4 for insufficient ASOS/candle data).

ASOS data resolution: using IEM's true **one-minute ASOS product** (`asos1min.py`), median obs gap across 3 stations = 1.0 min (min 1.0, max 1.0). The plain hourly-cadence ASOS archive endpoint was tested first and rejected: it visibly missed a real ~2F spike at KDEN on 2026-07-08 that occurred between two hourly readings and flipped a market's settlement (see below).


## 1. ASOS-observed vs official CLI settlement agreement (the key tail risk)

Comparing (full-LST-day ASOS max at the settlement station > strike) to the official Kalshi result: agreement = **40/41** (0.976). Disagreements: **1**.


Example disagreements (ASOS says one thing, official CLI settled the other):

| ticker | date | strike | ASOS full-day max | official result |
|---|---|---|---|---|
| KXHIGHDEN-26JUL09-T91 | 2026-07-09 | 91 | 92.0 | no |


## 2. Decision-event backtest, by margin


### Margin = 1°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 4 / 41 city-days (fire rate 0.098)
- Mean execution price at t*: 0.4850 (median 0.4850)
- Realized win rate: 0.750
- **Locked-YES that settled the other way: 1** ['KXHIGHDEN-26JUL09-T91']
- Net PnL/contract: mean 0.2499, day-clustered SE 0.1608, **t = 1.55** (n=4, n_clusters=4)
- Worst trade: -0.2631 on 2026-07-09 (KXHIGHDEN-26JUL09-T91)
- Capacity proxy: mean volume at execution candle = 107.0 contracts/min (median 53.8); mean open interest = 6466.4
- **Fillable (>0 volume in the 5min after t*): 4/4 (1.000)**, mean exec price when fillable = 0.4850, day-clustered t (fillable-only) = 1.55 (mean 0.2499, n=4)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=4, mean PnL = 0.2499
  - gap > 0.02: n=4, mean PnL = 0.2499
  - gap > 0.05: n=4, mean PnL = 0.2499

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 33 / 41 city-days (fire rate 0.805)
- Mean execution price at t*: 0.9994 (median 1.0000)
- Realized win rate: 1.000
- **Locked-NO that settled the other way: 0** []
- Net PnL/contract: mean 0.0006, day-clustered SE 0.0005, **t = 1.06** (n=33, n_clusters=14)
- Worst trade: 0.0000 on 2026-07-13 (KXHIGHDEN-26JUL13-T100)
- Capacity proxy: mean volume at execution candle = 7.0 contracts/min (median 0.0); mean open interest = 3408.2
- **Fillable (>0 volume in the 5min after t*): 9/33 (0.273)**, mean exec price when fillable = 0.9978, day-clustered t (fillable-only) = 1.18 (mean 0.0021, n=9)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=1, mean PnL = 0.0186
  - gap > 0.02: n=1, mean PnL = 0.0186
  - gap > 0.05: n=0, mean PnL = n/a

### Margin = 2°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 2 / 41 city-days (fire rate 0.049)
- Mean execution price at t*: 0.8050 (median 0.8050)
- Realized win rate: 1.000
- **Locked-YES that settled the other way: 0** None
- Net PnL/contract: mean 0.1841, day-clustered SE 0.0237, **t = 7.77** (n=2, n_clusters=2)
- Worst trade: 0.1506 on 2026-07-05 (KXHIGHDEN-26JUL05-T94)
- Capacity proxy: mean volume at execution candle = 38.5 contracts/min (median 38.5); mean open interest = 6165.4
- **Fillable (>0 volume in the 5min after t*): 2/2 (1.000)**, mean exec price when fillable = 0.8050, day-clustered t (fillable-only) = 7.77 (mean 0.1841, n=2)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=2, mean PnL = 0.1841
  - gap > 0.02: n=2, mean PnL = 0.1841
  - gap > 0.05: n=2, mean PnL = 0.1841

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 31 / 41 city-days (fire rate 0.756)
- Mean execution price at t*: 1.0000 (median 1.0000)
- Realized win rate: 1.000
- **Locked-NO that settled the other way: 0** []
- Net PnL/contract: mean 0.0000, day-clustered SE 0.0000, **t = n/a** (n=31, n_clusters=14)
- Worst trade: 0.0000 on 2026-07-13 (KXHIGHDEN-26JUL13-T100)
- Capacity proxy: mean volume at execution candle = 7.4 contracts/min (median 0.0); mean open interest = 3142.1
- **Fillable (>0 volume in the 5min after t*): 8/31 (0.258)**, mean exec price when fillable = 1.0000, day-clustered t (fillable-only) = n/a (mean 0.0000, n=8)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=0, mean PnL = n/a
  - gap > 0.02: n=0, mean PnL = n/a
  - gap > 0.05: n=0, mean PnL = n/a

## 2b. SHORT side sensitivity to late-day cutoff hour (margin=1°F)

| cutoff (LST hr) | fired | fire rate | mean price | win rate | mean PnL | t (all) | fillable n | t (fillable) |
|---|---|---|---|---|---|---|---|---|
| 15:00 | 33 | 0.805 | 0.9994 | 1.000 | 0.0006 | 1.06 | 9 | 1.18 |
| 17:00 | 32 | 0.780 | 1.0000 | 1.000 | 0.0000 | n/a | 5 | n/a |
| 19:00 | 31 | 0.756 | 1.0000 | 1.000 | 0.0000 | n/a | 6 | n/a |
| 21:00 | 29 | 0.707 | 1.0000 | 1.000 | 0.0000 | n/a | 6 | n/a |

## 3. By city (margin=1, LONG side)

| series | city | station | city-days | fired | mean PnL |
|---|---|---|---|---|---|
| KXHIGHDEN | Denver | KDEN | 14 | 4 | 0.2499 |
| KXHIGHCHI | Chicago (Midway) | KMDW | 14 | 0 | n/a |
| KXHIGHTPHX | Phoenix | KPHX | 13 | 0 | n/a |

## 4. Verdict

n_city_days = 41. ASOS-vs-CLI agreement = 0.976.

LONG margin=1: fired 4x, mean_ask=0.4850, win_rate=0.750, t=1.55, fillable=4/4 (t_fillable=1.55), locked_yes_settled_no=1.

SHORT margin=1: fired 33x, mean_price=0.9994, win_rate=1.000, t=1.06, fillable=9/33 (t_fillable=1.18), locked_no_settled_yes=0.
