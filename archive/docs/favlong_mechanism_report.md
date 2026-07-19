# FAVLONG mechanism report — why the edge exists, will it persist, is it the operator's own box?

**Scope.** Offline analysis on the 35-day archive (2026-06-10 … 2026-07-14) cached in
`/tmp/favlong_cache/win_{btc,eth,sol}.pkl`. Uses the exact decision math in
`favlongshot_edge.py` (`NORM`, `KFEE`, `_causal_sigma`, `score`), instrumented per-trade
with book state. 4,352 taken trades pooled across btc/eth/sol (clean-label filter on,
`decision_t=720s`, `edge=0.05`, +Kalshi fee). Scripts in scratchpad `mech.py … mech4.py`.

**One-line read.** The edge is REAL and NOT decaying on the archive, but it is SMALL and
lives in **wide, dislocated books — NOT in the tight/deep two-sided quotes that are the
box-maker's footprint.** Persistence risk: **MEDIUM.** Box-maker cannibalization: **LOW.**

---

## 0. What the edge actually is (direction check)

| taken side | n | mean price | realized ITM | mean $/ct | winrate |
|---|--:|--:|--:|--:|--:|
| BUY up-contract cheap  | 2256 | 0.1655 | 0.1968 | **+0.0243** | 0.197 |
| SELL up-contract rich  | 2096 | 0.8293 | 0.8068 | **+0.0154** | 0.193 |
| cheap side actually taken | 4352 | 0.168 | 0.195 | — | — |

The mechanism is a modest **favorite–longshot underpricing of the cheap side**: contracts
taken at ~0.166 settle ~0.197 (underpriced ~3c gross, ~2.4c net of fee). Low winrate +
positive mean = many small losses, occasional payoff — variance-heavy, needs sizing.

> **Honesty flag:** I could NOT reproduce the docstring's "underdog priced ~0.09 settle ITM
> ~0.32." On the actually-taken cheap side, price 0.168 → settle 0.195; restricting to
> price ≤ 0.15, it's 0.051 → 0.055. The real dislocation is a few cents, not 0.09→0.32.
> The headline number appears overstated relative to what the clean-label taker captures.

---

## 1. DECAY — is per-day edge trending down?

Pooled per-day mean $/ct regressed on calendar-day index (n=35 days):

| regression | slope ($/ct per day) | t | r² |
|---|--:|--:|--:|
| pooled per-DAY | **+0.00066** | +1.10 | 0.035 |
| per-(asset,day), n=105 | +0.00066 | +1.36 | 0.018 |

Slope is **slightly POSITIVE and insignificant** — no decay. Splits confirm it:

| split | mean $/ct | n | day-clustered t | days |
|---|--:|--:|--:|--:|
| EARLY half (06-10…06-26) | +0.0179 | 1991 | +1.61 | 17 |
| LATE  half (06-27…07-14) | **+0.0218** | 2361 | +2.83 | 18 |
| TRAIN (≤06-30) | +0.0181 | 2574 | +2.01 | 21 |
| TEST  (>06-30) | **+0.0227** | 1778 | +2.45 | 14 |

The late/test half is if anything STRONGER than the early/train half. **On the archive there
is no decay signal.** (Caveat: 35 days is short; favorite-longshot is a known, arbitrageable
effect, so this is necessary-not-sufficient — the forward gate still governs.)

---

## 2. REGIME — where does the edge concentrate?

Days bucketed into terciles by realized daily vol (median per-window causal σ) and by trend
(spot efficiency ratio = |net move| / path length):

**By realized vol:**

| bucket | days | n | mean $/ct | d-clust t |
|---|--:|--:|--:|--:|
| LOW  vol | 11 | 1416 | +0.0075 | +0.80 |
| MID  vol | 11 | 1378 | **+0.0342** | **+4.07** |
| HIGH vol | 13 | 1558 | +0.0188 | +1.32 |

**By trend/chop (efficiency ratio):**

| bucket | days | n | mean $/ct | d-clust t |
|---|--:|--:|--:|--:|
| LOW ER (chop)  | 11 | 1300 | +0.0194 | +1.27 |
| MID ER         | 11 | 1401 | +0.0219 | +2.04 |
| HIGH ER (trend)| 13 | 1651 | +0.0189 | +1.97 |

The edge **concentrates in MID realized-vol days** (t=4.07) and is roughly flat across
trend/chop. It is weak-but-positive in LOW vol (t=0.80) and does NOT strengthen in HIGH vol.
So it is not a "high-vol chaos" artifact and not a "trend-only" artifact — it survives across
regimes but pays best when vol is moderate (spot moves enough to dislocate a committed book,
not so much that σ scaling already prices it).

---

## 3. BOOK STATE — tight/deep (maker) vs wide/thin (illiquidity)?

Per-trade edge vs book state at entry (n=4352):

| feature | corr r | t | reading |
|---|--:|--:|---|
| pl vs spread (ask−bid) | **+0.041** | **+2.67** | edge BIGGER when spread WIDER |
| pl vs traded-side depth | +0.025 | +1.63 | weakly bigger when deeper (ns) |
| pl vs log(bidq/askq) imbalance | −0.004 | −0.23 | no relationship |

**Tight vs wide is the decisive cut:**

