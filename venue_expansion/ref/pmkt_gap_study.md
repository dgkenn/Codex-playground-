# Polymarket repricing-speed + capturability study — does the K-WX mechanical-lock edge exist there?

**Date:** 2026-07-19. **Script:** `pmkt_gap_study.py` (read-only, real API pulls — rerun for current
numbers; the tables below are one snapshot: 15 usable resolved city-days for the historical study,
today's live books for the depth sample). **Follows up:** `wx_new_capacity_scan.md` Q1, which found
Polymarket runs the same daily-temperature bracket-ladder mechanic as Kalshi across 51 cities but
flagged two things as **unmeasured**: (1) basis risk vs Kalshi's NWS-CLI source, and (2) whether
Polymarket's own book reprices as slowly as Kalshi's retail — the entire edge lives in that lag. This
study measures (2) directly with real historical price/obs data and gets a partial, concrete read on
(1) as a byproduct.

## Bottom line up front

**VERDICT: INCONCLUSIVE — a real, decaying price gap does exist post-lock (not NULL/efficient), but
it is NOT validated as a Kalshi-grade tradeable edge (not CONFIRMED either).** The core reason: Kalshi's
edge lives in a genuinely *mechanical* certainty (crossing a one-sided threshold is monotonically
irreversible — the running max only goes up). Polymarket's bracket ladder has **no equivalent
instantaneous certainty** — a rung inside the bracket can still be pushed out the top by a later-day
temperature rise, so there is no real-time signal as clean as Kalshi's. The best available proxy tested
here (30-minute "no new record" confirmation) shows a real average gap that shrinks over the next hour,
but with enough noise, non-monotonicity, and unmeasured false-lock risk that a paper harness isn't yet
justified without more data. See "What would move this to CONFIRMED or NULL" at the end.

---

## Step 1 — Historical gap-decay study (the core measurement)

### Method

For 11 US cities Kalshi also trades (the overlap set from `wx_new_capacity_scan.md`), 2 resolved
Polymarket daily-high-temperature events each (2026-07-11 and 2026-07-17 — both fully in the past,
so both Polymarket's own resolution and IEM's 1-2-day-lagged 1-minute ASOS archive are final):

1. **Winner identification** — read directly off Polymarket's own resolved data: the rung whose
   `outcomePrices` is `["1","0"]`. No inference needed here; this is ground truth from the venue itself.
2. **Lock-time reconstruction** — pulled the SAME true one-minute ASOS feed
   (`mesonet.agron.iastate.edu/.../asos1min.py`) `kalshi_weather_nowcast.py` uses, applied the repo's
   own glitch filter verbatim (`clean_station_obs`'s abs-cap + isolated-spike rule, reused not
   reimplemented), then computed the running max for the local calendar day. Two lock definitions
   were computed and compared:
   - **naive_lock** = timestamp of the observation that sets the day's *final* running max — only
     knowable in hindsight, not a real trading signal, reported for comparison only.
   - **confirmed_lock** = naive_lock + 30 minutes with no new record — the honest, real-time-computable
     proxy actually used for the gap measurement (a trader watching the live feed could act on this).
     This is the closest bracket-ladder analog of Kalshi's threshold-cross, but note it is NOT the
     same kind of guarantee (see verdict above) — it is a confirmation heuristic, not a mechanical lock.
3. **Price gap** — pulled Polymarket's own CLOB `prices-history` (`market=<clobTokenId>&startTs=&endTs=&fidelity=1`,
   ~1-minute resolution) for the winning rung's YES token and read `gap(t) = 1 - price(t)` at
   confirmed_lock and at +2/+5/+10/+30/+60 min — the direct Polymarket analog of the repo's
   `decay_gap_by_min` (`archive/code/phase2_trackA_price.py`).

