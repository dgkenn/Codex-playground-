# wx_earlylock accrual diagnosis (2026-07-20)

## Bottom line
No exception, no silent failure, no timezone bug in `wx_earlylock_forward.py` itself. Ran `settle`,
`snapshot`, and `report` locally (reproducing exactly what the workflow does) and pulled the last 5 real
workflow run logs (`kwx-earlylock`, 2026-07-19T09:17Z through 2026-07-19T23:09Z, all `conclusion: success`) --
every leg completed cleanly and printed sane event counts. `wx_earlylock_paper.jsonl` having 1 row after ~1.5
days is mostly **honest rarity by design** (P_clear>=0.95 is meant to be a rare, high-confidence event), but
it is compounded by **one real, fixed bug**: the LOW mirror had no dedicated snapshot window. `settled=0` is
**not a bug at all** -- it's just that the daily settle cron hasn't reached the row's eligible date yet.

## What I checked
- Read `wx_earlylock_forward.py`, `wx_earlylock_study.py`, and `origin/main:.github/workflows/kwx-earlylock.yml`.
- Pulled workflow run history via `actions_list`/`get_job_logs` for `kwx-earlylock.yml`: 5 runs total since
  the workflow was created (`4338f57`, 2026-07-19T04:16:21-04:00), all `schedule`-triggered, all `success`.
- Ran `python wx_earlylock_forward.py settle` and `snapshot` locally in the worktree (same checked-out branch
  code the workflow runs) to reproduce.

## settled=0: not a bug
The one paper row so far is dated `2026-07-19` (ts `2026-07-19T23:09:43Z`). `settle()`'s no-look-ahead guard
(`if d >= today_utc: continue`) correctly refuses to score a day that hasn't fully ended yet. As of this
diagnosis (2026-07-20T02:33 UTC) the daily settle cron (`20 7 * * *`, 07:20 UTC) for 2026-07-20 **has not
fired yet** -- the operator's premise that it "ran twice by now" doesn't match the actual run history (there
have been zero 07:20-UTC-dated runs since the one row was logged; the workflow is only ~1.5 days old and its
*first ever* run, delayed to 09:17 UTC on 7/19, predates the row entirely). I confirmed the settle logic
itself works: running `python wx_earlylock_forward.py settle` locally against the current `wx_earlylock_paper.jsonl`
settles the row correctly (`won=true`, realized IEM max 105F vs strike 103) -- I did not commit that local
settle output, since the jsonl logs are workflow-bot-owned state; the next real 07:20 UTC run will produce the
same result and commit it itself.

## snapshot: working, and the rarity is largely honest
Job logs for all 5 runs show `settle`/`snapshot`/`report` completing with clean event counts, e.g. the
2026-07-19T23:09Z run: `settled 0 new early-lock paper rows` then `snapshot: 19 daily-HIGH + 19 daily-LOW
events with ladder+running-extreme, 1 new early-lock paper rows`. A local re-run reproduces this shape (20
HIGH + 20 LOW events checked, 0 *new* rows because the day's ticker was already logged). P_clear>=0.95 with
the mechanical-lock-not-yet-fired gate is intentionally a narrow, late-arriving window (~60 min median lead
per the Phase-1 study) -- most station-days simply never cross 0.95 while still pre-lock, so 0-new-rows passes
are the expected common case, not evidence of a broken signal.

That said, I did **not** re-run the full 75-day `wx_earlylock_study.py` backtest to get a precise
signals/station-day rate here -- the local cache (`_earlylock_cache/`) is cold, and a fresh run would mean
~1,500 IEM fetches (75 days x 20 stations), out of proportion to what's needed to explain the gap. The
**live** accrual rate is the more decision-relevant number anyway: the study sweeps synthetic strike offsets
(extreme+/-1..5) to build a whole frontier, while the forward harness only logs the *one* strike actually on
the live ladder that the deployed mechanical lock buys -- a much narrower, real-world-gated event. `wx_earlylock_decision.py`
uses the observed live rate (1 row / ~1 day so far) for its ETA, explicitly, for this reason.

## The one real bug: LOW mirror has no pre-dawn snapshot window
`wx_earlylock_study.py`'s own Method section: the LOW case is "temp falls overnight to a pre-dawn trough...
the overnight cooling into the trough happens 00:00->~sunrise WITHIN the same LST calendar day." But the
original `kwx-earlylock.yml` cron only had:
- `7 18,19,20,21,22,23 * * *` -- afternoon HIGH window (documented and correct for highs)
- `20 7 * * *` -- once-daily settle

There was **no cron slot for the LOW pre-dawn window at all**. The LOW mirror only ever got snapshotted (a)
as an afternoon leftover of the HIGH cron -- by which point the overnight low has already happened and its
running minimum is no longer "early" (it's already mechanically locked or its P_clear window already closed),
or (b) once a day by the 07:20 UTC settle run, which is itself mistimed for the purpose: 07:20 UTC is ~3:20am
Eastern / ~12:20am Pacific -- hours *before* most stations' actual pre-dawn trough (typically nearer sunrise,
~5-7am local in July). This matches what the 2026-07-19T23:09Z run actually observed: 19 daily-LOW events with
a live ladder were checked, but none of them were still pre-lock and above threshold by that hour of the
afternoon -- because by 23:09 UTC (afternoon everywhere in the US), the actual daily low is long past.

**Fix applied** (`batch/earlylock-fix-main`, workflow-only PR to `main`): added a dedicated hourly pre-dawn
cron, `10 8,9,10,11,12,13 * * *` (08:00-13:00 UTC = ~04:00-06:00 Eastern through ~01:00-06:00 Pacific/Phoenix
local pre-dawn), giving the LOW sleeve comparable sampling density (6 checks/day) to the HIGH sleeve instead
of ~0 genuine pre-dawn checks. Did not touch the HIGH cron, the settle cron, `kwx_runner.py`,
`kwx_paper_gate.py`, or `kalshi_exec.py`.

## Expected time-to-decision
`wx_earlylock_decision.py`'s bar is `n>=30` settled fires (to ACTIVATE-PAPER or rule DEAD). At the observed
live rate before the fix (~1 row/day, all from the HIGH sleeve), that's roughly **~29-30 days**. With the LOW
pre-dawn cron now live, the LOW sleeve should start contributing real (not afternoon-leftover) signals too;
if it ends up contributing at a similar order of magnitude to HIGH, the honest expectation is something like
**~2-4 weeks** to n=30, but this is a rough prior, not a measurement -- `wx_earlylock_decision.py`'s ETA is
always computed from the actual observed rate at run time (`n_paper_logged / days_since_first_row`), not this
estimate, so it will self-correct as real data comes in either faster or slower than expected.

## Fee treatment (for the decision layer)
`wx_earlylock_decision.py` never recomputes fee for the *observed* EV -- it sums the `pnl` field each settled
row already carries, which `wx_earlylock_forward.settle()` computed net of the standard Kalshi quadratic taker
fee (`ceil(0.07*p*(1-p)*100)/100`, evaluated at the logged yes_ask) -- identical formula to
`wx_forecast_forward._kalshi_fee` and `kwx_runner`'s own paper accounting. The one place it *does* recompute
fee is the conservative/optimistic EV bounds, which re-weight the observed mean captured ask by a Wilson
lower/upper win-rate bound (a hypothetical, not a replay of individual fills), so fee is recomputed once at
that mean price for consistency.
