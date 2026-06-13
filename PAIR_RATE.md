# PAIR_RATE.md — Kalshi Maker-Box Pairing-Rate Study

**Verdict**: Combining entry filters (k≤9, spread≤3c, flow-imbal≤0.35) with 1c completion-improve raises P(both fill) from 0.89 → **0.97 OOS** while improving net c/win from −5.8c → −1.2c. The P(both)=0.93 cited in the brief is the live-data reference; our tape-replay baseline is 0.89. The achievable ceiling is ~0.975 — binding constraint is YES-strand adverse settlement flow (YES strands average −26c vs NO strands −7c; they resist completion because spot moves against the position before the window closes).

---

## 1. Baseline P(both fill)

| Split | P(both) | #boxes | #strands | mean lock | net c/win |
|-------|---------|--------|----------|-----------|-----------|
| IS (60%, n=144 windows) | 0.8818 | 783 | 105 | 0.84c | −6.39c |
| OOS (40%, n=97 windows) | 0.8911 | 573 | 70 | 0.96c | −5.76c |

**Note**: Tape-replay baseline is 0.89 (vs live 0.93 cited in brief). Gap is consistent with the live bot already deploying some pairing controls not modeled here (--max-net 1, strict same-minute pairing). Strand distribution: YES 32 OOS (mean −26.3c), NO 38 OOS (mean −7.0c). YES strands are 3.8× worse — informed settlement-takers hit the YES side just before resolution.

---

## 2. Ranked 10-Lever Table (OOS, best variant per lever)

| # | Lever | P(both) OOS | net c/win OOS | #boxes | ΔP | Δnet |
|---|-------|-------------|---------------|--------|----|------|
| **BASELINE** | — | 0.8911 | −5.758c | 573 | — | — |
| **L1** | Immediate 1c improve | **0.9440** | −3.352c | 607 | +0.053 | +2.41 |
| **L2** | Escalating improve (1/2/3c) | **0.9440** | −3.352c | 607 | +0.053 | +2.41 |
| **L3** | Taker-complete give=1c | **0.9440** | −3.352c | 607 | +0.053 | +2.41 |
| **L4** | Deadline force 90s (give=1c) | 0.8942 | −5.510c | 575 | +0.003 | +0.25 |
| **L5** | Book-depth thin (completing side) | 0.8715 | −6.182c | 434 | −0.020 | −0.42 |
| **L6** | Both-sides thin | 0.8750 | −6.031c | 434 | −0.016 | −0.27 |
| **L7** | Time-of-window k≤5 | 0.8810 | **−1.322c** | 185 | −0.010 | **+4.44** |
| **L8** | Flow-balance gate ≤20% | 0.8632 | −4.299c | 284 | −0.028 | +1.46 |
| **L9** | Vol-churn gate p50 | 0.9044 | **−1.770c** | 265 | +0.013 | **+3.99** |
| **L10** | Spread≤3c + tilt≤0.30 | 0.9044 | −3.225c | 350 | +0.013 | +2.53 |

**Key observations**:
- **L1/L2/L3 are equivalent** in this data: posting at a0−1c (improvement) achieves the same lift as escalating or immediate taker-cross. All boost P(both) by +5.3pp and net by +2.4c/win — the single most impactful completion lever.
- **L5/L6 (book depth) HURT**: depth data covers all 136 windows with no meaningful depth-P(both) correlation. The depth filter simply drops profitable windows; the overnight_data sample (48 files, 2 days) is too small for reliable calibration.
- **L7 (k≤5) and L9 (vol<p50) are the top entry-selection levers** by net c/win improvement (+4.4c and +4.0c). They work by restricting to early-in-window slots and low-volume slots where the strand risk is lower — not by raising P(both) but by avoiding high-loss strands.
- **L4 (deadline)** has negligible effect: strands that survive to the last 90s of the window tend to be adverse-flow YES-strands that no counterparty wants to complete.

---

## 3. Recommended Policy Combination

### PnL-Optimal Policy (recommended for deployment)
**Entry**: k≤9, spread≤3c, |taker_imbal|≤0.35  
**Completion**: immediate 1c improve on stranded leg (post at a0−1c for YES-strand, b0+1c for NO-strand)

| Split | P(both) | #boxes | mean lock | net c/win | n_windows |
|-------|---------|--------|-----------|-----------|-----------|
| IS | 0.9574 | 472 | 0.80c | −2.23c | 116 |
| **OOS** | **0.9735** | **331** | **0.90c** | **−1.22c** | **72** |

**Δ vs baseline OOS**: P(both) +0.082 (+8.2pp), net c/win +4.54c/win.

### Max-P(both) Policy (not recommended for deployment)
Entry: k≤7, spread≤2c, imbal≤0.20 + 2c improve completion  
OOS: P(both)=0.8613, net=−1.24c, #boxes=118. *Paradox*: tighter entry actually LOWERS P(both) vs PnL-optimal because it drops the most liquid/easily-paired slots. Max-P(both) via restriction = fewer boxes, not more pairs.

