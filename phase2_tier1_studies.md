# Phase-2 Tier-1 "Could This Still Fail" Studies — K-WX Weather Nowcast Edge

Run date: 2026-07-18. Base config margin=1/sustain=3 (cell key `1_3`) unless noted.
Data: `_trackA_results_raw.json` (4383 rung-market-days, 66 fire-dates, window 2026-05-12→2026-07-17,
67 calendar days), `phase2_trackA_price_summary.json`, plus 49 freshly-pulled real Predexon L2
order-book snapshots (20 re-fetched from the known-good sample + 29 new pulls at deployable
fires' exact `t_star`, out of 40 attempted).

Deployable := `exec_price < 0.99` at fire. This reproduces the stated ~1698 fires exactly
(1698 of 3891 fired = 43.6%). DOA := `exec_price >= 0.99` (2193 fires).

---

## STUDY 1 — Adverse selection: are deployable fires the "leftovers"?

| segment | n | mean pnl/ct | loss rate | n losses | mean OI@exec | mean vol@exec |
|---|---|---|---|---|---|---|
| Deployable (exec<0.99) | 1698 | **+0.2074** (se 0.0053) | **0.353%** | 6 | 3408 | 190.4 |
| DOA (exec>=0.99) | 2193 | +0.0004 (se 0.0005) | 0.046% | 1 | 3768 | 37.3 |
| All fired | 3891 | +0.0907 | 0.180% | 7 | 3611 | 104.1 |

**Verdict: the +0.207/ct deployable EV is real, not an illusion — but it is compensated risk,
not free money.** Deployable trades lose ~7.7x more often than DOA trades (0.35% vs 0.05%).
6 of the 7 total losses in the whole dataset occurred in the deployable bucket, even though
deployable is only 43.6% of fired volume. All 6 deployable losses are "wrong-way" glitch fires
where the market crossed strike+margin, sustained 3 minutes, then reversed before settlement —
exactly the tail risk you'd expect from trading *before* full repricing. OI at execution is
essentially indistinguishable between the two buckets (median 1834 vs 1807), so it is not simply
"thinner markets" driving the split — the difference is temporal (still-repricing vs already-locked).

Skew found:
- **Family**: HIGH carries all the deployable loss rate (0.67%, 6/898); LOW has **zero** losses
  in 800 deployable observations.
- **Rung group**: `between` rungs (interior ladder cells) carry all deployable risk (0.40% loss
  rate, 1498 of 1698 deployable fires); `greater`/`less` (open-ended tail rungs) have 0% losses
  in the deployable sample (118 + 82 obs).
- **City concentration**: Denver is 13.7% of all deployable volume (232/1698) with a 62.9%
  deployable-fraction (fires arrive with an open gap far more often there) — nearly 1.5x the
  average city's ~41% deployable-fraction. This is a volume/liquidity artifact (more of Denver's
  edge is still un-repriced when it fires), not a risk problem — Denver's deployable loss rate is
  0.00% (0/232).
- **Real risk hotspot**: Phoenix deployable loss rate is 6.25% (2/32) — an order of magnitude
  above the population average, both losses HIGH-family. Small n (32), but both Phoenix HIGH
  deployable losses landed at wide gaps (0.51, 0.24) — worth a per-city risk flag even though it
  doesn't change the pooled EV materially (Phoenix is only 1.9% of deployable volume).

**Bottom line for S1**: EV is not contaminated in the sense of being fake — the +0.207/ct mean
survives the 6 losses easily (se 0.0053, t≈39). But it is *concentrated* risk: HIGH-family
`between` rungs, disproportionately worth watching in Phoenix. LOW-family and edge (`greater`/
`less`) rungs are essentially riskless in this sample.

---

## STUDY 2 — Sustain vs latency (margin=1, deployable subset)

| cell | n fired (all) | n deployable | mean gap@t* | mean pnl/ct | win rate | n wrong_way | worst pnl | worst-case EV (mean−1.645·se) |
|---|---|---|---|---|---|---|---|---|
| 1_1 (sustain=1) | 4383 | 2434 | 0.2817 | 0.1356 | 86.32% | 333 | −0.972 | **0.1252** |
| 1_2 (sustain=2) | 4119 | 2081 | 0.2489 | 0.1779 | 93.80% | 129 | −0.972 | **0.1682** |
| 1_3 (sustain=3) | 3891 | 1698 | 0.2195 | 0.2074 | 99.65% | 6 | −0.773 | **0.1987** |

