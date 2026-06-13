# Round 1 — Strand-prevention research results (2026-06-13)

## Data

- **Tape**: 576 windows (BTC 15-min, 45-day fetch), 9,734 fills, 358 strand fills (3.68%)
- **Split**: IS=345 (60%), OOS=231 (40%), time-ordered
- **Strand rate**: IS=3.92%, OOS=3.36%
- **Book stream**: 169 windows with live depth/micro snapshots (OOS-heavy: 1,442/4,172 fills)

## Baselines

| Policy       | IS net/win | IS Sharpe | OOS net/win | OOS Sharpe | OOS skew | OOS CVaR95 |
|-------------|-----------|----------|------------|-----------|---------|-----------|
| P0 (always-pair) | −0.91c | −0.052 | +3.38c | +0.140 | — | — |
| live_current (t36) | +1.56c | +0.040 | +5.30c | +0.120 | +0.037 | −74.4c |

Note: live_current outperforms P0 substantially, confirming t36 guarded-opener is already deployed and working.

---

## Idea 1: Strand Predictor Gate (LogReg)

**Hypothesis**: Fit P(strand | sig, |micro-mid|, spread, |flow|, |p-0.5|, k) → gate opens when P(strand) < threshold.

**IS/OOS metrics** (net c/win vs live_current=+5.30c OOS):

| thresh | IS net/win | IS vol% | OOS net/win | OOS vol% | OOS sr% | diff_OOS |
|--------|-----------|--------|------------|---------|--------|---------|
| 0.10 | −0.36c | 99.7% | +2.90c | 99.6% | 3.37% | −2.40c |
| 0.20 | −0.80c | 99.9% | +3.38c | 100.0% | 3.36% | −1.92c |
| 0.30 | −0.83c | 100.0% | +3.38c | 100.0% | 3.36% | −1.92c |
| 0.60 | −0.91c | 100.0% | +3.38c | 100.0% | 3.36% | −1.92c |

**AUC**: IS=0.589, OOS=0.563 (weak but generalizes)

**Top features** (by |coef|): spread (+0.232), |p-0.5| (+0.213), sig (−0.170), |flow| (−0.167), k (+0.094), |micro-mid| (≈0, book coverage sparse)

**Verdict: MIRAGE** — OOS gate never fires (all thresholds keep 99.9–100% volume), gate too weak to cut meaningful volume. The LogReg P(strand) range is compressed (fills poorly separated). AUC 0.563 OOS is near-random. Key diagnosis: at 3.36% OOS strand rate, even a moderate predictor needs a very tight threshold to reduce strand-prone opens materially; none tested succeeded.

**Net vs live**: best OOS = +3.38c/win, diff = **−1.92c** vs live_current.

---

## Idea 2: A-S Quote Skew vs t36 Binary

**Hypothesis**: Continuous Avellaneda-Stoikov skew (spread floor = 0.01 + skew_factor × P(strand)) vs t36 binary spread floor.

| skf | IS net/win | IS sr% | OOS net/win | OOS sr% | diff_OOS |
|----|-----------|-------|------------|--------|---------|
| 0.00 | −0.36c | 3.54% | +2.98c | 3.35% | −2.31c |
| 0.02 | −0.26c | 6.33% | −0.12c | 7.06% | −5.42c |
| 0.05 | −0.21c | 6.43% | −0.05c | 7.16% | −5.35c |
| 0.10 | −0.23c | 5.99% | −0.04c | 7.59% | −5.33c |
| 0.20 | −0.46c | 9.09% | −0.36c | 9.24% | −5.66c |

**Verdict: MIRAGE** — The continuous skew inflates the spread floor above what fills arrive at, collapsing volume with no PnL improvement. The binary t36 outperforms every continuous skew variant by 2–5c/win OOS. The LogReg strand score adds no discriminating power above the simple 1c spread floor already deployed. Strand rates paradoxically *increase* with skf (the stranded subset is harder to gate because it arrives at wide spreads too).

**Net vs live**: best is skf=0.00 (= no skew) at +2.98c OOS, diff = **−2.31c** vs live.

---

## Idea 3: Spot-Momentum Filter (|sig| threshold)

**Hypothesis**: Refuse opens when |sig| (3-min spot move bps, signed adverse) exceeds threshold.

