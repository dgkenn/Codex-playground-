# Kalshi Crypto Tenor Expansion — does the maker-box edge extend beyond KXBTC15M?

**Goal:** expand the live bot's $/day ceiling (the 15-min BTC box is fill-rate limited,
~$10-27/day, saturates ~$100 bankroll). Find OTHER Kalshi crypto tenors/structures where the
maker-box is ALSO +EV and adds DEPLOYABLE, INDEPENDENT capacity.

**VERDICT (read first):**
> **YES — there is a deployable second crypto box market: `KXBTCD` (Bitcoin price Above/below,
> HOURLY ladder), traded on its ATM strike.** It has a 1c touch spread (same as 15M), a deep
> two-sided book, ~470k contracts/hour of ATM flow, 24 independent windows/day, and the same
> maker-fee-free (post-only) economics. Estimated **incremental ~$12-48/day** (24 windows x
> $50-200/window x ~1c), additive to the 15M box (disjoint settlement times = independent flow).
> The hourly bracket market `KXBTC` ("between" brackets) is NOT viable (2-6c spreads, $1-20 depth).
> All non-BTC assets stay CLOSED. This **re-opens the capacity question that CRYPTO_BINARY_MAP.md
> point 6 had closed** — that note tested the hourly *butterfly/ladder-arb*, not the single-strike
> ATM up/down box, which is a materially different (and liquid) structure.

---

## Data window, N, costs

- **Source:** Kalshi public REST `https://api.elections.kalshi.com/trade-api/v2` (no auth needed for
  market data), pulled **2026-06-14 ~19:20 UTC**. Books via `/markets/{t}/orderbook` (field
  `orderbook_fp`: `yes_dollars`/`no_dollars` = resting bids, price+size in $); tape via
  `/markets/trades`.
- **Inventory N:** 253 crypto series enumerated from `/series?category=Crypto`.
- **Box backtest N:** 20 settled `KXBTCD` hourly events (2026-06-13 20:00 -> 2026-06-14 19:00 UTC),
  ATM strike per event, full public trade tape (1.7k-8.1k prints/event, 175k-886k contracts/event).
- **Live book sample:** 10 ATM strikes across the 3 soonest live hourly windows.
- **Costs:** MAKER fills are ~fee-free (post-only) per FEES.md — identical treatment to the live 15M
  box. The +1-2c locked box margin is net of maker fees. Only CROSSING to complete a strand pays the
  crypto taker fee (ceil(M*P*(1-P)), M~0.07-0.14, max ~2-3.5c near P=0.5) — same as 15M.

Scripts (committed): `kalshi_tenor_sample.py` (inventory + book screen),
`kalshi_tenor_atm.py` (ATM two-sided strikes + flow), `kalshi_hourly_box_backtest.py` (box replay).

---

## 1. Crypto-market inventory (BTC tenors + box-relevant structures)

253 active crypto series exist. The box-relevant ones (single-strike up/down, or a bracket/ladder
that admits a box/butterfly) for **BTC** are:

| Series | Title | Tenor | Structure | Windows/day | Box mechanism |
|---|---|---|---|---|---|
| **KXBTC15M** | BTC price up/down | 15-min | **1 strike/window**, "greater_or_equal" vs ref | **96** | buy YES + buy NO on ONE ticker (LIVE) |
| **KXBTCD** | BTC price Above/below | **hourly** | ~188-strike "greater" LADDER | **24** | box on the ATM strike (buy YES + buy NO) |
| KXBTC | Bitcoin range | hourly | ~188 "between" BRACKETS + greater/less | 24 | one bracket = a box-like instrument |
| BTCD / BTCD-B | Above/below | daily | ladder | ~1-2 | too few windows |
| KXBTCMAXD / KXBTCMINMON | one-touch max/min | daily/monthly | one-touch, NOT a binary up/down | n/a | no clean box |
| (non-BTC: KXETHD/KXSOLD/KXXRPD hourly, KXETH15M etc.) | — | — | — | — | **CLOSED** (see §4) |

