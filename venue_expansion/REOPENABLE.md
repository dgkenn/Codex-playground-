# Can the collected data yield a winner? — what's actually reopenable (2026-07-27)

Short answer: **no strategy in the collected data IS a winner today.** But 8 of the 37 graveyard
entries were never disproved — they ran out of sample against a *live-API retention wall* — and the
archive does not have that wall. This measures which of those 8 the collected data genuinely
unblocks, so effort goes where a test is now possible rather than where it isn't.

Reproduce: `python venue_expansion/reopen_check.py` (read-only, predicate-pushdown over the HF
markets shards).

## Measured archive coverage vs what each kill could reach

| Series | Kill | Kill reached | Kill needed | **Archive holds** | Reopenable? |
|---|---|---|---|---|---|
| `KXHIGH*` | #3/#5/#9 directional SPEC 1/3/7 | n=17 / n=84 entries | n≥200 / n≥300 | **3,279 events, 19,355 settled** | **YES** — ~100× |
| `KXCPI` | #29 macro-surprise | ~31 TEST events | ≥40 events, ≥3 families | **104 events, 590 settled** | **YES** |
| `KXJOBLESSCLAIMS` | #24 illiquid r1s3 relist | 10 servable Thursdays | ≥15 Thursdays | **24 events, 192 settled** | **YES** |
| `KXPAYROLL` | #29 (second family) | — | contributes to ≥3 families | 26 events, 88 settled | partial — pairs with KXCPI |
| `KXFEDMENTION` | #22 illiquid r1s1 | 1 retrievable event | ≥8 event-days | 9 events, 264 settled | **MARGINAL** — 9 vs 8 floor |
| `KXJOBLESSCLAIMS` | #26 stacked r1s2 AR(1) | 10 of 28 weeks | **≥60 weeks** | 24 events | **NO** — still 36 short |
| `KXHANNITYMENTION` | #22 illiquid r1s1 | 2 retrievable events | ≥8 event-days | **0 rows — absent entirely** | **NO** |

So: **3 genuinely reopenable** (directional SPECs 1/3/7, macro-surprise, jobless relist),
1 marginal, 2 permanently dead. The retention-wall kills were, for the most part, an artifact of
querying the live `/events` endpoint instead of the archive.

## The honest caveat, which is large

These were killed for *insufficient data*. In the same funnels, every spec that **was** adequately
powered came back decisively negative:

- Directional SPEC 2 (n=815, t=−3.16), SPEC 4 (n=2,109, t=−4.05), SPEC 5 (n=525, t=−1.81),
  SPEC 6 (fill rate 19.7% vs 60% needed). The funnel's verdict as a family was NULL.
- #29's own mechanism preflight passed (10/10 releases cleared liquidity) but the hypothesis was
  never tested — so it is genuinely open, not merely underpowered-negative.

**More data unblocks the test; it does not improve the prior.** Running SPECs 1/3/7 resolves an
open question. It is not a likely path to a winner, and should be framed that way before anyone
spends on it.

## The bigger change: executable prices are now measurable

Larger than the shard finding, and underexploited. The single most common killer across the entire
graveyard is **entry realism** — the signal is real at the mid or last print, and the spread eats it
at the crossing price (#20, #30, #33, #34, and the forecast sleeve two days ago).

Every prior universe-wide screen ran on `last_price` or mid. Kalshi's candlestick endpoint returns
**per-minute `yes_bid` AND `yes_ask` history**, verified working this week (it is what priced the
261 forecast-sleeve trades at true executable cost). That means a screen can now be built on
**executable prices from the start**, instead of screening on a proxy and losing the survivors at
the realistic-entry retest — which is precisely how #34's 5 survivors died.

This cuts both ways and should be stated plainly: honest prices historically *kill* things here.
The value is that the answer would be trustworthy the first time, not that it is more likely to be
positive.

## Also outstanding

- **44% of the trade archive was never read** (9 of 16 shards, `DATA_SOURCES.md`). Every backtest in
  the graveyard ran on a partial, non-random sample of each market's tape. This does not resurrect
  the *mechanism* kills — "market prices it", "spread eats it" don't reverse with more rows — but it
  does mean the negatives were computed on incomplete data, and anything order-sensitive
  (first-trade-after-signal, VWAP) was measured on a subsample.
- **#31 favorite-longshot Spec 2** was scored `deployable=NO` purely because a join wouldn't finish
  in budget. That is an infrastructure kill, not evidence, and the full shard set makes it heavier,
  not lighter — it needs a budgeted background run, not a retry.

## Recommended order, if pursuing any of this

1. **Finish S3 (ForecastEx)** — in flight. Only candidate that is both structurally right and
   US-legal.
2. **Executable-price universe screen** using candlestick bid/ask — new capability, closes the
   methodological hole that killed the most studies, and reusable for everything after.
3. **Macro-surprise #29** — the only reopenable entry whose mechanism preflight actually passed and
   whose hypothesis was never tested.
4. Directional SPECs 1/3/7 and the jobless relist — testable now, poor family prior. Lowest priority.
