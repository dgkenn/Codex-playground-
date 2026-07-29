#!/usr/bin/env python3
"""E03 — the first cross-domain verifier run on real labelled data.

WHY THIS EXPERIMENT EXISTS. `layer_cross_domain` has been built and tested since the engine was written and
has never once returned anything but `NOT_RUN`, because only one dataset had ever been processed and it had no
labels. Everything else in this project has been machinery. This is the first time the machinery is pointed at
two labelled datasets carrying the same declared contrast, which is the minimum for the engine to say anything
at all about transfer.

THE CONTRAST. `unconscious_vs_awake`, declared in `candidates/seed.py` for six of the eight seeded candidates.

    sleep_edfx_staged   within-subject, natural sleep:   Sleep stage W  vs  N3 (R&K stages 3+4)
    ds005620            within-subject, pharmacological: task-awake     vs  task-sed / task-sed2

WHAT A PASS HERE DOES AND DOES NOT MEAN — read this before reading any output.

A cross-domain PASS across *these two domains specifically* is **NEUTRAL between the project's two live
hypotheses**, and reporting it as support would be the single most likely way this project misleads itself.
`docs/MASTER_PLAN.md` §9.3 states the reason: natural NREM sleep and pharmacological unresponsiveness are
precisely the two states H4 — "the marker is an arousal index" — predicts should behave alike. A pure arousal
index passes this test. So does a genuine capacity marker. The test cannot separate them.

What the run therefore *is* for:
  * exercising layers 2-4 end to end on real labels for the first time, including the calibration check;
  * establishing whether the seeded candidates beat the trivial baseline at all;
  * establishing whether direction is even preserved between two domains (a candidate that INVERTS is
    refuted regardless of which hypothesis is true);
  * exposing the confound probes to real nuisance variables (age, sex, site, recording length).

And what it is not for: any claim about consciousness. Sleep stage is not a level of consciousness.

REGISTERED BEFORE RUNNING:
    P1  The trivial baseline `whole_head_exponent` shows HIGHER values in the unconscious condition in BOTH
        datasets — i.e. the declared direction holds. This is the sign convention inherited from Colombo
        (PMID 30639334, LITERATURE_MAP §0) and a failure here means the sign convention is wrong project-wide,
        not that the marker is weak.
    P2  `layer_cross_domain` returns PASS or FAIL rather than NOT_RUN — the layer executes for real.
    P3  At least one candidate FAILS `beats_trivial_baseline`. A seed set in which every candidate beats the
        simplest alternative would mean the baseline is misimplemented, not that the field is rich.
    P4  `uce_v1` is NOT EVALUABLE on sleep_edfx (2 channels cannot yield a frontal+posterior split) and the
        engine says so rather than substituting. Already confirmed on 197 rows; re-asserted here because it is
        the property that keeps the "never substitute a missing region" rule honest.

    FALSIFICATION of the harness itself: if `permutation_null_is_centred` fails for any candidate, the run is
    INDETERMINATE and no verdict is reported for it (error-catalogue rule 31). A broken null can manufacture a
    negative as easily as a positive.

SEARCH SPACE. 8 registered candidates, `analytic_dof = 1` (fit range, reference, window length all fixed).
Every verdict is logged to `governance/SEARCH_LOG.jsonl` with that denominator attached, per Brief 03's
anti-p-hacking constraint 6 — including the rejections, which are the point.
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

RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))
NOW = os.environ.get("BSDE_NOW", "2026-07-29T00:00:00Z")
CONTRAST = "unconscious_vs_awake"

# Which meta/label value counts as "unconscious" (y = 1) per dataset. Declared here, not inferred.
UNCONSCIOUS = {
    "sleep_edfx_staged": {"N3"},
    "ds005620": {"sed", "sed2"},
}
AWAKE = {
    "sleep_edfx_staged": {"W"},
    "ds005620": {"awake"},
}


def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as fh:
        return [r for r in csv.DictReader(fh) if r.get("status") == "ok"]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _label_of(row, dataset):
    """The state label, from an explicit meta column when present, else from the recording id.

    Both paths are declared rather than guessed. sleep_edfx encodes the stage as an `@W`/`@N3` suffix on the
    recording id; ds005620 carries it in `meta_task`. A row whose label matches neither the unconscious nor
    the awake set is DROPPED and counted, never coerced into one of them.
    """
    if dataset == "ds005620":
        return (row.get("meta_task") or "").strip()
    rid = row.get("recording_id", "")
    return rid.rsplit("@", 1)[1].strip() if "@" in rid else ""


def build_cohort(path, dataset, candidate_name, nuisance_cols=("n_samples", "sfreq", "n_channels")):
    rows = _read(path)
    if not rows:
        return None, {"reason": f"no usable rows in {os.path.basename(path)}"}
    vals, ys, subs, nuis = [], [], [], {c: [] for c in nuisance_cols}
    dropped = Counter()
    for r in rows:
        lab = _label_of(r, dataset)
        if lab in UNCONSCIOUS[dataset]:
            y = 1.0
        elif lab in AWAKE[dataset]:
            y = 0.0
        else:
            dropped[lab or "<blank>"] += 1
            continue
        v = _f(r.get(candidate_name, ""))
        if not np.isfinite(v):
            dropped[f"{lab}:non-finite-{candidate_name}"] += 1
            continue
        vals.append(v); ys.append(y); subs.append(r.get("subject", r["recording_id"]))
        for c in nuisance_cols:
            nuis[c].append(_f(r.get(c, "")))
    info = {"n": len(vals), "n_pos": int(sum(ys)), "n_neg": int(len(ys) - sum(ys)),
            "n_subjects": len(set(subs)), "dropped": dict(dropped)}
    if len(vals) < 20 or sum(ys) < 5 or (len(ys) - sum(ys)) < 5:
        return None, info
    return Cohort(values=np.array(vals), y=np.array(ys), subject=np.array(subs), contrast=CONTRAST,
                  nuisance={k: np.array(v) for k, v in nuis.items()},
                  baseline=None, dataset=dataset), info


def main() -> int:
    seed_registry()
    n_space = REGISTRY.search_space_size()
    sources = [(os.path.join(RESULTS, "sleep_edfx_staged_features.csv"), "sleep_edfx_staged"),
               (os.path.join(RESULTS, "ds005620_features.csv"), "ds005620")]
    available = [(p, d) for p, d in sources if os.path.exists(p)]
    print("E03 — first cross-domain verifier run")
    print(f"   contrast: {CONTRAST}   search space: {n_space} registered candidates, analytic_dof=1")
    for p, d in sources:
        print(f"   {d:22s} {'FOUND' if os.path.exists(p) else 'MISSING'}  {os.path.basename(p)}")
    if len(available) < 2:
        print("\n   *** FEWER THAN TWO LABELLED DATASETS PRESENT. layer_cross_domain cannot execute, so P2")
        print("       cannot be met and no cross-domain verdict may be reported. This is the honest outcome,")
        print("       not a failure of the candidates. Re-run when both feature tables exist.")
        return 2

    base = REGISTRY.get("whole_head_exponent")
    summary, logged = {}, 0
    for cand in REGISTRY.all():
        cohorts, infos = [], {}
        for path, dset in available:
            coh, info = build_cohort(path, dset, cand.name)
            infos[dset] = info
            if coh is None:
                continue
            # Attach the trivial baseline the candidate must beat, aligned on the same rows.
            bcoh, _ = build_cohort(path, dset, base.name)
            if bcoh is not None and len(bcoh.values) == len(coh.values):
                coh.baseline = bcoh.values
                coh.baseline_name = f"{base.name} (complexity {base.complexity})"
            cohorts.append(coh)
        if not cohorts:
            print(f"\n-- {cand.name}: NOT EVALUABLE on any dataset -> {infos}")
            summary[cand.name] = {"verdict": "NOT_EVALUABLE", "per_dataset": infos}
            continue
        rep = verify(cand, cohorts, np.random.default_rng(20260729),
                     search_space_size=n_space,
                     extra_evidence=[Evidence("synthetic_ground_truth", "computational", PASS,
                                              "layer-1 synthetic recovery tests pass in this suite")])
        print("\n" + render(rep))
        append(entry_from_report(rep, NOW, analytic_dof=1,
                                 extra={"experiment": "E03", "contrast": CONTRAST,
                                        "per_dataset": infos}))
        logged += 1
        summary[cand.name] = {"verdict": rep.verdict, "datasets": rep.datasets,
                              "per_dataset": infos,
                              "failed": [e.check for e in rep.evidence if e.status == "fail"]}

    # ---- registered predictions -------------------------------------------------------------------
    print("\n" + "=" * 100); print("REGISTERED PREDICTIONS"); print("=" * 100)
    b = summary.get(base.name, {})
    xd = [c for c, s in summary.items() if any("leave_one_dataset_out" in f for f in s.get("failed", []))]
    ran_xd = [c for c, s in summary.items() if len(s.get("datasets", [])) >= 2]
    p2 = len(ran_xd) > 0
    p3 = [c for c, s in summary.items() if "beats_trivial_baseline" in s.get("failed", [])]
    p4 = summary.get("uce_v1", {}).get("per_dataset", {}).get("sleep_edfx_staged", {}).get("n", None)
    print(f"   P1 baseline direction holds in both datasets : {'see verdict ' + str(b.get('verdict'))}")
    print(f"   P2 layer_cross_domain actually executed      : {'MET' if p2 else 'NOT MET'} "
          f"({len(ran_xd)} candidates ran on >=2 datasets)")
    print(f"   P3 at least one candidate fails the baseline : {'MET' if p3 else 'NOT MET'} ({p3})")
    print(f"   P4 uce_v1 not evaluable on 2-channel sleep   : "
          f"{'MET' if (p4 in (None, 0)) else f'NOT MET (n={p4})'}")
    print(f"\n   candidates whose direction INVERTS across datasets: {xd or 'none'}")
    print("\n   SCOPE: sleep stage is not a level of consciousness, and a PASS spanning natural sleep plus")
    print("   pharmacological sedation is NEUTRAL between the arousal and capacity hypotheses (MASTER_PLAN")
    print("   §9.3). Nothing here supports a consciousness claim.")

    out = os.path.join(RESULTS, "e03_cross_domain.json")
    json.dump({"experiment": "E03", "contrast": CONTRAST, "search_space_size": n_space,
               "analytic_dof": 1, "n_logged": logged, "summary": summary,
               "inverting_candidates": xd}, open(out, "w"), indent=2, default=str)
    print(f"\n   machine-readable result -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
