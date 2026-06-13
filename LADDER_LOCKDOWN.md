# Strand-handling escalation ladder — LOCKDOWN program (2026-06-13)

GOAL: lock down the OPTIMAL SEQUENCE of strand-handling rungs, grounded in data; then find the best
strategy for each rung. Method below. Judge vs live_current; forward bar t>3/n>=300; backtests SCREEN.

>>> SEQUENCE IS NOW LOCKED — see "LOCKED SEQUENCE (data-grounded)" at the bottom. Phase C optimizes it. <<<

## Current ladder + best-per-rung (the BASELINE that was backtested)
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

## NON-PERP HEDGE RESULT (commit 1044a3c; NONPERP_HEDGE.md) -> HEDGE rung resolved
OPTIMAL non-perp hedge = ETH 15-min CROSS-ASSET BINARY. R^2=18.6% vs strand loss (11x the perp's
1.7%); std-reduction 9.8% (2x perp); IS/OOS stable. DEPLOYABLE NOW at $5 (same Kalshi API, ETH 15-min
ticker -- no perp min). Rule: BTC YES-strand -> buy ETH-NO; NO-strand -> buy ETH-YES (1-2 ct, maker
if possible, hold to settle; needs concurrent active ETH window = 62% of BTC strands; k<=10).
CROSS-TENOR DEAD: daily BTC R^2 0.66% (worse than perp), ladder <0.1% -- a 15-min strand is a single
Bernoulli trial; longer instruments average it out.
SIZING: beats perp on basis+deployability BUT MODEST -- 9.8% var reduction, +0.5c/strand taker /
+3.2c maker, 62% coverage. => HEDGE rung 5a = ETH cross-asset binary (MINOR rung; deployable);
5b = BTC perp (at-scale). Prevent/Complete/Risk-control remain the load-bearing rungs.

## PHASE-A BASELINE + PHASE-B ABLATION (commit 69a24d1; LADDER_BASELINE.md) -> SEQUENCE DATA
Backtest: BTC, 916 windows, 60/40 IS/OOS, full A/B metric block.

**Combined 5-rung baseline (OOS):** net **+3.50c/win** (beats P0 +2.77c and live_current +2.66c;
t=+2.54). Sharpe +0.133, Sortino +0.128, Skew -0.07 (vs P0 -2.95!), Kurt 2.02 (vs P0 28.1 -- tail
strands largely absorbed by R3+R5), Recovery 3.33, CVaR95 60.3c, PF 1.45, lift vs P0 +0.73c/win.
The +0.73c gain is carried almost entirely by R5 (hedge) and R3 (sell-cheap). DEEP-DIVE caveat: R4
(streak) inflates path-dependence badly -- MaxDD 385.5c vs P0's 46.3c, Ulcer 158.5c, TimeUW 81.5%.

**Leave-one-out ablation (OOS; Δ = ablated − combined):**
| Rung dropped | Δnet | ΔSharpe | ΔCVaR95 | Δstrand | Verdict |
|---|---|---|---|---|---|
| R1 PREVENT (t36) | +0.17c | +0.135 | **-24.3c** | +25.3pp | KEEP (risk-control: small net cost, huge CVaR/strand saving) |
| R2 PREDICT (GBM) | +0.08c | +0.003 | ~0 | +0.3pp | DORMANT but architecturally right (OOS AUC 0.883; too few positives @0.65% fill-strand). KEEP arch, RETUNE |
| R3 COMPLETE (sell-cheap) | **-0.55c** | -0.028 | +4.6c | 0 | KEEP (genuine PnL + tail saver) |
| R4 COOL-OFF (streak) | **+0.61c** | -0.006 | +4.8c | 0 | **NET-NEGATIVE -- dropping IMPROVES to +4.11c. REDESIGN** |
| R5 HEDGE (h=150) | **-0.98c** | -0.042 | +4.2c | 0 | KEEP (strongest single lever; arm at scale) |

**Candidate new rungs:**
- R0 BUFFER spread>=0.01: **ADD** -- +0.00c net cost, strand 37.9%->17.7% (HALVED for free; 1c-spread
  fills are break-even so filtering removes strand risk at no PnL cost). (spread>=0.02 over-blocks: -3.13c.)
- MANAGE-SPLIT (GBM continuous sizing max(0.25,1-p*5), replacing the streak guard): **ADD / REPLACE R4**
  -- +0.57c over combined (+1.18c over keeping the streak); proportional size-down on strand-likely
  fills without punishing recovery. Replaces both R2-skip and R4-streak with one sizing rule.
- CROSS-STRIKE hedge: INFEASIBLE in tape (no multi-strike data) -- Phase C / data-collection item.

## >>> LOCKED SEQUENCE (data-grounded) <<<
Synthesizing ablation (69a24d1) + literature (3dd4293) + Phase-B2 (ed5f2c2) + non-perp hedge (1044a3c):

