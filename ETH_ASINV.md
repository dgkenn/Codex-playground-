# ETH 15-min Avellaneda-Stoikov Inventory-Skewed Maker

**Verdict: NEGATIVE. No positive-EV A-S inventory maker exists on Kalshi ETH 15-min.**
Inventory-skew does NOT overcome the structural adverse selection. It actually *raises*
the strand rate (38% -> 73%), and every toxicity/spread lever only reduces participation,
shrinking the loss monotonically toward (but never crossing) zero. Do not deploy.

Study: `eth_asinv_study.py`. IS = first 60% of windows (1431), OOS = last 40% (954).
Maker fee = 0 (fee-advantaged). Backtest SCREENS only; forward-validation required before any
deployment decision (and the screen already kills it).

---

## 1. A-S model (adapted to a 15-min binary, |net|<=1 cap)

```
microprice  m_k     = YES mid_k
reservation r_k     = m_k - q * gamma * sigma_k^2 * tau_k        q in {-1,0,+1}
half-spread delta_k = gamma * sigma_k^2 * tau_k / 2 + (1/gamma)*ln(1+gamma/kappa) + base_extra
post bid  pb = r_k - delta_k     post ask  pa = r_k + delta_k    (YES price/cent units)
```
- `sigma_k` = realized intra-window vol of the YES mid up to minute k (std of minute-to-minute mid
  changes), in PRICE units so the skew/spread terms are in cents.
- `tau_k = (15-k)/15`, minutes 2..12.
- **Inventory cap = the binary skew mechanism:** q=0 posts both sides; q=+1 posts ask only
  (must reduce); q=-1 posts bid only. This is the strongest possible inventory aversion under |net|<=1.
- Quotes clamped to never cross the touch (`pb<=b0`, `pa>=a0`): A-S widening => post behind touch
  => fewer crossings => lower fill prob (the realistic cost of inventory aversion).

### Calibration (from the ETH tape)
| param | value | source |
|---|---|---|
| kappa (fill intensity) | **14.3 / cent** | MLE 1/mean(taker print distance from mid); mean dist = 7.0c over 1.22M prints |
| sigma (realized YES-mid vol @ k=7) | **9.5c** (median) | per-minute mid-change std; sigma^2 ~ 0.91 cent-units |
| gamma (risk aversion) | swept 0.25 .. 6.0 | calibrated below |
| maker fee | 0 | fee-advantaged |

Note: sigma is *large* (9.5c) — ETH 15-min YES mid is very noisy — so for gamma>=1 the A-S half-spread
term `gamma*sigma^2*tau/2` alone is many cents, pushing quotes far behind touch.

### Fill model (the load-bearing part)
Resting maker quotes for minute k fill ONLY when a taker crosses them in the next ~2 min (same horizon
the harness `window_fills` uses):
- resting bid at `pb` fills if a taker SELL prints at `p <= pb`;
- resting ask at `pa` fills if a taker BUY prints at `p >= pa`.

Residual inventory at expiry settles at `res_up` (YES) / `1-res_up` (NO): **the inventory you are stuck
with when price ran IS the loss.** This is modeled exactly, not approximated.

**Fill-model caveats:** (a) crossings are detected at the touch-clamped quote, so improving inside the
touch is allowed but never *through* it; (b) queue position is not modeled (we assume any taker print
at/through our price fills us — optimistic, favors the strategy, and it still loses); (c) one fill per
side per minute (first crossing); (d) latency/cancel dynamics ignored.

---

## 2. A-S vs NAIVE BOX (P0) — full A/B set

| | net | Sharpe | Win% | t vs 0 | fills/win | strand% |
|---|---|---|---|---|---|---|
| **IS**  P0 naive box (dead) | -10.18c | -0.397 | 34.2% | -15.00 | — | 42.4% |
| **IS**  A-S maker (g=1.5)   | -10.78c | -0.320 | 33.2% | -12.12 | 5.27 | **73.4%** |
| **OOS** P0 naive box (dead) | -13.15c | -0.502 | 31.9% | -15.50 | — | 38.1% |
| **OOS** A-S maker (g=1.5)   |  -9.26c | -0.283 | 34.5% |  -8.75 | 5.21 | **72.7%** |

A-S trims the OOS loss vs the naive box (-13.15c -> -9.26c) but stays deeply negative (t=-8.8). Crucially
the **strand rate nearly doubles (38% -> 73%)**: one-sided posting under the cap means once you hold a
leg you can only pair by waiting for a taker to cross the *opposite* skewed quote, which on a trending
window never arrives — so you hold to settlement far more often. The skew makes inventory accumulation's
*consequence* worse, not better.

---

## 3. Gamma x base-spread sweep (kappa=14.3)

| gamma | base | IS net | IS t | OOS net | OOS Sh | OOS t | OOS f/win | strand |
|---|---|---|---|---|---|---|---|---|
| 0.25 | 0.0c | -9.47c | -10.5 | -10.01c | -0.302 | -9.33 | 5.02 | 74.4% |
| 0.25 | 2.0c | **-7.51c** | -8.5 | -8.92c | -0.274 | -8.46 | 4.22 | 73.3% |
| 1.00 | 2.0c | -7.78c | -8.8 | -9.16c | -0.282 | -8.72 | 4.29 | 72.9% |
| 1.50 | 0.0c | -10.78c | -12.1 | -9.26c | -0.283 | -8.75 | 5.21 | 72.7% |
| 4.00 | 0.0c | -10.86c | -12.5 | -10.59c | -0.341 | -10.54 | 5.42 | 68.7% |
| 6.00 | 0.0c | -10.47c | -12.3 | -11.43c | -0.372 | -11.48 | 5.60 | 67.5% |

