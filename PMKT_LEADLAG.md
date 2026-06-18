# Polymarket vs Kalshi BTC Cross-Venue Lead-Lag — PRELIMINARY SCREEN

> ## ⛔ RESOLVED 2026-06-18 (5-day update, see §5): NOT TRADABLE — signal real, ~40× too small.
> The data blocker is cleared (1,098 windows / ~110h / 5 days / multiple regimes). The lead **replicates
> strongly vs SPOT** (Poly leads ~10–15s; incremental HAC t ≈ +27 over spot momentum) but **collapses
> vs KALSHI's own mid**: the Poly→Kalshi cross-corr peaks at **lag 0** (contemporaneous, +0.25), and the
> genuinely *leading* residual is statistically significant (NW t = **+4.16**) but worth only **≈0.064¢
> per quote-adjustment** — versus a Kalshi taker cost of `0.07·p(1−p)` ≈ **1.75¢ + ~1.1¢ spread ≈ 2–3¢**.
> Kalshi already aggregates the same info nearly contemporaneously, so the tradeable part is ~40× below
> cost. This is the SAME wall as every other 15m candidate (real signal, sub-cost magnitude). The last
> open directional candidate is now closed. Do NOT build a taker stack on this.

**Date:** 2026-06-14 · **Original verdict:** TOO EARLY — suggestive in-sample lead, NOT confirmed; need ~3–5 more weeks of multi-session touch data. **Touch depth is deeper than the earlier audit feared** (~$80 median executable, p95 ~$600), so capacity is NOT the blocker — DATA is.

This screens. All numbers below §1–4 are IN-SAMPLE on a single ~2.1h session. **Superseded by §5.**

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

---

## 5. FIVE-DAY UPDATE (2026-06-18) — data blocker cleared; signal real vs spot, DEAD vs Kalshi-mid net of cost

The touch collector kept running. We now have the sample the screen asked for, and ran BOTH harnesses
on it (`pmkt_touch_leadlag.py` vs spot, `pmkt_leadlag.py` vs Kalshi mid), 2026-06-14 → 06-18.

### Sample (capacity blocker resolved)
- **1,098 windows / 195,027 touch snapshots / 92.9h** across **5 distinct days** (multiple regimes) for the
  touch harness; **109.9h / 197,888 grid pts @2s** aligned for the Kalshi-mid harness.
- Executable touch depth confirmed **deeper, not thinner**: median **$106**, p95 **$848** to lift the ask
  (level-SUM `up_bsz` ~136× inflated by reward-farm levels, as before). Capacity is NOT the blocker.

### Result A — vs SPOT (replicates the encouraging screen, strongly)
`xcorr(poly_dprob[t], spot_ret[t+k])`, k>0 ⇒ Poly leads spot:

| lag | −10s | −5s | 0s | +5s | **+10s** | **+15s** | +20s |
|---|---|---|---|---|---|---|---|
| corr | −0.008 | −0.000 | +0.017 | +0.028 | **+0.136** | **+0.149** | +0.041 |

Incremental HAC (next spot move ~ spot_mom + poly_dev + poly_dmom): **poly_dev NW t = +27.7 / +26.3 / +15.2**
at 5/10/30s, spot_mom weak/negative. So Polymarket genuinely leads **spot** by ~10–15s, robustly, OOS-of-the-screen.

### Result B — vs KALSHI MID (the decisive, tradability-relevant test) — FAILS on magnitude
`ΔKalshi_fwd ~ const + b_poly·ΔPoly_past + b_spot·ΔSpot_past`, W=5s, HAC NW-lags=5, n=160,592:

| term | β | NW t | sig |
|---|---|---|---|
| Δpoly | +0.01064 | **+4.16** | *** |
| Δspot | −0.00000 | −0.00 | — |

- **Cross-corr Poly→Kalshi peaks at lag = 0s (+0.252)** — the two venues move *contemporaneously*; the
  leading residual is small.
- **Implied edge ≈ 0.064¢ per quote-adjustment.** β=0.011 means a 1¢ Poly move predicts a 0.011¢ Kalshi
  move over the next 5s; even a 10¢ Poly move ⇒ ~0.1¢ predicted Kalshi move.
- **Kalshi taker cost** `0.07·p(1−p)` ≈ **1.75¢** + **~1.1¢** spread ≈ **2–3¢ round trip.**
- ⇒ tradeable lead is **~30–45× below cost.** Statistically real (t=4.16), economically negligible.

### Why spot-lead ≠ Kalshi-lead (the resolution)
`DIRECTIONAL.md` already established Kalshi's 15m binary is efficient vs spot within ~1 minute. Polymarket
leads *spot* by ~10s, but Kalshi prices spot nearly instantly, so by the time Poly has moved, Kalshi's mid
has too. The cross-corr peak at lag 0 is exactly that. The ~0.064¢ residual is the only part Kalshi hasn't
already absorbed — far too little to cross the spread + fee as a taker, and impossible to capture as a
maker (queue position, the box's grave).

### Verdict
**The last open directional candidate is closed.** Every 15m-crypto Kalshi angle is now exhausted:
maker box (queue/strand-dead), directional taker (efficient <1min), signal ensemble (worse than the mid),
and cross-venue Poly lead-lag (real but ~40× sub-cost). There is no tradable 15m-crypto Kalshi stack for a
small-bankroll cloud trader. A tradable Kalshi stack, if one exists, must come from a DIFFERENT market
class where the edge is value / risk-premium (not sub-minute speed) — longer tenors or non-crypto markets
where being slow and small is not disqualifying. That is the only remaining direction worth pursuing.
