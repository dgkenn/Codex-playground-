# Candidate: Cross-Family Favorite–Longshot / Calibration Bias (Kalshi)

**Status: staged, uncommitted. READ-ONLY public Kalshi API. No orders, no keys, no live-config edits.**
**Date: 2026-07-15. Branch: claude/coding-bot-ab-test-results-ffmhxw.**

## Hypothesis
Prices systematically deviate from empirical resolution rates: longshots (~0.05–0.15) resolve
YES *less* often than priced (overpriced → sell), favorites (~0.85–0.95) resolve *more* often
than priced (underpriced → buy). Goal is the **cross-FAMILY map**: where (if anywhere) does the
bias actually live? This is explicitly orthogonal to — and overlaps — our already-NULL longshot +
tailbias sleeves; the new value is the family breakdown, not the longshot idea itself.

## Method (honest, reproducible)
- **Universe:** settled Kalshi markets, enumerated per family via
  `GET /markets?status=settled&series_ticker=…` (paginated).
  Families → series: crypto_15m {KXBTC15M, KXETH15M, KXXRP15M}, crypto_hourly {KXBTC, KXETH},
  crypto_daily {KXBTCD, KXETHD}, weather {KXHIGHNY/LAX/CHI/MIA/DEN/AUS/PHIL}, commodities {KXWTI},
  econ {KXCPI, KXCPIYOY, KXFED, KXFEDDECISION, KXPAYROLLS}.
- **Tradeable snapshot (NOT settlement):** for each market, pull 1-minute candlesticks
  (`GET /series/{s}/markets/{ticker}/candlesticks`) and take the **yes_bid/yes_ask mid at a fixed
  lead before close** (4 min for ≤20-min markets, 12 min ≤90 min, 30 min ≤6 h, else 60 min).
  Snapshot is always strictly before close (settlement candle explicitly excluded) → no look-ahead.
- **Outcome:** `market.result ∈ {yes,no}` (resolved-iff, not the status-string trap;
  same convention as `settle_recorder.py`).
- **Edge test (fixed a-priori FL rule, executable prices):**
  SELL-longshot if mid∈[0.02,0.15] → sell YES at **bid**, pnl = bid − y − taker_fee(bid);
  BUY-favorite if mid∈[0.85,0.98] → buy YES at **ask**, pnl = y − ask − taker_fee(ask).
  Requires non-degenerate book (spread ≤ 0.07). Kalshi quadratic taker fee `ceil(0.07·p(1−p)·100)/100`.
  t-stat is **day-clustered** by close date (cluster = event/day), matching the FAVLONG machinery.
- **API budget:** 323 usable snapshots from ~430 market lookups + ~40 list calls; paced ~0.12 s/call,
  cached to `snapshots.jsonl`. Gentle (other agents share the API).

## Data collected
323 snapshots: crypto_15m 90, crypto_hourly 46, crypto_daily 35, weather 65, commodities 38, econ 49.
Books are tight (median spread 0.005–0.02; zero wide/degenerate books), so snapshots are genuinely
tradeable.

## Headline structural finding (the reason power is thin)
At a fixed lead before close, the **strike-ladder families are already "decided"**: their price mass
sits in the deep tails. crypto_hourly (46/46), crypto_daily (35/35) and weather (57/65) live *entirely*
in the 0.00–0.05 or 0.95–1.00 bins — there is essentially **no mid-range price to calibrate**. Only
**crypto_15m** and **econ** show a full spread of prices across the 0.15–0.85 range. So most families
cannot even express a favorite-longshot bias at this horizon.

## Pooled calibration curve (all families)
| price bin | n | avg mid | empirical P(YES) | dev (emp−mid) |
|---|---|---|---|---|
| 0.00–0.05 | 172 | 0.007 | 0.006 | **−0.001** |
| 0.05–0.15 | 9   | 0.114 | 0.000 | −0.114 |
| 0.15–0.35 | 13  | 0.239 | 0.231 | −0.008 |
| 0.35–0.65 | 22  | 0.518 | 0.636 | +0.118 |
| 0.65–0.85 | 21  | 0.765 | 0.905 | +0.140 (>2·se) |
| 0.85–0.95 | 16  | 0.911 | 1.000 | +0.089 |
| 0.95–1.00 | 70  | 0.989 | 0.986 | **−0.004** |

The **deep tails, which hold 242 of 323 markets (75%), are essentially perfectly calibrated**
(0.007→0.006 and 0.989→0.986). A directional FL *shape* appears only in the thin interior bins
(below diagonal at 0.05–0.15, above diagonal at 0.35–0.95), but every interior bin has n ≤ 22.