| # | Rung | Strategy | Lifecycle | Status / decision |
|---|---|---|---|---|
| **0** | **STRUCTURAL BUFFER** | open only when spread >= 0.01 (both sides) | pre-open | **ADD** — strand -20pp at ~0 net cost |
| **1** | **PREVENT** | t36 YES-spread<2c gate + adverse-|sig| gate | open-select | KEEP (risk-control: CVaR -24c). Phase-C tune threshold / NO-side |
| **2** | **PREDICT** | GBM strand gate (AUC 0.883) feeding rung 4's sizing | open-select | KEEP ARCH, RETUNE (dormant as a hard skip; use as continuous signal) |
| **3** | **COMPLETE** | sell-cheap<0.30 + chase give<=0.02, T*=immediate | post-fill pair | KEEP (genuine PnL; -0.55c when dropped) |
| **4** | **MANAGE** (was COOL-OFF) | **GBM continuous sizing max(0.25,1-p*5)** replacing streak 0.75/0.5/0.25 | post-strand | **REDESIGN** — streak is net-negative (-0.61c); manage-split +0.57c |
| **5a** | **HEDGE (deployable)** | ETH 15-min cross-asset binary (BTC YES-strand->ETH-NO) | residual | MINOR rung; deployable now, modest (9.8% var, 62% cover) |
| **5b** | **HEDGE (at-scale)** | BTC-perp h=150 | residual | STRONGEST lever (-0.98c) but $6-min scale-gated; arm at scale |

**What changed vs the entering ladder:**
- **+ Rung 0 (BUFFER)** added on top — free strand-halving.
- **Rungs 1+2 fold** at the same lifecycle point: PREDICT stops being a hard skip and instead FEEDS
  the rung-4 sizing (its AUC is real; its positive count is too thin to gate alone).
- **Rung 4 REDESIGNED**: the streak scale-down (deployed today) is net-negative in backtest; replace
  with GBM-probability continuous sizing. *Forward-validate before swapping the live config.*
- **ATOMIC-ENTRY dropped** (refuted: no native combo on Kalshi; legging beats taking by ~1c).
- **Rung 5 split**: 5a = ETH cross-asset binary (deployable, minor); 5b = BTC perp (at-scale, biggest).
- Lifecycle order 0->1/2->3->4->5 is confirmed correct; R3 fires before R5 on the same stranded leg.

**Deployable-now ladder (current ~$5 size):** 0 BUFFER -> 1 PREVENT -> (2 PREDICT signal) -> 3 COMPLETE
-> 4 MANAGE(GBM sizing). [5a ETH hedge optional/minor; 5b perp dormant until scale.]
**At-scale ladder:** add 5b BTC-perp h=150 as the load-bearing residual hedge.

## OPEN DECISION (operator): the live streak-guard
The streak scale-down `--strand-scaledown "0.75,0.5,0.25"` deployed to live.yml today is now shown
net-NEGATIVE in the OOS ablation (-0.61c/win) and inflates MaxDD. It is a *backtest screen*, not a
forward result -- and we've been burned by backtests before (t02 collapse). Recommendation: leave it
live for now (it is a conservative risk-reducer, not a PnL grab), make the MANAGE redesign (GBM
continuous sizing) the TOP deployable Phase-C priority, and swap only after forward validation.

## PHASE C — per-rung deep optimization (priority by marginal contribution / deployability)
Deployable-now first (hedge 5b is at-scale, so it is shadow-only here):
1. **R4 MANAGE redesign** (deployable, biggest deployable win): implement GBM continuous sizing in the
   trader; test Kelly-fraction, VPIN-conditional, autocorr-weighted variants vs the live streak-guard.
2. **R3 COMPLETE** (deployable, -0.55c lever): price-threshold sweep (0.20-0.40), give sweep
   (0.00/0.01/0.02/0.03), tox-conditioned sell, force-complete-age param.
3. **R1 PREVENT** (deployable, CVaR -24c): tune the 2c threshold, extend to NO-side, vs VPIN gate, combo.
4. **R0 BUFFER** (deployable): calibrate the 1c threshold, side-specific, dynamic-by-regime.
5. **R2 PREDICT** (deployable signal): retune threshold / window-level GBM / rolling refit; wire as the
   rung-4 sizing input rather than a hard gate.
6. **R5b HEDGE** (SHADOW / at-scale): h sweep with integer-contract lumpiness, conditional-on-price,
   prophylactic vs reactive, side-specific delta. Also: collect k-1/k/k+1 strike books to unlock the
   cross-strike hedge (modeled ~88% corr) that beats both ETH and perp if it materializes.

## >>> PHASE C RESULTS — per-rung optimization (4 parallel agents) <<<
Commits: R3 ffe7ab4 (COMPLETE_RUNG.md), R4 e5f7268 (MANAGE_RUNG.md), R0/R1 c5bf1aa (PREVENT_RUNG.md),
R5 735daea (HEDGE_RUNG.md). All full-A/B-metric, IS(549)/OOS(367), backtest SCREEN only.

- **R3 COMPLETE — NO CHANGE (already optimal).** sell-cheap<0.30 / give=0.02 / T*=immediate sit inside
  a flat optimal plateau. Threshold 0.30 is the exact optimum (0.20-0.25 and 0.35-0.40 both degrade;
  sell-all worst -0.74c). Give 0/1/2c dead-flat. T*=immediate confirmed (age requirement hurts
  monotonically). Tox-conditioning HURT (-0.31c). Nothing clears a clean OOS t-bar.
