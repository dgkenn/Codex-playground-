# EDGE_SIZING — pre-registered study: how big is the "wide book near close" edge really?

**REGISTERED 2026-08-06, before any measurement.** Bars frozen here; they do not move.

## Why

One verified capturable instance exists in the program's entire history: `KXLOWTSEA-26JUL29-T57`,
77 seconds before close, book 48/99 (51c wide), true NO ask 52c, settled NO → **+46c/contract** had
it filled (`FORWARD_DATA_2026-08-02.md`). Every capacity number quoted for it (~$10–100/mo) is an
extrapolation from **n=1**. This study replaces that extrapolation with a measured frequency and a
depth proxy.

## Hypothesis

Weather markets near expiry sometimes leave the eventual **winning** side buyable well below 100c —
i.e. the book has not repriced to a determined outcome. If so, the frequency × capturable size of
that pattern is the true capacity of the mechanical-lock strategy, independent of whether *our* bot
detects it.

## Design — two stages, deliberately separated

### Stage 1 — UPPER BOUND (perfect-knowledge, no obs feed required)

For every **settled** weather market (`KXHIGH*`, `KXLOW*` series) in a frozen window:

- Pull per-minute candlesticks (`yes_bid`/`yes_ask`) for the final **60 minutes** before `close_time`.
- Reconstruct the executable price of the **winning** side per minute:
  - winner YES → cost = `yes_ask`
  - winner NO  → cost = `100 − yes_bid`
- A market-minute is **CAPTURABLE** if winner cost ≤ 98c (the deployed MAX_PAY gate) and the
  fee-inclusive net is > 0: `net = 100 − cost − ceil(7·p(1−p))` cents, p = cost/100.
- Report per market: whether any capturable minute existed, the **best** (cheapest) winner cost,
  minutes-until-close at that point, and the traded volume in those minutes.

This is a strict **upper bound**: it assumes an oracle that always knows the winner. No strategy
can beat it. If the upper bound is small, everything downstream is smaller.

### Stage 2 — REALISTIC (gated on what the obs feed actually knew)

For a random sample of ≥150 Stage-1 markets that had ≥1 capturable minute, stratified across
stations and dates:

- Pull IEM 1-minute (or finest available) obs for that station/day.
- Replay the **deployed lock rule verbatim** (`venue_expansion/kwx_lock_rule.py`:
  `sustained_extreme` / `locked_orders`, MARGIN_F=1.0, sustain-3, glitch bounds).
- A market is **REALISTICALLY CAPTURABLE** iff the lock rule would have fired **before** the last
  capturable minute — i.e. we knew the answer while the price was still there.
- Report the conversion rate (realistic ÷ upper-bound) with a Wilson CI.
- **Feed-latency disclosure is mandatory**: IEM `asos1min` publishes 22–34h late, so this is a
  backtest-only measurement; a live bot needs MADIS (~10 min) or Synoptic (~1–5 min). Report how
  many realistic captures would survive a **10-minute** and a **20-minute** feed delay applied to
  the lock timestamp.

### Capacity arithmetic (report all three, label each)

- **Oracle capacity** = Stage-1 frequency × mean net × volume proxy
- **Realistic capacity** = Stage-2 conversion × the above
- **Latency-adjusted capacity** = realistic, after the 10-min feed delay
Express all as $/month at the observed market count. State the depth caveat prominently: candlesticks
give **no order-book depth**, so the volume traded in the capturable minutes is the only size proxy
available and is an upper bound on what one participant could have taken.

## Frozen parameters

- Window: settled weather markets closing **2026-05-01 .. 2026-08-04** (recent enough that the
  current market structure applies; ends before today so all are settled).
- Series: every `KXHIGH*` / `KXLOW*` series discoverable from the Kalshi series catalog.
- Outcome truth: Kalshi's **official** `result` field only. Never self-computed.
- Fee: `ceil(7·p(1−p))` cents at the crossing price.
- Capturable threshold: winner cost ≤ 98c AND fee-inclusive net > 0.
- Stage-2 sample: ≥150 markets, or all of them if fewer qualify.
- Clustering: calendar day. Report day-clustered means where a mean is quoted.

## Pass / fail — what this study is FOR

This is a **sizing** study, not a go/no-go. There is no PASS bar. The deliverable is three numbers
with confidence intervals. Interpretation is frozen now to prevent post-hoc enthusiasm:

- **Latency-adjusted capacity < $50/mo** → the mechanical lock is not worth operating; retire the
  live bot and say so.
- **$50–500/mo** → worth running the existing $10 canary once the order path is fixed, never more.
- **> $500/mo** → justifies a dedicated re-registration; still requires a live canary first.

## Kill conditions

- Candlestick coverage is absent for >40% of sampled markets → report INSUFFICIENT, do not
  extrapolate from the covered remainder without disclosing the bias.
- If Stage 1 finds **zero** capturable market-minutes, stop — Stage 2 is moot and the 52c instance
  was a singular outlier; say exactly that.
