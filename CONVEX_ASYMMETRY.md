# CONVEX_ASYMMETRY.md — The best data-informed CONVEX, +EV, positive-skew high-upside sleeve, and its optimal BARBELL

**For:** a high-risk-tolerant US small-bankroll investor who will take risk **only** where the payoff is
disproportionately positive — large right tail, **capped** left tail, asymmetric upside — and only if it is **+EV**.
Not symmetric leverage. Not negative-EV lottery bets.

**Engine:** `convex_asymmetry.py` (this commit), which **reuses the committed engines**
`btc_trend_timing.py` (`sma_signal` / `backtest` / `perf`), the `trend_following` / `allweather_live` trend-gate
idea (the safe base is the trend-overlaid all-weather), and `final_portfolio.py`'s crypto-sleeve shape.

**Window:** yfinance daily closes. BTC 2014-09 → 2026-06 (full), ETH 2017-11→, SOL 2020-04→, equities 2014-01→.
**Costs:** crypto spot **20 bps/side** (40 bps round-trip) charged on every trend switch (matches `btc_trend_timing`);
LETF modelled with explicit **financing 6%/yr × (lev−1) + 0.95%/yr expense + daily path-decay**; cost scales with
levered notional. Safe-base turnover 3 bps/side. Monte-Carlo uses stationary block bootstrap (block≈20d) with a
right-tail **haircut** and crypto **gap risk** switched on. **PAPER ONLY** — you place trades manually.

---

## 1. How convexity / "disproportionate positive" is measured

A sleeve scores only if it is **both** positive-skew **and** +EV **and** left-tail-capped. The battery:

- **Skew** (monthly returns) — must be **> 0** (right tail fatter than left).
- **Tail ratio** = p95 monthly return / |p5 monthly return| — must be **> 1** (upside bigger than downside).
- **Omega(0)** = E[gains] / E[losses] — > 1 means asymmetric payoff.
- **CAGR / mean** — the **+EV gate**: must beat cash (~2%). *Non-negotiable.*
- **maxDD** — the **left-tail cap**: a drawdown worse than **−85%** = the left tail is **not capped**
  (the historical +EV was luck conditional on not having gapped to zero) → **REJECT**.
- **Monte-Carlo P(2x) / P(5x) / P(<half)** over 1/3/5yr — the realized asymmetry.

**dispro_score** rewards skew, (tail_ratio−1), (omega−1) and CAGR, divided by (1+|maxDD|).
It returns **NaN (REJECT)** unless **+EV AND maxDD > −85%**. This is what enforces the brutal bar.

---

## 2. Asymmetry-metric ranking — candidates (full history, net of cost)

| Rank | Sleeve | CAGR | Sharpe | maxDD | skew(M) | tailR | Omega | dispro | verdict |
|---|---|---|---|---|---|---|---|---|---|
| **1** | **(b) Crypto basket trend-timed (BTC+ETH+SOL, each 200d-SMA-gated)** | **74.7%** | 1.34 | **−58.0%** | **1.45** | **2.83** | **3.20** | **4.99** | **+EV ✓ left-tail capped ✓ — WINNER** |
| 2 | (a) BTC trend-timed SMA200 (the base convex engine) | 60.1% | 1.17 | −68.5% | 1.36 | 2.60 | 2.90 | 4.07 | +EV ✓ capped ✓ |
| — | (c) BTC **2x** trend-gated | 86.9% | 1.12 | **−93.4%** | 1.81 | 2.95 | 2.79 | **REJECT** | left tail **uncapped** |
| — | (c) BTC **3x** trend-gated | 64.4% | 1.11 | **−99.4%** | 2.26 | 3.09 | 2.80 | **REJECT** | left tail **uncapped** (gap-to-ruin) |
| 5 | (d) Cross-asset TF / managed-futures (SPY/TLT/GLD TS-trend) | 5.9% | 0.86 | −10.5% | 0.04 | 1.56 | 2.09 | 1.88 | +EV ✓ but ~zero skew, low upside |

