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

## Skill suite (the fund's operating manual — `.claude/skills/`)

Eight skills cover the whole workflow; each SKILL.md contains only commands verified in a real
session. Invoke by slash command or let them auto-load:

| Skill | Use it when |
|---|---|
| `/run-kwx` | Health-check or drive the bot: smoke, status, model, feed, digest, trial, studies. The committed driver is `.claude/skills/run-kwx/driver.sh`. |
| `/kwx-research-funnel` | Hunting a new edge: ideate → pre-register → backtest → adversarially verify → ship study PR (Sonnet workers / Fable judges). |
| `/kwx-study-audit` | Any positive result appears: the 10-point refutation checklist that has killed every false edge here. |
| `/kwx-deploy-gates` | Money decisions: stage ladder, numeric gates, kill criteria, halt switch. |
| `/kwx-capacity-model` | "What can this earn": run/read/update `wx_path_to_4k.py` + `p4k_params.json` honestly. |
| `/kwx-feeds` | Obs-feed work: Synoptic credentials, probes, latency trial, per-station quality. |
| `/kwx-portfolio` | Stacking sleeves: registry, shared caps, correlation, adding sleeve N+1. |
| `/kwx-incident` | Fleet trouble: leg outages, git races with the bot, halt states, log pollution. |

New-session quickstart: `./.claude/skills/run-kwx/driver.sh smoke`, then `python
kwx_goal_status.py`, then read `PATH_TO_4K.md`'s GOAL RECALIBRATION before proposing anything. Also reads RESEARCH_LEDGER.md for the full state of what's been tested.

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
