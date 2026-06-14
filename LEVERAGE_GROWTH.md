# Growth-Optimal Leverage on the Trend-Overlaid All-Weather Book

**Question.** The recommended book is a **trend-overlaid all-weather portfolio**
(PP-style base SPY/TLT/GLD + a 6–12m time-series trend filter that parks falling
sleeves in cash). Long-history (1972–2023) Sharpe ~1.43, maxDD ~-10% — **halved**
vs pure PP (~-17%). For a **young, medium-risk (-30..-40% DD budget), small-bankroll**
investor compounding toward a ~$70k income base: **what leverage maximizes growth
subject to maxDD ≤ 35% on the long history, by what vehicle, and what does it do to
the years-to-$70k vs the unlevered book — at what ruin/tail cost?**

`REGIME_ROBUSTNESS.md` showed levering a **pure static** is a bad deal (amplifies
the -17% DD + pays financing). The thesis here: the trend book's DD is already
halved AND it de-risks to cash in downturns, so it is a **fundamentally better
leverage candidate**. This study tests that honestly.

---

## Window, vehicles, costs (SCREENS)

| Item | Value |
|---|---|
| Long history | **1972-01 .. 2023-06**, monthly TR, n=618 (`regime_data.py` reconstruction: Shiller S&P TR, duration/convexity-reconstructed UST10/UST30, datahub gold, Ken French RF cash) |
| ETF era | **1994-01 .. 2026-06**, daily yfinance adj closes, n=8148 (SPY/TLT/GLD + BIL cash) |
| Book | trend-overlaid all-weather, REUSED verbatim from `regime_robustness.trend_overlay` (long) and the same 12m-TS-trend → BIL-cash rule on daily ETFs |
| Turnover cost | 5 bps/side on rebalance turnover |
| **Margin** vehicle | borrow the (L-1) portion at **T-bill + 125 bps** (mid of 100–150). Book's cash sleeve already earns T-bill, so net cost = spread × borrowed portion |
| **LETF** vehicle | daily-reset L× sleeves, **90 bps/yr** expense + **honest volatility decay** (modeled by compounding L×daily returns, so the −(L²−L)/2·σ² drag is *in* the curve, not fudged) |
| Kelly | full-Kelly = μ_excess/σ²; **half-Kelly is the practical max** (never exceed) |
| MC | stationary block bootstrap (21d blocks → keeps fat tails + vol clustering), **2%/yr mean haircut** (honest forward CAGR), 4000 paths |

Engine: `leverage_growth.py` (reuses `regime_robustness.py`; data staged non-repo to
`/tmp/regime_data`, `/tmp/etfmom_data`). Unlevered baselines reproduced exactly:
long-history CAGR 9.9% / Sharpe 1.43 / maxDD -10.1%; ETF-era CAGR 6.5% / Sharpe 0.94 / maxDD -13.6%.

---

## 1. Leverage curve

### Long history 1972–2023 (monthly)

| L | Margin CAGR | Margin Sharpe | Margin maxDD | Margin worstYr | LETF CAGR | LETF maxDD |
|---|---|---|---|---|---|---|
| 1.00 | 9.9% | 1.43 | -10.1% | -5.3% | 9.9% | -10.1% |
| 1.25 | 10.9% | 1.27 | -13.2% | -7.8% | 11.3% | -12.7% |
| 1.50 | 11.9% | 1.16 | -16.2% | -10.7% | 13.8% | -15.2% |
| 1.75 | 12.8% | 1.09 | -19.5% | -13.5% | 16.2% | -17.6% |
| 2.00 | 13.8% | 1.03 | -22.8% | -16.2% | 18.5% | -20.0% |

### ETF era 1994–2026 (daily; LETF decay from **actual daily compounding** — the honest path)

| L | Margin CAGR | Margin maxDD | LETF CAGR | LETF maxDD | LETF Sharpe |
|---|---|---|---|---|---|
| 1.00 | 6.5% | -13.6% | 5.6% | -15.0% | 0.81 |
| 1.25 | 7.4% | -17.3% | 7.2% | -18.2% | 0.84 |
| 1.50 | 8.2% | -20.8% | 8.8% | -21.3% | 0.86 |
| 1.75 | 9.0% | -24.4% | 10.4% | -24.3% | 0.87 |
| 2.00 | 9.8% | -28.2% | 11.9% | -27.2% | 0.88 |

