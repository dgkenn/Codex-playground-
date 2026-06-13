# Backtest screen: all trials vs P0 and vs live_current (deep 60-day tape)

**What:** `backtest_vs_live.py` runs the REAL `box_policy_ab.TRIALS` + `window_fills` on the deep
historical BTC tape (1,036 windows; IS 621 / OOS 415) to screen — *without waiting 3+ days* — which
trials are worth the forward wait. **SCREEN ONLY:** trials were mined from this tape, so in-sample t
is overfit (t02 was +2.79 IS → +0.09 forward). `tL_OOS` (vs live, out-of-sample) is the trustworthy
rank; nothing here is deploy-certified — the forward bar still decides.

## THE headline: the baseline choice changes everything (your methodology question, proven)
| trial | tP0_OOS (vs naive P0) | tL_OOS (vs LIVE = P0+t36) |
|---|---|---|
| t14_perp_hedge_unpaired | **+4.61** | **−0.04** |
| t32_vpin_open_gate | +4.92 | +1.94 |
| tc_mid_tailtrim | +4.36 | +1.98 |
| t_mid_window (k4,5) | +4.20 | +1.83 |
| tc_tailtrim_hedge | +1.72 | +0.11 |

`t14_perp_hedge_unpaired` looks like a **monster vs P0 (+4.61)** — and adds **nothing vs live (−0.04)**.
On this tape `t36` (which `live_current` includes) is strong and already captures the unpaired-handler
edge, so judging vs P0 **double-counts t36**. **Promoting t14/t11/t17/tc_tailtrim_hedge off their
vs-P0 numbers would have been a mistake** — exactly the trap the vs-live deploy gate now prevents.

## vs-live leaderboard (OOS, the deployment-relevant rank)
The only trials that beat *what we actually run* are **entry/selection gates**, not unpaired-handlers:
1. tc_mid_tailtrim +1.98 · 2. t32_vpin_open_gate +1.94 · 3. tc_mid_sellcheap +1.83 ·
4. **t_mid_window (k4,5) +1.83** · 5. tc_mid_hedge +1.82 · 6. t03_early_window +1.40.
Unpaired-handlers vs live: t14 −0.04, tc_tailtrim_hedge +0.11, t17 −1.19, t11 −1.24 — flat/negative.

**No trial clears t>3 vs live even in-sample.** Best is ~+2.0.

## Notes
- **OOS > IS for the leaders** (e.g. t_mid_window IS −2.18 → OOS +1.83): not classic overfit — it's
  **regime-dependent**; the recent OOS window favors mid-window/VPIN-gated entry. Treat as a regime
  signal, confirm forward.
- **Tape-specificity caveat:** on this 60-day tape t36 is strong, but on the live forward gha_data
  t36 is weak (t=+0.24) — so `live_current` is a *much* stronger baseline here than forward. The
  vs-live numbers are tape-conditioned; the forward A/B (vs the same live) governs deployment.

## Takeaway
- **Worth the forward wait:** the **k4,5 / mid-window entry family** (t_mid_window, tc_mid_*) and
  **t32_vpin_open_gate** — they add edge *on top of t36* (different decision: entry selection).
- **De-prioritize:** the unpaired-handlers (t14/t11/t17/tc_tailtrim_hedge) — on this tape they add
  little-to-nothing over t36; their forward vs-P0 crossings were largely t36's edge.
- **Nothing deploy-ready.** This shortens the search (what to watch / what to drop), it does not
  replace the forward t>3, n≥300 vs-live bar.
