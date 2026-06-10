# Polymarket crypto 15-min market-maker — research → live

A read-only-by-default research + paper-trading stack for market-making Polymarket's **BTC/ETH/SOL/XRP
15-minute Up/Down** markets, plus a deployable live bot. **The edge is the maker rebate**, harvested by
quoting two-sided, tiny, delta-neutral, and dodging adversely-selected fills. There is **no directional
alpha** (BTC-prediction and favorite-longshot were both tested and rejected).

> Status: paper-validated, **not yet confirmed live**. The single biggest open question is whether the
> maker rebate actually pays at our tier (`PAPER_VS_LIVE.md` A1) — that's what the $20 pilot exists to answer.

---

## Current state (the authoritative summary)

**The validated edge** = `rebate(p)·sz` per fill, kept positive by toxicity-avoidance and delta-neutrality:
- **Deployed gate** (`live_trader.py --gate`): **`ufat`** — microprice toxicity gate with a p-adaptive
  margin (strict near p≈0.5 where adverse selection peaks, loose at the benign tails). Beat plain
  `micro_gate` by ~24% on 4 days of prospective data.
- **Best backtested combo** (`combo_lab.py`, in+out-of-sample): **`ufat_band`** = `ufat` **+ skip the toxic
  0.30–0.55 P(up) zone** (`--mid-skip`). ~2× OOS net/win vs `ufat` alone; running in the live A/B before
  it becomes the default.
- **Long-run gate**: **`micro_cal`** — a calibrated ensemble that keeps a fill iff `predicted_markout +
  rebate > 0`, so the toxicity threshold **auto-adapts to the real rebate** once it's confirmed.
- **Breadth, not stacking**: maker P&L is ~uncorrelated across assets (net corr +0.10) → ~1.75× Sharpe
  running 4 markets. Running several gate variants as separate books does **not** help (they're 0.7–0.9
  correlated). Size **BTC-heavy** (it's ~3× the other assets).

**Honest open items:** the rebate (A1) and live adverse selection (A2) can only be confirmed live; the
4-day backtest's OOS>IS is a favorable regime, not edge inflation; deploy changes only after live A/B.

---

## Run it (`run.sh`)

```bash
./run.sh paper [secs]     # READ-ONLY paper sim (no keys)
./run.sh preflight        # GO/NO-GO gate before any money (go_live.py — 9 checks)
./run.sh dryrun [secs]    # live plumbing on the box, places NOTHING
./run.sh pilot [secs]     # tiny live ($25 cap, $5 loss limit) — needs I_UNDERSTAND_REAL_MONEY=yes
./run.sh reconcile        # post-pilot: live vs paper as a t-stat (pilot_reconcile.py)
```
Full deploy path: **`GO_LIVE.md`**. The bot defaults to **DRY-RUN**; real orders require `--live` **and**
`I_UNDERSTAND_REAL_MONEY=yes`. Keys live only in a gitignored `.env` on your box — never in this repo.

## Architecture / key code

| File | Role |
|---|---|
| `shadow_compare.py` | the paper engine: runs all enabled strategy variants on the live book, scores per-window net + per-fill markout |
| `strategies.py` | **declarative strategy registry** — single source of truth; add/remove/prune a strategy here (`ADDING_STRATEGIES.md`) |
| `multi_market.py` | runs `shadow_compare` across BTC/ETH/SOL/XRP in parallel (breadth), supervised/auto-restart |
| `live_trader.py` | the deployable bot: WS book cache, post-only guard, dead-man switch, `--gate ufat`, `--mid-skip`, presign, kill-switches |
| `live_multi.py` | runs `live_trader` per market (live breadth) |
| `fvfeed.py` / `fairvalue.py` / `netfast.py` | spot feed, fair-value, latency-tuned HTTP session |
| `collateral.py` / `notify.py` | mint/merge (CTF) + Telegram alerts |

## Analysis tools

| File | Answers |
|---|---|
| `leaderboard.py` | rank all variants on prospective net (full + IS/OOS) |
| `gate_lab.py` | backtest toxicity gates on the fill tape → `gate_model.json` (the `micro_cal` model) |
| `combo_lab.py` | heavily backtest gate **combinations** IS+OOS → the best composite (`ufat_band`) |
| `insights.py` | regenerate the 10 data-backed insights (`INSIGHTS_4DAY.md`) |
| `breadth_net_corr.py` | cross-asset net correlation → real breadth Sharpe |
| `stack_analysis.py` | does portfolio-stacking help? (no — too correlated) |
| `aggregate_shadow.py` | rolling paper summary |
| `pilot_reconcile.py` | the live go/no-go after a pilot |

## GitHub structure

- **Branches:** `claude/polymarket-btc-backtest-XZkKI` (code/dev), `main` (fires the schedules), `gha-data`
  (collected data only — never pollutes code).
- **Workflows (3):** `paper-collect` (hourly, multi-asset, all enabled strategies → commits to `gha-data`),
  `strategy-fine`, `wallet-track`. Pull data for analysis:
  `git fetch origin gha-data && git checkout origin/gha-data -- gha_data/`.

---

## Documentation map

**Current / authoritative**
- `README.md` (this file) · `INSIGHTS_4DAY.md` (10 insights + best combo, the latest data) ·
  `GATING.md` (toxicity-gating rebuild) · `EDGE.md` (the 3-lever edge decomposition) ·
  `ADDING_STRATEGIES.md` (modular registry workflow)
- Go-live: `GO_LIVE.md` · `PAPER_VS_LIVE.md` (the gap map) · `DEPLOY.md` (free colo) ·
  `LATENCY.md` (sub-10ms) · `QUEUE_PRIORITY.md` (fill-first levers) · `CAPTURE.md` (logging schema)

**Historical / phase records** (kept for provenance; conclusions folded into the current docs above)
- Reverse-engineering phase (concluded: 95% wallet-clone not achievable): `MAKERS.md`,
  `REVERSE_ENGINEERING.md`, `COPY_PROTOCOL.md`, `CAPTURE_REALITY.md`, `STRATEGIES.md`, `WALLET_20d2.md`
- Earlier edge research (superseded by the gating validation): `FINDINGS.md`, `ROADMAP.md`, `INSIGHTS.md`,
  `MAKER_CHANGES.md`, `MAKER_CHANGES2.md`, `WINNER_TWEAKS.md`, `MAKEREDGE.md`, `QUEUE.md`, `INFRA_IDEAS.md`,
  `PAPER_TRADING.md`, `LIVE_DESIGN.md`, `PILOT.md`, `PRODUCTION_BLUEPRINT.md`, `BOXARB.md`, `WATCHER.md`

Each historical doc carries a one-line note at top pointing to its current successor. When old and new
disagree, **the current docs + the code win** (the project's discipline: data decides, OOS confirms).
