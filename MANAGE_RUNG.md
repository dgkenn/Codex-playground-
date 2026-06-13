# RUNG 4 (MANAGE) optimization -- Phase-C deep dive (2026-06-13)

TOP deployable Phase-C priority. Find the best rung-4 MANAGE strategy for the Kalshi 15-min crypto box bot's strand-handling ladder.

**Method.** BTC tape, IS=first 60% (549 windows) / OOS=last 40% (367 windows). IS runs EXCLUDE the GBM gate (leakage avoidance, matching the baseline study); OOS runs include the GBM gate (OOS AUC=0.883, thresh=0.163). All sizing variants reuse the exact `walk()` inner loop (R1 t36 + R2 GBM + R3 sell-cheap<0.30 + R5 h=150) from `ladder_baseline_study.py`; rung-4 streak is OFF and replaced by the variant's continuous size multiplier on the OPENING leg (both legs inherit it). Helpers (tstat/sortino/recovery/ulcer/var95/cvar95/ir/...) imported from `box_policy_ab.py`. Backtests SCREEN only.

## References

- **(a) LIVE streak-guard** = combined ladder WITH `--strand-scaledown 0.75,0.5,0.25` (deployed today). OOS net **+3.50c/win**, MaxDD 385.5c, CVaR95 60.27c, strand 37.9%.

- **(b) BASELINE drop-R4** = combined ladder with rung 4 dropped entirely (the leave-one-out ablation winner). OOS net **+4.11c/win**, MaxDD 457.1c, CVaR95 65.03c, strand 37.9%. This is the bar to beat: the ablation showed dropping R4 is itself an improvement.

## Ranked variants (OOS, full A/B metric set)

