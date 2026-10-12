"""inspire/ -- INSPIRE external-validation stage for the PFDS-Clinical biomarker.

INSPIRE (PhysioNet v1.4.2) is credentialed data (SNUH, ~130k surgeries 2011-2020).
Access requires a PhysioNet account, DUA acceptance, and local data download.
All modules degrade gracefully when credentials / data are absent:
  ``from vitaldb_aki.inspire.client import available; available()`` returns False
  with a printed message, and every downstream function returns an empty / NaN
  result rather than raising.

Sub-modules
-----------
client        -- credentialed PhysioNet data loader (local directory reader)
labeling      -- KDIGO AKI label on INSPIRE creatinine (identical thresholds)
pfds_clinical -- distilled PFDS-Clinical biomarker from 5-min OR vitals + meds
validate      -- external-validation harness (AUROC/AUPRC/calibration/NRI/IDI/DCA)
"""
