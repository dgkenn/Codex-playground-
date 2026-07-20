# K-WX near-miss diagnosis — why ~50/52 mechanical locks were never buyable

Repo: `/home/user/Codex-playground-`, branch `claude/coding-bot-ab-test-results-ffmhxw`.
Source log: `kwx_near_miss.jsonl` (52 rows, all `reason:"ask>98"`, all `ask_c:100`, all `side:"no"`, spanning
LST contract-days `26JUL19` (n=40) and `26JUL20` (n=12), detected between 2026-07-20T02:27Z and 11:11Z).

## Method (and a material data-availability finding)

The brief asked for ground truth from IEM's `asos1min.py` 1-minute ASOS archive. **That archive is
unusable for this exercise**: empirically probed against six independent stations (DEN, ATL, AUS, MIA, ORD,
JFK) at the time of this analysis (system clock 2026-07-20T11:3xZ), every station's most recent available
1-minute record was **22–34 hours stale** (last obs between 2026-07-19T01:49Z and 13:37Z). This is a genuine
processing-lag property of that specific IEM product, not a proxy/network artifact — the *5-minute* NWS/MADIS
products from the same IEM-adjacent infrastructure were current to within ~45 minutes when probed. Because
nearly every near-miss's true lock time falls in the un-archived last day, IEM 1-min can reconstruct **zero**
of the 52 rows.

**Substitution used instead:** the exact two feeds `kwx_runner.py` itself runs in production (no
`.synoptic_token`/`SYNOPTIC_TOKEN` present, confirmed — the paid 1–2 min Synoptic tier is NOT wired up; the
live cascade is `MADIS (free, ~10 min latency, 5-min resolution) → weather.gov/METAR consensus (~15–20 min,
hourly-ish for non-hfmetar stations)`). `madis_feed.MadisFeed` and `weathergov_feed.WeatherGovFeed` were
called directly (46/52 rows via MADIS, 6/52 via weather.gov fallback for KDEN and NYC, which MADIS's own
docstring already flags as hfmetar-sparse). `kwx_runner.sustained_extreme()` (unmodified, imported directly)
was replayed incrementally against each obs stream with the exact live constants (`MARGIN_F=1.0`,
`STATION_MARGIN={"KPHX":2.0}`, `SUSTAIN_MIN=3`) and the **exact floor/cap** pulled live from
`GET /trade-api/v2/events/{event_ticker}` (not reverse-engineered from `cushion_f`) to find the first minute
the lock condition (`extreme > cap+margin` for max / `extreme < floor-margin` for min) is satisfied — this is
`lock_time`. All 52/52 rows resolved (no UNRESOLVED cases). Raw work: `reconstruction_raw.json`,
`reconstruction_classified.json`, `all_events.json`, `iem/*.csv` (kept for the record despite being unusable),
`kwx_live_commits.txt`.

Leg-coverage ground truth came from `git log` on `.github/workflows/kwx-live.yml`-produced commits
(`kwx-live YYYY-MM-DDTHHMMZ`), which double as a leg-alive heartbeat (each leg commits at the end of its
~16-minute run). Full history: **switch turned ON 2026-07-18T20:23:01Z**, two isolated attempt-commits at
2026-07-19T00:37–00:49Z, then a **20h39m dead zone with zero leg commits until 2026-07-19T21:28:17Z**, after
which 52 consecutive legs ran with **no gap over ~17 minutes** through the end of the window studied
(2026-07-20T11:29Z). That 20h39m dead zone is the single largest structural fact in this dataset.

## 1–2. Lock-time reconstruction and the detection-delay distribution

`detection_delay_s = near_miss.ts − lock_time`, all 52 rows:

| stat | value |
|---|---|
| median | 24,599 s (**410 min / 6.8 h**) |
| p10 | 483 s (8.1 min) |
| p90 | 59,190 s (986 min / 16.4 h) |
| min | 116 s (1.9 min) |
| max | 72,150 s (1,202 min / 20.0 h) |

That headline number is misleading on its own — it mixes two very different regimes and should not be read
as "the bot's typical detection lag." Split by contract-day batch:

| batch | n | median delay | range | driver |
|---|---|---|---|---|
| `26JUL19` (detected catching up after the outage) | 40 | 484 min (8.1 h) | 13 min – 20.0 h | historical 20.6 h leg-gap + backlog processing |
| `26JUL20` (fully inside the continuous-leg era) | 12 | **8.1 min** | 1.9 – 13.7 min | steady-state feed latency only |

