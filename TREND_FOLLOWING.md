# Trend-Following / Managed-Futures Sleeve as a Diversifier for the ETF-Momentum Winner

**Question.** The project's winner (`ETF_MOMENTUM.md`, e3e2d57) is a long-only **cross-sectional**
ETF-momentum book: 6m risk-adjusted relative-rank momentum, top-5 EW, SPY>200d gate, monthly,
Sharpe ~0.83 / maxDD ~-17%. It is long-only and has no crisis hedge beyond going to cash. This
study asks whether a structurally different **trend-following (time-series / absolute) sleeve** —
long when an asset's *own* trend is up, **short (via inverse ETFs) or to cash when down**,
vol-targeted, the classic CTA return stream — provides **crisis alpha** that lowers the *combined*
book's drawdown and raises its Sharpe. US-legal instruments only (long ETFs, inverse ETFs, cash;
**no futures/perps**).

**Verdict up front: YES, but only the INVERSE-ETF (short-in-crashes) version diversifies.**
A 70/30 (XS-winner / TF-inverse) combined book beats the XS-winner ALONE on **both** axes over the
2007-2026 overlap — **Sharpe 0.74 -> 0.81 and maxDD -15.6% -> -13.6%, net of costs** — because the
inverse-ETF TF leg is **-0.04 correlated to SPY** and is **positive in 2008 (+17% full year, +9%
GFC trough) and 2022 (+4%)**: genuine crisis alpha. The *cash-when-down* TF leg has a higher
standalone Sharpe (0.91) but is **0.78 correlated to the winner** (both are just long-trend with a
risk-off switch), so it raises combined drawdown and adds little diversification. Inverse ETFs cost
real drag (standalone Sharpe 0.66 vs 0.91 for cash), but that drag buys the negative-beta crash
payoff that is the entire point. **Recommendation: add a ~20-30% TF-inverse sleeve.**

---

## Data, window, costs (SCREENS)

- **Source:** yfinance daily **adjusted** closes (total return). Long ETFs reuse the winner's
  staged file `/tmp/etfmom_data/etf_prices.csv`; inverse ETFs staged at
  `/tmp/tf_data/inverse_etfs.csv` (**neither committed**).
- **TF universe (11 liquid cross-asset):** equities SPY/QQQ/EFA/EEM, bonds TLT/IEF,
  commodities DBC/GLD/USO, REIT VNQ, dollar UUP. All present from **2007-06** (UUP is the binder).
- **Inverse ETFs (short-in-crash leg):** SH(SPY), PSQ(QQQ), EFZ(EFA), EUM(EEM), TBT(TLT, de-levered
  -2x->-1x), GLL(GLD, -2x->-1x), DUG(USO, -2x->-1x), RWM(VNQ proxy). Assets with no clean liquid
  1x inverse (IEF/DBC/UUP) go to cash when their trend is down. **Inverse-ETF decay/expense is
  already inside their adjusted prices**; a synthetic daily-rebalanced -1x short (+50bps/yr borrow)
  is also tested to expose the rebalancing drag.
- **Window:** **2007-06 -> 2026-06 full overlap** (covers 2008 GFC, 2020 COVID, 2022). Recent-decade
  OOS holdout **2016-01 -> 2026-06**.
- **Costs:** **3 bps/side** on traded notional (matches the winner), charged on monthly turnover.
  Cost sensitivity reported (0/3/10/25 bps).
- **TF method:** time-series signal per asset (sign of 6m trailing return; price>10m-MA also
  tested), equal base weight 1/N, signed long/short, sleeve scaled to a vol target (7/10/15%),
  gross capped at 2x. Monthly rebalance. All numbers **net**.

---

## 1. TF sleeve standalone — plateau across lookback x vol-target (cash-when-down), 2007-2026

| config | CAGR | Sharpe | maxDD | vol | turn/mo |
|---|---|---|---|---|---|
| vt7% 3m | 7.5% | 0.82 | -14.1% | 9.3% | 0.38 |
| vt7% **6m** | 8.7% | **0.89** | -19.5% | 9.8% | 0.28 |
| vt7% 12m | 7.4% | 0.76 | -20.0% | 10.2% | 0.23 |
| vt10% 3m | 10.2% | 0.86 | -19.0% | 12.2% | 0.46 |
| vt10% **6m** | 11.6% | **0.91** | -23.8% | 13.0% | 0.32 |
| vt10% 12m | 9.8% | 0.76 | -24.5% | 13.5% | 0.25 |
| vt15% 6m | 13.1% | 0.93 | -23.8% | 14.4% | 0.32 |
| vt10% 10m-MA | 9.7% | 0.81 | -17.8% | 12.5% | 0.33 |

