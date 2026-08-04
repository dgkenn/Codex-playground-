# Running this research programme on your own machine

*Written 2026-08-04 for the transition off the Claude Code sandbox. Everything below was verified on the
sandbox at the time of writing — version numbers, test counts and failures are measured, not assumed.*

**Branch: `research`.** All research history lives here. `main` and
`claude/heedb-eeg-phenotype-discovery-2mnwzx` are unchanged; nothing was deleted.

---

## 0. Read this first, in this order

1. **`CLAUDE.md`** — the guide for anyone (human or model) working in this repo. Its first section
   explains that the repo's name and oldest documents are misleading, and which of the ~200 documents are
   actually live. **Read it top to bottom before touching anything.** Its error catalogue (97 numbered
   rules, each paid for with a wrong result) is the single most valuable artefact here.
2. **`bsde/docs/MASTER_PLAN.md`** — the plan for the active project.
3. **`bsde/docs/DECISIONS_2026_08_02_LINES_AND_BLOCKERS.md`** — which lines are running, which are
   abandoned and why, and what is blocked on you.
4. This file, for the mechanics.
5. **`bsde/docs/EXTRACTION_TAKEOVER.md`** — the paused extraction: exactly where it stopped, the
   one-command resume, and the optimisations ranked by measured benefit.
6. **`PROMPT_FOR_LOCAL_SESSION.md`** — two prompts to paste into Claude Code locally: one to take
   over and tune the machine, one for the standing research loop.

## 1. What is actually in this tree

Three threads, only two of them live:

| path | what it is | status |
|---|---|---|
| `bsde/` | **Brain-State Discovery Engine** — the active project. Registered experiments, the verifier, the governance ledger. | **live** |
| `analysis/`, `docs/research/` | The burst-suppression / clinical-EEG programme on HEEDB, I-CARE, VitalDB. 418 logged results. | **live, not being extended right now** |
| `cli.py`, `common/`, `guards/`, `pipeline/`, `phase2/` | The original pre-registered phenotype-discovery pipeline with the held-out firewall. Tested and working. | **cold storage** |
| `health_check.py`, `test/`, `vitaldb_aki/`, most of `.github/workflows/` | **Not part of this project** — trading workflows and unrelated code. Only `.github/workflows/eeg-phenotype-tests.yml` is ours. | ignore |
| `docs/` (156 files) | Mostly legacy from unrelated earlier projects. `CLAUDE.md` lists the ~8 that are current. | mostly legacy |

Nothing was pruned when this branch was made. If you want a research-only tree:

```bash
git rm -r --cached health_check.py test vitaldb_aki      # then delete locally and commit
# keep .github/workflows/eeg-phenotype-tests.yml; the others are trading workflows
```

## 2. Hardware and OS

**Use Linux, or WSL2 on Windows.** The toolchain is POSIX throughout — `scripts/heedb_run.sh`,
`scripts/checkpoint_loop.sh`, and the `setsid … nohup … & disown` pattern every long extraction uses.
Windows-native will fight you for no benefit.

| resource | needed | why |
|---|---|---|
| **Disk** | **200 GB+ free**, and 500 GB is comfortable | A full VitalDB waveform pass is ~55 GB (9.4 MB per EEG track × 5,870 cases). The HEEDB OMOP condition table alone is 3.3 GB. |
| RAM | 16 GB works; 32 GB is comfortable | The 3.3 GB OMOP table is the largest single object. |
| CPU | any modern 8-core | Every extraction is **network-bound**, not compute-bound — measured at ~800–1,000 windows/min against ~11 windows/sec/shard of DSP capacity. More cores buy very little. |
| GPU | **not used** | Nothing in the programme is GPU-bound: Welch PSDs, Lempel-Ziv, AUCs, permutation nulls. Only a future deep-learning direction would change this. |
| Network | matters more than the CPU | This is the actual bottleneck. |

## 3. Install

Python **3.11** (3.10+ per `bsde/pyproject.toml`; 3.11.15 is what the sandbox ran).

```bash
git clone -b research https://github.com/dgkenn/Codex-playground-.git
cd Codex-playground-
python3 -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt          # the full scientific stack
pip install -e 'bsde[io,dev]'            # the BSDE package, its IO extras and pytest
```

