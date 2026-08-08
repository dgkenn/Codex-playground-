#!/usr/bin/env bash
# Fetch a PhysioNet project (open or credentialed) into a local directory.
#
# WHY THIS EXISTS. Credentialed PhysioNet data is Tier 1 in SOP_DATA_ACQUISITION.md -- gated by a form,
# not by a person -- and it is the route this project had been ignoring in favour of emailing authors.
# This script removes every step between "credentials exist" and "data is on disk".
#
# CREDENTIALS ARE NEVER ARGUMENTS AND NEVER LAND IN THE REPO. Set them in the Claude Code web
# environment's environment-variable settings:
#     PHYSIONET_USER        the PhysioNet account username
#     PHYSIONET_PASSWORD    that account's password
#
#   bsde/scripts/physionet_fetch.sh eeg-power-anesthesia 1.0.0 /tmp/eeg_probe/physionet
#   bsde/scripts/physionet_fetch.sh propofol-anesthesia-dynamics 1.0 /tmp/eeg_probe/physionet   # open
#
# Two failure modes that look identical and are not (catalogue rule 8 -- diagnose per credential source):
#   403 with no credentials set  -> the project is restricted and you are anonymous
#   403 WITH credentials set     -> the account exists but has NOT signed THIS project's DUA.
#                                   Credentialed access is PER PROJECT. Holding it for one project
#                                   grants nothing for another.
set -uo pipefail

SLUG="${1:?usage: physionet_fetch.sh <slug> <version> <dest>}"
VER="${2:?version, e.g. 1.0.0}"
DEST="${3:?destination directory}"
URL="https://physionet.org/files/${SLUG}/${VER}/"

mkdir -p "$DEST"

anon_code=$(curl -sS -m 30 -o /dev/null -w '%{http_code}' "$URL" || echo 000)
echo "[physionet] ${SLUG} ${VER}: anonymous HTTP ${anon_code}"

if [ "$anon_code" = "200" ]; then
    echo "[physionet] open project; fetching without credentials"
    wget -q -r -N -c -np -nH --cut-dirs=3 -P "$DEST" "$URL"
elif [ -n "${PHYSIONET_USER:-}" ] && [ -n "${PHYSIONET_PASSWORD:-}" ]; then
    echo "[physionet] restricted; authenticating as \$PHYSIONET_USER"
    wget -q -r -N -c -np -nH --cut-dirs=3 -P "$DEST" \
         --user "$PHYSIONET_USER" --password "$PHYSIONET_PASSWORD" "$URL"
    rc=$?
    if [ $rc -ne 0 ]; then
        echo "[physionet] FAILED (wget rc=$rc). If this is a 403 WITH credentials set, the account has"
        echo "[physionet] not signed the data use agreement for THIS project. Sign it at"
        echo "[physionet]   https://physionet.org/content/${SLUG}/${VER}/"
        exit "$rc"
    fi
else
    echo "[physionet] REFUSING: project is restricted and PHYSIONET_USER/PHYSIONET_PASSWORD are unset."
    echo "[physionet] Set them in the environment settings; do not pass secrets on the command line."
    exit 2
fi

n=$(find "$DEST" -type f | wc -l)
echo "[physionet] done: ${n} file(s) under ${DEST}"
