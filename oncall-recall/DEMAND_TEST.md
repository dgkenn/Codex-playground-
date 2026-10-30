# Demand test — runbook. Frozen 2026-10-30, before any signup exists.

The landing page is built: `oncall-recall/index.html`, published for review at
https://claude.ai/artifact/49R2MzpWQoSaAYUqwVN6b4 (private — only you can open it until you share it).

This is the 8-hour gate on a 60-hour build. **Freeze the decision rule before posting**, for the same
reason every study in `venue_expansion/` froze its bars first: once signups are visible, the
temptation to re-read the threshold is overwhelming.

## Decision rule — frozen now

| signups in 30 days | action |
|---|---|
| **≥ 100** | demand is real at 1.6% penetration. Build the 60 hours. |
| 50–99 | re-test price ($29) and wedge before building. Do not build yet. |
| **< 50** | **do not build.** 60 hours saved, and that is the test working. |

Rationale: $4,000/month is 103 subscribers at $39. A waitlist converts at well under 100%, so 100
signups is **not** 100 subscribers — it is the minimum signal that 103 is reachable at all. Treating
100 signups as proof of $4,000/month would be the same error as reading one positive cell out of 352.

## Deploy — 30 minutes

1. **Form endpoint.** Pick one: [Formspree](https://formspree.io) free tier, [Tally](https://tally.so),
   or [Buttondown](https://buttondown.com) if you want the eventual email list in the same place.
2. **Wire it.** In `index.html`, the only line to change:
   ```js
   var ENDPOINT = "";   // <- paste your endpoint URL
   ```
   The form already POSTs JSON `{email}` and shows the thanks state on success or failure, so a
   mistyped endpoint fails quietly rather than losing the visitor.
3. **Host it.** Netlify Drop or Cloudflare Pages — drag the folder, done, free. Buy a domain only if
   you want to; a `*.pages.dev` URL does not hurt a waitlist.
4. **Before posting, read the footer disclaimer and decide whether you are comfortable with it.** I
   wrote it, I am not qualified to approve it, and it is the one thing on the page that should get a
   second pair of eyes.

## Where to post — and the copy for each

Lead with the differentiator in every venue: **the citation**. Not AI, not spaced repetition — those
are commodity claims. "Every answer names the page" is not.

### r/anesthesiology, r/Residency

Reddit punishes anything that reads like marketing. Post as what it is: a thing you built for
yourself.

> **I built a cited flashcard deck for the anesthesia blueprint and I want to know if it's just me**
>
> I got tired of board-bank explanations I couldn't trace, so I wrote out the blueprint as atomic
> knowledge points — 6,200 of them across 1,214 topics, anesthesia and IM — where every single answer
> carries the book and page it came from. Example card, unedited:
>
> *What two gastric parameters define high risk for aspiration pneumonitis?* → Gastric volume >25 mL
> (0.4 mL/kg) AND pH <2.5. — Morgan & Mikhail, p. 438
>
> It's been my own study tool and it has an FSRS scheduler that tracks calibration separately from
> accuracy. It has no web app, so right now nobody but me can use it.
>
> Before I spend a month building accounts and a review queue, I want to know whether anyone else
> wants it. The first release would be the on-call/cross-cover set — the 50 topics about the acutely
> changing ward patient, which board banks cover badly because they aren't board questions.
>
> Waitlist is here if you'd want it: [link]. No payment, no card, and if not enough people sign up
> I'll say so and drop it.
>
> Either way I'd like to know: would page-level citations change whether you trusted a deck?

**Rules that matter:** check each subreddit's self-promotion policy first and post under your own
account with real history. A new account posting a link gets removed, and a removal teaches you
nothing about demand.

### Anesthesia Twitter/X and Bluesky

> Every board-bank explanation I've ever read, I couldn't check.
>
> So: 6,200 knowledge points across the anesthesia + IM blueprint, each one citing the book and page.
>
> *Gastric volume >25 mL AND pH <2.5* — Morgan & Mikhail, p. 438.
>
> Waitlist if you'd use it, and tell me if citations matter to you: [link]

### Program-specific channels

Residency Discords and class GroupMes convert far better than Reddit because the recommendation comes
from someone known. If you are in any, post there **first** — a handful of signups from your own
program in week one tells you more than 500 Reddit impressions.

## What to measure, and what not to

Record weekly: **signups, source, and the single most common objection in replies.**

The objection is the most valuable output of this test and the easiest to throw away. If ten people
say "I'd pay for IM, not anesthesia," that redirects the build. If ten say "$39 is too much for a
resident," that is a pricing answer, not a demand answer, and the 50–99 band is where you retest at
$29.

**Do not** count impressions, upvotes, or "this is cool" replies. The program spent 56 studies
learning that the only number that counts is the executable one, and here that is an email address
typed into a box.

## If it passes

`venue_expansion/STRATEGY_C_PLAN.md` carries the 60-hour build breakdown. Build in this order so that
the first thing shipped is the thing people said yes to: schema → auth → study loop → the on-call set
only → Stripe. The other 1,164 topics stay behind the paywall roadmap until the wedge has paying
users.

## If it fails

That is a real result and it cost 8 hours instead of 60. The content keeps its value — it is still
your study tool, it is still cited, and it does not expire. Track D (the research portfolio) and Track
B (capital, if the figure supports it) remain open, and the honest finding is that residents will not
pay for this, which is worth knowing before a month of building rather than after.
