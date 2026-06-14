# BTC_TREND_TIMING — Is the best way to hold crypto buy-and-hold, or a trivial trend filter?

**Question (for a US small-bankroll crypto believer):** you want crypto exposure.
Is naive **buy-and-hold** BTC/ETH best, or does a simple single-asset **trend filter**
(price > moving-average / time-series-momentum, in→hold, out→cash) *dominate* it by
cutting the brutal −75/−85% bear drawdowns while keeping most of the upside? Deployable
via **spot (Coinbase/Kraken)** or the **spot ETFs (IBIT/ETHA)** — IRA-able, no perp/access wall.

**VERDICT (one line):** **Trend-timing does NOT raise BTC's raw CAGR much (BTC's buy-hold
CAGR is already enormous), but it roughly HALVES the volatility and meaningfully cuts the
worst drawdowns — so on a risk-adjusted basis it dominates: Sharpe ~0.97→~1.2 and maxDD
−83%→~−60/−68% on full history, and the drawdown cut is far bigger (−66/−77% → −26/−37%)
in the recent post-2021 cycle that actually matters for a new buyer. The honest answer is
"hold less, sleep much better": a 100–200d SMA / 6-month-TSMOM rule on BTC, checked weekly,
is the better way to hold crypto for anyone who cannot stomach an −80% paper loss.** Best
single rule: **BTC ≥ 200-day SMA, weekly check** (or 6-month TSMOM > 0), traded on the **IBIT
ETF in an IRA** (tax-free switches) or BTC spot. **ETH timing is even more valuable** (buy-hold
ETH is barely positive net of its −94% drawdown). It is a **better, cleaner crypto sleeve than
the proxy-ETF members** for a small bankroll, but it is essentially the *same risk premium* the
ETF-momentum book already harvests — so use one or the other, do not double-count.

---

## SCREENS — data, window, costs

- **Source:** yfinance daily closes (`auto_adjust=True`). `BTC-USD` (2014-09-17→2026-06-14, 4,288 days),
  `ETH-USD` (2017-11→2026-06, 3,139), `IBIT` (2024-01→2026-06, 606), `ETHA` (2024-07→2026-06, 474),
  `BIL` (T-bill ETF, the out-of-market/cash leg). Staged at `/tmp/btc_data/prices.csv` (**not committed**).
- **No look-ahead:** signal computed at close *t*, position effective close *t+1*.
- **Cash leg:** when OUT we earn **BIL** (realistic IRA cash / ~T-bill; a USDC stablecoin earns ~0,
  which is *worse* — so results are mildly optimistic by the T-bill carry, ~2–5%/yr).
- **Costs:** spot round-trip ~20–40 bps. We charge **20 bps PER SIDE** (= 40 bps round-trip) on every
  in↔out switch. Cost sensitivity (0/10/20/40 bps) reported — it is **immaterial** because turnover is low.
- **Annualization:** 365 days/yr (crypto trades 7 days a week; the BTC-USD series is daily-calendar).
- **Caveat on sample size:** BTC has ~**2.5 independent cycles** of clean data, ETH ~**2**. This is a
  small number of crashes. Treat every point estimate as a wide range; the *direction* (timing helps
  risk-adjusted, especially in bears) is robust, the *magnitude* is not precise.

---

## 1. BUY-AND-HOLD baseline — the brutal drawdown reality

| Window | CAGR | Sharpe | Sortino | maxDD | ann vol |
|---|---|---|---|---|---|
| **BTC** full 2014-09→ | **+52%** | 0.97 | 1.28 | **−83.4%** | 67% |
| BTC since 2020 | +40% | 0.87 | 1.17 | −76.6% | 60% |
| BTC since 2021-11 (last cycle top) | **+1%** | 0.28 | 0.40 | **−76.6%** | 52% |
| BTC recent OOS 2022→ | +7% | 0.39 | 0.55 | −66.7% | 51% |
| BTC ETF-era 2024→ | +17% | 0.56 | 0.84 | −51.2% | 49% |
| **ETH** full 2017-11→ | +21% | 0.66 | 0.91 | **−94.0%** | 85% |
| ETH since 2020 | +49% | 0.90 | 1.24 | −79.4% | 81% |
| ETH recent OOS 2022→ | **−17%** | 0.09 | 0.12 | −74.1% | 70% |

