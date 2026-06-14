# Combined Two-Sleeve Deployable Portfolio — the convergent book

**Question.** This project converged on two independently validated, deployable, US-legal,
small-bankroll sleeves:

- **Sleeve A** = cross-asset **ETF cross-sectional momentum** (`ETF_MOMENTUM.md` e3e2d57 /
  `etf_momentum.py`): ~30-ETF universe, 6m risk-adjusted XS momentum, top-5 EW, dual/absolute
  (>cash) + SPY>200d gate, monthly partial-rebalance (~1/3). **Standalone Sharpe ~0.83, maxDD ~-17%.**
- **Sleeve B** = inverse-ETF **time-series trend-following** (`TREND_FOLLOWING.md` 0350194 /
  `trend_following.py`): 6m TS trend, inverse ETFs (SH/PSQ/…) for short-in-downtrend, ~10% vol
  target, monthly. **Standalone Sharpe ~0.66** — its value is **crisis alpha** (+16.9% in 2008,
  -0.04 corr to SPY, **0.43 corr to Sleeve A**).

This document **builds and optimizes the COMBINED book**, tests optional satellites, produces the
combined outcome distribution + sizing, and ships a unified live harness (`portfolio_live.py`).
The sleeves' code/configs are **reused, not re-derived**.

**VERDICT up front: the locked book is 70% A / 30% B (inverse), NO satellites.** It beats
momentum-alone on **both** axes, net of costs, in-sample AND out-of-sample:

| book | window | CAGR | Sharpe | maxDD |
|---|---|---|---|---|
| Momentum-alone (A) | full 2007-2026 | 7.9% | 0.743 | -15.6% |
| **Combined 70/30** | full 2007-2026 | 8.3% | **0.808** | **-13.6%** |
| Momentum-alone (A) | **OOS holdout 2016-2026** | 8.9% | 0.809 | -15.6% |
| **Combined 70/30** | **OOS holdout 2016-2026** | 9.4% | **0.910** | **-12.6%** |

Sharpe +0.065 (full) / +0.10 (OOS), maxDD cut ~13-19%. The combo is **insurance-flavored**: it
drags in calm bulls (the inverse leg pays decay) and earns its keep in crashes. It is *not* a
return-maximizer vs a US-equity bull — that trade-off is accepted by design.

---

## Data, window, costs (SCREENS)

- **Source:** yfinance daily **adjusted** closes (`auto_adjust=True` => total return). Staged to
  the NON-repo paths the sleeve engines expect: long ETFs `/tmp/etfmom_data/etf_prices.csv`,
  inverse ETFs `/tmp/tf_data/inverse_etfs.csv`, vol-premium proxies `/tmp/vp_data/`. Fetched via
  `fetch_pf.py` (retry/backoff). Long file: 35 cols, 1993→2026-06-12. Inverse: 8 cols, 2006-06→.
- **Window:** **overlap 2007-06 → 2026-06** (UUP / inverse-ETF binder; covers 2008 GFC, 2020 COVID,
  2022). **Recent-decade OOS holdout 2016-01 → 2026-06** (never optimized on).
- **Costs:** **3 bps/side** of traded notional on both sleeves (commission-free ETFs). Sleeve B's
  **inverse-ETF expense/decay drag is already inside the inverse adjusted prices** (the prior work
  confirmed ~0.25 standalone Sharpe of structural cost via a synthetic-short cross-check). All
  figures below are **NET**.
- **Sleeve reproduction (verified before optimizing):** A full Sharpe 0.828 / maxDD -17.6%; A
  holdout 0.809 / -15.6%; A over the 2007-overlap 0.743 / -15.6%; B-inverse full 0.655 / -21.9%;
  B-cash full 0.908 / -23.8% — **all match the committed docs exactly.**
- **Reproduce:** `python3 run_portfolio_combined.py` (engine `portfolio_combined.py`, reuses
  `etf_momentum.py` + `trend_following.py`). Live target: `python3 portfolio_live.py`.

---

## 1. Combination sweep (A = XS-momentum, B = TF-INVERSE diversifier)

Both legs rebalanced monthly to target weight; drift within month. Net of 3 bps/side.

**FULL OVERLAP 2007-2026:**

