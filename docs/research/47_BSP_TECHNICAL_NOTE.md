# When does burst suppression probability beat a threshold ratio?

**An independent implementation of the BSP state-space estimator, validated against an exact solver, swept
across window lengths against simulated ground truth, and scored on forward prediction in 521
post-cardiac-arrest recordings.**

*Self-contained technical note. Code: `analysis/bsp.py` (estimator + unit tests),
`analysis/bsp_validate_exact.py` (exact-solver validation), `analysis/bsp_window_sweep.py` (§3b),
`analysis/bsp_window_real.py` (§3c).*

---

## Summary

Chemali, Ching, Purdon, Solt and Brown (*J Neural Eng* 2013, **PMID 24018288**) introduced burst suppression
probability (BSP) to replace thresholding-and-segmentation ratios, which in their words "provide no framework
for statistical inference". We implemented BSP from the published specification and report five findings.
The first two concern whether BSP improves an aggregate; the last three concern the question that actually
distinguishes it — at what time scale, and used how, it stops being a threshold ratio.

1. **At per-recording aggregation, BSP and a crude threshold ratio are interchangeable.** Correlation
   **r = 0.988**; BSP does not discriminate outcome better (out-of-bag increment **−0.010 [−0.021, +0.004]**;
   full BSP feature set **−0.018 [−0.064, +0.016]**), in 385 comatose post-cardiac-arrest patients with
   Cerebral Performance Category outcomes.
2. **The Gaussian approximation degrades sharply at abrupt transitions.** Validated against an exact grid
   forward–backward solution of the same model, the approximation agrees to **≤0.014** in steady and smoothly
   varying regimes but deviates by up to **0.775** at a step change — the regime where instantaneous tracking
   matters most.

3. **Below about 30 s the two stop being interchangeable, and the crossover is between 15 and 30 s.**
   Against simulated ground truth, correlation with the ratio is ≥ 0.98 at 60 s windows and longer, falls to
   0.956 at 15 s and 0.728 at 1 s; the online BSP overtakes the ratio in accuracy at 15 s and is **3.1× more
   accurate at 1 s**. The r = 0.988 above is the far end of a curve that turns at about half a minute.
4. **The short-window advantage is borrowed strength, not the model.** Given *exactly the same data* as the
   ratio, BSP is never more accurate at any window length (1.007–1.087, worsening as windows shorten). What it
   buys is the ability to use data from outside the window — which a monitor genuinely has.
5. **On real EEG, predicting forward, a threshold ratio is never the best predictor at any window length**,
   and the window-averaged causal BSP beats it at every one of them. But the summary matters more than the
   window: the *instantaneous* BSP loses to the ratio from 300 s down to 4 s.

Nothing here argues against BSP. Together these say something more precise: **BSP's value is time resolution
and per-timepoint uncertainty, not a better aggregate number** — the equivalence with a ratio holds only for
windows of about a minute or more, what breaks it is access to adjacent data rather than the model itself, and
if you want an estimate at a transition the Gaussian approximation is the wrong tool.

---

## 1. The model, as specified

    observation   n_t ~ Binomial(N_t, p_t)      n_t suppressed frames of N_t in bin t
    link          p_t = 1 / (1 + exp(-x_t))
    state         x_t = x_{t-1} + eps_t,        eps_t ~ N(0, sigma^2)

Estimated by a nonlinear recursive filter forward (Newton on the binomial log-likelihood per bin), a
Rauch–Tung–Striebel fixed-interval smoother backward, and EM for sigma² from the smoothed lag-one covariances.

**A numerical detail that is load-bearing.** When a bin is fully suppressed or fully bursting (n_t = N_t or
n_t = 0), the binomial curvature N·p(1−p) vanishes, the Hessian degenerates to the prior term alone, and an
undamped Newton step overshoots by hundreds of log-odds and then oscillates. **This is the regime burst
suppression lives in.** Our first implementation was stable at small sigma² and diverged once EM raised it,
returning BSP = 0.001 for a clean 0 → 100 % step. Damping with a backtracking line search and a step clamp
fixes it. Anyone reimplementing this should expect the same failure.

---

## 2. Validation against an exact solver

Unit tests against analytically known cases are necessary but not sufficient — they were written by the same
author as the code. We therefore discretised the latent state on a fine grid and ran exact HMM
forward–backward on the identical model, sharing no code with the estimator.

| case | max abs. deviation from exact |
|---|---|
| mid-range (p ≈ 0.5) | 0.0000 |
| extreme low / high (p ≈ 0, p ≈ 1) | 0.0137 |
| sparse bins (N = 2) | 0.0000 |
| realistic noisy ramp | 0.0107 |
| **abrupt step 0 → 1** | **0.7754** |

