# ETH 15-min Toxicity-Gated One-Sided Maker — VERDICT: NO EDGE

**Date:** 2026-06-13 · **Data:** Kalshi ETH 15-min binary, 2384 windows, 38,128 reconstructed
maker fills · **Split:** IS = first 60% windows, OOS = last 40% · **Fee:** maker ≈ $0 (no drag).

## TL;DR

There is **no positive-EV toxicity-gated one-sided maker on ETH 15-min.** Adverse selection
consumes the entire half-spread at every toxicity gate. The only apparently-positive cut
(ask-only) is an **in-sample directional drift artifact** (YES overpriced ~0.9pp this sample),
not spread capture — it cancels to negative when you net both sides, fails OOS significance, and
flips negative under any realistic queue assumption. **Do not deploy.**

---

## Fill model (read before trusting any number)

- A maker fill = we rest at the touch (`b0` bid / `a0` ask) and a taker **trades through our
  level** in the next 1–2 min (only counted when real size crosses; from `window_fills`).
  One-sided ⇒ we open a single directional leg and do **not** pair it.
- Leg value = `settle` (hold to settlement) = `res − b0` (YES buy) or `a0 − res` (NO/YES-sell).
  **Spread capture is baked in:** `settle = half_spread + (directional outcome vs mid)`. If the
  mid were efficient, `E[settle] = +half_spread`. Adverse selection = `E[res|filled] ≠ mid`.
- Mean spread = **2.11c** ⇒ half-spread ≈ **1.05c** (the gross prize from uninformed flow).
- **Queue caveat (decisive):** all headline numbers use `q0=0` (front-of-queue) — the single most
  optimistic fill assumption. With a modest queue ahead, fills get strictly more toxic (you only
  fill when the move clears the queue):

  | q0 (contracts ahead) | #fills | both-sides EV/fill | ask-only EV/fill |
  |---|---|---|---|
  | 0 (optimistic)  | 38,128 | **−0.77c** | +0.36c |
  | 5               | 36,336 | −1.30c | −0.11c |
  | 20              | 33,732 | −2.00c | −0.76c |

  Even the most generous fill model is net-negative on both sides; the ask-only "edge" evaporates by q0=5.

---

## TASK 1 — Uninformed vs informed flow decomposition (hold-to-settle, q0=0)

Half-spread captured ≈ **+1.05c on BOTH sides**, but adverse selection eats it:

| side | mean settle | half-spread | adverse-selection cost | net |
|---|---|---|---|---|
| BID (buy YES) | **−1.91c** | +1.05c | **−2.96c** | −1.91c |
| ASK (sell YES) | **+0.36c** | +1.05c | **−0.70c** | +0.36c |

The 2.26c side asymmetry is the **directional drift**: realized P(up)=48.17% but mean YES mid
priced 49.04% ⇒ YES overpriced ~0.9pp ⇒ selling YES (ask) "wins", buying YES (bid) "loses" — a
bet on a 2385-window sample drift, **not** a maker edge. Prior favorite-longshot work already
established this bias is not forward-exploitable.

Toxicity buckets (hold-to-settle EV/fill, all flow): every VPIN / |flow| / |sig| / size quartile
is **negative** (−0.46c to −1.28c, t = −1.0 to −3.0). Low-toxicity buckets are less negative but
never positive. VPIN is **non-monotone** on the ask side (Q2 worse than Q4) — a weak separator here.

## TASK 2 — Gated-maker sweep (accept LOW-toxicity only)

Best one-sided cuts are all **ask-side** (i.e. all riding the YES-overpricing drift):
`ask|vpin≤0.30` +1.02c (t=1.5), `ask||sig|≤4` +0.69c (t=1.6), `ask||sig|≤8` +0.62c (t=1.7).
Every **bid-side** cut is −1.9c to −2.2c (t = −4 to −6). 

**Drift-neutral test (the clean answer):** combine BOTH sides under each gate — this cancels the
directional drift, leaving only genuine spread-capture-minus-adverse-selection. **Every gate is
negative on both IS and OOS:**