**Key finding on leverage:** the trend gate amplifies the *right* tail of 2x/3x (skew 1.8–2.3, CAGR up to 87%),
but it does **NOT** cap their *left* tail — daily 2x/3x compounding through a fast crypto drawdown takes the equity
to −93% / −99% even *with* the trend filter, because the gate reacts on a weekly cadence while crypto can drop 30–50%
inside the gate's lag. So **levered trend-timed crypto FAILS the brutal bar**: it is convexity amplification with an
**uncapped** left tail. The clean way to get more right-tail exposure is **diversifying the entries (the basket)**,
not levering — the basket has a *shallower* maxDD (−58%) than even 1x BTC (−68%) while scoring *higher* on skew,
tail ratio and omega. Convex diversification beats convex leverage here.

### Failed contrasts (prove the filter works)

| Contrast | CAGR | skew(M) | maxDD | verdict |
|---|---|---|---|---|
| X1 BTC **buy-hold** (no trend) | 52.5% | 0.62 | −83.4% | +EV but **half the skew** of trend-timed (0.62 vs 1.36) and −83% DD — the trend gate is what *creates* the convexity |
| X2 **naive 3x BTC LETF** buy-hold | **−49.4%** | 1.49 | −100% | **REJECT: negative EV** (decay/financing eat it) + ruin |
| X3 30%-OTM **monthly call buying** | **−100%** | 4.24 | −100% | **REJECT: negative EV** — beautiful skew (4.24!) but premium bleed → −EV (the classic lottery trap) |
| X4 **SOL buy-hold** (lotto alt) | 100.5% | 1.96 | **−96.3%** | **REJECT: left tail uncapped** — high skew AND high CAGR *in-sample*, but −96% DD = you can be wiped before the upside |

