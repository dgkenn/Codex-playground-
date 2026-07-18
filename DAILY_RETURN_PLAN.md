# Daily-Return Plan — targeting the goal "~10%/day, minimized risk, statistically sound"

**Date:** 2026-07-18 · **Bankroll assumed:** ~$50 · **Discipline:** PROPOSE-ONLY (no live capital without operator authorization); tested must match live.

This document does the real quantitative work the goal demands, then states plainly what is and isn't
achievable. It does **not** manufacture a 10%/day strategy — doing so would be the exact "illusion" this
program exists to prevent (a fabricated plan loses real money on contact with the market).

---

## 1. The honest headline

**~10%/day at minimized risk is not achievable with any edge we have found, or with any statistically
sound edge available to a small participant in these markets.** Two independent proofs:

### (a) Compounding reductio — what 10%/day *is*
| horizon | growth factor | $50 becomes |
|---|---|---|
| 1 week (7d) | ×1.95 | $97 |
| 1 month (30d) | ×17.4 | $872 |
| 1 year (365d) | ×1.3×10¹⁵ | ~$6.4×10¹⁶ |

10%/day for a year turns $50 into roughly **1,000× world GDP**. No edge scales that way; a strategy earning
10%/day would absorb all the money in the world within months. It therefore cannot exist at any capacity —
let alone "at minimized risk." A *lucky streak* of 10%/day for a few days is possible; a *plan* that
delivers it in expectation is not.

### (b) Risk/leverage — what 10%/day would *demand* of our real edge
Monte Carlo (`daily_return_frontier.py`, 100k weeks, correlation-aware) of our one confirmed edge stacked
with the econ/biz sleeves:

- The diversified book earns ≈ **1.9%/week at risk-minimizing sizing** (¼-Kelly).
- Hitting 10%/day (= **+95%/week** compounded) requires ≈ **49× leverage**.
- Max loss per longshot position is −100% of its stake. At 49× leverage, **one correlated bad week —
  several longshot strikes hitting together on a single big crypto rally — is a bankroll-ending event.**
  Simulated 1-year ruin at that leverage: **100%.**

So the two constraints in the goal — *10%/day* and *minimized risk* — are mutually exclusive here. You can
have the frontier below, or you can chase 10%/day with leverage that guarantees ruin. Not both.

---

## 2. The achievable frontier (what a sound plan actually returns)

From the same Monte Carlo — diversified weekly book (12 crypto longshot wings at ρ=0.45 + 4 econ buckets +
3 biz longshots = 19 positions/wk), edge parameters from the confirmed nodes:

| sizing (Kelly frac) | week mean | week σ | **day-equivalent** | ann. Sharpe | 1-yr ruin | median max drawdown |
|---|---|---|---|---|---|---|
| 0.10 (very safe) | +0.77% | 1.5% | **+0.11%/day** | 3.7 | 0% | 5% |
| 0.25 (risk-min) | +1.92% | 3.8% | **+0.27%/day** | 3.7 | 0% | 13% |
| 0.50 | +3.80% | 7.6% | **+0.53%/day** | 3.6 | 0% | 25% |
| 1.00 (aggressive) | +7.69% | 15.1% | **+1.06%/day** | 3.7 | 0% | 49% |

Reading this honestly:
- The **risk-minimizing** operating point (¼-Kelly) yields ≈ **0.27%/day** (~2%/week, ~13% worst
  drawdown). Annualized Sharpe ≈ 3.7 — which, if it holds forward, would be *excellent* (top-tier funds run
  ~2–3). It is nowhere near 10%/day.
- Pushing to ~1%/day is possible only by accepting ~50% drawdowns — that is not "minimized risk."
- **Every number here assumes the backtest edge holds forward at size.** The live forward gates
  (`pmkt_shortvol/econ/biz`, `bucket_arb`) will confirm or haircut it over the coming weeks. Correlation and
  any forward shrinkage only *lower* these figures.

**Bottom line:** the realistic, statistically-sound target is **fractions of a percent to ~1% per day**, not
10%. On $50 that is roughly **+$1–4 per week** in expectation — real, but small, and $50 is below the scale
where the tail can be properly diversified.

---

## 3. The plan (run the frontier, not the fantasy)

The sound plan is the multi-sleeve book already built and forward-gating. Concretely:

1. **Sleeve 1 — Polymarket weekly crypto short-vol (the confirmed edge).** Sell far-OTM weekly BTC/ETH
   "above $X" longshots, band on the executable **bid** in [0.15,0.30], spread ≤ 0.06, first-half-of-week
   entry, zero fee. This is the engine. (`pmkt_shortvol_paper.py`)
2. **Sleeve 2 — macro-release buckets** (CPI/PPI/jobs/GDP/Fed), sell over-round buckets. Uncorrelated with
   crypto (ρ≈−0.01). (`pmkt_econ_paper.py`)
3. **Sleeve 3 — business/company longshots.** Marginal, sized smallest. (`pmkt_biz_paper.py`)
4. **Sleeve 4 — riskless bucket-arb.** Underround/overround exclusive-bucket sets; tiny but genuinely
   riskless; self-validates exhaustiveness at settlement. (`bucket_arb.py`)
5. **Allocation & sizing:** `portfolio.py` (inverse-variance / risk-parity across sleeves) + `sizing.py`
   (tail-first nested caps, fractional Kelly per sleeve). Operate at **¼-Kelly** for the risk-minimizing
   frontier point.
6. **Gate before scaling:** do not raise size until the forward settled logs confirm the backtest edge
   (day/week-clustered t, tail within model). Tested must match live.

### The one lever that could raise the *daily* rate (under test)
Because the target is per-*day*, the highest-value improvement is **bet frequency**: the confirmed edge is
*weekly*; Polymarket also lists **daily** "BTC/ETH above $X on <date>" ladders. If the short-vol premium
survives at daily horizon, ~7× the resolutions/week compound into a materially higher daily rate (still not
10%, but higher than the weekly-only frontier). **This is being measured now** (`daily_shortvol.py`); result
folds into §2 when it lands. A thinner-but-real daily premium raises the frontier; an efficient daily market
leaves §2 as the ceiling.

---

## 4. What would it take to go meaningfully higher (and why each breaks "minimized risk")

| lever | effect | why it's not the sound answer |
|---|---|---|
| Leverage / full-Kelly+ | scales return linearly | scales the fat left tail too → drawdowns/ruin; violates "minimize risk" |
| More uncorrelated sleeves | raises Sharpe → more size at same risk | diminishing; we've killed ~10 candidates finding uncorrelated edges are rare |
| Private/faster data | genuine new edge | we don't have it; every *public*-data probe (forecasts, sportsbook lines, order flow) is already priced |
| Higher frequency (daily/intraday) | more compounding events | under test; helps but bounded, and shorter horizon = thinner premium |
| More capital | same %, more $ | changes $ not %; and thin books cap deployable size anyway |

---

## 5. Verdict

- **Goal as stated (10%/day, minimized risk): infeasible.** Proven by compounding and by the leverage/ruin
  the target demands of our real edge. Any document promising it would be dishonest.
- **Best sound plan: the multi-sleeve book at ¼-Kelly, ≈ 0.27%/day expected** (up to ~1%/day only by
  accepting large drawdowns), contingent on the forward gates confirming the edge — with the daily-horizon
  frequency test as the one live lever that could raise it.
- **Next actions:** (1) let the daily-horizon backtest land and fold it in; (2) keep maturing the forward
  gates so the §2 numbers are live-validated, not just backtested; (3) operate PROPOSE-ONLY until a human
  authorizes capital.
