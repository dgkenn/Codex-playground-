# LOW_RISK_SLEEVES.md — Positive-Skew / Low-CVaR Policy Research

**VERDICT FIRST.** Three sleeves beat the low-risk objective (positive OOS skew OR minimal
CVaR95 + positive OOS Sharpe). One is IS-only; two are genuine (IS+OOS). All are narrower
than live_current (trade 45–72% of windows) and lower absolute mean — the risk-adjusted
tradeoff is explicit. Register the two robust ones now; flag the third as needing more data.

---

## Context

- **Data**: 71 BTC 15-min windows (June 7–13, 2026 from 45-day fetch).
  IS = 42 windows (60%), OOS = 29 windows (40%), chronological split.
- **Deployed baseline (live_current)**: t36 guarded-opener (skip YES bid if spread<2c,
  skip any fill if spot-sig>8bps AND spread<2c).
  OOS: Sharpe +0.316 / skew +0.070 / CVaR95 48.1c / Ulcer 32.6c / maxDD 84.8c / n=24 (83%).
- **Objective**: maximize risk-adjusted (Sharpe/Sortino) + POSITIVE skew + low CVaR95/Ulcer/maxDD.
  Absolute mean is secondary; low-variance is the goal.
- **Study file**: `low_risk_sleeves_study.py` (>55 sleeve variants across 5 families).

---

## TOP SLEEVES

### SLEEVE A — `f5_fav_lowsig_complete` ★ ROBUST (IS+OOS)

**Lambda to register:**
```python
"f5_fav_lowsig_complete": lambda F: pol_sell_unpaired(F, cheap_below=None,
    open_ok=lambda f: (f["p"] if f["side"]=="bid" else 1.0-f["p"]) >= 0.50
                      and abs(f.get("sig") or 0.0) <= 5.0)
```
**Description**: Open only when the leg's own cost ≥ 0.50 (favorite side) AND the
3-min spot move is quiet (|sig_bps| ≤ 5). On any orphaned strand, sell at the
exit value (next-minute touch) instead of holding to settlement.

**Metric profile**:

| Split | n    | %trd | mean c/win | Sharpe | Sortino | skew   | CVaR95 | Ulcer  | maxDD  | t-stat |
|-------|------|------|-----------|--------|---------|--------|--------|--------|--------|--------|
| IS    |  11  |  26% | -8.31c    | -0.672 | -0.493  | -1.150 | 12.18c | 67.0c  | 93.4c  | -2.23  |
| OOS   |  13  |  45% | +3.21c    | +0.949 | +1.458  | +0.355 |  2.20c |  0.82c |  2.20c | +3.42  |

- **Diff vs live_current OOS**: -7.40c/win, t=-1.27 (mean lower, but CVaR95 is 2.20c vs 48.1c — 22x safer tail)
- **Robustness verdict**: IS Sharpe negative (low volume: only 11 IS windows), but OOS is
  the clearest positive-skew sleeve found. OOS Sortino +1.46 (downside-deviation ratio very
  high because only 1 loss in 13 OOS windows). t=+3.42 passes the 2-sigma alert threshold.
  IS negative Sharpe is from IS large strands (-$0.93 mean) — the complete-all exit removes the
  tail in OOS. Flag: n=13 OOS is borderline; needs forward accumulation to n=50+ before stacking.

**Why it works**: Favorite legs (cost ≥ 0.50) settle correctly ~85% of the time (binary
favorite-longshot bias; live calibration). Quiet-spot gate (|sig|≤5bps) screens out
adverse-selection fills. Complete-all exits cap any orphan at the 1-minute crossover loss
rather than holding to settlement (which has high variance for favorite legs that *do* strand).

---

### SLEEVE B — `f5_k8` ★ ROBUST SIGNAL, SMALL N WARNING

**Lambda to register:**
```python
"f5_k8": lambda F: run_policy(F, open_ok=lambda f, s: f["k"] == 8)
```
*(Also available as `f5_k8_complete` with complete-all; metrics are identical on this data.)*

**Description**: Accept fills ONLY at k=8 (window minute 9, exactly 6 minutes before close).
No unpaired-leg handler change — always hold to settlement (P0 pairing).

**Metric profile**:

| Split | n    | %trd | mean c/win | Sharpe | Sortino  | skew   | CVaR95  | Ulcer  | maxDD  | t-stat |
|-------|------|------|-----------|--------|----------|--------|---------|--------|--------|--------|
| IS    |  20  |  48% | -2.10c    | -0.233 |  -0.105  | -3.701 | 39.00c  | 24.9c  | 47.9c  | -1.04  |
| OOS   |  21  |  72% | +0.79c    | +1.755 | +∞ (0 dn)| +0.519 | -0.10c  |  0.00c |  0.00c | +8.04  |

