# SPEC S3 — BUILD B (independent replication)

**ForecastEx daily-temperature lock study: false-lock rate + flat-fee EV on the venue's own trade tape**

Script: `venue_expansion/spec_S3_B.py` (read-only). Full machine-readable output:
`venue_expansion/out/spec_S3_B.json`. This build did not read `venue_expansion/spec_S3.py` or any
`spec_S3_A.*` file at any point — station mapping, timezone handling, CSV parsing, the tape/settlement
join, the lock walk, and all statistics below were written independently from the task spec text.

## VERDICT: **KILL**

**190 false locks out of 8,646 resolvable locks (2.20%, Wilson upper bound at z=2.128 = 2.56%)** —
both above the pass bar (≤1 false lock, UB≤2.5%) and past the pre-registered hard kill (**>4 false
locks ⇒ "basis to WU settlement unsound, stop pricing, publish the basis failure"**). Per the spec's
own instruction, pricing/EV is **not** treated as a survivor once this fires; the EV numbers below are
reported for transparency only and are explicitly flagged as untrustworthy for the same reason the
false-lock rate is high.

This is diagnosed below (not just measured) as a **structural feed-cadence mismatch**, not a code bug:
ForecastEx settles on Weather Underground, which — per the venue's own notice — sources US airport data
from **METAR** (routine ~hourly-cadence reports), while the lock **signal** in this spec is drawn from
IEM's **true 1-minute** ASOS archive. A temperature excursion that is genuinely sustained for 3+ minutes
in the 1-minute record can be invisible to WU/METAR if it does not coincide with a routine or SPECI
report. The false-lock rate is monotonically decreasing in the observed cushion above the lock margin
and is **exactly 0% for every lock with cushion ≥5°F** (see §5) — the textbook signature of a
measurement-basis mismatch concentrated at the boundary, not a random-bug fingerprint.

---

## 1. Order of operations followed (per spec)

1. Station mapping verified from the venue's own product catalog (§2).
2. `asos1min` inclusion guard run over the full window (§3): **9/10 candidate stations pass**; KBKF
   (Denver) fails cleanly (0 obs on all 160 days) — see §3.
3. Early tripwire, price-only, computed **before** any settlement/outcome data was read (§4): median
   first-fill-after-lock price over the first 30 days = **96.0c**, well under the 98.5c kill threshold,
   so the full pull proceeded.
4. Full-window pull + false-lock/EV computation (§5–§7).

---

## 2. Station mapping — source and verification