| Variant | IS net | OOS net | Sharpe | Sortino | Skew | Kurt | Recov | Ulcer | VaR95 | CVaR95 | IR-vs-base | Expect | TUW% | MaxDD | Strand% | PF |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| V2 Kelly lam1.0 | +3.39 | +4.13 | +0.15 | +0.15 | -0.02 | +1.13 | +3.16 | 199.61 | 43.90 | 58.63 | +0.00 | +1.01 | 78.5 | 479.5 | 37.9 | 1.49 |
| (b) BASELINE drop-R4 (ablation win) | +4.06 | +4.11 | +0.14 | +0.13 | -0.18 | +1.11 | +3.30 | 183.33 | 50.70 | 65.03 | +nan | +0.96 | 79.6 | 457.1 | 37.9 | 1.45 |
| V2 Kelly lam0.5 | +3.28 | +4.10 | +0.15 | +0.15 | -0.01 | +1.14 | +3.32 | 184.81 | 42.37 | 56.78 | -0.00 | +1.03 | 78.5 | 452.8 | 37.9 | 1.50 |
| V1 GBM 1-p*3 fl0.0 | +3.89 | +4.07 | +0.14 | +0.14 | -0.13 | +1.06 | +3.24 | 185.71 | 48.47 | 62.82 | -0.03 | +0.98 | 79.8 | 461.8 | 37.9 | 1.46 |
| V1 GBM 1-p*3 fl0.25 | +3.87 | +4.07 | +0.14 | +0.14 | -0.13 | +1.06 | +3.24 | 185.71 | 48.47 | 62.82 | -0.03 | +0.98 | 79.8 | 461.8 | 37.9 | 1.46 |
| V1 GBM 1-p*3 fl0.5 | +3.89 | +4.07 | +0.14 | +0.14 | -0.13 | +1.06 | +3.24 | 185.71 | 48.47 | 62.82 | -0.03 | +0.98 | 79.8 | 461.8 | 37.9 | 1.46 |
| V1 GBM 1-p*4 fl0.5 | +3.85 | +4.06 | +0.14 | +0.14 | -0.12 | +1.05 | +3.22 | 186.48 | 47.54 | 62.20 | -0.03 | +0.99 | 79.8 | 462.7 | 37.9 | 1.46 |
| V1 GBM 1-p*4 fl0.0 | +3.81 | +4.06 | +0.14 | +0.14 | -0.12 | +1.05 | +3.22 | 186.53 | 47.54 | 62.18 | -0.03 | +0.99 | 79.8 | 463.3 | 37.9 | 1.46 |
| V1 GBM 1-p*4 fl0.25 | +3.83 | +4.06 | +0.14 | +0.14 | -0.12 | +1.05 | +3.22 | 186.53 | 47.54 | 62.18 | -0.03 | +0.99 | 79.8 | 463.3 | 37.9 | 1.46 |
| V1 GBM 1-p*5 fl0.25 | +3.78 | +4.05 | +0.14 | +0.14 | -0.11 | +1.04 | +3.20 | 187.32 | 47.67 | 61.64 | -0.03 | +0.99 | 79.6 | 464.7 | 37.9 | 1.46 |
| V1 GBM 1-p*5 fl0.0 | +3.76 | +4.05 | +0.14 | +0.14 | -0.11 | +1.04 | +3.20 | 187.36 | 47.67 | 61.64 | -0.03 | +0.99 | 79.6 | 464.9 | 37.9 | 1.46 |
| V1 GBM 1-p*5 fl0.5 | +3.81 | +4.05 | +0.14 | +0.14 | -0.11 | +1.04 | +3.20 | 187.92 | 47.67 | 61.74 | -0.03 | +0.99 | 79.6 | 464.6 | 37.9 | 1.46 |
| V1 GBM 1-p*6 fl0.25 | +3.75 | +4.04 | +0.14 | +0.14 | -0.10 | +1.03 | +3.18 | 188.14 | 46.85 | 61.14 | -0.03 | +1.00 | 79.6 | 465.5 | 37.9 | 1.46 |
| V1 GBM 1-p*6 fl0.0 | +3.72 | +4.04 | +0.14 | +0.14 | -0.09 | +1.03 | +3.18 | 188.21 | 46.85 | 61.11 | -0.03 | +1.00 | 79.6 | 466.4 | 37.9 | 1.46 |
| V1 GBM 1-p*6 fl0.5 | +3.78 | +4.03 | +0.14 | +0.14 | -0.10 | +1.05 | +3.17 | 189.39 | 46.85 | 61.32 | -0.03 | +1.00 | 79.6 | 466.7 | 37.9 | 1.46 |
| V1 GBM 1-p*8 fl0.5 | +3.74 | +4.02 | +0.14 | +0.14 | -0.09 | +1.05 | +3.15 | 190.71 | 46.50 | 60.61 | -0.03 | +1.00 | 79.3 | 468.1 | 37.9 | 1.46 |
| V1 GBM 1-p*8 fl0.0 | +3.64 | +4.02 | +0.14 | +0.14 | -0.07 | +1.01 | +3.15 | 189.86 | 46.39 | 60.19 | -0.03 | +1.00 | 79.3 | 468.3 | 37.9 | 1.46 |
| V1 GBM 1-p*8 fl0.25 | +3.66 | +4.01 | +0.14 | +0.14 | -0.08 | +1.02 | +3.14 | 191.14 | 46.39 | 60.36 | -0.03 | +1.00 | 79.3 | 469.5 | 37.9 | 1.46 |
| V5 hybrid GBMk5 cut0.5@0.1 | +3.69 | +3.68 | +0.14 | +0.14 | +0.07 | +1.54 | +3.22 | 166.70 | 41.03 | 55.35 | -0.07 | +1.00 | 80.7 | 419.9 | 37.9 | 1.47 |
| V5 hybrid GBMk4 cut0.25@0.1 | +3.72 | +3.61 | +0.14 | +0.14 | +0.13 | +1.91 | +3.34 | 154.59 | 40.01 | 54.77 | -0.06 | +1.01 | 81.7 | 396.6 | 37.9 | 1.49 |
| V5 hybrid GBMk5 cut0.5@0.05 | +3.67 | +3.55 | +0.14 | +0.14 | +0.15 | +1.59 | +3.53 | 136.85 | 40.28 | 52.64 | -0.08 | +0.99 | 81.5 | 369.4 | 37.9 | 1.47 |
| (a) LIVE streak-guard 0.75/.5/.25 | +3.76 | +3.50 | +0.13 | +0.13 | -0.07 | +2.02 | +3.33 | 158.48 | 43.27 | 60.27 | -0.08 | +0.96 | 81.5 | 385.5 | 37.9 | 1.45 |
| V2 Kelly lam0.25 | +2.18 | +3.42 | +0.17 | +0.17 | -0.14 | +1.75 | +4.51 | 123.12 | 30.38 | 45.73 | -0.05 | +1.13 | 77.1 | 278.8 | 37.9 | 1.57 |
| V3 tox+GBM blend(.5) k5 fl.25 | +3.25 | +3.35 | +0.13 | +0.12 | -0.14 | +1.64 | +2.96 | 166.64 | 43.99 | 57.76 | -0.12 | +0.92 | 79.6 | 415.5 | 37.9 | 1.44 |
| V3 tox 1-p*3 fl0.25 | +3.29 | +3.25 | +0.13 | +0.12 | -0.20 | +1.86 | +2.93 | 164.03 | 42.03 | 58.87 | -0.12 | +0.94 | 79.8 | 407.7 | 37.9 | 1.43 |
| V6 AvSt GBMk5 g1.0 dec0.5 | +2.84 | +2.95 | +0.14 | +0.14 | +0.18 | +2.37 | +3.54 | 115.27 | 33.73 | 47.21 | -0.11 | +0.99 | 81.5 | 304.9 | 37.9 | 1.47 |
| V3 tox 1-p*5 fl0.25 | +2.75 | +2.76 | +0.12 | +0.11 | -0.24 | +2.39 | +2.56 | 158.47 | 41.04 | 56.30 | -0.13 | +0.93 | 80.9 | 396.4 | 37.9 | 1.40 |
| V6 AvSt GBMk5 g2.0 dec0.5 | +2.28 | +2.36 | +0.13 | +0.13 | +0.42 | +4.03 | +3.97 | 76.27 | 26.50 | 40.16 | -0.12 | +0.99 | 81.7 | 218.1 | 37.9 | 1.48 |
| V6 AvSt GBMk4 g2.0 dec0.7 | +2.14 | +2.07 | +0.13 | +0.13 | +0.21 | +2.81 | +3.40 | 81.39 | 24.48 | 35.48 | -0.13 | +0.98 | 81.7 | 224.1 | 37.9 | 1.45 |
| V4 Bayes 1/(1+2.0q)^2.0 dec0.5 | +1.97 | +1.89 | +0.12 | +0.12 | +0.46 | +5.46 | +4.13 | 56.97 | 20.72 | 36.41 | -0.12 | +0.97 | 82.6 | 167.4 | 37.9 | 1.47 |
| V4 Bayes 1/(1+4.0q)^2.0 dec0.5 | +1.40 | +1.28 | +0.10 | +0.10 | +0.61 | +8.46 | +3.74 | 42.55 | 16.88 | 29.56 | -0.13 | +0.96 | 82.6 | 125.5 | 37.9 | 1.46 |
| V4 Bayes 1/(1+4.0q)^2.0 dec0.7 | +1.10 | +0.92 | +0.11 | +0.11 | +0.52 | +6.54 | +3.73 | 29.75 | 11.89 | 18.82 | -0.14 | +0.96 | 83.7 | 90.8 | 37.9 | 1.45 |
| V4 Bayes 1/(1+8.0q)^2.0 dec0.5 | +0.96 | +0.79 | +0.08 | +0.08 | +0.78 | +12.63 | +2.96 | 35.23 | 10.57 | 22.92 | -0.14 | +0.95 | 84.2 | 97.9 | 37.9 | 1.43 |

