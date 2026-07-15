# Second-Edge Hunt — Settlement-Validated Search (companion to FAVLONG)

**Date:** 2026-07-15 · **Author:** research agent (offline, propose-only) · **Status:** all four candidates **NULL**

## Objective
Hunt for a SECOND, independent, settlement-validated edge on the same Kalshi 15m crypto binary
tick archive (btc/eth/sol "up" contracts), distinct from FAVLONG (a near-expiry, t≥600s
favorite-longshot contrarian *taker*). We deliberately explored **earlier in the window** and
**different mechanisms**: order-book imbalance, binary-mid momentum/reversion, an early-window
vol-risk-premium, and cross-asset lead-lag.

## Methodology (identical rigor to FAVLONG — this is the whole point)
- **Realized settlement label.** Outcome = the market's own terminal price, `mid_close > 0.5`.
  Verified decisive: 99.1% of BTC windows terminate at mid `<0.05` or `>0.95`, so terminal-mid is a
  clean proxy for the actual Kalshi settlement. No strike-proxy self-labeling.
- **Executable taker P&L, spread crossed.** Buy the "up" contract at the **ask**, sell at the
  **bid**. Every trade pays the **Kalshi fee** `0.07·p·(1−p)` per contract on the fill price.
- **Day-clustered t-stat.** P&L pooled to a per-(asset,day) [candidates 1–3] or per-day [candidate
  4, cross-asset] mean, then a clustered t across those cluster means (same estimator as
  `favlongshot_edge.py`).
- **Train = days ≤ 2026-06-30, Test = days > 2026-06-30.** Every hyperparameter (decision time,
  threshold, lookback, direction) was selected on TRAIN by net day-clustered t, then confirmed on
  TEST **once**.
- **Gross diagnostic.** Alongside net taker P&L we report `gross` = directional P&L vs the current
  mid (no spread, no fee). This separates "no signal at all" from "real signal, but smaller than
  trading costs." A candidate is REAL only if **net** OOS day-clustered t ≥ 2.
- **Multiple testing.** **186 configs** were scored across the four candidates (C1: 9, C2: 24,
  C3: 9, C4: 144). Verdicts below use the best-on-train config per candidate confirmed once on test.

Data: `win_{btc,eth,sol}.pkl` (2839/2859/2886 windows, 35 days) for candidates 1–3; a rebuilt
ws-aligned set (`aligned.pkl`, 2735 windows present in all three assets, 36 days) for candidate 4.

---

## Candidate 1 — Book Imbalance (taker on the heavier side)
**Design.** At a mid-window decision time (dt∈{180,300,420}s), with mid in (0.15,0.85), compute
`imb = (bidq−askq)/(bidq+askq)`. If `imb>thr` buy "up" at ask; if `imb<−thr` sell "up" at bid;
thr∈{0.3,0.5,0.7}. Does book pressure predict settlement beyond the current mid?

| set | n | net $/ct | net day-clust t | gross $/ct | gross t |
|---|---|---|---|---|---|
| TRAIN (best: dt=180, thr=0.5) | 3179 | **+0.0008** | **0.15** | +0.0242 | 3.02 |
| TEST | 2287 | −0.0111 | −1.18 | +0.0110 | 1.19 |

**Verdict: NULL.** There *is* a genuine gross microstructure fact — the heavier side of the book
predicts short-horizon settlement direction (gross ≈ +2.4c/ct, t≈3.0 in-sample). But it is worth
**almost exactly the spread + fee you must pay to take it**: net P&L collapses to ~0 in-sample and
goes negative OOS, and the gross signal itself weakens out-of-sample (t 3.0→1.2). This is a
maker-side observation (the live box-bot posting quotes may already harvest it); a **taker cannot
monetize it**.

## Candidate 2 — Binary-Mid Momentum / Reversion
**Design.** At dt∈{240,360,480}s compute the mid's change over a prior interval L∈{120,180}s.
MOM = trade in the direction of the move, REV = against it; threshold∈{0.05,0.10}; mid in (0.15,0.85).

| set | n | net $/ct | net day-clust t | gross $/ct | gross t |
|---|---|---|---|---|---|
| TRAIN (best: dt=360, L=120, REV, thr=0.10) | 1949 | −0.0119 | −0.35 | +0.0115 | 1.45 |
| TEST | 1304 | −0.0106 | −0.25 | +0.0108 | 1.48 |

**Verdict: NULL.** A weak *momentum* gross signal appears at the shortest horizon (dt=240, L=120:
gross +1.3c, t=2.44 in-sample) but does not survive to neighboring configs and never beats costs;
net P&L is negative or zero across all 24 configs. No tradeable edge in either direction.

