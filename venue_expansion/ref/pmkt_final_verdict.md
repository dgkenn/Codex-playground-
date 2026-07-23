# Polymarket temperature ladders -- PHASE 2 FINAL VERDICT

**Date:** 2026-07-19. **Script:** `pmkt_final_verdict.py` (read-only, reruns live; this run's raw output is
`pmkt_final_verdict_results.json`). **Unit:** the decisive follow-up both merged studies asked for.
`pmkt_settlement_basis.md` named a basis-SOUND city whitelist and declined to generalize past it.
`pmkt_gap_study.md` ended INCONCLUSIVE and listed exactly three things that would resolve it: scale the
sample to 60-100+ city-days, measure the false-lock rate (never measured -- every prior fire was a known
winner), and replace mid/last-trade price with an executable-ask-based entry cost. This script does all
three, restricted to the whitelist, and renders the verdict.

## VERDICT: **STILL-BLOCKED** (not GO, not a clean NO-GO either -- see why, and what would fix it, below)

**The blocker is not the false-lock rate -- that came back excellent, matching Kalshi.** It is that the
only free obs feed available for 5 of the 6 whitelist cities (routine hourly METAR -- IEM's true 1-minute
ASOS archive is confirmed US-only) is too coarse, combined with the deployed margin, to actually confirm
which bracket a day will settle in on most days. **106 of 144 backtested city-days (74%) never produced a
single "the deployed rule now believes we're in the winning bracket" signal at all** -- not because the
free feed disagreed with the eventual outcome, but because the sustained, margin-cleared extreme simply
never climbed into the settled bracket's own qualifying sub-range before the day's data ran out. That caps
realistic trade frequency on this venue far below what the false-lock-rate and EV numbers alone would
suggest, independent of whether the edge, when it does fire, is real. More of the SAME kind of data will
not fix this for the 5 international cities -- the 1-minute feed simply does not exist for them, free or
otherwise. It COULD be fixed for Chicago specifically (which does have a real 1-minute ASOS feed this
script deliberately did not use, for cross-city consistency -- see "What would move this to GO" below).

---

## 1. Sample (item 1: scale to 60-100+ city-days)

**Target was >=60 usable city-days; got 144**, well past target, honest about what's actually usable within
that:

| City | Station | Unit/margin | Sample window | Usable days | Skipped |
|---|---|---|---|---:|---:|
| Chicago | KORD | F / 1.0°F | 2026-02-09 to 2026-07-13 | 22 | 1 |
| London | EGLC | C / 0.5°C | 2026-02-09 to 2026-07-13 | 22 | 1 |
| Paris | LFPB | C / 0.5°C | 2026-02-17 to 2026-07-17 | 24 | 2 |
| Sao Paulo | SBGR | C / 0.5°C | 2026-02-17 to 2026-07-17 | 24 | 2 |
| Tokyo | RJTT | C / 0.5°C | 2026-03-15 to 2026-07-18 | 26 | 0 |
| Mexico City | MMMX | C / 0.5°C | 2026-04-06 to 2026-07-15 | 26 | 0 |
| **Total** | | | | **144** | **6** |

Whitelist and per-city agreement numbers are reused verbatim from `pmkt_settlement_basis.md`'s verdict
table: London/Paris/Mexico City/Sao Paulo/Tokyo (14/14 = 100.0% IEM-vs-settled in that study's 14-day
sample) plus Chicago (13/14 = 92.9%, single explainable 1-rung/2°F miss). Excluded, per that study's own
verdict, and NOT touched here: Denver (28.6%), NYC/Miami HIGH (borderline/71.4%), NYC/Miami LOW
(57-69%), Hong Kong (settles on the Hong Kong Observatory, not Wunderground/METAR at all).

**Earliest available date per city was MEASURED, not guessed** -- binary search on Gamma API event-slug
404s (2026-07-19): all six whitelist cities' ladders start between 2026-02-06 (Chicago/London) and
2026-04-03 (Mexico City). `END_DATE = 2026-07-18`, the same "last fully-settled day" convention
`pmkt_settlement_basis.py` used. Sample dates are a stride across each city's full available window
(~22-26 samples/city) rather than every single day, to keep CLOB/IEM call volume polite while comfortably
clearing the 60-day target. The only skip reason across all 6 cities was `event_not_found` (6 of 150
candidate slugs, 4%) -- IEM's routine METAR archive turned out to have essentially no coverage gaps for
this whitelist once the exclusive-end-date bug below was fixed (see "bugs caught").

