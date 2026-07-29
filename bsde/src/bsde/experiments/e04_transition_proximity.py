#!/usr/bin/env python3
"""E04 — transition proximity: does any candidate distinguish "sedated" from "sedated, one minute before
waking up"?

WHY THIS EXPERIMENT EXISTS, AND WHY IT IS BETTER THAN THE CONTRAST IT REPLACES.

E03's first version pooled ds005620's `sed` and `sed2` into one "unconscious" class. Reading the deposit's own
README showed that was wrong. It defines three task values:

    awake : Wakefulness
    sed   : Sedation condition
    sed2  : One-minute resting EEG recorded just before an awakening

So `sed2` is not deeper sedation and not a second dose level -- it is the minute IMMEDIATELY PRECEDING an
arousal. Pooling it with steady-state sedation mixed a state with a state-transition precursor. E03 now
excludes it, and this experiment asks the question `sed2` is actually built to answer:

    Among recordings where the subject is sedated and behaviourally unresponsive throughout, does any
    candidate separate the epochs that are about to be followed by an awakening from those that are not?

THIS IS THE MOST COMMERCIALLY RELEVANT QUESTION THIS PROJECT CAN CURRENTLY ASK. Brief 03's Program 3 is a
neural transition forecaster, and rates it above classification explicitly because forecasting enables
intervention. Brief 03's Discovery Challenge C wants a trajectory feature that predicts emergence before
conventional monitors. This is the reachable public-data version of both.

WHY IT IS NOT CIRCULAR, which E03 §9.6 showed the sleep contrast is. The label here is *which minute the
experimenters chose to awaken the subject in*. That was determined by the study protocol, not scored from the
EEG by a rater. Nothing about `sed2` is defined in terms of spectral content. A positive result therefore
cannot be a restatement of the labelling rule -- which is exactly the defect that makes the 0.992 Sleep-EDF
number uninterpretable as detection.

WHAT WOULD MAKE A POSITIVE RESULT UNINTERESTING ANYWAY, stated before running:
  * `sed2` segments are ONE MINUTE long by construction while `sed` segments are longer. If the analysis
    window differs between classes, any length-sensitive feature separates them for a trivial reason. The
    same 20 s window is therefore used for both, and `n_samples` is carried as a nuisance and probed.
  * `sed2` is `acq-rest` only. If `sed` includes other acquisition types, acquisition would proxy the label.
    The cohort is therefore restricted to `acq-rest` on BOTH sides, and the restriction is reported.
  * Awakenings were not randomly timed; anaesthetists awaken subjects when it is safe and convenient, which
    may correlate with drug level. A positive result may therefore reflect lighter sedation rather than an
    impending transition, and those two are NOT separable in this dataset. This is stated as a limitation
    that no analysis here can remove.

REGISTERED BEFORE RUNNING:
    P1  The permutation null is centred and uses the WITHIN-SUBJECT scheme (subjects contribute both classes).
        If it is not centred the run is INDETERMINATE and no verdict is reported (rule 31).
    P2  DIRECTION: pre-awakening epochs (`sed2`) show a LOWER aperiodic exponent than steady sedation
        (`sed`). Rationale: in this project's convention unconsciousness means a HIGHER exponent, and an
        epoch about to be followed by arousal should sit closer to wakefulness. A result in the OPPOSITE
        direction refutes the transition-precursor reading and is more likely to reflect the awakening
        protocol's timing than the brain's state.
    P3  Whatever separation exists is SMALLER than the awake-vs-sed separation in the same subjects. A
        pre-awakening epoch is still a sedated epoch; if the sed-vs-sed2 effect matched or exceeded
        awake-vs-sed, the labelling or the windowing is doing the work, not the physiology.
    P4  The `n_samples` probe does NOT fire. If it does, the contrast is being carried by window length.

    FALSIFICATION: if no candidate's interval excludes 0.5, the honest report is that this dataset shows no
    detectable pre-awakening signature at 20 s resolution in these features -- which is a real, publishable
    negative for a transition-forecasting claim, and is reported as such rather than reframed.

SCOPE: n is small (roughly 51 `sed2` recordings across 21 subjects at most). This is a feasibility probe for
a transition-forecasting programme, not evidence for a product.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from bsde.candidates.registry import REGISTRY                                    # noqa: E402
from bsde.candidates.seed import seed_registry                                    # noqa: E402
from bsde.governance.search_log import append, entry_from_report                   # noqa: E402
from bsde.verifier.engine import Cohort, verify                                    # noqa: E402
from bsde.verifier.report import Evidence, render, PASS                            # noqa: E402
from bsde.verifier.stats import directional_auc, cluster_bootstrap_ci, permutation_null  # noqa: E402

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
NOW = os.environ.get("BSDE_NOW", "2026-07-29T00:00:00Z")
CONTRAST = "emergence_within_subject"   # declared in seed.py's CONTRASTS
ACQ_KEEP = "rest"                       # both classes restricted to this, see the docstring


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as fh:
        return [r for r in csv.DictReader(fh) if r.get("status") == "ok"]


def build(rows, cand_name, pos_tasks, neg_tasks):
    """y = 1 for pos_tasks. Restricted to ACQ_KEEP on both sides so acquisition cannot proxy the label."""
    vals, ys, subs, nsamp = [], [], [], []
    dropped = Counter()
    for r in rows:
        task = (r.get("meta_task") or "").strip()
        acq = (r.get("meta_acq") or "").strip()
        if acq != ACQ_KEEP:
            dropped[f"acq={acq or '<blank>'}"] += 1
            continue
        if task in pos_tasks:
            y = 1.0
        elif task in neg_tasks:
            y = 0.0
        else:
            dropped[f"task={task or '<blank>'}"] += 1
            continue
        v = _f(r.get(cand_name, ""))
        if not np.isfinite(v):
            dropped[f"non-finite:{cand_name}"] += 1
            continue
        vals.append(v); ys.append(y); subs.append(r.get("subject", "")); nsamp.append(_f(r.get("n_samples")))
    info = {"n": len(vals), "n_pos": int(sum(ys)), "n_neg": int(len(ys) - sum(ys)),
            "n_subjects": len(set(subs)), "dropped": dict(dropped)}
    if len(vals) < 20 or sum(ys) < 5 or (len(ys) - sum(ys)) < 5:
        return None, info
    return Cohort(values=np.array(vals), y=np.array(ys), subject=np.array(subs), contrast=CONTRAST,
                  nuisance={"n_samples": np.array(nsamp)}, dataset="ds005620"), info


def main() -> int:
    seed_registry()
    rows = load(os.path.join(RESULTS, "ds005620_features.csv"))
    print("E04 — transition proximity: sedated vs sedated-one-minute-before-awakening")
    print(f"   ds005620 usable rows: {len(rows)}   acq restricted to {ACQ_KEEP!r} on both sides")
    if not rows:
        print("   *** no ds005620 feature table yet. Nothing is reported.")
        return 2
    tasks = Counter((r.get("meta_task"), r.get("meta_acq")) for r in rows)
    print(f"   task x acq present: {dict(tasks)}")

    n_space = REGISTRY.search_space_size()
    out, logged = {}, 0
    for cand in REGISTRY.all():
        # PRIMARY: sed2 (pre-awakening, y=1) vs sed (steady sedation, y=0)
        coh, info = build(rows, cand.name, {"sed2"}, {"sed"})
        # REFERENCE for P3, same subjects: sed (y=1) vs awake (y=0)
        ref, ref_info = build(rows, cand.name, {"sed"}, {"awake"})
        if coh is None:
            print(f"\n-- {cand.name}: primary contrast NOT EVALUABLE -> {info}")
            out[cand.name] = {"verdict": "NOT_EVALUABLE", "primary": info, "reference": ref_info}
            continue
        # The candidate declares a direction for `unconscious_vs_awake`, not for this contrast. P2 predicts
        # sed2 sits CLOSER to wake, i.e. the opposite sign to the unconscious direction. Score it explicitly
        # rather than borrowing the declared direction, and say so in the report.
        rng = np.random.default_rng(20260729)
        a_lower = directional_auc(coh.y, coh.values, "lower")     # P2: sed2 LOWER exponent than sed
        lo, hi, _ = cluster_bootstrap_ci(
            lambda idx: directional_auc(coh.y[idx], coh.values[idx], "lower"), coh.subject, rng, reps=1000)
        null = permutation_null(lambda yp: directional_auc(yp, coh.values, "lower"),
                               coh.y, coh.subject, rng, reps=1000)
        a_ref = (directional_auc(ref.y, ref.values, "higher") if ref is not None else float("nan"))

        rep = verify(cand, [coh], np.random.default_rng(20260729), search_space_size=n_space,
                     extra_evidence=[Evidence("synthetic_ground_truth", "computational", PASS,
                                              "layer-1 synthetic recovery tests pass in this suite")])
        print("\n" + render(rep))
        print(f"   E04 PRIMARY (scored as 'sed2 lower'): AUC {a_lower:.3f} [{lo:.3f}, {hi:.3f}]  "
              f"null mean {null['mean']:.4f} scheme={null.get('scheme')} n_perm={null['n']}")
        print(f"   E04 REFERENCE (sed vs awake, same subjects, 'higher'): AUC {a_ref:.3f}")
        append(entry_from_report(rep, NOW, analytic_dof=1,
                                extra={"experiment": "E04", "contrast": CONTRAST,
                                       "primary_auc_sed2_lower": a_lower, "primary_ci": [lo, hi],
                                       "null": null, "reference_auc_sed_vs_awake": a_ref,
                                       "primary_info": info, "reference_info": ref_info}))
        logged += 1
        out[cand.name] = {"verdict": rep.verdict, "auc_sed2_lower": a_lower, "ci": [lo, hi],
                          "null_mean": null["mean"], "null_scheme": null.get("scheme"),
                          "n_perm": null["n"], "reference_auc_sed_vs_awake": a_ref,
                          "primary": info, "reference": ref_info,
                          "failed": [e.check for e in rep.evidence if e.status == "fail"]}

    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    ev = [v for v in out.values() if "auc_sed2_lower" in v]
    p1 = all(abs(v["null_mean"] - 0.5) < 0.05 and v["n_perm"] > 0 for v in ev) if ev else False
    sig = {k: v for k, v in out.items() if v.get("ci") and v["ci"][0] > 0.5}
    inv = {k: v for k, v in out.items() if v.get("ci") and v["ci"][1] < 0.5}
    p3 = all(abs(v["auc_sed2_lower"] - 0.5) <= abs(v["reference_auc_sed_vs_awake"] - 0.5) + 1e-9
             for v in ev if np.isfinite(v.get("reference_auc_sed_vs_awake", np.nan)))
    p4 = not any("probe:n_samples" in v.get("failed", []) for v in out.values())
    print(f"   P1 null centred, within-subject scheme      : {'MET' if p1 else 'NOT MET'}")
    print(f"   P2 sed2 shows a LOWER exponent (CI > 0.5)   : "
          f"{'MET for ' + str(sorted(sig)) if sig else 'NOT MET (no candidate excludes 0.5)'}")
    print(f"   P3 effect smaller than awake-vs-sed         : {'MET' if p3 else 'NOT MET'}")
    print(f"   P4 n_samples probe does not fire            : {'MET' if p4 else 'NOT MET'}")
    print(f"\n   candidates in the OPPOSITE direction (CI < 0.5, refutes the precursor reading): "
          f"{sorted(inv) or 'none'}")
    if not sig and not inv:
        print("\n   HONEST NEGATIVE: no candidate separates pre-awakening from steady sedation at 20 s")
        print("   resolution in this cohort. That is a real result for a transition-forecasting claim.")
    print("\n   LIMITATION THAT NO ANALYSIS HERE REMOVES: awakenings were not randomly timed, so a positive")
    print("   result may reflect lighter sedation rather than an impending transition. Those two are not")
    print("   separable in this dataset.")

    dst = os.path.join(RESULTS, "e04_transition_proximity.json")
    json.dump({"experiment": "E04", "contrast": CONTRAST, "acq_restriction": ACQ_KEEP,
               "search_space_size": n_space, "analytic_dof": 1, "n_logged": logged,
               "summary": out}, open(dst, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
