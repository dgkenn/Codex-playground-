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
| B1 | pull/reprice quotes on regime change | ❓ | informed-flow signature → cancel before being run over. Sweep-fill study says sweeps DON'T strand more, so likely low value |
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
| D3 | give-up action: HOLD to settlement when theo favors | 🟡 | stopping rule holds implicitly; explicit "ride the winner" branch (leg deep ITM → holding is +EV) unmodeled |
| D4 | hedge stranded leg with perp delta | ❓ | binary delta-hedge via Binance perp until expiry: EV ≈ −costs but kills the −42c tail → Sharpe ↑. Simulable with tick spot paths |
| D5 | cross-venue completion: buy opposite side on Polymarket if Kalshi won't fill | ❓ NOVEL | synthetic pair across venues when PM opposite < Kalshi cross cost. pmkt_btc_updown stream exists; PM leads Kalshi (+0.045 AUC) so quotes may lag = capturable. Feasibility: contract equivalence, fees, settlement basis |
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
| F4 | multi-box re-entry same window | ❓ | needs per-window multi-fill replay; medium value |
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

### Round-2-of-loop meta-lesson
Both round-1 "promising" leads (G7 hours, G8 near-par) died under honest validation
(held-out test / deployable-subset). In-sample screens on 13 test days overfit fast —
every future lever gets the train-select/test-validate treatment before entering the
deploy queue.
