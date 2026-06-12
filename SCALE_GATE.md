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
- post 2→4; max-net 2→4 (= post); max-notional $20→$100 (10% of bankroll); loss-limit $12→$28.
  (Loss-limit derived, not arbitrary — the drawdown-cap formula from the sizing literature dive:
  keep P(daily loss > L) < 5% ⟹ L ≥ 1.645·σ_w·√N_w·post ≈ $1.72·post. post=16 ⟹ L ≥ $27.6.
  Equivalently N_max = floor(L/1.72): the $12 Stage-A limit supports post ≤ 6 — re-derive whenever
  σ_w (≈17¢/lot) shifts.)
- **MEASURED CAPACITY (empirical study 2026-06-12, 20k book ticks + 2,779 windows): KXBTC15M
  supports up to N=16 contracts/window (~$16 collateral/window, ~$608/day turnover) before the
  gates fail.** Depth is NOT the binding constraint (median touch: 764 YES / 673 NO contracts;
  N=16 is ~2% of it) — TAKER FLOW is: median one-side flow is only 476 ct/window, N=32 is 6.7%
  of it (FAIL) and fill rate collapses by N=64 (28% vs 95% at 1-lot). Fill rate at N=16 is still
  ~79%. So the contract ladder can eventually run 1→2→4→8→16 on this book (each step through the
  same gates: probation, markout, fill-p90) — 4× higher than this plan originally assumed — but
  $100+/window is physically unpairable (needs ≥100% of the market's own two-sided flow).
  Capital RECYCLES every 15 min, so N=16 uses only ~$16-32 concurrently; a $1000 bankroll is
  therefore never depth-limited, it is FLOW-limited to ~$600/day of box turnover on this book.
  The remainder deploys across STRATEGIES, not more size on one book — each behind its own
  pre-registered gate:
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

## Stage-B diversification — HOW the sleeves are built (operator request, 2026-06-12)
The $1000 stage deploys across SLEEVES, each an independent mini-business with its own ledger,
prospective test, sticky loss-limit, and entry gate. Design rules:
- **One shared master kill** (3%/day across everything flips LIVE_SWITCH off) + per-sleeve sticky
  limits; **<=30% of bankroll deployed at any instant** across all sleeves combined.
- **Category anti-correlation:** no two sleeves concentrated in the same event theme; the thin-market
  sleeve itself caps $150/category and $50/market.
- **Every sleeve passes the SAME bar the box engine faced:** prospective forward test vs a
  do-nothing baseline, pre-registered thresholds, >=2-sigma + economic sanity before real money.
- **Fee gates per sleeve (fee research 2026-06-12):** maker fee on each NEW series is verified with
  one 1-lot fill before sizing (no published per-series list exists); the new-listing 2-DAY FEE
  WAIVER makes fresh listings the cheapest entry for the thin-market sleeve; enroll in the Volume +
  Liquidity Incentive Programs (we qualify; up to $0.005/contract back).
- **The sleeves and their prospective tests (RUNNING AS OF TODAY):**
  1. Thin/new-market maker -- kalshi_thin_collect.py (tracks ~40 real thin event markets: 5-7c
     spreads, OI 300-6,700, ~zero daily volume) -> offline scorer paper-rests quotes at the recorded
     touch, infers fills from later prints, scores vs hold-nothing. Gate: >=2 weeks data, paper PF
     >=1.5 and positive after the per-series fee check.
  2. Ladder-lock maker -- kalshi_ladder_collect.py (BTC/ETH/S&P/Nasdaq ladders) counting crossable
     monotonicity violations. Gate: >=5 crossable dislocations/week observed, else the sleeve dies.
  3. Favorite-band maker -- same thin-market data, scoring restricted to the 60-95c band (the
     documented favorite-longshot maker side). Gate: same as (1) on the band subset.
- **Capital plan at $1000:** core box engine $100 cap (post 4) + sleeve 1 $150 + sleeve 2 $50 +
  sleeve 3 $100 (only after sleeve 1 validates) = max $400 deployed (40% hard ceiling, 30% target),
  $600+ reserve. Idle cash earns nothing on Kalshi -- the reserve is THE ruin-protection, not waste.

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

---
# STATUS + ROADMAP UPDATE (2026-06-12, operator scaling directive)

## Stage-A ($10→$100): the strategy is IN PLACE; the gates need TIME, not more research.
Dashboard: `python scale_status.py` (run daily). As of today: green-day streak 1/7; unpaired 18%
(passing rate, needs 150 windows); no kill trips; A/B ledger 100/300.
- **Deployment is pre-wired:** `--guard-yes-spread` is CODED in kalshi_trader.py (default OFF) —
  the live port of t36's dominant component (backtest: OOS +2.07c/win vs P0 +0.69, YES strands
  36→1 = the entire realized live loss mode). When t02/t36 clears the forward bar at n≥300,
  arming = one flag in live_loop.sh. Completion quotes are never suppressed (chase intact).
- **The binding constraint is CONTINUITY**: gates 1+4 need ~5-7 more clean days of bot + collector
  uptime. The container is ephemeral — the GHA cloud loop (live.yml, on main) is the durable path
  and STILL NEEDS the operator to add the GitHub secrets (KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY,
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID). Without them, every container death pauses the clock.
- Execution upgrades landed today (compound at any size): qtime margin re-fit 0.3→0.6c
  (QUEUE_VALUE.md break-even), no rung-splitting (t27 AGAINST), never reprice <0.5c.

## Stage-B ($100→$1000): confirmed MULTI-STRATEGY; the sleeve pipeline is already collecting.
Today's research sharpened the Stage-B map:
- BTC 15m box is FLOW-capped (~N=16, ~$600/day turnover) — more capital on this book does nothing.
- **Alts are NOT a sleeve** (MULTI_ASSET.md: ETH/SOL/XRP structurally negative-EV; re-test at 5-10x
  volume growth). t27 two-rung is OUT (QUEUE_VALUE.md). Polymarket wallet line: pending signature
  study; at best a detector refinement, not a sleeve.
- The viable sleeves remain the three ALREADY pre-registered + collecting (thin/new-market maker,
  ladder-lock, favorite-band — kalshi_thin_collect.py + kalshi_ladder_collect.py, gates above).
  First sleeve decision possible after ~2 weeks of collector data (~2026-06-25).
- Sequence: Stage-A box at post=2 → sleeve 1 paper-gate verdict → sleeve 1 at $50-150 → Stage-B
  entry per the pre-registered conditions. The box engine stays the core; sleeves absorb the
  capital the box physically cannot.
