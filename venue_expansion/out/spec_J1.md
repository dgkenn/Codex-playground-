# spec_J1 -- KXJOBLESSCLAIMS weekly-relist fade (reopen of graveyard #24)
**Verdict: INSUFFICIENT**
## Data provenance
- Shards read: **all 16** HF trade shards (trades-0000..0015), predicate-pushed to the
  KXJOBLESSCLAIMS ticker universe via the shared M1 tape pull (`cache/prereg/tape/`).
  Spot-verified this run: live re-query of `trades-0000.parquet` for a 0-row ticker and a
  365-row ticker both matched the cache exactly.
- Markets: `cache/M1/markets_universe.json`, pulled from all 4 HF markets shards,
  filtered to `series_key == 'KXJOBLESSCLAIMS'` exact (never a LIKE prefix).
- Date window: archive holds 24 KXJOBLESSCLAIMS events,
  2025-06-12 .. 2026-02-05 (release-Thursday close dates).
- Settlement: `GET /trade-api/v2/markets/{ticker}` attempted for **all 212** KXJOBLESSCLAIMS
  tickers (not just the 2 archive-unsettled ones), cached at `cache/J1/live_results.json`.
  **DIVERGENCE (reported per non-negotiable #1): all 212 requests returned HTTP 404.**
  This is the same retention wall that killed graveyard #24, now total for this series --
  even `KXJOBLESSCLAIMS-26JAN22-*` (closed 2026-01-22, ~6 months before this run) 404s, and
  bulk `/markets?event_ticker=...` / `?series_ticker=...&status=...` also return empty for
  every past event (confirmed live, `/series/KXJOBLESSCLAIMS` and current open markets DO
  resolve fine, so the series itself is live -- only historical single-market lookups are
  gone). Consequently the '0 disagreements' below reflects 0 *possible* comparisons, not
  genuine agreement, and settlement truth for the 210 already-archive-settled markets
  falls back to the archive's own `result` column (itself asserted authoritative per the
  top-level DATA FACTS). The 2 archive-unsettled tickers per event x 10 rungs = 20 markets
  in `KXJOBLESSCLAIMS-26JAN29` / `-26FEB05` have NO settlement source at all and are logged
  `result unavailable` (named skip-ledger category) rather than guessed.
  Archive-vs-live disagreements (of 0 possible comparisons): 0 (none).
- Executable prices: signal price = first trade at/after t_open within 6h, priced off
  `taker_side` (yes->yes_price/100 true ask, no->(100-no_price)/100 true bid). Entry price
  = first trade at/after the signal timestamp, within 60 min, whose OWN taker_side matches
  the side we must take, priced at that print's own crossing price. Never mid, never
  best-in-window.

## Divergence from the spec text (reported per non-negotiable #1)
`data_plan` states FIT = "the first 8 release Thursdays (2025-06-12 .. 2025-07-31)". The archive has no `KXJOBLESSCLAIMS-25JUN19` event -- only 7 events fall in that literal date span. The spec's own VALIDATION clause ("max 16 available") is only consistent with FIT having exactly 8 events (24-8=16), so this script uses the ordinal rule (first 8 chronological events, whichever dates they carry) as binding: FIT = ['2025-06-12', '2025-06-26', '2025-07-03', '2025-07-10', '2025-07-17', '2025-07-24', '2025-07-31', '2025-08-07']. This does not move any bar or floor.

## FIT: theta grid search (frozen grid {0.15, 0.25, 0.35})
| theta | n_entries | n_Thursdays | mean_net ($/ct) | t |
|---|---:|---:|---:|---:|
| 0.15 | 1 | 1 | 0.53 | None |
| 0.25 | 1 | 1 | 0.53 | None |
| 0.35 | 1 | 1 | 0.53 | None |

