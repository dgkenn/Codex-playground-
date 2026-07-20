---
name: kwx-incident
description: Diagnose and fix live K-WX fleet incidents — leg outages, workflow chain breaks, halt states, git conflicts with the bot, log pollution, stale feeds. Use for "bot is down", "no legs running", "workflow failed", "halt", "push rejected", "logs look wrong".
---

# Incident runbook (things that have actually broken)

Work from evidence, not pattern-matching: every incident below was real, and two of them
silently cost coverage for hours. Check state FIRST, then act.

## Triage order (verified commands)

```bash
python kwx_goal_status.py                      # halted? near-miss rate normal?
git log --oneline -8                           # leg commits every ~16-20 min = fleet alive
ls .kwx_halt 2>/dev/null && echo HALTED        # hard-halt state
cat KWX_SWITCH 2>/dev/null                     # on/off
./.claude/skills/run-kwx/driver.sh smoke
```
Then the Actions view: latest `kwx-live` runs (look for red), and each leg log's first line
(`feed cascade: ...`) for feed provenance.

## Known incident classes

1. **Leg-chain outage (THE big one).** 2026-07-18: switch ON but the self-chaining workflow
   never looped — 20h39m with zero coverage, silently. Symptom: no `kwx-live <UTC>` commits for
   >25 min while the switch is on. The watchdog workflow + `*/20` backup cron now exist as belt
   and braces; if commits stop anyway, dispatch `kwx-live` manually from the Actions UI and read
   the failed run's log. 62% of all logged near-misses trace to that one outage — coverage gaps
   corrupt downstream statistics, so after any outage, annotate the gap window in the incident
   notes before anyone reads rates across it.
2. **Push rejected (`HTTP 403 ... fetch first`).** The bot commits constantly; your push raced
   it. `git pull --rebase origin <branch>` then push. If a stash pop then conflicts on a file
   you never edited (ancient `botcode` WIP stash holds an obsolete `kwx_runner.py`):
   `git checkout HEAD -- <file>`, leave the stash alone.
3. **Local log pollution.** Local selftests/polls append test tickers (`*_T90_0`) to
   `kwx_near_miss.jsonl`. Discard with `git checkout -- kwx_near_miss.jsonl`; never commit.
4. **Feed regression.** Leg log says free cascade when Synoptic should be armed → the
   `SYNOPTIC_TOKEN` secret is missing/expired (Settings → Secrets → Actions). 401s despite a
   credential → APIKEY-vs-token confusion; `synoptic_feed.py` auto-exchanges since 2026-07-20,
   so update the code branch if a leg predates that.
5. **Halt (`.kwx_halt` present).** Created by kill criteria (win LB <97%, day drawdown >20%).
   Do NOT delete it to "get going again" — diagnose against `PATH_TO_4K.md`'s stage-table kill
   rows first; removal is an operator decision with the diagnosis written down.
6. **Disk-full in work sessions** (`no space left on device` during git ops): orphaned
   `tmp_pack_*` files from interrupted fetches accumulate under `.git/objects/pack/` — delete
   them (they're transfer debris, not repo data); 30GB has been recovered this way twice.

## After any incident

Re-run `./.claude/skills/run-kwx/driver.sh smoke`, confirm leg commits resumed, and note the
outage window + cause in the PR/commit that fixes it — future statistics need the annotation.
