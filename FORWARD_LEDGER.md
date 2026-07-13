# FORWARD VALIDATION LEDGER

Daily forward evidence for the pre-registered decision-layer arms. Maintained by the
daily improvement cycle (BOT_CHARTER.md). Arms are produced by box_shadow.py on the
collector (bot branch, deployed 2026-07-13 04:42Z, commit 31454af35) — one row per
(window, arm) in gha_data/<day>/box_shadow_<asset>15m.jsonl.

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
