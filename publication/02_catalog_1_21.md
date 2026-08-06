# Forty-Two Kills

## Part 2 — The Catalog, Cases 1–21

Every entry below is a pre-registered study that failed, drawn straight from the graveyard
table in `RESEARCH_LEDGER.md`. Each one started as a real hypothesis with a real bar to
clear — not a vibe, a number written down before the backtest ran. Each one died against
that number, or against an adversarial re-check of the number. We've kept the verdict
vocabulary the ledger uses, because the distinctions matter: **REFUTED** means we found the
specific bug that produced the false positive; **FAIL** and **KILL** mean the pre-registered
bar was cleanly missed; **NULL** means the point estimate collapsed to statistical noise;
**INSUFFICIENT**, **NO-SIGNAL**, and **NOT PROMISING** mean the sample or the market
structure never gave the idea a fair trial. That last group is not a disproof, and we don't
round it into one. We are not going to upgrade any of those distinctions for narrative
effect. Where the source hedges, we hedge.

---

## Maker Illusions

The oldest fantasy in market-making is that you can just... rest an order near the edge of
certainty and collect the spread while everyone else does the work. Three studies tested
variants of "wait near the lock, let the fill come to you." All three found that either the
fill wasn't a maker fill at all, or the edge existed only in a version of the past that had
already leaked the answer.

**#1 — Maker (post-lock resting bids): 22.5 claimed fills, 2 real ones.**
The idea was to place resting bid orders after a weather station's outcome had effectively
locked, collecting the bid-ask spread as a passive maker instead of paying it as an
aggressive taker. The backtest claimed 22.5 fills across a 65-day, 20-station sample. A
fill-by-fill audit found 2 confirmed (plus 1 possible) genuine fills. The mechanism that
killed it: 26 of 32 audited bids priced at 93 cents already had a best ask at or below 93
cents at the moment of placement — meaning the "resting maker bid" was actually marketable
on arrival and would have executed instantly as a taker order, never sitting in the book
long enough to earn the maker side of the trade it was credited with. Verdict: REFUTED.

**#2 — Early-lock tail capture: the best cell flipped sign when the data was cut in half.**
The hypothesis was that price behaves predictably in the final stretch before a weather
station's outcome locks, and that a well-timed entry could harvest that tail move. The
headline result looked thin but positive — +1.43 cents, t=0.28 — and the best-performing
cell (requiring at least 5 observations) reached +2.52 cents, t=0.35. Neither clears
anything close to significance on its own, but the real damage came from the multiple-
comparisons math: the grid nominally had 36 cells, but two of the price caps were
byte-identical, so it was really only 27 independent tests, which raises the Bonferroni bar
to |t|≥3.11 — an order of magnitude above what the best cell produced. Worse, that
best-looking cell's sign flipped from +9.6 cents to −8.1 cents across the two halves of the
sample. Verdict: NULL.

