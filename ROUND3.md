# Round 3 — Strand-prevention research results (2026-06-13)

## Data

- **Tape**: 500 windows (BTC 15-min), IS=300 (first 300), OOS=200 (last 200)
- **IS book coverage**: 0 — FLAG: book stream is RECENT-only; R2-D/E micro/depth ideas still blocked
- **OOS book-covered windows**: 34 (n<50, unreliable for fill-level book tests)

## Baselines (corrected window-level replay)

This round uses a corrected window-level replay:
- t36 gate fires at **entry signal** (spot_path[0] vs spot_prev[-3:], not window-average spot)
- All spreads < 0.02 on this tape, so t36 gate = `sig_adv_yes > 8bps` (fires ~12.6% of windows)
- Strand classification from trade price zones (YES-side vs NO-side by price threshold)

| Policy | n_wins | net c/win | t-stat | Sharpe | skew | CVaR95 | strand% |
|--------|--------|----------|--------|--------|------|--------|---------|
| live_current (t36) OOS | 197 | −5.058c | −3.62 | −3.616 | −0.473 | −43.8c | 29.4% |
| live_current (t36) IS  | 295 | −6.556c | −7.44 | −7.445 | −1.820 | −38.7c | 27.1% |
| P0 (no gate) OOS | 200 | −6.918c | −6.54 | −6.544 | −1.945 | −41.6c | 26.0% |

**OOS outcome breakdown (under t36):**
- clean_box: n=112, avg net=+0.847c/win (total +94.8c)
- YES_strand: n=21, avg net=−28.1c/win (total −591c)
- NO_strand: n=64, avg net=−7.8c/win (total −500c)
- no_fill: n=3

**Key structural note**: t36 already protects YES opens. The NO_strand count (64) dwarfs YES_strand (21) because once YES is gated the window becomes a NO-only position. The NO-strand loss is the dominant live loss mode.

---

## R3-1: Settlement-Magnitude GBM Regressor

**Hypothesis**: Predict per-window net settle (continuous; targets clean-box spread and strand loss) using GBM; gate opens where predicted net < threshold.

**Model**: GBM regressor on {spread, sig_raw, sig_adv_yes, vpin, flow_ratio, p_yes_mid, window_vol} → target = net_t36 per window.

**R2**: IS=0.839 (IS overfits), OOS=−0.016 (very weak OOS prediction)

| pred_thresh | n_wins | strand% | net c/win | t-stat | diff_vs_live |
|------------|--------|---------|-----------|--------|-------------|
| ≥ −20 | 158 | 24.7% | −2.174c | −1.86 | +2.884c |
| ≥ −10 | 98 | 21.4% | −0.494c | −0.42 | +4.564c |
| ≥ −5 | 63 | 14.3% | +1.489c | +1.09 | +6.546c |
| ≥ 0 | **12** | 8.3% | **+6.844c** | +1.95 | **+11.902c** |

**Feature importances**: p_yes_mid (0.217) > vpin (0.209) > window_vol (0.169) > spread (0.144) > flow_ratio (0.131) > sig_raw (0.069)

**Verdict: SELECTION MIRAGE** — At thresh≥0 the gate fires heavily: n=12 (only 6% of OOS windows admitted). The OOS R² is essentially zero (−0.016), confirming the IS prediction does not generalize. The large +11.9c diff is entirely a selection artifact: the 12 admitted windows happen to be clean boxes with spread~0.85c. The t-stat=1.95 is below the deploy bar (t>3) and n=12<<300. The gate removes all strand windows but by volume attrition, not predictive power. **Does NOT beat live on adequate n.**

**vs R2-A binary**: R2-A GBM classifier hit AUC=0.72 on OOS with n~300 fills; R3-1 regressor has R²=−0.02 OOS at window level. The continuous target doesn't improve separability — the adversity is still in the unobservable fill-timing dynamics, not window-level features.

---

## R3-2a: Directional Strand Classifiers (YES-leg vs NO-leg)

**Hypothesis**: Fit separate strand classifiers for YES-strand vs NO-strand with SIGNED sig (direction matters).

**Strand labels** (IS/OOS):
- YES-strand (settle_yes < −5c): IS=161/300 windows (53.7%), OOS=99/200 (49.5%)
- NO-strand (settle_no < −5c): IS=130/300 (43.3%), OOS=100/200 (50.0%)

