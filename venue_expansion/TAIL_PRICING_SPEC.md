# TAIL PRICING — pre-registered spec (REGISTERED 2026-10-27, before any outcome is read)

## Why this, and why the idea I proposed yesterday is already dead

`WEATHER_CLOSED.md` retired 47 studies with one structural finding: **every one was an information
bet** — know the answer sooner or better than the market — and the market's forecast beats any
observation to a conclusion the forecast reached first.

I proposed post-finality market making on Kalshi crypto hourlies as the escape. **Checking the venue
killed it before a line of spec was written**, and the kill is clean:

> Kalshi `KXBTCD` product metadata: *"At the last minute before expiration, **60 RTI prices are
> collected. The official and final value is the average of these prices.**"*

Settlement is the **mean of CF Benchmarks' BRTI over the final 60 seconds**. The outcome is not
determined until the close has fully elapsed; the averaging window is placed exactly where a
"trade the determined outcome" strategy would need to operate. That is deliberate anti-gaming
design, and it means the determined-before-close property **does not exist** on this product. For
far-from-spot strikes determination does happen hours earlier, but those sit at `yes_ask = 1c` with
`yes_bid = 0` (observed directly), so there is nothing to buy — the identical wall that closed
weather.

Two further corrections to claims I made before verifying them:

- **"Maker fee is $0 on crypto" is NOT established.** Kalshi's schedule defers per-market to the
  live fee page; third-party summaries report 126 series that do charge maker fees. `KXBTCD`
  reports `fee_type: quadratic, fee_multiplier: 1` and no maker field. **This spec therefore prices
  the TAKER path only.** A maker path may be added later only against a verified fee.
- The 15-minute products (`KXBTC15M`, `KXETH15M`) exist and are in scope for a later spec, not this
  one.

## What survives, and why it is a different kind of bet

This spec asks a question that is neither an information bet nor a speed bet:

> **Are Kalshi crypto hourly tail prices systematically higher than the frequencies they realise,
> by enough to survive the executable spread and fee?**

That is the **favorite–longshot bias**: a documented, structural tendency for low-probability
contracts to be overpriced because buyers overpay for lottery tickets. Fading it requires knowing
*nothing* the market does not know. It is a **risk-premium bet**, and the weather kill does not
reach it. It may well not exist here; the bars below are frozen so a pass is believable.

The population is large enough to answer the question decisively: ~3,800–4,400 settled strike
markets **per day** on `KXBTCD` alone (counted 2026-10-24..10-27 from the live listing, which had
not finished paging at 12,000 rows).

## The executable rule — the one that has killed every prior study

Fading an overpriced longshot means **SELLING YES**. The executable sell price is the **`yes_bid`**
— equivalently, buying NO at `100 − yes_bid`. It is **never `yes_ask`**, which is the price a buyer
pays, unfillable by a seller. This exact error has invalidated work in this repo twice.

Per contract sold at `yes_bid = b` cents, with taker fee `fee = ceil(7·p·(1−p))` at the crossing
price:

```
settles NO :  net = + b − fee
settles YES:  net = − (100 − b) − fee
EV          = b − 100·f − fee        where f = realised YES rate
```

So an edge exists **iff `b − 100·f − fee > 0`**. At `b = 3`, break-even is `f ≈ 2%` before fee. The
arithmetic is unforgiving and is stated here so no result can be read loosely.

**A strike-minute with `yes_bid = 0` is UNTRADEABLE** — counted in the denominator, never priced,
never back-filled. The untradeable fraction is a reported headline, not a footnote: it is what
closed weather.

## Design — frozen

- **Universe**: all settled `KXBTCD` (BTC hourly, threshold `-T` strikes) markets with an official
  `result` of yes/no, closing in a window of **≥ 60 distinct calendar days** ending 2026-10-20.
  Outcome = Kalshi's official `result` field ONLY, never self-computed from an index.
