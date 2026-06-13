# Round 5 (FINAL) — Strand-Prevention Research Results (2026-06-13)

## Data

- **Tape**: 500 windows (BTC 15-min), IS=300 (first 300), OOS=200 (last 200)
- **Baseline (live_current)**: OOS mean=+1.738c/win, strand%=10.0% (20/200 windows)
- **Early-flow coverage**: 67/200 OOS windows have trades in first 60s (33.5%)

---

## R5-1 (MAKE-OR-BREAK): EARLY-WINDOW CAUSAL FLOW

### Background

R4-4 found `flow_ratio` (full-window YES-volume fraction) delivers t=4.05 on sizing but is
LOOK-AHEAD (uses all 15 minutes of trades). R5-1 causalized it: compute flow from only trades
in the first {30, 60, 90}s after window open.

### (a) Correlation: early-flow vs full-window flow_ratio

| Early cutoff | n (OOS) | corr vs full | p-value | corr vs net_live | p-value |
|-------------|---------|-------------|---------|-----------------|---------|
| ef30 (30s)  | 64      | 0.429       | 0.0004  | +0.079          | 0.53    |
| ef60 (60s)  | 67      | 0.487       | <0.001  | −0.015          | 0.90    |
| ef90 (90s)  | 72      | 0.539       | <0.001  | −0.046          | 0.70    |

**Key finding**: Early-flow IS correlated with full-window flow (r=0.43–0.54, p<0.001). But
early-flow has ZERO correlation with net_live outcome (r≈−0.02 to +0.08, p>0.5). The same
pattern holds in-sample (IS ef60 corr vs net: r=−0.007, p=0.95).

### (b) Sizing: 0.5/1/1.5x by early-flow

| Policy | n (OOS) | net c/win | vs_live | t_vs_live |
|--------|--------|-----------|---------|-----------|
| live_current | 200 | +1.738c | — | — |
| ef60 sizing (1.5x if >0.55, 0.5x if <0.45) | 200 | +1.620c | −0.118c | −0.320 |

### VERDICT: EARLY-FLOW DOES NOT BEAT LIVE

**The look-ahead mirage (t=4.05 in R4-4) does NOT survive causalization.**

- Early-flow (first 60s) IS correlated with full-window flow (r=0.49) — the signal exists.
- But early-flow has NO correlation with the window's net P&L (r=−0.015, p=0.90).
- Sizing by early-flow yields t=−0.32 OOS (vs t=4.05 for full-window look-ahead).
- Coverage limitation: only 33.5% of OOS windows have trades in the first 60s. The 67 windows
  with early-flow data are not systematically different, but n=67 constrains inference.
- The full-window flow_ratio predicts net because it aggregates the SAME information that
  determines settlement (late-window momentum). Early flow does not.

**This closes the R4-4 loop: flow_ratio is a look-ahead mirage with no causal counterpart.**

---

## R5-5: STRAND-STREAK CONTINUOUS SCALE-DOWN

### Background

R4-5 found lag-1 strand autocorrelation 2.60× (chi2 p=0.025): P(strand|prior strand)=17.6%
vs base rate 6.8%. Streak scale-down applies a continuous size multiplier after consecutive
strands, preserving more volume than binary cooling-off.

### OOS backtest (200 windows, 20 strands, 16 runs, max run=2)

| Policy | n_active | net c/win (active) | vs_live | t_paired | maxConsecLoss | CVaR95 |
|--------|----------|-------------------|---------|----------|---------------|--------|
| live_current | 200 | +1.738c | — | — | −87.7c | −39.1c |
| streak_scaledown(0.75,0.5,0.25) | 200 | +1.900c | +0.162c | 1.717 | −76.8c | −37.1c |
| binary cooling-off N=1 (skip) | 180 | +2.672c | +0.667c (all-win) | 1.773 | −44.0c | −37.6c |
| scaledown(0.50,0.25,0.0) | 200 | +2.067c | +0.328c | 1.745 | −65.8c | −36.5c |
| scaledown(0.25,0.25,0.25) | 200 | +2.238c | +0.500c | 1.773 | −54.9c | −36.5c |

### Verdict: RISK CONTROL, NOT ALPHA