## Favorite–longshot strategy edge (net fee+spread, day-clustered)
| family | side | n | days | mean/contract | t |
|---|---|---|---|---|---|
| crypto_15m | SELL-longshot | 10 | 1 | +0.069 | n/a (1 day) |
| crypto_15m | BUY-favorite  | 18 | 1 | +0.062 | n/a (1 day) |
| commodities| SELL-longshot | 3  | 1 | +0.047 | n/a (1 day) |
| econ       | SELL-longshot | 6  | 3 | +0.045 | 6.08 |
| econ       | BUY-favorite  | 6  | 5 | **−0.140** | −0.83 |
| **POOLED** | **SELL-longshot** | **19** | **4** | **+0.058** | **5.99** |
| **POOLED** | **BUY-favorite**  | **27** | **6** | +0.013 | −0.10 |
(crypto_hourly/daily/weather contribute 0 tradeable FL trades — all mass in deep tails.)

### Why the +0.058, t≈6 longshot number is NOT a real edge
- **19/19 of the SELL-longshot trades resolved NO** (a perfect win rate) — the exact "high-win-rate
  illusion" the prior sleeve audit flagged (`audit_longshot_tailbias.md`: longshot 93% win, realized
  t=0.84). With zero losses observed, the day-clustered variance is near-zero, so t explodes
  mechanically; it is not evidence of robustness.
- **Boundary artifact:** markets at mid≈0.175–0.185 *did* resolve YES (KXETH15M-26JUL150830,
  KXPAYROLLS-26MAY-T150000) — they sit just above the [0.02,0.15] cutoff. Nudge the longshot
  threshold and the "edge" absorbs a −0.85 loss. The neighbouring 0.15–0.35 bin is already
  calibrated (emp 0.231 vs mid 0.239).
- **Uninsured tail:** selling a fairly-priced 0.10 longshot is ≈0 EV before costs; the per-contract
  "win" looks large only because the loss (YES resolves, −0.85 to −0.95) is rare and absent from this
  4-day / 19-trade window. This is precisely the risk that made the longshot sleeve NULL on 15
  realized bets.
- **Favorite side (the other half of the hypothesis) is NULL/negative:** BUY-favorite pooled
  +0.013, t=−0.10; econ favorites even went the *wrong* way (0.95–1.00 bin emp 0.875 < mid 0.977).
  Once you pay the ask + fee, the interior "underpricing" does not survive.

## Per-family verdict
| family | mid-range signal? | edge net of costs | powered? | **verdict** |
|---|---|---|---|---|
| crypto_15m   | yes (full spread) | FL shape visible; SELL +0.069 / BUY +0.062 but **1 settlement day** | no | **INSUFFICIENT-DATA** |
| crypto_hourly| none (46/46 deep tail) | 0 tradeable FL trades; tail perfectly calibrated | no | **NULL** |
| crypto_daily | none (35/35 deep tail) | tail calibrated (emp 0.029 vs 0.005, n=35) | no | **NULL** |
| weather      | none (57/65 deep tail) | tail calibrated; no interior obs | no | **NULL / INSUFFICIENT** |
| commodities  | mostly deep tail | SELL n=3 +0.047 (1 day); tail calibrated | no | **NULL / INSUFFICIENT** |
| econ         | yes (full spread) | roughly calibrated; SELL n=6 t=6.08 but 19/19-type artifact; BUY −0.14 | no | **NULL** |
| **POOLED**   | interior only, thin | SELL +0.058 (artifact); BUY +0.013 (t≈0); tails perfectly calibrated | no | **NULL** |

## Cross-family map (the deliverable's point)
- **Deep tails (0–0.05, 0.95–1.00): perfectly calibrated in every family** — no exploitable bias
  where 75% of the markets live.
- **The FL bias, to the extent it shows, lives only in the thin near-longshot band (0.05–0.15) and the
  0.65–0.95 favorite band, and only in the two families that even *have* mid-range prices (crypto_15m,
  econ).** In both it is boundary-sensitive, tail-uninsured, and driven by a zero-loss small sample.
- **No family clears a powered, cost-net, robustly-clustered bar.** The apparent pooled longshot edge
  is the same illusion already ruled NULL for the longshot/tailbias sleeves; this cross-family sweep
  adds no new exploitable location for it.

## Overall verdict: **NULL** (with crypto_15m/econ flagged INSUFFICIENT-DATA, not promising)
No family shows a real, powered, cost-net cross-family miscalibration. The one eye-catching number
(SELL-longshot +0.058/contract, day-clustered t≈5.99, n=19) is a boundary + zero-loss + 4-day
artifact, fully consistent with the previously-NULL longshot sleeve — not a new edge.

### To ever power this (pre-registration note)
Sample earlier in each market's life (not at the fixed near-close lead, where strike ladders have
already decided), across ≥30 independent settlement days, keeping the longshot cutoff fixed a-priori
and *forcing* the sample to include markets that straddle 0.10–0.20 so the −0.85 tail losses are in
the ledger. Only then is a longshot t ≥ 2.0 meaningful.

## Repro artifacts (scratchpad, not committed)
- `xfam/collect.py` — enumerate settled markets + fixed-lead candlestick snapshot.
- `xfam/recover.py` — sparse-candle recovery for KXBTC/KXBTCD (nearest pre-close candle).
- `xfam/analyze.py` — calibration tables + day-clustered FL edge.
- `xfam/snapshots.jsonl` — 323 (price, outcome, family) records.
