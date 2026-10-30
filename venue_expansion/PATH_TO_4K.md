# The $4,000/month target, against 55 studies of measurement — 2026-10-29

This is the arithmetic connecting the target to what has actually been measured, and the only
strategy set the measurements support. It is not encouraging, but it is specific, and the specificity
is what makes it actionable.

## 1. The target in return terms — the number that decides everything

$4,000/month is not a strategy, it is a **return rate**, and its feasibility is set entirely by
capital:

| capital | $4k/mo is | plausible? |
|---|---|---|
| $10,000 | **40%/month** (~5,600%/yr) | no — no honest edge does this |
| $50,000 | 8%/month (~150%/yr) | no |
| $100,000 | 4%/month (~60%/yr) | only elite, leveraged, full-time |
| $500,000 | 0.8%/month (~10%/yr) | yes, with a real edge |
| $1,200,000 | 0.33%/month (~4%/yr) | Treasury bills |

**I have never been told the capital, and it is the single input that changes the answer most.** The
rest of this document assumes it is small — consistent with every registered next step in this repo
being a ≤$100 canary. If the real figure is six or seven digits, the honest strategy is completely
different and mostly does not involve Kalshi.

## 2. The one measured edge, and its thinness

`FAVOURITE_MAKER`, Z2, T=15, k=1, pessimistic N=25 fill — the only non-closed candidate in 55 studies:

| | |
|---|---|
| EV per filled contract | **+1.47c** |
| EV per quoted contract | +1.22c |
| fill rate | 83.0% |
| win / lose | +7.04c at 94.43% / **−92.96c at 5.57%** |
| per-fill sd | 22.9c |
| **return per fill on capital at risk** | **+1.47c on 92.96c = 1.58%** |

That last line is the binding fact. **The edge is 1.58% of the capital it ties up.** To net $190/day
you must therefore expose roughly **$12,045 of notional per day**, and that figure is *invariant* —
it does not change whether you quote 5 contracts across 3,122 markets or 100 across 156:

| size/quote | fills/day needed | qualifying markets/day | vs 55 today | bad-day notional |
|---:|---:|---:|---:|---:|
| 5 | 2,592 | 3,122 | 57× | $12,045 |
| 10 | 1,296 | 1,561 | 28× | $12,045 |
| 25 | 518 | 624 | **11×** | $12,045 |
| 50 | 259 | 312 | 6× | $12,045 |
| 100 | 130 | 156 | 3× | $12,045 |

**$4,000/month requires ~$12,000 at risk, i.e. a 33%/month return on that base.** No measurement in
this repo supports 33%/month, and nothing will.

## 3. Size is the wrong lever — the data says so directly

The +1.47c was measured at **1 contract per quote**, with **N=25 contracts assumed resting ahead**.
Quoting 282 contracts puts you far behind that queue, and adverse selection is *asymmetric in size*:
you get **filled in full on the trades that go against you** and **partially on the ones that don't**.
`MAKER_FILL` and `FAVOURITE_MAKER` measured fill-conditional loss ratios of **1.1–2.3** at size ~1;
there is no basis for assuming they hold at 282, and every reason to expect them worse.

**The edge is not invariant to size. Scaling size is the one move the measurements forbid.**

## 4. Breadth is the right lever — and it fixes the risk, not just the revenue

The binding constraint on the target is **opportunity count**: 55 qualifying strikes/day on BTC
hourly. At a defensible 25 contracts/quote, $4k/month needs **~624 qualifying markets/day — 11×
today.**

And breadth does something size cannot. Those 55 BTC strikes share **one underlying price path**, so
a bad day is correlated: the perfectly-correlated bound is **+$912 on 94.4% of days and −$12,045 on
5.6%**, with a **70% chance of at least one such day per month** against $4,000 of expected profit.
Spreading the same notional across **uncorrelated** underlyings — weather, politics, economics,
commodities — converts that into the independent bound of **$439/day sd against $190/day EV**.

Kalshi has **15,416 series**. If even 1–2% of the catalog carries BTC-hourly-like economics, the
breadth exists. **`WIDE_SPREAD_MAKER`, running now, is the measurement of exactly this** — and it was
registered before this document, for the independent reason that we had only ever tested the
tightest-spread product on the venue.

## 5. The strategy set, with honest gates

**There is no deployable strategy today. Expected value of trading now is $0, and the measured
venue-wide drag means acting before the gates clear has negative expectation.**

| # | step | gate | what it buys |
|---|---|---|---|
| 1 | **~50c pre-flight** — one 1-contract NO order reconciled against `/portfolio/positions` | `side="ask"` proves short-YES | removes the most expensive latent bug in the repo; nothing offline can verify it |
| 2 | **`WIDE_SPREAD_MAKER`** (running) | a sweet spot exists: spread ≥5c **with** flow, adverse selection not consuming it | tells us whether breadth exists at all — the binding constraint |
| 3 | **Depth collection** on qualifying markets (needs `main`) | measures real queue position | replaces the assumed `N=25`; sets max defensible size |
| 4 | **December re-run** of `FAVOURITE_MAKER` at ≥130 days | Bonferroni Wilson lower bound clears break-even | establishes whether the edge is real at all |
| 5 | **1-contract canary**, ≤$100 | live fills match backtest fill rate | proves queue position and execution |
| 6 | Scale by **breadth, never size**, across uncorrelated underlyings | per-product economics hold | the only path with a defensible risk profile |

