# Phase 3: Does the settlement-nowcast/lock edge generalize to deeper Kalshi markets?

Generated 2026-07-18. All numbers pulled live from `https://api.elections.kalshi.com/trade-api/v2`
(no auth) during this run, plus one auxiliary free source (open-meteo archive API, used only as a
rough precip cross-check, not as ground truth).

**The confirmed edge, restated:** once a publicly-observable value mechanically locks a market's
outcome (temperature running max/min clears the strike), buy the cheap YES before slow retail
finishes repricing to ~100c. Validated on weather: +0.207/ct, 99.65% win, t=37.4 (deployable subset,
`phase2_trackA_price_results.md`), but capacity-capped at **~$460-$12,530/week** depending on
fill-depth assumptions (median resting size at best price 8.5 contracts, 32 within 1c, 90.5 within
2c; only ~39% of fires have any resting depth at all) — the task's "$1-1.6k/week" is the realistic
middle of that range.

Goal here: test whether the SAME mechanic exists on deeper Kalshi books, honestly, with nulls
allowed.

---

## Candidate A — Sports in-game (MLB game-winner markets, KXMLBGAME)

**Book depth vs weather — concrete numbers.**
Pulled live orderbooks on 3 currently-trading MLB games (2026-07-19 slate, mid-game/pregame mix):

| ticker | yes_ask | depth within ~20c of touch | depth at 1c (far OTM) |
|---|---|---|---|
| KXMLBGAME-...SFSEA-SF | 0.40 | 14,820 contracts resting @ 0.34 alone | 846,405 / 925,151 contracts (yes/no @ 0.01) |
| KXMLBGAME-...WSHATH-WSH | 0.54 | 68,294 @ 0.08, 30,751 @ 0.09, thousands at every cent | 916,780 / 870,931 @ 0.01 |
| KXMLBGAME-...LADNYY-LAD | 0.53 | 66,913 @ 0.08, 25,257 @ 0.11, thousands throughout | 906,910 / 879,736 @ 0.01 |

Settled-game lifetime volumes (2026-07-17 slate, pulled from `/markets?status=settled`):
**1.3M–5.0M contracts per side, per single game.** That is roughly **100-1,000x** weather's median
depth (8.5-90.5 contracts) and **10,000x+** its settled 24h-volume scale.

**Is there a capturable, non-sub-second lag?** Directly inspected 1-minute candlesticks for the last
90 minutes of a settled game (KXMLBGAME-26JUL172210SFSEA-SF, closed 2026-07-18T04:54Z, result=yes):

```
03:26  ask=0.70  (82,463 contracts traded that single minute)
03:49  ask=0.87
04:03  ask=0.93
04:04  ask=0.99  (69,483 contracts traded that minute)
04:07  ask=1.00  (14,603 contracts traded that minute)
04:14  ask=1.00 (steady)
```

The price climbs **smoothly and continuously** with the game state from 70c to 99c over ~40 minutes,
then closes the last 99c→100c gap in **~3 minutes**, with 14,600-69,500 contracts trading *at* 99c
during that exact window — i.e. the market was already efficiently priced near-certain well before
the literal final out, not sitting cheap-while-locked. No multi-minute "stale, mechanically-locked-
but-still-cheap" window was observed at 1-minute resolution; if a residual gap exists it is on the
scale of seconds, not minutes.

**Data-feed feasibility, honestly assessed.** To trigger a "near-locked" signal independent of
Kalshi's own price (the whole point of the nowcast principle) requires a live score/inning/game-
clock feed as a separate dependency — not built, not free at low latency (real-time play-by-play
APIs with sub-5-second latency are commercial/paid, e.g. Sportradar/Genius Sports tiers). And even
with that feed, the observed convergence speed (~1-3 minutes at coarse resolution, plausibly faster
intra-minute) means we'd be racing professional live-win-probability bots that already have faster,
paid access to the same underlying game state. This is a sub-minute microstructure race, not a
day/minute-scale nowcast — a fundamentally different (and much more expensive) infra problem than
polling METAR every few minutes.

**Verdict: NULL for the nowcast/lock principle.** Sports has by far the deepest books on the
platform (confirms the premise), but that same depth comes hand-in-hand with efficient, fast,
well-capitalized flow that closes any "mechanical near-certainty" gap before it's exploitable at our
latency. The task's stated concern — "the edge may already be arbed to zero" — is directly borne
out. Book depth is real; capturable lag is not, at the ~2-5 minute action-latency we can actually
build.

