# Forward-data review, 2026-08-02 — one real edge instance, and two urgent bugs

Re-ran the corrected analyses on everything the live branch collected since the 07-25 audit.
Data grew: forecast settled 261 → **616**, near-misses 398 → **857**, early-lock 2 → **3**, and
`kwx_forward_settled` 0 → **2** (the taker bot attempted its first-ever orders).

---

## 1. 🔴 URGENT — the live bot cannot place orders at all

Both order attempts were rejected by Kalshi with **HTTP 410**:

```
code 410  deprecated_v1_order_endpoint
"Please switch to the V2 endpoints" -> docs.kalshi.com/api-reference/orders/create-order-v2
```

`kalshi_exec.py:329` POSTs to `/trade-api/v2/portfolio/orders`. I probed that path directly: it
returns **410** (not 401), so it is dead for everyone, not an auth problem. Replacement, per the
docs: **`POST /portfolio/events/orders`** on `https://external-api.kalshi.com/trade-api/v2`, with a
different body (`ticker, side, count, price, time_in_force, self_trade_prevention_type`, fixed-point
dollar prices, single-book bid/ask side).

**Until this is migrated the bot is inert regardless of switch state.**

## 2. 🔴 URGENT — the gate is manufacturing a phantom track record

Both rejected orders were scored as *filled wins*:

```json
{"status":"live_error", "filled":null, "fill_vwap_c":null,  ...  "won":true, "pnl":0.46}
{"status":"live_error", "filled":null, "fill_vwap_c":null,  ...  "won":true, "pnl":0.02}
```

`kwx_gate_status.txt` now reads:

```
settled fires : 2   win rate: 100.0%   EV/contract: +0.240   VERDICT: ACCRUING (need n>=30, t>=3)
```

**That is a 100% win rate from zero actual fills.** The settle path keys off the requested price and
the settlement result, never checking `filled`. Its own bar is n≥30 and t≥3 — thirty rejected
orders would read as a PASS and green-light real capital on a record of nothing. Fix: score only
records with `filled > 0`, and treat `live_error` as a skip with its own counter.

## 3. ✅ One REAL, verified, capturable edge instance — the first in the program

Of the two attempts, **one was genuinely tradeable and I verified it against Kalshi's own
candlestick book history**:

**`KXLOWTSEA-26JUL29-T57`**, fire at 2026-07-30T07:58:43Z (77s before close):

| | |
|---|---|
| Last book before close (07:47:00Z) | yes_bid **0.48** / yes_ask 0.99 → **true NO ask = 52c** |
| Bot's recorded entry | **52c** — matches the real executable NO ask exactly |
| Official settlement | **`result: no`** → NO paid 100c |
| P&L had it filled | +48c gross − 2c fee = **+46c/contract** |

The market was quoting a 51c-wide spread (48/99) on an outcome already determined by observation —
exactly the mispricing the mechanical-lock thesis predicts. **The bot detected it correctly and lost
it to the dead endpoint, not to the market.**

**The second attempt was phantom**: `KXLOWTSFO-26JUL30-T59` recorded a 97c entry, but the real book
was yes_bid 0.00 / yes_ask 0.01 → **true NO ask 100c**, unbuyable. Its +$0.02 "profit" is fictional
even before the fill question. So the honest count is **1 real instance, not 2.**

### Honest scope of that instance
- **n = 1.** One verified opportunity in ~859 lock events over 13 days ≈ **0.12%**.
- **Depth unknown.** We see a 52c ask; we do not know if it was for 1 contract or 100. The order was
  never accepted, so no fill data exists. This is the binding uncertainty on any capacity estimate.
- At 1 instance/2 weeks × 46c × unknown depth, plausible capacity is **~$10–100/mo** — real, but two
  orders of magnitude below the $4k goal.
- It does **not** overturn the efficiency finding: 857 of 859 locks were at ask=100c (untradeable),
  so the market repriced first 99.8% of the time. What it overturns is the strength of the claim
  that live capture is *impossible* — it isn't, it's just rare and was until now untested because
  the execution path never worked.

## 4. Forecast sleeve — dead, now with 2.4× the data