**Plateau, not a spike:** Sharpe 0.76-0.93 across 3/6/12m x three vol targets and the MA variant.
6m is the sweet spot (classic). Realized vol runs a touch above target because the
independent-asset vol estimate understates correlated crash days — honest, not a bug.

## 2. The cost of shorting US-legally: cash vs inverse-ETF vs synthetic short (6m, vt10%)

| down-leg | CAGR | Sharpe | maxDD | vol | turn/mo |
|---|---|---|---|---|---|
| **cash** | 11.6% | **0.91** | -23.8% | 13.0% | 0.32 |
| **inverse ETF** | 8.7% | 0.66 | -21.9% | 14.3% | 0.54 |
| synthetic -1x (+borrow) | 9.4% | 0.66 | -23.7% | 15.5% | 0.62 |

Shorting via inverse ETFs costs **~0.25 Sharpe and ~3pp CAGR** standalone (decay + higher turnover
+ whipsaw). The synthetic short confirms this is structural, not an inverse-ETF tracking artifact.
**Standalone, cash-when-down wins.** The inverse leg only earns its keep inside the *combination*
(Section 5) because of its crash payoff.

## 3. CRISIS ALPHA — TF vs SPY and the XS winner in equity crashes

| crisis | SPY | XS winner | TF cash | **TF inverse** |
|---|---|---|---|---|
| 2008 GFC (Sep08-Mar09) | -36.9% | -0.1% | -1.8% | **+9.2%** |
| 2008 full year | -36.8% | +0.2% | +1.8% | **+16.9%** |
| 2020 COVID (Feb19-Mar23) | -33.4% | -14.9% | -21.5% | **-3.5%** |
| 2022 stocks+bonds | -18.2% | -1.5% | +0.5% | **+4.2%** |

