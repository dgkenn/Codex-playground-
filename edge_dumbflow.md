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
**[SUPERSEDED — see "LATE-FLOW-FOLLOW: FAVLONG-controlled" below: the +2.74 is a clean-label
selection artifact, not a real edge, and not FAVLONG-collinear either.]**

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

---

## LATE-FLOW-FOLLOW: FAVLONG-controlled (2026-07-15, follow-up)

**Question (operator):** should we bet WITH the late "chasers"? The fade-side null (signature 4) had a
mirror: *following* late move-aligned flow netted **+0.019/ct OOS, day-clustered t +2.74**. Is that a
REAL edge beyond FAVLONG, or FAVLONG re-expressed / an artifact? Same 18 days / 3 assets / clean-label
/ (asset,day) clustering; caches rebuilt to store FAVLONG fire+side per window and spec variants.

### 1. Reconciling +2.74 (mine) vs +0.70 (prior INFORMED-FLOW Test 4) — spec sensitivity
The two measured **different signals**. Replicating the prior spec ("largest late print sz≥1000, follow
its side") on my data reproduces the null: **OOS t = +0.72** (train −1.97). My +2.74 signal is *net
move-aligned late flow*, and its edge does **not** come from the flow at all:

| Follow spec (entry@720) | TRAIN t | TEST t | TEST net $/ct |
|---|---|---|---|
| move-aligned late net, t0=600, thr=100 (**headline**) | +2.06 | **+2.74** | +0.0188 |
| &nbsp;&nbsp;thr=50 / 250 | +1.78 / +2.20 | +2.73 / +2.62 | +0.019 / +0.017 |
| &nbsp;&nbsp;t0=500 / 660 | +2.38 / +1.38 | +1.75 / +3.23 | +0.012 / +0.023 |
| &nbsp;&nbsp;size-gate sz≥100 / sz≥1000 | +1.67 / +0.58 | +2.33 / +2.61 | +0.017 / +0.019 |
| **RAW late net (ignore move-alignment)**, thr=100 | **−3.41** | **−2.97** | **−0.0212** |
| largest late print sz≥1000 (prior Test 4 replic) | −1.97 | +0.72 | −0.007 |
| **pure momentum sign(spot@720−open), NO flow** | +1.57 | **+3.91** | +0.0233 |
| headline, entry@780 | +1.01 | +0.76 | +0.007 |

Reading: the signal is robust to threshold/t0/size-gate **but the "flow" is illusory** — following the
*raw* late taker-flow direction **loses** (t −2.97), and a signal using **no tape at all** (just the
sign of the spot move by t=720) is the **strongest** (t +3.91). So "late-flow-follow" is not a flow
edge; it is a **momentum / terminal-convergence** signal on the underlying, and it decays out of the
720s band (entry@780 → t +0.76). This resolves the contradiction: the prior agent measured a genuine
flow-print signal (null); I inadvertently measured spot momentum.

### 2. FAVLONG-controlled — the decisive test (net of Kalshi fee, OOS)
- **(a) FAVLONG-neutral windows** (where FAVLONG does not fire), clean-label: late-follow still nets
  **+0.0143/ct, t +2.05** (gross +0.0224, cost 0.0081) — *appears* to be a residual edge beyond FAVLONG.
- **(b) Incremental combo:** stacking a momentum-follow filler into FAVLONG-off windows lifts pooled OOS
  from FAVLONG-alone (n=952, mean +0.0309, **t +3.04**) to (n=1648, mean +0.0239, **t +4.37**) — *appears*
  additive.

But both (a) and (b) rely on **clean-label**, and for a pure direction signal that filter is
near-circular: it keeps only windows where sign(last_spot−open)==market outcome, and sign(spot@720−open)
≈ sign(spot@900−open). Measured directly: **P(sign(spot@720−open)==outcome) = 0.903 in clean-label
windows vs 0.870 in all windows** — the filter injects hit-rate into the signal, and a live trader
cannot apply it (the terminal label is unknown at t=720). Re-running **without clean-label** (market
label only — the deployable case):

| Signal (OOS, market label only) | TRAIN t | TEST t | TEST net | FAV-neutral residual |
|---|---|---|---|---|
| headline move-aligned late-follow | −0.13 | **+0.28** | +0.0031 | **−0.0187 (t −2.22)** |
| pure momentum sign@720 | **−1.48** | +1.37 | +0.0056 | −0.0128 (t −1.42) |

The edge **collapses**: headline OOS t +2.74 → **+0.28** (net ~0), pure momentum is **train-negative**,
and the "residual beyond FAVLONG" flips to **−2.22**. The +2.74 and the incremental-stack lift were
**clean-label selection artifacts**, not deployable edge.

### 3. Correlation reconciliation — same trade, or partly orthogonal?
On the 936 OOS windows where both fire: **corr(late-follow pl, FAVLONG pl) = −0.20**, and direction
agreement (late-follow side == FAVLONG side) = **0.19** — i.e. in shared windows they take
**opposite sides ~81% of the time**. So it is **not** FAVLONG re-expressed (my earlier "FAVLONG-collinear"
call was wrong): FAVLONG is a *near-expiry CONTRARIAN* trade (fade the dislocated favorite), while
late-follow is *momentum* (go with the move) — structurally opposite, firing largely in different
windows (hence the low, negative correlation). They share only the **mechanism** (book lags terminal
settlement near expiry), not the direction. The low correlation is real: it's a different, partly-
orthogonal signal — which is exactly why it needed its own falsification, and why it fails it.

### VERDICT: JUST-FAVLONG-adjacent ARTIFACT — do NOT stack, do NOT bet with the late chasers
The apparent late-flow-follow edge (OOS t +2.74, +1.9c/ct) is a **fragile, spec-dependent clean-label
selection artifact**: (i) the "flow" content is illusory — raw flow-follow loses (t −2.97) and pure
spot-momentum is stronger (t +3.91); (ii) removing the undeployable clean-label filter collapses it to
t +0.28 / net ~0 and turns the FAVLONG-neutral residual **negative** (t −2.22); (iii) it is not even
FAVLONG re-expressed — it's the opposite (momentum vs contrarian, 81% opposite side, corr −0.20) with
no deployable standalone edge. It is **not a REAL-COMPLEMENT**. Recommendation: do **not** bet with the
late chasers and do **not** stack this on FAVLONG. FAVLONG stands alone; the only DumbFlow worth
pursuing remains the separately-tracked heavy-flow fade.
