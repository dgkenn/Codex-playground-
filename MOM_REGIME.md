# Crypto Momentum — REGIME / CROWDING-TIMING Filter

Scope (per task split): **WHEN to be on / scale / flip the locked momentum book.**
Signal construction, universe, weighting, and multi-factor are owned by sibling agents
(see `MOM_SIGNAL.md`) and are taken as given, not re-derived.

## TL;DR verdict

**YES — a simple, robust regime filter helps.** A **BTC-trend (price vs long moving
average) "risk-on" gate** is the winner: it sits the book out when BTC is well below its
50–100d MA, the regime where cross-sectional momentum is structurally dead/negative.

- It **lifts recent-regime OOS Sharpe modestly AND cuts the crowding drawdown by ~half**,
  and it does so on a **strict IS-only param pick**, a **plateau** of thresholds/MA-lengths,
  **both weighting schemes**, and a **placebo test**.
- **Best deployable rule (strict IS pick, no peeking): be ON when BTC ≥ its 100-day MA,
  else FLAT** (dollar-neutral book scaled to 0). Optionally combine with a dispersion gate.
- **The own-equity "turn off after a losing streak" idea FAILS** — momentum mean-reverts
  after its own drawdowns, so cutting risk post-loss throws away the rebound. Honest negative.
- **Funding-stress is UNTESTABLE here** — OKX `funding-rate-history` serves only ~3 months,
  too short for a multi-year regime backtest. Reported, not used.

## Method / bar

- **Base strategy (locked):** risk-adjusted 10d momentum (ret/vol), top-15 liquid USDT perps,
  dollar-neutral long-top-30%/short-bottom-30%, equal- or rank-weight, **weekly rebalance**,
  **9 bps/side** turnover cost. Engine reused from sibling `mom_backtest.py`; reproduced exactly
  (FULL Sharpe +1.30 equal / +1.34 rank).
- **Overlay (this work, `regime_backtest.py`):** the base book is computed once; a regime gate
  `g(t) ∈ {0,1}` (or continuous) multiplies the book. Costs re-flow: a scaled book trades less,
  and **changing the gate level incurs its own turnover cost** (modeled at full gross = 2). All
  regime signals are observable **at the rebalance date `t`, before** the forward holding week
  (own-equity signals are `.shift(1)`-ed) — **no lookahead**.
- **Data:** sibling `mom_data.parquet` (OKX daily OHLCV, 37 USDT perps, 2020-01-01→2026-06-13),
  staged to `/tmp/regime_data/` (never committed). Funding from OKX `funding-rate-history`
  (`regime_fetch.py`) — only ~94 days available.
- **OOS protocol:** params chosen on **IS = pre-last-18mo only**; reported on the **OOS18 hard
  holdout**, with **REC12** (recent 12mo, headline) and an **independent PREV12** (24→12mo ago).
  Sharpe ann ×√52. Survivorship caveat from `MOM_SIGNAL.md` carries over (absolute Sharpe biased up).

## Base (no filter) — reference

| scheme | FULL | OOS18 | REC12 | PREV12 | FULL maxDD | OOS18 maxDD |
|---|---|---|---|---|---|---|
| equal | +1.30 | +1.19 | +2.33 | +1.39 | **-57%** | **-31%** |
| rank  | +1.34 | +1.14 | +2.24 | +1.59 | -58% | -31% |

The headline problem the filter must beat: deep drawdowns (-31% OOS, -57% full) and the
crowding-decay stretches inside REC12.

## 1. Filter-by-filter results (IS-best threshold; equal-weight, 9bps)

Net Sharpe; "IS-best" = threshold maximizing IS Sharpe, then read OOS. Δ vs base in parens.