| spread bucket | n | mean $/ct |
|---|--:|--:|
| spread ≤ 1c (pinned tight) | 2279 | **+0.0054** |
| spread > 1c (wide) | 2073 | **+0.0360** |

**2×2 (median spread 1c, median depth 90):**

| regime | n | mean $/ct | win |
|---|--:|--:|--:|
| **TIGHT & DEEP** (box-maker footprint) | 889 | **−0.0003** | 0.078 |
| TIGHT & THIN | 1330 | +0.0076 | 0.056 |
| WIDE & DEEP | 1287 | +0.0413 | 0.347 |
| WIDE & THIN (illiquidity) | 846 | +0.0285 | 0.305 |

This is the most important result for the mechanism question. **The edge is essentially ZERO
in the tight-and-deep regime and lives almost entirely where the spread is wide** (whether
deep or thin). A tight 1c two-sided book with large size is the signature of an automated
box-maker; in exactly that state there is nothing to exploit. The edge appears when the inside
market is WIDE — i.e. when the maker is NOT the tight inside quote (pulled / dislocated).
Net-of-crossing P&L already reflects paying the wider spread, so this is not an accounting
illusion. **Mechanism = a dislocated/wide book that is slow to reprice, not a sticky tight
maker quote.**

---

## 4. TERMINAL DYNAMICS — the lag that is the edge

Last 3 min, σ fixed at t≈600s; book confidence = |mid−0.5|·2, fair confidence = |fair−0.5|·2:

| t-bin (s) | n | book conf | fair conf | \|book−out\| | \|fair−out\| |
|---|--:|--:|--:|--:|--:|
| 600–660 | 365,760 | 0.699 | 0.565 | 0.206 | 0.259 |
| 660–720 | 367,313 | 0.757 | 0.619 | 0.168 | 0.224 |
| 720–780 | 367,621 | 0.821 | 0.680 | 0.126 | 0.185 |
| 780–840 | 330,721 | 0.881 | 0.735 | 0.081 | 0.147 |
| 840–870 |  95,247 | 0.923 | 0.730 | 0.052 | 0.146 |
| 870–900 |  36,549 | 0.959 | 0.787 | 0.027 | 0.116 |

The **book races to 0/1 faster and further than the model** (conf 0.70→0.96 vs 0.57→0.79).
Crucially, the book is also MORE accurate on average (|book−out| < |fair−out| throughout) —
so the book is not globally miscalibrated; it embeds information the naive σ-model lacks. The
edge is therefore **not** "the whole book is overconfident." It is a **selective lag**: in the
minority of windows where late spot moves against a book that has already committed toward
near-0/1, the book is slow to re-widen and re-price the cheap side. That selective lag is what
the model's `edge>0.05` filter isolates, and it coincides with the WIDE-book state in §3.

Underdog observations (fair<0.35), by time bin — book price is close to realized, model over-
estimates them; the exploitable gap is small and shrinks toward expiry:

| t-bin | mean book px | mean fair | realized ITM |
|---|--:|--:|--:|
| 600–660 | 0.101 | 0.154 | 0.075 |
| 720–780 | 0.059 | 0.108 | 0.037 |
| 870–900 | 0.025 | 0.071 | 0.010 |

---

## Verdicts

### Persistence risk: **MEDIUM**
Reasons it's not LOW: the edge is small (~2c/ct pooled, ~2.4c on the buy side), variance-heavy
(~20% winrate, ~62% of asset-days positive), and favorite–longshot is a *known, publishable,
arbitrageable* bias — precisely the kind that erodes once more takers crowd the last 3 minutes.
The reconstructed dislocation (≈3c) is far smaller than the docstring implies, leaving little
cushion against fees, latency, and impact at size.
Reasons it's not HIGH: across 35 archive days there is **no decay** (slope +0.0007/day, t=1.1;
late/test half ≥ early/train half), the effect replicates in all three assets, and it is a
structural convergence-lag in wide books rather than a fragile microstructure quirk. **The
forward gate (day-clustered t≥2 over ≥10 forward days) remains mandatory** — treat MEDIUM as
"trade only after the gate passes, and size for real variance."

### Box-maker cannibalization: **LOW**
The edge is ~**0** exactly in the TIGHT-&-DEEP regime that is the two-sided box-maker's
footprint (mean −0.0003 on 889 trades), and is concentrated in WIDE books (spread >1c: +3.6c
vs ≤1c: +0.5c). FAVLONG makes money when the inside market is wide/dislocated — i.e. when the
operator's tight maker quote is NOT the one being crossed. There is no evidence FAVLONG
systematically lifts/hits the operator's own tight box quotes; if anything the two strategies
are **complementary** (the maker earns spread in tight books, FAVLONG corrects mispricing in
wide books). Residual risk is only the incidental case where the operator is itself quoting a
wide market near expiry — worth a one-time check against the live maker's own quote log, but
the archive book-state evidence points to low conflict.

### Bottom line
Genuine, non-decaying, cross-asset-replicated favorite–longshot convergence-lag in wide
near-expiry books. Small and variance-heavy, headline underpricing overstated in the source
docstring, so keep it PROPOSE-ONLY behind the forward gate. It does not appear to feed on the
operator's own box quotes.
