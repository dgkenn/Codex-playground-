# DAILY-horizon crypto-longshot short-vol premium — measurement

_As-of 2026-07-18. Band YES∈[0.15,0.3]. Primary entry horizon = 24h before close. Haircut mid→bid = 0.01 (measured live band half-spread ~0.75–1c). Zero-fee headline (matches weekly ref) + with-fee sensitivity (0.07·p·(1-p)). Day-clustered t = cluster on resolution date._

**Universe:** 94 settled daily BTC+ETH `above ___` ladders (June 1–July 17 2026), 660 strike-markets priced.

## Horizon curve — YES longshot band, seller PnL/ct (day-clustered t)

| h-to-close | n | days | entry | realized YES | win% | mean(mid) | t | mean(exe −1c) | t | mean(exe+fee) | t |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 48h | 17 | 14 | 0.213 | 0.294 | 0.706 | -0.0814 | -0.67 | -0.0914 | -0.75 | -0.1096 | -0.90 |
| 24h | 11 | 11 | 0.217 | 0.455 | 0.545 | -0.2373 | -1.53 | -0.2473 | -1.60 | -0.2618 | -1.69 |
| 12h | 13 | 11 | 0.219 | 0.231 | 0.769 | -0.0122 | -0.09 | -0.0222 | -0.17 | -0.0406 | -0.31 |
| 6h | 12 | 11 | 0.230 | 0.333 | 0.667 | -0.1032 | -0.69 | -0.1132 | -0.75 | -0.1315 | -0.87 |

## Full calibration at 24h-to-close (ALL strikes, high-power)

_638 strike-markets with a valid 24h entry. edge = realized − entry; edge<0 ⇒ overpriced ⇒ seller gross-profits. sellPnL = entry − realized (mid, zero-fee); day-clustered t._

| bin | n | days | entry | realized YES | edge(r−e) | sellPnL | t |
|---|---|---|---|---|---|---|---|
| 0.02-0.05 | 20 | 15 | 0.031 | 0.000 | -0.031 | 0.031 | 15.43 |
| 0.05-0.10 | 16 | 12 | 0.073 | 0.000 | -0.073 | 0.073 | 20.55 |
| 0.10-0.15 | 9 | 9 | 0.124 | 0.222 | 0.098 | -0.098 | -0.67 |
| 0.15-0.30 | 11 | 11 | 0.217 | 0.455 | 0.237 | -0.237 | -1.53 |
| 0.30-0.50 | 19 | 14 | 0.401 | 0.368 | -0.032 | 0.032 | 0.26 |
| 0.50-0.70 | 18 | 14 | 0.607 | 0.667 | 0.059 | -0.059 | -0.41 |
| 0.70-0.85 | 15 | 12 | 0.786 | 0.667 | -0.119 | 0.119 | 0.80 |
| 0.85-0.98 | 44 | 27 | 0.937 | 0.977 | 0.041 | -0.041 | -1.68 |

_Structure: the coarse ~$2k-spaced ladder collapses toward 0/1 by 24h, so the weekly [0.15,0.30] band no longer holds longshots — it holds NEAR-MONEY strikes (realized ≫ entry, selling loses). The only overpriced region is the deep-OTM tail (2–10c, realized≈0): a mechanically-positive but tiny-per-contract, taker-dead-wing premium far below the weekly +0.12/ct._

## Primary = 24h-to-close entry (the DAILY-horizon bet)

- **n markets in band:** 11  |  **distinct resolution days:** 11  |  **positions/day:** 1.00
- **Calibration (OOS):** mean entry YES = **0.217** vs realized YES hit rate = **0.455** → NOT overpriced. Seller win rate = 0.545.
- **Equal-weight seller PnL/ct:**
  - mid, zero-fee: **-0.2373**  (day-clustered t = **-1.53**)
  - executable (mid−1c), zero-fee: **-0.2473**  (t = **-1.60**)
  - executable + fee(0.07·p(1-p)): **-0.2618**  (t = **-1.69**)
