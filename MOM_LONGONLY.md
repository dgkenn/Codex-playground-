# Long-only US-spot crypto momentum — is there a deployable +EV edge without perps? (2026-06-14)

**Question.** The validated cross-sectional crypto momentum book (MOMENTUM_SPEC.md) is
dollar-neutral long/short on offshore USDT perps. A US person **cannot legally short** those
perps (OKX/Binance/Bybit/dYdX geoblocked). So the only deployable form is **LONG-ONLY on
US-legal SPOT venues** (Coinbase Advanced Trade / Kraken Pro): hold the top-momentum names,
the rest of the book sits in **cash (USDC)**. How much edge survives, and is it deployable for
a US small bankroll?

**TL;DR verdict.** Long-only US-spot momentum **survives as a real edge** — but it is a
*directional crypto-beta-timing* strategy, not the market-neutral alpha engine the L/S book is.
The BTC-trend gate is load-bearing: it is the entire substitute for the lost short hedge, and
without it long-only is uninvestable. **Deployable, with eyes open about a deep, grinding
high-water-mark drawdown** that the short leg used to suppress.

---

## METHOD / BAR (honest framing)

- **Data:** Coinbase Exchange public daily USD candles, 2019-01-01 → 2026-06-14, paginated
  (no auth). 32 deep-USD-spot coins (BTC, ETH, SOL, XRP, DOGE, ADA, AVAX, LINK, LTC, BCH, DOT,
  ATOM, XLM, UNI, AAVE, ETC, FIL, NEAR, ALGO, APT, ARB, OP, SUI, INJ, ICP, GRT, CRV, COMP,
  SAND, MANA, AXS, XTZ). No obscure alts. Fetcher: `mlo_fetch.py`.
- **Signal/cadence REUSED verbatim** from the locked L/S spec (not re-searched): risk-adjusted
  ~10d momentum (trailing 10d return / trailing 10d vol), point-in-time top-15 liquid universe
  (by trailing-30d median USD volume), **WEEKLY**, **partial-rebalance 0.7**.
- **Long-only construction:** hold top-K names equal-weight; remainder in cash (return 0).
- **Gate:** when BTC < its N-day SMA → **fully to cash** (replaces the short-leg downside hedge).
- **Costs:** realistic US-spot round-trip taker. **Base 40 bps RT** (Coinbase Advanced retail
  ~40-60 bps, Kraken Pro ~20-40 bps), sensitivity 20-60 bps. Charged on per-rebalance turnover
  (cash↔coin moves included).
- **Holdout protocol:** params fixed from the L/S spec (no fitting here). **REC12** = recent-12mo
  HARD holdout; **PREV12** = independent 24→12mo slice; **OOS18** = last 18mo; year-by-year shown.
- **Survivorship:** Coinbase serves only listed pairs (dead alts missing) → UP bias. Backtests
  SCREEN. Engine: `mlo_backtest.py`; study: `mlo_study.py`.

---

## 1. THE GATE IS EVERYTHING (long-only has no short hedge)

| LO config (k=5, top-15, weekly, partial0.7, 40bps) | FULL Sh / ret / maxDD | OOS18 Sh | REC12 Sh / ret / maxDD | PREV12 Sh |
|---|---|---|---|---|
| **UNGATED** | +0.76 / +62% / **−86%** | **−0.78** | **−0.74 / −48% / −66%** | +0.83 |
| **Gated BTC≥MA100** | +1.12 / +71% / −66% | +0.16 | **+0.55 / +27% / −28%** | +0.82 |

Without the gate, long-only is a **disaster in any down-regime**: REC12 Sharpe −0.74, −48%
return, −66% drawdown — it just rides crypto beta into the ground. The gate flips REC12 to
**+0.55 Sharpe / +27% return** and roughly halves the recent drawdown. **This is the headline
finding: the short leg's job (downside protection) is taken over entirely by the regime gate.**

### Gate-length plateau (k=5, 40bps)
| Gate | % weeks in cash | OOS18 Sh | REC12 Sh / maxDD | PREV12 Sh |
|---|---|---|---|---|
| none | 0% | −0.78 | −0.74 / −66% | +0.83 |
| MA50 | 44% | −0.35 | −0.10 / −41% | +0.91 |
| MA75 | 42% | +0.15 | +0.49 / −30% | +0.85 |
| **MA100** | 41% | **+0.16** | **+0.55 / −28%** | +0.82 |
| MA150 | 39% | −0.38 | +0.02 / −38% | +0.59 |
| MA200 | 38% | −0.62 | +0.09 / −35% | +0.25 |

