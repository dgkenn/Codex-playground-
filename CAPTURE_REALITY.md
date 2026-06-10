# Can we capture 95% of the top MM bots' trades? The honest, artifact-free answer: NO (with a tight copy)

> _Historical — reverse-engineering phase (concluded: a ≥95% wallet-clone is not achievable, see CAPTURE_REALITY.md). Kept for provenance. Current state: **README.md**._

After chasing this hard and **catching five measurement artifacts** that each inflated the number, the
cleanest possible measurement says **a faithful tight follow-the-touch ladder captures ~37–86% of these
bots' fills, not 95%.** My earlier 95–100% claims were all artifacts. This documents the correction.

## The metric artifacts I caught (each inflated capture)
1. **Trivial tolerance** (`bid ≥ p−3¢`) → fake 100%.
2. **Time-band over-credit** (±8s min/max touch) → 40-tick swings counted as captured.
3. **Self-capture** (consensus path included the wallet's own trades) → trivial 100% offline.
4. **Consensus = mid, not touch** (offline) → ~half-spread closer than a real maker quote.
5. **Placement-window bug** (window `ts−30..ts+2` excluded the fill-time snapshot `touch_at` used at
   `ts..ts+5`; `win_max < inside_tk` impossible-consistency) → mislabelled near-touch fills as deep misses,
   AND the placement band (rangeW + 2·D) was simply wide.

## The clean measurement (live WS, fill-time touch, symmetric |inside_tk|≤D, no window)
Capture = fraction of the wallet's fills within D ticks of the **best bid/ask at fill time** (either
side — covers passive price-improvement inside the spread; taker fills are 0%):

| wallet | ≤5tk | ≤10tk |
|---|---|---|
| 0xdf7930e8 | 85% | 100% |
| 0x5e2b9261 | 86% | 96% |
| 0x62d728fb | 85% | 97% |
| 0x20d2309c | 73% | 88% |
| 0xed89b210 | 59% | 68% |
| 0x5d4aba8a | 37% | 58% |

**0/6 reach 95% at a tight 5-tick ladder; 3/6 at 10 ticks; none of the lower-volume ones.**

## What this means (honestly)
- **The "95% capture / 1:1 clone" goal is NOT achievable** from public fill data with a faithful,
  *profitable* tight ladder. The bots quote wider and/or ~15–40% of their fills land >5 ticks from the
  fill-time touch (price-improvement in wide spreads, fast-move fills, deeper rungs we can't attribute).
- **A ~10-tick ladder gets the top-volume MMs to ~96–100%** (df7930, 5e2b9261, 62d728fb), but not the
  rest, and a 10-tick-wide two-sided book is more capital/inventory-heavy (untested for profit; `band_p`,
  a different wide-quote test, lost money — so wider is not free).
- **We still don't have their private resting orders/cancels** — only fills — so a true clone is out of
  reach regardless of metric.

## The actually-useful takeaway (what survives all this)
The *learning* goal succeeded even though the *clone* goal didn't:
- These bots are **two-sided, tiny-clip, complete-set-discount, hold-to-resolution makers quoting near
  the touch** — and our **own backtest** independently found the profitable edge: **`micro_gate`
  (+5.10/win, t=6.67, gross-positive)**, with simplicity beating every complex variant.
- So the deployable answer for OUR bot is NOT "clone wallet X to 95%" (unachievable) but **run the
  `micro_gate` tight-MM core + breadth + rebate** — which is the same family the winners use and is
  backtest-positive. That's the real payoff.

## Bottom line
I won't claim 95% — the clean data says 37–86% at a tight ladder. The honest, evidence-backed conclusion
after removing every artifact: **we cannot capture 95% of every (or any low-volume) top-10% wallet with a
faithful profitable copy.** The value delivered is the *understood, backtested edge* (`micro_gate`), not a
high-fidelity clone.