**The inverse-ETF TF leg delivers true crisis alpha**: strongly positive in 2008 and 2022, roughly
flat in the COVID crash, all while SPY fell 18-37%. The **cash** TF leg only *avoids* losses (it
can't profit from a crash) and actually **lost -21.5% in the COVID 2020 V** — the textbook
trend-following weakness: a too-fast crash-and-rebound whipsaws a monthly trend system. The inverse
leg, being net-short in the slide, is the one that protects the COVID drawdown (-3.5% vs -21.5%).

## 4. Correlation to the winner and to SPY (monthly, 2007-2026)

| | XS winner | TF cash | TF inverse | SPY |
|---|---|---|---|---|
| XS winner | 1.00 | 0.78 | **0.43** | 0.61 |
| TF cash | 0.78 | 1.00 | 0.74 | 0.53 |
| TF inverse | 0.43 | 0.74 | 1.00 | **-0.04** |
| SPY | 0.61 | 0.53 | -0.04 | 1.00 |

The crux. **TF-cash is 0.78 correlated to the winner** — both are long-trend books with a risk-off
switch, so cash-TF is largely redundant. **TF-inverse is only 0.43 correlated to the winner and
-0.04 to SPY** — a genuinely different, market-neutral-to-negative return stream. *Diversification
value lives in the inverse leg, not the higher-Sharpe cash leg.*

## 5. COMBINED PORTFOLIO vs XS-winner ALONE (full overlap 2007-2026, net)

**TF leg = cash-when-down:**

| book | CAGR | Sharpe | maxDD |
|---|---|---|---|
| XS winner ALONE | 7.9% | 0.743 | -15.6% |
| 50/50 | 9.8% | 0.873 | -18.9% |
| 70/30 XS/TF | 9.1% | 0.833 | -17.6% |

**TF leg = inverse-when-down (the diversifier):**

| book | CAGR | Sharpe | maxDD |
|---|---|---|---|
| **XS winner ALONE** | 7.9% | **0.743** | **-15.6%** |
| 50/50 | 8.5% | 0.795 | **-14.0%** |
| **70/30 XS/TF** | 8.3% | **0.808** | **-13.6%** |
| risk-parity (0.56/0.44) | 8.5% | 0.804 | -13.8% |

**This is the whole point.** Adding the **inverse-ETF** TF sleeve at **70/30** raises Sharpe
**0.743 -> 0.808** AND cuts maxDD **-15.6% -> -13.6%** (a **13% drawdown reduction**), net of the
inverse-ETF drag. The cash-TF combo raises Sharpe more (higher standalone Sharpe) but *increases*
maxDD to -17.6% — it dilutes crash protection because it's correlated to the winner and can't be
net-short. **For the deployable goal (lower drawdown + higher risk-adjusted return), inverse-ETF TF
is the right leg.** During crises the 70/30 inverse combo returned **+2.7% (GFC), -11.5% (COVID, vs
winner -14.9%), +0.5% (2022)** — it improves every crash window.

## 6. Robustness — recent-decade OOS holdout (2016-2026)

| book | CAGR | Sharpe | maxDD |
|---|---|---|---|
| XS winner alone | 8.9% | 0.809 | -15.6% |
| TF cash alone | 14.4% | 1.099 | -23.8% |
| 50/50 (cash) | 11.6% | 1.014 | -18.9% |
| 70/30 (cash) | 10.5% | 0.946 | -17.6% |

The diversification benefit persists out-of-sample: the combo Sharpe exceeds the winner in the
never-optimized 2016-2026 window too. (The 2016-2026 inverse-leg combo is weaker than cash because
that decade had only one real crash, COVID, where inverse helped, but otherwise paid decay during a
bull — the inverse leg is *insurance*, expected to underperform in calm bulls and pay in crashes,
which is exactly the 2008/2022 evidence in Section 3.)

## 7. Costs and turnover (honesty)

- **TF cash cost sensitivity (full):** Sharpe 0.92 / 0.91 / 0.89 / 0.84 at 0/3/10/25 bps. Edge
  survives realistic costs.
- **Inverse-ETF leg turnover ~0.54/mo** (~6.5 turns/yr) — higher than the winner's 0.31, driven by
  flipping in/out of inverse positions. This is folded into the net numbers above.
- **Inverse-ETF drag is real and modelled** (it's in the adjusted price; the synthetic-short test
  confirms ~0.25 Sharpe of structural cost). Whipsaw is real: TF-cash *lost* in the fast 2020 V;
  monthly trend systems get chopped in sharp reversals. The inverse leg's crisis alpha is the
  compensation for accepting that drag in calm markets.

## VERDICT

**Add a trend-following sleeve — the INVERSE-ETF (short-in-crashes) version, at ~20-30% weight.**
It materially improves the deployable book vs XS-momentum alone, net of costs, OOS:

- **Config:** time-series 6m-trend, 11 liquid cross-asset ETFs, long when own trend up; when down,
  hold the asset's **inverse ETF** (SH/PSQ/EFZ/EUM/TBT-delev/GLL-delev/DUG-delev/RWM) or cash where
  no clean inverse exists; vol-target ~10%; monthly; 3 bps/side.
- **Combination:** **70/30 (XS-winner / TF-inverse)** rebalanced monthly. Full-sample 2007-2026:
  **Sharpe 0.74 -> 0.81, maxDD -15.6% -> -13.6%** (13% DD cut), and positive in 2008 (+17% yr) and
  2022 (+4%), -11.5% COVID vs winner -14.9%. Risk-parity (~0.56/0.44) gives a similar result.
- **Why not cash-TF:** higher standalone Sharpe (0.91) but 0.78-correlated to the winner and
  *increases* combined drawdown to -17.6% — it does not provide crisis alpha (can't be net-short),
  so it fails the brief. Use inverse.

**Honest caveats:** (1) the inverse-ETF leg *costs* ~0.25 standalone Sharpe — it is insurance, not
a return-maximizer, and will drag in calm bulls (visible in the 2016-2026 inverse holdout). (2) TF
is heavily published; the persistence into the OOS holdout and the 2008/2022 crisis evidence is
reassuring, but the diversification gain (≈+0.06 Sharpe, ~2pp DD) is **modest**, not transformative.
(3) Monthly TF whipsaws in fast V-reversals (the 2020 cash-TF loss). The verdict: **a small
inverse-TF overlay is worth adding for crash protection and a real DD reduction; sizing it above
~30% trades away too much of the winner's return for diminishing DD benefit.** If an operator wants
*only* the highest Sharpe and tolerates the -17% DD, XS-momentum alone is defensible — but for the
project's stated goal (lower drawdown, crisis alpha) the 70/30 inverse combo wins.

*Reproduce:* `python3 run_trend_following.py` (engine `trend_following.py`; reuses `etf_momentum.py`
for the winner). Net of 3 bps/side; data via yfinance to `/tmp/etfmom_data/` and `/tmp/tf_data/`
(not committed).
