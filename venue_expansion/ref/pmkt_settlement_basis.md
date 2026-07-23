# Polymarket temperature-ladder SETTLEMENT-BASIS study

**Date:** 2026-07-19. **Script:** `pmkt_settlement_basis.py` (read-only, reruns live). **Unit:** the
settlement-basis question flagged but not answered by `wx_new_capacity_scan.md` — is the temperature
Polymarket settles on (a wunderground.com/history station-history page, per city) reliably predictable from
the free real-time obs feeds K-WX already has, the way NWS CLI is for Kalshi (measured 1340/1340 there)?

**Headline answer: NO, not uniformly.** It ranges from perfect (5 of 10 sampled cities, all international,
all whole-°C) to poor (Denver: 28.6%; NYC/Miami LOW ladders: 57–69%) over a 14-day sample. The basis risk is
real, city-specific, and in the bad cases large enough to kill the mechanical-lock edge outright — a bot
that bought once the free-feed running extreme crossed a strike would have been WRONG on the settled
bracket 1 time in 3 to 1 time in 7 depending on the city, versus Kalshi's essentially-zero measured tail.

---

## 1. Sample and method

10 cities (mix required by the task: 4 Kalshi-overlap US cities + Denver as a 5th US city, 5 non-US),
14 trailing days (2026-07-05 to 2026-07-18, the last 14 fully-settled days as of the 2026-07-19 run date),
highest-temperature ladder for all 10, plus the lowest-temperature ladder for the 2 cities that list one
(NYC, Miami, per `wx_new_capacity_scan.md`). 168 Gamma API event pulls, cached under `_pmkt_cache/`.

For each city-day:
1. **Rule text** — pulled the full Gamma API event `description` + each rung's `resolutionSource` VERBATIM
   (not summarized) to get the exact station name, Wunderground URL, and precision statement. See section 2.
2. **Settled outcome** — pulled the same event once `closed=true`; the winning rung is the one with
   `outcomePrices=["1","0"]`. Parsed its printed range (e.g. `"80-81°F"` -> `(80,81)`, `"29°C"` -> `(29,29)`
   for the whole-degree-C cities, `"90°F or higher"` -> `(90,inf)`).
