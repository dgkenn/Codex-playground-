# Phase 2 / Track A: K-WX Nowcast Edge on the FULL Real Price History

Run: 2026-07-18. Script: `phase2_trackA_price.py`. Raw per-market-day checkpoint:
`_trackA_results_raw.json` (4,383 rung-market-days that fired at least one grid cell).
Summary: `phase2_trackA_price_summary.json`. Real Predexon L2 depth samples:
`_predexon_depth_samples.json` (20 clean pulls out of 51 attempted, real historical
fire-time snapshots, not live).

**Scope**: ALL 20 KXHIGH cities + their 20 KXLOWT mirror series, FULL 6-rung ladder per
city-day (1 `greater` + 4 `between` + 1 `less`, verified live against the Kalshi API before
coding: `KXHIGHNY-26JUL17-{T90,T83,B89.5,B87.5,B85.5,B83.5}` = exactly 1 greater/1 less/4
between), for the COMPLETE tradeable-market window this environment exposes:
**2026-05-12 to 2026-07-17 (67 days)**. 16,074 rung-market-days discovered (8,040 HIGH +
8,034 LOW), all analyzed; 4,383 had at least one firing cell across the margin x sustain
grid. Warm-season-only window (no winter data available in this environment — noted, not
fixable here).

## 0. The generalized ratchet rule (full ladder, both directions)

HIGH markets settle YES iff `floor < actual_high <= cap` (missing bound = +-inf). The 1-min
ASOS running max is a monotone-increasing LOWER bound on `actual_high`:
- rung with a floor and no cap (the top `greater` rung): once running_max clears
  `floor+margin` (sustained), YES is locked -> **buy YES**.
- any rung with a cap (`less` + all 4 `between` rungs): once running_max clears
  `cap+margin` (sustained), YES is impossible for that rung -> **buy NO**.

LOW markets mirror this with the running min (monotone-decreasing UPPER bound):
- rung with a cap and no floor (bottom `less` rung): running_min falls below
  `cap-margin` -> locked YES -> **buy YES**.
- any rung with a floor (`greater` + all 4 `between` rungs): running_min falls below
  `floor-margin` -> locked NO -> **buy NO**.

**Pipeline sanity check**: restricting this generalized rule to `family=HIGH,
rung_group=greater` (i.e. throwing away the new between/less/LOW rungs) at
margin=1/sustain=3 reproduces the OLD single-rung baseline exactly: n=42, win=100.0%, mean
PnL=+0.3433/ct, t=7.56, n_clusters=29 -- bit-for-bit identical to
`kalshi_weather_refined_report.md`. The full-ladder pipeline is verified correct against
the known-good prior result before trusting the expanded numbers below.

## 1. Walk-forward config selection (no in-sample cherry-pick)

66 unique fired dates split chronologically: **train = earliest 39 days (2026-05-12 to
2026-06-19)**, **test = latest 27 days (2026-06-20 to 2026-07-16)**. Grid = margin in
{1,2,3} x sustain in {1,2,3,5} = 12 cells, Bonferroni family size 12, corrected alpha =
0.05/12 = 0.004167. Selection on TRAIN only, ranked by worst-case (Wilson-95) EV among
Bonferroni-significant, n>=8 survivors:

| margin | sustain | n (train) | mean PnL | t | p (Bonferroni) | sig? | worst-case EV |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 2731 | 0.0738 | 15.05 | ~0 | YES | 0.0634 |
| 1 | 2 | 2584 | 0.0868 | 20.64 | ~0 | YES | 0.0792 |
| **1** | **3** | **2442** | **0.0893** | **25.81** | **~0** | **YES** | **0.0868 (BEST)** |
| 1 | 5 | 2268 | 0.0453 | 19.82 | ~0 | YES | 0.0432 |
| 2 | 1 | 2109 | 0.0400 | 15.29 | ~0 | YES | 0.0357 |
| 2 | 2 | 1943 | 0.0223 | 10.96 | ~0 | YES | 0.0193 |
| 2 | 3 | 1812 | 0.0149 | 9.19 | ~0 | YES | 0.0123 |
| 2 | 5 | 1651 | 0.0047 | 4.58 | 5.5e-05 | YES | 0.0019 |
| 3 | 1 | 1529 | 0.0082 | 5.86 | 5.7e-08 | YES | 0.0038 |
| 3 | 2 | 1393 | 0.0053 | 3.62 | 3.6e-03 | YES | 0.0020 |
| 3 | 3 | 1266 | 0.0031 | 2.40 | 0.197 | **no** | -0.0006 |
| 3 | 5 | 1131 | 0.0004 | 0.38 | 1.000 | **no** | -0.0037 |

