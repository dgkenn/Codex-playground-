# LIVE_DESIGN.md — the pilot's architecture (theory → `live_trader.py` spec)

The problem has changed shape. We're past "does the edge exist" — it's established as a **small,
non-directional, capacity-bound, multi-book liquidity edge**; prediction and hedging are dead
(see `FINDINGS.md`). So the relevant theory is no longer signal discovery — it's **multi-asset
quoting, online (not offline) parameter learning, and the dollar value of queue position**. And
it converges on the conclusion we reached empirically.

**The load-bearing meta-point:** three of the six components below — online κ-learning,
queue-position value, microprice repricing — **cannot be calibrated offline by construction**.
That is the formal statement of our recurring pain ("the backtest's fill assumption keeps
lying"). So this doc does not specify a #6 backtest. It specifies a pilot that **learns its
binding parameters live with bounded regret**, instead of fitting them offline and being wrong.

Status tags: ✅ built · ◐ partially built · ⬜ new for the live build.

---

## 1. Factor-model multi-asset quoting ⬜  (Bergault–Guéant; Bergault–Evangelista–Guéant–Vieira)
**Maps to:** our portfolio-cap finding — the crypto books are ~one factor (BTC-beta; that's what
√N and the ~1% residual correlation *mean*, `multimarket.py`).
**Spec:** do NOT run N independent A&S controllers (curse of dimensionality). Project inventory
onto the **factor (BTC-beta) space** and quote/cap on **factor inventory**, using the closed-form
multi-asset value-function approximation (greedy quoting). Add **size-dependent quotes** (a quote
curve per size, not one clip) — our adaptive-sizing lever in closed form. Compose with the
round-one **logit transform**: factor-level A&S quotes in **log-odds space** = the correct object
for a multi-book binary maker.
**Replaces in `live_trader.py`:** the per-token `desired_quotes`/skew → a single factor-inventory
controller emitting per-book, per-size quotes; the inventory cap → a **factor-inventory cap**
(the portfolio delta budget from `multimarket.py`).
**Online/offline:** structure offline; the factor loadings (betas) drift → re-estimate live.

## 2. Online no-regret learning of the fill parameters ⬜  (Abernethy–Kale; Market Making without Regret; log-regret ergodic A&S)
**Maps to:** "offline fill calibration keeps lying" — stated as a theorem. Other makers react to
our volume, so any offline κ (fill-intensity decay) is inaccurate.
**Spec:** the pilot must NOT run fixed params. Run a **regularized-MLE online learner for κ** that
updates from realized fills, using the offline estimate only as the **initial value**; ergodic
A&S gives **O(ln²T) regret**. Quotes are recomputed from the current κ̂ each step.
**Replaces:** static `--post`/spread/skew constants → a `KappaLearner` that ingests
(quote, distance-from-touch, filled?) tuples and outputs the current optimal half-spread/size.
**Online/offline:** **online by construction** — this is the reframe: the pilot is "deploy a thing
that *learns* κ," not "measure κ then deploy." Offline we can only seed the prior.

## 3. Queue-position valuation ⬜  (Moallemi–Yuan)
**Maps to:** the cancel-vs-hold tension (the whole `reprice_log` premise) — and it's **first-order**,
not a detail. Queue value can be the **same order as the half-spread**, which is essentially our
entire edge. Adverse selection **rises with queue position** → back-of-queue fills are the toxic
ones; front-of-queue fills are benign. That is our decile-0 / mean-reversion split **restated as
queue mechanics**.
**Spec:** the objective is **queue-position-weighted fill rate**, not raw fill rate. Value queue
position with the two-part model (static spread-vs-adverse-selection + dynamic cancellation
option). Every needless cancel pushes us toward the toxic end → the layer-don't-churn discipline
is now *quantified*, not just asserted.
**Replaces/extends:** `audit_report.py` fill-rate metric → **queue-weighted** capture; the kill/
reprice decisions weigh queue value lost vs adverse-selection avoided.
**Online/offline:** queue position is **live-only** (depth ahead at fill time); offline tape can't
see it. This is why raw-fill-rate backtests mislead.

## 4. Microprice repricing target ◐  (Stoikov)  — NOT the dead prediction lever
**Maps to:** the one surviving latency lever. **Read carefully:** we killed *window-direction*
forecasting (R²≈0, `drift_predict.py`). The **microprice is a different, much shorter-horizon
object** — the expected next-tick fair value given current **book imbalance**, NOT a forecast of
BTC. Repricing against the microprice (vs the stale mid) introduces an effect close to
**adverse-selection aversion** — precisely what the latency lever needs: don't rest at the mid the
book is about to leave; move to the imbalance-adjusted value so you're not the one left holding.
**Replaces in `live_trader.py`:** the reprice target (currently book mid / fair_up) → the
**microprice** computed from the live L2 imbalance. The `fvfeed`/predictive-pull scaffold and
`reprice_log` instrumentation stay (✅ built) — only the *target* changes to the microprice.
**Online/offline:** the microprice *weights* are estimated from the book's own short-horizon
transitions — **live**; offline they don't transfer across regimes.

## 5. Optimal cross-venue placement on effective rebate ⬜  (Cont–Kukanov)
**Maps to:** the thin-edge worry, made explicit — "small consistent limit-fill losses accumulate
into significant adverse-selection cost." Only relevant **if Kalshi becomes a second venue**
(retired as a *hedge*, see FINDINGS; possible as a *venue*, fee model differs, re-baseline first).
**Spec:** route size across venues on **effective rebate = gross rebate − expected adverse
selection**, not headline rebate; respect bounded per-venue execution capacity.
**Online/offline:** effective rebate needs live per-venue markout → live.

## 6. Market making with market impact at scale ⬜  (Barzykin–Bergault–Guéant)
**Maps to:** the ceiling on "raise the cap to the jackknife optimum." In a thin 15-min book **our
own size moves the price** (the performativity point) — an effect the offline cap sweep *cannot*
see (it replays a tape that didn't include our impact).
**Spec:** embed market impact into the optimal-quoting control to find the size beyond which
**self-impact eats the per-share edge** — the **real, impact-determined cap**, likely BELOW where
raw (or even jackknife) Sharpe peaks offline.
**Online/offline:** impact is measured live (own-quote → subsequent book move); offline is blind
to it. So the cap-frontier in `cap_tail.py` is an UPPER bound; the live impact curve sets the true
ceiling.

---

## What's already built vs new
- ✅ `reprice_log.jsonl` instrumentation (cancel-confirmed, queue-surrendered, taker-hit-old) —
  feeds #3 queue accounting and #4 microprice evaluation.
- ✅ `fvfeed.py` spot feed + safe degrade; ✅ `collateral.py` mint/merge primitive; ✅ layered
  post-only OMS (layer-don't-churn) — the chassis #1–#4 bolt onto.
- ◐ #4 microprice: the repricing *mechanism* exists; swap the *target* from mid→microprice.
- ⬜ #1 factor controller, #2 κ-learner, #3 queue-position P&L, #6 impact-cap — new live modules.

## The build order for the pilot (small, real money, your infra)
1. **Seed + deploy the κ-learner (#2)** on ONE book (BTC 15m), cap≈25–50, smallest size. The pilot
   *is* the learner converging — measure **queue-weighted capture (#3)**, not raw fill rate.
2. **Swap reprice target to the microprice (#4)**; read `reprice_log` for queue value lost vs
   adverse selection avoided (the ≤$2k-ceiling lever's live verdict).
3. **Add ETH 15m via the factor controller (#1)** — first live test of fill parity (the input √N
   rests on) and the portfolio factor-cap.
4. **Find the impact-cap (#6)** by raising size until own-quote impact bends the per-share edge —
   the true ceiling, below the offline frontier.
5. Cross-venue (#5) only if Kalshi is added and re-baselined.

**Everything here is online/live by design.** Offline work is complete; this spec exists so the
pilot deploys a *self-calibrating* controller, not fixed params the live tape would falsify.

### References
- Bergault & Guéant, *Size Matters for OTC Market Makers* (Math. Finance 2021)
- Bergault, Evangelista, Guéant & Vieira, *Closed-form Approximations in Multi-asset Market Making* (2021)
- Barzykin, Bergault & Guéant, *Algorithmic Market Making with Hedging and Market Impact* (Math. Finance 2023)
- Abernethy & Kale, *Adaptive Market Making via Online Learning* (NeurIPS 2013)
- *Market Making without Regret* (2024); *Logarithmic Regret in the Ergodic A&S Model* (2024)
- Moallemi & Yuan, *A Model for Queue Position Valuation in a Limit Order Book* (2016)
- Stoikov, *The Micro-Price* (2018)
- Cont & Kukanov, *Optimal Order Placement in Limit Order Markets* (2017)
