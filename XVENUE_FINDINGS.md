# XVENUE_FINDINGS.md — Kalshi 15m BTC vs Polymarket 5m BTC-updown

Scope: TASK 1/2/3 from the dormant-stream sweep (`cross_venue_gap.py`, `edge_verdicts.py`).
Data: shallow-fetched `origin/gha-data` (single-commit checkout, 2026-07-11), day-dirs
2026-06-10 .. 2026-07-11 (32 days).

## 1. Actual formats found (not the ones I assumed going in)

**Kalshi** (`gha_data/<day>/book_kalshi_btc15m_r*.jsonl.gz`) — one JSONL row per book
update, `type` in `{meta, book, stat}`:
```
{"type":"meta","t":1783641643.76,"ws":1783641600,"asset":"btc","tenor_min":15,
 "meta":{"ticker":"KXBTC15M-26JUL092015-15","floor_strike":63193.52,
         "strike_type":"greater_or_equal","yes_bid_dollars":"0.5400","yes_ask_dollars":"0.5500",...}}
{"type":"book","t":1783641644.14,"ws":1783641600,"spot":63195.27,
 "yes":[[0.001,61368.0],...],"no":[[0.001,58768.0],...]}   # resting-order depth, ascending price
{"type":"stat","t":1783641644.14,"ws":1783641600,"last_price":0.55,...}
```
- One market per **15-minute** window (`ws` steps by exactly 900s, confirmed across the whole
  scan: 2854 windows / 32 days ≈ 96/day = 24h × 4).
- `floor_strike` is an ATM `greater_or_equal` strike: in the sample above it's 63193.52 vs a
  concurrent `spot` of 63195.27, 44s into the window (i.e. ≈ spot at window open).
