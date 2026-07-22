# RESEARCH_LEDGER — K-WX Central Verdict (2026-07-22)

## 1. ONE-LINE STATUS + HONEST CAPACITY BOTTOM LINE

**$4,000/month goal: NOT REACHABLE at any bankroll tested (up to $50k) under current levers, in ANY scenario (conservative, conservative_live, base, optimistic).** (`PATH_TO_4K.md`, corrected model post two-judge review.)

- **Validated today (conservative_live, live-observed fill rate — 0 fills / 39 near-misses on the night measured, 0 fills cumulative since):** ~$146–149/mo (~3.7% of goal). Today's live `kwx_portfolio.py status` run: $146/mo at $2k, $148/mo at $10k; `PATH_TO_4K.md` digest: $147–$149/mo.
- **Deployed ceiling (conservative, backtest fill rates, depth-capped):** ~$1,047–$1,318/mo (26–33% of goal) — essentially flat past $500 bankroll, fixed DEPTH_CAP=25 binding at every bankroll tested up to $50k. Today's live status run: $1,319/mo at $2k, $1,311/mo at $10k.
- **Best-case scenario (optimistic, all assumed-gate sleeves, $50k bankroll, 90-day horizon):** ~$1,173+/mo (29% of goal), marked `+` because it depends entirely on unvalidated assumed sleeve accrual rates.
- **Live reality (verified this session):** 0 settled fires since switch-on 2026-07-18T20:23Z (~4 days with `KWX_SWITCH=on`); 189 near-misses logged 2026-07-20..22, every one `reason:"ask>98"` (repriced before capture); 26 near-misses today (2026-07-22).

---

## 2. WHAT'S LIVE / DEPLOYED (the blunt reality)

| Component | Status | Evidence |
|---|---|---|
| taker_mechanical | LIVE ($10 canary) | KWX_SWITCH=on, 0 fires observed; backtest baseline: +1.1c/ct at ~98c entry, ~99.6% win |
| stacking | VALIDATED, DEPLOYED | wx_rung_stacking verdict: KEEP CURRENT (confirmed in live registry) |
| station_derate_relax | DEPLOYED 2026-07-18 | kwx_runner.py recalib removed KLAX/KMIA/KPHL/KSEA derates (KPHX retains 0.5x) |
| book_watch | LIVE but NULL | 0 attributed fires (gate 0/30, accrual 0.0/day); WX_NEARMISS_DIAGNOSIS: near-misses are adverse-selected, the assumed 7.8/day conversion is refuted and zeroed in p4k_params.json; stays deployed only as a costless residual catcher |
| Synoptic feed | BOOTSTRAP READY | Encrypted credential pipeline committed, trial pending; go/no-go on the paid tier at trial_start+14d using measured latency uplift |
| **Fires since switch-on (2026-07-18)** | **0** | 0 settled; 189 near-misses logged 2026-07-20..22, all `ask>98`; halt switch off |

---

## 3. THE GRAVEYARD — Every Tested Strategy & Its Verdict

