# Bet sizing — the verdict (Kelly research + tape backtest)

Question: the operator observed early/near-50/50 legs pair ~certainly; should we SIZE UP there?
Answer: **the observation is correct, but conditional size-up does NOT beat flat on a risk-adjusted
basis. Keep flat ~1 contract. Quarter-Kelly is the absolute ceiling; our regime collapses to flat.**

## What the data says (tape backtest, 1,158 windows, 60/40 OOS)
- **Pair-rate claim CONFIRMED:** sweet-spot (k≤4, |p−0.5|≤0.05, 1st/2nd fill) pairs at **100%** (N=370);
  late + far-from-0.5 (k=11-12, |p−0.5|>0.15) drops to **65%**. Toxicity (unpaired settle) is meaningful
  only at late-k / far-from-0.5.
- **Size-up does NOT help risk-adjusted:** at clean queue (q0=0), the best conditional size-up earns
  marginally more net (+9% to +2.25× depending on aggressiveness) but **Sharpe is flat-to-marginal and
  the 5th-percentile tail WORSENS** (−50¢ vs −33¢/window at M=3). You buy mean with tail risk.
- The q0=2000 "realistic" disaster (−3,680¢/day) is **partly a sim artifact** (51.9% crossed boxes —
  the simulator pairs across an inverted market). Real live queue is between q0=0 and that; the live
  bridge made +17¢. So don't take the q0=2000 magnitude literally — but size-up makes it worse there too.

## What the theory says (Kelly research, fully cited in the dive)
- **Three-branch Kelly** (pair / unpaired-win / unpaired-lose): f* ≈ μ/(μ₂−μ²), dominated by the
  unpaired binary's variance. The pairing lock is negligible in the variance.
- **Conditional Kelly scales as P_pair/(1−P_pair)** — hyperbolic, blows up as P_pair→1. So sizing up on
  high-pair fills is *directionally* justified BUT must be capped.
- **Fractional Kelly under estimation error (Baker-McHale, MacLean-Thorp-Ziemba):** use **¼–½ Kelly**.
  Our prior 52% ruin came from applying high-P_pair Kelly fractions to lower-P_pair OOS fills.
- **Risk of ruin (Schlesinger):** at $-tens bankroll, flat 1-contract has P(ruin) < 2% even at thin
  edge; the danger is only when f > f_Kelly.
- **Integer/thin-edge collapse:** when f* < b/W (≈1% at $50 bankroll), Kelly says "1 unit or nothing."
  For P_pair < ~0.5 this is exactly our case → **flat 1 is near-optimal**.
- **A-S inventory overlay (the better-founded lever):** don't stop-loss (those lose); instead SUPPRESS
  new same-side fills as unpaired inventory accumulates (scale n_side down by q/q_max, pull at q_max).
  This is new-fill suppression, not exit — consistent with our strict-pairing clamp.

## Deployed decision
- **Sizing stays FLAT (1 contract).** Do not wire conditional size-up to live: marginal mean, worse
  tail, prior-ruin lesson, thin-edge collapse all agree.
- If we ever revisit: implement ONLY as ¼-Kelly, feature-bucketed P_pair with a hard per-fill cap
  (n_max = ¼·f*·W/b) and the A-S inventory suppression overlay — and ONLY behind the A/B tester +
  SCALE_GATE.md forward bar, never straight to live.
- **The real edge lever is execution (queue priority), not sizing or fatter boxes** — same conclusion
  as the completion-chase and wide-box analyses.
