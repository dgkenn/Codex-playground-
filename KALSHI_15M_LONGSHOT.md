# 15m BTC binary — favorite-longshot / under-reaction calibration (LEAD, not yet confirmed) 2026-06-21

Applied the soft-market WINNING framework (sell overpriced longshots) to the 15m BTC binary using the
now-richer tick+outcome data (912 windows, 611,992 ticks, 11 days, read from gha-data via
`kalshi_15m_longshot_calib.py`). Calibrating the UP-binary's QUOTED price vs its actual resolution:

| UP mid | windows | realUP | bias_pp | z | TAKER-NO EV |
|---|---|---|---|---|---|
| 0.05-0.08 | 478 | 0.037 | -2.7 | -2.4 | +2.15c |
| 0.08-0.12 | 492 | 0.075 | -2.4 | -1.8 | +1.48c |
| 0.12-0.16 | 500 | 0.103 | -3.7 | -2.4 | +2.31c |
| 0.16-0.20 | 520 | 0.139 | -4.1 | -2.4 | +2.52c |
| 0.20-0.35 | 653 | 0.241 | -3.7 | -2.1 | +1.83c |
| 0.35-0.50 | 815 | 0.390 | -3.7 | -2.1 | +1.45c |
| 0.50-0.65 | 820 | 0.565 | -0.7 | -0.4 | -1.55c |
| 0.88-0.95 | 489 | 0.937 | +2.0 | +1.6 | (fav underpriced) |

## The signal
Clean, symmetric: below 0.5 the UP side is OVERPRICED (realized resolves lower), above 0.5 UNDERPRICED.
The binary is **too sticky near 0.5 / under-reacts** and resolves MORE extreme than it prices. Selling the
overpriced UP-longshot (buy NO) is **+EV to settlement even as a TAKER** (crossing the spread), broad-based
across 470-820 distinct windows per band (not a few outlier days).

## Why it MATTERS if real (vs the soft-market harvest)
- **High capacity:** 15m BTC has orders of magnitude more volume than the soft markets (~$30-150/mo ceiling).
- **Taker-viable / queue-independent:** +EV crossing the spread => no resting/queue/fill war (the box's grave).
- **Hold to settlement:** no exit speed needed; the *sticky* overpricing gives time to sell into it.

## Why it is a LEAD, NOT a confirmed edge (the honest skepticism)
1. **Contradicts prior work** — `DIRECTIONAL.md` (15m efficient; "all taker tiers negative" after the 60s
   candle-timing fix) and `ETH_FAVLONG`/`XRP_15M` (favorite-longshot bias < spread+fee). Must reconcile:
   is BTC genuinely different, or does this re-introduce a measurement artifact?
2. **Marginal significance** — z ~ -2.4 per band on only ~11 days; could firm up or fade.
3. **Executability unproven** — +EV is on QUOTED bid prices. Whether you can actually sell UP at those bids
   WITH SIZE and WITHOUT adverse selection (the resting bid getting pulled, or you trading against info) is
   the KILLER test, exactly as in the maker study. Settlement-EV is necessary-not-sufficient.
4. **Under-reaction/momentum edges are fragile OOS.**

## NEXT (decisive): executability + adverse-selection
- Forward paper-track the 15m longshot-sell (analogous to `kalshi_longshot_paper.py`): record the quote we'd
  hit + outcome + actual subsequent fills, OOS, no look-ahead.
- Adverse-selection markout: after selling UP at the bid in the longshot band, does price move against us in
  the next seconds (stale-quote pickoff) or stay/continue down (real)?
- Reconcile vs DIRECTIONAL.md's timing-artifact: confirm price-vs-OUTCOME calibration (used here) is immune
  to the spot-vs-mid 60s artifact (it should be — outcome has no timing).
**Do NOT trade real money until executability passes.** But this is the strongest, highest-capacity 15m lead
the project has produced.

---

## RESOLVED 2026-06-21 (same day): the lead was a TIME-IN-BAND ARTIFACT. 15m stays EFFICIENT.

The pooled-ticks calibration above is BIASED by time-in-band selection: a window that ends DOWN *lingers*
at low UP prices (many ticks), while a window that ends UP passes *through* the low band quickly on its way
up. So at any low price, pooled ticks over-represent down-resolving windows -> a fake "UP-longshot overpriced"
and a fake favorable markout (price keeps falling because you're conditionally in a lingering-down window).

**Decisive control — ONE observation per window at a FIXED decision time (no time-in-band selection),
t=450/600/750s, ~900 windows:**
- The clean -3.7pp / z~-2.4-every-band pattern **DISAPPEARS**. Unbiased biases are **mixed-sign and mostly
  insignificant**: e.g. t=450s 0.22-0.30 +0.6pp (z+0.1), 0.40-0.50 **+5.6pp wrong sign**, 0.50-0.60 -9.2pp,
  0.60-0.70 -5.7pp -- no consistent favorite-longshot S-curve, ~all |z|<2 across 30 band x time cells (the
  one or two |z|~2 are multiple-testing noise with random signs).
- Executability stats (1c spread, 859-contract median bid, favorable markout) were REAL but are ALSO explained
  by the same selection -- they do not rescue a signal that the unbiased estimator says isn't there.

**VERDICT: NO tradable favorite-longshot edge in 15m BTC. The pooled "lead" was a selection artifact; the
efficient-corner finding (`DIRECTIONAL.md`, `ETH_FAVLONG`) STANDS** -- and is why this contradicted prior work.
Reconciliation complete: prior work was right. The richer data did not change the 15m conclusion. The one real
Kalshi edge remains the soft-market longshot-MAKER harvest (~$30-150/mo); 15m crypto is efficient at every
horizon >=1min. Lesson logged: calibrate intra-path binaries with ONE obs/window at a fixed decision time,
never pooled ticks.
