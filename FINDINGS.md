# Polymarket 15m BTC Up/Down — backtest findings

**Data:** Binance 1s spot + pmxt v2 archive (`r2v2.pmxt.dev`) order book/trades,
2026-04-14 → 2026-04-17 UTC (post-Jan-2026 fee regime). Market discovery via
Gamma (`btc-updown-{tf}-<utc_ts>`). READ-ONLY; no orders, no trading keys.

## THE THROUGHLINE (read this first)
Every lever that tried to be **clever about which fills to take, hedge, or forecast DIED**:
taker signals (fee is the moat), fill-selection / markout-toxicity gating, alpha-skew,
fair-value fill gating, the delta-hedge, and predictive-repricing's prediction channel. The
levers that **survived are the boring structural ones**: quote both sides, stay flat with a
cheap inventory skew, **size more**, **capture more markets**, win the queue. This is the
strategy telling you what it *is* — a thin, structural, capacity-bound liquidity edge that
rewards being bigger/broader/faster, **not smarter**. The experiments below prove that's the
shape of the edge, not a failure of imagination. Corollary for effort allocation: spend it on
**capacity and execution**, not on signal research.

## Data quality (dataqc.py) — PASS
- Window boundaries are **UTC, 900-s aligned** (slug ts %900==0, endDate=start+900);
  the ET in titles is cosmetic. No UTC/ET offset.
- Spot-label vs market resolution agree **100% on all 225 big-move (>=5bps) windows**;
  the 12 disagreements are all sub-5bps near-ties. Up/Down not inverted
  (direction-agreement 93%). Density ~92k book updates/window.
- **Fee = 1000 bps (10%) on takers**, not the spec's ~700. Verified market identity
  3 ways (slug -> conditionId -> asset_id). Makers pay 0 (Polymarket docs);
  taker fee = `0.10 * p * (1-p)` per share.

## The one methodological key: window-clustered significance
Trades/eval-points inside a window share one outcome, so they are **not
independent**. Per-trade t-stats are inflated by ~sqrt(trades/windows). All
verdicts below use **window-clustered** t-stats (the honest unit ≈ N windows).

## Taker fair-value-vs-quote (run_real.py) — FAILS (artifact)
- Raw sweep looked great: t≈+3.6→+4.3, World-A shape (late + mid-price). But:
  - Raw t was itself ~3.6x clustering-inflated (true ≈ t≈1.0).
  - **Truncation test:** exclude final 180s → full mean **−0.0043 (t=−0.55)**,
    OOS halves disagree in sign. The entire result was the last 180s.
  - **Vol-insensitivity** of the late bucket (t≈13 at sigma 0.5x–3x) is the
    mechanical-pinning fingerprint, not alpha.
- Conclusion: fill-at-quote books the **maker's spread** the taker can't capture.

## Pre-registered search (H1/H2/H3) — none pass

| Hypothesis | Honest metric | Verdict |
|---|---|---|
| **H1** maker hold-to-resolution, BTC 15m | window-clustered **t=+0.26** | no edge |
| **H2** BTC→alt lead-lag (ETH/SOL/XRP), 15m | btc coef sign-incoherent, hit≈0.50, fails multiple-testing | no signal |
| **H3** maker, BTC 5m | equal-wtd t=+2.64 **but size-wtd +0.0054, 95% CI [−0.012,+0.021]**; weakens OOS; t→1.5 sans final 60s | not economic |

Realized-trade economics (every trade has a real maker counterparty):
- BTC 15m: taker net **−0.0023/share** (lose after fee), maker ~flat.
- BTC 5m: taker net **−0.0195/share**, maker size-weighted **+0.0054 (CI spans 0)**.
The dominant, reliable structure is **takers lose roughly the fee** — i.e. the
edge is captured by the fee (Polymarket), not by either side of the book.

## Bottom line
After pre-registering 3 economically-motivated hypotheses and applying
truncation + out-of-sample + window-clustering + multiple-testing + size-weighted
economic significance, **no strategy clears the bar.** The harness correctly
rejected everything, including the things that looked like +4 t-stats.

A genuine winner here would need a lever this dataset cannot score: maker **fee
rebates** (flips maker economics), **active inventory/hedging** quoting models
(not scoreable from historical quotes), or **sub-second execution** for
cross-asset lead-lag (needs tick infra beyond hourly-bucketed archive).

## Round 2: five literature-grounded hypotheses (ideas2.py) — none pass

Tested as signals/calibration/realized-economics (not fill-at-quote), window-
clustered, Bonferroni |t|>2.58.

