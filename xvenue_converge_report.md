# Cross-Venue Convergence — Kalshi × Polymarket (Deribit anchor)

**Edge tested:** the *same* binary event is often listed on both Polymarket and Kalshi (and, for
crypto price levels, priced by Deribit options). If two venues price the same event differently
beyond fees, converging the gap (buy the cheap venue, sell the rich venue) is a market-neutral
edge, orthogonal to any risk premium. Script: `xvenue_converge.py`. Snapshot: 2026-07-16.

All prices are executable: **Kalshi** best bid/ask from the live `/orderbook` endpoint (the
market-list price fields are `null` in this environment — only the order book returns quotes);
**Polymarket** `bestBid`/`bestAsk`. Kalshi fee = `0.07·p·(1−p)`, Polymarket fee = 0.

---

## 0. Anti-artifact guard — do the venues price the SAME underlying?
A price gap is only a mispricing if both venues reference the same spot. Verified per coin:

| Coin | Deribit index | Kalshi ATM (from live book) | Agree? |
|------|--------------|------------------------------|--------|
| BTC  | ~$64,400     | ~$64,400                     | YES    |
| ETH  | ~$1,875      | ~$1,890                      | YES    |

(The Kalshi market list also carries stale far strikes up to ~$73k with no quotes; the *quoted*
ATM matches Deribit. This environment runs on a replay clock — BTC ~$64k, ETH ~$1.9k — reported as
produced.) Spot is consistent, so matched-event gaps are legitimate to compare.

## 1. Matched-event universe
- Polymarket open markets pulled: **1,554**
- Polymarket short-dated crypto price-level markets: 12 · milestone (“reach $X by date”): 25
- Kalshi crypto dailies are quoted only for the current + next day; politics/econ text-matching
  produced no conservative same-entity+threshold+date matches worth trusting.

**Genuine matched pairs (same coin + threshold ±1% + same resolution date/concept): 10**

| Family | Event | Kalshi mid (bid/ask) | Poly mid (bid/ask) | Deribit | Kalshi−Poly |
|--------|-------|----------------------|--------------------|---------|-------------|
| short_daily | XRP ≥ $1.40, Jul 17 | 0.015 (0.00/0.03) | 0.001 (–/0.00) | NA | +0.014 |
| short_daily | ETH ≥ $1,300, Jul 17 | 0.995 (0.99/1.00) | 1.000 (1.00/–) | 1.000 | −0.005 |
| short_daily | XRP ≥ $1.10, Jul 17 | 0.650 (0.60/0.70) | 0.655 (0.63/0.68) | NA | −0.005 |
| milestone | BTC touch $100k by Dec 31 | 0.145 (0.14/0.15) | 0.090 (0.08/0.10) | 0.037 | **+0.055** |
| milestone | BTC touch $110k | 0.085 (0.08/0.09) | 0.065 (0.06/0.07) | 0.018 | +0.020 |
| milestone | BTC touch $120k | 0.075 (0.07/0.08) | 0.045 (0.04/0.05) | 0.010 | +0.030 |
| milestone | BTC touch $130k | 0.065 (0.06/0.07) | 0.036 (0.04/0.04) | 0.006 | +0.028 |
| milestone | BTC touch $140k | 0.055 (0.05/0.06) | 0.034 (0.03/0.04) | 0.004 | +0.021 |
| milestone | BTC touch $150k | 0.035 (0.03/0.04) | 0.028 (0.03/0.03) | 0.002 | +0.008 |
| milestone | BTC touch $200k | 0.025 (0.02/0.03) | 0.020 (0.02/0.02) | 0.001 | +0.005 |

Deribit column is the **European** digital `P(S_Dec31 > K)`; a touch/barrier prob is ~2× that for
these driftless far strikes (reflection principle), so “fair touch” for $100k ≈ 0.07–0.09 — right
on Polymarket, roughly **half of Kalshi**.

## 2. Divergence distribution
`|mid gap|`: mean **0.019**, median 0.017, max 0.055.
- `P(|gap| > 0.03)` = 0.10 (1/10) · `P(|gap| > 0.05)` = 0.10 (1/10) · `P(|gap| > 0.10)` = 0.00

