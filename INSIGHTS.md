# INSIGHTS.md — 5 data-grounded insights, literature-cross-checked (Polymarket BTC 15-min MM)

> _Historical — superseded by the gating validation + 4-day multi-asset data. Kept for provenance; where this disagrees with current docs, **README.md / GATING.md / INSIGHTS_4DAY.md win**._

Basis: 58 settled windows, ~48k audited per-decision records (multi-day, multi-regime, paper on
LIVE data; audit reconciles to 0). Each insight: DATA finding → LITERATURE cross-check → TWEAK.

## 1. Adverse selection is the dominant cost; the microprice is the right "fair", and gating on it is the only robust edge
- DATA: baseline gross ≈ 0/negative — the *entire* net is the maker rebate. Short-horizon adverse
  markout is significant (mo30 window-clustered t = -3.06, 37w). The microprice EDGE (price vs
  microprice) is the one sign-consistent separator of good/bad fills (21/8 windows). micro_gate
  (pull when micro crosses our quote) beats baseline by +5.3/win, t = +5.99 over 58 windows.
- LIT: Stoikov, *The Micro-Price* (Quant. Finance 2018) — the microprice (mid + imbalance/spread
  adjustment) is the martingale "fair" and a better short-horizon predictor than mid; exactly the
  signal micro_gate uses. Glosten-Milgrom (1985) / prediction-market evidence ("makers earn the
  spread from noise but lose when picked off by insiders") — adverse selection IS the maker's cost.
- TWEAK (LIVE): microprice-gate every quote. Refinements in A/B: micro_marg (require an edge
  MARGIN, not edge>0 — even edge<0.001 fills were toxic) and tox_gate (composite).

## 2. Trade SMALLER — edge/Sharpe falls with inventory & capacity (the capacity dial)
- DATA: monotone in size — cap25 t=+3.64 (beats baseline), skew15 t=+3.87, baseline (cap50) +0.39,
  cap100 t=-2.48 (loses). 68% of decisions are skew-blocked (we sit at the inventory limit).
- LIT: Ho-Stoll (1981) and Avellaneda-Stoikov (2008) — optimal MM penalizes inventory by γσ²(T-t)q;
  bigger inventory = more variance/adverse exposure. Cont-Kukanov-Stoikov (2014): price-impact slope
  ∝ 1/depth → more size = more impact and adverse fill.
- TWEAK (LIVE): run tight cap/skew (cap25/skew15) or the principled continuous penalty (av_stoikov,
  +4.1/win so far); small per-quote size. More notional ≠ more profit here.

## 3. Book/flow imbalance predicts adverse markout NONLINEARLY — gate the extreme, don't widen linearly
- DATA: bid-HEAVY (imb>0.8) sells mo30 -0.0126 (toxic) vs ask-heavy +0.0057; imbalance is "mixed"
  as a *linear* feature but the EXTREME is clearly toxic. Composite toxicity score (low edge + high
  imb + bid-heavy) separates winners/losers in 24/32 windows (75%), incl. resolution P&L.
- LIT: Cont-Kukanov-Stoikov (2014), *The Price Impact of Order Book Events* — order-flow imbalance
  linearly drives short-term price (slope ∝ 1/depth). Our nonlinearity = the extreme-imbalance tail
  where the maker is most exposed.
- TWEAK (in A/B): tox_gate — skip fills at the bid-heavy/ask-heavy extreme OR below the edge margin,
  keeping mild fills (so rebate is retained where it covers the toxicity). It's a THRESHOLD problem:
  gate where adverse-selection > rebate, no further (over-gating forgoes rebate).

## 4. BTC spot LEADS the token ~0.5s — but the lead is too thin to beat the fee → use it DEFENSIVELY
- DATA: controlled feed-race — Coinbase WS spot leads the token mid ~0.5s, corr +0.39 (R²~0.15);
  the book microprice is contemporaneous with mid (no time lead). The OFFENSIVE taker (lag_taker)
  that lifts the stale book pays the 0.0175/share fee and loses: -27.9/win (n=3, but the sign +
  magnitude match the prior). Defensive variants (spot_react/micro_react) are neutral-to-positive.
- LIT: Bitcoin price-discovery / Hasbrouck information-share work — the more-informative/liquid venue
  leads a less-liquid correlated instrument (an illiquid prediction token lagging liquid spot is the
  clean case; the spot-vs-futures lead debate is only "mixed" between two liquid venues). Fee-moat
  killing latency-arb is standard effective-spread/adverse-selection economics.
- TWEAK (LIVE): reprice/pull resting quotes on a fast BTC move (defense, no fee needed) — micro_react
  /spot_react. Do NOT take. Discontinue lag_taker once n confirms (it's failing as predicted).

## 5. The edge is the rebate bounded by QUEUE POSITION; there is no directional alpha — so the prize is queue priority, not prediction
- DATA: gross ≈ 0 and resolution markout ≈ 0/noise (t=-0.23) across 58 windows — net is ~entirely the
  rebate. No exploitable directional/favorite-longshot signal.
- LIT: Moallemi-Yuan (2016), *Queue Position Valuation in a LOB* — positional value (static
  spread-vs-adverse-selection + dynamic optionality) can be of the order of the bid-ask spread;
  price-time priority drives a queue-position arms race. Prediction-market efficiency work: the
  favorite-longshot bias is weak in sophisticated markets (BTC 15-min) — MMs profit from spread/rebate,
  not from prediction.
- TWEAK (LIVE-ONLY): the headline live-pilot experiment is PREDICTIVE QUEUE POSITIONING — use the
  ~0.5s BTC lead to post early at the about-to-move level for FIFO priority over the laggard book.
  Paper can't validate it (queue is modeled); it's the single most valuable thing to test live.

## Cross-cutting
The whole edge is microstructural (rebate × queue × toxicity-avoidance), NOT predictive. Every
"go bigger / predict direction / take the arb" idea fails the fee or the variance; every
"avoid toxic flow / sit early in the right queue / stay small" idea is supported by both our data
and the canonical literature. Honest limit: paper models queue position; the queue-priority and
live-latency questions are decision-grade only on real orders.

## Sources
- Stoikov 2018, The Micro-Price: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2970694
- Cont, Kukanov, Stoikov 2014, Price Impact of Order Book Events: https://arxiv.org/abs/1011.6402
- Moallemi, Yuan 2016, Queue Position Valuation: https://moallemi.com/ciamac/papers/queue-value-2016.pdf
- Avellaneda, Stoikov 2008, HF trading in a LOB (inventory/reservation price).
- Bitcoin price discovery (Hasbrouck IS): https://arxiv.org/abs/2506.08718
- Kalshi prediction-market economics / favorite-longshot: https://www2.gwu.edu/~forcpgm/2026-001.pdf

---

# ROUND 2 — 5 more insights (deeper structure), literature-cross-checked

## 6. Adverse selection is concentrated at 5-30s and does NOT carry to resolution
- DATA: mo5 -0.0016 -> mo30 -0.0041 -> mo_res +0.0006. The pickoff peaks intra-window and is ~gone
  by resolution. So a hold-to-resolution maker realizes far less than the 30s markout; markout
  OVERSTATES the true cost, and cancel-churning would lock in transient losses.
- HONEST CAVEAT: mo_res~0 could be transient mean-reversion OR regime cancellation -- can't separate
  without intermediate horizons.
- LIT: Bouchaud propagator -- impact = transient (mean-reverting) + permanent (informational).
- TWEAK: add mo120/mo300 markout horizons to disambiguate; do NOT over-cancel/over-hedge on
  short-horizon markout -- favor passive holding (the gate handles entry; don't churn the exit).

## 7. The maker is a natural complete-set ("box") seller -> delta-neutral rebate + box premium
- DATA: sells split UP=3439 / DOWN=3369 (~even). Structurally that's selling complete sets.
- LIT: complete-set arbitrage on Polymarket (YES+NO=1); selling both legs when ask_up+ask_dn>1 sells
  the $1 box above par (risk-free leg premium) atop the rebate.
- TWEAK: actively BALANCE UP+DOWN sell inventory (stay delta-neutral -> kills the directional
  inventory risk that is the real resolution cost), and lean into a leg when the two-sided ask sum>1.

## 8. The "sell cheap / favorite-longshot" P&L pattern is REGIME-CONFOUNDED, not alpha
- DATA: sell-cheap vs sell-expensive mo_res FLIPS by outcome (resolved-DOWN +0.096 vs resolved-UP
  -0.021); robust in only 23/35 windows (mixed). We tested for a price-level directional edge and
  REJECTED it.
- LIT: favorite-longshot bias is weak in sophisticated markets (BTC 15-min).
- TWEAK: do NOT build a price-level directional tilt -- the price-level pnl spread is risk, not edge.

## 9. The strategy levers are NOT super-additive -- micro_gate captures ~all the edge
- DATA: micro_gate +5.30/win (58w) >= micro_skew15 +4.79 (26w); stacking tight skew doesn't compound.
- LIT: the microprice ~ Avellaneda-Stoikov reservation-price anchor -> the gate already controls
  inventory indirectly (it declines toxic fills that build adverse inventory).
- TWEAK: keep it simple -- micro_gate + a light cap; avoid over-engineered stacked gates
  (diminishing returns + multiple-testing risk).

## 10. The binding constraint is QUEUE POSITION & fill rate, not signal
- DATA: fill rate ~6%; 68% of decisions skew-blocked; the profitable buy-side is scarce (can't be
  summoned). We capture a tiny slice of flow; more alpha signals barely move net.
- LIT: Moallemi-Yuan queue value.
- TWEAK: the highest-leverage remaining work is LIVE FIFO queue priority, not more paper signals.

## Round-2 sources
- Bouchaud propagator / transient impact: https://arxiv.org/abs/1412.0141 ; MM + transient impact: https://arxiv.org/html/2601.13421
- Polymarket complete-set arbitrage: https://arxiv.org/abs/2508.03474
