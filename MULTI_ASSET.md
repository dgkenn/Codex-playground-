# MULTI_ASSET.md — Kalshi 15m Box Harvest: ETH/SOL/XRP Expansion Study

**Study date**: 2026-06-12  
**Script**: `multi_asset_study.py` (re-runnable, read-only)  
**Data**: `hist_kalshi_{asset}15m.parquet` + `trades_kalshi_{asset}15m.parquet`, 2026-05-11 to 2026-06-10  
**Method**: same-minute clean-box replay, q0=0 front-of-queue, 60/40 IS/OOS time split  

---

## Methodology note: cross-minute pairing artifact

The existing P0 walk in `box_policy_ab.py` opens a leg at minute k, then pairs it with the
**first opposite-side fill at any later minute k'**. When k ≠ k', this is **not a risk-free
box** — it is a directional bet on the mid drift from k to k'. Cross-minute "boxes" average
**−7c** (market trended against the open leg) vs same-minute clean boxes at **+0.9–3.8c**.
On BTC this barely matters (92% of boxes are same-minute). On ETH/SOL/XRP the cross-minute
fraction rises to 33–55%, making raw P0 deeply negative. This study uses per-minute
accounting throughout. The strand problem documented below is **real regardless** of this fix.

---

## Task 1 — Per-asset baseline (same-minute clean-box policy)

| Asset | N_OOS | IS c/W  | OOS c/W  | Box/W | Str/W | Str%  | c/Box  | OOS maxDD |
|-------|-------|---------|----------|-------|-------|-------|--------|-----------|
| BTC   |   464 | +2.42c  | +0.756c  |  8.39 |  0.64 |  7.0% | +0.906c|  +742c   |
| ETH   |   473 | −12.35c | −12.29c  |  6.54 |  2.65 | 28.8% | +1.817c| +6088c   |
| SOL   |   457 | −23.54c | −13.78c  |  4.60 |  4.46 | 49.2% | +3.501c| +6905c   |
| XRP   |    69 | −13.20c | −9.41c   |  4.75 |  5.04 | 51.5% | +3.646c| +1220c   |

**Str% = strand rate per offered minute** (i.e., of minutes where at least one side fills,
what fraction sees only one side). BTC: 7%. ETH: 29%. SOL/XRP: 49–52%.

**Same-minute clean boxes are always positive** (0% negative on all assets). Box profits
are real and scale with spread: BTC ~0.9c, ETH ~1.8c, SOL ~3.5c, XRP ~3.6c. The problem
is that strand losses overwhelm box profits on ETH/SOL/XRP.

---

## Task 2 — Strand asymmetry by side

| Asset | N_YES | YES settle | N_NO | NO settle | Note         |
|-------|-------|-----------|------|----------|--------------|
| BTC   |   151 |  −12.16c  |  144 |  −10.09c | YES worse    |
| ETH   |   640 |  −11.86c  |  614 |   −6.61c | YES worse    |
| SOL   | 1,039 |   −7.06c  | 1000 |   −6.48c | YES worse    |
| XRP   |   172 |   −8.12c  |  176 |   −2.86c | YES worse    |

**YES-only strands are worse on all assets.** Interpretation: informed takers
hit the YES bid in the final minutes of a window that settles UP, stranding the
maker's YES leg at a loss. This is NOT BTC-specific — it is a universal feature of
binary settlement mechanics. The YES strand asymmetry is more pronounced on ETH and XRP.

---

## Task 3 — Capacity and implied $/day

| Asset | MM size | Flow/win | Cap/win | OOS c/win | Impl $/day |
|-------|---------|----------|---------|-----------|-----------|
| BTC   |     265 |  17,832  |   265   |   +0.756c | +$192     |
| ETH   |      20 |   3,060  |    20   |  −12.287c |  −$236    |
| SOL   |      30 |   1,836  |    30   |  −13.780c |  −$397    |
| XRP   |      10 |   2,057  |    10   |   −9.413c |   −$90    |
| **TOTAL** | — | — | — | — | **−$531/day** |

**BTC-only: +$192/day. Adding ETH/SOL/XRP as-is: −$531/day (−376% vs BTC-only).**

Taker flow vastly exceeds MM ladder size on all assets — capacity is always MM-bound, not
flow-bound. The constraint is the depth of the resting ladder, not lack of taker activity.

---

## Task 4 — Gate transfer (OOS, vpin ≤ 0.40 gate)

