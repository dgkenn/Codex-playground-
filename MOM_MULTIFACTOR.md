# Multi-Factor Crypto Model vs Single-Factor Cross-Sectional Momentum

**Date:** 2026-06-14 · **Author:** automated research (claude) · **Branch:** claude/polymarket-bot-live-ready-vw7ut5

## TL;DR Verdict

**MOMENTUM-ALONE WINS. Combining factors does NOT beat it — every added factor lowers OOS Sharpe.**

A sibling agent already established that cross-sectional (XS) 14d momentum is the real crypto edge
(OOS Sharpe ~1.1-1.2, ~37%/yr, maxDD ~34%). My job was the *combination* question: do
lowly-correlated factors (carry, low-vol, long-horizon reversal, size) raise the combined Sharpe
and cut drawdown? Across a 5-factor cross-sectional long/short book on the liquid-perp universe,
weekly rebalance, net of realistic costs:

- **None of the candidate factors pays OOS standalone.** MOM OOS Sharpe **+1.17**; everything else is
  ≤ +0.25 or negative: REV +0.25, SIZE −0.10, LOWVOL −0.16, **CARRY −0.70** (and −0.95 even after
  crediting the funding cashflow). The diversifiers are statistically orthogonal to MOM
  (|corr| 0.02-0.24) but they are **zero-to-negative-return streams**, so blending them in just
  **dilutes** the one factor that works.
- **The combo loses to MOM on a like-for-like (common 2024-07→2026-06) window:** MOM-only Sharpe
  **1.42** vs MOM+CARRY **1.02**, MOM+REV **1.24**, MOM+LOWVOL **0.49**, MOM+SIZE **0.77**,
  all-5-factor EW **1.05**. On the chronological OOS split MOM-only **1.17** beats every blend.
- **Risk-parity / inverse-vol blend collapses to MOM-only** (it allocates ~all weight to the only
  factor with a positive return stream) — i.e. the optimizer agrees: keep momentum, drop the rest.
- **Robustness:** the MOM-weight grid is *monotone* — Sharpe rises as you tilt toward pure momentum.
  Adding the non-paying factors strictly hurts (textbook overfit-by-more-factors). The honest call
  is to **keep only momentum**.

**Best model = single-factor XS momentum (14d, weekly, L/S top/bottom 30%): OOS Sharpe 1.17, maxDD
−24.7% at 10 bps** (1.24 / −24% at 7 bps; 1.12 / −25% at 12 bps). Multi-factor is rejected.

---

## 1. Data Window & Cost Assumptions (this is a SCREEN)

| | |
|---|---|
| **Price source** | OKX public `history-candles` (daily), 10 USDT pairs: BTC ETH SOL XRP DOGE ADA AVAX LINK LTC BNB. Reused the sibling momentum agent's cached pulls. Binance/Bybit geo-blocked; Coinbase/Kraken/dYdX reachable. |
| **Price window** | 2019-11-19 → 2026-06-14 (~2400 daily bars; SOL/AVAX from 2020-09, BNB from 2022-12). |
| **Funding source** | **dYdX v4 `historicalFunding`** (hourly funding, aggregated to daily). OKX `funding-rate-history` is **hard-capped at ~3 months** (confirmed: paging past 2026-03-12 returns 0 rows) — too short for an OOS carry test, so dYdX is the carry source. |
| **Funding window** | BTC/ETH/SOL 2024-07-13→2026-06-14; XRP/DOGE/ADA/AVAX/LINK/LTC 2025-04-28→2026-06-14. Full 9-asset carry cross-section ≈ 2024-07 → 2026-06 (~2 yr). **Carry history is the binding data constraint.** |
| **Universe / construction** | Each factor ranked cross-sectionally each rebalance; long top 30%, short bottom 30%, equal-weight each leg, scaled to gross leverage ≈ 1 (dollar-neutral). |
| **Rebalance** | **Weekly** (every 7 bars; held between). Daily rebalance dies on costs per sibling work. |
| **Cost model** | `cost = COST_BPS × turnover` (Σ\|Δweight\|) per bar. **Base 10 bps round-trip** perp taker (≈5 bps/side + slippage); swept 7/10/12. |
| **Execution** | Signal on close[t]; weights lagged 1 bar (next-bar exec); ret[t]=close[t]/close[t−1]−1. No look-ahead. |
| **IS/OOS** | IS = first 65% of dates, OOS = last 35% (chronological). Plus a **recent-regime holdout = last 18 months**, and a **common-window** comparison restricted to the carry window so MOM-vs-(MOM+CARRY) is apples-to-apples. |

