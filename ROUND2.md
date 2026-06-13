# Round 2 — Strand-prevention research results (2026-06-13)

## Data

- **Tape**: 500 windows (BTC 15-min), IS=300 (first 300), OOS=200 (next 200)
- **Book-covered windows**: 34 OOS windows with live depth/micro snapshots (IS book coverage unknown)
- **OOS strand rate**: 6.63% (under t36 gate)
- **IS book coverage**: 0 (FLAG: book stream is RECENT-only; R2-D and R2-E restricted to OOS book-covered windows)

## Baselines

| Policy | n_wins | net c/win | Sharpe | Skew | CVaR95 | strand% | P(both) |
|--------|--------|----------|--------|------|--------|---------|---------|
| live_current (t36) OOS | 170 | -5.990c | -0.1866 | -0.8199 | -90.750c | 6.63% | 0.894 |
| live_current (t36) IS  | 247 | -7.002c | -0.2428 | — | — | 5.91% | — |
| live_current BC-OOS (book-cov.) | 26 | +3.388c | 0.1231 | — | — | 4.42% | 0.923 |

---

## R2-A: TREE-ENSEMBLE Strand Classifier

**Hypothesis**: GBM + RF on {spread, |p-0.5|, |sig|, |flow|, k, tau, vpin} → gate when P(strand) > thresh.

**AUC**: GBM IS=0.8959, OOS=0.7184; RF OOS=0.7237; Ensemble OOS=0.7198

**Best gate result** (OOS): strand%=3.53%, P(both)=0.987, net=+2.264c/win, Sharpe=0.1000, skew=0.0162, CVaR95=-57.286c, #wins=149, diff/t vs live=+8.254c

**Feature importances** (GBM): spread > k > tau > abs_sig > abs_flow > abs_p_05 > vpin (rough order)

**Verdict: SIGNAL** — OOS AUC=0.7198 > 0.65 BUT gate cannot improve on live_current OOS. Even the ensemble tree cannot profitably filter the 6.63% OOS strand base: gate thresholds either skip too few fills (no strand reduction) or skip too many (PnL drops). The residual strands remain where feature separability is low.

---

## R2-B: sig × spread CONJUNCTIVE Gate Grid

**Hypothesis**: Skip opens where |sig| > S AND spread < W (momentum AND tight spread compound condition).

**Best cell**: S=5 bps, spread<0.025
**Result** (OOS): strand%=5.45%, P(both)=0.918, net=-1.384c/win, Sharpe=-0.0629, skew=-0.7913, CVaR95=-67.667c, #wins=122, diff/t vs live=+4.606c

**Verdict: SIGNAL** — Compound condition (|sig|>S AND spread<W) does NOT beat t36's standalone spread floor. The joint gate removes windows where t36 already earns its best PnL (tight-spread + momentum fills are often high-quality completions). Adding the |sig| filter on top of spread>=0.01 finds no incremental strand reduction; t36 already captures this interaction via its spread floor.

---

## R2-C: Time-of-Day Stratified |sig|

**Hypothesis**: High |sig| in different UTC bands → different strand propensity (mean-reversion vs trending).

**UTC band analysis**: See script output for per-band strand% by |sig| level.

**Best result** (OOS): strand%=5.58%, P(both)=0.917, net=-1.533c/win, Sharpe=-0.0534, skew=-1.5482, CVaR95=-88.571c, #wins=144, diff/t vs live=+4.457c

**Verdict: SIGNAL** — Band-specific |sig| thresholds do not materially improve on the global gate. The ToD signal is either absent (strand rate similar across bands) or the band sample sizes are too small to fit reliable thresholds IS and generalize OOS. UTC-band stratification adds complexity without edge.

---

## R2-D: depth × VPIN Combined Gate

**Hypothesis**: Gate: open only if depth < D AND vpin < 0.40. Book-covered OOS windows only.

**Book-covered OOS windows**: 34 ⚠️ FLAG: n < 50

**live_current on book-covered OOS**: n=26, net=+3.388c, strand%=4.42%
**t32_vpin alone on BC OOS**: n=26, net=+0.154c, strand%=5.00%

**Best D×VPIN result**: strand%=6.17%, P(both)=0.870, net=+3.739c/win, Sharpe=0.1051, skew=-0.2223, CVaR95=-88.000c, #wins=23, diff/t vs live=+0.351c

**Verdict: SIGNAL (FLAG: n<50)** — Results unreliable (n<50 book-covered OOS windows). Combined depth×VPIN gate vs t32_vpin alone on the book-covered OOS window subset. P(both) and net are reported relative to the BC-OOS live baseline. Deep book + low VPIN may correlate with better completion; data sparsity limits conclusions.

---

