# edge_dumbflow.md — Fading systematically-WRONG (DumbFlow) taker flow on Kalshi 15m crypto binaries

**Node:** DUMBFLOW (2026-07-15). **Status: NULL** — none of the five DumbFlow fade signatures clears
its round-trip cost out-of-sample. The dumb subsets *are* mostly individually −EV (they lose money),
which confirms the DumbFlow premise at the flow level, but **fading them is not tradeable**: the
window-aggregated net direction of the dumb flow carries almost no directional gross edge, and where a
real per-trade wrongness exists it is smaller than the spread+fee you must pay to fade it. One
signature (late-window "chasers") turned out to be the *opposite* of dumb — informed/correct — so
fading it loses badly (OOS t = **−4.44**); the only positive thing found is *following* that flow,
which is FAVLONG-adjacent and not an established new edge. PROPOSE-ONLY research; no live change.

Complements the confirmed heavy-taker-flow DumbFlow (edge_informed_flow.md: heavy aggressive flow is
~63% wrong) that a separate agent is fading — this note tests OTHER dumb signatures and finds no
additional fadeable edge.

## Data & method
- **Sample:** 18 days spanning the train/test wall (heavier than the ≥12-day floor; full 35-day tape
  was too large to hold at once — 18.9 M trade prints in the sampled subset).
  Train (≤2026-06-30, 10 days): 06-11,13,15,18,20,22,24,26,28,30. Test (>2026-06-30, 8 days):
  07-01,03,05,07,09,11,13,15. Assets: btc/eth/sol (XRP excluded, per FAVLONG).
- **Windows after clean-label:** 4298 (train 2510 / test 1788); day-clustering unit = (asset,day),
  so OOS has up to 24 clusters (8 days × 3 assets).
- **Label:** realized settlement = market's own terminal mid > 0.5 (identical clean-label convention
  to `favlongshot_edge.py`; windows where the spot-move proxy disagrees are dropped).
- **Trade tape fields:** `side` (BUY/SELL = taker aggressor), `p`, `sz`, `t`(→ seconds-into-window
  via `t−ws`), `ws`, `up`(=1). This archive slice has **no `tid`**, so prints were deduped by
  (t,side,p,sz).
- **Fade mechanic (executable, hold to settle):** for each window, aggregate the dumb subset into a
  signed net (BUY=+sz, SELL=−sz) up to a decision time T; if |net| ≥ threshold, take the OPPOSITE
  side at the executable tick price at T (buy@ask / sell@bid), hold to settlement, net the Kalshi fee
  `0.07·p·(1−p)`. **The fade pays the spread+fee too** — baked in by filling at ask/bid vs a 0/1
  settlement. `gross` uses the mid as the fill (no spread) to isolate directional edge; `cost` =
  gross − net = the spread+fee drag.
- **Discipline:** thresholds and T chosen on TRAIN (max train day-clustered t, with n≥80 & ≥6 clusters),
  then the fade is run **once** on TEST. Day-clustered t reported pooled and per-asset. **56 fade
  configs** were searched across the 5 signature families (plus the base-flow/session grid) — none is
  positive OOS.

## Economics (unambiguous): a signature counts only if the dumb subset's wrongness EXCEEDS the ~1c round-trip cost
Measured round-trip cost of a fade at the decision tick is ≈ **0.8–1.7c/contract** (spread crossed +
Kalshi fee). So a dumb subset must be wrong by MORE than ~1c *at the window-aggregated, executable
level* for the fade to net positive. None is.

## Per-signature results

| # | Signature (fade) | Dumb subset OOS: hit @ avg price → takerEV/ct | Fade OOS: gross / cost / **NET** | Fade OOS day-clust t (pooled) | FAVLONG corr | Verdict |
|---|---|---|---|---|---|---|
| 1 | COUNTER-SPOT (trade against last-45s spot move) | 0.399 @ 0.505 → **−0.021** (wrong) | +0.0014 / 0.0165 / **−0.0151** | **−1.67** | −0.13 | **NULL** |
| 2a | TAIL-HIGH (buy YES >0.85), fade=short | 0.939 @ 0.942 → −0.007 (~fair) | −0.0011 / 0.0068 / **−0.0080** | −1.01 | **+0.44** | **NULL** (FAVLONG turf) |
| 2b | TAIL-LOW lottery (buy YES <0.15), fade=short | 0.045 @ 0.057 → **−0.016** (wrong) | −0.0096 / 0.0089 / **−0.0185** | −1.89 | −0.70 | **NULL** |
| 3 | ROUND-LOT (sz∈{10,25,50,100,…,round-000}) | 0.491 @ 0.506 → **−0.013** (wrong) | +0.0024 / 0.0102 / **−0.0078** | −1.58 | +0.02 | **NULL** |
| 4 | LATE-CHASE (t>600 in direction of prior move) | 0.858 @ 0.515 → **+0.027** (RIGHT) | −0.0181 / 0.0083 / **−0.0265** | **−4.44** | +0.23 | **NULL — flow is informed, not dumb** |

(All figures OOS/test unless noted; mean $ per contract.)

