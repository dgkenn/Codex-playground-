# Phase-2 Track A — price-EV re-validation on the FULL real Kalshi history

**Window:** 2026-05-12 → 2026-07-17 (67 days, the COMPLETE tradeable history — Kalshi weather
markets are new listings). ALL ~20 cities × full 6-rung ladder × KXHIGH + KXLOW. 16,074 rung-market-days
analyzed; 4,383 had ≥1 firing cell. Glitch filter removed only 11 obs total (glitches are rare).

## Headline: the edge SURVIVES, at ~90× the old sample — but with a large deployability caveat

**Best config (walk-forward selected on train=earliest 60% of days, verdict CONFIRMED): margin=1, sustain=3.**

| view | n_fired | win% | mean exec | mean PnL/ct (net fee) | cluster-t | Wilson95 worst-case loss | worst-case EV |
|---|---|---|---|---|---|---|---|
| train (39 days) | 2442 | 99.84% | 90.5¢ | **+0.0893** | 25.8 | 0.42% | +0.087 |
| test  (27 days) | 1449 | 99.79% | 90.1¢ | **+0.0930** | 19.1 | 0.61% | +0.089 |
| **full (66 days)** | **3891** | **99.82%** | **90.4¢** | **+0.0907** | **31.9** | **0.37%** | **+0.089** |

Train and test agree tightly → walk-forward robust, not in-sample overfit. Compare to the prior single-city
67-day number (n=42, +0.343/ct, t=7.56): the **all-city ladder gives ~90× the fires** and the same sign/
significance, but a **lower mean EV/ct (+0.091 vs +0.343)** because the full ladder includes many rungs that
are already fully priced. Full-history wins per the mandate: the honest blended EV is **+0.091/ct**, not +0.34.

## The profit-takeability caveat (the operator's key question, quantified)

The mean hides the distribution. Gap = (100¢ − exec_price) at the moment our sensor confirms the lock:

- Gap quantiles (full): p10=0, p25=0, **p50=0**, p75=11¢, p90=34¢.
- **The MEDIAN fire has ZERO gap** — by the time the observed max confirms the strike, the market is already at
  ~100¢. The +0.091 mean is carried entirely by the ~37% of fires that still have a gap.
- **Dead-on-arrival: 63% of fires** are already ≥97¢ (no meaningful profit). Honest **deployable n ≈ 1,435**
  (37% of 3,891), not 3,891. At the ≥99¢ threshold, 56% DOA → 1,698 deployable.
- On the deployable fires, EV is strong: **~+0.187/ct** if acted immediately.

**So: the edge is real and there IS profit to take — but only on ~1/3 of fires; the other 2/3 have already
repriced to ~100¢ before we can act.** This is exactly the risk the operator flagged.

## Gap decay / speed — SPEED IS EVERYTHING (half-life ≈ 3.3 min)

Mean residual gap after the observed cross: 0min=9.6¢ → 1min=7.6¢ → 2min=6.1¢ → 5min=3.1¢ → 10min=2.6¢ →
30min=1.8¢ → 60min=1.1¢. **Half-life ≈ 3.3 minutes.** Captured EV if we can only act k minutes after the cross
(counts only fires still carrying a gap at time k):

| act latency | fires still profitable | mean PnL/ct |
|---|---|---|
| 0 min | 1897 | +0.187 |
| 1 min | 1511 | +0.185 |
| 2 min | 1300 | +0.170 |
| 5 min | 740 | +0.149 |
| 10 min | 638 | +0.143 |
| 30 min | 431 | +0.137 |
| 60 min | 197 | +0.179 |

**Implication: GitHub-Actions 2-hour polling is far too slow** — by 60 min only ~1¢ of gap remains and the
number of live opportunities has collapsed. To capture this we need near-real-time reaction (sub-minute to
~2 min) around the crossing. This confirms and hardens the adaptive-fast-polling requirement. NOTE the obs
feed itself gates this: a real-time 1-min source (Synoptic HF-ASOS, ~2-5 min latency) puts us in the
act@2-5min band (n≈740-1300, EV≈+0.15-0.17) — still clearly positive, but we forfeit the fastest fires.
(This reconciles the earlier single-market eyeball that looked "hours-long": that was the PRE-lock forecast
drift over the afternoon; the 3.3-min clock is the POST-lock residual gap.)

## Where the edge lives: the BRACKETS, not the headline ">X" rung

| rung group | n | win% | mean exec | PnL/ct | deployable (gap>3¢) |
|---|---|---|---|---|---|
| greater (">X" top rung) | 713 | 100% | 96.7¢ | +0.032 | only 90 (87% DOA) |
| between/less (brackets) | 3178 | 99.78% | 89.0¢ | **+0.104** (t=32) | 1345 (58% DOA) |

The obvious ">X" rung reprices fastest (retail watches it) → 87% dead-on-arrival. **The bracket rungs carry
almost all the real edge** — they stay mispriced longer. This is *why* the full-ladder expansion pays off,
and it argues for concentrating on the between-brackets.

## KXHIGH vs KXLOW — both strong

- HIGH: n=2288, +0.082/ct, t=22.7, Wilson95 worst-case 0.57%.
- LOW:  n=1603, +0.103/ct, t=22.8, Wilson95 worst-case 0.35%. (LOW slightly richer.)

## Real depth (Predexon L2) — thin; capacity is small-per-market

Only 5/20 samples returned L2 (Predexon coverage gaps at exact firing ms). Where it did: size_at_best
1–40 contracts, depth-within-2¢ 4–99 (median ~10–13). **Confirms the earlier "$35k/wk was ~25× overstated"
correction — per-fire fillable size is ~10–40 contracts.** Scaling therefore requires HIGH VOLUME across many
markets/cities (≈21 deployable fires/day), not size in any one — exactly the operator's high-volume thesis.

## The tail is real but rare

7 losing tickers / 3891 (~0.18%). Worst single trade −1.00 (KXLOWTMIN 2026-05-12, day one) and −0.77
(KXHIGH Phoenix). These are the ASOS-vs-CLI disagreements Track B is quantifying multi-year.

## Conservative alternative (margin=2, sustain=1)
n=3310, 99.49% win, exec 95.2¢, +0.041/ct, t=21.0, Wilson95 worst-case 0.82%, half-life 4.6 min. Buys later/
higher → lower EV but fires still positive; useful as the lower-risk sizing floor.

## Verdict
**CONFIRMED on the full all-city ladder.** Blended edge +0.091/ct (t=31.9), but the *deployable* edge is
~+0.187/ct on the ~37% of fires that aren't already repriced, and capturing it demands sub-few-minute reaction
(half-life 3.3 min) and high market count (thin per-market depth). Pair with Track B's all-season tail for
final sizing.