**Live book / depth / spread at touch (sampled 2026-06-14 19:20 UTC):**

- **KXBTC15M** (live window, 11min to close): YESbid 0.74 ($21) / NObid 0.25 ($1398), **spr 1c**,
  maker box cost 0.99 -> **locked +1c**. Min fillable $21 — the known fill/size cap.
- **KXBTCD** ATM strike (T63799.99, BTC ~$63.8k, 40min to close): YESbid 0.50 ($2363) / NObid 0.49
  ($897), **spr 1c**, maker box -> **locked +1c**. Across 10 live ATM strikes: spread median 1.5c
  (1-2c), locked box margin median **+1.5c**. Queue depth at touch: **$14,469 YES / $4,742 NO**.
- **KXBTC** (hourly "between" brackets) ATM: spreads **2-6c**, depth **$1-20**. Thin and wide.

---

## 2. Box-viability per candidate

### KXBTCD (hourly above/below ladder) — VIABLE ✅
- **Spread / margin:** 1c touch spread on the ATM strike, identical to 15M. Maker box (post YES bid +
  NO bid) locks +1c (median +1.5c). Fee-free maker, same as 15M.
- **Flow / fill:** the ATM strike is extremely liquid. In one settled hour (KXBTCD-26JUN1400,
  ATM T64499.99): **886,079 contracts / 8,107 trades over a 60-min span; 52% of volume (464k
  contracts) traded at 0.40-0.60 (ATM)** — ~7,700 contracts/min at the inside. Even queuing behind
  $14k of resting size, the inside turns over many times per hour, so a small maker box fills BOTH
  legs comfortably.
- **Strand:** the strand risk is LOWER than 15M, not higher. Strand happens when one leg fills and
  price then trends through the strike before the second leg fills. The hourly gives **4x the window
  (60 vs 15 min)** and far deeper, balanced two-sided ATM turnover for the second leg to fill.
  Backtest (20 settled hours, ATM strike, resting box at median price, honest fill = a taker prints
  at/through each posted bid): **20/20 boxes completed, 0 strands, mean +2.0c/box** (the 2c reflects
  median ~1.5-2c spread at ATM; conservative deploy target = +1c). The 100% completion is an upper
  bound (the model counts "any print at each bid over the hour"; it does not model losing the queue
  race), but it is directionally correct given 52% of volume is ATM and prints both sides thousands
  of times/hour. The realistic deploy assumption: completion rate high (>90%), occasional strand
  near settlement handled by the same cross-to-complete/hold logic as 15M.
- **NOTE — this contradicts CRYPTO_BINARY_MAP.md point 6** ("longer tenor = worse box"). That earlier
  finding tested the hourly *multi-strike butterfly/ladder-arb* (statically internally-consistent ->
  no arb). It did NOT test the **single-strike ATM up/down maker box** on KXBTCD, which behaves like a
  longer-window version of the 15M box and is genuinely liquid. The "longer tenor worse" law applies
  to the static-arb framing, not to the ATM spread-capture box.

### KXBTC (hourly "between" brackets) — NOT VIABLE ❌
- Each bracket is its own ~$100-wide payoff. ATM brackets show 2-6c spreads and $1-20 depth at touch.
  Wide spread + near-zero depth = no harvestable maker box. Skip.

### BTCD / daily — NOT VIABLE (capacity) ❌
- Daily above/below exists but only ~1-2 windows/day -> negligible incremental capacity even if liquid.

### Non-BTC at other tenors — STAY CLOSED ❌
- Hourly directional ladders exist for ETH (KXETHD), SOL (KXSOLD), XRP (KXXRPD), DOGE, etc. The
  non-BTC complex is CLOSED as a box at 15-min (NONBTC_EV.md: -EV, intrinsic adverse selection) and
  CRYPTO_BINARY_MAP.md already tested the hourly multi-strike ladder for ETH/SOL/XRP (-EV). The bar
  to revisit is a *materially better book* at the new tenor; the non-BTC hourly books are far thinner
  than KXBTCD (BTC carries the dominant Kalshi crypto flow). Not worth re-opening without a structural
  edge. KXBTCD is the only non-15M BTC candidate that clears the bar.

