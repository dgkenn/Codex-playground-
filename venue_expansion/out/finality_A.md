# TERMINAL FINALITY -- BUILD A (primary) -- result

Spec: `venue_expansion/TERMINAL_FINALITY_SPEC.md` (frozen 2026-10-27).  Code: `venue_expansion/finality_A.py`.  Per-fire records: `venue_expansion/out/finality_A.json`.  Seed 20261027.

## Verdict (formal reading S = spec text literally): **INSUFFICIENT**

- reading **S** (interval [floor, cap] -- LITERAL spec (formal verdict)): **INSUFFICIENT**; PASS cells at L=10: none; KILL triggers: none; best one-sided 97.9% EV upper bound at L=10: n/ac
- reading **L** (interval [floor-0.5, cap+0.5] -- lattice/rounding reading (exploratory, pre-declared)): **INSUFFICIENT**; PASS cells at L=10: none; KILL triggers: none; best one-sided 97.9% EV upper bound at L=10: 4.72c

{{COMMENTARY}}

## Universe, sampling, skips

- Series tested: 40 (20 HIGH, 20 LOW; 20 stations).  Events (station-days): 6,039; bracket rungs: **24,156** (HIGH events 3,020, LOW events 3,019); close_time UTC date in 2026-05-23..2026-10-20.
- Obs feed per event: IEM 1-minute **5,109**, routine-METAR fallback **930** (1-minute day had < 600 obs).
- Rungs with at least one FINAL-YES fire (any reading/cell): **3,899** (all under reading L; reading S fires on none).
- **Sampling of the priced stage**: candlesticks were pulled for 652 of 3,899 fired rungs = **16.7%**.  Work order = all fired rungs, sorted only to make the shuffle reproducible, then shuffled with seed 20261027 and NEVER re-sorted, so the pulled set is a uniformly random subsample of the fired rungs (any prefix is representative).  Signal-level facts (fire counts, false-lock rate before pricing) use ALL fired rungs in the signals stage (3,899); the covered/priced statistics below use the pulled random subsample.
- Candle states of the pulled set: {"no_candles_in_final_120min": 51, "covered": 601, "not_fetched": 3247}

## Method (what was actually run)

1. **Universe** -- settled bracket rungs (`-B` tickers, `strike_type=between`, official `result` in {yes,no}) of the 40 US
   HIGH/LOW series with a verified station mapping, `close_time` UTC date in 2026-05-23..2026-10-20.  Market lists come from the
   live `/markets?status=settled` endpoint (post 2026-08-28 settlements) UNION `/historical/markets` (older), de-duplicated.
   Outcome = Kalshi `result` only; a random sample of fired rungs was cross-checked against `GET /markets/{ticker}`.
2. **Observations** -- IEM `asos1min.py` (1-minute) per station-month, cached; routine `asos.py` (report_type 3&4) as a disclosed per-market
   fallback when the 1-minute day has < 600 obs.  Feed recorded per market.
3. **Signal** -- streaming detector (`Stream`): consumes obs one at a time, keeps running extreme E and, for each R, the count of
   trailing obs at least R degrees away from E.  FINAL-YES at the first obs with (1) interval test, (2) run >= H, (3) obs within W minutes of
   `close_time`.  Signal stamped obs-minute + 60 s (decision D3).
4. **Entry** -- first candle with `end_period_ts >= sig_ts + L*60` and `<= close_ts`, `yes_ask <= 98c` and `100 - ask - fee > 0`; no earlier or
   better print is ever used; no such candle = UNTRADEABLE (counted).  One contract, held to settlement.  Fee `ceil(7 p (1-p))` via `V2.fee_c`.
   pnl = `100 - cost - fee` if the official result is YES else `-cost - fee`.  Candles are normalised by the shared `edge_sizing_v2.normalize()`.
5. **Statistics** -- false-lock rate with Wilson 95% bounds; volume-weighted EV (weight = entry-candle volume; unweighted shown); day-clustered
   (calendar event-date) CR1 standard error, signed t, df = days-1, bar = exact Student-t quantile at p=0.99896 on the realised df.
6. **Interpretation decisions (D1-D9)** are pre-declared in the `finality_A.py` module docstring before any outcome was analysed.

### D1 -- the bracket-width problem in the frozen text (read this)

A Kalshi bracket rung has `cap_strike = floor_strike + 1` (e.g. `B68.5` -> floor 68, cap 69, YES iff the official **integer** high is 68 or 69;
verified on every settled rung against `expiration_value`).  The spec's test `lo + M <= E <= hi - M` on `[lo,hi] = [floor,cap]` is therefore
an **empty interval for every M = 1.0 cell** (it needs E >= lo+1 and E <= lo) and a single point (`E = lo + 0.5`) for M = 0.5.  Since 1-minute ASOS
temperatures are whole degrees, reading S can essentially never fire.  This is a defect in the frozen text, discovered by arithmetic before
outcomes were read.  Rather than silently re-define the spec, BOTH readings were run on the identical grid: **S** = the literal text (formal
verdict) and **L** = the lattice reading `[floor-0.5, cap+0.5]` (the real-valued temperature range that rounds into the settlement set), under which
M=0.5 means "E rounds into the bracket" and M=1.0 requires E at the bracket centre (also near-vacuous on integer data).  L is exploratory and
cannot produce a PASS; a PASS would require re-registration.

## Worked timezone example

Event `KXLOWTATL-26AUG02` (station ATL, running MIN).
- Event date 2026-08-02; station fixed standard offset UTC-5 (the NWS climate day is local STANDARD time all year).
- Local-standard midnight that STARTS the day = 2026-08-02 00:00 LST = **2026-08-02 05:00Z**; the day ENDS at 2026-08-03 00:00 LST = **2026-08-03 05:00Z**, and Kalshi's `close_time` is exactly that (2026-08-03 05:00Z) -- asserted for every event (`close_time == (date+1) 00:00 - offset`).
- Expressed in daylight-saving wall-clock (UTC-4) the same day runs 01:00 on 2026-08-02 to 01:00 on 2026-08-03, i.e. it does NOT start at wall-clock midnight.  A naive 'local midnight to local midnight' window in DST wall-clock is the window shifted by s=-1h -- the classic 1-hour-skew trap.

| window shift s (h) | extreme in [close-24h+s, close+s) F | official `expiration_value` | integer match |
|---|---:|---:|:---:|
| -3 | 77.0 | 74 | no |
| -2 | 76.0 | 74 | no |
| -1 (naive DST wall-clock) | 75.0 | 74 | no |
| +0 (declared) | 74.0 | 74 | YES |
| +1 | 73.0 | 74 | no |
| +2 | 71.0 | 74 | no |
| +3 | 71.0 | 74 | no |

Only the declared window reproduces Kalshi's own official value on this day; the 1-hour-shifted windows do not.

## Worked no-look-ahead example

Rung `KXLOWTMIN-26JUN05-B64.5` (floor 64, cap 65, kind min, feed iem_1min), reading L, cell `M0.5_R2_H3_W120`:
- Signal (obs-only): E = 65.0 F at obs minute 2026-06-06 04:00Z; the last 1004 obs were each >= R away from E (current temp 71.0 F); obs index k = 1320; the signal is stamped 2026-06-06 04:01Z (= obs minute + 60 s), so every observation used has ts < signal ts.
- Computed by `Stream` one observation at a time; nothing after index k is ever visible to it.
- Assertion actually run on every fire (15,360 re-runs across all fires): (1) re-run the detector on obs[:k+1] only and (2) re-run on the full day with every observation after k replaced by an adversarial value 50 F beyond the signal-time temperature in the direction that would change the decision.  Both must reproduce the identical (k, E, sig_ts) or the run aborts.  0 violations (the script would have raised).
- Entry (L=10): `{"status": "priced", "entry_ts": 1780719060, "cost_c": 97, "fee_c": 1, "vol": 0.0, "win": true, "pnl_c": 2}`

## Sanity anchors

**(a) Oracle reconciliation -- HOLDS.**  Price join: 34/34 of the stored Stage-1 oracle bracket rungs re-derived from my own fresh candle pull reproduce the stored best winner cost, best net and capturable-minute count EXACTLY (same `normalize()`, fee, 98c constants).  Subset test: of 257 priced YES-settled fires in W=60 cells (entry necessarily inside the final 60 minutes), 0 are not oracle-capturable under the Stage-1 definition re-derived on the same candles.  The rule fires on 9 of the stored oracle bracket rungs.  Limitation: Only the top-40 'capturable_markets_detail' of out/edge_sizing_v2.json (34 bracket rungs) survives on disk; the full 140-market Stage-1 set and its population cache are gitignored and absent.  The subset anchor is therefore tested by re-deriving the Stage-1 capturable test (same fee/98c constants, same normalize()) on every priced YES fire, plus a price-join reproduction on the stored rungs.
**(b) No look-ahead -- HOLDS.**  15,360 assertion re-runs, none failed (see worked example).
**(c) Monotonicity / timezone -- HOLDS.**  Running-extreme monotonicity violations over 6,039 event-days: **0**.  Independent timezone proof: extreme of the obs inside windows shifted by s hours versus Kalshi's own official `expiration_value`:

| kind | s=-3 | s=-2 | s=-1 | s=0 | s=1 | s=2 | s=3 |
|---|---|---|---|---|---|---|---|
| max exact-match % | 41.4 | 41.7 | 42.4 | 43.1 | 42.8 | 42.8 | 42.8 |
| max mean abs err F | 0.96 | 0.92 | 0.90 | 0.89 | 0.89 | 0.88 | 0.88 |
| min exact-match % | 69.5 | 70.5 | 72.3 | 76.9 | 70.4 | 65.0 | 58.8 |
| min mean abs err F | 0.73 | 0.69 | 0.60 | 0.53 | 0.61 | 0.75 | 0.92 |

For LOW markets (late-evening / pre-dawn sensitive) the declared window s=0 is the clear optimum and error rises monotonically with |s|, which is the signature of correct handling; for HIGH markets the afternoon peak makes the day boundary nearly irrelevant, so the HIGH row is weakly informative (s=0 is still among the best).  The `close_time == LST midnight` assertion (+/-60 s, 588 events close at 23:59 LST) is the strict check and held for all 6,039 events (0 skips).

**Important side-finding from anchor (c):** even with the correct window the 1-minute-IEM extreme equals Kalshi's official integer in only 43% of HIGH days and 77% of LOW days (mean abs error 0.89 F / 0.53 F).  The official settlement value (The Weather Company) is not the ASOS 1-minute extreme; this is the root of the false-locks below, and it is independent of timing or latency.

## Primary cell (M=1.0, R=2, H=3, W=120) at L=10

Formal reading S: n fires = **0** (empty interval -- see D1).  Reading L: n fires = **0** (needs E exactly at the bracket centre, impossible on whole-degree 1-minute data).  The pre-declared primary cell therefore has **no observations under any reading** and cannot be evaluated; no KILL-on-primary-false-lock or PASS statement can be made about it.  The only cells that fire are the M=0.5 cells under reading L, tabled next.

## All cells, L = 10 (the deployable arm)

**Reading S (formal)**: all 8 cells x 3 arms have 0 fires (see D1); nothing to tabulate.

**Reading L (exploratory)**, M=0.5 cells (M=1.0 cells have 0 fires):

| cell | L | fires (covered) | false locks (rate, Wilson UB) | priced (vol>0) | untradeable | EV vw (c) | EV unw (c) | t vw (bar) | t unw | days | stn | FL priced (rate, UB) | UB97.9 (c) | all 5 bars |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M0.5_R2_H3_W60 | 10 | 571 | 135 (23.64%, 27.30%) | 136 (55) | 435 (76.18%) | 0.31 | 0.85 | 0.14 (3.17) | 0.65 | 90 | 20 | 74 (54.41%, 62.55%) | 4.72 | no |
| M0.5_R2_H3_W120 | 10 | 601 | 140 (23.29%, 26.84%) | 236 (92) | 365 (60.73%) | -1.29 | 1.08 | -2.26 (3.15) | 1.14 | 116 | 20 | 128 (54.24%, 60.47%) | -0.12 | no |
| M0.5_R4_H3_W60 | 10 | 498 | 127 (25.50%, 29.51%) | 95 (36) | 403 (80.92%) | -1.97 | -0.19 | -81.01 (3.20) | -0.27 | 72 | 19 | 69 (72.63%, 80.59%) | -1.92 | no |
| M0.5_R4_H3_W120 | 10 | 534 | 130 (24.34%, 28.16%) | 181 (72) | 353 (66.10%) | -1.94 | 0.96 | -48.93 (3.16) | 1.16 | 100 | 20 | 119 (65.75%, 72.27%) | -1.86 | no |

## All cells, L = 0 and L = 20