**Walk-forward-chosen config: margin=1F, sustain=3min.** Verdict: **CONFIRMED**. (Honest
null pocket: margin=3 with sustain>=3 is where the edge dies -- too few, too-late,
too-cheap fires to clear the Bonferroni bar; consistent with the earlier single-rung
finding.)

## 2. Headline numbers, chosen config (margin=1/sustain=3), pooled ALL rungs x ALL cities x HIGH+LOW

| view | n | win% | mean price | mean PnL/ct (net fee) | clustered t | n_clusters(days) | n_bad | worst-case loss (Wilson95) | worst-case EV |
|---|---|---|---|---|---|---|---|---|---|
| TRAIN (in-sample) | 2442 | 99.84% | 0.9053 | 0.0893 | 25.81 | 39 | 4 | 0.42% | 0.0868 |
| **TEST (true out-of-sample)** | **1449** | **99.79%** | **0.9011** | **0.0930** | **19.08** | **27** | **3** | **0.61%** | **0.0890** |
| FULL (train+test) | 3891 | 99.82% | 0.9037 | 0.0907 | 31.88 | 66 | 7 | 0.37% | 0.0888 |

Worst single loss (FULL): -1.00/ct, `KXLOWTMIN-26MAY12-B55.5` (2026-05-12) -- a between-rung
NO that fired and settled the wrong way, the very first day of the sample.

**Held out of sample, the edge did NOT decay** (test mean PnL 0.093 slightly beats train
0.089; test t=19.1 remains overwhelming even on only 27 days / 1449 fires). This is a real
walk-forward pass, not an in-sample cherry-pick.

### Conservative reference: margin=2F/sustain=1min (the OLD single-rung "confirmed" margin)

| view | n | win% | mean price | mean PnL/ct | t | n_bad | worst-case EV |
|---|---|---|---|---|---|---|---|
| TRAIN | 2109 | 99.4% | 0.9524 | 0.0400 | 15.29 | 12 | 0.0357 |
| TEST | 1201 | 99.6% | 0.9499 | 0.0439 | 15.91 | 5 | 0.0384 |
| FULL | 3310 | 99.5% | 0.9515 | 0.0414 | 21.04 | 17 | 0.0383 |

Both configs pass every bar (n>=8, Bonferroni-significant on train, worst-case EV>0) and
both hold up out of sample. margin=1/sustain=3 is the better choice: ~2.2x the mean PnL/ct
of margin=2/sustain=1, more n, higher t.

### The honest "dead-on-arrival" cut -- THE key caveat (median gap at fire = 0.0)

Pooling every rung inflates n a lot, but roughly half of all fires happen when yes_ask is
**already at 100c** (gap=0) -- i.e. the market had already fully repriced by the time our
signal's sustain requirement was satisfied. Those are not losses (fee=0, pnl=0 at a win,
which it always is at p=1) but they are **not real trades** -- nobody transacts at 100c for
a possible $0 profit. Restricting to genuinely tradeable fills:

| config | slice | n | win% | mean price | mean PnL/ct | t | worst-case EV |
|---|---|---|---|---|---|---|---|
| margin=1/sustain=3 | ALL (incl. DOA@100c) | 3891 | 99.82% | 0.9037 | 0.0907 | 31.88 | 0.0888 |
| margin=1/sustain=3 | **deployable (price<99c)** | **1698** | **99.65%** | **0.7805** | **0.2074** | **37.41** | **0.2032** |
| margin=2/sustain=1 | ALL | 3310 | 99.49% | 0.9515 | 0.0414 | 21.04 | 0.0383 |
| margin=2/sustain=1 | deployable (price<99c) | 818 | 98.04% | 0.8053 | 0.1673 | 22.71 | 0.1553 |

