# How to apply these fixes to the live branch

All work is on `claude/calci-trading-bot-strategy-mgyxti` under `livefix/`. Nothing has been pushed
to the live branch (`claude/coding-bot-ab-test-results-ffmhxw`) — CLAUDE.md keeps that path
off-limits to research agents, so this is yours to apply.

## Files changed (5 + 1 new test)

| file | fix |
|---|---|
| `kalshi_exec.py` | FIX 1 — v2 order endpoint + single-book side translation |
| `kwx_forward.py` | FIX 2 — phantom-win scoring |
| `kwx_paper_gate.py` | FIX 2 — same pattern |
| `wx_forecast_model.py` | FIX 3 — `bracket_prob` interval + continuity shift |
| `wx_forecast_forward.py` | FIX 3 — `_bracket_won` derived convention |
| `livefix_selftest.py` | NEW — 28 tests, all passing |

## Apply

```bash
git checkout claude/coding-bot-ab-test-results-ffmhxw
git checkout claude/calci-trading-bot-strategy-mgyxti -- livefix/
for f in kalshi_exec.py kwx_forward.py kwx_paper_gate.py wx_forecast_model.py wx_forecast_forward.py; do
  cp livefix/$f ./$f
done
cp livefix/livefix_selftest.py ./livefix_selftest.py
python3 livefix_selftest.py     # expect: Ran 28 tests ... OK
rm -rf livefix
git add -A && git commit -m "Fix dead order endpoint (v2), phantom-win scoring, bracket floor convention"
```

## REQUIRED PRE-FLIGHT before trusting the live order path

The order path could not be exercised without credentials. Do these in order, with
`KWX_SWITCH=off` for everything except step 2, and 1 contract only:

1. **Auth against the new host.** Orders now go to `external-api.kalshi.com` while reads stay on
   `api.elections.kalshi.com`. A key/signature mismatch shows up as a **401 on the first live order**.
2. **One 1-contract live NO order, reconciled.** The `ask` leg is the dangerous one. Fire a single
   NO buy on a cheap ticker, then `GET /trade-api/v2/portfolio/positions` and confirm the position
   is **NO / short-YES, not long YES**. Nothing offline can prove Kalshi's live interpretation of
   `side="ask"`.
3. **Confirm the response shape.** Capture the verbatim 201 body; confirm the keys are literally
   `fill_count` and `average_fill_price` as strings. If renamed, `_parse_fill` returns `filled=None`,
   which flows into `kwx_runner.py:679` (`if res.get("filled") != 0:`) and marks a rung fired with
   no fill and no error.
4. **Check `fill_vwap_c`** equals the price actually paid *per NO contract* (not the YES price).
5. `get_balance()` / `/portfolio/balance` was left untouched (out of scope) — confirm that endpoint
   hasn't also moved before relying on live balance reads.

## Known residual

Post-fix bracket disagreement is **7.0%** (down from 21.9%), not zero. All 43 residual mismatches
sit in 2026-07-27..31 and are frequently >1°F from any boundary (e.g. lo=93, hi=94, realized=92) —
not an off-by-one shape. Most likely IEM ASOS revision lag on recent days (preliminary vs finalized
readings). **Re-run the derivation in ~2 weeks** once those days finalize to confirm the convention
is exact.