The failure at transitions is a property of the Gaussian approximation, not a coding error: the true posterior
is sharply non-Gaussian where the state jumps.

**Does it contaminate a per-recording summary?** No, and we checked rather than assumed. Across steady,
drifting, occasionally-jumping and constantly-jumping series, the per-recording **mean** BSP differs from exact
by **≤0.0009**. The pointwise error averages out.

---

## 3. BSP versus the ratio, in 385 post-arrest patients

I-CARE cohort, our own detector on the raw EEG at hour 24 after arrest, outcome CPC 3–5 (61.0 % poor).

| model | cross-validated AUC |
|---|---|
| crude threshold ratio | **0.704** |
| BSP mean | 0.698 |
| BSP mean + p90 + SD + fraction > 0.5 | 0.693 |

Out-of-bag bootstrap increments over the ratio: **−0.010 [−0.021, +0.004]** (BSP mean) and
**−0.018 [−0.064, +0.016]** (full set). Correlation of BSP mean with the ratio: **r = 0.988**.

**Interpretation.** Over a whole recording, the state-space estimate and the raw fraction converge — which is
what one should expect, since both estimate the same time-averaged quantity and the smoothing that distinguishes
them is integrated away. The comparison exercises none of BSP's advertised advantages.

---

## 3b. Where the equivalence breaks down: a window-length sweep against ground truth

