# CROSS-VENUE ARBITRAGE — pre-registered spec (REGISTERED 2026-10-30, before any snapshot is scored)

## Why this exists: the operator was right and I had a specific blind spot

Fifty-six studies tested two things — whether I could **predict better than the market**, and whether
I could **make markets**. Both closed. I never tested whether Kalshi's prices differ from the
**sportsbook market**, which is far larger, demonstrably less efficient, and where **87% of Kalshi's
$39.7bn annual volume** sits. I dismissed cross-venue work because Polymarket is geo-blocked and never
asked the next question. That was a real gap, not a general efficiency finding.

## Correcting the published analyst comparison

Citizens JMP tracked NFL Week 1 and Week 4 implied vig: **Kalshi 4.28%, FanDuel 4.41%, DraftKings
4.47%** on straight bets, and reported Kalshi as cheaper.

**That compares the wrong two numbers.** Kalshi's figure is its **spread**; its fee is charged **on
top**. A sportsbook's margin is **inside the line** with no separate fee. Using the fee formula
verified in this repo, `ceil(7·p·(1−p))`:

| Kalshi price | fee | fee as % of stake | Kalshi all-in | vs book 4.47% |
|---:|---:|---:|---:|---|
| 50c | 2c | 4.0% | **8.3%** | book cheaper |
| 70c | 2c | 2.9% | 7.1% | book cheaper |
| 85c | 1c | 1.2% | 5.5% | book cheaper |
| 95c | 1c | **1.1%** | **5.3%** | book cheaper |

**At the money Kalshi is roughly 2× more expensive than the headline implies.** But the fee is
**quantized at 1 cent**, so as a fraction of stake it collapses on favourites — the same 1c floor that
killed every cheap-contract strategy in this program barely bites on expensive ones.

## Hypothesis

A two-leg position — **buy YES on Kalshi at the ask, bet the opposing side at a sportsbook** — crosses
only *one* spread. It is a true arbitrage iff:

```
kalshi_ask + kalshi_fee + book_implied_prob(other side)  <  1.00
```

Since the book's own vig puts roughly 2.2% on its side, the venues must **disagree on the true
probability by about 3.2% (at favourites) to 4.2% (at the money)** before an arb exists. Whether that
happens often enough, and with enough size, is an empirical question nobody in this repo has measured.

## Data — all verified reachable today, unauthenticated

- **Kalshi**: `GET /markets?series_ticker=KXNFLGAME&status=open` carries `yes_bid_dollars`,
  `yes_ask_dollars` **and `yes_bid_size_fp`/`yes_ask_size_fp`**. This is the **first time in this
  program that real top-of-book depth is available** — every maker study had to assume a queue.
- **Sportsbooks**: `GET https://api.actionnetwork.com/web/v2/scoreboard/nfl` returns per-book
  moneylines for every game. Verified: **7 distinct `book_id`s** across 14 games, free, no key.
- **Fee**: `ceil(7·p·(1−p))` cents at the crossing price, `fee_multiplier` 1 on sports series unless
  the series record says otherwise — check each series, since 18 MLB series carry 0.5.

## Design — frozen

- **Universe**: all `KXNFLGAME` open markets matchable to an Action Network game by team pair. Report
  every unmatched market and why.
- **Snapshots**: paired Kalshi + Action Network pulls **within 60 seconds of each other**, repeated on
  a fixed cadence for the measurement window. A pair separated by more than 60s is **discarded, not
  used** — stale legs are how an arb study fabricates results.
- **Direction**: for each game and each book, evaluate **both** pairings (Kalshi home + book away, and
  Kalshi away + book home).
- **Odds conversion, frozen**: American `o ≥ 0` → `100/(o+100)`; `o < 0` → `−o/(−o+100)`. No
  de-vigging — the book's posted price is what you actually pay.
- **Executable only**: Kalshi `yes_ask` for buying. **Never the bid, never the mid.** Assert in code.
- **Size**: cap each opportunity at the Kalshi ask size and report the dollar size, not just the
  percentage. An arb of 0.8% on 3 contracts is noise.

## PASS / KILL — frozen now

**PASS** requires ALL:
1. **≥ 20 fee-inclusive arbitrage instances** (combined cost < 100%) across **≥ 10 distinct games**
2. median arb **≥ 1.0%** of stake after Kalshi's fee
3. median executable size **≥ $100** at the Kalshi leg's ask size
4. instances are **not concentrated** in one book or one game (no single book > 50%)
5. **≥ 50% survive a 60-second re-check** — an arb that vanishes before you can place two legs is not
   an arb

**KILL** if zero fee-inclusive instances occur across the window, or if fewer than 10% survive the
re-check.

**Anything else → INSUFFICIENT.**

## Mandatory anchors

- **(a) Report the gap distribution, not just the count.** Every pairing's `100% − combined cost`,
  so a near-miss population is visible even on a KILL. This is the deliverable either way.
- **(b) Simultaneity.** Log both legs' fetch timestamps and discard pairs > 60s apart.
- **(c) No mid, no bid.** AST scan, with a negative control on a doctored copy that must raise.
- **(d) Fee provenance.** Confirm the series' `fee_type` and `fee_multiplier` from the API rather than
  assuming 1.
- **(e) Size reported in dollars** at every stage, capped by the Kalshi ask size.

## What this spec explicitly does not claim

Sportsbooks **limit or ban winning arbitrageurs within roughly 4–12 weeks** — a vendor-sourced figure,
so treat it as directional. An exchange does not. So even a PASS describes an edge with a **finite
per-account lifespan**, and the honest framing is that Kalshi is the durable **hedge leg**, not the
source of edge.

Separately and outside this spec: **promotional subsidy** (first-bet-safe, profit boosts, deposit
matches) is a one-sided gift that needs **no venue disagreement at all**, and Kalshi is the ideal hedge
venue because it does not limit winners. Rough arithmetic — 10 books × $1,000 face × 65% realised ≈
**$6,500 one-time**, then **$200–600/month** in boosts. That is real money and it is **not $4,000/month
recurring**, because first-bet promos do not repeat and boosts are capped by limiting.

No bar in this document may move after 2026-10-30.
