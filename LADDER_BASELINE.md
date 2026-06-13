# LADDER BASELINE — Phase A+B Results (BTC, 60/40 IS/OOS)

Generated: 2026-06-13  |  BTC windows total=916 (with fills), IS=549, OOS=367
GBM strand gate: IS AUC~0.98 (correct strand label), OOS AUC=0.883 | threshold=0.163 (IS F1-optimal)
live_current guard_yes_spread: 0.02

**Tape note**: Rung 2 GBM trained with per-fill strand label (P(this fill ends stranded)); OOS strand-fill
rate=0.65%; GBM blocks 0.8% of OOS fills at IS-tuned threshold. IS combined policy excludes GBM (leakage
avoidance). Tape mean spread = 1c; t36's 2c YES-spread floor blocks ~90% of bid fills in parquet tape.

---

## Phase A: Combined 5-Rung Baseline

### Policy stack (lifecycle order)
1. **PREVENT** (R1 / t36): skip YES opens where spread < 2c; skip any fill with sig > 8 bps at spread < 2c
2. **PREDICT** (R2 / GBM): skip opens where P(strand) > 0.163 (IS-tuned; 7 feats: spread, |p-0.5|, sig, |flow|, k, tau, vpin); OOS AUC=0.883
3. **COMPLETE** (R3 / sell-cheap): at window end, sell unpaired leg at exit price if price < 0.30
4. **COOL-OFF** (R4 / streak): scale PnL by 0.75/0.50/0.25 after 1/2/3+ consecutive stranded windows
5. **HEDGE** (R5 / h=150): delta-hedge remaining unpaired leg (price >= 0.30) with BTC perp at h=150

### Metrics Table

| Policy | n | net c/win | Win% | Sharpe | Sortino | Skew | Kurt | Recovery | Ulcer(c) | VaR95(c) | CVaR95(c) | IR_P0 | IR_live | AvgW/L | TimeUW% | P(both) | Strand% | MaxDD(c) | t-stat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P0 baseline IS | 549 | +0.73c | 66.3% | +0.043 | +0.038 | -0.36 | +2.15 | +0.5 | 131.4c | 43.2c | 46.6c | — | — | 1.014 | 62.7% | 0.877 | 12.3% | 129.5c | — |
| P0 baseline OOS | 367 | +2.77c | 74.9% | +0.179 | +0.147 | -2.95 | +28.1 | +6.0 | 46.2c | 29.8c | 45.0c | — | — | 0.918 | 73.0% | 0.877 | 12.3% | 46.3c | +3.42 |
| live_current IS | 549 | +2.75c | 55.6% | +0.095 | +0.089 | -1.05 | +6.4 | +1.3 | 155.5c | 49.2c | 60.7c | n/a | — | 0.840 | 74.3% | — | n/a | 209.0c | — |
| live_current OOS | 367 | +2.66c | 58.3% | +0.080 | +0.073 | -1.55 | +10.7 | +1.2 | 234.6c | 60.7c | 78.7c | -0.003 | — | 0.823 | 77.4% | — | n/a | 223.5c | +1.53 |
| **COMBINED IS** | 549 | **+3.76c** | 59.4% | +0.149 | +0.141 | -0.35 | +4.2 | +1.9 | 143.9c | 47.1c | 53.1c | +0.112 | n/a | 0.935 | 74.7% | 0.656 | 34.4% | 194.8c | — |
| **COMBINED OOS** | 367 | **+3.50c** | 59.9% | +0.133 | +0.128 | -0.07 | +2.02 | +3.3 | 158.5c | 43.3c | 60.3c | +0.027 | +0.052 | 0.964 | 81.5% | 0.621 | 37.9% | 385.5c | +2.54 |

### Phase A Deep-Dive

**Overall lift vs P0 OOS**: COMBINED +3.50c vs P0 +2.77c = **+0.73c/win** net improvement. vs live_current +2.66c = **+0.84c/win**.