- Best yes bid = max price with size>0 in `yes[]`; best yes ask = `1 - max(price in no[])`
  (same convention as `kalshi_weather_snapshot.parse_book`'s `best()`).
- ONE `meta` row per window (confirmed: 3 windows/file → 3 meta rows/file), full order-book
  depth on every `book` row, `spot` (continuous BTC mark) on every `book` row.

**Polymarket** (`gha_data/<day>/pmkt_btc_updown_r*.jsonl.gz`) — one JSONL row per poll
(~1.3s cadence):
```
{"t":1783641642.43,"end":1783641900.0,"venue":"polymarket","asset":"btc",
 "slug":"btc-updown-5m-1783641600",
 "up_bid":0.58,"up_ask":0.61,"up_bsz":31558.1,"up_asz":33898.2,
 "down_bid":0.40,"down_ask":0.41,"up_tbsz":216.3,"up_tasz":5.0,"down_tbsz":61.4,"down_tasz":55.1}
```
- One market per **5-minute** window (`slug` epoch steps by exactly 300s — checked 8611
  windows/32 days ≈ 269/day ≈ 288 expected for 24h × 12, short days are collector-downtime
  gaps, not a format issue).
- **BTC only.** No `pmkt_eth_updown` / `pmkt_sol_updown` / `pmkt_xrp_updown` stream exists on
  any sampled day (checked 2026-06-15, 2026-07-01, 2026-07-10 explicitly, plus the full-scan
  file listing) — the context's "pmkt_btc_updown*" naming is literal, not a placeholder for a
  per-asset family.
- `up_bsz`/`up_asz` are **book-wide size sums, not top-of-book** (already documented in this
  repo's `xvenue_pmkt.py` docstring) — irrelevant to the price-gap question here but worth
  flagging again since it would badly overstate capacity if reused for sizing.

## 2. The alignment problem: SAME TIME is possible, SAME EVENT is not

Because Kalshi windows are 900s and Polymarket windows are 300s, and `900 = 3 × 300`, exactly
**1 in 3** Polymarket windows opens at the same wall-clock instant as a Kalshi window
(`slug_epoch == ws`). At that shared `t0`:
- Both markets are ATM (Kalshi's `floor_strike` ≈ spot(t0); Polymarket's up/down reference is
  implicitly spot(t0)).
- So a genuine **same-time quote comparison** is possible, and the scan below does exactly that.

But the two markets do **not** resolve at the same time:
- Kalshi settles at `t0 + 900s` (spot vs `floor_strike`, avg over CF Benchmarks).
- Polymarket settles at `t0 + 300s` (spot(t0+300) vs spot(t0)).

A 5-minute-ahead "will it go up" bet and a 15-minute-ahead "will it go up" bet sharing the same
starting reference price are **different instruments with different implied volatility /
term structure**, not two quotes on the same contract. The empirical gap distribution below
confirms this directly: the mean |gap| is **~7-9 cents, every single day**, with essentially no
day-to-day variation in sign or magnitude (mean|gap| ranges 5.9c–9.4c across all 32 days,
never near 0). A real cross-venue mispricing would show gaps that are intermittent, mean-revert
toward 0, and correlate with liquidity/latency events — not a persistent multi-cent gap present
on literally every trading day regardless of market conditions. That signature is a **structural
term-premium**, not an arbitrageable inefficiency.

Buying "whichever venue is cheaper" therefore does **not** construct a hedge — it is a single-leg
directional bet on that venue's own (different-horizon) outcome. Calling the resulting spread a
"cross-venue gap net of cost" would misrepresent directional exposure as arbitrage.

**Conclusion: (b) the incremental forward-track (`gha_data/xvenue_<date>.jsonl`) is intentionally
NOT wired up.** `cross_venue_gap.py incremental` exists as a stub that explains this and exits
non-zero rather than silently producing a file. (a), the historical scan, is still produced in
full below, both because it is directly useful evidence for this conclusion and because it is a
legitimate same-time (if not same-event) diagnostic.

## 3. Historical scan results (32 days, 2026-06-10 .. 2026-07-11)

Full machine-generated output: `gha_data/xvenue_scan.txt` (local file, not committed — see repo
convention `.gitignore: gha_data/`). Summary:

| metric | value |
|---|---|
| days scanned | 32 (2026-06-10 .. 2026-07-11) |
| total Kalshi btc15m windows | 2854 |
| total Polymarket btc-updown-5m windows | 8611 |
| windows sharing an open t0 (1-in-3 by construction) | 2813 |
| windows with a usable aligned same-time quote pair | 2757 |

Gap distribution `|P(up)_pmkt − P(up)_kalshi|` at shared t0 (cents):

| n | mean | median | stdev | p10 | p90 | p99 | max |
|---|---|---|---|---|---|---|---|
| 2757 | 7.80c | 6.00c | 6.49c | 1.00c | 17.00c | 29.00c | 45.00c |

Signed mean (pmkt − kalshi): **+0.22c**, roughly balanced (1361/2757 windows pmkt-rich) — i.e.
no persistent directional skew, consistent with a symmetric term-structure effect rather than
one venue being systematically mispriced relative to the other.

N windows with `|gap|` exceeding an assumed total round-trip cost (Kalshi ~1c spread baseline;
Polymarket cost via `fees.py`'s `taker_fee = 0.07·p·(1−p)`, swept as a flat total threshold):

| threshold | n exceeding | % |
|---|---|---|
| 1c | 2606 / 2757 | 94.5% |
| 2c | 2357 / 2757 | 85.5% |
| 3c | 2094 / 2757 | 76.0% |

This looks superficially promising (gaps routinely exceed plausible costs) — which is exactly
why the same-event-vs-same-time distinction in §2 matters: a persistent multi-cent gap that
survives on 76-95% of windows regardless of cost assumption, every day, with no mean-reversion
signature, is the fingerprint of "these are different bets," not "there is free money sitting
here."

Would-be paper P&L of "take the cheaper venue's UP ask, exit at that venue's own settlement"
(single-leg directional, **not** a hedged locked box):

| | n | mean c/contract | total c | % positive |
|---|---|---|---|---|
| all | 2757 | +1.15c | +3181.6c | 47.5% |
| chose kalshi | 1474 | −3.42c | | 40.7% |
| chose pmkt | 1283 | +6.41c | | 55.3% |

Per-day mean P&L swings from −33.00c (2026-06-11, low-n day) to +7.08c (2026-06-29), with no
consistent sign — see `gha_data/xvenue_scan.txt` for the full 31-day breakdown.

## 4. Forward-bar verdict on this data (via `edge_verdicts.py`)

Run: `python edge_verdicts.py score gha_data/xvenue_scan.txt --kind xvenue-scan`

```
n_rows=31  n_forward_days=31  null=0.0
mean/day=+0.155  stdev/day=7.397  day-clustered t=0.12  %days positive=58.1%
VERDICT: FAIL  (t=0.12 (need >=3.0), %pos=58% (need >=80%))
```

Even treating this purely as a descriptive/retrospective series (NOT a real forward
paper-track — there was no live decision rule, this is 20/20 hindsight on `take the cheaper
ask`), it fails the pre-registered bar decisively: day-clustered t is ~0, and only 58% of days
are net positive vs the required 80%. This is exactly what §2's theoretical argument predicts:
a structural term-premium centered near a small positive mean with large day-to-day noise, not
a repeatable edge. It corroborates — it does not contradict — the decision to skip (b).

## 5. Bottom line

- Formats: fully inspected, documented above and in `cross_venue_gap.py`'s module docstring.
- Same-time alignment: possible and implemented (`cross_venue_gap.py scan`), producing
  `gha_data/xvenue_scan.txt` for all 32 available days.
- Same-event alignment: **not possible** — Kalshi (15m) and Polymarket (5m) BTC markets are
  different-tenor instruments with no overlapping resolution time. This is a genuine, evidenced
  "alignment impossible" case per the task's own definition of what should be attempted.
- (b) incremental forward-tracking: **skipped**, by design, with a self-documenting stub in
  `cross_venue_gap.py incremental` rather than silently building a live series that would be
  scored as a real "edge candidate" under the pre-registered same-event bar.