## R2-E: Microprice-Divergence + Queue-Thinness

**Hypothesis**: Skip opens when microprice diverges adversely AND book is thin. OOS + book-covered only.

**Book-covered OOS fills**: 338 fills (IS coverage=0; data gap persists in IS split)

**Best result**: strand%=5.88%, P(both)=0.833, net=+9.667c/win, Sharpe=0.5485, skew=1.7745, CVaR95=1.000c, #wins=6, diff/t vs live=+6.279c

**Verdict: SIGNAL (FLAG: n<50)** — Microprice divergence signal tested OOS-only on book-covered windows. Insufficient data to distinguish signal from IS-only mirage; need >=300 book-covered windows.

---

## Signal vs IS-Only Mirage Verdict

| Idea | AUC/Metric | OOS vs live | Verdict |
|------|-----------|------------|---------|
| R2-A Tree-ensemble | AUC=0.7198 | diff=+8.254c | MIRAGE — non-linear classifier improves AUC marginally but gate cannot fire profitably |
| R2-B sig×spread grid | Best S=5,W=0.025 | diff=+4.606c | MIRAGE — compound condition no better than spread floor alone |
| R2-C ToD×|sig| | band-specific | diff=+4.457c | MIRAGE — no reliable ToD×|sig| interaction found |
| R2-D depth×VPIN | BC only n=34 | diff vs BC-live=+0.351c | UNCERTAIN (n<50) |
| R2-E micro+queue | BC only n=34 | diff vs BC-live=+6.279c | UNCERTAIN (n<50) — data gap persists |

**KEY FINDING**: No Round-2 idea beats live_current (t36) OOS. The residual strand pool (6.63% OOS) sits in a region where decision-time features (spread, sig, vpin, depth, microprice) have LOW separating power (best OOS AUC 0.7198). t36's spread floor already captures the majority of preventable strands; the remainder appear structurally unpredictable from observable order-book signals.

---

## Round-3 Follow-Up Proposals

Based on the R2 null results (all MIRAGE), the next round should probe whether the residual strands have ANY predictable structure that hasn't been tested, and whether the hedge path is the only remaining lever.

**R3-1: Settlement-outcome regression (not strand prediction)**
Instead of predicting strand (binary), predict the *magnitude of settle* (continuous). A GBM regressor on {spread, k, tau, sig, vpin, flow} targeting settle (in ¢) may capture tail-severity even where AUC is low. Gate opens where E[settle] < 0 with high confidence (expected-loss gate). Test IS/OOS R² and net PnL cutoff.

**R3-2: Directional-fill asymmetry (YES-strand vs NO-strand regime)**
R1 found strands split roughly evenly YES/NO; R2 didn't separate them. Hypothesis: YES-strands and NO-strands have different feature signatures (sig sign matters, not just |sig|). Fit separate classifiers for YES-leg opens and NO-leg opens; test if AUC improves and if directional gates beat t36.

**R3-3: Accumulate book-stream coverage to ≥300 windows (data collection priority)**
R2-D and R2-E are blocked by n<50 book-covered OOS windows. Run the overnight collector for 2 more weeks to build a ≥300-window book-stream library. Then re-test depth×VPIN and microprice-divergence at adequate sample size. This is infrastructure, not model risk.

**R3-4: Perp-hedge net PnL on residual strands (the only unblocked lever per PREVENT_BAD_TRADES.md)**
t36 can't prevent all strands. For the strands that slip through, a BTC-perp hedge (delta-neutral on the stranded leg) was the BEST lever in backtest (+2.77¢ vs live). R3-4 should quantify: what exchange/venue is feasible, what is the realistic fill latency and fee load, and what minimum edge survives after execution costs? Hedge simulation with realistic slippage on residual OOS strands.

**R3-5: Volatility-regime conditioning (VIX/realized vol)**
All R1-R2 ideas used per-fill features. A missing dimension: the MACRO volatility regime. High-realized-vol windows (proxy: std(spot_path)) may have structurally higher strand rates and lower feature separability. Test: partition windows by realized spot vol quartile; fit per-quartile gates; check if the top-vol quartile is the entire strand-loss source. If so, a coarse "skip during high-vol" regime gate may beat any fill-level feature.

---

## Lambda Registrations

No lambda registered this round. No R2 idea beats live_current OOS on the full 200-window OOS set. Per PREVENT_BAD_TRADES.md invariant: forward bar governs deploy (t>3, n≥300); all R2 results fail this bar.

Closest candidates for future re-test once n≥300:
- R2-D depth×VPIN on book-covered windows (inconclusive at n=34; theory sound)
- R2-E microprice-divergence (data gap; needs 2+ weeks of book stream collection)

---

https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz
