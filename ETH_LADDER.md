# ETH 15-min Box + Strand-Prevention Ladder — Does the Ladder Rescue ETH?

**Verdict: NO. The ladder does not rescue ETH. It is irredeemably toxic.**
The full prevention ladder only "fixes" ETH by trading almost nothing (~92% of opens
removed), and the residual region it keeps is the *most* toxic part of the ETH tape
(box lock-margin -2.6c vs naked -1.1c). Net stays significantly negative IS and OOS.
**Do NOT deploy ETH boxes, with or without the ladder.**

Harness: `eth_ladder_study.py` (reuses `ladder_baseline_study.py` + `box_policy_ab.py`).
Data: `hist/trades_kalshi_eth15m.parquet` (+ btc). IS = first 60% (1430 windows), OOS = last 40% (954). Backtest screens; forward-validation still required.

---

## 1. Naked ETH baseline — confirmed structurally -EV

P0 always-pair walk (per-window pnl, includes full strand settle):

| Slice | n | net/win | Sharpe | CVaR95 | win% | strand% | t-stat |
|-------|---|---------|--------|--------|------|---------|--------|
| ALL | 2384 | **-11.37c** | -0.439 | 75.5c | 33.3 | 40.7 | -21.4 |
| IS  | 1430 | -10.18c | -0.397 | 72.5c | 34.2 | 42.4 | -15.0 |
| OOS | 954  | **-13.15c** | -0.502 | 78.8c | 31.9 | 38.1 | -15.5 |

Completed-box **lock margin** (the prior Phase-1 reference metric) — reproduced:

| metric | this run | prior Phase-1 |
|--------|----------|---------------|
| mean lock-margin / box | **-1.11c** | -1.5c |
| negative-margin boxes | **24.6%** | 29.6% |
| 5th-pctile | **-19.0c** | -21c |

Confirmed: the naked ETH box is **-EV at both the box level (-1.1c lock margin) and the
window level (-11 to -13c with a 40% strand rate)**. ETH strands far more than BTC and the
boxes that *do* lock are negative-margin on average.

---

## 2. Full ladder on ETH — net does NOT cross positive

Ladder = R0 buffer (spread>=1c, 2c dynamic when window mean|sig|>8bps) + R1 t36 guard +
edge-select (k in 5-9 AND window mean|sig| in 3-8bps AND favorite<=0.70) + R3 sell-cheap
+ chase-to-complete. R4 streak optional.

| Policy | n | net/win | Sharpe | CVaR95 | win% | strand% | opens | t-stat |
|--------|---|---------|--------|--------|------|---------|-------|--------|
| ETH P0 naked OOS | 954 | -13.15c | -0.502 | 78.8c | 31.9 | 38.1 | 7026 | -15.5 |
| **ETH FULL LADDER IS** | 1430 | **-2.18c** | -0.195 | 38.6c | 15.5 | 0.3 | 1105 | -7.4 |
| **ETH FULL LADDER OOS** | 954 | **-1.22c** | -0.132 | 32.1c | 14.0 | 0.0 | 570 | **-4.1** |
| BTC P0 naked OOS | — | **+2.77c** | — | — | 74.9 | — | — | +3.4 |
| BTC same ladder OOS | — | +0.17c | +0.014 | — | 22.6 | — | 299 | +0.3 |

The ladder cuts the ETH bleed from -13c to -1.2c, but **net is still negative and
statistically significant (t=-4.1 OOS, t=-7.4 IS)**. It never crosses zero. The reduction
is entirely from *removing volume*: opens fall from 7026 to 570 (~92% cut) and strand rate
goes to ~0. (win% reads low because most windows now have zero opens, scored as non-wins;
see the opened-only cut below.)

Contrast with BTC: BTC's naked P0 is already **+2.77c** — the ladder on BTC is roughly
net-flat-to-positive because it starts from a profitable tape. ETH starts at -13c and the
ladder cannot dig out of that hole.

### 2b. Leave-one-out (OOS, vs full ladder -1.22c) — which rung does the work?

| Rung dropped | net | Δnet | win% | opens | t |
|--------------|-----|------|------|-------|---|
| drop R0 buffer | -1.22c | +0.00 | 14.0 | 570 | -4.06 |
| drop R1 t36 | -1.63c | -0.41 | 13.9 | 634 | -5.48 |
| **drop edge-select (k/vol)** | **-7.63c** | **-6.41** | 33.1 | 2427 | -11.5 |
| drop fav-avoidance | -1.50c | -0.27 | 17.9 | 1254 | -4.08 |
| drop R3 sell-cheap | -1.22c | +0.00 | 14.0 | 570 | -4.06 |
| add R4 streak | -1.22c | +0.00 | 14.0 | 570 | -4.06 |

**Edge-select (k 5-9 + mid-vol) does ~all of the loss reduction (+6.4c)** — but purely by
shrinking the trade count from 2427 to 570 opens. R0 buffer, R1, R3, R4 add essentially
nothing on top of edge-select (R0/R3/R4 redundant once edge-select is on; their thin-spread
work is already subsumed). fav-avoidance trims a little. **No rung makes ETH positive — they
only throttle volume.**

### 2c. Single-gate isolation (OOS, each gate alone + chase-complete)