| # | Idea (lit) | Result | Verdict |
|---|---|---|---|
| I1 | favorite-longshot bias (Snowberg-Wolfers) | calibration gaps all <4%; compression slope b=1.06 (NOT <1); bet-favourite t=-0.58 | **well-calibrated, no FLB** |
| I2 | trade-flow imbalance / OFI (Cont et al.) | net-buy-fraction coef t=-0.08 beyond price | no incremental signal |
| I3 | intraday/session seasonality (Wen et al.) | every session: maker \|t\|<0.8, taker_net<0 | no seasonal edge |
| I4 | fade-the-dislocation (reversal) | clustered slope t=-1.12 (naive -2.27 was the clustering illusion) | no clean reversion |
| I5 | better vol model (BS-for-PM, VRP) | constant sigma Brier 0.156 = best; rolling/VRP worse | vol is NOT the binding constraint |

**Why nothing works:** the 15-min BTC market is **well-calibrated** (mean_fair 0.525
vs realized 0.521; Brier 0.156; price-bin gaps <4%) and price already impounds
order flow. This matches the "informed minority (~3%) keeps prices efficient"
literature. The only reliable structure remains takers-lose-≈-the-fee. Across
TWO rounds (taker fair-value + H1/H2/H3 + I1-I5), no strategy survives rigorous
validation; the harness rejected every candidate, including the ones that looked
significant before clustering/truncation/economic tests.

## Round 3: acquired maker-rebate data + proper market-making (markout) test

Acquired (Polymarket docs): makers pay 0 fees and receive a rebate ~= 20% of the
taker fee their liquidity generates (crypto), i.e. ~0.20*0.10*p(1-p) (~0.0035/share
here), plus a separate daily Liquidity-Rewards pool (not per-share quantifiable).
Deribit historical option data is reachable but its daily/weekly expiries can't
match Polymarket's 15-min strikes -> set aside.

Re-tested market-making properly via MARKOUT (a real MM captures spread and
flattens; hold-to-resolution bundles in directional risk), in-window only,
window-clustered + size-weighted + bootstrap CI + OOS, **with rebate**:

| 1s markout (+rebate) | size-wtd [95% CI] | OOS halves |
|---|---|---|
| MID-exit (frictionless; = mechanical half-spread) | +0.0063 [+0.0044,+0.0093] | +8.8/+4.3 |
| CROSS-exit (pay spread to flatten; honest floor) | +0.0013 [-0.0007,+0.0043] | **-2.6/+1.3** |
| hold-to-resolution | -0.0089 [-0.040,+0.021] | -0.0/+0.7 |

Bug caught & fixed: the first markout pass omitted the in-window filter; 10,285
pre-open + 2,610 post-close trades flipped the sign (+0.015 vs the correct
-0.012). After fixing, hold-to-resolution reconciles with maker_sim.

**Verdict: maker thesis FAILS even with rebates.** The only positive component is
the **mechanical half-spread** (MID-exit), which is unrealizable without
frictionless/queue-favorable fills. Under realistic flatten-by-crossing the edge
is statistically zero (CI spans 0) and **sign-flips out-of-sample** (first half
-2.6). Hold-to-resolution + rebate is negative. Capturing the spread for real
needs queue-position / two-sided-fill modeling that historical trade+quote data
cannot validate -- the lever remains genuinely unscoreable, not merely untested.

## Round 4 + 5: more strategies, diagnostics-driven theses (new data: Up+Down books, alt books, wallet-attributed trades, strike ladders)

No-data tests (all fail): S5 TS-momentum, S8 whale-follow (t=+0.00), S9 impact-reversion
(large trades have PERMANENT impact, fading loses t=-5.5), D late-extreme calibration,
E token-momentum.

Acquired data + tests:
- **S4 overround arb** (Up+Down books): Up_ask+Down_ask always >=1 (min 1.001), no
  crossing -> no arb (book internally consistent).
- **A strike-ladder arb** (10-strike 'above $K' ladders): MID non-monotone 43.9% of
  snapshots (mispricing signal) but **0 crossable inversions** -> absorbed by spread.
- **B cross-venue (Kalshi)**: archive 404, not available.
- **S2/D3 cross-sectional reversion** (4-coin token panel): GROSS edge REAL (+0.0068/step,
  t=+4.40; clustered slope t=-2.95) but round-trip cost ~0.10/pair (2 spreads + 4x10% fee)
  -> NET taker -0.093 (t=-56). Killed by fees (~15x the edge).
- **S3 / D1 market lead-lag**: alt tokens move contemporaneously with BTC token; lagged
  coef ~0.02 (t~0.6) -> no tradeable lead-lag.
- **Copy-the-informed-minority** (wallet-attributed trades, 628k trades / 10.8k wallets):
  top-1% wallets capture 45.5% of positive PnL (real informed minority). Ranking by
  per-trade ROI does NOT persist (t=0.7); ranking by TOTAL PnL **persists OOS**
  (+0.018/trade, **t=+3.76**). BUT a realistic follower (enter +60s later, taker, 10% fee)
  **loses -0.038/trade (t=-5.93)**: the wallets' ~1.8c/trade edge < the ~2.5c taker fee.

