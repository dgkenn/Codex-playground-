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
| C2 | completion-quote management: hold price vs reprice tighter (pay up, smaller box) vs widen (bigger box) vs instant self-cross | ❓ **TOP PRIORITY** | the continuous generalization of the disposal rule. Hazard model (AUC 0.909) already estimates P(fill at price p); extend to P(fill ≤ t \| quote at p) per p → maximize E[box value]. "When to buy to complete, big or small box" |
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
