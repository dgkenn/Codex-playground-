# Independent verification of study #44 — findings, including two spec-writing errors of mine

A third agent was tasked only with attacking study #44's two builds. It did not take either build's
word for anything: it wrote an **independent third build** (`build_C.py` / `build_C2.py`) reading
only the raw caches and importing nothing from `finality_A.py`, `finality_B.py` or
`edge_sizing_v2.py`, then reconciled all three.

**Result: both builds upheld. Severity of findings: material.** The verdict `INSUFFICIENT` stands,
and the verifier's own recommendation is to retire.

## Three-way reconciliation (A / B / C)

| quantity | A | B | C (independent) |
|---|---|---|---|
| false-lock rate | 22.4% | 23.8% | **23.76%** |
| Wilson UB | 24.1% | 25.0% | **25.00%** |
| untradeable @L=10 | 62.5% | 66.6% | **66.3%** |
| EV volume-weighted | −1.36c | −1.16c | **−1.17c** |
| EV equal-weight | −0.74c | −0.67c | **−0.67c** |
| signed day-clustered t (vw) | −3.46 | −2.21 | **−2.28** |
| days / stations | 151 / 20 | 147 / 24 | 147 / 24 |

C reproduces B exactly and A to within one rung (3,900 vs 3,899). The apparent A-vs-B fire gap
decomposes completely: (i) **274 fires from four stations missing from A's `SERIES_MAP`** (SAN 65,
SDF 66, TTN 81, EWR 62 — exactly the 1,800-rung universe difference, 24,156 + 1,800 = 25,956), and
(ii) ~560 fires from the **feed-qualification threshold, which my frozen spec never specified**
(A: ≥600 one-minute obs; B: ≥1000 obs AND ≥65 in the final 130 min). Item (ii) is spec
under-determination, not error in either build.

Literal spec reading: **A = 0, B = 0, C = 0 fires** in all 8 cells × 3 arms under *both* feed rules.
All 66,824 cached bracket rungs have `cap_strike − floor_strike = 1.0`, verified against the venue.

## SPEC ERROR #1 (mine) — the empty interval

Already recorded: `lo + M <= E <= hi - M` is empty at M=1.0 and needs a half-degree extreme at
M=0.5, on whole-degree data. The pre-registered primary cell genuinely has n=0.

## SPEC ERROR #2 (mine) — the price join was outcome-conditioned, and would have faked a PASS

This is the serious one and I had not noticed it. My frozen text said:

> winner-side executable cost = `yes_ask` if the rung settled YES, else `100 − yes_bid`

That is **conditioned on the outcome**. Implemented literally, it buys the NO side on every rung
that settled NO — making **every fire a winner by construction** and producing a large fake PASS.

Both builds deviated from the frozen text, correctly and with disclosure (`finality_A.py:27-30` D2;
`finality_B.py:912`), charging `yes_ask` on every fire with `pnl = −(ask + fee)` on a false lock.
The verifier hand-recomputed 5 fires from raw candlesticks: timestamp, ask, fee and pnl match 5/5;
entry volumes 400/400; `100 − yes_ask` is used nowhere. The oracle functions do use
`100 − yes_bid`, which is correct there because an oracle is explicitly an oracle.

So two independent Sonnet builds each caught and refused to implement a bar that would have handed
me the answer I was looking for. That is the only reason this study is not a false positive.

**Scope check:** this defect is isolated to `TERMINAL_FINALITY_SPEC.md`.
`FINALITY_NO_LADDER_SPEC.md` and `BOUND_RESOLUTION_SPEC.md` both price the NO side
*unconditionally* on the signal's direction, never on the realised outcome, so neither carries it.

## SPEC ERROR #3 (mine) — the KILL clause was shielded by its own noisiest cell

All three KILL disjuncts were blocked, and *how* they were blocked is itself the finding:

1. "false-lock > 5% in the primary cell" — disabled by my own arithmetic defect (primary cell 0/0).
2. "every cell with EV>0 fails the n floor" — **vacuous**: 0 of 24 cell-arm combinations has EV>0 on
   either weighting, so no such cell exists to fail anything.
3. "best one-sided 97.9% EV upper bound at L=10 < +0.5c" — does not fire: best is +1.46c (C) /
   +0.61c (A). **But only because that cell is 85% untradeable**, so it carries the widest standard
   error while its point estimate is *negative* (−0.41c, t=−0.45).

> The noisiest cell shields the hypothesis from its own KILL clause.

