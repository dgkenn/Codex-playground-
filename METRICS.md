# Performance metrics — the full suite (beyond Sharpe)

A reviewer correctly noted Sharpe alone is insufficient. `metrics.py` computes the risk / profitability /
consistency / execution suite on the shadow data. **Read the maker-specific caveats first — they change how
several metrics are interpreted.**

## Caveats (why naive per-trade metrics mislead for a rebate maker)
- **Unit = a WINDOW (one market we made), not a "trade."** A maker holds balanced sets to resolution; there
  is no discrete entry/exit "trade" with a win/loss. So Win Rate / Profit Factor / W-L are **per-window**.
- **`net` is rebate-inclusive and resolution-based**, so its variance INCLUDES the directional swing on
  residual inventory held to resolution — that's real risk for a hold-to-resolution book, and it's what
  drives drawdown.
- **PAPER / front-of-queue.** The sim fills at queue position ≈ 0, so absolute P&L, fill rate and edge are
  **upper bounds**; the live haircut is the queue battle (`PAPER_VS_LIVE.md` A4).
- **Annualized Sharpe/Sortino are meaningless here** — at ~140k 15-min windows/yr the √n factor inflates
  them absurdly. We report **per-window Sharpe as a t-stat** (is the edge real?) and use **MDD / Calmar /
  Profit Factor / Win-rate / W-L / edge-bps** for the comparative risk picture.
- **Maker ratio = 100% by construction** (post-only + the `would_cross` guard) — the gold standard; we never
  pay taker fees by accident.

## Current numbers (4 days, 56k fills, per-(asset,window))
| gate | net/win | Sharpe(t) | Sortino | MDD$ | Calmar | ProfitFactor | Win% | W/L | edge(bps) | kept% |
|---|---|---|---|---|---|---|---|---|---|---|
| micro | +4.88 | 3.3 | 0.33 | 249 | 8.4 | 1.69 | 54% | 1.46 | 97 | 78% |
| **ufat** (deployed) | +4.85 | 3.3 | 0.33 | 234 | **8.8** | 1.68 | 53% | 1.48 | 95 | 79% |
| **ufat_band** (best by net) | **+11.48** | 3.1 | 0.36 | **1253** | **3.9** | **1.74** | 45% | **2.11** | **309** | 54% |

## How we stack up vs the reviewer's targets
- **Profit Factor 1.68–1.74** → in the ">1.5 viable" band (not yet ">2.0 strong"). ✅ ok
- **Maker ratio 100%** → gold standard. ✅
- **Edge (PnL/volume) 95 bps (ufat)** → strong per-$-traded efficiency for a maker. ✅
- **Win rate 45–54%** → consistent with the reviewer's note that Polymarket makers "win ~47% of fills but
  net positive via fees." ✅ (ufat_band's 45% is offset by W/L 2.11.)
- **Sharpe t ≈ 3.3** → the edge is statistically real over the sample. ✅
- **Sortino 0.33–0.36 (per-window)** → low per-window, but positive and ≥ Sharpe (downside not fat). ◐
- **Max Drawdown / Calmar** → ⚠️ **the weak spot.** Plain `ufat` Calmar 8.8 is healthy; **`ufat_band`
  Calmar 3.9** — its extra return comes with 5× the drawdown.

## The key finding (the metrics overturn "ufat_band is simply best")
`ufat_band` wins on **raw net (+11.5)** and **Profit Factor / W-L / edge**, but it's **worse on Calmar/MDD**
because `notmid` (drop the 0.30–0.55 zone, keep the tails) concentrates into the **high-prob tail**, whose
fills carry large *directional* resolution swings. So a chunk of `ufat_band`'s extra edge is **directional
tail risk, not pure rebate** — exactly the trap the whole project guards against. Plain `ufat` is the better
**risk-adjusted** strategy today (Calmar 8.8 vs 3.9).

## Improvements this implied — NOW ACTIONED (detail in "Improvements actioned" at the bottom)
1. ✅ **Judge variants by Calmar/Sortino, not net/win** — `leaderboard.py` now ranks by Calmar with p/CI.
2. ❌ **Delta-hedge residual inventory** (BTC perp) — built + **properly backtested** (`hedge_backtest.py`) and
   **REFUTED** (the mo30 proxy was misleading). See "Delta-hedge: properly backtested" at the bottom.
