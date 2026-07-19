# Phase-3 Rain Sleeve Validation — KXRAIN monthly cumulative-precip ladders

**Question:** can Kalshi's monthly cumulative-rain-threshold ladders (KXRAINDALM, KXRAINCHIM, ...,
~10 cities) be a real, cleanly-lockable, deployable trading sleeve #2 that STACKS with the confirmed
K-WX temperature-nowcast edge? Prior scan (`phase3_capacity_expansion.md`) flagged the mechanic as
promising (same monotonic-ratchet lock, 10-100x deeper books, ~34-min convergence) but found an 11%
false-lock rate (2/18 "price jumped to ≥98c" events settled NO) when triggered off Kalshi's own price.
This report builds the missing piece: an independently-observed precip signal, tested against the full
real settlement history, with real book depth and a direct comparison to the temp sleeve's fire-day
pattern.

All numbers below are from live Kalshi API pulls + NWS/IEM data on 2026-07-18. Code and cached raw data
under `/tmp/.../scratchpad/` (session-local; not committed).

---

## 1. Settlement source — confirmed exactly

Pulled `series_ticker` metadata + one `rules_primary`/`rules_secondary` per city from
`api.elections.kalshi.com/trade-api/v2`. Every KXRAINxxxM series settles on:

> **"If the total precipitation at CLI\<STATION\> in \<City\> in \<Month\> \<Year\> is strictly greater
> than N inches, then the market resolves to Yes."**
> Source: **NWS Climatological Report (Daily)**, cited by Kalshi itself as *"the official and final
> value"*; Kalshi's own rules text warns *"Preliminary NWS reporting and measurement methods may be
> subject to underlying rounding and conversion nuances."*

Concretely: monthly total precipitation at the city's primary NWS climate station (DFW, MDW, HOU, MIA,
AUS, DEN, Central Park/NYC, SEA, SFO, LAX), calendar-month period, `strike_type=greater`. The NWS CLI
report is a genuine text product (AFOS pil `CLIxxx`, e.g. `CLIDFW`), issued ~1-2x/day, real-time via
`api.weather.gov/products?type=CLI&office=K<WFO>` (rolling ~7-day window only) or historically via IEM's
text archive (`mesonet.agron.iastate.edu/api/1/nws/afos/...`, unlimited history). **This is the true
observable** — not Kalshi price, not raw ASOS.

## 2. Two candidate "observed" signals tested, one ruled out

**Raw IEM ASOS 1-min `precip` summed to a running MTD total — REJECTED as a standalone signal.**
Pulled full 1-min precip for all 10 stations, May 1 – Jul 18 2026 (70k-105k obs/station). Compared the
raw-ASOS monthly sum to Kalshi's official settled monthly total (`expiration_value`):
- Two stations showed **massive, unacceptable divergence**: Dallas June (ASOS 5.43in vs official 8.1in,
  -33%) and Austin May (ASOS 4.55in vs official 8.0in, -43%).
- Root cause, verified directly: **systematic telemetry gaps in the public 1-min feed**, worst exactly
  when it matters — Dallas June was missing 21% of minutes including one 36-hour gap (Jun 23-25); Austin
  May was missing 25% of minutes including three gaps of 32-42 hours each. Heavy-rain periods correlate
  with reporting outages (plausible connectivity/power issues during storms), so raw-ASOS summation
  **silently and preferentially undercounts exactly the events a lock strategy needs to catch.** Not
  usable as a monthly-accumulation signal on its own.

