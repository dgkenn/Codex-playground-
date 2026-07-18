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
| S2 | Cox fill model (homerun) | realistic maker fill-prob → honest capture | yes | n/a (engineering) | TESTING |
| S3 | Print-level re-confirm (data-api) | confirm +0.12 edge OOS on real prints, full history | — | high | **DONE ✓ CONFIRMED** |
| S4 | Earnings beat-rate (dragonbear666) | corp earnings vs Kalshi implied-prob divergence | **KALSHI** | — | **DONE — NULL (instrument barely exists; calibrated; fee-killed)** |
| S5 | S&P daily brackets (quantgalore/kalshi-trading) | Kalshi S&P 500 daily bracket system | **KALSHI** | — | **DONE — NULL (priced ~1pt)** |
| S6 | Weather ensemble (suislanchez) | 31-member GFS ensemble → Kalshi KXHIGH temp | **KALSHI** | low (weather-info null, but ensemble differs) | QUEUED |
| S7 | homerun 25+ built-ins (copy/arb/AI-score) | scan for any with OOS edge | both | low-med | QUEUED |
| S8 | Premium-decay (oracle3) | distortion decays toward resolution → entry timing | yes | low (first-half already best) | QUEUED |
| S9 | **Edge portability to Polymarket US (QCX)** | does the short-vol edge exist on the LEGAL US venue? | **legal-PM** | — | **DONE — QCX is SPORTS-ONLY; crypto edge has no market there** |
| S10 | **QCX sports pricing efficiency** | is the new legal QCX venue mispriced vs sharp book / Kalshi / Global? | **legal-PM** | med (new/thin venue) | TESTING |

## Results (OOS verdicts) — see DECISION_MAP for detail
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

## Confirmed stack so far
Polymarket weekly crypto short-vol (+0.12/ct, engine) + ECON (uncorrelated, small) + biz (marginal) + bucket-arb (riskless, tiny).
Frontier ~0.3–1%/day sound. Kalshi short-vol = NULL (calibrated) → Kalshi edges must come from S4–S6 (earnings/S&P/weather) or structural, not longshot-selling.
