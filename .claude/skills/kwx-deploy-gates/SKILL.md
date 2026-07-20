---
name: kwx-deploy-gates
description: Operate the staged deployment gates of the K-WX bot — paper gate, canary, bankroll rungs, kill criteria, halt switch. Use for "can we scale", "should we deposit", "advance the stage", "activate a sleeve", "kill switch", "is the gate passed".
---

# Deployment gates (how money decisions get made here)

Nothing scales on vibes. Every stage advance has a numeric bar that was written down before the
data came in, and every stage has a kill criterion. The authoritative sequence lives in
`PATH_TO_4K.md` (stage table + GOAL RECALIBRATION section); this skill is the operator's cheat
sheet.

## Where am I? (verified command)

```bash
python kwx_goal_status.py     # CURRENT STAGE / NEXT GATE / BLOCKING ON + reopen calendar
```

## The ladder (as of 2026-07-20)

| Stage | Gate to enter | Kill criterion |
|---|---|---|
| 0 paper gate | n>=30 settled fires, win>=99%, EV/ct>=+0.12, day-clustered t>=3 | 0 fires after 21 days continuous coverage (~2026-08-09) → edge-as-implemented doesn't convert live; stop, don't deposit |
| 1 $10 canary | paper gate PASS | live Wilson95 win LB <97% or one-day drawdown >20% → `.kwx_halt` |
| 2 $50-$200 | n>=100 live fires, EV CI LB>0, fill>=90% | fill <90% past n=100 → freeze at $50 |
| 3 $200-$500 | depth_adaptive gate: >=15 distinct snapshot days, >=300 rows, stable medians | station medians swing >=2x → fixed DEPTH_CAP=25 forever |
| 4 $500-$1000 | depth cap resolved or fire-rate growth measured | ceiling: conservative flat ~$1.3k/mo past $500 — do NOT deposit past ~$1000 |

Sleeve activation (maker, early-lock, directional, book_watch) is CLOSED by studies — see the
GOAL RECALIBRATION section; those gates cannot accrue open again without new evidence of the
kind their kill reports specify.

## Controls (real, live-money — treat accordingly)

- `KWX_SWITCH` file: `on`/`off` — read by every leg before trading.
- `.kwx_halt` presence = hard halt (created on kill criteria; remove only after diagnosis).
- Repo secrets feed the legs: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY`, `SYNOPTIC_TOKEN`.
- Never bypass a gate "just this once": the gates ARE the strategy. The 2026-07-20 capacity
  model showed more bankroll past $500-1000 buys ~$0 — impatience has no payoff here.

## Gotchas

- `conservative_live` (fills observed live), not `conservative` (backtest fillable rate), is the
  honest planning scenario until real fires exist. They differ by ~9x today.
- The two fires/day sources in older docs (25.7 vs 10.4) are unreconciled — never quote either
  as fact; `wx_path_to_4k.py` prints both sensitivities.
- Gate ETAs quoted in docs assume accrual rates that live data has already contradicted once
  (book_watch's 7.8/day → measured ~0). Trust `kwx_goal_status.py`, not stale prose.
