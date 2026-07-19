# FAVLONG refinement — dislocation-conditioning & favorite-tilt vs the calibrated baseline

**Date:** 2026-07-15 · offline research, propose-only · **Status:** no refinement materially beats
the calibrated baseline; the tradeable window does **not** extend earlier.

## Question
Does conditioning the calibrated FAVLONG taker on **dislocation** (wide spread, or a large
`|model_fair − mid|` gap) (i) **grow** the per-trade edge and (ii) **extend** it to **earlier**
decision times (300/450/600 s), and does a **favorite-side** tilt (entry ≥ 0.40 / ≥ 0.60) improve it?

## Method (same rigor as the calibrated model)
- **Model held fixed = the calibrated FAVLONG:** baseline causal vol, `logndrift` moneyness,
  isotonic calibration (sklearn, fit **train-only**), `edge = 0.03`. Math imported verbatim from
  `favlong_model_v2.py` (`model_fair`, `fit_isotonic`); fees `KFEE = 0.07·p·(1−p)`; taker mechanics
  identical to `favlongshot_edge`. Isotonic re-fit on TRAIN windows **at each decision_t** (leak-free).
- **Refinements are pure entry filters** layered on top (they never touch the model or its calibration):
  - decision_t ∈ {300, 450, 600, 720} s
  - spread/dislocation: `ask−bid ≥` {none, 0.015, 0.025}
  - favorite tilt: position-cost `≥` {none, 0.40, 0.60}, where position-cost = `ask` (buy) or
    `1−bid` (sell) = the executable cost of the side actually held (deep-underdog = cost < 0.15).
- Realized-settlement label `mid_close > 0.5`; clean-label filter; pooled per-(asset,day)
  **day-clustered t**. Train = days ≤ 2026-06-30, Test = days > 2026-06-30.
- **TRAIN-select the single best config; evaluate on TEST exactly once.**
- **Multiple-testing count = 44** (36 in the primary spread×favorite×dt grid + 8 additional
  `|fair−mid|` model-dislocation configs). Selection uses TRAIN pooled t only (n ≥ 30 guard).

## Reference — the calibrated baseline (dt=720, no filter)
| set | pooled t | n (asset-days) | mean $/asset-day | pos |
|---|--:|--:|--:|--:|
| TRAIN | 5.64 | 63 | 0.0491 | 52/63 |
| **TEST (OOS)** | **7.70** (sklearn) / **~5.74** (stdlib prior) | 42 | **0.0591** | 36/42 |
| — btc / eth / sol OOS | 5.58 / 3.84 / 4.09 | 495/480/460 trades | 0.070 / 0.056 / 0.046 | all pos |

This is the anchor the task references (OOS t ~5.7 stdlib / 7.70 sklearn).

## Result 1 — dislocation (wide spread) FAILS: bigger $/ct, but LOWER t, and no earlier window
Spread-conditioning raises per-trade dollars but **collapses the day-clustered t** (fewer, more
variance-heavy trades). At dt=720 the calibrated edge degrades monotonically as the spread filter
tightens:

| dt=720 spread filter | TRAIN t | OOS t | OOS mean $/ct | n |
|---|--:|--:|--:|--:|
| none (baseline) | 5.64 | **7.70** | 0.0591 | 42 |
| ≥ 0.015 | 2.39 | 4.40 | 0.108 | 39 |
| ≥ 0.025 | 0.84 | 2.62 | 0.088 | 27 |

The `|fair − mid|` model-dislocation proxy behaves identically (dt=720: OOS t 7.70 → 4.68 at
≥0.10 → 5.67 at ≥0.20; higher $/ct, lower t). **Interpretation:** the mechanism report's
"wide-book edge is bigger" fact is *already absorbed by the isotonic calibration*; re-conditioning on
dislocation only throws away trades and inflates variance. The per-trade edge does grow (mean $/ct
roughly doubles) but statistical strength drops — hypothesis (i) not supported on the metric that
matters.

## Result 2 — the window does NOT extend earlier
Neither the raw calibrated model nor any dislocation/favorite conditioning produces a robust,
train-supported edge before ~600 s. Best per-decision_t TRAIN t (no filter): dt=300 → 1.45,
dt=450 → 2.03, dt=600 → 6.08, dt=720 → 5.64. The edge only "turns on" at dt ≥ 600.

Conditioning on dislocation does **not** rescue the early window: at dt=300/450 the spread and
`|fair−mid|` filters leave TRAIN t weak (≤ ~3.2) and OOS collapses. The single eye-catching early
blip — dt=450, spread ≥ 0.025, fav ≥ 0.60 (OOS t=4.23, mean $0.155) — sits on **n=19 asset-days**
with **TRAIN t=2.48** and was **not** selected: a small-sample post-hoc artifact. **Hypothesis (ii)
REJECTED — the tradeable window stays confined to the last ~3 minutes.**

## Result 3 — favorite tilt: more $/ct, all assets positive, but NOT higher pooled t
The favorite tilt is the only refinement that improves the dollar edge while staying significant.
At dt=720:

| dt=720 favorite filter | TRAIN t | OOS t | OOS mean $/ct | pos |
|---|--:|--:|--:|--:|
| none (baseline) | 5.64 | 7.70 | 0.0591 | 36/42 |
| ≥ 0.40 | 7.04 | 8.33* | 0.0858 | — |
| ≥ 0.60 **(selected)** | **7.26** | **6.56** | **0.0756** | 34/42 |

\*fav ≥ 0.40 is a **post-hoc** disclosure — it was **not** train-selected (TRAIN 7.04 < 7.26).

## Selected refinement (single OOS verdict)
TRAIN-selection over all 44 configs picks **dt=720, spread none, favorite ≥ 0.60** (highest TRAIN t
with n ≥ 30). Single TEST evaluation:

| | pooled OOS t | n | mean $/asset-day | pos | btc / eth / sol OOS t |
|---|--:|--:|--:|--:|--:|
| **Selected (fav ≥ 0.60)** | **6.56** | 42 | **0.0756** | 34/42 | 4.46 / 3.70 / 3.22 |
| Calibrated baseline | 7.70 | 42 | 0.0591 | 36/42 | 5.58 / 3.84 / 4.09 |

## Honest verdict
- **No train-selected refinement materially beats the calibrated baseline on day-clustered t.** The
  selected favorite tilt has **higher mean $/ct (+28%, 0.076 vs 0.059)** and clears t > 3 in all three
  assets, but its **pooled OOS t (6.56) is lower** than the baseline's (7.70/5.74), because favoring
  near-ATM entries discards ~55% of trades and raises day-to-day variance.
- **Dislocation-conditioning (spread or `|fair−mid|`) makes the edge worse, not better**, on the
  t-metric — the isotonic map already captures the wide-book premium. It raises $/ct but not
  significance.
- **The tradeable window does NOT extend earlier.** The edge remains a terminal-convergence effect
  living at dt ≥ 600 s; conditioning on dislocation gives no earlier capacity. Both new hypotheses
  are rejected on the pre-registered metric.

## Recommendation
Keep the **calibrated baseline (dt=720, no dislocation filter, iso)** as the forward-tracked prior;
its OOS t ~5.7 (stdlib) is unbeaten. The **favorite ≥ 0.40–0.60 tilt is a legitimate optional SIZING
lever** (more dollars per contract, all three assets positive, still-strong significance) — but it
is a dollar-efficiency choice, not a significance upgrade, and must be sized for the added variance.
Do **not** add a spread/dislocation entry gate. Nothing here changes the forward-gate requirement.
_Propose-only. No live flag, switch, size, or order was touched._
