---
name: kwx-research-funnel
description: Run a rigorous edge-research funnel for Kalshi strategies — ideate, pre-register specs, backtest, adversarially verify, ship study PRs. Use for "find a new edge", "research a strategy", "backtest an idea", "run the funnel", "is this edge real".
---

# The K-WX research funnel (how edges get found — and killed — here)

Every claimed edge in this repo went through this funnel; most died. That is the point. The
funnel's track record (2026-07-20 program): maker REFUTED, early-lock NULL, 8 directional specs
NULL, 6 expansion families → 1 weak survivor. Read `CLAUDE.md` first — its policies are binding.

## The shape (one Workflow, Sonnet workers / Fable judges)

1. **Ideate** — 3-5 parallel Sonnet agents, each pinned to a DIFFERENT mechanism angle. Feed
   every agent the graveyard (what died and why: `WX_DIRECTIONAL.md`, `wx_maker_deep_study.md`,
   `wx_earlylock_deep_study.md`, `WX_EXPANSION.md`, `WX_NEARMISS_DIAGNOSIS.md`) so nothing dead
   gets re-proposed.
2. **Select (Fable judge)** — scores candidates on: real counterparty error, backtestability NOW
   with free data at decisive n, production feasibility, independence from existing sleeves.
   Rewrites the top picks as PRE-REGISTERED specs: data, fit/validation split, exact entry/exit,
   fee-inclusive EV accounting, minimum n, pass bar — all fixed BEFORE any test data is read.
3. **Backtest (Sonnet workers)** — one agent per spec, executes it EXACTLY. Real data pulls,
   cache-then-delete, Wilson CIs + day-clustered t on the validation window only.
4. **Verify (Fable adversaries)** — paid to refute: look-ahead vs real feed latency, fit
   contamination, fee math, re-derive the t, multiple-comparisons across EVERY spec the funnel
   tested, survivorship, marketability/execution reality (would the order actually rest/fill at
   that price? — this single check killed the maker study's 22.5 claimed fills down to 2).
5. **Loop** until 2-3 survivors or the judge returns STOP. A dry funnel is a valid, publishable
   result (see `WX_DIRECTIONAL.md` for the canonical kill report format).
6. **Ship** — study doc + read-only reproduction harness (`<study>.py` + compact committed
   `<study>_data.json`, self-tests wired into `kwx_selftest.py`) + paper-only sleeve with a
   numeric activation gate. PR to the code branch. NEVER touch `kwx_runner.py`,
   `kwx_paper_gate.py`, `kalshi_exec.py`.

## Non-negotiables (each one has caught a real false positive here)

- Fee `ceil(7*p*(1-p))/100` per contract at the CROSSING price, never mid.
- Entry prices from the ask AT signal time — never best-price-in-window (killed the mentions
  family's naive +$0.316/ct → +$0.05/ct).
- Lock/deciding-condition detection must not condition on the outcome (a `ask>=98c` "lock"
  detector is the answer leaking in).
- Feed latency is part of the signal definition: IEM asos1min publishes 22-34h late (backtest
  only); MADIS ~10 min; weather.gov ~15-20 min; Synoptic ~1-5 min (verify per station).
- Zero-latency backtests are fiction — the near-miss diagnosis showed the market reprices a
  median 106 min before a conservative lock rule confirms.

## Verified reproduction commands

```bash
python wx_maker_deep_study.py --selftest      # ALL PASS
python wx_earlylock_deep_study.py | head -20  # reproduces the null verdict from committed data
./.claude/skills/run-kwx/driver.sh studies    # all of the above + goal status
```
