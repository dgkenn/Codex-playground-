# Full optimal stack vs current live strategy (2026-06-13)

Apples-to-apples, BTC tape, 367 OOS windows (last 40%), GBM not deployed (signal-only), R4 removed +
R5 hedge deferred in BOTH (matching the now-live reality after removing --strand-scaledown). So the
ONLY delta between the two is RUNG 0: the new dynamic-vol spread buffer (1c floor; 2c when window
|sig| >= p75 ~ 8.4bps). Everything else (R1 t36 gy=0.02, R3 sell-cheap<0.30 + give 0.02) is identical.

| metric | CURRENT LIVE (t36) | OPTIMAL (+buffer) | delta | read |
|---|---|---|---|---|
| net c/win | +2.38 | +3.34 | **+0.96c** (t=+1.00) | up, not yet significant |
| Sharpe | 0.072 | 0.121 | **+68%** | much better risk-adj |
| Sortino | 0.068 | 0.103 | +51% | better downside-adj |
| Skew | -0.20 | -0.10 | +0.10 | less left-tailed |
| Kurtosis | 0.70 | 1.91 | +1.21 | (still tame) |
| CVaR95 c | 73.2 | 64.3 | -8.8c | smaller tail loss |
| VaR95 c | 57.3 | 52.4 | -4.9c | smaller tail loss |
| **MaxDD c** | 1038 | 575 | **-45%** | drawdown ~halved |
| **Ulcer c** | 490 | 237 | **-52%** | pain index ~halved |
| Recovery | 0.84 | 2.13 | +153% | far better |
| TimeUW % | 87.7 | 82.0 | -5.7pp | less time underwater |
| Win % | 57.5 | 55.6 | -1.9pp | fewer marginal boxes |
| ProfitFactor | 1.21 | 1.44 | +0.23 | better |
| AvgWin/Loss | 0.89 | 0.82 | -0.07 | slightly worse... |
| **Strand %** | 48.8 | 17.4 | **-31pp** | ...offset by far fewer strands |
| IR vs P0 | -0.01 | +0.02 | +0.03 | crosses positive |

**Takeaway:** the optimal stack ~HALVES drawdown (MaxDD -45%, Ulcer -52%), nearly DOUBLES Sharpe
(+68%), cuts every tail metric (CVaR/VaR/skew), and slashes the strand rate ~3x -- for a small,
not-yet-significant net GAIN (+0.96c/win, t=1.00). Win% and avg-win/loss tick down slightly (we trade
fewer marginal break-even boxes) but the strand reduction more than compensates. The improvement is
overwhelmingly a RISK-QUALITY upgrade with a net that is at worst flat and likely modestly positive.

CAVEATS: (1) tape replay inflates absolute strand% (mean 1c spread; t36's 2c floor blocks ~90% of bid
fills in replay) -- read the DELTAS, not the levels. (2) +0.96c net is t=1.00, NOT significant -> the
buffer must clear the live A/B forward bar (n>=300, t>3) before going to live.yml. (3) The deferred
HEDGE (R5) is NOT in this stack -- Phase C showed a clean delta-neutral hedge barely helps (the
ablation's -0.98c was an over-hedge artifact), so it would add little here even if deployable.