- **Aggressive skew (high gamma) HURTS**, it does not help: bigger gamma -> wider, more lopsided quotes ->
  *more* strands relative to pairs and worse net (g=6 OOS -11.4c). The "avoid accumulating inventory"
  intuition fails on a binary because the avoidance just means you sit holding the leg you already have.
- The only lever that helps is the flat `base_extra` widening (g=0.25, base=2c) — and it helps *only* by
  cutting participation (fills/win 5.0 -> 4.2). Best-by-IS is still **-7.51c IS / -8.92c OOS, t=-8.5**.

A direct skew-aggression test (multiply the inventory term by 0..4x at g=0.25) confirms it: OOS net is
flat at ~-8.9c across all skew strengths — skew neither helps nor kills, it is simply irrelevant to the
sign of the result.

---

## 4. Toxicity extension (Glosten-Milgrom widening / quote-pull), g=0.25, base=2c

| variant | IS net | IS t | OOS net | OOS Sh | OOS t | f/win | strand |
|---|---|---|---|---|---|---|---|
| A-S only (no tox) | -7.51c | -8.5 | -8.92c | -0.274 | -8.46 | 4.22 | 73.3% |
| + VPIN widen 6x | -5.98c | -6.7 | -7.20c | -0.219 | -6.77 | 3.46 | 70.2% |
| + VPIN pull>0.55 | -5.81c | -6.7 | -6.94c | -0.214 | -6.60 | 3.46 | 68.7% |
| + VPIN pull>0.50 | -5.41c | -6.3 | -5.47c | -0.167 | -5.16 | 3.11 | 66.5% |
| + widen6 + pull0.50 | **-4.74c** | -5.5 | **-5.28c** | **-0.163** | **-5.02** | 3.01 | 64.7% |

Toxicity-widening + pull beats inventory-skew alone — but the mechanism is pure participation reduction
(fills/win 4.2 -> 3.0). The combined best (widen6 + pull0.50) is the least-negative config found:
**-4.74c IS / -5.28c OOS, Sharpe -0.16, t=-5.0**. Extrapolating the trend (less trading -> less loss)
to its limit is "post nothing" = 0c. There is no interior +EV point.

---

## 5. Why it cannot cross +EV — PnL decomposition (OOS, g=0.25, base=2c)

| component | mean / win |
|---|---|
| paired-box spread PnL (completed boxes) | **+3.34c** |
| residual-inventory settle PnL (strands) | **-12.27c** |
| total | -8.93c |
| paired-box margin when a box completes | +4.36c |
| strand-window settle (the 73% that strand) | -16.72c |

The spread capture on *completed* boxes is genuinely positive (+3.3c, +4.4c/box). The entire loss is the
strand-settle leg: on a 0/1 binary, the leg you are left holding when ETH ran settles to a ~16.7c loss,
and that swamps the spread ~4:1. **Inventory-skewing cannot help because:**
1. Under |net|<=1, "avoid accumulating inventory" = post one-sided once you hold a leg, which makes the
   held leg *harder* to pair (must wait for a taker to cross the opposite quote) -> strand rate 38%->73%.
2. Widening / pulling reduces the toxic-strand count, but proportionally reduces the good paired boxes too,
   so net moves monotonically toward 0 from below — never through it.

This is the same structural wall as the naive box: ETH 15-min mid is efficient, the toxic completion/strand
tail dominates, and a maker has no informational edge to price the residual inventory. A-S is the textbook
fix for *continuous* inventory + Gaussian terminal value; on a binary that settles 0/1 the terminal payoff
is all-or-nothing, the reservation-price skew has no continuous inventory to glide down, and the model's
core assumption (mean-reverting marginal inventory cost) does not hold.

---

## 6. Verdict + exact params

**No positive-EV Avellaneda-Stoikov inventory maker on Kalshi ETH 15-min.**

- Least-bad config found: **gamma=0.25, base half-spread=2c, VPIN widen 6x + pull>0.50, kappa=14.3.**
  - OOS: net **-5.28c/win**, EV/fill **-1.75c**, Sharpe **-0.16**, fills/win **3.01**, win% ~35%, t **-5.0**.
  - IS: net -4.74c, t -5.5. IS and OOS agree (no sign flip) — robustly negative.
- Pure A-S (gamma=1.5, base=0): OOS -9.26c, t=-8.8, strand 73%.
- vs the dead naive box: P0 OOS -13.15c, t=-15.5. A-S is less-bad but the same sign.
- **Skew rule finding: aggressive inventory skew HURTS** (g=6 -> -11.4c); skew strength is irrelevant to
  the sign (skew_mult 0..4x -> flat ~-8.9c). The only thing that helps is *trading less* (base spread,
  VPIN pull), which converges to 0 at the "post nothing" limit, never positive.

**Fill-model caveats:** queue position not modeled (we fill on any taker print at/through our quote — an
*optimistic* assumption that favors the strategy, yet it still loses); latency/cancel dynamics ignored;
one fill per side per minute. A more pessimistic (queue-aware) fill model would make the verdict *more*
negative, not less.

**Recommendation:** do not deploy. The structural adverse selection / 0-1 terminal-payoff problem is not
addressable by inventory-aware quoting. Consistent with prior findings that ETH mid is efficient and the
two-sided box is dead. Forward-validation unnecessary — the IS/OOS screen is decisive and one-directional.