**Coverage-only obs feed used, and why:** `asos1min.py` (IEM's TRUE 1-minute ASOS archive,
what `pmkt_gap_study.py` used) was tested live against all 6 whitelist stations on 2026-07-19: EGLC, LFPB,
MMMX, SBGR, RJTT all returned **zero rows** -- confirmed US-only. IEM's ROUTINE archive (`asos.py`, ~hourly
METAR) DOES cover all six (confirmed live: 24-25 obs/day for EGLC/RJTT). Per `kwx_runner.sustained_extreme`'s
own docstring, running the deployed sustain-3 rule on a coarser feed makes it MORE conservative, never
less -- so this is a valid, if coarser, application of the same rule, not a different one. **This coarseness
is the root of the STILL-BLOCKED verdict below, not a side note.**

**A real bug caught mid-run** (same spirit as the F/C rounding bug `pmkt_settlement_basis.py` caught): IEM's
`asos.py` treats its `day2` parameter as an EXCLUSIVE upper bound (a `day1=10,day2=11` request returns ONLY
day-10 rows, silently dropping day 11 entirely) -- confirmed reproducible 3x live, compared against a wider
3-day pull that did include the missing day. Fixed by padding the requested end date by one calendar day.
Uncaught, this would have silently truncated every city-day's obs to its first ~19 hours, corrupting the
completeness guard and the running-extreme computation identically across all 144 samples -- worth flagging
for the same reason the earlier F/C bug was: these free-feed studies are easy to get wrong in the
"looks fine" direction.

---

## 2. False-lock rate (item 2)

Two numbers are reported, deliberately NOT blended together, because they answer different questions:

### 2a. The PURE deployed rule (`kwx_runner.locked_orders`, reused verbatim, no extension)

`locked_orders()` only ever declares **YES** on an uncapped top rung ("X or higher") and **NO** on any rung
whose cap gets exceeded by margin -- by design, because a bounded bracket has no monotonic-running-max
guarantee the way Kalshi's one-sided threshold does. Applied to the whitelist's obs streams:

| | n | wrong | loss rate | 95% Wilson CI |
|---|---:|---:|---:|---|
| **Pooled, all 6 cities** | **745** | **0** | **0.000%** | **[0.000%, 0.513%]** |
| Chicago | 120 | 0 | 0.00% | -- |
| London | 85 | 0 | 0.00% | -- |
| Paris | 107 | 0 | 0.00% | -- |
| Sao Paulo | 94 | 0 | 0.00% | -- |
| Tokyo | 135 | 0 | 0.00% | -- |
| Mexico City | 204 | 0 | 0.00% | -- |

**This is the single best-news finding of this phase.** Kalshi's own measured analog
(`kalshi_wx_settlement_basis.py`) is ~0.4% conditional loss (1340/1340 ASOS-vs-CLI in one framing, a
small measured tail in the deployed-rule framing). 0/745 here, CI upper bound 0.513%, is squarely
consistent with Kalshi-grade reliability for the whitelist. The whitelist selection (from
`pmkt_settlement_basis.md`) is doing real work: basis-sound cities, run through the SAME glitch+sustain-3
discipline used live, produce a false-lock rate that does not distinguish itself from Kalshi's own record
in this sample.

The catch: 745 fires sounds like a lot, but the overwhelming majority are NO-locks ruling out low rungs
well after the temperature has obviously passed them (cheap, safe, low-urgency confirmations) -- explicit
YES locks (the economically live, "confirm the actual winner" signal) are rare, because only the single
uncapped top rung of each 11-rung ladder can ever get one directly. That's exactly why item 2b exists.

### 2b. Bracket-entry rate (the documented extension needed to price ANYTHING; item 3 feeds off this)