**NWS CLI daily report "MONTH TO DATE" field — the real clean signal.** Harvested every CLI product
issued for all 10 cities, May 1 – Jul 17 2026 (1,220 individual reports, both the ~AM "yesterday final"
and ~PM "today so far" issuances, via IEM's AFOS text archive). Built the full intra-month trajectory per
city. Result:

- **Every single one of 30 complete city-months tested is perfectly monotonic** — the officially-reported
  MTD figure never once decreased mid-month across the entire dataset (max-ever-reported == final
  reported value, in all 30 cases).
- Final CLI-reported MTD matches Kalshi's official settlement total (`expiration_value`) to within
  **0.02–0.05 inches in every single city-month** (mostly attributable to simple decimal rounding: e.g.
  Dallas CLI 8.07 vs Kalshi 8.1, Chicago CLI 1.60 vs Kalshi 1.6, NYC CLI 3.05/3.39 vs Kalshi 3.05/3.39
  exact). This is a **directly-confirmed, tight, honest basis-risk figure** — not an assumption.
- **Directly resolved both of the prior scan's two known "false lock" cases** using this trajectory:
  - `KXRAINDALM-26MAY-3` (strike >3in): true CLI-reported MTD peaked at **2.96in, never crossed 3**. The
    Kalshi price touching 98-100c was a pure price/forecast overreaction — the observed signal never
    fired.
  - `KXRAINMIAM-26JUN-4` (strike >4in): true CLI-reported MTD peaked at **1.87in**, nowhere close to 4.
    Same conclusion — pure price overreaction, observed signal never fired.

**Conclusion on Q1/Q2 (settlement source + lock-signal cleanliness):** the true observable is the NWS
CLI Daily Climate Report's "MONTH TO DATE" line, sourced identically to Kalshi's own settlement basis.
Built and back-tested as a trigger, it produced **0 false locks in 58 fired events across the full
available settled history** (versus the price signal's 11%, both of whose known failures are now
concretely explained as price running ahead of — not behind — the true accumulation). **The clean signal
is real, is buildable off existing infra style (mirrors `aviationweather_metar.py`'s confirmation-gate
pattern), and eliminates the false-lock risk entirely on this sample.**

## 3. OOS EV/ct, n, win% on the real KXRAIN candlestick history — the honest bad news

Backtested two variants of the clean signal against every settled monthly-ladder market (134 markets,
10 cities, May+June 2026 — **the only two complete monthly cycles that exist**; these are brand-new
products, `last_updated_ts` on the series ranges from 2026-03-25 to 2026-07-02, so this is not a
truncated sample, it is the entire available history):

| trigger | n fired | false locks | tradeable n | win% | mean pnl (EV/ct) | DOA (exec≥98c) | deployable n (exec<98c) | deployable EV/ct |
|---|---|---|---|---|---|---|---|---|
| **CLI report** (twice-daily, the true settlement source) | 58 | **0** | 57 | 100% | **+0.0046** | 96.5% | 1 | +0.189 |
| **Raw ASOS running-sum** (faster, ~5h median lead over CLI, but gap-prone) | 50 | **0** | 50 | 100% | **+0.0107** | 90.0% | 5 | +0.083 |

**Why the blended EV is so thin despite a perfectly clean signal:** rain accumulates over days-to-weeks,
not minutes. By the time an *official* twice-daily report (or even a faster raw-sensor read) confirms a
threshold crossing, Kalshi's own book has usually **already repriced to ~99-100c on its own** — sophisticated
rain-market participants clearly watch radar/local weather in real time and don't need to wait for the
government report. This is the opposite problem from temperature: on temp, the independent METAR feed
*beats* slow retail's repricing by minutes. On rain, the clean official signal *loses the race* to the
market roughly 90-97% of the time. The residual ~3-10% of fires that aren't already dead-on-arrival do
show real, attractive edge (+0.08–0.19/ct, 100% win in-sample) — but **n=1 to n=5** is not statistically
meaningful; it is a promising anecdote, not a validated edge, at this sample size.

**Real book depth (live, sampled today):** ask-side sweepable depth on partially-priced (not-yet-locked)
rungs across 6 spot-checked cities ranged **~$130 to ~$4,200 notional** per rung (Dallas strike-3 ~$?,
Chicago-4 exactly reproduced the prior scan's $1,080/1,135ct, Houston-4 ~$2,042, Denver-1 ~$1,755, Seattle-1
~$4,192, Austin-3/Miami-3/NYCM-4 in the $130-350 range). This confirms depth IS materially deeper than
weather's median (~$10-90 notional) — **but depth without a fast-enough trigger cannot be captured**, since
the depth is exactly what's absorbed by the time our clean signal fires.

**Rough weekly capacity, honest end-to-end:** ~5-6 fired events/week pooled across all 10 cities in this
window, of which ~10% (0.5-0.6/week) are non-DOA. At $100-2,000 realistically sweepable notional and
+0.03-0.19/ct on those, that is **roughly $5-100/week** of expected value from the *validated, clean*
signal — two orders of magnitude below the prior scan's $1,500-4,000/week estimate, because that estimate
was built on the unvalidated price-momentum trigger's raw average gap, without netting the fact that a
clean substitute signal (once actually built and tested) mostly arrives after the edge is gone.

**Partial mitigation checked:** could a cheap "require some independent corroboration" filter recover the
naive price-signal's larger apparent edge while blocking its false locks? Checked both known false-lock
cases against the true CLI trajectory: Miami-June's true MTD topped out at only 47% of strike (1.87/4.0)
— a corroboration floor of even 70-80% of strike would have cleanly blocked this one. Dallas-May's true
MTD reached 99% of strike (2.96/3.0) — a genuine near-miss that **no reasonable corroboration threshold
would have caught**, since the observed data really was almost there. So a hybrid filter helps but does
not fully close the tail risk; the price-momentum route remains fundamentally probabilistic, not a true
mechanical lock, no matter how it's filtered.

## 4. Diversification vs the temp sleeve

Compared same-city, same-day rain occurrence (ASOS-derived daily precip, all 10 rain cities exactly
match 10 of the temp sleeve's cities) against the temp sleeve's `margin1/sustain3` frozen-config daily
fire counts and PnL (`_trackA_results_raw.json`, n=3891 fires, 66/67 days with ≥1 fire):

- **608 matched city-days.** Rainy days (>0.1in, n=93) show mean **4.60 temp fires/day** vs dry days
  (n=515) mean **3.67 temp fires/day** — i.e. temp-sleeve activity is *not* suppressed on rainy days, it's
  mildly *higher*. Correlation of daily rain amount vs same-city-day temp-sleeve fire count = **+0.169**;
  vs temp-sleeve PnL = **+0.130**. Both weak-positive, not negative.
- **Mechanistic reason this is not surprising:** the temp sleeve fires on *any* running max/min crossing
  a bracket edge — including the "between/less than" brackets, which are *more* likely to lock early on a
  cooler, cloud-suppressed, rainy day (the day's high is capped early, locking a lower bracket sooner).
  So "rain suppresses hot-day fires" is true only for the headline ">X" hot rung; it is not true for the
  temp sleeve's actual (bracket-dominated) fire pattern.
- **Practical read:** rain does **not** provide the "fires on different days, smooths the drawdown"
  diversification the task hypothesized — and that framing was moot anyway, since the temp sleeve has
  **zero net-negative days in-sample** (per `DECISION_MAP.md`), so there is no drawdown to smooth. What
  rain *would* add, if the EV supported it, is a genuinely different trigger mechanism (precip vs
  temperature) and does not cannibalize execution bandwidth from the temp sleeve (different infra,
  different report cadence, different capital). But per Section 3, the dollar throughput it can honestly
  add today is negligible.

## 5. VERDICT

**Rain is a real mechanic, but not yet a real sleeve #2, and the honest numbers do not support the prior
scan's optimistic capacity estimate.**

- Settlement source and the true clean observable are now concretely nailed down (NWS CLI Daily report,
  same-source as settlement) — **this part of the task succeeded**: the false-lock problem is fully
  explained (price ran ahead of reality, not a data/observable failure) and a genuinely clean substitute
  signal was built and back-tested at **0% false-lock rate over the entire available settled history
  (n=58)**.
- But building the clean signal exposed the real problem the prior scan didn't test: **rain's threshold
  crossings are usually already priced in by the time any independently-observable confirmation exists**
  (96.5% DOA on the CLI trigger, 90% DOA even on a faster raw-sensor trigger). The blended EV of the
  validated signal is **+0.005 to +0.011/ct**, not the +0.15-0.20/ct the temp sleeve delivers, and the
  thin non-DOA tail that does show real edge (n=1-5) is far too small to trust as a stable number.
- Real book depth is genuinely deeper than weather's (confirmed live, $130-$4,200/rung vs weather's
  ~$10-90) — but depth is irrelevant if the trigger can't reach it before the market does.
- Diversification against the temp sleeve is weak-positive-to-null on fire-day correlation, and the
  drawdown-smoothing framing doesn't apply because the temp sleeve has no drawdowns to smooth in-sample.
- **Sample-size caveat, stated plainly:** these are brand-new Kalshi products with only 2 complete
  monthly cycles of history in total (not a subsample — the entire available history), across 10 cities.
  Every number above (0% false-lock rate, EV/ct, DOA%) should be read as "the best current honest
  estimate from a genuinely thin dataset," not as a temp-sleeve-grade (n=1698, t=37) confirmation.

**Bottom line: NULL for "deployable sleeve #2" as specified (a signal that is both clean AND captures
real edge AND diversifies).** It is clean. It does not yet capture real edge at any meaningful scale, and
it does not diversify in the way hypothesized. Do not deploy capital against the naive price-momentum
trigger (11% blowup, unquantified against its own EV) — and do not deploy capital against the clean
CLI/ASOS trigger either, because its EV is at noise level ($5-100/week) with n far too small to trust.
If this is to be revisited, the actionable next step is **not** more backtesting on this dataset (it is
already the full history) — it is waiting for more monthly cycles to accumulate (a structural, not
infra, blocker), or finding a genuinely faster corroboration source (e.g. real-time radar-derived
precipitation estimates, which were not tested here and are a different infra class entirely).