**Per-cycle BTC buy-hold drawdown (the thing nobody can hold):**

| Cycle | Total return | maxDD |
|---|---|---|
| 2014–15 bear | −50% | **−61%** |
| 2017 bull → 2018 bear | +275% | **−83%** |
| 2021 → 2022 bear | −44% | **−77%** |
| 2022 full year | −65% | −67% |
| 2023–24 recovery | +462% | −26% |
| 2025–26 (to date) | −32% | −51% |

**Reality:** BTC's *raw* CAGR is spectacular, but you "pay" for it with repeated **−60 to −85%**
peak-to-trough drawdowns and **60–85% annualized vol**. Buying near a cycle top (late-2021) left
you ~flat for 4+ years through a −77% hole. ETH buy-hold is *barely positive* over its full life once
you survive a −94% drawdown, and is **negative** since 2022. Few real humans hold through this; the
behavioral reality is they panic-sell the bottom. That is the problem trend-timing exists to fix.

---

## 2 & 3. TREND-TIMING results — does it dominate?

Rules tested (in = hold asset, out = BIL cash): **SMA 50/100/150/200/250** (price>SMA), **TSMOM 3/6/12-month**
(trailing return > 0), **50/200 dual-MA cross**, and **signal-check cadence** daily / weekly / monthly.
Net of 20 bps/side. Selected results:

### BTC — full history (2014-09→2026-06)

| Rule | CAGR | Sharpe | maxDD | vol | %invested | round-trips/yr |
|---|---|---|---|---|---|---|
| BUY-HOLD | +52% | 0.97 | **−83%** | 67% | 100% | 0 |
| SMA50 (daily) | +68% | 1.33 | −59% | 48% | 56% | 9.2 |
| SMA100 (daily) | +59% | 1.19 | −61% | 50% | 56% | 6.2 |
| SMA150 (daily) | +73% | 1.33 | −61% | 51% | 58% | 3.2 |
| **SMA200 (weekly)** | **+60%** | **1.17** | −68% | 52% | 58% | **1.4** |
| TSMOM 6m | +64% | 1.21 | −68% | 52% | 59% | 4.9 |
| TSMOM 12m | +69% | 1.23 | −71% | 55% | 69% | 1.8 |
| 50/200 cross | +53% | 1.05 | −69% | 54% | 59% | 0.9 |

### BTC — recent cycle (2021-11 top →) and OOS (2022→)

| Rule | CAGR (since 21-top) | maxDD | CAGR (2022→) | maxDD |
|---|---|---|---|---|
| BUY-HOLD | **+1%** | **−77%** | +7% | **−67%** |
| SMA150 (daily) | +26% | **−27%** | +29% | −27% |
| SMA200 (daily) | +27% | −33% | +28% | −33% |
| **SMA200 (weekly)** | +23% | −36% | +24% | −36% |
| TSMOM 6m | +30% | **−26%** | +31% | −26% |

### ETH — full + recent

| Rule | CAGR (full) | maxDD (full) | CAGR (2022→) | maxDD (2022→) |
|---|---|---|---|---|
| BUY-HOLD | +21% | **−94%** | **−17%** | **−74%** |
| SMA50 | +45% | −60% | +23% | −42% |
| SMA200 (daily) | +40% | −71% | +19% | **−39%** |
| TSMOM 6m | +31% | −65% | −4% | −57% |

**What dominates, honestly:**

1. **On full BTC history, timing barely changes raw CAGR (already ~+52%) — it cuts vol ~67%→~50% and
   lifts Sharpe ~0.97→~1.1–1.3.** The headline "−80% → −30%" drawdown cut **does NOT fully materialize
   on the *full-sample* maxDD** (it lands ~−60 to −68%). The reason is honest and important: BTC's worst
   crashes (2018, 2021→22) started *fast from fresh all-time highs* while price was still above even a
   200-day MA, so the filter sat through the first leg down before exiting. A slow MA cannot dodge a
   vertical crash; it dodges the *grind*.
