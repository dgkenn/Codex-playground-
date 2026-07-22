# FORECAST_OVERLAY_BACKTEST — does the forecast-vs-market-price sleeve (wx_forecast_forward.py) hold up on real history?

Date: 2026-07-21/22. Scope: two independent implementations (A, B) backtested the "forecast overlay" premise
-- use a free Open-Meteo forecast (`wx_forecast_model.py`) to compute `forecast_prob` per Kalshi temperature
rung and trade wherever it disagrees with the market's `yes_ask` by >= 0.15 -- against real history, reconciled
against each other, then put through a Fable adversarial verification pass. **This document reports the
verifier's verdict, not the two backtests' headline agreement -- the headline does not survive.**

## Verdict: NOT a real, activatable edge. `deployable = false`.

Both backtests nominally agreed (A: +0.203c/ct literal / +0.114c/ct honest-cost, t=16.5/11.1 day-clustered,
178 distinct days; B: +0.142c/ct, t=18.5, 427 distinct days) and their day-clustered t-statistics reproduced
exactly from their own trade logs, with 98.7% side agreement across 1,585 tickers common to both. **That
agreement was real but uninformative**: both implementations pulled their forecast input from the same
contaminated source. Open-Meteo's historical-forecast API returns a day-0 daily `temperature_2m_max` that is
assembled from the **latest intraday model runs** (lead ~0-6h) -- including runs issued *after* the sleeve's
05:00-11:00 local decision window and after the price snapshot the backtest priced against. That is
look-ahead: the "forecast" the backtest scored against already knew most of the day's actual weather.

## 1. The look-ahead, quantified against the sleeve's own live data

The forward paper harness (`wx_forecast_forward.py`) has been running live since 2026-07-19 and had 39
station-days of independently logged **morning** forecasts to check the archive against:

| forecast source | RMSE vs realized ASOS max |
|---|---|
| live-logged morning forecast (what the sleeve actually saw pre-decision) | **2.40F** |
| Open-Meteo historical-forecast archive, day-0 (what both backtests used) | **1.53F** |
| archive vs. the live morning forecast, directly | **2.44F RMSE** |

Example: KMDW 2026-07-20 -- live morning forecast 88.6F, archive day-0 value 80.6F, realized 82F. The archive
"knew" the bust; the morning forecast did not. An archive that is 2.44F RMSE away from what the sleeve would
actually have seen live is not a faithful backtest input -- it is closer to a same-day nowcast than a morning
forecast.

**Lead-1 previous-runs API validated as an unbiased proxy for the live morning value**: mean diff -0.04F,
RMSE 1.82F vs. the 39 live-logged station-days (vs. 2.44F for the day-0 archive). This is the honest input a
morning-decision backtest must use.

## 2. Honest rerun (no look-ahead)

Re-running Implementation A's exact pipeline with the validated lead-1 previous-runs forecasts, holding
everything else fixed (same cities, same window, same fee formula, same 178 distinct days, 2,614 trades):

| | leaky day-0 archive (both original backtests) | honest lead-1 rerun |
|---|---|---|
| EV/contract, net of fee | +0.114 to +0.203 | **-0.016** |
| day-clustered t | +11.1 to +16.5 | **-1.74** |
| win rate | (not directly comparable) | **39.6%** |
| distinct days | 178 | 178 |

The edge is fully explained by the leak. Interpolating a *true* morning-accuracy figure (2.40F, between the
archive's 1.53F and lead-1's 3.05F standalone residual) puts the honest edge near zero -- well below any
deployable bar and inside the noise band of trade-print fill optimism (below).

## 3. A second, independent bug (inflates both the backtest and the live paper log)

`wx_forecast_forward.settle()` prices **every** settled row -- including `side == "no"` rows -- using the
`yes_ask` price as the cost basis: `pnl = (1 - price - fee) if won else (-price - fee)`. For a NO position the
correct cost basis is the NO price (~`1 - yes_ask`, absent a captured no-side book), not the YES price. This
bug alone manufactures roughly **+0.08c/contract (t=7.7)** of apparent edge with zero real signal, and it also
inflates the **live paper log**: `wx_forecast_settled.jsonl` currently shows +0.217/trade over 112 rows, which
sounds attractive until you check the denominator -- those 112 rows span **2 calendar days** (2026-07-19,
2026-07-20). That is statistically empty (pseudo-replication: same-day fires across cities/rungs are not
independent draws) and additionally inflated by the same cost-basis bug. It is not evidence of anything yet.

