---
name: kwx-capacity-model
description: Run, read, or update the path-to-$4k capacity model (wx_path_to_4k.py + p4k_params.json) — scenario bands, sleeve gates, bankroll guidance. Use for "how much can this make", "capacity model", "update the params", "should we add bankroll", "what's the ceiling".
---

# The capacity model (what the fund can actually earn)

`wx_path_to_4k.py` Monte-Carlos $/month bands per scenario per bankroll from
`p4k_params.json`. The params file is the single source of truth — the script never needs code
changes to pick up new numbers.

## Run it (verified)

```bash
python wx_path_to_4k.py            # all scenario tables + sensitivity + honest-bottom-line
python kwx_goal_status.py          # the digest-sized summary
./.claude/skills/run-kwx/driver.sh model
```

## How to read it

- Four scenarios: `conservative` (backtest-validated only), `conservative_live` (forces the
  LIVE-observed fill rate — the honest one until fires exist), `base`, `optimistic`.
- A trailing `+` on any figure = depends on at least one ASSUMED-quality sleeve gate. Never
  quote a `+` number without the caveat.
- `binding` column tells you what constraint caps that row — once it says `DEPTH_CAP`, more
  bankroll buys nothing (true from ~$500 up as of 2026-07-20; ceiling ~$1.3k/mo conservative).

## How to update it honestly

1. Every leaf in `p4k_params.json` carries `quality`: MEASURED / BACKTEST / ASSUMED. New numbers
   enter at the quality they deserve, with `source` naming the study/file that produced them.
2. A sleeve refuted or nulled by a study gets EV zeroed in ALL scenarios and its `note` pointing
   at the kill report (see the maker / early_lock / book_watch entries for the pattern). Do not
   delete the entry — the graveyard is documentation.
3. Speculative sleeves (`added_markets_*`) keep `accrual_per_day: null` gates so they can never
   auto-pass into headline numbers.
4. After any edit: `python wx_path_to_4k.py` must run clean AND `python kwx_selftest.py` must
   pass, then commit params+doc together.
5. If a future revision claims $4k/mo is reachable, re-run the judge checklist named at the
   bottom of `PATH_TO_4K.md` Stage 5 before believing it — the first draft's "$2k → $5.6k/mo"
   died on exactly that review.

## Current verdict (2026-07-20, don't quote stale numbers — re-run the script)

No scenario clears $4k/mo at any bankroll ≤ $50k with current levers. $500-$1000 bankroll
captures the whole current opportunity. The gap to $4k must come from new verified capacity
(stacked sleeves, new families/venues), which is what the funnel + portfolio orchestrator work
toward.
