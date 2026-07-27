# When does burst suppression probability beat a threshold ratio?

**An independent implementation of the BSP state-space estimator, validated against an exact solver, applied to
385 post-cardiac-arrest patients.**

*Self-contained technical note. Code: `analysis/bsp.py` (estimator + unit tests),
`analysis/bsp_validate_exact.py` (exact-solver validation).*

---

## Summary

Chemali, Ching, Purdon, Solt and Brown (*J Neural Eng* 2013, **PMID 24018288**) introduced burst suppression
probability (BSP) to replace thresholding-and-segmentation ratios, which in their words "provide no framework
for statistical inference". We implemented BSP from the published specification and report two findings:

1. **At per-recording aggregation, BSP and a crude threshold ratio are interchangeable.** Correlation
   **r = 0.988**; BSP does not discriminate outcome better (out-of-bag increment **−0.010 [−0.021, +0.004]**;
   full BSP feature set **−0.018 [−0.064, +0.016]**), in 385 comatose post-cardiac-arrest patients with
   Cerebral Performance Category outcomes.
2. **The Gaussian approximation degrades sharply at abrupt transitions.** Validated against an exact grid
   forward–backward solution of the same model, the approximation agrees to **≤0.014** in steady and smoothly
   varying regimes but deviates by up to **0.775** at a step change — the regime where instantaneous tracking
   matters most.

Neither finding argues against BSP. Together they say something more precise: **BSP's value is time resolution
and per-timepoint uncertainty, not a better aggregate number** — and if you want it at a transition, the
Gaussian approximation is the wrong tool.

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

## 4. What this means in practice

- **If you need a per-recording exposure** — an aggregate for a regression, a cohort comparison, a
  prognostic score — **a threshold ratio is sufficient**, and the state-space machinery buys nothing. This is
  useful because it means results built on threshold ratios are not weakened by that choice.
- **If you need an instantaneous estimate with uncertainty** — closed-loop control, tracking depth in real
  time, formally comparing two moments in one recording — **only BSP provides it**, and the ratio cannot.
- **If your interest is transitions specifically** — onset of suppression, emergence, response to a bolus —
  **use the exact posterior, not the Gaussian approximation.** That is where the approximation is worst and
  where the question is sharpest.

---

## 5. Limitations

1. This is our implementation from the published description; the authors' code is not public. Any discrepancy
   with the original is ours.
2. The comparison is one cohort, one timepoint (hour 24), one detector configuration (5 µV / 8 µV amplitude
   threshold, 0.1 s frames, ≥0.5 s runs, bipolar longitudinal montage).
3. `r = 0.988` is specific to *whole-recording* aggregation. Shorter windows would give BSP more room, and we
   have not characterised where the equivalence breaks down as window length falls — that is the obvious next
   experiment and it is directly answerable with this code.
4. The exact-solver validation used a fine but finite grid; the reported deviations are lower bounds on
   agreement, not exact.

---

## 6. Reproducing

```bash
python analysis/bsp.py                 # estimator + 7 unit tests against known answers
python analysis/bsp_validate_exact.py  # exact grid forward-backward comparison
```
