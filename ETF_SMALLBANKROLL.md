# ETF_SMALLBANKROLL — execution realism for a real $1k account

The deployable winner (`ETF_DEPLOY.md` / `etf_momentum_live.py`, commit 1cf9cef)
is backtested with **continuous fractional weights**. That is a fiction at small
size: at $1k a 20% slot is ~$200, but **one share of QQQ is ~$721, SPY ~$742,
GLD ~$387, MTUM ~$324, IWM ~$293** (latest raw closes). You literally cannot put
a whole share into several slots. Whole-share-only execution forces cash to sit
idle (cash drag) and pushes realized weights away from target (weight
distortion) — neither of which the idealized backtest sees.

This doc quantifies that gap with **real share prices**, tests the fixes, checks
rebalance-timing luck, independently confirms the ~0.8 Sharpe, and states the
minimum viable bankroll + small-account operating rules.

## Method & costs (state it plainly)

- **Engine:** `etf_smallbankroll.py` reuses the EXACT signal/gate math of
  `etf_momentum.py` (6-month risk-adjusted XS momentum, top-K equal weight,
  DUAL/absolute>cash filter, SPY>200d-MA regime gate, monthly partial rebalance
  p=0.34) but drives a **real dollar share-count portfolio** instead of abstract
  weights.
- **Two price matrices (real, via yfinance):**
  - **Adjusted** closes (`auto_adjust=True`, total-return) → signals + the
    idealized fractional backtest.
  - **Raw** closes (`auto_adjust=False`) → the **actual price per share you pay**,
    used for whole-share rounding at every rebalance. Dividends are credited as
    cash daily via the adjusted-minus-raw return drip, and idle cash earns the
    BIL/T-bill yield. Data staged to `/tmp/etfsmall_data` (NOT committed).
- **Costs:** commission-free ETFs + **3 bps/side** of traded notional (same as
  the locked backtest). No per-ticket fee (commission-free brokers). All numbers
  are **net**.
- **Validation:** the fractional dollar engine reproduces the published headline
  to the decimal — full-sample **CAGR 8.91%, Sharpe 0.821, maxDD −17.6%** (claim
  ~8-9% / 0.83 / −17%), weight-distortion ≈ 0. So the dollar engine is faithful;
  every gap below is pure execution friction, not a model change.
- Two windows throughout: **FULL 2000-2026** and **RECENT 2016-2026**.

---

## 1. Whole-share / cash-drag by bankroll (real share prices)

Idealized **FRACTIONAL** reference: FULL CAGR 8.91% / Sharpe 0.821 / DD −17.6%
(cash drag 8.2% — the strategy's *intrinsic* cash from the regime/absolute gates);
RECENT CAGR 8.98% / Sharpe 0.803 / DD −15.9%.

**FULL 2000-2026 — whole-share only, K=5 core**

| bankroll | CAGR | Sharpe | maxDD | ΔCAGR vs frac | ΔSharpe | cashDrag | distortion |
|---|---|---|---|---|---|---|---|
| **$500** | 6.62% | 0.848 | −12.3% | **−2.30pp** | +0.027 | **40.7%** | 0.325 |
| **$1,000** | 7.76% | 0.828 | −15.2% | **−1.16pp** | +0.007 | **24.8%** | 0.166 |
| $5,000 | 8.69% | 0.826 | −17.1% | −0.23pp | +0.005 | 11.8% | 0.036 |
| $10,000 | 8.78% | 0.822 | −17.4% | −0.13pp | +0.001 | 10.1% | 0.019 |
| $100,000 | 8.91% | 0.821 | −17.6% | −0.01pp | +0.001 | 8.4% | 0.002 |

**RECENT 2016-2026 — whole-share only, K=5 core**

| bankroll | CAGR | Sharpe | maxDD | ΔCAGR vs frac | ΔSharpe | cashDrag | distortion |
|---|---|---|---|---|---|---|---|
| **$500** | 4.19% | 0.966 | −5.7% | **−4.79pp** | +0.164 | **75.2%** | 0.658 |
| **$1,000** | 5.56% | 0.836 | −9.6% | **−3.42pp** | +0.033 | **52.8%** | 0.433 |
| $5,000 | 8.12% | 0.810 | −14.3% | −0.86pp | +0.008 | 20.4% | 0.109 |
| $10,000 | 8.47% | 0.802 | −14.7% | −0.51pp | −0.000 | 15.1% | 0.057 |
| $100,000 | 8.92% | 0.802 | −15.7% | −0.06pp | −0.000 | 10.2% | 0.007 |

**Read:**
- Whole-share-only **costs ~1.2pp CAGR (full) / ~3.4pp (recent) at $1k**, and
  ~2.3pp / ~4.8pp at $500. That is a large bite out of an ~9% gross edge.
- The damage is **cash drag, not Sharpe collapse.** At $1k a quarter of the book
  (52.8% in the recent window, when SPY/QQQ ran rich) is stranded in cash that
  cannot buy a whole share of the priciest picks. Sharpe even ticks *up* because
  the idle cash damps volatility — but you are no longer running the strategy,
  you are running a half-cash version of it with a much lower compounded return.
- **Crossover:** drag is immaterial (ΔCAGR < ~0.25pp) only at **~$5k+**. Scan:
  $1k −1.16pp → $2k −0.51pp → $3k −0.42pp → $5k −0.23pp → $10k −0.13pp.
- **Below ~$3-5k, whole-share-only materially degrades the edge.** At $1k it is
  impractical *as a whole-share-only book on this exact universe* — the issue is
  structural (slot $200 < single-share price of QQQ/SPY/GLD/MTUM/IWM).

---

## 2. Mitigations at $1k (and $500) — without fractional shares

Tested: (a) fractional shares, (b) fewer positions (K=3/4), (c) lower-priced-ETF
universe substitution, (d) greedy "hold-what-fits". Net, full sample at $1k:

| config | CAGR | Sharpe | maxDD | cashDrag | distortion |
|---|---|---|---|---|---|
| whole K=5 (baseline) | 7.76% | 0.828 | −15.2% | 24.8% | 0.166 |
| **FRACTIONAL K=5** | **8.91%** | 0.821 | −17.6% | 8.2% | **0.000** |
| whole K=3 | 7.53% | 0.758 | −17.5% | 20.8% | 0.126 |
| whole K=4 | 7.27% | 0.775 | −15.9% | 23.7% | 0.155 |
| **whole K=5 CHEAP-univ** | **8.17%** | **0.847** | −16.0% | 21.7% | 0.136 |
| GREEDY K=5 | 8.32% | **0.446** | **−66.3%** | 0.2% | 0.410 |
| GREEDY K=3 | 5.66% | 0.368 | −77.9% | 0.3% | 0.410 |
| GREEDY K=5 CHEAP | 8.62% | 0.456 | −66.0% | 0.4% | 0.354 |

Recent window at $1k tells the same story (FRACTIONAL 8.98%/0.803; CHEAP-univ
6.86%/**0.899**; GREEDY 9.5% CAGR but Sharpe 0.67 with −24% DD).

**Verdict on each mitigation:**
- **(a) Fractional shares — the real fix.** Restores the ideal exactly (distortion
  0.000, drag back to the intrinsic 8.2%). Recovers the full +1.2pp (full) /
  +3.4pp (recent) CAGR at $1k. Offered free by **Fidelity, Schwab, Robinhood, M1,
  Webull, Public**. This single broker choice matters more than every other
  mitigation combined.
- **(b) Fewer positions — counterproductive.** K=3/4 makes each slot bigger
  ($333/$250) but does NOT fix drag (the priciest picks still don't fit cheaply)
  and it **lowers Sharpe** (0.83→0.76) by concentrating into a less-diversified
  book. Do not reduce K to fight rounding.
- **(c) Lower-priced-ETF universe — best non-fractional option.** Swapping
  SPY→SPLG ($87), GLD→IAU ($79), EFA→SCHF ($28), EEM→VWO etc. lifts $1k CAGR to
  **8.17% and Sharpe to 0.847 (highest of any non-fractional config)** while
  cutting DD. It does NOT fully close the gap (QQQ/MTUM/IWM remain >$200, so drag
  is still ~22%), but it recovers ~0.4pp and keeps the diversified shape.
- **(d) Greedy "hold-what-fits" — a trap, reject it.** Sweeping leftover cash into
  the top affordable pick kills cash drag (→0%) but **wrecks risk control: maxDD
  −66%, Sharpe 0.45.** It silently over-weights one name to ~40%+, abandoning the
  equal-weight diversification that produces the 0.8 Sharpe. Higher CAGR in some
  windows is pure concentration risk, not edge.

**How much does fractional access matter?** Decisively. Fractional is worth
**+1.2pp (full) to +3.4pp (recent) CAGR at $1k** vs whole-share, with zero
distortion. The best whole-share workaround (cheap universe) recovers only ~0.4pp.
**At $1k, fractional shares are effectively required.**

---

## 3. Rebalance-timing luck (the day is arbitrary)

Same locked config, fractional, rebalancing on the 1st / 8th / 15th / 22nd / EOM,
plus a 4-way tranche (equal blend of the four day variants):

**FULL 2000-2026**

| rebalance day | CAGR | Sharpe | maxDD |
|---|---|---|---|
| day 1 | 8.55% | 0.773 | −21.1% |
| day 8 | 9.12% | 0.844 | −18.2% |
| day 15 | 7.79% | 0.739 | −20.5% |
| day 22 | 8.54% | 0.791 | −22.2% |
| **EOM (locked)** | 8.91% | 0.821 | −17.6% |
| **4-way tranche** | 8.51% | 0.795 | −20.4% |

**RECENT 2016-2026:** CAGR 8.56-9.51%, Sharpe 0.730-0.837, tranche 9.09%/0.799.

**Dispersion:** CAGR spread **~1.0-1.3pp**, Sharpe spread **~0.10**. Every day
keeps Sharpe in the 0.74-0.84 band and stays well above the 60/40 / SPY
baselines. **The edge is robust to the rebalance day — no day is special, none
breaks it.** Month-end (the locked default) is at the *better* end in both windows
(it captures month-end seasonality and is operationally simplest).

The 4-way tranche lands near the **median** of the four days with the **lowest
dispersion** — it does not raise return, it removes the timing lottery. For a $1k
account, tranching means quartering already-tiny slots into even worse whole-share
fits, so it is not worth the extra friction at small size.

**Operational rule:** rebalance **once a month on the last trading day** (or the
first 1-2 trading days of the new month if EOM is inconvenient — the difference
is within the noise). Pick one day and keep it; do not chase the day-8 number.
Tranche only if/when the account is large enough that quartered slots still fit.

---

## 4. Independent universe confirmation (not re-optimization)

To check the ~0.8 Sharpe isn't an artifact of the exact 31-name list, re-run the
headline (fractional, K=5) on **modestly different, deterministic** universes —
no re-tuning of lookback/K/gates:

**FULL 2000-2026**

| universe | CAGR | Sharpe | maxDD |
|---|---|---|---|
| full 31-name core | 8.91% | 0.821 | −17.6% |
| drop 3 priciest (SPY, QQQ, GLD) | 8.63% | 0.797 | −16.8% |
| fixed 19-name subset (sectors+SPY/QQQ/IWM+key macro) | 9.00% | 0.858 | −19.4% |
| cheap-substituted 31-name | 9.01% | 0.830 | −18.1% |

**RECENT 2016-2026:** full 0.803, drop-3 0.740, fixed-19 0.876, cheap-sub 0.804.

**Read:** Sharpe holds in **0.74-0.88** across every universe variant and both
windows. Dropping the three most expensive ETFs costs almost nothing (0.821→0.797
full). The ~0.8 Sharpe is a **property of the cross-asset momentum system, not of
the specific 30 names** — confirmed, not re-optimized.

---

## 5. Minimum viable bankroll + final small-account operating rules

**Minimum viable bankroll**

| | with fractional shares | whole-share only |
|---|---|---|
| **Practical floor** | **$500-$1,000** (the edge is intact; sizing/round-lot is irrelevant) | **~$5,000** (drag < ~0.25pp CAGR) |
| at $1,000 | full edge: 8.9% CAGR / 0.82 Sharpe | degraded: 7.8% (full) / 5.6% (recent) CAGR, ~25-53% idle cash |
| at $500 | full edge | badly degraded: −2.3pp (full) / −4.8pp (recent) |

- **With fractional shares: the minimum viable bankroll is ~$500-$1k.** Whole-share
  geometry simply stops mattering — you hold exact target weights. This is the
  recommended path for any account under ~$5k.
- **Without fractional shares: do not run this at $1k.** The structural
  mismatch (slot $200 < single-share price of QQQ/SPY/GLD/MTUM/IWM) strands
  20-50% in cash and quietly turns it into a half-invested strategy. Whole-share
  execution only becomes faithful at **~$5k+**.

**Final small-account operating rules**

1. **Use a fractional-share broker** (Fidelity / Schwab / Robinhood / M1 / Public).
   This is the load-bearing decision; it recovers +1.2 to +3.4pp CAGR at $1k and
   makes the strategy deployable from ~$500. *If you have it, change nothing else.*
2. **Position count: keep K=5.** Do NOT cut to K=3/4 to fight rounding — it lowers
   Sharpe (0.83→0.76) without fixing drag.
3. **Rebalance day: month-end, monthly.** Robust to timing (≤1.3pp CAGR / ≤0.10
   Sharpe across any day). Pick one day, keep it. Skip tranching until the account
   is large enough that quartered slots still fit (~$20k+).
4. **If you are stuck whole-share-only and under ~$5k:** use the **lower-priced-ETF
   universe** (SPY→SPLG, GLD→IAU, EFA→SCHF, EEM→VWO; keep QQQ/MTUM/IWM/sectors) —
   it is the best non-fractional config (8.2% CAGR / 0.85 Sharpe at $1k full,
   0.90 Sharpe recent) and does NOT re-optimize the signal. **Never** use the
   greedy "hold-what-fits" sweep — it produces −66% drawdowns by over-concentrating.
5. **Costs/taxes unchanged:** commission-free + ~3 bps/side; run it in an IRA if
   possible (monthly rebalance generates short-term gains in a taxable account).

**Bottom line:** the edge survives small size *only with fractional shares*. With
them, $500-$1k is fine and you run the exact strategy. Without them, $1k is
impractical (−1.2 to −3.4pp CAGR, 25-53% stranded cash); the smallest sensible
whole-share account is ~$5k, ideally on the cheaper-ETF universe.
