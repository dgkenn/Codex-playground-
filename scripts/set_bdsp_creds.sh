#!/usr/bin/env bash
# Durable BDSP/HEEDB AWS credential setup.
#
# WHY THIS EXISTS: the container's AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars are
# agent-proxy placeholders (14 chars), NOT real AWS keys, and they SHADOW any profile in
# boto3's credential chain. ~/.aws/credentials is also wiped whenever the container resets.
# This script writes the profile AND neutralizes the shadowing env vars for the session.
#
# USAGE (never paste secrets into chat; run this in a terminal):
#   bash scripts/set_bdsp_creds.sh AKIA...YOURKEYID  wJalr...YOURSECRET
#
# For TRUE durability across container restarts, also set these two values in the
# Claude Code web environment's secret/env configuration, so every new session gets them.
set -euo pipefail
KEY_ID="${1:?usage: set_bdsp_creds.sh <access_key_id> <secret_access_key>}"
SECRET="${2:?usage: set_bdsp_creds.sh <access_key_id> <secret_access_key>}"

mkdir -p ~/.aws
# write BOTH [default] and [physionet]: repo code (pipeline/stream_fetch.py, cli.py) uses
# profile_name="physionet"; plain boto3.client() calls use [default].
cat > ~/.aws/credentials <<EOF
[default]
aws_access_key_id = ${KEY_ID}
aws_secret_access_key = ${SECRET}

[physionet]
aws_access_key_id = ${KEY_ID}
aws_secret_access_key = ${SECRET}
EOF
chmod 600 ~/.aws/credentials

cat > ~/.aws/config <<'EOF'
[default]
region = us-east-1
s3 =
  payload_signing_enabled = false

[profile physionet]
region = us-east-1
s3 =
  payload_signing_enabled = false
EOF

echo "wrote ~/.aws/credentials (0600) + ~/.aws/config"
echo
echo "IMPORTANT: unset the placeholder env vars in your shell so they stop shadowing the profile:"
echo "  unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN"
echo
# verify (with env vars neutralized)
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN python3 - <<'PY'
import boto3
from botocore.config import Config
AP="arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point"
try:
    ident=boto3.client("sts", region_name="us-east-1").get_caller_identity()
    print(f"STS OK  account={ident['Account']}  (expect 281627750420)")
except Exception as e:
    print("STS FAILED:", type(e).__name__, str(e)[:140]); raise SystemExit(1)
try:
    s3=boto3.client("s3", region_name="us-east-1", config=Config(s3={'payload_signing_enabled':False}))
    r=s3.list_objects_v2(Bucket=AP, Prefix="EEG/HEEDB_Metadata/", MaxKeys=5)
    print("BDSP ACCESS POINT OK — objects:")
    for o in r.get("Contents",[]): print("   ", o["Key"])
except Exception as e:
    print("BDSP access FAILED:", type(e).__name__, str(e)[:140]); raise SystemExit(1)
PY
echo "READY — HEEDB discovery arm can run: python3 analysis/heedb_bs_discovery.py describe"