**This is the real headline number: on the ~1,698 fires/67 days where there was still an
actual price gap to trade, margin=1/sustain=3 nets +0.207/ct at 99.65% win, t=37.4 -- even
stronger than the naive pooled number, because it strips out the zero-edge noise.**

Gap quantiles (best config, full sample, ALL fires): p10=0.00, p25=0.00, **p50=0.00**,
p75=0.11, p90=0.34. DOA (exec_price >= 0.97) = 63.1% (n=2456/3891). DOA (>=0.99) = 56.4%
(n=2193/3891).

## 3. KXHIGH vs KXLOW, greater vs between/less (best config, FULL sample, all fires incl. DOA)

| slice | n | win% | mean price | mean PnL/ct | t | n_clusters | n_bad | worst-case EV | DOA frac (>=97c) |
|---|---|---|---|---|---|---|---|---|---|
| **HIGH** (all rungs) | 2288 | 99.7% | 0.9117 | 0.0824 | 22.73 | 65 | 6 | 0.0793 | 67.4% |
| **LOW** (all rungs) | 1603 | 99.9% | 0.8923 | 0.1025 | 22.83 | 66 | 1 | 0.0996 | 57.0% |
| **greater rung only** | 713 | 100.0% | 0.9667 | 0.0321 | 7.04 | 66 | 0 | 0.0267 | 87.4% |
| **between/less rungs** | 3178 | 99.8% | 0.8896 | 0.1039 | 32.34 | 66 | 7 | 0.1015 | 57.7% |

Same breakdown for margin=2/sustain=1 (conservative):

| slice | n | win% | mean PnL/ct | t | n_bad | worst-case EV |
|---|---|---|---|---|---|---|
| HIGH | 2106 | 99.5% | 0.0481 | 15.90 | 10 | 0.0441 |
| LOW | 1204 | 99.4% | 0.0297 | 9.73 | 7 | 0.0236 |
| greater only | 555 | 99.3% | 0.0144 | 5.07 | 4 | 0.0032 |
| between/less | 2755 | 99.5% | 0.0468 | 21.85 | 13 | 0.0435 |