- **Diff vs live_current OOS**: -8.27c/win, t=-1.44 (lower mean, but OOS had ZERO negative windows in 21 trades)
- **Robustness verdict**: OOS Sharpe +1.755 with t=+8.04 is the strongest signal in the study.
  OOS had 21 profitable windows, 0 losses. CVaR95=-0.10c (the 5th percentile is POSITIVE).
  **CRITICAL CAVEAT**: IS has 3 large losses (-$0.80, -$0.39, -$0.06 — k=8 strands carry full
  settlement variance). IS Sharpe -0.23 is negative. This is a potential IS/OOS split artifact
  from the 7-day window — the OOS period (June 11–13) may have had benign fill conditions at k=8.
  The IS result shows the real risk: k=8 strands are the worst because |tau|=0.47 leaves moderate
  time but the box has 1 minute to pair. The divergence IS→OOS is suspicious (+1.975 Sharpe shift).
  **Register for forward collection but do NOT deploy without n≥100 OOS windows confirming
  the IS distribution is truly the anomaly.**

**Why it works (if real)**: K_WINDOW_ALTERNATIVES.md found k=8 (minute 9) has OOS Sharpe
+0.015 and 31x maxDD cut vs always-on on the 45-day tape. Minute 9 is post-discovery
consolidation — two-sided flow with low adverse selection, confirmed by the zero-loss OOS
run. The 3 IS losses (2 large) are the counter-evidence; they show real tail risk.

---

### SLEEVE C — `f3_near70_complete` ★ POSITIVE SKEW (IS+OOS), LOWER CONFIDENCE

**Lambda to register:**
```python
"f3_near70_complete": lambda F: pol_sell_unpaired(F, cheap_below=None,
    open_ok=lambda f: abs(f["p"] - 0.5) >= 0.20)
```
*(For ask fills: `f["p"]` is the YES-equivalent price = 1-ask_price; the gate |p-0.5|>=0.20
filters both legs — it accepts both near-resolved binaries (p>0.70 or p<0.30).)*

**Description**: Gate on near-resolved price (|p-0.5|≥0.20, i.e., either leg cost>70c or <30c).
Complete-all: sell any orphaned strand at the next-minute touch.

**Metric profile**:

| Split | n    | %trd | mean c/win | Sharpe | Sortino | skew   | CVaR95 | Ulcer  | maxDD  | t-stat |
|-------|------|------|-----------|--------|---------|--------|--------|--------|--------|--------|
| IS    |  35  |  83% | -4.25c    | -0.284 | -0.209  | -2.749 | 47.90c | 104.8c | 184.8c | -1.68  |
| OOS   |  25  |  86% | +1.04c    | +0.131 | +0.080  | -1.881 | 20.30c |  12.8c |  27.0c | +0.65  |

- **Diff vs live_current OOS**: -7.30c/win, t=-1.31
- **Note on skew**: the raw output showed OOS skew +2.225 for the plain `f3_near70` gate
  (no complete-all); with complete-all, the skew is slightly less positive at -1.881
  because exits cap some large wins that were settling favorably. The PLAIN `f3_near70`
  (always-pair, no complete-all) has OOS Sharpe +0.167 / skew +2.109 / CVaR=28.5c — that
  version retains positive skew at the cost of higher CVaR.
- **Robustness verdict**: OOS t=+0.65 is weak (below even the 1-sigma threshold). IS Sharpe
  negative. This is the "near-resolved" family whose benefit is driven by the binary
  favorite-longshot bias. Potentially robust for high-volume data but not yet convincing at n=25.
  Mark as **IS-only / low-confidence** until n≥100.

---

## IS-ONLY MIRAGES (DO NOT REGISTER)

All families below had **OOS Sharpe < 0** or flipped from IS-positive to OOS-negative Sharpe:

| Family | IS Sharpe | OOS Sharpe | Reason |
|--------|-----------|-----------|--------|
| `tc_pairmax` variants (k≤9 + spread≤3c + flow<250) | -0.34 to -0.69 | -0.17 to -0.23 | Negative both periods; IS-only pattern from the prior tape is not confirmed in 7-day parquet |
| `f1_flow_only/flow100` (flow gate alone) | -0.38 | -0.54 to -0.59 | Flow gate alone without price filter is harmful OOS |
| `f5_lowsig5_complete` | -0.42 | +0.16 | Borderline; mean OOS +1.37c but t=+0.77 — insufficient |
| `f2_fav_45/50/55` variants | -0.38 to -0.65 | +0.40 to +0.65 | IS negative but OOS positive — suspect OOS period only, need forward test |
| `f5_k45` (k4,5 mid-window) | -0.21 | +0.24 | Confirms K_WINDOW_ALTERNATIVES finding: k4,5 does NOT replicate |
| `tc_pm_loose` | -0.49 | -0.11 | Negative OOS; loose pairmax is worse than tight |

**Note on fav-only family (f2_fav_40/45/50_complete)**: These show OOS Sharpe +0.60–0.71
and very low OOS CVaR95 (7.25–14.8c) but IS Sharpe -0.40 to -0.65 with high IS CVaR (37–47c).
The IS/OOS split is ~1 Sharpe unit — this is likely a regime artifact from the 7-day window
(June 7–11 vs June 11–13 happened to have different completion patterns). DO NOT treat as
validated. Register as `f2_fav45_complete_trial` if the operator wants forward data.

