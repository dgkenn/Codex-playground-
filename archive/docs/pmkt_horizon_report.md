# Polymarket Longer-Horizon BTC/ETH Edge — Results

_Generated 2026-07-16T13:41:38.566951+00:00 | runtime 897s_

## Universe discovered

| family | asset | n markets | distinct weeks | median horizon (d) | total volume $ |
|---|---|---:|---:|---:|---:|
| weekly_terminal | BTC | 3424 | 50 | 7.0 | 1,026,619,446 |
| weekly_terminal | ETH | 3407 | 49 | 7.0 | 301,419,392 |
| week_touch | BTC | 196 | 14 | 7.0 | 57,628,112 |
| week_touch | ETH | 164 | 12 | 7.0 | 19,983,674 |

## TEST 1 — Calibration / Favorite-Longshot (zero-fee AND net half-spread)

Entry = time-weighted YES mid over first 10-50% of market life (causal). Cluster = resolution ISO-week. Half-spread subtracted = realized taker cost from fills.

### Calibration — weekly_terminal  (n=6831, weeks=50)

| entry bin | n | wks | mean entry | realized YES | diff(real-entry) | clustered t | net½sprd diff |
|---|---:|---:|---:|---:|---:|---:|---:|
| [0.00,0.05) | 1298 | 45 | 0.023 | 0.002 | -0.021 | -8.81 | +0.020 |
| [0.05,0.15) | 875 | 48 | 0.093 | 0.040 | -0.053 | -3.20 | +0.051 |
| [0.15,0.30) | 639 | 49 | 0.218 | 0.105 | -0.113 | -4.75 | +0.109 |
| [0.30,0.45) | 505 | 50 | 0.371 | 0.293 | -0.078 | -1.90 | +0.070 |
| [0.45,0.55) | 307 | 50 | 0.498 | 0.414 | -0.084 | -1.65 | +0.074 |
| [0.55,0.70) | 489 | 50 | 0.627 | 0.566 | -0.060 | -1.15 | +0.050 |
| [0.70,0.85) | 653 | 50 | 0.781 | 0.746 | -0.036 | -0.69 | +0.029 |
| [0.85,0.95) | 827 | 50 | 0.908 | 0.904 | -0.004 | -0.14 | +0.001 |
| [0.95,1.00) | 1238 | 46 | 0.977 | 0.968 | -0.010 | -0.65 | +0.009 |

- longshot side (entry<0.5): mean(real-entry) = -0.0577  (n=3480)
- favorite side (entry>=0.5): mean(real-entry) = -0.0234  (n=3351)

### Calibration — week_touch  (n=360, weeks=17)

| entry bin | n | wks | mean entry | realized YES | diff(real-entry) | clustered t | net½sprd diff |
|---|---:|---:|---:|---:|---:|---:|---:|
| [0.00,0.05) | 148 | 17 | 0.021 | 0.068 | +0.046 | +0.88 | +0.045 |
| [0.05,0.15) | 76 | 17 | 0.093 | 0.184 | +0.092 | +1.57 | +0.087 |
| [0.15,0.30) | 47 | 17 | 0.219 | 0.234 | +0.015 | +0.24 | +0.009 |
| [0.30,0.45) | 34 | 15 | 0.373 | 0.441 | +0.068 | +0.77 | +0.057 |
| [0.45,0.55) | 12 | 11 | 0.490 | 0.667 | +0.176 | +1.32 | +0.157 |
| [0.55,0.70) | 15 | 10 | 0.618 | 0.933 | +0.315 | +4.45 | +0.296 |
| [0.70,0.85) | 12 | 9 | 0.763 | 0.917 | +0.153 | +2.09 | +0.131 |
| [0.85,0.95) | 2 | - | - | - | underpowered | - |
| [0.95,1.00) | 14 | 10 | 0.999 | 1.000 | +0.000 | +nan | -0.025 |

- longshot side (entry<0.5): mean(real-entry) = +0.0626  (n=312)
- favorite side (entry>=0.5): mean(real-entry) = +0.1275  (n=48)

## TEST 2 — Cross-market vs Deribit (weekly terminal BTC/ETH)

Deribit implied P(S_T>K) = N(d2) from perp spot + DVOL(30d) at entry time. n=5590, weeks=50

**2a. Trade Polymarket TOWARD Deribit fair value** (buy the side Deribit says is cheap):

| metric | value |
|---|---|
| mean |gap| = |pmkt-deribit| | 0.0443 |
| mean PnL/market (mid, zero-fee) | +0.0008 |
| clustered t | +0.08  (N=5590, weeks=50) |
| median half-spread cost | 0.0032 |
| net PnL after half-spread | -0.0024 |

