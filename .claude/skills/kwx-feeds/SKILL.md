---
name: kwx-feeds
description: Operate and debug the observation feed stack — Synoptic token/probe, MADIS, weather.gov cascade, detection-latency trial, per-station data quality. Use for "feed is stale", "synoptic token", "probe a station", "latency trial", "which feed is the bot using".
---

# Feed operations (the bot's eyes)

Detection latency IS the edge: the near-miss diagnosis showed the market reprices ~106 min
before an 8-min-late feed confirms a lock. Feed work is therefore first-class.

## The cascade

`kwx_runner._synoptic_primary()`: Synoptic 1-min HF-ASOS (token-gated) → MADIS (~10 min lag,
needs `numpy`/`scipy` for netCDF) → weather.gov/METAR consensus (~15-20 min). With no token the
free cascade runs alone. Every leg log's first line states the choice:
`feed cascade: synoptic-hf+fallback` vs the free name.

## Credentials (two kinds — this bit everyone)

- Synoptic **APIKEY** (account-level) mints **TOKENs** via `/v2/auth`. The data API accepts only
  tokens; an APIKEY used directly gets HTTP 401. Since 2026-07-20 `synoptic_feed.py`
  auto-exchanges on 401 (cached in-process), so either kind works everywhere.
- Local: one line in gitignored `.synoptic_token` (mode 600). NEVER commit it — public repo.
- Cloud: `SYNOPTIC_TOKEN` repo secret (Settings → Secrets → Actions), passed through by
  `kwx-live.yml` and `kwx-synoptic-trial.yml`.

## Verified commands

```bash
python synoptic_feed.py probe KDEN,KMIA        # live obs: n_obs, resolution, freshness per station
python synoptic_feed.py selftest               # offline parser tests
python kwx_runner.py usage 2>/dev/null | head -1   # which cascade the runner would boot HERE
python wx_synoptic_trial.py --minutes 4 --interval 45   # one bounded live race sample run
python wx_synoptic_trial.py --report           # accrued detection-lead evidence (the $900/mo decision)
./.claude/skills/run-kwx/driver.sh feed
```

## Gotchas (hit for real)

- **Per-station resolution varies wildly**: KMIA returns true 5-min data, KDEN only hourly METAR
  through the same endpoint. Probe before assuming 1-min anywhere; the paid feed's value is
  per-station, and the trial quantifies exactly that.
- **IEM `asos1min.py` publishes 22-34 HOURS late** — gold for backtests, useless live. Never mix
  it into a live-timing argument.
- **Free-feed STALE warnings** in the digest are normal at ±8-20 min; alarm only if all stations
  stale >1h.
- The trial's paired lag samples only accrue during US-afternoon fire windows (cron 18-23 UTC)
  when running maxes are actually crossing — a quiet morning run produces 0 samples and that's
  expected, not broken.
- The pay/don't-pay decision bar: `--report` needs enough paired samples to state a median
  detection lead; decide at trial day 14, per `PATH_TO_4K.md` Stage 4's Synoptic decision point.