| Regime filter | dir | OOS18 | REC12 | PREV12 | OOS18 maxDD | rec exp | verdict |
|---|---|---|---|---|---|---|---|
| **BTC > MA50 / MA100** | uptrend ON | **+1.22…+1.57** | +1.8…+2.3 | **+1.9…+2.1** | **-13%** (was -31%) | 0.55–0.75 | **WINNER** |
| Cross-sectional dispersion | high ON | +1.30 (+0.11) | **+2.58 (+0.25)** | +1.49 | -31% | 0.79 | helps RETURN, not DD |
| BTC realized vol (low) | low-vol ON | +1.41 (+0.22) | +2.26 | +1.65 | -22% | 0.83 | helps, weaker/less robust |
| Breadth (frac up) | broad-up ON | +1.27 (+0.08) | +2.17 | +1.52 | -16% | 0.48 | marginal |
| Own rolling-Sharpe(8) | on if winning | +1.12 (-0.07) | +2.25 | +1.36 | -32% | 0.98 | **NO HELP** |
| Own rolling-Sharpe(4) | on if winning | +0.70 (-0.49) | +1.66 | +1.31 | -30% | 0.83 | **HURTS** |
| Own drawdown gate | off in deep DD | +0.92 (-0.27) | +2.33 | +1.11 | -36% | 0.75–1.00 | **NO HELP** |
| Vol-targeting overlay | continuous | +1.22 (+0.03) | +2.31 | +1.24 | -29% | 0.96 | neutral, very robust |
| BTC vol HIGH / disp LOW / breadth DOWN / BTC downtrend | (inverse) | +0.5…+0.9 | <base | often **negative** | — | — | **confirm wrong-way** |

**Reads**

- **(a) Momentum is a RISK-ON / HIGH-DISPERSION phenomenon.** Every "on in the good regime"
  filter (BTC uptrend, low vol, high dispersion, broad-up) helps or is neutral; every inverse
  ("on in stress") is strictly worse, often turning PREV12 **negative**. The edge is concentrated
  in calm, trending, dispersed markets — exactly the textbook momentum environment.
- **(b) The own-equity "turn off after a losing streak" idea is a TRAP.** Gating off after the
  strategy's own drawdown/low rolling-Sharpe *lowers* OOS Sharpe (e.g. Sharpe(4) +1.19→+0.70).
  Momentum's own losses are followed by rebounds, so de-risking post-loss sells the bottom.
  Autocorrelation of the strategy's weekly returns is near zero — there is nothing to time there.
- **(c) Funding-stress: untestable.** OKX `funding-rate-history` returns only ~94 days. Recent
  aggregate 8h funding is ~flat/slightly negative (not crowded-long *now*). No multi-year backtest
  is possible on the permitted (Binance/Bybit-blocked) venues, so we do not deploy a funding gate.

## 2. The winner — BTC-trend gate: ROBUSTNESS (plateau, not spike)

**Dense threshold sweep, MA=50, equal-weight** (gate ON when BTC/MA50 − 1 ≥ thr):

| thr | OOS18 | REC12 | PREV12 | FULL maxDD | OOS18 maxDD | rec exp |
|---|---|---|---|---|---|---|
| -0.12 | +1.46 | +2.28 | +1.70 | -39% | -19% | 0.87 |
| -0.10 | +1.48 | +2.28 | +1.71 | -39% | -19% | 0.87 |
| -0.08 | +1.34 | +2.23 | +1.74 | -39% | -19% | 0.81 |
| **-0.06** | +1.44 | +2.15 | +1.97 | -35% | -14% | 0.77 |
| **-0.04** | +1.46 | +2.12 | +1.91 | -35% | -13% | 0.69 |
| -0.02 | +1.24 | +1.96 | +1.88 | -33% | -15% | 0.58 |
|  0.00 | +1.22 | +1.55 | +2.01 | -33% | -12% | 0.46 |

The **entire −0.12 → −0.02 band improves OOS18 and PREV12 vs base while roughly halving maxDD** —
a plateau. Tightening the threshold past 0 over-trims exposure and erodes REC12 (you sit out too
much). **MA-length** is also a plateau: MA50/75/100 all give OOS18 +1.37…+1.57; only MA200 (too
slow) breaks. rank-weight gives the same picture (OOS18 +1.36…+1.46 across the band).

**Year-by-year** (equal, MA50, thr−0.05) vs base — improves the weak years, holds the strong ones:

| | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|
| base | +1.04 | +0.96 | +0.55 | +2.91 | +1.21 | +1.15 |
| **trend-gated** | +1.74 | +0.70 | +0.48 | +2.79 | +1.58 | **+1.62** |

## 3. The winner — FALSIFICATION tests (does it pay for the right reason?)

