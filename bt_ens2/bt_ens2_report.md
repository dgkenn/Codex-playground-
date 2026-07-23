# Backtest B — independent cross-check of ensemble-vs-Kalshi, with lead sensitivity

Written independently (did not read the sibling `wxens/` backtest's code or results before or during
this analysis). Code: `harvest.py`, `fetch_trades.py`, `analyze.py` in this directory. Raw caches:
`raw_forecast.json`, `raw_era5.json`, `raw_events.json`, `raw_trades.json`. Full numeric output:
`results.json`.

## Verdict: FAIL (null) at both leads tested — no exploitable edge found

Consistent with the pre-registered honest-null expectation ("Kalshi weather already prices the
ensemble = efficient"). Both leads land on essentially zero edge, and the market's own crossing prices
are a **better** (lower-Brier) forecast of the outcome than the model built for this test.

## Pre-registration (set before any VALIDATION-window number was looked at)

- Pass bar: day-clustered 95% CI of mean PnL/contract strictly > 0 for a lead, surviving Bonferroni
  correction for the 2 leads tested (effective alpha 0.025/lead).
- Min net (after-fee) edge to take a simulated trade: 2¢.
- FIT window (bias/sigma calibration only, never touches Kalshi prices): 2026-04-24 → 2026-05-31 (38
  days).
- VALIDATION (OOS trading test) window: 2026-06-01 → 2026-07-20 (50 days), strictly after FIT, no
  overlap.
- Scope: 4 cities chosen for climate diversity before pulling any data — KDEN (semi-arid continental),
  KMIA (tropical), KSEA (marine), KPHX (desert). HIGH-temp series (`KXHIGH*`) only; LOW series and the
  other 16 house cities are out of scope for this cross-check (documented limitation, not a filtered
  result).

## Data sources and the look-ahead-safety design

- **Forecast**: Open-Meteo `previous-runs-api` (`ecmwf_ifs025`), a genuine archived-forecast-run
  product with per-hour lead tags — NOT reanalysis. Two leads:
  - `dayahead` = `temperature_2m_previous_day1` (~24h lead at every valid hour). Simulated entry:
    previous local evening 21:00.
  - `samemorning` = `temperature_2m` (Open-Meteo's "day0"/freshest-run value; ~0–9h lead for
    afternoon peak hours). Simulated entry: same-day local 09:00.
  Both entry timestamps precede the observed daily high and Kalshi settlement by construction; spot
  checks confirm the picked entry trade's `created_time` lands minutes after the intended entry
  threshold and hours before market close (e.g. KXHIGHDEN-26JUN03-B85.5: entry threshold
  2026-06-03T04:00Z, matched trade at 2026-06-03T05:24Z, market didn't close until 2026-06-04T06:59Z).
- **Truth for bias-fitting** (FIT window only, never used as a trading signal): Open-Meteo `archive-api`
  (ERA5) daily max temp.
- **Kalshi**: live `/events/{ticker}?with_nested_markets=true` for market metadata/strikes/results
  (352/352 city-days recovered, 0 misses), and `/markets/trades?ticker=...&min_ts=...&max_ts=...` for
  the REAL trade nearest-after each simulated entry timestamp (yes_price/no_price/taker_side/
  created_time from the actual tape, not mid/last). Entry-trade coverage: 1177/1200 (98.1%) dayahead,
  1193/1200 (99.4%) samemorning.
- **Fee**: `ceil(7*p*(1-p))/100` per contract at the entry price (house formula), charged on every
  simulated trade regardless of outcome.
- **Settlement**: `market.result` (`yes`/`no`), NO-side payoff = 100 − no_price, both sides accounted.
- **Strike-bucket semantics** (verified against live payloads, not assumed): B-markets (floor & cap
  both set) → YES iff floor ≤ temp ≤ cap (a 2-integer-degree bucket); T-market floor-only → YES iff
  temp > floor; T-market cap-only → YES iff temp < cap.
- **Clustering**: by settlement date (all 4 cities on the same calendar day share correlated synoptic
  weather) — day-cluster means, not raw per-trade SE.

## Why NOT true multi-member ensemble (important finding, not a shortcut)

Empirically re-verified 2026-07-23, independent of the informal note this task started from: the
`ensemble-api.open-meteo.com` **historical** path (`start_date`/`end_date` in the past, any
`past_days` value 1–100) returns **all-NULL** for every member of every ensemble model tested
(`ecmwf_ifs025`, `gfs_seamless`, `icon_seamless`, `gem_global`, `ecmwf_aifs025`,
`ukmo_global_ensemble_20km`) once the request reaches more than **~92 hours (3.8 days)** before the
call time — a hard retention wall, not a boundary-hours artifact. This directly contradicts the prior
note that historical ensemble "works, confirmed" — that confirmation was only ever exercised against
the live/near-term window, not a genuinely historical one. True multi-member ensemble history is not
obtainable from this free API far enough back to run any day-clustered OOS test.

Given that wall, this backtest substitutes a **fitted Gaussian** (bias-corrected deterministic
forecast ± FIT-window residual sigma, per city per lead) for the ensemble's probability distribution.
This is a real compromise, not a free lunch — see calibration results below, which show it is not a
clean stand-in for true ensemble spread.

## Results by lead

| Lead | N trades | N days | Mean PnL ¢/contract (day-avg) | 95% CI | Win rate (Wilson 95% CI) | Model Brier | Market-implied Brier |
|---|---|---|---|---|---|---|---|
| dayahead (~24h) | 756 | 50 | **−0.55¢** | [−3.70, +2.60] | 43.8% [40.3%, 47.3%] | 0.133 | **0.106** |
| samemorning (~0–9h) | 690 | 50 | **−0.59¢** | [−2.50, +1.31] | 37.8% [34.3%, 41.5%] | 0.122 | **0.049** |

Both CIs straddle zero comfortably (t-stats −0.34 and −0.61) — neither survives an uncorrected test,
let alone the pre-registered Bonferroni bar. **No edge at either lead**, and the point estimates agree
in sign (both slightly negative) — i.e. the null is *consistent* across leads, not lead-dependent
noise cancelling out.

**Market beats the model at both leads**: the Kalshi crossing price alone (used as an implied
probability) has a lower Brier score than our bias-corrected forecast + fitted Gaussian, especially at
the same-morning lead (market Brier 0.049 vs model 0.122 — the market has clearly absorbed intraday
information the pure forecast model doesn't have). This is the sanity/calibration check item (b) from
the assignment, and it comes out the "boring but correct" way: **Kalshi weather pricing is skillful and
efficient relative to this forecast-only model**, reinforcing rather than contradicting the earlier
finding this task was cross-checking.

## Calibration diagnostic (item b/c) — and an honest weakness in the substitute model

Reliability tables (model_p bin vs realized frequency) show the fitted-Gaussian model is
**overconfident in the middle-to-upper probability bins** at both leads — e.g. dayahead 0.4–0.6 bin:
model says avg 47%, realized 34%; 0.6–0.8 bin: model says 66%, realized 44%. The 0–0.2 bin runs the
other way (model underconfident on the extreme-unlikely side: says 5%, realized 9.5%). Net picture:
**the fitted sigma is too narrow** — the FIT-window residual std understates real forecast uncertainty
at the leads tested, so the substitute-for-ensemble probability model manufactures apparent "edge"
that isn't real, which the market correctly declines to pay for. This is exactly the failure mode a
true multi-member ensemble (properly dispersed) would have been more robust to — flagged here as a
limitation of the required substitution, not swept under the rug.

## Bias/sigma fit (FIT window, 38 days/city)

| City | Lead | Bias (°F, fcst−truth) | Sigma (°F) |
|---|---|---|---|
| KDEN | dayahead | −1.15 | 2.98 |
| KDEN | samemorning | −1.42 | 1.45 |
| KMIA | dayahead | −2.45 | 1.43 |
| KMIA | samemorning | −1.95 | 1.17 |
| KSEA | dayahead | −1.09 | 1.90 |
| KSEA | samemorning | −1.37 | 1.00 (floor) |
| KPHX | dayahead | −0.01 | 1.00 (floor) |
| KPHX | samemorning | −0.39 | 1.00 (floor) |

All four cities show a small consistent cold-bias in the archived ECMWF forecast vs ERA5 truth on this
window (forecast reads 0–2.5°F low); several sigmas hit the 1.0°F floor imposed in code, which is
itself a sign the 38-day FIT sample is thin for a low-noise station/lead pair (e.g. Phoenix same-
morning) and the true residual distribution likely has fatter tails than what 38 days can show —
another reason the model-vs-market Brier gap should not be over-read as "the model is simply bad,"
it's also under-sampled.

## Capacity — moot

With CI-null point estimates at both leads (−0.55¢ and −0.59¢/contract, both statistically
indistinguishable from zero), there is no positive EV to size. Nominal $/month at 1 contract/trade
(453.6 trades/mo dayahead, 414/mo samemorning) would be **≈ −$2.49/mo (dayahead)** and
**≈ −$2.46/mo (samemorning)** — i.e. near-zero and if anything negative. Capacity gates do not apply
to a null result.

## Self-doubt / limitations (explicit, not hedging)

1. **Scope is 4 of 20 cities, HIGH series only.** Chosen for climate diversity, decided before pulling
   data, but this is not the full house universe — a real edge concentrated in the other 16
   cities/LOW series would not show up here. This backtest cross-checks the *shape* of the claim
   (efficient market, no lead-dependent edge), not the full capacity surface.
2. **True ensemble members were unavailable beyond ~92 hours of history** on the free API (verified,
   not assumed) — the substituted fitted-Gaussian model is demonstrably imperfectly calibrated (see
   above), so this test is a lower bound on how good a *properly*-dispersed ensemble forecast could do
   against Kalshi, not a definitive ceiling. A paid/longer ensemble archive could tell a different
   story; this backtest cannot rule that out.
3. **FIT window is short (38 days, 1 per city-lead)** — bias/sigma point estimates come from a single
   spring window; a full-year fit would likely widen sigma (see the 1.0°F sigma floor hits above) and
   could change which trades clear the 2¢ net-edge bar, in either direction.
4. **Entry simulation uses a single fixed local clock time per lead** (21:00 previous evening /
   09:00 same day) rather than modeling the full intraday price path — a real trader might catch
   better or worse crossings intraday. The 8-hour lookahead window for "nearest trade after entry"
   is a simplification; 23/1200 (dayahead) and 7/1200 (samemorning) markets had no trade in that
   window and were dropped (not counted as losses or wins).
5. **Kalshi taker fee is applied on every simulated trade** including ones that would have been
   free/maker in reality — this is the correct conservative (house-mandated) convention, but it means
   the already-null result is if anything an upper bound on realizable edge, not a floor.
6. The two leads' point estimates are close in sign and magnitude (−0.55¢ vs −0.59¢) and their CIs
   overlap heavily — this cross-check found **no evidence of lead-dependence** in whatever
   near-null effect exists, which is itself informative (rules out a "the edge only shows up at a
   specific lead" story for this scope).

## Bottom line

Independent cross-check, different code path, different lead structure, different (forced) data
source than a "true ensemble" approach — and it lands in the same place the house prior expects:
**no edge, market efficient, and specifically better-calibrated than a forecast-only model at both
leads tested.** The one new, actionable finding from this run is technical rather than statistical:
**Open-Meteo's free historical ensemble-member archive is not usable beyond ~92 hours back**, which
should be corrected in any future study that assumed otherwise.
