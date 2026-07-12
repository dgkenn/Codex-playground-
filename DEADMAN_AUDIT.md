# DEAD-MAN AUDIT: runner death while the bot holds inventory

Read-only trace of one failure path: **the GitHub Actions runner executing `live.yml` dies
mid-window (SIGKILL / OOM / infra force-terminate / spot preemption / GH schedules an
un-graceful stop) while `kalshi_trader.py` holds open orders and/or filled inventory.**
No code was changed to produce this document. Sources: `.github/workflows/live.yml` (main),
`kalshi_trader.py` (live-ready branch, read-only), `live_switch.sh`, `SWITCH.md`, `CLAUDE.md`.

Key distinction used throughout: `kalshi_trader.py` has excellent handling for **graceful**
termination (SIGTERM/SIGINT/SIGHUP, `atexit`, planned duration end, internal kill triggers) via
`_flatten_and_exit()` (kalshi_trader.py:1030-1062) registered on `atexit` (line 1089) and on
`SIGTERM`/`SIGINT`/`SIGHUP` (lines 1092-1099), plus the workflow's own
`timeout --signal=TERM --kill-after=60 2820` wrapper (live.yml:102). None of that machinery runs
on a **hard kill** (SIGKILL, OOM-killer, or GitHub Actions force-terminating the whole job/runner)
— Python cannot intercept SIGKILL, and a runner that simply disappears never executes any
remaining workflow steps either. That gap is the subject of this audit.

## (a) What happens to open (unfilled resting) orders?

Every order the trader places carries a **venue-side TTL**: `place_order(..., ttl_s=a.order_ttl_s)`
sets `expiration_ts = now + order_ttl_s` (kalshi_trader.py:423-442), and `--order-ttl-s` defaults to
**150 seconds** (kalshi_trader.py:746-749, live.yml:105 does not override it). This is Kalshi's
own venue-side dead-man: it does **not** depend on the process being alive. So:

- Resting orders are **not** GTC and do **not** rest forever. Each self-expires venue-side within
  150s of **its own placement time** (not 150s from the moment the runner dies).
- Because quotes are continuously reshaped during normal operation (`--requote-stale-s 20`,
  reshape-on-microstructure-change, etc.), in practice any order resting at the instant of death is
  usually much younger than 150s, so real exposure to a "phantom resting order" is bounded to well
  under ~150s in the typical case, and hard-bounded at 150s in the worst case.
- This is a genuinely solid rail: it is the one piece of the dead-man design that provably survives
  SIGKILL, because it lives entirely on the venue, not in the process.

**Verdict: (a) is well covered.** Post-only-only + a 150s venue TTL means orphaned *unfilled*
orders cannot rest indefinitely.

## (b) What happens to already-held (filled) positions until the next cron leg?

Filled inventory has **no venue-side analog to order TTL** — Kalshi does not auto-flatten held
contracts. The only mechanism that manages held inventory (pairing completion, `--dispose-cross`,
`--chase-unpaired-s`, `--close-force-s` forced-flatten in the closing seconds, and the loss-limit /
markout kills) is **all in-process, active-loop logic**. If the process is dead, none of it runs.

What actually resolves the position is Kalshi's own settlement clock, independent of the bot:

- **Paired inventory** (`min(YES,NO)` contracts, the box) is risk-free regardless: it pays $1/pair
  at settlement no matter what happens to the bot.
- **Unpaired/naked inventory** (a stranded single leg) rides completely unmanaged from the moment
  of death until the window's close (`KX*15M` windows are 15 minutes), because the disposal logic
  (`--dispose-cross`, `--close-force-s 45`, `--chase-unpaired-s 15` in live.yml:105) that would
  normally try to cheaply complete or force-flatten that leg near expiry never runs. Worst case:
  a leg struck at minute 0 of a window dies immediately after and rides naked for up to ~15 minutes
  with **zero** of the loss-mitigation logic the live invocation was specifically tuned to apply
  (live.yml:105's flags exist *because* naked legs are the documented loss source —
  `LIVE_POSTMORTEM.md` / `BOX_COMPLETION_EXEC.md` — and none of them fire during this gap).
