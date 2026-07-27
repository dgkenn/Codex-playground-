# Archive — legacy documentation from earlier, unrelated projects

*Archived 2026-07-27. Nothing here was deleted; everything was moved with `git mv`, so full history is
intact and any file can be restored with a single command.*

This repository accumulated documentation from several distinct research programmes before the current one.
Those documents were interleaved with the live burst-suppression and clinical-EEG work, which made the
documentation actively misleading — `research/README.md` described a study on racial measurement bias in
clinical chemistry, and a new session reading it would have concluded that was the project.

## What is in here

| location | contents |
|---|---|
| `./*.md` | 76 documents: electrolyte measurement bias, deconfounding methodology, MIMIC/eICU trial emulation, transfusion and sepsis trial replications, RDD/instrument work, publication and portfolio planning |
| `./scripts/` | ~65 loose Python/shell/CSV files that had been sitting in `docs/`, belonging to the electrolyte and trial-emulation work |
| `./research/` | 36 numbered research documents (01–32) from the electrolyte / measurement-bias / arterial-line programmes, plus their manuscript drafts and the old `README_racial_measurement_bias.md` |

## What was kept live, and why

Anything belonging to the **burst-suppression and clinical-EEG programme** (`research/26`, `30`, `33`–`49`),
the **phenotype pipeline** it grew out of (`RUNBOOK`, `GO_LIVE`, `SPEC_TRACEABILITY`, `HANDOFF`,
`MORGOTH_INTEGRATION`, `HEEDB_*`), and the **operating protocol** for the research loop
(`RESEARCH_MACHINE`, `IDEA_GATE`, `LESSONS`, `EXPERIMENT_QUEUE`).

## Restoring something

```bash
git log --diff-filter=R --follow -- docs/archive/<file>   # find where it came from
git mv docs/archive/<file> docs/<file>                    # put it back
```

Some archived work is genuinely finished rather than abandoned — several of these lines produced completed
analyses and manuscript drafts. They are archived because they are **not this project**, not because they
are wrong.
