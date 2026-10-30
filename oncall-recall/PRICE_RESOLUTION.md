# Price: I was wrong twice, in opposite directions. That is the finding. — 2026-10-30

## The record

| turn | price I set | anchor I used | why it was wrong |
|---|---|---|---|
| 1 | **$39** | "TrueLearn ~$300–500/**year**" | misread a **30-day** price as annual |
| 2 | **$59** | TrueLearn $299/30 days | right anchor, **wrong product category** |
| 3 | **$29** | TrueLearn $379/**365 days** = $32/mo | anesthesia-specific *and* continuous |

**Being wrong twice in two turns on the same number is itself the result.** The product straddles two
categories whose prices differ by **30–50×**, so desk research cannot settle it:

| comparable | price | category |
|---|---|---|
| older static AnKing decks | **free** | spaced-repetition deck |
| AnkiHub Core / Premium (live AnKing deck) | **~$6 / ~$10 per month** | spaced-repetition deck ← **our form** |
| TrueLearn anesthesia CME | $379 / 365 days = **$32/mo** | anesthesia-specific, continuous |
| TrueLearn ABA BASIC, 180-day tier | $449 = **$75/mo** | exam-style question bank |
| TrueLearn ABA BASIC, 30-day tier | **$299/mo** | exam-style question bank, cram timing |

Our product's **form** is a spaced-repetition deck — atomic knowledge points with FSRS scheduling. Its
**substance** is question-bank grade: blueprint-structured, with rationales and page citations. The
form anchors at $6–10, the substance at $32–299. I priced off the substance and ignored the form,
which is how I ended up at $59 against a free competitor.

## What this does to the target

| price/mo | subscribers for $4,000 | % of ~7,460 anesthesia residents |
|---:|---:|---:|
| $6 | 667 | **8.9%** |
| $10 | 400 | **5.4%** |
| $19 | 211 | 2.8% |
| **$29** | **138** | **1.8%** |
| $59 | 68 | 0.9% |

**Track C's viability now reduces to one testable question:** will residents pay question-bank-adjacent
prices for a cited deck, or only deck prices? At $29 the target needs 1.8% penetration — optimistic
but ordinary. At $10 it needs 5.4%, and at $6, 8.9% of every anesthesiology resident in the country.
**Those last two are not reachable.**

So the honest statement is narrower than my first one: **Track C reaches $4,000/month only if the
citation differentiator supports pricing near the anesthesia-specific annual tier.** If residents see
it as "a deck," the ceiling is a few hundred dollars a month, not four thousand.

## The threshold was calibrated to a price I had wrong — so it becomes a formula

My frozen rule said **≥100 signups → build**. That was roughly defensible at $59 (68 subscribers
needed). At $29 it is not: 138 subscribers needs far more than 100 signups.

Replacing the number with a rule that cannot drift with my pricing mistakes, **frozen now, before any
signup exists**:

```
signups required  =  (4000 / price_per_month)  /  0.35
```

where **0.35 is the assumed waitlist→paid conversion, declared now** and not revisable after seeing
results.

| price | subscribers needed | **signups required** |
|---:|---:|---:|
| $59 | 68 | 194 |
| $39 | 103 | 294 |
| **$29** | **138** | **394** |

**At $29 the test must produce ~394 signups to justify the 60-hour build.** That is four times the bar
I stated two turns ago, and it is the honest consequence of pricing the product as what it actually
is.

## Decision rule, final and frozen

Landing page is set to **$29/month**.

| signups in 30 days | action |
|---|---|
| **≥ 394** | demand supports $4,000/month. Build. |
| 150–393 | real interest, but a smaller business. Build only if a few hundred a month is worth 60 hours to you. |
| 40–149 | niche. Not a $4,000/month path. Consider shipping free to build goodwill, or stop. |
| **< 40** | **stop.** 8 hours spent instead of 60. |

The 150–393 band is new and it is the honest one: it is the most likely outcome, and it describes a
**real but smaller** product rather than a failure.

## What does not change

The **conversion assumption (0.35) and the four bands above are now fixed.** I have moved the price
three times on new evidence, which is legitimate; moving a threshold after signups exist would not be.
Any further price change recomputes the signup requirement **through the formula**, not by judgement.