`requirements.txt` pins `torch==2.5.1` / `torchaudio==2.5.1` for the frozen-backbone phenotype pipeline.
**You do not need those for the active research.** If you want a lighter install, drop the torch,
torchaudio, braindecode and huggingface_hub lines — the cold-storage pipeline is the only thing that uses
them.

## 4. Verify the install

```bash
make test-integrity        # stdlib only, no deps needed
python3 -m pytest bsde/tests -q
```

Measured 2026-08-04 on the sandbox:

- `make test-integrity` — **31 tests, all pass**, 0.17 s.
- `pytest bsde/tests` — **472 passed, 2 failed, 6 skipped** in 86 s.

**The two failures are pre-existing, unrelated to current work, and you should expect them.** Do not
treat them as a broken install:

1. `test_candidate_registry.py::test_every_seeded_candidate_is_computable_on_synthetic_eeg` —
   `alpha_peak_hz_wide` returns NaN on the test's clean synthetic EEG. This is a real, understood defect
   in the peak estimator (E237/E239 measured it inventing peaks in ~90 % of pure-noise draws, and a
   prominence gate takes that to 0.020). Fixing it changes every result that rests on peak availability,
   which is why it has not been quietly fixed.
2. `test_remote_zip_chennu.py::test_zip64_eocd_locator_raises_not_implemented` — a Zip64 guard in the
   Chennu remote-zip reader no longer raises. Affects only that deposit's loader.

## 5. Credentials

**VitalDB — the deposit the current work uses — needs no credentials at all.** It is a fully public API
(`https://api.vitaldb.net`). You can run everything in §6 with no secrets.

For the credentialed deposits (HEEDB, I-CARE, MORGOTH, PhysioNet DUA projects), see
**`docs/CREDENTIALS.md`**. On your own machine the sandbox-specific advice there simplifies:

```bash
# ~/.aws/credentials  — mode 600, NEVER in the repo
[default]
aws_access_key_id = AKIA...
aws_secret_access_key = ...
[physionet]
aws_access_key_id = AKIA...
aws_secret_access_key = ...
```

```bash
# ~/.netrc  — mode 600, for physionet.org over HTTPS
machine physionet.org login <user> password <password>
```

**Never commit a credential. This GitHub repository is PUBLIC — every push is a public disclosure.**
Patient-derived data must stay in gitignored paths.

Two sandbox-only workarounds you can drop locally:

- **`scripts/heedb_run.sh`** exists because the sandbox injects placeholder `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY` values for its proxy, which outrank `~/.aws/credentials` in boto3's resolution
  chain and produce a 403 that reads exactly like an expired key. On your machine there is no stub, so
  `python analysis/x.py` works directly. The wrapper is harmless either way.
- **Port 22 is blocked on the sandbox**, which is why TUH could never be pulled. Your machine has no such
  block — but note `CLAUDE.md`'s finding that TUH ships **no linked outcome data**, so it cannot replicate
  any outcome association regardless.

## 6. What is running right now, and how to resume it

The active experiment is **E248** (registered; see
`bsde/src/bsde/experiments/e248_agent_leakage_at_scale.py` for its full pre-registration). Its pipeline,
in order, with every step resumable and de-duplicating on its key:

```bash
# 1. Ventilation-state probe over all eligible VitalDB cases (~2 h; DONE, output committed)
for k in 0 1 2 3; do
  python3 bsde/scripts/vitaldb_ventilation_probe.py --all --shard $k --of 4 \
    --out bsde/results/vitaldb_vent_probe.s$k.csv &
done; wait

# 2. Derive the landmark rule from the probe's distributions, then apply it (DONE, output committed)
python3 bsde/scripts/vitaldb_vent_landmarks.py --report          # prints the distributions
python3 bsde/scripts/vitaldb_vent_landmarks.py --measure-runs 60 # derives the sustain
for k in 0 1 2 3; do
  python3 bsde/scripts/vitaldb_vent_landmarks.py --emit --sustain-s 120 \
    --out bsde/results/vitaldb_vent_landmarks.s$k.csv \
    --plan bsde/results/vitaldb_ventwin_plan.s$k.json --shard $k --of 4 &
done; wait
python3 -c "import json,glob; p={};
[p.update(json.load(open(f))) for f in sorted(glob.glob('bsde/results/vitaldb_ventwin_plan.s*.json'))];
json.dump(p, open('bsde/results/vitaldb_ventwin_plan.json','w')); print(len(p),'cases')"

# 3. EEG feature extraction on that plan  <-- IN PROGRESS, ~22k of 56,731 windows done
for k in 0 1 2 3; do
  python3 bsde/scripts/stream_vitaldb_transitions.py \
    --plan bsde/results/vitaldb_ventwin_plan.json \
    --out bsde/results/vitaldb_ventwin.s$k.csv --case-shard $k --of 4 &
done; wait

# 4. The analysis. Smoke-test FIRST (permutes the arm label; reveals nothing, writes no report).
cd bsde/src
python3 -m bsde.experiments.e248_agent_leakage_at_scale --smoke
python3 -m bsde.experiments.e248_agent_leakage_at_scale
```