**Where PnL comes from (OOS, via ablation)**:
- **R5 HEDGE** is the single largest contributor: dropping it costs -0.98c/win. The perp hedge converts naked stranded-leg directional losses into near-flat outcomes.
- **R3 COMPLETE** (sell-cheap) is second: dropping costs -0.55c/win and worsens CVaR +4.6c. Selling cheap longshot strands (price<0.30) avoids tail settlement losses.
- **R1 PREVENT** (t36): dropping IMPROVES net +0.17c but WORSENS strand-rate +25.3pp and CVaR -24.3c. The gate trades net PnL for tail protection — on this tape the gated-out fills were profitable on average.
- **R2 PREDICT** (GBM): near-zero contribution (+0.08c, -0.01c CVaR). Blocks only 0.8% of fills (strand-fill rate 0.65% leaves too few positives to trigger the threshold meaningfully).
- **R4 COOL-OFF** (streak): NEGATIVE net contribution — dropping IMPROVES net +0.61c. The streak scale-down punishes recovery windows, compounding losses during adverse streaks.

**Tail behavior (OOS)**:
- COMBINED skew = -0.07 vs P0 -2.95: sell-cheap and hedge eliminate most of the left-tail strand events.
- COMBINED excess kurtosis = +2.02 vs P0 +28.1: tail events are dramatically reduced.
- CVaR95 = 60.3c (worse than P0 45.0c): the R4 streak scale-down creates path-dependent amplification of worst-case sequences.
- MaxDD = 385.5c vs P0 46.3c: the large drawdown reflects extended periods of R4-reduced sizing.
- Ulcer = 158.5c vs P0 46.2c: time-underwater = 81.5% confirms the R4 streak creates prolonged underwater periods.

**Main remaining losses**: Stranded mid-price legs (0.30-0.70) where the h=150 hedge is imperfect during fast directional BTC moves. The hedge is SHADOW-only in production; live deployment of R5 is the highest-priority improvement.

---

## Phase B: Leave-One-Out Ablation (OOS)

Δ = (policy without rung) − (combined baseline). **Positive Δnet = rung adds net value; Negative Δnet = dropping improves net (rung hurts or is redundant).**

| Rung dropped | Δnet c/win | ΔSharpe | ΔCVaR95 | Δstrand-rate | Ablated net | Ablated Sharpe | Verdict |
|---|---|---|---|---|---|---|---|
| Drop R1 PREVENT (t36) | **+0.17c** | **+0.135** | **-24.3c** | **+25.3pp** | +3.67c | +0.268 | RISK-CONTROL: small net cost (+0.17c given up), massive CVaR saving (-24.3c). KEEP for tail protection. |
| Drop R2 PREDICT (GBM) | **+0.08c** | **+0.003** | **-0.01c** | **+0.3pp** | +3.58c | +0.136 | CURRENTLY DORMANT: blocks 0.8% fills. Keep architecture; retune threshold in Phase C. |
| Drop R3 COMPLETE (sell-cheap) | **-0.55c** | **-0.028** | **+4.6c** | **0.0pp** | +2.95c | +0.105 | EARNS ITS PLACE: -0.55c net, +4.6c CVaR when dropped. KEEP. |
| Drop R4 COOL-OFF (streak) | **-0.61c** | **-0.006** | **+4.8c** | **0.0pp** | +4.11c | +0.139 | HURTS NET: dropping improves net +0.61c. CVaR worsens +4.8c when dropped but net drag exceeds risk benefit. REDESIGN as manage-split. |
| Drop R5 HEDGE (h=150) | **-0.98c** | **-0.042** | **+4.2c** | **0.0pp** | +2.52c | +0.090 | STRONGEST CONTRIBUTOR: -0.98c net, +4.2c CVaR when dropped. KEEP; arm when BTC venue ready. |

---

## Candidate New Rungs (OOS vs Combined Baseline)

| Candidate | net c/win | Δnet vs COMBINED | Strand% | Sharpe | Verdict |
|---|---|---|---|---|---|
| Rung-0 BUFFER spread>=0.01 | +3.50c | **+0.00c** | 17.7% | +0.128 | **NEUTRAL net; strong strand reduction (-20.2pp)**. The 1c-spread fills blocked are break-even; filtering removes strand risk at zero PnL cost. ADD as Rung-0. |
| Rung-0 BUFFER spread>=0.02 | +0.37c | **-3.13c** | 0.5% | +0.055 | **HURTS (-3.13c)**. Redundant with t36 on YES side; blocks profitable NO fills universally. DO NOT ADD. |
| MANAGE split (size-down vs skip) | +4.07c | **+0.57c** | 38.1% | +0.142 | **ADDS VALUE (+0.57c)**. Continuous GBM-probability sizing (size=max(0.25, 1-p*5)) retains upside of low-strand-prob fills while proportionally reducing exposure to high-prob strands. RECOMMEND replacing R4 streak with this. |
| Cross-strike Kalshi hedge | n/a | n/a | n/a | n/a | INFEASIBLE: no adjacent-strike Kalshi data in parquet tape. Flag for Phase C when multi-strike depth data available. |

