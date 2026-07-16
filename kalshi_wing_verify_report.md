# Independent Verification — Kalshi KXBTCD Hourly BTC Wing Overpricing / VRP

**Author:** independent repro (own code, `kalshi_wing_verify.py`). Did **not** read or import
`kalshi_wing_vrp.py`. Data: Kalshi public API, pulled fresh 2026-07-16.

## Claim under test
On the hourly BTC ladder (KXBTCD, "BTC greater than X"), deep-OTM WING strikes are
systematically **overpriced** (favorite-longshot / variance risk premium); **selling YES** on
wings is **+1.3–1.6c/contract net of fees at VWAP entry** (day-clustered t≈1.8–4), but
**collapses to ~0 (t≈0.39) once a 1c half-spread is charged**.

## Method (my own, adversarial)
- Pulled **1,400 settled hourly events** (2026-05-17 → 2026-07-16), all markets per event,
  and **first-half trades** for every market with volume>0 (43,942 markets).
- Trades are newest-first, so I fetched them with an explicit **time window `[open, open+life/2]`**
  to grab the *early* (first-half) trades directly. This is unbiased: wings are low-volume and
  fully captured in one window page, and wings are defined by **early price only** (never by
  outcome), so no survivorship on winners/losers.
- Wing = early YES price in (0, 0.15]; filter ≥2 first-half trades. **34,260** markets qualify;
  **11,711** are wings (VWAP def). **61 distinct close-dates** — far above the ≥40 / ≥1,500 targets.
- Three independent entry-price defs: **(a) count-weighted VWAP** over first half; **(b) single
  trade nearest 1/3-life**; **(c) median** first-half trade price.
- Seller-of-YES PnL held to settlement = `entry − result − fee`. Fee = Kalshi taker fee
  `ceil(0.07·P·(1−P))` cents (per-1-contract = **worst case**; large orders pay ≈half).
- **Day-clustered t** everywhere (cluster-robust SE, cluster = close date, 61 clusters).

## (1) Calibration across the three entry definitions
`edge_buy = realized − entry` (negative ⇒ YES overpriced ⇒ selling gross-profits).
`sellNet¢ = (entry − result) − fee`, worst-case fee.

| bin | VWAP realiz/entry | VWAP sellNet¢ (t) | MEDIAN sellNet¢ (t) | NEAR sellNet¢ (t) |
|---|---|---|---|---|
| ≤.02 | .002/.013 | +0.05 (0.50) | +0.02 (0.22) | **−0.33 (−2.21)** |
| .02–.04 | .009/.028 | +0.90 (3.63) | +0.98 (3.17) | −0.46 (−0.93) |
| .04–.06 | .010/.049 | +2.92 (9.65) | +2.24 (4.38) | −1.02 (−1.14) |
| .06–.10 | .035/.078 | +3.31 (5.47) | +3.40 (5.89) | +0.33 (0.42) |
| .10–.15 | .061/.123 | +5.25 (6.13) | +5.05 (5.81) | +0.30 (0.27) |
| **ALL≤.15** | **.014/.039** | **+1.44 (6.73)** | **+1.17 (5.49)** | **−0.31 (−1.27)** |

- **Realized YES rate is far below entry in every bin** (e.g. .10–.15 wings priced 12.3c settle
  YES only 6.1% of the time). Overpricing is monotone and large.
- **Replicates cleanly under VWAP and MEDIAN** (both distributional first-half measures):
  +1.2–1.4c aggregate, t≈5.5–6.7.
- **Does NOT replicate under the single "nearest-1/3-life" trade** (aggregate −0.31c, t=−1.27).
  A single trade at these quantized low prices (0.01/0.02 ticks) is too noisy and sits nearer
  mid; it does not confirm the effect. **Caveat: the edge is a property of the first-half price
  distribution, not of any single print.** Two of three defs agree; the disagreeing one is the
  noisiest estimator.

## (2) Executable sell price — the crux
- **72.0%** of early wing *volume* is aggressive **BUYERS** lifting the offer ⇒ VWAP ≈ **ask**,
  so selling "at VWAP" is optimistic.
- **74.3%** of wings had a **real taker-SELL** (someone actually sold YES) in the first half —
  an *observed executable bid*, not a model.
- **Measured within-market half-spreads are small: 0.22–0.52c** across bins — **well under the
  1c the prior claim charged.**

Seller net PnL (cents/contract, worst-case fee), four sell-price assumptions:

