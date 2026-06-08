# Reverse-engineering the winning 15-min crypto market-makers

**Method.** Pulled the wallet-attributed trade tape (Polymarket data-api, no keys) for **246 closed
BTC-Up/Down 15-min markets (~60h)**, 6,301 wallets. Per (wallet, market): settled P&L = cashflow +
inventory×resolution. Per wallet: total + risk-adjusted (t-stat of per-market P&L), two-sidedness
(maker proxy), clip size, inventory carried, intra-window timing, realized spread, and **momentum-vs-fade
cross-referenced against our own collected real BTC spot** (`gha_data` ticks, 24 overlapping windows).
Tools: `makers_scan.py`, `makers_fingerprint.py`. Caveat: the tape has **no maker/taker flag**, so P&L is
**gross of fees/rebates** — a real maker is +rebate (better), a taker is −fee (worse); two-sidedness is
the maker proxy. (Multi-asset ETH/SOL/XRP enrichment is running; insights below are the BTC sample.)

## The maker population is brutal
597 wallets qualify as makers (two-sided >0.3, ≥5 markets, clip <60). **Median P&L ≈ 0; only 48% are
profitable.** Median clip = **7 shares**, median two-sidedness 0.41. Market-making here is a thin,
queue-and-rebate grind that *most* lose — the edge lives in a small, identifiable minority.

## Top makers by total P&L (the ones that made the most)
```
   wallet        pnl    t  /1k    vol  mkts   trd 2sided clip  Δinv late
0xdf7930e89a   +1668  2.4 +45  36770  235  6079  0.49   11   74  .03
0x674887d1ac   +1426  3.0 +25  57800  245 17634  0.48    8   37  .04   <- in ALL 245 mkts, most trades
0x20d2309cd9    +947  4.9 +35  27222  245  2777  0.46   22   23  .10   <- best risk-adjusted earner
0x5e2b9261b0    +428  3.6 +34  12596  245  3638  0.47    6   22  .11
0x75cc3b63a2    +388  3.2 +30  12949  245  3585  0.48    6   22  .11
0x5d4aba8ad4    +366  2.2 +37   9969  244  2230  0.47    8   17  .17
0xed89b210fa    +320  1.9 +36   8890  241  2093  0.46    8   18  .17
0x5c932f5090    +282  3.3 +21  13306  128  1713  0.45   15   16  .09
```
**Common signature:** tiny clips (6–22 sh), ~50/50 two-sided, present in **nearly every market**,
small inventory (Δinv 17–74), and trade **throughout the window, not at the close** (late-fraction
0.03–0.17). High-frequency, low-inventory, continuous two-sided quoting. The single biggest earner is
the one with the **most trades** (674887: 17,634) — volume × thin edge, i.e. **rebate-share scale**.

## Risk-adjusted leaders (t-stat of per-market P&L, ≥10 mkts)
`0x20d2309cd9 t=4.9 (+947)` is the standout — high P&L *and* high consistency. Then `0x5e2b9261 t=3.6`,
`0x5c932f50 t=3.3`, `0x75cc3b63 t=3.2`, `0x674887d1 t=3.0`. These are the wallets to emulate.

## Strategy archetypes (fingerprint + BTC cross-ref)
Cross-referencing each top maker's signed direction against **real prior-45s BTC moves** (our spot):

| wallet | btc_mom | realized spread | archetype |
|---|---|---|---|
| 0x674887d1 | **+0.01** (1263 tr) | ~0 | **Pure BTC-neutral MM** — pays no attention to BTC; harvests spread+rebate at scale |
| 0x20d2309c | +0.06 | +1.9¢ | near-neutral MM, slightly larger clips |
| 0x75cc3b63 | +0.08 | −9¢ | near-neutral, high-freq |
| 0xdf7930e8 | +0.14 | −4¢ | mild momentum lean |
| 0x5e2b9261 | **+0.30** | −9¢ | **Momentum** — leans into BTC moves (not a spread-capturer; negative realized spread) |
| 0x5c932f50 | **−0.17** | +3.6¢ | **Fade / liquidity-into-moves** — sells the side BTC is running toward, captures spread |

Plus a cohort of **low-volume pure passive MMs** (clip 1–6, two-sided ~0.5) that capture a clean
**+10 to +27¢/share realized spread** but in few markets/small size — the "textbook" MM, lower total $.
Archetype tally across the selected makers: ~neutral spread-capture and fade are the most common; a
minority run momentum; very few concentrate at expiry.

