# FINAL PORTFOLIO — the single best deployable book for a US small bankroll

**Capstone synthesis.** The project's humbling honesty-gate finding: a dead-simple
**STATIC** portfolio (Permanent Portfolio Sharpe ~0.93; inverse-vol risk-parity ~0.84)
**BEATS** the active momentum+trend book (~0.81) on risk-adjusted return. This document
tests whether a **LIGHT tactical overlay** on the static base can capture the static's
high Sharpe **PLUS** the active book's shallower drawdown — net of costs, out-of-sample,
on a *plateau not a spike* — and states the single deployable answer.

**Window:** full overlap **2007-06 → 2026-06**; OOS holdout **2016-01 → 2026-06**.
**Costs:** **3 bps/side** on rebalance turnover (identical model to every component).
**Data:** yfinance dividend-adjusted (total-return) closes. Statics get no fitting/overfit credit.
**Engines reused (NOT re-derived):** `static_allocation.py` (PP, risk-parity), `etf_momentum.py`
+ `trend_following.py` + `portfolio_combined.py` (active 70/30 book), `btc_trend_timing.py` (crypto).
**Drivers (new):** `final_overlays.py` (overlay/blend/correlation sweep), `final_robust.py`
(plateau & bootstrap checks), `final_portfolio.py` (the runnable deployable harness).

---

## 1. BASE — confirm the best simple static

| Base (net 3bps) | Sharpe FULL | maxDD FULL | Sharpe OOS | maxDD OOS | CAGR OOS | worst yr |
|---|---|---|---|---|---|---|
| **Permanent Portfolio** 25 SPY/TLT/GLD/BIL | **0.927** | **-17.6%** | **1.067** | **-17.6%** | 7.9% | -12.6% |
| Risk-Parity inv-vol SPY/TLT/GLD/DBC | 0.842 | -20.0% | 1.050 | -20.0% | 9.6% | -9.7% |

**Robust BASE pick: the Permanent Portfolio.** Higher Sharpe in *both* periods and a
shallower maxDD than risk-parity. (Risk-parity has higher CAGR and a milder worst-*year*,
but a deeper peak-to-trough; PP is the cleaner risk-adjusted base and is the textbook
near-zero-effort 4-ETF book.) The plateau result below also holds with the RP core, so the
choice is not load-bearing.

**Reference — the active 70/30 momentum+TF book:** Sharpe 0.808 FULL / 0.915 OOS, maxDD
-13.6% / -12.6%, CAGR 8.3% / 9.5%, worst year -4.8% / -1.7%. Confirms the honesty-gate:
on Sharpe the active book *loses* to pure static; its only standalone edge is a shallower
drawdown and a much milder worst year.

---

## 2. LIGHT OVERLAYS on the static base (each net of cost, full + OOS)

| Overlay (vs pure PP) | Sharpe FULL | maxDD FULL | Sharpe OOS | maxDD OOS | CAGR OOS | effort |
|---|---|---|---|---|---|---|
| **Pure Permanent Portfolio (base)** | 0.927 | -17.6% | 1.067 | -17.6% | 7.9% | ~zero (quarterly) |
| (a) Regime-gate equity slice (SPY<200dMA→BIL) | 0.945 | -16.3% | 0.948 | -16.3% | 6.4% | monthly check |
| (a) Regime-gate whole risk (eq+TLT+GLD→BIL) | 0.859 | -11.5% | 0.894 | -11.5% | 5.3% | monthly check |
| (c) Trend-filter each asset (>10m MA else BIL) | 0.964 | **-7.9%** | 0.968 | **-7.9%** | 5.5% | monthly check |
| **(b) 80/20 PP / active** | 1.013 | -13.8% | 1.130 | -13.8% | 8.3% | monthly |
| **(b) 70/30 PP / active** | **1.028** | -11.9% | **1.137** | -11.9% | 8.5% | monthly |
| **(b) 60/40 PP / active** | 1.024 | **-10.7%** | 1.128 | -10.7% | 8.6% | monthly |
| (b) 50/50 PP / active | 1.004 | -10.9% | 1.105 | -10.9% | 8.8% | monthly |

**Reading the overlays:**

- **(a) Regime-gating is a wash-to-negative.** Gating just the equity slice barely moves
  Sharpe (0.93→0.95) and *worsens* it OOS (1.067→0.948) while only trimming maxDD by ~1pp.
  Gating the whole risk book cuts maxDD nicely (-17.6%→-11.5%) but *kills* Sharpe (0.93→0.86)
  and CAGR (to 5.3%). The static's bonds/gold already cushion equity crashes — bolting a
  200-day filter on top mostly sells low and gives up the rebound. **Does not clear the bar.**

- **(c) Per-asset 10-month trend filter** gives the *shallowest* maxDD (-7.9%) and a small
  Sharpe bump (0.93→0.96), but at a heavy CAGR cost (7.9%→5.5% OOS) — it spends most of its
  time partly in cash. It's a fine *defensive* variant for the very risk-averse, but the
  return give-up is real and it does **not** dominate pure PP on Sharpe by enough to justify
  the monthly per-asset checks for most investors.