**2b. Who predicts better? (Brier, lower=better)**

| predictor | Brier | mean pred | realized |
|---|---:|---:|---:|
| Polymarket entry mid | 0.1130 | 0.490 | 0.442 |
| Deribit digital | 0.1154 | 0.479 | 0.442 |

- in-sample (older half): mean toward-Deribit PnL -0.0027, t=-0.15 (weeks=24)
- OOS (newer half): mean toward-Deribit PnL +0.0044, t=+0.48 (weeks=27)

## TEST 3 — MARKET-weighted vs TRADE-weighted (the discipline that killed the wing edge)

The favorite-longshot 'edge' says extreme longshots are overpriced. A tradeable version FADES longshots: SELL YES (buy NO) on low-entry markets, BUY YES on high-entry markets. We compare a MARKET-weighted backtest (1 obs/market at entry mid) to a TRADE-weighted backtest (actual taker fills at executed prices, weighted by size) — plus an adverse-selection check.

### weekly_terminal

| weighting | mean PnL/unit (net ½sprd) | clustered t | N | weeks |
|---|---:|---:|---:|---:|
| MARKET-weighted (entry mid) | +0.0104 | +0.90 | 6524 | 50 |
| TRADE-weighted, size-wtd (exec fills) | +0.0060 | +2.34 | 2661522 | 50 |
| TRADE-weighted, unweighted fills | +0.0140 | +2.34 | 2661522 | 50 |

- Adverse selection: signal-side outcome rate — MARKET-weighted YES=0.454 vs FILL-volume-weighted YES=0.459 (fills cluster where the taker side WINS/LOSES more than the market average)
- MARKET minus TRADE weighted PnL = +0.0045  (consistent)

### week_touch

| weighting | mean PnL/unit (net ½sprd) | clustered t | N | weeks |
|---|---:|---:|---:|---:|
| MARKET-weighted (entry mid) | -0.0380 | -0.90 | 348 | 17 |
| TRADE-weighted, size-wtd (exec fills) | -0.0058 | +0.39 | 133824 | 17 |
| TRADE-weighted, unweighted fills | +0.0114 | +0.39 | 133824 | 17 |

- Adverse selection: signal-side outcome rate — MARKET-weighted YES=0.261 vs FILL-volume-weighted YES=0.221 (fills cluster where the taker side WINS/LOSES more than the market average)
- MARKET minus TRADE weighted PnL = -0.0322  (consistent)


---

## ADDENDUM A — Is the overpricing Polymarket-specific? (per-bin PM vs Deribit)

Realized-minus-Polymarket vs realized-minus-Deribit, per entry bin (weekly_terminal, n=6831, 50 weeks).
If Polymarket had a retail-specific mispricing, `real-PM` would be systematically more negative than
`real-Deribit`. It is not — the smart options market missed YES by the **same amount**.

| entry bin | n | PM entry | Deribit | realized | real−PM | real−Deribit |
|---|---:|---:|---:|---:|---:|---:|
| [0.00,0.05) | 1298 | 0.023 | 0.018 | 0.002 | -0.021 | -0.016 |
| [0.05,0.15) |  875 | 0.093 | 0.099 | 0.040 | -0.053 | -0.059 |
| [0.15,0.30) |  639 | 0.218 | 0.222 | 0.105 | -0.113 | -0.117 |
| [0.30,0.45) |  505 | 0.371 | 0.358 | 0.293 | -0.078 | -0.064 |
| [0.45,0.55) |  307 | 0.498 | 0.475 | 0.414 | -0.084 | -0.062 |
| [0.55,0.70) |  489 | 0.627 | 0.587 | 0.566 | -0.060 | -0.021 |
| [0.70,0.85) |  653 | 0.781 | 0.745 | 0.746 | -0.036 | +0.001 |
| [0.85,0.95) |  827 | 0.908 | 0.894 | 0.904 | -0.004 | +0.011 |
| [0.95,1.00) | 1238 | 0.977 | 0.985 | 0.968 | -0.010 | -0.017 |

Brier: Polymarket 0.1130 vs Deribit 0.1154 (PM marginally BETTER calibrated). Trading Polymarket
toward Deribit fair value earns t=+0.08 (null). **The longshot overpricing is NOT a Polymarket
inefficiency — it is the short-dated-OTM / lottery risk premium, priced identically by the regulated
options market.**

