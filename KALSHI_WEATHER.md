# Kalshi Weather Markets vs Free NOAA/NWS Forecasts — Mispricing Study

**Date:** 2026-06-14 · **Branch:** `claude/polymarket-bot-live-ready-vw7ut5`
**Question:** Are Kalshi daily high/low-temperature contracts mispriced versus the best free
probabilistic forecast guidance (NWS / National Blend of Models)? Is there a deployable,
can't-ban-you +EV edge that clears spread + fee, or is it efficient/thin like the dead crypto
box and the SIG-priced sports book?

**TL;DR verdict (honest):** There is a **real, structurally-plausible deviation** between Kalshi's
book and NBM-implied fair value — concentrated in the **bracket just above the modal bin and in
the warm tail**, the classic "recreational anchors on the forecast high, underweights the upside
distribution" signature. After fee + spread, ~12–15 brackets/day across 8 cities show a nominal
**+3 to +14¢ net** edge. **BUT this is NOT yet a proven edge:** a point-in-time snapshot cannot
distinguish "Kalshi is wrong" from "my NBM-normal model is wrong" — the largest apparent edges are
exactly where Kalshi *disagrees* with NBM, and only forward calibration data settles who is right.
The lag edge (Kalshi slow to follow NBM updates) is **near-zero for next-day** (NBM moves 0–1°F
intraday) and **near-zero same-day** (the book converges to live observations within the hour).
**Capacity is thin** (tens to low-hundreds of contracts at touch). This is a **modeling edge that
needs ~30–45 days of forward CLV/settlement data to confirm**, not a backtest-now slam dunk. It is
more promising than crypto (dead) and arguably softer than sports (SIG-priced), but the burden of
proof is calibration, and capacity caps it at hobby/small scale.

---

## 1. Inventory: Kalshi weather markets

Kalshi runs a large `Climate and Weather` category (281 series total via
`GET /series?category=Climate and Weather`). The tradable, daily, modelable temperature markets:

### Daily high-temperature series (one event per city per day)
| City | Series ticker | NWS office (CLI) | Settlement station |
|------|---------------|------------------|--------------------|
| New York | `KXHIGHNY` | OKX | Central Park (KNYC) |
| Chicago | `KXHIGHCHI` | LOT | Midway (KMDW) |
| Miami | `KXHIGHMIA` | MFL | Miami Intl (KMIA) |
| Austin | `KXHIGHAUS` | EWX | Austin (KAUS / Camp Mabry) |
| Los Angeles | `KXHIGHLAX` | LOX | LAX (KLAX) |
| Phoenix | `KXHIGHTPHX` | PSR | Phoenix (KPHX) |
| Dallas | `KXHIGHTDAL` | FWD | DFW (KDFW) |
| Boston | `KXHIGHTBOS` | BOX | Boston Logan (KBOS) |
| Denver, Houston, Seattle, SF, DC, Atlanta, Vegas, OKC, San Antonio, New Orleans, Phoenix, Death Valley, "US high", multi-city `KXCITIESWEATHER` … | various `KXHIGH*` / `KXHIGHT*` | | |

There are matching **daily LOW** series (`KXLOWT*`), **rain** (`KXRAIND`, `RAINNYC`, …), **snow**
(monthly), **hourly directional** temp (`KXTEMP*H`, `KXHIGHNYD`), and longer-horizon climate
series (monthly/annual). The daily high/low temp set is the sweet spot: solved-science forecast +
recreational flow + slow scheduled resolution.

### Contract structure
Each daily-high event (e.g. `KXHIGHNY-26JUN15`) is a **set of ~6 mutually-exclusive brackets**:
- Interior bins are **2°F wide**: `78° to 79°`, `80° to 81°`, … (floor/cap strikes on the API).
- Two **tail bins**: `77° or below`, `86° or above`.
- Settlement = the **integer high in the final NWS Daily Climate Report (CLI)** for the station,
  midnight-to-midnight **Local Standard Time** (note: during DST the window runs 1 AM → 12:59 AM).
  `fee_type: quadratic`, `fee_multiplier: 1`.

