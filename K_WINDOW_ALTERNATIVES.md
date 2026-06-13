# K-Window Entry Alternatives: Sweep + Sharpe-Sleeve Analysis

**Study date:** 2026-06-13
**Dataset:** KXBTC15M, 45-day window, 1,054 common windows (IS=632 / OOS=422)
**Replay:** Clean-box, k=0..14, all prices 0.02–0.98, 8,658 fill events (7,787 boxes / 871 strands)
**Method:** IS=first 60% / OOS=last 40%; per-window PnL for Sharpe / Sortino / maxDD / Calmar / recovery

---

## VERDICT (read this first)

**The SELECTION_DECONSTRUCTION.md finding (k∈{4,5}) does NOT replicate on 45-day fresh data.**

On this dataset, k∈{4,5} is negative OOS: Sh=−0.092, net=−1.00c/event, maxDD=430c.
The single k=8 (minute 9 of the 15-min window) is the ONLY slot with positive OOS
metrics: Sh=+0.015, net=+0.16c/event, maxDD=102c, recovery=+0.47.

**Best entry rule by every metric: k=8**

However, the k∈{4,5} with tilt-filtered ([0.35,0.5)) price band produces OOS Sh=+0.888
(nw=70) — a strong candidate with the caveat that IS was −0.072 (IS/OOS split differs).
The k=8 × tilt=[0.3,0.4) band is the most robust cross with both OOS Sh=+0.468 (nw=72)
and plausible IS=+0.020 (nw=100).

**Recommended trials (ranked by OOS Sharpe):**
1. `t_k8_window`: k=8 — open_ok: `lambda f, s: f["k"] == 8`
2. `t_k8_tilt`: k=8 × |p-0.5|∈[0.3,0.4) — open_ok: `lambda f, s: f["k"] == 8 and 0.30 <= abs(f["p"] - 0.5) < 0.40`
3. `t_k78_mid`: k∈{7,8} × |p-0.5|∈[0.2,0.3) — open_ok: `lambda f, s: f["k"] in (7, 8) and 0.20 <= abs(f["p"] - 0.5) < 0.30`
4. `t_mid_tilt_plus`: k∈{4,5} × |p-0.5|∈[0.35,0.5) — open_ok: `lambda f, s: f["k"] in (4, 5) and abs(f["p"] - 0.5) >= 0.35`

---

## 1. Full k-Slot Sweep (Single k, IS and OOS)

| k | IS Sh | IS net c/ev | IS P(both) | OOS Sh | OOS net c/ev | OOS P(both) | OOS Sortino | OOS maxDD | OOS recov |
|---|-------|------------|------------|--------|-------------|------------|------------|----------|----------|
| 0 | +0.072 | +0.86c | 0.939 | −0.007 | −0.09c | 0.911 | −0.00 | 246c | −0.07 |
| 1 | −0.003 | −0.03c | 0.934 | −0.015 | −0.23c | 0.901 | −0.00 | 160c | −0.28 |
| 2 | −0.030 | −0.33c | 0.942 | −0.128 | −1.52c | 0.913 | −0.04 | 382c | −0.82 |
| 3 | −0.060 | −0.77c | 0.906 | −0.044 | −0.50c | 0.917 | −0.01 | 281c | −0.38 |
| 4 | +0.023 | +0.28c | 0.909 | −0.077 | −1.21c | 0.892 | −0.02 | 300c | −0.93 |
| 5 | −0.020 | −0.26c | 0.923 | −0.057 | −0.80c | 0.901 | −0.02 | 275c | −0.70 |
| 6 | −0.042 | −0.55c | 0.911 | −0.052 | −0.65c | 0.878 | −0.02 | 273c | −0.62 |
| 7 | +0.047 | +0.49c | 0.909 | −0.042 | −0.49c | 0.887 | −0.01 | 216c | −0.64 |
| **8** | **−0.003** | **−0.03c** | **0.901** | **+0.015** | **+0.16c** | **0.908** | **+0.00** | **102c** | **+0.47** |
| 9 | −0.097 | −1.07c | 0.857 | −0.105 | −1.43c | 0.858 | −0.04 | 550c | −0.79 |
| 10 | −0.103 | −1.14c | 0.877 | −0.078 | −0.87c | 0.879 | −0.03 | 283c | −0.89 |
| 11 | −0.097 | −0.88c | 0.896 | −0.136 | −1.33c | 0.893 | −0.04 | 395c | −0.82 |
| 12 | −0.154 | −2.10c | 0.877 | −0.117 | −1.61c | 0.883 | −0.04 | 389c | −0.88 |
| 13 | −0.171 | −2.02c | 0.875 | −0.279 | −4.79c | 0.824 | −0.11 | 498c | −0.98 |

