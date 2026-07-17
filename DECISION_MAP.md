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
| F4-marginal | per-box-index EV re-test (operator challenge 2026-07-13: "sure box 4 is negative? up to 10?") | ❌ box4+ ANYTIME negative (confirmed both models); 🟡 box4+ EARLY = fill-model-dependent maybe | Marginal EV by box index k (cap=10 replay, day-clustered vs k1-3 baseline, artifact-aware): monotone decline, both fill models. OPT: box3 −0.48c t=−2.06, box4 −0.63c t=−2.26, ... box10 −2.01c t=−4.34. PESS harsher: box2 already −0.61c t=−2.43, box4 −2.64c t=−5.68, box10 −6.03c t=−6.02. Strand% climbs 7.7→10.4%. SO: raising the flat cap is negative, not close — CONFIRMS F4. BUT split by fill-time: EARLY (min<=5) box4-7 in the OPT model are EV-NEUTRAL vs early-k1-3 (box4 −3.93 vs −3.84; box6 −3.63 BETTER; pair 75-78%), while PESS still dilutes (box4 −6.41 vs −4.62). Population is real (~0.5 early-box4/window). STREAK CAVEAT (critical): the "20 boxes in a row winning" are boxes 1-3 (we cap at 3) — ZERO live evidence on box4+ exists; box4+ fills BECAUSE the market trends one way (the regime where the OTHER leg strands), a different selection than the balanced windows that pair 1-3. Winning boxes = boxes that PAIRED; adding a box adds a trend-biased coin-flip, not a guaranteed winner. DISPOSITION: early-conditioned multibox is the ONE live-ish 'more boxes' idea not dead — a forward-arm candidate (fill-model-fragile, adjudicate on forward data), NOT a live change |
| F-fillcal | fill-model calibration vs live tape (2026-07-13, delegated; fillcal/RESULTS.md) | ✅ REALITY ≈ OPT — the replay fill rule is settled | 618 live placements (07-12/13) reconstructed from order_lifecycle, cross-validated against the fills ledger (exact count match). Scored vs tape: OPT precision 0.680 / recall 0.481 / F1 0.563; PESS 0.541/0.213/0.306. Calibrated dwell-parameter fits to beta=0.0 on both folds = collapses exactly to OPT. OPT timing error median +0.36s (70% within one tick). OPT's misses are TAPE-RESOLUTION driven (median dwell 0.87s < 1.2s tick gap) — the hires stream will sharpen future calibration. IMPLICATIONS: (1) ETH-BACK2's t=8.96 was scored under the OPT-side rule reality matches → headline survives; forward arm still adjudicates (OPT precision 0.68 = some predicted fills don't happen, and BACK-level fills are unmeasured directly). (2) F4-marginal early-4th-box: OPT-side 'EV-neutral' reading gains weight; still forward-candidate only. (3) All past PESS-pessimistic sensitivity bands can be read as lower bounds. Live ops stat: 58.6% of resting orders fill |
| F1b-repl | REPLICATION GATE on ETH-BACK2 (2026-07-13, independent re-implementation; ethvalidate/replicate.py) | 🟡 DIRECTION CONFIRMED, MAGNITUDE NOT — t=8.96 does not replicate; honest claim is t≈2.3-2.5 | Independent first-box-only, re-pegged-quote, all-window replay, 33 days: ETH BACK2−JOIN = +0.43c/window t=+2.48 (64% days positive); test-only +0.24c t=0.90 (loose fill) / +0.65c t=2.34 (strict fill, cross-by-extra-1c). BTC falsification control: −1.04c/window t=−5.33 (15-25% days positive) — the asymmetry the whole thesis rests on is REAL and strongly two-sided. Magnitude gap vs the study (5x) ≈ multi-box accounting + fill optimism at backed levels (the two places replay flatters reality). Strand economics visible: backed ETH quotes strand 10.1% of fills vs ~0 for re-pegged JOIN — the wider lock pays for it on ETH, not BTC. J-section lesson repeats (t=2.36→1.07 then; t=8.96→~2.5 now): NEVER deploy on a single implementation. STATUS: replay-supported forward candidate; the back2 box_shadow arm adjudicates from 2026-07-14; deploy bar = forward day-clustered t>=2 vs eth-JOIN over >=10 days |
| F1b-study | ETH tailored wide-quote study (2026-07-13, delegated; ethstudy/RESULTS.md) | 🟡 STRONG replay result superseded by F1b-repl (magnitude 5x lower on re-implementation) — see F1b-repl for the honest numbers | Test days only (13d), day-clustered. (A) Paired locked value ≈ spread at fill (definitional under never-cross): 1c→+1.0c, 2c→+2.0c, 3c→+3.1c; pair rate HOLDS at 2c (89.2→88.4%, NS) and breaks at 3c+ (83.9%). Net-of-strand best band = 2c. (B) ETH depth 19x thinner than BTC (median qdepth_c 128 vs 2426) but still 3-20x a 2-6ct clip — not binding. (C) Back-quote replay, EV/window deltas vs ETH-JOIN: BACK1 +0.7c t=2.75; BACK2 +2.1c t=8.96; BACK3 plateau (vs BACK2 t=0.13). Monotone pattern replicates on train days. ETH-JOIN vs BTC-JOIN: +0.2c t=0.60 (lateral); ETH-BACK2 vs BTC-JOIN: +2.3c t=4.49. OPPOSITE of BTC where BACK-1c was toxic (L0.5) — ETH's wider book changes the sign. CAVEAT: BACK fills are the most fill-model-sensitive replay object (deeper fills require bigger sweeps; thin ETH book) — interpretation gated on the fill-calibration study. Pre-registered pilot criteria: >=10 forward days, EV delta vs ETH-JOIN t>=2, pair>=75%, no BTC degradation, kill if strand >24.4% sustained 3d. NEXT: wire eth_back2 as a box_shadow forward arm (paper) |
| F1b | ETH as a second box-making sleeve (operator 2026-07-13: "ETH correlates w/ BTC, tailor a strategy?") | 🟡 PROMISING — ETH is BTC-tier for box-making + has a structural edge BTC lacks | Correlation isn't the reason (box-making ignores price direction); what matters is microstructure, and ETH's is BTC-tier: pair_ever 87.6% (BTC 88.3%), pair120 71.8% (73.3%), strand 12.4% (11.7%), med-time-to-pair 25.2s (21.4s), strand_pnl −0.4c (identical), ITM 0.6%. FAR closer to BTC than SOL(84%/38s)/XRP(82%/44s) — the F1 dead-tier. THE EDGE: ETH trades WIDER — only 70% of fills at 1c spread vs BTC's 96%; 23% at 2c, 6% at 3c — AND pairing HOLDS at 2c (86.1%) and 3c (87.6%), only collapsing at 4c+ (n=22). BTC box width is degenerate at 1c (F11 dead); ETH offers ~30% of fills at 2-3c width with pairing intact = potentially HIGHER edge/box, not just more volume. TAILORED STRATEGY = quote to capture the 2-3c ETH boxes (wider seed-width/skew than BTC). NEXT: forward-validate ETH 'live'-arm box economics (enabling in box-shadow.yml), then a wide-quote paper arm. Caveat: verify ETH tradeable DEPTH/window (event-parity ≠ contract-volume parity) before sizing |
| F4-time | is the box-index penalty really a TIME effect? (operator hypothesis 2026-07-13) | ✅ CONFIRMED (OPT) / partial (PESS) — operator right | Decomposed EV by index-group × minute. OPT model: once you control for minute, the k4+ penalty VANISHES — min3-5 gap −0.20c, min6-9 +1.14c (k4+ BETTER), min10+ +0.58c; only the odd min0-2 cell shows k4+ worse. So a k4+ box that fills at the SAME minute as a k1-3 box is ~as good. PESS model: time explains ~half (gaps shrink to −1.4/−0.9/−0.1c but stay negative). Verdict: the "later boxes are worse" intuition is the dominant mechanism; box COUNT per se is second-order. Reframes volume expansion away from "cap" toward TIMING/SIZING |
| F-size | state-dependent entry sizing by leg-price — "bet bigger where pairing is likely" (operator 2026-07-13) | ❌ CLOSED — the pairing-rate signal is an ILLUSION once strand loss is priced correctly | FIRST-pass table (constant 45c strand cost) looked great: pair rises monotone 79%→95% with leg price, implied-EV rising, rel_size up to 5x. WRONG. Built the honest study on e_locked (realized per-contract P&L: ~+1c paired, strand loss = what you PAID for the leg). Two decisive facts: (1) EDGE-THINNING: paired box locks a FLAT ~1.04c at every price band (not the concern). (2) THE KILLER: strand LOSS scales ~linearly with leg price — 0-15c strands 20.8% but loses only 8c/strand; 65-85c strands just 7.7% but loses 70c/strand. The bigger loss exactly cancels the lower frequency: mean e_locked is FLAT-to-U-shaped across price (0-15c −1.08c BEST, 65-85c −4.44c WORST) — the OPPOSITE of the naive table. Every sized policy (veto-cheap / down-only / graded 0-1.5x) is ≤ FLAT on BOTH EV (Δ −0.07 to −0.16c, day-t −1.6 to −2.0) AND risk (variance + CVaR5 WORSE, since risk-matched renorm concentrates contracts). FLAT sizing is optimal on the price axis; this is WHY the bot's flat size is right. Valuable negative result: caught a plausible-but-wrong idea that my own first-pass would have shipped — exactly why we test before deploy. REMNANT (untested): the TIME axis (F4-time: later 2nd/3rd boxes worse on correctly-priced e_locked) is the one sizing lever not yet ruled out, but it's narrow (first box 97% early; cap-3 already handles most late volume) — low priority |
| F4b | TIME-CONDITIONED cap: allow k>=4 only when they land EARLY (fills < min 4) | 🟡 quality-neutral but TINY | operator follow-up to F4 (2026-07-13). Naive replay: incremental EV −0.858c/window t=−5.91 (opt fill model; pess −0.267c t=−4.06) — but the negative-mean replay artifact applies (ALL replay boxes score negative; live runs +0.85c). Artifact-adjusted: early k>=4 boxes (−3.55c, strand 6.5%) are comparable-to-BETTER than the k1-3 replay baseline (−4.32c, strand 7.9%) — the intuition is right, early extras are normal-quality boxes. The killer is POPULATION SIZE: only 0.06–0.27 extra boxes/window (+2–9% volume), so even at full live quality the payoff is ~+0.05–0.23c/window. Disposition per rail 2b: forward-arm candidate at most ("cap 3; allow to 5 iff all fills < min 4"), below backlog top; NOT a live change |
| F4c | double/triple down when the hazard model says a strand will pair | ❌ CLOSED (2026-07-13, operator idea) | Two failure modes. MECHANICAL: box profit is fixed at quote time — a confident pair prediction has nothing left to buy; upsizing the completion quote mints a fresh REVERSE strand from a sweep fill (the exact adverse-selected population the strand studies mapped). ECONOMIC (coherent version = add new boxes when state is pair-friendly): payoff asymmetry +0.85c win vs ~−50c realized strand loss ⇒ break-even P(pair)≈98.3%. Quick honest test (BTC, at-fill logit on h0 state, train≤06-29/test≥06-30, AUC 0.617 — consistent with C1 at-fill ceiling; the 0.909 is the per-5s hazard, not available at entry): top-10% bucket pairs 95.4% (below bar), top-5% 98.2% (n=55, at bar, CI huge), top-2% 100% (n=22). Best-case EV ≈ −0.07c to +0.38c per added box on ~0.05 boxes/window ⇒ ≤+0.02c/window. Same verdict family as F4b: quality ~neutral at best, population tiny. Not worth a forward-arm slot vs C3 |
| P1 | PREY→PREDATOR step 1: sub-second websocket tick collector (Kalshi book/trade events at native resolution) | ❓ QUEUED as priority build (2026-07-13, free action — collector-side only) | The binding constraint is DATA resolution, not order latency: L1.5's "1.2s median lead" = ONE TICK at the collector's own 1.2s sampling — the C1 at-fill AUC ceiling (0.58) and the "no pre-fill signal" verdicts were all measured with data that cannot see sub-second microstructure. The predators' whole edge lives below our sampling floor. A ws recorder (sidecar feed) costs nothing live-side and unlocks: re-test C1 ceiling + L1.5 leads at true resolution; F10 exceedance DURATION measurement; dodge-economics for a future fast loop. p90 lead is already 4.8-6.0s even at coarse sampling — a real tail exists |
| P1-lead | FIRST sub-second spot→Kalshi lead measurement (2026-07-13, one 8-min hires capture — PRELIMINARY) | 🟡 the race window is ~0-400ms | Coinbase trade-price changes vs Kalshi trade-price changes, 100ms grid, 500ms horizons: corr 0.459 at lag 0 (±100ms), +0.337 at spot-leads-200ms, +0.160 at 400ms, +0.031 at 1s, ~0 by 2s. Near-symmetric peak → price discovery effectively simultaneous at our venue within ~200ms (the ms-bots consume spot within one tick of their loop). IMPLICATIONS: (a) quantifies P2's gate — a reaction loop must be <~200-300ms end-to-end to capture meaningful spot-lead; GHA ws (~0.5-1s) captures <10% of it; a us-east-1 VPS (~30-100ms) captures most; (b) explains L1.5's null at 1.2s sampling — the lead never existed at that resolution horizon; (c) F10-style 'slow prey' confirmed absent even at sub-second: signal is consumed too fast. CAVEATS: n=1 run (477s overlap), trade-price proxy (not ToB), single evening regime, Coinbase-only (Binance geo-blocked; true global lead may be earlier). Re-measure on ~5 days of sliced-v2 hires data before any P2 build decision. ETH EXTENSION (operator ask): when the ETH sleeve arms, add KXETH15M + ETH-USD to hires (sliced budget handles it) AND test BTC-spot→Kalshi-ETH cross-asset lead (crypto beta: BTC likely leads alt repricing by MORE than 200ms — potentially the one lead long enough for slower infra to capture) |
| P2 | PREY→PREDATOR step 2: fast reaction loop (ws order path, sub-second cancel/replace) | ❓ BLOCKED on P1 evidence | Do NOT build until P1 data shows (a) sub-second discriminating signal exists (else C1 ceiling binds and speed buys nothing — dodging all sweeps also dodges the 88% that pair) and (b) avoidable-toxicity EV > build+run cost. GHA cron can host a persistent ws process inside a leg; never colocated-fast, but the target tier is the SLOW predators/humans, not the ms-bots |
| P3 | PREY→PREDATOR step 3: VPS migration ladder (free GHA-ws → $5-15/mo us-east-1 VPS → top-tier colo-equivalent) | ❓ REGISTERED (2026-07-13) — gated | Latency chain today: spot feed ~1-3s stale + Kalshi poll ~1.2s + GHA→AWS order path ~50-150ms. Cheap tier (EC2/Lightsail us-east-1, ws feeds, ~30-100ms end-to-end) is the sweet spot: also fixes MEASURED losses independent of sniping — F7 13% coverage gap + the late-join strand class (1.7x, validated). GATES: deploy cheap tier iff F10 measures capturable pool >= ~$2/day at 100ms reaction; requires operator word (keys move off GHA; live-loop migration is a rail-1-adjacent architecture change — middle path: VPS does data+sniping only, GHA keeps box loop). Top tier ($100-500/mo, <15ms, MM API tier): only at escalation step 3+ AND F10 pool >$100/day — venue capacity and bankroll bind before infra does. All $ figures are PRIORS until F10; defensive gains are measured |
| F10 | stale-quote sniping (take obviously mispriced resting orders; exploit other bots' missing backstops) | ❌ CLOSED at >=2.4s persistence (2026-07-13 scan); sub-2.4s remains open pending P1 hires data | Scan ran twice on the 33-day BTC tape (train<=06-29 calibration / test>=06-30 economics, day-clustered). (1) HINDSIGHT detector (profitable vs mid 10s later): pool looks huge (+$112/day/contract, 2494 eps/day, t=19) — but that's momentum PREDICTION, not staleness; unusable at decision time. (2) CAUSAL detector (touch mispriced vs spot-distance theo, vol train-calibrated, margins 1-3c, >=2.4s persistence, take at re-observed tick-2 price): LOSES −$27/day/ct (t=−3.6); with empirically calibrated z→P(settle) map (no model-shape objection): −$38/day/ct (t=−4.2), robust across margins, worse with 1c slippage haircut. THE INSIGHT: book−theo deviation IS information (flow/momentum the book knows, static maps don't) — 'obviously mispriced' resting orders at observable resolution are the book being smarter than the model; the taker eats adverse selection just as our maker quotes do. Reliability table shows realized outcomes MORE extreme than driftless theo (pred .55→realized .65). No forgotten-backstop pool exists above 2.4s persistence. Sub-2.4s flash staleness = P1 question. Passive-only boundary stands (inducing malfunction = manipulation, out of scope) |
| F11 | width-gated pairing (engage only when box locks 2-4c; hold out for bigger boxes) | ❌ CLOSED (2026-07-13) | Achievable width at fill (1−p1−pc0) is nearly DEGENERATE: p10=p90=1c; width≥2c is only 3% of fills (n=81). Those wide boxes ARE relatively better (−1.57c vs −4.2c replay EV, pair 92.5% vs 88%) but subset day-t=−1.12 (NS) and gating on ≥2c discards 97% of volume ⇒ destroys ~97% of live EV. 'Hold out for wider' (quote back 1c) already falsified by L0.5 BACK-1c: deeper fills are MORE toxic — adverse selection eats the extra width. Only live path to more width is F2 (conditional widening in high vol, elasticity study open) |
| F4d | price-band × time cells where pairing is disproportionately likely → bypass the box cap there? | ❌ CLOSED (2026-07-13) — high pair rate ≠ profitable box | Direct test on the cap=10 replay (records_f4, both fill models): pairing IS disproportionately likely in EXTREME price bands — 85-99c leg-price boxes pair 89-94% (vs 75% baseline) with tiny strand rates (1-3.5%), and 65-85c pair 82-84%. BUT the reliably-pairing cells lock ~zero spread: 85-99c/min6-9 pairs 93.8% yet EV −0.37c/box (opt); 65-85c/min10+ pairs 82.5% yet EV −10.37c (the 17.5% that miss strand late+expensive). The cap (max-fills-side 3) is NOT a pairing constraint — it's an adverse-selection constraint, and extreme-price boxes just swap 'strand' for 'thin/negative lock'. Only genuinely positive cell (85-99c/min3-5: +0.04c opt / +0.81c pess) has n=38-132 over 33 days — the F4b population problem again. ACTIONABLE THREAD: the extreme-price regime pairs reliably with room to quote WIDER → that's F2 (adaptive quoted edge), the real way to monetize high pair rate. No cap bypass; feeds F2 |
| F13 | cross-venue Kalshi↔Polymarket (box or lead-lag) | ❌ CLOSED (2026-07-13, delegated study; xvenue2/RESULTS.md) | 30 overlapping days, 2.1M matched 1s points (80.5% joint uptime). (1) NO BOX IS CONSTRUCTIBLE: Polymarket lists ONLY btc-updown-5m (close-vs-open, 300s) — different claim AND tenor vs our 15m fixed-strike; no same-event pair exists in 1.5M rows/8597 contracts. (2) LEAD-LAG: KALSHI LEADS POLYMARKET (peak lag −1s, corr 0.291 t=71); pmkt-leads side only 0.032; strictly-predictive pmkt-beyond-spot partial 0.028, ΔR²=0.0013 — a tenth of a tick, likely spot echo. No signal worth a forward slot (pre-registered test spec in RESULTS if ever revisited; expectation: fails). (3) INCIDENTAL DATA-QUALITY FIND: the collector tick tapes' spot column (r[2]) LAGS Kalshi mid by ~12s (corr peak at −12s) — it's a stale index poll. Any past study using r[2] as 'real-time spot' inherited that staleness; the hires Coinbase trade stream (10/s, ms-stamped) is the fix going forward |
| F14 | FRACTIONAL partial-fill residuals ride to settlement unhedged | 🟡 ROOT-CAUSED — 3 integer-rounding blind spots; fix is propose-only + needs a venue probe | 2026-07-13 21:00Z settled −$0.20 despite looking paired. VENUE-CONFIRMED fractional positions (post_position_fp = −1.52 then 0.48): a 2-lot NO order partial-filled 1.52 while the YES filled 2, leaving 0.48 long-YES that settled worthless (5.52 boxes ×+0.01 = +$0.055 − 0.48×$0.53 = −$0.25 ⇒ −$0.20). QUANTIFIED across all 91 live-traded windows: 16 (17.6%) carried a residual; 5 sub-0.5 (the leak: 0.01/0.10/0.30/0.41/0.48); ~3 meaningful (>0.25). Est. drag ~$0.05-0.20/day = ~5-15% of current EV — real, not a fluke. EXACT MECHANISM — THREE sites all blind to sub-0.5 fractional net: (1) kalshi_trader L1144 completion size `deficit=int(round(abs(net)))` → round(0.48)=0 → no completion quote; (2) L2261 dispose-cross `need_=int(round(abs(nd)))` → 0 → no cross; (3) L1917 strand flag `abs(py-pn)>0.5` → not flagged. So a <0.5 residual is invisible to ALL machinery (is_completing_side DOES fire at >1e-9, but deficit rounds its order to 0). Note the rounding also OVERSHOOTS the other way (net 1.52 → completes 2 → creates the 0.48). DEFINITIVE ROOT CAUSE (resolved from history + Kalshi docs, no live probe needed): KXBTC15M is a FRACTIONAL-ENABLED market (Kalshi fixed-point migration — fractional order sizes enabled per-market; we see 1.52-contract fills, so it's on). On such markets the LEGACY integer `count` field is TRUNCATED; you must send `count_fp`. Our place_order (L~604) sends `"count": str(int(count))` — the legacy integer field — so we quote integer-quantized into a fractionally-filling market, and then integer orders can NEVER flatten a fractional residual (history proof: a window oscillated 1.00-lots −0.47→0.53→−0.47→0.53, never 0). Confirmed 22 clean fractional flattens in history were all NATURAL maker fills landing exactly on the residual, not deliberate closes. FIX (building behind default-off flag, bot branch = free action; deploy = operator flag-flip in live.yml, propose-only): (1) place_order gains count_fp support (2-dp); (2) near-close, flatten any |net|>0.01 via a count_fp sell-to-close sized to exact abs(net_delta); (3) telemetry records fractional-residual drag. OFF path byte-identical (still str(int(count))). Offline-validatable: sizing logic, dry-run byte-identity, manufactured partial-fill replay of the flatten decision. NOT offline-confirmable: live count_fp API acceptance — that lands on the operator's first ON run (or a tiny paused-bot probe). PREVENTION MONITOR (live now): daily-cycle fractional-residual scan on abs_strand (charter). FIX BUILT + pushed (bot branch 25e920080, default-off): --flatten-fractional flag; count_fp support in place_order (count_fp=None path byte-identical, verified); near-close single count_fp order flattens exact residual, fires once/window, genuine-fractional only. Gates: safeguards 40/41 (T21 pre-existing only), guardian 18/18, new T40. GRACEFUL-FAILURE PROPERTY: if Kalshi rejects the count_fp body, place_order just returns error and the residual rides to settlement = current behavior — the fix can only help or be neutral, never worse. DEPLOY PROPOSAL (operator, propose-only): add `--flatten-fractional 0.1` to live.yml trader args (0.1 catches the meaningful 0.3-0.48 residuals, skips trivial <0.1); first ON run confirms live count_fp API acceptance (watch the [F14] log line + winrec frac_flatten_count). AWAITING OPERATOR WORD |
| NS-QUOTE | near-strike quote-construction (distance-conditional edge-demand / asymmetric micro-imbalance quoting), tick replay | ❌ BOTH DEAD (2026-07-13; nsquote/RESULTS.md) | JOIN baseline −3.25c/win (33d, verified vs independent replicate.py). A (near-strike back-off 1c): dead across the whole D grid, best TEST −0.008c t=−0.40; far-control toxic (strand 1→14) = reproduces L0.5, no near-strike interaction. B (asymmetric micro-imbalance quoting, 128-cell grid): best TRAIN cell t=+4.52 → TEST +0.120c t=+0.95 (overfit collapse; only 1/15 top-train cells clears TEST t≥2 and it's not the selected one = multiple-comparisons noise). Neither clears t≥2 OOS. Clean negative closes the near-strike quote-construction question |
| NS-STRAND-CLOSEOUT | can the near-strike strand loss be prevented at ENTRY / quote-time? (comprehensive, 2026-07-13) | ❌ NO — entry side exhausted; disposal STACK is the only strand lever | Five approaches tested this session under honest train/test + falsification: F-size (price sizing) dead; NS-DISP (cross-complete exit) dead+subsumed; NS-QUIET (quiescence veto) marginal t=−1.49; completion-flow veto dead (flip); time×dist untestable; NS-QUOTE A+B dead. The STRAND-ATTR reframing (near-strike chop = 51%+58% of loss) correctly located WHERE the money bleeds, but every ENTRY/QUOTE intervention washes out OOS or is already inside the deployed hazard model. CONCLUSION: the strand leverage is DISPOSAL (the stack's L2 2-step stopping, forward-testing, gate ~07-24), not prevention. Highest-value action = get the stack through its forward gate; do not spend more on near-strike entry rules |
| NS-VETOES | entry-veto battery (near-strike × quiet / completion-flow / time×dist), train/test + calibration + falsification | 🟡 all WEAK; only NS-QUIET directionally survives, marginal | Proper train/test (thresholds on TRAIN≤06-29, eval TEST≥06-30), replay→live calibration (offset +4.98c), falsification on FAR legs. (1) NS-QUIET |p−.5|<.1 & quiet: TRAIN +0.23c/win t=−2.81 → TEST +0.065c/win t=−1.49 (degrades); sign survives (vetoed subset live-EV −0.32c<0) AND far-quiet control HURTS (−0.068c) so it IS near-strike-specific — but weak + costs 20% volume for ~1.5% EV. (2) COMPLETION-FLOW (ns & low tickrate): DEAD — train/test FLIP (test vetoed subset live-EV +1.22c POSITIVE → vetoing loses). (3) TIME×DIST (ns & late): untestable — near-strike-LATE first-fills too rare (first fills 97% early). VERDICT: the ENTRY side is a weak lever; NS-QUIET is real-but-marginal (forward-arm only if roster has headroom, low priority). The disposal-side STACK (forward-testing) remains the strand leverage. Supersedes the earlier in-sample NS-QUIET screen (t=−2.03 was pooled/in-sample; honest test is t=−1.49) |
| NS-QUIET | near-strike × QUIET entry veto (the vetoable subset the attribution points to) | 🟡 superseded by NS-VETOES (honest train/test): in-sample t=−2.03 → test t=−1.49, marginal | Diagnostic (in-sample, all 33d): near-strike opens (|p1−0.5|<10c) net −4.78c/11.9%-strand vs far −3.60c/11.5%. Splitting near-strike by QUIESCENCE (vol30 AND |drift30| both below median = the 58%-of-loss regime): near-strike+QUIET = −5.92c/14.4% strand vs near-strike+ACTIVE −3.94c/10.1%. QUIET-vs-ACTIVE difference −3.67c/open, day-clustered t=−2.03 (n=32d) — a real distance×quiescence interaction, NOT just the general near-strike or general-vol effect (both weaker). CONTRAST: static completion-side depth (qdepth_f) did NOT separate (thin −4.92 vs thick −4.64) — it's the DYNAMIC no-flow (quiet) condition, not static thinness. CAVEATS before believing it: (1) IN-SAMPLE, no train/test yet — hypothesis not result; (2) volume-cut artifact — vetoing removes 527 opens (19%), which flatters a negative-mean replay; needs volume-matched framing; (3) near-strike-quiet still PAIRS 85.6% — vetoing loses those good boxes, so the real question is strand-savings vs pair-profit-lost. DISTINCT from the deployed stack (L0 champion = depth+minute; hazard L2 = disposal not entry). NEXT: build as a box_shadow entry-veto arm (veto |p1−0.5|<D AND vol/drift both low), forward-gate t≥2 vs live over ≥10d |
| NS-DISP | near-strike cross-to-complete (operator's proposed fix: pay ~1c to complete coin-flip legs early) | ❌ does NOT generalize — suggestive in-sample, washes out OOS | Rigorous 33-day study (nsdisp/RESULTS.md, baseline = exact live-disposal reproduction, EV −4.61c/win). Best cross-complete cell (D=0.10,S=5s): TRAIN +0.39c/win t=1.73 → TEST +0.01c t=0.04 (gone). Robust D=0.05 cell: TEST +0.30c t≈0.8, still under bar. Far-leg falsification CLEAN (near-strike-specific, not a generic cross-early edge — the one encouraging sign). COMPLETE-vs-DISPOSE: tie BY CONSTRUCTION (tape has only the YES book; taker_fee symmetric in p(1−p) makes the two algebraically identical — a real comparison needs the NO book / live data). SUBSUMPTION: the deployed hazard model already has dist/theo_dist as its two largest coefficients (−2.33/−2.39, dwarfing 32 others) — a hard near-strike rule is a coarse proxy for what the stack's L2 stopping already encodes. VERDICT: not forward-testable as its own arm (t≈0.8); the near-strike signal is real but already inside the stack. The operator's instinct was right about WHERE the loss is (STRAND-ATTR) but the flat cross-complete rule isn't the lever — the stack's hazard stopping is |
| STRAND-ATTR | where does strand-loss money actually go? (deep dive 2026-07-13, operator ask after a losing cluster) | ✅ REFRAMED — near-strike CHOP, not directional moves | 324 BTC strands, mean −43c, median −44c. (1) FREQUENCY-driven NOT tail: worst 5% of strands = only 9% of loss, worst 50% = 66% (near-uniform) → cut frequency/depth, not rare disasters. (2) NEAR-STRIKE concentration: |p1−0.5|<10c legs = 51% of all strand loss (mean −48c), vs 25c+-from-strike = 14% (−31c). (3) COUNTERINTUITIVE — trending/vol markets strand LESS: hi-drift(top10%) strand rate 6.0% vs 12.3% rest; hi-vol 7.6% vs 12.2%; lo-drift+lo-vol QUIET windows = 58% of loss. MECHANISM: price hovers at strike → one leg fills maker → the other never completes (no momentum to push it) → strands as a coin flip. This is the DOMINANT loss mode (not the directional tail I first flagged for the 22:00Z cluster — that settle pattern was no/no/yes/yes = chop, consistent). LEVER (testing, node NS-DISP): near-strike unpaired legs have unfavorable RIDE economics — 2c maker edge × P(complete) is dwarfed by 43c × P(strand); aggressively cross-to-COMPLETE (or dispose) near-strike coin-flip legs early rather than rest-and-hope. Distance-to-strike-conditional disposal timing is the specific untested refinement beyond the stack's uniform hazard rule |
| F5 | strand-clustering cooldown | ❌ NO basis | P(strand\|prev strand)=0.143 vs base 0.142, t=−0.71. Strands do NOT cluster window-to-window. Keep consec-strand kill only as cheap tail insurance; don't extend it |
| F6 | inventory skew across concurrent legs | ❓ | covered partially by --max-net; model later |
| F7 | coverage gaps (GHA cycle restarts) | ✅ FIXED 2026-07-13 (main 63c03d946 + trader 093c98304, operator 'Fix all') | LIVE-CONFIRMED by audit: zero-box windows at 14:15/15:00/15:45Z on the ~46-min leg cadence = 3-4/23 daytime slots (~16%) lost. FIX (two coordinated parts resolving the overlap-vs-double-quote tension): (1) live.yml pre-chains the successor BEFORE trading — it parks PENDING in the concurrency singleton and starts the instant the old leg ends (gap 2-4min → ~60-90s setup; chain now survives runner hard-kills); (2) trader --join-fresh-s 60 — a window this process ATTACHED to >60s after open gets no OPENING quotes (completions/disposal exempt), so two sequential legs can never double-fill one window (the 12:00Z ny=5 strand class) and the node-N late-join strand class is closed at process level. winrec now carries join_s/joined_late — the direct A/B fields. Gates: safeguards 39/40 (pre-existing T21 only), guardian 18/18, new T39. MEASURE: daily cycle tracks zero-box-window count + strand rate before/after |
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

## OVERNIGHT ROOT-CAUSE (2026-07-14, operator ask: analyze every trade esp. negatives; do stacks work; are losses clustered?)
Corpus: 97 live-traded windows across 07-13/07-14 (winrec_all.jsonl), total +4.0c mark
(net POSITIVE overnight); 17 negative windows (17.5%). Plus 7-day BTC stack replay (bs.jsonl).

- OV-LOSSMODE ✅ **Losses are negative-width COMPLETIONS, not true strands.** Of 17 neg
  windows: only **2 are true strands** (|abs_strand|>0.5, mean −0.47c); **15 are
  negative-width completions** (|abs_strand|≈0, box bought >$1 at adverse price, mean
  −0.15c). True-strand rate is just 2/97=2.1% (well below the ~11% corpus baseline) — the
  disposal stack IS suppressing strands; the residual bleed is the machinery COMPLETING at
  an adverse price rather than leaving a leg naked. Reframes the loss target from "prevent
  strands" to "complete boxes before the price crosses through $1."

- OV-MECHANISM ✅ **legging_gap_s is the adverse-completion signal — NOT late-join.**
  Neg windows: mean legging_gap 27.4s vs winners 7.9s (3.5×). AUC 0.585. Threshold table:
  gap<5s → 14% neg-rate, +0.053c mean (69 windows, the healthy core); gap≥30s → 50%
  neg-rate, −0.021c mean (10 windows, the danger zone). By contrast join_s is a red
  herring: neg=20.5s vs pos=19.0s (identical); deadman_tier lift 0.99×; joined_late n=0.
  MECHANISM: when the second leg is slow to complete, spot drifts and the completing leg
  is bought through par → box costs >$1. This is exactly what the stack's hazard/thickbook
  stopping targets — coherent with the stack design.

- OV-CLUSTER 🟡 **Streaks are REAL but rare and regime-bound — earlier "no-clustering"
  verdict REVERSED by the fuller corpus.** Permutation run-test: 6 observed consec-negative
  pairs vs 2.81 expected under independence, **p=0.033**; lag-1 autocorr +0.226;
  P(neg|prev neg)=35% vs P(neg|prev clean)=13%. BUT it is entirely one 80-min regime:
  07-13 22:10–23:30 UTC = six near-consecutive neg windows (all full-size 6-box, all
  negative-width completions); 07-14 shows ZERO consec-neg pairs. So it's a persistent
  adverse-drift STRETCH, not a mechanical bot-state carryover. (Supersedes the 72-window
  peek that said lag1=−0.05; that sample missed the 07-13 evening regime.)

- OV-BREAKER ❌ **Streak circuit-breaker is NOT worth it.** Backtested skip-after-N-neg:
  skip-after-2 recovers only +0.22c over 97 windows by skipping 3 windows (2 neg / 1 pos);
  skip-after-1 recovers +0.09c but sacrifices 8 profitable windows (skips 8 pos / 4 neg);
  half-size-after-neg +0.14c. All marginal on tiny absolute numbers and the breaker throws
  away nearly as much good as bad — negativity isn't predictable enough window-ahead to
  gate on. The lever is the disposal stack (completes faster/cleaner), not a meta-skip.
  (Any size/skip change is live rail-1 propose-only regardless.)

- OV-STACK 🟡 **Stacks perform as designed in the 7-day TEST-period replay (07-07..07-13)
  — but this is NOT yet forward data.** BTC, day-clustered t vs live (live baseline
  −4.98c/win, 8.5% strand):
    combined      strand 8.5%→**0.0%**, +1.93c/win, **t=+4.68**
    stack_lean    0.0%, +1.46c, t=+4.51
    stack_full    0.0%, +1.61c, t=+4.34
    c3_share      4.3%, **+2.21c** (highest EV), **t=+8.02**
    hazard_stop   0.0%, +0.91c, t=+2.70
    thickbook_veto 6.4%, +1.20c, t=+2.47
    back2         13.8%, −0.67c, **t=−0.95** (falsification control on BTC — correctly
                  WORSE than live, as expected for quoting 2c behind touch)
    cell_veto / givecap15  byte-identical to live (inert; retire-watch at 10 days)
  CRITICAL CAVEAT: 07-07..07-13 is the arms' OWN fit/test window — these reproduce the
  replay priors, they are NOT held-out forward evidence. The forward clock starts 07-14
  (box-shadow.yml now running); promotion gate ~07-24 (≥10 forward days, day-clustered
  t≥2, avseq early-promotion only). Do not promote on these numbers.

## OV-VOLGATE (2026-07-14, operator ask: "predict AND prevent the negative-window streaks, statistically sound")
Follow-up to OV-CLUSTER (streaks are real, perm p=0.033, but regime-bound). The naive
circuit-breaker (OV-BREAKER) was rejected because it conditions on the noisy prior OUTCOME.
A sound predictor needs a CAUSAL, LEADING regime variable. Built one from per-window BTC
spot realized vol (from fills_all ctx.spot, 97 windows 07-13/07-14):

- MECHANISM ✅ **Streaks = volatility clustering.** Per-window spot logret-vol has lag-1
  autocorrelation **r=0.58** — high-vol regimes persist across windows. Negative windows are
  higher-vol (vol +32%, drift +42%, range +25% vs winners). The loss mode (negative-width
  completion) IS an adverse-price-move event, so it concentrates where vol/drift is high — and
  because vol clusters, the losses cluster. This is the generating mechanism of the streaks.

- PREDICTOR ✅ **Trailing (prior-window) vol is a sound leading signal.** AUC 0.655 for
  prior-window vol → this-window negative, beating prior-OUTCOME (0.619, the circuit-breaker's
  signal) and prior legging-gap (0.498). CONTEMPORANEOUS within-window vol does NOT predict
  (AUC 0.48) — so the tradeable signal must be LEADING, which only works because vol persists.
  Generalizes OOS across the day boundary: day-2 negatives also had higher trailing vol
  (1.20e-4 vs 7.60e-5); a day-1-trained threshold skipped 2 of 3 day-2 negatives.

- VS THE VOLUME-CUT NULL ✅ **Vol-gating beats volume-matched random-skip.** The artifact that
  invalidates any skip rule (skipping x% of a negative-mean process looks good) is defeated by
  a permutation null that skips the SAME NUMBER of random windows: top-decile-vol skip gives
  ruleEV +5.82 vs random-skip mean +4.38, **p=0.001**; top-quartile p=0.014. The rule
  preferentially skips bad windows far beyond chance — unlike the naive breaker.

- PREVENTION ✅ built as forward arm **volgate** (box_shadow, bot branch 70ed86897): veto
  opening a box when the immediately-prior window's realized vol sat in the top quartile of the
  trailing regime. Chosen over skip-on-outcome (noisy) and over a hard skip of ALL high-vol
  windows (forgoes the wider maker edge high vol also brings). Existing arms byte-identical
  (1850 rows). Replay prior 06-10..06-13: strand 7.6%→4.9%, +0.96c/win pooled, t=+1.59 (4 days).

- HONEST LIMITS: (1) validated on 2 day-clusters for the signal, 4 days for the arm prior —
  CANNOT pass the day-clustered gate yet; forward clock starts now, gate ~07-24+. (2) The arm
  uses KALSHI-MID vol as the in-harness regime proxy (BTC spot is not in the replay tape), a
  weaker signal than the study's spot logret vol — the forward arm may underperform the study.
  (3) Absolute prevention value is small (~+0.05c/day walk-forward on 07-14) because the
  disposal stack already shrank the losses to ~−15c — the streak is a real but low-stakes bleed.
  VERDICT: statistically sound predictor + prevention lever BUILT and forward-testing; deploy
  only after the gate (rail-1 propose-only for any live entry-veto regardless).

## OV-STATE (2026-07-14, operator ask: "pool all data at finest fidelity; unsupervised learning / Markov / K-means to define the streak-causing state")
Pooled 2864 BTC windows over 33 days (regime/tick_features.csv: per-window realized vol, mean
spread, mean depth, tick count) joined to box_shadow live-arm outcomes (631 windows, 10 days;
bad = bottom-quintile locked OR stranded, ~7.6%). GaussianMixture, BIC-selected K=5. Method
broke the small-live-sample bottleneck by using the replayed live-arm P&L as the large-N label.

- STATE DISCOVERY ✅ **A sharp bad-window state exists: tight-spread / illiquid / quiet.** The 5
  GMM states span 2.8%→22.7% bad rate (8× spread). Worst state = LOW tick-rate (314 vs ~650),
  low vol = the quiet/illiquid window (matches STRAND-ATTR: price hovers at strike, one leg never
  completes). Contemporaneous discrimination is STRONG and temporally validated: single mean_spread
  AUC ~0.74 pooled, and on a June-train/July-test holdout the tight-spread→bad direction holds at
  AUC ≈0.76 (widest-spread quintile has 0.29× the bad rate). This is a much sharper CONTEMPORANEOUS
  signal than single trailing-vol (0.65) — answers "there should be a higher-AUC signal": yes, but
  only WITHIN the window, from the full microstructure state.

- MARKOV / PERSISTENCE ✅ **The bad state does NOT persist → it CANNOT be the streak cause.** Fitted
  5-state transition matrix: self-persistence p_stay 0.25–0.37, expected dwell ~1.4 windows (~21 min)
  for EVERY state incl. the worst (0.29). Simulating the fitted state-Markov + state-conditional bad
  rates over 97 windows: P(bad-run≥6) = 0.000 (mean max-run 1.45) — FEWER long runs than independent
  draws (P≥6 = 0.003). And LEADING (prior-window state → this-window bad) AUC = 0.48 (nil). The market
  microstructure state reshuffles too fast to generate a 6-in-a-row streak.

- VERDICT ✅ **Unsupervised + Markov DECISIVELY REFUTES the persistent-market-regime hypothesis for
  the streaks.** The bad state is real but TRANSIENT (visited, not dwelt in). Reconciles with OV-CLUSTER
  (streaks = compounding of weak autocorr + chance clustering of the tiny near-strike coin-flips), not a
  sticky regime. The lever therefore is NOT a pre-window streak-breaker (leading signal ~nil) but an
  IN-WINDOW defensive trigger: tight-spread/illiquid is detectable in a window's first seconds → switch
  to defensive completion. CAVEATS: (1) outcome is replay locked, and mean_spread may couple
  mechanically with locked — needs live-P&L confirmation before any deploy; (2) a persistent driver, if
  one exists, must live OUTSIDE these 4 market features — directional spot drift, bot inventory carryover,
  or sub-second structure (P1 hires, retest ~07-18). Those are the only remaining places a streak-
  predictor could hide. NEXT: build the in-window tight-spread/illiquid defensive-completion arm; test
  drift-persistence + hires sub-second features for any true leading signal.

## OV-2POP (2026-07-14, operator hypothesis: "the clustered/consecutive negatives have a predictable state; other negatives are a different population")
CONFIRMED. Pooling the loss populations was diluting the signal. Two mechanistically distinct
loss types, split cleanly by MAGNITUDE (live overnight, 97 windows):
- BIG losses (mark < −0.15, n=6): DRIFT-DRIVEN adverse completions. mean |spot-drift| 0.0005
  vs 0.0002 for winners (~2.5×).
- SMALL negatives (−0.15 ≤ mark < 0, n=11): quiet near-strike COIN-FLIPS. mean |drift| 0.0001
  (BELOW winners) — genuinely driftless noise.

DISCRIMINATION (the vindication of the two-population hypothesis):
- Contemporaneous |drift| → BIG loss AUC 0.635; → SMALL neg AUC **0.500 (exactly chance)**. The
  clean separation (drift predicts big, is chance for small) is strong internal evidence the two
  populations are real and distinct, not one continuum.
- LEADING (prior-window |drift|) → BIG loss AUC **0.875**; → SMALL neg 0.568. The drift-driven
  big losses ARE predictable one window ahead, because |drift| (volatility) PERSISTS: |drift|
  lag-1 autocorr r=0.52 (signed-drift only 0.23 — magnitude persists, direction doesn't). This is
  why the pooled predictor capped at AUC 0.65: it averaged a strong signal (0.875, big) with noise
  (0.50, small).

RECONCILES EVERYTHING: (1) the 07-13 22:10–23:30 "streak" = 2 genuine drift-driven big losses
(22:10, 22:30, in a persistent high-|drift| stretch) + a TAIL of unrelated quiet coin-flips that
happened to follow → the run LENGTH is padded by noise, but its CORE is a real predictable regime.
(2) OV-STATE's replay showed no clustering because the replay lacks the directional price path —
the clustering driver is DRIFT/VOLATILITY, not Kalshi microstructure. (3) Matches vol-clustering
(vol autocorr 0.58) and volgate.

CRITICAL CAVEAT: n=6 big losses over 2 days — AUC 0.875 is a strong HINT with a huge CI, NOT
validated. The clean contemp big-vs-small separation (0.635 vs 0.500) is the robust part; the
0.875 leading figure needs forward data on the big-loss subset. VERDICT: operator was right —
the consecutive/clustered losses have a predictable state (persistent high-|drift|/volatility
regime, leading AUC ~0.875 provisional); the scattered small negatives are irreducible low-stakes
noise (don't try to prevent them). NEXT: (a) sharpen the leading detector to TARGET the drift-driven
big-loss subset (trailing |drift| / vol regime) rather than all negatives; (b) forward-collect the
big-loss subset to validate the 0.875; (c) trigger defensive completion (not skip) when the regime
fires, since the loss mode is adverse completion.

## OV-STRIKE (2026-07-14, operator: "could it be pegged to price or movement of price in BTC?")
YES — unifies both loss populations. The Kalshi box strike is pegged to BTC price; the leg prob
mid≈0.5 is a direct readout of "spot AT the strike." Live overnight (moneyness = |mid−0.5|,
leg-swing = mid range over the window):
- SETUP (both loss types): near-strike. entry |mid−0.5| big=0.068 small=0.076 vs winners 0.102;
  closest approach big=0.048 small=0.059 vs 0.085. You can only lose when spot is at the strike
  (coin-flip zone) — confirms STRAND-ATTR for BOTH populations.
- TRIGGER (separates big from small): PRICE MOVEMENT at the strike. leg-swing big=0.114 vs
  small=0.050 ≈ winners 0.048 (2.3×). AUC(mid_travel→big)=0.611, →small=0.520. Strike CROSSING
  per se does not discriminate (AUC 0.49) — it's the magnitude of movement, not a discrete cross.
- MECHANISM (complete unification): spot at strike + STILL → leg never completes → strand/coin-flip
  = SMALL loss (movement ≈ winners). Spot at strike + MOVING → complete 2nd leg at adverse price
  = BIG loss (movement 2.3×, = OV-2POP's drift-driven type). And movement persists (|drift| autocorr
  0.52) → big losses cluster + are leading-predictable (OV-2POP AUC 0.875 provisional).
- PRICE LEVEL (round numbers): losses marginally nearer $500 marks (dist $82/$85 vs winners $112)
  but n=6, weak — do not over-read.
CAVEAT: n=6 big, mid_travel AUC 0.611 modest/noisy. VERDICT: the loss is pegged to price-relative-
to-strike (setup) AND triggered by price movement at the strike (trigger) — both required. The
sharpened predictive feature is the INTERACTION near-strike × high-movement-regime, not raw drift;
forward-test that as the big-loss detector.

## STRATEGY SCOREBOARD — top 10, tested + tiered (2026-07-14, operator ask: rank the 10 best, promote winners)
Consolidated day-clustered replay (11 days: 06-10..13 + 07-07..13; volgate 4 days) vs live baseline
(strand 8.3%). TIER LADDER: ✅DEPLOYED(live) · 🟢PROPOSAL(prepared, awaits operator word + fwd gate)
· 🟡FORWARD-TESTING(replay-validated t>2, accruing toward ~07-24 gate) · 🟠PROVISIONAL(positive,
under bar/thin) · 🔬HYPOTHESIS(mechanism, n too small) · ❌DEAD. HARD HONESTY: the 11 days are the
arms' fit/test period, NOT forward — strong t = replay-validated, NOT gate-passed. Nothing is live-
promotable until ≥10 FORWARD days (clock started 07-14) + operator word (rail 1). avseq early-promo
needs ≥5 fwd days — not yet reachable either.

  #  strategy            Δc/win   t    strand%  tier          note
  1  c3_share           +1.94  +7.02   4.4   🟡 FWD-TEST   highest EV+t; completing-side depth-share veto
  2  combined           +1.90  +6.07   0.0   🟢 PROPOSAL   strand ELIMINATOR (haz+thick+cell); top deploy candidate
  3  stack_full         +1.47  +4.15   0.0   🟡 FWD-TEST   full L0-L4 stack, give-cap 0.15 + LCB sensor
  4  stack_lean         +1.39  +4.28   0.0   🟡 FWD-TEST   stack, give-cap 0.25, no LCB (leaner)
  5  thickbook_veto     +1.05  +3.29   6.3   🟡 FWD-TEST   skip when completing-side book too thick
  6  hazard_stop        +0.96  +3.49   0.0   🟡 FWD-TEST   FOUNDATIONAL state-dependent disposal (kappa)
  7  volgate            +0.96  +1.59   4.9   🟠 PROVIS     vol-regime entry veto (4d, under t2; OV-VOLGATE)
  8  F14 frac-flatten     —      —      —    ✅ DEPLOYED   live since 2cd9ae62c (operator-approved); 0 fires=no >0.1 residual yet
  9  join-fresh/k-cap5    —      —      —    ✅ DEPLOYED   late-join suppression + open-k-max 5 (in live.yml)
 10  nearstrike×move      —      —      —    🔬 HYPOTH     OV-STRIKE/2POP big-loss detector; leading AUC 0.875 @ n=6

PROMOTIONS THIS CYCLE: #1-6 advanced replay-supported → FORWARD-TESTING (accruing to ~07-24 gate).
#2 combined + #8 F14 → deploy PROPOSAL prepared (operator word required; F14 de-risking so operator
word alone suffices, the arms need the fwd gate too). #7 volgate stays provisional pending fwd days.
#10 stays hypothesis (n=6, forward-collect the big-loss subset to validate the 0.875).
DEAD (not winners, recorded — do not re-litigate): cell_veto (t=-1.0 inert), givecap15 (byte-identical
to live), back2-on-BTC (-0.85, the deliberate falsification control — correct), F-size, NS-DISP,
NS-QUOTE, F10 stale-snipe, F11 width-gate, hours/window selection.

## OV-ROUND (2026-07-14, operator: "pull the actual strike ladder; test round-number / liquidity-cliff effects properly")
KXBTC15M is ONE ATM strike per 15-min window (ticker suffix = quarter-hour, not a ladder); strike is
set ≈ spot-at-open. Inferred strike per window = spot where mid≈0.5 (198 windows, local 06-10..13 ticks;
130k ticks parsed). Tick = [t,mid,spot,micro,bb,bq,ba,aq]. Reusable test: scratchpad/strike_liquidity_probe.py.
- STRIKE ROUND-CLUSTERING ❌ REFUTED. Inferred strikes are ~uniform vs $100/$500/$1000 (mean dist-to-
  multiple ≈ uniform-expected). Kalshi sets the strike at spot, not at round numbers — so there is no
  round-number STRIKE-placement effect to exploit.
- LIQUIDITY-CLIFF 🟡 SUGGESTIVE but UNDERPOWERED (confounded). Pooled: near-$1000 depth 2195 vs far 2472
  (t=-10.6) + wider spread (0.0100 vs 0.0092, t=13.6) = ~11-14% thinner book near $1000 marks, and it
  SURVIVES day-demeaning (near/far depth ratio 0.86). BUT the $500 test flips sign (near-$500 = MORE depth,
  t=5.7) and there are only 4 distinct $1000 bands in the 4-day corpus (61/62/63/64k) — so "near round"
  is confounded with 4 specific price levels on 4 specific days. Cannot distinguish a round-number LAW from
  level/regime effects at this spot range. Direction (thinner near $1000) is consistent + significant, but
  not proven as a round-number law.
- ACTIONABILITY: even if real, a ~14% depth dip is second-order vs the primary loss driver (OV-STRIKE:
  movement-at-strike). Not a near-term lever. VERDICT: strike-round-number REFUTED; liquidity-cliff PARKED
  as suggestive-underpowered — re-run strike_liquidity_probe.py once the tick corpus spans ≥12 distinct
  $1000 bands (many weeks of wider BTC range), which cleanly deconfounds round-number from level. Do not
  invest further until then.

## OV-2POP-ARM / nsmove (2026-07-14, operator: "build the #10 near-strike×movement arm to accrue forward data")
BUILT + pushed (bot branch, box_shadow.py). nsmove = veto opening a box iff prior-window movement
regime high (reuses volgate_flag: prior-window vol top-quartile) AND entry near-strike (|p1−0.5|<0.15).
Operationalizes OV-2POP/OV-STRIKE: targets the drift-driven BIG-loss population (leading |drift| AUC
0.875 provisional, n=6), a strict SUBSET of volgate's vetoes — it spares the far-from-strike volume
volgate would also skip, so it can only remove volgate's collateral, never add risk.
- Verified: existing arms (incl volgate) BYTE-IDENTICAL (2035 rows, 06-10..13). Fixed an indentation
  bug (main-loop veto is 15-space vs 19-space nested; first pass added nsmove only to the strand path
  → 0 fires) — now fires 29× on the test days.
- Replay prior 06-10..13: +0.55c/win, t=0.79, strand 7.6→6.5% (29 vetoes). WEAKER than volgate
  (+0.96/t1.59) — expected: the big-loss population that motivates nsmove is in the OVERNIGHT 07-13/14
  sample, not this June period, so the near-strike restriction just skips fewer windows here for less
  benefit. Not a refutation; the arm's thesis is forward, not in-sample.
- TIER: 🔬→forward-testing. Now accruing forward rows alongside volgate; the head-to-head (does the
  targeted near-strike×movement veto beat the broad vol veto on the big-loss subset?) is the forward
  question. n=6 → both are provisional until the forward gate. Response is still veto here; a
  defensive-COMPLETE variant (mechanistically preferred, since the loss mode is adverse completion)
  is the next iteration once forward data shows nsmove targets the right windows.

## OV-ORTHO (2026-07-14, operator: "combine the orthogonal winning strategies + retest — maybe instantly promotable")
Tested. Orthogonality structure (4-day replay, per-window improvement correlation + Jaccard):
volgate ⟂ thickbook (corr 0.01, Jac 0.16) and ⟂ c3_share (0.14) — genuinely act on DIFFERENT
windows; thickbook↔c3_share redundant (0.37/0.36, pick one); volgate↔nsmove redundant (Jac 0.63,
subset); cell_veto inert (1 veto); hazard_stop = disposal, different mechanism (~0.41 with all).
So the orthogonal trio = disposal(hazard) + one book-veto + volgate; combined already has
hazard+thickbook but NOT volgate — the missing orthogonal ingredient.
- Synthesized combined+volgate: raw EV −1.90→−1.38c/win, t 3.39→3.29 — LOOKS better BUT veto rate
  35%→51% = the volume-cut artifact (DECISION_MAP K). Raw EV is invalid here.
- DECISIVE VOLUME-MATCHED TEST ❌ NO orthogonal value. Volgate additionally vetoes 30 of combined's
  120 kept windows; combined's hazard disposal earns −3.32c on those vs −2.82c on the kept — only
  slightly worse, and removing them is INDISTINGUISHABLE from removing 30 RANDOM combined-kept
  windows (permutation p=0.371). The EV "gain" is just cutting 16% more volume.
- MECHANISM (the real lesson): volgate and thickbook are orthogonal in WHICH WINDOWS they touch,
  but NOT in VALUE — hazard_stop's disposal already rescues the high-vol windows volgate would skip,
  so stacking volgate on top adds nothing but volume loss. Orthogonal-in-window ≠ orthogonal-in-value
  when a disposal layer subsumes both.
- VERDICT: combined+volgate is NOT promotable (no validated gain; and nothing is instantly live-
  promotable regardless — forward gate + rail-1). Do NOT build it as a new arm (roster already 12;
  additions need a positive replay prior, this has none). CAVEAT: these 4 days (06-10..13) are light
  on the vol-driven big-loss population (that lives in the overnight 07-13/14 sample) — volgate MIGHT
  add orthogonal value forward where that population appears. PLAN: at the ~07-24 gate, SYNTHESIZE
  combined+volgate from the forward rows of the individual arms (both accruing) and re-run the
  volume-matched test — no new arm needed. If volgate then shows orthogonal value, promote the combo.

## LIVE-BLEED (2026-07-14, operator: "unprofitable 36h, figure out what we're missing")
Went to BALANCE ground-truth (not mark/replay). Post-deposit trading window 07-12 15:30 ($61.16
peak) → 07-14 16:50 ($57.67) = **−$3.49 over ~49h** — a slow persistent bleed, not one disaster
(peaks ~$60.5-61 repeatedly and gives it back). Findings:

1. ❗ **OUR TELEMETRY OVER-REPORTS P&L vs the balance.** window_mark=+$0.17, net_final=+$1.17,
   `realized`=−$10.9 (this one is a cumulative running-sum of mark — do NOT sum it). Winrec-implied
   total ≈ +$1.6; balance says −$3.5. A ~$5 gap over 2 days we cannot explain from winrec fields —
   most likely open-position mark-to-market at the snapshot + window_mark's optimistic "every box
   settles to exactly $1" assumption + fractional-residual settlement. **We have been optimizing
   window_mark, which is NOT realized P&L.** First fix: a balance-truth realized-P&L reconciliation;
   stop scoring success on mark. (All arm/replay work is mark/locked-based — revalidate on realized.)

2. ❗ **The paired-box edge is razor-thin and BRUTALLY ASYMMETRIC.** Over 127 paired windows: 97
   positive-width wins (+$5.03, avg **+5.2c**) vs 25 negative-width losses (−$3.26, avg **−13.0c**) —
   **loss:win ratio 2.5:1**, net paired only ~+$1.8 and easily flipped negative by variance/fees. We
   win small and lose big. The whole strategy hinges on avoiding the −13c negative-width completions.

3. ❗ **Negative-width completions are NOT from crossing** — total dispose_give = $0.04, only 22 taker
   fills. They come from BOTH LEGS filling as MAKER at prices summing >$1: leg-1 fills cheap, the
   market moves, and the completing leg's resting quote fills at an adverse price (box costs >$1).
   This is the OV-2POP/OV-STRIKE adverse-completion mode, now measured in REALIZED terms. **The bot
   chases the pair — it completes the second leg at ANY price rather than capping it at ≤(1 − leg1 −
   target_width).** NEW UNTESTED LEVER: price-cap the completing MAKER quote so the box never
   completes above $1; if it can't fill there, strand it (strand EV vs guaranteed −13c). Distinct
   from the disposal stack (which manages strands after the fact; strands netted ~flat +$0.39 this
   window — the leak is adverse completions, not strands).

4. ❗ **F14 deployed but 0 fires despite 11 fractional-residual windows** (incl. one at abs_strand
   4.39) riding to settlement. `--flatten-fractional 0.1` is in live.yml but frac_flatten_count=0
   everywhere — the flatten isn't triggering on residuals it should catch. Concrete bug to chase.

5. Fees −$0.57 over the window — small but real drag on a ~breakeven edge.

VERDICT: we were "green" on mark while red on the balance. The edge is real but thin (+5c) and the
−13c adverse completions + fees + strand variance eat it. PRIORITIES (all propose-only / research —
rail 1): (a) balance-truth realized-P&L metric, re-score everything on it; (b) completing-leg price
cap (never complete a box >$1) — test in box_shadow, the highest-value NEW lever; (c) fix F14 firing;
(d) re-examine whether entry width is wide enough to survive the leg1→leg2 adverse move.

## METRIC-INVALID (2026-07-14, operator: "av_stoikov was supposed to be mega-profitable across a month — what happened? data-collection error? is realized ≠ estimated?")
ROOT CAUSE FOUND — and it invalidates the whole strategy-validation stack, not just av_stoikov.
The month-long A/B that crowned av_stoikov ("mega profitable, never net negative on the day",
WINNING_STRATEGY.md) was scored on the PAPER SHADOW layer (gha_data/<d>/SUMMARY.txt): per-fill
MARKOUT (5-min mid change) under a SIMULATED fill model, REBATE-INCLUSIVE, in per-win NORMALIZED
units, reported as **Δ vs baseline**. Every one of those four removes it from realized dollars:
- **Relative, not absolute.** 07-13 SUMMARY: baseline net/win = **+6.897 (positive)**, av_stoikov
  +11.890 (Δ +4.993). EVERY variant scores +6.9..+14.4/win. But live realized box P&L on 07-13 was
  flat-to-negative and live markout was −2.17. **The paper scores a losing live baseline at +6.9.**
  "Never negative on the day" always meant "beat baseline," never "made money."
- **Markout ≠ settlement.** Markout is the 5-min mid move on a fill; the live box settles $0/$1 at
  15 min. A fill with good markout still becomes a negative-width box or a strand (LIVE-BLEED).
- **Simulated fill model.** The paper fills the strategy against the live book with an OPTIMISTIC
  model (fills the strategy wouldn't get live / at better prices) → systematic over-estimate for
  ALL variants (baseline included), which is exactly what "+6.9 baseline vs negative live" shows.
- **Rebate-inclusive / per-win units.** Not dollars.

THREE LIVE P&L METRICS THAT DON'T RECONCILE (3-day sums): markout −$10.44, box-mark(window_mark)
+$0.57, BALANCE −$3.49. None agrees with another or with the money. **We literally cannot measure
strategy P&L today.** ANSWER to the operator's questions: (1) not a data-COLLECTION error — the
data is captured fine; it's a METRIC-VALIDITY error (the scored metric is not realized P&L). (2) YES
realized is drastically different from estimated — opposite SIGN (estimated +7..+14/win, realized
negative). (3) av_stoikov isn't "broken"; it was never measured on realized dollars — its edge is
"beats an inflated phantom baseline on a markout proxy," which does not imply live profit.

CONSEQUENCE: every ranking built on the paper metric (av_stoikov, mo_size, the box_shadow arm
deltas, the whole STRATEGY SCOREBOARD) is SUSPECT in absolute terms and its ordering is unproven
against realized. FIX (the only way to "accurately test strategies"): score on REALIZED box
settlement P&L reconciled to the balance. Built realized_pnl.py (this cycle). MANDATE (added to
runbook): no strategy is a "winner" until it clears the gate on realized P&L, not markout/paper-mark.
Re-validate av_stoikov + all arms on realized before any deploy weight is placed on them.

## SIM-LIVE-GAP (2026-07-14, #1 GOAL: tested performance must match live performance)
Quantified box_shadow 'live' arm (the sim) vs actual live realized (winrec window_mark), 95 aligned
windows 07-12/07-13. VERDICT: the sim CANNOT predict live — and it's not a fixable offset.
- OVERALL: sim −5.19c/win vs live −1.68c/win → bias −3.51c (sim too pessimistic); per-window
  corr **0.17**. A bias constant can't fix a 0.17 correlation.
- DETERMINISTIC (neither stranded, n=79, no settlement luck): sim −0.71c vs live **+1.30c** (live
  paired edge is POSITIVE, sim gets the sign wrong); per-window corr **0.036**. The sim fails on the
  DETERMINISTIC box economics — proof the FILL MODEL doesn't reproduce which quotes fill at what
  price (box cost is what it gets wrong). This is the core defect, not settlement luck.
- STRAND (n=16): sim −27c vs live −16c, corr −0.23. Settlement is a $0/$1 coin flip → irreducible.
- VARIANCE DECOMP: strand windows are 7% of windows but **54% of total P&L variance**. The signal
  (deterministic edge +1.3c, var 0.0033) is dwarfed by strand coin-flip noise (var 0.183). So both
  measurement AND prediction are luck-dominated.

WHY TESTED ≠ LIVE (root): (1) the fill model has ~zero correlation with actual fills → the sim's
box costs are fiction; (2) strand settlement variance (54%) is irreducible noise that no sim predicts
and that swamps the small edge, so aggregate P&L is a luck read over ~200 windows.

TWO LEVERS TO EARN CONFIDENCE (both required):
  A. CALIBRATE THE FILL MODEL against the live tape (order_lifecycle × fills × book context) so the
     sim reproduces actual box costs — validate: per-window corr(sim, live) on deterministic windows
     rises from 0.036 toward >0.5 and bias → 0. Until then no sim number is trustworthy.
  B. ELIMINATE STRANDS to remove the 54%-of-variance coin-flip. With strands gone, live P&L ≈ the
     deterministic paired edge (+1.3c, low-variance, measurable), which a calibrated sim CAN predict.
     (This re-frames the disposal stack: its value isn't just EV, it's making the system MEASURABLE.)
NEXT: build the fill-model calibration harness (lever A) — fit P(fill|book,quote-position) to the
live order/fill tape, re-run box_shadow with it, and re-measure corr + bias vs live. That harness IS
the confidence gate: a strategy's tested number is only trusted once the sim predicts the balance.

## SIM-LIVE-GAP-2 (2026-07-14, confirmation pass — "be absolutely sure before building")
Three independent evidence chains converge; diagnosis CONFIRMED at the mechanism level:
- P&L: per-box (normalized, deterministic windows n=42) corr(sim,live)=0.077; live realized/box
  clusters at +1c (26/42 windows) while sim's mode is −4c/box. Live wins small and consistently;
  the sim thinks the typical box loses.
- FILL: aligned first-fills (07-13, 32 windows): sim matches live's actual first fill on SIDE only
  50% (chance), median |price gap| 11.5c, timing +55s late. The sim replays different events.
- ORDER (prior fillcal study, 618 real placements vs tape): OPT rule (what box_shadow uses) F1=0.56
  — misses ~half of real fills; misses concentrate in orders living < the tape's ~1.2s sampling gap;
  a 1-param calibration grid COLLAPSES back to OPT on both folds. Within the 1.2s tape, the fill
  model is UNFIXABLE — tape resolution is the binding constraint (this is what P1 hires solves).
- METRIC bonus: live fills have NEGATIVE 60s markout (−2.6c) while the same fills realize +1c/box —
  markout is anti-correlated with completion-based box P&L. Second, independent kill of the
  markout-based av_stoikov validation.
VERDICT: the gap is the fill model + tape resolution. Consequences: (1) all box_shadow ABSOLUTE
EVs are fiction; deltas between arms sharing the same fill path are weaker-poisoned but unproven.
(2) Quote-changing strategy testing (price-cap, back2, av_stoikov family) is BLOCKED until a
hires-tape fill model exists (~07-18, node P1). (3) Entry-VETO arms don't need a fill model at all
— they only REMOVE windows whose realized P&L we KNOW. BUILD: live-anchored counterfactual scorer
(live_anchor.py) — scores veto arms against actual live realized outcomes; sim=live by construction.
This is the only strategy-testing path that satisfies the #1 goal TODAY.

## LIVE-ANCHOR (2026-07-14, built — the tested==live scorer, and its first verdict)
live_anchor.py scores entry-veto arms against ACTUAL live realized P&L (paired→window_mark,
strand→net_final): tested==live by construction, no fill model involved. First run (07-12..14,
108 windows, realized +$1.57):
  volgate  veto 28 → kept −$0.31 (delta −$1.88, vol-match p=0.79)
  nsmove   veto 26 → kept −$0.21 (delta −$1.78, p=0.79)
  thickbook veto 9 → kept −$0.51 (delta −$2.08, p=0.95)
  c3_share veto 7 → kept −$0.81 (delta −$2.38, p=0.99)
❗ ON REAL MONEY, EVERY VETO ARM HURTS: each removes windows that were BETTER than random
(p 0.79–0.99 = their removals cost more than random removals). The replay said +1–2c/win because
its fictional baseline made typical windows look like −5c losers worth skipping; in reality windows
average +1.5c and skipping them burns realized profit. The sim-live gap, caught in the act.
CAVEATS: 3 days / 108 windows, strand variance in kept sets, feature parity with box_shadow is
approximate (fills-derived depth/vol vs tape-derived). Not a kill — a REBASE: the 07-24 promotion
gate for veto arms must be judged on live_anchor realized deltas, NOT box_shadow locked deltas.
An arm that passes the fictional gate but fails the realized gate does not deploy. Runbook updated.

## EXEC-FAIL (2026-07-14, /goal find-a-winning-strategy — ROOT CAUSE OF THE LOSS TAIL FOUND)
Traced TRUE realized P&L (settlement-based, reconciled to balance within $0.99 — net_final is a
SIGNED POSITION not cash; realized = n_boxes + naked_payout(resolved_up) − cost) down to the order
log. **The execution layer silently fails: 115 rejected orders in 2 days (07-13/14):**
- **F14 flatten: fires correctly, venue refuses it.** 60/60 fractional count_fp orders → HTTP 400
  "invalid order", ALL in the final 45s (the flatten zone). Only success sets frac_flatten_used, so
  it retries and reports 0 fires. Response body not logged → cannot yet tell malformed-format vs
  fractional-orders-not-allowed.
- **Completion/dispose crosses: SELF-CROSS rejections.** 41/55 integer rejects had OUR OWN resting
  opposite-side quote at a crossing price at reject time (Kalshi self-trade prevention). Exactly
  when completion matters most (near close, our quote near the touch), the cross bounces → market
  moves → later completion at adverse price (the −13c negative-width mode) or strand. The loss tail
  we chased at the strategy level is (at least substantially) an ORDER-REJECTION bug.
- TRUE-realized context: clean fully-covered windows are PROFITABLE (+$1.04/23, median +4c/win,
  75/103 positive); the tail (4 windows −$5.72, avg box cost up to $1.20-1.31 from churn) exceeds
  the entire net loss. Every naive tail-cut (cost-stop, overpay-halt, k-cap, price-cap-conservative,
  entry vetoes) FAILS honest realized testing — because the tail isn't a strategy flaw, it's broken
  execution.
**GOAL ANSWER: the winning profitable strategy = the CURRENT strategy, executed correctly.** Its
clean-execution economics are positive; its losses trace to silent 400s. FIX (built, flag-gated,
default-off, operator word to enable): (1) --cross-self-cancel: before a crossing dispose/complete/
flatten order, cancel own resting opposite-side orders that would self-cross; (2) unconditional
logging of the 400 response body (diagnostics; decides the count_fp question). Forward validation
after enable: rejects/day ↓, negative-width tail ↓, TRUE realized/window ↑ vs the reconciled baseline.

## ZERO-EDGE (2026-07-14, /goal find-a-winning-strategy — the honest bottom line; CORRECTS EXEC-FAIL)
Two of my own EXEC-FAIL claims are REFUTED by the discriminating tests I then ran (recording both,
per the do-not-fabricate rule this whole session established):
- SELF-CROSS causes rejects → REFUTED. Rejected orders self-cross 75%, FILLED orders self-cross 91%
  (the bot always has opposite quotes up). Self-cross does not cause the 400s.
- REJECTS cause the losses → REFUTED. corr(reject_count, realized)=0.053; the worst window (−$1.84)
  had ZERO rejects; worst 3 windows are all STRANDS. Do NOT build --cross-self-cancel.
What survives from EXEC-FAIL: 115 rejects/2d is real hygiene debt (60 fractional count_fp → F14
flatten silently failing; 55 integer rejects cause UNKNOWN). The reject-body `details` logging
(prepared, propose-only) is the right + only justified fix — it diagnoses without a behavior change.

TRUE realized decomposition (settlement-based, 103 windows, 2.1 days), THE bottom line:
- CLEAN paired boxes (n=96): mean **−0.0002/win**, sum −$0.02 — **BREAKEVEN. There is no width edge.**
- STRAND (n=7): mean −0.556/win, sum −$3.89, mean t vs 0 = −1.39 — **zero-mean coin-flips, unlucky.**
- The −$3.49 balance = negative strand variance on a ZERO-edge base. Not execution, not measurement,
  not a specific loss mode — the strategy simply has no realized edge.
WHY (mechanism): live markout is NEGATIVE (−$10.44/SIM-LIVE-GAP-2) = ADVERSE SELECTION. The bot
captures nominal quoted width but gives it all back to fills that precede adverse moves; net width
after adverse selection ≈ 0. This is also why every mechanical lever (vetoes/price-cap/k-cap/
cost-stop) FAILS realized testing — you cannot re-slice a zero-mean process into profit.

GOAL VERDICT — HONEST: **we do NOT have a demonstrated winning profitable strategy.** The current
approach is zero-edge; "days to confirm profitability at t=2" = ∞ because the true mean is ~0. A real
edge must come from REDUCING ADVERSE SELECTION — wider quoting (buffer vs the leg1→leg2 move) or
faster/smarter quoting (avoid toxic fills). BOTH are quote-changing → require a calibrated fill model
to test honestly (hires tape, node P1, ~07-18). Until then, no honest test can produce a winner, and
manufacturing one would be the av_stoikov error again. The deliverable toward the goal is therefore:
(1) this rigorous zero-edge finding; (2) the fill-model harness as the prerequisite; (3) the
adverse-selection-reduction hypotheses (quote-width, latency) queued for when it exists.

## ZERO-EDGE-CONFIRM (2026-07-14, rebate check — closes the last "hidden income" hope)
Checked for maker rebate income (the balance was $0.40 better than winrec-realized; the old paper
metric was "rebate-inclusive"). RESULT: NO rebate. 866 maker fills = $0.000 fee AND $0.000 rebate;
22 taker fills = −$0.571 total. fee_reported has ZERO negative (credit) values. The winrec↔balance
$0.40 gap is unresolved-settlement/open-position accounting, NOT income. Kalshi 15m pays makers
nothing and charges takers only. So the strategy is zero-edge MINUS a small taker-fee drag =
slightly NEGATIVE EV. Exhaustive honest search now complete — clean-edge zero, strands zero-mean,
no rebate, every window-level lever fails realized OOS. A positive edge is NOT discoverable in the
current window-level data; it must come from sub-window quoting (adverse-selection reduction),
which requires the calibrated fill model (hires tape, ~07-18). INTERIM decision-theoretic note (for
the operator; de-risking = rail-1 exception, operator's call): given proven EV<=0, minimizing size
or pausing until an edge is demonstrated PRESERVES capital vs a guaranteed slow bleed — the only
"winning" (loss-minimizing) move available before the fill model exists.

## ADV-SELECT (2026-07-14, /goal — the identified candidate winning strategy + the honest ceiling)
Found the strongest mechanism-grounded lead: ADVERSE SELECTION BY QUOTE STALENESS. Fill-level live
markout (3467 fills): fills that rest <1s before filling = markout +$1.77; fills resting >=1s =
−$3.45. Textbook microstructure: a quote that sits gets filled BECAUSE the market moved to it
(sniped by informed flow); a fast fill is uninformed. Median resting = 0.80s; 17% of fills rest >2s
and carry the loss. This is WHY the strategy is zero-edge (ZERO-EDGE) and why markout is negative
(SIM-LIVE-GAP-2): the bot's quotes are stale-sniped.
THE CANDIDATE WINNING STRATEGY: anti-staleness quoting — cancel/reprice a quote BEFORE it rests long
enough to be picked off (shorter --order-ttl-s and/or cancel-on-spot-move), keeping the profitable
fast-fill flow and shedding the slow-fill adverse selection. Grounded in real microstructure, not a
statistical fluke. The bot already logs resting_s and reprices on a ~1.2s heartbeat, so this is a
threshold change (propose-only, rail 1).
HONEST CEILING: the fast/slow split does NOT survive 07-12/13 → 07-14 train/test (fast-only markout:
TRAIN +$4.1 improvement, TEST −$0.7 — flips). 3 days is too thin to VALIDATE any edge; ~15 candidates
tested this session ALL fail OOS, which is the expected behavior of train/test on a near-efficient
process with tiny data. So anti-staleness is the #1 HYPOTHESIS (mechanism + strong in-sample), NOT a
validated winner. Further slicing of these 3 days is p-hacking and risks manufacturing a false
positive — declined. VALIDATION PATH (the honest way to a confirmed winner): (a) measure the
fast/slow markout split daily as data accumulates — if the >1s-fill adverse selection is stable over
~2 weeks, the anti-staleness edge is real; (b) OR test it on the hires sub-second tape (~07-18) where
staleness is directly observable. Deploy proposal (operator, propose-only): tighten --order-ttl-s /
add cancel-on-spot-move; forward-validate that it shifts fills toward <1s and lifts realized.

## NO-EDGE-DEFINITIVE (2026-07-14, /goal — the complete-data verdict)
Pooled ALL available live realized (settlement-reconciled): 06-13, 06-14, 07-12, 07-13, 07-14 =
139 windows / 5 days. Per-day sums: +1.96, −2.85, −0.27, −1.52, −2.11. POOLED mean/win −0.0344,
per-window t=−1.23, **day-clustered t = −0.08** (5 days), 95% CI [−0.089, +0.020]. The current
strategy's realized edge is STATISTICALLY ZERO. This is the definitive answer to /goal: a "winning
profitable strategy" requires demonstrated t>2 POSITIVE realized edge; the complete data gives
t=−0.08. You cannot demonstrate profitability the data does not contain — this is a statistical fact,
not a research shortfall. Every alternative tested (~15) fails OOS on this sample; the best lead
(ADV-SELECT anti-staleness) is mechanism-grounded but flips OOS on 3 days. DEMONSTRATION is therefore
gated on one of: (a) deploying a candidate and accumulating weeks of realized data; (b) the hires
fill model (~07-18) to counterfactually test quote-changing candidates. No honest analysis of the
current 5 days can produce a demonstrated winner. Operator decision required — this is the terminal
state of what analysis alone can establish.

## ADV-STALE-CONFIG (2026-07-14, /goal — the candidate ROOT-CAUSED to a specific mis-tuned live flag)
The ADV-SELECT edge maps to a concrete, fixable config error. Live trader staleness protection:
  --requote-stale-s = 20.0  (drop a stale rung only after 20s + a mid move)
  --qtime-mp-margin = 0.0    (OFF: no microprice-divergence fast-cancel)
But ADV-SELECT shows fills get sniped at resting >=1-2s (fast <1s +$1.77 / slow >=1s -$3.45), and the
bot's OWN prior markout forensics (in-code, 2026-06-12) already found "fills on >15s-old quotes run
-2.04c/fill vs +0.79c fresh". So the live config re-quotes stale rungs an order of magnitude too
SLOWLY (20s vs the 1-2s sniping timescale) and the purpose-built fast-cancel is disabled. The entire
1-20s adverse-selection window is unprotected. This is the most likely single cause of the zero edge.
CANDIDATE WINNING STRATEGY, PACKAGED (deploy proposal — propose-only, rail 1, operator word):
  add to live.yml trader args:  --requote-stale-s 2  --qtime-mp-margin 0.01
  (tighten stale-requote 20s->2s to the sniping timescale; enable microprice fast-cancel)
HONEST STATUS: this is the identified + root-caused + packaged candidate, grounded in (a) ADV-SELECT
fill-level evidence, (b) the bot's own prior forensics, (c) a clear microstructure mechanism. It is
NOT yet a DEMONSTRATED winner — ADV-SELECT flips OOS on 3 days and the forensic support is markout-
based. DEMONSTRATION requires running it: forward-validate that it (1) shifts the fill distribution
toward <1s resting, (2) lifts realized/win vs the current zero-edge baseline over ~1-2 weeks (or
confirm on the hires tape ~07-18). This is the terminal analytical result: the winning-strategy
HYPOTHESIS is now a specific two-flag change with a mechanism and a forward test, awaiting operator
go-ahead. Analysis cannot demonstrate it further without live measurement.

## HIRES-ADVSELECT (2026-07-14, "wait + more research" — hires spot data WEAKENS the anti-staleness candidate)
Used the ms-resolution hires tape (07-14: 229k Coinbase spot ticks + full Kalshi books) to test the
ADV-SELECT sniping mechanism against TRUE spot, aligning 1761 of our fills to spot by ms timestamp.
RESULT: NO spot-driven adverse selection by fill speed. Spot markout (favorable=+) fast<1s vs slow>=1s:
  h=0.25s +0.000000/+0.000001 | 0.5s +0.000001/+0.000002 | 1s +0.000001/+0.000002 | 2s +0.000000/+0.000003
Slow fills are, if anything, very slightly POSITIVE post-fill (opposite of pickoff), and pre-fill
(the classic pickoff window) shows nothing. The Kalshi-`markout` fast/slow split (+$1.77/−$3.45) that
motivated ADV-SELECT does NOT reproduce on clean spot — and it already flipped OOS (train +$4.1/test
−$0.7). CONCLUSION: the "stale quotes get sniped by informed spot flow" story is NOT supported by the
best available data. The Kalshi-markout signal is book-microstructure noise, not spot-driven adverse
selection. DEEPER POINT: short-horizon markout (spot OR Kalshi) is (a) not robust and (b) IRRELEVANT
to realized P&L, which is settlement-driven (breakeven boxes + zero-mean strand coin-flips, 15-min
horizon). There is no markout-based fix because markout is not the P&L.
IMPACT ON ADV-STALE-CONFIG: the two-flag anti-staleness proposal is now WEAKLY supported, not the
confident candidate it looked like. Deploying it would likely change fill timing without lifting
realized edge (nothing to avoid). DO NOT present it as the likely winner. HONEST STANDING: current
strategy is edgeless (t=−0.08) AND the leading fix hypothesis is refuted by the hires data. A real
edge must come from capturing positive box width at ENTRY (a quoting/pricing question needing the
fill model + weeks) — not from quote-timing. Research has converged: no winning strategy is
discoverable OR mechanistically supported in the data available today.

## SPREAD-CAPTURE (2026-07-14, "more research" — the edge LOCATED precisely, grounded in measurement)
Hard-measured the theoretical edge and where it leaks. The bot is a double-maker: buy-YES@bid +
buy-NO@bid -> a completed box costs $1 − spread, so the EDGE IS THE SPREAD. Measured spread at our
3860 fills: mean 1.18c/box (median 1c, 84% at 1c). Theoretical prize if every box completed
double-maker: ~1.18c * ~730 boxes = ~$8.59/window. REALIZED clean-box ≈ 0 -> we capture ~NONE of it.
CRUCIALLY it is NOT lost to crossing (only 3.0% taker fills). It is lost to MAKER-CHASING: the bot
seeds wide (--seed-width 4c) but reprices the COMPLETING leg toward the ask to get filled, eroding
box cost from ~$0.96 back to ~$1.00. We give the spread away to complete.
THE HYPOTHESIS (best-grounded of the session): HOLD the completing quote FIRM at the target width
(the completing-leg price cap: never complete a box above $1 − w) instead of chasing. Then completed
boxes capture the full spread w (~1c), and the cost is MORE strands. The logic for why this is
positive-EV: strands are ~ZERO-MEAN (NO-EDGE-DEFINITIVE / t=−1.39). If hold-firm strands stay
zero-mean, expected edge = (completion_rate) * spread > 0 -- you capture ~1c on completions and the
extra strands don't cost in expectation. Expected realized ≈ p_complete * 1c/box, plausibly +$3-5/wk.
THE CATCH (why it needs the fill model): hold-firm may strand SELECTIVELY on adverse moves (you fail
to complete precisely when the market ran away), making hold-firm strands NEGATIVE-mean, not zero.
Whether the strand distribution stays zero-mean under hold-firm is THE question, and it is a
counterfactual (which fills would/wouldn't happen) -> needs the fill model (hires tape, ~07-18).
STATUS: this is a HYPOTHESIS with a real mechanism + hard measurement (spread=1.18c, 97% maker,
realized≈0), far better grounded than anti-staleness (refuted) — but NOT demonstrated; the strand-
neutrality assumption is unvalidated. This is the #1 thing to test with the fill model: simulate
hold-firm completion, measure the resulting strand-mean and net realized. If strands stay ~zero-mean,
this is the winning strategy. Supersedes ADV-STALE-CONFIG as the lead candidate.

## SPREAD-CAPTURE-REFUTED (2026-07-14, "more research" — WHY the edge is structurally zero; the complete answer)
Tested the hold-firm hypothesis directly: for 134 completed boxes, was the completing leg reachable
at the firm-width price (box cost <= 1 - 0.04)? RESULT: only 2/134 (1%). 99% of completions filled
~3-4c ABOVE firm (chased overshoot mean 0.038); actual mean box cost 1.0021 (~$1, zero width).
So hold-firm would have STRANDED 99% of currently-completed boxes — and stranded them SELECTIVELY on
adverse moves (you fail to complete precisely because the price ran away), making those strands
NEGATIVE-mean, not zero. Hold-firm is refuted; the completing-leg price cap does not capture the edge.
THE STRUCTURAL REASON (the complete answer to the whole investigation): a box maker legs in
SEQUENTIALLY, and leg-1 fills BECAUSE the price moved to your bid. The instant it fills, the price has
moved such that leg-2's width-bid is now off-market — so completing REQUIRES chasing the moved price
(99% of the time), which gives back exactly the spread you'd have captured. The ~1.18c spread is an
ILLUSION: it is precisely offset by the adverse price move implied by getting legged. This is why
clean-box realized is EXACTLY zero (NO-EDGE-DEFINITIVE) and why EVERY lever fails — the zero edge is
a STRUCTURAL property of sequential box-making on this market, not an execution or tuning flaw.
IMPLICATION FOR /goal: there is NO winning box-making strategy achievable by quoting/timing/completion
changes — all of them have now been refuted, and the mechanism explains why. The ONLY way to capture
the spread is to fill BOTH legs SIMULTANEOUSLY (before the price moves) = a SPEED/latency infrastructure
play (co-lo, sub-ms cancel-replace, the "millisecond sniper"), not a strategy. That is a capital+
engineering decision for the operator, outside what strategy research can deliver. The honest terminal
finding: box-making here is a structurally zero-edge game; the edge is only reachable via execution
SPEED, which is an infrastructure investment, not a strategy to be found in the data.

## LATENCY-ROI (2026-07-14, final research — even the speed escape hatch is marginal; investigation closed)
Tested whether execution speed could capture the spread SPREAD-CAPTURE-REFUTED said we chase away.
Measured completing-leg overshoot vs the leg-to-leg time-gap (134 box pairs). corr(gap, overshoot)
= +0.72 (waiting longer costs more -> speed helps directionally), BUT the level is ~instantaneous:
overshoot by gap bin: <0.5s +3.0c | 0.5-2s +3.2c | 2-10s +3.7c | >10s +3.5c. Even sub-0.5s
completions capture width 0% (0/27) and overshoot ~3c. So ~3c of adverse move is BAKED IN at the
instant of legging; only ~0.5c is time-dependent (recoverable by speed). CONCLUSION: speed
infrastructure recovers at most ~0.5c/box of the ~3-4c chase — a marginal improvement that does NOT
convert the structurally-zero-edge game into a clear winner. The adverse selection is in the fill
EVENT (you get legged because the price already moved), not in the reaction latency.
INVESTIGATION CLOSED. Every path is now exhausted with a mechanism, not just a null:
  - Strategy tactics (vetoes/price-cap/anti-staleness/hold-firm): REFUTED (legging is structurally adverse).
  - Speed/latency infrastructure: MARGINAL (adverse move is instantaneous, not latency-driven).
  - Other sleeves/markets: same sequential-legging structure, or paper-markout (proven untrustworthy).
DEFINITIVE ANSWER to /goal 'find a winning profitable strategy': for Kalshi short-dated binary
box-making, NONE exists that is demonstrable or mechanistically supported — the edge is structurally
zero (t=-0.08), every fix is refuted by the leg-in adverse-selection mechanism, and even speed
infra is marginal. The honest, complete, terminal finding. The realized-truth measurement framework
built this session (realized_pnl, live_anchor, the settlement reconciliation, the hires analyses) is
the durable asset: it is what makes this a PROVEN negative instead of another markout-based illusion.

## ETH-NO-REALIZED (2026-07-14, closing the last data-existing lead)
Before accepting the terminal box-making verdict, chased the one remaining within-scope lead: the ETH
sleeve, which FORWARD_LEDGER flagged weak-positive (back2 +0.2-0.4c/win; pair 87.6%; 30% of fills at
2-3c) exactly where BTC is the toxic falsification control. Hypothesis: ETH's wider spread / thinner
book might exceed the chase cost that zeroes out BTC. RESULT: NOT TESTABLE ON REALIZED MONEY. ETH was
never traded live -- origin/live-state carries BTC only (winrec/recon/metrics/fees all *_btc15m). The
ETH "metrics" on gha-data are paper box_policy_ab job logs (many are sklearn-ImportError tracebacks),
not settlement records, and the only ETH P&L signal (back2) is quote-CHANGING -> it lives on the
box_shadow fill model, which SIM-LIVE-GAP proved has ~0 correlation (0.036) with live realized. So the
ETH edge is UNFALSIFIABLE with existing data -- the same wall as BTC, not a way around it. To become a
real lead ETH needs live paper/small-size collection (an operator data-collection decision), not more
analysis. CONCLUSION: the last existing-data lead is closed. Every path a strategy search can reach with
current data is now exhausted. Advancing the /goal requires NEW DATA or an INFRA decision (both the
operator's), not further autonomous analysis on what we have. Holding for operator direction; will not
fabricate a winner.

## PAIRED-ZERO-DECOMP (2026-07-14, cleanest single proof; kills positive-selection too)
Tested the one counterintuitive live-money angle left: live_anchor showed every ENTRY VETO HURTS realized
(kept EV < base $2.57), which means the windows vetoes REMOVE are better than average -> a positive-
SELECTION strategy ("trade ONLY thick-book / high-depth-share / high-vol windows") might be the hidden
winner. Decomposed the realized to find out. RESULT -- it is 100% strand luck, not edge:
  - PAIRED boxes (real box economics): +$0.16 over 148 windows = +0.1c/window == EXACTLY ZERO. Independent
    confirmation of NO-EDGE-DEFINITIVE / t=-0.08, from raw decomposition with no model.
  - STRANDS (naked-leg coin flips, +-$1-2 each): +$2.43 over just 16 windows. The ENTIRE apparent +$2.57
    "profit" is 16 strands that happened to settle up. +$2.43 over 16 Bernoulli legs is well inside the
    +-$4-5 noise band -- could as easily be -$2.43. Top-12 windows by realized are ALL stranded.
  - So "thick-book/c3_share removes the profitable windows" was an ARTIFACT: those windows stranded and got
    lucky. Positive-selection on them = selecting high-variance coin flips that won IN-SAMPLE; zero forward
    value (a strand is zero-mean by construction). Confirmed: NO real positive subset exists.
TRIANGULATED NULL now from THREE independent angles: (1) mechanism (leg-in adverse selection),
(2) aggregate realized day-clustered t=-0.08, (3) this paired/strand decomposition (paired = +0.1c/win).
ALTERNATIVE STRATEGY FAMILIES also closed this session: directional 15m-settlement forecasting is NOT
testable (no strike/settled_up recorded in telemetry; and 15m BTC direction is a near-martingale a 2c
spread cannot beat) and ETH is unfalsifiable (ETH-NO-REALIZED). CONCLUSION stands, now maximally hardened:
no winning profitable strategy exists in the current data or instrument -- the paired edge is zero to 0.1c
and the only P&L is strand variance. A real winner requires a structurally different instrument/edge and
NEW data to test it on; it cannot be manufactured from what we have without fabricating.

## FAVLONG (2026-07-14, THE FIRST VALIDATED POSITIVE EDGE -- found by falsification, not fabrication)
After proving box-making structurally zero-edge (PAIRED-ZERO-DECOMP) and closing every box tactic,
turned to a STRUCTURALLY DIFFERENT strategy family using the powered gha-data tick archive (35 days,
btc/eth/sol, ~2800 windows/asset, tuple [t,mid,spot,micro,bid,bidq,ask,askq] for the 'up' contract).
FINDING: a near-expiry CONTRARIAN TAKER edge -- in the last ~2-3 min the Kalshi 15m book is
OVER-CONFIDENT (favorite-longshot bias): underdog contracts priced ~0.09 settle ITM ~0.32. Compute
fair-value P(up) from spot-vs-strike scaled by CAUSAL realized vol and shrinking tau; TAKE the side
the book underprices.
FALSIFICATION BATTERY (this is why it is trusted where av_stoikov was not -- built on SETTLEMENT):
  - reconstruction validated: mid@open 0.493+-0.082 (strike~=open spot), up-rate 0.498, proxy-vs-
    market-terminal settlement agree 92.5%.
  - LABEL ARTIFACT caught + removed: using our proxy strike for BOTH fair-value and outcome inflated
    t 6.64. Switching outcome to the MARKET's own terminal price (mid_close>0.5) and dropping proxy!=
    market windows cut it to the honest core: mean 0.046/ct, t=3.45 (btc OOS).
  - +Kalshi fees (0.07*p*(1-p)/ct): -> 0.039/ct, t=2.97 (btc OOS).
  - +fill LATENCY (execute up to 10 ticks later): t stays ~3.0 -> NOT stale-quote picking.
  - EXECUTABLE SIZE: traded (underdog) side depth median 420 contracts; 84% of trades >=50 avail;
    sized <=50 ct/window = +$937 OOS/14d (~$67/day), daily-$ clustered t=2.34.
  - CROSS-ASSET REPLICATION (the clincher): same sign btc/eth/sol independently. POOLED per-(asset,
    day) clustered t=3.99 over 105 asset-days, 65/105 positive. btc ALL t=3.25, eth 1.84, sol 1.77.
HONEST CAVEATS: small (~2c/ct pooled, ~4c btc); per-asset only BTC clears t>=2 OOS (eth 1.68 sol
0.55) -- confidence rests on pooling the shared mechanism + all-period positivity; concentrated in
last 2-3 min (t<=450s edge ~0); ~62% asset-days positive (real variance); it is a TAKER (crosses
spread) so needs NEW execution, not the maker box bot; favorite-longshot is a known effect that can
decay. Tool: favlongshot_edge.py (durable, committed). Registered in FORWARD_LEDGER.
VERDICT: this is a GENUINE winning candidate -- the first that survives realized-settlement scrutiny,
fees, latency, size, AND out-of-sample cross-asset replication. NOT box-making. PROPOSE-ONLY to live
(Rail 1): forward-gate (day-clustered t>=2 over >=10 FORWARD days) is required before any live sizing;
no switch/size/flag is touched without the operator's explicit word.

## LIVE-HALT (2026-07-15, operator-authorized) — box-maker stopped
Operator explicitly authorized halting live trading until a strategy is PROVEN profitable ("stop it,
don't start it until we prove a strategy to be profitable"). Set LIVE_SWITCH=off on branch
claude/polymarket-bot-live-ready-vw7ut5 (commit 024f57693); confirmed remote=off. The live-trade
GHA workflow gates fail-closed on this file + the kill sentinel, so the bot goes inert at its next
~25-min gate check and each self-chained leg re-reads it. Rationale: box-making is structurally
zero-edge (NO-EDGE-DEFINITIVE / PAIRED-ZERO-DECOMP) and the live account bled -$4.92 real balance
over the prior ~2.5 days while telemetry claimed +$3.23 (the ~$8 window-mark overstatement).
Do NOT re-arm until a candidate clears its forward gate AND the operator flips it back on.

## FAVLONG follow-up research (2026-07-15) — sharpened, RE-CHARACTERIZED, and one framing RETRACTED
Four delegated agents + independent verification. Net: the edge is REAL and materially IMPROVED, but
the original mechanism story was wrong and is corrected.

FAVLONG-MECHANISM: WHY/persist/cannibalization. No decay on the 35-day archive (per-day edge vs date
slope t=1.1, insignificant; late-half >= early-half). Edge concentrates in WIDE/dislocated books
(spread>1c ~+3.6c/ct vs tight <=1c ~+0.5c) and MID realized-vol days (t=4.07). In the TIGHT-AND-DEEP
book (the box-maker footprint) edge ~ZERO (-0.0003, n=889) => box-maker cannibalization LOW; strategies
complementary. Persistence risk MEDIUM (small, variance-heavy, known-arbitrageable). HONESTY: agent
could not reproduce the "0.09->0.32" headline; retracted (see below).

FAVLONG-XRP-NULL: the edge does NOT replicate on XRP (full-sample t=-1.35, OOS t=-0.32). Adding xrp
dilutes the pool (OOS t 3.03->2.63). The effect is asset-specific (btc/eth/sol), NOT a universal
crypto-binary bias. XRP excluded from the tradeable universe and the forward gate.

FAVLONG-SEGMENT: 38 segments, train-selected + single OOS look. Only MONEYNESS concentrates the edge:
deep-underdog (<0.15, ~62% of trades) has NO OOS edge (t=1.04); the profit is on the NEAR-ATM-TO-
FAVORITE side — favorite>=0.60 OOS t=2.24, near-ATM(0.40-0.60) OOS t=2.63, union entry>=0.40 (post-hoc)
OOS +0.136/ct t=4.06 (~6x pooled mean/ct). Depth/vol/time-of-day: no OOS-robust segment. => the
"buy the cheap longshot" framing (original FAVLONG headline) is REFUTED; retained id 'FAVLONG' is a
misnomer — it's a dislocated-book repricing-lag captured on the richer side.

FAVLONG-MODELV2: the raw Gaussian fair-value mis-shapes the 0.2-0.5 band. An EMPIRICAL ISOTONIC
calibration (fit model_fairP->empirical P(up) on TRAIN pooled, applied to TEST; leak-checked: fit on
train rows only, per-asset t=7.72 ~= pooled 7.70 so not a pooling artifact) ~DOUBLES the backtested
edge: OOS pooled day-clustered t 3.97 -> 7.70 (sklearn isotonic), mean +$0.059/ct, 36/42 positive
asset-days, all three assets clear t>=2 OOS for the first time (btc 5.58, eth 3.84, sol 4.09). NOTE:
the forward harness uses a STDLIB-BUCKET map (GHA has no sklearn), reproducing OOS pooled t=5.74
(btc 4.24 eth 2.87 sol 2.87, +$0.051/ct) -- 5.74 is the honest forward-tracked prior, not 7.70.
Verified independently via favlong_forward.py --acceptance. All 8 iso
variants beat all 16 raw variants on test; 24-config Bonferroni still overwhelming. Tool favlong_model_v2.py.
CAVEAT: the isotonic map is a FITTED component (21 train days) that can decay -> needs periodic refit;
forward gate still mandatory. RECOMMEND forward-tracking the calibrated model (pre-registered now, before
any forward data exists, so ungameable) alongside the raw as control.

F14-FIX (propose-only): the fractional-flattener never fires because the bot-branch live.yml omits
'--flatten-fractional 0.1' from the trader invocation, so a.flatten_fractional defaults 0.0 and the
guard (kalshi_trader.py ~L3789, flatten_fractional>0) is always False. Not a logic bug, a not-wired
flag. Fix = add the flag to the live.yml trader command. NOT applied (bot is halted; live change =
propose-only). See F14_FLATTEN_BUG.md.

## FAVLONG-SECOND-EDGE-NULL (2026-07-15) — no independent second edge (rigorous null)
Hunted a second settlement-validated edge distinct from FAVLONG: (1) book imbalance, (2) binary-mid
momentum/reversion, (3) vol-risk-premium, (4) cross-asset lead-lag. 186 configs, train-select/test-
confirm, realized labels + fees + executable spread-crossing + day-clustered t. ALL NULL (OOS net t:
-1.18 / -0.25 / -0.51 / -1.37; none even positive on train net). Finding: the MID-window is efficient
for a TAKER — imbalance & short-horizon momentum carry a real but tiny GROSS signal (~1-2.4c/ct) that
is <= the spread+fee, so net collapses to ~0 / negative OOS. This CORROBORATES FAVLONG from two sides:
its terminal-window overconfidence is the one gross edge large enough to clear costs, and candidate-3
confirms the fair-value model has ~zero predictive value BEFORE the last few minutes (genuine terminal-
convergence effect, not a whole-window artifact). Report: favlong_second_edge_report.md.

## NO-OTHER-EDGE sweep (2026-07-15) — 8 sleeves audited + 2 new hypotheses tested; FAVLONG stands alone
Answering "does any OTHER strategy have a clear edge?" — delegated 6 agents, all judged on REALIZED
settlement (not self-metrics). Result: NO. FAVLONG remains the ONLY validated edge.
EXISTING SLEEVES (all NO edge): longshot (15 bets/3d t=0.84) + tailbias (19/3d t=0.87) = underpowered
noise; weather-CLV = CLV-ILLUSION (CLV +49 but realized -11.84, 10% win); sports-CLV = no data (API key
unset); macro = no settlement recorded; etf = 2wk noise; kxwti = no settlement recorded; boxwide =
mark-ILLUSION (realized -1.27c vs mark +0.27c, does not escape adverse legging). SYSTEMIC: most sleeves
log PROXIES (CLV/mark/pre-entry edge) and never record settlement; the two that do (weather, boxwide)
lose real money. Reports: audit_longshot_tailbias / audit_weather_sports_clv / audit_macro_etf_kxwti /
audit_boxwide .md.
NEW HYPOTHESES (both fail to add a winner):
- POLYMARKET btc up/down (5-min up-from-open, tight ~1c + deep): FAVLONG mechanism is NULL/NEGATIVE
  (full-sample t=-4.22, OOS t=-2.24, even at ZERO fees). An apparent +5.69 was a MARKOUT ILLUSION (scored
  vs a Kalshi-spot-derived label sharing the fair-value feed; flips to -3.43 under real Polymarket
  settlement). Cross-venue arb not clean (5m vs 15m, up-from-open vs fixed-strike don't align). This is a
  POSITIVE confirmation of the mechanism: tight/deep books are efficient; FAVLONG lives only in WIDE/
  dislocated books. Report: newedge_polymarket.md.
- FAVLONG refinements (dislocation-conditioning, window-extension, favorite tilt): no upgrade. Wide-spread
  filter collapses pooled t (calibration already absorbs the wide-book premium); window does NOT extend
  before ~600s; favorite>=0.60 tilt gives +28% $/ct but lower pooled t (fewer trades) -> optional SIZING
  lever only. FAVLONG is near its ceiling on this data. Report: newedge_favlong_refine.md.
CONCLUSION: after auditing every existing sleeve and testing the two best-grounded new bets, FAVLONG
(near-expiry taker, wide-book repricing lag, btc/eth/sol, calibrated OOS t~5.74) is the sole demonstrable
edge. Everything else is null/illusion/insufficient. Forward gate (~07-25) remains the arbiter; all
propose-only. The favorite>=0.60 sizing tilt is the one usable add-on.

## ORTHOSTACK sweep (2026-07-15) — 3 orthogonal candidates on existing data; none is a clean diversifier
Sought return streams uncorrelated with FAVLONG to STACK (raise combined Sharpe). Each scored on realized
settlement, day-clustered, OOS, + per-window/day correlation with FAVLONG.
- SHOCK-REVERSION (fade a sharp mid-window spot move): NULL. Settlement OOS t=0.29; round-trip t=-2.02
  (costs>alpha). Orthogonal (r~0) but no edge -> no value.
- TIGHT-BOOK single-sided MAKER (complement regime): NULL. OOS t=0.52; adverse selection 61-64% correct
  (need >=75% vs fees) -- pick-off trap. Confirms tight books efficient; double-sided just re-derives the
  dead box-maker.
- CROSS-SECTIONAL RV (beta-neutral btc/eth/sol laggard-vs-peers): MARGINAL/underpowered. OOS t=1.33
  (dt=600), +0.138/ct, 57 trades/13d -- below the t>=2 bar. AND daily corr with FAVLONG = +0.53
  (complementary, NOT orthogonal) so limited diversification; per-window r~-0.06. Reports:
  orthostack_shock_reversion / orthostack_tightbook_maker / orthostack_xsectional_rv .md.
CONCLUSION: no clean orthogonal diversifier exists in the current Kalshi-15m data. XS-RV is the only
non-dead one but is underpowered + correlated; parked as a low-priority forward watch, not crowned.
NEXT ORTHOGONAL AVENUE: perp-based edges on Kalshi (carry/basis) -- a genuinely different return driver
(carry, not repricing). Operator confirmed perps run on Kalshi; no perp data collected yet -> building a
collector to start collect-then-forward-validate (all 3 shapes: perp<->binary basis, funding carry,
perp<->spot basis).

## CAPACITY-CAP (2026-07-15) — FAVLONG is REAL but SMALL-CAPACITY; the strategy must be a STACK
Realistic capacity + sizing study (favlong_capacity_sizing.md). KEY FINDING: FAVLONG's earnings are
HARD-CAPPED BY NEAR-EXPIRY BOOK DEPTH, not by capital. After a market-impact haircut the tradeable
size is ~50-100 contracts/window, so the capacity ceiling is a ~$200-400 EFFECTIVE position REGARDLESS
of bankroll (more capital just increases impact, doesn't earn more). Resulting P&L ceiling ~a few $/day
(~$50-150/month at best). At the current ~$56 balance: ~cents/day (~$0.50/month) << operational
overhead -> VALIDATION-ONLY, not worth live-deploying for profit. Becomes marginally worth it only
near the depth-capped ceiling (~$400 effective, ~$45-110/month) IF the forward gate confirms t>=2.
(Numbers are estimates from a haiku pass; the QUALITATIVE result -- depth-capped, small -- is robust:
edge ~2-6c/ct x ~50-100 ct x ~10 trades/day.)
STRATEGIC REFRAME: no single edge in this arena scales. Meaningful P&L requires a STACK of many small,
uncorrelated, capacity-capped edges. This VALIDATES the orthogonal/perp/other-tenor program as the core
strategy, not a side quest -- FAVLONG alone is a trickle. Portfolio construction (many small edges,
low mutual correlation, each depth-capped) is the goal. Also informs: consider funding the account only
once a STACK exists, since one edge at $56 earns cents.

## PERP-COLLECTOR-LIVE (2026-07-15) — Kalshi perps confirmed real; read-only collector deployed
Operator confirmed perps run on Kalshi. Agent live-validated it: /margin/markets (public reads today)
lists 16 crypto perps (btc/eth/sol/xrp + link/ltc/doge/bch/dot/hbar/near/sui/xlm/zec/hype/kshib), each
exposing bid/ask/mid, index (BRTI reference_price), mark (settlement_mark_price), funding_rate +
next_funding_time, OI/volume/notional, contract_size (now 0.0001 BTC), full depth. Deployed a READ-ONLY,
discovery-driven collector (kalshi_perp_collect.py on the bot branch; kalshi-perp-collect.yml on main,
cron 1,21,41 self-chaining; data -> gha-data). GET-only, no order path, no LIVE_SWITCH/live.yml touch.
Co-collects the aligned 15m-binary YES mid for the perp<->binary basis. First CI run dumps the full raw
schema (registry_kalshi_perp). COLLECT-THEN-FORWARD-VALIDATE 3 paper edges (perp_strategy_design.md):
(a) perp<->binary basis [same-venue, cleanest], (b) funding carry, (c) perp<->spot basis -- each with a
FAVLONG-style gate (pooled per-(asset,day) t>=2 over >=10 fwd days, frozen params). PRIOR ART flagged:
PERPS_BACKTEST.md (Deribit carry) had ETH sign-reverse OOS -> per-asset (not just pooled) forward gating
mandated. Fits CAPACITY-CAP thesis: another small capacity-capped orthogonal sleeve for the stack.

## SETTLEMENT-BUG (2026-07-15) — why sleeves lacked settlement: a status-string bug (fix built)
Root cause of "sleeves log proxies, never settlement": a resolved Kalshi market reports
status=="finalized", NOT "settled". macro_paper.py (~L534) + kxwti_paper.py (~L291) gate their inline
settle blocks on status=="settled" -> never fires (that is why macro_settled.jsonl / kxwti_settled.csv
were never created), while longshot/tailbias check "finalized" and DID settle. Built settle_recorder.py:
reusable, stdlib-only, READ-ONLY; loads a sleeve's entry log, queries GET /markets/{ticker}, keys
resolution on result in {yes,no} (immune to the status-string trap), appends realized P&L per position to
<sleeve>_settled.jsonl (idempotent on ticker+entry_ts; per-sleeve fee/PnL conventions mirrored). Tested
offline (all 4 sleeves) + live (4/4 resolved w/ correct signed P&L). Markets are ALREADY finalized ->
one-time BACKFILL is possible NOW to re-audit macro/kxwti on realized money. Template wiring for
kxwti-paper provided (kxwti-paper.settle-step.yml.snippet). PROPOSAL (not yet wired live): drop the
settle step into kxwti/macro workflows -> those sleeves become validatable like FAVLONG. Plan:
SETTLEMENT_LOGGING_PLAN.md.

## OTHER-TENOR (2026-07-15) — hourly crypto FAVLONG: no transfer at candle resolution, but UNDERPOWERED/confounded
No stored non-15m Kalshi time-series exists (gha-data is 15m-crypto only; hires is still 15m BTC; the
bot-branch kalshi_hourly_box_backtest.py / kalshi_econ.py hit live API / a parquet not in the branch).
Agent reconstructed a LIVE test on hourly directional KXBTCD/ETHD/XRPD from public minute candlesticks
(yes_bid/yes_ask + result/expiration_value/floor_strike) with Binance-vision spot for fair value.
DISLOCATION PRECONDITION HOLDS: hourly near-expiry ATM books are WIDE (p50 1c, p90 2-3c, 29% of
near-expiry minutes >1c) -- wider than 15m, clearly not Polymarket-tight. BUT the edge does NOT transfer:
18 cells (3 assets x 3 edges x 2 decision times) all pooled <=0, day-clustered t -1.1..-1.7, 12-18% win;
BTC alone ~0 insignificant. HEAVY CAVEATS -> this is a WEAK null, not a kill: underpowered (5-6 days,
66-86 windows, 7-10 clusters) and confounded by (a) 1-min-candle executable prices vs the SUB-SECOND
top-of-book FAVLONG actually trades, (b) Binance-vs-Kalshi index basis. A fair test needs a forward
COLLECT: sub-second top-of-book for the final ~5 min of KXBTCD/ETHD/SOLD, mirroring the 15m tick schema,
>=15 days. Parked with no live-sizeable signal until then. Report: newmarket_favlong_tenor.md.

## CANDIDATES-3 + 15m-SCOPE (2026-07-15) — /goal 3 candidates all NULL; scope locked to liquid 15m crypto
/goal "find 3 candidates orthogonal to FAVLONG, validatable on our/accessible data". Found + validated 3;
NONE is a usable edge, and the operator's 15m-liquidity constraint rules out the non-15m ones regardless:
- LADDER NO-ARB (arb family): NULL. 59,640 archive poll cycles + live snapshots; violations exist at MID
  but never at executable prices (inside spread / empty-book phantoms); live full-ladder snapshot = 0
  crossable; realized locked-arb $0.00. Multi-strike (non-15m) -> out of scope anyway. cand_ladder_noarb.md
- EVENT-VOL PREMIUM (vol family): INSUFFICIENT-DATA / point-estimate no-edge. n=7 events (API serves ~3
  recent monthly/series); implied~=realized move (ratio 1.005), premium ~0 gross, slightly neg net. Econ
  (non-15m) -> out of scope. cand_event_vol.md
- CROSS-FAMILY CALIBRATION (behavioral): NULL across all 6 families. 323 snapshots; deep tails (75% of
  markets) perfectly calibrated (0.007->0.006, 0.989->0.986); the eye-catching +0.058/ct t=5.99 was a
  ZERO-LOSS BOUNDARY ILLUSION (all 19 resolved NO; favorite side flat/neg) -- same illusion already ruled
  null for longshot/tailbias. crypto_15m + econ INSUFFICIENT (1-3 days). No exploitable home. cand_xfamily_calibration.md
OPERATOR SCOPE (2026-07-15): keep strategies constrained to LIQUID 15m crypto binaries (btc/eth/sol) --
FAVLONG's capacity study already showed depth is the binding limit, so less-liquid Kalshi markets are
strictly worse. Within 15m the space is heavily fished: FAVLONG (win) + second-edge nulls (imbalance/
momentum/VRP/lead-lag) + orthogonal sweep (reversion/maker null, XS-RV marginal+correlated) + refinements
(no upgrade). The ONE in-scope orthogonal avenue remaining = PERP<->15m-BINARY BASIS (operator confirmed
in scope; perp collector deployed, data pending). DIRECTION: build the perp-basis paper strategy once perp
data lands (collect-then-forward). Honest: the 15m pond may support only ~1-2 edges; the "stack" is thin.

## FINGERPRINT (2026-07-15) — participant behavioral fingerprint; FAVLONG decay early-warning + whale-informed flag
Behaviorally fingerprinted non-us participants (Kalshi anonymous + aggregated depth -> SIGNATURES only,
no actor IDs/count; "concentration" a weak proxy). Data: deduped trades, 1.2s ticks, our fills subtracted;
35 days fills, 12 days heavy book/trades. KEY FINDINGS:
- NAIVE-DOMINATED near-expiry: aggressor flow fat-tailed (median sweep 12-28ct, single-level); a RARE
  INFORMED WHALE tail (>5000ct, 11 fills, markout-to-settlement -0.083) -- i.e. LARGE trades ARE informed
  but rare. Actionable: FAVLONG "whale stand-down" regime flag (don't take when a whale sweeps).
- FAVLONG FEED IS EXTERNAL: our box-maker executed only ~0.6-1.0% of near-expiry volume -> turning it OFF
  is a <=1% ecosystem change; forward ~= archive for the feed (box-maker-off concern is minor).
- DECAY EARLY-WARNING (most important): even with FLAT backtest P&L slope, the counterparty is measurably
  WISING UP -- near-expiry reprice latency FALLING (median t=-7.45, stale-tail p90 t=-2.61), inside depth
  RISING (t=+2.50), spreads not yet tightening. The stale-quote lag that IS FAVLONG's edge is eroding
  FASTER than P&L reveals -> add a forward TRIPWIRE on reprice-latency-p90 / inside-depth to catch decay
  before it hits P&L. (Moderate confidence: 12-day regression, characterization not proof.)
- ASSET DURABILITY: btc feed deep/fast/many-sourced (most durable); sol slow/wide/stale but thin/round-lot
  (most fragile, thinnest capture); eth intermediate -> btc-weighted sizing.
ACTIONABLE FAVLONG ENHANCEMENTS (propose-only, forward-gate-first): staleness entry filter (inside quote
unchanged >=2-3 ticks AND spread>1c), whale stand-down, btc-weight sizing, latency/depth decay tripwire.
Report: participant_fingerprint.md. (The whale-informed finding feeds the separate informed-large-flow
edge test now running.)

## PLAYER-REID (2026-07-15) — re-identify+follow recurring winning players: NULL + INFEASIBLE on this feed
Operator hypothesis: fingerprint recurring players by repeatable signatures, backtest each one's win rate,
follow the persistent winners. VERDICT: NULL, and the re-ID premise is INFEASIBLE on the Kalshi public feed.
- The 15m trade tape exposes only an anonymous per-print UUID (tid), ms exchange ts, ws/side/price/size,
  always the 'up' leg -- NO account/order id. Only persistence-capable handles = exact size + sub-second
  phase, and they FAIL as actor fingerprints: each recurring odd-size cohort is ~50/50 buy/sell, active
  20-21/24h, all price bands, timing-phase resultant R~=0.01-0.11 (uniform, no bot cadence) -> a size does
  NOT carry one player. Re-ID confidence LOW by construction.
- Rigor: 14 days across the train/test wall, 4.50M trades, 1,027 settled windows; each exact size = a
  "synthetic player", 1,115 cohorts screened (multiple-testing count). 13/1,115 in-sample winners (train
  day-clustered t>=2) -- at/BELOW the ~25-41 false positives expected by chance -- and 0/13 reached OOS
  t>=2 (only 2/13 even stayed positive OOS vs ~6.5 by coin flip). No OOS-winning player, no positive
  follow t/mean.
- Baselines: whale (>=5000ct) follow/fade flips sign train->test (train t=-2.64, test t=-0.61, never sig);
  all-flow aggressor loses to fees on 0/21 test asset-days (efficient tape); FAVLONG-shaped proxy null
  (test -0.034); correlation of spurious train-winners with FAVLONG small/mixed (-0.27..+0.32) = no linkage.
CONCLUSION: player re-ID is not feasible on the public feed (no IDs; size/timing don't isolate actors), and
the tape is efficient -- nothing persistent to follow. The rare informed-whale FINGERPRINT signal remains
only as a FAVLONG stand-down FILTER, not a standalone followable edge. Report: edge_player_reid.md.

## INFORMED-FLOW (2026-07-15) — follow large/informed taker flow: NULL, hypothesis DISCONFIRMED (heavy flow is DUMB money)
Operator hypothesis: large/one-sided/clustered aggressive taker flow is informed -> follow it. VERDICT NULL.
Tape HAS aggressor side (BUY/SELL = taker). 19 days (11 train/8 test), btc/eth/sol, ~1550 windows/asset,
day-clustered. FOLLOW-the-flow results: Test2 net-flow-imbalance OOS t=-1.93 (-$0.037/ct; train already
neg -1.27); Test1 large-trade t=-0.14; Test3 consensus t=-0.42; Test4 smart-money-late-large t=+0.70 (only
train pick t=1.96 collapses OOS); 40 configs, none positive. DECISIVE DIAGNOSTIC: in heavy-flow windows the
FOLLOWED side hits settlement only ~37% while the book mid hits ~71-74% and flow agrees with mid only ~31%
-- heavy aggressive flow LIFTS THE UNDERDOG (longshot), the MIRROR of FAVLONG. So the bulk heavy flow is
DUMB MONEY (longshot chasing), NOT informed; following it pays spread+fee to chase an already-priced,
usually-wrong direction. FAVLONG corr = +0.199 (low). IMPLICATION: this REINFORCES FAVLONG's mechanism --
naive longshot-chasing flow is part of WHY favorites are underpriced near expiry, and FAVLONG partially
FADES it. Fading heavy flow ~= FAVLONG's favorite-buy (correlated, pays spread) -> at most a FAVLONG
confirmation/strength signal, NOT a standalone orthogonal edge. Report: edge_informed_flow.md.

## PARTICIPANT/FLOW THREAD SYNTHESIS (2026-07-15) — closed
Three studies (FINGERPRINT + PLAYER-REID + INFORMED-FLOW) answer "learn from other participants?":
- The 15m tape is ANONYMOUS with no account/order ids; size+timing do NOT fingerprint individuals -> player
  re-ID is INFEASIBLE, and best-effort synthetic-player search finds no OOS winner (fewer in-sample winners
  than chance).
- Aggressive flow is DUMB (longshot-chasing, ~63% wrong) not informed; following it LOSES. Only the RARE
  >5000ct whales are informed (markout -0.083).
- NET RESULT: no NEW followable edge in participant behavior. What we DID gain: (1) confirmation of FAVLONG's
  mechanism (it fades naive longshot-chasing flow via fair value), (2) a whale STAND-DOWN filter, (3) a
  DECAY EARLY-WARNING (counterparty reprice-latency falling -> wire a forward tripwire), (4) box-maker-off is
  a <=1% ecosystem change. Participant intel improves/monitors FAVLONG; it is not a second edge.

## FADE-FLOW (2026-07-15) — fading dumb heavy flow: DIRECTION VALIDATED but NULL net-of-fee (the FEE is the killer)
Directly tested FADING heavy dumb flow (take the OPPOSITE side at executable price, cross spread, net Kalshi
fee -- not inferred from the follow). VERDICT: NULL net-of-cost, BUT the operator's direction is VALIDATED:
the anti-flow (favorite) side wins ~64% at exec price ~0.63 = +1.0c/ct GROSS (after spread, OOS). The Kalshi
fee ~= 0.07*p*(1-p) ~= 1.3c/ct at those prices EXCEEDS the 1c gross -> nets -0.3c/ct. THE FEE, NOT THE SIGNAL,
KILLS IT. 34 fade configs, none OOS t>=2 (best pooled t=-0.50, -0.003/ct; per-asset btc -0.011, eth +0.048
tiny-n, sol -0.060). Conditioning on heavy flow does NOT beat unconditional favorite-buy (-0.024 vs -0.018).
FADE-vs-FAVLONG corr = -0.220 (low/orthogonal, as predicted) -- moot while sub-fee.
KEY INSIGHT (reframes the DumbFlow hunt): FAVLONG monetizes this SAME favorite direction ONLY because it is
SELECTIVE -- it fires only on dislocated wide-book near-expiry windows where gross (3-4c) >> fee. The
unconditional/flow-conditioned fade's gross (1c) sits below the ~1.3c fee. => To monetize a fade you must get
GROSS > FEE, via (a) a MORE SELECTIVE dumb subset (bigger dislocation, like FAVLONG's wide-book gate), or
(b) trading at EXTREME prices where the fee 0.07*p(1-p) is SMALLER (p~0.1/0.9 fee ~0.6c vs ~1.75c at 0.5).
This is exactly what the DumbFlow-signature hunt (counter-spot/tail/round-lot/late/session) should surface --
tail/extreme-price fades naturally pay a lower fee. Report: edge_informed_flow.md (FADE section).

## DUMBFLOW-HUNT (2026-07-15) — 5 DumbFlow fade signatures on Kalshi: all NULL; Kalshi participant theme EXHAUSTED
Tested fading counter-spot, tail/extreme-price, round-lot, late-window-chase, session. 18 days, 4298 windows,
18.9M prints, train-select/test-once, (asset,day)-clustered. VERDICT: NULL -- none clears cost.
- PREMISE CONFIRMED per-trade: dumb subsets are -EV (counter-spot takerEV -0.021, round-lot -0.013, lottery
  tail(buy YES<0.15) -0.016). BUT fading loses net OOS: window-aggregated net direction carries ~0 gross
  edge (counter-spot +0.0014, round-lot +0.0024), and the one real per-trade wrongness (lottery -1.6c) is
  SMALLER than the ~1c round-trip cost + rare tail losses (fade net -0.0185). You cannot monetize spread-
  payers by also paying the spread.
- KEY CORRECTION: late-window "chasers" are NOT dumb -- they are INFORMED (86% correct, takerEV +0.027);
  fading them is strongly negative (OOS day-clustered t=-4.44). Tail-high buys near-fair + FAVLONG-collinear
  (corr +0.44). Session/retail-hours: no stable effect (wrong sign if any).
- ONE POSITIVE, flagged NOT-a-new-edge: FOLLOWING late directional flow nets +0.019/ct OOS (t=+2.74) but it
  is mechanically FAVLONG's terminal-convergence re-expressed through the tape (corr -0.23, same 720s band,
  contradicts the prior informed-flow late-follow null) -> mild independent tape-CONFIRMATION of FAVLONG,
  must NOT be stacked without a FAVLONG-controlled forward test.
CONCLUSION: the KALSHI participant/flow theme is EXHAUSTED -- every follow/fade variant is NULL net-of-fee
(the mid prices direction efficiently; residual wrong flow's per-trade edge < round-trip cost; can't fade
spread-payers by paying the spread). The remaining hope for a participant edge is POLYMARKET (zero-fee CLOB +
persistent wallet IDs, analysis running). Report: edge_dumbflow.md.

## LATE-FLOW-CONTROLLED (2026-07-15) — "bet WITH late chasers?": NO -- the +2.74 was a CLEAN-LABEL LOOK-AHEAD artifact
FAVLONG-controlled test resolved it. VERDICT: do NOT bet with late chasers, do NOT stack; NOT deployable.
- The +2.74 "follow late flow" was a CLEAN-LABEL SELECTION / LOOK-AHEAD artifact: in clean-label windows
  sign(spot@720-open) = outcome 90.3% BY CONSTRUCTION. Removing that undeployable filter (a live trader
  cannot know the terminal label at t=720) collapses OOS t +2.74 -> +0.28 (net ~0), turns pure-momentum
  train-negative, and flips the FAVLONG-neutral residual +2.05 -> -2.22.
- Raw late taker-flow-follow actually LOSES (OOS t=-2.97). The strongest variant used NO tape at all (just
  sign(spot@720-open), t=+3.91) => it was spot-momentum, not a flow edge. Contradiction w/ informed-flow
  null (+0.70) resolved: single-largest-print spec reproduces the null.
- Correlation reconciliation: NOT FAVLONG re-expressed (earlier call wrong) -- corr -0.20, opposite sides 81%
  (FAVLONG near-expiry CONTRARIAN; momentum-follow goes WITH the move). Partly-orthogonal but no deployable edge.
CRITICAL FOLLOW-UP RAISED: the clean-label SELECTION inflated a spot-direction signal by ~2.5 t of look-ahead.
FAVLONG is ALSO validated on clean-label windows and its signal is spot-vs-strike -> MUST verify FAVLONG's
edge survives WITHOUT the clean-label selection, else our one edge shares this leak. Check launched. Report:
edge_dumbflow.md (LATE-FLOW-FOLLOW section).

## FAVLONG-INFLATED (2026-07-15, CRITICAL — overturns the central result) — the "one edge" was a look-ahead artifact
FAVLONG's validated edge is MATERIALLY a LOOK-AHEAD SELECTION ARTIFACT of the clean-label filter
(favlongshot_edge.py:137 / favlong_model_v2.py:123: `if out_proxy != outcome: continue`, dropping windows
where sign(final_spot-open_spot) != (mid_close>0.5)). That drop PEEKS at the terminal outcome (a live trader
cannot apply it) and deletes exactly the ~7% of windows where FAVLONG's spot-direction signal disagrees with
settlement -- the trades most likely to LOSE (dropped windows realize -0.20..-0.23/ct).
INDEPENDENTLY VERIFIED (lead re-ran, toggling ONLY that line): calibrated OOS pooled t 5.74 -> 1.80 without
the drop (btc 1.97, eth 1.41, sol -0.27), mean 0.051 -> 0.015/ct; agent got 1.87/0.018 and in-sample t=-0.34.
BOTH BELOW the t>=2 charter gate -- no deployable edge in OR out of sample; only btc alone is near-2 (1.97).
The favorite>=0.60 "rescue" (t=2.24) was itself computed on the selected subset (deployable t=0.66). Isotonic-
fit-on-selected-rows is second-order (refit -> t~1.80). ROOT CAUSE: the STRIKE is proxied as open-spot (the
real Kalshi strike isn't in the tick archive; binmid confirms open YES mid 0.365/0.625 != 0.5 => strike !=
open). The proxy is wrong in ~7% of windows, flipping the outcome; clean-label hid those losses by outcome-
peeking.
IMPLICATIONS: (1) FAVLONG as validated is NOT a deployable edge. (2) The forward harnesses (favlong_forward.py,
favlong_taker.py) score the INFLATED clean-label version -> the forward gate measures the WRONG thing and MUST
be corrected (drop the filter; label = market terminal on ALL windows). (3) POSSIBLE RECOVERY (not yet done):
re-derive FAVLONG with the TRUE strike / real binary price (the binmid ticker carries the real market) instead
of the open-spot proxy -- fixes the ~7% bad windows and removes the clean-label crutch; the deployable edge may
recover to >=2 or confirm dead. Report: favlong_cleanlabel_robustness.md.

## PMKT-WALLETS (2026-07-15) — Polymarket wallet-level smart/dumb: skill is REAL+persistent but NULL for a tradeable edge
Data fully obtainable: data-api.polymarket.com/trades (wallet addr, side, price, size) + Gamma UMA resolution;
632 btc-updown-5m markets, 2.53M trades, 30,761 wallets, 35d, zero-sum-validated. Smart/dumb PERSISTS in rank
(Spearman train->test ROI 0.16-0.18, z~6-8; top decile +11% OOS ROI, bottom negative) -- so with real IDs,
skill is genuinely identifiable. BUT NO follow/fade clears net: FOLLOW-smart +$28.7k (t=2.08) collapses to
-$2.1k without the top-10 whales; FADE-new t=4.82 but 88% is 50 blow-up accounts, reverses to -$64k (t=-5.71)
without the worst-200 -- the dollars live in ex-ante-UNIDENTIFIABLE tails. Size-independent directional signal
clears nothing (best t=1.89 pre-cost); FADE-dumb clean null. ROOT CAUSE: Polymarket books tight/deep/EFFICIENT
-> even ZERO fees open no fadeable behavioral mispricing (confirms newedge_polymarket). Transfer to Kalshi: LOW.
Verdict: excellent data + real persistent skill, rigorous NULL for a portable follow/fade edge. Report:
edge_polymarket_wallets.md.

## STATE OF THE PROGRAM (2026-07-15, honest reset)
After exhaustive search we currently have ZERO validated DEPLOYABLE edges. FAVLONG (the presumed winner) was
look-ahead-inflated -> deployable t~1.8 < gate. Box-making structurally dead. All sleeves/orthogonal/perp/
participant/flow/Polymarket avenues null. The rigor caught FAVLONG BEFORE any money was risked (live box-maker
OFF since LIVE-HALT). Concrete open recovery path: real-strike FAVLONG (use the true Kalshi strike from the
binary market spec, not the open-spot proxy). If that fails, 15m-crypto binary has no demonstrable edge for us.

## FAVLONG-DEAD (2026-07-15, DEFINITIVE) — true-strike recovery KILLS it; it never had a deployable edge
The true-strike test (real Kalshi floor_strike + result, ~100% coverage back to 06-10, so availability was a
non-issue) is the decisive kill. With the TRUE strike + TRUE result + NO clean-label drop, deployable OOS
pooled t = 0.91 (cache-days) / 0.78 (full), per-asset btc -0.27 / eth 1.16 / sol 0.66 -- below even the flawed
1.80, and the TRAIN edge is GONE (all 24 v2 variants <=0 on train; most-generous best-of-24 post-hoc TEST
t=1.31). Harness reproduced the prior 5.76 (inflated) / 1.79 (proxy-deployable) exactly -> alignment valid.
THE EDGE WAS A DOUBLE ARTIFACT: (1) the clean-label outcome-peek inflated 5.74; (2) the residual "1.80" was
itself the proxy-vs-true-strike MISSPECIFICATION -- not a real floor. PROFOUND: with the true strike the model
is BETTER CALIBRATED (Brier improves, e.g. sol 0.100->0.089) but CANNOT TRADE, because a correctly-specified
model AGREES with an already-EFFICIENT market. CONCLUSION: FAVLONG has NO deployable edge and never did.
Report: favlong_truestrike_recovery.md.

## STATE (2026-07-15) — 15m-crypto is efficient for us; the exhaustive search is null
Every edge TYPE has now been tested and is null-or-artifact for a correctly-specified small participant at our
cost structure: spread-capture (box, structurally dead), repricing-lag (FAVLONG, double artifact), directional/
informed-flow (null; flow is dumb but sub-fee), cross-strike arb (null, within-spread), calibration (null),
vol/event-VRP (null/insufficient), carry (perp funding=0), participant re-ID (infeasible, no ids), flow fade
(direction real but sub-fee), Polymarket wallets (real persistent skill but tail-dominated/untradeable).
The ONLY confirmed REAL signal in the whole program = Polymarket top-decile wallet skill (+11% OOS ROI,
Spearman 0.16-0.18) -- naive harvest is tail-dominated, but a TAIL-ROBUST copy-trade is the one un-exhausted
thread (pursuing). Also undecided: perp-basis forward gate (~07-25). Live box-maker remains OFF; NOTHING was
risked to learn all this -- the rigor (esp. the tested-vs-live discipline) worked, catching our own flagship.

## PMKT-COPYTRADE (2026-07-15) — skill-copy NULL; a favorite-longshot candidate emerged -> PENDING adversarial verify
Tail-robust copy-trade of persistent-skill Polymarket wallets. SKILL-COPY = NULL: agent caught its own
lookahead leak (signals used final-SETTLED positions; rebuilt from as-of-T, causal entry 0.50->0.75, edge
shrank ~3x). Quorum-copy / smart-vs-dumb-disagreement / consensus-strength all null net-of-spread; smart
DIRECTION carries no signal beyond price (unconditional favorite-buy t=+0.05; when smart lean diverges from
favorite it is WRONG 94-97%). => wallet skill is real (persists) but NOT harvestable directionally.
HOWEVER a favorite-longshot MICROSTRUCTURE candidate emerged: "buy the underpriced favorite when >=2 tracked
wallets late-buy the underdog" -- OOS day-clustered t=+5.5 net of 1c spread, win 97% at entry ~0.85, survives
all jackknifes (drop-top-5-mkts +3.7, drop-top-20-wallets +5.8, trim +8.3), IDENTITY-INDEPENDENT (smart/dumb/
random signal it equally => it's fade-noise-flow / favorite-longshot microstructure, NOT skill). ~180 configs.
DO NOT TRUST YET -- FAVLONG PARALLEL: same shape (favorite-longshot, high-t, jackknife-surviving) as FAVLONG
which was JUST proven a double look-ahead/misspecification artifact; it CONTRADICTS the prior 'Polymarket
efficient / FAVLONG-null-there' finding; and 97%-win-at-0.85 is economically implausible for an efficient book.
STATUS: PROBABLE ARTIFACT, pending an adversarial deployability/look-ahead audit (entry-ask causality at T,
settlement/favorite-label leak, real executable depth, reconcile with Polymarket-efficient). NOT a declared
winner. Report: edge_polymarket_copytrade.md.

## PMKT-FAVLONG-VERIFY (2026-07-15) — the candidate SURVIVED adversarial audit (unlike FAVLONG) -> strong, pending independent repro
Adversarial 9-toggle audit of the Polymarket "buy favorite when >=2 wallets late-buy underdog" candidate.
VERDICT: survived every deployable toggle. Entry-price toggle (THE FAVLONG KILLER) SURVIVES -- the ~0.84
favorite is a real executable ask off a tight 1c book, matches contemporaneous taker-print fair value
(0.835 vs 0.837); re-priced true-executable t=+5.85 (+5.37 with extra 1c slippage). Signal strictly causal
(underdog buys ts<=T on correct epoch; measuring EARLIER strengthens it, t up to +8.5) -> no post-T/settled
leak of the FAVLONG kind; settlement = true Gamma/UMA. Holds TRAIN (+6.2) + TEST, 15 days, 42 window-runs
(run-clustered t 4.96). Mechanism NOT skill nor momentum (random wallet sets reproduce it; momentum-gate null)
-- a "cheap-side participation marks a decisive/continuing move" residual: within a fixed price band the gate
splits same-priced favorites 100% (gate) vs 68% (non-gate). Strict deployable OOS day-clustered t ~= +5.4.
RESERVATIONS (do NOT declare winner yet): (1) ECONOMIC -- a costless PUBLIC (on-chain) signal splitting
68/100% at one price on a liquid 0-fee book should be arbitraged; persistence implies tiny/non-scalable
capacity OR a hidden leak. (2) UNTESTED sample-wide selection (all 632 markets share one construction; single
implementation can't rule it out). (3) EXECUTION -- filling 0.84 while the favorite climbs through it, ~6 thin
signals/day, capacity bounded by favorite ask depth. STATUS: strongest candidate of the whole program; passed
the audit FAVLONG failed -- but gated on (a) a SECOND from-scratch independent reproduction and (b) live
fill-quality before any winner claim or sizing. Report: pmkt_favlong_verify.md.

## PMKT-FAVLONG-INDEPENDENT (2026-07-15, DEFINITIVE) — the candidate is an ARTIFACT; independent repro on FRESH data kills it
From-scratch independent pipeline (own fetch, own code, forbidden files untouched), 1,239 resolved
btc-updown-5m markets incl. genuinely FRESH/forward 2026-07-15 data. VERDICT: NOT-CONFIRMED. The +5.4 does
NOT reproduce. ROOT CAUSES:
- THE FAVORITE IS CALIBRATED: in the ~0.84 band it wins ~86-88% (= its price), NOT 97% -> there is NO
  favorite mispricing to capture. The reported "97%" was small-n (forward n=15) + selection.
- THE GATE IS INERT: liquid markets have a MEDIAN ~217 distinct underdog buyers before T, so ">=2 wallets
  bought the underdog" is satisfied by ~100% of markets -> no "68% ungated" population exists. The prior
  +5.4 depended on a SMALL fixed wallet-set gate whose selectivity is a within-sample SELECTION artifact
  (the exact untestable concern flagged) -- not reproduced on fresh data or an independent build.
- OPTIMISTIC PRICING: the backtest used a mid ~1.7c below the real lifted ask (p90 9.5c on fast moves),
  inflating the mild residual. Clean net-of-realistic-fill day-clustered t: ~0.3 (tight 0.84 band) to ~1.4
  (realistic ask) -- BELOW the gate. Fresh 07-15 data behaves identically (gate saturated). Capacity micro.
LESSON: the adversarial audit SURVIVED only because it reused the original construction (shared the leak);
only a FROM-SCRATCH independent build on FRESH data caught it -> validates the two-independent-implementations +
forward-data discipline. Report: pmkt_favlong_independent.md.

## TERMINAL (2026-07-15) — no deployable winning strategy in the accessible universe; the market is efficient for us
After an exhaustive search, there is NO deployable winning strategy in the accessible universe (Kalshi 15m
crypto binaries + Polymarket 5m crypto + Kalshi perps; every edge TYPE: spread-capture, repricing-lag,
directional/informed-flow, cross-strike arb, calibration, vol/event-VRP, carry/funding, participant re-ID,
flow-follow/fade, wallet skill-copy, favorite-longshot). BOTH high-t candidates were ARTIFACTS caught by
verification: FAVLONG (t=5.74 -> deployable 0.9, clean-label look-ahead + strike misspecification) and the
Polymarket favorite-longshot (t=5.4 -> ~0.3-1.4, selection + optimistic-mid). Correctly-specified models AGREE
with these efficient/calibrated markets at our cost structure and size. NOTHING was risked (live box-maker OFF
since LIVE-HALT). The durable asset is a battle-tested VALIDATION FRAMEWORK (realized-settlement + look-ahead/
selection audits + adversarial toggles + from-scratch independent reproduction on fresh data) that reliably
separates real edges from illusions -- it just killed two convincing ones. A winning strategy requires a
STRUCTURALLY DIFFERENT domain/edge + infrastructure (an operator strategic decision); it cannot be honestly
manufactured from this universe.

## PERP-ALLASSETS (2026-07-15) — all 16 Kalshi perps probed for carry+basis: NULL (venue efficient, funding structurally 0)
Checked the genuinely-untested corner (illiquid altcoin perps, where new-venue inefficiency is most likely).
Across ALL 16 perps (btc/eth + hype/kshib/zec/sui/near/hbar/link/ltc/doge/bch/dot/xlm/xrp/sol):
- FUNDING = 0% annualized for EVERY asset -> Kalshi perp funding is structurally ~0/not implemented, so the
  funding-CARRY edge (the one thing that worked historically -- Deribit BTC OOS t=6.67, PERPS_BACKTEST.md) is
  UNAVAILABLE here. Not tradeable on any coin.
- MID-vs-INDEX basis is small and BELOW the spread for every asset (range -5.6bp near .. +2.6bp bch; e.g.
  near basis -5.6 vs spread 8.0; bch +2.6 vs 6.6; btc +1.4 vs 1.2) -> no tradeable basis arb even on the
  illiquid altcoins; the venue tracks its index tightly across all coins.
So the perp venue is EFFICIENT (0 funding, sub-spread basis) even in its thinnest corners. The only remaining
perp thread is edge-a (perp<->15m-binary basis), forward-gating with a thin day-1 read. This closes the last
genuinely-untested backtestable avenue with a real prior. Terminal conclusion stands.

## EXO-MOM (2026-07-15) — exogenous SPOT MOMENTUM near expiry is already PRICED (backtestable slice, NULL/negative)
Operator reopened the search on a NEW domain: "exogenous signal -> Kalshi 15m binaries." First the backtestable
part — does recent EXOGENOUS spot momentum (log-return over the last 1-5 min, causal) predict the binary's
terminal outcome BEYOND the Kalshi mid? FAVLONG's fair value assumed zero drift; if short-horizon spot flow had
un-priced continuation, sign(recent_return)*(outcome-mid) would be reliably >0 and a taker overlay would clear fees.
Tool: momentum_edge.py. Protocol: market's own terminal settlement label (no strike proxy), NO clean-label drop
(both known look-ahead traps here), train<=06-30 / test>06-30, day-clustered t, +Kalshi fees.
- RESIDUAL (gross, no cost), pooled all 3 assets, FIXED feature (no selection): ret3m weak-positive both train
  (0.81) and test (2.52) ~ +1.2c gross; ret2m sign-FLIPS train(-1.53)->test(2.34) = noise; others null.
- TRADEABLE overlay, PRE-REGISTERED fixed feat+threshold (no per-asset pick), net fees: NEGATIVE train
  day-clustered t for EVERY config (-4.75,-3.17,-2.53,-2.81,...). It LOSES in-sample. The only positive OOS blips
  (ret1m/thr .0015 test 2.20) were random in train (0.43) on tiny n.
- The initial per-asset feature+threshold search printed a shiny POOLED OOS t=2.41 -> that was the SAME selection
  artifact machinery as FAVLONG's 5.74: it cherry-picked SOL's lucky test corner while BTC (deepest) was null (0.20).
VERDICT: observable spot momentum is PRICED by the Kalshi book; any residual ~1c momentum lead is SUB-FEE/spread ->
not deployable as a taker. INDEPENDENT from-scratch repro (separate code, 6,459 windows) CONFIRMS the null: tradeable
overlay negative in-sample for ALL 16 (lookback,threshold) configs (train t down to -3.64); gross residual weak,
sign-UNSTABLE across train/test (L=120 flips -0.96->+2.72), and <spread+fee. This kills the *backtestable*
part of the exogenous-signal domain and confirms: adding degrees of freedom (per-asset feat/thresh) manufactures
false positives; a SINGLE pre-registered signal is the only honest test.

## EXO-OFI (2026-07-15) — true signed ORDER FLOW: the one untested exogenous signal; forward experiment DEPLOYED + PRE-REGISTERED
The archive has sampled spot+microprice (EXO-MOM shows that's priced) but NOT true signed trade flow. The only
genuinely-untested exogenous signal is CVD/OFI + book imbalance + aggressor intensity from a major spot venue,
which can lead price at seconds-to-minutes horizons. No historical signed-flow archive exists -> forward-only.
DEPLOYED: ofi_collect.py (Coinbase public REST, ~2s poll, signed flow via aggressor side + top-10 book imbalance,
self-chaining always-on like collect.yml) writing gha_data/<day>/ofi_coinbase_<asset>_r*.jsonl.gz; workflow
.github/workflows/ofi-collect.yml on main. PRE-REGISTERED (OFI_FORWARD.md, before any data exists = ungameable):
ONE primary signal = OFI over [ws+600,ws+720] normalized by trailing-30-window median |OFI|; FIXED threshold Z=1.0;
bet WITH the flow at the Kalshi ask/bid; net fees; label = terminal market settlement, no strike proxy, no
clean-label drop. GATE (ofi_forward.py, frozen): pooled per-(asset,day) day-clustered t>=2 over >=10 FORWARD days
AND btc-alone mean>0 (no single-asset corner); KILL if t<0 after 10d. PROPOSE-ONLY. Prior is WEAK (observable
exogenous signal already priced) but this is the honest way to actually TEST the operator's chosen domain rather
than declare it dead on a proxy. Clock starts at first full collection day; gate opens ~10 forward days later.

## EXO-XASSET (2026-07-15) — cross-asset BTC->alt lead-lag is also PRICED (null/negative in-sample)
Tested the one remaining backtestable exogenous PRICE signal distinct from own-asset momentum: does BTC's recent
spot move (leader, 120s causal return) predict the ETH/SOL binary outcome beyond the alt's own mid (BTC leads alts)?
Same discipline as EXO-MOM (settlement label, no strike proxy, no clean-label drop, ONE signal + fixed thresholds
reported in full, day-clustered t, +fees; windows joined on shared ws). Tool: crossasset_edge.py.
- RESIDUAL (gross): btc->eth NULL (train -0.44, test -0.14); btc->sol train NEGATIVE -1.39 -> test 2.71 = sign-flip
  noise. eth->btc / sol->btc controls null-to-negative.
- TRADEABLE (net fees): NEGATIVE train day-clustered t for EVERY fixed threshold (btc->eth -1.93/-0.79/-0.88;
  btc->sol -3.61/-2.45/-0.82/-1.86). Positive test blips (btc->sol thr .002 test 1.93) rest on n=15 trades, negative
  in train -> noise.
VERDICT: the alts already embed BTC's move (arbitraged within seconds); no residual 2-3min lead-lag to trade. Both
backtestable exogenous PRICE signals (own momentum EXO-MOM, cross-asset lead-lag EXO-XASSET) are PRICED. The ONLY
untested exogenous signal is true signed ORDER FLOW (EXO-OFI), which is forward-only and now collecting. The
backtestable exogenous-signal space is exhausted; terminal conclusion stands, with EXO-OFI as the live forward thread.

## RICHDATA (2026-07-15) — STRATEGY PIVOT: ultra-rich exogenous BTC data -> signal -> downstream to the 15m binary
Operator reframed the search (correctly): the edge is NOT in the venue's own book (everyone sees it -> efficient,
as proven exhaustively above). It is in RICH EXOGENOUS BTC data that predicts the short-horizon move the binary
settles on, which the Kalshi makers are NOT pricing -- "information not everyone has." Program: assemble multiple
ultra-rich multi-year BTC datasets, discover signals that predict forward BTC returns/vol OOS, then apply survivors
DOWNSTREAM to the 15m binary (which must additionally clear the ~2-4c spread + fee at t=720 -> forward execution test).
DATA SOURCES confirmed reachable through the proxy (all free/no-auth, multi-year):
- Binance Vision SPOT aggTrades (2017+, signed via isBuyerMaker) -> order flow / CVD.
- Binance Vision FUTURES metrics (5-min: open interest, top-trader & global long/short ratio, taker buy/sell vol),
  klines, aggTrades, bookDepth (L2 order-book depth history), fundingRate -> positioning/leverage/book stress.
- Deribit options API: instruments, DVOL implied-vol index history, per-option IV/greeks summary -> vol surface,
  skew, dealer-gamma (GEX). Full historical GEX needs forward collection; DVOL history is backtestable now.
- blockchain.info charts (on-chain), OKX funding history, Kraken/Coinbase OHLC, cryptodatadownload.
- One-day smoke (2024-03-01): corr(minute-OFI, fwd-3min spot ret) = -0.058, sign-hit 49% -> hints MEAN-REVERSION
  (transient impact), not momentum; needs the multi-year verdict.
LAUNCHED (rigorous anti-artifact specs: causal features, OOS-by-time, real costs, full grid, no cherry-pick;
any positive to be INDEPENDENTLY reproduced before it counts):
- btc_orderflow_backtest.py  -> spot order flow vs fwd 1/3/5/15min return, momentum AND reversion, ~90 days 2022-25.
- btc_derivatives_backtest.py -> OI/long-short/taker/funding stress vs fwd 5/15/30min return, ~90 days.
- kalshi_calibration.py -> favorite-longshot at scale across 8 Kalshi categories (de-emphasized per operator; BTC-data
  downstream is the better bet, but let it finish for completeness).
WAVE 2 (after wave-1 verdicts, to manage disk + verification): Deribit options GEX/skew/DVOL; futures bookDepth L2
imbalance. Verdicts pending; this node records the program + the confirmed data foundation.

## KALSHI-CALIB (2026-07-15) — favorite-longshot/calibration at scale: NULL (well-powered, 7579 markets)
De-emphasized per operator (BTC-data-downstream is the better bet) but finished for completeness. 7,579 settled
binary Kalshi markets across 8 categories (~200x the prior 35-day crypto attempt); entry = count-weighted YES-VWAP
over trades in the FIRST HALF of [open,close] only (anti-artifact: never last_price/settlement), OOS split by
close_time, isotonic map fit TRAIN-only, PnL net fee 0.07p(1-p) + 1c half-spread. Tool: kalshi_calibration.py.
- Calibration: mild POSITIVE deviation in the mid-low range (~0.10-0.55 early prices realize YES more often than
  priced, +0.05..+0.09); extremes well-calibrated. NOT classic favorite-longshot; and not tradeable after costs.
- OOS tradeable: POOLED TEST t=+1.25 (NULL). Strong cross-category heterogeneity (Economics buys LOSE t=-4.6).
  Crypto headline t=+3.45 rests on only 5 close-dates -> discarded (the exact thin-clustering artifact this was
  built to avoid). Only Climate/Weather is positive with adequate clustering (t=+2.39, +$0.042/ct, 13 dates) but
  FAILS Bonferroni across 8 categories (need |t|>2.7). PARKED (not pursued; weather is a possible future thread).
VERDICT: no well-powered, cost-surviving calibration/favorite-longshot edge in any Kalshi category. The venue's
own settled-market data is calibrated for a taker at our costs -> reinforces that the edge must come from EXOGENOUS
BTC data (RICHDATA program), not the venue's own information.

## EXO-OFI-BACKTEST (2026-07-15) — signed order flow does NOT predict short-horizon returns net of cost (NULL, well-powered)
FIRST backtest of the order-flow thesis on years of data (the reason OFI was forward-only: no historical signed-flow
archive existed -> now solved via Binance Vision aggTrades). 164 days across 2022-01..2026-07, 1-min bars, signed OFI
features (scale-free, causal), forward 3/15-min returns, train(115d)/test(49d), momentum AND reversion, day-clustered.
Tools: btc_orderflow_backtest.py (agent, had an epoch-minute reindex bug -> 80.8M fabricated rows, OOM; I fixed via
vol>0 filter + independent recompute) and btc_orderflow_report.md.
- GROSS momentum edge: ~ZERO in TRAIN (0.01-0.1 bps, t<1; one cell negative), tiny +0.1-0.3 bps in TEST (large t only
  from millions of obs). Era-UNSTABLE (train~0, test small+).
- NET of a token 1bp round-trip: EVERY cell, BOTH directions (momentum & reversion), BOTH splits is NEGATIVE
  (test t ~ -50..-145). MOM loses ~0.7-1.0 bps/trade; REV loses ~1.0-1.3 bps/trade.
- The 15m binary requires crossing ~2-4c spread = HUNDREDS of bps on a ~50c contract -> a <=0.3bp gross signal cannot
  possibly survive downstream.
VERDICT: signed order flow nudges price (as expected) but has NO cost-surviving short-horizon predictability -> the
momentum/OFI-leads-price thesis is dead at the tradeable level, and EXO-OFI's downstream prospects are poor (consistent
with its stated WEAK prior). This is the well-powered version of EXO-MOM's null, now on years of real signed flow.
Remaining exogenous angles still open: derivatives positioning stress (running), options GEX/skew/DVOL (wave 2),
sub-second flow (not backtestable). "Information not everyone has" at the flow level is real but ~0.1-0.3bp -> unpriced
by almost nothing; the venue/market prices it to within costs.

## EXO-DERIV-BACKTEST (2026-07-15) — derivatives positioning stress does NOT predict short-horizon returns (NULL)
Tested "information not everyone has": open interest change, top-trader & global long/short ratios, taker imbalance,
funding -> forward 5/15/30-min BTC returns. 40 days 2022-01..2026-05 (Binance Vision futures metrics 5-min + klines +
funding), causal z-features, train(28d)/test(12d), momentum AND reversion + 4 classic named setups. Tool:
btc_derivatives_backtest.py / btc_derivatives_report.md.
- Strongest signal = crowded long/short ratio (contrarian): gross corr only -0.03..-0.08. Best cell ~+1bp/trade gross
  with day-clustered t<1 (ls_top 30m 1bp REV +1.42/+0.91, t 0.92/0.70) -> insignificant + cost-dead.
- NO cell in the 138-cell grid is POSITIVE + significant (t>=+2) in BOTH train and test. Every direction loses net cost.
- The agent's report claimed "77 SURVIVED" -- that was a BUG (survive-flag used |t|>=2, so it flagged consistent
  LOSERS; all 77 have negative train AND test bps). I corrected the report; TRUE verdict is NULL.
VERDICT: derivatives-positioning stress has no positive, cost-surviving short-horizon predictability (sample thinner
than order-flow at 40 days, but signal clearly absent, not just underpowered). Positioning is priced too.
Now two well-powered exogenous nulls (order flow, derivatives). Remaining: options GEX/skew/DVOL (wave 2 -- the one
with a mechanism, dealer gamma hedging, that maps onto the binary's STRIKE-relative settlement).

## EXO-DERIV update: agent re-ran to 163 days (2022-01..2026-07, 46,427 5-min bars) with a FIXED survive-flag
(profitable = mean bps>0 AND t>=+2 in BOTH splits). Confirms NULL: ZERO profitable survivors in MOM or REV across
the full 138-cell grid; strongest signal still crowded long/short (contrarian) at gross corr -0.03..-0.08, cost-dead.
The larger 163-day run only strengthens the null. (dOI corr shows nan due to an agent corr-calc glitch, but the
day-clustered trade tests -- the robust arbiter -- are clean and negative.)

## EXO-LEADLAG (2026-07-15) — cross-exchange lead-lag: REAL but HFT-scale, NOT tradeable for us
Operator "widen the free-data net": does a faster venue lead the Kalshi settlement price? Binance PERP vs SPOT
1-second lead-lag (Binance Vision aggTrades, years). Tool: cross_venue_leadlag.py.
- corr(perp_ret[t], spot_ret[t+k]): k=-1s +0.088, k=0 +0.832, k=+1s +0.172, k=+2s +0.078, k=+3s +0.047.
- PERP LEADS SPOT (0.17@+1s > 0.09@-1s) -- the documented price-discovery lead -- but at ~1 SECOND, decaying to
  ~0.05 by 3s. Utterly irrelevant at the 15m binary's ~180s decision horizon; unexploitable at a Kalshi taker's
  seconds-of-latency (needs colocation/sub-second execution).
VERDICT: the lead is real but HFT-only. ALL predictive microstructure info decays within SECONDS; our tradeable
horizon is MINUTES. This is the crux of why every free-data signal is priced FOR US: the edge exists but lives in a
latency band we cannot access. Consistent with order-flow + derivatives nulls.

## EXO-BOOKDEPTH (2026-07-15) — order-book depth imbalance is priced too (NULL); on-chain is horizon-mismatched
Operator option 3 (grind remaining free microstructure). Binance Vision futures bookDepth (±1-5% depth, ~30s
snapshots) -> 1-min book imbalance vs forward 1/5/15-min return; 24 days 2024-25, joined to 1m klines, train/test.
- corr(imbalance, fwd return) = +0.003..+0.05 (tiny, train/test inconsistent). MOM net 1bp: -0.5..-1.0 bps (t neg);
  REV also -0.9..-1.5. Both directions LOSE net even 1bp. NULL.
- On-chain exchange flows (blockchain.info etc.) deliberately NOT run as a 15m signal: on-chain operates at HOURS-DAYS
  horizon, structurally mismatched to a 15-min bet (would be a category error to test it here).
VERDICT: every free microstructure signal (order flow, positioning, lead-lag, book depth) is priced at the 15m/taker
horizon. Unifying finding (EXO-LEADLAG): predictive info in crypto lives sub-second (microstructure) or multi-hour
(fundamental/on-chain); the 15m binary sits in the efficient dead zone between, gated by a latency band we can't reach.
The productive pivots are (1) LONGER-horizon Kalshi markets where slow info survives to resolution, or (2) sub-second
crypto HFT (different instrument+infra). Grinding more free 15m microstructure has exhausted its value.

## EXO-SUFFICIENCY (2026-07-15) — the 15m binary mid is a CONDITIONALLY-SUFFICIENT STATISTIC -> exotic math has no target
Operator asked whether exotic math/stats could work on the 15m market. First: KXBTC15M is SINGLE-STRIKE (one
greater_or_equal floor per event) -> cross-strike/butterfly arb and Breeden-Litzenberger implied-density are
IMPOSSIBLE. That leaves the distribution (vol/tail/skew) as the only predictable object. Decisive cheap diagnostic
on 2938 BTC windows: is mid a sufficient statistic? mean(outcome - mid) conditioned on the exact dimensions an
exotic distribution-model would exploit:
- overall calibration bias = +0.0014 (calibrated).
- by REALIZED VOL quintile: all |t|<1.6 (vol regimes priced correctly -> no GARCH/HAR-RV/rough-vol edge).
- by |MONEYNESS| quintile: all |t|<1.6 (tails priced correctly -> no EVT/fat-tail edge, no favorite-longshot).
- by SIGNED moneyness: all |t|<1.8.
- by UTC HOUR (vol seasonality): 24 tested, NONE reach |t|=2 (max +1.96; ~1 expected by chance) -> no seasonality edge.
VERDICT: the market mid conditionally captures vol, moneyness, and time-of-day -> it is a sufficient statistic on
every measurable distribution dimension. Therefore exotic distribution methods (GARCH/HAR-RV/EVT/rough-vol/HMM-regime/
Hawkes) have NO systematic bias to exploit -- they would only overfit noise. Exotic math cannot manufacture info that
conditional calibration shows isn't there. The ONLY non-foreclosed exotic-adjacent path is a genuinely NEW conditioning
variable carrying information the mid lacks -- i.e. options GEX/skew (wave 2, untested) -- and even that must beat the
~2-4c spread on a single-strike 15m contract. Combined with EXO-OFI-BACKTEST + EXO-BOOKDEPTH + derivatives nulls:
the 15m BTC binary is efficient for us in direction AND distribution.

## EXO-GEX/PINNING (2026-07-15) — round-number magnetism (GEX mechanism proxy) is NULL; GEX not worth a forward build
Tested the backtestable CORE of the options-GEX thesis without options data: option gamma concentrates at round
strikes, so if GEX-pinning moved 15m BTC spot it would show as magnetism toward round $500/$1000 levels. 2938 BTC
windows, decision t=720:
- corr(signed dist-to-round, fwd 720->end spot return) = -0.016 ($500) / +0.018 ($1000): ~zero, sign-inconsistent.
- Nearest-to-round quartile (strongest-pinning zone): corr -0.045 / -0.030 (still ~0).
- Bet-toward-round vs mid: mean(sign(dist)*(outcome-mid)) t = -0.05 / -0.11 (null); nearest quartile t=-0.09/+0.20.
Plus: GEX is FORWARD-ONLY (Deribit exposes only the current chain; no free historical OI/greeks -> not backtestable),
and the Kalshi 15m strike = arbitrary OPEN spot, NOT a round option strike -> the pinning->binary link is broken even
if pinning existed. So GEX has a weak mechanism for THIS market AND its backtestable proxy is null -> not worth the
forward-collection build. Last exotic-adjacent card is face-up.

## TERMINAL-15M (2026-07-15) — the 15-minute BTC binary is efficient for us across DIRECTION and DISTRIBUTION (evidenced)
With years of rich free data (Binance Vision spot+futures, Deribit) the 15m market has now been tested on every
measurable axis and is efficient for a small taker at our costs:
- DIRECTION: martingale. Order flow (164d), derivatives positioning/OI/funding (163d), book-depth imbalance, perp->spot
  lead-lag -- ALL null-to-negative net of even 1bp (EXO-OFI-BACKTEST, derivatives, EXO-BOOKDEPTH, EXO-LEADLAG).
- DISTRIBUTION: mid is a CONDITIONALLY-sufficient statistic (calibrated across vol regime, moneyness, hour) ->
  exotic vol/tail/seasonality math has no target (EXO-SUFFICIENCY). Pinning/round-number null (EXO-GEX).
- STRUCTURE: single-strike -> no cross-strike/butterfly arb. Venue's own calibration null (KALSHI-CALIB, 7579 mkts).
ROOT CAUSE (binding constraint): the 15m/single-strike/~2-4c-spread box. Predictive info in crypto lives sub-second
(unreachable latency band) or multi-hour (survives to resolution only at LONGER horizons); the 15m bet sits in the
efficient dead zone between, and its ~2-4c spread (= hundreds of bps) buries every free-data signal (<=0.3bp gross).
HONEST CONCLUSION: no deployable winning strategy exists for the 15m BTC binary using free public data. A winner
requires relaxing ONE constraint: (a) LONGER-horizon Kalshi crypto (slow info survives to resolution), (b) a MULTI-
STRIKE market (enables distribution/arb math), (c) a lower-cost/maker-rebate venue, or (d) PAID exclusive data
(true "information not everyone has": L3 tick, on-chain whale flows, options order flow) -- an operator decision.
One live forward experiment (EXO-OFI, weak prior) still accrues; nothing risked. Not fabricating a winner.

## MULTISTRIKE-ARB (2026-07-15) — ladder monotonicity/butterfly arbitrage is DEAD for us (taker + maker), live-confirmed
Operator chose the multi-strike direction (unlocks distribution/arb math the single-strike 15m foreclosed). Kalshi has
hourly ladders: KXBTC (188 'between' $100 buckets = discrete density) and KXBTCD (188 'greater' strikes = implied CDF),
plus KXETHD/KXINXU/KXNASDAQ. Analyzed the existing kalshi_ladder_collect month (2026-06-12..07-15, 22,087 within-event
snapshots) + a LIVE ground-truth pull:
- Crossable monotonicity violations appear in 8% of snapshots BUT: 96% last a single 45s poll (transient/phantom);
  42% are exactly 1c gaps; Kalshi fee rounds UP to the cent (min 1c/leg -> >=2c per 2-leg lock) so a 1c gap nets ~-1c;
  the big ~0.99 gaps are stale one-sided deep-ITM wing quotes (ask absent), not real locks.
- LIVE pull (grouped correctly BY EVENT -- cross-event strike compares are NOT locks, they settle at different times):
  ZERO within-event crossable locks on KXBTCD or KXINXU right now (52-119 live strikes/event).
VERDICT: taker ladder-arb dead (transient + fee-negative, matches prior 'all phantom'); maker version also dead
(lock needs captured gap > ~2c fee, i.e. the market must move >=2c against a resting leg after it fills = adverse
selection, not free money). The ARBITRAGE sub-angle of multi-strike is closed. Remaining multi-strike sub-angles
(different prior): cross-market KXBTC-vs-KXBTCD consistency, and WING mispricing / variance-risk-premium (deep-OTM
lottery tickets where fee~0 since p~0) -- under test next.

## MULTISTRIKE-WING-VRP (2026-07-15) — REAL, well-powered wing-overpricing on the hourly BTC ladder; edge survives FEES, gated by MAKER execution
Operator's multi-strike direction. Tested favorite-longshot / variance-risk-premium on the KXBTCD HOURLY BTC ladder:
are deep-OTM wing strikes ("BTC > spot+x% this hour") systematically overpriced? Tool: kalshi_wing_vrp.py. Sample:
330 events, 2775 WING obs across 55 distinct close-dates (2026-05-22..07-15) -- WELL-POWERED, no thin-cluster risk.
Entry = first-half-of-life count-weighted VWAP (>=2 early trades; look-ahead-free); result from settlement only.
- CALIBRATION (huge, monotone, robust): EVERY wing bin settles far below entry. (0,0.02]: entry 0.013 -> realized
  0.0008 (t=-15.5). (0.10,0.15]: 0.123 -> 0.063 (t=-3.95). Symmetric deep-ITM favorites UNDERpriced (0.96-1.0:
  0.984 -> 0.999, t=+16.5). Classic favorite-longshot / VRP -- the FIRST large real mispricing found this program.
- TRADEABLE (SELL YES on wings, OOS by date, day-clustered): gross TEST +0.0227 t=3.26. Net of ROUNDED fee at VWAP:
  TRAIN +0.0158 (t=4.07), TEST +0.0127 (t=1.83) -> THE FEE DOES NOT KILL IT (p~0 -> fee ~1c). Net of fee + 1c
  half-spread: TRAIN +0.0058 (t=1.49), TEST +0.0027 (t=0.39) -> execution kills it.
VERDICT: a genuine, well-powered, FEE-surviving wing-overpricing edge exists; tradeability hinges ENTIRELY on MAKER
execution -- capturing better-than-VWAP fills by RESTING YES offers / NO bids that the longshot-BUYERS lift, rather
than crossing the spread. Mechanistically plausible (naive longshot demand is what creates the overpricing AND is the
counterparty that lifts a resting offer), but the backtest CANNOT prove resting fills are achievable. This is the best
candidate found -- NOT dead on arrival like everything prior. NEXT: (1) INDEPENDENT from-scratch repro of the
calibration on fresh data (the discipline that killed FAVLONG t=5.74 & Polymarket t=5.5); (2) if it survives, a FORWARD
MAKER paper harness (rest wing offers, measure realistic fills + settlement, day-clustered gate) -- the only way to
answer the execution question. PROPOSE-ONLY; nothing risked.

## MULTISTRIKE-WING-VRP-VERIFIED (2026-07-15) — SURVIVED independent from-scratch repro; tradeable as a TAKER. FIRST real edge of the program.
The wing-overpricing edge was put through the exact gauntlet that KILLED FAVLONG (t=5.74) and the Polymarket
favorite-longshot (t=5.5): an INDEPENDENT from-scratch reproduction (separate code, never read kalshi_wing_vrp.py,
FRESH+larger data pull). It SURVIVED -- and the repro found the first study UNDERSTATED it:
- Sample: 1,400 settled hourly KXBTCD events (2026-05-17..07-16), 11,711 wings, 61 distinct close-dates. Overpricing
  real & monotone (12.3c wings settle YES 6.1%). Robust across 2 of 3 entry-price defs (the dissenter = noisiest
  single-tick; effect lives in the first-half price DISTRIBUTION).
- TRADEABLE AS A TAKER (the key correction): the prior "collapse under a 1c half-spread" used a MIS-CALIBRATED haircut.
  Measured wing half-spreads are only 0.22-0.52c. Selling YES into ACTUAL observed taker-sell bids nets +1.27c t=4.76
  (74% of wings had a real bid). VWAP-minus-modeled-halfspread +1.03c t=4.80. Even a flat 1c haircut leaves +0.44c t=2.05.
- Edge concentrates in the 0.04-0.15 wings (real-bid +2.2..+4.5c, t 4-7); only <=0.02 is taker-dead. Fee-robust
  (larger under realistic large-order fees, +2.0c t=7.5). NOT illiquid (median first-half wing volume ~3,500 ct; edge
  LARGER in liquid wings -- opposite of the illiquid-artifact worry). OOS in time: 1st half +1.58c t=4.8, 2nd half
  +0.94c t=2.3 (mild decay, watch).
MECHANISM: favorite-longshot / variance-risk-premium -- recreational buyers overpay for "BTC > spot+x% this hour"
lottery tickets; a disciplined seller harvests the premium. Well-documented effect (strong prior it SHOULD exist),
which is WHY it survives where mechanism-free signals died. Net harvestable ~+1-2c/contract in 4-15c wings.
STATUS: FIRST candidate to clear well-powered OOS + fees + correctly-measured spreads + independent from-scratch repro
+ liquidity/selection checks. NOT yet deployed: the final charter gate is FORWARD paper validation (tested must match
live) -- building the forward harness now (pre-registered, PROPOSE-ONLY, day-clustered gate). Nothing risked.

## MULTISTRIKE-WING-XASSET (2026-07-15) — cross-asset test DOWNGRADES the edge: real phenomenon, but marginal + BTC-specific tradeable
The cross-asset replication (the FAVLONG-style clincher) delivers a SOBERING correction to the earlier optimism.
Tool: kalshi_wing_xasset.py. 44 settled dates (Jun3-Jul16 2026, one regime), hourly ladders KXBTCD/ETHD/SOLD/XRPD/DOGED.
- PHENOMENON replicates universally: calibration gap negative on EVERY asset (wings settle YES less than priced) --
  the favorite-longshot overpricing is real and not asset-specific.
- TRADEABLE edge (net fee, at the REAL executable bid, strict date-OOS) replicates CLEANLY ONLY ON BTC: full
  +0.99c t=2.97, but **OOS-TEST t=1.49** (<2). ETH weak (OOS +0.54c t=0.53). SOL replicates at the MID but DIES at
  the executable bid (wider wing spread eats it, OOS t=0.25). XRP null/underpowered. DOGE +6.96 t=6.48 but degenerate
  zero-variance bins / ~0 ct/day = ARTIFACT, discarded.
- The earlier headline +1.27c t=4.76 (kalshi_wing_verify) was ONE optimistic entry/exec definition; the conservative
  real-bid + strict-OOS view gives BTC OOS t~1.5. The t=4.76-vs-1.49 spread IS the warning: significance hinges on
  execution assumptions -- exactly the uncertain part a backtest can't settle.
- CAPACITY small: ~$0.6-1.5k/day realistic edge PnL on BTC (wide-and-shallow across 24 hourly events, median wing
  fill ~279 ct); other assets negligible. SINGLE 6-week regime -- no multi-regime robustness available.
REVISED VERDICT: the wing overpricing is a REAL, universal phenomenon, but the *deployable* edge is BTC-specific,
small-capacity, single-regime, and only MARGINALLY significant OOS at realistic execution (t~1.5). This is a
PROMISING CANDIDATE, NOT a confirmed deployable winner -- downgraded from the earlier "first real edge" framing. The
FORWARD PAPER GATE is therefore ESSENTIAL (not a formality): the backtest evidence is mixed across execution
assumptions, so only live-matched forward data can resolve whether +1c/ct at the real bid actually holds. Do NOT
deploy capital on the backtest. Paper gate accruing; decision deferred to forward evidence.

## MULTISTRIKE-WING-DEAD (2026-07-15) — the wing edge is a MARKET-WEIGHTING artifact; adverse selection kills it at realistic fills
Prompted by the maker-execution question, I computed the wing economics WEIGHTED BY TRADE (realistic fills) instead of
BY MARKET (the agents' method), from the cached trade-price lists (wing_cache/recs.json, 34,260 BTC wings, no API).
Decisive contrast on the SAME data:
- MARKET-weighted (1 obs/wing at VWAP -- what kalshi_wing_vrp / _verify / _xasset all did): +3.9c/ct t=9.20, TEST t=3.80.
- TRADE-weighted (fills proportional to real volume, maker sell@ask OR taker sell@bid): ~0/NEGATIVE. Maker net-fee
  -0.17c t=-0.26 (TEST -0.61); taker@bid net-fee -0.34c t=-0.49 (TEST -0.88); even GROSS maker only +0.8c t=1.26 (TEST 0.10).
- ADVERSE SELECTION mechanism (the smoking gun): wing YES-rate = 3.4% weighted by MARKET but 8.7% weighted by TRADE.
  Buyers pile into wings ~2.6x more heavily exactly when those wings are about to go ITM; a seller fills
  disproportionately on the wings that WIN FOR THE BUYER -> gets run over when volume is high.
VERDICT: the "edge" is a MARKET-WEIGHTING ARTIFACT. The +1-4c figures (kalshi_wing_verify t=4.76, xasset t=1.49-2.97)
equal-weighted markets you would fill UNEQUALLY, and ignored that fills concentrate in adversely-selected (ITM-bound)
wings. At realistic volume-proportional execution the edge is ~0 to negative in BOTH train and test, maker AND taker.
The favorite-longshot OVERPRICING is real (calibration), but it is NOT profitably harvestable: the counterparties who
overpay for wings are the same flow that front-runs the wings into the money. This is the SAME class of subtle
weighting/execution artifact as FAVLONG (clean-label) and Polymarket (optimistic-mid) -- caught by asking "what do
REALISTIC FILLS look like," which two independent agents missed. The wing candidate is DEAD as a deployable edge.
The forward paper harness (wing_paper.py, 1 ct/wing at the bid) tests the OPTIMISTIC market-weighted version; keep it
running as free forward data but it is NOT trustworthy as deploy-proof given this finding. No capital -- correctly.

## HORIZON-PIVOT (2026-07-16) — operator authorized relaxing the 15-min constraint -> daily/weekly/monthly Kalshi crypto
Operator chose path 1 (relax horizon). Rationale (validated this session): the 15m binary is efficient BECAUSE it is
fast (arbed to a martingale; slow "info not everyone has" decays before settlement). At longer horizon slow signals
operate at the bet's timescale and survive to resolution. Discovery of LIQUID longer-horizon Kalshi crypto:
- KXBTCMAXMON: MONTHLY BTC ONE-TOUCH ("will BTC touch $X this month"). VERY liquid (settled markets 100k-880k contracts,
  total 3.8M). One-touch/barrier probs are a KNOWN retail-mispricing zone (P(touch)~2*P(end-above) under GBM; retail
  underprices touch). Smart fair value from Deribit vol surface or realized vol. HIGH prior. CAVEAT: ~15 monthly events
  = LOW independent-time power; account honestly (strikes within a month path-correlated).
- KXETHD: DAILY ETH above/below, 100+ markets = more time-power, moderate volume.
- Deribit BTC options: daily/weekly/monthly expiries -> matched smart-money fair value.
- Daily/weekly BTC above/below (BTCD/BTC) = EMPTY; liquid longer-horizon BTC is the MONTHLY one-touch.
PLAN: (a) KXBTCMAXMON one-touch barrier mispricing vs GBM/Deribit fair value; (b) KXETHD daily direction/calibration;
(c) cross-market Kalshi-vs-Deribit divergence. DISCIPLINE (from the 4 killed mirages): TRADE-WEIGHTED realistic-fill
economics from the start, OOS by time, honest power/multiple-testing, independent from-scratch re-check of any positive.
PROPOSE-ONLY. Delegated test launching.

## HORIZON-KALSHI-WALL (2026-07-16) — relaxing to longer-horizon Kalshi crypto hits a DATA + EFFICIENCY wall
Tested option-1 (relax 15m constraint) on Kalshi. Findings:
- Kalshi crypto liquidity map: 15m + HOURLY (KXBTCD/KXETHD are ~1.0h tenor, NOT daily -- the "D" != daily) are liquid
  but that's the same fast/efficient regime. TRUE daily/weekly above-below series (BTCD/BTC) are EMPTY. The only liquid
  LONGER product is KXBTCMAXMON (monthly one-touch).
- KXBTCMAXMON history: only ~3 close-months (May/Jun/Jul 2026) -> ~2-3 independent macro draws. Backtest is SEVERELY
  UNDERPOWERED and in-sample NULL/negative (kalshi_onetouch.py); adverse-selection check fired (vol-wtd touch 0.115 >>
  mkt-wtd 0.033) so the harness is sound, but no trustworthy conclusion possible from 3 months. DATA WALL (markets too new).
- LIVE cross-market check (the powered angle, cross-sectional today): current KXBTCMAXMON-26JUL31 ladder (7 upside
  strikes) vs Deribit vol-implied driftless one-touch FV: mean(Kalshi_mid - Deribit_FV) = -0.006 (0.6c), mixed sign,
  ALL within the ~2-4c spread. Far longshot strikes if anything slightly RICH (+0.2c), contradicting the retail-underprice
  hypothesis. -> Kalshi monthly one-touch is priced IN LINE with the Deribit smart-money surface. No tradeable divergence.
VERDICT: relaxing the horizon on KALSHI does NOT open an edge -- the liquid longer product is both too new to backtest
AND live-efficient vs Deribit. Kalshi crypto is young: no venue-internal series has both long horizon AND many settled
cycles. The horizon-relaxation thesis is sound but needs a venue WITH longer crypto history (Polymarket has years of
daily/weekly/monthly "BTC above X by date" + wallet data) OR the maker-rebate / proprietary-data paths. Fork back to operator.

## PMKT-HORIZON-VRP (2026-07-16) — REAL short-vol/longshot risk premium on zero-fee Polymarket, but MARGINAL at realistic fills + severe tail; PROMISING not proven
Operator authorized relaxing horizon; Kalshi lacked longer-horizon history so tested on Polymarket (years of weekly
"BTC/ETH above $X on <date>", zero-fee, ~7000 settled markets / 50 weeks). Tool: pmkt_horizon.py (agent) + my independent
recompute from scratchpad/pmkt_rows.json.
- CALIBRATION: solid favorite-longshot -- far-OTM weekly longshots settle YES far below entry (e.g. [.15,.30): entry .218
  -> realized .105). Real, well-powered, mechanism-backed (short-dated OTM crypto lottery/variance risk premium).
- CROSS-MARKET vs Deribit = NULL (Brier tied, t=0.08): NOT a Polymarket inefficiency/arbitrage -- the same premium exists
  on Deribit. It is a RISK PREMIUM (paid to sell tail insurance), not free money.
- ZERO-FEE is why it's accessible: Kalshi's 0.07p(1-p) (~0.6c at p~0.1) would eat the trade-weighted magnitude.
- MY INDEPENDENT RECOMPUTE tempers the agent's enthusiasm (agent claimed trade-wtd t=5-7, favorable adverse-sel):
  VOLUME-weighted (realistic-capacity proxy) COLLAPSES it: [.03,.15) t 1.63->0.16; [.03,.30) t 2.46->1.10; only the mid
  band [.15,.30) marginally survives (t 3.45->2.26). And adverse selection is ADVERSE in my volume weighting (YES-rate
  vol-wtd > mkt-wtd everywhere) -- CONTRADICTING the agent's per-trade "favorable" claim. Discrepancy (per-trade-size vs
  per-market-volume weighting) is UNRESOLVED and is the make-or-break question.
- TAIL: worst week -0.43/ct (wipes ~10+ wks of premium), ~25% of weeks negative, printing positions lose ~0.85/ct. Classic
  short-vol blow-up profile; 49 weeks under-samples the tail.
VERDICT: the most promising result of the program -- a REAL, mechanism-backed risk premium that partially survives the
discipline that killed the 4 prior mirages -- but NOT a clean deployable edge: marginal at realistic (volume-weighted)
fills, adverse-selection sign unresolved, and carrying genuine blow-up risk. It is a RISK-BEARING trade (selling lottery/
tail insurance), not a mispricing. NOT deployable on backtest alone. Honest next steps: (1) reconcile per-trade vs
per-volume weighting on trade-level data; (2) forward paper w/ strict tail-aware (fractional-Kelly, position caps) sizing;
(3) treat expected return as thin compensation for real tail risk, size accordingly. PROPOSE-ONLY; nothing risked.

## PMKT-SHORTVOL-CONFIRMED (2026-07-16) — the short-vol longshot edge is REAL at realistic fills (my own recompute CONFIRMS; earlier "adverse" was MY weighting error)
Resolved the contested adverse-vs-favorable question with trade-level data (601 settled [0.15,0.30]-band weekly BTC/ETH
"above $X" markets, 49 weeks) + MY OWN independent recompute from scratchpad/advsel_rows.json:
- PRINT RATE: unweighted 0.1032 vs YES-BUY-taker-volume-weighted 0.0850 = -0.018 -> FAVORABLE (a resting YES seller fills
  into buy-flow that tilts toward NON-printing longshots). My earlier PMKT-HORIZON-VRP "adverse" verdict weighted by
  per-market TOTAL volume (both sides) = the WRONG object; a seller only fills YES-BUY taker flow. Corrected -> favorable.
- SELLER PnL/ct net half-spread, week-clustered: per-market equal +0.090 (t=3.73); YES-BUY-VOLUME-weighted (realistic
  fills) +0.090 (t=2.88, >2). SURVIVES realistic fills. (Unlike the WING edge, where my trade-weighting KILLED it; here
  my recompute CONFIRMS it.) Half-spread median 0.6c, p90 2.1c << the ~9c gross edge.
- TAIL (respect it): worst week -0.44/ct (~5 wks of edge), 24% of weeks negative, negatively skewed (many small wins,
  occasional correlated full-print week when BTC pumps and many longshots hit at once). MUST size fractional-Kelly + caps.
VERDICT: this is a REAL, well-powered (49 wks), execution-validated, mechanism-backed edge -- selling the short-dated OTM
crypto lottery/variance RISK PREMIUM on zero-fee Polymarket. NOT an arbitrage (Deribit cross-market null) and NOT an
adverse-selection artifact (the tie-breaker + my own recompute both clear it). It is the FIRST genuine deployable-track
winner of the entire program, real precisely BECAUSE it is a risk premium (paid to bear tail risk), not a mispricing.
Status: forward paper gate deployed (pmkt_shortvol_paper.py + workflow, accruing). Remaining to capital: forward
confirmation (~8 wks) + operator capital/Polymarket-access sign-off + fractional tail-aware sizing. PROPOSE-ONLY.

## MULTISTRAT-PROGRAM (2026-07-16) — operator: build a multi-model/multi-strategy bot; hunt STACKABLE (uncorrelated) edges across ALL data sources
Confirmed edge #1: PMKT-SHORTVOL (weekly crypto longshot risk premium, t=2.88 realistic fills). Goal now: a PORTFOLIO of
uncorrelated edges + a bot that runs them with correlation-aware (portfolio-Kelly) sizing. Stackability = low cross-edge
PnL correlation (diversifies the short-vol tail). Data sources to mine: Polymarket (all categories + wallets + trades),
Kalshi (all categories + trades), Deribit (vol surface), Binance Vision (years spot/futures/options), on-chain.
Candidate STACKABLE edges (orthogonal to crypto short-vol):
- (A) Favorite-longshot risk premium in NON-crypto Polymarket (sports/politics/econ) -- same mechanism, UNCORRELATED
  underlyings -> diversifies the tail. Highest-value stack (multiplies edge #1 across independent domains).
- (B) Cross-venue convergence (same event on Polymarket vs Kalshi vs Deribit) -- market-neutral, orthogonal to risk premia.
- (C) Smart-wallet copy on Polymarket -- alpha-following, orthogonal.
DISCIPLINE (locked in from the 4 mirages + the wing/short-vol weighting lesson): YES-BUY-taker-volume weighting (NOT total
volume) from the start, OOS, tail metrics, favorable-vs-adverse check, independent recompute of any positive, cross-edge
CORRELATION matrix (a "stack" only counts if uncorrelated). PROPOSE-ONLY paper sleeves; portfolio harness combines them.

## MULTISTRAT-ECON (2026-07-16) — CONFIRMED 2nd stackable edge: Polymarket ECON longshots (my recompute matches); + stackability proven
Cross-category longshot-premium sweep (pmkt_categories.py) + MY independent recompute from scratchpad/cat_results.json
weekly series (matches agent exactly -> reproducible):
- ECON (macro-release buckets: PPI/CPI/JOLTS/net-worth): SELL longshots [0.10,0.35]. equal-wt t=3.09 (my recompute
  matches), YES-BUY-SHARE-wt t=3.77, 400 mkts / 55 weeks, jackknife drop-1-week t in [2.89,4.82], top week only 8.4%
  of PnL, adverse-sel neutral, monotone-overpriced calibration. REAL, WELL-POWERED, robust.
  CAVEATS (honest): wider spread (2.1c vs crypto 0.6c); DOLLAR-wt t=1.90 (<2) -> edge weaker on large buys = a CAPACITY
  limit (strong selling to many small retail buyers, thinner for big size); worse tail (worst week -0.72 vs crypto -0.44).
- SPORTS: t=0.55 but 74.8% of PnL from ONE week + dollar-wt -1.66 -> NULL (correctly rejected). OTHER: t=2.44 but
  dollar-wt 0.19, 19% top-week concentration -> MARGINAL, not confirmed. POLITICS: t=-0.70, ADVERSE (YES-buy flow lands
  on printing longshots 0.177->0.311) -> do NOT sell politics longshots (discipline caught it).
- STACKABILITY (the point): CRYPTO x ECON weekly-PnL corr = -0.01 (crypto weeks 2025, econ 2024-26 macro releases =
  independent events). Adding ECON DIVERSIFIES the short-vol tail rather than doubling it. TWO confirmed uncorrelated
  edges now: crypto short-vol (t=2.88) + econ longshot (t=3.09/3.77). Portfolio forming.
NEXT: build ECON forward paper sleeve + add to portfolio.py registry; size ECON smaller (capacity + tail). Cross-venue
convergence agent still running (candidate orthogonal edge #3). PROPOSE-ONLY.

## MULTISTRAT-XVENUE (2026-07-16) — cross-venue convergence NOT a confirmed stackable edge (real but tiny/low-capacity/not-riskless)
xvenue_converge.py: matched same-event pairs across Polymarket/Kalshi/Deribit. 1,554 PM markets -> only 10 genuine
same-coin+threshold+date matches. |mid gap| mean 0.019, max 0.055; short-dated crypto gaps sub-cent/inside fees. ONE real
signal: BTC year-end touch ladder persistently 2-5c RICHER on Kalshi than Polymarket (7/7 strikes monotone; Deribit
corroborates Kalshi overpriced 8/10). BUT: one correlated cluster (n_eff~1-2, no meaningful t), NOT riskless (Kalshi vs PM
settle a 5.5-month barrier off DIFFERENT oracles -> wick can split settlement), capital locked ~5.5 months for a few cents,
and the single-leg version collapses into the longshot-RP trade (not orthogonal). VERDICT: small, low-capacity, corroborated
relative-value tilt -- NOT a robust orthogonal edge on this evidence. Not added to the portfolio. (Watch: if venue coverage
of the SAME shorter-dated events grows, revisit.)

## MULTISTRAT-STATUS (2026-07-16) — portfolio = 2 confirmed uncorrelated edges; econ sleeve needs population-matched discovery
CONFIRMED STACKABLE EDGES: (1) crypto short-vol longshot (t=2.88 realistic fills), (2) econ macro-release longshot
(t=3.09 equal / 3.77 share, my recompute matches) -- weekly-PnL corr -0.01 => genuinely diversifying. Cross-venue = no.
Sports/politics/other = rejected. ECON FORWARD-SLEEVE CAVEAT: the measured edge is on RECURRING multi-strike macro-release
BUCKETS (CPI/PPI/JOLTS/net-worth); the currently-active PM econ longshots are mostly LONG-DATED one-offs (recession-by-2026)
= a DIFFERENT population. The econ paper sleeve must discover the recurring bucket-release events specifically to faithfully
forward-test the edge (else it tests an unvalidated population). Next: build population-matched econ sleeve + hunt more
orthogonal edges (Polymarket smart-wallet copy). portfolio.py aggregates sleeves w/ correlation-aware sizing. PROPOSE-ONLY.

## MULTISTRAT-STACK-VALUE (2026-07-16) — quantified: stacking the 2 uncorrelated edges lifts risk-adjusted return +27%
Both sleeves now LIVE-accruing (crypto short-vol + econ macro-release longshots, one workflow, portfolio.py aggregates).
Quantified the stacking benefit from the backtest weekly-PnL series (crypto from advsel_rows, econ from cat_results):
- CRYPTO sleeve: weekly Sharpe 0.533 (ann ~3.85), mean +0.090/ct, worst wk -0.435.
- ECON sleeve:   weekly Sharpe 0.416 (ann ~3.00), mean +0.069/ct, worst wk -0.716.
- STACKED risk-parity (w~50/50, measured corr -0.01): weekly Sharpe 0.675 (ann ~4.87) = +27% over the best single sleeve,
  and the joint worst-week is far less likely (independent tails). THIS is the concrete payoff of the multi-strategy design:
  two uncorrelated risk premia combine to raise risk-adjusted return and diversify the blow-up, not double it.
CAVEATS: annualized Sharpes assume weekly independence + edge persists forward (the live gates test that); backtest-derived.
The ROBUST result is the RELATIVE +27% from stacking (mechanism-driven by corr~0), less so the absolute Sharpe level.
Sleeve #3 (drift/momentum, different mechanism) under test. portfolio.py will recompute the true correlation + weights as
forward settled data lands. Size fractional-Kelly per sleeve w/ per-event caps (bucket events: only one outcome prints ->
selling multiple buckets/event already diversifies within-event). PROPOSE-ONLY.

## MULTISTRAT-DRIFT (2026-07-16) — drift/reversion: real overreaction but NOT a stackable 3rd edge (not orthogonal + not robust)
pmkt_drift.py: 8,684 settled markets, 138 weeks, momentum vs reversion decided at 40%-life, held to resolution, executable
net spread, week-clustered. Reversion is the positive side (pooled +0.011 t=2.93 at hs=0.01; continuous corr(m,outcome-p_mid)
=-0.045 pooled, crypto -0.115 t=-5.08). REJECTED as a 3rd edge on TWO independent gates:
1. NOT ORTHOGONAL: reversion weekly PnL corr -0.61 with the sell-longshots series -> it BUYS fallen longshots / SELLS risen
   favorites = largely the longshot premium INVERTED, not a diversifier.
2. NOT ROBUST: move the anchor off the noisy OPENING print to a fully-interior [10%->40%] window -> corr -0.021 (CI includes
   zero), reversion net-positive 0/3 thresholds. Much of the raw effect was mean-reversion of the seeded opening quote.
   Thin net of spread (~1-2c at hs=0.01, ~0 by 2c).
INSIGHT: the durable harvestable thing in these markets is the LONGSHOT / SHORT-VOL RISK PREMIUM; the "overreaction" is
partly the same phenomenon. Genuinely-different-mechanism hunts have now hit walls (drift=non-orthogonal; cross-venue=low
capacity; wallet-copy=earlier null). RELIABLE stacking path = MORE UNCORRELATED LONGSHOT UNDERLYINGS (crypto & econ proven;
each new independent underlying diversifies even at the same mechanism). Portfolio stays at 2 confirmed uncorrelated edges.

## MULTISTRAT-SIZING (2026-07-16) — tail-first sizing layer + execution-realism fix (band on the BID, not the mid)
Built sizing.py: TAIL-FIRST position sizing (these are short-vol premia -> size for the blow-up, not the mean). Nested
hard caps: per-trade worst-case <=0.5% bankroll, per-event <=1%, per-sleeve <=15%, per-WEEK-if-all-print <=20% (the
correlated-blowup guard), scaled within caps by fractional-Kelly (crypto 0.25, econ 0.20). Outputs proposed contract sizes
per open paper position. PROPOSE-ONLY (no orders). On $1000 paper: worst-case-if-all-print 11.5%, premium $32.
EXECUTION-REALISM BUG caught + fixed: both harnesses banded on the MID; wide-spread buckets had mid in-band but a near-ZERO
BID -> selling there collects ~0 premium but bears full print risk (NOT the measured edge, which entered ~0.22 mid). Fixed:
band now on the EXECUTABLE SELL PRICE (bid) in [band] AND spread<=0.06, so entry ~ backtest mid. Re-snapshotted econ clean
(24 positions, sell 0.10-0.34). Bot stack now: 2 confirmed uncorrelated edges (crypto+econ, +27% stacked Sharpe) -> harnesses
(bid-band, first-half, zero-fee, tail-gated) -> portfolio.py (gates + correlation + risk-parity weights) -> sizing.py
(tail-first nested caps + fractional-Kelly). All PROPOSE-ONLY paper; forward gates accruing; live capital = operator sign-off.

## MULTISTRAT-BUSINESS (2026-07-16) — 3rd stackable sleeve (BUSINESS/COMPANIES longshots), but MARGINAL: add & forward-gate, size smallest
Vertical sweep (pmkt_verticals.py) across geo/business/techai/weather/ent/sports-splits. Only BUSINESS passed the two-part
gate (real + uncorrelated). MY recompute: equal-wt t=1.68 (matches agent) -- NOTE <2; clears only via YES-BUY-SHARE-wt
t=2.28 (favorable adverse selection: share-wt print rate 0.032 << unweighted 0.076), jackknife-min 2.04, drop-best-week 2.04
(not one-week-driven, top week 14%), monotone-overpriced calibration. 394 mkts / 21 weeks (just clears power bar). corr to
CRYPTO +0.07, to ECON +0.07 (both <0.3 -> stacks). HONEST CAVEATS: equal-wt<2, DOLLAR-wt t=0.48 (~0 -> strong capacity
limit; edge is on many small retail buys, near-zero for big size), wider spread (2c), worst week -0.80, only 21 weeks ->
the FORWARD GATE is decisive, not the backtest. -> ADD as sleeve #3 but SIZE SMALLEST (lowest Kelly frac) and flag marginal.
7/8 verticals REJECTED (discipline held): TECHAI/ENT/WEATHER/NBA = tail mirages that collapse under YES-buy-vol weighting
(equal-wt looked good); GEO/NFL adverse-selected; SOCCER genuinely absent. Confirms the durable edge = longshot premium on
INDEPENDENT DOMAINS; the reliable stack is now crypto + econ + business (3 uncorrelated legs). PROPOSE-ONLY.

## MULTISTRAT-3EDGE (2026-07-16) — book widened to 3 uncorrelated legs; stacked ann Sharpe 4.87 -> 5.26 (+37% vs best single)
Option-a executed: hunt uncorrelated underlyings. Now 3 live-accruing sleeves (all PROPOSE-ONLY paper, deployed):
  crypto short-vol (ann Sharpe 3.85) + econ macro-release (3.00) + business/company (2.65), pairwise corr {-0.01,+0.07,+0.07}.
Risk-parity stack (w~0.36/0.37/0.27): weekly Sharpe 0.729 = ann ~5.26, +37% over the best single sleeve. Adding the
MARGINAL business leg still lifted the 2-edge stack (4.87 -> 5.26) -- the point of stacking: each UNCORRELATED leg, even a
weak one, raises risk-adjusted return + diversifies the tail. Bot now: 3 sleeves -> harnesses (bid-band, first-half, zero-fee,
tail-gated) -> portfolio.py (gates+corr+risk-parity) -> sizing.py (tail-first caps + per-sleeve Kelly, business smallest).
CAVEATS (honest): absolute Sharpes backtest-derived + assume weekly independence; business is marginal (fwd gate decisive);
the ROBUST result is the +37% RELATIVE lift (driven by ~0 cross-corr). Remaining untested verticals were rejected (7/8) or
absent -> the durable edge is the longshot premium across independent domains; crypto/econ/business are the liquid ones that
carry it uncorrelated. Next widening candidates thinner. Forward gates accrue; live capital = operator sign-off.

## RISKLESS (2026-07-16) — taxonomy + live scan: real arbs are RARE/SMALL; the genuine one is Polymarket bucket-underround
Enumerated riskless structures: (1) YES+NO ask-sum<1 within a market; (2) exclusive-exhaustive bucket set sum(asks)<1
buy-all / sum(bids)>1 sell-all; (3) ladder monotonicity bid(hi-strike)>ask(lo-strike); (4) vertical/butterfly; (5)
cross-venue same-event (already: rare, diff oracles); (6) decided-but-unresolved. Built riskless_scan.py (READ-ONLY).
FINDINGS (with a fixed scanner + executability filters -- FIRST pass had bugs: inverted ladder direction + treating
cumulative 'above X' ladders as exclusive buckets -> false positives, corrected):
- KALSHI ladder "violations" = STALE-QUOTE ARTIFACTS on thin hourly books (e.g. 'BTC>$63,900' ask 0.09 while spot ~$64k
  is nonsensical). Summary bid/ask not executable; a real scanner needs the live /orderbook + real arbs ~absent on liquid mkts.
- POLYMARKET EXCLUSIVE-BUCKET UNDERROUND = GENUINE (zero fee). VERIFIED live: GDP-2026 (6 exhaustive buckets <0.5..>2.5)
  sum(asks)=0.940 -> buy-all = +6.0c/$1 riskless; Fed-Oct (5 buckets) sum=0.979 -> +2.1c; Fed-cuts sell-all +0.7c.
  These are REAL but: SMALL (2-6c), CAPITAL-LOCKED to resolution (GDP-2026 -> months; ~12%/yr), LOW CAPACITY (bounded by
  thinnest leg's depth), and carry LEG/STRAND RISK (partial fills -> directional) = the SAME stranding problem as box bets.
VERDICT: riskless arbs EXIST but are rare/small on liquid markets (MMs enforce no-arb); the harvestable one is a CONTINUOUS
Polymarket bucket-underround scanner + fast ATOMIC multi-leg execution. Genuinely UNCORRELATED (it's arbitrage, not a risk
premium) -> a candidate 4th sleeve. Caveat: leg-risk makes it near-riskless not truly riskless without atomic fills.

## STRAND-MODEL (2026-07-16) — rich-feature ML does NOT beat a simple moneyness rule; strands are a LOPSIDED-MARKET effect
Built strand_model.py: join box_shadow strand labels (ws,asset,stranded; 1,469 live-arm windows btc+eth, 133 strands =
9.05% base) to causal tick features, time-OOS (6d train / 3d test), logistic + GBT. My independent check of results.json
CONFIRMS the headline:
- OOS AUC: logistic 0.635, GBT 0.617 (weak, CI>0.5). A SINGLE feature BEATS the ensemble: univariate OOS AUC rel_strike
  0.715, spread 0.709, |mid-0.5| 0.705 -- all > multivariate. Rich features (book depth, imbalance, rvol 0.56, recent_move)
  add OOS NOISE. Small n (133 events) -> the GBT/logistic OVERFIT.
- CAUSAL STORY (new, contradicts prior heuristics): strands are a LOPSIDED-MARKET / moneyness phenomenon -- when price moves
  OFF the strike, the off-side leg sits where nobody trades and never fills. NOT thin-book / high-vol / near-strike-movement.
  The deployed arms volgate & nsmove are COUNTERPRODUCTIVE here (kept-strand rate ABOVE no-veto baseline).
- VETO TRADEOFF (OOS, matched 20-25% veto): a one-line |mid-0.5| veto BEATS both the ML model and the heuristics
  (kept-strand 9.3%->~6-7%, retains ~77-81% of good fills). But lift is SMALL -- not enough to rescue the ~zero-edge box.
VERDICT (answers the operator's Q2): rich data does NOT build a materially better strand model; ship a PLAIN |mid-0.5| /
|spot-strike| threshold, not ML, and retrain as days accrue. The moneyness signal is real & worth using as a box veto AND
(principle, not the exact feature) as a reminder to check leg-fill probability before committing multi-leg arbs. The box
stays halted (lift too small); the useful artifact is the simple moneyness veto + the corrected causal understanding.

## RISKLESS-CAPACITY (2026-07-16) — riskless bucket-arb is REAL but NEGLIGIBLE in $; thin-leg DEPTH is the binding constraint
Studied "how much riskless money is actually there" using REAL CLOB book depth (not stale gamma summary quotes).
Direct verification of the two live arbs:
- GDP-2026: sum(CLOB ask)=0.960 -> edge +4.0c/$1, but thinnest leg = 11 shares -> CAPTURABLE = $0.43 (deploy ~$10.6,
  capital-locked ~5.5 months to resolution -> rate ~9% annualized riskless but $0.43 ABSOLUTE).
- Fed-Oct: sum=0.989 -> +1.1c/$1, thinnest leg 75 shares -> CAPTURABLE = $0.82 (deploy ~$74, ~3mo -> ~4%/yr).
BINDING CONSTRAINT = THIN-LEG DEPTH, not the edge. Deep events (Fed) have sums barely under 1 (tiny edge); the bigger
edges (GDP 4c) sit on thin legs (11 shares). Total capturable across the live arbs ~ $1.25.
VERDICT: riskless money is REAL (confirms the structure + the framework) but NEGLIGIBLE in absolute $ (single dollars per
snapshot, capital-locked for months). The RATE (~5-9%/yr riskless) isn't nothing, but capacity (~$10-75/arb, few arbs) makes
absolute profit trivial. DO NOT build a fast execution engine for it or allocate meaningful capital -- keep bucket_arb as a
FREE opportunistic add-on (the deployed sleeve already scans + self-validates). The 3 LONGSHOT RISK PREMIA remain the profit
engine (real capacity + ~+20-25%/mo expected at scale, at the cost of bearing the tail). Riskless-arb capped this thin is a
known property of liquid prediction markets: MMs keep the overround >=~1, so underrounds are rare, small, and shallow.
Caveat: full multi-hundred-event enumeration timed out; a handful more small arbs may exist but the depth ceiling applies to all.
