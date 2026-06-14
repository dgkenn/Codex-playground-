# ETF_DEPLOY — Deploying the WINNING edge: cross-asset ETF momentum

This is the **convergent payoff** of the whole research project. After exhausting
microstructure/mispricing plays on prediction markets and crypto venues, the one
edge that is *deployable for a US retail small bankroll* is a systematic
risk-premium: **cross-sectional + time-series momentum on liquid ETFs**. It is
US-legal in any brokerage, IRA-tax-free, $1k-deployable, has no access wall, and
historically delivers an equity-like return at ~1/3 of equity's drawdown.

This doc takes the **LOCKED config** validated in `ETF_MOMENTUM.md` (commit
e3e2d57) and turns it into something you can actually run and trade:
- a runnable harness (`etf_momentum_live.py`) that prints **this month's target**,
- an **honest forward outcome distribution** (block-bootstrap, mean-haircut),
- a **concrete %-of-net-worth sizing** rule,
- a **step-by-step deployment runbook**, and
- a **go-live bar** + two-sided risk list.

> **It is paper-only.** No brokerage API, no orders, no secrets. You read the
> report and place trades by hand. Run a forward PAPER track first; only then,
> small real money.

---

## 1. The LOCKED spec (do NOT re-optimize)

| Parameter | Value |
|---|---|
| **Universe** | ~30 liquid cross-asset ETFs: US sectors XLK/XLE/XLF/XLV/XLI/XLY/XLP/XLU/XLB; style SPY/QQQ/IWM/MTUM; intl/country EFA/EEM/EWJ/EWZ/EWG/EWU/FXI/VGK; bonds TLT/IEF; gold GLD; commodities DBC/USO; REIT VNQ; dollar UUP; plus SLV/HYG/LQD. Cash leg = **BIL** (1-3mo T-bill ETF). |
| **Signal** | **Risk-adjusted momentum** = (trailing **6-month** total return) / (trailing annualized vol), cross-sectional rank. |
| **Hold** | **Top K=5** equal-weight (20% each); remainder in BIL/T-bills. |
| **Gate 1 — DUAL/absolute** | Hold a ranked ETF only if its 6-month return **beats cash**; else that slot -> cash. |
| **Gate 2 — regime** | If **SPY < its 200-day MA**, go **100% cash** (BIL). |
| **Rebalance** | **Monthly**, **partial (p=0.34** — move ~1/3 of the way to target each month) to damp turnover/whipsaw. |
| **Costs** | Commission-free ETFs + ~3 bps/side spread. |
| **Optional** | Add crypto-proxy members **IBIT/MSTR/COIN/GBTC** (`--crypto-proxy`). Higher CAGR/Sharpe, ~2pp more DD, **short history — suggestive only**. |

**Backtested net (from `ETF_MOMENTUM.md`):** core CAGR ~8-9%, Sharpe ~0.80-0.83,
maxDD ~-17%; held up on the 2016-2026 OOS holdout and through 2008/2022. With
crypto-proxies (2016+): CAGR ~14.5%, Sharpe ~0.98, ~-18% DD.

---

## 2. PROOF — the harness runs on live data (current target portfolio)

Run end-to-end on real yfinance data, **as-of last bar 2026-06-12**:

```
$ python etf_momentum_live.py --capital 1000
==========================================================================
  ETF CROSS-ASSET MOMENTUM — LIVE TARGET (LOCKED CONFIG, PAPER ONLY)
==========================================================================
  data source     : yfinance
  as-of (last bar): 2026-06-12
  universe        : core
  config          : 6m risk-adj momentum, top K=5 EW, DUAL+SPY>200d, partial p=0.34
  SPY 200d gate   : ON (risk-on)   (SPY 741.75 vs 200d MA 684.07)
  decision        : RISK-ON: hold top 5 by 6m risk-adj momentum
--------------------------------------------------------------------------
  TARGET PORTFOLIO (top-K by 6m risk-adj momentum):
    ticker      weight   mom score
    DBC          20.0%       1.069     (broad commodities)
    USO          20.0%       1.044     (oil)
    XLE          20.0%       0.990     (energy)
    MTUM         20.0%       0.913     (US momentum factor)
    XLB          20.0%       0.909     (materials)
    CASH          0.0%
--------------------------------------------------------------------------
  PARTIAL-REBALANCE TRADES (move ~34% toward target this month), capital $1,000
    ticker     cur w   tgt w  step w    trade $  ~shares    price
    DBC         0.0%   20.0%    6.8%    +68.00 BUY     +2.4    28.55
    MTUM        0.0%   20.0%    6.8%    +68.00 BUY     +0.2   324.40
    USO         0.0%   20.0%    6.8%    +68.00 BUY     +0.5   125.43
    XLB         0.0%   20.0%    6.8%    +68.00 BUY     +1.3    52.18
    XLE         0.0%   20.0%    6.8%    +68.00 BUY     +1.2    57.55
    CASH target after step:   66.0%
==========================================================================
```

