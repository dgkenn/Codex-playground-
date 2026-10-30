# Strategy set for $4,000/month — 2026-10-30

## The finding that changes the scope

I spent 56 studies answering "$4,000/month **from Kalshi**." The goal was "$4,000/month." Those are
different questions, and the arithmetic I should have run first settles the first one:

**Even if every remaining gate clears, the measured ceiling is ~$355/month.**

| | |
|---|---|
| measured edge | +1.47c per filled contract |
| fills/day on BTC favourites | 46 |
| defensible size (vs the assumed `N=25` queue) | 25 contracts/quote |
| **ceiling** | **~$355/month**, with ~$1,069 of bad-day notional |
| **as a share of $4,000** | **9%** |
| breadth needed to close the gap | 11× — **measured negative** by `WIDE_SPREAD_MAKER` |

So the trading program is not a path to $4,000/month **even on success**, and that is a stronger claim
than "the probability is low." Combined with the ~8% odds the edge survives December at all, its
honest expected contribution is **a few dollars a month.**

## What $4,000/month actually requires

| source | requirement |
|---|---|
| Money market / T-bills (~4.5%/yr) | **$1,066,667** capital |
| Diversified equities (~8%/yr) | **$600,000** capital |
| Aggressive managed (~12%/yr) | **$400,000** capital |
| Elite hedge fund (~20%/yr) | $240,000 capital |
| Subscription product @ $40/mo | **100 subscribers** |
| Subscription product @ $60/mo | **67 subscribers** |
| Consulting @ $200/hr | **20 hrs/month** |
| **Trading program, full success** | **$355/mo (9% of target)** |

## The strategy set

### A — Finish the trading program to its honest ceiling. EV ≈ $3/month.

Not because it reaches the goal, but because the compute is already spent and three steps are cheap:

1. **~50c pre-flight** — one 1-contract NO order reconciled against `/portfolio/positions` to prove
   `side="ask"` is short-YES. Worth doing regardless; nothing offline can verify it, and a sign error
   there is the most expensive latent bug in the repo.
2. **Depth collection** (needs `main` permission) — replaces the assumed queue position and decides
   the last motivated cell, `k=0` at the touch.
3. **December re-run** at ≥130 days — decides whether the edge exists at all.

**Recommendation: do step 1, authorise step 2, wait for step 3. Fund nothing.**

### B — Capital at market returns. Solves the goal if the capital exists.

$4,000/month is **0.33%/month on $1.07M** (T-bills) or **0.67%/month on $600K** (equities). At that
scale the target is not a trading problem at all and prediction markets are the wrong instrument —
they have no risk premium to harvest, which is precisely what `CATALOG_CALIBRATION` measured (0 of 280
cells mispriced in the profitable direction).

**This is the only strategy here that is already solved, conditional on one fact I do not have: your
capital.** At $10K, $4,000/month is 40%/month and no honest strategy delivers it — not from me, not
from this repo, not from anyone selling a system that claims otherwise.

### C — The product already in this workspace. 67–100 subscribers.

This session exposes a **built medical-education platform** — 29 tools covering illness scripts,
dosing drills, spaced-repetition review queues, mastery gates, knowledge-point tracking, contrastive
cases, a student dashboard and retrieval over clinical sources — alongside ICD-10 and PubMed
infrastructure.

$4,000/month is **67 subscribers at $60** or **100 at $40**, which is squarely the price band
medical students already pay for question banks and spaced-repetition tools.

I am not assuming this is yours to sell or that you want to, and I have not touched it. But measured
against a trading ceiling of $355/month at <1% odds, **it is the most plausible path to the target
visible anywhere in this workspace, by a wide margin.** If you want it assessed as a product — what
exists, what is missing for a paid tier, what the realistic subscriber math looks like — say so and
I will.

### D — The skill this repo demonstrates. 20–40 hrs/month.

56 pre-registered studies with frozen bars, blind replication, adversarial verification, AST-based
negative controls, Wilson and Bonferroni correction, and day/event-clustered inference — including
**five defects caught in my own specs** by that apparatus. That is a quantitative-research portfolio,
and $4,000/month is **20 hours at $200** or **40 at $100**.

The repo is the artifact. It would need to be made presentable (the research log reads as an internal
record, not a portfolio), which is a bounded piece of work.

## What I need to proceed

**One number and one permission:**

1. **Your capital.** It decides whether strategy B already solves this or is unavailable. Nothing else
   changes the answer as much.
2. **`main`-branch permission**, for the depth collection in step A2.

Without the capital figure I would default to: **do A1 and A2, stop expecting anything from trading,
and put the real effort into C or D** — because those are the two strategies whose arithmetic actually
reaches $4,000/month.

## What I will not do

Keep generating studies against a space I have measured closed. Study #57 on this venue would cost
real tokens and return a result I can already predict, and presenting it as progress toward $4,000/month
would be dishonest. The honest summary of 56 studies is: **Kalshi is efficient to within its
transaction costs, and its transaction costs are larger than any edge an outside participant can
reach.**
