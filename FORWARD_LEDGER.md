# FORWARD VALIDATION LEDGER

Daily forward evidence for the pre-registered decision-layer arms. Arms are produced
by box_shadow.py — one row per (window, arm) in gha_data/<day>/box_shadow_<asset>15m.jsonl.

**CORRECTION 2026-07-13 (evening audit):** the box_shadow.py CODE was committed
04:42Z (31454af35) + STACK arms wired 161cd2e73, but NO workflow ever RAN it — so
from deploy until this correction, ZERO forward rows existed and the "accruing"
status below was aspirational, not real. Fixed: box-shadow.yml (main cd736e2a9)
now runs the replay daily at 02:47 UTC over a trailing 7-day window of collected
ticks. Harness verified locally (8 arms/window, ~5000 windows 07-06..07-12).
FORWARD CLOCK THEREFORE STARTS 2026-07-14 (first full post-deploy day the scheduled
job processes); the ~10-day gate opens ~2026-07-24, not 07-23. Pre-deploy replay
over 07-06..07-12 only reproduces the priors (that era is the arms' own test set).

## Promotion gate (from charter — do not relax)
Promote an arm when: day-clustered t >= 2 vs the live arm over >= 10 FORWARD days
(days after 2026-07-13, i.e. data the arm's design never saw), evaluated on the
gate-passed subset for entry vetoes / all events for disposal arms. Kill when t < 0
after 10+ forward days.

## Arms under forward test (pre-registered 2026-07-13, replay priors attached)
| arm | replay prior (test, day-clustered) | forward status |
|---|---|---|
| hazard_stop | +0.57c t=2.36 (gate +1.11c t=2.64); re-impl sensitivity noted (J) | accruing from 2026-07-13 |
| thickbook_veto | avoided 1.25c/event t=10.1 (in-sample) | accruing |
| cell_veto | +0.124c/window t=2.77 (train->test) | accruing |
| givecap15 | flat mean, tail cut (disposal study) | accruing |
| combined | untested as a stack | accruing |

## Daily entries
### 2026-07-13 (day 0 — deployment day)
- Live: SWITCH=on, no kill sentinel, telemetry fresh. Size-2 experiment day 2.
  BTC overnight windows quoted 0 orders (low-liquidity hours + gates); realized $0.
  Live edge sample remains tiny (4 trading days total) — see 2026-07-19 eval plan.
- box_shadow deployed 04:42Z; first arm rows expected from the next paper-collect
  run. Fidelity gate at deploy: live-arm correlation 1.00000 vs study values
  (682/682 exact) on 2026-06-25 + 2026-07-05.
- No forward stats yet (day 0). First promotion decision possible ~2026-07-23.