### Liquidity (live orderbooks, `GET /markets/{t}/orderbook` → `orderbook_fp`)
Books are genuinely two-sided. Representative tomorrow (`26JUN15`) snapshots, touch spread and
depth:
- **NYC**: spreads 1–5¢; depth 1–~350 contracts at touch (e.g. `80–81` bid 98 / ask 96).
- **Chicago**: spreads 1–5¢; depth single-digits to ~110.
- **Miami**: spreads 1–4¢; a 24,917-contract wall on the dead `86° or below` bin.
- **Austin**: spreads 1–5¢; tails 400–900 contracts deep, modal bins thin (1–5).
- **Sum of bracket mids = 99–105¢** → **overround ≈ 0–5%** (vig is small, occasionally <0).

**Capacity read:** you can place tens to low-hundreds of contracts per bracket near touch.
At ≤$1 stakes that is **hundreds to low-thousands of $ per city per day** before moving the book —
**thin**. Volume/OI fields are null on the public unauth `/markets` endpoint; orderbook depth is
the reliable proxy and it says "popular but small."

---

## 2. Fair-value model: NWS / NBM → calibrated P(bracket)

### Best free probabilistic input: NBM NBS text bulletin
The **National Blend of Models (NBM v5.0)** is NOAA's calibrated, post-processed blend and is the
backbone of NWS digital forecasts. The cleanest per-station probabilistic feed is the **NBS text
bulletin** on NOMADS, updated **hourly**:

```
https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/blend.YYYYMMDD/HH/text/blend_nbstx.tHHz
```
(`nbhtx` = hourly/short, `nbstx` = short to ~72 h, `nbetx`/`nbxtx` = extended.)

Per station the bulletin gives, every 3 h out to 72 h:
- **`TXN`** = the 18-h **max/min temperature** (°F) — i.e. the *calibrated forecast daily high*.
- **`XND`** = the **standard deviation of that max/min** (°F) — NBM's *own* calibrated spread.
- `TMP` (hourly temp) + `TSD` (hourly sd), plus precip prob `P06`, sky, wind, etc.

Parsing rule (validated): the **daytime high of local day D** is the `TXN` value at **UTC hour
`00`** whose `DT` day-label = D (the evening of D in UTC). `XND` at the same column is σ.
The deterministic high also matches `api.weather.gov` gridpoint `temperature` for the daytime
period (NWS = NBM-derived), but the API does **not** expose σ — so NBS is strictly better.

Backups: `api.weather.gov/gridpoints/{wfo}/{x},{y}/forecast` (point high, no σ); NBM QMD GRIB on
AWS Open Data / gribstream for full percentiles; `api.weather.gov/stations/{id}/observations` for
realized intraday max (settlement preview).

### From forecast to bracket probability
Model the realized integer high as **`high ~ Normal(μ = TXN, σ = XND)`** and integrate over each
bracket with a **±0.5°F rounding correction** (CLI reports whole degrees):

```
P(integer high in [a,b]) = Φ((b+0.5−μ)/σ) − Φ((a−0.5−μ)/σ)
tails:  "≤ n"  → Φ((n+0.5−μ)/σ);   "≥ n" → 1 − Φ((n−0.5−μ)/σ)
```

This is implemented in **`nbm_fairvalue.py`** / **`compare_kalshi_nbm.py`**. Observed σ matches the
literature: NWS day-ahead max-temp **standard deviation ≈ 1.6°F** in benign regimes, widening to
3–4°F under convective/frontal uncertainty — exactly the `XND` range we see (NYC 3, CHI 2, MIA 2,
AUS 3, DAL 3, PHX 2, LAX 1, BOS 3 for 26JUN15). The Normal is a defensible first approximation;
a skew/empirical-quantile refit from NBM QMD percentiles is the obvious upgrade.

---

## 3. The test: Kalshi book vs NBM fair value (point-in-time, 2026-06-14 20Z, target 06-15)