## Contrast: the directional one-siders make the most *gross* — but it's a different game
```
0x724db3c436  +8323  2sided 0.00  Δinv 636   |  0xeebde7a0e0 +3730  t4.9  32510 trades  Δinv 914
0xb27bc932bf  +4817  t3.0 21853 trades        |  0x9d57c42e84 +1541  t3.3  Δinv 48
```
These earn 2–5× the top makers but are **100% one-sided**, carry **huge inventory** (Δinv 160–910 =
big directional bets held to resolution), and — being aggressors — **pay the taker fee** the tape
doesn't show (peak ~3.15% at p=0.5). Their gross is inflated; net-of-fee is much thinner, and the risk
is directional. This matches our own finding that offensive BTC-following **loses to the fee** — their
visible profit is pre-fee and may not survive it.

## Cross-asset confirmation (ETH) — the winners run ONE strategy across assets
On 120 ETH 15-min markets (1,885 wallets, 80 makers), the **top ETH makers are the same wallets as BTC**:
`0x20d2309cd9` is **#1 on both** (BTC t=4.9 / ETH t=4.7, +445), alongside `0x5d4aba8ad4`, `0x75cc3b63a2`,
`0x5e2b9261b0`, `0xed89b210fa` — each with the **same fingerprint** (6–17-share clips, two-sided ~0.46,
present in ~all 120 ETH markets, low late-fraction). The winning bots aren't BTC-specialists; they run
**one tiny-clip two-sided book simultaneously across assets** — direct confirmation of the breadth lever
(#5): the edge generalizes BTC→ETH and the same code harvests both. (SOL/XRP enrichment ongoing.)

## Cross-reference with OUR research — what it confirms and what's new
**Confirms our edges:**
- **Tiny clips + delta-neutral wins.** The whole winning cohort runs 6–22-share two-sided clips with
  small inventory — exactly our cap25 / tight-skew result.
- **Avoid the late window.** Winners trade *throughout*, with late-fractions 0.03–0.17; they do **not**
  pile in at expiry — our `late_gate` finding (last-2-min fills are toxic), confirmed in the wild.
- **The standalone edge is spread+rebate, not direction.** The biggest, most-consistent maker
  (674887) is **BTC-neutral (btc_mom +0.01)** — direct external confirmation of our conclusion that
  there's no directional alpha; the seat is microstructural (spread × queue × rebate), and it scales
  with **volume/throughput** (→ our breadth lever #5, and the rebate-tier flywheel #6).
**New / tensions to test (with our OOS discipline):**
- **A momentum lean coexists with winning** (5e2b92 +0.30, df7930 +0.14). But our OOS tests found no
  robust directional alpha, so treat this as a *hypothesis*, not proven edge — over one ~60h sample it
  could be inventory-offloading (lean to the side you need to shed), regime, or survivorship. Worth an
  OOS test of a "lean toward the BTC move when reducing inventory" rule.
- **Fade makers profit by NOT pulling** (5c932f −0.17 btc_mom, +3.6¢ spread): they *provide* liquidity
  into BTC moves and get paid the spread, where our `micro_gate`/`spot_react` would *pull*. Tension:
  pulling avoids toxicity but forgoes the spread+rebate the faders capture. Likely resolution: pull on
  **large/fast** moves (toxic) but **stay and fade small** ones — a graded gate, not binary. Testable
  as a variant.

## Actionable tweaks for our bot
1. **Be in every market, all the time, tiny & two-sided** — the top earner is simply the highest-uptime,
   highest-trade-count, smallest-clip two-sided quoter (rebate-share scale). Prioritize uptime + breadth
   (#5) + latency/queue (#8) over cleverness.
2. **Keep clips ~6–10 shares and inventory small** — matches the entire winning cohort; confirms cap25.
3. **Don't quote the last ~2 min the way you quote mid-window** — winners de-emphasize the close.
4. **Graded toxicity gate, not binary** — fade (stay and capture spread on) *small* BTC moves; pull only
   on large/fast ones. Test a `micro_gate` with a magnitude threshold vs the current pull-on-any.
5. **A BTC-neutral spread+rebate book is a proven positive standalone** (674887) — validates running the
   maker purely for spread+rebate without a directional view; size it up via hedging (#1) + breadth.
6. **Watch list:** `0x20d2309cd9` (t4.9), `0x674887d1ac` (the workhorse), `0x5e2b9261b0`, `0x5c932f5090` —
   re-pull their tapes periodically to track how their behavior adapts (e.g. after fee changes).
