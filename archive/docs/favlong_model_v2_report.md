# FAVLONG fair-value model v2 — can a better fair-value model grow the OOS edge?

**Answer: yes, substantially — via empirical calibration.** Replacing the raw Gaussian
fair-value with a monotone isotonic calibration (model-fairP → empirical P(settle up),
fit on TRAIN only) roughly **doubles** the out-of-sample edge: pooled OOS day-clustered
**t 3.97 → 7.70**, mean **$0.033 → $0.059 / contract**, positive asset-days **26/42 → 36/42**,
and — for the first time — **all three assets independently clear t ≥ 2 OOS** (BTC 5.58,
ETH 3.84, SOL 4.09).

Tool: `favlong_model_v2.py` (reuses `favlongshot_edge` math: `NORM`, `KFEE`, `load_asset`;
caches at `/tmp/favlong_cache`; no rebuild from git). Taker mechanics are **identical** to
`favlongshot_edge`: take the side the executable price underprices by ≥ edge, pay
`KFEE = 0.07·p·(1−p)` per contract, label = market settlement `mid_close > 0.5`, clean-label
only (`out_proxy == outcome`), pooled per-(asset,day) day-clustered t.

## Protocol / discipline
- Fixed up front: `decision_t = 720`, `edge = 0.03` (matches the tuned baseline), sigma_mult = 1.0
  (the vol model / calibration replace the ad-hoc σ-shrink).
- Grid = **4 vol × 3 moneyness × 2 calibration = 24 variants** (the multiple-testing count).
- Select the **single** best variant by **TRAIN** pooled day-clustered t → evaluate on **TEST once**.
- Train = days ≤ 2026-06-30 (21 days); Test/OOS = days > 2026-06-30 (14 days, 42 asset-days).
- Calibration is fit **only on train rows / train outcomes** and applied to test — no look-ahead,
  no leakage. All vol/drift estimators are causal (ticks up to the decision index only).

### Variants
- **Vol σ:** `baseline` (pstdev of all causal log-returns to idx — the favlongshot estimator),
  `trailing` (pstdev of last K=90 causal log-returns), `ewma` (λ=0.94 EWMA vol), `blend` (½ baseline + ½ ewma).
- **Moneyness/drift:** `arith` (baseline `(spot−strike)/(spot·σ·√τ)`), `logn` (`ln(spot/strike)/(σ√τ)`),
  `logndrift` (`[ln(spot/strike) + (μ − ½σ²)τ]/(σ√τ)`, μ = causal mean log-return/s).
- **Calibration:** `raw` (`NORM(z)`) vs `iso` (isotonic map fairP→empirical P(up), sklearn PAVA,
  fit pooled on train).

## Selection (TRAIN only) — top variants by pooled day-clustered t
| variant | train t | mean $/ct | pos-days |
|---|---|---|---|
| **baseline / logndrift / iso  (SELECTED)** | **5.64** | 0.0491 | 52/63 |
| baseline / arith / iso | 5.53 | 0.0494 | 50/63 |
| baseline / logn / iso | 5.53 | 0.0494 | 50/63 |
| blend / arith / iso | 5.17 | 0.0561 | 52/63 |
| ewma / arith / iso | 4.91 | 0.0405 | 45/63 |
| baseline / logndrift / raw | 4.38 | 0.0316 | 43/63 |
| … (all 8 `iso` variants rank above every `raw` variant) | | | |
| baseline / arith / raw (≈ untuned baseline, σ=1.0) | 2.09 | 0.0115 | 36/63 |

The isotonic family sweeps the top 8 on train; the calibration is the dominant factor.
Moneyness/drift is second-order (`logndrift` edges `arith` by ~0.1 t). **Selected: `baseline / logndrift / iso`.**

## OOS — single evaluation of the selected variant vs tuned baseline
| metric | **SELECTED (baseline/logndrift/iso)** | tuned baseline (arith/σ0.8/raw) |
|---|---|---|
| pooled OOS day-clustered t | **7.70** | 3.97 |
| pooled mean $/contract | **+0.0591** | +0.0332 |
| positive asset-days | **36/42** | 26/42 |
| BTC OOS t (n) | **5.58** (495) | 3.74 (553) |
| ETH OOS t (n) | **3.84** (480) | 1.85 (550) |
| SOL OOS t (n) | **4.09** (460) | 1.42 (598) |

