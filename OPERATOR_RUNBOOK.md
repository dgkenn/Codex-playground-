# Operator Runbook — Kalshi multi-market / multi-strategy bot

One page. What's actually deployed, what to watch, what to do when it breaks. Everything below is
read directly from `main`'s `.github/workflows/*.yml` and this branch's scripts as of this commit —
nothing aspirational. Where something is paper-only or alert-only, it says so.

## 1. THE ONE CONTROL: LIVE_SWITCH

`LIVE_SWITCH` (one word, `on`/`off`) on branch `claude/polymarket-bot-live-ready-vw7ut5` is the
entire control surface for real money. `.github/workflows/live.yml` (on `main`) reads it every
cycle; when `off` or a kill sentinel is present, the job is a no-op.

- **Flip it:** `./live_switch.sh on|off` (or `status`). Commits+pushes the file with retry/rebase.
  Also controllable by **texting `on` / `off` / `status` to the Telegram bot** — `telegram_control.py`
  long-polls Telegram and calls `live_switch.sh`; it now runs piggybacked inside every
  `paper-collect` cycle (durable, not VM-only) so texting the bot works even with no local process.
- **Fail-closed by default:** missing `KALSHI_API_KEY_ID`/`KALSHI_PRIVATE_KEY` repo secrets, OR
  `LIVE_SWITCH != on` ⇒ the job does nothing. `live.yml` must live on `main` to fire at all, but
  checks out trading code from the live-ready branch.
