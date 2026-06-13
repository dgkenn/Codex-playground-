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

## >>> PHASE-1 SYNTHESIS (all 3 agents in) <<<
Commits: FRONTIER 16e55f9 (BOXYIELD_FRONTIER.md), FILL fde6fee (BOXYIELD_FILL.md), EDGE 3bca1ba
(BOXYIELD_EDGE.md). BTC parquet, IS/OOS 60/40, full A/B metric set. Backtests SCREEN.

**HEADLINE (convergent, high-confidence): the live BTC box policy is ALREADY at the yield frontier
on NET.** No (region x lock-floor) cell beats live net at |t|>=2 (FRONTIER best cell ties live,
t=-0.03). The big remaining PnL upside was on the LOSS/strand side -- which we already did. The gain
side is well-optimized; what's left here are RISK-quality trims + selection, not a net step-change.

**Convergent findings:**
1. **Profit is THIN-but-FREQUENT, not fat-but-rare.** Positive locked edge lives in the BALANCED band
   (~0.50-0.60, +1.31c/box). DEEP-FAVORITE boxes (favorite leg >0.70) LOSE -1.72c/box -- textbook
   adverse selection: both legs fill *because price was running*, one leg pre-pays the move.
2. **Fat boxes are localized: mid-window k=5-9 (k6-7 fattest +1.2-1.3c, t>3) + MID-VOL (3-8bps,
   +0.69c NET, t=3.4, IS==OOS).** HIGH-|sig| is a NET LOSS -- the "volatile = wider spread" intuition
   is WRONG here; captured spread collapses to ~0 in fast markets. Late slots (k>=11) strand.
   -> This is the one robust, deployable, NEW lever. Registered as t_edge_select (k5-9 + mid-vol),
   with t_edge_midvol / t_edge_k59 to isolate the components. Aligns with t03_early_window (k<=8),
   already on the live WATCH list at t=+2.38.
3. **Edge is real & stable: +0.55c/box, IS +0.556 -> OOS +0.551 (essentially identical).** ~6 boxes/win.
4. **Improve-tick / queue-ahead can't be won on this book OR proven on tape.** Mean spread is ~1c, so
   improving both sides locks the book; single-sided improve adds ~0.04 boxes/win while surrendering
   1c/leg (dnet -0.1 to -0.4c). It only flips positive under real queue depth (q0>=500) the tape can't
   observe -> a LIVE experiment, not a backtest decision.
5. **Lock-floor frontier is flat then collapses** (fee=0, ~1c spread): raising the implied floor above
   1-2c starves fills (#box/win 7.8 -> 0.9 from X=1c -> 2c). Net peaks at X=0, Sharpe at X=1c.
6. **Gentle edge-proportional sizing (f=0.25 fractional-Kelly on lock margin) is risk-adjusted
   dominant** (Sharpe +0.089 vs +0.080, MaxDD -31c) but modest and not t-significant. Phase-2 / forward.
7. **STRONG NEGATIVE: do NOT trade ETH (or SOL/XRP by extension).** ETH box is structurally -EV at
   every cell: median margin looks wider (+2.0c) but the MEAN is -1.5c (29.6% negative-margin boxes,
   5th-pctile -21c) from adverse selection on the pairing leg. 50/50 BTC+ETH vs BTC-alone = -8.03c/win
   (t=-6.79). Low cross-corr (+0.23) is moot when a sleeve has negative mean. The live trader is
   already --asset btc only, so NO live change -- but this CLOSES the "add assets for breadth" idea
   until a per-asset positive-mean-margin filter exists. (NB: the ETH cross-asset HEDGE is different
   and still valid -- there we BUY ETH directionally to offset a BTC strand, not run an ETH box.)

**Deployable-now levers (each via the forward A/B bar, t>3/n>=300):**
- t_edge_select (mid-window k5-9 + mid-vol 3-8bps) -- the convergent fat-box selection. NEW, registered.
- f=0.25 edge-proportional sizing -- risk trim, Phase-2 (needs a sizing path in the trader).
- (skewed-band+1c-floor Sharpe trim from FRONTIER is NOT registered: definition conflicts with the
  balanced-band edge finding and is not net-significant, t=-0.31.)

**Verdict:** the gain engine is near-optimal; the only clean new win is REGIME/SLOT SELECTION (trade
the fat mid-window mid-vol boxes, skip fast markets & late slots), which conveniently also reduces
strands -- and it's already half-validating via t03 on the live watchlist. ETH/SOL/XRP box expansion
is closed (-EV). Real future PnL remains on execution (queue-ahead, live-only) + the locked strand ladder.

## >>> PHASE-1 FOLLOW-UPS (combo stacking + ETH-with-ladder) <<<
**COMBO STACKING (commit 19b2309; BOXYIELD_COMBO.md):** stacking the levers does NOT help -- they
CANNIBALIZE (sub-additive, no positive interactions). Full 5-lever stack collapses volume 6.11->1.04
box/win, net +1.29c (worse than live +3.12c AND worse than every single lever). Leave-one-out:
edge_select's k in [5,9] strictly SUBSUMES k<=10 (marginal +0.000c); buffer/balanced-band partially
substitute (same adverse-selection tail). Best = a SINGLE lever (k_le_10: Sharpe +0.141 vs live 0.100,
net ~= live, strand 38%->13%; or edge_sizing by net). No combo beats live on net at |t|>=2. -> deploy
the LEAN single gate (already covered by t03/t_edge_* trials), never the stacked version.

**ETH + STRAND LADDER (commit 8265f84; ETH_LADDER.md): the ladder does NOT rescue ETH.**
- Naked ETH confirmed -EV: lock margin -1.11c/box (24.6% negative, p5 -19c), -13c/window at P0, 40% strand.
- Full ladder on ETH: OOS net -1.22c/win, t=-4.1 (IS -2.18c, t=-7.4) -- NEVER crosses zero. It only
  cuts the bleed by removing ~92% of opens (7026->570) and driving strands ~0; it creates NO edge.
- SMOKING GUN: the BTC-tuned gates select ETH's WORST boxes -- the ladder-pass region is -2.56c/box
  (t=-5.5) vs naked -1.11c. ETH's edge structure is INVERTED vs BTC: its only non-toxic slices are
  late-slot (k>9, +0.44c) and deep-favorites (>0.70), which are EXACTLY what edge-select + favorite-
  avoidance discard. No rung, single gate, or BTC-momentum gate makes ETH positive. Same ladder keeps
  BTC positive (+2.77c P0).
- VERDICT: ETH is NOT deployable as a box market -- gating only concentrates the loss; not enough good
  volume remains. KEEP ETH solely as the cross-asset HEDGE leg (RUNG-5a). (A theoretical ETH-NATIVE
  inverted ladder -- trade only late-slot k>9 -- shows just +0.44c on a thin slice; not worth pursuing.)
  The "add assets for breadth" idea is CLOSED (assume SOL/XRP share ETH's toxicity until shown otherwise).
