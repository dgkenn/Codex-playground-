# Phase-3 Daily Rain Sleeve — KXRAIN / KXRAIND / KXRAINSEA and the daily-rain family

**Question:** does the confirmed K-WX settlement-nowcast/lock mechanic (buy the ratchet-locked side
once the observable has mechanically decided the outcome, ahead of slow retail) extend to Kalshi's
*daily* (not monthly) rain markets, on deeper books, into a genuine second profitable sleeve? Prior
work already killed MONTHLY rain (`phase3_rain_sleeve.md`: DOA 96.5%, EV +0.005/ct — rain accumulates
over weeks, so by the time any observable confirms it the market has already repriced). This report
builds and backtests the DAILY-rain-specific version from scratch, live off the Kalshi API + IEM ASOS
present-weather data pulled 2026-07-18.

**Bottom line up front: NULL, but for the opposite reason monthly rain was NULL.** Monthly rain dies
because the lock is too *slow* to observe (days-to-weeks of accumulation). Daily rain's lock is real,
clean, and — confirmed here — the market's own repricing is *faster than we can act on it*: the book
closes the gap in **~1-2 minutes** of the earliest independently-observable confirmation, which is
tighter than the temperature sleeve's already-fast 3.3-minute half-life and (per a live example
below) sometimes faster than the fastest ground-truth precip signal that exists at all. At the
temperature sleeve's own 2-5 minute action-latency budget, the blended edge is statistically
indistinguishable from zero (t=0.30 at 2 min delay) and goes net negative past ~10 min.

---

## 1. The daily-rain product family — what actually exists, discovered live

Queried `/series/{ticker}` for every plausible daily-rain ticker, then pulled full settled history via
`/historical/markets` + `/markets?status=settled` (merged, de-duplicated):