- **Volume-weighted seller PnL/ct:**
  - mid, zero-fee (pooled vw): **-0.2447**  ; exe: **-0.2547**
  - day-level vol-weighted mean: **-0.2373**  (t across 11 days = **-1.53**)
- **Left tail:** worst day = 2026-07-10 mean **-0.8450**/ct (n=1); best day = 2026-06-26 0.3000 (n=1); fraction of negative days = **0.455**.

**By asset (mid, zero-fee, day-clustered):**
| asset | n | days | entry | realized | mean PnL | t |
|---|---|---|---|---|---|---|
| bitcoin | 5 | 5 | 0.159 | 0.400 | -0.2410 | -0.99 |
| ethereum | 6 | 6 | 0.266 | 0.500 | -0.2342 | -1.06 |

**Both-wings robustness** (YES∈band + NO∈band, sell the longshot either side): n=26, days=17, mean **-0.1691**/ct, day-clustered t=**-1.79**.

## Daily vs weekly magnitude

- Weekly documented mean = **+0.12/ct** (week-clustered t~4.6).
- Daily 24h mid mean = **-0.2373/ct** → **-1.98×** the weekly per-contract edge.

## Up/Down daily markets (brief)

- n=60 settled BTC/ETH Up-or-Down markets, entry ~6h pre-close. Mean entry YES(Up)=0.478, realized Up rate=0.583.
- Sell-YES PnL/ct=-0.1049, sell-NO PnL/ct=0.1049 → possible skew.

## VERDICT

**The weekly [0.15,0.30] short-vol premium does NOT survive at the daily horizon in that band — the frequency lever does not multiply the edge; it inverts it.**


1. **Same-band test fails.** Entering the daily ladder 24h-to-close, YES∈[0.15,0.30] gives n=11 over 11 days: mean seller PnL **-0.237/ct** (day-clustered t=-1.53), and calibration is INVERTED — entry 0.217 vs realized YES 0.455 (realized > priced). At daily horizon the coarse ~$2k ladder collapses to 0/1, so band strikes are NEAR-MONEY, not lottery longshots; they are fairly-to-UNDER-priced, so selling them LOSES. This is the opposite sign of the weekly overpricing, i.e. a clean fail of the transported hypothesis.

2. **Only the deep-OTM tail is sellable, and trivially so.** The 2–10c buckets resolve YES ≈0.000, so selling earns ~their price (e.g. 5–10c bucket sellPnL ≈0.073, mechanical t huge because the payoff is near-deterministic). But (a) this is a DIFFERENT, lower band than the weekly; (b) magnitude per contract (≈3–7c gross) is well BELOW the weekly +0.12/ct; (c) it is the taker-dead wing (nobody lifts your 3–7c bid reliably) — the same executability trap that killed prior deep-wing candidates; (d) with feesEnabled=0.07·p(1-p) and a ~1c spread haircut the net shrinks further.

3. **Corroborating higher-power checks all point the same way.** Both-wings (YES+NO longshot, n=26): mean -0.169/ct t=-1.79 (negative, not significant). Up/Down daily (n=60): sell-YES -0.105, sell-NO 0.105 — a directional artifact (BTC/ETH drifted up in-sample), NOT a stable short-vol premium; no sellable vol edge.

4. **Capacity/frequency.** In the pre-registered [0.15,0.30] band the daily ladder yields only ~1.0 tradeable position per resolution-day (n=11 over 11 days) — the coarse strike grid + short horizon starve the band. So even the intended 7× frequency uplift does not materialize AT the profitable band.

5. **BLUNT.** Daily ≠ a faster weekly. The premium's magnitude at the weekly band is **negative** at daily horizon (point est. -0.24/ct vs weekly +0.12); the only positive is a tiny deterministic deep-tail scrape (~3–7c gross, taker-dead, sub-weekly, ~1 name/day). **Verdict: NULL-to-NEGATIVE for the transported edge; do NOT treat daily resolution as a lever to multiply the confirmed weekly short-vol return.** Caveat: n in-band is small (structurally, not by choice); the calibration inversion and unanimous corroboration make a hidden positive unlikely.