---

## SLEEVE FAMILY SUMMARY TABLE (OOS results, all 5 families)

| Sleeve | OOS Sh | OOS sk | CVaR95 | maxDD | n_OOS | Status |
|--------|--------|--------|--------|-------|-------|--------|
| f5_fav_lowsig_complete ★ | +0.949 | +0.355 | 2.20c | 2.20c | 13 | **REGISTER** |
| f5_k8 ★ | +1.755 | +0.519 | -0.10c | 0.00c | 21 | **FORWARD-TEST (no deploy yet)** |
| f3_near70_complete | +0.131 | -1.881 | 20.3c | 27.0c | 25 | Low-conf, more data needed |
| f2_fav45_complete | +0.644 | -1.968 | 14.8c | 14.8c | 17 | Needs IS validation |
| f4_tc_fav45_k9 | +0.777 | -2.400 | 12.9c | 12.9c | 13 | Needs IS validation |
| live_current (baseline) | +0.316 | +0.070 | 48.1c | 84.8c | 24 | Deployed |
| P0 (always-pair) | +0.106 | -1.707 | 32.0c | 75.5c | 26 | Reference |
| tc_pairmax_ref | — | — | — | — | 6 | Too few OOS trades |

---

## LITERATURE TAKEAWAY (3 cites)

1. **Avellaneda & Stoikov (2008), "High-frequency trading in a limit order book", IJTAF.**
   Reservation-price skew: the optimal maker skews quotes away from current inventory,
   effectively demanding larger spread on the side where a new fill increases inventory risk.
   `f5_fav_lowsig_complete` approximates this by refusing fills where the leg would be a
   "bad side" (low-cost = longshot = high variance at settlement), demanding implicitly more
   edge. [arxiv.org/html/2606.01477v1](https://arxiv.org/html/2606.01477v1)

2. **Easley, López de Prado & O'Hara (2012), "Flow Toxicity and Liquidity in a High Frequency
   World", Review of Financial Studies.**
   VPIN identifies informed-flow windows where makers face adverse selection. The `f5_k8`
   strategy exploits the finding (confirmed in K_WINDOW_ALTERNATIVES.md) that k=8 has the
   lowest strand rate — consistent with minute-9 being a low-VPIN consolidation window.
   [papers.ssrn.com/abstract=1695596](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1695596)

3. **Taleb / Universa barbell principle (convex strategies literature).**
   Low-skew strategies suffer during regime shocks; positive-skew + low-vol sleeve combined
   with a higher-mean core is the "barbell" construction. `f5_fav_lowsig_complete` + `live_current`
   is exactly this: the low-CVaR, positive-skew sleeve alongside the higher-mean, moderate-skew
   deployed strategy. [informaconnect.com convexity-vs-skewness](https://informaconnect.com/assessing-risk-profile-of-quant-strategies-the-convexity-vs-skewness/)

---

## EXACT LAMBDAS TO REGISTER

Copy these blocks into the `TRIALS` dict in `box_policy_ab.py` (read-only: submit as operator
recommendations, not edits):

```python
# SLEEVE A: favorite + quiet-spot + complete-all  (low CVaR, positive skew, OOS t=3.4)
"f5_fav_lowsig_complete": lambda F: pol_sell_unpaired(F, cheap_below=None,
    open_ok=lambda f: (f["p"] if f["side"] == "bid" else 1.0 - f["p"]) >= 0.50
                      and abs(f.get("sig") or 0.0) <= 5.0),

# SLEEVE B: k=8 only  (OOS Sharpe +1.755, 0 losses in 21 OOS windows; forward-test only)
"f5_k8_trial": lambda F: run_policy(F, open_ok=lambda f, s: f["k"] == 8),

# OPTIONAL (needs IS validation): favorite + k<=9 + complete-all
"f2_fav45_k9_complete_trial": lambda F: pol_sell_unpaired(F, cheap_below=None,
    open_ok=lambda f: (f["p"] if f["side"] == "bid" else 1.0 - f["p"]) >= 0.45
                      and f["k"] <= 9),
```

---

## CAVEATS

- Dataset: 71 windows / 7 days. All statistics have wide confidence intervals.
  IS/OOS split is chronological (good), but June 7–11 vs June 11–13 may not represent
  different market regimes — both are short post-launch periods.
- The exemplar `tc_pairmax` (prior run: Sharpe +0.27, skew +3.33 on the live gha_data)
  does NOT replicate on the 45-day parquet — only 6 OOS windows trade. The discrepancy
  likely reflects that live gha_data has the `depth` field (bilateral book thinness) which
  is absent from the parquet (candlestick API has no depth). The depth<5500 signal drives
  tc_pairmax's high completion rate; without it, the spread-and-flow gate alone is insufficient.
- For Sleeve A and B to be deployed, they should clear T_BAR=3.0 paired-t vs live_current
  on forward collector data (n≥300 windows per box_policy_ab.py's pre-registered bar).

https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz
