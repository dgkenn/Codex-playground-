# Kalshi Weather Trading Strategy — Selection, Maker Execution, Kelly/Portfolio Sizing, Capacity

**Date:** 2026-06-14 · **Branch:** `claude/polymarket-bot-live-ready-vw7ut5`
**Companion research:** `KALSHI_WEATHER.md` (the mispricing study) · **Model:** `nbm_fairvalue.py` +
`compare_kalshi_nbm.py` (sibling agent is maximizing this) · **Sizing/metrics engine:**
`weather_strategy_sim.py` (this deliverable).

## SCREENS / honesty banner (read first)
- **Every metric below is CONDITIONAL on the model being calibrated.** A sibling agent owns the
  model; here it is the `Normal(TXN, XND)` NBM fair value. The edge is *unproven* until
  `weather_clv_harness.py` produces **30–45 trading days / ≥150–300 settled buy-signals** of forward
  CLV + settlement. This document is the *plan you deploy IF calibration holds*, plus the exact data
  to confirm it.
- **No historical price backtest exists** (Kalshi has no public weather-book archive; NOMADS NBS
  bulletins rotate off within days; the live API was 429-rate-limited from this CI). So the metrics
  come from a **parametric Monte-Carlo** (`weather_strategy_sim.py`), not a price replay. The inputs
  (edge size, fill rate, adverse selection, correlation) are the things the harness must measure.
- **Maker fills are NOT guaranteed.** The realized edge is modeled as **far below** the theoretical
  snapshot edge after (a) a 35–55% fill rate and (b) adverse-selection shading on the filled subset.
- The simulator's **CAGR figures are optimistic** (quarter-Kelly compounding on a high per-bet edge
  with frictionless reinvestment). The **robust, defensible headlines are the Sharpe and the absolute
  $/day at saturation** — NOT the CAGR. Treat CAGR as an upper-bound illustration.

---

## 1. SIGNAL / SELECTION — what to trade

**Edge thesis (from `KALSHI_WEATHER.md`):** Kalshi prices the **modal temperature bin efficiently**
(off the same NBM guidance) but **under-prices the bin just above the mode and the warm tail** —
the recreational signature (bettors anchor on the headline forecast high, under-weight the right
side of the distribution). The center is a dead-end; the edge lives in distribution *shape*.

**Selection rule (entry):**
```
TRADE bracket b in city c at lead L  IFF
   (1)  b is OFF-MODAL: the bin ABOVE the NBM modal bin, OR a WARM-TAIL bin (>= mode+2 bins / "X or above")
   (2)  edge = nbm_p(b) - kalshi_ask(b)  >=  THRESH                 # clears the maker spread
   (3)  kalshi_ask in [0.04, 0.40]                                  # cheap off-modal/tail prices
   (4)  |edge| not "extreme": if edge > 10c, SHRINK it (model-error haircut, sec.5)
   (5)  city is in the liquid set {NYC, CHI, MIA, AUS, LAX, PHX, DAL, BOS}
   (6)  lead L = NEXT-DAY (tomorrow's event). NOT same-day (book converges to live obs within the hour),
        NOT >2 days (NBM σ widens, edge unconfirmable).
```
- **THRESH:** start at **+3c maker** (clears a 1–2c maker rest + a calibration safety margin). The
  snapshot showed +3 to +14c nominal; assume the real, fillable edge is **low-single-digit cents**.
- **Where the edge is biggest/most reliable (to confirm with the harness, ranked priors):**
  - **Bracket position:** *bin directly above the modal bin* (most consistent, e.g. snapshot NYC
    82–83, CHI 78–79) and the *near warm tail* ("X or above" one step out). The deep far tail has
    edge too (DAL/BOS "86+") but is **rarer + thinner + most model-dependent** → size smallest.
  - **Cities:** softest recreational flow first. Heuristic prior: high-retail-interest, weather-as-
    -entertainment cities (NYC, CHI) over technical/desert-stable ones (PHX, LAX where σ≈1 and the
    distribution is tight). Confirm per-city net edge from the harness before weighting up.
  - **Lead:** **next-day only.** The lag edge is ~0 (NBM day-ahead moves 0–1°F; same-day book tracks
    obs), so the edge is purely the distribution-shape mispricing, best captured a full day ahead as
    a resting maker order while recreational flow accumulates.
- **NEVER trade:** the modal bin (efficient), rain/snow (lumpier, worse model), longer-horizon
  climate series, or any bracket where you cannot rest as maker.

---

## 2. EXECUTION — maker vs taker, fill-rate model

**Maker is the entire edge.** Kalshi taker fee = `round(0.07·P·(1−P), 2)` per contract per side;
**maker = 0**. From `weather_strategy_sim.py` per-bet table (q = price, edge = p−q):

| price q | edge | maker EV/bet | taker fee | taker EV/bet | fee as % of edge |
|--------:|-----:|-------------:|----------:|-------------:|-----------------:|
| 0.08 | 0.03 | **+0.030** | 0.010 | +0.020 | 33% eaten |
| 0.15 | 0.03 | **+0.030** | 0.010 | +0.020 | 33% eaten |
| 0.15 | 0.06 | **+0.060** | 0.010 | +0.050 | 17% eaten |
| 0.25 | 0.03 | **+0.030** | 0.010 | +0.020 | 33% eaten |

At a 3c edge the **taker fee eats ~1/3 of the edge** — fatal at the threshold. **Rule: maker-only.**
If you can't rest, you don't trade.

**Where/when to rest:**
- Rest the YES bid **at-or-1c-inside** the bracket's fair value (rest at `min(nbm_p − margin, current_ask − 1c)`),
  so you only get filled at a price that preserves edge.
- **Enter early** (evening before / overnight, right after a fresh NBM cycle) when the book is
  softest and recreational flow has not yet accumulated — you sit in the queue ahead of the flow.
- Re-quote on each new NBM cycle (hourly NBS); cancel if a cycle moves nbm_p below threshold.

**Fill-rate + adverse-selection model (the BRUTAL bar):** a resting order fills only when someone
crosses it, and crossers are partly informed, so the *filled subset* is adversely selected. The
simulator models:
```
p_fill          = base_fill                              # base_fill in 0.35..0.55 (you miss most)
p_win | filled  = p_true - info_share*(p_true - q)       # info_share 0.30..0.60 shades you down
```
- `info_share = 0` → fills random, full edge realized. `info_share = 1` → fills fully informed, edge → 0.
- **BASE assumption: base_fill 0.45, info_share 0.45.** This is why realized edge ≪ snapshot edge:
  you fill <half your quotes, and the half you fill is shaded ~45% toward the price. **Optimize for
  realized (filled) edge, not the theoretical snapshot number.**
- Settlement in the sim uses the *true unconditional* prob while your *expected* win used the
  adversely-selected prob → realized PnL < expected by construction. That gap is the honest cost of
  being a maker against informed crossers.

---

## 3. SIZING — the Sharpe engine (Kelly + portfolio)

**Per-bet Kelly on a binary** (buy YES at price q, true prob p):
```
f* = (p - q) / (1 - q)            # full-Kelly fraction of bankroll  ==  edge / odds
```
Implemented in `kelly_fraction()`. We deploy **quarter-Kelly (kelly_frac = 0.25)** with a **hard 2%-
of-bankroll cap per bet** (`kelly_cap`). Quarter-Kelly trades ~negligible long-run growth for a
**much smoother equity curve** (lower variance of log-growth → higher realized Sharpe) and robustness
to over-estimated edge (critical when calibration is unproven). The 2% cap enforces "small-per-bet"
and bounds single-bracket blow-ups.

**Sharpe from N ~independent bets** (`sharpe_from_N()`):
```
per-bet SR   = EV_bet / sd_bet
N_eff        = N_per_day / (1 + (k-1)*rho)      # within-day cross-city correlation cuts independence
annual SR    ≈ per-bet SR * sqrt(N_eff) * sqrt(252)
```
With edge = 4c, q = 0.15, k = 7 cities, **within-day rho = 0.5 (heat waves correlate cities)**:

| N bets/day | per-bet SR | N_eff | **annual Sharpe** |
|-----------:|-----------:|------:|------------------:|
| 5  | 0.102 | 1.2 | 1.81 |
| 10 | 0.102 | 2.5 | 2.56 |
| **14** | 0.102 | **3.5** | **3.03** |
| 20 | 0.102 | 5.0 | 3.62 |
| 14 (rho=0, idealized) | 0.102 | 14.0 | 6.06 |

**The correlation tax is large:** heat waves drag the effective independent-bet count from 14 down to
~3.5, roughly **halving the Sharpe** vs the naive independent assumption. Across-DAY independence is
the real diversification engine (252 weakly-correlated trading days/yr).

**Portfolio sizing rule:** size each bet at `min(quarter-Kelly·f*, 2% bankroll)`, then **pro-rata
scale the whole daily slate down to the capacity ceiling** (sec.4). Diversify across cities + brackets
+ days; cap correlated exposure (sec.5).

---

## 4. CAPACITY — $/day and saturation bankroll

Books are **thin: tens to low-hundreds of contracts at touch**, ~12–15 tradable brackets/day across
6–8 cities. Modeled ceiling **≈ $2,000/day deployable** before moving the book (conservative; could
be $1.5–2.5k). `weather_strategy_sim.py` saturation sweep (BASE edge, $2k/day ceiling):

| bankroll | deploy/day (med) | CAGR (illustrative) | Sharpe |
|---------:|-----------------:|--------------------:|-------:|
| $2,000   | $559   | ~5090% | 3.5 |
| $5,000   | $1,168 | ~2751% | 3.2 |
| $10,000  | **$2,000 (capped)** | ~1932% | 3.2 |
| $25,000  | $2,000 (capped) | ~943% | 3.0 |
| $50,000  | $2,000 (capped) | ~491% | 3.1 |
| $100,000 | $2,000 (capped) | ~250% | 3.2 |

- **$/day at saturation ≈ $1.5–2.5k deployed → ~$150–400/day net at base edge.**
- **Saturation bankroll ≈ $15–40k**: below it, quarter-Kelly wants less than the book offers and
  growth compounds; above it, you hit the $2k/day ceiling, **absolute $ profit plateaus** and
  **CAGR decays as ~1/bankroll** while Sharpe stays high. **This is a small-capacity, high-Sharpe,
  dollar-capped edge — it does NOT scale past low-$ thousands/day.** It is ideal for a small bankroll
  (the original appeal) and useless for size.

---

## 5. RISK CONTROLS

- **Model-error risk (the big one):** the largest snapshot edges are exactly where Kalshi *disagrees*
  with NBM — i.e. where the **model is most likely wrong**, per the calibration caveat. **Size DOWN on
  extreme disagreement:** the sim's `model_error_haircut` shrinks any edge > 10c toward a trusted band
  before sizing. Never full-Kelly a 14c "edge"; treat it as a model alarm, not a green light.
- **Within-day correlation (heat waves):** cap **≤ 1 bet per city per day** and **≤ N total/day**;
  treat the cross-city common factor as one risk (the N_eff tax in sec.3 already reflects it). Do not
  stack the same warm-tail thesis across all cities on a heat-wave day.
- **Settlement / station risk:** settles on the **final NWS CLI integer high** for a specific station
  (Central Park, Midway, etc.), midnight-to-midnight **Local Standard Time** (DST window shifts).
  Station/sensor quirks and the ±0.5°F rounding are real; the bracket-prob integration already does
  the rounding correction, but station mismatch (wrong station vs the series) is a silent killer —
  verify the settlement station per series.
- **Drawdown control:** quarter-Kelly + 2% cap → BASE median maxDD ~ −32% (worst-5% ~ −54%); BEAR
  ~ −24%. Add a **kill-switch**: if rolling realized Brier/calibration of `nbm_p` degrades or 20-day
  PnL breaches a floor, **stand down** until the harness reconfirms calibration.
- **Liquidity risk:** maker-only; never chase as taker; cancel stale quotes on each NBM cycle.

---

## 6. EXPECTED METRICS (conditional on calibration) + DATA TO CONFIRM

From `weather_strategy_sim.py` (quarter-Kelly, 2% cap, $2k/day capacity, 7 cities, rho per scenario):

| Scenario (edge / fill / adverse-sel / rho) | Sharpe (med, 10–90%) | Win-rate | MaxDD (med / worst5%) | Deploy/day |
|---|---|---|---|---|
| **BASE** (4c / 45% / 45% / 0.5) | **3.2 (2.5–3.9)** | ~21% | −32% / −54% | $2,000 |
| BULL (6c / 55% / 30% / 0.4) | 3.3 (2.8–4.0) | ~22% | −31% / −60% | $2,000 |
| BEAR (2.5c / 35% / 60% / 0.6) | 2.6 (1.5–3.4) | ~20% | −24% / −38% | $279 |
| **NOEDGE (selection-on-noise → should LOSE)** | **−0.05 (−1.5–1.1)** | 15% | −76% / −93% | $279 |

- **Win-rate is intentionally LOW (~20%)** — these are cheap off-modal/tail bins (q ≈ 0.10–0.25); +EV
  comes from the price being too low, not from winning often. Don't optimize for win-rate; optimize
  for filled-edge × N.
- **The NOEDGE sanity case loses money with negative Sharpe and ~−76% drawdown** — this is the trap
  the brutal bar warns about: if the apparent edge is selection-on-noise (model NOT calibrated),
  filtering on `edge ≥ 2c` selects upward noise that mean-reverts at settlement and you bleed the
  spread/adverse-selection. **This is exactly why the harness must confirm calibration BEFORE size.**
- **Honest headline (IF calibrated): Sharpe ~2.5–3.5, ~$150–400/day net, saturation bankroll
  ~$15–40k, win-rate ~20%, maxDD ~30%.** The high Sharpe is real *if the per-bet edge is real* — it
  comes from many small weakly-correlated daily bets. The CAGR numbers are upper-bound illustrations;
  do not quote them as expected return.

**Data needed to confirm (the gate):** run `weather_clv_harness.py` on cron (every 1–2h, next-day
events, 8 cities) for **≥ 30–45 trading days → ≥ 150–300 settled buy-signals**, then measure and plug
into `weather_strategy_sim.py`:
1. **Calibration:** Brier / log-loss / reliability of `nbm_p` vs CLI settlement — *is the model right?*
2. **Realized filled edge** per bracket-position and per city → `edge_mean`, `edge_sd`.
3. **Maker fill rate** and the **adverse-selection share** (win-rate on filled vs unfilled quotes) →
   `base_fill`, `info_share`.
4. **Within-day cross-city outcome correlation** → `city_rho`.
5. **Realized book depth** at the maker price → `capacity_per_day`.

Only then are the conditional metrics above de-conditioned. Until then: **paper/CLV only, no size.**

### Files (this deliverable)
- `WEATHER_STRATEGY.md` — this document.
- `weather_strategy_sim.py` — Kelly/portfolio sizing + Sharpe-from-N + fill/adverse-selection +
  capacity Monte-Carlo. Plug measured harness numbers into `simulate(...)` to de-condition.
- Reuses: `nbm_fairvalue.py`, `compare_kalshi_nbm.py`, `kalshi_weather_snapshot.py`,
  `weather_clv_harness.py` (model + book + forward CLV logger).
