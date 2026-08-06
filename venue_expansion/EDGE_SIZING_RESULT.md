# EDGE_SIZING — RESULT: retire the mechanical-lock bot (2026-08-06)

Executed against the frozen `EDGE_SIZING_SPEC.md`. **Verdict band: `under_50` → retire the live
mechanical-lock bot.** Reproduce: `edge_sizing_v2.py` (Stage 1), `edge_sizing_stage2.py` (Stage 2);
results in `out/edge_sizing_v2.json`, `out/edge_sizing_stage2.json`.

## The numbers

| | capacity, median estimator | mean estimator |
|---|---:|---:|
| **Oracle** (perfect foreknowledge — unreachable ceiling) | $2,115/mo | $45,756/mo |
| **Realistic** (deployed lock rule, no feed delay) | **$15/mo** | $327/mo |
| Latency-adjusted, 10-min feed | **$15/mo** | $327/mo |
| Latency-adjusted, 20-min feed | **$0/mo** | $0/mo |

Stage 1: 1,353 usable markets from a stratified, shuffled 1,800-market sample across all 40 weather
series → **140 capturable** (10.0% population-weighted). Capturable = the eventual winning side was
buyable ≤98c with fee-inclusive net > 0 in the final 60 minutes.

Stage 2: all 140 replayed through the deployed lock rule verbatim (135 on IEM 1-minute, 5 on
routine), 0 skipped. **Conversion: 1 of 140 (0.71%, Wilson 95% CI 0.13%–3.9%).** At a 20-minute
feed delay: **0 of 140.**

The mean estimator is ~22× the median and outlier-driven; the median is the honest number. Both
land in the same band.

## Two structural findings that matter more than the capacity number

### 1. The deployed rule cannot lock most of the opportunities — by construction

`locked_orders()` is asymmetric: on a bracket rung it can only ever lock **NO** (cap-overshoot for
HIGH markets, floor-undershoot for LOW). **It has no code path that can ever lock YES on a bracket**,
nor the "never reached the bracket" flavour of NO. So **77 of the 140 capturable markets are
structurally unlockable regardless of feed quality or latency.** Among the 63 that are even
theoretically lockable, conversion is still just **1/63 (1.6%)**.

This is a property of the rule, not of the market. A better feed does not fix it.

### 2. The one "real" instance cannot be reproduced from independent data

The KXLOWTSEA-26JUL29-T57 fire — the single verified capturable instance in the program's history,
the one I called real and worth +46c — **does not reproduce on IEM 1-minute data.**

- IEM never reports KSEA below **56.0°F** anywhere in the market's open-to-close window.
- The rule needs a sustained reading strictly below floor − margin = **56.0°F** to lock NO on T57.
- So on IEM data **the rule never fires for that market at all**.
- The bot's own log recorded `extreme_f = 55.94` — **0.06°F** below the firing threshold, and not
  corroborated by IEM.

That single instance was decided by six hundredths of a degree of disagreement between two feeds.
It is not evidence of a repeatable mechanism; it is a boundary artifact. **I previously described it
as a verified real edge instance lost to a broken endpoint. The book price and settlement were real
— the *detection* was not reproducible, and that materially weakens the claim.** The honest revision:
the endpoint bug cost us one coin-flip on a feed disagreement, not one reliable +46c capture.

## What this closes

The mechanical weather lock was the last strategy with any live claim. It now has a measured
ceiling of ~$2.1k/mo that **no strategy can reach**, a realistic capacity of **$15/mo** that
collapses to **$0** at any honest feed latency, a rule that structurally cannot address 55% of the
opportunities its own thesis identifies, and a single historical success that independent data
cannot reproduce.

Per the spec's frozen band: **retire it.** Turning it on after the endpoint fix would be operating a
bot whose measured expected value is roughly fifteen dollars a month before slippage, competition,
and depth constraints — and candlestick data carries no order-book depth, so even that $15 is an
upper bound.

## What the fixes are still for

The three live-path fixes remain worth applying, for a different reason than trading:
- The **phantom-win scoring bug** would otherwise manufacture a fake track record that reads as a
  PASS at n=30 and authorizes capital. That hazard exists whether or not the bot trades.
- The **bracket convention fix** corrects every downstream bracket study, not just this sleeve.
- The **order-endpoint migration** is a prerequisite for any future live work on Kalshi at all.

Apply them; then leave `KWX_SWITCH=off`.

---

## Addendum 2026-08-06 (evening) — two more attempts surfaced, and they strengthen the verdict

While applying the fixes I found the live branch's `kwx_exec_log.jsonl` had grown from 2 order
attempts to **4** — two more today, both again HTTP 410:

| attempt (UTC) | ticker | bot's recorded price | **true executable NO ask** |
|---|---|---|---|
| 07-30 07:58 | KXLOWTSEA-26JUL29-T57 | 52c | **52c** — real, but detection not reproducible on IEM |
| 07-30 08:59 | KXLOWTSFO-26JUL30-T59 | 97c | **100c** — phantom |
| 08-06 07:49 | KXLOWTAUS-26AUG06-B77.5 | — | **unverifiable**, zero candles within ±15 min (empty book) |
| 08-06 08:53 | KXLOWTOKC-26AUG06-B77.5 | — | **100c / briefly 99c** — phantom |

At first glance 4 attempts in 7 days looks like a much higher opportunity rate than the "1 in 3.5
weeks" I had quoted, which would argue *against* retiring. Checked against Kalshi's own book history,
it argues the opposite: **3 of the 4 attempts were at prices that were not actually available**, and
the fourth's detection cannot be reproduced from independent obs data.

The bot's `cap_c` is its own max-pay cap computed from whatever quote it saw, not a verified
executable ask. Every time we have checked it against the real book, it has been wrong more often
than right. That is a fifth independent line of evidence for the same conclusion, and it explains
the near-miss log's shape: the gate is not filtering to genuinely tradeable prices.

Both new markets were still `active` at time of check (close 2026-08-07T06:00Z), so no settlement
exists yet; the price verification does not depend on it.

**Verdict unchanged: retire.** Nothing here reopens the strategy — it removes the last reason to
think the opportunity count was being undercounted.