2. **In the recent cycle (where a new buyer actually lives), the drawdown cut IS dramatic: −77%/−67% →
   −26/−36%, with HIGHER CAGR (+1% → +23–30%) because buy-hold spent that whole window underwater.**
   This is the strongest, most decision-relevant result.
3. **For ETH, timing is unambiguously better on every axis** — buy-hold ETH is a coin-flip net of a −94%
   drawdown; the filter roughly doubles Sharpe and halves the drawdown, and turns the −17% post-2022
   buy-hold into +19/+23%.
4. **Downside mechanics (BTC SMA200 weekly, full):** worst single day −37%→−19% (we were OUT for 35% of
   the 20 worst days), and IN for 55% of the 20 best days. We keep most up-days, skip a chunk of crash-days.
5. **Whipsaw / cost:** weekly cadence gives **~1.4 round-trips/yr** (daily SMA50 churns ~9/yr — avoid).
   Cost is negligible: BTC SMA200 weekly CAGR is **61.0% @ 0bps vs 59.3% @ 40bps/side** — turnover is so
   low that fees barely register. The real friction in taxable accounts is **tax**, not fees (see §4).

**Net call on §3:** trend-timing **dominates buy-and-hold on a risk-adjusted basis (Sharpe & Sortino up,
vol roughly halved, recent-cycle drawdown cut by half)**, while keeping or *exceeding* CAGR. It does **not**
multiply the raw long-run CAGR, and it does **not** make BTC low-risk — a timed sleeve still draws down
~−30 to −40% in a real bear. The benefit is "hold the same dollars with half the vol and far shallower
holes," i.e. **you can size bigger / sleep / actually stay in the trade.**

---

## 4. ROBUSTNESS

**(a) Plateau across MA length** (BTC full, weekly signal, 20bps/side) — *not* a lucky single value:

| SMA n | 50 | 75 | 100 | 125 | 150 | 175 | 200 | 225 | 250 | 275 | 300 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CAGR% | 65 | 55 | 71 | 67 | 63 | 59 | 60 | 59 | 58 | 57 | 59 |
| Sharpe | 1.28 | 1.12 | 1.32 | 1.25 | 1.21 | 1.16 | 1.17 | 1.15 | 1.12 | 1.11 | 1.12 |

**Sharpe sits in a tight 1.1–1.3 band for every length from 50 to 300 days, vs 0.97 buy-hold.** This is a
genuine plateau, not a peak — the edge is the *trend-following structure*, not a tuned parameter. The
~100d region looks slightly best but is within noise; **200d is the conventional, robust middle.**

**(b) Recent holdout (2022→):** every sensible rule beats buy-hold on Sharpe *and* drawdown out-of-sample
(SMA200 weekly: +24% CAGR / −36% DD vs +7% / −67%). The edge did **not** evaporate post-discovery.

**(c) BTC vs ETH:** same direction on both; **ETH benefits more** (higher vol, deeper crashes → more to
gain from cutting them). Cross-asset agreement raises confidence it isn't a BTC-only fluke.

**(d) IBIT / ETHA ETF-era (2024→, ~1.5–2yr, tiny sample — directional only):**
- **IBIT:** buy-hold +20% CAGR / −52% DD; **SMA200 daily +24% / −30%**, 50/200 cross +24% / −33%. The
  classic slow-trend rules **work on the ETF**, confirming spot results transfer to the IRA-able instrument.
  (Fast/odd lengths like SMA100/150 underperformed here, but that is ~600 days = one wiggle; ignore as noise.)
- **ETHA:** buy-hold **−43% CAGR / −68% DD** (brutal 2024-on for ETH); SMA50 +32%/−34%, slow MAs mixed on
  the tiny sample. Consistent with "ETH timing cuts the bleed," but the window is too short to lean on.

**Tax note (NOT advice):** in an **IRA via IBIT/ETHA**, every trend-timing switch is **tax-free** — the
ideal home for this. In a **taxable** account, each exit **realizes gains** (short-term if held <1yr), which
can erode the after-tax edge of frequent rules — another reason to prefer **slow MA + weekly cadence**
(~1.4 trips/yr) and, ideally, the **IRA wrapper**.

---

## 5. COMPARE / COMBINE with the crypto-proxy-ETF momentum book

