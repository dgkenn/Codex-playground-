# Static Allocation Honesty Check — does the active momentum+TF book beat a lazy portfolio?

**Question.** The project's validated active book is a cross-asset ETF-momentum sleeve
(`ETF_MOMENTUM.md` e3e2d57, Sharpe ~0.83 full sample) plus a 70/30 momentum / inverse-ETF
trend-following combo (`TREND_FOLLOWING.md` 0350194, Sharpe ~0.81 full / ~0.91 OOS, maxDD
~-13.6%/-12.6%). A young US small-bankroll investor's **real alternative is not cash** — it is a
lazy 3-fund or all-weather portfolio. So the only honest test is: **does the active book beat a
boring static mix, risk-adjusted, after costs, on an equal footing — and by enough to justify the
effort?** If a static mix ~ties it, say so loudly.

**VERDICT UP FRONT (brutally honest): it is essentially a TIE on the metric that matters.** Over the
equal-footing full sample the active 70/30 book (Sharpe **0.81**, maxDD **-13.6%**) does **not** beat
the best simple static — the Permanent Portfolio posts a **higher** Sharpe (**0.93**) at the **same**
drawdown (-17.6%) with near-zero effort, and a simple inverse-vol risk-parity matches it (Sharpe 0.84,
maxDD -20%). On the recent-decade OOS holdout the gap **widens against the active book**: Permanent
Portfolio Sharpe **1.06**, risk-parity **1.05**, vs the active combo **0.91**. The active book's one
genuine, defensible edge is the **shallowest drawdown and worst-year** of anything tested (maxDD -13.6%
full / -12.6% OOS; worst year -4.8%/-1.7%) and uniquely strong **2022** behavior. But on Sharpe — the
brief's headline axis — **the lazy portfolio wins, net of costs, in-sample and out.** The complexity
buys a marginally smaller max drawdown and crash-robustness, **not** higher risk-adjusted return.

---

## Window, costs, screens (equal footing — the brutal bar)

- **Data:** yfinance daily **adjusted** (total-return) closes. ETF prices reused from the active
  book's staged file `/tmp/etfmom_data/etf_prices.csv`; static extras (AGG/IWN/SHY) at
  `/tmp/static_data/extra_prices.csv`. **Neither committed.**
- **Equal-footing full sample: 2007-06 → 2026-06.** This start is forced by the latest static-asset
  inception (DBC 2006-02, BIL 2007-05) so **every** portfolio — static and active — sees the **same**
  period. It conveniently equals the TF overlap window, so the active combo is on identical footing.
  (Longer SPY-only / momentum histories shown as *context only*, flagged as unequal windows.)
- **Recent-decade OOS holdout: 2016-01 → 2026-06** (~10.5y, never optimized on).
- **Costs:** commission-free ETFs (commission = 0) + **3 bps/side** spread on rebalance turnover —
  the **same** cost model the active book uses. Statics rebalanced **monthly** (quarterly variant also
  shown — cheaper, basically identical results).
- **Discipline:** every strategy rebalances on a fixed schedule; statics get **no** survivorship or
  overfit risk (fixed weights, nothing fitted) and trivial execution — they are given that credit.
- All numbers **net**. Reproduce: `python3 run_static_allocation.py` (engine `static_allocation.py`;
  active book via `etf_momentum.py` / `trend_following.py`, reproduced exactly: winner Sharpe 0.828
  full / 0.809 holdout, 70/30 combo 0.808/0.910).

Static portfolios built (US-legal, fractional-share-deployable at $1k):
(a) 100% SPY; (b) 60/40 SPY/AGG; (c) Permanent Portfolio 25% each SPY/TLT/GLD/BIL;
(d) Golden Butterfly 20% each SPY/IWN(small-value)/TLT/SHY/GLD; (e) inverse-vol risk-parity of
SPY/TLT/GLD/DBC; (f) All-Weather-lite 30% SPY / 55% bonds (40 TLT + 15 IEF) / 15% real assets
(7.5 GLD + 7.5 DBC).

---

## 1. Head-to-head — FULL SAMPLE 2007-06 → 2026-06 (equal footing, monthly, net 3 bps/side)

| strategy | CAGR | Sharpe | maxDD | worst year | vol |
|---|---|---|---|---|---|
| 100% SPY | 10.6% | 0.61 | -55.2% | -36.8% | 19.8% |
| 60/40 SPY/AGG | 7.9% | 0.70 | -35.8% | -21.1% | 11.9% |
| **Permanent Portfolio** | 6.8% | **0.93** | -17.6% | -12.6% | 7.4% |
| Golden Butterfly | 7.3% | 0.81 | -21.2% | -13.8% | 9.2% |
| All-Weather-lite | 6.5% | 0.80 | -23.7% | -19.3% | 8.3% |
| **Risk-Parity (inv-vol)** | 7.8% | **0.84** | -20.0% | -9.7% | 9.4% |
| ACTIVE: ETF momentum | 7.9% | 0.74 | -15.6% | -5.9% | 11.1% |
| **ACTIVE: 70/30 mom+TF** | 8.3% | **0.81** | **-13.6%** | **-4.8%** | 10.6% |

**Read it straight:** on **Sharpe**, the Permanent Portfolio (0.93) **beats** the full active book
(0.81) and even risk-parity (0.84) edges it. The active 70/30 book's distinction is the **smallest
maxDD (-13.6%) and best worst-year (-4.8%)** in the table — that is real, and no static matches it —
but it does **not** translate into a higher Sharpe. The active book also out-CAGRs the low-vol statics
(8.3% vs PP 6.8%), so it is not strictly dominated; it is a different point on the frontier (more return,
slightly more vol, smaller tail) — **not a risk-adjusted win.**

## 2. Head-to-head — RECENT-DECADE OOS HOLDOUT 2016-01 → 2026-06 (monthly, net 3 bps/side)

| strategy | CAGR | Sharpe | maxDD | worst year | vol |
|---|---|---|---|---|---|
| 100% SPY | 15.2% | 0.88 | -33.7% | -18.2% | 17.8% |
| 60/40 SPY/AGG | 10.0% | 0.91 | -21.6% | -15.8% | 11.1% |
| **Permanent Portfolio** | 7.9% | **1.06** | -17.6% | -12.6% | 7.4% |
| Golden Butterfly | 8.7% | 0.98 | -19.4% | -13.8% | 9.0% |
| All-Weather-lite | 6.6% | 0.78 | -23.7% | -19.3% | 8.6% |
| **Risk-Parity (inv-vol)** | 9.6% | **1.05** | -20.0% | -9.7% | 9.1% |
| ACTIVE: ETF momentum | 8.9% | 0.81 | -15.6% | -4.9% | 11.3% |
| **ACTIVE: 70/30 mom+TF** | 9.4% | 0.91 | **-12.6%** | **-1.7%** | 10.5% |

**The OOS holdout is the decisive, humbling result.** In the never-optimized 2016-2026 window the
**simple statics pull further ahead on Sharpe**: Permanent Portfolio **1.06**, risk-parity **1.05**,
Golden Butterfly **0.98**, even **60/40 (0.91)** ties the active combo (0.91). The active book again
owns the **smallest drawdown** (-12.6%) and **best worst-year** (-1.7%), but its Sharpe is matched by a
literal 60/40 and beaten by three different brain-dead static mixes. **The active book's OOS Sharpe edge
over the best static is negative.**

Quarterly rebalancing the statics (less effort, lower turnover) changes essentially nothing
(PP 0.94, Golden Butterfly 0.83, All-Weather 0.83 full sample) — confirming the static edge is not a
rebalance-frequency artifact.

## 3. Crisis windows — where the active book is supposed to shine

| crisis | SPY | Perm Port | Golden Bfly | Risk-Parity | **70/30 active** |
|---|---|---|---|---|---|
| 2008 GFC (Sep08-Mar09) | -36.9% | **-3.8%** | -12.1% | -7.9% | -10.7% |
| 2020 COVID (Feb-Mar) | -33.4% | **-6.4%** | -13.9% | -12.6% | -13.3% |
| 2022 stocks+bonds (full yr) | -18.2% | -12.6% | -13.8% | -9.7% | **-0.8%** |

A second humbling finding: the **Permanent Portfolio survived the GFC (-3.8%) and COVID (-6.4%) better
than the active book** (-10.7%, -13.3%). The active book's celebrated crisis alpha is **real only in
2022** (-0.8%, the one regime — simultaneous stock+bond selloff with persistent commodity/dollar trends
— where momentum rotation and a short leg genuinely dominate a fixed allocation). In the classic
flight-to-quality crashes, **25% long bonds + 25% gold did the same job, statically, for free.**

---

## 4. Leverage angle — is "lever a simple diversified portfolio" a credible competitor?

For a young, risk-tolerant investor, the natural move is to **lever a low-vol diversified static** up to
an equity-like risk budget. Modelled honestly: constant daily-reset leverage (which also captures
volatility decay, the LETF-style drag), financing the borrowed portion at **4.5%/yr margin**, drawdowns
amplified in full.

| strategy | CAGR | Sharpe | maxDD | worst yr |
|---|---|---|---|---|
| Permanent Portfolio 1.0x | 6.8% | **0.93** | -17.6% | -12.6% |
| Permanent Portfolio 1.4x | 7.6% | 0.75 | -25.1% | -18.9% |
| Permanent Portfolio 1.6x | 7.9% | 0.70 | -28.6% | -22.0% |
| Risk-Parity 1.0x | 7.8% | **0.84** | -20.0% | -9.7% |
| Risk-Parity 1.4x | 8.8% | 0.71 | -28.2% | -15.3% |
| Risk-Parity 1.8x | 9.7% | 0.63 | -37.7% | -20.8% |
| **ACTIVE 70/30 mom+TF (unlevered)** | 8.3% | **0.81** | **-13.6%** | **-4.8%** |

**Honest read on leverage.** Pure leverage leaves Sharpe **unchanged** (PP at 1.4x is 0.93 before
financing); the only thing that erodes it is the **financing drag** — ~1.8%/yr at 1.4x on ~10% vol
costs ~0.17 of Sharpe — **plus fully amplified drawdowns**. So a 1.4x Permanent Portfolio reaches the
active book's CAGR neighbourhood (7.6% vs 8.3%) but at a **deeper drawdown** (-25% vs -13.6%) and a
**lower Sharpe** (0.75 vs 0.81). Here the **active book wins the comparison**: it delivers similar return
to a modestly-levered static with **half the drawdown** and a higher Sharpe.

So the honest leverage verdict is split: **unlevered**, simple statics beat the active book on Sharpe.
**Once you lever a static to match the active book's return**, the active book's tail-control wins — the
financing cost and amplified DD make levered-static a *worse* deal than the active book at equal return.
A young investor who wants more return than an unlevered Permanent Portfolio is better served by the
active book than by margining the static — but is **equally well served** (Sharpe-wise) by just holding
the unlevered static and accepting its lower CAGR. **Caveats stated:** LETF/daily-reset decay, 4.5%
margin is variable and can spike, and a levered -25% drawdown is behaviorally brutal — most retail
investors capitulate there.

---

## 5. The behavioral / effort tax (the part a backtest hides)

| | active 70/30 book | static (e.g. Permanent Portfolio) |
|---|---|---|
| Monthly turnover | XS ~0.38 + TF-inverse ~0.54/mo (~6-10 trades/mo across two sleeves) | ~0 between rebalances; a few % drift snap; ~1-4 trades/quarter |
| Decisions / discipline | rank 30 ETFs monthly, run a vol-targeted inverse-ETF short sleeve, regime gate, partial rebalance | hold 4-5 fixed weights; rebalance quarterly |
| Behavioral hazard | **sitting in cash / short during bull runs** (underperforms SPY in every bull — see 2016-2026), tracking error vs friends in 100% SPY | drift only; nothing to second-guess |
| Execution/slippage risk | real (inverse-ETF spreads, whipsaw, two sleeves to keep in sync) | negligible |
| Overfit / forward-decay risk | momentum + TF are heavily published; OOS held but edge not guaranteed | none — fixed weights |

The active book asks for **monthly attention, an inverse-ETF short sleeve, and the discipline to hold
cash through bull markets** — and the OOS evidence says it **does not earn a higher Sharpe** for that
effort than weights you set once and ignore. For a small bankroll the realistic **execution + discipline
tax** (mistimed rebalances, abandoning the system mid-drawdown, slippage on the inverse leg) is exactly
the tax a static portfolio **avoids entirely** — which tilts the practical comparison **further** toward
static.

---

## THE HONEST QUESTIONS — answered

**(a) Does the active book beat the best static on Sharpe AND maxDD, net, OOS? By how much?**
**No — not on Sharpe.** Full sample: active 0.81 vs Permanent Portfolio **0.93** (active *loses* by
~0.12). OOS: active 0.91 vs Permanent Portfolio **1.06** / risk-parity **1.05** (active *loses* by
~0.15). The active book **only wins on maxDD/worst-year** (full -13.6% vs PP -17.6%, ~4pp shallower;
OOS -12.6% vs -17.6%, ~5pp) and on 2022-specific crisis alpha. It does **not** win on both axes; it wins
one (tail) and loses the headline one (Sharpe).

**(b) Is the margin big enough to justify the monthly effort, turnover, tracking error, behavioral
difficulty?** **No.** The margin on Sharpe is **negative**. The only positive margin is ~4-5pp of
maximum drawdown and a better worst-year — a genuine but **modest** tail improvement that costs monthly
work, an inverse-ETF short sleeve, and the discipline to underperform every bull market. For most small
investors that trade is **not worth it**.

**(c) For a small bankroll, does the edge survive the realistic execution/discipline tax?** **It gets
thinner, not bigger.** The static avoids that tax by construction; the active book pays it twice (two
sleeves, inverse-ETF whipsaw, cash-during-bulls behavioral strain). Net of the realistic tax, the
active book's *only* surviving advantage (the shallower drawdown) is partly eaten by execution slippage,
while its Sharpe deficit vs static is unchanged. **The realistic small-bankroll comparison favors the
static even more than the gross backtest does.**

---

## VERDICT — for a US small-bankroll investor

**Simple wins on the metric the brief asked about. Say it loudly: a boring static mix ties-or-beats the
active book risk-adjusted, net of costs, in-sample and out — so the complexity is NOT worth it for most
small investors.** Concretely:

- **On Sharpe (the headline): static WINS.** Permanent Portfolio 0.93 full / 1.06 OOS and inverse-vol
  risk-parity 0.84 / 1.05 both **beat** the active 70/30 book (0.81 / 0.91). Even a literal 60/40 ties it
  OOS. The active book does not earn a risk-adjusted premium for its effort.
- **What the active book genuinely buys (the honest "X"):** the **smallest maximum drawdown and best
  worst-year** of anything tested (-13.6% / -4.8% full, -12.6% / -1.7% OOS) and unique 2022-style
  stock+bond-crash robustness. If your single overriding objective is *minimize peak-to-trough pain and
  survive a simultaneous stock+bond selloff*, the active book delivers ~4-5pp shallower max drawdown than
  the best static — that is the entire payoff, and it is real.
- **But:** that DD edge is *modest*, costs monthly effort + an inverse-ETF short sleeve + the discipline
  to trail every bull market, and in the classic GFC/COVID crashes a static **25% bonds + 25% gold**
  Permanent Portfolio actually drew down **less** than the active book. The active book's crisis crown is
  really a *2022* crown.
- **Leverage angle:** unlevered, the static beats the active book on Sharpe; but if you *lever* a static
  to the active book's return, financing drag + amplified DD make the levered static *worse* (PP 1.4x:
  Sharpe 0.75, maxDD -25% vs active 0.81, -13.6%). So "lever a simple portfolio" is **not** a free win
  either — it's a credible CAGR competitor but a worse risk-adjusted/tail deal than the active book.

**Bottom line / recommendation:** *"The complexity buys you about 4-5 percentage points of maximum
drawdown and genuine 2022-style crash robustness — and nothing on Sharpe. For a US small bankroll, hold
an unlevered Permanent Portfolio or inverse-vol risk-parity (Sharpe ~0.9-1.0, maxDD ~-18-20%, zero
effort) unless minimizing drawdown is your single dominant goal, in which case the active 70/30 book's
~4-5pp shallower DD may justify the monthly work — for most people, it does not."* Static effectively
ties-or-beats the active book; the boring portfolio is the honest default.

**Honest caveats both ways:** (1) the equal-footing window starts 2007 (gold/commodity ETF inceptions);
a longer SPY/60-40 history exists but can't include GLD/DBC/PP on equal footing. (2) The statics enjoy a
17-year tailwind for **bonds and gold** that may not repeat — if bonds/gold mean-revert to poor returns,
the Permanent Portfolio's Sharpe falls and the active book (which rotates *out* of falling assets) could
look relatively better forward; the 2022 result is exactly this scenario, and is the active book's best
argument. (3) Momentum + TF are heavily published; OOS held but no edge is guaranteed forward. (4) All
results net of 3 bps/side; the active book's higher turnover means it is *more* cost-sensitive than the
statics, another small thumb on the scale toward simple.