| series | title | settlement source | settled markets found | live status (2026-07-18) |
|---|---|---|---|---|
| **KXRAIN** | "Where will it rain daily" (20 cities) | **The Weather Company** (`CLI<city>`, e.g. `CLINYC`) | **20** (2 event-days: Jul 15, Jul 17 only — Jul 16/18 don't exist) | **the current live product**, but only 2 days old in this environment |
| **KXRAIND** | "Rain Daily" | National Weather Service | **0** — zero markets, zero events, ever | metadata-only series, never launched |
| **KXRAINSEA** | Seattle rain | NWS Daily Climate Report | 347 (`RAINSEA-*` ticker prefix) | **dead since 2022-05-31**; no market since |
| **KXRAINNYC** | NYC rain | NWS CLI Daily Report (legacy) | **551**, continuous **2025-01-04 → 2026-07-15** | **just retired** — last settlement was the day before KXRAIN(multi-city) launched; clearly the predecessor product KXRAIN replaced |
| **KXRAINHOU** | Houston rain | NWS | 1 (from 2021-09-14) | dead |
| **KXRAINMIA** | Miami rain | AccuWeather | 0 | metadata-only, never launched |

**Two of the six named/discoverable series (`KXRAIND`, `KXRAINMIA`) have literally never listed a
single market** despite existing as registered series — a concrete, honest finding worth stating
plainly since the task named `KXRAIND` explicitly. `KXRAINSEA`/`KXRAINHOU` are historical relics from
Kalshi's 2021-2022 pre-"KX" era, dead for 4+ years. **`KXRAINNYC` is the only daily-rain product with
real, deep, current-through-3-days-ago history**, and it was retired on exactly the day the new
multi-city `KXRAIN` launched (2026-07-15) — a clean product hand-off, not a gap. Given `KXRAIN` itself
has only 2 event-days ever (and hasn't run on 2 of the last 4 calendar days, so it is not yet reliably
"daily" in practice), **`KXRAINNYC`'s 551-day run is used here as the structural proxy** for the same
underlying mechanic — same city (NYC/Central Park), same "any measurable precip locks YES" logic —
with one material rules difference flagged below.

## 2. Settlement definition — confirmed exactly, and a rules nuance that matters a lot

- **`KXRAIN` (current, live)**: *"If the total precipitation at CLI\<city\> in \<City\> on \<date\> is
  strictly greater than 0 inches, then the market resolves to Yes."* Source = The Weather Company.
  Rules explicitly state: **"'Trace' amounts (T) and missing daily precipitation values are counted as
  0 inches"** — i.e. trace precip does **NOT** lock YES; a genuine ≥0.01in measurable reading is
  required.
- **`KXRAINNYC` (legacy, 551-day backtest base)**: *"If the number of inches of precipitation recorded
  at Central Park, New York on \<date\> is strictly greater than 0..."* Source = NWS CLI Daily Report.
  Rules state: **"If the Expiration Value is T (Trace)... then the market resolves to Yes."** — trace
  precip **DOES** lock YES here.

This is a real, non-obvious difference between the retired product (used for the large-n backtest)
and the live product (what you'd actually deploy against): the fastest legitimate signal on
`KXRAINNYC` could fire on the very first trace reading; on the live `KXRAIN` it must wait for an actual
≥0.01in accumulation. **This makes the live product's fastest available signal somewhat slower than
what is backtested below** — a headwind on top of an edge that (see §4) is already razor-thin.

`can_close_early: true` and a 30-min `settlement_timer_seconds` apply to both — Kalshi's own system can
close the market early once it detects the event, similar to the monthly-rain finding, though in the
one detailed intraday example examined (§4), the market did NOT close early; it traded a full,
observable repricing curve through the day.

## 3. The fast signal, built and tested: METAR present-weather codes + trace/measurable precip

Built off IEM's ASOS request API (`mesonet.agron.iastate.edu/cgi-bin/request/asos.py`,
`data=p01i,wxcodes`) — the same class of infra as `aviationweather_metar.py`, extended to parse present-
weather type codes (RA/SN/DZ/PL/GR/GS/IC/UP) and the hourly precip-accumulation field, including
explicit trace (`T`) handling. Cadence reality-checked directly: **NYC/Central Park's ASOS reports at
routine hourly cadence (`:51` past the hour) plus SPECI reports triggered by significant-weather onset**
— confirmed a real SPECI-triggered mid-hour report on 2026-07-15 (`21:11 UTC, "+RA BR", 0.11in`).
Seattle's station additionally carries a finer (~5-min) present-weather feed; NYC does not — station
cadence varies and this was verified empirically, not assumed.

**Signal fired 207 times across the 551-day KXRAINNYC history** (first of: rain-type wxcode, trace
reading, or ≥0.01in measurable reading, per calendar LST day, America/New_York with real DST).

**False-lock rate: 1/207 (0.48%).** One case, `KXRAINNYC-26APR15-T0` — a `trace` signal fired but the
market settled NO (ask stayed at 0.26, never repriced up, confirming the signal itself was the
anomaly, not a late market). This is dramatically cleaner than the prior scan's naive-accumulation-
threshold signal (which found 18.5% ASOS-vs-official disagreement) — the present-weather-code /
trace-aware signal is the right one to use, and materially reduces tail risk relative to raw
accumulation summing.

**Missed-fire rate:** 43/249 actual rain-days (17.3%) had no wxcode/trace/measurable signal at all in
the IEM feed, concentrated in winter months (likely snow-reporting/sensor-icing artifacts) — a real
gap in signal coverage, though it only costs fire frequency, not correctness (we simply don't trade
those days).

## 4. The crux: is there a capturable intraday lag, or is it DOA? — **DOA, once realistic latency is added**

Pulled Kalshi 1-minute candlesticks (via `/historical/markets/{ticker}/candlesticks` for the pre-live-
window era, `/series/KXRAINNYC/markets/{ticker}/candlesticks` for the last ~65 days — confirmed the
candlestick API only serves a rolling ~65-70 day live window, same boundary found in prior weather
studies) around each of the 207 signal-fire timestamps. Fee model: `0.07 * p * (1-p)`/contract
(consistent with the confirmed temp sleeve).

**At theoretical instant (zero-delay) execution — looks promising:**

| sample | n (exec ask found) | win% | DOA% (ask≥0.98) | blended EV/ct | t | non-DOA n | non-DOA EV/ct |
|---|---|---|---|---|---|---|---|
| Full history (2025-01→2026-07) | 184 | 99.5% | 81.5% | +0.0332 | 4.02 | 34 | +0.1715 |
| 2026-only (deepest-book era) | 90 | 98.9% | 72.2% | +0.0547 | 3.59 | 25 | +0.1920 |
| 2026-04+ (most recent, most liquid) | 53 | 98.1% | 69.8% | +0.0599 | 2.68 | 16 | +0.1939 |

This alone would look like a real, temp-sleeve-grade edge (+0.15-0.20/ct on the non-DOA tail,
comparable to the confirmed temp margin=2°F result) — **and this is exactly why this had to be
stress-tested with a realistic action-latency delay before trusting it**, the same discipline the temp
study applies via its gap-decay sensitivity tables.

**Delay sweep (2026-only sample, n=90) — the honest result:**

| action delay | n | win% | DOA% | mean ask | blended EV/ct | t | non-DOA n | non-DOA EV/ct | non-DOA win% |
|---|---|---|---|---|---|---|---|---|---|
| 0 min (unrealistic) | 90 | 98.9% | 72.2% | 0.932 | **+0.0547** | 3.59 | 25 | +0.1920 | 96.0% |
| 1 min | 90 | 98.9% | 84.4% | 0.962 | +0.0254 | 2.44 | 14 | +0.1551 | 92.9% |
| **2 min** | 89 | 98.9% | 96.6% | 0.987 | **+0.0014** | **0.30 (n.s.)** | 3 | +0.0165 | 66.7% |
| 3 min | 87 | 98.9% | 96.6% | 0.987 | +0.0014 | 0.30 | 3 | +0.0165 | 66.7% |
| 5 min | 85 | 98.8% | 96.5% | 0.986 | +0.0015 | 0.30 | 3 | +0.0165 | 66.7% |
| 10 min | 79 | 98.7% | 96.2% | 0.993 | **-0.0061** | -0.50 | 3 | **-0.1815** | 66.7% |
| 15 min | 76 | 98.7% | 96.1% | 0.990 | -0.0039 | -0.36 | 3 | -0.1240 | 66.7% |

**The edge is gone by 2 minutes and is already the temp sleeve's own action-latency floor.** DOA jumps
from 72% to 97% between 0 and 2 minutes of delay; the tradeable non-DOA population collapses from 25
events to 3; the one false lock (§3) is inside that surviving-3 set, so its win rate craters to 67% and
its EV goes negative past 10 minutes. At the temp sleeve's realistic 2-5 minute action-latency budget
— the SAME infra/discipline this task explicitly asked to reuse — **daily rain's blended edge is
statistically indistinguishable from zero (t=0.30) and trends negative, not the confirmed +0.15-
0.20/ct.**

**A live, current-product anecdote makes the mechanism concrete** (`KXRAIN-26JUL15-NYC`, the actual
live product, 1-minute candles pulled directly):

```
20:00 UTC  ask=0.44  (pre-rain, forecast-based pricing)
20:34      ask=0.84  <- starts climbing well before any rain confirmation
20:48      ask=0.98  <- ALREADY at 98c
21:11      -- SPECI report hits the wire: "+RA BR", p01i=0.11in -- the fastest possible
              independent ground-truth confirmation, 23 MINUTES after the market was already at 98c
21:15      ask=1.00  vol=1,020 contracts print exactly at the crossing to full lock
```

The market reprices off something faster than any station-observation feed — almost certainly live
radar/nowcasting, which lets anyone watching a weather app literally see the storm approaching before
the rain gauge gets wet. This is the structural reason daily rain fails differently from monthly rain:
monthly rain is DOA because the observable is *slow* (multi-week accumulation gives forecasters weeks
to reprice); daily rain is DOA because the observable, even the fastest ground-truth version
buildable from public station data, is *slower than radar-based market participants*, not because
accumulation itself is slow.

## 5. History depth & volume — is it genuinely higher-volume than temperature? **Not on a fair comparison.**

- `KXRAIN`'s 20-city debut day (2026-07-15) traded 302-7,411 contracts per city (`vol24h_fp` field),
  NYC highest at 6,959 contracts (~$3-4k notional at the day's blended price).
- A **single** `KXHIGHNY` temperature strike on an ordinary day (2026-07-16/17, spot-checked) traded
  **8,000 to 103,765 contracts** — and a temperature city-day has **6-8 tradeable rungs simultaneously**
  (T-strikes and B-brackets), so aggregate temp-ladder volume per city-day is easily an order of
  magnitude above a single rain market's whole-day volume.
- On a like-for-like "one instrument we'd actually trade" basis, daily rain's book is **comparable to,
  or thinner than, a single temperature rung** — not the "genuinely higher volume" premise the task
  hypothesized. (Monthly rain ladders, by contrast, WERE confirmed deeper than temp in the prior
  report — $130-4,200/rung sweepable vs weather's $10-90 — but that finding does not transfer to the
  daily product.)
- Fillability check on the surviving delay=1min non-DOA events: most had real 5-minute post-signal
  volume (175-2,753 contracts), a couple were thin (1-12 contracts), and the one false lock had zero
  post-signal volume — so where the edge nominally exists, size is generally fillable; the binding
  constraint is time, not depth.

## 6. Diversification vs the temperature sleeve

Matched 61 NYC city-days (2026-05-12 to 2026-07-16, the overlap of the temp-sleeve's fired-cell log and
the rain-signal window) comparing rain occurrence to same-city-day temp-sleeve fire counts (all
margin/sustain configs pooled): rainy days (n=32) mean 34.16 temp fires/day vs dry days (n=29) mean
32.52/day. **Correlation(rain occurrence, temp-sleeve fire count) = +0.045** — essentially null, same
conclusion as the monthly-rain report (weak-positive-to-null, no meaningful drawdown-smoothing or
cannibalization either way).

## 7. VERDICT

**NULL for a deployable daily-rain sleeve at the temp sleeve's own action-latency budget — and the
task's core premises don't hold up under test:**

1. **The lock mechanic is real** and the settlement basis is now concretely nailed down per series
   (§2), including a material, previously-undocumented rules difference (trace=YES legacy vs
   trace=NO on the live product) that matters for anyone trying to build this.
2. **The clean, independently-observed fast signal was built and validated at a 0.48% false-lock
   rate** (1/207) — a major improvement over the prior scan's naive-threshold signal (18.5%
   disagreement) — so the "build a real precip feed, don't trust Kalshi's own price" part of the
   hypothesis succeeded.
3. **The DOA/capturable-lag question has a clean, honest answer, and it's DOA — for a new reason.**
   Unlike monthly rain (DOA because the observable is too slow), daily rain is DOA because the
   observable, even built as fast as public station data allows, **loses a race that closes in ~1-2
   minutes** to market participants who are almost certainly trading off real-time radar. At 0-1 min
   of (unrealistic) latency there IS a real, t>2, non-DOA edge (+0.15-0.20/ct) — but it evaporates to
   statistical noise (t=0.30) by 2 minutes and goes net negative by 10 minutes, and the temp sleeve's
   own proven, realistic action-latency budget is 2-5 minutes. **This edge does not survive contact
   with the same latency discipline that makes the temperature sleeve real.**
4. **"Deeper/higher-volume books than temperature" is not supported** on a fair per-instrument
   comparison — a single rain market's day is comparable-to-thinner than a single temperature rung,
   and much thinner than a temperature city-day's full multi-rung ladder.
5. **Diversification is null**, matching the monthly-rain finding (not harmful, not helpful).
6. **Product-family reality check**: the specific tickers named in the task (`KXRAIND`) have never
   listed a market; `KXRAINSEA` has been dead since 2022; the live `KXRAIN` multi-city product has
   exactly 2 event-days of history total as of 2026-07-18 and isn't yet reliably running daily. The
   only usable large-n dataset is the just-retired `KXRAINNYC`, used here as a structural proxy with
   its limitations flagged throughout.

**Do not deploy capital against daily rain as specified.** If this is revisited, the honest next step
is not more backtesting on station-observation data — it is a fundamentally faster (sub-1-minute,
likely direct radar/MRMS composite or a paid low-latency present-weather feed) signal class, since the
finding here is that the *existing* infra style (METAR/ASOS polling, even present-weather-code-
accelerated) is structurally too slow for daily rain's ~1-2 minute repricing window, not that the
mechanic itself is absent.

---

*Data and code: live Kalshi API + IEM ASOS pulls, 2026-07-18. Scratch files (not committed) under
`/tmp/.../scratchpad/`: `rain_markets_raw.json` (series discovery), `nyc_wx_full.csv` (472-day IEM
wxcodes/precip pull), `nyc_signals_local.json` (parsed signal timestamps), `nyc_merged.json`
(signal↔settlement join), `nyc_backtest_results_final.json` / `delay_sweep_results.json` (candlestick
backtest + latency-sweep, n=207 fires / n=90 2026-subset × 7 delays).*