`entries` tracks the first moment the SAME filtered extreme fell within each rung's own margin-adjusted
band -- the bracket-ladder generalization of "a cross," built from the identical deployed extreme, not a
new heuristic on raw obs. Its own false rate, kept separate from 2a:

**511/549 = 93.078% wrong (95% CI [90.642%, 94.916%])**

Read correctly, this is not bad news about the rule -- it is the quantified version of exactly what
`pmkt_gap_study.md` already concluded qualitatively ("Polymarket's bracket ladder has no equivalent
instantaneous certainty... a rung inside the bracket can still be pushed out the top later"): a naive
"buy whatever bracket the temperature is CURRENTLY in" strategy is wrong 93% of the time, because a rising
day's temperature visits several rungs on its way to the one it finally settles in. This number is the
correct base rate for item 3's win/loss weighting (below) -- it is NOT the number to compare to Kalshi's
0.4%; 2a is.

---

## 3. Ask-based EV (item 3)

**Fee, confirmed two independent ways** (docs.polymarket.com/trading/fees, help.polymarket.com's trading-fees
article, AND the live `feeSchedule` field pulled directly off every sampled market: `{"exponent": 1, "rate":
0.05, "takerOnly": true, "rebateRate": 0.25}`): Weather-category taker fee = `shares * 0.05 * p * (1-p)`
in USDC, **taker-only** (makers pay nothing). A mechanical-lock buy is always a taker (crossing the resting
ask), so this is the fee every fire below is charged. Lower nominal rate than Kalshi's 0.07 multiplier, and
no forced round-up-to-the-cent the way `_kalshi_fee_c` has -- a small structural tailwind for Polymarket at
the near-100c prices these fires cluster around.

**No historical ask exists via public API** (confirmed: `prices-history` returns last-trade/midpoint only;
there is no historical order-book endpoint) -- same limitation `pmkt_gap_study.md` already flagged. Proxy
used: last-trade price at/after the bracket-entry timestamp, plus HALF of a FRESH live spread pulled today
per city (Step-2-style CLOB book snapshot at run time): chicago 0.2c, paris 1.0c, tokyo 2.0c, mexico-city
12.0c (no live ladder open at run time for london/sao-paulo -- fell back to `pmkt_gap_study.md`'s own
pooled live-spread median, 3.3c/2).

**Sub-sample scoping, disclosed, not silent:** pricing every one of the 549 entries would be 500+ more CLOB
calls for rungs the market had mostly already abandoned -- not polite, and not informative. Instead, UP TO
TWO fires per usable city-day: (a) the settled WINNER's own entry (a win by construction), and (b) the
entry IMMEDIATELY PRECEDING the winner's (a loss by construction -- the "one rung too early" case). This
keeps the sample genuinely loss-inclusive (the #1 gap `pmkt_gap_study.md` flagged: "this backtest never
asks... does the rule ever confirm the WRONG bracket") without pricing the full 93%-wrong population 2a/2b
already characterize. 74 fires qualified (38 win-case, 36 loss-case, some days had no "prior" entry to
pair); **31 had usable CLOB price history** (15 win, 16 loss) -- the rest were thin/silent tokens.

| | n | mean net EV/ct | median net EV/ct |
|---|---:|---:|---:|
| Win-case fires | 15 | +39.99c | +29.83c |
| Loss-case fires | 16 | -2.51c | -1.10c |
| All 31, unweighted (NOT the right number -- see below) | 31 | +18.05c | -0.16c |

The unweighted mean/median mixes a manufactured ~48% win rate (one win + one loss per day, by
construction) with a true measured win rate of **6.9%** (from item 2b: 100% - 93.08%). Reweighting the
win/loss-case means by that measured rate gives the honest estimate of unconditional per-fire EV:

**EV/ct ~= 0.069 x (+39.99) + 0.931 x (-2.51) = +0.43c/ct**

Compare to Kalshi's confirmed +0.15 to +0.21/ct. On its face this beats Kalshi -- **but treat this as a
directionally-interesting, NOT a confirmed, number.** It rests on 31 priced fires, and the win side is
dominated by a handful of large-payoff outliers (three fires north of +80c/ct, from entries that landed
very early relative to settlement while the market still had real uncertainty priced in -- Paris 2026-06-23,
Tokyo 2026-07-13, Mexico City 2026-06-17). That pattern is consistent with, not contradicted by, the
gap-decay shape `pmkt_gap_study.md` already measured (its own n=15 confirmed-lock sample had mean gap 0.44
at lock) -- but n=31 total, with the loss side effectively capped near -6c/ct because losing rungs are
cheap by the time they're entered (which is itself a product of item 2b's 93% base rate -- a currently-priced
rung usually isn't cheap unless the market already suspects it's wrong), is nowhere near Kalshi's
multi-year, loss-inclusive sample size. The right read: **the sign and rough magnitude are plausible and
worth re-testing, not proven.**

---

## 4. Why this is STILL-BLOCKED and not GO

The false-lock rate (2a) is excellent. The reweighted EV (3) is plausibly positive and bigger than Kalshi's.
Neither of those is the blocker. **The blocker is signal coverage** -- how often the deployed rule ever
produces a "we're in the winning bracket" entry at all, measured directly in this run:

| City | Usable days | Winner bracket never entered | Coverage rate |
|---|---:|---:|---:|
| Chicago | 22 | 13 | **40.9%** |
| Mexico City | 26 | 12 | **53.8%** |
| Tokyo | 26 | 18 | 30.8% |
| Paris | 24 | 19 | 20.8% |
| London | 22 | 21 | **4.5%** |
| Sao Paulo | 24 | 23 | **4.2%** |
| **Pooled** | **144** | **106** | **26.4%** |

Nearly 3 in 4 backtested city-days across the whitelist produced ZERO tradeable confirmation of the actual
winning bracket -- not because the free feed disagreed with the outcome (2a says it essentially never does),
but because the sustained, margin-cleared extreme never climbed far enough into the settled bracket's own
qualifying sub-range before the day's obs ran out. Mechanism, confirmed by the per-city spread above: margin
(1°F / 0.5°C, unchanged from Kalshi's calibration) combined with a NARROW bracket (2°F for Chicago, 1°C for
the international cities -- versus Kalshi's typically wider-spaced uncapped thresholds) consumes a large
share of the bracket's own width as a "dead zone" near its lower edge, and hourly-cadence METAR (the only
free feed for 5 of 6 cities) systematically under-reports the true peak by roughly one hour's worth of
temperature change (the sustain-3 rule, run on ~60-minute-spaced points, takes the min of only 2 adjacent
hourly readings -- near a smooth diurnal peak that pair-min sits meaningfully below the true peak). Chicago
and Mexico City, whose diurnal curves evidently swing further past their bracket's lower edge before
flattening, clear this bar close to half the time; London and Sao Paulo essentially never do at whole-city
scale in this sample.

**More of the same kind of data will not fix this for London, Paris, Sao Paulo, or Tokyo.** The dead zone is
geometric (margin vs. bracket width) and the under-reporting is a property of hourly cadence itself, not
sample-size noise -- IEM's 1-minute ASOS archive, the only fix, is confirmed unavailable for these 4
international stations, free or otherwise. **It plausibly COULD be fixed for Chicago**, whose station (KORD)
genuinely is in IEM's 1-minute network (`pmkt_gap_study.py` already reads it) -- this script deliberately
used the coarser hourly feed for Chicago too, purely for cross-city apples-to-apples comparability. A
Chicago-only rerun on the true 1-minute feed is the single most promising, cheapest next step; see below.

---

## 5. What would move this to GO or a clean NO-GO

1. **Chicago-only, on its own true 1-minute ASOS feed** (not the hourly proxy used here for
   cross-city consistency). If signal coverage rises materially above 40.9% on 1-minute cadence -- plausible,
   since the under-reporting mechanism in section 4 is specifically a hourly-cadence artifact -- Chicago
   alone could clear a GO bar on a single US city even though the international leg cannot. This is cheap:
   same script, same rungs, swap `fetch_iem_routine` for `fetch_asos_1min` (already written in
   `pmkt_gap_study.py`, reusable) for `chicago` only.
2. **A genuinely finer international feed**, if one exists. This study did not find one (IEM's 1-minute
   archive is confirmed US-only; the Hong Kong Observatory precedent in `pmkt_settlement_basis.md` shows
   some non-US met agencies publish their own finer feeds, e.g. `data.weather.gov.hk` -- not yet checked
   for London/Paris/Sao Paulo/Tokyo's own national weather services, out of scope here). Absent that, the
   international 5/6 of this whitelist stays STILL-BLOCKED regardless of sample size.
3. **A larger, dedicated EV sample** on whichever subset clears (2), since 31 priced fires is far too thin
   to trust the +0.43c/ct reweighted estimate at Kalshi's level of confidence -- this is a sample-size
   problem, unlike (1)/(2), and WOULD be fixed by simply running more days once coverage is high enough to
   generate them.
4. A true historical-ask source (a CLOB book-snapshot archive, not `prices-history`) would remove the
   spread-proxy caveat in section 3 -- not available today via any public endpoint found.

---

## 6. Operator-decision reminders (not resolved here -- flagged for direct operator verification; no
trading code was built by this study)

- **Wallet/USDC/CLOB stack.** Unchanged from `pmkt_gap_study.md`: Polymarket's global venue (the one this
  entire study, and the earlier two, pulled data from -- `gamma-api.polymarket.com` / `clob.polymarket.com`)
  requires an Ethereum-compatible wallet, USDC funding on Polygon, and EIP-712 order signing. None of
  `kalshi_exec.py` applies. This is new infrastructure, not a config change, regardless of the verdict above.