---

## Candidate B — Rain / precipitation

Two structurally different Kalshi rain products exist. Findings differ sharply between them.

### B1. `KXRAIN` — daily binary "will it rain in city X today?"
- **Existence:** confirmed, but this is a brand-new pilot series. Across its ENTIRE history the API
  returns only **2 event-days ever** (2026-07-15 and 2026-07-17); no 2026-07-16 or 2026-07-18 event
  exists. Too sparse to build any track record or trust as a running capacity source right now.
- **Depth when it does run:** median 81 contracts/market, mean 424 (skewed by 1-2 cities) across 20
  cities on the one day sampled — thinner than or roughly comparable to weather temperature
  markets, not a capacity upgrade.
- **Lock mechanic:** exists in principle (any measurable precip locks YES: `"strictly greater than 0
  inches"`), but the market **closes early** the instant rain is detected (`can_close_early: true`),
  which compresses or eliminates the repricing window we'd want to trade into.
- **Verdict: NULL / not-yet-real.** Interesting mechanic, unusable today — too new, too thin, too
  few event-days, and early-close removes the post-lock lag window even if it existed.

### B2. Monthly cumulative rain-threshold ladders (`KXRAINDALM`, `KXRAINCHIM`, `KXRAINHOUM`,
`KXRAINMIAM`, `KXRAINAUSM`, `KXRAINDENM`, `KXRAINNYCM`, `KXRAINSEAM`, `KXRAINSFOM`, `KXRAINLAXM`) —
~9-10 cities, ~7 threshold rungs each ("total precip this month > N inches"), settled via NWS
Climatological Report / weather.com. **This is the real find.**

**The lock mechanic exists and is identical in kind to weather:** monthly precipitation only
accumulates — once month-to-date rain clears a rung, that rung's YES is mechanically locked and can
only settle in-the-money, exactly like the running max/min clearing a temperature strike.

**Depth — materially deeper than weather.** Live orderbook sweep on a partially-priced (not-yet-
fully-locked) rung, `KXRAINCHIM-26JUL-4` (yes_ask 0.92, yes_bid 0.62 — a 30c spread, i.e. high
probability but not yet certain):

```
no_dollars (defines yes_ask levels):  0.01¢×129.8, 0.05¢×800, 0.06¢×174.3, 0.08¢×31
  -> sweeping the whole visible book from 92c to 99c costs ~1,135 contracts / ~$1,080 notional
```
Open interest across the currently-open rungs: **1,000-40,000+ contracts per market**; lifetime
volumes 2,000-70,000+ contracts. That is **10-100x** weather's median depth (8.5 at best / 32 within
1c / 90.5 within 2c).

