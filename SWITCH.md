# The live bot light switch

One control surface for live trading: the **`LIVE_SWITCH`** file (one word, `on` or `off`).
Flip it and the bot starts/stops — no Claude prompt, no commands to remember.

```
./live_switch.sh on        # start live trading (also clears a sticky loss-limit kill)
./live_switch.sh off       # stop
./live_switch.sh status    # show current state
```
…or just edit the `LIVE_SWITCH` file on GitHub (web UI) to `on`/`off` and commit. Same effect.

## What reads the switch

Two independent runners honor it, so the switch works whether or not a session is alive:

| runner | where | use it for |
|---|---|---|
| **`.github/workflows/live.yml`** | GitHub Actions (cloud) | **runs while you're away / out of usage.** Self-chains every ~46 min, cron re-checks every ~25 min. This is the always-on path. |
| **`live_supervisor.sh`** | a persistent VM you own | the durable home (an always-free Oracle Cloud us-east box). Same switch, pulls strategy changes each cycle, keeps the collector up. |

The **collector** (`paper-collect`/`collect_forever.sh`) and **continuity watcher**
(`watch_continuity.py`) run independently of this switch — data gathering never stops; the
switch only gates *live money*.

## Robust to frequent strategy changes
Both runners check out / `git pull` the branch every cycle, so when we change the strategy or
its defaults, the next live cycle picks it up automatically. The bot's flags live in one place
(the `kalshi_trader.py` argparse defaults + the single invocation line in each runner), so a
strategy change is a code change, not a switch change.

## Safety (unchanged from the attended bot)
- **Inert by default**: no secrets or `LIVE_SWITCH=off` ⇒ the cloud job does nothing.
- Same caps: `$5` max notional, **`$3` sticky loss-limit**, post-only, startup reconciliation,
  dead-man cancel-all, WS-book + cooldowns, `--max-net 1` strict pairing.
- **Sticky kill**: a loss-limit trip flips `LIVE_SWITCH` to `off` automatically and stops the
  chain. You re-arm deliberately with `./live_switch.sh on` (which clears the kill sentinel).
- **Security**: the cloud workflow triggers on schedule/dispatch only (never `pull_request`), so
  a fork PR can never reach the secret; the PEM is written 0600 and shredded after each run.

## One-time activation of the cloud (always-on) path
This is a deliberate real-money + secrets step — left to you:
1. Add two repo secrets (Settings → Secrets and variables → Actions):
   `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY` (the full RSA PEM; multiline is fine).
2. Move `.github/workflows/live.yml` onto the **default branch (main)** — schedules only fire
   from there. It stays inert until both secrets exist **and** `LIVE_SWITCH=on`.
3. `./live_switch.sh on`.

> The repo is public, so the cloud path runs live money from a public repo's Actions. That's
> acceptable *because* triggers exclude `pull_request` (forks can't get the secret), but if you'd
> rather not, the `live_supervisor.sh` + an always-free VM is the more conservative home and the
> standing recommendation for the long run. Either way the switch is identical.
