# LATENCY_EDGE.md — Does Faster Execution Unlock Kalshi Crypto Up/Down? (2026-07-22)

## VERDICT (lead): **NO-EDGE-ANY-LATENCY — Option 1 (latency bot) is CLOSED**

Faster execution does not help. The speed-vs-EV curve across 1s–300s is **flat, not decaying**
— which is the signature of a market that has already absorbed the information into the fill
price *before* the fastest latency this study can measure (1s), not a market that a faster bot
could still beat. There is no sub-second, no sub-100ms, no co-location tier implied by this data
that turns the curve positive: a flat curve gives nothing to extrapolate. **This is category (c):
even infinite speed does not help. Do not build a latency bot. Option 1 is closed.**

This closes the item logged as *"Short-term crypto Up/Down temporal-arb + directional"* in
`RESEARCH_LEDGER.md` §4 (parked 2026-07-22 pending exactly this measurement).

- **Best latency tested:** 1s (fastest buildable proxy in this design; no order-book history
  exists to extrapolate below it)
- **EV at best latency:** **-1.7¢/contract** (fill-weighted per-contract mean, the honest
  estimate — see "Two constructions" below), fee `ceil(7·p·(1-p))/100` already deducted
- **Capacity:** **$0/month**
- **Infra recommendation:** **None.** Nothing to deploy. Do not extend the live taker path with
  a Kalshi order-API / WebSocket build for this purpose.

---

## 1. What was tested

Two independent re-implementations ("primary" and "curve2") of the same question: does a
model built from live Binance trade/kline data (`data.binance.vision` public klines) predict
Kalshi BTC/ETH hourly Up/Down settlement better than the Kalshi print at the moment of entry,
and does that edge survive at fill time L seconds after signal formation, for L ranging across a
six-point grid from 1s to 300s (1s, 5s, 15s, 30s, 60s, 300s)?

- Entries use **real next-trade prints at/after t+L** (not the signal-time price) — this is the
  fill-realism discipline the repo's other studies (`DATA_BACKED_BACKTESTS.md`,
  `FAVORITE_LONGSHOT.md`) established as load-bearing; fills-at-print with no order book is a
  **flattering proxy** (no spread paid), so the measured EV is an *upper bound* on real taker EV.