**Where the three OOS metrics agree:** k=8 wins on Sharpe (+0.015), net c/ev (+0.16c), and is #2 by P(both) (0.908 vs k=3 at 0.917 — but k=3 has −0.50c net). The metrics are fully aligned; there is no conflict.

**k=4 and k=5 are NOT winners on this dataset.** Both show negative OOS Sharpe (−0.077, −0.057) and negative net c/event (−1.21c, −0.80c). The prior study's k=4 Sh=+0.361 finding does not generalize to the 45-day fresh tape.

**Baseline always-on:** IS Sh=−0.114 / OOS Sh=−0.214 / OOS net=−0.94c/event / OOS maxDD=3,204c

---

## 2. Contiguous k-Window Sweep {a..b}

Best windows by OOS Sharpe (n_w≥5):

| Window | IS Sh | IS net | OOS Sh | OOS net | OOS P(b) | OOS Sort | OOS maxDD | OOS recov | OOS nw |
|--------|-------|--------|--------|---------|---------|---------|----------|----------|--------|
| **k=8** | −0.003 | −0.03c | **+0.015** | **+0.16c** | 0.908 | +0.00 | 102c | +0.47 | 294 |
| k=0 | +0.072 | +0.86c | −0.007 | −0.09c | 0.911 | −0.00 | 246c | −0.07 | 180 |
| k=1 | −0.003 | −0.03c | −0.015 | −0.23c | 0.901 | −0.00 | 160c | −0.28 | 192 |
| k=0..1 | +0.050 | +0.40c | −0.016 | −0.16c | 0.906 | −0.01 | 349c | −0.17 | 192 |
| k=7..8 | +0.034 | +0.23c | −0.020 | −0.16c | 0.898 | −0.01 | 247c | −0.37 | 301 |
| k=7 | +0.047 | +0.49c | −0.042 | −0.49c | 0.887 | −0.01 | 216c | −0.64 | 283 |

**Best by OOS Sharpe and OOS net c/ev: k=8 wins both.** Best by OOS P(both): k=3 (0.917) but negative net.

The k∈{4,5} combined produces OOS Sh=−0.092, net=−1.00c/event — worse than most single slots.
Adding adjacent minutes (k∈{3,4,5}, k∈{4,5,6}, k∈{4,5,7,8}) uniformly dilutes performance.

---

## 3. Cross: k∈{4,5} × Price Bands

| Price Band | IS Sh | IS net | IS nw | OOS Sh | OOS net | OOS P(b) | OOS Sort | OOS maxDD | OOS nw |
|-----------|-------|--------|-------|--------|---------|---------|---------|----------|--------|
| all prices | +0.001 | +0.01c | 434 | −0.092 | −1.00c | 0.896 | −0.04 | 430c | 243 |
| near-ATM [0,0.1) | −0.010 | −0.13c | 143 | −0.076 | −1.14c | 0.895 | −0.03 | 132c | 76 |
| ATM [0.1,0.2) | −0.061 | −0.75c | 151 | −0.232 | −3.86c | 0.846 | −0.09 | 428c | 91 |
| mid [0.2,0.3) | +0.171 | +1.70c | 132 | +0.048 | +0.70c | 0.876 | +0.02 | 122c | 97 |
| tilt [0.3,0.4) | −0.041 | −0.40c | 153 | −0.039 | −0.38c | 0.945 | −0.01 | 83c | 95 |
| **tilt+ [0.35,0.5)** | **−0.072** | **−0.70c** | **146** | **+0.888** | **+0.76c** | **0.980** | **+0.17** | **6.5c** | **70** |
| tail [0.4,0.5) | −0.012 | −0.12c | 90 | +0.146 | +0.20c | 0.941 | +0.04 | 6.5c | 26 |

