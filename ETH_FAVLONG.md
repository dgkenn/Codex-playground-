# ETH 15-min Favorite-Longshot Bias Study

- Data: Kalshi ETH 15-min binaries. 2384 windows, 38128 position-fills.
- IS=first 60% (1430 win, 22965 fills), OOS=last 40% (954 win, 15163 fills).
- Each fill = a position bought at price `p` (= implied win-prob). `win = settle>0`. Verified settle=(1-p) if win else -p, 0% mismatch.
- Taker cost = spread/2 (fee=0). Favorite = high p.

## 1. Calibration curve (favorite-longshot test)

Realized win-rate vs implied prob (price), per 0.05 bucket, both sides combined. bias = realized - implied (>0 = underpriced/favorite-like, <0 = overpriced/longshot).

| price bucket | n | implied | realized WR | 95% CI | bias (pp) |
|---|---|---|---|---|---|
| 0.05-0.10 | 2782 | 0.075 | 0.062 | [0.054,0.072] | -1.3 |
| 0.10-0.15 | 2231 | 0.125 | 0.114 | [0.101,0.128] | -1.1 |
| 0.15-0.20 | 2078 | 0.175 | 0.178 | [0.162,0.195] | +0.3 |
| 0.20-0.25 | 1912 | 0.225 | 0.221 | [0.203,0.240] | -0.4 |
| 0.25-0.30 | 2059 | 0.275 | 0.257 | [0.239,0.277] | -1.8 |
| 0.30-0.35 | 1932 | 0.325 | 0.325 | [0.305,0.346] | +0.0 |
| 0.35-0.40 | 1931 | 0.375 | 0.362 | [0.341,0.384] | -1.3 |
| 0.40-0.45 | 1812 | 0.425 | 0.412 | [0.389,0.435] | -1.3 |
| 0.45-0.50 | 1746 | 0.475 | 0.457 | [0.434,0.480] | -1.8 |
| 0.50-0.55 | 1780 | 0.525 | 0.497 | [0.474,0.520] | -2.8 |
| 0.55-0.60 | 1740 | 0.575 | 0.558 | [0.535,0.581] | -1.7 |
| 0.60-0.65 | 1794 | 0.625 | 0.596 | [0.574,0.619] | -2.9 |
| 0.65-0.70 | 1859 | 0.675 | 0.657 | [0.635,0.678] | -1.8 |
| 0.70-0.75 | 1871 | 0.725 | 0.700 | [0.679,0.720] | -2.5 |
| 0.75-0.80 | 1735 | 0.775 | 0.748 | [0.727,0.767] | -2.7 |
| 0.80-0.85 | 1794 | 0.825 | 0.807 | [0.788,0.825] | -1.8 |
| 0.85-0.90 | 1857 | 0.875 | 0.871 | [0.855,0.886] | -0.4 |
| 0.90-0.95 | 2347 | 0.925 | 0.931 | [0.920,0.940] | +0.6 |

- **FAVORITES p>=0.70**: n=10615, mean implied=0.839, realized WR=0.832 [0.825,0.839], bias=-0.7pp
- **LONGSHOTS p<=0.30**: n=13315, mean implied=0.149, realized WR=0.144 [0.139,0.150], bias=-0.4pp

### IS/OOS stability of the favorite bias

| split | slice | n | mean implied | realized WR | bias (pp) |
|---|---|---|---|---|---|
| IS | p>=0.70 | 6126 | 0.836 | 0.823 | -1.3 |
| IS | p>=0.80 | 3973 | 0.886 | 0.883 | -0.3 |
| IS | p<=0.30 | 7942 | 0.150 | 0.152 | +0.2 |
| OOS | p>=0.70 | 4489 | 0.842 | 0.844 | +0.1 |
| OOS | p>=0.80 | 3036 | 0.889 | 0.894 | +0.5 |
| OOS | p<=0.30 | 5373 | 0.146 | 0.133 | -1.3 |

## 2. Taker strategy: buy favorites crossing the spread

Buy every position with p>=thr as a taker (pay p+spread/2). EV/trade in cents/contract.

