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

## FULL COMBINATORIAL STACK (best-of-every-rung, with interactions) -- 2026-06-13
The per-rung agents each optimized in ISOLATION (held other rungs at baseline), so they never saw the
COMBINED optimum. Operator asked: stack the best buffer + best prevent + best complete + best hedge,
+/- best manage, and compare vs live. Done below (367 OOS windows; ETH hedge delta-corr-scaled 0.43;
Kelly = fractional-Kelly lam0.25; all vs the now-live t36+complete). KEY: rungs that LOST in isolation
HELP in the stack.

| Stack | net c/win | dNet (t) | Sharpe | CVaR95 | MaxDD | Ulcer | Recov | TUW% | Win% | strand% |
|---|---|---|---|---|---|---|---|---|---|---|
| LIVE (t36+complete) | 2.38 | -- | 0.07 | 73 | 1038 | 490 | 0.84 | 88 | 57.5 | 48.8 |
| core (+buffer R0) | 3.34 | +0.96 (1.00) | 0.12 | 64 | 575 | 237 | 2.13 | 82 | 55.6 | 17.4 |
| +ETH hedge (R5a) | **3.63** | **+1.25 (1.27)** | 0.13 | 62 | 499 | 203 | 2.67 | 81 | 56.1 | 17.4 |
| +Kelly0.25 (R4) | 2.63 | +0.25 (0.21) | 0.14 | 43 | 350 | 141 | 2.76 | 78 | 53.7 | 17.4 |
| +ETH +Kelly0.25 | 2.84 | +0.46 (0.38) | **0.15** | **42** | **299** | **119** | **3.49** | 75 | 54.0 | 17.4 |
| buffer-subsumes-t36 | 2.52 | +0.14 (0.09) | 0.19* | 40 | 125* | 37* | 7.40* | 64 | 67.0 | 4.1 |

FINDINGS:
- **The ETH hedge HELPS in the stack** (+0.29c over core, best NET +1.25c, MaxDD 575->499, Ulcer
  237->203) -- opposite to its isolated test, where the small standalone strand pool made it look like
  it added variance. In the full stack it trims the residual strand tail. Best NET stack = buffer + t36
  + complete + ETH hedge (no manage).
- **The MANAGE rung (Kelly lam0.25) ALSO helps -- on RISK, not net** (operator's hypothesis confirmed):
  +ETH+Kelly gives the best Sharpe (0.15, 2x live), CVaR 42 (-43%), MaxDD 299 (-71%), Recovery 3.49,
  at a smaller net gain (+0.46c). It trades ~0.8c net for a big drawdown cut -- a risk-budget choice.
- **buffer-subsumes-t36** posts the headline Sharpe 0.19 / MaxDD 125 / strand 4.1% BUT skew -1.79,
  AvgW/L 0.53, far fewer boxes -> the low drawdown is thin-sample (few large losses simply didn't
  cluster in 367 windows). FRAGILE; NOT recommended over keeping t36.
- NONE clears t>2 on net (best +1.25c at t=1.27) -> all are RISK-QUALITY upgrades with an unproven (but
  positive-leaning) net edge. Forward A/B required before any live change.

RECOMMENDED FULL OPTIMAL STACK (objective-dependent):
- MAX NET:           R0 buffer + R1 t36 + R3 complete + R5a ETH hedge      (+1.25c, MaxDD -52%)
- MAX RISK-ADJUSTED: + R4 Kelly lam0.25                                    (Sharpe 2x, MaxDD -71%, +0.46c)
Either way the buffer + ETH hedge are the additive pieces; Kelly is the optional drawdown lever.
Deploy order: buffer first (biggest, simplest), then ETH hedge, then Kelly if drawdown matters -- each
through the forward A/B bar. (The streak guard stays removed; Kelly is its proper replacement IF we
want a manage rung at all.)