- Exposure per window is bounded by `--max-notional 5` / `--post 1` / `--max-rungs 1`, so the
  dollar amount at risk in any single stranded leg is small (~$1-5) given the current $50-account,
  $5-cap deployment — but the *mechanism* that is supposed to bound it (active disposal) is exactly
  what's absent.

**Worst-case gap before *any* new trading activity resumes:** live.yml's continuity is
self-chain-primary / cron-backstop. The cron ticks at `3,28,53 * * * *` — every 25 minutes — and is
explicitly documented elsewhere in this repo (`collect.yml`'s header comment) as observed to *shed
ticks under load*, i.e. 25 minutes is the intended worst case, not a hard guarantee. Because the
self-chain step is itself a step in the same job that just died, a runner death **always** falls
back to the cron backstop — worst observed-design gap ≈ 25 minutes (longer if GitHub sheds a tick).
Note this gap does not extend the naked leg's own risk window (that's capped by the 15-minute
market close regardless of the bot's state); it only delays when the bot resumes *actively trading
new windows*.

## (c) Does the restarted run flatten or re-adopt inventory? Can state double-count?

**Neither.** Concretely:

1. **No flatten-on-startup.** Startup reconciliation (kalshi_trader.py:853-915, "C7") only cancels
   **open orders** for the newly-discovered ticker (`get_open_orders` + `cancel_order`). It never
   calls a positions endpoint and never crosses to flatten anything. `kalshi_trader.py` never calls
   `GET /portfolio/positions` anywhere in the file (confirmed by search) — the trader has no way to
   learn about pre-existing venue inventory at startup at all.
2. **No re-adoption, even in the lucky case where the new process picks up the very same still-open
   ticker.** `poll_fills()`'s first call for any ticker runs the "C-4" seeding branch
   (kalshi_trader.py:1322-1329): *"on first call for a ticker, seed all existing fill ids without
   booking them"* — i.e. any fills already sitting on that ticker (including ones left by a process
   that just died) are marked `seen` and **silently discarded**, never added to `pos`, `cash`, or
   `net_delta`. The new process's in-memory ledger (`net_delta = 0.0`, `pos = {}`, `realized = 0.0`,
   all initialized around kalshi_trader.py:932-940) starts **flat by construction**, whether or not
   the venue is actually flat.
3. **Double-count / blind-spot risk.** In the scenario where the new session's `discover()`
   (kalshi_trader.py:311-332) happens to land on the *same* ticker as the dead session (plausible if
   the death and the cron restart both fall inside one still-open 15-minute window), the new process
   believes `net_delta == 0` while the venue may actually hold real inventory. Every downstream
   safety rail that depends on `net_delta` — the strict box-pairing clamp (`--max-net 1`), the
   loss-limit worst-open calculation (kalshi_trader.py:~1528-1536), the markout kill — is evaluated
   against the **wrong** (understated) inventory. The bot could then place *additional* same-side
   exposure believing it is opening a fresh box, pushing true venue-side net exposure beyond the
   intended `|net|<=1` cap. This is not literal double-counting of dollars (Kalshi's own ledger is
   never wrong), but it is a real **risk-clamp blind spot**: the software's model of "what we hold"
   can diverge from "what we actually hold" indefinitely, with nothing to reconcile the two. This is
   precisely the gap `equity_snap.py` (Task 1) is designed to catch independently, since
   `kalshi_trader.py`'s own `realized` ledger has no cross-check against the venue's true balance.
4. In the far more common case (new ticker, prior window already closed), the stranded leg simply
   settles per Kalshi's normal clock, credited straight to account balance — invisible to the bot's
   own P&L variables (which reset every session) but visible in the account balance
   `equity_snap.py` now snapshots daily.

## (d) Does the STICKY loss-limit kill survive a runner death?