| book | CAGR | Sharpe | maxDD | vol |
|---|---|---|---|---|
| A alone (100/0) | 7.9% | 0.743 | -15.6% | 11.1% |
| B-inv alone (0/100) | 8.7% | 0.655 | -21.9% | 14.3% |
| 85/15 | 8.2% | 0.787 | -14.1% | 10.7% |
| **70/30** | 8.3% | **0.808** | **-13.6%** | 10.6% |
| 60/40 | 8.4% | 0.807 | -13.8% | 10.7% |
| 50/50 | 8.5% | 0.795 | -14.0% | 11.0% |
| risk-parity / inverse-vol (0.56/0.44) | 8.5% | 0.804 | -13.8% | 10.8% |
| 70/30 vol-targeted to 10% | 7.9% | 0.799 | -14.1% | 10.1% |

**OOS HOLDOUT 2016-2026:**

| book | CAGR | Sharpe | maxDD | vol |
|---|---|---|---|---|
| A alone | 8.9% | 0.809 | -15.6% | 11.3% |
| 85/15 | 9.2% | 0.870 | -14.1% | 10.8% |
| **70/30** | 9.4% | **0.910** | **-12.6%** | 10.5% |
| 60/40 | 9.6% | 0.921 | -11.6% | 10.6% |
| 50/50 | 9.8% | 0.920 | -11.7% | 10.8% |
| risk-parity (0.54/0.46) | 9.7% | 0.922 | -11.3% | 10.7% |

**Contrast — B = TF-CASH (the wrong leg):** at 70/30, full-sample Sharpe is higher (0.833) but
**maxDD *rises* to -17.6%** (worse than A-alone) because cash-TF is 0.78-correlated to A and cannot
be net-short. It fails the brief. **Use inverse.** (Matches `TREND_FOLLOWING.md` §5.)

## 2. Robust weight plateau (not a single in-sample spike)

Fine grid of wA, Sharpe & maxDD on both windows (B = inverse):

| wA | full Sharpe | full maxDD | holdout Sharpe | holdout maxDD |
|---|---|---|---|---|
| 1.00 | 0.743 | -15.6% | 0.809 | -15.6% |
| 0.85 | 0.787 | -14.1% | 0.870 | -14.1% |
| 0.80 | 0.797 | -13.6% | 0.886 | -13.6% |
| 0.75 | 0.804 | -13.5% | 0.900 | -13.1% |
| **0.70** | **0.808** | **-13.6%** | **0.910** | -12.6% |
| 0.65 | 0.809 | -13.7% | 0.917 | -12.1% |
| 0.60 | 0.807 | -13.8% | 0.921 | -11.6% |
| 0.55 | 0.802 | -13.9% | 0.922 | -11.3% |
| 0.50 | 0.795 | -14.0% | 0.920 | -11.7% |
| 0.40 | 0.774 | -15.6% | 0.907 | -12.7% |

**This is a plateau, not a spike.** Full-sample Sharpe is flat at 0.80-0.81 across the **entire
wA 0.55-0.80 band**; maxDD bottoms (~-13.5%) at wA 0.70-0.80. The holdout pushes the Sharpe-max a
touch lower (wA~0.55-0.60) and the DD-min lower still (more inverse = more crash protection in the
COVID-heavy decade), but every cell in 0.55-0.75 dominates A-alone on both axes. **70/30 is the
robust pick**: it sits dead-center on the full-sample Sharpe/DD plateau, is the most defensible
ex-ante (more of the higher-Sharpe sleeve, enough of the diversifier to cut DD), and matches the
prior committed combo — **confirming the ~70/30**. Risk-parity (~0.55/0.45) is a near-identical
alternative; vol-targeting the combo adds nothing (it just shaves return for the same Sharpe).

## 3. Optional satellites — do they EARN a place? (No.)

### 3a. PUTW vol-premium slice (VOL_PREMIUM.md: ≤20-30% of equity, shares the crash tail)

Carving a PUTW slice out of sleeve A's share, B held at 30% (ETF-era 2016+, and a full-history
^PUT-index cross-check):