**Step 3 is PAUSED at 35,988 of 56,731 windows** (35,679 ok, 305 legitimate device-disconnected
errors, 1,654 of 2,608 cases touched). Re-running the command resumes it — see
`bsde/docs/EXTRACTION_TAKEOVER.md` for the state in detail and for how to raise the shard count safely.

## 7. What changes for the better on your machine

The sandbox has one dominant tax that simply disappears locally:

**The container rolls the working tree AND `.git` back to a fixed old commit, roughly every 90 minutes.**
It happened **four times** on 2026-08-04 alone, each time killing every background job and deleting
everything uncommitted. `CLAUDE.md` rule 38 documents the diagnosis and recovery; the mitigations exist
only because of it:

- **`scripts/checkpoint_loop.sh`** commits and pushes in-flight extraction output on a timer. **You do
  not need this locally.** It is not harmful, just unnecessary.
- The obsessive commit-and-push-after-every-artifact discipline is a response to the same thing. Keep the
  *habit* — it is good practice and the ledger depends on it — but the urgency drops.
- `/tmp/eeg_probe/` is described throughout the docs as ephemeral and precious. Locally it is neither.
  **Point the caches somewhere durable**: the extraction scripts take explicit `--out` paths, and
  `analysis/heedb_omop_extract.py` takes `OMOP_OUT`.

Also gone: the disk allowance ceiling (the sandbox had ~20 GB free, which is why every VitalDB design ran
a cheap numeric-track probe before committing to a waveform pull), and the blocked port 22.

**What does *not* change: token cost.** `CLAUDE.md`'s standing SOP says research here is token-expensive
and has come close to the weekly cap. Running Claude Code on your own machine calls the same API. The
delegation table in `CLAUDE.md` (opus orchestrates, sonnet red-teams, haiku does mechanical work) still
applies.

## 8. The gotchas that cost hours here

All of these are in `CLAUDE.md`'s error catalogue, but these are the ones that bite during setup:

- **VitalDB's API gzips its responses regardless of `Accept-Encoding`.** Decompress explicitly or you
  will parse binary garbage and get plausible-looking wrong row counts. `bsde/src/bsde/ingestion/vitaldb.py`
  `_fetch()` handles it; copy that, do not write your own.
- **The `/cases` endpoint begins with a UTF-8 BOM**, which silently renames the first column to
  `﻿caseid`. Decode with `utf-8-sig`.
- **`BIS/BIS` emits a literal `0.0` when the sensor is detached**, and 0 is inside the index's valid
  range. Validity is a **positive** test on `BIS/SQI > 0`, never a ban on the value 0.
- **`mne` reads EDF in volts; the models expect µV** (×1e6).
- **Never use `hash()` for seeding** — Python salts string hashes per process and it silently breaks
  reproducibility only on the randomised paths.
- **Never use WebFetch/WebSearch for a bibliographic record or a file manifest.** Use NCBI E-utilities or
  the real API with `curl`/`urllib` and parse it yourself. This project has had six fabricated citations
  and one fabricated file manifest, and the fabrications that agreed with the hypothesis were the ones
  that survived review.

## 9. Conventions you must keep

- **Every analysis script carries its pre-registration in the module docstring**, written and committed
  *before* the result exists. This is the project's core integrity practice.
- **Register before running**: `bsde/governance/registry_ledger.py` appends to an append-only JSONL
  ledger and refuses any challenge letter that is not one of the three briefed ones.
- **Smoke-test on permuted labels, never real ones** (rule 26). Every recent experiment has a `--smoke`
  flag that does exactly this and refuses to write a report.
- **Heavy dependencies are imported lazily**, inside functions, so the integrity core imports and tests
  with the stdlib alone. Keep it that way.
