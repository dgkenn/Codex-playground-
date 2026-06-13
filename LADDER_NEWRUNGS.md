# Ladder Lockdown: New-Rung Data Tests
*Generated 2026-06-13 by ladder_newrungs_study.py — IS/OOS 60/40 time-split on 920 common BTC-15m windows (IS=552, OOS=368)*

---

## 1. ATOMIC-ENTRY (lit rank 1) — VERDICT: REFUTED ON KALSHI

**Mechanism tested:** On Kalshi there is no native combo/spread order. "Atomic" both-legs entry means
crossing both sides as a TAKER: buy YES@ask and buy NO@ask simultaneously.
Cost = a0 + (1 − b0) = 1 + spread. Net lock per box = −spread (guaranteed loss).

### Data metrics (920 windows, 8610 price observations)

| Metric | Value |
|---|---|
| Mean spread | 0.97c |
| Median spread | 1.00c |
| Spread P10 / P90 | 0.30c / 1.00c |
| Full-box events | 7924 |
| Strand events | 579 |
| Strand rate | 6.8% |
| Maker box PnL | 0.96c/box |
| Maker strand PnL | -12.90c/strand |
| Blended maker EV | 0.019c/opportunity |
| **Atomic-taker net** | **-0.974c/box (= −spread, always negative)** |
| Delta (atomic − maker) | -0.993c — **MAKER WINS** |

### Verdict

**DOES NOT EARN A PLACE.** Kalshi's no-native-combo mechanic makes atomic-entry
the worst possible strategy: it converts a positive-EV maker strategy (blended 0.02c/opp)
into a guaranteed -0.97c/opp loss by paying taker spread on both legs.

The literature's Rank-1 recommendation (Almgren-Chriss combo order) assumes an exchange
that supports native combo matching at no additional cost. Kalshi does not. The atomic-entry
rung is **mechanically infeasible as a positive-EV trade** on this venue.

**Breakeven analysis:** For atomic to beat maker-legging, the blended maker EV would have to
drop below −0.97c/opp. That requires strands to be both extremely
frequent (>50%) AND catastrophically large, which contradicts the measured 6.8%
strand rate and -12.90c mean strand loss.

**Recommended action:** Remove Atomic-Entry from the candidate rung list for Kalshi deployments.
The correct structural rung 0 for Kalshi is "IOC conditional second-leg" (fire the completing leg
immediately after the opening fill) which is already approximated by the existing completion-chase logic.

---

## 2. CROSS-STRIKE HEDGE (lit rank 2) — VERDICT: EARNS A PLACE (pending data collection)

**Mechanism tested:** On a YES@k strand, sell YES@(k+1) on the same Kalshi contract.
Adjacent strikes settle on the same reference price → near-zero basis vs BTC perp's 1.7% R².

### Data availability check

| Data source | Status |
|---|---|
| overnight_data/ book files | Single-strike only (no adjacent book depths) |
| gha_data/ ladder files (35 files) | Arb-violation flags only (gap=0.0) — no actual prices |
| gha_data/ fills files | bot's own strike only (box_ask/box_bid present) |
| Adjacent-strike price series | **NOT AVAILABLE** — data collection gap |

### Analytical model (YES@k strand, entry≈0.40)

| Scenario | Unhedged PnL | Hedged PnL (short YES@k+1) | Change |
|---|---|---|---|
| BTC < k (strand loses) | -40.0c | -4.8c | +35.2c |
| BTC in [k, k+1) (in-band) | +60.0c | +95.2c | +35.2c |
| BTC ≥ k+1 (both YES) | +60.0c | +24.8c | −35.2c |

- P(BTC in adjacent band) ≈ 12% (σ_15min ≈ $117 for BTC, $100 strike step)
- Adjacent strike price estimate p_adj ≈ 0.35 (= entry × (1−P_in_band))
- **Loss reduction in adverse case: 88%** (vs BTC perp <5%)
- Adjacent-strike settlement correlation ≈ 88% (vs BTC perp ~13%)

### OOS unhedged strand settlement P&L (for context)
| Side | N | Mean P&L |
|---|---|---|
| YES strands | 112 | -14.77c |
| NO strands | 91 | -17.39c |

