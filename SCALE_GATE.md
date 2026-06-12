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
- **max-net = post, exactly** (strict pairing restated for size: at most ONE unpaired LEG of current
  size, never more) — size scales the BOX, not the inventory risk. (At post=1 this is the original
  "max-net 1".)

---
# CAPITAL STAGES — the $100 and $1000 gates (operator request, 2026-06-12)

The contract-steps above govern SIZE-PER-QUOTE; these stages govern BANKROLL. Each stage names its
ENTRY benchmarks (all must hold), the PARAMETER TRANSITION (what changes, what must not), and a
3-day PROBATION that catches size-dependent breakage before it can compound.

## Stage A — fund to $100 (from the current ~$10-25)
**ENTER when ALL of (= Step-1 above, plus one validated edge):**
1. 7 consecutive net-positive days at current size, ≥20 windows/day, including unpaired drag.
2. Unpaired-window rate <30% over ≥150 windows; mean lock/box ≥ +0.5¢ (the chase isn't buying
   completion with guaranteed-loss pairs).
3. Zero kill-switch trips in those 7 days.
4. **≥1 A/B trial deployed past the pre-registered bar** (t02 is the live candidate at t=2.79,
   n=81/100) and its first live week matches its ledger sign.
**TRANSITION (the strategy adjustments):**
- post 1→2; **max-net 1→2** (= post); max-rungs stays 1; max-fills-side stays 4 (structure, not size).
- max-notional $5→$20 (20% of bankroll — the deployed fraction DROPS as capital grows).
- loss-limit $6→$12, sticky as ever; markout-kill bar UNCHANGED (it's per-contract).
- chase gives UNCHANGED (per-contract cents); all alerts/dead-man/switch unchanged.
- **Fee re-verification:** the API no longer exposes fee fields at all — confirm fee=0 on the FIRST
  2-lot fill before the run continues (one bad assumption at 2× size is 2× the damage).
**PROBATION (first 3 days at $100):** run the NEW size with the OLD loss-limit ($6) — a tighter
relative tolerance; revert to post=1 on any kill. Pass = markout curve within 0.3¢ of the 1-lot
baseline AND time-to-fill p90 <2× baseline (queue impact check). Then relax loss-limit to $12.

## Stage B — fund to $1000
**ENTER when ALL of:**
1. ≥21 days at Stage A with positive cumulative P&L and max drawdown <5% of bankroll (<$5).
2. **≥2 independent A/B-validated improvements deployed** (e.g. t02 + a toxicity gate) — the edge
   must be widening, not just surviving.
3. Markout curve at 2-lot within 0.3¢ of the 1-lot baseline over ≥500 fills (we are not yet moving
   the book against ourselves).
4. **Capacity probe passes:** from the live book stream, our resting size <10% of median touch depth
   on KXBTC15M (depth runs ~$100-900; 4-8 contracts ≈ $2-4 — fine, but VERIFY, don't assume).
5. No kill trips in the trailing 14 days.
**TRANSITION — this is where the strategy itself must change, not just the knobs:**
- post 2→4; max-net 2→4 (= post); max-notional $20→$100 (10% of bankroll); loss-limit $12→$25.
- **A single 15-min series cannot absorb $1000** (≈$4/quote deployed; >$900 idle). The remainder
  deploys across STRATEGIES, not more size on one book — each behind its own pre-registered gate:
  (a) thin/new-market maker pilot: $10-50 per market across 10-20 quiet event markets
      (KALSHI_GOLD_CANDIDATES #4) — cap category exposure at $150;
  (b) ladder-lock maker IF the two-week ladder collector shows ≥5 crossable dislocations/week
      (KALSHI_GOLD_CANDIDATES #3) — start $50;
  (c) favorite-band maker (#1) only after (a) has 2 green weeks — it is (a) with a price whitelist.
- **Aggregate exposure rule: ≤30% of bankroll deployed across ALL strategies at any instant**;
  every strategy keeps its own sticky loss-limit; one shared daily loss cap of $30 (3%) flips the
  master LIVE_SWITCH off.
**PROBATION (first week at $1000):** new strategies run at MINIMUM size while the box engine runs
Stage-A size; only after 7 clean days do both step to Stage-B parameters together.

## De-escalation (automatic, no judgment calls at 2am)
- Any kill-switch trip → drop ONE stage's parameters for 7 days (sticky; operator re-arms).
- Drawdown >10% of bankroll → Stage-0 sizing ($5 notional, post 1) until 7 consecutive green days.
- A deployed A/B trial's live diff goes negative over 200 windows → un-deploy it, return to the
  prior config, and its re-entry needs a fresh 2-sigma pass.

## Why these numbers
- 7/14 days ≈ 270/540 windows at the observed ~38 active windows/day — enough for the per-window
  t-stat the tape says distinguishes +0.3¢/win from zero (σ≈16¢ → t≈2 needs ~250 windows... at
  +2¢/win; at +0.3¢/win nothing short of months distinguishes — which is WHY the gate is framed on
  daily-net consistency + risk events, not on a t-stat we can't reach).
- <30% unpaired vs 39% baseline = the chase fix doing its minimum job (the A/B's own estimate of
  floor-blocked completions is larger, but live queue position will eat part of it).
- Lock floor ≥0.5¢/box guards against "completing" our way into guaranteed-loss pairs (the chase
  give caps at 2¢ mid-window / 4¢ close, so erosion shows up fast if it's happening).