GROUNDING asserted that "the contract terms PDF (`fx_daily_temp.pdf`) and the per-product filings under
`product_filings/` name the Weather Underground station." We read `fx_daily_temp.pdf` in full (all 6
pages, extracted via `pypdf`) and enumerated all 255 keys under `product_filings/`: **neither contains a
per-city station table.** The PDF is generic CFTC Rule 40.2(a) boilerplate ("the Underlying can be
accessed here [a link to wunderground.com's search], … users may use the search bar to locate the
relevant city and weather station"). `product_filings/Daily Temperature Forecast Contract.pdf` is the
same document. This is disclosed as a divergence from the literal orchestrator claim, not silently
worked around.

The per-city station **is** published, authoritatively and explicitly, by ForecastEx's own live
product-catalog API — `GET https://forecastex.com/api/products` (paginated, cached under
`cache/forecastex/api_products/products_p*.json`, 127 pages / 1015 products). Each Daily-Temperature
product's `description` field states the exact station, e.g. for `UHATL`:

> "The daily temperature high in Atlanta, GA as reported by the Weather Underground for the
> Hartsfield-Jackson Atlanta Intl Airport Station (KATL)."

`build_station_map()` parses this field with a regex (`Station \(K([A-Z0-9]+)\)`) rather than hand-typing
the mapping, so it is reproducible from the cached JSON on disk. This is what catches the Denver trap
GROUNDING warned about: `UHBKF`'s description says **"Buckley Space Force Base Station (KBKF)"** — not
Denver International (KDEN). We also cross-checked `notices_to_members/NTM_2026-45` ("Changing Source
Agency for Daily Temperature Contracts", Feb 10 2026): it confirms the WU/METAR switch effective for
contracts referencing Feb 11, 2026 onward (consistent with the corrected Feb 17 window start) but, like
the PDF, gives no per-city list — the live API is the only source that does.

Verified mapping for all 10 candidate stations (candidates = exactly the cities named in the
orchestrator's own verified "CITY VOLUME" list, fixed before any lock/tape data was read here):

| ticker (bare) | ICAO | city (per venue) | tz used | UH product | UL product |
|---|---|---|---|---|---|
| LAX | KLAX | Los Angeles | America/Los_Angeles | UHLAX | ULLAX |
| LAS | KLAS | Las Vegas | America/Los_Angeles | UHLAS | ULLAS |
| LGA | KLGA | New York City | America/New_York | UHLGA | ULLGA |
| SEA | KSEA | Seattle | America/Los_Angeles | UHSEA | ULSEA |
| SFO | KSFO | San Francisco | America/Los_Angeles | UHSFO | ULSFO |
| MIA | KMIA | Miami | America/New_York | UHMIA | ULMIA |
| PHX | KPHX | Phoenix | America/Phoenix | UHPHX | ULPHX |
| MDW | KMDW | Chicago | America/Chicago | UHMDW | ULMDW |
| AUS | KAUS | Austin | America/Chicago | UHAUS | ULAUS |
| BKF | KBKF | **Denver** (Buckley SFB, not KDEN) | America/Denver | UHBKF | ULBKF |

IANA timezones are standard geography for each airport (not an API field); they determine both (a) the
local calendar day the lock walk runs on, and (b) how the ticker's embedded `MMDDYY` is interpreted (see
§4 worked example).

---

## 3. Inclusion guard (asos1min, mechanical, pre-registered)

Station enters iff IEM `asos1min.py` returns ≥100 obs on ≥70% of the 160 window days
(2026-02-17..2026-07-26), counted on the **station's own local calendar day** (not UTC).

| station | days ≥100 obs | frac | verdict |
|---|---:|---:|---|
| LAX | 144/160 | 90.0% | PASS |
| LAS | 155/160 | 96.9% | PASS |
| LGA | 150/160 | 93.8% | PASS |
| SEA | 157/160 | 98.1% | PASS |
| SFO | 155/160 | 96.9% | PASS |
| MIA | 145/160 | 90.6% | PASS |
| PHX | 150/160 | 93.8% | PASS |
| MDW | 158/160 | 98.8% | PASS |
| AUS | 127/160 | 79.4% | PASS |
| **BKF** | **0/160** | **0.0%** | **FAIL** |

**9/10 stations survive** (≥2 required — not a kill). BKF fails cleanly, not marginally: 0 rows on all
160 days, confirmed via 3 separate spot-checked dates directly against the live endpoint (not a caching
artifact), while KBKF's **routine hourly** METAR archive (`asos.py`) *does* return normal data for the
same dates — i.e., KBKF is a real reporting station, it is simply outside IEM's true-1-minute network
entirely. This independently corroborates GROUNDING's warning not to guess Denver's station: the venue's
own choice of station (Buckley SFB over Denver Intl) turns out to also be the one station this signal
feed cannot serve at all.

Data source note: this repo already had a raw IEM-1min cache
(`venue_expansion/cache/forecastex_study/iem1min_<station>_*.json`) covering all 10 candidate stations
for most/all of the window, left on disk from earlier probing. This is public NOAA/IEM observation data,
not another build's analysis — reused read-only per "cache aggressively, never re-pull," with only the
missing tail (through 2026-07-26/27) fetched fresh into this build's own cache
(`venue_expansion/cache/spec_S3_B/`). In the event, the legacy cache fully covered the entire window for
all 10 stations, so **zero fresh IEM network calls were needed** for the guard itself.

---

## 4. Timezone / date-alignment handling — worked example

Three independent date/time representations are in play and were kept explicit throughout: (a) the
ticker's embedded `MMDDYY` (the station's own local observation date, per the venue's question text —
"Will the highest temperature in \<city\> … on \<date\>?"), (b) `pair_time`/`expiration_date` in the tape
(carry explicit `-05:00`/`-06:00` CT offsets), and (c) the pairs/prices **file name** date (verified
**not** equal to either of the above — see the DATE ALIGNMENT TRAP note in the task spec, confirmed
empirically below).

**Worked example — UHSFO_072126_81** (SFO, ticker date `072126` = 2026-07-21):

- SFO's IANA tz is `America/Los_Angeles`. The station's local day runs 2026-07-21T00:00 PDT (`07:00Z`)
  to 2026-07-22T00:00 PDT (`07:00Z` next day) — this is the exact UTC slice `run_lock_walk_for_station_day`
  uses for the 1-minute obs walk, **not** any file-date-derived window.
- `expiration_date` on both the pairs and prices rows for this ticker is `2026-07-22T03:00:00-05:00`
  (CT). Converting: 03:00 CDT (UTC-5) = 08:00 UTC = 01:00 PDT — i.e. resolution fires ~1 hour after SFO's
  own local midnight (00:00 PDT July 22, the instant the observation day ends), consistent with the
  contract's own "Resolution Time: the time at which the first temperature observation for any
  subsequent calendar day is published." Because Pacific is 2h behind Central, the *end* of Pacific
  calendar day D is, in CT, already calendar day D+1 — so **every** SFO contract's `expiration_date` CT
  calendar date is one day ahead of its own ticker date. This is a real, provable arithmetic fact, not
  file-naming noise.
- The pairs tape file is bucketed by the **CT calendar date of `expiration_date`**, not by the fill's own
  date and not by the ticker's own date: `pairs_20260722.csv` contains this ticker's fills, and directly
  inspecting `pair_time` values in that file shows both `2026-07-21` (the afternoon before) and
  `2026-07-22` (up to expiration) timestamps mixed together. We therefore never assume file date ==
  observation date == fill date; the fills index is built by scanning a **padded range of daily files**
  (window start −1 day .. window end +2 days for pairs, +6 days for prices) and joining purely on
  `event_contract`, exactly as instructed.
- The prices file's own `date` column is a third, independent thing again: it is the **trading/session
  day** the row's OHLC bar covers, not the ticker's date and not necessarily the settlement date — see
  §6 for why this matters and how the true settlement row is identified.

For Central-time stations (MDW, AUS), the station's own local midnight already **is** CT midnight, so the
CT expiration date is always ticker-date+1 too (resolution fires shortly after any local midnight,
pushing into the next calendar date regardless of which timezone you read the clock in). For Eastern
stations (LGA, MIA), Eastern local midnight converts to ~23:00 the *previous* CT calendar day, putting
the CT expiration date right at the boundary (same day or +1, depending on the exact publish-delay
minutes) — this is exactly why the join is done by scanning a padded file range and matching on
`event_contract`, rather than by deriving a single predicted file per ticker from arithmetic.

---

## 5. False-lock rate (== the WU settlement basis-risk measurement)

**Signal**: `kwx_lock_rule.sustained_extreme` / `locked_orders`, called byte-verbatim (MARGIN_F=1.0F,
SUSTAIN_MIN=3, glitch bounds unmodified), on obs only. One divergence, disclosed: `locked_orders` also
bundles a **price gate** (`yes_ask_c`/`no_ask_c` must be ≤98¢) into the same function as the geometric
margin/sustain decision. The spec's entry_rule requires "signal uses obs ONLY; no tape, no price, no
outcome input" and names only MARGIN_F/sustain-3/glitch-bounds as the parameters to reuse verbatim — so
every rung is passed a placeholder `yes_ask_c=no_ask_c=1` (always ≤98, always truthy), which structurally
disables the price gate without touching any of the sustain-3/margin/glitch math. **Performance note**
(no effect on results, verified below): rather than call `sustained_extreme` once per minute of the day
(~1440 calls/day, itself O(n) each, i.e. O(n²) overall — this did not finish in reasonable time on the
naive implementation), the harness exploits that `sustained_extreme`'s return value is monotonic
non-decreasing (max) / non-increasing (min) in the length of the obs prefix, and binary-searches, per
rung, for the first prefix index at which the byte-verbatim function's own return value crosses that
rung's threshold. This was checked against the naive per-minute walk on a spot-checked station-day
(SFO 2026-07-21): **identical fires, identical lock timestamps, identical extreme values** — the
optimization only reduces how many times the frozen function is called, not what it computes.

Lock decision uses ONLY the strike parsed out of the ticker string (`UH<city>_<MMDDYY>_<strike>` /
`UL<city>_<MMDDYY>_<strike>`) — never a price field — as the rung's floor/cap.

**Settlement**: taken from `prices/daily_prices_YYYYMMDD.csv`'s `settlement_price` field, per
GROUNDING's "use the venue's settlement_price field as ground truth" rule — but only from the row where
**`open_interest == 0`**. This is not optional bookkeeping: the *same ticker's* row on its own trading
day carries a **provisional, non-final** `settlement_price` while `open_interest` is still nonzero (e.g.
`UHSFO_072126_81` shows `settlement_price=0.83, open_interest=4632` in the 07-21 file), and only flips
to the true `1.00`/`0.00` once `open_interest` hits 0 in a later file (the 07-22 file: `settlement_price
=1.00, open_interest=0`). Using the trading-day row's value directly — exactly the class of "decide the
outcome yourself" error the audit found in the paper-trader's Bug 2 — would silently corrupt every
false-lock/EV number. We verified this is not spurious with an independent check: on the day this
mechanism was exercised (SFO 2026-07-21), the raw IEM 1-minute max was **93°F**, and ALL 14 strikes
listed that day (74–87) settled YES, matching the real observed heat spike, not an artifact.

**Result**, full window (2026-02-17..2026-07-26), 9 surviving stations:

- 8,675 total lock fires; 99 station-day skips (thin obs); 29 lock records excluded because no
  `open_interest==0` row was found in the pulled range (mostly contracts observing at the very end of
  the window whose settlement finalizes after 2026-07-29, "today," which is beyond what could be pulled)
  — disclosed, not silently dropped.
- **8,646 resolvable locks. 190 false (2.198%). Wilson upper bound (z=2.128, one-sided 98.33%,
  Bonferroni-3) = 2.559%.**
- Both fail the pass bar (≤1 false lock, UB≤2.5%) and trip the hard kill (>4 false locks).

**Diagnosis, not just measurement** — every false lock's `cushion_f` (how many °F the observed extreme
cleared the strike, beyond the 1°F margin) was inspected:

| cushion (°F) | total locks | false | false rate |
|---:|---:|---:|---:|
| 2 | 7,611 | 179 | 2.35% |
| 3 | 480 | 9 | 1.88% |
| 4 | 245 | 2 | 0.82% |
| 5 | 129 | 0 | 0.00% |
| 6 | 72 | 0 | 0.00% |
| 7 | 44 | 0 | 0.00% |
| ≥8 | 65 | 0 | 0.00% |

False-lock rate falls monotonically with cushion and is **exactly zero for every lock ≥5°F past
margin** — the signature of a measurement-basis mismatch concentrated at the boundary, not a random
implementation bug (a bug would not produce a clean monotone cushion gradient). A concrete example
(cushion=2, the modal false-lock case): KLAX 2026-02-23 — the raw IEM 1-minute feed shows a **12-minute
sustained** reading of exactly 74.0°F (18:34–18:47Z, safely inside the local day, confirmed via the
independently-recomputed raw max, not just the sustain-filtered value), which mechanically locks
`UHLAX_022326_72` YES (74 > 72+1). ForecastEx's own settlement, read from the `open_interest==0` row,
disagrees: `UHLAX_022326_71` settled YES and `UHLAX_022326_72` settled NO, i.e. WU's officially reported
daily high for that station/date was exactly 72°F — two degrees below what the true 1-minute archive
shows was sustained for over ten minutes. The mechanistic explanation is published by the venue itself:
`notices_to_members/NTM_2026-45` states that for US airport locations, "Weather Underground relies on
Meteorological Aerodrome Reports ('METAR')" — i.e. the *routine*, roughly-hourly (plus SPECI)
cadence — as its source, not a continuous 1-minute record. A brief-but-genuinely-sustained excursion
that does not happen to fall inside a routine or SPECI report is structurally invisible to WU, and
therefore to ForecastEx's settlement, even though it is fully real and fully sustained in the 1-minute
archive the lock signal is built on. **This is exactly the basis-risk measurement the false-lock rate
exists to make, and on ForecastEx it comes back materially non-zero (unlike the Polymarket Chicago
whitelist's 0/745)** — a genuine, structural, disclosed negative finding for this venue's version of the
mechanism, not an artifact of this build's code.

---

## 6. Early tripwire (price-only, pre-registered gate before the full pull)

First 30 window days (2026-02-17..2026-03-18), all 9 surviving stations, **settlement/outcome files were
not read at this step** — only obs (for the lock signal) and the pairs tape (for the raw first-fill
price). 795 locks, 478 tradeable (fill within 60 min). **Median first-fill-after-lock price = 96.0¢**,
well under the 98.5¢ kill threshold, so the full pull proceeded per spec.

---

## 7. EV — reported for transparency ONLY; NOT a survivor, per the spec's own "stop pricing" instruction

Because the false-lock kill fired, this EV is **not evidence of an edge**. It is reported because it was
already computed as part of the same run and hiding it would be worse than showing it clearly labeled.
Entry = first pairs-tape fill with `pair_time ≥ lock_utc` (untradeable if none within 60 min — 66.99% of
locks were untradeable by this rule, i.e. the tape rarely offers a fill in the first hour after a lock);
entry price = that fill's own `yes_price` (never derived from the NO side); net EV = payout − fill_price
− 1.0¢ slippage − 1.0¢ fee.

- n_priced = 2,854; station-day clusters = 1,028; stations = 9.
- Mean net EV = **+9.20¢/contract**, station-day-clustered t = **15.42** (calendar-day sensitivity:
  t=16.68, C=158 calendar-day clusters) — a number far outside anything plausible for a fee-cleared
  mechanical edge, and consistent with contamination from the same basis mismatch documented in §5:
  splitting by cushion, mean net EV is +9.11¢ (cushion=2, n=2,691) vs +10.68¢ (cushion≥3, n=163) — i.e.
  the inflated EV is **not** confined to the boundary-mismatch population, meaning it likely also
  reflects genuine tape-vs-settlement lag broadly, which is exactly the mechanism this study cannot
  responsibly price once the settlement basis itself has failed its own check. Per spec: stop pricing.

---

## 8. Divergences from a literal reading of the spec, all disclosed above

1. Window corrected to 2026-02-17..2026-07-26 per the orchestrator's pre-verified data-availability
   finding (no bar moved).
2. Station mapping sourced from ForecastEx's live product API rather than the CFTC filing PDF, because
   the PDF genuinely does not contain a per-city table (§2).
3. `locked_orders`' built-in price gate neutralized via placeholder ask fields so the lock decision is
   obs-only, per the spec's explicit "signal uses obs ONLY" requirement (§5).
4. Settlement taken from the `open_interest==0` row for each ticker, not the ticker's own trading-day
   row, because the latter is a non-final provisional mark (§5) — required to honor "use the venue's
   settlement_price field as ground truth" correctly rather than literally.
5. The per-minute lock walk was accelerated via binary search over the frozen function's own monotonic
   output (verified identical to the naive walk on a spot check) — a harness performance change, not a
   change to the lock rule.

## 9. Reproduction

```
python venue_expansion/spec_S3_B.py
```
Read-only; all pulls cached under `venue_expansion/cache/` (gitignored) and never re-fetched once
present. Full per-lock/per-fire records and every summary statistic above: `venue_expansion/out/spec_S3_B.json`.