- **US-person access changed materially since the last study and needs the operator's own read, not an
  assumption carried over.** As of this run (2026-07-19): the venue this study measured
  (`polymarket.com`, wallet-based, no KYC) remains geo-blocked to US persons per its 2022 CFTC settlement.
  Separately, Polymarket acquired QCX LLC (a CFTC-registered exchange/clearinghouse) in mid-2025; the CFTC
  issued an Amended Order of Designation on 2025-11-25 letting "Polymarket US" (QCX, full KYC, USD-denominated,
  brokerage-intermediated -- a DIFFERENT product with a DIFFERENT stack from everything measured in this
  study) open to US persons, starting with sports markets in December 2025. **Whether Polymarket US's
  regulated product lists the same city temperature ladders this study backtested is not established here**
  -- if the operator is a US person (this session's context suggests so), the FIRST question to answer
  before any of the above matters is which of these two products (if either) is both legally accessible and
  actually lists weather ladders, since they are not interchangeable: different KYC/auth, different
  settlement currency, and (unverified) possibly different or absent weather-market coverage. A new CFTC
  inquiry reportedly opened in June 2026 per public reporting -- another reason to check current status
  directly rather than rely on this snapshot.
- **This study exercised the global venue's public read-only APIs only** (Gamma + CLOB market data, no
  auth, no orders) -- it says nothing about whether those specific endpoints, or equivalent ones, exist on
  Polymarket US.

