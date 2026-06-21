# KALSHI LONGSHOT-MAKER HARVEST — SEGMENTATION OPTIMIZER

**Date:** 2026-06-21 **Script:** `kalshi_longshot_opt.py` (Kalshi public API, no auth, strict 0.4s rate-limit)
**Builds on:** `KALSHI_MAKER_ADVSEL.md` (+0.97¢/contract @17σ baseline, 263k fills), `KALSHI_MAKER_CAPACITY.md`
(~$30–150/mo, flow-capped), `KALSHI_MAKER_RANK.md` (zero-maker-fee `quadratic` default; category bias rank),
`KALSHI_MAKER_VERDICT.md`. **Does NOT re-derive them** — it optimizes *which* slice of the validated
longshot-SELL pocket maximizes the net (adverse-selection-inclusive) edge.

**Job:** find the optimal (category × price-band × filter × side) that maximizes the realized maker P&L to
settlement, net of fee, with **event-clustered** significance, an honest multiple-testing read, and a
held-out / cross-category robustness gate.

---

## Metric & method (the rigorous, selection-baked-in number)

Identical realized-P&L-to-settlement metric as `KALSHI_MAKER_ADVSEL.md` — it is conditioned on the fill
happening, so it **bakes in adverse selection**. The harvest side is **SELL_YES** (= rest a NO bid / offer
YES; you are filled only when a taker *lifts* YES, i.e. `taker_side=="yes"`):

```
SELL_YES fill: maker SHORT yes, pnl = fill_price − settle   (settle = 1 if result==yes else 0)
fee/contract  = 0 on `quadratic` series (the default soft universe);
                0.25·0.07·p·(1−p) on `quadratic_with_maker_fees` flagships (excluded by default).
```

**The decisive honesty fix vs. the baseline:** significance is **clustered by EVENT** (`event_ticker`), not by
fill. All fills in one event share a single settlement outcome and are **not independent** — naive
per-fill SEs (the source of the headline "17σ") overstate significance by ~√(fills/event). Every z below is
the event-clustered, contract(dollar)-weighted (VW) number a real maker actually absorbs.

**Sample (this run):** 1,024 settled binary soft markets, **218,113 stored low-band fills (p<0.35)**,
122,908 on the harvest (SELL_YES) side. Broadened beyond the weather-heavy baseline:
Climate 320 mkts / Economics 320 / Science&Tech 234 / Entertainment 139 / Politics 10 / World 1 / Companies 0.
**Caveat:** Politics yielded only 10 settled binaries with low-band fills (most resolve as MVE/long-horizon or
sit favorite-side) — so the baseline's "Politics top corner" is **not testable here** and is *not* claimed.
Climate still carries the most contract mass (it has by far the most settled binaries); the cross-category
checks below exist precisely to prove the result is not a weather artifact.

---

## 1. PRICE BAND — the optimization lives here

SELL_YES, zero-maker-fee universe, event-clustered VW net P&L ($/contract):

| band (yes-price) | VW net P&L | event-clustered z | n_fills | n_events | contracts |
|---|---:|---:|---:|---:|---:|
| **[0.00,0.05)** | **+0.0140** | +31 | 32,650 | 121 | 5.01 M |
| **[0.05,0.10)** | **+0.0495** | +6.9 | 25,776 | 123 | 0.96 M |
| **[0.10,0.15)** | **+0.0485** | +2.2 | 13,443 | 114 | 0.45 M |
| [0.15,0.20) | −0.0231 | −0.4 | 10,092 | 111 | 0.29 M |
| [0.20,0.25) | −0.0119 | −0.2 | 9,182 | 101 | 0.23 M |
| [0.25,0.35) | −0.0502 | −1.0 | 18,956 | 106 | 0.41 M |

**Findings, brutally honest:**

1. **The sweet spot is [0.05,0.15), at ~+5¢/contract** — *five times* the +0.97¢ baseline average, and the
   hypothesis (~0.05–0.15) is confirmed. Pooled [0.05,0.15): **+5.45¢, z=+4.7** (event-clustered).
2. **The deep tail (<0.05) is NOT efficient — but it is *thin* per contract: +1.40¢.** This *refines* the
   RANK doc's "deep tail is efficient" prior: there IS a positive edge at <0.05 (z=+31, dead-consistent across
   all four categories), but it is ~¼ the per-contract edge of the 0.05–0.15 band. The deep tail dominates the
   baseline's *contract count* (5.0 M of 6.7 M), which is exactly why the pooled p<0.20 average is dragged down
   to ~+1–2¢. **Dropping the deep tail roughly triples per-contract edge.**