### 1. Counter-spot — NULL
Trades taking the side opposite the last-45s spot move are genuinely −EV as individual prints
(takerEV −0.021, hit 0.40). But the **window-net counter-spot direction has ~zero gross edge**
(gross +0.0014). Per-trade wrongness ≠ a fadeable window-level directional bias; after ~1.6c cost the
fade nets −0.015 (t −1.67). Train picked the early T=450 config, which inverts OOS. Low FAVLONG corr
(−0.13) but moot — no edge.

### 2a. Tail-high (overpay near-certainty) — NULL & collinear
Buys of YES at >0.85 hit 94% at an avg price of 0.94 — they are essentially **fairly priced**, not
dumb (takerEV ≈ 0/−0.007). Fading them = shorting favorites, which is FAVLONG's own territory
(**corr +0.44**) and loses net −0.008. Not an independent signal.

### 2b. Tail-low (lottery tickets) — NULL
The clearest per-trade dumbness: cheap-YES buyers pay 5.7c for a 4.5%-likely outcome (takerEV −0.016).
But fading = selling the cheap tail, which has **negative gross** (−0.0096): windows with heavy
lottery buying are, if anything, ones where YES modestly outperforms its mid by settle, and the rare
~0.95 tail losses swamp the pennies collected. Wrong ≠ harvestable. Strongly anti-correlated with
FAVLONG (−0.70). Net −0.0185.

### 3. Round-lot (retail fingerprint) — NULL
Round-size prints lose ~1.3c/ct — but that is just the spread an uninformed taker pays, with hit 0.49
and **no directional bias** (fade gross +0.0024 ≈ 0). Fading nets −0.008 (t −1.58). Essentially
orthogonal to FAVLONG (corr +0.02) but has no edge to contribute.

### 4. Late-window chasers — NULL to fade (the flow is INFORMED)
The operator's hypothesis was that late-window flow chasing the move is dumb. **It is the opposite.**
Late (t>600) flow aligned with the window's realized move settles correctly 86% of the time and is
**+EV even after the taker's own fee (takerEV +0.027)**. Near expiry in a 15m binary, the direction
spot has already moved is the direction it settles — this is the informed/correct side. **Fading it
loses hard: NET −0.0265, day-clustered t −4.44** (eth −4.53, sol −2.45, btc −1.51 OOS). Do not fade.

### 5. Session / time-of-day — NULL
Base substrate = fade net all-flow @720 (thr 250); the all-flow taker is mildly −EV (takerEV −0.014),
consistent with uninformed spread-paying. Segmenting by "retail-heavy" UTC hours (US evenings
22:00–03:00 + weekends) gives **no stable effect** and if anything the wrong sign: TRAIN non-retail
(+0.0054) beat retail (−0.0005); OOS retail +0.0069 (t −0.22) vs non-retail −0.0080. The base fade
itself is null here (TRAIN +0.0025/t 0.85, TEST −0.0007/t −0.56). No dumb-hours edge.

## Multiple testing
56 fade configurations across the 5 families (thresholds × decision-times), plus the base-flow and
session grids. **Zero are positive net OOS.** The single best TRAIN pick per family either inverts
sign OOS (counter-spot, round-lot) or was already negative in train (tail-high, late-chase).

## Orthogonality with FAVLONG
No signature both clears cost AND is low-correlation, because none clears cost. For the record: the
cost-clearing candidates would need |corr| low — round-lot is the most orthogonal (corr +0.02) but has
no edge; the two tail signatures are the most FAVLONG-collinear (+0.44 / −0.70). **No orthogonal-stack
candidate emerges from fading.**

## Honest byproduct (NOT a claimed edge): FOLLOWING late-window directional flow
Because signature 4's flow is informed, its mirror — *following* net late-window directional flow
(same side, entered @720, |net|≥100) — is positive OOS: NET **+0.0188/ct, day-clustered t +2.74**
(train t +2.06; gross +0.029, cost 0.010). **This is flagged, not crowned:** it is mechanically the
FAVLONG effect re-expressed through the tape (near-expiry terminal convergence / momentum), its
FAVLONG correlation is ≈ −0.23 (only *modestly* independent), and it directly contradicts the prior
INFORMED-FLOW late-follow test (edge_informed_flow.md Test 4, OOS t ≈ 0.70). It is almost certainly
FAVLONG-collinear rather than a new orthogonal edge and must NOT be stacked without a dedicated
follow-side forward test that controls for FAVLONG. Sensitivity: the follow signal weakens as entry
moves later (T=780 t +1.68; T=840 t +0.30), i.e. it lives in the same 720s terminal band as FAVLONG.

## Bottom line
**NULL.** Fading dumb flow does not add a tradeable edge on the 15m crypto binaries. The recurring
reason is economic and matches the informed-flow finding: the binary mid already prices direction, so
residual taker wrongness is dominated by uninformed *spread-paying* (counter-spot, round-lot, lottery)
that leaves no window-level directional bias to harvest — and you cannot monetize someone paying the
spread by *also* paying the spread. The one place aggressive flow carries real directional information
is the **late-window, move-aligned** flow, which is the informed/correct side (fading it is
strongly −EV); its followable content is FAVLONG's terminal-convergence mechanism, not a new edge.
Best OOS number produced by any *fade* is negative; the best *follow* number (late-chase, t +2.74) is
FAVLONG-adjacent and unestablished. Recommend: do not build a dumb-flow fade; the only DumbFlow worth
pursuing remains the separately-tracked heavy-flow fade.