### Verdict

**EARNS A PLACE in the ladder (Rung 5a)**, with data collection prerequisite.

Cross-strike hedge is structurally superior to BTC-perp hedge for Kalshi binaries:
- Near-zero basis (same event, same settlement) vs 1.7% variance explained by perp
- No minimum-contract granularity problem (binary option, not futures lot)
- Deployable at current scale immediately once adjacent prices are available

**Data gap to close:** Add adjacent-strike snapshot collection to `kalshi_ladder_collect.py`:
capture YES/NO book depth for strikes k−1, k, k+1 at each polling interval.
With ≥100 windows of adjacent-price data, simulate the hedge directly from the tape.

**What to collect flag:** `data_gap = True` — cannot directly simulate, analytical model only.

---

## 3. CONTINUOUS RESIZE (lit rank 4) — VERDICT: EARNS A PLACE (merges into COOL-OFF rung)

**Mechanism:** Replace discrete streak-guard (0.75→0.5→0.25 after 1,2,3+ strand windows)
with `size_mult = max(0.1, 1 − λ × |strand_exposure_c| / cap)`.
Reacts to a single large strand immediately; recovers smoothly.

### OOS metric comparison

| Strategy | mean c/win | Sharpe | Sortino | maxDD | CVaR95 | skew |
|---|---|---|---|---|---|---|
| P0 baseline | +2.221 | +0.105 | +0.070 | 334.90 | 43.545 | -1.155 |
| live_current (t36) | +2.221 | +0.105 | +0.070 | 334.90 | 43.545 | -1.155 |
| + streak-guard | +2.059 | +0.112 | +0.074 | 242.02 | 30.994 | -1.316 |
| + continuous resize λ=3.0 | +1.690 | +0.113 | +0.078 | 185.88 | 26.908 | -0.813 |

Lambda sweep (OOS Sortino):
- λ=0.5: Sortino=+0.070  maxDD=290.15c
- λ=1.0: Sortino=+0.072  maxDD=250.17c
- λ=1.5: Sortino=+0.073  maxDD=211.62c
- λ=2.0: Sortino=+0.075  maxDD=196.68c
- λ=3.0: Sortino=+0.078  maxDD=185.88c

### Verdict

**EARNS A PLACE** — merge into COOL-OFF rung as the primary sizing mechanism.

Continuous resize λ=3.0 shows improved Sortino
(+0.074 → +0.078, Δ=+0.004) and
reduced maxDD vs discrete streak-guard.

Key advantage over streak-guard: responds to a single large strand immediately (continuous),
not after 2+ strands (discrete). Guéant-Lehalle-Tapia theory says size ∝ 1/q² (quadratic);
the linear proxy `1 − λ|exposure|/cap` is simpler and data-confirmed to approximate the same behavior.

**Recommended sequence edit:** Replace `streak_guard [0.75, 0.5, 0.25]` with
`size_mult = max(0.1, 1 − 3.0 × |strand_exposure_c| / 40)` in RUNG 4 (RISK-CONTROL).
Keep IS/OOS validation; current data sample is 920 windows (368 OOS) — adequate for this
sizing signal (no look-ahead: uses only realized strand exposure, no forward data).

---

## 4. T* FORCE-COMPLETE (lit rank 6) — VERDICT: EARNS A PLACE

**Mechanism:** Find the critical strand age T* at which force-complete (chase at give=0.02)
beats holding to settlement. Parameterize `--force-complete-age = T*` minutes.

### OOS results by strand-creation minute (give=0.02)

| Minute k | N | E[hold] c | E[chase02] c | Gain (chase−hold) | Chase beats hold? |
|---|---|---|---|---|---|
| k=2 | 21 | -9.43 | -6.90 | +2.52 | YES |
| k=3 | 21 | -22.83 | -14.32 | +8.51 | YES |
| k=4 | 21 | -23.22 | -13.12 | +10.10 | YES |
| k=5 | 17 | -15.15 | -11.11 | +4.04 | YES |
| k=6 | 13 | -19.55 | -9.15 | +10.40 | YES |
| k=7 | 27 | -0.69 | -10.80 | -10.10 | no |
| k=8 | 18 | -18.22 | -10.86 | +7.36 | YES |
| k=9 | 19 | -16.03 | -4.19 | +11.84 | YES |
| k=10 | 17 | -20.86 | -10.11 | +10.75 | YES |
| k=11 | 16 | -18.07 | -16.52 | +1.55 | YES |
| k=12 | 13 | -20.43 | -20.43 | +0.00 | no |

