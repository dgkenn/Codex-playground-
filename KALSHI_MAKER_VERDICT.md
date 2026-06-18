# Kalshi maker favorite-longshot harvest — CONSOLIDATED VERDICT (2026-06-18)

**A real, tradable, +EV Kalshi edge EXISTS — but it is capacity-capped at ~$30–150/month.**

This corrects the premature "no tradable Kalshi stack" call (`KALSHI_FAVLONG_SCAN.md` tested only the *taker*
side). Prompted by the right pushback — *low volume cannot mean a fully efficient market* — we tested the
**maker** side (the GWU "makers win, takers lose" result) across four parallel streams. The edge is real.

## The four streams

**1. Maker EV by band** (`kalshi_maker_harvest.py`, 860 settled soft markets, mid-life quotes)
- Buying at the bid / selling at the ask (maker) flips the favorite-longshot bias **+EV in 13/13 bands** —
  maker EV ≈ taker EV + spread. The cleanest, best-populated signal is **deep-longshot SELL** (maker NO):
  0.00–0.05 (n=254) +2.3¢; 0.05–0.10 (n=97) +5.8¢ — longshots resolve YES *less* than priced (overpriced).
- Caveat: per-band miscalibration z is mostly <2; the maker EV is dominated by spread capture. Necessary, not
  sufficient — the gate is adverse selection.

**2. Adverse selection — THE GATE** (`KALSHI_MAKER_ADVSEL.md`, 263,031 real maker fills, 13.9M contracts)
- **Overall maker P&L to settlement, net of fee ≈ −0.002¢/contract — the blanket "make everything" edge is DEAD**
  (favorites carry a ~2¢ adverse-selection drag: you get filled on a favorite precisely when it's about to fail).
- **BUT the deep-longshot SELL band (p<0.20) SURVIVES: +0.97¢/contract at ~17σ, net of adverse selection AND fee.**
- **No fast informed-taker pickoff** — +10-min markout is positive in every band — unlike the crypto box. The
  longshot *buyers* are genuinely uninformed (recreational lottery flow). This is the academically-robust pocket.
- Caveat: sample was weather-heavy (Climate 374/600); generalization rests on stream 4's cross-category bias.

**3. Capacity — THE BINDING CONSTRAINT** (`KALSHI_MAKER_CAPACITY.md`, real volume distribution)
- Median tradeable soft market turns over only **~1,000–1,700 contracts over its entire life** (~$300–800 notional,
  shared across all makers). Touch trades in **3–4 contract nibbles** — a $100–1,000 clip can't fill in size.
- Flow is **settlement-loaded (55–65% in the final third)** = the fillable flow is also the most adverse.
- **Realistic capture ~$1–5/day (~$30–150/month), optimistic ceiling ~$10/day — worse than the crypto box.**
- It is **flow-capped, not capital-capped**: more bankroll does NOT buy more harvest. ~$30–150/mo is the ceiling.

**4. Category softness × fees** (`KALSHI_MAKER_RANK.md`)
- **DECISIVE FEE FIND: soft categories are ZERO maker fee** (API `fee_type=quadratic` default). Only flagship
  series (NBA/NFL/Fed/CPI/Emmys, `quadratic_with_maker_fees`) charge makers 25% of taker. **95–100% of every soft
  category is maker-free** — so the longshot edge is NOT eroded by fees (stream 2 conservatively charged a fee it
  mostly wouldn't pay → the real edge is marginally *better* than +0.97¢).
- **Softness (vol-wtd |bias|): Science 18.8pp > Politics 17.8 > Climate 11.9 > Entertainment 10.4 > Econ 8.1 >
  Sports 8.0** — the longshot overpricing **generalizes across categories**, not a weather artifact.
- Best zero-fee corners: Politics BUY-NO 0.15–0.40; Climate BUY-NO 0.40–0.75; Entertainment BUY-NO 0.10–0.25.

## Verdict

**There IS a tradable Kalshi stack: be the maker who SELLS overpriced longshots on soft, zero-maker-fee markets.**
It is +EV (~+1¢/contract net), queue-independent, adverse-selection-surviving (longshots only — NOT favorites/mids),
maker-fee-free, has no fast-pickoff toxicity, and generalizes across categories. This vindicates the thesis that a
low-volume market can't be fully efficient — it isn't, and this is the capturable pocket.

**The catch is capacity, not edge.** The markets are so thin that the harvest ceilings at **~$30–150/month**,
flow-capped (more bankroll doesn't help), with **negative skew** (collect ~1¢ most of the time; lose ~95¢ when a
longshot hits → must diversify across many markets and size tiny). It does NOT reach the $500/mo goal and does NOT
scale. It is the fundamental favorite-longshot tension: the bias is biggest exactly where the books are thinnest.

**What it is:** the first genuinely +EV, deployable, retail-accessible Kalshi edge the project has found — a small
automated income stream (~$30–150/mo) runnable on the existing maker-box infra repointed at soft-market longshots.
**What it isn't:** a path to $500/mo or anything that scales with capital.

### Deploy decision (open)
Worth building IFF ~$30–150/mo of automated, uncorrelated, +EV income justifies the build + tail-risk management.
Pre-deploy hardening still needed: (a) longshot-only live paper-track to confirm fills + the +0.97¢ out-of-sample;
(b) negative-skew sizing (Kelly-fraction across many independent longshots, full-collateral aware); (c) avoid the
`quadratic_with_maker_fees` flagship series; (d) confirm the bias on a non-weather live sample.