`compare_kalshi_nbm.py` output (NBM cycle 20Z; net columns from
`weather_clv_harness.py` analysis, **taker fee = 0.07·P·(1−P)**, maker = 0):

| City | NBM high / σ | Bracket | NBM % | K ask | **Taker net** | Maker net |
|------|--------------|---------|------:|------:|------:|------:|
| NYC | 80 / 3 | 80–81 | 25.8 | 17 | **+7.8** | +9.3 |
| NYC | 80 / 3 | 82–83 | 18.7 | 9 | **+8.7** | +12.2 |
| NYC | 80 / 3 | 84–85 | 8.8 | 3 | **+5.8** | +6.3 |
| CHI | 76 / 2 | 78–79 | 18.7 | 14 | +3.7 | +7.2 |
| MIA | 92 / 2 | 89–90 | 18.7 | 12 | +5.7 | +8.7 |
| AUS | 83 / 3 | 82 or below | 43.4 | 36 | +5.4 | +7.9 |
| LAX | 73 / 1 | 74–75 | 30.2 | 18 | **+11.2** | +13.2 |
| DAL | 84 / 3 | 86 or above | 30.9 | 16 | **+13.9** | +15.4 |
| BOS | 84 / 3 | 86 or above | 30.9 | 19 | **+10.9** | +12.4 |

And the **modal bins are tightly priced** — CHI `76–77` (NBM 37.2 vs mid 34.5), MIA `91–92`
(37.2 vs 39.5), PHX `108–109` (37.2 vs 39.5) all sit within ~1–3¢ of fair. **Kalshi is clearly
pricing off the same NWS/NBM guidance for the center of the distribution.**

**The deviation is systematic and directional:** Kalshi tends to **over-price its own modal/lower
brackets and under-price the bin just above the mode and the warm tail.** That is the textbook
recreational error — bettors anchor on the headline forecast high and under-weight the right side
of the temperature distribution.

**Critical honesty caveat:** every one of those green numbers presumes my `Normal(TXN, XND)` is
the true distribution. The biggest edges (NYC 82–83, DAL/BOS 86+, LAX 74–75) are precisely where
Kalshi *disagrees* with NBM, so they double as "places my model could be wrong." A snapshot cannot
adjudicate. Forward settlement data can — hence the harness.

### Lag diagnosis (does Kalshi trail public guidance?)
- **Next-day:** the NBM point high moved **0–1°F across the 16Z/18Z/20Z cycles** for all 8 cities.
  Day-ahead guidance is stable → **the "Kalshi slow to follow NBM updates" edge is near zero.**
- **Same-day:** today's NYC market (`KXHIGHNY-26JUN14`) had already converged to `87–88` bid at
  **99¢** while live KNYC obs showed 86°F at 18Z and still climbing. **The book tracks
  observations within the hour → no exploitable same-day lag in liquid books.**

---

## 4. Edge-source diagnosis

| Candidate source | Verdict |
|------------------|---------|
| (a) Kalshi lags NBM forecast **updates** | **Weak.** Day-ahead NBM barely moves; same-day book converges to live obs fast. |
| (b) Recreational **distribution/tail** mispricing | **Most likely.** Consistent over-weight of modal bin, under-weight of upside bin + warm tail across cities. |
| (c) None / efficient | Partly — the **center is efficient**; only the off-modal/tail brackets deviate. |

So the realistic edge is **(b): modeling the distribution better than recreational flow**, taken
mostly via **resting maker orders (0 fee)** in the off-modal and warm-tail brackets.

---

## 5. Forward test harness (what's needed to actually confirm)

`weather_clv_harness.py` logs, on a schedule (cron ~1–2 h), one row per (event, bracket):
`ts, city, station, event, bracket, lo, hi, nbm_high, nbm_sigma, nbm_p, k_yes_bid/ask/mid,
nbm_cycle`. A settlement pass joins the **NWS CLI actual high** and computes:
- **Calibration** of `nbm_p` (Brier / log-loss; reliability curve) — *is the model even right?*
- **Realized PnL** of the rule `BUY when nbm_p − ask − fee > THRESH`, settling 0/100.
- **CLV** = entry mid vs final pre-settlement mid (does the book drift our way?).