**Data-quality guards actually enforced (not assumed):** a completeness check rejects any city-day
whose 1-minute feed cuts out more than 3 hours before local day-end — this caught a real bug on the
first pass (KLAX/2026-07-17's feed dropped at 15:07Z, producing a fake 73°F "day max" against the
true 86-87°F winning bracket). After the guard, **7 of 22 candidate city-days were skipped** for
incomplete station data (Atlanta 7/17, Denver both dates — Denver's Polymarket settlement station,
see below, isn't in the 1-minute ASOS network at all — LA 7/17, Miami 7/11, NYC both dates), leaving
**15 usable fires**.

### Real finding, not assumed: 4 of 11 cities settle on a DIFFERENT station than Kalshi

Reading each event's own `resolutionSource` (a Wunderground station-history URL) instead of reusing
`kalshi_weather_nowcast.CITY_CONFIG`'s station map caught this directly:

| City | Polymarket station | Kalshi station | Same? |
|---|---|---|---|
| Chicago | KORD (O'Hare) | KMDW (Midway) | **NO** |
| Dallas | KDAL (Love Field) | KDFW (DFW Intl) | **NO** |
| Denver | KBKF (Buckley/Aurora) | KDEN (Denver Intl) | **NO** |
| NYC | KLGA (LaGuardia) | Central Park COOP | **NO** |
| Atlanta, Austin, Houston, LA, Miami, SF, Seattle | same airport | same airport | yes (7/11) |

This means the two venues' "same city" ladders are not basis-interchangeable even for the 7 that
happen to share a station today — any live monitoring build has to use Polymarket's own
`resolutionSource` per event, not a copy of the Kalshi map.

### Decay table (n=15, gap = 1 − price of the winning rung)

| t (min after confirmed_lock) | n | mean gap | median gap | mean retention (gap(t)/gap(0)) |
|---|---|---|---|---|
| 0  | 15 | 0.382 | 0.435 | 1.000 |
| 2  | 15 | 0.371 | 0.320 | 0.914 |
| 5  | 15 | 0.347 | 0.290 | 0.872 |
| 10 | 15 | 0.278 | 0.225 | 0.799 |
| 30 | 15 | 0.228 | 0.110 | 0.556 |
| 60 | 15 | 0.145 | 0.060 | 0.343 |

- 13/15 (87%) fires had a real gap (>2c) at the confirmed-lock instant; mean gap when real = 0.440.
- Gap DOES shrink on average (retention 1.00 → 0.34 over the next hour) — directionally the shape
  Kalshi's edge lives in.
- **But it is not clean or monotonic.** Per-fire paths (full table in the script's stdout / cache):
  6/15 still had gap > 0.10 a full hour after confirmed_lock; 1/15 had the gap **grow net** over the
  next hour instead of shrink (Chicago 7/17: 0.57 → 0.94); several others swing wildly mid-window
  before eventually converging (SF 7/11: 0.44 → 0.06 → 0.46 → 0.12 → 0.02). That is real price
  volatility on a rung whose eventual winner we already know from the resolution — i.e., the market
  was still genuinely re-pricing uncertainty (or just thinly/noisily quoted), not smoothly bleeding
  out a known-certain outcome the way Kalshi's book does.
- Basis check (IEM ASOS whole-degree day max vs the Polymarket winning bracket, now on the CORRECTED
  per-venue stations): 8/15 agree (53%). Of the 7 disagreements, 6 show ASOS reading 2-4°F **warmer**
  than the winning PM bracket — the same direction and rough magnitude as the repo's own documented
  ASOS-vs-official-settlement warm bias for several stations (`kalshi_weather_refined.py`'s
  per-station margin correction, e.g. KPHX/KLAX/KMIA/KSEA). One outlier (Austin 7/17, ASOS 84°F vs a
  94-95°F winner) is almost certainly a feed-completeness artifact from the same class of gap noted
  above, not a real basis disagreement — flagged, not smoothed over.

### Rough EV read (NOT a validated, loss-inclusive number like Kalshi's)

Buying the winning rung at the confirmed-lock price and holding to settlement nets `gap(0)` per
contract before fees: mean **0.38/ct**, median **0.44/ct** in this sample. Two things this number is
missing that Kalshi's confirmed +0.15–0.21/ct **is not** missing:

1. **Survivorship** — every one of these 15 fires is a known winner (selected via Polymarket's own
   resolved outcome). This backtest never asks "does the 30-min-no-new-record rule ever confirm the
   WRONG bracket?" (i.e., a false lock, followed by a later-day heat spike that pushes the true max
   into a higher bucket). Kalshi's number is loss-inclusive (TRACK B, multi-year, ~0.4% conditional
   loss rate, measured); this Polymarket number has **no loss side measured at all**. That is the
   single biggest gap between "gap exists" and "edge is real."
2. **Mid/last-trade vs executable ask** — `prices-history` returns a midpoint/last-trade series, not
   the resting ask a marketable buy order actually pays. Today's live near-lock spreads (Step 2, below)
   ran 0.1–27c (median 3.3c) — on the wide end, a chunk of the measured gap would be eaten by crossing
   the spread, especially on the thinner rungs.

Net: the magnitude looks bigger than Kalshi's, but it isn't apples-to-apples — it is a "does a gap
exist" measurement, not a backtested, risk-adjusted EV.

---

## Step 2 — Live depth sample (today, 2026-07-19, same 11 cities)

For each city's currently-open ladder: the **near-lock** rung (highest `bestAsk`, i.e. closest to
converged) and a **pre-lock** rung (bestAsk closest to 0.50, i.e. mid-ladder, still genuinely
undecided), CLOB order-book depth within 2c of best ask.

