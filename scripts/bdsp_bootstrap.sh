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
#     PHYSIONET_USER               <physionet.org login>          (HiRID and any DUA-gated project)
#     PHYSIONET_PASSWORD           <that account's password>
#
# PhysioNet is a SEPARATE credential from BDSP_AWS_*: those authenticate to S3 access points and do
# nothing for physionet.org. Measured 2026-07-28 — the HiRID landing page is 200 unauthenticated,
# every file under /files/ is 403, and s3://physionet-open/ carries no hirid/ prefix because
# credentialed projects are not mirrored there. A DUA approval alone fetches nothing from here.
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

# The same probe with the environment left exactly as an ordinary script would see it.
probe_aws_ambient() {
  python3 - <<'PY' 2>/dev/null
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
    # probe_aws deliberately clears the ambient AWS_* placeholders, so "WORKS" here means the
    # PROFILE works — it says nothing about what an ordinary script sees. On 2026-07-28 that gap
    # cost a run: the bootstrap reported WORKS and the analysis then died with InvalidAccessKeyId,
    # because the container's placeholder AWS_ACCESS_KEY_ID outranks the profile in boto3's
    # resolution chain. So probe the AMBIENT environment too, and if only the cleared one works,
    # neutralize the placeholders for every future shell in this session.
    if ! probe_aws_ambient; then
      say "AWS: the ambient AWS_ACCESS_KEY_ID shadows that profile and does NOT work — this is the"
      say "AWS: InvalidAccessKeyId that reads exactly like expiry (error catalogue rule 36)."
      say "AWS: handled in Python by common/awsenv.py, which every S3 script calls. Nothing to do."
    fi
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

# ---------------------------------------------------------------------------- PhysioNet ----
# HiRID and every other DUA-gated PhysioNet project are fetched over HTTPS with ~/.netrc, NOT with the
# BDSP AWS keys. Measured 2026-07-28: the project landing page returns 200 unauthenticated while every
# file under /files/ returns 403, and the open S3 mirror (s3://physionet-open/) carries no hirid/ prefix.
# So a DUA approval alone changes nothing here without these two variables.
if [ -n "${PHYSIONET_USER:-}" ] && [ -n "${PHYSIONET_PASSWORD:-}" ]; then
  umask 077
  printf 'machine physionet.org login %s password %s\n' \
    "$PHYSIONET_USER" "$PHYSIONET_PASSWORD" > ~/.netrc
  chmod 600 ~/.netrc
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 45 --netrc \
         https://physionet.org/files/hirid/1.1.1/ 2>/dev/null || echo 000)
  case "$code" in
    200) say "PhysioNet: ~/.netrc written and HiRID v1.1.1 is READABLE (HTTP 200)." ;;
    403) say "PhysioNet: ~/.netrc written but HiRID returns 403 — credentials work only if the DUA is" >&2
         say "PhysioNet: approved for THIS account; check physionet.org/settings/credentialing/." >&2 ;;
    401) say "PhysioNet: ~/.netrc written but HiRID returns 401 — wrong username or password." >&2 ;;
    *)   say "PhysioNet: ~/.netrc written; probe returned HTTP $code (network or proxy issue)." >&2 ;;
  esac
elif [ -f ~/.netrc ] && grep -q physionet.org ~/.netrc 2>/dev/null; then
  say "PhysioNet: PHYSIONET_USER/PASSWORD not set, but ~/.netrc from an earlier session exists."
  say "PhysioNet: set them in the environment settings to make this durable."
else
  say "PhysioNet: no credentials — HiRID/SICdb/AmsterdamUMCdb unavailable. Set PHYSIONET_USER and"
  say "PhysioNet: PHYSIONET_PASSWORD in the environment settings (see docs/CREDENTIALS.md)."
fi

exit 0   # never fatal: VitalDB and any cached-data work continues regardless
