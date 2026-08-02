# LIVE-PATH FIX SPEC (three defects) — implement exactly; diagnosis is done, do not re-diagnose

These are REAL-MONEY live-path files, copied from the live branch into `/home/user/Codex-playground-/livefix/`
(kalshi_exec.py, kwx_forward.py, wx_forecast_model.py, wx_forecast_forward.py, kwx_runner.py,
kwx_paper_gate.py). **Edit them in place under `livefix/` ONLY.** Do not commit, push, or switch
branches. The operator applies them to the live branch afterwards.

Verified diagnosis: `venue_expansion/FORWARD_DATA_2026-08-02.md`.

---

## FIX 1 — DEAD ORDER ENDPOINT (kalshi_exec.py) — highest risk

`_post_order` (~line 326) POSTs to path `/trade-api/v2/portfolio/orders`, built as
`self.base.replace("/trade-api/v2","") + path`. That endpoint now returns **HTTP 410**
`{"code":"deprecated_v1_order_endpoint"}` for everyone (verified by direct probe). Both of the
bot's real order attempts died this way.

**Verified v2 contract** (docs.kalshi.com/api-reference/orders/create-order-v2, fetched 2026-08-02):

```
POST https://external-api.kalshi.com/trade-api/v2/portfolio/events/orders

REQUEST (fixed-point values are STRINGS):
  ticker                      string
  side                        "bid" (= buy YES) | "ask" (= sell YES)     <<< SINGLE BOOK
  count                       string, fixed-point 0-2 dp, e.g. "1"
  price                       string, fixed-point DOLLARS up to 6 dp, e.g. "0.5600"
  time_in_force               "fill_or_kill" | "good_till_canceled" | "immediate_or_cancel"
  self_trade_prevention_type  "taker_at_cross" | "maker"    <<< REQUIRED, absent in old API
  client_order_id             string (optional — keep it)

RESPONSE 201:
  order_id string; fill_count string; remaining_count string; ts_ms int;
  client_order_id?; average_fill_price? (string DOLLARS, present iff fill_count>0);
  average_fee_paid? (string dollars, present iff fill_count>0)
```

### *** THE CRITICAL SEMANTIC TRANSLATION — an inversion here places the OPPOSITE trade ***

v2 is **single-book on YES**. There is no `no_price` field. The old API expressed a NO buy as
`{action:"buy", side:"no", no_price:P}`. In v2:

```
buy YES at P cents  ->  side="bid",  price = P/100         e.g. P=52 -> "0.5200"
buy NO  at P cents  ->  side="ask",  price = (100-P)/100   e.g. P=52 -> "0.4800"
```

Algebra (verify it yourself and leave it as a comment): buying NO at q pays `+(1-q)` if NO and
`-q` if YES; selling YES at p pays `+p` if NO and `-(1-p)` if YES; equal iff `p = 1-q`.

This bot only ever **buys**, so: side "yes" → `"bid"` at P; side "no" → `"ask"` at 100−P.
Never emit `action` / `type` / `yes_price` / `no_price` to v2.

### Also required

- The signature path passed to `self._headers(...)` MUST be the exact new path
  `/trade-api/v2/portfolio/events/orders` (signing a stale path yields 401s).
- The order host differs from the read host. Add a module-level
  `ORDER_BASE = "https://external-api.kalshi.com/trade-api/v2"` (env-overridable
  `KALSHI_ORDER_BASE`); keep existing `KBASE` for public reads. Build the order URL from
  `ORDER_BASE`, not from `self.base`.
- **Fill parsing** (response shape changed; see `_parse_fill` and callers ~lines 300–322):
  `filled = float(fill_count)`; fill VWAP cents = `round(float(average_fill_price)*100)` when
  `fill_count > 0`.
  *** VWAP SIDE-TRANSLATION: `average_fill_price` is a **YES** price. If we bought NO
  (side="ask"), the price we effectively paid per NO contract is `1 - average_fill_price`.
  Convert back so `fill_vwap_c` stays denominated in the side we bought — every downstream P&L
  calculation assumes that. ***
- Preserve every safety property: `_submit_guarded` remains the single chokepoint, `_guard` still
  runs immediately before the POST, `HALT_FILE` still blocks, dry-run still simulates without
  POSTing, the bounded retry still routes through `_submit_guarded`.