- Kalshi taker fee `ceil(7·p·(1-p))/100` applied at the crossing price, per repo convention.
- `curve2` additionally re-ran with a **strictly-causal** signal (underlying + vol computed only
  from bars `<= t-1`, backward-only alignment) to clear the look-ahead kill risk baked into the
  primary's original ~1s signal-formation window. Result: materially identical to the primary
  (+1.46¢ mean-of-market-means, t=0.12 vs the primary's +1.41¢, t=0.116) — the small look-ahead
  in the original design was immaterial to the conclusion.
- `curve2`'s 40 logged sample signals reproduce the raw Kalshi tape's fills/fees/PnL exactly
  (0 mismatches) — the fee and fill mechanics are verified correct in both pipelines.

## 2. Speed-vs-EV curve (fee-inclusive, real next-print fills)

| Latency L | Primary (mean-of-market-means) | Primary (fill-weighted, honest) | curve2 (independent build) | Reaches pre-registered \|t\|≥3 bar? |
|---|---|---|---|---|
| 1s | +1.41¢/ct (t=0.116, n=11,359 fills) | **-1.7¢/ct** | **-9.5¢/ct** (t=0.12) | No |
| 5s | flat vs 1s (curve does not decay) | flat vs 1s | flat vs 1s | No |
| 15s | flat vs 1s | flat vs 1s | flat vs 1s | No |
| 30s | flat vs 1s | flat vs 1s | flat vs 1s | No |
| 60s | flat vs 1s | flat vs 1s | flat vs 1s | No |
| 300s | flat vs 1s | flat vs 1s | flat vs 1s | No |

**No point on the 1s–300s grid reaches the pre-registered `|t|≥3` bar**, in either construction,
under either day-clustering scheme (see §4). The curve's defining feature is that it is **flat
across almost three orders of magnitude of latency**, not decaying from a positive value toward
zero as L grows. A decaying curve would be the signature of a real, shrinking window a faster bot
could still catch; a flat curve at ~zero-to-negative means the signal was already priced into the
fill by the time the fastest achievable proxy (L=1s) enters — the "signal" is stale information,
not a live edge with a closing door.

**Two constructions, one conclusion:** the primary study's headline "+1.41¢/contract" is a mean
of per-market-cluster means, which is not the number a trading strategy actually realizes. The
fill-weighted per-contract mean (the number that matters for capacity and for an actual
strategy's realized P&L) is **-1.7¢ at L=1s and negative at every L tested** — agreeing in sign
with curve2's independently-built -9.5¢. Both constructions agree on the only conclusion that
matters: **no capturable edge anywhere in the 1–300s window.**

## 3. Why the curve is flat, not decaying — the mechanism

The reference "Kalshi price at t" used by both studies is the **last trade print**, not a live
order-book quote. Part of the apparent model-vs-market gap in the raw (pre-fill) signal is
**print staleness**, not a genuine forecasting edge — consistent with the primary's raw ~50% win
rate and with curve2's 59-60% directional accuracy being fully absorbed by the time a real fill
happens. In other words: the model can tell you which way BTC/ETH is going slightly better than
the last stale print suggests, but by the time you can actually transact (even at the fastest
buildable proxy, 1s), the price you'd cross has already moved to reflect it. This is the same
"stale mid/last-print" artifact family that killed studies #19, #20, and #34 in the graveyard
(`RESEARCH_LEDGER.md`) — recurring here on a different axis (latency, not signal construction).

## 4. Fable adversarial verification (summary)

Independent re-implementation (curve2) reproduces the primary's headline exactly: L=1s, n=11,359
fills, +1.406¢ cluster-mean, t=0.116. A strictly-causal variant (no look-ahead) is materially
identical (+1.46¢, t=0.12) — clears the look-ahead kill risk. Fee and fill mechanics verified
correct against the raw tape (40/40 logged signals reproduce exactly).

**Two corrections applied to the primary write-up:**

1. The primary's claim of "11 distinct settlement days" is **false** — BTC and ETH markets
   share calendar days (2024-11-20/21/22), leaving only **8 distinct calendar days**.
   Re-clustered by calendar day: t=0.12–0.18 — the null is unchanged, but the primary
   overstated its independent-sample count.
2. The headline **+1.41¢/contract is a mean-of-market-means**, not a fill-weighted mean. The
   fill-weighted per-contract mean is **-1.7¢** at L=1s and negative at every L — agreeing in
   sign with curve2's independently-built -9.5¢. This is a flattering-framing correction, not a
   conclusion change (the null holds either way, and is *strengthened* by the correction).

**Remaining caveats (do not change the verdict, bound its confidence):**

- Fills are next-trade-print proxies with **no order book**: no spread is paid, so the measured
  EV is an upper bound on real taker EV — the true taker EV is likely *at or below* the negative
  point estimates reported here.
- Statistical power is limited: day-cluster SE ≈12¢/contract on 8-9 clusters can only rule out
  large edges (several cents/contract); a persistent sub-3¢ edge would be invisible to this
  design. This does not change the recommendation — a sub-3¢ edge, even if real, would not clear
  Kalshi's fee (`ceil(7p(1-p))/100`, ~2¢/side at p≈0.5 where Up/Down markets live) plus any real
  spread, so it would not be capturable regardless.
- Sample concentration: the primary spans a single Nov-Dec 2024 high-volatility regime;
  mitigated by curve2's independent 9 days spanning 2024-11 through 2026-01 reaching the same
  conclusion.
- Multiple comparisons across the 6-point L grid and threshold variants are uncorrected — moot,
  since nothing approaches the pre-registered `|t|≥3` bar even before correction.
- Capacity was never measured against real order-book depth — moot given no edge exists
  (capacity is $0 regardless of depth).

## 5. Operator recommendation

**(c) NO-EDGE-ANY-LATENCY.** Even infinite speed (theoretical zero-latency execution) does not
help here — the curve is flat, not decaying toward zero as latency shrinks, which means the
information is priced into the fill before the fastest latency this study can measure. There is
no basis in this data to claim a sub-100ms or co-located edge exists either: a flat curve gives
no extrapolable decay to project below L=1s, and the fill-at-print proxy already flatters the
strategy (no real spread paid), so real taker EV is at or below the measured negative values —
i.e., building faster execution would very plausibly find an even *more* negative EV, not a
positive one.

**Do not build a WebSocket latency bot. Do not extend the Kalshi order API / live taker path for
this purpose.** This closes the option-1 question ("is faster execution worth building?") posed
in `RESEARCH_LEDGER.md` §4's parked crypto Up/Down entry: it was a **latency + zero-sum-at-fee
wall**, exactly as the original parking note predicted from the external lead's own framing
("better execution than slower participants," "before liquidity disappears") — this study is the
first to actually **quantify** that wall (flat 1-300s curve, negative fill-weighted EV at every
point) rather than infer it.

No `latency_bot_spec.md`, no `latency_edge_repro.py`, and no `p4k_params.json` sleeve are shipped
with this study — per the pre-registered plan, those artifacts are only warranted for an
EDGE-AT-BUILDABLE-LATENCY verdict, which this is not. See `RESEARCH_LEDGER.md` §4/§6 for the
ledger update closing this item.
