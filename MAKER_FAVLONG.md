# Favorite-Longshot Bias, Maker (Resting-Bid) Capture — DEPLOYABLE: NO

**Bottom line: both the taker-side and the maker-side attempts to capture Kalshi's
favorite-longshot bias are now dead. Two independent maker backtests, adversarially
reconciled by a Fable verifier pass, agree on a null: no liquidity cell clears its
pre-registered bar, honest capacity is $0/mo, and adverse selection is not even the
proximate kill — the edge dies first on day-clustered insignificance and on fill
realism. No sleeve is being shipped.**

This closes the favorite-longshot bias investigation for both execution styles this repo
can build a bot around. See `RESEARCH_LEDGER.md` §3/§6 for the updated meta-conclusion.

---

## 1. Why this question was still open after the taker-side kill

`FAVORITE_LONGSHOT.md` (PR #55, 2026-07-22) pre-registered and ran three **taker** specs
— buy/sell at the crossing (marketable) price, immediately, the way `kwx_runner.py`'s
mechanical-lock strategy already trades:

- **Spec 1 — broad longshot fade** (sports + other + fx_index): **CONFIRMED FAIL**. Net
  EV at realistic crossing price −3.41c/ct, day-clustered t=−4.87, honest capacity
  **−$60/mo** (a loser). Crossing-price slippage (3.18c) eats a naive +1.70c signal edge.
- **Spec 2 — favorite buy (70–90c band)**: candidate universe built clean but the
  candidates × 172M-trade join did not finish inside the compute budget — **closed as
  execution-limited**, not a measured negative, scored deployable=NO / $0/mo by the
  can't-ship-what-can't-be-checked rule.
- **Spec 3 — crypto isolation**: **CONFIRMED FAIL**. Structurally underpowered (40 events
  vs a 200-event floor, hard population ceiling of 84) and the point estimate itself is
  negative (−4.17c/ct, t=−0.64, CI crosses zero), driven almost entirely by one bad day.

**Both completed taker specs (1 and 3) are dead** — Spec 2 never got a number either way.
But the house rules are explicit that a taker-side kill doesn't settle the maker
question: `wx_maker_deep_study.md` already showed, for a *different* mechanism
(post-lock weather near-certainty), that a strategy dead at the crossing price can still
in principle be alive as a passive resting bid, because a maker never pays the spread —
it posts and waits, collects $0 maker fee on `KXHIGH*`/`KXLOWT*` weather series, and
isn't racing anyone on latency. The favorite-longshot bias is a different mechanism
(mispricing across the whole price axis, not just near-certainty weather), untested for
market-making across the **liquid universe** (sports, fx/index — the categories where
Spec 1's capital actually lives), and deployability profile is attractive on paper:
non-latency, persistent behavioral bias, capacity in principle huge (hundreds of
thousands of markets). The only structural kill risk that matters for a maker is
**adverse selection** — does your resting bid get filled preferentially right before the
price moves against you — plus a secondary **fill-realism** risk (would you actually get
filled resting at the naive price, or would you need to bid closer to fair, which erodes
the edge). This document reports that test.

## 2. The maker hypothesis and what was tested

Hypothesis: post a resting bid on the **favored side** of the favorite-longshot
mispricing (buy YES in the underpriced-favorite band, buy NO in the overpriced-longshot
band — the same directional read as `FAVORITE_LONGSHOT.md`'s taker specs) at or near the
prevailing best bid, across the liquid (non-weather) universe, and measure realized P&L
**conditioned on actually being filled** — i.e., exactly the `taker_side`-opposite prints
(a `taker_side='no'` hit fills a resting YES bid; a `taker_side='yes'` hit fills a
resting NO bid), priced at the print, settled against the real outcome. That
conditioning is what makes the sample adverse-selection-honest: it is not a fill-rate
assumption or an unconditional average, it is the actual population of fills a resting
maker order would have received.

Two independent backtests were run and cross-checked:

| | Study A | Study B |
|---|---|---|
| Cut | category × price-band, at print price | liquidity-tier, pooled favorite side |
| Fit/validation split | volume-weighted, 2025-12-28 | calendar, 2024-07-01 |
| Pnl sample | `taker_side`-opposite fills at print price, day-clustered | same conditioning, per-fill + day-clustered |
| Fee model | Kalshi taker fee formula for the resting-bid side's eventual settlement (see §3 for the maker-fee correction) | same |

Both pipelines' SQL was verified to select **exactly** the taker-side-opposite fills —
no unconditional-rate substitution, no settlement leakage into the entry signal.

## 3. Results and reconciliation

**No cell in either study passes its pre-registered bar. Honest $/mo = $0. Not
deployable.**

Where the studies overlap (sports/liquid, validation window): point estimate **+0.4c to
+1.3c/contract**, day-clustered t ≈ **0.6**, 95% CI crossing zero. Read literally as
noise, not edge.

The studies' apparent disagreement resolves cleanly on inspection: Study B's
"significant" T1/T2 positive cells are **unweighted per-fill means in thin/illiquid
markets** — the classic favorite-longshot bias surviving only where there is no capacity
to trade it, and its fit-period sign flips (not persistent). This matches Study A's
price-grid finding directly: capturing real volume requires bidding **80–90c**, where
realized pnl is **−7c to −18c/contract** — deep in FAVORITE_LONGSHOT.md Spec 1's
spread-eats-the-edge death mode, now reproduced independently on the maker side.

| Cell | Point estimate | Day-clustered t | Pass bar? |
|---|---|---|---|
| Sports/liquid, validation overlap (A ∩ B) | +0.4c to +1.3c/ct | ≈0.6 | NO — CI crosses zero |
| High-liquidity tier (B, actual historical fill prices) | edge compresses ~½–⅔ moving into this tier | — | NO |
| Bid-to-fill-volume price grid (A, 80–90c to capture real size) | **−7c to −18c/ct** | — | NO — negative |
| Thin/illiquid tiers (B, T1/T2, "significant" in isolation) | nominally positive | nominally significant | Disqualified: unweighted per-fill mean in a tier with no capacity, sign flips fit→validation |

**Honest capacity: $0/mo.**

## 4. Fee-rule correction (a genuine finding, independent of the null verdict)

`wx_maker_deep_study.md` established $0 maker fee for `KXHIGH*`/`KXLOWT*` weather
series via a live probe of 5 sampled series plus a prior 196-series incentive-program
sweep. That $0 assumption does **not** generalize to the dominant category this study
covers. Live `/series/{ticker}` probes run 2026-07-22 show
`fee_type=quadratic_with_maker_fees` (maker fee `ceil(0.0175·C·P·(1−P))` ≈ 0.33c/contract
at p≈0.75, i.e. 25% of the taker fee — not $0) on:

`KXNBAGAME, KXNFLGAME, KXNCAAFGAME, KXNCAAMBGAME, KXMLBGAME, KXNHLGAME, KXNBATOTAL,
KXNFLSPREAD, KXEPLGAME, KXWTAMATCH, KXATPMATCH, KXFEDDECISION`

— i.e. the dominant sports category and two of the previously-flagged "future candidate"
series now charge a maker fee. The earlier "only 3 maker-fee series" claim covered only
the 196 incentive-program series, not the sports vertical. Weather, crypto, and
FX/index series are confirmed **still $0 maker fee**. This cuts the already-null quoted
sports edges by a further ~0.3–0.4c/contract — it strengthens the null, it does not
create one; the primary verdict above is already negative before this correction is
applied.

## 5. Adverse selection

Conditioning is honest in both studies — the pnl sample is exactly the resting-bid fills
(`taker_side='no'` hits on a YES bid at `yes_price`; `taker_side='yes'` hits on a NO bid
at `no_price`), priced at the print, settled against the real result. This was verified
directly in each pipeline's SQL. **The null primary result above already has all adverse
selection baked in** — there is no separate unconditional-rate substitution to correct
for.

A secondary, separate claim in Study A — a pooled adverse-selection "gap" table claiming
selection is "small and mostly favorable" — is **not established** as measured: filled
vs. unconditional average prices differ by up to 1.4c (e.g. sports yes-favorite 74.6c
filled vs. 73.2c unconditional), which is a price-mix confound, not a clean measurement
of selection. This does not affect the primary conditioned-pnl verdict above, but the
side-claim should not be cited as "adverse selection is proven small" — it wasn't proven
either way. A price-matched gap recompute (9 shards, processed one at a time per the
trade-shard-heavy compute constraint) was launched to settle this; only 1/9 shards
completed before the reporting deadline, consistent with the partial result but not a
full re-derivation.

**Adverse selection is not the binding kill here.** The edge fails first on
day-clustered insignificance (t≈0.6, CI crosses zero) and on fill realism: to capture
material volume a maker must bid 80–90c, where the price-grid shows −7c to −18c/contract,
and the edge compresses roughly half to two-thirds moving into the high-liquidity tier
even priced at actual historical fill prices.

## 6. Fill realism (the other kill risk named in the pre-registration)

Modeled realistically — a resting bid posted at the prevailing bid, credited only with
fills that occurred at or below that price (no front-of-queue assumption) — capturing
real volume requires bidding materially closer to fair value (80–90c in Study A's grid),
which is exactly where the realized pnl turns negative (−7c to −18c/contract). The
naive thin-tier "significant" cells in Study B only look attractive because they trade
almost no size; scaled to any capacity that matters, the edge is gone before adverse
selection is even the question.

## 7. Data integrity

12/12 fresh random settlement spot-checks (sports incl.
`KXMVESPORTSMULTIGAMEEXTENDED`, crypto, weather, fx/index) matched the authoritative
`/historical/markets` API. 0 duplicate tickers across market shards. Verification of the
core SQL in both pipelines confirms the pnl-conditioning claim in §5. The independent
price-matched gap recompute did not finish (1/9 shards) before the deadline — flagged
above, not hidden.

## 8. Fable adversarial verdict (final)

| Field | Value |
|---|---|
| Verdict | **CONFIRMED** (both studies' null reconciles; disagreements resolve to a price-mix/thin-tier artifact, not a real positive cell) |
| Deployable | **NO** |
| Honest capacity | **$0/mo** |
| Governing reason | No cell clears its pre-registered bar; day-clustered t≈0.6 with CI crossing zero on the only overlap that isn't disqualified by thin-tier unweighting; capturing real volume requires bidding into a −7c to −18c/ct price zone |
| Adverse selection | Honestly conditioned in both primary pipelines (not the binding kill); a secondary pooled gap-table side-claim of "mostly favorable" selection is overstated (price-mix confound), separately flagged |
| Fee correction | Sports vertical (dominant category) now charges `quadratic_with_maker_fees` (~0.33c/ct at p≈0.75), not $0 — strengthens the null; weather/crypto/FX-index confirmed still $0 |

## 9. Disposition

**Per the house build-gate: since deployable=false, no sleeve is being shipped.**
`wx_makerfl_model.py` / `wx_makerfl_paper.py` / `wx_makerfl_decision.py` are explicitly
**not** built — this repo's convention (see `book_watch`, `early_lock`, `maker`,
`forecast` in `p4k_params.json`, all marked `DO NOT MODEL AS A LEVER`) is not to ship a
null as a lever. This document is doc-only.

**Both execution styles for the favorite-longshot bias — taker (crossing-price entry,
`FAVORITE_LONGSHOT.md`) and maker (resting-bid, this document) — have now been
adversarially tested on real Kalshi data and both are dead.** The raw-calibration
mispricing (`FAVORITE_LONGSHOT.md` §1) is real; capturing it with any bot this repo can
build is not. `RESEARCH_LEDGER.md` §3 and §6 are updated accordingly — see the new
graveyard row and the revised meta-conclusion.

## 10. Reproduction

The two backtests (Study A, Study B) and the Fable reconciliation pass that produced §3–§8
above were run against `kx_history.py`'s DuckDB/parquet trade-tape archive (~172M trades)
following this repo's standard shard-at-a-time compute discipline (filter by
`taker_side` + `yes_price` first, aggregate per shard, then join to a small pre-built
outcome table — `kx.TRADES(i) for i in range(kx.N_TRADE_SHARDS)`, summed, never a glob
scan). Per repo convention (see `wx_maker_deep_study.md` §6, `FAVORITE_LONGSHOT.md` §6),
large intermediate caches and per-shard scratch scripts are not committed to keep the
repo small; this document is the compact, audited artifact of that work — the same
pattern used for every other study in the graveyard. A future session reopening this
question should start from `FAVORITE_LONGSHOT.md`'s pre-registered bands/categories and
this document's §3 price grid (80–90c is the deployability wall to solve, not the
adverse-selection gap) rather than re-deriving the null from scratch.