**No, not reliably.** The kill sentinel `.kalshi_killed_{asset}15m` is explicitly **gitignored /
never staged** (`live_switch.sh`: *"sentinel is gitignored; never staged"*) — it is a plain file on
the ephemeral runner's local disk, nothing more, until something durable happens to it. The only
durable enforcement is the **"persist telemetry + sticky-kill"** step in live.yml (lines 112-149),
which:

1. Checks `if [ -f ".kalshi_killed_${ASSET}15m" ]` on the *same runner* right after the trade step
   ends, and if present, writes `LIVE_SWITCH=off` and commits+pushes it to `$BRANCH` (with retries).
2. This is the **only** place the kill becomes durable. If the runner is hard-killed anywhere
   between `_record_kill()` writing the local sentinel (kalshi_trader.py:817-822, called
   synchronously before `_flatten_and_exit`) and this step's `git push` succeeding — e.g. the whole
   job/runner is OOM-killed, the workflow is forcibly cancelled, GitHub infra reaps it, or the push
   retries all fail — **the sticky kill is entirely lost**. Nothing durable records that a
   loss-limit / toxic-markout / error-storm kill just fired.
3. The next run (self-chain dispatch, which itself requires the *prior* run to have finished
   normally and thus can't fire in this dead-runner scenario — so realistically the **cron
   backstop**) does a **fresh checkout** of `$BRANCH`. That checkout can never contain the sentinel
   file (it was never tracked in git to begin with), and `LIVE_SWITCH` is still whatever it was
   before the kill (i.e. `on`, since the flip never got committed). Result: **the bot resumes live
   trading with the switch on, unaware that a kill condition was just triggered**, defeating the
   entire purpose of "sticky."
4. As a secondary observation: the "gate on the switch" step at the *start* of every run
   (`[ -f ".kalshi_killed_${ASSET}15m" ] && sw=off`, live.yml:55) can never actually fire true on a
   fresh GHA checkout, since that file is never committed — it's effectively dead code on this
   runner (it would only matter on a persistent filesystem, e.g. `live_supervisor.sh` on a VM). The
   **real** enforcement is 100% dependent on the `LIVE_SWITCH=off` commit succeeding within the same
   job invocation that detected the kill.

## Severity-ranked gap list

1. **[HIGH] Sticky-kill is not durable across a hard runner death (answers (d)).** A loss-limit /
   toxic-markout / error-storm trip is recorded only on local (ephemeral, gitignored) disk; it
   becomes permanent only if the same job's later step completes a `git push`. A runner death
   between those two points silently discards the kill and the bot resumes trading on the next
   cron tick as if nothing happened — the one rail explicitly designed to require deliberate
   operator re-arm can be bypassed by the exact failure mode (a dying runner) this audit targets.

2. **[HIGH] No inventory reconciliation on startup — the bot cannot detect it is not actually flat
   (answers (c)).** `kalshi_trader.py` never calls `GET /portfolio/positions`. Startup
   reconciliation cancels stale *orders* only. Combined with the C-4 fill-seeding logic that
   discards pre-existing fills on a ticker's first poll, a restarted process always assumes
   `net_delta == 0` regardless of venue truth. In the (lower-probability but real) case where a
   restart lands on the same still-open ticker as the dead session, this can let the bot add
   exposure on top of unknown existing inventory, silently breaching the intended `|net|<=1`
   pairing discipline.

3. **[MEDIUM] Naked/unpaired legs get zero active disposal management for the remainder of their
   window if the runner dies while holding one (answers (b)).** The specific flags live.yml passes
   (`--dispose-cross`, `--close-force-s 45`, `--chase-unpaired-s 15`) exist precisely because
   untreated naked legs are the documented historical loss source; none of them can fire once the
   process is gone. Bounded in dollars by `--max-notional 5`, but the mitigating mechanism is fully
   absent for up to ~15 minutes per incident.