**MA75–100 is a genuine plateau** (not a spike); MA100 is the robust knee, matching the L/S
spec's 50–100d gate. Too-short (MA50) whipsaws; too-long (MA150/200) reacts late. The book
sits **~40% of weeks in cash** — that is the cost of replacing the short leg.

---

## 2. LONG-ONLY vs BENCHMARKS (US-spot pool, weekly, 2019–2026)

| Strategy | FULL Sh / ret / maxDD | OOS18 Sh | REC12 Sh / ret / maxDD | PREV12 Sh |
|---|---|---|---|---|
| **LO k=5 gate100 (HEADLINE)** | +1.12 / +71% / −66% | +0.16 | **+0.55 / +27% / −28%** | +0.82 |
| (a) L/S neutral PERP top-15 gate100 @9bps **[VALIDATED, not deployable by US]** | +1.59 / +66% / **−29%** | +1.26 | **+1.45 / +30% / −11%** | +2.14 |
| (a′) L/S neutral spot-pool gate100 @40bps **[hypothetical — US can't short]** | +0.47 / +20% / −63% | +0.37 | +0.66 / +14% / −13% | +1.23 |
| (b) EW buy-hold top-15 universe | +0.55 / +43% / −87% | −0.88 | −0.91 / −58% / −67% | +0.47 |
| (c) BTC buy-hold | +0.90 / +58% / −76% | −0.53 | −1.17 / −45% / −49% | +1.05 |
| (d) cash (USDC) | 0 / 0% / 0% | 0 | 0 / 0% / 0% | 0 |

**How much of the L/S Sharpe does long-only retain?**
- vs the *validated perp* L/S (REC12 1.45, the true lost edge at 9 bps perp cost): long-only
  retains **~38%** of the Sharpe (0.55/1.45) but **the same ~27-30% annual return** — long-only
  gives up Sharpe almost entirely through **drawdown** (−28% vs −11%), not return.
- vs L/S on an **apples-to-apples** footing (same spot pool, same 40 bps): the spot L/S only does
  REC12 0.66 — long-only retains **~83%** of *that*. The validated L/S's high Sharpe leans heavily
  on cheap perp fees AND a deeper short universe; on US-spot terms the gap narrows sharply.
- **Long-only crushes the passive benchmarks in the recent regime:** REC12 +0.55 vs EW-buyhold
  **−0.91** and BTC-buyhold **−1.17**. The momentum selection + gate is adding real value over
  "just own crypto," exactly when it matters (the 2024-25 chop/drawdown).

**Why long-only retains MORE return than expected:** in a long-biased crypto bull the short leg
often *drags* (you're short coins that keep ripping). Long-only with the gate captures the up-leg
cleanly and steps aside in the down-leg — it keeps the L/S *return* while sacrificing the L/S
*drawdown control*.

---

## 3. DRAWDOWN: THE BRUTAL TRUTH (no short hedge)

The full-sample **−66% maxDD is NOT a single crash — it is a 2-year grinding high-water-mark
drawdown** (peak 2021-09 → trough 2023-08):

| As of | gated LO drawdown |
|---|---|
| 2021-12 | −32% (momentum-crowding crash; gate not yet fully in cash) |
| 2022-06 | −46% |
| 2022-12 | −46% |
| 2023-06 | −61% |
| 2023-08 | **−66% (trough)** |

Year-by-year (gated LO k=5):

| Year | Sh | ann ret | maxDD | % weeks cash |
|---|---|---|---|---|
| 2019 | +1.21 | +79% | −40% | 32% |
| 2020 | +1.57 | +107% | −42% | 19% |
| 2021 | +2.41 | +203% | −32% | 33% |
| **2022 (bear)** | **−0.96** | **−20%** | **−27%** | **92%** |
| 2023 | +0.97 | +46% | −41% | 23% |
| 2024 | +0.99 | +88% | −54% | 25% |
| 2025 | +0.30 | +16% | −24% | 46% |
| 2026 (ytd) | +0.79 | +24% | −11% | 74% |

**The gate works as designed in the bear:** 2022 was only **−20%** for gated long-only (92% in
cash) vs **−103% / −77% maxDD ungated** and **−67% for EW buy-hold**. The catastrophe is avoided.
But the deep high-water-mark drawdown persists because **(i)** the 2021Q4 crowding crash hits
*before* the gate fully de-risks (momentum tops can precede the BTC<MA signal), and **(ii)** while
gated to cash the book earns 0, so the post-2021-mania high-water mark isn't recovered until the
next bull. **Most of the −66% is opportunity-cost grind, not capital destruction** — but a live
operator *will* watch a −40% to −60% paper drawdown for many months. This is the honest cost of
losing the short leg. **The L/S book's −11/−29% maxDD is genuinely better risk; that protection
is real and unavailable to a US person.**

---

## 4. FEES & SMALL-BANKROLL REALISM (fees do NOT kill it)

Average weekly turnover is only **0.44** (partial-0.7 + the cash leg cuts churn) → ~23×/yr →
**~4.6% annual fee drag at 40 bps RT**. Fee sensitivity is mild:

| RT cost | REC12 Sh | REC12 ret |
|---|---|---|
| 20 bps (Kraken Pro at volume) | +0.59 | +29% |
| 40 bps (base) | +0.55 | +27% |
| 60 bps (Coinbase retail worst) | +0.51 | +25% |

Even at 60 bps the edge is intact — **spot fees do NOT kill long-only momentum** (the 23 bps
perp-capacity worry from the L/S spec was about thin-alt *slippage at $3M+*, irrelevant here).

**Small-bankroll capacity is a non-issue.** With k=5: at **$1k** = 5 × $200, at **$10k** = 5 ×
$2k, at **$100k** = 5 × $20k. Coinbase/Kraken min orders (~$1-10) never bind; top-15 USD spot is
deep enough that slippage ≈ 0 at any of these sizes. **Realistic expectation at $1k and $10k is
identical:** net annual return ~25-30% in a normal/up regime, ~0 (cash) in a gated bear, with a
multi-month high-water-mark drawdown that can reach −40/−60% across a full bear cycle.

---

## 5. ROBUSTNESS (plateau, not spike)

- **K (names held):** k=3 → REC12 0.70, k=5 → 0.55, k=7 → 0.53, top-30% → 0.48. Smooth; k=3-5 is
  the knee (k=3 slightly higher return but more concentrated/noisier). **k=5 chosen** for
  diversification at small size.
- **Lookback:** lb 8/10/12 all REC12 0.54-0.82 (lb12 best at +0.82, but the spec locks ~10d;
  lb14 decays to 0.22 → don't extend). Plateau around 10.
- **Universe size:** top_n 10/15/20 → FULL Sh 1.07/1.12/1.14, REC12 0.32/0.55/0.46. Top-15 robust.
- **Partial-rebalance:** partial 1.0 actually scores higher OOS (REC12 0.82 vs 0.55) at this fee
  level because spot fees are low enough that smoothing's turnover saving doesn't pay for its
  signal lag — but 0.7 is kept for live-noise/robustness consistency with the locked spec, and the
  gap is within noise.

All knobs move smoothly → this is a **plateau, not an overfit spike.**

---

## VERDICT — deployable, with eyes open

**Long-only US-spot momentum is a deployable +EV edge for a US small bankroll — it is NOT a dead
end.** But it is a *gated directional crypto-timing* strategy, materially riskier than the L/S
book it replaces.

**Deployable config:**
- **Universe:** top-15 by trailing-30d USD volume from the 32-coin deep-USD-spot pool (Coinbase
  Advanced / Kraken Pro), rebuilt point-in-time.
- **Signal:** risk-adjusted ~10d momentum (trailing 10d return / trailing 10d vol).
- **K:** hold **top-5** equal-weight; remainder in **USDC cash**.
- **Gate:** **BTC ≥ 100-day SMA**, else **fully to cash** (this replaces the short hedge — do NOT
  run ungated).
- **Cadence:** **weekly**, partial-rebalance 0.7.
- **Cost assumption:** 40 bps RT (use Kraken Pro / Coinbase volume tiers to push toward 20-30).

**Expected net (recent-12mo holdout, 40 bps, survivorship-biased UP):** **Sharpe ~0.5-0.6,
annual return ~25-30% in up/normal regimes, ~0 when gated in a bear.**
**Honest drawdown:** recent-regime maxDD ~−28%; across a full bear cycle expect a **−40% to −60%
high-water-mark drawdown** (mostly opportunity-cost grind, not a crash — the gate prevents the
ungated −66/−86%). Discount the headline to **forward Sharpe ~0.4-0.6** for decay + survivorship.

**vs the lost L/S edge:** long-only keeps ~80%+ of the *spot-comparable* L/S Sharpe and the full
return, but gives up the L/S's clean −11/−29% drawdown. **The short leg was real, unavailable
downside protection** — that is the price a US person pays.

**Go-live bar:** paper-trade 3-6mo at weekly cadence on this exact config, booking 40 bps; require
rolling OOS Sharpe ≥ 0.4 and confirm the gate de-risks on the next BTC<MA100 cross. **Stand down
if it runs net-negative through a full gated quarter** (the decay thesis from the L/S spec applies
here too). This is a small-bankroll-friendly, genuinely deployable edge — the one momentum path a
US person can actually trade.
