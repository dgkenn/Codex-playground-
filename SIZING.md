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


## ROUND 2 — the 8-family sizing sweep at Stage-A parameters (2026-06-12, q0=0, base 2-lot)
Backtested 8 sizing shapes under the $100-stage discipline (matched-pair sizing, $12 daily limit,
60/40 OOS). **Flat-2 won again.** OOS deltas vs flat: hour-of-day +0.16c/win (the ONLY positive —
economically negligible, +14% variance; forward trial t25 will confirm or kill it); gamma-taper
−0.34c mean but **−36% maxDD / −39% std** (the one genuine RISK shape; forward trial t26);
sweet-spot −0.25c; quarter-Kelly −0.30c; tox-sized −0.59c; vol-inverse −0.51c; qkelly×tox combo
−1.38c (worst). REJECTED permanently: vol-inverse, combo. Daily $12-limit breach rate at Stage-A:
0.0% across ALL shapes — the loss-limit is not the binding risk at this size.
**The sweep's real headline: queue position dominates sizing.** At q0=500 every shape flips deeply
negative (91.7% daily-breach) — the entire strategy lives or dies on being front-of-queue, and no
sizing overlay moves the needle by more than ~0.2c/win. Sizing optimization is third-order;
execution priority is first-order. (Sweep script + tables in the research record.)


## ROUND 3 — maker-sizing literature dive (2026-06-12; full citations in research record)
The MM theory (Avellaneda-Stoikov, Guéant-Lehalle-Fernandez-Tapia, Bergault-Guéant) does NOT
prescribe lot-size modulation at all: canonical optimal market making holds size fixed and manages
risk via SPREAD ASYMMETRY + HARD INVENTORY CAPS — both of which we already run (strict-pairing
clamp, max-fills-side). Size-as-signal is a practitioner extension the tape keeps rejecting.
- **Drawdown-constrained sizing (Grossman-Zhou / Busseti-Ryu-Boyd):** the usable output is a CAP,
  not a signal: N_max = floor(L / (1.645·σ_w·√N_w)) ≈ floor(L/$1.72). At the $12 Stage-A limit:
  post ≤ 6 (non-binding at 2). At post=16 the loss-limit must be ≥ $28 — SCALE_GATE updated.
- **Queue beats size (Moallemi-Yuan):** priority is worth ~the full spread on large-tick books —
  the theory twin of our empirical q0=500 collapse. Same-price order SPLITTING is valueless under
  FIFO; a SECOND RUNG (touch−1¢) has value only when P(fill at touch) > ~0.85 (deep hours, big
  post). Registered as pending trial t27 (Stage-B, post≥8 only; not honestly simulable in the
  current replay — needs live A/B arms).
- **Bayesian scale-up:** fractional Kelly ≡ full Kelly on a shrunken edge estimate; for any NEW
  series use multiplier t/(t+100) over its first 100 fills (the thin-market sleeves inherit this).
- **Bottom line unchanged and now triple-confirmed (tape ×2 + theory): flat base size at every
  stage, walk the ladder via SCALE_GATE, spend engineering effort on queue priority, not sizing.**

## Deployed decision
- **Sizing stays FLAT (1 contract).** Do not wire conditional size-up to live: marginal mean, worse
  tail, prior-ruin lesson, thin-edge collapse all agree.
- If we ever revisit: implement ONLY as ¼-Kelly, feature-bucketed P_pair with a hard per-fill cap
  (n_max = ¼·f*·W/b) and the A-S inventory suppression overlay — and ONLY behind the A/B tester +
  SCALE_GATE.md forward bar, never straight to live.
- **The real edge lever is execution (queue priority), not sizing or fatter boxes** — same conclusion
  as the completion-chase and wide-box analyses.