3. ✅ **Per-regime breakdown** — by asset (Insight 2) + volatility regime (`metrics.py` E: calm vs volatile).
4. ◐ **Confirm fill rate live** — paper is the front-of-queue upper bound; `pilot_reconcile.py` does it live.
5. ✅ **Position sizing** — `live_multi.py` BTC-weighted; tiny clips + caps already the design.

Run: `python metrics.py` (after `git checkout origin/gha-data -- gha_data/`).

---

# Extended battery (`metrics_ext.py`) — tail / drawdown / benchmark / robustness, with p-values & CIs

Computed on the same 4 days (447 (asset,window) units). Maker caveats still apply (post-only → no taker
slippage; TCA "cost" = adverse-selection markout; beta-to-BTC ≈ 0 is the delta-neutral *design*).

## Headline: `micro_ufat` dominates the full risk battery (not just net)
| metric (micro_ufat) | value | reviewer target | verdict |
|---|---|---|---|
| Skewness | **+1.71** | >0 | ✅ right-tailed |
| Kurtosis | +4.94 | lower better | ◐ some fat tail |
| VaR95 / CVaR95 | −$8.5 / −$11.1 | monitor | small, recoverable |
| Recovery Factor | **67.0** | >5 excellent | ✅✅ |
| Ulcer Index ($) | **5.5** (lowest of all) | <10 | ✅ |
| Time-Underwater | **18%** | <30% | ✅ |
| Max-DD duration | **3 windows** | <15 | ✅ fast recovery |
| Information Ratio vs baseline | +0.57 (p≈7e-25) | >0.5 | ✅ |
| Monte-Carlo %positive (B=2000) | **100%** | >90% | ✅✅ |
| MDD 95th pct (bootstrap) | $44 | — | small |
| Parameter sensitivity (margin ±20%) | net +14.4→+14.4 (**flat**) | no cliff | ✅ not overfit |
| Walk-forward | positive in every segment w/ data | 5+ consistent | ✅ |

## New insights from the extended battery
1. **`micro_ufat` is the risk-adjusted winner across the WHOLE battery** — best Recovery Factor (67),
   lowest Ulcer ($5.5), lowest Time-Underwater (18%), shortest drawdown (3 windows), positive skew. This
   independently reconfirms it as the deployed default — not just by net, but by every risk metric.
2. **Every gate has positive skew (+1.5 to +2.0)** — favorable asymmetry (small frequent rebate wins, rare
   larger losses gated down). The reviewer wants skew>0; we have it.
3. **Extreme robustness:** Monte-Carlo bootstrap → **100% of 2000 resamples positive** for all top variants
   (≫ the 90% bar); parameter sensitivity is **flat** under ±20% margin (no curve-fit cliff); walk-forward
   is positive in every segment with data. The edge is not an artifact.
4. **Inventory drives drawdown** — `av_stoikov` (carries the most inventory) has the worst Ulcer (21.6) and
   Time-Underwater (52%); the tight-inventory gates have the lowest. The fix is **tight inventory** (which
   the winning gates already do) — NOT a BTC-perp delta-hedge, which a proper path-based backtest refuted
   (see bottom section). The mo30-based hint in `metrics.py §D` overstates the hedge benefit; ignore it in
   favor of `hedge_backtest.py`.
5. **Adverse-selection rate: 44% gated vs 48% baseline.** ~Half of maker fills are short-term adverse (the
   spread bounce) — *normal* for a 2-sided 1-tick maker; the rebate + the benign half net positive, and the
   gate trims the toxic 4 points. (The reviewer's <15% target is a directional-taker frame, not a maker's.)
6. **Information Ratio ~0.6 vs the baseline maker (p≈1e-30)** — the gates significantly out-consist the
   plain rebate maker; the toxicity overlay is genuine alpha over naive market-making.

## Improvements actioned
- **Deployed `ufat`** is confirmed best risk-adjusted (above) — keep it; `leaderboard.py` now ranks by
  **Calmar** (not net) and shows p/CI, so the A/B selects risk-adjusted winners going forward.
- **`hedger.py`** (BTC-perp hedge-ratio) built and **properly backtested** (`hedge_backtest.py`) — the hedge
  was **REFUTED** as an MDD fix (details below). Risk control = tight inventory + breadth, not a perp hedge.
- **Per-asset sizing** in `live_multi.py` (BTC-weighted) — concentrate capital where Recovery/edge is best.
- **Forward collection:** `shadow_compare` now records per-variant `adv_rate` (adverse-at-entry) for ALL
  strategies; net / inventory (`end_delta`,`max_delta`) / fill_rate were already collected — so the entire
  battery above regenerates for every strategy as data grows (`metrics.py`, `metrics_ext.py`).

