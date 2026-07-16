# Cross-Asset Replication + Capacity Study: Kalshi Hourly-Ladder Deep-OTM Wing VRP

**Date:** 2026-07-16
**Script:** `/home/user/Codex-playground-/kalshi_wing_xasset.py`
**Edge under test:** On Kalshi's hourly BTC ladder (KXBTCD), deep-OTM WING strikes
(early YES price in (0, 0.15]) are systematically OVERPRICED. SELLING YES on wings,
entered in the first half of [open, close] at the real observed bid, nets ~+1-2c/ct
net of fees. Question: does it replicate on ETH / SOL / XRP (and DOGE), and what is
realistic capacity?

Method mirrors the validated BTC verification, applied per asset, written from scratch.
Data: Kalshi public API (no auth), `https://api.elections.kalshi.com/trade-api/v2`.

---

## 1. Sibling series existence

All four candidate roots exist and settle, plus DOGE:

| Asset | Series | Exists | Sample span | Events/day |
|-------|--------|--------|-------------|-----------|
| BTC | KXBTCD | yes | 2026-06-03 .. 2026-07-16 | 24 (hourly) |
| ETH | KXETHD | yes | 2026-06-03 .. 2026-07-16 | 24 (hourly) |
| SOL | KXSOLD | yes | 2026-06-03 .. 2026-07-16 | 24 (hourly) |
| XRP | KXXRPD | yes | 2026-06-03 .. 2026-07-16 | 24 (hourly) |
| DOGE | KXDOGED | yes | 2026-06-03 .. 2026-07-16 | 24 (hourly) |
| ADA (KXADAD) | — | **NO** (returns nothing) | — | — |

Kalshi exposes ~44 settled dates of hourly-crypto history (early June to mid-July 2026).
The roots also carry a few 25h / 169h daily/weekly products (~7% of traded markets);
these are **filtered out** — the study restricts to markets with open→close life in
[0.8h, 1.2h] (the hourly ladder the edge is defined on).

## 2. Method (anti-artifact discipline)

- **Wing** = market whose count-weighted first-half YES VWAP ∈ (0, 0.15], with ≥2
  first-half trades. First half = `created_time ≤ open + (close-open)/2`, **strictly by
  timestamp, no look-ahead**.
- **Entry price** = count-weighted VWAP of `yes_price_dollars` over first-half trades.
- **Executable SELL price** = mean `yes_price` of first-half taker-SELL trades
  (`taker_side=="no"` ⇒ taker bought NO ⇒ sold YES ⇒ hit the YES bid). This is what a
  seller would actually receive. `nExec` = # wings that had ≥1 real taker-sell.
- **Outcome** from SETTLEMENT only (`result` yes=1 / no=0).
- **PnL/ct (sell YES)** = sell_price − outcome − fee, fee = max(0.01, ⌈0.07·p·(1−p)·100⌉/100).
- **Bins** by entry: ≤.02, .02–.04, .04–.06, .06–.10, .10–.15.
- **Day-clustered t** (cluster by close DATE), one-way cluster-robust SE.
- **OOS**: dates sorted, train = earliest 70%, test = latest 30%.
- **Power gate**: ≥1500 wing obs AND ≥30 dates/asset, else flagged UNDERPOWERED.

## 3. Per-asset results

Full-sample and OOS numbers are the trustworthy ones. Individual per-bin t-stats
occasionally explode (e.g. bins where realized-YES = 0 exactly → zero variance →
degenerate SE); those are artifacts and are ignored in the verdict.

### Calibration (favorite-longshot / overpricing) — replicates on EVERY asset

Realized YES rate is **below** entry price in essentially every wing bin, every asset
(aggregate `gap = realized − entry`, ALL wings ≤.15):

| Asset | entry | realized YES | gap | Overpriced? |
|-------|-------|--------------|-----|-------------|
| BTC | 0.038 | 0.017 | −0.022 | yes |
| ETH | 0.038 | 0.019 | −0.019 | yes |
| SOL | 0.040 | 0.021 | −0.020 | yes |
| XRP | 0.042 | 0.026 | −0.016 | yes |
| DOGE | 0.049 | 0.009 | −0.039 | yes |

The raw mispricing (wings pay out less often than their price implies) **replicates
cleanly cross-asset**. The question is whether it survives fees + the real executable
sell price.

### Wing-SELL PnL (cents/contract), day-clustered

| Asset | wings | dates | pwr | full sellVWAP¢ (t) | full sellExec¢ (t) | OOS-test sellVWAP¢ (t) | **OOS-test sellExec¢ (t)** | execCov |
|-------|------:|------:|:---:|:---:|:---:|:---:|:---:|:---:|
| **BTC** | 8826 | 44 | ok | +1.17 (4.48) | +0.99 (2.97) | +0.78 (1.38) | **+1.03 (1.49)** | 0.73 |
| **ETH** | 1771 | 44 | ok | +0.92 (2.27) | +0.80 (1.39) | +0.37 (0.50) | **+0.54 (0.53)** | 0.65 |
| **SOL** | 1536 | 44 | ok | +0.96 (2.16) | +0.36 (0.58) | +0.89 (0.94) | **+0.36 (0.25)** | 0.69 |
| XRP | 808 | 44 | **under** (obs) | +0.63 (0.94) | +0.20 (0.21) | +0.62 (0.74) | **−0.11 (−0.08)** | 0.53 |
| DOGE | 108 | 36 | **under** (obs) | +2.95 (2.84) | +5.40 (2.13) | +3.82 (4.18) | **+6.96 (6.48)** | 0.36 |

`execCov` = fraction of wings that actually had an observable taker-SELL to hit
(~30–47% of wings never traded on the bid in the first half — you simply couldn't sell
those at an observed price).