| |sig|≤ | IS net/win | IS sr% | OOS net/win | OOS sr% | diff_vs_live |
|--------|-----------|-------|------------|--------|------------|
| 3 bps | +0.01c | 3.74% | +1.04c | 3.88% | −4.26c |
| 5 bps | −0.37c | 3.83% | +2.52c | 3.55% | −2.78c |
| 8 bps | −0.60c | 3.85% | +2.73c | 3.35% | −2.56c |
| 12 bps | −0.93c | 3.99% | +2.70c | 3.36% | −2.60c |
| 15 bps | −0.81c | 3.92% | +3.35c | 3.31% | −1.95c |

**Verdict: MIRAGE** — OOS net improves monotonically toward `no gate` (15bps = almost P0), but never beats live_current. The 3-min |sig| filter cuts fills that are actually P0-positive on OOS. Key: t36 already embeds a sig>8bps gate for thin-spread opens; standalone |sig| adds nothing above t36. The OOS strand-rate drop is tiny (3.36%→3.31% at best). IS is consistently worse than OOS (normal: IS includes the harder high-vol windows).

**Net vs live**: best OOS = +3.35c/win, diff = **−1.95c**.

---

## Idea 4: Microprice-Divergence Gate

**Coverage issue**: IS book snapshots had 0/5,562 fills with micro_vs_mid (snapshots from the overnight_data only covered OOS windows). Fell back to spread-floor proxy.

**Spread-floor proxy results** (skip if spread < threshold):

| spread≥ | IS net/win | OOS net/win | diff_vs_live |
|--------|-----------|------------|------------|
| 0.005 | −0.49c | +3.15c | −2.15c |
| 0.010 | −0.36c | +2.98c | −2.31c |
| 0.015 | −0.29c | −0.15c | −5.45c |
| 0.020 | −0.30c | −0.17c | −5.47c |
| 0.025 | −0.19c | +0.11c | −5.19c |

**Verdict: MIRAGE** — Micro-divergence can't be properly tested without IS book snapshots. Spread proxy confirms that the t36 1c floor (0.01) already captures the useful spread signal; anything tighter chops OOS volume catastrophically. The full microprice test needs continuous book collection across the IS date range.

**Net vs live**: best proxy OOS = +3.15c/win, diff = **−2.15c**.

---

## Idea 5: Queue-Thinness Entry

**Coverage issue**: Depth from book stream was 0/5,562 IS fills, 1,442/4,172 OOS fills. Used |flow| as queue-pressure proxy.

| |flow|< | IS P(both) | IS net/win | OOS P(both) | OOS net/win | diff_vs_live |
|--------|-----------|-----------|------------|------------|------------|
| 50 | 0.983 | −1.16c | 0.970 | −0.61c | −5.91c |
| 200 | 0.983 | −1.11c | 0.970 | −0.53c | −5.83c |
| 800 | 0.983 | −1.16c | 0.970 | −0.87c | −6.17c |

**Verdict: MIRAGE** — Low-|flow| gate consistently selects the WORST windows (negative net vs even P0). The low-flow filter selects quiet windows where the bid-ask is also thin and price is less favorable. Correctly implemented depth-thinness (via bilateral displayed size) could not be tested on IS; this needs extended book collection.

**Net vs live**: best OOS = −0.53c/win, diff = **−5.83c**.

---

## Signal vs Mirage Summary

| Idea | IS verdict | OOS verdict | Best OOS diff vs live | Status |
|------|-----------|------------|----------------------|--------|
| 1. Strand LogReg gate | IS barely better than P0 | OOS = P0 (no gate fires) | −1.92c | **MIRAGE** |
| 2. A-S continuous skew | IS collapses | OOS collapses | −2.31c to −5.66c | **MIRAGE** |
| 3. |sig| momentum filter | IS < P0 uniformly | OOS best near P0, below live | −1.95c | **MIRAGE** |
| 4. Micro-divergence gate | IS N/A (no coverage) | OOS spread-proxy < live | −2.15c | **DATA GAP** |
| 5. Queue-thinness entry | IS negative | OOS deeply negative | −5.83c | **MIRAGE** |

**Key finding**: live_current (t36) at +5.30c/win OOS is a strong gate. All five Round-1 ideas underperform it. The single most important structural observation:

> **The 3.36% OOS strand rate on this tape is already LOW** (was 13.6% on the 323-window historical tape where −4,413¢ strand losses were documented). The t36 guarded opener has already cut most strand exposure. The remaining strand fills arrive in windows where decision-time signals are weakly separating — which is why a LogReg achieves only AUC 0.563 OOS.

---

## Most Promising Lever Found

**Spread × Price interaction (non-linear)**: The LogReg shows spread and |p-0.5| as the top-two strand predictors, but linearly they explain little variance. The t36 already uses a hard spread floor. The untested lever is a **non-linear interaction model** (GBM/XGBoost) that can capture "mid-price + wide-spread = safe" vs "mid-price + tight-spread = toxic" regimes. This is **R2-A** below, grounded in the AUC-0.563 signal that IS generalizing but linear boundary is insufficient.

---

## 5 Round-2 Follow-Up Proposals

### R2-A: Tree Ensemble Strand Classifier (t38)
Fit GradientBoostingClassifier on {spread, |p-0.5|, sig, |flow|, k, tau, vpin} (IS only).
Hypothesis: non-linear interactions (e.g., tight-spread × mid-price = strand risk) can lift AUC from 0.563 to 0.65+.
Target: OOS AUC>0.65 AND strand-rate cut >30% at 80% volume retained → distill to frozen logistic, register as t38_strand_gate with T_BAR=3.0, MIN_WINDOWS=300.
Feasibility: 218 IS strand events is borderline for GBM; use 5-fold cross-val on IS to avoid overfit signal.

### R2-B: Sig × Spread Conjunctive Gate
t36 already gates: YES side when spread<0.02 OR (sig>8 AND spread<0.02).
New: sweep **joint conditions** across 4×4 grid: |sig|∈{5,8,10,12}bps × spread∈{0.01,0.015,0.02,0.025}.
Apply gate: skip open when |sig|>sig_thr AND spread<sprd_thr (regardless of side).
Hypothesis: the compound condition (momentum + tightness) is the true strand-predictor; each alone is too blunt.
Expected: recover some of the IS/OOS gap by being specific about when both signals fire.

### R2-C: Time-of-Day Stratified |sig| Gate
Stratify OOS windows into 4 UTC hour-bands (00-06, 06-12, 12-18, 18-24).
For each band: compute median |sig| and strand rate vs |sig| quintile.
If the high-|sig| band has >2× strand rate vs low-|sig| band within a session, register a session-aware gate.
Hypothesis: Asia thin sessions structurally have higher |sig| but NOT higher strand rates (mean-reversion); EU/NY open has momentum → strand causation. A session-aware gate avoids blocking profitable Asia fills.

### R2-D: Depth × VPIN Combined Filter
Round 1 found book-depth data only partially available (IS coverage = 0). 
Action: extend overnight_data collection to cover IS date range (books go back to gha-data 2026-06-10).
Once IS depth is populated: test depth<D AND VPIN<0.40 combined gate vs t32_vpin_open_gate alone.
Hypothesis: bilateral book thinness (fast pairing) + low VPIN (non-toxic flow) jointly predict P(both fill)≥0.98, the completion ceiling. Cross-reference with box_policy_ab.completion_score (which already uses depth and flow but not jointly with VPIN).

### R2-E: Full Book Coverage & Re-run Round 1
The core data limitation in Round 1: IS windows (ws < 1782014100 ≈ 2026-06-08) have no book snapshots.
The gha-data branch goes back to 2026-06-10 and has 278 book files; the oldest IS windows fall in the 45-day window (starting ~2026-04-29) before collection began.
Action: collect hist+trades for last 14 days (deeper overlap with book data), re-run Round 1 Ideas 4 and 5 with IS book coverage.
Expected: micro-divergence and depth gates will show real IS/OOS behavior only when both sets have coverage.

---

## Lambdas Worth Registering Now

**None from Round 1 clear the deploy bar** (all underperform live_current OOS). However:

- **t36 is confirmed effective** on this newer 576-window tape (OOS +5.30c/win vs P0 +3.38c/win). The gap confirms the guarded opener is earning its keep.
- The best standalone idea (R2-B's sig×spread conjunctive gate) is architecturally already in t36; adding more conditions would make it t36+. Recommend R2-B as the next backtest before any registration.
- **Watch for**: R2-A (tree ensemble) generating a distillable logistic with OOS AUC>0.65 — that would be the first genuinely new frozen model since tox_p.
