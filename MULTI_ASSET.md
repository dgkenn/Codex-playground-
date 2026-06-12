# Multi-asset box expansion (ETH/SOL/XRP 15m) — replay verdict: NO-GO on all three (2026-06-12)

Question: per-day profit scales by NUMBER of markets, not size (BTC is flow-capped ~N=16/window,
SCALE_GATE.md) — so can the box harvest replicate on KXETH15M / KXSOL15M / KXXRP15M?
Method: identical always-pair P0 replay (q0=0) on all four tapes, 60/40 IS/OOS (`multi_asset_study.py`).

## The side-by-side (OOS)
| | BTC | ETH | SOL | XRP |
|---|---|---|---|---|
| windows (IS+OOS) | 1163 | 1184 | 1141 | 171 |
| pair rate | **0.73** | 0.44 | 0.34 | 0.29 |
| strands/window | 0.27 | 0.56 | 0.66 | 0.71 |
| mean strand cost | −0.067 | −0.133 | −0.138 | −0.137 |
| net/window OOS | **+** (only positive asset) | − | − | − |

**BTC is the ONLY asset positive in both IS and OOS.** The alts strand 56–71% of windows (vs BTC 27%)
at ~2× the strand cost — the thin alt books mean the second leg almost never pairs. Adding all three
at baseline would roughly HALVE total $/day (alt drag −$2.7k/−$1.1k/−$1.2k implied OOS vs BTC-only).

## Gate transfer: gates cannot rescue the alts
- BTC: t32 (vpin≤0.40) and t35 (combo≤0.3656) both mildly improve net + DD (keep 88%/99%).
- ETH: gates cut maxDD a lot (43→17) but net stays NEGATIVE — fundamentally broken, not fixable by gating.
- SOL/XRP: the combo gate passes only ~1.5% of windows = a "never trade" gate; the XRP +0.187/0-strand
  cell is n≈1–2 windows = noise. **No gate produces positive alt EV at tradeable volume.**

## What IS portable (and feeds the guarded-opener work)
- **YES-side strand toxicity is UNIVERSAL, not BTC-specific**: YES strands settle worse and lose more
  often than NO strands on all four assets (BTC −0.115 vs −0.107; ETH −0.121 vs −0.075; SOL −0.095 vs
  −0.060; XRP −0.078 vs −0.052). Structural: informed BUYERS hurt us more than informed sellers.
  Strengthens the t02/t08/t36 asymmetric-quoting thesis.
- **Late fills (k≥12) are worse everywhere** (small on BTC, bigger on alts; only ~5% of fills).
- **BTC's best session is 16–24 UTC** (+0.048–0.049 c/win OOS); Asian hours neutral-to-negative.
  Candidate additive time filter — forward-measure, don't deploy on this alone.

## Caveats (read before re-using numbers)
1. The study's "implied $/day" column scales to a naive 2%-of-volume cap (BTC "+$9.9k/day") — that
   CONTRADICTS the established flow-bound capacity study (~$608/day at N=16, SCALE_GATE.md), which
   models what actually FILLS at the touch. Trust SCALE_GATE for capacity; use this study only for the
   CROSS-ASSET RELATIVE comparison (same method on all four → ranking is robust, levels are not).
2. Absolute BTC net/window here differs from earlier replay conventions (e.g. +72c/day in
   RISKFREE_PLAYS.md) — different fill-qualifier strictness. Again: ranking robust, levels not.
3. XRP has only 171 windows — its cells are the least reliable.
4. Fees: $0 maker CONFIRMED on BTC and ETH fills; SOL/XRP only INFERRED from identical series config —
   MUST-VERIFY with a 1-lot live fill before any SOL/XRP deployment (moot while NO-GO stands).

## Bottom line
Capacity growth does NOT come from adding alt 15m markets today — they are structurally negative-EV
(pair rates collapse in thin books). The scaling path remains: BTC flow growth (+69%/mo, SCALE_GATE),
queue priority (QUEUE_VALUE.md), and the guarded opener cutting strand losses. Re-test alts if their
volumes grow ~5–10× (rerun `multi_asset_study.py`).
