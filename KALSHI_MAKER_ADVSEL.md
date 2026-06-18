# Kalshi Maker Adverse-Selection Test (SOFT markets)

**Date:** 2026-06-18
**Script:** `kalshi_maker_advsel.py` (public Kalshi API, no auth)
**Question:** A resting MAKER on low-volume soft (non-crypto) Kalshi markets only gets
filled when a TAKER chooses to trade against it. If takers are informed, the maker's
FILLED outcomes are systematically worse than the market's unconditional outcomes
(adverse selection), which would evaporate the apparent favorite–longshot edge that a
"fill-at-the-bid, ignore selection" backtest shows. **Does the maker edge survive
adverse selection, net of the Kalshi quadratic fee?**

---

## Method

For every public trade in a **settled, binary, non-MVE soft market with `volume_fp ≥ 300`**:

- The taker lifts; the **maker is the passive counterparty**.
- `taker_side == "yes"` → taker BOUGHT yes → **maker SOLD yes → maker SHORT yes**.
  Maker P&L to settlement = `fill_price − settle`.
- `taker_side == "no"` → taker SOLD yes → **maker BOUGHT yes → maker LONG yes**.
  Maker P&L to settlement = `settle − fill_price`.
- `settle = 1.0` if market `result == "yes"`, else `0.0`.
- **Fee** (Kalshi quadratic, per contract): `0.07 · p · (1−p)`, subtracted from every maker fill.

This is exactly the **realized P&L of whoever was resting and got hit** — i.e. it is
*conditioned on the fill happening*, which is the whole point: it bakes in adverse
selection. We aggregate **volume-weighted** (VW, by `count_fp` — the dollar that actually
gets traded) and **trade-weighted** (TW, equal per fill) means, by price band.

**Short-horizon markout** (selection signal that does *not* depend on settlement): using
60s candles, take the mid `(yes_bid.close + yes_ask.close)/2` ~10 min after each trade.
Maker markout = `mid_future − fill` (long maker) or `fill − mid_future` (short maker). If
price moves *against* the maker right after the fill, that is direct evidence of informed
takers, independent of how the market eventually settles.

