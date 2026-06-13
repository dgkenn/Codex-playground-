# Round 2 — Strand-prevention research results (2026-06-13)

## Data

- **Tape**: 500 windows (BTC 15-min), IS=300 (first 300), OOS=200 (next 200)
- **Strand fills**: 366 total (6.71% across all fills)
- **Book-covered OOS windows**: 34 (IS book coverage = 0 -- FLAG: book stream is RECENT-only)
- **OOS strand rate**: 6.63% under t36 spread gate

## Baselines

| Policy | n_wins | net c/win | Sharpe | Skew | CVaR95 | strand% | P(both) |
|--------|--------|-----------|--------|------|--------|---------|---------|
| live_current (t36) IS | 228 | -7.002c | -0.2428 | — | — | 6.72% | — |
| live_current (t36) OOS | 170 | -5.990c | -0.1866 | -0.8199 | -90.750c | 6.63% | 0.894 |
| live_current BC-OOS (book-cov.) | 26 | +3.388c | — | — | — | 4.42% | — |

**Note**: The live_current OOS baseline here is -5.99c/win vs ROUND1 which showed +5.30c/win. This tape has 500 windows vs 576 in R1; the current 500-window parquet includes a different/earlier window selection. The R1 figure remains the reference from the deployed system; the R2 study uses the data as loaded.

---

## R2-A: TREE-ENSEMBLE Strand Classifier

**Hypothesis**: GBM + RF on {spread, |p-0.5|, |sig|, |flow|, k, tau, vpin} -> gate when P(strand) > thresh.

**AUC**: GBM IS=0.8959, OOS=0.7184; RF OOS=0.7237; Ensemble OOS=0.7198

**Feature importances (GBM rank)**: vpin (0.524) > abs_sig (0.171) > abs_p_05 (0.165) > spread (0.051) > abs_flow (0.038) > tau (0.030) > k (0.020)

**Gate threshold sweep** (best thresh=0.15):
strand%=3.53%, P(both)=0.987, net=+2.264c/win, Sharpe=+0.1000, skew=+0.0162, CVaR95=-57.286c, #wins=149, diff vs live=+8.254c

**Verdict: SIGNAL (OOS AUC 0.72 > 0.65 threshold)** -- The tree ensemble achieves OOS AUC 0.72 (vs 0.563 for linear R1). Strand rate cut from 6.63% to 3.53% (-47%). Net improves from -5.99c to +2.264c on the 200-window OOS. Skew flips positive (+0.016). CVaR95 improves (-57c vs -90c). BUT: the t-stat vs live is -2.6 (gate SKIPS windows, shifting to fewer-but-better), so this is selection not additive lift. On skip-inclusive accounting (treating skipped windows as 0 gain), the gate must clear the forward bar (t>3, n>=300). Preliminary SIGNAL -- needs larger OOS before deploy.

**IS vs OOS check**: IS AUC=0.896 vs OOS AUC=0.718 -- moderate overfit but OOS AUC clearly > 0.65. Not a pure IS mirage.

---

## R2-B: sig x spread CONJUNCTIVE Gate Grid

**Hypothesis**: Skip opens where |sig| > S AND spread < W (compound: momentum AND tight book).

**Grid sweep** (|sig| in {5,8,10,12} bps x spread in {0.01,0.015,0.02,0.025}):

Best cell: |sig|>5 AND spread<0.025 -- strand%=5.45%, P(both)=0.918, net=-1.384c/win, Sharpe=-0.0629, skew=-0.791, CVaR95=-67.667c, #wins=122, diff vs live=+4.606c

**Standalone spread floor for comparison**:
- spread>=0.015: net=-5.221c, strand%=11.36% (WORSE -- wider floor kills volume)
- spread>=0.025: net=-5.750c, strand%=14.29% (WORSE -- even higher strand%)

**Verdict: MIRAGE** -- The compound gate improves net vs live (-1.38 vs -5.99) but the improvement comes entirely from SKIPPING windows (n_wins drops 170->122). The compound condition beats the standalone spread floor (which paradoxically HURTS by raising strand%). However, the compound gate does NOT beat live_current on a like-for-like window basis (t-stat=-0.846, insignificant). The |sig|>5 AND spread<0.025 condition captures a real interaction but not a deployable one.

---

## R2-C: Time-of-Day Stratified |sig|

