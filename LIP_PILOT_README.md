# LIP_PILOT operator guide

This is the operator checklist for `venue_expansion/LIP_PILOT_REGISTRATION.md` (the frozen spec --
read it first; nothing here overrides it). Everything ships **off**. Nothing trades until you
deliberately flip two separate switches (see step 3 and step 5 below) -- that's intentional
defense in depth, not a bug.

## What ships in this state

- `LIP_SWITCH` = `off` (tracked file, committed).
- No `lip_markets.json` (the bot refuses to run without it -- see step 2).
- `.github/workflows/lip-pilot.yml`: gated on `LIP_SWITCH` + `.lip_halt`, `workflow_dispatch`-only
  for now (see "Scheduling" below).
- `lip_quoter.py` defaults to **dry-run** even if the switch is on, unless the workflow's `LIP_LIVE`
  repo variable is also set to `1` (step 5).

## Enable checklist

1. **Fund the account with <= $1,000** dedicated to this pilot. The caps in
   `LIP_PILOT_REGISTRATION.md` bound the worst case to that $1,000 (and realistically to the $100
   cumulative-loss hard stop), but don't fund more than you're prepared to have the caps govern.

2. **Author `lip_markets.json` at Day-0 recon** (this file is NOT provided -- the registration is
   explicit that market identity is not a tuned parameter, the operator picks it, once, from what's
   actually visible in the authenticated account view). Shape:

   ```json
   {
     "day0_date": "2026-08-01",
     "markets": [
       {"ticker": "KXBTCMAXY-...", "series": "KXBTCMAXY"},
       {"ticker": "KXETHMAXY-...", "series": "KXETHMAXY"},
       {"ticker": "KXINXY-...",    "series": "KXINXY"}
     ],
     "escalation": {
       "escalate_market": null,
       "after_zero_payout_days": 4,
       "armed": false
     }
   }
   ```

   Rules `lip_quoter.py` enforces on this file (refuses to start otherwise):
   - 3-5 markets (frozen policy range; hard cap 5).
   - no market/series may start with `KXHIGH` or `KXLOW` (the kwx conflict guard -- never the same
     series as a live kwx weather position).
   - no duplicate tickers.
   - the `escalation` block's `armed` field starts `false` and MUST be set by hand (see step 6) --
     the bot never decides on its own that the escalation condition has been met.

3. **Set `LIP_SWITCH` to `on`** (commit the change on the branch the workflow runs against). This
   arms the workflow's gate and lets `lip_quoter.py` run its full cycle logic -- reads, cap checks,
   reconciliation, self-audit -- but it is still logging-only (dry-run) until step 5.

4. **Rehearse first.** Trigger the workflow (`workflow_dispatch`) with `LIP_SWITCH=on` and the
   `LIP_LIVE` repo variable unset/not `1`. Watch `lip_pilot_log.jsonl` fill with `place_dry_run` /
   `amend_dry_run` / `snapshot` / `reconcile` / `payout_check` lines that describe exactly what a
   live leg would have done. Run `python lip_pilot_report.py` against it. Confirm the ladder,
   distances, and market set look right before touching real money.

