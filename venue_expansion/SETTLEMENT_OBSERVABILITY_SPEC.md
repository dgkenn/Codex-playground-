# SETTLEMENT OBSERVABILITY — pre-registered measurement (REGISTERED 2026-10-27)

## Why this exists

Studies #1–#44 of this program all inferred daily-temperature outcomes from **1-minute ASOS
observations** (IEM `asos1min.py`), or from routine hourly METAR as a fallback. Study #44
(`finality_A.md`, `finality_B.md`) measured, for the first time and in two independent builds, how
well that feed actually reproduces Kalshi's official settlement value:

| feed | agreement with official `expiration_value` |
|---|---|
| IEM 1-minute extreme, HIGH markets | **43.1%** exact integer; mean abs err 0.89 °F |
| IEM 1-minute extreme, LOW markets | **76.9%** exact integer; mean abs err 0.53 °F |
| all markets, within 0.5 °F (Build B) | **58.2%** (n=6,486) |

The error is **one-sided**: the 1-minute max runs *above* official; the routine hourly max runs
*below* it. A bracket rung is 2 whole degrees wide, so a 1 °F feed bias flips the winner. That is
the entire reason Study #44's false-lock rate was ~24% against a 2% bar, and it is independent of
latency, timezone, parameters, or execution. Both builds proved timezone handling correct (0
monotonicity violations; shift-0 window optimal; `close_time == LST midnight` on all 6,039/6,489
events) and no-look-ahead (15,360 and 300 adversarial re-runs, 0 failures), so the disagreement is
a genuine source mismatch, not a bug.

## The mismatch, named

Kalshi's published rules (help.kalshi.com/markets/popular-markets/weather-markets, read 2026-10-27):

- **Daily** high/low markets — our entire `KXHIGH*`/`KXLOWT*` universe — settle on the **NWS Daily
  Climate Report (CLI)**, and *only* that. Settlement is delayed when the reported high "is not
  consistent with 6-hr or 24-hr highs reported by METAR."
- **Hourly** temperature markets settle on **The Weather Company** (a different product we do not
  trade and have never tested).

Build A's report attributed daily settlement to The Weather Company. That is **wrong** and I am
correcting it here: TWC governs the hourly product; the daily product is NWS CLI.

So the program has spent 44 studies inferring a variable it was never observing. The CLI value is
not the 1-minute extreme — it is the station's own recorded extreme, quality-controlled by NWS, and
cross-checked against the **METAR 6-hour and 24-hour max/min remark groups**.

## The lever: those groups are public, and they are in the same METAR we already fetch

Verified live 2026-10-27 on KORD, 2026-08-07, via `asos.py?data=metar`:

```
KORD 072351Z ... RMK AO2 SLP145 TCU DSNT E T02890194 10306 20278 55003
                                            ^^^^^ 6-hr max 30.6 C = 87.1 F
```
IEM's own daily climate value for ORD that day: `max_tmpf = 87.0`, `min_tmpf = 68.0`.

The `1xxxx` / `2xxxx` groups are the station's **recorded** 6-hour extreme (it does not miss the
peak the way hourly spot readings do), and `4xxxxxxxx` carries the 24-hour max/min. They are
published inside routine hourly METARs at the synoptic hours, i.e. **hours before a daily market
closes** — so unlike the CLI itself (next-morning), they are usable live at ~10 minute latency.

**Hypothesis, stated before measuring:** the settlement variable is observable after all. We were
reading the wrong field.

## What is measured (no prices, no trading rule, no outcome-conditional selection)

For every settled daily bracket/threshold market in the Study-#44 universe that carries a numeric
official `expiration_value` (Build B has n=6,486 on disk), compute the day's extreme four ways over
the identical NWS local-standard-time day window already proven correct in Study #44:

- **(1)** IEM 1-minute extreme — the incumbent. Known: 43% / 77%.
- **(2)** routine hourly METAR spot extreme — the incumbent fallback. Known: biased low.
- **(3)** **6-hour-group reconstruction** — decode every `1xxxx`/`2xxxx` group in the day's METAR
  remarks, take max/min across the groups whose 6-hour windows tile the local day, reconcile with
  the `4xxxxxxxx` 24-hour group where present.
- **(4)** **IEM `daily.json` `max_tmpf`/`min_tmpf`** — IEM's climate-report-derived daily value.
  Report `tmpf_est` separately; estimated rows are excluded from the headline rate.

Report for each: exact-integer match rate, within-0.5 °F rate, signed error histogram, and the rate
**stratified by HIGH/LOW and by station**, with Wilson 95% intervals.

Additionally, for (3) only, record **the latest UTC time at which the reconstruction was already
final** (the timestamp of the last 6-hour group needed), and the distribution of
`close_time − that timestamp`. This is what decides whether (3) is a live signal or only a
post-hoc check.

## Decision rule — frozen now, before any number is computed

This is a **measurement of a data source**, not a hypothesis test: there is no trading rule, no
price, and no parameter grid, so there is nothing to p-hack. The decision rule is therefore about
what gets built next, not about significance:

- **(3) or (4) matches official at ≥ 99.0% exact-integer (Wilson lower bound ≥ 98.0%), and for (3)
  the reconstruction is final ≥ 30 minutes before close on ≥ 80% of days** →
  **the finality family is revived.** Studies #44's FINAL-YES and the FINAL-NO/ladder spec get
  re-registered verbatim on feed (3), with their existing frozen bars untouched, because the
  2%-false-lock bar becomes reachable for the first time. No bar moves; only the input feed changes.
- **(3) best rate in 95.0–99.0%** → the bar is *approachable but not met*; a re-run is permitted
  only with the false-lock bar held at 2% and the explicit expectation that it fails. Report, do
  not build.
- **(3) best rate < 95.0%** → **daily weather temperature is permanently retired for this program.**
  The settlement variable is not observable at the 2 °F granularity these contracts trade at, by
  any feed available to this operator, and no execution engineering can repair that. Stop. Say so
  plainly and redirect to markets settling on a number that can be read exactly.

Reporting (3) and (4) separately is mandatory: (4) is next-morning and can never be a live signal,
so a pass on (4) alone proves observability in principle but gives no deployable path — that
outcome must be labelled **OBSERVABLE-BUT-NOT-LIVE**, not a revival.

## Anchors (each must hold or the result is void)

- **(a) Same window.** Reuse Study #44's proven LST day window and `close_time` assertion verbatim.
  Do not re-derive it.
- **(b) No outcome in the loop.** `expiration_value` is the *measurement target*, never a filter.
  Days are excluded only for missing data, and every exclusion is counted with its reason.
- **(c) Decode audit.** Show 10 worked METAR remark decodes by hand (raw string → °C → °F →
  contribution to the day extreme), including at least one negative-temperature group
  (`1` prefix sign digit) and one day where the 24-hour group contradicts the 6-hour groups.
- **(d) No cherry-picked stations.** Every station in the universe is reported; the headline rate is
  over all of them pooled, with the per-station table shown so a single good station cannot carry it.

No threshold in this document may move after 2026-10-27.
