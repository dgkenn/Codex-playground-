# PROJECT AUDIT — did the backtested edge collapse? (2026-06-14)

Operator skepticism: "I have a hard time believing my backtested edges collapsed this bad." CORRECT.
Checked all assumptions against live + backtest + shadow data. VERDICT: the edge did NOT collapse.

## What the data actually says
1. **MAKER BOX EDGE IS REAL AND INTACT.**
   - Backtest box edge over time: OLD half +0.22c/box, RECENT half +0.37c/box -> STABLE, no erosion.
   - LIVE passive maker boxes (06-14 selective run): 62 boxes, **+0.69c/box, +42.8c total** -- the live
     paired edge MATCHES/EXCEEDS the backtest. The thing you backtested works.
2. **THE ENTIRE LOSS IS STRAND DISPOSAL, NOT THE EDGE.**
   - 12 crossed completions (strand -> taker cross to complete): **-16.4c/box, -197.4c total.**
   - Net = +42.8c (passive) - 197.4c (disposal) = **-$1.55.** The 12 bad boxes wiped 200+ good ones'
     worth of edge. Some crossed boxes cost up to $1.83 (paid $0.83 over par).
3. **WHY THE BACKTEST NET WAS OPTIMISTIC (but the edge was real).** The tape-replay fill model assumed
   both legs fill at our quote (low strand rate, cheap completion). REALITY: strand rate 16-33% and
   disposal costs -16 to -22c. The backtest under-modeled the STRAND COST, not the edge. So "+1.5c/box,
   +EV" was a real edge attached to an under-counted liability.

## The actual math (this is the whole game)
net/box = (1 - strand_rate)*paired_edge - strand_rate*disposal_cost
        = 0.84*(+0.69c) - 0.16*(16c) = +0.58 - 2.56 = -2.0c/box   <- current
Break-even needs strand_rate < paired_edge/disposal_cost ~= 0.69/16 ~= 4.3%  (we are at 16%).
=> The edge is real; the ONLY problem is the strand rate (and the disposal cost). Cut strands to <~4%
   AND/OR disposal to <~-8c and the +0.69c paired edge nets POSITIVE.

## CORRECTED PATH FORWARD (it's a pairing-engineering problem, not "no edge")
The strategy is NOT dead. The edge exists; we are losing it to legging. Three concrete levers:
1. **CUT STRAND RATE to <4-5% (the dominant lever).** Only open a box when BOTH legs are likely to
   pair: deep+balanced book on both sides; open both near-simultaneously; do NOT open one leg
   speculatively. "Pair-or-don't-play." This is the core engineering task.
2. **CHEAPER DISPOSAL for residual strands.** The force-flatten "cross at ANY price in the final 45s"
   overpaid (created the $1.83 boxes). Revert to a GIVE-CAPPED early cross: cross when the move is
   still small (~-4c), accept a bounded loss, and prefer crossing EARLY over force-flattening LATE.
   (The -16.4c crossed avg is barely better than the -21.76c hold; neither is acceptable -- the fix is
   to cross EARLY/CHEAP or not strand at all.)
3. **VALIDATE pairing specifically.** Backtest + forward-measure the PAIR RATE and legging gap under
   the new open rules, not just net P&L. Target: strand <5%, disposal <-8c -> net ~+0.3c/box.

## Status / recommendation
- Bot OFF (commit b24bcc6) -- it was bleeding via the disposal mechanism, now understood.
- This is the most hopeful finding in the whole project: the edge is real and intact; the work is
  PAIRING (cut legging) + cheap disposal, not finding a new edge. Next: implement pair-or-don't-play +
  give-capped early disposal, backtest the pair rate, then a bounded live re-test.
- Shadow collector keeps running (free) for the pair-rate validation.
