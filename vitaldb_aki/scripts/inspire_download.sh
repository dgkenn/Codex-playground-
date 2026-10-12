#!/bin/bash
# inspire_download.sh -- self-healing INSPIRE 1.4.2 downloader (PhysioNet, credentialed
# via ~/.netrc). Resumable (wget -c), single-instance, retries per file, sha-verified.
# External-validation cohort for the VitalDB-AKI findings (external_validation.py).
set -u
cd /home/user/Codex-playground-/ || exit 1
B=https://physionet.org/files/inspire/1.4.2
DEST=vitaldb_aki/cache/inspire_raw
LOG=vitaldb_aki/cache/inspire_download.log
LOCK=vitaldb_aki/cache/inspire_download.lock
mkdir -p "$DEST"
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > "$LOCK"; trap 'rm -f "$LOCK"' EXIT
say "inspire downloader start pid=$$"

FILES="CHANGELOG.txt LICENSE.txt department.csv parameters.csv schema.csv icd10_excluded.csv \
diagnosis.csv.gz labs.csv.gz medications.csv.gz operations.csv.gz vitals.csv.gz ward_vitals.csv.gz \
SHA256SUMS.txt"

for f in $FILES; do
  tries=0
  while [ ! -s "$DEST/$f" ] && [ $tries -lt 6 ]; do
    tries=$((tries+1))
    say "downloading $f (try $tries)"
    wget --netrc -c -q --tries=3 --timeout=120 -O "$DEST/$f" "$B/$f" \
      && say "  done $f ($(du -h "$DEST/$f" 2>/dev/null | cut -f1))" \
      || { say "  FAILED $f try $tries"; sleep $((2**tries)); }
    # disk guard: if <4G free, stop to protect the running extractions
    avail=$(df --output=avail /home 2>/dev/null | tail -1 | tr -dc '0-9')
    if [ -n "$avail" ] && [ "$avail" -lt 4194304 ]; then
      say "DISK LOW (<4G) -- pausing inspire download to protect extractions"; exit 0
    fi
  done
done

# verify against SHA256SUMS (best-effort; only the data files we pulled)
if [ -s "$DEST/SHA256SUMS.txt" ]; then
  ( cd "$DEST" && sha256sum -c --ignore-missing SHA256SUMS.txt >> "../inspire_download.log" 2>&1 ) \
    && say "SHA256 verify PASS" || say "SHA256 verify had mismatches (see log)"
fi
n=$(ls -1 "$DEST"/*.csv.gz 2>/dev/null | wc -l)
say "INSPIRE DOWNLOAD COMPLETE ($n .csv.gz present)"
echo "{\"gz_files\": $n}" > vitaldb_aki/cache/_inspire_download_done.json
