# Forty-Two Kills

## Part 4 — Lessons and Outro

### 1. The transferable lessons

Forty-two dead studies are not forty-two unrelated facts. Read across the graveyard and a
handful of load-bearing lessons repeat, each earned by a specific number rather than a
vibe. Seven are worth naming, cited back to the kills that prove them, because a lesson
without a citation is just an opinion with better formatting.

**Efficiency is role-specific, not universal.** "Prediction markets are efficient" is too
coarse to be useful; what we actually measured is a quadrant — taker mechanics, maker
mechanics, speed, and information, all from a single seat: a retail-scale account on free
data, with no queue priority, no fee tier, and no privileged feed. The four corners came
back with four different verdicts, and every one of them is a verdict about that seat. A
participant sitting somewhere else in this market — a market maker with a rebate agreement,
a desk with a paid feed, anyone who is structurally the counterparty rather than the
crosser — is outside the tested quadrant, and nothing measured here says anything about
them either way.

Taker mechanics — buying a contract once its outcome is
effectively settled, paying the spread to do it — is the one mechanism this program ever
confirmed as a real, positive-EV shape: the weather mechanical lock backtested at
+1.1¢/contract at a ~99.6% win rate. Deployed live with a $10 canary it produced zero fills
against 189 logged near-misses, every one already priced past 98¢ before the detector could
act — real, but not reachable at retail speed. Maker mechanics — resting a bid — died three
separate times: the original weather post-lock maker study (case #1, 26 of 32 audited bids
were already marketable, not resting), the favorite-longshot maker study across the full
liquid universe (case #33, day-clustered t≈0.6, CI crossing zero, real volume requiring a
bid at −7 to −18¢/contract), and the crypto-hourly maker study that closed the year
(case #42: a real front-of-queue, pool-average *optimistic bound* of +0.76 to +1.25¢/contract
that evaporates the moment you ask whether a back-of-queue entrant could capture it — 0 of 20
cells stable across both temporal halves of the sample). Speed was measured directly and came
back flat: the latency-edge study (case #36) ran a model-vs-print speed curve across six
points from 1 to 300 seconds and found no decay, no positive point, anywhere on the grid. And information —
beating the market with a better forecast — lost twice, on two domains built to the same
standard: a walk-forward Elo model trained on 26 NFL seasons got *more* wrong as it
disagreed more with Kalshi's price (case #35, EV −0.043 to −0.067/contract, t as negative
as −2.21), and a *distributional* forecast rather than a point one — a fitted-Gaussian
stand-in, after the true 51-member ECMWF archive turned out to be unavailable beyond roughly
92 hours back — still lost to the market's own crossing price on Brier score at both leads
tested (case #37). That last one is the weakest of the four and is labeled as such in the
catalog: the genuine multi-member ensemble was never run, so what died is the reconstruction,
not the idea. Four roles, four independent failures, for four different reasons — a stronger
claim than "the market is efficient," because it rules out four separate escape hatches for
one seat instead of gesturing at all of them for everyone.

**High market frequency is not the same claim as high opportunity, and the latency study
measures the distinction with a flat line.** The intuitive story about speed is that faster
execution finds edges other people are too slow to take. Case #36 tested that story on the
fastest-moving instrument in the catalog — hourly crypto Up/Down — across a latency grid
from 1 to 300 seconds, and the curve that came back was **flat, not decaying**: no point,
including the fastest one measured, cleared the pre-registered significance bar, and the
fill-weighted EV was negative throughout (−1.7¢/contract at 1 second in the primary build,
−9.5¢/contract in an independent rebuild). Part 3 spells out why a flat curve settles more
than a decaying one would have; the consequence for anyone budgeting an infrastructure
spend is what matters here. When the engineering team built the actual low-latency stack
anyway, to answer the question honestly rather than assume it, the conclusion in
`ENGINEERING_STACK.md` reads: **"HFT hedge-fund tier" is achievable — and turns out to be
barely necessary.** The verified compute-plus-wire floor came in at 1.4–2.7 milliseconds,
roughly 400× inside the one-second budget the underlying economics pointed at, and it
changed the verdict on exactly zero strategies. Speed was never the moat — at least not at
any latency this design could resolve, which bottoms out at one second, not at the
microsecond scale where a co-located firm would be asking the question. The market
moving fast is not the same fact as the market leaving money on the table for whoever moves
fastest.

**Settlement provenance beats feed quality — and ForecastEx (case #38) is the cleanest
demonstration in the catalog.** The candidate looked like the one mechanism this
program had already confirmed working, transplanted onto a second, US-legal venue:
uncapped threshold ladders, a free millisecond-timestamped tape, and a 1-minute ASOS feed
reading a genuinely finer-grained truth than the venue's own settlement source. It died on
exactly that gap. ForecastEx settles on Weather Underground's METAR-sourced daily extreme,
a 5-minute-averaged value at routine cadence; the signal read IEM's true 1-minute record,
and a real, sustained 2–4°F excursion lasting a few minutes is **structurally invisible to
settlement**. Measured across 8,646 resolvable locks: 190 false locks, a rate of 2.198%,
Wilson upper bound 2.559% against a pre-registered ≤2.5% bar. The elegant part is what
happens at the obvious fix: demand a wider cushion so the false-lock rate falls to zero (it
does, at ≥5°F cushion). That cushion is exactly wide enough that the market has already
repriced to near-certainty, and there the flat $0.01 fee plus a pre-registered $0.01
slippage penalty consumes the entire remaining premium — fill≥98¢ mean net EV
−0.571¢/contract, day-clustered t=−5.66. That second door is the weaker of the two, and we
should say so plainly: the slippage penalty is a *pre-registered assumption* standing in
for an order book the venue doesn't publish, and without it the same fills come out around
+0.43¢ — so leg two is properly read as "not shown to survive under the conservatism we
committed to in advance," not as a measured loss. Leg one carries the kill on its own. What
generalizes is leg one's mechanism: a finer feed buys nothing against a coarser settlement
basis, because the extra resolution measures a quantity settlement never records — measured
at one venue over nine stations and five months, and worth re-checking rather than assuming
on any other weather market, before writing a line of backtest code.

**Executable-price discipline and sample size are in tension, and the ratio is roughly
20:1.** `REOPENABLE.md` originally argued that a 160-million-trade archive held roughly
100× the coverage of the original directional-strategy kills (cases #3, #5, #9) — enough,
on its face, to resolve three studies that had died from a shortage of data rather than a
negative result. Its own correction header says plainly that this was wrong: the archive
gave ~50× more raw *window* but produced *fewer* usable entries once the re-run
(`REOPEN_FUNNEL.md`'s spec D1) insisted on an actually-transacted crossing print instead of
a quoted snapshot — 5 entries against the original 17, 12 against the original 84. The
reason is measured: 4,188 of 5,034 test bracket rungs (83%) and 3,524 of 3,784 train
threshold rungs (93%) simply have no print at all in the entry window. Coverage and
*usable, executable* sample are different quantities, and on Kalshi's illiquid weather
ladders the gap runs about twenty to one — any research program reporting raw event counts
without separately reporting executable-print counts is quietly overstating its power.

**The spread IS the signal your screen finds, if you let it.** The final universe-wide
executable-price screen (`REOPEN_FUNNEL.md`'s spec U1) ran 946 taker unit-side hypotheses
against the entire eligible market universe, Bonferroni-corrected at α = 1.32×10⁻⁵, and
found 19 statistically overwhelming survivors against roughly 0.002 expected by chance
under the null — genuine signal, not noise. Seventeen of the nineteen were negative-EV.
That is the finding: a negative-EV taker unit-side is not a candidate trade waiting to be
flipped, it is a direct measurement of the round-trip cost of crossing the spread. Paired
against their complements, the two sides consistently summed to −6 to −10¢ (KXHIGHNY|B:
−6.36¢ yes-taker / −2.57¢ no-taker, summing to −8.93¢) — that sum *is* the spread plus fee,
priced exactly. A screen honest about executable prices will measure the cost of trading at
all, and mistaking that measurement for an edge is the single most common way a backtest
lies. (The other two survivors were legacy instruments that had stopped trading before the
validation window opened — unfalsifiable by construction, and shaped like the stale-print
artifact family that recurs throughout this catalog.)

**Pool-average maker EV is a front-of-queue mirage — case #42 is the year's final and most
expensive lesson in this shape.** `MAKER_VIABILITY.md` measured a real, positive,
arithmetic-exact pool of maker EV on Kalshi's crypto-hourly Up/Down markets: +0.76 to
+1.25¢/contract, reconciling to four decimal places against the independent taker-loss
number from the U1 screen above. Two blind builds, an independent mechanical recompute, and
an adversarial review gate all agreed the pool is real — and all four also agreed on what
kind of number it is, which the registration froze in advance and which no summary of this
study should drop: **a front-of-queue, pool-average optimistic bound.** It is the ceiling
available to a maker who is already first in line on every fill, averaged over every fill in
the pool. It was never a number a specific strategy was entitled to. What killed it was
asking the next question, frozen in advance by the registration (`MM2_REGISTRATION.md`): is
that pool something a scheduled, back-of-queue bot could actually collect? The listing-window cut —
fills in the first ten minutes after each hourly market opens, the one population where a
new entrant is genuinely front-of-queue — had **negative** point-estimate EV for both
assets (BTC −0.99¢, ETH −8.81¢). And the mechanism that would justify the pool average,
tested across both halves of the sample independently, held in opposite halves for the two
assets — BTC's nine passing cells all in the second half, ETH's one passing cell in the
first. A pool-average number that is real, exact, and reproducible can still be a mirage, if
the population generating the average isn't the population you can actually stand in front
of.

**And the meta-lesson: every verified positive was our own bug until proven otherwise.**
The single best-looking number this program ever produced — the forecast paper sleeve's
+$0.19/contract at day-clustered t=8.81 over 261 settled trades — did not survive being
checked against the venue's own settlement record. `PAPER_TRADER_AUDIT.md` traced it
through two stacked bugs: a known-and-unfixed NO-side cost error, and a previously
undetected settlement-boundary off-by-one that scored 37 of 261 trades (14.2%) against the
wrong outcome, every one in the same direction. Reconciled against Kalshi's own `result`
field, the same 261 trades come out to **−$0.0526/contract, t=−3.38** — a statistically
overwhelming positive, manufactured by two bugs, flipped to a statistically overwhelming
negative by checking. It kept happening: the latency study's mean-of-market-means framing
flattered the result until adversarial review corrected it to the honest fill-weighted
number (case #36); the weather-ensemble study's house note claiming historical ensemble
access "confirmed working" was refuted by a hard data-retention wall discovered during the
run (case #37); a macro-surprise re-test's builder called a "no signal" self-kill on a
statistic that, on review, carried zero information about the hypothesis — the verifier
overrode it to the more precise "never actually tested" (`REOPEN_FUNNEL.md`'s spec M1); the
maker-viability study's own anchor definition pooled two populations with opposite expected
signs before the registered correction separated them (`MM2_REGISTRATION.md`). None of
these reversals went the other direction. Every adversarial pass that found something found
a reason the positive wasn't real, never a reason a kill was actually a win in disguise —
which is the whole argument for treating verification as a non-negotiable stage rather than
a spot-check reserved for results that already look suspicious. The results that looked
*most* trustworthy were exactly the ones that turned out to be bugs.

### 2. What survived

Forty-two kills sounds like a program with nothing to show for itself, and mostly that's
correct — but three things came out of the year worth keeping regardless of what the P&L
says, because they are facts about infrastructure and data, not claims about edges, and
infrastructure facts don't expire when a strategy dies.

**The engineering stack.** Every number in `ENGINEERING_STACK.md` carries a label —
MEASURED, DELTA-VALID, CITED, or ASSUMED — and most of the load-bearing ones are the first
kind. A cold subprocess-per-call pattern, the architecture the bot actually ran on for most
of the year, cost 255–354 milliseconds per signing operation; a warm, persistent process
with the key already in memory cost 0.37–0.68 milliseconds — a roughly 500–650× tax the old
cron-on-a-schedule design was silently paying on every order attempt, before any market
condition was even considered. A cold connection reconnect cost 500–655 milliseconds —
enough, on its own, to consume most of a one-second reaction budget. And Kalshi's matching
engine lives in AWS us-east-2, reachable from a same-region VPS at a cited cross-AZ RTT of
1.0–2.0 milliseconds, which replaces colocation entirely here and costs about $5–20 a month
to stand up. None of these numbers depend on any strategy being alive — they are simply
true about how to talk to this exchange fast, and will still be true the next time anyone
builds something that needs to.

**The data-source register.** `DATA_SOURCES.md`'s headline finding is uncomfortable and
worth repeating precisely because it is: a hardcoded shard constant (`N_TRADE_SHARDS = 9`)
had been silently hiding 7 of the archive's 16 trade shards — 44% of the roughly
160-million-row Kalshi trade tape, invisible to every backtest run before the bug was
found. It did not resurrect any dead study — studies that died on mechanism (spread,
adverse selection, market efficiency) don't come back with more rows of the same
mechanism — but it is exactly the kind of finding a verification discipline exists to
catch, and it is now fixed and documented, along with the correct query pattern (explicit
shard enumeration; wildcard globbing 404s against Hugging Face's HTTP layer) and the
warning that the shards are not a time partition or a clean ticker range, so subsampling
them for anything order-sensitive silently corrupts the result. That register — which
sources are real, which are proxies, which endpoints are settlement truth versus
self-computed — is worth more than any single backtest built on top of it.

**Structural revenue, reported honestly.** After 42 statistical kills, `STRUCTURAL_REVENUE.md`
asked a narrower, more modest question: is there money here from a documented contract term
rather than a trading edge? Most candidates died on arithmetic before a dollar moved —
ForecastEx's incentive coupon floors at 1.565% and sits below parked-cash yield at every
holding period once its $0.02/pair fee is counted; Kalshi's own 3.25% cash APY runs
$5–10/month behind a T-bill at $10k and survives only as a carry offset for capital already
parked there for another reason; Polymarket's maker rebate is real but geo-blocked to a US
person. What's left, honestly ranked, tops out at hundreds of dollars a month, not
thousands — the document says so in as many words: **"the best case here is hundreds per
month, not thousands."** The one live, still-open question is the Kalshi Liquidity
Incentive Program — a presence-based, per-second-scored reward pool, $10–$1,000/day, with
two load-bearing parameters nobody has measured (the pool share a small quoter actually
earns, and whether the proximity discount forces you all the way to the touch, where the
measured fill economics sit at the same pessimistic −8.81¢/ct bound that killed case #42).
The recommended next step is a two-week, ≤$1,000 de minimis pilot with three pre-registered
falsifiers cheap enough to kill it in a week if it's dead — and a hard calendar deadline of
its own: the program window closes 2026-09-01. That is the one number in this publication
still unresolved, on a clock, rather than settled.

### 3. Outro: what we'd tell someone starting tonight with $1,000 and a bot framework

Not "don't." That's the lazy answer, and it isn't the honest one — the honest one requires
saying what it actually costs to find out, and what this catalog already rules out before
you spend a dollar of it.

It will cost less than you think to get a *statistically real* answer, and more than you
think to get a *deployable* one. Every kill here that reached its pre-registered bar did so
on free data — a public archive, a public candlestick endpoint, a public settlement field —
and the infrastructure that answered the hardest remaining question (is speed the
bottleneck?) cost about $5–20 a month on a small cloud instance. The statistical answer is
cheap. What's expensive is everything downstream of a real signal: the two-account custody
overhead that made an 11-pair, $65.95 cross-venue arbitrage not worth executing; the
queue-position infrastructure a maker strategy needs before its pool-average EV means
anything; the months of live losses this program's own verification discipline substituted
for with a $0-infrastructure measurement instead. If you're going to spend the $1,000,
spend the first hundred reproducing a kill, not standing up a strategy — you'll learn more
from confirming that #36's latency curve is really flat than from three weeks of live
trading on a signal nobody adversarially checked.

The map already rules out more territory than most people starting tonight will believe.
Kalshi is closed at every granularity we could construct — universe, category, individual
series, taker side and maker side both. Polymarket is closed at tradeable prices across
1,447 real markets, which matters because the classic favorite-longshot pattern that looked
real on Kalshi's quoted prices flattens out entirely once priced on a zero-fee venue at its
own tradeable prices — as close to a clean control as this kind of research gets.
Cross-venue arbitrage between the two is closed: the one opportunity that existed was a
$65.95 one-time profit for $3,344 tied up five months, worse than parked cash before paying
for two exchange accounts. The latency axis is closed, measured rather than assumed, flat
from one second down to the fastest latency the design could resolve. And the two most
tempting shortcuts — beat the market with a better forecast, or find the mispricing
everyone else's screen missed — both have a dated, numbered kill on top of them (#35, #37,
and the taker-spread mechanism inside U1). None of it is a guess; every closure has a
specific number and mechanism behind it, reproducible from the artifacts left on disk. And
every one of them is a closure for the seat this program sat in — retail account, free data,
no queue priority — which is the only seat any of these numbers describe. What we ruled out
is the territory a bot like this one can reach, which is not the same as the territory.

So here is the honest version of what you'd actually be answering tonight with that $1,000:
not "can I beat Kalshi," which forty-two studies already answered for the strategy families
a retail bot can reach — but something narrower and genuinely still open, because we didn't
test it. Maybe it's a market this catalog never touched. Maybe it's a domain forecasting
model built somewhere thinner, where the sports and weather axes we closed don't transfer.
Maybe it's running the Liquidity Incentive Program pilot before its September deadline and
reading the three numbers nobody else has measured yet. Whatever it is, ask the
pre-registration question before you touch a dollar: what result, specifically, would make
you stop? Write it down first. Every study in this catalog that skipped that step is
exactly the study most tempting to keep running past the point where the honest answer was
already in.

The scoreboard never moved from $4,000 a month. It sits, at year's end, at $146–149 a month
on live-observed evidence, or at best an assumption-heavy $1,173 a month nobody has
actually watched arrive. Get either of those numbers and you'll have learned something real
about a market tested harder than almost anything a retail account will ever point a bot
at — and if you get a number this catalog doesn't already have, that's the one entry we'd
genuinely want to read.