| gate (both sides) | IS EV/fill (t) | OOS EV/fill (t) |
|---|---|---|
| ungated | −0.72c (−2.6) | −0.85c (−2.6) |
| vpin≤0.35 | −0.72c (−1.4) | −0.97c (−1.6) |
| \|sig\|≤4 | −0.79c (−2.1) | −0.63c (−1.2) |
| \|flow\|≤250 | −0.74c (−1.9) | −0.90c (−1.9) |
| tksize≤3 | −0.54c (−1.3) | −0.80c (−1.7) |

No gate separates uninformed flow well enough to net the spread positive. Adverse selection
dominates spread capture at **every** threshold.

## TASK 3 — Inventory / exit

For the ungated book: HOLD-to-settle −0.77c, FLATTEN-at-touch −1.83c (t=−27), STOP-if-adverse
−1.18c. **Holding to settle dominates** — flattening pays the spread twice and stops crystallize
the adverse move. Even on the best (drift-biased) `ask|vpin≤0.30` cut, hold +1.02c beats
flatten −1.84c and stop +0.46c. Exit management cannot rescue a leg with no predictive edge: the
leg is a coin-flip plus a half-spread that adverse selection already ate.

## TASK 4 — Time / regime

By k-slot: best is k=2 (−0.06c) decaying to −1.4c mid-window; **no slot is positive**. By
hour-of-day: best hours (04–05, 20, 23 UTC) are −0.23c to −0.35c, worst (07–08, 11–12 UTC) are
−1.1c to −1.45c — a real retail/Asia-vs-EU-open texture, but the "good" hours are merely
**less negative**, never positive. No regime makes the strategy viable.

## TASK 5 — VERDICT

| rule | IS EV/Sh/t | OOS EV/Sh/t |
|---|---|---|
| ungated both (hold) | −0.72c / −0.02 / −2.6 | −0.85c / −0.02 / −2.6 |
| ask-only (hold) | +0.61c / +0.01 / +1.6 | **−0.02c** / 0.00 / 0.0 |
| ask & \|sig\|≤4 (hold) | +0.52c / +0.01 / +1.0 | +1.00c / +0.02 / **+1.4** |
| favored & \|sig\|≤4 (hold) | −0.92c / −0.02 / −1.7 | −0.93c / −0.02 / −1.2 |

The single least-bad candidate, **ask & |sig|≤4 (hold-to-settle)**: OOS EV +1.00c/fill but
Sharpe +0.02, t=+1.4 (**not significant**), bootstrap 95% CI **[−0.39c, +2.44c]** straddles zero
(P(EV>0)=0.93). It is entirely the in-sample YES-overpricing drift, dies to −0.11c at q0=5, and
the same directional bias was already shown non-exploitable forward.

### Bottom line
**No positive-EV toxicity-gated maker exists on ETH 15-min.** Half-spread ≈1.05c is real, but
adverse selection ≥ half-spread in every toxicity bucket and every gate; the drift-neutral
both-sides EV is negative IS and OOS at all thresholds. The only positive signal is a small-sample
directional drift masquerading as a maker edge — insignificant OOS and fragile to the fill model.

- **EV/fill:** best honest (drift-neutral) gate −0.54c to −0.97c; the drift-biased ask cut +1.0c OOS but CI straddles 0.
- **Sharpe:** ≈ 0 to slightly negative everywhere.
- **#fills:** ~38k (q0=0); fewer and more toxic as queue grows.
- **IS/OOS:** ask-only +0.61c IS → −0.02c OOS (the drift is not stable).
- **t vs zero:** ungated −2.6; best candidate +1.4 (fails).

**Recommended rule: DO NOT TRADE.** If forced to forward-validate one cut, log-only
`ask & |sig|≤4, hold-to-settle, q0≥5 fill model` and require a pre-registered 2σ live confirmation
before any capital — expectation is it confirms negative once queue and drift-reversion bite.

### Caveats
- q0=0 front-of-queue is unrealistically optimistic; the table above shows the edge is a fill-model
  artifact. Real queue priority on a passive quote is worse than q0=5.
- `settle` already nets spread capture and outcome; we did not double-count fees (maker ≈ $0, correct).
- ETH mid is informationally efficient (established prior): no taker/predictive edge to lean on for
  inventory, so a filled leg is a coin-flip + an already-eaten half-spread.
- Backtest SCREENS only. Conclusion (negative) is robust across IS/OOS, drift-neutralization,
  bootstrap, queue sensitivity, and regime slicing — consistent enough to reject without forward test.