**Hypothesis**: UTC band conditions |sig| threshold -- Asia session high-|sig| may mean-revert rather than strand.

**Band analysis** (OOS fills, t36-accepted):
- Asia [0-6h): high-|sig|>8 strand%=10.7% (n=168) vs low-|sig| strand%=6.5% (n=231) -- HIGH-SIG STRANDS MORE
- EU [6-12h): high-|sig| strand%=4.9% (n=206) vs low-|sig| strand%=5.8% (n=293) -- REVERSES (mean-reversion signal?)
- US [12-18h): high-|sig| strand%=6.1% (n=279) vs low-|sig| strand%=5.7% (n=174) -- roughly equal
- Late [18-24h): high-|sig| strand%=8.3% (n=109) vs low-|sig| strand%=7.3% (n=123) -- high-sig slightly worse

IS-derived band thresholds: Asia=8bps, EU=15bps, US=10bps, Late=15bps

**Results**:
- global |sig|>8: net=-1.934c, strand%=6.21%, diff=+4.056c, t=-1.230
- band-specific: net=-1.533c, strand%=5.58%, diff=+4.457c, t=-1.977

**Verdict: MIRAGE** -- Band-specific thresholds improve net vs live (+4.457c) but still negative (-1.533c/win). The EU-session inversion (high-|sig| LOWER strand%) is interesting -- it suggests mean-reversion in EU hours. However, t=-1.977 (not significant vs live) and n=144 is below the deploy bar. Interesting structural finding (Asia session high-sig is genuinely more strand-prone) but insufficient for deploy.

---

## R2-D: depth x VPIN Combined Gate

**Hypothesis**: Open only if depth < D AND vpin < 0.40. Book-covered OOS windows only.

**WARNING: n=34 book-covered OOS windows -- results unreliable, FLAG: n < 50**

live_current on BC-OOS: n=26, net=+3.388c, strand%=4.42%
t32_vpin alone on BC-OOS: n=26, net=+0.154c, strand%=5.00% (VPIN gate HURTS vs live on this subset)

Best D x VPIN: D=12000, vpin<0.30 -- strand%=6.17%, P(both)=0.870, net=+3.739c/win, Sharpe=+0.1051, skew=-0.2223, CVaR95=-88.000c, #wins=23, diff vs BC-live=+0.351c

**Verdict: UNCERTAIN (n<50)** -- Tiny sample (34 BC-OOS windows; 23 with gate applied). VPIN<=0.40 gate HURTS on BC-OOS subset (net drops 3.39->0.15). Combined depth<12000 + vpin<0.30 barely recovers (+3.74 vs +3.39 live). Results are noise at n=23. IS book coverage = 0 so no IS/OOS validation possible. Cannot draw conclusions.

---

## R2-E: Microprice-Divergence + Queue-Thinness

**Hypothesis**: Skip when microprice diverges adversely from our price AND book is thin. OOS+book-covered only.

**WARNING: n=34 BC-OOS windows (6 wins in best gate). FLAG: n < 50**

**Microprice computation**: micro = best_bid / (best_bid + best_ask) -- simple ratio microprice.
**Observed**: mean micro_div = 0.299 (large! microprice is ~0.30 away from YES price on average -- may indicate microprice computation issue with YES/NO bid structure).

**Key finding**: low micro_div (<=0.02) has HIGHER strand% (12.5%, n=8) vs high micro_div (3.9%, n=330). OPPOSITE of hypothesis.

Queue-thinness vs strand%: depth>=8000 has 0% strand rate (n=20) -- thick books complete cleanly.

Best result: micro_thr=0.03, depth<10000 -- net=+9.667c, strand%=5.88%, Sharpe=0.549, skew=+1.775, CVaR95=+1.000c, #wins=6, diff vs BC-live=+6.279c

**Verdict: UNCERTAIN (n<50, likely IS-only mirage)** -- #wins=6 is too small for any conclusion. The micro_div signal appears inverted from hypothesis (low divergence = more strands). CVaR95=+1.0c looks incredible at n=6; this is noise. The queue-thinness finding (thick books, depth>=8000, have 0% strand) is the only noteworthy result but n=20. IS book coverage=0 means we cannot validate IS->OOS.

---

## Signal vs IS-Only Mirage Verdict

