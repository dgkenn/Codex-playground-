# Cross-Sectional Crypto Momentum — Brutal De-Risk & Deploy Spec

**Date:** 2026-06-14
**Author:** automated research (claude)
**Branch:** claude/polymarket-bot-live-ready-vw7ut5
**Scope:** De-risk the prior "XS momentum (14d, weekly, top/bottom-30% of ~10 coins) +
55d channel overlay → OOS Sharpe ~1.0-1.2, 37%/yr, capacity $10-50M" finding into a
realistically-sized, deployable spec — or kill it.

---

## TL;DR — VERDICT: THINNER AND SMALLER THAN THE HEADLINE. Paper-trade only.

The headline overstated the edge on **two** independent axes, both exposed by this de-risk:

1. **The headline 14d Sharpe is a narrow SPIKE, not a plateau.** Full-history weekly surface:
   14d/30% = 1.39 Sharpe, but its immediate neighbours (7d, 21d, 30d) are 0.07–0.69. A single
   bright cell surrounded by mediocre ones is the signature of curve-fit, not a robust factor.
2. **The edge lives in the thin alts we CANNOT trade at scale.** On the realistically tradeable
   liquid-perp universe (6 coins, BTC/ETH/SOL/XRP/DOGE/ADA), the headline 14d/30% config goes
   **NEGATIVE in the recent 18 months (-0.14 Sharpe, -17% ann)**. The full-10-coin number is
   propped up by AVAX/LINK/LTC, which have only ~$13-16M/day perp volume — untradeable beyond ~$4M.
3. **Capacity is ~$3-6M, not $10-50M.** Binding coin caps it (ADA at $31M/day → ~$3-6M AUM;
   if you keep the thin alts, AVAX caps it at ~$4M). By $1M AUM net OOS Sharpe is already ~0.1;
   by $10M it is deeply negative.
4. **Short-side funding is a tiny tailwind, ~+0.5%/yr — effectively a rounding error**, not the
   "free boost" one might hope. All bottom-momentum coins ARE shortable (liquid OKX USDT perps).
5. **A surviving config exists but only after post-hoc re-selection**: shorten the lookback to
   **10d** and add a **vol-target + crash filter** on the 6-coin universe → recent OOS Sharpe
   0.66, ann ~13%, maxDD cut to -22%, and (unlike 14d) it is positive in all 4 historical folds.
   Because the 10d choice was found *after* 14d failed, treat its forward number as optimistic.

**Realistic forward expectation (deployable, after ALL frictions):** **Sharpe ~0.3–0.6, ann
~8–18%, maxDD ~25–35%** at $10k–$1M. NOT 37%. Capacity for our scale is fine; the *edge* is the
binding constraint, not liquidity. **Recommendation: PAPER-TRADE for 3-6 months against the
go-live bar below before any real capital.** This clears a generous bar barely, and only on a
config selected with hindsight.

---

## 1. Data Window & Assumptions

| | |
|---|---|
| **OHLCV** | OKX `history-candles`, daily, **2019-11-19 → 2026-06-14** (~2400 bars), 10 USDT pairs: BTC ETH SOL XRP DOGE ADA AVAX LINK LTC BNB. (SOL/AVAX from 2020-09, BNB from 2022-12.) |
| **Funding** | OKX `funding-rate-history` for the 10 USDT-SWAP perps. **Public API caps at ~3 months: 2026-03-12 → 2026-06-14** (283 events/coin = 3×/day). This is a hard limitation — funding netting below is characterized on the *current* regime only and corroborated by the well-documented structural positivity of perp funding. |
| **OI / liquidity** | OKX `open-interest` + ticker `volCcy24h` snapshots (2026-06-14). |
| **Cost model** | `cost = cost_bps × Σ|Δweight|` per rebalance. **Base = 7 bps** round-trip (OKX taker ~8-10 bps/side on perps + slippage on modest size). Scale-dependent slippage added in §4. |
| **Funding sign** | Positive funding ⇒ longs pay shorts ⇒ **short leg RECEIVES**. P&L term = `-weight × funding_rate` (short = negative weight earns positive funding). |
| **Execution** | Signal on close[t], position lagged 1 day (held t→t+1). Weekly = rebalance every 7 bars; biweekly = 14. Dollar-neutral, equal-weight legs. |
| **OOS holdout** | **Last 18 months (2024-12-14 → 2026-06-14)** as the hard forward proxy; 12-month (2025-06-14 →) shown alongside. Backtests SCREEN, not prove. |

