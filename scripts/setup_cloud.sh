#!/bin/bash
# Paste this into the Claude Code web environment's "Setup script" field.
# It installs everything the live HEEDB/BDSP pilot needs. Runs as root on
# Ubuntu 24.04 before the session starts. Network access must allow PyPI
# (default Trusted does) plus the AWS S3 domains for the run itself.
set -u

pip install --quiet \
  boto3 mne edfio numpy scipy scikit-learn pandas pyarrow statsmodels pyyaml || true

# Foundation-model forward pass (CBraMod). CPU wheels are large; allow to fail
# without blocking session start -- cli.py pass1 will report if torch is missing.
pip install --quiet torch braindecode huggingface_hub || true

# rsync/ssh are only for TUH external replication, which CANNOT run in this
# HTTP/HTTPS-only sandbox anyway; omitted on purpose.

echo "setup_cloud.sh complete"
