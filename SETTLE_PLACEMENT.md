# SETTLE_PLACEMENT.md -- placement manifest for the settlement recorder + its workflow

**Status:** DRAFT (working-tree only; lead reviews + places + commits across branches).
**Date:** 2026-07-15
Read-only market data; public Kalshi REST only; no auth, no secrets, no orders, no live-config.

This manifest says exactly **which file goes on which branch** so that `settle-sleeves.yml`'s
checkout finds `settle_recorder.py`, and gives the exact commands the lead runs to place them.

---

## The two files and where each must live

| File | Branch it must live on | Why |
|------|------------------------|-----|
| `settle-sleeves.yml` | **`main`** (in `.github/workflows/`) | GitHub fires `schedule:` triggers **only from the default branch**. Every other sleeve workflow (`collect.yml`, `kalshi-longshot.yml`, `favlong-forward.yml`, …) lives on `main` for this reason. |
| `settle_recorder.py` | **`claude/coding-bot-ab-test-results-ffmhxw`** (repo root) | The workflow does `actions/checkout` with `ref: $BRANCH`, then runs `python settle_recorder.py …` from `$GITHUB_WORKSPACE`. So the script must exist at the repo root of whatever branch `$BRANCH` names. The workflow sets `env.BRANCH: claude/coding-bot-ab-test-results-ffmhxw`. |

**`settle_recorder.py` is ALREADY committed on `origin/claude/coding-bot-ab-test-results-ffmhxw`**
(verified: `git cat-file -e origin/claude/coding-bot-ab-test-results-ffmhxw:settle_recorder.py` →
present). So **no file move is required** — only `settle-sleeves.yml` needs to be placed on `main`.

The entry logs it reads and the `*_settled.jsonl` ledgers it writes both live on the **`gha-data`**
DATA branch — independent of the CODE branch above. The workflow fetches `gha-data` into a
`/tmp/dw` worktree, reads entry logs from it, and commits the ledgers back to it.

---

## Placement decision: `settle_recorder.py` stays on `ffmhxw` (research/ab-test branch)

**Chosen:** keep `settle_recorder.py` on `claude/coding-bot-ab-test-results-ffmhxw` and set
`env.BRANCH` to that branch (matching `favlong-forward.yml`).

**The tradeoff (ffmhxw vs. the bot branch `claude/polymarket-bot-live-ready-vw7ut5`):**

- **Bot branch `vw7ut5`** is where the four *entry-generating* sleeve scripts live
  (`kalshi_longshot_paper.py`, `kxwti_paper.py`, `macro_paper.py`, `kalshi_tailbias_paper.py`).
  Putting `settle_recorder.py` there co-locates "all sleeve tooling in one place."
  - *Cost:* `settle_recorder.py` is **not** there today, so this requires an extra
    `cp` + commit onto `vw7ut5` (one more branch to touch = more moving parts / more risk), and
    `settle-sleeves.yml` would need `env.BRANCH: claude/polymarket-bot-live-ready-vw7ut5`.

- **Research branch `ffmhxw`** already holds `settle_recorder.py` (committed), plus
  `SETTLEMENT_LOGGING_PLAN.md` and the peer read-only recorder/replay `favlong_forward.py` +
  `favlong-forward.yml` (same `BRANCH=ffmhxw`). `settle_recorder.py` is **fully standalone**
  (stdlib only; it does **not** import any sleeve script — verified), so it gains **nothing
  functional** from sitting next to the entry scripts: it reads its inputs from the `gha-data`
  branch and hits the public API, not the code branch.

