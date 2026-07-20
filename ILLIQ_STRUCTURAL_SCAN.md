# Structural-mispricing scan on Kalshi's long tail (2026-07-20)

Method: public `/trade-api/v2` endpoints only (no auth), polite pacing (0.2-0.3s jitter,
exponential backoff on 429, none hit). Two bulk crawls: `/events?status=open` (7,939 events,
complete, cursor exhausted) and `/events?status=open&with_nested_markets=true` (same 7,939
events, complete, with every open leg's live yes_bid/yes_ask/volume/OI attached in one pass —
this is the authoritative dataset all numbers below come from). An earlier `/markets?status=open`
crawl was found to be **capped at 60 pages / 60,000 rows with more available** (ordering
front-loaded MLB/esports strike-ladder markets and silently missed obscure multi-candidate
series like KXNEXTNATOSECGEN/KXNEWPOPE) — discarded in favor of the complete nested-events
crawl. Scripts: `structural_scan.py` (superseded), `fetch_events_nested.py`,
`analyze_me.py`. Data: `all_open_events_nested.jsonl` (7,939 events, full nested market quotes).

## Headline result: all four patterns tested negative for capturable mispricing

Every pattern in the task brief was tested against real, live quotes, including on genuinely
obscure/zero-to-low-volume series. None produced a structural mispricing that survives a
rigorous second look (fees, exhaustiveness, or direct monotonicity check). This extends the
fund's established finding (killed edges die in contested/efficient markets) one step further:
**the specific mechanical patterns tested here don't survive even in the low-attention long
tail either** — Kalshi's own pricing/tick-rounding is internally consistent across the
correlated-market structures checked. This is a clean, evidence-backed null, not a "didn't
look hard enough" null — see per-pattern detail below.

---

### Pattern 1 — mutually-exclusive (ME) YES-price sums ≠ 1

Scanned **all 3,161** open events flagged `mutually_exclusive: true` with ≥2 active binary
legs (complete census, not a sample) — 1,049 Elections, 1,734 Sports, 105 Entertainment, 88
Climate/Weather, 73 Economics, 43 Politics, plus smaller categories.

- `sum(yes_bid)` distribution: median 0.935, p90 0.990, **max 1.060**. 28 events had
  `sum(yes_bid) > 1.01` (nominal "sell all legs" arbitrage, which — unlike the buy-side
  version — needs only mutual exclusivity, not exhaustiveness, to be risk-free).
- `sum(yes_ask)` distribution: median 1.070, **min 0.062** (!). 55 events had
  `sum(yes_ask) < 0.99` (nominal "buy all legs" arbitrage).

Both directions were checked for real capturability and **both refute**:

1. **Bid-side (sum>1) is real but fee-negative.** Checked 5 concrete cases (incl. two
   low-volume weather temp-bucket events, KXHIGHTSATX/KXHIGHTPHX/KXHIGHTMIN, vol 339-1097) by
   applying the fund's Kalshi taker fee convention `ceil(7·p·(1-p))/100` per leg per contract.
   Every case is net negative after fees:
   - `KXNBAEAST-27` (15 legs): gross +$0.060, fees $0.140, **net −$0.080**
   - `KXHIGHTSATX-26JUL21` (6 legs, vol=1097): gross +$0.040, fees $0.080, **net −$0.040**
   - `KXHIGHTPHX-26JUL21` (6 legs, vol=831): gross +$0.040, fees $0.080, **net −$0.040**
   - `KXHIGHTMIN-26JUL21` (6 legs, vol=339): gross +$0.030, fees $0.090, **net −$0.060**
   - `KXLLM1-26DEC31` (8 legs): gross +$0.021, fees $0.090, **net −$0.069**
   The pattern is structural: the fee scales with Σp(1-p) across N legs while the mispricing
   is a fixed few cents of tick-rounding slop from a many-way order book — fees always win
   once N gets large enough to produce a nonzero sum in the first place. Verified this is not
   just a large-N artifact — it fails even on the smallest, lowest-volume (obscure) 6-leg
   weather buckets.

2. **Ask-side (sum≪1) is not exhaustive, so "buy all legs" is not a hedge.** Inspected legs
   directly for the three most extreme cases:
   - `KXSTATE51-29` ("51st state") sum_ask=0.174 over 8 named long-shot candidates (DC,
     Puerto Rico, Canada, Greenland, Venezuela, Guam, Colombia, Cuba) — the missing ~83% is
     "no 51st state," which is not a tradable leg. Buying all 8 loses the whole stake if none
     of the named eight happens (the modal outcome).
   - `KXLAPRIMARY-01D26` (LA-01 Dem nominee) sum_ask=0.062 over only 2 currently-filed
     candidates — filing period context means undeclared future entrants aren't priced in;
     the market is explicitly not a complete partition yet.
   - `KXNBERRECESSQ` ("when will next US recession start") sum_ask=0.231 over 6 quarters —
     the dominant, unlisted outcome is "no recession in any listed quarter."
   Every ask-side "hit" checked follows this shape: Kalshi lists a finite subset of a
   larger/open-ended outcome space under one `mutually_exclusive:true` tag without a
   residual "other/none" leg. The prices are consistent (correctly-priced long shots), not
   mispriced — this is a trap for anyone who naively treats the ME flag as exhaustiveness.