(IR-vs-base = information ratio of the variant's per-window PnL vs reference (b). All metrics per-window, PnL in cents/contract.)

## Top-variant uplift + significance (OOS, paired t)

| Variant | d vs (b) base (c/win) | t-stat | d vs (a) streak (c/win) | t-stat |
|---|--:|--:|--:|--:|
| V2 Kelly lam1.0 | +0.02 | +0.03 | +0.62 | +0.94 |
| V2 Kelly lam0.5 | -0.01 | -0.01 | +0.60 | +0.89 |
| V1 GBM 1-p*3 fl0.0 | -0.03 | -0.59 | +0.57 | +1.47 |
| V1 GBM 1-p*3 fl0.25 | -0.03 | -0.59 | +0.57 | +1.47 |
| V1 GBM 1-p*3 fl0.5 | -0.03 | -0.59 | +0.57 | +1.47 |
| V1 GBM 1-p*4 fl0.5 | -0.05 | -0.58 | +0.56 | +1.45 |

## Verdict

**Nothing meaningfully beats simply DROPPING rung 4.** The drop-R4 baseline (b) sits at the TOP of the OOS net ranking at +4.11c/win; the highest-ranked MANAGE variant is within noise of it and fails the |t|>=2 significance bar (best variant `V2 Kelly lam1.0`: +0.02c/win, t=+0.03 vs base — NOT significant). The honest recommendation is to REMOVE the streak guard and run NO manage rung (rungs 1-3 + at-scale 5 only).


**Why continuous sizing can't add net here.** A box leg only loses money when it STRANDS; a paired box is locked/risk-free. Any size cut therefore shaves the locked edge on the (overwhelming) paired boxes to buy a smaller loss on the rare strand. At a ~0.65% per-fill strand rate the trade-off is roughly neutral-to-negative on net — exactly what the table shows: every aggressive sizer (V4 Bayes, V6 AvSt, V3 tox) cuts MaxDD/CVaR/Ulcer hard (Bayes drops MaxDD 457c->90c) but bleeds net (down to +0.79c). The only variants that hold net (V1 GBM, V2 Kelly) are the ones that barely cut size at all — i.e. they converge to the drop-R4 baseline.


**If a risk-budget (not net) is the objective**, the strong tail-control option is `V2 Kelly lam0.25` (+3.42c net but MaxDD 279c vs 457c, CVaR95 45.7c vs 65.0c, PF 1.57 vs 1.45, Sortino +0.17 vs +0.13) — it sacrifices ~0.7c/win for a ~40% MaxDD cut. This is a genuinely better risk-adjusted profile than the live streak-guard (which gives up net AND has worse tails). But on the mandated PRIMARY metric (net c/win) it loses to dropping R4.

## IS/OOS stability

Compare each row's IS net to OOS net in the ranked table above. Variants whose IS and OOS net agree in sign and rough magnitude are stable; large IS>>OOS gaps indicate in-sample overfit (note IS excludes the GBM gate, so IS net is mechanically higher for GBM-dependent variants — judge stability on RANK persistence, not absolute level).

## Deployment

The live trader (`live_trader.py` / `kalshi_trader.py`) uses argparse flags. The deployed manage rung is `--strand-scaledown "0.75,0.5,0.25"` (a discrete streak ladder). To deploy the recommendation:

- **REMOVE / leave empty** the streak-scaledown: run with `--strand-scaledown ""` (or omit it) so no manage-rung resize is applied. This matches the ablation finding that dropping R4 improves OOS net. Rungs 1 (t36), 2 (GBM gate), 3 (sell-cheap), and 5 (hedge, at-scale) remain.

- If a continuous size hook is later desired (it screened near-baseline, not above), add a `--manage-size gbm:k=5,floor=0.25` style flag that multiplies the opening clip by `max(floor, 1 - p_strand*k)` using the rung-2 GBM probability — but only AFTER forward validation, since it did not beat simply dropping the rung here.


**FORWARD VALIDATION REQUIRED** before swapping live config: backtests SCREEN only; bar t>3, n>=300 windows of paper/forward data per the lockdown protocol.
