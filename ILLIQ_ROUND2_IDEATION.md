# Round 2.1 Ideation — Leg-Dynamics Strategies (2026-07-20)

Public API only (`api.elections.kalshi.com/trade-api/v2`, no auth), read-only, polite pacing.
Both specs below are pre-registered before any outcome/EV data is read; the reconnaissance
calls made to write them (feasibility counts, ticker existence, leg-status snapshot) are
data-*availability* checks only, mirroring how `census.md`/`structural.md` were built — no
EV, price-direction, or backtest number was computed or peeked at.

## Why these two

Task brief: bias toward the strongest **structural, non-speed** pattern in `structural.md`
not yet tested. Of its four patterns, #1 (ME sum≠1) and #2 (nested-cutoff monotonicity) are
cleanly refuted (`structural.md`, `ideate_structural-arb.md`); #4 (mechanical-lock
generalized) is both refuted (0/64,829) *and* a speed pattern, already the fund's most
picked-over graveyard topic. That leaves **#3 (freshly-listed markets far from a reasonable
prior)** — flagged inconclusive because judging it needs an external reference price, which
the "public Kalshi API only" constraint rules out in its original form (no live gold/WTI/CPI
feed). Both specs below keep Pattern 3's mechanism — is a *newly seeded* price consistent
with the market's own already-revealed information — but make the reference **self-referential**
(built only from Kalshi's own data), so they stay inside the API constraint while testing a
genuinely new angle Patterns 1/2/4 didn't touch: cross-*time* consistency within one event's
lifecycle, not cross-sectional consistency at a single snapshot.

Both were also explicitly designed around the lesson `bt1`/`bt2`/`bt3` paid for: the public
API only serves full market/trade history for roughly the most recent event(s) per *series*
(older settled events return `markets: []`), which is what forced INCONCLUSIVE on all three
round-1 specs (r1s1-r1s3) regardless of the underlying idea's merit. Both specs here target
data that lives **inside a single currently-open event** (a leg's own creation time, or a
leg's own close_time, both fields present on every market object already in hand) rather than
requiring dozens of *settled* historical cycles of an entire series — so the retention wall
should not apply here the way it did to the mention-market and jobless-claims specs.

Neither series family below (multi-candidate nomination-speculation markets; multi-candidate
elimination races) has been proposed or killed in any prior round.

---

## Strategy A — Sibling-Anchored New-Leg Mispricing

**Target series (staggered-listing multi-candidate speculation markets, Politics/Elections,
non-weather, confirmed live in the full nested-events crawl):** `KXPRESNOMD-28` (46 active
legs, creation-time span 612d), `KX2028DRUN-28` (36 legs, 444d), `KX2028RRUN-28` (33 legs,
444d), `KXVPRESNOMD-28` (45 legs, 491d), `KXSCOURT-29` (38 legs, 601d), `KXPRESPERSON-28` (30
legs, 402d). These are "who will X be" events where new candidate legs get added over months
as speculation grows — verified via `created_time` dispersion within each event's nested
market list, not a snapshot artifact.

**Signal.** Within one event, sort legs by `created_time`. For each newly-added leg, build a
"sibling-implied prior" from the empirical day-1-opening-price and day-5-median-price of
previously-added siblings in the *same event* at a comparable rank/tier (via daily
candlesticks from each sibling's own `created_time`). If the new leg's actual day-1 opening
ask sits clearly outside that within-event sibling band, and subsequently drifts toward the
band over the following days, enter on day 1 in the direction of that drift; exit at
convergence or a fixed horizon (state N days, pre-registered before backtest).

**Backtest plan.** Pull daily candlesticks for every leg (from its own `created_time`
forward) in the ~10-15 staggered-listing events already identified above — this sidesteps the
r1s1-3 retention wall since all target events are currently open (full self-history should be
servable). **Pre-registered success bar:** ≥15 usable "new-leg" instances across ≥4 distinct
events (event-clustered day-of-listing t-test, not leg-clustered, since one event's field
shares macro narrative); Wilson CI on directional hit-rate; net EV/contract after
`ceil(7p(1-p))/100` fee at the actual crossing (ask) price; significance threshold corrected
for 2 specs this round (Bonferroni/2). If usable n < 15 or distinct events < 4 →
pre-registered verdict is INCONCLUSIVE (data-availability escape clause), not forced to a
pass/fail.

**EV mechanism (claimed).** A newly listed minor candidate in a slow, low-attention
nomination-speculation market may initially be seeded at a round-number/anchor price by
whoever lists the ladder, rather than at the price the field's own history implies for a
"just-added long shot" — a brief, low-competition window before narrative-driven order flow
arrives. Distinct from the (already-killed) mentions-market thesis: multi-day attention
window, not sub-minute broadcast reaction.

**Capacity.** Newly added long-shot legs start near-zero OI/volume by construction; new legs
appear irregularly (maybe 1-4/month across the whole watched family) — honest estimate
$10-60/month combined.

**Feasibility.** Daily-cron GH Actions job: diff each watched series' leg tickers against
yesterday's snapshot to detect new `created_time` entries, pull daily candlesticks. No
live/sub-minute monitoring needed; trivial politeness budget.

**Most likely secretly-zero-EV reason.** The within-event sibling reference band is itself
built from very few prior examples (often <5 per event) — nearly as noisy as the thing being
tested, i.e. fitting noise to noise. Also plausible: whoever actually lists a new candidate
leg already conditions the opening price on real news/polling, not blind anchoring, so there
may be no true prior-violation to find — the "sibling band" could be the naive estimator, not
the efficient one.

---

## Strategy B — Partial-Leg-Elimination Renormalization Lag

**Target series.** Full nested-events crawl (`all_open_events_nested.jsonl`, complete
census, 7,939 events) shows **51 currently-open mutually-exclusive events with mixed leg
status** (39 events mixing `active`+`finalized` legs, 12 mixing `active`+`inactive`).
Restricting to non-weather, non-Sports (sports eliminations are near-instant/mechanical —
too close to the already-killed speed thesis), non-Entertainment (thin/noisy awards
dynamics) leaves a Politics/Elections subset with clean, verified `close_time` timestamps per
leg, e.g.: `KXGOVCA-26` (25 legs, most already-finalized carry distinct `close_time`s months
apart, 2 active survivors currently summing to ~1.00 — i.e. *already* renormalized by now,
which is exactly why the test must anchor to each leg's own `close_time`, not "today"),
`KXTXSENOUTCOME-27JAN`, `KXMESENOUTCOME-27JAN`, `KXCAGOVLAMAYOR-26NOV`, `KXSENATEOKD-26`,
`KXTRUMPAGCOUNT-29`, `KXRECCOUNT-27`, `KXLOSEREELECTIONRSEN-2026`.

**Signal.** For each ME event, take each leg's `close_time` as its elimination moment. At that
timestamp, compute the "renormalization target" for the *then-still-active* survivors: their
last pre-elimination mid-prices rescaled to sum to 1 after removing the eliminated leg's
residual mass (pure arithmetic on Kalshi's own last-quoted prices — no external data).
Using daily candlesticks for survivors bracketing that date, measure how many days elapse
before `sum(survivor mid-prices)` closes the gap to the renormalized target. Entry: on the
elimination day, trade survivors toward the target if the gap exceeds the fee-adjusted
threshold; exit at convergence or a fixed horizon.

**Backtest plan.** Universe = the Politics/Elections subset of the 51 already-identified
mixed-status events (a data-availability characterization already in hand, not outcome data).
**Pre-registered success bar:** ≥15 elimination instances across ≥8 *distinct* events (not
leg-clustered — one race like `KXGOVCA-26` can contribute up to 10 simultaneous eliminations,
which must not be treated as 10 independent draws); event-clustered t-test on net EV/contract
after fee at the actual crossing price; Wilson CI on convergence-direction hit-rate;
Bonferroni/2 alongside Strategy A. If usable n < 15 or distinct events < 8 → pre-registered
verdict is INCONCLUSIVE.

**EV mechanism (claimed).** When a candidate's fate becomes clear enough that Kalshi stops
quoting their leg, the handful of participants watching an obscure multi-candidate race may
not immediately re-price survivors to absorb the freed probability mass, especially for a
minor eliminated candidate whose removal is barely newsworthy. Counterparty on a post-
elimination trade is a stale/passive quoter, not someone who just watched the same event and
repriced instantly.

**Capacity.** Only 51 mixed-status events exist in the entire open catalog today, and
eliminations cluster heavily within single high-profile races (10 of `KXGOVCA-26`'s are
correlated, not independent) — small, lumpy, calendar-clustered around primary/filing
deadlines. Honest estimate $20-100/month.

**Feasibility.** Daily-cron GH Actions job: diff each watched ME event's leg statuses vs.
yesterday's snapshot, flag newly-finalized/inactive legs, compute the renormalization target
for survivors. No sub-hour reaction required (the hypothesis explicitly claims a multi-day
lag) — trivial politeness budget.

**Most likely secretly-zero-EV reason.** The renormalization target itself is built from
survivor prices that may have already absorbed the elimination as a near-certainty *before*
Kalshi's status field flipped to `finalized`/`inactive` (i.e., price moves first, bookkeeping
status lags price, not the reverse) — in which case there is no real repricing lag to trade,
only an artifact of when a status field updates relative to when the market already
converged. This is the same failure shape that killed Patterns 1-2 (measuring a bookkeeping
artifact, not tradeable behavior) and is the first thing the backtest agent must rule out
before trusting any apparent lag.
