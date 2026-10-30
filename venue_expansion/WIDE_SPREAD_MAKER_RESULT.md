# WIDE-SPREAD MAKER — **KILL**. The spread is the price of adverse selection, everywhere.

> **ARTIFACT LOSS, disclosed up front.** The container was replaced mid-study with a fresh clone at an
> older commit. The executing agent's commit (`ef7b498`), its three output files
> (`wide_spread_maker.md` / `.json` and the final `.py`) and ~43 hours of cached trade tape were
> **local-only and are gone** — it had not pushed. The harness as of its last WIP push survives
> (`wide_spread_maker.py`, 94 KB, commit `a34142b`). **Every number below is transcribed from the
> agent's completion report, not re-derived from artifacts**, and cannot currently be reproduced
> without re-running the tape fetch. Treat it as a faithful record of a completed run, not as a
> verifiable one. This is a process failure on my part: I committed the harness as WIP but did not
> require the agent to push its results as it produced them.

## Verdict: KILL — and the failure mode is adverse selection, **not** missing fills

This is the first spec in this program whose **KILL clause actually fired.** Three of my earlier specs
froze gates that could not fire; this one could, and did.

## My prediction was half wrong, and the half that was wrong matters

I registered two failure modes. The one I thought most likely is **false**:

**"Wide spread means thin flow" — refuted.** Pooled fill rates across the 22 qualifying series:

| side | optimistic | N=25 | N=100 |
|---|---|---|---|
| sell | 83.6% | 77.0% | 71.1% |
| buy | 78.2% | 70.5% | 62.9% |

The 5% fill-rate gate was met in **172 of 176 cells**, with per-series N=25 rates from **32% to 96%**.
Wide quotes on products that trade at all **do** get crossed. Flow was never the problem.

**The other failure mode is what killed it.** Adverse-selection ratios ran **1.05–1.5** on liquid
esports/tennis books and **2.1–2.4** on thin wide books (`KXNCAAFTEAMRECTD`, `KXWNBAAST`). Of 176
cells, **38 met the n floor** (from 5 series: ATP Challenger doubles, Dota2 maps, LoL maps, NCAAF 1Q,
Valorant maps), and in **all 38** the Bonferroni-adjusted Wilson bound fails to clear break-even in
the profit direction — with point estimates **5.4 to 27.1 percentage points on the losing side.** They
still lose when restricted to quotes whose entry candle is ≤120 s old, so staleness is not the cause.

Best floor cells, both losing:
- sell: `KXNCAAF1Q` T=60 k=2 — P(YES|filled) **40.9%** vs break-even 35.5%
- buy: `KXLOLMAP` T=60 k=2 — P(YES|filled) **42.6%** vs break-even 52.9%

## The general finding

Market making on this venue is now measured at **both ends of the liquidity spectrum**:

| regime | spread | what adverse selection did |
|---|---|---|
| BTC hourly (tightest books) | 1–3c | ate essentially all of it; ratios 1.1–2.3 |
| In-play sports/esports (widest books that trade) | ≥5c | ate **more** than all of it; 5.4–27.1 pp on the losing side |

**The spread is not revenue waiting to be collected. It is precisely the compensation for adverse
selection, and it is priced correctly across the whole spectrum.** Wider spread buys you
proportionally worse selection, not more edge. That closes market making on Kalshi venue-wide, both
sides of the book, at every liquidity level we can reach.

## The one squeak, and why it is not a result

Two `KXUFCROUNDS` T=15 buy cells (k=1, k=2, the same 209 quotes) clear gate 1 — but on **175 fills
against a 500 floor**, so they cannot PASS and the KILL clause does not reach them. The agent's own
read, which I endorse: the quote population's YES rate is **67.5% against a mean quoted price of
48%**, and a *taker* buying the ask on those markets would have made **+18.7c/market before fees**.
That is a base-rate oddity over 121 events, not evidence a maker is paid. **With 352 comparisons, one
clear is roughly what a 5% family-wise error rate permits.** Flagged for separate registration only.

## Spec defects — my fifth and a correction to a claim I made four times

1. **Criterion C3 is degenerate.** "Median entry-candle volume > 0" is a *one-minute* statistic and is
   0 for almost every book — **`KXBTCD` itself fails it** (median 0; only **4.6% of its 55,205 entry
   minutes traded**). So my mechanical selection accidentally selected *in-play* sports/esports rather
   than the wide-spread-with-flow products I intended. The agent reported this rather than repairing
   it, which is correct. It also ran the intended population as a labelled exploratory tier (323
   series passing C1+C2, failing only C3): pooled T=15/k=1/N=25 gave sell fills 29.8%, buy 41.6%,
   adverse ratios 2.02 and 1.46, and **no pooled cell cleared gate 1.** So the defect did not hide
   the answer.
2. **"The EV t-statistic is unreachable" — I asserted this in four consecutive specs and it is not
   universally true.** Here the UFC cells reach **t = 4.3 and 4.4 against a bar of 3.9.** It is
   unreachable for thin-tailed binary payoffs with a *saturated day count*; with high fill rates and
   many events it is reachable. I should have scoped the claim instead of generalising it.

## Scope of the KILL

It covers **static quotes placed once and held to close.** Cancelling, re-quoting and quote skew were
excluded by design and are **untested** — see `PATH_TO_4K.md` for why that remainder is nonetheless
closed by inheritance from the latency measurement.

## Correctness anchors (all held)

- Taker-side mapping asserted two ways, with **nine doctored-copy negative controls** — outcome in the
  placement path, `100 − ask`, a mid price, bid/ask outside the spread function, a swapped taker-side
  map, a wrong fill predicate — **all raise.**
- Empirical check on the tape: taker sells print inside the candle bid range **100.0%** of the time,
  taker buys inside the ask range **100.0%** (8,574 and 29,380 prints).
- Ten hand-worked fills per side re-derived from raw JSON.
- **100% coverage** of every passing series' live universe; exact prefix of the saved shuffle, 0
  stragglers.
- Comparison count **M = 352** written to disk at 2026-10-29T19:48:32Z, **before** any quote, tape or
  outcome existed.
- Elections contributed nothing: **466 of its 467** live series fail C1.