- **t-statistics are in the 1.70–1.77 range** — below the deploy bar (t>3, n≥300) and
  below the screen bar (t>2, n≥200). Neither streak scale-down nor binary cooling-off
  beats live at statistically adequate confidence.
- **Risk benefits are real but modest**:
  - Scale-down (0.75,0.5,0.25): maxConsecLoss reduced 12% (−76.8c vs −87.7c), CVaR95 improved 5%
  - Binary N=1: maxConsecLoss cut 50% (−44c vs −87.7c) — the larger benefit because it fully
    skips the post-strand window
  - 4 multi-run strands in OOS (25% of runs): the tail-risk case that scale-down targets
- **Deployable as RISK CONTROL** (no model, deterministic): after a strand, reducing size to
  0.75x for the next window costs almost nothing in mean (−0.16c/win) while slightly reducing
  the CVaR tail. The simplest implementation: scale back to 0.75x after any strand, reset on clean.
- **Does it cap streak risk vs binary N=1?** Scale-down retains ~11% more volume than binary
  N=1 (200 vs 180 active windows) at the cost of higher maxConsecLoss (−76.8c vs −44.0c).
  Binary N=1 is better for tail control; scale-down is better for volume retention.

---

## R5-3: NO-GUARD + EARLY YES-SIDE PRESSURE (extend R3-2b)

### Background

R3-2b found W=0.015, T=5bps, p_no<0.60 carve-out was +1.865c but t=−2.20 on n=168.
R5-3 adds early YES-side taker pressure (first-60s buy imbalance) as a 2nd trigger.

### OOS results

The R3-2b gate fires on only **2/200 OOS windows** (1.0%) — extremely sparse. The 2 windows
where it fires are high-vol, strong-momentum UP windows where NO-only wins (res_up=0 in both,
settle_no_only = +37.3c mean). This makes the R3-2b net on its own windows look positive, but
the base n=2 is too small to generalize.

| Policy | n | net c/win | vs_live | t_vs_live |
|--------|---|-----------|---------|-----------|
| R3-2b only | 200 | +1.420c | −0.318c | −0.246 |
| R3-2b + ep60>0.55 | 200 | +1.720c | −0.018c | −0.012 |
| R3-2b + ep60>0.60 | 200 | +1.488c | −0.250c | −0.164 |
| R3-2b + ep60>0.65 | 200 | +1.668c | −0.070c | −0.047 |
| R3-2b + ep60>0.70 | 200 | +1.405c | −0.333c | −0.244 |
| R3-2b + ep60>0.75 | 200 | +1.723c | −0.015c | −0.011 |

### Verdict: DOES NOT CLEAR EVEN t=1.5

Best extension (ep60>0.55) reaches t=−0.012 — essentially noise. The early YES pressure
trigger fires on 25 additional windows but those windows average near live_current performance.
Adding ep60 as a trigger does not strengthen the NO-guard signal; it slightly dilutes it.

**Root cause**: R3-2b's R3 result (+1.865c, n=168) was in a different OOS subset (R3 used IS=300,
OOS was the 168-window section with a different temporal split). On this tape's OOS=200, the gate
fires only twice (n=2), making any result statistically meaningless. The t=−2.20 in R3 was itself
below the deploy bar; this round confirms the NO-guard idea lacks consistent signal.

---

## R5-2: HEDGE TIMING — PROPHYLACTIC VS REACTIVE

### Background

R4-2 found hedge t=4.63 (n=200) but assumed oracle-known strand events (reactive post-hoc).
R5-2 models what is actually deployable: prophylactic (hedge every NO-only position at fill).

### Hedge model

When t36 fires (NO-only position, 17.5% of windows = 35 OOS windows):
- Prophylactic: open long BTC perp at fill, close at settlement
- Drag on clean NO-only windows: −(slip_fee_bps/1e4) × notional
- Gain on strand windows: hedge_eff × BTC_move_pct × notional

### OOS results (hedge_eff=0.50, slip+fee=5bps)

| Policy | n | net c/win | vs_live | t_paired |
|--------|---|-----------|---------|----------|
| live_current | 200 | +1.738c | — | — |
| prophylactic (every NO window) | 200 | +1.740c | +0.002c | 0.107 |
| reactive intra (trigger>20bps) | 200 | +1.745c | +0.007c | 0.027 |
| reactive intra (trigger>30bps) | 200 | +1.743c | +0.005c | 0.021 |

