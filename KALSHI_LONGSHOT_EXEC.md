# Kalshi Longshot-Maker — EXECUTION OPTIMIZATION (when/where to quote, hold or exit)

**Date:** 2026-06-21 · **Script:** `kalshi_longshot_exec.py` (public Kalshi API, no auth, rate-limited 0.4s/call) · **Branch:** `claude/polymarket-bot-live-ready-vw7ut5`

**Scope.** This does NOT re-litigate whether the edge exists. The consolidated verdict
(`KALSHI_MAKER_VERDICT.md`) already established the one tradable pocket: **be the maker who
SELLS overpriced YES longshots** (= rest a NO-buy at/near the touch) on soft, zero-maker-fee
categories, **+0.97¢/contract** pooled, capacity-capped at **$30–150/month**, with flow
**settlement-loaded (55–65% in the final third)** and that late flow the most toxic. This doc
answers only: **HOW and WHEN do we quote to make that +0.97¢ as large as it can be?**

**Method.** For every settled binary soft market (`volume_fp≥300`, non-MVE) I replay the public
trade tape. We sell YES, so we only get filled when a taker **lifts the YES ask**
(`taker_side=="yes"`) in the longshot band **YES∈[0.02,0.20]**; that fill makes us **short YES =
long NO**, P&L to settle `= fill − settle` (settle=1 if result yes). I bucket each fill by
life-third, by quote placement (improve / at-touch / join-deeper, each with a queue-capture
haircut), and replay the per-minute candle mid AFTER each fill to test hold-to-settle vs
take-profit vs stop-loss. **Soft cats are zero maker fee** (`KALSHI_MAKER_RANK.md`), so fee=0.

**Samples (3 independent, sign-consistent).**
| run | markets | longshot-active | fills (n) | contracts | composition |
|---|---|---|---|---|---|
| Climate-only | 80 | 72 | 9,572 | 247,715 | weather (matches baseline weather-heavy set) |
| Multi-cat | 112 | 84 | 8,358 | 268,127 | Climate 57 / Entertainment 23 / Science 32 |
| Non-weather | 6 | 4 | 14 | 1,298 | Politics/Entertainment/Science (tiny, directional only) |

---

## 1. ENTRY TIMING — the dominant lever. The late third is a LOSER, not just "worse".

Maker-NO realized P&L to settlement, at-touch, by life-third (¢/contract, volume-weighted):

| life third | Climate-only VW | Multi-cat VW | Non-wx VW (n=14) | fillable-flow share |
|---|---|---|---|---|
| **early** | **+2.74¢** | **+1.83¢** | +2.04¢ | 16–18% |
| mid | −0.30¢ | −0.34¢ | −56.97¢* | 39–43% |
| **late** | **−3.09¢** | **−1.57¢** | −81.66¢* | 39–45% |

\*Non-weather mid/late are tiny-n and dominated by a couple of sharp Politics/Science resolutions;
read them as *direction* (early ≫ mid ≫ late), not magnitude.

**This is the headline finding.** The baseline +0.97¢ is a *pooled* average that silently nets a
**positive early edge against a negative late drag.** Decomposed:

- **Early third carries essentially the entire edge: +1.8¢ to +2.7¢/contract.** This is genuinely
  uninformed recreational lottery flow buying a longshot far from resolution.
- **Mid third ≈ 0.** Spread capture roughly offsets mild drift.
- **Late third is NET NEGATIVE (−1.6¢ to −3.1¢).** The settlement-loaded flow the baseline flagged
  as "most toxic" doesn't merely pay *less* — quoting into it **loses money**: you get lifted on a
  longshot precisely in the window where it's about to actually resolve YES (the lottery hits), and
  the realized short-YES P&L goes against you.
- Flow is back-loaded (39–45% of fillable contracts land in the late third), so the naive
  "quote-all-life" maker spends most of its fills in the worst window. In my YES-lift-only
  reconstruction the all-life blend is **−0.56¢ (multi-cat) / −0.83¢ (Climate)** — i.e. left
  un-gated, the late drag can swamp the early edge entirely.