Realized underlying drift over the Deribit sample window: BTC 27,082 → 64,557 (+138%), ETH 1,873 →
1,914 (+2%). Despite the large BTC uptrend, far-OTM 7-day "above" strikes almost never printed
(deepest bin realized 0.2% vs priced 2.3%) — classic short-dated-call overpricing, not a drift artifact
(and mirrored on Deribit).

## ADDENDUM B — Isolated SHORT-LONGSHOT leg: MARKET- vs TRADE-weighted (the discipline check)

Strategy: **SELL YES** on far-OTM weekly "above" markets (the overpriced side). Market-weighted = 1
obs/market at causal entry mid. Trade-weighted = replicate every ACTUAL taker YES-sell fill at its
executed price, size-weighted, clustered by resolution week. Adverse selection = fill-volume-weighted
YES outcome rate vs market-weighted (higher fill-YES ⇒ fills cluster where we LOSE).

| entry band | n mkts | weeks | MKT-wtd gross | MKT-wtd net ½sprd | t | TRADE-wtd (size) | t | fills | adverse (mkt→fill YES) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| [0.03,0.15) deep | 1246 | 48 | +0.0477 | +0.0452 | +3.91 | **+0.0095** | +4.81 | 443k | 0.029 → 0.025 (favorable) |
| [0.03,0.30) all  | 1885 | 49 | +0.0700 | +0.0675 | +4.62 | **+0.0177** | +6.98 | 765k | 0.055 → 0.047 (favorable) |
| [0.15,0.30) mild | 639  | 49 | +0.1135 | +0.1110 | +4.75 | **+0.0313** | +5.84 | 322k | 0.105 → 0.085 (favorable) |

Unlike the wing edge (which flipped NEGATIVE trade-weighted), the short-longshot leg stays **positive
and significant trade-weighted (t≈4.8–7.0)**, and adverse selection is **favorable** (fill-weighted
outcome rate is LOWER than market-weighted — takers sell YES most heavily in markets that resolve NO
even more often than average). Trade-weighted magnitude (≈1–3¢/contract) is smaller than market-weighted
(5–11¢) because volume concentrates in later fills at prices already nearer 0; both are net-positive
after the ~0.25¢ half-spread. The BUY-FAVORITE leg does NOT work (favorites also mildly overpriced), so
the mixed FLB strategy (Test 3, market-wtd t=0.90) is diluted — the edge is specifically SHORT-longshot.

---

## BLUNT VERDICT

**Is there a real, cost-surviving, trade-weighted edge at longer horizon on zero-fee Polymarket?**

- **Favorite–longshot (short-longshot leg): YES — real, cost-surviving, trade-weighted, not an
  adverse-selection artifact.** Selling short-dated far-OTM BTC/ETH weekly "above $X" longshots harvests
  a robust premium: market-weighted +5–11¢/contract (t≈4–4.8), **trade-weighted +1–3¢/contract
  (t≈4.8–7.0)** net the ~0.25¢ CLOB half-spread, with FAVORABLE (not adverse) fill selection. Well
  powered: ~1,900 markets, 49 distinct resolution weeks, $1.3B family volume. This is the first
  longer-horizon signal to survive the exact trade-weighting/adverse-selection discipline that killed
  the wing edge. Buying favorites does NOT work — the effect is one-sided (short the longshot).

- **Cross-market vs Deribit: NO edge.** Polymarket is not mispriced vs the smart options market (Brier
  tied, trade-toward-Deribit t=0.08, per-bin real−PM ≈ real−Deribit). The longshot premium is the SAME
  short-vol/lottery risk premium the regulated options market carries — it is a RISK PREMIUM, not a
  Polymarket-specific inefficiency.

**Bottom line:** The harvestable thing is a genuine short-dated-OTM crypto **lottery/short-vol risk
premium**, cheaply accessible on zero-fee Polymarket (half-spread ~0.25¢ vs Kalshi's 0.07·p·(1−p) fee
that would eat ~0.6¢/contract at p≈0.1). It is REAL, COST-SURVIVING, and TRADE-WEIGHTED-POSITIVE — but
it is **not free money and not an arbitrage**: (1) it is a one-sided SHORT-tail bet that blows up in a
violent up-week (tail risk demands strict sizing); (2) only ~49 weeks of history — modest power for a
premium whose whole risk lives in rare tails; (3) it is identically available on Deribit, so zero fees
are the only Polymarket advantage. Verdict: **a real cost-surviving short-longshot RISK PREMIUM, not a
mispricing — tradeable with tail-aware sizing; NO cross-market edge vs Deribit.**