---

## 3. Incremental capacity

KXBTCD is **independent of KXBTC15M**: 24 hourly windows settle at the top of each hour (XX:00),
disjoint from the 96 quarter-hourly 15M settlements, on a different series/order book. So fills are
**additive, not competing for the same flow**.

Incremental $/day = windows/day x box_size/window x net_c/box:

| Box size/window | Incremental $/day (24 windows x size x 1c) |
|---|---|
| $50 | ~$12/day |
| $100 | ~$24/day |
| $200 | ~$48/day |

- **Conservative (small bankroll, $50/window): ~$12/day** — roughly **+50% to +100% on the 15M
  ceiling** ($10-27/day).
- **The hourly is LESS fill-rate-limited per window than the 15M** (886k vs much smaller per-window
  flow), so the binding constraint shifts from fill-rate toward **bankroll/queue position**. With more
  bankroll the hourly scales further than the 15M did before saturating — exactly the ceiling lift the
  goal asked for.

---

## 4. Verdict & deploy spec

**Deployable second crypto box market: `KXBTCD` (BTC hourly Above/below), on the ATM strike.**

- **Ticker pattern:** `KXBTCD-{YYMMMDDHH}-T{strike}` (e.g. `KXBTCD-26JUN1416-T63799.99`). Each hour
  the event is `KXBTCD-{YYMMMDDHH}`; pick the strike whose `floor_strike` is nearest the live BTC
  index (the strike whose touch sits closest to 0.50).
- **Param differences from the 15M box config:**
  1. **Strike selection:** 15M has 1 strike/window; KXBTCD has ~188 — the bot must SELECT the ATM
     strike each hour (floor nearest spot / mid nearest 0.5) and re-select if BTC drifts past a strike
     boundary (strikes are $100 apart, so re-center when |spot - chosen_floor| > ~$50).
  2. **Window length:** 60 min vs 15 min — re-quote/refresh cadence can be slower; more time for the
     second leg to fill before recentre.
  3. **Strike step:** $100 (linear_cent) — the chosen strike's price wanders within the hour; recentre
     to the new ATM strike rather than chasing a strike that has gone deep ITM/OTM.
  4. Same maker post-only box, same 1c spread, same fee-free maker treatment, same cross-to-complete
     /hold strand handling as 15M. Pair-gating (the 2% strand cap that made 15M +EV) should be ported
     unchanged as a safety, though strand frequency is empirically lower here.
- **Settlement:** CF Benchmarks BRTI 60-sec average at the top of the hour (per market rules) — same
  index family as 15M, so settlement/index handling carries over.

**Is 15-min BTC the only viable one? NO.** KXBTCD hourly ATM box is a real, independent, deployable
second market. KXBTC hourly brackets and all non-BTC tenors are NOT viable (thin/wide or already
-EV). The capacity question resolves to: **two BTC box markets — KXBTC15M (96 windows/day) +
KXBTCD hourly (24 windows/day) — with the hourly adding ~$12-48/day and scaling further on bankroll.**

### Caveats / forward-test before full trust
- The 100% backtest completion is an upper bound (no queue-race modeling). Forward-test KXBTCD with
  small size; confirm realized completion >90% and realized net >= +0.5c/box before scaling.
- Strand handling near settlement: the last few minutes of the hour can move fast like the 15M close;
  keep the cross-to-complete vs hold logic and pair-gate.
- The crypto taker multiplier M is uncertain (0.07-0.14); it only bites on crossed completions, which
  should be rare given ATM liquidity, but size the strand allowance for M=0.14.

*Generated 2026-06-14 from live Kalshi public API + 20-event hourly box replay.*
