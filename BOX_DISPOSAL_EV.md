# BOX_DISPOSAL_EV — strand disposal: HOLD to settlement vs CROSS to complete

**Question.** When one leg of the 15-min BTC maker-box fills and the other does not (a STRAND),
should we CROSS to complete the box (pay the half-spread now, lock a known outcome) or HOLD the
naked leg to settlement? And what is the optimal give cap (we just cut `--dispose-max-give`
0.15 → 0.05)?

**Verdict (one line): COMPLETE wins, decisively — strands are ~100% adversely selected (the
stranded leg settles worthless in 18/18 historical and 4/4 live cases), so HOLD's leg-EV is 0 and
any cross at a price < $1 is weakly +EV. Keep `--dispose-cross` ON. The give cap is a
catastrophe/churn bound, not an EV lever — its EV cost is sub-cent. Recommend raising it
0.05 → 0.10.**

---

## Data window, N, method

- **Historical tape** `hist_kalshi_btc15m.parquet` × `trades_kalshi_btc15m.parquet`: 323 windows
  with BOTH the per-minute book paths (bid/ask/mid) AND the taker tape, settlement `res_up`.
  Strands reconstructed with the repo-standard front-of-queue (q0=0) maker fill model
  (`box_policy_ab.window_fills`): a YES-buy fills when a taker SELLS through our bid; a NO-buy
  fills when a taker BUYS through our ask; a STRAND = a window where the first leg fills and the
  opposite leg NEVER fills before close. **N = 18 strands (5.6% strand rate).**
- **Live telemetry** (`origin/live-state`, winrec walk + Kalshi-API settle, days 2026-06-13/14):
  52 windows, **4 stranded** — used ONLY to sanity-check direction (N far too small to fit on).
- Script: `box_disposal_ev.py` (self-contained; reads the two parquets + walks live-state).

**Statistical-power caveat:** 18 historical + 4 live strands. The DIRECTIONAL result (stranded leg
is toxic) is unanimous (22/22 settle against the held leg) and matches the repo's adverse-selection
thesis (COMPLETION_MODEL.md: "we're filled on the side the market is about to run over"), so it is
believable despite small N. The *magnitude* of the per-cap EV differences (sub-cent) is within noise
— which is itself the finding: the give cap is not an EV lever.

---

## 1. Strand inventory — strands are ~100% TOXIC

Every reconstructed strand opened on the **losing** side:

| side stranded | settles ITM (HOLD pays $1) | settles OTM (HOLD pays $0) |
|---|---|---|
| YES strands (n=12) | 0 | 12 (all res_up = NO) |
| NO strands (n=6)   | 0 | 6 (all res_up = YES) |
| **stranded-leg ITM rate** | **0 / 18 = 0%** | |

Live: 4/4 stranded legs also settled out-of-the-money (ITM rate 0/4). The leg gets stranded
*because* the informed taker who filled us ran the market through our quote and never came back — so
the unpaired leg is the side the market left behind = the loser. **HOLD's expected leg value ≈ 0.**

Mean strand basis 0.20 (so HOLD loses the full ~20c sunk basis per strand on average; range
0.035–0.93).

## 2. HOLD vs COMPLETE realized EV, by give cap

Margin (the sunk basis cancels): per strand, `Δ = COMPLETE − HOLD = (1 − cross_px) − hold_val`.
With `hold_val = 0` (toxic), **`Δ = 1 − cross_px = basis − give`** (an exact identity, verified) —
completing recovers the basis MINUS what you pay to cross.

| give cap | # complete / 18 | mean Δ vs HOLD (c/strand) | per-window (×5.6% strand rate) |
|---|---|---|---|
| 0c (never cross) | 0 | +0.00 | +0.000 |
| 2c  | 2  | +0.39 | +0.022 |
| **5c (current)** | **4** | **+0.44** | **+0.024** |
| 10c | 12 | +0.70 | +0.039 |
| 15c | 12 | +0.70 | +0.039 |
| ∞ (always cross) | 18 | **+0.72** | +0.040 |

Uncapped COMPLETE beats HOLD by **+0.72 c/strand, 95% bootstrap CI [+0.26, +1.33]** (excludes 0).
**COMPLETE dominates HOLD at every cap; EV is monotone non-decreasing in the cap.** This *inverts*
the half-spread theory: in a fair market HOLD would win by the half-spread, but the toxicity
(hold-EV = 0, not = fair_yes) swamps the spread completely. The theory's "UNLESS adversely selected"
escape clause is exactly the live regime.

