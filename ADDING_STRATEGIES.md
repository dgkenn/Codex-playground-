# How to add / remove / prune a strategy

The live paper-test roster is **declarative** and lives in one file: **`strategies.py`**. Everything
downstream (the collector, leaderboard, aggregation, breadth analysis) discovers variants from the
captured data, so the roster can change freely without touching any analysis code.

## Add a strategy

1. **If it reuses an existing gate** (e.g. another `micro`-based variant with a different cap/skew):
   add one line to `REGISTRY` in `strategies.py`:
   ```python
   Strat("my_variant", cap=30, skew=0.15, gate="micro", note="micro + very tight inv"),
   ```
2. **If it needs new logic** (a brand-new toxicity signal):
   - add a branch in `Variant._gate_one(self, g, ...)` in `shadow_compare.py` keyed on your gate string
     (return `True` to PULL/skip the fill), and
   - add the gate string to `KNOWN_GATES` in `strategies.py`, then add the `Strat(..., gate="my_gate")`.
   - Composite gates (OR of several) go in `Variant._gated` (see `micro_spot`, `gross_max`, `graded`).
3. Run `python strategies.py` — it prints the roster and **validates** it (duplicate names, unknown
   gate/size_mode, out-of-range params). This same check runs as a CI preflight before every collection.

## Remove / prune a strategy

Flip `enabled=False` and append the reason to its `note` — **do not delete the line**:
```python
Strat("vol_gate", gate="vol", enabled=False,
      note="PRUNED -7.9/win (gross -13.2): pull-both-in-vol-burst sheds too much rebate"),
```
This keeps the definition + params + why it failed for later re-enabling or offline study, and drops it
from the live A/B. Re-enable later by flipping the flag back. No core-file edits, no lost history.

## What makes capture robust to constant tinkering

- **Preflight validation** (`python strategies.py`) gates every run — a malformed roster fails fast
  instead of silently behaving like baseline (an unknown gate is a no-op) or wasting a ~5h run slot.
- **Per-variant error isolation** (`shadow_compare.py`): a buggy new strategy's exception is counted and
  the variant is **quarantined after 5 errors** — the rest of the roster keeps capturing. A crash in one
  module can never take down the whole window/process.
- **Self-describing data**: each run writes `gha_data/registry_<tag>.json` recording exactly which roster
  produced the data, so you can always tell what was live when a window was captured.
- **Multi-asset supervisor** (`multi_market.py`): if a market process dies mid-run it is auto-relaunched
  (bounded by `MAX_RESTARTS`, stable tag so data accumulates) — no silent market dropout over a 5h run.
- **Continuity** (`paper-collect.yml`): ~5h runs + 10-min incremental commits to the `gha-data` branch +
  workflow chain + watchdog, so collection survives container reclamation and scheduler gaps.

## The data layout (unchanged by roster edits)

- `gha_data/shadow_windows_<asset><tenor>m_r<run>.jsonl` — per-window per-variant attribution
  (each row carries `asset`/`tenor_min`/`ws` + a dict per variant).
- `gha_data/fills_*.jsonl`, `ticks_*.jsonl` — per-fill markout + (mid,spot) lead-lag series.
- `gha_data/registry_*.json` — the roster snapshot for that run.
- Analyze: `python aggregate_shadow.py` · `python leaderboard.py` · `python breadth_net_corr.py`
  · `python stack_analysis.py`.
