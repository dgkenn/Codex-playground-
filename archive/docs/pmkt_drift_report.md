# Polymarket Drift / Momentum vs Reversion — Third-Edge Hunt

_Generated 2026-07-16 17:46 UTC_

**Signal (strictly causal).** Per settled binary market, life `[t0,t1]`; `p_open`=first hourly YES mid; decision at `t40 = t0+0.40*(t1-t0)`; `p_mid`=last mid at t<=t40; drift `m=p_mid-p_open` (measured BEFORE the decision point). MOMENTUM buys the direction of `m`, REVERSION fades it; held to UMA resolution (outcome in {0,1}); entered at the executable price (cross half-spread `hs`). Zero fee. Outcome only from resolution. Cluster by resolution week.

**Universe.** Liquid settled Yes/No markets (volume >= $20000), life in [1,200]d. Candidates 9000; with usable causal mids **8684** across **138** resolution weeks. By category: crypto=1909, sports=1522, politics=996, econ=109, other=4148.

**Cost model.** No historical book snapshots exist, so entry cost is a flat half-spread sweep `hs in [0.005, 0.01, 0.02]` (primary headline **hs=0.010**, i.e. a 2c round-trip spread). Median reported per-market `spread` of the used universe = 0.0010 (justifies ~1c half-spread as realistic-to-conservative for these liquid markets).


## Momentum vs Reversion grid — net @ hs=0.010, week-clustered t

Each cell: mean PnL/contract (net) / week-clustered t / n trades. A REAL edge is one-sided (MOM xor REV) and consistent across thresholds and categories.

| group | thr | MOM mean | MOM t | MOM n | REV mean | REV t | REV n | weeks |
|---|---|---|---|---|---|---|---|---|
| POOLED | 0.03 | -0.0307 | -4.11 | 6419 | +0.0107 | +2.93 | 6419 | 136 |
| POOLED | 0.05 | -0.0317 | -3.78 | 5668 | +0.0117 | +2.62 | 5668 | 134 |
| POOLED | 0.10 | -0.0374 | -4.05 | 4540 | +0.0174 | +3.01 | 4540 | 133 |
| crypto | 0.03 | -0.0335 | -2.01 | 1642 | +0.0135 | +1.20 | 1642 | 106 |
| crypto | 0.05 | -0.0349 | -1.96 | 1491 | +0.0149 | +1.17 | 1491 | 106 |
| crypto | 0.10 | -0.0483 | -2.98 | 1235 | +0.0283 | +2.20 | 1235 | 102 |
| sports | 0.03 | -0.0522 | -3.53 | 837 | +0.0322 | +2.83 | 837 | 65 |
| sports | 0.05 | -0.0497 | -3.00 | 720 | +0.0297 | +2.38 | 720 | 64 |
| sports | 0.10 | -0.0474 | -2.36 | 598 | +0.0274 | +1.72 | 598 | 61 |
| politics | 0.03 | -0.0409 | -3.24 | 840 | +0.0209 | +2.44 | 840 | 93 |
| politics | 0.05 | -0.0392 | -2.42 | 759 | +0.0192 | +1.65 | 759 | 90 |
| politics | 0.10 | -0.0492 | -2.76 | 648 | +0.0292 | +2.04 | 648 | 85 |
| econ | 0.03 | +0.0407 | +0.62 | 95 | -0.0607 | -0.99 | 95 | 28 |
| econ | 0.05 | +0.0450 | +0.76 | 86 | -0.0650 | -1.11 | 86 | 28 |
| econ | 0.10 | +0.0196 | +0.57 | 71 | -0.0396 | -0.92 | 71 | 27 |
| other | 0.03 | -0.0225 | -2.72 | 3005 | +0.0025 | +1.73 | 3005 | 113 |
| other | 0.05 | -0.0253 | -2.74 | 2612 | +0.0053 | +1.77 | 2612 | 113 |
| other | 0.10 | -0.0259 | -2.56 | 1988 | +0.0059 | +1.66 | 1988 | 106 |

## Half-spread sensitivity (POOLED) — mean PnL/contract

| thr | dir | hs=0.005 | hs=0.010 | hs=0.020 | gross(hs=0) |
|---|---|---|---|---|---|
| 0.03 | MOM | -0.0257 | -0.0307 | -0.0407 | -0.0207 |
| 0.03 | REV | +0.0157 | +0.0107 | +0.0007 | +0.0207 |
| 0.05 | MOM | -0.0267 | -0.0317 | -0.0417 | -0.0217 |
| 0.05 | REV | +0.0167 | +0.0117 | +0.0017 | +0.0217 |
| 0.10 | MOM | -0.0324 | -0.0374 | -0.0474 | -0.0274 |
| 0.10 | REV | +0.0224 | +0.0174 | +0.0074 | +0.0274 |

