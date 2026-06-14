# Polymarket vs Kalshi BTC Cross-Venue Lead-Lag — PRELIMINARY SCREEN

**Date:** 2026-06-14 · **Verdict:** TOO EARLY — suggestive in-sample lead, NOT confirmed; need ~3–5 more weeks of multi-session touch data. **Touch depth is deeper than the earlier audit feared** (~$80 median executable, p95 ~$600), so capacity is NOT the blocker — DATA is.

This screens. All numbers below are IN-SAMPLE on a single ~2.1h session. Do not trade on this yet.

---

## 1. DATA INVENTORY

**Touch-depth (`up_tbsz/tasz/down_tbsz/tasz`) records exist for ONE session only.**

| Field | Value |
|---|---|
| Touch snapshots | 4,713 (with valid up_bid/ask) — 5,040 raw with the field |
| Distinct 5-min windows | 26 |
| Calendar days | **2026-06-14 only** |
| Time span | 16:52Z → 18:59Z = **2.12 hours, contiguous** |
| Poll cadence | median gap 1.50s; only 7 gaps >30s (window rollovers) → near-continuous WITHIN the session |
| Pre-touch up_mid history | ~97k Polymarket ticks across 06-13/06-14 usable for prob-only lead-lag, but NO touch sizes |

Note: the collector's touch fields (commit 3098ba4, ~06-13) only began producing populated `up_tbsz` on **06-14 16:52Z**. So despite the collector running for days, executable-depth coverage is a single afternoon block.

### Touch-size distribution (CONFIRM/REVISE the "~$5–63" audit)

Pooled up/down × bid/ask touch, contracts, >0 (n=18,848):

| p05 | p25 | p50 | p75 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| 14 | 71 | **225** | 512 | 974 | 4,455 | 12,885 |

Executable **$** to lift the ask touch (contracts × price): **median ~$80, p95 ~$594, max ~$12.3k**.

**This REVISES the earlier "~$5–63" finding.** Touch is materially deeper than that — the $5–63 figure looks like an unlucky thin sample. Confirmed separately: the level-SUM `up_bsz` (~41,144) overstates real touch by **~166×** (the 45+ reward-farm levels), so the "~40k depth" really is fake — but the *true* touch (~$80 median, hundreds at p95) is still usable for a small book. Spread is tight (~1.1¢); prob mean 0.535, sd 0.263 (windows span the full 0→1 range as expected for 5-min binaries).

**Capacity verdict: deep enough for a $100–$10k bankroll.** Median ~$80 / p95 ~$600 executable at touch comfortably supports $100 clips and is workable up to low-$1k clips; depth is the LEAST of the concerns here.

---

## 2. LEAD-LAG vs SPOT (touch window, 5s grid, BTC spot = Kalshi-tick field[2] = CF BRTI settle index)

`xcorr(poly_dprob[t], spot_ret[t+k])`, k>0 ⇒ Polymarket prob LEADS spot:

| lag | -10s | -5s | 0s | **+5s** | **+10s** | **+15s** | +20s | +30s |
|---|---|---|---|---|---|---|---|---|
| corr | -0.025 | -0.006 | -0.030 | +0.068 | **+0.161** | +0.122 | +0.100 | +0.004 |

In this session Polymarket prob change **leads BTC spot returns by ~10s** (peak +0.16 at +10s; the negative/zero side at k≤0 means spot does NOT lead Poly). Polymarket prob vs Kalshi box mid is contemporaneous (peak at lag 0, corr +0.22) — both venues move together; the edge, if any, is Poly→spot.

**Contradiction worth flagging:** the existing full-history harness (`pmkt_leadlag.py`, ~43h of mostly pre-touch up_mid) finds the Poly↔Kalshi relationship peaks at **lag 0** (contemporaneous, corr +0.245) and the incremental Poly term over spot is marginal (HAC t≈+2.4, ~0.05¢ edge). The strong +10s lead here is a single-session result and may be a regime artifact. Two harnesses, two different strengths → not robust.

---

## 3. INCREMENTAL INFO (next spot move ~ spot_momentum + poly_signal; HAC NW-lag=10)

| Horizon | n | R² | t(spot_mom) | t(poly_dev) | t(poly_dmom) |
|---|---|---|---|---|---|
| +5s | 1,524 | 0.071 | -3.52 | **+5.19** | +1.20 |
| +10s | 1,522 | 0.069 | -0.44 | **+4.91** | **+4.21** |
| +30s | 1,514 | 0.068 | -0.72 | **+3.14** | **+4.85** |

In this session, Polymarket's implied prob (deviation from 0.5, and its recent change) is a **statistically significant predictor of the next 5–30s BTC spot move EVEN with spot momentum in the regression** (poly t = +3 to +5 under HAC; spot momentum is mostly insignificant). On its face: Polymarket adds info beyond spot.

**Why this is NOT yet actionable:** N is effectively **26 independent 5-min windows in one ~2h afternoon, one BTC regime**. The 5s grid is heavily autocorrelated; HAC mitigates the t-stat inflation but cannot manufacture independent observations. The full-history harness's weaker, contemporaneous result is the cautionary counter-example. R² ~0.07 of a 5–30s move is small, and against Kalshi's ~1¢ tick + fees the realizable edge is thin.

---

## 4. VERDICT

**(c) TOO LITTLE DATA YET — with an encouraging signal and no capacity problem.**

- **Touch depth:** sufficient (~$80 median / ~$600 p95 executable) for $100–$10k. The "$5–63" / "40k depth" framing is resolved: 40k was reward-farm sum (166× inflation), true touch ~$80, still fine. NOT the blocker.
- **Lead / incremental info:** in one session Polymarket prob leads spot by ~10s and survives a spot-momentum control (HAC t +3 to +5). **Promising but single-regime and contradicted in strength by the 43h prob-only harness.** Cannot be called a usable signal on N=26 windows.
- **Downstream-of-spot?** Not cleanly — the poly term beats spot momentum here — but one afternoon cannot reject "spot-driven coincidence."

### How much more data is needed
- **Independent windows, not seconds, are the binding constraint.** 26 windows ≈ a meaningless sample. Target **≥1,000 windows across ≥15 distinct sessions spanning ≥3 trading regimes** before any OOS claim.
- 5-min windows = 288/day if continuous; realistic intermittent GHA coverage is ~50–150 touch-windows/day.
- ⇒ **~3–5 more weeks** of always-on touch collection to reach ~1,000+ windows over enough distinct days/regimes for a real train/test split. At that point: re-run with a **walk-forward OOS split** (windows ordered in time, fit on first 70%, test on last 30%) and require the poly coefficient to stay significant AND net-of-fee profitable OOS before any toxicity-gate or trade use.

### Harness
- `pmkt_leadlag.py` (pre-existing) — full-history up_mid, HAC incremental regression vs Kalshi mid + spot; reuses `box_policy_ab.iter_gz`.
- `pmkt_touch_leadlag.py` (added) — touch-depth capacity distribution + touch-window-only lead-lag vs spot + HAC incremental test. Run: `python pmkt_touch_leadlag.py <pmkt_dir> <kalshi_ticks_dir>`. Spot is read from `ticks_kalshi_btc15m` field[2] (no external API).

**State for the record:** window = 2026-06-14 16:52–18:59Z; N = 26 windows / 4,713 touch snapshots / 1,522 aligned 5s rows; in-sample only; significance HAC-adjusted but N-limited. SCREEN ONLY.
