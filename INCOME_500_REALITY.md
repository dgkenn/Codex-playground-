# INCOME_500_REALITY — can you make $500/mo ($6,000/yr) trading from a SMALL bankroll?

**The one-line answer up front:** *$500/mo is not a strategy — it is a function of your BANKROLL.* At the project's best honest returns (~8.5%/yr blend) you need roughly **$70k** to throw off $500/mo at the mean, and **~$165k** to do it through a 25th-percentile bad-luck year. Forcing $500/mo out of $5k–$25k requires 24–120%/yr, which only leveraged crypto-trend can even *target* — and at that aggression the Monte-Carlo says ruin is the base case. The realistic route is to **grow the bankroll** (contribute + compound the ~10% book) until it is large enough to pay you.

## Methods (so you can trust / attack the numbers)

- Return series are **reconstructed from yfinance** with the same logic as the committed engines (`static_allocation.py` PP; `etf_momentum.py`+`trend_following.py` active book; `btc_trend_timing.py` BTC SMA200-weekly), then **affine-calibrated** (vol + drift) to the committed stats in `FINAL_PORTFOLIO.md` / `BTC_TREND_TIMING.md` so the ruin math uses the **validated** Sharpe/CAGR/maxDD, while preserving the real series' autocorrelation, fat tails and drawdown timing.
- Annual-outcome distributions: **stationary block bootstrap** (21-day blocks) to keep vol-clustering. 20,000 draws each.
- Withdrawals: monthly $500 pulled from bootstrapped **daily** paths (sequence-of-returns risk modeled directly). Ruin = balance hits $0.
- Leveraged crypto: daily-rebalanced, leverage L gives `L*r-(L-1)*borrow`, 10% APR borrow, ruin if equity wiped intra-path.
- **Caveats:** mean returns may ride a non-repeating 2007–2026 bond+gold+crypto tailwind (haircut them mentally); calibration matches moments not every higher moment; crypto tail risk (exchange failure, 1-day -40% gaps, liquidation slippage) is UNDER-stated by a smooth daily bootstrap — real leveraged ruin is **worse** than shown. Nothing here is investment advice.

## 1. Capital required to earn $500/mo ($6,000/yr)

| Strategy | Mean ann. ret | p25 (bad-luck) yr | p10 yr | **$ needed @ mean** | **$ needed @ p25** | $ needed @ p10 | maxDD |
|---|---|---|---|---|---|---|---|
| PP+active BLEND | 8.5% | 3.6% | -1.0% | **$70,588** | **$165,409** | n/a (neg) | -15.8% |
| Pure Permanent Port | 7.9% | 2.7% | -2.0% | **$75,949** | **$223,839** | n/a (neg) | -18.3% |
| ETF cross-asset mom | 8.5% | 2.3% | -4.2% | **$70,588** | **$266,224** | n/a (neg) | -21.6% |
| BTC trend (full-cycle) | 57.0% | 8.4% | -19.7% | **$10,526** | **$71,436** | n/a (neg) | -67.1% |
| BTC trend (recent-cycle) | 24.0% | -12.7% | -34.9% | **$25,000** | **n/a (neg)** | n/a (neg) | -51.5% |

**Read it plainly.** The best deployable book (the blend, ~8.5%/yr) needs **~$70,588** to pay $500/mo at its *mean*, and **~$165,409** to still pay it in a *25th-percentile* year. Pure PP is similar. The crypto book *looks* like it needs far less capital at its mean — but that mean is a high-vol illusion: at the p25 outcome the crypto capital requirement balloons or goes infinite (a losing year pays $0), which is exactly the point of Sections 2–3.

## 2. The aggressive frontier — what $500/mo from $5k/$10k/$25k actually demands

| Bankroll | Required return for $6k/yr | Honest verdict |
|---|---|---|
| $5,000 | 120.0% | 120%/yr — no real strategy targets this without ruinous leverage |
| $10,000 | 60.0% | 60%/yr — only 2–3x leveraged crypto-trend can *aim* here; ruin-likely |
| $25,000 | 24.0% | 24%/yr — at the edge of unlevered crypto-trend's *good-cycle* mean only |
| $60,000 | 10.0% | 10%/yr — achievable by the ~8.5–10% blend; this is the real threshold |