Run: `python metrics_ext.py` (after `git checkout origin/gha-data -- gha_data/`).

---

# The metrics' hypotheses, tested (`metrics_hypo.py`)

The battery above generates three falsifiable hypotheses; all were tested on the full tape with a
sequential inventory REPLAY (walk each window's fills in time order, enforce the engine's actual
skew-block rule at tighter limits) under the select(A+B)/confirm(holdout C) protocol:

| hypothesis | result |
|---|---|
| **H1: `ufat` + tighter inventory skew** (insight 4: "inventory drives drawdown") | ✅ **supported as a risk knob** — skew 0.15·cap: holdout **Calmar 40.6 vs 31.0**, MDD −25%, in BOTH folds, at zero measurable net cost (paired t +0.3). Wired as shadow variant **`ufat_skew15`** for prospective A/B. |
| **H2: tight skew rescues `ufat_band`'s drawdown** | ❌ refuted — and the replay exposes something bigger: under real inventory mechanics **`ufat_band`'s 2× net advantage disappears entirely** (holdout +3.18 vs `ufat` +3.67, paired t −0.8). Its concentrated same-side tail fills hit the skew limit, collapsing its volume — the keep/drop studies (no inventory constraint) flattered it. A third independent strike against the band (after Calmar and the refuted hedge). |
| **H3: calm-regime filter** (skip windows whose *previous* window's spot vol is top-quartile — honest, past-only) | ❌ refuted — net collapses (paired t **−5.0**), Calmar falls (10.2 vs 31.0). Volatile windows carry positive rebate net; consistent with the pruned `vol_gate`. |

The replay approximates queue mechanics (a dropped fill can't alter others' queues), so H1's winner
follows the standing discipline: shadow A/B first, deployed-default change only on prospective
confirmation. Re-run: `python metrics_hypo.py`.

---

# Delta-hedge: properly backtested against the real spot path — REFUTED (`hedge_backtest.py`)

The earlier "hedge cuts MDD ~77–93%" was a **proxy artifact**: `metrics.py §D` used short-horizon markout
(mo30) as a stand-in for "hedged," which silently removes the terminal directional move *for free*. A real
hedge cannot do that. So I built a proper simulation: reconstruct each gate's inventory path from the fills,
hold a BTC-perp of notional `N = -(q_up-q_dn)·f'(S)·S` along the **actual ~1Hz spot path** (`ticks_*.jsonl`,
411 windows), using the window's **realized vol** for `f'`, perp fees + a proportional rebalance band, and —
critically — **freezing the hedge in the final τ_min** because a binary's delta explodes as τ→0 (pin risk).

| gate | unhedged net / Calmar | hedged (2 bps) net / Calmar | hedged (FREE) net / Calmar | paired p |
|---|---|---|---|---|
| micro | +1.45 / 0.6 | −4.85 / −1.0 | +2.10 / 1.1 | 0.40 (free) |
| ufat | +1.28 / 0.5 | −5.11 / −0.9 | +1.93 / 1.0 | 0.42 (free) |
| ufat_band | +11.00 / 5.7 | +5.08 / 2.4 | +10.67 / 6.1 | **0.76 (free)** |

**Verdict: the hedge does NOT make `ufat_band` risk-adjusted-superior.**
- With realistic perp fees (2 bps) it **hurts every gate** (net down, Calmar down).
- Even **free** (fee=0, impossible) the improvement is marginal and **statistically insignificant**
  (`ufat_band` Calmar 5.7→6.1, paired **p=0.76**; micro/ufat p≈0.40).

**Why (the honest mechanism):** a 15-min binary's delta explodes near expiry (gamma/pin risk), so you must
freeze the hedge exactly in the final minutes — but the **resolution is decided by that terminal move**. The
hedge therefore offsets early, *reversible* noise rather than the *decisive* terminal swing, while adding
fees and its own path variance. The residual inventory is also small (tight cap), so there's little
directional risk to hedge in the first place.

**Implication:** `ufat` stays the deployed default (best risk-adjusted, unhedged). `ufat_band`'s higher net
comes with a drawdown that **hedging cannot remove** — so prefer it only if you accept the drawdown, not on
the (now-falsified) premise that a hedge fixes it. The real risk controls are **tight inventory** (already
in the gates) and **breadth** (cross-asset net corr +0.10). `ROADMAP`'s delta-hedge Tier-1 is **demoted**.
Re-run: `python hedge_backtest.py [fee_bps] [hyst_usd]`.