| Gate | net | win% | opens | strand% |
|------|-----|------|-------|---------|
| naked chase-complete | -13.15c | 31.9 | 7026 | 38.1 |
| +R3 sell-cheap | -12.86c | 32.5 | 7026 | 38.1 |
| +R0 buffer>=1c | -12.44c | 34.1 | 6407 | 29.1 |
| +R0 buffer>=2c | -8.25c | 38.9 | 4037 | 13.9 |
| +R1 t36 | -10.48c | 39.5 | 5835 | 37.0 |
| **+edge k/vol** | **-2.25c** | 17.8 | 1593 | 4.4 |
| +fav-avoid | -9.30c | 33.2 | 2916 | 2.7 |

Every single gate leaves ETH **deeply negative**. The best single gate (edge k/vol) is still
-2.25c. Strand control (R3/R5/buffer) barely moves the needle because ETH's loss is not just
strands — the *paired* boxes are negative-margin too.

### 2d. BTC-momentum gate — no help

Suppressing ETH opens in high-|sig| BTC windows (266 toxic BTC windows): full ladder + BTC
gate OOS = -1.20c (Δ+0.03 vs -1.22c). Negligible. The ETH toxicity is not a BTC-momentum
artifact filterable cross-asset.

---

## 3. Why ETH is toxic — and why the ladder's filters point the WRONG way

Completed-box lock margins (all 16,640 boxes), conditioned on the ladder's own gate features:

| segment | n (share) | mean margin | neg% |
|---------|-----------|-------------|------|
| thin spread (<2c) | 6769 (40.7%) | -1.08c | 20.3 |
| wide spread (>=2c) | 9871 (59.3%) | -1.13c | 27.5 |
| high-\|sig\| window (>8bps) | 4081 (24.5%) | -1.98c | 26.4 |
| **mid-\|sig\| window (3-8bps)** | 8672 (52.1%) | -0.94c | 24.1 |
| low-\|sig\| window (<3bps) | 3887 (23.4%) | -0.59c | 23.6 |
| late slot (k>9) | 2645 (15.9%) | **+0.44c** | 12.9 |
| **mid slot (k5-9)** | 7909 (47.5%) | **-1.43c** | 26.9 |
| early slot (k<5) | 6086 (36.6%) | -1.38c | 26.6 |
| deep favorite (>0.70) | 9443 (56.7%) | -0.25c | 22.2 |
| **non-favorite (<=0.70)** | 7197 (43.3%) | **-2.24c** | 27.6 |
| **LADDER-PASS region (all gates)** | **1572 (9.4%)** | **-2.56c** | **29.8** |
| LADDER-BLOCKED region | 15068 (90.6%) | -0.96c | 24.0 |

**This is the crux. The ladder's selection criteria — tuned on BTC — select ETH's MOST toxic
boxes:**
- ETH's *least* toxic boxes are **late-slot (k>9): +0.44c** — exactly what edge-select (k 5-9)
  THROWS AWAY.
- ETH's *least* toxic boxes are **deep favorites (>0.70): -0.25c** — exactly what fav-avoidance
  THROWS AWAY (it keeps non-favorites at -2.24c).
- So the combined LADDER-PASS region is **-2.56c, ~2.3x worse than the naked -1.11c average.**

IS/OOS stability of the ladder-pass box margin: IS -2.52c (t=-7.1, n=1044), OOS -2.63c
(t=-5.5, n=528). Stable and significantly negative both halves. On *opened windows only*
(no dilution by no-trade zeros), the full ladder still loses **-4.65c/window (t=-4.16)**.

How much of the -1.1c mean is removed by gating? The gating removes ~92% of opens and the
remaining 8-9% are *more* negative, so gating does not "remove the loss" at all — it
concentrates the bad boxes and only the volume collapse shrinks the absolute per-window bleed.
On BTC the same gates select the fat-box (positive) region; on ETH they select the thin
toxic region. **ETH's edge structure is inverted relative to BTC: the ladder is anti-tuned to
ETH.**

---

## 4. Verdict — NOT deployable

**ETH 15-min boxes are irredeemably toxic, even with the full strand-prevention ladder.**

- Naked ETH box: -1.1c lock-margin / -13c per-window, 40% strand — structurally -EV (confirmed).
- Full ladder ETH OOS: **-1.22c/window, t=-4.1**, only ~570 opens / 954 windows (and IS -2.18c, t=-7.4).
- The ladder "fixes" ETH **only by trading nearly nothing** — and the boxes it keeps are the
  *worst* boxes (LADDER-PASS region -2.56c vs naked -1.11c, t=-5.5 OOS), because ETH's
  profitable slices (late-slot, deep-favorite) are the ones the BTC-tuned gates discard.
- No rung crosses zero; no leave-one-out, no single gate, and no BTC-momentum gate makes ETH
  positive. The +6.4c "rescue" from edge-select is volume throttling, not edge.
- Even if you inverted the gates to chase ETH's late-slot/favorite boxes (+0.44c / -0.25c),
  those are barely-positive-to-flat, thin, and would themselves need fresh OOS validation —
  not a deployable edge.

**Recommendation: do NOT add ETH boxes to the live maker-box bot.** Keep ETH only in its
already-validated role as the cross-asset *hedge* leg for BTC strands (RUNG-5a), not as a
box-trading market in its own right. Forward-validation not required because the screen is
unambiguously negative; revisit only if ETH tape structure (spread/strand regime) changes.
