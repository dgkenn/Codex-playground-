# Performance metrics — the full suite (beyond Sharpe)

A reviewer correctly noted Sharpe alone is insufficient. `metrics.py` computes the risk / profitability /
consistency / execution suite on the shadow data. **Read the maker-specific caveats first — they change how
several metrics are interpreted.**

## Caveats (why naive per-trade metrics mislead for a rebate maker)
- **Unit = a WINDOW (one market we made), not a "trade."** A maker holds balanced sets to resolution; there
  is no discrete entry/exit "trade" with a win/loss. So Win Rate / Profit Factor / W-L are **per-window**.
- **`net` is rebate-inclusive and resolution-based**, so its variance INCLUDES the directional swing on
  residual inventory held to resolution — that's real risk for a hold-to-resolution book, and it's what
  drives drawdown.
- **PAPER / front-of-queue.** The sim fills at queue position ≈ 0, so absolute P&L, fill rate and edge are
  **upper bounds**; the live haircut is the queue battle (`PAPER_VS_LIVE.md` A4).
- **Annualized Sharpe/Sortino are meaningless here** — at ~140k 15-min windows/yr the √n factor inflates
  them absurdly. We report **per-window Sharpe as a t-stat** (is the edge real?) and use **MDD / Calmar /
  Profit Factor / Win-rate / W-L / edge-bps** for the comparative risk picture.
- **Maker ratio = 100% by construction** (post-only + the `would_cross` guard) — the gold standard; we never
  pay taker fees by accident.

## Current numbers (4 days, 56k fills, per-(asset,window))
| gate | net/win | Sharpe(t) | Sortino | MDD$ | Calmar | ProfitFactor | Win% | W/L | edge(bps) | kept% |
|---|---|---|---|---|---|---|---|---|---|---|
| micro | +4.88 | 3.3 | 0.33 | 249 | 8.4 | 1.69 | 54% | 1.46 | 97 | 78% |
| **ufat** (deployed) | +4.85 | 3.3 | 0.33 | 234 | **8.8** | 1.68 | 53% | 1.48 | 95 | 79% |
| **ufat_band** (best by net) | **+11.48** | 3.1 | 0.36 | **1253** | **3.9** | **1.74** | 45% | **2.11** | **309** | 54% |

## How we stack up vs the reviewer's targets
- **Profit Factor 1.68–1.74** → in the ">1.5 viable" band (not yet ">2.0 strong"). ✅ ok
- **Maker ratio 100%** → gold standard. ✅
- **Edge (PnL/volume) 95 bps (ufat)** → strong per-$-traded efficiency for a maker. ✅
- **Win rate 45–54%** → consistent with the reviewer's note that Polymarket makers "win ~47% of fills but
  net positive via fees." ✅ (ufat_band's 45% is offset by W/L 2.11.)
- **Sharpe t ≈ 3.3** → the edge is statistically real over the sample. ✅
- **Sortino 0.33–0.36 (per-window)** → low per-window, but positive and ≥ Sharpe (downside not fat). ◐
- **Max Drawdown / Calmar** → ⚠️ **the weak spot.** Plain `ufat` Calmar 8.8 is healthy; **`ufat_band`
  Calmar 3.9** — its extra return comes with 5× the drawdown.

## The key finding (the metrics overturn "ufat_band is simply best")
`ufat_band` wins on **raw net (+11.5)** and **Profit Factor / W-L / edge**, but it's **worse on Calmar/MDD**
because `notmid` (drop the 0.30–0.55 zone, keep the tails) concentrates into the **high-prob tail**, whose
fills carry large *directional* resolution swings. So a chunk of `ufat_band`'s extra edge is **directional
tail risk, not pure rebate** — exactly the trap the whole project guards against. Plain `ufat` is the better
**risk-adjusted** strategy today (Calmar 8.8 vs 3.9).

## Improvements this implies (ranked)
1. **Judge variants by Calmar/Sortino, not net/win.** `leaderboard.py` should add MDD/Calmar columns; the
   A/B "winner" is the best *risk-adjusted* one, not the highest net. (Promotes `ufat`, demotes `ufat_band`
   until hedged.)
2. **Delta-hedge residual inventory** (BTC perp, `ROADMAP` Tier-1) → strips `ufat_band`'s directional tail,
   which should collapse its MDD and make its higher return risk-adjusted-superior. The hedge is the unlock
   that makes the high-octane gate safe.
3. **Per-regime breakdown** (reviewer #3): don't average across regimes — split by asset (done: BTC≫others),
   and add volatility/trend regime. `metrics.py` → add a `--by-asset` / `--by-regime` view.
4. **Confirm fill rate live** (paper is the front-of-queue upper bound) via `pilot_reconcile.py`.
5. **Position sizing** (reviewer): keep clips tiny (1–2% bankroll), cap total exposure — already the design;
   make the per-asset weight BTC-heavy (Insight 2) and bound aggregate inventory.

Run: `python metrics.py` (after `git checkout origin/gha-data -- gha_data/`).
