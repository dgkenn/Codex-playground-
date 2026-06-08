# Learned algorithms of the top-10% MM bots — and what to steal

Goal: not a mirror bot but to **learn each top-10%-by-MM-score wallet's underlying algorithm**, validate
we've learned it (prospective trade-prediction via `copy_live_multi.py`), then mine the best for our bot.
Tools: `mm_score.py` (rank) → `strategy_model.py` (extract each algorithm from its tape) →
`strategy_compare.py` (what drives performance + winning recipe) → `copy_live_multi.py` (prospective 95%
capture validation, shared WS book over all 23). Models in `strategy_models.json`.

## The 23 are NOT one strategy — four archetypes
| archetype | who | signature |
|---|---|---|
| **Pure complete-set-discount MM** | `0x674887d1` (MMscore 3.51, **+12¢** set discount, 2-side **0.99**), `0x5c932f50` (learn 0.89), `0x2ee54a09` | quote both tokens, BUY the pair when bid_up+bid_dn<$1, hold balanced → redeem $1. The cleanest + top-scoring. |
| **Momentum maker** | `0x5e2b9261`, `0x75cc3b63` (set-sum −11 to −15¢, win 70–74%) | two-sided but leans into the moving side (buys the rising leg above fair) — a directional tilt on top of MM. |
| **Late-window touch scalper** | `0x a492e4da` (ladder p50=0, late=1.00) | quotes only at the touch, only in the last window phase. |
| **Directional** | `0x9cf7a224` (2-side 0.16) | mostly one-sided; not a true MM. |
Most others are **mixed two-sided MMs** between these poles.

## What drives the MM score (corr across the 23 learned models)
- **two-sidedness ↑** and **learnability ↑** (consistent fixed-clip rule) track higher score.
- The **top-6 recipe vs the rest**: two-side **0.86 vs 0.74**, set-discount **−2.1¢ vs −6.0¢** (top buy sets
  *cheaper*), learnability **0.69 vs 0.57**, tiny clips (~$4.5), ladder **dense at the touch (median ~9tk)
  with a thin tail to ~33tk**, de-emphasized late (~0.15), hold partly-balanced to resolution.
- Net: **the winners are the most consistent, two-sided, cheap-complete-set accumulators** — exactly the
  `0x20d2309cd9` mechanic (WALLET_20d2.md), and `0x674887d1` does it best at scale ($7.2k book).

## The synthesized winning algorithm (to improve OUR bot)
1. **Quote both tokens of all 8 active markets** (btc/eth/sol/xrp × 5m/15m), tiny ~$3–6 clips, high uptime.
2. **Prioritize the complete-set discount entry**: BUY both legs whenever `bid_up+bid_dn < $1` (target a
   few-cent discount); hold the **balanced set to resolution and redeem $1** (no merge gas). This is the
   highest-fidelity shared driver of the top cohort — more than classic bid-ask spread.
3. **Ladder shape**: dense at the touch (most volume within ~3–9 ticks) with a **thin deep tail (to
   ~14–30 ticks)** to catch overshoots — matches their measured fill distribution (their p95 ≈ 14–33tk).
4. **De-emphasize the last window phase** (winners' late-fraction ~0.15); **stay delta-neutral** (hold
   balanced, not directional) — the directional/momentum variants do NOT score better risk-adjusted.
5. **Breadth + consistency + rebate** are the moat (all 4 assets, fixed rule, 20% maker rebate on top).

These feed directly into `copy_bot.py` (set-discount entry + ladder + hold-to-resolution) and refine
MAKER_CHANGES.md #2 (mint/complete-set inventory) and #1/#5/#8 (breadth, uptime, rebate).

## "Learned to 95%" — how it's validated
`copy_live_multi.py` watches all 23 wallets against one shared WS book and reports, per wallet, the
prospective capture-vs-depth curve + the depth that hits 95% (= their measured ladder). A wallet's
algorithm is "learned" when our model reproduces ≥95% of its prospective fills at a sane ladder depth
(≤20tk). For `0x20d2309cd9` this is met at ~14tk (WALLET_20d2.md). The remaining wallets accumulate over
`copy-validate-multi.yml` (overnight, → gha-data); `copy_agg.py` pools the verdict. Honest caveat: a few
low-volume wallets are bursty/idle and need more cycles; momentum-tilted ones (5e2b/75cc) carry a
directional component that a pure-MM rule won't fully reproduce (that *is* the learned finding).

## Bottom line for our bot
The best, most-learnable, highest-scoring algorithm in the wild is a **consistent, two-sided,
tiny-clip, complete-set-discount accumulator across all crypto Up/Down markets, held to resolution +
rebate** — `0x674887d1`'s playbook. Our edge research (BOXARB/MAKEREDGE/MAKER_CHANGES) already pointed
here; this confirms it with 23 real bots' data and gives the exact parameters to set.
