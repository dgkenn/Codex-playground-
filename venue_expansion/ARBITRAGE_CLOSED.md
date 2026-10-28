# Ladder arbitrage: the simultaneous ladder is never crossed — and the edge that does exist is sub-100ms

**Verdict: INSUFFICIENT study-wide. Part A is a clean KILL.** But the useful content is two things the
spec did not anticipate: the trap it forbade would have produced a spectacular false positive, and the
arbitrage *does* exist — in a window this operator cannot reach.

## Part A — zero fee-clearing violations on simultaneous quotes

**1,764,729 executable pair-observations** across 503 hours:

| reading | raw crossings | fee-clearing |
|---|---:|---:|
| `close`, same candle, every leg (**the only PASS-eligible reading**) | 6 | **0** |
| `close` carried across no-candle minutes (disclosure) | 6 | **0** |
| high/low — **NON-SIMULTANEOUS, cannot PASS** | 18,036 | **8,194** |

All 6 simultaneous crossings were **exactly 1c**. Two legs cost at least 2c in fees, so a 2-leg
arbitrage needs a **3c** crossing. All 6 net **−1c**. There is no 2-leg ladder arbitrage.

## The trap, quantified: it would have reported 8,194 arbitrages

The spec forbade the high/low construction because `yes_bid.high` of one strike and `yes_ask.low` of
another are **different instants inside the same minute**. That reading shows **8,194 fee-clearing
"opportunities."** On the same minutes, **98.9% of them are uncrossed by at least 1c at the close.**

Had the simultaneity rule not been frozen in advance, this study would have reported eight thousand
arbitrages that do not exist. This is the single clearest vindication of pre-registration in the
program's record.

## The real finding — and it contradicts the spec's own "no speed needed" premise

Tape sample, 250 of 1,043 high/low opportunities (seeded): **27 (10.8%) show a K1-lifted and K2-hit
pair at inverted fee-clearing prices within 100 milliseconds.** Several are at the **same microsecond
with equal sizes** — one participant firing both legs simultaneously.

So the ladder *does* cross, briefly, while 188 strikes are re-quoted, and **someone already takes it
at millisecond speed.** The spec claimed this edge needs "no forecast, no observation and no speed."
The first two hold. **The third is wrong**, and that is the answer to the standing goal of finding an
HFT-tier stack: the edge requiring exactly that tier exists, is measurable, and is already harvested.

For scale: this program's measured feed stack ran ~10 minutes for weather, and an unprivileged REST
client is tens to hundreds of milliseconds from the venue. The gap to a same-microsecond two-leg fire
is three to six orders of magnitude. **It is not closable by anything in this repo.** The opportunity
was never sized, and sizing it would not change that.

## Part B — partition-sum diagnostic (`KXBTC`, 503 of 503 hours)

- **Buy side:** buying all 188 legs at the ask **never costs below 146c** against a 100c payout. The
  partition is quoted ~46% rich on the ask.
- **Sell side:** selling only the bid-bearing legs exceeds 100c in **60 of 27,137 minutes**; 3 survive
  fees. All 3 fall in one hour (`KXBTCD-26AUG2901`) and their bid-sum is inflated by an 18c bid that
  looks **stale**. Not tape-checked, not tested as a strategy.

## Part C — cross-series, 3 legs

28 opportunities on 15 days out of **482,438 leg-triples**. Median net **1.0c**; all three legs traded
in 32.1%; only **8 of 28 (28.6%)** tape-confirmed. Misses every bar: 28 vs 100, 15 days vs 20, 1.0c vs
2.0c, 28.6% vs 50%, 32.1% vs 50%. The Part C residue is why KILL clause 1 ("zero across the covered
universe") does not fire study-wide.

## Corrections to my own spec

1. **`KXBTC` has 188 markets per hour, not 100.** My probe used `limit=100` and I reported a truncated
   page as the structure. It is still a verified complete partition — exactly one YES in all 503 hours.
2. **"The 100-leg dutch book is dead by arithmetic" was too strong.** It holds for *buying* 188 legs,
   but *selling* needs only the 3–10 legs that carry a bid, so the leg-count argument does not close
   the sell side. The sell side is closed by the stale-bid evidence above, not by arithmetic.
3. **"No speed" was wrong**, per the 100ms finding.

Anchors (a), (b), (c), (d), (f) all hold; the anchor-(a) and anchor-(d) AST scans carry **negative
controls** tested on doctored copies of the module that raise as they should. All 18,048 raw rows show
realised payoff 0 or +100 against official settlement, never negative — the state table is correct.
