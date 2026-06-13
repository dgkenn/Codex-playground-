# Hour-of-day deployment schedule — VERDICT: ALWAYS-ON (no robust schedule)

**Study:** `hour_schedule_study.py` (study 3 of the scaling batch). Read-only replay of the
same-minute clean-box policy on the BTC 15m tape; IS = first 60%, OOS = last 40%; coarse UTC-hour
session blocks only (per-hour fitting is known-unstable on this sample); quarterly stability check;
redundancy test against the t36 spread gate.

**Data:** `hist_kalshi_btc15m.parquet` ∩ `trades_kalshi_btc15m.parquet` = **182 BTC windows**
(small; the candlestick endpoint only retains a recent slice). ~5–22 traded windows per quarter.

## Result
| schedule (UTC hours) | %traded | IS c/win | OOS c/win | IS uplift | OOS uplift | IS+OOS ok? |
|---|---|---|---|---|---|---|
| 16–24 only | 33% | +1.43 | +1.68 | +4.19 | **−1.82** | no |
| 00–04 + 16–24 | 56% | +0.60 | +2.26 | +3.36 | **−1.24** | no |
| 20–04 (best IS) | 39% | +0.12 | +3.27 | +2.88 | **−0.23** | no |
| **always-on** | 100% | −2.76 | **+3.50** | 0 | 0 | baseline |

Every candidate schedule that looks good IS **loses to always-on out-of-sample** (negative OOS
uplift). The single best IS schedule (20:00–04:00) also fails the **quarterly stability check**
(Q0 negative), and t36 already blocks **100%** of windows in all the candidate schedule hours, so a
schedule adds nothing on top of the gate we already run.

The whole signal is dominated by a handful of large strand events in a 182-window sample — the
per-hour means swing from −74c to +20c on n≤6. Not enough power to carve the clock, and the OOS +
quarterly tests confirm any carve is overfit.

## Verdict
**ALWAYS-ON.** Keep collecting every window; do not gate the box engine by hour of day. Hour-22's
apparent edge (+17.6c tape, n=5) is too thin to act on — flag as a watch-item, not a rule.
Revisit only if the settled-candlestick history deepens to 4-figure window counts per quarter.

## Note
`live_hour22()` returned a `(str, [])` tuple on the file-missing / empty paths while the caller
guarded with `isinstance(live, str)` — so any environment without the live `window_audit_btc15m.jsonl`
crashed the whole study at the optional live cross-check. Fixed to return the bare string; the tape
analysis (the part that produces this verdict) was always correct and unaffected.
