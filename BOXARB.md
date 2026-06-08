# Direction-free / fee-free / risk-free bets on Polymarket: the complete-set "box"

A complete set (UP + DOWN, or YES + NO) of a Polymarket binary always redeems for **exactly $1**.
That identity is the source of every "risk-free / direction-free / fee-free" claim. This note settles,
with our own live data + the literature, whether such a bet actually exists in the **BTC 15-minute**
market we trade. **Short answer: not at the taker level (it's been competed away + fee'd out), and at
the maker level the "box premium" is just the bid-ask spread we already harvest.** The real free-box
money the literature documents lives in *illiquid / longshot / multi-outcome* markets — a different game.

## 1. There are TWO box premiums, and conflating them overstates the edge

In a 1-tick market the touch satisfies `mid_up + mid_dn ≈ 1`, so:

| You do | You receive / pay | "premium" | What it really is |
|---|---|---|---|
| **REST sell both** (maker, get lifted) | `ask_up + ask_dn` | `ask_up+ask_dn − 1` | the **round-trip MM spread** (`≈ +1 tick`) |
| **REST buy both** (maker, get hit) | `bid_up + bid_dn` | `1 − bid_up−bid_dn` | the **MM spread** (`≈ +1 tick`) |
| **TAKE sell both** (cross, hit bids) | `bid_up + bid_dn` | `bid_up+bid_dn − 1` | **genuinely free** if `>0` |
| **TAKE buy both** (cross, lift asks) | `ask_up + ask_dn` | `1 − ask_up−ask_dn` | **genuinely free** if `>0` |

The **maker** box is risk-free *only if both legs fill*; if one fills you hold a directional leg
(**legging risk**). It is mechanically `≈ +1 tick` because asks sit a tick above mids that sum to ~1.
**It is not new money — it is the spread, bound by queue position + adverse selection + the 20% maker
rebate, i.e. exactly the seat the rest of this repo studies.** Only the **taker** box (crossing both
sides at once) is a true free arb, and only when its premium is `> 0`.

`box_probe.py` originally measured only the *maker* convention and labeled it "RISK-FREE" — that was
the source of the earlier overstated "97–98% box premium / ~1¢ free." Corrected below.

## 2. Live measurement (our market, this repo)

`box_probe.py` (corrected), BTC 15-min, 56 touch samples, tick = 0.01:

```
MAKER box (the MM spread; risk-free only if both legs fill):
  rest-sell-both (ask_up+ask_dn-1): mean +0.0107  median +0.0100  %>0 98%  max +0.0300
  rest-buy-both  (1-bid_up-bid_dn): mean +0.0093  median +0.0100  %>0 95%  max +0.0200
TAKER box (the only genuinely free line):
  hit-both  (bid_up+bid_dn-1):      mean -0.0093  median -0.0100  %>0  4%  max +0.0100
  lift-both (1-ask_up-ask_dn):      mean -0.0107  median -0.0100  %>0  0%  max  0.0000
```

`live_trader.py --box-arb` dry-run independently shows the maker box pinned at **exactly +0.0100 every
poll** (`ask_up+ask_dn = 1.01`, `bid_up+bid_dn = 0.99`) and the `FREE_*` taker alerts never firing.

**Read:** the maker box ≡ the 1-tick spread (95–98% of the time, by construction). The genuinely
risk-free **taker** box is essentially **absent** — present ~2% of samples, at *exactly* one tick (a
momentary locked/crossed book), and the buy side (`lift-both`) **never** went positive. There is no
standing risk-free/direction-free/fee-free bet at the touch in liquid BTC 15-min.

## 3. What the literature says (and why it doesn't contradict §2)

- **Complete-set arb is real and large — in *illiquid* markets.** "Unravelling the Probabilistic
  Forest" (arXiv:2508.03474) finds **$10.6M** of single-condition (YES+NO) arbitrage extracted on
  Polymarket (Apr-24→Apr-25), but the **median mispriced complete set traded near $0.40** (a 60¢/dollar
  gap) and bids **clustered over ~1-hour windows** — i.e. deep, slow, *longshot* markets nobody is
  making, not a liquid book. 7,051 of 17,218 conditions had ≥1 opportunity.