**Data needed for a verdict:** ≥ 150–300 settled buy-signals across **≥ 30–45 trading days and
≥ 6 cities**; tail-bracket stats need the long end (signals are rarer there). This is the same
discipline as the sports/Polymarket CLV studies — **not backtestable now** (no historical Kalshi
weather book archive on hand; NBS bulletins on NOMADS rotate off within days).

---

## 6. Verdict

**Is there a deployable +EV Kalshi weather edge?**
**Provisionally yes, unproven, small-capacity** — a genuine *candidate*, materially better than the
dead ends, but gated on forward calibration:

- **Markets:** daily HIGH temperature, off-modal + warm-tail brackets, in the 6–8 most liquid
  cities (NYC, CHI, MIA, AUS, LAX, PHX, DAL, BOS). Skip the modal bin (efficient) and rain/snow
  (lumpier).
- **Model:** NBM **NBS bulletin** `TXN` (high) + `XND` (σ) → `Normal(TXN, XND)` with ±0.5°F
  rounding → bracket probabilities. Upgrade to NBM-QMD empirical quantiles to capture skew.
- **Expected net (IF NBM is calibrated):** snapshot suggests **+3 to +14¢/contract** on flagged
  brackets after fee; realistically **assume far less (low-single-digit ¢)** until the harness
  confirms calibration and you discount for adverse selection on maker fills. Trade as **maker
  (0 fee)** to keep the edge.
- **Capacity:** **thin** — tens to low-hundreds of contracts at touch; hundreds to low-thousands
  of $/city/day. Hobby/small scale, not institutional.
- **Cadence:** daily, scheduled resolution → **escapes the crypto box's queue-death** entirely.
  US-legal, no auth needed to model.
- **Effort:** low. The full pipeline (Kalshi public API + NOMADS NBS + Normal model) is ~3 small
  scripts, already built here.

**vs the other boxes:**
- **Crypto box** — dead (efficient + queue-death). Weather is strictly better: slow resolution,
  recreational flow, a free calibrated model.
- **Sports / macro** — efficient / SIG-priced. Weather's *center* is similarly efficient, but the
  **off-modal & tail brackets show a consistent recreational deviation** sports books don't leave.
- **The honest gap:** weather forecasting is mature and Kalshi prices the mode off the same NBM, so
  the edge lives only in the distribution shape, must be taken as maker, and is **capacity-capped
  and calibration-gated.** Run the harness for 30–45 days before risking size.

---

### Files
- `kalshi_weather_snapshot.py` — inventory + book/liquidity snapshot per event.
- `nbm_fairvalue.py` — NBM NBS bulletin fetch/parse + Normal-bracket fair value.
- `compare_kalshi_nbm.py` — Kalshi book vs NBM deviation table (point-in-time).
- `weather_clv_harness.py` — forward CLV/calibration logger (run on cron; **do not commit the
  generated `weather_clv_log.csv`**).

### Sources
- Kalshi public API `https://api.elections.kalshi.com/trade-api/v2/` (`/series`, `/markets`,
  `/events`, `/markets/{t}/orderbook`); Kalshi weather help & fee schedule
  (`help.kalshi.com/markets/popular-markets/weather-markets`, `kalshi.com/docs/kalshi-fee-schedule.pdf`).
- NOAA NBM: `vlab.noaa.gov/web/mdl/nbm`, NBS text card; NOMADS
  `nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod/`; NBM QMD percentiles; AWS Open Data NBM.
- NWS API: `api.weather.gov` (`/points`, `/gridpoints/.../forecast`, `/stations/.../observations`).
- Day-ahead max-temp forecast error σ ≈ 1.6°F: NWS GFE verification literature (vlab.noaa.gov MDL).