| book (2016+) | CAGR | Sharpe | maxDD |
|---|---|---|---|
| 70/30 no satellite | 9.6% | 0.916 | **-12.6%** |
| A0.60 / B0.30 / PUTW0.10 | 9.5% | 0.936 | -13.8% |
| A0.50 / B0.30 / PUTW0.20 | 9.5% | 0.950 | -15.0% |
| A0.40 / B0.30 / PUTW0.30 | 9.4% | 0.956 | -16.2% |

PUTW raises **Sharpe** but **monotonically worsens maxDD** (-12.6% → -13.8% → -16.2%) and barely
moves CAGR. This is exactly the VOL_PREMIUM.md warning: put-writing **shares the equity crash
tail** — it adds left-tail risk that the inverse-TF leg was specifically chosen to *remove*. The
full-history ^PUT check shows the same pattern (0.808→0.851 Sharpe, -13.6%→-14.9% DD at 20%). It
improves only ONE axis and degrades the very thing the book is built for. **Excluded.**

### 3b. High-octane stock momentum (STOCK_MOMENTUM.md: survivorship-biased, -28% DD)

Stock-momentum is survivorship-biased (today's-members universe). Raw it looks great (Sharpe 1.14,
CAGR 17%) but that is an optimistic upper bound; after a 30% drift haircut it is Sharpe 0.80, maxDD
**-25.5%**. Added to the combo:

| book (2016+, 30% haircut) | CAGR | Sharpe | maxDD |
|---|---|---|---|
| 70/30 no satellite | 9.4% | 0.910 | **-12.6%** |
| A0.60 / B0.30 / STK0.10 | 9.7% | 0.928 | -13.6% |
| A0.50 / B0.30 / STK0.20 | 10.0% | 0.940 | -14.5% |

Even haircut, stock-momentum **adds drawdown** (-12.6% → -14.5%) and concentration/single-name risk
for a marginal Sharpe bump that rests on a survivorship-flattered series. It raises CAGR but breaks
the low-drawdown mandate and adds real operational complexity (120-name universe, delisting risk).
**Excluded** — keep only what earns it on BOTH axes.

**Satellite verdict: neither earns a place. The locked book is the clean 2-sleeve 70/30.** Both
satellites improve Sharpe a little while *worsening* the drawdown — the opposite of this book's
purpose. Simplicity + lower DD wins.

## 4. Combined outcome distribution (block-bootstrap, 30% drift haircut)

Block-bootstrap (21-day blocks) of the locked 70/30 daily series, **drift haircut 30%** (keep
vol/shape), 5,000 paths/horizon. Compared to momentum-alone — **the combined drawdown is tighter
on every metric.**

**COMBINED 70/30:**

| horizon | $1k: p5 / median / p95 | $10k: p5 / median / p95 | P(maxDD>20%) | P(maxDD>30%) | time-underwater | P(<start) |
|---|---|---|---|---|---|---|
| 1yr | $919 / $1,057 / $1,224 | $9,195 / $10,572 / $12,242 | 0.8% | 0.0% | 33.0% | 25.6% |
| **2yr** | **$911 / $1,119 / $1,373** | **$9,106 / $11,188 / $13,734** | **4.5%** | **0.1%** | 27.1% | **18.4%** |
| 3yr | $919 / $1,180 / $1,514 | $9,190 / $11,802 / $15,144 | 9.0% | 0.5% | 23.8% | 13.8% |

**MOMENTUM-ALONE (sleeve A):**

| horizon | $1k: p5 / median / p95 | P(maxDD>20%) | P(maxDD>30%) | P(<start) |
|---|---|---|---|---|
| 1yr | $907 / $1,056 / $1,231 | 1.9% | 0.0% | 28.0% |
| 2yr | $892 / $1,114 / $1,383 | 7.6% | 0.3% | 20.7% |
| 3yr | $900 / $1,170 / $1,521 | 13.7% | 0.8% | 15.9% |

The combo's **P(maxDD>20%) is roughly half** momentum-alone's at every horizon (2yr: 4.5% vs 7.6%;
3yr: 9.0% vs 13.7%), the p5 floor is higher, and P(below-start) is lower — **the drawdown is
tighter, exactly as intended.** Both books have **P(< SPY @2yr) ≈ 70-73%** (combo 69.7%, A-alone
73.1%): like SPY-relative, this is a risk-managed book that usually trails a bull-market index on
raw return while protecting the downside — the honest framing.

