# FAVLONG tuning + sizing study

Disciplined hyperparameter + sizing study for the FAVLONG near-expiry contrarian taker edge.
Tool: `favlong_tuning.py` (reuses `favlongshot_edge.py` math; caches at `/tmp/favlong_cache`).
Protocol: grid fixed up front → select single best config by **TRAIN** pooled day-clustered t
(n≥30 guard) → evaluate that one config on **TEST (OOS)** exactly once → sizing study.
Train = days ≤ 2026-06-30; Test/OOS = days > 2026-06-30. 144 configs searched.

## Selected config (train-only selection)
`decision_t=720s, edge=0.03, sigma_mult=0.8, pricefilt=None` — train pooled t=4.35 (n=63).
The **sigma_mult=0.8** winner is consistent across the entire train top-10: the causal
realized-vol estimate runs slightly *high*, so shrinking it ~20% sharpens the fair-value
and surfaces more genuine mispricings. `edge=0.03` (vs 0.05 default) simply trades a bit more.

## OOS result — single evaluation of the selected config
| metric | selected (720/0.03/σ0.8) | baseline (720/0.05/σ1.0) |
|---|---|---|
| pooled OOS day-clustered t | **3.97** | 3.07 |
| pooled mean $/contract | **+0.0332** | +0.0255 |
| positive asset-days | 26/42 | 26/42 |
| BTC OOS t | 3.74 | (≈3.0) |
| ETH OOS t | 1.85 | — |
| SOL OOS t | 1.42 | — |

**Verdict:** tuning gives a **modest, real** OOS improvement (pooled t 3.07 → 3.97; ~3.3c/ct
vs ~2.6c/ct) — *not* a step-change. The character is unchanged: it is the same broad
favorite-longshot effect, slightly sharpened, and **only BTC clears t≥2 individually OOS**
(eth 1.85, sol 1.42). Confidence still rests on **pooling** the shared mechanism. Tuning did
not overfit to a fragile corner (the whole top-10 is coherent: t≥720, low σ), which is
reassuring.

## Sizing study (selected config, OOS) — READ THE CAVEAT
| sizing | pooled OOS daily-$ t | BTC-only OOS daily-$ t |
|---|---|---|
| flat (1 ct/trade) | 3.90 | 3.57 |
| edge-proportional | 4.96 | 3.79 |
| fractional-Kelly (0.25) | 5.35 | 5.71 |

**What is real:** edge-proportional and fractional-Kelly sizing **improve the risk-adjusted
t** (3.9 → ~5.3). That is a genuine, expected result — betting more when the model edge is
larger concentrates capital on the higher-confidence trades.

**What is NOT a projection (do not quote as P&L):** the raw dollar totals the study printed
(edge-prop ≈ $3,843 total / $91 per asset-day; Kelly ≈ $712) are **artifacts of an arbitrary
100-contract cap with no capital budget and no market-impact model**. Taking ~100 contracts on
an underdog leg (median depth 420 but many trades thinner) would move the price; none of that is
modeled. The **honest units are per-contract (~3c) and the flat-sized figure (~$1.3/asset-day at
1 contract).** Any real sizing must be bounded by the live account's capital and a slippage model,
and set live — not read off this uncapped backtest.

## Recommendations
1. **Config for forward tracking.** The tuned `720/0.03/σ0.8` is train-selected + single-OOS-
   confirmed (legitimate pre-registration) and modestly better. But the committed forward harness
   (`favlong_forward.py`) currently tracks the **baseline `720/0.05/σ1.0`**. Recommend the operator
   pick ONE pre-registered config for the gate; I did **not** silently change it (it defines the
   gate). Either is defensible; the tuned one is slightly stronger. Easiest honest path: forward-
   track BOTH and let the gate judge — cheap, and avoids a config-picking degree of freedom.
2. **Sizing = fractional-Kelly, capital-bounded.** If the forward gate passes, size by
   fractional-Kelly (0.25) **capped by both displayed depth and a hard per-trade capital limit**
   tied to the live balance — never the uncapped backtest sizing.
3. **BTC-first.** BTC is the only single instrument clearing t≥2 OOS; if going live, start BTC-only
   at minimal size and add eth/sol only if their forward rows independently firm up.

## Caveats (unchanged from FAVLONG)
Small edge (~3c/ct); concentrated in the last 2–3 min; ~62% asset-days positive (real variance);
TAKER strategy (new execution); favorite-longshot is a known effect that can decay → the **forward
gate (pooled day-clustered t≥2 over ≥10 forward days) remains mandatory before any live sizing**,
and all of the above is PROPOSE-ONLY (no live flag/switch/size touched without operator authorization).