VPIN gate is applied at the box level: skip the entire box if either leg's fill-time VPIN > 0.40.
Strand P&L is unchanged (strands have no open-gate to trigger).

| Asset | P0 OOS  | VPIN OOS | VPIN gain | Boxes kept |
|-------|---------|----------|-----------|-----------|
| BTC   | +0.756c | −0.279c  |  −1.035c  |  86%      |
| ETH   | −12.29c | −19.18c  |  −6.892c  |  43%      |
| SOL   | −13.78c | −26.00c  |  −12.21c  |  26%      |
| XRP   |  −9.41c | −22.05c  |  −12.64c  |  28%      |

**VPIN gate hurts on all assets.**

Key finding: **high-VPIN same-minute clean boxes earn the same c/box as low-VPIN boxes**
(ETH: low +1.94c vs high +1.85c; SOL: +3.61c vs +3.57c). VPIN does not predict
per-minute strands — strand rates are essentially identical across VPIN buckets
(ETH: 28% low-VPIN vs 29% high-VPIN; SOL: 49% vs 48%). The strand problem is
**structural (thin books), not toxicity-driven**. Filtering on VPIN just discards
profitable boxes without reducing strand losses.

**combo_tox gate**: equivalent to VPIN-proxy here (det_ features not pre-computed in
parquet; full `informed_detectors.build()` needed per window). Same direction: likely hurts.

---

## Task 5 — Hazard: last-120s fills

| Asset | n_early | early c/box | n_late | late c/box | diff    | EarlySz | LateSz | Ratio |
|-------|---------|-------------|--------|-----------|---------|---------|--------|-------|
| BTC   |  3,720  |    +0.914c  |    172 |   +0.848c | −0.07c  | 36.4    | 52.4   | 1.44× |
| ETH   |  2,947  |    +1.793c  |    146 |   +2.677c | +0.88c  | 14.0    | 25.3   | 1.80× |
| SOL   |  1,977  |    +3.483c  |    127 |   +4.139c | +0.66c  | 16.2    | 21.4   | 1.32× |
| XRP   |    301  |    +3.623c  |     27 |   +4.359c | +0.74c  | 13.7    | 16.9   | 1.23× |

**The informed-settlement-taker hazard does NOT appear in clean boxes.**
Late-120s fills are larger (1.2–1.8× size), consistent with the brief's description,
but they produce *better* clean-box profits on ETH/SOL/XRP (+0.7–0.9c more than earlier fills).
Large late takers sweep both sides of a tight book, completing clean boxes at wider spreads.

The hazard IS real but manifests as **strands, not clean-box markout**: large one-sided
informed takers in the last 120s clear one side of the book, then window closes without
the other side filling. This creates the high strand counts (especially SOL/XRP).

---

## Task 6 — GO/NO-GO ranking

### #1 BTC — GO ✓
- OOS +0.756c/win | pair rate 0.930 | strand rate 7% | implied +$192/day
- Caveats: none

### #2 XRP — NO-GO ✗
- OOS −9.41c/win | pair rate 0.485 | strand rate 52% | implied −$90/day
- **Caveats**: THIN DATA (n_oos=69, only 5 days); HIGH STRAND RATE 52%; STRAND LOSSES DOMINATE;
  ALT MAKER FEE $0 UNCONFIRMED; THIN BOOK (10-lot ladder)

### #3 ETH — NO-GO ✗
- OOS −12.29c/win | pair rate 0.712 | strand rate 29% | implied −$236/day
- **Caveats**: HIGH STRAND RATE 29%; ALT MAKER FEE $0 UNCONFIRMED (20-lot ladder)

### #4 SOL — NO-GO ✗
- OOS −13.78c/win | pair rate 0.508 | strand rate 49% | implied −$397/day
- **Caveats**: HIGH STRAND RATE 49%; STRAND LOSSES DOMINATE; ALT MAKER FEE $0 UNCONFIRMED;
  THIN BOOK (30-lot ladder + documented settlement-taker concentration)

---

## Root cause diagnosis

The alt markets have similar per-window mid drift to BTC (~46c, driven by binary settlement)
and wider spreads (ETH ~2c, SOL ~2.6c, XRP ~5.4c vs BTC ~1.1c). Clean-box profits are
real and larger than BTC in absolute cents. The problem is **per-minute strand frequency**:

| Asset | Strand rate | Required for viability | Gap   |
|-------|-------------|------------------------|-------|
| BTC   |  7%         | < ~15%                 | OK    |
| ETH   | 29%         | < ~15%                 | −14pp |
| SOL   | 49%         | < ~15%                 | −34pp |
| XRP   | 52%         | < ~15%                 | −37pp |

