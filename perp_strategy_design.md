# perp_strategy_design.md — three paper edges to build once real Kalshi-perp data lands

**Status:** design only. No perp data has accrued yet — `kalshi_perp_collect.py` (this PR) starts the
clock. Every edge below is **collect-then-forward-validate**: it is NOT tradeable until it clears the
same forward gate FAVLONG must clear (see §Gate). We design now so the collector captures exactly the
fields each edge needs, and so the forward ledger starts on day 1 of real data.

**Why perps at all:** carry/basis on a delta-neutral perp book is a return driver *orthogonal* to
FAVLONG (a directional-binary favorite-longshot edge). Orthogonality is the point — it diversifies
the book, it is not a second bet on the same factor.

---

## 0. What the collector actually captures (the ground truth these edges read)

Confirmed live 2026-07-15 against `external-api.kalshi.com/trade-api/v2/margin/markets` (public read):
16 crypto perps `KX{BTC,ETH,SOL,XRP,LINK,LTC,DOGE,BCH,DOT,HBAR,NEAR,SUI,XLM,ZEC,HYPE,KSHIB}PERP`.
Per perp, per poll, `ticks_kalshi_perp_<asset>_*.jsonl.gz` rows carry:

| field | meaning | edge that needs it |
|---|---|---|
| `bid` / `ask` / `mid` | perp top-of-book (dollars per contract) | all |
| `book.bids/asks` | full depth, near-touch-first (paired assets) | execution/capacity |
| `index` (`reference_price`) | CF Benchmarks **BRTI** spot index | basis (a), (c) |
| `mark` (`settlement_mark_price`) | mark used for funding/liq settlement | carry (b) |
| `last` (`price`) | last trade | all |
| `funding.funding_rate` | current funding rate (per ~8h stamp) | carry (b) |
| `funding.next_funding_time` | next funding stamp (UTC; ~8h cadence) | carry (b) |
| `open_interest`, `oi_notional_usd` | OI + $ notional | capacity/regime |
| `volume`, `volume_24h`, `*_notional_usd` | traded volume | capacity |
| `contract_size` | BTC per contract (e.g. `0.0001`) | **spot conversion** |
| `tick_size`, `leverage_estimate`, `liq_mark` | microstructure / risk | sizing |

**The one conversion everything hangs on — perp-implied spot:**

```
implied_spot_perp = perp_mid / contract_size      # e.g. 6.472 / 0.0001 = $64,720
```

The `index` field already *is* the BRTI spot (in the same per-contract units — divide by
`contract_size` for dollars). Same-clock 15m-binary YES mids for btc/eth/sol/xrp are co-collected in
`ticks_kalshi_perp_binmid_<asset>_*.jsonl.gz`, so the SAME-venue basis in (a) is computable on one
clock without cross-workflow time alignment.

**Cost assumptions (documented, not fit — carried from `PERPS_BACKTEST.md` so numbers are comparable):**
perp taker **6 bps/fill**, maker **1.5 bps/fill**; Kalshi perp fees are currently **0%** but we keep
the conservative generic assumption so an edge isn't a fee-holiday artifact. Binary side uses the
existing shadow schema (no rebate on Kalshi). Funding is paid/received on **mark × position** at each
~8h stamp.

---

## 1. Edge (a) — perp ↔ binary basis (SAME venue: Kalshi perp vs Kalshi 15m binary)

**Idea.** Both instruments price the same underlying on the same venue. The perp gives a continuous
implied spot; the 15m binary *ladder* gives a risk-neutral implied spot from the strike at which
`P(close > K) = 0.5`. When they disagree beyond costs, one leg is rich.

**Signal.**
- `implied_spot_perp = perp_mid / contract_size` (from the perp stream).
- `implied_spot_bin`: from the binary strike ladder, the strike `K*` where the YES probability
  crosses 0.5, linearly interpolated between adjacent rungs (risk-neutral median ≈ forward spot).
  For the single-strike 15m up/down market, the aligned `binmid` YES = `P(up)` at the window's own
  strike `K0` gives one `(K0, p)` point; stack the live window + the adjacent-window strikes into a
  local ladder to interpolate `K*`. (The multi-strike hourly/daily ladders `KXBTCD…`, already
  shadow-collected by `kalshi_ladder_collect.py`, are the cleaner ladder when a 15m ladder is thin.)
- `basis_bps = 1e4 * (implied_spot_perp / implied_spot_bin - 1)`.
- **Entry:** `|basis_bps| > entry_thr` (frozen; candidate 15–40 bps to clear round-trip cost).
  Long the cheap leg / short the rich leg, **delta-neutral** in spot terms:
  size the binary notional and the perp notional to equal $-delta at entry.
- **Exit:** basis reverts inside `exit_thr` (hysteresis, `exit_thr < entry_thr`), or the 15m binary
  settles (forced unwind of that leg; see accounting).

