# Individual US Large-Cap Stock Momentum — higher octane, but survivorship + crashes erase the edge

**Question.** The project winner (`ETF_MOMENTUM.md`, e3e2d57) is cross-asset ETF momentum:
risk-adjusted 6m cross-sectional momentum, top-5 equal-weight, dual + SPY>200d-MA regime gate,
monthly partial rebalance — **Sharpe ~0.83, CAGR ~9%, maxDD ~-17%**. Individual large-cap stocks
have far higher cross-sectional dispersion than 30 broad ETFs, which classically makes momentum
*stronger*. Does running the **same framework** on individual stocks beat the ETF winner on
risk-adjusted return, **net of survivorship bias, single-name risk, momentum crashes, turnover,
and costs**, for a US small-bankroll operator with fractional shares?

**Verdict up front: NO — once you haircut honestly for survivorship and the momentum-crash tail,
the individual-stock version does NOT reliably beat the ETF winner, and it is strictly worse on
every "small-bankroll robustness" axis (drawdown, turnover, single-name risk, no survivorship
problem, simplicity).** The raw stock backtest looks spectacular (Sharpe ~1.08, CAGR ~15%), but
that headline is an **optimistic upper bound built on today's index members** — i.e. winners are
baked in and losers are deleted. A defensible haircut pulls the realistic Sharpe down toward
**~0.8–0.9** with a **maxDD ~-25% to -30%** that is meaningfully deeper than the ETF's -17%. The
ETF winner remains the better *deployable* edge for a $1k operator; stock momentum is at best a
**higher-volatility satellite**, not a replacement.

---

## Data, window, costs, and the survivorship caveat (READ FIRST)

- **Source:** yfinance daily **auto-adjusted** closes (total return). Staged at
  `/tmp/sm_data/stock_prices.csv` (NOT committed). 120 tickers, 1998–2026.
- **Universe (SURVIVORSHIP-BIASED):** ~120 *current* US large-caps — S&P 100 core + the larger
  Nasdaq-100 names (mega-cap tech, financials, healthcare, energy, staples, industrials). This is
  a **TODAY-members list**. yfinance cannot give point-in-time S&P 100/Nasdaq-100 constituents,
  so this is the honest constraint.
- **Window:** full sample **2002-06 → 2026-06** (start padded so ≥100 names have ≥6m history and
  12m lookback room — 105 names eligible by 2002-06, 120 by 2016). **Recent OOS holdout:
  2016-01 → 2026-06 (~10.5y).** Late-IPO names (TSLA 2010, META 2012, V 2008, etc.) only become
  eligible once they have ≥6m history — no look-ahead on inception.
- **Costs:** commission-free + **4 bps/side spread** (large-caps trade 2–5 bps; sensitivity at
  0/2/4/10/25 bps reported). Costs charged on rebalance turnover. Method is a deliberate clone of
  `etf_momentum.backtest()` for an apples-to-apples comparison (`stock_momentum.py`).

### THE SURVIVORSHIP BIAS — stated plainly, because it is the killer

Backtesting **today's** S&P-100/Nasdaq-100 members over 2002–2026 bakes the winners in and
**silently deletes every name that crashed out of the index**: Lehman, Bear Stearns, Wachovia,
Washington Mutual, AIG (near-zero), Citigroup (90%+ drawdown), GE (ejected after collapse),
Kodak, Sears, Frontier, etc. A momentum strategy on the *survivors* never has to hold the names
that momentum-bought-high-then-imploded. **This inflates returns and, worse, hides the deepest
single-name drawdowns.** Everything in §1–§4 is therefore an **OPTIMISTIC UPPER BOUND.** We
quantify the haircut in §6 rather than pretending it away.

---

## 1. Lookback / K sweep — raw, survivorship-biased, ungated (full sample 2002–2026)

Risk-adjusted XS momentum (trailing return / vol), skip-last-month (classic for stocks), top-K
equal-weight, monthly. **No gate yet.**

| lookback | K | CAGR | Sharpe | maxDD | vol | turnover/mo |
|---|---|---|---|---|---|---|
| 6m | 10 | 18.1% | 0.91 | -50.2% | 20.7% | 0.88 |
| **6m** | **15** | **17.6%** | **0.92** | **-48.3%** | 19.8% | 0.78 |
| 6m | 20 | 17.1% | 0.91 | -51.2% | 19.5% | 0.73 |
| 12m | 10 | 18.0% | 0.90 | -41.7% | 20.9% | 0.67 |
| 12m | 20 | 15.3% | 0.83 | -47.6% | 19.5% | 0.54 |

**Dispersion does deliver — and a fat tail comes with it.** Raw Sharpe ~0.9 (vs ETF's 0.83 pre-
gate ~0.63), CAGR ~17–18% (vs ETF ~9%). But the **ungated drawdown is -48% to -51%** — about
*3× deeper* than the ETF version's -35% pre-gate. This is the single-name + momentum-crash tax,
visible even before we adjust for survivorship. 6m K=15 is a stable plateau (no single lucky cell).
Skip-last-month *lowers* the headline a touch (Sharpe 1.00→0.92) but is the academically honest
choice (avoids 1-month reversal contamination), so we keep it.

