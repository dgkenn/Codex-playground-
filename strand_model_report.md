# Stranded-Box Prediction Model — Report

**Goal.** Predict P(strand | causal features at the box decision instant) for the
Kalshi 15-minute box-maker, so quotes likely to strand can be vetoed. A *strand* =
one leg of the two-leg box fills and the other doesn't, leaving an unhedged
directional position (a loss). Secondary use: an execution risk-filter for a new
riskless multi-leg bucket-arb (same leg-fill problem).

**Honesty up front.** The box-maker itself is ~zero-edge and halted, so at best this
tweaks a marginal strategy. And as shown below, the rich model does **not** beat a
one-line rule — so the deliverable is mostly a *negative* result with one genuinely
useful causal finding.

---

## 1. Data & construction

- Source: git branch `origin/gha-data`, read via `git show` (no checkout).
- **Labels:** `box_shadow_<asset>15m.jsonl`, one row per (window, arm). Modeled the
  **`live`** arm — the most-populated non-veto arm — so we learn *raw* strand
  behaviour, not another arm's veto. Label = `stranded`.
- **Features:** `ticks_kalshi_<asset>15m_*.jsonl.gz`. A window's tick stream is
  split across ~30 run-files/day; aggregated by `ws`, sorted by `t`, and features
  built **causally from ticks with t ≤ 720s** (the decision instant). Tick =
  `[t, mid, spot, micro, bid, bidq, ask, askq]` on the "up" contract.
- **Assets:** btc + eth (only assets with box_shadow labels). **No OFI files**
  present for these days, so the optional Coinbase OFI join was skipped.
- **Join:** labels ↔ features on `(asset, ws)`.
- **Days:** 2026-07-07 … 2026-07-15 (9 days — more than the "07-12 onward" hint).
  Time-OOS split: train = first 6 days (07-07…07-12), test = last 3 (07-13…07-15).

**Features (12):** `spread`, `log_depth`(=log1p(bidq+askq)), `imbalance`,
`abs_imbalance`, `mid_dist_05`(=|mid−0.5|), `micro_skew`(=micro−mid),
`rel_strike`(=|spot−open_spot|/open_spot, strike≈open spot), `rvol` (causal
realized vol of spot over ticks ≤720), `recent_move` (|Δspot| over last ~60s),
`n_ticks_causal`, `hour` (UTC), `is_eth`. All strictly pre-decision. NaN `rvol`/
`spread` median-imputed (noted as a minor caveat given tiny n).

## 2. Sample size & base rate

| | value |
|---|---|
| joined windows (n) | **1,469** |
| strand events | **133** |
| **strand base rate** | **9.05%** |
| train | 1,028 windows, 92 strands |
| test (OOS) | 441 windows, 41 strands |

Small sample, especially the test fold (41 positives) → wide AUC CIs. Treat all
numbers as directional.

## 3. OOS performance

| model | OOS AUC | 95% bootstrap CI |
|---|---|---|
| Logistic regression (L2, balanced) | **0.635** | [0.563, 0.699] |
| Gradient-boosted trees (Hist-GBT) | **0.617** | [0.534, 0.688] |

Both CIs sit above 0.50, so there is a **real but weak** signal. GBT calibration is
poor at the top: its highest-score bin predicts ~30% strand but observes ~10%
(over-confident on 88 windows) — expected on this sample size.

**Single best feature beats the whole model.** Direction-agnostic *univariate* OOS
AUC:

| feature | univariate OOS AUC |
|---|---|
| `rel_strike` (|spot−strike|/spot) | **0.715** |
| `spread` | 0.709 |
| `mid_dist_05` (|mid−0.5|) | 0.705 |
| `hour` | 0.630 |
| `log_depth` | 0.582 |
| `rvol` | 0.560 |
| imbalance / micro_skew / recent_move / n_ticks | ≤ 0.55 |

One moneyness feature (0.71) **out-predicts the full multi-feature model (0.62–0.64)**
— the extra features add OOS noise. This is the central anti-overfit finding.

## 4. What predicts a strand (causal story)

Logistic coefficients (standardized) and GBT permutation importance agree:

- **Dominant:** `mid_dist_05` (coef **+1.19**) and `rel_strike` (GBT importance
  **top**). Larger distance of the contract mid from 0.5, and larger spot-vs-strike
  distance → **more** strands.
