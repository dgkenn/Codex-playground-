# Size-2 live experiment: pre-registered 1-week evaluation plan

**Experiment:** commit `1ec89c291` on main (deployed 2026-07-12) changed the live BTC bot
from `--post 1 --max-notional 5` to `--post 2 --max-notional 7`, time-boxed to ~1 week per
the capacity study (BTC per-box edge flat at 2x) and the Kelly study
(ladder `size(B) = clamp(floor(0.02·B), 1, 30)`; revert early if balance drops below $55).

**Evaluate on/after 2026-07-19.** A one-shot in-session reminder is scheduled for
2026-07-19 ~09:00, but it dies with the session — this file is the durable copy.

## Checklist

1. Pull the week's live telemetry from the `live-state` branch
   (`live_state/<day>/kalshi_winrec_btc15m.jsonl`, `kalshi_fees_btc15m.jsonl`,
   `live_recon_*.jsonl`, `order_lifecycle_*.jsonl`).
2. Compute at size 2: per-box edge vs the +0.85c size-1 anchor, fill rate,
   strand rate vs the 2.7%/window pivot from the Kelly study, realized daily
   P&L and max drawdown.
3. Read current balance (equity snapshots `gha_data/equity_*.jsonl` on the bot
   branch, or preflight balance log).

## Decision rule (pre-registered — do not re-litigate)

KEEP size 2 iff ALL of:
- balance ≥ $100 (ladder floor for size 2), AND
- per-box edge within ~30% of the size-1 anchor, AND
- strand rate < 2.7%/window.

Otherwise REVERT `live.yml` on main to `--post 1 --max-notional 5`.

Either way: report numbers + decision (Telegram + session), and rerun the Kelly
study distribution update with the fresh week of winrec data.

## Supersedure

If the Kelly-ladder auto-sizing (`--post auto`, built on the bot branch
`claude/polymarket-bot-live-ready-vw7ut5`) has been reviewed and deployed to
`live.yml` before the evaluation date, the manual keep/revert decision is
superseded — the ladder resolves size from balance every cycle. The evaluation
then only produces the metrics report + Kelly distribution refresh.
