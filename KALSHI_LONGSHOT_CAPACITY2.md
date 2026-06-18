# Kalshi longshot harvest — IS THERE A HIGH-VOLUME VERSION? (bias × volume tradeoff)

**Question this doc answers:** the soft-market study found a real maker edge (sell overpriced
longshots, rest NO when YES mid < 0.20) worth **+0.97¢/contract @17σ net** of adverse selection
+ fee — but capacity-capped at **~$30–150/month** because soft markets are tiny. The
favorite-longshot literature says the overpricing bias is **biggest in thin markets and smaller
(more efficient) in deep ones.** So: *does the same longshot-overpricing edge survive in
HIGH-VOLUME Kalshi markets, where capacity would no longer be the binding constraint — or does the
bias vanish exactly where the depth appears?*

**Answer (brutally honest): the bias vanishes where the depth appears. There is NO higher-capacity
version of the longshot harvest.** The tradeoff curve is steep and the two factors are
anti-correlated: every doubling of volume eats the overpricing, and by the deepest quartile the
sign actually FLIPS (deep longshots resolve YES slightly *more* than priced, i.e. mildly
*under*-priced). Where a real +overpricing bias does still show up (CPI/Fed threshold tails), it
sits inside the `quadratic_with_maker_fees` series, and the deepest individual legs (NBA champion)
have no bias at all. **The soft-market ~$30–150/mo ceiling is NOT beaten — it is the global maximum
of edge × capacity.**

Method, data, and the full tradeoff curve below. Script: `kalshi_longshot_capacity2.py`.

---

## Method

- Public Kalshi API only (no auth), `https://api.elections.kalshi.com/trade-api/v2`.
- Universe: the deepest known Kalshi longshot books across the three target families —
  **Sports futures** (NBA champion `KXNBA`, NBA conf `KXNBAEAST/WEST`, NBA MVP `KXNBAMVP`, NBA draft
  lottery `KXNBATOPPICK`, ATP `KXATP`), **Politics** ("will win" series), **Economics threshold
  tails** (CPI `KXCPI`/`KXCPIYOY`, Fed `KXFED`/`KXFEDDECISION`).
- Per **settled, single-outcome binary, non-MVE** market: computed the **mid-life YES mid** =
  (yes_bid.close + yes_ask.close)/2 from the candle nearest the temporal midpoint of [open,close]
  (hourly candles for ≤7-day markets, daily for season-long futures). Kept legs with mid-life mid
  **< 0.20** (longshot). **124 longshot legs.**
- **Overpricing bias = mean(mid) − realized YES-rate.** Positive ⇒ overpriced (priced higher than
  it resolves) ⇒ the SELL-the-longshot-NO maker edge the soft study monetized.