**Why the cap barely matters for EV:** recovery = `basis − give`. When `give ≥ basis` the leg was
bought cheap / the book ran far, so there is almost nothing left to recover (6/18 strands recover
≈0c regardless). When `give < basis` (12/18) completing recovers a few cents. So a *higher* cap only
ever adds tiny positive scraps; it never turns negative (you can't pay more than $1 for a winner, and
the winner is certain). The 5c→∞ EV gap is **+0.28 c/strand = +0.016 c/window** — noise-level.

## 3. Conditioning on moneyness & age

| moneyness (\|YES-equiv−0.5\|) | n | HOLD-EV | COMPLETE-EV (uncapped) | Δ | mean give |
|---|---|---|---|---|---|
| ATM (≤0.10) | 1 | 0c | 0c | +0.0c | 45c |
| MID (0.10–0.25) | 2 | 0c | 0c | +0.0c | 54c |
| TAIL (>0.25) | 15 | 0c | +0.86c | +0.86c | 13c |

| age (min unpaired → close) | n | Δ (complete−hold) | mean give |
|---|---|---|---|
| LATE (≤1m left) | 9 | +0.06c | 34c |
| MID (2–4m) | 9 | +1.38c | 4c |

- **There is NO regime where HOLD beats COMPLETE** — HOLD-EV is 0 everywhere (toxic leg). The only
  thing that varies is *how much* COMPLETE recovers.
- **The recoverable strands are TAIL legs caught EARLY (give still small).** A deep-OTM tail leg
  bought cheap, completed while the book is still near it, recovers its basis (Δ up to +1.4c).
- **Near-close / large-give strands recover ≈0** — by then the book has run away, the winner costs
  ~$1, recovery ≈ 0. Completing them is harmless (Δ ≈ +0.06c) but pointless for EV; their value is
  purely **risk control** (flatten the naked exposure off the book before settlement).
- ATM/MID strands are rare (3/18) because near-0.5 books are deep and pair both legs (matches the
  pair-gate/depth finding) — the strands that survive are the tail/thin-book ones.

State-dependent rule that the data implies: **complete whenever `give < basis` (recovery > 0);
beyond that, completing is for flatten-the-risk only, so a modest cap suffices.**

## 4. Recommended policy + flags

1. **`--dispose-cross` stays ON.** Holding a stranded leg = riding a ~100%-toxic position to a
   near-certain $0; completing it is weakly +EV in every cell. (Confirms the RCA-2026-06-13 fix that
   stopped strands settling at −21.76c.)
2. **Raise the give cap `--dispose-max-give 0.05 → 0.10.** EV is monotone in the cap; 10c captures
   12/18 vs 4/18 completions and +0.70 vs +0.44 c/strand. The 10c→∞ gain is negligible, so 10c is the
   point of diminishing returns AND keeps a sane catastrophe bound. **Do NOT go back to 0.15** (no
   extra EV: 10c and 15c complete the same 12 strands) and **do NOT drop to 0** (0 = never cross =
   the toxic-hold we are fixing).
3. **Keep the cap as a CHURN/CATASTROPHE bound, not an EV knob.** The historical EV says "cross at
   any price," but the live tape's pathological window (`n_dispose_cross = 47`, realized −82c) shows
   the real danger is *repeated partial re-crossing*, not the single-cross EV. The cap + the existing
   re-cross cooldown bound that tail. 10c lets a normal single cross through while capping the lock
   loss at 10c.

**Expected impact vs the current 5c config:** **+0.28 c/strand ≈ +0.016 c/window** (5c→10c), i.e.
essentially break-even on EV — the cap change is a wash, made for robustness (capture the cheap
TAIL-early recoveries, keep the catastrophe bound). The first-order P&L on strands is NOT in the
disposal cap; it is in the −20c sunk **basis** that HOLD-vs-COMPLETE both eat. **The real lever is
strand PREVENTION** (pair-gate depth filter, opening gate, streak guard), which attacks the −20c, not
the ±0.5c disposal margin.

### TL;DR flags
```
--dispose-cross                 # ON (keep)
--dispose-max-give 0.10         # raise from 0.05; EV-monotone, churn-bounded
```
Net: HOLD is never better than COMPLETE (toxic strands); the cap is a robustness bound worth ~0; the
money is in not stranding in the first place.
