# SCALE_GATE.md — pre-registered criteria for sizing up (frozen BEFORE the data arrives)

Scaling is the last lever (MARKET_SELECTION.md closed the venue question; the strategy is
validated but thin). To avoid fooling ourselves, the scale-up criteria are pre-registered HERE,
with numbers, before the forward data that will be judged against them exists. Changing these
criteria after seeing the data = starting the clock over.

## Step 1: current size → 2 contracts/leg (post 1→2, max-notional 5→10)
ALL of the following, measured on live forward data (window_audit + scorecard), no cherry-picked
start date — the window is "since the chase deploy":
1. **≥7 consecutive calendar days net-positive** at current size, *including* unpaired drag
   (sum of window_audit pnl > 0 each day, ≥20 windows/day traded).
2. **Unpaired-rate improvement holds**: windows with an unpaired residual <30% (live baseline 39%)
   over ≥150 windows, without lock erosion (mean lock per paired box ≥ +0.5¢).
3. **No kill-switch trips** (loss-limit / toxic-markout / dead-man) in those 7 days.

## Step 2: 2 → 4 contracts/leg (max-notional 10→20)
1. Step-1 size has run **≥14 days with positive cumulative P&L** and max drawdown < 1 day's mean
   gross box income.
2. **At least one A/B trial deployed**: a toxicity gate (t17/t18) or other trial crossed the
   pre-registered 2-sigma bar on ≥300 forward windows and its live behavior matches its ledger
   prediction (sign and rough magnitude).
3. **Fill-rate sanity at size**: doubling size did not degrade time-to-fill p90 >2× or flip
   markouts below the −0.04 kill bar (depth at touch is ~$100-900 — our size must stay invisible).

## Never-rules (cannot be overridden by a good week)
- **No size-up within 48h of any loss-limit/toxic kill** — and never auto-rearm (SWITCH.md stands).
- **Kelly sizing stays OFF** until an A/B trial validates it forward (the 52% ROR proxy result
  stands; flat sizing is the deployed default).
- **One step at a time**: never skip a step, never size up two parameters at once
  (post AND max-rungs), and any step DOWN resets the clock for the step back up.
- **max-net stays 1** (strict pairing) at every size — size scales the BOX, not the inventory risk.

## Why these numbers
- 7/14 days ≈ 270/540 windows at the observed ~38 active windows/day — enough for the per-window
  t-stat the tape says distinguishes +0.3¢/win from zero (σ≈16¢ → t≈2 needs ~250 windows... at
  +2¢/win; at +0.3¢/win nothing short of months distinguishes — which is WHY the gate is framed on
  daily-net consistency + risk events, not on a t-stat we can't reach).
- <30% unpaired vs 39% baseline = the chase fix doing its minimum job (the A/B's own estimate of
  floor-blocked completions is larger, but live queue position will eat part of it).
- Lock floor ≥0.5¢/box guards against "completing" our way into guaranteed-loss pairs (the chase
  give caps at 2¢ mid-window / 4¢ close, so erosion shows up fast if it's happening).