## 5. Crisis windows (locked 70/30 vs A-alone vs SPY)

| crisis | combo 70/30 | A-alone | SPY |
|---|---|---|---|
| 2008 GFC (Sep08-Mar09) | **+2.7%** | -0.1% | -36.9% |
| 2008 full year | **+5.2%** | +0.2% | -36.8% |
| 2020 COVID (Feb-Mar) | **-11.5%** | -14.9% | -33.4% |
| 2022 stocks+bonds | **+0.5%** | -1.5% | -18.2% |

The inverse-TF sleeve turns A's "merely flat in 2008" into "**+5% in 2008**", improves the COVID
drawdown (-11.5% vs -14.9%), and keeps 2022 positive. That is the crisis alpha the 0.43-correlation
sleeve was added for. **Honest caveat:** monthly trend-following whipsaws in fast V-reversals — the
inverse leg still took -11.5% in the COVID crash-and-snap-back (better than A-alone but not flat),
and in calm bulls (the 2016-2026 inverse leg) it pays decay. This is insurance, not free.

---

## 6. UNIFIED DEPLOYMENT

### 6a. Current live combined target (run 2026-06-12, real yfinance data)

`python3 portfolio_live.py --capital 10000` (regime gate ON: SPY 741.75 > 200d 684.07;
sleeve B: 8 long / 2 inverse, gross 1.12x). **Portfolio-level weights = 0.70·A + 0.30·B:**

| ticker | weight | sleeve(s) |
|---|---|---|
| DBC | 17.3% | A-mom + B-long |
| USO | 17.3% | A-mom + B-long |
| VNQ | 17.3% | A-mom + B-long |
| XLB | 14.0% | A-mom |
| XLE | 14.0% | A-mom |
| SPY | 3.3% | B-long |
| QQQ | 3.3% | B-long |
| EFA | 3.3% | B-long |
| EEM | 3.3% | B-long |
| UUP | 3.3% | B-long |
| TBT | 3.3% | B-inverse (short long-bonds: TLT downtrend) |
| GLL | 3.3% | B-inverse (short gold: GLD downtrend) |
| BIL / CASH | 3.3% | A+B residual |

Invested (risk) weight ≈ 103.5% — sleeve B's vol-target levers its 30% share slightly (gross
1.12x, capped at 2x). Sleeve A is currently in the **commodity/energy/materials** complex (DBC, USO,
XLE, XLB) plus REITs (VNQ) — the trending real-asset rotation. The inverse legs (TBT, GLL) reflect
TLT and GLD being in 6m downtrends. The script also prints the full whole-share trade list and a
`--paper-track` JSONL of combined paper equity (tested end-to-end; idempotent per month).

### 6b. Monthly operating runbook

1. **Once a month** (last trading day, or a fixed day each month), run
   `python3 portfolio_live.py --capital <acct> --holdings holdings.json --paper-track`.
2. Read the **combined target** + trade list. Place the BUY/SELL ETF trades manually in any
   commission-free brokerage (Fidelity/Schwab/Vanguard). Round to whole shares (or use fractional);
   rounding noise is small. Inverse ETFs (SH/PSQ/EFZ/EUM/TBT/GLL/DUG/RWM) appear **only** via
   sleeve B's short-in-downtrend leg.
3. **Regime gate:** if the report says SPY<200d → sleeve A goes 100% cash (only sleeve B trades).
4. Update `holdings.json` with your actual post-trade $ positions for next month's diff.
5. **Tax:** run in an **IRA** if possible — monthly turnover + the inverse-leg flips generate
   short-term activity; an IRA zeroes the tax drag. Combined turnover ≈ A's 0.31 + B's 0.54 share
   ≈ ~0.4-0.5/mo (a handful of small ETF trades).
6. Keep the paper-track JSONL accumulating; review rolling Sharpe at each run.

### 6c. Sizing (%-of-net-worth, off the combined maxDD)

