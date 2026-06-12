# Five gold-tier-approaching candidates WITHIN Kalshi
### (PF >3, Sharpe >3, win ~100%, DD <3% — Kalshi-only, evidence from 14 research streams + our own tape/live data)

The within-Kalshi space is FRIENDLIER to the gold tier than the general market: Kalshi cannot ban
winners (exchange, not book), maker fees are $0 on crypto15m (and low/zero elsewhere — verify per
series), and every research stream agreed the surviving retail edge is MAKER positioning, which is
exactly what Kalshi's fee structure subsidizes. Ranked by evidence × gold-proximity.

---
## 1. FAVORITE-LONGSHOT MAKER HARVEST (cross-category) — the academically documented edge
**The trade:** systematically take the MAKER side against longshot buyers across Kalshi categories:
rest NO-side bids on overpriced tail contracts / YES bids on underpriced favorites, at maker prices.
**Evidence (the strongest stack of any candidate):**
- Whelan/GWU 2026 (300k+ contracts): <10¢ contracts lose buyers >60% of capital; >50¢ contracts earn
  positive; **makers earn positive returns, takers lose ~20% pre-fee** — structural, persistent.
- Becker microstructure: 1¢ contracts showed **57% maker/taker divergence**; entertainment/world
  events ~7pp gaps; weather calibration (lycheedata): 90-100% bins resolve YES 98.6% — the tail
  buyer's counterparty wins ~99% of the time.
- OUR OWN live calibration: 80-100¢ entries won 100% (n=11), 60-80¢ won 86%; 0-20¢ won 0%.
- OUR OWN A/B leaderboard: the two leaders (t02 yes-caution, t16 NO-preference, t≈2.8) are
  expressions of exactly this bias on crypto15m.
**Vs gold:** win rate per position 85-99% by price band; PF 2-3 plausible on the deep-tail band; DD
driven by correlated tail events (a longshot hitting) — size flat, diversify across categories and
the DD stays small. Capacity: moderate (tails are thin per market but there are hundreds of markets).
**Killer risk:** correlated tail realization (one news shock flips many longshots at once) — cap
same-theme exposure. Fee check per series required (maker fee 0 confirmed only on crypto15m).
**Verdict: NEAR-GOLD, the best evidenced. Build = generalize our maker engine beyond crypto15m
with a price-band whitelist.** Difficulty 3/5.

## 2. SPORTS-ORACLE MARKET MAKING (de-vigged sportsbook line as free fair value)
**The trade:** NOT cross-venue arb — pure Kalshi market making on sports, priced off the de-vigged
sportsbook consensus line (a free, sharp, continuously-updated fair-value oracle that Kalshi retail
flow does not use). Quote two-sided around fair value; collect the spread from retail takers.
**Evidence:** Kalshi sports = 89% of $22.9B 2025 volume (deepest books on the venue, verified via
Sacra); structural vig gap ~3.77% (Kalshi effective cost ~0.85% vs ~4.6% book vig — the retail
counterparty is anchored to worse prices); Becker: professional MMs flipped to **+2.5pp edge**
post-Oct-2024 as volume surged; no ban risk (exchange).
**Vs gold:** win rate per round-trip high but not ~100% (inventory holds game risk); Sharpe 1.5-3
plausible with strict inventory caps; capacity the LARGEST of any Kalshi candidate ($1k-10k/event on
majors). **Killer risks:** in-game adverse selection from fast bettors (quote pre-game/halftime,
pull during play); sports-series FEES must be verified (not fee-exempt like crypto15m); regulatory
cliff (STOP Corrupt Bets Act, state bans) makes the category's lifespan finite — build light.
**Verdict: NEAR — biggest absolute $ within Kalshi; sub-gold on DD/regulatory tail.** Difficulty 3/5.

