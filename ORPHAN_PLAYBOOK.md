# Orphan playbook (t37) — what to do with an already-stranded leg

**Study:** `orphan_playbook_study.py` (study 1 of the scaling batch). Same-minute clean-box replay
on **825** common BTC windows (IS = first 60% / OOS = last 40%); for every STRAND (one leg fills,
the other doesn't) it scores three policies — **HOLD** to settlement, **SELL-now** (flatten at the
next-minute touch), **CHASE-with-lock-floor** (give ∈ {0,1,2,3}c) — bucketed by side × entry price.

## What the tape says
- **Strands are common and YES-skewed:** ~48% of windows strand ≥1 leg; **~57% of strands are YES**
  (bid-only) in both splits — the structural asymmetry from `LIVE_POSTMORTEM.md`. YES strands are
  the loss engine: held to settlement they bleed **−22c/strand OOS pooled** (worst buckets −37c).
- **YES strand, OOS pooled (N=125):** HOLD −21.95c · SELL **−12.52c** · best CHASE −16.40c.
- **NO strand, OOS pooled (N=96):** HOLD **−8.81c** · SELL −12.66c · CHASE −13.10c.
- So the OOS-winning policy is **side-asymmetric**: SELL the YES orphan, HOLD the NO orphan.
  NO orphans are mostly high-ask sells (0.6–1.0, ~62% of NO strands) that are favorable to ride —
  exiting them destroys edge, consistent with the "exits lose" invariant. YES orphans are
  adversely-selected fills that settle 0 ~86% of the time; the next touch sits above zero, so a
  prompt exit captures partial mean-reversion the hold gives back.

## Caveats that block an armed deploy (money-path judgment)
1. **The CHASE arm is degenerate — "SELL beats CHASE" is NOT established.** The model posts the
   completing leg at `a' = max(a0, b0 − give)`, and since `b0 < a0` always, `a' = a0` for every
   give in 0–3c. So the give sweep never lowered the completing price and never modeled the live
   trader's actual lever (`--chase-max-give` *relaxing the min-lock floor* to accept slightly-
   negative completions late in the window). The real completion-chase was not tested here.
2. **SELL-now is loss-MITIGATION, not profit** (−12.5c is still a loss). The real prize is **not
   stranding the YES leg at all** — i.e. **t36** (guarded opener), which this study re-confirms as
   the right primary lever: the worst outcome in every YES bucket is HOLD, and t36 removes it.
3. **Exit timing is coarse** — SELL uses the *next-minute* bid; the live trader can flatten in
   seconds, so the realized number could move either way.

## Verdict
- **Robust, reusable finding:** orphan handling should be **side-conditioned** — *sell YES orphans,
  hold NO orphans*. This is the deployable shape.
- **t37 = (YES-strand → SELL-now, NO-strand → HOLD):** register as a **SHADOW / forward-A/B
  candidate, NOT armed** for real money. Before arming, (a) fix the CHASE model to faithfully test
  lock-floor relaxation vs SELL, and (b) attribute against live per-fill telemetry (study 5).
- **Priority order:** arm **t36** first (prevents the YES strand — attacks the root cause); treat
  t37 as the secondary, post-strand mitigation, proven out in the forward test rather than on this
  coarse replay.

## Registering t37 (for when it clears the bar — do not arm now)
In `box_policy_ab.py`, the per-fill pnl already precomputes both outcomes on each fill dict:
`f["settle"]` (hold-to-settlement) and `f["exit"]` (= `bid[k+1] − b0`, the next-minute flatten).
A t37 variant is then a one-liner selecting per side:
`sum(f["exit"] if f["side"] == "bid" else f["settle"] for f in <strand-walk of F>)` —
i.e. exit-price for YES (bid-side) orphans, settle-price for NO (ask-side) orphans. Add it
alongside `t36` in the `TRIALS` dict as a shadow variant; arm only after the forward A/B clears the
pre-registered n≥100 / t-stat bar, exactly as `t02`/`t36` are gated.
