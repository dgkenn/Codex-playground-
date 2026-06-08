# 10 new data-backed tweaks (round 2) — from backtesting everything

Grounded in the live shadow backtest (n=66 windows; columns net/win, Δvs base, paired t, GROSS/win) +
the wallet decomposition. **Honest correction:** several round-1/wallet-derived ideas FAILED in backtest
(below); these 10 are what the data actually supports.

## What the backtest proved
```
variant       net/win  paired t  GROSS/win  fills/win
micro_gate     +5.10     +6.67     +0.66       173     <- THE edge (gross-positive, highly significant)
micro_marg     +3.67     +4.42     +0.48       126
tox_gate       +3.60     +5.32     +0.45       124
cap25          +1.86               -1.87       168
baseline       -0.23               -4.64       201
gross_max      +0.48               -1.85        92     <- over-gated
graded         -2.23     +2.58     -4.73        86     <- over-gated, gross still negative
band_p         -8.71               -13.77      168     <- mid-band p~0.5 is the MOST toxic zone
hedged_big    -47.8               -58.7         --     <- carrying inventory = disaster
lag_taker      -8.66               -2.75        --     <- TAKER overlay: no edge (loses to fee)
```
Top bots' fills: **100% passive, 0% taker** (decomposition) — they never cross the spread.

## The 10 tweaks (priority order)
1. **Make `micro_gate` the core, alone.** +5.10/win, t=6.67, gross-positive — the only consistently
   gross-positive single gate. Pull the side whose microprice says the book is tipping; nothing else
   beats it. *(deploy as default in live_trader)*
2. **Use ONE gate, not a union.** `graded`/`gross_max` (micro∪spot∪deplete∪band) cut fills 201→86–92 and
   net to ≤+0.5 — over-gating sheds rebate faster than it cuts toxicity. Retire the union variants.
3. **Gate only the worst ~14% of fills.** micro_gate keeps 173/201 fills for +5.3 net; micro_marg cuts to
   126 for less. Tune the micro threshold to the fill-count sweet spot ~170–185 (max rebate while
   gross≥0). *(new variant: `micro_soft` = micro_gate with a smaller margin)*
4. **Gate HARDER near p≈0.5, quote freely at the extremes.** `band_p` (quote only 0.2–0.8) had gross
   **−13.77** ≪ baseline −4.64 → the mid-band is where adverse selection + peak fee concentrate. Tweak:
   make the micro-margin **scale with proximity to 0.5** (strict at mid, loose at extremes). *(new variant
   `micro_ufat`: margin = MICRO_MARGIN·4·p·(1−p))*
5. **Keep inventory tiny (cap ≤25).** `hedged_big` (cap 200) = −47.8/win; resolution-variance dominates.
   A real perp hedge is the ONLY way to size up (paper can't test it; `hedge_value.py` showed it's
   variance, not mean) — until then, stay small.
6. **No taker / aggressive component.** `lag_taker` −8.66 and the top bots take 0%. Pure passive maker.
7. **Maximize rebate volume via breadth.** fills/win is the P&L driver (the rebate is the bulk; per-fill
   gross is ~0). Run all 8 markets × 4 assets (`multi_market.py`) to multiply rebate at the same per-fill
   edge — the single biggest lever (corr(pnl,#markets)=+0.59 from the wallet study).
8. **Complete-set-discount as a SIZING boost, not a gate.** Standalone box/`band` variants underperformed;
   instead, when `bid_up+bid_dn < 1`, *increase* size on the micro_gate-approved fills (capture the set
   discount on top of the rebate) rather than restricting to it. *(integrate into `_size`)*
9. **Hold balanced sets to resolution + redeem (no merge).** The top bots' mechanic — a balanced Up+Down
   set settles to $1 with no merge gas; avoids flatten churn/fees. Cuts cost vs actively flattening.
10. **Ladder depth ~14 ticks, tapered (dense at touch).** Matches the copyable bots' fill distribution
    (median 2tk, p95 14tk) — deeper than baseline's narrow quote to catch the passive fills that
    currently miss, but NOT a uniform wide band (which failed). Most size at touch, thin deep tail.

## Meta-finding
The winning recipe is **simple**: `micro_gate` + tiny inventory + max breadth + set-discount sizing +
hold-to-resolution. Complexity (unions, price-bands, big inventory, taking) all *lost* in backtest. This
matches the top wallet `0x674887d1` (two-sided, tiny-clip, gross≈0+rebate, breadth) — the cleanest,
most profitable, and now backtest-confirmed direction for our bot.
