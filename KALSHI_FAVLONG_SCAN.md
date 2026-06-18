# Favorite-longshot value edge on Kalshi SOFT (non-crypto) settled markets — first empirical pass

**Date:** 2026-06-18 · **Harness:** `kalshi_favlong_scan.py` (public API, no auth) · **Branch:** vw7ut5

## Why this test
After the 15m-crypto space was fully closed (box=queue-dead, directional=efficient, ensemble=worse-than-mid,
Poly lead-lag=sub-cost — see `PMKT_LEADLAG.md` §5), the only remaining shape for a tradable Kalshi stack is a
**value / risk-premium** edge that is queue- and latency-independent (takeable). The strongest such candidate
is the **favorite-longshot bias** (`KALSHI_GOLD_CANDIDATES.md` #1): academically documented (GWU 300k contracts,
Becker, weather calibration). It was tested here only on **crypto 15m** (dead — `ETH_FAVLONG`, `XRP_15M`: bias
absent / wrong-signed / < spread), which is the *most efficient* corner. It had **never** been tested on the
**soft non-crypto categories** (entertainment / politics / world / weather) where the academic evidence lives.

## What the scan does
Pull settled binary markets across 8 categories; for each, take the pre-settlement two-sided quote and the
yes/no `result`; bin by mid; compute realized win-rate vs price and **taker EV at the ask** net of the Kalshi
quadratic fee `0.07·p(1−p)`. Buy-YES at ask for favorites, buy-NO at `1−bid` for overpriced longshots.

## Result: NO demonstrated edge — naive signal was a data artifact
**Pass 1 (naive, any price field):** looked spectacular — "+16.6¢ buy-NO at mid 0.50" on 2,533 markets. **It was
an artifact.** 2,126 of those clustered at *exactly* implied=0.500 (a stale/default quote, not a real price), and
the dominant categories (Weather 1,052, Sports 1,014) are **multi-outcome bucket markets** whose legs resolve NO
by construction. Garbage in.

**Pass 2 (require a real, liquid two-sided quote: `0<bid<ask<1`, spread ≤15¢, exclude multi-leg collections):**
- Sample collapses **2,533 → 131** markets. The "edge" vanishes with the artifact.
- **No price band reaches n≥25** → no calibration curve. The settled-market snapshot simply does not retain a
  reliable pre-settlement tradable quote for most markets.
- **Median spread 3.0¢ (p90 9.0¢)** on the liquid subset — wide enough to eat any plausible favorite-longshot bias.
- Only Sports has n≥30 (n=81, bias +8.3pp), which **contradicts** the robust 706-game Kalshi sports calibration
  (`SHARP_VS_KALSHI.md`: ±0.3¢ efficient) → treated as small-sample/labeling noise, not edge.

## Why the prior was poor anyway (the part I under-weighted at first)
The GWU evidence says **makers earn positive, *takers lose ~20% pre-fee*.** So favorite-longshot is fundamentally
a **maker** (queue-dependent) edge — the exact thing we cannot win on cloud/GHA latency — and the taker version
(the only queue-independent one) is academically *expected to lose*. On the liquid markets the spread (~3¢) ≥ any
bias; on the soft illiquid markets a maker *could* sit alone in the queue, but spreads are 3–9¢+, fills are rare
and adverse, and capacity is tiny.

## Verdict
**This first rigorous pass does NOT establish a tradable favorite-longshot stack on Kalshi soft markets**, and the
prior is poor (taker-negative academically; spread ≥ bias; maker-version queue-bound). A *definitive* test would
need **per-market candlestick/trade history** (real traded prices at a decision time on genuinely binary, liquid
markets) rather than settled-market snapshots — a substantially bigger fetch. Given the poor prior, that build is
only worth it if the candlestick data shows the calibration holds on a clean, liquid, single-outcome subset.

**Where this leaves the goal:** every Kalshi edge examined — microstructure (queue-bound) and value (sub-spread /
taker-negative) — hits the same wall. The honest open question is no longer "which 15m tweak/variant" but whether
*any* Kalshi market class clears spread+fee for a slow, small, taker-or-uncontested-maker account. Candlestick-based
favorite calibration on liquid single-outcome markets is the one remaining test that could flip it; nothing else
in the mapped space has a positive prior.