## Candidate 3 — Vol-Risk-Premium (model favorite, early window)
**Design.** FAVLONG's fair-value model (spot-vs-strike scaled by causal realized vol and time-to-
expiry) applied **early** (dt∈{300,420,540}s): when the model says a side is favored by more than
`edge`∈{0.05,0.08,0.12} vs the executable price, take that (favorite) side — harvesting overpriced
uncertainty when the mid sits near 0.5 but spot has barely moved.

| set | n | net $/ct | net day-clust t | gross $/ct | gross t |
|---|---|---|---|---|---|
| TRAIN (best: dt=300, edge=0.12) | 1328 | −0.0190 | −2.47 | +0.0004 | −1.22 |
| TEST | 940 | −0.0109 | −0.51 | +0.0074 | 0.82 |

**Verdict: NULL.** The model has **no gross predictive value before the terminal window** (gross t
negative/≈0 on train). This directly confirms FAVLONG's own caveat that its edge is a
terminal-convergence effect (t≥600s) and is ~0 earlier — the VRP framing does not rescue it. Net
P&L is significantly *negative* in-sample (paying spread+fee for a non-signal).

## Candidate 4 — Cross-Asset Lead-Lag
**Design.** Rebuilt clock-aligned windows keyed by `ws` (window-start unix ts) so btc/eth/sol
windows can be matched. At dt∈{240,360,480}s, use a leader asset's spot log-return over L∈{60,120}s
(mode=`abs`) or its return minus the target's own return (mode=`rel`) to trade the target's "up"
binary; thr∈{0.0008,0.0015,0.003}; pairs eth←btc, sol←btc, btc←eth, sol←eth. 144 configs.

| set | n | net $/ct | net day-clust t | gross $/ct | gross t |
|---|---|---|---|---|---|
| TRAIN (best: target=sol, leader=btc, dt=360, L=60, rel, thr=0.0008) | 165 | +0.0751 | 1.01 | +0.1005 | 1.56 |
| TEST | 71 | −0.0247 | −1.37 | −0.0028 | −0.97 |

**Verdict: NULL.** The single best of 144 configs reached only net train t=1.01 (already below the
bar) and **flips sign on test** (net t −1.37, gross also negative). Classic in-sample fluke pulled
from a large grid. No stable cross-asset settlement mispricing was found.

---

## Summary Table

| # | Candidate | Best-train net t | **OOS (test) net t** | OOS mean $/ct | Gross signal? | Verdict |
|---|---|---|---|---|---|---|
| 1 | Book imbalance (taker) | 0.15 | **−1.18** | −0.0111 | Yes (~2.4c, t3.0) but ≈ spread | **NULL** |
| 2 | Mid momentum/reversion | −0.35 | **−0.25** | −0.0106 | Weak momentum, < costs | **NULL** |
| 3 | Vol-risk-premium (early) | −2.47 | **−0.51** | −0.0109 | None (t≈0/neg) | **NULL** |
| 4 | Cross-asset lead-lag | 1.01 | **−1.37** | −0.0247 | None (flips OOS) | **NULL** |

**No candidate reached OOS pooled day-clustered t ≥ 2.** None even cleared a positive *train* net
t ≥ 2. There is nothing here to promote to forward validation.

## Interpretation (honest)
- The archive is **efficient at mid-window horizons** for a taker. Two candidates (imbalance,
  short-horizon momentum) contain a *real but tiny* gross directional signal (~1–2.4c/ct), and in
  every case it is **≤ the bid/ask spread plus the Kalshi fee** a taker must pay. FAVLONG is special
  precisely because its terminal-window overconfidence (underdogs priced ~0.09 settling ~0.32)
  produces a gross edge *large enough* to clear costs — the mid-window signals do not.
- The one candidate with a plausibly monetizable *gross* signal, book imbalance, is a **maker-side**
  phenomenon. If anything it argues the existing live *maker* box-bot is on the right side of book
  pressure, not that a second *taker* strategy exists. It is not an independent tradeable edge.
- Candidate 3 independently reproduces FAVLONG's key caveat from the other direction: the fair-value
  model carries **no information before the last few minutes**. This is corroborating evidence that
  FAVLONG's edge is genuinely a terminal-convergence effect, not a general model advantage.

## Conclusion
All four candidates are NULL under fee-inclusive, spread-crossing, settlement-clean, day-clustered,
train/test-split evaluation (186 configs tried). **No second edge survived.** FAVLONG remains the
only validated positive edge; this null does not weaken it and mildly corroborates its mechanism.
Recommend no forward-validation slot be opened for any candidate here.

_Propose-only. No live flag, switch, size, or order was touched._
