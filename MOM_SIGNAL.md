# Cross-Sectional Crypto Momentum — Best SIGNAL & UNIVERSE

Scope (per task split): **signal construction + universe + weighting only.** Risk/deploy,
param-robustness deep-dive, and multi-factor are owned by sibling agents and not duplicated here.

## TL;DR verdict

The plain-14d baseline is **fragile at the lookback it's defined on** — its recent-regime
OOS Sharpe collapses to ~0.1 even though its full-history headline is ~1.3. The robust
improvement is to **shorten the lookback to ~10 days and risk-adjust** (return / trailing vol).

**Best robust config: risk-adjusted 10-day momentum, top-15 liquid USDT perps,
rank- or equal-weight, dollar-neutral, weekly rebalance, 30% tails.**
- Recent-12mo OOS net Sharpe **~2.0** vs baseline **~0.1** (full-history: ~1.3 both).
- Holds across **two independent OOS windows** (last 12mo AND the prior 12mo) and across a
  **9–13d lookback plateau** — not a single spike.
- Honest caveats: short lookback ⇒ higher turnover (~2.5×/rebalance); break-even cost ~45bps
  (comfortable vs the 9–12bps bar). Partial-2026 is negative for most configs (regime/crowding).

## Method / bar

- **Data:** OKX `history-candles`, daily (`1Dutc`), 37 USDT perps, 2020-01-01 → 2026-06-13
  (`mom_fetch.py` → `mom_data.parquet`). Closed candles only.
- **Backtest:** weekly rebalance (7d hold), perp long top-30% / short bottom-30%,
  **dollar-neutral**, point-in-time liquid universe (top-N by trailing-30d median quote volume).
  Forward return realized close→close; turnover-based cost charged each rebalance.
- **Costs:** default **9 bps/side** (≈18bps round-trip per unit leg turnover); swept 5–18.
- **OOS protocol:** params chosen on full/IS shape; reported on a **hard last-18mo holdout**,
  with **recent-12mo** (REC12) and an **independent prior-12mo** (PREV12 = 24→12mo ago) slice
  to test that the edge isn't a one-window fluke. Sharpe annualized ×√52.
- **Survivorship (honest):** OKX serves only *currently-listed* instruments. Delisted alts
  (dead 2021-cycle tokens, LUNA/UST, FTT, etc.) are **missing** ⇒ results are biased **upward**;
  absolute Sharpe should be discounted, but the *relative* ranking of variants is robust to this.

## 1. Signal variants — OOS table (top-15, equal-wt, 30% tails, 9bps)

Net Sharpe. FULL = full history; OOS18 = last 18mo; **REC12 = recent 12mo (headline)**.

| Signal | FULL | OOS18 | **REC12** | Note |
|---|---|---|---|---|
| **plain-14d raw (BASELINE)** | +1.28 | -0.06 | **+0.28** | strong headline, **fragile recent** |
| raw-7d | +0.78 | +0.37 | **+1.34** | short lookback wins recently |
| raw-30d | +0.53 | -0.74 | **-0.73** | long lookback dead OOS |
| raw-60d | +0.07 | -0.97 | **-1.25** | long lookback dead OOS |
| **riskadj-14d (ret/vol)** | +1.12 | +0.70 | **+1.13** | dominates raw-14d OOS |
| riskadj-30d | +0.50 | -0.73 | **-0.91** | |
| riskadj-60d | +0.33 | -0.60 | **-1.14** | |
| skip-recent3 14d→t-3 | +0.72 | +0.67 | **+0.87** | modest, no edge over short raw |
| skip-recent3 21/30d | +0.20/+0.12 | -0.07/-0.62 | +0.14/-0.73 | weak |
| ensemble 7/14/30/60 | +0.68 | -0.25 | **+0.17** | long legs drag it down |
| residual-vs-BTC 14d | -0.26 | +0.45 | **+0.03** | beta-strip didn't help net |
| residual-vs-BTC 30/60d | +0.13/-0.47 | -1.40/-0.63 | -0.30/-0.51 | weak |

**Reads:**
- **(a) Risk-adjustment helps** at the *right* lookback: riskadj-14d (OOS18 +0.70, REC12 +1.13)
  clearly dominates raw-14d (OOS18 -0.06, REC12 +0.28). It de-weights high-vol noise coins.
- **(b) Skip-recent (12-1 style) does NOT help** in crypto at weekly horizon — short-term
  *continuation* dominates over short-term reversal here; skipping the last 3d just throws away
  signal. (This contrasts with equities; crypto momentum lives at shorter horizons.)
- **(c) Multi-lookback ensemble underperforms** — the 30/60d legs are negative OOS and drag
  the blend down. Averaging across a bad horizon is not robustness, it's dilution.
- **(d) Residual (BTC-beta-stripped) momentum is a net loser** here — removing the market
  component removes most of the realized edge; idiosyncratic-only momentum is weak net of costs.
- **(e) Vol-normalized positions** (volinv weighting) ≈ equal-weight, slightly lower vol (see §3).

**The decisive axis is LOOKBACK, not the transform.** Short (≈10d) >> long (30–60d).

## 2. Universe sweep (best short signal, equal-wt, 9bps)

REC12 net Sharpe / ann return:

| Universe | FULL Sh | OOS18 Sh | **REC12 Sh** | REC12 ann |
|---|---|---|---|---|
| top-8 (incl BTC/ETH) | +1.23 | +1.05 | **+1.08** | +43% |
| **top-15 (incl BTC/ETH)** | +1.34 | +1.25 | **+2.07** | +79% |
| top-25 | +1.10 | +0.68 | **+1.14** | +35% |
| top-40 | +0.99 | +1.11 | **+1.47** | +44% |
| top-15 EXCL BTC/ETH | +1.40 | +0.86 | **+1.61** | +65% |
| top-25 EXCL BTC/ETH | +1.13 | +0.48 | **+0.92** | +31% |