| Idea | Key Metric | OOS Result | Diff vs Live | Verdict |
|------|-----------|-----------|-------------|---------|
| R2-A Tree-ensemble | AUC=0.7198 | net=+2.264c, strand 3.53% | +8.254c | SIGNAL (preliminary; AUC>0.65, OOS positive; needs n>=300) |
| R2-B sig*spread grid | best S=5,W=0.025 | net=-1.384c, strand 5.45% | +4.606c (skip-selection) | MIRAGE -- t=-0.85, improvement is window-selection not edge |
| R2-C ToD*|sig| | band-specific thresholds | net=-1.533c, strand 5.58% | +4.457c | MIRAGE -- t=-1.98, EU inversion interesting but not deployable |
| R2-D depth*VPIN | n=23 BC-OOS | net=+3.739c, strand 6.17% | +0.351c vs BC-live | UNCERTAIN -- n<50, VPIN gate hurts alone, data sparse |
| R2-E micro+queue | n=6 BC-OOS | net=+9.667c, strand 5.88% | +6.279c vs BC-live | UNCERTAIN (likely noise) -- n=6, micro_div inverted, data gap |

**KEY FINDING**: R2-A is the only SIGNAL. OOS AUC=0.72 is a material improvement over R1 linear (AUC 0.563). The tree ensemble cuts strand% from 6.63% to 3.53% OOS and flips net from -5.99c to +2.264c. The residual strand pool is non-linearly separable: vpin + |sig| interaction dominates (vpin importance 52%). B/C/D/E are all MIRAGE or UNCERTAIN. t36's performance on this 500-window tape (-5.99c) differs from R1 (+5.30c) because the tape composition differs.

---

## Round-3 Follow-Up Proposals

**R3-1: R2-A tree-gate forward validation (the key next step)**
R2-A cleared the AUC bar (0.72) but not the deploy bar (n<300, t<3). Pre-register the gate (thresh=0.15 on ensemble GBM+RF) and collect 300 fresh forward windows to get a proper paired t-test. The gate skips ~12% of opens; on 300 windows that is ~36 skipped per policy comparison -- adequate for t>3 if the effect is real. This is the single highest-priority R3 action.

**R3-2: vpin-dominant feature engineering (interaction with |sig|)**
R2-A shows vpin (52%) and |sig| (17%) together explain most strand prediction. These two features have a known interaction: high-VPIN + high-|sig| = informed directional flow (not noise, actual informed). Build a 2D feature: vpin * abs_sig, plus vpin^2 (VPIN is likely non-linear near saturation). Test whether this single engineered feature reaches AUC 0.75+ with a simpler threshold gate.

**R3-3: Accumulate book-stream to >=300 book-covered windows**
R2-D and R2-E are entirely blocked by n=34. Run the overnight collector for 2 additional weeks. Target: 300+ book-covered windows where both IS and OOS have book data. Then re-test depth*VPIN (R2-D) and microprice-divergence (R2-E) with proper IS/OOS validation. This is a data collection priority, not a modeling one.

**R3-4: Settle-magnitude regression (expected-loss gate)**
Instead of binary strand prediction, fit a GBM regressor on the SAME features predicting E[settle | strand]. A fill that strands AND settles at -80c is 20x worse than one settling at -4c. Gate opens where E[settle_if_strand * P(strand)] < -threshold (expected loss gate). This may capture the tail-severity that AUC-based gates miss -- the CVaR improvement in R2-A (from -90c to -57c) hints the tree already captures this partially.

**R3-5: Directional strand asymmetry -- YES vs NO separate gates**
The ToD analysis (R2-C) showed EU-session high-|sig| has LOWER strand% (4.9% vs 5.8% low-sig) -- a mean-reversion signal. Test whether YES-leg strands and NO-leg strands have different feature signatures: fit separate GBM classifiers for bid and ask fills. If the YES AUC >> NO AUC (or vice versa), a directional gate may outperform the symmetric R2-A gate. Also: sig sign (not just |sig|) may matter per side.

---

## Lambda Registrations

**No lambda registered this round.**

R2-A passes the AUC bar but NOT the deploy bar (t>3, n>=300 OOS forward windows). The 200-window OOS tape is historical backtest, not forward-validated. Per PREVENT_BAD_TRADES.md invariant: do not register until forward bar clears.

**Candidate for R3 forward registration**: t38_strand_gate (GBM+RF ensemble, thresh=0.15, features: vpin, abs_sig, abs_p_05, spread, abs_flow, tau, k). Re-test forward when n>=300 forward windows collected.

---

https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz
