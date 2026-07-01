#!/usr/bin/env python3
"""
Nurse-PRN-administration preference IV (instrument B) — DESIGN + SCAFFOLD.
STATUS: DATA-BLOCKED in this environment. Requires MIMIC-IV `hosp/emar.csv.gz` (~administration
events, several GB) + `emar_detail`, which are not downloaded (infeasible at the proxy throttle).
Code is written to run the moment emar is present.

DESIGN: for a PRN drug order (benzo/opioid/antipsychotic), the physician ORDER is confounded by
indication, but WHETHER/WHEN the covering nurse administers a given PRN dose is driven by nurse
practice + workload -> as-if-random conditional on the order existing.
  unit of analysis = (patient, active-PRN-order-window)
  treatment D      = >=1 PRN dose actually administered in the window (emar 'Administered' events)
  instrument Z     = the administering nurse's (caregiver_id) leave-one-out PRN-administration rate
  first stage D ~ Z | order/unit FE ; outcome (delirium/resp-failure/fall) ~ Z
  balance: patient severity proxies ~ Z should be ~0 (nurse assignment as-if-random within shift/unit).

WHY IT'S CLEANER: the confounding-by-indication lives in the ORDER (sicker -> ordered); conditioning
on an active order and instrumenting on the NURSE strips that, because nurse rostering is orthogonal
to the individual patient's indication. Analogous to provider-preference IV but at the administration
(second) decision, which is one causal step closer to as-if-random.

REVIEWER ATTACKS: (a) sicker patients assigned to more-experienced/lower-ratio nurses (nurse-patient
non-random) -> condition within unit x shift, test balance; (b) workload confounds both administration
and outcomes (busy shift -> less PRN AND worse monitoring) -> include unit-census/acuity controls;
(c) emar 'Administered' vs 'Not Given' coding fidelity.
"""
import os
SD = '/home/user/Codex-playground-/scratchpad/'
if not os.path.exists(SD + 'emar.csv.gz') and not os.path.exists(SD + 'emar.csv'):
    print('nurse_prn_iv: DATA-BLOCKED — emar not available; design scaffolded, not run.')
    print('To run: stream hosp/emar.csv.gz (caregiver_id + Administered events) + emar_detail, then implement')
    print('the leave-one-out nurse-administration-rate instrument per the module docstring.')
    raise SystemExit(0)
# (implementation would load emar administrations + caregiver_id and run the LOO-nurse-rate IV)
print('emar present — implement nurse-PRN IV here.')
