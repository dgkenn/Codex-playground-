# Boxwide-Paper Sleeve Audit

## Summary
Boxwide-paper (W=15c, Kalshi 15m wide-box with 60s managed disposal) exhibits the **ILLUSION** verdict: positive mark-based P&L metrics (+0.274c on 300ms snapshots) are masking systematically negative realized settlement (-1.269c across 2 calendar days of trade data). The strategy fails to escape the adverse-legging trap inherent to sequential box-making—the 60s disposal mechanism executes into unfavorable market locations, losing money on actual paired-box settlement while window-mark optimism inflates reported P&L by 121%.

## Data & Results
- **Settled trades:** 28 (across 2026-07-12 and 2026-07-13)
- **Expired/unscored:** 8
- **Realized P&L (actual disposals):** -1.269c total (-0.0453c/trade avg, 64% negative)
- **Mark-based P&L (300ms snapshots):** +0.274c (+0.0098c/trade avg, 46% positive)
- **Mark-optimism gap:** p300_pnl - realized = +1.543c (121% markup of realized loss)

## Pre-Registration Bar Status
Boxwide targets go-live only if ALL conditions clear:
1. ✗ **≥14 calendar days:** Only 2 days observed (2026-07-12, 2026-07-13)
2. ✗ **Day-clustered t ≥ 3.0 vs null:** t = -0.67 (mean daily P&L = -0.0276c; day-1 +0.0139c, day-2 -0.0690c)
3. ✗ **≥80% days positive:** 1 day positive / 2 total = 50%
4. ✗ **Per-asset sign consistent (4/4 positive):** Only SOL net positive (+0.035c); BTC, ETH, XRP all negative

## Per-Asset Breakdown
| Asset | Trades | Realized P&L | Mark P&L | Gap   | % Pos (realized) |
|-------|--------|-------------|----------|-------|------------------|
| BTC   | 7      | -0.363c     | +0.318c  | +0.681c | 29%             |
| ETH   | 7      | -0.658c     | -0.642c  | +0.017c | 29%             |
| SOL   | 7      | +0.035c     | +1.016c  | +0.982c | 57%             |
| XRP   | 7      | -0.282c     | -0.418c  | -0.136c | 29%             |

## Mechanism Assessment: Does Boxwide Escape Adverse Legging?
**No.** The 60-second managed disposal (taker cross at mid±1c) is executing into adverse locations:
- Realized settlement consistently worse than disposal_mid prices suggest
- Mark snapshots at 300ms (before full market impact realizes) show +1.543c phantom profit
- BTC/ETH/XRP all show mark-optimism gaps of +0.68c, +0.02c, -0.14c (directionally variable, but net positive illusion)
- The mechanism fails to find true edge in Kalshi 15m box pairs; it instead catches window-optimism artifacts

## Verdict
**ILLUSION** (positive mark, negative realized). Boxwide exhibits the same structural zero-edge + adverse-legging pattern as simpler box-making, with mark-window artifacts creating false appearance of +0.274c profitability while real settlement shows -1.269c loss. Strategy does not escape the trap and fails all pre-registration criteria with insufficient run length.
