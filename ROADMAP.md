# ROADMAP — ranked by expected P&L payoff

Honest framing that sets the ranking: the edge is **real but tiny and fill-rate-bound**,
and we proved cleverer *fill selection* does not help (Tier 1 in `FINDINGS.md`: gating and
markout-toxicity both retired; the cap + 2-sided structure already neutralizes the adverse
selection). So the alpha from here is NOT a smarter signal. It is:
  (a) **hedge** so we can safely quote more size,
  (b) **stack more revenue streams** onto the same quotes, and
  (c) **win more of the fills we already want**.

Status legend: ✅ done · 🔵 in flight · ⬜ not started.

---

## Tier 1 — new revenue / alpha (build next)

### 1. Delta-hedge residual inventory with a BTC perp ⬜  **(highest leverage)**
The structural unlock. Does three things at once:
- converts "hold leftover to resolution and pray" into a **hedged** book;
- lets us **raise the inventory cap** → more captured volume → directly more P&L (edge is
  per-share, so volume *is* the P&L);
- it's the **correct fix for the extreme-edge / near-expiry corner** where adverse selection
  actually bit (Tier 1 decile-0): *take* those fills and hedge them, don't refuse them.
This is the advantage an election-market maker can't have and we can — our event is a
function of a **tradable underlying** (spot/perp BTC). Hedge ratio = ∂(payout)/∂S; for a
window the position's BTC-delta is ≈ Σ inventory · ∂fair_token/∂S (use `fairvalue.fair_up`'s
derivative). Hedge venue is a perp (Binance/Bybit/Hyperliquid/dYdX) on the user's infra.
**Build:** `hedger.py` — net BTC-delta of the Polymarket book → target perp position →
rebalance with hysteresis (don't churn perp fees). Backtest the hedge P&L against `btc.npz`
to confirm it cuts window-P&L variance enough to justify a higher cap; then size up cap.
*Refs:* Avellaneda–Stoikov (inventory risk); standard options delta-hedging.

### 2. Liquidity Rewards stream, gated by our own regime map ⬜
Separate revenue from the maker rebate: Polymarket pays **daily** for resting near mid
**whether or not you fill** (two-sided, quadratic scoring). We already do the qualifying
behavior — we just need to (i) read each market's reward config programmatically and (ii)
optimize placement to the score. The sharp part comes straight from our finding: **farm
rewards tight-to-mid in the benign mid-window mean-reverting regime** (those fills settle
positive) and **pull/widen in the near-expiry toxic corner**. Our empirical regime split
*is* the map for when reward-farming is free money vs. a trap.
**Build:** read rewards config (CLOB `/markets` / `/rewards` fields: min size, max spread
from mid, rates); `rewards.py` to score candidate placements and bias `desired_quotes`
toward the scoring band when benign. Log earned rewards as a separate P&L source (feeds #11).

### 3. Continuous sizing f(fair_edge, tau), with the tail correction ⬜
We proved "lean, don't chop" (k=2 beat every gate) and that the signal is weakly
right-directional (corr +0.023). Use it as **one continuous size map** — bigger in
mid-window moderate-edge, smaller in extreme-edge / near-expiry — instead of flat k=2 or a
special-cased corner. Low risk, partially validated, **no n-tax**.
**Build:** size multiplier `w(fair_edge, tau)` in `live_trader.place` (and a backtest in
`fv_analysis` style on per-window Sharpe). Folds naturally on top of #1 (hedge the size).

### 4. Predictive repricing 🔵  *(in flight — `live_trader.py` + `fvfeed.py`)*
The one surviving alpha lever the backtest **structurally cannot score** (fill-tape replay
has no counterfactual cancels). Already wired with the instrumentation that makes the live
pilot interpretable: cancel-sent vs cancel-confirmed (`time_to_cancel`), taker-hit-old-quote,
queue-surrendered, avoided-fill resolution markout, clamp-binds (`reprice_log.jsonl`).
**Remaining:** run the live pilot; read `time_to_cancel` and queue-surrendered, not P&L, as
the verdict (sound-but-slow → buy latency; clamp binds constantly → calibration finding).
*Ref:* Cartea & Sánchez-Betancourt, *shadow price of latency*.

---

## Tier 2 — scale the captured volume (volume is the P&L)

### 5. Multi-market across correlated crypto, with portfolio-level delta ⬜
BTC 5m + ETH/SOL/XRP 15m (we already have `ETHUSDT/SOLUSDT/XRPUSDT.npz`). Each market is an
independent rebate + rewards stream → multiplies P&L. **Only safe once #1 exists**: these
markets are ≈ one risk factor, so "neutral in each" can be a large correlated bet overall —
aggregate delta and hedge at the **portfolio** level (one perp book nets them all).
**Build:** shared WS/OMS, one portfolio delta → one hedge target (extends #1).

### 6. Queue-reactive fill simulator ⬜  *(the remaining lie in the backtest)*
Our backtest's fill assumption (fill-at-quote / fill-on-trade-through) is the last
unvalidated piece. A calibrated queue-reactive model gives **fill probability as a function
of queue depth**, turning "join vs. improve-by-a-tick" into an EV decision and giving an
honest sim to test everything above (and, later, an RL policy) against.
*Ref:* Huang, Lehalle & Rosenbaum, *queue-reactive model*. **Build:** `queue_sim.py`
calibrated on the L2 `book`/`price_change` archive we already pulled.

### 7. Price the latency; place AND cancel ⬜
Measure marginal P&L per millisecond (shadow-price-of-latency) from the #4 pilot logs; spend
up to that, not past it. **Cancel latency matters as much as placement latency** — it's the
adverse-selection defense in exactly the corner we found toxic. (Instrumentation already in
`reprice_log.jsonl`; this is the analysis + the colo/cancel-path decision.)

---

## Tier 3 — protect the tiny edge from flipping negative

### 8. VPIN / flow-toxicity trigger ⬜
Wire Up/Down volume-imbalance toxicity into widen-or-pull and the kill-switch; it spikes
*before* the damage and is most valuable in the near-expiry corner. *Ref:* Easley, López de
Prado & O'Hara, VPIN. (We log per-side flow already; this acts on it at the regime boundary
only — not as a global fill filter, which we proved hurts.)

### 9. Vol- and tau-aware spreads in logit space ⬜
Replace any fixed spread with width = f(belief-vol σ_b, time-to-resolution), symmetric in
**logit**, widening hard near at-the-money expiry where the curve is vertical. The
A&S-in-logit form for a prediction-market kernel.

### 10. Continuous inventory skew (smooth reservation price), not the binary 25% cap ⬜
**Caution:** we found the cap + 2-sided structure is already neutralizing adverse selection,
so it is doing real work — the upgrade is to make it a smooth A&S reservation-price skew,
**not** to loosen it. Validate it doesn't widen the residual the cap currently bounds.

### 11. P&L attribution by source ⬜  *(the meta-tool)*
Decompose every cent into spread / maker rebate / liquidity rewards / adverse selection /
inventory carry / hedge P&L, at multiple markout horizons. On a strategy this thin, this is
how we know which lever pays and which bleeds — it tells us where to spend effort next.
**Build:** `attribution.py` over the audit logs (+ #1 hedge P&L + #2 rewards).

---

## Frontier (later, once #6 exists)
- **RL quoting policy** trained against the queue-reactive sim.
- **Self-impact / performativity check**: in a thin 15-min book our own quotes move the
  price; a price-taker assumption will mislead us. Measure own-quote market impact.

---

## If picking two to start: **#1 and #2.**
The delta-hedge raises safe size and salvages the toxic corner; liquidity rewards add a
revenue stream to quotes we already post. Together that's more incremental P&L than any
signal refinement, and **neither depends on winning the latency race** (#4/#7) that is still
unproven. #4 keeps progressing in parallel because only the live pilot can score it.

**Scope caveat carried throughout:** everything is validated on **BTC 15m, one OOS split**.
A good result on any item is "live-plausible on this market," not "generalizes."

---

## Update log — post-testing status (results overlay; see FINDINGS.md)

- **#1 Delta-hedge perp — TESTED → RETIRED.** On the deployed skewed book the frictionless
  hedge raises Sharpe via a MEAN effect (+~$7/win) with std UNCHANGED → within-window variance
  is non-directional, unhedgeable. Practical hedge net-destructive at every cap/τ_freeze (binary
  gamma churn spread through the window, not tail-concentrated; perp fees ~66× the prize). Skew
  already neutralizes delta for free. `hedge_sim.py`. **Do not build the hedger.**
- **#2 Liquidity rewards — TESTED → $0 on our market.** BTC 15m `rates:null` (unfunded);
  funded markets are politics/longshots ($100–1000/day pools, ~$2/day for a $200 LP, bearing
  resolution risk). `rewards.py` reader+screener auto-detects if BTC turns on. **#2 redirects to:
  SCALE THE CAP (validated) + MULTI-MARKET (#5).**
- **Raise the cap — ENDORSED, moderately.** Scales edge (75% of windows improve; jackknife
  Sharpe rises dropping the best 5), with a bounded terminal-move tail in the incremental gain.
  Move toward cap=100–200, not 400. `cap_tail.py`.
- **#3 Continuous sizing f(fair_edge,τ) — still open**, but tempered: the signal is the same
  weak `fair_edge` (corr ~0.02–0.06); expect a marginal lever, not a major one.
- **#4 Predictive repricing — DOWNGRADED to a measurement, not a bet.** The +$7/win drift is
  NOT quote-time predictable (`drift_predict.py`: OLS R²=0.0035, BTC momentum corr 0.0004), so
  #4 cannot pre-position; only the latency-race channel survives, ceiling ≤$2k total, scoreable
  solely by the live `reprice_log`. Keep the instrumented scaffold; do not over-invest.

**Net:** the two highest-ranked new-revenue ideas (#1, #2) do not apply to THIS market at THIS
scale. The endorsed path is **scale the validated cap + go multi-market (#5)** — fill-volume,
not new signals or hedges, is where the P&L is. Everything still scoped to BTC 15m, one OOS split.