3. **Free real-time-obs proxy** — pulled IEM's daily max/min summary (`mesonet.agron.iastate.edu/cgi-bin/
   request/daily.py`) for the exact station the rules name, using the SAME endpoint the repo's own
   `wx_earlylock_study.fetch_daily()` already calls as its ASOS cross-check. Confirmed IEM's ASOS mirror is
   NOT US-only: `GB__ASOS`, `FR__ASOS`, `MX__ASOS`, `BR__ASOS`, `JP__ASOS`, `HK__ASOS` all exist and contain
   the exact station codes the Polymarket rules cite (EGLC, LFPB, MMMX, SBGR, RJTT, VHHH) — so
   `aviationweather.gov`/IEM's global METAR network genuinely is the same real-time feed for these
   international stations that it is for the domestic 20.
4. **Agreement** = does the IEM daily extreme fall inside the settled bracket's printed range. This is the
   direct analog of the repo's `kalshi_wx_settlement_basis.py` ASOS-vs-CLI 1340/1340 check.

A floating-point bug was caught and fixed during this run: naive Fahrenheit-stored-value -> Celsius
conversion (IEM's `daily.py` only returns `max_temp_f`) leaves sub-0.1° epsilon noise (`82.4°F ->
28.000000000000004°C`) that flipped exact-boundary agreements to false misses for every whole-°C city. The
committed script rounds to 1 decimal before the bracket check; this fix alone moved the pooled agreement
rate from 72.5% to 82.4% — a reminder that this kind of study is easy to get wrong in the "looks close
enough" direction, not just the "looks fine" direction.

## 2. Rule text and station mapping (verbatim from Gamma API, sampled 2026-07-19)

| City | Settlement source (verbatim, abridged) | Station | Network match found in IEM's global ASOS mirror |
|---|---|---|---|
| Chicago | "...Wunderground, specifically the highest temperature recorded for all times on this day for the Chicago O'Hare Intl Airport Station..." `wunderground.com/history/daily/us/il/chicago/KORD` | KORD | `IL_ASOS` |
| Denver | "...Buckley Space Force Base Station..." `.../us/co/aurora/KBKF` | KBKF | `CO_ASOS` |
| Miami | "...Miami Intl Airport Station..." `.../us/fl/miami/KMIA` | KMIA | `FL_ASOS` |
| NYC | "...LaGuardia Airport Station..." `.../us/ny/new-york-city/KLGA` | KLGA | `NY_ASOS` |
| London | "...London City Airport Station..." `.../gb/london/EGLC` | EGLC | `GB__ASOS` (confirmed present) |
| Paris | "...Paris-Le Bourget Airport Station..." `.../fr/bonneuil-en-france/LFPB` | LFPB | `FR__ASOS` (confirmed present) |
| Mexico City | "...Benito Juárez International Airport Station..." `.../mx/mexico-city/MMMX` | MMMX | `MX__ASOS` (confirmed present) |
| Sao Paulo | "...Sao Paulo-Guarulhos International Airport Station..." `.../br/guarulhos/SBGR` | SBGR | `BR__ASOS` (confirmed present) |
| Tokyo | "...Tokyo Haneda Airport Station..." `.../jp/tokyo/RJTT` | RJTT | `JP__ASOS` (confirmed present) |
| **Hong Kong** | **"...highest temperature recorded by the Hong Kong Observatory... resolution source will be information from the Hong Kong Observatory, specifically the 'Absolute Daily Max (deg. C)'... available here: `weather.gov.hk/en/cis/climat.htm`"** | **NOT Wunderground, NOT VHHH airport METAR** | HKO HQ is a different physical site from the VHHH airport station |

9 of 10 sampled cities settle on a genuine Wunderground station-history page whose station is a standard
METAR/ASOS airport code, confirming the scan's read: the same global obs network the repo's
`aviationweather.gov`/IEM helpers already read covers these stations, domestic and international alike.

**Hong Kong is the one sampled city that breaks the pattern entirely** — not a Wunderground scrape, not the
airport, a different government agency's own published daily climate table. Using VHHH airport METAR as a
proxy (what a bot would naturally reach for) gives only 16.7% agreement (2/12) with a clear negative bias
(IEM/VHHH consistently reads *lower* than the settled HKO bracket) — almost certainly a real urban-heat-island
gap between HKO's in-town site and the airport on reclaimed land, not measurement noise. **Do not generalize
the Wunderground findings below to Hong Kong; it needs its own study against `data.weather.gov.hk`'s API
(also free, but not yet wired into this repo) before any trading logic could touch it.**

## 3. Rule quirks (from the verbatim text, not paraphrased)

- **Precision statement, per city**: each event states exactly what precision it resolves to — e.g. Chicago/
  Denver/Miami/NYC: *"measures temperatures to whole degrees Fahrenheit"*; London/Paris/Mexico City/Sao
  Paulo/Tokyo: *"measures temperatures to whole degrees Celsius"*; Hong Kong: *"measures temperatures in
  Celsius to **one decimal place**"* — a materially finer resolution than the other 9, which likely also
  contributes to Hong Kong's low naive-proxy agreement (a 0.1°C-precision bracket has effectively 10x the
  edge-hit rate of a whole-degree one for the same underlying noise).
- **Revision window, every city**: *"This market can not resolve until the first data point for the
  following date has been published... Revisions to temperatures recorded within this market's timeframe
  will be considered until [then], after which any alterations will not be considered."* This is a real
  difference from Kalshi's CLI report (a single official bulletin): the Wunderground-sourced number can be
  silently revised for hours into the *next* local day before it's final. A bot buying on a same-day
  "mechanical lock" is buying against a number that is provisional until well past local midnight — this
  widens the false-lock window relative to Kalshi's edge, independent of station quality.
- **Timezone / day-window**: none of the sampled rule texts name an explicit timezone or UTC offset — they
  say only "on 19 Jul '26" and point to the Wunderground URL, implicitly deferring to whatever local-clock
  convention that page uses (Wunderground history pages display station-local time). This script's IEM
  comparison used IEM's own per-station local-day aggregation (`daily.py`'s `day` column), which is the
  same convention `kwx_runner.CITY`/`wx_earlylock_study.STATION_OFFSET` already assume for the 20 domestic
  Kalshi cities. **Not independently verified here**: whether Wunderground's displayed local time follows
  DST for cities that observe it (London, Paris, Mexico City do; Hong Kong, Sao Paulo currently do not) the
  same way IEM's local-day boundary does. Given the clean 100% agreement measured for London/Paris/Mexico
  City in the sample window, if there were a DST-boundary bug it isn't showing up in these 14 (non-transition)
  days — but the sample window doesn't cross a DST transition, so this is genuinely untested, not confirmed
  fine.

## 4. Agreement results (rung-by-rung, IEM daily extreme vs settled Polymarket bracket)

| City | Ladder | n settled | agree | rate | 95% Wilson CI | Verdict |
|---|---|---:|---:|---:|---|---|
| Chicago (KORD) | high | 14 | 13 | 92.9% | [68.5, 98.7] | **SOUND** |
| Denver (KBKF) | high | 14 | 4 | **28.6%** | [11.7, 54.6] | **RISKY** |
| Miami (KMIA) | high | 14 | 10 | 71.4% | [45.4, 88.3] | **RISKY** |
| NYC (KLGA) | high | 14 | 12 | 85.7% | [60.1, 96.0] | SOUND (borderline) |
| London (EGLC) | high | 14 | 14 | **100.0%** | [78.5, 100.0] | **SOUND** |
| Paris (LFPB) | high | 14 | 14 | **100.0%** | [78.5, 100.0] | **SOUND** |
| Mexico City (MMMX) | high | 14 | 14 | **100.0%** | [78.5, 100.0] | **SOUND** |
| Sao Paulo (SBGR) | high | 14 | 14 | **100.0%** | [78.5, 100.0] | **SOUND** |
| Tokyo (RJTT) | high | 14 | 14 | **100.0%** | [78.5, 100.0] | **SOUND** |
| NYC (KLGA) | **low** | 14 | 8 | **57.1%** | [32.6, 78.6] | **RISKY** |
| Miami (KMIA) | **low** | 13 | 9 | 69.2% | [42.4, 87.3] | **RISKY** |
| Hong Kong (VHHH proxy) | high | 12 | 2 | 16.7% | — | **UNVERIFIABLE** (wrong station; see §2) |
| **Pooled (Wunderground-sourced only, excl. HK)** | — | **153** | **126** | **82.4%** | **[75.5, 87.6]** | — |

Compare to Kalshi's own measured ASOS-vs-CLI tail (`kalshi_wx_settlement_basis.py`): 1340/1340 = 100.0%
(effectively zero false-lock rate). **Even the best Polymarket cities in this sample only match that; the
worst (Denver, both NYC/Miami LOW ladders) are an order of magnitude worse — a bot mechanically locking on
those cities' free-feed running extreme would be flat-out wrong on the settled bracket roughly 1 time in 3.**

### The directional pattern (why, not just how much)

The misses are not random noise — they have a consistent sign, and the sign flips with HIGH vs LOW exactly
as a genuine physical mechanism would: on every HIGH-ladder miss (Denver, Miami-high, NYC-high), IEM's daily
max reads **higher** than the settled bracket; on every LOW-ladder miss (NYC-low, Miami-low), IEM's daily min
reads **lower** than the settled bracket. In other words, IEM's `daily.py` summary systematically captures a
**wider** intraday range than what ends up in Wunderground's settled history table. The most likely
explanation is that IEM's daily summary folds in brief SPECI/1-minute-resolution excursions that
Wunderground's displayed per-day table does not carry forward — but this study did not chase that down to a
confirmed root cause (that would need pulling Wunderground's actual page HTML per day, out of scope for a
read-only API study). What IS established: this bias is **not** attributable to the F-vs-C rounding bug
fixed in section 1 (that bug, now fixed, only ever pushed exact matches to false negatives, not the other
way, and it doesn't apply to the F-unit cities where the bias is largest). The practical upshot for any
future trading design: **the specific free feed matters, not just the station** — IEM's `daily.py`
post-summary is measurably not the same number Wunderground settles on for several cities, even though it's
reading the correct physical station. A live implementation would need to test against Wunderground's own
displayed running value (or the raw METAR text stream) rather than trusting IEM's daily aggregate as
ground truth for this specific settlement basis, the way the repo currently does for Kalshi/CLI.

## 5. Verdict per city

| City | Verdict | Why |
|---|---|---|
| London, Paris, Mexico City, Sao Paulo, Tokyo | **SOUND** | 14/14 exact agreement in-sample; whole-°C native precision removes the F/C rounding ambiguity that hurts the US cities; genuine METAR station confirmed present in IEM's global mirror. n=14/city is small — treat as "no evidence of a problem," not "proven equal to Kalshi's 1340." |
| Chicago | **SOUND** | 13/14 (92.9%), single miss by exactly 1 rung (2°F) on 07-06. |
| NYC (high) | **SOUND, borderline** | 12/14 (85.7%), CI lower bound 60% — good in this sample but noisier than Kalshi's own CLI basis; worth a larger sample before relying on it. |
| Miami (high) | **RISKY** | 10/14 (71.4%), 4 misses all in the "IEM reads higher" direction. |
| Denver | **RISKY** | 4/14 (28.6%) — the worst of the sample, consistent warm bias every miss. Do not treat KBKF's IEM daily summary as predictive of this market's settlement without further investigation. |
| NYC, Miami (low) | **RISKY** | 57–69% — both LOW ladders underperform their own city's HIGH ladder, consistent with the wider-observed-range mechanism in §4. |
| Hong Kong | **UNVERIFIABLE** (with current infra) | Settles on Hong Kong Observatory, not Wunderground/METAR at all. The airport METAR (VHHH) this repo can already read is the *wrong station* for this market — 16.7% agreement using it is expected, not a measurement failure. A real study needs HKO's own feed (`data.weather.gov.hk`, free, not yet integrated). |

## 6. Honest power statement

14 city-days per market is enough to catch a city that's clearly broken (Denver: 28.6% with a 95% CI upper
bound of 54.6% — clearly worse than Kalshi's ~100%) and enough to give real (if not conclusive) confidence
in a city that's clearly clean (5 cities at 14/14, CI floor 78.5% — consistent with, but not proof of,
parity with Kalshi's measured 100%). It is NOT enough to distinguish "90% reliable" from "97% reliable" for
the borderline cities (Chicago, NYC-high) — that would need Kalshi's own sample size (1340 days) or close to
it. Nothing here should be read as a green light to trade any of these markets; it answers the specific
predictability question the scan left open, with the honest conclusion that the answer is **city-dependent
and, for a meaningful fraction of the sampled cities, negative** — the Polymarket ladder does NOT inherit
Kalshi's CLI-grade settlement predictability uniformly, even though it shares the same mechanical-lock
market structure and, in most sampled cities, the same physical station.

## 7. Bottom line for the capacity question

`wx_new_capacity_scan.md` correctly flagged this as unmeasured and correctly declined to green-light it.
This study measures it: the Polymarket temperature ladder is **not** a drop-in second venue for the K-WX
mechanical-lock edge as-is. A subset of cities (the 5 whole-°C international ones, and plausibly Chicago)
look genuinely comparable to Kalshi's basis risk; a subset (Denver, both LOW ladders, Hong Kong) do not, for
reasons ranging from a real cross-feed bias (§4) to a completely different settlement source (§2). Any
follow-on capacity work on this venue needs to be scoped **per-city**, not as a blanket "Polymarket
temperature = same edge, 40 more cities" assumption — and should test against Wunderground's own displayed
value or the raw METAR stream rather than IEM's `daily.py` aggregate, given the systematic bias found here.

Rerun `pmkt_settlement_basis.py` periodically and widen `CITY_MIX`/`N_DAYS` before trusting any specific
city verdict above beyond "worth a closer look" vs "worth avoiding."