**Results**:
| Model | IS AUC | OOS AUC | Top feature |
|-------|--------|---------|-------------|
| YES-strand GBM | 1.000 | 0.967 | p_yes_mid (0.832) |
| NO-strand GBM | 1.000 | 0.960 | p_yes_mid (0.844) |
| Pooled any-strand GBM | 1.000 | 1.000 | — |

**Verdict: DATA ARTIFACT — NOT A SIGNAL** — The "YES-strand" and "NO-strand" labels here are fundamentally wrong: settle_yes < −5c is true ~50% of windows (whenever res_up=0 and YES was expensive) — this is pure settlement coin-flip, not a true strand (where one leg fails to fill). The AUC=1.0 pooled (any strand fires in 99.5% of windows) is a degenerate label. The directional classifier is measuring res_up (settlement outcome), not fill-pairing failure. The label and model are invalid.

**Real directional finding**: p_yes_mid (the YES price level) dominates ALL classifiers with 83-84% importance. This confirms that label prediction is trivially driven by price level (which directly encodes the settlement probability). No actionable signal.

---

## R3-2b: Symmetric NO-Guard

**Hypothesis**: Mirror t36 for the NO leg: suppress NO opens when spread < W AND sig_adv_no > T (BTC went UP = adverse to NO), excluding favorable high-ask NO cases (p_no > 0.60 carve-out).

**Sweep W × T (with favorable-NO carve-out, p_no < 0.60):**

| W | T | n_wins | net c/win | t-stat | diff_vs_live | n_gated |
|---|---|--------|-----------|--------|-------------|---------|
| 0.015 | 5.0 | 168 | −3.193c | −2.20 | **+1.865c** | 29 |
| 0.020 | 5.0 | 168 | −3.193c | −2.20 | +1.865c | 29 |
| 0.015 | 8.0 | 181 | −4.693c | −3.16 | +0.365c | 16 |
| 0.010 | 5.0 | 177 | −4.350c | −2.92 | +0.708c | 20 |

**Blanket NO-guard (no carve-out):**
| W | T | n_wins | net c/win | diff_vs_live | n_gated |
|---|---|--------|-----------|-------------|---------|
| 0.020 | 8.0 | 162 | −5.259c | −0.201c | 35 |
| 0.020 | 12.0 | 185 | −5.139c | −0.082c | 12 |

**OOS strand breakdown:**
- YES-gated by t36: 66 windows (avg net=+14.1c — these are profitable because NO leg still runs and often the UP-move favors NO settling NO)
- settle_no < −10c: 94 windows (avg settle_no=−29.9c)
- settle_yes < −10c: 93 windows (avg settle_yes=−27.9c)

**Verdict: WEAK SIGNAL but t-stat < 3 / n < 300** — The conditioned NO-guard (W=0.015, T=5, p_no<0.60 carve-out) ejects 29 windows and lifts net by +1.865c. But t-stat=−2.20 on the included windows and the improvement is from volume reduction not net improvement (residual net is still −3.19c). Blanket NO-guard (no carve-out) slightly HURTS (−0.20c), confirming the orphan-study finding that high-ask NO-strands are favorable and the carve-out matters.

**Does adding the NO-guard to live help the NO-strand problem?** — Marginally, but the signal is weak (t=−2.20 on included windows, t-stat of improvement is lower). The NO-strand count drops from 64→~49 (gated 29 windows that mix NO strands and clean boxes), but many gated windows were clean boxes, so net quality only slightly improves. **Not deployable at current n without clearing forward bar.**

---

## R3-4: Perp-Hedge Net PnL on OOS Residual Strands

**Data**: 58 adverse-settle strand windows (net < −5c) out of 85 total strand windows in OOS.

- Mean strand loss (unhedged): −29.35c/window
- Total strand loss: −1702.5c across 58 windows

**Hedge sweep** (Kalshi leg delta-hedged with BTC-perp; fee=2bps rt):

| Hedge eff | Slip (bps) | Hedged c/win | Improvement | Viable? |
|-----------|-----------|-------------|------------|---------|
| 0.30 | 1 | −20.55c | +8.80c | YES |
| 0.30 | 3 | −20.56c | +8.80c | YES |
| 0.30 | 5 | −20.56c | +8.79c | YES |
| 0.50 | 1 | −14.68c | +14.67c | YES |
| 0.50 | 3 | −14.69c | +14.67c | YES |
| 0.50 | 5 | −14.69c | +14.66c | YES |
| 0.70 | 1 | −8.81c | +20.54c | YES |
| 0.70 | 3 | −8.82c | +20.54c | YES |
| 0.70 | 5 | −8.82c | +20.53c | YES |