**Settlement / PnL accounting.**
- Perp leg: marked-to-`mark` continuously; realized P&L = `Δ(mark) × position_contracts × contract_size`
  minus funding paid/received over the hold (usually ≤ one 8h stamp for a ≤15-min basis trade → near
  zero), minus entry+exit fees.
- Binary leg: the 15m market **settles to 0/1** at window close. The basis trade is held to the
  binary's forced settlement (or unwound earlier at the binary mid). P&L of the binary leg =
  `settlement(0/1) − entry_price` (YES) per contract, ± fees; the perp leg is unwound at the same
  instant at its mid. **Net P&L = perp leg + binary leg**, and the *basis* view is `entry_basis −
  exit_basis` scaled by the neutral notional. Book both legs' fills into the existing
  `shadow_compare`-style rows (venue `kalshi`, rebate 0) so the forward scorer is the same code path.
- **Convergence anchor:** at binary settle, `implied_spot_bin` collapses to realized spot, so the
  basis trade's edge is precisely "was the perp rich/cheap vs where spot actually settled" — a clean,
  self-settling accounting with no mark ambiguity.

**Forward-validation gate.** See §Gate. Cluster unit = `(asset, day)`. A "trade" = one entered basis
pair scored at its unwind. Freeze `entry_thr/exit_thr/neutral-sizing` before forward day 1.

**Known risks.** (i) The 15m ladder can be too thin to invert a clean `K*` — fall back to the
hourly/daily ladder or skip the window (log it; a skipped window is data). (ii) Perp `mid` vs binary
`mid` have different tick/'spread regimes; cost model must use *marketable* prices, not mids, at
sizing time. (iii) Same-venue does not mean same-settlement-clock (perp never settles; binary does) —
the accounting above handles this by holding to binary settle.

---

## 2. Edge (b) — funding carry (harvest the funding-rate, delta-neutral)

**Idea.** Kalshi perp funding is paid ~every 8h on `mark × position`. When trailing funding is
persistently positive, **short perp / long spot** (or long the cheapest available spot proxy) collects
it; persistently negative, the reverse. This is the ONE perp edge that cleared the repo's bar OOS in
`PERPS_BACKTEST.md` (BTC funding carry, OOS t=+6.67, ≈+2.5%/yr) — but on *Deribit* funding. **This
edge re-runs that test on Kalshi's own funding regime**, which is the whole reason to collect it (the
`PERPS_BACKTEST.md` caveat: "re-pull that venue's own funding before trusting the $/day numbers").

**Signal.**
- Accrue `funding.funding_rate` and `funding.next_funding_time` per stamp → build the realized
  per-stamp funding series per asset. Annualize: `ann = funding_rate × (365 × 24 / 8)`.
- Trailing signal: 7-day mean of annualized funding, **lagged one stamp** (decided on data strictly
  before the current stamp — no look-ahead), exactly the `PERPS_BACKTEST.md` construction.
