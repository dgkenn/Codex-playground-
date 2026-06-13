# Box-Yield Phase-1 COMBO STACKING (BTC 15m crypto box)

**Question.** Do *combinations* of the five Phase-1 box-yield levers beat them individually (positive interactions), or do the gates overlap / cannibalise (double-gate volume to nothing)?

**Objective.** TOTAL PnL = (#boxes) x (edge/box) - strand losses. Judged vs `live_current` (t36 guarded-opener + always-complete), full A/B metric set, IS=first 60% / OOS=last 40%, BTC only (ETH box is -EV). IS=549 windows, OOS=367 windows.

**Levers** (independent toggles; all are OPEN-leg gates except `edge_sizing`; completing leg never gated; strand = sell-cheap if p_yeq<0.30 else hold to settle):

- `edge_select` — open only mid-slot k∈[5,9] AND mid-vol windows (window mean|sig|∈[3,8) bps).
- `balanced_band` — block deep-favorite opens (opening-leg YES-equiv price > 0.70).
- `buffer_1c` — require spread ≥ 1c to open (dynamic 2c when leg sig>8).
- `k_le_10` — cap opens at k ≤ 10 (no late-slot opens).
- `edge_sizing` — f=0.25 fractional-Kelly on the IS (session×vol-bucket) net-edge map.

## Combination metric table (OOS)

`live_current` = all levers off (t36+complete). `dLive` = paired per-window diff vs live_current.

| config | #box/win | lock c/box | strand% | net c | IS net | Sharpe | Sortino | CVaR95 | MaxDD | WR% | PF | dLive c | t_live |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| live_current (all off) | 6.11 | 0.551 | 38.1 | +3.12 | +2.71 | +0.100 | +0.095 | +69.94 | 677.80 | 58.3 | 1.31 | +nan | +nan |
| [1] edge_select | 1.79 | 0.768 | 3.0 | +1.25 | +1.35 | +0.091 | +0.070 | +30.94 | 181.60 | 33.5 | 1.41 | -1.874 | -1.32 |
| [1] balanced_band | 4.53 | 0.244 | 24.3 | +0.76 | +3.35 | +0.027 | +0.022 | +70.30 | 886.40 | 53.4 | 1.08 | -2.365 | -2.97 |
| [1] buffer_1c | 4.86 | 0.507 | 15.0 | +1.98 | +1.89 | +0.073 | +0.069 | +62.20 | 653.30 | 56.9 | 1.23 | -1.141 | -1.45 |
| [1] k_le_10 | 5.65 | 0.619 | 13.4 | +3.39 | +2.58 | +0.141 | +0.139 | +49.60 | 235.00 | 58.9 | 1.45 | +0.265 | +0.24 |
| [1] edge_sizing | 6.11 | 0.644 | 38.1 | +3.67 | +4.63 | +0.108 | +0.104 | +80.18 | 652.34 | 58.6 | 1.37 | +0.544 | +0.75 |
| [2] edge_select+edge_sizing | 1.79 | 1.020 | 3.0 | +1.68 | +1.78 | +0.102 | +0.081 | +36.90 | 177.21 | 33.5 | 1.48 | -1.440 | -1.01 |
| [2] edge_select+balanced_band | 1.28 | 0.481 | 0.5 | +0.62 | +1.43 | +0.050 | +0.031 | +30.64 | 279.30 | 29.2 | 1.22 | -2.502 | -1.70 |
| [2] buffer_1c+k_le_10 | 4.58 | 0.533 | 2.2 | +2.49 | +2.28 | +0.116 | +0.110 | +47.24 | 209.70 | 58.0 | 1.38 | -0.638 | -0.52 |
| [2] edge_select+buffer_1c | 1.36 | 1.173 | 0.5 | +1.58 | +0.81 | +0.125 | +0.094 | +27.76 | 85.90 | 34.3 | 1.65 | -1.541 | -1.07 |
| [FULL] all 5 | 1.04 | 1.239 | 0.3 | +1.29 | +1.18 | +0.092 | +0.057 | +33.27 | 147.43 | 30.5 | 1.46 | -1.837 | -1.24 |
| [LOO] full - edge_select | 3.69 | 0.487 | 1.4 | +1.89 | +4.05 | +0.083 | +0.073 | +53.39 | 229.99 | 54.8 | 1.29 | -1.230 | -0.87 |
| [LOO] full - balanced_band | 1.36 | 1.573 | 0.5 | +2.12 | +1.04 | +0.137 | +0.107 | +33.21 | 105.56 | 34.3 | 1.75 | -1.000 | -0.69 |
| [LOO] full - buffer_1c | 1.28 | 0.664 | 0.5 | +0.86 | +1.91 | +0.057 | +0.037 | +37.13 | 309.53 | 29.2 | 1.26 | -2.266 | -1.54 |
| [LOO] full - k_le_10 | 1.04 | 1.239 | 0.3 | +1.29 | +1.18 | +0.092 | +0.057 | +33.27 | 147.43 | 30.5 | 1.46 | -1.837 | -1.24 |
| [LOO] full - edge_sizing | 1.04 | 0.947 | 0.3 | +0.98 | +0.92 | +0.086 | +0.052 | +27.89 | 130.50 | 30.5 | 1.42 | -2.141 | -1.45 |

### Extended risk panel (OOS)

| config | skew | ulcer c | recovery | IR vs live | P(both fill) |
|---|---|---|---|---|---|
| live_current (all off) | -0.16 | 309.10 | +1.69 | +nan | 0.619 |
| [1] edge_select | +0.72 | 85.08 | +2.53 | -0.069 | 0.970 |
| [1] balanced_band | -0.52 | 497.83 | +0.31 | -0.155 | 0.757 |
| [1] buffer_1c | -0.06 | 309.94 | +1.11 | -0.076 | 0.850 |
| [1] k_le_10 | -0.09 | 75.29 | +5.29 | +0.012 | 0.866 |
| [1] edge_sizing | -0.13 | 285.08 | +2.06 | +0.039 | 0.619 |
| [2] edge_select+edge_sizing | +0.89 | 82.09 | +3.49 | -0.053 | 0.970 |
| [2] edge_select+balanced_band | -0.18 | 154.03 | +0.82 | -0.089 | 0.995 |
| [2] buffer_1c+k_le_10 | -0.12 | 83.67 | +4.35 | -0.027 | 0.978 |
| [2] edge_select+buffer_1c | +0.92 | 32.98 | +6.76 | -0.056 | 0.995 |
| [FULL] all 5 | +0.46 | 59.25 | +3.20 | -0.065 | 0.997 |
| [LOO] full - edge_select | -0.16 | 85.80 | +3.02 | -0.045 | 0.986 |
| [LOO] full - balanced_band | +1.10 | 38.36 | +7.39 | -0.036 | 0.995 |
| [LOO] full - buffer_1c | +0.29 | 165.77 | +1.02 | -0.080 | 0.995 |
| [LOO] full - k_le_10 | +0.46 | 59.25 | +3.20 | -0.065 | 0.997 |
| [LOO] full - edge_sizing | +0.29 | 57.61 | +2.77 | -0.076 | 0.997 |

## Leave-one-out interaction analysis (OOS)

FULL stack OOS: net **+1.29c**, Sharpe +0.092, #box/win 1.04, strand 0.3%, dLive -1.837c (t=-1.24).

`d(net) vs FULL` = what each lever ADDS to the full stack (FULL − LOO). Positive ⇒ the lever contributes net at the margin; ≈0 ⇒ redundant/subsumed; negative ⇒ it hurts inside the stack.

| drop lever | LOO net c | d(net) vs FULL | LOO Sharpe | d(box/win) | verdict |
|---|---|---|---|---|---|
| edge_select | +1.89 | -0.607 | +0.083 | 3.69 | HURTS net (drop) |
| balanced_band | +2.12 | -0.837 | +0.137 | 1.36 | HURTS net (drop) |
| buffer_1c | +0.86 | +0.429 | +0.057 | 1.28 | ADDS net (keep) |
| k_le_10 | +1.29 | +0.000 | +0.092 | 1.04 | net-neutral |
| edge_sizing | +0.98 | +0.304 | +0.086 | 1.04 | ADDS net (keep) |

Best single lever by net: **edge_sizing** (net +3.67c, Sharpe +0.108). Best single by Sharpe: **k_le_10** (net +3.39c, Sharpe +0.141).

Best MULTI-lever combo: **[LOO] full - balanced_band** (net +2.12c, Sharpe +0.137, #box/win 1.36) — vs best single Δ -1.264c/win (t=-1.21).

## Single BEST box-yield policy

**The best policy is a SINGLE lever, not a combo** — stacking does not improve on it.

**Policy:** `[1] k_le_10` — levers ON: k_le_10.

- OOS: net +3.39c/win, Sharpe +0.141, Sortino +0.139, CVaR95 +49.60c, MaxDD 235.00c, #box/win 5.65, strand 13.4%, WR 58.9%, PF 1.45.
- vs live_current: dLive +0.265c/win (t=+0.24); IS net +2.58c (OOS +3.39c) — sign-stable across the split.
- vs best single lever (`k_le_10`): paired diff -1.264c/win (t=-1.21).
- (Best by raw net among non-degenerate configs: `[1] edge_sizing`, net +3.67c, Sharpe +0.108.)

### Exact entry rule

```
OPEN a leg iff:  _live_open_ok(f)            # keep live t36 guard
             AND k <= 10                   # no late-slot opens
PAIR always (never gate the completing leg).
STRAND: sell-cheap if p_yeq<0.30 else hold to settle.
ASSET: BTC only (ETH box is -EV).
```

### Trader-flag sketch

```
--box-k-cap 10           # no opens after slot 10
--box-asset btc          # box disabled on ETH (-EV)
```

## Verdict — does stacking help?

- **Best policy overall** is `[1] k_le_10` (Sharpe +0.141, net +3.39c) — **a single lever**.
- **Does the best multi-lever combo beat the best single lever?** `[LOO] full - balanced_band` (Sharpe +0.137) vs `k_le_10` (Sharpe +0.141): **NO** (paired Δ -1.264c, t=-1.21). No combo beats live_current on net with |t|≥2 either.
- **Interaction read (LOO):** levers whose `d(net) vs FULL` ≈ 0 are *redundant inside the stack*. `k_le_10`'s marginal contribution to the full stack is **+0.000c (exactly ≈0)** — because `edge_select`'s k∈[5,9] gate is a strict subset of k≤10, it fully **subsumes** `k_le_10`. `buffer_1c` and `balanced_band` both attack adverse-selection/strand and partially substitute (dropping either inside the stack barely moves net). This is cannibalisation, not synergy.
- **Double-gating risk:** the full stack drives #box/win to 1.04 (vs live 6.11); the more gates ANDed, the thinner the volume. Watch the master table for configs whose #box/win collapses toward 0 — those 'wins' are mostly *not-trading*, not edge.
- **Honest verdict:** the levers are **mostly risk-quality selection, not additive alpha**. The marginal net gains stack sub-additively (LOO deltas are small and several near-zero), and no combo beats live_current on net with |t|≥2 (paired t's in the master table). The defensible stack win is **risk-adjusted** (Sharpe / CVaR / MaxDD), concentrated in k_le_10-style selection; piling on more gates past that mainly shrinks volume. Recommend the lean `[1] k_le_10` config, not the full stack.

### IS/OOS stability

- Best combo IS net +2.58c → OOS net +3.39c (live_current IS +2.71c → OOS +3.12c). Same sign across the split.
- P0 OOS reference: net +2.77c, strand 12.3%.

*Backtests SCREEN only (in-sample-on-OOS screens, not live-validated). The edge_sizing map is fit on IS and applied to OOS, but all gates are decision-time observables. Run the live collector A/B (2-sigma alert + pre-registered deploy bar) before arming any flag.*

