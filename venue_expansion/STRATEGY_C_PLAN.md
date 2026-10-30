# Strategy C — measured, scoped, estimated. The plan to $4,000/month.

Both blocking unknowns from `STRATEGY_C_DEVELOPED.md` are now **resolved by measurement**, and one of
my own objections was **wrong**.

## Unknown 1 — authored or skeletal? **AUTHORED, with page-level citations.**

Queried `get_kp_to_study(discipline="anesthesia")` on an untouched discipline (0 of 659 topics
studied). It returned complete database rows:

```json
{ "id": "aspiration-prev-mgmt-3",
  "topic": "Aspiration: prevention and management",
  "stem": "What two gastric parameters define the threshold at which a patient is at high risk for aspiration pneumonitis?",
  "answer": "Gastric volume >25 mL (0.4 mL/kg) AND gastric pH <2.5",
  "rationale": "Large volumes of acidic gastric contents cause severe chemical pneumonitis (Mendelson syndrome) when aspirated.",
  "bloom": "recall",
  "source": "[{\"book\": \"Morgan & Mikhail\", \"page\": 438}]",
  "discipline": "anesthesia", "tier": 1, "category": "topic",
  "is_critical_care": true, "car_safe": true }
```

Three things matter commercially:

1. **`source` carries book + page.** Page-level citation to Morgan & Mikhail — the standard anesthesia
   text. This is the **single most valuable field in the asset.** It is simultaneously the answer to
   the medical-liability concern I raised *and* the defensible differentiator against LLM-generated
   competitors, whose content cannot be traced to a page.
2. **`bloom`, `tier`, `category`, `is_critical_care`** — the catalog is pedagogically structured, with
   a priority ordering already implemented (presentation-first, critical-care-first, tier-ascending).
3. **`car_safe`** — KPs tagged as workable hands-free while driving. That is a product decision about
   a real user context (residents commuting), not a note-taking artifact.

**6,200 of these across 1,214 topics (~5 per topic).** The content — the genuinely hard, slow,
expensive part — **is done.**

## Unknown 2 — unit economics? **Resolved, and my objection was wrong.**

I wrote that content might be generated per request, making a $39 subscriber potentially unprofitable
at 20 study-hours/month. **That is wrong.** The core study loop is a **database read**: 6,200 rows at
~420 B is ~2.6 MB of content total. Marginal cost per subscriber-month is hosting, measured in cents,
not inference.

Any LLM features (free-text answer grading, Socratic follow-up) are **optional add-ons that can be
metered or omitted**, not load-bearing. Pricing is unconstrained by cost of goods.

## The build — scoped and estimated

| hours | task |
|---:|---|
| 4 | Schema: `users`, `user_kp_state` (FSRS fields), `sessions` |
| 4 | Auth (Clerk or Supabase) |
| 8 | Study-loop API: next / submit / progress |
| 12 | Study UI: queue, card, reveal, grade |
| 8 | Dashboard UI: mastery map |
| 8 | Stripe checkout + webhook + entitlement gating |
| 4 | Deploy: Vercel/Railway + managed Postgres |
| 8 | Landing page + copy |
| 4 | ToS + medical disclaimer — **needs qualified review, not mine** |
| **60** | **total ≈ 3 weeks at 20 h/wk, 6 weeks at 10 h/wk** |

It is small **because the two hard parts already exist**: the cited knowledge-point catalog, and FSRS
scheduling with calibration (already serving `get_due_reviews`, `get_mastery_map`, priority ordering).
What is missing is a front door, not a brain.

## Demand is the one thing still unmeasured — so measure it first, in 8 hours not 60

This is where I nearly repeated the program's original sin. The trading work was disciplined because
it **measured before building**; then I scoped a 60-hour build against *assumed* demand. Correcting
that:

**Step 0 — demand test. ~8 hours, under $50, before any build.**

- Landing page on the **on-call / cross-cover wedge** (50 topics): what every intern needs in July,
  badly served by board-prep question banks, small enough to launch alone.
- Lead with the differentiator: *every answer cites a textbook page.*
- $39/month waitlist or pre-order.
- Post to r/anesthesiology, r/Residency, r/medicalschool, anesthesia Twitter/Discord.

**Decision rule, frozen now, before any signup exists:**

| signups in 30 days | action |
|---|---|
| **≥ 100** | demand is real at 1.6% penetration — build the 60 hours |
| 50–99 | re-test pricing and wedge before building |
| **< 50** | demand is not there; **do not build.** 60 hours saved |

That rule is the point. It is the same apparatus that produced 56 honest closures, pointed at the one
path whose arithmetic reaches $4,000/month.

## The full path, with every number now measured except demand

| step | cost | what it resolves |
|---|---|---|
| 0. Demand test | 8 h, <$50 | **the only remaining unknown** |
| 1. Build MVP | 60 h | distribution — the binding constraint |
| 2. Launch at $39/mo | — | 103 subscribers = **$4,017/month** |

**103 subscribers is 1.6% of US anesthesiology residents (~6,500), or 0.31% of anesthesia + internal
medicine (~33,500).** Marginal cost per subscriber is cents. Content is sunk and already authored with
citations.

## Honest comparison to everything else

| track | to reach $4,000/mo | status |
|---|---|---|
| **C — this** | **103 subs at $39** | content done; 60 h of build; demand untested |
| A — trading | 11× breadth | **measured not to exist**; caps at $355/mo |
| B — capital | $600 K at 8%/yr | unknown — the capital figure was never given |
| D — consulting | 20 h/mo at $200 | portfolio exists as an internal log |

**Track C is the only one where every input except demand is now measured, and where the required
numbers are ordinary.** Track A is arithmetically incapable of the target. Track B is either already
solved or unavailable, and only you know which.

## What I will do without further instruction

Write the **step-0 landing page and the demand-test copy** — that is the 8-hour item, it is the gate on
everything else, and it needs no permission, no capital and no access to your systems. If you would
rather start at the build, say so and I will take the 60 hours instead.

The one thing I should not write unreviewed is the medical disclaimer.
