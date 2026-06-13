# BOX-YIELD research program -- the GAIN side (2026-06-13)

After the strand-handling ladder (the LOSS engine), pivot to the GAIN engine. Operator:
"how can we fill MORE boxes and/or get MORE PROFITABLE boxes."

## The objective (one equation)
TOTAL PnL  =  (#boxes filled)  x  (avg locked edge / box)  -  strand losses
We have driven down strand losses. Now MAXIMIZE THE PRODUCT of the first two terms -- which are in
TENSION (wider lock-margin entry -> fewer fills; more aggressive quoting -> more fills but thinner
margin and more strands). So this is a yield-optimization, not a single-lever push. Judge vs
live_current; forward bar t>3/n>=300; backtests SCREEN (same discipline as the ladder program).

A "box" = YES leg + NO leg both filled, locking edge = 1 - cost_yes - cost_no (crypto15m fee=0, so
pure spread capture). #boxes = participation x completion. Edge/box = lock margin at entry.

## EXHAUSTIVE brainstorm (every lever on the two terms)
**A. FILL MORE boxes (raise participation x completion)**
- Quote BOTH sides every window (we already post both); widen the price band we quote (mid 0.03-0.97).
- More k-slots (quote earlier/more minutes); multi-box / multi-rung per window when the band allows.
- Queue position: improve-by-a-tick / front-of-queue so resting maker orders actually fill.
- Window-open RACE: quote at the open before the book thickens (WINDOW_OPEN_RACE/LATENCY.md).
- Quote-ahead / re-quote as the touch moves; chase the completing side (already in COMPLETE rung).
- Asymmetric size skew toward the side likely to fill 2nd (raise P(both)).
- Lower the open bar in HIGH-completion regimes (thin book, balanced flow, flat OI).
- Add assets (ETH/SOL/XRP 15m) and tenors for more box opportunities (we collect all 4).

**B. MORE PROFITABLE boxes (raise edge/box)**
- Lock-margin entry gate: only open when 1 - cost_yes - cost_no >= X (the profitability floor).
- Improve-tick entry: capture an extra 1c of spread per leg (queue-ahead value).
- Price-region selection: favorite (cost>=0.5) vs longshot legs; |p-0.5| band with widest margin.
- k-slot / time-of-day / session selection for the widest spreads (most maker edge).
- Vol-regime: do wider spreads (more edge) appear in high-|sig| or low-|sig| windows?
- Edge-proportional SIZING: size ~ lock margin (Kelly on the locked edge) -> more $ on fatter boxes.
- Rebate/queue tiers (n/a on crypto15m: fee=0) ; maker-only (avoid paying spread).
- Adverse-selection-adjusted edge: net edge = gross margin - expected strand cost; maximize NET.

## Tension map (why it's a product, not a sum)
- Widen band / lower open bar -> MORE fills, THINNER margin, MORE strands.
- Raise lock-margin floor -> FATTER boxes, FEWER fills.
- Improve-tick -> more edge per box BUT worse queue position (fewer fills) -- net unclear.
- Size ~ edge -> more profit concentration BUT more variance.
The win is the FRONTIER: the (band, margin-floor, slot, size) combination that maximizes
total locked-edge PnL per unit risk, NET of the strand cost we already model.

## Program plan (mirrors the ladder program)
- BASELINE: measure current box yield -- #boxes/window, avg edge/box, total locked-edge PnL,
  P(both fill), across the full A/B metric set. This is the reference.
- Phase 1 (parallel agents, backtest on all data + literature):
  1. YIELD-FRONTIER by price-region & lock-margin: map edge x fillability across the band; find the
     band + margin-floor that maximizes total locked-edge throughput (objective A x B tradeoff).
  2. FILL-CONVERSION mechanics: improve-tick / queue-ahead / window-open race / multi-slot to raise
     #boxes & P(both) WITHOUT paying spread; quantify the queue-position vs fill-rate frontier.
  3. EDGE-SELECTION & SIZING: which slots/sessions/vol-regimes/assets yield the fattest boxes; size ~
     edge (Kelly on lock margin). Cross-asset breadth (ETH/SOL/XRP 15m) for more opportunities.
- Phase 2: stack the winners into a combined box-yield policy; backtest vs live + the strand ladder;
  register forward A/B trials. Lock the gain-side playbook.
Literature: Avellaneda-Stoikov (optimal two-sided quoting / spread), Ho-Stoll (inventory), Glosten-
Milgrom (adverse selection in the spread), queue-position value (Moallemi-Yuan), Kelly sizing.
