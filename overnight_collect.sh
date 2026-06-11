#!/usr/bin/env bash
# RISK-FREE overnight data gathering: shadow collector ONLY (no live money). All 25 registered
# variants x 4 assets (btc/eth/sol/xrp), every 15-min window -> fills/ticks/trades/markouts.
# Auto-restarts across windows until DEADLINE. The DURABLE overnight collector is GitHub Actions
# (collect.yml commits to gha-data); this is a best-effort local supplement for this container.
set -u
cd "$(dirname "$0")"
DEADLINE=$(( $(date +%s) + ${1:-8}*3600 ))
mkdir -p overnight_data
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  python -u kalshi_collect.py 3000 overnight_data "ov$(date +%H%M)" >> overnight_data/collect.log 2>&1
  sleep 3
done
echo "$(date -u +%H:%MZ) overnight collector loop ended" >> overnight_data/collect.log
