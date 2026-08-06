# EDGE_SIZING -- measured result, run 2026-08-06

Pre-registered spec: `venue_expansion/EDGE_SIZING_SPEC.md` (frozen 2026-08-06, bars did not move).
Context: the n=1 instance this study replaces the extrapolation for is `KXLOWTSEA-26JUL29-T57`, +46c/contract (`FORWARD_DATA_2026-08-02.md`).

## Sampling disclosure (read this first)

Population: **17,280** settled KXHIGH*/KXLOW* markets with a yes/no result, closing 2026-05-01..2026-08-04 (2.431 months).
That is too large for one session at the spec's ~1/sec politeness (17,280 candlestick calls). Per the spec's own fallback clause, Stage 1 draws a **fixed seeded random sample** (`seed=20260806`, `random.Random(seed).shuffle(index)`, first N taken). The DRAW is unbiased by date and station; the FETCH ORDER is population (series-grouped) order, so an incomplete pass is station-truncated even though the draw was not -- see the warning below.

**Stage-1 sample: 624 markets (3.6% of the population).**
Series represented: 11 of 40 in the population.

> **SELECTION BIAS — PARTIAL PASS: 624 of 2500 planned markets fetched. Because the fetch loop walks the sample in population (series-grouped) order, this partial result is STATION-TRUNCATED, not a random subsample: 11 of 40 series are represented and 29 are entirely absent. Frequency and capacity estimates computed from it are NOT population estimates and their direction of bias is unknown (untouched stations may be systematically wider or tighter). Do not extrapolate until the pass completes.**
>
> Series entirely absent: `KXHIGHTHOU`, `KXHIGHTLV`, `KXHIGHTMIN`, `KXHIGHTNOLA`, `KXHIGHTOKC`, `KXHIGHTPHX`, `KXHIGHTSATX`, `KXHIGHTSEA`, `KXHIGHTSFO`, `KXLOWTATL`, `KXLOWTAUS`, `KXLOWTBOS`, `KXLOWTCHI`, `KXLOWTDAL`, `KXLOWTDC`, `KXLOWTDEN`, `KXLOWTHOU`, `KXLOWTLAX`, `KXLOWTLV`, `KXLOWTMIA`, `KXLOWTMIN`, `KXLOWTNOLA`, `KXLOWTNYC`, `KXLOWTOKC`, `KXLOWTPHIL`, `KXLOWTPHX`, `KXLOWTSATX`, `KXLOWTSEA`, `KXLOWTSFO`

## Stage 1 -- oracle upper bound

- Scanned: 624 (usable 624, skipped 0, coverage 100.0%)

- Capturable markets: **3 / 624** (rate 0.481%, Wilson 95% CI [0.164%, 1.404%])
- Best (cheapest) winner cost among capturable markets, cents: min=92.0, p10=92.0, median=97.0, p90=97.0, max=98.0 (n=3)
- Mean fee-inclusive net over capturable minutes (day-clustered): 2.739c, t=2.15 over 3 days
- Volume proxy (contracts) in capturable minutes: mean=10271.83, median=605.28
  *candlestick volume_fp (contracts) summed over real (non-synthetic) candles in the last 60min whose own quoted state was capturable -- UPPER BOUND on what one participant could take; no order-book depth is visible in candlesticks*

## Stage 2 -- realistic (gated on IEM obs + the deployed lock rule, verbatim)

Not yet run / no eligible Stage-1-capturable markets found.

## Capacity -- three numbers, each labeled (read the depth caveat)

**Depth caveat**: Candlesticks give NO order-book depth. The volume traded during capturable minutes is the only size proxy available, and is an UPPER BOUND on what one participant could have taken (other participants may have been competing for or already filled that same volume).

**Oracle framing**: ORACLE CAPACITY IS A STRICT UPPER BOUND, NOT AN ACHIEVABLE NUMBER. It assumes perfect foreknowledge of the settled winner at every minute, zero detection latency, zero competition, and that 100% of the volume printed in capturable minutes was available to a single taker. No strategy can beat it and no strategy can reach it. It is a ceiling to be falsified by Stage 2, never a revenue forecast.

- **Oracle capacity — CEILING, NOT ACHIEVABLE** (Stage-1 frequency x mean net x volume proxy, perfect foreknowledge, no detection required): **$18,016.76/month**
  - same ceiling using the **median** per-market dollar figure instead of the mean: **$206.83/month**. A large gap between these two means the mean is carried by one or two high-volume markets and the point estimate is not stable.
- **Realistic capacity**: *not yet measured -- Stage 2 has not been run or produced no usable sample.*
- **Latency-adjusted capacity**: *not yet measured (depends on Stage 2).*
- Expected capturable markets across the full 2.431-month window (sample rate x population): 83.1
- Mean $ per capturable market (net x volume proxy): $527.2531

## Verdict band (interpretation frozen in the spec, not chosen post-hoc)

**INSUFFICIENT** -- no sizing verdict. The spec's three bands key off the LATENCY-ADJUSTED number, which requires a completed Stage 1 pass and a Stage 2 replay; one or both are missing. See the reasons listed above (coverage kill, partial/station-truncated Stage-1 pass, and/or Stage 2 not run). Note that 100% candlestick coverage on the markets that WERE fetched is not the same as a complete pass and does not license a verdict.

---
*This is a sizing study, not a go/no-go. No PASS bar exists. See EDGE_SIZING_SPEC.md for the frozen interpretation bands and kill conditions.*
