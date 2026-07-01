# Autonomous research machine — operating protocol

The standing protocol for running this repo as a 24/7, self-learning, publication-focused research
loop. Auto-loaded via CLAUDE.md. Read `docs/LESSONS.md` and `docs/EXPERIMENT_QUEUE.md` at the start of
every work cycle before doing anything else.

## Mission
Produce **ultra-high-impact, fully-validated medical-AI findings** (target tier: Anesthesiology /
Critical Care Medicine / Intensive Care Medicine and above — Nature Medicine / JAMA / Lancet Digital
Health for the strongest results). Primary asset: HEEDB (109k EEG + neuro outcomes, multi-site) via the
frozen EEG foundation model; secondary: MIMIC-IV / eICU / VitalDB / INSPIRE.

## The self-learning loop (one cycle)
1. **Orient** — read `docs/LESSONS.md` (what we know / what's been ruled out) and
   `docs/EXPERIMENT_QUEUE.md` (prioritized backlog). Never repeat a ruled-out dead end.
2. **Pick** the top-ranked open experiment from the queue that fits available compute.
3. **Run** it (delegating per the model policy below). Log raw results to `cache/` + a dated note.
4. **Red-team** the result adversarially (sonnet panel) before believing it — external validation,
   confounding, leakage, p>>n variance, novelty vs prior art.
5. **Learn** — append what was learned (positive AND negative, with the mechanism) to `docs/LESSONS.md`;
   re-prioritize `docs/EXPERIMENT_QUEUE.md`; update `docs/FINDINGS_LEDGER.md` with status.
6. **Persist** — commit + push every cycle (reaps wipe uncommitted work). Never commit PHI.
7. **Escalate or continue** — if a finding survives red-team + external validation, promote it toward a
   manuscript; else pull the next queue item.

The loop is self-learning because each cycle *reads and updates* the durable memory (LESSONS +
QUEUE + LEDGER); knowledge compounds across sessions instead of being re-derived.

## Impact bar & novelty discipline (hard-won — enforce every cycle)
- **Require external/cross-site validation.** Internal-only + observational = incremental, not top-tier.
- **Avoid already-named indices** (VIS, VDI, BPRI, HPI, SVV/PVI, augmentation index, SOFA, APACHE,
  shock index): reviewers desk-reject. Novelty must be a construct with no established literature.
- **Avoid confounded treatment-decision questions** (liberation order, dose→outcome): confounding-by-
  indication caps them at "sicker patients" unless a genuine natural experiment exists.
- **A clinical DECISION or a genuinely novel BIOMARKER beats another risk marker.**
- Every candidate: run a PubMed/prior-art novelty pre-screen BEFORE investing compute.

## Model delegation policy (cost-conscious — default to the cheapest sufficient model)
- **haiku** — mechanical/cheap: data pulls, cohort sizing, number reproduction/verification, running
  pre-written scripts, file/format checks, literature-hit triage. Use liberally; it's cheap.
- **sonnet** — substantive reasoning: adversarial red-team review, causal/stats critique, novelty/
  prior-art assessment, analysis design, failure analysis, abstract drafting.
- **opus (main loop)** — orchestration, synthesis, strategic decisions, final verdicts only.
- Rule of thumb: **if a task has a checkable right answer, use haiku; if it needs judgment, use sonnet;
  reserve opus for deciding what to do next and integrating results.** Prefer parallel sonnet/haiku
  panels over serial opus work.

## Compute awareness
- CPU is fine for tabular ML, data engineering, red-team panels, and *validating* pipelines. It is NOT
  enough for EEG foundation-model fine-tuning (see LESSONS) — queue those for a GPU environment.
- Long jobs (training, large embeds) run as background jobs with a watcher that re-invokes on completion;
  don't block the loop on them.

## Guardrails (never violate)
- **PHI / DUA:** HEEDB is credentialed. Keep raw PHI in scratchpad only; NEVER commit it (aggregate
  JSON/metrics only). Respect the DUA on where data may live.
- **Commit hygiene:** `git config user.email noreply@anthropic.com`; the required trailer; never put the
  model id in commits; commit+push every cycle.
- **Honesty:** report nulls and confounds faithfully; a killed hypothesis logged in LESSONS is a win.
- **Safety classifier:** unattended runs on credentialed data need permission rules in settings.json, or
  they will stall pending approval — set these up before long unattended loops.

## How to launch (operator)
- `/goal <objective>` — set the current thread's objective (Stop hook keeps the loop honest).
- `/loop 1h <cycle prompt>` — run the cycle on a cadence (e.g. "run the top queue experiment, red-team,
  log lessons, commit"). Omit the interval to self-pace.
- Cron for scheduled sweeps (nightly data/lit checks). GitHub PR-watch to keep analysis code green.
