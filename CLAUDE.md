# Claude session conventions for this repo

## Multi-agent workflow model policy (binding)

When orchestrating Workflow/agent fan-outs in this repo:

- **Workers run on Sonnet** (`model: 'sonnet'`): catalog sweeps, data harvests, backtests,
  refinement/build agents, committers — any stage that executes a well-specified task.
- **Judges run on Fable** (`model: 'fable'`): selection gates that decide where compute goes,
  adversarial verifiers that attack claimed results, and final production-readiness gates
  before anything is committed or PR'd.
- Every claimed positive result (an edge, an EV number, a capacity estimate) must pass a
  Fable adversarial verification stage before it is treated as real. A refuted or null
  result is a fine, useful answer — report it as such.

## Research discipline (established by the 2026-07-20 program)

- Pre-register success bars before reading test data; never move goalposts after results.
- Strict fit/validation separation; day-clustered stats; Wilson CIs; multiple-comparisons
  corrections that account for every spec tested in a funnel.
- Kalshi taker fee `ceil(7*p*(1-p))/100` per contract in all EV math.
- The mechanical-lock live path (`kwx_runner.py`, `kwx_paper_gate.py`, `kalshi_exec.py`)
  is off-limits to research agents: studies ship as docs + read-only reproduction
  harnesses + paper-only sleeves with numeric activation gates.
- Key context docs: `PATH_TO_4K.md` (goal recalibration), `WX_NEARMISS_DIAGNOSIS.md`,
  `wx_maker_deep_study.md`, `wx_earlylock_deep_study.md`, `WX_DIRECTIONAL.md`.
