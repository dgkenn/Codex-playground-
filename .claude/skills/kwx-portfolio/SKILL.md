---
name: kwx-portfolio
description: Manage the multi-sleeve portfolio — sleeve registry, stacked-edge accounting, correlation, combined caps, adding a new validated sleeve. Use for "portfolio status", "add a sleeve", "stack edges", "combined capacity", "central manager".
---

# Portfolio management (stacking edges centrally)

The fund's thesis: $4k/mo comes from STACKED, independent, individually-gated sleeves under one
central manager — not from scaling one edge. The registry of record is `p4k_params.json`'s
`sleeves` block; `kwx_portfolio.py` (shipped by the stacked-edges program; check
`STACKED_EDGES.md` for current state) is the runtime manager.

## Sleeve lifecycle (every sleeve, no exceptions)

FUNNEL (kwx-research-funnel skill) → verified corrected numbers → PAPER sleeve (forward logger +
Wilson-bar decision script, own files, no orders) → numeric activation gate passes on FORWARD
data → operator activates → registered in the shared-cap accounting.

## Portfolio-level rules

- **Shared caps**: one paper bankroll config; combined per-day deployment cap across all
  directional/paper sleeves mirrors `MAX_DAILY_DEPLOY_FRAC`; per-market dedupe against the live
  bot's plan log so two sleeves never double-count one market.
- **Correlation is measured, not assumed**: same-day signal overlap between sleeves from their
  logs; >50% overlap ⇒ halve the combined cap. Independence is why stacking works at all.
- **Speculative sleeves earn $0 in headline numbers** until their own gate passes (see
  `added_markets_kalshi` in the params for the pattern).
- **The graveyard stays registered**: refuted sleeves keep their zeroed entries + kill-report
  pointers. Deleting them invites re-proposing them.

## Status commands (verified where the module exists)

```bash
python kwx_goal_status.py                      # per-stage summary + reopen calendar
python wx_path_to_4k.py | tail -20             # combined honest ceiling
python kwx_portfolio.py status 2>/dev/null || echo "orchestrator not yet merged -- see STACKED_EDGES.md / latest batch/stacked-edges PR"
```

## Adding sleeve N+1 (checklist)

1. Funnel verdict CONFIRMED/WEAKENED-positive with Fable adversarial verification on record.
2. Paper module trio (`wx_<name>_model.py`, `wx_<name>_paper.py`, `wx_<name>_decision.py`) runs
   a real snapshot cycle.
3. Registry entry in `p4k_params.json` at honest quality with `source`.
4. Dedupe + shared-cap wiring proven (run the portfolio snapshot once, trace a dedupe hit).
5. `kwx_selftest.py` passes; PR; Fable production gate APPROVE before merge.