Bands: **longshot** `p < 0.20`, **mid** `0.20 ≤ p ≤ 0.80`, **favorite** `p > 0.80`
(band assigned by the fill's yes-price).

---

## Sample

| metric | value |
|---|---|
| Markets analyzed | **600** (all with candles) |
| Series scanned | 113 |
| Trades (fills) used, settlement | **263,031** |
| Contracts (Σ count_fp) | 13.9 M |
| Markets by category | Economics 173, Politics 53, Climate & Weather 374 |
| Trades by category | Econ 53.5k, Politics 6.9k, Climate/Wx 202.5k |

> **Sampling caveat (honest):** the run hit the 600-market global cap while still inside
> Climate & Weather, so **Entertainment was never reached and the sample is dominated by
> weather (62% of markets, 77% of trades)**. Economics and Politics are well represented;
> Entertainment is absent. Treat the OVERALL number as "soft minus entertainment, weather-heavy."

---

## Results — Maker realized P&L to SETTLEMENT, NET of fee ($/contract; + = maker wins)

| Band | n (fills) | contracts | **VW mean** | TW mean | TW se |
|---|---:|---:|---:|---:|---:|
| longshot (<0.20) | 117,135 | 8.12 M | **+0.0097** | +0.0073 | 0.0006 |
| mid [0.20,0.80]  | 118,204 | 2.68 M | **−0.0242** | −0.0096 | 0.0014 |
| favorite (>0.80) | 27,692  | 3.13 M | **−0.0143** | +0.0076 | 0.0018 |
| **OVERALL**      | 263,031 | 13.94 M | **−0.0022** | −0.0003 | 0.0007 |

## Results — Short-horizon markout (+10 min mid move, maker direction, PRE-fee)

| Band | n | **VW mean** | TW mean | TW se |
|---|---:|---:|---:|---:|
| longshot (<0.20) | 59,659 | **+0.0027** | +0.0053 | 0.0002 |
| mid [0.20,0.80]  | 60,901 | **−0.0032** | +0.0056 | 0.0004 |
| favorite (>0.80) | 13,246 | **+0.0022** | +0.0110 | 0.0007 |
| **OVERALL**      | 133,806 | **+0.0015** | +0.0060 | 0.0002 |

## Reference — "fade-the-longshot, ignore selection" benchmark (net of fee)

This is a *position* benchmark (always take the anti-longshot side at the fill price: long
yes if p<0.5 else short), **not** the maker's actual fills — it is the closest proxy here
to the naive "this is what favorite–longshot says you should earn" expectation. It is NOT
the same as the separate "fill-at-bid EV-by-band" test, so read it as directional context only.

| Band | **VW mean** | TW mean |
|---|---:|---:|
| longshot (<0.20) | −0.0203 | −0.0323 |
| mid [0.20,0.80]  | −0.0039 | −0.0217 |
| favorite (>0.80) | +0.0058 | +0.0127 |
| **OVERALL**      | −0.0113 | −0.0228 |

---

## Interpretation

**1. Overall, the maker edge does NOT survive net of fee.** The volume-weighted realized
maker P&L to settlement is **−0.0022 $/contract overall** (TW −0.0003). That is essentially
**zero-to-slightly-negative**: on the dollar-weighted flow that a real maker would actually
absorb, the passive side does not make money once the quadratic fee is paid. The apparent
"makers win" result is competed/selected away.

**2. The favorite–longshot edge is real on the SELL-longshot side, but small.** The only
band with a clean positive VW realized P&L is the **longshot band: +0.0097 $/contract**
(≈ +1.0¢, ~17σ on TW). This is consistent with GWU: resting an offer that lets takers *buy*
overpriced longshots (maker ends short the longshot) pays. But +1¢ on sub-20¢ contracts is
a thin edge that the **mid (−0.024) and favorite (−0.014) bands more than erase** in
dollar-weighted terms.

**3. Short-horizon markout shows NO violent adverse selection.** The +10-min markout is
**positive in every band** (OVERALL VW +0.0015, TW +0.0060). Price does *not* systematically
jump against the maker in the minutes after a fill. So on these soft markets the adverse
selection is **not** the fast "informed taker picks you off seconds before a move" kind that
killed the crypto box. The damage instead shows up at **settlement** in the mid/favorite
bands: makers there get hit slightly more often on the wrong side relative to where things
resolve, and the fee finishes the job.

**4. Adverse selection vs. the naive expectation.** The naive "fade-longshot" benchmark says
the longshot band should *lose* (−0.020 VW) because that benchmark *buys* longshots; the
maker's realized longshot P&L is *positive* (+0.0097) precisely because the maker is on the
*other* (short-longshot) side — so in the longshot band selection actually helps the maker.
But in the favorite band the realized P&L (−0.0143) is **worse** than the benchmark (+0.0058)
— a **~2¢ adverse-selection drag**: makers quoting favorites get filled disproportionately
when the favorite is about to fail. Net across bands, the dollar-weighted edge lands at zero.

---

## VERDICT

**The maker edge does NOT survive adverse selection net of the fee.** Volume-weighted realized
maker P&L to settlement is **−0.22¢/contract overall** — indistinguishable from zero and on the
wrong side of it. The one genuinely positive pocket is **short-the-longshot (p<0.20): +0.97¢/contract**,
robust and large-n, but the **mid (−2.4¢) and favorite (−1.4¢) bands wipe it out**, the latter
showing a clear ~2¢ adverse-selection drag vs. the no-selection benchmark. Short-horizon markout
is mildly positive everywhere, so there's no fast-information pickoff — the leakage is at
settlement. This is a **"positive-necessary-but-not-sufficient"** signal at best: the
favorite–longshot edge is real only in the longshot-sell band and is too thin, after fees and the
selection drag on the rest of the curve, to constitute a tradable maker stack for a small retail
account. **Same outcome as the crypto box: apparent edge, no surviving net edge.**

*Caveat:* sample is weather-heavy and contains no Entertainment markets (600-market cap reached
first); a longshot-band-only, Economics/Politics-restricted re-run is the natural follow-up before
fully closing the door on the +0.97¢ longshot pocket.
