# Feasibility test — "occult vasopressor dependence at normal pressure" (the novel top-tier angle)

After Round 2 killed the "stable patient trait" framing, the one remaining genuinely-novel angle
(neither VIS nor the dead trait) was the control-theory core sharpened into a testable, clinically
resonant claim:

> **Occult vasopressor dependence at normal pressure.** Because intraoperative/ICU MAP is feedback-
> regulated to target, two patients at the *same at-goal MAP* can have very different vasopressor
> requirements — and the requirement, not the reassuring pressure, carries the risk. Pressure-based
> monitoring misses the high-requirement patient.

This is novel because it is a statement about the **information content of a regulated vs unregulated
signal** (and a specific monitoring error), not a severity score (VIS) and not a cross-encounter trait.

## Feasibility verdict: NOT supported in the testable (intraoperative) setting
The only available data that can test this at scale on a hard outcome is INSPIRE (n=130,960, intraop MAP
metric `map_auc_below_65` + `intraop_norepi` + `death_inhosp`). The existing analysis
(cache/external_validation_inspire.json) already provides the decisive numbers:

| Outcome | n | events | MAP-alone AUC | requirement-alone AUC | requirement ΔAUC over MAP+demographics |
|---|---|---|---|---|---|
| in-hospital death | 130,960 | 1,555 | **0.702** | 0.607 | **+0.004** |
| composite organ injury | 130,960 | 13,884 | 0.690 | 0.574 | +0.002 |
| organ_renal | 90,246 | 4,497 | 0.666 | 0.577 | +0.0015 |

- **Norepinephrine is rare intraoperatively** (3,261 / 130,960 ops = 2.5%) — a vasopressor *requirement*
  barely exists in elective surgery, so the exposure is mostly a use/no-use indicator.
- **MAP exposure out-predicts the requirement** for every outcome (death AUC 0.70 vs 0.61). The dose adds
  essentially nothing beyond MAP (ΔAUC ≤ 0.004).
- This is the **opposite** of the occult-dependence prediction. The reason is mechanistic: intraoperatively
  the regulated variable (MAP) IS allowed to dip, so `map_auc_below_65` carries the insult — the
  control-theory premise (MAP held tightly at target → signal moves into the dose) is an **ICU** condition,
  not an elective-surgery one.

## Where the claim COULD still hold (and why it is hard)
The mechanism is most true in the **ICU**, where pressors are titrated to a MAP target and MAP is held
near-constant (VitalDB showed MAP CV 0.09 ≪ dose CV 0.44 in a controlled setting). Testing
"at-target-MAP ICU patients with high requirement have occult excess mortality" needs **per-stay MAP from
MIMIC chartevents** — the ~30 GB table that has been out of scope all along (disk + container-reap
constraints). That is the single remaining path to a potentially novel, top-tier, hard-outcome test; it is
high-effort, reap-prone, and may still return null.

## Net
The disciplined hunt for a novel Anesthesiology-tier angle on *currently-available* data is exhausted:
- trait — dead (cross-encounter ICC 0.07, Round 2);
- dose→mortality — real but known (VIS);
- occult-dependence intraop (INSPIRE) — MAP dominates, requirement ΔAUC +0.004 (this doc);
- occult-dependence in the ICU — requires MIMIC chartevents MAP (not yet attempted).

Recommendation recorded for the user: either (a) invest in the MIMIC-chartevents MAP pull to test the ICU
occult-dependence claim (the one remaining top-tier shot), or (b) accept the honest ceiling and finalize the
rigorous dose→outcome + control-theory + landmark paper at BJA / Anesthesia & Analgesia.