**Unifying conclusion across all rounds:** several signals are genuinely REAL
(cross-sectional reversion gross t=4.4; wallet-skill persistence t=3.76; ladder mid
non-monotonicity 44%) -- but every one is smaller than the 10% taker fee + spread, so
none is tradeable by a fee-paying taker. **The fee is the moat.** The structure is
captured only by fee-exempt maker/price-setters (0 fee + rebate), which historical
trade+quote data cannot score for queue position / fills. Verdict stands: no
backtestable taker strategy survives; the only viable seat is informed market-making,
which requires live fill data to validate.

## Round 6-7: hedge-fund playbooks, recombination, and the first STRONG candidate

JS/fund-style tests (corrected per-category fees, window-clustered, OOS):
- **Selective (toxicity-filtered) MM**: confirms small=benign/large=toxic structure but only
  breakeven under honest cross-to-flatten (queue-bound).
- **Two-Sigma ML ensemble**: market price BEATS the kitchen-sink model OOS (Brier 0.154<0.157);
  no predictive edge over price. Combining predictive signals does NOT stack into alpha.
- **Combination / trained toxicity-model maker**: selecting "best" fills makes it WORSE OOS
  (chases toxic vig); signals don't recombine into a maker edge.
- **Overround (S4) / 2-sided structure**: Up_ask+Down_ask ~1.01 always (no taker arb).

**>>> STRONG CANDIDATE: inventory-capped 2-sided maker (rebate farming).**
Quote both Up+Down, cap net delta. Earlier "maker fails" was ONE-sided only; making BOTH
sides hedges direction. Decomposition (cap=100, corrected 0.07 fee basis):
  GROSS trading +0.00007/sh (t=0.81, breakeven) ; + 20% maker rebate -> +0.00098/sh (t=12.2);
  IS/OOS t = 12.2 / 7.4 ; survives 50% rebate haircut (OOS t=4.3). Edge = the rebate; gross
  is breakeven taking ALL flow (worst-case adverse selection). cap is the risk/Sharpe knob
  (cap=25 t=19, cap=400 t=7.7). Paper-trading spec in PAPER_TRADING.md. Live unknowns:
  fill rate/queue, realized rebate pool share, adverse-selection-weighted fills.

**Multi-category calibration / favorite-longshot battery (3,056 resolved markets):**
- **Sports (fee 0.03): strong FLB**, bet-favourite +0.12 net (t=9.3), survives 5c half-spread
  (+0.07, t=5.5). BUT concentrated in slight-favourites (0.5-0.6: +0.245) and VANISHES in the
  most-liquid markets (n_pts>=300: t=-0.05); markets are illiquid UFC/MMA prop/futures whose
  tradable liquidity can't be verified from this data. REAL bias, tradability unproven ->
  strong lead needing LIVE liquidity validation, not a ready candidate.
- geopolitics (fee 0): favourites slightly OVER-priced (bet-fav negative) -> reverse bias.
- politics/tech/economy/culture/crypto: ~0 or negative net of fee.

