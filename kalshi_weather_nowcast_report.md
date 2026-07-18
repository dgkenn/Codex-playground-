# Kalshi KXHIGH Weather Settlement-Nowcast Backtest

Window: 2026-06-28 to 2026-07-18 (20 days), 6 KXHIGH city series.

City-days analyzed: **119** (skipped 1 for insufficient ASOS/candle data).


## 1. ASOS-observed vs official CLI settlement agreement (the key tail risk)

Comparing (full-LST-day ASOS max at the settlement station > strike) to the official Kalshi result: agreement = **118/119** (0.992). Disagreements: **1**.


Example disagreements (ASOS says one thing, official CLI settled the other):

| ticker | date | strike | ASOS full-day max | official result |
|---|---|---|---|---|
| KXHIGHDEN-26JUL08-T93 | 2026-07-08 | 93 | 92.0 | yes |


## 2. Decision-event backtest, by margin


### Margin = 1°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 2 / 119 city-days (fire rate 0.017)
- Mean execution price at t*: 0.9100 (median 0.9100)
- Realized win rate: 1.000
- **Locked-YES that settled the other way: 0** None
- Net PnL/contract: mean 0.0848, day-clustered SE 0.0600, **t = 1.41** (n=2, n_clusters=2)
- Worst trade: 0.0000 on 2026-07-05 (KXHIGHDEN-26JUL05-T94)
- Capacity proxy: mean volume at execution candle = 10.6 contracts/min (median 10.6); mean open interest = 7763.6
- **Fillable (>0 volume in the 5min after t*): 2/2 (1.000)**, mean exec price when fillable = 0.9100, day-clustered t (fillable-only) = 1.41 (mean 0.0848, n=2)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=1, mean PnL = 0.1697
  - gap > 0.02: n=1, mean PnL = 0.1697
  - gap > 0.05: n=1, mean PnL = 0.1697

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 114 / 119 city-days (fire rate 0.958)
- Mean execution price at t*: 0.9896 (median 1.0000)
- Realized win rate: 0.991
- **Locked-NO that settled the other way: 1** ['KXHIGHDEN-26JUL08-T93']
- Net PnL/contract: mean 0.0015, day-clustered SE 0.0107, **t = 0.14** (n=114, n_clusters=20)
- Worst trade: -0.8016 on 2026-07-08 (KXHIGHDEN-26JUL08-T93)
- Capacity proxy: mean volume at execution candle = 93.0 contracts/min (median 0.0); mean open interest = 3822.2
- **Fillable (>0 volume in the 5min after t*): 31/114 (0.272)**, mean exec price when fillable = 0.9629, day-clustered t (fillable-only) = 0.11 (mean 0.0043, n=31)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=5, mean PnL = 0.0338
  - gap > 0.02: n=3, mean PnL = 0.0502
  - gap > 0.05: n=2, mean PnL = 0.0566

### Margin = 2°F


**LONG (locked-YES: running max >= strike+margin, buy YES)**

- Decision events fired: 0 / 119 city-days (fire rate 0.000)
- Mean execution price at t*: n/a (median n/a)
- Realized win rate: n/a
- **Locked-YES that settled the other way: 0** None
- Net PnL/contract: mean n/a, day-clustered SE n/a, **t = n/a** (n=0, n_clusters=0)
- Capacity proxy: mean volume at execution candle = n/a contracts/min (median n/a); mean open interest = n/a
- **Fillable (>0 volume in the 5min after t*): 0/0 (n/a)**, mean exec price when fillable = n/a, day-clustered t (fillable-only) = n/a (mean n/a, n=0)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=0, mean PnL = n/a
  - gap > 0.02: n=0, mean PnL = n/a
  - gap > 0.05: n=0, mean PnL = n/a

**SHORT (locked-NO: LST hour>=15 & strike-max>=margin, buy NO)**

- Decision events fired: 111 / 119 city-days (fire rate 0.933)
- Mean execution price at t*: 0.9915 (median 1.0000)
- Realized win rate: 1.000
- **Locked-NO that settled the other way: 0** []
- Net PnL/contract: mean 0.0084, day-clustered SE 0.0080, **t = 1.05** (n=111, n_clusters=20)
- Worst trade: 0.0000 on 2026-07-12 (KXHIGHDEN-26JUL12-T99)
- Capacity proxy: mean volume at execution candle = 95.3 contracts/min (median 0.0); mean open interest = 3770.0
- **Fillable (>0 volume in the 5min after t*): 29/111 (0.261)**, mean exec price when fillable = 0.9676, day-clustered t (fillable-only) = 1.06 (mean 0.0322, n=29)
- Gap-threshold sensitivity (min required 1-price edge):
  - gap > 0.0: n=3, mean PnL = 0.3112
  - gap > 0.02: n=1, mean PnL = 0.9148
  - gap > 0.05: n=1, mean PnL = 0.9148

## 2b. SHORT side sensitivity to late-day cutoff hour (margin=1°F)

| cutoff (LST hr) | fired | fire rate | mean price | win rate | mean PnL | t (all) | fillable n | t (fillable) |
|---|---|---|---|---|---|---|---|---|
| 15:00 | 114 | 0.958 | 0.9896 | 0.991 | 0.0015 | 0.14 | 31 | 0.11 |
| 17:00 | 109 | 0.916 | 0.9909 | 0.991 | -0.0001 | -1.03 | 23 | n/a |
| 19:00 | 103 | 0.866 | 0.9904 | 0.990 | -0.0001 | -1.02 | 25 | n/a |
| 21:00 | 87 | 0.731 | 0.9886 | 0.989 | -0.0001 | -1.03 | 21 | n/a |

## 3. By city (margin=1, LONG side)

| series | city | station | city-days | fired | mean PnL |
|---|---|---|---|---|---|
| KXHIGHDEN | Denver | KDEN | 20 | 2 | 0.0848 |
| KXHIGHMIA | Miami | KMIA | 20 | 0 | n/a |
| KXHIGHCHI | Chicago (Midway) | KMDW | 20 | 0 | n/a |
| KXHIGHTBOS | Boston | KBOS | 19 | 0 | n/a |
| KXHIGHAUS | Austin (Bergstrom) | KAUS | 20 | 0 | n/a |
| KXHIGHTSEA | Seattle | KSEA | 20 | 0 | n/a |

## 4. Verdict

n_city_days = 119. ASOS-vs-CLI agreement = 0.992.

LONG margin=1: fired 2x, mean_ask=0.9100, win_rate=1.000, t=1.41, fillable=2/2 (t_fillable=1.41), locked_yes_settled_no=0.

SHORT margin=1: fired 114x, mean_price=0.9896, win_rate=0.991, t=0.14, fillable=31/114 (t_fillable=0.11), locked_no_settled_yes=1.
