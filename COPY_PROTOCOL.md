# Copy protocol: how we replicate a target market-maker (and the honest limits)

This maps the requested copy-trading framework to what we've built and to what is *actually possible*
from available data. Read the boundary first — it changes the whole approach.

## The hard boundary (why "mirror their LIMIT orders" is not possible from public data)
Polymarket's public data (data-api, on-chain) exposes **FILLS** — executed trades — **not** other
wallets' **resting or cancelled LIMIT orders**. Open orders live off-chain in the CLOB operator and are
private to the maker until matched. So you **cannot** see a target's quotes before they fill, cannot
detect their cancels, and cannot "vote their orders into the book" ahead of them. The Bullpen CLI reads
the same on-chain/fills surface — it does not grant the operator's private order book of an arbitrary
wallet. **Anyone claiming pre-fill order-mirroring of a third-party wallet is mistaken about the data.**

**Consequence:** the faithful 100% copy is **RULE replication**, not order mirroring — reverse-engineer
the target's quoting rule from its fills (we did), then run that rule with **our own** quotes. We've
fully extracted `0x20d2309cd9`'s rule (WALLET_20d2.md); `copy_bot.py` runs it.

## What we built (maps to the requested steps)
| Requested step | Our implementation | Status |
|---|---|---|
| 1. Verify true post-Jan-2026 MM (two-side, rebate, active) | `mm_score.py` (rubric: 2-side balance, win 55-70%, conc, rebate/liq proxies); `wallet_tracker.py` (live value/activity, every 6h) | ✅ data-backed |
| 2. Pull target trades incl. order detail | `wallet_deepdive.py` + data-api `/trades`,`/activity`,`/positions`,`/value` (FILLS only — see boundary) | ✅ within data limits |
| 3. Extract exact order logic (price/size/outcome/timing) | strategy PROFILE in `copy_bot.py` (measured: both tokens, ~$6 clips, ~3-tk ladder, buy-set-discount, hold-to-resolution) | ✅ from fills |
| 4. Build replication bot | `copy_bot.py` (generates the quote set per the rule; DRY-RUN/log) + `live_trader.py` (guarded live placement scaffold) | ✅ dry-run; live=your machine |
| 5. MM nuances (iceberg, merge, multi-wallet, fee decay) | iceberg→tiny clips already; merge→we hold balanced sets to redeem (no merge); multi-wallet→`wallet_tracker` watch-list; fee-decay→`wallet-track.yml` drift monitor | ✅ partial |
| 6/8. Validate / runtime monitoring | `copy_live.py` prospective capture-vs-depth curve + reconciliation; fill-rate, two-side, hold-time all measured | ✅ read-only validation |
| Position multiplier / risk caps | `copy_bot.py`: `POSITION_MULTIPLIER` env, `clip_usd`, `max_per_market_usd` | ✅ |
| Auto-redeem | noted; on-chain, live-only (balanced sets redeem to $1, no merge gas) | ⚠️ live-only |

## The replicated rule (0x20d2309cd9), parameterized in `copy_bot.py`
- Markets: BTC/ETH/SOL/XRP × {5m,15m} (8 concurrent).
- Both tokens, two-sided ladder `depth_ticks` around each touch; clip ~$6 × `POSITION_MULTIPLIER`.
- Complete-set discipline: keep BID legs only while `bid_up+bid_dn ≤ buy_set_max` (the ~3¢ discount).
- Hold balanced sets to resolution → redeem for $1 (no merge). Caps: `max_per_market_usd`.

## Validation loop (the 95% goal), honestly defined
"Capture %" can only mean **does our rule's quote envelope cover where the target actually fills** (we
can't observe whether *our* resting order would win the queue — that needs live placement). `copy_live.py`
measures this prospectively as a **capture-vs-ladder-depth curve** (d=1,2,3,5,7) with an independent
**reconciliation** (we saw N% of their in-window trades). Tune `depth_ticks` / market set until the curve
reaches ≥95% at a faithful depth (their observed ~6 levels). Note: capture trivially → 100% as depth→∞,
so report the depth, not just the number — 95% at depth≈their-ladder is the real target.

## Live deployment (your machine — not this read-only sandbox)
Requires your key + order placement, which this environment forbids. On a co-located box (DEPLOY.md):
1. Fund a burner; `live_trader.py` style guards (`I_UNDERSTAND_REAL_MONEY=yes`).
2. Wire `copy_bot.quotes_for_market()` into `live_trader.place()` (post-only LIMIT for rebate eligibility).
3. WebSocket user-channel for own fills; auto-redeem on resolution; `POSITION_MULTIPLIER=0.05–0.1` to start.
4. Risk caps (`max_per_market_usd`, max total notional); JSON log every order/fill; monitor fill-rate,
   two-side balance, hold-time (<15m), drawdown.
5. Test tiny first; scale only after the live fill-rate ≈ the `copy_live.py` capture estimate.

## Honest profitability caveat
Even a perfect rule copy isn't guaranteed profitable: the target's edge is thin (~3¢/set, gross-of-
rebate) and **queue-position/latency bound** — without their speed/queue priority you get fewer of the
same fills. The rebate (20% maker) and breadth (4 assets) are what make it work at scale; replicate
those (DEPLOY.md co-location + `multi_market.py`) or the copy underperforms the original.
