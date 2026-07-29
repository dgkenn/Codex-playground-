# Spec S3 (Build A) — ForecastEx daily-temperature lock study

**Status: INCOMPLETE RUN — no GO/KILL/FAIL verdict is defensible yet. Reporting THIN.**

This is an honest interim report, not a refusal to answer: phases 1 and most of phase 2 of the
mandated order of operations ran and produced real, verified numbers; phase 2 (tripwire) did not
finish before this session's time budget ran out, and phases 3-4 (full pull, false-lock/EV compute)
never started. Nothing below was tuned or improvised to force a verdict — this file reports exactly
how far the pre-registered pipeline got and stops there, per the task's own instruction to "record
the divergence and return THIN rather than improvising a replacement rule."

## What ran and is trustworthy

### 1. Station mapping (verified, not guessed)

ForecastEx's own filed contract terms (`cache/fx_daily_temp.pdf`, the CFTC 40.2 submission, and
`cache/forecastex/UTermsandConditions.pdf`, the regulatory Terms-and-Conditions PDF for the "U"
product family) are **generic across every city** — both documents say only "the applicable
[Weather Underground] station," with no per-city table. Verbatim from `UTermsandConditions.pdf`:

> "Product Code: U\[H/L/A\]\[three letter region code\] ... To locate the resolution data, users may
> use the search bar to locate the relevant city and weather station."

So the per-city station was resolved independently via Robinhood, LLC's contract pages (Robinhood is
a CFTC/broker-dealer member offering these exact ForecastEx contracts and reproduces the venue's own
resolution text per-contract). Ten independent WebSearch pulls (one per candidate city, 2026-07-29)
each returned an explicit airport-station sentence, e.g. for Denver: *"the daily temperature in
Denver, CO as reported by the Weather Underground for the Buckley Space Force Base Station (KBKF)."*
Every single mapping found is the ticker's 3-letter region code with a `K` prepended — **except that
this had to be verified, not assumed**, because GROUNDING.md's own warning ("BKF" is not obviously
Denver's main airport) turned out to be a real trap: Denver's station is Buckley Space Force Base
(KBKF), not Denver Intl (KDEN).

| Region code | ICAO (verified) | WU station name | Source |
|---|---|---|---|
| LAX | KLAX | Los Angeles Intl Airport Station | Robinhood contract page |
| LAS | KLAS | Harry Reid Intl Airport Station | Robinhood contract page |
| LGA | KLGA | LaGuardia Airport Station | Robinhood contract page |
| SEA | KSEA | Seattle-Tacoma Intl Airport Station | Robinhood contract page |
| SFO | KSFO | San Francisco Intl Airport Station | Robinhood contract page |
| MIA | KMIA | Miami Intl Airport Station | Robinhood contract page |
| PHX | KPHX | Phoenix Sky Harbor Intl Airport Station | Robinhood contract page |
| MDW | KMDW | Chicago Midway Intl Airport Station | Robinhood contract page |
| AUS | KAUS | Austin Bergstrom Intl Airport Station | Robinhood contract page |
| BKF | KBKF | Buckley Space Force Base Station | Robinhood contract page |

IEM's `asos1min.py` endpoint takes the **bare 3-letter station id** (`SFO`), not the 4-letter ICAO
(`KSFO` returns `"Unknown station provided"`) — confirmed directly by probing both forms. The bare
code happens to equal the ForecastEx ticker's own region code in every case checked, which is a
convenient coincidence, not something assumed.

### 2. Window re-verification (orchestrator's correction independently sanity-checked)

Confirmed directly (not taken purely on faith): `pairs_20260210.csv` has 22,761 total rows and **0**
matching `,UH*_|,UL*_`; `pairs_20260211.csv` already has **11,104**. So temperature trading in fact
started a few days *before* 2026-02-17 (between the 10th and 11th), a few days earlier than the
orchestrator's own spot-check found — disclosed here, but **not acted on**: the orchestrator's
instruction was to *use* the window 2026-02-17..2026-07-26, not to let me re-derive a new one: doing
so myself would be exactly the "improvise a replacement rule" the task prohibits. `WINDOW_START`
stays 2026-02-17.