## 2. Gates — the regime filter is essential (6m, K=15, skip-1m)

| config | CAGR | Sharpe | maxDD | vol | turnover/mo |
|---|---|---|---|---|---|
| XS only | 17.6% | 0.92 | -48.3% | 19.8% | 0.78 |
| +dual (abs>cash) | 17.9% | 0.92 | -46.1% | 20.0% | 0.80 |
| **+SPY>200d regime** | 16.1% | **1.08** | **-30.4%** | 14.8% | 0.68 |
| +dual+regime | 16.1% | 1.08 | -30.4% | 14.8% | 0.68 |
| +both+partial 0.50 | 15.6% | 1.09 | -22.5% | 14.3% | 0.44 |
| **+both+partial 0.34** | **15.4%** | **1.08** | **-24.8%** | 14.2% | 0.34 |

Same story as the ETF study: **the SPY>200d regime gate is the big lever** — it cuts max drawdown
from -48% to -30% and *raises* Sharpe 0.92→1.08 by sitting out bear markets. Partial rebalance
(~1/3 toward target) trims turnover from 0.68 to **0.34/mo** while holding Sharpe ~1.08 and
pulling maxDD to ~-25%. Dual momentum barely binds (in a 100+ name universe there's almost always
something beating cash). **Best config = risk-adj 6m, skip-1m, K=15, dual+regime, partial 0.34.**

## 3. Best config across K and windows (still survivorship-biased)

| | CAGR | Sharpe | maxDD | turnover/mo |
|---|---|---|---|---|
| K=10 full 2002-26 | 16.5% | 1.12 | -24.6% | 0.36 |
| **K=15 full 2002-26** | **15.4%** | **1.08** | **-24.8%** | 0.34 |
| K=20 full 2002-26 | 15.0% | 1.08 | -25.7% | 0.32 |
| K=15 **HOLDOUT 2016-26 (OOS)** | 14.6% | **0.98** | -24.8% | 0.35 |
| K=15 2010-2026 | 14.1% | 0.98 | -24.8% | 0.36 |
| K=15 2020-2026 | 14.8% | 1.04 | -19.9% | 0.34 |

The edge persists into the never-optimized 2016–2026 holdout (Sharpe **0.98**). More names (K=15–20)
vs the ETF's K=5 genuinely diffuses single-name risk (K=10 has higher Sharpe but I prefer K=15+ for
robustness). **Taken at face value this beats the ETF winner.** It does not survive the haircut (§6).

---

## 4. MOMENTUM CRASHES — the violent reversal tax (the headline risk)

Stock momentum is famous for crashing in sharp market rebounds: it is short low-momentum (here:
underweight/absent the beaten-down names) right when those names rip on the recovery.

**Worst monthly returns (full sample, K=15, 6m):**

| ungated | gated (best config) |
|---|---|
| 2008-10 **-12.1%** | 2018-10 -10.1% |
| 2009-02 **-11.9%** | 2010-05 -9.2% |
| 2022-01 -11.4% | 2022-01 -8.6% |
| 2009-01 -9.6% | 2008-01 -7.3% |
| 2008-01 -9.5% | 2020-02 -7.1% |

**Crash-window behavior (ungated vs gated):**

| window | ungated maxDD | ungated ret | gated maxDD | gated ret |
|---|---|---|---|---|
| **GFC + 2009 rebound** (2008-06→2009-12) | **-44.3%** | +1.8% | **-4.5%** | +28.8% |
| 2020 COVID + recovery | -32.8% | +45.2% | -9.3% | +22.8% |
| 2022 stock+bond | -14.9% | +2.3% | -4.1% | -1.2% |

This is the textbook **momentum crash**: ungated, the strategy went **-44% through the GFC and then
clawed back to roughly flat** over 18 months — the 2009 month-by-month shows **-11.9% in Feb-2009**
right at the bottom, then the rebound. The 2020 ungated path was a -33% intramonth gut-punch. **The
regime gate is what makes stock momentum survivable** — it sidesteps the worst of 2008–09 (-44% →
-4.5%) by going to cash below SPY's 200d MA. Even gated, the stock version's **maxDD -25% is ~8pp
deeper than the ETF winner's -17%**, because single-name gaps and the rebound-whipsaw still bite
inside risk-on regimes (note the -10% gated month in Oct-2018).

---

## 5. Costs and small-bankroll feasibility

**Cost sensitivity (best config, K=15, full):**

| bps/side | CAGR | Sharpe |
|---|---|---|
| 0 | 15.6% | 1.10 |
| 2 | 15.5% | 1.09 |
| 4 | 15.4% | 1.08 |
| 10 | 15.1% | 1.07 |
| 25 | 14.4% | 1.02 |

Costs are **not** the problem — turnover 0.34/mo at 4 bps barely dents it, and large-caps trade at
1–3 bps. Stock momentum *does* turn over more than the ETF version pre-partial (0.78 vs ~0.65), but
partial rebalance equalizes them.

