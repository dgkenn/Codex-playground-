# Polymarket 15m BTC Up/Down — backtest findings

**Data:** Binance 1s spot + pmxt v2 archive (`r2v2.pmxt.dev`) order book/trades,
2026-04-14 → 2026-04-17 UTC (post-Jan-2026 fee regime). Market discovery via
Gamma (`btc-updown-{tf}-<utc_ts>`). READ-ONLY; no orders, no trading keys.

## Data quality (dataqc.py) — PASS
- Window boundaries are **UTC, 900-s aligned** (slug ts %900==0, endDate=start+900);
  the ET in titles is cosmetic. No UTC/ET offset.
- Spot-label vs market resolution agree **100% on all 225 big-move (>=5bps) windows**;
  the 12 disagreements are all sub-5bps near-ties. Up/Down not inverted
  (direction-agreement 93%). Density ~92k book updates/window.
- **Fee = 1000 bps (10%) on takers**, not the spec's ~700. Verified market identity
  3 ways (slug -> conditionId -> asset_id). Makers pay 0 (Polymarket docs);
  taker fee = `0.10 * p * (1-p)` per share.

## The one methodological key: window-clustered significance
Trades/eval-points inside a window share one outcome, so they are **not
independent**. Per-trade t-stats are inflated by ~sqrt(trades/windows). All
verdicts below use **window-clustered** t-stats (the honest unit ≈ N windows).

## Taker fair-value-vs-quote (run_real.py) — FAILS (artifact)
- Raw sweep looked great: t≈+3.6→+4.3, World-A shape (late + mid-price). But:
  - Raw t was itself ~3.6x clustering-inflated (true ≈ t≈1.0).
  - **Truncation test:** exclude final 180s → full mean **−0.0043 (t=−0.55)**,
    OOS halves disagree in sign. The entire result was the last 180s.
  - **Vol-insensitivity** of the late bucket (t≈13 at sigma 0.5x–3x) is the
    mechanical-pinning fingerprint, not alpha.
- Conclusion: fill-at-quote books the **maker's spread** the taker can't capture.

## Pre-registered search (H1/H2/H3) — none pass

| Hypothesis | Honest metric | Verdict |
|---|---|---|
| **H1** maker hold-to-resolution, BTC 15m | window-clustered **t=+0.26** | no edge |
| **H2** BTC→alt lead-lag (ETH/SOL/XRP), 15m | btc coef sign-incoherent, hit≈0.50, fails multiple-testing | no signal |
| **H3** maker, BTC 5m | equal-wtd t=+2.64 **but size-wtd +0.0054, 95% CI [−0.012,+0.021]**; weakens OOS; t→1.5 sans final 60s | not economic |

Realized-trade economics (every trade has a real maker counterparty):
- BTC 15m: taker net **−0.0023/share** (lose after fee), maker ~flat.
- BTC 5m: taker net **−0.0195/share**, maker size-weighted **+0.0054 (CI spans 0)**.
The dominant, reliable structure is **takers lose roughly the fee** — i.e. the
edge is captured by the fee (Polymarket), not by either side of the book.

## Bottom line
After pre-registering 3 economically-motivated hypotheses and applying
truncation + out-of-sample + window-clustering + multiple-testing + size-weighted
economic significance, **no strategy clears the bar.** The harness correctly
rejected everything, including the things that looked like +4 t-stats.

A genuine winner here would need a lever this dataset cannot score: maker **fee
rebates** (flips maker economics), **active inventory/hedging** quoting models
(not scoreable from historical quotes), or **sub-second execution** for
cross-asset lead-lag (needs tick infra beyond hourly-bucketed archive).