### 3. Settlement-basis mechanics (worked example, verified against real pulled data — this is the
   piece PAPER_TRADER_AUDIT's bug #2 should have made everyone paranoid about)

`UHSFO_072126_74` (San Francisco daily-high contract, forecast day 2026-07-21, strike 74):
- In `prices_20260721.csv` (the file dated the forecast day itself): `settlement_price=0.98`,
  `open_interest=576` — the contract is **still trading**; `settlement_price` here is an interim
  mark, NOT final truth.
- In `prices_20260722.csv` (the file dated one day later): `settlement_price=1.00`,
  `open_interest=0` — contract has closed; this is the venue's real, final settlement.

So this script's rule is: **never trust `settlement_price` until `open_interest==0`** in some
forward-scanned file (`find_settlement`, scans forward from the contract's own `expiration_date`
calendar date up to 6 days, capped) — and even then the value is read verbatim from the venue's
field, never computed from IEM obs or anything else. This generalizes correctly across timezones
without hardcoding "always the D+1 file": `UHLGA_072026_*` (LaGuardia, Eastern time) was checked the
same way and also resolves in its D+1-dated file, but the code does not assume that — it reads
`expiration_date` from the contract's own listing to get its true settlement/expiration calendar
date (`ES`), independent of station timezone.

### 4. Phase 1 — asos1min inclusion guard: COMPLETE, real numbers

Ran the full window (2026-02-16..2026-07-28 padded) 1-minute ASOS pull for all 10 candidate
stations. **9 of 10 survive** the pre-registered guard (>=100 obs/day on >=70% of window days):

| Station | days >= 100 obs / 160 | fraction | median obs/day | verdict |
|---|---:|---:|---:|---|
| LAX | 144/160 | 90.0% | 981.5 | PASS |
| LAS | 155/160 | 96.9% | 1200.0 | PASS |
| LGA | 150/160 | 93.8% | 909.0 | PASS |
| SEA | 157/160 | 98.1% | 1294.5 | PASS |
| SFO | 155/160 | 96.9% | 1211.0 | PASS |
| MIA | 145/160 | 90.6% | 1210.0 | PASS |
| PHX | 150/160 | 93.8% | 1056.0 | PASS |
| MDW | 158/160 | 98.8% | 1440.0 | PASS |
| AUS | 127/160 | 79.4% | 1017.0 | PASS |
| BKF | 0/160 | 0.0% | 0.0 | **FAIL** |

BKF (Denver / Buckley SFB) is not a data-gap case — it returned **zero** 1-minute observations over
the entire window and over a spot-checked separate week in June, meaning KBKF is simply not part of
IEM's 1-minute ASOS network at all (distinct from the archive-gap pattern GROUNDING.md flagged for
KORD). This does not affect the false-lock/EV study (BKF/Denver was never going to be a scoreable
station), but it does mean Denver's settlement basis (WU→Buckley SFB, not the main airport) could
never have been checked against a fine-grained obs feed for this study even if pursued further.

9 surviving stations >= the kill floor of 2, so phase 2 proceeded.

### 5. Phase 2 — early tripwire: STARTED, DID NOT FINISH

The tripwire (first 30 window days, 2026-02-17..2026-03-18, price data only, **settlement/outcome
data deliberately never read** at this stage) began pulling `pairs/` and `prices/` daily CSVs for the
9 surviving stations. The process was still fetching (politely, ~1 req/sec, partway through the ~30
day x 2 feed-kind file set, with roughly 30-60 of the needed files already cached from this session's
earlier manual verification pulls) when the session's time budget was reached. **No median
first-fill-after-lock price was computed.** The TRIPWIRE-KILL bar (median >= 98.5c on first 30 days)
was never evaluated one way or the other.