**Answer to "combine the inefficiencies":** predictive signals are already in the price
(ensemble loses to price; combining doesn't help). The only net-positive, robust, ready edge
is the STRUCTURAL one (maker rebate), which doesn't need to beat the price. Sports FLB is a
real second inefficiency but lives in illiquid markets (untradeable from this data).

## Round 8: refine the maker before paper trading

Adjacent ideas tested on the inventory-capped 2-sided maker:
- per-quote SIZE LIMIT (post small depth): HURTS (the 2-sided vig scales with captured
  volume; throttling reduces it). Rejected.
- STOP quoting in the final sprint (tau<cutoff): HURTS (less volume/rebate, vig present late
  too). Rejected.
- **inventory CAP is the key knob — and TIGHTER is better/safer.** At cap<=25 the GROSS
  (no-rebate) edge is positive & significant: cap=25 gross +0.00019/sh t=+5.8 (OOS 3.3),
  cap=10 gross t=+10.6 (OOS 5.9), with near-zero drawdown ($0-11). NET (+rebate) t=20-24
  (OOS 11-13). **Zero-rebate stress (cap=25): survives (gross OOS t=3.3).**

REFINED VERDICT: the candidate is a **tight-inventory 2-sided vig-capture maker** whose
gross edge stands alone (rebate no longer a single point of failure; it ~triples the return).
Start cap~20, near-zero drawdown, gross-positive, rebate on top. Capacity is the tradeoff
(tight cap = small $/market) -> scale via MULTI-MARKET diversification (BTC 5m + ETH/SOL/XRP
15m, each an independent vig stream), the validated next step (needs up+down trade pulls).

## Round 9: refine for deployment (inventory skew + capacity)

Tested on historical data while the paper run collects prospective data:
- **Price-regime filter (quote only near 0.5): REJECTED.** Restricting hurts net (band=0.5/all
  is best); the cap already handles tail risk and extreme fills aren't as toxic as feared.
- **Inventory skew (Avellaneda-Stoikov-lite): WIN.** Lean to flatten once |delta|>=skew*cap.
  Monotonic improvement (skew_frac 1.0->0.25): cap=20 GROSS t 4.9->11.9, NET OOS t 12->16,
  maxDD->$0. Skewing cuts directional variance -> sharper, gross-stronger edge.
- **Capacity (skew unlocks bigger cap):** with skew=0.25, gross stays positive at large caps
  where the un-skewed version went negative (un-skewed cap=400 gross t=-0.28; skewed +4.8).
  Frontier: cap=20 gross t=11/$12k/maxDD$0; cap=50 gross t=8.6 (zero-rebate OOS t=5.0)/$18k/$7;
  cap=100 t=7.2/$24k/$31. **Deploy config: cap~50, skew 0.25, quote all prices** -- 2-3x the
  capacity of the original at near-zero drawdown, gross-positive without the rebate (OOS t=5.0).

Overnight paper run switched to this refined config (cap=50, skew=0.25). live_trader.py +
paper_trader.py updated with the skew. Note: the audit_*.jsonl capture raw market data, so any
config can be re-simulated offline from the prospective tape.

## Self-improvement loop — iteration 1: robustness / not-overfit
- cap x skew NET-OOS-t heatmap is a BROAD PLATEAU (all cells +7..+13), not a spike ->
  config is robust. Tighter skew (0.15) marginally better than 0.25 (Sharpe-vs-$ knob).
- Time sub-period stability (deploy cfg cap=50/skew=0.25): net positive & significant in
  all thirds (t=20.6 / 25.2 / 7.9). Edge is not a single-period blip.

## Self-improvement loop — iterations 2-5
- iter2 flow-imbalance filter: marginal (OOS t +0.4 at -16% volume); skew already absorbs
  adverse selection -> REJECT (keep simple).
- iter3 capture-fraction realism: per-share edge ~invariant (slightly higher at low capture);
  $ scales ~linearly with captured volume (f=10%~$1.2k/day @645k sh/day; f=5%~$660/day).
  Confirms: edge/share solid, absolute $ is a capacity/queue game ($100 -> tiny f -> tiny $).
- iter4 bake-off + bootstrap CIs: ALL configs have net AND gross-only(zero-rebate) 95% CIs
  strictly >0 -> edge is rebate-INDEPENDENT. Tight skew lets cap rise with $0 drawdown.
- FRONTIER (skew controls risk, cap sets size): cap=20/skew=1 (net CI[.00055,.00066], DD$1);
  cap=50/skew=0.25 (net CI[.00087,.00105], DD$7); cap=100/skew=0.15 (net CI[.00111,.00136], DD$0).
- DEPLOY: start cap=50/skew=0.25; scale toward cap=100/skew=0.15. Price filter & flow filter
  rejected. Edge = tight-inventory 2-sided vig (gross-positive, rebate-independent) + rebate.

## External review response + auto-flatten test
External review verdict: strategy A+, live profitability ~90% infrastructure (latency/queue/
OMS/keys). Concur. WS feed already adopted (addresses staleness). Concrete strategy item
tested -- "auto-flatten residual vs hold to resolution":
- hold-to-resolution: per-share +0.00095 t=+20.0, maxDD $7 over 288 windows.
- auto-flatten (cross at final mark): per-share ~0 t=-1.2 (adds spread cost + mark noise).
-> Inventory skew already keeps the residual tiny (maxDD $7), so the directional-residual
   concern does NOT bind; KEEP hold-to-resolution. Auto-flatten is optional LIVE risk hygiene
   (oracle/settlement-time risk), not a PnL improvement.

## Tier 1 reviewer idea — fair-value-model quoting / adverse-selection gating (TESTED, REJECTED for gating)
Reviewer's #1 idea: build a P(up) model from a low-latency SPOT feed and let it drive
quoting (gate/skew away from toxic flow) instead of pegging to the book. Tested whether
the spot fair value `fair_up = Phi(log(St/S0)/(sigma*sqrt(tau)))` (fairvalue.fair_up,
the actual resolution driver, NOT a book echo) identifies fills that hurt the maker.
`fv_maker.py` (capped gate sim), `fv_analysis.py` (per-fill discriminator), `fv_confirm.py`
(pre-registered capped test).

**Two methodology bugs caught and fixed first (both would have produced false results):**
1. trade `timestamp` is `datetime64[us]`; `astype(int64)//1e6` yields SECONDS not ms, so
   `tau` was a unix timestamp and `fair_up` collapsed to ~0.5 everywhere -> the first run's
   "fair-value gate" was secretly just a `price-far-from-0.5` filter. Fixed via
   `datetime64[ms].view(int64)`.
2. the inventory cap is PATH-DEPENDENT; the confirm sim must replay fills in (window,time)
   order. Sorting by window only (file order = all-Up-then-all-Down) flipped the capped
   baseline from +$16k to -$1k. Fixed with `np.lexsort((t_ms, win))`.

**Right metric (per reviewer): window-level Sharpe, n=288 windows FIXED regardless of how
many fills a gate skips -> no n-reduction tax (a t-stat falls mechanically when a gate cuts
volume, so t can't tell "cut edge" from "cut volume"). Fills scored at the RESOLUTION
horizon we actually hold to, not the short-horizon fair flag.**

Findings (uncapped per-fill discriminator unless noted):
- `corr(fair_edge, res_pnl) = +0.023` — weakly informative in the right direction, not a
  strong toxicity flag.
- Regime split (this is the real result): adverse selection is concentrated in **extreme
  edge AND near expiry** (decile 0, fair_edge<~-0.10, settles -0.027/sh). **Mid-window
  moderate-edge fills MEAN-REVERT and settle positive** (gated mid-window fills earned
  +0.006..+0.014 while kept ones were negative) — exactly the regime a passive maker is
  structurally long (Chakraborty-Kearns). A flat gate therefore cuts good flow.
- Binary gate on window-Sharpe (n fixed): **no threshold beats baseline**, IS or OOS.
- Continuous sizing `w=clip(1+k*fair_edge,0,2)` weakly beats binary gating (k=2 Sharpe
  +0.021 vs gates <= -0.005), matching r>0 — lean, don't chop — but the effect is tiny.
- **Pre-registered confirmatory test (capped real strategy, E_X=0.10/TAU_X=120s, not swept):**
  skip only extreme-edge near-expiry fills. cap=50 OOS Sharpe +0.543 -> +0.507; cap=100
  +0.468 -> +0.456. **No OOS improvement** — even the one genuinely-adverse regime is a wash,
  because the inventory cap + 2-sided structure already neutralizes that adverse selection.

**Scoped conclusion:** short-horizon spot fair value does NOT improve the capped maker via
fill selection (gating) on this hold-to-resolution book. RETIRE gating. Keep fair value for
the two uses a fill-tape backtest CANNOT score and that remain live-plausible: (a) PREDICTIVE
REPRICING / queue timing — move the resting quote when the model moves, before the informed
taker arrives (a latency effect, invisible to tape replay which only shows fills that
happened, not cancels you'd win); (b) marginal continuous sizing. This matches the prior
result that book-mid markout toxicity filtering also hurts — fill SELECTION is the wrong
lever; the edge is structural and you must take both sides.

## ROADMAP #1 — delta-hedge residual inventory with a BTC perp (TESTED, REDIRECTED)
`hedge_sim.py`. Four arms on the SKEWED (deployed skew=0.25) book + a no-skew surface,
frictionless (upper bound) vs practical (perp fee 4bps + funding + $25 rebalance band),
scored on window-Sharpe (n=288 FIXED). Baseline reproduces the known capped P&L
(Sharpe 0.913/0.815/0.695 at cap 50/100/200) before any treatment is trusted.

The instrument fights back, by theory not bug: a binary's gamma DIVERGES at expiry (the
spot->prob map is a vertical wall as sigma*sqrt(tau)->0), so naive continuous hedging
rebalances hundreds-to-thousands of times/window (first cut: $276k perp fees = the math
working). A binary can't be dynamically replicated near resolution (incompleteness).

Findings (refine BOTH the "variance is hedgeable" and "tail-concentrated" priors):
- **The frictionless ideal hedge raises Sharpe 0.913->1.011 but leaves std UNCHANGED
  (70.25->70.78).** So its benefit is a MEAN effect (+~$7/window): the inventory carries a
  small adverse-selection DRIFT a perfect hedge removes. The within-window variance is
  NON-DIRECTIONAL (ideal std == baseline std) -> a perp cannot reduce it. Hedging was never
  a variance play here.
- **Practical hedge is net-destructive at every cap and every tau_freeze** (Sharpe -1.7..-2.9,
  fees $130k-$460k). Freezing the last 300s cuts median rebalances only 557->356 (~36%): the
  gamma churn is spread THROUGHOUT the window (BTC ticks are large vs the ~13bp window-vol),
  not tail-concentrated. So "hedge the last 90s is the problem" does NOT hold; it's costly
  everywhere. The +$7/win benefit is ~66x smaller than the ~$460/win perp fees the gamma forces.
- Skew already delivers Sharpe 0.91 AND the cap can be raised WITHOUT hedging (cumulative P&L
  stays positive; $tot rises 18.5k->33.8k from cap 50->400). The brake hedging was meant to
  release (can't raise cap) is not binding.

**Verdict: skew DOMINATES the perp hedge at this scale; do not build the perp hedger.**
Revisit only if scaled past the point where refusing the leaning side (skew) leaves real
volume on the table -- then take+hedge could beat refuse. Funding negligible at 15m, as expected.

CORRECTION (reviewer): do NOT hand the +$7/win residual to #4 as "its job" -- that's a hopeful
handoff. The frictionless figure is a CEILING: ~$2k total recoverable WITH PERFECT HINDSIGHT of
the within-window path. Whether #4 can touch it is gated by a quote-time-predictability test
(below) and a brutal ~$7/win cost bar. Recorded as an open question, not a promise.

### Drift-predictability gate for #4 (drift_predict.py)
Is the adverse drift the hedge harvested PREDICTABLE from quote-time features (a forecast #4
could pre-position on), or only harvestable ex-post? Per-fill drift = d_delta*(resolved_up -
p_up_at_fill); regress on EXOGENOUS quote-time features (signed_size excluded -- mechanically in
the target).
- **OLS R^2 = 0.0035; corr(prediction, drift) = 0.059** -- all of it the weak `fair_edge`
  signal (corr -0.059) that ALREADY failed fill-selection. **BTC 30s momentum corr = 0.0004**
  (zero -- past moves don't forecast within-window drift; market efficient). tau corr 0.005.
- => **#4 prediction channel is CLOSED, not deferred.** The within-window adverse drift is not
  predictable from ANY quote-time-observable feature tested (R^2~=0.003, entirely a signal that
  already failed elsewhere; momentum forecast power 0.0004 == absent, not weak). Predictive
  repricing has NO forecasting channel. Only the LATENCY-RACE channel survives -- react to a
  CONTEMPORANEOUS spot move faster than the taker (not a forecast) -- scoreable solely live, and
  bounded by a <=$2k ceiling that perfect foresight wouldn't beat, net of the queue position
  every cancel forfeits. Three doors shut at once: prediction is dead, the ceiling is measured,
  the one live channel is named with its bound attached.

### Raising the cap -- tail check (cap_tail.py)
Is the cap-50->400 lift ($18.5k->$33.8k) scaled edge or a few lucky terminal settlements?
- **Scaling edge:** 75.3% of windows IMPROVE when raising the cap (broad-based); 93-99% of
  windows positive; **jackknife Sharpe RISES when the best 5 windows are dropped** (0.91->1.47
  @cap50, 0.66->1.01 @cap400) -- the edge is in the bulk, not the tail.
- **Bounded caveat:** the INCREMENTAL gain has mild terminal-move concentration -- top-10
  windows = 31% of the gain; top-decile-|move| windows contribute 20.6% (2x their 10% share);
  corr(incremental, |terminal move|) = +0.137.
- **Cap frontier (the refinement): jackknife Sharpe peaks at cap~5 (1.95) and DECREASES
  MONOTONICALLY** with cap (1.66@50, 1.34@100, 1.17@200, 1.01@400) -- there is NO interior
  optimum. The cap is a pure CAPACITY DIAL: more $tot ($4.6k@5 -> $33.8k@400) for less
  luck-adjusted Sharpe, smoothly, with NO cliff (pos% >=93% throughout). So "maximize jackknife
  Sharpe" => run tiny; the real decision is WHERE TO SIT on a smooth Sharpe-vs-capacity frontier
  given capital + risk budget.
- **Verdict: the cap is a risk-budget choice, not an optimization. For the live pilot START
  SMALL (cap~25-50: jackknife Sharpe ~1.5-1.7, validates fills/queue) and CLIMB the frontier as
  fills/queue confidence and capital grow -- each step trades measured Sharpe for $, no cliff.**

## ROADMAP #2 — Liquidity Rewards stream (TESTED, REDIRECTED: $0 on our market)
`rewards.py` (config reader + screener + live-book share estimator).
- **BTC 15m markets: `rates: null` on every window** -> liquidity rewards are UNFUNDED there.
  The scaffold exists (min_size=50, max_spread=4.5c) but pays $0. The only active incentive on
  our market is the maker rebate (makerRebatesFeeShareBps=10000), already in our model.
- The `rates` field IS populated where rewards are funded (validated reader), and those markets
  are **politics / longshots** ($100-$1000/day pools): Peruvian/Colombian/Brazilian elections,
  Fed-rate, SpaceX-IPO, etc. -- slow, not spot-tied, different microstructure. Our fast-binary
  vig+skew edge does NOT port to them.
- Share estimate (live-book denominator): on the largest pool ($1000/day), a $200 two-sided
  placement at 1c from mid earns **~$2.27/day** (share 0.23%, competing Qmin ~53k) AND bears
  the market's election-resolution risk. So reward-farming is a SEPARATE strategy on OTHER
  markets, not incremental revenue on our quotes.
**Verdict: rewards do not stack onto the BTC 15m strategy (unfunded). The reader auto-detects
if BTC turns on; the screener ranks where farming is its own (small, capital-parked) play.**
So the "#2 = rewards" leg is retired for our market; #2 becomes **scale the cap + multi-market**.

## ROADMAP #5 — multi-market scale + portfolio delta (multimarket.py)
Crux: is "neutral-in-each" neutral overall? Spot per-window return corr across BTC/ETH/SOL/XRP
15m = **0.81 mean** (BTC-ETH 0.91 .. XRP-BTC 0.74); resolution (Up/Down) corr 0.49-0.73. The
underlyings ARE ~one risk factor.
- BUT maker P&L variance has two parts: a NON-directional vig-capture part (independent across
  books -> diversifies ~sqrt(N)) and a DIRECTIONAL residual (correlated rho). The hedge
  experiment measured the directional FRACTION: on the skewed book the ideal delta-hedge could
  not cut std => f~=0.01 (no-skew <=0.06). So the correlated piece is small.
- Portfolio Sharpe multiple = sqrt(N)/sqrt(1+f*(N-1)*rho): **x1.98 at f=0.01 (deployed), x1.87 at
  f=0.06** for N=4 (edge always x4). The naive "all-directional" assumption (f=1) would give only
  x1.08 -- that was the wrong model. Crossover where the correlated term dominates: N~=22 books.
- **Verdict: #5 is a CLEAN capacity win at this N -- edge x4, Sharpe ~sqrt(N).** Guardrails:
  (1) NET DELTA AT THE PORTFOLIO LEVEL (the small correlated residual is the only non-diversifying
  part; it grows ~N^2 and dominates only past ~20 books or if skew is loosened);
  (2) per-market maker P&L for the alts needs their TRADE tapes -- only top-of-book is on disk, so
  fetch ETH/SOL/XRP trades to confirm the per-book edge ports before sizing real capital there.

## ROADMAP #1 (capacity primitive) — mint/merge (mintmerge.py, collateral.py)
Mint/merge is the CTF-native collateral primitive (split $1 USDC -> 1 Up+1 Down to source
2-sided inventory; merge matched pairs -> reclaim $1). It makes posted collateral a function of
NET DELTA (~$cap), not of cumulative gross turnover -- the capacity unlock, with NO model risk
(exact $1 conservation). Required for the live build, not optional. Decision logic in
`collateral.plan()` (tested); on-chain executor `MintMerge` (web3, live-only, guarded); wired
into `live_trader.py` (merge at rollover). NOT a P&L lever -- it removes a capital constraint.

## #5 caveat (record precisely): √N is banked diversification on UNBANKED fills
The Sharpe x1.98 is PROVEN diversification structure on an ASSUMED input: it holds **iff alt
fill rates match BTC**. Alts are book-only / BTC-5m is UP-trades-only on disk, so the x4 edge is
modeled on fill PARITY across books -- the same live-only unknown that gates everything. Honest
claim: "breadth gives ~sqrt(N) diversification of a non-directional edge with ~1% residual-corr
drag, headroom far beyond the 4-5 markets accessible (N^2 crossover ~22 is out-of-domain, not a
target) -- CONDITIONAL on alt fill rates matching BTC, a live-pilot measurement." Diversification
banked; per-book fill rate unbanked.

## OFFLINE RESEARCH PROGRAM — COMPLETE
The investigation has converged. Mapping every lever:
- **DEAD** (tested, retired): taker signals; fill-selection / markout-toxicity gating; alpha-skew;
  fair-value fill gating; delta-hedge (variance is non-directional); predictive-repricing's
  PREDICTION channel (drift not quote-time forecastable, R^2~0.003); liquidity rewards ($0 on BTC).
- **VALIDATED GROWTH LEVERS (both pure capacity, both structural):**
  1. **Raise the cap** to the risk-budget point on a smooth Sharpe-vs-capacity frontier (jackknife
     Sharpe is monotone, peaks at small cap -> start small, climb; no cliff).
  2. **Scale to 4-5 funded crypto books** with a PORTFOLIO-level delta cap (~sqrt(N) diversification,
     ~1% corr drag) -- conditional on alt fill parity.
  Plus mint/merge as the collateral primitive that makes the size feasible on fixed capital.
- **LIVE-ONLY (unscoreable offline; the pilot's job):** real fill rate / queue position won;
  latency-race repricing vs its <=$2k/queue-cost bar; whether the cap raise and alt edge hold
  under live fills + competition.
**The next bit of information that changes anything costs real money and comes from the pilot.**
The honest next move is NOT a #6 -- it is to deploy the two validated levers SMALL and measure
the one input the whole edifice now rests on: capture rate. Build is done; go measure.

## CRITICAL CORRECTION (live paper vs offline fill model) — the edge is REBATE, not vig
Deep dive on live paper data (deepdive.py) + offline cross-check on the SAME historical tape
exposed a large fill-model artifact. The historical DATA is sound (dataqc: 0 FAIL / 2 WARN /
23 PASS; live-vs-historical overround +0.0127 vs ~0.01, rebate formula, price ranges all
consistent). The problem is the offline FILL MODEL, not the data:

| metric (cap50/skew0.25) | OFFLINE replay (288 win) | LIVE paper queue model (32 win) |
|---|---|---|
| GROSS, zero-rebate | +$29.79/win, t=+7.87, 87% pos | -$0.18/win, ~0 (38% pos) |
| rebate share of net | 54% | 104% |
| net/win | +$64.15 | +$4.60 |

- Offline `replay`/`vig_hedged` take the opposite of EVERY taker at the trade price (assume
  always-at-touch, always-win-the-fill) -> books ~$30/win of "structural vig" that a realistic
  QUEUE model shows is competed away (~0). The live paper only fills on trade-through after the
  size ahead is consumed -> gross ~= 0, edge is ~100% the MAKER REBATE.
- => The earlier "gross-positive, rebate-INDEPENDENT edge" (round-4 frontier) was a FILL-MODEL
  ARTIFACT. Honest picture: short-horizon we capture the half-spread (live markout +5s our-SELL
  +0.0012) but holding to binary resolution erodes it to ~0 gross; the rebate is the actual edge.
  Offline overstated $/win ~14x AND mis-attributed the source (vig -> really rebate).
- Live markout: our-SELL (93% of fills) +0.0012/+0.0015 (+5s/+30s, favorable); our-BUY (7%)
  -0.0017/-0.0037 (adverse -- the rare buys are toxic). Aggregate +0.0011 (sells dominate).
- Resolution sample 59% up (19/32) and net|UP +7.17 vs net|DOWN +0.84 -> watch for a small
  directional/sample inflation of the +$4.60/win (normalizes with more windows; n=32).

**Implications (rebate-farming, not vig-capture):** (1) the entire economic case rests on the
maker rebate -> maximize rebate-qualifying VOLUME and quote MID (rebate ~ p(1-p), peaks at 0.5);
(2) never cross / minimize churn (every cancel forfeits queue = forfeits a rebate-earning fill);
(3) queue position decides gross (whoever is front captures the spread; we get the rebate on our
fills regardless) -> the pilot must measure queue-weighted fill rate; (4) offline $/win and the
gross-vs-rebate split are NOT trustworthy in absolute terms -- use offline only for RELATIVE
config comparison; the live queue numbers are the honest ones.

## Tweak backtest (tweak_backtest.py) — only significant changes, on 288 historical windows
Discipline check (after the n=32 deep-dive suggested "quote mid" / "tighten buy-side"):
backtest each candidate tweak on the FULL 288-window tape with PAIRED per-window deltas
(cancels shared window variance), require |t|>2.6 AND OOS-consistent to adopt.

| tweak | dNet/win | paired t | verdict |
|---|---|---|---|
| cap100 (raise cap) | +18.76 | +9.03 | only net-raiser (>half is rebate=transfers) |
| skew0.15 / skew0.40 | -0.42 / -0.54 | -0.72 / -1.11 | n.s. -- "tighter skew helps" was NOISE |
| cap25 | -16.98 | -10.2 | worse |
| mid_weighted sizing | -14.26 | -8.04 | **significantly WORSE** |
| buy_half / buy_off | -3.48 / -13.06 | -7.1 / -13.4 | **significantly WORSE** |
| skip_extremes | -13.43 | -5.78 | worse |

**Both n=32 deep-dive ideas FAIL: "quote mid for rebate" and "tighten the toxic buy-side" are
significantly WORSE.** Reason = throughline restated: edge is rebate, rebate ∝ VOLUME, so any
selection that cuts volume (mid-weighting shrinks every clip; dropping buys; skipping extremes;
tighter skew) loses more rebate than the per-share quality it buys. Selection loses; volume wins.
- The ONLY significant net-raiser is **raising the cap** (more qualifying volume -> more rebate),
  but that's the known CAPACITY DIAL (cap_tail: higher cap = more $, lower risk-adjusted Sharpe),
  a risk-budget choice, not new alpha. Scale cautiously, confirm live.
- **No new tweak clears the bar; strategy stays cap50/skew0.25; cap is the only validated knob.**
  The n=32 eyeball would have shipped two significantly-worse changes -- paired n=288 caught them.
