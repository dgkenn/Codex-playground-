# Cross-Asset Lead-Lag Taker on Kalshi 15-min Crypto Binaries (BTC→ETH/SOL/XRP)

**Verdict: DEAD.** There is no viable cross-asset lead-lag taker edge. The hypothesis
— that less-liquid binaries (XRP/SOL/ETH) lag the common crypto move BTC's binary
already reflects, lettng a taker trade the laggard after BTC moves — fails on raw
tick data at every decision time, every threshold, and every asset. The laggard's
binary mid **does not follow** a strictly-lagged BTC binary move; if anything it mean-
reverts. Every net-of-cost taker config is negative (net −2c to −10c/contract,
window-clustered t = −2 to −4), and IS/OOS agree on the loss. This independently
re-confirms `XASSET_RELVAL.md` (parquet harness) directly on the git tick stream,
and extends it with far more SOL/XRP windows (~900 vs the parquet harness's ~470/443).

Harness: `kalshi_15m_xasset.py`. Data: raw ticks read straight from `origin/gha-data`
(`ticks_kalshi_{asset}15m_*.jsonl.gz`, `shadow_windows_*.jsonl`), no API, no parquet.

---

## Method (artifact-proof by construction)

For each target ∈ {ETH, SOL, XRP}, on the BTC∩target common 15-min windows (matched by
`ws` epoch), at fixed decision times t ∈ {300, 450, 600}s with horizon Δ = 60s:

- **Strictly-lagged predictor** (kills the 60s candle-timing artifact). BTC's UP-binary
  mid change and BTC spot return are measured over **[t−Δ, t]** — entirely *before* the
  response. The response is the target's binary-mid change over **[t, t+Δ]** and the
  target's `resolved_up`. The predictor is stale relative to everything it predicts.
- **One observation per window** at each t (kills the time-in-band / pooled-tick
  autocorrelation artifact that produced the prior false longshot signal). We never pool
  intra-window ticks; each window is a single independent draw.
- **Window-clustered / heteroskedasticity-robust inference.** Regression t-stats use HC0
  robust SEs on the one-obs-per-window panel; taker P&L CIs are window-clustered (each
  window's trade = one draw).
- All step-function lookups (`step_at`) take the last tick **at or before** t — no
  look-ahead.

Two regressions, each **incremental to the target's own current binary mid**:
- **Test A**: lagged BTC binary move + lagged BTC spot ret + own spot ret + own mid → target *future* binary move.
- **Test B**: lagged BTC binary move + lagged BTC spot ret + own mid → target `resolved_up`.

A real lag-follow edge requires a **positive, significant** BTC coefficient (laggard
catches up to BTC's prior move). Then we simulate **taking** the laggard: when lagged BTC
binary moved up, buy target YES at the ask; when down, buy NO at (1−bid); held to
settlement; net = payoff − entry − Kalshi taker fee (0.07·p·(1−p)) − the crossed spread
(already embedded in entry = ask / 1−bid). OOS = chronological 60/40 split by `ws`.

Coverage (resolved windows): BTC 908, ETH 910, SOL 909, XRP 907; common per pair ≈ 895–905
at each t. This is ~2× the SOL/XRP sample of the prior parquet study.

---

## Test A — does lagged BTC binary move predict the laggard's FUTURE binary move? NO.

Standardized BTC-binary-move coefficient on target future binary move (coef, robust SE, t),
incremental to own mid + own/btc spot ret:

| target | t=300s | t=450s | t=600s |
|--------|--------|--------|--------|
| ETH | −0.0021 (t=−0.39) | −0.0003 (t=−0.05) | **−0.0138 (t=−2.15)** |
| SOL | −0.0085 (t=−1.45) | −0.0068 (t=−1.05) | **−0.0145 (t=−2.52)** |
| XRP | −0.0041 (t=−0.83) | −0.0029 (t=−0.50) | −0.0043 (t=−0.71) |

Every coefficient is **≤ 0**. The two cells that clear |t|=2 (ETH/SOL at t=600) have the
**wrong sign**: a BTC up-move predicts the laggard binary ticking *down* next — mean-
reversion of micro-noise, the opposite of a tradeable lag. There is no "laggard catches up
to BTC" effect anywhere. The lagged BTC spot return is likewise ~0 (max t=1.56, ETH t=450).

## Test B — does lagged BTC binary move predict the laggard's resolved_up? NO.

Incremental to own mid, the standardized BTC-binary-move coefficient on `resolved_up`
never reaches |t|=2 (largest magnitudes: ETH t=300 t=−1.75, SOL t=300 t=−1.82 — again
*negative*). The laggard's own current binary mid already prices the common factor; BTC's
prior move adds nothing of the right sign. This matches the parquet harness's Δ-AUC ≈ 0.

---

## Taker EV — every configuration is negative net of cost (window-clustered)

Net cents/contract, held to settlement, net of fee + crossed spread; trades gated by
|standardized lagged BTC binary move| ≥ thr; `cap` = median available size on the taken
side (contracts).

| target | t | thr=0 | thr=0.5 | thr=1.0 | med cap |
|--------|------|-------|---------|---------|---------|
| ETH | 300 | −5.75 (t=−3.9) | −6.68 (t=−3.3) | −9.52 (t=−3.3) | ~50 |
| ETH | 600 | −2.60 (t=−2.3) | −1.46 (t=−0.7) | −0.01 (t=0.0) | ~60 |
| SOL | 300 | −6.09 (t=−4.2) | −7.21 (t=−3.6) | −9.63 (t=−3.3) | ~200 |
| SOL | 450 | −3.76 (t=−2.9) | −4.54 (t=−2.3) | −6.44 (t=−2.2) | ~280 |
| SOL | 600 | −3.45 (t=−3.1) | −4.20 (t=−2.1) | −2.62 (t=−1.0) | ~170 |
| XRP | 300 | −3.95 (t=−2.7) | −6.02 (t=−3.1) | −8.28 (t=−3.0) | ~370 |
| XRP | 450 | −3.02 (t=−2.3) | −3.65 (t=−1.8) | −3.09 (t=−1.1) | ~390 |
| XRP | 600 | −2.38 (t=−2.1) | −3.30 (t=−1.6) | −3.43 (t=−1.3) | ~220 |

(ETH t=450 ≈ −1.8c, t=−1.4 — also negative.) **No positive cell exists.** Tightening the
threshold (acting only on big BTC moves) makes it *worse*, not better — confirming the
signal's gross direction is wrong, not merely fee-eroded. The losses exceed the ~1–2c fee,
so this is not the "positive-but-for-fees" mirage of the prior ETH sleeve; it is a real
negative-alpha trade (you are buying the laggard side that BTC's move makes look cheap, but
the laggard already priced it, so you systematically overpay and the residual reverts).

## OOS time-split (chronological 60/40, ~1c BTC-binary-move gate)

| target | t | IS net (t) | OOS net (t) |
|--------|------|-----------|-------------|
| ETH | 300 | −7.36 (−3.8) | −4.61 (−1.9) |
| ETH | 600 | −2.81 (−1.7) | −3.35 (−1.7) |
| SOL | 300 | −7.41 (−3.8) | −4.99 (−2.1) |
| SOL | 600 | −4.47 (−2.7) | −3.09 (−1.6) |
| XRP | 300 | −4.44 (−2.3) | −2.84 (−1.2) |
| XRP | 600 | −4.72 (−2.7) | +0.53 (+0.3) |

IS and OOS **agree on the loss** in 8 of 9 cells. The lone OOS-positive cell (XRP t=600,
+0.5c, t=0.28) is statistically zero and is directly contradicted by its own IS (−4.7c,
t=−2.7) — textbook noise, not a survivor.

---

## Capacity

Moot, since EV is negative. For the record, taker depth on the laggard side is real and
large (median available size: ETH ~50, SOL ~170–280, XRP ~220–390 contracts), so a *real*
edge here would have had genuine taker capacity — which is exactly why the hypothesis was
worth testing and exactly why its failure is decisive rather than a small-sample shrug.

## Why it's dead (mechanism)

Crypto spot is arbed across BTC/ETH/SOL/XRP in well under a second, and each 15-min binary
absorbs its own spot within a minute (`DIRECTIONAL.md`). By the time BTC's *binary* has
moved, the common factor is already in the laggard's spot and therefore in the laggard's
binary mid. There is no residual divergence left to take — the cross-asset signal is
redundant with the laggard's own mid (Test A/B incremental coef ≈ 0, wrong-signed), and
crossing the spread to chase it just pays fee + spread for negative alpha.

**Do not deploy.** Re-run only if market microstructure visibly changes (e.g., a new alt
binary launches with materially worse liquidity/latency than the spot it tracks).