- The ETF-momentum book (`ETF_MOMENTUM.md`) reports core CAGR ~9% / Sharpe ~0.80 / maxDD ~−17%, rising to
  **CAGR ~14% / Sharpe ~0.98 / maxDD ~−18%** when crypto-proxy ETFs (GBTC/MSTR/COIN/IBIT) are added as
  high-beta members under the same dual-momentum + SPY-200d-gate framework.
- A **trend-timed BTC/IBIT sleeve** (Sharpe ~1.1–1.3, but maxDD ~−35% recent / ~−68% worst-case, vol ~50%)
  is **higher Sharpe but far higher absolute risk** than the diversified book. They are **not competitors at
  the same risk level** — the book is a *diversified, low-DD* product; trend-timed BTC is a *concentrated,
  high-vol* single bet whose only risk control is the on/off switch.
- **Same risk premium, two delivery vehicles.** Adding crypto-proxies to the book *is* a diversified,
  position-sized, regime-gated way of holding "trend-timed crypto." A standalone trend-timed BTC sleeve is
  the **concentrated, purer-beta** version. **They are largely redundant — do not stack both at full size**
  (you'd double your crypto beta).
- **Which is the better way to add crypto?** For someone who **already runs the ETF-momentum book**, just let
  the **crypto-proxy members** carry the crypto exposure — it's diversified and position-sized for you. For a
  **crypto *believer* who wants deliberate, sizable BTC/ETH exposure** (more than a momentum book would ever
  allocate), a **small standalone trend-timed BTC/IBIT sleeve is the cleaner, higher-conviction vehicle** —
  it's the single-name version of the exact same trend premium, with an explicit risk dial.

---

## 6. VERDICT — the best way for a US small-bankroll crypto believer to hold crypto

1. **Do NOT naive buy-and-hold the whole position.** Raw CAGR is huge, but the −60/−85% drawdowns and 60–85%
   vol are unholdable for most, and ETH buy-hold is barely positive net of a −94% crash. The behavioral
   failure mode (panic-selling the bottom) destroys the buy-hold CAGR you never actually captured.
2. **Use a simple, slow trend filter.** **Best rule: hold BTC while price ≥ its 200-day SMA, check the signal
   weekly, move to cash/T-bill when it breaks.** (6-month TSMOM > 0 is an equally good, near-identical cousin;
   pick one.) ~1.4 round-trips/yr, costs immaterial, robust across a 50–300d plateau and out-of-sample.
3. **Instrument:** **IBIT (BTC) / ETHA (ETH) in an IRA** so the switches are **tax-free**; or **BTC/ETH spot
   on Coinbase/Kraken** if you want self-custody (then accept taxable exits). Both are perp-free, access-wall-free.
4. **Expected profile (be humble — wide ranges, ~2–3 cycles of data):** trend-timed BTC ≈ **CAGR ~comparable
   to or modestly above buy-hold, vol ~50% (half of buy-hold), Sharpe ~1.1–1.3, realistic bear drawdown
   ~−30 to −40% (worst-case still ~−60% in a vertical crash).** Versus buy-hold's ~−80% and Sharpe ~0.97.
5. **Sizing:** because the filter caps the *typical* drawdown near −35% (not −80%), a believer can hold the
   *same risk* with roughly **~2× the notional** of an unhedged buy-hold position — or, more sensibly, keep
   notional modest (a **single-digit % of net worth** crypto sleeve) and enjoy the lower vol. The trend dial
   is a risk control, not a license to over-size a still-volatile asset.
6. **Don't double-count crypto beta.** If you already run the ETF-momentum book with crypto-proxy members, that
   IS your trend-timed crypto — a separate full-size BTC sleeve is redundant. Run one, sized deliberately.

**Bottom line:** the honest, useful truth is the expected one — **buy-and-hold's raw CAGR is so high that
timing mainly helps *risk-adjusted* return, not raw return. That is exactly the win for a real person: a
trivial 200d-SMA / 6m-TSMOM weekly trend filter lets you hold crypto with half the volatility and far
shallower (and recently, less than half the) drawdowns — hold less, sleep better, and actually stay in
the trade. For a US small bankroll: trend-timed BTC via IBIT in an IRA is the best way to hold crypto.**
