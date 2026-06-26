"""organ_labeling.py -- composite end-organ-damage outcome (protocol amendment).

The PRIMARY outcome is a composite of objectively-labelable postoperative
end-organ injury; the individual organ components are pre-specified SECONDARY
outcomes. Each component uses an objective postoperative lab/outcome threshold
relative to a preoperative baseline, in the same adjudication-free spirit as KDIGO.

Components (config `organ_outcomes`):
  * renal          -- KDIGO creatinine (reuses cohort.labeling)
  * hepatocellular -- AST or ALT >= 3x ULN postop (excl. liver/biliary/transplant
                      surgery, where transaminitis is the expected surgical target)
  * cholestatic    -- bilirubin >= 2x ULN postop (same exclusions)
  * coagulation_plt-- postop platelet nadir < 100 OR >=50% fall from baseline
  * coagulation_inr-- postop INR >= 1.5 (flagged: confounded by anticoagulation)
  * hypoperfusion  -- postop lactate >= 4 (flagged: sicker cases get postop lactate)
  * mortality      -- in-hospital death

NOT included: myocardial injury (VitalDB open labs have no troponin/CK),
respiratory failure (postop ABG too sparse), neurologic (uncoded). These are
stated limitations, not silently dropped.

Component labels MAY use postoperative data by definition; no postoperative value
may become a model FEATURE (Sec 11 firewall, enforced in features/base.py).
stdlib only -- operates on already-parsed lab series so it unit-tests offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vitaldb_aki.cohort.labeling import label_case


@dataclass(frozen=True)
class OrganLabel:
    caseid: str
    composite: int | None                       # 1/0, None if wholly unlabelable
    components: dict[str, int | None]            # per-organ 1/0/None
    fired: list[str] = field(default_factory=list)  # which components were positive


def _peak(series: list[float]) -> float | None:
    return max(series) if series else None


def _nadir(series: list[float]) -> float | None:
    return min(series) if series else None


def label_organs(
    caseid: str,
    optype: str | None,
    baselines: dict[str, float | None],          # analyte -> most-recent preop value
    postop: dict[str, list[float]],              # analyte -> postop values within window
    death_inhosp: bool,
    renal_inputs: dict[str, Any],                # for the KDIGO call
    cfg: dict[str, Any],
) -> OrganLabel:
    """Apply every enabled component, then OR into the composite."""
    oc = cfg["organ_outcomes"]
    uln = oc["ULN"]
    comps: dict[str, int | None] = {}

    for name, spec in oc["components"].items():
        if not spec.get("enabled", True):
            continue
        comps[name] = _label_component(name, spec, optype, baselines, postop,
                                       death_inhosp, renal_inputs, uln, cfg)

    # Labelability (mirrors the renal cohort's "require a postop creatinine"):
    # death is always an observed end-organ outcome, but a LIVING patient is only
    # labelable if at least one organ was actually MEASURED postop -- otherwise we
    # have no evidence of injury or its absence and must not score it 0 (that would
    # be a measurement-bias false negative). Mortality alone does not make a living
    # case labelable.
    died = comps.get("mortality") == 1
    lab_observed = any(v is not None for k, v in comps.items() if k != "mortality")
    if died:
        composite: int | None = 1
    elif lab_observed:
        composite = 1 if any(v == 1 for v in comps.values()) else 0
    else:
        composite = None                        # alive, no postop organ measurement
    fired = [k for k, v in comps.items() if v == 1]
    return OrganLabel(caseid, composite, comps, fired)


def _excluded(spec: dict, optype: str | None) -> bool:
    ex = spec.get("exclude_optypes") or []
    return bool(optype) and any(optype.strip() == e for e in ex)


def _label_component(name, spec, optype, baselines, postop, death_inhosp,
                     renal_inputs, uln, cfg) -> int | None:
    src = spec.get("source")
    if src == "kdigo":
        res = label_case(renal_inputs["caseid"], renal_inputs["baseline"],
                         renal_inputs["baseline_source"], renal_inputs["postop_cr"],
                         cfg["kdigo"])
        return res.aki                      # None if unlabelable
    if src == "death_inhosp":
        return 1 if death_inhosp else 0     # always labelable

    analytes = spec.get("analytes", [])
    vals: list[float] = []
    for a in analytes:
        vals += postop.get(a, [])
    rule = spec["rule"]

    if rule == "peak_ge_mult_uln":
        if _excluded(spec, optype):
            return None                     # injury is the surgical target here
        if not vals:
            return None
        thr = spec["mult_uln"] * float(uln[analytes[0]])
        return 1 if _peak(vals) >= thr else 0
    if rule == "peak_ge":
        if not vals:
            return None
        return 1 if _peak(vals) >= float(spec["threshold"]) else 0
    if rule == "nadir_below_or_drop":
        post = postop.get(analytes[0], [])
        if not post:
            return None
        nad = _nadir(post)
        if nad < float(spec["nadir_below"]):
            return 1
        base = baselines.get(analytes[0])
        if base and nad <= (1.0 - float(spec["drop_frac_from_baseline"])) * base:
            return 1
        return 0
    raise ValueError(f"unknown rule {rule!r} for component {name!r}")
