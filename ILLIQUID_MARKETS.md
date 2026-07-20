# Illiquid / Long-Tail Markets Funnel — 2026-07-20

**Verdict: NULL. Zero survivors.** No sleeve files ship from this funnel; the kill report below
is the deliverable, per house rules ("a null is a fine, final answer").

Scope: non-weather long-tail Kalshi markets, public unauthenticated
`api.elections.kalshi.com/trade-api/v2` only, no orders, no secrets. Thesis under test:
**attention scarcity** — obscure/uncontested series should show wide, persistent spreads that a
patient bot can capture, the way the fund's weather-lock edge captured mechanical-lock scarcity.
This funnel spent one day testing that thesis directly, outside weather, for the first time.

---

## 1. Recon census — where the long tail actually is

Full method and tables: `census.md`, `structural.md` (both shipped alongside this doc as
reproduction artifacts, see §5).

- `GET /series` (single call, `limit` ignored, full catalog returned): **12,022 series**, 18
  categories. Weather/Climate (289 series) excluded per scope — already the fund's mainline.
- `GET /events?status=open` paginated to exhaustion: **7,937 currently-open events / 2,882
  distinct series**, non-weather. This — not the 12k raw catalog, mostly dead tickers — is the
  honest "what's live right now" picture.
- Stratified sample of 143 series (deepest-tail singles + thin 2-4-event series + top-2-by-volume
  contrast set per category) pulled at `/markets?series_ticker=X&status=open&limit=50` for real
  book stats.
- **Contrast confirms the thesis mechanically**: `KXLLM1`, `KXBTCMAXY`, `KXIMPEACH`,
  `KXREDISTRICTING`, `KXFEDDECISION` — all mainstream, contested, 1-2¢ spreads, six-to-seven-figure
  volume. Everywhere Kalshi has a genuine cross-venue price feed or mass attention, spreads
  compress to the minimum, same as weather.
- **15 uncontested series families identified** with real (nonzero) OI/volume sitting behind wide
  (5-83¢) two-sided quotes: broadcast "mentions" markets, slow corporate-KPI trackers, novel
  AI/LLM meta-markets, foreign macro prints, off-cycle elections, novelty/influencer one-shots,
  far-future sports meta-markets, foreign sports leagues, esports map spreads, niche fixed-income
  tenors, regulatory-approval timing, one-off corporate/political events, fresh altcoin momentum,
  human-interest narrative markets, and season-long player-prop crossovers.
- **Trap flagged and avoided**: zero-volume/zero-OI "empty shell" series (`KXBNB`, `KXETH`,
  `KXXRP`, `KXSHIBA` strike grids sitting at the exchange default 0¢/1¢ placeholder) look
  maximally uncontested but have no counterparty at all — not an opportunity, just unlisted
  price discovery. The useful signal is nonzero volume/OI *at* a wide spread, not zero-everything.
- **Limitation carried forward honestly**: this is a single-day snapshot. "Persistent" wide
  spread is inferred from standing OI, not a multi-day time series — exactly the gap the
  backtests in §2 were built to close, and exactly where the API's retention wall (§2) bit hardest.

## 2. Structural-mispricing scan (snapshot arbitrage, not time-series)

Full detail: `structural.md`. Complete-census (not sampled) checks, four patterns from the task
brief, all against real live quotes including the obscure long tail:

| # | Pattern | Coverage | Result |
|---|---|---|---|
| 1 | ME leg-sum ≠ 1 (buy-all / sell-all arb) | all 3,161 open ME events, ≥2 active legs | **Refuted.** Bid-side (sum>1) is real but fee-negative in every case checked (`ceil(7p(1-p))/100` per leg eats it — fees scale with Σp(1-p) across N legs, the mispricing doesn't). Ask-side (sum≪1) is not exhaustive — missing "none of the above" leg, not mispriced. |
| 2 | Nested-cutoff monotonicity (short-horizon bid > long-horizon ask) | 6 candidate nested-horizon families | **Refuted.** No violation at any of the checked thresholds, including the lowest-volume legs. |
| 3 | Fresh-listing far from prior | 561 markets created in trailing 6h | **Inconclusive** — needs an external reference price (spot gold/WTI/CPI) outside the public-API-only scope. Not treated as evidence either way. Addressed via a self-referential reformulation in round-2 ideation (§4). |
| 4 | Mechanical-lock generalized (any series, `close_time` past but `status=active`) | all 64,829 currently active markets | **0/64,829.** Confirms/extends `WX_NEARMISS_DIAGNOSIS.md`: Kalshi transitions status essentially immediately at close; no snapshot-visible stale-quote window on any series. Inherently sub-snapshot — cannot be fully ruled out by a static crawl, but nothing here suggests it exists outside weather either. |

Net: no capturable structural (snapshot) mispricing anywhere in the live order book, popular or
obscure. This ruled out the "free money sitting in the book" version of the thesis and pushed the
funnel toward genuine time-series/behavioral specs (§3).

## 3. Round-1 backtests — pre-registered specs, adversarially verified

Three specs were pre-registered from the census families most likely to harbor a real,
capturable, non-arbitrage edge (mentions markets and the jobless-claims weekly relist), then
backtested against live-pulled data, then independently re-verified against fresh API pulls.
**All three hit the same wall: Kalshi's public API silently truncates historical
market/trade data to roughly the most recent 1-2 events per series** — `/events` lists full
historical metadata, but `/markets?event_ticker=<old event>` returns `markets: []` for anything
older than the most recent finalized event, no error, count=0. This is a genuine data-retention
limit of the public endpoint, confirmed independently by all three specs on three different
series families, not a script bug in any one of them.

### r1s1 — Mention-Open Base-Rate Anchor (KXFEDMENTION, KXHANNITYMENTION)

**INCONCLUSIVE** (pre-registered stop condition triggered — not a pass, no goalpost moved).
Independently re-verified against fresh live pulls of `api.elections.kalshi.com/trade-api/v2`;
all headline numbers reproduce exactly. Only **3 distinct broadcast-event-days** are retrievable
(vs. pre-registered minimum 8): KXFEDMENTION collapses to 1 event (45 markets, all others
`markets: []`), KXHANNITYMENTION has 2. 16 validation entries (need ≥30), win rate 68.75% (Wilson
95% CI [0.444, 0.858]), mean net EV/contract +$0.207 — but day-clustered t-stat is undefined
(**NaN**, 1 cluster, no between-cluster variance) and the mandatory adverse-selection check could
not even be attempted (no non-fired control markets). Both pre-registered gates fail
(n=16<30, event-days=1<8) → fixed INCONCLUSIVE per pre-registration. Full detail: `bt1/results.md`.

### r1s2 — Off-Air Passive Quoting (KXFEDMENTION, KXHANNITYMENTION)

**INCONCLUSIVE** per the pre-registered min-n gate (3 accessible event-days vs. required ≥10),
**with a substantive negative overlay** — confirmed by independent re-verification. Even on the
descriptive full-sample numbers (756 fills, 3 event-days, exploratory only): mean net-of-fee
markout is **negative in every cut** (validation −2.29¢, pooled −4.57¢, both series individually),
and the mandatory pre-air (≤24h) adverse-selection sub-check **fails everywhere it can be
computed** (validation −10.4¢, pooled −4.79¢, must be ≥0 to pass). This is not a "no data, shrug"
null — prints on these markets move toward the true outcome faster than a 12¢-wide passive quote
can track in the hours before broadcast, i.e. informed-counterparty risk, exactly what the
adverse-selection check was built to catch. Treated as functionally dead, not merely unproven.
Full detail: `bt2/results.md`.

### r1s3 — Jobless-Claims Relist Fade (KXJOBLESSCLAIMS)

**INCONCLUSIVE** — pre-registered escape clause fired, independently verified against the live
API and a from-scratch rerun. Only **10 distinct release Thursdays** are reachable (pre-reg
assumed 47 events/100 markets; `/events` lists all 47 but 37 return `markets: []`), against a
floor of ≥15 distinct Thursdays even under the most generous re-split (0 fit weeks). The API data
wall is real, not a script bug: `/events` lists 47 settled KXJOBLESSCLAIMS events correctly by
title/date, but market/trade data is only servable for the 10 most recent. Exploratory-only run
(not a hypothesis test, θ not selected on an independent fit set): n=29/7 Thursdays, win rate
62.07% (Wilson 95% CI [0.44, 0.7731]), mean net EV/contract +$0.101, Thursday-clustered t=1.353 —
explicitly flagged as uninterpretable at 7 clusters. A specific second-order risk was flagged for
any future resumption: the 37 missing weeks straddle the Oct-2025 government-shutdown gap, so
naively concatenating pre/post-shutdown claims later would silently splice a regime break into
the delta model. Full detail: `bt3/results.md`.

### Why all three collapsed the same way

This is the single biggest finding of the round: **the public Kalshi API's historical-data
retention wall is a structural obstacle to backtesting any low-volume, infrequently-relisted
series family**, independent of whether the underlying idea has merit. It doesn't affect
high-volume series (weather, majors) because those get harvested continuously by the fund's live
infra rather than relying on `/markets?status=settled` after the fact. Any future long-tail
research funnel needs either (a) continuous forward-harvesting of target series before a
backtest is attempted, or (b) to accept these series can't clear a rigorous n-floor on the public
API and should be retired rather than re-attempted on the same stunted data.

## 4. Round-2 ideation — pre-registered, not yet backtested

To route around the retention wall, two follow-on specs were pre-registered
(`ideate_round2_leg-dynamics.md`) targeting data that lives *inside a single currently-open
event's own nested market list* (a leg's own `created_time` / `close_time`), rather than
requiring dozens of settled historical cycles of an entire series:

- **Strategy A — Sibling-Anchored New-Leg Mispricing**: within staggered-listing multi-candidate
  speculation events (`KXPRESNOMD-28`, `KX2028DRUN-28`, `KXSCOURT-29`, etc.), test whether a
  newly-added candidate leg's day-1 price sits outside the within-event sibling band implied by
  previously-added legs at a comparable tier, and converges toward it. Pre-registered bar: ≥15
  new-leg instances across ≥4 distinct events, Bonferroni/2.
- **Strategy B — Partial-Leg-Elimination Renormalization Lag**: on the 51 currently-open
  mutually-exclusive events with mixed active/finalized legs, test whether survivor mid-prices
  lag the arithmetic renormalization target implied by an eliminated leg's `close_time`.
  Pre-registered bar: ≥15 elimination instances across ≥8 distinct events, Bonferroni/2.

**These were not backtested in this funnel pass** — pre-registration and feasibility recon only
(both self-flagged their own most-likely-zero-EV failure mode: fitting a noisy few-example
sibling/renormalization band to noise, or measuring a bookkeeping-timestamp artifact rather than
a real repricing lag — the same failure shape that killed structural Patterns 1-2 above). A
follow-up funnel pass should backtest these against fresh candlestick pulls before any claim is
made either way; until then they are neither survivors nor kills, just queued.

## 5. Bottom line for the attention-scarcity thesis

The thesis holds directionally — the census and structural scan both confirm obscure/uncontested
Kalshi series really do sit at wide, real (nonzero-OI) spreads while contested series compress to
1-2¢, exactly like weather. But **wide spread alone is not a demonstrated edge**, and every
concrete mechanism tested this round to convert that spread into tradeable EV either (a) has no
free-arbitrage version once fees are applied (structural Patterns 1-2), (b) cannot be statistically
validated on the public API's retrievable history (r1s1, r1s3), or (c) validates cleanly *and
loses money net of fees with a failing adverse-selection check* (r1s2). Long-tail attention
scarcity outside weather is real as a *description* of the order book; this funnel found no
version of it that is real as a *tradeable edge* on data the public API will actually hand back.

**Honest capacity from this funnel: $0/month.** No sleeve files ship. Nothing here overturns or
should be read as walking back the weather-lock edge — the two domains differ exactly on the
axis that matters: weather has a live, continuously-harvested feed and a mechanical settlement
rule; the long-tail families tested here have neither.

## Reproduction artifacts

All read-only, no orders, no auth, no secrets. Committed alongside this doc:

- `ILLIQ_CENSUS.md`, `ILLIQ_STRUCTURAL_SCAN.md` — full census/structural-scan method, data, and
  per-pattern detail (§1-2 above).
- `ILLIQ_ROUND2_IDEATION.md` — the two pre-registered, not-yet-backtested round-2 specs (§4).
- `illiq_r1s1_mention_anchor.py`, `illiq_r1s1_results.md`, `illiq_r1s1_results.json` — r1s1.
- `illiq_r1s2_offair_quoting.py`, `illiq_r1s2_fetch_trades.py`, `illiq_r1s2_results.md`,
  `illiq_r1s2_results.json` — r1s2.
- `illiq_r1s3_jobless_relist_fade.py`, `illiq_r1s3_results.md`, `illiq_r1s3_results.json`,
  `illiq_r1s3_verify_events.json`, `illiq_r1s3_verify_markets.json` — r1s3, including the
  independent re-verification pull used to confirm the headline numbers.

Raw bulk pulls used only for census construction (multi-hundred-MB `/events`, `/markets`,
`/series` dumps) are not committed — they are reproducible from the scripts above against the
live public API and were intentionally left out of git per the read-only/no-bloat spirit of this
funnel; the `results.md`/`results.json` files are the durable record of what was found and how.