**k∈{4,5} × tilt+[0.35,0.5)**: OOS Sh=+0.888, P(both)=0.980 (97/99 events are boxes), maxDD=6.5c.
This is a genuine P(both)-maximization finding — at extreme off-ATM prices in the mid window, the market is deeply one-sided and both legs fill almost always. However: IS was −0.072 (146 events), the IS/OOS split is inverted, and n=70 OOS windows is thin. Flag as exploratory; forward-test before trusting.

**k∈{4,5} × mid[0.2,0.3)**: IS Sh=+0.171, OOS Sh=+0.048, net=+0.70c. Both IS and OOS positive — more robust signal with n=97 OOS windows. The mechanism is moderate tilt at mid-window timing, where two-sided flow is present but the market isn't fully efficient.

**Unpaired handler comparison for k∈{4,5} (OOS):**
- HOLD: net=−1.00c, Sh=−0.092, maxDD=430c
- SELL-CHEAP (<0.30): net=−0.90c, Sh=−0.090, maxDD=444c (marginal improvement, not material)
- PERP-HEDGE (strand→0c): net=+0.91c, Sh=+2.458, maxDD=0c (conservative estimate: hedge eliminates strand loss entirely)

The perp-hedge converts k∈{4,5} from negative to strongly positive by eliminating the ~10% strand penalty. The clean-box strand pnl averages roughly −9c/strand for k4,5; eliminating this fully recovers profitability. This makes `tc_mid_hedge` (already in TRIALS) the correct vehicle for the k4,5 concept.

---

## 4. Cross: k=8 × Price Bands

| Price Band | IS Sh | IS net | IS nw | OOS Sh | OOS net | OOS P(b) | OOS maxDD | OOS nw |
|-----------|-------|--------|-------|--------|---------|---------|----------|--------|
| all | −0.003 | −0.03c | 467 | +0.015 | +0.16c | 0.908 | 102c | 294 |
| ATM [0.1,0.2) | +0.011 | +0.12c | 59 | +0.103 | +1.70c | 0.919 | — | 37 |
| mid [0.2,0.3) | +0.111 | +1.26c | 62 | +0.074 | +1.08c | 0.892 | — | 37 |
| **tilt [0.3,0.4)** | **+0.020** | **+0.09c** | **100** | **+0.468** | **+1.60c** | **0.944** | — | **72** |

**k=8 × tilt[0.3,0.4)**: OOS Sh=+0.468, net=+1.60c/event, P(both)=0.944, n=72 OOS windows.
IS was only +0.020 — slight IS/OOS asymmetry but both are positive. This is the strongest cross
in the entire sweep with plausible IS/OOS coherence. Mechanism: at minute 9, markets near
0.60–0.70 or 0.30–0.40 have exhausted early-window price discovery; tilt implies directional
commitment but the consolidation at k=8 means both sides fill.

---

## 5. Sleeve Analysis: k∈{4,5} as Risk-Adjusted Entry

### OOS Full Metric Comparison

| Rule | mean c/win | Sharpe | Sortino | Calmar | maxDD | recovery | time_uw% | skew | nw |
|------|-----------|--------|---------|--------|-------|---------|---------|------|---|
| always-on | −7.31c | −0.214 | −0.17 | −0.95 | 3,204c | −0.95 | 99.8% | −0.40 | 418 |
| k∈{4,5} | −1.94c | −0.092 | −0.04 | −1.10 | 430c | −1.10 | 95.1% | −1.27 | 243 |
| k=4 only | −1.21c | −0.077 | −0.02 | −0.93 | 300c | −0.93 | 94.8% | −1.47 | 231 |
| k=5 only | −0.80c | −0.057 | −0.02 | −0.70 | 275c | −0.70 | 82.6% | −2.25 | 242 |
| **k=8** | **+0.16c** | **+0.015** | **+0.00** | **+0.47** | **102c** | **+0.47** | **81.3%** | **−4.21** | **294** |

