# BOX_REGIME — can WINDOW-SELECTION (a regime/time filter) turn the Kalshi BTC 15M maker-box net-positive?

**Verdict (one line): NO. Strand is effectively REGIME-INVARIANT. No pre-open feature
(time-of-day, day-of-week, session, opening book depth/spread, recent realized vol, strand-streak,
distance-to-round-strike) carves out a window subset with strand reliably below the ~4.4% break-even
AND with enough windows to matter AND stable out-of-sample. The lowest *robust* bucket sits at
~12–15% strand — 3–4× over break-even — and every filter that looks good in-sample REVERSES on the
OOS holdout and across 3 time folds. One hypothesis even runs BACKWARDS: deeper opening book →
*worse* strand (35% at the top decile vs 18.5% baseline), not better. The box's fate rests entirely
on the queue-timing / completion fix; there is no window-selection lever that rescues it the way the
BTC-trend gate rescued momentum.**

---

## Data, N, costs, screens

- **Tape (for N):** `gha_data/2026-06-{10,11,12,13}/` collector streams (book / trades / fills /
  shadow_windows), the SAME forward streams `box_policy_ab.py` reconstructs from. Per-window box
  outcomes reconstructed with `box_policy_ab.window_fills` (collect_fills logic, q0=0 front-of-queue,
  always-pair P0) + settlement from `resolved_up`.
- **N = 162 windows** with book+settle+tape+fills (06-11..06-13 have book/depth/spread; 06-10 lacks
  book records). Book regime features available for all 162.
- **Live (for strand-rate TRUTH):** `live_state/2026-06-{13,14}/kalshi_winrec_btc15m.jsonl` =
  **4 winrecs** — far too few to bucket; used only to confirm the tape's strand level is right.
  Tape baseline strand **18.5%** matches the live ~18% post-fix figure (BOX_SIZING_ALLOC).
- **Costs / break-even:** clean edge **+0.69c/box**, bounded post-fix toxic loss **−15c** →
  break-even strand **p\* = 0.69/(0.69+15) ≈ 4.4%** (BOX_SIZING_ALLOC, AUDIT_EDGE agree). Live-net
  per window modeled as `0.69·(1−s) − 15·s`. CRYPTO15M maker fee = 0.
- **SCREEN flags:** the from-fills `net(fill)` column uses the optimistic q0=0 backtest strand
  losses (small) and is NOISY/misleading; the **`net(live)` column (live-calibrated −15c tox) is
  the load-bearing one** and is reported alongside everywhere.
- Reproduce: `python box_regime.py` (writes `box_regime_windows.csv`).

Baseline (all 162 windows): **strand = 0.185, live-net = −2.22 c/box-window.**

---

## Per-regime strand / net table (live-calibrated net = 0.69·(1−s) − 15·s)

Only buckets with n≥6 shown; full output in `box_regime.py`. `frac_vol` = share of all windows.

### Session (broad, robust cut)
| session | n | strand | live-net c | frac_vol |
|---|---|---|---|---|
| Asia 0–8 UTC | 62 | 0.145 | −1.59 | 0.38 |
| EU 8–13 UTC | 28 | 0.179 | −2.11 | 0.17 |
| US 13–24 UTC | 72 | **0.222** | −2.80 | 0.44 |

→ US hours are the *thesis-favored* "deep liquidity" regime but have the **WORST** strand. Backwards.

### Opening book depth (top-5 min displayed size), quartiles
| depth bucket | n | strand | live-net c |
|---|---|---|---|
| q1 (thinnest) | 41 | 0.146 | −1.61 |
| q2 | 40 | 0.200 | −2.45 |
| q3 | 40 | 0.150 | −1.66 |
| q4 (deepest) | 41 | **0.244** | −3.14 |

Plateau scan: depth>q0.5 → 19.8%; >q0.7 → 22.4%; **>q0.9 → 35.3%.** Monotone WRONG direction:
**deeper book = more strand**, not less. The "trade only when book is deep" hypothesis is falsified.

### Recent realized vol (prev-window early vol, bps), quartiles
| prev-vol bucket | n | strand | live-net c |
|---|---|---|---|
| q1 (calmest) | 40 | 0.150 | −1.66 |
| q2 | 40 | 0.200 | −2.45 |
| q3 | 39 | 0.205 | −2.53 |
| q4 (most vol) | 40 | 0.200 | −2.45 |

Calm is marginally better (15% vs 20%) but **not below break-even** and **not stable** (see folds).

### Opening spread
| spread | n | strand | live-net c |
|---|---|---|---|
| = 1c | 151 | 0.166 | −1.91 |
| > 1c | 11 | **0.455** | −6.44 |

Wide-spread windows ARE reliably toxic — but that is **already inside the live pair-gate** (it
requires a tight 1c book) and is only 7% of windows. No incremental edge.