4. **[MEDIUM] No independent ground-truth accounting existed before Task 1 of this work
   (contributing factor to #1 and #2).** Prior to `equity_snap.py`, nothing outside
   `kalshi_trader.py`'s own in-memory ledger checked the venue's real balance/positions, so a
   silent drift from any of the above gaps could go unnoticed indefinitely between manual checks.
   (Mitigated by this delivery, not eliminated — see recommendations.)

5. **[LOW] Self-chain continuity has a soft dependency on GitHub Actions schedule reliability.**
   The self-chain is the primary continuity mechanism; a dead runner always falls back to the
   25-minute cron backstop, which this repo's own `collect.yml` documents as observed to shed ticks
   under load. Low severity because it only delays *new* trading, not resolution of existing
   inventory (that's gated by Kalshi's own settlement clock, not the cron).

6. **[LOW] `SWITCH.md` documents a `$3` sticky loss-limit; the code default is `$6`
   (`--loss-limit` default and live.yml's explicit `--loss-limit 6`).** Not a dead-man gap per se,
   but stale documentation that could mislead an operator's mental model of the actual risk cap
   during an incident review.

## Fix recommendations (not implemented — read-only audit)

- **For #1 (sticky-kill durability):** write the kill sentinel to a location that becomes durable
  independently of a later step succeeding — e.g. commit-and-push the `LIVE_SWITCH=off` flip (or a
  dedicated kill marker) as the *very next action* immediately after `_record_kill()`, inside
  `kalshi_trader.py` itself (it already has `GH_TOKEN`/`REMOTE_SWITCH_URL` context available) rather
  than deferring it to a separate workflow step that a dead runner can skip entirely. A belt-and-
  suspenders option: have `equity_snap.py` (or a dedicated cheap watchdog) independently compare
  today's balance delta against expectations and flip `LIVE_SWITCH` off itself if it detects a loss
  beyond the configured limit, so enforcement doesn't depend on the trade job at all.
- **For #2 (no startup reconciliation of positions):** add a `GET /portfolio/positions` call at
  startup (read-only, same auth) and either (a) refuse to start if any non-zero position exists on
  the series until an operator confirms/clears it (fail-closed, mirrors the existing order
  reconciliation's fail-closed posture), or (b) explicitly re-adopt the position into `pos`/
  `net_delta` so the running session's risk clamps see true inventory from second one.
  `equity_snap.py`'s daily snapshot is a detective control for this gap, not a preventive one —
  worth considering a cheap pre-trade positions check inside `kalshi_preflight.py` too.
- **For #3 (unmanaged naked legs during downtime):** consider a lightweight, separate watchdog
  workflow (independent of the trading job) that, on a short interval, checks for any non-zero
  position on the live series and — if the trading job is not currently `in_progress`/`queued` —
  force-flattens it via a minimal, read-mostly script with a narrowly-scoped ability to cross only
  to flatten (not to open new risk). This is a new, carefully-scoped component, not a change to
  `kalshi_trader.py`.
- **For #4:** now delivered — keep `equity_snap.py`'s daily snapshot running, and consider adding a
  same-day alert if the balance delta diverges materially from the sum of `kalshi_winrec_*.jsonl`'s
  reported `realized` across sessions on the live-state branch, which would surface exactly the
  drift described in gap #2 without needing a code change to the trader.
- **For #5:** no change recommended at current account size; if capital scales up, consider adding
  a second, differently-timed cron backstop and/or an external heartbeat monitor (the pattern
  `collect.yml` already uses via `HEARTBEAT_URL`) on `live.yml` specifically.
- **For #6:** update `SWITCH.md`'s stated loss-limit to match the code (`$6`) — a pure documentation
  fix, no code risk.

## Fixes implemented

Both HIGH-severity gaps (#1, #2) are now fixed in `kalshi_trader.py`. #3/#4/#5/#6 remain as
documented above (out of scope for this change; #4 was already delivered separately via
`equity_snap.py`).

### Fix #1 — durable sticky-kill (`kalshi_trader.py`)

Added `remote_switch_kill(gh_token, remote_switch_url, reason, sess=..., retries=3,
backoff_s=1.5, alert_fn=...)` as a module-level function (testable independent of `main()`).
`_record_kill()` — the closure both the loss-limit kill and the toxic-markout kill already called
— now calls it immediately after writing the local sentinel, at the moment the kill fires, rather
than deferring durability to a later `live.yml` workflow step that a hard-killed runner never
reaches:

1. GETs the current `LIVE_SWITCH` file via the GitHub contents API (reusing the exact
   `REMOTE_SWITCH_URL` + `GH_TOKEN` the process already receives — no new config surface) to
   obtain the file's current `sha`, then PUTs `off` (base64-encoded) back with that `sha`, setting
   `branch` from the url's `?ref=` query parameter.
2. Retries 3x with exponential backoff (re-fetching `sha` on every attempt, since a stale `sha`
   from a prior attempt would 409).
3. On total failure, falls back to the pre-existing sentinel + workflow-step path (unchanged) and
   fires a Telegram alert (`notify.alert_sync`) flagging that the kill may not survive a runner
   death, so an operator is not silently unaware.
4. Clean no-op (zero network calls, returns `False`) when `GH_TOKEN` or `REMOTE_SWITCH_URL` is
   absent, or the url isn't `api.github.com` — local/dry runs are unaffected.

Unit-tested in `kalshi_safeguards_test.py` as **T11** (8 sub-cases: no-token no-op, no-url no-op,
non-GitHub-host no-op, first-attempt success with sha/branch/content verification, retry-then-
success, total-failure-triggers-alert, and a GET-with-no-sha guard that never PUTs blind).

### Fix #2 — startup venue-position reconciliation (`kalshi_trader.py`)

Added `get_positions(sess, private_key)` (GET `/trade-api/v2/portfolio/positions`, following the
same `_api()`/error-handling pattern as the existing `get_open_orders`/`get_fills`/`get_balance`)
and `_parse_inherited_position(mpos_list, ticker)` (pure, defensive parser: filters to the active
ticker, maps Kalshi's signed `position` field to this file's own `side`/`net_delta` sign
convention — positive = long YES — and best-effort seeds a cost basis from `market_exposure`
cents so it under-, never over-, estimates the C2 loss-limit's worst-open calc on inherited
inventory).

Wired into `main()`, live mode only, immediately after the existing (fail-closed) startup order
reconciliation:

1. Queries positions and Telegram-alerts (`notify.alert`) immediately if the active ticker has
   nonzero inherited inventory, independent of whether this session ever actually attaches to
   that ticker's window.
2. The state-init block seeds `net_delta`/`pos`/`win_cost` from the inherited position exactly
   once, the first time this session attaches to a window — and only if that window's ticker
   still matches the one the startup query was filtered to (a narrow race — the window rolling
   between the startup query and loop entry — is handled by skipping the seed rather than
   misattributing inventory to the wrong ticker). Once seeded, every existing risk clamp
   (`--max-net`, the C2 loss-limit worst-open calc) and disposal mechanism (`--dispose-cross`,
   `--chase-unpaired-s`, `--close-force-s`) treats it exactly like a position opened this session
   — no separate handling needed, per the audit's recommendation (b).
3. Defensive throughout: any exception during the positions query/parse logs and safe-defaults to
   the pre-fix behavior (assume flat) rather than blocking startup, unlike the fail-closed order
   reconciliation it sits next to.

Unit-tested in `kalshi_safeguards_test.py` as **T12** (12 sub-cases): `get_positions` driven
end-to-end through a mocked session (including a 5xx safe-default-to-`[]` case), `_parse_
inherited_position` against long-YES/long-NO/flat/ticker-absent/malformed-row/`None`-input
payloads, and a replica of the "seed exactly once, ticker-matched" rollover logic covering the
seed-applied, ticker-mismatch-skips, exactly-once, and flat-venue-still-marks-consumed cases.