3. **The edge dies at p≥0.15.** [0.15,0.20) and up are mixed-sign and insignificant — thin, noisy, not
   harvestable. The earlier docs' "0.15–0.40" Politics corner does **not** survive on the net metric in this
   (non-Politics-heavy) sample; the harvestable window is **narrower and lower than 0.20**.

**→ Optimal band = [0.05, 0.15).**

## 2. CATEGORY — the edge GENERALIZES (not a weather artifact)

Pooled [0.05,0.15), SELL_YES, zero-fee, by category:

| category | VW net P&L | clustered z | n_events | contracts |
|---|---:|---:|---:|---:|
| Entertainment | **+0.0757** | +4.4 | 9 | 53 k |
| Science & Technology | **+0.0652** | +2.6 | 32 | 145 k |
| Climate & Weather | **+0.0539** | +3.7 | 53 | 1.07 M |
| Economics | +0.0401 | +1.6 | 34 | 140 k |
| Politics | n/a | — | 0 | 0 |

**Every testable category is positive in the sweet spot (+4.0¢ to +7.6¢), three of four at z≥2.6.** This is
the multiple-testing-robust core finding: the band edge is *not* one lucky cell — it reproduces across four
independent category samples. Deep-tail (<0.05) is likewise +1.3¢ to +1.8¢ in **all four** (z 4.7–34).
Ranking on the *net* edge: **Entertainment ≈ Sci&Tech > Climate > Economics** — note this **reorders** the
RANK doc's calibration-based list (which had Sci>Politics>Climate>Ent>Econ); on the realized, fee-and-
selection-net metric, **Entertainment and Sci&Tech carry the richest per-contract edge** (though small-n).

## 3. FILTER LIFT (base = SELL_YES, zero-fee, p∈[0.05,0.20))

| filter | VW net P&L | clustered z | n_events | verdict |
|---|---:|---:|---:|---|
| BASELINE | +0.0370 | +2.3 | 133 | — |
| volume_fp ≥ 1000 | +0.0369 | +2.3 | 117 | ~zero lift |
| volume_fp ≥ 2000 | +0.0365 | +2.2 | 103 | ~zero lift |
| volume_fp ≥ 5000 | +0.0405 | +2.4 | 81 | +0.35¢, marginal |
| **early life (≥50% life left)** | **+0.0505** | **+3.1** | 107 | **+1.3¢ lift, real** |
| mid life (10–50% left) | +0.0287 | +1.4 | 107 | drag |
| late life (<10%, settlement) | +0.0424 | +1.6 | 69 | neutral, but toxic-flow window |
| single-outcome (1 leg) | +0.0799 | +1.6 | 15 | rich but tiny-n |
| multi-leg (≥2 legs) | +0.0347 | +2.1 | 118 | bulk of flow |
| broad multi-leg (≥5 legs) | +0.0346 | +2.1 | 114 | no extra lift |