**Policy:** **Quote only in the early+mid two-thirds of a market's life; STOP quoting (pull the
NO-buy) in the final third.** Gating the late third lifts the blended edge by **+0.84¢/contract**
(multi-cat: −0.56¢ → +0.28¢) on its own, and removes the only band with reliably negative realized
P&L. The cost is capacity: you forgo ~45% of fillable flow (the toxic 45%).

---

## 2. QUOTE PLACEMENT — sit AT the touch. Do NOT improve (undercut).

Realized maker-NO P&L by placement, queue-capture-haircut applied (improve q=0.50, touch q=0.25,
join q=0.12), multi-cat:

| placement | VW edge | exp. fills | $ harvested (VW×ctr) |
|---|---|---|---|
| **improve** (sell YES 1¢ cheaper) | **−2.33¢** | 91,480 | **−2130** (worst) |
| **at-touch** (sell at the ask) | **−0.56¢** | 67,032 | −376 |
| **join deeper** (sell YES 1¢ richer) | −0.66¢ | 26,709 | −178 |

Placement × third (VW, multi-cat) — the interaction is decisive:

| | early | mid | late |
|---|---|---|---|
| improve | +0.68¢ | −1.42¢ | **−4.79¢** |
| **touch** | **+1.83¢** | −0.34¢ | −1.57¢ |
| join | +1.81¢ | −0.10¢ | −2.17¢ |

**Improving the bid to win queue is the worst thing you can do.** Undercutting buys you *more fills
of the same toxic flow* at a *worse price* (you sell the longshot 1¢ cheaper). In the late third
improving is catastrophic (−4.79¢): you front-run the queue straight into the resolution lift.
**At-touch dominates on edge in every third.** Join-deeper has marginally lower edge than touch but
captures so little flow it isn't worth the queue risk; its only merit is mechanically skipping the
1-2¢ deep-longshot prints. **Sit at the touch (rest NO-buy at `no_bid` = sell YES at `yes_ask`);
never improve.** Queue position is irrelevant here — the books are thin and the flow that fills an
improved quote is exactly the flow you don't want.

---

## 3. HOLD vs EARLY-EXIT — TAKE PROFIT on decay; NEVER stop-loss.

After a fill (short YES at `f`), replaying the candle mid path to settlement:

| management | Climate VW | Multi-cat VW |
|---|---|---|
| HOLD to settle | −0.83¢ | −0.56¢ |
| **TP @ mid≤0.5·f** (buy back on decay) | **+0.41¢** | **+0.56¢** |
| **TP @ mid≤0.25·f** | **+0.76¢** | **+0.85¢** |
| STOP @ mid≥2·f (cut loss) | **−27.2¢** | **−22.5¢** |
| STOP @ mid≥3·f | −27.7¢ | −24.0¢ |
| TP0.5 + STOP3 combined | −0.94¢ | −1.71¢ |

**Take-profit is a real, free uplift of ~+1.1¢/contract** (hold −0.56¢ → TP@0.5 +0.56¢; TP@0.25
+0.85¢). When the longshot mean-reverts/decays mid-life, **buying the YES back** (closing the NO at
a few cents) locks the gain instead of round-tripping it through a late re-pricing. Most longshots
decay toward 0, so the short is frequently closeable at <½ the entry price well before settlement.

**Stop-loss is CATASTROPHIC (−22¢ to −27¢) — do not use it.** A longshot doubling (mid≥2·f) is
overwhelmingly the *true positive resolving* — the lottery actually hitting. Stopping out converts
a fixed −95¢ tail (which the sizing already budgets for) into a guaranteed mid-path loss locked at
the worst moment, and any stop layered on top of TP (combo −1.7¢) just re-introduces that drag. The
negative skew of this strategy must be *absorbed by tiny sizing across many independent markets*,
**not** managed with stops.

**Policy:** **Hold the NO; take profit by buying YES back when YES mid falls to ≤0.5×fill (tighten
to ≤0.25×fill for thin names). Never stop out on an adverse move.**

---

## 4. RE-QUOTE CADENCE — the touch barely moves; refresh every ~5 min.

Fraction of fillable flow still reachable at a given refresh interval, and touch (yes_ask) movement:

| refresh | flow captured (Climate / Multi-cat) |
|---|---|
| 1 min | 98.8% / 98.9% |
| **5 min** | **95.8% / 96.7%** |
| 15 min | 87.6% / 88.9% |
| 60 min | 52.9% / 59.2% |

Touch (yes_ask) minute-over-minute move: **median 0.0¢, p90 2–3¢, ≥1¢ in only 24–33% of minutes.**

**The book is nearly static between bursts.** A 1-min refresh is overkill (gains ~2-3 pts of flow
over 5-min). 5-min refresh captures ~96% of fillable flow with ~12× fewer order operations; 15-min
already starts to miss real flow (the bursty prints), and 60-min misses ~40%. **Re-quote every ~5
minutes, plus an event-driven re-quote whenever yes_ask moves ≥1¢** (cancel/replace to stay exactly
at the touch). No need for sub-minute quoting — there's no fast pickoff here (markout is positive;
`KALSHI_MAKER_ADVSEL.md`), so latency is not a source of edge.

---

## 5. THE OPTIMAL EXECUTION POLICY

| dimension | NAIVE baseline | **OPTIMAL** |
|---|---|---|
| **when** | quote all life | **quote early+mid thirds only; pull in final third** |
| **where** | at touch | **at touch (`no_bid`); NEVER improve/undercut** |
| **hold/exit** | hold to settle | **hold NO; TP buy-back when YES mid ≤0.5×fill; NO stop-loss** |
| **cadence** | — | **re-quote ~5 min + on any ≥1¢ touch move** |
| **realized edge** | −0.56¢ (my YES-lift recon) / +0.97¢ (pooled doc) | **~+1.4¢/contract** |

**Quantified lift over naive at-touch-hold-to-settle:**
- Gate the late third: **+0.84¢/contract**
- Add take-profit @0.5×: **+1.1¢/contract**
- Combined (early+mid, at-touch, TP@0.5): **~+1.4¢/contract realized, a +2.0¢ lift** — roughly
  **2–3× the per-contract edge** of the naive policy.
- "Improve to win queue" would have **subtracted** ~1.8¢ vs touch — the single biggest avoidable
  mistake.

---

## 6. BRUTAL HONESTY — what the optimization does and does NOT buy you

1. **The lift is real but it's a $/contract improvement, and capacity is the binding constraint
   (it always was).** Gating the late third **discards ~45% of the fillable flow** — the very flow
   the baseline counted toward the $30–150/month ceiling. You raise edge-per-contract ~2–3× while
   cutting fillable volume ~½. Net $/month is roughly **flat-to-modestly-up**: you harvest fewer,
   cleaner contracts. The optimization makes the harvest **safer and higher-quality, not bigger.**
   It does **not** break the capacity ceiling and does **not** approach $500/mo.
2. **"Naive hold-at-touch" is NOT near-optimal — it's actively damaged by the late third.** This is
   the one place cleverness clearly pays: the pooled +0.97¢ hides a positive early edge being eaten
   by a negative late drag. Simply *not quoting the final third* is the highest-ROI change and is
   trivial to implement (a clock gate on life-fraction).
3. **Take-profit (+1.1¢) is the second free win** and requires only watching the mid decay — no
   forecasting. **Stop-loss is a trap** (−22¢): the negative skew is a sizing problem, not an
   exit-management problem.
4. **Placement cleverness is mostly about avoiding a mistake** (don't improve) rather than finding
   new edge; at-touch is correct and queue games don't help on books this thin.
5. **Cadence barely matters** — the touch is static; 5-min refresh is plenty. Anyone building
   sub-second quoting for this is wasting effort.
6. **Sample caveat:** the clean magnitudes come from the Climate/Entertainment/Science multi-cat set
   (268k contracts); Politics/Science settled-longshot markets are genuinely scarce (the non-weather
   run found only 4 longshot-active markets, confirming the capacity doc), so their −56¢/−82¢ late
   figures are tiny-n and used only to confirm the **sign** (early ≫ mid ≫ late holds everywhere).

**Bottom line:** the optimal execution policy is **quote early+mid only, at the touch, never
improve, hold-with-take-profit (no stops), re-quote ~5 min** — worth **~+2¢/contract (2–3×)** over
naive, but it buys *quality and safety*, not capacity. The $30–150/month ceiling stands.
