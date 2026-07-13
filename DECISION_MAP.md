# Bot decision map — every choice, its model, and its status (2026-07-13)

Architecture: the bot is a chain of decision nodes; each gets a predictive model or
policy, researched independently, EV-tested with day-clustered stats. Status legend:
✅ solved (numbers below) · 🟡 partial · ❓ unresearched.

## A. PRE-ENTRY (before quoting a window)

| node | decision | status | evidence / next |
|---|---|---|---|
| A1 | which asset | ✅ | BTC only pairs profitably; ETH/SOL/XRP box edge negative even gated (PAIR_GATE). SOL/XRP strand 13–15%: downsize not drop if ever run |
| A2 | trade this window at all (regime gate) | ✅ | depth≥med + k≤10 + \|sig\|<10 → strand 14.8→1.9%, +0.46c/box |
| A2b | thick-book veto | 🟡 NEW EDGE | top-quintile depth strands MORE (informed size), t=10.1; live gate keeps these. Add depth≤q80 upper bound — unexploited |
| A3 | box width / which strikes | 🟡 | boxwidth study exists (scratchpad); revisit only if A-nodes above deployed |
| A4 | quote price levels & queue position | ❓ | join-vs-improve, level laddering. Data: full book streams. Medium value |
| A5 | size | ✅ | Kelly ladder clamp(floor(0.02·B),1,30) built (--post auto, tested, undeployed); mo_mult per-window sizing live |
| A6 | timing within window (k-slot) | ✅ | k≤10 kills the catastrophic tail (every settle <−50c was k=11–12) |

## B. IN-FLIGHT, NO FILL YET (resting quotes)

