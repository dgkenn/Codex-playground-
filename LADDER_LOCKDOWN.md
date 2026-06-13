# Strand-handling escalation ladder — LOCKDOWN program (2026-06-13)

GOAL: lock down the OPTIMAL SEQUENCE of strand-handling rungs, grounded in data; then find the best
strategy for each rung. Method below. Judge vs live_current; forward bar t>3/n>=300; backtests SCREEN.

## Current ladder + best-per-rung (the BASELINE to backtest)
| Rung | Purpose | Best CURRENT strategy | Status |
|---|---|---|---|
| 1. PREVENT | don't open the strand-prone leg | **t36** guarded-opener (suppress thin-spread YES opens) | DEPLOYED |
| 2. PREDICT/GATE | skip opens a model flags strand-prone | **GBM strand gate** (feats: spread,\|p-.5\|,sig,\|flow\|,k,tau,vpin; AUC 0.72) | forward-validating |
| 3. COMPLETE | pair the stranded leg fast | **completion-chase** `--chase-max-give 0.02` (+ sell-cheap<0.30) | DEPLOYED (give=0/0.02 optimal) |
| 4. COOL-OFF | reduce participation when strands streak | **streak scale-down** `0.75,0.5,0.25` | DEPLOYED today |
| 5. HEDGE | offset residual directional exposure | **BTC-perp h=150** over-hedge | deferred (no venue; pays at scale) |

## EXHAUSTIVE strategy brainstorm (every way to prevent or mitigate a strand)
Organized by where in the leg's lifecycle it acts. (* = not yet a ladder rung -> candidate new step.)

**0. STRUCTURAL — change box construction so legging is rarer** *
- simultaneous two-sided marketable/IOC entry (cross both legs at once -> no legging window)
- min-spread/lock BUFFER on opens (only open when lock margin > X -> a stranded leg costs less)
- asymmetric quote SIZE skew toward the side likely to fill second
- strict pairing / max-net=1 (DEPLOYED)
- quote BOTH legs improved (front-of-queue both sides -> symmetric fast fill)