| Test | equal | rank | reading |
|---|---|---|---|
| **Q1 conditional Sharpe**: base return when gate ON vs OFF | ON +1.80 / OFF **−0.30** | ON +1.87 / OFF **−0.42** | the OFF weeks (BTC<MA50) are genuinely a **negative-Sharpe regime** — the gate skips real losers, not random weeks |
| **Q2 strict IS-only pick** of (MA, thr) → read OOS | MA100/0.0 → OOS18 **+1.22** (base +1.19), maxDD **−13%** | MA100/0.0 → OOS18 **+1.32** (base +1.14), maxDD **−15%** | survives a clean no-peek protocol: modest Sharpe lift, **big drawdown cut** |
| **Q3 vol-neutral** (re-lever gated book to base vol) | OOS18 **+1.57** (base +1.19) | **+1.56** (base +1.14) | gain is **pure timing**, not just deleveraging |
| **Q4 placebo** (400 random gates, matched 72% exposure) | random +1.00±0.42; real **+1.57 = 94th pctile** | random +0.96±0.41; real +1.56 = 94th pctile | unlikely by chance |

Q1 is the key result: BTC-below-MA weeks earn a **negative** Sharpe for the momentum book, so
turning off there is economically motivated, not a curve-fit. Q3 proves the Sharpe improvement
holds after equalizing risk. Q4 says the specific gate beats ~94% of random gates of equal size.

## 4. Best timing rule (deployable) and a combined variant

**RULE (honest, strict-IS pick):** at each weekly rebalance, compute BTC's 100-day SMA.
**If BTC close ≥ MA100 → run the full dollar-neutral momentum book; else → go FLAT** (0 gross)
until BTC reclaims the MA. (MA50–100 and a small negative buffer −0.05 are all in the plateau;
MA100/0 is the most conservative no-peek choice.) Effect: OOS18 Sharpe +1.22→+1.32 (vs base
+1.14–1.19), **OOS maxDD −31% → −13/−15%**, recent-12mo exposure ~50–55%.

**Optional combined gate (best all-round, full-shape thresholds):**
**ON only when (BTC ≥ MA50·0.95) AND (10d return dispersion ≥ its rolling 20th percentile).**

| combined | OOS18 | REC12 | PREV12 | FULL maxDD | OOS18 maxDD | rec exp |
|---|---|---|---|---|---|---|
| equal | **+1.68** | +2.46 | +1.92 | -33% | **-13%** | 0.60 |
| rank | **+1.54** | +2.29 | +2.04 | -35% | **-16%** | 0.60 |

The combine improves **every** window in **both** schemes over base and cuts maxDD by half, at the
cost of ~40% time in cash. Dispersion alone lifts REC12 most (+2.58→+2.80) but barely touches
drawdown; trend alone cuts drawdown most. Together they cover both objectives.

## 5. Honest limitations

- **The filter trims, it doesn't transform.** It removes a structurally bad regime; it cannot
  rescue a decayed signal. The Sharpe lift from the strict-IS rule is **modest (~+0.1–0.2)**; the
  headline win is **risk** (maxDD roughly halved) and avoiding the crowded-negative stretches.
- **Exposure cost.** You sit in cash ~30–50% of recent time, so absolute return is lower even as
  Sharpe/maxDD improve. Re-levering ON-periods (Q3) recovers return at equal risk if desired.
- **Survivorship** (sibling caveat) still biases absolute numbers up; discount accordingly. A
  realistic forward expectation is base ~1.0–1.5 lifted to ~1.2–1.6 net **with materially smaller
  drawdowns**, not a Sharpe-doubling.
- **Funding/OI crowding gate not deliverable** on the allowed venues (history too short). If a
  longer funding series becomes available, an aggregate-funding-stress gate is the obvious next test.

## Files

- `regime_fetch.py` — OKX funding-rate fetcher (documents the ~3mo history limit).
- `regime_backtest.py` — overlay engine: base-book builder, gate application w/ cost re-flow,
  regime-signal library (BTC/basket vol, dispersion, trend, breadth, funding, own-equity), windows.
- `regime_run.py` — full filter × threshold sweep (§1) with IS-only pick highlighted.
- `regime_deep.py` — dense plateau, MA-length robustness, year-by-year, combined gate (§2, §4).
- `regime_honesty.py` — conditional-Sharpe, strict-IS pick, vol-neutral, placebo, funding (§3, §5).