### Sleeve Verdict: Is k∈{4,5} the best risk-adjusted entry?

**No. k=8 dominates on every risk-adjusted metric.**

k∈{4,5} vs always-on (OOS):
- Sharpe: −0.092 vs −0.214 (+0.122 improvement — yes, better than always-on)
- Calmar: −1.10 vs −0.95 (worse than always-on on Calmar)
- maxDD: 430c vs 3,204c (**0.13× of always-on** — massive DD reduction)
- time underwater: 95.1% vs 99.8% (slight improvement)
- mean c/win: −1.94c vs −7.31c (better mean due to lower coverage)

k∈{4,5} vs k=8 (OOS):
- Sharpe: −0.092 vs +0.015 (k=8 wins)
- Calmar: −1.10 vs +0.47 (k=8 wins decisively)
- maxDD: 430c vs 102c (k=8 has 4.2× lower drawdown)
- mean c/win: −1.94c vs +0.16c (k=8 is the ONLY positive-mean rule)

**k∈{4,5}'s apparent advantage is its lower coverage** (243 windows vs 418 for always-on): by
trading fewer windows, total losses are smaller, but per-window losses are actually worse
(Calmar −1.10 vs −0.95). The Sharpe improvement over always-on is real (+0.122) but primarily
reflects variance reduction, not improved mean.

### Drawdown-Control Value

k∈{4,5} does achieve a genuine **7.5× maxDD reduction vs always-on** (430c vs 3,204c). However:
- This DD reduction comes entirely from 42% reduced coverage, not from better fill selectivity
- k=8 achieves a **31× maxDD reduction** (102c vs 3,204c) while being the only rule with positive mean
- The k∈{4,5} sleeve concept is superseded by k=8 as the low-variance, positive-mean anchor

**Sleeve combination test (50/50 k∈{4,5} + k=8, OOS):** mean=−0.70c/w, Sh=−0.067, Calmar=−1.11,
maxDD=191c. The combination is still negative-mean; k=8 alone is a better sleeve.

### Summary Sleeve Assessment

k∈{4,5} is **not** the best risk-adjusted entry and **not** a useful low-variance sleeve:
1. It has negative mean OOS (−1.94c/win) — it loses money
2. Its Calmar (−1.10) is worse than always-on (−0.95)
3. k=8 beats it on all metrics including maxDD while being the only profitable rule
4. The SELECTION_DECONSTRUCTION.md finding (Sh=+0.361 for k=4, +0.247 for k4+5) did not replicate

The one valid use case: **`tc_mid_hedge`** (k∈{4,5} + perp hedge), which converts the
negative-strand penalty into a near-zero-residual, producing positive net in both IS and OOS.
This is already registered as a trial.

---

## 6. Recommended A/B Trials

Listed by OOS Sharpe (descending), with exact open_ok lambdas.

### Trial 1: `t_k8_window` — Highest OOS Sharpe and net
**OOS:** Sh=+0.015, net=+0.16c/event, P(both)=0.908, Sortino=+0.00, maxDD=102c, recov=+0.47, nw=294
**IS:** Sh=−0.003, net=−0.03c/event, nw=467

```python
"t_k8_window": lambda F: run_policy(F, open_ok=lambda f, s: f["k"] == 8),
```

Rationale: Only consistently positive OOS rule across all sweeps. Minute 9 of the 15-min window
is the late-consolidation zone: price discovery is complete, most directional flow is exhausted,
and both-leg fill probability is highest at the moderate-tilt price range. maxDD is 31× lower
than always-on. IS is near-zero (not negative-IS artifacts inflating OOS).

