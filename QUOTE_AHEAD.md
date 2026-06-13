# Quote-ahead-of-the-ladder — VERDICT: NOT DEPLOYABLE standalone (tiny capacity); folds into t36

**Study:** `quote_ahead_study.py` (study 2 of the scaling batch). The thesis: when spot jumps, the
mechanical MM lags re-centering its ladder, so posting at the *new* fair touch first should win
front-of-queue at a price the MM hasn't repriced yet.

**Data:** `overnight_data/book_kalshi_btc15m_*.jsonl.gz` — full-depth book + spot, ~1.2s cadence,
sourced from the durable **gha-data** collector stream (the same rich `kalshi_collect.py` snapshots;
the old VM `overnight_data/` dir didn't survive a container restart). **34.2h span**, plus the
`trades_kalshi_btc15m.parquet` tape for settlement.

## Result
1. **Spot jumps ($50 / 3s):** 215 raw → **74 de-duped events** (≥30s apart). ~52/day raw.
2. **MM re-center lag is REAL:** p50 ≈ 1.8s, but **59% of jumps leave the ladder stale >12s** —
   the lag the thesis needs genuinely exists.
3. **But the touch rarely moves to a postable new level:** in **86% of jumps the touch stays at the
   same price** (the book is deep enough to absorb the jump), so there's nothing new to post ahead
   of. Only **14%** create a new-level opportunity → ~**8 actionable events/day**.
4. **P(front-of-queue) at the new level = 0.28** (level usually already has resting size).
5. **Edge (new-level events only, n=11):** P(fill 1–120s)=1.00, mean **+36c/fill**, median +53c,
   P(positive)=0.82, **std 52.75c** → implied ~**$2.78/day** at 1 contract. Real sign, but n=11 and
   the variance dwarfs the mean — not a deployable standalone strategy.
6. **Adverse selection:** post-jump P(continuation)≈54% at +30s (mild momentum). Quoting only the
   **jump-safe side** (spot up → quote NO bid; spot down → quote YES bid) removes the threatened leg;
   below 8bps both sides are safe — which is exactly the **t36** threshold we already gate on.

## Verdict
**NOT a standalone deploy:** ~8 events/day × n=11 fills × σ≫μ = no power and trivial capacity
(~$2.78/day). The valuable, robust finding is directional, not a new strategy: **the post-jump
quote should be one-sided to the safe side**, which the existing t36 spread gate already approximates.
**Action:** no new tester variant; record "quote-safe-side-after-jump" as confirmation of t36's
direction. Re-measure if/when book depth thins enough that jumps routinely move the touch (would
raise the 14% new-level rate and the per-day capacity).
