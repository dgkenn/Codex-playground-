# QUEUE.md — live queue-positioning: study (literature + data) and test design

## The literature verdict (Moallemi-Yuan 2016; optimal-placement work)
- Under price-time priority, earlier orders fill first → a FIFO arms race for front-of-queue.
- **Queue position matters MOST when the tick is economically large.** When the tick is small vs
  price you gain priority by price-improving a tick; when the tick is large you *cannot* improve
  cheaply, so the **only** way to gain edge is to **win the queue**. (Moallemi-Yuan; "Optimal
  Placement in a LOB", INFORMS; "Limit Order Strategic Placement with Adverse Selection Risk",
  arXiv:1610.00261; Fokker-Planck large-tick queue dynamics, arXiv:1304.6819.)
- Front-of-queue value is twofold: (1) guaranteed/earlier execution, (2) **lower adverse selection**
  (you fill on small early trades, not only on the big sweep that runs the level over). Queue value
  can be of the order of the bid-ask spread.

## Our data says this market is the high-queue-value regime
- **Relative tick = 1.96%** (1c spread on a ~$0.50 token) — an order of magnitude larger than equities
  (bps). So by the literature we are squarely in "queue position cannot be ignored; you must win the
  FIFO race, not price-improve." This is the single strongest structural reason an edge exists here.
- ~**13.6 mid-moves (>=0.5c)/min => ~204 repricing events per 15-min window** — each a queue reset
  where being early at the new level wins. Plenty of opportunities.
- We also have a ~0.5s BTC->token lead (feed_race) — the SIGNAL for *when/where* to pre-position.

## The honest test verdict: queue positioning is UN-testable in paper
- The paper fill model is **degenerate on queue position**: q_ahead collapses to ~0 at fill (the sim
  fills us once the displayed queue ahead is consumed). So there is no queue-position variation to
  measure or exploit in paper.
- KEY REALIZATION: because the paper model already fills us at ~front-of-queue, **the entire paper
  A/B is already the queue-positioning UPPER BOUND.** micro_gate's +5.7/win is "what you earn IF you
  win the queue." The whole live haircut vs paper *is* the queue battle. So there is no separate
  paper test to run — the ceiling is already measured; queue positioning is the LIVE work to realize it.

## CRUCIAL STRUCTURAL FINDING (building it surfaced this)
In a **1-tick-spread market** (this market, ~96% of the time) you **cannot pre-position at a
not-yet-touch level without crossing the spread** — there is no empty level between bb and ba, and
posting at the level the touch will move INTO means crossing = becoming a **taker** = paying the
0.07 fee = the play that already failed (lag_taker -27.9/win). So "post early at the next level"
does NOT work here. Real queue positioning in a large-tick market = **lead-aware standing-rung
priority**: keep aged rungs on BOTH sides; when the BTC lead says the touch is heading one way,
PROTECT the rungs on that side (they become front-of-queue when the touch arrives) and SHED the
rungs on the side the book is leaving (about to be run over). This needs no crossing and no fee.

BUILT + DRY-RUN VERIFIED: `live_trader.py --queue-jump` (Arm A). A daemon thread streams Coinbase
WS BTC; on a move > jump-bps over jump-lag, it protects the lead-favored side's rungs and sheds the
adverse side, logging every action to queue_jump_log.jsonl. Arm B = default (no flag). Dry-run:
BTC fell ~$13 -> on the Down token it protected BUY rungs and shed SELL rungs (correct).

## Best way to do it (synthesized) + the LIVE experiment
Mechanism: on the BTC-lead, post at the level the book is about to move to, a fraction-second early,
to secure front FIFO position before the laggard bots; capture the least-toxic front-of-queue flow +
rebate; cancel-on-reversal (Moallemi-Yuan dynamic/optionality value). Stay delta-neutral, small.

LIVE A/B (requires real orders on user infra — keys/capital; paper cannot adjudicate):
- Arm A "pre-position": reprice to the BTC-implied next level on the lead signal.
- Arm B "at-touch control": quote at the current touch only.
- MEASURE (live-only, decision-grade): realized **queue rank at fill**, **fill rate**, **markout by
  queue rank**, hold-to-resolution P&L. Pre-registered: A beats B on fill-rate AND markout-by-rank,
  clustered by window, across >=3 weeks/regimes.
- Risk: post-only, tiny size, tight inventory, cancel-on-reversal; burner key; I_UNDERSTAND_REAL_MONEY.

## Sources
- Moallemi-Yuan, Queue Position Valuation: https://moallemi.com/ciamac/papers/queue-value-2016.pdf
- Optimal Placement in a LOB (INFORMS): https://pubsonline.informs.org/doi/pdf/10.1287/educ.2013.0113
- Strategic placement w/ adverse selection: https://arxiv.org/pdf/1610.00261
- Large-tick queue dynamics (Fokker-Planck): https://arxiv.org/pdf/1304.6819
