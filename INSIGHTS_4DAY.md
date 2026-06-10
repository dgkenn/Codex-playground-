# 10 insights from 4 days of prospective data (447 windows, 56k fills)

Drawn from the multi-asset shadow A/B (`gha-data`): **447 settled windows** across BTC/ETH/SOL/XRP and
**56,203 ungated fills** with realized markout. Each insight has the number and the bot action. Reproduce:
`python insights.py` (after `git checkout origin/gha-data -- gha_data/`).

Note on markout: `mo5` = short-horizon markout (adverse selection a maker controls; >0 = benign). `net/win`
= rebate-inclusive deployable P&L per window. Toxicity ≠ the directional outcome (see GATING.md).

---

### 1. `micro_gate` was NOT the best gate — three variants beat it ~24% (now acted on).
Full-sample net/win: **`micro_marg` +5.72 (t=10.0)**, `tox_gate` +5.63, `micro_ufat` +5.65, `mo_size` +5.67
vs **`micro_gate` +4.62 (t=9.1)**. All gross-positive. → **Done:** `live_trader --gate` now defaults to
**`ufat`** (+24% net at the same risk); `combo_lab` then found `ufat_band` beats even that (see the combo
section below).

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
1. **Swap the deployed gate** `micro` → **`ufat`** (Insights 1, 5, 9) — ✅ **DONE** (`live_trader --gate`
   default; still DRY-RUN until the pilot). `combo_lab` then found **`ufat_band`** beats it — running in A/B.
2. **Size by asset** — BTC ≫ ETH≈SOL > XRP (Insight 2); keep breadth for Sharpe (Insight 3). ⬜
3. **Avoid ≥2-tick spreads**; reconsider `--improve` (Insight 4). ⬜
4. **Stop over-chasing front-of-queue**; the deep/benign-sweep fills are the edge (Insight 6). ⬜
5. **Retire `flow_gate`/`late_gate`** (Insight 7); keep the gate micro-centric (Insight 8). ⬜
6. **Let `micro_cal` tune to the live rebate** (Insight 10) — the long-run gate. ⬜

The `ufat` default was adopted on this 4-day prospective evidence; `ufat_band`/`--mid-skip` and `micro_cal`
stay in the live A/B and become defaults only after live confirmation, per the project's standing discipline.

---

## Best COMBO (heavy backtest, `combo_lab.py`, IS + OOS)

Enumerated core gates × the orthogonal insight-filters, scored on per-(asset,ws) deployable net, split
IS (first 70%) / OOS (last 30%). **Winner that beats every single gate on BOTH halves:**

**`ufat + notmid`** = the p-adaptive micro gate AND skip the toxic 0.30–0.55 P(up) zone.
- IS net/win **+8.16** (vs `ufat` +3.48) · OOS **+16.46, t=+2.9** (vs `ufat` +6.91) · OOS `mo5` **+3.27**
  (positive → real toxicity-avoidance, not directional luck) · keeps ~54% of fills.
- `notmid` is the single most powerful add-on — it ~doubled OOS net on **every** core gate.

**What did NOT help (honest):**
- **`spread1`** (drop ≥2-tick spreads) *hurts* (`ufat+notmid` 16.5 → `+spread1` 13.9): wide-spread fills are
  toxic per-fill, but their rebate still nets positive, so dropping them sheds too much volume. Insight 4 is a
  *caution*, not a filter.
- **Portfolio stacking** (running several gates as separate books) doesn't raise Sharpe — the positive gates
  are 0.7–0.9 correlated. The real diversification is **breadth across assets** (net corr +0.10, Insight 3).

**Caveat:** OOS net > IS net is a favorable recent regime, not edge inflation — the stable signal is the
*ranking* (`ufat+notmid` tops both halves). Validate live before sizing up.

**Built:** `ufat_band` variant (live A/B) + `live_trader --gate ufat --mid-skip` (the deployable combo).

**Risk caveat (`METRICS.md`):** `ufat_band` wins on raw net/Profit-Factor/edge but has **5× the drawdown**
and **lower Calmar (3.9 vs `ufat` 8.8)** — `notmid` concentrates into directional high-prob tails, so part
of its extra edge is directional risk, not rebate. **`ufat` is the better risk-adjusted default.** The two
proposed rescues both FAILED: the delta-hedge was refuted by the path-based backtest (`hedge_backtest.py`,
`METRICS.md`), and under real inventory mechanics the band's net advantage **disappears entirely** — its
concentrated same-side tail fills are exactly what the skew limit blocks (`metrics_hypo.py` H2: replay
holdout +3.18 vs `ufat` +3.67). Judge variants by Calmar/Sortino, not net; the keep/drop numbers above
overstate the band because they ignore inventory constraints.
