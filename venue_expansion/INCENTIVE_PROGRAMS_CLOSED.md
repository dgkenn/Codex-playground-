# Kalshi incentive programs: closed on structure — 2026-10-29

The liquidity/volume incentive line was the last **non-trading** revenue idea in the program, and the
only one where the 1-cent fee floor does not apply (a rebate pays whether or not your trade has
edge). `FORWARD_DATA_2026-09-30.md` recorded it as **"expired, not refuted — it was never tested."**
It is now refuted on structure, and my earlier record needs two corrections.

## Corrections to my own record

1. **The LIP window did not simply lapse on 2026-09-01.** The 15 July 2026 CFTC filing sets the end
   at the *earlier* of 2026-09-01, **2027-01-01**, or an earlier Kalshi amendment/termination, and a
   secondary source reports amended terms effective 2026-07-30 with a 2027-01-01 end. So the program
   may still be live. I wrote it off too early.
2. **The program reported as terminating is the Volume Incentive Program, not the LIP.** They are
   distinct, and my first reading of the press coverage conflated them. The VIP (launched March 2023)
   is being ended "no earlier than Oct. 13" per Kalshi's CFTC filing.
3. **The wash-trading allegations are about ETH perpetual futures, not the incentive program.** The
   CFTC was reported to be examining ~$5,500 repeated trades that accounted for >$5bn of ETH perps
   volume against ~$3.1m open interest on ~$539m daily volume. Kalshi says it is not under
   investigation. The termination "comes amid reported regulatory scrutiny," which is not the same as
   traders exploiting the rebate, and I should not have implied it was.

## Why both programs are closed for this operator — structure, not arithmetic

I could **not** read the exact LIP figures: the CFTC filing is image-only and has no extractable
prose. What is readable are the formula labels, and they are enough:

```
Payout(user)  ≈  Time Period Liquidity Provider Score(user) × Time Period Reward
Score(bid)    =  DiscountFactor^max(ReferencePrice − Price(bid), 0) × Size(bid)
                 ... each bid normalised against all qualifying bids
scaling       =  (nonexcluded Snapshots) / (Total Snapshots)
```

And the VIP pays "from reward pools based on their share of eligible volume."

**Both are pro-rata shares of a fixed pot, not per-contract rebates.** Three consequences, each
independently disqualifying here:

1. **Income depends on competition, not on edge.** `Score(user) / Σ Scores × Reward`. A sophisticated
   participant posting size drives every other share toward zero. Nothing about our analysis improves
   our share.
2. **The score is proportional to `Size(bid)` — it is capital-weighted, not skill-weighted.** The
   standing constraint on this account is small capital (the registered canary is ≤$100 at risk). A
   pot divided by size is the one payoff structure that explicitly cannot be won from a small base.
3. **`DiscountFactor^distance-from-reference` forces tight quotes** — which is precisely the regime
   where this program has now *measured* adverse selection running against the maker in **12 of 12
   cells** on both sides of the book (`MAKER_FILL`, `FAVOURITE_MAKER`). The rebate is paid for taking
   exactly the exposure we measured to be costly, and the pot share is diluted by whoever else is
   willing to take it.

## The venue describes our own measurement

Kalshi's explanation of the repeated perps prints is **"market makers posting fixed quotes that faster
traders hit."**

That is, in the venue's own words, the mechanism `MAKER_FILL` and `FAVOURITE_MAKER` quantified
(fill-conditional loss ratios 1.1–2.3), and it is consistent with `ARBITRAGE_CLOSED.md` finding
two-leg takes at the **same microsecond**. Independent corroboration from the exchange that the
resting-quote side of this book is systematically picked off by faster participants.

## Verdict

**Closed.** Not "expired" this time — refuted on payoff structure. An incentive pot that is
capital-weighted, competition-diluted, and conditioned on quoting tight against measurably faster
traders is not a small-capital revenue line, whichever end date applies.

**Honest limit of this closure:** it rests on the formula's *structure* plus the pro-rata description,
not on the exact discount factor, reference-price rule, pot size, or per-trader cap, none of which I
could read. If the operator can obtain the current terms from their Kalshi account (the filing says
eligibility and a schedule of target sizes and rewards are marked **on each market page**, though no
such field is exposed on the public API's market records — checked 2026-10-29), the arithmetic is
worth one re-check against the measured adverse-selection cost. I would expect it to confirm the
above rather than overturn it.

## Incidental discovery, worth more than this closure

Open-market records **do** expose `yes_bid_size_fp` and `yes_ask_size_fp` — **live top-of-book depth**.
Every maker and arbitrage study in this repo explicitly could not measure size and had to assume a
queue position (`N ∈ {25, 100}` contracts resting ahead). `FAVOURITE_MAKER_REVISIT.md` names queue
position as the decisive remaining unknown.

These fields are **live only** — settled markets expose candlesticks, which carry no depth — so
closing that gap requires forward snapshot collection, not a backfill. Recorded here as the concrete
input the revisit needs.