### Where They Diverge
PnL-optimal keeps k=8,9 and spread=3c slots which have higher flow and more natural completion opportunities. The narrower Max-P(both) filter removes these, leaving only the most adversely-selected residual strands. **Conclusion**: the PnL-optimal policy IS the max-P(both) policy in this data.

### Achievable Ceiling and Binding Constraint
- **Achievable ceiling ≈ 0.975** (OOS, with entry filter + 1c improve)  
- **Ceiling not 0.98**: the binding constraint is YES-strand adverse flow. Of 32 OOS YES-strands, only 81.2% are completable at give=1c with mean lock=−0.15c (i.e., crossing below breakeven). The remaining 18.8% represent windows where spot has moved so sharply that no taker will sell YES at any reasonable price before settlement.
- **Taker-crossing at give>1c is PnL-destructive**: give=2c reaches 87.5% YES completion but at mean lock=−1.10c — eliminating the economic rationale. Give=3c: 87.5% YES at −2.10c lock. These are worse outcomes than holding the strand to settlement for some price buckets.
- **Trivial 0.98 path (rejected)**: crossing the full spread to buy the missing leg as taker at give=3c forces P(both)≈0.94 but at negative lock (−1.84c avg), destroying P&L. This is the "costs the lock" scenario noted in the study brief.
- **True ceiling to raise further**: front-of-queue improvement (queue position tracking, t27 findings) could reduce strand formation rate. QUEUE_VALUE.md confirms 85.2% of fills happen at q_ahead=0 — being front-of-queue on BOTH sides simultaneously is the structural barrier. Queue position on the completing side is uncorrelated with queue position on the opening side in the current implementation.

---

## 4. Literature Takeaway

**Queue-reactive market making** (Avellaneda & Stoikov 2008, *High Frequency Trading in a Limit Order Book*): optimal quotes are symmetric around mid, adjusted for inventory and queue depth. For prediction-market boxes, the key insight extends directly: inventory imbalance (YES-only fill = positive gamma) requires completion quotes biased toward the missing leg. **Lever 1/3 is the operationalization** — posting at a0−1c after a YES-strand is the discrete analog of Avellaneda-Stoikov's dynamic inventory-triggered repricing.

**Adverse selection and fill asymmetry** (Glosten & Milgrom 1985, *Bid, Ask and Transaction Prices*): informed traders preferentially arrive on the side that will resolve favorably. Our YES-strand mean of −26.3c vs NO-strand −7.0c is direct evidence: informeds buy YES just before UP resolution, taking our YES bid before we can complete the NO leg. This is the "toxic YES fill" signature. **Mitigation**: flow-balance gate (L8) and vol-churn gate (L9) screen out high-informed-flow windows, consistent with Glosten-Milgrom's prediction that market makers should withdraw quotes in high-information regimes.

**Prediction-market microstructure** (Berg, Forsythe, Nelson, Rietz 2008, *Results from a Dozen Years of IEM Research*; also Budish, Cramton, Shim 2015 on latency arbitrage): in binary prediction markets, the bid-ask spread encodes the marginal cost of adverse selection, not inventory risk. Box strategies eliminate directional risk but retain the "two-sided simultaneous fill" execution problem — the precise focus of this study. The key finding is structural: single-window fill probability is bounded by the arrival rate of informed flow, not by our quote aggressiveness.

**Sources**: Avellaneda & Stoikov (2008) *IJTAF* 11(3); Glosten & Milgrom (1985) *JFE* 14(1):71–100; Budish, Cramton & Shim (2015) *QJE* 130(4):1547–1621.

---

## 5. Summary

| Policy | P(both) OOS | net c/win OOS | #boxes | Status |
|--------|-------------|---------------|--------|--------|
| Baseline | 0.8911 | −5.758c | 573 | Current |
| L1/L3 (1c improve only) | 0.9440 | −3.352c | 607 | Deploy now |
| **PnL-Optimal Combo** | **0.9735** | **−1.215c** | **331** | **Recommended** |
| Max-P(both) (k≤7, tight) | 0.8613 | −1.239c | 118 | Not recommended |
| Taker-cross give=3c | ~0.94 | ~−2.5c | ~600 | Reject (lock cost) |

The net c/win remains negative because strand losses (avg −15c) dwarf box gains (avg +1c per event). The combo policy reduces strand count from 70 to 9 OOS and raises P(both) to 0.97, making the per-window P&L −1.2c (vs −5.8c baseline). For the strategy to be net positive, either: (a) live box sizes must be much larger (scale effect), or (b) the +5.4c/win in box-only windows (no strands) must dominate — which the combo achieves by avoiding most strand-forming windows.

https://claude.ai/code/session_015L9LmWW7LrbuVCAyawnbWz