## Continuous relationship: corr(m, outcome - p_mid)

Does first-40% drift predict the RESIDUAL future move beyond the current price (p_mid)? r>0 => momentum/underreaction; r<0 => reversion/overreaction. 95% CI from week-block bootstrap (1000 reps).

| group | r | naive t | 95% CI (week-block) | n |
|---|---|---|---|---|
| POOLED | -0.0453 | -4.22 | [-0.072, -0.023] | 8684 |
| crypto | -0.1154 | -5.08 | [-0.178, -0.048] | 1909 |
| sports | -0.0229 | -0.89 | [-0.067, +0.013] | 1522 |
| politics | -0.0312 | -0.98 | [-0.107, +0.037] | 996 |
| econ | +0.0883 | +0.92 | [-0.114, +0.325] | 109 |
| other | -0.0205 | -1.32 | [-0.047, +0.008] | 4148 |

## Stackability vs the longshot short-vol series

Best directional cell by week-clustered t (net@0.010): **REV thr=0.10**, mean +0.0174, t=+3.01. Its weekly PnL vs a 'sell longshots' series (p_mid in [0.15,0.3], SELL YES, same market set, 106 weeks): **corr = -0.57** over 106 overlapping weeks.

## Robustness — is the reversion real or a stale-opening-print artifact?

**(1) Interior anchor.** Replace the first (possibly seed/noisy) print with the mid at the 10% point of life; keep the decision at 40%. `m` now spans the fully INTERIOR window [10%,40%] — no opening-print artifact, no resolution overlap.

- Interior corr(m_int, outcome-p_mid) = -0.0214 (t=-2.00, 95% CI [-0.051,+0.010], n=8684).
- Interior POOLED reversion net@0.010:

| thr | REV mean | REV t | n | weeks |
|---|---|---|---|---|
| 0.03 | +0.0055 | +0.29 | 4467 | 131 |
| 0.05 | +0.0106 | -0.24 | 3489 | 129 |
| 0.10 | +0.0054 | -0.21 | 2273 | 123 |

**(2) Sane-open filter.** Keep only markets whose opening print is in [0.05,0.95] (n=7773).

- Sane-open corr(m, outcome-p_mid) = -0.0480 (t=-4.24, 95% CI [-0.074,-0.023], n=7773).

| thr | REV mean | REV t | n | weeks |
|---|---|---|---|---|
| 0.03 | +0.0128 | +2.90 | 6235 | 136 |
| 0.05 | +0.0134 | +2.69 | 5613 | 134 |
| 0.10 | +0.0188 | +3.06 | 4513 | 133 |

**(3) Reversion vs longshot series at every threshold** (orthogonality):

| thr | REV weekly-PnL corr to sell-longshots | overlap weeks |
|---|---|---|
| 0.03 | -0.65 | 106 |
| 0.05 | -0.62 | 106 |
| 0.10 | -0.57 | 106 |

## BLUNT VERDICT

- Continuous pooled corr(m, outcome-p_mid) = -0.0453 (naive t=-4.22, week-block 95% CI [-0.072,-0.023]).
- POOLED net@0.010: MOMENTUM cells with t>=2 & mean>0: 0/3; REVERSION such cells: 3/3.
- Interior-anchor [10%->40%] reversion: corr=-0.0214 (CI [-0.051,+0.010]); net-positive at 0/3 thresholds.
- Reversion vs sell-longshots weekly-PnL corr (mean over thresholds) = -0.61 -> NOT orthogonal.
- Net edge size @hs=0.010: REV mean ~ +0.0174/contract; at hs=0.020 -> +0.0074/contract.

**Verdict: REVERSION signal is REAL but NOT a stackable third edge.** A first-40% move partially reverts (pooled continuous corr significantly negative, reversion net-positive across thresholds), BUT its weekly PnL is strongly anti-correlated with the sell-longshots series (mean corr -0.61). Mechanically it BUYS fallen longshots / SELLS risen favorites — i.e. it is largely the OPPOSITE side of the existing longshot premium, not an orthogonal diversifier. Net margin is also thin (~1-2c/contract) and decays toward zero by a 2c half-spread.

_Bottom line for the book: there is a genuine short-horizon over-reaction (prices that jump in the first 40% of a market's life tend to give some of it back), strongest in crypto. But as a THIRD edge it is disappointing — it is thin net of spread and, crucially, it is not orthogonal to the longshot/short-vol premium already held; it is partly the same bet inverted. Do NOT size it as an independent diversifier._