- **Entry times, frozen**: a single observation per strike at exactly `T` minutes before
  `close_time`, for `T ∈ {5, 15, 30, 45}`. Use the **last candlestick at or before `close − T`**;
  no candle ⇒ that strike-T is UNTRADEABLE. **No "best minute" search** — that is cherry-picking
  and is forbidden.
- **Price buckets, frozen** on the executable `yes_bid b`: `{1, 2, 3, 4–5, 6–10, 11–20, 21–40}`
  cents. Buckets above 40c are reported but are not longshots and cannot produce a PASS.
- **Cluster unit = calendar day.** One large BTC move corrupts every strike in every hour of that
  day simultaneously, so the day is the only defensible cluster. Hour-clustered statistics are
  reported as a (weaker) robustness view, never as the gate.
- **Sampling**: if the full universe cannot be priced, sample **whole hours** (so every strike of a
  sampled hour is priced together, preserving the ladder) in a **seeded shuffled order (seed
  20261027), saved and never re-sorted**. Report the fraction covered. A prior study here produced
  a biased prefix by re-sorting; that must not recur.
- Reuse the batch candlestick endpoint (`GET /markets/candlesticks?market_tickers=...`) and
  `edge_sizing_v2.normalize()` for parsing.

## PASS / KILL — frozen now

Bonferroni over 7 longshot buckets × 4 entry times = **28 comparisons**; two-sided α = 0.05/28 =
0.00179 ⇒ bar is the exact Student-t quantile at p = 0.99911 on realised day-count df. **Signed**
t: a negative t clearing the magnitude is evidence for KILL, never PASS.

**PASS** requires ALL, in ≥1 bucket × entry-time cell:
1. fee-inclusive **EV ≥ +1.0c per contract sold**, on **both** equal-weight and volume-weighted
   readings
2. signed day-clustered **t ≥ the exact Bonferroni bar**
3. **n ≥ 400 priced sales across ≥ 40 distinct days**
4. **untradeable fraction ≤ 70%** in that cell
5. **≥ 50% of priced entries have non-zero traded volume** in the entry candle (a zero-volume quote
   is a doubtful fill; a prior study's headline rested on ~186 real observations out of 517)

**KILL** if, across every longshot cell: the one-sided 97.9% upper bound on EV is `< +0.2c` **in
every cell that also meets the n floor**. *(This clause is deliberately written to require the n
floor. In study #44 the KILL clause failed to fire because the noisiest, most-untradeable cell had
the widest standard error and therefore the highest upper bound — "the noisiest cell shields the
hypothesis from its own KILL clause." Conditioning on precision closes that hole.)*

**Anything else → INSUFFICIENT.**

## Mandatory anchors (each must hold or the result is void)

- **(a) Executable-side proof.** Show, on 10 hand-worked entries, that the sale price used equals
  the candle's `yes_bid` and that `yes_ask` appears nowhere in the P&L path. Assert in code that
  `100 − yes_ask` is never computed.
- **(b) No outcome conditioning.** The entry rule must be computable without the result. Assert that
  no branch of the pricing code reads `result` before the P&L step. *(My `TERMINAL_FINALITY_SPEC`
  contained an outcome-conditioned price join that, followed literally, would have produced a fake
  PASS. It was caught only because two blind builds refused to implement it.)*
- **(c) Calibration table, reported whatever the verdict.** Realised YES rate with Wilson 95% CI
  for every bucket × entry time, against the executable `yes_bid`. This is the scientific content
  of the study and must be reported even on a KILL — it is the first calibration curve this program
  will have for a non-weather product.
- **(d) Settlement provenance.** Official `result` only. Spot-check ≥20 strikes against
  `GET /markets/{ticker}` and report mismatches.
- **(e) Tail-risk disclosure.** Report the worst single day's aggregate P&L and the maximum
  simultaneous short exposure per day. Selling tails loses many small and few large; a positive mean
  with one catastrophic day is not a strategy and must be visible.

No bar in this document may move after 2026-10-27. A PASS is necessary-but-not-sufficient; the only
permitted next step is a separately-registered 1-contract live canary.
