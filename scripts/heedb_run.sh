#!/usr/bin/env bash
# Run a HEEDB analysis with working BDSP credentials.
#
# WHY THIS EXISTS. The sandbox injects a PLACEHOLDER AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY pair for the
# agent proxy. Static credentials in the environment outrank profile credentials in boto3's resolution chain,
# so every script silently authenticated as the stub and got 403 from the BDSP access point -- which reads
# exactly like expired credentials and is not. The real keys are in ~/.aws (profiles `default` and
# `physionet`, both valid). Removing the two stub variables lets the normal chain find them, with no change to
# any analysis script.
#
# AWS_CA_BUNDLE and HTTPS_PROXY are deliberately left alone: the proxy still carries the traffic.
#
# Usage:  scripts/heedb_run.sh python analysis/heedb_vs_guideline.py
#         BURDEN_SCOPE=max scripts/heedb_run.sh python analysis/heedb_vs_guideline.py
set -euo pipefail

if [ $# -eq 0 ]; then
    echo "usage: $0 <command> [args...]" >&2
    exit 64
fi

exec env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY "$@"