This is the experiment §5.3 of the previous version named as unanswered. It has to be simulation: real EEG has
no ground-truth instantaneous probability, so real data can show only whether two estimators **agree**, never
which is **right**. Seven regimes × 12 seeds × 1,200 one-second bins — two constants, two random walks (the
model's own assumption), and three processes the model does not assume: a step, a ramp, an oscillation.

Four estimators, and the distinction between them is the point. `ratio` is the pooled fraction inside the
window. `bsp_win` refits BSP on the window's data **alone** — the like-for-like comparison, identical data in
and identical summary out. `bsp_causal` is the forward-filtered estimate, using no observation after the
window. `bsp_full` is the smoother fitted to the whole series and is **not causal**; it is labelled as such
everywhere it appears.

RMSE against the true window-mean p:

| window | ratio | bsp_win | ewma tuned | ewma oracle | bsp_causal | bsp_full (non-causal) | corr(ratio, bsp) |
|---|---|---|---|---|---|---|---|
| 600 s | 0.0045 | 0.0046 | 0.0104 | 0.0038 | 0.0053 | 0.0050 | — |
| 300 s | 0.0065 | 0.0065 | 0.0140 | 0.0057 | 0.0073 | 0.0069 | 0.983 |
| 120 s | 0.0103 | 0.0105 | 0.0219 | 0.0096 | 0.0130 | 0.0108 | 0.994 |
| 60 s | 0.0149 | 0.0149 | 0.0274 | 0.0134 | 0.0176 | 0.0148 | 0.989 |
| 30 s | 0.0213 | 0.0209 | 0.0319 | 0.0181 | 0.0224 | 0.0189 | 0.979 |
| 15 s | 0.0303 | 0.0302 | 0.0356 | 0.0228 | **0.0276** | 0.0226 | 0.956 |
| 8 s | 0.0417 | 0.0427 | 0.0382 | 0.0269 | **0.0317** | 0.0250 | 0.916 |
| 4 s | 0.0587 | 0.0610 | 0.0401 | 0.0303 | **0.0348** | 0.0264 | 0.862 |
| 2 s | 0.0826 | 0.0894 | 0.0414 | 0.0324 | **0.0368** | 0.0271 | 0.797 |
| 1 s | 0.1167 | 0.1148 | 0.0423 | 0.0337 | **0.0382** | 0.0276 | 0.728 |

**Interchangeable at 60 s and longer; diverging at 30 s and below; crossover between 15 and 30 s.**

**The advantage is borrowed strength, not the model.** `bsp_win` — same data as the ratio — is never more
accurate at any window: 1.014, 1.007, 1.028, 1.017, 1.021, 1.047, 1.057, 1.081, 1.087 from 600 s down to 2 s.
It gets *worse* as the window shortens. (At 1 s BSP is undefined on a single bin and degenerates to the ratio;
that entry is bookkeeping.) Everything BSP gains at short windows, it gains by using data from outside them.

**Is it worth more than exponential smoothing?** A fair question, because the state equation *is* a random
walk and an EWMA is very nearly its optimal filter, so beating a one-second ratio proves nothing. Two
baselines bracket it: one tuned causally by one-step-ahead error on the first 30 % (deployable by anyone), one
handed the best constant from the true p (a ceiling, not a method). `bsp_causal` beats the deployable
baseline at **every** window — RMSE ratios 0.513, 0.522, 0.596, 0.642, 0.702, 0.775, 0.828, 0.867, 0.890,
0.903 — and loses to the ceiling everywhere. **The state-space machinery earns real accuracy over what a
practitioner would otherwise write, without exhausting what smoothing could in principle deliver.**

**Where the smoothing pays, and where it costs.** `bsp_win / ratio` by regime:

| regime | 600 s | 120 s | 30 s | 8 s | 2 s |
|---|---|---|---|---|---|
| constant 0.50 | 0.998 | 0.993 | 0.981 | 0.954 | **0.851** |
| constant 0.90 | 0.973 | 1.035 | 0.980 | 1.215 | 1.238 |
| random walk, slow | 1.023 | 1.004 | 0.994 | 0.986 | 0.994 |
| random walk, fast | 1.029 | 1.009 | 1.031 | 1.069 | 1.291 |
| **step** | **1.324** | **1.251** | **1.214** | **1.503** | **1.851** |
| ramp | 0.967 | 0.990 | 0.984 | 0.997 | 0.944 |
| oscillation | 0.982 | 1.038 | 1.050 | 0.982 | 1.007 |

Smoothing pays where the state is smooth and costs where it jumps. The step penalty reaches **1.851** and
persists even at 600 s windows — the same defect §2 found as a 0.775 pointwise deviation, reached here by a
completely different route.

**Does the credible band cover?** The paper's stated motivation is that ratios "provide no framework for
statistical inference", and an interval is only worth having if it covers. Pooled coverage of the true p_t is
**0.979 against a nominal 0.950** — the band **over-covers**, which is the safe direction, in six of seven
regimes (0.988–0.996). The exception is the fast random walk at **0.916**: where the state moves fastest, the
interval is too narrow. Fitted σ² tracks the truth sensibly (0.0062 for a constant, 0.0474 for the fast walk).

---

## 3c. On real EEG: predicting forward instead of scoring against truth

Simulation can say which estimator is *right*; real EEG cannot. It can answer a question that needs no ground
truth and is closer to the clinical use: **given everything observed so far, which estimator best predicts
what the EEG does next?** Binomial log-loss on the next window, strictly causal — σ² fitted by EM on the first
30 % of each recording and frozen, and only windows entirely after that burn-in scored, so nothing sees its
own future. 521 I-CARE recordings, median length 3,600 s, median burden 0.338.

| window | ratio | cumulative | ewma tuned | ewma oracle | bsp_last | **bsp_mean** | best |
|---|---|---|---|---|---|---|---|
| 300 s | 0.3154 | 0.3255 | 0.4878 | 0.3106 | 0.5738 | **0.3146** | bsp_mean |
| 120 s | 0.2864 | 0.3118 | 0.4416 | 0.2827 | 0.5184 | **0.2855** | bsp_mean |
| 60 s | 0.2811 | 0.3072 | 0.4350 | 0.2727 | 0.5100 | **0.2797** | bsp_mean |
| 30 s | 0.2899 | 0.3091 | 0.4335 | 0.2724 | 0.5058 | **0.2866** | bsp_mean |
| 15 s | 0.3145 | 0.3061 | 0.4204 | 0.2676 | 0.4934 | **0.3030** | bsp_mean |
| 8 s | 0.3505 | **0.3052** | 0.4006 | 0.2657 | 0.4764 | 0.3234 | cumulative |
| 4 s | 0.4163 | **0.3046** | 0.3695 | 0.2630 | 0.4468 | 0.3491 | cumulative |
| 2 s | 0.5145 | **0.3043** | 0.3245 | 0.2598 | 0.4014 | 0.3698 | cumulative |
| 1 s | 0.5615 | 0.3042 | **0.2861** | 0.2542 | 0.3370 | 0.3370 | ewma |

**The trailing ratio is never the best predictor at any window length.** Paired per-recording, `bsp_mean`
beats it at every window with bootstrap CIs excluding zero, from +0.0008 [+0.0004, +0.0013] at 300 s to
+0.2246 [+0.2032, +0.2479] at 1 s. One qualification: at 300 s it wins on average but on only **44 %** of
recordings, so the mean is carried by a minority with large gains; win rates reach ~74 % at ≤8 s.

**The summary matters more than the window.** `bsp_mean` averages the causal filter over the window;
`bsp_last` takes its value at the final bin. At 300 s they score **0.3146 versus 0.5738**, and `bsp_last`
*loses* to the trailing ratio from 300 s down to 4 s. In burst suppression the filtered probability at any
instant is usually near 0 or 1, and a confident value at one bin is a poor stand-in for the next five minutes,
which will contain both states. **An instantaneous estimate is the wrong object for predicting an interval** —
which is a statement about how to use BSP, not a defect in it.

**Two places the simulation does not carry over.** The practical-EWMA result is weaker on real data:
`bsp_mean` leads from 300 s to 8 s, ties at 4 s, and **loses at 2 s and 1 s**. And the cumulative average is
strong and nearly flat (0.3042–0.3255 everywhere), winning outright at ≤8 s — over these horizons real
recordings are close to stationary, so at short horizons nothing beats the patient's overall level so far.

Rerun without the interior-gap exclusion (572 recordings), every verdict is identical and every value moves by
less than 0.007.

---

## 4. What this means in practice

- **If you need a per-recording exposure** — an aggregate for a regression, a cohort comparison, a
  prognostic score — **a threshold ratio is sufficient**, and the state-space machinery buys nothing. This is
  useful because it means results built on threshold ratios are not weakened by that choice. The same holds
  for **any window of about a minute or more**: at 60 s and longer the two agree at r ≥ 0.98.
- **Below about 30 s, use BSP** — that is where the two part company, with the accuracy crossover between
  15 and 30 s and BSP 3.1× more accurate at 1 s. But be clear about *why* it wins: not because the model
  extracts more from the window, which it does not, but because it can use the data on either side of it.
  A window-wise summary that cannot see its neighbours gains nothing from the model.
- **Average the filter over your window; do not read it at a point.** On real EEG this is the single largest
  effect in the whole comparison — 0.3146 versus 0.5738 at 300 s — and it runs the opposite way to intuition:
  the instantaneous estimate, the thing BSP uniquely provides, is the *worst* predictor of an interval,
  because a value near 0 or 1 at one bin cannot represent five minutes containing both states.
- **Check a cheap baseline before reaching for the model.** A causally-tuned EWMA is beaten by BSP in
  simulation at every window, but on real EEG it wins at 1–2 s. And the cumulative average — the patient's
  overall level so far — beats everything at windows of 8 s and below, because real recordings are close to
  stationary over those horizons.
- **If you need uncertainty as well as an estimate** — closed-loop control, formally comparing two moments in
  one recording — **only BSP provides it**, and the ratio cannot. The band over-covers (0.979 against a
  nominal 0.950) in every regime except the fastest-moving one, where it under-covers at 0.916.
- **If your interest is transitions specifically** — onset of suppression, emergence, response to a bolus —
  **use the exact posterior, not the Gaussian approximation.** That is where the approximation is worst and
  where the question is sharpest, and two independent routes now agree on it: a 0.775 pointwise deviation
  against the exact solver, and a step-regime accuracy penalty reaching 1.851 that persists even at 600 s.

---

## 5. Limitations

1. This is our implementation from the published description; the authors' code is not public. Any discrepancy
   with the original is ours.
2. The comparison is one cohort, one timepoint (hour 24), one detector configuration (5 µV / 8 µV amplitude
   threshold, 0.1 s frames, ≥0.5 s runs, bipolar longitudinal montage).
3. The exact-solver validation used a fine but finite grid; the reported deviations are lower bounds on
   agreement, not exact.
4. The window-length sweep (§3b) is simulation. Its regimes are chosen to include processes the model does not
   assume, but they are not real EEG, and §3c shows two places where they do not carry over — real recordings
   are more persistent and more bursty than any of them.
5. §3c scores binomial log-loss with predictions clipped to [1e-4, 1−1e-4]. A proper scoring rule punishes
   confident-and-wrong predictions heavily, which is why `bsp_last` fares so badly at long windows; the
   *ranking* of the window-averaged methods does not depend on that choice, but the magnitude of `bsp_last`'s
   penalty does.
6. §3c conditions on the interior-gap exclusion, which is **outcome-related** (75.3 % poor outcome among
   excluded recordings versus 61.2 % kept). This arm makes no prognostic claim, and the unfiltered rerun
   changes no verdict, but the selection is real and is not hidden.
7. `bsp_causal` in §3b fits σ² on the full series while filtering causally — a small acknowledged leak.
   §3c has no such leak: σ² comes from the first 30 % only.

---

## 6. Reproducing

```bash
python analysis/bsp.py                 # estimator + 7 unit tests against known answers
python analysis/bsp_validate_exact.py  # exact grid forward-backward comparison
SWEEP_T=1200 SWEEP_SEEDS=12 python analysis/bsp_window_sweep.py   # Sec. 3b, simulation sweep
python analysis/bsp_window_real.py                                # Sec. 3c, real EEG (needs the
                                                                  # suppression series and keep-list)
ICARE_KEEP=none python analysis/bsp_window_real.py                # Sec. 3c unfiltered sensitivity
```

The per-second suppression series §3c needs is produced by `analysis/icare_topography.py`, and the
interior-gap keep-list by `analysis/icare_seq_exclusions.py`.