## 3. PASSIVE LADDER-CONSISTENCY CAPTURE (resting monotonicity locks) — purest gold-shape
**The trade:** on multi-strike ladders ("BTC above X" for X1<X2<X3...), price must be monotonic
(P(>X1) ≥ P(>X2)). Instead of RACING violations (dead — our scan + literature), REST orders that can
only fill AT violating prices: e.g. a bid on the higher strike + structures that lock if both sides
fill. A fill = someone crossed into an inconsistency = locked profit at settlement, by construction.
**Evidence:** our live scan found ~64 apparent vertical locks (all phantom/illiquid at the touch —
takers can't capture them), but ladders DO dislocate transiently (QuantPedia: 41% of multi-outcome
conditions dislocate); the maker version waits for the dislocation to come to you — no speed race
(the meta-finding). This is our box logic generalized from {YES,NO} to {strike_i, strike_j}.
**Vs gold:** win ~100% on filled pairs (locked by construction — same as our box); the risk is the
LEGGED state (one side filled), identical species to our unpaired-leg problem, manageable with the
same machinery (completion chase, max-net). Capacity: small (these are thin markets); opportunity
frequency unknown — needs a 2-week passive shadow collector to measure before building.
**Verdict: GOLD-SHAPED, capacity-unknown. Cheapest research: point a collector at the BTC/ETH daily
ladders for two weeks and count crossable dislocations.** Difficulty 2/5 (reuses our code).

## 4. NEW/THIN-MARKET MAKER (volume-conditional mispricing)
**The trade:** rest wide two-sided quotes in NEWLY LISTED / low-volume Kalshi event markets (<$100k
cumulative volume), where mispricing is documented to persist for days-weeks and informed flow has
not arrived. Be the first book; collect fat spreads from early takers anchored on priors.
**Evidence:** Tetlock 2008 + JFE 2016: thin/immature markets are chronically mispriced; arXiv
"Anatomy of Polymarket": price impact ~50× larger pre-liquidity; mispricing persists until ~$100k
cumulative volume — **volume-conditional, not time-gated**, so no race; Becker's biggest maker/taker
gaps were in exactly the low-attention categories (entertainment, world events).
**Vs gold:** win rate high in QUIET markets (the early flow is uninformed by construction — informed
traders wait for liquidity); the killer risk is the occasional informed early actor (insider-ish flow
on niche events — cap size per market) and slow capital turnover (events resolve in weeks). PF 2-3
plausible, DD small if sized $10-50/market across many.
**Verdict: NEAR — diversified small-ticket version of #1 with wider spreads; pairs naturally with it.**
Difficulty 2/5 (listing-detector + our maker engine, slow polling is FINE here).

## 5. THE UPGRADED KXBTC15M BOX ENGINE (incumbent, compounding small edges)
**The trade:** what we run — strict-paired box harvesting on the only liquid fee-exempt short-tenor
book — upgraded with the validated stack: completion chase (deployed), t02 yes-caution gate (t=2.79,
~1 day from the n≥100 deploy bar), toxicity exit (t17/t18 accumulating), queue priority.
**Evidence:** ours, live: $0 maker fee confirmed on every fill; +17¢ realized in the first bridged
session; boxes pair ~100% when both legs fill; A/B forward test shows the gated variants positive
(+2.45¢/win OOS) in a regime where the ungated baseline LOSES 2.8¢/win.
**Vs gold:** per-BOX win rate ~100% (gold); window-level PF 1.65 → target 2+ with the full gate
stack; DD small in absolute cents; the binding constraint is CAPACITY (~$5-20/window at our queue
position) — gold shape, small absolute $. **It is also the platform every other candidate reuses**
(collectors, A/B harness, switch, alerts, dead-man).
**Verdict: NEAR-GOLD in shape, capacity-bound. Keep as the core; scale per SCALE_GATE.md.**

---
## Demoted within Kalshi (evidence-based, don't relitigate)
- **Taker Dutch books / crossed boxes:** zero on liquid markets (our live scan; median yes_ask+no_ask
  = $1.01); sub-second bot game.
- **Weather TAKER models:** speed-gated to NWS cycles (documented 0-for-32 retail postmortem); the
  weather TAIL-MAKER side folds into candidate #1.
- **CPI/macro nowcast taking:** Fed WP shows Kalshi CPI already tracks consensus; 25 events/yr.
- **Late-window favorite taking:** our backtest — fee + priced-in (maker variant unproven fill).
- **Wide-box hunting, multi-asset 15m boxes, ETH/SOL/XRP books:** our backtests — all OOS-negative.
- **BTCPERP carry:** real but min-size ~$1000 notional and margin not enabled at our tier — revisit
  at larger bankroll.

## Sequencing
1. (free, this week) Point a shadow collector at BTC/ETH daily LADDERS → measure #3's opportunity
   frequency. 2. (cheap) Fee-check + paper-quote 3 thin new listings → pilot #4 at $10-50/market.
3. Deploy t02 when it crosses the bar → #5 compounds. 4. Build #1's price-band maker as the first
   cross-category expansion (reuses everything). 5. #2 only after #1 proves the multi-series engine,
   and sized for the regulatory cliff.