**Quantified lifts:**
- **Time-to-settle is the one filter that genuinely lifts edge: fill EARLY (≥50% of life remaining) → +5.05¢
  vs +3.70¢ baseline (+1.3¢, z=+3.1).** This is the opposite of the capacity doc's "flow is settlement-loaded"
  problem — the *cleanest* fills are the early ones, before informed end-of-life flow arrives. It also
  *reduces* the negative-skew exposure (more time = the longshot hasn't yet been picked off).
- **Volume thresholds add ~nothing** (the edge is not a thin-book illusion that liquidity washes out; if
  anything ≥5k is marginally *better*, +0.35¢, contradicting any "only works on garbage markets" worry).
- **Single-outcome vs multi-leg: single-leg looks richer (+8.0¢) but n_events=15 is too small to bank.**
  The bulk multi-leg flow is +3.5¢ — fine. **No meaningful correlated-event penalty observed** once you
  cluster SE by event (which already neutralizes within-event correlation).
- **Maker-fee (`quadratic_with_maker_fees`) series:** the band edge survives there too (+5.88¢ net of the
  0.25× maker fee in [0.05,0.15)), so the fee exclusion is a *small* lift in this band (fee ≈0.1¢ at p≈0.1),
  not the dominant lever it is mid-curve. Still exclude them — free money — but the band is the real driver.

## 4. SUB-POCKET hunt — multiple-testing-honest

23 (category × band) cells tested; Benjamini–Hochberg FDR ≤ 10% applied. The cells that **survive BH** and the
robustness gate, ranked by net edge:

| cell | VW net P&L | clustered z | n_events | contracts | BH | held-out folds |
|---|---:|---:|---:|---:|:--:|:--:|
| Sci&Tech [0.12,0.17) | +0.110 | +4.4 | 21 | 48 k | ✅ | CONSISTENT (+0.107 / +0.132) |
| Entertainment [0.10,0.15) | +0.085 | +3.6 | 8 | 26 k | ✅ | CONSISTENT (+0.118 / +0.069) |
| Entertainment [0.07,0.12) | +0.067 | +8.6 | 9 | 31 k | ✅ | CONSISTENT (+0.077 / +0.062) |
| Climate [0.07,0.12) | +0.054 | +3.4 | 53 | 596 k | ✅ | — |
| Climate [0.05,0.10) | +0.052 | +6.2 | 53 | 739 k | ✅ | — |
| Sci&Tech [0.05,0.10) | +0.050 | +3.6 | 29 | 99 k | ✅ | — |
| Climate [0.02,0.07) | +0.031 | +13.8 | 53 | 1.17 M | ✅ | — |

**Is the +5¢ band a small-n multiple-testing mirage? No — and here is the proof it isn't:**
- **Cross-category replication:** the [0.05,0.15) edge is positive and BH-significant in Climate (n_evt 53,
  1.07M contracts — *not* small-n), AND independently in Sci&Tech, AND in Entertainment. A noise cell does not
  reproduce across three independent category samples.
- **Held-out split:** pooling [0.05,0.15) and splitting *events* into two disjoint folds by hash →
  **fold A +4.66¢ (z=2.4) / fold B +6.51¢ (z=9.6)** — same sign, both significant, out-of-sample.
- The richest individual cells (Sci&Tech / Entertainment ~+8–11¢) are **small-n (8–21 events)** and should be
  treated as *upper-bound flavor*, NOT banked. The **honest deployable number is the pooled [0.05,0.15)
  ~+5¢**, which is large-n (128 events, 1.4M contracts) and survives every gate.

---

## THE OPTIMAL TRADING RULE

> **Be the MAKER who SELLS overpriced YES longshots (rest a NO bid) in the price band p ∈ [0.05, 0.15), on
> soft, zero-maker-fee (`fee_type == quadratic`) Kalshi categories — preferring Entertainment, Science &
> Technology, and Climate & Weather — and preferentially fill EARLY in market life (≥50% of life remaining).
> Exclude `quadratic_with_maker_fees` flagship series. Skip the deep tail p<0.05 (thin per-contract) and skip
> p≥0.15 (no edge).**

**Expected net edge / contract (adverse-selection- and fee-inclusive), with honest event-clustered CI:**

| rule | net edge/contract | 95% CI (clustered) | basis |
|---|---:|---:|---|
| **OPTIMAL: SELL_YES, [0.05,0.15), zero-fee, all-cat** | **+5.45¢** | **[+3.2¢, +7.7¢]** | 128 events, 1.41 M contracts |
| + early-life (≥50% life left) tilt | **≈ +6.5¢** | wider (n↓) | +1.3¢ lift, z=+3.1 |
| Baseline (ADVSEL, p<0.20 pooled both sides) | +0.97¢ | — | 263 k fills |
| Same-defn baseline here (SELL_YES p<0.20 pooled) | +1.91¢ | [+1.1¢,+2.7¢] | deep-tail-diluted |

**Verdict on "is the optimal meaningfully better than baseline?" — YES, ~3–5×, and it is real.** The +0.97¢
headline was a blend that drowned the rich [0.05,0.15) pocket under the high-volume-but-thin deep tail and the
zero-edge p>0.15 region. Isolating the band lifts the per-contract edge to **+5.45¢ (lower-CI +3.2¢)**,
replicated across four categories and a held-out split. This is the genuine optimum.

**The catch is unchanged and must be stated:** this does **NOT** raise the capacity ceiling. The richer band
[0.05,0.15) holds only ~1.4 M of the 6.7 M low-band contracts (~21%) — i.e. the deep tail you're now *skipping*
was most of the flow. Per `KALSHI_LONGSHOT_CAPACITY2.md` / `KALSHI_MAKER_CAPACITY.md`, the harvest is
**flow-capped at ~$30–150/mo**; a higher per-contract edge on a smaller filtered flow lands at a **similar
$/month**, just at higher quality-per-fill and lower variance. Negative skew is mild and manageable: only
**9% of events lose money** in the band (a longshot actually hitting); diversify across many uncorrelated
events and size tiny. **This is an edge-quality optimization, not a capacity unlock.**

### One-line rule for the bot
`side=SELL_YES (rest NO bid); 0.05 ≤ yes_price < 0.15; fee_type==quadratic; prefer Entertainment/SciTech/Climate; fill when ≥50% of market life remains; exclude quadratic_with_maker_fees.`
