# Hour-of-day deployment schedule — VERDICT: ALWAYS-ON (no robust schedule)

**Study:** `hour_schedule_study.py` (study 3 of the scaling batch). Read-only replay of the
same-minute clean-box policy on the BTC 15m tape; IS = first 60%, OOS = last 40%; coarse UTC-hour
session blocks only (per-hour fitting is known-unstable on this sample); quarterly stability check;
redundancy test against the t36 spread gate.

**Data:** `hist_kalshi_btc15m.parquet` ∩ `trades_kalshi_btc15m.parquet` = **825 BTC windows**
(full month, 2026-05-14 → 06-13; ~206 windows/quarter — re-run on the deepened candlestick history,
4.5× the original 182-window sample).

## Result (825 windows)
| schedule (UTC hours) | %traded | IS c/win | OOS c/win | IS uplift | OOS uplift | net-positive both halves? |
|---|---|---|---|---|---|---|
| 16–24 only | 35% | +1.22 | **−0.83** | +1.36 | +2.16 | no (OOS negative) |
| 20–04 | 33% | +0.46 | **−0.19** | +0.59 | +2.79 | no (OOS negative) |
| 12–24 | 52% | +1.09 | **−1.34** | +1.23 | +1.64 | no (OOS negative) |
| **always-on** | 100% | −0.14 | **−2.98** | 0 | 0 | baseline |

No schedule is net-positive in **both** halves: every candidate is IS-positive but **OOS-negative**.
Schedules do cut the OOS loss vs always-on (positive OOS *uplift*), but they never turn it positive,
and the carve fails the **quarterly stability check** — Q3 (the most recent ~week) is **−4.72c/win**
and only Q2 is (barely) positive. A gate that flips sign quarter-to-quarter is overfit, not a clock.

Note this baseline is the *ungated* same-minute clean-box replay (no t02/t36/vpin gates, no $0-fee /
queue-position credit) — it is a relative yardstick for the schedule question, **not** the deployed
system's expectancy. The takeaway is narrow and robust: hour-of-day is not a usable lever.

## Verdict
**ALWAYS-ON.** Keep collecting every window; do not gate the box engine by hour of day. Hour-22's
apparent edge (+17.6c tape, n=5) is too thin to act on — flag as a watch-item, not a rule.
Revisit only if the settled-candlestick history deepens to 4-figure window counts per quarter.

## Note
`live_hour22()` returned a `(str, [])` tuple on the file-missing / empty paths while the caller
guarded with `isinstance(live, str)` — so any environment without the live `window_audit_btc15m.jsonl`
crashed the whole study at the optional live cross-check. Fixed to return the bare string; the tape
analysis (the part that produces this verdict) was always correct and unaffected.
