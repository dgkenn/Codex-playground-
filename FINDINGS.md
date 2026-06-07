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

## Round 4 + 5: more strategies, diagnostics-driven theses (new data: Up+Down books, alt books, wallet-attributed trades, strike ladders)

No-data tests (all fail): S5 TS-momentum, S8 whale-follow (t=+0.00), S9 impact-reversion
(large trades have PERMANENT impact, fading loses t=-5.5), D late-extreme calibration,
E token-momentum.

Acquired data + tests:
- **S4 overround arb** (Up+Down books): Up_ask+Down_ask always >=1 (min 1.001), no
  crossing -> no arb (book internally consistent).
- **A strike-ladder arb** (10-strike 'above $K' ladders): MID non-monotone 43.9% of
  snapshots (mispricing signal) but **0 crossable inversions** -> absorbed by spread.
- **B cross-venue (Kalshi)**: archive 404, not available.
- **S2/D3 cross-sectional reversion** (4-coin token panel): GROSS edge REAL (+0.0068/step,
  t=+4.40; clustered slope t=-2.95) but round-trip cost ~0.10/pair (2 spreads + 4x10% fee)
  -> NET taker -0.093 (t=-56). Killed by fees (~15x the edge).
- **S3 / D1 market lead-lag**: alt tokens move contemporaneously with BTC token; lagged
  coef ~0.02 (t~0.6) -> no tradeable lead-lag.
- **Copy-the-informed-minority** (wallet-attributed trades, 628k trades / 10.8k wallets):
  top-1% wallets capture 45.5% of positive PnL (real informed minority). Ranking by
  per-trade ROI does NOT persist (t=0.7); ranking by TOTAL PnL **persists OOS**
  (+0.018/trade, **t=+3.76**). BUT a realistic follower (enter +60s later, taker, 10% fee)
  **loses -0.038/trade (t=-5.93)**: the wallets' ~1.8c/trade edge < the ~2.5c taker fee.

**Unifying conclusion across all rounds:** several signals are genuinely REAL
(cross-sectional reversion gross t=4.4; wallet-skill persistence t=3.76; ladder mid
non-monotonicity 44%) -- but every one is smaller than the 10% taker fee + spread, so
none is tradeable by a fee-paying taker. **The fee is the moat.** The structure is
captured only by fee-exempt maker/price-setters (0 fee + rebate), which historical
trade+quote data cannot score for queue position / fills. Verdict stands: no
backtestable taker strategy survives; the only viable seat is informed market-making,
which requires live fill data to validate.

## Round 6-7: hedge-fund playbooks, recombination, and the first STRONG candidate

JS/fund-style tests (corrected per-category fees, window-clustered, OOS):
- **Selective (toxicity-filtered) MM**: confirms small=benign/large=toxic structure but only
  breakeven under honest cross-to-flatten (queue-bound).
- **Two-Sigma ML ensemble**: market price BEATS the kitchen-sink model OOS (Brier 0.154<0.157);
  no predictive edge over price. Combining predictive signals does NOT stack into alpha.
- **Combination / trained toxicity-model maker**: selecting "best" fills makes it WORSE OOS
  (chases toxic vig); signals don't recombine into a maker edge.
- **Overround (S4) / 2-sided structure**: Up_ask+Down_ask ~1.01 always (no taker arb).

**>>> STRONG CANDIDATE: inventory-capped 2-sided maker (rebate farming).**
Quote both Up+Down, cap net delta. Earlier "maker fails" was ONE-sided only; making BOTH
sides hedges direction. Decomposition (cap=100, corrected 0.07 fee basis):
  GROSS trading +0.00007/sh (t=0.81, breakeven) ; + 20% maker rebate -> +0.00098/sh (t=12.2);
  IS/OOS t = 12.2 / 7.4 ; survives 50% rebate haircut (OOS t=4.3). Edge = the rebate; gross
  is breakeven taking ALL flow (worst-case adverse selection). cap is the risk/Sharpe knob
  (cap=25 t=19, cap=400 t=7.7). Paper-trading spec in PAPER_TRADING.md. Live unknowns:
  fill rate/queue, realized rebate pool share, adverse-selection-weighted fills.

**Multi-category calibration / favorite-longshot battery (3,056 resolved markets):**
- **Sports (fee 0.03): strong FLB**, bet-favourite +0.12 net (t=9.3), survives 5c half-spread
  (+0.07, t=5.5). BUT concentrated in slight-favourites (0.5-0.6: +0.245) and VANISHES in the
  most-liquid markets (n_pts>=300: t=-0.05); markets are illiquid UFC/MMA prop/futures whose
  tradable liquidity can't be verified from this data. REAL bias, tradability unproven ->
  strong lead needing LIVE liquidity validation, not a ready candidate.
- geopolitics (fee 0): favourites slightly OVER-priced (bet-fav negative) -> reverse bias.
- politics/tech/economy/culture/crypto: ~0 or negative net of fee.

**Answer to "combine the inefficiencies":** predictive signals are already in the price
(ensemble loses to price; combining doesn't help). The only net-positive, robust, ready edge
is the STRUCTURAL one (maker rebate), which doesn't need to beat the price. Sports FLB is a
real second inefficiency but lives in illiquid markets (untradeable from this data).

## Round 8: refine the maker before paper trading

Adjacent ideas tested on the inventory-capped 2-sided maker:
- per-quote SIZE LIMIT (post small depth): HURTS (the 2-sided vig scales with captured
  volume; throttling reduces it). Rejected.
- STOP quoting in the final sprint (tau<cutoff): HURTS (less volume/rebate, vig present late
  too). Rejected.
- **inventory CAP is the key knob — and TIGHTER is better/safer.** At cap<=25 the GROSS
  (no-rebate) edge is positive & significant: cap=25 gross +0.00019/sh t=+5.8 (OOS 3.3),
  cap=10 gross t=+10.6 (OOS 5.9), with near-zero drawdown ($0-11). NET (+rebate) t=20-24
  (OOS 11-13). **Zero-rebate stress (cap=25): survives (gross OOS t=3.3).**

REFINED VERDICT: the candidate is a **tight-inventory 2-sided vig-capture maker** whose
gross edge stands alone (rebate no longer a single point of failure; it ~triples the return).
Start cap~20, near-zero drawdown, gross-positive, rebate on top. Capacity is the tradeoff
(tight cap = small $/market) -> scale via MULTI-MARKET diversification (BTC 5m + ETH/SOL/XRP
15m, each an independent vig stream), the validated next step (needs up+down trade pulls).
