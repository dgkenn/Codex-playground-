# Premise check: the two numbers Track C rests on — 2026-10-30

Track C's whole case is "103 subscribers at $39 = $4,017/month, which is 1.6% of one specialty." That
sentence has two unverified inputs, and I built an argument on both without checking either. Checked
now, before the demand test goes live, because a landing page priced off a wrong anchor wastes the
test.

## Premise 1 — market size. My estimate was **conservative**.

| | |
|---|---|
| 2026 NRMP Match, anesthesiology PGY-1 positions | **1,865** (all filled) |
| plus PGY-2 Advanced / Physician-R | 306 / 119 → **2,290 total positions** |
| 4-year residency → steady state in training | **~7,460** |
| what I claimed | ~6,500 |

**103 subscribers is 1.4% of the pool, not 1.6%.** Slightly easier than stated.

*Caveat, stated because it matters:* ACGME's total-in-training figure did not surface. Multiplying
first-year slots by four is **my arithmetic, not a sourced total** — it ignores attrition, the
Physician-R entry path and fellows. Treat ~7,460 as an order-of-magnitude figure.

## Premise 2 — price anchor. **I was wrong, and badly.**

I wrote: *"TrueLearn and M5 anesthesia board banks run roughly $300–500/year (~$25–42/mo), so $39/month
is defensible rather than aspirational."*

Verified TrueLearn listings:

| product | listed | monthly equivalent |
|---|---|---|
| ABA BASIC SmartBank | **$299 / 30 days** | **$299** |
| ABA BASIC, longer tier | $449 / ~180 days | $75 |
| Anesthesiology CME SmartBank | $379 / 365 days | $32 |
| Anesthesiologist Assistant (NCCAA) | $249 / 30 days | $249 |

**$299 is for thirty days, not a year.** I read a 30-day price as an annual one and concluded $39 was
near the ceiling. The truth is the opposite: the incumbent's exam-prep tier runs **$75–299/month**,
its year-long CME tier **~$32/month**, and **$39/month sits just above the annual tier while
undercutting the cram tier by roughly 8×.**

*Caveats:* these snapshots are ~64 days old and 2026 pricing is unconfirmed; one third-party review
claims $99–200 per QBank, which conflicts with the vendor's own pages and which the search flagged as
unreliable. Confirm on truelearn.com before setting a final price.

## Corrected arithmetic

| price/mo | subscribers for $4,000 | % of ~7,460 | vs the 30-day incumbent |
|---:|---:|---:|---|
| $39 | 103 | 1.4% | ~7.7× cheaper |
| $49 | 82 | 1.1% | ~6.1× cheaper |
| **$59** | **68** | **0.9%** | ~5.1× cheaper |
| $79 | 51 | 0.7% | ~3.8× cheaper |

## What this changes

1. **There is real pricing headroom.** $39 was chosen against a mis-read anchor. At **$59** the target
   needs **68 subscribers — under 1% of anesthesiology residents alone** — while still undercutting
   the incumbent's 30-day price about fivefold.
2. **The demand test should probably price at $59, not $39.** Testing too cheap is the more expensive
   mistake: it inflates signups, understates willingness to pay, and you cannot raise the price on
   people who joined at the lower one. The `DEMAND_TEST.md` fallback band already retests downward at
   $29, so the asymmetry is covered in the direction that matters.
3. **The incumbent's structure is a product insight, not just a price.** TrueLearn's expensive tier is
   **30 days** — it is sold for the month before an exam. A year-round, cited, spaced-repetition deck
   priced monthly is a different purchase (continuous rather than cram), which supports the on-call
   wedge over a board-prep framing.

## Recommendation

Change the landing page price to **$59/month** before posting, and leave the frozen decision rule
untouched: **≥100 signups → build; 50–99 → retest at $29; <50 → do not build.** Changing the price is
a correction to a verified error in an input. Changing the threshold after seeing results would not be,
and will not happen.