**1. PREVENT (entry selection — don't open the toxic leg)**
- spread-floor gate (t36); side-asymmetric (YES-in-downreg / NO-in-upreg, symmetric guard)
- spot-momentum |sig| gate; microprice-divergence gate; VPIN/toxicity gate
- queue-thinness entry (completing side thin); balanced-flow gate; OI-churn gate
- favorite-only (cost>=0.5); tilt-band; k-slot/time-of-window; vol-regime; time-of-day/session
- one-sided "no-open" (only ever complete, never open)

**2. PREDICT (model-gated)** *as its own rung?*
- logistic / GBM / RandomForest / online-rolling classifier on decision features
- settlement-MAGNITUDE regressor (gate on E[settle]<0); P(strand)-weighted continuous SIZING

**3. COMPLETE (pair the leg)**
- passive re-quote; improve-tick queue-front on the COMPLETING side (BOX_PLAYBOOK #6)
- escalating improve as unpaired-age grows; taker-cross at lock floor (give sweep); deadline force-complete
- partial/smaller completing size

**4. MANAGE / MITIGATE (limit damage without pairing or hedging)** *split from cool-off?*
- sell/flatten the strand at touch (sell-cheap by price band; sell-all); HOLD-to-settle (do nothing)
- cool-off / scale-down after strands (streak guard, DEPLOYED); size-down on strand-prone setups
- position-limit tightening in adverse regimes

**5. HEDGE (offset directional exposure externally)**
- BTC-perp delta-hedge (h ratio; conditional-on-toxic; side-specific; prophylactic vs reactive timing)
- BTC spot hedge; cross-STRIKE Kalshi hedge (offset with an adjacent strike box); cross-tenor; options

## Program plan
- **Phase A (BASELINE):** stack the 5 best-per-rung strategies into one combined policy; backtest on ALL
  data across the FULL A/B metric set (net/win, Sharpe, Sortino, skew, kurtosis, recovery, Ulcer,
  VaR/CVaR95, IR-vs-live, expectancy, time-underwater, adverse-sel, strand-rate, P(both)). Deep dive.
- **Phase B (LOCK SEQUENCE):** from the exhaustive list, test whether the ladder needs MORE rungs
  (Structural-0? split Manage from Cool-off? cross-strike hedge?), FEWER, DIFFERENT, or REORDERED
  rungs -- via ablation (drop each rung; reorder where order matters; add candidate rungs) on data.
  Lock the sequence by marginal contribution + interaction.
- **Phase C (OPTIMIZE EACH RUNG):** parallel deep-dives, one per locked rung, for the best strategy.
Novel ideas + prior research + literature welcome throughout. Parallelize + delegate.

## CONSTRAINT (operator, 2026-06-13): HEDGE rung is SCALE-GATED
The BTC-perp minimum contract is ~$6 notional. Our current box size is ~$5/window (1 contract,
legs ~$0.40-0.60). So you CANNOT hedge a small stranded leg cleanly: a $6 perp min on a ~$0.50
strand = ~12x OVER-hedge = a directional BTC BET, not a hedge. Implications:
- Rung 5 (HEDGE) is NOT deployable at current size; the h=150 backtest benefit is OPTIMISTIC (it
  models a proportional hedge that the min-contract granularity forbids at unit size).
- The CURRENT deployable ladder is RUNGS 1-4 only. Rung 5 activates only once strand notional is
  comparable to / exceeds the ~$6 perp min -- i.e. after meaningful SCALE-UP (SCALE_GATE Stage A+).
- Phase C must NOT spend effort optimizing a live hedge now; treat hedge as an AT-SCALE rung and
  model it with the min-contract lumpiness (integer perp contracts), not a smooth h.
- This makes COMPLETE (rung 3) + MANAGE/COOL-OFF (rung 4) the binding residual-strand handlers at
  current size -- prioritize their optimization.

## LITERATURE REVISION (commit 3dd4293; LADDER_LITERATURE.md) -> candidate revised sequence
Theory confirms prevent->complete->risk-control->hedge (cost up / root-cause-efficacy down the ladder;
regime shifts thresholds not order). Mandated revisions to TEST on data:
  0. ATOMIC-ENTRY (new, top): simultaneous IOC both legs + unwind -> eliminate the legging window
     (dominates AUC-0.72 prediction which leaks 28%). [Almgren-Chriss]
  1. PREVENT (merge PREDICT in -- same lifecycle point; gates + GBM model together).
  2. SKEW (new): inventory!=0 -> skew new opens toward natural-hedge side / accept worse lock to
     attract offsetting flow. [Avellaneda-Stoikov, Ho-Stoll]
  3. COMPLETE with calibrated T* force-complete-age. [Almgren-Chriss urgency]
  4. RISK-CONTROL (merge cool-off + continuous RESIZE: size ~ 1/q^2; one big strand -> immediate cut).
     [Gueant-Lehalle-Tapia]; + WIDEN (proportional lock-margin under sub-gate toxicity). [VPIN]
  5a. CROSS-STRIKE HEDGE (NEW, DEPLOY-NOW): hedge the strand with the adjacent-strike binary
     (sell YES@k+1 / buy NO@k) -- near-zero basis vs BTC perp's 1.7%; no perp min, current size OK.
     [Stoikov-Saglam incomplete-market]
  5b. BTC PERP -- deferred to scale (per the $6-min constraint).
Novel: directional completion urgency; settlement-hazard triage by tau; session circuit breaker;
Bayesian autocorr-weighted size; pre-warmed resting completer.
Ranked tests to run: 1 atomic-entry, 2 cross-strike-hedge, 3 skew, 4 continuous-resize, 5 bayesian-size,
6 T*-force-complete, 7 widen(VPIN), 8 session-circuit-breaker.

## HEDGE-RUNG PIVOT (operator, 2026-06-13): find the optimal NON-PERP hedge
Perp is DEMOTED to "a noted possibility" (scale-gated, $6 min). Rung 5 should be a NON-PERP hedge
deployable at current ~$5 size. STRUCTURAL REALITY: KXBTC15M is a SINGLE-STRIKE up/down binary, so
there is NO same-event adjacent strike -> the literature's cross-strike vertical spread doesn't apply
directly. The non-perp hedge must use a CORRELATED Kalshi instrument; candidates (rank by basis):
  - CROSS-ASSET 15-min: hedge a BTC strand with an ETH/SOL 15-min position (have BTC+ETH data).
  - CROSS-TENOR BTC: hourly/daily BTC up-down or the daily KXBTC multi-strike LADDER (has strikes) at
    a comparable level -- basis = different settlement window/reference.
  - DAILY-LADDER vertical spread: a true vertical on the daily ladder to offset the directional delta.
  - Other intra-Kalshi offsets.
TASK: find the optimal non-perp hedge (lowest basis vs the 15-min strand's directional P&L, cost,
min-size feasibility at ~$5) and TEST its loss-reduction -- OR conclude honestly that no non-perp
hedge has acceptable basis for a 15-min strand (reinforcing prevent/complete/cool-off as the real fix).
Perp stays the AT-SCALE option (5b).

## PHASE-B2 RESULTS (commit ed5f2c2; LADDER_NEWRUNGS.md)
- ATOMIC-ENTRY: REFUTED on Kalshi (no native combo -> take = pay spread -0.97c/box; maker-legging
  beats by ~1c; breakeven P(box)=86% vs actual 93%). DROP from ladder.
- CROSS-STRIKE/LADDER HEDGE: earns a place (5a) -- ~88% modeled settlement corr (vs perp 13%) ->
  ~88% loss reduction, BUT data-blocked (need adjacent-strike/ladder prices; ladder files are
  arb-flags only). ACTION: add k-1/k/k+1 strike book collection to kalshi_ladder_collect.py. The
  non-perp-hedge agent is testing the rigorous cross-asset/cross-tenor version.
- CONTINUOUS RESIZE (lambda=3): EARNS A PLACE -- UPGRADES the deployed streak-guard (maxDD 242->186c,
  CVaR 31->27c; Sortino +0.004 marginal; -0.37c/win cost). Merge into RISK-CONTROL; responds to one
  big strand immediately. (Phase-C: validate forward before swapping the live streak-guard.)
- T*-FORCE-COMPLETE = IMMEDIATE (chase beats hold from the strand minute; +4.63c/strand, +2.55c/win).
  Confirms deployed prompt-completion optimal; adds the formal --force-complete-age param.
SEQUENCE so far: DROP atomic-entry; COMPLETE(T*=now) and RISK-CONTROL(continuous-resize) confirmed;
HEDGE(5a non-perp) pending the non-perp agent + data. Awaiting a731473a (current-ladder ablation).
