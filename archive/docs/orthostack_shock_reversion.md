# ORTHOSTACK SHOCK-REVERSION TEST: OOS RESULTS

**Hypothesis**: The market overreacts to sharp mid-window spot moves (shocks) and reverts. After detecting a shock, FADE it by taking the opposite side.

## Data & Setup
- **Train**: 21 days (≤ 2026-06-30) → train shock threshold
- **Test**: 14 days (> 2026-06-30) → OOS day-clustered t-stats
- **Assets**: BTC, ETH, SOL (3 independent markets)
- **Decision Times**: {300, 450, 600}s
- **Shock Detection**: 90th percentile of |spot move %| over 60s windows, before decision_t
- **Fading Rule**: Take binary side OPPOSITE shock direction
- **Scoring Modes**:
  - (a) **Settlement**: Hold to realized settlement (clean label: terminal mid > 0.5)
  - (b) **Round-trip**: Intra-window entry after shock, exit at later tick's mid if reversion detected

## Results: OOS Day-Clustered t-Stats

### Settlement Mode (Hold to Expiry)
| Asset | n | Mean ($/ct) | t-stat | Pos-Days |
|-------|---|-------------|--------|----------|
| BTC   | 458 | +0.0012 | 0.04 | 7/14 |
| ETH   | 439 | +0.0136 | 0.73 | 8/14 |
| SOL   | 415 | -0.0008 | -0.04 | 6/14 |
| **POOLED** | **1312** | **+0.0052** | **0.29** | **6/14** |

### Round-Trip Mode (Fast Reversion Capture)
| Asset | n | Mean ($/ct) | t-stat | Pos-Days |
|-------|---|-------------|--------|----------|
| BTC   | 494 | -0.0068 | -0.66 | 5/14 |
| ETH   | 470 | -0.0123 | -1.36 | 4/14 |
| SOL   | 447 | -0.0190 | -1.84 | 4/14 |
| **POOLED** | **1411** | **-0.0133** | **-2.02** | **5/14** |

### FAVLONG (Reference, Same Windows)
| Asset | n | Mean ($/ct) | t-stat | Pos-Days |
|-------|---|-------------|--------|----------|
| BTC   | 570 | +0.0460 | 2.97 | 9/14 |
| ETH   | 590 | +0.0238 | 1.68 | 9/14 |
| SOL   | 618 | +0.0067 | 0.55 | 8/14 |
| **POOLED** | **1778** | **+0.0246** | **2.45** | **10/14** |

## Orthogonality (Stack Diversification)

Per-window return correlation with FAVLONG:
- **Settlement mode**: r = **-0.157** (weak negative → slight diversifier, but no alpha)
- **Round-trip mode**: r = **-0.003** (orthogonal, but negative edge cancels benefit)

## Verdict

**NULL EDGE — HYPOTHESIS REJECTED OOS**

Neither scoring mode shows a statistically significant standalone edge:
- **Settlement**: t = 0.29 (completely flat, no mean reversion signal)
- **Round-trip**: t = -2.02 (negative; likely costs dominate any fast reversion)

**Interpretation**: Shocks occur, but the book does NOT systematically overreact to mid-window spot moves. Either shocks are too noisy, reversion too slow, or fees/latency erase any edge. The 90th percentile threshold on training data does not generalize.

**Stack Note**: Orthogonal to FAVLONG (r ≈ 0) but non-accretive—no added diversification value without a positive edge of its own. **Do not deploy.**

## Technical Notes
- Shock threshold trained (90th percentile %-move in 60s window): BTC=0.11%, ETH=0.15%, SOL=0.18%
- Clean settlement labels only (proxy-vs-market agreement)
- Kalshi fees applied: 0.07 × p × (1−p) per contract
- Day-clustered t-stat: per-day mean clustering, t = mean_daily / (SE_daily)
- All trades used executable bid/ask; no markout