**Current target (2026-06): commodities/energy + US-momentum + materials**, all
equal-weight 20%, regime risk-ON (SPY 741.75 > 200d MA 684.07). With
`--crypto-proxy` the target is **identical this month** — IBIT/MSTR/COIN/GBTC are
scored but currently have **negative** 6-month risk-adj momentum (IBIT -0.77,
MSTR -0.49, COIN -0.74, GBTC -0.79), so the dual filter correctly excludes them.
This is the gate doing its job: it only holds crypto-proxies when they trend.

> The first month you start from cash, the partial rule buys only ~1/3 toward
> target (≈6.8% per sleeve, 66% left in cash). Full weight is approached over
> ~3 months of monthly rebalances — by design, to avoid buying a top in one shot.

---

## 3. Forward OUTCOME DISTRIBUTION (honest)

Method (`etf_outcome_dist.py`): take the locked-config backtest's **monthly net
return** series, **haircut the mean by 30%** (forward realism: published-edge
decay + live slippage; keeps full vol & fat tails), then **stationary block
bootstrap** (≈6-month blocks, 20,000 paths) to preserve autocorrelation and
vol-clustering. Post-haircut the base sleeve runs at **ann. mean ~6.5%, ann. vol
~9.3%, Sharpe ~0.69**.

### BASE (core ~30 ETFs)

| Horizon | Terminal @ $1k (p5 / p25 / **median** / p75 / p95) | Terminal @ $10k (p5 / **median** / p95) |
|---|---|---|
| 1yr | $932 / $1,000 / **$1,055** / $1,119 / $1,228 | $9,316 / **$10,547** / $12,278 |
| **2yr** | **$931** / $1,035 / **$1,123** / $1,222 / **$1,375** | **$9,310** / **$11,233** / **$13,747** |
| 3yr | $946 / $1,078 / **$1,191** / $1,316 / $1,526 | $9,461 / **$11,908** / $15,258 |

| Risk metric (BASE) | 1yr | 2yr | 3yr |
|---|---|---|---|
| P(maxDD > 20%) | 0.0% | 0.6% | 1.5% |
| P(maxDD > 30%) | 0.0% | **0.0%** | 0.0% |
| Time underwater (median / p95 frac of horizon) | 67% / 100% | 71% / 96% | 72% / 94% |
| P(below starting capital at 2yr) | — | **16.9%** | — |
| P(underperform SPY over 2yr) | — | **60.3%** | — |

### CRYPTO-PROXY (core + IBIT/MSTR/COIN/GBTC, 2016+ only — SHORT HISTORY)

Post-haircut ann. mean ~10.7%, vol ~14.4%, Sharpe ~0.74.

| Horizon | Terminal @ $1k (p5 / **median** / p95) | Terminal @ $10k (p5 / **median** / p95) |
|---|---|---|
| 1yr | $915 / **$1,066** / $1,401 | $9,153 / **$10,662** / $14,008 |
| **2yr** | **$909** / **$1,188** / **$1,670** | **$9,088** / **$11,877** / **$16,704** |
| 3yr | $931 / **$1,301** / $1,940 | $9,315 / **$13,005** / $19,404 |

| Risk metric (CRYPTO) | 1yr | 2yr | 3yr |
|---|---|---|---|
| P(maxDD > 20%) | 0.3% | 2.4% | 5.2% |
| P(maxDD > 30%) | 0.0% | 0.0% | **0.2%** |
| P(below starting capital at 2yr) | — | **16.9%** | — |
| P(underperform SPY over 2yr) | — | **67.0%** | — |

**How to read this honestly:**
- The median doubles-your-money story is **not** here. This is a **risk-managed,
  equity-*like*** return: 2yr base median **+12%**, p5 **-7%**, p95 **+38%**.
- **You will spend most of the time underwater** from a prior peak (median ~70%
  of the horizon). That is normal for momentum — sit through it.
- It loses to SPY most of the time (**~60% over 2yr**) precisely because its job
  is **drawdown control**, not out-returning a bull. If you want to beat a bull
  market, buy the bull market and accept its -55% crashes.
- **Tail caveat (important):** the bootstrap's P(maxDD>30%)≈0% and p5 2yr DD of
  ~14% are *thinner* than the documented full-sample maxDD of -17/18%, because a
  2-year window rarely contains the single worst 26-year crash. **Do not** read
  "30% DD basically can't happen." Treat the **historical -17/18% maxDD as the
  honest floor**, and a momentum-crash year as a real -20%+ possibility. The
  sizing rule below uses that conservative number, not the rosier bootstrap p5.

---

## 4. CONCRETE SIZING (%-of-net-worth)

"Size small" made concrete: size so a **1-in-20 bad path is a $ loss you can
shrug off**. We size off the **worst case** = max(bootstrap p5 2yr drawdown,
historical full-sample maxDD) = **~18%** peak-to-trough on the allocated sleeve
(both base and crypto-proxy, since crypto's deeper bootstrap p5 DD ≈ the base's
historical floor).

> **Rule:** if you can stomach losing **T%** of net worth at the bottom of a bad
> run, allocate **(T% / 18%)** of net worth to this sleeve.

| Risk tolerance (NW loss you'd shrug off) | Allocate (% of net worth) |
|---|---|
| 5% of NW | **~28% of NW** |
| 10% of NW | **~56% of NW** |

Worked examples (base **and** crypto-proxy — same ~18% sizing DD):

| Net worth | Tolerate 5% NW loss ($) → allocate | Tolerate 10% NW loss ($) → allocate |
|---|---|---|
| $50,000 | $2,500 → **$13,900 (28%)** | $5,000 → **$27,800 (56%)** |
| $200,000 | $10,000 → **$55,600 (28%)** | $20,000 → **$111,100 (56%)** |

**Small-bankroll reading:** if your investable net worth is, say, $3,600 and you
can shrug off a 5% (≈$180) hit, that maps to a ~$1,000 sleeve — which is exactly
the `--capital 1000` default. For a brand-new operator, **start smaller than the
formula** (e.g. $500-$1,000 regardless) until the live paper track clears the
go-live bar; the formula is a ceiling, not a target.

> Crypto-proxy note: its **upside** is fatter (2yr p95 +67% vs base +38%) but its
> tail is also fatter and rests on ~9 years of history. Size it the same ~18% but
> mentally budget more variance; treat the crypto numbers as **suggestive**.

---

## 5. DEPLOYMENT RUNBOOK (step by step)

**Goal:** a monthly, ~15-minute manual routine in a commission-free brokerage,
ideally inside an IRA so the whole thing is tax-free.

1. **Open / pick an account.** Any commission-free US brokerage (Fidelity,
   Schwab, Vanguard, etc.). **Prefer an IRA** (Roth or Traditional): monthly
   rebalancing generates taxable events in a taxable account, but **in an IRA
   taxes are zero** — this is the single biggest structural advantage of this
   strategy over the weekly-turnover crypto sleeve. Enable **fractional shares**
   if offered (helps at $1k with $300-700 ETFs like MTUM/QQQ).

2. **Fund it small.** Use the §4 sizing as a ceiling; for a first deployment,
   $500-$1,000 is plenty. The strategy has **zero capacity issue** (these ETFs
   trade billions/day), so size is purely about your own risk, not market impact.

3. **Pick a fixed monthly day and stick to it.** E.g. the **first business day of
   each month**. Consistency matters more than the exact date; do NOT cherry-pick
   timing. (The backtest rebalances at month-end; a fixed early-month day is fine
   and is what the sample GitHub Action uses.)

4. **Run the harness** on your chosen day:
   ```
   python etf_momentum_live.py --capital 1000              # base
   python etf_momentum_live.py --crypto-proxy --capital 1000   # if you opted into crypto
   ```
   To get exact trade sizes, pass your **current holdings**:
   ```
   # holdings.json:  {"XLE": 130.0, "DBC": 70.0, "CASH": 800.0}   ($ per ticker)
   python etf_momentum_live.py --capital 1000 --holdings holdings.json
   ```

5. **Read the report and place the trades manually.**
   - If **"GO TO CASH"** (SPY < 200d MA, or nothing beats cash): sell down toward
     cash per the partial step, park proceeds in BIL or your sweep.
   - Otherwise: place the listed **BUY/SELL** orders. The script moves only ~1/3
     toward target each month — that's intended; do not "catch up" in one go.
   - **Whole-share practicality at $1k:** each sleeve is ~$200. For ETFs priced
     $25-$130 (DBC, USO, XLE, XLB, GLD-no/most sectors) you can buy 1-7 whole
     shares; for $300-$700 ETFs (MTUM, QQQ, SPY) use **fractional shares**, or
     round to the nearest whole share and accept small weight drift (noise is
     minor at K=5). Skip any trade smaller than ~$20 to avoid odd-lot churn.

6. **Log it.** Add `--paper-track` so each run appends a dated row (holdings,
   weights, gate state, paper equity) to `etf_paper_track.jsonl`. This is your
   forward track record. Re-running in the same month overwrites that month's row
   (idempotent), so you can run it as many times as you like.

7. **Repeat monthly.** ~3-4 small trades/month. Don't touch it between rebalances;
   don't override the gate with your opinion.

**Optional automation (inert sample provided):** `etf-paper.yml.sample` is a
monthly GitHub Actions cron that runs `--paper-track` and commits the JSONL to a
`data` branch, auto-accumulating the forward track. It is left as a `.sample`
(GitHub won't run it) — copy it to `.github/workflows/etf-paper.yml` to opt in.
It is **paper only**: it never places an order and needs no secrets.

---

## 6. GO-LIVE BAR (gate real money behind a forward paper track)

The backtest is necessary but not sufficient. **Before any real money:**

- [ ] Run `etf_momentum_live.py --paper-track` **every month for 3-6 months**
      (or enable `etf-paper.yml.sample`) to build a real, dated forward track.
- [ ] **Rolling Sharpe of the paper track ≥ 0.6** over that 3-6 month window.
      (Don't expect 0.83 in a short window — but a sustained *negative* Sharpe or
      a >20% paper drawdown is a red flag to pause and re-check.)
- [ ] The reports must have **run cleanly each month** (data fetched, gate logic
      sensible, trades plausible) — i.e. the operational routine actually works
      in your hands.
- [ ] You have **internalized §3** — you accept ~17% drawdowns, ~70%-of-the-time
      underwater, and losing to SPY in bull markets, *without* bailing.

Only when all four are checked: deploy **real money at the §4 size (or smaller)**.
Then keep the paper track running in parallel as a live sanity check.

---

## 7. HONEST RISKS (two-sided)

1. **Momentum crashes.** Momentum's classic failure mode is a sharp reversal
   after a market bottom (e.g. 2009): the strategy is positioned in the prior
   leaders/cash and gets whipsawed as junk rips. The regime gate and partial
   rebalance soften this but **do not eliminate it** — budget a -20%+ year.
2. **Regime-gate whipsaw.** A choppy market that crosses the SPY 200d MA
   repeatedly can flip you in/out of cash near tops/bottoms, locking in small
   losses. The monthly cadence and partial step limit, but don't remove, this.
3. **It will NOT beat a raw bull market.** ~60% chance of underperforming SPY
   over 2yr (§3). This is **by design**: you are buying drawdown control, not
   maximum return. If the next 5 years are another straight-up bull, plain SPY
   will likely win on return (and lose badly on the eventual crash).
4. **Published-edge decay.** Cross-asset momentum is heavily published. Its
   persistence into the 2016-2026 OOS holdout is reassuring, but no edge is
   guaranteed forward — hence the 30% mean haircut and the go-live bar.
5. **Crypto-proxy = short history + fat tails.** The crypto uplift rests on ~9
   years (some members <4). The proxies can gap hard; the gate caps but doesn't
   remove that. Suggestive, not proven.
6. **Data dependency.** The harness needs yfinance/Yahoo. If it's unreachable the
   script degrades gracefully (falls back to a cached file and refuses to write a
   bogus paper row), but you may have to retry on a different day.
7. **Execution drift at $1k.** Whole-share rounding and odd-lot avoidance add
   small tracking error vs the idealized backtest. Minor at K=5, but real.

---

## 8. Reproduce

```
python etf_momentum_live.py [--crypto-proxy] [--capital 1000] [--paper-track] [--holdings holdings.json]
python etf_outcome_dist.py        # the §3/§4 distribution + sizing (needs the backtest price cache)
```

- Live target & paper track: `etf_momentum_live.py` (self-contained; locked config).
- Outcome distribution & sizing: `etf_outcome_dist.py` (reuses `etf_momentum.py`).
- Locked-config evidence & backtest: `ETF_MOMENTUM.md` + `run_etf_momentum.py`.
- Sample monthly automation (inert): `etf-paper.yml.sample`.

All figures net of ~3 bps/side. Paper only — no real-money, order, or secret code.
