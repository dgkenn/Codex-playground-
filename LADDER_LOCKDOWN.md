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
