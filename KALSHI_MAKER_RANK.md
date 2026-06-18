# KALSHI MAKER-EDGE RANKING — Soft (non-crypto) Favorite-Longshot Harvest

**Date:** 2026-06-18  **Scope:** Kalshi public API (`https://api.elections.kalshi.com/trade-api/v2`, no auth) + public fee docs.
**Job:** (1) nail the MAKER fee structure per category/series; (2) rank soft categories by favorite-longshot miscalibration; (3) name the 2–3 best (category, band, side) MAKER corners.

**Script:** `kalshi_maker_rank.py`. **Raw output:** `maker_rank_results.json`.

---

## 1. FEE STRUCTURE — the single most important finding

### 1a. The API itself tells you who pays maker fees
Every series carries a `fee_type` field. There are exactly two values in the soft universe:

| `fee_type` | Maker pays? | Meaning |
|---|---|---|
| `quadratic` | **NO — zero maker fee** | Taker pays `0.07·p·(1−p)·mult`; **maker pays $0**. |
| `quadratic_with_maker_fees` | **YES** | Maker pays `0.0175·p·(1−p)·mult` (= 25% of taker); taker pays `0.07·p·(1−p)·mult`. |

This is the decisive answer to the brief's CRITICAL question. **Makers do NOT pay the taker fee everywhere.** Maker fees are an opt-in flag set only on Kalshi's flagship/high-profile series. The default on low-volume soft markets is `quadratic` → **zero maker fee** — exactly the regime crypto15m enjoyed (post-only / maker-free), and exactly what a favorite-longshot maker harvest needs.

### 1b. Share of series carrying maker fees, by category (live API scan)

| Category | # series | `quadratic` (0 maker fee) | `quadratic_with_maker_fees` | **Maker-fee %** |
|---|---:|---:|---:|---:|
| **Politics** | 2045 | 2045 | 0 | **0.0%** |
| **Climate and Weather** | 281 | 281 | 0 | **0.0%** |
| **World** | 151 | 151 | 0 | **0.0%** |
| **Companies** | 175 | 175 | 0 | **0.0%** |
| **Science and Technology** | 332 | 331 | 1 | **0.3%** |
| **Entertainment** | 2478 | 2471 | 7 | **0.3%** |
| **Economics** | 581 | 571 | 10 | **1.7%** |
| **Sports** | 2230 | 2122 | 108 | **4.8%** |

The maker-fee series are precisely the flagships (verified by ticker):
- **Sports (108):** `KXNBA`, `KXSB` (Super Bowl), `KXNFLSPREAD`, `KXNHLGAME`, `KXINDY500`, `KXWNBA`, `KXNFLANYTD`, US Open, NBA Finals MVP…
- **Economics (10):** `KXFED`, `KXCPI`, `KXGDP`, `KXU3` (unemployment), `KXPAYROLLS` (jobs), `KXRATECUTCOUNT`, `KXEGGS`, `KXAAAGASM` (gas)…
- **Entertainment (7):** the Emmys slate (`KXEMMY*`) + `KXSUPERBOWLHEADLINE`.

**Implication:** if you simply avoid those named flagship series, the maker fee is **$0** across 95–100% of every soft category. The miscalibration you harvest is kept in full — there is no maker fee to net against the spread.

### 1c. The fee formula (taker, and maker where charged)
Quadratic, peaking at p=0.50, vanishing at the extremes — which is favorable because favorite-longshot harvest lives in the tails (p<0.15 and p>0.85) where even the taker fee is small:

- **Taker:** `fee = ceil_to_$0.0001( 0.07 · C · p · (1−p) · fee_multiplier )` per contract. Max ≈ **1.75¢** at p=0.50; ≈0.60¢ at p=0.10/0.90; ≈0.33¢ at p=0.05/0.95.
- **Maker (only on `quadratic_with_maker_fees` series):** `0.0175 · C · p · (1−p)` = **25% of taker**. Max ≈0.44¢ at p=0.50; ≈0.16¢ at p=0.10/0.90.
- **Maker (on plain `quadratic` series):** **$0.00.**
- `fee_multiplier` in the API is a **taker** scalar (almost all soft series = 1; a handful = 0). It is NOT a maker field. S&P/Nasdaq index series use 0.035 (half) per the public schedule, but those are not in the soft set we target.
- Fee rounding is **up** to the nearest $0.0001 and the fee accumulator is kept per-order "regardless of whether fills are taker or maker" — i.e. there is **no maker rebate**; the only maker discount is the all-or-nothing `fee_type` flag above.

### 1d. Source reconciliation (third-party sources conflicted — API is authoritative)
Public secondary sources split into two camps and **both are partially right**:
- "Maker = 25% of taker (0.0175·p·(1−p))" — correct *for series that charge maker fees*.
- "0% / effectively zero maker fee on most markets" — correct *for the default `quadratic` series*.

