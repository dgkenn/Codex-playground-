# Track A -- Chicago GO-check on IEM's TRUE 1-minute ASOS feed

Pre-registered check from `ref/pmkt_final_verdict.md` section 5, item 1. Script:
`venue_expansion/tracka_chicago_1min.py`. Full machine-readable results:
`venue_expansion/out/tracka_results.json`. Run date: 2026-07-23.

## Pre-registered bars (fixed before reading any test data)

PASS iff:
- (a) pooled winner-bracket coverage >= 55% **and** its 95% Wilson lower bound > 40.9% (the measured
  hourly-cadence baseline, `pmkt_final_verdict.md` section 4's Chicago row).
- (b) the deployed rule's (`locked_orders`) false-lock count == 0 on the 1-minute streams.
- (c) coverage computed identically to `pmkt_final_verdict.py` section 4 (margin=1.0F, sustain-3, same
  qualifying sub-range/bracket-entry definition) -- only the feed cadence changes.

Universe: every available Chicago (KORD) ladder day, 2026-02-06 (earliest Gamma listing) through
2026-07-21 (last fully-settled). Target n>=60 usable days, every skip reported with reason.
Non-gating: priced-fire EV, verdict script's exact win/loss-fire construction + item-2b base-rate
reweighting.

## Method

`tracka_chicago_1min.py` is a restricted copy of `ref/pmkt_final_verdict.py`: same bracket parsing, same
deployed lock rule (`sustained_extreme` + `locked_orders`, sustain-3, glitch filter, 1.0F margin), same
"entries" bracket-band-touch extension, same false-lock scoring, same ask-proxy + Polymarket-fee EV
construction, same Wilson CI formula. The **only** substantive change: the obs feed driving the walk is
IEM's true 1-minute ASOS archive (`asos1min.py`) instead of the hourly-ish "routine" METAR archive
(`asos.py`).

Two disclosed, non-arbitrary adaptations (see script docstring for full reasoning):
- **Deployed-rule provenance.** `kwx_runner.py` (the live runner `pmkt_final_verdict.py` imported
  `sustained_extreme`/`locked_orders` from) is a live-path file, absent from this research branch by
  design. `venue_expansion/kwx_lock_rule.py` reproduces those two functions **byte-identical** (verified
  by direct text diff), extracted from `kwx_runner.py` at commit `bd90504` (the exact commit paired with
  `pmkt_final_verdict.py`). No live/execution code was pulled in.
- **Completeness-guard cadence adaptation.** The hourly guard (>=15 obs/day, <=4h end-gap) was explicitly
  hourly-tailored. For 1-minute cadence this run uses the guard `pmkt_gap_study.py` itself established for
  this exact feed: >=100 obs/day, last obs within 3h of local day-end.
- **Sampling density.** The prior study strided ~22 samples/city for 6-city comparability. This run
  samples **every day** (stride=1) over the full window, per the task's pre-registered universe.

Mind the known IEM `asos.py` exclusive-end-date bug (padded by 1 day in `fetch_iem_routine`, unchanged
from the prior script). `asos1min.py` uses a continuous `sts`/`ets` timestamp range rather than
whole-day `day1`/`day2` buckets, so that specific bug does not structurally apply there -- confirmed
empirically (sanity check B) rather than assumed.

## Sanity checks (both required before trusting the primary run)

**A -- harness parity.** Rerun the *hourly* feed, chicago-only, with the prior study's exact sample
stride (`TARGET_SAMPLES_PER_CITY=22`) and end date (2026-07-18):

```
usable=22  never_entered=13  coverage=40.9%
EXACT MATCH to pmkt_final_verdict.md's published Chicago row: True
```

Exact match on both the raw counts and the published coverage figure. The harness (bracket parsing,
sustain-3/margin walk, entries logic) reproduces the prior study bit-for-bit before any new claim is
trusted.

**B -- feed-cadence spot check.** Chicago, 2026-07-15:

```
hourly rows in local day: 24
1-min  rows in local day: 1440
ratio: 60.0x
```

Exactly 60x, confirming `fetch_iem_1min` is genuinely pulling native 1-minute cadence, not a
silently-degraded feed.

## Primary run results

163 candidate days (2026-02-09 through 2026-07-21, +3-day buffer past the earliest Gamma listing).
**67 usable city-days** (96 skipped) -- clears the n>=60 target.

Skip reasons (rough tally): 70 `thin_station_data` (many concentrated in 2026-02-09 through 2026-02-22,
where IEM's 1-minute ASOS archive for ORD returns **zero rows for the whole day** -- see Finding 1
below), 22 `station_feed_gap_near_dayend`, 3 `event_not_found`, 1 `not_resolved_or_unparseable`.

| Metric | Value |
|---|---:|
| Usable city-days | 67 |
| Winner bracket entered | 43 |
| **Pooled coverage** | **64.2%** |
| 95% Wilson CI | [52.2%, 74.6%] |
| Hourly baseline (pmkt_final_verdict.md sec.4) | 40.9% |
| Deployed-rule locks (item 2a), n | 344 |
| Deployed-rule false locks | **0** |
| False-lock rate, 95% Wilson upper | 1.104% |
| Bracket entries (item 2b), n | 309 |
| Entry false rate | 86.08% (95% CI [81.78%, 89.50%]) |
| EV-priced fires | 72 (37 win, 35 loss) of 80 candidate fires |
| Unweighted net EV/ct (loss-inclusive) | mean +1.25c, median +0.10c |
| 2b-reweighted net EV/ct (non-gating) | **-19.41c/ct** |

## Verdict

**PASS.**

- (a) coverage 64.2% >= 55%, and its Wilson lower bound 52.2% > 40.9%: **True**.
- (b) false-lock count on the pure deployed rule: 0/344, **True**.
- (c) identical section-4 methodology, only feed cadence changed: by construction (same
  `backtest_day` logic, parameterized only on the fetch function and the disclosed cadence-appropriate
  completeness guard).

Both pre-registered gating bars clear. The hypothesis in `pmkt_final_verdict.md` section 4 -- that
hourly METAR under-reports the diurnal peak by roughly an hour's worth of temperature change, and that a
true 1-minute feed would materially raise Chicago's coverage above 40.9% -- is confirmed directly: the
SAME calendar day (2026-07-15) that the hourly feed backtested as "winner bracket never entered" (a
coverage miss) is a coverage **hit** on the 1-minute feed (verified in an ad hoc single-day
cross-check during development, in addition to the full-sample numbers above).

## Important caveats (do not treat this as a clean "go build it")

1. **The 1-minute ASOS archive itself has real day-level coverage gaps for KORD, not just the known
   22-34h publication latency.** All of 2026-02-09 through 2026-02-22 (14 consecutive days) returned
   **zero** 1-minute rows -- confirmed not a rate-limit/error artifact by inspecting the raw HTTP response
   directly (a clean 37-byte header-only reply, not a 429 or malformed body). Scattered zero/thin days
   recur through the rest of the sample too. "KORD is in IEM's 1-minute network" (as stated in
   `pmkt_final_verdict.md`) is true in the sense that the archive sometimes has dense per-minute data for
   it, but it is **not** a complete, gap-free historical record the way the hourly METAR archive is. Any
   live deployment plan must separately confirm the *live/real-time* 1-minute feed (Synoptic HF-ASOS,
   MADIS hfmetar) doesn't share this gap pattern -- this study only speaks to the backtest archive.
2. **Item 2b's bracket-entry false rate (86.1%) is far higher than item 2a's pure-lock false rate (0%),
   and it is what actually feeds the EV measurement.** This is the same structural fact
   `pmkt_final_verdict.md` documented (the pure deployed rule only ever confirms the single uncapped top
   rung or definitively rules OUT a rung; it essentially never *positively* confirms a middle rung, so
   the "entries" extension -- first touch of any rung's own band -- is needed to have any tradeable
   winning-rung timestamp at all, and most first-touches are, correctly, not the eventual winner).
3. **The non-gating EV number is strongly negative (-19.41c/ct, 2b-reweighted), not just thin.** This
   reverses the sign of the whitelist-wide +0.43c/ct (n=31) estimate in `pmkt_final_verdict.md`. The raw
   unweighted mean (mean=+1.25c/ct, median=+0.10c/ct) looks marginal-to-flat before reweighting; the
   reweighting by item 2b's true ~13.9% correct-entry rate is what drives it sharply negative, because
   the loss-case mean (-27.08c/ct) is large and applies to ~86% of entries. This is the SAME
   win/loss-fire construction and reweighting logic as `pmkt_final_verdict.md` section 3, applied
   correctly here -- it is a genuine, disclosed finding, not a bug: on Chicago's 1-minute feed, coverage
   went up materially, but the *tradeable* signal (bracket entries) is dominated by low-conviction,
   frequently-wrong early touches whose average loss outweighs the smaller number of well-timed wins.
   **Coverage clearing the pre-registered bar does not by itself imply a positive-EV strategy** -- item 3
   was explicitly non-gating for exactly this reason, and this run demonstrates why: a materially higher
   coverage rate, on its own, does not resolve the deeper open question (already flagged in
   `pmkt_final_verdict.md` item 4) of whether a real historical-ask source and better entry timing (e.g.,
   entering nearer to the deployed rule's actual lock rather than the coarser "band touch" extension)
   would flip this sign back positive.
4. **Only Chicago clears any bar here.** This result says nothing about the international 5/6 of the
   whitelist (London, Paris, São Paulo, Tokyo, Mexico City), which remain STILL-BLOCKED per
   `pmkt_final_verdict.md` -- IEM's 1-minute archive is US-only, confirmed there and not re-tested here.
5. **Operator-decision reminders from `pmkt_final_verdict.md` section 6 (wallet/USDC/CLOB stack,
   US-person access, Polymarket US vs global-venue product uncertainty) are unchanged and unresolved by
   this run.** Flagged, not decided, per `GROUNDING.md`.

## Bottom line

Track A's pre-registered coverage/false-lock GO-check **PASSes** for Chicago on the true 1-minute ASOS
feed: pooled coverage rises from the hourly baseline's 40.9% to 64.2% (Wilson LB 52.2%, clearing both
bars), with zero false locks across 344 deployed-rule fires (67 usable city-days, above the n>=60
target), and both required sanity checks (exact reproduction of the prior hourly number; 60x row-count
confirmation) pass. This resolves the specific "signal coverage" blocker `pmkt_final_verdict.md`
identified as the reason Chicago was not already a GO. It does **not**, however, resolve whether a
Chicago-only build is actually profitable: the non-gating, loss-inclusive reweighted EV on this same
sample is sharply negative (-19.41c/ct), driven by an 86% false-entry rate on the tradeable
"bracket-entry" signal that item 2a's pure lock rule structurally can't avoid using for a bounded ladder.
**Recommendation: do not treat this as a green light to build a Chicago trading harness off coverage
alone.** The coverage blocker is resolved; a real profitability question, and the archive's own
historical-gap limitation (Finding 1), are now the open items before any further step, most directly:
(i) a real historical-ask source to remove the last-trade+spread proxy from the EV construction (already
flagged as unresolved in `pmkt_final_verdict.md` item 4), and (ii) a materially larger EV sample with
better-timed entries (closer to the deployed rule's actual lock, not the coarser band-touch extension)
before trusting the sign of the EV estimate either way.