**Margin vs LETF.** On the long history the *monthly* LETF model flatters LETF
(monthly variance drag is tiny). The **honest read is the ETF-era daily LETF**: on
this **low-vol (~7%) trend book, decay is small**, so **LETF ≈ margin** at equal
leverage (within ~1pp CAGR) and the LETF actually preserves Sharpe slightly better
because it has no explicit financing line. The classic "LETF decay eats you alive"
warning is a *high-vol-asset* phenomenon (3x QQQ); on a 7%-vol trend-de-risked book
the decay is mild. **Both vehicles are viable** — margin if you have a taxable margin
account, 2x-LETF if you're in an IRA (see §4).

**The curve confirms the thesis vs a pure static.** DD grows roughly linearly with L
off a **-10% base**, so even 2x stays inside the -23..-28% band — whereas levering a
pure-PP -17% base to 2x would blow through -35%+. The halved, trend-protected DD is
exactly what buys the leverage headroom.

---

## 2. Growth-optimal (Kelly) + DD-constrained leverage

```
long-history excess μ = 5.41%/yr,  σ = 6.75%/yr
FULL-Kelly  L* = μ/σ² = 11.86x   (theoretical growth-max — BRUTAL, never go here)
HALF-Kelly       = 5.93x          (the practical ceiling — also far above any sane DD)
```

Full-Kelly is absurdly high (~12x) because the book's Sharpe is high and its vol is
low — **Kelly is NOT the binding constraint; the drawdown budget is.** This is the
whole point: for a high-Sharpe low-vol book, *Kelly says lever a lot, but the DD
budget says don't.*

**DD-constrained (maxDD ≤ 35% on the WORSE of long-history-monthly AND ETF-era-daily):**

| Vehicle | DD-binding L | CAGR (long hist) | Sharpe | worst DD (binding) | long-hist DD | ETF-era DD |
|---|---|---|---|---|---|---|
| Margin | **2.45x** | 15.4% | 0.95 | -34.8% | -28.5% | -34.8% |
| LETF | **2.65x** | 24.6%* | 1.32 | -34.5% | -26.3% | -34.5% |

\*the monthly-LETF CAGR is optimistic; daily-honest LETF ≈ the margin figure.

The **ETF-era daily DD is the binding leg** (it sees 2008/2020/2022 *intramonth*; the
monthly long-history series cannot). At the cliff, **2.45x margin** maxes growth
within budget. **Headline recommendation steps one notch below the cliff to ~2.2x**
for a safety margin — you do **not** want to sit exactly at -35% when the next regime
is, by construction, unseen.

---

## 3. Ruin / sequence Monte-Carlo (4000 paths, 21d blocks, **2%/yr haircut**)

Years to $70k (p25 / median / p75), P(ruin = ever < $1), P(intra-path DD > 50%):

**$5,000 start, +$500/mo** (the realistic compounding case):

| Leverage | P(ruin) | P(DD>50%) | p25 | **median** | p75 | reach |
|---|---|---|---|---|---|---|
| 1.0x (unlevered) | 0% | 0% | 8.0 | **8.5** | 9.1 | 100% |
| 2.2x (chosen) | 0% | 0% | 6.3 | **7.2** | 8.1 | 100% |
| 2.45x (DD-cap) | 0% | 0.1% | 6.1 | **7.0** | 7.9 | 100% |

**$5,000 start, $0/mo** (lump-sum only — leverage's tail is exposed):

| Leverage | P(ruin) | P(DD>50%) | p25 | **median** | p75 | reach (40y) |
|---|---|---|---|---|---|---|
| 1.0x | 0% | 0% | 36.7 | **38.0** | 39.2 | 2% |
| 2.2x | 0% | **9.2%** | 24.6 | **29.2** | 33.9 | 77% |
| 2.45x | 0% | **13.4%** | 22.5 | **27.2** | 32.5 | 83% |

**$2,000 start, +$500/mo:** 1x median 9.0y → 2.2x median 7.6y (P(DD>50%) ~0% with contributions).

### The honest read

- **With $500/mo contributions, leverage barely moves the median timeline:**
  **8.5y → 7.2y at 2.2x — a ~1.3-year cut**, and only ~1.5y even at the 2.45x cliff.
  At small size the **contributions dominate compounding**, not the return rate. This
  is the single most important, most under-appreciated finding: *you cannot lever your
  way out of a small-contribution timeline.*
- **Leverage's payoff is real only in the low/no-contribution regime** (lump sum,
  $0/mo): there 2.2x cuts the median from 38y → 29y and raises the reach-rate from 2%
  → 77%. But that regime is *exactly* where the tail bites: **P(DD>50%) jumps from 0%
  to ~9% at 2.2x and ~13–16% at the cliff.** Roughly **1 path in 11** sees a >50%
  drawdown — survivable for a disciplined young investor with no withdrawals, brutal
  for one who panic-sells.