### Strand streak / cooloff (autocorrelation)
- Lag-1 autocorrelation of strand **r = 0.181** (mild clustering).
- P(strand | prev stranded) = **0.333** vs P(strand | prev clean) = **0.152**.
- Cooloff (skip a window after any prev strand) trims strand to **15.2%** — real, but still **3.5×
  over break-even**, live-net still **−1.69c**. It does not flip the sign.

### Day-of-week / round-strike distance: no usable signal (all 11–22% strand, no monotone, unstable).

---

## Filter tests — good-regime-only vs always (OOS = last 30% by time)

`keep` = fraction of windows retained (net-of-volume sanity). Live-net is the honest column.

| filter | ALL keep | ALL strand | ALL live-net | IS strand | OOS strand | OOS live-net | survives OOS? |
|---|---|---|---|---|---|---|---|
| (a) calm-vol only (<med) | 0.49 | 0.165 | −1.89 | 0.103 | **0.225** | −2.84 | **NO** (IS 10%→OOS 22%) |
| (b) deep-book only (>med) | 0.50 | 0.198 | −2.41 | 0.182 | 0.267 | −3.49 | **NO** (wrong direction) |
| (c) US-hours (13–24) | 0.44 | 0.222 | −2.80 | 0.197 | **0.500** | −7.15 | **NO** |
| (d) cooloff (skip after strand) | 0.81 | 0.152 | −1.69 | 0.138 | 0.184 | −2.20 | NO (best, still 3.5× BE) |
| (e) tight-spread (≤1c) | 0.09 | 0.400 | −5.59 | 0.455 | 0.250 | — | NO (already gated) |
| (f) far-from-strike (>250) | 0.75 | 0.190 | −2.29 | 0.165 | **0.250** | −3.23 | **NO** |
| (combo) deep AND calm | 0.17 | 0.214 | −2.67 | 0.167 | 0.300 | −4.02 | **NO** (+ tiny n) |

**Not one filter produces a positive live-net in any split.** The best live-net achieved by any
filter is ~−1.7c (cooloff), still deeply negative. Every "good" in-sample strand reverses OOS.

### 3-fold contiguous time-split (stability)
| filter | fold0 strand | fold1 strand | fold2 strand | stable? |
|---|---|---|---|---|
| deep-book>med | 0.152 | 0.219 | 0.250 | drifting up |
| calm-vol<med | **0.067** | 0.150 | 0.205 | **collapses** |
| cooloff (prev-clean) | 0.125 | 0.171 | 0.163 | stable but all >12% |
| far-from-strike>250 | **0.118** | **0.276** | 0.220 | **flips** |

Every filter's apparent edge lives in ONE fold and evaporates in the next — the textbook overfit
signature. **No bucket of n≥20 anywhere reaches strand <5%.** The achievable floor is ~12%.

---

## VERDICT

**Strand is regime-invariant; there is NO deployable window-selection filter.**

1. **No feature+threshold turns the box net-positive.** Break-even needs strand <4.4%; the lowest
   robust, sufficiently-populated bucket is ~12–15% (cooloff / calm-vol / Asia), 3–4× over the bar,
   live-net stuck at −1.7 to −2.2c/box. Best filter retains 81% of windows and still loses money.
2. **The flagship hypothesis is backwards.** Deeper/US-hours books have *more* strand, not less —
   consistent with the strand mechanism being queue contention behind a faster ladder-MM that is
   MORE aggressive precisely in deep/active books, not a thin-book artifact.
3. **The only real, stable signal (wide opening spread → toxic) is already captured** by the live
   1c-tight pair-gate and covers just 7% of windows — no incremental lever.
4. **Strand clusters mildly in time** (lag-1 r=0.18; cooloff helps) but not enough: it lowers strand
   from 18.5%→15.2%, nowhere near 4.4%. A cooloff is a marginal risk-reducer, not a profit-maker.
5. **Net-of-volume:** even ignoring stability, the only sub-15% buckets retain <50% of windows while
   STILL being negative-EV — you lose half the (already capacity-capped) volume and still lose money.

**Conclusion:** This is the honest "no regime helps" result the brief flagged as valid and
important. The box cannot be rescued by *when* you trade it. Its viability rests **entirely** on the
queue-timing / completion fix driving the live strand rate below ~5% (BOX_COMPLETION_EXEC /
BOX_DISPOSAL_EV). Until a live re-test shows strand <5%, do NOT run the box, and do NOT expect any
time/regime gate to substitute for the completion fix. **No deployable config; regime-invariant.**

*Reproduce: `python box_regime.py`. Tape N=162 windows (gha_data 06-11..06-13), live strand-truth
4 winrecs (live_state 06-13/14). Costs: clean +0.69c, tox −15c, break-even 4.4%. Net(live) is the
load-bearing column; net(fill) is the optimistic q0=0 backtest and is SCREEN-only.*
