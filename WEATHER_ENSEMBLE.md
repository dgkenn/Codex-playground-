# WEATHER_ENSEMBLE — does a real ensemble-probability edge beat Kalshi weather?

Date: 2026-07-23. Scope: the ensemble-probability thesis for Kalshi weather markets
(`KXHIGH*`/`KXLOWT*`), backtested two independent ways and put through Fable adversarial
verification.

## DEPLOYABLE: NO. Honest capacity: $0/mo.

**Even the ensemble version of the weather thesis — a strictly higher evidentiary bar than
the already-dead point-forecast overlay — does not beat Kalshi weather.** No sleeve was
built (per the task's "if not deployable, doc-only" branch). This closes the weather
forecasting axis at the ensemble level, not just the deterministic-forecast level.

---

## 1. The thesis (info-gap, not the dead overlay)

The prior forecast-overlay sleeve (`FORECAST_OVERLAY_BACKTEST.md`, REFUTED, PR #53) died on
two bugs: (a) a look-ahead — the "forecast" input was assembled from model runs issued
*after* the sleeve's decision window, and (b) a `settle()` accounting bug that mispriced the
NO side. Once both were fixed, its honest edge collapsed to −0.016c/ct (t=−1.74) — a
deterministic point-forecast has no edge over Kalshi's crossing price.

The **ensemble** thesis is a different, harder-to-dismiss claim: even with the look-ahead and
settle bugs fixed, maybe a full **probability distribution** — not just a bias-corrected point
estimate — carries information the market hasn't priced. Retail Kalshi weather traders mostly
see a point forecast (NWS/AccuWeather high temp); if the market-implied probability reflects
that point-forecast "crowd" rather than the true forecast uncertainty (spread, skew, tail
risk) that a 50-member operational ensemble encodes, there could be an **information gap**
between ensemble-grade uncertainty and what's priced. This is the info-gap thesis this task
set out to test — genuinely distinct from, and a strictly higher bar than, the dead
point-forecast overlay above.

Both backtests below fix the overlay's two known bugs by construction: entry timestamps are
verified to precede both the market close and (for the samemorning arm, with a caveat) the
forecast run's issue time, and settlement prices both YES and NO legs correctly
(NO payoff = 100 − no_price).

---

## 2. Backtest A (true 51-member ensemble) — NEVER COMPLETED

`bt_ens/bt_ens.py` (11.6KB, pre-registered pass bar in its own docstring: mean EV/contract >
0 net of fee, day-clustered t≥3, OOS split, Wilson LB positive, primary threshold 0.08 swept
over {0.03,0.05,0.08,0.10,0.15,0.20}) is the only artifact in `bt_ens/` — no
`joined_rows.json`, no `trade_cache.json`, no results file. Its own docstring records why:
Open-Meteo's `ensemble-api.open-meteo.com` **historical** path only retains non-null member
data for the trailing ~3–4 days from query time, collapsing the usable settled-market sample
to 2026-07-20/21/22 (2026-07-23 unsettled) — a severe, structural sample-size ceiling that
also makes clean look-ahead verification impossible at any useful N. **This is a
data-infrastructure finding, not a result**, and it is independently corroborated by Backtest
B below. Backtest A produced no numeric verdict and contributes no PnL claim to this report.

---

## 3. Backtest B (independent cross-check, substitute fitted-Gaussian) — completed

Full report: `bt_ens2/bt_ens2_report.md` (code: `harvest.py`, `fetch_trades.py`,
`analyze.py`; raw caches `raw_forecast.json`, `raw_era5.json`, `raw_trades.json`; numeric
output `results.json`). Written independently of Backtest A's code/results.

**Design**: Open-Meteo `previous-runs-api` (`ecmwf_ifs025`) gives a genuine archived
forecast-run with per-hour lead tags. Two leads tested, both entry timestamps verified to
precede market close and settlement:
- `dayahead` (~24h lead): entry = previous local evening 21:00.
- `samemorning` (~0–9h lead for the afternoon peak): entry = same-day local 09:00.

Because true multi-member ensemble history is unobtainable beyond ~92h (see §4), Backtest B
substitutes a **fitted Gaussian** — bias-corrected deterministic forecast ± FIT-window
residual sigma, per city per lead — for the ensemble's probability distribution. FIT window
2026-04-24→2026-05-31 (38 days, bias/sigma only, never touches Kalshi prices); VALIDATION
2026-06-01→2026-07-20 (50 days OOS, no overlap). Scope: 4 cities picked for climate
diversity before pulling data (KDEN, KMIA, KSEA, KPHX), `KXHIGH*` series only. Entry executed
at the **real tape print** nearest-after each simulated entry (yes_price/no_price/
taker_side/created_time from `/markets/trades`, not mid/last); fee `ceil(7p(1-p))/100` per
contract at that price; settlement from `market.result`, NO payoff = 100 − no_price, verified
against live event payloads for all three strike-bucket shapes (B/floor-only/cap-only).
Day-clustered by settlement date (4 cities on the same day share correlated synoptic
weather).

**Pre-registered pass bar** (set before VALIDATION data was read): day-clustered 95% CI of
mean PnL/contract strictly > 0, surviving Bonferroni for 2 leads (effective α 0.025/lead);
min 2¢ net edge to simulate a trade.

### Results

| Lead | N trades | N days | Mean PnL ¢/ct | 95% CI | Win rate (Wilson 95%) | Model Brier | Market-implied Brier |
|---|---|---|---|---|---|---|---|
| dayahead (~24h) | 756 | 50 | **−0.55¢** | [−3.70, +2.60] | 43.8% [40.3%, 47.3%] | 0.133 | **0.106** |
| samemorning (~0–9h) | 690 | 50 | **−0.59¢** | [−2.50, +1.31] | 37.8% [34.3%, 41.5%] | 0.122 | **0.049** |

Both CIs straddle zero comfortably (t = −0.34, −0.61) — neither clears an uncorrected test,
let alone the pre-registered Bonferroni bar. Both leads agree in sign (both slightly
negative): the null is consistent across leads, not lead-dependent noise cancelling out.
**The market beats the model at both leads** — Kalshi's crossing price alone has a lower
Brier score than the ensemble-substitute forecast, especially same-morning (market 0.049 vs
model 0.122), evidence the market has absorbed intraday information the forecast-only model
lacks.

**Calibration**: the fitted-Gaussian substitute is overconfident in the mid/upper probability
bins at both leads (e.g. dayahead 0.6–0.8 bin: model says 66%, realized 44%) — the FIT-window
sigma is too narrow, manufacturing apparent "edge" the market correctly declines to pay for.
Nominal capacity at these point estimates: ≈ −$2.49/mo (dayahead), ≈ −$2.46/mo
(samemorning) at 1 contract/trade — near-zero and, if anything, negative. Capacity gates do
not apply to a null result.

---

## 4. Why not a true multi-member ensemble (the house-note correction)

Both agents independently re-verified 2026-07-23: `ensemble-api.open-meteo.com`'s
**historical** path (`start_date`/`end_date` in the past, `past_days` 1–100) returns
all-NULL for every member of every ensemble model tested (`ecmwf_ifs025`, `gfs_seamless`,
`icon_seamless`, `gem_global`, `ecmwf_aifs025`, `ukmo_global_ensemble_20km`) once the request
reaches more than **~92 hours (3.8 days)** before the call time — a hard retention wall, not
a boundary-hours artifact. **The prior house note that "historical ensemble is confirmed
working" is REFUTED and corrected here**: that confirmation was only ever exercised against
the live/near-term window, never a genuinely historical one. No free source combines a
genuine past fixed forecast lead with member/spread granularity far enough back to run a
day-clustered OOS test — this is the structural reason Backtest A never completed and
Backtest B had to substitute a fitted Gaussian.

---

## 5. Fable adversarial verification

**Verdict: CONFIRMED, deployable = false.**

> Honest null CONFIRMED: no exploitable ensemble/forecast-vs-Kalshi-weather edge at either
> tested lead. Backtest A (true 51-member ensemble) NEVER COMPLETED — its recon and
> Backtest B independently proved Open-Meteo's free ensemble-api retains member data only
> ~92h back, so no historical multi-member ensemble backtest is feasible on free data.
> Backtest B (4 cities, HIGH series, 50-day OOS, bias-corrected deterministic forecast +
> fitted Gaussian) fully reproduced by independent recomputation from raw caches: dayahead
> −0.55c/ct (t=−0.34, CI [−3.70,+2.60], N=756/50 days), samemorning −0.59c (t=−0.61, CI
> [−2.50,+1.31], N=690/50 days); real tape entry prints (0 pre-entry violations, yes+no=100
> on all), house fee formula, NO payoff 100−no_price all verified correct. Look-ahead:
> dayahead arm materially clean; samemorning arm CONTAMINATED (day0 values use runs issued
> after the 09:00 entry — MAE 0.97F vs 1.65F day1 confirms near-analysis skill) — but
> contamination biases TOWARD edge and the model still loses to the market (model Brier
> 0.122 vs market 0.049), so the null holds a fortiori. Market is better calibrated than the
> model at both leads. Nothing deployable; capacity $0/mo.

**Look-ahead-clean check (per house KILL RISK #1)**: `lookahead_clean = false` at the
verifier's strict standard. The `dayahead` arm is materially clean (entry precedes both
market close and the forecast run's issue time by construction, ~24h lead). The
`samemorning` arm is contaminated — its "day0" temperature values are Open-Meteo's freshest
run at each valid hour, so afternoon-peak values can come from runs issued/published *after*
the 09:00 local entry (empirically confirmed: day0 daily-max MAE 0.97–1.98F vs day1
0.86–2.29F, i.e. near-analysis skill, not a clean 0–9h forecast). Critically, this
contamination biases **toward** finding an edge (the model gets to peek at fresher
information than a real trader would have), and the result is still null — so the null is
*strengthened*, not undermined, by the one look-ahead flaw found. The verifier's other four
house kill-risk checks (real tape crossing price, fee formula, both-sides settlement
accounting, day-clustering) passed clean.

**Other issues the verifier flagged** (informational, do not change the verdict): only one
of two backtests completed numerically (A/B reconciliation is data-infra-only, not a second
independent PnL number); entry-to-fill pairing allows up to an 8h gap between decision and
executed print (23/1200 dayahead and 7/1200 samemorning markets had no print in-window and
were dropped, not scored); the fitted-Gaussian is a substitute for a true ensemble and is
demonstrably overconfident in mid/upper bins, so this null rules out *this model's* edge, not
any conceivable true-ensemble edge; scope is 4/20 cities, HIGH series only, one 50-day summer
window.

---

## 6. Bottom line

**DEPLOYABLE: NO.** Honest capacity: **$0/mo.** No sleeve, no `p4k_params.json` change, no
live-path (`kwx_runner.py`/`kwx_paper_gate.py`/`kalshi_exec.py`) touch. The weather
forecasting axis is now closed at both the deterministic-point-forecast level
(`FORECAST_OVERLAY_BACKTEST.md`) and the ensemble-probability level (this document): Kalshi
weather markets price not just a point forecast but ensemble-grade uncertainty (spread,
calibration) as well or better than the best free-data reconstruction this repo can build.
The one durable, actionable finding is technical, not statistical: Open-Meteo's free
historical ensemble-member archive is unusable beyond ~92 hours back, which corrects the
prior house note and should prevent any future study from silently assuming that archive
exists. A paid/longer ensemble archive, or a forward paper-trading harness accruing live
`ensemble-api` days going forward, remain the only sound ways to test this thesis again —
neither was in scope here.

See also: `RESEARCH_LEDGER.md` §3 (graveyard entry added), `FORECAST_OVERLAY_BACKTEST.md`
(the sibling deterministic-forecast study this cross-checks against), `bt_ens/bt_ens.py`
(Backtest A, incomplete), `bt_ens2/bt_ens2_report.md` (Backtest B, complete).
