# INSIGHTS.md — 5 data-grounded insights, literature-cross-checked (Polymarket BTC 15-min MM)

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