---

## 2. TASK 1 — Parameter Robustness Surface (overfit check)

### Full-history Sharpe surface — WEEKLY rebalance, 7bps, 10-coin (no funding)

| lookback \ quantile | 20% | 30% | 40% |
|---|---|---|---|
| **7d** | 0.07 | 0.28 | 0.26 |
| **10d** | 0.43 | 0.48 | 0.51 |
| **14d** | 0.44 | **1.39** | 1.21 |
| **21d** | 0.21 | 0.48 | 0.57 |
| **30d** | 0.50 | 0.69 | 0.75 |

The 14d/30% cell (1.39) is **an isolated spike** — every neighbour is 0.2–0.8. Surface
mean 0.55, sd 0.35. **This is not a plateau.** A robust factor would show a broad high-Sharpe
ridge; here one cell dominates.

### Recent 18-month OOS Sharpe surface — WEEKLY (10-coin)

| lookback \ quantile | 20% | 30% | 40% |
|---|---|---|---|
| **7d** | 0.47 | 0.32 | 0.50 |
| **10d** | 0.66 | 0.67 | 0.45 |
| **14d** | 0.50 | 0.53 | -0.03 |
| **21d** | **-0.32** | -0.20 | -0.20 |
| **30d** | **-0.48** | -0.35 | -0.51 |

The surface **collapses out-of-sample**: mean Sharpe 0.13, only 53% of cells positive. The edge
**migrated to SHORTER lookbacks (7-10d)** recently and **longer lookbacks (21-30d) now LOSE money**.
The headline 14d still ~0.5 on the full universe but, as §4 shows, that depends on the thin alts.
Biweekly rebalance is generally worse (more cells negative).

### Decay / regime — baseline 14d/weekly/30%, 4 equal folds (10-coin)

| Fold | Window | Sharpe | Ann | maxDD |
|---|---|---|---|---|
| 1 | 2019-11 → 2021-07 | 1.67 | 307% | -46% |
| 2 | 2021-07 → 2023-03 | 2.05 | 225% | -38% |
| 3 | 2023-03 → 2024-10 | 0.29 | 3% | -41% |
| 4 | 2024-10 → 2026-06 | 1.51 | 83% | -44% |

Not a clean monotone decay — fold 3 nearly died then fold 4 rebounded. So it's **regime-dependent,
not purely crowding**, but the level is clearly **far below the early-history 200-300% ann**. The
honest forward number is the recent-regime one, **not** 37% full-history.

**Realistic forward (10-coin, 14d/weekly/30%, 7bps, no overlay): OOS18 Sharpe 0.53, ann ~13%,
maxDD -44%; OOS12 Sharpe 0.79.** Already well below the 37% headline.

---

## 3. TASK 2 — Short-Side Funding Interaction

### Current funding (OKX, 2026-03-12 → 2026-06-14), annualized

| Coin | %/8h | Ann | Coin | %/8h | Ann |
|---|---|---|---|---|---|
| BTC | +0.0014 | +1.5% | ADA | +0.0019 | +2.1% |
| ETH | +0.0019 | +2.0% | AVAX | +0.0013 | +1.4% |
| **SOL** | **-0.0008** | **-0.8%** | LINK | +0.0024 | +2.6% |
| XRP | +0.0023 | +2.5% | LTC | +0.0033 | +3.6% |
| DOGE | +0.0036 | +4.0% | BNB | +0.0031 | +3.4% |

**9 of 10 coins have POSITIVE funding ⇒ a SHORT receives funding (structural crypto tailwind).**
Only SOL was mildly negative recently. Magnitudes are small now (calm regime; in euphoric markets
alt funding spikes to 50-100%+ ann, a much bigger short tailwind — but also when momentum crashes).