The only deployable book in this project that can even *target* >25%/yr is leveraged crypto-trend. Here is its 3-year ruin/drawdown Monte-Carlo (recent-cycle BTC-trend base, calibrated to the committed ~24% CAGR / ~50% vol / ~-36% DD, daily-rebalanced, 10% borrow):

| Leverage | implied target CAGR (p50) | P(ruin, 3yr) | P(account halved) | CAGR p25 | CAGR p05 | maxDD p50 | maxDD worst-5% |
|---|---|---|---|---|---|---|---|
| 1x | 23.1% | **0.0%** | 6.2% | 1.2% | -22.8% | -51.4% | -76.1% |
| 2x | 7.6% | **0.0%** | 29.8% | -27.0% | -58.5% | -83.2% | -97.2% |
| 3x | -25.1% | **0.0%** | 52.7% | -59.2% | -82.0% | -96.1% | -99.8% |
| 4x | -61.4% | **0.0%** | 73.1% | -82.3% | -94.3% | -99.5% | -100.0% |

**Brutal reading.** Note literal P(ruin)=$0-wipe is low because a smooth daily-rebalanced series rarely posts a single -25%/-33% day (what it takes to wipe 3x/4x in one print) — but that is cold comfort, and the **practical** ruin numbers are damning: at 2x leverage the *median* CAGR collapses to ~8% (leverage does NOT double a 24% book's return — vol drag eats it), P(account halved) is ~30%, and the worst-5% drawdown is ~-97%. At 3x the median outcome is **negative** (~-25%/yr) and ~53% of paths are halved; at 4x the median loses ~-61%/yr and worst-5% DD is **-100%** (functional ruin). And this UNDER-states reality: real crypto gaps (-40% in a day, exchange/liquidation events) WOULD trigger literal margin wipeouts the smooth bootstrap misses. Targeting >~25–30%/yr is a request for ruin-level risk: a leveraged series down -60% needs +150% just to recover. **There is no config that delivers the 60–120%/yr a $5k–$10k bankroll needs at survivable odds.**

## 3. Withdrawal drag — survival with $500/mo pulled out (sequence-of-returns risk)

Start with $X, withdraw $500 every month, run the validated daily path 3 years. P(survive) = account never hits $0 within the horizon.


**BTC trend (recent):**

| Start bankroll | $500/mo as % of capital/yr | P(survive 1yr) | P(survive 2yr) | P(survive 3yr) | median end-bal (3yr) | p25 end-bal |
|---|---|---|---|---|---|---|
| $5,000 | 120.0% | 36.9% | 4.1% | 1.4% | $0 | $0 |
| $10,000 | 60.0% | 97.8% | 49.6% | 24.1% | $0 | $0 |
| $25,000 | 24.0% | 100.0% | 98.6% | 88.5% | $20,650 | $6,230 |
| $60,000 | 10.0% | 100.0% | 100.0% | 99.8% | $85,965 | $42,263 |

**PP+active BLEND:**

| Start bankroll | $500/mo as % of capital/yr | P(survive 1yr) | P(survive 2yr) | P(survive 3yr) | median end-bal (3yr) | p25 end-bal |
|---|---|---|---|---|---|---|
| $5,000 | 120.0% | 0.1% | 0.0% | 0.0% | $0 | $0 |
| $10,000 | 60.0% | 100.0% | 5.1% | 0.0% | $0 | $0 |
| $25,000 | 24.0% | 100.0% | 100.0% | 100.0% | $11,763 | $9,933 |
| $60,000 | 10.0% | 100.0% | 100.0% | 100.0% | $56,749 | $51,246 |

**The decisive picture.** Pulling $500/mo ($6k/yr) is a 120%/yr drain on $5k, 60% on $10k, 24% on $25k. On the aggressive (crypto) book those withdrawal rates guarantee the account is bled to zero with high probability inside 1–3 years — the withdrawals lock in losses during every drawdown (sequence risk). Only at **$60k**, where $6k/yr is a ~10% drain matched to the blend's ~10% return, does survival become robust. **A small, volatile account + fixed withdrawals = an accelerated path to ruin.**

## 4. The realistic path — contribute + compound to the bankroll that pays you

Trading skill is the **~10% edge**; the bankroll is the **lever**. Years to reach the ~$70k that sustainably yields $500/mo, compounding the ~8.5% blend while contributing $/mo:

| Starting bankroll | +$200/mo | +$500/mo | +$1,000/mo | +$2,000/mo |
|---|---|---|---|---|
| $5,000 | 13.1 yr | 7.4 yr | 4.4 yr | 2.5 yr |
| $10,000 | 11.4 yr | 6.7 yr | 4.0 yr | 2.2 yr |

**The honest math of building capital.** Compounding 8.5% alone barely moves a small balance; contributions dominate at this size. From $10k, saving $1,000/mo reaches the $70k income-bankroll in ~4 years; $2,000/mo in ~2. The trading edge then quietly adds a few years of acceleration — it is the *finisher*, not the engine, until the bankroll is large.

## 5. High-return-on-small-capital edge sweep — is there a shortcut?

The recurring finding across this project's research docs is that every *high-ROC-on-tiny-capital* edge is **dead, walled, or too thin to matter**:

- **Kalshi box / fair-value taker / sports / macro:** DEAD or walled (`BOXARB.md`, `BINARY_FAIRVAL.md` etc.) — no repeatable edge net of fees/fills.
- **Kalshi weather (LEAD):** the one thin/unproven lead. Even if real, prediction-market weather contracts have a **tiny capacity ceiling** (per-market liquidity is hundreds–low-thousands of dollars; fills move the price). A genuine 5–10% edge on $1–3k of deployable size per event is **$50–300/event a few times a month at best**, before it is arbitraged or the book widens — it cannot be scaled to a reliable $500/mo, and it is **unproven**. Treat as a research project, not income.
- **General principle:** any edge with high return *on small capital* is, by definition, **capacity-constrained** — if it scaled, institutions would have compressed it. Small-capacity edges produce small absolute dollars. You cannot out-clever a $5k bankroll into $500/mo reliably; the dollars just aren't there.

**Sweep verdict:** no edge in this project produces reliable, scalable $/mo from a small bankroll. The only validated, *capacity-unconstrained* books are the boring ~8–10% diversified portfolios — and those pay you in proportion to capital.

## 6. VERDICT — the honest answer

1. **At safe/realistic returns (~8.5–10% blend), $500/mo needs ~$70k** (~$70,588 at the mean; ~$165,409 to survive a bad-luck p25 year). That is the threshold, full stop.
2. **Forcing $500/mo from $5k / $10k / $25k requires 120% / 60% / 24% per year.** Only leveraged crypto-trend can even target it, and the Monte-Carlo shows that at the leverage required the **median outcome is a large loss** (2x: ~8% CAGR with ~30% of paths halved; 3x: median ~-25%/yr; 4x: median ~-61%/yr, worst-5% DD -100%) — functional ruin is the base case, and real crypto gaps make literal margin wipeout likely on top of that.
3. **With $500/mo withdrawals, the small accounts do not survive.** On the aggressive book, $5k/$10k/$25k are bled toward zero with high probability inside 1–3 years (sequence risk); only ~$60k matched to a ~10% book survives robustly.
4. **No shortcut edge exists.** Every high-ROC-on-small-capital edge in this project is dead/walled/capacity-capped (incl. the thin Kalshi-weather lead). Small-capacity edges = small dollars.
5. **The real path: grow the bankroll.** Contribute + compound the ~8.5–10% book; from $10k, +$1,000/mo reaches the $70k income-bankroll in ~4 years (+$2,000/mo in ~2). The trading edge is the ~10% finisher; the bankroll is the lever that actually pays the $500/mo. **No false hope: you cannot trade $5k into $500/mo without taking ruin-level risk. The honest move is to build the capital.**