The tuned-baseline row was reproduced inside this exact harness and matches
`favlong_tuning_report.md` to the decimal (t = 3.97, $0.0332), confirming an apples-to-apples
comparison. Note the calibrated model trades **fewer** windows (495/480/460 vs 553/550/598)
yet earns more per contract at higher t — it is more *selective and accurate*, not just more active.

## Per-asset OOS t of every variant (post-hoc disclosure; NOT the selection basis)
Every `iso` variant lands at OOS pooled t ≈ 5.5–7.7; every `raw` variant at ≈ 2.2–4.9. The
result does not hinge on the specific vol/drift pick — it hinges on calibration.

| vol | moneyness | raw OOS t | iso OOS t |
|---|---|---|---|
| baseline | arith | 2.16 | 7.02 |
| baseline | logn | 2.16 | 7.08 |
| baseline | logndrift | 4.30 | **7.70 (selected)** |
| trailing | arith/logn | 3.08 | 5.5 |
| trailing | logndrift | 4.44 | 5.82 |
| ewma | arith/logn | 3.33 | 5.9 |
| ewma | logndrift | 4.91 | 6.47 |
| blend | arith/logn | 2.84 | 6.1 |
| blend | logndrift | 4.47 | 6.27 |

## What the calibration actually corrects (train, 4850 windows)
The isotonic map is smooth, monotone and densely populated (hundreds of windows per bin). It
reveals a systematic mis-shape of the raw Gaussian: in the **0.2–0.5** model-probability band the
raw fairP reads a few points **too high** vs realized settlement, and the map shrinks it — exactly
the region where the contrarian mispricing trades live.

| model fairP bin | n | empirical P(up) | isotonic pred |
|---|---|---|---|
| 0.05–0.10 | 279 | 0.029 | 0.020 |
| 0.10–0.15 | 225 | 0.044 | 0.052 |
| 0.20–0.30 | 289 | 0.156 | 0.130 |
| 0.30–0.40 | 232 | 0.280 | 0.236 |
| 0.40–0.50 | 236 | 0.462 | 0.439 |
| 0.60–0.70 | 239 | 0.699 | 0.708 |
| 0.80–0.90 | 366 | 0.902 | 0.920 |

## Robustness checks
- **Pooled vs per-asset calibration:** fitting a separate isotonic map on each asset's own train
  data gives pooled OOS **t = 7.72** (BTC 5.16 / ETH 3.52 / SOL 4.90) — essentially identical to
  the pooled-calibration t = 7.70. The gain is **not** a pooling artifact.
- **Whole-family coherence:** all 8 iso variants beat all 16 raw variants on both train and test;
  the selected variant is not a fragile corner.
- **Multiple testing:** 24 variants scored on train. Even a conservative Bonferroni adjustment
  (×24) leaves the OOS t ≈ 7.7 overwhelmingly significant, and selection was on train with a single
  test evaluation.

## Verdict (honest)
The empirical-calibration idea — flagged as the highest-value lever — **delivers a genuine
step-change over the tuned baseline (t 3.97 → 7.70; ~3.3¢ → ~5.9¢/ct)**, and it does so in the
qualitatively important way: **all three assets now clear t ≥ 2 OOS independently** (previously
only BTC), and 36/42 asset-days are positive. It is robust to the calibration-pooling choice and
to the vol/drift estimator. Better *vol* estimators (trailing/ewma/blend) and the drift/lognormal
terms are **second-order** — they help the raw model modestly but the calibration dominates and
partly subsumes them; `logndrift` is retained only because it is the marginal best partner.

**Caveats (do not oversell):** still a small per-contract taker edge (~6¢/ct) requiring real
execution; the calibration map is fit on 21 train days and the favorite-longshot magnitude is a
known effect that **can decay**, so the map itself needs periodic refit and the pre-registered
**forward gate (day-clustered t ≥ 2 over ≥ 10 forward days) remains mandatory** before any live
sizing. The OOS window is 14 calendar days / 42 asset-days — a large t but a modest calendar span.
PROPOSE-ONLY: no live flag/switch/size is touched on the basis of this study.

## Selected model
`decision_t=720, edge=0.03, vol=baseline (causal realized), moneyness=logndrift (lognormal + causal
drift), calibration=isotonic (fairP→empirical P(up), fit on TRAIN, pooled)`.
Reproduce: `FAVLONG_CACHE=/tmp/favlong_cache python3 favlong_model_v2.py`.