| City | Rung | bestAsk | bestBid | spread | depth ≤2c of ask ($) |
|---|---|---|---|---|---|
| Atlanta | 90-91°F (near-lock) | **none — empty ask book** | 0.999 | — | $0 |
| Atlanta | 81°F or below (pre-lock) | 0.001 | — | — | $59 |
| Austin | 94-95°F (near-lock) | 0.87 | 0.80 | 0.07 | $53 |
| Austin | 96-97°F (pre-lock) | 0.22 | 0.11 | 0.11 | $5 |
| Chicago | 78-79°F (near-lock) | 0.97 | 0.96 | 0.01 | $592 |
| Chicago | 80-81°F (pre-lock) | 0.05 | 0.03 | 0.02 | $3 |
| Dallas | 98-99°F (near-lock) | 0.977 | 0.941 | 0.036 | $441 |
| Dallas | 100-101°F (pre-lock) | 0.04 | 0.02 | 0.02 | $0.06 |
| Denver | 98-99°F (near-lock) | 0.979 | 0.953 | 0.026 | $762 |
| Denver | 100-101°F (pre-lock) | 0.03 | 0.02 | 0.01 | $0.30 |
| Houston | 94-95°F (near-lock) | 0.94 | 0.93 | 0.01 | $236 |
| Houston | 96-97°F (pre-lock) | 0.07 | 0.05 | 0.02 | $5 |
| Los Angeles | 76-77°F (near-lock) | 0.89 | 0.81 | 0.08 | $40 |
| Los Angeles | 78-79°F (pre-lock) | 0.20 | 0.09 | 0.11 | $11 |
| Miami | 90-91°F (near-lock) | 0.999 | 0.998 | 0.001 | $1,377 |
| Miami | 92-93°F (pre-lock) | 0.002 | 0.001 | 0.001 | $5 |
| NYC | 80-81°F (near-lock) | 0.979 | 0.949 | 0.03 | $788 |
| NYC | 82-83°F (pre-lock) | 0.059 | 0.022 | 0.037 | $7 |
| San Francisco | 64-65°F (near-lock) | 0.929 | 0.662 | 0.267 | $104 |
| San Francisco | 66-67°F (pre-lock) | 0.25 | 0.08 | 0.17 | $3 |
| Seattle | 76-77°F (near-lock) | 0.54 | 0.47 | 0.07 | $30 |
| Seattle | 78-79°F (pre-lock) | 0.48 | 0.30 | 0.18 | $29 |

**Aggregate:** near-lock depth ≤2c: n=11, median **$236**, mean **$402**, range $0–$1,377. Pre-lock
depth ≤2c: n=11, median **$5**, mean **$12**, range $0–$59. Spread across all sampled rungs: median
3.3c, mean 6.4c.

Atlanta's near-lock rung shows the exact "locked, empty ask book" state `wx_new_capacity_scan.md`
first spotted on a Hong Kong rung: bestBid 0.999, **no ask at all** — the outcome is effectively
decided and nobody is selling, so there's literally nothing to buy into on that specific rung right now.

### Comparison to Kalshi (fresh pull, same day, `wx_capacity_probe.py --report`)

Live Kalshi near-lock fillable YES depth (ask ≤98c), 33 rung-snapshots across its 20 cities today:
**median 538ct, mean 944ct, p25 143ct, p90 1976ct** (converting at a rough ~0.93 average near-lock
price: median ≈$500, mean ≈$878, p25 ≈$133, p90 ≈$1,838 notional).

| | Kalshi (today, live) | Polymarket (today, live) |
|---|---|---|
| Near-lock depth, median | ~$500 notional | $236 |
| Near-lock depth, mean | ~$878 notional | $402 |
| Near-lock depth, max sampled | ~$4,900 (NYC) | $1,377 (Miami) |
| Half-life / decay speed | measured 3.3 min pooled (archive backtest) | not cleanly measurable here — see verdict |
| Confirmed capacity | $1.1-1.6k/wk (loss-inclusive, forward-validated) | not computable yet (no loss-rate data) |

