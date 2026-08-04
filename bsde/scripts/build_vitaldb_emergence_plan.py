"""Build a DENSE peri-emergence sampling plan for VitalDB, so E102 can ask a within-case question.

WHY THIS IS NOT MOVING A GOALPOST. E90 established a fact about AVAILABILITY -- the self-computed
aperiodic exponent is finite in 75.1 % of peri-emergence windows where BIS is finite in only 29.9 % -- and
its own text names the next question and refuses to answer it: "Whether it should be BELIEVED there is the
next question, not this one." E102 asks exactly that question. It needs windows E90 did not need.

WHY A NEW EXTRACTION IS REQUIRED AND NOT A CONVENIENCE. Counted before designing anything (rule 32): on
`vitaldb_grid.csv` the peri-emergence period (|rel_aneend_s| <= 600 s) holds 902 exponent-finite windows
across 222 cases -- 362 with BIS present, 540 with BIS absent -- but **exactly ONE case has >= 3 windows
in BOTH cells**. The grid is a whole-case sampling grid; it was never dense near the end of anaesthesia.
A present-versus-absent comparison on that table would therefore be almost entirely BETWEEN cases, which
is the one thing it must not be: BIS availability is a property of the case's monitor and its sensor, so a
between-case contrast compares monitors, not windows.

THE PLAN IS BUILT FROM THE CLINICAL RECORD ONLY. Per case, windows every 30 s from 900 s before the
recorded anaesthesia end to 300 s after it -- 41 windows per case. The landmark is `aneend`, taken from
VitalDB's own clinical table; no candidate column, no BIS value and no exponent is consulted in choosing
which cases or which times to sample. Cases are those already present in `vitaldb_grid.csv` with a finite
`meta_aneend_s`, so no new case selection is introduced either.

COST. ~220 cases at 41 windows = ~9,000 windows. The expensive operation is fetching a case's waveform,
which is per case and already paid for these cases in the grid pass, so this is a density increase rather
than a new cohort.

    python bsde/scripts/build_vitaldb_emergence_plan.py
    for k in 0 1 2 3; do
      python bsde/scripts/stream_vitaldb_fine.py --case-shard $k --of 4 \
             --plan bsde/results/vitaldb_emergence_plan.json \
             --out bsde/results/vitaldb_emergence.s$k.csv &
    done; wait
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

PRE_S, POST_S, STEP_S = 900.0, 300.0, 30.0


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(RESULTS, "vitaldb_emergence_plan.json"))
    a = ap.parse_args(argv)

    # aneend, in the recording's own time base, per case -- read from the grid table's metadata only
    end, span = {}, {}
    files = [os.path.join(RESULTS, "vitaldb_grid.csv")] + sorted(
        glob.glob(os.path.join(RESULTS, "vitaldb_grid.s*.csv")))
    seen = 0
    for f in files:
        if not os.path.exists(f):
            continue
        for r in csv.DictReader(open(f, newline="")):
            seen += 1
            c = r.get("meta_caseid")
            ae, t = _f(r.get("meta_aneend_s", "")), _f(r.get("meta_t_s", ""))
            if not c or not math.isfinite(ae):
                continue
            end[c] = ae
            if math.isfinite(t):
                lo, hi = span.get(c, (t, t))
                span[c] = (min(lo, t), max(hi, t))

    plan = {}
    for c, ae in sorted(end.items()):
        lo = max(0.0, ae - PRE_S)
        hi = ae + POST_S
        # do not plan windows beyond the last time the grid pass ever saw for this case plus one step;
        # a planned window past the end of the record is not a missing value, it is a fabricated request
        if c in span:
            hi = min(hi, span[c][1] + STEP_S)
        n = int(math.floor((hi - lo) / STEP_S)) + 1
        if n < 8:
            continue
        plan[c] = [round(lo + i * STEP_S, 3) for i in range(n)]

    json.dump(plan, open(os.path.abspath(a.out), "w"))
    tot = sum(len(v) for v in plan.values())
    print(f"read {seen} grid rows; {len(end)} cases carry a finite aneend")
    print(f"planned {len(plan)} cases, {tot} windows "
          f"({tot / max(1, len(plan)):.1f} per case, step {STEP_S:.0f} s, "
          f"-{PRE_S:.0f}..+{POST_S:.0f} s around aneend) -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
