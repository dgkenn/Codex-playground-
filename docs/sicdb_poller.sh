#!/bin/bash
# Self-healing SICdb fetcher (same pattern that solved eICU/INSPIRE 403s): poll PhysioNet cheaply until
# access propagates from gated(403)->approved(200), then download the 4 files needed for the cross-method
# Hb transfusion replication, write a READY sentinel. Idempotent; safe to re-run.
cd /home/user/Codex-playground-/scratchpad || exit 1
mkdir -p sicdb_raw
BASE="https://physionet.org/files/sicdb/1.0.6"
LOG=sicdb_poll.log
echo "sicdb poller start $(date -u +%H:%M:%S)" > $LOG
FILES="d_references.csv.gz laboratory.csv.gz medication.csv.gz cases.csv.gz"
# poll up to ~24h (144 x 10min)
for i in $(seq 1 144); do
  code=$(curl -sS --netrc -L -r 0-0 -o /dev/null -w "%{http_code}" "$BASE/d_references.csv.gz" 2>/dev/null)
  echo "$(date -u +%H:%M:%S) attempt $i: access probe HTTP $code" >> $LOG
  if [ "$code" = "200" ] || [ "$code" = "206" ]; then
    echo "ACCESS GRANTED at attempt $i -- downloading" >> $LOG
    ok=1
    for f in $FILES; do
      wget -c -q --netrc --tries=20 --waitretry=10 "$BASE/$f" -O "sicdb_raw/$f" 2>>$LOG || ok=0
      echo "  fetched $f ($(ls -la sicdb_raw/$f 2>/dev/null | awk '{print $5}') bytes)" >> $LOG
    done
    if [ "$ok" = "1" ]; then echo "SICDB_ALLFILES_READY $(date -u +%H:%M:%S)" >> $LOG; touch SICDB_READY; exit 0; fi
    echo "partial download; will retry" >> $LOG
  fi
  sleep 600
done
echo "TIMEOUT: access never propagated in ~24h -- check DUA signed under netrc account + CITI training" >> $LOG
exit 2