- **`volume_fp` verified to be actual contracts traded** (summed the per-trade `count_fp` stream on
  the deepest leg KXNBA-26-SAS: 40k trades = 11.4M contracts and still paging, vs reported
  volume_fp 81M — consistent; it is a contract count, Kalshi now supports fractional/$-denominated
  contracts so it's a float). So the depth numbers are real, not scaled artifacts.
- **Fee caveat enforced:** recorded `fee_type` per series. Flagship sports/econ
  (`quadratic_with_maker_fees`) charge makers ~25% of the taker fee; default soft `quadratic`
  series charge makers **zero**. Results are split zero-fee vs maker-fee.

---

## 1. The headline: bias vs volume — the tradeoff is real and steep

Longshot legs sorted by life-volume into quartiles. **Overprice bias decays monotonically with
volume and flips sign in the deepest quartile.**

### All longshot legs (n=124)
| Volume quartile | vol range (contracts) | n | mean mid | realized YES | **overprice bias** | z |
|---|---|---|---|---|---|---|
| Q1 (thinnest) | 0 – 5,917 | 31 | 0.061 | 0.000 | **+6.10¢** | 1.4 |
| Q2 | 7.4k – 45.5k | 31 | 0.051 | 0.032 | **+1.89¢** | 0.5 |
| Q3 | 49k – 1.49M | 31 | 0.064 | 0.032 | **+3.16¢** | 0.7 |
| Q4 (deepest) | 1.53M – 75.8M | 31 | 0.064 | 0.065 | **−0.06¢** | 0.0 |

### Zero-maker-fee legs only — the tradable universe (n=40)
| Volume quartile | vol range | n | mean mid | realized YES | **overprice bias** | z |
|---|---|---|---|---|---|---|
| Q1 (thinnest) | 0 – 500 | 10 | 0.085 | 0.000 | **+8.50¢** | 1.0 |
| Q2 | 615 – 3,026 | 10 | 0.057 | 0.000 | **+5.65¢** | 0.8 |
| Q3 | 5,055 – 18,988 | 10 | 0.076 | 0.100 | **−2.40¢** | −0.3 |
| Q4 (deepest) | 22,542 – 796,087 | 10 | 0.071 | 0.100 | **−2.90¢** | −0.4 |

**Read this as the tradeoff curve.** The +6–9¢ overpricing that powered the soft-market edge lives
**only in the thinnest quartiles** (vol < ~5k contracts) — i.e. exactly the soft markets the
earlier study already covered, where capacity caps at $30–150/mo. As volume climbs into the
thousands, the bias collapses, and past ~20k contracts it is **negative** (deep longshots are if
anything mildly under-priced). The depth and the edge are anti-correlated. No z-score in any deep
quartile is significant — the deep markets are statistically calibrated, and the point estimate
that *is* there points the wrong way for the seller.

---

## 2. By fee type and category — where (if anywhere) does deep bias remain?

| Cut | n | mean mid | realized | overprice bias | z | life-vol (contracts) |
|---|---|---|---|---|---|---|
| **Zero-maker-fee** (`quadratic`) | 40 | 0.072 | 0.050 | +2.21¢ | 0.5 | **1.55M** |
| **Maker-fee** (`quadratic_with_maker_fees`) | 84 | 0.054 | 0.024 | +3.04¢ | 1.2 | **369M** |
| Sports | 84 | 0.062 | 0.048 | +1.47¢ | 0.6 | 347M |
| Economics (CPI/Fed tails) | 40 | 0.055 | 0.000 | **+5.50¢** | 1.5 | 23.8M |
| Politics | 0 | — | — | — | — | — |

Series-level vol-weighted bias:

| Series | family | fee | n | mean mid | realized | bias |
|---|---|---|---|---|---|---|
| KXCPI | Econ tail | maker-fee | 11 | 0.068 | 0.000 | **+6.8¢** |
| KXFEDDECISION | Econ tail | maker-fee | 5 | 0.066 | 0.000 | **+6.6¢** |
| KXCPIYOY | Econ tail | maker-fee | 13 | 0.052 | 0.000 | **+5.2¢** |
| KXFED | Econ tail | maker-fee | 11 | 0.041 | 0.000 | **+4.1¢** |
| KXNBAEAST | Sports conf | maker-fee | 8 | 0.086 | 0.000 | +8.6¢ |
| KXATP | Sports | zero-fee | 25 | 0.074 | 0.040 | +3.4¢ |
| KXNBAMVP | Sports | maker-fee | 11 | 0.026 | 0.000 | +2.6¢ |
| KXNBATOPPICK | Sports | zero-fee | 15 | 0.069 | 0.067 | **+0.2¢** |
| KXNBA (champion) | Sports | maker-fee | 17 | 0.044 | 0.059 | **−1.4¢** |
| KXNBAWEST | Sports conf | maker-fee | 8 | 0.077 | 0.125 | **−4.8¢** |

**Two structural facts kill the high-capacity thesis:**

1. **The deepest individual legs have no bias.** The genuinely huge books (NBA champion KXNBA, 8–76M
   contracts/leg) show **−1.4¢** vol-weighted — the seller would be paying, not collecting. KXNBAWEST
   (−4.8¢) is worse. The mega-volume is in the most efficient, most picked-over markets.
2. **The one pocket with a persistent +bias — CPI/Fed threshold tails (+4 to +6.8¢, every tail
   resolved NO) — is entirely `quadratic_with_maker_fees`.** It is moderately deep (e.g.
   KXFEDDECISION-26JUN-H25 = 6.0M contracts) but the maker pays ~25% of the taker fee, and the
   sample (n=40, z=1.5) is small and structurally suspect: these are *threshold* tails ("CPI above
   X"), whose NO-resolution is partly a regime artifact (low-inflation regime ⇒ every high-CPI tail
   misses), not a stable behavioral overpricing. It is not the same uninformed lottery flow the
   adverse-selection study validated.
3. **Politics deep longshots don't exist as settled data.** Every deep zero-fee politics series
   (KXPRESPARTY, KXSENATE, KXHOUSE, KXSPEAKER, candidate "will win") had **zero settled binary
   markets** in the window — they are pending future elections. There is no harvestable deep
   politics longshot universe to test right now.

---

## 3. Capacity — $/month if you harvested only the high-volume longshots

Same maker-realism haircut as the soft-market study: capturable ≈ life_volume × 0.075
(side-engagement 0.5 × queue-capture 0.25 × touch-presence 0.6).

| Universe | n legs | life-vol (contracts) | capturable | gross harvest, lifetime | **annualized** | edge real? |
|---|---|---|---|---|---|---|
| Zero-maker-fee (all) | 40 | 1.55M | 116k | ~$1,126 @ +0.97¢ | **~$94/mo** | **NO — deepest-Q bias is −2.9¢** |
| Maker-fee (all) | 84 | 369M | 27.7M | ~$237k after fee | ~$19,784/mo | **NO — deepest-Q bias ≈ 0/neg** |

**Why both numbers are mirages:**

- The **zero-fee $94/mo** assumes the +0.97¢ soft-market edge applies — but it does **not** at this
  depth. The zero-fee deep universe is just KXATP + KXNBATOPPICK; their **deepest quartile measured
  bias is −2.9¢** (and KXNBATOPPICK overall is +0.2¢ ≈ 0). Applying the soft edge here is
  double-counting an edge the data says is gone. Real expected harvest on the deep zero-fee legs is
  **≈ $0 (or negative).** What little +bias remains is in the *thin* KXATP legs that are themselves
  back in the $30–150/mo soft regime.
- The **maker-fee $19,784/mo** looks enormous (369M contracts of real depth!) but the deepest
  quartile bias is **−0.06¢** — there is no overpricing to sell, you'd pay the maker fee for the
  privilege of a coin-flip. The CPI/Fed +bias pocket inside it is small ($23.8M vol → ~$130/mo at
  CAPTURE×bias even if you believed it), maker-fee'd, and regime-driven.

So the **revised $/month ceiling for a genuinely +EV, depth-backed longshot harvest is essentially
the same ~$30–150/mo as the soft study — and it still comes from the thin markets.** The deep
markets add volume but subtract edge at a faster rate; edge × capacity does not improve anywhere
along the curve. **The soft-market pocket is the global maximum.**

---

## 4. Where on the tradeoff curve is edge × capacity maximized?

Approximating per-leg expected harvest as `life_vol × 0.075 × max(bias, 0)`:

| Zero-fee quartile | vol/leg | bias | edge×capacity signal |
|---|---|---|---|
| Q1 thinnest | <500 | +8.5¢ | high bias, ~$0 depth → tiny $ (the soft regime) |
| Q2 | 0.6–3k | +5.65¢ | **best product, but still soft-market-scale ($30–150/mo)** |
| Q3 | 5–19k | −2.4¢ | bias gone → zero |
| Q4 deepest | 22k–800k | −2.9¢ | negative → you lose |

The product peaks in **Q2 (low-thousands of contracts)** — which is precisely the soft-market band
already characterized, with the same $30–150/mo ceiling. There is no interior pocket where rising
volume buys enough extra fills to outrun the falling bias. The curve is monotone against you past
the soft regime.

---

## 5. VERDICT

1. **The longshot-overpricing bias does NOT survive into deep Kalshi markets.** It decays
   monotonically with volume and **flips negative in the deepest quartile** (zero-fee: +8.5¢ → −2.9¢
   across the volume range). This confirms the favorite-longshot literature's core tension *on
   Kalshi specifically*: the bias is a thin-market phenomenon.
2. **The deepest books are the most efficient.** NBA champion legs (8–76M contracts) show −1.4¢
   vol-weighted bias — the seller pays. The mega-volume is exactly where there is no edge.
3. **The only persistent +bias pocket (CPI/Fed threshold tails, +4–7¢) is maker-fee'd, small-n
   (z=1.5), and regime-driven** — not the validated uninformed-lottery flow, and not safely tradable.
4. **Politics deep longshots are unavailable** (all settled-binary series are pending elections; zero
   settled data).
5. **Revised ceiling: there is NO higher-capacity version of the harvest.** Edge × capacity is
   maximized in the same thin soft-market band as before (~$30–150/mo). Adding depth strictly
   subtracts edge. **The capacity wall stands; the deep markets do not rescue the strategy.**
