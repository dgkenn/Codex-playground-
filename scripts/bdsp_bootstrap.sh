#!/usr/bin/env bash
# BDSP/HEEDB credential bootstrap — runs at session start, no secrets in the repo.
#
# Reads the credentials from CUSTOM-NAMED environment variables and materializes
# ~/.aws/credentials. Custom names are deliberate: the container ships AWS_ACCESS_KEY_ID /
# AWS_SECRET_ACCESS_KEY as 14-char agent-proxy PLACEHOLDERS, and boto3's chain puts env vars
# ahead of profiles — so real creds under those names can collide/be shadowed. Using
# BDSP_AWS_* sidesteps that entirely.
#
# SET THESE TWO IN THE CLAUDE CODE WEB ENVIRONMENT'S SECRET/ENV SETTINGS:
#   BDSP_AWS_ACCESS_KEY_ID       = AKIA...
#   BDSP_AWS_SECRET_ACCESS_KEY   = <the 40-char secret>
set -uo pipefail
KEY_ID="${BDSP_AWS_ACCESS_KEY_ID:-}"
SECRET="${BDSP_AWS_SECRET_ACCESS_KEY:-}"

if [ -z "$KEY_ID" ] || [ -z "$SECRET" ]; then
  echo "[bdsp_bootstrap] BDSP_AWS_* not set — HEEDB access unavailable this session." >&2
  exit 0   # non-fatal: VitalDB work continues fine
fi

mkdir -p ~/.aws
umask 077
cat > ~/.aws/credentials <<EOF
[default]
aws_access_key_id = ${KEY_ID}
aws_secret_access_key = ${SECRET}

[physionet]
aws_access_key_id = ${KEY_ID}
aws_secret_access_key = ${SECRET}
EOF
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
chmod 600 ~/.aws/credentials
echo "[bdsp_bootstrap] ~/.aws/credentials written from BDSP_AWS_* env vars."

# verify quietly, with the placeholder env vars neutralized
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN python3 - <<'PY' 2>/dev/null || echo "[bdsp_bootstrap] WARNING: verification failed — check the key/secret."
import boto3
from botocore.config import Config
s3=boto3.client("s3",region_name="us-east-1",config=Config(s3={'payload_signing_enabled':False}))
r=s3.list_objects_v2(Bucket="arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point",
                     Prefix="EEG/HEEDB_Metadata/",MaxKeys=1)
print(f"[bdsp_bootstrap] BDSP access point OK (KeyCount={r.get('KeyCount',0)}).")
PY
