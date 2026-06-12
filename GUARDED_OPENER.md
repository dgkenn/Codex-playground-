# GUARDED_OPENER.md — Live-Deployable Spec for t36_guarded_opener

## What This Solves

Live audit (2-day, 103 fills): **100% of realized losses** came from one mechanism —
a stranded YES leg. Our YES bid fills as spot falls toward it; the NO bid never pairs;
BTC closes below strike; YES settles $0. **6 of 8 strands were YES-side** (structural
asymmetry confirmed: YES fills at −1.3c spread vs NO at +1.3c).

---

## The Winning Policy: t36_guarded_opener (A-S Skew Approximation)

### Exact Rule (two conditions, either blocks the open):

```
SKIP a leg if:
  (1) it is the YES side (bid) AND spread < 2c   [t02: structural YES-caution]
  OR
  (2) adverse spot move > 8bps (sig > 8) AND spread < 2c  [t07+spread floor]
```

In code (`box_policy_ab.py`, lambda for `open_ok(f, s)`):
```python
not (f["side"] == "bid" and f["spread"] < 0.02)
and not ((f.get("sig") or 0.0) > 8.0 and f["spread"] < 0.02)
```

### Interpretation

This is an Avellaneda-Stoikov reservation-skew approximation. True A-S skew would
demand 1c more edge on the threatened side (quote 1c lower on YES when vol is high).
Since the parquet replay cannot price-improve individual fills, we approximate via a
**binary spread floor**: on any leg touched by structural toxicity (YES) or momentum
toxicity (sig>8), we require the spread to be at least 2c before opening. At the 2c
boundary the two approaches are equivalent (A-S would just barely open; we do too).

The t35_combo_tox_gate (VPIN+detectors logistic) is NOT in the deployed policy:
at THRESH=0.3656 it fires on <0.1% of opens on the BTC tape, adding no incremental
gate over t02+t07. It remains a separate prospective trial (t35) for its own n≥300.

---

## IS/OOS Results (1163 BTC windows, 60/40 time-split)

### Summary Table

| Variant | IS net c/win | IS tstat | OOS net c/win | OOS tstat | OOS skip% | OOS pair-rate | OOS maxDD c |
|---|---|---|---|---|---|---|---|
| P0 (baseline) | +2.79 | — | +0.69 | — | 0.0% | 99.2% | 4667 |
| t02 YES-caution | +4.36 | +1.41 | +1.93 | +0.88 | 23.4% | 96.2% | 92 |
| t07 spot-gate | +2.62 | −0.39 | +0.86 | +0.18 | 10.5% | 98.2% | 25432 |
| t35 combo-tox | +2.74 | −0.95 | +0.69 | 0.00 | 0.1% | 99.2% | 4505 |
| t36a UNION | +4.28 | +1.35 | +1.85 | +0.86 | 34.8% | 96.7% | 556 |
| t36b SPOT+SIDE | +4.05 | +1.17 | +1.19 | +0.41 | 45.0% | 97.0% | 85 |
| t36c VOTE-2-of-3 | +3.14 | +1.08 | +1.41 | +1.00 | 4.3% | 98.7% | 9494 |
| **t36d AS-SKEW** | **+4.30** | **+1.37** | **+2.07** | **+1.03** | **34.4%** | **96.7%** | **1246** |

IS = first 697 windows (60%), OOS = last 466 windows (40%). Sort key: `ws` (unix timestamp).

### Strand Decomposition (OOS)

| Variant | YES strands/win | NO strands/win | Strand cost c/win | ΔStrand YES vs P0 |
|---|---|---|---|---|
| P0 | 0.077 | 0.060 | −0.47 | — |
| t36d AS-SKEW | 0.002 | 0.363 | +0.18 | **−0.075 (−97%)** |
| t36a UNION | 0.006 | 0.358 | +0.17 | −0.071 (−92%) |
| t36b SPOT+SIDE | 0.002 | 0.277 | +0.05 | −0.075 (−97%) |
| t36c VOTE-2-of-3 | 0.056 | 0.155 | −0.71 | −0.021 (−27%) |

---

## Why t36d Wins