This is the whole thesis in one table: the highest-skew things (OTM calls 4.24, SOL 1.96) are exactly the ones that
**fail** — on −EV or on an uncapped left tail. The rare survivor is **trend-following on volatile assets**: the trend
exit *cuts the left tail* (turning buy-hold's 0.62 skew into 1.45 and its −83% DD into −58%) **while staying +EV**.

### Recent-regime check (2022-01+) — is the convexity just a 2017/2021 artifact?

| Sleeve 2022+ | CAGR | Sharpe | maxDD | skew(M) | tailR |
|---|---|---|---|---|---|
| (a) BTC trend-timed | 24.4% | 0.81 | −35.7% | 1.46 | 1.66 |
| (c) BTC 2x trend-gated | 31.9% | 0.74 | −64.1% | 1.91 | 1.66 |
| X1 BTC buy-hold | 7.2% | 0.39 | −66.7% | 0.48 | 1.80 |

**Honest answer: partly, but it survives.** Through the harsh 2022–24 bear, trend-timed BTC still earned 24%/yr at
−36% DD with skew **1.46** vs buy-hold's 7%/yr at −67% DD with skew 0.48. The convexity is **dampened** out-of-sample
(tail ratio 1.66 vs 2.8 full-sample, Sharpe 0.81 vs 1.17) but **not a pure 2017/2021 artifact** — the left-tail
cut (−36% vs −67%) is the durable, repeatable part. The *magnitude* of past 10x runs is the fragile part; haircut it.

---

## 3. The BARBELL — safe base + convex sleeve (weight sweep)

**Safe base** = trend-overlaid all-weather (SPY/TLT/GLD/BIL @ 25%, each risk sleeve held only if its trailing-12m
trend > 0 else → BIL; the `allweather_live` conservative shape). Standalone: CAGR ~3.9%, Sharpe 0.72, **maxDD −10.6%**
on this 2014+ window (its full-history Sharpe in the repo's longer sample is ~1.1–1.4; here the low-rate 2014-21 era
drags the CAGR). It is the bounded, low-DD floor.

**Convex sleeve** = the WINNER, crypto basket trend-timed. Daily-rebalanced blend (continuously reset to target → the
convex slice stays bounded; "you can only lose the convex slice" each rebalance).

| w_convex | CAGR | maxDD | skew(M) | Sharpe | tailR | median yrs→$70k* | P(reach ≤5yr)* |
|---|---|---|---|---|---|---|---|
| 0% | 4.1% | −10.6% | 0.02 | 0.74 | 1.40 | 8.7 | 0% |
| 5% | 6.3% | −11.4% | 0.09 | 1.02 | 1.53 | 7.9 | 0% |
| 10% | 8.4% | −14.4% | 0.27 | 1.14 | 1.55 | 7.3 | 0% |
| **20%** | **12.6%** | **−20.7%** | **0.68** | **1.15** | **1.95** | **6.4** | **5%** |
| 30% | 16.7% | −26.7% | 0.94 | 1.11 | 2.05 | 5.7 | 23% |
| 50% | 24.6% | −37.7% | 1.23 | 1.05 | 2.06 | 4.7 | 59% |

\* $5k start + $500/mo contributions, block-bootstrap MC. P(<half) at 3yr was **0.00** at every weight — the safe
base + monthly inflows make total ruin of the *blend* effectively nil; only the convex slice is ever at risk.

**Reading the sweep:** Sharpe **peaks at 10–20%** (1.14–1.15) then declines — that is the barbell sweet spot where the
convex sleeve is a *diversifying return engine*, not a risk hog. Skew climbs monotonically with weight (0.02 → 1.23):
more convex weight buys more right-tail asymmetry, paid for in deeper DD (−10% → −38%). For a **high-risk** investor
who wants max right tail with bounded ruin, the honest band is **20–30%**:

- **20%** keeps maxDD ~**−21%** (shallower than holding SPY), Sharpe at its plateau peak, and still injects real skew (0.68).
- **30%** pushes CAGR to ~17%, skew to ~0.94, P(reach $70k in ≤5yr) to 23%, at maxDD ~**−27%**.

**Recommended: 20% convex / 80% safe base** as the default; **30%** for the most aggressive who can stomach −27%.
Above 30% the Sharpe rolls off and DD deepens faster than skew improves — diminishing convexity per unit of pain.

---

## 4. Honest payoff distribution — the recommended 20% barbell, from $5k

All numbers MC with **right-tail haircut ON** (crypto drift haircut ≈ 12%/yr on the convex slice) and **gap risk ON**
(jump to −40% at ~0.1/yr on the crypto slice). Two lenses — *with contributions* (the real plan) and *lump-sum*
(isolates the pure convexity, no contribution masking).

**(A) $5k + $500/mo, 20% barbell (the actual plan), haircut+gap ON:**

| Horizon | median | p5 | p95 | P(2x) | P(5x) | P(<half) |
|---|---|---|---|---|---|---|
| 1yr | $11,091 | $7,902 | $13,159 | 0.83 | 0.00 | 0.00 |
| 3yr | $25,454 | $16,122 | $33,226 | 1.00 | 0.54 | 0.00 |
| 5yr | $40,913 | $23,670 | $59,241 | 1.00 | 0.93 | 0.00 |

(P(2x)/P(5x) here are vs the original $5k and are dominated by the $6k/yr of contributions — *not* a convexity signal.)
**Median years to $70k ≈ 7.7 (haircut) / 7.1 (no haircut); P(reach by 10yr) ≈ 0.82–0.90.** P(<half) = 0 — the base + inflows floor it.

**(B) LUMP-SUM $5k, NO contributions — 20% barbell (isolates the asymmetry), haircut+gap ON:**

| Horizon | median | p5 | p95 | P(2x) | P(5x) | P(<half) |
|---|---|---|---|---|---|---|
| 1yr | $5,388 | $3,305 | $6,715 | 0.00 | 0.00 | 0.00 |
| 3yr | $6,061 | $2,982 | $9,059 | 0.02 | 0.00 | 0.02 |
| 5yr | $6,615 | $2,704 | $11,650 | 0.12 | 0.00 | 0.04 |
| | | | | **right-skewed: p95 $11.6k vs p5 $2.7k, median only $6.6k** | | |

**(C) LUMP-SUM $5k in the PURE convex sleeve alone (max asymmetry), heavy haircut (−20%/yr) + gap ON:**

| Horizon | median | p5 | p95 | P(2x) | P(5x) | P(<half) |
|---|---|---|---|---|---|---|
| 1yr | $5,537 | $1,732 | $17,548 | 0.20 | 0.02 | 0.12 |
| 3yr | $6,862 | $948 | $49,702 | 0.37 | 0.14 | 0.20 |
| 5yr | $8,405 | **$671** | **$111,997** | **0.46** | **0.23** | 0.22 |

**This is the disproportionate payoff, concretely:** $5k in the pure convex sleeve has a 5yr **p95 of ~$112k** (a 22x)
and **P(5x)=23%**, against a p5 of **$671** and **P(<half)=22%**. The median is only $8.4k — the mean is dragged up by
the right tail you cannot get any other way. **That is positive skew + capped left tail + (historically) +EV in one
object.** The barbell's job is to harvest that p95 while the 80% base guarantees the p5 of the *total* portfolio never
approaches ruin (lump-sum 20%-blend P(<half) ≈ 0.04 even after haircut+gaps).

---

## 5. VERDICT

**Best data-informed convex high-upside sleeve:** the **crypto BASKET trend-timed** (BTC+ETH+SOL, each held only above
its 200-day SMA, else cash/BIL; weekly cadence; 20 bps/side). It is the rare object that is **+EV AND positive-skew
AND left-tail-capped**: skew **1.45**, tail ratio **2.83**, Omega **3.20**, CAGR **75%**, maxDD **−58%** full-sample
(skew 1.46 / CAGR 24% / DD −36% even in the harsh 2022+ regime). The trend exit is what *manufactures* the convexity —
it cuts buy-hold's −83% DD to −58% and lifts skew from 0.62 to 1.45 while staying +EV. Diversifying the *entries*
(basket) beats *levering* (2x/3x both REJECTED for −93%/−99% uncapped left tails) and beats single-asset BTC.

**Optimal barbell:** **20% convex sleeve / 80% trend-overlaid all-weather base** (go to **30%** if you can stomach a
~−27% drawdown). At 20%: CAGR **~12.6%**, maxDD **~−21%**, skew **0.68**, Sharpe at its **1.15 plateau peak**, P(<half)
of the *total* ≈ 0. Sharpe rolls off and DD deepens faster than skew above ~30% → that is the convex sweet spot.

**From $5k:** with $500/mo, median **~7 years to $70k**, P(reach by 10yr) ~0.82–0.90, P(ruin)≈0.
The asymmetry lives in the **pure convex slice**: lump-sum $5k → 5yr **P(2x)=46%, P(5x)=23%, p95 ≈ $112k** vs
**p5 ≈ $671, P(<half)=22%**. Real, large, right-tailed upside; a bounded, survivable downside on the slice; **zero**
total-portfolio ruin because the 80% base + contributions floor it.

**Vehicle:** hold the convex crypto sleeve via **spot ETFs (IBIT/ETHA) in an IRA/Roth** — the trend rule churns
(roundtrips/yr), so a tax-advantaged account avoids short-term-gains drag, and an ETF in an IRA gives the spot
exposure **without margin and without LETF financing/gap-to-ruin risk**. **Do NOT use a 3x LETF or taxable margin for
this** — both reintroduce the uncapped left tail the whole strategy exists to avoid (and the LETF is outright −EV).

**Is the convexity genuinely disproportionate after costs? YES — but humbly.** It is real and data-backed, and it
*survives* the 2022–24 bear (so not purely a 2017/2021 artifact), but it is **dampened** out-of-sample (tail ratio
2.8 → 1.66) and the crypto sample is short (~1 clean cycle of independent right-tail events). We therefore haircut the
right tail explicitly (−12 to −20%/yr) and still find a disproportionate +EV payoff. **This is high-variance**: the
upside is genuinely outsized, but on the convex slice you have a ~1-in-5 chance of ending below half over 5 years.
That is exactly why it is sized at 20% behind a low-DD all-weather base — you can only lose the slice.

---
*All figures from `convex_asymmetry.py` on `/tmp/convex_data/prices.csv` (yfinance, not committed). PAPER ONLY.
Past 10x crypto runs may not repeat; the durable edge is the left-tail cut, not the magnitude of the right tail.*