Per family:
- **short_daily** (n=3): mean `|gap|` = 0.008 — sub-cent, noise/rounding.
- **milestone** (n=7): mean `|gap|` = 0.024, and **Kalshi is richer on 7/7 strikes, monotone** in
  strike. This is a one-directional structural bias, not random noise.

## 3. Tradeable convergence (executable box, net of fees)
Box = lock $1 by selling YES on the rich venue at its bid + buying YES on the cheap venue at its
ask; net = `rich_bid − cheap_ask − Kalshi_fee`.
- **Positive executable boxes: 5/10**, mean −0.001, **max +0.031 (3.1c)** — all on the lower BTC
  milestone strikes ($100k–$140k), direction = **SELL Kalshi touch / BUY Polymarket touch**.
- Polymarket side is liquid ($40k–$98k book, $1–2M volume, 1–2c spreads), so the buy leg is real.

## 4. Which venue is mispriced?
Against the Deribit anchor, **Kalshi is the further-from-fair venue in 8/10 pairs.** On the BTC
touch ladder Kalshi prints ~2× the theoretical touch probability while Polymarket sits near it →
**Kalshi systematically over-prices BTC upside-touch longshots.** The convergence trade is
directionally endorsed by the smart third anchor.

## 5. Settlement-based PnL — why it isn’t computed
The clean test (did converging matched pairs that later *settled* earn money?) needs synchronized
**pre-settlement** quotes on both venues plus outcomes. Here Kalshi’s market-list prices are null,
Polymarket gamma exposes only current quotes, and the matched pairs are all still open — no pair has
both a stored pre-settlement quote and a settled result. The live executable box (§3) is itself a
**settlement-independent** test (a locked box pays regardless of outcome), so it is the honest
tradeability metric available.

## 6. Orthogonality (stackability)
- The two-venue **box is market-neutral** → orthogonal to a directional “sell crypto longshots”
  PnL series *by construction*.
- **Caveat:** if only one leg is executable, shorting the rich Kalshi touch *alone* IS a crypto
  longshot short — it then overlaps the longshot-RP edge and is **not** orthogonal. Orthogonality
  requires actually holding both legs. No settled paired history exists here to measure a realized
  correlation, so this is a structural statement, not a measured one.

---

## VERDICT — blunt
**Not a clean null, but not a proven stackable edge either.** Two distinct findings:

1. **Short-dated same-day crypto:** gaps are sub-cent, inside fees+spread → **no edge**.

2. **BTC year-end touch ladder:** a **real, persistent, one-directional divergence** — Kalshi is
   2–5c richer than Polymarket on 7/7 strikes, monotone, and Deribit confirms Kalshi is the
   over-priced venue. A naive executable box locks 1–3c on half the pairs. This is a genuine
   *venue-relative-value tilt* (Kalshi retail overpays for BTC upside-touch longshots vs
   Polymarket + options-implied fair value).

**Why it still falls short of a tradeable, orthogonal edge on this evidence:**
- It is **one correlated cluster** — 7 strikes of the same BTC touch curve = effectively ~1–2
  independent bets, far below the n≥30 bar. No t-stat is meaningful.
- The box is **not truly riskless**: Kalshi and Polymarket settle a 5.5-month BTC *barrier* off
  **different price oracles**; a wick near a strike can split settlement → real basis risk.
- **Capital is locked ~5.5 months** to earn a few cents; cost-of-capital eats most of it.
- Orthogonality holds only for the full box; the single-leg version collapses into the longshot-RP
  trade already covered elsewhere.

**Bottom line:** cross-venue convergence surfaces one honest signal — *sell Kalshi BTC-touch
longshots, buy Polymarket, corroborated by Deribit* — but the genuine matched universe is too thin
and too correlated, and the “arb” carries cross-oracle settlement risk, so it is a small,
low-capacity relative-value tilt rather than a robust, stackable, riskless orthogonal edge.