- **What flips it to `off` automatically (sticky kill):**
  1. **Per-asset loss-limit / toxic-markout / error-storm kill** inside `kalshi_trader.py`
     (`--loss-limit 6`). On trip it writes a local sentinel (`.kalshi_killed_<asset>15m`) and, per
     `DEADMAN_AUDIT.md` fix #1, immediately calls `remote_switch_kill()` to PUT `LIVE_SWITCH=off`
     via the GitHub contents API from *inside the trading process* (not deferred to a later
     workflow step, which a hard-killed runner could skip). `live.yml`'s own "persist telemetry +
     sticky-kill" step is a second, redundant durability path that does the same commit if the
     sentinel is present when the job finishes normally.
  2. **Portfolio guardian** (`portfolio_guardian.py`, run by `equity.yml` every 6h): read-only,
     GET-only judge over account balance/positions. On **CRITICAL** — daily drawdown >15% vs the
     most recent prior-day snapshot, OR all-time drawdown >30% vs the highest balance ever
     recorded — it flips `LIVE_SWITCH=off` via the same `remote_switch_kill()` mechanism and
     Telegram-alerts with the exact numbers. Open notional >50% of balance is **WARN only**
     (Telegram, switch untouched — a busy book isn't necessarily an unhealthy one).
- **Re-arm:** `./live_switch.sh on` — this is the only thing that also clears the local kill
  sentinel. Never automatic; always a deliberate operator action, and only after investigating why
  the kill fired.

**Current live config** (from `main`'s `live.yml`, `--asset btc` only — one sleeve is live):
`kalshi_trader.py --asset btc --live --gate as --size-mode markout --skew 0.99 --post 1
--max-notional 5 --loss-limit 6 --max-rungs 1 --guard-yes-spread 0
--strand-scaledown 0.75,0.5,0.25 --max-fills-side 3 --pair-gate --pair-min-depth 33000
--open-k-min 2 --open-k-max 10 --dispose-cross --dispose-cross-s 15 --close-force-s 45
--chase-unpaired-s 15 --dispose-max-give 0.25 --post-complete-freeze 1.5 --duration 2760
--remote-switch-s 20`. Gate/size-mode is the Avellaneda-Stoikov inventory gate + markout-weighted
sizing (32-day shadow A/B winner, see `WINNING_STRATEGY.md`), not the roster default. Cap is $5
notional/cycle, $6 sticky loss-limit, post-only both sides, single asset (btc). Cron re-checks the
switch every ~25 min (`3,28,53 * * * *`) so a dead runner's chain restarts itself; a live run
self-chains via `workflow_dispatch` while the switch stays on.

## 2. Every workflow on `main` (16 total)

All checkout **code** from `claude/polymarket-bot-live-ready-vw7ut5`; all write **data** to the
`gha-data` branch (never the code branch) unless noted. Concurrency groups prevent double-runs.

**Trading**
| Workflow | Cadence | Does |
|---|---|---|
| `live.yml` | cron `3,28,53 * * * *` + self-chain | Gate on `LIVE_SWITCH`+secrets → `kalshi_preflight.py` GO/NO-GO → real-money `kalshi_trader.py --live` (btc only, ~46min run) → persists fee/markout/winrec telemetry to the `live-state` branch → self-chains next run while switch is on. |
| `equity.yml` | cron every 6h (`37 3,9,15,21 * * *`) | Read-only `equity_snap.py` (balance+positions snapshot → `gha_data/equity_<date>.jsonl` on gha-data) + `portfolio_guardian.py` (may flip `LIVE_SWITCH=off`, see §1). No order-placing code in either script. |

**Collection (shadow A/B corpus for the crypto maker-box strategy)**
| Workflow | Cadence | Does |
|---|---|---|
| `collect.yml` | cron `9,29,49 * * * *` (chain-restart backstop) + self-chain | ~42min run of `kalshi_collect.py` (KX{BTC,ETH,SOL,XRP}15M shadow strategy variants) + `pmkt_collect.py` (Polymarket cross-venue BTC 5m) + `kalshi_ladder_collect.py` + `kalshi_thin_collect.py`, all in parallel; runs the Telegram on/off/status poller (`telegram_control.py`) piggybacked; writes `gha_data/SUMMARY.txt`; also **reseeds the live chain** if `LIVE_SWITCH=on` but no `live.yml` run is queued/in-progress (self-healing watchdog for the live chain specifically). |
| `sidecar-feeds.yml` | cron `6,36 * * * *` | `sidecar_feeds.py`: composite Binance+Coinbase spot mid, Kalshi WS latency stamps (needs Kalshi secrets; degrades gracefully without), 7-day macro calendar (CPI/FOMC/NFP/PPI/GDP). |
| `strategy-fine.yml` | manual dispatch only (schedule retired 2026-06-10, study concluded) | Reconstructs top-5 wallets' exact placement logic from WS book + fills. |
| `wallet-track.yml` | cron every 6h (`23 */6 * * *`) | Snapshots watch-list maker wallets to `wallet_track.jsonl` (drift detection). |

**Paper sleeves (forward OOS validation, no money, no keys except where noted)**
| Workflow | Cadence | Does |
|---|---|---|
| `etf-paper.yml` | weekly, Mon `30 14 * * 1` | `portfolio_live.py`/`allweather_live.py --paper-track`: ETF momentum/trend + all-weather sleeves, appends to `gha_data/paper/*.jsonl`. Building the forward Sharpe track needed before any real ETF money. |
| `kalshi-longshot.yml` | daily `30 17 * * *` | `kalshi_longshot_paper.py`: settles + snapshots a paper longshot-sell-harvest strategy → `gha_data/longshot/`. |
| `kalshi-weather.yml` | 2x daily (`15 16,22 * * *`) | `weather_clv_harness.py`: Kalshi weather book vs NBM fair value → `gha_data/weather/weather_clv_log.csv`. Accumulating CLV data to test if the mispricing is real before risking size. |
| `kxwti-paper.yml` | 2x daily (`41 13,21 * * *`) | `kxwti_paper.py`: WTI crude daily-strike-ladder maker paper-track → `gha_data/kxwti_*`. |
| `macro-paper.yml` | daily `52 15 * * *` | `macro_paper.py`: CPI/Fed-decision event-market paper-track → `gha_data/macro_*`. |
| `sports-clv.yml` | 3x daily | `sports_clv_collect.py`: Pinnacle vs Kalshi lag data → `gha_data/sports_clv/`. No-op without `ODDS_API_KEY` secret (not currently set, per the workflow's own comment). |

**Monitoring / ops**
| Workflow | Cadence | Does |
|---|---|---|
| `health.yml` | cron every 30min (`14,44 * * * *`) | `health_check.py`: independent freshness/content-validity check of every collected stream on gha-data. On CRITICAL (stall >130min or empty-payload stream): Telegram alert + reseeds `collect.yml`. Daily ~14:14 UTC heartbeat so silence never means "is it dead?". |
| `dashboard.yml` | daily `7 5 * * *` | `promotion_check.py` (alert-only pre-registered promotion bar, §5) then `dashboard.py` renders `gha_data/DASHBOARD.html`, committed to gha-data. |
| `strategy-alert.yml` | hourly (`17 * * * *`) | `box_policy_ab.py --alert` per asset (btc/eth/sol/xrp): scores every trial strategy's forward A/B ledger; Telegram + GitHub `::warning::` on DEPLOY-READY / RISK-UPGRADE-READY / 2-sigma crossings (§3). Appends a metrics snapshot to `gha_data/metrics/<date>/`. |
| `venue-scan.yml` | daily `23 11 * * *` | `market_scanner.py`: whole-venue Kalshi sweep for other maker-box-shaped opportunities → `gha_data/venue_scan_*.jsonl.gz`. Pure research, no strategy attached. |

## 3. Alerts you may receive (Telegram)

All alerts are best-effort (`notify.alert`/`alert_sync`, no-op if `TELEGRAM_BOT_TOKEN`/
`TELEGRAM_CHAT_ID` unset) and never block trading. Patterns, grepped from the source:

| Alert (prefix/pattern) | Source | Meaning → action |
|---|---|---|
| `🟢 live session armed (btc) — preflight GO...` | `live.yml` | Cycle started trading. Informational. |
| `🟡 live cycle skipped (btc) — preflight NO-GO...` | `live.yml` | `kalshi_preflight.py` said NO-GO this cycle (market/balance gate). Retries next cycle automatically — no action unless it repeats for hours. |
| `[kalshi] KILL loss-limit (real ... worst-open ...)` / `KILL markout toxic` | `kalshi_trader.py` | Per-asset sticky kill fired; `LIVE_SWITCH` is being flipped off. **Investigate before re-arming.** |
| `[kalshi] DEAD-MAN <reason>: cancel-all` | `kalshi_trader.py` | Feed staleness / error storm tripped the dead-man; all orders cancelled, position flattened where possible. Check the run log for `<reason>`. |
| `🚨 FOREIGN ORDER on <ticker>...ANOTHER TRADER IS LIVE` | `kalshi_trader.py` | An order exists on the account that this process didn't place — a second trader instance is running somewhere. **Stop and confirm exactly one trader before re-arming** (single-trader invariant). |
| `⚠️ [kalshi] inherited venue position at startup...` | `kalshi_trader.py` | Startup found existing venue inventory (from a prior dead runner); it was seeded into this session's risk state, not ignored. Informational unless it keeps recurring. |
| `📦 box paired (...)+...c/pair locked` / `box flattened` | `kalshi_trader.py` | Normal fill/settlement telemetry. Informational. |
| `[kalshi btc] HH:MMZ settled WIN/LOSS ±X.XX (session ±Y.YY)` | `kalshi_trader.py` | Per-window settlement result. Informational. |
| `🚨 FEE ALERT: maker fill charged fee=...` | `kalshi_trader.py` | Crypto-15m maker fee should be $0 (a known invariant); a nonzero fee means something changed venue-side. **Investigate.** |
| `⚠️ INVENTORY BREACH: \|net\|=... exceeds max-net` | `kalshi_trader.py` | Pairing discipline breached (`--max-net 1`). **Investigate.** |
| `🔴 live bot OFF (remote switch) — flattening...` | `kalshi_trader.py` | Operator (or a guardian) flipped the switch off mid-run; the bot is self-flattening (polls the switch every ~20s, so OFF takes <1min, not the full cycle). Informational. |
| `🚨 PORTFOLIO GUARDIAN — CRITICAL\n<rule>\n<switch status>` | `portfolio_guardian.py` (via `equity.yml`) | Daily or all-time drawdown limit breached; `LIVE_SWITCH` durably flipped off (or the flip failed — message says which). **Investigate before `./live_switch.sh on`.** |
| `⚠️ PORTFOLIO GUARDIAN — WARN\nEXPOSURE: ...` | `portfolio_guardian.py` | Open notional >50% of balance. Switch untouched — informational, go look at the book. |
| `⚠️ [portfolio_guardian] switch-off PUT FAILED...flip it manually` | `portfolio_guardian.py` | The guardian wanted to kill but the GitHub API PUT failed after retries. **Flip `./live_switch.sh off` manually immediately.** |
| `⚠️ data collection <WARN|CRITICAL>\n...` | `health_check.py` (via `health.yml`) | A collector stream is stale (>130min) or empty-payload. `health.yml` already auto-reseeds `collect.yml` on CRITICAL; this alert is FYI unless it repeats. |
| `✅ data collectors healthy — ...` | `health_check.py` | Daily ~14:14 UTC passive heartbeat. Absence of this for >1 day with no CRITICAL alert either is itself suspicious (check manually). |
| `PROMOTION BAR CLEARED (pre-registered, strategies.py): PROMOTE-READY ...` | `promotion_check.py` (via `dashboard.yml`) | A shadow-A/B candidate cleared the global promotion bar (§5). **Alert-only — nothing is auto-promoted.** Review and manually edit `strategies.py`/live config if warranted. |
| `PER-MARKET TAILORING OPPORTUNITY...TAILOR-READY ...` | `promotion_check.py` | A per-asset challenger beat the champion (`av_stoikov`) head-to-head on one market (§5). Alert-only. |
| `🚀 DEPLOY-READY [<asset>]: trial(s) cleared the pre-registered deploy bar...` | `box_policy_ab.py --alert` (via `strategy-alert.yml`) | Hourly 2-sigma bar cleared (paired \|t\|>2, ≥100 forward windows) vs the live baseline. Alert-only; also written to `STRATEGY_ALERTS.txt` and a GitHub `::warning::`. |
| `🛡️ RISK-UPGRADE-READY [<asset>]: ...` | `box_policy_ab.py --alert` | A trial is net non-inferior with materially lower tail risk (MaxDD/CVaR) than live. Alert-only. |

`REBALANCE-SUGGESTED` (`portfolio_allocator.py`) is **not** a Telegram alert — it only ever appears
as a flag inside the `gha_data/DASHBOARD.html` Portfolio section (§4) when the fractional-Kelly
recommendation for the live crypto sleeve diverges >2x from the `--max-notional`/`--loss-limit`
actually deployed in `live.yml`. No workflow pings Telegram for it; check the dashboard.

## 4. Dashboards & data

- **`gha_data/DASHBOARD.html`** on the **`gha-data`** branch (rendered nightly by `dashboard.yml`,
  05:07 UTC). Self-contained HTML (inline SVG, no external assets). Sections, top to bottom:
  **Portfolio: account equity** (curve from `gha_data/equity_*.jsonl`); **Portfolio: per-sleeve P&L
  attribution** (`sleeve_ledger.py` — see below); **Portfolio: allocator recommendation**
  (`portfolio_allocator.py`, alert-only, includes the `REBALANCE-SUGGESTED` flag from §3); then the
  pre-existing shadow-A/B sections — 30-day trend of daily edge-vs-baseline for top arms, latest
  day-clustered leaderboard, decay-watch status, live-recon (real fills vs shadow, if that data
  exists), verdict-ledger family win/loss stats. Every section is independently guarded — missing
  input renders a "not available" note rather than breaking the page.
- **Sleeve ledger** (`sleeve_ledger.py`, new — feeds the dashboard's Portfolio sections): normalizes
  every sleeve into one row shape (`{date, sleeve, pnl_usd, notional_usd, n_trades, is_live}`).
  `crypto_mm_<asset>` is the only `is_live=true` sleeve today (reads `gha_data/live_recon_*` or
  `live-state`'s `kalshi_winrec_*`); `longshot_paper`, `wti_paper`, `macro_paper` are paper-only,
  each sourced from that sleeve's own settled-CSV/JSONL (§4 paths below). Run standalone with
  `python sleeve_ledger.py [--days N]` for a plain-text per-sleeve table. `portfolio_allocator.py`
  (`python portfolio_allocator.py --bankroll 50`) is a fractional-Kelly capital-allocation
  recommendation over those sleeves — **alert-only, never writes to any config**; paper sleeves get
  $0 real allocation but show a would-be $ figure for promotion-decision context. No workflow runs
  either script standalone — both are only invoked from inside `dashboard.py` (via `dashboard.yml`).
- **`gha_data/<date>/SUMMARY.txt`** — per-collect-cycle output of `aggregate_shadow.py`. Two key
  tables: the top **paired-t comparison** (variant net/win vs baseline, paired t over shared
  windows — the powerful test since window outcome variance is shared across variants) and the
  **day-clustered table** (`n_days`, `mean Δ/day`, `clust t`, `days+`) — windows within a day share
  one regime, so day-level clustering is the honest significance test, not raw window count.
  **Decay watch**: tracks the currently-*deployed* variant (`DEPLOYED = "micro_gate"` in
  `aggregate_shadow.py`) over the trailing 14 UTC days specifically — flags `DECAY-ALERT: ...
  looks INERT` (edge collapsed toward zero) or `...looks DECAYED` (day-clustered-significantly
  negative). This is a distinct thing from live btc trading, which currently runs a different
  gate/size-mode (`as`/`markout`, §1) — check which arm is actually live before reading decay watch.
- **Equity snapshots**: `gha_data/equity_<YYYY-MM-DD>.jsonl` on `gha-data`, one JSON line per
  `equity.yml` run (`{ts, balance_cents, positions, n_open}`); multiple rows/day are expected
  (guardian and digest both read the *last* row of a date).
- **Live trader telemetry** (fees/markout/winrec/live-metrics jsonl): the **`live-state`** branch,
  under `live_state/<YYYY-MM-DD>/`, one commit per `live.yml` run.
- **Paper sleeve ledgers**: all under `gha_data/` on `gha-data` — `gha_data/paper/` (ETF/all-weather
  paper tracks), `gha_data/longshot/` (longshot-sell paper), `gha_data/kxwti_*` (WTI ladder paper),
  `gha_data/macro_*` (CPI/Fed paper), `gha_data/weather/` (weather CLV log), `gha_data/sports_clv/`
  (sports lag data), `gha_data/venue_scan_*.jsonl.gz` (venue sweep), `gha_data/metrics/<date>/`
  (hourly per-trial risk/perf snapshots). Pull any of these with
  `git fetch origin gha-data && git checkout origin/gha-data -- gha_data/<path>`.

## 5. Promotion discipline

**Nothing goes live without clearing a pre-registered forward bar first.** All bars below were
declared in code *before* the data that judges them was collected; `promotion_check.py` never edits
the roster — promotion is always a human decision made after reading its output.

**Global promotion bar** (`promotion_check.py`, `as_markout`/roster note in `strategies.py`) — a
candidate must clear ALL of:
- `n_days >= 14` forward UTC days of paired data vs baseline (`MIN_DAYS`)
- day-clustered `t >= 3.0` on the daily mean of (variant − baseline) net, one obs/day (`T_BAR`)
- gross-positive on `>= 80%` of those days — the edge must exist outside rebate harvesting
  (`GROSS_POS_FRAC`)
- mean edge on shared days `>=` the best of the two current reference winners (`av_stoikov`,
  `mo_size`) over those *same* days — an unfair regime-luck comparison otherwise

**Per-market dethronement bar** (`per_market_champion.py`, reused by `promotion_check.py`'s
per-asset section) — a challenger must clear ALL of, head-to-head vs the global champion
(`av_stoikov`) on that one asset:
- day-clustered `t >= 3.0` (`TAILOR_T_BAR`)
- days-positive fraction `>= 0.70` (`TAILOR_DAYS_POS_BAR`)
- `n_days >= 10` of head-to-head data (`MIN_DAYS_EVAL`) — fewer than 5 days doesn't even print as a
  candidate line, 5–9 prints informationally as "per-market" but can never flag TAILOR-READY

**Macro sleeve event-count bar** (`macro_paper.py` module docstring — deliberately NOT the 14-day
bar, since CPI/FOMC events are monthly cadence and a day-count bar is meaningless there):
`>= 6 settled events` AND aggregate `t >= 2`. Score anytime with
`python edge_verdicts.py score gha_data/macro_settled.jsonl --kind generic`.

**KXWTI sleeve bar** (`kxwti_paper.py` docstring / `edge_verdicts.py`): `>= 14 forward days`,
day-clustered `t >= 3`, positive on `>= 80%` of days. Score with
`python edge_verdicts.py score gha_data/kxwti_settled.csv`.

Every bar's check is **alert-only**: it prints/Telegrams `PROMOTE-READY`/`TAILOR-READY`/`wait
<reasons>` and never writes to `strategies.py`, `live.yml`, or any config. Acting on a cleared bar
(editing the roster, changing `live.yml`'s flags) is always a manual operator step.

## 6. Weekly 10-minute checklist

1. `./live_switch.sh status` — confirm the switch state matches what you expect, and that no kill
   sentinel is sitting there unexplained.
2. Open `gha_data/DASHBOARD.html` (gha-data branch) — check the decay-watch line for the currently
   *deployed* live variant is not `DECAY-ALERT`; skim the 30-day trend chart for a sign flip.
3. Check the last few `equity_<date>.jsonl` rows (or the Telegram equity digest) — balance trend
   sane, no unexplained drawdown between checks.
4. Scan Telegram history for the last 7 days for any `KILL`, `DEAD-MAN`, `FOREIGN ORDER`, `FEE
   ALERT`, `INVENTORY BREACH`, or `PORTFOLIO GUARDIAN — CRITICAL` message you haven't already acted
   on (§3).
5. Confirm the daily `✅ data collectors healthy` heartbeat has appeared at least once in the past
   day (its absence, with no CRITICAL either, means check `health.yml`'s run history manually).
6. Skim any `PROMOTE-READY` / `TAILOR-READY` / `DEPLOY-READY` / `RISK-UPGRADE-READY` alerts — these
   require a manual roster/config decision, they don't act themselves.
7. Spot-check that `live.yml` and `collect.yml` both have recent successful runs in the Actions tab
   (self-chain + cron backstop should mean gaps are rare — a multi-hour gap on either is worth
   investigating even with no alert).

**Escalation triggers** (stop and investigate immediately, don't wait for the weekly pass):
`FOREIGN ORDER`, `PORTFOLIO GUARDIAN — CRITICAL`, `FEE ALERT`, repeated `KILL` on the same day,
`switch-off PUT FAILED`, or `LIVE_SWITCH` reading `on` while you did not intentionally re-arm it.

## 7. Recovery playbook

- **Chain stalled (no `live.yml` or `collect.yml` runs for a while, no CRITICAL alert):**
  `collect.yml` already reseeds `live.yml` if the switch is on and no live run is queued/in-progress
  (its "live watchdog" step), and `health.yml` reseeds `collect.yml` on CRITICAL (>130min stale).
  If both chains are down simultaneously, manually `workflow_dispatch` `collect.yml` from the
  Actions tab (ref `main`) — its self-chain and the live-reseed step will re-establish both.
- **Kill tripped (per-asset sticky loss-limit / toxic-markout / error-storm):** `LIVE_SWITCH` is
  already off (durably, per DEADMAN_AUDIT fix #1 — the trading process itself commits the flip, not
  a later workflow step, so this survives a hard runner death). Read the kill alert for the reason
  and the numbers. Check recent fills/settlements in the `live-state` branch telemetry. Only run
  `./live_switch.sh on` once you understand why it fired — this also clears the local kill sentinel.
- **Portfolio guardian fired (CRITICAL drawdown):** same as above — switch is already off. Pull
  `gha_data/equity_*.jsonl` to see the balance history that tripped `DAILY_DD_FRAC` (15%) or
  `TOTAL_DD_FRAC` (30%). If the guardian's Telegram message says the switch-off PUT itself failed,
  flip it manually with `./live_switch.sh off` right away, then investigate.
- **Secrets rotation:** `live.yml`, `equity.yml`, and `sidecar-feeds.yml`'s WS-latency loop all
  read `KALSHI_API_KEY_ID`/`KALSHI_PRIVATE_KEY` from repo secrets; rotating them is a plain GitHub
  Settings → Secrets update, no code change. All three workflows are already fail-closed/no-op on
  missing or invalid secrets, so a mid-rotation gap just pauses those workflows rather than
  erroring. `ODDS_API_KEY` (sports-clv) and `HEARTBEAT_URL` (collect.yml, healthchecks.io dead-man)
  are optional and independently no-op-safe if unset.
- **GitHub cron flakiness:** documented directly in `collect.yml`'s header — GitHub sheds schedule
  ticks under load, which is why every collector is self-chaining (dispatches its own successor)
  with cron as a restart-only backstop, and why `health.yml` exists as a wholly separate cron/failure
  domain to catch a total chain death. **The naked-leg watchdog is NOT yet implemented**:
  `DEADMAN_AUDIT.md` recommends (fix #3, not yet built) a separate, narrowly-scoped workflow that
  checks for any non-zero position on the live series when `live.yml` is not in-progress/queued and
  force-flattens it — closing the gap where a runner dies mid-window holding a naked (unpaired) leg
  with no active disposal management until Kalshi's own settlement clock resolves it (bounded to the
  15-minute window, and to `--max-notional 5` in dollar terms, but currently unmanaged for that
  window). Until it exists, a mid-window runner death's naked-leg exposure is bounded but passive —
  no immediate action possible beyond waiting for settlement or the next scheduled equity snapshot.
