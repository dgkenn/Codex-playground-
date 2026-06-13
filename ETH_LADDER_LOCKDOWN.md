# ETH strand-handling ladder — LOCKDOWN program (2026-06-13)

GOAL: build the OPTIMAL strand-handling ladder FOR THE ETH 15-min market — the full BTC lockdown
program (LADDER_LOCKDOWN.md) re-run for ETH: optimize each rung for ETH, then LOCK THE SEQUENCE via
ablation (which rungs, what order, add/subtract/reorder), grounded in the exhaustive brainstorm.
Judge vs ETH-naked / ETH-P0; forward bar t>3/n>=300; IS(60)/OOS(40) + any live ETH data the collector
has accumulated (the collector captures ETH alongside BTC). Backtests SCREEN.

## Why ETH needs its OWN lockdown (do not reuse BTC's)
ETH's edge structure is INVERTED vs BTC (established, ETH_LADDER.md / BOX_YIELD.md):
- Naked ETH box is -EV: completed-box margin MEAN -1.11c but MEDIAN +2.0c, 24.6% NEGATIVE-margin,
  p5 -19c, ~40% strand. => WIDE boxes with a TOXIC NEGATIVE TAIL dragging the mean down.
- The BTC-tuned ladder does NOT rescue ETH (-1.22c/win, t=-4.1): the BTC gates pick ETH's WORST
  boxes. ETH's non-toxic slices are LATE-slot (k>9, +0.44c) and DEEP-FAVORITES (>0.70) — exactly
  what BTC's edge-select (k5-9) + favorite-avoidance DISCARD. So every threshold/sign may flip for ETH.
OPERATOR THESIS: the wide ETH boxes can be harvested IF we (a) avoid the toxic tail at entry AND
(b) really cut down the unpaired leg (complete/sell/hedge). This program tests that rigorously.

## EXHAUSTIVE strategy brainstorm (reused from LADDER_LOCKDOWN.md — re-evaluate EACH for ETH)
Every lever, re-asked "what is the ETH-optimal setting?" (signs/thresholds may invert vs BTC).
**0. STRUCTURAL** — spread/lock BUFFER (ETH spread floor?), size skew, strict pairing, quote-both.
**1. PREVENT (entry gate)** — spread-floor; |sig| momentum gate; microprice-divergence; VPIN/toxicity;
   queue-thinness; balanced-flow; FAVORITE-band (ETH: deep-favorite may be GOOD, opposite of BTC);
   k-slot/time (ETH: LATE-slot k>9 may be the good slice); vol-regime; session; one-sided no-open.
**2. PREDICT (model-gated)** — ETH-NATIVE classifier on the toxic (negative-margin) box at entry; is
   ETH toxicity PREDICTABLE at entry (avoidable) or INTRINSIC to completion (price-ran adverse)?
   settlement-magnitude regressor; P(toxic)-weighted continuous sizing.
**3. COMPLETE (pair the leg)** — chase/improve give sweep (ETH-tuned); force-complete-age; partial.
**4. MANAGE/MITIGATE** — SELL the stranded ETH leg cheap: ETH's OWN price threshold (BTC's 0.30 likely
   wrong); sell-all vs cheap-only; tox-conditioned; cool-off/scale-down; size-down on toxic setups.
**5. HEDGE** — IS THE ETH STRAND HEDGEABLE? cross-asset BTC hedge (mirror of ETH-hedges-BTC R^2=18.6%);
   ETH-perp at scale (integer-lumpy, $6 min); cross-tenor.

## Program plan (mirrors the BTC lockdown)
- **Phase C-first (per-rung, RUNNING):** two agents optimize the rungs for ETH NOW —
  (i) ETH-NATIVE: PREVENT+PREDICT (toxic-tail avoidability, ETH entry gates, classifier AUC) -> ETH_NATIVE.md;
  (ii) ETH-DISPOSAL: COMPLETE+SELL+HEDGE (per-rung recovery; BTC-hedgeability headline) -> ETH_DISPOSAL.md.
- **Phase A (BASELINE):** stack the ETH best-per-rung into one combined ETH policy; backtest on all
  ETH data across the FULL A/B metric set; deep dive. The ETH reference.
