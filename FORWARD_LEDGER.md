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
| stack_full / stack_lean | replay: EV +1.47c t=2.84, strand 6.73→2.14%, CVaR5 halved (STRAND_DEFENSE stack test) | accruing from 2026-07-14 (box-shadow.yml) |
| c3_share (added 2026-07-13, 17514ec87) | +1.42c t=5.15 marginal beyond thickbook (in-sample; large-skip artifact known — forward is the only valid sizing). NOTE: observed veto rate 39-49% of windows, higher than the 'mild' label implied; investigated at wiring (real property of depth-share stat, values span full range; thickbook 18-22% in same runs confirms harness). Judge on gate-passed forward deltas only | accruing from 2026-07-14 |
| eth 'live' sleeve (added 2026-07-13) | node F1b viability: ETH pair 87.6%, 30% of fills at 2-3c spread | accruing from 2026-07-14 |
| back2 (added 2026-07-13, 0f5bdf4ac; runs BOTH assets) | HONEST triangulated prior: +0.2-0.4c/window on ETH (study t=8.96 did NOT survive replication — F1b-repl; three implementations agree weak-positive). BTC = falsification control (L0.5: back-quoting toxic). Deploy bar: ETH day-clustered t>=2 vs eth-live over >=10 forward days AND BTC control non-positive | accruing from 2026-07-14 |

## Daily entries
### 2026-07-13 (day 0 — deployment day)
- Live: SWITCH=on, no kill sentinel, telemetry fresh. Size-2 experiment day 2.
  BTC overnight windows quoted 0 orders (low-liquidity hours + gates); realized $0.
  Live edge sample remains tiny (4 trading days total) — see 2026-07-19 eval plan.
- box_shadow deployed 04:42Z; first arm rows expected from the next paper-collect
  run. Fidelity gate at deploy: live-arm correlation 1.00000 vs study values
  (682/682 exact) on 2026-06-25 + 2026-07-05.
- No forward stats yet (day 0). First promotion decision possible ~2026-07-23.