## 4. Other flatterers in the original backtests (noted, not individually fatal on top of #1-#3)

- **Fill realism**: both backtests used the observed trade-print price as an ask proxy (zero-impact fills);
  ~19% of rungs were excluded for having no morning print at all (a liquidity-selection filter that keeps the
  easier-to-fill rungs and drops the rest).
- **SIGMA_MAX=1.2 miscalibration**: `wx_forecast_model.py`'s SIGMA_MAX was fit to a "lead-0, morning-of"
  residual of ~1.17F -- which, per Section 1, is the **leaky archive's** residual, not the live morning
  residual (2.40F). The deployed model's predictive distribution is roughly **2x overconfident** relative to
  what it actually sees live. `BIAS_MAX_CORRECTION=+1.09F` also has the wrong sign on the 39-day live sample
  (the live raw forecast ran +1.06F **warm**, not cold, over that window) -- too small a sample to recalibrate
  from yet, but a flag that the correction direction needs live-data confirmation before it is trusted, not a
  fixed constant carried over from the leaky fit.

## 5. Prior art -- this is a rediscovery, not a new mechanism

`WX_DIRECTIONAL.md` already records a **WEATHER-EDGE** decision (2026-07-17, 315 city-days): the market prices
public NWS/NBM-MOS forecasts at least as well as the forecast itself, and trading the forecast-vs-market
divergence loses money (-1.7c/ct, t=-2.18). This forecast-overlay study probes the same axis (a public,
free forecast vs. Kalshi's market price) with a different forecast source and different backtest machinery,
and lands on the same wall. Public forecast information is priced; beating the market needs private/faster
information this repo does not have.

## Capacity: $0/month

Moot -- there is no verified positive edge to size. `capacity_usd_month = 0`.

## Actions taken / recorded

1. **Do NOT deploy.** No change to the live mechanical-lock path (`kwx_runner.py`, `kwx_paper_gate.py`,
   `kalshi_exec.py`) -- none was made or considered; this sleeve was never wired into it.
2. `wx_forecast_decision.py` (new, this change) is the KILL/keep-accruing decision gate for this sleeve:
   it records the verified backtest bar above (honest EV -0.016c/ct, day-clustered t=-1.74, 178 distinct
   days) as the number any future forward evidence must beat, recomputes pnl from raw fields (bypassing the
   known NO-side cost-basis bug in `wx_forecast_forward.settle()` rather than trusting the logged `pnl`), and
   emits KILL / ACCRUING / RECONSIDER against a conservative, Wilson/day-clustered bar. It never places
   orders and only reads the existing paper logs.
3. `p4k_params.json`'s new `sleeves.forecast` entry is set to `quality: BACKTEST (refuted)`, `status:
   REFUTED`, gated on `wx_forecast_decision.py`'s own distinct-day accrual, and is **not** modeled as a
   capacity lever (mirrors how `early_lock` and `maker` are carried after their own refutations) -- it does
   not move the headline $/mo figure.
4. **Not fixed in this change** (flagged for whoever next touches `wx_forecast_forward.py` /
   `wx_forecast_model.py`, deliberately left alone here to keep this a docs+gate change, not a live-adjacent
   code change): `settle()`'s NO-side cost-basis bug (Section 3), and `SIGMA_MAX`/`BIAS_MAX_CORRECTION`
   recalibration off the live 2.40F morning residual instead of the leaky 1.17F archive fit (Section 4). Any
   future rerun of this study **must** use the previous-runs/lead-shifted Open-Meteo API, never the day-0
   historical-forecast endpoint, for the forecast input.

## Reproduction

Backtest artifacts (Impl A, Impl B) and the Fable verifier's full findings were produced under
`/tmp/claude-0/-home-user-Codex-playground-/a1344cbd-0d6d-5d88-b275-43c6164c3448/scratchpad/fcbt/implA/` and
`.../implB/` (scratchpad, not committed -- read-only public-API backtests, reproducible from the commands
logged in those directories against `kx_history.py` + Open-Meteo's previous-runs API). The live forward paper
harness continues to accrue at `wx_forecast_paper.jsonl` / `wx_forecast_settled.jsonl`; check current status
with `python wx_forecast_decision.py`.