- **Weak/irrelevant:** book depth (`log_depth`), order-book `imbalance`, `spread`
  (once moneyness is included — spread's univariate power is redundant with it),
  and — notably — `rvol` and `recent_move`.

**Interpretation:** strands happen on **lopsided / far-from-strike** markets. When the
15-min market has moved away from the strike (mid near 0 or 1), one leg is deep/cheap
and the *other leg's price sits where nobody trades*, so it never fills → the deep leg
strands. Near a coin-flip (mid≈0.5) both legs are symmetric and both fill → locked/hedged.

This **contradicts the intuition baked into the existing heuristics** ("thin book,
high vol, near-strike+movement"). It's the *level* of moneyness at the decision
instant that matters, not book thinness, not realized vol, and not recent movement.

## 5. Veto tradeoff vs heuristics (OOS test set)

At a veto threshold matched to each heuristic's veto rate: strand% among **kept**
windows (lower is better) and % of good (locked/hedged) fills retained.

| policy | veto% | kept | strand% (kept) | strands kept | good retained |
|---|---:|---:|---:|---:|---:|
| **no-veto (live)** | 0.0% | 441 | 9.3% | 41 | 100.0% |
| thickbook_veto | 20.6% | 350 | 9.4% | 33 | 79.2% |
| model @ thickbook rate (GBT) | 20.6% | 350 | 9.1% | 32 | 79.5% |
| model @ thickbook rate (LR) | 20.6% | 350 | 8.6% | 30 | 80.0% |
| **simple \|mid−0.5\| @ thickbook rate** | 20.6% | 350 | **7.4%** | **26** | **81.0%** |
| volgate | 25.4% | 329 | 10.3% | 34 | 73.8% |
| model @ volgate rate (GBT) | 25.4% | 329 | 8.8% | 29 | 75.0% |
| model @ volgate rate (LR) | 25.4% | 329 | 8.8% | 29 | 75.0% |
| **simple \|mid−0.5\| @ volgate rate** | 25.4% | 329 | **6.4%** | **21** | **77.0%** |
| nsmove | 12.7% | 385 | 9.9% | 38 | 86.8% |

Reading this table:

- **The existing heuristics barely help — two actively hurt.** `volgate` (10.3%) and
  `nsmove` (9.9%) leave a strand rate among kept windows *above* the 9.3% no-veto
  baseline: they veto good fills while keeping strands. `thickbook_veto` is roughly
  neutral (9.4%).
- **The rich model gives a small, real improvement** over the heuristics at matched
  veto rate (e.g. 8.6% vs 9.4% strand, +0.8pp fills retained vs thickbook).
- **A single-feature rule beats everything.** Vetoing the most lopsided windows by
  `|mid−0.5|` cuts kept-strand rate to **7.4% / 6.4%** *and* retains **more** good
  fills (81.0% / 77.0%) than either the model or the heuristics. The GBT/LR dilute
  this dominant signal with noisy features and rank slightly worse.

## 6. Blunt verdict

**Does a rich-feature model predict strands materially better than the simple
heuristics? No.**

1. There *is* a genuine, causal predictor of strands, but it is **one variable:
   moneyness / distance-from-strike** (`|mid−0.5|` ≈ `|spot−strike|`, univariate OOS
   AUC ≈ 0.71). Strands are a lopsided-market phenomenon, not a thin-book/high-vol one.
2. The **rich logistic/GBT models are worse than that single feature** (AUC 0.62–0.64
   < 0.71) — on this small sample the extra features only add overfit noise. A
   gradient-boosted tree is unjustified here.
3. Against the deployed heuristics, a plain `|mid−0.5|` veto **dominates**: at matched
   veto rates it removes noticeably more strands (7.4%/6.4% vs 9–10%) while keeping
   *more* good fills. `volgate` and `nsmove` are counterproductive on this data.
4. **Is the lift big enough to matter for the box? No.** Even the best rule only moves
   the kept-strand rate from 9.3% → ~7%, costing ~20% of good fills — nowhere near
   enough to rescue a zero-edge maker.
5. **As an arb-leg fill filter? Modestly useful, but keep it simple.** The lopsidedness
   signal is real and directionally sensible: avoid quoting legs where the market has
   moved far from the strike (the off-side leg won't fill). Implement it as a single
   `|mid−0.5|` (or `|spot−strike|`) threshold — do **not** ship the GBT. Retrain the
   threshold as more days accrue; 9 days / 133 events is underpowered (test-fold CIs
   span ~0.53–0.70).

**Bottom line:** the honest result is a *near-null for the rich model* plus *one useful,
simple, causal rule*. Ship the one-line moneyness veto (if anything); shelve the GBT.

---

### Reproduce
```
python3 strand_model.py      # reads origin/gha-data via git show; ~35s
```
Writes `strand_model_results.json` (all metrics, coefficients, tables). No git commit made.

**Caveats:** small sample (esp. 41 OOS positives); median-imputation of missing
`rvol`/`spread` fitted on the full pool; only btc+eth; no OFI features (files absent);
`live`-arm-only (raw strand). Findings are directional, not production-grade.