The combined book's worst historical drawdown is **~-13.6%** (full sample) / ~-12.6% (OOS); the
bootstrap puts P(maxDD>20%) at 4.5% (2yr) and a ~0.1% tail beyond -30%. **Plan for a -20% worst
case** (1.5× the historical -13.6%, for live slippage + an unseen crash). To cap **whole-net-worth**
drawdown from this book at a tolerance `T`:

> **allocation = T / 0.20.**

- Conservative (cap book contribution to NW drawdown at **-5%**): allocate **~25%** of net worth.
- Moderate (cap at **-8%**): allocate **~40%**.
- Aggressive (cap at **-12%**): allocate **~60%** (this book *is* the risk-managed equity sleeve).
- Hold the remainder in T-bills/cash/short bonds. At **$1k** the K=5 + TF legs are fine with
  fractional shares; at **$10k-$100k** zero capacity issue (these ETFs trade billions/day).

### 6d. Go-live bar

**Do NOT deploy real capital until the paper track clears the bar:** run `portfolio_live.py
--paper-track` monthly and require a **rolling paper Sharpe ≥ 0.70 over 3-6 months** of forward
paper trading, with realized drawdown behavior consistent with the backtest (no >-15% paper DD in a
non-crisis month). If the paper book whipsaws badly in a calm market (a known inverse-ETF failure
mode), pause and re-examine before sizing up. Start at the **conservative 25%** allocation and step
up only after 6+ clean paper months.

---

## VERDICT

**Locked combined book: 70% Sleeve A (ETF cross-sectional momentum) / 30% Sleeve B (inverse-ETF
trend-following), monthly rebalanced, NO satellites.** Chosen on a robust Sharpe+drawdown plateau
(flat across wA 0.55-0.80), not an in-sample spike; confirms the prior ~70/30.

- **Net vs momentum-alone:** Sharpe **0.743 → 0.808** (full) and **0.809 → 0.910** (OOS holdout);
  maxDD **-15.6% → -13.6%** (full) / **-12.6%** (OOS); CAGR ~8.3% / 9.4% — beats A-alone on **both**
  axes in-sample AND out-of-sample, justifying the extra sleeve.
- **Crisis alpha:** +5.2% in 2008 (SPY -37%), -11.5% COVID (vs A -14.9%, SPY -33%), +0.5% in 2022.
- **2yr $1k outcome (30% haircut):** p5 **$911** / median **$1,119** / p95 **$1,373**;
  P(maxDD>20%) **4.5%** (vs 7.6% momentum-alone); P(below-start) 18.4%; P(<SPY) ~70%. Tighter
  drawdown than momentum-alone on every metric.
- **Sizing:** plan for -20% worst case → allocate **T/0.20** of net worth (25% conservative / 40%
  moderate / 60% aggressive); rest in T-bills.
- **Satellites rejected:** PUTW and stock-momentum each raise Sharpe slightly but **worsen the
  drawdown** (PUTW shares the crash tail; stock-mom is survivorship-flattered with -25% DD) — they
  break the low-DD mandate. Keep the clean 2-sleeve book.

**Honest caveats:** this is **insurance-flavored** — the inverse-ETF leg costs decay in calm bulls
(it dragged in the 2016-2026 inverse holdout) and whipsaws in fast V-reversals (the -11.5% COVID
print). It usually trails a US-equity bull on raw return (P(<SPY@2yr)≈70%). Both sleeves are
heavily-published risk premia; OOS-holdout + 2008/2022 crisis persistence is reassuring but no edge
is guaranteed forward. The diversification gain is **real but modest** (≈+0.07-0.10 Sharpe, ~2pp DD)
— worth the complexity for the lower-drawdown mandate, defensible to skip if an operator wants only
the simplest single sleeve.

**Current live combined target (2026-06-12, regime ON):** DBC 17.3%, USO 17.3%, VNQ 17.3%,
XLB 14.0%, XLE 14.0%, SPY/QQQ/EFA/EEM/UUP 3.3% each, TBT 3.3%, GLL 3.3%, BIL 3.3%. (Real-asset
momentum rotation; inverse legs short long-bonds and gold.)

*Reproduce:* `python3 run_portfolio_combined.py` (engine `portfolio_combined.py`); live target
`python3 portfolio_live.py`. Net of 3 bps/side; data via yfinance to non-repo `/tmp` paths.