Read: Polymarket's near-lock depth is real and the same order of magnitude as Kalshi's — roughly
**half the median, similar max** — matching `wx_new_capacity_scan.md`'s qualitative call ("hundreds-
to-thousands $ per rung, not obviously deeper or thinner") now with fresh numbers on both sides.
Pre-lock rungs are much thinner on both venues (that's expected and fine — you don't need depth on
rungs you're not trading yet).

### Rough gross-notional capacity envelope (explicitly NOT an EV/profit number)

11 overlap cities × 7 days/wk × (68% station-data-available rate measured above, 15/22) × (87%
real-gap rate measured above, 13/15) × $236 median near-lock depth ≈ **~$10.7k/wk gross fillable
notional**, *if* every one of those fires is genuinely correct and fully executable at the sampled
depth. This is presented only as a rough ceiling on how much capital COULD touch this product per
week under favorable assumptions — it is **not** risk-adjusted, does not subtract false-lock losses
(unmeasured — see below), and does not account for ask-side execution cost (vs the mid/last-trade
price used in Step 1). It is roughly an order of magnitude above Kalshi's confirmed $1.1–1.6k/wk
*specifically because* it has none of the netting-out that number has: no loss rate, no spread, no
false-lock discount, on top of a 15-fire sample. Read it as "the depth is there if the edge turns out
to be real," not as a profit projection — the gap between this ceiling and a defensible number is
exactly the false-lock-rate + execution-cost work item 2/3 below.

---

## Execution realities (honest flags, no trading code built here)

- **Different stack entirely.** Kalshi is a cash-account CFTC-regulated exchange with API-key auth.
  Polymarket is a crypto-settled CLOB: trading requires an Ethereum-compatible wallet, USDC funding
  (on Polygon), and a CLOB API key/signature flow (EIP-712 order signing) — none of the K-WX repo's
  existing execution code (`kalshi_exec.py`) applies. This would be new infrastructure, not a config
  change.
- **Compliance/geo-restriction question, unresolved here.** Polymarket has historically restricted or
  geoblocked US persons on its main product; the current status (as of any live deployment date)
  needs to be checked by the operator directly against Polymarket's terms of service and any
  applicable US regulatory guidance before committing capital — this is explicitly **flagged, not
  answered**, and this study does not attempt to resolve it.
- **Settlement-source basis risk is now partially measured, not just flagged.** Raw ASOS-vs-PM-bracket
  agreement in this small sample is ~53% at whole-degree resolution, with a consistent small
  (2-4°F) warm bias in the ASOS-vs-Wunderground direction that matches known station-bias patterns
  already documented for the Kalshi side — but n=15 is too small to trust as a stable false-lock
  rate, and one outlier (Austin) looks like a feed-artifact rather than a real basis gap. This needs
  the same multi-year treatment `kalshi_wx_settlement_basis.py` gave the Kalshi side before it can be
  called measured.
- **Free 1-minute ASOS feed coverage is incomplete for Polymarket's own settlement stations.**
  Denver's Polymarket station (KBKF) isn't in IEM's 1-minute ASOS network at all; several other
  station-days had mid-day transmission gaps. A live monitoring build for Polymarket cannot assume
  the same feed reliability the Kalshi side gets from its 20-city set — this is new integration work,
  not a drop-in reuse.

---

## What would move this from INCONCLUSIVE to CONFIRMED or NULL

1. **Scale the historical sample** (60-100+ city-days, same technique) to check whether the observed
   mean-retention decay curve (1.00 → 0.34 by +60min) is a stable pattern or noise from n=15 — right
   now the 2/15 non-monotonic fires and wide per-fire spread make this genuinely uncertain.
2. **Measure the false-lock rate.** This study only ever looked at known winners. The single biggest
   unmeasured risk is: does a "30-min no new record" signal ever fire on a bracket that a later-day
   temperature swing subsequently pushes out of? Kalshi's Track B (multi-year, all-season) answered
   this for the threshold family; nothing equivalent exists yet for Polymarket's bracket family.
3. **Replace mid/last-trade price with real executable-ask cost** in the gap measurement (pull CLOB
   `book` snapshots at the same historical timestamps, not just `prices-history`) to get a true,
   spread-inclusive entry cost.
4. **Resolve the operational blockers** (wallet/USDC/API-key infra, geo/compliance status) — separately
   from the statistical question, since they gate whether a validated edge could even be deployed.

Until (1)-(3) land, this is a real, not-previously-measured, structurally-DIFFERENT-from-Kalshi signal
worth tracking, but not yet a green light for a paper harness.