- **R4 MANAGE — DROP THE RUNG (no sizer beats removing it).** Dropping rung 4 tops the OOS net ranking
  (+4.11c/win); the best of 6 sizer families (Kelly λ=1.0) only ties at t=+0.03 (noise). MECHANISM: a
  paired box is locked/risk-free; the only loss is the ~0.65% that strand -> any size cut shaves the
  locked edge on 99% of boxes to soften a tiny tail, so net can't improve. The live streak-guard is
  reconfirmed net-negative (-0.61c). ONLY risk-budget play: Kelly λ=0.25 = ~40% MaxDD cut (457->279c,
  CVaR 65->46c) for ~0.7c/win -- strictly better risk-adjusted than the streak-guard if drawdown is
  ever prioritized over net, but still loses on net.
- **R0/R1 PREVENT+BUFFER — ADD a 1c buffer; t36 & buffer are SUBSTITUTES on YES.** Buffer spread>=0.01
  cuts OOS strand 12.5%->4.9% at only -0.13c net, halves CVaR (57->36c), MaxDD 539->183c -- best single
  gate. Best config = DYNAMIC-VOL buffer (1c floor; 2c when window |sig|>=p75~9bps): strand 4.4%, CVaR
  34.7c, MaxDD 107c. t36(2c-YES) DOMINATES the 1c buffer on YES, so stacking both is redundant (joint
  CVaR worse). Do NOT extend t36 to NO at 2c (over-blocks, -2.84c); a 1c NO floor is the only viable
  NO-side touch. Alt gates (queue/balanced-flow) only "win" by refusing to trade (degenerate).
- **R5 HEDGE — DEMOTED: the ablation OVERSTATED it; real hedging is weak tail-insurance, not edge.**
  HONEST CORRECTION: the ablation's -0.98c/+4.2c-CVaR hedge lever came from h=150 = a ~$150 OVER-hedge
  (a directional BTC bet that caught in-sample drift), NOT a hedge. A clean delta-neutral INTEGER perp
  barely reduces strand variance even at scale (~0.3-0.7% std-red), consistent with perp's 1.7% R^2
  basis -- a 15-min strand is near-pure Bernoulli noise. Perp becomes a CLEAN (not strong) hedge only
  at box_ct>=4 (~$20/win), where round($1*box_ct/$6)>=1 lands in a 0.6-1.6x band. ETH 5a did NOT
  reproduce its ~10% std-reduction on this 136-strand pool (added variance; coverage ~59%) -> forward-
  test candidate, NOT a confirmed reducer. Cross-strike (~88% modeled corr) stays the best-basis option
  but is data-blocked (k-1/k/k+1 daily-ladder book collection spec written in HEDGE_RUNG.md).

## >>> FINAL LADDER (Phase-C-revised, honest) <<<
| # | Rung | Verdict | Deployable now? |
|---|---|---|---|
| **0** | BUFFER (dynamic-vol: 1c floor, 2c high-vol) | **ADD** — best single risk gate, ~free | YES (forward-validate) |
| **1** | PREVENT (t36 2c-YES) | KEEP; substitute-not-complement with buffer; don't extend NO@2c | DEPLOYED |
| **2** | PREDICT (GBM AUC 0.883) | KEEP as telemetry/signal only — too thin to gate; sizing on it doesn't pay | shadow |
| **3** | COMPLETE (sell-cheap<0.30, give 0.02, T*=now) | KEEP UNCHANGED — at optimum | DEPLOYED |
| **4** | MANAGE / COOL-OFF | **REMOVE the streak-guard** (net-negative; no sizer beats dropping). Optional Kelly-λ0.25 ONLY if drawdown is prioritized over net | live config change |
| **5** | HEDGE | Weak/tail-only. Perp clean only at >=$20/win; ETH unconfirmed; cross-strike data-blocked. NOT a live priority | at-scale + data-collect |

**LOAD-BEARING rungs (where the money actually is): R0 BUFFER + R1 PREVENT + R3 COMPLETE.** R2 is a
signal, R4 should be removed, R5 is weak insurance for later. The strand fix is PREVENTION + prompt
COMPLETION, not management or hedging -- the data is now unambiguous on this.

**Deployable changes pending operator + forward-validation:**
1. REMOVE `--strand-scaledown` (revert rung 4 to none) — reverts a backtest-based addition; two
   independent analyses + a clean mechanism agree it's net-negative.
2. ADD an `--open-spread-floor` buffer (static 1c, or dynamic 1c/2c@vol) — new strand-halving gate;
   may let t36 be subsumed on the YES side.
Both should go through the live A/B forward bar (n>=300, t>3) before changing live.yml — except the
streak removal, which only reverts my own recent backtest-driven change to the prior known-good config.

## DATA-COLLECTION backlog (unlocks the best-basis hedge)
Add k-1/k/k+1 (adjacent-strike) book capture to kalshi_ladder_collect.py per HEDGE_RUNG.md's spec, to
make the ~88%-corr cross-strike hedge testable. Until then HEDGE stays demoted.
