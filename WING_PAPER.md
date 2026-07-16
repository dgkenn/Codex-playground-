# WING-VRP — forward paper validation (PRE-REGISTERED)

**Registered 2026-07-15.** The wing-overpricing / variance-risk-premium edge on Kalshi's hourly BTC ladder
(KXBTCD) is the FIRST candidate of this research program to clear the full backtest gauntlet: well-powered,
OOS-in-time, fee-robust, spread-robust (measured wing half-spread 0.2–0.5¢), liquid, AND survived an INDEPENDENT
from-scratch reproduction on fresh data (kalshi_wing_verify.py: +1.27¢/ct t=4.76 selling into real bids, 11,711
wings / 61 dates) — the exact discipline that killed FAVLONG (t=5.74) and the Polymarket favorite-longshot (t=5.5).

Backtests are necessary but not sufficient. This harness is the charter gate: **tested performance must match live.**

## Frozen rule (`wing_paper.py` — DO NOT retune)
- Universe: KXBTCD (hourly BTC "greater than X" ladder).
- Entry: each run, for every OPEN market still in its event's FIRST HALF (`now ≤ open + 0.5·(close−open)`),
  if YES mid `(yes_bid+yes_ask)/2 ∈ [0.04, 0.15]` and `yes_bid > 0` and not already held:
  record a paper **SELL of 1 YES contract at the executable price = `yes_bid`** (conservative TAKER — hit the bid,
  the price the verification proved harvestable; NOT the optimistic mid/VWAP).
- Exit: hold to settlement. `PnL/ct = sell_price − outcome − fee`, `outcome = 1 if result=='yes'`,
  `fee = max(0.01, ceil(0.07·p·(1−p)·100)/100)`.
- Wing band 0.04–0.15 ONLY (the backtest's ≤0.02 bin was taker-dead).

## Gate (charter, do not relax)
- **PASS:** pooled per-close-DATE day-clustered t ≥ 2 over ≥ 10 forward dates AND mean PnL > 0.
- **KILL:** t < 0 after ≥ 10 forward dates.
- Until then: ACCRUING / CLOCK-NOT-STARTED.
- PROPOSE-ONLY: paper only. No order, flag, switch, or size is touched without explicit operator authorization,
  and only after PASS. Expected magnitude ≈ +1–2¢/contract; forward must corroborate before any capital.

## Why this is the honest final step
Everything else this program tested was efficient/priced (direction, distribution, flow, arbitrage). This edge is
different because it has a documented MECHANISM (recreational longshot demand → overpricing) and survived independent
repro. The remaining real risks are execution-at-scale (queue priority, our own market impact), capacity, and decay
(2nd-half OOS was +0.94¢ t=2.3 vs 1st-half +1.58¢ t=4.8). Forward paper trading is the only way to measure those
without risking capital. Deployed hourly via `.github/workflows/wing-paper.yml`; log committed back to the branch.
