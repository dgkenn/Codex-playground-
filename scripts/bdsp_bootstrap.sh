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
  # BDSP_AWS_* absent does NOT mean no access. ~/.aws/credentials persists across sessions in this
  # environment, so credentials written by an earlier session are very often still there and still valid.
  # Announcing "unavailable" without looking cost a session's worth of work once: every script got 403 from
  # the placeholder env keys, which reads exactly like expired credentials, while working keys sat on disk.
  # So probe before giving up, with the placeholders neutralized the same way a real run must neutralize them.
  if [ -f ~/.aws/credentials ] && env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN \
       python3 -c "
import boto3
from botocore.config import Config
boto3.client('s3',region_name='us-east-1',config=Config(s3={'payload_signing_enabled':False})).head_object(
    Bucket='arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point',
    Key='EEG/eeg-metadata/S0001_eeg_metadata_2026_04_30.csv')" 2>/dev/null; then
    echo "[bdsp_bootstrap] BDSP_AWS_* not set, but ~/.aws/credentials from an earlier session WORKS."
    echo "[bdsp_bootstrap] HEEDB access IS available. The container's AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY"
    echo "[bdsp_bootstrap] are agent-proxy placeholders and outrank profiles in boto3's chain, so they must be"
    echo "[bdsp_bootstrap] neutralized: run analyses via  scripts/heedb_run.sh python analysis/<script>.py"
  else
    echo "[bdsp_bootstrap] BDSP_AWS_* not set and no working ~/.aws/credentials — HEEDB unavailable." >&2
  fi
  exit 0   # non-fatal either way: VitalDB work continues fine
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
