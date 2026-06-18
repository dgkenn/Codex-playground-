# KALSHI MAKER — CAPACITY & FILL REALISM (soft / non-crypto markets)

**Agent scope:** Not "does the favorite-longshot maker edge exist" (other agents own EV-by-band
and adverse selection). **This doc answers only:** *can a $100–$1,000 retail account actually get
filled passively, and how much $/month can it harvest before its own size moves the price?*

**Data:** Kalshi public API (no auth), `https://api.elections.kalshi.com/trade-api/v2`.
Settled, binary, non-MVE markets with `volume_fp >= 300`, across Economics, Politics,
Climate & Weather, Entertainment, Science & Technology. Volume time-distribution from hourly
candlesticks; touch size / fill direction from the `/markets/trades` stream (`taker_side`:
`yes` lifts the ask, `no` hits the bid). Script: `kalshi_maker_capacity.py`.

---

## 1. Total volume per market (the honest, whale-adjusted view)

Means are useless here — a handful of mega election/CPI markets dominate them. The number that
matters for a small maker is the **median tradeable market**, because that is the body of the
distribution you'll actually be quoting.

| Category | tradeable mkts (vol≥300) | **median life volume** | p25 / p75 | mean (whale-skewed) | max |
|---|---|---|---|---|---|
| Economics | 254 | **1,660 contracts** | 1,005 / 3,088 | 3,594 | 118,666 |
| Climate & Weather | 949 | **1,240 contracts** | 604 / 2,689 | 2,562 | 88,291 |
| Entertainment | 92 | **1,016 contracts** | 642 / 2,234 | 2,452 | 73,193 |
| Politics | few settled\* | ~29,000 | — | 29,479 | 33,217 |
| Science & Tech | 49 | ~30k mean | — | 33,788 | — |

\*Politics resolves mostly at long horizons or as MVE; very few binary soft markets settle in any
given window. The Politics/Sci-Tech *means* in the script output (`358k`, `34k`) come from a
couple of mega-markets and are **not** representative of anything a small maker can repeatedly trade.

**Median soft market = ~1,000–1,700 contracts traded over its ENTIRE life.** At a ~30–50¢ average
price that's **$300–$800 of total notional turnover per market, lifetime** — and that is *taker*
turnover shared across *all* makers, not yours alone.

---

## 2. How volume is distributed over time — it is NOT steady

A passive maker needs **steady, two-sided flow**. The data shows the opposite:

| Category | first⅓ / mid⅓ / **last⅓** of life | active-hours fraction | shape |
|---|---|---|---|
| Economics | 37% / 38% / 25% | 36% | mildly front/mid |
| Politics | 42% / 9% / **50%** | 33% | barbell, settlement-heavy |
| Climate & Weather | 4% / 37% / **58%** | 78% | strongly settlement-loaded |
| Entertainment | 12% / 24% / **64%** | 42% | strongly settlement-loaded |
| Science & Tech | 6% / 36% / **59%** | 17% | strongly settlement-loaded |

- **3 of 5 categories put ~55–65% of volume in the final third of life** — right at resolution,
  exactly when adverse selection is worst (the other agents' problem, but it kills the maker thesis
  too: the flow that *would* fill you is the most toxic flow).
- **Active-hours fraction is low (17–42%) outside weather** — the touch sits idle most of the time.
  Weather is "active 78%" only because those are same-day markets that live a few hours; the flow
  is bursty, not steady (see §3).

There is **no category with steady, evenly-distributed two-sided flow.** A maker is either idle or
fighting end-of-life informed flow.

---

## 3. Touch size & how often the touch trades

Probed median-volume markets directly (Climate `KXLOWTLAX` daily-temperature, the most plentiful
tradeable soft series). Representative ~950-contract markets:

| ticker | life vol | # trades | **median clip** | max clip | trades/day | median gap between trades |
|---|---|---|---|---|---|---|
| KXLOWTLAX-26JUN15-B60.5 | 920 | 70 | **3** | 200 | 42 | 0.3 min |
| KXLOWTLAX-26JUN12-T57 | 935 | 81 | **4** | 175 | 49 | 0.0 min |
| KXLOWTLAX-26JUN13-B59.5 | 984 | 108 | **3** | 200 | 64 | 0.0 min |

Across all categories the **median trade clip is 3–50 contracts** (Climate/Ent ≈ 3–10, Economics ≈ 50).
At typical prices that's **~$1–$25 of notional per print.**

Critical implications:
- **The touch trades in tiny bites.** A maker who posts a $100–$1,000 clip ($300–$3,000 of contracts)
  cannot get the clip filled at the touch — it gets nibbled 3–4 contracts at a time, and the
  remainder sits until either it's stale or the price moves through it (adverse fill).
- The near-zero median gaps are **bursts**: 40–60 trades cram into a short active window near
  settlement, then silence. That is not the steady drip a passive maker monetizes.

---

## 4. Realistic passive FILL RATE

Of the lifetime taker flow, how much would lift *your* resting clip at the touch? It is throttled by:

