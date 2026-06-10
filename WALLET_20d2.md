# Deep dive: 0x20d2309cd92b797ae7ca175ed828ed8a27fbe29d (the t=4.9 outlier)

> _Historical — reverse-engineering phase (concluded: a ≥95% wallet-clone is not achievable, see CAPTURE_REALITY.md). Kept for provenance. Current state: **README.md**._

The standout maker: **#1 risk-adjusted on BOTH BTC and ETH** (t≈4.9), **+3.5%/$ GROSS** (tape excludes
rebate), ~BTC-neutral. Pulled everything available (data-api `/trades`, `/activity`, `/positions`,
`/value`) and cross-referenced our **historical archive (April, months back)** and **prospective ticks
(June, last days)**. Tools: `wallet_deepdive.py`, `makers_scan/levers.py`, duckdb on `wallet_trades.parquet`.

## What it is
A **small-bankroll, high-velocity, cross-asset complete-set market maker.**
- **Scale:** portfolio **$426**, yet cycles **~$38k of trades + $12.7k of redeems in ~8h** (≈90× daily
  turnover on bankroll). Returns are high-% but modest absolute.
- **Velocity/breadth:** **~415 trades/hr**, **median 4 concurrent markets** (max 9) across **BTC/ETH/XRP/SOL**
  15-min Up/Down simultaneously. Inter-trade gap median 4s, 28% within 1s.
- **On-chain mechanic (`/activity`):** only **TRADE + REDEEM — NO split/merge.** It does **not** mint
  sets; it **buys both Up and Down on the open market and redeems balanced sets at resolution** (1 Up +
  1 Down → $1, no merge gas).

## The edge ("exploit")
**Complete-set accumulation at a discount, not classic spread.**
- Buys **both** outcomes in 404/441 markets; its **buy-VWAPs sum to ~$0.97** → **+3.1¢ discount per $1
  set, volume-weighted over 15,914 matched sets** (mean +2.8¢, median +3.5¢). That ~3% *is* the gross edge.
- **Spread-vs-consensus ≈ 0** (mean +0.0007/sh) → the edge is **not** buy-bid/sell-ask spread; it's the
  **combined complete-set discount** it assembles by absorbing two-sided flow on each leg over the window.
- **Not a pure arbitrage:** set-balance min(Up,Dn)/max = **0.36** (carries a directional residual), and it
  does **not** cherry-pick the cheaper leg (cheap-side buy fraction 0.48). So it's a **statistical
  complete-set-discount + roughly-neutral churn**, realized **+$3.12/market, 56% profitable** (34-market
  resolution sample). The high **t=4.9 comes from diversification** — many small consistent wins across
  ~4 uncorrelated concurrent markets — *plus* the 20% maker rebate (on top, not in our gross P&L).

**Verdict:** not a bug/exploit — it's **professional complete-set liquidity provision**: the market's
heavily one-sided, momentum-driven flow lets a patient both-sides buyer assemble $1 sets for ~$0.97,
then redeem risk-light at resolution. The "secret sauce" is the *combination*: complete-set discount ×
cross-asset diversification × HFT uptime × rebate.

## Cross-reference with OUR data
**Prospective (June, our real BTC spot, 24–28 overlapping tick windows):**
- BTC-momentum corr = **+0.06** (≈neutral) → confirms it is **not** taking BTC direction; the P&L is
  microstructural (set discount), consistent with the on-chain "buy-both + redeem" mechanic.

**Historical (April archive `wallet_trades.parquet`, ~2 months back, 6,156 of its trades, 287 markets):**
- Ran **~2,050 trades/day across ~95 markets/day**, every day — the *same* high-frequency operation.
- April Up-token realized spread vs own-VWAP = **+1.83¢/share** (genuine spread capture even on one leg).
- (April archive is Up-token-only, a fetch artifact, so the box premium isn't directly computable then —
  but the velocity/two-sided/every-market signature is identical to June.)
- **The edge is durable: the same wallet has been a top crypto-MM for ≥2 months.**

**Cohort persistence (who else survived April→June):**
- Persistent veterans: `0x20d2309cd9`, **`0x674887d1ac` (13,195 April trades!)**, `0x5e2b9261b0`, `0x75cc3b63a2`.
- Newer entrants (post-April), now top earners: `0xdf7930e89a` (current #1 by P&L), `0x5c932f5090`,
  `0x5d4aba8ad4`, `0xed89b210fa` → the maker field is **growing and competitive**; new bots out-scale
  veterans, consistent with the complete-set discount slowly being competed down.

## How WE replicate it (maps to existing roadmap)
1. **Buy-both-when-cheap, hold balanced to resolution, redeem** — MAKEREDGE #2 (complete-set inventory),
   but *without* minting: just accumulate both legs on the book when their sum is < $1 and let resolution
   pay the set. No split/merge gas. (Our `--box-arb` should add a "buy-both-and-hold-to-resolution" mode,
   not just mint-and-merge.)
2. **Run ~4 crypto assets concurrently** — `multi_market.py`; diversification is what turns a thin
   per-market edge into t≈4.9.
3. **High uptime + small clips** — confirmed again (clip ~22, every market). Latency/queue (#8) wins the
   both-sides fills that assemble the discounted set.
4. **Layer the 20% rebate on top** — it's pure addition to the set discount.

## Honest caveats
- `/trades` caps at ~3,500 / 8h and `/positions` shows only *current* open positions, so lifetime P&L
  isn't directly queryable; figures are from the rolling tape + the April archive snapshot.
- The April archive captured only the Up token (no box check then); the box edge is measured on June data.
- Tape P&L is gross of fees/rebate and has no maker/taker flag — magnitudes are directional, not exact.