- **In liquid markets it's a latency race that's over.** Opportunity duration has fallen to **~2.7s**
  (from 12.3s in 2024) with **~73% of profit captured by sub-100ms bots**. A 15-min crypto book is the
  *most* contested venue; the touch is efficient (our §2 data).
- **Polymarket explicitly fee'd out the 15-min box.** The **dynamic taker fee** on 15-min crypto was
  introduced *specifically to curb latency arbitrage*; it **peaks at p≈0.50 (~3.15% on a 50¢ contract),
  exactly where box/latency arb lived**, and tapers to the extremes. Any taker box smaller than that
  fee is unprofitable by design — and §2 shows the gross taker box is ≤ 1 tick anyway.
- **Multi-outcome (negRisk) is where the capital-efficient box still pays — but that's not our market.**
  NegRisk "market rebalancing" (sum of N≥3 mutually-exclusive YES ≠ 1, captured via the `convert`
  adapter) generated **~$28.6M extracted, 73% of arb profit from 8.6% of opportunities (≈29× capital
  efficiency)**. Our BTC Up/Down is a plain 2-outcome binary, so the negRisk `convert` edge does not
  apply; only the simple sum-to-one box does, and §2 shows it's gone here.
- **Maker economics confirm §1.** Polymarket maker rebate = **20% of taker fees (crypto)**, paid daily
  in pUSD, pro-rata to *your filled maker volume's fee-equivalent*, $1 min, **no spread/size/uptime
  gate**. So the maker box pays the spread **+** a 20% rebate kicker — which is precisely the edge we
  already model (rebate + spread − adverse selection), not a separate free lunch.

## 4. Verdict

For the **BTC 15-minute** market:

1. **No standing risk-free/direction-free/fee-free taker bet exists.** The touch is efficient; the gross
   taker box is ≤ 1 tick and appears ~2% of the time; the dynamic fee (peak ~3.15% at p=0.5) dwarfs it;
   sub-100ms bots take the rare crumbs. This is now empirically nailed (§2) and matches the literature.
2. **The "box premium" is the spread.** The maker complete-set box ≡ `+1 tick`, captured only by being
   the resting quote on *both* legs and getting filled on *both* — i.e. delta-neutral market making with
   minted inventory. It is risk-free only if both legs fill (legging risk) and its economics are
   identical to our existing maker seat: **spread + 20% rebate, bounded by queue position and
   adverse-selection (the micro-gate edge)**. `live_trader.py --box-arb` implements this honestly as a
   dry-run MM-with-minted-inventory mode (not a free arb), and now logs `FREE_*` only if a true taker box
   ever appears.
3. **The real free-box money is in a different market.** Illiquid / longshot single-condition sets
   (median $0.40, hour-long persistence) and negRisk multi-outcome rebalancing (29× capital efficiency)
   are genuinely capturable but require on-chain split/merge, gas, idle capital, and patience — and live
   *outside* the liquid 15-min crypto book. If we ever want a true risk-free line, that is where to fish,
   not here. (Track A of the standing plan already points at low/zero-fee, higher-inefficiency markets.)

## 5. Instrumentation added (so the GHA tape settles this at scale, not just a 56-sample probe)

- `shadow_compare.py` now logs four box fields on **every paper fill**: `box_ask`, `box_bid` (maker
  spread) and **`box_sell_tk` = bid_up+bid_dn−1, `box_buy_tk` = 1−ask_up−ask_dn** (the genuinely free
  taker box). If `box_sell_tk` or `box_buy_tk` is ever persistently `>0` across the live tape, that is a
  real free arb and we revisit; the prior is they hover at `−1 tick`.
- `box_probe.py` corrected to report maker vs taker conventions separately (no more "RISK-FREE" on the
  spread).
- `live_trader.py --box-arb` emits a `FREE_sell_taker` / `FREE_buy_taker` alert whenever a true taker box
  appears, distinct from the `sell_box`/`buy_box` maker-spread harvest it posts.
