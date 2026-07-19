# Audit: kalshi-longshot-paper and tailbias-paper

## Executive Summary

Both sleeves show **ILLUSION**: positive self-metrics (93-95% win rates) but **flat/noise realized P&L with sub-threshold day-clustered t-statistics**. Neither achieves the t ≥ 2.0 out-of-sample threshold on realized money.

---

## LONGSHOT SLEEVE

### Data
- **Settled bets**: 15 positions  
- **Settlement window**: 2026-07-12 to 2026-07-14 (3 settlement days)
- **Entry strategy**: Sell YES (maker side) on overpriced longshots at 7-15c tail prices
- **Fee model**: No explicit taker/maker split (paper, but workflow doc claims ~0.97c/contract net of adverse selection + fee)

### Realized P&L

| Metric | Value |
|--------|-------|
| **Total P&L** | +$0.6600 |
| **Mean P&L/contract** | +$0.0440 |
| **Median P&L/contract** | +$0.1000 |
| **Std Dev** | $0.2719 |
| **Win rate** | 93.3% (14 wins, 1 loss of -$0.93) |

### Day-Clustered Analysis
Daily P&L by settlement date:
- **2026-07-12**: +$0.34 (2 bets settled)
- **2026-07-13**: −$0.28 (5 bets settled)  
- **2026-07-14**: +$0.60 (8 bets settled)

**Day-clustered t-test** (H₀: mean daily P&L = 0):
- t-statistic: **0.8428** (target ≥ 2.0)
- p-value: 0.488
- **Does NOT achieve t ≥ 2.0** ✗

### Risk Factor
The single loss is a −$0.93 outcome (KXTECHRANKLISTAICODE, YES settled against the short). The 14 wins cluster tightly around +$0.09–$0.20. The distribution is not consistent with a reliable edge—high win rate is an artifact of rare but severe drawdowns compressed into a 3-day window.

### Verdict
**ILLUSION**  
Realized P&L is essentially noise (~$0.66 / 15 bets = $0.044/contract) with insufficient statistical power (t = 0.84, well below the 2.0 threshold). The high win rate is misleading; a single −$0.93 loss erodes confidence. No evidence of an out-of-sample edge on realized money.

---

## TAILBIAS SLEEVE

### Data
- **Settled bets**: 19 positions  
- **Settlement window**: 2026-07-12T21:30 to 2026-07-14T22:15 (3 settlement days)
- **Entry strategy**: Buy favorite (YES) or sell tail (NO) on KXBTC15M/KXETH15M/KXXRP15M in the [8,10]min-to-close window
- **Fee model**: Two variants recorded—**taker** (conservative, includes 1c taker fee per side) and **maker** (optimistic, includes 1c maker fee)

### Realized P&L (Taker variant, actual execution costs)

| Metric | Value |
|--------|-------|
| **Total P&L (taker)** | +$0.7780 |
| **Mean P&L/contract** | +$0.0409 |
| **Std Dev** | $0.2243 |
| **Win rate** | 94.7% (18 wins, 1 loss of −$0.88) |

### Day-Clustered Analysis
Daily P&L (taker) by settlement date:
- **2026-07-12**: +$0.780 (8 bets settled)
- **2026-07-13**: −$0.252 (8 bets settled)  
- **2026-07-14**: +$0.250 (3 bets settled)

**Day-clustered t-test** (H₀: mean daily P&L = 0):
- t-statistic: **0.8704** (target ≥ 2.0)
- p-value: 0.476
- **Does NOT achieve t ≥ 2.0** ✗

### Risk Factor
Identical to longshot: one large loss (−$0.88 on KXXRP15M 26JUL130500, YES settled against a short NO tail entry) and 18 small wins (+$0.06–$0.13 range). Daily P&L is volatile (−$0.252 on day 2) despite high win rate. The taker variant (realistic) returns +$0.778 on 19 bets = +$0.041/contract, indistinguishable from noise.

For reference, the maker variant (optimistic, unrealistic for paper validation) shows +$1.158 total, but since paper execution is closer to taker-like conditions, this is wishful thinking.

### Verdict
**ILLUSION**  
Taker-realistic P&L is flat noise (~+$0.041/contract, t = 0.87 << 2.0). The high win rate masks poor sizing discipline: one loss (-$0.88) wipes out 14 average wins. No out-of-sample edge on realized money.

---

## Comparative Summary

| Metric | Longshot | Tailbias |
|--------|----------|----------|
| Total settled bets | 15 | 19 |
| Settlement days | 3 | 3 |
| Realized P&L | +$0.66 | +$0.78 (taker) |
| P&L per contract | +$0.044 | +$0.041 |
| Win rate | 93.3% | 94.7% |
| Day-clustered t-stat | 0.84 | 0.87 |
| **Achieves t ≥ 2.0?** | **NO** | **NO** |
| **Verdict** | **ILLUSION** | **ILLUSION** |

---

## Conclusion

Both sleeves are **self-reported illusions** in the spirit of av_stoikov—they look profitable on win-rate metrics but realize flat/negative-t money in practice. With only 3 settlement days each and t-statistics around 0.84–0.87 (needing ≥2.0), **neither has demonstrated a real edge out-of-sample**. The positive P&L (~$0.66–$0.78) is consistent with lucky noise rather than a robust strategy. 

**Recommendation**: Treat as NULL / INSUFFICIENT-DATA pending 30+ days of live settlement with t ≥ 2.0 confidence.
