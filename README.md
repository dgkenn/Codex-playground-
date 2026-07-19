# Codex-playground — Kalshi weather-nowcast trading bot (K-WX)

This repo is now a single live trading system: **K-WX**, a Kalshi
temperature settlement-nowcast bot. Everything else here is retired research and
lives under [`archive/`](archive/).

## What it does

K-WX trades Kalshi daily high/low **temperature** ladder markets (~20 US cities,
both high and low, the full 6-rung ladder). The edge is mechanical: once the
observed station temperature has cleared a strike, that rung can only settle
in-the-money, so the bot buys it before slow retail finishes repricing.

- Validated on full all-city history (Phase-2 Track A): **+0.207/ct, ~99.6% win,
  t=37**, on the ~37% of fires that have a real gap.
- The gap has a **~3.3-minute half-life**, so detection speed is the whole game —
  captured EV is ~+0.15–0.17/ct at a realistic 2–5 min feed latency.
- Sizing is Monte-Carlo optimized: **quarter-Kelly × 5% per-fire cap × ~17.5%
  per-city cap**, ruin ≈ 0. This is a **small-capital** edge (capacity ceiling
  ~$1–1.6k/week of profit); it does not scale to large AUM.

See `THE_PLAN.md` for the honest return distribution and `KWX_DEPLOY.md` for the
full deployment runbook and go-live gates.

## Live components

| file | role |
|---|---|
| `kwx_runner.py` | LIVE loop: feed → running max/min → adaptive-cadence polling → glitch/sustain cross → locked-rung detection → order |
| `kalshi_exec.py` | Kalshi order client — **dry-run unless `KWX_LIVE=1` AND `.kalshi_creds` both present** |
| `kwx_paper_gate.py` | turnkey paper driver: runs the loop in paper, settles + reports, writes `kwx_gate_status.txt` verdict |
| `kwx_forward.py` | settles paper fires vs Kalshi results, compares realized **live vs backtest** (the hard go-live gate) |
| `kwx_selftest.py` | fast self-test of the fire path + guards (the CI/pre-commit gate) |
| `kwx_notify.py` / `kwx_telegram.py` | Telegram alerts (FIRE / SETTLE / HALT) and `/on` `/off` control |
| `kwx_sizing.py`, `kwx_conviction_sizing.py`, `kwx_exit_rules.py`, `kwx_metrics.py`, `kwx_turnover.py` | sizing, conviction, exit, and metrics helpers |
| feeds: `aviationweather_metar.py`, `weathergov_feed.py`, `madis_feed.py`, `synoptic_feed.py` | temperature feeds (published METAR + api.weather.gov confirmation; Synoptic HF-ASOS for the fast band) |
| forecast/study modules: `wx_forecast_model.py`, `wx_forecast_forward.py`, `wx_capacity_probe.py`, `phase2_trackB_tail.py`, `kalshi_weather_*.py`, `kalshi_wx_settlement_basis.py` | forecast overlay, capacity/tail studies, settlement-basis analysis |

Data flow: feed → `kwx_runner.poll_once()` → `kalshi_exec` (dry-run) →
`kwx_runner_plan.jsonl` → `kwx_forward settle` → `kwx_forward_settled.jsonl` →
`report` (tested == live).

## Operating it

**On/off switch.** The live bot trades only when `KWX_SWITCH` contains `on`
**and** the Kalshi secrets exist; otherwise it is completely inert (fail-closed).

```
./kwx_switch.sh on      # start live trading ($10 canary), clears .kwx_halt
./kwx_switch.sh off     # stop
./kwx_switch.sh status  # show current switch
```

You can also toggle it from Telegram with `/on` and `/off`.

**Kill switch / guards.** `touch .kwx_halt` blocks all live orders instantly
(`rm` to resume). A circuit breaker auto-halts on a suspected feed glitch
(>15 fires/cycle), plus a daily-deployment cap, fat-finger ceilings, per-order
idempotency, and feed-staleness drop are always on.

## Workflows (GitHub Actions, all `kwx-*`)

| workflow | purpose |
|---|---|
| `kwx-live.yml` | the live bot — self-healing chain (pre-chain + self-chain + 20-min cron backup), singleton concurrency, gated on `KWX_SWITCH` + secrets |
| `kwx-forecast.yml` | forecast overlay refresh |
| `kwx-depthprobe.yml` | order-book depth / capacity probing |
| `kwx-telegram.yml` | Telegram command + alert bridge |
| `kwx-watchdog.yml` | heartbeat watchdog — alerts + re-dispatches if the live chain goes stale |
| `kwx-ci.yml` | runs `kwx_selftest.py` on the working branch |

## Archive

`archive/` holds retired strategies that no longer run — box, favlong, polymarket
(pmkt), perp, wing, longshot, btc/deribit derivatives, short-vol, ETF/macro, and
various Kalshi trader experiments. See `archive/README.md` for a one-line index.
Nothing under `archive/` is imported by the live weather bot.
