# Strategy Farm — GitHub → OOS test → refine/stack (goal: 10%/day-stack, Kalshi-deployable)

**Operating loop (the operator's angle, 2026-07-18):**
1. **Farm** public GitHub for prediction-market strategies AND new data sources.
2. **Test** each on OUR aggregated data as strict **out-of-sample** (walk-forward, week-clustered t, multiple-testing haircut, executable prices — the discipline that killed ~18 candidates).
3. **Refine & stack** the survivors (a strategy only earns a sleeve if it's real OOS *and* adds uncorrelated PnL).
4. **Mine GitHub for solutions** whenever we hit a blocker (data gap, fill model, execution, pricing).
5. Bias toward **Kalshi-deployable** edges (that's where we trade), but take real edges wherever they are.

**Honesty rail:** every result recorded in `DECISION_MAP.md`, nulls included; no fabrication; PROPOSE-ONLY until a human authorizes capital. I am the scorekeeper — I report what the stack *actually* delivers vs the 10%/day target.

## Data sources farmed (DECISION_MAP: DATA-SOURCE-FIND, GITHUB-ARCH-FIND)
- **Polymarket data-api `/trades`** — real per-market trade prints (side/price/size/ts/outcome/wallet). SURGICAL, in use.
- **Jon-Becker/prediction-market-analysis** — 36GB Poly+Kalshi trade-level archive (full history; monolithic download).
- **Oddpool/PredictionMarketBench** — Kalshi replay data + backtest benchmark.
- **Kalshi public API** — live (we cache `.kalshi_cache`).
- Binance Vision (years crypto), Deribit (options/DVOL) — already exploited (efficient).

## Architecture farmed
- **homerun** — Cox fill model + L2 replay backtester + shadow→live triangulation (our charter productized). Fill model being prototyped (`fill_model.py`).
- **oracle3** — Wang Transform longshot-pricing (being tested as selection overlay). Also: premium-decay, exclusivity-arb strategies.
- **flumine** — mature OMS patterns (Betfair; Poly/Kalshi roadmap-only). **pmxt / pykalshi** — go-live execution clients.

## Strategy backlog (to test OOS, ranked by prior × Kalshi-deployability)
| # | Strategy (repo) | Idea | Kalshi? | Prior | Status |
|---|---|---|---|---|---|
| S1 | Wang Transform (oracle3) | distortion model → sharpen longshot selection | yes | — | **DONE — NULL (4th selection null)** |
| S2 | Cox fill model (homerun) | realistic maker fill-prob → honest capture | yes | — | **DONE — capture ~40% (+0.048/ct), ~$3-1235/wk, brutal tail; reusable arch** |
| S3 | Print-level re-confirm (data-api) | confirm +0.12 edge OOS on real prints, full history | — | high | **DONE ✓ CONFIRMED** |
| S4 | Earnings beat-rate (dragonbear666) | corp earnings vs Kalshi implied-prob divergence | **KALSHI** | — | **DONE — NULL (instrument barely exists; calibrated; fee-killed)** |
| S5 | S&P daily brackets (quantgalore/kalshi-trading) | Kalshi S&P 500 daily bracket system | **KALSHI** | — | **DONE — NULL (priced ~1pt)** |
| S6 | Weather ensemble (suislanchez) | 31-member GFS ensemble → Kalshi KXHIGH temp | **KALSHI** | low (weather-info null, but ensemble differs) | QUEUED |
| S7 | homerun 25+ built-ins (copy/arb/AI-score) | scan for any with OOS edge | both | low-med | QUEUED |
| S8 | Premium-decay (oracle3) | distortion decays toward resolution → entry timing | yes | low (first-half already best) | QUEUED |
| S9 | **Edge portability to Polymarket US (QCX)** | does the short-vol edge exist on the LEGAL US venue? | **legal-PM** | — | **DONE — QCX is SPORTS-ONLY; crypto edge has no market there** |
| S10 | **QCX sports pricing efficiency** | is the new legal QCX venue mispriced vs sharp book / Kalshi / Global? | **legal-PM** | — | **DONE — NULL (tracks sharp lines ~1.3c; fee kills it; closes QCX)** |
| S11 | **De-risk short-vol** | cap the -70% tail | technique | — | **DONE — verticals overpriced; fix = per-week gross cap + corr-aware sizing (worst -25% @ ~2.7%/wk)** |

## Results (OOS verdicts) — see DECISION_MAP for detail
_K-WX weather-nowcast: **CONFIRMED** (deep n=35, margin=2, +0.168/ct, t=4.60 Bonferroni-sig, worst-case EV+); FIRST legal Kalshi edge (small ~$1.2k/wk). Refinement in progress. SHORT=null._
| strategy | OOS verdict | stack? |
|---|---|---|
| S3 print-reconfirm | **CONFIRMED** — +0.121/ct trade-wt t=4.17 over 49 wks real prints; maker-only; ~$9k/wk flow | engine (Global, NOT legal-US) |
| S1 Wang selection | NULL — 4th selection null; edge unconditional | no |
| S5 Kalshi S&P brackets | NULL — priced ~1pt | no |
| S4 Kalshi earnings | NULL — instrument barely exists, calibrated, fee-killed | no |
| S9 QCX portability | BLOCKED — QCX is sports-only; crypto edge has no market there | n/a |

## LEGAL CONSTRAINT (2026-07-18)
US-legal venues only: **Kalshi** (clean) + **Polymarket US / QCX** (CFTC DCM, KYC+USD). **Polymarket GLOBAL is NOT legal
for US** (geoblocked 2022) — our confirmed +0.121/ct edge is validated THERE, so it is proven-but-not-US-deployable until
we confirm it PORTS to Polymarket US (QCX). Do not evade geoblocks. Primary = Kalshi-native edges; test QCX portability.

## KALSHI-ONLY PIVOT (effective after S10/S11 land, per operator 2026-07-18)
Farm + goals CONSTRAINED TO KALSHI ONLY going forward. Rationale: Polymarket Global = illegal US; Polymarket US/QCX =
sports-only. Kalshi is the one clean, legal, full venue. CONSEQUENCE: the confirmed crypto short-vol edge (Polymarket) is
SHELVED as non-deployable (kept as research/technique); the hunt resets to a NEW Kalshi edge. HONEST STATE: Kalshi has been
calibrated/NULL across everything farmed (longshot, index brackets, earnings). Hard venue. Untried Kalshi-only angles below.

### Kalshi-only backlog (to farm next)
| # | Kalshi angle | why it might work / untested |
|---|---|---|
| K1 | Kalshi MAKER-REBATE MM (CFTC rebate formula) | UN-KILLED (distinct from Poly LP-pool); ref: aasuper1/kalshi-alpha-strategies; net-of-adverse-sel |
| K2 | Kalshi structural NO-ARB (ladder-mono + complement-sum + range-sum) | **TOP candidate**; 3 ref impls (Hulkmode85/Dbentley142/oracle3); math-provable, free data; caveat: Poly ver was NULL (stale quotes)+1.75% fee |
| K3 | Kalshi NEW-LISTING mispricing | ref impl djmorgan26 (<48h, spread>=6c, 48h converge); day-scale patience play |
| K4 | Kalshi SPORTS vs sharp book / vs QCX-Global | Kalshi now lists sports; is it mispriced vs de-vigged lines? (legal, uncorrelated) |
| K5 | Farm GitHub Kalshi bots (ryanfrigo, Krypt-Trader, quantgalore, homerun-Kalshi) → OOS test each on Kalshi data | direct strategy transfer |
| K6 | Kalshi settlement-timing / decided-but-unresolved capture | Kalshi's fixed close/settlement mechanics |
| K7 | Kalshi FAVLONG revisit (favorite-longshot on Kalshi tenors) | prior program work; re-test net-of-fee on current data |
| K9 | Theta-decay curve mispricing (homerun) | price vs sqrt-time decay curve to 0/1; trade >7% deviation; multi-day |
| K8 | **Fill data holes from GitHub (high-leverage unlocks)** | see K8 data targets below — prioritize deep history + sharp lines |
Discipline unchanged: NET of Kalshi fees always (the recurring killer); executable prices; cluster t; multiple-testing; honest nulls.


### K8 data targets (found 2026-07-18, ranked by leverage)
1. **DEEP KALSHI HISTORY (fixes our #1 weakness = short API window starving t-stats):**
   - Jon-Becker/prediction-market-analysis — full Kalshi trades (taker_side) + markets (result), retrospective (36GB monolithic; extract Kalshi slice).
   - PCeltide/snapevent (Rust) — Kalshi L2 order books + trade tape -> Parquet, deterministic replay (FORWARD collector; start now to build our own depth history).
   - vcorp-dev/kalshi-price-data — DepthFeed aggregator: yes/no prices, full order-book depth, price history (verify if real history vs paid).
2. **SHARP CONSENSUS SPORTSBOOK LINES (unlock for K4 sports):** TheRundown API — 16+ sportsbooks + Kalshi, free tier. Far better 'truth' than single-book ESPN.
3. **STRUCTURAL SCANNER + fee math (jumpstarts K2):** Dbentley142/kalshi-bot-toolkit — structural mispricing scanner, fee-aware, keyless.
4. **WEATHER GROUND-TRUTH (if weather revisited):** mostlyright-sdk — METAR/ASOS/GHCNh/NWS-CLI + Kalshi settlements.
5. **ECON DIVERGENCE (econ signals):** emmett-hannam/economic-signals-framework — 50+ sources (FRED/BLS/GDELT) vs prediction markets.
6. Strategy sources to farm (K5): ryanfrigo/kalshi-ai-trading-bot, OctagonAI/kalshi-trading-bot-cli, djmorgan26/Invest (10 strats x 40k mkts), homerun Kalshi strategies.
PRIORITY: #1 (deep history) is the biggest unlock — it converts our null-with-thin-n results into properly-powered tests; #2 sharpens K4.


## K-WX REFINEMENT PLAN (execute IF deep-history confirms, per operator 2026-07-18)
Make the weather-nowcast the best-possible strategy. Priority:
1. SHRINK THE TAIL (loss=free-ASOS>official-CLI): (a) multi-source obs agreement (METAR + 1-min ASOS + 6-hr max) before firing; (b) require SUSTAINED above strike (N min, not a 1-min spike — the Miami loss); (c) per-STATION margin calibrated from that station's historical ASOS-vs-CLI bias.
2. OPTIMIZE margin/entry-timing (gap vs fillability) + tail-aware Kelly sizing + CROSS-CITY correlation (heat waves fire many cities together → size as correlated).
3. EXTEND: full KXHIGH bracket ('between X,Y' once obs clears X); optional forecast-assisted early-entry spectrum (earlier=bigger gap+more risk).
4. FORWARD PAPER GATE (tested==live) before any sizing.
Deploy only after: adequate n, honest tail acceptable, forward-gate-confirmed.

## Confirmed stack so far
Polymarket weekly crypto short-vol (+0.12/ct, engine) + ECON (uncorrelated, small) + biz (marginal) + bucket-arb (riskless, tiny).
Frontier ~0.3–1%/day sound. Kalshi short-vol = NULL (calibrated) → Kalshi edges must come from S4–S6 (earnings/S&P/weather) or structural, not longshot-selling.
