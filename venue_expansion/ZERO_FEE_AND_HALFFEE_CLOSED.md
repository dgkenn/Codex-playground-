# Zero-fee and half-fee series: both closed without a study — 2026-10-28

Two of the four remaining leads died to direct checks rather than studies. Recording the checks
because the *reasons* are structural and they close the "find a cheaper fee regime" idea for good.

## The 12 zero-fee series: 0 of 200 markets have ANY resting order

The 2026-10-27 fee survey found 12 of 9,191 series with `fee_multiplier: 0` — **no fees at all**.
That is the one thing that would overturn the arithmetic which closed four studies (`ceil(7·p·(1−p))`
has a 1-cent floor per leg, so cheap contracts cannot pay for their own fee).

Checked directly (2026-10-28):

| series | markets | settled | books with resting depth |
|---|---:|---:|---:|
| `KXBTCY` | 28 | 0 | **0** |
| `KXETHY` | 18 | 0 | **0** |
| `KXGDPYEAR` | 154 | 0 | **0** |
| **total probed** | **200** | **1*** | **0** |

\* across all 12 series, exactly one settled market exists (in `KXGAMBLINGREPEAL`).

**Two independent kills:**

1. **No settled history** — all 12 series are long-dated annual/one-off contracts still `active`, so
   no backtest is possible at all.
2. **No resting orders** — `0 of 200` order books carry a single bid or ask at any depth. There is
   nothing to cross, nothing to take, and nobody to fill a resting quote.

**The explanation is the point:** the fee waiver is a **liquidity subsidy on markets that have no
liquidity.** These series are zero-fee *because* nobody trades them. A zero-fee edge cannot be
harvested without a counterparty, so the fee regime that would break the arithmetic is attached
precisely to the markets where no trade is possible.

## The 18 half-fee MLB series: the 0.5× multiplier cannot break the 1-cent floor

`fee_multiplier: 0.5` gives `ceil(3.5·p·(1−p))`. The maximum of `3.5·p·(1−p)` is `0.875` at `p=0.5`,
so **the half-fee rounds up to 1 cent at every single price.**

| p | full `ceil(7p(1−p))` | half `ceil(3.5p(1−p))` | saving |
|---|---|---|---|
| 0.01–0.15 | 1c | 1c | **0c** |
| 0.20–0.70 | 2c | 1c | 1c |
| 0.85–0.99 | 1c | 1c | **0c** |

So halving the coefficient saves **at most 1 cent, and only in the middle price band.** It saves
**nothing** in the cheap tail (p ≤ 0.17) or the expensive tail (p ≥ 0.83) — which is exactly where
every near-certain edge in this program has lived, and exactly where the fee consumed it.

**The binding constraint is the 1-cent quantization floor, not the coefficient.** No fee multiplier
above zero can break it. That is an arithmetic statement, so no study is warranted, and running one
would have burned a day to rediscover a rounding rule.

## What this leaves

Of the four leads open after `MAKER_FILL`:

| lead | status |
|---|---|
| Ladder arbitrage (`KXBTCD`/`KXBTC`, state-independent) | **registered, running** |
| Favourite-side maker (the untested half of the book) | **registered, running** |
| 12 zero-fee series | **closed above** — no history, no books |
| 18 half-fee MLB series | **closed above** — arithmetic, no study needed |