- **Entry:** short-perp/long-spot when trailing signal `> +entry_thr` (candidate 5%/yr); long-perp/
  short-spot when `< −entry_thr`; flat in a hysteresis band down to `exit_thr` (candidate 1%/yr) to
  avoid churn (this repo's prior carry screens found churn is what kills carry).
- Delta-neutral: the spot leg (external spot / `spot_composite`, or a second Kalshi instrument) is
  sized to offset the perp's dollar delta so P&L ≈ pure funding minus turnover cost.

**Settlement / PnL accounting.**
- Daily/stamp P&L = `−position × funding_rate_that_stamp − cost × |Δposition| / 2`, where `position`
  is signed perp exposure (short = +1 collects positive funding). `−position × funding` is the funding
  cash flow on `mark × contracts × contract_size`; the spot leg is delta-flat so contributes ~0
  price P&L by construction (its own funding/borrow, if any, is booked separately and is ~0 for a held
  spot).
- Round-trip cost (2-leg, open+close = 4 fills): **24 bps taker / 6 bps maker** (as `PERPS_BACKTEST.md`).
- Because funding P&L barely moves stamp-to-stamp, expect a **high Sharpe but small annualized**
  return (8–11 Sharpe = "small steady low-vol payoff," NOT "amazing" — flag this explicitly so it is
  not oversized).

**Forward-validation gate.** See §Gate. Cluster unit = `(asset, day)`; per-day P&L is the daily
funding-carry return. **Watch for the `PERPS_BACKTEST.md` ETH failure mode**: ETH carry looked great
in-sample and *reversed sign* OOS (t=−3.25). The forward gate must be run **per asset** — a pooled
pass can hide a single-asset reversal. Kill any asset whose forward pooled t < 0.

**Known risks.** (i) Kalshi funding is only ~8h cadence → a ≤15-min-style book rarely crosses a stamp;
carry is a *multi-day hold*, a different risk profile (overnight gap, liquidation on the perp leg —
monitor `liq_mark`). (ii) The delta-neutral spot leg needs a real venue; if the only spot is external,
this becomes a cross-venue trade with its own basis risk (→ edge c). (iii) `contract_size` minimum
(`0.0001 BTC` ≈ $6.5/contract now; was 0.01 in `PERP_HEDGE.md` — **the product re-scaled**, so
capacity/min-size must be re-checked from the live `contract_size`, never hardcoded).

---

## 3. Edge (c) — perp ↔ spot basis (Kalshi perp vs external spot / `spot_composite`)

**Idea.** The classic cash-and-carry: perp trades at a premium/discount to spot (the basis is the
market's forward funding expectation). When `implied_spot_perp` diverges from a robust external spot
(`spot_composite` — the repo's blended Coinbase/etc. feed — or the perp's own `index`/BRTI as the
reference), short the rich / long the cheap, delta-neutral, and collect convergence + funding.

**Signal.**
- `implied_spot_perp = perp_mid / contract_size`.
- `spot_ext`: `spot_composite` (external blended spot) **or** the perp's `index` field (BRTI) as the
  same-object reference (captured every poll → no cross-feed latency).
- `basis_bps = 1e4 * (implied_spot_perp / spot_ext − 1)`.
- **Entry:** `|basis_bps| > entry_thr` (frozen). **Exit:** revert inside `exit_thr`, or roll at a
  funding stamp. Distinguish the two reference choices as **two registered variants** (`c_index` uses
  BRTI, `c_composite` uses external spot) — `c_index` isolates pure perp mispricing vs its own
  reference (near-mechanical, tiny), `c_composite` adds cross-venue spot basis (larger, noisier).

**Settlement / PnL accounting.**
- Perp leg marked to `mark`; spot leg marked to `spot_ext`. P&L = `Δbasis × neutral_notional +
  funding_collected − costs`. No hard settlement (perp never expires) → the trade is closed on
  reversion or at a chosen horizon; **there is mark ambiguity** (unlike edge a's self-settling binary),
  so book the exit at *marketable* prices and treat mark-to-mark P&L as unrealized until unwound.
- Costs: 6 bps taker / 1.5 bps maker per fill, both legs.

**Forward-validation gate.** See §Gate. Cluster unit = `(asset, day)`; a trade scored at unwind.
`c_index` and `c_composite` scored separately (they are different edges).

**Known risks.** (i) `c_composite` inherits the external feed's outages/lag — a feed glitch prints a
fake basis; gate on feed-fresh windows only. (ii) `c_index` basis is near-mechanical and likely too
small to beat costs — expect it to *fail* the gate and serve mainly as the clean benchmark for how
much of `c_composite`'s basis is genuine cross-venue vs measurement noise. (iii) US-legal spot venue
for the neutral leg is a real constraint (Binance/Bybit geo-blocked per `PERPS_BACKTEST.md`).

---

## Gate — the forward-validation bar (identical discipline to FAVLONG)

Copied from `favlong_forward.py` / `FORWARD_LEDGER.md`, **do not relax**:

> **Pooled per-`(asset, day)` day-clustered t ≥ 2 over ≥ 10 FORWARD days** (days strictly AFTER the
> edge's frozen-params date), post-cost.
> - **PASS:** ≥ 10 forward days AND pooled day-clustered t ≥ 2 → promotable to paper-live.
> - **FAIL/KILL:** ≥ 10 forward days AND pooled t < 0 → kill per charter.
> - **PENDING:** < 10 forward days → keep collecting, no decision.

Rules that make the gate honest (all from the FAVLONG harness):
1. **Freeze every parameter** (thresholds, sizing, reference choice) BEFORE forward day 1 and persist
   them as JSON. Forward days apply the frozen config unchanged — **no refit, ever** (refitting on
   forward data is the leakage this whole apparatus exists to prevent).
2. **Only score COMPLETE forward days** (strictly before today UTC) so logged data never changes.
3. **Day-clustering is mandatory** — raw t-stats here are ~3–4× clustering-inflated (see `FINDINGS.md`:
   naive t=2.27 collapsed to clustered t=1.12). The honest unit is the `(asset, day)`, not the tick.
4. **Score each asset separately AND pooled.** Carry (b) proved a single asset (ETH) can reverse sign
   OOS while the pool looks fine — a pooled-only gate would have shipped a loser.
5. **Economic screen after statistical:** an edge that clears t ≥ 2 but returns < costs at achievable
   size (likely for `c_index`, plausibly for (a) if the ladder is thin) is logged as "real but not
   worth capital," not promoted.

**Forward ledger file (proposed):** `perp_forward_log.jsonl`, one record per `(edge, asset, day)`
with `n_trades`, per-day P&L, and the running pooled/per-asset clustered t — the perp analogue of
`favlong_forward_log.jsonl`. Build the scorer (`perp_forward.py`) once ~10 forward days exist; until
then this collector just accrues the raw streams.