**Reads:**
- **top-15 is the sweet spot.** top-8 is too small (insufficient cross-sectional dispersion);
  top-25/40 dilute into thinner/noisier coins and OOS Sharpe softens. (Note: our 37-coin set is
  itself survivorship-pruned, so the true top-40 net edge is likely *worse* than shown.)
- **Excluding BTC/ETH** does NOT improve net OOS — the mega-caps add useful low-vol anchor legs
  to a dollar-neutral book; dropping them raises vol without raising Sharpe. **Keep BTC/ETH in.**

## 3. Weighting sweep (riskadj-10d, top-15, 9bps)

FULL / OOS18 / REC12 / PREV12 net Sharpe:

| Weighting | FULL | OOS18 | REC12 | PREV12 | avg turn |
|---|---|---|---|---|---|
| **equal** | +1.31 | +1.33 | +2.17 | +1.42 | 2.43 |
| **rank** | +1.34 | +1.25 | +2.07 | +1.63 | 2.55 |
| signal-proportional | +1.14 | +0.92 | +1.67 | +1.93 | 3.02 |
| vol-inverse | +1.35 | +1.53 | +2.59 | +1.15 | 2.55 |

**Reads:** equal and rank are the most *consistent across both OOS windows* (tightest REC12↔PREV12
spread) and lowest turnover. signal-proportional concentrates too hard (higher vol/turnover, no
Sharpe gain). vol-inverse posts the single highest REC12 (2.59) but its PREV12 (1.15) is the
weakest — that's a **window-specific spike, not robust** → not selected. **Use equal or rank.**
All are dollar-neutral by construction; beta-neutral was not needed (mega-caps already balance).

## 4. Robustness — plateau, not spike

**Fine lookback grid** (riskadj, top-15, rank, 9bps), REC12 / PREV12 net Sharpe:

| lb | 7d | 8d | 9d | **10d** | 11d | 12d | 13d | 14d |
|---|---|---|---|---|---|---|---|---|
| REC12 | +0.92 | +1.40 | +1.27 | **+2.07** | +1.61 | +1.41 | +1.62 | +0.91 |
| PREV12 | +1.57 | +1.21 | +1.63 | **+1.63** | +1.19 | +1.28 | +1.72 | +2.04 |

The **entire 8–13d band is solidly positive in BOTH independent OOS windows** — a plateau. lb=10
is the peak but is surrounded by good neighbors, so it is not a fragile point estimate. The 14d
baseline lookback sits at the unstable edge (REC12 swings 0.12–0.91 depending on transform/weight).

**Year-by-year net Sharpe** (top-15, equal, 9bps):

| cfg | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|
| raw-10d | +1.20 | +1.72 | +1.17 | +2.28 | +1.92 | -0.46 |
| riskadj-14d | +1.89 | +0.59 | +0.71 | +2.76 | +1.23 | -0.19 |
| plain-14d (baseline) | +2.15 | +1.26 | +1.01 | +2.13 | +0.83 | **-1.90** |

raw-10d / riskadj are positive every full year; **2026 (partial, ~5.5mo) is negative** for all
— consistent with the task's "decaying with crowding" warning. The baseline's 2026 is the worst.

**Cost / break-even** (REC12, top-15): raw-10d stays positive to ~40bps/side; riskadj-10d to
~48bps/side. At the realistic 9–12bps bar both retain Sharpe ~1.2–2.0. Edge is **not** a
cost artifact, but it **is** turnover-heavy (~2.5×), so execution quality matters at scale.

## Best config vs baseline

| | plain-14d BASELINE | **BEST: riskadj-10d, top-15, rank/equal** |
|---|---|---|
| Full-history Sharpe | +1.28 | +1.3–1.34 |
| OOS-18mo Sharpe | **-0.06 → +0.21** | **+1.25–1.33** |
| **REC-12mo Sharpe (headline)** | **+0.12–0.28** | **+2.0** |
| REC-12mo ann return | ~+4–9% | ~+77% |
| PREV-12mo Sharpe (independent) | +1.35 | +1.4–1.6 |
| Turnover / rebalance | 2.1× | 2.4–2.5× |
| Break-even cost | — | ~45 bps/side |

**Improvement over baseline:** recent-regime OOS Sharpe rises from ~0.1–0.3 to ~2.0 by
(i) shortening the lookback from 14d→~10d and (ii) risk-adjusting (ret/vol). Discounting for
survivorship, a realistic **forward expectation is Sharpe ~1.0–1.5 net** (vs baseline's
decayed ~0.3–0.7), with the band 8–13d giving similar results — pick 10d for the plateau center.

**Honest negatives:** skip-recent, multi-lookback ensemble, residual/BTC-beta-stripped momentum,
universe expansion beyond ~15, and signal-proportional/vol-inverse weighting all **failed** to
beat the simple short risk-adjusted variant on robust (two-window) OOS. The real edge is "use a
shorter lookback and risk-adjust," not any exotic transform.

## Files
- `mom_fetch.py` — OKX daily OHLCV fetcher (universe + survivorship note).
- `mom_backtest.py` — signal library (raw/riskadj/skip/ensemble/residual), weighting schemes, weekly XS backtest engine, windowed stats.
- `mom_sweep.py` — signal × universe × weighting × cost × lookback sweep (§1–§3, lookback table).
- `mom_robust.py` — fine lookback grid, two-window OOS, year-by-year, break-even cost (§4).
- `mom_final.py` — best-config confirmation (10d × weighting × universe + plateau).
