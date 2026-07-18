# FUNDING / BASIS / OI DIRECTIONAL SIGNAL vs POLYMARKET WEEKLY LONGSHOTS

_As-of 2026-07-18. Binance USD-M futures microstructure -> weekly BTC & ETH direction, out-of-sample, and vs the Polymarket price on settled weeklies._

## TL;DR verdict

**NULL — no stackable directional edge; it is already priced.** Across 11 Binance microstructure features, the walk-forward classification AUC on weekly BTC/ETH direction looks strong (0.66) but is a REGIME-AUTOCORRELATION ILLUSION (it survives — AUC 0.56 — even when returns are rolled 26 weeks out of alignment). The leak-robust economic test is null: signing positions by the combined signal earns +0.0015/wk at week-clustered t = **+0.40**, BELOW passive long (+0.0046/wk); combined linear OOS R2 vs drift is -0.113 (negative). The Polymarket residual test is data-limited (only 5 independent settled-weekly week-clusters) and inconclusive/leaning-null. Funding/basis/OI are public and efficiently priced — the harvestable edge remains the short-vol/longshot risk premium, not a direction signal.

## Data / panel

- Weekly non-overlapping panel: **576 rows** (288 distinct weeks x 2 assets), 2021-01-04 -> 2026-07-06.

- Features (11): `funding_lvl, funding_trend, basis, basis_trend, oi_chg, oi_z, lsr_glob, lsr_top, lsr_chg, taker, mom`.

- Target returns are strictly non-overlapping weekly (Mon->Mon) close-to-close; every feature uses only data up to the Monday-00:00 entry. Expanding-window walk-forward, standardisation on train stats only, pooled BTC+ETH, clustered by week.

## PART 1 -- Pure OOS prediction on Binance data

### The HONEST headline: economic (tradeable) test

A high classification AUC on weekly direction is easy to manufacture from **regime autocorrelation** (level features like funding/OI/LSR are high in bull regimes, and bull regimes have more up-weeks). The question that matters for a *stackable edge* is whether SIGNING positions by the combined signal actually earns out-of-sample, week-clustered, and beats simply being passively long (beta).

| walk-forward variant | OOS AUC | signal L/S mean/wk | **L/S week-clustered t** | always-long mean/wk (t) |
|---|---|---|---|---|
| **REAL** | 0.657 | +0.0015 | **+0.40** | +0.0046 (+1.00) |
| autocorr placebo (returns rolled 26w) | 0.560 | -0.0012 | -0.30 | -- |
| shuffle placebo (labels permuted) | 0.493 | -0.0076 | -1.90 | -- |

- **The combined signal's directional L/S earns +0.0015/week at week-clustered t = +0.40** — statistically indistinguishable from zero, and *below* the passive always-long return (+0.0046/wk). The AUC of 0.657 does NOT translate into tradeable directional profit.

- **Autocorrelation placebo (returns rolled 26 weeks, breaking true alignment but preserving regime autocorrelation) still shows AUC = 0.560** — proof that the AUC>0.5 is a regime-autocorrelation artifact, not genuine predictive information. Week-clustering removes the BTC/ETH cross-sectional correlation but NOT the serial regime persistence; the economic L/S t (which is null) is the honest metric.

- **Shuffle placebo (labels fully permuted): AUC = 0.493, L/S t = -1.90** — confirms the pipeline is leak-free (shuffled labels give ~coin-flip / negative skill).

- **Continuous target:** combined linear OOS R2 vs drift baseline = **-0.1130** (n=456) — negative, i.e. the features predict the weekly return *worse* than just guessing the historical mean.

### Descriptive classification stats (AUC / clustered directional-skill t) -- INFLATED, shown for transparency

These are the raw walk-forward classification numbers. They look strong, but per the placebos above they are inflated by regime autocorrelation and do NOT survive the economic test. The directional-skill t is week-clustered but NOT robust to serial regime persistence.

**Target `direction`** (n_oos=456, base rate 0.491); combined AUC 0.657:

| feature | OOS AUC | skill t (inflated) | #weeks |
|---|---|---|---|
| funding_trend | 0.694 | +4.28 | 228 |
| basis_trend | 0.674 | +4.18 | 228 |
| funding_lvl | 0.719 | +4.14 | 228 |
| oi_z | 0.690 | +4.07 | 228 |
| mom | 0.674 | +3.87 | 228 |
| lsr_glob | 0.677 | +3.85 | 228 |
| lsr_chg | 0.666 | +3.61 | 228 |
| oi_chg | 0.682 | +3.48 | 228 |
| taker | 0.665 | +3.41 | 228 |
| lsr_top | 0.644 | +3.22 | 228 |
| basis | 0.617 | +1.93 | 228 |

**Target `up_longshot_5pct`** (n_oos=456, base rate 0.282); combined AUC 0.590:

| feature | OOS AUC | skill t (inflated) | #weeks |
|---|---|---|---|
| lsr_glob | 0.639 | +4.04 | 228 |
| taker | 0.623 | +3.46 | 228 |
| oi_chg | 0.641 | +3.35 | 228 |
| lsr_chg | 0.631 | +2.59 | 228 |
| lsr_top | 0.591 | +2.54 | 228 |
| oi_z | 0.631 | +2.43 | 228 |
| funding_lvl | 0.661 | +2.37 | 228 |
| funding_trend | 0.623 | +2.11 | 228 |
| mom | 0.646 | +2.10 | 228 |
| basis_trend | 0.615 | +1.20 | 228 |
| basis | 0.577 | +1.04 | 228 |

## PART 2 -- Does the signal add info over the Polymarket price?

- Settled weekly strike-markets matched: **594** across **27** resolution dates but only **5 iso-week clusters** (2026-06-21 -> 2026-07-17).

- **DATA-LIMITATION CAVEAT (important):** Only settled 7-day 'above' ladders from a ~4-week window were recoverable via the Polymarket API; they resolve DAILY (overlapping 7-day windows) so residual observations are highly autocorrelated, and there are only 5 iso-week clusters. The residual regression is UNDERPOWERED and its t-stats are NOT credible; also the ladder is near-money (mean price ~0.5), not the 0.15-0.30 longshot band.

- Polymarket calibration on this set: mean YES price **0.498** vs realized YES rate **0.510** — near-money and well calibrated (no gross mispricing for a directional signal to exploit).

- Regression of residual `(outcome - pm_price)` on each standardised Binance signal known at entry. Week-clustered t (k iso-weeks) is the honest one; date-clustered t shown too, but overlapping 7-day windows inflate both.

| feature | slope | naive t | wk-clustered t (k wks) | date-clustered t |
|---|---|---|---|---|
| oi_chg | +0.0343 | +4.03 | +2.71 (k=5) | +2.28 |
| funding_trend | -0.0139 | -1.61 | -2.32 (k=5) | -1.08 |
| taker | -0.0257 | -3.00 | -1.85 (k=5) | -1.80 |
| lsr_chg | -0.0067 | -0.78 | -0.56 (k=5) | -0.44 |
| basis | -0.0123 | -1.43 | -0.33 (k=5) | -1.81 |
| lsr_top | +0.0049 | +0.57 | -0.21 (k=5) | +0.72 |
| funding_lvl | +0.0046 | +0.53 | -0.14 (k=5) | +0.49 |
| lsr_glob | +0.0105 | +1.21 | +0.08 (k=5) | +0.75 |
| oi_z | +0.0042 | +0.49 | -0.01 (k=5) | +0.84 |
| basis_trend | -0.0157 | -1.82 | +0.00 (k=5) | -1.08 |

- With only **5 independent week-clusters** and ~10 features tested, any single |t|~2-3 here is expected noise and would not clear the Bonferroni bar. **Part 2 is treated as inconclusive / data-limited, leaning null.**

## Multiple-testing accounting

- Classification targets: **2** (`direction`, `up_longshot_5pct`); features: **11**; univariate classification tests = **22**.

- Plus 2 combined-model tests + 1 continuous R2 + 1 combined economic L/S test + 10 Part-2 residual regressions. Total distinct specs tried ~ **36** (the primary gate is the single combined economic L/S test; the per-feature tables are descriptive).

- Bonferroni 5% threshold ~ p<0.0020, i.e. |t| ~ **3.09**. A single |t|~2 among dozens of tests is expected under the null.

## VERDICT (blunt)

- **NO stackable directional edge. It is already priced.** The Binance microstructure features (funding, basis, OI change, long/short ratio, taker imbalance) produce a high-looking OOS classification AUC, but that AUC is a **regime-autocorrelation illusion**: it survives even when returns are rolled 26 weeks out of alignment. The tradeable test is null — signing positions by the combined signal earns +0.0015/week at week-clustered t = +0.40 (below passive long +0.0046/wk), and the combined linear OOS R2 vs drift is -0.1130 (negative). The Polymarket residual test is data-limited (only 5 independent week-clusters of settled 7-day ladders recoverable, overlapping windows, near-money not longshot) and is treated as inconclusive/leaning-null, not a positive. Funding/basis/OI are public and efficiently priced into both the underlying and Polymarket. The STACKING hypothesis fails: the harvestable edge is the short-vol / longshot risk premium (bearing tail risk), NOT a microstructure DIRECTION signal.


- Honest tradeable metric: combined-signal OOS L/S = **+0.0015/wk, week-clustered t = +0.40** (vs passive-long +0.0046/wk).

- OOS combined AUC on `direction` = **0.657**, but autocorr-placebo AUC (rolled 26w) = **0.560** -> the AUC is an artifact.

- Combined linear OOS R2 vs drift = **-0.1130** (negative).

- Part 2: 594 settled weeklies / 5 weeks; features passing Bonferroni on the residual test: **none**.