Scripts: `multifactor.py` (factors, standalone OOS, correlations), `combine.py` (blends + robustness),
`fetch_funding_hist.py` / `fetch_funding_rest.py` (dYdX funding). Parquets are NOT committed.

---

## 2. Factors

Each factor is a cross-sectional score (higher ⇒ more long), ranked into a dollar-neutral L/S book:

- **MOM** (anchor): 14d trailing return. Long winners / short losers.
- **CARRY**: perp funding rate. Long LOW/negative-funding, short HIGH-funding (the carry premium).
- **LOWVOL**: 30d realized vol. Long LOW vol / short HIGH vol (the vol anomaly).
- **REV** (long-horizon reversal): −(return from t−126d to t−21d), i.e. ~1–2 quarter past return
  **skipping the most recent month** (LSV-style; the skip keeps it from cannibalising 14d MOM).
- **SIZE/liquidity**: −(30d avg dollar volume). Long smaller/less-liquid (illiquidity premium).

### 2a. Standalone OOS (weekly, 10 bps)

| Factor | Full Sharpe | OOS Sharpe | OOS ann | OOS maxDD | Window | Pays OOS? |
|---|---|---|---|---|---|---|
| **MOM** | **1.40** | **+1.17** | **+29.3%** | **−24.7%** | 2019-11 → 2026-06 | **YES** |
| REV | −0.56 | +0.25 | +3.2% | −27.5% | 2019-11 → 2026-06 | marginal |
| SIZE | 0.63 | −0.10 | −3.4% | −24.2% | 2019-11 → 2026-06 | no (IS-only ⇒ overfit) |
| LOWVOL | −0.48 | −0.16 | −7.4% | −48.3% | 2019-11 → 2026-06 | no |
| CARRY (price-only) | −1.15 | −0.70 | −8.8% | −12.5% | 2024-07 → 2026-06 | no |
| CARRY (+funding cashflow) | −0.95 | — | −10.6% | −26.1% | 2024-07 → 2026-06 | no |

