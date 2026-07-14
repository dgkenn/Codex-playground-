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
