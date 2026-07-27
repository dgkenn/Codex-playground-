# Documentation index

*Current at R392, 2026-07-27. Read `../CLAUDE.md` first — it explains what this project actually is, which
is not what the repository name suggests.*

---

## Where to start

| you want to… | read |
|---|---|
| pick up the research and keep going | **`research/49_HANDOFF_STATE.md`** |
| know what this data can and cannot settle | **`research/48_RESEARCH_LANDSCAPE.md`** |
| see every result and the constraint table | **`research/41_RESULTS_LEDGER.md`** |
| avoid repeating a known mistake | **`LESSONS.md`** (and the error catalogue in `../CLAUDE.md`) |
| pull the next experiment | **`EXPERIMENT_QUEUE.md`** |
| run something against real credentialed data | **`RUNBOOK.md`**, then `HEEDB_UNLOCK.md` |

## Live documents at this level

| document | what it is |
|---|---|
| `EXPERIMENT_QUEUE.md` | prioritised backlog, re-ranked 2026-07-27 |
| `LESSONS.md` | accumulated memory — append after every experiment, negatives included |
| `RESEARCH_MACHINE.md` | the autonomous research-loop operating protocol |
| `IDEA_GATE.md` | the idea discriminator: score and rank candidates before spending compute |
| `RUNBOOK.md` | procedure for running on real data |
| `HEEDB_UNLOCK.md` | HEEDB access, validated forward pass, preprocessing gotchas (volts vs µV) |
| `HEEDB_FAILURE_ANALYSIS.md` | what has failed against HEEDB and why |
| `MORGOTH_INTEGRATION.md` | wire-up checklist for the MORGOTH backbone; the model remains unobtainable |
| `HANDOFF.md` | handoff for the **frozen-backbone phenotype pipeline** (cold storage, not the active thread) |
| `GO_LIVE.md`, `SPEC_TRACEABILITY.md` | phenotype pipeline go-live checklist and section→code→test map |
| `GPU_ACCESS.md` | GPU availability, which gates the foundation-model work |
| `NOVELTY_EEG_FM_OUTCOMES.md` | novelty assessment for EEG foundation-model → outcome work |
| `research/` | **the live research record** — see `research/README.md` |
| `archive/` | legacy work from unrelated earlier projects — see `archive/README.md` |
| `data_gates/` | data-gate definitions |

---

## A note on the archive

On 2026-07-27 this directory held **156 markdown files and ~65 loose Python scripts**, the large majority
from unrelated earlier projects (electrolyte measurement bias, MIMIC/eICU trial emulation, arterial-line
tooling, occult hypoxaemia). They were moved to `archive/` with `git mv`, so **nothing was deleted and
history is intact**. The remaining files at this level are live.

This mattered enough to do because the old `research/README.md` described a completely different study, and
a new session reading the documentation would have been misled about what the project is.