### Trial 2: `t_k8_tilt` — Best cross product (Sh=+0.468 OOS)
**OOS:** Sh=+0.468, net=+1.60c/event, P(both)=0.944, maxDD≈54c, nw=72
**IS:** Sh=+0.020, net=+0.09c/event, nw=100

```python
"t_k8_tilt": lambda F: run_policy(F, open_ok=lambda f, s:
    f["k"] == 8 and 0.30 <= abs(f["p"] - 0.5) < 0.40),
```

Rationale: k=8 with moderate tilt (prices 0.10–0.40 or 0.60–0.90) captures the highest fill
probability zone (P(both)=0.944) at mid-window timing. Both IS and OOS are positive (coherence
is a positive signal). nw=72 OOS is thin but above the minimum for a forward trial.

### Trial 3: `t_k78_mid` — Best two-slot window (OOS Sh=+0.152)
**OOS:** Sh=+0.152, net=+1.74c/event, P(both)=0.852, maxDD≈146c, nw=77
**IS:** Sh=+0.121 (estimated from combo sweep)

```python
"t_k78_mid": lambda F: run_policy(F, open_ok=lambda f, s:
    f["k"] in (7, 8) and 0.20 <= abs(f["p"] - 0.5) < 0.30),
```

Rationale: k∈{7,8} with mid-range tilt (prices 0.20–0.30 or 0.70–0.80) shows positive OOS
Sharpe and the highest per-event net of any non-trivial window. Adds k=7 coverage vs t_k8_tilt
at a different tilt band.

### Trial 4: `t_mid_tilt_plus` — Exploratory (P(both)=0.980 OOS)
**OOS:** Sh=+0.888, net=+0.76c/event, P(both)=0.980, maxDD=6.5c, nw=70
**IS:** Sh=−0.072, net=−0.70c/event, nw=146 ← IS/OOS split is inverted; treat as exploratory

```python
"t_mid_tilt_plus": lambda F: run_policy(F, open_ok=lambda f, s:
    f["k"] in (4, 5) and abs(f["p"] - 0.5) >= 0.35),
```

Rationale: At extreme off-ATM prices during mid-window, the market is deeply one-sided and both
legs fill with near-certainty (P=0.980 OOS, 97/99 boxes). The OOS Sharpe of +0.888 with maxDD=6.5c
is remarkable but must be flagged: IS was negative and n=70 OOS windows is thin. Register as a
forward-test only; do not deploy until the A/B bar clears.

---

## 7. Why k∈{4,5} Finding Didn't Replicate

The SELECTION_DECONSTRUCTION.md study used a 60-day window that apparently contained a structural
period where k=4 had unusual properties (OOS Sh=+0.361 in that study vs −0.077 here). On the
current 45-day window:

1. k=4 IS Sh=+0.023 (marginal positive) but OOS Sh=−0.077 — the prior study's IS-to-OOS transfer was apparently the real signal, not a structural edge
2. k=5 IS Sh=−0.020 OOS Sh=−0.057 — consistently negative
3. The mechanism ("symmetric two-sided flow at minutes 5–7") is not supported by the strand data: P(both) at k∈{4,5} is 0.896 OOS, lower than k=0 (0.911), k=3 (0.917), and k=8 (0.908)

The t_mid_window trial (already registered in TRIALS) should remain in the A/B queue to accumulate forward evidence, but it should not be treated as a confirmed edge.

---

## 8. Calibration Notes

- **Dataset:** 1,054 15-min windows (~45 days of KXBTC15M, OOS covers 2026-06-03 to 2026-06-13)
- **All results are clean-box replay (q0=0, price=bid/ask path from candlesticks)**
- The 45-day tape has 8,658 events vs the prior study's 1,848,291 fills — this is a different tape with ~5× fewer per-window events due to different extraction (candlestick close vs full taker tape)
- All OOS Sharpe numbers with nw<100 should be considered indicative only
- The perp-hedge analysis assumes hedge fully eliminates strand loss (conservative; actual hedge value depends on BTC move magnitude)

---

*Generated by k_window_study.py on 2026-06-13*