The API `fee_type` flag resolves the contradiction cleanly: maker fees are a per-series opt-in, charged on flagships only. Honest caveat: the Feb-2026 official PDF (`kalshi.com/docs/kalshi-fee-schedule.pdf`) is a JS-rendered viewer that neither WebFetch nor curl could extract as text (HTTP 429 / Astro HTML shell), so the per-series maker list is taken from the **live API flag** (primary, authoritative) corroborated by secondary write-ups.

**Sources:**
- Kalshi public API `fee_type` field (primary): `GET /series?category=…` on `api.elections.kalshi.com` — observed values `quadratic` and `quadratic_with_maker_fees`.
- Kalshi Fee Schedule (Feb 2026): https://kalshi.com/docs/kalshi-fee-schedule.pdf (viewer; not text-extractable) and https://kalshi.com/fee-schedule
- Kalshi Help Center — Fees: https://help.kalshi.com/en/articles/13823805-fees
- Kalshi API docs — Fee Rounding: https://docs.kalshi.com/getting_started/fee_rounding ; event fee overrides: https://docs.kalshi.com/api-reference/events/get-event-fee-changes
- pm.wiki, marketmath.io, predictionhunt.com, usigaminghub.com (secondary, July-2025 update: maker 0.0175·C·p·(1−p) on high-profile series; flat $0.0025 pre-July-2025).

---

## 2. SOFTNESS RANKING (favorite-longshot miscalibration)

**Method.** Per category: `GET /series?category=` → sample series → `GET /markets?series_ticker=&status=settled` (binary only, exclude `mve_collection_ticker` MVE legs, require `volume_fp ≥ 300`, `result∈{yes,no}`) → `GET …/candlesticks?period_interval=60` over `[open_time, close_time]`, take the **mid-life hour** quote: `mid=(yes_bid.close+yes_ask.close)/2`, `spread=yes_ask−yes_bid`. Bias = `realized_WR − mean(mid)` per price bin. Category score = volume-weighted mean |bias|.

**Sample:** ~370 priced settled markets across ~70 sampled series (caps: 50 series/cat, 6 markets/series).

| Rank | Category | n_mkts | Vol-wtd \|bias\| (pp) | Maker fee on bulk? | Notes |
|---:|---|---:|---:|---|---|
| 1 | Science & Technology | 23 | 18.8 | **0% (default)** | thin sample; high variance, wide CIs |
| 2 | Politics | 22 | 17.8 | **0% (all)** | clean tails; strong longshot overpricing |
| 3 | Climate & Weather | 74 | 11.9 | **0% (all)** | good n, tight spreads, real volume |
| 4 | Entertainment | 23 | 10.4 | **0% (bulk)** | very tight tail spreads (1–2pp) |
| 5 | Economics | 68 | 8.1 | **0% (bulk; flagships excl.)** | good n; favorite under-pricing |
| 6 | Sports | 78 | 8.0 | 0% bulk / **4.8% flagged** | huge volume; flagships charge maker |
| — | World / Companies | 1 / 0 | n/a | 0% | too few settled binaries to rank |

**Caveat (brutal honesty):** per-bin n is small (often 1–8), so individual `bias_pp` values carry ±15–35pp binomial SE. Treat the *direction and ordering* as signal, the point estimates as noisy. The classic favorite-longshot signature (longshots overpriced → negative bias; favorites underpriced → positive bias) shows up most cleanly in **Politics** and **Climate**; Sports/Econ are muddier.

### Key bins (priced via real mid-life candles)

**Politics** — textbook longshot overpricing, tiny spreads, real volume:
- 0.15–0.25: mid 0.193, WR **0.00**, bias **−19.3pp**, spread 5.3pp, vol 30k
- 0.25–0.40: mid 0.320, WR **0.00**, bias **−32.0pp**, spread 3.0pp, vol 769k
- 0.40–0.60: mid 0.516, WR 0.25, bias **−26.6pp**, spread 5.2pp, vol 31k
- Favorite side 0.85–1.00: bias +4.6 to +15pp, spreads 4–6pp.

**Climate & Weather** — best sample size, tight spreads:
- 0.10–0.15: mid 0.125, WR 0.00, bias **−12.5pp**, spread 8.0pp, vol 38k
- 0.40–0.60: mid 0.482, WR 0.286, bias **−19.6pp**, spread 6.4pp, vol 147k
- 0.60–0.75: mid 0.635, WR 0.25, bias **−38.5pp**, spread 6.0pp, vol 97k
- (longshot 0–0.05 well-calibrated: bias −2.2pp — extreme tail is efficient)

**Entertainment** — tail spreads are razor-thin (good for a maker):
- 0.10–0.15: mid 0.140, WR 0.00, bias **−14.0pp**, spread **1.0pp**, vol 536k
- 0.15–0.25: mid 0.220, WR 0.00, bias **−22.0pp**, spread 2.0pp, vol 2.5k
- favorite 0.75–0.90: bias +10 to +22pp, spreads 6–11pp.

**Economics** — favorite *under*-pricing is the cleaner edge:
- 0.75–0.85: mid 0.795, WR **0.90**, bias **+10.5pp**, spread 6.6pp, vol 40k (n=10, SE 9.5)
- 0.25–0.60: bias +14pp but spreads wide (14–20pp) → harder to make.

---

## 3. THE 2–3 BEST MAKER CORNERS

Selection = large favorite-longshot bias × maker keeps spread (`fee_type=quadratic` ⇒ **$0 maker fee**) × coverable spread × non-zero volume.

### Corner A — **Politics, BUY-NO maker on longshots 0.15–0.40** ⭐ top pick
- Bias **−19 to −32pp** (longshots overpriced ⇒ NO is cheap relative to truth).
- **Maker fee = $0** (Politics is 100% `quadratic`). You keep the entire spread + the bias.
- Spreads **3–5pp** — easily coverable by a passive NO bid. Volume 30k–769k contracts in-band.
- Trade: rest a NO buy (= sell YES) just inside the ask in the 0.15–0.40 YES band on resolved-binary political longshots; harvest both the half-spread and the structural over-pricing.

### Corner B — **Climate & Weather, BUY-NO maker on 0.40–0.75** ⭐
- Bias **−19.6pp (0.40–0.60)** and **−38.5pp (0.60–0.75)**: these "coin-flip / slight-favorite" weather longshots resolve NO far more than priced.
- **Maker fee = $0** (Climate is 100% `quadratic`). Spreads 6–6.4pp, vol 97k–147k. Best n in the study (74 markets).
- Trade: passive NO bids in the 0.40–0.75 YES band. Note the extreme tail (<0.05) is efficient — stay in the mid-tail, not the deep tail.

### Corner C — **Entertainment, BUY-NO maker on longshots 0.10–0.25** (tightest spreads)
- Bias **−14 to −22pp**; spreads an exceptional **1–2pp**, so almost the whole edge is net.
- **Maker fee = $0** on the bulk (`quadratic`); the only Entertainment maker-fee series are the 7 Emmys/`KXSUPERBOWLHEADLINE` flagships — **avoid those tickers** and you pay nothing.
- Lower volume than A/B per market (2.5k–536k, uneven) → smaller capacity, but cleanest spread economics.

**Honorable mention not chosen:** *Economics favorites 0.75–0.85 BUY-YES* (bias +10.5pp, $0 maker fee once you exclude the 10 flagged macro series). Real but smaller edge and you must screen out `KXFED/KXCPI/KXGDP/KXU3/KXPAYROLLS/...`. **Sports** is excluded as a primary corner: 4.8% of series (every flagship: NBA, NFL, SB, NHL, Indy500) charge the 0.0175·p·(1−p) maker fee, and bias is the weakest (8.0pp) and noisiest.

---

## 4. VERDICT

1. **Maker fee is the thesis's friend, not its enemy.** Kalshi flags maker fees per-series via `fee_type`. The default soft-market value `quadratic` means **makers pay $0**; only flagship series (`quadratic_with_maker_fees`: NBA/NFL/SB/Indy500, Fed/CPI/Jobs, Emmys) charge makers 0.0175·p·(1−p) (=25% of taker). So **Politics, Climate, World, Companies = 0% maker everywhere**; Entertainment/Science/Econ are 0% on >98% of series; Sports 95%.
2. **Best deployable corners (all zero-maker-fee):** **(A) Politics BUY-NO on 0.15–0.40 longshots** (bias −19 to −32pp, spread 3–5pp); **(B) Climate BUY-NO on 0.40–0.75** (bias −20 to −39pp, spread ~6pp, best sample); **(C) Entertainment BUY-NO on 0.10–0.25** (bias −14 to −22pp, spread 1–2pp).
3. **The harvested edge is kept in full** — there is no maker fee to net against the spread on these series, unlike a taker who bleeds 0.07·p·(1−p) every fill.
4. **Brutal caveats:** per-bin n is small (±15–35pp SE) — direction is robust, magnitudes aren't; mid-life single-candle pricing is coarse; and **adverse selection / fill-rate / capacity are NOT modeled here** (separate agents) and can erase the printed edge. Deep tails (<0.05) are already efficient — fish the mid-tails.
5. **If a future schedule flips soft series to `quadratic_with_maker_fees`,** re-screen by `fee_type` before deploying — the whole edge depends on the maker keeping the spread fee-free.
