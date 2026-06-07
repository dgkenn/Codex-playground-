# WATCHER.md — keeping the paper collector running unattended

The dev container is reclaimed on idle and nothing inside survives it, so the collector and any
watcher must live on **GitHub Actions** (container-independent, free on this public repo). The hard
part is *triggering*: GitHub's `schedule` is **best-effort and drops runs** (we observed 1 run in
4 h on a 30-min cron, because repeated workflow edits kept resetting the scheduled-workflow
activation delay). So continuity does **not** rely on the scheduler — it self-perpetuates.

## Layer 0 — the `workflow_run` ping-pong chain (PRIMARY, **VERIFIED 2026-06-07**)
Two workflows bounce off each other's completion, so the loop drives itself with **no scheduler and
no PAT**:
- `paper-collect.yml` collects ~45 min, commits data, and **on completion triggers**
  `paper-collect-chain.yml` (`on: workflow_run: workflows:["paper-collect"] types:[completed]`).
- `paper-collect-chain.yml` is a ~10 s no-op bouncer whose **completion triggers** `paper-collect`
  again (`on: workflow_run: workflows:["paper-collect-chain"] types:[completed]`).
- The bouncer exists only because a workflow **cannot** trigger on its own completion; you need a
  second workflow to bounce off. `workflow_run` → `workflow_run` is **not** recursion-blocked
  (that block only applies to `GITHUB_TOKEN`-initiated `push`/`dispatch` events).

**Verified end-to-end** (run ids on `main`): run #2 `paper-collect` completed 18:47:41Z →
`paper-collect-chain` #1 fired via `workflow_run` (18:47:43→18:47:53Z) → `paper-collect` **#3**
fired via `workflow_run` at 18:47:55Z — fully autonomous, immediately, zero manual action, no PAT.
This is the continuous driver; the layers below are redundancy.

## Layer 1 — schedule `*/30` (backup seed)
`paper-collect` also has `schedule: */30`. If the chain ever breaks (e.g. a run is cancelled before
it can trigger the bouncer, or an Actions outage interrupts the ping-pong), the cron re-seeds a new
run, which restarts the chain. Best-effort, but only needs to fire *once* to relight Layer 0.

## Layer 2 — `paper-watchdog.yml` schedule `15,45` (independent self-heal)
A separate workflow on an offset cron checks the age of the last `gha_data` commit and **only
collects if data is stale (>45 min)** — filling gaps without double-collecting when healthy. Two
independent schedules + the chain mean no single dropped trigger stalls collection.

## Layer 3 — PAT self-chain (optional; chain already works without it)
If a repo secret **`DISPATCH_PAT`** exists, each `paper-collect` run also re-dispatches the next via
`workflow_dispatch` (PAT dispatches start runs; the built-in `GITHUB_TOKEN` ones don't). Now that
Layer 0 is verified self-perpetuating, this is **redundant insurance**, not required.

## Layer 4 — HEARTBEAT (observability + the only total-outage alert)
The chain/schedule/watchdog all run *inside* Actions, so none can report their own death (a
GitHub-wide outage takes the watchers down with the collector). The heartbeat fixes that:
- **Local liveness:** each run writes `gha_data/HEARTBEAT_<tag>.json` (utc, settled_windows, cum),
  committed by the incremental loop. At-a-glance "alive / when last": that file or
  `git log -1 -- gha_data/`.
- **External dead-man's-switch:** if repo secret **`HEARTBEAT_URL`** is set, every run pings it
  (~90 s). Point it at a free **healthchecks.io** check expecting a ping every ~30–60 min; if pings
  STOP it emails/texts you. Living OUTSIDE GitHub, it's the ONLY layer that catches a total Actions
  outage. No-op until the secret is set (local heartbeat still works).

## How to (re)start it from zero
Push any commit to **`main`** (a `push: branches:[main]` trigger seeds `paper-collect` immediately —
no activation delay), or Actions tab → paper-collect → Run workflow. The chain takes over from there.

## Health check — `python watch_continuity.py`
Git-based (reads the committed data trail; no API/rate-limit dependency, runs from any clone):
- `python watch_continuity.py` → last `gha_data` commit age + staleness warning + whether an
  autonomous run beyond the seed has appeared.
- `python watch_continuity.py --probe` → loops, exits 0 once a new autonomous run commits data.
- `python aggregate_shadow.py` → window count climbing across days (the power table in CAPTURE.md).

## What can still stop it (honest limits)
- A **GitHub-wide Actions outage** halts everything (rare; Layer 0 relights via Layer 1 when it
  returns, and Layer 4's external ping alerts you meanwhile).
- **Free-tier minutes**: unlimited on a *public* repo (this one). If made private, ~2000 min/mo caps it.
- The collector is **paper** (READ-ONLY public WS + Coinbase spot, no keys). The live pilot
  (`live_trader.py --live`) runs on YOUR infra, not here.

## Optional secrets, ranked
1. **`HEARTBEAT_URL`** (do this) — get ALERTED if collection ever stops, even in a GitHub outage.
2. **`DISPATCH_PAT`** (optional) — redundant now that the `workflow_run` chain is verified, but adds
   a scheduler-independent dispatch path as extra insurance.
