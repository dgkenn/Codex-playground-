# 10 insights from 4 days of prospective data (447 windows, 56k fills)

Drawn from the multi-asset shadow A/B (`gha-data`): **447 settled windows** across BTC/ETH/SOL/XRP and
**56,203 ungated fills** with realized markout. Each insight has the number and the bot action. Reproduce:
`python insights.py` (after `git checkout origin/gha-data -- gha_data/`).

Note on markout: `mo5` = short-horizon markout (adverse selection a maker controls; >0 = benign). `net/win`
= rebate-inclusive deployable P&L per window. Toxicity ≠ the directional outcome (see GATING.md).

---

### 1. The deployed `micro_gate` is NOT the best gate — three variants beat it ~24%.
Full-sample net/win: **`micro_marg` +5.72 (t=10.0)**, `tox_gate` +5.63, `micro_ufat` +5.65, `mo_size` +5.67
vs **`micro_gate` +4.62 (t=9.1)**. All gross-positive. → **Promote `micro_marg` or `micro_ufat`** to the
deployed `live_trader` gate (currently plain `micro`). +24% net at the same risk.

### 2. BTC is the money market; XRP barely pays.
`micro_ufat` net/win by asset: **BTC +12.96 (86% win)**, SOL +4.32, ETH +3.82, **XRP +1.47 (55% win)**.
→ **Weight capital/rungs toward BTC** (it's ~3× the others); keep XRP only for breadth diversification, not
size. Per-market sizing should scale with this, not be equal-weight.

### 3. Breadth is a *real* Sharpe win — maker P&L is nearly uncorrelated across assets.
Cross-asset **net** correlation = **+0.10** (vs the 0.80 *outcome* correlation we feared) → **~1.75× Sharpe
lift** running 4 markets. The rebate edge is microstructural, not directional, so it diversifies. → **Keep
all assets live** (breadth raises risk-adjusted return), but size by Insight 2.

### 4. Wider spreads are sharply toxic — stay in 1-tick books.
Mean `mo5`: **1-tick −0.0006, 2-tick −0.0040, 3+tick −0.0108** (18× worse). → **Gate hard / don't quote when
spread ≥ 2 ticks.** Directly tempers the `--improve` lever: price-improving *into* a wide spread lands you in
the most toxic regime — keep `--improve` off or tightly toxicity-gated, and prefer markets that sit at 1 tick.

### 5. Price-level toxicity is ASYMMETRIC — the high tail is the only profitable zone.
Mean `mo5` by P(up): tail<0.3 −0.0027, 0.3–0.45 **−0.0045**, ~0.5 −0.0037, 0.55–0.7 −0.0018, **tail>0.7
+0.0019** (only positive bucket). → Gate **hardest in 0.3–0.55**, quote freely in the **high tail**. This is
why `micro_ufat` (strict at p≈0.5, loose at tails) wins — and why the symmetric `band_p` lost. The asymmetry
itself is worth an A/B (could be a UP-token/asset artifact).

### 6. Queue priority is OVERRATED for toxicity — front-of-queue fills are the adverse ones.
Mean `mo5` by queue-ahead at fill: **front (~0) −0.0018**, 1–50 −0.0026, 50–200 **+0.0052**, **deep>200
+0.0095**. Informed flow picks off the front of the book; large *benign* sweeps fill the deep rungs. →
**Reconsider the queue-priority chase**: fighting to the front raises fill *rate* but worsens the *mix*. The
`--max-queue-ahead` lever is **backwards** (it skips the benign deep fills). The edge is *participating in
big sweeps*, not winning small races — so rest a fuller ladder and don't over-pay latency for front position.

### 7. Flow and time-to-close are weak toxicity signals — don't gate on them.
Adverse 30s flow>100 → `mo5` −0.0016 ≈ neutral −0.0020. Tau buckets are flat (−0.0012 to −0.0024). →
**Retire `flow_gate` and `late_gate`** as toxicity gates (they add complexity without edge), consistent with
`gate_lab` (flow/VPIN lost).

### 8. The microprice is the one dominant toxicity signal — everything else is noise on top.
In the `gate_lab` ridge model the microprice term dominates (weight −0.75); every gross-positive variant is a
micro-* variant. → **Keep micro at the core**; only its refinements (edge-margin, p-adaptive strictness) add
value. Resist multi-signal ensembles that dilute it (`gross_max`, `graded` underperform).

### 9. `micro_ufat` is the principled deployable gate — it matches the data.
It's strict at p≈0.5 and loose at the tails, exactly the toxicity shape in Insight 5, and lands top-3 on
prospective net (+5.65, t=9.4, n=379) while keeping high fill volume (~160/win). → **Deploy `micro_ufat`**
(or `micro_marg`) into `live_trader.model_filter` after it confirms on a few more days; it's the best
risk/volume balance found.

### 10. The rebate makes "more BENIGN volume" beat "stricter gating" on deployable P&L.
On pure adverse selection (`mo5`) stricter gates win (`gate_lab`: `micro_strict`/`micro_cal`), but on
**deployable resolution-net** the higher-volume `micro_ufat`/`mo_size`/`micro_marg` win — the rebate on each
extra benign fill exceeds its tiny adverse cost. → **Optimize for benign fill VOLUME, with the toxicity
threshold tied to the rebate.** This is exactly what **`micro_cal`** encodes (keep iff `pred_markout +
rebate > 0`); it should converge to the leader as it accrues live data and the **real rebate is confirmed**
(the pilot's #1 unknown). Re-fit with `gate_lab.py` once the live rebate is known.

---

## The shortlist of bot changes (ranked)
1. **Swap the deployed gate** `micro` → **`micro_ufat`** (Insights 1, 5, 9) — biggest, safest win.
2. **Size by asset** — BTC ≫ ETH≈SOL > XRP (Insight 2); keep breadth for Sharpe (Insight 3).
3. **Avoid ≥2-tick spreads**; reconsider `--improve` (Insight 4).
4. **Stop over-chasing front-of-queue**; the deep/benign-sweep fills are the edge (Insight 6).
5. **Retire `flow_gate`/`late_gate`** (Insight 7); keep the gate micro-centric (Insight 8).
6. **Let `micro_cal` tune to the live rebate** (Insight 10) — the long-run gate.

All are A/B-testable in the running multi-asset collector; promote to `live_trader` only after live
confirmation, per the project's standing discipline.
