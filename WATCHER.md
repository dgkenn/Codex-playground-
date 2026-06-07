# WATCHER.md — keeping the paper collector running unattended

The dev container is reclaimed on idle and nothing inside survives it, so the collector and any
watcher must live on **GitHub Actions** (container-independent, free on this public repo). The hard
part is *triggering*: GitHub's `schedule` is **best-effort and drops runs** (we observed 1 run in
4 h on an hourly cron). So continuity is layered:

## The three layers
1. **`paper-collect.yml` — schedule `*/30`** (every 30 min). Each run collects ~45 min of the
   7-variant shadow comparison and **commits incrementally every ~10 min** (crash-safe; a killed
   runner costs ≤10 min). Unique files (`gha_data/shadow_windows_r<id>.jsonl`) never conflict.
2. **`paper-watchdog.yml` — schedule `15,45`** (independent, offset). It checks the age of the last
   `gha_data` commit and **only collects if data is stale (>45 min)** — filling gaps when
   paper-collect's cron is dropped, without double-collecting when healthy. Two independent
   schedules mean a single dropped cron no longer stalls collection.
3. **PAT self-chain (the GUARANTEED layer)** — if a repo secret **`DISPATCH_PAT`** exists, each
   `paper-collect` run re-dispatches the next via `workflow_dispatch`. PAT-triggered dispatches
   (unlike the built-in `GITHUB_TOKEN`) **do** start new runs, so the chain is continuous and
   **immune to the flaky scheduler**. Without the secret it logs a note and relies on layers 1–2.

## The ONE manual step for guaranteed unattended uptime  ← do this
Layers 1–2 are best-effort (GitHub can still drop both crons during an outage). To make it
**truly continuous**, add a Personal Access Token once:
1. GitHub → Settings → Developer settings → **Fine-grained PAT**: repo = `dgkenn/Codex-playground-`,
   permissions **Actions: Read and write** (+ Contents: Read). Copy the token.
2. Repo → Settings → Secrets and variables → Actions → **New repository secret**:
   name `DISPATCH_PAT`, value = the token.
3. Kick one run (Actions tab → paper-collect → **Run workflow**). From then on it self-chains
   continuously, no scheduler dependence.

## Health check (how to know it's alive)
- Actions tab: `paper-collect` / `paper-watchdog` runs should appear regularly.
- Or from the branch: `git log --oneline | grep -c "gha:"` should keep rising; newest
  `gha: paper-collect` / `WATCHDOG` commit timestamp = last collection.
- `python aggregate_shadow.py` → window count climbing across days (the power table in CAPTURE.md).

## What can still stop it (honest limits)
- A **GitHub-wide Actions outage** halts everything (rare; layers resume when it returns).
- **Free-tier minutes**: unlimited on a *public* repo (this one) — non-issue. If made private,
  ~2000 min/mo would cap continuous running.
- The collector is **paper** (READ-ONLY public WS + Coinbase spot, no keys). The live pilot
  (`live_trader.py --live`) runs on YOUR infra, not here.