---

## 7. Bottom line

`pmkt_settlement_basis.md` measured which cities are basis-sound. `pmkt_gap_study.md` measured that a real,
decaying price gap exists but left the false-lock rate and sample size as open items. This phase closes
both: **the false-lock rate on the whitelist, run through the actual deployed rule, is excellent (0/745,
Kalshi-grade)**, and a **loss-inclusive EV estimate is plausibly positive and larger than Kalshi's own
edge, but on too thin a sample (n=31) to trust**. Neither of those is what stops this from being a GO.
**What stops it is that the free feed available for 5 of 6 whitelist cities is too coarse, combined with
the deployed margin, to actually confirm the winning bracket on most days (26% pooled coverage, as low as
~4% for two of the five international cities)** -- a structural, not statistical, limitation that more of
the same backtest cannot fix. Chicago is the one city where the fix (its own real 1-minute feed) is known,
cheap, and available; the international leg needs a feed that, as far as this study could determine, does
not exist for free. **Recommendation: do not build a Polymarket trading harness on this whitelist as
currently fed. If pursuing further, rerun Chicago-only on its true 1-minute ASOS feed as the single next
step before any infrastructure work, and resolve the US-access question in section 6 independently of the
statistics, since it may moot the international leg regardless of what a rerun finds.**