### Verdict: PROPHYLACTIC DRAG ELIMINATES R4-2'S ADVANTAGE

The R4-2 t=4.63 assumed a reactive hedge that fires ONLY on confirmed strand windows (oracle).
In practice:
- Prophylactic: drag on 35 NO-only windows. Most NO-only windows (42.9%) resolve correctly
  (NO wins), meaning the hedge drag is pure cost on ~60% of NO-only hedged windows. Net
  improvement: +0.002c/win (t=0.107).
- The fundamental problem: R²=0.017 (R4-2 finding) means only 1.7% of strand loss variance
  is BTC-move-correlated. A BTC perp hedge cannot capture the binary settlement risk.
- **The BUILD VENUE recommendation from R4-2 was based on oracle-reactive hedging. R5-2
  shows prophylactic hedging does not work.** The venue build is not justified unless a
  strand can be detected before settlement — which is only possible at minute 14 (too late
  to hedge profitably with current latency).
- Adaptive hedge size by |sig| adds no material improvement (t≈0.10 across all configurations).

---

## Summary: Did ANYTHING Beat Live Across All 5 Rounds?

| Round | Strategy | OOS n | net c/win | vs_live | t_diff | Verdict |
|-------|----------|-------|-----------|---------|--------|---------|
| R4-2 | hedge reactive (oracle) | 200 | +2.36c | +0.22c | 4.63 | ORACLE-ONLY — not deployable |
| R4-4 | full-window sizing | 200 | +4.97c | +2.83c | 4.05 | LOOK-AHEAD (flow_ratio) |
| R5-1 | ef60 causal sizing | 200 | +1.62c | −0.12c | −0.32 | No signal |
| R5-5 | streak scale-down | 200 | +1.90c | +0.16c | 1.72 | Risk control only |
| R5-3 | NO-guard+early-flow | 200 | +1.72c | −0.02c | −0.01 | No signal |
| R5-2 | prophylactic hedge | 200 | +1.74c | +0.00c | 0.11 | No edge (drag offsets) |
| R4-5 | cooling-off N=1 | 184 | +2.67c | +0.67c | 1.77 | Risk control only |
| R4-1 | Q4 classifier | 81 | +2.65c | +0.17c | 1.52 | Rediscovers t36 |
| R1-R3 | various gates | varies | — | — | <2 | All below bar |

**OVERALL VERDICT**: **No strategy clears t>3, n≥300 on OOS replay data in any round.**

The only t>2, n≥200 results are R4-2 (t=4.63, requires oracle-known strands) and R4-4
(t=4.05, look-ahead flow_ratio). Both are mirages that do not survive causal inspection.

The deployed t36 guarded-opener is the only validated signal (armed in forward A/B via
box_policy_ab.py). The research loop confirmed: strand prevention at the ENTRY level (t36)
is the right lever. No additional causal signal has been found to layer on top of it.

**Lambda registered: NONE** (no OOS causal t>2, n≥200 result found).

The closest to a deployable improvement from all 5 rounds:
1. Streak scale-down 0.75x after a strand (risk control, no alpha, trivially deployable)
2. Prospective forward-test of `f5_fav_lowsig_complete` in box_policy_ab.py (not yet at n≥300)

---

## 5 Most Valuable Next Directions

### 1. PROPHYLACTIC HEDGE — RETHINK THE MECHANISM (highest operational priority)

R4-2's oracle-reactive hedge (t=4.63) showed genuine P&L improvement, but R5-2 confirmed the
BTC-perp drag on clean NO-only windows eliminates the edge prophylactically. The correct path is:

**(a) Per-fill (not per-window) hedge**: open a BTC perp position ONLY on YES-side fills (the
strand-prone leg), not on NO-only windows. The YES fill is the exact directional risk event.
Close at the next minute mark or at settlement. This requires fill-time detection, not just
gate detection. The hedge should be sized proportional to the YES price (deep favorites have
less residual uncertainty). The drag is much smaller (only YES fills, ~50% of opens).

**(b) Intrawindow strand detection at minute 13**: if by minute 13 the YES leg has not paired
(open interest stayed single-leg), fire an emergency hedge. This is late but still reduces
settlement exposure for the remaining 2 minutes. Requires the live trader to track per-fill
pairing status.