Sustain=1 captures the *largest raw gap* on paper (0.282 vs 0.220 for sustain=3) — exactly as
predicted by the 3.3-min gap half-life, since less time elapses before entry. But that extra gap
is overwhelmingly captured on trades that turn out to be **glitches**: sustain=1 has 333 wrong-way
deployable fires (13.7% of its deployable population) vs 6 for sustain=3 (0.35%). The realized
mean pnl and worst-case EV are strictly monotonic in sustain length (1 < 2 < 3): confirming more
gap and fewer glitches are not correctable inversely — waiting the third minute is the single
highest-leverage risk filter in the whole system.

**Recommendation: sustain=3 remains optimal.** It maximizes worst-case EV (0.199 vs 0.168 vs
0.125) despite having ~30% fewer deployable opportunities than sustain=1. Sustain=2 is not a good
middle ground — it still carries 129 wrong-way fires (21.5x sustain=3's rate) for only 8% more
opportunity count. This study does **not** change the deployability verdict — it reconfirms the
existing best-config choice was correct, and quantifies exactly how much of sustain=1's apparent
extra gap is actually latency-arbitrage noise rather than real edge.

---

## STUDY 3 — Market-impact capacity curve (real Predexon L2)

Data quality: of 91 total L2 pull attempts (51 original + 40 new, targeted at deployable
fires' actual `t_star`), 49 (53.8%) returned a usable order book; 19 (20.9%) were **confirmed
empty books** (zero resting size on the relevant side at the exact fire moment — a real
execution-feasibility risk not modeled in the backtest); 23 (25.3%) had no snapshot in the
±10-min window at all (data-coverage gap, unknown liquidity state). Treat 53.8%–79.1% as the
honest range for "fraction of deployable fires with any confirmed executable depth."

EV/ct after sweeping the real book (size-weighted avg fill, fee = 0.07·p·(1−p) recomputed on
avg fill price), aggregate mean across the 49 sampled deployable fires:

| target size (ct) | mean EV/ct (unconstrained fill) | mean $ profit/fire (capped at 0.10 EV/ct floor) | mean n filled (0.10 floor) |
|---|---|---|---|
| 1 | 0.1781 | — | — |
| 5 | 0.1737 | 0.74 | 2.9 |
| 10 | 0.1695 | 1.44 | 5.7 |
| 25 | 0.1616 | 3.45 | 14.3 |
| 50 | 0.1536 | 6.56 | 28.0 |
| 100 | 0.1409 | 11.71 | 51.7 |

At the pooled/aggregate level, EV/ct degrades gently (0.178→0.141, ~21% decay from 1 to 100
contracts) and never crosses the 0.10 floor even at 100 contracts — that headline number is
**misleadingly optimistic**, because it's a mean over a bimodal population:

- **42.9% of sampled deployable fires (21/49) cannot clear the +0.10 EV/ct floor at ANY size** —
  their book is thin enough that even 1 contract's fill price already erodes EV below 0.10 (these
  are near-DOA-with-a-sliver-of-gap trades, exec price already ~0.90+).
- **57.1% (28/49) can take size while staying above 0.10 EV/ct**, with a highly skewed depth
  distribution: median max size ≈147 contracts, but 8/49 (16.3%) have book depth exceeding 500
  contracts while still clearing the floor.

**Per-market max size at EV≥+0.10**: bimodal — 0 contracts for ~43% of fires, median ~147
contracts (mean 243) for the remaining ~57%, with real observed depths on the deep side up
to 3878 contracts on the visible book (KXLOWTSATX-26MAY27-B64.5).

**Honest total weekly capacity**, using target size = 100 contracts/fire (chosen because it is
the largest of the requested grid where the *aggregate* EV/ct still clears 0.10), applying the
per-market depth-and-floor cap ($11.71 mean $/fillable-fire at that target), historical
deployable rate of 1698/67 days × 7 = **177.4 fires/week**, and the two fillability bounds:

- Conservative (53.8% fillable, treats no-snapshot as unfillable): **≈$1,118/week**
- Optimistic (79.1% fillable, treats no-snapshot as coverage-gap only): **≈$1,643/week**

At a more conservative 25-contract sizing the range is **≈$330–$485/week**. This is materially
below what a naive "just multiply 1698 fires/67 days × $0.207/ct × 100 contracts" extrapolation
would suggest (~$5,270/week) — real book depth and the 43%-of-fires-have-no-real-size problem cut
that naive number by roughly 4–5x.

---

## STUDY 4 — Correlated same-day failure (heat-wave tail)

- 66 distinct fire-dates over the 67-day window; mean 58.95 fires/day (median 61), spread across
  a mean of 17.0 distinct cities/day (max 20 of the ~20-city universe).
- **No historical day ever had a net-negative aggregate pnl.** The worst day by total pnl was
  2026-06-24 (net pnl $0.00, 6 fires, all DOA — a quiet day, not a loss day). Every day with a
  real loss (7 loss-trades total, spread across 7 different dates: 2026-05-12, 05-19, 06-11,
  06-16, 06-20, 06-22, 06-29) still finished net-positive because losses never co-occurred more
  than once per day — the single worst individual tail loss (Minneapolis, 2026-05-12, pnl=−1.00
  on a $46.43-capital day) was still only −2.15% of that day's deployed capital.
- **Cross-city correlation of daily mean pnl is essentially zero**: mean pairwise correlation
  across 190 city pairs with ≥5 common fire-dates = **−0.0098**. Strongest single pairs (|r|~0.4–0.47,
  e.g. Oklahoma City/Washington DC r=−0.47, Houston/San Antonio r=0.40) are noise-level given n≈25–52
  paired days each — no systematic regional contagion pattern detected in this window.
- **City concentration**: mean city share of a day's deployed capital = 5.9% (median 5.4%, p90
  10.0%); the single highest observed concentration was 33.3% (Austin, on the smallest fire-day,
  $6 total capital — not a meaningful stress case).