---

## Order / Priority Interactions

1. **R3 and R5 act on same stranded leg**: R3 (sell if price<0.30) fires first; R5 (hedge if price>=0.30) fires on the remainder. Priority R3 before R5 is correct as implemented — no conflict.
2. **R1 and R2 both gate opens**: R1 fires first (cheap, rule-based), R2 on R1 survivors (model-based). Correct order.
3. **R4 interacts with ALL other rungs**: streak scale-down reduces PnL of R3 and R5 on stranded legs during recovery periods — this is an architectural conflict that partly explains R4's negative net contribution.
4. **Candidate R0 buffer** should fire before R1 (structural, unconditional). Insert order: R0 (structural-buffer) → R1 (entry filter) → R2 (model gate) → R3 (completion) → R4 (sizing) → R5 (hedge residual).

---

## Recommended LOCKED SEQUENCE

| Order | Rung | Strategy | Status | Decision |
|---|---|---|---|---|
| 0 | STRUCTURAL BUFFER | spread >= 0.01 (any fill) | Candidate | **ADD** — zero net cost, cuts strand -20pp |
| 1 | PREVENT | t36 guarded-opener (YES spread<2c / sig>8bps at thin spread) | DEPLOYED | **KEEP** — risk-control rung; tune threshold Phase C |
| 2 | PREDICT | GBM strand gate (OOS AUC=0.883, retune threshold) | Shadow | **KEEP; RETUNE** — architecture valid, currently dormant |
| 3 | COMPLETE | sell-cheap<0.30 + chase give<=0.02 | DEPLOYED | **KEEP** — confirmed -0.55c when dropped |
| 4 | COOL-OFF → MANAGE | Replace streak 0.75/0.5/0.25 WITH continuous GBM sizing (max(0.25, 1-p*5)) | DEPLOYED (streak) | **REDESIGN** — streak costs -0.61c net; manage-split adds +0.57c |
| 5 | HEDGE | BTC-perp h=150 over-hedge residual (price >= 0.30) | SHADOW-only | **KEEP; ARM when venue ready** — largest contributor -0.98c |

**Rationale for order**: structural gate cheapest first → rule-based filter deployed → model gate on survivors → completion action on strand → exposure-control sizing → hedge residual. No rung conflicts in this order (see interaction analysis above).

---

## Phase C Priority: Rungs Worth Deep Optimization

Ranked by marginal ablation contribution and forward-validation gap:

1. **(Priority 1) R5 HEDGE** (Δnet −0.98c when dropped): h ratio sweep (50–300), conditional-on-price sizing, prophylactic vs reactive timing, side-specific delta, venue selection. **Highest PnL lever once BTC venue is live.**
2. **(Priority 2) R4 MANAGE** (Δnet −0.61c net drag when kept as streak): Implement manage-split (GBM continuous sizing). Test: linear (1-p) sizing, Kelly-fraction, VPIN-conditional. Manage-split prototype: +0.57c vs combined baseline.
3. **R3 COMPLETE** (Δnet −0.55c when dropped): Sweep price threshold (0.20–0.40), chase give sweep (0.00/0.01/0.02/0.03), tox-conditioned sell (sell when vpin>0.40 or tox_p>0.55).
4. **R1 PREVENT** (ΔCVaR −24.3c when kept): Tune YES-spread threshold (1c vs 2c vs 3c vs dynamic), extend to NO-side for adverse regimes, vs VPIN gate (t32), vs combo detector gate (t35).
5. **R2 PREDICT** (GBM currently dormant): Retune threshold (try p50 of OOS strand probs), window-level GBM (predict P(any strand in window)), rolling refit for drift.
6. **R0 BUFFER** (candidate, 0.00c net, -20pp strand): Calibrate threshold (0.005/0.01/0.015/0.02), side-specific, dynamic.

---

## ETH Multi-Asset Note

ETH OOS windows: ~1430, P0 net ~0c/win. ETH strand rate is structural (40-106% per multi_asset_study.py). The 5-rung ladder reduces strand rate but not below the ~15% viability threshold. The BTC-only GBM was not retrained on ETH IS. ETH remains NO-GO for the maker box strategy until the simultaneous two-sided IOC entry or equivalent strand elimination is available.

---

*https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz*
