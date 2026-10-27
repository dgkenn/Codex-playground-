# Weather is closed — 2026-10-27

47 pre-registered studies. This document states why no further weather study should be run, in the
specific form that makes it a structural claim rather than a tired one.

## The last study, and why it is the one that settles it

`BOUND_RESOLUTION_SPEC.md` tested the strongest version of the idea this program ever had:

- a signal built on **the settlement source's own field** (NWS's METAR 6-hour max/min remark groups,
  which the Daily Climate Report is built from and checked against),
- **provably correct** rather than probabilistically inferred — a monotone bound, where once the
  recorded max exceeds a rung's cap the rung cannot win,
- available a **median of 8.1 hours before close** (p10 307 min, p90 669 min).

Result, on **100% candle coverage** of all 6,231 fired tickers (not a sample):

| | measured | bar |
|---|---|---|
| bound violations | **1 in 2,037** station-days (0.049%) | — |
| **false locks** | **0 of 2,850 fires** (Wilson UB 0.13%) | ≤2%, UB ≤5% |
| priced entries | **8** of 2,850 | n ≥ 100 |
| **untradeable** | **99.72%** | ≤70% |

**The signal is perfect and the trade does not exist.** At the first candle after signal+10 min the
**YES bid is already 0 on 2,779 of 2,850 fires (97.5%)**, so the NO costs 100c and cannot be bought
at ≤98c. Verdict **KILL** by the letter of the frozen rule — but its evidential content is not
"EV is negative"; it is "the population is ~99.7% unbuyable."

The caveat that cannot rescue it: 69 fires (2.4%) have no candle row after the signal, so a quiet
standing bid could in principle hide there. **Even if every one were tradeable, untradeable would
still be ≥97.3%.**

## The structural finding: the market forecasts, we observed

This is the sentence the whole program was missing.

We spent 47 studies making observation **faster, better-sourced, and provably correct.** The market
had pushed those rungs to a zero bid **eight hours before** the observation that proves them dead was
published. A 6-hour METAR group is a *lagged digest* of temperatures the market had already priced
from live data — and more than that, from forecasts.

Anchor (e) makes the point even sharper: against the deployed rule on a 1-minute feed, **67% of
these fires are on rungs the deployed rule also locks, and it locks 879 of them a median of 140
minutes earlier.** Our newest, most authoritative signal is *slower* than the one we already had.

So the failure was never latency, feed quality, parameter choice, or execution. **It is that the
price of a weather contract is a forecast, and no amount of observation beats a forecast to a
conclusion that a forecast reached first.** That holds at any latency, for any observation-based
rule, permanently. It is not an empirical result about this sample; it is a statement about what
these markets price.

## Three routes to an accurate signal, all unbuyable

| route | accuracy | untradeable |
|---|---|---|
| never-arrival, wide gap (#45) | 1.77% false-lock | 97.1% / 99.0% |
| METAR 6-hr bound (#47) | **0.00% false-lock** | **99.72%** |
| deployed rule, 1-min feed | locks 67% of the above, 140 min earlier | same price wall |

And the economic ceiling, measured independently by the #44 verifier: in the only tradeable band
(ask 90–98c) you pay ~97.6c to win ~2.4c, so break-even is a **97.9%** win rate and clearing the
+2.0c bar needs **99.60%** — while the data's own upper bound is **99.2%**. The requirement sits
above what the data permits, and more months push that bound *down*.

## Predictions I made in advance that were wrong

Recorded because the value of this log is that it does not round in my favour.

- **I named sensor faults as the likely cause of death.** They were not: 0.05% on the primary arm,
  zero false locks. The corroboration guard I registered removed 0 of the 1 fault and cost <2% of
  fires. It mattered only on the LOW arm, which could not PASS anyway.
- **I predicted the 6-hr groups would be "hours before close, so unlike the CLI they are usable
  live."** The timing claim was right (8.1 h median) and the inference from it was wrong. Early is
  worthless when the market is earlier.
- **I wrote three defective specs.** An empty-interval bracket test; an outcome-conditioned price
  join that, implemented literally, would have produced a **fake PASS**; and a KILL clause that its
  own noisiest cell shielded. Two blind builds and a paid adversary caught all three.

## What this closes

No further weather study is justified: not FINAL-NO variants, not ladder pricing, not new stations,
not more months, not a faster feed. The population is priced before any observation-based rule can
reach it. `kwx-earlylock` and `kwx-depthprobe` remain armed on cron on **main** with their questions
long since answered; disabling them is the operator's call and has been flagged twice.

The live bot stays `KWX_SWITCH=off`. The one live action still worth taking regardless of strategy
is the **~50c pre-flight**: a single 1-contract NO order reconciled against `/portfolio/positions`
to prove `side="ask"` in Kalshi's v2 single-book API is short-YES. Nothing offline can verify it,
and a sign error there is the most expensive latent bug in this repo.

## What is structurally different, and therefore not closed by this

Every weather study was an **information bet**: we tried to know the answer sooner or better than
the market. That bet is now provably lost, because the market's forecast beats our observation.

The one shape this does *not* kill is a **liquidity bet** — not knowing more than anyone, but being
paid for immediacy. Post-finality market making on crypto hourlies is the registered candidate:
Kalshi crypto settles on a **named public index at a named timestamp**, so in the final seconds
there is nothing left to forecast and **nobody can know more than anybody** — adverse selection, the
mechanism that killed the maker study (#42) and that shows up in every weather result above as
"the fires you can fill are the ones you're wrong about," is absent by construction. Maker fee on
crypto is **$0**, so a 1c capture is 1c.

That is a different mechanism, not a 48th weather variant, and it is **unproven**. It needs its own
pre-registration and its own chance to fail: specifically, whether the book still quotes the loser
side above 1c once the outcome is determined, which is measurable from Kalshi candlesticks plus a
public index series with no new data purchase.

**No weather strategy in this repo makes money. None of the 47 ever did. The honest expected value
of continuing down this road is zero, and I am not going to propose a 48th variant of it.**