| # | Strategy | Study | Verdict | Key Number | Mechanism That Killed It |
|---|---|---|---|---|---|
| 1 | Maker (post-lock resting bids) | wx_maker_deep_study.md | REFUTED | 2 confirmed (+1 possible) genuine fills (vs 22.5 claimed) across 65d×20 stations | Marketability flaw: 26/32 audited P=93 bids had best ask ≤93c at placement (instant taker fills, not resting maker orders) |
| 2 | Early-lock (tail capture) | wx_earlylock_deep_study.md | NULL | Headline +1.43c, t=0.28; best n≥5 +2.52c, t=0.35 | 36 nominal grid cells collapse to 27 effectively distinct; Bonferroni bar is \|t\|≥3.11 and best is 0.35σ noise; headline cell sign-flips +9.6c→−8.1c across sample halves |
| 3 | Directional SPEC 1 | WX_DIRECTIONAL.md | INSUFFICIENT | n=17 entries vs ≥200 floor | Market too young (67 days, 1 warm season); reopens with deeper history |
| 4 | Directional SPEC 2 (MOS revision fade) | WX_DIRECTIONAL.md | KILL | n=815, mean EV −$0.0255, t=−3.16 | Event-vs-control comparison ≈0: signal has zero info beyond unconditional control |
| 5 | Directional SPEC 3 (thin-book longshot) | WX_DIRECTIONAL.md | INSUFFICIENT | n=84 entries vs ≥300 floor | Thin-liquidity filter defines the strategy; too few qualify |
| 6 | Directional SPEC 4 (intraday nowcast lag) | WX_DIRECTIONAL.md | FAIL | n=2,109, t=−4.05, Wilson-LB win 16.7% vs 21.7% breakeven | Seasonal drift: R-distribution fit on TRAIN (spring/early-summer) fails on TEST (full-summer warming trend) |
| 7 | Directional SPEC 5 (order-flow drift) | WX_DIRECTIONAL.md | FAIL | n=525, Wilson LB 75.4% vs 82.1% breakeven, t=−1.81 | Rich entry prices (mean $0.80, often $0.95+); yes-side actively anti-predictive (28.9% win rate) |
| 8 | Directional SPEC 6 (ladder arb) | WX_DIRECTIONAL.md | FAIL + INSUFFICIENT | n=110, fill rate 19.7% (need ≥60%) | Quote staleness/thin-book noise, not durable arb; bid-ask spread eats the correction |
| 9 | Directional SPEC 7 (salient anchoring) | WX_DIRECTIONAL.md | NO-SIGNAL | Only 2 of 5 price bins reached the ≥20-sample floor; 1 cleared \|gap\|≥0.04 vs a required 3-of-5 sign agreement | Bar structurally unreachable from the TRAIN slice; not disproven, just underpowered |
| 10 | Directional R4-1 (climate long-lead) | WX_DIRECTIONAL.md | FAIL | 0 two-sided quotes at 48h/72h/120h lead | Market structure ceiling: KXHIGH only lists 39–42h before close; market doesn't exist at ≥48h |
| 11 | Directional R4-2 (upwind advection) | WX_DIRECTIONAL.md | FAIL | 0/556 theta cleared breakeven | Timing-artifact signal: partial-day running max vs full-day forecast max, not a genuine bias |
| 12 | Near-miss conversion (fill lag fix) | WX_NEARMISS_DIAGNOSIS.md | NULL | Median lock→detection 410 min (mixes outage backlog); steady-state 8.1 min (feed-bound) | Market pushed no_ask above 98c BEFORE the lock rule fired in 10/10 sampled tickers (median −106 min); ~0% of the 52 near-misses convertible by feed/leg/watcher fixes, theoretical upper bound ≈2–4% (2/10 close-call samples) |
| 13 | Expansion: Sports totals | WX_EXPANSION.md | NOT PROMISING | Median lag 0.0s, EV +$0.0296/ct (below $0.05 bar) | Fast bots watch scoreboards; mechanical shape real but window is ~zero |
| 14 | Expansion: Earnings/Gutfeld mentions (Family 2) | WX_EXPANSION.md | PROMISING-WEAKENED | Confirm-gated EV ≈+$0.05/ct (6x below +$0.316 claim) | Look-ahead flaws: hindsight best-price entry; "ask≥98c" lock detector conditions on the answer (29/30 NO markets also hit max_ask≥0.98) |
| 15 | Expansion: Earthquake magnitude | WX_EXPANSION.md | NOT PROMISING | Only 2 real M6.8+ events, freq 0.077/day | USGS magnitude revised 10–60+ min after origin; market and feed converge together, no lag |
| 16 | Expansion: Commodity ladders (WTI/NGAS) | WX_EXPANSION.md | NOT PROMISING | EV +$0.171/ct (overstated by settle-print look-ahead), freq 0.038/day hist (fails 0.5/day bar by 13x; even 2026 only 0.169/day) | Frequency is decisive; mechanism real |
| 17 | Expansion: Crypto MAX ladders | WX_EXPANSION.md | NOT PROMISING | EV +$0.0414/ct (below bar), freq 0.10/day capturable | can_close_early=true: 46% of sample repriced >1h before official close, collapsing the lag |
| 18 | Expansion: FDA drug approvals | WX_EXPANSION.md | NOT PROMISING | 0/2 verified capturable, freq 0.030/day (fails bar ~17x) | No minute-resolution public feed vs FDA's date-only record |
| 19 | Weather calibration-fade (near-certainty) | DATA_BACKED_BACKTESTS.md | FAIL (CONFIRMED) | 0/8 bins cleared FIT bar; liquid bins: high_99_100 claimed −1.50c → corrected −2.0c (worse); low_1_3 claimed −3.0c → corrected ~−1.9c | Market correctly fee-priced at near-certainty; adversarial correction made the headline bin's loss WORSE, verdict unchanged either way |
| 20 | Long-tail passive spread | DATA_BACKED_BACKTESTS.md | FAIL (CONFIRMED) | 39,220 fills / 34 days / 144 series, net −14.32c/contract, day-clustered t=−29.57 | Genuine adverse selection on realized settlement (fee only 1.77c of the loss); semi-thin band dominated by short-lived props, not attention scarcity |
| 21 | Illiquid snapshot arbs (leg-sum, nested-cutoff, stale-quote) | ILLIQUID_MARKETS.md | REFUTED | 0 fee-surviving arbitrage patterns; 0/64,829 active markets with a stale post-close quote | Bid-side leg-sum>1 is fee-negative (fees scale with Σp(1−p) per leg); no snapshot-visible stale windows |
| 22 | Illiquid r1s1 (mention anchor) | ILLIQUID_MARKETS.md | INCONCLUSIVE | n=16 vs ≥30 floor; event-days 1 vs ≥8 floor | Data retention wall: KXFEDMENTION collapses to 1 retrievable event, KXHANNITYMENTION to 2 (3 broadcast-days total); older events return `markets: []` |
| 23 | Illiquid r1s2 (off-air passive quoting) | ILLIQUID_MARKETS.md | INCONCLUSIVE + NEGATIVE | 3 event-days vs ≥10 floor; exploratory markout −2.29c (validation) to −4.57c (pooled) | Informed-counterparty risk: prints move toward truth faster than a 12c-wide passive quote tracks; adverse-selection sub-check fails everywhere computable — functionally dead |
| 24 | Illiquid r1s3 (jobless-claims relist) | ILLIQUID_MARKETS.md | INCONCLUSIVE | 10 reachable Thursdays vs ≥15 floor (exploratory n=29 over 7 Thursdays, uninterpretable) | Data wall: /events lists 47 settled events but 37 return `markets: []`; only 10 servable |
| 25 | Stacked r1s1 (broadcast-mention siblings) | STACKED_EDGES.md | CONFIRMED FAIL | n=265 settled/88 entries, win 97.7% but net EV −$0.0178 flat / −$0.0420 day-clustered, t=−1.25 | Reactive-entry ceiling: fires only after book at 0.90–0.99; one false lock (~−$0.95/ct) erases dozens of ~$0.01 wins |
| 26 | Stacked r1s2 (KXJOBLESSCLAIMS AR(1)+MA nowcast) | STACKED_EDGES.md | CONFIRMED FAIL (underpowered pre-registered kill) | 10 of 28 TEST weeks servable vs ≥60-week gate (~10-week retention wall) | Underpowering is a kill per protocol; informational point estimate negative and worse-calibrated than market anyway |
| 27 | Stacked r1s3 (cross-venue reprice race) | STACKED_EDGES.md | CONFIRMED FAIL/UNTESTED | 1 surviving Kalshi-vs-Polymarket pair; 0 triggered entries | History purge leaves n=1; both venues already at ~0.99/0.997 through the announcement window |
| 28 | Stacked r2s1 (crypto cross-venue lead-lag) | STACKED_EDGES.md | FAIL (preflight self-kill) | 0 reconcilable single-instrument pairs (BTC and ETH both confirmed) | Kalshi $100-wide hourly BRTI strikes vs Polymarket strike-less/$2,000-wide Binance-close brackets — nothing matches |
| 29 | Stacked r2s2 (macro-surprise pass-through drift) | STACKED_EDGES.md | N-GATE INSUFFICIENT | ~31 TEST events vs ≥40-event/≥3-family bar | Genuine insufficient: mechanism preflight PASSED (10/10 releases clear liquidity bar) but hypothesis never tested |
| 30 | Favorite-longshot bias Spec 1 (broad longshot fade, ex-crypto ex-weather) | FAVORITE_LONGSHOT.md | CONFIRMED FAIL | n=2,958/2,189 events/256 days; realistic-crossing net EV −3.41c/ct, day-clustered t=−4.87, 95% CI [−5.16c,−1.66c]; honest capacity **−$60/mo** | Entry-realism kill: naive signal edge only +1.70c, crossing-price slippage costs 3.18c — same spread-eats-the-edge death mode as the long-tail passive-spread study (#20); negative in all 3 categories and both persistence halves |
| 31 | Favorite-longshot bias Spec 2 (favorite buy, 70–90c band, ex-crypto ex-weather) | FAVORITE_LONGSHOT.md | CONFIRMED FAIL (execution-limited, not measured-negative) | Candidate universe built clean (383,553 markets); trade-tape join (candidates × 9 shards, ~172M trades) did not complete in economy-mode budget (confirmed on rerun, 170s+ no output) | No verifiable P&L exists to certify — scored deployable=NO / capacity $0/mo by the can't-ship-what-can't-be-checked rule, not a disproven edge; re-run methodology preserved in `scratchpad/flb/bt2/05_join_trades.py` for a future longer-budget attempt |
| 32 | Favorite-longshot bias Spec 3 (crypto isolation, 5–45c) | FAVORITE_LONGSHOT.md | CONFIRMED FAIL | n=118/40 events/33 days vs ≥200-event/≥60-day pre-registered floor (hard population ceiling 84 events); T24 mean −4.17c/ct, t=−0.64, CI crosses zero; ex-worst-day mean = exactly $0.00 | Structural sample ceiling (Kalshi crypto verticals are intraday/hourly, 24h-lead filter starves the sample) plus one bad day (2026-01-02) driving the entire net loss — no persistent edge either sign |
| 33 | Favorite-longshot bias — maker (resting-bid) capture across the liquid universe | MAKER_FAVLONG.md | CONFIRMED FAIL | Two independent backtests (category/band @ print price, split 2025-12-28; liquidity-tier pooled favorite, split 2024-07-01) reconcile to a null: overlap point estimate +0.4 to +1.3c/ct, day-clustered t≈0.6, CI crosses zero; capturing real volume requires bidding 80–90c where pnl is −7 to −18c/ct; honest capacity **$0/mo** | Fill realism, not adverse selection, is the binding kill: Study B's nominally "significant" thin-tier cells are unweighted per-fill means in illiquid markets with fit→validation sign flips (classic favorite-longshot bias surviving only where there's no capacity); adverse-selection conditioning itself is honest in both pipelines. Side finding: sports vertical (dominant category) now charges a maker fee (`quadratic_with_maker_fees`, ~0.33c/ct), correcting a stale $0-maker-fee assumption inherited from the weather-only `wx_maker_deep_study.md` |
| 34 | Per-series last_price screen (144 series) → realistic-entry retest of the 5-series shortlist | PER_SERIES_SCAN.md | CONFIRMED FAIL | Step 1: 144 series Bonferroni-screened (α=3.47e-4), 5 survivors (KXBTC/KXETH/KXNFLFIRSTTD/KXINX/KXNFL), all −4.3c to −10.7c last_price bias, highly significant fit+val. Step 2 (real crossed-spread NO-taker fills, fee-inclusive, day-clustered, 3/9 archive shards = 13–22 real trading days per series, 18.4M fills): all 5 collapse to \|t\|<2.2, none survives Bonferroni-over-5 or is weighting-stable; capacity was never the constraint (KXBTC $406k/day notional) | Same two artifact mechanisms already in this graveyard reproduce exactly: stale-`last_price` on expire-worthless above-strike markets (KXBTC/KXETH/KXINX, same mechanism as #19/#20), and a `^[A-Z]+`-regexp family-conflation bug that mixes heterogeneous sub-products under one "series" (all 5 — visible as violent sign flips across entry-price buckets, e.g. KXINX −32.3c to +25.0c) |

**Summary of graveyard:**
- **Refuted (actively disproven):** Maker (post-lock weather), maker (favorite-longshot resting-bid, all liquid categories), near-miss conversion, illiquid snapshot arbs, weather calibration-fade, long-tail passive spread, stacked r1s1, per-series last_price shortlist at realistic entry
- **NULL (indistinguishable from zero after correction):** Early-lock (historical), directional funnel as a whole
- **FAIL (decisively negative or structurally closed):** Directional SPECs 2/4/5/6, R4-1 (lists only 39–42h ahead), R4-2, stacked r1s2/r1s3/r2s1, favorite-longshot Specs 1/3
- **NOT PROMISING (structural frequency/latency fails, archived):** Expansion sports, earthquakes, commodities, crypto, FDA
- **Insufficient/inconclusive (underpowered or data-walled, not disproven):** Directional SPECs 1/3/7, illiquid r1s1/r1s2/r1s3, stacked r2s2, favorite-longshot Spec 2 (join infra limit, not disproof)
- **Weak survivor (open, gated):** Expansion Family 2 mentions — PROMISING-WEAKENED, ~$18/mo defensible, see §4

---

## 4. WHAT'S STILL OPEN (Genuinely Unresolved)

| Item | Status | Evidence | Next Step |
|---|---|---|---|
| **Forecast-overlay sleeve** | ❌ REFUTED (2026-07-22, FORECAST_OVERLAY_BACKTEST.md, PR #53) — NOW CLOSED | Two independent backtests agreed on +EV but shared a **look-ahead**: Open-Meteo's day-0 archive is rebuilt from model runs issued *after* the sleeve's decision window (2.44°F closer to truth than what the sleeve saw live). Honest lead-1 forecast: **−0.016c/ct, day-clustered t=−1.74 over 178 days**. Plus a `settle()` accounting bug (NO-side priced at YES cost) that inflated both the backtest and the +0.217/trade live log (itself only ~2 calendar days = statistically empty). Rediscovery of the WX_DIRECTIONAL dead axis | CLOSED — `wx_forecast_decision.py` kill-gate authored; `p4k_params.json` forecast entry = BACKTEST(refuted), not a capacity lever |
| **Depth_adaptive sizing** | IN-VALIDATION (1/15 distinct-calendar-day gate, accrual 1.0/day) | n=86 rows are 3 sweeps of ~29 markets on ONE day (pseudo-replicated); fire-conditional (not pooled) depth measure required | Review at ~15-day mark; if station-median depth swings ≥2x sweep-to-sweep, do NOT adopt — stay on fixed DEPTH_CAP=25 permanently; else adopt alpha=0.25 vs pessimistic depth measure |
| **Synoptic latency trial** | BOOTSTRAP READY, TRIAL PENDING | 14-day free-trial clock independent of fire-rate luck | Run trial to completion; go/no-go on paid tier from *measured* latency uplift only |
| **Early-lock paper harness** | ACCRUING (n=1/30 settled, ~0.7–1.0 signals/day observed; honest ETA ~29 days) | Historical prior NULL (wx_earlylock_deep_study.md); forward paper runs via `kwx_portfolio.py snapshot` | Accumulate to n=30; PASS bar: forward t≥3, EV/ct≥+1.1c (≥ deployed baseline), Kalshi-settlement truth, sign stable across temporal split; else declare closed |
| **Expansion Family 2 (mentions) gate** | MEASUREMENT PRE-STEP (not backtested) | Confirm-gated EV ≈+$0.05/ct survived audit, sitting exactly at the pre-registered bar; ~$18/mo defensible, ~$140/mo speculative | Stand up live transcript/caption feed, measure bid-lead latency on 5–10 live events; gate to Stage 1 backtest only if feed leads bid by >2 min at ≤0.90 AND q(bid≥0.90 false-lock)≤5% on the full 122-market NO sample |
| **Weather settlement-mismatch thesis** | ❌ NULL (2026-07-22, DATA_BACKED_BACKTESTS.md, PR #52) — NOW CLOSED | Near-certain (≥97c) weather locks fail at settlement only **0.25%** (FIT 3/1195) vs 2.08% breakeven, day-clustered t=−9.0; VAL 0/1705, t=−140.6. Market under-prices the fail-tail if anything — no fade edge. (Also explains the live taker bot: locks are genuinely near-certain and priced to 100c before any feed can act) | CLOSED |
| **Long-tail stale-resolution thesis** | ❌ REFUTED-STRUCTURAL (2026-07-22, DATA_BACKED_BACKTESTS.md, PR #52) — NOW CLOSED | n=3,371 reproduced & `/historical/*`-verified, but no exploitable window can exist by construction: sports props close at the decision instant (`can_close_early`), crypto/index resolve on the close value by definition. Tradeability separately defeated by a duplicate-timestamp artifact | CLOSED |
| **Short-term crypto Up/Down "temporal-arb + directional" (external lead)** | ⏸️ EVALUATED, PARKED (2026-07-22, RetroValix X article — 1,000 Polymarket bots) | Real strategy class = two-sided market-making with directional inventory skew, harvesting sub-$1 Up+Down pairs built across time. But it is a **latency + zero-fee** edge: the article's own edge sources are "better execution than slower participants" / "before liquidity disappears" (5-min markets, ~5 skew-rotations each) — our exact speed wall. On Kalshi the fee `ceil(7·p(1−p))/100` is **maximized at p≈0.5** (~2c/side) where Up/Down live, eating the ~5c/pair structural edge. No P&L shown (descriptive + promotional, Polymarket referral). | PARKED — only accessible angle worth a bounded test: do **minutes-persistent** sub-$1 pair windows exist on Kalshi net of fees? Prior: negative (fee-at-0.5 + speed). Not run pending user go/no-go |
| **Favorite-longshot bias Spec 2 (favorite-buy join)** | ❌ FAIL — execution-limited, NOW CLOSED as a lever (2026-07-22, FAVORITE_LONGSHOT.md) | Clean 383,553-market candidate universe built, but the candidates × 172M-trade join did not finish inside economy-mode budget (confirmed on a direct rerun this session: 170s+, zero output) — no P&L exists to certify one way or the other | Scored deployable=NO / $0/mo by default (can't ship an unverified claim); genuinely reopenable if a future session budgets a multi-hour background join — see `scratchpad/flb/bt2/05_join_trades.py`. Not blocking: Specs 1 and 3 of the same funnel both completed and were negative, so the prior for Spec 2 is not favorable |

---

## 5. INFRASTRUCTURE BUILT

| Asset | Purpose | Status |
|---|---|---|
| `kx_history.py` | Data unblock: DuckDB predicate-pushdown over the HF parquet trade archive (~172M trades, Jun 2021–Jan 2026) + Kalshi official `/historical/*` API | Complete, read-only; enabled the long-tail re-backtest to scan 2.16M qualifying markets / 1,807 series and the weather studies ~21.3k settled markets — far beyond the walled live API |
| `.claude/skills/run-kwx/` | Health-check & driver (smoke, status, model, feed, digest) | Complete; `.claude/skills/run-kwx/driver.sh smoke` entry point |
| `.claude/skills/kwx-research-funnel/` | Ideate → pre-register → backtest → judge → ship workflow | Complete; Sonnet workers / Fable judges |
| `.claude/skills/kwx-study-audit/` | 10-point refutation checklist | Complete; has killed every false positive tested here |
| `.claude/skills/kwx-deploy-gates/` | Numeric stage ladder, kill criteria, halt switch | Complete; baked into `PATH_TO_4K.md` |
| `.claude/skills/kwx-capacity-model/` | Runs/reads/updates `wx_path_to_4k.py` + `p4k_params.json` | Complete; Monte-Carlo over 4 scenarios |
| `.claude/skills/kwx-feeds/` | Obs-feed work (Synoptic, probes, latency trials) | Complete; bootstrap ready, trial pending |
| `.claude/skills/kwx-portfolio/` | Stacking sleeves, registry, shared caps, correlation | Complete; `kwx_portfolio.py` orchestrates all paper sleeves |
| `.claude/skills/kwx-incident/` | Fleet trouble (outages, races, halts, log pollution) | Complete; the one-time 20h39m leg outage (2026-07-18T20:23→07-19T21:28Z) diagnosed & structurally fixed (52 consecutive legs, no gap >19 min since) |
| `kwx_portfolio.py` | Central manager: status, snapshot, correlate, registry | Complete; runs all paper sleeves fail-soft; dedupe vs live plan log; verified live this session |
| `kwx_goal_status.py` | Stage/gate status + bankroll-rung table | Complete; verified live this session (Stage 0, 0 settled, 26 near-misses today) |
| `wx_path_to_4k.py` | Capacity Monte-Carlo (corrected depth conditioning, market impact, parameter uncertainty) | Complete; 3 FATAL + 5 MAJOR fixes (12 review findings total) post two-judge review; prints both the headline 25.7/day and gate-basis 10.4/day rates (unreconciled sources, deliberately surfaced) |
| Synoptic bootstrap | Encrypted credential pipeline, health check | Complete; 14-day trial clock armed, not started |

---

## 6. THE META-CONCLUSION

**Kalshi is efficient against every strategy class a retail GitHub-Actions-speed bot can test at the scales we've measured.** The rigorous negative result — not a vague null but specific, adversarially-verified kills of maker, near-miss-conversion, directional, expansion-family, calibration-fade, long-tail, illiquid, and cross-venue mechanisms across multiple independent data sources and funnel rounds — **IS the deliverable.**

**Update 2026-07-22: the map is now fully closed on the tested classes.** The forecast-overlay sleeve — the last signal showing green — was REFUTED (look-ahead + accounting bug; see §4). No strategy class tested on real data survives adversarial verification, and the live taker bot has made **0 fires in 72h**. One external lead (short-term crypto Up/Down temporal-arb) was evaluated and parked as a latency+fee wall (§4).

**Update 2026-07-22 (per-series scan, `PER_SERIES_SCAN.md`): the search is now exhaustive at the SERIES granularity too, not just universe/category.** Every prior funnel this session scanned at the *category* level (weather, sports, crypto, index, favorite-longshot-as-a-class); this pass instead screened all 144 individual series with >=300 settled markets for a last_price bias, Bonferroni-corrected and fit/val-separated, and took the 5 survivors (KXBTC, KXETH, KXNFLFIRSTTD, KXINX, KXNFL — all a naive "buy NO" signal) to a realistic-entry retest against real crossed-spread NO-taker fills, fee-inclusive, day-clustered. **All 5 failed**: none clears an uncorrected significance bar on both a contract- and print-weighted estimate simultaneously, none survives Bonferroni-over-5, and the one nominal near-miss (KXINX, t=-2.13 contract-weighted only) shows the exact price-bucket sign-instability signature of the already-known `^[A-Z]+` family-conflation bug rather than a real uniform bias. Both mechanisms that have killed every other last_price/mid-based claim this session (stale-quote artifact on expire-worthless markets; mixed-family noise) reproduce here too. Taker- **and** maker-side, category- **and** series-granularity, the map is now closed.

**Update 2026-07-22 (maker-side favorite-longshot close, `MAKER_FAVLONG.md`): the favorite-longshot bias is now closed under BOTH execution styles.** `FAVORITE_LONGSHOT.md` killed it at the crossing price (taker entry, Specs 1 and 3 confirmed FAIL, Spec 2 execution-limited). `MAKER_FAVLONG.md` then tested the maker/resting-bid alternative — deliberately attractive on paper (non-latency, $0-fee-eligible on some categories, persistent behavioral bias, huge nominal capacity) — across the full liquid universe (not just weather, where `wx_maker_deep_study.md` had already killed the post-lock maker mechanism on a different question). Two independent backtests, adversarially reconciled, agree: no cell clears its bar, day-clustered t≈0.6 with a CI crossing zero on the only non-disqualified overlap, and capturing real volume requires bidding into a −7c to −18c/contract price zone. Honest capacity **$0/mo**. **The raw favorite-longshot mispricing is real (per the original 2.97M-market scan); capturing it — by crossing the spread or by resting a bid — is not achievable by any bot this repo can build.** This is the honest end of the favorite-longshot search, not a partial result awaiting a future retry.

**In order of evidence-weighted realism, the only remaining paths toward (not to) $4k/mo — none validated, none a proven edge:**
1. **Depth_adaptive validation** — pending the 15-distinct-day snapshot gate (currently 1/15) plus station-median stability; if it fails, the pure-bankroll path hard-caps near $1,047–$1,318/mo permanently; if it passes, proceed toward $500 sizing with alpha=0.25 against the pessimistic fire-conditional depth measure (no larger $/mo figure for a pass is honestly quantifiable today).
2. **Synoptic measured latency** — 14-day trial; the paid 1–2-min tier would cut steady-state detection from ~8 min, but WX_NEARMISS_DIAGNOSIS shows this cannot fix adverse selection: the market beat the lock rule itself by a median 106 min in 10/10 sampled cases (~0% convertible, ≈2–4% theoretical upper bound).
3. **Expansion Family 2 (mentions)** — ~$18/mo defensible, ~$140/mo speculative only if a ×8 sibling extrapolation AND a still-unmeasured transcript-feed latency both validate; requires an external caption source not yet available.

**None of these paths clears $4k/mo without either (a) live fill rate eventually matching the 0.79 backtest fillable assumption (observed live: 0 fills against 189 logged near-misses), or (b) a measured, non-speculative capacity increase.** The model's own math is honest: conservative tops out ~$1,318/mo (33%), base ~$885+/mo at $2k ($838–843+ at $2k–$10k in today's live run, 21–22%), optimistic ~$1,173+/mo (29%) — all `+`-marked figures depend on ASSUMED sleeve gates, and actual live accrual so far is: early_lock n=1 settled paper fire, forecast 112 settled but ungated, book_watch 0 attributed fires, maker refuted, depth_adaptive 1/15 days.

**Immediate action:** Use `conservative_live` (~$146–149/mo at today's observed fill evidence) as the planning basis, not `conservative` (~$1.3k). If 0 fires persist past the 21-day Stage-0 kill window (switch-on was 2026-07-18T20:23Z), stop assuming either fires/day rate and re-diagnose the detection/fill bottleneck before any deposit. Do not deposit beyond ~$1,000 expecting more return — incremental capital past that earns ~$0 under every scenario tested to $50,000.

---

## SECTION HEADERS SHIPPED

1. ONE-LINE STATUS + HONEST CAPACITY BOTTOM LINE
2. WHAT'S LIVE / DEPLOYED (the blunt reality)
3. THE GRAVEYARD — Every Tested Strategy & Its Verdict
4. WHAT'S STILL OPEN (Genuinely Unresolved)
5. INFRASTRUCTURE BUILT
6. THE META-CONCLUSION

## REVIEWER VERIFICATION NOTES (flags from the draft, resolved)

| Draft flag | Resolution |
|---|---|
| "26 near-misses / 0 fires today; 72h+ aggregate unknown" | VERIFIED live: 26 near-misses today (2026-07-22), 0 settled fires; full log = 189 near-misses over 2026-07-20..22, all `ask>98`; switch-on 2026-07-18T20:23Z, so the 0-fire window is ~4 days |
| "~$18/mo defensible for Family 2" | VERIFIED against WX_EXPANSION.md judge table row 1 (+$0.05/ct confirm-gated, 0.95 ev/day, ~$18/mo defensible, ~$140/mo speculative ceiling); latency assumption remains unmeasured |
| "−14.32c/contract (39,220 fills)" | VERIFIED; t=−29.57 is on unweighted day means (−13.87c), headline is pooled mean (−14.32c) — both decisively negative, per DATA_BACKED_BACKTESTS.md's own adversarial note |
| "t=0.28 early-lock headline; 27 vs 36 cells" | VERIFIED: 36 nominal cells collapse to 27 effectively distinct (95c/95.3c caps byte-identical); Bonferroni bar ≈3.11; temporal sign flip +9.60c→−8.08c |
| "Forecast 59 settled rows" | STALE: live status run now shows 164 paper rows / 112 settled; still no decision gate authored — informational only |
| "Synoptic bootstrap ready" | VERIFIED: bootstrap committed, 14-day trial not started; decision only on measured latency uplift |

---

## 7. VENUE-RELAXATION TESTED — Polymarket (2026-07-22, single Sonnet agent, no live-path code)

The favorite-longshot bias died on Kalshi partly on fees + spread, so the zero-fee venue was the one worth testing. **Result: Polymarket is also efficient at real tradeable prices — DEPLOYABLE: NO, $0/mo.**

- Powered scan: 6,610 resolved markets fetched → **1,447 usable** binary markets (2023-01→2026-07), entry price taken 36h before resolution (or 50% of life), no look-ahead. Data via curl (urllib is 403'd by the proxy for gamma-api/clob hosts).
- Favorite-longshot TAILS (price <0.20 or >0.80) are FLAT — no CI excludes price, no monotonic FLB pattern. The classic bias does NOT reproduce at Polymarket's tradeable prices, which means the Kalshi "bias" was substantially a last_price/mid artifact — both venues are efficient at prices you can actually trade.
- The two nominally-significant mid bins fail persistence + day-clustering ([0.40,0.50): early t=−0.10, late t=+2.82 — late-sample artifact); low bins flip sign across the date split. Sports marginal +10.9¢ pooled but insignificant in both halves (likely a listing-order/seeding artifact).
- Slippage (walk-the-book proxy): median 1.0¢, p75 6.2¢ — same order as any marginal edge, so even nominal findings wouldn't survive execution.

**META-CONCLUSION (final, 2026-07-22):** every strategy class a retail, public-data, minutes-cadence bot can reach has now been tested on real data at tradeable prices across BOTH major prediction-market venues (Kalshi: universe→category→series, taker+maker; Polymarket: zero-fee, 1,447 markets), all adversarially verified. No deployable non-latency edge exists. The rigorous, exhaustively-mapped negative result is the deliverable. A deployable edge now requires relaxing a structural constraint the operator controls: faster/co-located execution (compete in timing games), or a domain forecasting model (different project, efficient-where-liquid), or accepting the validated mechanical sleeve (~$150/mo conservative_live) and not depositing past the canary.

## 8. CROSS-VENUE ARBITRAGE TESTED — Kalshi vs Polymarket (2026-07-22, Sonnet agent)

**DEPLOYABLE: NO.** 11 matched BTC/ETH annual-max threshold pairs priced with full depth-walk: total **$65.95 one-time locked profit for $3,344 capital tied up ~5 months** (~5% annualized). Direction is systematic (Kalshi YES ask > Polymarket at every strike) = the same Kalshi favorite-longshot bias reappearing, not a cross-venue inefficiency. Killed by: (a) two-account custody/KYC overhead (Kalshi fiat + Polymarket USDC/Polygon, no netting) plausibly exceeding the $66 edge; (b) unquantifiable basis risk — Kalshi resolves on CF Benchmarks BRTI/ERTI trimmed-mean index, Polymarket on raw Binance 1-min candles; (c) the more-numerous daily crypto family disqualified on a confirmed 1-hour close-time mismatch (Kalshi 17:00 UTC vs Polymarket 16:00 UTC). Capacity ~$0/mo. Not seriously explored: elections/sports finals (none in season during sampling) — "crypto cross-venue arb is null" ≠ "all cross-venue arb is null", the one honest residual.

**FINAL STATUS:** three avenues now closed — single-venue Kalshi (all granularities, taker+maker), single-venue Polymarket (1,447 markets, tradeable prices), and cross-venue arbitrage. No deployable non-latency edge exists for a retail bot on either major prediction-market venue or between them. Search exhausted; remaining moves require an operator constraint decision (execution speed, or a domain forecasting model, or accept the ~$150/mo validated mechanical sleeve).
