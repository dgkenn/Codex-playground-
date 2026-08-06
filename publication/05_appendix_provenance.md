# Forty-Two Kills

## Appendix — Provenance and Reproduction

The front matter of this publication says reproduction harnesses exist for every numbered
case and are referenced by filename throughout. That claim is checked here, case by case,
rather than asserted once and left alone. For each of the 42 numbered studies in Parts 2 and
3, the table below gives the source document the catalog entry was drawn from and the
specific script or data file that document cites as its reproduction harness — verified
against this repository and against the live trading branch
(`origin/claude/coding-bot-ab-test-results-ffmhxw`), not assumed from the write-up's prose.
Verdict labels are copied verbatim from the source; we have not normalized "FAIL" and "KILL"
and "INSUFFICIENT" into one flavor of "didn't work," because the distinction between a
measured negative and a study that never reached its own pre-registered sample bar is the
thing this publication is asking a reader to trust. **"[not shipped]" marks a case where the
study produced a write-up but no reproduction script or data file survives as a committed,
checkable artifact** — either because the source names none, or because it names one living
in an untracked scratch directory (this repo's own convention is to keep large intermediates
and per-shard scratch code out of git, which is disclosed honestly in several of the source
documents themselves, not something we uncovered independently).

| # | Strategy | Verdict (verbatim) | Source document | Reproduction artifact |
|---|---|---|---|---|
| 1 | Maker (post-lock resting bids) | REFUTED | `wx_maker_deep_study.md` | `wx_maker_deep_study.py` [live branch] |
| 2 | Early-lock (tail capture) | NULL | `wx_earlylock_deep_study.md` | `wx_earlylock_deep_study.py` [live branch] |
| 3 | Directional SPEC 1 (horizon-conditional calibration fade) | INSUFFICIENT | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 4 | Directional SPEC 2 (MOS revision fade) | KILL | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 5 | Directional SPEC 3 (thin-book longshot) | INSUFFICIENT | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 6 | Directional SPEC 4 (intraday nowcast lag) | FAIL | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 7 | Directional SPEC 5 (order-flow drift) | FAIL | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 8 | Directional SPEC 6 (ladder arb) | FAIL + INSUFFICIENT | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 9 | Directional SPEC 7 (salient anchoring) | NO-SIGNAL | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 10 | Directional R4-1 (climate long-lead) | FAIL | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 11 | Directional R4-2 (upwind advection) | FAIL | `WX_DIRECTIONAL.md` | none named [not shipped] |
| 12 | Near-miss conversion (fill lag fix) | NULL | `WX_NEARMISS_DIAGNOSIS.md` | `nearmiss_diagnosis.json` (cited under "Files in this directory," never committed) [not shipped] |
| 13 | Expansion: Sports totals | NOT PROMISING | `WX_EXPANSION.md` | `fam1/analysis_results.json` (scratchpad, not committed) [not shipped] |
| 14 | Expansion: Earnings/Gutfeld mentions (Family 2) | PROMISING-WEAKENED | `WX_EXPANSION.md` | `fam2/analyze2.py` (scratchpad, not committed) [not shipped] |
| 15 | Expansion: Earthquake magnitude | NOT PROMISING | `WX_EXPANSION.md` | `fam3/results.md` (scratchpad, not committed) [not shipped] |
| 16 | Expansion: Commodity ladders (WTI/NGAS) | NOT PROMISING | `WX_EXPANSION.md` | `fam4/analyze1.py` (scratchpad, not committed) [not shipped] |
| 17 | Expansion: Crypto MAX ladders | NOT PROMISING | `WX_EXPANSION.md` | `fam5/results.md` (scratchpad, not committed) [not shipped] |
| 18 | Expansion: FDA drug approvals | NOT PROMISING | `WX_EXPANSION.md` | `fam6/results.md` (scratchpad, not committed) [not shipped] |
| 19 | Weather calibration-fade (near-certainty) | FAIL (CONFIRMED) | `DATA_BACKED_BACKTESTS.md` | `weather_calib/analyze.py` (scratchpad, explicitly noted as living outside the repo root) [not shipped] |
| 20 | Long-tail passive spread | FAIL (CONFIRMED) | `DATA_BACKED_BACKTESTS.md` | `lt_spread/02_run.py` (scratchpad, explicitly noted as living outside the repo root) [not shipped] |
| 21 | Illiquid snapshot arbs (leg-sum, nested-cutoff, stale-quote) | REFUTED | `ILLIQUID_MARKETS.md` | `structural_scan.py` / `analyze_me.py` (cited in `ILLIQ_STRUCTURAL_SCAN.md`, scripts themselves not committed) [not shipped] |
| 22 | Illiquid r1s1 (mention anchor) | INCONCLUSIVE | `ILLIQUID_MARKETS.md` | `illiq_r1s1_mention_anchor.py` [live branch] |
| 23 | Illiquid r1s2 (off-air passive quoting) | INCONCLUSIVE + NEGATIVE | `ILLIQUID_MARKETS.md` | `illiq_r1s2_offair_quoting.py` [live branch] |
| 24 | Illiquid r1s3 (jobless-claims relist) | INCONCLUSIVE | `ILLIQUID_MARKETS.md` | `illiq_r1s3_jobless_relist_fade.py` [live branch] |
| 25 | Stacked r1s1 (broadcast-mention siblings) | CONFIRMED FAIL | `STACKED_EDGES.md` | `scratchpad/stacked/bt1/` (not committed) [not shipped] |
| 26 | Stacked r1s2 (KXJOBLESSCLAIMS AR(1)+MA nowcast) | CONFIRMED FAIL (underpowered pre-registered kill) | `STACKED_EDGES.md` | `scratchpad/stacked/bt2/` (not committed) [not shipped] |
| 27 | Stacked r1s3 (cross-venue reprice race) | CONFIRMED FAIL/UNTESTED | `STACKED_EDGES.md` | `scratchpad/stacked/bt3/` (not committed) [not shipped] |
| 28 | Stacked r2s1 (crypto cross-venue lead-lag) | FAIL (preflight self-kill) | `STACKED_EDGES.md` | `scratchpad/stacked/r2b1/` (not committed) [not shipped] |
| 29 | Stacked r2s2 (macro-surprise pass-through drift) | N-GATE INSUFFICIENT | `STACKED_EDGES.md` | `scratchpad/stacked/r2b2/` (not committed) [not shipped] |
| 30 | Favorite-longshot bias Spec 1 (broad longshot fade, ex-crypto ex-weather) | CONFIRMED FAIL | `FAVORITE_LONGSHOT.md` | `scratchpad/flb/bt1/backtest_spec1.py` (not committed) [not shipped] |
| 31 | Favorite-longshot bias Spec 2 (favorite buy, 70–90c band, ex-crypto ex-weather) | CONFIRMED FAIL (execution-limited, not measured-negative) | `FAVORITE_LONGSHOT.md` | `scratchpad/flb/bt2/05_join_trades.py` (not committed) [not shipped] |
| 32 | Favorite-longshot bias Spec 3 (crypto isolation, 5–45c) | CONFIRMED FAIL | `FAVORITE_LONGSHOT.md` | `scratchpad/flb/bt3/` (not committed) [not shipped] |
| 33 | Favorite-longshot bias — maker (resting-bid) capture across the liquid universe | CONFIRMED FAIL | `MAKER_FAVLONG.md` | none committed — the source states per-shard scratch scripts and intermediate caches are deliberately not kept [not shipped] |
| 34 | Per-series last_price screen (144 series) → realistic-entry retest of the 5-series shortlist | CONFIRMED FAIL | `PER_SERIES_SCAN.md` | `scratchpad/series/scan/step1_screen.py`, `step2_realistic_entry.py` (not committed) [not shipped] |
| 35 | Sports/forecasting axis: KXNFLGAME vs sharp Vegas closing line AND a walk-forward Elo trained model | CONFIRMED NULL (sharp-line) + CONFIRMED NEGATIVE (trained model) | `FORECAST_MODEL.md` | `elo_model.py`, `build_games.py`, `fetch_candles.py` (session scratchpad, explicitly not committed) [not shipped] |
| 36 | Latency axis: crypto Up/Down (KXBTC/KXETH hourly) speed-vs-EV, model-vs-print at L=1s..300s | NO-EDGE-ANY-LATENCY (CONFIRMED, two independent builds + Fable adversarial verify) | `LATENCY_EDGE.md` | `latency_edge_repro.py` — the source states outright that this was never shipped, since it's warranted only for a positive verdict [not shipped] |
| 37 | Weather ensemble-probability info-gap: 51-member ECMWF ensemble P(clear strike) vs Kalshi crossing price | CONFIRMED NULL (Fable adversarial verify) | `WEATHER_ENSEMBLE.md` | `bt_ens/bt_ens.py` (incomplete Backtest A), `bt_ens2/` — `harvest.py`, `fetch_trades.py`, `analyze.py` (complete Backtest B) [live branch] |
| 38 | ForecastEx (IBKR/CFTC, US-legal) daily-temperature mechanical lock | CONFIRMED KILL (two independent pre-registered grounds; three builds, one adversarial) | `S3_FORECASTEX.md` | `venue_expansion/spec_S3_B.py`, `venue_expansion/out/spec_S3_B.json`, `venue_expansion/out/spec_S3_B.md` [in repo] |
| 39 | Executable-price universe screen on reconstructed crossing prices (U1) | CONFIRMED FAIL | `REOPEN_FUNNEL.md` | `venue_expansion/spec_U1.py`, `venue_expansion/out/spec_U1.json` [in repo] |
| 40 | Macro-surprise pass-through reopen (M1, reopen of #29) + KXJOBLESSCLAIMS weekly-relist reopen (J1, reopen of #24) | INSUFFICIENT — NOT TESTED (both legs) | `REOPEN_FUNNEL.md` | `venue_expansion/spec_M1.py`, `venue_expansion/spec_J1.py` [in repo] |
| 41 | Directional SPECs 1/3/7 re-run at archive n, executable crossing prints (D1, reopen of #3/#5/#9) | INSUFFICIENT ×3 — NOT TESTED | `REOPEN_FUNNEL.md` | `venue_expansion/spec_D1.py`, `venue_expansion/out/spec_D1.json` [in repo] |
| 42 | Kalshi crypto-hourly maker (adverse-selection-filtered spread capture, reaction speed 1s–300s) | MM2-FAIL → PERMANENT KILL | `MAKER_VIABILITY.md` | `venue_expansion/maker_stageB_A.py`, `venue_expansion/maker_stageB_B.py`, `venue_expansion/out/spec_MM1_frozen.json`, `venue_expansion/MM2_REGISTRATION.md` [in repo] |

---

### The honest count

Of the 42 cases catalogued in this publication, **11 have a reproduction artifact we could
actually locate and verify** — 5 as committed files in this repository (cases 38–42, the
ForecastEx and reopen-funnel batch, all under `venue_expansion/`) and 6 more on the live
trading branch, `origin/claude/coding-bot-ab-test-results-ffmhxw`, absent from this one
(cases 1, 2, 22, 23, 24, and 37). **The remaining 31 — nearly three in four — have no
committed reproduction harness at all.** Nine of those (cases 3–11, the full
`WX_DIRECTIONAL.md` funnel) name no script or data file whatsoever in their own source
document; the other twenty-two name a specific script or scratch directory that was never
checked into either branch, a fact several of the source documents disclose about themselves
in plain language ("not committed — repo convention keeps large intermediates out of git").

That 11-of-42 figure is not what the front matter promises. "Reproduction harnesses exist
for every numbered case and are referenced by filename throughout" is true of the *filename
references* — every case here is in fact tied to a specific study document, and most study
documents are in fact tied to a specific script name — but it overstates what a reader can
independently check today. What actually survives, checkable, is the verdict math shown
inline in each source document (the frozen bars, the n's, the t-statistics, reproduced by
independent builds and adversarial review passes described in the text) rather than a script
a reader can run themselves for 31 of the 42 cases. We are stating this plainly rather than
rounding it up, because a publication whose whole argument is that pre-registration and
checkability are what make a negative result trustworthy does not get to be vague about how
much of its own record is actually checkable.
