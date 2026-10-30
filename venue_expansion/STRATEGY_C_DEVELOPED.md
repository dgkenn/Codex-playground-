# Strategy C, developed: the path that actually reaches $4,000/month — 2026-10-30

I was asked for strategies to reach $4,000/month and spent 56 studies on a venue I have now measured
cannot provide it. `STRATEGY_SET_4K.md` named four tracks but developed none. This develops the one
whose arithmetic reaches the target, using measured facts rather than conditionals.

**A note on scope:** every prior session asked about the trading bot. This is a different domain. I am
going there because the goal is **$4,000/month**, and I have measured that the trading program caps at
**$355/month (9% of target) even if every remaining gate clears.** Continuing to study Kalshi would be
work that cannot reach the goal by arithmetic. If this domain is unwelcome, say so and I will stop —
but I would be failing the stated goal to leave it unexamined.

## What is actually there — measured, not assumed

Queried the live system (`get_mastery_map`) on 2026-10-30:

| | |
|---|---|
| curriculum topics | **1,214** |
| knowledge-point catalog | **6,200** |
| disciplines | medicine (**555** topics), anesthesia (**659** topics) |
| named domains | **29** |
| topics studied | **27 (2.2%)** |
| knowledge points tracked | **141 (2.3%)** |

The domain list is not a flashcard deck. It is the **complete anesthesiology board blueprint** —
airway management, anesthetic pharmacology, monitoring & equipment, cardiac, thoracic, neuro, OB,
peds, regional & neuraxial, pain, perioperative crises, preop evaluation, critical care, patient
safety — **plus** internal medicine by organ system **plus** a 50-topic "on-call & cross-cover"
domain, which is the single most useful and least-served thing a junior resident needs.

**The shape of this is unambiguous: product-scale content, near-zero usage. "Built but unlaunched,"
not "personal study tool."** That is the most valuable and most common failure state for a software
asset, and it is the opposite of the trading program, which has been exhaustively validated into a
measured null.

## The arithmetic that reaches the target

US resident pools: anesthesiology ≈ **6,500**; internal medicine ≈ **27,000**.

| price/mo | subscribers for $4,000 | % of anesthesia pool | % of anes + IM |
|---:|---:|---:|---:|
| $19 | 211 | 3.2% | 0.63% |
| $29 | 138 | 2.1% | 0.41% |
| **$39** | **103** | **1.6%** | **0.31%** |
| $49 | 82 | 1.3% | 0.24% |
| $60 | 67 | 1.0% | 0.20% |

**$4,000/month is 1–2% penetration of one specialty's residents.** Set against the trading program —
which needed 11× breadth that was *measured not to exist* and caps at 9% of target on full success —
this is the first path in this entire program whose required numbers are ordinary.

Price anchors in this market: TrueLearn and M5 anesthesia board banks run roughly $300–500/year
(~$25–42/mo), so **$39/month is defensible rather than aspirational**, and the differentiator is real:
calibration tracking and spaced repetition over a full blueprint, rather than a static question bank.

## The gap between "built" and "sellable" — honest, and it is the real work

This is where I would expect the effort to go, and I am inferring from the tool surface, not from
having read the code:

1. **Distribution is the binding constraint, not content.** The system is an **MCP server**. Residents
   will not configure MCP servers. **It needs a web front end** — auth, a study view, a review queue,
   a dashboard. That is the single largest piece of work and it is what stands between 1 user and 103.
2. **Multi-tenancy.** The tool surface reads single-user (`get_progress`, `get_student_dashboard`,
   `start_study_session` with no student argument). Per-user state, isolation and billing are
   prerequisites, not features.
3. **Content provenance at scale.** `answer_from_clinical_sources` and `search_clinical_sources`
   suggest retrieval over real sources, and `get_illness_script` / `get_contrastive_case` /
   `get_dosing_drill` suggest generation on demand. If content is generated per request, the unit
   economics are **inference cost per student-hour**, which must be measured before pricing — a $39/mo
   subscriber who studies 20 hours/month at meaningful token volume can be unprofitable.
4. **Medical-content liability.** A paid tool that gives dosing guidance to clinicians needs explicit
   scope limits, sourcing, and disclaimers reviewed by someone qualified. This is not optional and it
   is not something I should draft unreviewed.
5. **The 2.3% catalog figure needs interpretation.** Whether 6,200 knowledge points are *authored* or
   *skeletal* changes the build estimate by an order of magnitude. This is the first thing to establish.

## Why this beats the alternatives, stated plainly

| track | required to hit $4,000/mo | status |
|---|---|---|
| **C — this** | **103 subscribers at $39** | content built; distribution unbuilt |
| B — capital | $600K at 8%/yr | solved if the capital exists; unknown |
| D — consulting | 20 hrs/month at $200 | portfolio exists as an internal log |
| A — trading | 11× breadth | **measured not to exist**; caps at $355/mo |

## What I propose to do next, concretely

In priority order, and each is bounded work I can do in this repo or alongside it:

1. **Establish whether the 6,200 knowledge points are authored or skeletal.** One query. It decides
   whether this is a 2-week or a 6-month build, and therefore whether the whole track is viable.
2. **Measure the unit economics** — token cost per study session at realistic volume, against a $39
   price. If a subscriber costs $45/month to serve, the price is wrong and that must be known first.
3. **Scope the minimum sellable product**: auth, per-user state, a study view, a review queue, Stripe.
   Written as a build plan with estimates, not prose.
4. **Pick the beachhead.** The "on-call & cross-cover" domain (50 topics) is the sharpest wedge — it is
   the thing every intern needs in July, it is badly served by existing board-prep products, and it is
   small enough to launch on.

**Say which of these to start and I will build it.** Absent direction, I will do (1) and (2), because
they are measurements rather than commitments and they determine whether the rest is worth anything —
the same discipline that kept the trading program honest, applied where the arithmetic can actually
reach $4,000/month.