### Net into strategy P&L (over the 95-day funding window)

| | Without funding | With funding |
|---|---|---|
| Ann return | +47% | +47% |
| Sharpe | 2.14 | 2.16 |

**Net funding contribution: ~+0.5%/yr (+0.15 bps/day).** Why so small despite positive funding?
The strategy is **dollar-neutral**: it is long high-momentum coins (which carry the *highest*
positive funding, so the LONG leg PAYS) and short low-momentum coins (lower funding, so the SHORT
leg receives less). The two legs largely cancel. **Funding is neither a hidden cost nor a free
boost — it's a wash (~+0.5%/yr tailwind) in the current regime.** It can swing more positive in
high-funding regimes, but those coincide with crash risk.

### Shortability

All 10 coins have **liquid OKX USDT-perpetuals (perp = YES for all)**. Bottom-momentum alts are
fully shortable via perps — no borrow constraint (perps don't require locating borrow). OI ranges
$11M (AVAX) to $2.0B (BTC). Shorting is mechanically fine; the constraint is *trade liquidity* (§4),
not availability.

---

## 4. TASK 3 — Crash / Tail Risk & Risk Overlays

### Worst momentum-crash days (10-coin baseline)

Full-history maxDD = **-59%** (peaked 2021-08). Worst single days clustered in **Jan–May 2021**
(strat -13% to -18%/day). Notably several occurred when the market was NOT in drawdown
(2021-01-06 strat -18%, market dd 0%) — i.e. **violent intra-leadership rotation / reversal**, the
classic momentum crash, not just beta. A pure market-drawdown crash filter only partially catches these.

### Overlays — 10-coin, full history & recent OOS

| Overlay | Full Sharpe | Full ann | Full maxDD | OOS18 Sharpe | OOS18 ann | OOS18 maxDD |
|---|---|---|---|---|---|---|
| base (14d/30%) | 1.39 | 124% | -59% | 0.53 | 13% | -44% |
| vol-target 40% | 1.27 | 63% | -60% | 0.31 | 4% | -60% |
| **crash filter** | 1.23 | 78% | **-45%** | 0.53 | 8% | **-25%** |
| voltgt40 + crash | 1.33 | 42% | **-36%** | 0.31 | 4% | -36% |

**Key result:** On the 10-coin universe, **vol-targeting HURTS recent Sharpe (0.53→0.31)** —
crypto vol is trending/auto-correlated, so 1/vol sizing de-risks right before rebounds. The
**crash filter (de-gross to 0.5× when the equal-weight market is >20% off its high OR realized vol
> rolling 90th pct) is the winner: it keeps Sharpe (0.53) while cutting maxDD from -44% to -25%.**

On the **deployable 6-coin universe with the surviving 10d lookback**, vol-targeting *does* help
(thinner universe, different vol dynamics) — best combo there is voltgt40 + crash (see §6).

---

## 5. TASK 4 — Execution & Capacity at Our Scale

### Turnover

Avg gross turnover ~2.06 per weekly rebalance; **~103× notional/yr annualized**. At 7 bps that's
~7%/yr cost drag — the dominant friction, consistent with the cost-sensitivity in the prior study.

### Per-coin capacity (10% of 24h perp $-volume per rebalance ⇒ ~single-digit-bps slippage)

| Coin | 24h $vol | AUM cap | Coin | 24h $vol | AUM cap |
|---|---|---|---|---|---|
| **AVAX** | $13M | **$3.9M** | ADA | $31M | $9.3M |
| LINK | $14M | $4.1M | XRP | $93M | $27.9M |
| LTC | $16M | $4.7M | DOGE | $170M | $51M |
| BNB | $25M | $7.6M | SOL | $318M | $95M |
| | | | ETH/BTC | $2.6-2.8B | $770M+ |

**The thin alts (AVAX/LINK/LTC) bind capacity at ~$4M.** Restricting to the liquid-perp universe
(vol24h ≥ $30M ⇒ **6 coins: BTC ETH SOL XRP DOGE ADA**) raises the binding coin to ADA → AUM cap
**~$3-6M** (5-10% participation). Either way, **realistic capacity ≈ $3-6M, NOT $10-50M.**

### Net at scale (10-coin, scale-dependent slippage, voltgt40+crash overlay, recent OOS18)

| AUM | Cost (bps) | Thin-coin partic | OOS18 Sharpe | OOS18 ann | maxDD |
|---|---|---|---|---|---|
| $10k | 7.1 | 0.03% | 0.31 | 4% | -36% |
| $100k | 7.8 | 0.26% | 0.29 | 4% | -36% |
| **$1M** | 14.7 | 2.57% | **0.07** | -1% | -37% |
| $10M | 84.1 | 25.7% | -1.85 | -33% | -52% |

**At ≤$100k frictions are immaterial; by $1M slippage on the thin alts halves the (already thin)
edge; by $10M the strategy is dead.** This is the honest capacity picture for the *full* universe.

---

## 6. THE DEPLOYABLE UNIVERSE — where the headline breaks

Trading only the liquid-perp universe (the realistic deployment) changes the conclusion:

### XS 14d/weekly/30% by universe (7bps, +funding)

| Universe | Full Sharpe | OOS18 Sharpe | OOS18 ann | OOS18 maxDD | OOS12 Sharpe |
|---|---|---|---|---|---|
| 10-coin (full) | 1.39 | 0.54 | 13% | -44% | 0.79 |
| **6-coin (deployable)** | 1.11 | **-0.14** | **-17%** | -57% | **-0.13** |
| 5-coin (>$90M/d) | 0.99 | -0.36 | -25% | -60% | -0.96 |
| 8-coin (>$15M/d) | 1.41 | 0.18 | -1% | -50% | -0.00 |

**On the deployable 6-coin universe the headline 14d/30% config LOSES MONEY in the recent regime.**
The full-universe edge was riding the thin alts. This is the single most important de-risk finding.

### Recovering an edge on the 6-coin universe — lookback × quantile (recent OOS18 Sharpe)

| lookback | q20 | q30 | q40 |
|---|---|---|---|
| 7d | -0.06 | -0.06 | -0.18 |
| **10d** | **+0.37** | **+0.37** | **+0.60** |
| 14d | -0.14 | -0.14 | -0.30 |
| 21d | -0.10 | -0.10 | +0.36 |
| 30d | -0.46 | -0.46 | -0.44 |

Only the **10d lookback** survives on the deployable universe. With overlays (10d/20%):

| Config (6-coin, 10d/20%, weekly, +funding) | OOS18 Sharpe | OOS18 ann | OOS18 maxDD |
|---|---|---|---|
| base | 0.37 | 6% | -50% |
| + crash filter | 0.45 | 9% | -31% |
| + vol-target 40% | 0.68 | 22% | -39% |
| **+ vol-target + crash** | **0.66** | **13%** | **-22%** |

This config is also the **most fold-stable** of anything tested — positive in all 4 folds
(1.38 / 0.73 / 1.14 / 1.16), OOS12 Sharpe 1.51 / ann 36%. **BUT the 10d lookback was selected
AFTER 14d failed on the deployable set — a hindsight choice. Discount its forward number.**

---

## 7. DEPLOYABLE SPEC (recommended config)

| Parameter | Value | Rationale |
|---|---|---|
| **Universe** | BTC, ETH, SOL, XRP, DOGE, ADA (6 liquid OKX USDT-perps, vol24h ≥ $30M) | only tradeable beyond ~$1M; full 10-coin edge is a thin-alt artifact |
| **Signal** | Cross-sectional 14-day return rank | NOTE: 14d is the *robust prior*; **10d** is the recent survivor. Run **both 10d and 14d in paper and pick by live evidence**, don't hard-commit to the hindsight 10d |
| **Construction** | Long top quantile / short bottom quantile, dollar-neutral, equal-weight | |
| **Quantile** | 30% (≈2 long / 2 short of 6) | 20-40% all similar; 30% middle-of-road |
| **Rebalance** | **Weekly** | biweekly worse; daily fee-eaten |
| **Vol-target** | size ∝ 40%-ann-vol / 30d-realized-vol, capped 2×, floor 0.1× | helps on 6-coin universe; cuts DD |
| **Crash filter** | de-gross to 0.5× when EW-market >20% below its high OR 20d realized vol > rolling-90th-pct | cuts maxDD ~50% → ~22-30% with little Sharpe cost |
| **Funding** | net into P&L; expect ~wash (+0.5%/yr) | structural short tailwind, small when neutral |
| **Venue** | OKX USDT perps (primary); dYdX/Hyperliquid as backup/redundancy | all 6 coins liquid; shorting via perps = no borrow constraint |
| **Capacity** | **hard-cap AUM at ~$3M** (≤10% of ADA 24h vol per rebalance) | above this, slippage on ADA/XRP kills the thin edge |
| **Cost budget** | 7 bps base; alarm if realized > 12 bps | turnover ~100×/yr ⇒ cost is the dominant drag |

**Realistic forward expectation for this spec (after ALL frictions, recent regime):
Sharpe ~0.3-0.6, ann ~8-18%, maxDD ~22-35%.** Headline 37% is NOT the forward number.

---

## 8. FORWARD PAPER-VALIDATION PLAN (before any real capital)

**Run paper/shadow for a minimum of 3 months (target 6) on OKX live prices + live funding.**

**Track weekly:**
1. **Realized vs backtest weekly returns** — correlation and tracking error. Flag if live
   underperforms backtest by >1 sd for 4 consecutive weeks.
2. **Realized slippage per rebalance per coin** vs the 7 bps assumption (especially ADA/XRP).
   Go-live requires realized round-trip ≤ 12 bps.
3. **Realized funding** on both legs vs the modeled ~wash. Confirm short leg actually receives.
4. **Rolling 8-week Sharpe** of the live paper book (annualized).
5. **Max drawdown** vs the -22 to -35% expectation; verify crash filter actually de-grosses in
   any market wobble.
6. **10d vs 14d horse-race** in parallel paper books — let live data, not hindsight, pick.

**GO-LIVE BAR (all must hold over ≥3 months paper):**
- Rolling paper Sharpe (after real fills + funding) **≥ 0.5 annualized**.
- Realized cost/slippage **≤ 12 bps** round-trip.
- No drawdown **> 35%**, and the crash filter demonstrably engaged in any >15% market drop.
- Live-vs-backtest weekly return correlation **≥ 0.6** (model is tracking reality).
- Start real capital at **≤ $250k**, scale toward the $3M cap only after 3 further live months
  clearing the same bar.

**KILL CRITERIA:** if paper Sharpe < 0 over any 8-week window after the crash filter, OR realized
slippage > 20 bps, OR live-vs-backtest correlation < 0.3 — **do not deploy / pull capital.**

---

## 9. Honest Bottom Line

The prior study's headline (Sharpe ~1.1, 37%/yr, $10-50M) does **not** survive a deployable lens:
- The 14d Sharpe is a **curve-fit spike**, not a plateau.
- The full-universe edge **rides untradeable thin alts**; on the tradeable 6-coin set the headline
  config is **negative recently**.
- **Capacity is ~$3-6M, not $10-50M.**
- Funding is a **~0.5%/yr wash**, not a boost.
- A **surviving config exists (6-coin, 10d, vol-target + crash filter, Sharpe ~0.5-0.7, ann
  ~13-22%, maxDD ~22%)** — but the 10d choice is hindsight, so the honest forward number is
  **Sharpe ~0.3-0.6 / ann ~8-18% / maxDD ~25-35%**, and it must be **paper-validated for 3-6
  months against the bar above before risking real capital.** This is a small, fragile sleeve —
  not the headline edge.

### Files
- `momdeep_fetch.py` — OKX funding-rate-history + open-interest + liquidity fetcher
- `momdeep_analysis.py` — robustness surface, funding netting, crash/overlay, capacity engine
- `momdeep_universe.py` — deployable-universe sensitivity + recommended-config validation