- **Side engagement (~0.5):** a favorite-longshot maker is on one side (sell the favorite / buy the
  longshot), so only ~half the two-sided flow ever crosses to your quote.
- **Queue capture (~0.25):** at a quiet touch you are not alone (Kalshi MM + others); you win the
  queue maybe a quarter of the time on small markets, less on liquid ones.
- **Touch presence (~0.60):** you are quoted at the touch ~60% of the active life (you pull on news,
  you re-quote, you're asleep for some of the burst).

`capturable contracts ≈ life_volume × 0.5 × 0.25 × 0.60 ≈ 7.5% of life volume.`

On the **median ~1,200-contract** soft market that is **~90 contracts you could ever passively fill
over the market's entire life** — and most of those arrive in the toxic final third.

---

## 5. $/day and $/month capacity ceiling

Net maker edge per filled contract on these wide-but-thin books is ~**1¢** (1–3¢ gross spread minus
Kalshi's quadratic fees and the slice you give back to informed flow). Capacity = filled contracts ×
edge, spread over the market's life, times the number of markets one account can realistically quote
at once (~5 per category, heavily overlapping in time).

**Script output (per-category model):**

| Category | est. capturable/market-life | $/day per market | $/day @5 mkts | **$/month** |
|---|---|---|---|---|
| Economics | 198 contracts | $0.10 | $0.52 | **$16** |
| Entertainment | 345 | $0.22 | $1.10 | **$33** |
| Science & Tech | 2,534\* | $0.35 | $1.77 | **$53\*** |
| Climate & Weather | 726 | $4.35 | $21.77 | **$653\*** |
| Politics | 26,879\* | $5.79 | $28.95 | **$868\*** |

\*Climate, Politics and Sci-Tech are inflated by **mean** (whale) life-volume and by the optimistic
queue/presence assumptions. Re-running the model on the **median** market and against the realized
3–4-contract touch (you can only ever fill the small clips, not the rare 200-lot whale prints)
collapses these:

- Median ~1,200-contract market → ~90 capturable contracts → **~$0.90 of edge over the market's whole
  life.** A weather market lives ~1 day, so **~$0.90/day/market**.
- One account can babysit maybe **5–8 of these bursty markets** concurrently → **~$5–7/day** realistic,
  and that *assumes* the favorite-longshot edge is real and survives fees/adverse selection.

**Honest blended ceiling for a small account: roughly $5–10/day ≈ $150–300/month at the absolute
optimistic top**, and **realistically $1–5/day ≈ $30–150/month** once you down-weight the
settlement-loaded toxic flow and the fact that your $100–$1,000 clip can't be filled in 3–4-contract
nibbles. The script's headline "$1,623/month" is an artifact of whale-skewed means + generous
capture and should be **disregarded** in favor of the median-market figure.

---

## 6. Reconciliation with the crypto box reality

The 15-minute crypto box was **fill-rate-limited to ~$10–27/day and saturated a ~$100 bankroll.**

| Dimension | Crypto 15m box | Soft markets (this study) |
|---|---|---|
| Flow cadence | Continuous, 24/7, every 15 min a fresh market | Bursty, settlement-loaded, mostly idle |
| Touch trades | Frequently, decent size | 3–50 contract nibbles, then silence |
| Two-sided steady flow | Yes (mechanical) | **No** — back-loaded near resolution |
| Realized maker capacity | **$10–27/day** | **~$1–5/day realistic, ~$10 optimistic** |
| Bankroll that saturates | ~$100 | **< $100** (you can't even deploy $1,000 — the touch is 3–4 contracts) |

**Soft markets are WORSE than the box on capacity, not better.** The box at least had continuous
mechanical flow; soft markets give you long idle stretches punctuated by toxic end-of-life bursts,
and a touch so thin that a $1,000 clip is irrelevant — you'd be filled in dribs and your unfilled
remainder is pure adverse-selection bait. The box already proved a $100 bankroll saturates at
~$10–27/day; soft markets clear an even **lower** ceiling.

---

## 7. VERDICT

**Capacity is NOT investable for a small bankroll, and the constraint bites before edge even matters.**

1. The median tradeable soft market turns over only **~1,000–1,700 contracts in its whole life**
   (~$300–$800 notional), shared across all makers.
2. The touch trades in **3–4 contract nibbles**, so a $100–$1,000 maker clip can never be filled at
   the touch — capacity is throttled by tick-by-tick crumbs, not bankroll.
3. Flow is **settlement-loaded (55–65% in the final third)** — the fillable flow is also the most
   toxic flow.
4. Realistic blended capacity is **~$1–5/day ≈ $30–150/month** optimistic-case; the honest central
   estimate sits **below or around the $50/month uninvestability threshold.**
5. This is **worse than the crypto box** ($10–27/day), which already saturated a $100 bankroll.

**Even if the favorite-longshot maker edge is real, it is uninvestable for a $100–$1,000 retail
account: you cannot get filled in size, the harvestable $/month is sub-$150 (and plausibly sub-$50),
and the flow you *can* catch is concentrated exactly where adverse selection is worst.** The
capacity ceiling alone kills the thesis.
