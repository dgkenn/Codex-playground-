# UCE — a generalizable EEG framework for preserved consciousness and cognitive capacity

**Start here:** `docs/RESEARCH_PROGRAM_BRIEF.md` — the investigator's brief, verbatim and immutable. It is the
source of authority for this project. Then `docs/RESEARCH_STRATEGY.md` for the project's own strategy, which
may be revised (revisions are logged in its §9).

**Read §0 of RESEARCH_STRATEGY.md before doing anything with UCE v1.** It establishes, by algebra alone and
before any data, that the frozen construct is approximately a one-feature model, and that the reported
"96.8 % of variance explained" is a restatement of r(frontal, posterior) = 0.936. This changes the baseline
the project must beat.

## What is real here right now

| component | status |
|---|---|
| Investigator brief, saved verbatim | done |
| RESEARCH_STRATEGY.md (Artifact 1) | done |
| Synthetic EEG with known aperiodic exponent | done, tested |
| Aperiodic exponent/offset estimator | done, **validated against known ground truth** |
| Frozen UCE v1 + its mandatory one-feature baseline | done, tested |
| Subject-level splitting, evaluation/calibration | done, tested |
| **Any real EEG dataset** | **NOT downloaded — nothing here has touched patient data** |

Nothing in `results/` is a scientific finding until a dataset is registered, downloaded under its licence, and
processed through a locked pipeline.

## Non-negotiables (from the brief)

* Never use arousal, responsiveness, cognition, command-following, prognosis or injury severity as synonyms.
* UCE v1 is frozen. New versions are new modules, evaluated independently.
* The system must be permitted to abstain.
* No protected patient data in this repository.

## Layout

```
docs/    RESEARCH_PROGRAM_BRIEF.md (immutable) | RESEARCH_STRATEGY.md | LITERATURE_MAP.md
         ANALYSIS_PLAN.md | NEXT_ACTIONS.md
data_registry/  DATASET_REGISTRY.csv
src/uce/ config, synth, features/, models/, preprocessing/, quality_control/, evaluation/
tests/   synthetic ground-truth tests -- Gate A
```

Run the suite: `cd uce && python -m pytest tests/ -q`