- **(b) STATIC CORE + small ACTIVE satellite is the standout.** Blending 70% PP with 30%
  of the active book **beats BOTH** pure static (Sharpe 1.067→1.137, maxDD -17.6%→-11.9% OOS)
  **AND** pure active (Sharpe 0.915→1.137, maxDD -12.6%→-11.9%). And it is a **plateau, not a
  spike**: 80/20 → 70/30 → 60/40 all sit at Sharpe ~1.13 with **monotonically improving**
  maxDD (-13.8% → -11.9% → -10.7%). A flat ridge across the blend ratio is the signature of a
  *structural* effect, not a fitted one. **This clears the brutal bar.**

---

## 3. Cross-correlation / conflict check — do the pieces fight?

Daily-return correlations (full overlap):

|        | SPY  | TLT   | GLD  | ACTIVE | PP   |
|--------|------|-------|------|--------|------|
| TLT    | -0.31|  1.00 | 0.17 | -0.08  | 0.42 |
| GLD    | 0.06 |  0.17 | 1.00 |  0.29  | 0.74 |
| ACTIVE | 0.45 | -0.08 | 0.29 |  1.00  | 0.43 |

- **beta(ACTIVE ~ TLT) = -0.05**, beta(~GLD) = +0.17, beta(~SPY) = +0.24.
- **Crash check (worst-5% PP days, n=240):** corr(ACTIVE, PP) = **+0.26** only; corr to TLT
  on those days is **-0.16**. When the bond/gold-heavy static is bleeding, the active book is
  *not* bleeding with it.

**Verdict: diversifying, not conflicting.** The TF leg *does* sometimes short the very bonds/
gold the static is long — but in aggregate the active book is near-**zero/negative beta to
TLT** and only mildly correlated to the static overall. The occasional short does not net out
to a meaningful long-bond conflict; instead the active book plugs exactly the PP's weak spot
(a simultaneous stock+bond drawdown, e.g. 2022). That is *why* the blend's drawdown shrinks.

---

## 4. THE ANSWER — is pure static the honest optimum, or does an overlay earn its effort?

**The blend's edge is real but its character matters.** The headline single-period OOS
Sharpe jump (1.067 → 1.137) is **not** the robust part:

- Per calendar year, the 70/30 blend beats pure PP in only **9/20 years (45%)**.
- Rolling 3-year Sharpe: blend ≥ PP in **54%** of windows (48% OOS) — roughly a coin flip.
- Block-bootstrap (3y horizon, 30% drift haircut, OOS returns): **P(blend Sharpe > PP
  Sharpe) = 63%** — a tilt, not a slam dunk.

**What IS robust and repeatable is the drawdown / crash protection:**