1. **YES strands eliminated**: cuts YES strands from 0.077 to 0.002/window (−97%), the
   primary loss source. Strand cost flips from −0.47c to +0.18c/win.

2. **Volume retained**: skips 34.4% of opens (only YES legs at thin spreads + any leg
   in a moving market at thin spreads). Pair-rate 96.7% vs 99.2% P0 — acceptable.

3. **Decomposition (OOS)**: +1.39c/win improvement over P0 breaks down as:
   - ~+0.65c from strand cost improvement (YES strands → near-zero)
   - ~+0.74c from improved per-fill quality on retained fills
   The trade-off: skipping YES at thin spreads loses some box volume but avoids toxic
   inventory. The favorable NO strands that remain (+0.303 extra vs P0) are mildly
   +EV (t08 finding: unpaired NO held to settlement is +EV).

4. **vs alternatives**:
   - t36a UNION adds t35 (combo-tox) on top but t35 fires <0.1% → nearly identical to t36d
   - t36b SPOT+SIDE skips 45% of opens (too aggressive, loses box volume)
   - t36c VOTE-2-of-3 only cuts 27% of YES strands (insufficient protection)
   - t07 alone: minimal gate (10.5% skip), high OOS maxDD (25,432c) due to spot-gate
     asymmetry — gates NO legs with upward moves that were actually fine

5. **Honest caveats**:
   - OOS t-stat = 1.03 (well below deploy bar of 3.0, below even the 2-sigma alert)
   - This is an IS/OOS on the 20k-fill HISTORICAL tape, not prospective forward data
   - The forward A/B (box_policy_ab.py) is the binding gate; needs n≥300 windows

---

## Deployment Checklist

### Flags and Features Needed in kalshi_trader.py

| Feature | Status | Source |
|---|---|---|
| `spread` (ask − bid at quote time) | Available | Best-bid, best-ask from book snapshot |
| `sig` (3-min spot move in bps) | Available | `sig_adv` in collect_fills / kalshi_sizing.py |
| Side detection (YES=bid, NO=ask) | Available | Order side in the resting logic |

### Conditions the Live Opener Must Check

```python
# At open time, before resting a new leg:
spread = best_ask - best_bid          # from current book snapshot
sig = spot_bps_3min                   # 3-min spot move bps, + = adverse to this side

# Block YES (bid) if spread is thin:
if side == "YES" and spread < 0.02:
    skip()

# Block ANY leg in a moving market if spread is thin:
if abs(sig) > 8.0 and spread < 0.02:
    skip()
```

Note: `sig` as used in window_fills is already oriented as adverse to the side (bid side
sees positive sig for downward spot moves). The `abs(sig)` version in t36b was tested but
performed worse (higher skip%, lower OOS return) vs the `sig > 8` (adverse-only) version
already in t07. The final rule uses `(sig or 0.0) > 8.0` matching t07's exact formula.

### What Is Missing (not yet in kalshi_trader.py)

1. **The spread floor check on opening**: kalshi_trader.py does not currently inspect
   the spread as a gate for YES legs. Would need: `if side==YES and spread < MIN_SPREAD_YES: skip`.
2. **Spot-move gate conditioned on spread**: t07 already exists as a standalone gate but
   is not deployed. This policy adds the spread-conditioned version.
3. **The `--min-spread` flag** exists but gates BOTH sides equally. We need an asymmetric
   YES-specific spread floor.

---

## Deployment Bar

**Do NOT deploy to live money** until:
- n ≥ 300 forward windows in the prospective A/B (box_policy_ab.py) show t36_guarded_opener
  vs P0 with paired t ≥ 3.0 (T_BAR) AND maxDD(t36) ≤ 1.25 × maxDD(P0).
- At ~5–10 windows/day, that is approximately 30–60 days of forward accumulation.
- Current forward ledger: 100 windows (as of 2026-06-12). Need ~200 more.

The 2-sigma alert (ALERT_T=2.0, ALERT_N=100) will fire if the forward data confirms
the direction; that triggers a review but NOT auto-deploy.

---

## Registration

Registered in `box_policy_ab.py` as `t36_guarded_opener` (inside TRIALS dict, after t35).
The lambda is self-contained: no new imports, no new module dependencies.
Forward scoring begins automatically on the next collector run.