**Rationale for picking `ffmhxw`:** zero file movement (it's already there), it mirrors the
proven `favlong-forward.yml` exactly (same `$BRANCH`, same "read-only recorder that commits
results" role), and co-locating on `vw7ut5` buys no functional benefit because the recorder has
no cross-imports. Fewer branches touched = lower risk. If the team later prefers all sleeve
tooling on `vw7ut5`, moving it is a one-line `env.BRANCH` change + a `cp`/commit (see below).

---

## Exact commands for the lead

### 1. Place `settle-sleeves.yml` on `main` (required)

```bash
# from a clean checkout of the repo:
git fetch origin
git switch main
git pull --ff-only

# copy the drafted workflow from the ffmhxw working tree (where this task drafted it):
git show claude/coding-bot-ab-test-results-ffmhxw:.github/workflows/settle-sleeves.yml \
    > .github/workflows/settle-sleeves.yml
# (or: cp .github/workflows/settle-sleeves.yml from the ffmhxw working tree)

git add .github/workflows/settle-sleeves.yml
git commit -m "add settle-sleeves daily settlement recorder workflow"
git push origin main
```

### 2. Confirm `settle_recorder.py` is on `$BRANCH` (should already be true — no action needed)

```bash
git cat-file -e origin/claude/coding-bot-ab-test-results-ffmhxw:settle_recorder.py \
    && echo "OK: settle_recorder.py present on \$BRANCH" \
    || echo "MISSING -- place it (see step 3)"
```

### 3. ONLY IF you instead want it on the bot branch `vw7ut5` (optional alternative)

```bash
# put the script on vw7ut5:
git switch claude/polymarket-bot-live-ready-vw7ut5
git show claude/coding-bot-ab-test-results-ffmhxw:settle_recorder.py > settle_recorder.py
git add settle_recorder.py
git commit -m "add settle_recorder.py (settlement recorder for paper sleeves)"
git push origin claude/polymarket-bot-live-ready-vw7ut5

# then, on main, edit settle-sleeves.yml:
#   env.BRANCH: claude/polymarket-bot-live-ready-vw7ut5
```

### 4. (Optional) immediate back-fill without waiting for the cron

The recorder is idempotent and read-only, so the lead can create the ledgers now:

```bash
git worktree add --detach /tmp/settle-backfill origin/gha-data
python settle_recorder.py /tmp/settle-backfill/gha_data/macro_pending.json \
    --sleeve macro --out /tmp/settle-backfill/gha_data/macro_settled.jsonl
python settle_recorder.py /tmp/settle-backfill/gha_data/kxwti_pending.json \
    --sleeve kxwti --out /tmp/settle-backfill/gha_data/kxwti_settled.jsonl
python settle_recorder.py /tmp/settle-backfill/gha_data/longshot/longshot_pending.json \
    --sleeve longshot --out /tmp/settle-backfill/gha_data/longshot/longshot_settled.jsonl
for f in /tmp/settle-backfill/gha_data/tailbias/tailbias_*.jsonl; do
  case "$f" in *_settled.jsonl) continue;; esac
  python settle_recorder.py "$f" --sleeve tailbias \
      --out /tmp/settle-backfill/gha_data/tailbias/tailbias_settled.jsonl
done
# then commit the *_settled.jsonl files to gha-data.
```

---

## Entry-log → ledger map the workflow uses (on the `gha-data` branch)

| Sleeve | Entry log read (`/tmp/dw/gha_data/…`) | Ledger written | Notes |
|--------|----------------------------------------|----------------|-------|
| macro | `macro_pending.json` | `macro_settled.jsonl` | primary fix (no working settled file today) |
| kxwti | `kxwti_pending.json` | `kxwti_settled.jsonl` | primary fix; FILLED maker quotes only |
| longshot | `longshot/longshot_pending.json` | `longshot/longshot_settled.jsonl` | parallel cross-check to existing `longshot_settled.csv` |
| tailbias | `tailbias/tailbias_*.jsonl` daily tapes (loop) | `tailbias/tailbias_settled.jsonl` | `tailbias_pending.json` is empty (`[]`) — 15-min markets finalize fast — so the durable entry log is the daily tape; recorder auto-detects JSONL and is idempotent, so all tapes replay into one ledger |

A sleeve whose entry log is absent is **skipped** (logged, workflow continues) — see the
`if [ -f … ]` / `for f in … [ -e "$f" ]` guards in `settle-sleeves.yml`.