Key reads:
- **BTC** — the validated edge holds with full power: overpriced in every bin,
  sell-YES at the executable price = **+0.99c/ct t=2.97 full sample, +1.03c/ct t=1.49
  out-of-sample**. Confirmed. (In-sample TRAIN was +0.98c t=2.53; the claimed t~4-6
  shows up on the mid-price/VWAP variant and on the training window.)
- **ETH** — directionally replicates (overpriced, positive PnL) but **weaker**:
  full-sample +0.80c t=1.39; OOS test decays to +0.54c t=0.53. Not independently
  significant out-of-sample.
- **SOL** — mispricing is real at the MID (sellVWAP +0.96c t=2.16), but a real seller
  hitting the bid gives almost all of it back: **executable +0.36c t=0.58**, OOS
  +0.36c t=0.25. The wider wing half-spread on SOL eats the edge. Does **not** replicate
  at the executable price.
- **XRP** — underpowered on obs (808 wings), no tradeable edge: executable ≈ 0, OOS
  slightly negative.
- **DOGE** — the only large/"significant" executable number, but it is **not credible**:
  108 wings, only 39 with any executable sell, most bins have realized-YES = 0 exactly
  (degenerate), and median tradeable size is ~0 contracts/day. Statistical noise on an
  untradeable market.

## 4. Capacity study

Depth measure (a), `yes_bid_size_fp` in the market object, is **uniformly 0** across all
wings on all assets — it is a post-settlement snapshot, so live resting-bid depth is not
recoverable from settled data. Capacity is therefore estimated from **realized first-half
taker-SELL volume** (contracts that actually transacted by hitting the YES bid) as a
lower-bound proxy for "size you could sell without moving price more than ~1c," plus total
first-half wing volume.

| Asset | first-half wing vol/mkt p50 / p90 (ct) | taker-SELL vol/mkt p50 / p90 (ct) | per-EVENT sellable p50 (ct) | **per-DAY sellable p50 (ct / $prem)** |
|-------|:---:|:---:|:---:|:---:|
| BTC | 2 581 / 32 586 | 279 / 9 070 | 22 183 | **~581 500 ct / ~$49 600** |
| ETH | 2 252 / 9 568 | 136 / 1 743 | 620 | **~22 500 ct / ~$1 205** |
| SOL | 800 / 4 649 | 42 / 915 | 200 | **~7 540 ct / ~$387** |
| XRP | 354 / 1 864 | 1 / 420 | 5 | **~1 510 ct / ~$76** |
| DOGE | 252 / 1 309 | 0 / 296 | 0 | **~0 ct / ~$0** |

Blunt capacity reality:
- "$ premium" = sellable_contracts × wing_price, i.e. the notional YES premium you'd
  collect on a full day, **not** profit. At the ~1c realized edge, gross theoretical PnL
  is roughly premium × (edge / price) ≈ sellable_contracts × 1c. For BTC that's
  ~581k × $0.01 ≈ **$5.8k/day gross at 100% capture of executable sell flow** — but you
  would be *competing with* that flow, not adding to it, so realistic capture is a
  fraction (say 10–25%) ⇒ **~$600–1,500/day on BTC**.
- ETH ≈ 22.5k ct/day ⇒ ~$225/day at full capture, realistically <$60/day.
- SOL/XRP ≈ 7.5k / 1.5k ct/day ⇒ tens of dollars/day; DOGE untradeable.
- Per-market executable size is small (BTC median only 279 contracts; p90 ~9k). The large
  per-day totals come from summing ~24 hourly events × many wing strikes. Capacity is
  "wide and shallow": many tiny fills, not a few big ones.

## 5. Verdict (blunt)

- **Sibling series exist for ETH, SOL, XRP, DOGE** (ADA does not).
- **The raw overpricing (favorite-longshot) replicates cross-asset** — every asset's wings
  settle YES less often than priced. That part is robust and universal.
- **The TRADEABLE edge (net of fees, at the executable sell price) replicates cleanly only
  on BTC.** BTC: +1.0c/ct, day-clustered t≈3 full / ≈1.5 OOS, 44 dates, 8826 obs.
- **ETH is a weak/partial replication** (+0.8c full t=1.4, but OOS t≈0.5). **SOL replicates
  at the mid but NOT at the executable price** — the wider wing spread consumes the edge
  (executable +0.36c, t<1). **XRP shows no tradeable edge** and is obs-underpowered.
  **DOGE is untradeable noise.**
- This is therefore **NOT a clean cross-asset win.** It is a BTC-specific edge that leaves
  a directional footprint (overpricing) everywhere but only clears fees + real spread on
  the single most liquid ladder. Selling the mid overstates it on every non-BTC asset.
- **Realistic capacity** (the honest, executable number): BTC ~**$0.6–1.5k/day** of edge
  PnL at partial capture (~$50k/day gross wing premium, ~1c edge, wide-and-shallow fills);
  ETH an order of magnitude smaller; SOL/XRP/DOGE negligible. This is a small-capacity,
  BTC-centric edge — not a scalable cross-asset program.

### Caveats / anti-artifact notes
- Sample is 44 consecutive dates (Jun 3 – Jul 16, 2026); this is the full settled history
  Kalshi exposes for these hourly crypto ladders. One ~6-week regime; no multi-regime test
  is possible.
- Live resting-bid depth is not in settled market objects (`yes_bid_size_fp`=0 post-settle);
  capacity rests on realized taker-sell flow, a proxy you'd be competing against.
- Individual per-bin t-stats can be degenerate where realized-YES=0 exactly; only the
  aggregate ≤.15 and OOS figures are used for conclusions.
- First-half entry strictly by `created_time`; outcome only from settlement; all t-stats
  day-clustered by close date.