| bin | A: @VWAP (t) | **B: @real bid (t)** | C: VWAP−halfspr (t) | D: VWAP−1c (t) |
|---|---|---|---|---|
| ≤.02 | +0.05 (0.50) | −0.09 (−0.60) | −0.16 (−1.55) | −0.95 (−8.98) |
| .02–.04 | +0.90 (3.63) | +0.22 (0.75) | +0.43 (1.74) | −0.10 (−0.40) |
| .04–.06 | +2.92 (9.65) | +2.20 (6.69) | +2.40 (7.93) | +1.92 (6.35) |
| .06–.10 | +3.31 (5.47) | +2.46 (3.90) | +2.90 (4.78) | +2.31 (3.82) |
| .10–.15 | +5.25 (6.13) | +4.54 (5.33) | +4.93 (5.76) | +4.25 (4.96) |
| **ALL≤.15** | **+1.44 (6.73)** | **+1.27 (4.76)** | **+1.03 (4.80)** | **+0.44 (2.05)** |

**The edge SURVIVES at a realistic taker sell price.** At the *actual observed bid* (def B) the
aggregate is **+1.27c, t=4.76**; VWAP−modeled-halfspread (def C) **+1.03c, t=4.80** — two
independent executable-price estimates, both strongly positive. Even the harsh flat-1c haircut
(def D) gives **+0.44c, t=2.05** — a reduction, **not** the claimed collapse to t≈0.39.
The prior "collapse" is an artifact of charging a 1c half-spread when true wing half-spreads are
~0.3–0.5c. **The edge is concentrated in the .04–.15 bins** (real-bid +2.2 to +4.5c, t 4–7);
the **≤.02 bin is genuinely dead** at a taker bid.

**Fee sensitivity:** under realistic large-order (continuous) fees the aggregate is even larger —
sell@VWAP +2.19c t=10.3, sell@real-bid +2.01c t=7.5 — and even the ≤.02 bin flips positive
(+0.82c, t=5.4). The ≤.02 null above is purely the 1c fee-rounding on single contracts.

## (3) Selection / tradeability
- **Wings are NOT illiquid.** First-half volume percentiles: p10=100, **p50≈3,500**, p90≈58,000,
  max 1.4M contracts. Only 9% of wings traded <100 contracts.
- **Edge is present in every volume tertile and is *larger* in more liquid wings**
  (real-bid: low +0.65c t=7.2 · mid +1.39c t=13.4 · high +1.44c t=2.4). It is **not**
  concentrated in untradeable illiquid wings — the opposite of the selection-artifact worry.

## (4) Robustness
- 61 clusters; no headline result rests on <10 dates.
- Temporal split: first-half dates (30) real-bid **+1.58c t=4.75**; second-half dates (31)
  **+0.94c t=2.26**. Positive and significant in both — some decay, no collapse.

## VERDICT
**(i) Is the wing overpricing real and robust across entry definitions?**
**Yes — real and large**, and it **replicates under VWAP and MEDIAN** (realized YES rate far below
entry; +1.2–1.4c, t≈5.5–6.7, monotone across bins, 61 dates). **Caveat:** it does **not** show up
under a single nearest-1/3-life print (noisy null), so the effect lives in the first-half price
*distribution*, not any single trade.

**(ii) Does a tradeable edge survive at a realistic SELLABLE price for a TAKER?**
**Yes — contrary to the prior claim.** At the actual observed bid, selling YES on wings nets
**+1.27c/contract (t=4.76)**; VWAP−modeled-spread **+1.03c (t=4.80)**. Concentrated in the
**0.04–0.15** wings (+2.2 to +4.5c). The prior "collapse to t≈0.39 under a 1c half-spread" is a
**mis-calibrated haircut** — measured wing half-spreads are 0.3–0.5c, and even a flat 1c leaves
+0.44c (t=2.05). The ≤0.02 bin is the only genuinely dead zone for a taker.

**(iii) Is the residual hope purely a MAKER (resting-offer) play?**
**No.** The edge is already positive and significant for a **taker** hitting real bids. A maker
would capture the spread on top and do better, but the claim that only a maker play survives is
**not supported** by this independent data.

### Bottom line
The favorite-longshot / VRP overpricing on KXBTCD wings **is not an artifact** — it replicates on
fresh data across two of three entry definitions, survives realistic taker execution, is
fee-robust, holds out-of-sample in time, and is present in liquid (not just illiquid) wings.
The prior study **understated** the edge by charging a 1c half-spread that is ~2–3× the true wing
spread. Net harvestable taker edge ≈ **+1 to +2c/contract**, concentrated in the 4c–15c wings.