| cell | L | fires (covered) | false locks (rate, Wilson UB) | priced (vol>0) | untradeable | EV vw (c) | EV unw (c) | t vw (bar) | t unw | days | stn | FL priced (rate, UB) | UB97.9 (c) | all 5 bars |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M0.5_R2_H3_W60 | 0 | 571 | 135 (23.64%, 27.30%) | 171 (72) | 400 (70.05%) | -0.64 | 0.16 | -0.54 (3.16) | 0.14 | 99 | 20 | 103 (60.23%, 67.27%) | 1.81 | no |
| M0.5_R2_H3_W60 | 20 | 571 | 135 (23.64%, 27.30%) | 116 (50) | 455 (79.68%) | 2.18 | 0.89 | 0.72 (3.18) | 0.56 | 80 | 20 | 65 (56.03%, 64.73%) | 8.39 | no |
| M0.5_R2_H3_W120 | 0 | 601 | 140 (23.29%, 26.84%) | 251 (92) | 350 (58.24%) | 0.40 | 1.05 | 0.27 (3.15) | 1.01 | 120 | 20 | 136 (54.18%, 60.24%) | 3.52 | no |
| M0.5_R2_H3_W120 | 20 | 601 | 140 (23.29%, 26.84%) | 226 (97) | 375 (62.40%) | -0.97 | 0.49 | -1.51 (3.15) | 0.52 | 113 | 20 | 123 (54.42%, 60.79%) | 0.35 | no |
| M0.5_R4_H3_W60 | 0 | 498 | 127 (25.50%, 29.51%) | 125 (48) | 373 (74.90%) | -1.75 | -0.35 | -11.57 (3.18) | -0.60 | 86 | 20 | 95 (76.00%, 82.64%) | -1.44 | no |
| M0.5_R4_H3_W60 | 20 | 498 | 127 (25.50%, 29.51%) | 80 (34) | 418 (83.94%) | -1.49 | -1.01 | -5.20 (3.21) | -4.34 | 63 | 19 | 60 (75.00%, 83.19%) | -0.89 | no |
| M0.5_R4_H3_W120 | 0 | 534 | 130 (24.34%, 28.16%) | 194 (67) | 340 (63.67%) | -1.68 | 0.87 | -7.30 (3.16) | 1.06 | 103 | 20 | 126 (64.95%, 71.31%) | -1.21 | no |
| M0.5_R4_H3_W120 | 20 | 534 | 130 (24.34%, 28.16%) | 174 (73) | 360 (67.42%) | -1.81 | 0.25 | -17.15 (3.16) | 0.35 | 99 | 20 | 114 (65.52%, 72.18%) | -1.60 | no |

## Diagnostics: why the signal loses (reading L, M=0.5, R=2, W=120, L=10)

n = 601 covered fires.  `official_value - E` (official integer minus the obs extreme at signal time): {"-4": 1, "-3": 2, "-2": 8, "-1": 145, "0": 337, "1": 87, "2": 14, "3": 3, "4": 3, "5": 1}; HIGH {"-3": 1, "-2": 6, "-1": 129, "0": 138, "1": 51, "2": 14, "3": 3, "4": 3, "5": 1}, LOW {"-4": 1, "-3": 1, "-2": 2, "-1": 16, "0": 199, "1": 36}.  A non-zero entry means the official value differs from what the obs showed; because reading-L fires have E sitting ON a bracket edge (M=0.5), a +/-1 disagreement moves the settlement into a neighbouring bracket -> false lock.

Calibration of the market at the first quote at/after signal+10 min, whatever its price (YES rate among fired rungs, by yes_ask):

| yes_ask bucket | n | settled YES | YES rate |
|---|---:|---:|---:|
| 0-49c | 127 | 3 | 2.36% |
| 50-79c | 13 | 9 | 69.23% |
| 80-94c | 24 | 24 | 100.00% |
| 95-98c | 53 | 53 | 100.00% |
| 99-100c | 344 | 344 | 100.00% |
| no_quote | 40 | 28 | 70.00% |

Where the book still offers the winner side at <=98c the book is, on average, correctly pricing the risk that the signal is wrong: the fires that are cheap are disproportionately the false locks.  This is adverse selection into the tradeable subset.

## Every skip, with its reason

| reason | count | where |
|---|---:|---|
| not_bracket_rung(T-threshold) | 33,487 | rungs, before the window filter |
| no_official_result('scalar') | 4 | rungs, before the window filter |
| close_after_2026-10-20 | 1,104 | bracket rungs outside the frozen 2026-05-23..2026-10-20 window (catalog also holds older/newer settled rungs) |
| close_before_2026-05-23 | 39,037 | bracket rungs outside the frozen 2026-05-23..2026-10-20 window (catalog also holds older/newer settled rungs) |
| event-level skips (tz assertion, insufficient obs) | 0 | 0 events skipped; the 1-minute->routine fallback was used for 930 events |
| series with no verified station/tz mapping (D7) | 1,800 | 8 series with in-window bracket rungs: KXHIGHTEWR=220, KXHIGHTSAN=248, KXHIGHTSDF=212, KXHIGHTTTN=220, KXLOWTEWR=220, KXLOWTSAN=248, KXLOWTSDF=212, KXLOWTTTN=220 (international + extra US); zero-rung series omitted |
| fired rung: no_candles_in_final_120min | 51 | no candle in the final 120 minutes -> outside 'candlestick coverage' universe, excluded from covered stats |
| fired rung: candle_fetch_error | 0 | HTTP error on both candle endpoints |
| fired rung: not_fetched | 3,247 | not reached by the shuffled candle pull (random, un-selected) -- sampling, see fraction above |
| scalar-result rungs | 4 | result neither yes nor no -> dropped |

## Caveats / what this does NOT show

{{CAVEATS}}
