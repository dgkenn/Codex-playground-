#!/usr/bin/env bash
# Credential bootstrap for this project — runs at session start. NO SECRETS IN THIS REPO.
#
# ============================================================================================
# HOW TO MAKE CREDENTIALS DURABLE ACROSS CLAUDE SESSIONS
# ============================================================================================
# Containers are ephemeral; anything written to ~ can vanish when one is reclaimed. The durable
# store is the **Claude Code web environment's environment-variable / secret settings**, which
# are attached to the environment rather than to a session. Set the variables below there once
# and every future session — yours or another Claude's — gets them automatically.
#
#   Environment settings → Environment variables:
#
#     BDSP_AWS_ACCESS_KEY_ID       AKIA...              (HEEDB / I-CARE / MORGOTH on S3)
#     BDSP_AWS_SECRET_ACCESS_KEY   <40-char secret>
#     NEDC_SSH_KEY_B64             <base64 of the private key>   (TUH, optional — see below)
#     NEDC_SSH_USER                nedc-tuh-eeg         (optional; defaults to this)
#
# To produce NEDC_SSH_KEY_B64 on your own machine:
#     base64 -w0 ~/.ssh/id_ed25519      # macOS: base64 -i ~/.ssh/id_ed25519 | tr -d '\n'
# Base64 because environment variables do not carry multi-line values reliably.
#
# WHY CUSTOM NAMES. The container ships AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY as 14-char
# agent-proxy PLACEHOLDERS, and boto3 puts environment variables ahead of profiles in its
# resolution chain — so real credentials under those names get shadowed or collide. BDSP_AWS_*
# sidesteps that entirely. Analyses must still run through scripts/heedb_run.sh, which unsets
# the placeholders for the child process.
#
# THIS SCRIPT NEVER PRINTS A SECRET. It reports presence and whether the credential works —
# never a value.
# ============================================================================================
set -uo pipefail

say() { echo "[bdsp_bootstrap] $*"; }

# ---------------------------------------------------------------------------- AWS / BDSP ----
KEY_ID="${BDSP_AWS_ACCESS_KEY_ID:-}"
SECRET="${BDSP_AWS_SECRET_ACCESS_KEY:-}"

probe_aws() {
  env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN python3 - <<'PY' 2>/dev/null
import boto3
from botocore.config import Config
boto3.client('s3', region_name='us-east-1',
             config=Config(s3={'payload_signing_enabled': False})).list_objects_v2(
    Bucket='arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point',
    Prefix='EEG/HEEDB_Metadata/', MaxKeys=1)
PY
}

if [ -n "$KEY_ID" ] && [ -n "$SECRET" ]; then
  mkdir -p ~/.aws; umask 077
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
  if probe_aws; then say "AWS: written from BDSP_AWS_* and VERIFIED against the BDSP access point."
  else say "AWS: written from BDSP_AWS_* but VERIFICATION FAILED — check the key/secret."; fi
else
  # Absent BDSP_AWS_* does NOT mean no access: ~/.aws/credentials often survives from an earlier
  # session. Announcing "unavailable" without probing cost a session's work once — every script
  # got 403 from the placeholder env keys, which reads exactly like expiry, while valid keys sat
  # on disk. So probe before giving up.
  if [ -f ~/.aws/credentials ] && probe_aws; then
    say "AWS: BDSP_AWS_* not set, but ~/.aws/credentials from an earlier session WORKS."
    say "AWS: set BDSP_AWS_* in the environment settings to make this durable."
  else
    say "AWS: no working credentials — HEEDB/I-CARE/MORGOTH unavailable. Set BDSP_AWS_* in the" >&2
    say "AWS: Claude Code web environment's environment-variable settings." >&2
  fi
fi

# ---------------------------------------------------------------------------- NEDC / TUH ----
# NOTE ON SCOPE, so nobody spends a session on this by mistake: the TUH EEG Corpus carries
# **no linked outcome data** (its manifest is recording_id, patient_id, edf_path, sfreq, age,
# sex — see config.yaml and ledger R321). It therefore CANNOT replicate any outcome
# association, including the aetiology reversal. It can only validate a *measurement* against
# a clinician label at a different health system. Wire it up if that is what you want.
NEDC_USER="${NEDC_SSH_USER:-nedc-tuh-eeg}"
if [ -n "${NEDC_SSH_KEY_B64:-}" ]; then
  mkdir -p ~/.ssh; umask 077
  if printf '%s' "$NEDC_SSH_KEY_B64" | base64 -d > ~/.ssh/id_ed25519 2>/dev/null \
     && [ -s ~/.ssh/id_ed25519 ] && head -1 ~/.ssh/id_ed25519 | grep -q "BEGIN.*PRIVATE KEY"; then
    chmod 600 ~/.ssh/id_ed25519
    say "NEDC: private key materialized to ~/.ssh/id_ed25519 (mode 600), user '${NEDC_USER}'."
  else
    rm -f ~/.ssh/id_ed25519
    say "NEDC: NEDC_SSH_KEY_B64 did not decode to a private key — check the base64." >&2
  fi
fi

if [ -f ~/.ssh/id_ed25519 ]; then
  missing=""
  command -v rsync >/dev/null 2>&1 || missing="rsync"
  command -v ssh   >/dev/null 2>&1 || missing="${missing:+$missing and }ssh"
  if [ -n "$missing" ]; then
    say "NEDC: key present but ${missing} is NOT INSTALLED in this container, and apt cannot"
    say "NEDC: reach the package mirrors here. TUH transport needs a host that has them."
  else
    say "NEDC: key present and rsync/ssh available — TUH transport is possible."
  fi
fi

exit 0   # never fatal: VitalDB and any cached-data work continues regardless
