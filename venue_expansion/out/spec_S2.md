# S2 — Tokyo RJTT GO-check on JMA 10-minute AMeDAS (Track A extension, GO-path #2)

**Verdict: NO-GO / FAIL** (pre-registered bar (a) not met; bar (b) cleared). Publishable dry
result per GROUNDING.md non-negotiable #9.

## What this tested

`ref/pmkt_final_verdict.md` found Tokyo's winner-bracket coverage on hourly METAR to be 30.8%
(26 usable days, 18 never-entered) and named "finer feed for the international cities" as
GO-path #2, hypothesizing (as Track A confirmed for Chicago on 1-min ASOS) that hourly cadence,
not the diurnal shape, was the binding constraint. A feed-recon pass
(`out/feedhunt_tokyo.json`) found JMA's own 10-minute AMeDAS archive for the Haneda point
(block_no=0371, ~0.3km from RJTT's aerodrome reference point, temps spot-matched 0.1–0.3°C vs
RJTT METAR), 144 rows/day, no auth, verified to 365 days of depth. S2 reruns the coverage/
false-lock GO-check on that feed.

## Method (fidelity to Track A)

`venue_expansion/spec_S2.py` reuses `backtest_day` copied **verbatim** from
`tracka_chicago_1min.py`'s already fetch-fn-generalized version — bracket parsing, the
byte-identical deployed lock rule (`kwx_lock_rule.py`: sustain-3, glitch filter, margin), and
the winner-bracket-entry walk are all unchanged. The only things that differ per spec are:

- **fetch_fn**: `fetch_jma_10min` — HTML-table-parses `data.jma.go.jp`'s 10-min AMeDAS archive
  page per JST calendar day (prec_no=44, block_no=0371), converts JST→UTC (with JMA's own
  "24:00 = next day's 00:00" convention), and converts °C→°F before handing observations to
  `R.sustained_extreme` — matching the Fahrenheit convention every other fetch_fn in this
  codebase uses, since the glitch filters (8.0°F jump threshold, ±130/-60°F bounds) are
  calibrated in Fahrenheit. `backtest_day` converts the returned extreme back to native °C
  exactly as it already does for the other 0.5°C-margin cities.
- **completeness guard**: `>=100 obs/day, <=3h end-gap` — Track A's own disclosed 1-minute
  guard family, reused verbatim in threshold value (a complete JMA day yields ~143 obs in
  `[day_start, day_end)`, so this is comfortably clearable on a genuinely complete day).
- **sampling**: dense, stride=1, over the frozen window 2026-03-15..2026-07-18 (126 candidate
  days = Tokyo's earliest-live date 2026-03-12 + 3-day buffer, through the same END_DATE the
  published hourly baseline used).

EV was explicitly **out of scope / non-gating** for this spec (delegated to S1's measured-ask
method) — no CLOB/ask pricing was pulled or computed here.

## Mandatory pre-run sanity check (passed exactly)

Reproduced `ref/pmkt_final_verdict.py`'s published hourly Tokyo row using the identical hourly
IEM "routine" METAR feed, identical strided sampling (`TARGET_SAMPLES_PER_CITY=22`,
`END_DATE=2026-07-18`), identical `MIN_DAY_OBS=15` / `MAX_END_GAP_H=4h` guard:

| | usable | never_entered | coverage |
|---|---|---|---|
| Published (pmkt_final_verdict.md §4) | 26 | 18 | 30.8% |
| This script's reproduction | 26 | 18 | 30.8% |

**Exact match: True.** Primary run proceeded per spec.

## Primary run results (JMA 10-min AMeDAS)

- Candidate days: 126 (2026-03-15..2026-07-18)
- Usable Tokyo days: **123** (3 skipped: `event_not_found` on 2026-03-31, 2026-05-17,
  2026-05-18 — Gamma had no event for those dates; not a JMA feed gap)
- JMA archive fetch gaps: **0/123 (0.0%)** — well under the 25% kill threshold
- Deployed-rule lock records: **755** (n>=200 min-n bar cleared)

### Bar (a) — pooled winner-bracket coverage

54/123 covered = **43.9%**, Wilson CI @ z=2.128: **[34.76%, 53.47%]**

- Coverage >= 50%? **No** (43.9% < 50%).
- Wilson lower bound > 30.8% published baseline? **Yes** (34.76% > 30.8%) — the coverage lift
  over hourly cadence is real and statistically decisive in isolation, but does not clear the
  spec's absolute 50% floor.
