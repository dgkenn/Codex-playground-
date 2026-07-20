---
name: run-kwx
description: Run, smoke-test, or check the K-WX Kalshi weather bot — status, stage/gate, capacity model, feed cascade, daily digest, study reproduction. Use for "run the bot", "is the bot healthy", "check status", "smoke test", "which feed is live".
---

# Run / smoke the K-WX bot

The bot itself is a cron fleet on GitHub Actions (`kwx-live.yml` on `main`, self-chaining ~16-min
legs, code checked out from `claude/coding-bot-ab-test-results-ffmhxw`). You do not "start" it
locally — you *verify* it and *drive its operator surface* with the committed driver. All driver
subcommands are read-only/paper-safe. Paths relative to repo root.

## Prerequisites

Python 3 stdlib only for the driver paths. (`numpy`/`scipy` are only needed by the MADIS netCDF
feed inside real legs; the driver's probes don't require them.)

## Agent path (primary)

```bash
./.claude/skills/run-kwx/driver.sh smoke     # full health pass: selftest, goal status, feed, studies, model tail
./.claude/skills/run-kwx/driver.sh status    # CURRENT STAGE / NEXT GATE / BLOCKING ON one-pager
./.claude/skills/run-kwx/driver.sh model     # capacity model, all scenario tables
./.claude/skills/run-kwx/driver.sh feed      # feed-cascade provenance + live Synoptic probe
./.claude/skills/run-kwx/driver.sh digest    # compose the daily digest text (no send)
./.claude/skills/run-kwx/driver.sh trial     # Synoptic detection-latency trial evidence so far
./.claude/skills/run-kwx/driver.sh studies   # reproduce every committed study verdict from its data
```

`smoke` exits non-zero if anything fails, including the local-log-pollution check (see Gotchas).

## Checking the LIVE fleet (cloud)

- Latest leg commits land on the code branch as `kwx-live <UTC>` commits touching
  `.kwx_heartbeat` / `kwx_gate_status.txt`: `git log --oneline -5` after a pull.
- Each leg's Actions log starts with `feed cascade: <name>` — `synoptic-hf+fallback` means the
  `SYNOPTIC_TOKEN` repo secret reached the runner; a free-cascade name means it didn't.
- Kill switch: `KWX_SWITCH` file (`on`/`off`) + `.kwx_halt` presence. Never flip these casually —
  they gate real orders.

## Human path

There is no meaningful local "run": `python kwx_runner.py once` does one paper poll cycle
(prints the feed line first), `loop` runs it continuously. LIVE requires `KWX_LIVE=1` + Kalshi
creds and should only ever happen inside the Actions legs.

## Gotchas (all hit for real)

- **Local runs pollute bot-owned logs.** `kwx_selftest.py` (and any local poll) appends test rows
  (ticker pattern `*_T90_0`) to `kwx_near_miss.jsonl`. NEVER commit those — they corrupt the
  near-miss measurement dataset. `git checkout -- kwx_near_miss.jsonl` after local runs; the
  smoke driver warns automatically.
- **The Actions bot pushes constantly** (leg commits every ~16-20 min). Plain `git push` will be
  rejected mid-day; use pull --rebase, and stash/pop around it — but see next bullet.
- **Stale-stash landmine.** `git stash pop` after the rebase can resurrect ancient WIP stashes
  (one from branch `botcode` holds an obsolete `kwx_runner.py` and will conflict). If a pop
  conflicts on a file you didn't edit: `git checkout HEAD -- <file>` and leave the stash alone.
- **`.synoptic_token` is gitignored on purpose** — public repo; the credential must never be
  committed. Cloud legs get it via the `SYNOPTIC_TOKEN` repo secret instead.
- **Synoptic 401 with a valid-looking credential** = you have the account APIKEY, not a data
  token. `synoptic_feed.py` auto-exchanges it via `/v2/auth` since 2026-07-20; both kinds work.
- **KDEN (and some stations) return sparse hourly obs via Synoptic** while KMIA returns true
  5-min data — per-station resolution differs; check `synoptic_feed.py probe <stations>` before
  assuming 1-min everywhere.

## Troubleshooting

- `feeds: STALE at <station>` in the digest → free feeds lag 8-20 min; only worrying if ALL
  stations stale for >1h (then check the latest kwx-live Actions run for red).
- `no paired lag samples yet` from `trial` → the Synoptic-vs-free race only accrues during
  US-afternoon fire windows (cron 18-23 UTC); wait for those hours.
- Push rejected with `HTTP 403 ... fetch first` → the bot committed between your pull and push;
  redo `git pull --rebase origin <branch>` then push.
