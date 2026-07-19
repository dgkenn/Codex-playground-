# Rung stacking: is firing the full `locked_orders()` set worth it? (evidence, no code change)

Source: `wx_rung_stacking.py`, reading the committed `_trackA_results_raw.json` (Phase-2 Track A
walk-forward raw grid, 4383 market-days, deployed cell `1_3` = `MARGIN_F=1.0`/`SUSTAIN_MIN=3`, same
admissibility filter as `wx_ev_concentration.py`/`wx_fee_floor_impact.py`: `cells["1_3"].fired` and
`exec_price*100 <= MAX_PAY_CENTS(98)`) and `wx_book_snapshots.jsonl` (live near-lock books, 1 sweep
committed so far). **n = 1698 live-admissible fires, total pnl $352.08.** Propose-only: reads recorded
data and prints numbers; no runner parameter or code path is touched.

**Question**: `kwx_runner.locked_orders()` already returns every rung the observed extreme has
mechanically cleared in one poll — not just the just-crossed ("marginal") rung, but any deeper-ITM rung
still priced `<=MAX_PAY_CENTS`, and the mirrored NO-side rungs. `poll_once()` fires all of them. Since
each rung's fill is capacity-bounded by its own book, does the full stacked set actually carry meaningful
extra EV+capacity over firing only the single best rung — or is rank-2+ dead weight at 98-99c after fees?

## Study 1 — trackA: rank-1 (best gap) vs rank-2+ (rest of the stack)

**Fire event = (series, date)** — one city-market-day's cascade of rung locks (the task's definition).
Within each event, fired rungs are ranked by `gap` (`= 1 - exec_price`, the edge still open) descending;
rank-1 = biggest-gap rung fired that day/series, rank-2+ = every other rung that also fired.

- n events = 1056; **422/1056 (40.0%) of events fired more than one rung.**
- rungs-fired-per-event: 1x=634, 2x=283, 3x=84, 4x=33, 5x=18, 6x=4.

| tier | n | total pnl | mean $/ct | capacity (vol_at_exec) | win rate | Wilson95 |
|---|---:|---:|---:|---:|---:|---:|
| rank-1 (best gap) | 1056 | $281.77 | $0.2668 | 203,942 | 99.4% | [98.8%, 99.7%] |
| rank-2+ (rest) | 642 | $70.31 | $0.1095 | 119,422 | 100.0% | [99.4%, 100%] |
| **all fires** | **1698** | **$352.08** | **$0.2073** | **323,364** | **99.6%** | — |

**Rank-1-only would capture 80.0% of EV and only 63.1% of capacity.** Stacking (firing rank-2+ too) adds
the other **20.0% of EV and 36.9% of capacity** — a real, not marginal, uplift, and it comes at a *lower*
but still clearly positive per-contract edge ($0.11/ct vs rank-1's $0.27/ct) with a **100% empirical win
rate** (Wilson95 lower bound 99.4%, i.e. even under the pessimistic end of sampling uncertainty rank-2+ is
not free money that quietly turns into losses).

### Is thin-gap rank-2+ actually dead weight after fees?

| rank-2+ gap bucket | n | total pnl | mean $/ct | capacity | win rate |
|---|---:|---:|---:|---:|---:|
| <5c | 261 | $6.89 | $0.0264 | 53,746 | 100% |
| 5-15c | 233 | $19.04 | $0.0817 | 36,184 | 100% |
| >15c | 148 | $44.39 | $0.2999 | 29,492 | 100% |

No. Even the thinnest bucket (<5c gap, 41% of rank-2+ fires by count) is net **positive after fees**
(mean $0.0264/ct, fee already netted into `pnl`) — not zero, not negative. `>15c` rank-2+ fires (148 of
642, 23%) carry per-contract edge ($0.30/ct) comparable to rank-1's own average — i.e. a meaningful chunk
of rank-2+ isn't "leftover scraps," it's independently strong. The rank-1 gap-bucket table (below) shows
the same shape, confirming gap bucket — not stack rank — is the dominant EV driver (consistent with
`wx_ev_concentration.md`'s finding that `>15c` fires are 48% of count / 85% of EV system-wide):

| rank-1 gap bucket | n | total pnl | mean $/ct | win rate |
|---|---:|---:|---:|---:|
| <5c | 126 | $3.65 | $0.0290 | 100% |
| 5-15c | 263 | $23.32 | $0.0887 | 100% |
| >15c | 667 | $254.80 | $0.3820 | 99.1% |

### Robustness cut: literal same-minute-poll simultaneity

The day-level grouping above lumps together a whole day's sequential crossings, not just rungs that fired
in the exact same poll. A stricter cut — event = (series, date, t_star), i.e. rungs whose fire timestamp
matches to the minute — isolates genuinely simultaneous stacking:

- n strict events = 1603; only **89 (5.6%) have >1 rung firing in the same poll.**
- STRICT rank-1: n=1603, total $329.19, mean $0.2054/ct, win 99.6%.
- STRICT rank-2+ (literal simultaneous only): **n=95, total $22.89, mean $0.2410/ct, win 100%**
  (Wilson95 [96.1%, 100%]).

Literal same-poll stacking is a smaller slice (6.5% of EV under this stricter definition vs 20.0% under
the day-level definition), but it is **not lower quality** — its mean $/ct ($0.24) is actually *higher*
than the strict rank-1 baseline ($0.21), consistent with the framing in the task: the deeper-ITM rungs
locked in the same moment as the marginal one are often *more* mispriced, not less, because the book
hasn't caught up to all of them yet. Both cuts point the same direction: stacking is real incremental EV,
not noise from aggregating unrelated crossings.

## Study 2 — live book depth (`wx_book_snapshots.jsonl`)

Only **1 sweep / 33 rows** are committed so far (today, 2026-07-19T22:03Z) — this is a data-availability
limitation, not a null result: `wx_capacity_probe.py`'s near-lock gate (yes-ask in `[50,98]c`) scans every
market in every open event, so a future sweep that lands while 2+ rungs on the same event are both mid-way
to locking would populate this comparison. In today's single sweep, **0/33 event-sweep groups had more
than one rung simultaneously in the near-lock band** — every open event had at most one rung with an ask
in `[50,98]c` at that moment, so no direct "aggregate depth across the locked set vs single best rung"
multiplier can be computed from live data yet.

What the single-rung rows do show: depth `<=98c` at near-lock time ranges min=1 to max=5265 contracts
(median 538, n=33, 0 empty books) — i.e. individual-rung capacity is highly variable by city/liquidity,
which is exactly consistent with Study 1's finding that rank-2+ capacity (119,422 across 642 fires, mean
~186 ct/fire) is the same order of magnitude as rank-1's own per-fire book depth, not a rounding error.
**Recommendation: keep accruing `wx_book_snapshots.jsonl` via the existing `kwx-depthprobe` workflow** —
once a sweep catches simultaneous near-lock rungs on the same event, this section can be re-run for a
direct live capacity-multiplier number; trackA's `volume_at_exec` (Study 1) is the best capacity evidence
available today.

## Study 3 — NO-side (SHORT) vs YES-side (LONG) mirror

trackA's `side` field: `SHORT` = the fired order is a NO buy (the "between"/most "less"/"greater"
cap-crossed rungs — a market that resolves NO once the extreme clears its cap), `LONG` = the fired order
is a YES buy (the rare open-ended floor-crossed rung). This is the NO-side mechanical-lock mirror
`locked_orders()` already handles.