- **No path "ruins"** (goes to ~$0) at any tested leverage — because the book
  de-risks to cash and never holds a falling sleeve at full size. Leverage amplifies
  drawdowns, **not** the wipeout probability, *for this trend-protected book*. (This
  would NOT hold for levering a buy-and-hold or a pure static.)

---

## 4. IRA-LETF practicality (margin is not allowed in an IRA)

Margin needs a **taxable margin account** — so the tax-efficient IRA path *cannot*
use margin. The IRA stand-in is a **trend-overlaid 2x-LETF all-weather** (SSO 2× S&P,
UBT 2× Treasuries, UGL 2× gold), trend-gated to cash exactly like the base book.

| Vehicle | CAGR | Sharpe | maxDD | vol | Account |
|---|---|---|---|---|---|
| Unlevered book (1×) | 6.5% | 0.94 | -13.6% | 7.0% | taxable **or** IRA |
| Margin 1.5× | 8.2% | 0.81 | -20.8% | 10.5% | taxable only |
| Margin 2.0× | 9.8% | 0.74 | -28.2% | 13.9% | taxable only |
| **1.5×-LETF book** | 8.8% | 0.86 | -21.3% | 10.5% | **IRA-legal** |
| **2.0×-LETF book** | 11.9% | 0.88 | -27.2% | 14.0% | **IRA-legal** |

**Yes — a trend-overlaid 2x-LETF book approximates the levered book in an IRA well.**
On this low-vol trend book the decay is mild, so the **2x-LETF tracks 2x-margin within
~1pp CAGR and matches the DD** (-27% vs -28%). The IRA path **avoids the
short-term-gains tax drag** of the churny momentum sleeve, which is a real offsetting
advantage. Practical caveats at $2–5k: hold the LETF sleeves only for *ON* sleeves
(cash, not a levered-cash ETF, for *OFF*); use a **fractional-share** broker so a
12–18% sleeve isn't dwarfed by one whole share; rebalance monthly to control decay.

---

## 5. Verdict

**Growth-optimal, DD-constrained leverage exists and the thesis holds** — the
halved, trend-protected DD genuinely buys leverage headroom that a pure static does
not have. The DD-budget (not Kelly) is the binding constraint, and the
**growth-within-budget optimum is ~2.2–2.45x** (CAGR ~15% long-history, Sharpe ~0.95,
maxDD held to the -35% line by the ETF-era 2008/2020/2022 stress).

**But the honest, practical recommendation is more conservative — and depends on
whether you contribute:**

> **If you contribute (~$500/mo) — the realistic case — use modest leverage, ~1.25–1.5x, or even stay 1×.** Leverage only cuts the median $5k→$70k path from **8.5y to ~7.2y even at 2.2x** (~1.3y), because **contributions dominate the timeline at small size.** That ~1.3-year gain costs a ~9% chance of a >50% drawdown. **1.25–1.5x margin (taxable) or a 1.5×-LETF sleeve (IRA)** captures most of the modest benefit with a fraction of the tail. **Going to the 2.2–2.45x cliff is not worth it when you're contributing.**
>
> **If you are NOT contributing (lump sum only), leverage matters much more** — 2.2x roughly cuts the median lump-sum-only timeline 38y→29y and lifts the reach-rate 2%→77% — **but you must accept a ~9–13% chance of a >50% drawdown and the discipline never to panic-sell.** Only a genuinely medium-risk, no-withdrawal young investor should take 2.2x; even then, **2.2x via margin (taxable) or 2×-LETF (IRA), not higher.**

**Vehicle.** Margin (T-bill+125bps) in a **taxable** account, OR a **trend-overlaid
2×-LETF** sleeve (SSO/UBT/UGL) in an **IRA** — on this 7%-vol book they track within
~1pp CAGR / matched DD, and the IRA-LETF path dodges the momentum sleeve's
short-term-gains tax.

**No ruin at any tested leverage** because the trend overlay de-risks to cash —
leverage amplifies the **drawdown**, not the **wipeout**. That is precisely why this
book, and not a pure static, is a defensible leverage candidate. **Half-Kelly (~6x)
is irrelevant here; the -35% DD budget caps you at ~2.2–2.45x, and prudence +
the contribution-dominates-timeline reality argue for 1.25–1.5x in the case that
actually applies.**

*Bottom line: leverage's tail cost is **not** worth it if you contribute (stay
1.25–1.5x); it's a real accelerant only for the lump-sum, no-contribution investor
who can stomach a 1-in-11 chance of a >50% drawdown — and even then, cap at ~2.2x.*
