#!/usr/bin/env bash
# sync_data.sh -- pull the GHA-collected paper data from the dedicated `gha-data` branch into ./gha_data
# (the workflow commits data there, not the code branch, so it never clobbers code -- see paper-collect.yml).
# Run this before aggregate_shadow.py / hedge_value.py / alpha_scan.py in a fresh container.
set -euo pipefail
git fetch origin gha-data 2>/dev/null || { echo "no gha-data branch yet (no runs have committed)"; exit 0; }
git checkout origin/gha-data -- gha_data/ 2>/dev/null || { echo "no gha_data/ on gha-data yet"; exit 0; }
echo "synced $(ls gha_data/shadow_windows_*.jsonl 2>/dev/null | wc -l) window files into ./gha_data"