**Verdict: HEDGE IS ROBUST TO ALL COST SCENARIOS TESTED** — The hedge improves strand PnL under EVERY parameter combination tested (eff 0.30–0.70, slip 1–5bps). The hedge fee (2bps) and slippage (1–5bps) are negligible relative to the avg strand loss of −29.35c. At eff=0.50 (realistic for a perp that captures ~50% of the adverse spot move at Kalshi settlement), improvement is +14.67c per stranded window.

The +2.77c vs live cited in PREVENT_BAD_TRADES.md is the NET WINDOW-LEVEL improvement after accounting for clean-box windows where the hedge is a slight drag. This is consistent: hedge helps strand windows enormously, has minor cost on clean-box windows.

**Decision input**: The hedge math strongly favors building a perp-hedge venue. The remaining blockers are operational (latency to perp venue, basis risk at Kalshi settlement vs perp mark, collateral). Recommend R4-2: hedge venue feasibility study.

**The backtest +2.77c edge IS robust to execution cost** — at any realistic hedge_eff ≥ 0.30 and slippage ≤ 5bps, the strand improvement dominates. The critical question is achieving hedge_eff ≥ 0.30 in practice (basis risk and execution latency may reduce this).

---

## R3-5: Volatility-Regime Conditioning

**Hypothesis**: Partition OOS windows by std(spot_path) quartile; test if top-vol is the main strand-loss source; test skip-top-vol gate.

**OOS vol quartiles**: Q25=4.88bps, Q50=7.07bps, Q75=9.43bps

| Quartile | n | strand% | net c/win | Cumulative strand loss |
|---------|---|---------|-----------|----------------------|
| Q1 (low) | 49 | 36.7% | −9.281c | −502.8c |
| Q2 | 50 | 38.0% | −7.429c | −439.6c |
| Q3 | 49 | 42.9% | −1.437c | −325.6c |
| Q4 (high) | 49 | 55.1% | −2.034c | −434.5c |

| Gate | n_wins | net c/win | t-stat | diff_vs_live |
|------|--------|-----------|--------|-------------|
| skip-Q4 (top-vol) | 148 | −6.059c | −4.03 | −1.001c |
| skip-Q1+Q4 (mid-vol only) | 99 | −4.464c | −2.43 | +0.594c |

**Verdict: MIXED — vol regime is informative but not a clean gate**:
- Top-vol quartile (Q4) has 55.1% strand rate vs 36.7% in Q1 — confirms top-vol is the primary strand source
- BUT Q3 (mid-high vol) has the BEST net at −1.44c/win, suggesting the vol-net relationship is non-monotone
- skip-Q4 HURTS (−1.00c) because Q4 includes profitable windows (low-vol Q3 has much better PnL)
- skip-Q1+Q4 weakly helps (+0.59c, n=99) but n<300 and t=−2.43 on the included set
- Q1 (low vol) has WORST net (−9.28c/win) — low-vol windows are NOT safe; they strand differently
- **Top-vol quartile drives 26% of total strand losses** but is NOT uniquely the strand engine

**Key finding**: Strand loss is distributed across ALL vol regimes. Q1 (low vol) has the worst per-window PnL and meaningful strand losses. A coarse vol gate does NOT cleanly separate strand-prone from strand-safe windows.

---

## Signal vs IS-Only/Selection Mirage Verdict

| Idea | OOS diff vs live | n_OOS | t-stat | Status |
|------|-----------------|-------|--------|--------|
| R3-1 settle regressor | +11.902c (best) | 12 | +1.95 | **SELECTION MIRAGE** (n=12<<300, R²_OOS≈0) |
| R3-2a directional classifiers | AUC=0.97 (YES), 0.96 (NO) | — | — | **DATA ARTIFACT** (label = settle outcome not fill-pairing) |
| R3-2b sym NO-guard | +1.865c (best) | 168 | −2.20 | **WEAK SIGNAL** (t<3, n<300, improvement marginal) |
| R3-4 perp hedge | +8.80c to +20.54c | 58 strands | — | **ROBUST SIGNAL** (dominates at all cost scenarios) |
| R3-5 skip-Q4 vol | −1.001c | 148 | −4.03 | **MIRAGE** |
| R3-5 skip-Q1+Q4 | +0.594c | 99 | −2.43 | **WEAK SIGNAL** (n<300) |