| thr | split | n | hit-rate | EV/trade (c) | Sharpe | t-stat |
|---|---|---|---|---|---|---|
| 0.55 | ALL | 16008 | 0.755 | -2.02 | -0.049 | -6.25 |
| 0.55 | IS | 9471 | 0.743 | -2.77 | -0.067 | -6.48 |
| 0.55 | OOS | 6537 | 0.773 | -0.93 | -0.023 | -1.90 |
| 0.60 | ALL | 14268 | 0.779 | -1.97 | -0.050 | -5.94 |
| 0.60 | IS | 8376 | 0.767 | -2.79 | -0.069 | -6.31 |
| 0.60 | OOS | 5892 | 0.797 | -0.82 | -0.021 | -1.62 |
| 0.65 | ALL | 12474 | 0.806 | -1.75 | -0.046 | -5.12 |
| 0.65 | IS | 7252 | 0.796 | -2.42 | -0.062 | -5.32 |
| 0.65 | OOS | 5222 | 0.819 | -0.81 | -0.022 | -1.58 |
| 0.70 | ALL | 10615 | 0.832 | -1.62 | -0.045 | -4.61 |
| 0.70 | IS | 6126 | 0.823 | -2.29 | -0.062 | -4.85 |
| 0.70 | OOS | 4489 | 0.844 | -0.71 | -0.020 | -1.35 |
| 0.75 | ALL | 8744 | 0.860 | -1.31 | -0.039 | -3.61 |
| 0.75 | IS | 4996 | 0.851 | -2.12 | -0.061 | -4.32 |
| 0.75 | OOS | 3748 | 0.872 | -0.23 | -0.007 | -0.43 |
| 0.80 | ALL | 7009 | 0.888 | -0.78 | -0.025 | -2.11 |
| 0.80 | IS | 3973 | 0.883 | -1.17 | -0.037 | -2.35 |
| 0.80 | OOS | 3036 | 0.894 | -0.27 | -0.009 | -0.48 |
| 0.85 | ALL | 5215 | 0.916 | -0.25 | -0.009 | -0.66 |
| 0.85 | IS | 2940 | 0.914 | -0.39 | -0.014 | -0.77 |
| 0.85 | OOS | 2275 | 0.918 | -0.07 | -0.002 | -0.12 |
| 0.90 | ALL | 3358 | 0.940 | +0.06 | +0.003 | +0.16 |
| 0.90 | IS | 1882 | 0.942 | +0.28 | +0.012 | +0.53 |
| 0.90 | OOS | 1476 | 0.938 | -0.21 | -0.009 | -0.34 |

Same sweep with NO spread cost (idealized maker fill, theta only):

| thr | split | n | EV/trade (c) | Sharpe | t-stat |
|---|---|---|---|---|---|
| 0.55 | ALL | 16008 | -0.99 | -0.024 | -3.07 |
| 0.55 | OOS | 6537 | +0.01 | +0.000 | +0.01 |
| 0.60 | ALL | 14268 | -0.97 | -0.024 | -2.91 |
| 0.60 | OOS | 5892 | +0.10 | +0.003 | +0.20 |
| 0.65 | ALL | 12474 | -0.77 | -0.020 | -2.26 |
| 0.65 | OOS | 5222 | +0.08 | +0.002 | +0.15 |
| 0.70 | ALL | 10615 | -0.68 | -0.019 | -1.94 |
| 0.70 | OOS | 4489 | +0.15 | +0.004 | +0.28 |
| 0.75 | ALL | 8744 | -0.41 | -0.012 | -1.13 |
| 0.75 | OOS | 3748 | +0.59 | +0.018 | +1.10 |
| 0.80 | ALL | 7009 | +0.06 | +0.002 | +0.15 |
| 0.80 | OOS | 3036 | +0.49 | +0.016 | +0.89 |
| 0.85 | ALL | 5215 | +0.50 | +0.018 | +1.30 |
| 0.85 | OOS | 2275 | +0.61 | +0.022 | +1.06 |
| 0.90 | ALL | 3358 | +0.69 | +0.029 | +1.69 |
| 0.90 | OOS | 1476 | +0.33 | +0.014 | +0.53 |

### Selling longshots
On a binary, selling a longshot at price q (q<=0.30) == buying the opposing favorite at 1-q (>=0.70). The dataset already contains both faces of every window, so the favorite-buy sweep above subsumes the sell-longshot trade. No separate edge exists beyond what the favorite buckets show.

## 3. One-sided favorite maker vs taker

A resting bid on the favored side fills at the bid (no spread crossed) but only when the tape trades through it. We approximate the maker as the SAME favorite positions at ZERO spread cost (best case) and at HALF the taker cost (a mid-ish fill). Maker realism: fills are adversely-selected (you fill more when about to lose), so true maker EV sits between the zero-cost and taker rows. We bracket it.

| thr | mode | split | n | EV/trade (c) | Sharpe | t-stat |
|---|---|---|---|---|---|---|
| 0.70 | taker(full spr) | OOS | 4489 | -0.71 | -0.020 | -1.35 |
| 0.70 | maker(half spr) | OOS | 4489 | -0.28 | -0.008 | -0.54 |
| 0.70 | maker(zero spr) | OOS | 4489 | +0.15 | +0.004 | +0.28 |
| 0.75 | taker(full spr) | OOS | 3748 | -0.23 | -0.007 | -0.43 |
| 0.75 | maker(half spr) | OOS | 3748 | +0.18 | +0.005 | +0.33 |
| 0.75 | maker(zero spr) | OOS | 3748 | +0.59 | +0.018 | +1.10 |
| 0.80 | taker(full spr) | OOS | 3036 | -0.27 | -0.009 | -0.48 |
| 0.80 | maker(half spr) | OOS | 3036 | +0.11 | +0.004 | +0.20 |
| 0.80 | maker(zero spr) | OOS | 3036 | +0.49 | +0.016 | +0.89 |

## 4. Time/regime refinement (favorites p>=0.70, taker)

### By k-slot (minute within window)

