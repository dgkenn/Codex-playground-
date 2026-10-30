# Who actually makes money on these markets — 2026-10-30

You said you don't believe this is the only efficient market in the world, and that people make money
here all the time. **Both are true.** I tested the cross-venue hypothesis you implied, it closed, and
in closing it the measurement finally made clear *who* is making money and why none of those seats is
available to an outside retail participant with a REST API.

## The cross-venue result

231 paired snapshots over 115 minutes at a 30-second cadence, 13 matched NFL games, 5 real
sportsbooks, **30,030 pairings**:

| | |
|---|---|
| fee-inclusive arbitrages | **0** |
| median gap (100% − combined cost) | **−4.73 pp** |
| best gap observed | −1.67 pp |
| observations within 1 pp of an arb | **0** |
| **best gap with Kalshi's fee set to zero** | **+0.04 pp** |

That last line is the finding. The venues don't merely fail to disagree *enough* — **they agree to
within 0.04 pp of the fee.** A total fee waiver would leave four hundredths of a percentage point,
which is nothing. This is not a transaction-cost result; it is a genuine efficiency result, and it is
the first one this program has measured *across* venues rather than within one.

The best single case: Tennessee YES at 14c + 1c fee + DraftKings Bengals −650 at 86.7c = **101.67c**.

## My spec had a defect that would have manufactured 9 arbs

I wrote "**7 distinct book_ids**" into the spec from my own probe. Two of them are not sportsbooks:
id 15 is **Consensus** and id 30 is the **Open** (opening line). Scored literally, all 7 ids produce
**9 "arbs" across 9 games, up to 10.6 pp — every one from the stale Open line**, which moved 0 of 28
times in the window against DraftKings' 4 of 28.

The agent caught it *before* collecting and scored only the 5 bettable books. **That is the fifth
defect in my own specifications caught by this apparatus**, after a 30-day price read as annual, the
wrong product category, the catalog undervalued, and the AnkiHub royalty that didn't exist.

It also caught a second fabrication: **BetMGM's NHL line had two teams' odds swapped** relative to
every other book, producing a **28.9 pp fake arb at 91,000 contracts.** A cross-book median filter
removed it, and removed zero NFL rows.

And the NHL "signal" was a stub: 104 episodes, all one game, a **50-contract** ask at 44c under a
107,000-contract ask at 50c — median edge 0.51 pp, median leg **$22**, and **0 of 95 survived the
60-second re-check.**

## So who is making money, and why not us

| who | how | why it isn't available here |
|---|---|---|
| **HFT participants** | taking two-leg ladder arbs at the **same microsecond** | measured; we are 3–6 orders of magnitude slower |
| **The books themselves** | collecting 4.25 pp of vig as the house | requires being the house |
| **Sharp bettors** | genuine handicapping edges, hedged across books | an information edge, and books limit them in 4–12 weeks |
| **Promo farmers** | harvesting one-sided subsidy, hedging on an exchange | **real, and bounded — see below** |
| **Market makers at scale** | spread capture with rebates and inventory | measured: adverse selection equals the spread |

You were right that money is made. The measurement says it is made from **subsidy** (promos), from
**speed** (microseconds), or from **being the house** (vig) — and in 57 studies not once from an
outsider pricing these contracts better than the market.

## The one path that survives, honestly bounded

**Promotional subsidy is not an edge in the market — it is a gift from a book's marketing budget**, and
it needs no venue disagreement at all. Kalshi is the ideal hedge leg precisely because an exchange
does not limit winners.

| | |
|---|---|
| ~10 books × $1,000 face × 65% realised | **≈$6,500, one time** |
| ongoing boosts and odds specials | **$200–600/month** |
| constraint | first-bet promos don't repeat; books limit winners in 4–12 weeks |

**That is real money and it is not $4,000/month recurring.** It is a few thousand up front and a few
hundred a month after, and it is active work, not passive.

## Honest limits of this kill

One 115-minute Friday pre-game window with no news shock I could identify. It kills the
pre-registered window, not the proposition that an arb has *never* existed. The things most likely to
produce one — a sharp injury move, a thin market, a book's limit error — are rare, fast, and small,
which is exactly the profile of the microsecond population we already measured being harvested by
somebody faster.

The one structural change that would reopen it: **Kalshi waiving or rebating the taker fee.** The
+0.04 pp zero-fee figure says even that only reaches breakeven — so not even that reopens it.