The verifier refused to read KILL anyway, because that would mean moving a frozen bar — the one
thing a verifier must not do. Hence `INSUFFICIENT` with an explicit retire recommendation. A future
spec's KILL clause should be written on a **precision floor**, not on an unqualified upper bound.

## THE DECISIVE ARITHMETIC — why more months cannot help

Measured independently from raw obs and `expiration_value`:

- IEM 1-minute day extreme reproduces the official value on **46.4% of HIGH days** (n=2,015) and
  **82.5% of LOW days** (n=2,013); routine METAR is worse on HIGH (33.6%).
- The HIGH error splits ~50/50 between 0 and +1 °F (935 at 0, 1,003 at +1), so **no constant
  calibration fixes it** — best achievable accuracy under *any* constant shift is **49.8%**.

And the economics of the only tradeable band (ask 90–98c, where the market agrees with the signal):

| | |
|---|---|
| all-in cost | ~97.6c to win ~2.4c |
| break-even win rate | **97.9%** |
| win rate needed to clear the frozen +2.0c/ct bar | **99.60%** |
| measured accuracy there | **97.9%**, Wilson [94.7%, 99.2%] |
| realised profit across those 190 trades | **59 cents on $183.51 deployed** |
| effect of one more adverse settlement | flips the subgroup to **−39c** |

The required 99.60% lies **above the upper end of what the data permits**, and additional months push
that upper bound *down* toward 97.9%, i.e. further from the requirement. A feed delivering ~50% error
against a required ~0.4% error is a two-order-of-magnitude gap. This is arithmetic, not pessimism.

## Adverse selection, quantified

Conditional on being tradeable at L=10, the false-lock rate rises from **23.8% unconditional to
58.2% priced**. At the first quote after the signal: the 99–100c bucket (n=1,437) is right **99.9%**
of the time and is excluded by the ≤98c gate; the 0–49c bucket (n=486) that *passes* the gate is
right **1.6%** of the time. The priced population is dominated by ~1c lottery asks (mean cost 41.4c,
win rate 41.8%). My ≤98c gate performs no economic screening, and this failure mode appears nowhere
in the frozen bars.

## The one positive slice, and why it is not an edge

Entries at ask 80–89c, pooled across cells on distinct rungs: n=60 over 46 days, **93.3% win rate,
+6.80c/contract**, day-clustered t = **+2.22** against a 3.14 Bonferroni bar. Its Wilson 95% lower
bound on the win rate (**84.1%**) sits *below* the **86.0%** break-even at that cost, so EV at the
lower bound is **−1.93c**. B's ask≥90c variant is worse: n=190, EV +0.311c, t=+0.30.

Both are post-hoc price buckets found after 24 pre-registered comparisons, 2 readings and 2 feed
rules were already spent. Not results.

## Defects reported and deliberately NOT patched

The verifier declined to edit analysis code after outcomes were known, because that would
desynchronise the scripts from the on-disk outputs. Correct call. Recorded for future builds:

1. `finality_A.py:112-136` — `SERIES_MAP` omits SAN, SDF, TTN, EWR: 1,800 rungs, 274 fires untested.
   Disclosed by A, immaterial to the verdict.
2. **No physical-plausibility filter on parsed temperatures.** 11 event-days have
   |feed extreme − official| > 5 °F, including **LAX 2026-05-24 reporting a 120 °F max and a −29 °F
   min on the same day**, and **MDW 2026-07-07 a −1 °F July min**. ~0.3% of rungs — immaterial here,
   but *"it would corrupt any future LOW-market build, since a spurious low reading pins the running
   minimum."* **Relayed to the running `BOUND_RESOLUTION` study**, whose monotone `BMAX` has exactly
   this exposure and whose registered corroboration guard is supposed to catch it.
3. **331 of 517 priced entry minutes have zero volume**, so the volume-weighted statistic —
   load-bearing for PASS criterion 2 — effectively rests on ~186 observations, and a zero-volume
   entry minute is a doubtful fill in the first place.
4. `finality_A.py:397` uses a 1e-9 epsilon on a frozen inequality, undisclosed. Harmless here.
5. Minor residual look-ahead: `finality_B.py:317-328` `pick_source` selects the feed from whole-day
   coverage counts, which include post-signal minutes. In population construction, not in the
   signal; cannot manufacture profit.

## What I take from this

Three of the material findings are errors in specs **I** wrote, one of which would have produced a
false PASS had either build followed my text literally. The process caught them because the builds
were blind to each other and a third agent was paid to attack both. That is the part of this program
worth keeping.
