#!/bin/bash
# SessionStart hook — make a freshly-provisioned container able to run this repo's tests.
#
# WHY THIS EXISTS. A container was reclaimed mid-session on 2026-07-30 and came back with numpy, scipy, mne
# and boto3 present (they are in the image) but h5py, pytest, scikit-learn and statsmodels GONE. Every commit
# survived; the environment did not. `bsde/pyproject.toml` declares those extras correctly and nothing was
# installing them, so the repo could not run its own test suite until someone noticed and pip-installed by
# hand. That is a silent, recurring tax on every future session and this hook is the fix.
#
# DESIGN NOTES
#   * Remote-only. Local machines have their own environments and this must not touch them.
#   * Idempotent. pip is a no-op when a package is already satisfied, so re-running costs a few seconds.
#   * Synchronous, deliberately. Async would start the session sooner but introduces a race: the agent can
#     reach for pytest before pip has finished. Given the whole point is "the tests can run", losing that
#     guarantee to save thirty seconds is the wrong trade.
#   * The heavy ML stack in requirements.txt (torch, torchaudio, braindecode, huggingface_hub) is NOT
#     installed. It belongs to the frozen phenotype pipeline, which CLAUDE.md describes as a working asset in
#     cold storage rather than the active thread, and it would add gigabytes and minutes to every session.
#     Install it by hand if that pipeline is ever resumed.
#   * The credential bootstrap runs LAST and its failure is non-fatal: credentials are supplied by the
#     environment's settings, not by this repo, and a session with no S3 access is still a usable session.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# --- what the bsde test suite needs -----------------------------------------------------------------
#   h5py    the Chennu adapter: all 80 EEGLAB .set files in that deposit are MATLAB v7.3 (HDF5)
#   pytest  the bsde suite is pytest; the legacy suite is unittest and needs nothing
#   scipy / mne  already in the image, listed so a thinner image still works
# --- what the LEGACY suite needs, per CLAUDE.md's `make test` -----------------------------------------
#   scikit-learn, statsmodels, pyyaml
python -m pip install --quiet --disable-pip-version-check --root-user-action=ignore \
  h5py pytest scipy mne scikit-learn statsmodels pyyaml 2>&1 | tail -2 || {
    echo "[session-start] pip install reported a problem; continuing so the session still starts" >&2
}

# --- report what is actually importable, so a gap is visible at session start rather than mid-task ----
python - <<'PY'
import importlib.util
missing = [m for m in ("numpy", "scipy", "mne", "h5py", "pytest", "sklearn", "statsmodels", "boto3")
           if not importlib.util.find_spec(m)]
print(f"[session-start] python deps: {'ALL PRESENT' if not missing else 'MISSING ' + ', '.join(missing)}")
PY

# --- credentials last, and never fatal ----------------------------------------------------------------
bash "$PROJECT_DIR/scripts/bdsp_bootstrap.sh" 2>&1 | tail -2 || true
