# Forty-Two Kills

## Part 1 — Introduction and Methodology

### 1. The punchline, up front

Over roughly a year, we pre-registered 42 trading studies against Kalshi, Polymarket, and — in
a late cameo appearance — ForecastEx. All 42 died: 42 pre-registered strategies, 42 verdicts of
dead, refuted, null, insufficient, or fee-negative, each one nailed to a specific number and a
specific mechanism rather than a shrug.

One definition first, because the rest of this publication depends on it. "Died" here means
*closed without a deployable edge for this operator* — it does not mean every hypothesis was
disproven. The catalog keeps three kinds of death separate and never merges them: a measured
negative (the number came back on the wrong side of the bar, significantly), a miss (the number
was computed and cleanly failed the pre-registered floor), and an insufficiency (the study never
reached its own frozen sample bar, so its underlying question is still open — we just aren't
allowed to call that a win, and neither is anyone else). Several entries here are of the third
kind and say so; one (#14) survives as a weakened, unproven residue rather than a corpse. What
none of the 42 produced is a positive result that survived verification and could be traded.

None of that is a confession. It's the finding. A retail-scale bot — free data, a bankroll that never
exceeded five figures, and (for most of the year) a scheduler that woke up on a cron tick instead of
sitting on a socket — was tested against Kalshi's and Polymarket's prediction markets across every
strategy family we could construct: maker rebates, taker mechanics, directional forecasting,
favorite-longshot bias, near-miss conversion, cross-venue arbitrage, latency races, calibration
fades, ensemble-probability edges. Every one of them either wasn't there, wasn't reachable at
retail execution, or evaporated the moment we insisted on paying the fee and crossing the real
spread. The one mechanism that did work — a mechanical lock on Kalshi weather markets, buying a
rung once a sustained, margin-cleared temperature extreme had settled the outcome before the book
caught up — backtested at +1.1¢/contract with a ~99.6% win rate. Deployed live with a $10 canary,
it produced zero fills in its first four days against 189 logged near-misses, every single one
already priced to the payout ceiling before our detector could act. That's not a bug. That's the
market repricing faster than a retail-tier detector could act on it — measured over four days and
189 near-misses, not proven as a law — and it is the shape this publication finds forty-two
different ways.

We use a single number as the honest scoreboard throughout: **$4,000 a month.** Not because it's
an arbitrary round figure chosen for drama — it was the operator's stated target for what this
research program needed to produce to be worth running. We never hit it. At the most optimistic,
best-case, assumption-heavy reading of every sleeve that ever showed a positive number, the model
tops out around $1,173/month (29% of goal), and that figure is explicitly flagged as depending on
accrual rates nobody has actually observed. The number we'd actually defend, based on live fill
behavior rather than backtest assumption, is $146–149/month — under 4% of goal. Keeping that
target visible on every page is what keeps this honest: it is very easy to write a research report
that quietly redefines success down to "we found a statistically significant coefficient." $4,000
a month is a business bar, not a p-value, and nothing in this catalog clears it.

### 2. The venues and the toolkit — three attempts, increasing sophistication

This is not the record of one naive pass at prediction markets. It's three, each more capable than
the last, and each one still came back empty.

**Kalshi** was the primary venue throughout — CFTC-regulated, dollar-settled, and the one place we
ever had live capital at risk (a canary-sized weather taker position). Its weather markets
(`KXHIGH*`/`KXLOWT*`), its crypto hourly Up/Down markets (`KXBTC`/`KXETH`), its sports moneylines
(`KXNFLGAME`), its macro-release brackets (`KXCPI`, `KXJOBLESSCLAIMS`), and its long tail of
roughly 289 climate-and-weather series were all in scope at one point or another. **Polymarket**
got the same treatment as the zero-fee, globally-listed counterpart — favorite-longshot bias, a
weather-ladder mechanics search across 51 cities that stayed unresolved rather than closing (real
signal coverage on Chicago's own 1-minute feed, but never a confirmed EV), cross-venue arbitrage
against Kalshi's crypto brackets — with the standing caveat that the global venue is geo-blocked to
US persons, so even a positive result there was never a deployable one for this operator.
**ForecastEx**, IBKR's CFTC-regulated Forecast
Contract exchange, got a late, narrower look: one candidate mechanism, one pre-registered spec,
one kill (case #38, and it's a genuinely interesting one — see Part 3).

The infrastructure evolved underneath all three. For most of the program the bot ran the way most
retail systems do: a GitHub Actions workflow on a cron schedule, cold-starting a subprocess for
every signing operation, reading free public feeds (NWS ASOS/CLI data via the Iowa Environmental
Mesonet, Open-Meteo forecasts, Kalshi's own public candlestick and trade-archive endpoints, a
160-million-row Hugging Face trade archive). That is genuinely retail-tier: no colocation, no paid
data, no persistent connection. Late in the program we built and verified something categorically
different — a warm, persistent-process, same-region execution stack — specifically to answer the
question of whether the retail bot's own latency was the reason nothing worked. It wasn't a toy
benchmark: every number in that stack is measured, not assumed. A cold subprocess-per-call pattern
cost 255–354ms; a warm process with the signing key already in memory cost 0.37–0.68ms — a
roughly 500–650× tax the old architecture was silently paying on every single order attempt. Wired
together, the whole stack landed comfortably inside the reaction budget the underlying economics
actually required, for about $5–20/month on a small cloud instance (the measured floor and the
margin are in Part 4, which is where that stack is worth reading in full). "HFT hedge-fund tier"
execution turned out to be "barely necessary" — the honest conclusion, spelled out plainly in the
engineering writeup, is that speed was never the constraint. The strategy the stack was built
for (crypto maker capture) failed its own validation anyway, on stability grounds that had
nothing to do with milliseconds. We tested at three levels of sophistication — naive cron bot, informed cron bot,
verified low-latency bot — and the market didn't care which one showed up.

### 3. THE METHOD

If you take one thing from this publication and apply it elsewhere, take this section. Everything
that follows in this catalog is a strategy dying against a fixed set of rules that were written down
*before* any test data was read, and the rules are more interesting than any individual kill.

**Pre-registration before test data.** Every study here has a frozen hypothesis, a frozen success
bar, and a frozen split between the data used to tune it and the data used to judge it, written down
before the judging data was touched. This sounds obvious and is routinely not done. The clearest
demonstration of why it matters shows up in the reopen funnel late in the program: four re-attempts
at old, data-starved kills were registered with bars frozen in advance, and when the archive turned
out to unlock roughly 50× more raw coverage than the original studies had, the number of *usable,
executable-price* entries went *down* — 5 versus the original 17, 12 versus the original 84 — because
the newly-imposed discipline of requiring an actual transacted crossing print, not a quoted snapshot,
turned out to be the binding constraint all along. Had the bar not been frozen first, it would have
been extremely tempting to relax "executable print" back to "quoted price" the moment the sample
came up short, and the result would have quietly reintroduced the exact artifact — pricing signals
off quotes nobody could actually trade — that killed several earlier entries in the first place.

**Frozen bars that never move.** Related, stated separately because it's the discipline that makes
pre-registration mean something under pressure: once a significance threshold, a minimum sample
size, or a Bonferroni correction is set, it does not move even when the realized data lands just
short of it, and even when moving it would turn a kill into a headline. The reopen funnel's
macro-surprise re-test needed ≥40 validation events after Bonferroni correction; it reached 31,
strictly below the frozen floor, because the fit window predates half of the six registered
macro-release families entirely (jobless claims and ISM PMI markets among them, both of which
simply hadn't launched yet). The honest verdict is "insufficient, not tested" — not a relaxed bar
and a manufactured null.

**Fee-inclusive EV at executable prices — never mid, never last.** This single rule kills more
studies in this catalog than any other. Kalshi charges `ceil(7·p·(1−p))` cents per contract;
Polymarket charges `0.05·p·(1−p)` in USDC, taker-only. Both get applied at the actual crossing
price — the ask you'd lift buying, the bid you'd hit selling — never at the market's last trade or
midpoint, because those proxies systematically flatter an edge that a real order could never have
captured. Case after case in the graveyard is exactly this artifact: a naive signal looked real
against `last_price`, and evaporated the moment it was repriced against the spread it would have
actually had to cross.

**Day-clustered t, Wilson confidence intervals, Bonferroni over every spec in a funnel.** A trading
signal that fires 500 times in three calendar days is not 500 independent observations — it's three,
and the day-clustered t-statistic says so, often collapsing an eye-catching per-trade significance
down to noise. Win-rate claims get a Wilson interval, not a normal approximation, because many of
the interesting samples here are small and near the edges (0 false locks out of 745, for instance).
And when a funnel tests four or ten or 946 candidate specifications at once — as the executable-price
universe screen did, testing 946 unit-side hypotheses simultaneously — the significance bar is
Bonferroni-corrected across the whole funnel, not per test. That screen found 19 "significant"
survivors against roughly 0.002 expected by chance under the null — genuinely not noise — and every
one of them turned out to be either the cost of crossing the spread, restated, or an instrument that
had stopped trading before the validation window even opened.

**Strict settlement provenance — the venue's own result, never self-decided.** A study is not
allowed to compute its own idea of who won. Verdicts come from Kalshi's own `result` field, or
Polymarket's own resolved `outcomePrices == 1.0`, full stop. This rule alone caught the single most
consequential bug in the entire program, worked below.

**Independent blind replication builds.** For load-bearing results, two builders work from the same
frozen specification without seeing each other's code, and their numbers have to reconcile — often
to four decimal places — before a verdict is allowed to stand. The crypto maker-viability study (case
#42, the last kill of the year) ran two blind builds plus an independent mechanical recompute plus
an adversarial review gate, and the positive pool of maker EV they jointly confirmed (+0.76 to
+1.25¢/contract — explicitly a front-of-queue, pool-average *optimistic bound*, not a number any
strategy is entitled to capture) still died, because the two builds' temporal-stability checks
agreed the "good" regime was in opposite halves of the sample for each asset.

**Adversarial verification whose default posture is that a positive is a bug.** Every result that
looked survivable got handed to an independent reviewer whose job was to find the reason it wasn't
real — a stale-print artifact, a look-ahead, a mislabeled fee, a sign error — before it was allowed
into the record as anything other than "unverified." Several kills in this catalog exist *because*
that reviewer overrode a builder's own optimistic read: a "no signal" self-kill on a macro-surprise
study got overridden to the more precise "never actually tested," because the statistic the builder
used to declare no-signal turned out to carry zero information about the hypothesis in the first
place.

**The worked example — the forecast sleeve.** In late July, the paper-trading forecast sleeve
reported the single best-looking number this entire program ever produced: **+$0.19/contract**
over 261 settled forward trades, day-clustered **t = 8.8** — the kind of result that, reported
without the machinery above, would look like a real edge. Running it through the process above
took four steps, each one shaving the number down:

| Arm | EV/contract | day-clustered t |
|---|---:|---:|
| (a) As the sleeve logged it | **+$0.1905** | +8.81 |
| (b) Naive NO-side cost fix (still wrong) | +$0.0892 | +9.94 |
| (c) True executable cost, sleeve's own self-scored outcomes | +$0.0739 | +8.84 |
| (d) True cost **+ Kalshi's official settlement** | **−$0.0526** | **−3.38** |

Step (b)/(c) fixed a real accounting bug: the code charged every NO contract the cost of a YES
contract, a known, previously-flagged, never-patched error. Fixing it *shrank* the apparent edge
but kept it positive — execution realism was not, in this instance, what killed the sleeve, which
is itself worth noting since it's the mechanism that killed several other studies in this catalog.
The fatal step was (d): reconciling the sleeve's self-declared wins and losses against Kalshi's own
official `result` field turned up a settlement-boundary off-by-one — the sleeve's own bracket logic
excluded a rung's lower bound, while Kalshi's actually includes it — and that single bug had scored
**37 of 261 trades (14.2%) against the wrong outcome, every one of them in the same direction.**
Fixing it alone flips the whole sample from a statistically overwhelming positive to a
statistically overwhelming negative. The live money path, for what it's worth, never touched this
particular bug — it uses a different, margin-buffered comparison that structurally can't land on
the exact boundary — but the paper sleeve had been quietly logging a fake edge for days before
anyone checked it against the venue's own truth. That's the entire argument for every rule above,
compressed into one worked example: a genuinely well-intentioned, live-running system produced a
t = 8.8 headline number entirely out of two bugs, and the only reason we know that is that
checking against ground truth was a non-negotiable step, not an afterthought.

### 4. Reader's guide to the catalog

What follows is organized as a graveyard, not a chronicle — each entry gets a strategy, a study, a
verdict, a key number, and the specific mechanism that killed it, in the same format used
throughout the underlying research ledger. Read it in whatever order serves you; the entries are
independent, but a few threads recur enough to be worth watching for as you go:

- **The stale-print family.** A remarkable number of "significant" findings across very different
  strategies — calibration fades, long-tail passive spreads, a 144-series universe screen, even a
  legacy index-market artifact inside the final executable-price screen — turn out to be the same
  underlying mechanism: a `last_price` or mid-price observation frozen on a market that had
  effectively already settled. It appears early, and it appears again near the very end, on a
  supposedly novel instrument, because the discipline of checking for it is not automatic — it has
  to be re-applied every time.
- **The spread-eats-it family.** Favorite-longshot bias, near-miss conversion, and the final
  universe-wide executable-price screen all found a real, statistically genuine mispricing that
  simply cost more to capture than it was worth — the fee and the crossing spread consistently ate
  signals that looked clean at quoted prices.
- **The venue-axis closures.** The catalog systematically closes off entire axes rather than just
  individual strategies: single-venue Kalshi at every granularity (universe, category, series,
  taker and maker), single-venue Polymarket at 1,447 tradeable-price markets, cross-venue arbitrage
  between the two, a full latency-relaxation sweep from 1 second down to 1, and — arriving late — a
  second, CFTC-regulated US venue in ForecastEx. Each closure is a chapter, and each one ends the
  same way: no edge this operator could reach at the prices it could actually trade. That is a
  claim about a retail-scale taker and maker working from free data — not about every participant
  in these markets, and specifically not about anyone standing somewhere in the queue, the fee
  schedule, or the data pipeline that this program never occupied.
- **The self-caught bugs.** At least a handful of the 42 kills involve us finding our own error
  before anyone else could — a mis-set shard constant that hid 44% of a trade archive, a family-
  conflation regex that blurred unrelated markets into one series, a strike-sign parser that read a
  negative number as positive, the settlement off-by-one above. None of them resurrect an edge. All
  of them are disclosed, because a research program that only publishes the mistakes it didn't make
  itself isn't publishing an honest one.

The number at the top of every page is still $4,000 a month. It never got any closer.
