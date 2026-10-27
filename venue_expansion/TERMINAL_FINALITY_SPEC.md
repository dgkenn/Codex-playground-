# TERMINAL FINALITY — pre-registered spec (REGISTERED 2026-10-27, before any outcome is read)

## Why this exists — the gap in my own prior work

`EDGE_SIZING_RESULT.md` measured that **~10% of settled weather markets** have a moment in their
final 60 minutes where the eventual winning side is buyable at ≤98c with positive fee-inclusive net.
Stage 2 then measured that the **deployed** lock rule converts **1 of 140 (0.71%)** of those, and
retired the bot on that basis.

That conclusion conflated a rule failure with a market verdict. The same study showed
`locked_orders()` is **asymmetric by construction**: on a bracket rung it can only ever lock NO
(cap-overshoot / floor-undershoot). **It has no code path that can lock YES on a bracket.** Of the 40
highest-net capturable markets, **34 are brackets and 18 settled YES** — a population the deployed
rule cannot address at any feed speed.

Second missed asymmetry: the deployed rule detects a **crossing**, which is inherently
latency-sensitive — hence 0/140 conversion at a 20-minute feed delay. The rule specified here infers
**finality** (the extreme is established; nothing further will happen). Finality is latency-*tolerant*
by nature. The latency curve measured in `LATENCY_EDGE.md` does not transfer to it.

**This spec is not a re-run of a dead idea. It is the first test of a rule shape this program has
never implemented.** It may well fail; the bars below are frozen so that a pass is believable.

## Hypothesis

For a daily-temperature **bracket** rung `[lo, hi]` closing at time `T`: if the running extreme from
observations lies inside the bracket with margin, **and** the extreme is established (the series has
reversed away from it by a margin and held), **and** the remaining window to `T` is short, then the
rung settles YES at high accuracy — and the market still offers the winning side below 98c often
enough to be worth trading.

## Signal definition (obs-only — no price, no outcome, no post-signal data)

For each settled bracket rung, walk the station's observation series in time order. At each
observation time `t` with running extreme `E(t)` (running max for HIGH markets, running min for LOW):

Declare **FINAL-YES** at the first `t` satisfying all of:
1. **Inside with margin**: `lo + M <= E(t) <= hi - M`
2. **Reversed and held**: the series has moved away from `E(t)` by at least `R` degrees and stayed
   away for at least `H` consecutive observations (for HIGH: current temp `<= E(t) - R`; for LOW:
   `>= E(t) + R`)
3. **Terminal window**: `t` is within `W` minutes of the rung's `close_time`

`FINAL-NO` is left to the deployed rule's existing cap-overshoot/floor-undershoot logic and is **not
re-tested here** — it is already measured.

**Parameter grid (frozen):** `M ∈ {0.5, 1.0}` °F · `R ∈ {2, 4}` °F · `H ∈ {3}` obs · `W ∈ {60, 120}`
min → **8 cells**. Primary cell, declared now: `M=1.0, R=2, H=3, W=120`.

## Data (all already verified available)

- **Universe**: settled `KXHIGH*` / `KXLOWT*` **bracket** rungs (`-B` suffix) with an official
  `result` of yes/no and candlestick coverage, closing 2026-05-23 .. 2026-10-20 (the observed
  catalog span; all settled).
- **Outcome**: Kalshi's official `result` field **only**. Never self-computed.
- **Observations**: IEM 1-minute (`asos1min.py`); routine (`asos.py` with
  `report_type=3&report_type=4`) as a disclosed fallback, recorded per market.
- **Prices**: Kalshi 1-minute candlesticks. Winner-side executable cost =
  `yes_ask` if the rung settled YES, else `100 − yes_bid`. **Never `100 − yes_ask`** (that is the NO
  bid, unfillable by a buyer) — this error has already invalidated work in this repo.
- **Fee**: `ceil(7·p·(1−p))` cents at the crossing price.

## Entry rule

Entry is the **first** candlestick at or after the signal timestamp whose winner-side cost is ≤98c
with net > 0. If no such minute exists within the terminal window, the fire is **UNTRADEABLE** —
counted, disclosed, and never priced from an earlier or better print. One contract per fire, held to
settlement. No exits.

## Latency arms (all three reported; the 10-minute arm is the deployable one)

Add a delay `L ∈ {0, 10, 20}` minutes to every signal timestamp before seeking an entry. `L=0` is a
backtest-only reference (IEM's archive publishes 22–34h late). **A live bot would run on MADIS
(~10 min) or Synoptic (~1–5 min), so `L=10` is the arm that decides deployability.**

## PASS / KILL — frozen now

Bonferroni over the 8 cells × 3 latency arms = **24 comparisons**; two-sided α = 0.05/24 = 0.00208,
so the bar is the exact Student-t quantile at p=0.99896 on the realised day-count df (≈3.3 at
df≈60–120). **Signed** t: a negative t clearing the magnitude is evidence for KILL, never PASS.

**PASS** requires ALL of, in the `L=10` arm, in at least one cell:
1. **False-lock rate ≤ 2%** with Wilson 95% upper bound ≤ 5% (a FINAL-YES on a rung that settled NO
   is a false lock)
2. **Fee-inclusive EV ≥ +2.0c/contract**, volume-weighted
3. **Signed day-clustered t ≥ +3.3** (exact quantile at realised df)
4. **n ≥ 100 priced fires across ≥ 40 distinct days and ≥ 10 stations**
5. **Untradeable fraction ≤ 70%**

**KILL** if: false-lock rate > 5% in the primary cell (the finality inference is simply wrong); or
every cell with EV > 0 fails the n floor; or the `L=10` arm's best one-sided 97.9% upper bound on EV
is < +0.5c (no economically relevant edge survives realistic latency).

**Anything else → INSUFFICIENT.** No bar in this document may move after 2026-10-27.

## Mandatory sanity anchors (each must hold or the result is void)

- **(a) Oracle reconciliation**: the set of rungs this rule fires on must be a **subset** of the
  capturable set `EDGE_SIZING` already identified, on the overlapping window. If it fires on rungs
  the oracle says were never capturable, the price join is broken.
- **(b) No look-ahead**: the signal must be computable from observations with timestamp `< t` only.
  Assert it in code and show a worked example.
- **(c) Monotonicity sanity**: running max must be non-decreasing and running min non-increasing
  within a market's local day. A violation means the day-window or timezone handling is wrong.

## Interpretation, frozen in advance

A PASS here is **necessary but not sufficient**. It would establish that a capturable, latency-
tolerant population exists — not that this operator can bank it. Depth is known to be adequate
(median 506 contracts ≤98c, measured 2026-09-30), so the remaining unknowns after a PASS are
competition and queue position at the moment of entry. The only permitted next step on a PASS is a
separately-registered 1-contract live canary, never a scaled build.
