# LIP_PILOT — pre-registered 2-week de minimis pilot of Kalshi's Liquidity Incentive Program
**REGISTERED 2026-07-30, frozen before any order is placed. Program window ends 2026-09-01.**

## Objective (measurement, not profit)

The LIP pays $10–$1,000/day pools for quoting **presence** (per-second snapshots of
`order_size × distance_multiplier`), not fills. Two load-bearing parameters are unpublished and
undocumented anywhere: the **pool scope** (exchange-wide vs per-market) and the **Distance
Discount Factor** curve; a third ambiguity is whether "Target Size: 100–20,000 contracts" is a
per-order floor. This pilot measures, with ≤$1,000 collateral at risk:

- **M1**: $ payout per day per unit of (size × distance × uptime) — calibrates score share + discount curve
- **M2**: fill rate on resting orders as a function of distance from touch
- **M3**: realized per-fill P&L (settlement-inclusive, fee-inclusive) vs the measured
  −8.81c/ct pessimistic bound from `MAKER_VIABILITY.md`

## Hard caps (fail-closed; violating any = bug, halt immediately)

| cap | value |
|---|---|
| Account collateral exposed to pilot | ≤ $1,000 |
| Aggregate cost basis of open positions | ≤ $300 |
| Aggregate resting-order cost (sum of price×size of open orders) | ≤ $100 |
| Per-order size | 1 contract (escalation step below is the only exception) |
| Per-market position | ≤ 10 contracts |
| Daily realized loss | ≤ $25 → halt for the day |
| Cumulative pilot realized loss | ≤ $100 → **hard stop, pilot over, publish kill** |
| Switch | file `LIP_SWITCH` must read `on`; `.lip_halt` present ⇒ inert; missing Kalshi secrets ⇒ inert |

These caps make the sweep's worked-example-B disaster (1,000-contract adverse day = −$88)
structurally impossible: max theoretical one-day loss is bounded by the caps, not by luck.

## Quote policy (frozen)

- **Distance ladder**: each selected market carries 1-contract resting orders at distances
  **{1, 3, 5, 8}c** from the current touch on each quoted side, re-centered when the touch moves
  by ≥2c (re-centering cadence bounded to ≤1 amend/order/minute to respect churn discipline and
  rate limits). Ladder assignments rotate daily across markets so the discount curve is
  identifiable from payout variation.
- **Two-sided** where position caps allow; the side that would grow |position| beyond cap stops
  quoting (delta discipline).
- **Markets**: 3–5, chosen by frozen rule at Day 0 recon: (i) appear on the LIP-incentivized list
  as visible in the authenticated account/app view; (ii) prefer categories with $0 or minimal
  maker fee; (iii) prefer high snapshot-hours (long trading sessions) over episodic markets;
  (iv) never the same series as any live kwx weather position. If no incentivized list is
  programmatically visible, Day-0 recon documents what IS visible and the operator picks from it —
  market identity is not a tuned parameter, the policy is.
- **Escalation step (single, pre-registered)**: if ≥4 calendar days of measured presence produce
  **$0.00 total payout** from 1-contract orders, ONE market gets ONE 100-contract order at a price
  ≤15c (cost-if-filled ≤$15, inside all caps) at the far rung for ≥2 days — this isolates the
  Target-Size-floor hypothesis. No other size increase is permitted during the pilot.

## Falsifiers (frozen; any one ⇒ kill the LIP line, fall back to the graveyard publication)

- **F1**: First full week's payout < realized fill losses + $2 → net-negative even with the 3.25%
  APY offset → kill in ~7 days.
- **F2**: Payouts ≈ $0 at all ladder distances (discount factor zeroes off-touch presence AND/OR
  the Target-Size escalation also pays $0) while at-touch quoting is the only scoring option →
  the program requires exactly the exposure `MAKER_VIABILITY.md` measured as unstable-to-negative
  → kill without moving to the touch.
- **F3**: Program lapses 2026-09-01 without a successor → ends by calendar.
- **Success bar to continue past day 14**: net (payout − fill P&L − fees) ≥ +$1/day sustained over
  the second week AND projected ≥ $30/mo at ≤$1k collateral. Below that, the honest verdict is
  "real but not worth the operational risk" — publish and stop.

## Deployment (pilot-expedient, documented trade-offs)

- Runs on the repo's proven **GHA self-chaining pattern** (pre-chain + self-chain + cron backup,
  singleton concurrency), one persistent ~16-minute warm Python process per leg — the
  `ENGINEERING_STACK.md` subprocess-tax lesson applied within what GHA allows. Orders rest
  exchange-side between legs; the ~60–90s inter-leg gaps mean stale-quote risk, accepted at
  1-contract size and capped loss, and disclosed as a pilot limitation (the stack-correct home is
  a us-east-2 VPS; the pilot does not require it).
- **Scheduled runs require the workflow file on the default branch**; until merged, the chain runs
  on `workflow_dispatch` self-dispatch targeting this branch. The README documents both modes.
- Reuses the existing secrets names (`KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY`, `TELEGRAM_*`);
  ships with `LIP_SWITCH=off`. **Nothing trades until the operator flips the switch.**
- Every order/cancel/fill/snapshot appended to `lip_pilot_log.jsonl` (committed each leg);
  payouts recorded in `lip_payouts.jsonl` (manual or API-scraped when visible). Analysis script
  `lip_pilot_report.py` renders M1–M3 and the falsifier states daily.

## What this is not

Not a return to edge-hunting: the revenue line is a documented program payment, the trading policy
is designed to minimize (and measure) fill exposure rather than seek it, and the caps bound the
worst case to coffee money. A kill here is cheap and final for the LIP line; the fallback
(graveyard publication) is already scoped.
