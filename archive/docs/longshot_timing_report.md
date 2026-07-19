# Longshot / short-vol SELL premium — does a LATER entry give a richer edge?

**Study script:** `longshot_timing.py`  **Run:** 2026-07-17, 322 s, Polymarket public API (zero-fee),
read-only. **Sample:** settled markets resolving on/after 2025-06-01.

## Question

We SELL far-OTM longshots on zero-fee Polymarket (confirmed edges: crypto weekly BTC/ETH "above $X on
<date>" + econ macro-release buckets), currently entering in the FIRST HALF of life. Does entering
LATER (closer to resolution) improve edge-per-trade and/or annualized return-on-capital (shorter
remaining hold frees capital sooner)? A priori there should be a sweet spot: too early = less
information; too late = price has mechanically converged toward the outcome so no premium is left.

## Method (causal, anti-artifact)

- **Universe.** CRYPTO: Gamma series 45 (BTC) + 42 (ETH), closed events, per-market life 2–10 d
  (isolates the ~7 d weekly), question contains "above", cleanly UMA-resolved to 0/1 → **6911 candidate
  markets, 2626 longshot-qualified**. ECON: `public-search` on macro families (CPI/PPI/jobs/JOLTS/Fed/
  GDP/nonfarm/PCE/retail/payrolls), closed events with ≥4 mutually-exclusive buckets, life 1–90 d →
  **676 candidates, 143 qualified**.
- **Full hourly YES-mid path** from `clob prices-history` (fidelity=60).
- **Longshot qualification (no peek):** YES mid touches [0.10, 0.35] at some tick in the FIRST 40% of
  life — defines the population without using any price at/after the entry fraction.
- **Entry fractions** f ∈ {0.20, 0.35, 0.50, 0.65, 0.80}. **Causal entry price** = YES mid at the last
  tick at/before f·life. "In-band at f" = that entry mid ∈ [0.10, 0.35] (the tradeable population at f).
- **Executable SELL** = entry_mid − half_spread (mid-only path ⇒ subtract conservative fixed
  half-spread: crypto 0.010, econ 0.015). **Edge/ct = (entry_mid − half_spread) − outcome**; outcome
  from UMA resolution only. Zero fee.
- **YES-BUY volume weight** (from `data-api trades`): YES-buy taker size = (Yes&BUY)+(No&SELL) in a
  ±10%-of-life window around f — the demand a YES-seller actually fills into (adverse-selection check).
- **Week-clustered t** (cluster by resolution ISO-week): equal-weight (`t_eq`) and YES-buy-vol-weighted
  (`t_bv`). **Annualized ROC** = (edge/(1−entry))/((1−f)·horizon_years); capital per contract ≈ 1−entry.

## CRYPTO — 2626 longshot-qualified weekly BTC/ETH markets

```
    f     n  wks   edge/ct   t_eq  vw_edge   t_bv   mid  yes%  hold_d  ann_ROC   vw_ROC
---------------------------------------------------------------------------------------
 0.20  1202   49   +0.0611   1.56  -0.0249   1.49  0.21  13.4    5.58    +5.19    -1.62
 0.35  1062   49   +0.0569   1.60  -0.0327   0.29  0.21  13.8    4.54    +5.88    -3.09
 0.50   827   49   +0.0323   0.51  -0.0647  -0.70  0.20  16.1    3.49    +4.25    -8.13
 0.65   594   48   +0.0221   0.36  -0.1275  -0.46  0.20  17.2    2.44    +4.27   -24.62
 0.80   385   48   +0.0096  -0.03  -0.0470  -0.76  0.21  18.7    1.40    +3.49   -15.55
```
(edge/ct, vw_edge in $ per contract; ann_ROC, vw_ROC are annualized return-on-capital multiples.)

**Read:** equal-weight edge-per-contract DECAYS monotonically as you enter later (+0.061 → +0.010) and
the week-clustered t falls from ~1.6 to ~0 (never significant at 2). Annualized ROC also decays after
f≈0.35. **Crucially, YES-BUY-volume-weighted edge is NEGATIVE at every fraction** (−0.025 to −0.128,
t_bv < 1 everywhere): the volume a seller can actually fill into is concentrated in the longshots that
end up printing → adverse selection erases the premium. Max risk-adjusted cell = **earliest fraction
(f=0.20)**, not a later one.

## ECON — 143 longshot-qualified macro-release buckets (underpowered)

```
    f     n  wks   edge/ct   t_eq  vw_edge   t_bv   mid  yes%  hold_d  ann_ROC   vw_ROC
---------------------------------------------------------------------------------------
 0.20    75   17   +0.0209  -0.30  +0.0246  -1.83  0.22  18.7    5.53    -0.54   +47.65
 0.35    61   16   +0.0158   0.97  +0.1251  -0.71  0.21  18.0    4.13    +3.57   +75.76
 0.50    74   18   +0.0232   0.54  +0.0713  -1.80  0.21  17.6    3.55    +2.16   +86.12
 0.65    66   17   -0.0140  -0.43  -0.4571  -2.69  0.20  19.7    2.53    -0.65  -152.07
 0.80    66   18   -0.0017  -0.19  -0.4463  -2.03  0.21  19.7    1.45   -14.17  -188.44
```

**Read:** edge/ct is mildly positive early/mid (+0.016 to +0.023 for f≤0.50) then turns NEGATIVE at
f=0.65 and f=0.80. No fraction reaches statistical significance (t_eq max 0.97; **t_bv is negative at
every fraction**). The huge vw_ROC swings (+86 to −188) are artifacts of tiny 1−entry denominators on
few high-volume names in an n≈60–75/cell sample — not a real return. n per cell is small; treat all econ
numbers as directional only.

## Verdict — does later entry help?

**No. For both populations the premium DECAYS with later entry; there is no later sweet spot.**

- **Edge-per-trade is richest EARLIEST** (crypto +0.061 at f=0.20, monotonically down to +0.010 at
  f=0.80; econ positive only for f≤0.50, negative after). This is the "mechanical convergence" arm: as
  f→1, price drifts to the outcome and the harvestable premium shrinks to ~0 (crypto) or flips negative
  (econ). The opposite "too-early = too little info" arm is **not** visible in the tested range —
  0.20 (the earliest fraction) is already the best cell.
- **Annualized ROC does not rescue later entry either.** Although later entry has a shorter remaining
  hold, the edge shrinks faster than the hold, so equal-weight ann_ROC also peaks early (crypto peak at
  f=0.35 = +5.88, f=0.20 = +5.19, then declining).
- **The decisive caveat:** once weighted by the YES-BUY volume you could actually sell into, the edge is
  **negative at essentially every fraction in both sleeves** (crypto t_bv < 1 throughout; econ t_bv < 0
  throughout). The tradeable, adverse-selection-adjusted premium does not clearly exist here at any entry
  time — and it certainly does not get richer later.

**Practical answer to the desk:** keep entering in the first half; if anything the equal-weight signal
is marginally strongest at the *earliest* window (f≈0.20–0.35), i.e. slightly earlier than mid-life, not
later. Do **not** delay entry hoping for a fatter late premium — the premium mechanically decays and the
sellable (volume-weighted) side is already negative.

## Honest caveats

1. **Volume-weighting kills it.** The single most important result: `t_bv` never clears 1 (crypto) and is
   negative throughout (econ). This is the same adverse-selection signature that has killed ~6 prior
   candidates. The equal-weight positives (crypto f=0.20–0.35) are real but modest (t≈1.5–1.6, below the
   t=2.26 of the pre-registered PMKT-SHORTVOL backtest) and do not survive the fill-weighting.
2. **This is a "still-in-band-at-f" conditional recompute**, not the original first-half rule, and it uses
   a fresh (post-2025-06) sample — so it is not directly comparable to the frozen backtest; it should not
   be used to retune the live rule. It answers only the *timing* question.
3. **Half-spread is a fixed estimate** (mid-only history; no historical best-bid reconstructable). Real
   executable edge is if anything worse than shown, especially for econ (wider books).
4. **ann_ROC / vw_ROC are high-variance** by construction (small 1−entry and 1−f denominators). Believe
   the ordering of `edge/ct` and the sign of the clustered t, not the ROC magnitudes — the extreme econ
   vw_ROC values are small-sample artifacts.
5. **Econ is underpowered** (143 qualified, ~60–75 per cell). Late-f cells and the negative econ edges are
   suggestive but not conclusive.
6. **Mechanical-convergence guard worked:** hold_days shrink (crypto 5.6→1.4 d) and n shrinks with f; we
   see edge→0 rather than a spurious late spike, so the late cells are not obviously convergence-inflated —
   they are simply de-premiumed.
```