- **Bar (a): FAIL** (both conjuncts required; only the second held).

### Bar (b) — false-lock rate, pure deployed rule

0/755 wrong = **0.0000%**, Wilson CI @ z=2.128: **[0.0000%, 0.5962%]**

- False locks <= 1? Yes (0).
- Wilson upper bound <= 1.5%? Yes (0.596%).
- **Bar (b): PASS.** The JMA feed carries a Kalshi-grade false-lock rate for Tokyo — no
  evidence of an AMeDAS-vs-settlement-basis sensor-offset problem (this doubled as the spec's
  end-to-end settlement-basis test; a basis problem would have manifested as false locks).

### Item 2b — bracket-entry false rate (non-gating, reported for transparency)

587/641 entries wrong = **91.6%** (Wilson CI @ z=2.128: [88.9%, 93.6%]). Consistent with
GROUNDING non-negotiable #7 ("a rising day visits many rungs: currently-in-bracket is wrong
93% of the time (measured)") — the *entry*-level false rate is high by construction; the
*coverage* metric (bar a) and the *deployed lock rule*'s false-lock rate (bar b, item 2a) are
the metrics that actually gate a trading decision, and only the deployed rule matters for
false-positive risk.

## Verdict against the pre-registered pass bar

**GO iff BOTH (a) and (b).** (a) failed on the absolute coverage-floor conjunct despite clearing
the Wilson-lower-bound-over-baseline conjunct; (b) passed cleanly.

**Verdict: NO-GO / FAIL.**

No kill condition was hit (sanity reproduction matched exactly; JMA archive gap rate 0% well
under 25%; usable days 123 >> 60; false locks 0 << 2) — this is a clean, decisive negative
result at full pre-registered power, not a THIN/INSUFFICIENT non-answer.

## Interpretation

Track A's hypothesis — "hourly cadence, not diurnal shape, was the binding coverage
constraint" — is **partially but not fully confirmed** for Tokyo. Moving from hourly METAR to
genuine 10-minute AMeDAS did lift coverage from 30.8% to 43.9% (statistically real: Wilson LB
34.76% clears the old baseline with room to spare), roughly the direction Track A predicted.
But unlike Chicago (1-minute ASOS: 40.9%→64.2%, which cleared its own 55% floor), Tokyo's
10-minute cadence — 6x coarser than Chicago's 1-minute feed — was not enough to clear this
spec's pre-registered 50% floor. The most likely remaining structural cause, per
`pmkt_final_verdict.md`'s own diagnosis ("margin eats a dead zone out of narrow brackets... 1°C
international vs 2°F US"): Tokyo's brackets are 1°C wide against a 0.5°C margin — a
margin-to-bracket-width ratio matched to Chicago's 1°F margin / 2°F bracket, so bracket width is
not obviously the differentiator; more likely, JMA's 10-minute native cadence itself (vs. IEM's
true 1-minute ASOS) leaves genuine gaps in the sustain-3 window's ability to catch a bracket that
is only fleetingly cleared between samples. **A true 1-minute (or finer) Japanese feed was not
found in this recon pass** (JMA's own historical archive tops out at 10-minute; see
`out/feedhunt_tokyo.json`) — so no cheap further lift is currently available from a JMA feed.

## Deployability note (publish with any GO — recorded here regardless of the NO-GO)

The JMA archive page used is **historical-only**: it explicitly refuses the in-progress JST day
(`out/feedhunt_tokyo.json`'s `realtime_lag_note`). A live deployment (moot given the NO-GO, but
recorded for completeness) would need JMA's separate near-real-time AMeDAS JSON distribution
channel (`www.jma.go.jp/bosai/amedas/...`), which was **not verified** in this or the prior
recon run — latency is part of the signal definition (GROUNDING non-negotiable #5). Global
Polymarket venue deployability carries the same US-person geo-block flag noted for S1 and in
`GROUNDING.md` — flagged, not decided, here.

## Files

- Script: `venue_expansion/spec_S2.py` (read-only, reusable)
- Full results: `venue_expansion/out/spec_S2_results.json` (per-day log, all 755 lock records,
  all 641 entry records, sanity-check detail, JMA archive fetch log)
- Cache: `venue_expansion/cache/tokyo_10min/` (123 cached JMA day-pages + Gamma event JSONs,
  gitignored), `venue_expansion/cache/tracka_chicago_1min/` (reused for the hourly-sanity IEM
  pulls, shared cache dir with Track A's own hourly-cadence pulls where dates overlap)