**INSUFFICIENT (procedural divergence, non-negotiable #1)**: Thursday-clustered t is UNDEFINED (fewer than 2 populated FIT Thursday clusters) at all three grid cells, for every theta -- entry construction is so sparse in the FIT window (illiquid relist; most rungs killed by 'no print within 6h of open' or 'anchor ambiguous') that only 1 of the 7 anchorable FIT Thursdays ever produces a qualifying entry, regardless of theta. The frozen 'highest FIT t' selection procedure cannot be executed -- this is not the spec's self-kill clause (t<=0, which presumes t is defined). No substitute selection rule was improvised. Validation is never read.

## Skip ledger (263 entries)
| reason | count |
|---|---:|
| live reconciliation unavailable, fell back to archive result | 192 |
| no print within 6h of open | 32 |
| result unavailable (neither live nor archive settled) | 20 |
| anchor ambiguous: strike falls inside prior week's unresolved band | 14 |
| no prior KXJOBLESSCLAIMS event in archive to anchor on | 5 |

## Full run log
```
==============================================================================
spec_J1 -- KXJOBLESSCLAIMS weekly-relist fade (reopen of graveyard #24)
==============================================================================
KXJOBLESSCLAIMS events in archive: 24  (spec's own data_plan states 24)
archive result vs live-reconciled result: 0 disagreements across all settled markets
  2025-06-12  KXJOBLESSCLAIMS-25JUN12      t_open=2025-06-09 18:00:00+00:00  n_rungs=5
  2025-06-26  KXJOBLESSCLAIMS-25JUN26      t_open=2025-06-19 14:00:00+00:00  n_rungs=4
  2025-07-03  KXJOBLESSCLAIMS-25JUL03      t_open=2025-06-25 14:00:00+00:00  n_rungs=6
  2025-07-10  KXJOBLESSCLAIMS-25JUL10      t_open=2025-07-01 14:00:00+00:00  n_rungs=6
  2025-07-17  KXJOBLESSCLAIMS-25JUL17      t_open=2025-07-10 21:30:00+00:00  n_rungs=7
  2025-07-24  KXJOBLESSCLAIMS-25JUL24      t_open=2025-07-11 14:00:00+00:00  n_rungs=7
  2025-07-31  KXJOBLESSCLAIMS-25JUL31      t_open=2025-07-11 14:00:00+00:00  n_rungs=7
  2025-08-07  KXJOBLESSCLAIMS-25AUG07      t_open=2025-07-22 14:00:00+00:00  n_rungs=10
  2025-08-14  KXJOBLESSCLAIMS-25AUG14      t_open=2025-08-07 14:00:00+00:00  n_rungs=10
  2025-08-21  KXJOBLESSCLAIMS-25AUG21      t_open=2025-08-07 14:00:00+00:00  n_rungs=10
  2025-08-28  KXJOBLESSCLAIMS-25AUG28      t_open=2025-08-07 14:00:00+00:00  n_rungs=10
  2025-09-04  KXJOBLESSCLAIMS-25SEP04      t_open=2025-09-02 15:55:00+00:00  n_rungs=10
  2025-09-11  KXJOBLESSCLAIMS-25SEP11      t_open=2025-09-04 14:00:00+00:00  n_rungs=10
  2025-09-18  KXJOBLESSCLAIMS-25SEP18      t_open=2025-09-11 13:00:00+00:00  n_rungs=10
  2025-09-25  KXJOBLESSCLAIMS-25SEP25      t_open=2025-09-18 14:00:00+00:00  n_rungs=10
  2025-10-02  KXJOBLESSCLAIMS-25OCT02      t_open=2025-09-25 16:00:00+00:00  n_rungs=10
  2025-12-18  KXJOBLESSCLAIMS-25DEC18      t_open=2025-12-11 22:00:00+00:00  n_rungs=10
  2025-12-24  KXJOBLESSCLAIMS-25DEC24      t_open=2025-12-18 16:30:00+00:00  n_rungs=10
  2025-12-31  KXJOBLESSCLAIMS-25DEC31      t_open=2025-12-26 03:00:00+00:00  n_rungs=10
  2026-01-08  KXJOBLESSCLAIMS-26JAN08      t_open=2025-12-31 17:00:00+00:00  n_rungs=10
  2026-01-15  KXJOBLESSCLAIMS-26JAN15      t_open=2026-01-08 17:00:00+00:00  n_rungs=10
  2026-01-22  KXJOBLESSCLAIMS-26JAN22      t_open=2026-01-15 17:00:00+00:00  n_rungs=10
  2026-01-29  KXJOBLESSCLAIMS-26JAN29      t_open=2026-01-22 15:00:00+00:00  n_rungs=10
  2026-02-05  KXJOBLESSCLAIMS-26FEB05      t_open=2026-01-29 17:00:00+00:00  n_rungs=10

FIT events (first 8, ordinal): ['2025-06-12', '2025-06-26', '2025-07-03', '2025-07-10', '2025-07-17', '2025-07-24', '2025-07-31', '2025-08-07']
VALIDATION events (remaining 16): ['2025-08-14', '2025-08-21', '2025-08-28', '2025-09-04', '2025-09-11', '2025-09-18', '2025-09-25', '2025-10-02', '2025-12-18', '2025-12-24', '2025-12-31', '2026-01-08', '2026-01-15', '2026-01-22', '2026-01-29', '2026-02-05']

tape: 16 shards read, 9812 KXJOBLESSCLAIMS trades in local cache

------------------------------------------------------------------------------
FIT: theta grid search on first 8 release Thursdays
------------------------------------------------------------------------------
  theta=0.15  n_entries=  1  n_Thursdays=1  mean_net=0.53  t=None
  theta=0.25  n_entries=  1  n_Thursdays=1  mean_net=0.53  t=None
  theta=0.35  n_entries=  1  n_Thursdays=1  mean_net=0.53  t=None

DIVERGENCE: Thursday-clustered t is UNDEFINED for all three FIT theta grid cells (never more than 1 populated FIT Thursday cluster, for any theta). The frozen 'highest FIT t' selection procedure cannot be executed. This differs from the spec's self-kill clause (t<=0, which presumes t is defined). Returning INSUFFICIENT per non-negotiable #1 -- no substitute selection rule improvised.
```