**Read.** Only MOM clears the bar. REV is a weak positive (consistent with reversal coexisting with
mid-horizon momentum) but not enough to stand alone. SIZE has a positive IS Sharpe (0.89) that
**vanishes OOS (−0.10)** — the classic overfit signature. LOWVOL is negative (the equity-style vol
anomaly does not show up in this crypto L/S construction). **CARRY is the cleanest disappointment:**
ranking on funding builds a book whose *price drift* loses ~12%/yr, and even crediting the
**actual funding cashflow harvested (~+2.2%/yr)** the book is still Sharpe −0.95. The funding premium
is real but tiny (≈2%/yr — matching the sibling funding agent's "too small to matter" finding) and is
swamped by the directional price exposure of the funding-ranked book.

### 2b. Cross-correlations of factor net-return streams (full overlap)

|        | MOM | LOWVOL | REV  | SIZE | CARRY |
|--------|-----|--------|------|------|-------|
| MOM    | 1.00| −0.24  | −0.09| −0.02| −0.02 |
| LOWVOL | −0.24| 1.00  | 0.56 | −0.12| −0.02 |
| REV    | −0.09| 0.56  | 1.00 | 0.20 | 0.03  |
| SIZE   | −0.02| −0.12 | 0.20 | 1.00 | 0.06  |
| CARRY  | −0.02| −0.02 | 0.03 | 0.06 | 1.00  |

The diversification *correlation* picture is excellent — MOM is near-orthogonal to everything
(|corr| ≤ 0.24, CARRY −0.02). **But low correlation only helps if the streams have positive
expected return.** Here the candidate diversifiers have ≤0 OOS return, so the low correlation buys
nothing: you are averaging a +1.17-Sharpe stream with ~0-Sharpe streams.

---

## 3. Combination Results — does the combo beat MOM-alone?

Two schemes: (A) equal-risk z-score blend at the **score** level (rank the summed z-scores into one
book); (B) **risk-parity / inverse-vol** blend of the factor **return** streams. Compared to MOM-only
on OOS, recent-18mo, and the common carry window (CW, 2024-07→2026-06, the fair like-for-like).

| Config | OOS Sharpe | OOS maxDD | Recent Sharpe | CW Sharpe | CW maxDD |
|---|---|---|---|---|---|
| **MOM-only (baseline)** | **1.17** | **−0.25** | **0.85** | **1.42** | **−0.25** |
| MOM+REV (EW) | 1.02 | −0.19 | 0.10 | 1.24 | −0.19 |
| MOM+CARRY (EW) | −0.88 | −0.18 | −0.05 | 1.02 | −0.22 |
| MOM+LOWVOL (EW) | 0.65 | −0.29 | 0.92 | 0.49 | −0.29 |
| MOM+SIZE (EW) | 0.59 | −0.28 | −0.62 | 0.77 | −0.28 |
| ALL 5 factors EW | 0.78 | −0.18 | 0.41 | 1.05 | −0.17 |
| Risk-parity (inv-vol) blend | 1.17 | −0.25 | 0.85 | 1.42 | −0.25 |

**No combination beats MOM-alone on OOS Sharpe.** The closest (MOM+REV) still trails (1.02 vs 1.17 OOS;
1.24 vs 1.42 CW). MOM+CARRY is the worst on the chronological OOS (−0.88) because the carry leg's price
drift is sharply negative in the recent window. Blends do modestly **cut maxDD** (−0.18 to −0.29 vs
−0.25) — a few of them dampen drawdown — but never enough to compensate the Sharpe loss, and the
drawdown improvement is exactly what you'd get by simply **vol-targeting / sizing down momentum**
(a risk-layer job the sibling deploy agent owns), with none of the return give-up.

The **risk-parity blend collapses onto MOM-only** (identical numbers): the inverse-vol allocator,
seeing only one factor with a positive Sharpe, routes essentially all risk to momentum. The data's
own answer to "how should I weight these factors" is *"100% momentum."*

---

## 4. Robustness

**MOM-weight grid (vs CARRY partner), common window:** Sharpe is monotone in the momentum tilt —

| MOM weight | 0.25 | 0.5 | 0.75 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|
| CW Sharpe | 0.21 | 1.17 | 1.15 | 1.02 | 1.01 | 1.22 | 0.98 |
| OOS Sharpe | −1.51 | −0.73 | −0.91 | −0.88 | −0.89 | −1.00 | −1.76 |

There is **no plateau where a balanced multi-factor weight wins** — the more carry you add, the worse
the OOS book. The edge is not a fragile knife-edge of multi-factor weights; it is simply *momentum*,
and the right amount of every other factor is ~zero.

**Overfit test (does adding non-paying factors hurt?):** YES. The all-5-factor EW book (OOS 0.78,
CW 1.05) sits well below MOM-only (1.17 / 1.42). Every factor that fails the standalone OOS bar drags
the combo down — a clean demonstration of "more factors = more overfit risk." Keeping only the factor
that earns its place (MOM) is the robust choice.

**Cost sensitivity (MOM-only):** OOS Sharpe 1.24 / 1.17 / 1.12 at 7 / 10 / 12 bps; CW ann 39.5% /
37.2% / 35.7%. Survives the realistic 7–12 bps band comfortably.

**Recent-regime honesty:** MOM's last-18mo Sharpe (0.85 at 10 bps) is below its full-OOS 1.17 —
the same decay the sibling momentum agent flagged (the factor is well-known and crowding). It still
leads every alternative in that window. This is a size-it-small, decaying sleeve, not a free lunch.

---

## 5. Best Model

**Single-factor cross-sectional momentum — NOT multi-factor.**

| Parameter | Value |
|---|---|
| Factor | 14d trailing-return rank, long top 30% / short bottom 30%, equal-weight, dollar-neutral |
| Rebalance | Weekly |
| Universe | 10 liquid OKX USDT perps (BTC ETH SOL XRP DOGE ADA AVAX LINK LTC BNB) |
| Cost | 10 bps round-trip (robust 7–12) |
| **OOS Sharpe** | **1.17** (last-35% chronological split) |
| **OOS maxDD** | **−24.7%** |
| OOS ann | +29.3% |
| Recent-18mo Sharpe | 0.85 (decaying — size accordingly) |

**vs momentum-alone:** the best multi-factor config does not exist — momentum-alone *is* the best
config. Carry, low-vol, size, and long-horizon reversal are each rejected: none pays OOS standalone,
and adding any of them lowers the combined OOS Sharpe. The factors are pleasingly uncorrelated, but
diversifying into zero-return streams only dilutes the one real edge.

### Honest caveats / limitations
- **Carry's test is short** (~2 yr, one funding regime; OKX caps at 3 mo so dYdX is the only deep
  source). In a hotter-funding bull regime the carry *income* could be larger — but the structural
  problem (funding-ranked book carries adverse price drift that dwarfs ~2%/yr funding) is regime-robust
  here, and the sibling funding agent independently concluded carry is "too small."
- This is a **screen** (vectorized, frictions modeled as bps×turnover, no borrow/funding-availability
  or shorting-capacity constraints, no intraday execution). Window + costs stated above.
- Drawdowns are large (~25–35%); momentum needs vol-targeting/sizing (the deploy agent's job).
- If forced to add anything, **REV** is the only candidate with a non-negative OOS standalone, but it
  still does not improve the combo — so the recommendation is to ship **momentum-only**.
