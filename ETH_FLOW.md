# ETH 15-min Counterparty Flow Profiling

**Question (operator's dichotomy):** classify the ACTUAL takers in the Kalshi ETH
15-min tape by their order-flow footprint and decide — EITHER a smart sub-population
consistently WINS (so FOLLOW it) OR naive bettors consistently LOSE (so FADE them) —
and determine whether either yields an accessible positive-EV strategy at our latency
(seconds, not sub-ms).

**Data:** `trades_kalshi_eth15m.parquet` — 1,996,017 taker trades across 2,385 windows
(after dropping windows with <3 trades). Each trade: time, YES price `p`, size, aggressor
side `buy`. Settlement `res_up` from `hist`. Per-trade P&L to settlement:
buy YES at p → `res_up − p`; sell YES at p (= bought NO) → `p − res_up`.
IS = first 60% of windows (1,183,007 trades), OOS = last 40% (813,010 trades).
Trade-level informed features computed causally up to and including each trade:
same-side run length, sweep depth (consecutive same-side at worsening price),
10-second intensity, size; retail tells = round-5c price, round-lot size, tiny size.

---

## TASK 1 — Aggregate taker outcome (the naive-bettor test)

| set | n | win% | EV (c/contract) | t vs 0 | mid markout +1m |
|-----|---|------|-----------------|--------|-----------------|
| ALL IS  | 1,183,007 | 55.28 | **−0.373** | −10.11 | −0.056c |
| ALL OOS |   813,010 | 54.71 | **−0.510** | −11.96 | +0.029c |

**Takers lose as a class** — robustly, IS and OOS, t ≈ −10 to −12. So the naive-bettor
direction is correct *at the aggregate level*. BUT the loss is only ~0.4–0.5c/contract,
which is **far smaller than the spread+fee the taker crossed** (~1.8c spread + ~2.7c
crypto taker fee). The taker's realized loss-to-settlement is small because the mid is a
near-martingale; almost the entire transfer the taker makes is the **spread captured by
the resting maker**, not a settlement misprediction.

**Reconciliation with "makers get adversely selected":** the mirror of the aggregate
taker loss is a +0.51c/contract gross maker win (t≈12). This is exactly the half-spread
capture. The established honest adverse-selection fill model (prior commits: naive maker
+0.9c/fill is a 100% fill-model artifact; adverse-selection-aware fills flip to
**−9.5c/fill, t=−49**) already showed this gross capture does not survive once the maker
is filled *only when price runs against it*. The two facts are consistent: takers lose
the spread to makers in aggregate, but the maker cannot harvest it because the fills it
actually gets are the toxic ones.

---

## TASK 2 — Smart vs naive buckets (win-rate + EV by detector feature)

OOS (IS shown where it differs in sign; full IS table in `_flow_out.txt`):

| bucket | n (OOS) | win% | EV c/ct | Sharpe | t | mid mk +1m |
|--------|--------:|-----:|--------:|-------:|--:|-----------:|
| all | 813,010 | 54.71 | −0.510 | −0.013 | −11.96 | +0.03 |
| **sweep ≥ 2** | 56,083 | 53.06 | **−1.846** | −0.048 | −11.33 | −0.44 |
| **sweep ≥ 3** | 21,304 | 50.38 | **−3.320** | −0.087 | −12.63 | −0.61 |
| run ≥ 4 (same side) | 384,799 | 58.76 | −0.744 | −0.020 | −12.26 | +0.04 |
| run ≥ 6 | 254,510 | 61.00 | −0.911 | −0.025 | −12.39 | +0.02 |
| intensity ≥ 5 /10s | 727,280 | 54.95 | −0.564 | −0.015 | −12.46 | +0.02 |
| intensity ≥ 10 /10s | 538,707 | 55.73 | −0.549 | −0.014 | −10.52 | +0.04 |
| size ≥ 10 | 420,847 | 51.70 | −0.515 | −0.013 | −8.71 | +0.03 |
| size ≥ 50 | 93,398 | 52.52 | −0.896 | −0.025 | −7.69 | −0.10 |
| **INFORMED (any of above)** | 690,769 | 55.05 | **−0.562** | −0.015 | −12.22 | +0.03 |
| round-5c price | 169,143 | 56.25 | −0.201 | −0.005 | −2.15 | +0.06 |
| round-lot size | 128,419 | 62.00 | −0.386 | −0.010 | −3.66 | +0.08 |
| size ≤ 1 (tiny) | 160,357 | 60.91 | −0.543 | −0.014 | −5.67 | −0.01 |
| **NAIVE (round+tiny+no-flow)** | 18,966 | 56.50 | −0.322 | −0.008 | −1.11 | −0.30 |

**The smart-money hypothesis is FALSIFIED — in the wrong direction.** The "informed"
footprint flow loses *more*, not less:
- **Sweeps are the worst trades on the tape**: −1.8c (sweep≥2) to −3.3c (sweep≥3),
  win-rate collapsing toward 50%, t down to −16 (IS). The +1m mid markout is strongly
  negative (−0.4 to −0.6c): a sweep pays up through the book and the mid then reverts
  against it. This is impact-paying urgency, not information.
- Large size, high intensity, long runs all lose ~0.5–0.9c — modestly worse than average.
- The supposedly-naive buckets (round-lot, tiny size) are actually the **least bad**:
  round-lot/tiny are ≈ breakeven IS (+0.02c) and only mildly negative OOS. There is no
  clean naive-loser sub-population whose loss exceeds the aggregate.

So there is no winning sub-population to follow, and the losing sub-population (sweeps)
loses by *over-paying spread/impact* — money that is captured by the resting maker, not
recoverable by a same-latency taker.

---

## TASK 3 — Follow-the-smart-money (cost-adjusted, taker)

Trade alongside informed flow (same side as the informed taker), as a taker paying
`p` + crypto taker fee (`ceil(0.14·p(1−p))` ¢, ~2.6–2.7c here).

| strategy | n | gross c | fee c | NET c | Sharpe | t | win% |
|----------|--:|--------:|------:|------:|-------:|--:|-----:|
| FOLLOW-informed IS  | 999,385 | −0.376 | 2.738 | **−3.11** | −0.078 | −78.1 | 53.2 |
| FOLLOW-informed OOS | 690,769 | −0.562 | 2.634 | **−3.20** | −0.084 | −69.5 | 52.0 |

Informed flow is gross-negative *before* costs, so following it is catastrophically
negative after the taker fee. **Dead.**

---

## TASK 4 — Fade-the-naive (taker vs maker framing)

Take the opposite side of NAIVE flow (round-5c price + size≤2 + no run + no sweep).

| strategy | n | gross c | fee c | NET c | Sharpe | t | win% |
|----------|--:|--------:|------:|------:|-------:|--:|-----:|
| FADE-naive TAKER IS  | 25,733 | +0.081 | 2.858 | **−2.78** | −0.068 | −10.8 | 42.2 |
| FADE-naive TAKER OOS | 18,966 | +0.322 | 2.795 | **−2.47** | −0.062 |  −8.5 | 41.1 |
| FADE-naive MAKER IS  | 25,733 | +0.081 | 0.000 | **+0.08** | +0.002 |  +0.3 | 44.7 |
| FADE-naive MAKER OOS | 18,966 | +0.322 | 0.000 | **+0.32** | +0.008 |  +1.1 | 43.5 |

- **Fade as a taker:** naive flow's loss (~0.1–0.3c) is dwarfed by the taker fee → −2.5 to
  −2.8c. Dead.
- **Fade as a maker:** the only positive line (+0.08c IS, +0.32c OOS) and it is **the
  adverse-selection trap again.** It is the exact mirror of the naive taker's realized
  P&L = the half-spread the naive crossed, under the unrealistic assumption every quote
  fills. On the naive subset it is **not even statistically significant** (t = +0.3 IS,
  +1.1 OOS). The honest adverse-selection fill model (filled only when price runs against
  you) already converted this gross spread-capture to −9.5c/fill (t=−49) in prior work.
  Which framing survives costs? **Neither.**

---

## TASK 5 — VERDICT on the operator's dichotomy

**No accessible positive-EV strategy exists from counterparty profiling on ETH 15-min.**

The dichotomy resolves to "neither, usefully":
1. **No smart money to follow.** The footprints that look informed (sweeps, high
   intensity, long runs, large size) systematically LOSE — sweeps worst of all
   (OOS −1.8 to −3.3c, t to −13; +1m mid markout −0.4 to −0.6c). These are
   urgency/impact-payers, not informed predictors; the mid reverts against them.
   Following them is −3.2c/contract OOS after fee (t=−69).
2. **The naive class does lose, but only by the spread — uncapturable at our latency.**
   Takers as a whole lose −0.51c OOS (t=−12), and the matching +0.51c maker gross win is
   pure half-spread capture. Fading naive as a taker is −2.5c after fee; fading as a maker
   is the +0.3c spread-capture mirror that is (a) statistically insignificant on the naive
   subset (t=+1.1) and (b) already proven to flip to −9.5c/fill (t=−49) under the honest
   adverse-selection fill model. **The winners (resting makers) win on structure/queue
   priority and selective fills we cannot reach as a seconds-latency taker; the naive loss
   is entirely the spread, which the adverse-selection trap prevents us from harvesting.**

**Exact best rule found and its metrics (the only non-negative one):** "Fade-naive as a
maker" — NET +0.32c/contract OOS, Sharpe +0.008, n=18,966, win% 43.5, **t = +1.1
(insignificant)**, IS +0.08c/t=+0.3. This is the spread-capture artifact, not an edge.
Every genuinely tradeable rule (any taker rule) is −2.5 to −3.2c/contract OOS, t<−8.

**Honest bottom line:** counterparty profiling confirms takers are net losers and the
"informed-looking" flow loses hardest, but **all of the transfer is spread/impact captured
by makers via structure and selective fills, not a settlement-prediction edge** — so it is
inaccessible to a seconds-latency taker, and the maker side is the adverse-selection trap
already shown to be −EV. Verdict: **DEAD — do not deploy.** Backtest SCREENS only;
no forward validation performed.
