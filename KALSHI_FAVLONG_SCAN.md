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

---

## UPDATE 2 (2026-06-18) — DEFINITIVE candlestick test: also NULL. Candidate closed.

Ran the candlestick version (`kalshi_favlong_candle.py`): for each liquid, single-outcome settled binary, the
real **mid-life** two-sided quote (50% between open/close, spread ≤10¢) as a buy-and-hold entry; realized WR vs
mid; taker EV at the ask, net of the quadratic fee.

**Pooled (405 mid-life quotes; median spread 2.0¢, p90 8¢):** the script's naive auto-verdict flagged three
"+EV" bands (0.05–0.10, 0.10–0.15, 0.95–1.00) — but they are **small-n (25–48), non-monotone** (0.00–0.05 is
*negative* while 0.05–0.10 is positive; 0.90–0.95 negative while 0.95–1.00 positive) and each only **~1–1.4 SE**.
A genuine favorite-longshot curve is monotone; this is multiple-testing noise (~10 bands × 2 sides).

**Economics deep-dive (350 markets, per-band binomial z):** the only category with substance, and it fails the
honest test:
- **No band reaches |z|≥2** (strongest 0.5–0.6: +18.6pp but n=15, z=+1.44 = noise).
- **Non-monotone**, with the bias concentrated **mid-range (0.5–0.7)** and ~0 at the extremes — the *opposite*
  of a favorite-longshot shape.
- A marginal **overall** tilt exists — mean(win−mid) = **+4.5¢, z=+2.57** — but its flat, mid-concentrated shape
  is the signature of a **directional YES-skew / sampling-period artifact** (a settled-market window where data
  leaned YES), not a persistent, localizable edge. It is strongest exactly where the 2¢ spread + 1.75¢ fee bite
  hardest, can't be pinned to a tradable band, and won't survive OOS.

### FINAL VERDICT — favorite-longshot / value taker edge on Kalshi: CLOSED
No monotone, significant, cost-clearing favorite-longshot bias exists on Kalshi soft markets for a taker. The
maker version is queue-bound (the box's grave). This was the last positive-prior candidate. **Combined with the
15m closures (`PMKT_LEADLAG.md` §5) and the macro closure (`KALSHI_MACRO.md`), there is no tradable Kalshi stack
for a small-bankroll, cloud-latency, taker-or-uncontested-maker account.**

### What WOULD unlock a Kalshi stack (the honest preconditions)
1. **Win the maker queue** — co-location / sub-100ms infra to hold queue priority on liquid markets (the +7.7¢
   shadow box edge is real *if filled*). Not available on cloud/GHA; capital- and ops-heavy.
2. **A maker rebate large enough to pay for strands** — Kalshi's fee structure doesn't provide one on these books.
3. **A value bias > spread+fee that persists OOS** — none found across crypto (efficient), macro (efficient),
   sports (±0.3¢ calibrated), weather (calibrated), or the soft-market favorite-longshot curve (this doc).
4. **A genuinely new, soft, *un-arbitraged* market class** with recreational mispricing AND a tight enough book to
   take through — the soft markets that are mispriced are exactly the ones with 3–9¢ spreads (mutually exclusive).

Absent (1)–(4), the deployable answer for the user's actual objective remains the portfolio route
(`PROJECT_VERDICT.md` final answer), not a Kalshi trading stack.