**#12 — Near-miss conversion: the market got there 106 minutes before we could look.**
This one targeted a mechanical problem rather than a mispricing: near-misses (markets that
almost but didn't trigger a fill) were being logged, and the question was whether fixing
detection lag could convert more of them into fills. The median lock-to-detection time
looked bad at 410 minutes, but that number mixed in an outage backlog; the steady-state,
feed-bound figure was a much more respectable 8.1 minutes. It didn't matter. In 10 of 10
sampled tickers, the market had already pushed the no-side ask above 98 cents — a median of
106 minutes — *before* the lock rule even fired. Speeding up the watcher fixes a problem
that was never the bottleneck. Of the 52 logged near-misses, roughly 0% were convertible by
any feed, leg, or watcher fix the repo could build; the theoretical ceiling, generously
estimated from the 2 most favorable of 10 close-call samples, was 2–4%. Verdict: NULL.

---

## Directional Weather

`WX_DIRECTIONAL.md` ran nine variations of one question: does anything about weather
forecasts, order flow, or market microstructure predict the *direction* of a coming price
move before the crowd prices it in? Seven numbered specs plus two follow-up variants (R4-1,
R4-2) each got their own pre-registered floor. None cleared it. Three didn't even get
enough qualifying trades to be testable, which the ledger — correctly — still counts as a
kill under the funnel's own pre-registration protocol, not a "maybe next time."

**#3 — SPEC 1: 17 entries, needed 200.**
A baseline directional signal test never accumulated enough qualifying entries — 17 against
a pre-registered floor of at least 200 — because the market itself was only 67 days old at
the time, covering a single warm season. Verdict: INSUFFICIENT, explicitly left open for a
retest once the market has more history behind it.

**#4 — SPEC 2 (MOS revision fade): −$0.0255 per contract, t=−3.16.**
The idea was to trade against revisions in the Model Output Statistics forecast feed. With
815 qualifying entries — a real sample — the mean EV came in at −2.55 cents per contract,
comfortably significant in the wrong direction. An event-versus-control comparison showed
the signal carried essentially zero information beyond an unconditional control: whatever
the revision looked like, it told you nothing the market didn't already know. Verdict:
KILL.

**#5 — SPEC 3 (thin-book longshot): 84 entries, needed 300.**
Restricting to thin-liquidity longshot situations is, definitionally, a filter that starves
its own sample — only 84 entries qualified against a 300-entry floor. Verdict:
INSUFFICIENT.

**#6 — SPEC 4 (intraday nowcast lag): 16.7% win rate against a 21.7% breakeven.**
This spec fit a probability distribution to intraday nowcast behavior on a training slice
(spring/early summer) and tested it out of sample. On 2,109 entries the Wilson lower-bound
win rate came in at 16.7%, well under the 21.7% breakeven the price implied, t=−4.05. The
distribution fit on the training window simply didn't survive contact with the full-summer
warming trend in the test window — a seasonal-drift failure, not a coin flip. Verdict: FAIL.

**#7 — SPEC 5 (order-flow drift): yes-side win rate of 28.9%.**
Trading in the direction of recent order flow sounds intuitive; it lost. Across 525 entries
the Wilson lower bound was 75.4% against an 82.1% breakeven (t=−1.81), driven by consistently
rich entry prices (mean 80 cents, frequently above 95) and a yes-side that was actively
anti-predictive — it won only 28.9% of the time when the signal said "buy yes." Verdict:
FAIL.

**#8 — SPEC 6 (ladder arb): a 19.7% fill rate against a 60% floor.**
A supposed arbitrage across a price ladder needed fills on at least 60% of its legs to be
real; it got 19.7% across 110 attempts. The gap between quoted and fillable prices was quote
staleness and thin-book noise, not a durable mispricing — the bid-ask spread ate whatever
correction the arb was supposed to capture. Verdict: FAIL + INSUFFICIENT.

**#9 — SPEC 7 (salient anchoring): 2 of 5 price bins even reached the sample floor.**
This one tested whether prices anchor to salient round numbers. Only 2 of 5 pre-registered
price bins reached the required 20-sample minimum, and only 1 of those cleared the required
gap threshold (|gap|≥0.04) — nowhere near the 3-of-5 sign-agreement bar the study needed to
call a pattern real. The ledger is explicit that this bar was structurally unreachable from
the training slice available: the idea is not disproven, just never given enough data to be
tested. Verdict: NO-SIGNAL.

**#10 — R4-1 (climate long-lead): the market doesn't exist yet at the horizon being traded.**
This variant wanted to trade 48, 72, and 120 hours before a station's close. At all three
horizons, there were zero two-sided quotes to trade against — because Kalshi's `KXHIGH`
series only lists markets 39–42 hours before close. The strategy failed for the most
structural reason possible: the market it needed hadn't been listed yet. Verdict: FAIL.

**#11 — R4-2 (upwind advection): 0 of 556 theta values cleared breakeven.**
The hypothesis compared a partial-day running maximum temperature to the full-day forecast
max, treating any gap as a signal of upwind weather moving in. None of 556 tested theta
values cleared breakeven. The gap turned out to be a timing artifact — comparing an
in-progress running max to a full-day forecast is comparing two different things by
construction, not detecting a real bias. Verdict: FAIL.

---

## Expansion Families

`WX_EXPANSION.md` took the one mechanism this program had actually gotten to work —
mechanical detection of a market locking near-certain before the crowd's ask catches up —
and asked whether it transfers to markets that aren't weather. Five families were tested;
none cleared the pre-registered $0.05-per-contract bar outright, though one came close
enough to stay on life support.

**#13 — Sports totals: a zero-second window.**
Scoreboard-driven sports totals markets showed a real mechanical shape (median detection
lag of exactly 0.0 seconds) and a small positive EV of $0.0296 per contract — but that's
below the $0.05 bar, and a lag of zero means there was never a window to trade into in the
first place. Faster bots than this one are already watching the scoreboard. Verdict: NOT
PROMISING.

**#14 — Earnings/Gutfeld mentions (Family 2): the survivor, weakened.**
This is the one entry in this section that didn't flatly die. After confirm-gating, EV came
in around $0.05 per contract — six times below the original $0.316 claim, because that
original number carried two look-ahead flaws: it entered at the best price achievable
anywhere in a window (a price no live trader could actually hit), and its own lock detector
(ask ≥ 98 cents) turned out to condition on the answer — 29 of 30 markets that later settled
NO had also hit that same ask≥98c threshold at some point, meaning the "signal" was partly
just recognizing outcomes it had already been shown. What's left, after correcting both
flaws, sits exactly on the pre-registered bar rather than above it. Verdict:
PROMISING-WEAKENED — the only entry in this catalog not fully closed; the ledger elsewhere
prices it at roughly $18/month defensible capacity if a live transcript feed can be proven
to lead the bid, and leaves it open pending that measurement.

**#15 — Earthquake magnitude: 2 qualifying events, ever.**
A market on earthquake magnitude thresholds had a base rate problem before it had a pricing
problem: only 2 real M6.8+ events occurred at a frequency of 0.077 per day. Even where the
mechanism looked sound — USGS revises its magnitude estimate for 10 to 60-plus minutes after
an origin, which sounds like exploitable lag — the market and the feed converge on the same
information at the same pace, leaving no lag to trade. Verdict: NOT PROMISING.

**#16 — Commodity ladders (WTI/NGAS): real mechanism, dead frequency.**
The threshold-ladder mechanism looked genuinely real here — EV of $0.171 per contract,
though that figure is overstated by a settle-print look-ahead baked into the backtest. It
didn't matter, because event frequency was the decisive constraint: 0.038 qualifying events
per day historically, missing the pre-registered 0.5-per-day bar by roughly 13x, and even
2026's better year only reached 0.169 per day. Verdict: NOT PROMISING.

**#17 — Crypto MAX ladders: the market closes itself before you can.**
EV of $0.0414 per contract, below bar, on a capturable frequency of 0.10 per day — already
a soft kill on its own — compounded by a structural one: 46% of the sample allowed the
market to close more than an hour before its official close time (`can_close_early=true`),
collapsing whatever lag the strategy needed to exploit. Verdict: NOT PROMISING.

**#18 — FDA drug approvals: no feed fine enough to trade against.**
Only 2 events were even verified capturable, at a frequency of 0.030 per day — roughly 17
times below the pre-registered bar. The deeper problem is structural: there is no
minute-resolution public feed for FDA approval timing, only a date-level public record,
against which no lag-based mechanism can be timed. Verdict: NOT PROMISING.

---

## Calibration and Stale-Print Artifacts

`DATA_BACKED_BACKTESTS.md` targeted the two places retail intuition says a market should be
mispriced: right at the edges of certainty, and in the long, thinly-traded tail of markets
nobody's watching. Both hypotheses died, and one of them died *harder* after an adversarial
correction meant to give it a fair shake.

**#19 — Weather calibration-fade: the correction made the loss worse, not better.**
The idea was to fade weather markets priced at near-certainty (99–100 cents or 1–3 cents),
on the theory that retail crowds overpay for near-sure things. None of 8 pre-registered
price bins cleared the fit bar. In the two most liquid bins, the original claimed edges were
−1.50 cents (high, 99–100c) and −3.00 cents (low, 1–3c) — both already losses for the
proposed trade. An adversarial correction to the methodology didn't rescue either number; it
made the headline bin's loss worse, to −2.0 cents, while the low bin corrected to roughly
−1.9 cents. The verdict didn't change either way, but it's a useful data point that "let's
re-check this more carefully" cuts against you as often as for you. Verdict: FAIL
(CONFIRMED).

**#20 — Long-tail passive spread: −14.32 cents per contract, t=−29.57.**
The pitch was to passively quote the spread in the thin long tail of markets, on the theory
that low attention means low competition for the spread. Across 39,220 fills over 34 days
and 144 series, the net result was a loss of 14.32 cents per contract, day-clustered
t=−29.57 — about as decisively negative as a number gets in this catalog. Fees explain only
1.77 cents of that loss; the rest is genuine adverse selection realized at settlement. The
"semi-thin" liquidity band this strategy targeted turned out to be dominated by short-lived
proposition markets with informed counterparties, not by genuine attention scarcity waiting
to be harvested. Verdict: FAIL (CONFIRMED).

---

## Illiquid Corners

`ILLIQUID_MARKETS.md` went looking for arbitrage in the market's quietest corners — the
places thin enough that a stale quote or a leg that doesn't sum to 100% might survive
undetected. One study in this range completed; it found nothing to take.

**#21 — Illiquid snapshot arbs: 0 out of 64,829 markets.**
Three variants were tested in one pass: leg-sum arbitrage (buying all outcomes of a market
for less than $1 combined), nested-cutoff arbitrage (exploiting overlapping threshold
markets), and stale-quote arbitrage (trading against a quote that hadn't updated after a
market's effective close). None survived. Bid-side leg-sum mispricings greater than 1 are
fee-negative by construction, because Kalshi's fee scales with Σp(1−p) summed across every
leg in the combination — the more legs you need to complete the arb, the more fee you pay
per leg, and it eats the entire mispricing. And the stale-quote hunt came back empty at
scale: zero of 64,829 active markets showed a stale post-close quote visible in a snapshot.
Verdict: REFUTED.

---

## The Running Theme

Read across all 21 of these, and the same handful of bugs keep reappearing wearing
different clothes. Three are worth naming explicitly, because they recur well beyond this
first batch of kills:

| Artifact family | What it looks like | Where it shows up here |
|---|---|---|
| **Stale last_price / stale-quote** | A backtest treats a market's last recorded print as tradeable, when in reality the quote had gone stale (often on an expire-worthless market where nobody bothered to update the ask). | #21's explicit stale-quote hunt (0/64,829); the ledger itself later ties #19 and #20's calibration/long-tail losses to this same mechanism when it recurs against a five-series shortlist |
| **Best-price-in-window (hindsight entry)** | A backtest lets itself buy at the best price *achieved anywhere in a window*, not the price actually available at decision time — quietly assuming a fill no live trader could get. | #14's original $0.316 claim (corrected to ~$0.05); #16's commodity-ladder EV, "overstated by settle-print look-ahead" |
| **Outcome-conditioned signals** | A "lock detector" or filter is built using information that only exists because the market already resolved — so it looks predictive purely because it's peeking at the answer. | #14's `ask≥98c` detector, which fired on 29 of 30 markets that went on to settle NO — recognizing the outcome, not predicting it |

None of these are exotic. They're the ordinary ways a backtest lies to you if you don't go
looking for the lie. The value of pre-registering the bar before running the study is that
these three families get caught instead of shipped — which, as the next batch of entries
shows, is a discipline this program needed again and again, not just once.