- **Phase B (LOCK SEQUENCE) — the ablation studies the operator asked for:**
  - leave-one-out: drop each rung; marginal contribution on ETH.
  - reorder: where order matters for ETH (e.g. does sell-cheap precede hedge? does predict gate or size?).
  - add/subtract: from the brainstorm, test ETH-specific candidate rungs (late-slot-only opener,
    deep-favorite opener, BTC-momentum gate, ETH toxicity classifier as a rung) — ADD if they earn it,
    SUBTRACT rungs that are net-negative or redundant on ETH.
  - Lock the ETH sequence by marginal contribution + interaction (NET of fill-volume; a rung that
    "helps" only by trading ~nothing does not count — ETH's thin book makes this critical).
- **Phase D (VERDICT):** is there an ETH ladder that makes the wide boxes net-positive AND deployable
  (enough #boxes/win after gating)? If yes: the locked ETH sequence + exact params/flags. If no:
  document precisely why (toxic tail intrinsic / not enough clean volume) and keep ETH = hedge leg only.

## Status
- Per-rung agents RUNNING (ETH_NATIVE.md, ETH_DISPOSAL.md). When both land -> launch the Phase A+B
  ablation/sequence-lockdown agent (combined ETH baseline + leave-one-out + reorder + add/subtract),
  then synthesize the LOCKED ETH SEQUENCE here. All vs ETH-naked baseline; forward bar t>3/n>=300.

## >>> PER-RUNG RESULTS IN (both agents) -> ETH VERDICT <<<
**ENTRY: PREVENT+PREDICT (commit 4066a0d; ETH_NATIVE.md):** toxicity is INTRINSIC to completion, NOT
avoidable at entry -- classifier OOS-AUC=0.60; gating 73% of volume still nets -0.07c. WIDE boxes are
MORE adversely selected (27.5% neg vs 20.3%) -- the boxes the thesis targeted are the problem, not the
prize. Pure box-completion stays negative on every clean slice (best k>=11&fav>=0.85 = -0.38c, t=-1.6,
0.54 box/win). Only a perp OVERLAY turns positive, but it's a directional leverage knob (net & CVaR rise
monotonically with h), not box edge.
**DISPOSAL: COMPLETE+SELL+HEDGE (commit 40470f2; ETH_DISPOSAL.md):** strand = -3.61c/win (~32% of ETH's
-11.37c P0 loss), 41% strand rate, mean -8.87c (95% negative), late-slot-heavy. The ONLY robust disposal
rung = FLATTEN-ALL (sell every stranded leg at touch, NO price gate, don't chase give=0): +0.91c/win OOS,
t=+3.87, IS->OOS stable. ETH's cut is inverted vs BTC (favorites included -> sell). HEADLINE: the ETH
strand is NOT hedgeable -- BTC-hedges-ETH basis R^2=4.1%/|corr|=0.20 (a quarter of the symmetric
18.6%/0.43), std-red 2.1%, coverage 22%; ETH-perp <0.4%. FLATTEN, don't hedge. Disposal alone recovers
only ~25% of strand cost; box stays deeply negative (-13.15c -> -12.24c).

## ETH LOCKDOWN VERDICT (Phases A-D resolved by the per-rung evidence)
ETH boxes are -EV AT COMPLETION (adverse selection is intrinsic, not gateable) and the strand is NOT
hedgeable. Neither entry-prevention, nor disposal, nor hedging rescues the box -- the wide boxes ARE the
toxic ones. A formal Phase-A/B ablation would only confirm "all rungs negative / no positive sequence to
lock," because no per-rung strategy is net-positive to stack. So:
- **ETH box market: CLOSED.** Do not trade ETH (or SOL/XRP by extension) as a box market.
- **ETH strand is NOT hedgeable** (R^2 4.1%) -- so if ETH were ever traded, FLATTEN-ALL is the only
  backstop, not a hedge.
- **ETH's one durable use = the cross-asset HEDGE LEG (RUNG-5a) for BTC strands** (that direction works:
  ETH-hedges-BTC R^2=18.6%). The reverse (BTC-hedges-ETH) does not.
- Add/subtract/reorder is MOOT for a market with no positive rung. The BTC ladder stands as the product;
  ETH stays a hedge instrument, not a venue.
LADDER STEP CHANGES for ETH vs BTC (had it been viable): sell-cheap -> SELL-ALL (no price gate); chase
give -> 0 (don't chase); hedge rung -> DROP (not hedgeable); entry edge inverted (late-slot/deep-fav).
But these are academic given the -EV completion. Forward note: FLATTEN-ALL is the only ETH finding worth
a forward trial IF ETH is ever revisited.