5. **Go live**: set the `LIP_LIVE` **repository variable** (Settings -> Secrets and variables ->
   Actions -> Variables, NOT a secret -- it's not sensitive) to `1`. From the next leg onward,
   `lip_quoter.py` will actually POST orders, subject to every cap in `Caps` (see
   `lip_quoter.py`'s `Caps` class) checked before every placement, plus the self-audit re-check
   every cycle.

6. **The escalation step** (only after >= 4 calendar days of measured $0.00 total payout from the
   1-contract ladder, confirmed via `lip_pilot_report.py`'s F2 line): hand-edit `lip_markets.json`,
   set `escalation.escalate_market` to the chosen ticker and `escalation.armed` to `true`, commit.
   The next leg will place the ONE 100-contract order (<=15c, <=$15 cost-if-filled) at the far rung
   and hold it for >= 2 days. This is the only pre-registered exception to 1-contract sizing; the
   bot enforces its mechanics but never decides on its own to trigger it.

## How to halt

Either of these stops all trading (both are read by `lip_quoter.py` at startup AND every loop
iteration, and by the workflow's own gate step):

- **Soft**: set `LIP_SWITCH` back to `off` and commit. In-flight resting orders are left alone
  (they rest exchange-side); no new orders are placed and no more legs are dispatched.
- **Hard**: `printf 'operator halt %s\n' "$(date -u +%FT%TZ)" > .lip_halt && git add -f .lip_halt
  && git commit -m "manual halt" && git push`. This is exactly what a cap-violation or
  cumulative-loss kill path does automatically -- creating it by hand has the identical effect:
  every LIP- order gets batch-cancelled on the next (final) leg, and the workflow gate refuses to
  run at all after that.
- **Automatic**: `lip_quoter.py` writes `.lip_halt` itself (and batch-cancels + Telegram-alerts) on
  a cumulative realized loss reaching $100, or on any cap-violation detected by its self-audit
  (which never trusts local bookkeeping -- it recomputes exposure from Kalshi's own `/portfolio`
  endpoints every cycle). A daily loss reaching $25 is the softer path: it writes
  `.lip_stop_today` (new orders pause for the rest of the UTC day; existing orders are left resting;
  the switch stays on and the next calendar day resumes automatically).

## Where the daily report lands

`python lip_pilot_report.py` reads `lip_pilot_log.jsonl` (and `lip_payouts.jsonl`, if you're
recording payouts manually or via a future API scrape) and prints M1/M2/M3 plus the current F1/F2/F3
falsifier states and the days-to-program-end countdown. It's read-only -- safe to run any time,
including while a leg is in flight. Run it after every leg during the pilot; pipe `--out FILE` if
you want a saved copy.

## Falsifier decision calendar

Program window: **2026-09-01** (`F3` -- ends by calendar regardless of the other two).

| day (from Day 0) | checkpoint |
|---|---|
| ~day 7 | **F1**: is week 1's payout < realized fill losses + $2? If yes -> kill. |
| any day, ongoing | **F2**: are payouts ~$0.00 at every ladder distance? If sustained -> kill (do not chase to the touch -- that's the explicit non-goal). |
| day 4+ of $0.00 payout | escalation step becomes eligible (see step 6) -- ONE 100-contract order, ONE market, operator-armed. |
| ~day 14 | **success bar**: net (payout - fill P&L - fees) >= +$1/day over week 2 AND projected >= $30/mo. Below that: publish and stop, even if not technically falsified. |
| 2026-09-01 | **F3** -- program lapses. If no successor program is announced, this is the end regardless of M1-M3. |

## Scheduling note (frozen deployment trade-off)

Scheduled (`cron`) triggers only fire for the workflow file version committed to the repository's
**default branch**. `lip-pilot.yml` currently lives on `claude/calci-trading-bot-strategy-mgyxti`,
not `main` -- so the `schedule:` block in the workflow is commented out, and continuity runs
entirely on the pre-chain + self-chain `workflow_dispatch` pattern (same shape as `kwx-live.yml`,
which explains the mechanism in more detail). Once this file is merged to the default branch,
uncomment the `schedule:` block for the ~20-minute cron backup; until then, kick off the chain once
manually (`workflow_dispatch`) after step 3/5 above and it will keep itself alive as long as
`LIP_SWITCH` stays `on`.

## Known limitation, disclosed

Orders rest exchange-side between legs, but each leg starts from a fresh GHA checkout with a
~60-90s inter-leg gap (the GHA self-chain pattern, not a dedicated always-on process -- see
`venue_expansion/ENGINEERING_STACK.md` for why a us-east-2 VPS is the stack-correct home this pilot
deliberately doesn't require). At 1-contract size and hard-capped loss, this is an accepted,
disclosed pilot limitation, not an oversight.