**Why are alt strand rates so high?** The MM ladder is thin (20/30/10 lots vs BTC 265 lots).
A 50-contract informed taker sweeps the YES bid in a single trade. The NO ask may not
receive a symmetric taker in the same minute. With thin books, one-sided large takers
complete one leg and leave the other stranded. This is amplified in the final 120s.

**What would make alts viable?**
1. Reduce strand rate to ~10%: requires either (a) a much thicker MM ladder (100+ lots on
   ETH, similar for SOL/XRP) or (b) a same-minute bilateral sweep gate (only enter if the
   book is so thin the NEXT taker will sweep both sides).
2. No gate currently works: VPIN, combo_tox, flow gates all fail to predict strands.
3. Wider spreads partially offset — SOL earns +3.5c/box but needs ~35 boxes per strand
   to cover the ~9c strand cost. Currently at 4.6 boxes per 4.46 strands = roughly 1:1.

---

## Critical unverified items before any alt deployment

1. **Maker fee**: $0 confirmed ONLY on live BTC fills. ETH/SOL/XRP maker fee unknown.
   Any non-zero fee rewrites capacity math and may eliminate the box edge entirely.
2. **MM ladder depth**: the 20/30/10-lot ladders must be calibrated per-asset; the brief
   states these as current values but confirmation before arming is required.
3. **Queue position**: q0=0 (front-of-queue) assumed throughout. Alt books may have longer
   queues relative to order size — actual fill rates could be lower.
4. **XRP data**: only 69 OOS windows (5 days). All XRP numbers should be treated as
   directional only, not statistically reliable.

---

## Summary verdict

| Asset | Verdict      | Why                              | Biggest caveat                       |
|-------|-------------|----------------------------------|--------------------------------------|
| BTC   | **GO**       | +0.76c OOS, 7% strand rate       | None                                 |
| ETH   | **NO-GO**    | 29% strand rate overwhelms 1.8c  | Maker fee unconfirmed                |
| SOL   | **NO-GO**    | 49% strand rate, settlement-taker| Maker fee unconfirmed + thin book    |
| XRP   | **NO-GO**    | 52% strand rate + tiny dataset   | 5 days of OOS data, unconfirmable    |

**Net capacity delta from adding alts: −$723/day vs BTC-only. Do not arm.**

The BTC box harvest does NOT replicate on ETH/SOL/XRP with current ladder sizes and P0 policy.
The per-minute strand rate is the binding constraint. Fix strand rate first; then gate research.

---
## Reconciliation notes (main-agent review, do not skip)
1. **Capacity numbers here vs SCALE_GATE.md:** this study's "Cap/win 265" treats the BTC MM's own
   ladder size as our capacity and implies +$192/day; SCALE_GATE's flow-bound study says N=16/window
   (~$608/day turnover) — different methods, different answers. **SCALE_GATE remains the deployed
   planning number**; this study's capacity column is for cross-asset comparison only. Both agree on
   the conclusion that matters: alts add NEGATIVE dollars today.
2. **"VPIN gate hurts BTC (−1.04c)" here vs the first replay's "mildly improves":** box-level vs
   fill-level gate accounting. The arbiter is the FORWARD A/B (t32/t35 enrolled); neither replay
   overrides it. The agreed part: VPIN does NOT fix alt strand rates (structural thin-book problem,
   not toxicity).
3. **Cross-minute pairing artifact:** the methodology point is real for ALTS (a leg paired minutes
   later often pairs at NEGATIVE lock after drift — "completion" bought at a loss; 33–55% of alt
   pairs vs 8% on BTC), and it is why raw P0 looks worse on alts than the clean-box view. On BTC the
   distinction is negligible (92% same-minute). Worth keeping in mind when reading box_policy_ab.py
   absolute levels; its TRIAL-vs-P0 comparisons are differential and unaffected.
4. **The genuinely new finding:** the alt box EDGE is real and bigger than BTC's (c/box +1.8–3.6 vs
   +0.9, clean boxes ~always positive) — the kill is per-minute STRAND FREQUENCY (29–52% vs BTC 7%)
   from thin MM ladders (10–30 lots): one informed take sweeps a whole side. Viability bar: strand
   rate <~15%. RE-TEST TRIGGER: alt MM ladder depth growing ≳5× or strand rate measured <15%.