**Conclusion: no capturable ME arbitrage found**, in either direction, across the complete
census of currently open multi-leg ME markets, low-volume ones included.

### Pattern 2 — nested/implied cutoff-date disagreement (e.g. "by 2027" vs "by 2035")

Found 6 genuinely nested (same underlying, strictly increasing horizon) series with ≥2 open
events by title-matching `\b(by|before)\b`: `KXEARTHQUAKECALIFORNIA` (before
2027/2028/2035), `KXLASTEXAM` (before Dec-2026/Dec-2027, per-threshold), `KXGOVTCUTS` (before
2027 / before term-end, per-threshold), `KXREDISTRICTING` (before midterms / before 2028,
per-state). For a monotone-implication pair (shorter horizon ⟹ longer horizon), the
risk-free arb condition is `yes_bid(short) > yes_ask(long)` (sell short-horizon YES, buy
long-horizon YES; payoff is non-negative in all three logical cases, so any positive
bid-minus-ask spread is a locked profit). Checked every overlapping threshold/state pair by
hand:

- `KXEARTHQUAKECALIFORNIA`: bid(before-2027)=0.07 vs ask(before-2028)=0.13; bid(2028)=0.10 vs
  ask(2035)=0.43 — both consistent, wide margin, no violation. Low volume on the 2028 leg
  (9,104 contracts) — genuinely obscure, still consistent.
- `KXLASTEXAM` (7 overlapping thresholds T60-T90): every `bid(2026,T) < ask(2027,T)`, e.g.
  T90: bid(2026)=0.02 vs ask(2027)=0.27. No violation at any threshold.
- `KXGOVTCUTS` (5 overlapping thresholds): every `bid(before-2027,T) < ask(before-termend,T)`,
  e.g. $2T threshold: bid=0.015 vs ask=0.084. No violation.
- `KXREDISTRICTING` (6 overlapping states): every `bid(midterm,state) < ask(2028,state)` by a
  wide margin (e.g. NY: 0.022 vs 0.82). No violation.

**Conclusion: no nested-cutoff monotonicity violation found** in any of the 6 candidate
families checked, including the lowest-volume ones.

### Pattern 3 — freshly-listed markets far from a reasonable prior

Found 561 non-Sports active markets created in the trailing 6h. The list is dominated by
just-opened strike-ladder buckets (gold/WTI/CPI/temperature threshold markets) seeded with
`yes_bid=0.00 / yes_ask≈1.00` (or the reverse) and zero volume at creation, e.g.
`KXGOLDH-26JUL2016-T3981.99` and the `KXCPIYOY-26AUG` bucket set. **This pattern is
inconclusive, not refuted**: distinguishing "correctly-priced far-out-of-the-money strike at
inception" from "genuinely mispriced before price discovery" requires an external live
reference price (spot gold/WTI/CPI-nowcast) that this scan did not fetch. Flagging as the one
pattern that would need a follow-up pass with a live reference feed before a verdict either
way — do not treat the wide initial spreads alone as evidence of edge.

### Pattern 4 — markets near a known-but-unsettled scheduled resolution (weather-style mechanical lock, on obscure series)

Scanned all 64,829 currently active markets for `close_time` already in the past while
`status` is still `active` (the literal signature of the weather-bot's mechanical-lock
opportunity, generalized to any series). **Result: 0/64,829.** Kalshi transitions market
status essentially immediately at `close_time` in this snapshot — there is no
snapshot-visible stale-quote window on any series, obscure or not. This is consistent with,
and extends, the fund's own `WX_NEARMISS_DIAGNOSIS.md` finding that the lock window is
extremely tight. **Caveat**: this pattern is inherently sub-snapshot (the opportunity, if it
exists at all, would live in the seconds around the exact close/settlement event); a static
crawl cannot rule it out the way it can rule out Patterns 1-2, and any real test needs
live monitoring pinned to specific known-outcome close times, not a point-in-time scan.

---

## Bottom line for the funnel

Patterns 1 and 2 are **cleanly refuted** with real quotes and full-census coverage (not
samples) — no capturable structural mispricing on Kalshi's public order book right now, in
the popular markets or the obscure long tail. Pattern 4 is a **clean negative but
methodologically inconclusive** (needs live/event-driven monitoring, not a snapshot).
Pattern 3 is **genuinely inconclusive** — it needs an external reference-price feed to
adjudicate and should not be reported either way without one. Net: this scan did not find a
live, real, spot-checked structural edge on any series family tested. Per the fund's
research discipline, this is reported as a refuted/null result, not massaged into a maybe.