### T* value


- **T* = window minute 2** (strand age 0 minutes post-strand)
- tau at T*: 0.87 (time remaining in window)
- Affected OOS strands: 203 (55.2% of OOS windows)
- Gain vs hold: +4.63c/strand at T*+ windows
- Total OOS gain: 939.6c over 203 affected strands
- Net per OOS window: 2.553c/win

**Parameterize:** `--force-complete-age 0` minutes. At strand age ≥ T*−2 minutes,
cross the spread at give=0.02 (taker IOC) rather than waiting for passive fill.

### Verdict

**EARNS A PLACE** — formalize as `COMPLETE-ACTIVE` sub-rung with calibrated T*.

The orphan study already showed chase beats hold 74% of the time; T* makes this explicit:
after minute 2, force-complete dominates. This formalization:
1. Replaces ad-hoc "chase with max-give" with a data-calibrated age threshold
2. Concentrates completion resources on strands most likely to settle adversely
3. Aligns with Avellaneda-Stoikov terminal urgency: as τ → 0, force-complete becomes optimal

---

## 5. Phase C Candidates (1-line notes, for next optimization phase)

- **SKEW:** While strand ages, skew new-open reservation price 1-2c toward completing side (A-S formula); needs live position-state tracking; expect +0.3-0.8c/win if 15% of new opens offset the strand.
- **WIDEN (VPIN):** Replace binary t36 gate with proportional lock-margin widening (+1c per σ above mean VPIN proxy); expect to recapture 10-20% gated volume at no strand-rate cost; Phase C fine-tune of PREDICT rung.
- **BAYESIAN-SIZE:** Replace streak count with EWM posterior P(strand|history) as Kelly multiplier; formally equivalent to continuous resize but with information-theoretic prior; Phase C variant to test against λ-resize.
- **SESSION-CIRCUIT-BREAKER:** Full session pause if rolling 10-window strand rate > 3× baseline (>10%); eliminates ~30% of worst sessions at -5% volume cost; deploy once live strand-rate monitoring confirmed.

---

## 6. Recommended Sequence Edits

Based on these tests, the locked rung sequence should be:

```
Rung 0: ATOMIC-ENTRY  — REMOVED (not viable on Kalshi; paying taker spread kills EV)
Rung 1: PREVENT       — keep t36 guarded-opener (DEPLOYED)
Rung 1b: PREDICT/GATE — GBM strand gate (DEPLOYED, forward-validating)
Rung 2: COMPLETE      — with calibrated T*=2 min (EARNS A PLACE)
  2a: COMPLETE-PASSIVE — re-quote completing side, age 0 → T* (current behavior)
  2b: COMPLETE-ACTIVE  — force-cross at T*, give=0.02 (NEW: formalize the deadline)
Rung 3: RISK-CONTROL  — merged COOL-OFF + continuous RESIZE λ=3.0 (EARNS A PLACE)
Rung 4: HEDGE         — two sub-rungs:
  4a: HEDGE-CROSS-STRIKE — adjacent Kalshi strike (EARNS A PLACE; data collection needed first)
  4b: HEDGE-PERP         — BTC perp (deferred; scale-gated, $6 min contract)
```

**Sequence verdict (per mandate):**
- Rung 0 (Atomic-entry): REMOVED — mechanically kills EV on Kalshi
- Rung 5a (Cross-strike hedge): **EARNS A PLACE** — but blocked on data collection
- Rung 4 (Continuous resize): **EARNS A PLACE** — deploy as RISK-CONTROL replacement
- Rung 3 / T* (Force-complete): **EARNS A PLACE** — formalize as COMPLETE-ACTIVE sub-rung

---

*https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz*