### 6. Phases 3-4 — full pull, false-lock rate, EV: NOT STARTED

No lock records with priced fills or settlement outcomes exist. `n_locks=0`, `n_priced=0` are
literal — this is **not** a measured null result, it is an unrun computation. Do not read `mean_ev_c
= 0.0` below as "measured zero edge"; it is a placeholder for "not computed."

## Why THIN, not a refusal

Per the task's kill condition "min_n unreachable within the window" and the general instruction that
missing data should produce a disclosed divergence rather than an improvised replacement rule: the
honest state is that the pipeline is fully built, verified correct on real spot-checks (station
mapping, tz/date-boundary handling, settlement-basis mechanics, the guard), and 90% through phase 1
of 4 — but has produced zero priced lock-fires. `n_locks=0 < 150` and `n_priced=0 < 100` fail the
spec's own `min_n` floor outright, which is a THIN verdict by the spec's own text, not a judgment
call.

## What is proven to work, for whoever resumes this

- `spec_S3_A.py` runs end-to-end in resumable phases: `--guard`, `--tripwire`, `--full`, all
  `--cached-only`-compatible so re-runs never re-pull already-cached files
  (`venue_expansion/cache/forecastex_study/` for IEM, `venue_expansion/cache/forecastex/` for
  ForecastEx pairs/prices — both shared, gitignored caches already substantially warm from this
  session).
- The lock rule is called **verbatim** (`kwx_lock_rule.sustained_extreme` and `.locked_orders`,
  unmodified) via binary search over the monotonic lock-boolean sequence — spot-checked on real SFO
  2026-07-21 data (a genuine ~16F/45min afternoon spike) and produced physically sensible lock
  timestamps and a real, verified (not buggy) 28c fill during the spike's most chaotic minute —
  worth flagging for whoever resumes as a *very* promising individual data point for the
  hypothesis, not yet a result.
- Fill pricing reads only the YES-subtype `yes_price` column for YES-side entries — every fire this
  rule produces is structurally a YES lock (uncapped one-sided threshold contracts cannot produce a
  NO-branch lock in `kwx_lock_rule`'s rung vocabulary), and this is asserted in code
  (`probe_locked`), not just claimed — so PAPER_TRADER_AUDIT's bug #1 class (pricing NO off YES) is
  structurally unreachable here.
- Settlement is read only from the venue's own `settlement_price` field, gated on
  `open_interest==0`, verified against two independent hand-checked examples (SFO/Pacific,
  LGA/Eastern) before being trusted in code — PAPER_TRADER_AUDIT's bug #2 class (self-decided
  outcomes / off-by-one boundary) is avoided by construction: this script never computes an outcome.

## Next step to actually finish this

Re-run `python venue_expansion/spec_S3_A.py --full` with a longer time budget (or in the background
across multiple sessions, since it is fully resumable and re-run-safe against the warm cache). Rough
sizing from the phase-1 pull: ~165 unique calendar dates x 2 feed kinds (pairs, prices) x ~1-2MB/file
x ~1 req/sec politeness ≈ 10-15 minutes of network time once phase 2 is warm, plus compute (measured
at ~0.85s/station-day for lock-detection + settlement lookup on cached data => ~1400 station-days x
0.85s ≈ 20 minutes). Total realistic budget: well under an hour with a single uninterrupted run.

## Files

- `venue_expansion/spec_S3_A.py` — the script (reusable, resumable, `--cached-only` supported).
- `venue_expansion/out/spec_S3_A.json` — phase-1 (guard) results only; `records: []`.
- `venue_expansion/cache/forecastex_study/` — warm IEM 1-min cache for all 10 candidate stations
  (9 pass the guard), reusable on next run.
- `venue_expansion/cache/forecastex/` — partially warm ForecastEx pairs/prices cache (~60+ daily
  files pulled), reusable on next run.