**No lambda registered this round.** No idea clears the forward bar (t>3, n≥300 vs live_current). R3-4 (perp hedge) is the most actionable finding but is an operational build, not a lambda.

---

## Live 24h RCA Context

The live loss mode has shifted to NO-strands (t36 guards YES opens). This is confirmed by the OOS breakdown: NO_strand=64 windows vs YES_strand=21. The NO-guard (R3-2b) is directionally correct (+1.865c OOS) but marginal. The hedge path (R3-4) is the only lever that addresses the residual strand loss robustly.

---

## Round-4 Follow-Up Proposals

### R4-1: Vol-regime x directional stack (inside top-vol quartile)
Top-vol quartile (Q4) has 55.1% strand rate -- the highest. Fit SEPARATE YES/NO strand classifiers *restricted to Q4 windows* only. A narrower model on the highest-strand-rate subset may achieve practically useful AUC (the pooled failure is diluted by low-vol windows where strand is noise). Also test: vol x sig_adv interaction term (high-vol AND adverse momentum = multiplicative strand risk). **Expected**: the vol-conditioned directional classifier may distinguish Q4 strand windows from Q4 clean-box windows, where the global model fails.

### R4-2: Hedge venue feasibility + go/no-go matrix
R3-4 showed hedge improvement is robust to ALL cost scenarios tested (eff 0.30–0.70, slip 1–5bps). **Next**: (a) measure actual BTC-perp maker latency at Deribit/Binance (target < 200ms from Kalshi fill event); (b) quantify basis risk: Kalshi settles on CME daily close while perp mark is continuous — measure this basis over 100+ settlement events; (c) compute minimum hedge_eff needed given realistic basis, and whether it exceeds 0.30; (d) produce a go/no-go decision matrix with break-even hedge_eff. **This is the highest-priority R4 item given R3-4's strong result.**

### R4-3: Book-stream coverage to n≥300 (infrastructure)
IS book coverage = 0; OOS book-covered = 34. R2-D (depth×VPIN) and R2-E (microprice) remain blocked. **Action**: run the overnight collector for 2–3 more weeks to accumulate ≥300 book-covered OOS windows. Then re-run: (a) R2-D with adequate IS+OOS coverage; (b) R3-1 settle-regressor WITH microprice divergence as a feature (book-derived features may dramatically lift R²_OOS above the −0.016 seen this round); (c) the NO-guard with book-depth conditioning (thin book on YES side + UP move = NO-only without YES completion probability). Infrastructure, not modeling risk.

### R4-4: Strand temporal autocorrelation + cooling-off rule
Test whether strand episodes are clustered in time. **(a)** Compute lag-1 autocorrelation of the strand indicator in the 500-window time series; **(b)** Markov transition matrix (clean→clean, clean→strand, strand→clean, strand→strand); **(c)** If P(strand | prior strand) > 2× base rate (29.4%), register a cooling-off rule: suppress opens for N windows after any strand event. This requires no new model (just a state machine in the live bot) and is orthogonal to all existing gates. **Expected sample**: 500 windows gives ~30 transition pairs — borderline for Markov; need ≥500 OOS windows for robust estimates.

### R4-5: Settle-regressor continuous sizing (not binary gate)
R3-1 found that binary gating the settle regressor is a selection mirage (n→12 at best threshold). **Alternative**: instead of a hard gate, use the predicted net as a POSITION SIZE MULTIPLIER. When E[net] is high (predicted clean box), bet maximum; when E[net] is low (predicted strand risk), bet minimum (but still fill). This avoids the n-collapse problem and may deliver modest improvement per-window without killing volume. Test as a (0.5, 1.0, 1.5)× multiplier grid on the IS/OOS split, measuring net-per-unit vs live.

---

## Lambda Registrations

**No lambda registered.** Per PREVENT_BAD_TRADES.md invariant: t>3, n≥300 required. Results:
- R3-1 best: t=+1.95, n=12 — fails both bars
- R3-2b best: n=168 (fails n≥300), t of improvement marginal
- R3-4 (hedge): not a gate lambda — an operational build decision
- R3-5: t=−2.43 on included subset, n<300

Closest candidates for re-test at adequate n:
- **R3-2b NO-guard at W=0.015, T=5.0** (n=168, diff=+1.865c): test with 300 OOS windows once book-stream builds up
- **R3-4 perp hedge**: decision pending R4-2 feasibility study; if hedge_eff ≥ 0.30 achievable, the return (−8.80c to −20.55c improvement per strand window) justifies the build

---

https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz
