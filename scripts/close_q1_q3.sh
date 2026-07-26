#!/usr/bin/env bash
# Drive the remaining extraction + analysis chain for Q1 (withdrawal vs refractory shock) and Q3 (what burden
# is a marker of). Sequential on purpose: these tables hold ~1e9 rows and running them concurrently OOM-killed
# the container once already.
set -uo pipefail
cd "$(dirname "$0")/.."
R=scripts/heedb_run.sh
FULL=/tmp/heedb_eeg_all_patients.txt
log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a /tmp/q1q3.log; }

log "=== concept sets ==="
for k in procedure observation; do
  if [ ! -s /tmp/eeg_probe/concept_names_$k.csv ]; then
    $R python analysis/heedb_concept_select.py $k > /tmp/csel_$k.txt 2>&1
    log "concept_select $k -> $(grep -c . /tmp/eeg_probe/concept_ids_$k.txt 2>/dev/null || echo 0) ids"
  fi
done

log "=== procedure_occurrence (concept-id filtered) ==="
rm -f /tmp/eeg_probe/heedb_omop/procedure_life_support.{csv,done.json}
PIDS_FILE=$FULL ID_FILTER_COL=procedure_concept_id \
  ID_FILTER_FILE=/tmp/eeg_probe/concept_ids_procedure.txt \
  $R python analysis/heedb_omop_extract.py procedure_life_support > /tmp/ext_procedure_life_support.log 2>&1
log "procedures: $(wc -l < /tmp/eeg_probe/heedb_omop/procedure_life_support.csv) rows"

log "=== observation (concept-id filtered) ==="
rm -f /tmp/eeg_probe/heedb_omop/observation_goals.{csv,done.json}
PIDS_FILE=$FULL ID_FILTER_COL=observation_concept_id \
  ID_FILTER_FILE=/tmp/eeg_probe/concept_ids_observation.txt \
  $R python analysis/heedb_omop_extract.py observation_goals > /tmp/ext_observation_goals.log 2>&1
log "observations: $(wc -l < /tmp/eeg_probe/heedb_omop/observation_goals.csv) rows"

log "=== Q1 analysis: terminal extubation ==="
$R python analysis/heedb_wlst_procedure.py > /tmp/q1_result.txt 2>&1
log "Q1 exit=$? ; see /tmp/q1_result.txt"

log "=== measurement: NSE (551 parts, the long pole) ==="
rm -f /tmp/eeg_probe/heedb_omop/measurement_nse.{csv,done.json}
PIDS_FILE=$FULL $R python analysis/heedb_omop_extract.py measurement_nse > /tmp/ext_measurement_nse.log 2>&1
log "nse: $(wc -l < /tmp/eeg_probe/heedb_omop/measurement_nse.csv) rows"

log "=== Q3 analysis: burden vs neuron-specific enolase ==="
$R python analysis/heedb_burden_nse.py > /tmp/q3_result.txt 2>&1
log "Q3 exit=$? ; see /tmp/q3_result.txt"
log "=== CHAIN COMPLETE ==="