- **Stress test**: on the single largest historical fire-day (2026-05-19, 88 fires, $81.95
  capital), it would take **9 simultaneous worst-observed-magnitude (pnl=−1.00) losses** on that
  one day to breach a −10%-of-day-capital threshold. Historically the max simultaneous losses on
  any single day was **1**.

**Recommended cross-city daily cap**: no single city should exceed ~15–20% of a day's deployed
capital (roughly 1.5–2x the historical p90 concentration of 10%). This is a *precautionary* cap,
not a fitted one — the 67-day sample shows no evidence of correlated failure (near-zero
cross-city pnl correlation, max 1 simultaneous loss/day), but 67 days is not enough history to
rule out a genuine multi-city heat-dome/cold-snap event that could correlate glitches (all 7
observed losses to date cluster in the May–June warm-onset period, consistent with the theory
that early-season temperature volatility drives more false triggers — worth monitoring as more
data accrues rather than treating the near-zero correlation as proven-safe).

---

## Overall verdict: does any of this change deployability?

**No — the edge remains deployable, but three real refinements emerge:**

1. **S1**: the deployable EV is genuine, not adverse-selection noise, but it is concentrated risk
   (HIGH-family, `between`-rung, with Phoenix as a per-city outlier at 6.25% loss rate on n=32).
   Consider a modest per-city risk multiplier down-weighting Phoenix HIGH `between` rungs, or just
   monitor it — it is not large enough to change the pooled number.
2. **S2**: sustain=3 is confirmed as the right choice — no change, but now quantified: sustain=1's
   apparent extra gap is 96% latency-arbitrage noise (333/2434 wrong-way vs 6/1698), not real edge.
3. **S3 is the most material new finding**: realistic weekly $ capacity at reasonable size (25–100
   ct/fire) is **~$330–$1,640/week**, not the naive multi-thousand-dollar extrapolation of the raw
   per-contract EV — because (a) ~21% of deployable fires have zero visible resting liquidity at
   the fire moment, and (b) ~43% of fires that do have liquidity are too thin to support any size
   above the 0.10 EV/ct floor. This doesn't kill the edge, but it caps how much capital it can
   usefully absorb, and any live implementation needs per-fire depth checks rather than assuming a
   fixed size is always fillable at the backtested exec price.
4. **S4**: no evidence yet of correlated tail risk across cities/days in 67 days of data — the
   edge's risk profile so far looks like isolated idiosyncratic misses, not systemic. A 15–20%
   per-city daily cap is recommended as a precaution, not because the data demands it.