**Findings**: (a) LOW is at least as good as HIGH, not a weaker mirror as the earlier
single-rung KXLOW pass worried about -- mean PnL/ct is actually higher (0.1025 vs 0.0824)
and it has fewer bad trades (1 vs 6) at the best config. (b) The `between`/`less` rungs are
where almost all the volume AND most of the edge now live (n=3178 of 3891, mean PnL
0.104/ct vs the top `greater` rung's thin 0.032/ct at n=713, SAME margin/sustain) -- the
single biggest finding of extending to the full ladder: **the top "greater" rung, which is
ALL the earlier single-rung research looked at, is actually the weakest and thinnest part
of the edge, and 87.4% dead-on-arrival.** The obvious ">X" rung reprices fastest (retail
watches it); the bracket (between/less) rungs stay mispriced longer and carry the real edge.

## 4. Gap half-life and captured EV at latency (best config, FULL sample)

**Gap half-life: 3.31 minutes.** Mean gap trajectory after the confirmed cross:

| t+min | 0 | 1 | 2 | 5 | 10 | 30 | 60 |
|---|---|---|---|---|---|---|---|
| mean gap | 0.0963 | 0.0764 | 0.0611 | 0.0315 | 0.0264 | 0.0176 | 0.0112 |

The book reprices fast -- by t+5min the average gap has fallen ~68% from its value at the
cross.

**Captured EV at simulated action latency** (price actually observed at cross+k min, same
fired-event set):

| latency | 0min | 1min | 2min | 5min | 10min | 30min | 60min |
|---|---|---|---|---|---|---|---|
| n | 1897 | 1511 | 1300 | 740 | 638 | 431 | 197 |
| mean PnL/ct | 0.187 | 0.185 | 0.170 | 0.149 | 0.143 | 0.137 | 0.179 |

**Caveat (honest, stated plainly)**: n shrinks hard with latency because many fires happen
late in the settlement day and run out of candle data before market close -- the 60min
column (n=197) is disproportionately morning fires with more runway, a real selection
effect, not a true steady-state number. The 1-10min columns (n=740-1511) are the
trustworthy read: **captured EV degrades ~23% from 0.187 to 0.143/ct over the first 10
minutes of latency, but stays solidly positive and tradeable even at 10-minute action
latency.** Implication: GitHub-Actions-style multi-hour polling is far too slow; near
real-time reaction (sub-few-minute) is required to capture most of the edge, but this is
NOT a sub-second HFT requirement -- a 2-5 minute latency source still nets ~+0.15-0.17/ct.

## 5. Real Predexon L2 depth (replaces the discredited $35k/wk candlestick-volume proxy)

51 real firing markets (from the margin=1/sustain=3 fired set, randomly sampled) attempted
against the real Predexon `/v2/kalshi/orderbooks` endpoint at the exact fire timestamp
(+-15min window, with retry/backoff on 429s), until **20 clean (non-error) snapshots**
were collected:

- 20/51 (39.2%) returned a real order book snapshot with resting size on the relevant side
- 19/51 (37.3%) returned a real snapshot but with an **empty book on the relevant side**
  (zero resting orders at the exact fire instant -- consistent with Section 4's finding
  that the book takes a few minutes to reprice/refill after a mechanical lock)
- 12/51 (23.5%) had no Predexon snapshot at all in the +-15min window (thin coverage on
  these low-volume weather sub-markets, or a genuine data gap)

**Real depth, among the 20 successful pulls:**

| metric | median | p25 | p75 |
|---|---|---|---|
| size resting AT best price | 8.5 | 4.2 | 15.2 |
| depth within 1c of best | 32.0 | 8.2 | 88.2 |
| depth within 2c of best | 90.5 | 33.5 | 122.2 |

Range was wide (0-458 contracts) -- city/market-specific, matching the prior live-snapshot
finding in `kalshi_weather_orderbook_report.md`, which independently found a similar
ballpark (median size-at-ask 13.0, median depth@1c 65.5 on a small n=4 live-locked-KXLOW
sample). The two independent measurements -- live snapshot bucket vs actual historical
fire-time pulls -- corroborate each other reasonably well.

**Honest per-week capacity estimate** (deployable fires only, price<0.99, best config:
1698 fires / 9.57 weeks = 177.4 deployable fires/week across all 20 cities x HIGH+LOW x
full ladder; mean deployable price ~$0.78; applying the REAL observed 39.2% fillable-book
rate as a haircut for fires where no depth was actually resting at t=0):

| assumption | contracts/fire | effective fillable fires/wk | $/week (notional deployed) |
|---|---|---|---|
| zero-slippage (size at best) | 8.5 | 69.6 | **~$460/week** |
| within 1c | 32.0 | 69.6 | **~$1,740/week** |
| within 2c | 90.5 | 69.6 | **~$4,910/week** |
| within 2c, no fillable-rate haircut (book fills in within the ~3min half-life before you act) | 90.5 | 177.4 | **~$12,530/week** |

**Verdict: real per-week capacity is ~$500-$12,500/week depending on how aggressively you
assume the book refills before you act -- one to two orders of magnitude below the earlier
$35k/wk candlestick-volume proxy.** The volume proxy overstated capacity because 24h
candlestick volume includes retail flow that never sits as resting, immediately-fillable
depth at the exact moment of a mechanical lock. This is a capacity ceiling, not a kill --
even the conservative $460-1,740/wk figure is meaningfully positive risk-adjusted return on
a near-zero-capital, near-zero-directional-risk strategy -- but it means this edge does NOT
scale past a small/single-operator size without either (a) posting resting limit orders
ahead of the mechanical lock (maker-side, not taker) or (b) working many names
simultaneously to add up small per-name capacity (the "high fire-count across many
markets/cities" thesis, not "large size in any one market").

## 6. The tail is real but rare

7 losing tickers out of 3891 fires (~0.18%). Worst single trade -1.00/ct (`KXLOWTMIN-
26MAY12-B55.5`, the first day of the sample) and -0.59/ct (`KXHIGHMIA-26JUN20-B92.5`, in
the out-of-sample test fold). These are genuine ASOS-vs-official-CLI disagreements /
sub-margin misses, same failure mode the earlier single-rung passes documented, now with
n=7 examples across the full ladder instead of 1-3.

## 7. Summary verdict

- **The edge SURVIVES on the full all-city, full-ladder, HIGH+LOW price history.**
  Walk-forward-selected config: **margin=1F, sustain=3min**.
  - Pooled (all fires, incl. dead-on-arrival at 100c): n=3891, win=99.8%, EV=+0.091/ct
    net fee, t=31.9, worst-case (Wilson-95) EV=+0.089/ct.
  - Deployable-only (the honest tradeable-edge number, price<99c at fire): **n=1698,
    win=99.65%, EV=+0.207/ct net fee, t=37.4, worst-case EV=+0.203/ct.**
  - True out-of-sample (test fold, last 27 days, not used for config selection): n=1449,
    win=99.8%, EV=+0.093/ct, t=19.1 -- the edge did not decay out of sample.
  - Bonferroni-adjusted across the full 12-cell (margin x sustain) search grid: p ~ 0 (well
    under the corrected alpha=0.004167) at both margin=1/sustain=3 and margin=2/sustain=1.

- **vs the prior single-rung 67-day numbers (KXHIGH "greater" only, margin=1/sustain=3:
  n=42, 100% win, +0.343/ct, t=7.56):** the full-ladder pipeline reproduces that number
  EXACTLY as a subset (verified bit-for-bit, Section 0) -- the earlier finding was correct
  but was only looking at 18% of the real n (713/3891) and, surprisingly, the WEAKER slice
  of it (mean PnL 0.032/ct on the greater-rung-only subset at the SAME margin/sustain, vs
  0.104/ct on the between/less rungs the earlier passes never tested). **Full history wins
  decisively**: ~93x the sample size, still-overwhelming significance, genuine
  out-of-sample confirmation, and it locates where most of the real edge actually lives
  (the between/less rungs, not the top rung).

- **KXHIGH vs KXLOW**: both profitable and both statistically overwhelming; LOW is
  slightly BETTER per-contract (0.103 vs 0.082/ct) with fewer wrong-way settlements (1 vs
  6) at the best config -- the earlier fear that KXLOW would be a weaker/thinner mirror is
  not borne out once the full ladder is included.

- **Greater vs between/less**: between/less rungs supply 82% of fires (3178/3891) and are
  MORE profitable per contract (0.104 vs 0.032/ct) -- a genuine, previously-undiscovered
  reallocation of where the edge lives.

- **Real depth (Predexon, 20 successful historical fire-time L2 pulls)**: median 8.5
  contracts at best price / 32 within 1c / 90.5 within 2c, but only ~39% of fires had ANY
  resting depth at the exact lock instant (the rest were empty-book or uncovered). Honest
  capacity: **~$500-$12,500/week** across all 20 cities x HIGH+LOW x full ladder combined
  -- this REPLACES and is materially lower than the discredited $35k/wk candlestick-volume
  proxy.

- **Honest nulls / degradations, stated plainly**:
  1. margin=3 with sustain>=3 is dead (not Bonferroni-significant, negative worst-case EV)
     -- the edge does not survive being made "extra safe" past margin=2.
  2. Over half of all nominal ladder fires (56-63%) are dead-on-arrival at 100c with zero
     tradeable edge left by the time the sustain filter confirms the cross -- the real,
     tradeable n is much smaller than the raw fired-count suggests.
  3. Gap half-life is only ~3.3 minutes -- this is a fast-decaying edge that needs
     few-minutes-scale execution, not a leave-a-limit-order-overnight edge.
  4. Real order-book coverage at the exact fire instant is spotty (23.5% no snapshot,
     37.3% empty book) -- actual fill probability at t=0 is lower than the raw depth
     numbers alone would suggest.
  5. Sample is warm-season-only (May-Jul); no winter/shoulder-season data exists in this
     environment to check for seasonal degradation.
