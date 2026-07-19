# VRP-REGIME — does a vol-regime signal time/size the Polymarket short-vol longshot edge?

**Verdict: NULL — and directionally backwards from the hypothesis.** The confirmed
short-vol premium is **effectively unconditional.** Conditioning on any entry-time
volatility-regime signal does **not** raise the Sharpe frontier; with the pre-registered
(theory-implied) sign, **every one of 18 walk-forward sizing rules LOWERS Sharpe** vs the
blanket sell. The premium is actually *larger* in the weeks the hypothesis predicted it
would be *smaller*.

Run: `python3 vrp_regime.py` → `vrp_regime_summary.json`. Written independently.

---

## Setup

- **Edge under test:** SELL far-OTM weekly "BTC/ETH above $X on `<date>`" longshots at YES
  mid ∈ [0.15,0.30], zero-fee Polymarket. Seller PnL/ct (conservative **bid** fill) =
  `(entry − half_spread) − yes_win`.
- **Sample:** 601 settled longshots, **49 resolution-weeks** (2025-08 → 2026-07), BTC+ETH
  (from `scratchpad/advsel_rows.json`, the same dataset the LONGSHOT-CONDITIONAL null used).
- **Unconditional baseline:** mean **+10.57c/ct**, week-clustered **t = 4.27** — re-confirmed.
- **Regime features, all observed as-of the market START** (`end − horizon_days`, strictly
  before the first-half entry → no lookahead):
  - Realized vol: Binance Vision **spot 1d** klines → trailing **RV7, RV30** (annualized %),
    `rv_trend = RV7−RV30`, `trend30`, `drawdown30`.
  - Implied vol: **Deribit DVOL** index (BTC, ETH), 12h resolution, as-of entry.
  - **VRP7 = DVOL − RV7**, **VRP30 = DVOL − RV30** (the implied-minus-realized premium).
  - Funding: Binance Vision futures `fundingRate`, trailing 7d mean.
- **Hypothesis (pre-registered sign):** premium **larger** when VRP/DVOL **high**; **smaller**
  when realized vol (RV7/RV30/rv_trend) **high**.

---

## 1. Per-regime tercile split (in-sample, descriptive) + week-clustered HIGH−LOW spread

| signal | exp | LOW tercile | HIGH tercile | **HIGH−LOW spread** |
|---|---|---|---|---|
| **vrp7** | + | +14.44c (t 5.58) | +5.47c (t 1.42) | **−8.97c (t −2.05)** |
| vrp30 | + | +14.45c (t 5.78) | +8.08c (t 1.54) | −6.38c (t −1.12) |
| dvol | + | +10.92c (t 3.65) | +9.48c (t 3.25) | −1.43c (t −0.47) |
| **rv7** | − | +8.51c (t 2.50) | +13.98c (t 5.45) | **+5.46c (t +1.54)** |
| rv30 | − | +12.84c (t 4.41) | +13.24c (t 5.20) | +0.40c (t +0.11) |
| rv_trend | − | +9.18c (t 2.51) | +13.35c (t 3.30) | +4.17c (t +0.75) |
| trend30 | ? | +12.37c (t 3.66) | +11.54c (t 3.76) | −0.82c (t −0.19) |
| drawdown30 | ? | +13.92c (t 5.30) | +11.88c (t 3.86) | −2.04c (t −0.59) |
| funding | ? | +8.43c (t 2.05) | +12.62c (t 4.58) | +4.19c (t +0.91) |

**Every sign is the OPPOSITE of the hypothesis.** The premium is *bigger* when VRP is **low**
(implied ≈/below realized, i.e. realized vol elevated) and when realized vol is **high** — not
when implied richly exceeds realized. The single largest spread (vrp7, t=−2.05) points the
wrong way and does not clear the multiple-testing bar (below). Every regime *still earns a
positive premium* — even the "worst" high-VRP tercile is +5.5c — which is why timing can't help.

**Mechanism read:** this is a lottery/overpricing premium, roughly constant in
probability terms (band longshots settle YES ~10.5% while priced ~22%). It is not a
vol-risk-premium that concentrates in high-implied weeks; if anything high-VRP weeks are the
*calm, more-efficiently-priced* ones where the retail overpricing is slightly smaller.

---

## 2. Walk-forward sizing rules vs unconditional (Sharpe) — the decisive test

Warmup 16 wk, **33 applied weeks**. Regime threshold = trailing **median** of the weekly
signal over weeks **strictly before** t. Sizes normalized to mean 1 (same average capital),
so Sharpe changes reflect *timing only*. Weekly PnL/ct series; Sharpe is weekly (×√52 = annual).

**Unconditional blanket sell (applied window):** mean **+10.70c/wk**, sd 15.26c,
weekly-Sharpe **0.701** (annualized 5.06).

**Result: 0 of 18 rules beat it.** Best conditional = `rv30·proportional` at Sharpe 0.549
(**ΔSharpe −0.153**). The pre-registered primary (`vrp7·binary_top`, size up in high-VRP weeks)
collapses to Sharpe **0.239** (**ΔSharpe −0.462**, annualized −3.3) — it concentrates capital
in exactly the *lower*-premium weeks.

| rank | rule | cond Sharpe | ΔSharpe vs unc |
|---|---|---|---|
| best | rv30 · proportional_rank | 0.549 | −0.153 |
| … | vrp30 · proportional_rank | 0.512 | −0.190 |
| worst | trend30 · binary_top | 0.224 | −0.477 |
| primary | **vrp7 · binary_top** | **0.239** | **−0.462** |

Full table in `vrp_regime_summary.json` / console output.

### Robustness: even sign-mined, the gain is marginal and unjustifiable
If we **grant the adversary the empirically-favored sign** (choose orientation with hindsight,
still walk-forward), only **7 / 18** rules beat unconditional and the **max Sharpe is 0.881**
(vs 0.701) — a modest +0.18 that (a) requires committing to the **anti-theoretical** direction
(size up when realized vol is *high* / VRP *low*), (b) is not supported by any per-regime spread
clearing significance, and (c) is pure sign data-snooping. The honest, pre-committed-sign result
is **0 / 18**.

---

## 3. Multiple testing

**27 tests:** 9 signals × (1 per-regime HIGH−LOW spread test + 2 walk-forward rule types).
Family-wise Bonferroni |t| threshold at α=0.05 (normal approx) = **3.11**. The largest
per-regime spread statistic is |t| = 2.05 (vrp7, wrong sign) — **nothing clears the bar.**

---

## Blunt verdict

**Regime timing does NOT raise the frontier. It lowers it.** The +0.12/ct short-vol premium
is **effectively unconditional** across VRP, DVOL, realized-vol level, realized-vol trend,
momentum, drawdown, and funding regimes. The one economically-motivated bet — "size up when
implied richly exceeds realized" — is **the single worst walk-forward rule** (ΔSharpe −0.46),
because the premium is a roughly-constant retail-overpricing effect that, if anything, is
*fatter* in higher-realized-vol / compressed-VRP weeks, not the reverse.

This mirrors the prior LONGSHOT-CONDITIONAL null (moneyness/demand didn't sharpen per-trade EV):
now a *vol-based* signal fails the **Sharpe/timing** bar too. **Trade the edge unconditionally
(blanket sell, fractional/capital-bounded sizing); do not add a vol-regime overlay.**

Candidate status: **DEAD** (VRP-REGIME null). Confirmed edge re-validated unconditional
(+10.6c, t=4.27).