**Is there a capturable lag? Yes — slower and more forgiving than weather's 3.3-minute half-life.**
Scanned daily candlesticks across all 9-10 cities' currently-open plus the last two settled months
(May-July 2026) for "price jumps from <90c to ≥98c within one bar" — found **28 distinct lock events**
over ~10.6 weeks (≈2.6 events/week pooled across covered cities), median jump-day volume ≈1,973
contracts. Directly inspected one at 1-minute resolution, `KXRAINDALM-26JUL-1` (Dallas, "> 1 inch
this month"), 2026-07-13:

```
11:07  ask=0.77  (stable for hours before this)
11:10  ask=0.75  vol=690.8   <- price actually DIPS on a noisy print, then:
11:13  ask=0.88  vol=539.3
11:18  ask=0.95  vol=859.0
11:41  ask=1.00  vol=60.0    <- fully locked
```
The transition from 75c to fully-locked 100c took **~34 minutes**, with ~2,089 contracts trading
*during* the climb (not just after) at an average price well below 100c. That is a genuinely
minute-scale, human/bot-actionable window — **~10x slower to close than weather's 3.3-min half-life**
— comfortably inside a 2-5 minute action-latency budget.

**Critical honesty check — false-lock rate.** Cross-referenced 18 of the 28 "jumped to ≥98c" events
(the ones from already-settled months) against their actual final settlement result:
**2 of 18 (11%) settled NO** despite the market price briefly touching 98-100c
(`KXRAINDALM-26MAY-3`, `KXRAINMIAM-26JUN-4`). This means a naive strategy that triggers off
**Kalshi's own price** crossing 90-98c is NOT a true mechanical-lock signal for rain the way running-
max/min directly compared to the strike is for temperature — it is a probabilistic near-certainty
signal that occasionally reverses. A real implementation must trigger off an **independently
observed** cumulative-precipitation feed (the same class of infra already built for temperature —
`aviationweather_metar.py`'s METAR precip remark groups, e.g. `Pxxxx`/`6xxxx` groups — extended to
track running MTD accumulation vs. the exact rung, with the same trace-amount and basis-risk
handling already documented for the temperature bot in `kalshi_wx_settlement_basis_report.md`), not
off Kalshi's price momentum. This is real, buildable, reuses existing infra — but it is NOT yet
built, and skipping this step would occasionally buy a "locked-looking" 98c YES for a full loss.

**Frequency / seasonality caveat.** All 28 observed lock events came from cities/months with
meaningful rain (Dallas, Chicago, Houston, Miami, Austin, NYC, plus one each Denver/Seattle); **zero**
events in the arid-city series (LA, SF, Phoenix) over the same window. The ~2.6 events/week pooled
rate is a wet-season, warm-months figure across the ~9-10 covered cities — likely an upper bound,
not a year-round steady-state.

**Rough weekly capacity, using the same conservative haircut logic as the weather study** (partial,
not full, capture of the swept book given the ~34-min window, similar spirit to weather's 39%-
fillable / 1-2c-slippage treatment): **~2.6 events/week x ~$800-1,500 realistically-capturable
notional per event ≈ roughly $1,500-4,000/week**, additive to (not multiplicative with) the weather
sleeve, since it trades different cities/instruments on the same underlying nowcast principle.

**Verdict: weak-positive / real but modest.** Genuine same-family mechanic, materially deeper books,
and a slower (more capturable) decay than weather. But lower event frequency, seasonal, and requires
a real (buildable, not yet built) independent precip feed to avoid an observed ~11% false-lock rate
if naively price-triggered. Net effect: a **1-3x add-on**, not a step-change unlock. The always-on
daily binary (`KXRAIN`) is currently too new/thin to count as a capacity source at all.

---

## BOTTOM LINE

| candidate | lock mechanic exists? | books deeper than weather? | capturable lag at 2-5min latency? | data-feed feasibility | net capacity effect |
|---|---|---|---|---|---|
| Sports (MLB in-game) | conceptually, near a blowout/final out | **YES, ~100-1000x** | **NO** — closes in ~1-3 min, likely faster; already arbed | needs paid low-latency play-by-play feed + near-sub-second execution — different infra class entirely | **NULL** |
| Rain, daily binary (KXRAIN) | yes, but early-close compresses it | no (thin, comparable to weather) | untestable — series has only 2 event-days ever | N/A yet | **NULL (too new)** |
| Rain, monthly threshold ladder | **YES, identical mechanic to weather** | **YES, ~10-100x** | **YES, ~34-min half-life observed (slower than weather's 3.3-min)** | buildable by extending existing METAR infra; NOT yet built; ~11% false-lock rate if price-triggered instead of precip-triggered | **weak positive, ~1-3x add-on** |

**Can the nowcast principle break past the ~$1-1.6k/week weather ceiling, and by how much?**

**Mostly no — not by an order of magnitude, from either candidate tested.** The one venue with truly
deep books (sports) is exactly the venue where the mechanic dies, because depth and market
efficiency arrive together: the same liquidity that would fund bigger size is supplied by
participants fast enough to close the "near-certain but not yet 100c" gap before a 2-5 minute-latency
bot can act. The one venue that DOES preserve a capturable multi-minute lag (rain monthly-threshold
ladders) is real and worth building, but its incremental capacity is estimated at only
**~$1,500-4,000/week**, additive, seasonal, and requiring new (though reusable-infra) real-time precip
plumbing before it's safe to trade — call it a plausible **1-3x** expansion of the current ceiling,
not 10x or 100x.

**Combined realistic ceiling (weather + rain, both at their honest/conservative end):** roughly
**$2,000-6,000/week**, versus weather alone at ~$500-1,700/week conservative / up to ~$12,500/week
under the most optimistic same-week fillability assumption already on record. That is a real but
modest lift, not a capacity breakthrough.

**This confirms the premise stated in the task, plainly: K-WX (and now, modestly, K-RAIN) is an
inherently small-capital edge family.** Reaching materially higher aggregate throughput — and
certainly anything like a 10%/day target — requires **stacking multiple orthogonal edges** (different
markets, different mechanisms, different risk factors), not scaling this one nowcast/lock trick into
a deeper venue. The one deep-book venue on Kalshi that exists (sports) is precisely the one this
mechanic does not survive in.
