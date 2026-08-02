"""Build a DENSE, timing-focused sampling plan for VitalDB around BOTH anaesthesia transitions.

MECHANICAL EXTRACTION (bsde/docs/PROBE_2026_08_02_CHALLENGE_C_TIMING.md), not a registered experiment. This
script only decides WHICH TIMES to sample; it never looks at a candidate, a BIS value or an outcome.

WHY. `vitaldb_grid.csv` samples the whole case on a 300 s grid and has a MEDIAN OF ZERO windows within
+/-10 min of anaesthesia start, and 0 of 250 cases with >=5 (measured in the probe doc). Challenge C --
"seeing a transition before the conventional monitor" -- needs sub-BIS-lag resolution (BIS's own lag is
20-160 s per the literature cited in the probe), so the grid cannot answer it no matter how it is analysed.

THE PLAN IS BUILT FROM THE CLINICAL RECORD ALREADY IN HAND, NOT RE-DERIVED. `meta_anestart_s` and
`meta_aneend_s` are read from the cached `vitaldb_grid.csv` / `vitaldb_grid.s*.csv` tables (per the task
instruction) rather than re-fetched from the VitalDB `/cases` endpoint -- the timing is already known per
case from the existing extraction.

WINDOWS: 10 s window, 10 s stride (no overlap, no gap), from transition-10min to transition+10min, i.e. 121
points per transition per case (-600, -590, ..., +600). Two transitions, both windowed identically, because
loss of consciousness and recovery are not each other's reverse (module docstring, `bsde/src/bsde/ingestion/
vitaldb.py`). `VitalDBTargetedAdapter` drops any planned time < 0 (case-relative), so induction windows on
the 93%+ of cases where `anestart` is itself negative (BIS sensor applied after induction -- documented in
the same module) will mostly not survive into the plan; that is a property of the deposit, not a bug here,
and is reported rather than concealed.

Emits ONE combined plan (case -> sorted, de-duplicated list of times) for the extractor to stream, plus a
separate small JSON recording each case's anestart/aneend so the transition label can be reconstructed
losslessly downstream from `rel_anestart_s`/`rel_aneend_s` (both already carried by the adapter's own
metadata) without threading a label through the ingestion code.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))

PRE_S = 600.0
POST_S = 600.0
STEP_S = 10.0


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _window(center: float) -> list:
    n = int(round((PRE_S + POST_S) / STEP_S)) + 1  # 121
    return [round(center - PRE_S + i * STEP_S, 3) for i in range(n)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(RESULTS, "vitaldb_transitions_plan.json"))
    ap.add_argument("--landmarks-out", default=os.path.join(RESULTS, "vitaldb_transitions_landmarks.json"))
    a = ap.parse_args(argv)

    # anestart/aneend per case, read ONLY from the already-cached grid table(s) -- not re-derived.
    landmark: dict = {}
    files = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
        glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))
    files = [f for f in files if "seed" not in os.path.basename(f)]
    seen = 0
    for f in files:
        if not os.path.exists(f):
            continue
        for r in csv.DictReader(open(f, newline="")):
            seen += 1
            c = r.get("meta_caseid")
            if not c:
                continue
            ast, aet = _f(r.get("meta_anestart_s", "")), _f(r.get("meta_aneend_s", ""))
            if c not in landmark:
                landmark[c] = {"anestart_s": ast, "aneend_s": aet}

    plan: dict = {}
    n_induction_planned = n_induction_kept = 0
    n_emergence_planned = n_emergence_kept = 0
    cases_with_induction_window = 0
    for c, lm in sorted(landmark.items(), key=lambda kv: int(kv[0])):
        ast, aet = lm["anestart_s"], lm["aneend_s"]
        times = set()
        if math.isfinite(ast):
            ind = _window(ast)
            n_induction_planned += len(ind)
            kept = [t for t in ind if t >= 0.0]
            n_induction_kept += len(kept)
            if kept:
                cases_with_induction_window += 1
            times.update(kept)
        if math.isfinite(aet):
            emg = _window(aet)
            n_emergence_planned += len(emg)
            kept = [t for t in emg if t >= 0.0]
            n_emergence_kept += len(kept)
            times.update(kept)
        if times:
            plan[c] = sorted(times)

    json.dump(plan, open(os.path.abspath(a.out), "w"))
    json.dump(landmark, open(os.path.abspath(a.landmarks_out), "w"), indent=2, sort_keys=True)

    tot = sum(len(v) for v in plan.values())
    print(f"read {seen} grid rows from {len(files)} file(s); {len(landmark)} cases carry landmark data")
    print(f"induction window: planned {n_induction_planned} windows, {n_induction_kept} survive t>=0 "
          f"({cases_with_induction_window}/{len(landmark)} cases keep >=1 induction window)")
    print(f"emergence window: planned {n_emergence_planned} windows, {n_emergence_kept} survive t>=0")
    print(f"combined plan: {len(plan)} cases, {tot} total windows "
          f"({tot / max(1, len(plan)):.1f} per case, step {STEP_S:.0f}s) -> {a.out}")
    print(f"landmarks -> {a.landmarks_out}")
    assert len(plan) > 0, "empty plan -- landmark source produced nothing (rule 5)"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
