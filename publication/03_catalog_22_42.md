# Forty-Two Kills

## Part 3 — The Catalog, Cases 22–42

The first twenty-one entries killed the easy ideas — resting orders that weren't really
resting, directional signals that were noise, thin corners with nothing arbitrageable in
them. This batch is more expensive per kill: bigger archives, more adversarial rounds,
studies that survived a first pass only to die on a second one, and — at the end — the one
study that got closest to a real edge before its own pre-registered temporal split took it
apart. A few new verdict labels appear here. **CONFIRMED FAIL** means a verdict that already
looked dead got independently re-derived by a second build or an adversarial reviewer and
held. **N-GATE INSUFFICIENT**, **INCONCLUSIVE**, and **INSUFFICIENT — NOT TESTED** all mean
the pre-registered sample floor was never reached — not the same thing as a negative result,
and we keep making that distinction even where it costs the narrative a clean kill. We hedge
exactly where the source hedges, including one place where we have to walk back our own
earlier framing, in public, inside this same catalog.

---

## Illiquid Corners, Continued

`ILLIQUID_MARKETS.md` closed one clean kill in Part 2 (#21). The next three didn't find an
edge, but they didn't get a fair trial either — they ran into a wall that recurs throughout
this half of the catalog: Kalshi's `/events` endpoint quietly drops old markets, returning
`markets: []` for events that plainly used to exist.

**#22 — r1s1 (mention anchor).** The plan was to anchor passive quotes off broadcast-mention
markets. The data wall hit first: `KXFEDMENTION` collapsed to one retrievable event and
`KXHANNITYMENTION` to two — three broadcast-days against a floor of ≥30 entries and ≥8
event-days. Verdict: INCONCLUSIVE.

**#23 — r1s2 (off-air passive quoting).** Three event-days survived against a floor of 10 —
already a fail — but the exploratory markout that could be computed was negative anyway:
−2.29 cents validation, −4.57 cents pooled. Prints on these markets move toward the true
outcome faster than a 12-cent passive quote can track, and every adverse-selection sub-check
that was computable failed. Verdict: INCONCLUSIVE + NEGATIVE — functionally dead regardless.

**#24 — r1s3 (jobless-claims relist).** `KXJOBLESSCLAIMS` relists weekly, which sounded like
a clean recurring sample; `/events` lists 47 settled events, 37 of which return an empty
`markets: []`. Ten reachable Thursdays survived against a floor of 15. Verdict:
INCONCLUSIVE.

---

## Stacked Edges

`STACKED_EDGES.md` tried combining signals that each looked individually promising, on the
theory that a weak signal plus a weak signal plus real execution discipline might clear a bar
none of them cleared alone.

**#25 — r1s1 (broadcast-mention siblings): 97.7% win rate, still a loss.** Across 265 settled
markets and 88 entries, this strategy won almost every trade and still lost money on net:
−1.78 cents flat, −4.20 cents day-clustered, t=−1.25. It only fires once the book is already
between 90 and 99 cents, so one false lock at roughly −95 cents erases dozens of one-cent
wins. Verdict: CONFIRMED FAIL.

**#26 — r1s2 (KXJOBLESSCLAIMS AR(1)+MA nowcast).** The same `/events` retention wall as #24,
from a different angle: only 10 of 28 TEST weeks were servable against a floor of ≥60.
Underpowered this badly counts as a kill under this program's protocol, and the point
estimate that could be computed was negative and worse-calibrated than the market anyway.
Verdict: CONFIRMED FAIL (underpowered pre-registered kill).

**#27 — r1s3 (cross-venue reprice race): n=1.** A history purge left exactly one surviving
Kalshi/Polymarket matched pair, and it triggered zero entries — both venues were already
sitting at roughly 0.99 and 0.997 through the entire announcement window. Verdict: CONFIRMED
FAIL/UNTESTED.

**#28 — r2s1 (crypto cross-venue lead-lag): zero reconcilable pairs.** A preflight check,
confirmed for both BTC and ETH, found zero reconcilable single-instrument pairs before any
lead-lag test could start: Kalshi runs $100-wide hourly BRTI strikes, Polymarket runs
strike-less or $2,000-wide Binance-close brackets, and the structures don't overlap. Verdict:
FAIL (preflight self-kill).

**#29 — r2s2 (macro-surprise pass-through drift): ~31 events, needed 40.** The one entry
here whose mechanism preflight actually passed (10 of 10 sampled releases cleared the
liquidity bar) and whose hypothesis was, for that reason, never genuinely tested. Verdict:
N-GATE INSUFFICIENT — a loose thread picked back up later in this catalog, twice.

---

## Favorite-Longshot Bias

The favorite-longshot bias — bettors systematically overpaying for longshots and
underpaying for favorites — is one of the best-documented biases in all of betting-market
research. `FAVORITE_LONGSHOT.md` and its maker-side companion study spent real effort trying
to find a version retail could actually capture on Kalshi. The bias itself turned out to be
real. Capturing it did not turn out to be possible.

**#30 — Spec 1 (broad longshot fade, ex-crypto ex-weather): −$60/month, honestly.** The
largest, cleanest test in this section: 2,958 trades across 2,189 events and 256 days. The
naive signal edge was real, +1.70 cents — but crossing the spread at a realistic entry price
cost 3.18 cents, leaving a net EV of −3.41 cents per contract, day-clustered t=−4.87, 95% CI
[−5.16c, −1.66c]. Honest capacity: **−$60/month**, negative across all three sub-categories
and both halves of the sample. Verdict: CONFIRMED FAIL — the same spread-eats-the-edge death
that killed the long-tail passive-spread study (#20).

**#31 — Spec 2 (favorite buy, 70–90 cents): a join that never finished, not a disproven
edge.** A clean 383,553-market candidate universe got built; the join against roughly 172
million trades, sharded nine ways, did not complete inside the compute budget — confirmed on
a direct rerun that produced zero output after 170-plus seconds. No P&L exists to certify
one way or the other, so under this program's own rule (you can't ship a claim you can't
verify) it's scored deployable: NO, capacity $0/month. Verdict: CONFIRMED FAIL
(execution-limited, not measured-negative) — a real distinction, even though the practical
result is the same.

**#32 — Spec 3 (crypto isolation, 5–45 cents): one bad day did all the damage.** 118 trades
across 40 events and 33 days, against a floor of ≥200 events / ≥60 days — a hard population
ceiling of 84 events meant the floor could never be reached. The mean was −4.17 cents per
contract, t=−0.64, CI crossing zero; excluding the single worst day (2026-01-02) brings the
mean to exactly zero. Verdict: CONFIRMED FAIL.

**#33 — Maker favorite-longshot: real bias, unreachable via resting bids.** The maker-side
retest across the whole liquid universe, not just weather. Two independent backtests
reconciled to a null — overlap point estimate +0.4 to +1.3 cents, day-clustered t≈0.6, CI
crossing zero — and capturing real volume required bidding into a zone paying −7 to −18
cents per contract. Honest capacity: **$0/month**. Side finding: the sports vertical, the
dominant category here, now charges a real maker fee (~0.33 cents/contract), correcting a
stale zero-fee assumption inherited from the earlier weather-only maker study. Verdict:
CONFIRMED FAIL. Between #30–#33, favorite-longshot bias is dead under both execution styles:
real, and not capturable by crossing the spread or resting a bid.

---

## The Series-Level Scan and Two Cross-Domain Axes

Four studies here each closed off an entire *axis* of the search rather than one strategy —
worth reading together, because each answers a version of the same question: is there some
*dimension* — series, forecasting model, execution speed, forecast uncertainty — along which
this market is beatable, even if no single strategy on that dimension is?

**#34 — Per-series last_price screen: 5 survivors at scale, 0 at a realistic entry.** This
screen ran all 144 series with ≥300 settled markets through a Bonferroni-corrected
last-price-bias test. Five survived — KXBTC, KXETH, KXNFLFIRSTTD, KXINX, KXNFL — each
showing a highly significant "buy NO" bias of 4.3 to 10.7 cents. The retest at real,
crossed-spread, fee-inclusive taker prices (13–22 real trading days per series, 18.4 million
fills) collapsed all five to |t| < 2.2; capacity was never the binding constraint (KXBTC
alone traded roughly $406,000 notional per day). The same two artifacts that killed earlier
studies reproduced exactly: a stale-`last_price` signature on markets that expire worthless,
and a regex bug conflating unrelated sub-products under one "series" name. Verdict:
CONFIRMED FAIL.

**#35 — Sports forecasting axis: the market beats the model, and gets more right as the
model gets more wrong.** Two tests on `KXNFLGAME`'s moneyline market against 274–282 games
of the 2025 season, real pregame crossing prices, no look-ahead. Against the devigged Vegas
closing line, a clean null: EV −0.0001/contract, t=−0.13, 189 trades / 49 game-days. Against
a walk-forward Elo model trained on 26 seasons (1999–2024) and run genuinely out-of-sample
through 2025, worse than null: EV −0.043 to −0.067/contract, t=−1.33 to −2.21, getting *more
negative* the more the model disagreed with the market. Spot-checked against one real
settled game (Cowboys at Eagles, 2025-09-04): devigged Vegas 22.32% versus Kalshi 21–22
cents. Verdict: CONFIRMED NULL (sharp-line) + CONFIRMED NEGATIVE (trained model).

**#36 — Latency axis: crypto Up/Down at six speeds, and the curve is flat.** Does going
faster help? Two independent builds measured a model-vs-print speed-versus-EV curve on
hourly BTC/ETH Up/Down markets across six latencies, 1 to 300 seconds, fee-inclusive real
fills. The curve is flat, not decaying, and non-positive everywhere: −1.7 cents/contract at
1 second in the primary build, −9.5 cents in an independent rebuild; no point reaches the
pre-registered |t|≥3 bar. A flat curve is decisive here — it means the signal is already
priced into the fill by the fastest latency this design can measure, leaving nothing to
extrapolate toward a sub-100ms or co-located edge. Verdict: NO-EDGE-ANY-LATENCY. Faster
execution was the one operator-controlled lever that looked plausibly worth building. The
data says don't.

**#37 — Weather ensemble-probability info-gap: the real ensemble was unreachable, and the
best available stand-in was already priced.**
An earlier study had shown a single deterministic weather forecast carries no edge against
Kalshi's weather prices; this asked whether the *distributional* information in a genuine
multi-member ensemble beats the market instead. The intended test, on a true 51-member ECMWF
ensemble, never produced a result — the historical archive is null beyond roughly 92 hours
back for every model tested, a hard retention wall. A fitted-Gaussian substitute (4 cities,
50 out-of-sample days, real tape entries) came back null at both leads (day-ahead −0.55
cents, t=−0.34; same-morning −0.59 cents, t=−0.61), with the market beating the model on
Brier score at both. Verdict: CONFIRMED NULL — and scoped exactly as the source scopes it:
the substitute is measurably overconfident in the mid and upper probability bins, so this
closes *this model's* edge, not any conceivable true-ensemble edge. What can be said is the
narrower thing: Kalshi weather prices ensemble-grade uncertainty about as well as the best
free-data reconstruction available to a retail operator, and the genuine article stayed out
of reach behind a retention wall rather than being beaten.

---

## #38 — The Venue You Can't Beat With a Finer Feed

**ForecastEx daily temperature: killed on two independent grounds, and the second one is
philosophically interesting.**

Every other entry in this catalog fights Kalshi. This one is different: ForecastEx is a
separate, CFTC-regulated, IBKR-accessible venue, and the appeal was obvious — a fresh venue
means a fresh chance the mispricing hasn't been arbitraged away yet. The study built 8,646
resolvable mechanical locks across nine stations over a five-month window (temperature
contracts didn't exist on this venue before 2026-02-17, measured, not assumed) and found the
mechanism dead on both legs it was pre-registered against.

**Leg one: the venue's settlement source is coarser than the feed built to beat it.**
ForecastEx settles on Weather Underground's METAR-sourced daily extreme — averaged over
five-minute windows, sampled at roughly hourly cadence. The signal read the true one-minute
ASOS record. That mismatch produced 190 false locks out of 8,646 — 2.198%, a Wilson upper
bound of 2.559% against a pre-registered bar of 2.5%. Not one bad sensor: the false-lock rate
ranged from 1.07% at the best station to 4.64% at the worst, and is monotone in cushion —
2°F of cushion produced 183 false locks out of 7,615, 3°F produced 10 of 481, 4°F produced 2
of 245, and every cushion ≥5°F produced zero. One worked case makes it concrete: at KLGA on
2026-06-12, the one-minute archive shows a genuine sustained excursion — 96, 98, 98, 99, 98,
96°F across five minutes — while the venue's own settlement ladder recorded an official high
of exactly 94°F, and the tape never priced YES above 12 cents all day. The finer feed was
"right" about a quantity the settlement process structurally cannot see.

**Leg two: the escape hatch closes itself.** The obvious fix — trade only where the cushion
is wide enough that false locks vanish, ≥5°F — fails for a cleaner reason than data
insufficiency: wide cushion means the excursion is obvious, and obvious means the market has
already repriced. At fills of 98 cents or higher, where the tape agrees the lock is
genuinely confirmed, mean net EV was **−0.571 cents per contract**, day-clustered t=−5.66,
one-sided upper bound −0.357 cents against a kill threshold of +0.2 cents.

That second number carries a dependency worth stating in the same breath as the number
itself, because it changes its sign: the −0.571¢ includes the spec's **frozen 1-cent
slippage penalty** on top of the 1-cent fee, and without that penalty the same fills come
out at roughly **+0.43¢**. The penalty was pre-registered in advance as the conservatism
substitute for an order book ForecastEx doesn't publish, so it cannot be dropped after the
fact and the EV leg stands as registered — but it is an assumption standing in for a
measurement, not a measured execution cost, and a reader who thinks that assumption is too
harsh should read leg two as unproven rather than as a measured negative. Leg one, the
false-lock breach, does not depend on it at all; that is why the kill holds either way.

The build's headline number — +9.20 cents, t=15.42 — was population mixing, not an edge:
81.2% of all profit came from the 26.3% of fires printing below 80 cents, where the market flatly
disagreed the contract was locked, winning only 83.1% of the time — an unregistered
directional bet that a one-minute spike foreshadows the official record, not the mechanical
lock this study was built to test.

One honest correction worth repeating rather than smoothing over: the operator's team
initially argued ForecastEx's flat one-cent fee wasn't worse than Kalshi's, since Kalshi's own
`ceil(7p(1−p))` also lands at one cent above roughly 83 cents — a correct comparison. The
conclusion drawn from it, that the fee was therefore survivable, was wrong: a lock bought at
98 cents or higher has at most 2 cents of gross premium, and 1 cent of fee plus 1 cent of
pre-registered slippage consumes all of it. Not worse than Kalshi is not the same as
survivable.

Three builds went into this verdict — two independent, plus a third written because the
first stalled mid-run — and they reproduce each other to every digit. The generalization is
the useful part, stated as the mechanism implies rather than as a law: **a feed finer than
the settlement basis buys you nothing about the settled quantity** — the extra resolution
measures something settlement structurally never records. Measured here on nine stations
over five months at one venue, so treat it as a preflight check rather than a proven
universal: on any future weather market, find out exactly what settlement averages, and at
what cadence, before writing a line of backtest code.

---

## #39–41 — The Executable-Price Screen, and a Lesson About Counting

Before these three, there was a wrong idea that deserves to be shown, not hidden. An earlier
analysis (`REOPENABLE.md`) looked at eight of the graveyard's underpowered kills — studies
that died for lack of sample, not a negative result — and compared the sample each had
reached against what a much larger trade archive could theoretically supply, which held
roughly 100 times the events some of these studies had used. The conclusion looked
straightforward: rerun them against the bigger archive, and three or four of the eight should
finally become testable. **The premise was wrong, and the correction is the more interesting
document.** The original analysis counted *events and settled markets*; the kill bars were
stated in *entries* — instances where a signal actually qualified and produced a tradeable,
transacted price. Those are not the same unit, and the gap turned out to be enormous. When
one of the reopened directional specs (SPEC 1) actually ran against roughly 50 times the
original window, it produced *fewer* qualifying entries than the original study had — 5
against 17 — because the original studies triggered on quoted bid/ask snapshots, and
requiring an actually-transacted crossing print instead meant 83% of bracket rungs and 93% of
threshold rungs had no print at all inside the entry window. **More archive coverage doesn't
unblock a test if the entry rule itself starves on realistic prices; it just moves where the
starvation happens.** The "100× more data" claim was true of coverage and false of usable
sample — the corrected document says so in its first paragraph, in bold, before anything
else — and it reframed the whole reopen effort into four brand-new pre-registered specs, run
properly.

**#39 — U1, the executable-price universe screen: the biggest single measurement in this
program, and it detected the spread.** This was the fix for the single most common killer in
the catalog — screening on `last_price` or the mid, then losing the survivors the moment a
realistic entry price gets applied (exactly what killed #34, #20, and #33). U1 built prices
the honest way from the start: every price is a reconstructed crossing price off the recorded
`taker_side` — lift the ask, hit the bid — with fees applied at that same price, across all
16 trade shards. That's **154,505,005 rows scanned, 17,006,887 qualifying** after the
pre-registered admission bands, spanning 473 eligible series×side units tested on both taker
actions — 946 hypotheses, Bonferroni-corrected to a per-test threshold of about 1.3×10⁻⁵.
Worth disclosing rather than rounding away: only 143 of those 946 unit-sides actually cleared
the pre-registered minimum-sample floor and produced a computable statistic, so the screen's
real coverage of the eligible universe was 15%, not 100% — conservative, since it doesn't move
any bar, but it's the honest denominator.

Nineteen unit-sides survived. **Seventeen of the nineteen had negative EV, and that is the
finding, not a footnote.** A negative-EV taker unit-side isn't an inverted edge waiting to
be flipped — its opposite isn't the other side of the same trade, it's resting a bid, i.e.
maker capture, already killed twice (#1, #33). The paired numbers make the mechanism
explicit: on the KXHIGHNY high-bracket, buying YES cost −6.36 cents and buying NO on the
identical instrument cost −2.57 cents — both losses, summing to −8.93 cents, close to the
round-trip cost of crossing the spread plus fee. Every KX-era survivor has this shape. The
screen had real power — 19 survivors against roughly 0.002 expected by chance — and what it
detected, at scale, was the market correctly charging for the spread it quotes.

The two positive survivors don't rescue anything either. Both — a legacy `INXD` threshold
series and a legacy `U3` series — stopped trading before the validation window even opened
(last `INXD` print 2024-12-31; last `U3` 2024-11-01), unfalsifiable by construction, and their
price-decile profiles carry the exact signature of an already-decided market trading at a
stale price: a 100% win rate at both the 70–80 and 80–90 cent deciles, complement at exactly
0%. At Stage 2, the best surviving candidate — `KXHIGHNY` bracket, YES side — cleared every
validation clause except the one requiring the win rate to beat fee-inclusive breakeven, and
died there with a genuinely stable loss (−4.262 cents, t=−4.626, stable across 10 of 10
deciles). Verdict: CONFIRMED FAIL. It closes, not opens, the methodological question
`REOPENABLE.md` raised: run the honest-price screen properly, once, and among every
unit-side that produced a computable statistic there is nothing there. The 15% coverage
above is the limit on how far that sentence reaches — the 803 unit-sides that never cleared
the sample floor are unmeasured, not cleared.

**#40 — Two reopened kills that still aren't answered.** Two of the original graveyard's
data-walled deaths got a genuine, pre-registered rerun against the larger archive, and both
came back **not tested**, distinct from a negative result. The macro-surprise reopen (#29's
second attempt) found that both of its two qualifying entries had no opposite-side print
anywhere in the required exit window, so their result was a mechanical certainty (minus fees)
before any hypothesis about drift was engaged, and the family's sample ceiling (31 events
against a floor of 40) was unreachable ex ante, since the fitting window predates half the
registered market families entirely. The jobless-claims relist reopen (#24's second attempt)
reached exactly one qualifying entry out of seven anchorable weeks — entry starvation, not a
mispricing. Neither strategy's underlying question has been answered by any study here.

**#41 — The directional specs, reopened, and the same wall from the other side.** SPECs 1,
3, and 7 — the original youth-of-market kills from Part 2 (#3, #5, #9) — were rerun at
roughly 50 times the original window and still didn't clear their floors: 5 qualifying test
entries against a floor of 200 for SPEC 1, 12 against 300 for SPEC 3, and zero of five
required price bins reaching minimum sample size for SPEC 7. The transferable finding is the
same one U1 hit from the other direction: executable-price discipline and sample size are in
direct tension on these instruments, roughly 20-to-1. #3, #5, and #9 remain open in the
strict sense — never disproved — but the honest reason has changed from "the market was too
young" to "these entry rules do not produce executable fills at any depth this archive has."

Taken together, #39 through #41 are the moment this catalog corrects itself in public: a
wrong premise about what more data would unlock, followed by the measurement, followed by an
honest accounting of what it did and didn't settle.

---

## #42 — The Closest Thing to a Real Edge

**Kalshi crypto-hourly maker capture: a genuinely positive pool, killed by its own
pre-registered temporal split.**

Everything above this line is either a clean negative or an unresolved data-availability
question. This one is different, and it's the right note to end the catalog on, because it's
the study that came closest to surviving.

The measurement itself is not in dispute — two blind builds, a full mechanical recompute
that matched both to arithmetic exactness, and an adversarial review gate all agree: **the
maker pool on Kalshi's hourly BTC/ETH markets is real and positive.** Across all 16 trade
shards, October 2024 through January 2026, all-fills maker EV came in at roughly +0.76 cents
per contract on the all-day universe and up to +1.25 cents on BTC in the final trading hour,
best gated cell about +2.4 cents. That number reconciles to four decimal places against U1's
independent measurement of the taker side's loss on the same instruments — two separate
studies arriving at the same number from opposite directions, about as strong a cross-check
as this program produced anywhere.

But that positive number is explicitly **a front-of-queue, pool-average, optimistic bound**
— not a number any specific strategy is entitled to capture — and the pre-registered second
stage (MM2) existed to test whether it was achievable. It wasn't, on three grounds:

1. **The good half keeps changing which half it is.** Zero of 20 tested cells passed the
   study's core clauses in *both* halves of the sample. BTC's nine passing cells all fall in
   the second half; ETH's single passing cell falls in the first — the two assets' good
   periods are literally opposite periods, the signature of a regime that doesn't persist.
2. **The proposed mechanism doesn't show up when tested directly.** The theory required
   informed flow to lose money against the resting maker. Full-sample it does (BTC −0.049
   cents, ETH −0.063 cents) but at t≈−0.08, statistically zero, and in one half per asset it
   doesn't hold at all.
3. **The one population a real strategy could access is negative.** Restricting to fills in
   the first ten minutes after each hourly open — the only slice where a new order is
   genuinely front-of-queue — produced negative point estimates for both assets: −0.99 cents
   for BTC, −8.81 cents for ETH (underpowered, but both on the wrong side of zero).

The plain reading: the positive pool-average EV lives in fills a scheduled new entrant
wouldn't capture, in a regime that doesn't hold across the sample. The registration had
pre-committed to exactly one anchor redesign as a one-shot spend if the first-pass gate came
back ambiguous — it did, the redesign was spent, and it still didn't clear both temporal
halves. Under the study's own frozen rules, that closes the door permanently.

Verdict: **MM2-FAIL → PERMANENT KILL.** Running total: **42 tested, 42 dead.** The honest
framing worth keeping: this answer — a real, measurable, ultimately unreachable pool — came
from roughly zero dollars of infrastructure and one careful measurement, instead of building
a five-figure market-making stack and finding out the same thing after months of live
losses. That was the entire point of measuring first.
