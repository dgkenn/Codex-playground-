# PAIR-GATE: cutting maker-box strand rate to <5% (BTC 15m)

**Verdict: YES — the BTC box can be paired reliably.** A simple decision-time entry gate
(**both-sides depth ≥ median + no opens in the last 2 minutes + spot-move filter**) cuts the
window strand rate from **14.8% → 1.9%** while retaining **86% of volume**, turning net/box from
the current **≈ −2c** into **+0.46c**, stable IS↔OOS, Sharpe +0.23. ETH does NOT pair profitably
(box edge stays negative even gated) — run the box on BTC only.

> SCREENING CAVEAT: this is a tape-replay fill model. It is optimistic on strands (the pairing leg
> is assumed to fill). Treat the **strand-rate reduction as DIRECTIONAL** evidence that the gate
> targets the right conditions, not as a guaranteed live number. Forward (paper/pilot) validation
> required before sizing up. The edge magnitude (+0.4–0.7c/box) is consistent with the audited
> +0.69c live / +0.37c backtest paired edge.

---

## 1. Strand rate by entry condition (per opening leg, BTC, n=8,080 opening fills)

Overall per-leg strand rate 1.7%; window-level strand (yes-count≠no-count) 14.8%.

**(d) K-SLOT — the dominant predictor (and tail source):**

| k (minute) | strand% | n   |     | k | strand% | n   |
|-----------:|--------:|----:|-----|--:|--------:|----:|
| 2 | 0.0% | 894 |  | 8  | 1.0% | 769 |
| 3 | 0.1% | 867 |  | 9  | 2.5% | 708 |
| 4 | 0.1% | 848 |  | 10 | 3.8% | 632 |
| 5 | 0.2% | 849 |  | 11 | 5.3% | 507 |
| 6 | 0.8% | 837 |  | **12** | **12.0%** | 357 |
| 7 | 0.6% | 812 |  |    |       |     |

Late opens (k=11–12) carry both the high strand rate AND the catastrophic tails: every
settle < −50c strand (and the −95.6c worst case) is a k=11–12 leg bought near par that the binary
ran away from. **Capping k ≤ 10 removes the catastrophic tail entirely** (worst residual −19c).

**(b) MIN BOTH-SIDE DEPTH (top-5 displayed):** thin books pair fine; the *thickest* quintile
strands MORE (2.9% vs 1.4%) — heavy displayed size = informed pressure that runs the other leg.
Using `depth ≥ median` keeps the bulk of volume and trims the worst opens.

| depth quintile | strand% |
|---|---|
| Q1 (3.4k–21k) … Q4 (38k–51k) | ~1.4% |
| Q5 (51k–248k) | 2.9% |

**(e) |SIG| (spot bps move into the leg):** 0–2bp 1.1% → 5–10bp 2.5%. `|sig| < 10` shaves the
adverse-momentum opens that strand.

**(a) Microprice divergence |p_yeq−0.5|, (c) spread, (f) flow:** weak/non-monotone predictors at
the per-leg level. Divergence "gates" (e.g. div≤.05) work only because they select near-0.5 prices
— they kill box edge (boxedge → −0.04c) and crush volume. **Not recommended as the primary gate.**

## 2. Pair-gate grid (target strand <5%, keep volume) — BTC full sample

| gate | traded% | strand% | box edge | net/box |
|---|---:|---:|---:|---:|
| **no-gate (current)** | 100% | **14.8%** | +0.29c | +0.18c |
| **depth≥med + k≤10 + \|sig\|<10  ← RECOMMENDED** | **85.7%** | **1.9%** | **+0.49c** | **+0.46c** |
| depth≥med + k≤9 + \|sig\|<10 | 83.2% | 1.0% | +0.46c | +0.44c |
| depth≥q75 + k≤10 | 63.4% | 2.2% | +0.43c | +0.43c |
| div≤.05 + depth≥med + \|sig\|<10 (low-vol, high-purity) | 25.5% | 0.4% | +0.37c | +0.51c |
| div≤.10 + depth≥med (no k-cap) | 45.3% | 1.0% | +0.38c | +0.49c |

Many gates clear strand<5%. The recommended one is chosen for **max retained volume × positive
net/box**: it keeps 86% of windows, strand 1.9% (< 4.3% break-even), and is net-positive.

## 3. Disposal cost by timing (residual stranded legs)

On the **gated** residual strands (n=15, the legs that still strand under the recommended gate):

| disposal | mean cost/strand | worst |
|---|---:|---:|
| HOLD to expiry (late/force) | −6.83c | −19.0c |
| **EARLY cross at k+1 (~15–20s, small move)** | **−5.14c** | **−16.8c** |

**Early-cheap-cross beats late-force-hold by +1.69c/strand**, confirming the live finding (late
force paid up to +$0.83 over par; here the k-gate plus early cross caps the worst at −19c, no −83c
events). On the **ungated** strands the late-force tail reaches −95.6c — that tail is *entry-driven*
(near-par k=12 legs), so the **k≤10 entry gate is what kills it**, not the disposal rule.

**Give-cap recommendation:** cross EARLY by default; **HOLD instead if the early cross would lock a
loss worse than −15c** (give-cap = 15c). With the gate in place only ~1 in 15 residual strands ever
hits the cap, so the cap is a cheap belt-and-suspenders rather than the main lever. (Wider caps to
22c give nearly identical mean; tighter than ~10c starts forcing more holds without benefit.)

## 4. Combined (pair-gate + give-capped early disposal) — IS/OOS stability

Gate = `depth≥median(33,195) + k≤10 + |sig|<10`; disposal = early cross, give-cap 15c:

| split | traded | strand% | box edge | net/box | net/win | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| BTC IS  (first 60%) | 83.1% | 1.3% | +0.48c | **+0.46c** | +1.30c | +0.24 |
| BTC OOS (last 40%)  | 89.6% | 2.7% | +0.51c | **+0.46c** | +1.79c | +0.22 |
| BTC FULL | 85.7% | 1.9% | +0.49c | **+0.46c** | +1.50c | +0.23 |

**Net/box +0.46c IS == +0.46c OOS — robust, not overfit.** vs current ≈ −2c/box this is a ~+2.5c
swing, driven almost entirely by the strand-rate collapse (14.8%→1.9%).

**ETH cross-check (same structural rule, ETH-local median depth):** strand drops 40.7%→8.7%, **but
box edge stays NEGATIVE (−1.1c/box, Sharpe −0.26)**. ETH's book is too thin (median depth 844 vs
BTC 33k) — the paired edge isn't there, and no gate manufactures it. **Do not run the box on ETH.**

---

## DEPLOY — exact trader flags (BTC 15m maker-box only)

```
box_enabled_assets      = ["BTC"]        # ETH box edge is negative — OFF
gate_min_both_depth     = 33000          # top-5 displayed size, min(bid,ask) side; ~BTC median
gate_max_open_k         = 10             # no NEW opening legs in the last 2 minutes (k>10)
gate_max_abs_sig_bps    = 10             # skip opens with |3-min spot move| >= 10 bps into the leg
disposal_mode           = "early_cross"  # cross unpaired leg at the touch ~15-20s after detection
disposal_give_cap_cents = 15             # if early cross locks worse than -15c, HOLD to expiry
# pairing leg is always completed; gate applies to OPENING legs only
```

Expected (screen): strand ≈ 2% (vs 14.8%), ~86% window participation, net/box ≈ +0.46c,
Sharpe ≈ +0.23, stable IS↔OOS. Forward-validate strand rate on paper before scaling.