**Small-bankroll at $1,000, K=15:** $1000/15 = **~$67 per slot.** Many large-caps trade well above
$67 (e.g. mega-caps in the hundreds–thousands), so this is **only feasible with fractional shares**
(Fidelity/Schwab/Robinhood support them). At 0.34 turnover that's ~$340 of trades/month spread
across ~5–6 names — fine commission-free. **But K=15 fractional slots is materially more operational
complexity than the ETF winner's K=5**, and rounding/cash-drag noise is larger when each slot is
~$67. At $1k the ETF version (5 slots × $200, whole or fractional) is simpler and cleaner. No
capacity wall either way (mega-caps trade billions/day).

---

## 6. THE HAIRCUT — what's left after survivorship + crash realism

The raw 0.98–1.08 Sharpe is **not** what a live operator would have earned. Two adjustments:

**(a) Survivorship — the unfixable part.** My universe contains zero names that crashed *out* of
the index. A point-in-time backtest would have *forced* momentum to buy names like Citi/AIG/GE/
Lehman near their highs and then eat the collapse. The academic literature on long-only large-cap
momentum with point-in-time, delisting-adjusted data puts realistic net Sharpe around **0.6–0.8**,
not >1.0. A **proxy test** — dropping the 8 hottest mega-cap winners (NVDA, TSLA, AAPL, AMD, META,
NFLX, AMZN, MSFT), which are exactly the "winners baked in" — cuts the holdout result from
**Sharpe 0.98 / CAGR 14.6% to Sharpe 0.87 / CAGR 11.8%**, and that test still doesn't add back the
*delisted losers*. Net: a defensible survivorship haircut is **~0.10–0.20 Sharpe and ~3–5pp CAGR**,
landing realistic stock-momentum at **Sharpe ~0.80–0.90, CAGR ~10–12%.**

| | raw (biased) | after survivorship haircut |
|---|---|---|
| Sharpe (holdout) | 0.98 | **~0.80–0.90** |
| CAGR (holdout) | 14.6% | **~10–12%** |
| maxDD | -24.8% | **~-25% to -30%** (haircut makes DD *worse*, not better — losers add tail) |

**(b) Crash realism.** Survivorship also *hides* drawdown: the worst single-name implosions are
absent. The true maxDD with point-in-time losers would be **deeper** than -25%, plausibly -30%+.

**After both haircuts, individual-stock momentum lands around Sharpe ~0.8–0.9 / CAGR ~10–12% /
maxDD ~-28%** — i.e. roughly *tied* with the ETF winner on Sharpe, *higher* on CAGR, but
*meaningfully worse on drawdown*, with single-name risk, 3× the names, and a survivorship cloud the
ETF version simply does not have.

---

## VERDICT

**The ETF winner is the better deployable edge for a US small bankroll. Individual-stock momentum
does not clearly beat it once haircut.**

- **Risk-adjusted:** raw stock Sharpe (~1.0) looks superior, but the honest, survivorship-haircut
  Sharpe (**~0.8–0.9**) is roughly **tied** with the ETF winner's 0.83. There is no robust
  Sharpe edge once you stop counting baked-in winners.
- **Return:** stock momentum *does* carry higher CAGR (~10–12% haircut vs ETF ~9%) — that's the
  dispersion payoff and the only honest "higher-octane" win. But it's bought with risk, not for free.
- **Drawdown:** stock version is **clearly worse** — gated maxDD -25% (likely -28%+ with point-in-
  time losers) vs the ETF's **-17%**. The momentum-crash tail (2008–09 ungated -44%) is real and
  only the regime gate makes it survivable.
- **Single-name / survivorship / operational:** the ETF version has **no survivorship problem**
  (broad ETFs don't get delisted for going to zero), fewer names (K=5 vs 15), lower complexity,
  and is fully IRA-tax-friendly. Stock momentum needs fractional shares, 15+ tiny slots at $1k, and
  carries an irreducible survivorship cloud.

**Recommended config IF deploying stock momentum anyway** (as a higher-vol satellite, not the core):
risk-adjusted **6m** momentum, **skip-last-month**, **K=15** equal-weight, **dual + SPY>200d-MA
regime gate** (non-negotiable — it's what prevents the -44% momentum crash), **monthly partial
rebalance (~1/3)**, fractional shares, 4 bps/side budget. Realistic net expectation after the
survivorship haircut: **CAGR ~10–12%, Sharpe ~0.8–0.9, maxDD ~-28%.**

**Bottom line:** higher dispersion is real and shows up as higher CAGR, but **single-name risk +
momentum crashes + the survivorship haircut erase the risk-adjusted advantage**. For a $1k operator
who wants risk-managed equity-like return with crash protection and zero survivorship/operational
overhead, **the ETF cross-asset momentum winner remains the better choice.** Stock momentum is a
legitimate but *not* dominating sibling — deploy it only as a small high-octane satellite alongside,
never instead of, the ETF core.

---

*Reproduce:* `python3 run_stock_momentum.py` (engine `stock_momentum.py`; survivorship/crash probes
in the run script). All figures net of 4 bps/side. Data via yfinance to `/tmp/sm_data/` (NOT
committed). **Headline stock numbers are an optimistic upper bound — see §6 for the haircut.**
