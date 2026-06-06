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

## Round 2: five literature-grounded hypotheses (ideas2.py) — none pass

Tested as signals/calibration/realized-economics (not fill-at-quote), window-
clustered, Bonferroni |t|>2.58.

| # | Idea (lit) | Result | Verdict |
|---|---|---|---|
| I1 | favorite-longshot bias (Snowberg-Wolfers) | calibration gaps all <4%; compression slope b=1.06 (NOT <1); bet-favourite t=-0.58 | **well-calibrated, no FLB** |
| I2 | trade-flow imbalance / OFI (Cont et al.) | net-buy-fraction coef t=-0.08 beyond price | no incremental signal |
| I3 | intraday/session seasonality (Wen et al.) | every session: maker \|t\|<0.8, taker_net<0 | no seasonal edge |
| I4 | fade-the-dislocation (reversal) | clustered slope t=-1.12 (naive -2.27 was the clustering illusion) | no clean reversion |
| I5 | better vol model (BS-for-PM, VRP) | constant sigma Brier 0.156 = best; rolling/VRP worse | vol is NOT the binding constraint |

**Why nothing works:** the 15-min BTC market is **well-calibrated** (mean_fair 0.525
vs realized 0.521; Brier 0.156; price-bin gaps <4%) and price already impounds
order flow. This matches the "informed minority (~3%) keeps prices efficient"
literature. The only reliable structure remains takers-lose-≈-the-fee. Across
TWO rounds (taker fair-value + H1/H2/H3 + I1-I5), no strategy survives rigorous
validation; the harness rejected every candidate, including the ones that looked
significant before clustering/truncation/economic tests.

## Round 3: acquired maker-rebate data + proper market-making (markout) test

Acquired (Polymarket docs): makers pay 0 fees and receive a rebate ~= 20% of the
taker fee their liquidity generates (crypto), i.e. ~0.20*0.10*p(1-p) (~0.0035/share
here), plus a separate daily Liquidity-Rewards pool (not per-share quantifiable).
Deribit historical option data is reachable but its daily/weekly expiries can't
match Polymarket's 15-min strikes -> set aside.

Re-tested market-making properly via MARKOUT (a real MM captures spread and
flattens; hold-to-resolution bundles in directional risk), in-window only,
window-clustered + size-weighted + bootstrap CI + OOS, **with rebate**:

| 1s markout (+rebate) | size-wtd [95% CI] | OOS halves |
|---|---|---|
| MID-exit (frictionless; = mechanical half-spread) | +0.0063 [+0.0044,+0.0093] | +8.8/+4.3 |
| CROSS-exit (pay spread to flatten; honest floor) | +0.0013 [-0.0007,+0.0043] | **-2.6/+1.3** |
| hold-to-resolution | -0.0089 [-0.040,+0.021] | -0.0/+0.7 |

Bug caught & fixed: the first markout pass omitted the in-window filter; 10,285
pre-open + 2,610 post-close trades flipped the sign (+0.015 vs the correct
-0.012). After fixing, hold-to-resolution reconciles with maker_sim.

**Verdict: maker thesis FAILS even with rebates.** The only positive component is
the **mechanical half-spread** (MID-exit), which is unrealizable without
frictionless/queue-favorable fills. Under realistic flatten-by-crossing the edge
is statistically zero (CI spans 0) and **sign-flips out-of-sample** (first half
-2.6). Hold-to-resolution + rebate is negative. Capturing the spread for real
needs queue-position / two-sided-fill modeling that historical trade+quote data
cannot validate -- the lever remains genuinely unscoreable, not merely untested.