| k-slot | split | n | hit-rate | EV/trade (c) | Sharpe | t-stat |
|---|---|---|---|---|---|---|
| k 2-5 | ALL | 3641 | 0.809 | -0.77 | -0.020 | -1.20 |
| k 2-5 | OOS | 1576 | 0.819 | +0.00 | +0.000 | +0.00 |
| k 6-9 | ALL | 4580 | 0.846 | -1.20 | -0.034 | -2.33 |
| k 6-9 | OOS | 1932 | 0.861 | -0.18 | -0.005 | -0.24 |
| k 10-12 | ALL | 2394 | 0.840 | -3.73 | -0.105 | -5.15 |
| k 10-12 | OOS | 981 | 0.849 | -2.90 | -0.083 | -2.60 |
| k 9-12 | ALL | 3441 | 0.844 | -3.08 | -0.088 | -5.15 |
| k 9-12 | OOS | 1411 | 0.852 | -2.36 | -0.068 | -2.57 |
| k 2-12 | ALL | 10615 | 0.832 | -1.62 | -0.045 | -4.61 |
| k 2-12 | OOS | 4489 | 0.844 | -0.71 | -0.020 | -1.35 |

### Late-slot (k>=9) calibration of favorites

| split | slice | n | mean implied | realized WR | bias (pp) |
|---|---|---|---|---|---|
| ALL | p>=0.70 & k>=9 | 3441 | 0.864 | 0.844 | -2.0 |
| IS | p>=0.70 & k>=9 | 2030 | 0.863 | 0.838 | -2.5 |
| OOS | p>=0.70 & k>=9 | 1411 | 0.866 | 0.852 | -1.4 |

## 5. Cost realism

Spread distribution for favorite (p>=0.70) positions:

- spread p25 = 1.0c
- spread p50 = 1.8c
- spread p75 = 2.9c
- spread p90 = 3.3c
- mean spread = 1.88c ; half-spread (taker cost) = 0.94c

- Gross favorite underpricing edge = -0.68c/contract (realized 0.832 - implied 0.839).
- Taker half-spread cost = 0.94c/contract.
- Net after taker cost = -1.62c/contract.

- p>=0.70 taker ALL: 10615 trades, 1.20 trades/win, EV=-1.62c, t=-4.61
- p>=0.70 taker OOS: 4489 trades, EV=-0.71c, t=-1.35

## VERDICT

**NO positive-EV favorite-longshot strategy exists on Kalshi ETH 15-min. Do NOT deploy.**

1. **No favorite-longshot bias.** The calibration curve shows realized win-rate sits AT or
   slightly BELOW the implied price in nearly every bucket (favorites p>=0.70: bias **-0.7pp**;
   longshots p<=0.30: bias **-0.4pp**). The classic favorite-longshot pattern requires favorites
   UNDER-priced (realized > implied, positive bias) and longshots over-priced. ETH 15-min shows
   the opposite/flat: a small *uniform* negative bias on the transacted side. This is the
   signature of tape adverse-selection (you trade at marginally bad prices), not a favorite edge.

2. **Taker loses at every threshold.** Buy-favorite-as-taker EV/trade is negative for thr 0.55-0.85
   (ALL: -2.0c to -0.25c, t = -6.3 to -0.7) and only crosses ~0 at thr 0.90 (EV +0.06c, t=+0.16,
   not significant). The gross favorite "edge" (-0.7pp = -0.68c) is itself negative and the
   ~0.94c taker half-spread sinks it further: net -1.62c/contract at p>=0.70, t=-4.61.

3. **One-sided maker is the only thing near break-even, and only at zero modeled cost.** At a
   perfect mid/maker fill (zero spread crossed) the favorite buckets are ~flat OOS (thr 0.75 OOS:
   +0.59c, Sharpe +0.018, t=+1.10 — not significant). At a realistic half-spread maker fill it is
   ~0. Real maker fills on a thin, adversely-selected book sit at or below this, so the maker does
   not produce a robust positive edge either. The apparent OOS positivity is a sub-1-sigma artifact
   and IS is clearly negative (no IS/OOS stability).

4. **No regime rescues it.** Late slots (k>=9), the previously "clean" ETH slice, are the WORST for
   this trade (k 10-12 taker EV -3.7c, t=-5.2) because favorites that survive to late minutes are
   priced tighter and the residual bias stays negative (-2.0pp). No k-slot, threshold, or split
   gives a positive, significant edge.

5. **Cost wall.** Favorite spreads are wide (mean 1.88c, p90 3.3c) so the taker half-spread alone
   (0.94c) exceeds any plausible bias. The favorite bias would need to be **>+0.94pp positive** to
   clear the spread; it is measured at **-0.7pp negative**. The edge is not merely too small — it
   has the wrong sign.

**Exact rule:** none qualifies. Best honest candidate (zero-cost maker, p>=0.75) is OOS +0.59c /
Sharpe +0.018 / t=+1.10 / ~1.15 trades-per-win, but IS-negative and statistically indistinguishable
from zero, so it fails IS/OOS stability and the t-test vs zero. Backtest SCREENS only; this one
screens NEGATIVE — no forward validation warranted.

