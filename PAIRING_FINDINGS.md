# Pairing / strand prediction — findings (2026-07-13)

Question: can we predict which maker-box legs pair vs strand well enough to matter?
Prior study: 10-feature logistic, test AUC 0.558. This effort tested that ceiling
exhaustively and found where the real edge is. All results: train days ≤2026-06-29,
test ≥2026-06-30, day-blocked (never split a day), ~11k first-fill events, 4 assets.

## 1. At-fill prediction has a hard ~0.58 ceiling — not the product

| model | test AUC (pair-ever) | notes |
|---|---|---|
| prior logistic (reproduced) | 0.562 | matches prior 0.558 |
| first-passage physics, standalone | ~0.54 | closed-form didn't break through |
| 220-feature HGB (feature lab) | 0.577 pooled / 0.543 BTC | overfits day drift, worse on BTC |
| flow/ladder family marginal | +0.018 pooled / ~0 BTC | real prints add ~nothing |

Label grid (HGB, at fill): AUC is **flat ~0.56–0.59 across every label horizon**
T ∈ {15s…600s, ever}. Shorter labels raise the base rate, NOT discrimination.
**Conclusion: a better entry-time pair-probability gate is not where the money is.**
The existing static pair-gate (depth≥med + k≤10 + |sig|<10) already captures the
entry-time value (strand 14.8%→1.9%, +0.46c/box).

## 2. Post-fill DETECTION clears 0.75 — the information is there, after the fill

Clairvoyance curve — test AUC of "won't pair by 120s" using ticks up to fill+h:

| h (s after fill) | 0 | 30 | 60 | 90 |
|---|---|---|---|---|
| AUC (BTC) | 0.57 | 0.72 | **0.81** | 0.82 |

5-second pairing hazard model P(pair in next 5s | state): **test AUC 0.909, well-calibrated.**
Top driver by far: distance from fair value to the completing quote.
BUT high AUC ≠ money: a naive threshold alarm LOSES on test (−0.2c) — 84.5% of its
alarms are false, dumping likely-winners to catch few losers.

## 3. THE EDGE: state-dependent optimal-stopping disposal (replaces fixed 120s)

Rule: dispose when `wait_edge(s) = hz·(dist+fee) − (1−hz)·E[Δcost|no pair] < kappa`,
hz = fitted 5s pairing hazard, kappa ≈ −0.5c.

| policy | TEST EV/box | vs live (day-clustered) |
|---|---|---|
| live fixed-120s | −4.603c | — |
| best fixed deadline (T=300s) | −4.217c | +0.386c, t≈−0.1 (NOT robust) |
| **state-dependent stopping** | **−3.983c** | **+0.570 ± 0.241c, t=2.36** ✅ |
| oracle (dispose all true strands at fill) | −1.390c | +3.21c (ceiling) |

- First policy that **robustly** beats live (t=2.36). Captures **19.3%** of the oracle gap.
- No fixed deadline (incl. the live 120s) is reliably better than live — the win is
  from being *adaptive*, not from re-tuning the constant.
- Adaptivity confirmed: would-strand legs disposed 72% (mean 98s); would-complete
  legs disposed 42% (mean 37s). Still a high 74.5% false-disposal rate — fragile,
  high-churn edge that barely nets positive; improving the hazard is the lever.

## How we use it
1. **Drop** the "better at-fill pair model" line of work — ceiling is 0.58, no EV.
2. **Ship the disposal change**: replace fixed-120s dispose with hazard-based
   state-dependent stopping. Worth ~+0.57c/box (t=2.36) on top of live.
3. RenTec framing realized: not a crystal ball (AUC), but a modest edge acted on
   optimally across ~380 bets/day.

## Open tests (in flight)
- Does perp microstructure / liquidation data raise hazard AUC → oracle capture >19%?
- Does the +0.57c stopping edge SURVIVE on top of the live entry pair-gate, or is it
  redundant with it? (deployment-critical)
- +40 days Kalshi backfill (series → 2026-05-06) as extra training data.
- Ensemble/stack across signal families for the hazard model.

## Caveats
Tape-replay fill model (optimistic on the completing leg). Stopping edge is fragile
(74.5% false disposals; dca cost-regressor weak, corr 0.13). Forward/paper validation
required before sizing. BTC only — ETH/SOL/XRP boxes don't pair profitably even gated.