| side | n | total pnl | mean $/ct | capacity | win rate | Wilson95 |
|---|---:|---:|---:|---:|---:|---:|
| SHORT (NO buy) | 1624 | $325.29 | $0.2003 | 302,377 | 99.6% | [99.2%, 99.8%] |
| LONG (YES buy) | 74 | $26.80 | $0.3621 | 20,987 | 100.0% | [95.1%, 100%] |

**SHORT (NO-side) fires are 95.6% of all live-admissible fires** — the runner's NO-side mirror is already
the dominant source of fires, not a rare edge case, and its economics (99.6% win, $0.20/ct mean) track the
overall population closely. LONG fires are rarer (74, 4.4%) and skew to a *higher* mean $/ct ($0.36 vs
$0.20) with a clean win record, though n=74 is small enough that the Wilson lower bound (95.1%) is the more
honest read than the point estimate. Of the 422 multi-rung day-events, **74 (17.5%) mix a SHORT fire and a
LONG fire on the same city-day** — i.e. stacking isn't purely "several NO rungs on one side of the ladder";
a meaningful minority of stacked events span both sides of the mirror simultaneously, which is exactly the
scenario the task description called out ("the mirrored NO-side rungs").

## Verdict

**KEEP CURRENT — firing the full `locked_orders()` set is already close to optimal; no rank-based
filtering is supported by the data.**

Evidence against filtering:
1. Rank-2+ is net-positive in every gap bucket tested, including the thinnest (<5c, mean +$0.026/ct after
   fees) — there is no cents-threshold above which rank-2+ becomes dead weight; the data doesn't show one.
2. Rank-2+ contributes 20.0% of total EV and 36.9% of total capacity (day-level cut) or a smaller-but-not-
   negligible 6.5% of EV (strict same-poll cut) — either way it's real money left on the table by a
   rank-1-only policy, not noise.
3. Win rate for rank-2+ is 100% empirically with a Wilson95 floor of 99.4% (day-level) / 96.1% (strict) —
   no evidence it's riskier than rank-1.
4. 17.5% of multi-rung events mix SHORT+LONG fires — a rank-1-only or NO-side-only policy would also
   silently drop the rarer, higher-mean-$/ct LONG-side fires on those days.

One low-risk, low-priority refinement worth flagging for a future PR (NOT implemented here): **order the
`poll_once()` fire loop by descending `gap` within an event**, so that on the rare day a `MAX_DAILY_DEPLOY_FRAC`
/`PER_CITY_DAILY_CAP_FRAC` cap actually binds mid-stack, the capital that *does* fire is guaranteed to be
the highest-edge rung first rather than whatever order the Kalshi event-markets API happens to return. This
repo's trackA data can't directly measure how often a cap binds mid-event (that requires runtime skip logs,
not backtest records), so this is flagged as a plausible small hedge, not a data-backed must-do — it would
cost nothing when caps don't bind (the common case) and only helps in the tail case they do.

No other refinement (skip rank-2+ above X cents, restrict stacking to one side of the mirror, cap stack
depth) is supported by this data — every cut tested shows rank-2+/mirror fires pulling their weight.