- maxDD **-17.6% → -11.9%** (≈6 pp shallower), monotone across the blend plateau.
- Worst year **-12.6% → -8.7%**; the 2022 stock+bond crash (PP's worst year) was **-8.7% vs
  -12.6%**, and 2013's taper tantrum was **+2.1% vs -4.2%**.
- The same DD improvement holds with a **risk-parity core** (Sharpe 1.05→1.11, maxDD
  -20.0%→-14.9% OOS) — confirming it is structural diversification, not a PP-specific fluke.

**Honoring the brutal bar.** Pure PP is near-zero-effort (4 ETFs, quarterly) and its high
Sharpe may partly ride a non-repeating 2007–2026 bond+gold tailwind. Any overlay must clear
a *high* bar. Regime-gating (a) and the trend filter (c) **fail** it — they trade away return
for marginal or no risk-adjusted gain. The **70/30 static-core + active-satellite blend (b)
passes**, but the honest sell is *"same-or-better Sharpe with a materially shallower crash,"*
**not** *"a big Sharpe upgrade."*

> **Honest bottom line.** If you will not reliably do monthly work, **just hold the Permanent
> Portfolio, rebalance quarterly — done.** That is a perfectly good answer. If you *will*
> reliably spend ~15 min/month rebalancing, the **70/30 PP-core + active-satellite blend**
> genuinely earns that effort by cutting the drawdown ~6 pp for the same-or-better Sharpe.

---

## 5. FINAL RECOMMENDATION + RUNBOOK

### Recommended portfolio (the deployable default — `--mode blend`)

```
70% STATIC CORE  : Permanent Portfolio = 17.5% SPY, 17.5% TLT, 17.5% GLD, 17.5% BIL
30% ACTIVE SAT.  : 70% of sat -> ETF risk-adj momentum (top-5, 200d regime gate, dual filter)
                   30% of sat -> inverse-when-down trend-following sleeve (vol-targeted 10%)
Rebalance        : MONTHLY (partial ~1/3 toward target on the satellite to damp turnover);
                   the PP core only needs QUARTERLY rebalancing.
```

Zero-effort alternative (`--mode static`): the pure Permanent Portfolio, quarterly.

### Sizing as %-of-net-worth by risk tolerance

The book above is the *risky* allocation; size it as a fraction of investable net worth and
keep the rest in your own emergency cash / short T-bills **outside** the engine:

| Risk tolerance | % of net worth in this book |
|---|---|
| conservative | 40% |
| moderate (default) | 65% |
| aggressive | 85% |

(The PP core is itself defensive, so these can run higher than a 100%-equity book would.)

### Optional crypto sleeve (separate, NOT double-counted)

- **Trend-timed IBIT** (or ETHA), **200-day SMA**: hold only while price > 200d MA, else cash.
  Validated in `btc_trend_timing.py` (timing lifts Sharpe ~0.97→1.2 and cuts recent maxDD
  ~-77%→-35% vs buy-hold). **Hold in an IRA/Roth**, sized **≤5% of the book**, as a *separate*
  satellite (the harness prints it apart and does not fold it into the 100% above).
- *Current signal:* IBIT **below** its 200d MA → **0% (cash)**.

### IRA / tax notes

- **PP core** (SPY/TLT/GLD/BIL) is buy-and-hold and tax-efficient → fine in a **taxable** account.
- **Satellites churn monthly and use inverse/leveraged ETFs** (SH/PSQ/EFZ/EUM/TBT/GLL/DUG/RWM)
  → realize short-term gains; **prefer an IRA/Roth** for the satellite + crypto sleeve to avoid
  short-term-gains tax drag. If everything must be taxable, lean toward `--mode static`.

### Runbook (the harness)

```bash
# this month's full target allocation, $25k, moderate risk, with crypto sleeve:
python final_portfolio.py --capital 25000 --risk moderate --crypto

# zero-effort pure Permanent Portfolio:
python final_portfolio.py --mode static --capital 25000

# append a dated row to the forward PAPER track (idempotent per month+mode):
python final_portfolio.py --capital 25000 --crypto --paper-track
```

The harness reuses the locked engines, fetches live yfinance prices (degrades to a cache if
Yahoo is unreachable), prints current-month target weights + $ targets, and is **paper-only**
(no brokerage API, no orders, no secrets). You read the report and place trades manually.

### CURRENT TARGET ALLOCATION (as-of 2026-06-12, $25,000, moderate, blend, +crypto)

Risky-book capital = $16,250 (65% of $25k); remaining $8,750 = your cash/T-bills outside the engine.
Satellite A regime ON, momentum picks = DBC, USO, XLE, MTUM, XLB; TF sleeve 8 long / 3 down.

| Instrument | Weight | $ target |
|---|---|---|
| SPY | 18.50% | $3,007 |
| TLT | 17.50% | $2,844 |
| GLD | 17.50% | $2,844 |
| BIL | 16.46% | $2,675 |
| DBC | 5.20% | $846 |
| USO | 5.20% | $846 |
| MTUM | 4.20% | $682 |
| XLB | 4.20% | $682 |
| XLE | 4.20% | $682 |
| QQQ / EFA / EEM / TBT / GLL / VNQ / UUP | ~1.00% each | ~$163 each |
| **TOTAL** | **100%** | **$16,250** |
| CRYPTO SLEEVE (IRA, ≤5% = $813) | IBIT below 200d MA → **0% (cash)** | $0 |

---

## SCREENS (limitations & honest caveats)

1. **Bond+gold tailwind may not repeat.** PP's 2007–2026 Sharpe rode a historic bond bull +
   gold strength. The blend's *drawdown* protection is more robust to this than its Sharpe,
   which is the honest reason to weight the verdict toward "shallower crash, similar Sharpe."
2. **The Sharpe bump is modest** (bootstrap P=63%, ~half of rolling windows). Do not oversell it.
3. **Inverse-ETF realism.** The TF sleeve de-levers -2x inverse ETFs (TBT/GLL/DUG) to ~1x
   notionally; real-world tracking, borrow, and daily-rebalance drag could shave a little.
4. **Satellite turnover** assumes disciplined monthly partial rebalancing; whipsaw/forgetting
   degrades it. Fractional shares are needed to hit these weights cleanly below ~$5k.
5. **Crypto sleeve** is small and trend-gated by design; sized ≤5% and held in an IRA it cannot
   sink the book, and it is reported separately so it is never double-counted.
6. **No leverage, no shorting outside the small TF sleeve, no derivatives**; commission-free
   ETFs assumed; 3 bps/side spread is the only trading cost modeled.

**Verdict:** Pure Permanent Portfolio (quarterly) is the honest near-zero-effort optimum. The
**one** overlay that genuinely earns added effort is the **70/30 PP-core + active-satellite
blend**, which buys a ~6 pp shallower drawdown for the same-or-better Sharpe — on a plateau,
OOS, net of costs.
