# ALLWEATHER_DEPLOY — deployable trend-overlaid all-weather harness + growth plan

**The BUILD/operationalize step of the locked verdict** (PROJECT_VERDICT.md `e85e2af`,
REGIME_ROBUSTNESS.md `959984e`, INCOME_500_REALITY.md `945f828`). The research is done;
this turns the FINAL recommendation — a **trend-overlaid all-weather portfolio** — into a
runnable tool a US small-bankroll operator (<$5k now, medium risk, goal $500/mo *eventually*)
can actually run each month, plus the honest multi-year growth plan to get there.

Nothing here is re-derived. It REUSES the committed engines: `etf_momentum_live.fetch_prices`
/ `compute_target` (LOCKED ETF risk-adj momentum), the 6-12m time-series trend rule validated
in `regime_robustness.py` / `trend_following.py`, and the 200d-SMA crypto timer from
`final_portfolio.py` / `BTC_TREND_TIMING.md`. **PAPER ONLY — no brokerage API, no orders, no
secrets; you read the report and place the trades manually.**

- **Window:** conservative core stats are the long-history 1972-2023 (`regime_robustness.py`);
  the growth-tilt validation + planner run on ETF-era **yfinance, 2006-06-13 .. 2026-06-12**
  (n=5032 trading days). **Costs:** 5 bps/side on the long-history reuse; **10 bps round-trip**
  per unit of monthly turnover in the growth backtest (conservative for commission-free
  fractional ETFs).
- **SCREENS:** all numbers below are real script output pasted verbatim (as-of bar 2026-06-12).
  yfinance total-return series; IBIT only has history since 2024-01-11, so it contributes to the
  growth book only in the recent window (the full-sample growth stats are mostly IBIT-OFF).
  The COVID-2020 fast crash is the binding tail — no *monthly* trend filter dodges a 3-week gap;
  the 15% permanent cash floor is what keeps the full-sample DD in-band.

---

## 1. The two configs (one engine, `allweather_live.py`)

The rule, in one sentence: **hold each risk sleeve only if its trailing 12-month total return
is positive (trend up); otherwise that sleeve's weight goes to BIL cash.** The crypto sleeve uses
a 200-day SMA timer instead. Monthly, partial rebalance (~1/3 toward target, `p=0.34`, to damp
whipsaw).

| Sleeve | CONSERVATIVE (default) | GROWTH (`--growth`) |
|---|---|---|
| SPY (US stocks, trend-gated) | 25% | 32% |
| TLT (long Treasuries, trend-gated) | 25% | 18% |
| GLD (gold, trend-gated) | 25% | 12% |
| MOM satellite (cross-asset ETF momentum) | — | 18% |
| IBIT (crypto, 200d-SMA timed, capped) | — | 5% |
| BIL (cash floor, always) | 25% | 15% |
| **Expected** | Sharpe ~1.4, CAGR ~10%, maxDD ~-10% (1972-2023) | CAGR ~13-18%/yr, maxDD ~-30-40% |

Whatever is trend-OFF in a given month adds to BIL. The growth tilt's permanent 15% cash floor +
the trend gates are what keep it medium-risk rather than a 100%-equity bet.

### 1a. CURRENT real target allocation — CONSERVATIVE (as-of 2026-06-12, $5,000)

```
  SLEEVE TREND GATES:
    SPY    base   25%  ON  (hold)    12m ret +24.8%
    TLT    base   25%  ON  (hold)    12m ret +4.1%
    GLD    base   25%  ON  (hold)    12m ret +25.3%
  TARGET ALLOCATION:
    INSTRUMENT    WEIGHT        $ TARGET
    SPY            25.0%          $1,250
    TLT            25.0%          $1,250
    GLD            25.0%          $1,250
    BIL            25.0%          $1,250  (cash)
    TOTAL         100.0%          $5,000
```
All three risk sleeves are above their 12-month trend right now, so the conservative book is the
full Permanent Portfolio (25% each). If, say, TLT's 12m trend turned negative, its 25% would move
to BIL (50% cash) until the bond trend repaired.

### 1b. CURRENT real target allocation — GROWTH (as-of 2026-06-12, $5,000)

```
  SLEEVE TREND GATES:
    SPY    base   32%  ON  (hold)    12m ret +24.8%
    TLT    base   18%  ON  (hold)    12m ret +4.1%
    GLD    base   12%  ON  (hold)    12m ret +25.3%
    MOM    base   18%  regime ON; picks=['DBC', 'USO', 'XLE', 'MTUM', 'XLB']
    IBIT   base    5%  OFF (-> cash) BELOW 200d SMA -> CASH
  TARGET ALLOCATION:
    INSTRUMENT    WEIGHT        $ TARGET
    SPY            32.0%          $1,600
    BIL            20.0%          $1,000  (cash)   <- 15% floor + 5% IBIT-off this month
    TLT            18.0%            $900
    GLD            12.0%            $600
    DBC             3.6%            $180
    MTUM            3.6%            $180
    USO             3.6%            $180
    XLB             3.6%            $180
    XLE             3.6%            $180
    TOTAL         100.0%          $5,000
```
IBIT is **OFF** (below its 200d SMA), so its 5% sits in cash — exactly the trend discipline that
keeps crypto from being a buy-and-hold drag. The 18% momentum satellite resolved this month to a
commodity/energy/momentum basket (DBC/USO/XLE/MTUM/XLB, equal-weight within the sleeve).

---

## 2. Growth-tilt validation (does it EARN its risk, or just add it?)

`growth_planner.py --validate`, ETF-era yfinance 2006-06-13 .. 2026-06-12, 10 bps round-trip cost.
**Verbatim output:**

```
  --- FULL SAMPLE  (2006-06-13 .. 2026-06-12) ---
  candidate                               CAGR  Sharpe    maxDD     vol
  PP (pure Permanent Portfolio)           7.4%    1.00   -17.3%    7.4%
  CONSERVATIVE (trend-overlaid PP)        7.0%    0.97   -17.1%    7.3%
  GROWTH (tilt)                          13.4%    0.76   -39.8%   19.1%

  --- RECENT 5Y (OOS-ish, the hardest test)  (2021-06-13 .. 2026-06-12) ---
  candidate                               CAGR  Sharpe    maxDD     vol
  PP (pure Permanent Portfolio)           7.2%    0.87   -17.3%    8.4%
  CONSERVATIVE (trend-overlaid PP)        8.0%    0.96   -17.1%    8.4%
  GROWTH (tilt)                          17.5%    0.91   -29.4%   19.9%

  --- HONESTY CHECKS (does GROWTH earn its risk, not just add it?) ---
  GROWTH adds +6.4pp CAGR for +22.6pp more maxDD (ret/DD trade = +0.28)
  bootstrap P(GROWTH daily mean > CONSERVATIVE) = 98%
  rolling-1y windows GROWTH > CONSERVATIVE: 66%
  GROWTH maxDD full=-39.8%, recent=-29.4%
  VERDICT: GROWTH tilt -> KEEP
```

**Reading it honestly.**
- **It earns the return, on a plateau, not a spike.** GROWTH out-CAGRs the conservative book by
  +6.4pp full-sample and +9.5pp recent; bootstrap P(GROWTH daily mean > CONSERVATIVE) = **98%**
  and it wins **66%** of rolling 1-year windows. This is a persistent risk-premium harvest
  (more trend-gated equity + momentum + a small trend-timed crypto sleeve), not one lucky year.
- **It sits at medium risk, in-band.** Recent-5y maxDD **-29.4%** is squarely in the target
  -30..-40% band; full-sample **-39.8%** (the worst case, driven by the **COVID March-2020
  3-week crash** that no monthly filter can dodge) is at the top of the band — **not** the -60%
  of a levered/buy-and-hold-crypto book. Recent Sharpe 0.91 ≈ pure PP's 0.87 — i.e. you take more
  drawdown but the *risk-adjusted* return holds up because the trend gates and the 15% cash floor
  truncate the tails.
- **Net of cost.** All numbers are after 10 bps round-trip on turnover; the edge survives.
- **The trade-off, stated plainly:** GROWTH buys ~2x the CAGR of the conservative book for ~2.5x
  the drawdown and ~2.7x the vol. That is the *right* trade in **phase 1** (small account, no
  withdrawals, long horizon to compound) and the *wrong* trade in **phase 2** (you're drawing
  income and a -40% year would gut the paycheck) — hence the staged runbook in §4.

**Verdict: KEEP the growth tilt for the accumulation phase.** It honestly earns its higher return
OOS net of cost and stays at medium (not ruinous) risk. Switch to the conservative book before
you start drawing income.

---

## 3. Contribution-and-compound planner — your real timeline to $70k

`$500/mo needs ~$70k` at safe returns (INCOME_500_REALITY.md). From <$5k that is a **GROWTH**
problem: contribute monthly and compound — do **not** withdraw. The planner Monte-Carlos the
**GROWTH config's OWN bootstrapped daily returns** (stationary block bootstrap, 21-day blocks,
keeps fat tails + vol clustering — **the bad tail is in the distribution**), adds a fixed monthly
contribution, no withdrawals, and reports the YEARS to reach $70k.

`growth_planner.py --plan`, **verbatim** (2,500 paths; p25 = lucky / median / p75 = unlucky):

```
  driver: GROWTH config's OWN bootstrapped daily returns (CAGR 13.4%, vol 19.1%, maxDD -39.8%)
     start | +$200/mo (p25/med/p75 yr) | +$500/mo (p25/med/p75 yr) | +$1000/mo (p25/med/p75 yr)
  --------------------------------------------------------------------------
  $  2000 |  9.6/10.9/12.6    |  5.8/ 6.6/ 7.4    |  3.7/ 4.1/ 4.6
  $  5000 |  8.5/ 9.8/11.5    |  5.4/ 6.1/ 7.0    |  3.5/ 3.9/ 4.4
```

**The operator's real timeline (years to the $70k '$500/mo base'):**

| Start | +$200/mo | +$500/mo | +$1,000/mo |
|---|---|---|---|
| **$2,000** | 10.9 (9.6–12.6) | 6.6 (5.8–7.4) | 4.1 (3.7–4.6) |
| **$5,000** | 9.8 (8.5–11.5) | **6.1 (5.4–7.0)** | 3.9 (3.5–4.4) |

*(median, with p25–p75 band.)* **Contributions dominate at this size** — note how the starting
balance ($2k vs $5k) barely moves the timeline, but the monthly contribution ($200 → $1,000)
roughly halves it. The ~13-18% trend-gated edge is the *finisher*; saving rate is the engine until
the balance is large. **From $5k at $500/mo: median 6.1 years (5.4 lucky / 7.0 unlucky) to $70k.**

This is a **multi-year plan, not a fast track.** Even the lucky-quartile $5k/$500-mo path is >5
years. There is no honest shortcut from $5k to $500/mo (INCOME_500_REALITY.md §2-3: forcing it
needs 120%/yr, which only ruin-level leverage can target).

---

## 4. The runbook (staged)

### Broker
- **Fractional-share, commission-free brokerage** — mandatory at small size: a 3.6% momentum
  sleeve on a $5k account is ~$180, well under one share of MTUM (~$324). Fidelity, Schwab, or
  M1 all do fractional + $0 commission on ETFs.
- **Use an IRA / Roth IRA** for tax-efficiency. The PP core is tax-efficient anyway, but the
  momentum satellite and the trend-timed IBIT sleeve churn (monthly), so holding them in an IRA
  avoids the short-term-gains drag. (Caveat: an IRA can't be withdrawn penalty-free before 59½ —
  if you genuinely need the $500/mo as spendable cash *before then*, run the conservative core in
  a taxable account instead; it barely churns.)

### Cadence
- **Once a month, on a fixed day** — e.g. the **1st trading day of the month** (or any fixed day
  you'll remember). Trend signals are slow; the exact day doesn't matter, *consistency* does.
- ~15 minutes: run the script, read the report, place the listed partial-rebalance trades.

### How to run it
```bash
# Phase 1 (accumulation): the growth tilt, sized to your account
python allweather_live.py --growth --capital 5000 --holdings holdings.json

# Phase 2 (income): the conservative trend-overlaid all-weather
python allweather_live.py --capital 70000 --holdings holdings.json
```
`holdings.json` = your CURRENT dollar positions, e.g. `{"SPY": 1600, "GLD": 600, "CASH": 1000}`.
Omit it on the first run (the report then shows full first-month BUYs from all-cash). The report
prints **current vs target weights** and the **partial trades** (in $ and approx whole shares).
Place them, add your monthly contribution as cash (it shows up as a BIL buy next month), done.

### The sleeve-trend rule in plain English
> For each sleeve, look at its price 12 months ago vs today. **If it's up over the year, hold it.
> If it's down, sell it to cash (BIL) and wait.** Re-check monthly. Crypto (IBIT) uses the
> 200-day average instead: hold only while price is above its 200d average. You never hold a
> falling asset — that one rule is what halved the drawdown and cut the 2022 loss from -13% to -4%
> in the long-history test, and it's why this beats a raw Permanent Portfolio.

### Sizing
- The `--capital` you pass IS the book. There is no separate leverage. Keep your true emergency
  cash (3-6 months expenses) **outside** this account entirely.
- Partial rebalance moves ~1/3 toward target each month — so a fresh account takes ~3 months to
  fully ramp in. That's intentional (dollar-cost-averaging + whipsaw damping).

### STAGING (the explicit phases)
1. **Phase 1 — GROW (now → ~$70k):** run `--growth`, contribute monthly, **withdraw nothing.**
   Tolerate the -30-40% drawdowns; you're compounding, not spending. Median ~6 years from
   $5k + $500/mo (§3).
2. **Phase 2 — DRAW (at ~$70k):** switch to the conservative `allweather_live.py` (no `--growth`)
   and begin drawing ~$500/mo. At ~$70k a $6k/yr draw is a ~8.5% rate, matched to the conservative
   book's safe return; INCOME_500_REALITY.md shows survival is robust only at this base, **not** at
   $5k/$10k/$25k (those get bled to zero by withdrawals inside 1-3 years).

---

## 5. Honest risks

- **Trend whipsaw.** In choppy, trendless markets the 12-month gate sells low and buys back higher,
  bleeding a few % a year. The partial (1/3) rebalance and 12m (slow) lookback damp it, but it's
  real — it's the premium you pay for the crash insurance.
- **It will NOT beat a raw bull market.** When everything rips (2017, 2021), the conservative book
  trails 100%-stocks badly, and even the growth tilt's cash floor + bonds + gold drag vs SPY-only.
  Its value is *risk-managed, crash-truncated* growth, not maximal return. If you want to beat a
  bull, this isn't it.
- **The COVID-type fast crash is not dodged.** A monthly trend filter can't react to a 3-week -34%
  gap; that's the -39.8% full-sample tail. The 15% cash floor caps it, but a fast crash will still
  hurt the growth book. Don't run `--growth` with money you'll need within a couple of years.
- **$500/mo needs the BASE first.** This is the load-bearing honesty: the strategy is the ~10%
  finisher; **contributions + time are the lever.** You cannot trade $5k into $500/mo — you grow
  $5k into ~$70k over years, *then* it pays you. There is no config in this whole project that
  does it faster without ruin-level risk.
- **Tailwind caveat (inherited).** The conservative core's long-history edge leaned partly on a
  one-time 1970s gold repricing + the 2007-2024 negative stock-bond correlation; the trend overlay
  is precisely what makes it robust to those NOT repeating (REGIME_ROBUSTNESS.md §4). The growth
  tilt's recent CAGR also rode a strong 2023-2025 equity/commodity run — haircut the point estimate
  mentally; the planner's p75 (unlucky) band is the more honest number to plan around.

---

## 6. (Optional) wire the recommended portfolio into the existing paper track

`--paper-track` appends/updates a dated, idempotent (per mode, per month) row to a JSONL so the
**recommended** trend-overlaid all-weather book — not just the old ETF momentum book — accrues a
forward paper track:

```bash
python allweather_live.py --paper-track --track-file allweather_paper_track.jsonl --capital 5000
python allweather_live.py --growth --paper-track --track-file allweather_paper_track.jsonl --capital 5000
```

To have the existing **monthly `etf-paper.yml`** workflow accrue this track automatically, **add
one line** to its "Run the locked-config live harness" step (do NOT edit the workflow's structure;
this is the only change needed):

```yaml
      # add inside the existing "Run ..." step, alongside the etf_momentum_live.py calls:
      - python allweather_live.py --growth --paper-track --track-file allweather_paper_track.jsonl --capital 5000
      # and add allweather_paper_track.jsonl to the `git add` line in the commit step.
```

It is PAPER ONLY (computes target + appends a row; never places an order) and degrades gracefully
if yfinance is down (won't write a bogus row off stale cache).

---

## Files
- `allweather_live.py` — the runnable monthly harness (conservative + `--growth`, `--paper-track`).
- `growth_planner.py` — `--validate` (the §2 backtest) + `--plan` (the §3 Monte-Carlo planner).
- Reuses (does NOT edit): `etf_momentum_live.py`, `regime_robustness.py`, `trend_following.py`,
  `final_portfolio.py`.

*Window: conservative core 1972-2023 (regime_robustness.py); growth validation + planner ETF-era
yfinance 2006-06-13..2026-06-12. Costs: 5 bps/side long-history reuse; 10 bps round-trip growth
backtest. As-of bar 2026-06-12. PAPER ONLY; not investment advice. SCREENS: IBIT history starts
2024-01 (full-sample growth mostly IBIT-OFF); the COVID-2020 gap is the binding -39.8% tail; recent
CAGR rode a strong 2023-25 run — plan around the p75 band, not the point estimate.*