## 6. My honest probability assessment

Stated numerically because vagueness here would be a disservice:

- **Edge survives the December re-run: ~15%.** The effect is **non-monotone in T** (+2.11 → +1.47 →
  +0.12 → +0.75pp), which is a noise signature, and this program has twice watched "underpowered"
  become "losing" with more data (the forecast sleeve, early-lock).
- **Conditional on that, breadth exists at 11×: ~40%.** Unknown, and `WIDE_SPREAD_MAKER` will say.
- **Conditional on both, it survives live queue position and 25× size: ~30%.** The venue's own
  participants act at the same microsecond; Kalshi itself describes the flow as "market makers posting
  fixed quotes that faster traders hit."

**Joint: roughly 2% of reaching a few hundred dollars a month. Materially below that for $4,000** —
and $4,000 additionally requires ~$12,000 of risk capital that no step above assumes you have.

## 7. What I would actually advise

**Do not fund this to $4,000/month.** The honest expected value of the program as it stands is near
zero, and the one open candidate is not statistically established.

Two things are nonetheless worth doing because they are cheap and they resolve real uncertainty:
the **50c pre-flight** (step 1), and letting **steps 2–4 finish**, which cost compute and not capital.

And the one thing that would change my assessment most is not another study: **tell me the actual
capital.** At $500k+, $4,000/month is a 10%/yr target and the right instrument is almost certainly
not a prediction market. At $10k it is a 40%/month target and the answer is that it cannot be done —
by me, by this repo, or by anyone selling a system that claims otherwise.

---

# UPDATE 2026-10-30 — the breadth lever is closed

`WIDE_SPREAD_MAKER` returned **KILL**. Section 4 above identified **breadth** as the binding
constraint on $4,000/month and named that study as its measurement. The measurement came back
negative, and it closes the lever:

- **Flow was never the problem** — pooled fill rates 63–84%, the 5% gate met in 172 of 176 cells. My
  predicted "wide spread means thin flow" failure mode is **refuted**.
- **Adverse selection is worse at wider spreads, not better.** All 38 floor-meeting cells fail, with
  point estimates **5.4–27.1 percentage points on the losing side** — against ~1pp on BTC favourites.

**The spread is the price of adverse selection, not revenue.** Measured at both ends of the liquidity
spectrum, it is priced correctly. So the 11× breadth that $4k/month needs **does not exist at
breakeven economics**, let alone profitable ones.

## Revised probabilities

| | before | now |
|---|---|---|
| edge survives the December re-run | ~15% | **~8%** |
| breadth exists at 11× | ~40% | **~3%** (measured negative) |
| survives live queue + size | ~30% | ~30% |
| **joint, a few hundred $/month** | ~2% | **well under 1%** |

The downgrade is driven by one specific thing: the `KXUFCROUNDS` squeak. Two cells cleared gate 1 on
352 comparisons and dissolved on inspection — the quote population's base rate was simply off (67.5%
YES at a 48% mean price). **The BTC-favourite +1.47c is the same kind of object: one positive cell
among hundreds.** That is now a demonstrated failure mode in this program, not a hypothetical.

## The one thing that cuts the other way

Re-examining `FAVOURITE_MAKER`'s own numbers, the **k-gradient is structured where the T-gradient is
not**:

| k | edge per fill | adverse-selection gap | fill rate | EV/quoted |
|---|---|---|---|---|
| 1 | +1.47pp | −0.95pp | 83.0% | +1.223c |
| 2 | +1.48pp | −3.06pp | 60.2% | +0.890c |

**The edge per fill is essentially invariant in k (+1.47 vs +1.48pp); what varies is the fill rate.**
Adverse selection worsening with k is *mechanistically required* — quoting deeper means you are filled
only when the market moves to you — so this is structure, not fit. The non-monotone T-gradient
(+2.11 → +1.47 → +0.12 → +0.75pp) remains evidence against.

This implies the untested cell **k = 0 — join the touch rather than improve inside it** — should carry
the highest fill rate at the same per-fill edge. **But k=0 puts you at the back of the queue at the
best bid, so the answer is entirely determined by the queue position that every study has had to
assume (`N ∈ {25, 100}`).** It cannot be answered without the depth data.

## Where the target stands

**$4,000/month is not reachable from anything measured, and the breadth path that was its best hope is
now closed by measurement rather than by argument.** The remaining work is bounded and blocked:

1. **Depth collection** (needs `main`) → decides k=0, which is the last motivated cell.
2. **December re-run** at ≥130 days → decides whether the BTC-favourite edge exists at all.
3. The **~50c pre-flight** → still worth doing regardless.

Nothing else on this venue is untested that is also testable with available data.