| | 07-25 (n=261) | now (n=616, 13 days) |
|---|---|---|
| Outcomes scored against the **wrong** result | 14.2% | **21.9%** (135/616) |
| Corrected EV/contract | −0.053 | **−0.0324** |
| Day-clustered t | −3.38 | **−3.01** |
| Model Brier vs market | 0.291 vs 0.172 | **0.314 vs 0.179** |

More data, same verdict, now better powered: **significantly negative**. The model remains worse
than a constant base-rate predictor (~0.22). The bracket-floor off-by-one is still unfixed and is
corrupting a growing sample — every additional row makes the cleanup worse.

## 5. Other sleeves

- **Early-lock**: n=3 settled (needs 30). At ~0.23/day, the gate is ~120 days away. Not a live path.
- **Near-misses**: 857 total, **856 at ask=100c, 1 at 99c** (nets exactly 0 after fee). Unchanged
  conclusion — the near-miss population has no economic content.

---

## What to do, in order

1. **Migrate the order endpoint** to `POST /portfolio/events/orders` on `external-api.kalshi.com`
   (new body schema). Without it nothing else matters.
2. **Fix the phantom-win accounting** — require `filled > 0` before scoring. This is the dangerous
   one: it manufactures the exact evidence the gate uses to authorize capital.
3. **Fix the bracket-floor off-by-one** (`bracket_prob`/`_bracket_won`, inclusive floor) — it
   corrupts every bracket study downstream, not just this sleeve.
4. Then, and only then, is the "does live capture work?" question actually testable: the mechanism
   produced one verified +46c instance, and the execution path has never once functioned.

---

# UPDATE 2026-08-06 — four more days, no winners, and the forecast axis is now definitively closed

Data: forecast settled 616 → **798** (17 days), near-misses 857 → **1,206**, live fires **still 2**,
early-lock **still 3**. **The three fixes have NOT been applied to the live branch** (0 references to
the v2 endpoint or `_is_scoreable`), so the bot still cannot place an order, and
`kwx_gate_status.txt` still advertises the phantom `2 fires / 100.0% win / +0.240 EV`.

## No new opportunities

1,206 near-misses: **1,205 at ask=100c, 1 at 99c, zero tradeable.** Four more days (349 new locks)
produced no new attemptable fire. The single verified real opportunity (KXLOWTSEA at 52c, +46c)
remains **n=1 in ~3.5 weeks** — consistent with the earlier ~0.1% estimate, still far too thin to
size on.

## The forecast sleeve: killed by the market, not by its own bug

The one genuinely open question was whether the sleeve looked bad only because its own
`bracket_prob` carried the off-by-one. Re-ran it with the corrected, data-derived interval
(`lo<=X<=hi` with a ±0.5 continuity shift), re-selecting trades at the same frozen `EDGE_THR=0.15`
and scoring against Kalshi's **official** settlement at executable prices:

| | n | EV/contract | day-clustered t |
|---|---:|---:|---:|
| As-traded (buggy model) | 798 | **−0.0375** | **−4.34** (17d) |
| Counterfactual (fixed `bracket_prob`) | 607 | **−0.0363** | **−3.61** (17d) |

**Fixing the model does not rescue the sleeve.** Both arms are significantly negative, and the
as-traded arm got *more* significant with the extra data (t −3.01 → −4.34).

Brier scores confirm the mechanism:

| model (buggy) | model (FIXED) | market | constant base-rate (0.361) |
|---:|---:|---:|---:|
| 0.3173 | **0.3189** | **0.1760** | 0.2307 |

The corrected model is *marginally worse* than the buggy one, and **both are worse than always
predicting the base rate**. The market's 0.176 is in a different class. The bracket bug was a real
accounting defect worth fixing — it was never the reason the sleeve lost money. The forecast axis
is closed on its own merits, for the third independent time.

*(Method note: this counterfactual is a post-hoc re-analysis on data already read. It is
exploratory, not confirmatory — it can kill, which is what it did, but a positive here would have
required a fresh pre-registered forward test to count.)*

## Standing answer

No winners. The only live-capturable instance in the program's history is still that one 52c fire,
and the execution path that lost it is still broken until the `livefix/` changes are applied.