Recommended venue: Deribit BTC-PERPETUAL (maker rebate −1bp, 5ms latency) as per R4-2.

### 2. BOOK STREAM ACCUMULATION + MICROPRICE GATE (blocked since Round 2)

IS book coverage is ZERO; OOS book coverage = 34 windows. The entire microprice-divergence
thread (R2-E), the depth×VPIN gate (R2-D), and book-depth conditioning for NO-guard are
blocked until sufficient book snapshots accumulate. With 3-4 more weeks of collection, aim
for 150+ OOS book-covered windows. At that point:
- Run depth×VPIN combined gate (R2-D): VPIN > 0.5 AND depth < 2000 = skip open
- Microprice divergence as causal sizing: if bid-side microprice > YES mid, YES fill more likely
- Book-depth conditioning for R5-3: thin YES book + UP sig = NO-only without YES fill risk

### 3. PROSPECTIVE A/B OF `f5_fav_lowsig_complete` (SLEEVE A — highest risk-adjusted candidate)

This policy (favorite leg cost ≥ 0.50, |sig| ≤ 5bps, complete-all strands) showed OOS Sharpe
+0.95 and CVaR95 22× safer than live in the LOW_RISK_SLEEVES study. It is already registered
in box_policy_ab.py's TRIALS dict. It needs n≥300 prospective forward windows to clear the
deploy bar. This is the most compelling unvalidated candidate:
- Complementary to t36 (t36 targets YES-strand prevention; Sleeve A targets entry quality)
- Positive skew (unlike live which has strand-driven negative tail)
- Deployable without any new infrastructure
Action: ensure the box_policy_ab.py accumulation is running for ALL registered trials;
prioritize live data collection to reach n≥300 prospective windows.

### 4. ONLINE ROLLING CLASSIFIER: EARLY-FLOW + VPIN + SPREAD

R5-1 showed early-flow alone is uncorrelated with outcomes. But the COMBINATION of early-flow
(YES taker pressure in first 60s), VPIN at fill time (strand predictor, r=−0.346 from
fingerprint_causality.py), and spread (available causally) may outperform any single signal.

Design: rolling logistic classifier trained on the last N=150 windows with known outcomes.
At each decision, predict P(strand) from {ef60, vpin, spread, sig_adv} → gate open if P < 0.2.
The rolling design avoids backtest overfitting (always trained only on past windows). Test
OOS AUC threshold: >0.57 to justify registering as T37. This requires maintaining a rolling
window of live fill outcomes — the data collection infrastructure is already in place via the
shadow collector. Expected time to 150-window training set: ~4 weeks at current rate.

### 5. STRAND CAUSATION MECHANISM STUDY (direct from R4-5 autocorrelation finding)

Lag-1 strand autocorrelation 2.6× (p=0.025) is the only statistically significant finding
across 5 rounds that is both causal and significant. The mechanism is unknown:

**(a) Structural/agent persistence**: the same informed agent trades across consecutive windows
(persistent VPIN). Test: does VPIN at lag-1 predict lag-1 strand given a prior strand?
If yes, extend the VPIN gate to a 2-window lookback: skip if VPIN was elevated in prior window.

**(b) Microstructure distortion**: after a strand, the spread may widen or book thin temporarily.
Test: spread at window t+1 after strand vs after clean. If wider, the post-strand window is
naturally protected (less fill risk anyway); the cooling-off may be redundant.

**(c) Calendar clustering**: strand runs may cluster at specific UTC hours (13-20 UTC is
highest vol). Test: strand autocorrelation by hour bracket. If clustering is hour-specific,
deploy hour-gated cooling-off: skip lag-1 only during 13-20 UTC, trade normally otherwise.
This would improve the cooling-off t-stat by focusing on the hours where lag-1 matters.

---

## Commit Record

No lambda registered this round. Closest candidates:

| Candidate | Constraint | Path |
|-----------|------------|------|
| Streak scale-down 0.75x | t<2, risk-control only | Deploy as protective behavior (no model) |
| f5_fav_lowsig_complete | Needs n≥300 prospective | Already in box_policy_ab.py A/B |
| Per-fill BTC hedge on YES legs | Needs venue build | R5 next-direction #1 |

---

https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz
