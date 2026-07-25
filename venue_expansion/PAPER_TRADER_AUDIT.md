# PAPER TRADER AUDIT — 2026-07-25

**Question asked:** is anything in the paper trader promising?

**Answer: no.** Two of the three paper sleeves have essentially no data. The third — the forecast
sleeve — reports **+$0.19/contract at t=8.8 over 261 settled forward trades**, which is the only
winner-shaped number anywhere in this system. It is an artifact of two independent bugs. Corrected
against Kalshi's own official settlement and true executable prices, the same 261 trades are
**−$0.053/contract, day-clustered t = −3.38** — significantly negative, not positive.

Reproduce: `python venue_expansion/forecast_paper_audit.py` then
`python venue_expansion/verify_settlement_truth.py` (both read-only, public endpoints, no auth).

---

## 1. The three sleeves

| Sleeve | Settled fires | Verdict |
|---|---:|---|
| Forward paper gate (live taker mechanism) | **0** | No data in 7 days live. 398 near-misses, **397 of them at ask = 100c** |
| Early-lock | **2** | Both entered at ask = 100c → pnl exactly $0.00. Gate needs n≥30 |
| Forecast | **261** | Headline +$0.19/ct is two bugs; corrected it is **−$0.053/ct, t=−3.38** |

### 1a. The forward gate has nothing to measure

398 near-misses over 6 days (66/day). Every one logged `reason: "ask>98"`. The ask distribution is
**397 at 100c, 1 at 99c** — and at 99c the Kalshi fee `ceil(7·p(1−p))` is 1c, so that single fire
nets exactly **0c**. There is no threshold relaxation that rescues this population: the contracts
are priced at the payout ceiling. Capture rate 0/398, Wilson 95% CI [0%, 0.96%].

The counterfactual ceiling — if every near-miss had somehow filled at the 98c gate threshold — is
+1c/ct net × 66/day × DEPTH_CAP 25 = **$497/mo**, and that number has never been approached (0 fills).

This is not a slow-detection problem. It confirms `WX_NEARMISS_DIAGNOSIS.md`: the market is already
at 100c before the lock rule can confirm.

### 1b. Early-lock is not accruing at a usable rate

n=2 settled in 6 days, both at `yes_ask_c = 100` → **pnl $0.00 by construction**. At 0.33 fires/day
the n≥30 gate is ~90 days away, not the ~29 days `RESEARCH_LEDGER.md` projected. Both fires also
carry zero economic content for the same reason as §1a.

---

## 2. The forecast sleeve: how +$0.19/ct becomes −$0.053/ct

261 settled forward trades, 2026-07-19..23, 5 distinct days, all `lead_days=0`, HIGH markets,
82 YES / 179 NO.

| Arm | n | win% | EV/ct | day-clustered t |
|---|---:|---:|---:|---:|
| (a) as-logged — what the sleeve reports | 261 | 53.3% | **+0.1905** | +8.81 |
| (b) NO cost = 1 − yes_ask (naive fix, still wrong) | 261 | 53.3% | +0.0892 | +9.94 |
| (c) true executable cost, sleeve's own outcomes | 261 | 53.3% | +0.0739 | +8.84 |
| (d) **true cost + Kalshi's OFFICIAL settlement** | 261 | **40.6%** | **−0.0526** | **−3.38** |
| (d) YES only | 82 | 8.5% | −0.0304 | −1.82 |
| (d) NO only | 179 | 55.3% | −0.0627 | −3.91 |

### Bug 1 — NO contracts charged the YES ask as their cost (known, never fixed)

`wx_forecast_forward.py:207`:

```python
price = r["price"]                 # this is ALWAYS yes_ask_c/100
fee   = _kalshi_fee(price)
pnl   = (1.0 - price - fee) if won else (-price - fee)
```

Correct for a YES buy; wrong for a NO buy, which costs `1 − yes_bid`, not the YES ask. 179 of 261
trades are NO. `RESEARCH_LEDGER.md` flagged this in the 2026-07-22 forecast-overlay refutation
("a `settle()` accounting bug — NO-side priced at YES cost"); the sleeve was left running with the
bug in place, so every number it has emitted since is contaminated.

The naive correction (`1 − yes_ask`) is *also* wrong and flatters the result — that is the NO **bid**,
the price you'd get selling. `forecast_paper_audit.py` recovers the real cost from Kalshi's 1-minute
candlestick `yes_bid`/`yes_ask` at each trade's own `issued` timestamp (first candle **at or after**
the signal — no best-price-in-window look-ahead). Measured spreads are genuinely tight (median 1c,
p75 2c) and the logged ask matches the measured ask (median 0c apart), so this correction is small
and honest: **+0.1905 → +0.0739**. Execution realism is *not* what kills this sleeve — worth stating,
because it is what killed graveyard entries #20, #30, #33 and #34.

### Bug 2 — settlement boundary off-by-one (new finding; this is the kill)

`wx_forecast_model.bracket_prob` computes `P(lo < X ≤ hi)`, and `settle()` scores outcomes with the
matching `_bracket_won(lo, hi, realized)` — lower bound **exclusive**, justified in the docstring as
"mirroring Kalshi's '>' settlement". That is right for a threshold rung (`T93` = above 93) and wrong
for a bracket rung: Kalshi's bracket **includes its floor**.

Verified against Kalshi's official `result` field for all 256 tickers in the log:

**37 of 261 trades (14.2%) were scored against the wrong outcome — every single one in the same
direction**, and every one is the same case: realized temperature lands exactly on the bracket's
lower bound, the sleeve declares NO, Kalshi settled YES.

```
KXHIGHTBOS-26JUL19-B81.5   lo=81 hi=82  IEM=81.0  sleeve_yes_won=False  OFFICIAL=yes  side=no  logged_pnl=+0.45
KXHIGHAUS-26JUL19-B95.5    lo=95 hi=96  IEM=95.0  sleeve_yes_won=False  OFFICIAL=yes  side=no  logged_pnl=+0.34
KXHIGHTOKC-26JUL19-B94.5   lo=94 hi=95  IEM=94.0  sleeve_yes_won=False  OFFICIAL=yes  side=no  logged_pnl=+0.47
KXHIGHNY-26JUL20-B81.5     lo=81 hi=82  IEM=81.0  sleeve_yes_won=False  OFFICIAL=yes  side=no  logged_pnl=+0.59
   ... 33 more, all identical in shape
```

Whole-degree temperatures land on a 2°F bracket's lower edge roughly half the time it lands in the
bracket at all, and the sleeve is 69% NO trades — so the bug manufactures fake NO wins at scale.
Fixing it alone moves the sleeve from **+0.0739 to −0.0526/ct (t = −3.38)**.

### Independent confirmation: the model has no skill

Scored on official outcomes, at the signal timestamp:

- **Model Brier 0.2914** vs **market Brier 0.1724** — the market is far better calibrated.
- A constant prediction at the base rate (85/256 ≈ 0.33) would score ≈0.22. **The model is worse
  than a constant.**
- Calibration is not merely weak, it is inverted in the mid range: `fc_prob` 0.6–0.8 → realized YES
  **11.1%** (n=9); `fc_prob` 0.0–0.2 → realized YES **37.8%** (n=143).

This is the same conclusion `FORECAST_OVERLAY_BACKTEST.md` and `WEATHER_ENSEMBLE.md` already
reached by other routes: Kalshi prices public weather forecasts better than this fitted-Gaussian
model does. The forward paper log is now a third independent confirmation rather than a survivor.

---

## 3. The live money path does NOT share Bug 2

`kwx_runner.locked_orders` gates on margin-buffered strict inequalities:

```python
if cap is not None and extreme_f > cap + margin:        _consider(..., "no", ...)
elif cap is None and floor is not None and extreme_f > floor + margin:  _consider(..., "yes", ...)
...
if floor is not None and extreme_f < floor - margin:    _consider(..., "no", ...)
```

With `margin` ≥ 1.0°F the exact-boundary case can never be the deciding comparison, so the live
lock rule is not exposed to the off-by-one. The bug is confined to the forecast paper sleeve's
scoring. Stated explicitly because this is the path that touches real money.

---

## 4. Housekeeping found along the way

- `kwx_portfolio_state.json` still lists `forecast: $3.47` deployed and is stale at day `2026-07-20`
  (5 days old) — a refuted sleeve carrying registry exposure.
- `kwx_forward_settled.jsonl`, `kalshi_weather_settled.jsonl`, `kwx_runner_plan.jsonl` and
  `kwx_exec_log.jsonl` are all **empty** on the live branch.
- The forecast and early-lock workflows keep committing paper rows on cron, so the contaminated
  ledger grows every few hours until the sleeve is stopped or `settle()` is fixed.

---

## 5. Bottom line

Nothing in the paper trader is promising. Two sleeves have no data; the third's apparent edge was
one known-and-unfixed accounting bug stacked on one previously undetected settlement bug, and the
corrected sign is negative with the model measurably worse than a constant predictor.

The honest recommendation is to fix `_bracket_won`/`bracket_prob` to inclusive-floor and the
NO-side cost in `settle()` **regardless** of what happens to this sleeve, because every future
bracket-market study in this repo will inherit both. Then either stop the forecast sleeve or let it
accrue clean rows from scratch — the existing 261 rows cannot be salvaged, only rescored, and
rescored they are negative.