- Refuse to build an order whose translated price falls outside `(0,1)`.

---

## FIX 2 — PHANTOM-WIN SCORING (kwx_forward.py, ~line 70)

Current guard: `if p.get("filled") == 0:` → `n_zero_fill += 1; continue`

A **rejected** order has `"filled": null` (None). `None == 0` is False, so it slips past the guard,
is then priced at `cap_c` (~line 84), and scored as a **WIN**. That is how `kwx_gate_status.txt`
came to read `settled fires: 2, win rate 100.0%, EV/contract +0.240` from **zero actual fills** —
against a gate whose bar is n≥30 and t≥3, meaning 30 rejections would read PASS and authorize
real capital.

**Fix:** score only records representing a REAL fill. Skip (counted separately) any record where
`filled` is None / not a number / ≤ 0, **or** whose `status` is a non-fill status (`"live_error"`,
`"blocked"`, anything not indicating a fill). Add an `n_unfilled` counter distinct from
`n_zero_fill`, and surface BOTH in this module's status/report output so an operator sees
"2 attempted, 0 filled" rather than silence.

Also make the entry-price fallback safe: if `fill_vwap_c` is None for a record that somehow reaches
scoring, **skip** rather than falling back to `cap_c` — `cap_c` is a requested cap, never an
achieved price.

Check `kwx_paper_gate.py` for the same pattern and fix identically if present.

---

## FIX 3 — BRACKET FLOOR OFF-BY-ONE (wx_forecast_model.bracket_prob, wx_forecast_forward._bracket_won)

`_bracket_won` uses `floor < X <= cap`; `bracket_prob` uses `cdf(hi)-cdf(lo)` to match. Measured
against Kalshi's **official** `result` field this mis-scores **21.9% of a 616-row sample** (135
rows), every one the same shape: `realized == lo`, sleeve says NO, Kalshi says YES. So Kalshi's
bracket **includes its floor**.

**Do NOT guess the convention for other rung shapes — DERIVE it from data:**

- Read `venue_expansion/paper2/wx_forecast_settled.jsonl` (616 rows; has lo/hi/realized) and
  `venue_expansion/cache/official_results.json` (ticker → official result, already fetched).
- For each candidate convention, per rung shape (full bracket = both bounds; top rung = hi None;
  cap-only = lo None), compute the disagreement rate vs official. Candidates at minimum:
  - full bracket: `lo<X<=hi`, `lo<=X<=hi`, `lo<=X<hi`
  - top rung: `X>lo`, `X>=lo`
  - cap-only: `X<=hi`, `X<hi`
- Pick the minimum-disagreement convention per shape and **report the table**. Implement the winner.
  If a shape has fewer than 20 rows to distinguish, keep current behaviour and say so.
- Fix `bracket_prob` to be the probability of exactly the implemented interval. For whole-degree
  data an inclusive floor means the mass at `lo` counts — use a half-degree continuity shift
  (CDF boundaries at `lo-0.5` / `hi+0.5`) and **document the choice**. Check adjacent rungs neither
  double-count nor leave a gap.
- Report the post-fix disagreement rate; it should drop to near zero.

---

## TESTS (required) — `livefix/livefix_selftest.py`

At minimum:

- v2 body: buy YES 52c → `{"side":"bid","price":"0.5200"}`; buy NO 52c → `{"side":"ask","price":"0.4800"}`;
  `count`/`price` are STRINGS; `self_trade_prevention_type` present; no `action`/`type`/`yes_price`/`no_price` keys.
- Signing path is the new path.
- Fill parse: `fill_count="1"`, `average_fill_price="0.4800"` on a **NO** buy → `filled=1`, `fill_vwap_c=52`.
- Dry-run never POSTs; HALT_FILE blocks; guard runs before POST.
- kwx_forward scoring: `filled=None` → NOT scored; `filled=0` → NOT scored; `status="live_error"` →
  NOT scored; `filled=1` with `fill_vwap_c` → scored correctly, both win and loss.
- The exact two real rejected records in `venue_expansion/paper2/kwx_forward_settled.jsonl` produce
  **ZERO** scored fires.
- `_bracket_won` under the derived convention: the known case (lo=81, hi=82, realized=81) → YES.

Run it; ALL must pass. Report the verbatim tail.