| node | decision | status | notes |
|---|---|---|---|
| B1 | pull/reprice quotes on regime change | ❌ CLOSED (L1.5 study) | 18 signal×cooldown arms, 0 clear the bar (best t=1.17). Mechanism: median signal-to-fill lead = 1.2s (ONE tick) — there is no 'before' to act in; 90-95% of avoided fills would have paired; replacements statistically identical. Completes the trio with C1 and the sweep study: toxic fills are indistinguishable at, by-type, and BEFORE the fill. All information lives post-fill (Layer 2's domain) |
| B2 | stale-feed guard | ✅ | live (ws_stale suppresses quoting) |

## C. FIRST FILL LANDS (the box is legged)

| node | decision | status | notes |
|---|---|---|---|
| C1 | predict pairing at fill | ✅ DEAD END | hard ceiling AUC ~0.58 across 300+ features, all labels. Don't revisit |
| C2 | completion-quote management: hold vs reprice tighter vs widen vs self-cross | ❌ RESOLVED: binary wins | tested static ladders (16 configs) AND dynamic one-step-lookahead pricing: BOTH significantly worse than the binary stopping rule (dynamic vs binary t=−2.66; gate-passed +0.35c t=0.99 vs binary's +1.11c t=2.64). Paying up sacrifices locked spread for hazard the wait branch gets free. Don't build the advanced model — D1's binary stop is the optimum in this action space |
| C3 | live pairing likelihood (holding the leg) | ✅ | 5s hazard AUC 0.909, calibrated. THE core in-flight model |

## D. LEG LOOKS UNLIKELY TO PAIR (hazard collapsed)

| node | decision | status | notes |
|---|---|---|---|
| D1 | when to give up waiting | ✅ | state-dependent stopping: +1.11c/box on traded windows, t=2.64 (vs any fixed deadline incl. live 120s). Deployable |
| D2 | give-up action: cross the spread (sell/complete at loss) | ✅ | early-cross with give-cap 15c beats late-force-hold +1.69c/strand |
| D3 | give-up action: HOLD to settlement when theo favors | ❌ DEAD — no basis (L4 study) | at the strand decision point, theo averages 0.255 AGAINST the held side (adverse selection: strands are ~3:1 against you by construction). There is never a winner to ride |
| D4 | hedge stranded leg with perp delta | ❌ DEAD (2026-07-13 study, 214 real strands) | worse on mean AND variance AND CVaR: portfolio variance UP >20x, mean −4.5c→−15.5c. Near-expiry binary gamma defeats linear hedging: median 97 rehedges costing $1.03/event (>max payout), hedge/settlement corr only −0.31. Hedge-and-wait recovers 0/214 (completing quote NEVER refills after the decision point — the 'option' is worthless). Layer 4 collapses to cheap disposal (L3) + possibly D3 ride-the-winner |
| D5 | cross-venue completion: buy opposite side on Polymarket if Kalshi won't fill | ❌ DEAD (contract mismatch) | PM's product is a 5-MINUTE up/down from period open — different strike reference, expiry grid, and settlement vs Kalshi's fixed-strike 15m. No fungible completion possible; at best a partial hedge with ugly basis. PM stream stays useful only as a leading price signal (H4, +0.045 AUC) |
| D6 | partial disposal / scale-out | ❓ | only relevant at size ≥3; defer until sizing up |

## E. PORTFOLIO / META

| node | decision | status | notes |
|---|---|---|---|
| E1 | concurrent-window & net-delta caps | ✅ | --max-net, notional caps, loss-limit + sticky kill live |
| E2 | hour-of-day / day-of-week allocation | 🟡 | eventday study exists; fold into A2 regime gate later |
| E3 | cross-asset correlation (simultaneous same-direction legs) | ❓ | BTC+ETH legs = doubled delta; net-delta cap partially covers |
| E4 | model retraining cadence & drift detection | ❓ | hazard trained on 20d; needs weekly refit + PSI-style drift alarm before deployment |
| E5 | capital growth policy | ✅ | Kelly ladder + $55 floor + July-19 eval plan |

## Research queue (EV-ranked, token-conscious)
1. **C2 completion-quote pricing** — biggest open lever; upgrades D1's binary stop
   into a continuous "complete now at p vs wait" policy. Data on disk (events_alarm per-5s state).
2. **D5 cross-venue completion (BTC)** — novel, bounded scope: price the PM offset
   vs Kalshi cross on historical strands. Data on disk (pmkt stream).
3. **D3/D4 strand branch: hold-if-winning + perp hedge sim** — Sharpe play, tail kill.
4. A2b thick-book veto — 1-line gate change, paper-validate alongside D1.
5. E4 retrain/drift harness — prerequisite to shipping any of the above.

Everything below the line already researched: C1 (dead), A1/A2/A6/D1/D2 (numbers above),
per PAIRING_FINDINGS.md and PAIR_GATE.md.

## F. ROUND-2 NODES (brainstorm 2026-07-13, quick data verdicts same day)

| node | decision | verdict | evidence |
|---|---|---|---|
| F1 | expand universe (DOGE/BNB/ZEC/NEAR/HYPE 15m) | ❌ mostly dead | midday vol: HYPE~27k, BNB~19k, DOGE~18k ≈ SOL-tier (16k); BTC=733k mean. SOL-tier assets don't pair profitably (PAIR_GATE). ZEC/NEAR dead (<5k). Only HYPE merits a 1-day tape look if ever expanding |
| F2 | adaptive quoted edge (wider in high vol) | ❓ promising | vol top-quintile costs +0.64c/event (t=7.9); demand more edge instead of skipping. Needs fill-rate elasticity study |
| F3 | competitor-MM fingerprint → edge/stand-down | ❓ | low priority; flicker features were weak at fill |
| F4 | multi-box re-entry same window | ❌ CLOSED (2026-07-13 study): do NOT raise max-fills-side | cap=3 DOMINATES every higher cap on BOTH return and risk (day-clustered \|t\|=8-40, no sign flips, both fill-quality models, both halves). Volume unlock is real (+23-91% boxes) but buys the WORST part of the window: the k>=4 penalty is mostly a TIME effect — extra volume lands late where EV is worst, territory the late-join cap + stopping rule already handle. No efficient frontier exists on this parameter. Engine validated against the 214-strand baseline |
| F4b | TIME-CONDITIONED cap: allow k>=4 only when they land EARLY (fills < min 4) | 🟡 quality-neutral but TINY | operator follow-up to F4 (2026-07-13). Naive replay: incremental EV −0.858c/window t=−5.91 (opt fill model; pess −0.267c t=−4.06) — but the negative-mean replay artifact applies (ALL replay boxes score negative; live runs +0.85c). Artifact-adjusted: early k>=4 boxes (−3.55c, strand 6.5%) are comparable-to-BETTER than the k1-3 replay baseline (−4.32c, strand 7.9%) — the intuition is right, early extras are normal-quality boxes. The killer is POPULATION SIZE: only 0.06–0.27 extra boxes/window (+2–9% volume), so even at full live quality the payoff is ~+0.05–0.23c/window. Disposition per rail 2b: forward-arm candidate at most ("cap 3; allow to 5 iff all fills < min 4"), below backlog top; NOT a live change |
| F4c | double/triple down when the hazard model says a strand will pair | ❌ CLOSED (2026-07-13, operator idea) | Two failure modes. MECHANICAL: box profit is fixed at quote time — a confident pair prediction has nothing left to buy; upsizing the completion quote mints a fresh REVERSE strand from a sweep fill (the exact adverse-selected population the strand studies mapped). ECONOMIC (coherent version = add new boxes when state is pair-friendly): payoff asymmetry +0.85c win vs ~−50c realized strand loss ⇒ break-even P(pair)≈98.3%. Quick honest test (BTC, at-fill logit on h0 state, train≤06-29/test≥06-30, AUC 0.617 — consistent with C1 at-fill ceiling; the 0.909 is the per-5s hazard, not available at entry): top-10% bucket pairs 95.4% (below bar), top-5% 98.2% (n=55, at bar, CI huge), top-2% 100% (n=22). Best-case EV ≈ −0.07c to +0.38c per added box on ~0.05 boxes/window ⇒ ≤+0.02c/window. Same verdict family as F4b: quality ~neutral at best, population tiny. Not worth a forward-arm slot vs C3 |
| P1 | PREY→PREDATOR step 1: sub-second websocket tick collector (Kalshi book/trade events at native resolution) | ❓ QUEUED as priority build (2026-07-13, free action — collector-side only) | The binding constraint is DATA resolution, not order latency: L1.5's "1.2s median lead" = ONE TICK at the collector's own 1.2s sampling — the C1 at-fill AUC ceiling (0.58) and the "no pre-fill signal" verdicts were all measured with data that cannot see sub-second microstructure. The predators' whole edge lives below our sampling floor. A ws recorder (sidecar feed) costs nothing live-side and unlocks: re-test C1 ceiling + L1.5 leads at true resolution; F10 exceedance DURATION measurement; dodge-economics for a future fast loop. p90 lead is already 4.8-6.0s even at coarse sampling — a real tail exists |
| P2 | PREY→PREDATOR step 2: fast reaction loop (ws order path, sub-second cancel/replace) | ❓ BLOCKED on P1 evidence | Do NOT build until P1 data shows (a) sub-second discriminating signal exists (else C1 ceiling binds and speed buys nothing — dodging all sweeps also dodges the 88% that pair) and (b) avoidable-toxicity EV > build+run cost. GHA cron can host a persistent ws process inside a leg; never colocated-fast, but the target tier is the SLOW predators/humans, not the ms-bots |
| P3 | PREY→PREDATOR step 3: VPS migration ladder (free GHA-ws → $5-15/mo us-east-1 VPS → top-tier colo-equivalent) | ❓ REGISTERED (2026-07-13) — gated | Latency chain today: spot feed ~1-3s stale + Kalshi poll ~1.2s + GHA→AWS order path ~50-150ms. Cheap tier (EC2/Lightsail us-east-1, ws feeds, ~30-100ms end-to-end) is the sweet spot: also fixes MEASURED losses independent of sniping — F7 13% coverage gap + the late-join strand class (1.7x, validated). GATES: deploy cheap tier iff F10 measures capturable pool >= ~$2/day at 100ms reaction; requires operator word (keys move off GHA; live-loop migration is a rail-1-adjacent architecture change — middle path: VPS does data+sniping only, GHA keeps box loop). Top tier ($100-500/mo, <15ms, MM API tier): only at escalation step 3+ AND F10 pool >$100/day — venue capacity and bankroll bind before infra does. All $ figures are PRIORS until F10; defensive gains are measured |
| F10 | stale-quote sniping (take obviously mispriced resting orders; exploit other bots' missing backstops) | ❌ CLOSED at >=2.4s persistence (2026-07-13 scan); sub-2.4s remains open pending P1 hires data | Scan ran twice on the 33-day BTC tape (train<=06-29 calibration / test>=06-30 economics, day-clustered). (1) HINDSIGHT detector (profitable vs mid 10s later): pool looks huge (+$112/day/contract, 2494 eps/day, t=19) — but that's momentum PREDICTION, not staleness; unusable at decision time. (2) CAUSAL detector (touch mispriced vs spot-distance theo, vol train-calibrated, margins 1-3c, >=2.4s persistence, take at re-observed tick-2 price): LOSES −$27/day/ct (t=−3.6); with empirically calibrated z→P(settle) map (no model-shape objection): −$38/day/ct (t=−4.2), robust across margins, worse with 1c slippage haircut. THE INSIGHT: book−theo deviation IS information (flow/momentum the book knows, static maps don't) — 'obviously mispriced' resting orders at observable resolution are the book being smarter than the model; the taker eats adverse selection just as our maker quotes do. Reliability table shows realized outcomes MORE extreme than driftless theo (pred .55→realized .65). No forgotten-backstop pool exists above 2.4s persistence. Sub-2.4s flash staleness = P1 question. Passive-only boundary stands (inducing malfunction = manipulation, out of scope) |
| F11 | width-gated pairing (engage only when box locks 2-4c; hold out for bigger boxes) | ❌ CLOSED (2026-07-13) | Achievable width at fill (1−p1−pc0) is nearly DEGENERATE: p10=p90=1c; width≥2c is only 3% of fills (n=81). Those wide boxes ARE relatively better (−1.57c vs −4.2c replay EV, pair 92.5% vs 88%) but subset day-t=−1.12 (NS) and gating on ≥2c discards 97% of volume ⇒ destroys ~97% of live EV. 'Hold out for wider' (quote back 1c) already falsified by L0.5 BACK-1c: deeper fills are MORE toxic — adverse selection eats the extra width. Only live path to more width is F2 (conditional widening in high vol, elasticity study open) |
| F5 | strand-clustering cooldown | ❌ NO basis | P(strand\|prev strand)=0.143 vs base 0.142, t=−0.71. Strands do NOT cluster window-to-window. Keep consec-strand kill only as cheap tail insurance; don't extend it |
| F6 | inventory skew across concurrent legs | ❓ | covered partially by --max-net; model later |
| F7 | coverage gaps (GHA cycle restarts) | 🟡 REAL LOSS | only 87% of windows observed per asset-day (collector proxy). ~13% missed volume ≈ free EV at current edge. Ops fix, not model: tighten cycle overlap/handoff |
| F8 | dispose maker-out vs taker-out | ❓ | fold into C2/D1 prototype (rest an improve-order for 5-10s before crossing) |
| F9 | within-day circuit breaker / loss-limit level | ✅ SUPPORTED | day P&L serially correlated: corr(1st-half, 2nd-half EV)=+0.28; after bottom-quartile first half, 2nd-half EV −5.33c vs −4.18c. Bad days stay bad → the $6 loss-limit is directionally right; tightening is defensible. Risk reducer |
| F10 | settle-vs-spot basis on held legs | ❓ | only matters if D3 hold-branch ships |

### Round-2 clear winners (no further research needed)
- **F9**: keep/tighten the daily loss-limit — first data-backed validation of it (bad days persist).
- **F5 negative**: don't build strand-cooldown logic beyond what exists — no signal.
- **F7**: operational — recover ~13% missed windows (cycle handoff), pure volume gain.
### Round-2 promising (prospective tests queued)
- F2 adaptive edge (vol-conditional pricing) — after C2 lands, same hazard machinery.
- F8 maker-out disposal — bolt onto the D1/C2 paper prototype.

## G. ROUND-3 NODES (loop round 1/3, 2026-07-13; solutions tested where data allows)

| node | decision + candidate solutions | verdict | evidence |
|---|---|---|---|
| G2 | side selection at quote: (a) both always (status quo), (b) lean drift-aligned, (c) only theo-favored side, (d) asymmetric size | ❌ dead | drift-aligned vs against fills: EV diff −0.03c, t=−0.08. Side doesn't matter at fill; no lean justified |
| G6 | day-after-bad-day sizing: (a) full size, (b) half size, (c) skip day | ❌ no basis | day-EV lag-1 autocorr +0.126 (n=33, NS). Bad days do NOT persist across days (they persist WITHIN days — F9). Keep full size next day |
| G7 | hour-of-day gating: (a) trade all hours, (b) skip worst-k hours, (c) vol-condition instead, (d) hour-specific edge demand | ❌ DEAD (round-2 honest test) | train-selected worst hours evaluated on held-out test days: +0.12c, t=0.24. The round-1 −1.44c was a multiple-testing artifact. Trade all hours |
| G8 | avoid near-par entries (\|p1−0.5\|<0.1): (a) hard skip, (b) wider edge near par, (c) size down | ❌ ABSORBED by gate (round-2) | full-sample t=−3.62 is real but vanishes on gate-passed events (pooled −0.02c t=−0.02; BTC +0.95c NS). The near-par penalty lives in windows the live gate already rejects. No add-on needed |
| G9 | concurrent multi-asset exposure: (a) independent sizing (status quo), (b) same-window combined cap, (c) correlation-scaled sizing | ✅ RISK FINDING | same-window strand correlation across assets is LARGE: btc-eth 0.43, eth-sol 0.40, all pairs 0.28–0.43. Concurrent legs ≈ one correlated bet, not four. Validates net-delta caps; if multi-asset ever resumes, size as ~1.5 independent bets, not 4. Pure Sharpe protection |

## H. ROUND-4 NODES (loop round 2/3, 2026-07-13)

| node | decision + solutions | verdict | evidence |
|---|---|---|---|
| H1 | settlement-basis risk on held legs: how close to strike is "too close to call" at expiry? Solutions: (a) ignore, (b) fixed uncertainty band, (c) modeled CF-vs-spot basis | ✅ QUANTIFIED → (b) | settle vs our spot ~57s pre-close: abs-median ≈ 2bps, p95 ≈ 9–11bps (BTC & ETH, n=355). Any D3 hold-to-settle model must treat legs within ~10bps of strike late-window as coin flips (uncertainty floor). Risk parameter, zero engineering beyond a constant |
| H2 | iceberg/display-size quoting | ❓ no data | Kalshi API has no iceberg; moot |
| H5 | stale-feed threshold (currently ~15s suppress) | ❓ low value | only 4 stale events/day, all ~15.5s; not enough data to tune; leave |
| H6 | strike-band selection when quoting (near-money only vs wider) | 🟡 note | strikes are chained (next strike = last settle, verified in index); current near-money-only is right; revisit only with multi-strike quoting ambitions |

## J. HAZARD DISTILLATION (overnight run 1, 2026-07-13)

Deploy target is numpy-only (collector/live env has no sklearn). Tested distilling the
stopping rule's hazard model:

| variant | AUC | full-sample delta t | gate-passed delta t |
|---|---|---|---|
| HGB 33-feat (re-implementation) | 0.909 | 1.07 | 1.75 |
| **Logistic 33-feat (numpy-deployable)** | 0.903 | 1.12 | **1.88** |
| Logistic 6/4/2-feat | 0.90 | ~0 | ~0.16 (kappa pinned at grid edge — degenerate) |

Verdicts: (1) **logistic-all is the deployable form** — matches the boosted model;
coefficients exported to the shadow-arm implementation. (2) **Feature pruning kills the
EV while barely moving AUC** — the money is in fine calibration, not rank order; do NOT
ship a "simple" hazard. (3) **Robustness warning:** the re-implementation (different
NaN handling + linear cost model) got t=1.07 vs the original t=2.36 full-sample — the
stopping edge is implementation-sensitive. This DOWNGRADES confidence in the +1.11c
point estimate and makes forward paper validation strictly mandatory before any live
deploy; the shadow arm must replicate the original pipeline exactly (HGB-equivalent
NaN handling, fitted cost regressor, kappa=-0.5c).

## DEPLOY QUEUE (validated, ready; 2026-07-13)

Beyond the earlier five (hazard stopping +1.11c t=2.64; thick-book veto t=10.1;
vol/momentum filters; alt downsizing), the next five deploy-ready items:

1. **Kelly --post auto ladder** — code built on bot branch worktree, 11/11 tests,
   pre-registered sizing study. Deploy at the Jul-19 size-2 decision point. (Growth-
   optimal EV; fail-safe post=1/$5.)
2. **Window-cell entry veto** — skip window-open (vol×spread) cells that were worst
   on train: TEST +0.124c/window, t=2.77, skips only 3.2% of windows (pairprob Q2 —
   honest train-select→test-validate). One-line entry filter.
3. **Tighten --dispose-max-give 0.25 → 0.15** — disposal study: give-caps 15–22c have
   identical mean cost, beyond that admits tail; live sits at 25c, outside the flat
   region. Pure tail-risk (Sharpe) cut, zero expected-cost change, one flag.
4. **Cycle-coverage recovery (ops)** — only 87% of windows are covered around GHA
   cycle boundaries; closing the gap is ~+15% volume at the live +0.85c/box edge
   with unchanged per-window risk limits. Workflow scheduling fix, no model.
5. **Wide-spread entry veto (spread >2c)** — train-chosen threshold, TEST +0.35c/event,
   t=2.03. Currently inert on BTC (its spread never exceeds 2c) → a free safety rail
   that activates if BTC's book regime changes or alts return. Honest caveat attached.

Killed by honest validation this round (do NOT deploy): loss-limit tightening
(t=−0.33 held-out), hour gating (t=0.24), near-par filter (absorbed by gate),
completion repricing (worse than binary stop, t=−2.66), PM cross-venue completion
(contract mismatch), strand cooldowns (no clustering), day-after downsizing (NS).

## I. ROUND-5 NODES (loop-2 round 1/3, 2026-07-13)

| node | decision + solutions | verdict | evidence |
|---|---|---|---|
| I1 | minimum-spread-to-quote (skip 1c-spread windows?): (a) no floor, (b) require ≥2c | ❌ dead | thin-spread windows are NOT worse (1c vs rest −0.24c, t=−0.51); cost is monotone in WIDER spreads (already covered by wide-spread veto). No floor |
| I5 | minute-of-hour gating (:00/:15/:30/:45): (a) uniform, (b) skip worst slot | ❌ dead | train-worst slot (:30) came back BETTER on test (+1.05c, t=1.81 wrong-signed). No stable effect |
| I9 | model retrain cadence: (a) daily, (b) weekly, (c) on-drift-only | ✅ STABILITY FINDING → (b/c) | daily edge trend over 33 days: +0.018c/day, corr +0.13 — NO decay, first and last 5-day means identical (−5.16c). The regime is stationary at month scale → weekly refit + drift alarm suffices; no need for aggressive retraining (E4 input) |
| I10 | extreme-moneyness window veto (\|mid−0.5\|>0.35): (a) skip, (b) keep | ❌ dead | +1.62c t=1.62 wrong-signed (extreme windows slightly BETTER, consistent with G8's monotone); only 3% of events. Keep trading them |

## K. REPLACEMENT-ARM CANDIDATES (brainstormed + tested 2026-07-13, post-prune)

| candidate | test result (train-thresh → test, day-clustered) | verdict |
|---|---|---|
| C1 front-load entries (skip minute 7–10) | +0.46c, t=1.11, skips 0.6% | ❌ NS — k≤10 already captures it |
| C2 thick-book veto q80 | +1.25c t=10.1 full / survives gate subset | 🟡 already in deploy queue (forward arm live) |
| **C3 completing-side depth-share veto** | share>0.8: +2.38c t=8.3; **+1.42c t=5.15 BEYOND C2** (P(C3\|C2)=0.72, partially independent) | 🟡 → backlog top; mechanism: book leaning against completion = informed pressure. Forward-test MILD variant (share>0.9) only |
| C4 skip alts on BTC vol top-decile | +0.35c t=6.8, alt-only | 🟡 backlog (inert while BTC-only) |
| C5 skip dead-book opens (low tickrate0) | +0.65c t=1.58 | ❌ NS |

**Accounting artifact caught (important):** on the gate-passed subset the C2\|C3 combined
veto shows t=12.45 — but skips 90.9% of traded windows. In this replay (mean −5c/event,
blind to the live strategy's positive edge) any large skip "wins" mechanically. Entry-veto
replay numbers are only trustworthy at small skip fractions; at scale they must be
validated as box_shadow forward arms with apples-to-apples accounting. This artifact is
exactly why NOTHING goes straight to live regardless of in-sample t-stat.

## N. LEG-BOUNDARY LATE-JOIN STRANDS (diagnosed live 2026-07-13)

Both of today's live strands were windows the restarting leg JOINED mid-flight
(first fills at t=536s / min 9, vs t=60-64s in every clean window). The ~46-min leg
chain makes ~1/3 of windows late-joins — a population the replay corpus structurally
lacks (only 1.1% of replay events have t1>=300s, because shadow quoting always starts
at window open). All available evidence is directionally consistent:
- live today: 2/2 strands were late-joins;
- corpus (thin, n=30 btc): late first-fills strand 30.0% vs 11.5% early (2.6x);
- pooled minute-9 pair rate 56% vs 86% at minute 2 (pairprob).
This also partly explains live strand rates (7-22%) running far above the study's
gated 1.9% — the k<=9/10 cap was validated for start-quoted windows only.

✅ VALIDATED (manufactured-population replay, 2026-07-13): 2,745 BTC windows re-replayed
with delayed quote starts. Strand rate climbs monotonically with join lateness:
11.6% (min2) -> 15.1% (min5, t=3.9) -> 18.0% (min7, t=5.7) -> 19.4% (min9, t=7.6).
Fix pricing decomposed (income foregone vs cost avoided, artifact-aware): pooled
{5,7,9} net +2.93c/window t=17.6 (absolute EV inflated by replay's negative baseline
— the trustworthy signal is the strand-rate climb). Cost of the fix at min-3/5 joins:
<=1.5% volume dropped. Meets charter 2b. 
✅ DEPLOYED 2026-07-13 (main 59b56c58d, explicit operator word "go ahead with all
recommendations"): live.yml `--open-k-max 9` -> `5` (no opening fills past minute 5
anywhere; disposal/completion unaffected; costs a few % of volume). Alternative
trader-side join-window-only rule remains a backlog option if volume cost bites.
Replay could not size the benefit precisely (population absent) — the live A/B from
here IS the measurement: daily cycle tracks strand-rate before/after deploy; expected
direction ~19% fewer strands overall (late-join class removed).

## M. PAIRED-BOX RISK ACCOUNTING (operator insight 2026-07-13)

Paired boxes are settlement-guaranteed ($1/contract in <=15min) yet the notional cap
counts their full cash cost as exposure (kalshi_trader.py:3408: exposure =
open_buy_notional + max(-cash,0) — includes paired principal). Risk-true exposure of
a paired box is only max(cost-1.00, 0) ≈ 0.
- Today: harmless coincidence — at size 2 the notional cap AND --max-fills-side 3
  both bind at 3 pairs/window (the constant n_boxes=6). No volume lost yet.
- At post>=3 (Kelly ladder): notional (2*post+3) binds BEFORE the fills rail →
  throttles risk-free volume. Fix required before auto-sizer deploy.
- ✅ FIXED (operator-approved, d5a6cd3d6 on bot branch, 2026-07-13): module-level
  cash_at_risk(cash,pos) helper — paired_guaranteed = min(ΣYES,ΣNO)·$1;
  cash_at_risk = max(spent − paired_guaranteed, 0). Applied at all 3 C8 sites
  (scoping verified: pos/cash always window-synced). Gates: 7/7 new unit tests,
  38/39 safeguards (pre-existing T21 only), 18/18 guardian, dry-run byte-equivalent.
  NOTE: auto-sizer worktree (--post auto) predates this — rebase it before its deploy.
- The real volume unlock at current size is --max-fills-side (F4 multi-box node) —
  needs its own study; the 3-cap has adverse-selection data behind it (4th-5th
  same-side fill post-mortem). F4 priority raised.

## L. ACTIVE vs INACTIVE HOURS — one strategy or two? (2026-07-13, resolved)

Question: do quiet hours need a different strategy? Verdict: **NO dual strategy — one
state-adaptive strategy trading 24/7.**
- Per-event economics are uniform across regimes: lull (07-08 UTC) EV −4.34c/strand
  13.1% vs rest −4.55c/11.6%; state-quiet (low tick-rate) actually best (−3.05c).
  Quiet = fewer fills, not worse fills. Spread-bucket EV flat across regimes.
- The ONE real difference: pairing is ~70% slower in quiet tape (med time-to-pair 41s
  vs 24s; pairs completing ≤120s: 75% vs 81%) → fixed deadlines clip more good boxes
  when quiet. The state-dependent stopping rule (hazard uses tickrate/vol) adapts to
  this automatically — third independent argument for it over any fixed deadline.
- Clock-based rules are now 0-for-2 under honest validation (G7 skip-hours, and this
  study's regime-conditional spread floor which reproduced the volume-cut artifact,
  +4.4c t=17 REJECTED as mechanical — same failure mode as DECISION_MAP K).
- 24/7 posture data-validated: every UTC hour fills 3-4.2 of 4 windows historically;
  P(zero-fill hour) ≤12% except 07-08 (~21%). Keep quoting all hours; the activity
  guard (built 2026-07-13) alarms if placements stop during non-lull hours.

### Round-2-of-loop meta-lesson
Both round-1 "promising" leads (G7 hours, G8 near-par) died under honest validation
(held-out test / deployable-subset). In-sample screens on 13 test days overfit fast —
every future lever gets the train-select/test-validate treatment before entering the
deploy queue.
