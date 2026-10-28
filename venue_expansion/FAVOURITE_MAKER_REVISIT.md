# Favourite-side maker — the one open thread, with its gate frozen NOW

**Registered 2026-10-28, before the additional data exists.** The point of writing this today is that
the bar cannot be moved once the data arrives and I can see which way it went.

## Why this is the only thread left open

52 studies are closed. This one is **INSUFFICIENT with a positive point estimate**, which has not
happened before — every other "not yet significant" result in this program had a negative or
zero-centred estimate.

`FAVOURITE_MAKER` (Z2 = real two-sided asks 80–99c, N=25 pessimistic fill, T=15):

| k | P(YES\|quoted) | P(YES\|filled) [99.79%] | break-even | filled − quoted (95% day-bootstrap) | fill rate | EV/quoted |
|---|---|---|---|---|---|---|
| 1 | 95.38% | 94.43% [91.91, 96.19] (n=1,113) | 92.96% | **−0.95pp [−1.25, −0.67]** | 83.0% | **+1.223c** |
| 2 | 95.38% | 92.32% [88.92, 94.74] (n=807) | 90.84% | −3.06pp [−4.02, −2.23] | 60.2% | +0.890c |

Best cell overall: **Z2, T=5, k=1, N=25 → +1.81c per quoted contract** (SE 0.85, t=2.13).

**Adverse selection is real** — it runs in the feared direction in **12 of 12 cells in both zones**,
with the day-bootstrap interval excluding zero on the negative side in all 12. The loss-event ratio in
Z2 at T=15 is 1.20 / 1.66 / 2.07 for k=1/2/3, the same magnitude `MAKER_FILL` found from the other
side of the book. **But at k=1 it does not fully eat the edge**: gross per fill is +1.47pp (T=15),
+2.11pp (T=5), +0.12pp (T=30), +0.75pp (T=45).

## Two reasons for strong scepticism, recorded before the re-run

1. **The effect is not monotone in T** (+2.11 → +1.47 → +0.12 → +0.75). Non-monotonicity in a
   parameter that should order the effect is a signature of noise, not structure. If this were a real
   liquidity premium it should decay smoothly with time-to-close.
2. **This program has twice watched "underpowered" become "losing" once there was enough data** — the
   forecast sleeve (flat at n=161, measurably negative at n=620 pre-fix) and early-lock (starved at
   n=0 of economic content, then −0.18/contract at n=14). That is the strongest available prior
   against the positive estimate here, and it is the reason this document exists instead of a
   deployment.

## What settles it, measured

The binding constraint is **calendar days**, not hours — strikes within an hour move together.

| | |
|---|---|
| days in the current window | **60** |
| fills at Z2 T=15 k=1 | 1,113 |
| fills needed for gate 1 at the observed effect | ~2,300 |
| **raw days implied** | **~124** |
| days for the EV t-statistic to reach the 3.22 bar | ~137 (≈0.4 yr) |

Intra-hour correlation lowers effective n, so the honest figure is **more** than 124 days.

**Waiting is sufficient and needs no infrastructure.** Verified 2026-10-28: Kalshi's
`GET /markets/trades` still serves prints with microsecond `created_time` for the 2026-08-22 event —
**67 days old** — so the tape for the intervening period will be fetchable retroactively. No live
collector, no cron, and no push to the default branch is required. (An earlier probe returning zero
trades was a deep-OTM strike that never traded, not a retention limit.)

## The re-run, frozen now

- **When**: once the settled window covers **≥ 130 distinct calendar days** (i.e. roughly 2026-12-30
  or later), re-run `favourite_maker.py` unchanged over the extended window.
- **Universe**: `KXBTCD`, zone **Z2 only** (`80c ≤ yes_ask ≤ 99c`). Z1 is retired — it was 98%
  `yes_ask = 100c`, a price with no resting offer, which was a defect in my original spec.
- **Primary cell, declared now**: **T=15, k=1, N=25.** T=5 had the larger estimate but sits closest to
  the close where the cached candles were thinnest; T=15 is the honest primary.
- **Gates — carried over verbatim from `FAVOURITE_MAKER_SPEC`, not relaxed**: the Bonferroni-adjusted
  99.79% Wilson **lower** bound on `P(YES | filled)` must exceed `mean(d)/100`; the day-bootstrap 95%
  CI for `filled − quoted` must not have an upper bound below −1.0pp; n ≥ 500 fills over ≥ 40 days;
  fill rate ≥ 5%; per-quoted EV > 0 by sign. **No EV t-statistic gate** — the power ceiling makes one
  unreachable, and a gate that cannot be met is a defect, not rigour.
- **Pre-committed reading of the outcome:**
  - gate 1 clears → a separately-registered **1-contract live canary**, ≤$100 at risk, and nothing
    larger.
  - the estimate has **decayed toward or through zero** → the favourite side joins the other 52, and
    market making on this product is closed from both sides of the book. **This is the outcome the
    program's own history predicts** and it must be reported as plainly as a pass would be.
  - still INSUFFICIENT at ≥130 days → **stop**. An effect that needs more than four months of this
    product's full tape to distinguish from zero is too small to survive live queue position,
    competition and operational risk, whatever its sign.

## What is NOT claimed

No profit is established. Gate 1 holds in **0 of 12** cells today. The venue's own participants
already demonstrated they operate at the millisecond scale on this product
(`ARBITRAGE_CLOSED.md`: two-leg fires at the same microsecond), so even a passing gate leaves queue
position as an unmeasured and probably decisive unknown.