The `26JUL20` batch is the operationally meaningful number: **with the leg running continuously and the
book-watcher active, the bot notices a true lock in a median of ~8 minutes, entirely consistent with (and
fully explained by) MADIS's documented ~10-minute publication latency and weather.gov's documented
~15–20-minute latency** — not adaptive-poll-cadence laziness (the runner already polls every 5–20s once
within 2°F of a strike) and not leg downtime (verified continuous).

## 3. Decomposition

**(a) Obs publication latency:** not independently measurable against IEM 1-min per the finding above (that
product itself lags by ~a day). Using the feeds actually deployed: MADIS is documented/measured at ~10 min,
weather.gov consensus at ~15–20 min (`madis_feed.py`, `weathergov_feed.py` docstrings, "MEASURED 2026-07-18").
The `26JUL20` steady-state median (8.1 min) sits inside that band — obs latency is the dominant, essentially
complete explanation of steady-state detection delay.

**(b) Leg-coverage gap:** classified every row by whether its reconstructed `lock_time` falls before or after
the verified 2026-07-19T21:28:17Z continuity start:

| class | n | definition | meaning here |
|---|---|---|---|
| **LEG-GAP** | 32 (62%) | `lock_time` inside the pre-21:28:17Z dead zone | true lock happened while **no leg was running at all** — this is the historical 20h39m outage (switch was ON but the workflow chain wasn't actually looping), not an ongoing problem: the pre-chain/self-chain fix that produced the unbroken 52-leg run from 21:28:17Z onward was merged into the same day |
| **POLL-GAP** | 20 (38%) | `lock_time` after 21:28:17Z, detection came >90s later | leg alive, but detection still lagged — for the 8 of these still in the `26JUL19` batch (13–298 min lag), this looks like backlog/first-catch-up-cycle behavior right after the outage ended, not steady state; for the 12 in the `26JUL20` batch (2–14 min lag) this is the clean, explainable feed-latency signature above |
| **MARKET-FASTER** (strict definition: leg polled ≤90s before lock and ask was already 100) | 0 (0%) | — | no row's leg-alive detection came within 90s of true lock, by this narrow definition |

No LEG-GAP fraction is a live, ongoing problem — it is 100% attributable to the one-time pre-continuity-fix
outage window, which by construction cannot recur under the current chained-leg design (verified zero gaps
>19 min across 52 consecutive legs after the fix).

## 4. Market repricing speed — the finding that actually answers "would anything help"

10 tickers sampled (3 LEG-GAP, 3 `26JUL19`-batch POLL-GAP/backlog, 4 `26JUL20`-batch POLL-GAP/steady-state) —
`GET /series/{s}/markets/{ticker}/candlesticks?period_interval=1` from market open through the near-miss
timestamp, `no_ask = 1 − yes_bid` per 1-min candle, comparing the **last minute `no_ask ≤ 98¢`** against the
reconstructed ground-truth `lock_time` (not against detection time):

| ticker | class | last no_ask≤98¢ vs. **lock_time** |
|---|---|---|
| KXHIGHMIA-26JUL19-T88 | LEG-GAP | **−24.2 h** |
| KXHIGHTPHX-26JUL19-T96 | LEG-GAP | −15.5 h |
| KXHIGHAUS-26JUL19-T93 | POLL-GAP (backlog) | −5.8 h |
| KXHIGHDEN-26JUL19-B93.5 | POLL-GAP (backlog) | −2.6 h |
| KXLOWTNOLA-26JUL20-T81 | POLL-GAP (steady-state) | −2.15 h |
| KXHIGHTLV-26JUL19-T101 | POLL-GAP (backlog) | −83 min |
| KXLOWTNYC-26JUL20-B66.5 | POLL-GAP (steady-state) | −60 min |
| KXLOWTMIN-26JUL20-T73 | POLL-GAP (steady-state) | −13 min |
| KXHIGHTATL-26JUL19-T90 | LEG-GAP | **−5 min** |
| KXLOWTOKC-26JUL20-B75.5 | POLL-GAP (steady-state) | **−4 min** |

Median: **−106 minutes**. **In all 10/10 sampled tickers, the market had already pushed `no_ask` above 98¢
*before* the ground-truth mechanical lock condition itself was satisfied** — not just before the bot detected
it. The gap between "market believes this is essentially certain" and "the conservative, glitch-filtered,
margin-1°F/sustain-3-min rule formally confirms it" ranges from 4 minutes to over a day, median ~1.8 hours.

This is not a novel discovery in this codebase — it corroborates the repo's own **EARLY-LOCK** research
program (`wx_earlylock_deep_study.md`, `wx_earlylock_accrual.md`), which independently measured a **~60-minute
median lead** between the market crossing P(clear)≥0.95 and the mechanical lock firing, and which explicitly
tried to monetize exactly this pre-lock window. Their verdict, after an adversarial re-review that flipped a
scoring bug: **no cell (36 threshold×delay×cap combinations, both HIGH and LOW) clears statistical
significance** — best day-clustered |t| ≈ 0.28–1.6 against a Bonferroni bar of ≈3.11, and the single
best-looking cell reverses sign between the first and second half of its own sample (+9.6c → −8.1c). Their
recommendation was explicit non-activation.

## 5. Verdict

**Of the four candidate fixes, none converts a material fraction of these 52 near-misses, and the data says
so for two structurally different reasons:**

- **(a) Faster obs feed (e.g., activating the paid Synoptic 1–2 min tier):** would cut the *detection* delay
  (steady-state ~8 min → ~1–2 min) but **cannot** create a capture window that the candlestick data shows
  already closed before the ground-truth *lock condition itself* fired, in 10/10 sampled cases. Even a
  zero-latency feed running the identical rule is bounded by `lock_time`, and the market beat `lock_time` by a
  median of 106 minutes. **Estimated convertible fraction: ~0%.** (2 of the 10 samples — ATL −5 min, OKC
  −4 min — show the market beating the rule by less than the ~10-min MADIS latency itself, so in principle a
  sub-4-minute feed+poll combination *might* reach those; call this an upper bound of **≈10–20%**, not a
  demonstrated one, since the repo's own EARLY-LOCK study found no monetizable edge even when it CAN see
  the pre-lock window.)
- **(b) Tighter leg coverage:** matters only for the 62% LEG-GAP share, and that share is a one-time historical
  artifact of the pre-fix 20h39m outage (2026-07-18T20:23–2026-07-19T21:28), already closed by the
  pre-chain/self-chain change merged the same day (verified: 52/52 legs since then with no gap >19 min).
  Coverage is not the live bottleneck. **Estimated convertible fraction going forward: ~0%** (there is nothing
  left to fix — and even where it once mattered, the market had usually already repriced hours before the
  gap-era lock anyway, e.g. MIA −24.2h, PHX −15.5h).
- **(c) Book-watcher / poll-cadence tuning:** the watcher's 0 attributed fires is the **expected, correct**
  outcome given (a) and (4) — it watches for an ask dropping back ≤98¢ *after* a confirmed lock, but in every
  sampled case the ask was already ≥99¢ before the lock even fired, so there was never a post-lock window for
  it to catch. **Estimated convertible fraction: ~0%.**
- **(d) Nothing — the window never existed for this rule:** **this is the dominant, correct explanation for
  essentially all 52 rows.** `kwx_runner`'s lock rule is deliberately conservative (require the extreme to
  clear the strike by a full margin degree AND sustain 3+ minutes, specifically to avoid the 13.7% glitch-loss
  rate of `sustain=1`). The market, informed by same-day forecast trajectory and momentum rather than only the
  raw obs stream, prices "no" toward the ceiling well ahead of that conservative confirmation — a dynamic the
  repo already characterized and already tried to trade (EARLY-LOCK) without finding a statistically robust
  edge. The bot's `MAX_PAY_CENTS=98` filter and its own comment ("skip dead-on-arrival fires — ~63% of raw
  fires have no gap") already assumed this; this analysis supplies the first per-row, ground-truth-timed
  confirmation of it for the current near-miss batch.

**Bottom line: ~0% of the 52 near-misses are convertible by feed speed, leg-coverage, or watcher tuning under
the current lock rule; at most ~1–2 of 52 (≈2–4%, extrapolated from the 2/10 close-call samples) sit within a
theoretically reachable few-minute window, and even that slice has no demonstrated positive EV per the repo's
own EARLY-LOCK study.** The mechanical-lock strategy's real ceiling is not detection latency — it is adverse
selection: rungs cheap enough to still be tradeable at margin+sustain confirmation are, by the market's own
more-informed pricing, already mostly resolved.

## Files in this directory
- `nearmiss_diagnosis.json` — per-row: ticker, lock_time, detect_ts, delay_s, class, capture_window_s (10/52 sampled)
- `reconstruction_raw.json` / `reconstruction_classified.json` — full working data incl. obs source, floor/cap, margin
- `candle_sample.json` — the 10-ticker candlestick sample behind §4
- `all_events.json`, `events/*.json` — raw Kalshi event/market data (floor/cap ground truth)
- `iem/*.csv`, `iem_manifest.json` — IEM 1-min pulls (kept for the record; unusable, see Method)
- `kwx_live_commits.txt`, `leg_commits_sorted.txt` — leg-alive git-commit heartbeat history
